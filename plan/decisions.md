# Decisions log (ADR-lite)

Back to [overview](00-overview.md). One entry per decision that is hard to reverse or that other roles build on. Format: context, decision, consequences. Owner: TL.

---

## ADR-0001: Scaling-law physics bridge plus Monte Carlo, not CFD or a full Bayesian model
- **Status:** accepted (build phase 1)
- **Context:** No fire tests exist at lunar or Martian gravity, so a partial-g prediction has to be inferred from 0 g (PSI microgravity data) and 1 g data. A CFD flame model needs chemistry, radiation and geometry we do not have, and would take far longer than the hackathon. A full Bayesian hierarchical model needs likelihoods per metric and enough overlapping data, which PSI does not have outside a few investigations.
- **Decision:** Use the order-of-magnitude scaling laws in [03-physics-engine.md](03-physics-engine.md) §2: u_b = C_b·sqrt(g·L·ΔT/T), Ri = u_b²/u_f², G* = (g/g₀)(P/P₀)², and the bridge u_eff = sqrt(u_f² + (k·u_b)²) that maps partial g onto an equivalent microgravity forced flow. Uncertainty comes from Monte Carlo (N = 2,000, seeded) over C_b ~ U[0.5, 1.5], k ~ U[0.3, 1.0], ΔT/T ~ U[3, 6] and L × U[0.5, 1.5] (`engine/montecarlo.py`).
- **Consequences:**
  - Fast (milliseconds), transparent and reproducible: every number can be checked by hand ([tests/fixtures/physics_reference.json](../tests/fixtures/physics_reference.json)).
  - Outputs are estimates with bands, never point predictions. Radiation and kinetics are not captured; G* is valid only for laminar buoyant flow structure. This is shown in the UI.
  - Coefficient ranges are assumptions until calibrated against BASS effective-flow literature (E4). Changing them changes every band, so it is a new engine version.
  - Uniform independent priors are a deliberate simplification; correlations between C_b and ΔT/T are ignored.

## ADR-0002: Python is the physics source of truth; the TypeScript port is checked by shared fixtures
- **Status:** accepted
- **Context:** The web app needs instant slider feedback (client side), and the API, Monte Carlo and artifacts need the same formulas server side. Two implementations can drift.
- **Decision:** `engine/physics.py` is canonical. It uses only `math` (no numpy) and plain scalar functions so `web/lib/physics.ts` can mirror it one function at a time. `tests/fixtures/physics_reference.json` (TL owned) is the contract: pytest (T2) and vitest (T3) both run every case. Exact-formula cases use rel_tol 1e-6; rounded plan values (R1–R4 "≈") use 0.01. T3 additionally requires TS = Python to 1e-9 relative.
- **Consequences:**
  - A physics change is made in Python first, the fixture is regenerated and hand-checked, then the TS port is updated until T3 is green.
  - Fixture conventions both sides must implement: `"inf"` (string) in `args` or `expected` means +Infinity; an expected 0 is compared with abs tol 1e-12; string `expected` (for `regime`) is compared exactly.
  - `engine/montecarlo.py` is numpy-vectorized and has no TS twin; a test asserts it equals the scalar functions sample by sample.

## ADR-0003: Serializing an infinite Richardson number
- **Status:** accepted
- **Context:** With ventilation off (u_f = 0) and g > 0, Ri = u_b²/u_f² is infinite (e.g. the Earth preset, u = 0). JSON has no Infinity, Python's `json` emits invalid `Infinity` by default, and a large finite sentinel (1e9) would leak a fake number into charts, quantiles and AI explanations.
- **Decision:**
  - In memory (Python `richardson`, numpy arrays from `sample_physics`), Ri stays `math.inf` / `np.inf`; `regime(inf)` = `"buoyant"`.
  - On any JSON boundary (`evaluate()`, API responses, `artifacts/regime_grid.json`), infinite Ri is `null` (`None`). `regime` is always present alongside it, so a consumer can tell infinite Ri (`ri: null, regime: "buoyant"`) apart from no data. `null` never means 0: g = 0 gives `ri: 0`.
  - Monte Carlo quantiles use linear interpolation over all samples including infinities; a quantile that is or touches infinity is reported as `null`. `ri_inf_fraction` reports the share of infinite samples. No sentinel is used.
  - The shared fixture uses the string `"inf"` (contract), because it is a test format, not an API payload.
  - All JSON writes in the engine use `allow_nan=False`, so an unhandled inf fails loudly.
- **Consequences:** FE renders `ri: null` as "∞ (ventilation off)" and must not plot it as 0. AI must not compute with it. Tests assert `json.dumps(..., allow_nan=False)` succeeds on these outputs.

