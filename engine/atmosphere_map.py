"""S5 atmosphere evidence map: what the evidence says across cabin atmospheres (ADR-0011).

Contract: plan/contracts.md "Round 3 · S5 Atmosphere map addendum". Plan: plan/15-round-3-features.md §S5.

The map never ranks atmospheres; it shows evidence. For M1-M3 it evaluates the fitted model on an
O2 x pressure grid (O2 0.15-0.40 linear, 26 values; pressure 4-16 psia log spaced, 20 values) with the same honesty
gate as ``engine.bounds.predict`` (``bounds._distances``, distance <= 2). A cell outside the gate gets
``estimate: null`` and ``band90: null``: no colour, no guess.

What depends on what (ADR-0005, checked in engine.bounds / engine.montecarlo): the M1-M3 estimate and the unwidened
model band depend only on the atmosphere and the fuel options, never on gravity or vent speed. Gravity reaches only
the band, through the Monte Carlo regime fractions, and those depend on gravity, vent speed and flame size, not on
O2 or pressure. So the estimates are computed once per metric, and each gravity preset needs one widening factor
for the whole grid. Every covered cell equals ``bounds.predict`` at that atmosphere (default fuel and options; vent
10 cm/s, flame size 10 mm).

Overlays: the six habitat presets, the R1 incident atmospheres, the tested atmospheres (engine.coverage) and crew
limits from data/crew_limits.json, drawn by each entry's ``map_rule`` and carrying its source.

Run ``python -m engine.atmosphere_map`` to write artifacts/atmosphere_map/{metric}_{gravity}.json.
"""

from __future__ import annotations

import json
import math
import time
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

import numpy as np

from engine import bounds, coverage
from engine.bounds import (
    FITTED,
    GATE_DISTANCE,
    METRICS,
    json_safe,
    widen_band,
    widen_factor,
)
from engine.models import get_model, query_row
from engine.montecarlo import sample_physics
from engine.physics import PSIA_PER_ATM
from engine.presets import PRESETS

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "artifacts" / "atmosphere_map"
CREW_LIMITS_PATH = ROOT / "data" / "crew_limits.json"
INCIDENTS_PATH = ROOT / "artifacts" / "incidents.json"

O2_RANGE = (0.15, 0.40)
P_RANGE_PSIA = (4.0, 16.0)
N_O2 = 26
N_P = 20
U_CM_S = 10.0
L_MM = 10.0
N_MC = 2000
SEED = 0
SIG = 4
MMHG_PER_PSIA = 51.715
WATER_VAPOUR_MMHG = 47.0
GRAVITIES = {
    "orbit": {"g_m_s2": 0.0, "label": "Orbit (0 g)"},
    "lunar": {"g_m_s2": 1.62, "label": "Moon (1.62 m/s²)"},
    "mars": {"g_m_s2": 3.71, "label": "Mars (3.71 m/s²)"},
    "earth": {"g_m_s2": 9.81, "label": "Earth (9.81 m/s²)"},
}
INVESTIGATION = {"M1": "PSI-69", "M2": "PSI-69", "M3": "PSI-159"}
RULE = "The map never ranks atmospheres; it shows evidence (ADR-0011)."
WHAT_VARIES = ("The estimate depends only on O₂ and pressure (and the default fuel options), not on gravity: the "
               "tests flew in microgravity with no imposed flow (ADR-0005). Gravity only widens the band, by one "
               "factor for the whole map, so the covered cells and the estimates are the same in every gravity "
               "file; only band90 changes.")
NOT_DRAWN_OUTSIDE_MAP = "outside the map's O₂ range (0.15-0.40); not drawn"


# ------------------------------------------------------------------ helpers
def sig(x, digits: int = SIG):
    """Round to `digits` significant figures (None stays None)."""
    if x is None:
        return None
    x = float(x)
    if x == 0 or not math.isfinite(x):
        return 0.0 if x == 0 else None
    return round(x, digits - 1 - math.floor(math.log10(abs(x)))) + 0.0


def grid_axes() -> tuple[list[float], list[float]]:
    o2 = np.linspace(O2_RANGE[0], O2_RANGE[1], N_O2)
    p = np.geomspace(P_RANGE_PSIA[0], P_RANGE_PSIA[1], N_P)
    return [sig(v) for v in o2], [sig(v) for v in p]


def _on_map(o2: float, p_psia: float) -> bool:
    return O2_RANGE[0] <= o2 <= O2_RANGE[1] and P_RANGE_PSIA[0] <= p_psia <= P_RANGE_PSIA[1]


