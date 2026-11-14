"""R2 suppression calculator tests (contract: plan/contracts.md R2 addendum, engine/suppression.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine import suppression
from engine.presets import PRESETS, PRESETS_BY_ID

N_BOOT = 60
N_MC = 300
REF_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "suppression_reference.json"
TOP_KEYS = {"diluent", "label", "habitat", "points", "dose_for_p90", "tested", "tested_o2_range",
            "gate_note", "safety_note", "model_version"}


def _hab(pid):
    p = PRESETS_BY_ID[pid]
    return {k: p[k] for k in ("g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm")}


@pytest.fixture(scope="module")
def iss_co2():
    return suppression.curve("co2", **_hab("iss"), n=N_MC, n_boot=N_BOOT)


@pytest.fixture(scope="module")
def lunar_co2():
    return suppression.curve("co2", **_hab("lunar_base"), n=N_MC, n_boot=N_BOOT)


def test_diluents_registry():
    assert suppression.DILUENTS == {"co2": {"label": "Carbon dioxide (CO2)", "max": 0.70},
                                    "he": {"label": "Helium", "max": 0.45}}


def test_contract_shape(iss_co2):
    r = iss_co2
    assert TOP_KEYS <= set(r)
    assert r["diluent"] == "co2" and r["habitat"] == _hab("iss")
    assert len(r["points"]) == 15
    fr = [p["fraction"] for p in r["points"]]
    assert fr[0] == 0 and abs(fr[-1] - 0.70) < 1e-9 and fr == sorted(fr)
    for p in r["points"]:
        for m in ("M1", "M2"):
            assert set(p[m]) >= {"applicable", "estimate", "band90", "reason"}
            if p[m]["applicable"]:
                lo, hi = p[m]["band90"]
                assert lo <= p[m]["estimate"] <= hi
            else:
                assert p[m]["estimate"] is None and p[m]["band90"] is None and p[m]["reason"]
    for t in r["tested"]:
        assert {"o2", "p_atm", "fraction", "n", "extinctions"} <= set(t)
        assert t["fraction"] > 0 and 0 <= t["extinctions"] <= t["n"]
    lo, hi = r["tested_o2_range"]
    assert 0.12 <= lo <= hi <= 0.25
    assert "dangerous to breathe" in r["safety_note"] and "not an operating procedure" in r["safety_note"]
    assert isinstance(r["model_version"], str) and r["model_version"]


def test_json_safe(iss_co2, lunar_co2):
    json.dumps(iss_co2, allow_nan=False)
    json.dumps(lunar_co2, allow_nan=False)


def test_iss_co2_curve_rises(iss_co2):
    ok = [p for p in iss_co2["points"] if p["M1"]["applicable"]]
    assert len(ok) >= 5 and any(p["fraction"] > 0 for p in ok)
    assert ok[-1]["M1"]["estimate"] > ok[0]["M1"]["estimate"], "M1 should rise with CO2 overall"
    assert "between 14% and 24%" in iss_co2["gate_note"]


def test_iss_direction_matches_empirical_reference(iss_co2):
    if not REF_PATH.exists():
        pytest.skip("artifacts/suppression_reference.json not built yet (DE)")
    ref = json.loads(REF_PATH.read_text(encoding="utf-8"))
    try:
        direction = ref["trend"]["co2"]["Heptane"]["0.17_0.22"]["direction"]
    except (KeyError, TypeError):
        pytest.skip("reference has no co2/Heptane/0.17_0.22 trend")
    ok = [p for p in iss_co2["points"] if p["M1"]["applicable"]]
    delta = ok[-1]["M1"]["estimate"] - ok[0]["M1"]["estimate"]
    if direction == "rises":
        assert delta > 0
    elif direction == "falls":
        assert delta < 0
    else:
        pytest.skip(f"reference trend is {direction!r}; no direction to compare")


def test_lunar_base_gated_at_every_dilution(lunar_co2):
    for p in lunar_co2["points"]:
        if p["fraction"] == 0:
            continue
        for m in ("M1", "M2"):
            assert p[m]["applicable"] is False
            if p["n2"] < 0:  # 34% O2 + 70% CO2 is over 100%
                assert p[m]["reason"] == "composition over 100%"
            else:
                assert "between 14% and 24% O2" in p[m]["reason"], p[m]["reason"]
    assert lunar_co2["dose_for_p90"] is None
    assert "no evidence" in lunar_co2["gate_note"] and "34%" in lunar_co2["gate_note"]


def test_lunar_base_helium_gated():
    r = suppression.curve("he", **_hab("lunar_base"), steps=5, n=N_MC, n_boot=N_BOOT)
    assert not any(p["M1"]["applicable"] for p in r["points"] if p["fraction"] > 0)


def test_composition_over_100_percent_invalid():
    r = suppression.curve("co2", g_m_s2=0.0, p_psia=14.7, o2=0.5, u_cm_s=10, L_mm=10, steps=8,
                          n=N_MC, n_boot=N_BOOT)
    bad = [p for p in r["points"] if p["n2"] < 0]
    assert bad
    for p in bad:
        for m in ("M1", "M2"):
            assert p[m]["applicable"] is False and p[m]["reason"] == "composition over 100%"


def test_dose_only_from_applicable_points():
    for pid in ("iss", "exploration"):
        for d in ("co2", "he"):
            r = suppression.curve(d, **_hab(pid), n=N_MC, n_boot=N_BOOT)
            dose = r["dose_for_p90"]
            first = next((p for p in r["points"] if p["M1"]["applicable"] and p["M1"]["estimate"] >= 0.9), None)
            if first is None:
                assert dose is None
            else:
                assert dose["metric"] == "M1" and dose["fraction"] == first["fraction"]


def test_bad_inputs():
    with pytest.raises(ValueError):
        suppression.curve("argon", **_hab("iss"))
    with pytest.raises(ValueError):
        suppression.curve("co2", **_hab("iss"), steps=1)


def test_artifacts_exist_after_build():
    for p in PRESETS:
        for d in suppression.DILUENTS:
            path = suppression.ARTIFACT_DIR / f"{p['id']}_{d}.json"
            assert path.exists(), f"run python -m engine.suppression ({path})"
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["preset_id"] == p["id"] and data["diluent"] == d and len(data["points"]) == 15


def test_safety_note_is_specific_to_the_diluent():
    """The CO2 breathing warning must not be shown for helium (each diluent has its own note)."""
    from engine.suppression import SAFETY_NOTES

    he = SAFETY_NOTES["he"]
    assert "CO₂" not in he and "CO2" not in he
    assert "helium" in he and "not an operating procedure" in he
    assert "dangerous to breathe" in SAFETY_NOTES["co2"]
