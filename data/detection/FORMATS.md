# Detection pillar raw file formats (R3 spike)

Files are fetched by `python scripts/fetch_detection.py` into `data/detection/raw/<PSI-id>/`
(spaces in PSI names become underscores). Sizes and sha256 are in `data/detection/manifest.json`.
Parsers: `engine/detection.py`. Everything below was read from the files themselves; anything not
confirmed by a file is marked `[verify]`.

Investigation ids (from `data/psi_metadata/`): PSI-101 = SAME-R, PSI-102 = SAME, PSI-47 = DAFT / DAFT-2,
PSI-115 = smoke simulation built on SAME data.

## 1. SAME-R per-run TEM workbooks (PSI-101, `.xlsx`, openpyxl)

`PSI-101_Analyzed_Data_54_lampwick_binneddatacorr_from_GWM.xlsx`, `..._60_silicone.xlsx`,
`..._62_Kapton_unaged.xlsx`. Instrument: transmission electron microscope images of particles collected
on thermal-precipitator grids, sized with image analysis. All diameters are in **micrometres**
("Minimum particle size 0.010 um", sheet `Comments on binned data`, row 2).

| Sheet | Content |
|---|---|
| `Results ...` | Per-image particle measurements (Area, Diameter, Volume, LN(D), Perim., ...). In the lampwick and Kapton files these sheets are named `Results 64-pre-*`, left over from a Pyrell run-64 template: do not use the sheet names to identify the run. |
| `all data`, `all data big only` (silicone: `all data (2)`) | One particle per row from row 19: B = area (um^2 `[verify]`), C = diam (um), D = vol, E = LN(D). Summary in rows 3-15: C6 = Davg, D11 = Dg, E8 = sigma-g, B9 = number of particles (big-only sheet). |
| `Binned data`, `Binned data big only` (Kapton: `Binned data (2)`, `Binned data big only (2)`, `Binned data big only`) | **The size distribution.** Header in row 14, data from row 15. |
| `Comments on binned data` | Column-by-column notes by the authors (lampwick and Kapton files). |

`Binned data*` columns (row 14 header, rows 15 to the last bin):

| Col | Header | Meaning |
|---|---|---|
| A, B | `Diameter`, `# of particles` | Pasted histogram scratch input. **Not** the distribution; ignore. |
| C | `LN(D)` | ln of the bin lower edge (um) |
| D | `dN` | **count**: particles in the bin |
| E, F | `dN/dLnD`, `dN/NdLnD` | count per ln-width, and normalised (integrates to 1) |
| G | `D` | **diameter**: bin lower edge, um |
| H | `Dmid` | **diameter**: geometric bin centre, um (this is what the parser uses) |
| K-N | `V`, `Vmid`, `dV/dlnD`, `dV/VdLnD` | volume-weighted versions |

Other cells: C8 = `dLnD` (bin width in ln space), D5 = total particles, I9 = `Dg` (um), J9 = `Sigmagn`,
O9 = `Dgv`, P9 = `Sigmagv`. "big only" sheets leave `dN` empty for the smallest bins (the authors'
cut removing the small-particle population); everything else is identical.

| File | Sheet | Data rows | dLnD | Non-zero bin centres (nm) | Particles |
|---|---|---|---|---|---|
| 54 lampwick | `Binned data` | 15-44 | 0.1733 | 11.8-1271 | 576 |
| 54 lampwick | `Binned data big only` | 25-44 | 0.1733 | 56.1-1271 | 511 |
| 60 silicone | `Binned data` | 15-39 | 0.24 | 5.9-440 | 973 |
| 60 silicone | `Binned data big only` | 26-39 | 0.24 | 64.6-440 | 519 |
| 62 Kapton unaged | `Binned data (2)` | 15-49 | 0.1429 | 10.8-680 | 1803 |
| 62 Kapton unaged | `Binned data big only (2)` | 15-37 | 0.1429 | 59.9-680 | 1293 |

Quirks: the silicone sheet repeats its last bin (C = 0.26) with zero counts in rows 40-64 (parser drops
them). The comments sheet says the bin width is 0.132, but cell C8 holds 0.1733 / 0.24 / 0.1429; the
parser reads C8. `SizeDist` holds a lognormal overlay with `#NUM!` cells; not used.

## 2. SAME / SAME-R results workbook (PSI-101, `.xlsx`, openpyxl)

`PSI-101_Analyzed_Data_SAME,_SAME-R_Results.xlsx` (4.1 MB, 40 sheets). **Integrated moments per run,
no size bins.**

Sheet `SAME R Results`: group header in row 1, column header in row 2, one run per row in rows 3-122
(100 rows have a full set of moment numbers; row 122 is `#VALUE!`).

