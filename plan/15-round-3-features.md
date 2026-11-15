# 15 · Round 3 features: briefing, honesty test, uncertainty drivers, compare, atmosphere map

Back to [overview](00-overview.md). Follows [13 · Round 2 features](13-round-2-features.md) (R1 replay, R2 suppression,
R3 detection evidence). Same team roles (TL, DE, AI, FE), same rules: contract first, one commit per section with an
explanation, every number traces to a PSI file or an engine output, "no evidence" is shown instead of a guess.

| Code | Feature | Answers the judge question | Size | Depends on |
|---|---|---|---|---|
| **S1** | Habitat fire-safety briefing | "What does a mission planner get from this?" | M | S2, S3, S4, existing engine |
| **S2** | Honesty test (hold out tested atmospheres) | "Can I trust it?" | M | existing models |
| **S3** | What drives the uncertainty | "What should NASA test next?" | M | existing Monte Carlo + models |
| **S4** | Side-by-side habitat compare | "What changes between ISS and the Moon?" | S | existing `/bounds` |
| **S5** | Atmosphere evidence map | "Which cabin air does the evidence support?" | M–L | S2 (trust), cited crew limits |

Suggested order: **S4 → S3 → S2 → S1 → S5**. S4 is quick and reused by S1; S3 and S2 feed sections of the briefing;
S5 is last because it needs a sourcing step and carries the most wording risk.

---

## Facts checked in the code before planning (2026-11-14)

- **Each fitted model comes from one investigation.** M1 (droplet self-extinction, 206 tests) and M2 (extinction
  diameter, 158 tests) are trained on FLEX (PSI-69) only; M3 (gas flame self-extinction, 133 tests) on CFI-G (PSI-159)
  only. So "hide one investigation and retrain" is impossible for the fitted models: there would be no training data
  left. S2 therefore hides **whole tested atmospheres** (O₂ × pressure × diluent groups) inside an investigation
  instead, which tests exactly the claim the app makes: "near tested air we can give a number, far from it we say no
  evidence". The cross-investigation check that does exist (SAFFIRE hindcast, 7/9 vs a 3/9 baseline) is reused as-is.
- **A one-at-a-time sensitivity chart already exists.** `engine/bounds.py` returns `sensitivity` (low/high swing per
  parameter, the "C11 tornado") and `web/components/BoundsPanel.tsx` draws it; `engine/validation.py`
  `sensitivity_summary()` names the top parameter per preset. S3 must add something new: the **share of the band**
  each source of uncertainty causes (including model uncertainty and the gravity widening, which the tornado does not
  cover), and a "what would shrink it" link to the Planner.
- **Monte Carlo inputs** (`engine/montecarlo.py`): C_b ~ U[0.5, 1.5], k ~ U[0.3, 1.0], ΔT/T ~ U[3, 6],
  L ~ L_mm × U[0.5, 1.5], independent. M1 has a 500-refit bootstrap (`engine.models.get_model`).
- **Presets:** iss, exploration, lunar_base, lunar_rover, mars_base, earth (`engine/presets.py`).
- **Pillars already available per habitat:** prevention (M3 gas flames; M4 SAFFIRE solids: silicone, SIBAL
  cotton-fiberglass, PMMA, PMMA & Nomex), behaviour (M1, M2, M5 coflow), suppression (R2 curves), detection (R3; not
  habitat-dependent except the labelled gravity simulation), incidents (R1), coverage (`engine/coverage.py`),
  planner, ledger.
- **At the lunar base today:** M1 = 0.20 and M3 = 0.87 are covered; M2, M4, M5 are "no evidence".
- **Crew breathing limits are not in the repo.** S5 must not draw any limit line until a NASA source is cited.

---

## S4 · Side-by-side habitat compare (do first, small)

