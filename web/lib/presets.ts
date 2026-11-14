/** F0 habitat presets, mirroring engine/presets.py (plan/04-features.md). */

export interface Preset {
  id: PresetId;
  label: string;
  g_m_s2: number;
  p_psia: number;
  o2: number;
  u_cm_s: number;
  L_mm: number;
  source: string;
  /** Fields that are engineering assumptions, shown as "assumed, editable". */
  assumed: string[];
}

export type PresetId =
  | "iss"
  | "exploration"
  | "lunar_base"
  | "lunar_rover"
  | "mars_base"
  | "earth";

const BRIEF = "NASA Space Apps 2026 challenge brief";
const EXPLORATION_ATM = "NASA exploration atmosphere 8.2 psia / 34% O2 (BRE PSI-20 objectives)";
const ASSUMED = ["u_cm_s", "L_mm"];

export const PRESETS: readonly Preset[] = [
  {
    id: "iss",
    label: "ISS",
    g_m_s2: 0.0,
    p_psia: 14.7,
    o2: 0.21,
    u_cm_s: 10.0,
    L_mm: 10.0,
    source: `${BRIEF}; ISS sea-level cabin atmosphere 14.7 psia / 21% O2`,
    assumed: [...ASSUMED],
  },
  {
    id: "exploration",
    label: "Exploration vehicle",
    g_m_s2: 0.0,
    p_psia: 10.2,
    o2: 0.265,
    u_cm_s: 10.0,
    L_mm: 10.0,
    source: `${BRIEF}; NASA exploration vehicle atmosphere 10.2 psia / 26.5% O2`,
    assumed: [...ASSUMED],
  },
  {
    id: "lunar_base",
    label: "Lunar base",
    g_m_s2: 1.62,
    p_psia: 8.2,
    o2: 0.34,
    u_cm_s: 10.0,
    L_mm: 10.0,
    source: `${BRIEF}; ${EXPLORATION_ATM}`,
    assumed: [...ASSUMED],
  },
  {
    id: "lunar_rover",
    label: "Lunar rover",
    g_m_s2: 1.62,
    p_psia: 8.2,
    o2: 0.34,
    u_cm_s: 5.0,
    L_mm: 10.0,
    source: `${BRIEF}; ${EXPLORATION_ATM}`,
    assumed: [...ASSUMED],
  },
  {
    id: "mars_base",
    label: "Mars base",
    g_m_s2: 3.71,
    p_psia: 8.2,
    o2: 0.34,
    u_cm_s: 10.0,
    L_mm: 10.0,
    source: `${BRIEF}; ${EXPLORATION_ATM}`,
    assumed: [...ASSUMED],
  },
  {
    id: "earth",
    label: "Earth reference",
    g_m_s2: 9.81,
    p_psia: 14.7,
    o2: 0.21,
    u_cm_s: 0.0,
    L_mm: 10.0,
    source: `${BRIEF}; Earth sea-level air 14.7 psia / 21% O2 (quiescent)`,
    assumed: [...ASSUMED],
  },
];

export const PRESETS_BY_ID: Readonly<Record<PresetId, Preset>> = Object.fromEntries(
  PRESETS.map((p) => [p.id, p]),
) as Record<PresetId, Preset>;

export const DEFAULT_PRESET_ID: PresetId = "lunar_rover";