@cache
def _estimates(metric: str) -> tuple:
    """(covered, estimate, lo, hi, nearest) arrays of shape (N_P, N_O2), computed once (no gravity dependence)."""
    model = get_model(metric)
    o2s, ps = grid_axes()
    opts = {"L_mm": L_MM}
    rows, near = [], []
    for p in ps:
        p_atm = p / PSIA_PER_ATM
        for o2 in o2s:
            rows.append(query_row(metric, o2, p_atm, opts, model)[0])
            near.append(float(bounds._distances(model, o2, p_atm).min()))
    out = model.predict(np.vstack(rows))
    shape = (len(ps), len(o2s))
    near = np.array(near).reshape(shape)
    return (near <= GATE_DISTANCE, out["estimate"].reshape(shape), out["lo"].reshape(shape),
            out["hi"].reshape(shape), near, model.model_version)


def gravity_factor(g_m_s2: float) -> tuple[float, dict]:
    """ADR-0005 widening factor at this gravity (vent 10 cm/s, L 10 mm); independent of O2 and pressure."""
    fr = sample_physics(g_m_s2, 10.2, 0.21, U_CM_S, L_MM, n=N_MC, seed=SEED)["regime_fractions"]
    return widen_factor(fr), fr


def grid(metric: str, g_m_s2: float) -> dict:
    """Cells for one metric and gravity (JSON-safe, rounded to 4 significant figures)."""
    metric = metric.upper()
    if metric not in FITTED:
        raise KeyError(f"map metrics are {list(FITTED)}; {metric!r} is a rule table or unknown")
    covered, est, lo, hi, near, version = _estimates(metric)
    kind = METRICS[metric]["kind"]
    factor, fr = gravity_factor(g_m_s2)
    o2s, ps = grid_axes()
    cells = []
    for j, p in enumerate(ps):
        for i, o2 in enumerate(o2s):
            c = bool(covered[j, i])
            band = widen_band(kind, float(est[j, i]), float(lo[j, i]), float(hi[j, i]), factor) if c else None
            cells.append({"i": i, "j": j, "o2": o2, "p_psia": p, "covered": c,
                          "estimate": sig(est[j, i]) if c else None,
                          "band90": [sig(band[0]), sig(band[1])] if c else None,
                          "nearest_distance": sig(near[j, i])})
    n_cov = int(covered.sum())
    return {"cells": cells, "n_cells": len(cells), "n_covered": n_cov,
            "evidence_share": sig(n_cov / len(cells)), "widen_factor": sig(factor),
            "regime_fractions": {k: sig(v) for k, v in fr.items()}, "model_version": version}


# ------------------------------------------------------------------ overlays
def _covered_at(metric: str, o2: float, p_psia: float) -> tuple[bool, float]:
    d = float(bounds._distances(get_model(metric), o2, p_psia / PSIA_PER_ATM).min())
    return d <= GATE_DISTANCE, sig(d)


def preset_markers(metric: str) -> list[dict]:
    out = []
    for p in PRESETS:
        cov, d = _covered_at(metric, p["o2"], p["p_psia"])
        out.append({"id": p["id"], "label": p["label"], "o2": p["o2"], "p_psia": p["p_psia"], "g_m_s2": p["g_m_s2"],
                    "on_map": _on_map(p["o2"], p["p_psia"]), "covered": cov, "nearest_distance": d,
                    "citation": f"eng:{metric}"})
    return out


