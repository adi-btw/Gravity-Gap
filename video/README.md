# Gravity Gap: 30-second demo video

The project video for **Gravity Gap** (team **BTRMLK**, Adityan Kesavan; NASA Space Apps Challenge 2026, challenge
**Flame in Freefall**), built in code with [Remotion](https://www.remotion.dev). 1920×1080, 30 fps, 885 frames =
**29.5 s** (the Space Apps limit is 30 s). No audio.

## Beats

| Time | Beat | On screen |
|---|---|---|
| 0:00 | Team | BTRMLK, Adityan Kesavan, NASA Space Apps Challenge 2026 |
| 0:02 | Challenge | Flame in Freefall, over NASA's 1 g and 0 g candle photos drifting at two speeds |
| 0:05 | Project | Gravity Gap + tagline, inside the Apollo 11 Earthrise cut into two parallax planes |
| 0:10 | The gap | To-scale gravity axis: orbit and Earth investigations at the ends, Moon 1.62 and Mars 3.71 in the hatched gap; habitat air 8.2 psia, 34% O₂ |
| 0:14 | Data | 1,710 real NASA PSI combustion tests |
| 0:15.6 | Band | M1 at the lunar base: the 0 g band 3.9%–48.2% widens to 1.2%–68.4%, estimate 20% |
| 0:18 | No evidence | M1–M5 at the lunar base; NO EVIDENCE stamps land on M2, M4, M5; M2 nearest test at distance 2.14 past the 2.0 gate |
| 0:20.6 | Sections | Simulated page scroll through Bounds, Compare, Air map, Briefing, Trust, Planner (screens on a slow plane, type on a fast one) |
| 0:26 | Impact | "Test the gap before crews live in it.", planner rank 1, live site URL, team line, credits |

Every number comes from the committed artifacts: `npm run facts` (`scripts/build-facts.mjs`) reads `../artifacts/`
and writes `src/facts.json`, which the scenes import. Rebuild it whenever the artifacts change.

## Preview, render

```bash
npm i
npm run facts                     # refresh src/facts.json from ../artifacts
npx remotion studio               # preview and edit in the browser
npm run render                    # out/gravity-gap-demo.mp4 (H.264, yuv420p, CRF 16; see remotion.config.ts)
npm run stills                    # 12 PNG stills + out/stills/sheet.png contact sheet (needs Python + Pillow)
npx remotion ffprobe -show_entries format=duration -of csv=p=0 out/gravity-gap-demo.mp4   # must be <= 30
```

Site screenshots in `public/screens/` were captured from the live site (https://nasa-hackathon-2026-two.vercel.app/,
lunar base habitat) with Playwright at 2× and cropped below the site header; `story-full.jpg` is the full story page
at 1×.

## Design

- Type: IBM Plex Sans (display and text) and IBM Plex Mono (figures, meta), the site's own bundled files, loaded with
  `@remotion/fonts` from `public/fonts/`. Licence: SIL Open Font License 1.1 (`public/fonts/OFL-*.txt`).
- Colour: the site's night palette from `web/app/globals.css` (regolith greys, the single flame accent `#f0743e`,
  blueprint blue for 0 g evidence and ochre for 1 g evidence).
- Motion: one easing curve throughout (the site's `cubic-bezier(0.22, 1, 0.36, 1)`), linear drift for parallax, no
  springs, no flashing transitions; scenes dip through the dark ground.

## Credits

- Photos: NASA Image and Video Library, public domain, credited on screen.
  - `as11-44-6549`, View of Earth rising over Moon's horizon, Apollo 11, 1969 (`public/photos/cover-earth.webp`,
    `cover-moon.webp`: two planes cut from one photo).
  - `GRC-1998-C-00486`, candle flame in normal gravity and microgravity, NASA Glenn (`candle-1g.webp`, `candle-0g.webp`;
    logo and caption text cropped off).
  - Full credits: `../scrollcraft/builds/gravity-gap/CREDITS.md`.
- Data: NASA Physical Sciences Informatics (psi.nasa.gov), CC0-1.0.
- No NASA logos, insignia, flags or mission patches are used. Gravity Gap is not a NASA product.

## AI disclosure

Every frame carries a visible "Made with AI assistance" mark (bottom right), as the Space Apps rules ask. The video
and the app were built with AI-written code (Anthropic's Claude via Claude Code) under the team's direction. No
imagery in the video is AI-generated: the photographs are NASA's and the screens are captures of the real site.

## Remotion licence

Remotion is source-available, not open source. Its licence lets **individuals and companies of up to 3 people** use it
for free (https://www.remotion.dev/docs/license/pricing); a team of one for a hackathon qualifies. Larger companies
need a Company License. See https://www.remotion.dev/docs/license.
