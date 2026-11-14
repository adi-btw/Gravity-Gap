import { describe, expect, it } from "vitest";
import { CUSTOM_SUPPRESSION_NOTE, OfflineUnavailableError, createClient } from "./api";
import { presetToHabitat } from "./habitat";
import { PRESETS_BY_ID } from "./presets";
import {
  DOSE_NOT_REACHED,
  doseLabel,
  fmtPct,
  layoutCurve,
  normalizeReference,
  normalizeSuppression,
  parseBand,
  parseDiluent,
  referenceFor,
  summaryLine,
  wilson90,
} from "./suppression";

const API = "http://api.test";
const ISS = presetToHabitat(PRESETS_BY_ID.iss);

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function fakeFetch(api: ((url: string, init?: RequestInit) => Response) | "down", files: Record<string, unknown> = {}) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const impl = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, init });
    if (url.startsWith(API)) {
      if (api === "down") throw new TypeError("fetch failed");
      return api(url, init);
    }
    const rel = url.replace(/^\/artifacts\//, "");
    if (rel in files) return json(files[rel]);
    return new Response("not found", { status: 404 });
  }) as typeof fetch;
  return { impl, calls };
}

const ok = (estimate: number, band: [number, number]) => ({ applicable: true, estimate, band90: band, reason: null });
const gated = (reason = "Extrapolation: no evidence.") => ({ applicable: false, estimate: null, band90: null, reason });

/** Contract-shaped curve (plan/contracts.md R2): applicable, gap, applicable again, trailing gap. */
const CURVE = {
  diluent: "co2",
  label: "Carbon dioxide (CO2)",
  habitat: { g_m_s2: 0, p_psia: 14.7, o2: 0.21, u_cm_s: 10, L_mm: 10 },
  points: [
    { fraction: 0, M1: ok(0.5, [0.3, 0.7]), M2: ok(4, [3, 5]) },
    { fraction: 0.1, M1: ok(0.7, [0.5, 0.85]), M2: ok(4.2, [3.1, 5.2]) },
    { fraction: 0.2, M1: gated(), M2: gated() },
    { fraction: 0.3, M1: ok(0.92, [0.8, 0.97]), M2: ok(4.6, [3.5, 5.6]) },
    { fraction: 0.4, M1: gated(), M2: gated() },
    { fraction: 0.5, M1: gated("composition over 100%"), M2: gated() },
  ],
  dose_for_p90: { fraction: 0.3, metric: "M1" },
  tested: [{ o2: 0.14, p_atm: 1, fraction: 0.36, n: 2, extinctions: 2 }],
  tested_o2_range: [0.14, 0.24],
  gate_note: "FLEX tested CO₂ dilution only between 14% and 24% O₂.",
  safety_note: "CO₂ is dangerous to breathe.",
  model_version: "m1",
};

const LUNAR_CURVE = {
  ...CURVE,
  habitat: { g_m_s2: 1.62, p_psia: 8.2, o2: 0.34, u_cm_s: 10, L_mm: 10 },
  points: [
    { fraction: 0, M1: ok(0.2, [0.01, 0.68]), M2: gated() },
    ...[0.05, 0.1, 0.15].map((f) => ({ fraction: f, M1: gated(), M2: gated() })),
  ],
  dose_for_p90: null,
};

