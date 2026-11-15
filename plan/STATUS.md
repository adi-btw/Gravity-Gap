# Project status

> ## Round 3 status (2026-11-15)
> Round 3 ([plan 15](15-round-3-features.md)) is complete: S4 `/compare`, S3 drivers on `/bounds`, S2 `/trust`,
> S1 `/briefing` (printable), S5 `/atmospheres` (Air map with sourced crew limits). The drivers lever and the AI's
> "What would narrow it" now name the same Planner test. Demo script updated (section 1b).

Back to [overview](00-overview.md). Owner: TL (PM hat). Snapshot: **2026-11-14, phase 3 in progress** (M5 → M7).
Backlog IDs from [12-backlog.md](12-backlog.md); commit hashes from `git log --oneline`. "Phase 3 (uncommitted)" means
the work exists in the working tree but is not yet committed by the team lead.

**Backlog: 58 tasks → 42 done · 10 partial · 6 not started.**

## Commits
| Hash | Commit |
|---|---|
| `d30557c` | Engineering plan and plan knowledge graph |
| `9820712` | PSI experimental tables, cleaning script, clean dataset (1,710 tests) |
| `9efe3b5` | Physics engine core (TL: C1–C4, A4) |
| `2eff35b` | FastAPI backend and CI (AI: A2, A3, D1–D3, T5) |
| `17e1282` | Web foundation and regime screens (FE: G1–G5) |
| `a6f1877` | PSI catalog, ranking, data-quality gates (DE: B1–B4, T1) |
| `056b35d` | M4/M5 rule models, gravity-aware ranking (DE: C8) |
| `b1fb7b0` | Prediction models, honesty gate, test planner (TL: C5–C13) |
| `385fe10` | Ledger, grounded AI layer, phase-2 API (AI: F1, F2, E1a–E6a, D4–D6) |
| `8be1f82` | Phase-2 screens (FE: G6–G12) |

## Backlog
### Epic A: Foundation
| ID | Status | Commit | Note |
|---|---|---|---|
| A1 | done | `9efe3b5`, `2eff35b` | `engine/ api/ web/ tests/ artifacts/ ledger/` in place |
| A2 | partial | `2eff35b` | CI runs pytest, eslint, vitest and the web build; **ruff is not in CI** |
| A3 | done | `2eff35b` | `.env.example`, `.env` git-ignored, no keys in git |
| A4 | done | `9efe3b5` | `plan/decisions.md` ADR-0001..0005 |

### Epic B: Data
| ID | Status | Commit | Note |
|---|---|---|---|
| B1 | done | `a6f1877` | `scripts/fetch_psi.py`, sha256 `data/raw_manifest.json`, idempotent |
| B2 | done | `9820712`, `a6f1877` | Cleaner in `scripts/`; T1 data-quality tests |
| B3 | done | `a6f1877` | `artifacts/catalog.json`: 26 records (24 combustion), computed condition ranges |
| B4 | done | `a6f1877` | FLEX → PSI-117, PSI-142; SPICE → PSI-60; BASS → PSI-62; SAME → PSI-115 |
| B5 | not started | — | No literature extractor / `paper_values.json` |
| B6 | not started | — | Depends on B5 |
| B7 | not started | — | Data flags documented in `data/clean/CLEANING_REPORT.md`, not resolved from papers |

### Epic C: Physics engine
| ID | Status | Commit | Note |
|---|---|---|---|
| C1 | done | `9efe3b5` | `engine/physics.py` (u_b, Ri, G*, p_O₂, u_eff, atmosphere distance) |
| C2 | done | `9efe3b5` | 35 shared fixture cases (Python + TS parity) |
| C3 | done | `9efe3b5` | Seeded Monte Carlo, N = 2,000 |
| C4 | done | `9efe3b5` | `artifacts/regime_grid.json` |
| C5 | done | `b1fb7b0` | M1 FLEX logistic + 500 bootstraps, AUC 0.824 |
| C6 | done | `b1fb7b0` | M2 quantile model, coverage 0.848 (target 0.90) reported |
| C7 | done | `b1fb7b0` | M3 CFI-G, AUC 0.622 (weak, flagged) |
| C8 | done | `056b35d` | M4 SAFFIRE-II rule table, M5 SPICE coflow windows (`artifacts/rules.json`) |
| C9 | done | `b1fb7b0` | Atmosphere-distance gate (> 2 → no number); M4/M5 have their own gate (`056b35d`) |
| C10 | partial | `056b35d` | Low-flow non-monotonic flag in M4/M5 rules; not calibrated from papers (B6 not done); M1–M3 always false by design (ADR-0005) |
| C11 | done | `b1fb7b0` | Tornado sensitivity in every bounds JSON |
| C12 | done | `b1fb7b0` | `artifacts/planner.json` top 10 + design implications |
| C13 | partial | `b1fb7b0` | V2 and V5 in `artifacts/validation_report.md`; V3 SAFFIRE hindcast done (`44a5af7`, `artifacts/validation_saffire.md`: 7/9 vs 3/9 baseline, not discriminative at n = 9); V4 not done (needs B5) |

