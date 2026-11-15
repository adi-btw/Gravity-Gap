/**
 * S4 side-by-side habitat compare (plan/contracts.md "Round 3 · S4 Compare addendum").
 *
 * The live API (`POST /compare`, engine/compare.py) is the source of truth. Offline, for two presets, the same
 * diff and summary are rebuilt here from the bundled bounds artifacts with the SAME rules (a parity test checks
 * this against engine output). Never subtracts a number from "no evidence".
 */
import { matchPreset, presetToHabitat, type Habitat } from "./habitat";
import { PRESETS_BY_ID, type PresetId } from "./presets";
import type { Band, BoundsResult, Estimate, MetricKind } from "./types";

export type Regime = "forced" | "mixed" | "buoyant";
export type SideKey = PresetId | "current";

export interface CompareHabitat extends Habitat {
  preset_id: string | null;
  label: string;
}

export interface CompareSide {
  applicable: boolean;
  reason: string | null;
  estimate: Estimate;
  band90: Band;
  regime: Regime | null;
  regime_fractions: { forced: number; mixed: number; buoyant: number } | null;
  transfer: { basis: string; confidence: "high" | "medium" | "low" } | null;
  n_train: number | null;
  model_version: string | null;
}

export interface MetricDiff {
  regime: { a: Regime | null; b: Regime | null; changed: boolean };
  coverage: { a: boolean; b: boolean; change: "both" | "neither" | "lost" | "gained" };
  estimate: { a: Estimate; b: Estimate; delta: number | null; direction: "higher" | "lower" | "same" | "changed" } | null;
  estimate_note: string | null;
  band_width: { a: number; b: number; direction: "wider" | "narrower" | "same" } | null;
}

export interface MetricCompare {
  metric: string;
  label: string;
  unit: string | null;
  kind: MetricKind;
  a: CompareSide;
  b: CompareSide;
  diff: MetricDiff;
}

export interface InputDiff {
  field: keyof Habitat;
  label: string;
  unit: string;
  a: number;
  b: number;
}

export interface CompareResult {
  a: CompareHabitat;
  b: CompareHabitat;
  inputs_diff: InputDiff[];
  metrics: MetricCompare[];
  summary: string;
  model_versions?: Record<string, string | null>;
}

export const METRIC_IDS = ["M1", "M2", "M3", "M4", "M5"] as const;
export const DEFAULT_A: SideKey = "iss";
export const DEFAULT_B: SideKey = "current";
const FIELDS: (keyof Habitat)[] = ["g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm"];
const FIELD_INFO: Record<keyof Habitat, [string, string]> = {
  g_m_s2: ["gravity", "m/s²"],
  p_psia: ["pressure", "psia"],
  o2: ["O₂", "%"],
  u_cm_s: ["vent speed", "cm/s"],
  L_mm: ["flame size", "mm"],
};
const REGIMES: Regime[] = ["forced", "mixed", "buoyant"];
export const REGIME_WORDS: Record<Regime, string> = { forced: "forced flow", mixed: "mixed", buoyant: "buoyancy-dominated" };
export const CURRENT_LABEL = "Current habitat";

// ------------------------------------------------------------------ URL state

/** `?a=` / `?b=` value -> preset id or "current"; anything else falls back. */
export function parseSide(raw: string | null | undefined, fallback: SideKey): SideKey {
  if (raw === "current") return "current";
  if (raw && Object.prototype.hasOwnProperty.call(PRESETS_BY_ID, raw)) return raw as PresetId;
  return fallback;
}

/** Query string for /compare: both sides plus the habitat query (which "current" refers to). */
export function compareQuery(a: SideKey, b: SideKey, habitatQuery: string): string {
  const q = new URLSearchParams(habitatQuery);
  q.set("a", a);
  q.set("b", b);
  return q.toString();
}

export interface ResolvedSide {
  key: SideKey;
  habitat: Habitat;
  presetId: PresetId | null;
  label: string;
}

/** A side key -> concrete habitat. "current" that matches a preset is that preset (offline works for it). */
export function resolveSide(key: SideKey, current: Habitat): ResolvedSide {
  if (key !== "current") {
    const p = PRESETS_BY_ID[key];
    return { key, habitat: presetToHabitat(p), presetId: p.id, label: p.label };
  }
  const p = matchPreset(current);
  return p
    ? { key, habitat: presetToHabitat(p), presetId: p.id, label: p.label }
    : { key, habitat: { ...current }, presetId: null, label: CURRENT_LABEL };
}

/** "Compare with…" target from /bounds: the current habitat against ISS (or the lunar base when already at ISS). */
export function compareWithTarget(current: Habitat): { a: SideKey; b: SideKey } {
  return { a: "current", b: matchPreset(current)?.id === "iss" ? "lunar_base" : "iss" };
}

