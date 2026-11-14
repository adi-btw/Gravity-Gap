"""E3 test planner (C12): rank candidate partial-gravity tests (plan/03 §4).

Candidate grid: g in {0.165 g, 0.38 g} (1.62, 3.71 m/s^2), P in {8.2, 10.2, 14.7}
psia, O2 in {0.21, 0.265, 0.30, 0.34}, u_f in {0, 5, 10, 20} cm/s, for each
fitted metric M1-M3 (M4/M5 are categorical rule tables with no band width).

Score = band_width x habitat_weight x mixed_fraction, where
    band_width     90% band width from engine.bounds.predict (probabilities: hi-lo;
                   quantities: (hi-lo)/estimate, capped at 1). A gated candidate
                   (no evidence) gets band_width 1, the maximum.
    habitat_weight max over target habitats h of w_h * exp(-d^2/2), d = atmosphere
                   distance; w = 1.0 (8.2 psia / 0.34, lunar and Mars), 0.7
                   (10.2 / 0.265, exploration), 0.4 (14.7 / 0.21, ISS). Exactly
                   those values at the anchor atmospheres, smooth in between.
    mixed_fraction Monte Carlo share of samples in the mixed regime (L = 10 mm).

Greedy top-k: after each pick, every remaining candidate's score is multiplied by
(1 - s * K), K = exp(-D^2/2) a kernel over atmosphere distance, gravity and flow
(D below), s = 1 for the same metric and 0.3 for another metric (one test campaign
informs neighbouring metrics weakly). This models "the chosen test collapses local
uncertainty" and keeps the list diverse.

Candidate type "dilution" (R2, ADR-0006): M1 with CO2 0.2/0.3/0.4 replacing N2 at 8.2 psia /
34% O2, g 1.62 and 3.71, every vent speed. Scored with the same formula (gated -> band_width 1);
the re-scoring kernel also includes the CO2 fraction (scale 0.10). Items carry ``type`` and ``co2``.

Run ``python -m engine.planner`` to write artifacts/planner.json.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

import numpy as np

from engine import __version__
from engine.bounds import DILUENT_SCALE, FITTED, METRICS, diluted_o2_range, json_safe, predict
from engine.montecarlo import sample_physics
from engine.physics import G0, PSIA_PER_ATM, RI_FORCED_MAX, atmosphere_distance

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = ROOT / "artifacts" / "planner.json"
CATALOG_PATH = ROOT / "artifacts" / "catalog.json"

G_VALUES = [1.62, 3.71]
P_VALUES = [8.2, 10.2, 14.7]
O2_VALUES = [0.21, 0.265, 0.30, 0.34]
U_VALUES = [0.0, 5.0, 10.0, 20.0]
L_MM = 10.0
HABITAT_TARGETS = [
    {"p_psia": 8.2, "o2": 0.34, "weight": 1.0, "label": "lunar/Mars base 8.2 psia / 34% O2"},
    {"p_psia": 10.2, "o2": 0.265, "weight": 0.7, "label": "exploration vehicle 10.2 psia / 26.5% O2"},
    {"p_psia": 14.7, "o2": 0.21, "weight": 0.4, "label": "ISS 14.7 psia / 21% O2"},
]
SAME_METRIC_REDUCTION = 1.0
OTHER_METRIC_REDUCTION = 0.3
G_SCALE = 2.0  # m/s^2 per kernel unit
U_SCALE = 10.0  # cm/s per kernel unit
METRIC_INVESTIGATION = {"M1": "PSI-69", "M2": "PSI-69", "M3": "PSI-159"}
# R2 / ADR-0006 candidate type "dilution at high O2": FLEX diluted droplets only at 13-25% O2,
# so a suppression (CO2) number at the exploration atmosphere is gated. Same score formula.
DILUTION_CANDIDATES = {"metric": "M1", "diluent": "co2", "fractions": [0.2, 0.3, 0.4],
                       "p_psia": 8.2, "o2": 0.34, "g_m_s2": G_VALUES}


def habitat_weight(p_psia: float, o2: float) -> tuple[float, str]:
    best, label = 0.0, ""
    for h in HABITAT_TARGETS:
        d = atmosphere_distance(o2, p_psia / PSIA_PER_ATM, h["o2"], h["p_psia"] / PSIA_PER_ATM)
        w = h["weight"] * math.exp(-0.5 * d * d)
        if w > best:
            best, label = w, h["label"]
    return best, label


def _band_width(res: dict) -> float:
    if not res["applicable"] or res["band90"] is None:
        return 1.0
    lo, hi = res["band90"]
    if res["kind"] == "probability":
        return float(hi - lo)
    est = res["estimate"]
    return float(min((hi - lo) / max(abs(est), 1e-9), 1.0))


def _kernel(a: dict, b: dict) -> float:
    d_atm = atmosphere_distance(a["o2"], a["p_psia"] / PSIA_PER_ATM, b["o2"], b["p_psia"] / PSIA_PER_ATM)
    dg = (a["g_m_s2"] - b["g_m_s2"]) / G_SCALE
    du = (a["u_cm_s"] - b["u_cm_s"]) / U_SCALE
    dc = (a.get("co2", 0.0) - b.get("co2", 0.0)) / DILUENT_SCALE  # ADR-0006 diluent scale
    return math.exp(-0.5 * (d_atm * d_atm + dg * dg + du * du + dc * dc))


def _load_catalog() -> list[dict]:
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["investigations"]
    except (OSError, ValueError, KeyError):
        return []


def _extends(c: dict, catalog: list[dict]) -> list[str]:
    """Training investigation first, then catalog investigations whose tested
    O2 and pressure ranges cover (within a small margin) the candidate."""
    out = [METRIC_INVESTIGATION[c["metric"]]]
    p_atm = c["p_psia"] / PSIA_PER_ATM
    for rec in catalog:
        if not rec.get("is_combustion"):
            continue
        cond = rec.get("conditions") or {}
        o2r, pr = cond.get("o2"), cond.get("pressure_atm")
        if not o2r or not pr:
            continue
        if o2r[0] - 0.02 <= c["o2"] <= o2r[1] + 0.02 and pr[0] * 0.9 <= p_atm <= pr[1] * 1.1:
            if rec["id"] not in out:
                out.append(rec["id"])
    return out


def _rationale(c: dict, res: dict, parts: dict, hab_label: str) -> str:
    g_rel = c["g_m_s2"] / G0
    body = "Moon" if abs(c["g_m_s2"] - 1.62) < 0.01 else "Mars"
    bw = parts["band_width"]
    if c.get("type") == "dilution":
        rng = diluted_o2_range(c["metric"], "co2")
        rng_txt = f"{100 * rng[0]:.0f}-{100 * rng[1]:.0f}% O2" if rng else "no O2 level"
        state = ("so the suppression calculator has no evidence here (honesty gate)" if not res["applicable"]
                 else f"and the current 90% band is {bw:.2f} wide")
        return (f"Dilution at high O2: {METRICS[c['metric']]['label']} with {100 * c['co2']:g}% CO2 replacing "
                f"nitrogen at {body} gravity ({g_rel:.3f} g), {c['p_psia']:g} psia / {100 * c['o2']:g}% O2, vent "
                f"{c['u_cm_s']:g} cm/s. FLEX tested CO2 dilution only at {rng_txt}, {state}; "
                f"{100 * parts['mixed_fraction']:.0f}% of physics samples are in the mixed regime, and the "
                f"atmosphere is the {hab_label} target (weight {parts['habitat_weight']:.2f}). A droplet test "
                f"here tells whether CO2 suppression works the same way in oxygen-enriched cabin air.")
    if res["applicable"]:
        unc = f"the current 90% band is {bw:.2f} wide" + (" (relative)" if res["kind"] == "quantity" else "")
    else:
        unc = "there is no microgravity evidence at this atmosphere (honesty gate)"
    return (f"{METRICS[c['metric']]['label']} at {body} gravity ({g_rel:.3f} g), {c['p_psia']:g} psia / "
            f"{100 * c['o2']:g}% O2, vent {c['u_cm_s']:g} cm/s: {unc}, "
            f"{100 * parts['mixed_fraction']:.0f}% of physics samples are in the mixed regime where neither 0 g "
            f"nor 1 g data apply, and the atmosphere is close to the {hab_label} target "
            f"(weight {parts['habitat_weight']:.2f}).")


def candidates(n: int = 2000, seed: int = 0, n_boot: int = 500) -> list[dict]:
    out = []
    mc_cache: dict = {}
    for g, p, o2, u in product(G_VALUES, P_VALUES, O2_VALUES, U_VALUES):
        key = (g, p, o2, u)
        if key not in mc_cache:
            mc_cache[key] = sample_physics(g, p, o2, u, L_MM, n=n, seed=seed)["regime_fractions"]["mixed"]
        mixed = mc_cache[key]
        hw, hab_label = habitat_weight(p, o2)
        for m in FITTED:
            res = predict(m, g, p, o2, u, L_MM, n=n, seed=seed, n_boot=n_boot)
            parts = {"band_width": _band_width(res), "habitat_weight": hw, "mixed_fraction": mixed}
            c = {"g_m_s2": g, "p_psia": p, "o2": o2, "u_cm_s": u, "metric": m, "type": "atmosphere",
                 "co2": 0.0, "score": parts["band_width"] * hw * mixed, "parts": parts,
                 "_res": res, "_hab": hab_label}
            out.append(c)
    dc = DILUTION_CANDIDATES
    p, o2, m = dc["p_psia"], dc["o2"], dc["metric"]
    hw, hab_label = habitat_weight(p, o2)
    for g, u, f in product(dc["g_m_s2"], U_VALUES, dc["fractions"]):
        mixed = mc_cache[(g, p, o2, u)]
        res = predict(m, g, p, o2, u, L_MM, n=n, seed=seed, n_boot=n_boot, **{dc["diluent"]: f})
        parts = {"band_width": _band_width(res), "habitat_weight": hw, "mixed_fraction": mixed}
        out.append({"g_m_s2": g, "p_psia": p, "o2": o2, "u_cm_s": u, "metric": m, "type": "dilution",
                    "co2": f, "score": parts["band_width"] * hw * mixed, "parts": parts,
                    "_res": res, "_hab": hab_label})
    return out


def plan_tests(top_k: int = 10, n: int = 2000, seed: int = 0, n_boot: int = 500) -> list[dict]:
    pool = candidates(n=n, seed=seed, n_boot=n_boot)
    catalog = _load_catalog()
    current = [c["score"] for c in pool]
    picked: list[dict] = []
    used = set()
    for rank in range(1, top_k + 1):
        best = max((i for i in range(len(pool)) if i not in used), key=lambda i: (current[i], -i), default=None)
        if best is None:
            break
        used.add(best)
        c = pool[best]
        picked.append({
            "rank": rank,
            "g_m_s2": c["g_m_s2"], "p_psia": c["p_psia"], "o2": c["o2"], "u_cm_s": c["u_cm_s"],
            "metric": c["metric"],
            "type": c["type"], "co2": c["co2"],
            "score": current[best],
            "base_score": c["score"],
            "parts": c["parts"],
            "rationale": _rationale(c, c["_res"], c["parts"], c["_hab"]),
            "extends": _extends(c, catalog),
        })
        for i, other in enumerate(pool):
            if i in used:
                continue
            s = SAME_METRIC_REDUCTION if other["metric"] == c["metric"] else OTHER_METRIC_REDUCTION
            current[i] *= 1.0 - s * _kernel(c, other)
    return json_safe(picked)


def design_implications(n: int = 2000, seed: int = 0) -> list[str]:
    """Plain-language engineering numbers derived from the physics (not the fits)."""
    out = []
    ri_factor = 1.0 / math.sqrt(RI_FORCED_MAX)  # Ri < 0.1  <=>  u_f > u_b / sqrt(0.1)
    for name, g in (("lunar", 1.62), ("Mars", 3.71)):
        mc = sample_physics(g, 8.2, 0.34, 0.0, L_MM, n=n, seed=seed)
        u_b50 = mc["summary"]["u_b"]["p50"]
        u_b95 = mc["summary"]["u_b"]["p95"]
        out.append(
            f"At {name} gravity a 10 mm flame stays forced-flow dominated (Ri < 0.1, where microgravity "
            f"evidence transfers) only above about {u_b50 * ri_factor:.0f} cm/s of vent flow at the "
            f"median coefficients, and above {u_b95 * ri_factor:.0f} cm/s to cover 95% of the Monte Carlo "
            f"samples (u_b p50 {u_b50:.1f} cm/s, p95 {u_b95:.1f} cm/s). Typical cabin vents (5-20 cm/s) "
            f"are far below this, so {name} fires are mixed or buoyancy-dominated."
        )
        out.append(
            f"At {name} gravity a 10 mm flame becomes buoyancy-dominated (Ri > 10) when the vent flow is "
            f"below about {u_b50 / math.sqrt(10):.1f} cm/s (median coefficients): turning ventilation off "
            f"does not create a microgravity-like quiescent flame."
        )
    out.append(
        "Droplet and gas-burner extinction evidence (M1-M3) has no flow variable, so for partial-gravity "
        "habitats its bands are widened rather than shifted; tests in the mixed regime at 8.2 psia / 34% O2 "
        "are the most valuable way to narrow them."
    )
    return out


def main() -> None:
    items = plan_tests()
    doc = {
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": ("score = band_width x habitat_weight x mixed_fraction; greedy top 10 with kernel "
                   "re-scoring over atmosphere distance, gravity (2 m/s^2), vent flow (10 cm/s) and CO2 "
                   "fraction (0.10)"),
        "grid": {"g_m_s2": G_VALUES, "p_psia": P_VALUES, "o2": O2_VALUES, "u_cm_s": U_VALUES,
                 "L_mm": L_MM, "metrics": list(FITTED)},
        "candidate_types": {
            "atmosphere": "every grid point x metric M1-M3, habitat diluent N2",
            "dilution": {**DILUTION_CANDIDATES, "u_cm_s": U_VALUES,
                         "why": "FLEX dilution tests were all at 13-25% O2; CO2 suppression at 34% O2 is gated"},
        },
        "habitat_targets": HABITAT_TARGETS,
        "items": items,
        "design_implications": design_implications(),
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(json_safe(doc), indent=2, allow_nan=False), encoding="utf-8")
    print(f"wrote {ARTIFACT_PATH}")
    for it in items[:10]:
        print(f"  #{it['rank']} {it['type']} {it['metric']} co2={it['co2']} g={it['g_m_s2']} p={it['p_psia']} o2={it['o2']} "
              f"u={it['u_cm_s']} score={it['score']:.4f} extends={it['extends']}")
    for s in doc["design_implications"]:
        print("  -", s)


if __name__ == "__main__":
    main()
