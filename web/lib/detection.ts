/**
 * R3 Detection evidence (plan/contracts.md "Round 2 · R3 Detection evidence addendum", ADR-0007).
 *
 * Types for artifacts/detection.json (GET /detection serves it unchanged), the normalize guard, and the pure
 * helpers the charts use (log axis, ticks, grouping). Nothing here computes a new number: every value drawn comes
 * from the artifact.
 */
import { fmtSig } from "./format";

export interface DetectionSource {
  investigation_id: string;
  file: string;
  sheet: string | null;
  rows: string;
}

export interface SizeDefinition {
  label: string;
  note: string;
}

export interface DetectionGap {
  id: string;
  text: string;
}

export interface SmokeBinSeries {
  id: string;
  label: string;
  material: string;
  material_label: string;
  run: string;
  variant: "all" | "big_only";
  variant_label: string;
  size_definition: string;
  note: string;
  source: DetectionSource;
  diameter_nm: number[];
  count: number[];
  fraction: number[];
  dlnD: number | null;
  stats: {
    count_median_diameter_nm: number;
    geometric_mean_diameter_nm: number;
    geometric_std: number;
    particle_count: number;
  };
  workbook_reported?: { geometric_mean_diameter_nm: number; geometric_std: number; cells: string } | null;
}

export interface SmokeRunPoint {
  material: string;
  aged: boolean;
  run: string;
  row: number;
  description?: string;
  value_nm: number;
  geometric_std?: number;
}

export interface SmokeRunsByMaterial {
  material: string;
  material_label: string;
  aged: boolean;
  n_runs: number;
  dg_nm: { median: number; min: number; max: number };
  geometric_std_median: number;
  diameter_of_average_mass_nm_median: number;
}

export interface SmokeRuns {
  id: string;
  label: string;
  size_definition: string;
  note: string;
  source: DetectionSource;
  materials: string[];
  material_labels: Record<string, string>;
  points: SmokeRunPoint[];
  by_material: SmokeRunsByMaterial[];
}

export interface DustPoint {
  bag: number;
  value_nm: number;
  workbook_reported_nm?: number;
  number_per_cm3?: number;
  mass_mg_per_m3?: number;
}

export interface AverageMassComparison {
  size_definition: string;
  note: string;
  smoke: {
    id: string;
    label: string;
    source: DetectionSource;
    points: { material: string; aged: boolean; run: string; row: number; value_nm: number }[];
    range_nm: { min: number; max: number };
  };
  dust: {
    id: string;
    label: string;
    material_text: string;
    source: DetectionSource;
    material_source: DetectionSource;
    assumed_density_g_per_cm3: number;
    density_note: string;
    points: DustPoint[];
    range_nm: { min: number; max: number };
  };
}

export interface SimSeries {
  id: string;
  label: string;
  case: string;
  case_label: string;
  gravity: "earth" | "micro";
  variant: "base" | "no_settling" | "no_thermophoresis";
  surrogate: string;
  time_s: number;
  is_simulation: true;
  size_definition: string;
  note: string;
  source: DetectionSource;
  diameter_nm: number[];
  fraction: number[];
  stats: {
    count_median_diameter_nm: number;
    geometric_mean_diameter_nm: number;
    geometric_std: number;
    peak_diameter_nm: number;
    share_of_count_above_20um: number;
  };
}

export interface DetectionArtifact {
  schema_version: number;
  generated_at?: string;
  title: string;
  verdict: string;
  scope_note: string;
  generated_from: { file: string; sha256: string; bytes: number }[];
  gaps: DetectionGap[];
  size_definitions: Record<string, SizeDefinition>;
  smoke_bins: SmokeBinSeries[];
  smoke_runs: SmokeRuns;
  average_mass_comparison: AverageMassComparison;
  simulation: SimSeries[];
}

// ------------------------------------------------------------------ guard

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);

function isSource(v: unknown): v is DetectionSource {
  return isObj(v) && typeof v.investigation_id === "string" && typeof v.file === "string";
}

