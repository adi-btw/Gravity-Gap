# Graph Report - plan  (2026-11-14)

## Corpus Check
- Corpus is ~9,045 words - fits in a single context window. You may not need a graph.

## Summary
- 340 nodes · 1136 edges · 9 communities
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 97 edges (avg confidence: 0.87)
- Token cost: 234,386 input · 0 output

## Community Hubs (Navigation)
- Mission Framing and Objectives
- Data Pipeline and Provenance
- System Architecture and AI
- Foundation Tasks and Delivery
- Regime and Scaling Physics
- Bounds Models and Prediction
- API, Ledger and Data Export
- Frontend Build Epic
- Team, Schedule and Risk

## God Nodes (most connected - your core abstractions)
1. `12 Backlog` - 70 edges
2. `02 Data Pipeline` - 48 edges
3. `Gravity Gap Plan Overview` - 33 edges
4. `03 Physics Engine (E1, E2, E3)` - 33 edges
5. `06 Frontend and UX` - 32 edges
6. `07 API and Backend` - 31 edges
7. `AI: AI / Backend Engineer` - 29 edges
8. `01 Architecture` - 28 edges
9. `08 Testing and QA` - 28 edges
10. `FE: Frontend Engineer` - 27 edges

## Surprising Connections (you probably didn't know these)
- `Scientific honesty rule (order-of-magnitude scaling, labeled estimates)` --implements--> `Pillar: Honesty`  [INFERRED]
  03-physics-engine.md → 00-overview.md
- `Known limitations (scaling orders, thin low-pressure evidence, few solid tests)` --semantically_similar_to--> `Known data gaps shown as findings`  [INFERRED] [semantically similar]
  03-physics-engine.md → 02-data-pipeline.md
- `Prompt explain_bounds.v1` --references--> `F4 Bounds Panel`  [INFERRED]
  05-ai-layer.md → 04-features.md
- `Post-validator (numbers within 0.5%, citations resolve, retry then template fallback)` --semantically_similar_to--> `B5 E4 literature extractor with verbatim gate`  [INFERRED] [semantically similar]
  05-ai-layer.md → 12-backlog.md
- `RFC 7807 problem+json errors (extrapolation is not an error)` --semantically_similar_to--> `C9 Applicability gate`  [INFERRED] [semantically similar]
  07-api-backend.md → 12-backlog.md

## Hyperedges (group relationships)
- **Partial-gravity bridge physics chain (u_b -> Ri/u_eff -> bounds prediction)** — 03_physics_engine_buoyant_velocity, 03_physics_engine_richardson_number, 03_physics_engine_effective_flow_u_eff, 03_physics_engine_partial_g_prediction_pipeline, 03_physics_engine_applicability_gate [EXTRACTED 1.00]
- **Offline precompute pipeline P1->P2->P3/E1/E4->E2->E3/E5 -> artifacts** — 01_architecture_p1_ingest, 01_architecture_p2_cleaner, 01_architecture_p3_evidence_catalog, 01_architecture_e1_physics_engine, 01_architecture_e4_literature_extractor, 01_architecture_e2_bounds_models, 01_architecture_e3_test_planner, 01_architecture_e5_prediction_ledger, 01_architecture_versioned_artifacts [EXTRACTED 1.00]
- **AI grounding guardrails (context pack, prompt rules, structured output, post-validator, offline cache)** — 05_ai_layer_context_pack, 05_ai_layer_system_prompt_rules, 05_ai_layer_structured_output, 05_ai_layer_post_validator, 05_ai_layer_offline_answer_cache [EXTRACTED 1.00]
- **Backlog critical path** — 12_backlog_critical_path, 12_backlog_a1_repo_layout, 12_backlog_c1_physics_py, 12_backlog_c3_monte_carlo_sampler, 12_backlog_c5_flex_extinction_model, 12_backlog_c9_applicability_gate, 12_backlog_d4_bounds_endpoint, 12_backlog_g7_f4_bounds_panel, 12_backlog_h1_playwright_e2e, 12_backlog_h3_demo_rehearsal, 12_backlog_h5_space_apps_submission [EXTRACTED 1.00]
- **Offline demo resilience (AI cache, compose fallback, E2E offline)** — 10_risks_r4_ai_outage, 10_risks_r13_hosting_failure, 07_api_backend_ai_cache_json, 07_api_backend_deploy_docker_compose, 08_testing_qa_t7_e2e_demo_path, 12_backlog_e6a_offline_ai_cache [INFERRED 0.85]
- **Physics reference-case verification across Python and TS** — 08_testing_qa_t2_physics_reference_cases, 08_testing_qa_t3_physics_parity, 12_backlog_c2_reference_case_fixtures, 12_backlog_g3_physics_ts_port, 12_backlog_c1_physics_py [INFERRED 0.85]

## Communities (9 total, 0 thin omitted)

### Community 0 - "Mission Framing and Objectives"
Cohesion: 0.05
Nodes (64): Gravity Gap Plan Overview, Earth applications (optional challenge objective), Exploration atmosphere 10.2 psia / 26.5% O2, Gravity Gap (partial-gravity fire prediction engine), LUCI and FM2 (future partial-gravity sources), Lunar base / rover atmosphere 8.2 psia / 34% O2, 2026 NASA Space Apps Challenge (SI-powered fire safety dashboard), Out of scope (rockets, raw TB-scale imagery, full CFD, safety certification) (+56 more)

