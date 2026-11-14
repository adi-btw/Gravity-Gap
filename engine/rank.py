"""F1 evidence ranking: which PSI investigations best inform a given habitat.

    rank(catalog, g_m_s2, p_psia, o2, u_cm_s, weights=None) -> list[dict]

Each part is in [0, 1]:
- atmosphere:   max over the record's tested (o2, pressure) corners and midpoint of
                exp(-atmosphere_distance / 2). Missing pressure with a known O2 range
                is taken as 1 atm (all PSI flight tests ran near cabin pressure unless
                stated); no O2 data at all -> 0.2.
- pillar:       weighted coverage of the 3 fire-safety pillars, weighted toward
                prevention and suppression for habitats (PILLAR_WEIGHTS sum to 1).
- fuel_realism: solid 1.0, liquid 0.6, gas 0.4 (unknown 0.0).
- outcomes:     1 if the record has test outcomes, else 0.
- n_tests:      log10(1 + n) / log10(1 + max n over the ranked records).

score = sum(w_k * part_k) / sum(w_k). With the default weights (sum 1) this is the
plain weighted sum. Ties are broken by investigation id (numeric), so the order is
deterministic. Non-combustion records (is_combustion false) are excluded.

g_m_s2 and u_cm_s are accepted for API symmetry; with no partial-gravity data in PSI
they do not change any part yet (documented open issue).
"""
from __future__ import annotations

import math
import re

from engine.physics import PSIA_PER_ATM, atmosphere_distance

DEFAULT_WEIGHTS: dict[str, float] = {
    "atmosphere": 0.35, "pillar": 0.2, "fuel_realism": 0.2, "outcomes": 0.15, "n_tests": 0.1,
}
PILLAR_WEIGHTS: dict[str, float] = {"prevention": 0.4, "suppression": 0.4, "detection": 0.2}
FUEL_REALISM: dict[str, float] = {"solid": 1.0, "liquid": 0.6, "gas": 0.4}
NO_CONDITIONS_ATMOSPHERE = 0.2
ASSUMED_PRESSURE_ATM = 1.0


def _id_key(i: str) -> tuple:
    m = re.match(r"PSI-(\d+)", str(i))
    return (int(m.group(1)) if m else 10**9, str(i))


def atmosphere_part(conditions: dict | None, o2: float, p_atm: float) -> tuple[float, str]:
    c = conditions or {}
    o2r, pr = c.get("o2"), c.get("pressure_atm")
    if not o2r:
        return NO_CONDITIONS_ATMOSPHERE, "no O2 data"
    basis = "tested O2 x pressure corners + midpoint"
    if not pr:
        pr = [ASSUMED_PRESSURE_ATM, ASSUMED_PRESSURE_ATM]
        basis = "tested O2 range, pressure assumed 1 atm"
    o2s = [o2r[0], o2r[1], (o2r[0] + o2r[1]) / 2]
    ps = [pr[0], pr[1], math.sqrt(pr[0] * pr[1])]  # geometric midpoint (distance uses ln p)
    pts = {(o2r[0], pr[0]), (o2r[0], pr[1]), (o2r[1], pr[0]), (o2r[1], pr[1]), (o2s[2], ps[2])}
    best = max(math.exp(-atmosphere_distance(o2, p_atm, xo, xp) / 2.0) for xo, xp in pts if xp > 0)
    return best, basis


def pillar_part(pillars) -> float:
    return sum(PILLAR_WEIGHTS.get(p, 0.0) for p in set(pillars or []))


def _weights(weights: dict | None) -> dict[str, float]:
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        unknown = set(weights) - set(DEFAULT_WEIGHTS)
        if unknown:
            raise ValueError(f"unknown weight keys: {sorted(unknown)}")
        w.update({k: float(v) for k, v in weights.items()})
    if any(v < 0 or math.isnan(v) for v in w.values()) or sum(w.values()) <= 0:
        raise ValueError("weights must be non-negative and sum to more than 0")
    return w


def rank(catalog: list[dict], g_m_s2: float, p_psia: float, o2: float, u_cm_s: float,
         weights: dict | None = None) -> list[dict]:
    if p_psia <= 0:
        raise ValueError("p_psia must be > 0")
    if not 0 <= o2 <= 1:
        raise ValueError("o2 must be a mole fraction in [0, 1]")
    if isinstance(catalog, dict):  # accept the whole artifact too
        catalog = catalog.get("investigations", [])
    w = _weights(weights)
    p_atm = p_psia / PSIA_PER_ATM
    recs = [r for r in catalog if r.get("is_combustion")]
    max_n = max((int(r.get("n_tests") or 0) for r in recs), default=0)
    total_w = sum(w.values())

    out = []
    for r in recs:
        atm, basis = atmosphere_part(r.get("conditions"), o2, p_atm)
        n = int(r.get("n_tests") or 0)
        parts = {
            "atmosphere": round(atm, 6),
            "pillar": round(pillar_part(r.get("hazard_pillars")), 6),
            "fuel_realism": FUEL_REALISM.get(r.get("fuel_phase") or "", 0.0),
            "outcomes": 1.0 if r.get("outcomes_available") else 0.0,
            "n_tests": round(math.log10(1 + n) / math.log10(1 + max_n), 6) if max_n > 0 else 0.0,
        }
        score = sum(w[k] * parts[k] for k in parts) / total_w
        out.append({"id": r["id"], "acronym": r.get("acronym"), "score": round(score, 6),
                    "parts": parts, "atmosphere_basis": basis})
    out.sort(key=lambda x: (-x["score"], _id_key(x["id"])))
    return out
