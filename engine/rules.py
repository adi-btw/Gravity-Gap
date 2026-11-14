"""E2 rule-table metrics M4 and M5 (plan/03 §3), returning the bounds.predict shape.

    predict_m4(g_m_s2, p_psia, o2, u_cm_s, L_mm, n=2000, seed=0, material=None) -> dict
    predict_m5(g_m_s2, p_psia, o2, u_cm_s, L_mm, n=2000, seed=0, fuel=None, nozzle_mm=None) -> dict
    python -m engine.rules   -> writes artifacts/rules.json, prints the preset outputs

Both use engine.montecarlo.sample_physics for the regime fractions and the u_eff
distribution (03 §2.4 bridge: partial g ~ microgravity response at u_eff).

M4 "Solid material burn extent" (kind "category")
    Data: data/clean/psi_saffire_ug_vs_1g.csv, SAFFIRE-II (PSI-99), 9 samples burned in
    microgravity (Cygnus) and in 1 g, both at ~22% O2 and 20 cm/s forced flow. The
    microgravity category comes from psi_tests.csv ``outcome``; the 1 g category from the
    1 g burned fraction (0 -> no_sustained_burn, 1 -> complete_burn, else partial_burn).
    Per material the outcome is the plurality over its samples, ties -> the more severe.
    Samples with ``needs_manual_review`` (PMMA, PMMA & Nomex: footnotes / mixed material)
    make that material's confidence "low". material=None -> "any" = most severe outcome
    over all materials (conservative envelope).
    Gate: applicable only for 0.20 <= O2 <= 0.24 and 0.9 <= P <= 1.1 atm. SAFFIRE tested
    only ~22% O2 at ~1 atm cabin pressure (pressure not in the table), so e.g. lunar
    34% O2 / 8.2 psia is extrapolation -> applicable False, estimate None.
    Estimate: forced fraction >= 0.9 -> microgravity outcome; buoyant fraction >= 0.9 ->
    1 g outcome; otherwise (mixed) -> the shared outcome if both agree, else the string
    "between" with band90 = [less severe, more severe] and transfer.confidence "low".
    Valid estimates: no_sustained_burn | partial_burn | complete_burn | between | None.
    band90 = [least, most severe] category reachable by >= 5% of the samples.
    ref_0g = microgravity outcome, ref_1g = 1 g outcome (the one metric with a real 1 g
    reference). nonmonotonic_flag: u_eff p05 < 10 cm/s, the low-flow region where thin-
    solid flame spread peaks or quenches ("Goldilocks" zone, PSI-62 hypothesis).

M5 "Supported coflow window" (kind "probability", unit "fraction")
    Data: SPICE (PSI-107) rows in psi_tests.csv where a flame existed (ignited True),
    excluding loss-of-signal rows and rows flagged with a negative air rate. Window per
    fuel and nozzle = [min, max] observed flow_speed_cm_s. fuel/nozzle None -> pooled.
    estimate = fraction of the habitat's u_eff samples inside the window (0..1); the
    window itself is in transfer.basis and in artifacts/rules.json. band90 = the range of
    that fraction over the sub-windows pooled (nozzles, or fuels x nozzles) widened by the
    90% binomial Monte Carlo error. ref_0g: u_eff = u_f; ref_1g: bridge at g = 9.81.
    SPICE records no O2 or pressure (flames burned in ISS cabin air, assumed ~21% O2 /
    ~1 atm), so applicable only for 0.19 <= O2 <= 0.235 and 0.9 <= P <= 1.1 atm, and
    transfer.confidence is at most "medium". nonmonotonic_flag: the partial-g fraction is
    outside [ref_0g, ref_1g] by more than 0.05.
"""
from __future__ import annotations

