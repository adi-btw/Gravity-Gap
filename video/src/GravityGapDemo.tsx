import React from "react";
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { ChallengeScene, TeamScene, TitleScene } from "./scenes/Intro";
import { CloseScene, SectionsScene } from "./scenes/Sections";
import { BandScene, DataScene, GapScene, RefusalScene } from "./scenes/Story";
import { C, MONO, SANS, SIDE } from "./theme";

// Beat sheet in frames at 30 fps; 885 frames = 29.5 s (Space Apps limit is 30 s).
const BEATS = [
  { name: "Team", from: 0, dur: 62 },
  { name: "Challenge", from: 62, dur: 90 },
  { name: "Project", from: 152, dur: 148 },
  { name: "The gap", from: 300, dur: 120 },
  { name: "Data", from: 420, dur: 48 },
  { name: "Band", from: 468, dur: 72 },
  { name: "No evidence", from: 540, dur: 78 },
  { name: "Sections", from: 618, dur: 162 },
  { name: "Impact", from: 780, dur: 105 },
] as const;

/** Persistent frame furniture: project mark, beat index, AI disclosure, progress hairline. */
const Chrome: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const beat = BEATS.findIndex((b) => frame >= b.from && frame < b.from + b.dur);
  const idx = beat < 0 ? BEATS.length - 1 : beat;
  const markIn = interpolate(frame, [56, 70], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          left: SIDE,
          top: 52,
          fontFamily: SANS,
          fontWeight: 500,
          fontSize: 26,
          color: C.fg,
          opacity: markIn,
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <svg width="18" height="24" viewBox="0 0 18 24">
          <path d="M9 1 C13 7 17 11 17 15.5 A8 8 0 0 1 1 15.5 C1 11 5 7 9 1 Z" fill={C.accent} />
        </svg>
        Gravity Gap
        <span style={{ fontFamily: MONO, fontWeight: 400, fontSize: 22, color: C.muted, marginLeft: 10 }}>BTRMLK</span>
      </div>
      <div style={{ position: "absolute", right: SIDE, top: 56, fontFamily: MONO, fontSize: 22, color: C.muted }}>
        {String(idx + 1).padStart(2, "0")} / {String(BEATS.length).padStart(2, "0")}
        <span style={{ color: C.fg, marginLeft: 14 }}>{BEATS[idx].name}</span>
      </div>
      {/* AI disclosure, required by the Space Apps rules: visible on every frame. */}
      <div
        style={{
          position: "absolute",
          right: SIDE,
          bottom: 50,
          fontFamily: MONO,
          fontSize: 22,
          color: C.fg,
          backgroundColor: "rgba(14,15,16,0.78)",
          border: `1px solid ${C.lineStrong}`,
          padding: "6px 12px",
          borderRadius: 2,
        }}
      >
        Made with AI assistance
      </div>
      <div
        style={{
          position: "absolute",
          left: 0,
          bottom: 0,
          height: 4,
          width: `${((frame + 1) / durationInFrames) * 100}%`,
          backgroundColor: C.accent,
        }}
      />
    </AbsoluteFill>
  );
};

export const GravityGapDemo: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <Sequence name="Team" from={0} durationInFrames={62}>
        <TeamScene />
      </Sequence>
      <Sequence name="Challenge" from={62} durationInFrames={90}>
        <ChallengeScene />
      </Sequence>
      <Sequence name="Project" from={152} durationInFrames={148}>
        <TitleScene />
      </Sequence>
      <Sequence name="The gap" from={300} durationInFrames={120}>
        <GapScene />
      </Sequence>
      <Sequence name="Data" from={420} durationInFrames={48}>
        <DataScene />
      </Sequence>
      <Sequence name="Band" from={468} durationInFrames={72}>
        <BandScene />
      </Sequence>
      <Sequence name="No evidence" from={540} durationInFrames={78}>
        <RefusalScene />
      </Sequence>
      <Sequence name="Sections" from={618} durationInFrames={162}>
        <SectionsScene />
      </Sequence>
      <Sequence name="Impact" from={780} durationInFrames={105}>
        <CloseScene />
      </Sequence>
      <Chrome />
    </AbsoluteFill>
  );
};
