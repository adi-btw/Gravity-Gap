"""C12 test planner tests (contract: plan/contracts.md Phase 2, engine/planner.py)."""

from __future__ import annotations

import json
import math

import pytest

from engine import planner


@pytest.fixture(scope="module")
def plan():
    return planner.plan_tests(top_k=10, n=500, n_boot=60)


def test_returns_ten_sorted(plan):
    assert len(plan) == 10
    assert [p["rank"] for p in plan] == list(range(1, 11))
    scores = [p["score"] for p in plan]
    assert scores == sorted(scores, reverse=True)
    assert all(s >= 0 for s in scores)


def test_item_shape(plan):
    for p in plan:
        assert {"rank", "g_m_s2", "p_psia", "o2", "u_cm_s", "metric", "score", "parts", "rationale", "extends"} <= set(p)
        assert set(p["parts"]) >= {"band_width", "habitat_weight", "mixed_fraction"}
        assert math.isclose(p["parts"]["band_width"] * p["parts"]["habitat_weight"] * p["parts"]["mixed_fraction"],
                            p["base_score"], rel_tol=1e-9, abs_tol=1e-12)
        assert p["score"] <= p["base_score"] + 1e-12
        assert p["g_m_s2"] in planner.G_VALUES and p["u_cm_s"] in planner.U_VALUES
        assert p["extends"] and p["extends"][0] in ("PSI-69", "PSI-159")
        assert isinstance(p["rationale"], str) and len(p["rationale"]) > 40


def test_diverse(plan):
    keys = {(p["g_m_s2"], p["p_psia"], p["o2"], p["u_cm_s"], p["metric"]) for p in plan}
    assert len(keys) == 10
    assert len({(p["p_psia"], p["o2"]) for p in plan}) >= 3
    assert len({p["metric"] for p in plan}) >= 2


def test_habitat_weight_anchors():
    assert math.isclose(planner.habitat_weight(8.2, 0.34)[0], 1.0)
    assert math.isclose(planner.habitat_weight(10.2, 0.265)[0], 0.7, rel_tol=1e-6)
    assert math.isclose(planner.habitat_weight(14.7, 0.21)[0], 0.4, rel_tol=1e-6)


def test_design_implications():
    out = planner.design_implications(n=500)
    assert out and all(isinstance(s, str) for s in out)
    assert any("lunar" in s and "cm/s" in s for s in out)


def test_json_safe(plan):
    json.dumps(plan, allow_nan=False)
