"""S2: honesty test by holding out whole tested atmospheres (ADR-0009).

Contract: plan/contracts.md "Round 3 · S2 Holdout addendum".

Each fitted model (M1, M2 on FLEX; M3 on CFI-G) comes from one investigation, so leaving an
investigation out is impossible. Instead, for every tested atmosphere group (O2, pressure, and
for M1/M2 CO2 and He, rounded as engine.coverage rounds them: O2 and diluents to 3 decimals,
pressure to 2):

1. drop every test in the group and refit the model (bootstrap n_boot = 200 for M1/M3);
2. ask the app about the group's atmosphere exactly as ``engine.bounds.predict`` does, with the
   refitted model: the honesty gate then sees only the remaining tests;
3. compare with what the held-out tests actually did.

Query used for every group: g = 0 (the tests flew in microgravity, so the band is the plain model
band, widening factor 1), vent 10 cm/s (the preset value; at g = 0 it has no effect), and each
held-out test's own fuel and droplet size (M1/M2: L_mm = droplet size, which is the app's default
droplet size) or fuel and fuel fraction (M3). The group's predicted rate is the mean of the
per-test estimates; its band is the mean of the per-test band edges.

Hit rules (stated in the artifact):
    M1/M3: the observed share of self-extinctions gets a 90% Wilson interval; a hit is when that
        interval overlaps the predicted band ("overlap"), which is lenient for groups of 1-3
        tests; ``strict_hit`` (observed share inside the band) is reported too.
    M2: a hit is when the median observed extinction diameter is inside the band; the share of
        individual held-out diameters inside their own 5-95% band is pooled as well.

Run ``python -m engine.holdout`` to write artifacts/holdout.json.
"""

from __future__ import annotations

import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from engine.bounds import FITTED, METRICS, _model_eval, json_safe, predict
from engine.models import (
    CFIG_ID,
    FLEX_ID,
    TrainingSet,
    fit_model,
    load_tests,
    training_set,
)
from engine.physics import PSIA_PER_ATM
from engine.suppression_reference import wilson

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = ROOT / "artifacts" / "holdout.json"
HINDCAST_PATH = ROOT / "artifacts" / "hindcast_saffire.json"
N_BOOT = 200
QUERY_G = 0.0
QUERY_U = 10.0
QUERY_L_M3 = 10.0
MC_N = 200  # at g = 0 every sample is forced-flow (factor 1), so the Monte Carlo size has no effect
WEAK_BELOW = 10
O2_BAND = 0.10  # wide check: hold out a whole 0.10-wide O2 band at once
N_WORST = 5
ROUND_O2 = 3
ROUND_P = 2
ROUND_DIL = 3
DILUENT_METRICS = ("M1", "M2")
HIT_RULES = {
    "probability": ("Observed share of self-extinctions with a 90% Wilson interval; hit when that interval "
                    "overlaps the predicted 90% band (lenient for groups of 1-3 tests). strict_hit: the "
                    "observed share itself is inside the band."),
    "quantity": ("Hit when the median observed extinction diameter is inside the predicted 90% band; the share "
                 "of single held-out diameters inside their own band is pooled as a calibration check."),
}


# -------------------------------------------------------------------- groups
def group_keys(metric: str, ts: TrainingSet) -> pd.DataFrame:
    """One row per training test: rounded atmosphere key columns (engine.coverage rounding)."""
    df = pd.DataFrame({"o2": np.round(ts.o2.astype(float), ROUND_O2),
                       "p_atm": np.round(ts.p_atm.astype(float), ROUND_P)})
    if metric in DILUENT_METRICS:
        df["co2"] = ts.X["co2"].to_numpy(dtype=float).round(ROUND_DIL)
        df["he"] = ts.X["he"].to_numpy(dtype=float).round(ROUND_DIL)
    return df


def group_id(metric: str, key: dict) -> str:
    gid = f"{metric}-o2_{key['o2']:.3f}-p_{key['p_atm']:.2f}"
    if "co2" in key:
        gid += f"-co2_{key['co2']:.3f}-he_{key['he']:.3f}"
    return gid


def _psi_lookup() -> dict:
    df = load_tests()
    return {r: {"source_file": f, "source_row": int(s) if pd.notna(s) else None}
            for r, f, s in zip(df["record_id"], df["source_file"], df["source_row"])}


