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


# --------------------------------------------------------------------------- R2 suppression calculator

import sys  # noqa: E402
import types  # noqa: E402

SUPPRESSION_QUESTIONS = [
    ("How much CO₂ would it take to put out a flame in ISS air?", "iss", ["co2"]),
    ("Why can't Gravity Gap answer suppression for the lunar base?", "lunar_base", ["co2"]),
    ("Does helium work better than CO₂?", "iss", ["co2", "he"]),
]
FAKE_SAFETY = ("CO₂ at these concentrations is dangerous to breathe. Spacecraft use portable CO₂ or water-mist "
               "extinguishers aimed at the fire, not cabin flooding. This shows how dilution affected flames in "
               "NASA's tests; it is not an operating procedure.")
FAKE_REFERENCE = {"version": 1, "max_diluted_o2_by_diluent": {"co2": 0.24, "he": 0.24}, "tables": {
    "co2": {"Heptane": {"0.17_0.22": {"o2_band": "0.17 < O2 <= 0.22", "n": 12, "bins": [
        {"bin": "0", "fraction_lo": 0.0, "fraction_hi": 0.0, "n": 5, "extinctions": 2, "completions": 3,
         "disruptions": 0, "extinction_rate": 0.4, "record_ids": ["PSI-69:FLEX:1"]},
        {"bin": "(0.1, 0.2]", "fraction_lo": 0.1, "fraction_hi": 0.2, "n": 7, "extinctions": 6, "completions": 1,
         "disruptions": 0, "extinction_rate": 0.857143, "record_ids": ["PSI-69:FLEX:2"]}]},
        "gt_0.22": {"o2_band": "O2 > 0.22", "n": 0, "bins": []}}},
    "he": {"Heptane": {"0.17_0.22": {"o2_band": "0.17 < O2 <= 0.22", "n": 3, "bins": [
        {"bin": "(0, 0.2]", "fraction_lo": 0.0, "fraction_hi": 0.2, "n": 3, "extinctions": 1, "completions": 2,
         "disruptions": 0, "extinction_rate": 0.333333, "record_ids": ["PSI-69:FLEX:3"]}]}}}},
    "trend": {"co2": {"Heptane": {"0.17_0.22": {"direction": "rises"}}}}}


def fake_curve(diluent, g_m_s2, p_psia, o2, u_cm_s, L_mm, steps=15, seed=0):
    """Contract-shaped stand-in for engine.suppression.curve (dilution tested at 14-24% O2, CO2 dose 50%)."""
    mx = {"co2": 0.70, "he": 0.45}[diluent]
    rng = [0.14, 0.24]
    pts, dose = [], None
    for i in range(steps):
        f = round(mx * i / (steps - 1), 6)
        if o2 + f > 1:
            m = {"applicable": False, "estimate": None, "band90": None, "reason": "composition over 100%"}
            pts.append({"fraction": f, "M1": m, "M2": m})
            continue
        if f > 0 and not rng[0] <= o2 <= rng[1]:
            m = {"applicable": False, "estimate": None, "band90": None,
                 "reason": "Extrapolation: no evidence. FLEX tested dilution only between 14% and 24% O2."}
            pts.append({"fraction": f, "M1": m, "M2": m})
            continue
        e = round(min(0.99, 0.3 + (1.2 if diluent == "co2" else 0.6) * f), 6)
        pts.append({"fraction": f,
                    "M1": {"applicable": True, "estimate": e,
                           "band90": [round(e * 0.7, 6), round(min(0.999, e * 1.08), 6)], "reason": None},
                    "M2": {"applicable": True, "estimate": round(2 + 3 * f, 6), "band90": [1.5, round(3 + 3 * f, 6)],
                           "reason": None}})
        if dose is None and e >= 0.9:
            dose = {"fraction": f, "metric": "M1"}
    ok = rng[0] <= o2 <= rng[1]
    note = ("FLEX tested this dilution only between 14% and 24% O₂; "
            + ("this habitat is inside that range." if ok else "there is no evidence at this oxygen level."))
    return {"diluent": diluent, "label": {"co2": "Carbon dioxide (CO2)", "he": "Helium"}[diluent],
            "habitat": {"g_m_s2": g_m_s2, "p_psia": p_psia, "o2": o2, "u_cm_s": u_cm_s, "L_mm": L_mm},
            "points": pts, "dose_for_p90": dose,
            "tested": [{"o2": 0.15, "p_atm": 0.7, "fraction": 0.5, "n": 4, "extinctions": 4}],
            "tested_o2_range": rng, "gate_note": note, "safety_note": FAKE_SAFETY, "model_version": "fake"}


