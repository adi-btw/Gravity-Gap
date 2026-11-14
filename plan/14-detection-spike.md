# 14 · R3 detection pillar: feasibility spike result

Back to [overview](00-overview.md). Spike defined in [13 · Round 2 features](13-round-2-features.md) ("R3 · Phase 0").
Format details: [`data/detection/FORMATS.md`](../data/detection/FORMATS.md). Code: `scripts/fetch_detection.py`,
`engine/detection.py`, `tests/test_detection_spike.py`.

## Verdict: PARTIAL (no-go for the smoke-vs-dust overlap chart, go for a reduced page)

The plan's rule is "go if SAME-R binned sizes **and** DAFT dust sizes can be parsed into the same diameter axis".

| Requirement | Result |
|---|---|
| SAME-R binned smoke sizes | **Yes.** Three TEM workbooks parsed into count-per-bin vs diameter (nm). |
| DAFT dust sizes | **No binned sizes exist.** DAFT flew a particle counter (total number) and a mass monitor (total mass). The only size is one derived *diameter of average mass* per dust bag (1.57-1.72 um), which assumes a density of 1.0 g/cm^3. |
| "Lunar dust" | **Not in the data.** The DAFT dust is Arizona Road Dust (ARD Fine) blown with ISS nitrogen and sampled through an impactor. No lunar regolith or simulant. |
| PSI-115 gravity vs no-gravity | **Yes.** Six simulated size distributions parsed (44 size nodes each). |

So the planned overlap metric ("share of smoke counts in size bins where dust is also present") **cannot be
computed**: dust has no bins. What can be shown honestly is smaller:

1. Smoke size distributions per material (SAME-R TEM bins) and per-run smoke moments (100 runs, 5 materials).
2. One like-for-like comparison: *diameter of average mass* of smoke (SAME-R, per run) against the same
   quantity for ARD dust (DAFT, 3 bags). Both come from a number count plus a mass reading.
3. PSI-115 simulated gravity vs microgravity distributions, labelled "simulation, DBP surrogate".

**Recommendation:** build the fallback "detection evidence" page with items 1-3, title the dust series
"Arizona Road Dust (DAFT)", and do not use the words "lunar dust" for any data series. The question
"could lunar dust fool a smoke detector?" stays a stated gap, not an answered one.

### Data that could not be parsed, and why
- **DAFT dust size distribution:** does not exist in PSI-47. The instruments report totals only.
- **Lunar dust of any kind:** not present in PSI-47, PSI-101, PSI-102 or PSI-115 files examined.
- **SAME (PSI-102) data files:** not downloaded in the spike (only its 8-row experimental table). The SAME-R
  results workbook contains sheets `SAME1 Flight Tests 8-27-09` and `SAME Ground Test Results` that were not
  examined.
- **`Sample descriptions tables.docx`:** text extracted, no parser written; it duplicates the results workbook
  and has at least one garbled row.

## File inventory

24 files, 54.9 MB in `data/detection/raw/` (48.1 MB of that is three reference documents; the data files are
6.8 MB). Full sha256 values: `data/detection/manifest.json`.

