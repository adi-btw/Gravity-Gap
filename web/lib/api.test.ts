import { describe, expect, it } from "vitest";
import {
  ApiError,
  CUSTOM_HABITAT_NOTE,
  OfflineUnavailableError,
  STATIC_METRICS,
  createClient,
  liveDisabled,
  matchCachedAnswer,
  normalizeAiCache,
  normalizeMetrics,
  normalizePlanner,
} from "./api";
import { presetToHabitat } from "./habitat";
import { PRESETS_BY_ID } from "./presets";

const API = "http://api.test";
const ROVER = presetToHabitat(PRESETS_BY_ID.lunar_rover);

type Handler = (url: string, init?: RequestInit) => Response | Promise<Response>;

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** Fake fetch: the API host is handled by `api`, static files by the `files` map. */
function fakeFetch(api: Handler | "down", files: Record<string, unknown> = {}) {
  const calls: string[] = [];
  const impl = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push(url);
    if (url.startsWith(API)) {
      if (api === "down") throw new TypeError("fetch failed");
      return api(url, init);
    }
    const rel = url.replace(/^\/artifacts\//, "");
    if (rel in files) return typeof files[rel] === "string" ? new Response(files[rel] as string) : json(files[rel]);
    return new Response("not found", { status: 404 });
  }) as typeof fetch;
  return { impl, calls };
}

const BOUNDS = { metric: "M1", applicable: true, estimate: 0.2, band90: [0.01, 0.7] };

describe("data layer fallback", () => {
  it("uses the live API when it answers", async () => {
    const { impl, calls } = fakeFetch(() => json(BOUNDS));
    const r = await createClient({ apiUrl: API, fetchImpl: impl }).bounds(ROVER, "M1");
    expect(r.source).toBe("api");
    expect(r.data.estimate).toBe(0.2);
    expect(calls).toEqual([`${API}/bounds`]);
  });

  it("falls back to the preset artifact when the API is down", async () => {
    const { impl, calls } = fakeFetch("down", { "bounds/lunar_rover_M1.json": { ...BOUNDS, estimate: 0.21 } });
    const r = await createClient({ apiUrl: API, fetchImpl: impl }).bounds(ROVER, "M1");
    expect(r.source).toBe("offline");
    expect(r.data.estimate).toBe(0.21);
    expect(r.note).toMatch(/offline/);
    expect(calls[1]).toBe("/artifacts/bounds/lunar_rover_M1.json");
  });

  it("falls back on 5xx and on 404 (endpoint not deployed)", async () => {
    for (const status of [503, 404]) {
      const { impl } = fakeFetch(() => json({ detail: "x" }, status), { "planner.json": { items: [{ rank: 1 }], design_implications: ["d"] } });
      const r = await createClient({ apiUrl: API, fetchImpl: impl }).planner();
      expect(r.source).toBe("offline");
      expect(r.data.tests).toHaveLength(1);
    }
  });

  it("falls back on timeout", async () => {
    const hang: Handler = (_u, init) =>
      new Promise((_res, rej) => init?.signal?.addEventListener("abort", () => rej(new DOMException("aborted", "AbortError"))));
    const { impl } = fakeFetch(hang, { "catalog.json": { investigations: [{ id: "PSI-69" }] } });
    const r = await createClient({ apiUrl: API, fetchImpl: impl, timeoutMs: 20 }).catalog();
    expect(r.source).toBe("offline");
    expect(r.data.map((x) => x.id)).toEqual(["PSI-69"]);
  });

  it("refuses to fake numbers for a custom habitat offline", async () => {
    const { impl, calls } = fakeFetch("down", { "bounds/lunar_rover_M1.json": BOUNDS });
    const custom = { ...ROVER, u_cm_s: 7 };
    await expect(createClient({ apiUrl: API, fetchImpl: impl }).bounds(custom, "M1")).rejects.toThrow(CUSTOM_HABITAT_NOTE);
    expect(calls).toHaveLength(1); // never fetched a static file
  });

  it("throws OfflineUnavailableError when the artifact is missing too", async () => {
    const { impl } = fakeFetch("down");
    await expect(createClient({ apiUrl: API, fetchImpl: impl }).bounds(ROVER, "M9")).rejects.toBeInstanceOf(OfflineUnavailableError);
  });

  it("does not fall back on a 422 (bad input is a real error)", async () => {
    const { impl } = fakeFetch(() => json({ detail: "weights must be non-negative" }, 422), { "catalog.json": [] });
    const p = createClient({ apiUrl: API, fetchImpl: impl }).rank(ROVER, { atmosphere: 0, pillar: 0, fuel_realism: 0, outcomes: 0, n_tests: 0, regime_fit: 0 });
    await expect(p).rejects.toBeInstanceOf(ApiError);
    await expect(p).rejects.toThrow("weights must be non-negative");
  });

  it("never ranks client-side: offline rank returns null with a note", async () => {
    const { impl } = fakeFetch("down", { "catalog.json": [] });
    const r = await createClient({ apiUrl: API, fetchImpl: impl }).rank(ROVER);
    expect(r).toEqual({ data: null, source: "offline", note: expect.stringMatching(/ranking needs the API/) });
  });

  it("metrics fall back to the static M1-M5 list and normalise the API dict", async () => {
    const { impl } = fakeFetch("down");
    const r = await createClient({ apiUrl: API, fetchImpl: impl }).metrics();
    expect(r.data.map((m) => m.id)).toEqual(["M1", "M2", "M3", "M4", "M5"]);
    expect(r.data).toBe(STATIC_METRICS);
    expect(normalizeMetrics({ M1: { label: "a", unit: "probability", kind: "probability" } })).toEqual([
      { id: "M1", label: "a", unit: "probability", kind: "probability" },
    ]);
  });

  it("data explorer needs the API", async () => {
    const { impl } = fakeFetch("down");
    await expect(createClient({ apiUrl: API, fetchImpl: impl }).tests({})).rejects.toBeInstanceOf(OfflineUnavailableError);
  });

  it("ledger falls back to the bundled JSONL text", async () => {
    const { impl } = fakeFetch("down", { "ledger/predictions.jsonl": '{"id":"GG-P0001"}\n' });
    const r = await createClient({ apiUrl: API, fetchImpl: impl }).ledgerText();
    expect(r).toMatchObject({ source: "offline", data: { kind: "jsonl", text: '{"id":"GG-P0001"}\n' } });
  });

  it("export URL carries the same filters but not pagination", () => {
    const c = createClient({ apiUrl: API });
    expect(c.exportUrl({ investigation_id: "PSI-69", o2_min: 0.3, limit: 50, offset: 100 }, "csv")).toBe(
      `${API}/data/export?investigation_id=PSI-69&o2_min=0.3&format=csv`,
    );
  });

  it("passes the outcome filter through to tests and export", async () => {
    const c = createClient({ apiUrl: API });
    expect(c.exportUrl({ outcome: "extinction" }, "json")).toBe(`${API}/data/export?outcome=extinction&format=json`);
    const { impl, calls } = fakeFetch(() => json({ total: 0, limit: 50, offset: 0, rows: [] }));
    await createClient({ apiUrl: API, fetchImpl: impl }).tests({ outcome: "extinction", limit: 50 });
    expect(calls.some((u) => u.includes("/data/tests?outcome=extinction&limit=50"))).toBe(true);
  });

  it("normalises the planner artifact (items or list)", () => {
    expect(normalizePlanner({ items: [{ rank: 1 }], design_implications: ["x"], method: "m" })).toMatchObject({
      tests: [{ rank: 1 }],
      design_implications: ["x"],
      method: "m",
    });
    expect(normalizePlanner([{ rank: 2 }]).tests).toEqual([{ rank: 2 }]);
  });
});

