"""R3 detection evidence artifact (reduced scope, ADR-0007).

Contract: plan/contracts.md "Round 2 · R3 Detection evidence addendum". Runs on the committed data
files only (data/detection/raw/, without the git-ignored reference documents).
"""
import itertools
import json
import math

import pytest

pytest.importorskip("openpyxl")
pytest.importorskip("xlrd")

from engine import detection as d

TOP_KEYS = {
    "schema_version", "generated_at", "engine_version", "generated_by", "title", "verdict", "scope_note",
    "generated_from", "gaps", "size_definitions", "smoke_bins", "smoke_runs", "average_mass_comparison",
    "simulation",
}
GAP_IDS = ["lunar_dust", "dust_sizes", "detector_sensitivity", "detector_signals", "size_definitions_disagree",
           "tem_coverage", "simulation_units", "simulation_vs_experiment", "daft_bag_mapping", "same_files"]
SOURCE_KEYS = {"investigation_id", "file", "sheet", "rows"}
BIN_KEYS = {"id", "label", "material", "material_label", "run", "variant", "variant_label", "size_definition",
            "note", "source", "diameter_nm", "count", "fraction", "dlnD", "stats", "workbook_reported"}
SIM_KEYS = {"id", "label", "case", "case_label", "gravity", "variant", "surrogate", "time_s", "is_simulation",
            "size_definition", "note", "source", "diameter_nm", "fraction", "stats"}
SIM_IDS = {"psi115_case1_earth", "psi115_case1_micro", "psi115_case1_earth_no_settling",
           "psi115_case1_micro_no_thermophoresis", "psi115_case2_earth", "psi115_case2_micro"}


@pytest.fixture(scope="module")
def art() -> dict:
    return d.build()


def all_series(a: dict) -> list[dict]:
    cmp_ = a["average_mass_comparison"]
    return [*a["smoke_bins"], a["smoke_runs"], cmp_["smoke"], cmp_["dust"], *a["simulation"]]


def test_top_level_shape(art):
    assert set(art) == TOP_KEYS
    assert art["verdict"] == "partial"
    assert art["schema_version"] == d.SCHEMA_VERSION
    assert "Reduced scope" in art["scope_note"]
    assert len(art["smoke_bins"]) == 6
    assert {s["id"] for s in art["simulation"]} == SIM_IDS
    for s in art["smoke_bins"]:
        assert set(s) == BIN_KEYS
        assert set(s["stats"]) == {"count_median_diameter_nm", "geometric_mean_diameter_nm", "geometric_std",
                                   "particle_count"}
    for s in art["simulation"]:
        assert set(s) == SIM_KEYS
        assert set(s["stats"]) == {"count_median_diameter_nm", "geometric_mean_diameter_nm", "geometric_std",
                                   "peak_diameter_nm", "share_of_count_above_20um"}
        assert s["is_simulation"] is True and s["time_s"] == 7 and s["surrogate"] == "dibutyl phthalate"
        assert s["label"].endswith("(simulation, dibutyl phthalate surrogate, t = 7 s)")


def test_every_series_has_source_and_one_size_definition(art):
    for s in all_series(art):
        assert set(s["source"]) == SOURCE_KEYS, s["id"]
        assert s["source"]["investigation_id"] in {"PSI-101", "PSI-47", "PSI-115"}
        assert s["source"]["file"] and s["source"]["rows"]
    for s in [*art["smoke_bins"], art["smoke_runs"], *art["simulation"]]:
        assert s["size_definition"] in art["size_definitions"], s["id"]
        assert s["note"]
    assert art["average_mass_comparison"]["size_definition"] == "diameter_of_average_mass"
    defs = {s["size_definition"] for s in art["smoke_bins"]} | {s["size_definition"] for s in art["simulation"]}
    assert defs == {"tem_image_diameter", "simulation_node_diameter"}
    for p in art["smoke_runs"]["points"]:
        assert isinstance(p["row"], int)


def test_generated_from_matches_manifest(art):
    manifest = json.loads(d.MANIFEST.read_text(encoding="utf-8"))["files"]
    used = {s["source"]["file"] for s in all_series(art)} | {art["average_mass_comparison"]["dust"]
                                                             ["material_source"]["file"]}
    names = {g["file"].rsplit("/", 1)[-1] for g in art["generated_from"]}
    assert used <= names
    for g in art["generated_from"]:
        assert manifest[g["file"]]["sha256"] == g["sha256"]
        assert not g["file"].endswith((".doc", ".docx", ".pdf"))  # reference documents are git-ignored


def test_diameters_increase_and_values_nonnegative(art):
    for s in [*art["smoke_bins"], *art["simulation"]]:
        dia = s["diameter_nm"]
        assert len(dia) == len(s["fraction"]) >= 2
        assert all(b > a > 0 for a, b in itertools.pairwise(dia)), s["id"]
        assert all(f >= 0 for f in s["fraction"])
    for s in art["smoke_bins"]:
        assert all(c >= 0 for c in s["count"])
    cmp_ = art["average_mass_comparison"]
    for p in [*art["smoke_runs"]["points"], *cmp_["smoke"]["points"], *cmp_["dust"]["points"]]:
        assert p["value_nm"] > 0


