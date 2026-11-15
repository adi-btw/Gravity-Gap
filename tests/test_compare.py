"""S4 habitat compare (engine/compare.py; plan/contracts.md "Round 3 · S4 Compare addendum")."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine import compare as cmp

ROOT = Path(__file__).resolve().parents[1]
BOUNDS_DIR = ROOT / "artifacts" / "bounds"


def _pred(applicable=True, estimate=0.5, band=(0.4, 0.6), fr=(1.0, 0.0, 0.0), kind="probability", unit="probability"):
    return {"applicable": applicable, "reason": None if applicable else "Extrapolation: no evidence.",
            "estimate": estimate if applicable else None, "band90": list(band) if applicable else None,
            "kind": kind, "unit": unit, "label": "x",
            "regime_fractions": dict(zip(("forced", "mixed", "buoyant"), fr)),
            "transfer": {"basis": "b", "confidence": "high"}, "n_train": 3, "model_version": "t"}


def _fake(table):
    """predict_fn from {(preset_id, metric): prediction}."""
    return lambda h, m: table[(h["preset_id"], m)]


@pytest.fixture(scope="module")
def iss_lunar():
    return cmp.compare("iss", "lunar_base")


# ------------------------------------------------------------------- real engine: ISS vs lunar base
def test_iss_vs_lunar_base_shape(iss_lunar):
    r = iss_lunar
    assert [m["metric"] for m in r["metrics"]] == ["M1", "M2", "M3", "M4", "M5"]
    assert r["a"]["preset_id"] == "iss" and r["b"]["preset_id"] == "lunar_base"
    assert [d["field"] for d in r["inputs_diff"]] == ["g_m_s2", "p_psia", "o2"]
    json.dumps(r, allow_nan=False)  # JSON-safe


def test_m2_covered_on_iss_no_evidence_on_lunar_base(iss_lunar):
    m2 = next(m for m in iss_lunar["metrics"] if m["metric"] == "M2")
    assert m2["a"]["applicable"] is True and m2["a"]["estimate"] == pytest.approx(4.0038, rel=1e-3)
    assert m2["b"]["applicable"] is False and m2["b"]["estimate"] is None and m2["b"]["band90"] is None
    assert m2["diff"]["coverage"]["change"] == "lost"
    assert m2["diff"]["estimate"] is None  # never subtract from "no evidence"
    assert m2["diff"]["band_width"] is None
    assert m2["diff"]["estimate_note"] == "No difference shown: Lunar base has no evidence for M2."


def test_iss_vs_lunar_base_regime_flip_and_covered_estimates(iss_lunar):
    by = {m["metric"]: m for m in iss_lunar["metrics"]}
    for m in by.values():
        assert m["diff"]["regime"] == {"a": "forced", "b": "mixed", "changed": True}
    m1 = by["M1"]["diff"]["estimate"]
    assert m1["direction"] == "lower" and m1["delta"] == pytest.approx(m1["b"] - m1["a"])
    assert by["M1"]["diff"]["band_width"]["direction"] == "wider"
    assert {k for k, m in by.items() if m["diff"]["coverage"]["change"] == "lost"} == {"M2", "M4", "M5"}


def test_iss_vs_lunar_base_summary(iss_lunar):
    s = iss_lunar["summary"]
    assert s.startswith("Moving from ISS to Lunar base changes gravity 0 m/s² → 1.62 m/s², pressure 14.7 psia → "
                        "8.2 psia and O₂ 21% → 34%.")
    assert "The flame regime changes from forced flow to mixed for every metric." in s
    assert "M2, M4 and M5 lose their evidence at Lunar base" in s
    assert "M1 goes from 93.9% to 20.1%" in s and "M3 goes from 97.2% to 87.2%" in s
    assert "M2 goes" not in s


def test_matches_bounds_artifacts(iss_lunar):
    """Offline compare (web) is built from the bounds artifacts: the live numbers must be the same."""
    for side, pid in (("a", "iss"), ("b", "lunar_base")):
        for m in iss_lunar["metrics"]:
            f = BOUNDS_DIR / f"{pid}_{m['metric']}.json"
            if not f.exists():
                pytest.skip(f"{f.name} not built")
            art = json.loads(f.read_text(encoding="utf-8"))
            assert m[side]["applicable"] == art["applicable"]
            assert m[side]["estimate"] == (pytest.approx(art["estimate"]) if isinstance(art["estimate"], float)
                                           else art["estimate"])


# ------------------------------------------------------------------- diff rules (fake predictions)
def test_covered_vs_not_and_neither():
    table = {
        ("iss", "M1"): _pred(), ("lunar_base", "M1"): _pred(applicable=False),
        ("iss", "M2"): _pred(applicable=False), ("lunar_base", "M2"): _pred(estimate=0.7),
        ("iss", "M3"): _pred(applicable=False), ("lunar_base", "M3"): _pred(applicable=False),
        ("iss", "M4"): _pred(estimate="complete_burn", kind="category", unit="category"),
        ("lunar_base", "M4"): _pred(estimate="partial_burn", kind="category", unit="category"),
        ("iss", "M5"): _pred(estimate=0.3), ("lunar_base", "M5"): _pred(estimate=0.3, band=(0.1, 0.9)),
    }
    r = cmp.compare("iss", "lunar_base", predict_fn=_fake(table))
    by = {m["metric"]: m["diff"] for m in r["metrics"]}
    assert by["M1"]["coverage"]["change"] == "lost" and by["M1"]["estimate"] is None
    assert by["M2"]["coverage"]["change"] == "gained" and by["M2"]["estimate"] is None
    assert by["M2"]["estimate_note"] == "No difference shown: ISS has no evidence for M2."
    assert by["M3"]["coverage"]["change"] == "neither"
    assert by["M3"]["estimate_note"] == "No difference shown: neither habitat has evidence for M3."
    assert by["M4"]["estimate"] == {"a": "complete_burn", "b": "partial_burn", "delta": None, "direction": "changed"}
    assert by["M5"]["estimate"]["direction"] == "same" and by["M5"]["band_width"]["direction"] == "wider"
    s = r["summary"]
    assert "M1 loses its evidence at Lunar base" in s and "M2 gains evidence at Lunar base" in s
    assert "M3 has no evidence on either side" in s
    assert "M4 changes from complete burn to partial burn" in s and "M5 stays at 30%" in s
    assert "The flame regime" not in s  # no regime flip in the fake table


def test_regime_flip_only_some_metrics():
    table = {(p, m): _pred() for p in ("iss", "earth") for m in cmp.bounds.METRICS}
    table[("earth", "M1")] = _pred(fr=(0.1, 0.2, 0.7))
    r = cmp.compare("iss", "earth", predict_fn=_fake(table))
    m1 = r["metrics"][0]["diff"]["regime"]
    assert m1 == {"a": "forced", "b": "buoyant", "changed": True}
    assert "The flame regime changes from forced flow to buoyancy-dominated for M1." in r["summary"]


def test_dominant_regime_ties_and_missing():
    assert cmp.dominant_regime({"forced": 0.4, "mixed": 0.4, "buoyant": 0.2}) == "forced"
    assert cmp.dominant_regime(None) is None


def test_resolve_custom_and_unknown():
    h = cmp.resolve({"g_m_s2": 1.62, "p_psia": 8.2, "o2": 0.34, "u_cm_s": 10, "L_mm": 10})
    assert h["preset_id"] == "lunar_base" and h["label"] == "Lunar base"
    c = cmp.resolve({"g_m_s2": 1.0, "p_psia": 8.2, "o2": 0.3, "u_cm_s": 10})
    assert c["preset_id"] is None and c["label"] == "Custom habitat" and c["L_mm"] == 10.0
    with pytest.raises(ValueError):
        cmp.resolve("moonbase")
    with pytest.raises(ValueError):
        cmp.resolve({"g_m_s2": 1.0})


def test_same_habitat_has_no_differences():
    table = {(p, m): _pred() for p in ("iss",) for m in cmp.bounds.METRICS}
    r = cmp.compare("iss", "iss", predict_fn=_fake(table))
    assert r["inputs_diff"] == []
    assert r["summary"].startswith("ISS and ISS have the same inputs.")
