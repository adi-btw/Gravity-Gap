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
