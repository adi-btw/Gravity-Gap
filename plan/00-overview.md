# Gravity Gap: Plan Overview

**Project:** Gravity Gap, a partial-gravity fire prediction engine and dashboard
**Event:** 2026 NASA Space Apps Challenge, the "SI-powered fire safety dashboard" challenge
**Plan owner:** the whole team. This is the source of truth; every other plan file links back here.

## 1. Problem statement
NASA has decades of combustion data from **microgravity** (ISS, Cygnus) and from **normal gravity** (Earth labs).
Crewed habitats are being designed now for the **Moon (0.165 g)** and **Mars (0.38 g)**, at **reduced pressure and raised oxygen**:
- 10.2 psia / 26.5% O₂ (exploration atmosphere)
- 8.2 psia / 34% O₂ (lunar base and pressurized rover)

The PSI database holds **no partial-gravity combustion data**. The challenge brief confirms this and names LUCI and FM2 as future sources.

**Gravity Gap answers one question:**
> "For this habitat (gravity, pressure, oxygen, ventilation), which existing experiments still apply, how far can we trust them, what do they predict, and which test should NASA run next?"

## 2. Mapping to the challenge objectives
| Challenge requirement | Where Gravity Gap delivers it |
|---|---|
| SI-powered, web-based dashboard | The whole app; AI layer in [05-ai-layer.md](05-ai-layer.md) |
| Summarizes investigations | Gravity Spectrum Map + Investigation Cards ([04-features.md](04-features.md) F1, F7) |
| Ranks investigations | Relevance ranking per habitat and gravity level (F1) |
| Interprets findings | Regime Calculator, Bounds Panel, AI explanations (F2–F4, F7) |
| Goal 1: relevance to spacecraft, stations, lunar/Mars bases, rovers | Habitat presets drive every view (F0) |
| Goal 2: data that supports predictive modeling | Clean dataset + Bounds models + CSV/JSON export ([02-data-pipeline.md](02-data-pipeline.md), F4, F8) |
| Goal 3: next-gen fire safety controls and equipment | Test Planner + design implications, e.g. ventilation settings (F6) |
| Partial-gravity consideration in the brief | The core of the product ([03-physics-engine.md](03-physics-engine.md)) |
| Elevated O₂ and reduced pressure in the brief | Atmosphere axis in every model; BRE and CFI-G evidence |
| Earth applications (optional) | Earth-spinoff panel on investigation cards (F7) |

## 3. Product pillars
1. **Evidence:** every number traces to a PSI dataset row or a cited paper.
2. **Physics:** physics scaling bridges 0 g and 1 g. It is never a black-box guess.
3. **Honesty:** uncertainty is always shown, and gaps are shown as findings.
4. **Actionable:** the output is a prediction or a test plan, not just a chart.

## 4. Features (detail in [04-features.md](04-features.md))
- F0 Habitat Selector
- F1 Gravity Spectrum Map
- F2 Flame Regime Calculator
- F3 Pressure × Gravity Explorer
- F4 Bounds Panel
- F5 Prediction Ledger
- F6 Test Planner
- F7 Investigation Cards + AI Assistant
- F8 Data Explorer and Export

## 5. Success criteria (definition of done for the hackathon)
- S1: The live demo runs end to end, offline-capable, in under 2 minutes.
- S2: At least 10 PSI investigations are integrated; all 1,710 clean tests are loaded.
- S3: The Regime Calculator and Pressure × Gravity Explorer match hand-calculated reference cases within 1%.
- S4: The Bounds Panel shows predictions with uncertainty bands for at least 3 response metrics.
- S5: The Prediction Ledger holds at least 5 dated, hashed predictions for LUCI and FM2-type tests, committed to git.
- S6: Every AI answer carries citations; there are zero uncited numeric claims in the evaluation set.
- S7: Space Apps submission complete: project page, demo video or slides, repo link.

## 6. Out of scope
- Rocket and propellant combustion (excluded by the brief).
- Downloading or processing raw image and video data (TB-scale). It is a stretch goal only.
- Full CFD simulation. We use scaling laws and data-driven fits.
- Claims of certified safety. The tool is decision support for research prioritization.

## 7. Plan map
| File | Content |
|---|---|
| [01-architecture.md](01-architecture.md) | System architecture, components, tech stack |
| [02-data-pipeline.md](02-data-pipeline.md) | Ingestion, cleaning, schema, provenance, literature extraction |
| [03-physics-engine.md](03-physics-engine.md) | Regime physics, scaling, bounds model, uncertainty, validation |
| [04-features.md](04-features.md) | Feature specs F0–F8 with acceptance criteria |
| [05-ai-layer.md](05-ai-layer.md) | Claude integration, grounding, citations, guardrails, evals |
| [06-frontend-ux.md](06-frontend-ux.md) | Screens, flows, design system, accessibility |
| [07-api-backend.md](07-api-backend.md) | API contracts, services, build artifacts |
| [08-testing-qa.md](08-testing-qa.md) | Test strategy, reference cases, CI |
| [09-timeline-team.md](09-timeline-team.md) | Team roles, 48-hour schedule, milestones |
| [10-risks.md](10-risks.md) | Risk register and mitigations |
| [11-demo-pitch.md](11-demo-pitch.md) | Demo script, submission package |
| [12-backlog.md](12-backlog.md) | Every task with ID, owner, estimate, dependencies |
| [13-round-2-features.md](13-round-2-features.md) | Round 2: fire replay, suppression calculator, detection pillar |