def _test_options(metric: str, ts: TrainingSet, i: int, key: dict) -> tuple[dict, float]:
    """Per-test predict options (the test's own fuel and size) and the habitat L_mm used."""
    x = ts.X.iloc[i]
    if metric in DILUENT_METRICS:
        d = float(x["droplet_mm"])
        fuel = "Methanol" if x["is_methanol"] > 0.5 else "Heptane"
        return {"fuel": fuel, "droplet_mm": d, "co2": key["co2"], "he": key["he"]}, d
    fuel = "ethane" if x["is_ethane"] > 0.5 else ("propane" if x["is_propane"] > 0.5 else "butane")
    return {"fuel": fuel, "fuel_fraction": float(x["fuel_fraction"])}, QUERY_L_M3


def _interval_gap(a: list[float], b: list[float]) -> float:
    """0 when [a] and [b] overlap, else the distance between them."""
    return max(0.0, max(a[0], b[0]) - min(a[1], b[1]))


# ---------------------------------------------------------------- one group
def _evaluate_group(metric: str, ts: TrainingSet, mask: np.ndarray, key: dict, psi: dict,
                    rest: TrainingSet, model) -> dict:
    """Score one atmosphere group (``mask``) against a model fitted on ``rest`` (which excludes it)."""
    idx = np.flatnonzero(mask)
    gid = group_id(metric, key)
    kind = METRICS[metric]["kind"]
    rows = [{"record_id": str(ts.record_id[i]), "investigation_id": str(ts.investigation_id[i]),
             **psi.get(str(ts.record_id[i]), {"source_file": None, "source_row": None})} for i in idx]
    atm = {"o2": key["o2"], "p_atm": key["p_atm"], "p_psia": key["p_atm"] * PSIA_PER_ATM}
    if metric in DILUENT_METRICS:
        atm.update(co2=key["co2"], he=key["he"])
    y = ts.y[idx]
    base = {"id": gid, "citation": f"eng:holdout:{gid}", "metric": metric, "atmosphere": atm,
            "n_tests": len(idx), "psi_rows": rows}
    if model is None:
        return {**base, "status": "skipped", "skip_reason": "too few remaining tests (or one outcome only) to refit",
                "covered": None, "hit": None}

    opts0, L0 = _test_options(metric, ts, int(idx[0]), key)
    gate = predict(metric, QUERY_G, atm["p_psia"], key["o2"], QUERY_U, L0, n=MC_N, seed=0, model=model, **opts0)
    covered = bool(gate["applicable"])
    nearest = gate["evidence"][0]["distance"] if gate["evidence"] else None

    est, lo, hi = [], [], []
    for i in idx:
        opts, L = _test_options(metric, ts, int(i), key)
        e, low, high, _ = _model_eval(model, metric, key["o2"], key["p_atm"], {**opts, "L_mm": L})
        est.append(e), lo.append(low), hi.append(high)
    est, lo, hi = np.array(est), np.array(lo), np.array(hi)
    band = [float(lo.mean()), float(hi.mean())]
    out = {**base, "status": "evaluated", "covered": covered, "nearest_remaining_distance": nearest,
           "n_train_remaining": len(rest.y), "model_version": model.model_version,
           "query": {"g_m_s2": QUERY_G, "u_cm_s": QUERY_U, "L_mm": L0,
                     "per_test_options": [_test_options(metric, ts, int(i), key)[0] for i in idx]},
           "predicted": {"estimate": float(est.mean()), "band90": band,
                         "shown_to_user": covered,
                         "note": None if covered else "Ungated model output; the app shows 'no evidence' here."}}
    if kind == "probability":
        k, n = int(y.sum()), len(y)
        rate = k / n
        ci = wilson(k, n)
        gap = _interval_gap(ci, band)
        ybar = float(rest.y.mean())
        out.update(
            observed={"positives": k, "n": n, "rate": rate, "interval90": ci},
            hit=gap == 0.0, strict_hit=bool(band[0] <= rate <= band[1]), gap=gap,
            error=float(est.mean() - rate),
            brier=float(np.mean((est - y) ** 2)), brier_baseline=float(np.mean((ybar - y) ** 2)),
            baseline_rate=ybar,
        )
    else:
        med = float(np.median(y))
        inside = int(np.sum((y >= lo) & (y <= hi)))
        out.update(
            observed={"n": len(y), "median": med, "min": float(y.min()), "max": float(y.max()),
                      "values": [float(v) for v in y]},
            hit=bool(band[0] <= med <= band[1]), strict_hit=bool(band[0] <= med <= band[1]),
            gap=_interval_gap([med, med], band), error=float(est.mean() - med),
            tests_inside_band=inside,
        )
    return out