| File (under `raw/<PSI-id>/`) | Size (bytes) | sha256 (first 16) | Holds |
|---|---|---|---|
| `PSI-101_Analyzed_Data_54_lampwick_binneddatacorr_from_GWM.xlsx` | 241,661 | `3a264eda40cb49eb` | TEM binned sizes, lampwick run 54 |
| `PSI-101_Analyzed_Data_60_silicone.xlsx` | 423,378 | `6987ebfe9e209cb1` | TEM binned sizes, silicone run 60 |
| `PSI-101_Analyzed_Data_62_Kapton_unaged.xlsx` | 425,564 | `e621db68f06276e0` | TEM binned sizes, Kapton run 62 (unaged) |
| `PSI-101_Analyzed_Data_SAME,_SAME-R_Results.xlsx` | 4,061,669 | `6d3a539ccf425b1f` | Per-run moments for all SAME-R runs; paper summary tables |
| `PSI-101_Analyzed_Data_Sample_descriptions_tables.docx` | 28,571,083 | `715cd2c4560799a0` | Sample table with TEM morphology notes and 123 images |
| `PSI-101_Analyzed_Data_thermal_precipitator_map_updated.xlsx` | 17,138 | `fe3765a3980ef9c6` | Run-to-precipitator map, viewing notes |
| `PSI-101_Experimental_table_SAME-R.csv` | 5,674 | `87164b7dc9168a42` | Run list: material, flow, heating ratio, aging times |
| `PSI-102_Experimental_table_SAME.csv` | 331 | `268d1e121d2f211b` | SAME sample list (8 rows) |
| `PSI-47_Experimental_table_DAFT.csv` | 518 | `d9d1a436c6e7bbc4` | DAFT sessions; names the dust (ARD Fine) |
| `PSI-47_Analyzed_Data_DAFT_Retrieved_Data_Summary.xls` | 1,004,032 | `a5c23d302f076de6` | All 7 DAFT logs + per-bag averages + derived diameter |
| `PSI-47_Analyzed_Data_flight_data_063_PTrk0002.xls` | 283,648 | `b622b43c51c1fa9d` | P-Trak / DustTrak series, tests 2-4, event timing |
| `PSI-47_Analyzed_Data_flight_data_063_DTrk0002.xls` | 283,648 | `a3bb7d6d33f733c0` | Same sheets as the file above |
| `PSI-47_Raw_Data_PTrk0002.txt` | 4,030 | `a108a81dd3752e66` | Raw P-Trak log, test 2 (724 readings, particles/cc) |
| `PSI-47_Raw_Data_DTrk0002.txt` | 3,752 | `1b87985871ef1677` | Raw DustTrak log, test 2 (778 readings, mg/m3) |
| `PSI-47_Reports_DAFT_FinalReport.doc` | 8,844,800 | `290c97891d808594` | Reference: dust material, density assumption |
| `PSI-115_Analyzed_Data_nodeDiameters.dat` | 1,059 | `9c190a7e0d884f6e` | 44 size-node diameters (m) |
| `PSI-115_Analyzed_Data_8cmGravityPSD.dat` | 1,716 | `ef90fed1159c8515` | Case 1, Earth gravity |
| `PSI-115_Analyzed_Data_8cmNoGravityPSD.dat` | 1,716 | `80a3e6a37912d474` | Case 1, microgravity |
| `PSI-115_Analyzed_Data_8cmGravityNS_PSD.dat` | 1,755 | `9bdaac8bbd2d663f` | Case 1, Earth gravity, no settling |
| `PSI-115_Analyzed_Data_8cmNoGravityNoTF_PSD.dat` | 1,755 | `2fcee7dc9098fa0a` | Case 1, microgravity, no thermophoresis |
| `PSI-115_Analyzed_Data_10cmGravityPSD.dat` | 1,716 | `f67f2ff614eff26a` | Case 2, Earth gravity |
| `PSI-115_Analyzed_Data_10cmNoGravityPSD.dat` | 1,716 | `32f39f6a51baef37` | Case 2, microgravity |
| `PSI-115_Science_Documents_DataOrganizationDocument.pdf` | 96,899 | `754cd3b7e1f1334f` | Reference: case naming, t = 7 s |
| `PSI-115_Reports_NNX17AF08A_FinalReport.pdf` | 10,617,514 | `487108f951ba8ec9` | Reference: node spacing, PSD definition |

**Commit recommendation (team lead decides):** total is over 25 MB only because of three reference documents.
Suggest committing the 21 data files and `manifest.json` (6.8 MB, same convention as
`data/psi_experimental_tables/`) and adding the `.docx`, `.doc` and the 10.6 MB `.pdf` to `.gitignore`; the
manifest keeps their sha256 and `fetch_detection.py` restores them. `.gitignore` was not changed.

