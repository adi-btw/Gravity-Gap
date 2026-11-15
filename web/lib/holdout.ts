/**
 * S2 honesty test (plan/contracts.md "Round 3 · S2 Holdout addendum", ADR-0009).
 *
 * Types for artifacts/holdout.json (GET /holdout serves it unchanged), the normalize guard, and pure helpers for the
 * /trust page. Every number shown comes from the artifact; helpers only pick, sort and format.
 */
import { PSIA_PER_ATM } from "./physics";

export interface HoldoutRate {
  k: number;
  n: number;
  rate: number | null;
  interval90: [number, number] | null;
}

export interface HoldoutAtmosphere {
  o2: number;
  p_atm: number;
  p_psia: number;
  co2?: number;
  he?: number;
}

export interface PsiRow {
  record_id: string;
  investigation_id: string;
  source_file: string;
  source_row: number;
}

export interface HoldoutObservedProb {
  positives: number;
  n: number;
  rate: number;
  interval90: [number, number];
}

export interface HoldoutObservedQty {
  n: number;
  median: number;
  min: number;
  max: number;
  values: number[];
}

export type HoldoutObserved = HoldoutObservedProb | HoldoutObservedQty;

export interface HoldoutGroup {
  id: string;
  citation: string;
  metric: string;
  atmosphere: HoldoutAtmosphere;
  n_tests: number;
  psi_rows: PsiRow[];
  status: "evaluated" | "skipped";
  skip_reason?: string;
  covered: boolean | null;
  hit: boolean | null;
  strict_hit?: boolean | null;
  predicted?: { estimate: number | null; band90: [number, number] | null; shown_to_user: boolean; note: string | null };
  observed?: HoldoutObserved;
  gap?: number | null;
  error?: number | null;
  nearest_remaining_distance?: number | null;
}

export interface WorstMiss {
  id: string;
  atmosphere: HoldoutAtmosphere;
  n_tests: number;
  band90: [number, number];
  observed: HoldoutObserved;
  gap: number;
  error: number;
}

export interface HoldoutSummary {
  metric: string;
  n_groups: number;
  n_tests: number;
  n_skipped: number;
  n_covered: number;
  n_not_covered: number;
  band_coverage: HoldoutRate;
  strict_coverage: HoldoutRate;
  gate_precision: HoldoutRate;
  no_evidence_justified: HoldoutRate;
  weak_test: boolean;
  brier_covered?: number | null;
  brier_baseline_covered?: number | null;
  tests_inside_band_covered?: HoldoutRate;
  worst_misses: WorstMiss[];
}

export interface HoldoutResult {
  metric: string;
  label: string;
  kind: "probability" | "quantity" | string;
  investigation_id: string;
  scheme: string;
  hit_rule: string;
  groups: HoldoutGroup[];
  summary: HoldoutSummary;
}

export interface HoldoutOverall {
  n_groups: number;
  n_tests: number;
  n_covered: number;
  n_not_covered: number;
  n_skipped: number;
  band_coverage: HoldoutRate;
  gate_precision: HoldoutRate;
  no_evidence_justified: HoldoutRate;
  weak_test: boolean;
  target_coverage: number;
}

export interface SaffireHindcast {
  available: boolean;
  metric?: string;
  headline?: { primary: string; accuracy: number; hits: number; n: number; baseline_accuracy: number };
  scores?: Record<string, { hits: number; n: number; accuracy: number }>;
  caveat?: string;
  citation?: string;
}

export interface HoldoutArtifact {
  artifact: string;
  adr: string;
  citation: string;
  method: string;
  generated_at?: string;
  settings: { n_boot?: number; interval?: string; weak_below_groups?: number; query?: Record<string, unknown> } & Record<string, unknown>;
  metrics: Record<string, HoldoutResult>;
  overall: HoldoutOverall;
  wide_check: { scheme: string; what: string; metrics: Record<string, HoldoutResult>; overall: HoldoutOverall } | null;
  saffire_hindcast: SaffireHindcast | null;
}

export const HOLDOUT_METRICS = ["M1", "M2", "M3"] as const;

function isObj(v: unknown): v is Record<string, unknown> {
  return !!v && typeof v === "object" && !Array.isArray(v);
}

function isResult(v: unknown): v is HoldoutResult {
  return isObj(v) && Array.isArray(v.groups) && isObj(v.summary) && isObj((v.summary as Record<string, unknown>).band_coverage);
}

/** Validate artifacts/holdout.json; throws on a malformed artifact so the page shows an error, never a guess. */
export function normalizeHoldout(raw: unknown): HoldoutArtifact {
  if (!isObj(raw) || !isObj(raw.metrics) || !isObj(raw.overall)) throw new Error("holdout artifact is malformed");
  const metrics: Record<string, HoldoutResult> = {};
  for (const [m, r] of Object.entries(raw.metrics)) if (isResult(r)) metrics[m] = r;
  if (!Object.keys(metrics).length) throw new Error("holdout artifact is malformed: no metric results");
  const w = raw.wide_check;
  let wide: HoldoutArtifact["wide_check"] = null;
  if (isObj(w) && isObj(w.metrics) && isObj(w.overall)) {
    const wm: Record<string, HoldoutResult> = {};
    for (const [m, r] of Object.entries(w.metrics)) if (isResult(r)) wm[m] = r;
    wide = { scheme: String(w.scheme ?? ""), what: String(w.what ?? ""), metrics: wm, overall: w.overall as unknown as HoldoutOverall };
  }
  const sf = isObj(raw.saffire_hindcast) ? (raw.saffire_hindcast as unknown as SaffireHindcast) : null;
  return {
    artifact: String(raw.artifact ?? "holdout"),
    adr: String(raw.adr ?? "ADR-0009"),
    citation: String(raw.citation ?? "eng:holdout"),
    method: String(raw.method ?? ""),
    generated_at: typeof raw.generated_at === "string" ? raw.generated_at : undefined,
    settings: (isObj(raw.settings) ? raw.settings : {}) as HoldoutArtifact["settings"],
    metrics,
    overall: raw.overall as unknown as HoldoutOverall,
    wide_check: wide,
    saffire_hindcast: sf,
  };
}