describe("suppression data layer", () => {
  it("POSTs the habitat and diluent to the live API", async () => {
    const { impl, calls } = fakeFetch(() => json(CURVE));
    const r = await createClient({ apiUrl: API, fetchImpl: impl }).suppression(ISS, "co2");
    expect(r.source).toBe("api");
    expect(r.data.points).toHaveLength(6);
    expect(calls[0].url).toBe(`${API}/suppression`);
    expect(calls[0].init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({ g_m_s2: 0, p_psia: 14.7, o2: 0.21, u_cm_s: 10, L_mm: 10, diluent: "co2" });
  });

  it("falls back to the preset artifact when the API is down or the endpoint 404s", async () => {
    for (const api of ["down", () => new Response("", { status: 404 })] as const) {
      const { impl, calls } = fakeFetch(api, { "suppression/iss_he.json": { ...CURVE, diluent: "he" } });
      const r = await createClient({ apiUrl: API, fetchImpl: impl }).suppression(ISS, "he");
      expect(r.source).toBe("offline");
      expect(r.data.diluent).toBe("he");
      expect(r.note).toMatch(/ISS preset/);
      expect(calls[1].url).toBe("/artifacts/suppression/iss_he.json");
    }
  });

  it("a custom habitat offline needs the live API (no invented curve)", async () => {
    const { impl, calls } = fakeFetch("down", { "suppression/iss_co2.json": CURVE });
    const custom = { ...ISS, u_cm_s: 7 };
    const p = createClient({ apiUrl: API, fetchImpl: impl }).suppression(custom, "co2");
    await expect(p).rejects.toBeInstanceOf(OfflineUnavailableError);
    await expect(p).rejects.toThrow(CUSTOM_SUPPRESSION_NOTE);
    expect(calls).toHaveLength(1);
  });

  it("reference: live, then the bundled artifact offline", async () => {
    const ref = { tables: { co2: { Heptane: { "0.17_0.22": { o2_band: "0.17 < O2 <= 0.22", n: 9, bins: [{ fraction_range: [0.05, 0.1], n: 9, extinctions: 5, extinction_rate: 1, interval90: [0.65, 1], record_ids: ["PSI-69:FLEX:148"] }] } } } } };
    const live = await createClient({ apiUrl: API, fetchImpl: fakeFetch(() => json(ref)).impl }).suppressionReference();
    expect(live.source).toBe("api");
    expect(live.data.bins).toHaveLength(1);
    const off = await createClient({ apiUrl: API, fetchImpl: fakeFetch("down", { "suppression_reference.json": ref }).impl }).suppressionReference();
    expect(off.source).toBe("offline");
    expect(off.data.bins[0].interval).toEqual([0.65, 1]);
  });
});

describe("gap logic", () => {
  const c = normalizeSuppression(CURVE);

  it("never joins a line across a non-applicable point", () => {
    const { segments, gaps } = layoutCurve(c.points, "M1");
    expect(segments.map((s) => s.map((v) => v.fraction))).toEqual([[0, 0.1], [0.3]]);
    // Gap around 0.2 spans half-way to both neighbours; the trailing gap runs to the end.
    expect(gaps).toEqual([
      { from: 0.15000000000000002, to: 0.25, reason: "Extrapolation: no evidence." },
      { from: 0.35, to: 0.5, reason: "Extrapolation: no evidence." },
    ]);
    for (const s of segments) for (const v of s) expect(v.fraction).not.toBe(0.2);
  });

  it("treats a point without an estimate, or without an explicit applicable flag, as no evidence", () => {
    const n = normalizeSuppression({
      points: [
        { fraction: 0, M1: { estimate: 0.5, band90: [0.4, 0.6] } },
        { fraction: 0.1, M1: { applicable: true, estimate: null } },
        { fraction: 0.2, M1: { applicable: true, estimate: 0.8, band90: [0.7, 0.9] } },
      ],
    });
    const { segments, gaps } = layoutCurve(n.points, "M1");
    expect(segments.map((s) => s.map((v) => v.fraction))).toEqual([[0.2]]);
    expect(gaps).toHaveLength(1);
    expect(gaps[0]).toMatchObject({ from: 0, to: 0.15000000000000002 });
  });

  it("lunar base: only the undiluted point is drawn", () => {
    const { segments, gaps } = layoutCurve(normalizeSuppression(LUNAR_CURVE).points, "M1");
    expect(segments).toEqual([[{ fraction: 0, estimate: 0.2, band: [0.01, 0.68] }]]);
    expect(gaps).toEqual([{ from: 0.025, to: 0.15, reason: "Extrapolation: no evidence." }]);
  });
});

describe("labels", () => {
  it("formats the dose label", () => {
    expect(doseLabel({ fraction: 0.3, metric: "M1" }, "co2")).toBe("~30% CO₂ reaches 90%");
    expect(doseLabel({ fraction: 0.032143, metric: "M1" }, "he")).toBe("~3.2% helium reaches 90%");
    expect(doseLabel({ fraction: 0, metric: "M1" }, "co2")).toBe("already ≥90% with no CO₂ added");
    expect(doseLabel(null, "co2")).toBe(DOSE_NOT_REACHED);
    expect(DOSE_NOT_REACHED).toMatch(/not reached inside tested conditions/);
  });

  it("formats fractions", () => {
    expect(fmtPct(0.25)).toBe("25%");
    expect(fmtPct(0.05)).toBe("5%");
    expect(fmtPct(0.064286)).toBe("6.4%");
    expect(fmtPct(0.128571)).toBe("13%");
  });

  it("builds the summary from the data", () => {
    expect(summaryLine(normalizeSuppression(CURVE), "ISS air", 0.21)).toMatch(/^At ISS air \(21% O₂\), about 30% CO₂ gives a 90% chance/);
    expect(summaryLine(normalizeSuppression(LUNAR_CURVE), "lunar base", 0.34)).toBe(
      "At lunar base (34% O₂) there is no evidence for any CO₂ dilution: FLEX tested CO₂ dilution only between 14% and 24% O₂.",
    );
    expect(summaryLine(normalizeSuppression({ ...CURVE, dose_for_p90: null }), "ISS air", 0.21)).toMatch(/not reached inside tested conditions/);
  });

  it("parses the diluent query value", () => {
    expect(parseDiluent("he")).toBe("he");
    expect(parseDiluent("co2")).toBe("co2");
    expect(parseDiluent("xenon")).toBe("co2");
    expect(parseDiluent(null)).toBe("co2");
  });
});

describe("empirical reference", () => {
  const raw = {
    max_diluted_o2: 0.25,
    tables: {
      co2: {
        Heptane: {
          "le_0.17": { n: 0, bins: [] },
          "0.17_0.22": {
            o2_band: "0.17 < O2 <= 0.22",
            n: 31,
            bins: [
              { bin: "0", fraction_range: [0, 0], n: 22, extinctions: 8, extinction_rate: 0.571429, interval90: [0.36, 0.76], o2_range: [0.18, 0.21], record_ids: ["a"] },
              { bin: "(0, 0.1]", fraction_range: [0.05, 0.1], n: 9, extinctions: 5, extinction_rate: 1, interval90: [0.65, 1], o2_range: [0.19, 0.2], record_ids: ["b"] },
            ],
          },
          "gt_0.22": { o2_band: "O2 > 0.22", n: 2, bins: [{ fraction_range: [0.2, 0.2], n: 2, extinctions: 1, extinction_rate: 0.5 }] },
        },
        Methanol: { "0.17_0.22": { n: 1, bins: [{ fraction_range: [0.1, 0.2], n: 1, extinctions: 1, extinction_rate: 1, interval90: null }] } },
      },
      he: { Heptane: { "0.17_0.22": { n: 3, bins: [{ fraction_range: [0.1, 0.2], n: 3, extinctions: 2, extinction_rate: 0.66, interval90: [0.2, 0.9] }] } } },
    },
    trend: { co2: { Heptane: { "0.17_0.22": { sequence: [{ bin: "0", extinction_rate: 0.5, rated_n: 14 }] } } } },
  };

  it("flattens DE's tables into bins with fuel, O2 band and interval", () => {
    const ref = normalizeReference(raw);
    expect(ref.bins).toHaveLength(5);
    const b = ref.bins.find((x) => x.fuel === "Heptane" && x.fraction[1] === 0.1);
    expect(b).toMatchObject({ diluent: "co2", o2_band: [0.17, 0.22], n: 9, extinction_rate: 1, interval: [0.65, 1], interval_source: "artifact" });
    expect(ref.bins.find((x) => x.fuel === "Methanol")?.interval_source).toBe("wilson90");
  });

  it("matches the habitat O2 band and drops bins above the dilution ceiling", () => {
    const ref = normalizeReference(raw);
    const iss = referenceFor(ref, "co2", 0.21, [0.14, 0.24]);
    expect(iss.map((b) => `${b.fuel}:${b.fraction.join("-")}`)).toEqual(["Heptane:0-0", "Heptane:0.05-0.1", "Methanol:0.1-0.2"]);
    expect(referenceFor(ref, "co2", 0.34, [0.14, 0.24])).toEqual([]);
    expect(referenceFor(ref, "he", 0.21, [0.13, 0.24])).toHaveLength(1);
  });

  it("parses band ids and labels", () => {
    expect(parseBand("le_0.17")).toEqual([0, 0.17]);
    expect(parseBand("gt_0.22")).toEqual([0.22, 1]);
    expect(parseBand("0.17_0.22")).toEqual([0.17, 0.22]);
    expect(parseBand("0.17 < O2 <= 0.22")).toEqual([0.17, 0.22]);
    expect(parseBand("O2 > 0.22")).toEqual([0.22, 1]);
  });

  it("Wilson 90% interval brackets the rate", () => {
    const [lo, hi] = wilson90(5, 9) as [number, number];
    expect(lo).toBeLessThan(5 / 9);
    expect(hi).toBeGreaterThan(5 / 9);
    expect(wilson90(0, 0)).toBeNull();
  });
});

// Real artifacts (when built): the page's numbers come from these files offline.
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

const ART = path.resolve(__dirname, "..", "..", "artifacts");
const read = (rel: string) => JSON.parse(readFileSync(path.join(ART, rel), "utf-8"));

describe.skipIf(!existsSync(path.join(ART, "suppression", "iss_co2.json")))("real suppression artifacts", () => {
  it("ISS CO2 has a drawn curve and a dose; lunar base has no diluted evidence", () => {
    const iss = normalizeSuppression(read("suppression/iss_co2.json"));
    expect(layoutCurve(iss.points, "M1").segments.flat().length).toBeGreaterThan(3);
    expect(doseLabel(iss.dose_for_p90, "co2")).not.toBe("");
    const lunar = normalizeSuppression(read("suppression/lunar_base_co2.json"));
    expect(lunar.points.filter((p) => p.fraction > 0).every((p) => !p.M1.applicable && !p.M2.applicable)).toBe(true);
    expect(summaryLine(lunar, "lunar base", 0.34)).toMatch(/no evidence/);
  });
});

describe.skipIf(!existsSync(path.join(ART, "suppression_reference.json")))("real reference artifact", () => {
  it("flattens into bins and ISS air gets reference dots", () => {
    const ref = normalizeReference(read("suppression_reference.json"));
    expect(ref.bins.length).toBeGreaterThan(5);
    expect(ref.bins.every((b) => b.fuel && b.o2_band[1] > b.o2_band[0])).toBe(true);
    expect(referenceFor(ref, "co2", 0.21, [0.14, 0.24]).length).toBeGreaterThan(0);
    expect(referenceFor(ref, "co2", 0.34, [0.14, 0.24])).toEqual([]);
  });
});
