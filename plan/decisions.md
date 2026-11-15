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

## ADR-0006: Dilution-aware honesty gate for M1/M2 (R2 suppression calculator)
- **Status:** accepted (round 2, R2)
- **Context:** M1 and M2 use `co2` and `he` as features, but the ADR-0004 gate looked only at O2 and pressure. Every diluted FLEX training test is at 13-24% O2 (0.69-3.05 atm; 95 CO2 and 44 He rows in M1). Without a diluent dimension the gate would vouch for "CO2 at 34% O2 / 8.2 psia". Even with a 4-D distance, the undiluted 34% O2 / 0.71 atm tests sit 0.80 from the lunar base, so CO2 fractions up to ~0.18 would still pass while the CO2 effect there is pure extrapolation of one logistic slope learned at other O2 levels.
- **Decision:**
  - For M1/M2 the gate distance is `sqrt(((O2-O2_t)/0.05)^2 + ((ln p - ln p_t)/0.3)^2 + ((CO2-CO2_t)/0.10)^2 + ((He-He_t)/0.10)^2)`, applicable if <= 2 to some eligible training test (`engine.bounds._distances`, `dilution_distance`). M3-M5 unchanged.
  - **Diluent evidence rule:** a query with CO2 > 0 (He > 0) may only be vouched for by training tests that also used CO2 (He). An undiluted query (habitat air) is compared with all tests, as before.
  - Scale 0.10 for CO2 and He is an **assumption**: it makes the gate radius +/-0.20 mole fraction, the typical spacing between tested FLEX dilution levels (0.05-0.10 steps up to 0.70 CO2 / 0.45 He), so a query between two tested levels stays covered and one far past the highest level is not. It is not calibrated against any model-error measurement. Changing it changes what the calculator shows.
  - `engine.coverage` uses the same distance and rule (M1/M2 points carry `co2`, `he`; `habitat_status`/`coverage_for` take optional `co2`/`he`) so "covered == applicable" holds.
  - Suppression curves hold habitat O2 and pressure and replace N2 with the diluent (`engine.suppression`).
- **Consequences:**
  - Preset results (undiluted queries) are unchanged: no applicable/estimate/band flip in `artifacts/bounds/`. Only the evidence lists and nearest-test text changed; exploration M1/M2 nearest distance grew (0.50 -> 0.70 / 1.30) because the nearest test was CO2-diluted.
  - ISS air: CO2 covered up to 0.60, He up to 0.45. Exploration air: CO2 up to 0.50. Lunar/Mars base (34% O2): every CO2 or He fraction > 0 is gated, which feeds the planner as a "dilution at high O2" candidate.
  - Out-of-fold M1 discrimination on CO2-diluted rows is weak (AUC ~0.55, `artifacts/validation_report.md`); the curve is a trend, not a dose-response measurement.

## ADR-0007: Detection pillar ships in reduced scope; dust is Arizona Road Dust, not lunar dust
- **Status:** accepted (round 2, R3)
- **Context:** Plan 13 R3 asked "would a smoke detector see this fire, and could lunar dust fool it?", with an overlap chart and an overlap metric (share of smoke counts in size bins where dust is also present). Its go rule was "SAME-R binned sizes **and** DAFT dust sizes on one diameter axis". The spike (`plan/14-detection-spike.md`) returned PARTIAL:
  - SAME-R (PSI-101) has real binned smoke sizes from microscope images (3 runs downloaded) and per-run integrated moments for 100 runs of 5 materials.
  - DAFT (PSI-47) flew a particle counter (total number) and a mass monitor (total mass). There are no dust size bins. The only dust size is one diameter of average mass per bag (3 bags), computed with an assumed density of 1.0 g/cm^3.
  - The DAFT dust is Arizona Road Dust (ARD Fine), per the DAFT experimental table. No lunar regolith or simulant appears in PSI-47, 101, 102 or 115 files.
  - PSI-115 gives six simulated size distributions (dibutyl phthalate surrogate, t = 7 s) in Earth gravity and microgravity, in a value unit we could not confirm.
  - No cited source for ionization vs photoelectric detector size sensitivity is in the repo. The SAME-R results workbook has detector voltages per run, but one column is empty, one is all zero, and the offset/baseline meaning is not documented.
