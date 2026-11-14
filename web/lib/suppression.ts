/**
 * R2 suppression calculator helpers (plan/13-round-2-features.md §R2, plan/contracts.md R2 addendum).
 *
 * Pure functions only: normalizing the engine curve and DE's empirical reference, splitting a curve into
 * applicable segments (never interpolating across a non-applicable point), and building the plain-language
 * labels from the numbers in the data. Nothing here computes a model number.
 */
import type {
  DiluentId,
  DiluentInfo,
  SuppressionCurve,
  SuppressionMetricPoint,
  SuppressionPoint,
  SuppressionReference,
  SuppressionReferenceBin,
  SuppressionTested,
} from "./types";

export const DILUENT_IDS: readonly DiluentId[] = ["co2", "he"];

/** Static mirror of engine/suppression.py DILUENTS (GET /suppression/diluents). */
export const STATIC_DILUENTS: Record<DiluentId, DiluentInfo> = {
  co2: { label: "Carbon dioxide (CO2)", max: 0.7 },
  he: { label: "Helium", max: 0.45 },
};

/** Short name used inside sentences. */
export const DILUENT_SHORT: Record<DiluentId, string> = { co2: "CO₂", he: "helium" };

/** Contract safety note (plan/13 §R2); the page prefers the `safety_note` the engine returns. */
export const DEFAULT_SAFETY_NOTE =
  "CO₂ at fire-suppression concentrations is dangerous to breathe. Real spacecraft use CO₂ or water-mist extinguishers locally, not cabin flooding. This tool studies how dilution affects flames in the data; it is not an operating procedure.";

export function parseDiluent(v: string | null | undefined): DiluentId {
  return v === "he" ? "he" : "co2";
}

function isNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function numOrNull(v: unknown): number | null {
  return isNum(v) ? v : null;
}

function pair(v: unknown): [number, number] | null {
  return Array.isArray(v) && v.length >= 2 && isNum(v[0]) && isNum(v[1]) ? [v[0], v[1]] : null;
}

// ------------------------------------------------------------------ curve

function normMetric(raw: unknown): SuppressionMetricPoint {
  const o = (raw ?? {}) as Record<string, unknown>;
  const estimate = numOrNull(o.estimate);
  const band90 = pair(o.band90);
  // A point is applicable only when the engine says so; a missing flag means "not applicable" (honesty gate).
  return {
    applicable: o.applicable === true,
    estimate,
    band90,
    reason: typeof o.reason === "string" ? o.reason : null,
  };
}

/** Accept the engine curve (POST /suppression or artifacts/suppression/{preset}_{diluent}.json). */
export function normalizeSuppression(raw: unknown, fallbackDiluent: DiluentId = "co2"): SuppressionCurve {
  const o = (raw ?? {}) as Record<string, unknown>;
  const diluent = o.diluent === "he" || o.diluent === "co2" ? o.diluent : fallbackDiluent;
  const points: SuppressionPoint[] = (Array.isArray(o.points) ? o.points : [])
    .filter((p): p is Record<string, unknown> => !!p && typeof p === "object" && isNum((p as Record<string, unknown>).fraction))
    .map((p) => ({ fraction: p.fraction as number, M1: normMetric(p.M1), M2: normMetric(p.M2) }))
    .sort((a, b) => a.fraction - b.fraction);
  const doseRaw = o.dose_for_p90 as Record<string, unknown> | null | undefined;
  const dose =
    doseRaw && isNum(doseRaw.fraction)
      ? { fraction: doseRaw.fraction, metric: String(doseRaw.metric ?? "M1"), note: typeof doseRaw.note === "string" ? doseRaw.note : null }
      : null;
  const tested: SuppressionTested[] = (Array.isArray(o.tested) ? o.tested : [])
    .filter((t): t is Record<string, unknown> => !!t && typeof t === "object")
    .filter((t) => isNum(t.o2) && isNum(t.fraction))
    .map((t) => ({
      o2: t.o2 as number,
      p_atm: numOrNull(t.p_atm) ?? NaN,
      fraction: t.fraction as number,
      n: numOrNull(t.n) ?? 1,
      extinctions: numOrNull(t.extinctions),
    }));
  const h = o.habitat as Record<string, unknown> | undefined;
  return {
    diluent,
    label: typeof o.label === "string" ? o.label : STATIC_DILUENTS[diluent].label,
    habitat:
      h && isNum(h.o2)
        ? {
            g_m_s2: Number(h.g_m_s2),
            p_psia: Number(h.p_psia),
            o2: h.o2,
            u_cm_s: Number(h.u_cm_s),
            L_mm: Number(h.L_mm),
          }
        : null,
    points,
    dose_for_p90: dose,
    tested,
    tested_o2_range: pair(o.tested_o2_range),
    gate_note: typeof o.gate_note === "string" ? o.gate_note : null,
    safety_note: typeof o.safety_note === "string" && o.safety_note.trim() ? o.safety_note : null,
    model_version: typeof o.model_version === "string" ? o.model_version : null,
  };
}

