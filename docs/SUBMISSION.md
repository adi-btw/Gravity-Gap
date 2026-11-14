# Space Apps 2026 submission draft: Gravity Gap

Owner: TL (PM hat). Status: **draft (H5)**. Paste-ready text for the Space Apps project page. Items marked
**[verify]** must be checked by a human before submitting. Every number is taken from a committed artifact named next to it.

---

## Project title
**Gravity Gap: predicting fire behavior where no one has tested**

## One-line summary
NASA has fire data from orbit and from Earth but none from the Moon or Mars; Gravity Gap uses transparent physics and
1,710 real PSI combustion tests to predict fire behavior in partial-gravity habitats, shows exactly how sure it is (and
refuses when there is no evidence), and ranks the tests NASA should run next.

## Challenge
2026 NASA Space Apps Challenge: the SI-powered fire safety dashboard challenge (summarize, rank and interpret NASA
microgravity combustion investigations from the Physical Sciences Informatics (PSI) system). **[verify exact challenge
title and URL on the event site]**

## The problem
Crewed habitats for the Moon (1.62 m/s², 0.165 g) and Mars (3.71 m/s², 0.38 g) are being designed now, at reduced
pressure and raised oxygen (8.2 psia / 34% O₂ for a lunar base or pressurized rover; 10.2 psia / 26.5% O₂ for the
exploration atmosphere). PSI holds decades of microgravity (ISS, Cygnus) combustion data and some normal-gravity
references, but **no partial-gravity combustion data**. Future experiments (LUCI, FM2) will be the first. Designers
today must guess which existing evidence applies.

## What it does (by feature)
- **F0 Habitat selector.** Six presets (ISS, exploration vehicle, lunar base, lunar rover, Mars base, Earth) plus custom
  sliders. State lives in the URL (`?g=1.62&p=8.2&o2=0.34&u=10&L=10`, g in m/s²), so every view is shareable. Vent speed
  and flame size are marked "assumed, editable".
- **F1 Gravity spectrum map and ranking.** Every PSI investigation on a 0–1 g axis, with the Moon and Mars inside a
  "no direct data" zone, plus a relevance ranking for the chosen habitat with visible, editable score parts (atmosphere
  closeness, fire-safety pillar, fuel realism, outcome data, test count, regime fit). Non-combustion records are excluded
  with a note.
- **F2 Flame regime calculator.** Buoyant velocity, Richardson number and a forced / mixed / buoyant badge, with a
  regime map and Monte Carlo regime split.
- **F3 Pressure × gravity explorer.** The Grashof ratio G* = (g/g₀)(P/P₀)² heat map with habitat markers and an
  always-visible caveat (laminar flow structure only).
- **F4 Bounds panel.** Five response metrics (M1–M5) with an estimate, a 90% band, the 0 g and (where it exists) 1 g
  reference, a transfer-confidence badge, a sensitivity tornado and up to 20 nearest evidence rows. An **honesty
  gate** returns "Extrapolation: no evidence" (no number) when the habitat atmosphere is too far from every tested
  condition.
- **F5 Prediction ledger.** Predictions frozen as append-only JSON lines with a SHA-256 hash, committed to git and
  re-verified in the browser, so LUCI/FM2 results can confirm or refute them later.
- **F6 Test planner.** A ranked list of 10 candidate partial-gravity tests (score = band width × habitat weight × mixed
  fraction, greedy with a diversity penalty), each with a rationale and the investigations it extends, plus ventilation
  design implications.
- **F7 Investigation cards + Ask.** 26 cards from PSI metadata (objective, hypothesis, hardware, computed condition
  ranges, pillars, DOIs, flight → ground-study lineage) and a grounded AI assistant.
- **F8 Data explorer and export.** A filterable table of the clean tests with CSV/JSON export whose header cites the DOI
  of every included investigation.
- **Offline mode.** If the API is unreachable, every preset view falls back to precomputed artifacts and says so.

## How it uses NASA data
Source: NASA Physical Sciences Informatics (PSI), https://psi.nasa.gov, data licensed **CC0-1.0**. Raw experimental
tables (18 CSVs) were downloaded with a SHA-256 manifest (`data/raw_manifest.json`) and cleaned by
`scripts/clean_psi_tables.py` without inventing values (every fix is flagged; each row keeps `source_file` and
`source_row`). Outputs (`data/clean/CLEANING_REPORT.md`): **1,710 individual tests from 10 investigations**, 9
SAFFIRE-II microgravity-vs-normal-gravity samples, and 120 test-day condition summaries. Investigation metadata (title,
objective, hypothesis, publications) comes from the PSI API for all 26 records in `artifacts/catalog.json`.

DOIs below are from `artifacts/catalog.json` (catalog version `1.1.0+4dfd844b4112`).

