"""S1 habitat fire-safety briefing (engine/briefing.py; plan/contracts.md "Round 3 · S1 Briefing addendum")."""

from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path

import pytest

from engine import bounds, physics, uncertainty
from engine import briefing as br
from engine.presets import PRESETS
from tests.artifact_compare import assert_same_build

ROOT = Path(__file__).resolve().parents[1]
ART_DIR = ROOT / "artifacts" / "briefing"
PRESET_IDS = [p["id"] for p in PRESETS]
# Same citation prefixes as engine/ai/validator.py CITE_PREFIX (copied: that module is owned by the AI role).
CITE = re.compile(r"^(?:PSI-\d+|rec:[^\s,;\]]+|doi:[^\s,;\]]+|eng:[^\s,;\]]+|https?://[^\s,;\]]+)$")
SECTIONS = ("habitat", "verdicts", "key_numbers", "drivers", "gaps", "next_tests", "history", "trust", "footer",
            "citations")


@pytest.fixture(scope="module")
def docs():
    return {pid: br.briefing(pid, generated_at="2026-01-01T00:00:00+00:00") for pid in PRESET_IDS}


@pytest.fixture(scope="module")
def preds():
    out = {}
    for p in PRESETS:
        hab = [p[k] for k in ("g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm")]
        out[p["id"]] = {m: bounds.predict(m, *hab, n=2000, seed=0) for m in bounds.METRICS}
    return out


def _strip(doc: dict) -> dict:
    d = copy.deepcopy(doc)
    d["footer"].pop("generated_at", None)
    d["footer"].pop("date", None)
    d["footer"].pop("manifest", None)  # changes at every manifest rebuild (the manifest also hashes this file)
    d.pop("preset_id", None)
    return d


