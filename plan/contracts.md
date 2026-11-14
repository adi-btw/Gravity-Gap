# Team Contracts (build phases 1 and 2; phase 2 addendum at the end)

Back to [overview](00-overview.md). This is the shared interface every role builds against, so parallel work fits together.
**Change a contract only by editing this file and saying so in your hand-off report.**

## Ownership (each role writes ONLY its own paths)
| Role | Owns |
|---|---|
| TL (Tech Lead / Physics) | `engine/__init__.py`, `engine/physics.py`, `engine/presets.py`, `engine/montecarlo.py`, `engine/regime_grid.py`, `tests/fixtures/physics_reference.json`, `tests/test_physics.py`, `tests/test_montecarlo.py`, `artifacts/regime_grid.json`, `plan/decisions.md` |
| DE (Data Engineer) | `scripts/fetch_psi.py`, `engine/catalog.py`, `engine/rank.py`, `tests/test_data_quality.py`, `tests/test_catalog.py`, `tests/test_rank.py`, `artifacts/catalog.json`, `data/raw_manifest.json` |
| AI (AI / Backend Engineer) | `api/**`, `tests/test_api.py`, `requirements.txt`, `pytest.ini`, `.github/workflows/ci.yml`, `.env.example` |
| FE (Frontend Engineer) | `web/**` |

Nobody runs `git commit` or `git push`; the team lead integrates and commits.

## Units and conventions
- Gravity in m/s² (`g_m_s2`). Constants: `G0 = 9.81`, Moon = 1.62, Mars = 3.71.
- Pressure in psia (`p_psia`). `P0_PSIA = 14.7`. `PSIA_PER_ATM = 14.696`.
- O₂ is a mole fraction (`o2`, 0.21 = 21%).
- Flow speeds in cm/s (`u_cm_s`). Flame or fuel size in mm (`L_mm`).

## `engine/physics.py` (TL)
```python
G0 = 9.81; P0_PSIA = 14.7; PSIA_PER_ATM = 14.696
RI_FORCED_MAX = 0.1; RI_BUOYANT_MIN = 10.0

def buoyant_velocity_cm_s(g_m_s2: float, L_mm: float, dT_over_T: float = 4.0, C_b: float = 1.0) -> float
    # C_b * sqrt(g * L * dT/T), L in metres inside, result in cm/s. g=0 -> 0.
def richardson(u_b_cm_s: float, u_f_cm_s: float) -> float
    # u_b^2 / u_f^2 ; u_b == 0 -> 0.0 ; u_f == 0 and u_b > 0 -> math.inf
def regime(ri: float) -> str            # "forced" (<0.1) | "mixed" (0.1..10) | "buoyant" (>10)
def g_star(g_m_s2: float, p_psia: float) -> float      # (g/G0) * (p/P0_PSIA)**2
def o2_partial_pressure_psia(o2: float, p_psia: float) -> float
def effective_flow_cm_s(u_f_cm_s: float, u_b_cm_s: float, k: float = 1.0) -> float   # sqrt(u_f^2 + (k u_b)^2)
def atmosphere_distance(o2: float, p_atm: float, o2_t: float, p_t_atm: float) -> float
    # sqrt(((o2-o2_t)/0.05)^2 + ((ln p - ln p_t)/0.3)^2)
def evaluate(g_m_s2, p_psia, o2, u_cm_s, L_mm, dT_over_T=4.0, C_b=1.0, k=1.0) -> dict
    # keys: u_b_cm_s, ri, regime, g_star, p_o2_psia, u_eff_cm_s   (ri may be inf -> serialize as None)
```

## `engine/presets.py` (TL)
`PRESETS: list[dict]` with keys `id, label, g_m_s2, p_psia, o2, u_cm_s, L_mm, source, assumed` (ids: `iss, exploration, lunar_base, lunar_rover, mars_base, earth`). Values exactly as in [04-features.md](04-features.md) F0; `L_mm` default 10.

## `engine/montecarlo.py` (TL)
`sample_physics(g_m_s2, p_psia, o2, u_cm_s, L_mm, n=2000, seed=0) -> dict` draws C_b ~ U[0.5,1.5], k ~ U[0.3,1.0], dT/T ~ U[3,6], L ~ L_mm × U[0.5,1.5]; returns arrays `u_b, ri, u_eff` and `summary` = {p05,p50,p95} for each plus `regime_fractions` {forced, mixed, buoyant}.

