"""F1 evidence ranking: which PSI investigations best inform a given habitat.

    rank(catalog, g_m_s2, p_psia, o2, u_cm_s, weights=None, *, L_mm=10.0, n=2000, seed=0)
        -> list[{id, acronym, score, parts{...}, atmosphere_basis, regime_fit_basis}]

Each part is in [0, 1]:
- atmosphere:   exp(-d / 2), d = atmosphere_distance from the habitat to the NEAREST
                point of the record's tested O2 x pressure box (habitat clamped to
                [o2_min, o2_max] x [p_min, p_max]; inside the box d = 0 -> 1.0). The
                distance is separable in O2 and ln p, so clamping gives the true
                minimum. O2 uses ambient rows only (catalog ``conditions.o2``; burner-
                stream O2 of inverse flames is excluded). Missing pressure with a known
                O2 range is taken as 1 atm (PSI flight tests ran near cabin pressure
                unless stated); no O2 data at all -> 0.2.
- pillar:       weighted coverage of the 3 fire-safety pillars, weighted toward
                prevention and suppression for habitats (PILLAR_WEIGHTS sum to 1).
- fuel_realism: solid 1.0, liquid 0.6, gas 0.4, aerosol 0.0 (DAFT test dust, not a
                fuel), unknown 0.0.
- outcomes:     1 if the record has test outcomes, else 0.
- n_tests:      log10(1 + n) / log10(1 + max n over the ranked records).
- regime_fit:   uses gravity and vent speed through engine.montecarlo.sample_physics
                (one draw per rank call, L_mm default 10).
                * flow-tested records (``conditions.flow_cm_s`` known): fraction of the
                  habitat's u_eff samples inside the tested flow range widened by
                  FLOW_TOLERANCE (x1/1.5 .. x1.5; a single tested speed like SAFFIRE's
                  20 cm/s otherwise has zero width). Negative source flows clip to 0.
                * quiescent / droplet / burner records (no flow variable): the forced-
                  regime fraction of the habitat, i.e. how far microgravity evidence
                  without a flow variable transfers (03 §2.2).

score = sum(w_k * part_k) / sum(w_k). Default weights sum to 1, so it is the plain
weighted sum:  atmosphere 0.30, pillar 0.15, fuel_realism 0.15, outcomes 0.15,
n_tests 0.10, regime_fit 0.15. Ties are broken by investigation id (numeric), so the
order is deterministic. Non-combustion records (is_combustion false) are excluded.
"""
from __future__ import annotations

import math
import re

import numpy as np

from engine.montecarlo import sample_physics
from engine.physics import PSIA_PER_ATM, atmosphere_distance

DEFAULT_WEIGHTS: dict[str, float] = {
    "atmosphere": 0.30, "pillar": 0.15, "fuel_realism": 0.15, "outcomes": 0.15,
    "n_tests": 0.10, "regime_fit": 0.15,
}
PILLAR_WEIGHTS: dict[str, float] = {"prevention": 0.4, "suppression": 0.4, "detection": 0.2}
FUEL_REALISM: dict[str, float] = {"solid": 1.0, "liquid": 0.6, "gas": 0.4, "aerosol": 0.0}
NO_CONDITIONS_ATMOSPHERE = 0.2
ASSUMED_PRESSURE_ATM = 1.0
FLOW_TOLERANCE = 1.5


def _id_key(i: str) -> tuple:
    m = re.match(r"PSI-(\d+)", str(i))
    return (int(m.group(1)) if m else 10**9, str(i))


def _clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


def atmosphere_part(conditions: dict | None, o2: float, p_atm: float) -> tuple[float, str]:
    c = conditions or {}
    o2r, pr = c.get("o2"), c.get("pressure_atm")
    if not o2r:
        return NO_CONDITIONS_ATMOSPHERE, "no ambient O2 data"
    basis = "nearest point in tested ambient O2 x pressure box"
    if not pr:
        pr = [ASSUMED_PRESSURE_ATM, ASSUMED_PRESSURE_ATM]
        basis = "nearest point in tested ambient O2 range, pressure assumed 1 atm"
    o2_t = _clamp(o2, min(o2r), max(o2r))
    p_t = _clamp(p_atm, min(pr), max(pr))
    if p_t <= 0:
        return NO_CONDITIONS_ATMOSPHERE, "non-positive tested pressure"
    return math.exp(-atmosphere_distance(o2, p_atm, o2_t, p_t) / 2.0), basis


def regime_fit_part(conditions: dict | None, u_eff: np.ndarray, forced_fraction: float) -> tuple[float, str]:
    fr = (conditions or {}).get("flow_cm_s")
    if fr:
        lo, hi = max(0.0, min(fr)), max(0.0, max(fr))
        lo_t, hi_t = lo / FLOW_TOLERANCE, hi * FLOW_TOLERANCE
        frac = float(np.mean((u_eff >= lo_t) & (u_eff <= hi_t))) if u_eff.size else 0.0
        return frac, f"fraction of u_eff samples in tested flow {lo:g}-{hi:g} cm/s (x/{FLOW_TOLERANCE:g}..x{FLOW_TOLERANCE:g})"
    return forced_fraction, "no flow variable tested: habitat forced-regime fraction"


def pillar_part(pillars) -> float:
    return float(sum(PILLAR_WEIGHTS.get(p, 0.0) for p in set(pillars or [])))


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
         weights: dict | None = None, *, L_mm: float = 10.0, n: int = 2000, seed: int = 0) -> list[dict]:
    if p_psia <= 0:
        raise ValueError("p_psia must be > 0")
    if not 0 <= o2 <= 1:
        raise ValueError("o2 must be a mole fraction in [0, 1]")
    if isinstance(catalog, dict):  # accept the whole artifact too
        catalog = catalog.get("investigations", [])
    w = _weights(weights)
    p_atm = p_psia / PSIA_PER_ATM
    mc = sample_physics(g_m_s2, p_psia, o2, u_cm_s, L_mm, n=n, seed=seed)
    u_eff, forced = mc["u_eff"], mc["regime_fractions"]["forced"]
    recs = [r for r in catalog if r.get("is_combustion")]
    max_n = max((int(r.get("n_tests") or 0) for r in recs), default=0)
    total_w = sum(w.values())

    out = []
    for r in recs:
        atm, basis = atmosphere_part(r.get("conditions"), o2, p_atm)
        fit, fit_basis = regime_fit_part(r.get("conditions"), u_eff, forced)
        n_t = int(r.get("n_tests") or 0)
        parts = {
            "atmosphere": round(atm, 6),
            "pillar": round(pillar_part(r.get("hazard_pillars")), 6),
            "fuel_realism": FUEL_REALISM.get(r.get("fuel_phase") or "", 0.0),
            "outcomes": 1.0 if r.get("outcomes_available") else 0.0,
            "n_tests": round(math.log10(1 + n_t) / math.log10(1 + max_n), 6) if max_n > 0 else 0.0,
            "regime_fit": round(fit, 6),
        }
        score = sum(w[k] * parts[k] for k in parts) / total_w
        out.append({"id": r["id"], "acronym": r.get("acronym"), "score": round(score, 6),
                    "parts": parts, "atmosphere_basis": basis, "regime_fit_basis": fit_basis})
    out.sort(key=lambda x: (-x["score"], _id_key(x["id"])))
    return out
