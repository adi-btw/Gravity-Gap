"""T5 API contract tests (plan/contracts.md API table, plan/08-testing-qa.md T5)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROBLEM_KEYS = {"type", "title", "status", "detail", "instance"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def presets_mod():
    return pytest.importorskip("engine.presets", reason="engine/presets.py (TL) not present yet")


@pytest.fixture(scope="module")
def physics_engine():
    pytest.importorskip("engine.physics", reason="engine/physics.py (TL) not present yet")
    pytest.importorskip("engine.montecarlo", reason="engine/montecarlo.py (TL) not present yet")


@pytest.fixture(scope="module")
def catalog_ready():
    if not (ROOT / "artifacts" / "catalog.json").exists():
        pytest.skip("artifacts/catalog.json (DE) not built yet")


def _preset(presets_mod, pid: str) -> dict:
    by_id = {p["id"]: p for p in presets_mod.PRESETS}
    p = by_id[pid]
    return {k: p[k] for k in ("g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm")}


def _assert_problem(resp, status: int) -> dict:
    assert resp.status_code == status
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert PROBLEM_KEYS <= body.keys()
    assert body["status"] == status
    return body


def _all_finite_or_null(obj) -> bool:
    if isinstance(obj, dict):
        return all(_all_finite_or_null(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_all_finite_or_null(v) for v in obj)
    if isinstance(obj, float):
        return math.isfinite(obj)
    return True


# --------------------------------------------------------------------------- health / presets


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body["artifact_version"], str) and body["artifact_version"]
    assert "engine_version" in body


def test_cors_allows_web_origin(client):
    r = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_presets_has_six(client, presets_mod):
    r = client.get("/presets")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert len(r.json()) == 6
    assert ids == {"iss", "exploration", "lunar_base", "lunar_rover", "mars_base", "earth"}


# --------------------------------------------------------------------------- physics


def _physics(client, body: dict):
    r = client.post("/physics", json=body)
    assert r.status_code == 200, r.text
    # Strict JSON: no NaN / Infinity tokens.
    data = json.loads(r.text, parse_constant=lambda c: pytest.fail(f"non-finite JSON token {c}"))
    assert _all_finite_or_null(data)
    return data


def test_physics_lunar_base_mixed(client, presets_mod, physics_engine):
    # R4 in plan/08: Moon, u_f = 10 cm/s, L = 10 mm -> Ri ~ 6.5 -> mixed.
    data = _physics(client, _preset(presets_mod, "lunar_base"))
    assert data["regime"] == "mixed"
    assert math.isclose(data["ri"], 6.5, rel_tol=0.02)


def test_physics_lunar_rover_shape(client, presets_mod, physics_engine):
    # Lunar rover vent is 5 cm/s, so the point estimate is Ri ~ 26 (buoyant) with
    # contract formulas; the Monte Carlo spread still straddles mixed/buoyant.
    data = _physics(client, _preset(presets_mod, "lunar_rover"))
    for key in ("u_b_cm_s", "ri", "regime", "g_star", "p_o2_psia", "u_eff_cm_s", "mc"):
        assert key in data
    assert data["regime"] == "buoyant"
    assert math.isclose(data["g_star"], 0.0513, rel_tol=0.01)
    mc = data["mc"]
    assert mc["n"] == 2000 and mc["seed"] == 0
    for q in ("u_b", "ri", "u_eff"):
        assert mc[q]["p05"] <= mc[q]["p50"] <= mc[q]["p95"]
    fr = mc["regime_fractions"]
    assert set(fr) >= {"forced", "mixed", "buoyant"}
    assert math.isclose(sum(fr[k] for k in ("forced", "mixed", "buoyant")), 1.0, abs_tol=1e-6)


def test_physics_matches_engine_evaluate(client, presets_mod, physics_engine):
    from engine.physics import evaluate

    body = _preset(presets_mod, "lunar_base")
    data = _physics(client, body)
    ref = evaluate(**body)
    assert data["regime"] == ref["regime"]
    assert math.isclose(data["u_b_cm_s"], ref["u_b_cm_s"], rel_tol=1e-12)


def test_physics_orbit_forced(client, presets_mod, physics_engine):
    data = _physics(client, _preset(presets_mod, "iss"))
    assert data["regime"] == "forced"
    assert data["ri"] == 0


def test_physics_earth_still_air_inf_is_null(client, presets_mod, physics_engine):
    # Earth preset has u = 0, so Ri = inf; it must serialize as null, not Infinity.
    data = _physics(client, _preset(presets_mod, "earth"))
    assert data["ri"] is None
    assert data["regime"] == "buoyant"


def test_physics_invalid_body_problem_json(client):
    r = client.post("/physics", json={"g_m_s2": -1, "p_psia": 14.7, "o2": 0.21, "u_cm_s": 10, "L_mm": 10})
    body = _assert_problem(r, 422)
    assert body["errors"]


def test_physics_missing_field_problem_json(client):
    _assert_problem(client.post("/physics", json={"g_m_s2": 1.62}), 422)


# --------------------------------------------------------------------------- catalog / rank


def test_catalog_unknown_id_404_problem_json(client, catalog_ready):
    _assert_problem(client.get("/catalog/DOES-NOT-EXIST"), 404)


def test_catalog_list_and_record(client, catalog_ready):
    r = client.get("/catalog")
    assert r.status_code == 200
    records = r.json()
    assert records
    first = records[0]["id"]
    r2 = client.get(f"/catalog/{first}")
    assert r2.status_code == 200 and r2.json()["id"] == first


def test_unknown_route_problem_json(client):
    _assert_problem(client.get("/no-such-route"), 404)


def test_rank_excludes_non_combustion_and_sorted(client, catalog_ready):
    pytest.importorskip("engine.rank", reason="engine/rank.py (DE) not present yet")
    body = {"g_m_s2": 1.62, "p_psia": 8.2, "o2": 0.34, "u_cm_s": 5, "L_mm": 10}
    r = client.post("/rank", json=body)
    assert r.status_code == 200, r.text
    items = r.json()
    assert items
    records = {rec["id"]: rec for rec in client.get("/catalog").json()}
    non_combustion = {rid for rid, rec in records.items() if rec.get("is_combustion") is False}
    assert not ({i["id"] for i in items} & non_combustion)
    scores = [i["score"] for i in items]
    assert scores == sorted(scores, reverse=True)
    assert {"atmosphere", "pillar", "fuel_realism", "outcomes", "n_tests"} <= items[0]["parts"].keys()


# --------------------------------------------------------------------------- data/tests


def test_data_tests_pagination(client):
    r1 = client.get("/data/tests", params={"limit": 5, "offset": 0})
    r2 = client.get("/data/tests", params={"limit": 5, "offset": 5})
    assert r1.status_code == 200 and r2.status_code == 200
    p1, p2 = r1.json(), r2.json()
    assert p1["total"] == p2["total"] > 10
    assert len(p1["rows"]) == 5 and len(p2["rows"]) == 5
    assert {r["record_id"] for r in p1["rows"]}.isdisjoint({r["record_id"] for r in p2["rows"]})
    json.loads(r1.text, parse_constant=lambda c: pytest.fail(f"non-finite JSON token {c}"))


def test_data_tests_filter(client):
    total = client.get("/data/tests", params={"limit": 1}).json()["total"]
    r = client.get("/data/tests", params={"investigation_id": "PSI-69", "o2_min": 0.2, "o2_max": 0.25, "limit": 1000})
    assert r.status_code == 200
    body = r.json()
    assert 0 < body["total"] < total
    for row in body["rows"]:
        assert row["investigation_id"] == "PSI-69"
        assert 0.2 <= row["o2_mole_fraction"] <= 0.25


def test_data_tests_bad_limit_problem_json(client):
    _assert_problem(client.get("/data/tests", params={"limit": 0}), 422)