- **Decision:**
  - Ship a "Detection evidence" page (`artifacts/detection.json`, contract "Round 2 · R3 Detection evidence addendum"), not the overlap page. It shows: smoke size distributions per material (TEM, full sheet and the authors' "big only" cut); per-run smoke moments per material, aged and unaged kept apart; one like-for-like comparison (diameter of average mass of smoke per run vs the same quantity for 3 DAFT dust bags); and PSI-115 gravity vs microgravity curves, normalised to a share of count per size node.
  - **No overlap metric** and **no detector sensitivity ranges.** Detector voltages are not shown.
  - The dust is always labelled "Arizona Road Dust (DAFT)", with the density-1.0 assumption stated next to it. "Lunar dust" appears only in an explicit gap: the question "could lunar dust fool a smoke detector?" is stated as unanswered by these data.
  - Every series carries one `size_definition` and a `source {investigation_id, file, sheet, rows}`. Different size definitions (TEM image diameter, moment-method diameter, diameter of average mass, simulation node) never share a series, because the spike showed they disagree for the same smoke (lampwick run 54: 192 nm vs 72 nm).
  - The artifact is built from committed data files only, and records their manifest hashes in `generated_from`.
- **Consequences:**
  - The page answers a smaller question: how big smoke particles from heated spacecraft materials are, how that compares with one test dust on one size measure, and what gravity does to a simulated smoke. It does not say whether a detector would alarm, or whether lunar dust would trigger it.
  - The smoke-vs-dust comparison is weak by design: one number per dust bag, with an assumed density. Mineral dust is denser than 1.0 g/cm^3, so the real dust diameter is smaller than shown (ARD density is not in these files).
  - The catalog's detection evidence for PSI-101, PSI-47 and PSI-115 now names the data files used; PSI-102 points only to its 8-row sample table.
  - Reopening the overlap chart needs new data: a dust size distribution (or a lunar simulant measurement) and a cited detector sensitivity source. The AI answers must state the same gaps.

## ADR-0008: What drives the uncertainty — a band-width budget (S3)
- **Status:** accepted (round 3, S3)
- **Context:** Plan 15 S3 asked for the share of each covered band that comes from each source of uncertainty: the four Monte Carlo inputs (C_b, k, dT/T, L), model uncertainty and the gravity widening, with a "biggest lever". Checking `engine.bounds` first: for M1-M3 the **estimate** depends only on the atmosphere (O2, pressure, CO2, He) and the fuel options. Gravity, vent speed and the Monte Carlo inputs never move it (ADR-0005). They reach the **band** only through the regime fractions, which set the widening factor f = 1 + 0.5 mixed + 1.0 buoyant. And k enters only u_eff, not the Richardson number, so it never reaches an M1-M3 band. A plain Sobol split of "the output" would therefore give every physics input a first-order share of about zero (they only stretch the spread the model already has), which is true but useless.
- **Decision:** `engine/uncertainty.py` `drivers(metric, habitat)` splits the final 90% band width W into parts that add up to 1:
  - **Model uncertainty** (basis `psi_data`) = W(f = 1) / W, the unwidened band. M1/M3: the 5-95% spread of the bootstrap refits at fixed physics (bootstrap s.d. also reported). M2 has no bootstrap: its band is the q05-q95 quantile-regression spread, which mixes test-to-test scatter with model fit; we say so in `model_detail.note`.
  - **Gravity widening** (basis `honesty_rule`) = (W(f_min) - W(1)) / W, where f_min is the smallest per-sample factor over the Monte Carlo samples: the widening every plausible flame gets. No physics input can remove it.
  - **C_b, k, dT/T, L and remainder** (basis `engineering_assumption`) = (W - W(f_min)) / W, the extra widening that exists because some plausible input values make the flame more buoyant. It is split by first-order indices of the per-sample band width W(f_i): each input is binned into deciles and S_i = Var(E[W | bin]) / Var(W). The unsplit part (1 - sum S_i) is shown as "interactions / not split". k is reported with share 0 and `reaches_band: false`.
  - O2 and pressure are not sources: the user sets them exactly.
  - **Lever** = the largest source other than the remainder. Model uncertainty → "more tests near this atmosphere" plus the nearest same-metric Planner candidate (planner kernel distance ≤ 2, else none). Gravity widening → only partial-gravity tests could shrink it, and the PSI data have none. A physics input → named as an engineering assumption, "pinning it down would either remove this part of the band or confirm it" (on average, knowing the input does not make the band narrower; it tells which of the possible widths is right).
  - Only covered M1-M3 queries get a breakdown; "no evidence" and the M4/M5 rule tables return `applicable: false` with a reason. Seeded (same n = 2000 samples and seed as `predict`), about 6 ms per metric after the model fit.
  - Estimator check (`tests/test_uncertainty.py`): within ±0.05 of the known indices on a linear model (deciles, n = 2000) and on the Ishigami function (20 bins, n = 20 000). With deciles the Ishigami x2 index comes out 0.37 instead of 0.44, because deciles smooth an oscillating effect. Our real output is a monotone step in each input, where deciles are accurate.
- **Consequences:**
  - Orbit presets (ISS, exploration): 100% model uncertainty, lever "more tests near this atmosphere". Lunar base M1: model 66%, gravity widening 27%, C_b 3%, L 1%, dT/T 0.4%, k 0, remainder 2%; M3: model 60%, widening 31%, C_b 4%. Earth (u = 0, all samples buoyant): the inputs get 0 and the widening is 50-61% of the band.
  - The physics inputs are small everywhere because the regime is mostly settled by gravity and vent speed; the honest headline is "the band is wide because few tests exist near 34% O2 and because the tests had no buoyancy", not "flame temperature".
  - The shares are a split of width, not of a probability distribution, and the split of the input part is a stated rule. The UI rounds shares to 5% and shows the remainder.

## ADR-0009: Honesty test by holding out tested atmospheres (S2)
- **Status:** accepted (round 3, S2)
- **Context:** Plan 15 S2 asked "when the app says covered, does the truth land in the band, and when it says no evidence, was that right?". Each fitted model comes from one investigation (M1/M2 FLEX, M3 CFI-G), so leaving an investigation out is impossible.
- **Decision:** `engine/holdout.py` → `artifacts/holdout.json`.
  - **Groups:** tested atmospheres rounded as `engine.coverage` rounds them (O2 and CO2/He to 3 decimals, pressure to 2; diluents only for M1/M2). M1 74 groups, M2 65, M3 83.
  - **Primary scheme:** drop one group, refit (`engine.models.fit_model(metric, train)` with a subset `TrainingSet.subset(mask)`, n_boot = 200), then call `engine.bounds.predict(..., model=refit)` so the gate sees only the remaining tests. Both hooks are new optional parameters; the default behaviour is unchanged.
  - **Query:** g = 0 (the tests flew in microgravity with no imposed flow, so the band is the plain model band, factor 1), vent 10 cm/s (no effect at g = 0), and each held-out test's own fuel and droplet size (M1/M2, with L_mm = droplet size, the app's default) or fuel and fuel fraction (M3). The group's predicted rate is the mean of the per-test estimates, its band the mean of the per-test band edges.
  - **Hit rules:** M1/M3: 90% Wilson interval on the observed share of self-extinctions; hit when it overlaps the band (lenient for 1-3 tests); `strict_hit` = observed share inside the band. M2: hit when the median observed diameter is inside the band; single diameters inside their own band are pooled. Brier vs the remaining-training average for M1/M3.
  - **Wide check:** every group in a 0.10-wide O2 band is dropped at once (one refit per band), because one group at a time almost never leaves an atmosphere without a tested neighbour. A band whose removal leaves one outcome only is listed as skipped with its reason.
  - **SAFFIRE-II hindcast** (M4) is included unchanged with its caveat: 7/9, the same as the constant "1 g always burns more" rule, so it is not discriminative.
  - Bands and gate are **not** changed by this result; any change needs its own ADR.
