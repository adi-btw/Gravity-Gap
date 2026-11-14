/**
 * Data layer (plan R4/R13). Every call tries the live API at NEXT_PUBLIC_API_URL with a short timeout and,
 * when the API is unreachable, falls back to the static artifacts copied into /public/artifacts at build time
 * (scripts/copy-artifacts.mjs). Results carry `source` so pages can show an "offline data" chip.
 *
 * Offline never invents numbers: bounds come only from the precomputed preset artifacts, so a habitat that
 * matches no preset gets OfflineUnavailableError ("live API needed for custom habitats"), and ranking is never
 * recomputed in the browser.
 */
import { normalizeCoverage } from "./coverage";
import { matchPreset, type Habitat } from "./habitat";
import { STATIC_DILUENTS, normalizeReference, normalizeSuppression } from "./suppression";
import type {
  AskAnswer,
  BoundsResult,
  CatalogRecord,
  DiluentId,
  DiluentInfo,
  Incident,
  IncidentsArtifact,
  MetricInfo,
  PlannerArtifact,
  PlannerItem,
  RankItem,
  RankWeights,
  SuppressionCurve,
  SuppressionReference,
  TestsPage,
} from "./types";

/** Backend base URL (FastAPI, plan/contracts.md). */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

export type DataSource = "api" | "offline";

export interface Sourced<T> {
  data: T;
  source: DataSource;
  /** Human-readable note for the offline chip or an inline caveat. */
  note?: string;
}

/** The API is down and no honest static fallback exists for this request. */
export class OfflineUnavailableError extends Error {
  readonly offline = true;
  constructor(message: string) {
    super(message);
    this.name = "OfflineUnavailableError";
  }
}

/** The API answered with a client error (bad input, unknown id). Not a reason to fall back. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Network failure, timeout, 404 (endpoint not deployed yet) or 5xx: the live path is unavailable. */
class LiveUnavailable extends Error {}

export const OFFLINE_NOTE = "offline data: the live API is unreachable, showing precomputed artifacts";
export const CUSTOM_HABITAT_NOTE =
  "Live API needed for custom habitats: precomputed bounds exist only for the six presets.";
export const CUSTOM_SUPPRESSION_NOTE =
  "Live API needed for custom habitats: precomputed suppression curves exist only for the six presets.";
/** A suppression curve runs the M1/M2 models at every fraction, so the first live call gets more time. */
const SUPPRESSION_TIMEOUT_MS = 10_000;

/** Static fallback for GET /metrics (plan/03 §3 metric table). */
export const STATIC_METRICS: MetricInfo[] = [
  { id: "M1", label: "P(droplet flame self-extinguishes before burnout)", unit: "probability", kind: "probability", data: "FLEX (PSI-69)", flow_dependent: false },
  { id: "M2", label: "Extinction diameter", unit: "mm", kind: "quantity", data: "FLEX", flow_dependent: false },
  { id: "M3", label: "P(gas flame self-extinguishes vs flow-terminated)", unit: "probability", kind: "probability", data: "ACME CFI-G (PSI-159)", flow_dependent: false },
  { id: "M4", label: "Solid-material burn extent: microgravity vs 1 g", unit: "category", kind: "category", data: "SAFFIRE-II (PSI-99) + SAFFIRE-I/III, BASS-II context", flow_dependent: true },
  { id: "M5", label: "Flame existence vs coflow speed", unit: "category", kind: "category", data: "SPICE (PSI-107) coflow windows", flow_dependent: true },
];

export interface ClientOptions {
  apiUrl?: string;
  staticBase?: string;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
}

export interface TestsFilters {
  investigation_id?: string;
  o2_min?: number;
  o2_max?: number;
  /** Exact match on the outcome column (phase 3 API; comma-separate for several). Ignored by older APIs. */
  outcome?: string;
  limit?: number;
  offset?: number;
}

function habitatBody(h: Habitat) {
  return { g_m_s2: h.g_m_s2, p_psia: h.p_psia, o2: h.o2, u_cm_s: h.u_cm_s, L_mm: h.L_mm };
}

