# 10 · Risk Register

Back to [overview](00-overview.md).

| ID | Risk | Likelihood | Impact | Mitigation | Owner | Linked |
|---|---|---|---|---|---|---|
| R1 | Scaling-law predictions judged "made up" | Med | High | Every formula cited and shown; uncertainty bands; SAFFIRE hindcast (V3); "estimate" labels | TL | [03](03-physics-engine.md) |
| R2 | Non-monotonic flammability makes the "bounds" framing wrong | Med | High | Effective-flow bridge + explicit non-monotonic detection and warning in F4 | TL | [03](03-physics-engine.md) §2.4 |
| R3 | Sparse solid-material data (SAFFIRE n = 9) | High | Med | Rule table, not ML; show n on screen; lean on BASS literature via E4 | DE | [02](02-data-pipeline.md) |
| R4 | AI API outage or rate limit during the demo | Med | High | Pre-generated AI cache + template fallback; offline mode tested (T7) | AI | [05](05-ai-layer.md) |
| R5 | AI hallucinates numbers | Med | High | Deterministic post-validator + retry + template fallback; T6 evals | AI | [05](05-ai-layer.md) |
| R6 | Literature extraction yields wrong values | Med | Med | Verbatim gate + human review before any value feeds a model | DE | [02](02-data-pipeline.md) |
| R7 | Scope creep (too many features) | High | High | Cut order in [09](09-timeline-team.md); M3 is the must-have core | PM | [09](09-timeline-team.md) |
| R8 | Physics TS/Python drift | Low | Med | Shared fixtures parity test T3 | TL/FE | [08](08-testing-qa.md) |
| R9 | PSI API changes or signed URL expiry | Low | Med | Raw CSVs already committed locally with sha256 manifest | DE | [02](02-data-pipeline.md) |
| R10 | Overclaiming safety | Low | High | About-page limitations; "decision support, not certification" banner | PM | [00](00-overview.md) |
| R11 | Low-pressure evidence thin (most data near 1 atm) | High | Med | Applicability gate returns "extrapolation"; Planner prioritizes low-P tests | TL | [03](03-physics-engine.md) |
| R12 | Team smaller than 4 | Med | Med | Role merges defined; cut order | PM | [09](09-timeline-team.md) |
| R13 | Hosting failure at judging time | Low | High | Local `docker compose` fallback + recorded video | AI | [07](07-api-backend.md) |
