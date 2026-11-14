"""C3: Monte Carlo sampler tests."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from engine import physics
from engine.montecarlo import sample_physics

LUNAR = dict(g_m_s2=1.62, p_psia=8.2, o2=0.34, u_cm_s=10.0, L_mm=10.0)


def _json_part(out):
    return {k: out[k] for k in ("summary", "regime_fractions", "ri_inf_fraction", "g_star", "p_o2_psia")}


def test_reproducible_with_seed():
    a = sample_physics(**LUNAR, seed=42)
    b = sample_physics(**LUNAR, seed=42)
    c = sample_physics(**LUNAR, seed=43)
    np.testing.assert_array_equal(a["u_b"], b["u_b"])
    np.testing.assert_array_equal(a["ri"], b["ri"])
    assert a["summary"] == b["summary"]
    assert not np.array_equal(a["u_b"], c["u_b"])


def test_shapes_and_types():
    out = sample_physics(**LUNAR, n=500)
    for key in ("u_b", "ri", "u_eff"):
        assert isinstance(out[key], np.ndarray) and out[key].shape == (500,)
    json.dumps(_json_part(out), allow_nan=False)
    for stats in out["summary"].values():
        assert all(isinstance(v, float) for v in stats.values())


@pytest.mark.parametrize(
    "params",
    [
        LUNAR,
        dict(LUNAR, u_cm_s=5.0),
        dict(g_m_s2=3.71, p_psia=8.2, o2=0.34, u_cm_s=10.0, L_mm=10.0),
        dict(g_m_s2=9.81, p_psia=14.7, o2=0.21, u_cm_s=0.0, L_mm=10.0),
        dict(g_m_s2=0.0, p_psia=14.7, o2=0.21, u_cm_s=10.0, L_mm=10.0),
    ],
)
def test_fractions_and_quantile_order(params):
    out = sample_physics(**params)
    fr = out["regime_fractions"]
    assert set(fr) == {"forced", "mixed", "buoyant"}
    assert math.isclose(sum(fr.values()), 1.0, abs_tol=1e-12)
    assert all(0.0 <= v <= 1.0 for v in fr.values())
    for stats in out["summary"].values():
        vals = [math.inf if v is None else v for v in (stats["p05"], stats["p50"], stats["p95"])]
        assert vals[0] <= vals[1] <= vals[2]


def test_orbit_is_fully_forced():
    out = sample_physics(g_m_s2=0.0, p_psia=14.7, o2=0.21, u_cm_s=10.0, L_mm=10.0)
    assert out["regime_fractions"] == {"forced": 1.0, "mixed": 0.0, "buoyant": 0.0}
    assert np.all(out["u_b"] == 0) and np.all(out["ri"] == 0)
    np.testing.assert_allclose(out["u_eff"], 10.0)


def test_vent_off_under_gravity_is_inf_and_buoyant():
    out = sample_physics(g_m_s2=9.81, p_psia=14.7, o2=0.21, u_cm_s=0.0, L_mm=10.0)
    assert out["ri_inf_fraction"] == 1.0
    assert out["regime_fractions"]["buoyant"] == 1.0
    assert out["summary"]["ri"] == {"p05": None, "p50": None, "p95": None}
    json.dumps(_json_part(out), allow_nan=False)


def test_orbit_vent_off_is_zero_not_inf():
    out = sample_physics(g_m_s2=0.0, p_psia=14.7, o2=0.21, u_cm_s=0.0, L_mm=10.0)
    assert out["ri_inf_fraction"] == 0.0
    assert out["regime_fractions"]["forced"] == 1.0


def test_samples_within_declared_ranges():
    out = sample_physics(**LUNAR)
    s = out["samples"]
    assert s["C_b"].min() >= 0.5 and s["C_b"].max() <= 1.5
    assert s["k"].min() >= 0.3 and s["k"].max() <= 1.0
    assert s["dT_over_T"].min() >= 3 and s["dT_over_T"].max() <= 6
    assert s["L_mm"].min() >= 5 and s["L_mm"].max() <= 15


def test_vectorized_matches_scalar_physics():
    out = sample_physics(**LUNAR, n=50, seed=7)
    s = out["samples"]
    for i in range(50):
        ub = physics.buoyant_velocity_cm_s(1.62, s["L_mm"][i], s["dT_over_T"][i], s["C_b"][i])
        assert math.isclose(out["u_b"][i], ub, rel_tol=1e-12)
        assert math.isclose(out["ri"][i], physics.richardson(ub, 10.0), rel_tol=1e-12)
        assert math.isclose(out["u_eff"][i], physics.effective_flow_cm_s(10.0, ub, s["k"][i]), rel_tol=1e-12)


def test_median_near_nominal():
    out = sample_physics(**LUNAR, n=20000)
    nominal = physics.buoyant_velocity_cm_s(1.62, 10, 4.5, 1.0)
    assert abs(out["summary"]["u_b"]["p50"] - nominal) / nominal < 0.1
