"""M4 / M5 rule-table metrics: contract shape, gates, regime transfer, flags, data windows."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from engine import rules
from engine.presets import get_preset
from engine.rules import CATEGORIES, m5_window, predict_m4, predict_m5

ROOT = Path(__file__).resolve().parents[1]
KEYS = {"metric", "label", "unit", "kind", "applicable", "reason", "estimate", "band90", "ref_0g",
        "ref_1g", "regime_fractions", "u_eff_summary", "nonmonotonic_flag", "nonmonotonic_note",
        "transfer", "evidence", "sensitivity", "n_train", "model_version"}
VALID_M4 = set(CATEGORIES) | {"between", None}
ISS22 = (0.0, 14.7, 0.22, 20.0, 10.0)
LUNAR = (1.62, 8.2, 0.34, 10.0, 10.0)
EARTH = (9.81, 14.7, 0.21, 0.0, 10.0)


def _habitat(pid):
    p = get_preset(pid)
    return (p["g_m_s2"], p["p_psia"], p["o2"], p["u_cm_s"], p["L_mm"])


def _check_shape(r, metric):
    assert set(r) == KEYS
    assert r["metric"] == metric
    assert set(r["regime_fractions"]) == {"forced", "mixed", "buoyant"}
    assert sum(r["regime_fractions"].values()) == pytest.approx(1.0)
    assert set(r["u_eff_summary"]) == {"p05", "p50", "p95"}
    assert set(r["transfer"]) == {"basis", "confidence"}
    assert r["transfer"]["confidence"] in ("high", "medium", "low")
    assert set(r["ref_0g"]) == {"estimate", "band90"}
    assert r["ref_1g"] is None or set(r["ref_1g"]) == {"estimate", "band90"}
    assert len(r["evidence"]) <= 20
    for e in r["evidence"]:
        assert set(e) == {"record_id", "investigation_id", "distance"}
    for s in r["sensitivity"]:
        assert set(s) == {"param", "low", "high"}
    assert isinstance(r["n_train"], int) and r["n_train"] > 0
    assert isinstance(r["model_version"], str)
    json.dumps(r, allow_nan=False)  # JSON safe
    if not r["applicable"]:
        assert r["estimate"] is None and r["band90"] is None and r["reason"]


@pytest.mark.parametrize("pid", ["iss", "exploration", "lunar_base", "lunar_rover", "mars_base", "earth"])
@pytest.mark.parametrize("material", [None, "silicone", "sibal", "pmma", "pmma_nomex"])
def test_m4_shape_and_categories(pid, material):
    r = predict_m4(*_habitat(pid), material=material)
    _check_shape(r, "M4")
    assert r["kind"] == "category"
    assert r["estimate"] in VALID_M4
    if r["band90"] is not None:
        assert all(c in CATEGORIES for c in r["band90"])
        assert rules.SEVERITY[r["band90"][0]] <= rules.SEVERITY[r["band90"][1]]
    for ref in (r["ref_0g"], r["ref_1g"] or {}):
        assert ref.get("estimate") in VALID_M4


@pytest.mark.parametrize("pid", ["iss", "exploration", "lunar_base", "lunar_rover", "mars_base", "earth"])
@pytest.mark.parametrize("fuel", [None, "propylene", "ethylene"])
def test_m5_shape(pid, fuel):
    r = predict_m5(*_habitat(pid), fuel=fuel)
    _check_shape(r, "M5")
    assert r["kind"] == "probability"
    if r["applicable"]:
        assert 0.0 <= r["estimate"] <= 1.0
        lo, hi = r["band90"]
        assert 0.0 <= lo <= hi <= 1.0


def test_m4_gate_rejects_lunar_atmosphere():
    r = predict_m4(*LUNAR, material="silicone")
    assert r["applicable"] is False and r["estimate"] is None
    assert "22% O2" in r["reason"] and "1 atm" in r["reason"]
    assert "34.0%" in r["reason"] and "8.2 psia" in r["reason"]
    assert "extrapolation" in r["reason"]


def test_m4_gate_rejects_low_pressure_only():
    r = predict_m4(0.0, 10.2, 0.22, 20.0, 10.0)
    assert r["applicable"] is False and "pressure" in r["reason"] and "habitat O2" not in r["reason"]


def test_m4_iss_like_gives_microgravity_outcome_for_silicone():
    r = predict_m4(*ISS22, material="silicone")
    assert r["applicable"] is True
    assert r["regime_fractions"]["forced"] == 1.0
    assert r["estimate"] == "no_sustained_burn" == r["ref_0g"]["estimate"]
    assert r["ref_1g"]["estimate"] == "complete_burn"
    assert r["transfer"]["confidence"] == "medium"
    assert all(e["investigation_id"] == "PSI-99" for e in r["evidence"])
    assert r["n_train"] == 4


def test_m4_earth_buoyant_gives_1g_outcome():
    r = predict_m4(*EARTH, material="silicone")
    assert r["regime_fractions"]["buoyant"] >= 0.9
    assert r["estimate"] == r["ref_1g"]["estimate"] == "complete_burn"
    r2 = predict_m4(*EARTH, material="sibal")
    assert r2["estimate"] == "complete_burn"


def test_m4_mixed_regime_is_between_with_low_confidence():
    # 22% O2 / 1 atm at lunar gravity and 10 cm/s vent: mostly mixed regime
    r = predict_m4(1.62, 14.7, 0.22, 10.0, 10.0, material="silicone")
    assert r["regime_fractions"]["mixed"] > 0.5
    assert r["estimate"] == "between"
    assert r["band90"] == ["no_sustained_burn", "complete_burn"]
    assert r["transfer"]["confidence"] == "low"
    # SIBAL burns completely in both: mixed regime still has a definite answer
    assert predict_m4(1.62, 14.7, 0.22, 10.0, 10.0, material="sibal")["estimate"] == "complete_burn"


def test_m4_footnoted_material_low_confidence():
    r = predict_m4(*ISS22, material="pmma")
    assert r["estimate"] == "partial_burn" and r["transfer"]["confidence"] == "low"


def test_m4_any_material_is_most_severe():
    assert predict_m4(*ISS22)["estimate"] == "complete_burn"   # SIBAL burns fully in microgravity


def test_m4_nonmonotonic_flag_low_flow():
    low = predict_m4(0.0, 14.7, 0.22, 5.0, 10.0, material="silicone")
    assert low["nonmonotonic_flag"] is True
    assert "Goldilocks" in low["nonmonotonic_note"] and "PSI-62" in low["nonmonotonic_note"]
    hyp = rules._psi62_hypothesis()
    assert hyp and hyp in low["nonmonotonic_note"]
    high = predict_m4(*ISS22, material="silicone")
    assert high["nonmonotonic_flag"] is False and high["nonmonotonic_note"] is None
    # lunar rover (5 cm/s): flag is physics-based, raised even though the gate fails
    rover = predict_m4(*_habitat("lunar_rover"))
    assert rover["applicable"] is False and rover["nonmonotonic_flag"] is True


def test_m4_unknown_material():
    with pytest.raises(ValueError):
        predict_m4(*ISS22, material="kevlar")


def test_m4_table_matches_saffire_csv():
    sf = pd.read_csv(ROOT / "data" / "clean" / "psi_saffire_ug_vs_1g.csv")
    mats = rules.m4_table()["materials"]
    assert sum(m["n"] for k, m in mats.items() if k != "any") == len(sf) == 9
    assert mats["silicone"]["ug_outcome"] == "no_sustained_burn"
    assert mats["sibal"]["ug_outcome"] == mats["sibal"]["1g_outcome"] == "complete_burn"
    assert mats["pmma"]["confidence"] == mats["pmma_nomex"]["confidence"] == "low"
    assert mats["silicone"]["confidence"] == "medium"


def test_m5_window_from_data():
    t = pd.read_csv(ROOT / "data" / "clean" / "psi_tests.csv", low_memory=False)
    s = t[(t["investigation_id"] == "PSI-107") & (t["fuel"] == "Propylene")]
    s = s[s["ignited"].astype(str) == "True"]
    s = s[~s["quality_flags"].fillna("").str.contains("loss_of_signal|negative_air_rate")]
    s = s[pd.to_numeric(s["flow_speed_cm_s"], errors="coerce") > 0]
    for noz, g in s.groupby(s["size_mm"].round(4)):
        w = m5_window("propylene", noz)
        assert w["min_cm_s"] == pytest.approx(g["flow_speed_cm_s"].min())
        assert w["max_cm_s"] == pytest.approx(g["flow_speed_cm_s"].max())
        assert w["n"] == len(g)
    pooled = m5_window()
    assert pooled["min_cm_s"] > 0                       # the -0.28 cm/s row is excluded
    assert rules.m5_table()["excluded_rows"]["loss_of_signal"] == 3


def test_m5_estimate_is_fraction_inside_window():
    w = m5_window("propylene", 0.4064)
    inside = predict_m5(0.0, 14.7, 0.21, 20.0, 10.0, fuel="propylene", nozzle_mm=0.4064)
    assert inside["estimate"] == 1.0 and inside["transfer"]["confidence"] == "medium"
    assert f"{w['min_cm_s']:g}-{w['max_cm_s']:g} cm/s" in inside["transfer"]["basis"]
    assert "atmosphere is unknown" in inside["transfer"]["basis"]
    below = predict_m5(0.0, 14.7, 0.21, 2.0, 10.0, fuel="propylene", nozzle_mm=0.4064)
    assert below["estimate"] == 0.0
    assert inside["ref_0g"]["estimate"] == 1.0


def test_m5_confidence_never_high_and_gate():
    for pid in ("iss", "earth"):
        r = predict_m5(*_habitat(pid))
        assert r["applicable"] and r["transfer"]["confidence"] in ("medium", "low")
    r = predict_m5(*LUNAR)
    assert r["applicable"] is False and "SPICE" in r["reason"]


def test_m5_unknown_fuel_or_nozzle():
    with pytest.raises(ValueError):
        predict_m5(*ISS22, fuel="hydrogen")
    with pytest.raises(ValueError):
        predict_m5(*ISS22, fuel="propylene", nozzle_mm=3.0)


def test_deterministic():
    assert predict_m4(*EARTH, seed=3) == predict_m4(*EARTH, seed=3)
    assert predict_m5(*EARTH, seed=3) == predict_m5(*EARTH, seed=3)


def test_rules_artifact():
    path = ROOT / "artifacts" / "rules.json"
    assert path.exists(), "run `python -m engine.rules`"
    art = json.loads(path.read_text(encoding="utf-8"))
    assert {"version", "m4", "m5"} <= set(art)
    assert {"silicone", "sibal", "pmma", "pmma_nomex", "any"} == set(art["m4"]["materials"])
    assert art["m5"]["windows"] and all(w["min_cm_s"] > 0 and w["min_cm_s"] <= w["max_cm_s"]
                                        for w in art["m5"]["windows"])
    assert not any(isinstance(v, float) and math.isnan(v) for v in art["m5"]["excluded_rows"].values())
