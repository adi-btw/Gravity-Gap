# explain_bounds v1

Task: explain one Gravity Gap prediction (`predictions[<metric>]`) for the habitat in the context pack.

Cover, in this order, each in one or two sentences with citations:
1. **Regime** — `physics.regime`, `physics.ri`, `physics.u_b_cm_s` vs the vent `habitat.u_cm_s`, and the
   Monte Carlo `physics.mc.regime_fractions` [eng:physics]. Thresholds: forced Ri < 0.1, buoyant Ri > 10.
2. **Estimate and 90% band** — `estimate`, `band90`, and the microgravity-only `ref_0g` band [eng:<metric>].
   If `applicable` is false, give the `reason` instead and stop the numeric part.
3. **Transfer confidence** — `transfer.confidence` and what it means for this regime.
4. **Why the band is wide** — the largest entry in `sensitivity` (spread between `low` and `high`),
   separately for `quantity: "estimate"` (atmosphere) and `quantity: "band_width"` (physics constants),
   and the widening factor `inputs.widen_factor` if present.
5. **What test would narrow it** — the best matching `planner` item [eng:planner:N] and the
   investigations it extends; if no planner is in the pack, say so and name the regime/atmosphere gap.
6. **Evidence** — the nearest `evidence` rows [rec:...] and their investigation [PSI-xx].

Use only numbers from the pack. Output the JSON object described in the system prompt.
