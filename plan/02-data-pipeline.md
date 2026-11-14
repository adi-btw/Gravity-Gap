# 02 · Data Pipeline

Back to [overview](00-overview.md). Uses components P1, P2, P3 and E4 from [01-architecture.md](01-architecture.md).

## 1. Sources
| Source | What | Status |
|---|---|---|
| PSI experimental tables | 18 CSVs from 16 investigations (FLEX, FLEX-2, CFI, CFI-G, Flame Design, BRE, CLD, E-FIELD, s-Flame, SPICE, SLICE, BASS, BASS-II, SAFFIRE-I/II/III) | Downloaded to `data/psi_experimental_tables/` |
| PSI investigation metadata (ISA-Tab / API JSON) | Objective, hypothesis, impacts, hardware, publications, DOI | 11 zips in hand; the rest come through the API `geode-py/ws/repo/investigations/{id}` |
| Linked publications | Numbers missing from tables: partial-g results, E-FIELD voltage and ion current, flammability limits | To extract (E4) |
| Test-point logs (e.g. `19304A1_TP.txt`) | Per-run event timeline; 19304A1 is ACME s-Flame, 31 Oct 2019 | Stretch goal |
| NASA public specs | Cabin ventilation speeds, habitat atmospheres | Manual entry with citation |

License: PSI data is CC0-1.0. Cite each DOI, as PSI asks.

## 2. Pipeline stages
### P1 Ingest (`scripts/fetch_psi.py`)
- Reads the investigation list from config. Calls the PSI API for metadata, the experimental-table file list and signed download URLs.
- Writes the raw CSVs plus `data/raw_manifest.json` (file, version, sha256, fetched_at).
- Idempotent: it skips files whose sha256 has not changed.

### P2 Clean (`scripts/clean_psi_tables.py`): **DONE**
Outputs:
- `psi_tests.csv`: 1,710 tests
- `psi_saffire_ug_vs_1g.csv`: 9 samples
- `psi_test_day_summaries.csv`: 120 rows
- `CLEANING_REPORT.md`

Rules: never invent values; every fix is flagged; every row keeps `source_file` + `source_row`.

Remaining work:
- D1: add a pressure lookup for BRE days from the BRE papers (the table lacks pressure)
- D2: confirm FLEX burning-rate units (mm²/s?)
- D3: decode BASS-II fan and air display units from engineering docs

### P3 Evidence Catalog (`engine/catalog.py` → `artifacts/catalog.json`)
One record per investigation:
```json
{
  "id": "PSI-69", "acronym": "FLEX", "title": "...", "doi": "10.60555/...",
  "platform": "ISS", "hardware": "CIR/MDCA", "fuel_phase": "liquid",
  "gravity_levels": ["microgravity"], "ground_reference": false,
  "conditions": {"o2": [0.13, 0.40], "pressure_atm": [0.5, 3.1], "flow_cm_s": null},
  "n_tests": 274, "outcomes_available": true,
  "hazard_pillars": ["suppression", "prevention"],
  "objective": "...", "hypothesis": "...", "impacts": "...",
  "publications": [{"doi": "...", "title": "..."}],
  "fire_safety_relevance": {"score": 0.0, "evidence_quotes": []}
}
```
Condition ranges are computed from `psi_tests.csv`. They are never typed in by hand.

### E4 Literature Extractor (`engine/literature.py` → `artifacts/paper_values.json`)
- Inputs: PDFs or abstracts of the linked publications (priority list below).
- Claude extracts candidate values as `{quantity, value, unit, conditions, gravity_level, quote, page}`.
- **Verbatim gate:** the value and its quote must appear in the extracted PDF text (normalized whitespace), or the value is rejected.
- **Human review:** a reviewer marks each value `accepted` or `rejected` in a CSV before it can feed a model.
- Priority papers:
  1. BASS: "Simplified model for predicting difference between flammability limits of a thin material in normal gravity and microgravity" (Takahashi et al., DOI 10.1016/j.proci.2014.07.017)
  2. BASS: "A Correlation for an Effective Flow Velocity... Opposed-Flow Flame Spread over Thin Fuels" (Bhattacharjee et al., DOI 10.1080/00102202.2014.900056)
  3. BASS: "Opposed-flow flame spread: a comparison of microgravity and normal gravity experiments" (DOI 10.1016/j.firesaf.2015.11.011)
  4. E-FIELD: "Ion Current and Flame Changes with Electric Fields in Microgravity"
  5. BRE: Burning Rate Emulator flight results (from the PSI-20 publication list)
  6. Partial-gravity flammability literature (parabolic flight / lunar-g / Mars-g material tests). **Must verify** what exists before using any of it.

## 3. Canonical schema
Defined in `data/clean/README.md`. Key fields used downstream:
- `o2_mole_fraction`, `o2_context`
- `pressure_atm`
- `flow_speed_cm_s`
- `size_mm`, `size_kind`
- `ignited`, `outcome`, `burn_time_s`, `extinction_diameter_mm`
- `fuel_phase`, `configuration`, `investigation_id`
- `quality_flags`, `record_id`

## 4. Data quality gates (run in CI; see [08-testing-qa.md](08-testing-qa.md) T1)
- Physical ranges: O₂ in [0, 1]; pressure in [0.05, 10] atm; flow in [-1, 200] cm/s.
- Ambient gas fractions sum to 1 ± 0.03.
- No duplicate `record_id`.
- Row counts per investigation match the last accepted run, unless the change is approved.
- Every model input row has a `record_id`.

## 5. Known data gaps (shown in the UI as findings)
| Gap | Impact | Mitigation |
|---|---|---|
| No partial-gravity data in PSI | Core reason for the product | Physics bridging + literature + ledger |
| SPICE lacks O₂ and pressure | Can't use it for atmosphere effects | Use it only for the flow regime |
| BRE lacks pressure and per-O₂ outcomes | Weaker habitat-atmosphere evidence | D1 literature lookup |
| E-FIELD lacks voltage and current | Can't quantify the buoyancy analog | E4 extraction from papers |
| Normal-gravity references are sparse (only SAFFIRE-II in tables) | Weaker 1 g bound | Literature 1 g limits (E4), flagged as such |
