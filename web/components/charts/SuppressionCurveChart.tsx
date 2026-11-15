"use client";

import { useId } from "react";
import { fmtSig } from "@/lib/format";
import { binMid, fmtPct, layoutCurve } from "@/lib/suppression";
import type { SuppressionPoint, SuppressionReferenceBin } from "@/lib/types";

interface Props {
  points: SuppressionPoint[];
  metric: "M1" | "M2";
  /** Fixed y domain (e.g. [0, 1] for M1). */
  domain?: [number, number];
  yLabel: string;
  xLabel: string;
  /** x upper bound (the diluent's sweep max). */
  xMax: number;
  ariaLabel: string;
  dose?: { fraction: number; label: string } | null;
  reference?: SuppressionReferenceBin[];
  color?: string;
  fill?: string;
  testId?: string;
}

const W = 640;
const H = 300;
const M = { l: 56, r: 16, t: 28, b: 44 };
const FUEL_SHAPES = ["circle", "square", "triangle"] as const;

function niceDomain(vals: number[]): [number, number] {
  if (!vals.length) return [0, 1];
  let lo = Math.min(...vals);
  let hi = Math.max(...vals);
  if (lo === hi) {
    lo -= Math.abs(lo) * 0.2 || 1;
    hi += Math.abs(hi) * 0.2 || 1;
  }
  const pad = (hi - lo) * 0.1;
  return [lo >= 0 && lo - pad < 0 ? 0 : lo - pad, hi + pad];
}

/**
 * A metric vs diluent fraction with its 90% band. Each run of applicable points is its own line and band;
 * non-applicable stretches are hatched "no evidence" gaps and the line never crosses them.
 */
