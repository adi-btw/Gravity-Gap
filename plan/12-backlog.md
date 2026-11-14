# 12 · Backlog (follow this to build)

Back to [overview](00-overview.md). Roles are in [09-timeline-team.md](09-timeline-team.md). Estimates are ideal hours. **Depends on** lists task IDs that must be done first.

## Epic A: Foundation
| ID | Task | Role | Est | Depends on | Done when |
|---|---|---|---|---|---|
| A1 | Create repo layout (`engine/ api/ web/ tests/ artifacts/ ledger/`) | AI | 0.5 | — | Layout committed |
| A2 | CI skeleton: ruff, eslint, pytest, vitest | AI | 1 | A1 | CI runs on PR |
| A3 | Env config + secrets handling (Claude key) | AI | 0.5 | A1 | `.env.example`, no keys in git |
| A4 | Decisions log `plan/decisions.md` | TL | 0.25 | A1 | First ADR written |

## Epic B: Data (P1–P3, E4)
| ID | Task | Role | Est | Depends on | Done when |
|---|---|---|---|---|---|
| B1 | `scripts/fetch_psi.py` with sha256 manifest | DE | 2 | A1 | Re-run downloads nothing new |
| B2 | Move cleaner to `scripts/`, add T1 data-quality tests | DE | 1.5 | A2 | T1 green |
| B3 | `engine/catalog.py` → `catalog.json` (computed coverage ranges) | DE | 3 | B2 | 16 investigations in catalog |
| B4 | Lineage links (flight → reanalysis studies) in catalog | DE | 1 | B3 | FLEX shows PSI-117, PSI-142 |
| B5 | E4 literature extractor with verbatim gate | DE/AI | 4 | B3, C1 | `paper_values.json` candidates |
| B6 | Human review of paper values | DE | 2 | B5 | Accepted/rejected CSV |
| B7 | D1 BRE pressures; D2 FLEX rate units; D3 BASS-II flow units | DE | 2 | B5 | Flags resolved or documented |

## Epic C: Physics engine (E1–E3)
| ID | Task | Role | Est | Depends on | Done when |
|---|---|---|---|---|---|
| C1 | `engine/physics.py`: u_b, Ri, Gr ratio G*, p_O₂, u_eff | TL | 3 | A1 | T2 green |
| C2 | Reference-case fixtures (R1–R5) shared JSON | TL | 1 | C1 | Used by T2 and T3 |
| C3 | Monte Carlo sampler for C_b, k, ΔT/T, L | TL | 2 | C1 | Reproducible with seed |
| C4 | Regime grid artifact | TL | 1 | C3 | `regime_grid.json` |
| C5 | Metric M1 FLEX extinction model + bootstrap | TL | 3 | B2, C3 | AUC reported |
| C6 | Metric M2 extinction-diameter quantile model | TL | 2 | B2 | Interval coverage reported |
| C7 | Metric M3 CFI-G self-extinction model | TL | 2.5 | B2, C3 | AUC reported |
| C8 | Metric M4 SAFFIRE rule table + M5 SPICE flow windows | DE | 2 | B2 | Tables in artifacts |
| C9 | Applicability gate (atmosphere distance) | TL | 1.5 | C5, C7 | "extrapolation" path tested |
| C10 | Non-monotonic detector (u_eff near flammability peak) | TL | 2 | C3, B6 | Warning flag in output |
| C11 | Sensitivity (tornado) computation | TL | 1.5 | C5 | Included in bounds JSON |
| C12 | E3 Test Planner greedy ranking | TL | 3 | C9, C11 | `planner.json` top 10 |
| C13 | Validation report V2–V5 | TL | 3 | C5–C10 | `validation_report.md` |

