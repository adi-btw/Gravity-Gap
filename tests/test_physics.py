"""T2: physics reference cases (shared fixture) + property tests for engine.physics."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from engine import physics
from engine.presets import PRESETS

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "physics_reference.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


def _decode(v):
    return math.inf if v == "inf" else v


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_reference_case(case):
    fn = getattr(physics, case["fn"])
    args = {k: _decode(v) for k, v in case["args"].items()}
    got = fn(**args)
    expected = _decode(case["expected"])
    if isinstance(expected, str):
        assert got == expected
    elif math.isinf(expected):
        assert math.isinf(got) and got > 0
    else:
        assert math.isclose(got, expected, rel_tol=case["rel_tol"], abs_tol=1e-12), (got, expected)


def test_fixture_has_required_cases():
    ids = {c["id"] for c in CASES}
    assert {"R1", "R2", "R3", "R4_ueff", "R4_ri", "R4_regime", "R5_ri", "R5_regime"} <= ids
    fns = {c["fn"] for c in CASES}
    assert {
        "buoyant_velocity_cm_s",
        "richardson",
        "regime",
        "g_star",
        "effective_flow_cm_s",
        "o2_partial_pressure_psia",
        "atmosphere_distance",
    } <= fns


# ---------- properties ----------

GS = [0.0, 0.5, 1.62, 3.71, 9.81, 20.0]
LS = [0.5, 1, 2, 5, 10, 20, 50, 100]


def test_u_b_monotonic_in_g():
    vals = [physics.buoyant_velocity_cm_s(g, 10) for g in GS]
    assert all(a < b for a, b in zip(vals, vals[1:]))


def test_u_b_monotonic_in_L():
    vals = [physics.buoyant_velocity_cm_s(1.62, L) for L in LS]
    assert all(a < b for a, b in zip(vals, vals[1:]))


def test_u_b_sqrt_scaling():
    # quadrupling g doubles u_b
    a = physics.buoyant_velocity_cm_s(1.0, 10)
    b = physics.buoyant_velocity_cm_s(4.0, 10)
    assert math.isclose(b, 2 * a, rel_tol=1e-12)


@pytest.mark.parametrize("u_f", [0, 0.5, 5, 10, 40])
@pytest.mark.parametrize("u_b", [0, 1, 25.46, 62.64])
@pytest.mark.parametrize("k", [0.3, 0.65, 1.0])
def test_effective_flow_lower_bound(u_f, u_b, k):
    u_eff = physics.effective_flow_cm_s(u_f, u_b, k)
    assert u_eff >= max(u_f, k * u_b) - 1e-12
    assert u_eff <= u_f + k * u_b + 1e-12


def test_regime_thresholds():
    assert physics.regime(0.0) == "forced"
    assert physics.regime(math.nextafter(0.1, 0)) == "forced"
    assert physics.regime(0.1) == "mixed"
    assert physics.regime(10.0) == "mixed"
    assert physics.regime(math.nextafter(10.0, math.inf)) == "buoyant"
    assert physics.regime(math.inf) == "buoyant"
    with pytest.raises(ValueError):
        physics.regime(-1.0)
    with pytest.raises(ValueError):
        physics.regime(math.nan)


def test_richardson_edges():
    assert physics.richardson(0, 0) == 0.0
    assert physics.richardson(0, 10) == 0.0
    assert physics.richardson(5, 0) == math.inf


def test_negative_inputs_rejected():
    with pytest.raises(ValueError):
        physics.buoyant_velocity_cm_s(-1, 10)
    with pytest.raises(ValueError):
        physics.atmosphere_distance(0.21, 0, 0.21, 1)


def test_ri_independent_of_pressure_g_star_depends():
    a = physics.evaluate(1.62, 8.2, 0.34, 10, 10)
    b = physics.evaluate(1.62, 14.7, 0.34, 10, 10)
    assert a["ri"] == b["ri"]
    assert a["g_star"] < b["g_star"]


def test_evaluate_keys_and_inf_serialization():
    out = physics.evaluate(9.81, 14.7, 0.21, 0, 10)
    assert set(out) == {"u_b_cm_s", "ri", "regime", "g_star", "p_o2_psia", "u_eff_cm_s"}
    assert out["ri"] is None and out["regime"] == "buoyant"
    json.dumps(out, allow_nan=False)


def test_evaluate_orbit_is_forced():
    out = physics.evaluate(0, 14.7, 0.21, 10, 10)
    assert out["u_b_cm_s"] == 0 and out["ri"] == 0 and out["regime"] == "forced"
    assert out["u_eff_cm_s"] == 10


def test_evaluate_matches_components():
    out = physics.evaluate(1.62, 8.2, 0.34, 10, 10)
    assert math.isclose(out["u_b_cm_s"], 25.455844122715714, rel_tol=1e-12)
    assert math.isclose(out["ri"], 6.48, rel_tol=1e-6)
    assert out["regime"] == "mixed"
    assert math.isclose(out["p_o2_psia"], 2.788, rel_tol=1e-12)


# ---------- presets ----------

EXPECTED_PRESETS = {
    "iss": (0.0, 14.7, 0.21, 10),
    "exploration": (0.0, 10.2, 0.265, 10),
    "lunar_base": (1.62, 8.2, 0.34, 10),
    "lunar_rover": (1.62, 8.2, 0.34, 5),
    "mars_base": (3.71, 8.2, 0.34, 10),
    "earth": (9.81, 14.7, 0.21, 0),
}


def test_presets_match_f0():
    assert [p["id"] for p in PRESETS] == list(EXPECTED_PRESETS)
    keys = {"id", "label", "g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm", "source", "assumed"}
    for p in PRESETS:
        assert set(p) == keys
        assert (p["g_m_s2"], p["p_psia"], p["o2"], p["u_cm_s"]) == EXPECTED_PRESETS[p["id"]]
        assert p["L_mm"] == 10
        assert p["source"] and set(p["assumed"]) == {"u_cm_s", "L_mm"}
        json.dumps(physics.evaluate(p["g_m_s2"], p["p_psia"], p["o2"], p["u_cm_s"], p["L_mm"]), allow_nan=False)
