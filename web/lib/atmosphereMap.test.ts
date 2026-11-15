import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  VIRIDIS,
  cellAt,
  cellFill,
  cellHabitat,
  colourDomain,
  crewDash,
  crewLineGeometry,
  crewTag,
  edges,
  groupMarkers,
  isHatched,
  legendTicks,
  makeScales,
  mapQuery,
  moveCell,
  nearestCellIndex,
  normalizeAtmosphereMap,
  parseGravity,
  parseMetric,
  viridis,
  type CrewLimit,
} from "./atmosphereMap";

const load = (m: string, g: string) =>
  normalizeAtmosphereMap(JSON.parse(readFileSync(path.resolve(__dirname, `../../artifacts/atmosphere_map/${m}_${g}.json`), "utf-8")));
const M1 = load("M1", "lunar");
const M2 = load("M2", "lunar");
const BOX = { left: 0, top: 0, width: 100, height: 100 };

describe("normalize and lookup", () => {
  it("accepts the artifact (26 x 20 cells, row-major by pressure)", () => {
    expect(M1.cells).toHaveLength(520);
    const c = cellAt(M1, 3, 5)!;
    expect([c.i, c.j]).toEqual([3, 5]);
    expect(c.o2).toBe(M1.axes.x.values[3]);
  });
  it("throws on malformed input", () => {
    expect(() => normalizeAtmosphereMap({ cells: [] })).toThrow(/malformed/);
  });
});

describe("colour scale and hatch rule", () => {
  it("viridis runs from the first to the last stop and clamps", () => {
    expect(viridis(0)).toBe(VIRIDIS[0]);
    expect(viridis(1)).toBe(VIRIDIS[VIRIDIS.length - 1]);
    expect(viridis(-3)).toBe(VIRIDIS[0]);
    expect(viridis(0.5)).toBe(VIRIDIS[4]);
  });
  it("uncovered cells are hatched and get no colour; covered cells get one", () => {
    const d = colourDomain(M1);
    for (const c of M1.cells) {
      expect(isHatched(c)).toBe(!c.covered);
      expect(cellFill(c, d) === null).toBe(!c.covered);
    }
    expect(M1.cells.filter((c) => !isHatched(c))).toHaveLength(M1.summary.n_covered);
  });
  it("legend: % for probabilities, mm over the covered range for M2", () => {
    expect(colourDomain(M1)).toEqual([0, 1]);
    expect(legendTicks(M1, [0, 1]).map((t) => t.label)).toEqual(["0%", "25%", "50%", "75%", "100%"]);
    const d2 = colourDomain(M2);
    const est = M2.cells.filter((c) => c.covered).map((c) => c.estimate as number);
    expect(d2).toEqual([Math.min(...est), Math.max(...est)]);
    expect(legendTicks(M2, d2)[0].label).toMatch(/ mm$/);
  });
});

describe("geometry", () => {
  it("cell edges: linear midpoints for O2, geometric midpoints for pressure", () => {
    const xe = edges([0.15, 0.16, 0.17], "linear");
    expect(xe.map((v) => Number(v.toFixed(6)))).toEqual([0.145, 0.155, 0.165, 0.175]);
    const ye = edges([4, 16], "log");
    expect(ye[1]).toBeCloseTo(8, 9);
    expect(ye[0]).toBeCloseTo(2, 9);
  });
  it("crew lines come straight from the artifact polylines", () => {
    const s = makeScales(M1, BOX);
    const drawn = M1.overlays.crew_limits!.drawn as CrewLimit[];
    const curve = drawn.find((c) => c.id === "pio2_mild_hypoxia_lower_limit")!;
    const g = crewLineGeometry(curve, s)!;
    expect(g.kind).toBe("path");
    const pts = g.d!.split(/[ML]/).filter((t) => t.trim()).map((t) => t.trim().split(" ").map(Number));
    expect(pts).toHaveLength(curve.polyline!.length);
    expect(pts[0][0]).toBeCloseTo(s.x(curve.polyline![0][0]), 1);
    expect(pts[0][1]).toBeCloseTo(s.y(curve.polyline![0][1]), 1);
    const band = drawn.find((c) => c.shape === "band")!;
    expect(crewLineGeometry(band, s)!.kind).toBe("area");
    const point = drawn.find((c) => c.shape === "point")!;
    expect(crewLineGeometry(point, s)).toMatchObject({ kind: "point", cx: s.x(point.point![0]), cy: s.y(point.point![1]) });
  });
  it("crew tags and dashes follow the brief", () => {
    const by = Object.fromEntries((M1.overlays.crew_limits!.drawn as CrewLimit[]).map((c) => [c.id, c]));
    expect(crewTag(by.pio2_mild_hypoxia_lower_limit)).toBe("limit");
    expect(crewDash(by.pio2_mild_hypoxia_lower_limit)).toBeUndefined();
    expect(crewTag(by.pio2_absolute_hypoxia_floor)).toBe("absolute floor");
    expect(crewDash(by.pio2_absolute_hypoxia_floor)).toBeDefined();
    expect(crewTag(by.pio2_normoxia_target_low)).toBe("target, not a limit");
    expect(crewTag(by.o2_max_lsam_2007_baseline)).toBe("2007 program baseline (materials)");
    expect(crewTag(by.o2_max_orion_2007_baseline)).toBe("2007 program baseline (materials)");
    expect(M1.overlays.crew_limits!.not_drawn.map((c) => c.id)).toEqual(["o2_max_from_min_diluent"]);
  });
  it("presets that share an atmosphere share one labelled marker", () => {
    const groups = groupMarkers(M1.overlays.presets);
    const lunar = groups.find((g) => g.o2 === 0.34 && g.p_psia === 8.2)!;
    expect(lunar.items.map((i) => i.id).sort()).toEqual(["lunar_base", "lunar_rover", "mars_base"]);
    expect(groupMarkers(M1.overlays.incidents).flatMap((g) => g.items.map((i) => i.id))).not.toContain("apollo1");
  });
});

describe("URL state and keyboard", () => {
  it("metric and gravity params", () => {
    expect(parseMetric("M3")).toBe("M3");
    expect(parseMetric("M4")).toBe("M1");
    expect(parseGravity("mars")).toBe("mars");
    expect(parseGravity(null, 0)).toBe("orbit");
    expect(parseGravity("venus", 2.5)).toBe("lunar");
    const q = new URLSearchParams(mapQuery("g=1.62&p=8.2", "M2", "earth"));
    expect([q.get("metric"), q.get("gravity"), q.get("p")]).toEqual(["M2", "earth", "8.2"]);
  });
  it("a clicked cell loads its O2, pressure and the map gravity; vent and flame size stay", () => {
    const h = cellHabitat({ o2: 0.29, p_psia: 8.925 }, "mars", { g_m_s2: 0, p_psia: 14.7, o2: 0.21, u_cm_s: 5, L_mm: 20 });
    expect(h).toEqual({ g_m_s2: 3.71, p_psia: 8.925, o2: 0.29, u_cm_s: 5, L_mm: 20 });
  });
  it("arrow keys move and clamp at the edges; up is higher pressure", () => {
    expect(moveCell(0, 0, "ArrowLeft", 26, 20)).toEqual([0, 0]);
    expect(moveCell(0, 0, "ArrowUp", 26, 20)).toEqual([0, 1]);
    expect(moveCell(5, 19, "ArrowUp", 26, 20)).toEqual([5, 19]);
    expect(moveCell(5, 3, "End", 26, 20)).toEqual([25, 3]);
    expect(nearestCellIndex(M1, 0.34, 8.2)).toEqual([19, 10]);
  });
});
