# 04 · Feature Specifications

Back to [overview](00-overview.md). Physics is in [03-physics-engine.md](03-physics-engine.md). UI is in [06-frontend-ux.md](06-frontend-ux.md). APIs are in [07-api-backend.md](07-api-backend.md).

Each feature lists: **purpose · user story · inputs · outputs · acceptance criteria · dependencies**. Backlog IDs are in [12-backlog.md](12-backlog.md).

---
## F0 Habitat Selector
- **Purpose:** one shared state that drives every view.
- **User story:** "As a habitat engineer I pick 'Lunar rover' and every panel updates to 0.165 g, 8.2 psia, 34% O₂."
- **Presets:**
  | Preset | g | P (psia) | O₂ | Default vent (cm/s) |
  |---|---|---|---|---|
  | ISS | 0 | 14.7 | 21% | 10 |
  | Exploration vehicle | 0 | 10.2 | 26.5% | 10 |
  | Lunar base | 0.165 g | 8.2 | 34% | 10 |
  | Lunar rover | 0.165 g | 8.2 | 34% | 5 |
  | Mars base | 0.38 g | 8.2 | 34% | 10 |
  | Earth reference | 1 g | 14.7 | 21% | 0 |
  | Custom | sliders | sliders | sliders | slider |
- **Acceptance:** state is in the URL (shareable link); preset values cite their source; vent defaults are marked "assumed, editable."
- **Depends on:** nothing.

## F1 Gravity Spectrum Map
- **Purpose:** summarize and rank the evidence along the gravity axis.
- **Visual:** a horizontal axis from 0 to 1 g. Investigations are dots at 0 g (ISS/Cygnus); 1 g references (SAFFIRE-II ground columns, literature) sit on the right; E-FIELD is a special "buoyancy analog" marker. The Moon and Mars are vertical lines inside a shaded **"no direct data"** zone.
- **Ranking:** relevance = w1·(1 − normalized atmosphere distance) + w2·(fire-safety pillar match) + w3·(fuel realism: solid > liquid > gas) + w4·(outcome data available) + w5·(n tests, log-scaled). Weights are shown and editable.
- **Outputs:** ranked list with score breakdown bars; each item opens F7.
- **Acceptance:** ranking changes when the habitat changes; PSI-181 (solder) and PSI-108 (fluids) are excluded with a visible "not combustion" note.
- **Depends on:** P3 catalog, F0.

## F2 Flame Regime Calculator
- **Purpose:** tell the user which data family applies.
- **Inputs:** g, u_f, L (from F0 plus local sliders).
- **Outputs:** u_b, Ri, a regime badge (forced / mixed / buoyant), and a 2D regime map (x = vent speed, y = flame size) with the current point; the regions are shaded per gravity.
- **Insight callout:** "At lunar gravity with 5–15 cm/s ventilation, typical cabin flames sit in the MIXED regime, the least-tested condition."
- **Acceptance:** matches reference cases V1; updates in under 50 ms per change (client-side).
- **Depends on:** E1 TS port.

## F3 Pressure × Gravity Explorer
- **Purpose:** show the combined effect of low g and low P.
- **Outputs:** a G* heat map over (g, P) with habitat markers; a side table of p_O₂ and the X_O₂ vs P "flammability concern" overlay; the caveat banner (laminar flow structure only).
- **Acceptance:** G*(Moon, 8.2 psia) displays 0.051 ± rounding; the caveat is always visible.
- **Depends on:** E1.

## F4 Bounds Panel
- **Purpose:** the prediction itself.
- **Inputs:** habitat + metric (M1–M5).
- **Outputs:** a chart with the 0 g reference, the 1 g reference, the partial-g estimate and its 90% band; an evidence list (record_ids grouped by investigation); the sensitivity tornado; an "extrapolation" state when the applicability gate fails; a **non-monotonic warning** when u_eff hits the flammability peak.
- **Acceptance:** at least 3 metrics working; every point is hover-traceable to evidence; the gate triggers correctly in tests.
- **Depends on:** E2 artifacts or `POST /bounds`.

## F5 Prediction Ledger
- **Purpose:** turn the data gap into a falsifiable contribution.
- **Behavior:** a user, or the team before the demo, freezes a prediction. The ledger stores `{id, created_at, habitat, metric, estimate, band, model_version, artifact_hashes, rationale}` in `ledger/predictions.jsonl`. The SHA-256 of the record is committed to git, so the commit timestamp is the proof.
- **UI:** a table of predictions with a status of `open / confirmed / refuted / inconclusive`, plus a "how to check this when LUCI reports" note.
- **Acceptance:** at least 5 seeded predictions; records are append-only (CI rejects edits to existing lines); hashes are verifiable in-app.
- **Depends on:** F4, E5.

## F6 Test Planner
- **Purpose:** "If LUCI or FM2 can only run 10 tests, run these."
- **Outputs:** a ranked list of candidate tests (g, P, O₂, vent, metric) with the score breakdown, the expected band shrink, the rationale, and the investigations each test extends. It also gives **design implications**, e.g. "keeping ventilation above X cm/s keeps flames in the forced regime, where ISS data applies."
- **Acceptance:** list renders in under 1 s from precomputed artifacts; each item has a plain-language reason.
- **Depends on:** E3.

## F7 Investigation Cards + AI Assistant
- **Card:** a 3-sentence AI summary, objective, hypothesis, hardware, conditions covered (computed), outcome availability, hazard pillars, Earth applications, DOI and publications, data-quality flags, and a "lineage" link (flight → ground reanalysis studies, e.g. FLEX → PSI-117, PSI-142).
- **Assistant:** "Explain this prediction" and free questions. Answers are grounded in the engine output and catalog and carry citations ([05-ai-layer.md](05-ai-layer.md)).
- **Acceptance:** zero uncited numbers in the eval set; refuses out-of-scope topics (rockets) with a pointer.
- **Depends on:** P3, AI layer.

## F8 Data Explorer and Export
- **Purpose:** goal 2 (support predictive modeling).
- **Features:** a filterable table of `psi_tests.csv` (investigation, O₂, P, outcome, flags); a scatter builder; download of the filtered CSV/JSON with a citation block (DOIs) auto-included.
- **Acceptance:** export includes DOIs and the cleaning-report version.
- **Depends on:** P2 outputs.
