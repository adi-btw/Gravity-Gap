"""S3 uncertainty drivers (ADR-0008; contract: plan/contracts.md "Round 3 · S3 Uncertainty drivers addendum")."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pytest

from engine.presets import PRESETS, PRESETS_BY_ID
from engine.uncertainty import ARTIFACT_DIR, SOURCE_ORDER, drivers, first_order_indices

N_BOOT = 60  # fewer refits keeps the suite fast; the method is the same
N_MC = 2000
BASES = {"psi_data", "engineering_assumption", "honesty_rule"}


def _hab(pid):
    p = PRESETS_BY_ID[pid]
    return {k: p[k] for k in ("g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm")}


def _drv(metric, pid, **kw):
    return drivers(metric, **_hab(pid), n=N_MC, n_boot=N_BOOT, **kw)


# ------------------------------------------------------------- estimator
def test_estimator_linear_model_known_indices():
    rng = np.random.default_rng(1)
    x = rng.uniform(0, 1, (3, 2000))
    y = 1 * x[0] + 2 * x[1] + 3 * x[2]
    s = first_order_indices({"a": x[0], "b": x[1], "c": x[2]}, y)
    truth = {"a": 1 / 14, "b": 4 / 14, "c": 9 / 14}
    for k, v in truth.items():
        assert s[k] == pytest.approx(v, abs=0.05)


def test_estimator_ishigami_known_indices():
    """Ishigami (a=7, b=0.1): S1=0.314, S2=0.442, S3=0. Needs finer bins for the oscillating x2 term."""
    rng = np.random.default_rng(2)
    x = rng.uniform(-np.pi, np.pi, (3, 20000))
    y = np.sin(x[0]) + 7 * np.sin(x[1]) ** 2 + 0.1 * x[2] ** 4 * np.sin(x[0])
    s = first_order_indices({"x1": x[0], "x2": x[1], "x3": x[2]}, y, n_bins=20)
    assert s["x1"] == pytest.approx(0.3139, abs=0.05)
    assert s["x2"] == pytest.approx(0.4424, abs=0.05)
    assert s["x3"] == pytest.approx(0.0, abs=0.05)


def test_estimator_constant_output_is_zero():
    x = np.linspace(0, 1, 100)
    assert first_order_indices({"x": x}, np.ones(100)) == {"x": 0.0}


def test_estimator_length_mismatch():
    with pytest.raises(ValueError):
        first_order_indices({"x": np.ones(3)}, np.ones(4))


# --------------------------------------------------------------- drivers
@pytest.mark.parametrize("pid", [p["id"] for p in PRESETS])
@pytest.mark.parametrize("metric", ["M1", "M2", "M3"])
def test_shares_valid(pid, metric):
    d = _drv(metric, pid)
    assert d["citation"] == f"eng:drivers:{metric}"
    if not d["applicable"]:
        assert d["reason"]
        return
    ids = [s["id"] for s in d["sources"]]
    assert ids == list(SOURCE_ORDER)
    for s in d["sources"]:
        assert s["basis"] in BASES
        if s["id"] == "remainder":
            assert s["share"] >= -0.05
        else:
            assert 0.0 <= s["share"] <= 1.0
    assert d["shares_sum"] == pytest.approx(1.0, abs=1e-6)
    k = next(s for s in d["sources"] if s["id"] == "k")
    assert k["share"] == 0.0 and k["reaches_band"] is False  # k enters u_eff only, not Ri
    assert d["lever"]["source"] != "remainder" and d["lever"]["text"]
    json.dumps(d, allow_nan=False)


def test_covered_vs_not():
    assert _drv("M1", "lunar_base")["applicable"] is True
    m2 = _drv("M2", "lunar_base")
    assert m2["applicable"] is False and "no evidence" in m2["reason"].lower()
    m4 = drivers("M4", **_hab("lunar_base"))
    assert m4["applicable"] is False


def test_orbit_band_is_all_model_uncertainty():
    d = _drv("M1", "iss")
    sh = {s["id"]: s["share"] for s in d["sources"]}
    assert sh["model_uncertainty"] == pytest.approx(1.0)
    assert sh["gravity_widening"] == 0.0
    assert d["lever"]["source"] == "model_uncertainty"


def test_lunar_base_split_and_widening():
    d = _drv("M1", "lunar_base")
    sh = {s["id"]: s["share"] for s in d["sources"]}
    assert sh["gravity_widening"] > 0  # every sample is at least mixed at 10 cm/s
    assert sh["C_b"] > 0 and sh["dT_over_T"] >= 0 and sh["L_mm"] > 0
    assert d["widen_factor"] == pytest.approx(1 + 0.5 * d["regime_fractions"]["mixed"]
                                              + d["regime_fractions"]["buoyant"])
    basis = {s["id"]: s["basis"] for s in d["sources"]}
    assert basis["model_uncertainty"] == "psi_data" and basis["gravity_widening"] == "honesty_rule"
    assert basis["C_b"] == "engineering_assumption"


def test_earth_inputs_do_not_split():
    """u = 0 with g > 0: every sample is buoyant, so no input changes the widening."""
    d = _drv("M3", "earth")
    sh = {s["id"]: s["share"] for s in d["sources"]}
    assert sh["C_b"] == sh["dT_over_T"] == sh["L_mm"] == 0.0
    assert sh["gravity_widening"] > 0


def test_deterministic_with_seed():
    a = _drv("M3", "lunar_rover", seed=3)
    b = _drv("M3", "lunar_rover", seed=3)
    assert a == b


def test_fast_after_fit():
    _drv("M1", "mars_base")  # fit + warm cache
    t0 = time.perf_counter()
    _drv("M1", "mars_base")
    assert time.perf_counter() - t0 < 1.0


def test_artifacts_if_built():
    paths = sorted(Path(ARTIFACT_DIR).glob("*.json"))
    if not paths:
        pytest.skip("run python -m engine.uncertainty")
    assert {p.stem for p in paths} >= {p["id"] for p in PRESETS}
    for p in paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        assert set(doc["metrics"]) == {"M1", "M2", "M3", "M4", "M5"}
