# NASA Hackathon 2026: Gravity Gap

**Gravity Gap** is a partial-gravity fire prediction engine and dashboard for the 2026 NASA Space Apps Challenge
(SI-powered dashboard for microgravity combustion and fire safety).

> NASA has fire data from space and from Earth, but none from the Moon. Gravity Gap uses physics and 1,700 real ISS tests
> to predict fire behavior where no one has tested, shows how sure it is, and tells NASA what to test next.

## The plan
Start at **[plan/00-overview.md](plan/00-overview.md)**. Every other plan file links from there.

| # | File | What it covers |
|---|---|---|
| 00 | [Overview](plan/00-overview.md) | Problem, objective mapping, features, success criteria, scope |
| 01 | [Architecture](plan/01-architecture.md) | Components, data flow, tech stack, repo layout |
| 02 | [Data pipeline](plan/02-data-pipeline.md) | PSI sources, cleaning, catalog, literature extraction, data gaps |
| 03 | [Physics engine](plan/03-physics-engine.md) | Buoyancy, Richardson, Grashof (P²g) scaling, effective-flow bridge, bounds models, planner, validation |
| 04 | [Features](plan/04-features.md) | F0–F8 specs with acceptance criteria |
| 05 | [AI layer](plan/05-ai-layer.md) | Claude grounding, citations, post-validator, evals |
| 06 | [Frontend and UX](plan/06-frontend-ux.md) | Screens, flows, design system, accessibility |
| 07 | [API and backend](plan/07-api-backend.md) | Endpoints, contracts, artifacts, deploy |
| 08 | [Testing and QA](plan/08-testing-qa.md) | Test suites T1–T9, reference cases, CI |
| 09 | [Team and timeline](plan/09-timeline-team.md) | Roles, milestones, 48-hour schedule, cut order |
| 10 | [Risks](plan/10-risks.md) | Risk register R1–R13 |
| 11 | [Demo and pitch](plan/11-demo-pitch.md) | 2-minute demo script, submission, judge Q&A |
| 12 | [Backlog](plan/12-backlog.md) | Every task with owner, estimate, dependencies, critical path |

## Plan knowledge graph
Built with [graphify](https://github.com/safishamsi/graphify) from the `plan/` folder:
- `graphify-out/graph.html`: interactive graph (download and open in a browser)
- `graphify-out/GRAPH_REPORT.md`: communities, hub nodes, suggested questions
- `graphify-out/graph.json`: raw graph data (GraphRAG-ready)

## Data
Built on NASA Physical Sciences Informatics (PSI) combustion data (CC0-1.0). Each dataset is cited by its DOI in the plan and in the app.
