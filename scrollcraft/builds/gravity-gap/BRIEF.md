# Gravity Gap · scroll-craft brief

**Interview status:** partly interviewed. The user answered four decisions directly (below, verbatim choice labels).
Everything marked *Authored* was written by the team lead from those answers and the project's own material
(plan/, docs/DEMO_SCRIPT.md, docs/SUBMISSION.md). Not invented user quotes.

## User's request (verbatim)
"I want you to use this skill and make it so that gravity gap doesn't look like ai, and that it looks a lot better."

## Answered by the user (2026-11-15)
| Decision | User's choice |
|---|---|
| Scope | **Landing + restyle**: a new scroll-driven story page at `/` that leads into the app, plus a new visual style applied to every app page so they match |
| Look | **Mission report**: editorial and technical, like a NASA flight-test report or an engineering drawing; serif headings, monospace data, ruled lines, sparse colour |
| Imagery | **Real NASA photos**: public-domain NASA images with credits; no generation, no API key |
| Structure | **Separate scenes**: distinct chapters, each with its own scroll behaviour (not one continuous flight) |

## The eight topics
1. **Vibe** (*Authored, from "Mission report"*): sober, exact, quietly alarming, handmade-technical.
   References from other media: an Apollo-era flight test report (typewritten tables, rubber-stamped classifications,
   hand-ruled margins); Edward Tufte's printed books (small multiples, data ink); the film *First Man* (restraint,
   real hardware, silence before the moment).
2. **Scroll journey** (*Authored*): the brief's own argument, in order. (1) Fire is the hazard every crew plans for;
   NASA has run hundreds of fire tests. (2) They are all at two gravities: orbit and Earth. (3) The Moon and Mars sit in
   the gap between them, at 8.2 psia and 34% oxygen. (4) Gravity Gap carries the evidence across that gap and says
   where it cannot. (5) What it finds at the lunar base, honestly, including "no evidence". (6) Open the tool.
3. **Energy curve** (*Authored*): calm and factual at the start; tightening through the gap; the loudest visual
   moment at the gap itself; then calm, precise, documentary through the evidence; a confident, still close.
4. **Feeling curve and peak** (*Authored*; spec in references/feel.md; final per-act curve is in SCORE.md):
   recognition → unease → vertigo at the gap → trust → resolve. **Peak:** the moment the visitor sees that the Moon
   and Mars fall exactly where NASA has no fire data.
5. **One thing no other site does** (*Authored*): the page refuses to give a number where the evidence is missing, in
   front of you. The signature move grows out of this (to be designed in SCORE.md).
6. **Range from premium-minimal**: editorial (user chose "Mission report").
7. **One world or scenes**: separate scenes (user's choice).
8. **Assets**: none supplied. Use public-domain NASA imagery (images.nasa.gov / NASA image API), each image recorded
   with its NASA id, title, centre and credit in `CREDITS.md` and shown on the page. No NASA insignia or logos, and a
   visible line that Gravity Gap is an independent hackathon project, not a NASA product. No AI-generated imagery.

## Tell-someone sentence (*Authored*)
"It's the site where the Moon lands right in the hole in NASA's fire data, and the tool shows you exactly what it
doesn't know."

## Shared design floor (both builders must use these; the app restyle and the story page must look like one product)
**Type** (Google Fonts via `next/font`; replaces Inter / JetBrains Mono, which read as template defaults):
- Display / headings: **Newsreader** (serif; optical sizes; use 500–600, not bold-black)
- Text / UI: **IBM Plex Sans** (400, 500, 600)
- Data / numbers / labels: **IBM Plex Mono** (400, 500), tabular figures

**Colour** (sparse; one accent; the existing semantic roles are kept but redrawn as ink colours):

| Token | Paper (light, default) | Night (dark) | Role |
|---|---|---|---|
| canvas `--bg` | `#F2EFE6` (report paper) | `#0F1011` | page |
| surface | `#FAF8F2` | `#17181A` | panels |
| surface-2 | `#E8E4D8` | `#202124` | insets, table stripes |
| line | `#C9C3B3` | `#34363A` | rules, borders (1px, ruled-paper feel) |
| fg ink | `#16181B` | `#ECE8DE` | text |
| muted | `#55595F` | `#A2A39F` | secondary text |
| accent / flame | `#C2410C` | `#F0743E` | the one accent: flame, CTAs, the gap |
| micro (orbit data) | `#1F4E79` (blueprint blue) | `#7FB0DD` | microgravity evidence |
| normal (Earth data) | `#7A5C12` (ochre ink) | `#D9B45A` | 1 g evidence |
| partial (estimate) | `#C2410C` (= flame) | `#F0743E` | partial-gravity estimate |
| nodata | `#8A8577` hatched | `#6E6C66` hatched | no evidence |
| warn | `#A61B1B` | `#F07A7A` | warnings |

All text pairs must pass WCAG AA (the repo runs axe in both themes); check and adjust shades, never drop the check.
**Default theme:** paper (light) for the report look; night stays available via the toggle.

**Form:** 1px ruled lines instead of shadows and rounded cards; corner radius 0–2px; section labels in small-caps mono;
numbers in mono with units; generous margins; a narrow measure for prose (~68ch); figure captions like a report
("Fig. 3 · ..."). No gradients, no glow, no glassmorphism, no emoji, no em dashes in visible copy (skill hard rule),
no "scroll" cue, no `01 / 06` counters, no eyebrow over every heading.
