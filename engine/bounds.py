"""E2 bounds models: metric predictions with 90% bands and an honesty gate (C5-C11).

Contract: plan/contracts.md "Phase 2 addendum", engine/bounds.py.
Decisions: ADR-0004 (metric definitions and exclusions), ADR-0005 (gravity
honesty rule) in plan/decisions.md.

M1-M3 are fitted here (engine.models) on microgravity droplet (FLEX) and
spherical-burner (CFI-G) data. Those tests have NO flow variable, so gravity
never changes the M1-M3 estimate: the estimate is the microgravity-matched
model output at the query's O2 and pressure. Partial gravity only widens the
band (by the Monte Carlo regime fractions) and lowers transfer.confidence.
M4/M5 are flow dependent and are owned by DE (engine.rules); they are
dispatched lazily.

Run ``python -m engine.bounds`` to write artifacts/bounds/{preset}_{metric}.json.
"""

from __future__ import annotations

import importlib
import json
import math
from pathlib import Path

import numpy as np

from engine.models import get_model, query_row
from engine.montecarlo import (
    C_B_RANGE,
    DT_OVER_T_RANGE,
    K_RANGE,
    L_FACTOR_RANGE,
    sample_physics,
)
from engine.physics import PSIA_PER_ATM, RI_BUOYANT_MIN, RI_FORCED_MAX, atmosphere_distance
from engine.presets import PRESETS

ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "bounds"
GATE_DISTANCE = 2.0
N_EVIDENCE = 20
N_BOOT_DEFAULT = 500
MIXED_WIDEN = 0.5
BUOYANT_WIDEN = 1.0
O2_STEP = 0.03
P_FACTOR = 0.2
_EPS = 1e-6

METRICS: dict[str, dict] = {
    "M1": {
        "label": "P(droplet flame self-extinguishes before burnout)",
        "unit": "probability",
        "kind": "probability",
        "data": "FLEX (PSI-69) droplet tests: extinction vs completion (disruption excluded)",
        "flow_dependent": False,
    },
    "M2": {
        "label": "Extinction diameter",
        "unit": "mm",
        "kind": "quantity",
        "data": "FLEX (PSI-69) droplet tests that ended in extinction with a recorded extinction diameter",
        "flow_dependent": False,
    },
    "M3": {
        "label": "P(gas flame self-extinguishes vs flow-terminated)",
        "unit": "probability",
        "kind": "probability",
        "data": "ACME CFI-G (PSI-159) normal spherical-burner flames (ambient O2)",
        "flow_dependent": False,
    },
    "M4": {
        "label": "Solid-material burn extent: microgravity vs 1 g",
        "unit": "category",
        "kind": "category",
        "data": "SAFFIRE-II (PSI-99) microgravity vs 1 g pairs + SAFFIRE-I/III, BASS-II context (rule table, engine.rules)",
        "flow_dependent": True,
    },
    "M5": {
        "label": "Flame existence vs coflow speed",
        "unit": "category",
        "kind": "category",
        "data": "SPICE (PSI-107) coflow flow windows per fuel and nozzle (rule table, engine.rules)",
        "flow_dependent": True,
    },
}
FITTED = ("M1", "M2", "M3")
RULE_METRICS = {"M4": "predict_m4", "M5": "predict_m5"}


# ------------------------------------------------------------------- helpers
def json_safe(obj):
    """Recursively convert numpy types; NaN/inf -> None (ADR-0003)."""
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [json_safe(v) for v in obj.tolist()]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return f if math.isfinite(f) else None
    return obj


def _logit(p):
    p = np.clip(p, _EPS, 1 - _EPS)
    return np.log(p / (1 - p))


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def widen_factor(fractions: dict) -> float:
    """ADR-0005: 1 + 0.5*mixed + 1.0*buoyant (1 when fully forced)."""
    return 1.0 + MIXED_WIDEN * fractions["mixed"] + BUOYANT_WIDEN * fractions["buoyant"]


