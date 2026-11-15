import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  bandText,
  fmtCount,
  fmtInterval,
  groupMark,
  mapPoints,
  markCounts,
  normalizeHoldout,
  observedText,
  skipReasons,
  worstMissRows,
  type HoldoutGroup,
} from "./holdout";

const raw = JSON.parse(readFileSync(path.resolve(__dirname, "../../artifacts/holdout.json"), "utf-8"));

describe("normalizeHoldout", () => {
  it("accepts the real artifact", () => {
    const d = normalizeHoldout(raw);
    expect(Object.keys(d.metrics)).toEqual(["M1", "M2", "M3"]);
    expect(fmtCount(d.overall.band_coverage)).toBe(`${raw.overall.band_coverage.k} of ${raw.overall.band_coverage.n}`);
    expect(d.wide_check?.metrics.M3.summary.weak_test).toBe(raw.wide_check.metrics.M3.summary.weak_test);
    expect(d.saffire_hindcast?.caveat).toMatch(/Not discriminative/);
  });
  it("throws on malformed input", () => {
    expect(() => normalizeHoldout(null)).toThrow(/malformed/);
    expect(() => normalizeHoldout({ metrics: {}, overall: {} })).toThrow(/malformed/);
    expect(() => normalizeHoldout({ metrics: { M1: { groups: "x" } }, overall: {} })).toThrow(/malformed/);
  });
  it("tolerates a missing wide check and SAFFIRE section", () => {
    const d = normalizeHoldout({ ...raw, wide_check: undefined, saffire_hindcast: undefined });
    expect(d.wide_check).toBeNull();
    expect(d.saffire_hindcast).toBeNull();
  });
});

describe("map marks and counts", () => {
  const g = (over: Partial<HoldoutGroup>) => ({ status: "evaluated", covered: true, hit: true, ...over }) as HoldoutGroup;
  it("maps hit / miss / no evidence / skipped", () => {
    expect(groupMark(g({})).mark).toBe("hit");
    expect(groupMark(g({ hit: false })).mark).toBe("miss");
    expect(groupMark(g({ covered: false, hit: null }))).toEqual({ mark: "grey", greyReason: "no_evidence" });
    expect(groupMark(g({ status: "skipped", covered: null, hit: null }))).toEqual({ mark: "grey", greyReason: "skipped" });
  });
  it("counts every wide-check M3 group, skipped ones with their reason", () => {
    const r = normalizeHoldout(raw).wide_check!.metrics.M3;
    const c = markCounts(mapPoints(r));
    expect(c.hit + c.miss + c.noEvidence + c.skipped).toBe(r.summary.n_groups);
    expect(c.skipped).toBe(r.summary.n_skipped);
    expect(c.noEvidence).toBe(r.summary.n_not_covered);
    expect(skipReasons(r).reduce((s, x) => s + x.n, 0)).toBe(r.summary.n_skipped);
  });
  it("joins worst misses to their PSI rows", () => {
    const rows = worstMissRows(normalizeHoldout(raw).metrics.M1);
    expect(rows.length).toBe(raw.metrics.M1.summary.worst_misses.length);
    expect(rows[0].group?.psi_rows[0].record_id).toMatch(/^PSI-69:FLEX:/);
  });
});

describe("formatting", () => {
  it("formats intervals, bands and observed results", () => {
    expect(fmtInterval([0.90449, 0.958862])).toBe("90–96%");
    expect(fmtCount({ k: 0, n: 0, rate: null, interval90: null })).toBe("no groups");
    expect(bandText("probability", [0.688, 0.919])).toBe("69%–92%");
    expect(bandText("quantity", [1.7748, 2.7432])).toBe("1.77–2.74 mm");
    expect(observedText({ positives: 0, n: 2, rate: 0, interval90: [0, 0.57] })).toBe("0 of 2 self-extinguished");
    expect(observedText({ n: 3, median: 1.52, min: 1.34, max: 3.22, values: [] })).toBe("median 1.52 mm (3 tests)");
  });
});
