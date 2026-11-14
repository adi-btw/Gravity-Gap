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