@pytest.fixture
def fake_suppression(tmp_path, monkeypatch):
    """Fake engine.suppression + reference artifact; preset artifacts are hidden so the fake is used."""
    from engine.ai import context as ctx

    mod = types.ModuleType("engine.suppression")
    mod.curve = fake_curve
    mod.DILUENTS = {"co2": {"label": "Carbon dioxide (CO2)", "max": 0.70}, "he": {"label": "Helium", "max": 0.45}}
    monkeypatch.setitem(sys.modules, "engine.suppression", mod)
    monkeypatch.setattr(ctx, "SUPPRESSION_DIR", tmp_path / "no_suppression_artifacts")
    ref = tmp_path / "suppression_reference.json"
    ref.write_text(json.dumps(FAKE_REFERENCE), encoding="utf-8")
    monkeypatch.setattr(ctx, "SUPPRESSION_REFERENCE_PATH", ref)
    return mod


def _check_suppression(res, diluents):
    assert res["intent"] == "suppression" and res["mode"] == "template"
    assert res["validated"], res["validation"]["errors"]
    assert all(n["source"] for n in res["validation"]["numbers"]), "every number must be in the context pack"
    assert all(c["resolved"] for c in res["validation"]["citations"])
    for d in diluents:
        assert f"eng:suppression:{d}" in res["citations"]
    assert "PSI-69" in res["citations"]
    md = res["answer_markdown"]
    assert "**Safety note:**" in md and "dangerous to breathe" in md and "not an operating procedure" in md


@pytest.mark.parametrize("question,habitat,diluents", SUPPRESSION_QUESTIONS)
def test_suppression_answers_validate(answer_mod, fake_suppression, question, habitat, diluents):
    _check_suppression(answer_mod.ask(question, habitat, use_cache=False), diluents)


def test_suppression_iss_co2_has_dose_and_bands(answer_mod, fake_suppression):
    res = answer_mod.ask(SUPPRESSION_QUESTIONS[0][0], "iss", use_cache=False)
    md = res["answer_markdown"]
    assert "about 50% CO₂" in md                                   # fake dose_for_p90
    assert md.count("90% band") >= 3 and "M2 extinction diameter" in md
    assert "eng:suppression_reference" in res["citations"] and "6 self-extinguished" in md
    assert "Helium" not in md


def test_suppression_lunar_base_explains_ceiling_without_dose(answer_mod, fake_suppression):
    res = answer_mod.ask(SUPPRESSION_QUESTIONS[1][0], "lunar_base", use_cache=False)
    md = res["answer_markdown"]
    assert "No evidence at any CO₂ fraction above 0" in md
    assert "24% O₂" in md and "above that ceiling" in md
    assert "not reached inside tested conditions" in md
    assert "about" not in md.split("**Dilution")[1].split("\n")[0]   # no dose number
    assert "M1 estimate" not in md                                   # no curve values at gated points


def test_suppression_helium_comparison(answer_mod, fake_suppression):
    md = answer_mod.ask(SUPPRESSION_QUESTIONS[2][0], "iss", use_cache=False)["answer_markdown"]
    assert "**CO₂ versus helium:**" in md and "only CO₂ reaches" in md
    assert "cannot say which works better" in md