import functools
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from engine.montecarlo import C_B_RANGE, DT_OVER_T_RANGE, K_RANGE, L_FACTOR_RANGE, sample_physics
from engine.physics import PSIA_PER_ATM, atmosphere_distance, evaluate

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
SAFFIRE_CSV = CLEAN / "psi_saffire_ug_vs_1g.csv"
TESTS_CSV = CLEAN / "psi_tests.csv"
PSI62_JSON = ROOT / "data" / "psi_metadata" / "PSI-62.json"
OUT = ROOT / "artifacts" / "rules.json"
RULES_VERSION = "1.0.0"

CATEGORIES = ("no_sustained_burn", "partial_burn", "complete_burn")
SEVERITY = {c: i for i, c in enumerate(CATEGORIES)}
M4_O2_RANGE = (0.20, 0.24)
M5_O2_RANGE = (0.19, 0.235)
P_ATM_RANGE = (0.9, 1.1)
DOMINANT = 0.9          # regime fraction needed to call a regime dominant
BAND_MIN_FRACTION = 0.05
SAFFIRE_FLOW = 20.0
LOW_FLOW_CM_S = 10.0
Z90 = 1.645

MATERIAL_ALIASES = {
    "silicone": "silicone",
    "sibal": "sibal", "cotton": "sibal", "cotton-fiberglass": "sibal", "cotton-fiberglass (sibal)": "sibal",
    "pmma": "pmma",
    "pmma_nomex": "pmma_nomex", "pmma & nomex": "pmma_nomex", "pmma+nomex": "pmma_nomex",
    "any": "any",
}
_SOURCE_MATERIAL = {"Silicone": "silicone", "Cotton-Fiberglass (SIBAL)": "sibal",
                    "PMMA": "pmma", "PMMA & Nomex": "pmma_nomex"}


# ----------------------------------------------------------------- tables
def _cat_from_fraction(f) -> str | None:
    if f is None or (isinstance(f, float) and math.isnan(f)):
        return None
    if f <= 1e-9:
        return "no_sustained_burn"
    if f >= 1 - 1e-9:
        return "complete_burn"
    return "partial_burn"


def _plurality(cats: list[str]) -> str:
    counts = {c: cats.count(c) for c in set(cats)}
    return max(counts, key=lambda c: (counts[c], SEVERITY[c]))


def _sha(*paths: Path) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


@functools.lru_cache(maxsize=1)
def _tests() -> pd.DataFrame:
    return pd.read_csv(TESTS_CSV, low_memory=False)


@functools.lru_cache(maxsize=1)
def m4_table() -> dict:
    sf = pd.read_csv(SAFFIRE_CSV)
    t = _tests()
    s2 = t[t["investigation_id"] == "PSI-99"].set_index("source_row")
    materials: dict[str, dict] = {}
    for _, r in sf.iterrows():
        key = _SOURCE_MATERIAL.get(str(r["material"]).strip())
        if key is None:
            raise ValueError(f"unmapped SAFFIRE-II material {r['material']!r}")
        tr = s2.loc[int(r["source_row"])] if int(r["source_row"]) in s2.index else None
        ug = tr["outcome"] if tr is not None and isinstance(tr["outcome"], str) else \
            _cat_from_fraction(r["ug_burned_fraction"])
        row = {
            "sample": str(r["sample"]),
            "record_id": tr["record_id"] if tr is not None else None,
            "thickness_mm": None if pd.isna(r["thickness_mm"]) else float(r["thickness_mm"]),
            "flow_cm_s": float(r["flow_speed_cm_s"]),
            "flow_direction": r["flow_direction"],
            "o2": float(r["o2_mole_fraction"]),
            "ug_burned_fraction": float(r["ug_burned_fraction"]),
            "1g_burned_fraction": float(r["1g_burned_fraction"]),
            "ug_outcome": ug,
            "1g_outcome": _cat_from_fraction(r["1g_burned_fraction"]),
            "needs_manual_review": bool(r["needs_manual_review"]),
            "ug_burn_length_raw": r["ug_burn_length_raw"],
        }
        materials.setdefault(key, {"label": str(r["material"]).strip(), "rows": []})["rows"].append(row)
    for m in materials.values():
        m["ug_outcome"] = _plurality([x["ug_outcome"] for x in m["rows"]])
        m["1g_outcome"] = _plurality([x["1g_outcome"] for x in m["rows"]])
        m["confidence"] = "low" if any(x["needs_manual_review"] for x in m["rows"]) else "medium"
        m["n"] = len(m["rows"])
    all_rows = [x for m in materials.values() for x in m["rows"]]
    materials["any"] = {
        "label": "any SAFFIRE-II material (most severe)",
        "rows": all_rows,
        "ug_outcome": max((m["ug_outcome"] for m in materials.values()), key=SEVERITY.get),
        "1g_outcome": max((m["1g_outcome"] for m in materials.values()), key=SEVERITY.get),
        "confidence": "low",
        "n": len(all_rows),
    }
    return {
        "source": "data/clean/psi_saffire_ug_vs_1g.csv (+ psi_tests.csv outcome), SAFFIRE-II PSI-99",
        "tested": {"o2": [min(x["o2"] for x in all_rows), max(x["o2"] for x in all_rows)],
                   "pressure_atm": "not in table; ~1 atm cabin assumed", "flow_cm_s": SAFFIRE_FLOW},
        "gate": {"o2": list(M4_O2_RANGE), "pressure_atm": list(P_ATM_RANGE)},
        "materials": materials,
    }


