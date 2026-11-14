"""E2 step 1: Monte Carlo over the E1 scaling-law coefficients (03 §3).

Draws (independently, uniform):
    C_b   ~ U[0.5, 1.5]
    k     ~ U[0.3, 1.0]
    dT/T  ~ U[3, 6]
    L     ~ L_mm * U[0.5, 1.5]

Formulas are the vectorized twins of engine.physics (same thresholds, same
edge cases), so a sample with fixed coefficients equals physics.evaluate.

Infinite Richardson numbers (u_f = 0 with g > 0) stay ``np.inf`` in the
``ri`` array. Quantiles use numpy's default linear interpolation over the
full sample *including* the infinities; any quantile that lands on or
interpolates into an infinite sample is reported as ``None`` (JSON null),
consistent with ADR-0003. ``ri_inf_fraction`` gives the share of infinite
samples so the UI can say "Ri = inf in X % of samples". No finite sentinel
is used, because a sentinel would leak a made-up number into the summary.
"""

from __future__ import annotations

import math

import numpy as np

from engine.physics import RI_BUOYANT_MIN, RI_FORCED_MAX, g_star, o2_partial_pressure_psia

C_B_RANGE = (0.5, 1.5)
K_RANGE = (0.3, 1.0)
DT_OVER_T_RANGE = (3.0, 6.0)
L_FACTOR_RANGE = (0.5, 1.5)
QUANTILES = {"p05": 0.05, "p50": 0.50, "p95": 0.95}


def _quantiles(values: np.ndarray) -> dict:
    """p05/p50/p95 as JSON-safe floats; non-finite results become None."""
    with np.errstate(invalid="ignore"):
        qs = np.quantile(values, list(QUANTILES.values()))
    out = {}
    for name, q in zip(QUANTILES, qs):
        q = float(q)
        out[name] = q if math.isfinite(q) else None
    return out


def sample_physics(
    g_m_s2: float,
    p_psia: float,
    o2: float,
    u_cm_s: float,
    L_mm: float,
    n: int = 2000,
    seed: int = 0,
) -> dict:
    """Sample u_b, Ri and u_eff under coefficient uncertainty.

    Returns:
        {
          "n", "seed",
          "samples": {"C_b", "k", "dT_over_T", "L_mm"}  (np.ndarray),
          "u_b", "ri", "u_eff"                          (np.ndarray, cm/s / -),
          "summary": {"u_b"|"ri"|"u_eff": {"p05","p50","p95"}}  (float | None),
          "regime_fractions": {"forced","mixed","buoyant"}       (float, sum 1),
          "ri_inf_fraction": float,
          "g_star", "p_o2_psia": float  (deterministic, no sampled inputs),
        }
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    for name, v in (("g_m_s2", g_m_s2), ("p_psia", p_psia), ("u_cm_s", u_cm_s), ("L_mm", L_mm)):
        if v < 0 or math.isnan(v):
            raise ValueError(f"{name} must be a non-negative number, got {v!r}")

    rng = np.random.default_rng(seed)
    C_b = rng.uniform(*C_B_RANGE, size=n)
    k = rng.uniform(*K_RANGE, size=n)
    dT = rng.uniform(*DT_OVER_T_RANGE, size=n)
    L = L_mm * rng.uniform(*L_FACTOR_RANGE, size=n)

    # u_b = C_b * sqrt(g * L[m] * dT/T) in cm/s
    u_b = C_b * np.sqrt(g_m_s2 * (L / 1000.0) * dT) * 100.0

    # Ri = u_b^2 / u_f^2 ; u_b == 0 -> 0 ; u_f == 0 and u_b > 0 -> inf
    if u_cm_s == 0:
        ri = np.where(u_b > 0, np.inf, 0.0)
    else:
        ri = (u_b * u_b) / (u_cm_s * u_cm_s)

    u_eff = np.sqrt(u_cm_s * u_cm_s + (k * u_b) ** 2)

    forced = float(np.mean(ri < RI_FORCED_MAX))
    buoyant = float(np.mean(ri > RI_BUOYANT_MIN))
    mixed = 1.0 - forced - buoyant

    return {
        "n": int(n),
        "seed": int(seed),
        "samples": {"C_b": C_b, "k": k, "dT_over_T": dT, "L_mm": L},
        "u_b": u_b,
        "ri": ri,
        "u_eff": u_eff,
        "summary": {
            "u_b": _quantiles(u_b),
            "ri": _quantiles(ri),
            "u_eff": _quantiles(u_eff),
        },
        "regime_fractions": {"forced": forced, "mixed": mixed, "buoyant": buoyant},
        "ri_inf_fraction": float(np.mean(np.isinf(ri))),
        "g_star": g_star(g_m_s2, p_psia),
        "p_o2_psia": o2_partial_pressure_psia(o2, p_psia),
    }
