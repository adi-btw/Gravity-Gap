"""Tested-atmosphere coverage per metric (what the Bounds Panel draws when there is no estimate).

For every metric this returns the O2 x pressure points that were actually tested (aggregated with
counts) plus the applicability rule the engine uses:

* M1-M3 (fitted models): a habitat is covered when its atmosphere distance
  (engine.physics.atmosphere_distance) to some training test is <= 2.
* M4-M5 (rule tables): a habitat is covered only inside the tested O2 / pressure box
  (engine.rules gates).

SAFFIRE-II rows have no pressure and SPICE rows have neither O2 nor pressure in the PSI tables;
the values used for them (~1 atm, ~21% O2 ISS cabin air) are the same assumptions engine.rules
makes, and every such point is flagged ``assumed``. Nothing here changes a prediction.

Run ``python -m engine.coverage`` to write artifacts/coverage/{metric}.json (offline fallback).
"""
from __future__ import annotations

import copy
import json
import math
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from engine import physics
from engine.models import load_tests, training_set
from engine.rules import M4_O2_RANGE, M5_O2_RANGE, P_ATM_RANGE

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "coverage"
GATE_DISTANCE = 2.0
SAFFIRE_ID = "PSI-99"
SPICE_ID = "PSI-107"
ASSUMED_P_ATM = 1.0
ASSUMED_O2 = 0.21


def _aggregate(o2, p_atm, inv, assumed: str | None) -> list[dict]:
    df = pd.DataFrame({"o2": list(o2), "p_atm": list(p_atm), "investigation_id": list(inv)})
    df = df.dropna(subset=["o2", "p_atm"])
    df["o2"] = df["o2"].astype(float).round(3)
    df["p_atm"] = df["p_atm"].astype(float).round(2)
    grouped = df.groupby(["o2", "p_atm", "investigation_id"]).size().reset_index(name="n")
    return [
        {"o2": float(r.o2), "p_atm": float(r.p_atm), "investigation_id": str(r.investigation_id),
         "n": int(r.n), "assumed": assumed}
        for r in grouped.itertuples(index=False)
    ]


def coverage(metric: str) -> dict:
    """Tested points + applicability rule for a metric (cached; returns a fresh copy)."""
    return copy.deepcopy(_coverage(metric.upper()))


@lru_cache(maxsize=None)
def _coverage(metric: str) -> dict:
    if metric in ("M1", "M2", "M3"):
        ts = training_set(metric)
        points = _aggregate(ts.o2, ts.p_atm, ts.investigation_id, None)
        rule = {"type": "distance", "max_distance": GATE_DISTANCE,
                "o2_scale": 0.05, "ln_p_scale": 0.3,
                "text": "Covered when the habitat is within atmosphere distance 2 of a tested point "
                        "(about +/-0.10 O2 mole fraction, or a factor of ~1.8 in pressure)."}
        note = f"{len(ts.y)} training tests"
    elif metric == "M4":
        df = load_tests()
        s = df[df["investigation_id"] == SAFFIRE_ID]
        points = _aggregate(s["o2_mole_fraction"], [ASSUMED_P_ATM] * len(s), s["investigation_id"],
                            "pressure not in the PSI table; ~1 atm assumed")
        rule = {"type": "box", "o2": list(M4_O2_RANGE), "pressure_atm": list(P_ATM_RANGE),
                "text": "Covered only inside the SAFFIRE-II tested box (O2 20-24%, 0.9-1.1 atm)."}
        note = f"{len(s)} SAFFIRE-II samples"
    elif metric == "M5":
        df = load_tests()
        s = df[(df["investigation_id"] == SPICE_ID) & (df["ignited"] == True)]  # noqa: E712
        points = _aggregate([ASSUMED_O2] * len(s), [ASSUMED_P_ATM] * len(s), s["investigation_id"],
                            "SPICE table records no atmosphere; ISS cabin air (~21% O2, ~1 atm) assumed")
        rule = {"type": "box", "o2": list(M5_O2_RANGE), "pressure_atm": list(P_ATM_RANGE),
                "text": "Covered only inside ISS-cabin-like air (O2 19-23.5%, 0.9-1.1 atm)."}
        note = f"{len(s)} SPICE flames"
    else:
        raise KeyError(f"unknown metric {metric!r}")
    return {"metric": metric, "points": points, "rule": rule, "note": note,
            "n_points": sum(p["n"] for p in points)}


def habitat_status(cov: dict, o2: float, p_atm: float) -> dict:
    """Is the habitat covered, and how far is it from the nearest tested point?"""
    nearest = None
    for p in cov["points"]:
        d = physics.atmosphere_distance(o2, p_atm, p["o2"], p["p_atm"])
        if nearest is None or d < nearest[0]:
            nearest = (d, p)
    rule = cov["rule"]
    if rule["type"] == "distance":
        covered = nearest is not None and nearest[0] <= rule["max_distance"]
    else:
        covered = (rule["o2"][0] <= o2 <= rule["o2"][1]
                   and rule["pressure_atm"][0] <= p_atm <= rule["pressure_atm"][1])
    return {"o2": o2, "p_atm": p_atm, "covered": bool(covered),
            "nearest_distance": None if nearest is None else round(nearest[0], 4),
            "nearest_point": None if nearest is None else nearest[1]}


def coverage_for(metric: str, p_psia: float | None = None, o2: float | None = None) -> dict:
    cov = coverage(metric)
    if p_psia is not None and o2 is not None and p_psia > 0 and not math.isnan(o2):
        cov["habitat"] = habitat_status(cov, o2, p_psia / physics.PSIA_PER_ATM)
    return cov


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for m in ("M1", "M2", "M3", "M4", "M5"):
        cov = coverage(m)
        cov["generated_at"] = stamp
        (OUT_DIR / f"{m}.json").write_text(json.dumps(cov, indent=1, allow_nan=False), encoding="utf-8")
        print(f"{m}: {len(cov['points'])} tested atmospheres, {cov['n_points']} tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
