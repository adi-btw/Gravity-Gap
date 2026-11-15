import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { createClient } from "./api";
import {
  binMaterials,
  fmtNm,
  fmtShare,
  fmtTickNm,
  jitter,
  logDomain,
  logScale,
  logTicks,
  mentionsLunar,
  normalizeDetection,
  pickBinSeries,
  simCases,
  simForCase,
  sourceText,
} from "./detection";

const repo = path.resolve(__dirname, "..", "..");
const raw = () => JSON.parse(readFileSync(path.join(repo, "artifacts", "detection.json"), "utf-8"));

describe("normalizeDetection", () => {
  it("accepts the real artifact unchanged in size", () => {
    const d = normalizeDetection(raw());
    expect(d.smoke_bins).toHaveLength(6);
    expect(d.simulation).toHaveLength(6);
    expect(d.smoke_runs.points).toHaveLength(100);
    expect(d.average_mass_comparison.smoke.points).toHaveLength(100);
    expect(d.average_mass_comparison.dust.points).toHaveLength(3);
    expect(d.gaps).toHaveLength(10);
    expect(d.gaps[0].id).toBe("lunar_dust");
  });

  it("rejects payloads that are not the detection artifact", () => {
    expect(() => normalizeDetection(null)).toThrow(/malformed/);
    expect(() => normalizeDetection([])).toThrow(/malformed/);
    expect(() => normalizeDetection({ smoke_bins: [], simulation: [] })).toThrow(/malformed/);
    const r = raw();
    delete r.average_mass_comparison;
    expect(() => normalizeDetection(r)).toThrow(/malformed/);
  });

  it("drops undrawable series and points instead of inventing values", () => {
    const r = raw();
    r.smoke_bins[0].fraction = r.smoke_bins[0].fraction.slice(1); // length mismatch
    r.simulation[0].diameter_nm[0] = 0; // not on a log axis
    r.simulation[1].is_simulation = false; // contract: simulation curves are flagged
    r.smoke_runs.points[0].value_nm = null;
    r.average_mass_comparison.dust.points[0].value_nm = -1;
    const d = normalizeDetection(r);
    expect(d.smoke_bins).toHaveLength(5);
    expect(d.simulation).toHaveLength(4);
    expect(d.smoke_runs.points).toHaveLength(99);
    expect(d.average_mass_comparison.dust.points).toHaveLength(2);
  });

  it("puts lunar_dust first whatever the order", () => {
    const r = raw();
    r.gaps.reverse();
    expect(normalizeDetection(r).gaps[0].id).toBe("lunar_dust");
  });

  it("no series label, id or material mentions lunar; the dust is Arizona Road Dust", () => {
    const d = normalizeDetection(raw());
    expect(mentionsLunar(d)).toEqual([]);
    expect(d.average_mass_comparison.dust.label).toBe("Arizona Road Dust (DAFT)");
    const r = raw();
    r.smoke_bins[0].label = "Lunar dust";
    expect(mentionsLunar(normalizeDetection(r))).toEqual([r.smoke_bins[0].id]);
  });

  it("each chart series has exactly one size definition", () => {
    const d = normalizeDetection(raw());
    expect(new Set(d.smoke_bins.map((s) => s.size_definition))).toEqual(new Set(["tem_image_diameter"]));
    expect(new Set(d.simulation.map((s) => s.size_definition))).toEqual(new Set(["simulation_node_diameter"]));
    expect(d.average_mass_comparison.size_definition).toBe("diameter_of_average_mass");
  });
});