## Format summary

| Source | Format | Diameter | Value | Instrument |
|---|---|---|---|---|
| SAME-R TEM workbook, sheet `Binned data*`, rows 15+ | xlsx | col H `Dmid`, um | col D `dN`, particles per bin | TEM image sizing of thermal-precipitator samples |
| SAME-R results workbook, sheet `SAME R Results`, rows 3-121 | xlsx | cols BI / BJ / BN, um (moments, no bins) | col BD number, #/cm^3; col BM sigma-g | P-Trak (number), ionization chamber (length moment), DustTrak (mass) |
| DAFT raw logs / flight xls | txt, xls | none | one total per second: particles/cc or mg/m3 | TSI P-Trak, TSI DustTrak |
| DAFT summary, sheet `Logged Data Summary`, rows 5, 9, D20 | xls | derived diameter of average mass, um | per-bag averages | same two instruments |
| PSI-115 `*PSD.dat` + `nodeDiameters.dat` | text | node diameter, m | number density per size node, m^-3 `[verify]` | simulation |

No SMPS or TEOM data file was found in the downloaded set (TEOM appears only as a DustTrak calibration
factor column).

## Numbers available

### Smoke, binned (SAME-R TEM; `engine.detection.parse_same_r_tem`)
Statistics computed by our parser; geometric mean and sigma-g match the workbook cells I9 / J9 to better than 1%.

| Material / run | Sheet, rows | Particles | Count median (nm) | Geometric mean (nm) | Geometric std | Non-zero bins (nm) |
|---|---|---|---|---|---|---|
| Lampwick, run 54 | `Binned data`, 15-44 | 576 | 252 | 192 | 2.71 | 12-1271 |
| Lampwick, run 54 | `Binned data big only`, 25-44 | 511 | 276 | 254 | 1.87 | 56-1271 |
| Silicone, run 60 | `Binned data`, 15-39 | 973 | 62 | 54 | 2.68 | 6-440 |
| Silicone, run 60 | `Binned data big only`, 26-39 | 519 | 108 | 113 | 1.55 | 65-440 |
| Kapton, run 62 unaged | `Binned data (2)`, 15-49 | 1803 | 123 | 89 | 2.93 | 11-680 |
| Kapton, run 62 unaged | `Binned data big only (2)`, 15-37 | 1293 | 162 | 162 | 1.64 | 60-680 |

The full sheets are bimodal (a population of very small particles plus the main mode), which is why the
median and geometric mean differ; the "big only" sheets are the workbook authors' own cut.

### Smoke, moments per run (`parse_same_r_moments`; sheet `SAME R Results`, rows 3-121, 100 usable runs)
Medians computed by us across runs; test conditions (heating, flow, aging) vary between runs.

| Material | Aged repeat | Runs | Dg median (min-max), nm | sigma-g median | Diameter of average mass median, nm |
|---|---|---|---|---|---|
| Kapton | no | 13 | 82 (33-251) | 1.94 | 116 |
| Kapton | yes | 12 | 99 (51-279) | 1.87 | 169 |
| Lampwick | no | 13 | 96 (55-380) | 2.36 | 289 |
| Lampwick | yes | 7 | 177 (102-331) | 2.05 | 414 |
| Pyrell | no | 12 | 155 (63-303) | 2.19 | 439 |
| Pyrell | yes | 8 | 291 (155-385) | 1.89 | 629 |
| Silicone | no | 14 | 168 (117-826) | 2.43 | 538 |
| Silicone | yes | 8 | 360 (251-1056) | 2.02 | 757 |
| Teflon | no | 10 | 122 (32-241) | 1.86 | 231 |
| Teflon | yes | 3 | 115 (70-198) | 2.30 | 309 |

Across all 100 runs: Dg 32-1056 nm, diameter of average mass 89-1217 nm, number 3.5e4-5.9e6 particles/cm^3.
The experimenters' own per-material averages are in the three "Paper data table" sheets (rows 3-12); they
disagree with each other slightly, so they were not used.

