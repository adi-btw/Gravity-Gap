"use client";

import { useMemo } from "react";
import { buoyantVelocityCmS, RI_BUOYANT_MIN, RI_FORCED_MAX } from "@/lib/physics";

export const U_MAX = 40;
export const L_MIN = 1;
export const L_MAX = 100;

const W = 640;
const H = 380;
const M = { l: 60, r: 18, t: 16, b: 48 };
const PW = W - M.l - M.r;
const PH = H - M.t - M.b;

const xOf = (u: number) => M.l + (Math.min(Math.max(u, 0), U_MAX) / U_MAX) * PW;
const yOf = (L: number) =>
  M.t + (1 - (Math.log10(Math.min(Math.max(L, L_MIN), L_MAX)) - 0) / 2) * PH;

/** Vent speed at which Ri equals riCrit for flame size L: u = u_b / sqrt(Ri). */
export function ventForRi(g: number, L: number, riCrit: number): number {
  return buoyantVelocityCmS(g, L) / Math.sqrt(riCrit);
}

interface Props {
  g: number;
  u: number;
  L: number;
}

/**
 * F2 regime map: x = vent speed (0–40 cm/s), y = flame size (1–100 mm, log).
 * Regions come from the Ri thresholds solved analytically per L, so the boundaries are exact.
 */
export function RegimeMap({ g, u, L }: Props) {
  const { forced, mixed, buoyant, lineB, lineF } = useMemo(() => {
    const n = 80;
    const Ls = Array.from({ length: n + 1 }, (_, i) => 10 ** ((2 * i) / n));
    const xb = Ls.map((l) => [xOf(ventForRi(g, l, RI_BUOYANT_MIN)), yOf(l)] as const);
    const xf = Ls.map((l) => [xOf(ventForRi(g, l, RI_FORCED_MAX)), yOf(l)] as const);
    const pts = (a: readonly (readonly [number, number])[]) => a.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
    const top = yOf(L_MAX);
    const bottom = yOf(L_MIN);
    const right = xOf(U_MAX);
    const left = xOf(0);
    return {
      forced: `${pts(xf)} ${right},${top} ${right},${bottom}`,
      buoyant: `${left},${bottom} ${pts(xb)} ${left},${top}`,
      mixed: `${pts(xb)} ${pts([...xf].reverse())}`,
      lineB: pts(xb),
      lineF: pts(xf),
    };
  }, [g]);

  const xTicks = [0, 5, 10, 15, 20, 25, 30, 35, 40];
  const yTicks = [1, 2, 5, 10, 20, 50, 100];
  const px = xOf(u);
  const py = yOf(L);
  const offScale = u > U_MAX || L > L_MAX || L < L_MIN;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full"
      role="img"
      aria-label={`Regime map at g = ${g.toFixed(2)} m/s². Horizontal axis vent speed 0 to 40 cm/s, vertical axis flame size 1 to 100 mm on a log scale. Regions: buoyancy dominated at low vent speed, mixed in between, forced-flow dominated at high vent speed. Current point: ${u.toFixed(1)} cm/s, ${L.toFixed(0)} mm.`}
    >
      <defs>
        <clipPath id="rm-plot">
          <rect x={M.l} y={M.t} width={PW} height={PH} />
        </clipPath>
      </defs>
      <rect x={M.l} y={M.t} width={PW} height={PH} fill="var(--surface-2)" />
      <g clipPath="url(#rm-plot)">
        <polygon points={forced} fill="var(--micro-fill)" />
        <polygon points={mixed} fill="var(--partial-fill)" />
        <polygon points={buoyant} fill="var(--normal-fill)" />
        {g > 0 ? (
          <>
            <polyline points={lineB} fill="none" stroke="var(--normal)" strokeWidth={1.5} strokeDasharray="5 3" />
            <polyline points={lineF} fill="none" stroke="var(--micro)" strokeWidth={1.5} strokeDasharray="5 3" />
          </>
        ) : null}
        {/* lunar cabin ventilation band from the F2 insight (5–15 cm/s) */}
        <rect x={xOf(5)} y={M.t} width={xOf(15) - xOf(5)} height={PH} fill="none" stroke="var(--muted)" strokeDasharray="2 4" />
      </g>

      {/* region labels */}
      {g > 0 ? (
        <>
          <text x={M.l + 8} y={M.t + 18} fontSize={12} fill="var(--normal)" fontWeight={600} className="svg-halo">
            ↑ BUOYANT (Ri &gt; 10)
          </text>
          <text x={W - M.r - 8} y={H - M.b - 10} fontSize={12} fill="var(--micro)" fontWeight={600} textAnchor="end" className="svg-halo">
            → FORCED (Ri &lt; 0.1)
          </text>
        </>
      ) : (
        <text x={M.l + PW / 2} y={M.t + PH / 2} fontSize={13} fill="var(--micro)" fontWeight={600} textAnchor="middle" className="svg-halo">
          g = 0: no buoyancy, every point is FORCED (Ri = 0)
        </text>
      )}
      <text x={xOf(10)} y={M.t + PH - 6} fontSize={10} fill="var(--muted)" textAnchor="middle" className="svg-halo">
        5–15 cm/s cabin vent
      </text>

      {/* axes */}
      <g fontSize={11} fill="var(--muted)" className="num">
        {xTicks.map((t) => (
          <g key={`x${t}`}>
            <line x1={xOf(t)} x2={xOf(t)} y1={M.t + PH} y2={M.t + PH + 5} stroke="var(--line)" />
            <text x={xOf(t)} y={M.t + PH + 18} textAnchor="middle">
              {t}
            </text>
          </g>
        ))}
        {yTicks.map((t) => (
          <g key={`y${t}`}>
            <line x1={M.l - 5} x2={M.l} y1={yOf(t)} y2={yOf(t)} stroke="var(--line)" />
            <line x1={M.l} x2={M.l + PW} y1={yOf(t)} y2={yOf(t)} stroke="var(--line)" strokeOpacity={0.35} />
            <text x={M.l - 8} y={yOf(t) + 4} textAnchor="end">
              {t}
            </text>
          </g>
        ))}
      </g>
      <rect x={M.l} y={M.t} width={PW} height={PH} fill="none" stroke="var(--line)" />
      <text x={M.l + PW / 2} y={H - 8} fontSize={12} fill="var(--fg)" textAnchor="middle">
        Vent (forced) flow speed u_f (cm/s)
      </text>
      <text transform={`translate(16 ${M.t + PH / 2}) rotate(-90)`} fontSize={12} fill="var(--fg)" textAnchor="middle">
        Flame size L (mm, log)
      </text>

      {/* current point */}
      <g>
        <line x1={px} x2={px} y1={M.t} y2={M.t + PH} stroke="var(--fg)" strokeOpacity={0.35} />
        <line x1={M.l} x2={M.l + PW} y1={py} y2={py} stroke="var(--fg)" strokeOpacity={0.35} />
        <circle cx={px} cy={py} r={7} fill="var(--bg)" stroke="var(--fg)" strokeWidth={2.5} />
        <circle cx={px} cy={py} r={2.5} fill="var(--fg)" />
        <text
          x={px + (px > W - 160 ? -12 : 12)}
          y={py - 10}
          fontSize={12}
          fill="var(--fg)"
          fontWeight={600}
          textAnchor={px > W - 160 ? "end" : "start"}
        >
          Your habitat{offScale ? " (clipped to chart)" : ""}
        </text>
      </g>
    </svg>
  );
}
