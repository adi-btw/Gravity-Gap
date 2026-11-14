import { atmosphereDistance, PSIA_PER_ATM } from "./physics";

/** One tested O2 x pressure condition (aggregated) for a metric. Mirrors engine/coverage.py. */
export interface CoveragePoint {
  o2: number;
  p_atm: number;
  investigation_id: string;
  n: number;
  /** Non-null when the PSI table lacked this value and the engine assumed it (SAFFIRE pressure, SPICE air). */
  assumed: string | null;
}

export type CoverageRule =
  | { type: "distance"; max_distance: number; o2_scale: number; ln_p_scale: number; text: string }
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
  covered: boolean;
  nearestDistance: number | null;
  nearest: CoveragePoint | null;
}

/** Same rule as engine/coverage.py habitat_status: distance <= max for fitted models, inside the box for rules. */
export function coverageStatus(cov: Coverage, o2: number, p_psia: number): CoverageStatus {
  const p_atm = p_psia / PSIA_PER_ATM;
  let nearest: CoveragePoint | null = null;
  let best = Infinity;
  for (const p of cov.points) {
    const d = atmosphereDistance(o2, p_atm, p.o2, p.p_atm);
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
  return { o2, p_atm, covered, nearestDistance: nearest ? best : null, nearest };
}

export function normalizeCoverage(raw: unknown): Coverage {
  const c = raw as Coverage;
  if (!c || !Array.isArray(c.points) || !c.rule) throw new Error("malformed coverage payload");
  return c;
}