## ADR-0004: Bounds metric definitions and training-set exclusions (M1-M3)
- **Status:** accepted (build phase 2)
- **Context:** M1-M3 are fitted on microgravity PSI tables (`data/clean/psi_tests.csv`) whose outcome labels do not map one-to-one onto "does the fire go out". Some rows lack features. A cabin query (O2, pressure, L) does not specify fuel or droplet size.
- **Decision:**
  - **M1** P(droplet flame self-extinguishes before burnout): FLEX (PSI-69), y = 1 for `extinction`, 0 for `completion`. The 61 `disruption` rows are **excluded**: the droplet broke apart, so whether the flame would have extinguished before burnout is unknown (treating them as "not extinction" would bias P downward). n = 206 (179 extinctions).
  - **M2** extinction diameter (mm): FLEX rows with outcome `extinction` and a recorded `extinction_diameter_mm` (38 disruption rows with a diameter are excluded for the same reason). n = 158.
  - **M3** P(gas flame self-extinguishes vs flow-terminated): ACME CFI-G (PSI-159) **normal** flames only (`o2_context = ambient`). The 154 inverse-flame rows are excluded because their O2 is the burner stream, not the cabin atmosphere. `no_ignition` and `flash_only` are excluded (no sustained flame). n = 133 (102 self-extinguished).
  - Rows with a missing feature are dropped, never imputed (M1: 7, M2: 1).
  - Features: M1/M2 `o2, ln p_atm, he, co2, is_methanol, droplet_mm`; M3 `o2, ln p_atm, is_ethane, is_propane (butane baseline), fuel_fraction`. Adiabatic flame temperature is **not** used in M3: a habitat query has no Tad, and Tad is a function of fuel, dilution and O2 that are already features.
  - Models: standardized logistic regression (C = 1) + 500 bootstrap refits (5th-95th percentile band) for M1/M3; linear quantile regression at q = 0.05/0.5/0.95 for M2 (sorted to avoid crossing, clipped at 0).
  - Query defaults: M1/M2 `fuel = "Heptane"` (closer to cabin hydrocarbons than methanol), `he = co2 = 0` (habitat diluent is N2), `droplet_mm = L_mm` **clipped to the training range** (1.1-4.67 mm; L = 10 mm therefore uses 4.67 mm, flagged as `inputs.droplet_clipped`). M3 `fuel = "propane"`, `fuel_fraction = 0.3` (the most tested dilution). All are `predict(**options)` keyword overrides.
  - Applicability gate: nearest training-row atmosphere distance over (O2, p_atm) > 2 gives `applicable = false`, no number, and a reason naming the nearest test. Habitat pressure is `p_psia / PSIA_PER_ATM`.
  - `model_version` = first 12 hex of sha256(code version, training rows, n_boot, seed).
- **Consequences:** M1 answers "extinction vs burning to completion", not "any flame loss". The lunar/Mars base atmosphere (34% O2, 0.56 atm) is **gated for M2** (nearest extinction-diameter test: 30% O2 at 1.01 atm, distance 2.14); M1 there rests on two nearby tests (34% O2 at 0.71 atm). Out-of-fold numbers are in `artifacts/validation_report.md`; M3 discrimination is weak (AUC ~0.62).

## ADR-0005: Gravity honesty rule for flow-free metrics (M1-M3)
- **Status:** accepted (build phase 2)
- **Context:** FLEX droplets and CFI-G spherical burners were tested in microgravity with no imposed flow, so the data contain no variable through which gravity (via u_eff) could act. Mapping partial gravity onto these models would invent a dependence the data cannot support.
- **Decision:**
  - `estimate` for M1-M3 is the microgravity model at the query's O2 and pressure, **independent of g and u_f**. `ref_0g` = the same estimate with the unwidened model band. `ref_1g = null` (no normal-gravity counterpart in PSI for these investigations). `nonmonotonic_flag = false`.
  - The regime fractions from `engine.montecarlo.sample_physics` widen the band by `f = 1 + 0.5 * mixed + 1.0 * buoyant` around the estimate: in logit space for probabilities (`logit(est) -/+ f * distance to logit(lo/hi)`, clipped to [0, 1]) and proportionally for quantities (lower edge clipped at 0). Fully forced (orbit) gives f = 1.
  - `transfer.confidence`: high if forced >= 0.8, medium if forced + mixed >= 0.8, else low. `transfer.basis` states the regime split, that gravity does not change the estimate, the widening factor, and that no 1 g reference exists.
  - Sensitivity (C11): O2 +/-0.03 and pressure +/-20% report the **estimate** at each end (`quantity: "estimate"`, `null` if that end is gated); C_b, k, dT/T and the L factor are pinned to each end of their Monte Carlo range and report the **band width** (`quantity: "band_width"`). k enters only u_eff, not Ri, so it never changes M1-M3 bands. He/CO2 are not varied (habitat queries assume N2 diluent).
  - The factors 0.5 and 1.0 are a stated assumption, not a calibrated quantity: no partial-gravity droplet or burner data exist.
- **Consequences:** Orbit presets get high confidence and the plain model band; lunar/Mars presets (0% forced at 10 cm/s, ~70% mixed) get the same estimate with a ~1.6x wider logit band and low confidence; Earth (u = 0, 100% buoyant) gets f = 2. The UI must show that the partial-g number is a microgravity number with a wider band, not a partial-g measurement. The test planner (C12) uses these widened bands, so it ranks mixed-regime lunar/Mars tests highest.