### Epic D: API
| ID | Status | Commit | Note |
|---|---|---|---|
| D1 | done | `2eff35b`, `385fe10` | `/health` with manifest integrity check |
| D2 | done | `2eff35b` | `/catalog`, `/catalog/{id}` |
| D3 | done | `2eff35b` | `/physics`, `/rank` |
| D4 | done | `385fe10` | `/bounds` |
| D5 | done | `385fe10` | `/planner`, `/ledger` GET/POST (team token) |
| D6 | done | `385fe10` | `/data/tests`, `/data/export` with DOI header; `outcome=` filter in phase 3 (uncommitted) |
| D7 | not started | — | Web types are hand-written (`web/lib/types.ts`), not generated from OpenAPI |

### Epic E: AI layer
| ID | Status | Commit | Note |
|---|---|---|---|
| E1a | done | `385fe10` | `engine/ai/context.py` |
| E2a | partial | `385fe10` | 3 versioned prompts (`system`, `explain_bounds`, `summarize_investigation`), plan asked for 5 |
| E3a | done | `385fe10` | Validator (numbers ±0.5%, citations), 1 retry, template fallback |
| E4a | done | `385fe10` | `/ask`, 20/min rate limit |
| E5a | partial | `385fe10` | Validator and template-answer tests in `tests/test_ai.py`; no 30-question T6 eval harness as a CI job |
| E6a | done | `385fe10` | `artifacts/ai_cache.json`: 6 validated answers incl. a refusal |
| E7a | not started | — | Cards use PSI metadata text; no AI-generated summaries / relevance stored in catalog |

### Epic F: Ledger
| ID | Status | Commit | Note |
|---|---|---|---|
| F1 | done | `385fe10` | `engine/ledger.py`, SHA-256, `verify()`; CI append-only check in phase 3 (uncommitted `scripts/check_ledger_append_only.py`) |
| F2 | done | `385fe10` | GG-P0001..0005 seeded via `scripts/seed_ledger.py` and committed |

### Epic G: Frontend
| ID | Status | Commit | Note |
|---|---|---|---|
| G1 | done | `17e1282` | Next.js 15, tokens, dark/light themes |
| G2 | done | `17e1282` | HabitatBar, presets, URL state (`g` in m/s²) |
| G3 | done | `17e1282` | `web/lib/physics.ts`, T3 parity on all fixture cases |
| G4 | done | `17e1282` | F2 regime calculator + map |
| G5 | done | `17e1282` | F3 heat map, G* 0.051, caveat |
| G6 | done | `8be1f82` | F1 spectrum map + ranking with editable weights |
| G7 | done | `8be1f82` | F4 bounds panel: band chart, evidence, tornado, extrapolation and non-monotonic states |
| G8 | done | `8be1f82` | F7 cards (26, pre-rendered) + Ask drawer |
| G9 | done | `8be1f82` | F5 ledger, in-browser hash verify (5/5) |
| G10 | done | `8be1f82` | F6 planner page |
| G11 | done | `8be1f82` | F8 data explorer + CSV/JSON export |
| G12 | done | `8be1f82` | About page, all DOIs |
| G13 | partial | phase 3 (uncommitted) | axe-core a11y spec in `web/e2e/a11y.spec.ts`; FE in progress |

### Epic H: Quality, deploy, demo
| ID | Status | Commit | Note |
|---|---|---|---|
| H1 | partial | phase 3 (uncommitted) | `web/e2e/` demo, offline and a11y specs + Playwright config; FE in progress |
| H2 | partial | phase 3 (uncommitted) | `Dockerfile.api`, `web.Dockerfile`, `docker-compose.yml`, `render.yaml`, `docs/DEPLOY.md`; no public URL yet |
| H3 | partial | phase 3 (uncommitted) | `docs/DEMO_SCRIPT.md` + `plan/11-demo-pitch.md` (lunar base, offline path, 30 s version); 3 timed rehearsals not yet run |
| H4 | not started | — | FE recording into `docs/media/` from the E2E run |
| H5 | partial | phase 3 (uncommitted) | `docs/SUBMISSION.md` draft; human checklist not executed |

