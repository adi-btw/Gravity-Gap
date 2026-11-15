import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { CUSTOM_COMPARE_NOTE, OfflineUnavailableError, createClient } from "./api";
import {
  CURRENT_LABEL,
  METRIC_IDS,
  buildCompare,
  compareQuery,
  compareQuestion,
  compareWithTarget,
  fmt3,
  parseSide,
  resolveSide,
  type CompareHabitat,
  type CompareResult,
} from "./compare";
import { habitatFromQuery, habitatToQuery, presetToHabitat } from "./habitat";
import { PRESETS_BY_ID, type PresetId } from "./presets";
import type { BoundsResult } from "./types";

const ART = path.resolve(__dirname, "..", "..", "artifacts");
const FIXTURE = JSON.parse(readFileSync(path.join(__dirname, "__fixtures__", "compare.json"), "utf-8")) as {
  pairs: Record<string, CompareResult>;
};
const LUNAR = presetToHabitat(PRESETS_BY_ID.lunar_base);
const CUSTOM = { ...LUNAR, u_cm_s: 7 };

function bounds(pid: string): BoundsResult[] {
  return METRIC_IDS.map((m) => JSON.parse(readFileSync(path.join(ART, "bounds", `${pid}_${m}.json`), "utf-8")));
}

function hab(pid: PresetId): CompareHabitat {
  const p = PRESETS_BY_ID[pid];
  return { ...presetToHabitat(p), preset_id: p.id, label: p.label };
}

describe("compare URL state", () => {
  it("parses a/b and falls back on junk", () => {
    expect(parseSide("lunar_base", "iss")).toBe("lunar_base");
    expect(parseSide("current", "iss")).toBe("current");
    expect(parseSide("moonbase", "iss")).toBe("iss");
    expect(parseSide(null, "current")).toBe("current");
    expect(parseSide("toString", "iss")).toBe("iss");
  });

  it("round-trips both sides and the habitat through the query", () => {
    const qs = compareQuery("iss", "current", habitatToQuery(CUSTOM).toString());
    const q = new URLSearchParams(qs);
    expect(parseSide(q.get("a"), "earth")).toBe("iss");
    expect(parseSide(q.get("b"), "earth")).toBe("current");
    expect(habitatFromQuery(q)).toEqual(CUSTOM);
  });

  it("resolves 'current' to the matching preset, else a custom habitat", () => {
    expect(resolveSide("current", LUNAR)).toMatchObject({ presetId: "lunar_base", label: "Lunar base" });
    expect(resolveSide("current", CUSTOM)).toMatchObject({ presetId: null, label: CURRENT_LABEL, habitat: CUSTOM });
    expect(resolveSide("iss", CUSTOM)).toMatchObject({ presetId: "iss", label: "ISS" });
  });

  it("'Compare with…' from /bounds and the cached question wording", () => {
    expect(compareWithTarget(LUNAR)).toEqual({ a: "current", b: "iss" });
    expect(compareWithTarget(presetToHabitat(PRESETS_BY_ID.iss))).toEqual({ a: "current", b: "lunar_base" });
    expect(compareQuestion("iss", "lunar_base")).toBe("What changes between ISS and the lunar base?");
  });

  it("formats like the engine (3 significant figures)", () => {
    expect(fmt3(93.87076846641129)).toBe("93.9");
    expect(fmt3(1.2463962053841043)).toBe("1.25");
    expect(fmt3(4.003825654706249)).toBe("4");
    expect(fmt3(100)).toBe("100");
    expect(fmt3(21.000000000000004)).toBe("21");
  });
});

describe.skipIf(!existsSync(path.join(ART, "bounds", "iss_M1.json")))("offline compare parity with engine/compare.py", () => {
  for (const [key, expected] of Object.entries(FIXTURE.pairs)) {
    const [a, b] = key.split("__") as [PresetId, PresetId];
    it(`${a} vs ${b}`, () => {
      const got = buildCompare(hab(a), hab(b), bounds(a), bounds(b));
      expect(got.summary).toBe(expected.summary);
      expect(got.inputs_diff).toEqual(expected.inputs_diff);
      got.metrics.forEach((m, i) => {
        const e = expected.metrics[i];
        expect(m.metric).toBe(e.metric);
        expect(m.diff.coverage).toEqual(e.diff.coverage);
        expect(m.diff.regime).toEqual(e.diff.regime);
        expect(m.diff.estimate_note).toBe(e.diff.estimate_note);
        expect(m.diff.estimate?.direction ?? null).toBe(e.diff.estimate?.direction ?? null);
        expect(m.diff.band_width?.direction ?? null).toBe(e.diff.band_width?.direction ?? null);
        expect(m.b.estimate).toEqual(e.b.estimate);
      });
    });
  }

  it("ISS vs lunar base: M2 'no evidence' on the right only, never a difference", () => {
    const r = buildCompare(hab("iss"), hab("lunar_base"), bounds("iss"), bounds("lunar_base"));
    const m2 = r.metrics.find((m) => m.metric === "M2")!;
    expect(m2.a.applicable).toBe(true);
    expect(m2.b.applicable).toBe(false);
    expect(m2.diff.estimate).toBeNull();
  });
});

describe("api.compare", () => {
  const API = "http://api.test";
  const files = (pids: string[]) =>
    Object.fromEntries(pids.flatMap((p) => METRIC_IDS.map((m) => [`bounds/${p}_${m}.json`, readFileSync(path.join(ART, "bounds", `${p}_${m}.json`), "utf-8")])));
  const fetchImpl = (served: Record<string, string>, live: "down" | unknown) =>
    (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.startsWith(API)) {
        if (live === "down") throw new TypeError("fetch failed");
        return new Response(JSON.stringify({ body: JSON.parse(String(init?.body)), live }), { status: 200 });
      }
      const rel = url.replace(/^\/artifacts\//, "");
      return rel in served ? new Response(served[rel]) : new Response("nf", { status: 404 });
    }) as typeof fetch;

  it("sends preset ids for presets and fields + label for a custom side", async () => {
    const c = createClient({ apiUrl: API, fetchImpl: fetchImpl({}, true) });
    const r = await c.compare(resolveSide("iss", CUSTOM), resolveSide("current", CUSTOM));
    expect(r.source).toBe("api");
    expect((r.data as unknown as { body: unknown }).body).toEqual({
      a: "iss",
      b: { g_m_s2: 1.62, p_psia: 8.2, o2: 0.34, u_cm_s: 7, L_mm: 10, label: CURRENT_LABEL },
    });
  });

  it.skipIf(!existsSync(path.join(ART, "bounds", "iss_M1.json")))("offline: preset pair from the bounds artifacts", async () => {
    const c = createClient({ apiUrl: API, fetchImpl: fetchImpl(files(["iss", "lunar_base"]), "down") });
    const r = await c.compare(resolveSide("iss", LUNAR), resolveSide("current", LUNAR));
    expect(r.source).toBe("offline");
    expect(r.data.summary).toBe(FIXTURE.pairs.iss__lunar_base.summary);
  });

  it("offline: a custom side needs the live API (no invented values)", async () => {
    const c = createClient({ apiUrl: API, fetchImpl: fetchImpl({}, "down") });
    const p = c.compare(resolveSide("iss", CUSTOM), resolveSide("current", CUSTOM));
    await expect(p).rejects.toBeInstanceOf(OfflineUnavailableError);
    await expect(p).rejects.toThrow(CUSTOM_COMPARE_NOTE);
  });
});