def test_suppression_invented_dose_rejected(answer_mod, fake_suppression):
    from engine.ai import context as ctx

    q = SUPPRESSION_QUESTIONS[0][0]
    pack = ctx.build_context("iss", question=q)
    res = answer_mod.ask(q, "iss", use_cache=False)
    assert validate(res["answer_markdown"], pack)["ok"]
    rep = validate(res["answer_markdown"] + "\n\nAbout 37% CO₂ puts any flame out [eng:suppression:co2].", pack)
    assert not rep["ok"] and any("37%" in e for e in rep["errors"])
    rep = validate("See [eng:suppression:n2].", pack)
    assert "unresolved citation: eng:suppression:n2" in rep["errors"]


def test_suppression_citation_needs_curve_in_pack(answer_mod, fake_suppression):
    from engine.ai import context as ctx

    pack = ctx.build_context("iss", question="Why is the ISS in the forced regime?")
    assert pack["suppression"] == {} and "eng:suppression:co2" not in pack["citable_ids"]


def test_suppression_engine_missing_still_safe(answer_mod, tmp_path, monkeypatch):
    from engine.ai import context as ctx

    monkeypatch.setitem(sys.modules, "engine.suppression", None)  # import raises ImportError
    monkeypatch.setattr(ctx, "SUPPRESSION_DIR", tmp_path / "none")
    res = answer_mod.ask(SUPPRESSION_QUESTIONS[0][0], "iss", use_cache=False)
    assert res["intent"] == "suppression" and res["validated"], res["validation"]["errors"]
    md = res["answer_markdown"]
    assert "not available in this build" in md and answer_mod.SAFETY_NOTE in md


def test_suppression_intent_does_not_capture_other_questions(answer_mod):
    assert answer_mod.classify("Why is the M1 band wide for the lunar base?") == "band"
    assert answer_mod.classify("Explain the M2 extinction diameter") == "explain"
    assert answer_mod.classify("Can CO2 put out a rocket propellant fire?") == "refusal"
    assert answer_mod.classify("Does helium work better than CO₂?") == "suppression"


def test_reference_rows_parse_de_layout():
    from engine.ai import context as ctx

    rows = ctx.reference_rows(FAKE_REFERENCE, "co2")
    assert [r["bin"] for r in rows] == ["0", "(0.1, 0.2]"]
    assert rows[0]["fuel"] == "Heptane" and rows[0]["o2_lo"] == 0.17 and rows[1]["trend"] == "rises"
    assert ctx.reference_rows({"unexpected": []}, "co2") == []


def test_demo_questions_include_suppression(answer_mod):
    qs = dict(answer_mod.DEMO_QUESTIONS)
    for q, hab, _ in SUPPRESSION_QUESTIONS:
        assert qs.get(q) == hab


def test_suppression_cache_roundtrip(answer_mod, fake_suppression, tmp_path, monkeypatch):
    path = tmp_path / "ai_cache.json"
    monkeypatch.setattr(answer_mod, "CACHE_PATH", path)
    data = answer_mod.build_cache(path, [(q, h) for q, h, _ in SUPPRESSION_QUESTIONS])
    assert all(e["validated"] and e["intent"] == "suppression" for e in data["entries"])
    res = answer_mod.ask(SUPPRESSION_QUESTIONS[1][0], "lunar_base")
    assert res["mode"] == "cached" and res["validated"]


@pytest.mark.parametrize("question,habitat,diluents", SUPPRESSION_QUESTIONS)
def test_suppression_answers_on_real_engine(answer_mod, question, habitat, diluents):
    pytest.importorskip("engine.suppression", reason="engine/suppression.py (TL) not present yet")
    res = answer_mod.ask(question, habitat, use_cache=False)
    _check_suppression(res, diluents)
    if habitat == "lunar_base":
        md = res["answer_markdown"]
        assert "No evidence at any CO₂ fraction above 0" in md and "above that ceiling" in md
        assert "M1 estimate" not in md


# --------------------------------------------------------------------------- R3 detection evidence

DETECTION_PATH = ROOT / "artifacts" / "detection.json"
DUST_Q = "Could lunar dust trigger the smoke alarm?"
SMOKE_Q = "Is smoke in space different?"


@pytest.fixture
def detection_ready():
    if not DETECTION_PATH.exists():
        pytest.skip("artifacts/detection.json (TL) not built yet (python -m engine.detection)")
    return json.loads(DETECTION_PATH.read_text(encoding="utf-8"))