def _spice_rows() -> tuple[pd.DataFrame, dict]:
    t = _tests()
    s = t[t["investigation_id"] == "PSI-107"].copy()
    flags = s["quality_flags"].fillna("")
    flow = pd.to_numeric(s["flow_speed_cm_s"], errors="coerce")
    los = flags.str.contains("loss_of_signal")
    neg = flags.str.contains("negative_air_rate") | (flow <= 0)
    no_flame = s["ignited"].astype(str).str.lower() != "true"
    keep = ~los & ~neg & ~no_flame & flow.notna()
    excluded = {"loss_of_signal": int(los.sum()), "negative_or_zero_flow": int((neg & ~los).sum()),
                "no_flame_or_unknown": int((no_flame & ~los & ~neg).sum()),
                "flow_missing": int((flow.isna() & ~los & ~neg & ~no_flame).sum())}
    s = s[keep].assign(flow=flow[keep], fuel_key=s.loc[keep, "fuel"].str.strip().str.lower(),
                       nozzle=s.loc[keep, "size_mm"].astype(float).round(4))
    return s, excluded


@functools.lru_cache(maxsize=1)
def m5_table() -> dict:
    s, excluded = _spice_rows()
    windows = []
    for (fuel, noz), g in s.groupby(["fuel_key", "nozzle"]):
        windows.append({"fuel": fuel, "nozzle_mm": float(noz), "min_cm_s": float(g["flow"].min()),
                        "max_cm_s": float(g["flow"].max()), "n": int(len(g))})
    return {"source": "data/clean/psi_tests.csv, SPICE PSI-107, ignited rows",
            "atmosphere": "not in table (o2_and_pressure_not_in_table); ISS cabin air ~21% O2 / ~1 atm assumed",
            "gate": {"o2": list(M5_O2_RANGE), "pressure_atm": list(P_ATM_RANGE)},
            "excluded_rows": excluded, "n_rows": int(len(s)), "windows": windows}


@functools.lru_cache(maxsize=1)
def _psi62_hypothesis() -> str:
    try:
        return (json.loads(PSI62_JSON.read_text(encoding="utf-8")).get("hypothesis") or "").strip()
    except (OSError, ValueError):
        return ""