## Shared physics fixtures (TL writes, FE and AI read)
`tests/fixtures/physics_reference.json`:
```json
{"cases":[{"id":"R1","fn":"buoyant_velocity_cm_s","args":{"g_m_s2":9.81,"L_mm":10,"dT_over_T":4,"C_b":1},"expected":62.64,"rel_tol":0.01}, ...]}
```
`fn` is one of the physics function names; `args` use the Python keyword names; `expected` is a number, or a string for `regime`; for an infinite result use `"inf"`. Include at least R1–R5 from [08-testing-qa.md](08-testing-qa.md) plus g_star, effective_flow, regime and atmosphere_distance cases.

## `artifacts/catalog.json` (DE)
`{"version": "...", "generated_at": "...", "investigations": [record, ...]}` with each record as in [02-data-pipeline.md](02-data-pipeline.md) P3: `id, acronym, title, doi, platform, hardware, fuel_phase, gravity_levels, ground_reference, conditions{o2:[min,max]|null, pressure_atm:[min,max]|null, flow_cm_s:[min,max]|null}, n_tests, outcomes_available, hazard_pillars[], objective, hypothesis, impacts, publications[{doi,title}], related[], is_combustion`. Condition ranges are computed from `data/clean/psi_tests.csv` (and day summaries); text fields come from the PSI API `https://psi.nasa.gov/geode-py/ws/repo/investigations/{id}`.