def widen_band(kind: str, est: float, lo: float, hi: float, factor: float) -> list[float]:
    """Widen [lo, hi] around est: logit space for probabilities, proportional for quantities."""
    if factor == 1.0:
        return [float(lo), float(hi)]
    if kind == "probability":
        le, ll, lh = _logit(est), _logit(lo), _logit(hi)
        nlo = float(_sigmoid(le - factor * (le - ll)))
        nhi = float(_sigmoid(le + factor * (lh - le)))
        return [min(max(nlo, 0.0), est), max(min(nhi, 1.0), est)]
    return [max(0.0, est - factor * (est - lo)), est + factor * (hi - est)]


def transfer_confidence(fractions: dict) -> str:
    if fractions["forced"] >= 0.8:
        return "high"
    if fractions["forced"] + fractions["mixed"] >= 0.8:
        return "medium"
    return "low"


def _transfer_basis(g_m_s2: float, fr: dict, conf: str, factor: float) -> str:
    pct = {k: round(100 * v) for k, v in fr.items()}
    src = ("droplet and spherical-burner tests were run in microgravity with no imposed flow, "
           "so gravity does not change the estimate")
    if g_m_s2 == 0:
        return (f"Orbit (0 g): no buoyancy, so the microgravity tests match this case directly. "
                f"The {src.split(',')[0]}; the band is the model band, not widened.")
    return (f"At {g_m_s2:g} m/s^2 the Monte Carlo puts the flame {pct['forced']}% forced-flow, "
            f"{pct['mixed']}% mixed and {pct['buoyant']}% buoyancy-dominated. The {src}; "
            f"the 90% band is widened x{factor:.2f} to cover buoyancy the tests did not have "
            f"(transfer confidence {conf}). No 1 g reference: these investigations have no "
            f"normal-gravity counterpart in the PSI data.")


def _regime_fractions_from_ri(ri: np.ndarray) -> dict:
    forced = float(np.mean(ri < RI_FORCED_MAX))
    buoyant = float(np.mean(ri > RI_BUOYANT_MIN))
    return {"forced": forced, "mixed": 1.0 - forced - buoyant, "buoyant": buoyant}


def _fractions_with_fixed(mc: dict, u_cm_s: float, L_mm: float, param: str, value: float) -> dict:
    """Regime fractions with one MC coefficient pinned to `value` (others sampled)."""
    s = mc["samples"]
    u_b = mc["u_b"].copy()
    if param == "C_b":
        u_b = u_b * (value / s["C_b"])
    elif param == "dT_over_T":
        u_b = u_b * np.sqrt(value / s["dT_over_T"])
    elif param == "L_factor":
        u_b = u_b * np.sqrt(value * L_mm / s["L_mm"])
    # k enters u_eff only, not Ri: regime fractions are unchanged for M1-M3.
    if u_cm_s == 0:
        ri = np.where(u_b > 0, np.inf, 0.0)
    else:
        ri = (u_b * u_b) / (u_cm_s * u_cm_s)
    return _regime_fractions_from_ri(ri)


# ------------------------------------------------------------------- predict
def _not_applicable_base(metric: str) -> dict:
    meta = METRICS[metric]
    return {"metric": metric, "label": meta["label"], "unit": meta["unit"], "kind": meta["kind"]}


def _predict_rules(metric: str, g_m_s2, p_psia, o2, u_cm_s, L_mm, n, seed) -> dict:
    try:
        rules = importlib.import_module("engine.rules")
    except ImportError as exc:  # DE is writing engine/rules.py
        raise NotImplementedError(
            f"{metric} is provided by engine.rules ({RULE_METRICS[metric]}), which is not available yet"
        ) from exc
    fn = getattr(rules, RULE_METRICS[metric], None)
    if fn is None:
        raise NotImplementedError(f"engine.rules has no {RULE_METRICS[metric]}() yet")
    return fn(g_m_s2=g_m_s2, p_psia=p_psia, o2=o2, u_cm_s=u_cm_s, L_mm=L_mm, n=n, seed=seed)


