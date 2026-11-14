"""E1 core physics: order-of-magnitude scaling laws for partial-gravity flames.

This module is the physics source of truth (ADR-0002). It uses only ``math``
so that ``web/lib/physics.ts`` can mirror it line for line; parity is checked
against ``tests/fixtures/physics_reference.json``.

Units (see plan/contracts.md):
    gravity  g_m_s2  m/s^2
    pressure p_psia  psia (atmosphere_distance takes atm)
    oxygen   o2      mole fraction (0.21 = 21 %)
    speeds   *_cm_s  cm/s
    size     L_mm    mm

Every output is an *estimate* from a scaling law (plan/03-physics-engine.md),
not a resolved flame simulation.
"""

from __future__ import annotations

import math

G0 = 9.81  # m/s^2, Earth reference gravity
P0_PSIA = 14.7  # psia, Earth sea-level cabin reference
PSIA_PER_ATM = 14.696  # psia per standard atmosphere

RI_FORCED_MAX = 0.1  # Ri below this -> forced-flow dominated
RI_BUOYANT_MIN = 10.0  # Ri above this -> buoyancy dominated

_X_SCALE = 0.05  # O2 mole-fraction scale in atmosphere_distance
_LNP_SCALE = 0.3  # ln-pressure scale in atmosphere_distance


def _require_non_negative(name: str, value: float) -> None:
    if value < 0 or math.isnan(value):
        raise ValueError(f"{name} must be a non-negative number, got {value!r}")


def buoyant_velocity_cm_s(
    g_m_s2: float, L_mm: float, dT_over_T: float = 4.0, C_b: float = 1.0
) -> float:
    """Buoyant velocity scale ``u_b = C_b * sqrt(g * L * dT/T)`` (03 §2.1).

    Args:
        g_m_s2: gravity [m/s^2]; 0 (orbit) gives 0.
        L_mm: characteristic flame/fuel size [mm]; converted to metres inside.
        dT_over_T: flame-to-ambient temperature ratio term [-], nominal 4.
        C_b: order-unity coefficient [-], bracketed over [0.5, 1.5].

    Returns:
        u_b in cm/s. Example: g=9.81, L=10 mm, dT/T=4 -> 62.64 cm/s.
    """
    _require_non_negative("g_m_s2", g_m_s2)
    _require_non_negative("L_mm", L_mm)
    _require_non_negative("dT_over_T", dT_over_T)
    _require_non_negative("C_b", C_b)
    if g_m_s2 == 0 or L_mm == 0:
        return 0.0
    L_m = L_mm / 1000.0
    return C_b * math.sqrt(g_m_s2 * L_m * dT_over_T) * 100.0


def richardson(u_b_cm_s: float, u_f_cm_s: float) -> float:
    """Richardson number ``Ri = u_b^2 / u_f^2`` (equivalently Gr/Re^2, 03 §2.2).

    Edge cases:
        u_b == 0 -> 0.0 (no buoyancy, e.g. orbit), even when u_f == 0.
        u_f == 0 and u_b > 0 -> math.inf (ventilation off under gravity).

    Both speeds in cm/s (any consistent unit works; Ri is dimensionless).
    """
    _require_non_negative("u_b_cm_s", u_b_cm_s)
    _require_non_negative("u_f_cm_s", u_f_cm_s)
    if u_b_cm_s == 0:
        return 0.0
    if u_f_cm_s == 0:
        return math.inf
    return (u_b_cm_s * u_b_cm_s) / (u_f_cm_s * u_f_cm_s)


def regime(ri: float) -> str:
    """Classify a Richardson number (03 §2.2).

    ``"forced"`` if Ri < 0.1, ``"mixed"`` if 0.1 <= Ri <= 10,
    ``"buoyant"`` if Ri > 10 (including Ri = inf). Boundaries are mixed.
    """
    if math.isnan(ri) or ri < 0:
        raise ValueError(f"ri must be a non-negative number, got {ri!r}")
    if ri < RI_FORCED_MAX:
        return "forced"
    if ri > RI_BUOYANT_MIN:
        return "buoyant"
    return "mixed"


