# Gravity Gap · unslop audit and direction

Method: unslop by Damir Sokolovsky ([@heydamir](https://x.com/heydamir)), https://heydamir.design/unslop, licensed
CC BY 4.0. The audit, the five-line direction and the nine passes below follow that skill.

Screens looked at (before, 1440×900 and 390×844, paper and night): `/` at ten scroll stops, /bounds (lunar base, M1),
/compare?a=iss&b=lunar_base, /briefing?habitat=lunar_base, /trust, /atmospheres, /regime, /explore, /planner.
Shots: `unslop/shots/before/`.

## Audit (signs.md, one line each, with where it lives)

The "mission report" restyle already removed the loud slop (no purple, no glow, no emoji, no gradient text, no
pulsing). What is left is the newer, quieter template that AI tools now produce for "editorial" requests, and it is
the reason the site still reads as machine-made:

- Template look: cream paper `#f2efe6` + Newsreader serif + IBM Plex Mono uppercase eyebrows + "Fig. n" captions is
  the stock "editorial report" look (globals.css tokens, layout.tsx fonts, story.css)
- Three type families on every screen (Newsreader, Plex Sans, Plex Mono); the skill allows one family and one partner
- Uppercase, tracked mono labels everywhere: `F4 · BOUNDS PANEL` (.doc-label on every page title), `HABITAT`,
  `HISTORY` (HabitatBar), `ASSUMED, EDITABLE` (NumberField), `TRANSFER CONFIDENCE: LOW` (BoundsPanel),
  `MIXED` (RegimeBadge), `EVIDENCE REPORT · NASA SPACE APPS 2026`, `CONTENTS`, `FIG. 4 …` (story), chart table heads
- Card soup: 46 identical `rounded-lg border border-line bg-surface p-4` boxes; every section is a framed box, so
  nothing leads (BoundsPanel, CompareView, TrustView, PlannerView, ExploreView, RegimeCalculator, …)
- Trailing periods on headlines: all six story h1/h2 ("NASA's fire data stops at two gravities.")
- Link labels with ellipsis and arrows stacked in a row ("Compare with… →") (BoundsPanel header)
- Metric selector buttons of four different widths wrapping raggedly (BoundsPanel)
- Coverage chart scales with the panel width, so at 1440 its axis text is ~20px and the dots are huge, bigger than the
  page title (CoverageChart)
- Heavy chrome: habitat bar with two chip rows, five boxed fields and a source paragraph takes ~260px above every
  page title on desktop, more than the content's first block
- Weight 600 used for emphasis in many panel headings and badges (`font-semibold` 60+ times)
- `transition` without a named easing; two easing curves (story 0.23,1,0.32,1 vs none)
- Parallax on the story cover (kept on purpose, see exception)
- Not slop, kept: viridis on the atmosphere map (perceptually uniform and colour-blind safe, chosen and unit-tested),
  semantic inks (orbit blue, Earth ochre, flame for the estimate), hatch for "no data", the rubber "No evidence"
  stamp, the real NASA photographs

Verdict: light-to-medium slop. Colour, icons and copy are mostly fine; type, labels, framing and the cream template
are what read as AI. So: keep the product, palette roles, layout order and visuals; change the type system, the
neutral ramp, the labels and the framing (polish plus a firmer direction).

## Direction

- **Product.** Gravity Gap carries NASA's orbit and Earth fire-test data to Moon and Mars habitat air, for habitat and
  fire-safety engineers, and says where the evidence stops.
- **Character.** Exact, sober, quietly alarming.
- **World.** Apollo flight documents on the lunar surface: regolith grey, black sky, instrument hairlines, one flame.
- **Moments.** The Apollo 11 cover in layers and the gravity-gap figure on the story; on each app page its main chart
  (bounds band chart, compare rows, atmosphere map) drawn as the one rich thing.
- **Signature.** The rubber "No evidence" stamp with hatching wherever the engine refuses to print a number.

## Decisions per pass

1. Spacing: one 4px rhythm; panels become open sections with 24px inner and 40px between; habitat bar tightened.
2. Color: cream paper replaced by a cool regolith-grey neutral ramp (paper and night), three text roles, the flame
   stays the one accent; semantic inks unchanged.
3. Icons: the few line icons kept at one size and stroke; arrows removed from link labels.
4. Copy: no trailing periods on headlines and labels, no ellipsis in links, sentence case labels.
5. Type: Newsreader dropped. IBM Plex Sans for interface and headlines (400/500, tight tracking only on large
   display), IBM Plex Mono as the one partner for figures and meta. No uppercase tracked labels.
6. Layout: section order unchanged; app panels lose their boxes and become ruled sections; metric selector becomes a
   segmented list; coverage chart capped so it sits beside its caption instead of filling the screen.
7. Details: 6px controls, 2px tags, 1px hairlines; the stamp kept as the signature.
8. Visuals: no new decoration. The Apollo cover, the gap figure, the photos and the existing charts carry the colour.
9. Motion: one easing curve (`cubic-bezier(0.22, 1, 0.36, 1)`), named transitions, no loops except the live caret
   in the refusal field (it stands for a live input).

## Exception: parallax (the user asked for it)

The skill's motion pass removes parallax. The user explicitly asked for parallax scroll effects, so the user wins,
with limits: transform only, a few dozen pixels, driven by the existing scroll engine, off under
`prefers-reduced-motion`, and only where depth means something: the Apollo 11 cover (Earth behind the lunar
horizon, the title between them), the hazard photographs (the BASS-II flame inset floats above the ISS rack photo)
and the candle pair. No floating loops, nothing on app chrome.

## What changed (applied)

- Tokens (web/app/globals.css): cream ramp replaced by a cool regolith-grey ramp in both themes, every text role
  re-checked (muted 6.3:1 on paper, 7.5:1 on night); radius scale 2 / 6 / 8; one easing curve.
- Type (layout.tsx, globals.css, story.css): Newsreader removed; Plex Sans 400/500 for headlines with tight tracking
  only at display sizes; `font-semibold`/`font-bold` and SVG weights 600/700 capped at 500; `.doc-label`, `.label-mono`,
  `.fig-no`, story labels and table heads in sentence case; leftover `uppercase`/`tracking-*` utilities neutralised.
- Layout: 46 boxed `rounded-lg border bg-surface` cards became `.panel` / `.panel-tight` open sections under a
  hairline (briefing keeps its sheet frame for print); habitat bar fields lose their boxes; coverage chart capped at
  680px beside its caption.
- Copy: no trailing periods on the six story headings and the "between" line; "Compare with… →" became "Compare with
  another habitat →"; chart labels in sentence case (Moon, Mars, "No fire test at any gravity in this span",
  "No direct fire data", "Buoyant (Ri > 10)", "Forced (Ri < 0.1)"); "assumed, editable" as quiet text.
- Parallax: cover title layer added between the Earth and lunar-horizon planes; hazard photo (0.2) and BASS-II inset
  (-0.55) on separate depths; candle pair (-0.3). All via the engine (off under reduced motion).

---

Part of unslop by Damir Sokolovsky ([@heydamir](https://x.com/heydamir)), CC BY 4.0.
