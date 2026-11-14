"""V3 SAFFIRE-II hindcast: determinism, coverage, scoring, JSON-safe artifact."""
from __future__ import annotations

import json
import math

import pytest

from engine import hindcast
from engine.hindcast import CLASSES, L_CHOICES, bridge_predict, run, score


@pytest.fixture(scope="module")
def res():
    return run(seed=0)


def test_deterministic_with_seed(res):
    again = run(seed=0)
    assert json.dumps(res, sort_keys=True) == json.dumps(again, sort_keys=True)


def test_nine_samples_covered(res):
    ids = [r["sample"] for r in res["samples"]]
    assert ids == [f"2-{i}" for i in range(1, 10)]
    for r in res["samples"]:
        assert r["actual"] in CLASSES
        for c in L_CHOICES:
            for where in ("earth", "moon"):
                fr = r[where][c]["regime_fractions"]
                assert math.isclose(sum(fr.values()), 1.0, abs_tol=1e-9)
                assert r[where][c]["u_b_cm_s"]["p50"] > 0
            assert r["pred"][c]["conservative"] in CLASSES


def test_accuracy_in_unit_interval_and_baseline_present(res):
    for subset in ("scores_all", "scores_unflagged"):
        sc = res[subset]
        assert "baseline_same_as_ug" in sc
        for s in sc.values():
            assert 0.0 <= s["accuracy"] <= 1.0
            assert 0.0 <= s["binary_accuracy"] <= 1.0
            total = sum(sum(row.values()) for row in s["confusion_actual_by_predicted"].values())
            assert total == s["n"]
    assert res["scores_all"]["baseline_same_as_ug"]["n"] == 9
    # baseline hits = samples whose 1 g outcome matched ug
    same = sum(r["actual"] == "same" for r in res["samples"])
    assert res["scores_all"]["baseline_same_as_ug"]["hits"] == same
    assert res["scores_unflagged"]["baseline_same_as_ug"]["n"] == len(res["unflagged_samples"]) < 9


def test_bridge_rule():
    assert bridge_predict("forced", 0.0) == "same"
    assert bridge_predict("buoyant", 0.0) == "more_at_1g"
    assert bridge_predict("buoyant", 1.0) == "same"  # ceiling
    assert bridge_predict("mixed", 0.3) == "more_at_1g"
    assert bridge_predict("mixed", 0.3, "strict") == "same"


def test_score_counts():
    s = score(["same", "more_at_1g"], ["same", "same"])
    assert s["hits"] == 1 and s["accuracy"] == 0.5
    assert s["confusion_actual_by_predicted"]["same"]["more_at_1g"] == 1


def test_moon_buoyancy_weaker_than_earth(res):
    for r in res["samples"]:
        for c in L_CHOICES:
            assert r["moon"][c]["ri"]["p50"] < r["earth"][c]["ri"]["p50"]


def test_artifact_json_safe(res, tmp_path):
    jp, mp = tmp_path / "h.json", tmp_path / "v.md"
    hindcast.write_outputs(res, jp, mp)
    loaded = json.loads(jp.read_text(encoding="utf-8"))
    json.dumps(loaded, allow_nan=False)
    assert loaded["headline"]["n"] == 9
    md = mp.read_text(encoding="utf-8")
    assert md.index("Plain-language summary") < md.index("Scores, all 9") < md.index("Limitations")
