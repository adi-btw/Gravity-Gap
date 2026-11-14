/**
 * R1 real-fire replay helpers: turn an incident record into a habitat and a shareable URL. Values are passed
 * through unchanged (no rounding, no clamping beyond the habitat field limits), so Apollo 1's 16.7 psia and
 * 100% O₂ reach the engine exactly as sourced.
 */
import { DEFAULT_HABITAT, clampField, habitatToQuery, type Habitat, type HabitatKey } from "./habitat";
import type { Incident } from "./types";

const EPS = 1e-9;
const KEYS: HabitatKey[] = ["g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm"];

function isNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

/** Habitat for an in-scope incident; null when it is out of scope or lacks gravity/pressure/O₂. */
export function incidentHabitat(inc: Incident): Habitat | null {
  if (!inc.in_scope || !isNum(inc.g_m_s2) || !isNum(inc.p_psia) || !isNum(inc.o2)) return null;
  const h = { ...DEFAULT_HABITAT };
  for (const k of KEYS) {
    const v = inc[k];
    if (isNum(v)) h[k] = clampField(k, v);
  }
  return h;
}

/** `/path?g=&p=&o2=&u=&L=` for an incident, or null when it cannot be loaded. */
export function incidentHref(inc: Incident, path = "/bounds"): string | null {
  const h = incidentHabitat(inc);
  return h ? `${path}?${habitatToQuery(h).toString()}` : null;
}

/** In-scope incident whose five habitat values match exactly (for the History chips). */
export function matchIncident(h: Habitat, incidents: readonly Incident[]): Incident | null {
  return (
    incidents.find((inc) => {
      const ih = incidentHabitat(inc);
      return ih !== null && KEYS.every((k) => Math.abs(ih[k] - h[k]) < EPS);
    }) ?? null
  );
}

/** Year from an ISO date ("1967-01-27" -> "1967"); passes other strings through. */
export function incidentYear(date: string): string {
  const m = /^(\d{4})/.exec(date ?? "");
  return m ? m[1] : date;
}
