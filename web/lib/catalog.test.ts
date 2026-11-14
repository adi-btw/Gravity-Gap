import { describe, expect, it } from "vitest";
import { allDois, conditionRows, firstSentences } from "./catalog";
import type { CatalogRecord } from "./types";

describe("catalog helpers", () => {
  it("takes the first two sentences of the PSI objective without list markers", () => {
    const obj = "The primary objectives of this flight experiment are:\nA. Obtain soot-inception limits. Identify temperatures.\nB. More.";
    expect(firstSentences(obj, 2)).toBe("The primary objectives of this flight experiment are: Obtain soot-inception limits.");
    expect(firstSentences("One. Two. Three.", 2)).toBe("One. Two.");
    expect(firstSentences(null)).toBe("");
  });

  it("formats condition ranges including o2_burner_stream and unknown keys", () => {
    const rows = conditionRows({ o2: [0.21, 0.4], pressure_atm: null, flow_cm_s: [20, 20], o2_burner_stream: [0.5, 1] } as unknown as CatalogRecord["conditions"]);
    expect(rows.find((r) => r.key === "o2")?.value).toBe("21.0% – 40.0%");
    expect(rows.find((r) => r.key === "pressure_atm")?.value).toBe("not recorded");
    expect(rows.find((r) => r.key === "flow_cm_s")?.value).toBe("20.0 cm/s");
    expect(rows.find((r) => r.key === "o2_burner_stream")?.label).toMatch(/burner/);
  });

  it("collects de-duplicated dataset and publication DOIs", () => {
    const recs = [
      { id: "PSI-1", acronym: "A", title: "t", doi: "10.1/a", publications: [{ doi: "10.1/p", title: "p" }, { doi: "10.1/A", title: "dup" }] },
      { id: "PSI-2", acronym: "B", title: "t", doi: null, publications: [{ doi: "10.1/p", title: "p again" }] },
    ] as unknown as CatalogRecord[];
    expect(allDois(recs).map((d) => d.doi)).toEqual(["10.1/a", "10.1/p"]);
  });
});