describe("offline Ask cache", () => {
  const cache = normalizeAiCache({
    version: "v1",
    entries: [
      { question: "Why is the M1 band wide for the lunar base?", habitat: "lunar_base", answer_markdown: "Wide [eng:M1].", citations: ["eng:M1"], numbers_used: [], validated: true, mode_generated: "template" },
      { question: "What should LUCI test first?", habitat: "lunar_base", answer_markdown: "Test 1.", citations: [], numbers_used: [], validated: true },
    ],
  });

  it("reads the ai_cache.json entries shape and marks answers as cached", () => {
    expect(cache).toHaveLength(2);
    expect(cache[0]).toMatchObject({ habitat_id: "lunar_base", answer: { mode: "cached", validated: true, citations: ["eng:M1"] } });
  });

  it("matches exact, case/punctuation-insensitive and near questions", () => {
    expect(matchCachedAnswer("what should luci test first", cache)?.question).toBe("What should LUCI test first?");
    expect(matchCachedAnswer("Why is the M1 band so wide for the lunar base?", cache)?.question).toMatch(/M1 band/);
    expect(matchCachedAnswer("Tell me about rockets", cache)).toBeNull();
  });

  it("answers offline from the cache, or says the live API is needed", async () => {
    const { impl } = fakeFetch("down", { "ai_cache.json": { entries: [{ question: "What should LUCI test first?", answer_markdown: "x", validated: true }] } });
    const c = createClient({ apiUrl: API, fetchImpl: impl });
    const hit = await c.ask("What should LUCI test first?", ROVER);
    expect(hit).toMatchObject({ source: "offline", data: { answer_markdown: "x", mode: "cached" } });
    await expect(c.ask("Explain quantum gravity", ROVER)).rejects.toThrow(/live API is needed/);
  });
});

describe("liveDisabled (website-only deployments)", () => {
  it("is off when NEXT_PUBLIC_API_URL is off, none or empty", () => {
    for (const v of ["off", "none", "", "  OFF "]) expect(liveDisabled(v, "gravity-gap.vercel.app")).toBe(true);
  });
  it("skips a localhost API when the page is served from a real host", () => {
    expect(liveDisabled("http://localhost:8000", "gravity-gap.vercel.app")).toBe(true);
    expect(liveDisabled("http://127.0.0.1:8000", "example.org")).toBe(true);
  });
  it("keeps the live API for local development and for a real API host", () => {
    expect(liveDisabled("http://localhost:8000", "localhost")).toBe(false);
    expect(liveDisabled("http://localhost:8000", "127.0.0.1")).toBe(false);
    expect(liveDisabled("https://gravity-gap-api.onrender.com", "gravity-gap.vercel.app")).toBe(false);
  });
  it("falls back to bundled data without calling fetch when disabled", async () => {
    const urls: string[] = [];
    const impl = (async (url: string) => {
      urls.push(String(url));
      throw new Error("network down");
    }) as unknown as typeof fetch;
    const c = createClient({ apiUrl: "off", fetchImpl: impl, staticBase: "/artifacts" });
    await c.planner().catch(() => undefined);
    // Only the bundled artifact is requested; nothing goes to the live API.
    expect(urls.length).toBeGreaterThan(0);
    expect(urls.every((u) => u.startsWith("/artifacts/"))).toBe(true);
  });
});