# ----------------------------------------------------------------- helpers
def _gate(o2: float, p_atm: float, o2_rng, what: str, tested: str) -> str | None:
    bad = []
    if not o2_rng[0] <= o2 <= o2_rng[1]:
        bad.append(f"O2 {o2 * 100:.1f}% outside {o2_rng[0] * 100:.0f}-{o2_rng[1] * 100:.1f}%")
    if not P_ATM_RANGE[0] <= p_atm <= P_ATM_RANGE[1]:
        bad.append(f"pressure {p_atm * PSIA_PER_ATM:.1f} psia ({p_atm:.2f} atm) outside "
                   f"{P_ATM_RANGE[0]}-{P_ATM_RANGE[1]} atm")
    if not bad:
        return None
    return (f"extrapolation, no evidence: {what} only tested {tested}; habitat "
            + "; ".join(bad) + ". No estimate is given outside the tested atmosphere.")


def _regime_category(regime: str, ug: str, g1: str):
    if regime == "forced":
        return ug
    if regime == "buoyant":
        return g1
    return ug if ug == g1 else "between"


def _param_grid(u_cm_s: float, L_mm: float) -> list[tuple[str, dict, dict]]:
    mid = {"C_b": 1.0, "k": sum(K_RANGE) / 2, "dT_over_T": sum(DT_OVER_T_RANGE) / 2}
    u_lo, u_hi = (0.5 * u_cm_s, 1.5 * u_cm_s) if u_cm_s > 0 else (0.0, 5.0)
    grid = [("C_b", {"C_b": C_B_RANGE[0]}, {"C_b": C_B_RANGE[1]}),
            ("k", {"k": K_RANGE[0]}, {"k": K_RANGE[1]}),
            ("dT_over_T", {"dT_over_T": DT_OVER_T_RANGE[0]}, {"dT_over_T": DT_OVER_T_RANGE[1]}),
            ("L_mm", {"L_mm": L_mm * L_FACTOR_RANGE[0]}, {"L_mm": L_mm * L_FACTOR_RANGE[1]}),
            ("u_cm_s", {"u_cm_s": u_lo}, {"u_cm_s": u_hi})]
    base = {**mid, "L_mm": L_mm, "u_cm_s": u_cm_s}
    return [(name, {**base, **lo}, {**base, **hi}) for name, lo, hi in grid]


def _det(g, p, o2, a: dict) -> dict:
    return evaluate(g, p, o2, a["u_cm_s"], a["L_mm"], dT_over_T=a["dT_over_T"], C_b=a["C_b"], k=a["k"])


def _rf(mc: dict) -> dict:
    return {k: round(float(v), 6) for k, v in mc["regime_fractions"].items()}


def _base(metric, label, unit, kind, mc, n_train, version) -> dict:
    return {"metric": metric, "label": label, "unit": unit, "kind": kind,
            "applicable": True, "reason": None, "estimate": None, "band90": None,
            "ref_0g": {"estimate": None, "band90": None}, "ref_1g": None,
            "regime_fractions": _rf(mc), "u_eff_summary": dict(mc["summary"]["u_eff"]),
            "nonmonotonic_flag": False, "nonmonotonic_note": None,
            "transfer": {"basis": "", "confidence": "low"},
            "evidence": [], "sensitivity": [], "n_train": int(n_train), "model_version": version}


# ----------------------------------------------------------------- M4
def resolve_material(material: str | None) -> str:
    if material is None:
        return "any"
    key = MATERIAL_ALIASES.get(str(material).strip().lower())
    if key is None:
        raise ValueError(f"unknown material {material!r}; choose from {sorted(set(MATERIAL_ALIASES.values()))}")
    return key