// ------------------------------------------------------------------ gap logic

export interface CurveVertex {
  fraction: number;
  estimate: number;
  band: [number, number] | null;
}

export interface CurveLayout {
  /** Runs of consecutive applicable points with an estimate; each is drawn on its own (a gap breaks the line). */
  segments: CurveVertex[][];
  /** Contiguous non-applicable stretches [from, to] in fraction units, drawn hatched as "no evidence". */
  gaps: { from: number; to: number; reason: string | null }[];
}

/** A point contributes to the curve only if the gate allows it and the engine gave a number. */
export function isDrawable(m: SuppressionMetricPoint): boolean {
  return m.applicable && isNum(m.estimate);
}

/**
 * Split a metric's points into drawable segments and no-evidence gaps. A gap spans half-way to each neighbour
 * so it visibly covers the untested point; segments never join across it (no interpolation).
 */
export function layoutCurve(points: SuppressionPoint[], metric: "M1" | "M2"): CurveLayout {
  const pts = [...points].sort((a, b) => a.fraction - b.fraction);
  const segments: CurveVertex[][] = [];
  const gaps: CurveLayout["gaps"] = [];
  let seg: CurveVertex[] = [];
  let gapStart: number | null = null;
  let gapReason: string | null = null;
  const lo = pts.length ? pts[0].fraction : 0;
  const hi = pts.length ? pts[pts.length - 1].fraction : 0;
  const mid = (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0) return lo;
    if (j >= pts.length) return hi;
    return (pts[i].fraction + pts[j].fraction) / 2;
  };
  pts.forEach((p, i) => {
    const m = p[metric];
    if (isDrawable(m)) {
      if (gapStart !== null) {
        gaps.push({ from: gapStart, to: mid(i - 1, 1), reason: gapReason });
        gapStart = null;
        gapReason = null;
      }
      seg.push({ fraction: p.fraction, estimate: m.estimate as number, band: m.band90 });
    } else {
      if (seg.length) {
        segments.push(seg);
        seg = [];
      }
      if (gapStart === null) {
        gapStart = mid(i, -1);
        gapReason = m.reason;
      }
    }
  });
  if (seg.length) segments.push(seg);
  if (gapStart !== null) gaps.push({ from: gapStart, to: hi, reason: gapReason });
  return { segments, gaps };
}

// ------------------------------------------------------------------ labels

/** Fraction -> "12%" (1 decimal below 10% unless whole). */
export function fmtPct(fraction: number): string {
  const v = fraction * 100;
  if (Math.abs(v - Math.round(v)) < 1e-6 || v >= 10) return `${Math.round(v)}%`;
  return `${v.toFixed(1)}%`;
}

export const DOSE_NOT_REACHED = "90% not reached inside tested conditions";

/** Dose marker text: "~20% CO₂ reaches 90%", "already ≥90% with no CO₂ added", or the not-reached text. */
export function doseLabel(dose: SuppressionCurve["dose_for_p90"], diluent: DiluentId): string {
  if (!dose || !isNum(dose.fraction)) return DOSE_NOT_REACHED;
  if (dose.fraction <= 0) return `already ≥90% with no ${DILUENT_SHORT[diluent]} added`;
  return `~${fmtPct(dose.fraction)} ${DILUENT_SHORT[diluent]} reaches 90%`;
}