def g_star(g_m_s2: float, p_psia: float) -> float:
    """Grashof ratio vs Earth sea level ``G* = (g/G0) * (p/P0_PSIA)^2`` (03 §2.3).

    From Gr = g*beta*dT*L^3/nu^2 with nu = mu/rho and rho proportional to P,
    so Gr is proportional to g*P^2*L^3. Dimensionless; Earth at 14.7 psia -> 1.
    Valid for laminar buoyant flow structure only (not radiation/kinetics).
    """
    _require_non_negative("g_m_s2", g_m_s2)
    _require_non_negative("p_psia", p_psia)
    return (g_m_s2 / G0) * (p_psia / P0_PSIA) ** 2


def o2_partial_pressure_psia(o2: float, p_psia: float) -> float:
    """Oxygen partial pressure ``p_O2 = X_O2 * P`` in psia (03 §2.5)."""
    _require_non_negative("o2", o2)
    _require_non_negative("p_psia", p_psia)
    if o2 > 1:
        raise ValueError(f"o2 is a mole fraction in [0, 1], got {o2!r}")
    return o2 * p_psia


def effective_flow_cm_s(u_f_cm_s: float, u_b_cm_s: float, k: float = 1.0) -> float:
    """Bridge-model effective flow ``u_eff = sqrt(u_f^2 + (k*u_b)^2)`` (03 §2.4).

    Maps a partial-gravity case onto an equivalent microgravity forced-flow
    case. k is a mixing coefficient bracketed over [0.3, 1.0]. Result in cm/s.
    g = 0 (u_b = 0) gives u_eff = u_f.
    """
    _require_non_negative("u_f_cm_s", u_f_cm_s)
    _require_non_negative("u_b_cm_s", u_b_cm_s)
    _require_non_negative("k", k)
    kb = k * u_b_cm_s
    return math.sqrt(u_f_cm_s * u_f_cm_s + kb * kb)


def atmosphere_distance(o2: float, p_atm: float, o2_t: float, p_t_atm: float) -> float:
    """Normalized atmosphere distance between a habitat and test conditions (03 §2.5).

    ``d = sqrt(((X - X_t)/0.05)^2 + ((ln P - ln P_t)/0.3)^2)``, pressures in
    atm (must be > 0), O2 as mole fractions. Dimensionless; d > 2 means the
    query is an extrapolation.
    """
    if p_atm <= 0 or p_t_atm <= 0:
        raise ValueError("pressures must be > 0 atm for atmosphere_distance")
    dx = (o2 - o2_t) / _X_SCALE
    dp = (math.log(p_atm) - math.log(p_t_atm)) / _LNP_SCALE
    return math.sqrt(dx * dx + dp * dp)


def evaluate(
    g_m_s2: float,
    p_psia: float,
    o2: float,
    u_cm_s: float,
    L_mm: float,
    dT_over_T: float = 4.0,
    C_b: float = 1.0,
    k: float = 1.0,
) -> dict:
    """Evaluate every E1 quantity for one habitat state.

    Returns a JSON-safe dict with keys
    ``u_b_cm_s, ri, regime, g_star, p_o2_psia, u_eff_cm_s``.
    An infinite Richardson number is returned as ``ri = None`` with
    ``regime = "buoyant"`` (ADR-0003); callers must not treat None as 0.
    """
    u_b = buoyant_velocity_cm_s(g_m_s2, L_mm, dT_over_T, C_b)
    ri = richardson(u_b, u_cm_s)
    return {
        "u_b_cm_s": u_b,
        "ri": None if math.isinf(ri) else ri,
        "regime": regime(ri),
        "g_star": g_star(g_m_s2, p_psia),
        "p_o2_psia": o2_partial_pressure_psia(o2, p_psia),
        "u_eff_cm_s": effective_flow_cm_s(u_cm_s, u_b, k),
    }
