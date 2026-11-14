"""C13 validation report for the E2 bounds models (plan/03 §5).

V2  5-fold cross-validation inside each investigation (seeded):
    M1, M3: ROC AUC, Brier score vs a base-rate baseline, 3-bin calibration.
    M2: pinball loss at q = 0.05/0.5/0.95 vs constant-quantile baseline,
        empirical coverage of the 5-95% interval, MAE of the median.
    Leave-one-investigation-out (plan/03 §5 V2) is NOT possible: FLEX and
    CFI-G share no outcome definition and no fuel, so we say so in the report.
V3  SAFFIRE-II hindcast: owned by DE's M4 rule table (engine.rules); this report
    only points to it (and lists whether it is available).
V5  Sensitivity summary from engine.bounds.predict for every preset.

Run ``python -m engine.validation`` to write artifacts/validation_report.md.
"""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.metrics import brier_score_loss, mean_pinball_loss, roc_auc_score
from sklearn.model_selection import KFold, StratifiedKFold

from engine import __version__
from engine.bounds import FITTED, METRICS, predict
from engine.models import QUANTILES, fit_point, get_model, training_set
from engine.presets import PRESETS

REPORT_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "validation_report.md"
N_FOLDS = 5
SEED = 0


def _features(metric):
    ts = training_set(metric)
    feats = get_model(metric).features
    return ts, ts.X[feats].to_numpy(dtype=float), ts.y


def cv_classifier(metric: str) -> dict:
    ts, X, y = _features(metric)
    oof = np.empty(len(y))
    base = np.empty(len(y))
    for tr, te in StratifiedKFold(N_FOLDS, shuffle=True, random_state=SEED).split(X, y):
        oof[te] = fit_point(metric, X[tr], y[tr])(X[te])
        base[te] = y[tr].mean()
    bins = np.quantile(oof, [0, 1 / 3, 2 / 3, 1])
    calib = []
    idx = np.clip(np.searchsorted(bins, oof, side="right") - 1, 0, 2)
    for b in range(3):
        m = idx == b
        if m.any():
            calib.append({"bin": b + 1, "n": int(m.sum()), "mean_pred": float(oof[m].mean()),
                          "observed": float(y[m].mean())})
    return {
        "metric": metric, "n": int(len(y)), "positives": int(y.sum()),
        "auc": float(roc_auc_score(y, oof)),
        "brier": float(brier_score_loss(y, oof)),
        "brier_baseline": float(brier_score_loss(y, base)),
        "calibration": calib,
    }


def cv_quantile(metric: str = "M2") -> dict:
    ts, X, y = _features(metric)
    oof = np.empty((3, len(y)))
    base = np.empty((3, len(y)))
    for tr, te in KFold(N_FOLDS, shuffle=True, random_state=SEED).split(X):
        oof[:, te] = fit_point(metric, X[tr], y[tr])(X[te])
        base[:, te] = np.quantile(y[tr], QUANTILES)[:, None]
    pin = {q: float(mean_pinball_loss(y, oof[i], alpha=q)) for i, q in enumerate(QUANTILES)}
    pin_b = {q: float(mean_pinball_loss(y, base[i], alpha=q)) for i, q in enumerate(QUANTILES)}
    cover = float(np.mean((y >= oof[0]) & (y <= oof[2])))
    cover_b = float(np.mean((y >= base[0]) & (y <= base[2])))
    return {
        "metric": metric, "n": int(len(y)), "pinball": pin, "pinball_baseline": pin_b,
        "coverage90": cover, "coverage90_baseline": cover_b,
        "mae_median": float(np.mean(np.abs(y - oof[1]))),
        "mae_median_baseline": float(np.mean(np.abs(y - base[1]))),
        "mean_interval_width": float(np.mean(oof[2] - oof[0])),
    }


