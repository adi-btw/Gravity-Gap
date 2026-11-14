import type { Coverage, CoverageStatus } from "@/lib/coverage";
import { PSIA_PER_ATM } from "@/lib/physics";

interface Props {
  cov: Coverage;
  status: CoverageStatus;
  habitatLabel: string;
}

const W = 640;
const H = 320;
const M = { l: 60, r: 16, t: 16, b: 46 };
const LOG_TICKS = [0.1, 0.25, 0.5, 1, 2, 4, 8];

function clamp(v: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, v));
}

/**
 * Tested-atmosphere map for one metric: every tested O2 x pressure condition (dot size = number of tests),
 * the zone where the engine is allowed to give a number (shaded), and the user's habitat (diamond) with a
 * dashed line to the nearest tested condition. This is what the Bounds Panel shows instead of inventing a
 * band when the habitat is outside the tested range.
 */
export function CoverageChart({ cov, status, habitatLabel }: Props) {
  const r = cov.rule;
  const reachO2 = r.type === "distance" ? r.max_distance * r.o2_scale : 0;
  const reachLnP = r.type === "distance" ? r.max_distance * r.ln_p_scale : 0;

  const o2s = [...cov.points.map((p) => p.o2), status.o2];
  const ps = [...cov.points.map((p) => p.p_atm), status.p_atm];
  if (r.type === "box") {
    o2s.push(...r.o2);
    ps.push(...r.pressure_atm);
  }
  const xLo = clamp(Math.min(...o2s) - reachO2 - 0.04, 0, 1);
  const xHi = clamp(Math.max(...o2s) + reachO2 + 0.04, 0, 1);
  const yLo = clamp((Math.min(...ps) * Math.exp(-reachLnP)) / 1.3, 0.05, 20);
  const yHi = clamp(Math.max(...ps) * Math.exp(reachLnP) * 1.3, 0.05, 20);

  const x = (o2: number) => M.l + ((o2 - xLo) / (xHi - xLo || 1)) * (W - M.l - M.r);
  const y = (p: number) =>
    M.t + (1 - (Math.log(p) - Math.log(yLo)) / (Math.log(yHi) - Math.log(yLo) || 1)) * (H - M.t - M.b);

  const xTicks = Array.from({ length: 5 }, (_, i) => xLo + ((xHi - xLo) * i) / 4);
  const yTicks = LOG_TICKS.filter((t) => t >= yLo && t <= yHi);
  const hx = x(status.o2);
  const hy = y(status.p_atm);
  const near = status.nearest;
  const lineColor = status.covered ? "var(--micro)" : "var(--warn)";
  const flip = hx > W - 200;
  // Labels go below the diamond (clear of the tested points, which sit at higher pressure) unless that runs off the plot.
  const below = hy + 44 < H - M.b;
  const labelY = below ? hy + 26 : hy - 28;
  const distY = below ? hy + 40 : hy - 14;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full"
      role="img"
      aria-label={`Tested atmospheres for ${cov.metric}: ${cov.points.length} tested O2 and pressure conditions (${cov.n_points} tests). ${habitatLabel} at ${(status.o2 * 100).toFixed(1)}% O2 and ${status.p_atm.toFixed(2)} atm is ${status.covered ? "inside" : "outside"} the covered zone${status.nearestDistance !== null ? `, distance ${status.nearestDistance.toFixed(2)} from the nearest test` : ""}.`}
      data-testid="coverage-chart"
    >
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
      <text
        transform={`translate(14 ${(M.t + H - M.b) / 2}) rotate(-90)`}
        fontSize={11}
        textAnchor="middle"
        fill="var(--muted)"
        aria-hidden="true"
      >
        cabin pressure (psia, log scale)
      </text>

      <g aria-hidden="true" opacity={0.22} fill="var(--micro)">
        {r.type === "distance" ? (
          cov.points.map((p, i) => {
            const cx = x(p.o2);
            const cy = y(p.p_atm);
            const rx = Math.abs(x(p.o2 + reachO2) - cx);
            const ry = Math.abs(y(p.p_atm * Math.exp(reachLnP)) - cy);
            return <ellipse key={i} cx={cx} cy={cy} rx={rx} ry={ry} />;
          })
        ) : (
          <rect
            x={x(r.o2[0])}
            y={y(r.pressure_atm[1])}
            width={Math.max(2, x(r.o2[1]) - x(r.o2[0]))}
            height={Math.max(2, y(r.pressure_atm[0]) - y(r.pressure_atm[1]))}
          />
        )}
      </g>

      <g aria-hidden="true">
        {cov.points.map((p, i) => (
          <circle
            key={i}
            cx={x(p.o2)}
            cy={y(p.p_atm)}
            r={2.5 + Math.min(6, Math.sqrt(p.n))}
            fill={p.assumed ? "none" : "var(--micro)"}
            stroke="var(--micro)"
            strokeWidth={1.5}
            strokeDasharray={p.assumed ? "2 2" : undefined}
          >
            <title>{`${p.investigation_id}: ${p.n} test${p.n === 1 ? "" : "s"} at ${(p.o2 * 100).toFixed(1)}% O2, ${p.p_atm.toFixed(2)} atm${p.assumed ? ` (${p.assumed})` : ""}`}</title>
          </circle>
        ))}
      </g>

      {near ? (
        <line
          x1={hx}
          y1={hy}
          x2={x(near.o2)}
          y2={y(near.p_atm)}
          stroke={lineColor}
          strokeWidth={1.5}
          strokeDasharray="5 4"
          aria-hidden="true"
        />
      ) : null}
      <g aria-hidden="true">
        <path
          d={`M ${hx} ${hy - 9} L ${hx + 9} ${hy} L ${hx} ${hy + 9} L ${hx - 9} ${hy} Z`}
          fill="var(--partial)"
          stroke="var(--fg)"
          strokeWidth={1.5}
        />
        <text
          x={hx + (flip ? 4 : -4)}
          y={labelY}
          fontSize={12}
          fontWeight={600}
          textAnchor={flip ? "end" : "start"}
          fill="var(--partial)"
          className="svg-halo"
        >
          {habitatLabel}: {status.covered ? "covered" : "no evidence"}
        </text>
        {status.nearestDistance !== null && r.type === "distance" ? (
          <text
            x={hx + (flip ? 4 : -4)}
            y={distY}
            fontSize={11}
            textAnchor={flip ? "end" : "start"}
            fill={lineColor}
            className="num svg-halo"
          >
            distance {status.nearestDistance.toFixed(2)} (limit {r.max_distance})
          </text>
        ) : null}
      </g>
      <line x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} stroke="var(--fg)" aria-hidden="true" />
      <line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} stroke="var(--fg)" aria-hidden="true" />
    </svg>
  );
}
