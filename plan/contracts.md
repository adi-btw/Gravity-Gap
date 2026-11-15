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

---

# Round 2 · R2 Suppression calculator addendum (see plan/13-round-2-features.md §R2)

## Ownership (R2)
| Role | Owns |
|---|---|
| TL | `engine/bounds.py` + `engine/models/` (dilution-aware gate), `engine/coverage.py` (same gate), `engine/suppression.py`, `engine/planner.py` (new candidate type), `artifacts/suppression/`, `artifacts/bounds/`, `artifacts/coverage/`, `artifacts/planner.json`, `artifacts/validation_report.md`, `tests/test_bounds.py`, `tests/test_coverage.py`, `tests/test_suppression.py`, `tests/test_planner.py`, `plan/decisions.md` (ADR-0006) |
| DE | `engine/suppression_reference.py`, `artifacts/suppression_reference.json`, `tests/test_suppression_reference.py` |
| AI | `api/**`, `engine/ai/**`, `tests/test_api.py`, `tests/test_ai.py` |
| FE | `web/**` |
Nobody commits. Team lead rebuilds incidents, AI cache and MANIFEST at the end.

## Dilution-aware gate (TL, ADR-0006)
For metrics whose models use diluents (M1, M2): a query is applicable only if some training test is within distance 2 in
`(o2/0.05, ln p/0.3, co2/0.10, he/0.10)`. M3–M5 unchanged. `engine/coverage.py` uses the same 4-D distance for M1/M2
(points gain `co2`, `he`) so "covered == applicable" still holds. Report any preset/incident result that changes.

## `engine/suppression.py` (TL)
```python
DILUENTS = {"co2": {"label": "Carbon dioxide (CO2)", "max": 0.70}, "he": {"label": "Helium", "max": 0.45}}
def curve(diluent, g_m_s2, p_psia, o2, u_cm_s, L_mm, steps=15, seed=0) -> dict
```
Holds the habitat O₂ and pressure; the diluent replaces nitrogen (`n2 = 1 - o2 - fraction`; a point with n2 < 0 is
`applicable: false`, reason "composition over 100%"). Returns:
```
{diluent, label, habitat:{g_m_s2,p_psia,o2,u_cm_s,L_mm},
 points:[{fraction, M1:{applicable, estimate, band90, reason}, M2:{applicable, estimate, band90, reason}}],
 dose_for_p90: {fraction, metric:"M1"} | null,      # smallest applicable fraction whose M1 estimate >= 0.9
 tested: [{o2, p_atm, fraction, n, extinctions}],  # FLEX training tests with this diluent > 0 (aggregated)
 tested_o2_range: [min, max] | null, gate_note: str, safety_note: str, model_version}
```
`python -m engine.suppression` writes `artifacts/suppression/{preset_id}_{co2|he}.json` for the 6 presets.

## `artifacts/suppression_reference.json` (DE)
Empirical FLEX outcome rates by diluent bin, independent of the models: for each diluent and fuel, bins of diluent
fraction (0, 0–0.1, 0.1–0.2, … per data) × O₂ bands (≤0.17, 0.17–0.22, >0.22): `{n, extinctions, completions,
disruptions, extinction_rate}` with record ids. Used to check the model curve's direction and shown as dots on the chart.

## API (AI)
| Method | Path | Response |
|---|---|---|
| GET | `/suppression/diluents` | `DILUENTS` |
| POST | `/suppression` | habitat fields + `diluent` (+ optional `steps` 5–30) → `curve(...)` (JSON-safe) |
| GET | `/suppression/reference` | `artifacts/suppression_reference.json` |