export function filtersToQuery(f: TestsFilters, extra?: Record<string, string>): string {
  const q = new URLSearchParams();
  (Object.entries(f) as [string, string | number | undefined][]).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    if (typeof v === "number" && !Number.isFinite(v)) return;
    q.set(k, String(v));
  });
  if (extra) Object.entries(extra).forEach(([k, v]) => q.set(k, v));
  return q.toString();
}

export function normalizeMetrics(raw: unknown): MetricInfo[] {
  if (Array.isArray(raw)) return raw as MetricInfo[];
  if (raw && typeof raw === "object") {
    return Object.entries(raw as Record<string, Omit<MetricInfo, "id">>).map(([id, m]) => ({ ...m, id }));
  }
  return [];
}

export function normalizePlanner(raw: unknown): PlannerArtifact {
  if (Array.isArray(raw)) return { tests: raw as PlannerItem[], design_implications: [] };
  const o = (raw ?? {}) as Record<string, unknown>;
  const tests = (o.items ?? o.tests ?? o.candidates ?? o.plan ?? []) as PlannerItem[];
  const implications = (o.design_implications ?? []) as string[];
  return {
    tests: Array.isArray(tests) ? tests : [],
    design_implications: Array.isArray(implications) ? implications : [],
    method: typeof o.method === "string" ? o.method : undefined,
    version: typeof o.version === "string" ? o.version : undefined,
    generated_at: typeof o.generated_at === "string" ? o.generated_at : undefined,
    habitat_targets: Array.isArray(o.habitat_targets) ? (o.habitat_targets as PlannerArtifact["habitat_targets"]) : undefined,
  };
}

export function normalizeCatalog(raw: unknown): CatalogRecord[] {
  if (Array.isArray(raw)) return raw as CatalogRecord[];
  const inv = (raw as { investigations?: unknown } | null)?.investigations;
  return Array.isArray(inv) ? (inv as CatalogRecord[]) : [];
}

/** Accept {incidents: [...]} (the artifact / GET /incidents) or a bare list. */
export function normalizeIncidents(raw: unknown): IncidentsArtifact {
  const o = (Array.isArray(raw) ? { incidents: raw } : (raw ?? {})) as Record<string, unknown>;
  const list = Array.isArray(o.incidents) ? (o.incidents as Incident[]) : [];
  return {
    incidents: list.map((i) => ({ ...i, assumed: Array.isArray(i.assumed) ? i.assumed : [], sources: Array.isArray(i.sources) ? i.sources : [] })),
    generated_at: typeof o.generated_at === "string" ? o.generated_at : undefined,
    engine_version: typeof o.engine_version === "string" ? o.engine_version : undefined,
  };
}

// ------------------------------------------------------------------ offline AI cache matching

export interface CachedAnswer {
  question: string;
  answer: AskAnswer;
  habitat_id?: string | null;
}

