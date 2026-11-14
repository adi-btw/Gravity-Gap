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


# --------------------------------------------------------------------------- R1 real-fire replay (incidents)

MIR_URL = "https://www.nasa.gov/history/25-years-ago-fire-aboard-space-station-mir/"
A1_URL = "https://sma.nasa.gov/sma-disciplines/accllp/apollo-1"
INCIDENTS_FIXTURE = {"generated_at": "2026-11-14T00:00:00+00:00", "engine_version": "test", "incidents": [
    {"id": "apollo1", "name": "Apollo 1", "date": "1967-01-27", "phase": "pre-launch test on the launch pad",
     "in_scope": True, "scope_note": None, "g_m_s2": 9.81, "p_psia": 16.7, "o2": 1.0, "u_cm_s": 10, "L_mm": 10,
     "assumed": ["u_cm_s", "L_mm"], "assumed_note": "Ventilation (10 cm/s) and size (10 mm) are assumptions.",
     "summary": "During a preflight test on Jan. 27, 1967, a fire swept through the Command Module.",
     "sources": [{"field": "o2", "url": A1_URL, "quote": "the cabin pressurized with 100% oxygen."},
                 {"field": "summary", "url": A1_URL, "quote": "a fire swept through the Command Module (CM)."}],
     "physics": {"u_b_cm_s": 62.6418, "ri": 39.24, "regime": "buoyant"},
     "regime_fractions": {"forced": 0.0, "mixed": 0.0365, "buoyant": 0.9635},
     "metrics": {m: {"applicable": False, "estimate": None, "band90": None, "transfer_confidence": "low",
                     "reason": "Extrapolation: no evidence. O2 100% is outside every tested atmosphere."}
                 for m in ("M1", "M2", "M3", "M4", "M5")},
     "coverage": {m: {"covered": False, "nearest_distance": 13.29} for m in ("M1", "M2", "M3", "M4", "M5")},
     "findings": ["O2 100% at 16.7 psia is outside every tested atmosphere: no evidence for M1-M5."]},
    {"id": "mir1997", "name": "Mir oxygen-generator fire", "date": "1997-02-24", "phase": "in orbit aboard Mir",
     "in_scope": True, "scope_note": None, "g_m_s2": 0.0, "p_psia": 14.7, "o2": 0.21, "u_cm_s": 10, "L_mm": 10,
     "assumed": ["p_psia", "o2", "u_cm_s", "L_mm"], "assumed_note": None,
     "summary": "On Feb. 24, 1997, a solid-fuel oxygen generator ignited in Mir's Kvant-1 module.",
     "sources": [{"field": "summary", "url": MIR_URL, "quote": "when a fire ignited in an oxygen generating system."}],
     "physics": {"u_b_cm_s": 0.0, "ri": 0.0, "regime": "forced"},
     "regime_fractions": {"forced": 1.0, "mixed": 0.0, "buoyant": 0.0},
     "metrics": {"M1": {"applicable": True, "estimate": 0.93871, "band90": [0.82469, 0.98151], "reason": None,
                        "transfer_confidence": "high"},
                 "M4": {"applicable": True, "estimate": "complete_burn", "band90": ["complete_burn", "complete_burn"],
                        "reason": None, "transfer_confidence": "low"}},
     "coverage": {"M1": {"covered": True, "nearest_distance": 0.0009}},
     "findings": ["In orbit (0 g) the flame is forced-flow: the regime ISS data covers best.",
                  "M1 applies here: estimate 0.939."]},
    {"id": "apollo13", "name": "Apollo 13", "date": "1970-04-13", "phase": "translunar flight", "in_scope": False,
     "scope_note": "Outside this tool's scope: Apollo 13 was a failure of a high-pressure oxygen tank, not a cabin fire.",
     "g_m_s2": None, "p_psia": None, "o2": None, "u_cm_s": None, "L_mm": None, "assumed": [],
     "summary": "On the third day of the mission, oxygen tank number two failed; the crew returned safely.",
     "sources": [{"field": "summary", "url": "https://sma.nasa.gov/sma-disciplines/accllp/apollo-13",
                  "quote": "oxygen tank number two blew up"}],
     "physics": None, "regime_fractions": None, "metrics": None, "coverage": None,
     "findings": ["Outside this tool's scope: Apollo 13 was a failure of a high-pressure oxygen tank, not a cabin fire.",
                  "A better design would have prevented this."]},  # hindsight finding: must be dropped
]}

INCIDENT_QUESTIONS = [
    ("What does Gravity Gap say about the Mir fire?", "mir1997"),
    ("What would Gravity Gap say about Apollo 1's cabin air?", "apollo1"),
    ("Is Apollo 13 in scope?", "apollo13"),
]


@pytest.fixture
def incidents_tmp(tmp_path, monkeypatch):
    from engine.ai import context as ctx

    path = tmp_path / "incidents.json"
    path.write_text(json.dumps(INCIDENTS_FIXTURE), encoding="utf-8")
    monkeypatch.setattr(ctx, "INCIDENTS_PATH", path)
    return path


