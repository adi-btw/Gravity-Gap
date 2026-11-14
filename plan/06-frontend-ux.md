# 06 · Frontend and UX

Back to [overview](00-overview.md). Implements the features in [04-features.md](04-features.md).

## 1. Information architecture
```
/                       Landing: problem in one sentence + habitat picker (F0) + "the gap" hero chart
/explore                F1 Gravity Spectrum Map (default after picking a habitat)
/regime                 F2 Regime Calculator + F3 Pressure × Gravity Explorer (tabs: ?tab=pressure selects F3)
/bounds                 F4 Bounds Panel (metric selector, ?metric=M1..M5)
/ledger                 F5 Prediction Ledger
/planner                F6 Test Planner
/investigations/[id]    F7 Investigation Card
/data                   F8 Data Explorer and Export
/about                  Method, limitations, data sources, citations, team
```
A persistent **habitat bar** at the top shows g · P · O₂ · vent and can be edited from any page. A persistent **"Ask"** drawer holds the F7 assistant.

## 2. Core user flows
1. **Engineer flow:** pick **"Lunar base"** (1.62 m/s², 8.2 psia, 34% O₂, vent 10 cm/s) → see the regime badge **"MIXED"** (Ri ≈ 6.48) → open Bounds M1 → read the band and the evidence → "Explain" → switch to M2 and see "Extrapolation: no evidence" → Planner → export evidence CSV.
   Use the lunar base, not the lunar rover, as the MIXED example: with its assumed 5 cm/s vent the rover is **buoyant** (Ri ≈ 25.9). The rover is the contrast case ("fans down does not make it ISS-like").
2. **Researcher flow:** /data → filter FLEX at O₂ ≥ 0.3 → download with DOIs → open the FLEX card → follow lineage to PSI-117 and PSI-142.
3. **Judge demo flow:** the scripted 2-minute path in [11-demo-pitch.md](11-demo-pitch.md) and [docs/DEMO_SCRIPT.md](../docs/DEMO_SCRIPT.md).

## 3. Design system
- Tokens: a dark "mission control" theme as the default plus a light theme. Colors:
  - microgravity: cyan
  - normal gravity: amber
  - partial gravity estimate: violet
  - "no data" zone: hatched grey
  - warnings: red
- Typography: Inter for UI; JetBrains Mono for numbers and IDs.
- Components: HabitatBar, RegimeBadge, EvidenceChip (record_id hover), BandChart, TornadoChart, CitationList, CaveatBanner, ExtrapolationState, LedgerRow, PlannerItem.
- Uncertainty is always drawn as a band, never as a lone point.

## 4. Accessibility and quality bar
- WCAG 2.2 AA contrast; color is never the only signal (regime badges carry text + icon).
- All charts have a data-table alternative and descriptive aria labels.
- Keyboard navigable; the habitat sliders have numeric inputs.
- Mobile: read-only layout works at 375 px; the full interaction targets desktop (judging setting).
- Performance: first load under 2.5 s on hackathon Wi-Fi; artifacts are gzipped. Charts are hand-built SVG (no Plotly).

## 5. Frontend architecture
- Next.js App Router; state in the URL query; plain React state for UI-only state (no Zustand).
- **URL query parameters** (every link is shareable):
  | Param | Meaning | Unit | Example (lunar base) |
  |---|---|---|---|
  | `g` | gravity | **m/s²** (not a fraction of g: Moon = 1.62, Mars = 3.71, Earth = 9.81) | `g=1.62` |
  | `p` | cabin pressure | psia | `p=8.2` |
  | `o2` | O₂ mole fraction | fraction (0.34 = 34%) | `o2=0.34` |
  | `u` | vent (forced) flow speed | cm/s | `u=10` |
  | `L` | flame / fuel size | mm | `L=10` |
  | `tab` | `/regime` tab; `pressure` selects F3, anything else F2 | — | `tab=pressure` |
  | `metric` | `/bounds` metric, `M1`..`M5` (default `M1`) | — | `metric=M2` |

  Example: `/bounds?g=1.62&p=8.2&o2=0.34&u=10&L=10&metric=M1`. Implemented in `web/lib/habitat.ts` (`QUERY_KEYS`), `web/components/RegimeTabs.tsx` and `web/components/BoundsPanel.tsx`.
- `web/lib/physics.ts` mirrors `engine/physics.py` (parity tests T3).
- Data loading: static artifacts from `/public/artifacts` (build-time copy) with `fetch` to the API for live bounds, ranking, data and Ask; pages fall back to the static artifacts when the API is down and show an "offline data" chip.
- Error boundaries per panel; a failed panel never blanks the page.
