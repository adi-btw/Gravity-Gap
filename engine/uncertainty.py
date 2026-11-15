"""S3: what drives the uncertainty of a covered metric's 90% band (ADR-0008).

Contract: plan/contracts.md "Round 3 · S3 Uncertainty drivers addendum".

What really varies (checked in engine.bounds, ADR-0005): for M1-M3 the ESTIMATE depends only on
the atmosphere (O2, pressure, diluents) and the fuel/droplet options. Gravity, vent speed and the
four Monte Carlo inputs (C_b, k, dT/T, L) never move it. They reach the BAND only through the
regime fractions, which set the ADR-0005 widening factor f = 1 + 0.5 mixed + 1.0 buoyant. And k
enters only u_eff, not Ri, so it never reaches an M1-M3 band at all.

So the breakdown is a budget of the final band width W (shares sum to 1):

    model_uncertainty  W(f=1) / W
        the unwidened band: for M1/M3 the 5-95% spread of the bootstrap refits at fixed physics,
        for M2 the q05-q95 spread of the quantile regressions (no bootstrap; this mixes
        test-to-test scatter with model fit). Basis: PSI data (limited tests).
    gravity_widening   (W(f_min) - W(f=1)) / W
        the widening every plausible flame gets: f_min is the smallest per-sample factor over
        the Monte Carlo samples. No physics input can remove it. Basis: honesty rule.
    C_b, k, dT_over_T, L_mm, remainder   (W - W(f_min)) / W, split by first-order indices
        the extra widening that exists because some plausible input values put the flame in a
        more buoyant regime. Each per-sample band width W_i = W(f_i) is binned on each input
        (deciles); S_i = Var(E[W_i | bin_i]) / Var(W_i). That part of W is split by S_i, and
        (1 - sum S_i) is the "remainder" (interactions / not split). Basis: engineering
        assumption (the input ranges are not PSI data).

O2 and pressure are not sources: the habitat sets them exactly.

Run ``python -m engine.uncertainty`` to write artifacts/uncertainty/{preset}.json.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np

from engine.bounds import (
    FITTED,
    GATE_DISTANCE,
    METRICS,
    _distances,
    json_safe,
    predict,
    widen_band,
)
from engine.models import get_model, query_row
from engine.montecarlo import (
    C_B_RANGE,
    DT_OVER_T_RANGE,
    K_RANGE,
    L_FACTOR_RANGE,
    sample_physics,
)
from engine.physics import PSIA_PER_ATM, RI_BUOYANT_MIN, RI_FORCED_MAX
from engine.presets import PRESETS

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = ROOT / "artifacts" / "uncertainty"
PLANNER_PATH = ROOT / "artifacts" / "planner.json"
N_BINS = 10
PLANNER_MAX_DISTANCE = 2.0  # same reach as the honesty gate (planner kernel distance)
METHOD = ("Shares of the final 90% band width: the unwidened model band, the gravity widening every "
          "plausible flame gets, and the extra widening split between the Monte Carlo inputs by "
          "first-order (decile-binned) variance shares (ADR-0008).")

INPUTS = {
    "C_b": {"label": "Buoyant velocity coefficient C_b", "range": list(C_B_RANGE)},
    "k": {"label": "Flow-mixing coefficient k", "range": list(K_RANGE)},
    "dT_over_T": {"label": "Flame temperature rise dT/T", "range": list(DT_OVER_T_RANGE)},
    "L_mm": {"label": "Flame size L", "range": list(L_FACTOR_RANGE), "range_note": "x the habitat L_mm"},
}
SOURCE_ORDER = ("model_uncertainty", "gravity_widening", "C_b", "k", "dT_over_T", "L_mm", "remainder")


# ------------------------------------------------------------------ estimator
def first_order_indices(inputs: dict, y, n_bins: int = N_BINS) -> dict:
    """First-order variance shares by equal-count binning: Var(E[y | bin of x]) / Var(y).

    ``inputs`` maps a name to a 1-D sample array (same length as ``y``). Bins are equal-count
    (deciles for n_bins = 10) by rank, so ties are split deterministically. Returns 0 for every
    input when Var(y) == 0. The estimator is biased up by about (n_bins - 1) / n for an input that
    does not matter (0.0045 at n = 2000), and down a little for inputs whose effect changes within
    a bin; both are covered by the +/-0.05 check in tests/test_uncertainty.py.
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    var = float(np.var(y))
    out = {}
    for name, x in inputs.items():
        x = np.asarray(x, dtype=float)
        if len(x) != n:
            raise ValueError(f"input {name!r} has {len(x)} samples, y has {n}")
        if var <= 0:
            out[name] = 0.0
            continue
        rank = np.empty(n, dtype=int)
        rank[np.argsort(x, kind="stable")] = np.arange(n)
        b = rank * n_bins // n
        counts = np.bincount(b, minlength=n_bins)
        means = np.bincount(b, weights=y, minlength=n_bins) / np.maximum(counts, 1)
        between = float(np.sum(counts * (means - y.mean()) ** 2) / n)
        out[name] = between / var
    return out