| Col | Header (row 2) | Meaning / units |
|---|---|---|
| B | `Sample Type` | Kapton, Lampwick, Pyrell, Silicone, Teflon |
| F | `SAME #` | run number; a trailing `a` (e.g. `60a`) is the aged repeat of the same smoke |
| G | `Description` | e.g. "Baseline", "High Temp aging", "No flow run w/ aging" |
| K, L, M | `Inlet Velocity (cm/sec)`, `Rt/R0`, `Duration (sec)` | test conditions |
| AQ-AX | `ISS Obscuration (volts)`, `ISS Detector Scatter (volts)`, `STS Detector (volts)`, `Ion A/B (volts)` + offsets | smoke-detector and ionization-chamber signals, volts |
| AY | `Ptrak (PT/cc)` | P-Trak condensation particle counter, particles/cm^3 (before dilution correction) |
| AZ, BB | `DustTrak A/B (mg/m3)` | DustTrak light-scattering mass monitors |
| BD | `M0 best Diameter (#/cm3)` | zeroth moment = number concentration, particles/cm^3 |
| BE | `M1 (mm/cm3)` | first moment (from the ionization chamber) |
| BI | `M1/M0 (micro-m)--AMD` | arithmetic (count) mean diameter, um |
| BJ | `Diameter of Average mass (micro-m)` | um |
| BM | `Hatch Choate Sigma g` | geometric standard deviation (lognormal assumed) |
| BN | `Hatch Choate Dg` | geometric mean (= count median for a lognormal) diameter, um |
| BT, BW | `Dust Trak Cal Factor (Teom/Dusttrak)`, `Particle density g/cc` | calibration inputs (TEOM is named only as the calibration reference) |

Sheets `ICES 2012 Paper data table`, `AIAA 2012 Paper data table`, `IAASS Paper data table`: per-material
averages, "Baseline Aging" vs "Aged 720 sec", columns M-P in um and Q-T in nm (`Geom.Mean Diam. (nm)`,
`Arithmetic Mean Diam. (nm)`, `Diam. of Average Mass (nm)`, `sigma g`), rows 3-12. The three sheets give
**different numbers** for the same material (e.g. Kapton baseline Dg 42 / 47 / 44 nm); which is final is
`[verify]`. Other sheets (plots, `SAME1 Flight Tests 8-27-09`, `SAME Ground Test Results`,
`detection June 14`, ...) were not examined.

## 3. SAME-R sample descriptions (PSI-101)

- `PSI-101_Experimental_table_SAME-R.csv`: `Sample Type, SAME Test #, Description, Date, Inlet velocity
  (cm/s), Rt/R0, Duration (sec), Primary aging time (sec), Primary mixing time (sec), Net aging time (sec)`;
  one row per run (runs 48-114, `a` = aged).
- `PSI-101_Analyzed_Data_Sample_descriptions_tables.docx` (28.6 MB, 123 embedded TEM images, one table):
  `Precipitator | Run | Sample | Aged? | Date TEM | Description | Rt/R0 | Morphology | Image 1 | Image 2 |
  M0 Best Diameter | M1/M0 (um) AMD | Diameter of Average Mass (um) | Hatch Choate sigma-g`. Text is read with
  `zipfile` from `word/document.xml`; no parser was written. The numbers duplicate the results workbook,
  and at least one row is garbled (run 50 Teflon shows "65.14" under AMD; the workbook has 0.148 um), so
  prefer the workbook. The morphology notes (e.g. "No particles noted") are unique to this file.
- `PSI-101_Analyzed_Data_thermal_precipitator_map_updated.xlsx`, `Sheet1`: which run is on which
  thermal-precipitator position, with viewing notes ("particles present", "no particles").
- `PSI-102_Experimental_table_SAME.csv` (SAME, 8 rows): `Sample #, Sample Material, Air Flow (cm/s),
  Weight loss rate (mg/min), Aging Duration (minutes)`; materials Teflon, Kapton, Silicone Rubber,
  Lampwick, Dibutyl Phthalate. No SAME (PSI-102) data file was downloaded in the spike.

## 4. DAFT (PSI-47): no particle sizes

Instruments: TSI P-Trak (condensation particle counter, total number) and TSI DustTrak (light
scattering, total mass). Neither reports a size.

- `PSI-47_Raw_Data_PTrk0002.txt`, `..._DTrk0002.txt`: 8 header lines (`Instrument`, `SerialNumber`,
  `TestID`, `GMT`, `StartDate`, `StartTime`, `Units`, `Number of points`), then one reading per line from
  line 9. Units `particles/cc` (P-Trak) or `mg/m3` (DustTrak). One reading per second (timestamps in the
  summary workbook step by 1 s). Line endings are CR CR LF. `DTrk0002.txt` declares 778 points but holds
  779 values (the last, `2`, has no line ending); small negative DustTrak readings occur (-0.006).
