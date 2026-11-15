import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import facts from "../facts.json";
import { Fade, Kicker, Rise, Scene } from "../parts";
import { C, EASE, MONO, SANS, SIDE, hatch, lin, prog } from "../theme";

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

const headline: React.CSSProperties = {
  fontFamily: SANS,
  fontWeight: 600,
  fontSize: 120,
  lineHeight: 1.0,
  letterSpacing: "-0.04em",
  color: C.fg,
};

/** 0:10 The gap: a to-scale gravity axis, every PSI combustion investigation at its two ends, Moon and Mars between. */
export const GapScene: React.FC = () => {
  const frame = useCurrentFrame();
  const X0 = SIDE;
  const W = 1920 - 2 * SIDE;
  const AXIS = 800;
  const gx = (g: number) => X0 + (W * g) / facts.g.earth;
  const axis = prog(frame, 8, 26);
  const drift = lin(frame, 0, 120);
  const sq = (n: number, x: number, color: string, delay: number) =>
    Array.from({ length: n }, (_, i) => {
      const p = prog(frame, delay + i * 1.2, 14);
      return (
        <div
          key={i}
          style={{
            position: "absolute",
            left: x,
            top: AXIS - 20 - i * 15,
            width: 30,
            height: 10,
            backgroundColor: color,
            opacity: p,
            scale: `${p}`,
          }}
        />
      );
    });
  const marker = (g: number, name: string, delay: number) => {
    const p = prog(frame, delay, 20);
    return (
      <div style={{ position: "absolute", left: gx(g), top: 0, opacity: p }}>
        <div
          style={{
            position: "absolute",
            left: -1,
            top: AXIS - 230 + (1 - p) * -80,
            width: 2,
            height: 230,
            backgroundColor: C.accent,
          }}
        />
        <div
          style={{
            position: "absolute",
            left: -13,
            top: AXIS - 13,
            width: 26,
            height: 26,
            borderRadius: 13,
            backgroundColor: C.accent,
            scale: `${p}`,
          }}
        />
        <div
          style={{
            position: "absolute",
            left: 16,
            top: AXIS - 236 + (1 - p) * -80,
            fontFamily: SANS,
            fontWeight: 500,
            fontSize: 52,
            color: C.fg,
            whiteSpace: "nowrap",
          }}
        >
          {name} <span style={{ fontFamily: MONO, fontWeight: 400, fontSize: 40, color: C.accent }}>{g.toFixed(2)}</span>
        </div>
      </div>
    );
  };
  return (
    <Scene>
      <AbsoluteFill style={{ padding: `120px ${SIDE}px 0`, translate: `0 ${-drift * 36}px` }}>
        <Fade at={0} dur={14}>
          <Kicker>The gap</Kicker>
        </Fade>
        <div style={{ ...headline, marginTop: 14 }}>
          <Rise at={2}>NASA&rsquo;s fire data stops</Rise>
          <Rise at={7}>at two gravities.</Rise>
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{ translate: `0 ${-drift * 14}px` }}>
        {/* the gap itself: hatched, no tests */}
        <div
          style={{
            position: "absolute",
            left: X0 + 44,
            top: AXIS - 130,
            width: W - 88,
            height: 130,
            backgroundImage: hatch(C.nodataFill, 9),
            opacity: prog(frame, 24, 20) * 0.9,
          }}
        />
        <div
          style={{
            position: "absolute",
            left: gx(6.6),
            top: AXIS - 92,
            fontFamily: MONO,
            fontSize: 30,
            color: C.fg,
            backgroundColor: C.bg,
            padding: "4px 12px",
            translate: "-50% 0",
            opacity: prog(frame, 30, 18),
            whiteSpace: "nowrap",
          }}
        >
          no fire tested here
        </div>
        {sq(facts.orbitInvestigations, X0, C.micro, 12)}
        {sq(facts.earthInvestigations, X0 + W - 30, C.normal, 16)}
        <div style={{ position: "absolute", left: X0, top: AXIS, width: W * axis, height: 3, backgroundColor: C.fg }} />
        {marker(facts.g.moon, "Moon", 46)}
        {marker(facts.g.mars, "Mars", 54)}
        <div style={{ position: "absolute", left: X0, top: AXIS + 26, fontFamily: MONO, fontSize: 32, color: C.micro, opacity: prog(frame, 18, 16) }}>
          Orbit &asymp; 0
          <div style={{ color: C.muted, fontSize: 24, marginTop: 6 }}>{facts.orbitInvestigations} investigations</div>
        </div>
        <div
          style={{
            position: "absolute",
            right: SIDE,
            top: AXIS + 26,
            textAlign: "right",
            fontFamily: MONO,
            fontSize: 32,
            color: C.normal,
            opacity: prog(frame, 22, 16),
          }}
        >
          Earth {facts.g.earth} m/s&sup2;
          <div style={{ color: C.muted, fontSize: 24, marginTop: 6 }}>{facts.earthInvestigations} investigations</div>
        </div>
        <div
          style={{
            position: "absolute",
            left: gx(facts.g.moon) - 13,
            top: AXIS + 120,
            fontFamily: MONO,
            fontSize: 34,
            color: C.fg,
            opacity: prog(frame, 72, 18),
            translate: `0 ${(1 - prog(frame, 72, 18)) * 16}px`,
          }}
        >
          Habitat air {facts.habitat.p_psia} psia &middot; {Math.round(facts.habitat.o2 * 100)}% O&#8322;
        </div>
      </AbsoluteFill>
    </Scene>
  );
};

