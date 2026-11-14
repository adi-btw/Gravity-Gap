import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  atmosphereDistance,
  buoyantVelocityCmS,
  effectiveFlowCmS,
  evaluate,
  gStar,
  o2PartialPressurePsia,
  regime,
  richardson,
} from "./physics";
import { PRESETS } from "./presets";

type Args = Record<string, number | string | null>;
interface FixtureCase {
  id: string;
  fn: string;
  args: Args;
  expected?: unknown;
  rel_tol?: number;
  abs_tol?: number;
  raises?: unknown;
}

/** Python fixture `fn` name → TS implementation and its positional keyword order. */
const FUNCTIONS: Record<string, { call: (...a: number[]) => unknown; params: string[] }> = {
  buoyant_velocity_cm_s: { call: buoyantVelocityCmS, params: ["g_m_s2", "L_mm", "dT_over_T", "C_b"] },
  richardson: { call: richardson, params: ["u_b_cm_s", "u_f_cm_s"] },
  regime: { call: regime, params: ["ri"] },
  g_star: { call: gStar, params: ["g_m_s2", "p_psia"] },
  o2_partial_pressure_psia: { call: o2PartialPressurePsia, params: ["o2", "p_psia"] },
  effective_flow_cm_s: { call: effectiveFlowCmS, params: ["u_f_cm_s", "u_b_cm_s", "k"] },
  atmosphere_distance: { call: atmosphereDistance, params: ["o2", "p_atm", "o2_t", "p_t_atm"] },
  evaluate: {
    call: evaluate,
    params: ["g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm", "dT_over_T", "C_b", "k"],
  },
};

function toNumber(v: unknown): number {
  if (v === "inf" || v === "Infinity") return Infinity;
  if (v === "-inf") return -Infinity;
  if (v === null) return Infinity; // evaluate() serializes Ri = ∞ as None/null
  return Number(v);
}

function callCase(c: FixtureCase): unknown {
  const entry = FUNCTIONS[c.fn];
  if (!entry) throw new Error(`Unmapped fixture fn "${c.fn}" in case ${c.id}`);
  const positional: number[] = [];
  let lastGiven = -1;
  entry.params.forEach((p, i) => {
    if (p in c.args) lastGiven = i;
  });
  for (let i = 0; i <= lastGiven; i++) {
    const p = entry.params[i];
    // undefined lets the TS default apply, same as an omitted Python keyword
    positional.push(p in c.args ? toNumber(c.args[p]) : (undefined as unknown as number));
  }
  const unknownKeys = Object.keys(c.args).filter((k) => !entry.params.includes(k));
  if (unknownKeys.length) throw new Error(`Case ${c.id}: unknown args ${unknownKeys.join(",")}`);
  return entry.call(...positional);
}

function expectClose(actual: unknown, expected: unknown, relTol: number, absTol: number, label: string) {
  if (typeof expected === "string" && !["inf", "-inf", "Infinity"].includes(expected)) {
    expect(actual, label).toBe(expected);
    return;
  }
  if (expected !== null && typeof expected === "object") {
    for (const [key, val] of Object.entries(expected as Record<string, unknown>)) {
      const got = (actual as Record<string, unknown>)[key];
      if (val === null) {
        expect(got, `${label}.${key}`).toBeNull();
      } else {
        expectClose(got, val, relTol, absTol, `${label}.${key}`);
      }
    }
    return;
  }
  const exp = toNumber(expected);
  const act = actual === null ? Infinity : Number(actual);
  if (!Number.isFinite(exp)) {
    expect(act, label).toBe(exp);
    return;
  }
  const tol = Math.max(relTol * Math.abs(exp), absTol);
  expect(Math.abs(act - exp), `${label}: got ${act}, expected ${exp} ± ${tol}`).toBeLessThanOrEqual(tol);
}

const FIXTURE_PATH = resolve(__dirname, "../../tests/fixtures/physics_reference.json");
const fixtureExists = existsSync(FIXTURE_PATH);
const fixtureCases: FixtureCase[] = fixtureExists
  ? (JSON.parse(readFileSync(FIXTURE_PATH, "utf8")) as { cases: FixtureCase[] }).cases
  : [];

describe("T3 parity with shared fixture tests/fixtures/physics_reference.json", () => {
  if (!fixtureExists) {
    it.skip(`fixture not found at ${FIXTURE_PATH}; inline reference cases still run`, () => {});
    return;
  }
  it("has cases", () => {
    expect(fixtureCases.length).toBeGreaterThan(0);
  });
  for (const c of fixtureCases) {
    it(`${c.id} ${c.fn}`, () => {
      if (c.raises !== undefined && c.raises !== null && c.raises !== false) {
        expect(() => callCase(c)).toThrow();
        return;
      }
      expectClose(callCase(c), c.expected, c.rel_tol ?? 1e-9, c.abs_tol ?? 1e-12, c.id);
    });
  }
});

