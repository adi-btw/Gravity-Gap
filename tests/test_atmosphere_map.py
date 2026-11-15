"""S5 atmosphere evidence map (engine/atmosphere_map.py; plan/contracts.md "Round 3 · S5 Atmosphere map addendum")."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from engine import atmosphere_map as am
from engine import bounds

ROOT = Path(__file__).resolve().parents[1]
ART_DIR = ROOT / "artifacts" / "atmosphere_map"
METRICS = ("M1", "M2", "M3")


@pytest.fixture(scope="module")
def maps():
    return {(m, g): am.atmosphere_map(m, g) for m in METRICS for g in am.GRAVITIES}


def _cell(doc, o2, p_psia):
    return min(doc["cells"], key=lambda c: (c["o2"] - o2) ** 2 + (math.log(c["p_psia"] / p_psia)) ** 2)


def _texts(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _texts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _texts(v)


def test_grid_shape_and_axes(maps):
    d = maps[("M1", "lunar")]
    xs, ys = d["axes"]["x"]["values"], d["axes"]["y"]["values"]
    assert len(xs) == 26 and len(ys) == 20 and len(d["cells"]) == 520
    assert xs[0] == 0.15 and xs[-1] == 0.4 and ys[0] == 4.0 and ys[-1] == 16.0
    ratios = np.diff(np.log(ys))
    assert np.allclose(ratios, ratios[0], rtol=1e-2)  # log spaced
    assert d["axes"]["y"]["scale"] == "log"


def test_far_cell_is_null(maps):
    for m in METRICS:
        c = _cell(maps[(m, "lunar")], 0.15, 4.0)
        assert c["covered"] is False and c["estimate"] is None and c["band90"] is None
        assert c["nearest_distance"] > bounds.GATE_DISTANCE


def test_gate_rule_every_cell(maps):
    for d in maps.values():
        for c in d["cells"]:
            assert c["covered"] == (c["nearest_distance"] <= bounds.GATE_DISTANCE + 1e-3) or \
                math.isclose(c["nearest_distance"], bounds.GATE_DISTANCE, rel_tol=1e-3)
            if c["covered"]:
                lo, hi = c["band90"]
                assert lo <= c["estimate"] <= hi
            else:
                assert c["estimate"] is None and c["band90"] is None


def test_covered_share_matches_and_same_for_every_gravity(maps):
    for m in METRICS:
        shares = set()
        for g in am.GRAVITIES:
            d = maps[(m, g)]
            n = sum(c["covered"] for c in d["cells"])
            assert d["summary"]["n_covered"] == n
            assert math.isclose(d["summary"]["evidence_share"], n / 520, rel_tol=1e-3)
            assert math.isclose(d["summary"]["evidence_share"] + d["summary"]["no_evidence_share"], 1, abs_tol=1e-3)
            shares.add(n)
            assert f"{n} of 520" in d["reading"]
        assert len(shares) == 1
        est = [[c["estimate"] for c in maps[(m, g)]["cells"]] for g in am.GRAVITIES]
        assert all(e == est[0] for e in est)  # estimate does not depend on gravity


@pytest.mark.parametrize("metric", METRICS)
@pytest.mark.parametrize("gravity", ["orbit", "lunar", "earth"])
def test_cells_match_bounds_predict(maps, metric, gravity):
    d = maps[(metric, gravity)]
    g = am.GRAVITIES[gravity]["g_m_s2"]
    picks = [c for c in d["cells"] if c["covered"]][::97] + [c for c in d["cells"] if not c["covered"]][::53]
    for c in picks:
        r = bounds.predict(metric, g, c["p_psia"], c["o2"], am.U_CM_S, am.L_MM)
        assert r["applicable"] == c["covered"]
        if c["covered"]:
            assert math.isclose(r["estimate"], c["estimate"], rel_tol=1e-3, abs_tol=1e-4)
            for a, b in zip(r["band90"], c["band90"]):
                assert math.isclose(a, b, rel_tol=1e-3, abs_tol=1e-4)


def test_lunar_base_marker_matches_bounds(maps):
    for m in METRICS:
        lb = next(p for p in maps[(m, "lunar")]["overlays"]["presets"] if p["id"] == "lunar_base")
        art = json.loads((ROOT / "artifacts" / "bounds" / f"lunar_base_{m}.json").read_text(encoding="utf-8"))
        assert lb["covered"] == art["applicable"]


def test_crew_limit_lines_have_sources(maps):
    cl = maps[("M1", "lunar")]["overlays"]["crew_limits"]
    assert cl["drawn"]
    for e in cl["drawn"] + cl["not_drawn"]:
        assert e["source"]["url"].startswith("https://") and e["source"]["title"]
        assert e["citation"] == f"eng:crew_limit:{e['id']}"
        assert e["quote"]
    ids = {e["id"] for e in cl["drawn"]}
    assert {"pio2_mild_hypoxia_lower_limit", "total_pressure_min_indefinite", "o2_max_lsam_2007_baseline",
            "o2_max_orion_2007_baseline", "o2_max_iss_nominal", "o2_max_at_14p7_from_30pct_cert"} <= ids
    assert [e["id"] for e in cl["not_drawn"]] == ["o2_max_from_min_diluent"]
    byid = {e["id"]: e for e in cl["drawn"]}
    assert byid["o2_max_at_14p7_from_30pct_cert"]["shape"] == "point"
    assert byid["o2_max_at_14p7_from_30pct_cert"]["point"] == [0.256, 14.7]
    for lid in ("o2_max_lsam_2007_baseline", "o2_max_orion_2007_baseline"):
        assert "program baseline" in byid[lid]["role"]
    assert byid["total_pressure_min_indefinite"]["polyline"][0][1] == 5.0
    for e in cl["drawn"]:
        for x, y in e.get("polyline") or [pt for pl in e.get("polylines", []) for pt in pl]:
            assert am.O2_RANGE[0] - 1e-6 <= x <= am.O2_RANGE[1] + 1e-6
            assert am.P_RANGE_PSIA[0] - 1e-6 <= y <= am.P_RANGE_PSIA[1] + 1e-6


def test_pio2_curve_passes_exploration_atmosphere(maps):
    cl = {e["id"]: e for e in maps[("M3", "orbit")]["overlays"]["crew_limits"]["drawn"]}
    pts = cl["pio2_mild_hypoxia_lower_limit"]["polyline"]
    xs = [x for x, _ in pts]
    ps = [p for _, p in pts]
    assert xs == sorted(xs)
    p_at_034 = float(np.interp(0.34, xs, ps))
    assert abs(p_at_034 - 8.2) < 0.15  # PIO2 at 8.2 psia / 34% is 128 mmHg, on the 127 mmHg line by design
    assert math.isclose(max(xs), 0.40, abs_tol=1e-3) and math.isclose(max(ps), 16.0, rel_tol=1e-3)
    for x, p in pts:
        assert math.isclose(x * (p * 51.715 - 47), 127, rel_tol=2e-3)


def test_overlays_present(maps):
    ov = maps[("M2", "mars")]["overlays"]
    assert {p["id"] for p in ov["presets"]} == {"iss", "exploration", "lunar_base", "lunar_rover", "mars_base", "earth"}
    assert ov["tested"] and all("investigation_id" in t for t in ov["tested"])
    apollo = [i for i in ov["incidents"] if i["id"] == "apollo1"]
    assert apollo and apollo[0]["on_map"] is False


def test_no_safest_and_rule_stated(maps):
    for d in maps.values():
        assert "never ranks" in d["rule"]
        for s in _texts(d):
            assert "safest" not in s.lower()
    assert am.atmosphere_map("M1", "orbit")["what_varies"].startswith("The estimate depends only")


def test_rule_metrics_rejected():
    with pytest.raises(KeyError):
        am.grid("M4", 1.62)
    with pytest.raises(KeyError):
        am.atmosphere_map("M1", "venus")


@pytest.mark.parametrize("metric", METRICS)
@pytest.mark.parametrize("gravity", list(am.GRAVITIES))
def test_artifacts_match_engine(maps, metric, gravity):
    path = ART_DIR / f"{metric}_{gravity}.json"
    assert path.exists(), "run python -m engine.atmosphere_map"
    art = json.loads(path.read_text(encoding="utf-8"))
    art.pop("generated_at")
    assert art == maps[(metric, gravity)]
    assert path.stat().st_size < 150_000