# ------------------------------------------------------------------ summary
def _rate(k: int, n: int) -> dict:
    return {"k": int(k), "n": int(n), "rate": (k / n) if n else None, "interval90": wilson(k, n)}


def summarize(metric: str, groups: list[dict]) -> dict:
    ev = [g for g in groups if g["status"] == "evaluated"]
    cov = [g for g in ev if g["covered"]]
    unc = [g for g in ev if not g["covered"]]
    hits = sum(bool(g["hit"]) for g in cov)
    strict = sum(bool(g["strict_hit"]) for g in cov)
    s = {
        "metric": metric,
        "n_groups": len(groups),
        "n_tests": int(sum(g["n_tests"] for g in groups)),
        "n_skipped": len(groups) - len(ev),
        "n_covered": len(cov),
        "n_not_covered": len(unc),
        "band_coverage": _rate(hits, len(cov)),
        "strict_coverage": _rate(strict, len(cov)),
        "gate_precision": _rate(hits, len(cov)),
        "no_evidence_justified": _rate(sum(not g["hit"] for g in unc), len(unc)),
        "weak_test": len(cov) < WEAK_BELOW,
    }
    if METRICS[metric]["kind"] == "probability":
        tc = [g for g in cov]
        nt = sum(g["n_tests"] for g in tc)
        s["brier_covered"] = (sum(g["brier"] * g["n_tests"] for g in tc) / nt) if nt else None
        s["brier_baseline_covered"] = (sum(g["brier_baseline"] * g["n_tests"] for g in tc) / nt) if nt else None
    else:
        s["tests_inside_band_covered"] = _rate(sum(g["tests_inside_band"] for g in cov),
                                               sum(g["n_tests"] for g in cov))
    misses = sorted((g for g in cov if not g["hit"]), key=lambda g: -g["gap"])
    s["worst_misses"] = [{"id": g["id"], "atmosphere": g["atmosphere"], "n_tests": g["n_tests"],
                          "band90": g["predicted"]["band90"], "observed": g["observed"], "gap": g["gap"],
                          "error": g["error"]} for g in misses[:N_WORST]]
    big = sorted(cov, key=lambda g: -abs(g["error"]))
    s["largest_errors"] = [{"id": g["id"], "n_tests": g["n_tests"], "error": g["error"], "hit": g["hit"]}
                           for g in big[:N_WORST]]
    return s


def _refit(metric: str, rest: TrainingSet, n_boot: int, seed: int):
    if len(rest.y) < 5 or (METRICS[metric]["kind"] == "probability" and rest.y.min() == rest.y.max()):
        return None
    return fit_model(metric, rest, n_boot=n_boot, seed=seed)


def o2_band_id(o2: float) -> str:
    lo = math.floor(round(o2 / O2_BAND, 9)) * O2_BAND
    return f"o2_{lo:.2f}-{lo + O2_BAND:.2f}"


