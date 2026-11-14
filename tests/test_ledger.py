"""F5 ledger tests: hashes verify, tampering is detected, existing lines are never rewritten."""

from __future__ import annotations

import hashlib
import json

import pytest

from engine import ledger

HABITAT = {"preset_id": "lunar_base", "label": "Lunar base", "g_m_s2": 1.62, "p_psia": 8.2,
           "o2": 0.34, "u_cm_s": 10.0, "L_mm": 10.0}


def _prediction(metric="M1", estimate=0.42, band=(0.2, 0.7)):
    return {"metric": metric, "estimate": estimate, "band90": list(band), "applicable": True,
            "transfer": {"basis": "test", "confidence": "medium"}, "model_version": "test-1"}


@pytest.fixture()
def path(tmp_path):
    return tmp_path / "ledger" / "predictions.jsonl"


def test_append_and_verify(path, tmp_path):
    rec = ledger.append(_prediction(), "because", "tester", habitat=HABITAT, path=path,
                        artifacts_dir=tmp_path)
    assert rec["id"] == "GG-P0001" and rec["status"] == "open"
    assert rec["habitat"]["preset_id"] == "lunar_base"
    # sha256 is over canonical JSON of the other fields.
    body = {k: v for k, v in rec.items() if k != "sha256"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert rec["sha256"] == hashlib.sha256(canon.encode("utf-8")).hexdigest()
    assert ledger.load(path) == [rec]
    assert ledger.verify(path) == [{"id": "GG-P0001", "ok": True, "line": 1}]


def test_existing_lines_never_rewritten(path, tmp_path):
    ledger.append(_prediction(), "first", "tester", habitat=HABITAT, path=path, artifacts_dir=tmp_path)
    before = path.read_bytes()
    rec2 = ledger.append(_prediction("M3", 0.1, (0.05, 0.3)), "second", "tester", habitat=HABITAT,
                         path=path, artifacts_dir=tmp_path)
    after = path.read_bytes()
    assert after.startswith(before)
    assert rec2["id"] == "GG-P0002"
    assert [r["ok"] for r in ledger.verify(path)] == [True, True]


def test_tampering_detected(path, tmp_path):
    ledger.append(_prediction(), "first", "tester", habitat=HABITAT, path=path, artifacts_dir=tmp_path)
    ledger.append(_prediction("M2"), "second", "tester", habitat=HABITAT, path=path, artifacts_dir=tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["estimate"] = 0.99  # edit a frozen prediction
    lines[0] = json.dumps(rec)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = ledger.verify(path)
    assert result[0]["ok"] is False and result[0]["error"] == "sha256 mismatch"
    assert result[1]["ok"] is True


def test_numpy_and_nonfinite_values_are_canonicalised(path, tmp_path):
    np = pytest.importorskip("numpy")
    pred = _prediction(estimate=np.float64(0.5), band=(np.float64(0.1), float("inf")))
    rec = ledger.append(pred, "r", "a", habitat=HABITAT, path=path, artifacts_dir=tmp_path)
    assert rec["estimate"] == 0.5 and rec["band90"] == [0.1, None]
    assert ledger.verify(path)[0]["ok"]


def test_module_level_path_override(monkeypatch, tmp_path):
    p = tmp_path / "x.jsonl"
    monkeypatch.setattr(ledger, "LEDGER_PATH", p)
    ledger.append(_prediction(), "r", "a", habitat=HABITAT, artifacts_dir=tmp_path)
    assert p.exists() and len(ledger.load()) == 1


@pytest.mark.parametrize("kwargs", [
    {"rationale": "", "author": "a"},
    {"rationale": "r", "author": " "},
])
def test_rejects_missing_rationale_or_author(path, kwargs):
    with pytest.raises(ValueError):
        ledger.append(_prediction(), habitat=HABITAT, path=path, **kwargs)


def test_rejects_missing_habitat(path):
    with pytest.raises(ValueError):
        ledger.append(_prediction(), "r", "a", habitat={"g_m_s2": 1.62}, path=path)


def test_artifact_hashes_from_files(tmp_path):
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "ai_cache.json").write_text("{}", encoding="utf-8")
    hashes = ledger.artifact_hashes(tmp_path)
    assert list(hashes) == ["a.json"]
    assert hashes["a.json"] == hashlib.sha256(b"{}").hexdigest()


def test_repo_ledger_verifies_if_present():
    if not ledger.LEDGER_PATH.exists():
        pytest.skip("ledger/predictions.jsonl not seeded yet (scripts/seed_ledger.py)")
    results = ledger.verify()
    assert results and all(r["ok"] for r in results), results
