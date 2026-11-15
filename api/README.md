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
| POST | `/bounds` | habitat fields + `metric` | `engine.bounds.predict(...)` (JSON-safe; 422 unknown metric; 503 if `engine.bounds`/`engine.rules` missing); plus optional `drivers` = `engine.uncertainty.drivers(metric, same habitat)` (S3 band-width shares, ADR-0008; `applicable: false` with a reason when there is no band; `null` if it fails, never blocks the answer) |
| POST | `/compare` | `{a, b}`: each a preset id (`"iss"`) or habitat fields (+ optional `label`) | `engine.compare.compare(a, b)` (S4): `{a, b, inputs_diff[], metrics[{metric, label, unit, kind, a, b, diff{regime, coverage, estimate, estimate_note, band_width}}], summary, model_versions}`. `diff.estimate` is `null` unless both sides have evidence; `summary` is one rule-built line (no LLM); 422 unknown preset / invalid habitat / extra keys |
| GET | `/coverage/{metric}` | `p_psia?, o2?, co2? (0..1), he? (0..1)` | `engine.coverage.coverage_for(...)`: tested points + rule, plus `habitat: {covered, nearest_distance, ...}` when `p_psia` and `o2` are given. For M1/M2 `co2`/`he` use the 4-D dilution-aware gate (ADR-0006); 422 if `o2 + co2 + he > 1`; 404 unknown metric |
| GET | `/planner` | – | `artifacts/planner.json` (`items[]`, `design_implications[]`); 503 if not built |
| GET | `/incidents` | – | `artifacts/incidents.json` (R1 real-fire replay: `{generated_at, engine_version, incidents[]}`); 503 if not built |
| GET | `/incidents/{id}` | – | one incident (`apollo1`, `mir1997`, `artemis2`, `apollo13`), 404 problem+json if unknown, 503 if not built |
| GET | `/suppression/diluents` | – | `engine.suppression.DILUENTS` (`{co2: {label, max: 0.70}, he: {label, max: 0.45}}`); 503 if `engine.suppression` missing |
| POST | `/suppression` | habitat fields + `diluent` (`co2`\|`he`, case-insensitive) + optional `steps` (5..30, default 15) | `engine.suppression.curve(...)` (JSON-safe): `{diluent, label, habitat, points[{fraction, M1, M2}], dose_for_p90, tested[], tested_o2_range, gate_note, safety_note, model_version}`; 422 bad diluent/steps or engine `ValueError`; 503 problem+json if `engine.suppression` missing |
| GET | `/suppression/reference` | – | `artifacts/suppression_reference.json` (empirical FLEX rates by diluent bin, no model); 503 if not built |
| GET | `/detection` | – | `artifacts/detection.json` unchanged (R3 detection evidence, reduced scope, ADR-0007: `scope_note`, `gaps[]`, `size_definitions`, `smoke_bins[]`, `smoke_runs`, `average_mass_comparison`, `simulation[]`); 503 if not built or not valid JSON |
| GET | `/holdout` | – | `artifacts/holdout.json` unchanged (S2 honesty test, ADR-0009: `metrics.{M1,M2,M3}` with `groups[]` + `summary`, `overall`, `wide_check`, `saffire_hindcast`); 503 if not built or not valid JSON |
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
  each citation (`PSI-xx`, `rec:...`, `doi:...`, `eng:...`, incident source `https://...` URLs) must resolve. Out-of-scope questions (rockets,
  propellants, weapons) get a refusal. Rebuild the cache with `python -m engine.ai.answer --build-cache`.
- **Real-fire replay (R1).** `/incidents` serves `artifacts/incidents.json` (built by `python -m engine.incidents`
  from `data/incidents.json`), read on every request, with `inf`/`NaN` as `null`. Out-of-scope incidents
  (`apollo13`) have `in_scope: false`, a `scope_note` and `physics`/`metrics`/`coverage` = `null`.
  `/ask` recognises incident questions ("What does Gravity Gap say about the Mir fire?", "Is Apollo 13 in
  scope?"; or `context_ids: ["mir1997"]`) as intent `incident`. Without a `habitat` the answer uses the incident's
  own conditions. Answers use only the incident artifact's numbers and cite `[eng:incident:<id>]` plus the
  source URL exactly as written in the incident's `sources` (the validator resolves both and never reads
  numbers inside URLs). Out-of-scope incidents get an "Outside Gravity Gap's scope" explanation and no
  hindsight wording ("would have prevented") is ever produced.
- **Suppression calculator (R2).** `POST /suppression` holds the habitat O₂ and pressure and replaces nitrogen
  with the diluent (`n2 = 1 - o2 - fraction`). Points outside the dilution-aware gate (ADR-0006) have
  `applicable: false` and `estimate: null` (draw them as gaps). `/ask` treats questions about putting a flame out
  with CO₂ / helium ("How much CO₂ would it take to put out a flame in ISS air?", "Does helium work better than
  CO₂?"; or `context_ids: ["eng:suppression:co2"]`) as intent `suppression`. The answer uses only the curve
  (preset artifact `artifacts/suppression/{preset}_{diluent}.json`, else live `curve(...)`) and the reference rows
  for the habitat's O₂ band. It cites `[eng:suppression:<co2|he>]`, `[PSI-69]` and `[eng:suppression_reference]`
  and gives the 90% dose, or "not reached inside tested conditions", plus a few estimates with bands, or the tested
  O₂ range when the habitat is gated (lunar base, 34% O₂). Every answer ends with the safety note. It gives no
  operational advice.
- **Artifact build order:** engine artifacts (incl. `python -m engine.incidents`) -> `python -m engine.ai.answer --build-cache` ->
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