def holdout_metric(metric: str, train: TrainingSet | None = None, n_boot: int = N_BOOT, seed: int = 0,
                   max_groups: int | None = None, scheme: str = "atmosphere") -> dict:
    """Hold out tested-atmosphere groups of one fitted metric and score each one.

    scheme "atmosphere" (primary): each group is dropped on its own (one refit per group).
    scheme "o2_band" (wide check): every group in the same 0.10-wide O2 band is dropped together
    (one refit per band), so far-away atmospheres lose their neighbours and the gate is exercised.
    ``max_groups`` limits the number of hold-out units (used by the fast pytest subset).
    """
    if metric not in FITTED:
        raise KeyError(f"holdout needs a fitted metric {FITTED}, got {metric!r}")
    if scheme not in ("atmosphere", "o2_band"):
        raise ValueError(f"unknown scheme {scheme!r}")
    ts = training_set(metric) if train is None else train
    keys = group_keys(metric, ts)
    cols = list(keys.columns)
    keys["unit"] = (keys.apply(lambda r: group_id(metric, {c: r[c] for c in cols}), axis=1) if scheme == "atmosphere"
                    else keys["o2"].map(o2_band_id))
    psi = _psi_lookup()
    groups, units = [], []
    for unit, usub in keys.groupby("unit", sort=True):
        if max_groups is not None and len(units) >= max_groups:
            break
        umask = np.zeros(len(ts.y), dtype=bool)
        umask[usub.index.to_numpy()] = True
        rest = ts.subset(~umask)
        model = _refit(metric, rest, n_boot, seed)
        units.append({"id": unit, "n_tests": int(umask.sum()), "n_train_remaining": len(rest.y),
                      "refit": model is not None})
        for _, sub in usub.groupby(cols, sort=True):
            key = {c: float(sub[c].iloc[0]) for c in cols}
            mask = np.zeros(len(ts.y), dtype=bool)
            mask[sub.index.to_numpy()] = True
            g = _evaluate_group(metric, ts, mask, key, psi, rest, model)
            g["held_out_unit"] = unit
            groups.append(g)
    return {"metric": metric, "label": METRICS[metric]["label"], "kind": METRICS[metric]["kind"],
            "investigation_id": FLEX_ID if metric in DILUENT_METRICS else CFIG_ID, "scheme": scheme,
            "hit_rule": HIT_RULES[METRICS[metric]["kind"]], "units": units, "groups": groups,
            "summary": summarize(metric, groups)}


def saffire_section() -> dict:
    """The SAFFIRE-II hindcast, unchanged, with its caveat (cross-investigation check for M4)."""
    try:
        h = json.loads(HINDCAST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"available": False, "source": "artifacts/hindcast_saffire.json",
                "caveat": "Hindcast artifact missing; run python -m engine.hindcast."}
    head = h["headline"]
    sc = h["scores_all"]
    const = sc.get("baseline_always_more_at_1g_capped", {})
    return {
        "available": True,
        "source": "artifacts/hindcast_saffire.json",
        "metric": "M4",
        "headline": head,
        "scores": {k: {"hits": v["hits"], "n": v["n"], "accuracy": v["accuracy"]} for k, v in sc.items()},
        "caveat": (f"Not discriminative: the bridge scores {head['hits']}/{head['n']}, but the constant rule "
                   f"'1 g always burns more' also scores {const.get('hits')}/{const.get('n')}. It checks the "
                   f"direction of the gravity effect, not whether the bridge can tell samples apart."),
        "citation": "eng:holdout:saffire",
    }


def _overall(metrics: dict) -> dict:
    sums = [metrics[m]["summary"] for m in metrics]
    hits = sum(s["band_coverage"]["k"] for s in sums)
    ncov = sum(s["n_covered"] for s in sums)
    overall = {
        "n_groups": sum(s["n_groups"] for s in sums),
        "n_tests": sum(s["n_tests"] for s in sums),
        "n_covered": ncov,
        "n_not_covered": sum(s["n_not_covered"] for s in sums),
        "n_skipped": sum(s["n_skipped"] for s in sums),
        "band_coverage": _rate(hits, ncov),
        "gate_precision": _rate(hits, ncov),
        "no_evidence_justified": _rate(sum(s["no_evidence_justified"]["k"] for s in sums),
                                       sum(s["no_evidence_justified"]["n"] for s in sums)),
        "weak_test": ncov < WEAK_BELOW,
        "target_coverage": 0.90,
    }
    return overall


