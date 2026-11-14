# 11 · Demo and Pitch

Back to [overview](00-overview.md). Flows come from [06-frontend-ux.md](06-frontend-ux.md); features from [04-features.md](04-features.md).
The full, second-by-second presenter script (setup, offline fallback, rehearsal log) is **[docs/DEMO_SCRIPT.md](../docs/DEMO_SCRIPT.md)**.
Submission text is **[docs/SUBMISSION.md](../docs/SUBMISSION.md)**.

**Number rule:** every figure in the pitch comes from a committed artifact and is quoted with its source. No rounding beyond what is shown on screen, no figures from memory.

## 1. One-line pitch
**"NASA has fire data from space and from Earth, but none from the Moon. Gravity Gap uses physics and 1,710 real PSI tests to predict fire behavior where no one has tested, shows how sure it is (and when it can't say), and tells NASA what to test next."**

(Earlier drafts said "1,700 real ISS tests". The clean dataset is 1,710 tests from 10 PSI investigations, and SAFFIRE flew on Cygnus, not ISS: `data/clean/CLEANING_REPORT.md`.)

## 2. Demo habitat and the numbers on screen
The demo uses **Lunar base** (1.62 m/s², 8.2 psia, 34% O₂, vent 10 cm/s assumed, L = 10 mm), not the rover: it is the **mixed** regime, the least-tested condition. The rover (vent 5 cm/s) is buoyancy-dominated and is only a contrast.

| Quantity | Value | Source |
|---|---|---|
| Buoyant velocity u_b | 25.5 cm/s | `engine.physics.evaluate` (lunar_base preset) |
| Richardson number Ri | 6.48 → **MIXED** | same |
| Monte Carlo regime split | 0% forced / 71.7% mixed / 28.3% buoyant | `artifacts/bounds/lunar_base_M1.json` `regime_fractions` |
| G*(Moon, 8.2 psia) | 0.0514 (UI shows 0.051) | `engine.physics.g_star` |
| Lunar rover (vent 5) contrast | Ri 25.9 → BUOYANT; 11.9% mixed / 88.1% buoyant | `engine.physics`, `engine.montecarlo` |
| M1 P(droplet self-extinguishes before burnout) | 0.20, 90% band [0.012, 0.684]; microgravity-only band [0.039, 0.482]; widened ×1.64; transfer confidence **low**; n_train 206 | `artifacts/bounds/lunar_base_M1.json` |
| M2 extinction diameter | **Extrapolation: no evidence** (nearest PSI-69:FLEX:45, 30% O₂ at 1.01 atm, distance 2.14 > 2) | `artifacts/bounds/lunar_base_M2.json` |
| M3 P(gas flame self-extinguishes) | 0.872, band [0.560, 0.985], low confidence | `artifacts/bounds/lunar_base_M3.json` |
| M4 / M5 | **No evidence** (SAFFIRE-II and SPICE atmospheres ~21–22% O₂, ~1 atm) | `artifacts/bounds/lunar_base_M4.json`, `_M5.json` |
| Ledger | 5 predictions GG-P0001..0005; GG-P0001 = lunar base M1, sha256 `def6ffb58fd2…` | `ledger/predictions.jsonl` |
| Planner rank 1 | M2 at 1.62 m/s², 8.2 psia, 34% O₂, vent 20 cm/s, score 1.0, extends PSI-69, PSI-10, PSI-159 | `artifacts/planner.json` |
| Design implication | Lunar 10 mm flame is forced-regime only above ~80 cm/s vent (139 cm/s for 95% of samples); buoyancy-dominated below ~8 cm/s | `artifacts/planner.json` `design_implications` |

## 3. Two-minute demo (summary; full script in docs/DEMO_SCRIPT.md)
| Time | Screen | Say | Proof shown |
|---|---|---|---|
| 0:00 | Landing, "the gap" graphic | "No fire tests exist at Moon or Mars gravity. Habitats are planned at 8.2 psia and 34% oxygen." | F1 no-data zone |
| 0:12 | Pick **Lunar base** | "One click; every panel and the URL switch to Moon conditions." | F0 habitat bar |
| 0:22 | Regime Calculator | "Buoyancy 25 cm/s vs fan 10 cm/s: Ri 6.5, the **mixed** regime. 72% mixed, 28% buoyant, zero forced." | F2 badge MIXED |
| 0:40 | Pressure × Gravity tab | "Low g and low P stack: the buoyancy term is about 5% of Earth's." | F3 G* = 0.051 |
| 0:50 | Bounds M1 | "20%, band 1% to 68%, widened from the ISS-only 4–48% because these flames feel buoyancy. Confidence: low. Every point traces to a test." | F4 band + evidence chips |
| 1:10 | Explain | Validated AI answer with citations | F7 citations |
| 1:20 | Bounds M2 | "Here the tool refuses to answer: no test is close to this atmosphere. That's the finding." | F4 extrapolation state |
| 1:32 | Ledger | "Five predictions, hashed and committed today. When LUCI flies, check us." | F5 verified hashes |
| 1:43 | Planner | "If NASA can run one test, run extinction diameter at exactly this lunar atmosphere." | F6 rank 1 |
| 1:55 | Close | "Real NASA data, honest uncertainty, the next test to run." | — |

