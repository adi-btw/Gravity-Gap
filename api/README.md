# Gravity Gap API

Thin FastAPI wrapper around `engine/` and the build artifacts. The binding contract is the API table in
[`plan/contracts.md`](../plan/contracts.md).

## Run

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

Run from the repo root. Interactive docs: http://localhost:8000/docs (OpenAPI JSON at `/openapi.json`).

At startup the app loads `artifacts/catalog.json` (if present) and `data/clean/psi_tests.csv` once and caches them.
`artifact_version` is the first 12 hex chars of the sha256 of `catalog.json` (or `"missing"`); the
`MANIFEST.json` integrity check is phase 2. CORS allows `http://localhost:3000` and `http://127.0.0.1:3000`.

## Endpoints

| Method | Path | Body / query | Response |
|---|---|---|---|
| GET | `/health` | – | `{status, artifact_version, engine_version}` |
| GET | `/presets` | – | `engine.presets.PRESETS` (6 habitats) |
| GET | `/catalog` | – | list of investigation records |
| GET | `/catalog/{id}` | – | one record, 404 problem+json if unknown |
| POST | `/physics` | `{g_m_s2, p_psia, o2, u_cm_s, L_mm}` | `engine.physics.evaluate(...)` + `mc` |
| POST | `/rank` | habitat fields + optional `weights` | `engine.rank.rank(...)` |
| GET | `/data/tests` | `investigation_id?, o2_min?, o2_max?, limit=100 (1..1000), offset=0` | `{total, limit, offset, rows[]}` |

Input bounds (`HabitatIn`): `0 <= g_m_s2 <= 30`, `0.5 <= p_psia <= 20`, `0.05 <= o2 <= 1`,
`0 <= u_cm_s <= 200`, `0 < L_mm <= 1000` (default 10).

`POST /physics` `mc` block: Monte Carlo from `engine.montecarlo.sample_physics(n=2000, seed=0)`:
`{n, seed, u_b, ri, u_eff: {p05, p50, p95}, regime_fractions: {forced, mixed, buoyant}, ri_inf_fraction}`.
Raw sample arrays are not returned. Any `inf`/`NaN` (for example `ri` when `u_cm_s = 0`) is serialized as `null`.

### Errors

All errors are RFC 7807 `application/problem+json`:

```json
{"type": "about:blank", "title": "Unprocessable Entity", "status": 422,
 "detail": "body.g_m_s2: Input should be greater than or equal to 0",
 "instance": "/physics", "errors": [{"loc": ["body", "g_m_s2"], "msg": "...", "type": "greater_than_equal"}]}
```

503 means an engine module or artifact is not available yet.

## Examples

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/physics -H "Content-Type: application/json" \
  -d '{"g_m_s2": 1.62, "p_psia": 8.2, "o2": 0.34, "u_cm_s": 5, "L_mm": 10}'

curl -X POST http://localhost:8000/rank -H "Content-Type: application/json" \
  -d '{"g_m_s2": 1.62, "p_psia": 8.2, "o2": 0.34, "u_cm_s": 5, "L_mm": 10}'

curl "http://localhost:8000/data/tests?investigation_id=PSI-98&limit=20&offset=0"
```

## Tests

```bash
python -m pytest tests/test_api.py -q
```

Tests that need `engine/*` modules or `artifacts/catalog.json` skip with a reason when those are not built yet.
