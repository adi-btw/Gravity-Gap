# 01 · Architecture

Back to [overview](00-overview.md).

## 1. Architecture principles
- **Precompute heavy, serve light.** Model fitting, uncertainty sampling and literature extraction run offline in Python and produce versioned JSON artifacts. The web app reads those artifacts, so the demo never depends on a live model fit.
- **One physics source of truth.** Physics formulas live in `engine/physics.py`. A TypeScript port (`web/lib/physics.ts`) gives instant slider feedback, and parity tests ([08-testing-qa.md](08-testing-qa.md) T3) keep the two identical.
- **Provenance everywhere.** Every value the UI shows carries `record_id` or `citation_id` back to [02-data-pipeline.md](02-data-pipeline.md).
- **AI is an explainer, not a calculator.** Claude reads engine outputs and evidence and explains them. It never produces numbers itself ([05-ai-layer.md](05-ai-layer.md)).
- **Offline demo mode.** If the network or the AI API fails, cached AI answers and static artifacts keep the demo running (risk R4 in [10-risks.md](10-risks.md)).

## 2. System diagram
```
 PSI website / API ──► [P1 Ingest] ──► data/psi_experimental_tables/*.csv
                           │
 PSI metadata zips ────────┤
 Linked papers (PDF) ──────┤
                           ▼
                      [P2 Clean]  scripts/clean_psi_tables.py   (DONE)
                           │
                           ▼
              data/clean/psi_tests.csv, psi_saffire_ug_vs_1g.csv, psi_test_day_summaries.csv
                           │
          ┌────────────────┼──────────────────────────┐
          ▼                ▼                          ▼
 [P3 Evidence Catalog]  [E1 Physics Engine]    [E4 Literature Extractor]
 investigations.json    regime, scaling,       paper_values.json (verbatim-checked)
                        u_eff mapping
          │                │                          │
          └────────► [E2 Bounds Models] ◄─────────────┘
                           │  fits + Monte Carlo uncertainty
                           ▼
                    [E3 Planner] [E5 Ledger]
                           │
                           ▼
                 artifacts/*.json  (versioned, hashed)
                           │
              ┌────────────┴─────────────┐
              ▼                          ▼
       [API] FastAPI (thin)        [WEB] Next.js app
       /physics /bounds /ask       F0–F8 screens, Plotly charts
              │
              ▼
       [AI] Claude API (grounded explainer, citations)
```

## 3. Components
| ID | Component | Language | Responsibility | Plan link |
|---|---|---|---|---|
| P1 | Ingest | Python | Download PSI experimental tables + metadata through the PSI API | [02](02-data-pipeline.md) |
| P2 | Cleaner | Python | Tidy, unit-normalized, flagged tests (already built) | [02](02-data-pipeline.md) |
| P3 | Evidence Catalog | Python | One JSON record per investigation: metadata, hardware, conditions covered, tags | [02](02-data-pipeline.md) |
| E1 | Physics Engine | Python + TS port | Buoyant velocity, Richardson number, Grashof scaling, effective flow | [03](03-physics-engine.md) |
| E2 | Bounds Models | Python | Response-metric fits with uncertainty; partial-g predictions | [03](03-physics-engine.md) |
| E3 | Test Planner | Python | Ranks candidate experiments by uncertainty reduction | [03](03-physics-engine.md) |
| E4 | Literature Extractor | Python + Claude | Pulls numbers from linked papers; verbatim check | [02](02-data-pipeline.md), [05](05-ai-layer.md) |
| E5 | Prediction Ledger | Python + git | Freezes and hashes predictions | [04](04-features.md) F5 |
| API | Backend | FastAPI | Serves artifacts, runs on-demand bounds queries, proxies AI | [07](07-api-backend.md) |
| WEB | Frontend | Next.js + TS | All screens | [06](06-frontend-ux.md) |
| AI | AI Layer | Claude API | Grounded explanations, Q&A, investigation summaries | [05](05-ai-layer.md) |

## 4. Tech stack (decisions)
| Concern | Choice | Why | Alternative rejected |
|---|---|---|---|
| Data and modeling | Python 3.13, pandas, numpy, scipy, scikit-learn | Already used by the cleaner; team familiarity | R (team skill) |
| Uncertainty | Monte Carlo + bootstrap (numpy) | Simple, explainable, fast enough offline | Full Bayesian (PyMC): too slow to build in 48 h |
| Backend | FastAPI | Typed, fast, shares the Python engine | Flask (no typing), Node-only (would duplicate physics) |
| Frontend | Next.js 15 (App Router) + TypeScript + Tailwind | Fast to build, static export possible | Streamlit: too limited for the UX bar |
| Charts | Plotly.js (react-plotly) | Scientific charts, hover, bands | D3 (too slow to hand-build) |
| AI | Claude API (latest Sonnet-class model, e.g. `claude-sonnet-5-5`; Opus for offline extraction) | Strong grounded reasoning, citations | n/a |
| Hosting | Vercel (web) + Render/Fly (API), or static export + serverless function | Free tier, quick | Self-hosting |
| Repo and CI | GitHub, GitHub Actions | Ledger timestamps via commits | n/a |

## 5. Repository layout (target)
```
/plan/                    this plan (graph built from it)
/scripts/                 ingest + clean (P1, P2)
/engine/                  physics.py, bounds.py, planner.py, ledger.py, catalog.py, literature.py
/artifacts/               generated JSON (regime_grid, bounds, predictions, catalog) + MANIFEST.json with hashes
/api/                     FastAPI app
/web/                     Next.js app
/tests/                   pytest + vitest + playwright
/data/psi_experimental_tables/  raw downloads (CC0)
/data/clean/              cleaned outputs
/ledger/                  frozen predictions (append-only)
```

## 6. Data flow at runtime
1. The user picks a habitat in F0. The web state holds `{g, pressure_psia, o2_pct, vent_cm_s, flame_size_mm}`.
2. F2 and F3 compute instantly in the browser (TS physics port).
3. F4 Bounds asks the API (`POST /bounds`) or reads precomputed grid artifacts. The response has the prediction, the interval and the evidence `record_id`s.
4. F7 "Explain" sends the engine outputs and evidence snippets to `/ask`. The answer comes back from Claude with citations, and the validator checks them before display.
