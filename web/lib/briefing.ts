/**
 * S1 habitat fire-safety briefing (plan/contracts.md "Round 3 · S1 Briefing addendum", ADR-0010).
 *
 * Types for POST /briefing and artifacts/briefing/{preset}.json, the normalize guard, URL state and pure helpers for
 * the /briefing page. Every number shown comes from the briefing; helpers only pick and format.
 */
import { habitatToQuery, matchPreset, presetToHabitat, type Habitat } from "./habitat";
import { PRESETS_BY_ID, type Preset, type PresetId } from "./presets";

export type ChipValue = "evidence" | "partial" | "no evidence";
export type Pillar = "prevention" | "behaviour" | "detection" | "suppression";

export interface BriefingChip {
  pillar: Pillar;
  label: string;
  value: ChipValue;
  rule: string;
  because: string;
  metrics: Record<string, boolean>;
  citations: string[];
}

export interface BriefingKeyNumber {
  metric: string;
  label: string;
  unit: string;
  kind: string;
  estimate: number | string;
  band90: [number | string, number | string] | null;
  transfer_confidence: string | null;
  n_train: number | null;
  text: string;
  citations: string[];
}

export interface BriefingDriver {
  metric: string;
  source: string;
  share: number;
  basis: string;
  text: string;
  planner_candidate: { rank: number } | null;
  citations: string[];
}

export interface BriefingGap {
  kind: "metric" | "detection" | "suppression";
  id: string;
  text: string;
  metric?: string;
  label?: string;
  diluent?: string;
  safety_note?: string;
  citations: string[];
}

export interface BriefingNextTest {
  rank: number;
  metric: string;
  type: string;
  g_m_s2: number;
  p_psia: number;
  o2: number;
  u_cm_s: number;
  co2: number;
  rationale: string;
  close: boolean;
  citations: string[];
}

export interface Briefing {
  preset_id?: string | null;
  habitat: {
    preset_id: string | null;
    label: string;
    g_m_s2: number;
    p_psia: number;
    o2: number;
    u_cm_s: number;
    L_mm: number;
    assumed: string[];
    source: string;
    line: string;
  };
  verdicts: BriefingChip[];
  key_numbers: BriefingKeyNumber[];
  drivers: BriefingDriver[];
  gaps: BriefingGap[];
  next_tests: { rule: string; note: string | null; items: BriefingNextTest[]; citations: string[] };
  history: { status: string; rule: string; text: string; citations: string[] };
  trust: { text: string; citations: string[] };
  footer: {
    model_versions: Record<string, string>;
    engine_version: string;
    manifest: { artifact_set_sha256: string | null; generated_at: string | null; note: string };
    generated_at: string;
    date: string;
    disclaimer: string;
  };
  citations: string[];
}

export const PILLAR_ORDER: readonly Pillar[] = ["prevention", "behaviour", "detection", "suppression"];
const VALUES: readonly ChipValue[] = ["evidence", "partial", "no evidence"];

/** Accept a briefing (live or the preset artifact); throw on anything that is not one. */
export function normalizeBriefing(raw: unknown): Briefing {
  const o = (raw ?? {}) as Partial<Briefing>;
  const ok =
    !!o.habitat &&
    Array.isArray(o.verdicts) &&
    o.verdicts.length === 4 &&
    o.verdicts.every((c, i) => c.pillar === PILLAR_ORDER[i] && VALUES.includes(c.value)) &&
    Array.isArray(o.key_numbers) &&
    Array.isArray(o.gaps) &&
    !!o.next_tests &&
    !!o.history &&
    !!o.trust &&
    !!o.footer &&
    typeof o.footer.disclaimer === "string";
  if (!ok) throw new Error("malformed briefing");
  return {
    ...(o as Briefing),
    drivers: Array.isArray(o.drivers) ? o.drivers : [],
    citations: Array.isArray(o.citations) ? o.citations : [],
  };
}

/** Words and a symbol for each chip value, so the strip never relies on colour (and prints in black and white). */
export const CHIP_TEXT: Record<ChipValue, { word: string; symbol: string; srWord: string }> = {
  evidence: { word: "Evidence", symbol: "✓", srWord: "evidence" },
  partial: { word: "Partial", symbol: "◐", srWord: "partial evidence" },
  "no evidence": { word: "No evidence", symbol: "✕", srWord: "no evidence" },
};

export function isPresetId(v: string | null | undefined): v is PresetId {
  return !!v && Object.prototype.hasOwnProperty.call(PRESETS_BY_ID, v);
}

export interface BriefingTarget {
  presetId: PresetId | null;
  habitat: Habitat;
  label: string;
}

/**
 * URL state: `?habitat=<preset>` wins (and is then written back as habitat-bar values); otherwise the habitat-bar
 * query, which resolves to a preset when all five values match one.
 */
export function resolveBriefingTarget(param: string | null | undefined, habitat: Habitat): BriefingTarget {
  if (isPresetId(param)) {
    const p = PRESETS_BY_ID[param];
    return { presetId: p.id, habitat: presetToHabitat(p), label: p.label };
  }
  const p: Preset | null = matchPreset(habitat);
  return p ? { presetId: p.id, habitat: presetToHabitat(p), label: p.label } : { presetId: null, habitat, label: "Custom habitat" };
}

/** Query string for the /briefing link: the habitat-bar values, plus `habitat=<preset>` when they match a preset. */
export function briefingQuery(habitat: Habitat): string {
  const q = habitatToQuery(habitat);
  const p = matchPreset(habitat);
  if (p) q.set("habitat", p.id);
  return q.toString();
}

/** First 12 hex characters of the manifest hash, or null. Labelled "artifact set at build time": it goes stale. */
export function shortHash(sha: string | null | undefined): string | null {
  return sha && /^[0-9a-f]{12,}$/i.test(sha) ? sha.slice(0, 12) : null;
}

export function gapsByKind(gaps: BriefingGap[]) {
  return {
    metric: gaps.filter((g) => g.kind === "metric"),
    detection: gaps.filter((g) => g.kind === "detection"),
    suppression: gaps.filter((g) => g.kind === "suppression"),
  };
}

function num(n: number): string {
  return String(Number(n.toFixed(3)));
}

/** Compact one-line description of a planner candidate; values copied from the briefing, only formatted. */
export function nextTestLine(t: BriefingNextTest): string {
  const parts = [`${t.metric} ${t.type} test`, `${num(t.g_m_s2)} m/s²`, `${num(t.p_psia)} psia`, `${num(t.o2 * 100)}% O₂`, `vent ${num(t.u_cm_s)} cm/s`];
  if (t.co2) parts.push(`${num(t.co2 * 100)}% CO₂ replacing nitrogen`);
  return parts.join(" · ");
}

/** "M1, M3" style list of a chip's metrics with their coverage words (for the screen-reader label). */
export function chipLabel(c: BriefingChip): string {
  return `${c.label}: ${CHIP_TEXT[c.value].srWord}`;
}
