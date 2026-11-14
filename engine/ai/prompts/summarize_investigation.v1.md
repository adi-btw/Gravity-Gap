# summarize_investigation v1

Task: summarize one PSI investigation record from `records` in the context pack.

Write exactly:
- **Summary:** three sentences on what was burned, on which platform/hardware, at which tested
  conditions (`conditions.o2`, `conditions.pressure_atm`, `conditions.flow_cm_s`, `n_tests`), and whether
  outcomes are available — using only fields of the record.
- **Hazard pillars:** the record's `hazard_pillars` (prevention / detection / suppression).
- **Earth application:** one sentence, only if the record text supports it; otherwise write
  "Not stated in the record."
- **Cite:** `[PSI-xx]` and `[doi:...]` from the record.

Never add numbers that are not in the record. Output the JSON object described in the system prompt.
