import { G0 } from "@/lib/physics";
import type { CatalogRecord } from "@/lib/types";

export const FUEL_STYLE: Record<string, { color: string; label: string; shape: "square" | "circle" | "triangle" | "diamond" | "ring" }> = {
  solid: { color: "var(--normal)", label: "solid", shape: "square" },
  liquid: { color: "var(--micro)", label: "liquid", shape: "circle" },
  gas: { color: "var(--partial)", label: "gas", shape: "triangle" },
  aerosol: { color: "var(--warn)", label: "aerosol", shape: "diamond" },
  unknown: { color: "var(--muted)", label: "unknown phase", shape: "ring" },
};

export function fuelStyle(phase: string | null | undefined) {
  return FUEL_STYLE[phase ?? "unknown"] ?? FUEL_STYLE.unknown;
}

export function Glyph({ x, y, phase, r = 5 }: { x: number; y: number; phase: string | null | undefined; r?: number }) {
  const s = fuelStyle(phase);
  switch (s.shape) {
    case "square":
      return <rect x={x - r} y={y - r} width={2 * r} height={2 * r} fill={s.color} />;
    case "triangle":
      return <path d={`M ${x} ${y - r - 1} L ${x + r + 1} ${y + r} L ${x - r - 1} ${y + r} Z`} fill={s.color} />;
    case "diamond":
      return <path d={`M ${x} ${y - r - 1} L ${x + r + 1} ${y} L ${x} ${y + r + 1} L ${x - r - 1} ${y} Z`} fill={s.color} />;
    case "ring":
      return <circle cx={x} cy={y} r={r - 1} fill="none" stroke={s.color} strokeWidth={2} />;
    default:
      return <circle cx={x} cy={y} r={r} fill={s.color} />;
  }
}

const W = 860;
const H = 300;
const M = { l: 70, r: 70 };
const AXIS_Y = 230;
const xOf = (frac: number) => M.l + frac * (W - M.l - M.r);

export function isEField(r: CatalogRecord) {
  return /E-FIELD/i.test(r.acronym ?? "") || r.id === "PSI-22";
}