# ------------------------------------------------------------------- helpers
def _per_sample_factor(mc: dict, u_cm_s: float) -> np.ndarray:
    """ADR-0005 widening factor of each Monte Carlo sample (1, 1.5 or 2); its mean is widen_factor."""
    ri = mc["ri"]
    forced = ri < RI_FORCED_MAX
    buoyant = ri > RI_BUOYANT_MIN
    mixed = ~forced & ~buoyant
    return 1.0 + 0.5 * mixed + 1.0 * buoyant


def _width(kind: str, est: float, lo: float, hi: float, f: float) -> float:
    b = widen_band(kind, est, lo, hi, float(f))
    return float(b[1] - b[0])


def _model_detail(metric: str, res: dict, o2: float, p_atm: float, options: dict, n_boot: int) -> dict:
    model = get_model(metric, n_boot=n_boot)
    lo, hi = res["ref_0g"]["band90"]
    d = _distances(model, o2, p_atm, float(options.get("co2", 0.0)) if metric != "M3" else 0.0,
                   float(options.get("he", 0.0)) if metric != "M3" else 0.0)
    near = int(np.sum(d <= GATE_DISTANCE))
    out = {"band90_unwidened": [lo, hi], "tests_within_gate": near, "n_train": res["n_train"],
           "investigation_id": str(model.train.investigation_id[0])}
    if model.kind == "probability":
        row, _ = query_row(metric, o2, p_atm, {**options, "L_mm": options.get("L_mm", 10.0)}, model)
        z = ((row[None, :] - model.boot_mu) / model.boot_sd * model.boot_w).sum(axis=1) + model.boot_b
        pb = 1.0 / (1.0 + np.exp(-z))
        out.update(source="bootstrap", n_boot=int(model.n_boot), boot_sd=float(np.std(pb)),
                   note=f"Spread of {model.n_boot} bootstrap refits of the logistic model at this atmosphere "
                        f"(physics fixed).")
    else:
        out.update(source="quantile_spread", n_boot=None, boot_sd=None,
                   note="M2 has no bootstrap: the band is the 5%-95% quantile-regression spread of extinction "
                        "diameters at this atmosphere, so it mixes test-to-test scatter with model uncertainty.")
    return out


def _load_planner() -> list[dict]:
    try:
        return json.loads(PLANNER_PATH.read_text(encoding="utf-8"))["items"]
    except (OSError, ValueError, KeyError):
        return []


def nearest_planner_candidate(metric: str, g_m_s2: float, p_psia: float, o2: float, u_cm_s: float,
                              co2: float = 0.0) -> dict | None:
    """Closest same-metric Planner item (planner kernel distance <= 2), or None."""
    from engine.planner import _kernel

    hab = {"g_m_s2": g_m_s2, "p_psia": p_psia, "o2": o2, "u_cm_s": u_cm_s, "co2": co2}
    best = None
    for it in _load_planner():
        if it.get("metric") != metric:
            continue
        k = _kernel(hab, it)
        dist = math.sqrt(max(-2.0 * math.log(max(k, 1e-300)), 0.0))
        if best is None or dist < best[0]:
            best = (dist, it)
    if best is None or best[0] > PLANNER_MAX_DISTANCE:
        return None
    it = best[1]
    keys = ("rank", "metric", "type", "g_m_s2", "p_psia", "o2", "u_cm_s", "co2")
    return {**{k: it.get(k) for k in keys}, "distance": round(best[0], 4) + 0.0}