def build(n_boot: int = N_BOOT, seed: int = 0, max_groups: int | None = None) -> dict:
    metrics = {m: holdout_metric(m, n_boot=n_boot, seed=seed, max_groups=max_groups) for m in FITTED}
    wide = {m: holdout_metric(m, n_boot=n_boot, seed=seed, max_groups=max_groups, scheme="o2_band")
            for m in FITTED}
    return {
        "artifact": "holdout",
        "adr": "ADR-0009",
        "citation": "eng:holdout",
        "method": ("Each tested atmosphere is hidden in turn, the model is refitted without it, and the app is "
                   "asked about that atmosphere with the refitted model (same honesty gate, same band)."),
        "settings": {
            "n_boot": n_boot, "boot_seed": seed,
            "grouping": {"o2_decimals": ROUND_O2, "p_atm_decimals": ROUND_P, "diluent_decimals": ROUND_DIL,
                         "same_as": "engine.coverage", "diluents_in_key": list(DILUENT_METRICS)},
            "query": {"g_m_s2": QUERY_G, "u_cm_s": QUERY_U,
                      "L_mm": "M1/M2: each held-out test's droplet size; M3: 10",
                      "options": "each held-out test's own fuel (and droplet size or fuel fraction)",
                      "why": ("The tests flew in microgravity with no imposed flow, so g = 0 gives the plain model "
                              "band (widening factor 1); vent speed has no effect at g = 0.")},
            "group_band": "mean of the per-test estimates and band edges",
            "interval": "Wilson score, 90% two-sided",
            "weak_below_groups": WEAK_BELOW,
            "max_groups": max_groups,
        },
        "metrics": metrics,
        "overall": _overall(metrics),
        "wide_check": {
            "scheme": "o2_band",
            "what": (f"Every tested atmosphere in the same {O2_BAND:.2f}-wide O2 band is hidden at once, so an "
                     f"atmosphere far from the rest loses its neighbours. This checks the 'no evidence' side of "
                     f"the gate, which the primary test (one atmosphere at a time) almost never reaches."),
            "metrics": wide,
            "overall": _overall(wide),
        },
        "saffire_hindcast": saffire_section(),
    }


def _print_summary(title: str, metrics: dict, overall: dict) -> None:
    print(title)
    for m, res in metrics.items():
        s = res["summary"]
        bc = s["band_coverage"]
        extra = (f"Brier {s['brier_covered']:.3f} vs baseline {s['brier_baseline_covered']:.3f}"
                 if s.get("brier_covered") is not None else
                 f"single diameters inside band {s['tests_inside_band_covered']['k']}/"
                 f"{s['tests_inside_band_covered']['n']}" if "tests_inside_band_covered" in s else "")
        rate = None if bc["rate"] is None else round(bc["rate"], 3)
        print(f"  {m}: {s['n_groups']} groups ({s['n_tests']} tests), covered {s['n_covered']}, not covered "
              f"{s['n_not_covered']}, skipped {s['n_skipped']}; band coverage {bc['k']}/{bc['n']} = {rate} "
              f"{bc['interval90']}; strict {s['strict_coverage']['k']}/{s['strict_coverage']['n']}; "
              f"no-evidence justified {s['no_evidence_justified']['k']}/{s['no_evidence_justified']['n']}; {extra}"
              + ("; WEAK TEST" if s["weak_test"] else ""))
        for w in s["worst_misses"]:
            obs = {k: v for k, v in w["observed"].items() if k != "values"}
            print(f"     miss {w['id']} n={w['n_tests']} band={[round(b, 3) for b in w['band90']]} "
                  f"observed={obs} gap={w['gap']:.3f}")
    o = overall
    print(f"  overall: {o['n_groups']} groups, {o['n_covered']} covered, {o['n_not_covered']} not covered; band "
          f"coverage {o['band_coverage']['k']}/{o['band_coverage']['n']} {o['band_coverage']['interval90']}; "
          f"no-evidence justified {o['no_evidence_justified']['k']}/{o['no_evidence_justified']['n']}")


def main() -> None:
    t0 = time.perf_counter()
    doc = build()
    dt = time.perf_counter() - t0
    doc = {**doc, "generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "runtime_s": round(dt, 1)}
    ARTIFACT_PATH.write_text(json.dumps(json_safe(doc), indent=2, allow_nan=False), encoding="utf-8")
    print(f"wrote {ARTIFACT_PATH} in {dt:.1f} s")
    _print_summary("Primary: one tested atmosphere at a time", doc["metrics"], doc["overall"])
    _print_summary("Wide check: one 0.10 O2 band at a time", doc["wide_check"]["metrics"],
                   doc["wide_check"]["overall"])
    print(f"SAFFIRE: {doc['saffire_hindcast'].get('caveat')}")


if __name__ == "__main__":
    main()
