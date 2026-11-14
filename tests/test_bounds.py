"""C5-C11 bounds model tests (contract: plan/contracts.md Phase 2, engine/bounds.py)."""

from __future__ import annotations

import json
import math

import pytest

from engine import bounds
from engine.bounds import METRICS, predict, widen_band
from engine.presets import PRESETS_BY_ID

N_BOOT = 60  # fewer refits keeps the suite fast; shape and logic are the same
N_MC = 500
CONTRACT_KEYS = {
    "metric", "label", "unit", "kind", "applicable", "reason", "estimate", "band90", "ref_0g", "ref_1g",
    "regime_fractions", "u_eff_summary", "nonmonotonic_flag", "nonmonotonic_note", "transfer",
    "evidence", "sensitivity", "n_train", "model_version",
}


def _hab(pid):
    p = PRESETS_BY_ID[pid]
    return {k: p[k] for k in ("g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm")}


def _pred(metric, pid="iss", **kw):
    return predict(metric, **{**_hab(pid), **kw.pop("hab", {})}, n=N_MC, n_boot=N_BOOT, **kw)


def test_metrics_registry():
    assert set(METRICS) == {"M1", "M2", "M3", "M4", "M5"}
    for m, meta in METRICS.items():
        assert {"label", "unit", "kind", "data", "flow_dependent"} <= set(meta)
        assert meta["kind"] in ("probability", "quantity", "category")
    assert not any(METRICS[m]["flow_dependent"] for m in ("M1", "M2", "M3"))
    assert all(METRICS[m]["flow_dependent"] for m in ("M4", "M5"))


@pytest.mark.parametrize("metric", ["M1", "M2", "M3"])
@pytest.mark.parametrize("pid", ["iss", "exploration", "lunar_base", "earth"])
def test_shape_and_band(metric, pid):
    r = _pred(metric, pid)
    assert CONTRACT_KEYS <= set(r)
    assert r["metric"] == metric and r["kind"] == METRICS[metric]["kind"]
    assert r["ref_1g"] is None and r["nonmonotonic_flag"] is False
    assert r["transfer"]["confidence"] in ("high", "medium", "low")
    assert set(r["regime_fractions"]) == {"forced", "mixed", "buoyant"}
    assert math.isclose(sum(r["regime_fractions"].values()), 1.0, abs_tol=1e-9)
    assert 1 <= len(r["evidence"]) <= 20
    ds = [e["distance"] for e in r["evidence"]]
    assert ds == sorted(ds)
    assert r["n_train"] > 50 and isinstance(r["model_version"], str)
    if not r["applicable"]:
        assert r["estimate"] is None and r["band90"] is None and r["reason"]
        return
    lo, hi = r["band90"]
    assert lo <= r["estimate"] <= hi
    if r["kind"] == "probability":
        assert 0.0 <= lo <= hi <= 1.0
    else:
        assert lo >= 0
    # 0 g reference band is never wider than the gravity-widened band
    rlo, rhi = r["ref_0g"]["band90"]
    assert r["ref_0g"]["estimate"] == r["estimate"]
    assert rlo >= lo - 1e-12 and rhi <= hi + 1e-12
    params = {s["param"] for s in r["sensitivity"]}
    assert {"o2", "pressure", "C_b", "k", "dT_over_T", "L_factor"} <= params
    for s in r["sensitivity"]:
        assert {"param", "low", "high"} <= set(s)


def test_gravity_does_not_change_estimate():
    """Honesty rule: same atmosphere at 0 g and lunar g -> same estimate, wider band."""
    a = _pred("M1", "lunar_base", hab={"g_m_s2": 0.0})
    b = _pred("M1", "lunar_base")
    assert a["estimate"] == b["estimate"]
    assert (b["band90"][1] - b["band90"][0]) > (a["band90"][1] - a["band90"][0])


def test_transfer_confidence_orbit_high_lunar_lower():
    assert _pred("M1", "iss")["transfer"]["confidence"] == "high"
    lunar = _pred("M1", "lunar_base")
    assert lunar["transfer"]["confidence"] in ("medium", "low")
    assert "widened" in lunar["transfer"]["basis"]


@pytest.mark.parametrize("metric", ["M1", "M2", "M3"])
def test_gate_triggers_on_extreme_atmosphere(metric):
    r = predict(metric, g_m_s2=0.0, p_psia=14.7, o2=0.9, u_cm_s=10, L_mm=10, n=N_MC, n_boot=N_BOOT)
    assert r["applicable"] is False
    assert r["estimate"] is None and r["band90"] is None
    assert "nearest tested condition" in r["reason"]