def _lever(metric: str, sources: list[dict], hab: dict, detail: dict) -> dict:
    cand = [s for s in sources if s["id"] != "remainder"]
    top = max(cand, key=lambda s: s["share"])
    pct = 5 * round(20 * top["share"])
    planner = None
    if top["id"] == "model_uncertainty":
        planner = nearest_planner_candidate(metric, hab["g_m_s2"], hab["p_psia"], hab["o2"], hab["u_cm_s"],
                                            hab.get("co2", 0.0))
        text = (f"About {pct}% of this band comes from the model itself: {detail['tests_within_gate']} "
                f"{detail['investigation_id']} tests lie within the honesty-gate distance of this atmosphere. "
                f"More tests near {100 * hab['o2']:.1f}% O2 and {hab['p_psia']:g} psia would shrink it the most.")
        text += (f" See Planner candidate #{planner['rank']}." if planner
                 else " No Planner candidate is close to this habitat.")
    elif top["id"] == "gravity_widening":
        text = (f"About {pct}% of this band is the gravity honesty widening (ADR-0005): the tests had no "
                f"buoyancy, and at this gravity and vent speed every plausible flame is at least partly "
                f"buoyancy-driven. No physics input can remove it; only fire tests run in partial gravity, "
                f"which the PSI data do not have, could.")
    else:
        lo, hi = INPUTS[top["id"]]["range"]
        text = (f"The biggest single source is {INPUTS[top['id']]['label']} (about {pct}%). It is an "
                f"engineering assumption (range {lo:g} to {hi:g}), not PSI data. It decides whether the flame "
                f"here counts as mixed or buoyancy-dominated, which sets how much the band is widened. Pinning "
                f"it down would either remove this part of the band or confirm it.")
    return {"source": top["id"], "share": top["share"], "basis": top["basis"], "text": text,
            "planner_candidate": planner}


# -------------------------------------------------------------------- drivers
def drivers(metric: str, g_m_s2: float, p_psia: float, o2: float, u_cm_s: float, L_mm: float,
            co2: float = 0.0, he: float = 0.0, n: int = 2000, seed: int = 0, n_boot: int = 500,
            **options) -> dict:
    """Shares of the covered metric's 90% band width by source (ADR-0008). JSON-safe."""
    metric = metric.upper()
    if metric not in METRICS:
        raise KeyError(f"unknown metric {metric!r}; known: {sorted(METRICS)}")
    base = {"metric": metric, "label": METRICS[metric]["label"], "citation": f"eng:drivers:{metric}",
            "adr": "ADR-0008"}
    if metric not in FITTED:
        return {**base, "applicable": False,
                "reason": f"{metric} is a rule table with categories, not a numeric band, so there is no band "
                          f"width to split."}
    dil = {"co2": co2, "he": he} if metric in ("M1", "M2") else {}
    res = predict(metric, g_m_s2, p_psia, o2, u_cm_s, L_mm, n=n, seed=seed, n_boot=n_boot, **dil, **options)
    if not res["applicable"]:
        return {**base, "applicable": False,
                "reason": "No evidence at this atmosphere (honesty gate), so there is no band to break down."}

    kind = res["kind"]
    est = res["estimate"]
    lo, hi = res["ref_0g"]["band90"]
    mc = sample_physics(g_m_s2, p_psia, o2, u_cm_s, L_mm, n=n, seed=seed)
    f_i = _per_sample_factor(mc, u_cm_s)
    f_mean = float(f_i.mean())
    f_min = float(f_i.min())
    w_model = _width(kind, est, lo, hi, 1.0)
    w_floor = _width(kind, est, lo, hi, f_min)
    w_final = _width(kind, est, lo, hi, f_mean)
    widths = {f: _width(kind, est, lo, hi, f) for f in np.unique(f_i)}
    w_i = np.array([widths[f] for f in f_i])

    s = mc["samples"]
    reach = {"C_b": True, "k": False, "dT_over_T": True, "L_mm": True}  # k enters u_eff only, not Ri
    s1 = first_order_indices({k: s[k] for k, r in reach.items() if r}, w_i)
    s1["k"] = 0.0
    sum_s1 = sum(s1.values())

    if w_final <= 0:
        model_share, floor_share, input_part = 1.0, 0.0, 0.0
    else:
        model_share = w_model / w_final
        floor_share = (w_floor - w_model) / w_final
        input_part = (w_final - w_floor) / w_final

    notes = {
        "model_uncertainty": "Unwidened model band: limited tests at this atmosphere.",
        "gravity_widening": ("Widening every plausible flame gets at this gravity and vent speed (ADR-0005)."
                             if floor_share > 0 else "No widening: the flame is forced-flow in every sample."),
        "C_b": "Moves the buoyant velocity, so it can tip a sample between regimes.",
        "k": "Enters only the effective flow speed, not the Richardson number, so it never changes this band.",
        "dT_over_T": "Moves the buoyant velocity, so it can tip a sample between regimes.",
        "L_mm": "Moves the buoyant velocity, so it can tip a sample between regimes.",
        "remainder": "Interactions between the inputs: not split to one input.",
    }
    shares = {"model_uncertainty": model_share, "gravity_widening": floor_share,
              **{k: input_part * s1[k] for k in INPUTS}, "remainder": input_part * (1.0 - sum_s1)}
    basis = {"model_uncertainty": "psi_data", "gravity_widening": "honesty_rule"}
    labels = {"model_uncertainty": "Model uncertainty (limited tests)",
              "gravity_widening": "Gravity widening (honesty rule)",
              "remainder": "Interactions / not split", **{k: v["label"] for k, v in INPUTS.items()}}
    sources = [{"id": k, "label": labels[k], "share": round(float(shares[k]), 4) + 0.0,  # no -0.0
                "basis": basis.get(k, "engineering_assumption"),
                "reaches_band": bool(reach.get(k, True)) if k in INPUTS else True,
                "note": notes[k]} for k in SOURCE_ORDER]

    p_atm = p_psia / PSIA_PER_ATM
    detail = _model_detail(metric, res, o2, p_atm, {**dil, **options, "L_mm": L_mm}, n_boot)
    hab = {"g_m_s2": g_m_s2, "p_psia": p_psia, "o2": o2, "u_cm_s": u_cm_s, "L_mm": L_mm, **dil}
    out = {
        **base,
        "applicable": True,
        "kind": kind,
        "unit": res["unit"],
        "estimate": est,
        "band90": res["band90"],
        "band_width": w_final,
        "model_band90": [lo, hi],
        "model_band_width": w_model,
        "widen_factor": f_mean,
        "widen_factor_min": f_min,
        "regime_fractions": res["regime_fractions"],
        "what_varies": {
            "estimate": ("Only the atmosphere (O2, pressure, diluents) and fuel options move the estimate; gravity, "
                         "vent speed and the Monte Carlo inputs do not (ADR-0005)."),
            "band": ("The Monte Carlo inputs reach the band only through the regime fractions that set the "
                     "gravity widening; k never reaches it."),
        },
        "sources": sources,
        "shares_sum": round(float(sum(shares.values())), 6),
        "first_order": {**{k: round(float(s1[k]), 4) for k in INPUTS}, "sum": round(float(sum_s1), 4),
                        "n_bins": N_BINS, "output": "per-sample band width W(f_i)"},
        "model_detail": detail,
        "lever": None,
        "method": METHOD,
        "n": int(n),
        "seed": int(seed),
        "model_version": res["model_version"],
    }
    out["lever"] = _lever(metric, sources, hab, detail)
    return json_safe(out)