def predict_m4(g_m_s2, p_psia, o2, u_cm_s, L_mm, n=2000, seed=0, material=None) -> dict:
    table = m4_table()
    mkey = resolve_material(material)
    mat = table["materials"][mkey]
    ug, g1 = mat["ug_outcome"], mat["1g_outcome"]
    p_atm = p_psia / PSIA_PER_ATM
    mc = sample_physics(g_m_s2, p_psia, o2, u_cm_s, L_mm, n=n, seed=seed)
    out = _base("M4", "Solid material burn extent", "category", "category", mc, mat["n"],
                f"rules-m4-{RULES_VERSION}+{_sha(SAFFIRE_CSV)}")
    rf, ue = out["regime_fractions"], out["u_eff_summary"]

    out["evidence"] = sorted(
        ({"record_id": r["record_id"], "investigation_id": "PSI-99",
          "distance": round(atmosphere_distance(o2, p_atm, r["o2"], 1.0), 4)} for r in mat["rows"]),
        key=lambda e: (e["distance"], e["record_id"] or ""))[:20]

    p05 = ue["p05"]
    if p05 is not None and p05 < LOW_FLOW_CM_S:
        hyp = _psi62_hypothesis()
        out["nonmonotonic_flag"] = True
        out["nonmonotonic_note"] = (
            f"possible Goldilocks low-flow regime, may be more flammable than both references: u_eff "
            f"p05 = {p05:.1f} cm/s is below {LOW_FLOW_CM_S:g} cm/s, where flame spread over thin solids "
            f"is known to peak or quench (SAFFIRE tested only {SAFFIRE_FLOW:g} cm/s). PSI-62 hypothesis: "
            + (hyp if hyp else "not available"))

    reason = _gate(o2, p_atm, M4_O2_RANGE, "SAFFIRE-II",
                   "~22% O2 (21.5-22.1%) at ~1 atm cabin pressure and 20 cm/s flow")
    if reason:
        out.update(applicable=False, reason=reason)
        out["transfer"] = {"basis": "no transfer: habitat atmosphere outside the SAFFIRE-II test "
                                    "atmosphere (lunar/exploration 34% O2 / 8.2 psia is untested)",
                           "confidence": "low"}
        out["sensitivity"] = [{"param": nm, "low": None, "high": None} for nm, _, _ in _param_grid(u_cm_s, L_mm)]
        return out

    out["ref_0g"] = {"estimate": ug, "band90": [ug, ug]}
    out["ref_1g"] = {"estimate": g1, "band90": [g1, g1]}
    near = p05 is not None and ue["p95"] is not None and \
        SAFFIRE_FLOW / 2 <= p05 and ue["p95"] <= SAFFIRE_FLOW * 2
    win = f"{mat['label']}: microgravity {ug}, 1 g {g1} (n={mat['n']}, SAFFIRE-II at 20 cm/s)"
    if rf["forced"] >= DOMINANT:
        est = ug
        conf = "medium" if near else "low"
        basis = (f"forced-flow dominated ({rf['forced']:.0%}); microgravity outcome at u_eff "
                 f"{ue['p50']:.1f} cm/s" + ("" if near else
                 f", but u_eff is not within x2 of the tested {SAFFIRE_FLOW:g} cm/s"))
    elif rf["buoyant"] >= DOMINANT:
        est, conf = g1, "medium"
        basis = f"buoyancy dominated ({rf['buoyant']:.0%}); 1 g outcome applies"
    else:
        est = ug if ug == g1 else "between"
        conf = "low"
        basis = (f"mixed regime (forced {rf['forced']:.0%}, mixed {rf['mixed']:.0%}, buoyant "
                 f"{rf['buoyant']:.0%}); neither 0 g nor 1 g data alone applies"
                 + ("" if ug == g1 else f", outcome lies between {ug} and {g1}"))
    if mat["confidence"] == "low":
        conf = "low"
        basis += "; low-confidence material (footnoted / mixed-material samples or 'any' envelope)"
    covered = set()
    if rf["forced"] + rf["mixed"] >= BAND_MIN_FRACTION:
        covered.add(ug)
    if rf["buoyant"] + rf["mixed"] >= BAND_MIN_FRACTION:
        covered.add(g1)
    covered = sorted(covered or {est}, key=SEVERITY.get)
    out.update(estimate=est, band90=[covered[0], covered[-1]],
               transfer={"basis": f"{basis}. {win}", "confidence": conf})
    out["sensitivity"] = [
        {"param": nm,
         "low": _regime_category(_det(g_m_s2, p_psia, o2, lo)["regime"], ug, g1),
         "high": _regime_category(_det(g_m_s2, p_psia, o2, hi)["regime"], ug, g1)}
        for nm, lo, hi in _param_grid(u_cm_s, L_mm)]
    return out


