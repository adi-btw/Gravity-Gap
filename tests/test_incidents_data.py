"""R1 real-fire replay: schema and sourcing gates on data/incidents.json (plan/contracts.md R1 addendum)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
INCIDENTS_JSON = ROOT / "data" / "incidents.json"

EXPECTED_IDS = {"apollo1", "mir1997", "artemis2", "apollo13"}
REQUIRED_KEYS = {
    "id", "name", "date", "phase", "in_scope", "scope_note",
    "g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm", "assumed", "summary", "sources",
}
NUMERIC_FIELDS = ("g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm")
SOURCED_FIELDS = ("g_m_s2", "p_psia", "o2")  # physical values that must trace to a NASA page unless assumed
RANGES = {
    "g_m_s2": (0.0, 9.81),
    "p_psia": (0.5, 20.0),
    "o2": (0.05, 1.0),
    "u_cm_s": (0.0, 100.0),
    "L_mm": (0.1, 1000.0),
}
BRIEF_SOURCE = "2026 NASA Space Apps Challenge brief"
MAX_QUOTE_WORDS = 25


@pytest.fixture(scope="module")
def data() -> dict:
    with INCIDENTS_JSON.open(encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def incidents(data) -> list[dict]:
    return data["incidents"]


def _is_nasa_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return parsed.scheme == "https" and (host == "nasa.gov" or host.endswith(".nasa.gov"))


def _in_scope(incidents):
    return [i for i in incidents if i["in_scope"]]


def test_version(data):
    assert data["version"] == 1


def test_schema_keys(incidents):
    for inc in incidents:
        missing = REQUIRED_KEYS - inc.keys()
        assert not missing, f"{inc.get('id')}: missing {missing}"
        assert isinstance(inc["assumed"], list)
        assert isinstance(inc["sources"], list) and inc["sources"], f"{inc['id']}: no sources"


def test_ids_unique_and_exact(incidents):
    ids = [i["id"] for i in incidents]
    assert len(ids) == len(set(ids))
    assert set(ids) == EXPECTED_IDS


def test_dates_iso(incidents):
    for inc in incidents:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", inc["date"]), inc["id"]


def test_in_scope_numeric_in_range(incidents):
    for inc in _in_scope(incidents):
        for field in NUMERIC_FIELDS:
            val = inc[field]
            assert isinstance(val, (int, float)) and not isinstance(val, bool), f"{inc['id']}.{field}"
            lo, hi = RANGES[field]
            assert lo <= val <= hi, f"{inc['id']}.{field}={val} outside [{lo}, {hi}]"
        assert inc["scope_note"] is None


def test_assumed_fields_are_known(incidents):
    for inc in incidents:
        for field in inc["assumed"]:
            assert field in NUMERIC_FIELDS, f"{inc['id']}: unknown assumed field {field}"


def test_vent_and_length_are_assumptions(incidents):
    for inc in _in_scope(incidents):
        assert {"u_cm_s", "L_mm"} <= set(inc["assumed"]), inc["id"]


def test_sources_well_formed(incidents):
    for inc in incidents:
        for src in inc["sources"]:
            assert src.get("field"), inc["id"]
            quote = (src.get("quote") or "").strip()
            assert quote, f"{inc['id']}: empty quote"
            assert len(quote.split()) <= MAX_QUOTE_WORDS, f"{inc['id']}: quote too long"
            url = src.get("url") or ""
            if src.get("source") == BRIEF_SOURCE:
                assert src["field"] == "summary", "the challenge brief may only source the Artemis summary"
            else:
                assert _is_nasa_url(url), f"{inc['id']}: non-NASA URL {url}"


def test_unassumed_values_have_nasa_source(incidents):
    for inc in _in_scope(incidents):
        assumed = set(inc["assumed"])
        for field in NUMERIC_FIELDS:
            if field in assumed:
                continue
            hits = [s for s in inc["sources"] if s["field"] == field and _is_nasa_url(s.get("url", ""))
                    and s.get("quote", "").strip()]
            assert hits, f"{inc['id']}.{field} is neither assumed nor sourced"


def test_physical_values_sourced_or_assumed(incidents):
    for inc in _in_scope(incidents):
        for field in SOURCED_FIELDS:
            assert field in inc["assumed"] or any(s["field"] == field for s in inc["sources"]), (
                f"{inc['id']}.{field}")


def test_in_scope_has_summary_and_date_source(incidents):
    for inc in incidents:
        fields = {s["field"] for s in inc["sources"]}
        assert "summary" in fields, inc["id"]
        assert "date" in fields, inc["id"]


def test_assumed_pressure_or_o2_is_disclosed_in_summary(incidents):
    for inc in _in_scope(incidents):
        if {"p_psia", "o2"} & set(inc["assumed"]):
            assert "assumed" in inc["summary"].lower(), inc["id"]


def test_apollo13_out_of_scope(incidents):
    inc = next(i for i in incidents if i["id"] == "apollo13")
    assert inc["in_scope"] is False
    assert inc["scope_note"] and "not a cabin fire" in inc["scope_note"]
    for field in ("g_m_s2", "p_psia", "o2"):
        assert inc[field] is None


def test_other_three_in_scope(incidents):
    assert {i["id"] for i in _in_scope(incidents)} == {"apollo1", "mir1997", "artemis2"}


def test_apollo1_values(incidents):
    inc = next(i for i in incidents if i["id"] == "apollo1")
    assert inc["g_m_s2"] == 9.81 and inc["p_psia"] == 16.7 and inc["o2"] == 1.0


@pytest.mark.parametrize("phrase", [r"would have", r"could have prevented", r"should have"])
def test_summaries_no_hindsight(incidents, phrase):
    for inc in incidents:
        text = " ".join(filter(None, [inc["summary"], inc.get("scope_note"), inc.get("assumed_note")]))
        assert not re.search(phrase, text, re.IGNORECASE), f"{inc['id']}: hindsight phrasing"


def test_summary_length(incidents):
    for inc in incidents:
        sentences = [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])",inc["summary"].strip()) if s]
        assert 1 <= len(sentences) <= 2, inc["id"]