/** F1 Gravity Spectrum Map. Each investigation dot links to its card. */
export function GravitySpectrum({
  records,
  currentG,
  queryString,
}: {
  records: CatalogRecord[];
  currentG: number;
  queryString: string;
}) {
  const combustion = records.filter((r) => r.is_combustion);
  const zeroG = combustion.filter((r) => r.gravity_levels?.includes("microgravity") && !isEField(r));
  const oneG = combustion.filter((r) => r.gravity_levels?.includes("normal_gravity") || r.ground_reference);
  const efield = combustion.filter(isEField);
  const moon = 1.62 / G0;
  const mars = 3.71 / G0;
  const cur = Math.min(1, Math.max(0, currentG / G0));
  const zoneL = xOf(0.04);
  const zoneR = xOf(0.96);

  // Stack in columns of 8 near each end so dots never overlap.
  const place = (i: number, side: 0 | 1) => {
    const col = Math.floor(i / 8);
    const row = i % 8;
    const x = side === 0 ? xOf(0) - 18 + col * 16 : xOf(1) + 18 - col * 16;
    return { x, y: AXIS_Y - 16 - row * 22 };
  };
  const href = (id: string) => `/investigations/${id}?${queryString}`;
  const dot = (r: CatalogRecord, x: number, y: number, note: string) => (
    <a key={`${r.id}-${note}`} href={href(r.id)} aria-label={`${r.id} ${r.acronym ?? ""} (${fuelStyle(r.fuel_phase).label}, ${note})`}>
      <title>{`${r.id} ${r.acronym ?? r.title ?? ""} · ${fuelStyle(r.fuel_phase).label} · ${note} · ${r.n_tests} tests`}</title>
      <circle cx={x} cy={y} r={9} fill="transparent" />
      <Glyph x={x} y={y} phase={r.fuel_phase} />
    </a>
  );

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full"
      role="group"
      aria-label={`Gravity spectrum from 0 g to 1 g: ${zeroG.length} microgravity investigations at 0 g, ${oneG.length} normal-gravity references at 1 g, E-FIELD as a buoyancy analog, and no direct data between them where the Moon (0.165 g) and Mars (0.38 g) sit. Your habitat is at ${cur.toFixed(3)} g.`}
    >
      <defs>
        <pattern id="spec-hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="8" stroke="var(--nodata)" strokeWidth="3" strokeOpacity="0.5" />
        </pattern>
      </defs>
      <rect x={zoneL} y={30} width={zoneR - zoneL} height={AXIS_Y - 30} fill="url(#spec-hatch)" />
      <text x={(zoneL + zoneR) / 2 + 120} y={60} fontSize={14} fill="var(--muted)" textAnchor="middle" fontWeight={600}>
        NO DIRECT FIRE DATA
      </text>
      {[
        { f: moon, label: "Moon 0.165 g" },
        { f: mars, label: "Mars 0.38 g" },
      ].map(({ f, label }) => (
        <g key={label}>
          <line x1={xOf(f)} x2={xOf(f)} y1={34} y2={AXIS_Y} stroke="var(--partial)" strokeWidth={2} />
          <text x={xOf(f)} y={26} fontSize={12} fill="var(--partial)" textAnchor="middle" fontWeight={600}>
            {label}
          </text>
        </g>
      ))}

      {zeroG.map((r, i) => {
        const p = place(i, 0);
        return dot(r, p.x, p.y, "0 g flight");
      })}
      {oneG.map((r, i) => {
        const p = place(i, 1);
        return dot(r, p.x, p.y, r.ground_reference ? "1 g ground columns" : "1 g ground study");
      })}
      {efield.map((r, i) => {
        const x = xOf(0.07) + i * 16;
        const y = AXIS_Y - 150;
        return (
          <g key={r.id}>
            <line x1={xOf(0)} x2={x} y1={AXIS_Y - 8} y2={y} stroke="var(--fg)" strokeDasharray="3 3" strokeOpacity={0.6} />
            <a href={href(r.id)} aria-label={`${r.id} ${r.acronym}: buoyancy analog (electric-field body force in microgravity)`}>
              <title>{`${r.id} ${r.acronym}: buoyancy analog. An electric field imposes a body force on the flame, mimicking buoyancy in 0 g.`}</title>
              <rect x={x - 8} y={y - 8} width={16} height={16} transform={`rotate(45 ${x} ${y})`} fill="var(--surface)" stroke="var(--fg)" strokeWidth={2} />
            </a>
            <text x={x + 14} y={y + 4} fontSize={11} fill="var(--fg)">
              E-FIELD: buoyancy analog
            </text>
          </g>
        );
      })}

      <line x1={xOf(0)} x2={xOf(1)} y1={AXIS_Y} y2={AXIS_Y} stroke="var(--fg)" strokeWidth={1.5} />
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line x1={xOf(t)} x2={xOf(t)} y1={AXIS_Y} y2={AXIS_Y + 6} stroke="var(--fg)" />
          <text x={xOf(t)} y={AXIS_Y + 20} fontSize={12} fill="var(--muted)" textAnchor="middle" className="num">
            {t} g
          </text>
        </g>
      ))}
      <text x={xOf(0) - 30} y={AXIS_Y + 40} fontSize={12} fill="var(--micro)">
        ISS / Cygnus (0 g)
      </text>
      <text x={xOf(1) + 30} y={AXIS_Y + 40} fontSize={12} fill="var(--normal)" textAnchor="end">
        Earth references (1 g)
      </text>
      <path d={`M ${xOf(cur)} ${AXIS_Y + 2} l -7 12 h 14 z`} fill="var(--fg)" />
      <text x={xOf(cur)} y={AXIS_Y + 58} fontSize={12} fill="var(--fg)" textAnchor="middle" fontWeight={600}>
        your habitat
      </text>
    </svg>
  );
}
