import { G0 } from "./physics";
import { DEFAULT_PRESET_ID, PRESETS, PRESETS_BY_ID, type Preset } from "./presets";

/** One shared habitat state (F0). Units follow plan/contracts.md. */
export interface Habitat {
  g_m_s2: number;
  p_psia: number;
  o2: number;
  u_cm_s: number;
  L_mm: number;
}

export type HabitatKey = keyof Habitat;

/** URL query key for each field: ?g=&p=&o2=&u=&L= (g in m/s², o2 as mole fraction). */
export const QUERY_KEYS: Record<HabitatKey, string> = {
  g_m_s2: "g",
  p_psia: "p",
  o2: "o2",
  u_cm_s: "u",
  L_mm: "L",
};

export interface FieldSpec {
  key: HabitatKey;
  label: string;
  unit: string;
  min: number;
  max: number;
  step: number;
  decimals: number;
}

/** Slider/input ranges follow plan/03 §1 (typical ranges), widened slightly for exploration. */
export const FIELDS: Record<HabitatKey, FieldSpec> = {
  g_m_s2: { key: "g_m_s2", label: "Gravity", unit: "m/s²", min: 0, max: 9.81, step: 0.01, decimals: 2 },
  p_psia: { key: "p_psia", label: "Cabin pressure", unit: "psia", min: 4, max: 20, step: 0.1, decimals: 1 },
  o2: { key: "o2", label: "O₂", unit: "%", min: 0.15, max: 1, step: 0.005, decimals: 3 },
  u_cm_s: { key: "u_cm_s", label: "Vent speed", unit: "cm/s", min: 0, max: 40, step: 0.5, decimals: 1 },
  L_mm: { key: "L_mm", label: "Flame size", unit: "mm", min: 1, max: 100, step: 1, decimals: 0 },
};

export function presetToHabitat(p: Preset): Habitat {
  return { g_m_s2: p.g_m_s2, p_psia: p.p_psia, o2: p.o2, u_cm_s: p.u_cm_s, L_mm: p.L_mm };
}

export const DEFAULT_HABITAT: Habitat = presetToHabitat(PRESETS_BY_ID[DEFAULT_PRESET_ID]);

export function clampField(key: HabitatKey, value: number): number {
  const f = FIELDS[key];
  if (!Number.isFinite(value)) return DEFAULT_HABITAT[key];
  return Math.min(f.max, Math.max(f.min, value));
}

interface QueryLike {
  get(name: string): string | null;
}

/** Parse ?g=&p=&o2=&u=&L=; missing or invalid values fall back to the default preset. */
export function habitatFromQuery(q: QueryLike | null | undefined): Habitat {
  const out = { ...DEFAULT_HABITAT };
  if (!q) return out;
  (Object.keys(QUERY_KEYS) as HabitatKey[]).forEach((key) => {
    const raw = q.get(QUERY_KEYS[key]);
    if (raw === null || raw.trim() === "") return;
    const n = Number(raw);
    if (Number.isFinite(n)) out[key] = clampField(key, n);
  });
  return out;
}

function fmtQuery(n: number): string {
  // Trim float noise without losing preset precision (e.g. 0.265, 1.62).
  return String(Number(n.toFixed(4)));
}

export function habitatToQuery(h: Habitat, base?: URLSearchParams): URLSearchParams {
  const q = new URLSearchParams(base);
  (Object.keys(QUERY_KEYS) as HabitatKey[]).forEach((key) => {
    q.set(QUERY_KEYS[key], fmtQuery(h[key]));
  });
  return q;
}

const EPS = 1e-9;

/** Preset whose five values match exactly, else null ("Custom"). */
export function matchPreset(h: Habitat): Preset | null {
  return (
    PRESETS.find(
      (p) =>
        Math.abs(p.g_m_s2 - h.g_m_s2) < EPS &&
        Math.abs(p.p_psia - h.p_psia) < EPS &&
        Math.abs(p.o2 - h.o2) < EPS &&
        Math.abs(p.u_cm_s - h.u_cm_s) < EPS &&
        Math.abs(p.L_mm - h.L_mm) < EPS,
    ) ?? null
  );
}

/** Preset whose atmosphere and gravity match (vent/size edited), for citing the source. */
export function nearestPresetAtmosphere(h: Habitat): Preset | null {
  return (
    PRESETS.find(
      (p) =>
        Math.abs(p.g_m_s2 - h.g_m_s2) < EPS &&
        Math.abs(p.p_psia - h.p_psia) < EPS &&
        Math.abs(p.o2 - h.o2) < EPS,
    ) ?? null
  );
}

export function gFraction(g_m_s2: number): number {
  return g_m_s2 / G0;
}
