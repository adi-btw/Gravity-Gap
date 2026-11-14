import { atmosphereDistance, PSIA_PER_ATM } from "./physics";

/** One tested O2 x pressure condition (aggregated) for a metric. Mirrors engine/coverage.py. */
export interface CoveragePoint {
  o2: number;
  p_atm: number;
  investigation_id: string;
  n: number;
  /** M1/M2 only (ADR-0006): diluent mole fractions of the tested condition. */
  co2?: number;
  he?: number;
  /** Non-null when the PSI table lacked this value and the engine assumed it (SAFFIRE pressure, SPICE air). */
  assumed: string | null;
}

export type CoverageRule =
  | {
      type: "distance";
      max_distance: number;
      o2_scale: number;
      ln_p_scale: number;
      /** Present for diluent-aware metrics (M1/M2, ADR-0006). */
      co2_scale?: number;
      he_scale?: number;
      text: string;
    }
  | { type: "box"; o2: [number, number]; pressure_atm: [number, number]; text: string };

export interface Coverage {
  metric: string;
  points: CoveragePoint[];
  rule: CoverageRule;
  note: string;
  n_points: number;
}

export interface CoverageStatus {
  o2: number;
  p_atm: number;
  co2: number;
  he: number;
  covered: boolean;
  nearestDistance: number | null;
  nearest: CoveragePoint | null;
}

/** engine/bounds.py dilution_distance (ADR-0006): 4-D distance in (O2, ln p, CO2, He). */
export function dilutionDistance(
  o2: number,
  p_atm: number,
  co2: number,
  he: number,
  t: { o2: number; p_atm: number; co2?: number; he?: number },
  scales: { o2: number; ln_p: number; co2: number; he: number } = { o2: 0.05, ln_p: 0.3, co2: 0.1, he: 0.1 },
): number {
  const dx = (o2 - t.o2) / scales.o2;
  const dp = (Math.log(p_atm) - Math.log(t.p_atm)) / scales.ln_p;
  const dc = (co2 - (t.co2 ?? 0)) / scales.co2;
  const dh = (he - (t.he ?? 0)) / scales.he;
  return Math.sqrt(dx * dx + dp * dp + dc * dc + dh * dh);
}

/**
 * Same rule as engine/coverage.py habitat_status: distance <= max for fitted models, inside the box for rules.
 * For M1/M2 (rule carries co2_scale) the distance is 4-D and a diluted query (co2 > 0 or he > 0) is compared only
 * with tests that used that diluent (ADR-0006 diluent evidence rule); other metrics ignore co2/he.
 */
export function coverageStatus(cov: Coverage, o2: number, p_psia: number, co2 = 0, he = 0): CoverageStatus {
  const p_atm = p_psia / PSIA_PER_ATM;
  const r0 = cov.rule;
  const dil = r0.type === "distance" && r0.co2_scale !== undefined;
  const scales =
    r0.type === "distance"
      ? { o2: r0.o2_scale, ln_p: r0.ln_p_scale, co2: r0.co2_scale ?? 0.1, he: r0.he_scale ?? r0.co2_scale ?? 0.1 }
      : undefined;
  let nearest: CoveragePoint | null = null;
  let best = Infinity;
  for (const p of cov.points) {
    if (dil && ((co2 > 0 && (p.co2 ?? 0) <= 0) || (he > 0 && (p.he ?? 0) <= 0))) continue;
    const d = dil ? dilutionDistance(o2, p_atm, co2, he, p, scales) : atmosphereDistance(o2, p_atm, p.o2, p.p_atm);
    if (d < best) {
      best = d;
      nearest = p;
    }
  }
  const r = cov.rule;
  const covered =
    r.type === "distance"
      ? nearest !== null && best <= r.max_distance
      : o2 >= r.o2[0] && o2 <= r.o2[1] && p_atm >= r.pressure_atm[0] && p_atm <= r.pressure_atm[1];
  return { o2, p_atm, co2: dil ? co2 : 0, he: dil ? he : 0, covered, nearestDistance: nearest ? best : null, nearest };
}

export function normalizeCoverage(raw: unknown): Coverage {
  const c = raw as Coverage;
  if (!c || !Array.isArray(c.points) || !c.rule) throw new Error("malformed coverage payload");
  return c;
}
