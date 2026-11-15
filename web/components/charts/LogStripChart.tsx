import { fmtNm, fmtTickNm, jitter, logDomain, logScale, logTicks } from "@/lib/detection";

export type StripShape = "circle" | "diamond" | "square";

export interface StripKind {
  label: string;
  color: string;
  shape: StripShape;
  /** Hollow markers keep kinds apart without colour (e.g. aged = hollow diamond). */
  hollow?: boolean;
}

export interface StripRow {
  key: string;
  label: string;
  /** Second line under the row label (e.g. the density assumption next to the dust). */
  note?: string;
  points: { value: number; kind: string; title: string }[];
}

interface Props {
  rows: StripRow[];
  kinds: Record<string, StripKind>;
  xLabel: string;
  ariaLabel: string;
  testId: string;
  rowHeight?: number;
}

const W = 640;
const M = { l: 178, r: 24, t: 12, b: 44 };

function Marker({ cx, cy, k, title }: { cx: number; cy: number; k: StripKind; title: string }) {
  const fill = k.hollow ? "none" : k.color;
  const common = { fill, stroke: k.color, strokeWidth: 1.5, fillOpacity: k.hollow ? undefined : 0.75 };
  const t = title ? <title>{title}</title> : null;
  if (k.shape === "square") return <rect x={cx - 4} y={cy - 4} width={8} height={8} {...common}>{t}</rect>;
  if (k.shape === "diamond")
    return <path d={`M${cx} ${cy - 5}L${cx + 5} ${cy}L${cx} ${cy + 5}L${cx - 5} ${cy}Z`} {...common}>{t}</path>;
  return <circle cx={cx} cy={cy} r={4} {...common}>{t}</circle>;
}

/** Dots on a log diameter axis (nm), one row per group. Every row shares one size definition (caller). */
export function LogStripChart({ rows, kinds, xLabel, ariaLabel, testId, rowHeight = 40 }: Props) {
  const H = M.t + M.b + rows.length * rowHeight;
  const dom = logDomain(rows.flatMap((r) => r.points.map((p) => p.value)));
  const x = logScale(dom, [M.l, W - M.r]);
  const xTicks = logTicks(dom);
  const kindKeys = Object.keys(kinds);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={ariaLabel} data-testid={testId}>
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
      {rows.map((r, ri) => {
        const top = M.t + ri * rowHeight;
        const mid = top + rowHeight / 2;
        // Each kind gets its own lane inside the row, so aged/unaged (or smoke/dust) never overlap.
        const lanes = Array.from(new Set(r.points.map((p) => p.kind))).sort((a, b) => kindKeys.indexOf(a) - kindKeys.indexOf(b));
        const laneH = (rowHeight - 8) / Math.max(1, lanes.length);
        return (
          <g key={r.key} data-row={r.key} aria-hidden="true">
            {ri > 0 ? <line x1={M.l} x2={W - M.r} y1={top} y2={top} stroke="var(--line)" /> : null}
            <text x={M.l - 8} y={r.note ? mid - 2 : mid + 4} fontSize={12} textAnchor="end" fill="var(--fg)" data-series-label>
              {r.label}
            </text>
            {r.note ? (
              <text x={M.l - 8} y={mid + 12} fontSize={10} textAnchor="end" fill="var(--muted)">
                {r.note}
              </text>
            ) : null}
            {r.points.map((p, i) => {
              const lane = lanes.indexOf(p.kind);
              const cy = top + 4 + laneH * (lane + 0.5) + jitter(i) * Math.max(0, laneH / 2 - 5);
              return <Marker key={i} cx={x(p.value)} cy={cy} k={kinds[p.kind]} title={p.title || fmtNm(p.value)} />;
            })}
          </g>
        );
      })}
      <line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} stroke="var(--fg)" aria-hidden="true" />
      <line x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} stroke="var(--fg)" aria-hidden="true" />
    </svg>
  );
}

export function StripLegend({ kinds }: { kinds: Record<string, StripKind> }) {
  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
      {Object.entries(kinds).map(([key, k]) => (
        <li key={key} className="flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="-6 -6 12 12" aria-hidden="true">
            <Marker cx={0} cy={0} k={k} title="" />
          </svg>
          <span data-series-label>{k.label}</span>
        </li>
      ))}
    </ul>
  );
}