/** Lowercase, strip punctuation, collapse whitespace. */
export function normalizeQuestion(q: string): string {
  return q
    .toLowerCase()
    .replace(/[^a-z0-9₂%.\s-]/g, " ")
    .replace(/[.-](?=\s|$)/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const STOP = new Set(["the", "a", "an", "is", "are", "of", "to", "in", "at", "for", "this", "that", "why", "what", "how", "does", "do", "it", "on", "and", "or", "so"]);

function tokens(q: string): Set<string> {
  return new Set(normalizeQuestion(q).split(" ").filter((t) => t && !STOP.has(t)));
}

/** Accept the shapes ai_cache.json may take: a list, {entries|answers|items: [...]}, or {question: answer}. */
export function normalizeAiCache(raw: unknown): CachedAnswer[] {
  const toEntry = (e: Record<string, unknown>, fallbackQ?: string): CachedAnswer | null => {
    const question = String(e.question ?? fallbackQ ?? "");
    const ans = (e.answer && typeof e.answer === "object" ? e.answer : e.response && typeof e.response === "object" ? e.response : e) as Record<string, unknown>;
    const md = ans.answer_markdown ?? (typeof e.answer === "string" ? e.answer : undefined);
    if (!question || typeof md !== "string") return null;
    const habitat = e.habitat as Record<string, unknown> | string | undefined;
    const habitat_id =
      typeof habitat === "string" ? habitat : ((e.habitat_id ?? e.preset_id ?? e.preset ?? (habitat && (habitat.id ?? habitat.preset_id))) as string | undefined);
    return {
      question,
      habitat_id: habitat_id ?? null,
      answer: {
        answer_markdown: md,
        citations: (ans.citations as string[]) ?? [],
        numbers_used: (ans.numbers_used as (number | string)[]) ?? [],
        validated: Boolean(ans.validated),
        mode: "cached",
      },
    };
  };
  let list: unknown[] = [];
  if (Array.isArray(raw)) list = raw;
  else if (raw && typeof raw === "object") {
    const o = raw as Record<string, unknown>;
    const inner = o.entries ?? o.answers ?? o.items ?? o.questions ?? o.cache;
    if (Array.isArray(inner)) list = inner;
    else {
      const src = (inner && typeof inner === "object" ? inner : o) as Record<string, unknown>;
      return Object.entries(src)
        .filter(([, v]) => v && typeof v === "object")
        .map(([k, v]) => toEntry(v as Record<string, unknown>, k))
        .filter((x): x is CachedAnswer => x !== null);
    }
  }
  return list
    .filter((e): e is Record<string, unknown> => !!e && typeof e === "object")
    .map((e) => toEntry(e))
    .filter((x): x is CachedAnswer => x !== null);
}

/** Best cached answer for a question: exact normalized match, else token Jaccard >= 0.6; preset match breaks ties. */
export function matchCachedAnswer(question: string, entries: CachedAnswer[], presetId?: string | null): CachedAnswer | null {
  const nq = normalizeQuestion(question);
  if (!nq) return null;
  const qt = tokens(question);
  let best: { e: CachedAnswer; s: number } | null = null;
  for (const e of entries) {
    let s: number;
    if (normalizeQuestion(e.question) === nq) s = 2;
    else {
      const et = tokens(e.question);
      const inter = [...qt].filter((t) => et.has(t)).length;
      const union = new Set([...qt, ...et]).size;
      s = union ? inter / union : 0;
      if (s < 0.6) continue;
    }
    if (presetId && e.habitat_id === presetId) s += 0.05;
    if (!best || s > best.s) best = { e, s };
  }
  return best?.e ?? null;
}

// ------------------------------------------------------------------ client

export function createClient(opts: ClientOptions = {}) {
  const apiUrl = (opts.apiUrl ?? API_URL).replace(/\/+$/, "");
  const staticBase = (opts.staticBase ?? "/artifacts").replace(/\/+$/, "");
  const doFetch: typeof fetch = opts.fetchImpl ?? ((...a) => fetch(...a));
  const timeoutMs = opts.timeoutMs ?? 2500;

  async function live(path: string, init?: RequestInit, ms = timeoutMs): Promise<Response> {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), ms);
    let res: Response;
    try {
      res = await doFetch(`${apiUrl}${path}`, { ...init, signal: ctrl.signal });
    } catch (e) {
      throw new LiveUnavailable(e instanceof Error ? e.message : String(e));
    } finally {
      clearTimeout(timer);
    }
    if (res.status === 404 || res.status >= 500) throw new LiveUnavailable(`HTTP ${res.status}`);
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        detail = String(body.detail ?? body.title ?? detail);
      } catch {
        /* keep status text */
      }
      throw new ApiError(detail, res.status);
    }
    return res;
  }

  async function liveJson<T>(path: string, init?: RequestInit, ms?: number): Promise<T> {
    return (await (await live(path, init, ms)).json()) as T;
  }

  function post(body: unknown): RequestInit {
    return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  }

  async function staticFile(rel: string, missing: string): Promise<Response> {
    let res: Response;
    try {
      res = await doFetch(`${staticBase}/${rel}`);
    } catch {
      throw new OfflineUnavailableError(missing);
    }
    if (!res.ok) throw new OfflineUnavailableError(missing);
    return res;
  }

  async function staticJson<T>(rel: string, missing: string): Promise<T> {
    return (await (await staticFile(rel, missing)).json()) as T;
  }

  /** Try live; on LiveUnavailable run the offline branch. ApiError propagates. */
  async function withFallback<T>(liveFn: () => Promise<T>, offlineFn: () => Promise<Sourced<T>>): Promise<Sourced<T>> {
    try {
      return { data: await liveFn(), source: "api" };
    } catch (e) {
      if (!(e instanceof LiveUnavailable)) throw e;
      return offlineFn();
    }
  }

  return {
    apiUrl,

    catalog: () =>
      withFallback(
        async () => normalizeCatalog(await liveJson<unknown>("/catalog")),
        async () => ({
          data: normalizeCatalog(await staticJson("catalog.json", "API offline and no catalog artifact was bundled.")),
          source: "offline",
          note: OFFLINE_NOTE,
        }),
      ),

    /** Ranking always needs the API; offline returns null so the page shows catalog order with a note. */
    rank: (h: Habitat, weights?: RankWeights) =>
      withFallback<RankItem[] | null>(
        () => liveJson<RankItem[]>("/rank", post({ ...habitatBody(h), weights })),
        async () => ({ data: null, source: "offline", note: "offline: ranking needs the API, showing catalog order" }),
      ),

    metrics: () =>
      withFallback(
        async () => normalizeMetrics(await liveJson<unknown>("/metrics")),
        async () => ({ data: STATIC_METRICS, source: "offline", note: OFFLINE_NOTE }),
      ),

    bounds: (h: Habitat, metric: string) =>
      withFallback(
        () => liveJson<BoundsResult>("/bounds", post({ ...habitatBody(h), metric })),
        async () => {
          const preset = matchPreset(h);
          if (!preset) throw new OfflineUnavailableError(CUSTOM_HABITAT_NOTE);
          const data = await staticJson<BoundsResult>(
            `bounds/${preset.id}_${metric}.json`,
            `API offline and no precomputed bounds for ${preset.label} / ${metric}.`,
          );
          return { data, source: "offline", note: `${OFFLINE_NOTE} (${preset.label} preset)` };
        },
      ),

    /** Tested O2 x pressure points for a metric (habitat status is computed client-side, same rule as the engine). */
    coverage: (metric: string) =>
      withFallback(
        async () => normalizeCoverage(await liveJson<unknown>(`/coverage/${encodeURIComponent(metric)}`)),
        async () => ({
          data: normalizeCoverage(
            await staticJson(`coverage/${metric}.json`, `API offline and no coverage artifact for ${metric} was bundled.`),
          ),
          source: "offline",
          note: OFFLINE_NOTE,
        }),
      ),

    /** R1 real-fire replay: engine results for real spacecraft fire events (artifacts/incidents.json offline). */
    incidents: () =>
      withFallback(
        async () => normalizeIncidents(await liveJson<unknown>("/incidents")),
        async () => ({
          data: normalizeIncidents(
            await staticJson("incidents.json", "API offline and no incidents artifact was bundled."),
          ),
          source: "offline",
          note: OFFLINE_NOTE,
        }),
      ),

    /** R2 diluents (GET /suppression/diluents); offline mirrors engine/suppression.py DILUENTS. */
    suppressionDiluents: () =>
      withFallback<Record<DiluentId, DiluentInfo>>(
        () => liveJson<Record<DiluentId, DiluentInfo>>("/suppression/diluents"),
        async () => ({ data: STATIC_DILUENTS, source: "offline", note: OFFLINE_NOTE }),
      ),

    /**
     * R2 suppression curve (POST /suppression). Offline: the preset artifact artifacts/suppression/{preset}_{diluent}.json;
     * a custom habitat has no honest offline curve.
     */
    suppression: (h: Habitat, diluent: DiluentId) =>
      withFallback<SuppressionCurve>(
        async () =>
          normalizeSuppression(
            await liveJson<unknown>("/suppression", post({ ...habitatBody(h), diluent }), Math.max(timeoutMs, SUPPRESSION_TIMEOUT_MS)),
            diluent,
          ),
        async () => {
          const preset = matchPreset(h);
          if (!preset) throw new OfflineUnavailableError(CUSTOM_SUPPRESSION_NOTE);
          const raw = await staticJson<unknown>(
            `suppression/${preset.id}_${diluent}.json`,
            `API offline and no precomputed suppression curve for ${preset.label} / ${diluent === "he" ? "helium" : "CO₂"}.`,
          );
          return { data: normalizeSuppression(raw, diluent), source: "offline", note: `${OFFLINE_NOTE} (${preset.label} preset)` };
        },
      ),

    /** R2 empirical FLEX outcome rates by diluent bin (GET /suppression/reference, artifacts/suppression_reference.json). */
    suppressionReference: () =>
      withFallback<SuppressionReference>(
        async () => normalizeReference(await liveJson<unknown>("/suppression/reference")),
        async () => ({
          data: normalizeReference(
            await staticJson("suppression_reference.json", "API offline and no suppression reference artifact was bundled."),
          ),
          source: "offline",
          note: OFFLINE_NOTE,
        }),
      ),

    planner: () =>
      withFallback(
        async () => normalizePlanner(await liveJson<unknown>("/planner")),
        async () => ({
          data: normalizePlanner(await staticJson("planner.json", "API offline and no planner artifact was bundled.")),
          source: "offline",
          note: OFFLINE_NOTE,
        }),
      ),

    /**
     * Ledger records as raw JSONL text. Raw text (not parsed JSON) is required for hash verification: number
     * spellings such as 10.0 must survive exactly as Python wrote them.
     */
    ledgerText: () =>
      withFallback<{ kind: "jsonl" | "ledger-json"; text: string }>(
        async () => {
          // GET /ledger returns {predictions[], verification[]}; extract raw predictions text spans.
          const text = await (await live("/ledger")).text();
          return { kind: "ledger-json", text };
        },
        async () => ({
          data: {
            kind: "jsonl",
            text: await (await staticFile("ledger/predictions.jsonl", "API offline and no ledger file was bundled.")).text(),
          },
          source: "offline",
          note: OFFLINE_NOTE,
        }),
      ),

    ask: (question: string, h: Habitat, contextIds: string[] = []) =>
      withFallback(
        () => liveJson<AskAnswer>("/ask", post({ question, habitat: habitatBody(h), context_ids: contextIds })),
        async () => {
          const cache = normalizeAiCache(
            await staticJson("ai_cache.json", "The live API is needed to answer questions (no offline answer cache)."),
          );
          const hit = matchCachedAnswer(question, cache, matchPreset(h)?.id ?? null);
          if (!hit) {
            throw new OfflineUnavailableError(
              "The live API is needed for this question. Offline, only the pre-generated demo questions have answers.",
            );
          }
          return { data: hit.answer, source: "offline", note: `offline: cached answer to "${hit.question}"${hit.habitat_id ? ` (${hit.habitat_id} habitat)` : ""}` };
        },
      ),

    tests: async (f: TestsFilters): Promise<Sourced<TestsPage>> => {
      try {
        return { data: await liveJson<TestsPage>(`/data/tests?${filtersToQuery(f)}`), source: "api" };
      } catch (e) {
        if (e instanceof LiveUnavailable) {
          throw new OfflineUnavailableError("The data explorer needs the live API (the test table is not bundled offline).");
        }
        throw e;
      }
    },

    exportUrl: (f: TestsFilters, format: "csv" | "json") => {
      const { limit: _l, offset: _o, ...rest } = f;
      void _l;
      void _o;
      return `${apiUrl}/data/export?${filtersToQuery(rest, { format })}`;
    },
  };
}

export type Client = ReturnType<typeof createClient>;

/** Shared browser client. */
export const api: Client = createClient();