def test_fractions_sum_to_one(art):
    for s in [*art["smoke_bins"], *art["simulation"]]:
        assert math.isclose(sum(s["fraction"]), 1.0, rel_tol=1e-9), s["id"]
    for s in art["smoke_bins"]:
        assert math.isclose(sum(s["count"]), s["stats"]["particle_count"])


def test_dust_is_arizona_road_dust_and_nothing_is_called_lunar(art):
    dust = art["average_mass_comparison"]["dust"]
    assert "Arizona Road Dust" in dust["label"]
    assert dust["label"] == "Arizona Road Dust (DAFT)"
    assert "Arizona Road Dust" in dust["material_text"]
    assert dust["assumed_density_g_per_cm3"] == 1.0
    assert "1 g/cm3" in dust["density_note"]
    for s in all_series(art):
        for key in ("id", "label", "material", "material_label"):
            assert "lunar" not in str(s.get(key, "")).lower(), (s["id"], key)
    for p in art["smoke_runs"]["points"]:
        assert "lunar" not in p["material"].lower()
    lunar_text = [g["id"] for g in art["gaps"] if "lunar" in g["text"].lower()]
    assert lunar_text == ["lunar_dust"]


def test_gaps(art):
    assert [g["id"] for g in art["gaps"]] == GAP_IDS
    lunar = art["gaps"][0]["text"]
    assert "No lunar dust" in lunar and "open question" in lunar
    assert all(g["text"] for g in art["gaps"])


def test_smoke_runs_by_material(art):
    runs = art["smoke_runs"]
    assert runs["materials"] == ["Kapton", "Lampwick", "Pyrell", "Silicone", "Teflon"]
    assert len(runs["by_material"]) == 10
    assert sum(b["n_runs"] for b in runs["by_material"]) == len(runs["points"]) == 100
    for b in runs["by_material"]:
        assert b["dg_nm"]["min"] <= b["dg_nm"]["median"] <= b["dg_nm"]["max"]
        pts = [p["value_nm"] for p in runs["points"] if p["material"] == b["material"] and p["aged"] == b["aged"]]
        assert len(pts) == b["n_runs"] and min(pts) == b["dg_nm"]["min"]
    aged = {p["run"]: p["aged"] for p in runs["points"]}
    assert all(v == k.endswith("a") for k, v in aged.items())


def test_average_mass_comparison_uses_same_rows(art):
    cmp_ = art["average_mass_comparison"]
    assert [p["row"] for p in cmp_["smoke"]["points"]] == [p["row"] for p in art["smoke_runs"]["points"]]
    assert len(cmp_["dust"]["points"]) == 3
    for p in cmp_["dust"]["points"]:
        assert math.isclose(p["value_nm"], p["workbook_reported_nm"], rel_tol=0.01)
    for side in ("smoke", "dust"):
        vals = [p["value_nm"] for p in cmp_[side]["points"]]
        assert cmp_[side]["range_nm"] == {"min": min(vals), "max": max(vals)}


def test_tem_stats_match_workbook_cells(art):
    """Our geometric mean and sigma-g agree with the workbook's own I9 / J9 within 1%."""
    for s in art["smoke_bins"]:
        rep = s["workbook_reported"]
        assert rep["cells"] == "I9, J9"
        assert math.isclose(s["stats"]["geometric_mean_diameter_nm"], rep["geometric_mean_diameter_nm"],
                            rel_tol=0.01), s["id"]
        assert math.isclose(s["stats"]["geometric_std"], rep["geometric_std"], rel_tol=0.01), s["id"]
    # and the cells really are what the workbook holds (read directly, not via the artifact)
    import openpyxl
    for material, run, name in d.TEM_RUNS:
        s = next(x for x in art["smoke_bins"] if x["material"] == material and x["variant"] == "all")
        wb = openpyxl.load_workbook(d.RAW_DIR / "PSI-101" / name, read_only=True, data_only=True)
        try:
            ws = wb[s["source"]["sheet"]]
            i9, j9 = ws["I9"].value, ws["J9"].value
        finally:
            wb.close()
        assert math.isclose(s["stats"]["geometric_mean_diameter_nm"], i9 * 1000, rel_tol=0.01)
        assert math.isclose(s["stats"]["geometric_std"], j9, rel_tol=0.01)


def test_simulation_microgravity_keeps_more_large_particles(art):
    by_id = {s["id"]: s for s in art["simulation"]}
    for case in ("1", "2"):
        earth = by_id[f"psi115_case{case}_earth"]["stats"]["share_of_count_above_20um"]
        micro = by_id[f"psi115_case{case}_micro"]["stats"]["share_of_count_above_20um"]
        assert 0 <= earth < micro <= 1


def test_json_safe_and_artifact_on_disk(art):
    text = json.dumps(art, allow_nan=False, ensure_ascii=False)
    assert json.loads(text)["title"] == "Detection evidence"
    if d.OUT.exists():
        disk = json.loads(d.OUT.read_text(encoding="utf-8"))
        assert set(disk) == TOP_KEYS
        assert [g["id"] for g in disk["gaps"]] == GAP_IDS
        assert disk["smoke_bins"] == art["smoke_bins"] and disk["simulation"] == art["simulation"]