# ----------------------------------------------------------------- M5
def _select_windows(fuel, nozzle_mm) -> tuple[list[dict], str]:
    ws = m5_table()["windows"]
    desc = []
    if fuel is not None:
        fk = str(fuel).strip().lower()
        ws = [w for w in ws if w["fuel"] == fk]
        if not ws:
            raise ValueError(f"unknown SPICE fuel {fuel!r}; choose from "
                             f"{sorted({w['fuel'] for w in m5_table()['windows']})}")
        desc.append(fk)
    else:
        desc.append("all fuels")
    if nozzle_mm is not None:
        sel = [w for w in ws if abs(w["nozzle_mm"] - float(nozzle_mm)) <= 0.05 * w["nozzle_mm"]]
        if not sel:
            raise ValueError(f"no SPICE nozzle near {nozzle_mm} mm; choose from "
                             f"{sorted({w['nozzle_mm'] for w in ws})}")
        ws = sel
        desc.append(f"{ws[0]['nozzle_mm']:g} mm nozzle")
    else:
        desc.append("all nozzles")
    return ws, ", ".join(desc)


def _inside(u, lo, hi) -> float:
    u = np.atleast_1d(np.asarray(u, dtype=float))
    return float(np.mean((u >= lo) & (u <= hi)))


def m5_window(fuel=None, nozzle_mm=None) -> dict:
    ws, desc = _select_windows(fuel, nozzle_mm)
    return {"selection": desc, "min_cm_s": min(w["min_cm_s"] for w in ws),
            "max_cm_s": max(w["max_cm_s"] for w in ws), "n": sum(w["n"] for w in ws), "windows": ws}


