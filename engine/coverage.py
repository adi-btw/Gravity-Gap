"""Tested-atmosphere coverage per metric (what the Bounds Panel draws when there is no estimate).

For every metric this returns the O2 x pressure points that were actually tested (aggregated with
counts) plus the applicability rule the engine uses:

* M1-M2 (fitted, use diluents): covered when the ADR-0006 distance over (O2, ln p, CO2, He)
  (engine.bounds.dilution_distance) to some training test is <= 2; points carry ``co2``/``he``.
* M3 (fitted): covered when the atmosphere distance (engine.physics.atmosphere_distance) to some
  training test is <= 2.
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
from engine.bounds import DILUENT_METRICS, DILUENT_SCALE, LN_P_SCALE, O2_SCALE, dilution_distance
from engine.models import load_tests, training_set
from engine.rules import M4_O2_RANGE, M5_O2_RANGE, P_ATM_RANGE

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "coverage"
GATE_DISTANCE = 2.0
SAFFIRE_ID = "PSI-99"
SPICE_ID = "PSI-107"
ASSUMED_P_ATM = 1.0
ASSUMED_O2 = 0.21


def _aggregate(o2, p_atm, inv, assumed: str | None, co2=None, he=None) -> list[dict]:
    """Group tests by atmosphere; with co2/he (M1/M2, ADR-0006) also by diluent."""
    cols = {"o2": list(o2), "p_atm": list(p_atm), "investigation_id": list(inv)}
    dil = co2 is not None and he is not None
    if dil:
        cols.update(co2=list(co2), he=list(he))
    df = pd.DataFrame(cols)
    df = df.dropna(subset=["o2", "p_atm"])
    df["o2"] = df["o2"].astype(float).round(3)
    df["p_atm"] = df["p_atm"].astype(float).round(2)
    keys = ["o2", "p_atm", "investigation_id"]
    if dil:
        df["co2"] = df["co2"].astype(float).round(3)
        df["he"] = df["he"].astype(float).round(3)
        keys = ["o2", "p_atm", "co2", "he", "investigation_id"]
    grouped = df.groupby(keys).size().reset_index(name="n")
    out = []
    for r in grouped.itertuples(index=False):
        pt = {"o2": float(r.o2), "p_atm": float(r.p_atm)}
        if dil:
            pt.update(co2=float(r.co2), he=float(r.he))
        pt.update(investigation_id=str(r.investigation_id), n=int(r.n), assumed=assumed)
        out.append(pt)
    return out


def coverage(metric: str) -> dict:
    """Tested points + applicability rule for a metric (cached; returns a fresh copy)."""
    return copy.deepcopy(_coverage(metric.upper()))


@lru_cache(maxsize=None)
def _coverage(metric: str) -> dict:
    if metric in DILUENT_METRICS:
        ts = training_set(metric)
        points = _aggregate(ts.o2, ts.p_atm, ts.investigation_id, None,
                            co2=ts.X["co2"], he=ts.X["he"])
        rule = {"type": "distance", "max_distance": GATE_DISTANCE,
                "o2_scale": O2_SCALE, "ln_p_scale": LN_P_SCALE,
                "co2_scale": DILUENT_SCALE, "he_scale": DILUENT_SCALE,
                "text": "Covered when the habitat is within distance 2 of a tested point in O2, pressure, "
                        "CO2 and helium (about +/-0.10 O2 mole fraction, a factor of ~1.8 in pressure, "
                        "or +/-0.20 CO2 or helium mole fraction). A CO2- or helium-diluted habitat is "
                        "compared only with tests that used that diluent. Habitat air has no CO2 or "
                        "helium unless a diluent is chosen (ADR-0006)."}
        note = f"{len(ts.y)} training tests"
    elif metric == "M3":
        ts = training_set(metric)
        points = _aggregate(ts.o2, ts.p_atm, ts.investigation_id, None)
        rule = {"type": "distance", "max_distance": GATE_DISTANCE,
                "o2_scale": O2_SCALE, "ln_p_scale": LN_P_SCALE,
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


def habitat_status(cov: dict, o2: float, p_atm: float, co2: float = 0.0, he: float = 0.0) -> dict:
    """Is the habitat covered, and how far is it from the nearest tested point?

    For M1/M2 (rule has ``co2_scale``) the distance includes CO2 and He (ADR-0006), and a
    query with CO2 > 0 (He > 0) is compared only with tests that used CO2 (He); other metrics
    ignore co2/he.
    """
    rule = cov["rule"]
    dil = "co2_scale" in rule
    nearest = None
    for p in cov["points"]:
        if dil and ((co2 > 0 and p["co2"] <= 0) or (he > 0 and p["he"] <= 0)):
            continue  # ADR-0006 diluent evidence rule: only tests with that diluent count
        if dil:
            d = dilution_distance(o2, p_atm, co2, he, p["o2"], p["p_atm"], p["co2"], p["he"])
        else:
            d = physics.atmosphere_distance(o2, p_atm, p["o2"], p["p_atm"])
        if nearest is None or d < nearest[0]:
            nearest = (d, p)
    if rule["type"] == "distance":
        covered = nearest is not None and nearest[0] <= rule["max_distance"]
    else:
        covered = (rule["o2"][0] <= o2 <= rule["o2"][1]
                   and rule["pressure_atm"][0] <= p_atm <= rule["pressure_atm"][1])
    extra = {"co2": co2, "he": he} if dil else {}
    return {"o2": o2, "p_atm": p_atm, **extra, "covered": bool(covered),
            "nearest_distance": None if nearest is None else round(nearest[0], 4),
            "nearest_point": None if nearest is None else nearest[1]}


def coverage_for(metric: str, p_psia: float | None = None, o2: float | None = None,
                 co2: float | None = None, he: float | None = None) -> dict:
    cov = coverage(metric)
    if p_psia is not None and o2 is not None and p_psia > 0 and not math.isnan(o2):
        cov["habitat"] = habitat_status(cov, o2, p_psia / physics.PSIA_PER_ATM,
                                        co2=float(co2 or 0.0), he=float(he or 0.0))
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