### Dust (DAFT; `parse_daft_summary`; sheet `Logged Data Summary`)

| Bag | Number, row 5 (particles/cm^3) | Mass, row 5 (mg/m^3) | Diameter of average mass, row 9 (nm) |
|---|---|---|---|
| 1 | 17,236 | 45.6 | 1716 |
| 2 | 16,589 | 33.8 | 1573 |
| 3 | 26,578 | 62.7 | 1651 |

Workbook average (cell B25): 1.647 um. Density assumed 1.0 g/cm^3 (cell D20); with the true density of the
mineral dust the diameter would be smaller (density of ARD `[verify]`). The other DAFT series carry no size
information either; which test number corresponds to which bag is `[verify]`.

### Simulated smoke (PSI-115; `parse_psi115_psd`), dibutyl phthalate surrogate, t = 7 s

| File | Rows | Count median (um) | Geometric mean (um) | Geometric std | Peak node (um) | Share of count above 20 um |
|---|---|---|---|---|---|---|
| `8cmGravityPSD.dat` | 1-44 | 6.12 | 5.90 | 1.53 | 7.1 | 0.0038 |
| `8cmNoGravityPSD.dat` | 1-44 | 6.71 | 6.98 | 1.50 | 7.1 | 0.038 |
| `8cmGravityNS_PSD.dat` | 2-45 | 5.49 | 5.37 | 1.46 | 5.4 | 0.0021 |
| `8cmNoGravityNoTF_PSD.dat` | 2-45 | 5.96 | 6.07 | 1.40 | 5.4 | 0.0079 |
| `10cmGravityPSD.dat` | 1-44 | 4.91 | 4.97 | 1.39 | 5.4 | 0.0037 |
| `10cmNoGravityPSD.dat` | 1-44 | 5.69 | 5.83 | 1.43 | 5.4 | 0.014 |

In both cases the microgravity run keeps a larger share of very large particles (about 10x for case 1, 4x
for case 2), consistent with the final report's statement that the largest particles settle out in Earth
gravity. Totals differ between runs and depend on the `[verify]` unit, so compare shapes, not totals.

## Caveats
- **Different size definitions.** TEM gives a projected-area diameter of collected particles; the moment
  method gives diameters inferred from three integrated signals with a lognormal assumption; DAFT gives a
  diameter of average mass with assumed density. For the same run they disagree: lampwick run 54 is
  192 nm (TEM geometric mean, all particles) vs 72 nm (moment Dg, results row 11). The cause was not
  investigated. Do not mix them in one series.
- **Small samples.** TEM counts are 511-1803 particles per run, one run per material in the spike. Eight more
  `.xlsx` workbooks with run-number names are listed in PSI-101 (runs 55, 57, 62 aged, 63 and 64 aged/unaged,
  94) and were not downloaded; by file name none is for Teflon.
- **Sizes in simulation vs experiment differ by ~30x.** PSI-115 particles peak at 5-7 um; SAME-R smoke is
  mostly 0.03-1 um. PSI-115 models a DBP surrogate, not the SAME-R materials. Show it on its own chart.
