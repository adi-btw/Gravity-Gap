import type { MapPoint } from "@/lib/holdout";
import { PSIA_PER_ATM } from "@/lib/physics";

const W = 640;
const H = 320;
const M = { l: 60, r: 16, t: 16, b: 46 };
// Same axes as CoverageChart: O2 (% of the air) linear, cabin pressure in psia on a log scale.
const LOG_TICKS = [0.1, 0.25, 0.5, 1, 2, 4, 8];

function clamp(v: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, v));
}

/** Marker shapes (shape, not colour alone): hit = filled circle, miss = hollow circle with a cross, grey = square / dashed ring. */
export function HoldoutMarker({ p, cx, cy, r }: { p: Pick<MapPoint, "mark" | "greyReason">; cx: number; cy: number; r: number }) {
  if (p.mark === "hit") return <circle cx={cx} cy={cy} r={r} fill="var(--micro)" stroke="var(--micro)" strokeWidth={1.5} />;
  if (p.mark === "miss") {
    const d = r * 0.75;
    return (
      <g>
        <circle cx={cx} cy={cy} r={r + 1} fill="var(--surface)" stroke="var(--warn)" strokeWidth={2} />
        <path d={`M ${cx - d} ${cy - d} L ${cx + d} ${cy + d} M ${cx - d} ${cy + d} L ${cx + d} ${cy - d}`} stroke="var(--warn)" strokeWidth={2} />
      </g>
    );
  }
  if (p.greyReason === "skipped") {
    return <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--nodata)" strokeWidth={1.5} strokeDasharray="2 2" />;
  }
  return <rect x={cx - r} y={cy - r} width={2 * r} height={2 * r} fill="var(--nodata)" stroke="var(--nodata)" strokeWidth={1} />;
}

/**
 * Held-out tested atmospheres on the O2 x pressure plane for one metric and one scheme: did the band shown without
 * those tests catch them? Misses are drawn last so they are never hidden under a hit at the same O2 and pressure.
 */
export function HoldoutMap({ points, ariaLabel }: { points: MapPoint[]; ariaLabel: string }) {
  const o2s = points.map((p) => p.o2);
  const ps = points.map((p) => p.p_atm);
  const xLo = clamp(Math.min(...o2s, 0.21) - 0.03, 0, 1);
  const xHi = clamp(Math.max(...o2s, 0.21) + 0.03, 0, 1);
  const yLo = clamp(Math.min(...ps, 1) / 1.4, 0.05, 20);
  const yHi = clamp(Math.max(...ps, 1) * 1.4, 0.05, 20);
  const x = (o2: number) => M.l + ((o2 - xLo) / (xHi - xLo || 1)) * (W - M.l - M.r);
  const y = (p: number) => M.t + (1 - (Math.log(p) - Math.log(yLo)) / (Math.log(yHi) - Math.log(yLo) || 1)) * (H - M.t - M.b);
  const xTicks = Array.from({ length: 5 }, (_, i) => xLo + ((xHi - xLo) * i) / 4);
  const yTicks = LOG_TICKS.filter((t) => t >= yLo && t <= yHi);
  const order = { grey: 0, hit: 1, miss: 2 } as const;
  const sorted = [...points].sort((a, b) => order[a.mark] - order[b.mark]);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={ariaLabel} data-testid="holdout-map">
      {xTicks.map((t) => (
        <g key={`x${t}`} aria-hidden="true">
          <line x1={x(t)} x2={x(t)} y1={M.t} y2={H - M.b} stroke="var(--line)" strokeDasharray="2 4" />
          <text x={x(t)} y={H - M.b + 16} fontSize={11} textAnchor="middle" fill="var(--muted)" className="num">
            {(t * 100).toFixed(0)}%
          </text>
        </g>
      ))}
      {yTicks.map((t) => (
        <g key={`y${t}`} aria-hidden="true">
          <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeDasharray="2 4" />
          <text x={M.l - 6} y={y(t) + 4} fontSize={11} textAnchor="end" fill="var(--muted)" className="num">
            {(t * PSIA_PER_ATM).toFixed(t < 1 ? 1 : 0)}
          </text>
        </g>
      ))}
      <text x={(M.l + W - M.r) / 2} y={H - 6} fontSize={11} textAnchor="middle" fill="var(--muted)" aria-hidden="true">
        oxygen (% of the air)
      </text>
      <text transform={`translate(14 ${(M.t + H - M.b) / 2}) rotate(-90)`} fontSize={11} textAnchor="middle" fill="var(--muted)" aria-hidden="true">
        cabin pressure (psia, log scale)
      </text>
      <g aria-hidden="true">
        {sorted.map((p) => (
          <g key={p.id} data-mark={p.mark} data-grey={p.greyReason ?? undefined}>
            <title>{p.label}</title>
            <HoldoutMarker p={p} cx={x(p.o2)} cy={y(p.p_atm)} r={2.5 + Math.min(4, Math.sqrt(p.n_tests))} />
          </g>
        ))}
      </g>
      <line x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} stroke="var(--fg)" aria-hidden="true" />
      <line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} stroke="var(--fg)" aria-hidden="true" />
    </svg>
  );
}