**What the user sees:** `/compare?a=iss&b=lunar_base` with two habitat pickers (presets or the current custom
habitat) and one row per metric M1–M5: estimate + 90% band for each side, the regime (forced / mixed / buoyant), the
coverage verdict, and a plain-language "what changed" line (e.g. "Moving from ISS to the lunar base adds weak
buoyancy (mixed regime) and raises O₂ from 21% to 34%; M2 loses its evidence").

**Build**
- **TL:** `engine/compare.py` `compare(a, b)` → for each metric both `bounds.predict` results plus a `diff` block:
  regime change, coverage change, estimate change only when both sides are covered (never subtract a number from "no
  evidence"). Rule for "what changed": list the habitat inputs that differ, then the metrics whose coverage or regime
  flipped. Contract addendum "Round 3 · S4 Compare".
- **AI:** `POST /compare` (two habitats in the existing habitat schema) and a cached answer "What changes between ISS
  and the lunar base?" citing both sides.
- **FE:** `/compare` page reusing the Bounds band component for each side (two columns on desktop, stacked on phone);
  URL keeps both habitats; nav item; a "Compare with…" button on `/bounds`.

**Acceptance:** no difference is shown when either side is "no evidence"; bands use the same axis per metric so the
widths can be compared by eye; works offline from the bounds artifacts for preset pairs.

**Tests:** pytest diff rules (covered vs not, regime flip); vitest URL round-trip; Playwright ISS vs lunar base shows
M2 "no evidence" on the right only; axe both themes.

---

## S3 · What drives the uncertainty (variance shares + "what would shrink it")

**What the user sees:** on `/bounds` (and in the briefing) a stacked bar per metric, e.g. "Of this band's width, about
55% comes from flame temperature (ΔT/T), 25% from how strongly the vent flow mixes (k), 15% from the model itself
(limited tests), 5% from the gravity widening." (illustrative wording; real shares come from the engine). Under it:
"Biggest lever: a test that pins down ΔT/T at 34% O₂ would shrink this band the most → see Planner".

**Method (TL owns, ADR-0008)**
- Sources of uncertainty, each its own share: the four Monte Carlo inputs (C_b, k, ΔT/T, L), **model uncertainty**
  (bootstrap refits for M1; quantile spread for M2; the equivalent for M3), and the **gravity widening factor**
  (ADR-0005).
- Shares: first-order variance-based (Sobol-style) indices from the existing samples. Simple estimator: bin each
  input into deciles, share_i = Var(E[output | bin_i]) / Var(output). Model uncertainty share = variance across
  bootstrap refits at fixed physics. Gravity share = the extra width the widening adds, as a fraction of the final
  width. Report the remainder ("interactions / not split") rather than forcing shares to sum to 100%.
- Seeded and deterministic; reuse `n = 2000` samples; must stay under ~1 s per metric after the first model fit.
- "Biggest lever" = the source with the largest share. If it is model uncertainty, the lever is "more tests near this
  atmosphere" and the link goes to the Planner candidate nearest the habitat. If it is a physics input, the text names
  the input and says it comes from engineering assumptions, not PSI data.
- Only for covered metrics. "No evidence" metrics show no breakdown.

**Build**
- **TL:** `engine/uncertainty.py` `drivers(metric, habitat)`; validation: on a synthetic function with known Sobol
  indices the estimator is within ±0.05; on real metrics shares are in [0, 1] and the remainder ≥ −0.05.
- **AI:** add `drivers` to the `/bounds` response (new optional field, contract addendum) and to the AI context
  (citation `eng:drivers:<metric>`); cached answer "Why is the lunar base band so wide?".
- **FE:** stacked bar under each band on `/bounds` (screen-reader text lists the shares); keep the existing tornado
  under a "one-at-a-time view" disclosure so the two charts are not confused.

**Acceptance:** each share is labelled with its source and whether it is a PSI-data or engineering-assumption source;
shares are rounded to 5% in the UI so they do not look more precise than they are; the method is explained in one
sentence plus a link to ADR-0008.

**Tests:** estimator on a known function; determinism with a fixed seed; covered vs not covered; Playwright: lunar
base M1 shows a breakdown, M2 does not.

---

## S2 · Honesty test: hold out tested atmospheres

**Question it answers:** "When the app says 'covered' and gives a 90% band, how often does the truth land inside? And
when it says 'no evidence', was that the right call?"

**Method (TL owns, ADR-0009)**
1. Group each fitted model's training tests by tested atmosphere: (O₂, pressure, CO₂, He) rounded as in
   `engine/coverage.py` (FLEX groups for M1/M2, CFI-G groups for M3).
2. For each group: drop the whole group, refit the model (bootstrap with a reduced `n_boot`, e.g. 200, for speed), then
   ask the app about that group's atmosphere exactly as a user would (`bounds.predict` with the held-out model).
3. Record per group:
   - **Gate call:** would the honesty gate (distance ≤ 2, diluent rule) have said "covered" without these tests?
   - **Band hit:** if covered, did the held-out observed result (M1/M3: share of self-extinctions; M2: observed
     diameters) fall inside the 90% band? For small groups use a binomial interval on the observed rate and count a
     hit when the intervals overlap; state that rule on the page.
   - **Error:** estimate vs observed, plus the Brier score for M1/M3 against a "training average" baseline.
4. Summaries: band coverage among covered groups (target ≈ 90%, shown with its own interval because groups are few),
   gate precision ("covered" calls that were right), and the list of groups where the app was confidently wrong.
5. Reuse the SAFFIRE hindcast (M4) as the cross-investigation section, unchanged, with its caveat (not
   discriminative).

**Honesty rules:** results are published even if bad; a bad result changes the engine (wider band, stricter gate)
only through a new ADR, never silently. The page shows how many groups there are; with fewer than 10 groups the text
says the test is weak.

**Build**
- **TL (+ DE for grouping):** `engine/holdout.py` → `artifacts/holdout.json` (per group: metric, atmosphere, n tests,
  PSI rows, gate call, band, observed, hit, error) + summary; added to `validation_report.md`. Runtime target under
  5 minutes in CI; if longer, build the artifact offline and have CI check its hash plus a small subset.
- **AI:** `GET /holdout`; cached answer "How do you know it works?" citing the summary and the worst miss.
- **FE:** `/trust` page "Can I trust it?": scorecard (band coverage, gate precision, SAFFIRE hindcast), the held-out
  groups on the O₂ × pressure map (hit = filled, miss = hollow with a cross, not covered = grey; shapes, not colour
  alone), and a table of misses. Linked from `/about` and the Bounds panel ("How often are these bands right? →").

**Acceptance:** every row names the held-out tests' PSI rows; summary rates show their sample size; no group is left
out without a stated reason.

**Tests:** pytest on a tiny synthetic dataset where the right answer is known (gate says "no evidence" for a far
group; bands hit for a near group); determinism; JSON-safe artifact; Playwright `/trust` renders; axe both themes.

---

## S1 · Habitat fire-safety briefing

**What the user sees:** `/briefing?habitat=lunar_base` (any preset or custom habitat) and a "Download PDF" / print
button. One page, in this order:
1. **Habitat line:** gravity, pressure, O₂, vent speed, flame size, marking which values are assumed.
2. **Verdict strip:** one chip per pillar (Prevention, Flame behaviour, Detection, Suppression): "evidence",
   "partial" or "no evidence", each chip following a rule written in the contract (e.g. Prevention = "evidence" only
   if M3 and M4 are both covered).
3. **Key numbers:** each covered metric's estimate and band in one cited sentence.
4. **What drives the uncertainty** (S3), one line per covered metric.
5. **Known gaps:** the "no evidence" metrics with their nearest tested atmosphere and distance (from coverage), the
   detection gaps (lunar dust, detector sensitivity), the suppression gate note.
6. **Recommended next tests:** the top 3 Planner candidates for this habitat.
7. **History check:** the closest R1 incident atmosphere and how it compares (only where it informs; R1 wording rules,
   no blame).
8. **How far to trust this:** one line from S2 ("bands held for X of Y held-out atmospheres").
9. **Footer:** model versions, artifact manifest hash, date, "not an operating procedure".

**Build**
- **TL:** `engine/briefing.py` `briefing(habitat)` composing existing engine calls (bounds, coverage, suppression,
  detection gaps, planner, incidents, S3, S2 summary) into one JSON; pillar verdict rules in ADR-0010. No new
  modelling.
- **AI:** `POST /briefing`; narrative sentences from the grounded template mode by default (deterministic and
  validated: numbers ±0.5%, every claim cited), optional Claude path behind the same validator; cached briefings for
  the six presets; manifest rebuild.
- **FE:** `/briefing` page with print CSS (A4 and Letter, one page for presets, readable in black and white); a
  "Briefing" button in the habitat bar; PDF through the browser's print-to-PDF (no server PDF dependency); works
  offline from the cached preset briefings.

**Acceptance:** every number in the briefing appears in an engine output; every pillar chip follows its written rule;
the lunar base briefing lists M2/M4/M5 under "Known gaps", not as numbers; every preset prints on one page.

**Tests:** pytest briefing shape for all presets; validator passes on all six cached briefings; Playwright: open from
the habitat bar, print emulation (`page.emulateMedia({ media: "print" })`) fits one page; axe both themes.

---

## S5 · Atmosphere evidence map (renamed from "safest-atmosphere finder")

**Why renamed:** the data cannot honestly name a "safest" atmosphere. The fitted models cover a narrow range of
tested air, the metrics measure different things (self-extinction probabilities, extinction size, burn extent), and
crew limits are outside the PSI data. What the app can show honestly is **a map of what the evidence says across
cabin atmospheres**, with crew limits overlaid only from a cited NASA source.

**What the user sees:** `/atmospheres` for a chosen gravity and vent speed: an O₂ (x) × pressure (y, log) map.
- For a chosen metric (M1 or M3 first), each cell is coloured by the estimate **only where the gate says covered**;
  uncovered cells are hatched "no evidence". The share of the map with evidence is shown as a number.
- Markers: the six presets, the R1 incident atmospheres, and the tested-atmosphere points (as on the coverage chart).
- **Crew-limit overlay (hidden until sourced):** minimum O₂ partial pressure, maximum O₂ fraction, and the
  spacewalk-prebreathe trade-off behind 8.2 psia / 34% O₂, each line with its citation [verify: source documents and
  values, e.g. NASA exploration-atmosphere working group reports]. Without a cited source the toggle is not shown.
- A plain-language reading generated from the grid, for example where the evidence ends relative to the lunar base.
- Click a cell → load that atmosphere into the habitat bar (then Bounds, Compare or Briefing).

**Build**
- **DE:** sourcing spike (≤ 2 h): find and cite NASA documents for crew O₂ limits and the 8.2 psia / 34% choice;
  record values in `data/crew_limits.json` (number, unit, source, page, short quote ≤ 15 words). If none is found, S5
  ships without the overlay and says so.
- **TL:** `engine/atmosphere_map.py` → grid (O₂ 0.15–0.40, pressure 4–16 psia, about 26 × 20 cells) per metric and
  gravity preset, using `bounds.predict` with the gate; cached as `artifacts/atmosphere_map/{metric}_{g}.json`; reuse
  model fits; target under 30 s per grid offline. ADR-0011: "the map never ranks atmospheres; it shows evidence".
- **AI:** `GET /atmosphere-map/{metric}?g=`; cached answer "What cabin air does the evidence support?" that must state
  the no-evidence share of the map.
- **FE:** heat-map SVG with a hatch pattern for no evidence, colour-blind-safe sequential scale with a legend in
  probability units, labelled markers, keyboard navigation (or a table view), click-to-load.

**Acceptance:** no colour in uncovered cells; no limit line without a citation; the word "safest" does not appear on
the page; the evidence share is shown.

**Tests:** pytest: the grid uses the gate (a far cell is null), JSON-safe, crew-limit file schema requires a source
per value; Playwright: hatch present, click loads the habitat; axe both themes.

---

## Ownership (round 3)
| Role | Owns |
|---|---|
| TL | `engine/compare.py`, `engine/uncertainty.py`, `engine/holdout.py`, `engine/briefing.py`, `engine/atmosphere_map.py`, ADR-0008…0011, contract addenda |
| DE | crew-limits sourcing spike, `data/crew_limits.json`, held-out group definitions checked against the cleaned tables |
| AI | `/compare`, `/bounds` drivers field, `/holdout`, `/briefing`, `/atmosphere-map`; AI context, citations, cached answers, manifest |
| FE | `/compare`, Bounds drivers bar, `/trust`, `/briefing` (+ print), `/atmospheres`; nav; E2E + axe |

## Order and timing (about two working days with four agents)
| Step | Who | Depends on | Est. |
|---|---|---|---|
| 1. S4 compare engine + API + page | TL, AI, FE | — | 3 h |
| 1. Crew-limits sourcing spike | DE | — | 2 h |
| 2. S3 drivers (method, ADR-0008, check on a known function) | TL | — | 3 h |
| 2. S2 holdout engine + artifact | TL (+ DE) | — | 4 h |
| 3. S3 UI + AI; S2 `/trust` page + AI | FE, AI | step 2 | 4 h |
| 4. S1 briefing engine, cached briefings, page + print | TL, AI, FE | S2, S3, S4 | 5 h |
| 5. S5 map engine + page (overlay only if sourced) | TL, AI, FE | S2, spike | 5 h |
| 6. Rebuild artifacts → AI cache → manifest; full tests; demo script update | team lead | all | 1.5 h |

One commit per section; CI green before the next section starts.

## Test plan additions (summary)
- pytest: compare diff rules; Sobol estimator on a known function; holdout on synthetic data; briefing for all
  presets; map gate; crew-limit schema.
- vitest: URL state for compare and briefing; share rounding; map colour scale and hatch rule.
- Playwright: compare flow; drivers bar; `/trust`; briefing print fits one page; atmosphere map click-to-load; axe on
  all new pages in both themes; demo still under 2 minutes.

## Risks
| Risk | Mitigation |
|---|---|
| S2 shows the bands are too narrow | Publish it; respond with an ADR (widen bands or tighten the gate); in the pitch this is a strength |
| Few held-out groups → noisy rates | Show sample size and an interval on every rate; say "weak test" below 10 groups |
| S3 shares look more precise than they are | Round to 5%; show the "not split" remainder; one-sentence method |
| Briefing reads like an operating procedure | Fixed footer; R2 safety-note wording rules; verdict rules written down |
| S5 read as a recommendation | Renamed; no ranking; "no evidence" hatch; no crew limits without citations |
| Holdout refits too slow for CI | Reduced bootstrap; offline artifact + hash check in CI |

## Demo integration
Close the demo on the briefing: "Here is everything Gravity Gap can tell a lunar base designer, on one page, and what
it can't." If a judge asks "how do you know?", open `/trust`. If asked "what should NASA do next?", point to the
uncertainty breakdown and its Planner link. Use `/compare` (ISS vs lunar base) as the opening contrast.
