# Crew atmosphere limits for the S5 overlay (sourcing spike, 2026-11-14)

Data: `data/crew_limits.json`. Schema test: `tests/test_crew_limits.py`. Every value has a NASA URL, a page or
section, and a verbatim quote of 15 words or fewer. Values from conference papers are labelled as program baselines.

## Verdict: GO, with one caveat on the max-O₂ line

| Overlay line | Status | Source |
|---|---|---|
| Minimum O₂ (hypoxia) | **GO**, agency standard | NASA-STD-3001 Vol 2 [V2 6003], Table 6.2-1 |
| Minimum total pressure | **GO**, agency standard | NASA-STD-3001 Vol 2 [V2 6006] |
| 8.2 psia / 34 % O₂ and the reason for it | **GO** | NTRS 20150021491 (HRP evidence report), plus the standard's table |
| Maximum O₂ fraction (flammability) | **PARTIAL**: sourced, but as 2007 program baselines, not as a standard | NTRS 20070018178 |

## What was found

**Minimum O₂.** NASA-STD-3001 limits **inspired** O₂ (PIO₂), not the dry-air O₂ partial pressure:
`PIO₂ = (PB − 47) × FIO₂`, with PB in mmHg (47 mmHg is water vapour at body temperature).
- Mild hypoxia lower limit: **127 mmHg (2.46 psia)**, a 1-hour time-weighted average, allowed indefinitely with
  health monitoring. The table lists the 8.2 psia / 34 % O₂ exploration atmosphere as an example.
- Absolute floor: **122 mmHg (2.36 psia)**.
- Normoxia target: **145 to 155 mmHg (2.80 to 3.00 psia)**.
- Also in the table but off the map: an indefinite hyperoxia upper limit of 356 mmHg and a short-term (6 to 9 h
  prebreathe) limit of 791 mmHg. The schema has no "ppO₂ max" quantity, so these are not in the JSON.

**Total pressure.** 5 psia < p ≤ 15.0 psia (34.5 to 103 kPa) for indefinite exposure. The rationale explains the
5.0 psia figure: with at least 30 % diluent gas and normoxia and CO₂ limits held, it is the lowest cabin pressure
that can be reached. The ebullism threshold (0.91 psi) appears in OCHMO-TB-003 but is not a habitable limit.

**Maximum O₂ fraction.** No agency standard sets a single cabin O₂ cap for flammability.
- NASA-STD-6001 is a test method: materials are tested in the worst atmosphere each vehicle expects, so each
  program sets its own maximum.
- NASA-STD-3001 [V2 6002] requires at least 30 % diluent gas. That caps O₂ at 70 %, but the reason is lung
  collapse (atelectasis), not fire, and 70 % is off the map.
- The flammability caps found are the 2007 Constellation baselines (NTRS 20070018178): **30 % O₂ for Orion** and
  **34 % O₂ for the lunar lander (LSAM)**. The paper adds "these numbers may change". The same paper gives the ISS
  nominal maximum as **24.1 %**.
- NTRS 20110008636 shows the cap depends on pressure. A material certified at 30 % O₂ and 10.2 psia stays certified
  at 14.7 psia only up to about **25.6 % O₂**. At a fixed O₂ partial pressure, flammability is worst at low total
  pressure.

**Why 8.2 psia / 34 %.** Source: NTRS 20150021491, which summarises the EAWG and the 2012 action team.
- The 2006 EAWG recommended 8.0 psia / 32 % for EVA-heavy phases. Its trade space was hypoxia, flammability and
  decompression sickness (DCS). It judged 8.0 / 32 "mildly hypoxic" with "acceptable flammability risk" and a low
  prebreathe overhead.
- In 2012 the atmosphere was changed to 8.2 / 34 "to reduce the hypoxic stress". This added 11 mmHg of alveolar O₂
  without changing DCS risk or materials concerns, and an HEOMD memo (Feb 2013) adopted it.
- The EVA benefit: cabin ppN₂ drops from 11.6 to 5.4 psia, so about a 15-minute O₂ prebreathe and suitport EVA
  become possible.
- PIO₂ at 8.2 / 34 is 128 mmHg, about the same as the Shuttle's 10.2 psia / 26.5 % staging atmosphere (127 mmHg).
  So the exploration atmosphere sits right on the 127 mmHg mild-hypoxia line by design.

**ISS nominal.** 14.7 psia / 21 % O₂ (OCHMO-TB-003, p.8; also NTRS 20150021491).

## How FE draws each item (x = O₂ fraction 0.15 to 0.40, y = total pressure 4 to 16 psia, log)

| Item | Shape | Formula / position |
|---|---|---|
| PIO₂ 127 mmHg (mild hypoxia limit) | solid curve | `x = 127 / (p_psia × 51.715 − 47)`. On the map it runs from about (0.40, 7.05 psia) through (0.34, 8.2) and (0.264, 10.2) to (0.163, 16). Cells below or left of it are under the limit. |
| PIO₂ 122 mmHg (absolute floor) | dashed curve | `x = 122 / (p × 51.715 − 47)` |
| PIO₂ 145 to 155 mmHg (normoxia target) | optional light band | the same formula for 145 and 155. Label it "target", not "limit". |
| Total pressure > 5 psia | horizontal line at 5.0 psia | the bound is exclusive. Optionally shade the area below it. |
| 34 % O₂ (LSAM 2007 baseline) | vertical line at x = 0.34 | Label: "34 % O₂ max: 2007 lunar-lander baseline (materials)". |
| 30 % O₂ (Orion 2007 baseline) | vertical line at x = 0.30 | same style as the 34 % line |
| 24.1 % O₂ ISS max | short tick at x = 0.241 near 14.7 psia | ISS context only |
| 25.6 % at 14.7 psia | point, not a line | shows that the O₂ cap depends on pressure |
| 8.2 / 34, 8.0 / 32 (superseded), 10.2 / 26.5, 14.7 / 21 | markers | `reference_atmosphere` entries: `value` = psia, `o2_percent` |
| 70 % O₂ (30 % diluent) | do not draw | off the map, and it is a lung limit, not a fire limit |

Important: the hypoxia line is **not** `p × x = const`. Because of the 47 mmHg water-vapour term it bends further
away at low pressure. Using dry ppO₂ would put the line in the wrong place: at 8.2 / 34 the dry ppO₂ is 144 mmHg, but
PIO₂ is only 128 mmHg.

## Caveats (must stay next to the overlay)
- The limits depend on mission phase, duration and document. 127 mmHg is allowed only with health monitoring
  ("no opportunity to collect data in microgravity" for exploration-length missions). The O₂ caps are program
  baselines from 2007, not standards.
- The NASA-STD-3001 web edition (updated Apr 21, 2026) shows no revision letter. OCHMO-TB-003 Rev A cites the same
  requirements as Vol 2 Rev D. The Table 6.2-1 values were read from the table image on nasa.gov.
- The EAWG final report (NASA/TP-2010-216134) and the 2013 HEOMD memo were not retrieved directly. Their content
  comes from NTRS 20150021491 and NTRS 20130013505 (NASA/TM-2013-217377).
- The lines show crew and materials limits. They do not say how safe a fire would be, and they are not a ranking of
  atmospheres. Keep the S5 rule: no ranking, and never use the word "safest".