/** 0:14 Built on the real tests. */
export const DataScene: React.FC = () => {
  const frame = useCurrentFrame();
  const n = Math.round(
    interpolate(frame, [2, 22], [0, facts.cleanedTests], { easing: EASE, extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
  );
  const drift = lin(frame, 0, 48);
  return (
    <Scene>
      <AbsoluteFill style={{ padding: `0 ${SIDE}px`, justifyContent: "center" }}>
        <div style={{ translate: `0 ${-drift * 30}px` }}>
          <Fade at={0} dur={12}>
            <Kicker>Built on</Kicker>
          </Fade>
          <div
            style={{
              fontFamily: MONO,
              fontWeight: 500,
              fontSize: 380,
              lineHeight: 1,
              letterSpacing: "-0.05em",
              color: C.fg,
              fontVariantNumeric: "tabular-nums",
              marginTop: 6,
            }}
          >
            {n.toLocaleString("en-US")}
          </div>
        </div>
        <Fade at={10} style={{ translate: `0 ${-drift * 60}px` }}>
          <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 84, letterSpacing: "-0.02em", color: C.fg, marginTop: 10 }}>
            real NASA fire tests
            <span style={{ fontFamily: MONO, fontWeight: 400, fontSize: 34, color: C.muted, marginLeft: 28 }}>
              PSI combustion archive
            </span>
          </div>
        </Fade>
      </AbsoluteFill>
    </Scene>
  );
};