**Offline fallback:** every screen in this path works with the API stopped (presets are precomputed; Explain uses the cached question; ledger and planner are static). See docs/DEMO_SCRIPT.md §2. Last resort: the recorded video in `docs/media/`.

## 4. 30-second version
> "NASA has fire tests from the ISS and from Earth, but none at Moon gravity, and lunar habitats are planned at 34% oxygen and 8.2 psia. Gravity Gap bridges that with transparent physics and 1,710 real PSI tests. At a lunar base a cabin flame sits in the mixed regime (Richardson number 6.5), where neither ISS nor Earth data apply. So we give an estimate with an honest band, for example a 20% chance a droplet flame self-extinguishes, with a 90% band from 1% to 68%, and where there is no evidence, we refuse to guess. We've hash-committed five predictions for LUCI to check, and our planner says the first test to run is extinction diameter at exactly that lunar atmosphere."

## 5. Submission package (verify the current Space Apps rules on the event site)
Drafted in [docs/SUBMISSION.md](../docs/SUBMISSION.md), with the human checklist at the end.
- Project page text: problem, solution, how it uses NASA data (every PSI DOI), the AI's role, limitations.
- Demo video (≤ the length allowed; verify) recorded from the scripted path (FE, `docs/media/`).
- Repo link (private repo made public or shared with judges, as the team decides).
- Live link plus local-run fallback ([README.md](../README.md), [docs/DEPLOY.md](../docs/DEPLOY.md)).
- No NASA logo or insignia misuse; cite the data (PSI, CC0-1.0).

## 6. Judge Q&A prep (real numbers only)
| Likely question | Answer anchor | Source |
|---|---|---|
| "How do you know the Moon estimate is right?" | We don't claim it is. We bound it, show the band, lower the stated confidence (low at the lunar base), refuse when there's no evidence (M2, M4, M5 at the lunar base), and pre-register 5 predictions for LUCI/FM2 to falsify. | `artifacts/bounds/`, `ledger/predictions.jsonl` |
| "How good are the models on data you do have?" | 5-fold out-of-fold on microgravity PSI data: **M1 AUC 0.824**, Brier 0.081 vs 0.114 base rate (n = 206 FLEX tests). **M2** median error 0.325 mm vs 0.803 mm baseline; 5–95% interval coverage **0.848** vs 0.90 nominal, so we call the band optimistic. **M3 AUC 0.622**, Brier 0.177 vs 0.179: weak, and the report says so. | `artifacts/validation_report.md` |
| "Can you hindcast anything real?" | SAFFIRE-II flew samples in microgravity with matching normal-gravity ground tests (9 samples). Hindcast from microgravity data + the bridge: bridge 7/9 vs 3/9 for the naive "1 g = 0 g" baseline, but a constant "1 g burns more" guess also scores 7/9, so with n = 9 it does not yet show the bridge discriminates between materials. We say exactly that. | `artifacts/validation_saffire.md` |
| "Why not just interpolate between 0 g and 1 g?" | Flammability is non-monotonic in flow: a low-flow "Goldilocks" regime can be more flammable than both references. The effective-flow bridge u_eff = √(u_f² + (k·u_b)²) maps partial g onto an equivalent forced flow, and the engine raises a non-monotonic warning (flow-dependent rule models M4/M5) when u_eff falls there. At the lunar base u_eff p50 is 18.8 cm/s (p05 11.8, p95 34.5). | `plan/03-physics-engine.md`, `engine/rules.py`, `lunar_base_M1.json` |
| "Why does gravity not change your M1 number?" | FLEX droplets and CFI-G burners had no imposed flow, so there's no variable through which gravity could act. We keep the microgravity estimate and widen the band (×1.64 at the lunar base) instead of inventing a gravity dependence (ADR-0005). | `plan/decisions.md` ADR-0005 |
| "Where does the AI come in?" | Summaries, explanations and Q&A, all grounded: every number must appear in the engine's context pack (±0.5%) and every citation must resolve, or the answer is rejected. It runs with Claude when a key is set, otherwise from a validated cache (6 demo answers) or deterministic templates. Numbers always come from the engine, never the model. | `engine/ai/validator.py`, `artifacts/ai_cache.json` |
| "What's the use for NASA?" | Test prioritization for LUCI/FM2 (planner rank 1 = extinction diameter at lunar g, 8.2 psia, 34% O₂) and ventilation guidance: at lunar g a 10 mm flame is forced-regime only above ~80 cm/s, so typical 5–20 cm/s cabin vents leave fires mixed or buoyant. | `artifacts/planner.json` |
| "Earth benefit?" | The same pressure-scaling and ventilation reasoning applies to aircraft cabins, submarines and high-altitude buildings (discussion, not a claim). | — |
| "Is the lunar rover safer with the fans off?" | No claim of "safer". Fans off makes it buoyancy-dominated (rover at 5 cm/s: Ri 25.9, 88% buoyant), not ISS-like quiescent. | `ai_cache.json`, `engine.montecarlo` |
