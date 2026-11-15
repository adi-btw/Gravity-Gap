"""S2 holdout honesty test (ADR-0009; contract: plan/contracts.md "Round 3 · S2 Holdout addendum").

The full run takes about 1.5 minutes (`python -m engine.holdout`), so the real-data test here uses a
small subset (2 hold-out units, 30 bootstrap refits); the committed artifact is checked for shape.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from engine import holdout
from engine.bounds import _model_eval, predict
from engine.models import M3_FEATURES, TrainingSet, fit_model, get_model, training_set


def _synthetic_m3() -> TrainingSet:
    """Four near atmospheres (20-23% O2, 1 atm) with 50% self-extinction and one far one (45% O2)."""
    rows = []
    for o2 in (0.20, 0.21, 0.22, 0.23):
        rows += [(o2, 1.0, float(i % 2)) for i in range(8)]
    rows += [(0.45, 1.0, float(i % 2)) for i in range(4)]
    o2 = np.array([r[0] for r in rows])
    p = np.array([r[1] for r in rows])
    y = np.array([r[2] for r in rows])
    X = pd.DataFrame({"o2": o2, "log_p": np.log(p), "is_ethane": 0.0, "is_propane": 1.0,
                      "fuel_fraction": 0.3})[M3_FEATURES]
    ids = np.array([f"SYN:{i}" for i in range(len(y))])
    return TrainingSet(metric="M3", X=X, y=y, record_id=ids, investigation_id=np.array(["SYN"] * len(y)),
                       o2=o2, p_atm=p)


@pytest.fixture(scope="module")
def synthetic():
    return holdout.holdout_metric("M3", train=_synthetic_m3(), n_boot=30)


def test_far_group_is_no_evidence(synthetic):
    far = next(g for g in synthetic["groups"] if g["atmosphere"]["o2"] == 0.45)
    assert far["covered"] is False
    assert far["predicted"]["shown_to_user"] is False
    assert synthetic["summary"]["n_not_covered"] == 1


def test_near_group_hits(synthetic):
    near = next(g for g in synthetic["groups"] if g["atmosphere"]["o2"] == 0.21)
    assert near["covered"] is True
    assert near["observed"]["rate"] == 0.5
    assert near["hit"] is True and near["gap"] == 0.0
    assert near["observed"]["interval90"][0] < 0.5 < near["observed"]["interval90"][1]


def test_synthetic_rows_and_ids(synthetic):
    assert len(synthetic["groups"]) == 5
    for g in synthetic["groups"]:
        assert g["psi_rows"] and len(g["psi_rows"]) == g["n_tests"]
        assert g["citation"] == f"eng:holdout:{g['id']}"


def test_summary_counts(synthetic):
    s = synthetic["summary"]
    assert s["n_covered"] + s["n_not_covered"] + s["n_skipped"] == s["n_groups"] == 5
    assert s["weak_test"] is True  # fewer than 10 covered groups
    assert s["band_coverage"]["n"] == s["n_covered"]


def test_deterministic():
    a = holdout.holdout_metric("M3", train=_synthetic_m3(), n_boot=30)
    b = holdout.holdout_metric("M3", train=_synthetic_m3(), n_boot=30)
    assert json.dumps(holdout.json_safe(a), sort_keys=True) == json.dumps(holdout.json_safe(b), sort_keys=True)


def test_one_outcome_left_is_skipped():
    ts = _synthetic_m3()
    ts.y[:] = 1.0
    ts.y[-4:] = [0.0, 1.0, 0.0, 1.0]  # only the far group has non-extinctions
    res = holdout.holdout_metric("M3", train=ts, n_boot=10)
    far = next(g for g in res["groups"] if g["atmosphere"]["o2"] == 0.45)
    assert far["status"] == "skipped" and far["skip_reason"]


def test_real_subset_shape_and_json_safe():
    res = holdout.holdout_metric("M1", n_boot=30, max_groups=2)
    assert len(res["units"]) == 2
    text = json.dumps(holdout.json_safe(res), allow_nan=False)
    assert "PSI-69:FLEX:" in text
    for g in res["groups"]:
        assert g["status"] == "evaluated"
        for r in g["psi_rows"]:
            assert r["investigation_id"] == "PSI-69" and r["source_file"] and r["source_row"] is not None


def test_wide_scheme_groups_by_o2_band():
    res = holdout.holdout_metric("M3", train=_synthetic_m3(), n_boot=30, scheme="o2_band")
    assert {u["id"] for u in res["units"]} == {"o2_0.20-0.30", "o2_0.40-0.50"}


def test_injected_model_matches_model_band_at_zero_g():
    """predict(model=...) at g = 0 returns the model's own band (widening factor 1)."""
    ts = training_set("M3")
    m = fit_model("M3", ts, n_boot=30)
    r = predict("M3", 0.0, 14.7, 0.39, 10.0, 10.0, n=200, model=m)
    e, lo, hi, _ = _model_eval(m, "M3", 0.39, 14.7 / 14.696, {"L_mm": 10.0})
    assert r["applicable"] and r["estimate"] == pytest.approx(e)
    assert r["band90"] == pytest.approx([lo, hi])


def test_injected_model_wrong_metric():
    with pytest.raises(ValueError):
        predict("M1", 0.0, 14.7, 0.21, 10.0, 10.0, n=200, model=get_model("M3", n_boot=30))


def test_fit_model_matches_cached_fit():
    a = get_model("M1", n_boot=30)
    b = fit_model("M1", training_set("M1"), n_boot=30)
    assert a.model_version == b.model_version
    assert np.allclose(a.boot_w, b.boot_w)


def test_artifact_if_built():
    path = holdout.ARTIFACT_PATH
    if not path.exists():
        pytest.skip("run python -m engine.holdout")
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["citation"] == "eng:holdout" and doc["adr"] == "ADR-0009"
    assert set(doc["metrics"]) == {"M1", "M2", "M3"} and set(doc["wide_check"]["metrics"]) == {"M1", "M2", "M3"}
    for block in (doc["metrics"], doc["wide_check"]["metrics"]):
        for res in block.values():
            s = res["summary"]
            assert s["n_covered"] + s["n_not_covered"] + s["n_skipped"] == s["n_groups"] == len(res["groups"])
            for g in res["groups"]:
                assert g["psi_rows"], g["id"]
                assert all(r["record_id"] and r["source_file"] for r in g["psi_rows"])
                assert g["status"] == "evaluated" or g["skip_reason"]
    assert doc["saffire_hindcast"]["caveat"]