/** Question for the Ask drawer, phrased like the cached demo question ("What changes between ISS and the lunar base?"). */
const QUESTION_NAMES: Record<PresetId, string> = {
  iss: "ISS",
  exploration: "the exploration vehicle",
  lunar_base: "the lunar base",
  lunar_rover: "the lunar rover",
  mars_base: "the Mars base",
  earth: "Earth",
};
export function compareQuestion(a: PresetId, b: PresetId): string {
  return `What changes between ${QUESTION_NAMES[a]} and ${QUESTION_NAMES[b]}?`;
}

// ------------------------------------------------------------------ formatting (mirrors engine/compare.py)

/** 3 significant figures, plain decimal (engine.compare.fmt / engine.ai.answer.fmt). */
export function fmt3(x: number | string): string {
  if (typeof x === "string") return x.replace(/_/g, " ");
  if (x === 0) return "0";
  if (Math.abs(x) >= 100) return String(Math.round(x));
  const d = Math.max(0, 2 - Math.floor(Math.log10(Math.abs(x))));
  let s = x.toFixed(d);
  if (s.includes(".")) s = s.replace(/0+$/, "").replace(/\.$/, "");
  return s;
}

export function fmtValue(kind: string | null | undefined, unit: string | null | undefined, x: number | string): string {
  if (typeof x === "string") return fmt3(x);
  if (kind === "probability" || unit === "probability" || unit === "fraction") return `${fmt3(x * 100)}%`;
  return unit && unit !== "category" ? `${fmt3(x)} ${unit}` : fmt3(x);
}

function fmtInput(field: keyof Habitat, v: number): string {
  return field === "o2" ? `${fmt3(v * 100)}%` : `${fmt3(v)} ${FIELD_INFO[field][1]}`;
}

function same(a: number, b: number): boolean {
  return Math.abs(a - b) <= Math.max(1e-9 * Math.max(Math.abs(a), Math.abs(b)), 1e-12);
}

