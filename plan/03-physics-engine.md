# 03 · Physics Engine (E1, E2, E3)

Back to [overview](00-overview.md). Components are defined in [01-architecture.md](01-architecture.md). Data comes from [02-data-pipeline.md](02-data-pipeline.md).

> **Scientific honesty rule:** every formula below is a standard order-of-magnitude scaling law. Each output is labeled an *estimate* with an uncertainty band. Coefficients are fitted or bracketed, never hidden.

## 1. Inputs (habitat state from F0)
| Symbol | Meaning | Units | Typical range |
|---|---|---|---|
| g | Gravity | m/s² | 0 (orbit), 1.62 (Moon), 3.71 (Mars), 9.81 (Earth) |
| P | Cabin pressure | psia → atm | 4.3–14.7 psia |
| X_O₂ | O₂ mole fraction | – | 0.21–1.0 |
| u_f | Forced (ventilation) flow speed | cm/s | 0–40 |
| L | Characteristic flame or fuel size | mm | 1–100 |
| ΔT/T∞ | Flame-to-ambient temperature ratio term | – | 3–6 (Monte Carlo range) |

## 2. E1 Core physics
### 2.1 Buoyant velocity scale
`u_b = C_b · sqrt( g · L · ΔT/T∞ )`, with C_b ≈ 1 bracketed over [0.5, 1.5].
- Example: L = 10 mm and ΔT/T∞ = 4 give u_b ≈ 63 cm/s on Earth, ≈ 25 cm/s on the Moon and ≈ 39 cm/s on Mars.
- Shows how much flow buoyancy alone drives around a flame at that gravity.

### 2.2 Mixed-convection regime: Richardson number
`Ri = u_b² / u_f²` (equivalently Gr/Re²).
| Ri | Regime | Which evidence applies |
|---|---|---|
| Ri < 0.1 | **Forced-flow dominated** | Microgravity tests at matching forced flow (BASS, SAFFIRE, SPICE) transfer well |
| 0.1 ≤ Ri ≤ 10 | **Mixed** | Neither 0 g nor 1 g data alone; highest uncertainty |
| Ri > 10 | **Buoyancy dominated** | Normal-gravity behavior is a better guide (with pressure correction) |

With u_f = 0 (ventilation off), Ri → ∞ for g > 0. In orbit, g = 0 gives Ri = 0, so the flame relies on diffusion and ventilation alone.

### 2.3 Pressure × gravity coupling: Grashof scaling
`Gr = g · β · ΔT · L³ / ν²`, with ν = μ/ρ and ρ ∝ P, so **Gr ∝ g · P² · L³**.
- Buoyancy strength relative to viscous damping scales with g·P². This is the basis of "pressure modeling" in fire research.
- Ratio vs. Earth sea level: `G* = (g/g₀) · (P/P₀)²`.
  - Moon at 8.2 psia: 0.165 × (0.558)² ≈ **0.051**
  - Moon at 10.2 psia: ≈ **0.080**
  - Mars at 8.2 psia: ≈ **0.118**
- **Caveat shown in the UI:** radiation and chemical kinetics do not follow this scaling, so G* is valid for laminar buoyant flow structure only.
- Note: Ri does not depend on P; Gr and Re do. F3 shows both, so users don't conflate them.

### 2.4 Effective flow mapping: the bridge model
The key idea: **map a partial-gravity situation onto an equivalent microgravity forced-flow situation**, where PSI has lots of data.
`u_eff = sqrt( u_f² + (k · u_b)² )`
- k is a mixing coefficient bracketed over [0.3, 1.0]. It is to be calibrated against the effective-flow-velocity correlation in the BASS literature (E4, priority paper 2).
- The partial-g prediction is the microgravity response at flow u_eff, with oxygen and pressure matched.
- **Non-monotonic behavior is expected.** Flame spread and flammability have a peak at low-to-moderate flow ("Goldilocks" zone, see PSI-62). So **partial g is not guaranteed to sit between 0 g and 1 g.** The engine explicitly detects when u_eff lands on the peak and flags "partial gravity may be MORE flammable than both bounds."