| PSI ID | Investigation | DOI | How Gravity Gap uses it |
|---|---|---|---|
| PSI-69 | FLEX (Flame Extinguishment Experiment) | [10.60555/mbq8-0451](https://doi.org/10.60555/mbq8-0451) | 274 droplet tests. Trains **M1** (P(self-extinguish before burnout), n = 206) and **M2** (extinction diameter, n = 158); evidence rows; ranking; card |
| PSI-159 | ACME CFI-G | [10.60555/cyt1-kh64](https://doi.org/10.60555/cyt1-kh64) | 333 spherical-burner tests. Trains **M3** (P(gas flame self-extinguishes), n = 133 normal flames); ranking; card |
| PSI-99 | SAFFIRE-II | [10.60555/2chp-m469](https://doi.org/10.60555/2chp-m469) | 9 samples with microgravity vs normal-gravity outcomes: **M4** rule table (the only real 1 g reference); SAFFIRE hindcast (`artifacts/validation_saffire.md`) |
| PSI-98 | SAFFIRE-I | [10.60555/0t15-1z43](https://doi.org/10.60555/0t15-1z43) | 2 tests; M4 context; ranking; card |
| PSI-100 | SAFFIRE-III | [10.60555/040q-4h36](https://doi.org/10.60555/040q-4h36) | 2 tests; M4 context; ranking; card |
| PSI-107 | SPICE (Smoke Point In Co-flow) | [10.60555/9kbh-e962](https://doi.org/10.60555/9kbh-e962) | 434 tests; **M5** coflow-window rule table (407 ignited rows); ranking; card |
| PSI-10 | ACME / Flame Design | [10.60555/w4zy-bt45](https://doi.org/10.60555/w4zy-bt45) | 327 tests; ranking; planner "extends"; data explorer; card |
| PSI-25 | BASS-II | [10.60555/4qc4-de67](https://doi.org/10.60555/4qc4-de67) | 129 tests; M4 context; ranking; card |
| PSI-26 | BASS | [10.60555/58h4-dy80](https://doi.org/10.60555/58h4-dy80) | 121 tests; ranking; card |
| PSI-39 | CFI (Cool Flames Investigation) | [10.60555/m6pj-a914](https://doi.org/10.60555/m6pj-a914) | 79 tests; ranking; data explorer; card |
| PSI-20 | ACME BRE (Burning Rate Emulator) | [10.60555/vb93-3y72](https://doi.org/10.60555/vb93-3y72) | Test-day condition summaries (O₂, pressure ranges); ranking; card |
| PSI-21 | ACME CLD Flame | [10.60555/23e1-9950](https://doi.org/10.60555/23e1-9950) | Test-day condition summaries; ranking; card |
| PSI-22 | ACME E-FIELD Flames | [10.60555/se5a-8c73](https://doi.org/10.60555/se5a-8c73) | Test-day summaries; shown as the "buoyancy analog" marker on the spectrum map; card |
| PSI-23 | ACME s-Flame | [10.60555/k57n-p030](https://doi.org/10.60555/k57n-p030) | Test-day condition summaries; ranking; card |
| PSI-68 | FLEX-2 | [10.60555/byp8-h018](https://doi.org/10.60555/byp8-h018) | Test-day summaries; ranking; planner "extends"; card |
| PSI-106 | SLICE | [10.60555/pm12-rg61](https://doi.org/10.60555/pm12-rg61) | Test-day summaries; ranking; card (lineage to SPICE) |
| PSI-47 | DAFT / DAFT-2 | [10.60555/ztgj-d202](https://doi.org/10.60555/ztgj-d202) | Metadata: card, ranking (aerosol) |
| PSI-101 | SAME-R | [10.60555/2np7-jv14](https://doi.org/10.60555/2np7-jv14) | Metadata: card, ranking |
| PSI-102 | SAME | [10.60555/gd4k-8h62](https://doi.org/10.60555/gd4k-8h62) | Metadata: card, ranking, lineage to PSI-115 |
| PSI-60 | Computational and Experimental Analysis of SPICE Data Sets (ground) | [10.60555/mzjm-yv57](https://doi.org/10.60555/mzjm-yv57) | Metadata: lineage from SPICE; card |
| PSI-62 | Concurrent Flame Spread Modeling using Flamelet Generated Manifolds (ground) | [10.60555/e9xp-ex83](https://doi.org/10.60555/e9xp-ex83) | Metadata: lineage from BASS; its hypothesis is cited for the non-monotonic (low-flow) warning |
| PSI-115 | Utilization of the SAME Data for Advanced Modeling (ground) | [10.60555/q0v5-1v28](https://doi.org/10.60555/q0v5-1v28) | Metadata: lineage from SAME; card |
| PSI-117 | Effect of External Thermo-Convective Perturbation on Cool Flame Dynamics (ground) | [10.60555/gz0q-b577](https://doi.org/10.60555/gz0q-b577) | Metadata: lineage from FLEX; card |
| PSI-142 | Quantitative Studies of Cool Flame Transitions (ground) | [10.60555/80qf-vj95](https://doi.org/10.60555/80qf-vj95) | Metadata: lineage from FLEX; card |
| PSI-108 | STDCE-1 (fluids, not combustion) | [10.60555/j1z3-bw42](https://doi.org/10.60555/j1z3-bw42) | Listed and **excluded** from ranking as non-combustion |
| PSI-181 | Pb-Sn and Sn-Ag-Cu solders (materials, not combustion) | [10.60555/td9e-cz97](https://doi.org/10.60555/td9e-cz97) | Listed and **excluded** from ranking as non-combustion |

Preset atmospheres come from the challenge brief and NASA exploration-atmosphere values (`engine/presets.py`, each
preset cites its source). **[verify: the challenge brief names LUCI and FM2 as future partial-gravity sources]**

## Role of AI
- **Grounded, not generative, for numbers.** All numbers come from the engine (physics, models, rule tables, planner).
  The AI layer (`engine/ai/`) builds a context pack (habitat, engine outputs with ids, top catalog records, evidence
  rows) and answers questions about it.
- **Validated.** `engine/ai/validator.py` rejects any answer containing a number not in the context pack (±0.5%) or a
  citation (`PSI-xx`, `rec:…`, `doi:…`, `eng:…`) that does not resolve. Out-of-scope questions (rockets, propellants,
  weapons) are refused.
- **Three modes.** `claude` when `ANTHROPIC_API_KEY` is set and the `anthropic` package is installed; `cached` from
  `artifacts/ai_cache.json` (6 pre-generated, validated demo answers, including a refusal); `template`, a deterministic
  answer built from engine outputs. The demo works with no key and no network.
- **SI used in the engine.** Logistic regression with 500 bootstrap refits (M1, M3), linear quantile regression (M2),
  Monte Carlo uncertainty (2,000 seeded samples), a greedy test planner, and a transparent relevance ranker.
- Versioned prompts live in `engine/ai/prompts/`.

## Key findings (real numbers)
1. **A lunar base fire is in the mixed regime, the least-tested condition.** Lunar base (1.62 m/s², 8.2 psia, 34% O₂,
   vent 10 cm/s, 10 mm flame): u_b 25.5 cm/s, **Ri ≈ 6.48 (mixed)**; Monte Carlo **0% forced / 71.7% mixed / 28.3%
   buoyant** (`artifacts/bounds/lunar_base_M1.json`). With the rover's 5 cm/s vent it is buoyancy-dominated
   (Ri ≈ 25.9).
2. **Low g and low P stack.** G*(Moon, 8.2 psia) ≈ **0.0514** (`engine.physics.g_star`).
3. **ISS data transfers only with much stronger ventilation.** At lunar g a 10 mm flame is forced-regime (Ri < 0.1)
   only above ~80 cm/s vent (139 cm/s to cover 95% of samples); below ~8 cm/s it is buoyancy-dominated, so turning
   fans off does not make it ISS-like (`artifacts/planner.json` design implications).
4. **Estimates come with honest bands.** Lunar base M1 = **0.20**, 90% band **[0.012, 0.684]**, microgravity-only band
   [0.039, 0.482] widened ×1.64, transfer confidence **low** (`lunar_base_M1.json`). M3 = 0.872 [0.560, 0.985], low.
5. **The lunar atmosphere is mostly untested.** M2, M4 and M5 return **"no evidence"** at the lunar base: the nearest
   extinction-diameter test is 30% O₂ at 1.01 atm (distance 2.14 > gate 2); SAFFIRE-II and SPICE ran near 21–22% O₂
   at ~1 atm (`lunar_base_M2/M4/M5.json`).
6. **The planner targets exactly that gap.** Rank 1: extinction diameter (M2) at 1.62 m/s², 8.2 psia, 34% O₂, vent
   20 cm/s, score 1.0, extending PSI-69, PSI-10, PSI-159 (`artifacts/planner.json`).
7. **Five pre-registered predictions** GG-P0001..GG-P0005 (lunar base M1/M3, Mars base M1, lunar rover M3, exploration
   M3), hashed and committed (`ledger/predictions.jsonl`).
8. **Model quality on tested conditions** (5-fold out-of-fold, `artifacts/validation_report.md`): M1 AUC 0.824 (Brier
   0.081 vs 0.114 base rate); M2 median error 0.325 mm vs 0.803 mm baseline, 5–95% coverage 0.848 vs 0.90 nominal;
   M3 AUC 0.622 (weak, flagged). SAFFIRE-II hindcast: bridge 7/9 vs 3/9 for the naive "1 g = 0 g" baseline, but a constant "1 g burns more" guess also scores 7/9, so with n = 9 it does not yet show the bridge discriminates between materials (`artifacts/validation_saffire.md`).

## Limitations and honesty rules
- **No partial-gravity ground truth exists.** Partial-g bands are a stated assumption (widening factor
  1 + 0.5·mixed + 1.0·buoyant, ADR-0005), not a validated quantity.
- **Gravity does not move M1–M3 estimates**: droplet and burner tests had no imposed flow, so we widen the band and lower
  confidence instead of inventing a gravity effect.
- **Honesty gate**: if no training test is within atmosphere distance 2, no number is shown; the nearest tested condition
  is named instead.
- Scaling laws are order-of-magnitude (laminar, no radiation or detailed chemistry); coefficient ranges are assumptions.
- M3 discrimination is weak (AUC 0.622); M2 bands under-cover (0.848 vs 0.90). Habitat queries at L = 10 mm use the
  largest tested droplet (4.67 mm), an edge of the training range.
- **Decision support for research prioritization, not a safety certification.** The tool never says "safe".
- Rocket and propellant combustion are out of scope.

## Tools and technology
- **Engine:** Python 3.13, NumPy, SciPy, pandas, scikit-learn (`engine/`).
- **API:** FastAPI, Pydantic v2, Uvicorn; RFC 7807 errors; manifest-hash integrity check on `/health`.
- **Web:** Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS v4, hand-built SVG charts; physics ported to
  TypeScript and checked against shared fixtures.
- **AI:** Anthropic Claude (optional at runtime) with a deterministic validator; cached and template fallbacks.
- **Testing:** pytest (331 passing at the time of writing), vitest (81 at commit `8be1f82`), Playwright E2E + axe
  accessibility checks **[verify: FE E2E status]**; GitHub Actions CI.
- **Deploy:** Docker / docker compose and hosted deploy (see [docs/DEPLOY.md](DEPLOY.md)) **[verify]**.
- Built with help from Claude Code (AI coding assistant). **[verify: Space Apps AI-use disclosure rules]**

## Team
| Role | Responsibilities |
|---|---|
| TL: Tech Lead / Physics (+ PM hat) | Physics engine, Monte Carlo, bounds models M1–M3, honesty gate, test planner, validation, demo and submission |
| DE: Data Engineer | PSI fetch and cleaning, catalog, ranking, M4/M5 rule tables, SAFFIRE hindcast |
| FE: Frontend Engineer | Web app, design system, accessibility, E2E, demo video |
| AI: AI / Backend Engineer | FastAPI, AI layer and validator, prediction ledger, CI, deploy |

**[verify: team member names and Space Apps usernames]**

## Links
- Repository: `https://github.com/adi-btw/NASA-Hackathon-2026` **[verify: make public or share with judges]**
- Live app: `<LIVE_WEB_URL>` **[fill from docs/DEPLOY.md]**
- API docs: `<LIVE_API_URL>/docs` **[fill]**
- Demo video: `<VIDEO_URL>` **[fill; source file in docs/media/]**
- Demo script: [docs/DEMO_SCRIPT.md](DEMO_SCRIPT.md)

---

## Human submission checklist (H5)
Do these in order; tick when done.

- [ ] **Verify the current Space Apps rules on the event site** (spaceappschallenge.org): submission deadline and time
      zone, required fields, video length limit, whether a live link is required, AI-use disclosure, NASA branding and
      logo rules, data-citation rules. Update this file where it says **[verify]**.
- [ ] Confirm the team page lists every member.
- [ ] Final artifact rebuild by the team lead: engine artifacts → `python -m engine.ai.answer --build-cache` →
      `python scripts/build_manifest.py`; then `curl <api>/health` shows `manifest_ok: true`.
- [x] SAFFIRE hindcast numbers inserted into Key findings from `artifacts/validation_saffire.md`.
- [ ] Re-check every number in this file and `docs/DEMO_SCRIPT.md` against the rebuilt artifacts.
- [ ] Deploy (docs/DEPLOY.md); open the live URL in a private window; run the 2-minute path online and offline.
- [ ] Make the repo public, or share it with the judges' accounts, as the team decides. Check no secrets are committed
      (`.env` is ignored; `.env.example` only).
- [ ] Upload the demo video (from `docs/media/`) to an allowed host; check it plays logged-out; paste the URL.
- [ ] Paste title, summary and sections above into the Space Apps project page; add links.
- [ ] Submit the form before the deadline (target M7, 2 h buffer); save the confirmation (screenshot or email).
- [ ] Update `plan/STATUS.md` (H5 done, confirmation reference).
