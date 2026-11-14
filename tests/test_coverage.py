"""Tests for engine.coverage and GET /coverage/{metric} (the Bounds Panel coverage chart)."""
import json
import math

import pytest

from engine import bounds
from engine.coverage import OUT_DIR, coverage, coverage_for

METRICS = ["M1", "M2", "M3", "M4", "M5"]
LUNAR = {"g_m_s2": 1.62, "p_psia": 8.2, "o2": 0.34, "u_cm_s": 10, "L_mm": 10}
ISS = {"g_m_s2": 0.0, "p_psia": 14.7, "o2": 0.21, "u_cm_s": 10, "L_mm": 10}


@pytest.mark.parametrize("metric", METRICS)
def test_shape_and_json_safe(metric):
    cov = coverage(metric)
    assert cov["metric"] == metric
    assert cov["points"], "every metric has tested points"
    assert cov["rule"]["type"] in {"distance", "box"}
    assert cov["n_points"] == sum(p["n"] for p in cov["points"])
    for p in cov["points"]:
        assert 0 < p["o2"] <= 1 and p["p_atm"] > 0 and p["n"] >= 1
    json.dumps(cov, allow_nan=False)


@pytest.mark.parametrize("metric", ["M1", "M2", "M3"])
def test_model_metrics_count_matches_training_rows(metric):
    cov = coverage(metric)
    assert cov["n_points"] == bounds.predict(metric, **ISS)["n_train"]


@pytest.mark.parametrize("metric", METRICS)
@pytest.mark.parametrize("hab", [LUNAR, ISS], ids=["lunar_base", "iss"])
def test_covered_agrees_with_engine_gate(metric, hab):
    """The chart must never contradict the Bounds result: covered <=> applicable."""
    status = coverage_for(metric, hab["p_psia"], hab["o2"])["habitat"]
    assert status["covered"] == bounds.predict(metric, **hab)["applicable"]


DILUENT_CASES = [
    (LUNAR, {"co2": 0.05}), (LUNAR, {"co2": 0.3}), (LUNAR, {"he": 0.2}),
    (ISS, {"co2": 0.2}), (ISS, {"co2": 0.7}), (ISS, {"he": 0.45}),
    ({**ISS, "o2": 0.265, "p_psia": 10.2}, {"co2": 0.5}),
]


@pytest.mark.parametrize("metric", ["M1", "M2"])
@pytest.mark.parametrize("hab,dil", DILUENT_CASES)
def test_covered_agrees_with_engine_gate_diluted(metric, hab, dil):
    """ADR-0006: the 4-D gate in the chart matches bounds.predict for diluted queries."""
    status = coverage_for(metric, hab["p_psia"], hab["o2"], **dil)["habitat"]
    r = bounds.predict(metric, **hab, n=300, n_boot=60, **dil)
    assert status["covered"] == r["applicable"]
    assert status["co2"] == dil.get("co2", 0.0) and status["he"] == dil.get("he", 0.0)


@pytest.mark.parametrize("metric", ["M1", "M2"])
def test_diluent_points_and_rule(metric):
    cov = coverage(metric)
    assert cov["rule"]["co2_scale"] == 0.10 and cov["rule"]["he_scale"] == 0.10
    assert all({"co2", "he"} <= set(p) for p in cov["points"])
    diluted = [p for p in cov["points"] if p["co2"] > 0 or p["he"] > 0]
    assert diluted and max(p["o2"] for p in diluted) <= 0.25
    assert "co2" not in coverage("M3")["points"][0]


def test_diluent_ignored_for_other_metrics():
    a = coverage_for("M3", 8.2, 0.34)["habitat"]
    b = coverage_for("M3", 8.2, 0.34, co2=0.3)["habitat"]
    assert a == b


def test_lunar_base_gaps_are_the_documented_ones():
    covered = {m: coverage_for(m, 8.2, 0.34)["habitat"]["covered"] for m in METRICS}
    assert covered == {"M1": True, "M2": False, "M3": True, "M4": False, "M5": False}
    d = coverage_for("M2", 8.2, 0.34)["habitat"]["nearest_distance"]
    assert 2.0 < d < 2.3


def test_assumed_atmospheres_are_flagged():
    assert all(p["assumed"] for p in coverage("M4")["points"])
    assert all(p["assumed"] for p in coverage("M5")["points"])
    assert not any(p["assumed"] for p in coverage("M1")["points"])


def test_cached_result_is_a_copy():
    a = coverage("M1")
    a["points"].clear()
    assert coverage("M1")["points"]


def test_unknown_metric():
    with pytest.raises(KeyError):
        coverage("M9")


def test_artifacts_exist_after_build():
    for m in METRICS:
        path = OUT_DIR / f"{m}.json"
        assert path.exists(), f"run python -m engine.coverage ({path})"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["metric"] == m and not math.isnan(data["n_points"])


def test_api_coverage_endpoint():
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    r = client.get("/coverage/m2", params={"p_psia": 8.2, "o2": 0.34})
    assert r.status_code == 200
    body = r.json()
    assert body["metric"] == "M2" and body["habitat"]["covered"] is False
    assert client.get("/coverage/M4").json()["rule"]["type"] == "box"
    bad = client.get("/coverage/M9")
    assert bad.status_code == 404
    assert bad.headers["content-type"].startswith("application/problem+json")
