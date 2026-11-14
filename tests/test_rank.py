"""F1 ranking: ordering, exclusion, habitat sensitivity, weights, determinism."""
from __future__ import annotations

import copy
import random

import pytest

from engine.catalog import build_catalog
from engine.rank import DEFAULT_WEIGHTS, atmosphere_part, rank

ISS = dict(g_m_s2=0.0, p_psia=14.7, o2=0.21, u_cm_s=10.0)
LUNAR = dict(g_m_s2=1.62, p_psia=8.2, o2=0.34, u_cm_s=10.0)


@pytest.fixture(scope="module")
def records() -> list[dict]:
    return build_catalog()["investigations"]


def test_shape_and_sorted(records):
    out = rank(records, **LUNAR)
    assert out
    scores = [x["score"] for x in out]
    assert scores == sorted(scores, reverse=True)
    for x in out:
        assert {"id", "acronym", "score", "parts"} <= set(x)
        assert set(x["parts"]) == set(DEFAULT_WEIGHTS)
        assert all(0.0 <= v <= 1.0 for v in x["parts"].values())
        assert 0.0 <= x["score"] <= 1.0


def test_excludes_non_combustion(records):
    ids = {x["id"] for x in rank(records, **ISS)}
    for r in records:
        if not r["is_combustion"]:
            assert r["id"] not in ids
    assert len(ids) == sum(r["is_combustion"] for r in records)


def test_excludes_synthetic_non_combustion(records):
    fake = copy.deepcopy(records[0])
    fake.update(id="PSI-9999", is_combustion=False, n_tests=10**6)
    assert "PSI-9999" not in {x["id"] for x in rank(records + [fake], **ISS)}


def test_lunar_ranks_differently_from_iss(records):
    iss = rank(records, **ISS)
    lunar = rank(records, **LUNAR)
    assert [x["id"] for x in iss] != [x["id"] for x in lunar] or \
        [x["score"] for x in iss] != [x["score"] for x in lunar]
    a_iss = {x["id"]: x["parts"]["atmosphere"] for x in iss}
    a_lun = {x["id"]: x["parts"]["atmosphere"] for x in lunar}
    assert a_iss != a_lun


def test_weights_change_ordering(records):
    base = [x["id"] for x in rank(records, **LUNAR)]
    only_n = [x["id"] for x in rank(records, **LUNAR, weights={k: 0.0 for k in DEFAULT_WEIGHTS} | {"n_tests": 1.0})]
    only_fuel = [x["id"] for x in rank(records, **LUNAR, weights={k: 0.0 for k in DEFAULT_WEIGHTS} | {"fuel_realism": 1.0})]
    assert base != only_n or base != only_fuel
    assert only_n[0] == max((r for r in records if r["is_combustion"]), key=lambda r: r["n_tests"])["id"]


def test_score_is_weighted_sum(records):
    for x in rank(records, **LUNAR):
        expect = sum(DEFAULT_WEIGHTS[k] * v for k, v in x["parts"].items())
        assert x["score"] == pytest.approx(expect, abs=1e-5)


def test_bad_weights_rejected(records):
    with pytest.raises(ValueError):
        rank(records, **ISS, weights={"bogus": 1.0})
    with pytest.raises(ValueError):
        rank(records, **ISS, weights={k: 0.0 for k in DEFAULT_WEIGHTS})


def test_deterministic_and_order_independent(records):
    a = rank(records, **LUNAR)
    shuffled = records[:]
    random.Random(7).shuffle(shuffled)
    b = rank(shuffled, **LUNAR)
    assert a == b == rank(records, **LUNAR)


def test_tie_break_by_id():
    rec = {"is_combustion": True, "acronym": "X", "conditions": None, "hazard_pillars": [],
           "fuel_phase": "gas", "outcomes_available": False, "n_tests": 1}
    recs = [dict(rec, id="PSI-20"), dict(rec, id="PSI-3"), dict(rec, id="PSI-100")]
    assert [x["id"] for x in rank(recs, **ISS)] == ["PSI-3", "PSI-20", "PSI-100"]


def test_atmosphere_part_rules():
    assert atmosphere_part(None, 0.21, 1.0)[0] == 0.2
    assert atmosphere_part({"o2": None, "pressure_atm": None}, 0.21, 1.0)[0] == 0.2
    exact = atmosphere_part({"o2": [0.21, 0.21], "pressure_atm": [1.0, 1.0]}, 0.21, 1.0)[0]
    assert exact == pytest.approx(1.0)
    far = atmosphere_part({"o2": [0.85, 0.85], "pressure_atm": [3.0, 3.0]}, 0.21, 1.0)[0]
    assert far < 0.01
