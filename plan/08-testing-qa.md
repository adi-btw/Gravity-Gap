# 08 · Testing and QA

Back to [overview](00-overview.md). It checks [02](02-data-pipeline.md), [03](03-physics-engine.md), [05](05-ai-layer.md), [06](06-frontend-ux.md) and [07](07-api-backend.md).

## Test suites
| ID | Suite | Tool | What it proves | Gate |
|---|---|---|---|---|
| T1 | Data quality | pytest | Cleaner gates: ranges, gas sums, unique IDs, row counts, flags present | CI blocks merge |
| T2 | Physics reference cases | pytest | u_b, Ri, G* and u_eff match hand-calculated values within 1% (V1) | CI blocks merge |
| T3 | Physics parity | pytest + vitest (shared JSON fixtures) | The TS port equals Python to 1e-9 relative | CI blocks merge |
| T4 | Model validation | pytest (reports) | V2 cross-investigation AUC/calibration and V3 SAFFIRE hindcast; publishes `validation_report.md` | Report required; no threshold block |
| T5 | API contract | pytest + schemathesis | Endpoints match OpenAPI; the extrapolation path returns `applicable:false` | CI blocks merge |
| T6 | AI evals | custom harness | Groundedness, citations, refusals, extraction precision ([05-ai-layer.md](05-ai-layer.md) §5) | Runs on prompt or model change |
| T7 | E2E demo path | Playwright | The scripted judge flow works end to end in under 2 min, online and offline modes | Required before the demo freeze |
| T8 | Accessibility | axe-core in Playwright | No serious or critical violations | Required before the demo freeze |
| T9 | Ledger integrity | pytest | `predictions.jsonl` is append-only; hashes recompute | CI blocks merge |

## Reference cases (T2 seed)
| Case | Inputs | Expected |
|---|---|---|
| R1 | g = 9.81, L = 10 mm, ΔT/T = 4, C_b = 1 | u_b ≈ 62.6 cm/s |
| R2 | g = 1.62, same | u_b ≈ 25.5 cm/s |
| R3 | Moon, 8.2 psia | G* ≈ 0.0513 (0.165 × 0.5578²) |
| R4 | u_f = 10, u_b = 25.5, k = 1 | u_eff ≈ 27.4 cm/s; Ri ≈ 6.5 → mixed |
| R5 | g = 0, u_f = 10 | Ri = 0 → forced; u_eff = 10 |

(Values are recomputed and confirmed in T2 before freezing.)

## CI pipeline (GitHub Actions)
`lint (ruff, eslint) → T1 → T2 → T3 → T5 → T9 → build artifacts → T4 report → web build → T7/T8 (on main)`

## Manual QA checklist before the demo
- [ ] Every preset habitat renders every panel without errors.
- [ ] Offline mode: disconnect the network and run the full demo script.
- [ ] Every chart hover shows evidence IDs.
- [ ] The About page lists every DOI used.
