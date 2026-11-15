import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { createClient, type Sourced } from "./api";
import type { BoundsResult } from "./types";
import {
  basisText,
  drawnSources,
  driversFromArtifact,
  driversSummary,
  normalizeDrivers,
  plannerHref,
  roundShare5,
  shareLabel,
  type DriversApplicable,
} from "./uncertainty";

const ARTIFACT = path.resolve(__dirname, "../../artifacts/uncertainty/lunar_base.json");
const lunar = JSON.parse(readFileSync(ARTIFACT, "utf-8"));

describe("share rounding", () => {
  it("rounds to 5% steps, half to even like the engine", () => {
    expect(roundShare5(0.6604)).toBe(65);
    expect(roundShare5(0.2724)).toBe(25);
    expect(roundShare5(0.03)).toBe(5);
    expect(roundShare5(0.0095)).toBe(0);
    expect(roundShare5(0.025)).toBe(0); // 0.5 -> 0 (half to even, Python round)
    expect(roundShare5(0.075)).toBe(10); // 1.5 -> 2
    expect(roundShare5(Number.NaN)).toBe(0);
  });
  it("labels tiny shares as under 5% and zero as 0%", () => {
    expect(shareLabel(0.6604)).toBe("about 65%");
    expect(shareLabel(0.0037)).toBe("under 5%");
    expect(shareLabel(0)).toBe("0%");
  });
  it("names each basis in words", () => {
    expect(basisText("psi_data")).toBe("from limited NASA tests");
    expect(basisText("honesty_rule")).toBe("honesty rule for gravity");
    expect(basisText("engineering_assumption")).toBe("engineering assumption, not PSI data");
  });
});

describe("normalizeDrivers", () => {
  it("accepts the real lunar base M1 artifact and lists every share for screen readers", () => {
    const d = driversFromArtifact(lunar, "M1") as DriversApplicable;
    expect(d.applicable).toBe(true);
    expect(d.sources.map((s) => s.id)).toEqual(["model_uncertainty", "gravity_widening", "C_b", "k", "dT_over_T", "L_mm", "remainder"]);
    expect(drawnSources(d).map((s) => s.id)).not.toContain("k");
    const sr = driversSummary(d);
    expect(sr).toContain("Model uncertainty (limited tests): about 65% (from limited NASA tests)");
    expect(sr).toContain("Flow-mixing coefficient k: 0%, never reaches this band");
    expect(sr).toContain("Not split (interactions)");
  });
  it("keeps not-applicable metrics without a breakdown", () => {
    const d = driversFromArtifact(lunar, "M2");
    expect(d?.applicable).toBe(false);
    expect(d && "reason" in d && d.reason).toBeTruthy();
  });
  it("rejects malformed input instead of inventing a split", () => {
    expect(normalizeDrivers(null)).toBeNull();
    expect(normalizeDrivers({ metric: "M1", applicable: true, sources: [], band90: [0, 1] })).toBeNull();
    expect(normalizeDrivers({ metric: "M1", applicable: true, band90: [0, 1], sources: [{ id: "x", label: "x", share: "big" }] })).toBeNull();
    expect(driversFromArtifact({}, "M1")).toBeNull();
  });
  it("builds the planner anchor only for a real candidate", () => {
    const c = { rank: 6, metric: "M1", g_m_s2: 3.71, p_psia: 8.2, o2: 0.34, u_cm_s: 20, distance: 1.4 };
    expect(plannerHref(c, "g=1")).toBe("/planner?g=1#candidate-6");
    expect(plannerHref(null, "g=1")).toBeNull();
  });
});

describe("api.drivers", () => {
  const lunarHab = { g_m_s2: 1.62, p_psia: 8.2, o2: 0.34, u_cm_s: 10, L_mm: 10 };
  const base = { metric: "M1", applicable: true } as unknown as BoundsResult;
  it("uses the live drivers field when present", async () => {
    const c = createClient({ fetchImpl: (() => Promise.reject(new Error("no fetch"))) as typeof fetch });
    const bounds: Sourced<BoundsResult> = { data: { ...base, drivers: lunar.metrics.M1 }, source: "api" };
    const r = await c.drivers(lunarHab, "M1", bounds);
    expect(r.source).toBe("api");
  });
  it("falls back to the preset artifact, and refuses for a custom habitat", async () => {
    const c = createClient({
      fetchImpl: (async (url: string) => {
        if (String(url).endsWith("uncertainty/lunar_base.json")) return new Response(JSON.stringify(lunar));
        return new Response("", { status: 404 });
      }) as typeof fetch,
    });
    const bounds: Sourced<BoundsResult> = { data: base, source: "offline" };
    const r = await c.drivers(lunarHab, "M1", bounds);
    expect(r.source).toBe("offline");
    expect(r.data.applicable).toBe(true);
    await expect(c.drivers({ ...lunarHab, p_psia: 8.0 }, "M1", bounds)).rejects.toThrow(/live API/);
  });
});
