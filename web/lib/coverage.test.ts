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

  it("ADR-0006 diluted queries match engine/coverage.py habitat_status (M1 and M2)", () => {
    // [o2, psia, co2, he] -> [covered, nearest_distance] from python -c habitat_status(...) on the same artifacts.
    const cases: [number, number, number, number, boolean, number][] = [
      [0.34, 8.2, 0.05, 0, false, 2.6118], // lunar base + 5% CO2: only CO2 tests count, all at <= 25% O2
      [0.21, 14.7, 0.2, 0, true, 0.501], // ISS + 20% CO2
      [0.21, 14.7, 0, 0.3, true, 1.118], // ISS + 30% He
      [0.21, 14.7, 0.65, 0, false, 2.2596], // ISS + 65% CO2: past the tested fractions
    ];
    for (const m of ["M1", "M2"]) {
      for (const [o2, p, co2, he, covered, d] of cases) {
        const s = coverageStatus(load(m), o2, p, co2, he);
        expect(s.covered, `${m} ${o2} ${p} co2=${co2} he=${he}`).toBe(covered);
        expect(s.nearestDistance).toBeCloseTo(d, 3);
        if (co2 > 0) expect(s.nearest?.co2).toBeGreaterThan(0);
        if (he > 0) expect(s.nearest?.he).toBeGreaterThan(0);
      }
    }
  });

  it("other metrics ignore co2/he", () => {
    expect(coverageStatus(load("M3"), 0.34, 8.2, 0.3, 0)).toEqual(coverageStatus(load("M3"), 0.34, 8.2));
  });

  it("rejects malformed payloads", () => {
    expect(() => normalizeCoverage({})).toThrow();
  });
});