def sensitivity_summary() -> list[dict]:
    rows = []
    for p in PRESETS:
        hab = {k: p[k] for k in ("g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm")}
        for m in FITTED:
            r = predict(m, **hab)
            if not r["applicable"]:
                rows.append({"preset": p["id"], "metric": m, "applicable": False, "reason": r["reason"]})
                continue
            def _v(x, base):
                return base if x is None else x
            est_sw = {s["param"]: abs(_v(s["high"], s["baseline"]) - _v(s["low"], s["baseline"]))
                      for s in r["sensitivity"] if s["quantity"] == "estimate"}
            bw_sw = {s["param"]: abs(s["high"] - s["low"]) for s in r["sensitivity"] if s["quantity"] == "band_width"}
            top_est = max(est_sw, key=est_sw.get)
            top_bw = max(bw_sw, key=bw_sw.get)
            rows.append({
                "preset": p["id"], "metric": m, "applicable": True, "estimate": r["estimate"],
                "band90": r["band90"], "confidence": r["transfer"]["confidence"],
                "top_estimate_param": top_est, "top_estimate_swing": est_sw[top_est],
                "top_band_param": top_bw, "top_band_swing": bw_sw[top_bw],
            })
    return rows


def _rules_note() -> str:
    try:
        rules = importlib.import_module("engine.rules")
    except ImportError:
        return ("`engine.rules` (DE) was not importable when this report was built, so the SAFFIRE-II "
                "hindcast is not reported here. It belongs to M4 and must be reported by DE with hits and "
                "misses shown.")
    has = [fn for fn in ("predict_m4", "predict_m5") if hasattr(rules, fn)]
    hind = getattr(rules, "hindcast_saffire", None)
    txt = (f"`engine.rules` is available (functions: {', '.join(has) or 'none'}). The SAFFIRE-II hindcast "
           f"(predict 1 g burn extent from microgravity data plus the bridge at g = 9.81, compare with the 1 g "
           f"columns of `data/clean/psi_saffire_ug_vs_1g.csv`) is owned by DE's M4 rule table; see "
           f"`artifacts/rules.json` and `tests/test_rules.py`.")
    if callable(hind):
        try:
            txt += f"\n\nHindcast summary from `engine.rules.hindcast_saffire()`: `{hind()}`"
        except Exception as exc:  # report, never hide
            txt += f"\n\n`hindcast_saffire()` raised: {exc!r}"
    return txt


def _f(x, nd=3):
    return "n/a" if x is None else f"{x:.{nd}f}"