def test_detection_intent_and_pack(answer_mod, detection_ready):
    from engine.ai import context as ctx

    assert answer_mod.classify(DUST_Q) == "detection" and answer_mod.classify(SMOKE_Q) == "detection"
    assert answer_mod.classify("Why is the lunar base in the mixed regime?") == "regime"
    assert answer_mod.classify("How much CO₂ would it take to put out a flame in ISS air?") == "suppression"
    pack = ctx.build_context("lunar_base", question=DUST_Q)
    cites = set(pack["citable_ids"])
    for g in detection_ready["gaps"]:
        assert f"eng:detection:{g['id']}" in cites
    for s in detection_ready["simulation"] + detection_ready["smoke_bins"]:
        assert f"eng:detection:{s['id']}" in cites
    assert {"eng:detection", "eng:detection:same_r_runs_dg", "eng:detection:daft_ard_dam"} <= cites
    sims = pack["detection"]["simulation"]
    assert all("diameter_nm" not in s and "fraction" not in s for s in sims)  # no raw arrays in the pack
    other = ctx.build_context("lunar_base", question="Why is the lunar base in the mixed regime?")
    assert other["detection"] is None and not any(c.startswith("eng:detection") for c in other["citable_ids"])


def test_detection_citation_only_for_artifact_ids(answer_mod, detection_ready):
    from engine.ai import context as ctx

    pack = ctx.build_context("lunar_base", question=DUST_Q)
    ok = validate("No lunar dust data [eng:detection:lunar_dust] [eng:detection:psi115_case1_micro].", pack)
    assert ok["ok"], ok["errors"]
    bad = validate("Regolith sizes [eng:detection:lunar_regolith].", pack)
    assert "unresolved citation: eng:detection:lunar_regolith" in bad["errors"]


def test_detection_dust_answer(answer_mod, detection_ready):
    res = answer_mod.ask(DUST_Q, use_cache=False)
    assert res["intent"] == "detection" and res["mode"] == "template"
    assert res["validated"], res["validation"]["errors"]
    md = res["answer_markdown"]
    assert "no lunar dust and no lunar dust simulant" in md and "smoke detector responds to" in md
    for gid in ("lunar_dust", "dust_sizes", "detector_sensitivity"):
        assert f"eng:detection:{gid}" in res["citations"]
    assert "Arizona Road Dust (DAFT)" in md and "density of 1 g/cm3" in md
    assert "[verify]" not in md


def test_detection_smoke_in_space_answer(answer_mod, detection_ready):
    res = answer_mod.ask(SMOKE_Q, use_cache=False)
    assert res["intent"] == "detection" and res["validated"], res["validation"]["errors"]
    md = res["answer_markdown"]
    assert "simulation" in md and "surrogate" in md and "20 µm" in md
    assert "3.84%" in md and "0.38%" in md  # case 1: microgravity 0.0384 vs Earth 0.0038
    assert "eng:detection:psi115_case1_micro" in res["citations"]
    assert "different size definition" in md


def test_detection_invented_number_rejected(answer_mod, detection_ready):
    from engine.ai import context as ctx

    pack = ctx.build_context("lunar_base", question=SMOKE_Q)
    rep = validate("Microgravity keeps 7.7% of particles above 20 µm [eng:detection:psi115_case1_micro].", pack)
    assert not rep["ok"] and any("7.7" in e for e in rep["errors"])


def test_detection_artifact_missing_still_safe(answer_mod, tmp_path, monkeypatch):
    from engine.ai import context as ctx

    monkeypatch.setattr(ctx, "DETECTION_PATH", tmp_path / "missing.json")
    res = answer_mod.ask(DUST_Q, use_cache=False)
    assert res["intent"] == "detection" and res["validated"]
    assert "not available in this build" in res["answer_markdown"]


def test_demo_questions_include_detection(answer_mod):
    qs = dict(answer_mod.DEMO_QUESTIONS)
    assert DUST_Q in qs and SMOKE_Q in qs


# --------------------------------------------------------------------------- S4 habitat compare

