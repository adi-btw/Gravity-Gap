import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { C, EASE, MONO, prog } from "./theme";

/** A scene wrapper: dark ground, short fade in and out so cuts dip through black instead of flashing. */
export const Scene: React.FC<{ children: React.ReactNode; fadeIn?: number; fadeOut?: number }> = ({
  children,
  fadeIn = 8,
  fadeOut = 8,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const opacity = Math.min(
    fadeIn ? interpolate(frame, [0, fadeIn], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 1,
    fadeOut
      ? interpolate(frame, [durationInFrames - fadeOut, durationInFrames], [1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: EASE,
        })
      : 1,
  );
  return <AbsoluteFill style={{ backgroundColor: C.bg, opacity }}>{children}</AbsoluteFill>;
};

/** Text that rises out of a mask (a clipped line), the one entrance used for display type. */
export const Rise: React.FC<{
  at: number;
  dur?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ at, dur = 22, children, style }) => {
  const frame = useCurrentFrame();
  const p = prog(frame, at, dur);
  return (
    <div style={{ overflow: "hidden", paddingBottom: "0.08em", marginBottom: "-0.08em", ...style }}>
      <div style={{ translate: `0 ${(1 - p) * 105}%` }}>{children}</div>
    </div>
  );
};

/** A plain fade-and-lift, for supporting lines. */
export const Fade: React.FC<{
  at: number;
  dur?: number;
  lift?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ at, dur = 18, lift = 24, children, style }) => {
  const frame = useCurrentFrame();
  const p = prog(frame, at, dur);
  return <div style={{ opacity: p, translate: `0 ${(1 - p) * lift}px`, ...style }}>{children}</div>;
};

/** Small mono label in the accent, used once per scene to name it. */
export const Kicker: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <div style={{ fontFamily: MONO, fontSize: 30, letterSpacing: "0.02em", color: C.accent, ...style }}>{children}</div>
);
