# 09 · Team and Timeline

Back to [overview](00-overview.md). Task IDs reference [12-backlog.md](12-backlog.md).

## 1. Roles (team of 4; with fewer people, merge roles as noted)
| Role | Owns | Merge if short-staffed |
|---|---|---|
| **TL: Tech Lead / Physics** | E1, E2, E3, validation, architecture decisions | — |
| **DE: Data Engineer** | P1, P3, E4, data quality, F8 | merge with TL |
| **FE: Frontend Engineer** | WEB, F0–F8 UI, design system, a11y | — |
| **AI: AI / Backend Engineer** | API, AI layer, ledger, CI, deploy | merge with FE |
| **PM hat (rotating, TL by default)** | Scope, demo script, submission, judging story | — |

## 2. Milestones
| ID | Milestone | Exit criteria | Target (hour) |
|---|---|---|---|
| M0 | Kickoff | Plan accepted; repo, CI skeleton, env keys | H0–H2 |
| M1 | Data foundation | Catalog + clean data + T1 green | H8 |
| M2 | Physics core | E1 + T2/T3 green; F2/F3 interactive | H16 |
| M3 | Prediction core | E2 metrics M1–M3 + `/bounds` + F4 | H26 |
| M4 | Intelligence | AI layer + F7 + evals T6 passing | H32 |
| M5 | Full product | F5, F6, F8 + E2E T7 green | H40 |
| M6 | Demo freeze | Ledger seeded and committed; offline mode verified; video recorded | H44 |
| M7 | Submission | Space Apps form submitted with links | H46 (2 h buffer) |

## 3. 48-hour schedule (parallel workstreams)
| Hours | TL (Physics) | DE (Data) | FE (Frontend) | AI (Backend/AI) |
|---|---|---|---|---|
| 0–2 | Kickoff, freeze scope | Repo layout, move cleaner | Next.js scaffold, design tokens | FastAPI scaffold, CI |
| 2–8 | `physics.py` + reference cases | Catalog builder, fetch script, data gates | HabitatBar, F0, routing | `/catalog`, `/physics`, OpenAPI → TS types |
| 8–16 | u_eff Monte Carlo, regime grid | Literature extractor (E4) runs | F2 regime map, F3 heat map | AI context pack + validator |
| 16–26 | Bounds models M1–M3, applicability gate | Human review of paper values; D1–D3 | F1 spectrum map + ranking UI | `/bounds`, `/rank`, AI prompts v1 |
| 26–32 | Planner E3, sensitivity | F8 data explorer backend | F4 Bounds panel | `/ask`, evals T6, cache |
| 32–40 | Validation V2–V5 report | M4/M5 rule table (SAFFIRE) | F5, F6, F7, F8 UI | Ledger E5, T9, deploy |
| 40–44 | Seed ledger predictions | Citations / About page | Polish, a11y T8 | E2E T7, offline mode |
| 44–48 | Demo rehearsal x3 | Submission text | Video capture | Submission + buffer |

## 4. Working agreements
- Trunk-based: short branches, PR review by one teammate, CI green to merge.
- Daily-standup equivalent every 6 hours (10 minutes): done, next, blocked.
- **Scope cut order** if behind (cut from the bottom): F8 scatter builder → F6 design implications → M4/M5 metrics → mobile layout → light theme. **Never cut:** the honesty gate, citations, the offline demo mode.
- Decisions are logged in `/plan/decisions.md` (ADR-lite).