/** A drawable curve: equal-length arrays, positive diameters for the log axis, finite non-negative fractions. */
function isCurve(s: Record<string, unknown>): boolean {
  const d = s.diameter_nm;
  const f = s.fraction;
  return (
    Array.isArray(d) &&
    Array.isArray(f) &&
    d.length > 0 &&
    d.length === f.length &&
    d.every((x) => isNum(x) && x > 0) &&
    f.every((x) => isNum(x) && x >= 0) &&
    typeof s.label === "string" &&
    typeof s.size_definition === "string" &&
    isSource(s.source)
  );
}

const positiveValue = (p: unknown): boolean => isObj(p) && isNum(p.value_nm) && p.value_nm > 0;

/**
 * Accept artifacts/detection.json or GET /detection. Throws on a payload that is not the detection artifact;
 * drops individual series or points that could not be drawn honestly (bad arrays, non-positive sizes).
 */
export function normalizeDetection(raw: unknown): DetectionArtifact {
  if (!isObj(raw) || !Array.isArray(raw.smoke_bins) || !Array.isArray(raw.simulation) || !Array.isArray(raw.gaps)) {
    throw new Error("malformed detection payload");
  }
  const runs = raw.smoke_runs;
  const amc = raw.average_mass_comparison;
  if (!isObj(runs) || !Array.isArray(runs.points) || !isObj(amc) || !isObj(amc.smoke) || !isObj(amc.dust)) {
    throw new Error("malformed detection payload");
  }
  const smoke = amc.smoke as Record<string, unknown>;
  const dust = amc.dust as Record<string, unknown>;
  const gaps = (raw.gaps as unknown[]).filter(
    (g): g is DetectionGap => isObj(g) && typeof g.id === "string" && typeof g.text === "string",
  );
  // lunar_dust is always first (contract), whatever order the payload uses.
  gaps.sort((a, b) => Number(b.id === "lunar_dust") - Number(a.id === "lunar_dust"));
  return {
    ...(raw as unknown as DetectionArtifact),
    scope_note: typeof raw.scope_note === "string" ? raw.scope_note : "",
    generated_from: Array.isArray(raw.generated_from) ? (raw.generated_from as DetectionArtifact["generated_from"]) : [],
    size_definitions: isObj(raw.size_definitions) ? (raw.size_definitions as Record<string, SizeDefinition>) : {},
    gaps,
    smoke_bins: (raw.smoke_bins as unknown[]).filter((s): s is SmokeBinSeries => isObj(s) && isCurve(s) && typeof s.material === "string"),
    simulation: (raw.simulation as unknown[]).filter((s): s is SimSeries => isObj(s) && isCurve(s) && s.is_simulation === true),
    smoke_runs: {
      ...(runs as unknown as SmokeRuns),
      materials: Array.isArray(runs.materials) ? (runs.materials as string[]) : [],
      material_labels: isObj(runs.material_labels) ? (runs.material_labels as Record<string, string>) : {},
      points: (runs.points as unknown[]).filter(positiveValue) as SmokeRunPoint[],
      by_material: Array.isArray(runs.by_material) ? (runs.by_material as SmokeRunsByMaterial[]) : [],
    },
    average_mass_comparison: {
      ...(amc as unknown as AverageMassComparison),
      smoke: {
        ...(smoke as unknown as AverageMassComparison["smoke"]),
        points: (Array.isArray(smoke.points) ? smoke.points : []).filter(positiveValue) as AverageMassComparison["smoke"]["points"],
      },
      dust: {
        ...(dust as unknown as AverageMassComparison["dust"]),
        points: (Array.isArray(dust.points) ? dust.points : []).filter(positiveValue) as DustPoint[],
      },
    },
  };
}

// ------------------------------------------------------------------ chart helpers

/** Decade-aligned [lo, hi] that contains every positive value. */
export function logDomain(values: number[]): [number, number] {
  const v = values.filter((x) => isNum(x) && x > 0);
  if (!v.length) return [1, 10];
  const lo = 10 ** Math.floor(Math.log10(Math.min(...v)));
  let hi = 10 ** Math.ceil(Math.log10(Math.max(...v)));
  if (hi <= lo) hi = lo * 10;
  return [lo, hi];
}

/** Map a positive value onto [r0, r1] with a log10 scale over the domain. */
export function logScale([d0, d1]: [number, number], [r0, r1]: [number, number]) {
  const a = Math.log10(d0);
  const span = Math.log10(d1) - a || 1;
  return (v: number) => r0 + ((Math.log10(v) - a) / span) * (r1 - r0);
}