### 2.5 Oxygen and pressure axes
- Report both the mole fraction X_O₂ and the partial pressure p_O₂ = X_O₂ · P.
- Atmosphere distance between a habitat and test conditions: `d = sqrt( ((X−X_t)/0.05)² + ((ln P − ln P_t)/0.3)² )`. It is used for evidence relevance (F1) and model applicability.

## 3. E2 Bounds Models
For each **response metric** we fit a data-driven model on microgravity data and combine it with the physics bridge.

| Metric ID | Response | Data | Model | Output |
|---|---|---|---|---|
| M1 | Probability a droplet flame self-extinguishes before burnout (vs O₂, P, diluent) | FLEX (274), CFI-G | Logistic regression with bootstrap (500 resamples) | P(extinction) with 90% interval |
| M2 | Extinction diameter vs O₂, He, CO₂ (suppression effectiveness) | FLEX | Gradient-boosted or quantile regression | Median and 5–95% interval |
| M3 | Self-extinguish vs flow-terminated for gas flames vs O₂, P, Tad | CFI-G (333) | Logistic + bootstrap | Probability with interval |
| M4 | Solid-material burn extent at given flow: μg vs 1g | SAFFIRE-II (9) + literature | Rule table + literature limits (small n, no ML) | Categorical with evidence |
| M5 | Flame existence vs coflow speed | SPICE (434) | Empirical ranges (min/max u per fuel and nozzle) | Supported flow window |

**Partial-g prediction pipeline (per query):**
1. Compute u_b(g), Ri and u_eff (E1) by Monte Carlo over C_b, k, ΔT/T∞ and L uncertainty (N = 2,000).
2. For each sample, evaluate the metric model at (X_O₂, P, u_eff).
3. Combine the model bootstrap spread and the physics-sample spread into a 90% band.
4. Lower and upper reference: the same metric at g = 0 (u_eff = u_f) and at a 1 g-equivalent u_eff.
5. Applicability check. If the query's atmosphere distance to the nearest training data is above 2, return **"extrapolation: no evidence"** with no number (honesty gate).

Outputs are written to `artifacts/bounds/*.json` for preset habitats and also served live from `POST /bounds` ([07-api-backend.md](07-api-backend.md)).

## 4. E3 Test Planner
Goal: rank candidate LUCI/FM2-style tests by **expected uncertainty reduction in habitat-relevant conditions**.
1. Candidate grid: g ∈ {0.165, 0.38}, P ∈ {8.2, 10.2, 14.7} psia, X_O₂ ∈ {0.21, 0.265, 0.30, 0.34}, u_f ∈ {0, 5, 10, 20} cm/s.
2. Score = (width of the 90% band at the candidate) × (habitat weight) × (fraction of physics samples in the mixed regime).
3. Greedy selection of the top 10, re-scoring after each pick, assuming the chosen point collapses local uncertainty (a kernel-weighted reduction over the neighborhood).
4. Output: a ranked list with a plain-language rationale and the investigations whose data would be extended.

## 5. Validation plan (see [08-testing-qa.md](08-testing-qa.md))
- V1: Unit reference cases for u_b, Ri, G* and u_eff, hand-calculated in a spreadsheet and checked to 1%.
- V2: Leave-one-investigation-out validation for M1–M3 (e.g. train on FLEX, test on CFI-G where the variables overlap). Report AUC and calibration.
- V3: **Hindcast with SAFFIRE-II.** Predict 1 g burn extent from μg data plus the bridge at g = 9.81, and compare with the 1 g columns. Report hits and misses honestly.
- V4: Literature sanity check: compare against any published partial-g flammability results found in E4. Mismatches are shown, not hidden.
- V5: Sensitivity analysis: tornado chart of C_b, k, ΔT/T∞ and L influence on each prediction (shown in F4).

## 6. Known limitations (shown in the app's About panel)
- Scaling laws give orders of magnitude. They don't resolve chemistry or radiation.
- PSI microgravity data mostly sits near 1 atm. The low-pressure evidence is thinner (CFI 0.75 atm, CFI-G ~0.5 bar, Flame Design ~0.5 atm).
- Solid materials (the real cabin hazard) have the fewest tests (SAFFIRE, BASS). Results there are mostly qualitative.