/** 0:15.6 The 90% band widens to pay for the gravity difference. */
export const BandScene: React.FC = () => {
  const frame = useCurrentFrame();
  const X0 = SIDE + 420;
  const W = 1920 - SIDE - X0;
  const px = (v: number) => X0 + W * v;
  const grow = prog(frame, 22, 30);
  const [a0, b0] = facts.m1.band0g;
  const [a1, b1] = facts.m1.band90;
  const lo = a0 + (a1 - a0) * grow;
  const hi = b0 + (b1 - b0) * grow;
  const row = (y: number, label: string, sub: string, color: string, l: number, h: number, delay: number, est?: boolean) => {
    const p = prog(frame, delay, 18);
    return (
      <div style={{ position: "absolute", left: 0, top: y, width: 1920, opacity: p }}>
        <div style={{ position: "absolute", left: SIDE, top: 6, fontFamily: SANS, fontWeight: 500, fontSize: 44, color: C.fg }}>
          {label}
          <div style={{ fontFamily: MONO, fontWeight: 400, fontSize: 24, color: C.muted, marginTop: 4 }}>{sub}</div>
        </div>
        <div style={{ position: "absolute", left: X0, top: 44, width: W, height: 2, backgroundColor: C.line }} />
        <div
          style={{
            position: "absolute",
            left: px(l),
            top: 14,
            width: (px(h) - px(l)) * p,
            height: 62,
            backgroundColor: color,
            opacity: 0.32,
          }}
        />
        <div style={{ position: "absolute", left: px(l), top: 14, width: 3, height: 62, backgroundColor: color }} />
        <div style={{ position: "absolute", left: px(h) - 3, top: 14, width: 3, height: 62, backgroundColor: color }} />
        <div style={{ position: "absolute", left: px(l), top: 88, fontFamily: MONO, fontSize: 28, color, translate: "-50% 0" }}>{pct(l)}</div>
        <div style={{ position: "absolute", left: px(h), top: 88, fontFamily: MONO, fontSize: 28, color, translate: "-50% 0" }}>{pct(h)}</div>
        {est ? (
          <>
            <div style={{ position: "absolute", left: px(facts.m1.estimate) - 3, top: 0, width: 6, height: 90, backgroundColor: C.fg }} />
            <div style={{ position: "absolute", left: px(facts.m1.estimate) + 14, top: -64, fontFamily: MONO, fontWeight: 500, fontSize: 48, color: C.fg }}>
              {Math.round(facts.m1.estimate * 100)}%
            </div>
          </>
        ) : null}
      </div>
    );
  };
  return (
    <Scene>
      <AbsoluteFill style={{ padding: `120px ${SIDE}px 0` }}>
        <Fade at={0} dur={12}>
          <Kicker>Carry the evidence across</Kicker>
        </Fade>
        <div style={{ ...headline, marginTop: 14 }}>
          <Rise at={2}>A 90% band that widens</Rise>
          <Rise at={7}>
            <span style={{ color: C.muted }}>to pay for the gap.</span>
          </Rise>
        </div>
      </AbsoluteFill>
      {row(560, "0 g tests", "ISS, microgravity", C.micro, a0, b0, 8)}
      {row(760, "Lunar base", "Moon gravity, 1.62 m/s²", C.accent, lo, hi, 16, true)}
      <div
        style={{
          position: "absolute",
          right: SIDE,
          top: 920,
          fontFamily: MONO,
          fontSize: 28,
          color: C.muted,
          opacity: prog(frame, 40, 16),
          textAlign: "right",
        }}
      >
        M1, droplet flame self-extinguishes &middot; band widened &times;{facts.m1.widen}, confidence {facts.m1.confidence}
      </div>
    </Scene>
  );
};

/** 0:18 Where the data runs out, it says so. */
export const RefusalScene: React.FC = () => {
  const frame = useCurrentFrame();
  const TX = 1120;
  return (
    <Scene>
      <AbsoluteFill style={{ padding: `120px ${SIDE}px 0` }}>
        <Fade at={0} dur={12}>
          <Kicker>Honest by design</Kicker>
        </Fade>
        <div style={{ ...headline, marginTop: 14, width: 920 }}>
          <Rise at={2}>Where data</Rise>
          <Rise at={6}>runs out,</Rise>
          <Rise at={10}>
            <span style={{ color: C.accent }}>it says so.</span>
          </Rise>
        </div>
        <Fade at={40} style={{ marginTop: 60, width: 880 }}>
          <div style={{ fontFamily: MONO, fontSize: 30, lineHeight: 1.45, color: C.muted }}>
            {facts.noEvidence} of {facts.metrics.length} metrics at the lunar base. M2: nearest NASA test at distance{" "}
            <span style={{ color: C.fg }}>{facts.m2.distance}</span>, past the {facts.m2.gate.toFixed(1)} gate.
          </div>
        </Fade>
      </AbsoluteFill>
      {facts.metrics.map((m, i) => {
        const p = prog(frame, 6 + i * 3, 16);
        return (
          <div
            key={m.metric}
            style={{
              position: "absolute",
              left: TX,
              top: 300 + i * 112,
              width: 1920 - SIDE - TX,
              height: 92,
              borderTop: `2px solid ${C.line}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              opacity: p,
              translate: `${(1 - p) * 40}px 0`,
              fontFamily: MONO,
              fontSize: 40,
            }}
          >
            <span style={{ color: C.muted }}>{m.metric}</span>
            {m.applicable && m.estimate !== null ? (
              <span style={{ color: C.fg }}>{pct(m.estimate)}</span>
            ) : (
              <span
                style={{
                  color: C.accent,
                  fontWeight: 500,
                  fontSize: 32,
                  letterSpacing: "0.06em",
                  padding: "6px 16px",
                  border: `3px solid ${C.accent}`,
                  rotate: "-4deg",
                  opacity: prog(frame, 20 + i * 5, 10),
                  scale: `${1.6 - 0.6 * prog(frame, 20 + i * 5, 10)}`,
                }}
              >
                NO EVIDENCE
              </span>
            )}
          </div>
        );
      })}
    </Scene>
  );
};