### Community 1 - "Data Pipeline and Provenance"
Cohesion: 0.07
Nodes (61): E4 Literature Extractor, P1 Ingest, P2 Cleaner (clean_psi_tables.py), Canonical schema (data/clean/README.md), artifacts/catalog.json (investigation record schema), PSI CC0-1.0 license and DOI citation requirement, CLEANING_REPORT.md, Cleaning rules: never invent values, flag every fix, keep source_file+source_row (+53 more)

### Community 2 - "System Architecture and AI"
Cohesion: 0.07
Nodes (44): S6: Every AI answer cited; zero uncited numeric claims, AI Layer (Claude API), API Backend (FastAPI), 01 Architecture, Runtime habitat state {g, pressure_psia, o2_pct, vent_cm_s, flame_size_mm}, Versioned hashed JSON artifacts (artifacts/*.json + MANIFEST.json), WEB Frontend (Next.js), Verbatim gate (value+quote must appear in PDF text) (+36 more)

### Community 3 - "Foundation Tasks and Delivery"
Cohesion: 0.20
Nodes (34): M6 Demo freeze (H44), TL: Tech Lead / Physics, R11 Low-pressure evidence thin, Space Apps submission package, A1 Create repo layout, A2 CI skeleton, A3 Env config + secrets, A4 Decisions log (+26 more)

### Community 4 - "Regime and Scaling Physics"
Cohesion: 0.11
Nodes (32): E1 Physics Engine (physics.py + TS port), web/lib/physics.ts (TypeScript physics port), G* = (g/g0)(P/P0)^2, Grashof scaling Gr ~ g P^2 L^3, O2 partial pressure p_O2 = X_O2 P, V1: Unit reference cases checked to 1%, F2 Flame Regime Calculator, F3 Pressure x Gravity Explorer (+24 more)

### Community 5 - "Bounds Models and Prediction"
Cohesion: 0.14
Nodes (28): E2 Bounds Models, CFI-G investigation, FLEX investigation (PSI-69), Applicability (honesty) gate: atmosphere distance > 2 returns extrapolation, artifacts/bounds/*.json, Buoyant velocity scale u_b = C_b sqrt(g L dT/T), 03 Physics Engine (E1, E2, E3), Effective flow mapping u_eff = sqrt(u_f^2 + (k u_b)^2) (bridge model) (+20 more)

### Community 6 - "API, Ledger and Data Export"
Cohesion: 0.18
Nodes (25): E5 Prediction Ledger, F8 Data Explorer and Export, Deploy: Render/Fly container, Vercel web, docker compose local, 07 API and Backend, FastAPI stateless service (api/main.py), GET /catalog/{id}, GET /data/export, GET /data/tests (+17 more)

### Community 7 - "Frontend Build Epic"
Cohesion: 0.35
Nodes (17): FE: Frontend Engineer, R8 Physics TS/Python drift, Epic G: Frontend, G10 F6 Planner page, G11 F8 Data Explorer + export, G12 About page (method, limitations, DOIs), G13 Accessibility pass (T8), G1 Next.js scaffold, tokens, themes (+9 more)

### Community 8 - "Team, Schedule and Risk"
Cohesion: 0.26
Nodes (10): M5: Flame existence vs coflow speed (SPICE empirical ranges), 48-hour parallel workstream schedule, 09 Team and Timeline, M0 Kickoff (H0-H2), M7 Submission (H46), PM hat (rotating, TL by default), 10 Risk Register, R10 Overclaiming safety (+2 more)

## Knowledge Gaps
- **10 isolated node(s):** `Test-point logs (e.g. 19304A1_TP.txt, ACME s-Flame)`, `NASA public specs (ventilation speeds, habitat atmospheres)`, `Design tokens: mission-control theme, gravity color coding`, `Accessibility and quality bar (WCAG 2.2 AA, data tables, keyboard, 375 px, <2.5 s load)`, `Per-panel error boundaries` (+5 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 14 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Gravity Gap Plan Overview` connect `Mission Framing and Objectives` to `Data Pipeline and Provenance`, `System Architecture and AI`, `Foundation Tasks and Delivery`, `Regime and Scaling Physics`, `Bounds Models and Prediction`, `API, Ledger and Data Export`, `Team, Schedule and Risk`?**
  _High betweenness centrality (0.220) - this node is a cross-community bridge._
- **What connects `Test-point logs (e.g. 19304A1_TP.txt, ACME s-Flame)`, `NASA public specs (ventilation speeds, habitat atmospheres)`, `Design tokens: mission-control theme, gravity color coding` to the rest of the system?**
  _10 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Mission Framing and Objectives` be split into smaller, more focused modules?**
  _Cohesion score 0.05413469735720375 - nodes in this community are weakly interconnected._
- **Why does `12 Backlog` connect `Foundation Tasks and Delivery` to `Mission Framing and Objectives`, `Data Pipeline and Provenance`, `System Architecture and AI`, `API, Ledger and Data Export`, `Frontend Build Epic`, `Team, Schedule and Risk`?**
  _High betweenness centrality (0.187) - this node is a cross-community bridge._
- **Should `Data Pipeline and Provenance` be split into smaller, more focused modules?**
  _Cohesion score 0.07139079851930195 - nodes in this community are weakly interconnected._
- **Why does `02 Data Pipeline` connect `Data Pipeline and Provenance` to `Mission Framing and Objectives`, `System Architecture and AI`, `Regime and Scaling Physics`, `Bounds Models and Prediction`?**
  _High betweenness centrality (0.157) - this node is a cross-community bridge._
- **Should `System Architecture and AI` be split into smaller, more focused modules?**
  _Cohesion score 0.07337662337662337 - nodes in this community are weakly interconnected._