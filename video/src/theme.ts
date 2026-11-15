import { loadFont } from "@remotion/fonts";
import { Easing, interpolate, staticFile } from "remotion";

// The site's own type: IBM Plex Sans for words, IBM Plex Mono for figures and meta (web/app/fonts, SIL OFL 1.1).
const faces: [string, string, string][] = [
  ["Plex Sans", "ibm-plex-sans-latin-400-normal.woff2", "400"],
  ["Plex Sans", "ibm-plex-sans-latin-500-normal.woff2", "500"],
  ["Plex Sans", "ibm-plex-sans-latin-600-normal.woff2", "600"],
  ["Plex Mono", "ibm-plex-mono-latin-400-normal.woff2", "400"],
  ["Plex Mono", "ibm-plex-mono-latin-500-normal.woff2", "500"],
];
for (const [family, file, weight] of faces) {
  loadFont({ family, url: staticFile(`fonts/${file}`), weight, display: "block" });
}

export const SANS = "'Plex Sans', system-ui, sans-serif";
export const MONO = "'Plex Mono', ui-monospace, monospace";

// Night palette from web/app/globals.css ([data-theme="dark"]): regolith neutrals, one flame accent.
export const C = {
  bg: "#0e0f10",
  surface: "#151618",
  surface2: "#1d1f22",
  line: "#2c2f33",
  lineStrong: "#5d6268",
  fg: "#eceeef",
  muted: "#9da3a8",
  accent: "#f0743e",
  micro: "#7fb0dd",
  normal: "#d9b45a",
  nodataFill: "rgba(128, 132, 136, 0.4)",
};

// One easing family for every move: the site's --ease, cubic-bezier(0.22, 1, 0.36, 1).
export const EASE = Easing.bezier(0.22, 1, 0.36, 1);

/** 0 to 1 over [start, start + dur], eased and clamped. */
export const prog = (frame: number, start: number, dur: number) =>
  interpolate(frame, [start, start + dur], [0, 1], {
    easing: EASE,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

/** Linear 0 to 1 over a range, for constant-speed parallax drift. */
export const lin = (frame: number, start: number, end: number) =>
  interpolate(frame, [start, end], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

export const SIDE = 140; // safe side margin at 1920 wide
export const hatch = (fill: string, w = 10) =>
  `repeating-linear-gradient(45deg, ${fill} 0 ${w}px, transparent ${w}px ${w * 2}px)`;