function join(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

function plural(ms: string[], one: string, many: string): string {
  return `${join(ms)} ${ms.length === 1 ? one : many}`;
}

// ------------------------------------------------------------------ diff rules (mirrors engine/compare.py)

export function dominantRegime(fr: CompareSide["regime_fractions"] | undefined): Regime | null {
  if (!fr) return null;
  const vals = REGIMES.map((r) => (typeof fr[r] === "number" ? fr[r] : -1));
  const max = Math.max(...vals);
  return max < 0 ? null : REGIMES[vals.indexOf(max)];
}

export function sideFromBounds(r: BoundsResult): CompareSide {
  return {
    applicable: Boolean(r.applicable),
    reason: r.reason ?? null,
    estimate: r.estimate ?? null,
    band90: r.band90 ?? null,
    regime: dominantRegime(r.regime_fractions),
    regime_fractions: r.regime_fractions ?? null,
    transfer: r.transfer ?? null,
    n_train: r.n_train ?? null,
    model_version: r.model_version ?? null,
  };
}

export function metricDiff(metric: string, labelA: string, labelB: string, sa: CompareSide, sb: CompareSide): MetricDiff {
  const change = sa.applicable ? (sb.applicable ? "both" : "lost") : sb.applicable ? "gained" : "neither";
  const diff: MetricDiff = {
    regime: { a: sa.regime, b: sb.regime, changed: sa.regime !== sb.regime },
    coverage: { a: sa.applicable, b: sb.applicable, change },
    estimate: null,
    estimate_note: null,
    band_width: null,
  };
  if (!(sa.applicable && sb.applicable) || sa.estimate === null || sb.estimate === null) {
    diff.estimate_note =
      !sa.applicable && !sb.applicable
        ? `No difference shown: neither habitat has evidence for ${metric}.`
        : `No difference shown: ${sa.applicable ? labelB : labelA} has no evidence for ${metric}.`;
    return diff;
  }
  const ea = sa.estimate;
  const eb = sb.estimate;
  if (typeof ea === "string" || typeof eb === "string") {
    diff.estimate = { a: ea, b: eb, delta: null, direction: ea === eb ? "same" : "changed" };
    return diff;
  }
  const s = same(ea, eb);
  diff.estimate = { a: ea, b: eb, delta: s ? 0 : eb - ea, direction: s ? "same" : eb > ea ? "higher" : "lower" };
  const ba = sa.band90;
  const bb = sb.band90;
  if (ba && bb && [...ba, ...bb].every((v) => typeof v === "number")) {
    const wa = (ba[1] as number) - (ba[0] as number);
    const wb = (bb[1] as number) - (bb[0] as number);
    diff.band_width = { a: wa, b: wb, direction: same(wa, wb) ? "same" : wb > wa ? "wider" : "narrower" };
  }
  return diff;
}

export function buildSummary(a: CompareHabitat, b: CompareHabitat, inputs: InputDiff[], rows: MetricCompare[]): string {
  const parts: string[] = [];
  if (inputs.length) {
    const ch = inputs.map((d) => `${d.label} ${fmtInput(d.field, d.a)} → ${fmtInput(d.field, d.b)}`);
    parts.push(`Moving from ${a.label} to ${b.label} changes ${join(ch)}.`);
  } else {
    parts.push(`${a.label} and ${b.label} have the same inputs.`);
  }

  const flips = new Map<string, string[]>();
  rows.forEach((r) => {
    const rg = r.diff.regime;
    if (rg.changed && rg.a && rg.b) flips.set(`${rg.a}|${rg.b}`, [...(flips.get(`${rg.a}|${rg.b}`) ?? []), r.metric]);
  });
  flips.forEach((ms, k) => {
    const [ra, rb] = k.split("|") as [Regime, Regime];
    const who = ms.length === rows.length ? "for every metric" : `for ${join(ms)}`;
    parts.push(`The flame regime changes from ${REGIME_WORDS[ra]} to ${REGIME_WORDS[rb]} ${who}.`);
  });

  const by = (c: string) => rows.filter((r) => r.diff.coverage.change === c).map((r) => r.metric);
  const lost = by("lost");
  const gained = by("gained");
  const neither = by("neither");
  if (lost.length) parts.push(`${plural(lost, "loses its", "lose their")} evidence at ${b.label} (no estimate there).`);
  if (gained.length) parts.push(`${plural(gained, "gains", "gain")} evidence at ${b.label}.`);
  if (neither.length) parts.push(`${plural(neither, "has", "have")} no evidence on either side.`);

  const moves: string[] = [];
  const cats: string[] = [];
  rows.forEach((r) => {
    const est = r.diff.estimate;
    if (!est || est.a === null || est.b === null) return;
    const va = fmtValue(r.kind, r.unit, est.a);
    const vb = fmtValue(r.kind, r.unit, est.b);
    if (est.delta === null) cats.push(est.direction === "changed" ? `${r.metric} changes from ${va} to ${vb}` : `${r.metric} stays at ${va}`);
    else if (est.direction === "same") moves.push(`${r.metric} stays at ${va}`);
    else moves.push(`${r.metric} goes from ${va} to ${vb}`);
  });
  if (moves.length) parts.push(`Where both sides have evidence, ${join(moves)}.`);
  if (cats.length) parts.push(`${join(cats)}.`);
  (["wider", "narrower"] as const).forEach((w) => {
    const ms = rows.filter((r) => r.diff.band_width?.direction === w).map((r) => r.metric);
    if (ms.length) parts.push(`The 90% band is ${w} at ${b.label} for ${join(ms)}.`);
  });
  return parts.join(" ");
}

/** Offline compare: the engine's rules applied to two sets of precomputed bounds results (M1..M5 in order). */
export function buildCompare(a: CompareHabitat, b: CompareHabitat, boundsA: BoundsResult[], boundsB: BoundsResult[]): CompareResult {
  const inputs: InputDiff[] = FIELDS.filter((k) => !same(a[k], b[k])).map((k) => ({
    field: k,
    label: FIELD_INFO[k][0],
    unit: FIELD_INFO[k][1],
    a: a[k],
    b: b[k],
  }));
  if (a.label === b.label && inputs.length) {
    a = { ...a, label: `${a.label} (A)` };
    b = { ...b, label: `${b.label} (B)` };
  }
  const rows: MetricCompare[] = boundsA.map((pa, i) => {
    const pb = boundsB[i];
    const sa = sideFromBounds(pa);
    const sb = sideFromBounds(pb);
    return { metric: pa.metric, label: pa.label, unit: pa.unit, kind: pa.kind, a: sa, b: sb, diff: metricDiff(pa.metric, a.label, b.label, sa, sb) };
  });
  return {
    a,
    b,
    inputs_diff: inputs,
    metrics: rows,
    summary: buildSummary(a, b, inputs, rows),
    model_versions: Object.fromEntries(boundsA.map((p) => [p.metric, p.model_version ?? null])),
  };
}

/** Shared value axis for one metric row: both sides' estimates and bands (probabilities always 0..1). */
export function sharedDomain(row: MetricCompare): [number, number] | undefined {
  if (row.kind === "probability" || row.unit === "fraction" || row.unit === "probability") return [0, 1];
  return undefined; // BandChart pads one domain over BOTH columns, so the axis is shared either way
}
