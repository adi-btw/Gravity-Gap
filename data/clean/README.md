# Clean PSI combustion data

Built by `scripts/clean_psi_tables.py` from the experimental-table CSVs in `data/psi_experimental_tables/`
(downloaded from psi.nasa.gov). Re-run any time with:

```bash
python scripts/clean_psi_tables.py
```

`CLEANING_REPORT.md` lists every dropped row, fixed value and flag from the last run.

## Ground rules
- **No invented values.** If a source cell is missing, unreadable or clearly wrong, the clean value is empty and `quality_flags` says why.
- **Every row traces back.** `source_file` + `source_row` point to the original CSV row (1 = first data row).
- **All tests are microgravity** (ISS, or Cygnus after leaving ISS). The only normal-gravity numbers are in `psi_saffire_ug_vs_1g.csv`.

## Files

### `psi_tests.csv`: one row per test (1,710 rows, 10 investigations)
FLEX, CFI, ACME CFI-G, ACME Flame Design, SPICE, BASS, BASS-II, SAFFIRE-I/II/III.

| Column | Meaning |
|---|---|
| `record_id` | Unique id: `investigation:table:source_row` |
| `investigation_id`, `investigation` | PSI id (e.g. PSI-69) and acronym (FLEX) |
| `hardware`, `platform` | Rack/apparatus and where it flew |
| `fuel_phase` | `gas`, `liquid` or `solid` |
| `configuration` | Droplet, spherical porous burner (normal/inverse flame), coflow jet, flat sample, etc. |
| `test_id`, `test_date` | Test identifier and ISO date. ACME dates are decoded from YYDDD test codes. SPICE has no year. |
| `fuel`, `fuel_mole_fraction` | Fuel or material, and its fraction in the fuel stream (or ambient, for inverse flames) |
| `gravity` | Always `microgravity` here |
| `o2_mole_fraction`, `o2_mole_fraction_final` | O₂ as a fraction (0.21 = 21%), at the start and end of the test |
| `o2_context` | `ambient` (the surrounding atmosphere) or `burner_oxidizer_stream` (inverse flames: O₂ flows out of the burner into a fuel atmosphere) |
| `pressure_atm` | Pressure in atm (converted from mmHg or bar where needed) |
| `n2_ / co2_ / he_mole_fraction` | Diluent fractions in the ambient (FLEX, CFI, BASS-II) |
| `flow_speed_cm_s`, `flow_direction` | Air speed past the flame (SPICE coflow, SAFFIRE), and its direction |
| `size_mm`, `size_kind` | Characteristic size: droplet diameter, nozzle diameter, sample thickness or sample dimension |
| `ignited` | True / False / empty (unknown) |
| `outcome` | How the test ended: `extinction`, `disruption`, `completion` (FLEX); `self_extinguished`, `flow_terminated`, `no_ignition`, `flash_only` (CFI-G); `complete_burn`, `partial_burn`, `no_sustained_burn` (SAFFIRE-II). Empty means not recorded. |
| `burn_time_s` | Burn duration in seconds (SPICE: derived from ignition and flame-off times) |
| `extinction_diameter_mm` | FLEX droplet diameter when the visible flame went out |
| `burning_rate_source_units` | FLEX burning rate exactly as given. The source labels the unit "mm", which is probably mm²/s, so check before using. |
| `cool_flame` | CFI-G normal flames: whether a cool flame was seen |
| `adiabatic_flame_temp_k`, `stoich_mixture_fraction` | ACME computed flame properties (Tad, Zst) |
| `notes` | Source comments, flame color, peak burner temperature, raw BASS-II fan/air settings |
| `quality_flags` | Semicolon list of every caveat or fix (see below) |
| `source_file`, `source_row` | Where the row came from |

### `psi_saffire_ug_vs_1g.csv`: microgravity vs normal gravity (9 SAFFIRE-II samples)
The same material tested in orbit and on the ground, at about 22% O₂ and 20 cm/s airflow.
Key columns are `ug_burn_length_cm` and `1g_burn_length_cm`, the burned fractions, and `which_burned_more`.
"Complete" in the source is converted to the full 29 cm sample length.
Rows with `needs_manual_review = True` involve mixed materials or footnotes, so read `ug_burn_length_raw`.

### `psi_test_day_summaries.csv`: one row per test day or condition range (120 rows)
ACME BRE, CLD Flame, E-FIELD Flames and s-Flame (O₂ levels or fuel tested that day, and flames ignited),
SLICE (free-text test days) and FLEX-2 (condition ranges only).
For BRE, the ignitions are **not split by O₂ level**, and **pressure is not in the table**.

## Most important flags
| Flag | Meaning |
|---|---|
| `no_outcome_in_table` | The table gives conditions but not how the test ended (CFI, Flame Design, BASS, BASS-II, SAFFIRE-I/III) |
| `o2_and_pressure_not_in_table` | SPICE lists airflow but not atmosphere |
| `conditions_not_in_table` | BASS lists only test numbers and materials |
| `pressure_approximate_in_source` | CFI-G lists "approx p (bar)" |
| `text_marker_in_numeric_column_set_to_missing` | The source had RAMP, LOW O2 or #DIV/0! in a number column |
| `flame_off_before_ignition_in_source_burn_time_missing` | SPICE time typo, so burn time left empty |
| `loss_of_signal_in_source_flow_and_ignition_unknown` | SPICE "LOS" rows |
| `pressure_zero_in_source_treated_as_missing` | One FLEX row records 0 mmHg |
| `thickness_typo_037mm_read_as_0.37mm` | SAFFIRE-II "037 mm" |
| `material_blank_in_source_filled_from_row_above` | SAFFIRE-II rows with an empty material cell (likely merged cells) |
| `flow_settings_kept_raw_units_unknown` | BASS-II fan and air "display" values have no stated units, so they are kept raw in `notes` |

## Validation
`psi_saffire_ug_vs_1g.csv` is the only microgravity-vs-1 g pairing in the data, so it is used for the
V3 hindcast (`python -m engine.hindcast`): predict the 1 g outcome of each SAFFIRE-II sample from its
microgravity result plus the physics bridge at g = 9.81, then score against the 1 g columns.
Results: `artifacts/validation_saffire.md` (summary, tables, limitations) and
`artifacts/hindcast_saffire.json`. Tests: `tests/test_hindcast.py`.
Sample 2-8 has no thickness in the source ("See Fig. 5"); the hindcast uses a flagged 10 mm fallback.
