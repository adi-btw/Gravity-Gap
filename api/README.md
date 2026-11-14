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
`artifact_version` is the first 12 hex chars of the sha256 of `catalog.json` (or `"missing"`).
`/health` also re-hashes every file in `artifacts/` and compares with `artifacts/MANIFEST.json`
(`python scripts/build_manifest.py`): a mismatch gives `status: "degraded"` and `manifest_ok: false` with the
changed/missing/unlisted files; it never crashes. CORS allows the comma-separated origins in env `CORS_ORIGINS`
(default `http://localhost:3000,http://127.0.0.1:3000`). Deployment: [`docs/DEPLOY.md`](../docs/DEPLOY.md).

## Endpoints

| Method | Path | Body / query | Response |
|---|---|---|---|
| GET | `/health` | – | `{status: "ok"\|"degraded", artifact_version, engine_version, manifest_ok, manifest}` |
| GET | `/presets` | – | `engine.presets.PRESETS` (6 habitats) |
| GET | `/catalog` | – | list of investigation records |
| GET | `/catalog/{id}` | – | one record, 404 problem+json if unknown |
| POST | `/physics` | `{g_m_s2, p_psia, o2, u_cm_s, L_mm}` | `engine.physics.evaluate(...)` + `mc` |
| POST | `/rank` | habitat fields + optional `weights` | `engine.rank.rank(...)` |
| GET | `/data/tests` | `investigation_id?, o2_min?, o2_max?, outcome?, limit=100 (1..1000), offset=0` | `{total, limit, offset, rows[]}` |
| GET | `/metrics` | – | `engine.bounds.METRICS` (`M1`..`M5` -> `{label, unit, kind, data, flow_dependent}`) |
| POST | `/bounds` | habitat fields + `metric` | `engine.bounds.predict(...)` (JSON-safe; 422 unknown metric; 503 if `engine.bounds`/`engine.rules` missing) |
| GET | `/planner` | – | `artifacts/planner.json` (`items[]`, `design_implications[]`); 503 if not built |
| GET | `/ledger` | – | `{predictions[], verification[{id, ok, line}]}` from `ledger/predictions.jsonl` |
| POST | `/ledger` | header `X-Team-Token`; `{metric, habitat: preset id \| fields, rationale, author}` | 201 + appended record (`id, created_at, habitat, metric, estimate, band90, model_version, artifact_hashes, rationale, author, status, sha256`) |
| POST | `/ask` | `{question, habitat?: preset id \| fields, context_ids?: [PSI-xx, rec:..., M1]}` | `{answer_markdown, citations[], numbers_used[], validated, mode: "claude"\|"cached"\|"template", intent, habitat, validation}` |
| GET | `/data/export` | `investigation_id?, o2_min?, o2_max?, outcome?, format=csv\|json` | CSV with `#` header lines (cleaning-report version + one line per included investigation with its DOI), or JSON `{source, cleaning_report, citations[], total, rows[]}` |

`outcome` (phase 3) is an exact, case-sensitive match on the `outcome` column (e.g. `extinction`,
`self_extinguished`, `flow_terminated`); repeat it (`?outcome=a&outcome=b`) or comma-separate it
(`?outcome=a,b`) to match any of the values. Blank values are ignored.

### Phase 2 notes

- **Ledger writes** need env `LEDGER_TEAM_TOKEN`; when it is unset every `POST /ledger` is rejected (403).
  A wrong/missing `X-Team-Token` is 401. Predictions with `applicable: false` are refused (422): there is
  nothing falsifiable to freeze. The ledger is append-only; `sha256` is over the canonical JSON
  (`sort_keys`, `(",", ":")` separators, UTF-8) of all other fields; see `engine/ledger.py`.
- **Rate limits** (in-memory, per client IP, sliding 60 s window): `/ask` 20/min (`GRAVITY_GAP_ASK_RATE`),
  `POST /ledger` 10/min (`GRAVITY_GAP_LEDGER_RATE`). Exceeding them returns 429 problem+json with `Retry-After`.
- **AI modes.** `/ask` uses Claude only when `ANTHROPIC_API_KEY` is set *and* the `anthropic` package is
  installed (model `GRAVITY_GAP_MODEL`, default `claude-sonnet-5-5`); otherwise a fresh entry of
  `artifacts/ai_cache.json` (`mode: "cached"`) or a deterministic template answer (`mode: "template"`).
  Every answer is checked by `engine/ai/validator.py`: each number must be in the context pack (±0.5%) and
  each citation (`PSI-xx`, `rec:...`, `doi:...`, `eng:...`) must resolve. Out-of-scope questions (rockets,
  propellants, weapons) get a refusal. Rebuild the cache with `python -m engine.ai.answer --build-cache`.
- **Artifact build order:** engine artifacts -> `python -m engine.ai.answer --build-cache` ->
  `python scripts/build_manifest.py` (last).

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

curl -X POST http://localhost:8000/bounds -H "Content-Type: application/json"   -d '{"g_m_s2": 1.62, "p_psia": 8.2, "o2": 0.34, "u_cm_s": 10, "L_mm": 10, "metric": "M1"}'

curl -X POST http://localhost:8000/ask -H "Content-Type: application/json"   -d '{"question": "Why is the M1 band wide for the lunar base?", "habitat": "lunar_base"}'

curl -X POST http://localhost:8000/ledger -H "Content-Type: application/json" -H "X-Team-Token: $LEDGER_TEAM_TOKEN"   -d '{"metric": "M3", "habitat": "mars_base", "rationale": "Why we expect this...", "author": "Team"}'

curl -o psi_tests.csv "http://localhost:8000/data/export?investigation_id=PSI-69&format=csv"
```

## Tests

```bash
python -m pytest tests/test_api.py tests/test_ledger.py tests/test_ai.py -q
```

Tests that need `engine/*` modules or `artifacts/catalog.json` skip with a reason when those are not built yet.