# ---------------------------------------------------------------------- main
def build_artifacts(out_dir: Path = ARTIFACT_DIR, n: int = 2000, seed: int = 0) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for preset in PRESETS:
        hab = {k: preset[k] for k in ("g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm")}
        doc = {"preset_id": preset["id"], "habitat": hab, "method": METHOD, "adr": "ADR-0008",
               "metrics": {m: drivers(m, **hab, n=n, seed=seed) for m in METRICS}}
        path = out_dir / f"{preset['id']}.json"
        path.write_text(json.dumps(json_safe(doc), indent=2, allow_nan=False), encoding="utf-8")
        written.append(path)
    return written


def main() -> None:
    t0 = time.perf_counter()
    get_model("M1"), get_model("M2"), get_model("M3")
    t_fit = time.perf_counter() - t0
    t1 = time.perf_counter()
    paths = build_artifacts()
    t_run = time.perf_counter() - t1
    print(f"wrote {len(paths)} files to {ARTIFACT_DIR} (model fits {t_fit:.1f} s, drivers {t_run:.2f} s "
          f"for {len(paths) * len(METRICS)} metric queries)")
    for p in paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        for m, d in doc["metrics"].items():
            if not d["applicable"]:
                print(f"  {doc['preset_id']} {m}: not applicable ({d['reason'][:60]})")
                continue
            sh = ", ".join(f"{s['id']}={s['share']:.3f}" for s in d["sources"])
            print(f"  {doc['preset_id']} {m}: width {d['band_width']:.3f} -> {sh}; lever {d['lever']['source']}")


if __name__ == "__main__":
    main()