describe("chart helpers", () => {
  it("logDomain snaps to decades", () => {
    expect(logDomain([9.9, 1511])).toEqual([1, 10000]);
    expect(logDomain([100, 1000])).toEqual([100, 1000]);
    expect(logDomain([100])).toEqual([100, 1000]);
    expect(logDomain([0, -1])).toEqual([1, 10]);
  });

  it("logScale maps decades evenly", () => {
    const x = logScale([1, 1000], [0, 300]);
    expect(x(1)).toBeCloseTo(0);
    expect(x(10)).toBeCloseTo(100);
    expect(x(1000)).toBeCloseTo(300);
  });

  it("logTicks lists the powers of ten inside the domain", () => {
    expect(logTicks([1, 10000])).toEqual([1, 10, 100, 1000, 10000]);
  });

  it("formats nm, ticks, shares and sources", () => {
    expect(fmtTickNm(10000)).toBe("10,000");
    expect(fmtNm(191.736)).toBe("192 nm");
    expect(fmtNm(1716.39)).toBe("1,720 nm");
    expect(fmtShare(0.00379832)).toBe("0.38%");
    expect(fmtShare(0)).toBe("0%");
    expect(fmtShare(0.2776)).toBe("27.8%");
    expect(sourceText({ investigation_id: "PSI-101", file: "a.xlsx", sheet: "Binned data", rows: "15-44" })).toBe(
      "PSI-101 · a.xlsx · sheet “Binned data” · rows 15-44",
    );
    expect(sourceText({ investigation_id: "PSI-115", file: "b.dat", sheet: null, rows: "1-44" })).toBe("PSI-115 · b.dat · rows 1-44");
  });

  it("jitter is deterministic and bounded", () => {
    for (let i = 0; i < 50; i++) {
      expect(Math.abs(jitter(i))).toBeLessThanOrEqual(1);
      expect(jitter(i)).toBe(jitter(i));
    }
  });

  it("material picker options and series selection come from the artifact", () => {
    const d = normalizeDetection(raw());
    expect(binMaterials(d).map((m) => m.label)).toEqual(["Cotton lamp wick", "Silicone", "Kapton"]);
    expect(pickBinSeries(d, "Silicone", "big_only")?.id).toBe("tem_silicone_60_big_only");
    expect(pickBinSeries(d, "Kapton", "all")?.id).toBe("tem_kapton_62_all");
    expect(pickBinSeries(d, "Teflon", "all")).toBeNull();
  });

  it("simulation cases: base curves Earth then micro; variants only on request", () => {
    const d = normalizeDetection(raw());
    expect(simCases(d).map((c) => c.case)).toEqual(["1", "2"]);
    expect(simForCase(d, "1", false).map((s) => s.id)).toEqual(["psi115_case1_earth", "psi115_case1_micro"]);
    expect(simForCase(d, "1", true)).toHaveLength(4);
    expect(simForCase(d, "2", true).map((s) => s.id)).toEqual(["psi115_case2_earth", "psi115_case2_micro"]);
  });
});

describe("api.detection", () => {
  const API = "http://api.test";
  function fetchWith(apiStatus: number | "down") {
    const calls: string[] = [];
    const impl = (async (input: RequestInfo | URL) => {
      const url = String(input);
      calls.push(url);
      if (url.startsWith(API)) {
        if (apiStatus === "down") throw new TypeError("fetch failed");
        return apiStatus === 200 ? new Response(JSON.stringify(raw())) : new Response("{}", { status: apiStatus });
      }
      if (url === "/artifacts/detection.json") return new Response(JSON.stringify(raw()));
      return new Response("not found", { status: 404 });
    }) as typeof fetch;
    return { impl, calls };
  }

  it("uses GET /detection when it answers", async () => {
    const { impl, calls } = fetchWith(200);
    const r = await createClient({ apiUrl: API, fetchImpl: impl }).detection();
    expect(r.source).toBe("api");
    expect(calls).toEqual([`${API}/detection`]);
  });

  it.each([404, 503, "down"] as const)("falls back to the bundled artifact when the API gives %s", async (status) => {
    const { impl, calls } = fetchWith(status);
    const r = await createClient({ apiUrl: API, fetchImpl: impl }).detection();
    expect(r.source).toBe("offline");
    expect(r.data.smoke_bins).toHaveLength(6);
    expect(calls[1]).toBe("/artifacts/detection.json");
  });
});