describe("inline reference cases (plan/08 R1-R5)", () => {
  it("R1 u_b Earth, 10 mm, dT/T 4 ≈ 62.64 cm/s", () => {
    expect(buoyantVelocityCmS(9.81, 10, 4, 1)).toBeCloseTo(62.64, 1);
  });
  it("R2 u_b Moon ≈ 25.46 cm/s", () => {
    expect(buoyantVelocityCmS(1.62, 10, 4, 1)).toBeCloseTo(25.46, 1);
  });
  it("R3 G*(Moon, 8.2 psia) ≈ 0.0514", () => {
    const expected = (1.62 / 9.81) * (8.2 / 14.7) ** 2;
    expect(gStar(1.62, 8.2)).toBeCloseTo(expected, 12);
    expect(gStar(1.62, 8.2)).toBeCloseTo(0.0514, 3);
    expect(gStar(9.81, 14.7)).toBe(1);
  });
  it("R4 u_eff(10, 25.46) ≈ 27.35; Ri ≈ 6.48 → mixed", () => {
    expect(effectiveFlowCmS(10, 25.46)).toBeCloseTo(27.35, 1);
    const ri = richardson(25.46, 10);
    expect(ri).toBeCloseTo(6.48, 1);
    expect(regime(ri)).toBe("mixed");
  });
  it("R5 g = 0, u_f = 10 → Ri 0, forced, u_eff 10", () => {
    const e = evaluate(0, 14.7, 0.21, 10, 10);
    expect(e.ri).toBe(0);
    expect(e.regime).toBe("forced");
    expect(e.u_eff_cm_s).toBe(10);
  });
  it("vent off under gravity → Ri ∞ (null in evaluate), buoyant", () => {
    expect(richardson(25, 0)).toBe(Infinity);
    expect(richardson(0, 0)).toBe(0);
    const e = evaluate(9.81, 14.7, 0.21, 0, 10);
    expect(e.ri).toBeNull();
    expect(e.regime).toBe("buoyant");
  });
  it("regime boundaries are mixed", () => {
    expect(regime(0.0999)).toBe("forced");
    expect(regime(0.1)).toBe("mixed");
    expect(regime(10)).toBe("mixed");
    expect(regime(10.0001)).toBe("buoyant");
  });
  it("p_O2 and atmosphere distance", () => {
    expect(o2PartialPressurePsia(0.34, 8.2)).toBeCloseTo(2.788, 10);
    expect(atmosphereDistance(0.21, 1, 0.21, 1)).toBe(0);
    expect(atmosphereDistance(0.26, 1, 0.21, 1)).toBeCloseTo(1, 12);
  });
  it("rejects invalid inputs like the Python engine", () => {
    expect(() => buoyantVelocityCmS(-1, 10)).toThrow(RangeError);
    expect(() => o2PartialPressurePsia(1.2, 10)).toThrow(RangeError);
    expect(() => atmosphereDistance(0.2, 0, 0.2, 1)).toThrow(RangeError);
  });
});

describe("presets mirror engine/presets.py", () => {
  const presetsPy = resolve(__dirname, "../../engine/presets.py");
  it("has the six contract presets with exact values", () => {
    const byId = Object.fromEntries(PRESETS.map((p) => [p.id, p]));
    expect(PRESETS.map((p) => p.id)).toEqual([
      "iss",
      "exploration",
      "lunar_base",
      "lunar_rover",
      "mars_base",
      "earth",
    ]);
    expect(byId.lunar_rover).toMatchObject({ g_m_s2: 1.62, p_psia: 8.2, o2: 0.34, u_cm_s: 5, L_mm: 10 });
    expect(byId.earth).toMatchObject({ g_m_s2: 9.81, p_psia: 14.7, o2: 0.21, u_cm_s: 0 });
  });
  it.skipIf(!existsSync(presetsPy))("numeric values match engine/presets.py", () => {
    const src = readFileSync(presetsPy, "utf8");
    for (const p of PRESETS) {
      const block = src.split(`"id": "${p.id}"`)[1]?.split("}")[0];
      expect(block, `preset ${p.id} in presets.py`).toBeDefined();
      for (const key of ["g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm"] as const) {
        const m = block!.match(new RegExp(`"${key}":\\s*([0-9.]+)`));
        expect(m, `${p.id}.${key}`).not.toBeNull();
        expect(Number(m![1]), `${p.id}.${key}`).toBe(p[key]);
      }
    }
  });
});
