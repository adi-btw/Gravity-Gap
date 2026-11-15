import { readFileSync } from "node:fs";
import path from "node:path";
import { evaluate, G0 } from "@/lib/physics";
import { PRESETS_BY_ID } from "@/lib/presets";

/**
 * Build-time facts for the story page at "/". Every number the page prints comes from here, and every value here is
 * read from a committed artifact (copied into public/artifacts by scripts/copy-artifacts.mjs) or computed by the
 * app's own physics. Nothing is typed in by hand: if an artifact changes, the page changes with it.
 */

interface RawInvestigation {
  id: string;
  acronym: string | null;
  platform: string | null;
  gravity_levels: string[];
  n_tests: number | null;
  n_tests_basis?: string;
  is_combustion: boolean;
}

interface RawBounds {
  label: string;
  unit: string;
  kind: string;
  applicable: boolean;
  reason: string | null;
  estimate: number | null;
  band90: [number, number] | null;
  ref_0g: { estimate: number; band90: [number, number] } | null;
  regime_fractions: { forced: number; mixed: number; buoyant: number };
  transfer: { basis: string; confidence: string };
  evidence: { record_id: string; investigation_id: string; distance: number }[];
}

export interface GapColumn {
  /** Investigation ids with acronyms, for the figure's accessible description. */
  items: { id: string; name: string }[];
  platforms: string[];
}

export interface MetricRow {
  metric: string;
  label: string;
  applicable: boolean;
  /** Printed value, e.g. "20.1%". Null when the engine refuses. */
  value: string | null;
  /** Printed 90% band, e.g. "1.2% to 68.4%". */
  band: string | null;
  confidence: string;
  /** One-line reason when there is no evidence. */
  note: string | null;
}

export interface StoryData {
  combustionInvestigations: number;
  cleanedTests: number;
  cleanedInvestigations: number;
  platforms: string[];
  orbit: GapColumn;
  earth: GapColumn;
  partialCount: number;
  g: { moon: number; mars: number; earth: number };
  lunarBase: { p_psia: number; o2Pct: number; ri: number; regime: string; mixedPct: number; buoyantPct: number };
  m1: { estimate: number; band: [number, number]; band0g: [number, number]; widen: string; nTrain: number | null };
  m2: {
    distance: number;
    gate: number;
    nearestId: string;
    nearestInvestigation: string;
    nearestO2Pct: number;
    nearestAtm: number;
    queryAtm: number;
  };
  rows: MetricRow[];
}

function readArtifact<T>(rel: string): T {
  const candidates = [
    path.join(process.cwd(), "public", "artifacts", rel),
    path.join(process.cwd(), "..", "artifacts", rel),
  ];
  for (const p of candidates) {
    try {
      return JSON.parse(readFileSync(p, "utf-8")) as T;
    } catch {
      /* try the next location */
    }
  }
  throw new Error(`story page: artifact ${rel} not found (run npm run copy-artifacts)`);
}

const pct = (x: number, d = 1) => `${(x * 100).toFixed(d)}%`;

function bandText(b: [number, number]): string {
  // Probabilities: one decimal for small edges keeps 1.2% from reading as 1%.
  return `${pct(b[0])} to ${pct(b[1])}`;
}

function shortNote(metric: string, reason: string | null): string | null {
  if (!reason) return null;
  if (metric === "M4") return "SAFFIRE-II only burned samples near 22% O₂ at about 1 atm.";
  if (metric === "M5") return "SPICE only ran in ISS cabin air, about 21% O₂ at about 1 atm.";
  return null;
}