def test_deterministic_with_seed():
    a = _pred("M3", "lunar_base", seed=7)
    b = _pred("M3", "lunar_base", seed=7)
    assert a == b
    c = _pred("M3", "lunar_base", seed=8)
    assert c["regime_fractions"] != a["regime_fractions"] or c["u_eff_summary"] != a["u_eff_summary"]


def test_fuel_option_and_droplet_clip():
    h = _pred("M1", "iss", fuel="Heptane")
    m = _pred("M1", "iss", fuel="Methanol")
    assert h["estimate"] != m["estimate"]
    assert h["inputs"]["droplet_clipped"] is True and h["inputs"]["droplet_mm"] <= 4.67
    with pytest.raises(ValueError):
        _pred("M1", "iss", fuel="diesel")


def test_widen_band_logit_and_quantity():
    lo, hi = widen_band("probability", 0.5, 0.4, 0.6, 2.0)
    assert lo < 0.4 and hi > 0.6 and 0 <= lo and hi <= 1
    assert widen_band("probability", 0.5, 0.4, 0.6, 1.0) == [0.4, 0.6]
    assert widen_band("quantity", 2.0, 1.5, 2.5, 2.0) == [1.0, 3.0]
    assert widen_band("quantity", 1.0, 0.2, 1.5, 3.0)[0] == 0.0


def test_unknown_metric():
    with pytest.raises(KeyError):
        predict("M9", **_hab("iss"))


def test_rules_dispatch_missing(monkeypatch):
    real = bounds.importlib.import_module

    def fake(name, *a, **k):
        if name == "engine.rules":
            raise ImportError("engine.rules not written yet")
        return real(name, *a, **k)

    monkeypatch.setattr(bounds.importlib, "import_module", fake)
    with pytest.raises(NotImplementedError):
        predict("M4", **_hab("iss"))


@pytest.mark.parametrize("metric", ["M1", "M2", "M3"])
def test_json_safe(metric):
    for pid in ("iss", "earth", "lunar_rover"):
        json.dumps(_pred(metric, pid), allow_nan=False)


def test_artifacts_json_safe(tmp_path):
    paths = bounds.build_artifacts(out_dir=tmp_path, n=N_MC)
    names = {p.name for p in paths}
    for pid in ("iss", "exploration", "lunar_base", "lunar_rover", "mars_base", "earth"):
        for m in ("M1", "M2", "M3"):
            assert f"{pid}_{m}.json" in names
    for p in paths:
        json.loads(p.read_text(encoding="utf-8"))
        json.dumps(json.loads(p.read_text(encoding="utf-8")), allow_nan=False)


# ---------------------------------------------------------------- ADR-0006 dilution-aware gate
def test_gate_rejects_co2_at_34_percent_o2():
    for co2 in (0.05, 0.2, 0.4):
        r = _pred("M1", "lunar_base", co2=co2)
        assert r["applicable"] is False and r["estimate"] is None
        assert "CO2-diluted" in r["reason"] and "between 14% and 24% O2" in r["reason"]
    assert _pred("M1", "lunar_base", he=0.2)["applicable"] is False


def test_gate_accepts_co2_in_iss_air():
    r = _pred("M1", "iss", co2=0.2)
    assert r["applicable"] is True and 0 <= r["estimate"] <= 1
    assert r["inputs"]["co2"] == 0.2
    assert _pred("M2", "iss", co2=0.2)["applicable"] is True


def test_undiluted_presets_unchanged_by_diluent_gate():
    """Undiluted queries: same applicability as before ADR-0006 (lunar M2 stays gated)."""
    assert _pred("M1", "lunar_base")["applicable"] is True
    assert _pred("M2", "lunar_base")["applicable"] is False
    assert _pred("M1", "iss")["applicable"] is True


def test_diluent_evidence_rule_uses_only_diluted_tests():
    # lunar base is 0.80 from undiluted 34% O2 tests; with a little CO2 those do not count
    d0 = _pred("M1", "lunar_base")["evidence"][0]["distance"]
    d1 = _pred("M1", "lunar_base", co2=0.05)["evidence"][0]["distance"]
    assert d0 < 1.0 and d1 > bounds.GATE_DISTANCE


def test_m3_ignores_diluent_gate():
    a = _pred("M3", "lunar_base")
    assert a["applicable"] is True


def test_composition_over_one_rejected():
    with pytest.raises(ValueError):
        _pred("M1", "iss", co2=0.9)


def test_dilution_distance_matches_vector():
    d = bounds.dilution_distance(0.21, 1.0, 0.2, 0.0, 0.21, 1.0, 0.0, 0.0)
    assert math.isclose(d, 2.0)
