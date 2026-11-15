import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";
import { Fade, Kicker, Rise, Scene } from "../parts";
import { C, MONO, SANS, SIDE, lin, prog } from "../theme";

/** 0:00 Team. */
export const TeamScene: React.FC = () => {
  const frame = useCurrentFrame();
  const rule = prog(frame, 10, 30);
  return (
    <Scene fadeIn={0}>
      <AbsoluteFill style={{ padding: `0 ${SIDE}px`, justifyContent: "center" }}>
        <Fade at={0} dur={14}>
          <Kicker>Team</Kicker>
        </Fade>
        <Rise at={2} dur={24} style={{ marginTop: 18 }}>
          <div
            style={{ fontFamily: SANS, fontWeight: 600, fontSize: 330, lineHeight: 0.92, letterSpacing: "-0.045em", color: C.fg }}
          >
            BTRMLK
          </div>
        </Rise>
        <div style={{ height: 2, backgroundColor: C.line, marginTop: 46, width: `${rule * 100}%` }} />
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 34 }}>
          <Fade at={16}>
            <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 84, letterSpacing: "-0.02em", color: C.fg }}>
              Adityan Kesavan
            </div>
          </Fade>
          <Fade at={22}>
            <div style={{ fontFamily: MONO, fontSize: 34, color: C.muted }}>NASA Space Apps Challenge 2026</div>
          </Fade>
        </div>
      </AbsoluteFill>
    </Scene>
  );
};

/** 0:02 The challenge, over NASA's 1 g and 0 g candle photographs drifting at two speeds. */
export const ChallengeScene: React.FC = () => {
  const frame = useCurrentFrame();
  const drift = lin(frame, 0, 95);
  const panel = (src: string, label: string, color: string, x: number, speed: number, delay: number) => {
    const p = prog(frame, delay, 26);
    return (
      <div
        style={{
          position: "absolute",
          left: x,
          top: 120,
          width: 380,
          translate: `0 ${(1 - p) * 120 - drift * speed}px`,
          opacity: p,
        }}
      >
        <div style={{ width: 380, height: 620, overflow: "hidden", backgroundColor: "#000" }}>
          <Img src={staticFile(src)} style={{ width: 380, height: 620, objectFit: "cover", scale: `${1.06 - drift * 0.05}` }} />
        </div>
        <div style={{ fontFamily: MONO, fontSize: 34, color, marginTop: 16 }}>{label}</div>
      </div>
    );
  };
  return (
    <Scene>
      {panel("photos/candle-1g.webp", "1 g  Earth", C.normal, 1000, 70, 4)}
      {panel("photos/candle-0g.webp", "0 g  orbit", C.micro, 1400, 30, 10)}
      <div style={{ position: "absolute", left: 1000, top: 836, fontFamily: MONO, fontSize: 20, color: C.muted, opacity: prog(frame, 20, 20), translate: `0 ${-drift * 30}px` }}>
        Photo: NASA, GRC-1998-C-00486
      </div>
      <AbsoluteFill style={{ padding: `0 ${SIDE}px`, justifyContent: "flex-end", paddingBottom: 150 }}>
        <Fade at={6} dur={14}>
          <Kicker>Challenge</Kicker>
        </Fade>
        <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 176, lineHeight: 0.98, letterSpacing: "-0.04em", color: C.fg, marginTop: 16 }}>
          <Rise at={8}>Flame in</Rise>
          <Rise at={14}>
            <span style={{ color: C.accent }}>Freefall</span>
          </Rise>
        </div>
      </AbsoluteFill>
    </Scene>
  );
};

/** 0:05 Project name and tagline, inside the Apollo 11 Earthrise cut into two planes. */
export const TitleScene: React.FC = () => {
  const frame = useCurrentFrame();
  const t = lin(frame, 0, 150);
  const intro = prog(frame, 0, 60);
  // Planes are 1.4x the 1920 source; the horizon sits at y = 700 when settled.
  const plane: React.CSSProperties = { position: "absolute", left: -40, top: -476, width: 2688, height: 2688 };
  return (
    <Scene>
      <Img
        src={staticFile("photos/cover-earth.webp")}
        style={{ ...plane, translate: `${-t * 40}px ${(1 - intro) * 110 - t * 30}px` }}
      />
      <AbsoluteFill style={{ padding: `150px ${SIDE}px 0` }}>
        <div style={{ translate: `0 ${-t * 60}px` }}>
          <Fade at={8} dur={14}>
            <Kicker>Project</Kicker>
          </Fade>
          <Rise at={14} dur={26} style={{ marginTop: 10 }}>
            <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 200, lineHeight: 1, letterSpacing: "-0.045em", color: C.fg }}>
              Gravity Gap
            </div>
          </Rise>
          <Fade at={34} style={{ marginTop: 26 }}>
            <div style={{ fontFamily: SANS, fontWeight: 400, fontSize: 50, lineHeight: 1.22, color: C.muted, width: 900 }}>
              How a fire would behave on the Moon and Mars, from real NASA tests.
            </div>
          </Fade>
        </div>
      </AbsoluteFill>
      <Img
        src={staticFile("photos/cover-moon.webp")}
        style={{ ...plane, translate: `${-t * 90}px ${(1 - intro) * 300 - t * 90}px` }}
      />
      <div
        style={{
          position: "absolute",
          left: SIDE,
          bottom: 60,
          fontFamily: MONO,
          fontSize: 20,
          color: C.fg,
          backgroundColor: "rgba(14,15,16,0.72)",
          padding: "6px 12px",
          borderRadius: 2,
          opacity: prog(frame, 30, 20),
        }}
      >
        Photo: NASA, Apollo 11, as11-44-6549
      </div>
    </Scene>
  );
};
