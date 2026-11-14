import { fmtSig } from "@/lib/format";

export interface BandPoint {
  key: string;
  label: string;
  sublabel?: string;
  estimate: number | null;
  band: [number, number] | null;
  color: string;
  fill: string;
  /** Text shown on hover/focus (e.g. evidence trace). */
  trace?: string;
}

interface Props {
  points: BandPoint[];
  unit: string | null;
  /** Fixed y domain, e.g. [0, 1] for probabilities. */
  domain?: [number, number];
  ariaLabel: string;
}

const W = 640;
const H = 280;
const M = { l: 56, r: 16, t: 16, b: 52 };

function niceDomain(vals: number[]): [number, number] {
  if (!vals.length) return [0, 1];
  let lo = Math.min(...vals);
  let hi = Math.max(...vals);
  if (lo === hi) {
    lo -= Math.abs(lo) * 0.2 || 1;
    hi += Math.abs(hi) * 0.2 || 1;
  }
  const pad = (hi - lo) * 0.12;
  lo = lo >= 0 && lo - pad < 0 ? 0 : lo - pad;
  return [lo, hi + pad];
}

function ticks([lo, hi]: [number, number], n = 5): number[] {
  const step = (hi - lo) / (n - 1);
  return Array.from({ length: n }, (_, i) => lo + i * step);
}

/**
 * Shared-value-axis chart: one column per reference (0 g, your habitat, 1 g). Each column draws its 90% band
 * as a filled bar and the estimate as a tick, so uncertainty is always visible as a band.
 */
export function BandChart({ points, unit, domain, ariaLabel }: Props) {
  const vals = points.flatMap((p) => [p.estimate, ...(p.band ?? [])]).filter((v): v is number => v !== null && Number.isFinite(v));
  const [lo, hi] = domain ?? niceDomain(vals);
  const y = (v: number) => M.t + (1 - (v - lo) / (hi - lo || 1)) * (H - M.t - M.b);
  const colW = (W - M.l - M.r) / Math.max(1, points.length);
  const cx = (i: number) => M.l + colW * (i + 0.5);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="group" aria-label={ariaLabel}>
      {ticks([lo, hi]).map((t) => (
        <g key={t} aria-hidden="true">
          <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeDasharray="2 4" />
          <text x={M.l - 6} y={y(t) + 4} fontSize={11} textAnchor="end" fill="var(--muted)" className="num">
            {fmtSig(t, 3)}
          </text>
        </g>
      ))}
      <text
        transform={`translate(14 ${(M.t + H - M.b) / 2}) rotate(-90)`}
        fontSize={11}
        textAnchor="middle"
        fill="var(--muted)"
        aria-hidden="true"
      >
        {unit ?? "value"}
      </text>
      {points.map((p, i) => {
        const x = cx(i);
        const bw = Math.min(64, colW * 0.4);
        const has = p.estimate !== null || p.band !== null;
        return (
          <g key={p.key} tabIndex={0} role="img" aria-label={p.trace ?? p.label} className="focus:outline-none">
            <title>{p.trace ?? p.label}</title>
            <rect
              className="svg-focus-ring"
              x={x - colW / 2 + 4}
              y={M.t - 6}
              width={colW - 8}
              height={H - M.t}
              fill="none"
              stroke="var(--micro)"
              strokeWidth={2}
              rx={6}
            />
            {p.band ? (
              <rect
                x={x - bw / 2}
                y={y(Math.max(p.band[0], p.band[1]))}
                width={bw}
                height={Math.max(2, Math.abs(y(p.band[0]) - y(p.band[1])))}
                fill={p.fill}
                stroke={p.color}
                strokeWidth={1.5}
                rx={3}
              />
            ) : null}
            {p.estimate !== null ? (
              <line x1={x - bw / 2 - 6} x2={x + bw / 2 + 6} y1={y(p.estimate)} y2={y(p.estimate)} stroke={p.color} strokeWidth={3} />
            ) : null}
            {!has ? (
              <text x={x} y={(M.t + H - M.b) / 2} fontSize={11} textAnchor="middle" fill="var(--muted)">
                no basis
              </text>
            ) : null}
            <text x={x} y={H - M.b + 18} fontSize={12} textAnchor="middle" fill={p.color} fontWeight={600}>
              {p.label}
            </text>
            {p.sublabel ? (
              <text x={x} y={H - M.b + 34} fontSize={11} textAnchor="middle" fill="var(--muted)" className="num">
                {p.sublabel}
              </text>
            ) : null}
          </g>
        );
      })}
      <line x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} stroke="var(--fg)" />
    </svg>
  );
}
