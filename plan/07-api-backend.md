# 07 · API and Backend

Back to [overview](00-overview.md). Serves [06-frontend-ux.md](06-frontend-ux.md) and wraps the engine in [03-physics-engine.md](03-physics-engine.md).

## 1. Service
FastAPI app (`/api/main.py`), stateless. It loads `artifacts/` at startup and checks `artifacts/MANIFEST.json` hashes; startup fails if they don't match.

## 2. Endpoints
| Method | Path | Request | Response | Used by |
|---|---|---|---|---|
| GET | `/health` | – | `{status, artifact_version, model_version}` | Ops |
| GET | `/catalog` | – | List of investigation records (P3) | F1, F7 |
| GET | `/catalog/{id}` | – | One record + computed condition coverage + lineage | F7 |
| POST | `/physics` | `{g, p_psia, o2, u_cm_s, L_mm}` | `{u_b, Ri, regime, G_star, p_o2, u_eff_samples_summary}` | F2, F3 (server check) |
| POST | `/rank` | habitat state + weights | Ranked investigations with score parts | F1 |
| POST | `/bounds` | habitat state + `metric` | `{estimate, band90, ref_0g, ref_1g, regime_mix, evidence[], applicable, nonmonotonic_flag, sensitivity[]}` | F4 |
| GET | `/planner` | `?habitat=` | Ranked candidate tests | F6 |
| GET | `/ledger` | – | Predictions + verification hashes | F5 |
| POST | `/ledger` | Prediction draft (team-only token) | Created record + hash | F5 (team) |
| POST | `/ask` | `{question, habitat, context_ids[]}` | `{answer_markdown, citations[], validated: bool}` | F7 |
| GET | `/data/tests` | Filters | Paged rows of `psi_tests.csv` | F8 |
| GET | `/data/export` | Filters + format | CSV/JSON + citation header | F8 |

## 3. Contracts
- Pydantic models in `/api/schemas.py`; the OpenAPI JSON is generated, and the TS types are generated from it (`openapi-typescript`) so web and API can't drift.
- Errors: RFC 7807 problem+json. An extrapolation is **not** an error: it is `applicable: false` with a reason.

## 4. Build artifacts (`make artifacts`)
| Artifact | Producer | Consumer |
|---|---|---|
| `catalog.json` | P3 | `/catalog`, `/rank`, AI context |
| `regime_grid.json` | E1 | F2 static fallback |
| `bounds/{habitat}_{metric}.json` | E2 | F4 static fallback |
| `planner.json` | E3 | F6 |
| `paper_values.json` | E4 (+ human review) | E2, F7 |
| `ai_cache.json` | AI layer | Offline demo |
| `MANIFEST.json` | build | API integrity check, ledger hashes |

## 5. Security and operations
- The `/ask` and `/ledger` POST endpoints are rate-limited; the ledger POST needs a team token from env.
- CORS is limited to the web origin.
- Logs: structured JSON, no PII.
- Deploy: a container on Render/Fly; the web app on Vercel; one-command local run with `docker compose up`.
