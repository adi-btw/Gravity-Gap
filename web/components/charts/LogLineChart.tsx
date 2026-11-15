import { fmtShare, fmtTickNm, logDomain, logScale, logTicks } from "@/lib/detection";

export interface LogLineSeries {
  id: string;
  label: string;
  x: number[];
  y: number[];
  color: string;
  /** SVG stroke-dasharray; lines differ by dash as well as colour. */
  dash?: string;
  marker?: "circle" | "square" | "none";
}

interface Props {
  series: LogLineSeries[];
  xLabel: string;
  yLabel: string;
  ariaLabel: string;
  testId: string;
  /** Optional fixed x domain so toggling series does not move the axis. */
  xDomain?: [number, number];
}

const W = 640;
const H = 280;
const M = { l: 56, r: 30, t: 16, b: 44 };

function niceMax(v: number): number {
  if (!(v > 0)) return 0.1;
  const step = v > 0.2 ? 0.1 : v > 0.1 ? 0.05 : 0.02;
  return Math.ceil((v * 1.05) / step) * step;
}

/** Share-per-size-class line chart on a log diameter axis (nm). Each series has one size definition (caller). */
export function LogLineChart({ series, xLabel, yLabel, ariaLabel, testId, xDomain }: Props) {
  const dom = xDomain ?? logDomain(series.flatMap((s) => s.x));
  const x = logScale(dom, [M.l, W - M.r]);
  const yMax = niceMax(Math.max(0, ...series.flatMap((s) => s.y)));
  const y = (v: number) => M.t + (1 - v / yMax) * (H - M.t - M.b);
  const yStep = yMax > 0.3 ? 0.1 : yMax > 0.12 ? 0.05 : 0.02;
  const yTicks = Array.from({ length: Math.floor(yMax / yStep + 1e-9) + 1 }, (_, i) => i * yStep);
  const xTicks = logTicks(dom);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={ariaLabel} data-testid={testId}>
      {yTicks.map((t) => (
        <g key={`y${t}`} aria-hidden="true">
          <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeDasharray="2 4" />
          <text x={M.l - 6} y={y(t) + 4} fontSize={11} textAnchor="end" fill="var(--muted)" className="num">
            {fmtShare(t)}
          </text>
        </g>
      ))}
      {xTicks.map((t) => (
        <g key={`x${t}`} aria-hidden="true">
          <line x1={x(t)} x2={x(t)} y1={M.t} y2={H - M.b} stroke="var(--line)" strokeDasharray="2 4" />
          <text x={x(t)} y={H - M.b + 16} fontSize={11} textAnchor="middle" fill="var(--muted)" className="num">
            {fmtTickNm(t)}
          </text>
        </g>
      ))}
      <text x={(M.l + W - M.r) / 2} y={H - 6} fontSize={11} textAnchor="middle" fill="var(--muted)" aria-hidden="true">
        {xLabel}
      </text>
      <text transform={`translate(14 ${(M.t + H - M.b) / 2}) rotate(-90)`} fontSize={11} textAnchor="middle" fill="var(--muted)" aria-hidden="true">
        {yLabel}
      </text>

      {series.map((s) => {
        const pts = s.x.map((xv, i) => `${x(xv).toFixed(1)},${y(s.y[i]).toFixed(1)}`).join(" ");
        return (
          <g key={s.id} data-series={s.id} aria-hidden="true">
            <polyline points={pts} fill="none" stroke={s.color} strokeWidth={2} strokeDasharray={s.dash} strokeLinejoin="round" />
            {s.marker === "none"
              ? null
              : s.x.map((xv, i) =>
                  s.marker === "square" ? (
                    <rect key={i} x={x(xv) - 2.5} y={y(s.y[i]) - 2.5} width={5} height={5} fill={s.color} />
                  ) : (
                    <circle key={i} cx={x(xv)} cy={y(s.y[i])} r={2.5} fill={s.color} />
                  ),
                )}
          </g>
        );
      })}
      <line x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} stroke="var(--fg)" aria-hidden="true" />
      <line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} stroke="var(--fg)" aria-hidden="true" />
    </svg>
  );
}

/** Legend for LogLineChart: a line swatch with the same colour and dash, plus the full series label. */
export function LogLineLegend({ series }: { series: LogLineSeries[] }) {
  return (
    <ul className="mt-2 space-y-1 text-xs">
      {series.map((s) => (
        <li key={s.id} className="flex items-start gap-2">
          <svg width="28" height="10" viewBox="0 0 28 10" aria-hidden="true" className="mt-1 shrink-0">
            <line x1="0" x2="28" y1="5" y2="5" stroke={s.color} strokeWidth="2" strokeDasharray={s.dash} />
            {s.marker === "square" ? <rect x="11.5" y="2.5" width="5" height="5" fill={s.color} /> : null}
            {s.marker === "circle" || s.marker === undefined ? <circle cx="14" cy="5" r="2.5" fill={s.color} /> : null}
          </svg>
          <span data-series-label>{s.label}</span>
        </li>
      ))}
    </ul>
  );
}