def predict_m5(g_m_s2, p_psia, o2, u_cm_s, L_mm, n=2000, seed=0, fuel=None, nozzle_mm=None) -> dict:
    win = m5_window(fuel, nozzle_mm)
    lo, hi = win["min_cm_s"], win["max_cm_s"]
    p_atm = p_psia / PSIA_PER_ATM
    mc = sample_physics(g_m_s2, p_psia, o2, u_cm_s, L_mm, n=n, seed=seed)
    out = _base("M5", "Supported coflow window", "fraction", "probability", mc, win["n"],
                f"rules-m5-{RULES_VERSION}+{_sha(TESTS_CSV)}")
    rf, ue = out["regime_fractions"], out["u_eff_summary"]
    u_eff = mc["u_eff"]

    # evidence: SPICE rows in the selected windows nearest the median u_eff (flow-only distance)
    s, _ = _spice_rows()
    keys = {(w["fuel"], w["nozzle_mm"]) for w in win["windows"]}
    s = s[[(f, z) in keys for f, z in zip(s["fuel_key"], s["nozzle"])]]
    ref_u = max(float(ue["p50"] or 0.0), 0.1)
    d = (np.log(np.maximum(s["flow"].to_numpy(), 0.1)) - math.log(ref_u)) / 0.3
    s = s.assign(dist=np.abs(d)).sort_values(["dist", "record_id"]).head(20)
    out["evidence"] = [{"record_id": r.record_id, "investigation_id": "PSI-107", "distance": round(float(r.dist), 4)}
                       for r in s.itertuples()]

    basis_win = (f"SPICE flames observed at coflow {lo:g}-{hi:g} cm/s for {win['selection']} "
                 f"(n={win['n']} ignited rows; LOS / negative-flow rows excluded); SPICE has no O2 or "
                 f"pressure in its table, so the atmosphere is unknown (ISS cabin air assumed)")
    reason = _gate(o2, p_atm, M5_O2_RANGE, "SPICE",
                   "in ISS cabin air (assumed ~21% O2 / ~1 atm; the table records no atmosphere)")
    frac = _inside(u_eff, lo, hi)
    f0 = _inside(u_cm_s, lo, hi)
    mc1 = sample_physics(9.81, p_psia, o2, u_cm_s, L_mm, n=n, seed=seed)
    f1 = _inside(mc1["u_eff"], lo, hi)
    if min(f0, f1) - 0.05 > frac or frac > max(f0, f1) + 0.05:
        out["nonmonotonic_flag"] = True
        out["nonmonotonic_note"] = (f"partial-g fraction inside the window ({frac:.2f}) is outside the 0 g "
                                    f"({f0:.2f}) to 1 g ({f1:.2f}) references: u_eff lands "
                                    + ("inside" if frac > max(f0, f1) else "outside")
                                    + " the observed flame window only at this gravity")
    if reason:
        out.update(applicable=False, reason=reason)
        out["transfer"] = {"basis": "no transfer: " + basis_win, "confidence": "low"}
        out["sensitivity"] = [{"param": nm, "low": None, "high": None} for nm, _, _ in _param_grid(u_cm_s, L_mm)]
        return out

    se = math.sqrt(max(frac * (1 - frac), 0.25 / len(u_eff)) / len(u_eff))
    subs = [_inside(u_eff, w["min_cm_s"], w["max_cm_s"]) for w in win["windows"]] + [frac]
    band = [round(max(0.0, min(subs) - Z90 * se), 6), round(min(1.0, max(subs) + Z90 * se), 6)]
    conf = "medium" if rf["forced"] >= DOMINANT else "low"
    regime_txt = (f"forced-flow dominated ({rf['forced']:.0%}): coflow evidence transfers"
                  if conf == "medium" else
                  f"not forced dominated (forced {rf['forced']:.0%}, mixed {rf['mixed']:.0%}, buoyant "
                  f"{rf['buoyant']:.0%}): buoyant flow mapped through u_eff, larger uncertainty")
    out.update(estimate=round(frac, 6), band90=band,
               ref_0g={"estimate": f0, "band90": [f0, f0]},
               ref_1g={"estimate": round(f1, 6), "band90": [round(f1, 6), round(f1, 6)]},
               transfer={"basis": f"{regime_txt}. {basis_win}. ref_1g is the bridge model at g = 9.81 "
                                  f"(no 1 g SPICE data)", "confidence": conf})
    out["sensitivity"] = [
        {"param": nm,
         "low": _inside(_det(g_m_s2, p_psia, o2, a_lo)["u_eff_cm_s"], lo, hi),
         "high": _inside(_det(g_m_s2, p_psia, o2, a_hi)["u_eff_cm_s"], lo, hi)}
        for nm, a_lo, a_hi in _param_grid(u_cm_s, L_mm)]
    return out


# ----------------------------------------------------------------- artifact
def build_rules() -> dict:
    m4 = m4_table()
    return {
        "version": f"{RULES_VERSION}+{_sha(SAFFIRE_CSV, TESTS_CSV)}",
        "generated_by": "engine/rules.py",
        "categories": list(CATEGORIES) + ["between"],
        "m4": m4,
        "m5": m5_table(),
        "psi62_hypothesis": _psi62_hypothesis(),
    }


def main() -> int:
    from engine.presets import PRESETS

    rules = build_rules()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rules, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rules['m4']['materials']) - 1} M4 materials, "
          f"{len(rules['m5']['windows'])} M5 windows, version {rules['version']}")
    for p in PRESETS:
        h = (p["g_m_s2"], p["p_psia"], p["o2"], p["u_cm_s"], p["L_mm"])
        m4, m4s, m5 = predict_m4(*h), predict_m4(*h, material="silicone"), predict_m5(*h)
        print(f"  {p['id']:<12} M4(any)={m4['estimate']!s:<18} M4(silicone)={m4s['estimate']!s:<18} "
              f"M5={m5['estimate']!s:<9} band={m5['band90']} applicable={m4['applicable']}/{m5['applicable']} "
              f"nonmono={m4['nonmonotonic_flag']}/{m5['nonmonotonic_flag']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
