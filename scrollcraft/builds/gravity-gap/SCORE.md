# Gravity Gap · score

Written before any markup. Inputs: BRIEF.md (user decisions: landing + restyle, mission-report look, real NASA
photos, separate scenes; authored topics 1 to 8). Every number planned below is read from a committed artifact at
build time (`artifacts/catalog.json`, `artifacts/bounds/lunar_base_M1..M5.json`, `artifacts/briefing/lunar_base.json`)
or computed by the app's own physics (`web/lib/physics.ts`). No number is typed into the page by hand.

## 1. Grammar: Flight-test report (a named new grammar, built from chaptered editorial)

**What it is.** The page is a printed evidence report. The unit is the numbered **figure**, not the act: each
chapter exists to show one figure (Fig. 1, Fig. 2, ...), and the prose beside it is commentary, set in a narrow
measure with a report caption under every figure. Chapters land on their own ground and cut hard; nothing
interpolates between grounds.

**How it differs from 2.2 chaptered editorial** (so it earns its own name, not a relabel):

| | Chaptered editorial | Flight-test report |
|---|---|---|
| Hero | Title page, no media above the fold | A **cover plate**: one real photograph cut into planes, the only place on the page where type sits on media |
| Unit | Chapter spread | The numbered figure; two figures are **fold-out plates** (pinned, the figure is an instrument driven by scroll) |
| Nav | Folio with chapter number | A **contents column** in the left margin: chapter titles only (no numbers), the current one ruled, every entry a link |
| Close | Colophon, CTA as running text | A **distribution sheet**: the reader fills in which habitat their copy is for (the app's real preset control), then one line of running text opens the tool, then credits and the independence line |

**Forbids:** `scrub` (no video at all; this build is stills only); `drift` (grounds are painted per section, hard
cuts); `spotlight`; `magnet`; `kinetic` splitting; pinned crossfade type acts (copy never swaps inside a pin); cards;
media under type anywhere except the cover; centred hero copy; section numbers or `01 / 06` counters (figures are
numbered because a report cites them, chapters are not).

**Leans on:** `flow` + `in` for prose, `reveal` for the one change-of-state photograph, `parallax` only on the
cover's photographic planes, `pin` only for fold-out figure plates, bespoke CSS driven from `--sc-p` inside them.

### Why the other seven lost

- **Filmic one-shot**: the user chose *separate scenes*; a continuous film with hidden seams is the opposite.
- **Chaptered editorial**: closest relative, but it bans media above the fold, and the brief needs a dimensional
  photographic cover (hero-depth baseline) plus two scroll-driven figure plates. Rather than break its rules, the
  differences are written down as a new grammar above.
- **Live surface**: the app itself is the live surface; the landing page's job is the argument *before* the tool.
  Painting the tool on the landing page would duplicate it, and the honesty rule forbids a fake one.
- **Continuous world**: needs one unbroken place and worldflight video; the user chose scenes, and there is no full
  ffmpeg and no clip generation in this environment.
- **Typographic poster**: the user asked for real NASA photographs; type-only would discard them.
- **Gallery / catalog**: the visitor's question is "should I believe this", not "what are the options"; the six
  habitats are a choice at the end, not the spine.
- **Split stage**: there are two sides (orbit and Earth) but the story is the empty third place between them, so a
  50/50 stage resolving to one winner says the wrong thing.
- **Rhythmic cutlist**: "sober, exact, quietly alarming" is the opposite of a cut every second.

## 2. Signature move: the refusal press

Fig. 6 is the lunar base, metric by metric, set as a report table. As the plate is scrolled, each value is printed
into its field (M1 20.1%, M3 87.2%, read from the bounds artifacts). The M2 row is the instrument: an empty numeric
field with a blinking caret, and under it a distance gauge from the lunar-base atmosphere to the nearest tested one.
The needle travels with the scroll toward 2.14 (`lunar_base_M2.json`, nearest test PSI-69 FLEX 45, 30% O2 at 1.01
atm). The moment it crosses the honesty gate at 2.00 the press stops: the caret dies, the field is struck through,
and a rubber stamp lands on it: **NO EVIDENCE**. M4 and M5 are stamped a beat later. One second-person line, the
only one on the page: "You scrolled for a number. There is no test close enough to print one." A plain button,
"Try to print M2 again", replays the attempt on demand (keyboard reachable; instant under reduced motion).

It is bespoke page code (CSS from `--sc-p` plus a 30-line replay), not a kit device, and it is the page's
tell-someone moment told from the visitor's side: the site refused, in front of them, and showed why.

## 3. Fingerprint gate

`scrollcraft/FINGERPRINTS.md` is empty (first build in this workspace). Nothing to clear; gate trivially passes. The
row is appended after shipping.

## 4. Journey (BRIEF topic 2)

```
1  Cover          the Moon's horizon with Earth sinking behind it: this is about leaving 1 g
2  Hazard         fire is the emergency every crew plans for; NASA has a real archive of tests
3  Two gravities  every one of those tests burned in orbit or on Earth (the candle wipe)
4  Silence        between them, the archive is empty
5  The gap        PEAK: the axis runs out through nothing, then the Moon and Mars drop into the hole
6  The bridge     Gravity Gap carries orbit evidence across and widens the band to pay for it
7  The refusal    and where the evidence does not reach, it refuses to print a number
8  Distribution   choose the habitat for your copy; open the tool
```

## 5. Feeling curve (one line per act: emotion, then the cause)

```
1  Calm        a real Apollo 11 photograph, held still; the horizon climbs over the headline as you scroll
2  Respect     a real astronaut at the real fire rack, and the real size of the archive
3  Unease      the tall yellow candle wiped into the dim blue dome: the same fire, two different physics
4  Hush        one line on a bare tinted sheet, nothing else on screen (authored silence)
5  Vertigo     PEAK: the axis keeps extending through hatched nothing for screen after screen, then the
               Moon and Mars fall into the empty span
6  Relief      there is an answer: one estimate, and you can see exactly how much wider its band got
7  Conviction  the press refuses in front of you; the stamp lands on the empty field
8  Resolve     a still, ruled form: pick your habitat, one line opens the tool
```

No two adjacent acts share a feeling. **Peak:** act 5, "the line kept going through nothing, and then the Moon and
Mars dropped right into the hole." It gets the largest span (3.6 viewport-heights, the next largest is 2.6), the
darkest ground on the page (a hard cut from the paper-tinted silence), the most choreography, and the act before it
is the quietest on the page.

**Authored silence:** act 4 (`#between`) is deliberately near-empty: one sentence on a tinted sheet. It is not dead
scroll.

## 6. Score table (device per beat)

| Beat | Act | Device | Span | Why this one |
|---|---|---|---|---|
| Cover | `#cover` | `parallax` (flow act, three photo planes) | natural, 100svh | Depth from the real photograph: Earth plane lags, the lunar surface plane climbs over the headline. The cover is a plate, not a film |
| Hazard | `#hazard` | `flow` + `in` | natural | Information beat, reads like a report page; no device should compete with the photograph of a person |
| Two gravities | `#two-gravities` | `reveal` (wipe on a figure) | natural | A wipe is a change of state, and this beat is literally one fire becoming another |
| Silence | `#between` | `flow` + `in` (one line) | ~0.9 screen | Quiet before the drop; nothing moves |
| The gap (peak) | `#gap` | `pin` + bespoke `--sc-p` figure | **3.6** | The axis is drawn by the reader's hand; holding the frame while it extends is what makes the emptiness last |
| The bridge | `#bridge` | `flow` + `in` (band widens on entry) | natural | Calm documentary pace after the peak; the one animated element is the band growing |
| The refusal | `#refusal` | `pin` + bespoke press (signature) | 2.6 | The press has to happen while the visitor watches; a pin holds the table still while the needle travels |
| Distribution | `#distribution` | `flow`, a real form | natural, holds | A report ends on a sheet you fill in; the page stops moving and starts responding |

Device families: parallax, flow/in, reveal, pin, bespoke figure. Five families. No family twice in a row (flow
acts 2 and 4 are separated by the reveal; pins 5 and 7 by flow). No scrub at all. Eight acts, roughly 12 to 13
viewport-heights at desktop, outside the 6-to-7-act band.

## 7. Layer contract for the cover (hero-depth.md)

| Plane | Asset | Movement | Occlusion rule |
|---|---|---|---|
| Far: space | CSS ground matched to the photo's black sky | none | none |
| Mid: Earth | `cover-earth.webp`, alpha cut from AS11-44-6549 (sky keyed out by brightness) | lags the page (`parallax` +0.9): Earth sets | sits behind the headline and behind the lunar surface |
| Type | real `<h1>`, sub, label | 1x (normal scroll) | between Earth and the surface |
| Near: lunar surface | `cover-moon.webp`, alpha cut along the measured horizon of the same photo | climbs faster than the page (`parallax` -1.6) | overtakes the bottom of the copy block as the cover leaves |

Mobile: the same planes, re-anchored (horizon at 70% of the cover, scene sized off the viewport height so Earth
stays in frame), headline stepped down one size and set above the Earth. Reduced motion: planes still, composition
intact, depth carried by occlusion alone.

## 8. Feel check (after build, from the contact sheets, written cold before re-reading section 5)

| Act | Felt | Intended | Change made |
|---|---|---|---|
| Cover | calm, then distance | Calm | none |
| Hazard | respect | Respect | none |
| Two gravities | first pass: nothing (the wipe never showed: the reveal wrapper had zero height) | Unease | wrappers made absolute; the wipe now runs, 1 g candle to 0 g dome |
| Silence | hush | Hush | none |
| The gap | first pass: waiting, then vertigo | Vertigo | axis travel shortened (p 0.04 to 0.46), "0 tests here" tip enlarged, hatch label held until the hatch reaches it, punchline caption now holds from p 0.79 to 1 |
| Bridge | study (reads as a document) | Relief | not changed; the widening band is the one moving element. Noted as the weakest act |
| Refusal | conviction | Conviction | first pass the margin contents overlapped the copy (press wrapper did not fill the stage); fixed |
| Distribution | resolve | Resolve | none |

Peak check: the gap plate is the largest visual change on the sheets (only dark full-frame figure, 3.6 vh), and the
act before it (one line on a tinted sheet) is the quietest. The close holds with content on the last screen.
