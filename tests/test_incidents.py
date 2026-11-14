"""R1 real-fire replay engine (engine/incidents.py)."""
import json
from pathlib import Path

import pytest

from engine import incidents

ROOT = Path(__file__).resolve().parents[1]
METRICS = ("M1", "M2", "M3", "M4", "M5")


def _inc(id_, g, p, o2, in_scope=True, scope_note=None):
    return {"id": id_, "name": id_, "date": "2000-01-01", "phase": "test", "in_scope": in_scope,
            "scope_note": scope_note, "g_m_s2": g, "p_psia": p, "o2": o2, "u_cm_s": 10, "L_mm": 10,
            "assumed": ["u_cm_s", "L_mm"], "summary": "fixture", "sources": []}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    path = tmp_path_factory.mktemp("inc") / "incidents.json"
    path.write_text(json.dumps({"version": 1, "incidents": [
        _inc("apollo1_like", 9.81, 16.7, 1.0),
        _inc("mir_like", 0.0, 14.7, 0.21),
        _inc("tank_like", None, None, None, in_scope=False, scope_note="a high-pressure tank failure, not a cabin fire."),
    ]}), encoding="utf-8")
    out = incidents.build_incidents(path)
    return {i["id"]: i for i in out["incidents"]}, out


def test_json_safe(built):
    _, out = built
    json.dumps(out, allow_nan=False)
    assert out["engine_version"] and out["generated_at"]


def test_out_of_scope_nulls(built):
    inc = built[0]["tank_like"]
    for k in ("physics", "regime_fractions", "metrics", "coverage"):
        assert inc[k] is None
    assert len(inc["findings"]) == 1 and "scope" in inc["findings"][0].lower()


def test_apollo1_like_buoyant_no_evidence(built):
    inc = built[0]["apollo1_like"]
    assert inc["physics"]["regime"] == "buoyant"
    for m in METRICS:
        assert inc["metrics"][m]["applicable"] is False
        assert inc["metrics"][m]["estimate"] is None
    assert any("no evidence for M1–M5" in f for f in inc["findings"])


def test_mir_like_forced_m1(built):
    inc = built[0]["mir_like"]
    assert inc["physics"]["regime"] == "forced"
    assert inc["metrics"]["M1"]["applicable"] is True
    assert inc["metrics"]["M1"]["estimate"] is not None
    assert any(f.startswith("M1 applies here") for f in inc["findings"])


def test_findings_and_coverage_consistent(built):
    for inc in built[0].values():
        assert inc["findings"]
        assert all("would have" not in f.lower() for f in inc["findings"])
        if inc["metrics"] is None:
            continue
        for m in METRICS:
            assert inc["coverage"][m]["covered"] == inc["metrics"][m]["applicable"], (inc["id"], m)


def test_real_artifact():
    path = ROOT / "artifacts" / "incidents.json"
    if not path.exists():
        pytest.skip("artifacts/incidents.json not built yet")
    data = json.loads(path.read_text(encoding="utf-8"))
    json.dumps(data, allow_nan=False)
    ids = {i["id"] for i in data["incidents"]}
    assert {"apollo1", "mir1997", "apollo13"} <= ids
    for inc in data["incidents"]:
        assert inc["findings"]
        assert all("would have" not in f.lower() for f in inc["findings"])
        if not inc["in_scope"]:
            assert inc["physics"] is None and inc["metrics"] is None and inc["coverage"] is None
        elif inc["metrics"] is not None:
            for m in METRICS:
                assert inc["coverage"][m]["covered"] == inc["metrics"][m]["applicable"]