/** "208 of 222" */
export function fmtCount(r: HoldoutRate | null | undefined): string {
  return r && r.n ? `${r.k} of ${r.n}` : "no groups";
}

/** 0.937 -> "94%" (whole percent; the interval says how uncertain it is). */
export function fmtPct(x: number | null | undefined, digits = 0): string {
  return x === null || x === undefined || !Number.isFinite(x) ? "–" : `${(x * 100).toFixed(digits)}%`;
}

/** "90–96%" for a Wilson interval. */
export function fmtInterval(iv: [number, number] | null | undefined): string {
  return iv ? `${(iv[0] * 100).toFixed(0)}–${(iv[1] * 100).toFixed(0)}%` : "–";
}

export type MapMark = "hit" | "miss" | "grey";

export interface MapPoint {
  id: string;
  o2: number;
  p_atm: number;
  p_psia: number;
  n_tests: number;
  mark: MapMark;
  /** Why the point is grey: not covered (no evidence) or skipped. */
  greyReason?: "no_evidence" | "skipped";
  metric: string;
  label: string;
}

/** Map mark for one group: hit = filled, miss = hollow + cross, no-evidence or skipped = grey. */
export function groupMark(g: HoldoutGroup): { mark: MapMark; greyReason?: "no_evidence" | "skipped" } {
  if (g.status === "skipped") return { mark: "grey", greyReason: "skipped" };
  if (!g.covered) return { mark: "grey", greyReason: "no_evidence" };
  return { mark: g.hit ? "hit" : "miss" };
}

export function atmText(a: HoldoutAtmosphere): string {
  const bits = [`${(a.o2 * 100).toFixed(1)}% O₂`, `${(a.p_psia ?? a.p_atm * PSIA_PER_ATM).toFixed(1)} psia`];
  if (a.co2) bits.push(`CO₂ ${a.co2}`);
  if (a.he) bits.push(`He ${a.he}`);
  return bits.join(", ");
}

export function mapPoints(r: HoldoutResult): MapPoint[] {
  return r.groups.map((g) => {
    const m = groupMark(g);
    const mark = m.mark;
    const what = mark === "hit" ? "band held" : mark === "miss" ? "band missed" : m.greyReason === "skipped" ? "skipped" : "no evidence";
    return {
      id: g.id,
      o2: g.atmosphere.o2,
      p_atm: g.atmosphere.p_atm,
      p_psia: g.atmosphere.p_psia,
      n_tests: g.n_tests,
      mark,
      greyReason: m.greyReason,
      metric: g.metric,
      label: `${g.metric} ${atmText(g.atmosphere)}: ${g.n_tests} test${g.n_tests === 1 ? "" : "s"}, ${what}`,
    };
  });
}

export function markCounts(points: MapPoint[]): { hit: number; miss: number; noEvidence: number; skipped: number } {
  return {
    hit: points.filter((p) => p.mark === "hit").length,
    miss: points.filter((p) => p.mark === "miss").length,
    noEvidence: points.filter((p) => p.greyReason === "no_evidence").length,
    skipped: points.filter((p) => p.greyReason === "skipped").length,
  };
}

/** Distinct skip reasons with their counts (every skipped group is counted with its reason). */
export function skipReasons(r: HoldoutResult): { reason: string; n: number }[] {
  const by = new Map<string, number>();
  r.groups.forEach((g) => {
    if (g.status === "skipped") by.set(g.skip_reason ?? "no reason given", (by.get(g.skip_reason ?? "no reason given") ?? 0) + 1);
  });
  return [...by.entries()].map(([reason, n]) => ({ reason, n }));
}

/** The worst misses of a result joined to their groups (for the PSI rows), largest gap first as in the artifact. */
export function worstMissRows(r: HoldoutResult): { miss: WorstMiss; group: HoldoutGroup | undefined }[] {
  const by = new Map(r.groups.map((g) => [g.id, g]));
  return (r.summary.worst_misses ?? []).map((miss) => ({ miss, group: by.get(miss.id) }));
}

export function isProbObserved(o: HoldoutObserved | undefined): o is HoldoutObservedProb {
  return !!o && "positives" in o;
}

/** Observed result in words: "0 of 2 self-extinguished" or "median 1.52 mm (3 tests)". */
export function observedText(o: HoldoutObserved | undefined): string {
  if (!o) return "–";
  if (isProbObserved(o)) return `${o.positives} of ${o.n} self-extinguished`;
  return `median ${o.median.toFixed(2)} mm (${o.n} test${o.n === 1 ? "" : "s"})`;
}

export function bandText(kind: string, b: [number, number] | null | undefined): string {
  if (!b) return "–";
  return kind === "probability" ? `${fmtPct(b[0])}–${fmtPct(b[1])}` : `${b[0].toFixed(2)}–${b[1].toFixed(2)} mm`;
}
