# Gravity Gap: demo script

Owner: TL (PM hat). Plan context: [plan/11-demo-pitch.md](../plan/11-demo-pitch.md). Every number below is read from a
committed artifact; the source is named next to it. If an artifact is rebuilt, re-check this page against it before
rehearsing (`artifacts/bounds/lunar_base_M*.json`, `artifacts/planner.json`, `ledger/predictions.jsonl`).

**Demo habitat: Lunar base** (1.62 m/s² = 0.165 g, 8.2 psia, 34% O₂, vent 10 cm/s assumed, flame size 10 mm).
We use the lunar base, not the rover, because it is the **mixed** regime (Ri ≈ 6.48), the condition no PSI test covers.
The rover (vent 5 cm/s) is buoyancy-dominated (Ri ≈ 25.9) and is used only as a one-line contrast.

## 0. Setup (before judges arrive)

```bash
# terminal 1, repo root
python -m uvicorn api.main:app --port 8000
# terminal 2
cd web && npm run build && npm start        # production build on http://localhost:3000
```

Open these tabs in order (all share the same habitat query, so nothing needs typing during the demo):

| Tab | URL (localhost:3000) |
|---|---|
| 1 | `/` |
| 2 | `/regime?g=1.62&p=8.2&o2=0.34&u=10&L=10` |
| 3 | `/regime?g=1.62&p=8.2&o2=0.34&u=10&L=10&tab=pressure` |
| 4 | `/bounds?g=1.62&p=8.2&o2=0.34&u=10&L=10&metric=M1` |
| 5 | `/ledger` |
| 6 | `/planner` |

`g` is in m/s² (1.62 = Moon), `p` in psia, `o2` a fraction, `u` in cm/s, `L` in mm. Check the header chip says
**live API**. Close the Ask drawer. Zoom the browser to 110–125% so numbers read on a projector.

## 1. The 2-minute demo (second by second)

