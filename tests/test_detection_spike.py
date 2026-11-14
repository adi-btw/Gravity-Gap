"""R3 detection spike: light tests of the prototype parsers on the real PSI files.

The raw files come from ``python scripts/fetch_detection.py``; every test skips when its file (or an
Excel reader) is missing.
"""
import math

import pytest

pytest.importorskip("openpyxl")
pytest.importorskip("xlrd")

from engine import detection as d

RAW = d.RAW_DIR
TEM_FILES = [
    "PSI-101_Analyzed_Data_54_lampwick_binneddatacorr_from_GWM.xlsx",
    "PSI-101_Analyzed_Data_60_silicone.xlsx",
    "PSI-101_Analyzed_Data_62_Kapton_unaged.xlsx",
]
PSD_FILES = [
    "PSI-115_Analyzed_Data_8cmGravityPSD.dat",
    "PSI-115_Analyzed_Data_8cmNoGravityPSD.dat",
    "PSI-115_Analyzed_Data_8cmGravityNS_PSD.dat",
    "PSI-115_Analyzed_Data_8cmNoGravityNoTF_PSD.dat",
    "PSI-115_Analyzed_Data_10cmGravityPSD.dat",
    "PSI-115_Analyzed_Data_10cmNoGravityPSD.dat",
]
SOURCE_KEYS = {"investigation_id", "file", "sheet", "rows"}


def raw(inv_id: str, name: str):
    path = RAW / inv_id / name
    if not path.exists():
        pytest.skip(f"raw file absent: {path.name} (run scripts/fetch_detection.py)")
    return path


def check_common(rec: dict) -> None:
    assert set(rec["source"]) == SOURCE_KEYS
    assert rec["units"] and rec["value_kind"]
    assert len(rec["diameter_nm"]) in (0, len(rec["value"]))
    assert all(math.isfinite(v) for v in rec["value"])
    assert all(a < b for a, b in zip(rec["diameter_nm"], rec["diameter_nm"][1:]))


def test_size_stats_recovers_a_lognormal():
    mu, sigma = math.log(200.0), math.log(1.8)
    diam = [math.exp(math.log(10.0) + 0.05 * i) for i in range(140)]
    count = [math.exp(-((math.log(x) - mu) ** 2) / (2 * sigma**2)) for x in diam]
    s = d.size_stats(diam, count)
    assert s["count_median_diameter_nm"] == pytest.approx(200.0, rel=0.01)
    assert s["geometric_mean_diameter_nm"] == pytest.approx(200.0, rel=0.01)
    assert s["geometric_std"] == pytest.approx(1.8, rel=0.01)
    assert d.size_stats([100.0], [5.0]) is None
    assert d.size_stats([100.0, 200.0], [0.0, 0.0]) is None


@pytest.mark.parametrize("name", TEM_FILES)
@pytest.mark.parametrize("big_only", [False, True])
def test_same_r_tem_bins(name, big_only):
    rec = d.parse_same_r_tem(raw("PSI-101", name), big_only=big_only)
    check_common(rec)
    assert rec["units"] == "particles" and rec["value_kind"] == "particle_count_per_bin"
    assert all(v >= 0 for v in rec["value"]) and sum(rec["value"]) > 100
    assert 1.0 < min(rec["diameter_nm"]) and max(rec["diameter_nm"]) < 5000.0
    # our statistics reproduce the Dg / sigma-g written in the workbook (cells I9 / J9)
    reported = rec["workbook_reported"]
    assert rec["stats"]["geometric_mean_diameter_nm"] == pytest.approx(reported["geometric_mean_diameter_nm"], rel=0.01)
    assert rec["stats"]["geometric_std"] == pytest.approx(reported["geometric_std"], rel=0.01)


def test_same_r_moments_rows():
    rows = d.parse_same_r_moments(raw("PSI-101", "PSI-101_Analyzed_Data_SAME,_SAME-R_Results.xlsx"))
    assert len(rows) >= 50
    assert {r["material"] for r in rows} == {"Kapton", "Lampwick", "Pyrell", "Silicone", "Teflon"}
    for r in rows:
        check_common(r)
        assert r["units"] == "particles/cm3" and r["value"][0] > 0
        assert r["geometric_std"] > 1.0
        assert 10.0 < r["diameter_nm"][0] < r["count_mean_diameter_nm"] < r["diameter_of_average_mass_nm"]


@pytest.mark.parametrize("name,units,points", [
    ("PSI-47_Raw_Data_PTrk0002.txt", "particles/cm3", 724),
    ("PSI-47_Raw_Data_DTrk0002.txt", "mg/m3", 778),
])
def test_daft_raw_log_has_no_sizes(name, units, points):
    rec = d.parse_daft_txt(raw("PSI-47", name))
    check_common(rec)
    assert rec["units"] == units and rec["diameter_nm"] == []
    assert len(rec["value"]) == len(rec["time_s"]) == points
    if units == "particles/cm3":
        assert all(v >= 0 for v in rec["value"])
    else:  # the DustTrak log holds small negative readings (-0.006 mg/m3) around zero
        assert min(rec["value"]) > -0.05


def test_daft_xls_matches_raw_log():
    xls = d.parse_daft_xls(raw("PSI-47", "PSI-47_Analyzed_Data_flight_data_063_PTrk0002.xls"), "PTrk0002")
    txt = d.parse_daft_txt(raw("PSI-47", "PSI-47_Raw_Data_PTrk0002.txt"))
    check_common(xls)
    assert xls["units"] == "particles/cm3" and xls["value"] == txt["value"]


def test_daft_summary_gives_one_derived_diameter_per_bag():
    bags = d.parse_daft_summary(raw("PSI-47", "PSI-47_Analyzed_Data_DAFT_Retrieved_Data_Summary.xls"))
    assert [b["bag"] for b in bags] == [1, 2, 3]
    for b in bags:
        check_common(b)
        assert len(b["diameter_nm"]) == 1 and b["value"][0] > 0
        assert b["assumed_density_g_per_cm3"] == 1.0
        assert b["diameter_nm"][0] == pytest.approx(b["workbook_reported_diameter_nm"], rel=1e-6)
        assert 1000.0 < b["diameter_nm"][0] < 2000.0


@pytest.mark.parametrize("name", PSD_FILES)
def test_psi115_psd_nodes(name):
    rec = d.parse_psi115_psd(raw("PSI-115", name), raw("PSI-115", "PSI-115_Analyzed_Data_nodeDiameters.dat"))
    check_common(rec)
    assert len(rec["diameter_nm"]) == 44 and rec["units"].startswith("m^-3")
    assert all(v >= 0 for v in rec["value"])
    assert rec["diameter_nm"][0] == pytest.approx(1.2404, rel=1e-3)
    ratio = rec["diameter_nm"][1] / rec["diameter_nm"][0]
    assert ratio == pytest.approx(2.25 ** (1 / 3), rel=1e-6)  # node volume grows by 2.25 (final report)
    assert rec["stats"]["geometric_std"] > 1.0
