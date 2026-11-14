# 13 · Round 2 features: Fire Replay, Suppression Calculator, Detection

Back to [overview](00-overview.md). Builds on phases 1–3 (see [STATUS.md](STATUS.md)). Same team roles, contracts style
and rules as before: no invented numbers, every value traces to a source, honesty gate always on.

| ID | Feature | Brief objective it serves | Size | Main risk |
|---|---|---|---|---|
| **R1** | Real-fire replay (Apollo 1, Mir, Artemis II, Apollo 13) | Storytelling + "relevant to habitable crew environments" | S | Getting incident atmospheres exactly right and wording them respectfully |
| **R2** | Suppression calculator (CO₂ / helium dilution) | Goal 3: next-gen fire safety controls and equipment (FLEX = suppression) | S–M | Dilution was never tested above 25% O₂: needs a dilution-aware honesty gate |
| **R3** | Detection pillar (smoke vs lunar dust) | NASA pillar "detection" (SAME, SAME-R, DAFT named in the brief) | M–L | Raw data is in messy Excel files; needs a feasibility spike first |

---

## Facts checked before planning
- **FLEX dilution coverage** (`data/clean/psi_tests.csv`, PSI-69): 123 tests with CO₂ > 0 (up to 70%), 50 with helium > 0
  (up to 45%), both fuels. **But every diluted test had O₂ between 13% and 25%**, at 0.69–3.05 atm. No dilution test
  exists at 30–34% O₂.
  → The current gate (O₂ × pressure distance only) would **not** flag "CO₂ at lunar-base air" as extrapolation. R2 must
  add diluent dimensions to the gate before showing any suppression number.
- M1 and M2 were already trained with `he` and `co2` as features (`engine/models`), and `bounds.predict(...)` accepts
  `he=` and `co2=` options. The suppression engine reuses them; no new model is needed for the first version.
- **Detection data in PSI** (from the PSI API file lists):
  | Investigation | What is there | Size |
  |---|---|---|
  | PSI-101 SAME-R | 86 "Analyzed Data" files, mostly one Excel file per sample material with binned particle data (e.g. `54 lampwick binneddatacorr`, `60 silicone`), plus a sample-description table; the experimental table (109 rows: inlet velocity, aging times) | ~495 MB analyzed |
  | PSI-102 SAME | 63 analyzed Excel files (per-run housekeeping, test logs, averages) | ~228 MB |
  | PSI-47 DAFT / DAFT-2 | 12 small flight-data Excel files from the P-Trak particle counter and the DustTrak (`PTrk…`, `DTrk…`) | ~3.5 MB |
  | PSI-115 (ground, SAME re-analysis) | Simulation outputs incl. smoke particle size distributions with gravity (`8cmGravityPSD.dat`, …) | ~254 MB |
  None of this is downloaded yet. Formats need `openpyxl` (xlsx) and `xlrd` (xls).

---

## R1 · Real-fire replay

**What the user sees:** a `/replay` page with incident cards. Click one and the habitat bar loads that incident's
conditions; the page then shows what Gravity Gap says about it: regime, which PSI data apply, and where the honesty gate
says "no evidence".

### Incidents (every value must be confirmed against the cited NASA page before shipping)
| Incident | Gravity | Atmosphere | Source to verify | Expected engine story |
|---|---|---|---|---|
| **Apollo 1 (1967)** pre-launch plugs-out test | 1 g (on the pad) | ~100% O₂ at ~16.7 psia [verify] | sma.nasa.gov/sma-disciplines/accllp/apollo-1 | Buoyant regime; O₂ far beyond any tested atmosphere, so most metrics say "no evidence". The point: today's data still can't vouch for pure-oxygen cabins |
| **Mir (1997)** oxygen-generator (candle) fire | ~0 g (orbit) | ~normal air, ~14.7 psia [verify] | nasa.gov/history/25-years-ago-fire-aboard-space-station-mir | Forced or quiescent microgravity: the case PSI data covers best. Ventilation still matters |
| **Artemis II** smoke alarm (in transit) | ~0 g | Orion cabin air [verify value] | challenge brief quote + NASA mission pages | Detection story: links to R3 ("was it smoke or something else?") |
| **Apollo 13 (1970)** oxygen tank explosion | ~0 g | inside a pressurized O₂ tank, not cabin air | sma.nasa.gov/sma-disciplines/accllp/apollo-13 | Shown as **outside the tool's scope** (high-pressure tank failure, not a cabin fire), and honestly labelled so |