| Time | Screen / action | Say (approximately) | On-screen number to point at | Source |
|---|---|---|---|---|
| 0:00–0:12 | Tab 1, landing. Point at "the gap" graphic. | "NASA has hundreds of fire tests in orbit and on Earth, and none at Moon or Mars gravity, where crews will live next. Those habitats are planned at 8.2 psia and 34% oxygen." | Moon and Mars inside the hatched **no data** zone | `web/app/page.tsx`, PSI catalog |
| 0:12–0:22 | Pick **Lunar base** in the picker. | "One click sets the habitat; every panel and the URL switch to it." | Habitat bar: 1.62 m/s² · 8.2 psia · 34% O₂ · vent 10 cm/s (vent tagged *assumed, editable*) | `engine/presets.py` |
| 0:22–0:40 | Tab 2, Regime Calculator. | "At lunar gravity the flame's own buoyancy, 25 cm/s, and the cabin fan, 10 cm/s, are comparable. Richardson number 6.5: the **mixed** regime. Neither ISS data nor Earth data applies directly. Across our uncertainty sampling it's 72% mixed, 28% buoyant, zero forced." | u_b **25.5 cm/s**, Ri **6.48**, badge **MIXED**; Monte Carlo **0% / 71.7% / 28.3%** | `engine.physics.evaluate`; `artifacts/bounds/lunar_base_M1.json` `regime_fractions` |
| (optional, +5 s) | Drag vent to 5 cm/s (= lunar rover). | "Turn the fans down and it goes fully buoyant, not ISS-like." | Ri **25.9**, **BUOYANT** | `engine.physics.evaluate` (lunar_rover) |
| 0:40–0:50 | Tab 3, Pressure × Gravity. | "Low gravity and low pressure stack: the buoyancy driving term is about 5% of Earth's." | G\* **0.051** (0.0514); caveat banner visible | `engine.physics.g_star(1.62, 8.2)` |
| 0:50–1:10 | Tab 4, Bounds, metric M1. Hover one evidence chip. | "Here is a prediction: the chance a droplet flame self-extinguishes before burnout. 20%, but with a 90% band from 1% to 68%. The microgravity-only band was 4% to 48%; we widen it 1.6 times because 100% of these flames feel buoyancy the ISS tests never had. Transfer confidence: low, and we say so. Every point traces to a real test." | Estimate **0.20**, band **[0.012, 0.684]**, 0 g band **[0.039, 0.482]**, widened **×1.64**, confidence **low**, n = **206** FLEX tests; nearest evidence `PSI-69:FLEX:20` | `artifacts/bounds/lunar_base_M1.json` |
| 1:10–1:20 | Click **Explain**. | "The AI explains it, and every number it uses is checked against the engine, with citations." | Answer with `[eng:M1]`, `[PSI-69]`, `[rec:PSI-69:FLEX:20]` chips; validated | `artifacts/ai_cache.json` ("Why is the M1 band wide for the lunar base?") |
| 1:20–1:32 | Switch metric to **M2** (extinction diameter). | "And here's the moment we're proudest of. For this metric the tool refuses to give a number. The nearest tested atmosphere is 30% oxygen at 1 atmosphere, too far away. That's not a bug. That's the finding: the lunar atmosphere is untested." | **Extrapolation: no evidence**; nearest `PSI-69:FLEX:45`, O₂ 0.30 at 1.01 atm, distance **2.14** (gate = 2) | `artifacts/bounds/lunar_base_M2.json` |
| 1:32–1:43 | Tab 5, Ledger. Point at GG-P0001. | "So we pre-registered our predictions. Each is hashed and committed to git today. When LUCI or FM2 flies, check us." | **GG-P0001** lunar base M1 0.201 [0.0125, 0.684], hash `def6ffb58fd2…` **✓ verified**; 5 predictions total | `ledger/predictions.jsonl` |
| 1:43–1:55 | Tab 6, Planner. | "And if NASA can run only ten tests, run this one first: extinction diameter at lunar gravity, 8.2 psia, 34% oxygen. Exactly the gap you just saw. Design takeaway: at lunar gravity, fans would need roughly 80 cm/s to make ISS data apply." | Rank 1: **M2** at 1.62 m/s², 8.2 psia, 34% O₂, vent 20 cm/s, score **1.0**, extends PSI-69, PSI-10, PSI-159; design implication **~80 cm/s** (139 cm/s for 95% of samples) | `artifacts/planner.json` |
| 1:55–2:00 | Stay on Planner. | "Gravity Gap: real NASA data, honest uncertainty, and the next test to run." | — | — |

M4 and M5 at the lunar base are also "no evidence" (SAFFIRE-II and SPICE were run near 21–22% O₂ at ~1 atm;
`artifacts/bounds/lunar_base_M4.json`, `lunar_base_M5.json`). Mention only if asked; it costs time in the main script.

### Rules for the presenter
- Say "estimate" and "band", never "the Moon value is". Never say "safe".
- If a number on screen differs from this table, read the screen, not this table, and tell the team afterwards.
- Do not open `/data` or `/explore` in the timed run: `/data` needs the live API and `/explore` ranking needs `POST /rank`.

## 1b. Round 3 additions (compare, briefing, trust, air map)

Extra tabs to open during setup:

| Tab | URL (localhost:3000) |
|---|---|
| 7 | `/compare?a=iss&b=lunar_base` |
| 8 | `/briefing?habitat=lunar_base` |
| 9 | `/trust` |
| 10 | `/atmospheres` |

**Opening contrast (replaces 0:12–0:22 if time allows, +10 s):** Tab 7. "Same tool, ISS on the left, lunar base on
the right. The flame regime changes from forced flow to mixed, three of five metrics lose their evidence, and the
droplet self-extinction chance drops from 94% to 20% with a wider band." Source: `engine/compare.py` summary
(POST `/compare`).