- **Dust is Arizona Road Dust**, impactor-filtered, in a 15-litre bag. Not lunar.
- **Run identity of TEM files** rests on the file name and the PSI folder ("Reduced Gravity/Cotton Lamp
  wick/Run 054"); sheet names inside two of the files refer to run 64 (template leftovers).
- **Units:** PSI-115 PSD value unit `[verify]`; `area` unit in the TEM sheets `[verify]`; ARD density `[verify]`.
- **Detector sensitivity ranges** (ionization vs photoelectric) are still `[verify with a cited source]`, as in
  plan 13. The results workbook does hold detector voltages per run (`ISS Obscuration`, `ISS Detector
  Scatter`, `STS Detector`, `Ion A/B`), which could support a data-based detector note; not examined here.
- `xlrd` is needed for the DAFT `.xls` files and `openpyxl` for the SAME-R `.xlsx` files; both were added to
  `requirements.txt`.

## Proposed `artifacts/detection.json` (build phase)

Every series keeps the common parser shape, so each curve traces to file, sheet and rows.

```json
{
  "generated_at": "ISO-8601",
  "engine_version": "x.y.z",
  "verdict": "partial",
  "gaps": [
    "DAFT measured total number and total mass only; no dust size distribution exists.",
    "The DAFT dust is Arizona Road Dust, not lunar regolith or simulant."
  ],
  "smoke_binned": [
    {
      "material": "Lampwick", "run": "54", "variant": "all | big_only",
      "source": {"investigation_id": "PSI-101", "file": "...", "sheet": "Binned data", "rows": "15-44"},
      "instrument": "TEM image sizing of thermal-precipitator samples",
      "diameter_nm": [], "bin_lower_nm": [], "dlnD": 0.1733,
      "value": [], "value_kind": "particle_count_per_bin", "units": "particles",
      "stats": {"count_median_diameter_nm": 0, "geometric_mean_diameter_nm": 0, "geometric_std": 0, "total": 0}
    }
  ],
  "smoke_moments": {
    "source": {"investigation_id": "PSI-101", "file": "...Results.xlsx", "sheet": "SAME R Results", "rows": "3-121"},
    "runs": [
      {"material": "Kapton", "run": "62", "aged": false, "row": 25,
       "number_per_cm3": 0, "geometric_mean_diameter_nm": 0, "count_mean_diameter_nm": 0,
       "diameter_of_average_mass_nm": 0, "geometric_std": 0}
    ],
    "by_material": [
      {"material": "Kapton", "aged": false, "n_runs": 13,
       "geometric_mean_diameter_nm": {"median": 0, "min": 0, "max": 0},
       "diameter_of_average_mass_nm": {"median": 0, "min": 0, "max": 0},
       "geometric_std_median": 0}
    ]
  },
  "dust": {
    "material": "Arizona Road Dust (ARD Fine), impactor-filtered",
    "is_lunar": false,
    "bags": [
      {"bag": 1, "source": {"investigation_id": "PSI-47", "file": "...Summary.xls", "sheet": "Logged Data Summary", "rows": "5, 9, 20"},
       "number_per_cm3": 0, "mass_mg_per_m3": 0, "diameter_of_average_mass_nm": 0, "assumed_density_g_per_cm3": 1.0}
    ]
  },
  "average_mass_comparison": {
    "note": "Same quantity for smoke and dust: diameter of average mass. Not a size-distribution overlap.",
    "smoke_nm": {"min": 0, "max": 0}, "dust_nm": {"min": 0, "max": 0}
  },
  "simulation": [
    {"case": "1", "gravity": "earth | micro", "variant": "base | no_settling | no_thermophoresis",
     "label": "simulation", "surrogate": "dibutyl phthalate", "time_s": 7,
     "source": {"investigation_id": "PSI-115", "file": "...", "sheet": null, "rows": "1-44"},
     "diameter_nm": [], "value": [], "value_kind": "simulated_number_density_per_size_node", "units": "m^-3 [verify]",
     "stats": {}}
  ]
}
```

Zeros and empty lists above are placeholders for the shape only, not values.

## Next steps if the reduced page is approved
1. DE: add the remaining TEM workbooks (8 files, each under 1 MB; Pyrell runs 63/64, lampwick 55/57, Kapton
   62 aged/94) by extending `SELECTED` in `fetch_detection.py`. No Teflon TEM workbook is listed, so Teflon
   would have moments only.
2. DE: `python -m engine.detection` writer for `artifacts/detection.json`.
3. TL: replace the overlap metric with the average-mass comparison, or drop it.
4. Catalog: PSI-47 detection evidence should say "Arizona Road Dust, number and mass only".