export function countApplicable(c: SuppressionCurve, metric: "M1" | "M2", dilutedOnly = true): { applicable: number; total: number } {
  const pts = c.points.filter((p) => !dilutedOnly || p.fraction > 0);
  return { applicable: pts.filter((p) => isDrawable(p[metric])).length, total: pts.length };
}

/** O2 range of the diluted FLEX tests: the engine's tested_o2_range, else derived from `tested`. */
export function testedO2Range(c: SuppressionCurve): [number, number] | null {
  if (c.tested_o2_range) return c.tested_o2_range;
  if (!c.tested.length) return null;
  const o2s = c.tested.map((t) => t.o2);
  return [Math.min(...o2s), Math.max(...o2s)];
}

/** One plain sentence built only from the curve's own numbers. */
export function summaryLine(c: SuppressionCurve, habitatLabel: string, habitatO2: number): string {
  const name = DILUENT_SHORT[c.diluent];
  const where = `At ${habitatLabel} (${fmtPct(habitatO2)} O₂)`;
  const { applicable, total } = countApplicable(c, "M1");
  const range = testedO2Range(c);
  const rangeText = range ? `FLEX tested ${name} dilution only between ${fmtPct(range[0])} and ${fmtPct(range[1])} O₂` : `FLEX has no ${name} dilution tests to compare with`;
  if (total > 0 && applicable === 0) {
    return `${where} there is no evidence for any ${name} dilution: ${rangeText}.`;
  }
  if (c.dose_for_p90 && c.dose_for_p90.fraction <= 0) {
    const est = c.points.find((p) => p.fraction === 0 && isDrawable(p.M1))?.M1.estimate;
    return `${where}, the model already gives ${est != null ? `a ${Math.round(est * 100)}%` : "at least a 90%"} chance that a droplet flame goes out on its own before burning out with no ${name} added (model M1); the curve shows how it changes as ${name} is added, inside tested conditions only.`;
  }
  if (c.dose_for_p90) {
    const partial = applicable < total ? ` Some higher fractions are outside the tested conditions and show no number.` : "";
    return `${where}, about ${fmtPct(c.dose_for_p90.fraction)} ${name} gives a 90% chance that a droplet flame goes out on its own before burning out (model M1, inside tested conditions).${partial}`;
  }
  const maxTested = c.points.filter((p) => isDrawable(p.M1)).map((p) => p.fraction);
  const upTo = maxTested.length ? ` up to ${fmtPct(Math.max(...maxTested))} ${name}` : "";
  return `${where}, the chance of self-extinction stays below 90% everywhere the data reaches${upTo}; a 90% dose is not reached inside tested conditions.`;
}

// ------------------------------------------------------------------ empirical reference (DE)

const BAND_RE = /^\s*(?:(<=|≤|<|>=|≥|>)\s*)?([0-9.]+)\s*%?\s*(?:[-–]|to)?\s*([0-9.]+)?\s*%?\s*$/;

function scale(v: number): number {
  return v > 1 ? v / 100 : v;
}

/** O2 band ids and labels: "le_0.17", "gt_0.22", "0.17_0.22", "0.17 < O2 <= 0.22", "O2 <= 0.17", "O2 > 0.22". */
export function parseBand(v: unknown): [number, number] | null {
  if (typeof v !== "string") return null;
  let m = /^le_([0-9.]+)$/.exec(v);
  if (m) return [0, scale(Number(m[1]))];
  m = /^gt_([0-9.]+)$/.exec(v);
  if (m) return [scale(Number(m[1])), 1];
  m = /^([0-9.]+)_([0-9.]+)$/.exec(v);
  if (m) return [scale(Number(m[1])), scale(Number(m[2]))];
  m = /^\s*([0-9.]+)\s*<=?\s*O2\s*<=?\s*([0-9.]+)\s*$/i.exec(v);
  if (m) return [scale(Number(m[1])), scale(Number(m[2]))];
  m = /^\s*O2\s*(<=?|>=?)\s*([0-9.]+)\s*$/i.exec(v);
  if (m) return m[1].startsWith("<") ? [0, scale(Number(m[2]))] : [scale(Number(m[2])), 1];
  return null;
}

