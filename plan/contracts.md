# Team Contracts (build phase 1)

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
`rank(catalog: list[dict], g_m_s2, p_psia, o2, u_cm_s, weights: dict | None = None) -> list[dict]`, each item `{id, acronym, score, parts{atmosphere, pillar, fuel_realism, outcomes, n_tests}}`, sorted by descending score. Non-combustion records (`is_combustion: false`) are excluded. Default weights `{atmosphere:0.35, pillar:0.2, fuel_realism:0.2, outcomes:0.15, n_tests:0.1}`.

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
