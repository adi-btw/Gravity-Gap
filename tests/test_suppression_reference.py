"""Tests for the empirical FLEX suppression reference (R2, DE)."""
from __future__ import annotations

import json
import math

import pandas as pd
import pytest

from engine import suppression_reference as sr


@pytest.fixture(scope="module")
def flex() -> pd.DataFrame:
    return sr.load_flex()


@pytest.fixture(scope="module")
def ref() -> dict:
    return sr.build()


def _cells(ref):
    for dil, by_fuel in ref["tables"].items():
        for fuel, by_band in by_fuel.items():
            for band, table in by_band.items():
                for cell in table["bins"]:
                    yield dil, fuel, band, cell


def test_json_safe(ref):
    text = json.dumps(ref, allow_nan=False)
    assert json.loads(text)["source"]["investigation_id"] == "PSI-69"


def test_source_doi_from_catalog(ref):
    cat = json.loads(sr.CATALOG.read_text(encoding="utf-8"))
    doi = next(i["doi"] for i in cat["investigations"] if i["id"] == "PSI-69")
    assert ref["source"]["doi"] == doi and doi


def test_rules_present(ref):
    for key in ("rows", "exclusions", "binning", "rate", "interval", "trend"):
        assert ref["rules"][key]
    assert "disruption" in ref["rules"]["rate"].lower()


def test_counts_add_up(ref, flex):
    n_flex = len(flex)
    for dil, other in (("co2", "he"), ("he", "co2")):
        acc = ref["accounting"][dil]
        assert acc["flex_rows"] == n_flex
        dropped = (acc["dropped_outcome_not_flex_label"] + acc["dropped_fuel_not_heptane_methanol"]
                   + acc["dropped_missing_o2_or_diluent"] + acc[f"excluded_{other}_gt_0"])
        assert acc["rows_used"] + dropped == n_flex
        expected_excl = int((flex[sr.DILUENTS[other]] > 0).sum())
        assert acc[f"excluded_{other}_gt_0"] == expected_excl
        cells = [c for d, _, _, c in _cells(ref) if d == dil]
        assert sum(c["n"] for c in cells) == acc["rows_used"]
        ids = [r for c in cells for r in c["record_ids"]]
        assert len(ids) == len(set(ids)) == acc["rows_used"]
        for c in cells:
            assert c["n"] == c["extinctions"] + c["completions"] + c["disruptions"] == len(c["record_ids"])


def test_band_totals(ref):
    for dil, by_fuel in ref["tables"].items():
        for fuel, by_band in by_fuel.items():
            for band, table in by_band.items():
                assert table["n"] == sum(c["n"] for c in table["bins"])


def test_rates_and_intervals(ref):
    for _, _, _, c in _cells(ref):
        rated = c["extinctions"] + c["completions"]
        if rated == 0:
            assert c["extinction_rate"] is None and c["interval90"] is None
            continue
        r = c["extinction_rate"]
        assert 0.0 <= r <= 1.0
        assert math.isclose(r, c["extinctions"] / rated, abs_tol=1e-6)
        lo, hi = c["interval90"]
        assert 0.0 <= lo <= r + 1e-9 and r - 1e-9 <= hi <= 1.0


def test_record_ids_exist_and_match_cell(ref, flex):
    by_id = flex.set_index("record_id")
    for dil, fuel, _, c in _cells(ref):
        col = sr.DILUENTS[dil]
        rows = by_id.loc[c["record_ids"]]
        assert len(rows) == c["n"]
        assert (rows["fuel"] == fuel).all()
        assert int((rows["outcome"] == "extinction").sum()) == c["extinctions"]
        assert (rows[sr.DILUENTS[sr.OTHER[dil]]] == 0).all()
        if c["bin"] == "0":
            assert (rows[col] == 0).all()
        else:
            assert (rows[col] > c["fraction_lo"] - 1e-9).all() and (rows[col] > 0).all()
            if c["fraction_hi"] is not None:
                assert (rows[col] <= c["fraction_hi"] + 1e-9).all()


def test_bins_merged_to_min_n_where_possible(ref):
    for _, _, _, by_band in [(d, f, None, t) for d, bf in ref["tables"].items() for f, t in bf.items()]:
        for table in by_band.values():
            diluted = [c for c in table["bins"] if c["bin"] != "0"]
            if sum(c["n"] for c in diluted) >= sr.MIN_BIN_N:
                assert all(c["n"] >= sr.MIN_BIN_N for c in diluted)


def test_max_diluted_o2_matches_data(ref, flex):
    dil = flex[(flex["co2_mole_fraction"] > 0) | (flex["he_mole_fraction"] > 0)]
    expected = round(float(dil["o2_mole_fraction"].max()), 6)
    assert ref["max_diluted_o2"] == expected
    assert expected <= 0.25
    assert any("25%" in n and str(expected) in n for n in ref["notes"])


def test_trend_shape(ref):
    for dil in sr.DILUENTS:
        for fuel in sr.FUELS:
            for band in sr.O2_BANDS:
                t = ref["trend"][dil][fuel][band["id"]]
                assert t["direction"] in {"rises", "falls", "flat", "insufficient"}
                if t["direction"] != "insufficient":
                    assert len(t["sequence"]) >= 2
                    if t["direction"] == "rises":
                        assert t["delta"] >= sr.TREND_DELTA
                    elif t["direction"] == "falls":
                        assert t["delta"] <= -sr.TREND_DELTA
                    else:
                        assert abs(t["delta"]) < sr.TREND_DELTA


def test_wilson_basic():
    assert sr.wilson(0, 0) is None
    lo, hi = sr.wilson(5, 10)
    assert lo < 0.5 < hi and math.isclose(lo + hi, 1.0, abs_tol=1e-6)
    lo, hi = sr.wilson(10, 10)
    assert hi == 1.0 and 0.7 < lo < 1.0


def test_artifact_on_disk_matches_build(ref):
    if not sr.OUT.exists():
        pytest.skip("artifact not built")
    disk = json.loads(sr.OUT.read_text(encoding="utf-8"))
    disk.pop("generated_at")
    fresh = dict(ref)
    fresh.pop("generated_at")
    assert disk == json.loads(json.dumps(fresh))