def _model_eval(model, metric, o2, p_atm, options):
    row, inputs = query_row(metric, o2, p_atm, options, model)
    out = model.predict(row[None, :])
    return float(out["estimate"][0]), float(out["lo"][0]), float(out["hi"][0]), inputs


def _distances(model, o2, p_atm) -> np.ndarray:
    ts = model.train
    dx = (o2 - ts.o2) / 0.05
    dp = (math.log(p_atm) - np.log(ts.p_atm)) / 0.3
    return np.sqrt(dx * dx + dp * dp)


def predict(
    metric: str,
    g_m_s2: float,
    p_psia: float,
    o2: float,
    u_cm_s: float,
    L_mm: float,
    n: int = 2000,
    seed: int = 0,
    **options,
) -> dict:
    """Predict one metric for a habitat state (contract shape, JSON-safe).

    Options (M1-M3 only; ignored for M4/M5):
        fuel: M1/M2 "Heptane" (default) | "Methanol"; M3 "propane" (default) | "ethane" | "butane".
        droplet_mm: M1/M2 initial droplet diameter; default L_mm, clipped to the training range.
        he, co2: M1/M2 diluent mole fractions (default 0: habitat air uses N2).
        fuel_fraction: M3 fuel mole fraction in the burner stream (default 0.3, the most tested).
        n_boot: bootstrap refits for M1/M3 (default 500); boot_seed (default 0).
    """
    if metric not in METRICS:
        raise KeyError(f"unknown metric {metric!r}; known: {sorted(METRICS)}")
    if metric in RULE_METRICS:
        return json_safe(_predict_rules(metric, g_m_s2, p_psia, o2, u_cm_s, L_mm, n, seed))
    if p_psia <= 0:
        raise ValueError("p_psia must be > 0")
    if not 0 <= o2 <= 1:
        raise ValueError("o2 must be a mole fraction in [0, 1]")

    meta = METRICS[metric]
    model = get_model(metric, n_boot=int(options.pop("n_boot", N_BOOT_DEFAULT)),
                      seed=int(options.pop("boot_seed", 0)))
    p_atm = p_psia / PSIA_PER_ATM
    options = {**options, "L_mm": L_mm}

    mc = sample_physics(g_m_s2, p_psia, o2, u_cm_s, L_mm, n=n, seed=seed)
    fr = mc["regime_fractions"]

    d = _distances(model, o2, p_atm)
    order = np.argsort(d, kind="stable")
    ts = model.train
    evidence = [
        {"record_id": ts.record_id[i], "investigation_id": ts.investigation_id[i], "distance": float(d[i])}
        for i in order[:N_EVIDENCE]
    ]
    nearest = order[0]
    applicable = bool(d[nearest] <= GATE_DISTANCE)

    out = {
        **_not_applicable_base(metric),
        "applicable": applicable,
        "reason": None,
        "estimate": None,
        "band90": None,
        "ref_0g": None,
        "ref_1g": None,
        "regime_fractions": fr,
        "u_eff_summary": mc["summary"]["u_eff"],
        "nonmonotonic_flag": False,
        "nonmonotonic_note": None,
        "transfer": None,
        "evidence": evidence,
        "sensitivity": [],
        "n_train": int(len(ts.y)),
        "model_version": model.model_version,
    }
    near_txt = (f"nearest tested condition is {ts.investigation_id[nearest]} {ts.record_id[nearest]} "
                f"at O2 {ts.o2[nearest]:.3f}, {ts.p_atm[nearest]:.2f} atm "
                f"(atmosphere distance {d[nearest]:.2f})")
    if not applicable:
        out["reason"] = (f"Extrapolation: no evidence. The query (O2 {o2:.3f}, {p_atm:.2f} atm) is more than "
                         f"{GATE_DISTANCE:g} atmosphere-distance units from every {metric} training test; "
                         f"the {near_txt}.")
        out["transfer"] = {"basis": "No estimate: outside the tested atmosphere range.", "confidence": "low"}
        return json_safe(out)

    est, lo, hi, inputs = _model_eval(model, metric, o2, p_atm, options)
    factor = widen_factor(fr)
    band = widen_band(meta["kind"], est, lo, hi, factor)
    conf = transfer_confidence(fr)
    out.update(
        estimate=est,
        band90=band,
        ref_0g={"estimate": est, "band90": [lo, hi]},
        ref_1g=None,
        transfer={"basis": _transfer_basis(g_m_s2, fr, conf, factor), "confidence": conf},
        inputs={**inputs, "p_atm": p_atm, "widen_factor": factor, "nearest": near_txt},
    )

    # C11 sensitivity (tornado). Atmosphere params move the estimate; physics
    # params move only the band (gravity honesty rule).
    sens = []
    for param, (qlo, qhi) in (
        ("o2", (max(o2 - O2_STEP, 0.0), min(o2 + O2_STEP, 1.0))),
        ("pressure", (p_atm * (1 - P_FACTOR), p_atm * (1 + P_FACTOR))),
    ):
        vals = []
        for qv in (qlo, qhi):
            o2q, pq = (qv, p_atm) if param == "o2" else (o2, qv)
            gated = _distances(model, o2q, pq).min() > GATE_DISTANCE
            vals.append(None if gated else _model_eval(model, metric, o2q, pq, options)[0])
        sens.append({"param": param, "low": vals[0], "high": vals[1], "baseline": est,
                     "quantity": "estimate", "input_low": qlo, "input_high": qhi})
    width0 = band[1] - band[0]
    for param, rng in (("C_b", C_B_RANGE), ("k", K_RANGE), ("dT_over_T", DT_OVER_T_RANGE),
                       ("L_factor", L_FACTOR_RANGE)):
        widths = []
        for v in rng:
            f2 = _fractions_with_fixed(mc, u_cm_s, L_mm, param, v)
            b2 = widen_band(meta["kind"], est, lo, hi, widen_factor(f2))
            widths.append(b2[1] - b2[0])
        sens.append({"param": param, "low": widths[0], "high": widths[1], "baseline": width0,
                     "quantity": "band_width", "input_low": rng[0], "input_high": rng[1]})
    out["sensitivity"] = sens
    return json_safe(out)