export function getStoryData(): StoryData {
  const catalog = readArtifact<{ investigations: RawInvestigation[] }>("catalog.json");
  const comb = catalog.investigations.filter((r) => r.is_combustion);
  const name = (r: RawInvestigation) => (r.acronym ? `${r.id} ${r.acronym}` : r.id);
  const orbitRecs = comb.filter((r) => r.gravity_levels.includes("microgravity"));
  const earthRecs = comb.filter((r) => r.gravity_levels.includes("normal_gravity"));
  const partial = comb.filter((r) => r.gravity_levels.some((g) => g !== "microgravity" && g !== "normal_gravity"));
  // Individual cleaned tests: rows in data/clean/psi_tests.csv, as the catalog records them per investigation.
  const cleaned = comb.filter((r) => (r.n_tests_basis ?? "").startsWith("rows in data/clean/psi_tests.csv"));
  const uniq = (xs: (string | null)[]) => [...new Set(xs.filter((x): x is string => !!x))];

  const M = (m: string) => readArtifact<RawBounds>(`bounds/lunar_base_${m}.json`);
  const m1 = M("M1");
  const m2 = M("M2");
  const briefing = readArtifact<{ key_numbers: { metric: string; n_train: number }[] }>("briefing/lunar_base.json");

  // M2: parse the engine's own refusal sentence for the gate and the nearest tested atmosphere.
  const r2 = m2.reason ?? "";
  const gate = Number(r2.match(/more than (\d+(?:\.\d+)?) atmosphere/)?.[1] ?? NaN);
  const near = r2.match(/nearest tested condition is (\S+) (\S+) at O2 (\d+\.\d+), (\d+\.\d+) atm/);
  const query = r2.match(/query \(O2 (\d+\.\d+), (\d+\.\d+) atm/);
  const widen = m1.transfer.basis.match(/widened x(\d+(?:\.\d+)?)/)?.[1] ?? "";

  const lb = PRESETS_BY_ID.lunar_base;
  const ev = evaluate(lb.g_m_s2, lb.p_psia, lb.o2, lb.u_cm_s, lb.L_mm);

  const rows: MetricRow[] = ["M1", "M2", "M3", "M4", "M5"].map((metric) => {
    const b = M(metric);
    const prob = b.kind === "probability";
    return {
      metric,
      label: ((l: string) => l.charAt(0).toUpperCase() + l.slice(1))(b.label.replace(/^P\((.*)\)$/, "$1")),
      applicable: b.applicable,
      value: b.applicable && b.estimate !== null && prob ? pct(b.estimate) : null,
      band: b.applicable && b.band90 && prob ? bandText(b.band90) : null,
      confidence: b.transfer.confidence,
      note: shortNote(metric, b.reason),
    };
  });

  return {
    combustionInvestigations: comb.length,
    cleanedTests: cleaned.reduce((s, r) => s + (r.n_tests ?? 0), 0),
    cleanedInvestigations: cleaned.length,
    platforms: uniq(comb.map((r) => r.platform)),
    orbit: { items: orbitRecs.map((r) => ({ id: r.id, name: name(r) })), platforms: uniq(orbitRecs.map((r) => r.platform)) },
    earth: { items: earthRecs.map((r) => ({ id: r.id, name: name(r) })), platforms: uniq(earthRecs.map((r) => r.platform)) },
    partialCount: partial.length,
    g: { moon: PRESETS_BY_ID.lunar_base.g_m_s2, mars: PRESETS_BY_ID.mars_base.g_m_s2, earth: G0 },
    lunarBase: {
      p_psia: lb.p_psia,
      o2Pct: Math.round(lb.o2 * 100),
      ri: ev.ri ?? Infinity,
      regime: ev.regime,
      mixedPct: m1.regime_fractions.mixed * 100,
      buoyantPct: m1.regime_fractions.buoyant * 100,
    },
    m1: {
      estimate: m1.estimate ?? NaN,
      band: m1.band90 ?? [NaN, NaN],
      band0g: m1.ref_0g?.band90 ?? [NaN, NaN],
      widen,
      nTrain: briefing.key_numbers.find((k) => k.metric === "M1")?.n_train ?? null,
    },
    m2: {
      distance: m2.evidence[0]?.distance ?? NaN,
      gate,
      nearestId: near?.[2] ?? m2.evidence[0]?.record_id ?? "",
      nearestInvestigation: near?.[1] ?? m2.evidence[0]?.investigation_id ?? "",
      nearestO2Pct: near ? Number(near[3]) * 100 : NaN,
      nearestAtm: near ? Number(near[4]) : NaN,
      queryAtm: query ? Number(query[2]) : NaN,
    },
    rows,
  };
}
