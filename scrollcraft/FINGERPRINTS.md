# Fingerprints

Every site you build with **scroll-craft** gets one row here, appended after it
ships. The registry exists so your next build can prove it is a different page
rather than a re-skin of one you already made.

This file is **yours**. It starts empty on purpose: the gate is about not
repeating *yourself*, so it has nothing to say until you have built something.

The rules and the gate live in the skill's
`references/uniqueness.md`. Short version:

**A new build must differ from EVERY row below on at least 4 of the 6
dimensions.** Four against each row individually, not four on average across the
table. If a planned build fails, change the plan. Never edit a row to make room
for it.

The six dimensions are: **grammar**, **nav treatment**, **hero device**,
**act-sequence shape**, **close pattern**, **signature move**.

Dimension 6 is free, because a signature move is unique by definition. So the
gate really asks for three more out of the remaining five, and a build that
changes only grammar and world will fail it.

---

## The registry

| Build | Grammar | Nav treatment | Hero device | Act-sequence shape | Close pattern | Signature move | World | Port |
|---|---|---|---|---|---|---|---|---|
| gravity-gap (2026-11-15) | Flight-test report (new; from chaptered editorial: photographic cover plate, numbered figures, fold-out pinned figure plates) | App SiteNav kept on top; own nav is a fixed left-margin contents column (chapter titles, no numbers, current one ruled), hidden over the dark plates and below 1400px | Cover plate: one Apollo 11 photo cut into Earth and lunar-surface alpha planes, headline set between them; parallax (Earth +0.9, surface -1.6), surface climbs over the copy | 8 acts: parallax cover, flow+in, reveal, authored silence, PIN peak 3.6 (data figure from --sc-p), flow+in, PIN 2.6 (signature), flow close; ~12.2 vh desktop, ~14.2 vh phone, 7.7 vh reduced | Distribution sheet: the app's habitat presets as a ruled form, one running-text link "Open the tool", credits colophon and independence line; no button island, no magnet, no spotlight | The refusal press: a gauge needle travels to the nearest tested atmosphere (2.14), crosses the honesty gate (2.00), and a NO EVIDENCE stamp lands on the empty M2 field; replayable | Real NASA photography + hand-drawn SVG data figures, paper report / night plates | Next.js route `/` on :3000 |


---

## What is taken

Add a bullet here whenever a build claims something a later build should avoid
reusing: a grammar, a nav treatment, a close pattern, a signature move, an
act-count-and-length band. The shared columns are what the next build inherits
as a constraint, so writing them down is the whole point.

- **Flight-test report grammar** (gravity-gap): cover plate + numbered figures + pinned fold-out figure plates + distribution-sheet close.
- **Margin contents column** as nav (gravity-gap).
- **Photo cut into two alpha planes with type between them** as the hero (gravity-gap).
- **Distribution-sheet close** (a real form whose choice the CTA carries) (gravity-gap).
- **Scroll-drawn data axis peak** (an axis that extends through empty data, then markers drop in) (gravity-gap).
- **Refusal stamp** signature (gravity-gap).
- Act band taken: 8 acts at ~12.2 vh.

---

## Appending a row

After shipping, add one line to the table and one bullet to **What is taken** if
the build claimed something new. Fill every column. Say what the build shares
with existing rows.

Rows are append-only. A build that has been superseded stays in the table,
because the space it occupies is still occupied.

---

## Worked example

The skill's author kept a registry of twelve builds across eight page grammars.
If you want to see what a filled-in table looks like, and which shapes tend to
collide, read `EXAMPLES.md` in the scroll-craft repository. Treat it as
illustration only: those rows are somebody else's builds and they do **not**
constrain yours.
