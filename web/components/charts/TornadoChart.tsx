import { fmtSig } from "@/lib/format";

export interface TornadoRow {
  param: string;
  low: number;
  high: number;
}

/** Sensitivity tornado: metric at each parameter's low and high setting, bars sorted by swing, base line marked. */
export function TornadoChart({ rows, base, unit, ariaLabel }: { rows: TornadoRow[]; base: number | null; unit: string | null; ariaLabel: string }) {
  const sorted = [...rows].sort((a, b) => Math.abs(b.high - b.low) - Math.abs(a.high - a.low));
  const vals = sorted.flatMap((r) => [r.low, r.high]).concat(base !== null ? [base] : []);
  let lo = Math.min(...vals);
  let hi = Math.max(...vals);
  if (lo === hi) {
    lo -= 1;
    hi += 1;
  }
  const W = 640;
  const rowH = 26;
  const M = { l: 130, r: 20, t: 10, b: 30 };
  const H = M.t + M.b + rowH * sorted.length;
  const x = (v: number) => M.l + ((v - lo) / (hi - lo)) * (W - M.l - M.r);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={ariaLabel}>
      {sorted.map((r, i) => {
        const yy = M.t + i * rowH;
        const a = Math.min(r.low, r.high);
        const b = Math.max(r.low, r.high);
        return (
          <g key={r.param}>
            <title>{`${r.param}: low ${fmtSig(r.low)} · high ${fmtSig(r.high)}`}</title>
            <text x={M.l - 8} y={yy + rowH / 2 + 4} fontSize={12} textAnchor="end" fill="var(--fg)" className="num">
              {r.param}
            </text>
            <rect x={x(a)} y={yy + 5} width={Math.max(2, x(b) - x(a))} height={rowH - 10} fill="var(--partial-fill)" stroke="var(--partial)" rx={2} />
            <text x={x(r.low)} y={yy + rowH / 2 + 4} fontSize={10} textAnchor={r.low <= r.high ? "end" : "start"} dx={r.low <= r.high ? -3 : 3} fill="var(--muted)" className="num">
              lo
            </text>
            <text x={x(r.high)} y={yy + rowH / 2 + 4} fontSize={10} textAnchor={r.high >= r.low ? "start" : "end"} dx={r.high >= r.low ? 3 : -3} fill="var(--muted)" className="num">
              hi
            </text>
          </g>
        );
      })}
      {base !== null ? (
        <line x1={x(base)} x2={x(base)} y1={M.t} y2={H - M.b} stroke="var(--fg)" strokeDasharray="4 3" />
      ) : null}
      <line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} stroke="var(--line)" />
      {[lo, (lo + hi) / 2, hi].map((t) => (
        <text key={t} x={x(t)} y={H - M.b + 16} fontSize={11} textAnchor="middle" fill="var(--muted)" className="num">
          {fmtSig(t, 3)}
          {unit && t === hi ? ` ${unit}` : ""}
        </text>
      ))}
    </svg>
  );
}