# ---------------------------------------------------------------------- main
def _rules_available() -> bool:
    try:
        rules = importlib.import_module("engine.rules")
    except ImportError:
        return False
    return all(hasattr(rules, fn) for fn in RULE_METRICS.values())


def build_artifacts(out_dir: Path = ARTIFACT_DIR, n: int = 2000, seed: int = 0) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = list(FITTED) + (list(RULE_METRICS) if _rules_available() else [])
    written = []
    for preset in PRESETS:
        hab = {k: preset[k] for k in ("g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm")}
        for m in metrics:
            try:
                res = predict(m, **hab, n=n, seed=seed)
            except NotImplementedError as exc:
                print(f"skip {preset['id']} {m}: {exc}")
                continue
            res = {"preset_id": preset["id"], "habitat": hab, **json_safe(res)}
            path = out_dir / f"{preset['id']}_{m}.json"
            path.write_text(json.dumps(res, indent=2, allow_nan=False), encoding="utf-8")
            written.append(path)
    return written


def main() -> None:
    paths = build_artifacts()
    print(f"wrote {len(paths)} files to {ARTIFACT_DIR}")
    for p in paths:
        r = json.loads(p.read_text(encoding="utf-8"))
        est = r.get("estimate")
        print(f"  {p.name}: estimate={est!r} band90={r.get('band90')} "
              f"confidence={(r.get('transfer') or {}).get('confidence')}")


if __name__ == "__main__":
    main()
