import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";
import facts from "../facts.json";
import { Fade, Kicker, Scene } from "../parts";
import { C, EASE, MONO, SANS, SIDE, prog } from "../theme";

type Section = { name: string; path: string; line: string; img: string };

const SECTIONS: Section[] = [
  { name: "Bounds", path: "/bounds", line: "An estimate and its 90% band, for each fire metric", img: "screens/bounds.jpg" },
  { name: "Compare", path: "/compare", line: "Two habitats side by side: ISS and lunar base", img: "screens/compare.jpg" },
  { name: "Air map", path: "/atmospheres", line: "Which cabin air NASA's evidence covers", img: "screens/atmospheres.jpg" },
  { name: "Briefing", path: "/briefing", line: "One printable fire-safety page per habitat", img: "screens/briefing.jpg" },
  {
    name: "Trust",
    path: "/trust",
    line: `The honesty test: bands held for ${facts.trust.held} of ${facts.trust.of} hidden test atmospheres`,
    img: "screens/trust.jpg",
  },
  { name: "Planner", path: "/planner", line: "The next tests NASA should run, ranked", img: "screens/planner.jpg" },
];

const SLOT = 27; // frames per section
const MOVE = 12; // frames of each scroll step
const STEP = 860; // px between cards

/** 0:20.6 The main sections, as a simulated page scroll: screens on one plane, big type on a faster one. */
export const SectionsScene: React.FC = () => {
  const frame = useCurrentFrame();
  // Scroll position in sections: settle on 0, then step one section per slot.
  let s = -0.8 + 0.8 * prog(frame, 0, MOVE + 4);
  for (let k = 1; k < SECTIONS.length; k++) s += prog(frame, k * SLOT - 4, MOVE);
  const CARD_W = 1060;
  const CARD_H = 640;
  const CARD_X = 1920 - SIDE - CARD_W;
  const imgH = (CARD_W * 1277) / 1600;
  return (
    <Scene>
      {/* back plane: hairlines at half speed */}
      {Array.from({ length: 12 }, (_, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: ((i * 380 - s * STEP * 0.5) % 4560 + 4560) % 4560 - 380,
            height: 1,
            backgroundColor: C.line,
            opacity: 0.6,
          }}
        />
      ))}
      {SECTIONS.map((sec, i) => {
        const d = i - s;
        const local = frame - i * SLOT;
        const pan = prog(local, 0, 46);
        return (
          <div
            key={sec.name}
            style={{
              position: "absolute",
              left: CARD_X,
              top: 540 - CARD_H / 2 + 30 + d * STEP,
              width: CARD_W,
              opacity: 1 - Math.min(1, Math.abs(d)) * 0.7,
            }}
          >
            <div style={{ fontFamily: MONO, fontSize: 24, color: C.muted, marginBottom: 12 }}>
              nasa-hackathon-2026-two.vercel.app<span style={{ color: C.fg }}>{sec.path}</span>
            </div>
            <div style={{ width: CARD_W, height: CARD_H, overflow: "hidden", border: `1px solid ${C.lineStrong}`, backgroundColor: "#f3f4f4" }}>
              <Img
                src={staticFile(sec.img)}
                style={{ width: CARD_W, height: imgH, translate: `0 ${-(imgH - CARD_H) * pan}px` }}
              />
            </div>
          </div>
        );
      })}
      {SECTIONS.map((sec, i) => {
        const d = i - s;
        const vis = Math.max(0, 1 - Math.abs(d) * 1.6);
        return (
          <div
            key={sec.name}
            style={{
              position: "absolute",
              left: SIDE,
              top: 540 + d * STEP * 1.45,
              translate: "0 -50%",
              width: CARD_X - SIDE - 60,
              opacity: EASE(vis),
            }}
          >
            <div style={{ fontFamily: MONO, fontSize: 30, color: C.accent }}>{String(i + 1).padStart(2, "0")}</div>
            <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 116, lineHeight: 1.02, letterSpacing: "-0.04em", color: C.fg, marginTop: 8 }}>
              {sec.name}
            </div>
            <div style={{ fontFamily: SANS, fontSize: 40, lineHeight: 1.25, color: C.muted, marginTop: 22 }}>{sec.line}</div>
          </div>
        );
      })}
      {/* header and footer bands the page scrolls under */}
      <AbsoluteFill
        style={{
          background: `linear-gradient(${C.bg} 0px, ${C.bg} 150px, rgba(14,15,16,0) 230px, rgba(14,15,16,0) 950px, ${C.bg} 1030px)`,
        }}
      />
      <AbsoluteFill style={{ padding: `112px ${SIDE}px 0`, pointerEvents: "none" }}>
        <Fade at={0} dur={10}>
          <Kicker>Inside Gravity Gap</Kicker>
        </Fade>
      </AbsoluteFill>
    </Scene>
  );
};

/** 0:26 Impact and the live site, with the story page scrolling past. */
export const CloseScene: React.FC = () => {
  const frame = useCurrentFrame();
  const W = 520;
  const H = 780;
  const pageH = (W * 6817) / 1440;
  const scroll = prog(frame, 0, 100);
  const p1 = facts.planner1;
  return (
    <Scene fadeOut={0}>
      <div
        style={{
          position: "absolute",
          right: SIDE,
          top: 150,
          width: W,
          opacity: prog(frame, 0, 16),
          translate: `0 ${(1 - prog(frame, 0, 24)) * 60}px`,
        }}
      >
        <div style={{ width: W, height: H, overflow: "hidden", border: `1px solid ${C.lineStrong}` }}>
          <Img src={staticFile("screens/story-full.jpg")} style={{ width: W, height: pageH, translate: `0 ${-(pageH - H) * scroll}px` }} />
        </div>
      </div>
      <AbsoluteFill style={{ padding: `150px ${SIDE}px 0` }}>
        <Fade at={0} dur={12}>
          <Kicker>Impact</Kicker>
        </Fade>
        <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 112, lineHeight: 1.0, letterSpacing: "-0.04em", color: C.fg, marginTop: 14 }}>
          <Fade at={2} lift={40}>Test the gap</Fade>
          <Fade at={6} lift={40}>before crews</Fade>
          <Fade at={10} lift={40}>
            <span style={{ color: C.accent }}>live in it.</span>
          </Fade>
        </div>
        <Fade at={22} style={{ marginTop: 34, width: 1060 }}>
          <div style={{ fontFamily: SANS, fontSize: 40, lineHeight: 1.3, color: C.muted }}>
            Planner rank 1: {p1.metric} at {p1.g_m_s2} m/s&sup2;, {p1.p_psia} psia, {Math.round(p1.o2 * 100)}% O&#8322;, the exact lunar
            base air.
          </div>
        </Fade>
        <Fade at={34} style={{ marginTop: 48 }}>
          <div style={{ fontFamily: MONO, fontWeight: 500, fontSize: 46, color: C.fg }}>nasa-hackathon-2026-two.vercel.app</div>
        </Fade>
        <Fade at={42} style={{ marginTop: 18 }}>
          <div style={{ fontFamily: MONO, fontSize: 28, color: C.muted }}>
            BTRMLK &middot; Adityan Kesavan &middot; Flame in Freefall
          </div>
        </Fade>
      </AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: SIDE,
          bottom: 56,
          fontFamily: MONO,
          fontSize: 20,
          color: C.muted,
          opacity: prog(frame, 46, 16),
        }}
      >
        Photos: NASA (as11-44-6549, GRC-1998-C-00486). Data: NASA PSI, CC0. Not a NASA product.
      </div>
    </Scene>
  );
};