def build_report() -> str:
    c1, c3 = cv_classifier("M1"), cv_classifier("M3")
    q2 = cv_quantile("M2")
    sens = sensitivity_summary()
    L = [
        "# Validation report: E2 bounds models (M1-M3)",
        "",
        f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} by `python -m engine.validation` "
        f"(engine {__version__}). Model versions: "
        + ", ".join(f"{m} `{get_model(m).model_version}`" for m in FITTED) + ".",
        "",
        "All numbers are out-of-fold (5-fold, seed 0) on microgravity PSI data. They measure how well each model "
        "interpolates *within* its own investigation; they say nothing about partial gravity, which no PSI test "
        "covers (see ADR-0005).",
        "",
        "## V2 Cross-validation",
        "",
        "Leave-one-investigation-out (plan/03 §5) is not possible: FLEX (droplets, heptane/methanol, outcome "
        "extinction/completion) and CFI-G (gas spherical burner, ethane/propane/butane, outcome self-extinguished/"
        "flow-terminated) share no outcome definition or fuel. We report within-investigation k-fold instead.",
        "",
        "### Classifiers (M1, M3)",
        "",
        "| Metric | Data | n | positives | AUC | Brier | Brier (base rate) |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in (c1, c3):
        L.append(f"| {c['metric']} | {METRICS[c['metric']]['data']} | {c['n']} | {c['positives']} | "
                 f"{_f(c['auc'])} | {_f(c['brier'])} | {_f(c['brier_baseline'])} |")
    L += ["", "Calibration (out-of-fold predictions split into terciles):", "",
          "| Metric | Bin | n | mean predicted | observed rate |", "|---|---|---|---|---|"]
    for c in (c1, c3):
        for b in c["calibration"]:
            L.append(f"| {c['metric']} | {b['bin']} | {b['n']} | {_f(b['mean_pred'])} | {_f(b['observed'])} |")
    L += [
        "",
        "### Quantile model (M2, extinction diameter in mm)",
        "",
        f"n = {q2['n']}. Linear quantile regression at q = 0.05 / 0.5 / 0.95 on standardized features.",
        "",
        "| Quantity | Model | Constant-quantile baseline |",
        "|---|---|---|",
    ]
    for q in QUANTILES:
        L.append(f"| Pinball loss q={q} | {_f(q2['pinball'][q], 4)} | {_f(q2['pinball_baseline'][q], 4)} |")
    L += [
        f"| 5-95% interval coverage (target 0.90) | {_f(q2['coverage90'])} | {_f(q2['coverage90_baseline'])} |",
        f"| MAE of median (mm) | {_f(q2['mae_median'])} | {_f(q2['mae_median_baseline'])} |",
        f"| Mean 5-95% width (mm) | {_f(q2['mean_interval_width'])} | |",
        "",
        "### Reading these honestly",
        "",
    ]
    notes = []
    for c in (c1, c3):
        better = c["brier"] < c["brier_baseline"]
        notes.append(f"- {c['metric']}: AUC {_f(c['auc'])}; Brier {_f(c['brier'])} is "
                     f"{'better' if better else 'NOT better'} than the base-rate baseline "
                     f"{_f(c['brier_baseline'])} (margin {_f(c['brier_baseline'] - c['brier'])}"
                     + ("; marginal, so treat this model's discrimination as weak)." if c["brier_baseline"] - c["brier"] < 0.01 else ")."))
    notes.append(f"- M1 is imbalanced ({c1['positives']} extinctions of {c1['n']}); 61 disruption tests are excluded "
                 "(ADR-0004), so M1 answers \"extinction vs burning to completion\" only.")
    notes.append("- M3 has a near-separation: every normal flame below ~0.33 O2 self-extinguished, so its "
                 "low-O2 predictions are close to 1 and the bootstrap band there is narrow; that is the data, not "
                 "certainty about cabin fires.")
    notes.append(f"- M2 interval coverage {_f(q2['coverage90'])} vs nominal 0.90"
                 + (" (under-covers: treat the band as optimistic)." if q2["coverage90"] < 0.85 else "."))
    notes.append("- Habitat queries with L_mm = 10 use the largest tested droplet (4.67 mm for M1, M2 clip), "
                 "an edge of the training range.")
    L += notes
    L += ["", "## V3 SAFFIRE-II hindcast", "", _rules_note(), "",
          "## V5 Sensitivity (tornado) summary", "",
          "For each preset: the atmosphere input that moves the estimate most (O2 +/-0.03, pressure +/-20%), "
          "and the physics coefficient that moves the 90% band width most (C_b, k, dT/T, L). k enters only u_eff, "
          "not Ri, so it never changes M1-M3 bands.", "",
          "| Preset | Metric | Estimate | 90% band | Transfer | Top estimate driver (swing) | Top band driver (swing) |",
          "|---|---|---|---|---|---|---|"]
    for r in sens:
        if not r["applicable"]:
            L.append(f"| {r['preset']} | {r['metric']} | gated | - | - | {r['reason']} | - |")
            continue
        L.append(f"| {r['preset']} | {r['metric']} | {_f(r['estimate'])} | [{_f(r['band90'][0])}, "
                 f"{_f(r['band90'][1])}] | {r['confidence']} | {r['top_estimate_param']} "
                 f"({_f(r['top_estimate_swing'])}) | {r['top_band_param']} ({_f(r['top_band_swing'])}) |")
    L += ["", "## Not done", "",
          "- V4 literature sanity check (needs E4 papers).",
          "- No partial-gravity ground truth exists; the widened bands (ADR-0005) are a stated assumption, "
          "not a validated quantity.", ""]
    return "\n".join(L)


def main() -> None:
    text = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    print(text)


if __name__ == "__main__":
    main()
