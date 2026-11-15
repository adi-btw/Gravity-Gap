import { fmtPct } from "@/lib/suppression";
import type { SuppressionTested } from "@/lib/types";

interface Props {
  tested: SuppressionTested[];
  habitatO2: number;
  habitatLabel: string;
  xMax: number;
  diluentName: string;
  ariaLabel: string;
}

const W = 640;
const H = 280;
const M = { l: 56, r: 16, t: 16, b: 44 };

/** "Where dilution was tested": FLEX diluted tests (x = diluent fraction, y = O2) and the habitat's O2 as a line. */
export function TestedDilutionChart({ tested, habitatO2, habitatLabel, xMax, diluentName, ariaLabel }: Props) {
  const o2s = [...tested.map((t) => t.o2), habitatO2];
  const yLo = Math.max(0, Math.floor((Math.min(...o2s) - 0.03) * 20) / 20);
  const yHi = Math.min(1, Math.ceil((Math.max(...o2s) + 0.03) * 20) / 20);
  const xHi = Math.max(xMax, ...tested.map((t) => t.fraction), 0.05);
  const x = (f: number) => M.l + (f / xHi) * (W - M.l - M.r);
  const y = (o2: number) => M.t + (1 - (o2 - yLo) / (yHi - yLo || 1)) * (H - M.t - M.b);
  const xStep = xHi > 0.3 ? 0.1 : 0.05;
  const xTicks = Array.from({ length: Math.floor(xHi / xStep + 1e-9) + 1 }, (_, i) => i * xStep);
  const yTicks = Array.from({ length: Math.round((yHi - yLo) / 0.05) + 1 }, (_, i) => yLo + i * 0.05);
  const maxO2 = tested.length ? Math.max(...tested.map((t) => t.o2)) : null;
  const hy = y(habitatO2);
  const above = maxO2 !== null && habitatO2 > maxO2;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={ariaLabel} data-testid="tested-dilution-chart">
      {yTicks.map((t) => (
        <g key={`y${t}`} aria-hidden="true">
          <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeDasharray="2 4" />
          <text x={M.l - 6} y={y(t) + 4} fontSize={11} textAnchor="end" fill="var(--muted)" className="num">
            {fmtPct(t)}
          </text>
        </g>
      ))}
      {xTicks.map((t) => (
        <text key={`x${t}`} x={x(t)} y={H - M.b + 16} fontSize={11} textAnchor="middle" fill="var(--muted)" className="num" aria-hidden="true">
          {fmtPct(t)}
        </text>
      ))}
      <text x={(M.l + W - M.r) / 2} y={H - 6} fontSize={11} textAnchor="middle" fill="var(--muted)" aria-hidden="true">
        {diluentName} in the test atmosphere (% of the gas)
      </text>
      <text transform={`translate(14 ${(M.t + H - M.b) / 2}) rotate(-90)`} fontSize={11} textAnchor="middle" fill="var(--muted)" aria-hidden="true">
        oxygen (%)
      </text>

      {maxO2 !== null ? (
        <g aria-hidden="true">
          <line x1={M.l} x2={W - M.r} y1={y(maxO2)} y2={y(maxO2)} stroke="var(--micro)" strokeDasharray="4 4" />
          <text x={W - M.r - 4} y={y(maxO2) + 14} fontSize={11} textAnchor="end" fill="var(--micro)" className="svg-halo">
            highest O₂ in any diluted test: {fmtPct(maxO2)}
          </text>
        </g>
      ) : null}

      <g aria-hidden="true">
        {tested.map((t, i) => (
          <circle key={i} cx={x(t.fraction)} cy={y(t.o2)} r={2.5 + Math.min(5, Math.sqrt(t.n))} fill="var(--micro-fill)" stroke="var(--micro)" strokeWidth={1.5}>
            <title>{`${t.n} FLEX test${t.n === 1 ? "" : "s"} at ${fmtPct(t.fraction)} ${diluentName}, ${fmtPct(t.o2)} O2`}</title>
          </circle>
        ))}
      </g>

      <g aria-hidden="true">
        <line x1={M.l} x2={W - M.r} y1={hy} y2={hy} stroke="var(--partial)" strokeWidth={2.5} />
        <text x={M.l + 6} y={hy - 6} fontSize={12} fontWeight={500} fill="var(--partial)" className="svg-halo">
          {habitatLabel}: {fmtPct(habitatO2)} O₂{above ? " (above every diluted test)" : ""}
        </text>
      </g>
      <line x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} stroke="var(--fg)" aria-hidden="true" />
      <line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} stroke="var(--fg)" aria-hidden="true" />
    </svg>
  );
}
