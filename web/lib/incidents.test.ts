import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/incidents.json";
import { createClient, normalizeIncidents } from "./api";
import { FIELDS, habitatFromQuery, matchPreset } from "./habitat";
import { incidentHabitat, incidentHref, matchIncident } from "./incidents";
import type { Incident } from "./types";

const API = "http://api.test";
const INCIDENTS = (fixture as unknown as { incidents: Incident[] }).incidents;
const byId = (id: string) => INCIDENTS.find((i) => i.id === id)!;

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function fakeFetch(api: ((url: string) => Response) | "down", files: Record<string, unknown> = {}) {
  const calls: string[] = [];
  const impl = (async (input: RequestInfo | URL) => {
    const url = String(input);
    calls.push(url);
    if (url.startsWith(API)) {
      if (api === "down") throw new TypeError("fetch failed");
      return api(url);
    }
    const rel = url.replace(/^\/artifacts\//, "");
    return rel in files ? json(files[rel]) : new Response("not found", { status: 404 });
  }) as typeof fetch;
  return { impl, calls };
}

describe("incidents data layer", () => {
  it("uses GET /incidents when the API answers", async () => {
    const { impl, calls } = fakeFetch(() => json(fixture));
    const r = await createClient({ apiUrl: API, fetchImpl: impl }).incidents();
    expect(r.source).toBe("api");
    expect(r.data.incidents.map((i) => i.id)).toEqual(["apollo1", "mir1997", "artemis2", "apollo13"]);
    expect(calls).toEqual([`${API}/incidents`]);
  });

  it("falls back to artifacts/incidents.json when the API is down", async () => {
    const { impl, calls } = fakeFetch("down", { "incidents.json": fixture });
    const r = await createClient({ apiUrl: API, fetchImpl: impl }).incidents();
    expect(r.source).toBe("offline");
    expect(r.note).toMatch(/offline/);
    expect(r.data.incidents).toHaveLength(4);
    expect(calls[1]).toBe("/artifacts/incidents.json");
  });

  it("falls back when the endpoint is not deployed (404) or the artifact is not built (503)", async () => {
    for (const status of [404, 503]) {
      const { impl } = fakeFetch(() => json({ title: "x" }, status), { "incidents.json": fixture });
      const r = await createClient({ apiUrl: API, fetchImpl: impl }).incidents();
      expect(r.source).toBe("offline");
    }
  });

  it("reports offline-unavailable when neither the API nor the artifact exists", async () => {
    const { impl } = fakeFetch("down");
    await expect(createClient({ apiUrl: API, fetchImpl: impl }).incidents()).rejects.toMatchObject({ offline: true });
  });

  it("normalizes a bare list and missing arrays", () => {
    const n = normalizeIncidents([{ id: "x", name: "X" }]);
    expect(n.incidents[0].assumed).toEqual([]);
    expect(n.incidents[0].sources).toEqual([]);
    expect(normalizeIncidents(null).incidents).toEqual([]);
  });
});

describe("Load this habitat URL", () => {
  it("passes Apollo 1's 16.7 psia and 100% O2 through unclamped", () => {
    const href = incidentHref(byId("apollo1"))!;
    expect(href.startsWith("/bounds?")).toBe(true);
    const q = new URLSearchParams(href.split("?")[1]);
    expect(q.get("g")).toBe("9.81");
    expect(q.get("p")).toBe("16.7");
    expect(q.get("o2")).toBe("1");
    expect(q.get("u")).toBe("10");
    expect(q.get("L")).toBe("10");
    // Round-trips through the URL parser without clamping.
    const h = habitatFromQuery(q);
    expect(h.p_psia).toBe(16.7);
    expect(h.o2).toBe(1);
    expect(FIELDS.p_psia.max).toBe(20);
  });

  it("builds a /regime link and a Mir habitat at 0 g", () => {
    const href = incidentHref(byId("mir1997"), "/regime")!;
    expect(href).toMatch(/^\/regime\?g=0&p=14\.7&o2=0\.21&u=10&L=10$/);
  });

  it("gives no habitat for out-of-scope incidents", () => {
    expect(incidentHabitat(byId("apollo13"))).toBeNull();
    expect(incidentHref(byId("apollo13"))).toBeNull();
  });

  it("matches incidents for the History chips without changing preset matching", () => {
    const apollo1 = incidentHabitat(byId("apollo1"))!;
    expect(matchIncident(apollo1, INCIDENTS)?.id).toBe("apollo1");
    expect(matchPreset(apollo1)).toBeNull();
    // Mir's fixture values equal the ISS preset: both the preset and the incident match.
    const mir = incidentHabitat(byId("mir1997"))!;
    expect(matchPreset(mir)?.id).toBe("iss");
    expect(matchIncident(mir, INCIDENTS)?.id).toBe("mir1997");
    expect(matchIncident({ ...apollo1, u_cm_s: 7 }, INCIDENTS)).toBeNull();
  });
});

describe("incident extras", () => {
  it("keeps assumed_note and unlinked sources through normalization", () => {
    const a2 = normalizeIncidents(fixture).incidents.find((i) => i.id === "artemis2")!;
    expect(a2.assumed_note).toMatch(/fans/);
    const brief = a2.sources.find((s) => !s.url);
    expect(brief?.source).toBe("2026 NASA Space Apps Challenge brief");
  });
});
