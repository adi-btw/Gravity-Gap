import { G0 } from "@/lib/physics";

const W = 760;
const H = 190;
const M = { l: 40, r: 40 };
const AXIS_Y = 120;
const xOf = (frac: number) => M.l + frac * (W - M.l - M.r);

/** "The gap": evidence exists at 0 g and 1 g; Moon and Mars sit in between with no direct data. */
export function GapHero({ currentG }: { currentG?: number }) {
  const moon = 1.62 / G0;
  const mars = 3.71 / G0;
  const zoneL = xOf(0.025);
  const zoneR = xOf(0.975);
  const cur = currentG === undefined ? null : Math.min(1, Math.max(0, currentG / G0));
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full"
      role="img"
      aria-label="Gravity axis from 0 g to 1 g. Hundreds of fire tests exist at 0 g on the ISS and Cygnus and at 1 g on Earth. Between them, including the Moon at 0.165 g and Mars at 0.38 g, there is no direct fire data."
    >
      <defs>
        <pattern id="hero-hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="8" stroke="var(--nodata)" strokeWidth="3" strokeOpacity="0.55" />
        </pattern>
      </defs>
      <rect x={zoneL} y={36} width={zoneR - zoneL} height={AXIS_Y - 36} fill="url(#hero-hatch)" />
      <text x={(zoneL + zoneR) / 2 + 90} y={58} fontSize={14} fill="var(--muted)" textAnchor="middle" fontWeight={500} className="svg-halo">
        No direct fire data
      </text>

      {/* 0 g evidence cluster */}
      {Array.from({ length: 14 }, (_, i) => (
        <circle key={`m${i}`} cx={xOf(0) + ((i * 7) % 11) - 5} cy={AXIS_Y - 12 - ((i * 13) % 60)} r={3.5} fill="var(--micro)" />
      ))}
      {/* 1 g evidence cluster */}
      {Array.from({ length: 14 }, (_, i) => (
        <circle key={`n${i}`} cx={xOf(1) + ((i * 5) % 11) - 5} cy={AXIS_Y - 12 - ((i * 17) % 60)} r={3.5} fill="var(--normal)" />
      ))}

      {[
        { f: moon, label: "Moon 0.165 g" },
        { f: mars, label: "Mars 0.38 g" },
      ].map(({ f, label }) => (
        <g key={label}>
          <line x1={xOf(f)} x2={xOf(f)} y1={30} y2={AXIS_Y} stroke="var(--partial)" strokeWidth={2.5} />
          <text x={xOf(f)} y={24} fontSize={13} fill="var(--partial)" textAnchor="middle" fontWeight={500}>
            {label}
          </text>
        </g>
      ))}

      <line x1={xOf(0)} x2={xOf(1)} y1={AXIS_Y} y2={AXIS_Y} stroke="var(--fg)" strokeWidth={1.5} />
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line x1={xOf(t)} x2={xOf(t)} y1={AXIS_Y} y2={AXIS_Y + 6} stroke="var(--fg)" />
          <text x={xOf(t)} y={AXIS_Y + 20} fontSize={12} fill="var(--muted)" textAnchor="middle" className="num">
            {t} g
          </text>
        </g>
      ))}
      <text x={xOf(0)} y={AXIS_Y + 40} fontSize={12} fill="var(--micro)" textAnchor="start">
        ISS / Cygnus tests (0 g)
      </text>
      <text x={xOf(1)} y={AXIS_Y + 40} fontSize={12} fill="var(--normal)" textAnchor="end">
        Earth labs (1 g)
      </text>
      {cur !== null ? (
        <g>
          <path d={`M ${xOf(cur)} ${AXIS_Y + 2} l -7 12 h 14 z`} fill="var(--fg)" />
          <text x={xOf(cur)} y={AXIS_Y + 58} fontSize={12} fill="var(--fg)" textAnchor="middle" fontWeight={500}>
            your habitat
          </text>
        </g>
      ) : null}
    </svg>
  );
}