## Web (FE)
`/suppression` page "Put it out": diluent toggle, M1 curve with 90% band (gaps where not applicable, never
interpolated), M2 curve, the dose marker, the empirical reference dots, a "tested conditions" chart (diluent fraction × O₂
of the FLEX tests with the habitat's O₂ as a line), and an always-visible **warn-tone** safety note. Offline: preset
artifacts `artifacts/suppression/{preset}_{diluent}.json`; custom habitats need the live API.

# Round 2 · R3 Detection evidence addendum (see plan/13-round-2-features.md §R3, plan/14-detection-spike.md, ADR-0007)

**Reduced scope.** The spike returned PARTIAL. DAFT holds no dust size distribution, and none of the files hold lunar
dust. So the planned smoke-vs-dust overlap chart and the overlap metric are **dropped**. The page is called "Detection
evidence". It does not answer "could lunar dust fool a smoke detector?"; that question is listed as a gap.

## Ownership (R3)
| Role | Owns |
|---|---|
| TL | `engine/detection.py` (`build()`, `main()`), `artifacts/detection.json`, `tests/test_detection.py`, `plan/decisions.md` (ADR-0007), this section |
| DE | `scripts/fetch_detection.py`, `data/detection/**`, `engine/catalog.py` (`DETECTION_DATA`), `artifacts/catalog.json`, `tests/test_detection_spike.py` |
| AI | `api/**`, `engine/ai/**`, `tests/test_api.py`, `tests/test_ai.py` |
| FE | `web/**` |
Nobody commits. Team lead rebuilds the AI cache and MANIFEST at the end.

## `artifacts/detection.json` (TL, `python -m engine.detection`)
Built only from the committed files in `data/detection/raw/`, never from the git-ignored reference documents. Every
number comes from a parser in `engine/detection.py`; nothing is typed in. Written with `allow_nan=False`, UTF-8.
```
{
  "schema_version": 1, "generated_at": "ISO-8601", "engine_version": "0.1.0", "generated_by": "engine/detection.py",
  "title": "Detection evidence", "verdict": "partial",
  "scope_note": str,                          # reduced scope and why (plain language)
  "generated_from": [{"file": "data/detection/raw/<PSI>/<name>", "sha256": hex, "bytes": int}],
                                              # hashes from data/detection/manifest.json, re-checked on build
  "gaps": [{"id": str, "text": str}],         # ids below; always shown on the page
  "size_definitions": {<key>: {"label": str, "note": str}},   # legend for every size_definition used below
  "smoke_bins": [BinSeries],                  # 6: 3 runs x {all, big_only}
  "smoke_runs": RunSeries,                    # moment-method middle size per run, 5 materials, aged kept apart
  "average_mass_comparison": {...},           # the one like-for-like smoke vs dust comparison
  "simulation": [SimSeries]                   # 6 PSI-115 curves
}

BinSeries (smoke_bins[i]):
{ "id": "tem_lampwick_54_all", "label": str, "material": "Lampwick", "material_label": "Cotton lamp wick",
  "run": "54", "variant": "all" | "big_only", "variant_label": str,
  "size_definition": "tem_image_diameter", "note": str,
  "source": {"investigation_id": "PSI-101", "file": str, "sheet": str, "rows": "15-44"},
  "diameter_nm": [float],            # geometric bin centre, strictly increasing
  "count": [float],                  # particles counted in the bin (>= 0)
  "fraction": [float],               # count / particle_count, sums to 1
  "dlnD": float | null,              # bin width in ln(d), workbook cell C8
  "stats": {"count_median_diameter_nm", "geometric_mean_diameter_nm", "geometric_std", "particle_count"},
  "workbook_reported": {"geometric_mean_diameter_nm", "geometric_std", "cells": "I9, J9"} }

RunSeries (smoke_runs):
{ "id": "same_r_runs_dg", "label": str, "size_definition": "moment_geometric_mean", "note": str,
  "source": {"investigation_id": "PSI-101", "file": str, "sheet": "SAME R Results", "rows": "3-121"},
  "materials": ["Kapton", "Lampwick", "Pyrell", "Silicone", "Teflon"],
  "material_labels": {"Lampwick": "Cotton lamp wick", ...},
  "points": [{"material", "aged": bool, "run": "60a", "row": int, "description": str,
              "value_nm": float, "geometric_std": float}],           # one dot per run (strip chart)
  "by_material": [{"material", "material_label", "aged": bool, "n_runs": int,
                   "dg_nm": {"median", "min", "max"}, "geometric_std_median": float,
                   "diameter_of_average_mass_nm_median": float}] }  # 10 rows: 5 materials x unaged/aged

average_mass_comparison:
{ "size_definition": "diameter_of_average_mass", "note": str,
  "smoke": {"id": "same_r_runs_dam", "label": "Smoke from heated spacecraft materials (SAME-R)",
            "source": {... same file and sheet as smoke_runs ...},
            "points": [{"material", "aged", "run", "row", "value_nm"}], "range_nm": {"min", "max"}},
  "dust":  {"id": "daft_ard_dam", "label": "Arizona Road Dust (DAFT)", "material_text": str,   # quoted from the DAFT CSV
            "source": {"investigation_id": "PSI-47", "file": str, "sheet": "Logged Data Summary", "rows": "5, 9, 20"},
            "material_source": {"investigation_id": "PSI-47", "file": "PSI-47_Experimental_table_DAFT.csv",
                                "sheet": null, "rows": "2-3"},
            "assumed_density_g_per_cm3": 1.0, "density_note": str,
            "points": [{"bag": 1, "value_nm", "workbook_reported_nm", "number_per_cm3", "mass_mg_per_m3"}],
            "range_nm": {"min", "max"}} }

SimSeries (simulation[i]):
{ "id": "psi115_case1_earth", "label": str,   # always ends "(simulation, dibutyl phthalate surrogate, t = 7 s)"
  "case": "1" | "2", "case_label": "8cm" | "10cm", "gravity": "earth" | "micro",
  "variant": "base" | "no_settling" | "no_thermophoresis",
  "surrogate": "dibutyl phthalate", "time_s": 7, "is_simulation": true,
  "size_definition": "simulation_node_diameter", "note": str,
  "source": {"investigation_id": "PSI-115", "file": str, "sheet": null, "rows": "1-44"},
  "diameter_nm": [float],            # size-node diameter, strictly increasing
  "fraction": [float],               # share of this curve's own count per node, sums to 1 (raw unit is [verify])
  "stats": {"count_median_diameter_nm", "geometric_mean_diameter_nm", "geometric_std",
            "peak_diameter_nm", "share_of_count_above_20um"} }
```
Ids of simulation series: `psi115_case1_earth`, `psi115_case1_micro`, `psi115_case1_earth_no_settling`,
`psi115_case1_micro_no_thermophoresis`, `psi115_case2_earth`, `psi115_case2_micro`.

**Gap ids** (all present, in this order): `lunar_dust`, `dust_sizes`, `detector_sensitivity`, `detector_signals`,
`size_definitions_disagree`, `tem_coverage`, `simulation_units`, `simulation_vs_experiment`, `daft_bag_mapping`,
`same_files`.

**Size definitions** (keys of `size_definitions`): `tem_image_diameter` (measured on microscope images of collected
particles), `moment_geometric_mean` (worked out from three instrument totals, assuming a lognormal shape),
`diameter_of_average_mass` (size of a sphere with the average particle mass; needs a density),
`simulation_node_diameter` (size class in the PSI-115 model).

## Rules
- **Provenance:** every series (each item of `smoke_bins` and `simulation`, `smoke_runs`, `average_mass_comparison.smoke`
  and `.dust`) has `source: {investigation_id, file, sheet, rows}`; per-run points also carry `row`.
- **One size definition per series.** Series with different `size_definition` never share one line or one set of dots;
  the FE puts them on separate charts or clearly separate panels.
- **Wording:** the dust is always "Arizona Road Dust (DAFT)". No series `id`, `label`, `material` or `material_label`
  contains "lunar". "Lunar dust" appears only in the `lunar_dust` gap. The density-1.0 assumption is stated wherever a
  dust diameter is shown. No overlap metric. No ionization vs photoelectric sensitivity ranges (no cited source).
  Detector voltages are not shown (gap `detector_signals`). Plain language, short sentences, no hype.
- **Simulation:** shapes only (`fraction`); never compare simulation totals and never draw simulation curves on the
  experiment charts.

## Catalog (DE, `python -m engine.catalog`, version 1.2.0)
Every record gains `pillar_data: {}` or `{"detection": {"holds": str, "files": ["data/detection/raw/..."], "artifact":
"artifacts/detection.json" | null}}` for PSI-101, PSI-102 (sample table only, `artifact: null`), PSI-47 and PSI-115.
`pillar_evidence` (metadata keywords) is unchanged. The FE investigation card may show `holds` under the detection pillar.

## API (AI)
| Method | Path | Response |
|---|---|---|
| GET | `/detection` | `artifacts/detection.json` unchanged; 503 problem if missing or not valid JSON (as `/suppression/reference`) |

## Web (FE)
`/detection` page "Detection evidence" (hand-rolled SVG, log-scale diameter axis in nm):
1. `scope_note` at the top (info tone) and the `gaps` list always visible (`lunar_dust` first, warn tone).
2. Smoke size distributions: one chart per run, `fraction` vs `diameter_nm`; "all" and "big only" of the same run may
   share a chart (same size definition); `stats` as a small table; the series `note`.
3. Per-run smoke sizes: strip/dot chart of `smoke_runs.points` (`value_nm`, log axis) grouped by material, unaged and
   aged in two colours; `by_material` as a table.
4. Like-for-like: `average_mass_comparison.smoke.points` and `.dust.points` as dots on one log axis (same size
   definition), with the comparison `note`, and the dust `density_note` next to the dust dots.
5. Simulation: Earth vs microgravity per case (`fraction` vs `diameter_nm`) on its own chart, titled from `label`;
   `share_of_count_above_20um` shown as a number per curve; the two variants behind a secondary toggle.
6. Every chart shows its source file / sheet / rows (from `source`).

---

# Round 3 · S4 Compare addendum (see plan/15-round-3-features.md §S4)

## Ownership (S4)
| Role | Owns |
|---|---|
| TL | `engine/compare.py`, `tests/test_compare.py` |
| AI | `api/main.py` + `api/schemas.py` (`POST /compare`), `api/README.md` row, `engine/ai/context.py` (compare block), `engine/ai/answer.py` (intent `compare`, cached question), `tests/test_api.py`, `tests/test_ai.py` |
| FE | `web/app/compare/`, `web/components/CompareView.tsx`, `web/lib/compare.ts` (+ test), `web/lib/api.ts` (`compare`), nav item, `/bounds` link, `web/e2e/compare.spec.ts`, `/compare` in `web/e2e/a11y.spec.ts` |
No new artifact: offline compare for preset pairs is built in the browser from `artifacts/bounds/{preset}_{metric}.json`
with the same rules. Nobody commits; the team lead rebuilds the AI cache and MANIFEST.

## `engine/compare.py` (TL)
```python
def compare(a, b, n=2000, seed=0, predict_fn=None) -> dict   # a, b: preset id or habitat dict (+ optional label, preset_id)
```
`predict_fn(habitat, metric)` defaults to `engine.bounds.predict` (the AI context passes the preset artifacts, same numbers).
Returns (JSON-safe):
```
{a: Habitat, b: Habitat,                     # {preset_id|null, label, g_m_s2, p_psia, o2, u_cm_s, L_mm}
 inputs_diff: [{field, label, unit, a, b}],  # only fields that differ (math.isclose, rel 1e-9)
 metrics: [MetricCompare],                   # M1..M5 in order
 summary: str,                               # one plain-language line, built by rule (no LLM)
 model_versions: {M1: str, ...}}
MetricCompare:
{metric, label, unit, kind,
 a: Side, b: Side,
 diff: {regime:   {a, b, changed: bool},                         # dominant regime of regime_fractions
        coverage: {a: bool, b: bool, change: "both"|"neither"|"lost"|"gained"},
        estimate: {a, b, delta: float|null, direction: "higher"|"lower"|"same"|"changed"} | null,
        estimate_note: str|null,
        band_width: {a, b, direction: "wider"|"narrower"|"same"} | null}}   # only when estimate is numeric on both sides
Side: {applicable, reason, estimate, band90, regime: "forced"|"mixed"|"buoyant"|null, regime_fractions,
       transfer: {basis, confidence}|null, n_train, model_version}
```
**Diff rules.**
1. `inputs_diff`: every habitat field whose value differs, in the order g, p, O₂, vent, flame size.
2. Regime = the largest of `regime_fractions` (ties: forced, mixed, buoyant); `changed` when the two differ.
3. Coverage = `applicable`. "lost": covered at A, not at B; "gained": the reverse.
4. **Estimate change only when both sides are covered.** Numbers: `delta = b - a`, direction `higher`/`lower`/`same`
   (same when `math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)`). Categories (M4): `delta: null`, direction `same` or
   `changed`. When either side has no evidence, `estimate: null` and `estimate_note` says "No difference shown: <label>
   has no evidence for <metric>." Never subtract a number from "no evidence".

**Summary rule** (in this order, one sentence each, skipped when empty):
1. "Moving from <A> to <B> changes <list of 'field a → b'>." (or "<A> and <B> have the same inputs.")
2. Regime: "The flame regime changes from <a> to <b> (<metrics>)." (all five → "for every metric").
3. Coverage: "<metrics> lose their evidence at <B>." / "<metrics> gain evidence at <B>." / "<metrics> have no
   evidence on either side."
4. Estimates (both covered, numeric): "Where both sides have evidence, M1 goes from x to y and M3 from x to y."
   Categories that change: "M4 changes from <a> to <b>." Same: listed as "stays at".
5. Band width (both covered, numeric): "The 90% band is wider at <B> for M1 and M3." (and/or "narrower"), so an
   unchanged estimate never hides a change in uncertainty.
Values: probabilities as % and quantities with unit, 3 significant figures (same `fmt` as `engine/ai/answer.py`);
regime words "forced flow", "mixed", "buoyancy-dominated". Plain language, no hype.

## API (AI)
| Method | Path | Response |
|---|---|---|
| POST | `/compare` | `{a, b}`, each a preset id or habitat fields (`HabitatIn`; optional `label`) → `compare(a, b)`; 422 unknown preset / invalid habitat |

## AI
`build_context` adds `pack["compare"]` when the question names two presets with a compare cue ("compare", "change",
"differ", "between", "vs", "versus") or `context_ids` has `eng:compare`: `{id: "eng:compare", a, b, inputs_diff, summary,
metrics: {M1: {id: "eng:compare:M1", ...MetricCompare}}}`. Citable: `eng:compare` and `eng:compare:<metric>` for the
metrics present. Intent `compare` (template). Cached question: "What changes between ISS and the lunar base?" (`lunar_base`).

## Web (FE)
`/compare?a=iss&b=lunar_base` (+ habitat query). `a`/`b` = preset id or `current` (the habitat bar values in the
URL); defaults `a=iss`, `b=current`. Two pickers; one row per metric: both sides on ONE shared axis per metric
(BandChart with two columns), regime and coverage chips, "no difference shown" when a side has no evidence; the
summary line on top. Stacks on phone. Nav item "Compare"; "Compare with…" link on `/bounds`. Offline: both sides
presets → computed from the bounds artifacts; a custom side → "Live API needed" state.

# Round 3 · S3 Uncertainty drivers addendum (see plan/15-round-3-features.md §S3, ADR-0008)

## Ownership (S3)
| Role | Owns |
|---|---|
| TL | `engine/uncertainty.py`, `artifacts/uncertainty/{preset}.json`, `tests/test_uncertainty.py`, ADR-0008 |
| AI | `drivers` field on `/bounds`, AI context + citation `eng:drivers:<metric>`, cached answer "Why is the lunar base band so wide?" |
| FE | stacked bar under each band on `/bounds`; the existing tornado moves under a "one-at-a-time view" disclosure |

## `engine/uncertainty.py` (TL)
```python
def drivers(metric, g_m_s2, p_psia, o2, u_cm_s, L_mm, co2=0, he=0, n=2000, seed=0, n_boot=500, **options) -> dict
def first_order_indices(inputs: dict[str, array], y, n_bins=10) -> dict[str, float]
```
`options` are passed to `bounds.predict` (fuel, droplet_mm, fuel_fraction). `co2`/`he` are used for M1/M2 only.
Not applicable (no evidence, or M4/M5): `{metric, label, citation, adr: "ADR-0008", applicable: false, reason}`.
Applicable (JSON-safe):
```
{metric, label, citation: "eng:drivers:M1", adr: "ADR-0008", applicable: true, kind, unit,
 estimate, band90: [lo, hi], band_width,                 # same estimate/band as bounds.predict
 model_band90: [lo, hi], model_band_width,               # unwidened (= ref_0g band)
 widen_factor, widen_factor_min, regime_fractions: {forced, mixed, buoyant},
 what_varies: {estimate: str, band: str},
 sources: [                                              # always these 7, in this order; shares sum to 1
   {id: "model_uncertainty", label, share, basis: "psi_data",               reaches_band: true, note},
   {id: "gravity_widening",  label, share, basis: "honesty_rule",           reaches_band: true, note},
   {id: "C_b" | "k" | "dT_over_T" | "L_mm", label, share, basis: "engineering_assumption", reaches_band, note},
   {id: "remainder", label: "Interactions / not split", share, basis: "engineering_assumption", reaches_band: true, note}],
 shares_sum,                                             # 1.0
 first_order: {C_b, k, dT_over_T, L_mm, sum, n_bins, output},   # S_i of the per-sample band width
 model_detail: {band90_unwidened, tests_within_gate, n_train, investigation_id,
                source: "bootstrap" | "quantile_spread", n_boot | null, boot_sd | null, note},
 lever: {source, share, basis, text,
         planner_candidate: {rank, metric, type, g_m_s2, p_psia, o2, u_cm_s, co2, distance} | null},
 method: str, n, seed, model_version}
```
Rules: `share` in [0, 1] except `remainder` ≥ −0.05; `k` is always 0 with `reaches_band: false` (k is not in Ri);
`lever.source` is never `remainder`; `planner_candidate` is the nearest same-metric item of `artifacts/planner.json`
within planner-kernel distance 2, else null.

## `artifacts/uncertainty/{preset}.json` (TL, `python -m engine.uncertainty`)
`{preset_id, habitat: {g_m_s2, p_psia, o2, u_cm_s, L_mm}, method, adr: "ADR-0008", metrics: {M1..M5: drivers(...)}}`
for the 6 presets (M4/M5 always `applicable: false`).

## API (AI)
`/bounds` response gains an **optional** field `drivers` = `drivers(metric, same habitat and options)` (omit or null
on error; never blocks the bounds answer). Offline: read `artifacts/uncertainty/{preset}.json`. Citation
`eng:drivers:<metric>`; answers must name the basis ("engineering assumption, not PSI data" for C_b/k/dT/T/L).

## Web (FE)
Stacked bar per covered metric, shares rounded to 5% (labels from `sources[].label`, a basis tag on each segment,
`remainder` shown as "not split"), screen-reader text listing the shares, the `lever.text` under it with a Planner
link when `planner_candidate` is not null, one-sentence method + link to ADR-0008. No bar when `applicable` is false.

# Round 3 · S2 Holdout addendum (see plan/15-round-3-features.md §S2, ADR-0009)

## Ownership (S2)
| Role | Owns |
|---|---|
| TL | `engine/holdout.py`, `artifacts/holdout.json`, `tests/test_holdout.py`, S2 section of `artifacts/validation_report.md` (`engine.validation.holdout_section`), ADR-0009; optional hooks `engine.models.fit_model(metric, train, n_boot, seed)`, `TrainingSet.subset(mask)`, `bounds.predict(..., model=)` |
| AI | `GET /holdout`, citations `eng:holdout` / `eng:holdout:<group id>` / `eng:holdout:saffire`, cached answer "How do you know it works?" |
| FE | `/trust` page "Can I trust it?" |

## `artifacts/holdout.json` (TL, `python -m engine.holdout`, ~1.5 min)
```
{artifact: "holdout", adr: "ADR-0009", citation: "eng:holdout", method, generated_at, runtime_s,
 settings: {n_boot, boot_seed, grouping: {o2_decimals: 3, p_atm_decimals: 2, diluent_decimals: 3, same_as, diluents_in_key},
            query: {g_m_s2: 0, u_cm_s: 10, L_mm: str, options: str, why: str}, group_band, interval, weak_below_groups: 10,
            max_groups: null},
 metrics: {M1|M2|M3: RESULT},                 # primary: one tested atmosphere at a time
 overall: OVERALL,
 wide_check: {scheme: "o2_band", what: str, metrics: {M1|M2|M3: RESULT}, overall: OVERALL},
 saffire_hindcast: {available, source, metric: "M4", headline, scores: {name: {hits, n, accuracy}}, caveat, citation}}

RESULT  = {metric, label, kind, investigation_id, scheme: "atmosphere" | "o2_band", hit_rule: str,
           units: [{id, n_tests, n_train_remaining, refit: bool}], groups: [GROUP], summary: SUMMARY}
GROUP   = {id: "M1-o2_0.210-p_1.01-co2_0.000-he_0.000" | "M3-o2_0.354-p_0.50", citation: "eng:holdout:<id>",
           metric, atmosphere: {o2, p_atm, p_psia, co2?, he?}, n_tests,
           psi_rows: [{record_id, investigation_id, source_file, source_row}],   # cleaned table data/clean/psi_tests.csv
           held_out_unit, status: "evaluated" | "skipped",
           # skipped: skip_reason, covered: null, hit: null
           covered: bool, nearest_remaining_distance, n_train_remaining, model_version,
           query: {g_m_s2, u_cm_s, L_mm, per_test_options: [...]},
           predicted: {estimate, band90: [lo, hi], shown_to_user: bool, note},   # band shown only if covered
           hit: bool, strict_hit: bool, gap, error,
           # M1/M3: observed: {positives, n, rate, interval90}, brier, brier_baseline, baseline_rate
           # M2:    observed: {n, median, min, max, values}, tests_inside_band}
SUMMARY = {metric, n_groups, n_tests, n_skipped, n_covered, n_not_covered,
           band_coverage, strict_coverage, gate_precision, no_evidence_justified: RATE,
           weak_test: bool,                      # fewer than 10 covered groups
           brier_covered, brier_baseline_covered (M1/M3) | tests_inside_band_covered: RATE (M2),
           worst_misses: [{id, atmosphere, n_tests, band90, observed, gap, error}] (≤5, largest gap first),
           largest_errors: [{id, n_tests, error, hit}] (≤5)}
RATE    = {k, n, rate | null, interval90: [lo, hi] | null}       # Wilson 90%
OVERALL = {n_groups, n_tests, n_covered, n_not_covered, n_skipped, band_coverage, gate_precision,
           no_evidence_justified: RATE, weak_test, target_coverage: 0.9}
```
`gate_precision` = covered groups whose band held (same count as `band_coverage` under the overlap rule).
`no_evidence_justified` = "no evidence" groups where the ungated band would have missed (k) out of all of them (n).
`gap` is in probability (M1/M3) or mm (M2).

## API (AI)
| Method | Path | Response |
|---|---|---|
| GET | `/holdout` | `artifacts/holdout.json` unchanged; 503 problem if missing or not valid JSON (as `/detection`) |

## Web (FE)
`/trust`: scorecard (primary band coverage with its interval and n, the strict rate next to it, pooled Brier /
single-diameter coverage, wide-check gate numbers, SAFFIRE hindcast with its caveat), "weak test" wherever
`weak_test` is true, the groups on the O₂ × pressure map (hit = filled, miss = hollow with a cross, not covered = grey,
skipped = not drawn but counted), a misses table naming `psi_rows`, and the hit rules (`hit_rule`) in plain words.
