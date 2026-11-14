"""Catalog artifact: schema, consistency with clean data, lineage."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from engine.catalog import LINEAGE, build_catalog

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "catalog.json"

REQUIRED_KEYS = {
    "id", "acronym", "title", "doi", "platform", "hardware", "fuel_phase", "gravity_levels",
    "ground_reference", "conditions", "n_tests", "outcomes_available", "hazard_pillars",
    "objective", "hypothesis", "impacts", "publications", "related", "is_combustion",
    "pillar_evidence", "lineage", "reanalyzed_by",
}


@pytest.fixture(scope="module")
def catalog() -> dict:
    return build_catalog()


@pytest.fixture(scope="module")
def by_id(catalog) -> dict:
    return {r["id"]: r for r in catalog["investigations"]}


@pytest.fixture(scope="module")
def tests_df() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "clean" / "psi_tests.csv", low_memory=False)


def test_top_level(catalog):
    assert {"version", "generated_at", "investigations"} <= set(catalog)
    assert isinstance(catalog["investigations"], list) and catalog["investigations"]


def test_artifact_on_disk_matches_schema():
    assert ARTIFACT.exists(), "run `python -m engine.catalog`"
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    for r in art["investigations"]:
        assert REQUIRED_KEYS <= set(r), r["id"]


def test_record_schema(catalog):
    ids = [r["id"] for r in catalog["investigations"]]
    assert len(ids) == len(set(ids))
    for r in catalog["investigations"]:
        assert REQUIRED_KEYS <= set(r), r["id"]
        assert set(r["conditions"]) == {"o2", "pressure_atm", "flow_cm_s", "o2_burner_stream"}
        for v in r["conditions"].values():
            assert v is None or (len(v) == 2 and v[0] <= v[1])
        assert isinstance(r["n_tests"], int) and r["n_tests"] >= 0
        assert isinstance(r["outcomes_available"], bool)
        assert isinstance(r["is_combustion"], bool)
        assert set(r["hazard_pillars"]) <= {"prevention", "detection", "suppression"}
        assert set(r["pillar_evidence"]) == set(r["hazard_pillars"])
        assert r["fuel_phase"] in (None, "gas", "liquid", "solid", "aerosol")
        assert set(r["gravity_levels"]) <= {"microgravity", "normal_gravity"}
        for p in r["publications"]:
            assert set(p) == {"doi", "title"}


def test_all_clean_investigations_present(by_id, tests_df):
    days = pd.read_csv(ROOT / "data" / "clean" / "psi_test_day_summaries.csv")
    for inv in set(tests_df["investigation_id"]) | set(days["investigation_id"]):
        assert inv in by_id, inv


def test_ranges_and_counts_match_clean_data(by_id, tests_df):
    for inv, g in tests_df.groupby("investigation_id"):
        r = by_id[inv]
        assert r["n_tests"] == len(g)
        amb = g["o2_context"] == "ambient"
        burner = g["o2_context"] == "burner_oxidizer_stream"
        for key, col, rows in (("o2", "o2_mole_fraction", amb), ("pressure_atm", "pressure_atm", None),
                               ("flow_cm_s", "flow_speed_cm_s", None),
                               ("o2_burner_stream", "o2_mole_fraction", burner)):
            sub = g if rows is None else g[rows]
            s = pd.to_numeric(sub[col], errors="coerce").dropna()
            if s.empty:
                assert r["conditions"][key] is None, (inv, key)
            else:
                assert r["conditions"][key] == pytest.approx([s.min(), s.max()], abs=1e-6), (inv, key)
        assert r["outcomes_available"] == bool(g["outcome"].notna().any())
        assert r["fuel_phase"] == g["fuel_phase"].mode().iat[0]


def test_known_values(by_id):
    assert by_id["PSI-69"]["outcomes_available"] is True
    assert by_id["PSI-69"]["fuel_phase"] == "liquid"
    assert by_id["PSI-107"]["conditions"]["o2"] is None          # SPICE lacks atmosphere
    assert by_id["PSI-107"]["conditions"]["flow_cm_s"] is not None
    bre = by_id["PSI-20"]                                        # day-summary only
    assert bre["conditions"]["o2"] == [0.21, 0.4]
    assert bre["conditions"]["pressure_atm"] is None
    assert bre["n_tests"] == 194
    assert by_id["PSI-68"]["conditions"]["o2"] == [0.17, 0.3]


def test_ground_reference_only_saffire2(by_id):
    assert [i for i, r in by_id.items() if r["ground_reference"]] == ["PSI-99"]
    assert "normal_gravity" in by_id["PSI-99"]["gravity_levels"]


def test_flight_records_are_microgravity(by_id, tests_df):
    for inv in tests_df["investigation_id"].unique():
        assert "microgravity" in by_id[inv]["gravity_levels"]


def test_non_combustion_flagged(by_id):
    if "PSI-181" not in by_id:
        pytest.skip("PSI-181 metadata not fetched")
    assert by_id["PSI-181"]["is_combustion"] is False
    if "PSI-108" in by_id:
        assert by_id["PSI-108"]["is_combustion"] is False


def test_lineage_both_directions(by_id):
    checked = 0
    for child, (parents, _) in LINEAGE.items():
        if child not in by_id:
            continue
        lin = by_id[child]["lineage"]
        assert lin and lin["reuses"] == parents
        assert "normal_gravity" in by_id[child]["gravity_levels"]
        for p in parents:
            assert p in by_id[child]["related"]
            if p in by_id:
                assert child in by_id[p]["reanalyzed_by"]
                assert child in by_id[p]["related"]
                checked += 1
    assert checked >= 4  # 117/142 -> 69, 60 -> 107, 62 -> 26/25


def test_reanalyzed_by_points_back(by_id):
    for inv, r in by_id.items():
        for child in r["reanalyzed_by"]:
            assert inv in by_id[child]["lineage"]["reuses"]


def test_pillar_rule_is_transparent(by_id):
    from engine.catalog import PILLAR_PATTERNS
    import re
    for r in by_id.values():
        for pillar, words in r["pillar_evidence"].items():
            assert all(re.search(PILLAR_PATTERNS[pillar], w, re.I) for w in words)


def test_o2_excludes_burner_stream(by_id, tests_df):
    """Inverse-flame burner-stream O2 (up to 85%) is not an atmosphere."""
    for inv in ("PSI-10", "PSI-159"):
        r = by_id[inv]
        assert r["conditions"]["o2_burner_stream"] is not None
        assert r["conditions"]["o2"][1] <= 0.41
        assert r["conditions"]["o2_burner_stream"][1] >= 0.84
    assert by_id["PSI-69"]["conditions"]["o2_burner_stream"] is None


def test_fuel_phase_overrides(by_id):
    from engine.catalog import FUEL_PHASE_OVERRIDES
    expect = {"PSI-47": "aerosol", "PSI-101": "solid", "PSI-102": "solid", "PSI-115": "solid"}
    assert {k: v[0] for k, v in FUEL_PHASE_OVERRIDES.items()} == expect
    for inv, phase in expect.items():
        if inv not in by_id:
            continue
        assert by_id[inv]["fuel_phase"] == phase
        assert by_id[inv]["fuel_phase_basis"].startswith("curated:")
        assert "metadata evidence" in by_id[inv]["fuel_phase_basis"]