/** "0.17-0.22", "<=0.17", ">0.22", [0.17, 0.22], {lo, hi} -> [lo, hi]. */
export function parseRange(v: unknown): [number, number] | null {
  if (isNum(v)) return [v, v];
  const p = pair(v);
  if (p) return [scale(p[0]), scale(p[1])];
  if (Array.isArray(v) && v.length >= 2) {
    const lo = isNum(v[0]) ? v[0] : 0;
    const hi = isNum(v[1]) ? v[1] : 1;
    return [scale(lo), scale(hi)];
  }
  if (v && typeof v === "object") {
    const o = v as Record<string, unknown>;
    const lo = numOrNull(o.lo ?? o.min ?? o.low ?? o.from);
    const hi = numOrNull(o.hi ?? o.max ?? o.high ?? o.to);
    if (lo !== null || hi !== null) return [scale(lo ?? 0), scale(hi ?? 1)];
    return null;
  }
  if (typeof v !== "string") return null;
  const m = BAND_RE.exec(v);
  if (!m) return null;
  const a = scale(Number(m[2]));
  if (m[3] !== undefined) return [a, scale(Number(m[3]))];
  if (m[1] && /<|≤/.test(m[1])) return [0, a];
  if (m[1] && />|≥/.test(m[1])) return [a, 1];
  return [a, a];
}

/** Wilson score interval at 90% (z = 1.645) for k successes in n trials. */
export function wilson90(k: number, n: number): [number, number] | null {
  if (!(n > 0) || k < 0 || k > n) return null;
  const z = 1.645;
  const p = k / n;
  const d = 1 + (z * z) / n;
  const c = (p + (z * z) / (2 * n)) / d;
  const h = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / d;
  return [Math.max(0, c - h), Math.min(1, c + h)];
}

function o2BandLabel(b: [number, number]): string {
  if (b[0] <= 0) return `≤${fmtPct(b[1])} O₂`;
  if (b[1] >= 1) return `>${fmtPct(b[0])} O₂`;
  return `${fmtPct(b[0])}–${fmtPct(b[1])} O₂`;
}

const FRACTION_KEYS = ["fraction_bin", "fraction_range", "fraction", "bin", "diluent_bin", "diluent_fraction", "range", "x"];
// Band definitions only: a bin's observed "o2_range" is narrower than its band and must not decide membership.
const O2_KEYS = ["o2_band", "o2_bin", "band_id", "band"];
const FUELS = /heptane|methanol|ethanol|decane|dodecane|propanol|hexadecane|fuel/i;

function rowFrom(o: Record<string, unknown>, ctx: { diluent?: DiluentId; fuel?: string; o2?: [number, number]; fraction?: [number, number] }): SuppressionReferenceBin | null {
  const n = numOrNull(o.n ?? o.count ?? o.n_tests);
  if (n === null) return null;
  const diluent = o.diluent === "he" || o.diluent === "co2" ? o.diluent : ctx.diluent;
  if (!diluent) return null;
  let fraction: [number, number] | null = null;
  for (const k of FRACTION_KEYS) {
    if (k in o) {
      fraction = parseRange(o[k]);
      if (fraction) break;
    }
  }
  if (!fraction) {
    const lo = numOrNull(o.fraction_lo ?? o.fraction_min ?? o.lo);
    const hi = numOrNull(o.fraction_hi ?? o.fraction_max ?? o.hi);
    if (lo !== null && hi !== null) fraction = [lo, hi];
  }
  fraction = fraction ?? ctx.fraction ?? null;
  let o2: [number, number] | null = null;
  for (const k of O2_KEYS) {
    if (k in o) {
      o2 = parseBand(o[k]) ?? parseRange(o[k]);
      if (o2) break;
    }
  }
  o2 = o2 ?? ctx.o2 ?? null;
  if (!fraction || !o2) return null;
  const extinctions = numOrNull(o.extinctions);
  const rate = numOrNull(o.extinction_rate) ?? (extinctions !== null && n > 0 ? extinctions / n : null);
  const given = pair(o.interval90 ?? o.interval ?? o.ci90 ?? o.ci ?? o.ci95 ?? o.extinction_rate_ci ?? o.rate_interval ?? o.wilson);
  const interval = given ?? (extinctions !== null ? wilson90(extinctions, n) : null);
  const ids = o.record_ids ?? o.records ?? o.ids;
  return {
    diluent,
    fuel: typeof o.fuel === "string" ? o.fuel : (ctx.fuel ?? null),
    fraction,
    o2_band: o2,
    o2_band_label: o2BandLabel(o2),
    n,
    extinctions,
    completions: numOrNull(o.completions),
    disruptions: numOrNull(o.disruptions),
    extinction_rate: rate,
    interval,
    interval_source: given ? "artifact" : interval ? "wilson90" : null,
    record_ids: Array.isArray(ids) ? ids.map(String) : [],
  };
}

