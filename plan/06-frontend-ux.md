# 06 · Frontend and UX

Back to [overview](00-overview.md). Implements the features in [04-features.md](04-features.md).

## 1. Information architecture
```
/                       Landing: problem in one sentence + habitat picker (F0) + "the gap" hero chart
/explore                F1 Gravity Spectrum Map (default after picking a habitat)
/regime                 F2 Regime Calculator + F3 Pressure × Gravity Explorer (tabs)
/bounds                 F4 Bounds Panel (metric selector)
/ledger                 F5 Prediction Ledger
/planner                F6 Test Planner
/investigations/[id]    F7 Investigation Card
/data                   F8 Data Explorer and Export
/about                  Method, limitations, data sources, citations, team
```
A persistent **habitat bar** at the top shows g · P · O₂ · vent and can be edited from any page. A persistent **"Ask"** drawer holds the F7 assistant.

## 2. Core user flows
1. **Engineer flow:** pick "Lunar rover" → see the regime badge "MIXED" → open Bounds M3 → read the band and the evidence → "Explain" → Planner → export evidence CSV.
2. **Researcher flow:** /data → filter FLEX at O₂ ≥ 0.3 → download with DOIs → open the FLEX card → follow lineage to PSI-117 and PSI-142.
3. **Judge demo flow:** the scripted 2-minute path in [11-demo-pitch.md](11-demo-pitch.md).

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
- Performance: first load under 2.5 s on hackathon Wi-Fi; artifacts are gzipped; Plotly is lazy-loaded.

## 5. Frontend architecture
- Next.js App Router; state in the URL query (`?g=0.165&p=8.2&o2=0.34&u=5&L=10`) and Zustand for UI-only state.
- `web/lib/physics.ts` mirrors `engine/physics.py` (parity tests T3).
- Data loading: static artifacts from `/public/artifacts` (build-time copy) with `fetch` to the API only for live bounds and Ask.
- Error boundaries per panel; a failed panel never blanks the page.