def _texts(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _texts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _texts(v)


@pytest.mark.parametrize("pid", PRESET_IDS)
def test_shape_all_presets(docs, pid):
    d = docs[pid]
    for k in SECTIONS:
        assert k in d
    assert d["artifact"] == "briefing" and d["adr"] == "ADR-0010" and d["citation"] == "eng:briefing"
    assert [v["pillar"] for v in d["verdicts"]] == ["prevention", "behaviour", "detection", "suppression"]
    assert d["habitat"]["preset_id"] == pid
    assert d["habitat"]["line"].startswith(d["habitat"]["label"])
    assert "not an operating procedure" in d["footer"]["disclaimer"].lower()
    json.dumps(d, allow_nan=False)


@pytest.mark.parametrize("pid", PRESET_IDS)
def test_every_chip_has_rule_and_because_and_follows_it(docs, preds, pid):
    p = preds[pid]
    for chip in docs[pid]["verdicts"]:
        assert chip["value"] in br.VALUES
        assert chip["rule"] == br.PILLAR_RULES[chip["pillar"]] and chip["rule"]
        assert chip["because"].strip().endswith(".")
        assert chip["citations"]
        ms = br.PILLARS[chip["pillar"]]["metrics"]
        if ms:
            cov = [p[m]["applicable"] for m in ms]
            want = "evidence" if all(cov) else ("partial" if any(cov) else "no evidence")
            assert chip["value"] == want
            assert chip["metrics"] == {m: p[m]["applicable"] for m in ms}
    det = docs[pid]["verdicts"][2]
    assert det["value"] == "partial"


def test_suppression_chip_rule(docs):
    for pid, d in docs.items():
        chip = d["verdicts"][3]
        flags = list(chip["metrics"].values())
        want = "evidence" if all(flags) else ("partial" if any(flags) else "no evidence")
        assert chip["value"] == want, pid
    assert docs["iss"]["verdicts"][3]["value"] == "evidence"
    assert docs["lunar_base"]["verdicts"][3]["value"] == "no evidence"


def test_lunar_base_gaps_not_numbers(docs):
    d = docs["lunar_base"]
    assert [k["metric"] for k in d["key_numbers"]] == ["M1", "M3"]
    gap_metrics = [g["metric"] for g in d["gaps"] if g["kind"] == "metric"]
    assert gap_metrics == ["M2", "M4", "M5"]
    ids = [g["id"] for g in d["gaps"]]
    assert "lunar_dust" in ids and "detector_sensitivity" in ids
    assert {"suppression_co2", "suppression_he"} <= set(ids)
    chips = {c["pillar"]: c["value"] for c in d["verdicts"]}
    assert chips == {"prevention": "partial", "behaviour": "partial", "detection": "partial",
                     "suppression": "no evidence"}
    for g in d["gaps"]:
        if g["kind"] == "metric":
            assert g["nearest_distance"] > bounds.GATE_DISTANCE
            assert g["nearest_point"] is not None


@pytest.mark.parametrize("pid", PRESET_IDS)
def test_key_numbers_trace_to_predict(docs, preds, pid):
    p = preds[pid]
    shown = {k["metric"]: k for k in docs[pid]["key_numbers"]}
    assert set(shown) == {m for m in bounds.METRICS if p[m]["applicable"]}
    for m, k in shown.items():
        assert k["estimate"] == p[m]["estimate"]
        assert k["band90"] == p[m]["band90"]
        assert k["transfer_confidence"] == p[m]["transfer"]["confidence"]
        assert f"eng:{m}" in k["citations"]
    for g in docs[pid]["gaps"]:
        if g["kind"] == "metric":
            assert not p[g["metric"]]["applicable"]
            if g["metric"] in bounds.FITTED:
                assert math.isclose(g["nearest_distance"], p[g["metric"]]["evidence"][0]["distance"], abs_tol=1e-4)
    assert docs[pid]["footer"]["model_versions"] == {m: p[m]["model_version"] for m in bounds.METRICS}


def test_drivers_trace_to_uncertainty(docs):
    d = docs["lunar_base"]
    assert [x["metric"] for x in d["drivers"]] == ["M1", "M3"]
    for x in d["drivers"]:
        u = uncertainty.drivers(x["metric"], 1.62, 8.2, 0.34, 10.0, 10.0)
        assert x["share"] == u["lever"]["share"] and x["text"] == u["lever"]["text"]
        assert x["citations"][0] == f"eng:drivers:{x['metric']}"


def test_next_tests_from_planner(docs):
    items = {it["rank"]: it for it in json.loads((ROOT / "artifacts" / "planner.json").read_text(encoding="utf-8"))["items"]}
    for d in docs.values():
        nt = d["next_tests"]["items"]
        assert len(nt) == min(3, len(items))
        for t in nt:
            src = items[t["rank"]]
            assert t["score"] == src["score"] and t["metric"] == src["metric"]
            assert t["citations"] == [f"eng:planner:{t['rank']}"]
        rel = [t["score"] * t["kernel"] for t in nt]
        assert rel == sorted(rel, reverse=True)
    assert docs["lunar_base"]["next_tests"]["items"][0]["rank"] == 1


def test_history_distances(docs):
    lb = docs["lunar_base"]["history"]
    assert lb["status"] == "none_close" and lb["close"] == []
    assert lb["nearest"]["distance"] > br.HISTORY_MAX_DISTANCE
    iss = docs["iss"]["history"]
    assert iss["status"] == "close"
    n = iss["nearest"]
    d = physics.atmosphere_distance(0.21, 14.7 / physics.PSIA_PER_ATM, n["o2"], n["p_psia"] / physics.PSIA_PER_ATM)
    assert math.isclose(n["distance"], round(d, 4), abs_tol=1e-9)
    assert "assumed" in iss["text"]
    for word in ("caused", "would have", "fault", "blame"):
        assert word not in iss["text"].lower()


def test_trust_from_holdout(docs):
    hold = json.loads((ROOT / "artifacts" / "holdout.json").read_text(encoding="utf-8"))
    t = docs["lunar_base"]["trust"]
    assert set(t["metrics"]) == {"M1", "M3"}
    for m, v in t["metrics"].items():
        s = hold["metrics"][m]["summary"]
        assert (v["band_held"], v["n_groups"]) == (s["band_coverage"]["k"], s["band_coverage"]["n"])
        assert (v["strict_held"], v["strict_n"]) == (s["strict_coverage"]["k"], s["strict_coverage"]["n"])
        assert f"{v['band_held']} of {v['n_groups']}" in t["text"]
        assert f"{v['strict_held']} of {v['strict_n']}" in t["text"]
    assert "0 g" in t["text"]


@pytest.mark.parametrize("pid", PRESET_IDS)
def test_citations_are_valid_and_collected(docs, pid):
    d = docs[pid]
    allc = set(d["citations"])
    for c in allc:
        assert CITE.match(c), c
    for sec in ("verdicts", "key_numbers", "drivers", "gaps"):
        for it in d[sec]:
            assert it["citations"] and set(it["citations"]) <= allc
    for sec in ("next_tests", "history", "trust"):
        assert set(d[sec]["citations"]) <= allc


def test_no_safest_wording(docs):
    for d in docs.values():
        for s in _texts(d):
            assert "safest" not in s.lower()


def test_deterministic_except_date():
    a = br.briefing("mars_base", generated_at="2026-01-01T00:00:00+00:00")
    b = br.briefing("mars_base")
    assert _strip(a) == _strip(b)
    assert a["footer"]["date"] == "2026-01-01"


def test_custom_habitat_marks_assumed():
    d = br.briefing({"g_m_s2": 1.62, "p_psia": 9.0, "o2": 0.30, "u_cm_s": 8.0, "label": "My base"})
    assert d["habitat"]["preset_id"] is None and d["habitat"]["label"] == "My base"
    assert d["habitat"]["assumed"] == ["L_mm"]
    assert "(assumed)" in d["habitat"]["line"]


@pytest.mark.parametrize("pid", PRESET_IDS)
def test_artifact_matches_engine(docs, pid):
    path = ART_DIR / f"{pid}.json"
    assert path.exists(), "run python -m engine.briefing"
    art = json.loads(path.read_text(encoding="utf-8"))
    assert art["preset_id"] == pid
    assert_same_build(_strip(art), _strip(docs[pid]))  # cross-platform: last float digits and model hashes
