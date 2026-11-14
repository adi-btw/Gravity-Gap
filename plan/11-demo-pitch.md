# 11 · Demo and Pitch

Back to [overview](00-overview.md). Flows come from [06-frontend-ux.md](06-frontend-ux.md); features from [04-features.md](04-features.md).

## 1. One-line pitch
**"NASA has fire data from space and from Earth, but none from the Moon. Gravity Gap uses physics and 1,700 real ISS tests to predict fire behavior where no one has tested, shows how sure it is, and tells NASA what to test next."**

## 2. Two-minute demo script
| Time | Screen | Say | Proof shown |
|---|---|---|---|
| 0:00 | Landing, "the gap" chart | "Zero fire tests exist at lunar gravity. Habitats are being designed now at 34% oxygen." | F1 empty zone |
| 0:15 | Pick "Lunar rover" | "Watch every panel switch to Moon conditions." | F0 habitat bar |
| 0:25 | Regime Calculator | "At lunar gravity, buoyancy and the cabin fans are about equally strong: the mixed regime, the least-tested one." | F2 badge MIXED |
| 0:45 | Pressure × Gravity | "Low gravity and low pressure stack: buoyancy is about 5% of Earth's, so ISS data matters more than people assume." | F3 G* = 0.051 |
| 1:00 | Bounds Panel | "Here's our estimate with its uncertainty, and every point traces to real tests." Hover → record IDs. | F4 band + evidence |
| 1:20 | Ask "why is this band wide?" | AI explains with citations. | F7 citations |
| 1:35 | Prediction Ledger | "We committed these predictions to git today. When LUCI flies, check us." | F5 hashes |
| 1:50 | Test Planner | "And if NASA can only run 10 tests, here they are." | F6 list |

## 3. Submission package (verify the current Space Apps rules on the event site)
- Project page text: problem, solution, how it uses NASA data (list all PSI DOIs), the AI's role, limitations.
- Demo video (≤ the length allowed) or slides; recorded at M6.
- Repo link (the private repo is made public or shared with judges at submission, as the team decides).
- Live link plus a local-run instructions fallback.
- Space Apps rules on NASA data use and branding: no NASA logo misuse; cite data.

## 4. Judge Q&A prep
| Likely question | Answer anchor |
|---|---|
| "How do you know the Moon estimate is right?" | We don't claim to; we bound it, show uncertainty, hindcast SAFFIRE, and pre-register predictions (F5) |
| "Why not just interpolate between 0 g and 1 g?" | Flammability is non-monotonic in flow; the effective-flow bridge catches cases where partial g is worse than both |
| "Where does the AI come in?" | Summaries, relevance, explanations, paper extraction, all grounded and validated; numbers come from the engine |
| "What's the use for NASA?" | Test prioritization for LUCI/FM2 and ventilation design guidance for habitats |
| "Earth benefit?" | The same pressure-scaling and ventilation insights apply to aircraft cabins, submarines and high-altitude buildings (framed as discussion, not a claim) |