### Build
- **DE:** `data/incidents.json` with incident, date, gravity, pressure, O₂, vent assumption, short neutral description,
  source URL, quote of the sourced value, `in_scope` flag. Tests that every in-scope incident has a source and values in range.
- **TL:** `engine/incidents.py` → `artifacts/incidents.json`: for each incident runs physics + bounds M1–M5 + coverage and
  stores the results (regime, applicable flags, nearest-test distances).
- **AI:** `GET /incidents`; add the incidents to the AI context so "What would Gravity Gap have said about Mir?" gets a
  cited, validated answer; extend the offline answer cache with one question per incident.
- **FE:** `/replay` page (cards with date, what happened, a "Load this habitat" button, an engine summary), a "History"
  group in the habitat bar, and a landing-page link "Start with a real fire".
- **Writing rules:** respectful and factual tone; name the crews only as NASA does; no hindsight claims ("this would have
  prevented…"). Phrase as "what today's data can and cannot say about these conditions".

### Acceptance
- Each in-scope incident loads in one click and every number on its card traces to `artifacts/incidents.json`.
- Apollo 1 shows "no evidence" for metrics outside the tested O₂ range, using the existing gate (no special-casing).
- Apollo 13 is shown with an "outside scope" badge and a sentence explaining why.

---

## R2 · Suppression calculator

**What the user sees:** a "Put it out" section (on `/bounds`, or a `/suppression` page) with a diluent picker (CO₂ or
helium) and a slider (0–70% CO₂ / 0–45% He). A curve shows the M1 chance that a droplet flame self-extinguishes, and the M2
extinction diameter, versus dilution, with 90% bands. A marker gives "dilution needed to reach 90% self-extinction" when
the curve gets there **inside tested conditions**.

### Engine (TL)
- `engine/suppression.py`: `curve(diluent, g, p_psia, o2, u, L, steps=15) -> {points:[{fraction, M1:{estimate, band90,
  applicable}, M2:{...}}], dose_for_p90, gate_notes}`. It holds the habitat O₂ and pressure and replaces nitrogen with the
  diluent (document this; FLEX compositions sum to 1 the same way).
- **Dilution-aware gate (required):** extend the applicability check so a query with CO₂ > 0 or He > 0 is "covered" only
  if a training test is within distance 2 in (O₂, ln p, CO₂, He). Scales: 0.05 for O₂, 0.3 for ln p, **0.10 for CO₂ and
  He [assumption; record as ADR-0006]**. Add the same dimensions to `engine/coverage.py` so the chart can show diluted
  tests. Expected result: suppression numbers exist for ISS-like air (13–25% O₂) and are gated at the 34% O₂ lunar base,
  which is itself a finding and should feed the test planner as a new candidate type ("dilution at 34% O₂").
- Reuse `bounds.predict(..., co2=, he=)`; no new model in v1. Validation: hold-out curves on FLEX diluted tests (AUC on
  the diluted subset), reported in `artifacts/validation_report.md`.

### API, AI, UI
- **AI:** `POST /suppression`; a cached explanation "How much CO₂ would it take at ISS air?".
- **FE:** curve chart with bands, the coverage chart reused with diluent points, the "dose for 90%" marker, and
  "Extrapolation: no evidence" for gated points (drawn as gaps in the curve, never interpolated).
- **Safety note (always visible):** CO₂ at fire-suppression concentrations is dangerous to breathe. Real spacecraft use
  CO₂ or water-mist extinguishers locally, not cabin flooding. This tool studies how dilution affects flames in the
  data; it is not an operating procedure.

### Acceptance
- ISS air with CO₂ gives a monotonic-looking curve with bands (verify against FLEX raw trends) and a dose estimate;
  lunar-base air gives "no evidence" at every CO₂ > 0, with the reason naming the 25% O₂ ceiling of the dilution tests.
- Tests: gate rejects 34% O₂ + CO₂; accepts 21% O₂ + 20% CO₂; curve JSON-safe; parity of the web gate with Python.

---

## R3 · Detection pillar (smoke vs lunar dust)

**What the user sees:** a `/detection` page answering "Would a smoke detector see this fire, and could lunar dust fool
it?", with smoke particle-size distributions for burning materials (SAME-R), dust particle measurements (DAFT), a
gravity vs no-gravity smoke comparison (PSI-115 simulation), and an overlap chart where smoke and dust sizes collide.

### Phase 0: feasibility spike (DE, ≤ 3 h, go/no-go before any UI work)
1. Download only the sample-description table, 3 SAME-R material files (e.g. lampwick, silicone, one more), 2 DAFT
   files, and the PSI-115 `*PSD.dat` files (gravity and the matching no-gravity runs, if present).
2. Write down each format: columns, units, bin edges, which number is particle diameter vs count.
3. **Go** if at least SAME-R binned sizes and DAFT dust sizes can be parsed into the same diameter axis. Otherwise ship
   R3 as a smaller "detection evidence" page (catalog + PSI-115 only) and say so.

### Build (if go)
- **DE:** `scripts/fetch_detection.py` (selected files only, sha256 manifest, same rules as `fetch_psi.py`);
  `engine/detection.py` → `artifacts/detection.json` with, per material, count-median diameter, geometric standard
  deviation and binned distribution; DAFT dust distribution; PSI-115 gravity vs no-gravity summary. Add `openpyxl` and
  `xlrd` to `requirements.txt`.
- **TL:** an overlap metric (share of smoke counts in size bins where dust is also present) and a plain-language
  detector note. The usual ionization-vs-photoelectric sensitivity ranges are [verify with a cited source] and must not
  be shown without one.
- **AI:** `GET /detection`; 2 cached answers ("Could lunar dust trigger the smoke alarm?", "Is smoke in space different?").
- **FE:** `/detection` page with log-scale size-distribution charts (smoke per material, dust, overlap shading), a
  materials picker, and a link from the Artemis II replay card.
- **Catalog:** detection-pillar evidence for PSI-101, 102, 47 and 115 now points to real data, not just keywords.

### Acceptance
- Every curve traces to a named PSI file and row range; units are shown on the axes.
- Gravity effects on smoke are shown only from the PSI-115 simulation and labelled "simulation".
- If the spike says no-go, the page states which data could not be parsed.

---

## Ownership (round 2)
| Role | Owns |
|---|---|
| TL | `engine/suppression.py`, gate extension in `engine/bounds.py` + `engine/coverage.py`, `engine/incidents.py`, the detection overlap metric, ADR-0006/0007, validation additions |
| DE | `data/incidents.json`, `scripts/fetch_detection.py`, `data/detection/`, `engine/detection.py`, `requirements.txt` (parsers), catalog pillar updates |
| AI | `/incidents`, `/suppression`, `/detection` endpoints, AI context + cache updates, manifest rebuild |
| FE | `/replay`, the suppression section, `/detection`, habitat-bar History group, E2E + a11y for all three |

## Order and timing (about one working day with the four agents in parallel)
| Step | Who | Depends on | Est. |
|---|---|---|---|
| 1. Incident sources verified + `incidents.json` | DE | — | 1.5 h |
| 1. Dilution-aware gate + ADR-0006 + tests | TL | — | 2 h |
| 1. Detection feasibility spike (go/no-go) | DE (after incidents) | — | 3 h |
| 2. `engine/incidents.py`, `engine/suppression.py` | TL | gate | 3 h |
| 2. `/incidents`, `/suppression` + AI cache | AI | step 2 engine | 2 h |
| 2. `/replay` page + suppression section | FE | API shapes (contract first) | 4 h |
| 3. Detection engine + API + page | DE, TL, AI, FE | spike = go | 5–6 h |
| 4. Rebuild artifacts → AI cache → manifest; full tests; E2E + a11y; docs + demo script update | team lead | all | 1.5 h |

R1 and R2 ship first (one commit per section). R3 follows only after the spike.

## Test plan additions
- pytest: incidents (sources, ranges, scope flag); dilution gate (accept/reject cases above); suppression curve shape and
  JSON-safety; detection parsers on the downloaded sample files (units, non-negative counts, bin order).
- vitest: web gate parity for diluents; chart helpers.
- Playwright: replay "Load habitat" flow, suppression slider online/offline, `/detection` render; axe on all new pages in
  both themes; demo path still under 2 minutes.

## Risks
| Risk | Mitigation |
|---|---|
| Incident values misremembered | Each value quoted from the cited NASA page; [verify] until checked; tests require a source |
| Replay reads as blame or hindsight | Writing rules above; reviewed by the PM role |
| Suppression numbers at untested O₂ | Dilution-aware gate is a hard prerequisite (step 1) |
| CO₂ read as a crew procedure | Always-visible safety note |
| Detection files unparseable or too large | Spike first; selected files only; fallback scope defined |
| Detector sensitivity claims without a source | Not shown until a citation is added |

## Demo integration
New 30-second opening: "This is Apollo 1's cabin atmosphere. Even with every test NASA has run since, Gravity Gap says
it has no evidence that air like this is safe." Then switch to the lunar base and continue the existing demo. The
suppression curve and the dust-vs-smoke chart become judge Q&A material.