**New ending (replaces 1:43–2:00):** Tab 8. "Everything Gravity Gap can tell a lunar base designer, on one printable
page: prevention partial, flame behaviour partial, detection partial, suppression no evidence. Each chip follows a
written rule, each number is cited, and the gaps say which NASA test is nearest and how far away. The next test to run
is on the page too." Point at the four chips and "Print / save as PDF". Source: `artifacts/briefing/lunar_base.json`.

**Judge Q&A material**

| Question | Show | Point at |
|---|---|---|
| "How do you know it works?" | Tab 9, `/trust` | Lenient: band held for 208 of 222 hidden test atmospheres; strict: 7 of 74 (M1) and 4 of 83 (M3); weak-test badges; worst misses with PSI rows; SAFFIRE 7 of 9 with its caveat (`artifacts/holdout.json`) |
| "What should NASA test next?" | Tab 4, Bounds M1, "What makes this band wide" | About 65% of the band is model uncertainty (few tests near 34% O₂), lever links to Planner #6 (`artifacts/uncertainty/lunar_base.json`) |
| "Which cabin air does the evidence support?" | Tab 10, Air map | Evidence covers 71% (M1), 55% (M2) and 94% (M3) of the map; crew limits drawn from NASA-STD-3001 with sources; the map never ranks atmospheres (`artifacts/atmosphere_map/`) |
| "Could lunar dust set off the smoke alarm?" | `/detection` | The lunar dust gap: no lunar dust data in PSI; only Arizona Road Dust vs smoke on one size measure |

Offline: tabs 7–10 work for presets from the bundled artifacts; a custom habitat shows "needs the live API".

---

## 2. Offline-mode fallback (API down, no network)

Decide at setup: if `curl http://localhost:8000/health` fails or venue Wi-Fi is bad, run offline. The web app falls
back to static artifacts copied into `web/public/artifacts/` at build time and shows an **offline data** chip.

| Step | Offline behaviour | What to change in the script |
|---|---|---|
| Landing, Regime, Pressure × Gravity | Fully client-side (`web/lib/physics.ts`) | None |
| Bounds M1 / M2 | Served from `artifacts/bounds/lunar_base_M1.json` / `_M2.json` (the six presets work; custom habitats say "live API needed") | Keep the habitat on a preset. The rover contrast (vent 5) is also a preset, so it still works |
| Explain | Answers only the pre-generated questions in `artifacts/ai_cache.json` (6 entries, all validated) | Use the exact cached question: "Why is the M1 band wide for the lunar base?" |
| Ledger | Read from `ledger/predictions.jsonl`; hashes re-verified in the browser | None |
| Planner | Read from `artifacts/planner.json` | None |

Say once, at 0:12: "We're running fully offline right now; everything you see is precomputed from the same engine."
That turns the outage into a reliability point.

**Last resort:** play the recorded video from `docs/media/` (FE is producing it from the E2E run) and narrate over it.

## 3. 30-second version (elevator, or the first 30 s of the video)

> "NASA has fire tests from the ISS and from Earth, but none at Moon gravity, and lunar habitats are planned at 34% oxygen and 8.2 psia.
> Gravity Gap bridges that with transparent physics and 1,710 real PSI tests. At a lunar base a cabin flame sits in the **mixed** regime (Richardson number 6.5), where neither ISS nor Earth data apply.
> So we give an estimate with an honest band, for example a 20% chance a droplet flame self-extinguishes, with a 90% band from 1% to 68%, and where there is no evidence, we refuse to guess.
> We've hash-committed five predictions for LUCI to check, and our planner says the first test to run is extinction diameter at exactly that lunar atmosphere."

Screens if shown: Regime (MIXED, Ri 6.48) → Bounds M1 → Bounds M2 "no evidence" → Planner rank 1.

## 4. Rehearsal log (H3: three timed runs required)

| Run | Date / time | Mode (live / offline) | Duration | Issues |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

Exit criterion: three consecutive runs under 2:00, at least one offline.