## Milestones
| ID | Milestone | Status | Evidence |
|---|---|---|---|
| M0 | Kickoff | done | `d30557c` plan; CI `2eff35b` |
| M1 | Data foundation | done | `9820712`, `a6f1877` (catalog + clean data + T1) |
| M2 | Physics core | done | `9efe3b5` (T2), `17e1282` (T3, F2/F3) |
| M3 | Prediction core | done | `b1fb7b0` (M1–M3, gate), `385fe10` (`/bounds`), `8be1f82` (F4) |
| M4 | Intelligence | mostly done | AI layer + F7 done (`385fe10`, `8be1f82`); T6 30-question eval not built (E5a partial) |
| M5 | Full product | in progress | F5, F6, F8 done (`8be1f82`); E2E T7 in progress (H1) |
| M6 | Demo freeze | in progress | Ledger seeded and committed (`385fe10`); offline E2E and video pending (H1, H4) |
| M7 | Submission | not started | `docs/SUBMISSION.md` draft; form not submitted |

## Success criteria
| ID | Criterion | Status | Evidence |
|---|---|---|---|
| S1 | Live demo end to end, offline-capable, under 2 min | partial | Offline fallbacks implemented (`8be1f82`; web/README "Offline behaviour"); script in `docs/DEMO_SCRIPT.md`; offline E2E (H1) and timed rehearsals (H3) pending |
| S2 | ≥ 10 PSI investigations; all 1,710 clean tests loaded | met | `artifacts/catalog.json` 26 records (24 combustion); `data/clean/psi_tests.csv` 1,710 tests from 10 investigations (`CLEANING_REPORT.md`) |
| S3 | Regime calculator and P × g explorer match reference cases within 1% | met | 35 fixture cases in `tests/fixtures/physics_reference.json`, pytest (T2) and vitest (T3) green; G*(Moon, 8.2 psia) = 0.0514 |
| S4 | Bounds for ≥ 3 metrics with uncertainty bands | met | M1–M5 in `artifacts/bounds/` (30 files); M1, M2, M3 have bands; honesty gate returns no number where untested |
| S5 | ≥ 5 dated, hashed predictions committed to git | met | GG-P0001..0005 in `ledger/predictions.jsonl`, committed in `385fe10`; 5/5 verify in browser |
| S6 | Every AI answer cited; zero uncited numbers in eval set | partial | Validator rejects uncited numbers; 6 cached answers all validated (`tests/test_ai.py`); the 30-question eval set (E5a) does not exist yet |
| S7 | Space Apps submission complete | not met | Draft in `docs/SUBMISSION.md`; checklist pending |

Test counts: pytest **331 passed** (full suite, working tree, 2026-11-14); vitest 81 at `8be1f82`.

## Remaining work (priority order)
1. **H1/G13** FE: finish Playwright E2E (online + offline) and a11y pass; commit.
2. **C13/V3** DE: SAFFIRE-II hindcast → `artifacts/validation_saffire.md`; then paste its numbers into `docs/SUBMISSION.md` and the judge Q&A.
3. **H2** AI: deploy API + web, get a public URL, fill links in `docs/SUBMISSION.md`.
4. **Team lead integration:** commit phase-3 work; rebuild artifacts in order (engine artifacts → `python -m engine.ai.answer --build-cache` → `python scripts/build_manifest.py`); check `/health` `manifest_ok: true`.
5. **H3** three timed rehearsals (one offline); fill the log in `docs/DEMO_SCRIPT.md`.
6. **H4** FE: record the demo video into `docs/media/`.
7. **H5** run the human checklist in `docs/SUBMISSION.md` (verify Space Apps rules first).
8. Nice to have if time: ruff in CI (A2), 30-question eval job (E5a, closes S6), OpenAPI → TS types (D7).
9. Cut (out of time budget): B5–B7 literature extraction, V4, E7a AI summaries.

## Open issues / risks
- **Artifacts may be rebuilt** at integration: re-check every number in `docs/DEMO_SCRIPT.md`, `docs/SUBMISSION.md` and `plan/11-demo-pitch.md` afterwards.
- Hindcast committed (`44a5af7`); its numbers are now quoted in SUBMISSION and the judge Q&A.
- **Rover vs base:** the old pitch used the rover as the MIXED example; it is buoyant (Ri ≈ 25.9). All docs now use the lunar base.
- **Old pitch text** said "1,700 real ISS tests"; corrected to 1,710 PSI tests (SAFFIRE flew on Cygnus).
- **`/explore` ranking and `/data`** need the live API; kept out of the timed demo path.
- **Space Apps rules** (video length, AI disclosure, live-link requirement) not yet verified on the event site.
