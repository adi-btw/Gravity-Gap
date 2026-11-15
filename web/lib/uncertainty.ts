/**
 * S3 "What makes this band wide" (plan/contracts.md "Round 3 · S3 Uncertainty drivers addendum", ADR-0008).
 *
 * Types for the optional `drivers` field of POST /bounds (and artifacts/uncertainty/{preset}.json offline), the
 * normalize guard, and the pure display helpers. Nothing here computes a new share: shares come from the engine and
 * are only rounded to 5% for display, so they do not look more precise than they are.
 */

export type DriverBasis = "psi_data" | "honesty_rule" | "engineering_assumption";
export type DriverSourceId = "model_uncertainty" | "gravity_widening" | "C_b" | "k" | "dT_over_T" | "L_mm" | "remainder";

export interface DriverSource {
  id: DriverSourceId | string;
  label: string;
  share: number;
  basis: DriverBasis | string;
  reaches_band: boolean;
  note?: string;
}

export interface PlannerCandidateRef {
  rank: number;
  metric: string;
  type?: string;
  g_m_s2: number;
  p_psia: number;
  o2: number;
  u_cm_s: number;
  co2?: number;
  distance: number;
}

export interface DriversLever {
  source: string;
  share: number;
  basis: string;
  text: string;
  planner_candidate: PlannerCandidateRef | null;
}

export interface DriversApplicable {
  metric: string;
  label: string;
  citation: string;
  adr: string;
  applicable: true;
  kind: string;
  unit: string | null;
  estimate: number;
  band90: [number, number];
  band_width: number;
  model_band90: [number, number];
  model_band_width: number;
  widen_factor: number;
  sources: DriverSource[];
  shares_sum: number;
  lever: DriversLever | null;
  method: string;
}

export interface DriversNotApplicable {
  metric: string;
  label?: string;
  citation?: string;
  adr?: string;
  applicable: false;
  reason: string;
}

export type Drivers = DriversApplicable | DriversNotApplicable;

export const BASIS_TEXT: Record<DriverBasis, string> = {
  psi_data: "from limited NASA tests",
  honesty_rule: "honesty rule for gravity",
  engineering_assumption: "engineering assumption, not PSI data",
};

export function basisText(basis: string): string {
  return BASIS_TEXT[basis as DriverBasis] ?? basis.replace(/_/g, " ");
}

/** Round half to even, like Python's round(), so the UI matches the engine's lever text ("About 65%"). */
function roundHalfEven(x: number): number {
  const r = Math.round(x);
  return Math.abs(x % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r;
}

/** A share (0..1) rounded to 5% steps, as a whole percent. */
export function roundShare5(share: number): number {
  if (!Number.isFinite(share)) return 0;
  return 5 * roundHalfEven(20 * share);
}

/** "about 65%", "under 5%" (non-zero but rounds to 0) or "0%". */
export function shareLabel(share: number): string {
  if (!Number.isFinite(share) || share <= 0) return "0%";
  const p = roundShare5(share);
  return p === 0 ? "under 5%" : `about ${p}%`;
}

/** Display name: the remainder is "not split" (interactions between the inputs). */
export function sourceName(s: DriverSource): string {
  return s.id === "remainder" ? "Not split (interactions)" : s.label;
}

/** Segments worth drawing: share > 0 and the source actually reaches the band (k never does). */
export function drawnSources(d: DriversApplicable): DriverSource[] {
  return d.sources.filter((s) => s.reaches_band && Number.isFinite(s.share) && s.share > 0);
}

/** Screen-reader text listing every share in order. */
export function driversSummary(d: DriversApplicable): string {
  const parts = d.sources.map((s) =>
    !s.reaches_band ? `${sourceName(s)}: 0%, never reaches this band` : `${sourceName(s)}: ${shareLabel(s.share)} (${basisText(s.basis)})`,
  );
  return `What makes the ${d.metric} band wide, shares of its width rounded to 5%: ${parts.join("; ")}.`;
}

function isObj(v: unknown): v is Record<string, unknown> {
  return !!v && typeof v === "object" && !Array.isArray(v);
}

/** Validate a raw drivers object; null for missing or malformed data (never invents a breakdown). */
export function normalizeDrivers(raw: unknown): Drivers | null {
  if (!isObj(raw) || typeof raw.metric !== "string" || typeof raw.applicable !== "boolean") return null;
  if (!raw.applicable) {
    return { metric: raw.metric, label: raw.label as string | undefined, applicable: false, reason: String(raw.reason ?? "No band to break down.") };
  }
  const sources = raw.sources;
  if (!Array.isArray(sources) || !sources.length) return null;
  const ok = sources.every((s) => isObj(s) && typeof s.id === "string" && typeof s.label === "string" && typeof s.share === "number" && Number.isFinite(s.share));
  if (!ok) return null;
  const band = raw.band90;
  if (!Array.isArray(band) || band.length !== 2 || !band.every((x) => typeof x === "number")) return null;
  const lever = isObj(raw.lever) && typeof raw.lever.text === "string" ? (raw.lever as unknown as DriversLever) : null;
  return {
    ...(raw as unknown as DriversApplicable),
    sources: (sources as DriverSource[]).map((s) => ({ ...s, reaches_band: s.reaches_band !== false, basis: String(s.basis ?? "") })),
    lever: lever ? { ...lever, planner_candidate: isObj(lever.planner_candidate) ? lever.planner_candidate : null } : null,
  };
}

/** One metric's drivers out of artifacts/uncertainty/{preset}.json ({metrics: {M1: drivers, ...}}). */
export function driversFromArtifact(raw: unknown, metric: string): Drivers | null {
  if (!isObj(raw) || !isObj(raw.metrics)) return null;
  return normalizeDrivers(raw.metrics[metric]);
}

/** Planner anchor for a candidate (PlannerView gives each item id="candidate-<rank>"). */
export function plannerHref(c: PlannerCandidateRef | null | undefined, queryString: string): string | null {
  if (!c || !Number.isFinite(c.rank)) return null;
  return `/planner?${queryString}#candidate-${c.rank}`;
}