- `PSI-47_Analyzed_Data_flight_data_063_PTrk0002.xls` and `..._DTrk0002.xls` (xlrd): the two files hold
  the same sheets: `TIMING` (event log in seconds: HEPA on/off, hose on, velcro start/stop) and
  `PTrk0002-4`, `DTrk0002-4`. Per sheet: column A = the raw log, row-1 headers `Time (sec)` and `pt/cc` or
  `mg/m3` (columns E/F, or F/G in `PTrk0004`), data from row 2. These are cabin-air / Velcro tests of
  4 Mar 2005, not dust-bag tests.
- `PSI-47_Analyzed_Data_DAFT_Retrieved_Data_Summary.xls` (xlrd):
  - `Raw PTrak Data`, `Raw DustTrak Data`: `DateN, TimeN, DataN` for tests 1-7 (Excel serial dates
    22 Feb 2005, 4 Mar 2005 x3, 17 Aug 2006, 21 Aug 2006 x2), data from row 2.
  - `Headers`: instrument settings per test (serial numbers, start times, number of points).
  - `Voice Down Data Summary`, `Logged Data Summary`: three dust bags, column pairs B/C, E/F, H/I =
    `P-Trak n/cm3`, `DustTrak mg/m3`. In `Logged Data Summary`: row 5 `average**`, row 7 `Mass Per
    Particle (gram)`, row 8 `Volume Per Particle (cm3)`, row 9 `D (micon)`, D20 `density` = 1.0, B25
    `Average D (micron)`.
  - `P-Trak vs. DustTrak Data`: paired series per bag from row 3.
  - Which test number is which bag is `[verify]` (only tests 6-7, 21 Aug 2006, reach tens of mg/m3).

What can be derived: a **diameter of average mass** per bag, d = (6 m / (pi rho N))^(1/3), from the
average mass and number concentrations with the workbook's assumed density of 1.0 g/cm^3 ("assuming a
material density of water", DAFT final report). Values: 1.72, 1.57, 1.65 um (bags 1-3). It is one
number per bag, not a distribution. The dust is **Arizona Road Dust (ARD Fine)** dispersed with ISS
GN2, sampled through an impactor that removes the largest particles (experimental table CSV; final
report). It is not lunar regolith or a lunar simulant.

- `PSI-47_Experimental_table_DAFT.csv`: `Session Name, Actual Day, Hardware Description, Sample Material,
  Sampled Location`, 2 rows (D1, D2).

## 5. PSI-115 simulated particle size distributions (`.dat`, plain text)

A simulation of dibutyl phthalate (DBP) vapour condensing into particles downstream of a heated source,
in Earth gravity and microgravity; all files are at t = 7 s (data organization document).

- `PSI-115_Analyzed_Data_nodeDiameters.dat`: header line "Diameter (starting from first non-vapor node)",
  then 44 diameters, 1.240e-9 to 1.385e-4. Units are metres (not stated in the file; they match the
  final report: 45 size nodes, node 1 = one DBP molecule of volume 4.44e-28 m^3, each node 2.25 times
  the volume of the previous one). Line n holds node n+1.
- `*PSD.dat`: two whitespace-separated columns, `node index` and `value`, no header. Files with 44
  lines start at node 2; `8cmGravityNS_PSD.dat` and `8cmNoGravityNoTF_PSD.dat` have 45 lines and start
  at node 1 (the vapour, ~5e20), which the parser drops. The value is the "collected number density"
  of that size node at the downstream measurement plane (final report section on PSD). The report writes
  the unit as m^-3, but its formula is velocity-weighted, so the exact unit and scaling are `[verify]`.
  Values are per node, not divided by the node width.

| File | Case (PSI subcategory) |
|---|---|
| `8cmGravityPSD.dat` / `8cmNoGravityPSD.dat` | Case 1 (inlet 0.08 m/s), Earth gravity / microgravity |
| `8cmGravityNS_PSD.dat` | Case 1, Earth gravity, no settling |
| `8cmNoGravityNoTF_PSD.dat` | Case 1, microgravity, no thermophoresis |
| `10cmGravityPSD.dat` / `10cmNoGravityPSD.dat` | Case 2 (inlet 0.1 m/s), Earth gravity / microgravity |

The much larger PSI-115 field files (`*NumDen.dat`, `*Smoke.dat`, ..., 6-18 MB each) were not downloaded.

## Reference documents fetched only to confirm units and materials

`PSI-115_Science_Documents_DataOrganizationDocument.pdf`, `PSI-115_Reports_NNX17AF08A_FinalReport.pdf`
(10.6 MB), `PSI-47_Reports_DAFT_FinalReport.doc` (8.8 MB). Not parsed by code.