COMPARE_Q = "What changes between ISS and the lunar base?"


def test_compare_detection_of_intent():
    from engine.ai import context as ctx

    assert ctx.preset_mentions(COMPARE_Q) == ["iss", "lunar_base"]
    assert ctx.wants_compare(COMPARE_Q)
    assert not ctx.wants_compare("Is the lunar rover safer with the fans off?")
    assert not ctx.wants_compare("Why is the lunar base in the mixed regime?")
    assert ctx.wants_compare("Tell me more", ["eng:compare"])


def test_demo_questions_include_compare(answer_mod):
    assert dict(answer_mod.DEMO_QUESTIONS).get(COMPARE_Q) == "lunar_base"


def test_compare_answer_grounded_and_validated(answer_mod):
    res = answer_mod.ask(COMPARE_Q, "lunar_base", use_cache=False, allow_claude=False)
    assert res["mode"] == "template" and res["intent"] == "compare"
    assert res["validated"], res["validation"]["errors"]
    assert {"eng:compare", "eng:compare:M1", "eng:compare:M2"} <= set(res["citations"])
    md = res["answer_markdown"]
    assert "M2, M4 and M5 lose their evidence at Lunar base" in md
    assert "No difference shown: Lunar base has no evidence for M2." in md
    assert "M1 goes from 93.9% to 20.1%" in md


def test_compare_cite_ids_only_for_present_metrics():
    from engine.ai import context as ctx

    pack = ctx.build_context("lunar_base", question=COMPARE_Q)
    assert pack["compare"]["a"]["preset_id"] == "iss" and pack["compare"]["b"]["preset_id"] == "lunar_base"
    ids = {c for c in pack["citable_ids"] if c.startswith("eng:compare")}
    assert ids == {"eng:compare", *(f"eng:compare:{m}" for m in pack["compare"]["metrics"])}
    assert not validate("See [eng:compare:M9].", pack)["ok"]
    plain = ctx.build_context("lunar_base", question="Why is the lunar base in the mixed regime?")
    assert plain["compare"] is None and not any(c.startswith("eng:compare") for c in plain["citable_ids"])


# --------------------------------------------------------------------------- S3 uncertainty drivers

DRIVERS_Q = "Why is the lunar base band so wide?"


def test_demo_questions_include_drivers_and_trust(answer_mod):
    qs = dict(answer_mod.DEMO_QUESTIONS)
    assert qs.get(DRIVERS_Q) == "lunar_base" and "How do you know it works?" in qs


def test_drivers_answer_grounded_and_validated(answer_mod):
    res = answer_mod.ask(DRIVERS_Q, "lunar_base", use_cache=False, allow_claude=False)
    assert res["mode"] == "template" and res["intent"] == "band"
    assert res["validated"], res["validation"]["errors"]
    md = res["answer_markdown"]
    assert "eng:drivers:M1" in res["citations"]
    assert "What makes this band wide" in md and "rounded to 5%" in md
    assert "from limited NASA tests" in md and "honesty rule for gravity" in md
    assert "engineering assumption, not PSI data" in md and "it never reaches this band" in md
    assert "Biggest lever" in md and "Why the band is wide (one input at a time)" in md


def test_drivers_pack_only_on_band_questions_and_ids_exist():
    from engine.ai import context as ctx

    pack = ctx.build_context("lunar_base", question=DRIVERS_Q)
    assert pack["drivers"]["M1"]["applicable"] is True and pack["drivers"]["M2"]["applicable"] is False
    shares = {s["source"]: s["share_pct"] for s in pack["drivers"]["M1"]["sources"]}
    assert all(v % 5 == 0 for v in shares.values()) and shares["k"] == 0
    assert {"eng:drivers:M1", "eng:drivers:M3"} <= set(pack["citable_ids"])
    assert not validate("See [eng:drivers:M9].", pack)["ok"]
    plain = ctx.build_context("lunar_base", question="Why is the lunar base in the mixed regime?")
    assert plain["drivers"] == {} and not any(c.startswith("eng:drivers") for c in plain["citable_ids"])
    only = ctx.build_context("lunar_base", question="Tell me more", context_ids=["eng:drivers:M3"])
    assert list(only["drivers"]) == ["M3"]


