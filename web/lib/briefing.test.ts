import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  CHIP_TEXT,
  briefingQuery,
  gapsByKind,
  nextTestLine,
  normalizeBriefing,
  resolveBriefingTarget,
  shortHash,
} from "./briefing";
import { presetToHabitat } from "./habitat";
import { PRESETS_BY_ID } from "./presets";

const art = (id: string) => JSON.parse(readFileSync(path.resolve(__dirname, `../../artifacts/briefing/${id}.json`), "utf-8"));
const LUNAR = presetToHabitat(PRESETS_BY_ID.lunar_base);

describe("normalizeBriefing", () => {
  it("accepts every preset artifact", () => {
    for (const id of ["iss", "exploration", "lunar_base", "lunar_rover", "mars_base", "earth"]) {
      const b = normalizeBriefing(art(id));
      expect(b.verdicts.map((c) => c.pillar)).toEqual(["prevention", "behaviour", "detection", "suppression"]);
      expect(b.footer.disclaimer).toMatch(/^Not an operating procedure/);
    }
  });
  it("throws on malformed input", () => {
    expect(() => normalizeBriefing(null)).toThrow(/malformed/);
    const bad = art("lunar_base");
    bad.verdicts[0].value = "safe";
    expect(() => normalizeBriefing(bad)).toThrow(/malformed/);
  });
});

describe("chips do not rely on colour", () => {
  it("every value has a word and a distinct symbol", () => {
    const symbols = Object.values(CHIP_TEXT).map((t) => t.symbol);
    expect(new Set(symbols).size).toBe(3);
    expect(CHIP_TEXT["no evidence"].word).toBe("No evidence");
  });
});

describe("URL state", () => {
  it("?habitat=<preset> wins over the habitat bar", () => {
    const t = resolveBriefingTarget("iss", LUNAR);
    expect(t.presetId).toBe("iss");
    expect(t.habitat.p_psia).toBe(14.7);
  });
  it("falls back to the habitat bar; a preset match resolves to it, else custom", () => {
    expect(resolveBriefingTarget(null, LUNAR).presetId).toBe("lunar_base");
    expect(resolveBriefingTarget("atlantis", LUNAR).presetId).toBe("lunar_base");
    const custom = resolveBriefingTarget(null, { ...LUNAR, u_cm_s: 7 });
    expect(custom.presetId).toBeNull();
    expect(custom.label).toBe("Custom habitat");
  });
  it("briefing link carries the habitat values and the preset id when they match", () => {
    const q = new URLSearchParams(briefingQuery(LUNAR));
    expect(q.get("habitat")).toBe("lunar_base");
    expect(q.get("o2")).toBe("0.34");
    expect(new URLSearchParams(briefingQuery({ ...LUNAR, u_cm_s: 7 })).get("habitat")).toBeNull();
  });
});

describe("helpers", () => {
  it("lunar base gaps: M2, M4, M5 then detection then suppression", () => {
    const g = gapsByKind(normalizeBriefing(art("lunar_base")).gaps);
    expect(g.metric.map((x) => x.id)).toEqual(["M2", "M4", "M5"]);
    expect(g.detection.map((x) => x.id)).toEqual(["lunar_dust", "detector_sensitivity"]);
    expect(g.suppression.every((x) => typeof x.safety_note === "string")).toBe(true);
  });
  it("next-test line copies the planner values", () => {
    const t = normalizeBriefing(art("lunar_base")).next_tests.items[1];
    expect(nextTestLine(t)).toBe("M1 dilution test · 1.62 m/s² · 8.2 psia · 34% O₂ · vent 20 cm/s · 40% CO₂ replacing nitrogen");
  });
  it("short hash only for a hex hash", () => {
    expect(shortHash("2e978155f341403e7bf0f3f9f6d5b795")).toBe("2e978155f341");
    expect(shortHash(null)).toBeNull();
    expect(shortHash("not-a-hash")).toBeNull();
  });
});