/**
 * Flatten artifacts/suppression_reference.json whatever its nesting (by diluent, fuel, O2 band, fraction bin):
 * any object with a count `n` and enough context for a diluent, a fraction bin and an O2 band becomes a bin.
 */
export function normalizeReference(raw: unknown): SuppressionReference {
  const bins: SuppressionReferenceBin[] = [];
  const walk = (v: unknown, ctx: Parameters<typeof rowFrom>[1], key: string | null, depth: number) => {
    if (depth > 8 || v === null || typeof v !== "object") return;
    const next = { ...ctx };
    if (key) {
      if (key === "co2" || key === "he") next.diluent = key;
      else if (FUELS.test(key) && !/^fuels?$/i.test(key)) next.fuel = key;
      else if (parseBand(key)) next.o2 = parseBand(key) as [number, number];
      else if (parseRange(key) && /[0-9]/.test(key)) {
        const r = parseRange(key) as [number, number];
        // Keys under an O2 grouping are O2 bands; others are fraction bins.
        if (/o2/i.test(key) || ctx.fraction) next.o2 = r;
        else next.fraction = r;
      }
    }
    if (Array.isArray(v)) {
      v.forEach((x) => walk(x, next, null, depth + 1));
      return;
    }
    const o = v as Record<string, unknown>;
    if (o.diluent === "co2" || o.diluent === "he") next.diluent = o.diluent;
    if (typeof o.fuel === "string") next.fuel = o.fuel;
    const band = parseBand(o.o2_band) ?? parseBand(o.band_id);
    if (band) next.o2 = band;
    const row = rowFrom(o, next);
    if (row) {
      bins.push(row);
      return;
    }
    Object.entries(o).forEach(([k, x]) => {
      if (x && typeof x === "object") walk(x, next, k, depth + 1);
    });
  };
  const o = (raw ?? {}) as Record<string, unknown>;
  // DE's artifact keeps the bins under `tables`; skip its `trend` summary (no counts per bin).
  walk(o.tables && typeof o.tables === "object" ? o.tables : raw, {}, null, 0);
  return {
    bins,
    generated_at: typeof o.generated_at === "string" ? o.generated_at : undefined,
    note: typeof o.note === "string" ? o.note : Array.isArray(o.notes) && typeof o.notes[0] === "string" ? o.notes[0] : undefined,
  };
}

/**
 * Reference bins for this diluent in the habitat's O2 band. Returns none when the habitat O2 lies above every
 * diluted FLEX test (e.g. 34% O2): an open-ended ">22%" band must not stand in for an untested atmosphere.
 */
export function referenceFor(ref: SuppressionReference | null, diluent: DiluentId, o2: number, testedRange: [number, number] | null): SuppressionReferenceBin[] {
  if (!ref) return [];
  if (testedRange && (o2 > testedRange[1] + 0.01 || o2 < testedRange[0] - 0.01)) return [];
  return ref.bins
    .filter((b) => b.diluent === diluent && o2 >= b.o2_band[0] - 1e-9 && o2 <= b.o2_band[1] + 1e-9)
    .filter((b) => isNum(b.extinction_rate))
    .sort((a, b) => a.fraction[0] - b.fraction[0] || String(a.fuel).localeCompare(String(b.fuel)));
}

/** x position of a bin's dot (bin midpoint). */
export function binMid(b: SuppressionReferenceBin): number {
  return (b.fraction[0] + b.fraction[1]) / 2;
}