export function SuppressionCurveChart({
  points,
  metric,
  domain,
  yLabel,
  xLabel,
  xMax,
  ariaLabel,
  dose,
  reference = [],
  color = "var(--partial)",
  fill = "var(--partial-fill)",
  testId,
}: Props) {
  const pid = useId().replace(/:/g, "");
  const { segments, gaps } = layoutCurve(points, metric);
  const vals = segments.flat().flatMap((v) => [v.estimate, ...(v.band ?? [])]);
  const [lo, hi] = domain ?? niceDomain(vals);
  const xHi = Math.max(xMax, ...points.map((p) => p.fraction), 0.05);
  const x = (f: number) => M.l + (f / xHi) * (W - M.l - M.r);
  const y = (v: number) => M.t + (1 - (Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo || 1)) * (H - M.t - M.b);
  const xStep = xHi > 0.3 ? 0.1 : 0.05;
  const xTicks = Array.from({ length: Math.floor(xHi / xStep + 1e-9) + 1 }, (_, i) => i * xStep);
  const yTicks = Array.from({ length: 5 }, (_, i) => lo + ((hi - lo) * i) / 4);
  const fuels = [...new Set(reference.map((r) => r.fuel ?? "all fuels"))];
  const gapMinPx = 3;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={ariaLabel} data-testid={testId}>
      <defs>
        <pattern id={`hatch-${pid}`} width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="8" height="8" fill="var(--nodata-fill)" opacity={0.35} />
          <line x1="0" y1="0" x2="0" y2="8" stroke="var(--nodata)" strokeWidth="3" />
        </pattern>
      </defs>
      {yTicks.map((t) => (
        <g key={`y${t}`} aria-hidden="true">
          <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeDasharray="2 4" />
          <text x={M.l - 6} y={y(t) + 4} fontSize={11} textAnchor="end" fill="var(--muted)" className="num">
            {domain && domain[1] === 1 ? `${Math.round(t * 100)}%` : fmtSig(t, 3)}
          </text>
        </g>
      ))}
      {xTicks.map((t) => (
        <text key={`x${t}`} x={x(t)} y={H - M.b + 16} fontSize={11} textAnchor="middle" fill="var(--muted)" className="num" aria-hidden="true">
          {fmtPct(t)}
        </text>
      ))}
      <text x={(M.l + W - M.r) / 2} y={H - 6} fontSize={11} textAnchor="middle" fill="var(--muted)" aria-hidden="true">
        {xLabel}
      </text>
      <text transform={`translate(14 ${(M.t + H - M.b) / 2}) rotate(-90)`} fontSize={11} textAnchor="middle" fill="var(--muted)" aria-hidden="true">
        {yLabel}
      </text>

      <g aria-hidden="true" data-testid={testId ? `${testId}-gaps` : undefined}>
        {gaps.map((g, i) => {
          const gx = x(g.from);
          const gw = Math.max(gapMinPx, x(g.to) - gx);
          return (
            <g key={i} data-gap="true">
              <rect x={gx} y={M.t} width={gw} height={H - M.t - M.b} fill={`url(#hatch-${pid})`} stroke="var(--nodata)" strokeDasharray="3 3" />
              {gw > 70 ? (
                <text x={gx + gw / 2} y={M.t + 16} fontSize={11} textAnchor="middle" fill="var(--fg)" className="svg-halo" fontWeight={500}>
                  no evidence
                </text>
              ) : null}
            </g>
          );
        })}
      </g>

      <g aria-hidden="true">
        {segments.map((seg, i) => {
          const banded = seg.filter((v) => v.band);
          const bandPath =
            banded.length >= 2
              ? `M ${banded.map((v) => `${x(v.fraction)} ${y((v.band as [number, number])[1])}`).join(" L ")} L ${[...banded]
                  .reverse()
                  .map((v) => `${x(v.fraction)} ${y((v.band as [number, number])[0])}`)
                  .join(" L ")} Z`
              : null;
          return (
            <g key={i} data-segment="true">
              {bandPath ? <path d={bandPath} fill={fill} stroke="none" /> : null}
              {banded.length === 1 ? (
                <line
                  x1={x(banded[0].fraction)}
                  x2={x(banded[0].fraction)}
                  y1={y((banded[0].band as [number, number])[0])}
                  y2={y((banded[0].band as [number, number])[1])}
                  stroke={color}
                  strokeWidth={6}
                  strokeOpacity={0.35}
                />
              ) : null}
              {seg.length >= 2 ? (
                <path d={`M ${seg.map((v) => `${x(v.fraction)} ${y(v.estimate)}`).join(" L ")}`} fill="none" stroke={color} strokeWidth={2.5} />
              ) : null}
              {seg.map((v) => (
                <circle key={v.fraction} cx={x(v.fraction)} cy={y(v.estimate)} r={3} fill={color} />
              ))}
            </g>
          );
        })}
      </g>

      {reference.length ? (
        <g aria-hidden="true" data-testid={testId ? `${testId}-reference` : undefined}>
          {reference.map((r, i) => {
            const cx = x(binMid(r));
            const cy = y(r.extinction_rate as number);
            const shape = FUEL_SHAPES[Math.max(0, fuels.indexOf(r.fuel ?? "all fuels")) % FUEL_SHAPES.length];
            return (
              <g key={i}>
                {r.interval ? (
                  <line x1={cx} x2={cx} y1={y(r.interval[0])} y2={y(r.interval[1])} stroke="var(--normal)" strokeWidth={1.5} />
                ) : null}
                {shape === "circle" ? (
                  <circle cx={cx} cy={cy} r={4.5} fill="var(--surface)" stroke="var(--normal)" strokeWidth={2} />
                ) : shape === "square" ? (
                  <rect x={cx - 4} y={cy - 4} width={8} height={8} fill="var(--surface)" stroke="var(--normal)" strokeWidth={2} />
                ) : (
                  <path d={`M ${cx} ${cy - 5} L ${cx + 5} ${cy + 4} L ${cx - 5} ${cy + 4} Z`} fill="var(--surface)" stroke="var(--normal)" strokeWidth={2} />
                )}
                <title>{`FLEX tests (raw), ${r.fuel ?? "all fuels"}, ${fmtPct(r.fraction[0])}–${fmtPct(r.fraction[1])}: ${r.extinctions ?? "?"} of ${r.n} extinguished`}</title>
              </g>
            );
          })}
        </g>
      ) : null}

      {dose ? (
        <g aria-hidden="true" data-testid={testId ? `${testId}-dose` : undefined}>
          <line x1={x(dose.fraction)} x2={x(dose.fraction)} y1={M.t - 4} y2={H - M.b} stroke="var(--fg)" strokeWidth={1.5} strokeDasharray="6 4" />
          {domain && domain[1] === 1 ? (
            <line x1={M.l} x2={W - M.r} y1={y(0.9)} y2={y(0.9)} stroke="var(--fg)" strokeOpacity={0.4} strokeDasharray="1 3" />
          ) : null}
          <text
            x={x(dose.fraction) + (x(dose.fraction) > W - 200 ? -6 : 6)}
            y={M.t - 10}
            fontSize={12}
            fontWeight={500}
            textAnchor={x(dose.fraction) > W - 200 ? "end" : "start"}
            fill="var(--fg)"
            className="svg-halo"
          >
            {dose.label}
          </text>
        </g>
      ) : null}

      <line x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} stroke="var(--fg)" aria-hidden="true" />
      <line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} stroke="var(--fg)" aria-hidden="true" />
    </svg>
  );
}
