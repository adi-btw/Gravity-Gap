import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { coverageStatus, normalizeCoverage, type Coverage } from "./coverage";

const repo = path.resolve(__dirname, "..", "..");
const load = (m: string): Coverage =>
  normalizeCoverage(JSON.parse(readFileSync(path.join(repo, "artifacts", "coverage", `${m}.json`), "utf-8")));

describe("coverageStatus mirrors engine/coverage.py", () => {
  it("lunar base (8.2 psia, 34% O2): M1/M3 covered, M2/M4/M5 not", () => {
    const got = Object.fromEntries(["M1", "M2", "M3", "M4", "M5"].map((m) => [m, coverageStatus(load(m), 0.34, 8.2).covered]));
    expect(got).toEqual({ M1: true, M2: false, M3: true, M4: false, M5: false });
  });

  it("M2 nearest tested atmosphere is just past the distance-2 gate", () => {
    const s = coverageStatus(load("M2"), 0.34, 8.2);
    expect(s.nearestDistance).toBeGreaterThan(2);
    expect(s.nearestDistance).toBeLessThan(2.3);
    expect(s.nearest?.investigation_id).toBe("PSI-69");
  });

  it("ISS air (14.7 psia, 21% O2) is inside the SAFFIRE and SPICE boxes", () => {
    expect(coverageStatus(load("M4"), 0.21, 14.7).covered).toBe(true);
    expect(coverageStatus(load("M5"), 0.21, 14.7).covered).toBe(true);
  });

  it("rejects malformed payloads", () => {
    expect(() => normalizeCoverage({})).toThrow();
  });
});