- **Consequences (results of the first run, 82-96 s on a laptop):**
  - Primary: every one of the 222 groups stayed covered (median distance to the nearest remaining test 0.02-0.03, largest 1.8), so this run tests the bands, not the "no evidence" side of the gate. Band coverage (overlap rule) M1 72/74, M2 58/65, M3 78/83; overall 208/222 = 0.94 (90% interval 0.90-0.96). The strict rule is much lower for M1 (7/74) and M3 (4/83): most groups have 1-3 tests whose observed share is 0 or 1, outside a band that rarely reaches 0 or 1. Pooled Brier: M1 0.083 vs 0.115 baseline (better); M3 0.175 vs 0.182 (barely better). M2 single diameters inside their band 134/158 = 0.85, under the nominal 0.90.
  - Wide check: 16 groups got "no evidence"; for none of the 14 M1/M3 ones would the ungated band have missed (1 of 2 for M2), so the gate is cautious rather than wrong. Covered bands held less often: M2 49/63 = 0.78 and single diameters 112/156 = 0.72 (M2 bands are too narrow away from dense data, especially for helium- and CO2-diluted tests); M3 could only be scored for 16 groups (weak test) because dropping 30-40% O2 leaves only self-extinguished flames, and there its Brier 0.176 is worse than the training average 0.100.
  - Worst misses are small groups: M1 18% O2 / He 0.15 (0/2 self-extinguished vs band 0.69-0.92), M3 35% O2 / 0.5 atm (0/2 vs 0.70-0.92), M2 16% O2 / CO2 0.25 (median 1.52 mm vs 1.78-2.74).
  - The overlap rule flatters small groups; the `/trust` page must show the strict rate and the pooled numbers next to it and say "weak test" where fewer than 10 groups are covered.