## Epic D: API
| ID | Task | Role | Est | Depends on | Done when |
|---|---|---|---|---|---|
| D1 | FastAPI scaffold + manifest integrity check | AI | 1.5 | A2 | `/health` live |
| D2 | `/catalog`, `/catalog/{id}` | AI | 1 | B3, D1 | T5 passes |
| D3 | `/physics`, `/rank` | AI | 1.5 | C1, B3 | T5 passes |
| D4 | `/bounds` | AI | 2 | C9, C11 | T5 passes |
| D5 | `/planner`, `/ledger` GET/POST | AI | 1.5 | C12, F1 | T9 passes |
| D6 | `/data/tests`, `/data/export` with citation header | AI | 1.5 | B2 | Export includes DOIs |
| D7 | OpenAPI → TS types generation | AI | 0.5 | D2 | Types used in web |

## Epic E: AI layer
| ID | Task | Role | Est | Depends on | Done when |
|---|---|---|---|---|---|
| E1a | Context-pack builder | AI | 2 | B3, D4 | Unit tested |
| E2a | Prompts v1 (5 prompts) | AI | 2 | E1a | Versioned files |
| E3a | Post-validator (numbers + citations) + retry + fallback | AI | 3 | E2a | T6 groundedness 100% |
| E4a | `/ask` endpoint + rate limit | AI | 1 | E3a | T5 passes |
| E5a | Eval harness T6 + 30 scripted questions | AI | 2.5 | E3a | CI job |
| E6a | Offline AI cache for demo questions | AI | 1 | E5a | Works with network off |
| E7a | Investigation summaries + relevance scores (offline Opus run) | AI | 1.5 | E2a, B3 | Stored in catalog |

## Epic F: Ledger
| ID | Task | Role | Est | Depends on | Done when |
|---|---|---|---|---|---|
| F1 | `engine/ledger.py` append-only JSONL + SHA-256 | AI | 1.5 | A1 | T9 green |
| F2 | Seed ≥ 5 predictions (team review) | TL | 2 | D4, F1 | Committed to git |

## Epic G: Frontend
| ID | Task | Role | Est | Depends on | Done when |
|---|---|---|---|---|---|
| G1 | Next.js scaffold, tokens, themes, layout | FE | 2 | A1 | Builds in CI |
| G2 | HabitatBar + F0 presets + URL state | FE | 2 | G1 | Shareable links |
| G3 | `physics.ts` port + T3 parity | FE | 2 | C2 | T3 green |
| G4 | F2 Regime Calculator + map | FE | 3 | G2, G3 | <50 ms updates |
| G5 | F3 Pressure × Gravity heat map + caveat | FE | 2 | G3 | Shows G* 0.051 |
| G6 | F1 Spectrum Map + ranking list | FE | 4 | D3, G2 | Re-ranks on habitat change |
| G7 | F4 Bounds Panel (band chart, evidence, tornado, states) | FE | 5 | D4 | All states rendered |
| G8 | F7 Investigation Card + Ask drawer | FE | 4 | D2, E4a | Citations clickable |
| G9 | F5 Ledger page | FE | 1.5 | D5 | Hash verify works |
| G10 | F6 Planner page | FE | 2 | D5 | Rationales shown |
| G11 | F8 Data Explorer + export | FE | 3 | D6 | Filter + download |
| G12 | About page (method, limitations, DOIs) | FE | 1 | B3 | All DOIs listed |
| G13 | Accessibility pass (T8) | FE | 2 | G4–G11 | No serious violations |

## Epic H: Quality, deploy, demo
| ID | Task | Role | Est | Depends on | Done when |
|---|---|---|---|---|---|
| H1 | Playwright E2E demo path (online + offline) | AI | 3 | G4–G10, E6a | T7 green |
| H2 | Deploy API + web; docker compose fallback | AI | 2 | D1–D6, G1 | Public URL works |
| H3 | Demo rehearsal x3 + timing | PM | 2 | H1, F2 | Under 2 min |
| H4 | Video recording | FE | 1.5 | H3 | File exported |
| H5 | Space Apps submission | PM | 1.5 | H2, H4 | Confirmation received |

## Critical path
`A1 → C1 → C3 → C5 → C9 → D4 → G7 → H1 → H3 → H5`
Anything on this path slipping more than 2 h triggers the scope-cut order in [09-timeline-team.md](09-timeline-team.md).
