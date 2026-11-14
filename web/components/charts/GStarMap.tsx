"use client";

import { useMemo } from "react";
import { G0, gStar, P0_PSIA } from "@/lib/physics";
import { fmtSig } from "@/lib/format";

const W = 640;
const H = 400;
const M = { l: 60, r: 90, t: 16, b: 48 };
const PW = W - M.l - M.r;
const PH = H - M.t - M.b;
export const G_RANGE = [0, 9.81] as const;
export const P_RANGE = [4, 15] as const;

const xOf = (g: number) => M.l + ((g - G_RANGE[0]) / (G_RANGE[1] - G_RANGE[0])) * PW;
const yOf = (p: number) => M.t + (1 - (p - P_RANGE[0]) / (P_RANGE[1] - P_RANGE[0])) * PH;

// Sequential ramp (dark indigo → violet → amber), legible on both themes; mapped on log10(G*).
const RAMP = ["#1e1b4b", "#3b2a83", "#6d28d9", "#a21caf", "#db2777", "#f97316", "#fbbf24"];
const LOG_MIN = -3;
const LOG_MAX = Math.log10(gStar(9.81, 15)); // ≈ 0.018

function hexToRgb(h: string): [number, number, number] {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function colorFor(gs: number): string {
  const t = Math.min(1, Math.max(0, (Math.log10(Math.max(gs, 1e-12)) - LOG_MIN) / (LOG_MAX - LOG_MIN)));
  const pos = t * (RAMP.length - 1);
  const i = Math.min(RAMP.length - 2, Math.floor(pos));
  const f = pos - i;
  const a = hexToRgb(RAMP[i]);
  const b = hexToRgb(RAMP[i + 1]);
  const c = a.map((v, k) => Math.round(v + (b[k] - v) * f));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export interface Marker {
  id: string;
  label: string;
  g: number;
  p: number;
  /** Put the label above the marker (avoids collisions between nearby habitats). */
  above?: boolean;
}

interface Props {
  markers: Marker[];
  current: { g: number; p: number };
}

/** F3: G* = (g/g0)(P/P0)² heat map over g × P with habitat markers and iso-G* contours. */
export function GStarMap({ markers, current }: Props) {
  const cells = useMemo(() => {
    const nx = 49;
    const ny = 44;
    const dg = (G_RANGE[1] - G_RANGE[0]) / nx;
    const dp = (P_RANGE[1] - P_RANGE[0]) / ny;
    const out: { x: number; y: number; w: number; h: number; fill: string }[] = [];
    for (let i = 0; i < nx; i++) {
      for (let j = 0; j < ny; j++) {
        const g = G_RANGE[0] + (i + 0.5) * dg;
        const p = P_RANGE[0] + (j + 0.5) * dp;
        out.push({
          x: xOf(G_RANGE[0] + i * dg),
          y: yOf(P_RANGE[0] + (j + 1) * dp),
          w: PW / nx + 0.5,
          h: PH / ny + 0.5,
          fill: colorFor(gStar(g, p)),
        });
      }
    }
    return out;
  }, []);

  const contours = useMemo(() => {
    const levels = [0.01, 0.05, 0.1, 0.25, 0.5, 1];
    return levels.map((lvl) => {
      const pts: string[] = [];
      for (let k = 1; k <= 120; k++) {
        const g = (G_RANGE[1] * k) / 120;
        const p = P0_PSIA * Math.sqrt((lvl * G0) / g);
        if (p >= P_RANGE[0] && p <= P_RANGE[1]) pts.push(`${xOf(g).toFixed(1)},${yOf(p).toFixed(1)}`);
      }
      return { lvl, pts };
    });
  }, []);

  const gTicks = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9.81];
  const pTicks = [4, 6, 8, 10, 12, 14, 15];
  const legendStops = [-3, -2, -1, 0];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full"
      role="img"
      aria-label={`Heat map of G star, buoyant flow strength relative to Earth sea level, over gravity 0 to 9.81 m/s² and pressure 4 to 15 psia. Current habitat G star is ${fmtSig(gStar(current.g, current.p))}. Habitat markers: ${markers.map((m) => `${m.label} ${fmtSig(gStar(m.g, m.p))}`).join("; ")}.`}
    >
      <defs>
        <pattern id="gs-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" stroke="var(--nodata)" strokeWidth="3" />
        </pattern>
      </defs>
      <g shapeRendering="crispEdges">
        {cells.map((c, i) => (
          <rect key={i} x={c.x} y={c.y} width={c.w} height={c.h} fill={c.fill} />
        ))}
      </g>
      {/* g = 0 edge: G* = 0, no buoyancy */}
      <rect x={M.l} y={M.t} width={5} height={PH} fill="url(#gs-hatch)" />

      {contours.map(({ lvl, pts }) =>
        pts.length > 1 ? (
          <g key={lvl}>
            <polyline points={pts.join(" ")} fill="none" stroke="#ffffff" strokeOpacity={0.55} strokeWidth={1} strokeDasharray="4 3" />
            <text
              x={Number(pts[pts.length - 1].split(",")[0]) - 4}
              y={Number(pts[pts.length - 1].split(",")[1]) - 4}
              fontSize={10}
              fill="#ffffff"
              textAnchor="end"
              className="num"
            >
              G*={lvl}
            </text>
          </g>
        ) : null,
      )}

      {/* axes */}
      <g fontSize={11} fill="var(--muted)" className="num">
        {gTicks.map((t) => (
          <g key={`g${t}`}>
            <line x1={xOf(t)} x2={xOf(t)} y1={M.t + PH} y2={M.t + PH + 5} stroke="var(--line)" />
            <text x={xOf(t)} y={M.t + PH + 18} textAnchor="middle">
              {t === 9.81 ? "" : t}
            </text>
          </g>
        ))}
        {pTicks.map((t) => (
          <g key={`p${t}`}>
            <line x1={M.l - 5} x2={M.l} y1={yOf(t)} y2={yOf(t)} stroke="var(--line)" />
            <text x={M.l - 8} y={yOf(t) + 4} textAnchor="end">
              {t}
            </text>
          </g>
        ))}
      </g>
      <rect x={M.l} y={M.t} width={PW} height={PH} fill="none" stroke="var(--line)" />
      <text x={M.l + PW / 2} y={H - 8} fontSize={12} fill="var(--fg)" textAnchor="middle">
        Gravity g (m/s²)
      </text>
      <text transform={`translate(16 ${M.t + PH / 2}) rotate(-90)`} fontSize={12} fill="var(--fg)" textAnchor="middle">
        Cabin pressure P (psia)
      </text>

      {/* habitat markers */}
      {markers.map((m) => {
        const x = xOf(m.g);
        const y = yOf(m.p);
        const right = x > M.l + PW - 120;
        return (
          <g key={m.id}>
            <rect x={x - 5} y={y - 5} width={10} height={10} fill="#ffffff" stroke="#111827" strokeWidth={1.5} transform={`rotate(45 ${x} ${y})`} />
            <text
              x={m.above ? x : right ? x - 10 : x + 10}
              y={m.above ? y - 12 : y + 4}
              fontSize={11}
              fill="#ffffff"
              stroke="#111827"
              strokeWidth={3}
              paintOrder="stroke"
              fontWeight={600}
              textAnchor={m.above ? "middle" : right ? "end" : "start"}
            >
              {m.label} · {fmtSig(gStar(m.g, m.p), 2)}
            </text>
          </g>
        );
      })}
      <g>
        <circle cx={xOf(current.g)} cy={yOf(Math.min(Math.max(current.p, P_RANGE[0]), P_RANGE[1]))} r={8} fill="none" stroke="#ffffff" strokeWidth={2.5} />
        <circle cx={xOf(current.g)} cy={yOf(Math.min(Math.max(current.p, P_RANGE[0]), P_RANGE[1]))} r={8} fill="none" stroke="#111827" strokeWidth={1} />
      </g>

      {/* legend */}
      <g transform={`translate(${M.l + PW + 22} ${M.t})`}>
        <text x={0} y={0} dy={10} fontSize={11} fill="var(--fg)">
          G*
        </text>
        {Array.from({ length: 40 }, (_, i) => {
          const lg = LOG_MAX - ((LOG_MAX - LOG_MIN) * i) / 39;
          return <rect key={i} x={0} y={18 + i * 6} width={16} height={6.5} fill={colorFor(10 ** lg)} />;
        })}
        {legendStops.map((s) => {
          const y = 18 + ((LOG_MAX - s) / (LOG_MAX - LOG_MIN)) * 240;
          return (
            <text key={s} x={22} y={y + 4} fontSize={10} fill="var(--muted)" className="num">
              {10 ** s >= 1 ? "1" : (10 ** s).toString()}
            </text>
          );
        })}
        <rect x={0} y={272} width={16} height={12} fill="url(#gs-hatch)" />
        <text x={22} y={282} fontSize={10} fill="var(--muted)">
          0 (0 g)
        </text>
        <circle cx={8} cy={302} r={6} fill="none" stroke="var(--fg)" strokeWidth={2} />
        <text x={22} y={306} fontSize={10} fill="var(--muted)">
          You
        </text>
      </g>
    </svg>
  );
}
