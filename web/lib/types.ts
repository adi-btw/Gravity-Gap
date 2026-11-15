/** Shapes from plan/contracts.md (phase 1 API + phase 2 addendum). Extra fields are tolerated. */

export type Range = [number, number] | null;

export interface Publication {
  doi: string | null;
  title: string | null;
}

export interface Lineage {
  reuses?: string[];
  evidence?: string;
  missing_from_catalog?: string[];
}

export interface CatalogRecord {
  id: string;
  acronym: string | null;
  title: string | null;
  doi: string | null;
  platform: string | null;
  hardware: string | null;
  fuel_phase: string | null;
  gravity_levels: string[];
  ground_reference: boolean;
  ground_reference_note?: string | null;
  conditions: { o2: Range; pressure_atm: Range; flow_cm_s: Range } | null;
  n_tests: number;
  outcomes_available: boolean;
  hazard_pillars: string[];
  pillar_evidence?: Record<string, string[]>;
  /** Catalog 1.2.0 (R3): which data files back a pillar, e.g. detection for PSI-101/102/47/115. */
  pillar_data?: { detection?: { holds: string; files: string[]; artifact: string | null } };
  objective: string | null;
  hypothesis: string | null;
  impacts: string | null;
  publications: Publication[];
  related: string[];
  reanalyzed_by?: string[];
  lineage?: Lineage | null;
  is_combustion: boolean;
  is_combustion_basis?: string;
  research_area?: string;
  sub_research_area?: string;
}

export interface RankParts {
  atmosphere: number;
  pillar: number;
  fuel_realism: number;
  outcomes: number;
  n_tests: number;
  [k: string]: number;
}

export interface RankItem {
  id: string;
  acronym: string | null;
  score: number;
  parts: RankParts;
  atmosphere_basis?: string;
  regime_fit_basis?: string;
}

export type RankWeights = Record<"atmosphere" | "pillar" | "fuel_realism" | "outcomes" | "n_tests" | "regime_fit", number>;

/** Mirrors engine/rank.py DEFAULT_WEIGHTS (DE added regime_fit in phase 2). */
export const DEFAULT_WEIGHTS: RankWeights = {
  atmosphere: 0.3,
  pillar: 0.15,
  fuel_realism: 0.15,
  outcomes: 0.15,
  n_tests: 0.1,
  regime_fit: 0.15,
};

export type MetricKind = "probability" | "quantity" | "category";

export interface MetricInfo {
  id: string;
  label: string;
  unit: string | null;
  kind: MetricKind;
  data?: string;
  flow_dependent?: boolean;
}

export type Band = [number, number] | [string, string] | null;
export type Estimate = number | string | null;

export interface RefPoint {
  estimate: Estimate;
  band90: Band;
}

export interface EvidenceRow {
  record_id: string;
  investigation_id: string;
  distance?: number | null;
}

export interface SensitivityRow {
  param: string;
  low: Estimate;
  high: Estimate;
  /** Value at the habitat setting; rows differ in what they measure (see quantity). */
  baseline?: Estimate;
  /** "estimate" (metric value) or "band_width" (width of the 90% band). */
  quantity?: "estimate" | "band_width" | string;
  input_low?: number;
  input_high?: number;
}

export interface BoundsResult {
  preset_id?: string;
  habitat?: Record<string, number>;
  metric: string;
  label: string;
  unit: string | null;
  kind: MetricKind;
  applicable: boolean;
  reason: string | null;
  estimate: Estimate;
  band90: Band;
  ref_0g: RefPoint | null;
  ref_1g: RefPoint | null;
  regime_fractions: { forced: number; mixed: number; buoyant: number } | null;
  u_eff_summary: { p05: number; p50: number; p95: number } | null;
  nonmonotonic_flag: boolean;
  nonmonotonic_note: string | null;
  transfer: { basis: string; confidence: "high" | "medium" | "low" } | null;
  evidence: EvidenceRow[];
  sensitivity: SensitivityRow[];
  n_train: number;
  model_version: string;
  /** S3 band-width breakdown (optional; raw, see lib/uncertainty.ts normalizeDrivers). */
  drivers?: unknown;
}

export interface PlannerItem {
  rank: number;
  g_m_s2: number;
  p_psia: number;
  o2: number;
  u_cm_s: number;
  metric: string;
  score: number;
  parts: Record<string, number>;
  rationale: string;
  extends: string[];
  base_score?: number;
}

