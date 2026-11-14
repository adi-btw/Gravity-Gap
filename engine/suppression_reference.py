"""Empirical FLEX suppression reference: droplet-flame outcomes versus diluent (R2, model-free).

For each diluent (CO2, He) and fuel (Heptane, Methanol) the FLEX (PSI-69) tests are binned by diluent
fraction and crossed with O2 bands, and each cell reports raw outcome counts and an extinction rate.
Nothing here uses a fitted model; it exists so the M1/M2 suppression curves (engine.suppression) can
be checked against the raw data direction and drawn as reference dots.

Rules (also written into the JSON under ``rules``):

* Rows: ``investigation_id == "PSI-69"`` in data/clean/psi_tests.csv, outcome in
  {extinction, completion, disruption}. A row missing O2 or the diluent fraction is dropped (counted).
  A missing pressure does not drop the row (pressure is only reported as a range).
* Exclusion: a row whose *other* diluent is > 0 is excluded from this diluent's table (counted).
  Undiluted rows (CO2 = He = 0) form the 0 bin of both tables.
* Diluent bins: base edges 0 | (0, 0.1] | (0.1, 0.2] | (0.2, 0.3] | (0.3, 0.4] | > 0.4. Within each
  fuel x O2 band, consecutive non-empty base bins are merged left to right until the merged bin has
  n >= 3; a trailing bin with n < 3 is merged into the previous diluted bin. The 0 bin is never merged.
  Empty bins are omitted.
* O2 bands: <= 0.17 | (0.17, 0.22] | > 0.22.
* extinction_rate = extinctions / (extinctions + completions). Disruptions (droplet broke apart, so
  the self-extinction outcome is unknown) are excluded from the rate, the same rule as M1 (ADR-0004).
  The rate is null when extinctions + completions = 0. Interval: Wilson score, 90 % (z = 1.6449).
* Trend (per diluent x fuel x O2 band): bins with extinctions + completions >= 3 are "rated". Fewer
  than 2 rated bins (or no rated diluted bin) -> "insufficient". Otherwise delta = rate(last rated
  bin) - rate(first rated bin): >= +0.10 "rises", <= -0.10 "falls", else "flat". Flags:
  ``non_monotonic`` (a step reverses by >= 0.10) and ``intervals_overlap`` (first/last 90 % intervals
  overlap, so the change is not distinguishable at this n).

Run ``python -m engine.suppression_reference`` to write artifacts/suppression_reference.json.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "clean" / "psi_tests.csv"
CATALOG = ROOT / "artifacts" / "catalog.json"
OUT = ROOT / "artifacts" / "suppression_reference.json"

FLEX_ID = "PSI-69"
DILUENTS = {"co2": "co2_mole_fraction", "he": "he_mole_fraction"}
OTHER = {"co2": "he", "he": "co2"}
FUELS = ("Heptane", "Methanol")
OUTCOMES = ("extinction", "completion", "disruption")
# Base diluent edges: (lo, hi] intervals after the exact-zero bin; the last is open-ended.
BASE_EDGES = (0.0, 0.1, 0.2, 0.3, 0.4)
O2_BANDS = (
    {"id": "le_0.17", "label": "O2 <= 0.17", "lo": None, "hi": 0.17},
    {"id": "0.17_0.22", "label": "0.17 < O2 <= 0.22", "lo": 0.17, "hi": 0.22},
    {"id": "gt_0.22", "label": "O2 > 0.22", "lo": 0.22, "hi": None},
)
MIN_BIN_N = 3
TREND_MIN_RATED = 3
TREND_DELTA = 0.10
WILSON_Z = 1.6448536269514722  # two-sided 90 %
DILUTED_O2_CEILING = 0.25
ROUND = 6


def wilson(k: int, n: int, z: float = WILSON_Z) -> list[float] | None:
    if n <= 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [round(max(0.0, centre - half), ROUND), round(min(1.0, centre + half), ROUND)]


def _base_bin(x: float) -> int:
    """0 for x == 0, 1..len(BASE_EDGES) for (edge[i-1], edge[i]] and the open last bin."""
    if x <= 0:
        return 0
    for i, hi in enumerate(BASE_EDGES[1:], start=1):
        if x <= hi + 1e-9:
            return i
    return len(BASE_EDGES)


def _base_label(i: int) -> tuple[str, float, float | None]:
    if i == 0:
        return "0", 0.0, 0.0
    if i == len(BASE_EDGES):
        return f">{BASE_EDGES[-1]:g}", BASE_EDGES[-1], None
    return f"({BASE_EDGES[i - 1]:g}, {BASE_EDGES[i]:g}]", BASE_EDGES[i - 1], BASE_EDGES[i]


def _o2_band(o2: float) -> str:
    if o2 <= 0.17 + 1e-9:
        return O2_BANDS[0]["id"]
    if o2 <= 0.22 + 1e-9:
        return O2_BANDS[1]["id"]
    return O2_BANDS[2]["id"]


def load_flex(path: Path = DATA) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    return df[df["investigation_id"] == FLEX_ID].copy()


def _merge_bins(present: list[int], counts: dict[int, int]) -> list[list[int]]:
    """Group consecutive non-empty diluted base bins so each group has n >= MIN_BIN_N."""
    groups: list[list[int]] = []
    cur: list[int] = []
    for b in present:
        cur.append(b)
        if sum(counts[x] for x in cur) >= MIN_BIN_N:
            groups.append(cur)
            cur = []
    if cur:
        if groups:
            groups[-1].extend(cur)
        else:
            groups.append(cur)
    return groups


def _rng(s: pd.Series) -> list[float] | None:
    s = s.dropna()
    if s.empty:
        return None
    return [round(float(s.min()), ROUND), round(float(s.max()), ROUND)]


def _cell(rows: pd.DataFrame, dil_col: str, group: list[int]) -> dict:
    labels = [_base_label(b) for b in group]
    lo, hi = labels[0][1], labels[-1][2]
    if group == [0]:
        label = "0"
    elif hi is None:
        label = f">{lo:g}"
    else:
        label = f"({lo:g}, {hi:g}]"
    k = int((rows["outcome"] == "extinction").sum())
    c = int((rows["outcome"] == "completion").sum())
    d = int((rows["outcome"] == "disruption").sum())
    rated = k + c
    rate = round(k / rated, ROUND) if rated else None
    return {
        "bin": label,
        "fraction_lo": lo,
        "fraction_hi": hi,
        "lo_inclusive": group == [0],
        "merged_from": [lb[0] for lb in labels] if len(group) > 1 else None,
        "fraction_range": _rng(rows[dil_col]),
        "n": int(len(rows)),
        "extinctions": k,
        "completions": c,
        "disruptions": d,
        "extinction_rate": rate,
        "interval90": wilson(k, rated),
        "o2_range": _rng(rows["o2_mole_fraction"]),
        "p_atm_range": _rng(rows["pressure_atm"]),
        "n_missing_pressure": int(rows["pressure_atm"].isna().sum()),
        "record_ids": sorted(rows["record_id"].astype(str).tolist()),
    }


def _trend(bins: list[dict]) -> dict:
    rated = [b for b in bins if (b["extinctions"] + b["completions"]) >= TREND_MIN_RATED]
    seq = [{"bin": b["bin"], "extinction_rate": b["extinction_rate"],
            "rated_n": b["extinctions"] + b["completions"]} for b in rated]
    if len(rated) < 2 or all(b["bin"] == "0" for b in rated):
        return {"direction": "insufficient", "delta": None, "non_monotonic": None,
                "intervals_overlap": None, "sequence": seq}
    delta = round(rated[-1]["extinction_rate"] - rated[0]["extinction_rate"], ROUND)
    if delta >= TREND_DELTA:
        direction = "rises"
    elif delta <= -TREND_DELTA:
        direction = "falls"
    else:
        direction = "flat"
    steps = [b["extinction_rate"] - a["extinction_rate"] for a, b in zip(rated, rated[1:])]
    reverses = any(st <= -TREND_DELTA for st in steps) if delta > 0 else         any(st >= TREND_DELTA for st in steps) if delta < 0 else False
    lo_a, hi_a = rated[0]["interval90"]
    lo_b, hi_b = rated[-1]["interval90"]
    return {"direction": direction, "delta": delta, "from_bin": rated[0]["bin"],
            "to_bin": rated[-1]["bin"], "non_monotonic": bool(reverses),
            "intervals_overlap": bool(lo_a <= hi_b and lo_b <= hi_a), "sequence": seq}


def _flex_doi() -> str | None:
    try:
        cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for inv in cat.get("investigations", []):
        if inv.get("id") == FLEX_ID:
            return inv.get("doi")
    return None


def build(df: pd.DataFrame | None = None) -> dict:
    flex = load_flex() if df is None else df.copy()
    n_flex = int(len(flex))
    flex = flex[flex["outcome"].isin(OUTCOMES)]
    dropped_outcome = n_flex - int(len(flex))
    flex = flex[flex["fuel"].isin(FUELS)]
    dropped_fuel = n_flex - dropped_outcome - int(len(flex))

    tables: dict = {}
    trends: dict = {}
    accounting: dict = {}
    for dil, col in DILUENTS.items():
        other_col = DILUENTS[OTHER[dil]]
        missing = flex[col].isna() | flex["o2_mole_fraction"].isna() | flex[other_col].isna()
        excl_other = (~missing) & (flex[other_col] > 0)
        used = flex[(~missing) & (~excl_other)].copy()
        used["_bin"] = used[col].map(_base_bin)
        used["_band"] = used["o2_mole_fraction"].map(_o2_band)
        accounting[dil] = {
            "flex_rows": n_flex,
            "dropped_outcome_not_flex_label": dropped_outcome,
            "dropped_fuel_not_heptane_methanol": dropped_fuel,
            "dropped_missing_o2_or_diluent": int(missing.sum()),
            f"excluded_{OTHER[dil]}_gt_0": int(excl_other.sum()),
            "rows_used": int(len(used)),
            "rows_used_undiluted": int((used[col] == 0).sum()),
            "rows_used_diluted": int((used[col] > 0).sum()),
        }
        tables[dil] = {}
        trends[dil] = {}
        for fuel in FUELS:
            tables[dil][fuel] = {}
            trends[dil][fuel] = {}
            for band in O2_BANDS:
                sub = used[(used["fuel"] == fuel) & (used["_band"] == band["id"])]
                counts = sub["_bin"].value_counts().to_dict()
                bins = []
                if counts.get(0, 0):
                    bins.append(_cell(sub[sub["_bin"] == 0], col, [0]))
                present = sorted(b for b in counts if b > 0)
                for group in _merge_bins(present, counts):
                    bins.append(_cell(sub[sub["_bin"].isin(group)], col, group))
                tables[dil][fuel][band["id"]] = {"o2_band": band["label"], "n": int(len(sub)),
                                                 "bins": bins}
                trends[dil][fuel][band["id"]] = _trend(bins)

    any_dil = flex[(flex["co2_mole_fraction"].fillna(0) > 0) | (flex["he_mole_fraction"].fillna(0) > 0)]
    max_dil_o2 = round(float(any_dil["o2_mole_fraction"].max()), ROUND) if len(any_dil) else None
    max_o2_by = {}
    for dil, col in DILUENTS.items():
        s = flex.loc[flex[col].fillna(0) > 0, "o2_mole_fraction"]
        max_o2_by[dil] = round(float(s.max()), ROUND) if len(s) else None
    max_all_o2 = round(float(flex["o2_mole_fraction"].max()), ROUND)
    both = int(((flex["co2_mole_fraction"].fillna(0) > 0) & (flex["he_mole_fraction"].fillna(0) > 0)).sum())

    notes = [
        (f"No diluted FLEX test exceeds {DILUTED_O2_CEILING:.0%} O2: the highest O2 with CO2 or He > 0 is "
         f"{max_dil_o2} (CO2: {max_o2_by['co2']}, He: {max_o2_by['he']}); undiluted tests reach "
         f"{max_all_o2}.") if max_dil_o2 is not None and max_dil_o2 <= DILUTED_O2_CEILING else
        f"Highest O2 among diluted FLEX tests is {max_dil_o2} (undiluted tests reach {max_all_o2}).",
        f"{both} FLEX rows have both CO2 > 0 and He > 0.",
        "Empirical counts only: bins mix pressures, droplet sizes and O2 within a band, so a cell rate is "
        "not a controlled single-variable effect. Use it to check direction, not magnitude.",
        "Disruptions are excluded from the extinction rate (outcome unknown), as in M1 (ADR-0004); with "
        "most FLEX flames extinguishing, many cells sit near 1 and their trend is flat by construction.",
        "A missing pressure keeps the row (pressure is only reported as a range); see n_missing_pressure.",
    ]

    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generated_by": "engine.suppression_reference",
        "source": {"investigation_id": FLEX_ID, "acronym": "FLEX", "doi": _flex_doi(),
                   "file": "data/clean/psi_tests.csv"},
        "rules": {
            "rows": f"investigation_id == {FLEX_ID}, outcome in {list(OUTCOMES)}, fuel in {list(FUELS)}; "
                    "rows missing O2 or a diluent fraction are dropped; missing pressure is kept.",
            "exclusions": "A row whose other diluent is > 0 is excluded from this diluent's table. "
                          "Undiluted rows (CO2 = He = 0) are the 0 bin of both tables.",
            "binning": {
                "base_bins": ["0", "(0, 0.1]", "(0.1, 0.2]", "(0.2, 0.3]", "(0.3, 0.4]", ">0.4"],
                "merge": f"Within each fuel x O2 band, consecutive non-empty diluted base bins are merged "
                         f"left to right until n >= {MIN_BIN_N}; a trailing bin with n < {MIN_BIN_N} joins the "
                         "previous diluted bin; the 0 bin is never merged; empty bins are omitted.",
                "o2_bands": [b["label"] for b in O2_BANDS],
            },
            "rate": "extinction_rate = extinctions / (extinctions + completions); disruptions excluded "
                    "(same rule as M1, ADR-0004); null when the denominator is 0.",
            "interval": "Wilson score interval, 90 % two-sided (z = 1.6449), on extinctions out of "
                        "extinctions + completions.",
            "trend": f"Per diluent x fuel x O2 band, bins with extinctions + completions >= {TREND_MIN_RATED} "
                     "are rated. < 2 rated bins or no rated diluted bin: insufficient. Else delta = last "
                     f"rated rate - first rated rate: >= +{TREND_DELTA} rises, <= -{TREND_DELTA} falls, "
                     "otherwise flat. non_monotonic: some step between consecutive rated bins moves "
                     f"against the overall direction by >= {TREND_DELTA} (for flat, any step is ignored). "
                     "intervals_overlap: the first and last rated bins' 90 % Wilson intervals overlap, "
                     "i.e. the change is not distinguishable at this sample size.",
        },
        "accounting": accounting,
        "max_diluted_o2": max_dil_o2,
        "max_diluted_o2_by_diluent": max_o2_by,
        "max_o2_all_flex": max_all_o2,
        "tables": tables,
        "trend": trends,
        "notes": notes,
    }


def main() -> None:
    ref = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(ref, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    for dil in DILUENTS:
        for fuel in FUELS:
            for band in O2_BANDS:
                t = ref["trend"][dil][fuel][band["id"]]
                seq = ", ".join(f"{s['bin']}={s['extinction_rate']}(n{s['rated_n']})" for s in t["sequence"])
                print(f"  {dil:3s} {fuel:8s} {band['id']:9s} {t['direction']:12s} "
                      f"overlap={t['intervals_overlap']} nonmono={t['non_monotonic']}  {seq}")
    print("  max diluted O2:", ref["max_diluted_o2"])


if __name__ == "__main__":
    main()