def test_validator_url_and_incident_citations():
    pack = {"citable_ids": ["eng:incident:mir1997", MIR_URL], "incidents": [{"p_psia": 14.7}]}
    assert validate(f"Mir cabin 14.7 psia [eng:incident:mir1997] [{MIR_URL}].", pack)["ok"]
    # numbers inside URLs are not numbers; a fake URL or incident id does not resolve
    rep = validate("See [https://www.nasa.gov/fake-123] and [eng:incident:challenger1986].", pack)
    assert "unresolved citation: https://www.nasa.gov/fake-123" in rep["errors"]
    assert "unresolved citation: eng:incident:challenger1986" in rep["errors"]
    assert rep["numbers"] == []
    assert not validate("Bare link https://example.com/x1 is a citation too.", pack)["ok"]


def test_find_incidents_aliases():
    from engine.ai import context as ctx

    incs = INCIDENTS_FIXTURE["incidents"]

    def ids(q, c=()):
        return [i["id"] for i in ctx.find_incidents(q, c, incs)]

    assert ids("What about Apollo 1's cabin air?") == ["apollo1"]
    assert ids("Is Apollo 13 in scope?") == ["apollo13"]
    assert ids("the Mir fire") == ["mir1997"]
    assert ids("Why is the lunar base mixed?") == []
    assert ids("explain", ["eng:incident:mir1997"]) == ["mir1997"]


@pytest.mark.parametrize("question,iid", INCIDENT_QUESTIONS)
def test_incident_answers_validate(answer_mod, incidents_tmp, question, iid):
    res = answer_mod.ask(question, use_cache=False)
    assert res["intent"] == "incident" and res["mode"] == "template"
    assert res["validated"], res["validation"]["errors"]
    assert f"eng:incident:{iid}" in res["citations"]
    assert all(n["source"] for n in res["validation"]["numbers"]), "every number must be in the context pack"
    assert all(c["resolved"] for c in res["validation"]["citations"])
    urls = {s["url"] for i in INCIDENTS_FIXTURE["incidents"] if i["id"] == iid for s in i["sources"]}
    assert urls & set(res["citations"]), "sourced facts must cite the source URL"
    md = res["answer_markdown"].lower()
    assert "would have" not in md and "prevented" not in md


def test_apollo13_answer_outside_scope(answer_mod, incidents_tmp):
    res = answer_mod.ask("Is Apollo 13 in scope?", use_cache=False)
    md = res["answer_markdown"]
    assert "Outside Gravity Gap's scope" in md and "not a cabin fire" in md
    assert "Regime:" not in md and "90% band" not in md


def test_apollo1_answer_says_no_evidence(answer_mod, incidents_tmp):
    res = answer_mod.ask("What would Gravity Gap say about Apollo 1's cabin air?", use_cache=False)
    md = res["answer_markdown"]
    assert md.count("**no evidence**") == 5
    assert "100%" in md and "16.7 psia" in md and "(assumed" in md
    assert res["habitat"] == "Apollo 1"


def test_incident_answer_rejects_invented_number(answer_mod, incidents_tmp):
    from engine.ai import context as ctx

    q = "What does Gravity Gap say about the Mir fire?"
    res = answer_mod.ask(q, use_cache=False)
    pack = ctx.build_context(ctx.incident_habitat(INCIDENTS_FIXTURE["incidents"][1]), question=q)
    assert validate(res["answer_markdown"], pack)["ok"]
    rep = validate(res["answer_markdown"] + "\n\nThe cabin reached 987.6 psia [eng:incident:mir1997].", pack)
    assert not rep["ok"] and any("987.6" in e for e in rep["errors"])


def test_incident_cache_roundtrip(answer_mod, incidents_tmp, tmp_path, monkeypatch):
    path = tmp_path / "ai_cache.json"
    monkeypatch.setattr(answer_mod, "CACHE_PATH", path)
    data = answer_mod.build_cache(path, [(q, None) for q, _ in INCIDENT_QUESTIONS])
    assert [e["habitat"] for e in data["entries"]] == [f"incident:{i}" for _, i in INCIDENT_QUESTIONS]
    assert all(e["validated"] and e["intent"] == "incident" for e in data["entries"])
    res = answer_mod.ask("Is Apollo 13 in scope?")
    assert res["mode"] == "cached" and res["validated"]


def test_demo_questions_include_incidents(answer_mod):
    qs = [q for q, _ in answer_mod.DEMO_QUESTIONS]
    for q, _ in INCIDENT_QUESTIONS:
        assert q in qs


@pytest.mark.parametrize("question,iid", INCIDENT_QUESTIONS)
def test_incident_answers_on_real_artifact(answer_mod, question, iid):
    if not (ROOT / "artifacts" / "incidents.json").exists():
        pytest.skip("artifacts/incidents.json (TL, python -m engine.incidents) not built yet")
    res = answer_mod.ask(question, use_cache=False)
    assert res["intent"] == "incident"
    assert res["validated"], res["validation"]["errors"]
    assert f"eng:incident:{iid}" in res["citations"]
    assert any(c.startswith("https://") for c in res["citations"])
    assert "would have" not in res["answer_markdown"].lower()
    if iid == "apollo13":
        assert "Outside Gravity Gap's scope" in res["answer_markdown"]