export interface PlannerArtifact {
  tests: PlannerItem[];
  design_implications: string[];
  method?: string;
  version?: string;
  generated_at?: string;
  habitat_targets?: { p_psia: number; o2: number; weight: number; label: string }[];
}

export interface AskAnswer {
  answer_markdown: string;
  citations: string[];
  numbers_used: (number | string)[];
  validated: boolean;
  mode: "claude" | "cached" | "template" | string;
}

export interface TestsPage {
  total: number;
  limit: number;
  offset: number;
  rows: Record<string, unknown>[];
}

// ------------------------------------------------------------------ R1 real-fire replay (contracts.md, R1 addendum)

export type IncidentId = "apollo1" | "mir1997" | "artemis2" | "apollo13" | (string & {});

export interface IncidentSource {
  /** Which field the quote supports: p_psia | o2 | g_m_s2 | summary | date. */
  field: string;
  /** Absent for non-web citations (e.g. the challenge brief); then `source` names the document. */
  url?: string | null;
  source?: string | null;
  quote: string;
}

export interface IncidentMetric {
  applicable: boolean;
  estimate: Estimate;
  band90: Band;
  reason: string | null;
  transfer_confidence?: string | null;
}

export interface IncidentCoverage {
  covered: boolean;
  nearest_distance: number | null;
}

export interface Incident {
  id: IncidentId;
  name: string;
  date: string;
  phase: string;
  in_scope: boolean;
  scope_note: string | null;
  g_m_s2: number | null;
  p_psia: number | null;
  o2: number | null;
  u_cm_s: number | null;
  L_mm: number | null;
  /** Habitat fields that are engineering assumptions rather than sourced values. */
  assumed: string[];
  /** Plain-language explanation of the assumed values (may be absent). */
  assumed_note?: string | null;
  summary: string;
  sources: IncidentSource[];
  physics?: Record<string, unknown> | null;
  regime_fractions?: { forced: number; mixed: number; buoyant: number } | null;
  metrics?: Record<string, IncidentMetric> | null;
  coverage?: Record<string, IncidentCoverage> | null;
  findings?: string[];
}

export interface IncidentsArtifact {
  generated_at?: string;
  engine_version?: string;
  incidents: Incident[];
}

// ------------------------------------------------------------------ R2 suppression (plan/contracts.md R2 addendum)

export type DiluentId = "co2" | "he";

export interface DiluentInfo {
  label: string;
  /** Highest fraction the engine sweeps (0.70 CO2, 0.45 He). */
  max: number;
}

export interface SuppressionMetricPoint {
  applicable: boolean;
  estimate: number | null;
  band90: [number, number] | null;
  reason: string | null;
}

export interface SuppressionPoint {
  /** Diluent mole fraction (replaces nitrogen; O2 and pressure held at the habitat's). */
  fraction: number;
  M1: SuppressionMetricPoint;
  M2: SuppressionMetricPoint;
}

/** One aggregated FLEX training condition with this diluent > 0. */
export interface SuppressionTested {
  o2: number;
  p_atm: number;
  fraction: number;
  n: number;
  extinctions: number | null;
}

export interface SuppressionCurve {
  diluent: DiluentId;
  label: string;
  habitat: { g_m_s2: number; p_psia: number; o2: number; u_cm_s: number; L_mm: number } | null;
  points: SuppressionPoint[];
  /** Smallest applicable fraction whose M1 estimate >= 0.9, or null when not reached inside tested conditions. */
  dose_for_p90: { fraction: number; metric: string; note?: string | null } | null;
  tested: SuppressionTested[];
  tested_o2_range: [number, number] | null;
  gate_note: string | null;
  safety_note: string | null;
  model_version: string | null;
}

/** One empirical FLEX outcome bin from artifacts/suppression_reference.json (flattened). */
export interface SuppressionReferenceBin {
  diluent: DiluentId;
  fuel: string | null;
  /** Diluent fraction bin [lo, hi]; [0, 0] for the undiluted bin. */
  fraction: [number, number];
  /** O2 band [lo, hi] (open ends as 0 / 1). */
  o2_band: [number, number];
  o2_band_label: string;
  n: number;
  extinctions: number | null;
  completions: number | null;
  disruptions: number | null;
  extinction_rate: number | null;
  /** Interval on the extinction rate: from the artifact when given, else a Wilson 90% interval from n and extinctions. */
  interval: [number, number] | null;
  interval_source: "artifact" | "wilson90" | null;
  record_ids: string[];
}

export interface SuppressionReference {
  generated_at?: string;
  bins: SuppressionReferenceBin[];
  note?: string;
}
