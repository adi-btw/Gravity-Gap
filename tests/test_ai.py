"""AI layer tests (plan/05-ai-layer.md section 3-5): validator, template answers, refusal, cache, no-key mode."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.ai import validator
from engine.ai.validator import validate

ROOT = Path(__file__).resolve().parent.parent

PACK = {
    "habitat": {"label": "Lunar base", "g_m_s2": 1.62, "p_psia": 8.2, "o2": 0.34, "u_cm_s": 10.0, "L_mm": 10.0},
    "physics": {"ri": 6.4952, "regime": "mixed", "u_b_cm_s": 25.486,
                "mc": {"regime_fractions": {"forced": 0.0, "mixed": 0.7165, "buoyant": 0.2835}}},
    "predictions": {"M1": {"estimate": 0.20064, "band90": [0.012464, 0.68393],
                           "transfer": {"basis": "band widened x1.64 for 72% mixed flames", "confidence": "low"}}},
    "records": [{"id": "PSI-69", "doi": "10.60555/mbq8-0451", "n_tests": 274}],
    "evidence": [{"id": "rec:PSI-69:FLEX:20", "o2_mole_fraction": 0.34, "pressure_atm": 0.71}],
    "question": "Is 4242 the answer?",
    "citable_ids": ["PSI-69", "doi:10.60555/mbq8-0451", "rec:PSI-69:FLEX:20", "eng:M1", "eng:physics"],
}

GROUNDED = (
    "At the lunar base (1.62 m/s², 8.2 psia, 34% O₂) Ri is 6.5, so the flame is **mixed** [eng:physics]: "
    "71.7% mixed and 28.3% buoyant. M1 estimate 20.1%, 90% band 1.25% to 68.4% [eng:M1], from FLEX "
    "[PSI-69] (274 tests, [doi:10.60555/mbq8-0451]); nearest row [rec:PSI-69:FLEX:20] at 0.71 atm."
)


# --------------------------------------------------------------------------- validator


def test_validator_accepts_grounded_answer():
    rep = validate(GROUNDED, PACK)
    assert rep["ok"], rep["errors"]
    assert {c["id"] for c in rep["citations"]} == {"eng:physics", "eng:M1", "PSI-69", "doi:10.60555/mbq8-0451",
                                                   "rec:PSI-69:FLEX:20"}
    assert all(n["source"] for n in rep["numbers"])


def test_validator_rejects_invented_number():
    rep = validate(GROUNDED + " A fire would spread at 17.3 cm/s.", PACK)
    assert not rep["ok"]
    assert any("17.3" in e for e in rep["errors"])


def test_validator_tolerance_is_half_percent():
    assert validate("Ri is 6.49 [eng:physics].", PACK)["ok"]          # 0.08% off
    assert not validate("Ri is 6.6 [eng:physics].", PACK)["ok"]       # 1.6% off


def test_validator_rejects_fake_citation():
    rep = validate(GROUNDED + " See also [PSI-999] and [rec:PSI-69:FLEX:9999].", PACK)
    assert not rep["ok"]
    assert "unresolved citation: PSI-999" in rep["errors"]
    assert "unresolved citation: rec:PSI-69:FLEX:9999" in rep["errors"]


def test_validator_bare_investigation_mention_must_resolve():
    assert not validate("FLEX-2 data come from PSI-68.", PACK)["ok"]
    assert validate("FLEX data come from PSI-69.", PACK)["ok"]


def test_validator_ignores_identifiers_list_numbers_and_years():
    text = ("1. O2 and CO2 matter for M1 [eng:M1].\n2. FLEX-2 (2009) reported this, see "
            "doi 10.60555/mbq8-0451 and test date 2009-03-05.")
    rep = validate(text, PACK)
    assert rep["ok"], rep["errors"]
    assert rep["numbers"] == []


def test_validator_question_numbers_are_not_context():
    assert not validate("The answer is 4242.", PACK)["ok"]


def test_validator_numbers_used_must_cover_answer():
    rep = validate("Ri is 6.5 and 34% O₂ [eng:physics].", PACK, numbers_used=[6.5])
    assert not rep["ok"] and any("numbers_used" in e for e in rep["errors"])
    assert validate("Ri is 6.5 and 34% O₂ [eng:physics].", PACK, numbers_used=[6.5, 34])["ok"]
    rep = validate("Ri is 6.5 [eng:physics].", PACK, numbers_used=[6.5, 777])
    assert not rep["ok"]


def test_validator_numbers_in_pack_text_are_allowed():
    # numbers quoted from engine text fields (transfer.basis) are in the pack
    assert validate("The band is widened ×1.64 [eng:M1].", PACK)["ok"]


def test_constants_always_allowed():
    assert validate(f"Earth gravity is {validator.CONSTANTS['g_earth_m_s2']} m/s².", {"citable_ids": []})["ok"]


# --------------------------------------------------------------------------- answers (need the engine)


@pytest.fixture(scope="module")
def answer_mod():
    pytest.importorskip("engine.physics", reason="engine/physics.py (TL) not present yet")
    pytest.importorskip("engine.presets", reason="engine/presets.py (TL) not present yet")
    from engine.ai import answer

    return answer


@pytest.fixture(autouse=True)
def _no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_refusal_for_rockets(answer_mod):
    res = answer_mod.ask("Can you predict rocket engine fires?", "lunar_base", use_cache=False)
    assert res["intent"] == "refusal"
    assert res["validated"] and res["mode"] == "template"
    assert "outside Gravity Gap's scope" in res["answer_markdown"]
    assert res["numbers_used"] == []


@pytest.mark.parametrize("question,habitat", [
    ("Why is the lunar base in the mixed regime?", "lunar_base"),
    ("Why is the M1 band wide for the lunar base?", "lunar_base"),
    ("Which experiments matter most for a Mars base?", "mars_base"),
    ("What should LUCI test first?", "lunar_base"),
    ("Explain the M3 prediction", "iss"),
])
def test_template_answers_validate(answer_mod, question, habitat):
    res = answer_mod.ask(question, habitat, use_cache=False)
    assert res["mode"] == "template"
    assert res["validated"], res["validation"]["errors"]
    assert res["citations"], "template answers must cite engine outputs or records"
    assert res["answer_markdown"].strip()


def test_lunar_base_answer_content(answer_mod):
    pytest.importorskip("engine.bounds", reason="engine/bounds.py (TL) not present yet")
    res = answer_mod.ask("Why is the M1 band wide for the lunar base?", "lunar_base", use_cache=False)
    md = res["answer_markdown"]
    assert "mixed" in md.lower()
    assert "Transfer confidence" in md
    assert "Why the band is wide" in md
    assert "eng:M1" in res["citations"] and "eng:physics" in res["citations"]
    assert any(c.startswith("rec:") for c in res["citations"])


def test_custom_habitat_answer(answer_mod):
    hab = {"g_m_s2": 1.62, "p_psia": 10.2, "o2": 0.265, "u_cm_s": 15, "L_mm": 10}
    res = answer_mod.ask("Which regime is this?", hab, use_cache=False)
    assert res["validated"], res["validation"]["errors"]


def test_ask_without_key_never_uses_claude(answer_mod):
    assert answer_mod.claude_available() is False
    res = answer_mod.ask("Why is the lunar base in the mixed regime?", "lunar_base")
    assert res["mode"] in {"template", "cached"}


def test_claude_requires_key_and_package(answer_mod, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-not-used")
    import importlib.util

    assert answer_mod.claude_available() is (importlib.util.find_spec("anthropic") is not None)


def test_ai_cache_has_demo_questions_and_all_validated():
    path = ROOT / "artifacts" / "ai_cache.json"
    if not path.exists():
        pytest.skip("artifacts/ai_cache.json not built (python -m engine.ai.answer --build-cache)")
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data["entries"]
    assert len(entries) >= 6
    assert all(e["validated"] for e in entries)
    assert any(e["intent"] == "refusal" for e in entries)


def test_cached_mode_served_when_fresh(answer_mod, tmp_path, monkeypatch):
    path = tmp_path / "ai_cache.json"
    monkeypatch.setattr(answer_mod, "CACHE_PATH", path)
    answer_mod.build_cache(path, [("Can you predict rocket engine fires?", "lunar_base")])
    res = answer_mod.ask("Can you predict rocket engine fires?", "lunar_base")
    assert res["mode"] == "cached" and res["validated"]