/** Powers of ten inside the domain (major ticks). */
export function logTicks([d0, d1]: [number, number]): number[] {
  const out: number[] = [];
  for (let e = Math.ceil(Math.log10(d0) - 1e-9); e <= Math.floor(Math.log10(d1) + 1e-9); e++) out.push(10 ** e);
  return out;
}

/** Tick label in nm: 10, 100, 1,000, 10,000 (whole numbers; sub-nm ticks keep their decimals). */
export function fmtTickNm(v: number): string {
  return v >= 1 ? Math.round(v).toLocaleString("en-US") : String(v);
}

/** "192 nm" / "1,716 nm" (3 significant figures, thousands separated). */
export function fmtNm(v: number): string {
  if (!isNum(v)) return "–";
  const s = Number(fmtSig(v, 3));
  return `${Number.isFinite(s) ? s.toLocaleString("en-US") : fmtSig(v, 3)} nm`;
}

/** Share 0..1 as a percent; tiny non-zero shares keep two significant figures instead of rounding to 0%. */
export function fmtShare(v: number): string {
  if (!isNum(v)) return "–";
  const p = v * 100;
  if (p === 0) return "0%";
  if (p < 1) return `${Number(p.toPrecision(2))}%`;
  return `${Number(p.toFixed(1))}%`;
}

export function sourceText(s: DetectionSource): string {
  const parts = [s.investigation_id, s.file];
  if (s.sheet) parts.push(`sheet “${s.sheet}”`);
  if (s.rows) parts.push(`rows ${s.rows}`);
  return parts.join(" · ");
}

/** Materials that have microscope size bins, in artifact order, with their display label. */
export function binMaterials(d: DetectionArtifact): { material: string; label: string }[] {
  const seen = new Map<string, string>();
  for (const s of d.smoke_bins) if (!seen.has(s.material)) seen.set(s.material, s.material_label || s.material);
  return [...seen].map(([material, label]) => ({ material, label }));
}

/** The series of one material and variant, falling back to the material's first series. */
export function pickBinSeries(d: DetectionArtifact, material: string, variant: "all" | "big_only"): SmokeBinSeries | null {
  const ofMat = d.smoke_bins.filter((s) => s.material === material);
  return ofMat.find((s) => s.variant === variant) ?? ofMat[0] ?? null;
}

/** Simulation curves of one case: the two base curves (Earth, microgravity), plus the variants when asked. */
export function simForCase(d: DetectionArtifact, kase: string, withVariants: boolean): SimSeries[] {
  return d.simulation
    .filter((s) => s.case === kase && (withVariants || s.variant === "base"))
    .sort((a, b) => Number(a.variant !== "base") - Number(b.variant !== "base") || a.gravity.localeCompare(b.gravity));
}

export function simCases(d: DetectionArtifact): { case: string; case_label: string }[] {
  const seen = new Map<string, string>();
  for (const s of d.simulation) if (!seen.has(s.case)) seen.set(s.case, s.case_label);
  return [...seen].map(([c, l]) => ({ case: c, case_label: l })).sort((a, b) => a.case.localeCompare(b.case));
}

/** Deterministic vertical offset in [-1, 1] so strip-chart dots of one row do not sit on top of each other. */
export function jitter(i: number): number {
  const x = Math.sin((i + 1) * 12.9898) * 43758.5453;
  return (x - Math.floor(x)) * 2 - 1;
}

/** True when any series label, id, material or material label mentions lunar (contract wording rule). */
export function mentionsLunar(d: DetectionArtifact): string[] {
  const out: string[] = [];
  const check = (where: string, ...vals: (string | undefined)[]) => {
    if (vals.some((v) => typeof v === "string" && /lunar/i.test(v))) out.push(where);
  };
  d.smoke_bins.forEach((s) => check(s.id, s.id, s.label, s.material, s.material_label));
  d.simulation.forEach((s) => check(s.id, s.id, s.label));
  check(d.smoke_runs.id, d.smoke_runs.id, d.smoke_runs.label, ...Object.values(d.smoke_runs.material_labels));
  const { smoke, dust } = d.average_mass_comparison;
  check(smoke.id, smoke.id, smoke.label);
  check(dust.id, dust.id, dust.label);
  return out;
}