def incident_markers(metric: str) -> list[dict]:
    try:
        doc = json.loads(INCIDENTS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for inc in doc.get("incidents") or []:
        if not inc.get("in_scope") or not all(isinstance(inc.get(k), (int, float)) for k in ("o2", "p_psia")):
            continue
        cov, d = _covered_at(metric, inc["o2"], inc["p_psia"])
        out.append({"id": inc["id"], "label": inc["name"], "date": inc.get("date"), "o2": inc["o2"],
                    "p_psia": inc["p_psia"], "g_m_s2": inc.get("g_m_s2"),
                    "atmosphere_assumed": any(k in (inc.get("assumed") or []) for k in ("o2", "p_psia")),
                    "on_map": _on_map(inc["o2"], inc["p_psia"]), "covered": cov, "nearest_distance": d,
                    "citation": f"eng:incident:{inc['id']}"})
    return out


def tested_points(metric: str) -> list[dict]:
    out = []
    for pt in coverage.coverage(metric)["points"]:
        p_psia = pt["p_atm"] * PSIA_PER_ATM
        row = {"o2": pt["o2"], "p_psia": sig(p_psia), "n": pt["n"], "investigation_id": pt["investigation_id"],
               "on_map": _on_map(pt["o2"], p_psia)}
        if "co2" in pt:
            row.update(co2=pt["co2"], he=pt["he"], undiluted=pt["co2"] == 0 and pt["he"] == 0)
        out.append(row)
    return out


def _pio2_curve(pio2_mmhg: float, n: int = 61) -> list[list[float]]:
    """x = PIO2 / (p_psia * 51.715 - 47) for p in the map range, clipped to the O2 range (with exact end points)."""
    def x_at(p):
        return pio2_mmhg / (p * MMHG_PER_PSIA - WATER_VAPOUR_MMHG)

    def p_at(x):
        return (pio2_mmhg / x + WATER_VAPOUR_MMHG) / MMHG_PER_PSIA

    ps = list(np.geomspace(P_RANGE_PSIA[0], P_RANGE_PSIA[1], n))
    for x_edge in O2_RANGE:
        pe = p_at(x_edge)
        if P_RANGE_PSIA[0] < pe < P_RANGE_PSIA[1]:
            ps.append(pe)
    pts = sorted((float(x_at(p)), float(p)) for p in ps)
    return [[sig(x), sig(p)] for x, p in pts if O2_RANGE[0] - 1e-9 <= x <= O2_RANGE[1] + 1e-9]


def crew_limit_overlays(path: Path = CREW_LIMITS_PATH) -> dict:
    """Crew-limit geometry in map coordinates (x = O2 fraction, y = total pressure psia), one entry per limit."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    drawn, not_drawn = [], []
    x0, x1 = O2_RANGE
    p0, p1 = P_RANGE_PSIA
    for e in doc["limits"]:
        lid = e["id"]
        base = {"id": lid, "label": e["label"], "quantity": e["quantity"], "map_rule": e.get("map_rule"),
                "citation": f"eng:crew_limit:{lid}", "caveat": e.get("caveat"), "confidence": e.get("confidence"),
                "quote": e.get("quote"),
                "source": {k: e["source"].get(k) for k in ("title", "org", "id_or_number", "url", "page_or_section")}}
        if lid.startswith("pio2_") and e["quantity"] == "o2_partial_pressure_min":
            if e.get("value_high") is not None:
                geo = {"shape": "band", "style": "shaded", "role": "target, not a limit",
                       "polylines": [_pio2_curve(e["value"]), _pio2_curve(e["value_high"])]}
            else:
                geo = {"shape": "curve", "style": "dashed" if "floor" in lid else "solid", "role": "limit",
                       "polyline": _pio2_curve(e["value"])}
            geo["formula"] = "x = PIO2_mmHg / (p_psia * 51.715 - 47)"
        elif e["quantity"] == "total_pressure_min":
            geo = {"shape": "hline", "style": "solid", "role": "limit", "p_psia": e["value"],
                   "exclusive": bool(e.get("exclusive")), "polyline": [[x0, e["value"]], [x1, e["value"]]]}
        elif e["quantity"] == "o2_fraction_max":
            x = e["converted"]["value"]
            if not x0 <= x <= x1:
                not_drawn.append({**base, "reason": NOT_DRAWN_OUTSIDE_MAP})
                continue
            if "POINT" in (e.get("map_rule") or ""):
                geo = {"shape": "point", "role": "illustration", "point": [x, 14.7]}
            elif "segment" in (e.get("map_rule") or ""):
                geo = {"shape": "tick", "role": "context", "polyline": [[x, 13.0], [x, p1]],
                       "note": "ISS context only"}
            else:
                geo = {"shape": "vline", "style": "solid", "role": "program baseline", "polyline": [[x, p0], [x, p1]]}
                if e.get("caveat"):
                    geo["note"] = "program baseline (2007), not an agency standard"
        elif e["quantity"] == "reference_atmosphere":
            x = e["o2_percent"] / 100.0
            geo = {"shape": "marker", "role": "reference atmosphere", "point": [x, e["value"]],
                   "hollow": "superseded" in e["label"]}
        else:
            not_drawn.append({**base, "reason": f"no map rule for quantity {e['quantity']!r}"})
            continue
        drawn.append({**base, **geo})
    return {"source_file": "data/crew_limits.json", "retrieved": doc.get("retrieved"), "drawn": drawn,
            "not_drawn": not_drawn,
            "note": ("Crew and materials limits from cited NASA documents, drawn by each entry's map_rule. They "
                     "say nothing about how a fire would behave and are not a ranking of atmospheres.")}


# ------------------------------------------------------------------ main entry
def atmosphere_map(metric: str, gravity: str = "lunar") -> dict:
    """Full map document for one metric (M1-M3) and gravity preset id (contract shape, JSON-safe)."""
    if gravity not in GRAVITIES:
        raise KeyError(f"gravity must be one of {list(GRAVITIES)}, got {gravity!r}")
    metric = metric.upper()
    g = GRAVITIES[gravity]["g_m_s2"]
    gr = grid(metric, g)
    o2s, ps = grid_axes()
    pct = f"{100 * gr['evidence_share']:.0f}%"
    reading = (f"{metric} has evidence in {gr['n_covered']} of {gr['n_cells']} cells ({pct} of this map); the "
               f"rest is no evidence. ")
    lb = next(m for m in preset_markers(metric) if m["id"] == "lunar_base")
    reading += ("The lunar base atmosphere (34% O₂, 8.2 psia) is inside the evidence."
                if lb["covered"] else
                f"The lunar base atmosphere (34% O₂, 8.2 psia) is outside the evidence (distance "
                f"{lb['nearest_distance']} to the nearest test, the gate is 2).")
    return json_safe({
        "artifact": "atmosphere_map",
        "adr": "ADR-0011",
        "citation": f"eng:atmosphere_map:{metric}",
        "rule": RULE,
        "metric": metric,
        "label": METRICS[metric]["label"],
        "unit": METRICS[metric]["unit"],
        "kind": METRICS[metric]["kind"],
        "investigation_id": INVESTIGATION[metric],
        "gravity": {"id": gravity, **GRAVITIES[gravity], "u_cm_s": U_CM_S, "L_mm": L_MM,
                    "widen_factor": gr["widen_factor"], "regime_fractions": gr["regime_fractions"]},
        "defaults": {"u_cm_s": U_CM_S, "L_mm": L_MM,
                     "options": "M1/M2: Heptane, droplet size = L_mm clipped to the tested range, no CO₂/He; "
                                "M3: propane, fuel fraction 0.3",
                     "why": "Preset vent speed and flame size. They only matter through the widening factor."},
        "what_varies": WHAT_VARIES,
        "axes": {"x": {"name": "o2", "label": "O₂ mole fraction", "scale": "linear", "values": o2s},
                 "y": {"name": "p_psia", "label": "Total pressure (psia)", "scale": "log", "values": ps}},
        "gate": {"max_distance": GATE_DISTANCE,
                 "text": coverage.coverage(metric)["rule"]["text"]},
        "cells": gr["cells"],
        "summary": {"n_cells": gr["n_cells"], "n_covered": gr["n_covered"], "evidence_share": gr["evidence_share"],
                    "no_evidence_share": sig(1 - gr["n_covered"] / gr["n_cells"]),
                    "same_for_every_gravity": True},
        "reading": reading,
        "overlays": {"presets": preset_markers(metric), "incidents": incident_markers(metric),
                     "tested": tested_points(metric), "crew_limits": crew_limit_overlays()},
        "rounding": f"{SIG} significant figures",
        "model_version": gr["model_version"],
    })


def build_artifacts(out_dir: Path = OUT_DIR) -> list[tuple[Path, float]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    written = []
    for metric in FITTED:
        for gid in GRAVITIES:
            t0 = time.perf_counter()
            doc = {**atmosphere_map(metric, gid), "generated_at": stamp}
            path = out_dir / f"{metric}_{gid}.json"
            path.write_text(json.dumps(doc, separators=(",", ":"), allow_nan=False, ensure_ascii=False),
                            encoding="utf-8")
            written.append((path, time.perf_counter() - t0))
    return written


def main() -> None:
    t0 = time.perf_counter()
    for m in FITTED:
        get_model(m)
    t_fit = time.perf_counter() - t0
    t1 = time.perf_counter()
    written = build_artifacts()
    print(f"wrote {len(written)} files to {OUT_DIR} (model fits {t_fit:.1f} s, maps {time.perf_counter() - t1:.2f} s)")
    for path, dt in written:
        d = json.loads(path.read_text(encoding="utf-8"))
        s = d["summary"]
        print(f"  {path.name}: {s['n_covered']}/{s['n_cells']} cells with evidence ({s['evidence_share']}); "
              f"widen x{d['gravity']['widen_factor']}; {path.stat().st_size // 1024} KB; {dt:.2f} s")


if __name__ == "__main__":
    main()