def test_drivers_custom_habitat_computed_live():
    from engine.ai import context as ctx

    hab = {"g_m_s2": 1.62, "p_psia": 8.0, "o2": 0.34, "u_cm_s": 10, "L_mm": 10}
    pack = ctx.build_context(hab, question="Why is the M1 band wide?")
    assert pack["habitat"]["preset_id"] is None and pack["drivers"]["M1"]["id"] == "eng:drivers:M1"


# --------------------------------------------------------------------------- S2 honesty test

TRUST_Q = "How do you know it works?"


@pytest.fixture
def holdout_ready():
    path = ROOT / "artifacts" / "holdout.json"
    if not path.exists():
        pytest.skip("artifacts/holdout.json (TL) not built yet (python -m engine.holdout)")
    return json.loads(path.read_text(encoding="utf-8"))


def test_trust_intent_does_not_capture_other_questions(answer_mod):
    assert answer_mod.classify(TRUST_Q) == "trust"
    assert answer_mod.classify("How often are these bands right?") == "trust"
    assert answer_mod.classify("Can I trust it?") == "trust"
    assert answer_mod.classify("Does helium work better than CO₂?") == "suppression"
    assert answer_mod.classify("Why is the M1 band wide for the lunar base?") == "band"
    assert answer_mod.classify("Is the lunar rover safer with the fans off?") == "fans_off"


def test_trust_answer_grounded_and_validated(answer_mod, holdout_ready):
    res = answer_mod.ask(TRUST_Q, use_cache=False, allow_claude=False)
    assert res["mode"] == "template" and res["intent"] == "trust"
    assert res["validated"], res["validation"]["errors"]
    md = res["answer_markdown"]
    ov = holdout_ready["overall"]
    assert f"{ov['band_coverage']['k']} of {ov['band_coverage']['n']}" in md
    m1 = holdout_ready["metrics"]["M1"]["summary"]["strict_coverage"]
    assert f"strict rule {m1['k']} of {m1['n']}" in md
    assert "wide check" in md.lower() and "weak test" in md and "Not discriminative" in md
    assert {"eng:holdout", "eng:holdout:saffire"} <= set(res["citations"])
    worst = holdout_ready["metrics"]["M1"]["summary"]["worst_misses"][0]["id"]
    assert f"eng:holdout:{worst}" in res["citations"]
    assert any(c.startswith("rec:PSI-69:FLEX:") for c in res["citations"])


def test_trust_pack_is_small_and_cites_only_present_groups(holdout_ready):
    from engine.ai import context as ctx

    pack = ctx.build_context("lunar_base", question=TRUST_Q)
    assert len(json.dumps(pack["holdout"])) < 30_000  # summaries + worst misses, not 222 groups
    ids = {c for c in pack["citable_ids"] if c.startswith("eng:holdout")}
    groups = {g["id"] for r in holdout_ready["metrics"].values() for g in r["groups"]}
    assert "eng:holdout" in ids and "eng:holdout:saffire" in ids
    assert all(i.split("eng:holdout:", 1)[1] in groups for i in ids - {"eng:holdout", "eng:holdout:saffire"})
    assert len(ids) < 20
    assert not validate("See [eng:holdout:M1-o2_0.999-p_9.99].", pack)["ok"]
    assert not validate("The test held out 13579 groups [eng:holdout].", pack)["ok"]
    plain = ctx.build_context("lunar_base", question="Why is the lunar base in the mixed regime?")
    assert plain["holdout"] is None


def test_trust_artifact_missing_still_safe(answer_mod, tmp_path, monkeypatch):
    from engine.ai import context as ctx

    monkeypatch.setattr(ctx, "HOLDOUT_PATH", tmp_path / "missing.json")
    res = answer_mod.ask(TRUST_Q, use_cache=False, allow_claude=False)
    assert res["intent"] == "trust" and res["validated"]
    assert "not available in this build" in res["answer_markdown"]