## `engine/rank.py` (DE)
`rank(catalog: list[dict], g_m_s2, p_psia, o2, u_cm_s, weights: dict | None = None) -> list[dict]`, each item `{id, acronym, score, parts{atmosphere, pillar, fuel_realism, outcomes, n_tests}}`, sorted by descending score. Non-combustion records (`is_combustion: false`) are excluded. Default weights `{atmosphere:0.35, pillar:0.2, fuel_realism:0.2, outcomes:0.15, n_tests:0.1}`. **Phase 2:** a sixth part `regime_fit` was added (u_eff samples inside the record's tested flow range, or the forced fraction for no-flow records); default weights are now `{atmosphere:0.30, pillar:0.15, fuel_realism:0.15, outcomes:0.15, n_tests:0.10, regime_fit:0.15}`. Catalog records add `conditions.o2_burner_stream`; `fuel_phase` may be `aerosol`.

## API (AI): FastAPI app `api.main:app`, run with `uvicorn api.main:app --reload --port 8000`
| Method | Path | Body / query | Response |
|---|---|---|---|
| GET | `/health` | – | `{status:"ok", artifact_version, engine_version}` |
| GET | `/presets` | – | `PRESETS` |
| GET | `/catalog` | – | list of records |
| GET | `/catalog/{id}` | – | record (404 problem+json if missing) |
| POST | `/physics` | `{g_m_s2, p_psia, o2, u_cm_s, L_mm}` | `evaluate(...)` + `mc` = `sample_physics(...)["summary"]` and `regime_fractions` |
| POST | `/rank` | habitat fields + optional `weights` | `rank(...)` |
| GET | `/data/tests` | `investigation_id?, o2_min?, o2_max?, limit=100, offset=0` | `{total, rows[]}` from `data/clean/psi_tests.csv` |
CORS allows `http://localhost:3000`. Errors use RFC 7807 problem+json.

## Web (FE)
Next.js (App Router, TypeScript, Tailwind) in `web/`. API base from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
`web/lib/physics.ts` mirrors `engine/physics.py` function-for-function (camelCase names allowed, but the parity test maps fixture `fn` names). `web/lib/presets.ts` mirrors `engine/presets.py`.
The parity test (vitest) reads `../tests/fixtures/physics_reference.json`.

---

# Phase 2 addendum (M3 Prediction core, M4 Intelligence, M5 Full product)

## Ownership (phase 2)
| Role | Owns |
|---|---|
| TL | `engine/bounds.py`, `engine/models/` (M1–M3 fitting code), `engine/planner.py`, `artifacts/bounds/`, `artifacts/planner.json`, `tests/test_bounds.py`, `tests/test_planner.py`, `engine/validation.py`, `artifacts/validation_report.md`, `plan/decisions.md` (append) |
| DE | `engine/rules.py` (M4, M5), `artifacts/rules.json`, `engine/rank.py` + `engine/catalog.py` (improvements), `tests/test_rules.py`, `tests/test_rank.py`, `tests/test_catalog.py` |
| AI | `api/**`, `engine/ledger.py`, `ledger/predictions.jsonl`, `engine/ai/` (context pack, validator, prompts, offline cache), `artifacts/ai_cache.json`, `artifacts/MANIFEST.json` + `scripts/build_manifest.py`, `tests/test_api.py`, `tests/test_ledger.py`, `tests/test_ai.py`, `requirements.txt` |
| FE | `web/**` |

## `engine/bounds.py` (TL)
```python
METRICS: dict[str, dict]   # id -> {label, unit, kind: "probability"|"quantity"|"category", data, flow_dependent: bool}
def predict(metric: str, g_m_s2, p_psia, o2, u_cm_s, L_mm, n=2000, seed=0) -> dict
```
`predict` returns:
```
{metric, label, unit, kind,
 applicable: bool, reason: str|None,                 # honesty gate (atmosphere distance > 2 -> applicable False, estimate None)
 estimate: float|str|None, band90: [lo, hi]|None,
 ref_0g: {estimate, band90}, ref_1g: {estimate, band90}|None,   # 1g ref None when no basis
 regime_fractions: {forced, mixed, buoyant}, u_eff_summary: {p05,p50,p95},
 nonmonotonic_flag: bool, nonmonotonic_note: str|None,
 transfer: {basis: str, confidence: "high"|"medium"|"low"},   # how microgravity evidence transfers at this gravity
 evidence: [{record_id, investigation_id, distance}],        # up to 20 nearest training rows
 sensitivity: [{param, low, high}],                          # tornado: metric at param low/high
 n_train: int, model_version: str}
```
M1–M3 are fitted by TL; M4 and M5 dispatch to `engine.rules.predict_m4(...)` / `predict_m5(...)` (DE) which return the same shape.
**Gravity honesty rule:** droplet and spherical-burner data (FLEX, CFI-G) contain no flow variable, so for M1–M3 gravity must NOT silently change the estimate. Use the regime: forced fraction → evidence transfers (confidence high); mixed/buoyant → keep the microgravity-matched estimate but widen the band and lower `transfer.confidence`, and say so in `transfer.basis`. Flow-dependent metrics (M4, M5) map partial gravity through `u_eff`.
Precomputed: `artifacts/bounds/{preset_id}_{metric}.json` for all 6 presets × 5 metrics.

## `engine/planner.py` (TL)
`plan_tests(top_k=10) -> list[{rank, g_m_s2, p_psia, o2, u_cm_s, metric, score, parts{band_width, habitat_weight, mixed_fraction}, rationale, extends:[investigation_id]}]`; `main()` writes `artifacts/planner.json` (also `design_implications: [str]`).

## `engine/rules.py` (DE)
`predict_m4(...)`, `predict_m5(...)` with the `predict` signature and return shape above. M4 uses `data/clean/psi_saffire_ug_vs_1g.csv` (+ SAFFIRE-I/III, BASS-II context) as a rule table; M5 uses SPICE `flow_speed_cm_s` windows per fuel and nozzle. `artifacts/rules.json` holds the tables.

## Ledger (AI): `engine/ledger.py`
`append(prediction: dict, rationale: str, author: str) -> dict` writes one JSON line to `ledger/predictions.jsonl` with `{id, created_at, habitat, metric, estimate, band90, model_version, artifact_hashes, rationale, status:"open", sha256}`; `sha256` covers the canonical JSON of all other fields. `load()`, `verify() -> list[{id, ok}]`. Append-only: never rewrite existing lines.

## AI layer (AI): `engine/ai/`
`context.py` builds the context pack (habitat, engine outputs with ids, top catalog records, evidence rows). `validator.py` checks every number in an answer appears in the context pack (±0.5%) and every citation id (`PSI-xx`, `rec:...`, `doi:...`) resolves. `answer.py` → `ask(question, habitat, context_ids) -> {answer_markdown, citations[], numbers_used[], validated, mode: "claude"|"cached"|"template"}`: uses Claude only if `ANTHROPIC_API_KEY` is set and the `anthropic` package is installed; otherwise a deterministic template answer built from engine outputs. Prompts in `engine/ai/prompts/*.md` (versioned).

## API additions (AI)
| Method | Path | Response |
|---|---|---|
| GET | `/metrics` | `bounds.METRICS` |
| POST | `/bounds` | body: habitat fields + `metric` → `bounds.predict(...)` (JSON-safe) |
| GET | `/planner` | `artifacts/planner.json` |
| GET | `/ledger` | `{predictions[], verification[]}` |
| POST | `/ledger` | header `X-Team-Token` must equal env `LEDGER_TEAM_TOKEN`; body {metric, habitat, rationale, author} → appended record |
| POST | `/ask` | {question, habitat, context_ids[]} → `ask(...)` |
| GET | `/data/export` | filters + `format=csv|json`; CSV starts with `#` comment lines citing every included investigation DOI |

---

# Phase 3 addendum (M5 Full product → M7 Submission)

## Ownership (phase 3)
| Role | Owns |
|---|---|
| TL (+ PM hat) | `plan/11-demo-pitch.md`, `plan/06-frontend-ux.md` (fix `?g=` units), `plan/STATUS.md`, `docs/SUBMISSION.md`, `docs/DEMO_SCRIPT.md`, `README.md` |
| DE | `engine/hindcast.py`, `artifacts/validation_saffire.md`, `artifacts/hindcast_saffire.json`, `tests/test_hindcast.py`, `data/clean/README.md` |
| AI | `api/**`, `Dockerfile.api`, `web.Dockerfile`, `docker-compose.yml`, `.dockerignore`, `render.yaml`, `.github/workflows/**`, `requirements*.txt`, `docs/DEPLOY.md`, `tests/test_api.py`, `scripts/check_ledger_append_only.py` |
| FE | `web/**`, `docs/media/**` |

Nobody commits or pushes. Do not run `scripts/build_manifest.py` or `engine.ai.answer --build-cache` (the team lead rebuilds them once at the end).

## Interfaces added in phase 3
- `GET /data/tests` and `/data/export` accept `outcome=` (exact match on the `outcome` column; repeatable or comma-separated).
- E2E tests live in `web/e2e/` (Playwright). `npm run e2e` starts the API (`python -m uvicorn api.main:app --port 8000` from the repo root) and the web app (`next start` on 3000) through Playwright `webServer`, and runs the scripted demo path online and offline (API stopped / blocked).
- `docs/media/` holds demo screenshots and the recorded demo video produced by the E2E run.

---

# Round 2 · R1 Real-fire replay addendum (see plan/13-round-2-features.md)

## Ownership (R1)
| Role | Owns |
|---|---|
| DE | `data/incidents.json`, `tests/test_incidents_data.py` |
| TL | `engine/incidents.py`, `artifacts/incidents.json`, `tests/test_incidents.py` |
| AI | `api/**` (incident endpoints), `engine/ai/**` (incident context + cached questions), `tests/test_api.py`, `tests/test_ai.py` |
| FE | `web/**` |
Nobody commits. Do not run `scripts/build_manifest.py` (team lead runs cache + manifest last).

## `data/incidents.json` (DE)
```json
{"version": 1, "incidents": [{
  "id": "apollo1", "name": "Apollo 1", "date": "1967-01-27",
  "phase": "pre-launch plugs-out test on the pad",
  "in_scope": true, "scope_note": null,
  "g_m_s2": 9.81, "p_psia": 16.7, "o2": 1.0, "u_cm_s": 10, "L_mm": 10,
  "assumed": ["u_cm_s", "L_mm"],
  "summary": "neutral, factual 1-2 sentences",
  "sources": [{"field": "p_psia|o2|g_m_s2|summary|date", "url": "https://...", "quote": "exact words from the page"}]
}]}
```
- ids: `apollo1`, `mir1997`, `artemis2`, `apollo13`. Out-of-scope incidents (`apollo13`) set `in_scope: false`, a `scope_note`, and may leave g/p/o2 as null.
- Every in-scope numeric field except those listed in `assumed` needs a `sources` entry with a verbatim quote. A value that can't be confirmed from an official NASA page is listed in `assumed` with a note in `summary`, never guessed silently.

## `artifacts/incidents.json` (TL, `python -m engine.incidents`)
```
{generated_at, engine_version, incidents: [ {<all data/incidents.json fields>,
   physics: evaluate(...) (ri null for inf) | null,
   regime_fractions: {forced, mixed, buoyant} | null,
   metrics: {M1..M5: {applicable, estimate, band90, reason, transfer_confidence}} | null,
   coverage: {M1..M5: {covered, nearest_distance}} | null,
   findings: [plain-language factual strings built only from the numbers above]} ]}
```
Out-of-scope incidents get `physics`/`metrics`/`coverage` = null and one finding explaining the scope.

## API (AI)
| Method | Path | Response |
|---|---|---|
| GET | `/incidents` | `artifacts/incidents.json` (503 problem+json if not built) |
| GET | `/incidents/{id}` | one incident (404 problem+json if unknown) |

## Web (FE)
`/replay` page (cards → "Load this habitat" sets `?g=&p=&o2=&u=&L=` then links to `/bounds`), a "History" group in the habitat bar, a landing link "Start with a real fire". Offline: reads `artifacts/incidents.json` (copied by `copy-artifacts.mjs`). The habitat bar pressure input max must allow 16.7 psia (raise to 20, matching the API limit).
