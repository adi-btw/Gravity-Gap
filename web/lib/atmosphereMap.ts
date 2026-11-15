/**
 * S5 atmosphere evidence map (plan/contracts.md "Round 3 · S5 Atmosphere map addendum", ADR-0011).
 *
 * Types for artifacts/atmosphere_map/{metric}_{gravity}.json (GET /atmosphere-map/{metric}?g= serves it unchanged),
 * the normalize guard, and pure helpers for the /atmospheres page: axes and cell edges, the colour-blind-safe
 * sequential scale (viridis), the hatch rule, crew-line geometry and URL state. The map never ranks atmospheres:
 * nothing here scores, orders or picks a cell.
 */
import type { Habitat } from "./habitat";

export type MapMetric = "M1" | "M2" | "M3";
export type MapGravity = "orbit" | "lunar" | "mars" | "earth";

export const MAP_METRICS: readonly { id: MapMetric; label: string }[] = [
  { id: "M1", label: "Droplet flame goes out on its own" },
  { id: "M2", label: "Droplet size when the flame goes out" },
  { id: "M3", label: "Gas flame goes out on its own" },
];

export const MAP_GRAVITIES: readonly { id: MapGravity; label: string; g_m_s2: number }[] = [
  { id: "orbit", label: "Orbit", g_m_s2: 0 },
  { id: "lunar", label: "Moon", g_m_s2: 1.62 },
  { id: "mars", label: "Mars", g_m_s2: 3.71 },
  { id: "earth", label: "Earth", g_m_s2: 9.81 },
];

export interface MapCell {
  i: number;
  j: number;
  o2: number;
  p_psia: number;
  covered: boolean;
  estimate: number | null;
  band90: [number, number] | null;
  nearest_distance: number;
}

export interface MapMarker {
  id: string;
  label: string;
  o2: number;
  p_psia: number;
  g_m_s2: number;
  on_map: boolean;
  covered: boolean;
  nearest_distance: number;
  citation: string;
  date?: string;
  atmosphere_assumed?: boolean;
}

export interface TestedPoint {
  o2: number;
  p_psia: number;
  n: number;
  investigation_id: string;
  on_map: boolean;
}

export interface CrewSource {
  title: string;
  org?: string;
  id_or_number?: string;
  url?: string;
  page_or_section?: string;
}

export interface CrewLimit {
  id: string;
  label: string;
  quantity: string;
  map_rule: string;
  citation: string;
  caveat: string | null;
  confidence: string;
  quote: string;
  source: CrewSource;
  shape: "curve" | "band" | "hline" | "vline" | "tick" | "point" | "marker";
  role: string;
  style?: string;
  note?: string;
  polyline?: [number, number][];
  polylines?: [number, number][][];
  point?: [number, number];
  hollow?: boolean;
  reason?: string;
}

export interface AtmosphereMap {
  artifact: "atmosphere_map";
  citation: string;
  rule: string;
  metric: MapMetric;
  label: string;
  unit: string;
  kind: string;
  investigation_id: string;
  gravity: { id: MapGravity; g_m_s2: number; label: string; u_cm_s: number; L_mm: number; widen_factor: number };
  what_varies: string;
  axes: { x: { label: string; values: number[] }; y: { label: string; values: number[] } };
  gate: { max_distance: number; text: string };
  cells: MapCell[];
  summary: { n_cells: number; n_covered: number; evidence_share: number; no_evidence_share: number; same_for_every_gravity: boolean };
  reading: string;
  overlays: {
    presets: MapMarker[];
    incidents: MapMarker[];
    tested: TestedPoint[];
    crew_limits: { source_file: string; retrieved: string; note: string; drawn: CrewLimit[]; not_drawn: CrewLimit[] } | null;
  };
  model_version: string;
}

export function normalizeAtmosphereMap(raw: unknown): AtmosphereMap {
  const o = (raw ?? {}) as Partial<AtmosphereMap>;
  const nx = o.axes?.x?.values?.length ?? 0;
  const ny = o.axes?.y?.values?.length ?? 0;
  if (!Array.isArray(o.cells) || !nx || !ny || o.cells.length !== nx * ny || !o.summary || !o.overlays) {
    throw new Error("malformed atmosphere map");
  }
  return o as AtmosphereMap;
}

export function parseMetric(v: string | null | undefined): MapMetric {
  return MAP_METRICS.some((m) => m.id === v) ? (v as MapMetric) : "M1";
}

/** `?gravity=` when valid; else the map gravity equal to the habitat's gravity; else the Moon. */
export function parseGravity(v: string | null | undefined, habitatG?: number): MapGravity {
  if (MAP_GRAVITIES.some((g) => g.id === v)) return v as MapGravity;
  const match = MAP_GRAVITIES.find((g) => habitatG !== undefined && Math.abs(g.g_m_s2 - habitatG) < 1e-9);
  return match?.id ?? "lunar";
}

export function gravityInfo(id: MapGravity) {
  return MAP_GRAVITIES.find((g) => g.id === id)!;
}

/** Cell at grid position (i = O₂ index, j = pressure index); cells are row-major by j. */
export function cellAt(m: AtmosphereMap, i: number, j: number): MapCell | undefined {
  return m.cells[j * m.axes.x.values.length + i];
}

/** n + 1 cell edges around n centre values: midpoints (geometric on a log axis), ends extended by half a step. */
export function edges(values: number[], scale: "linear" | "log"): number[] {
  const f = scale === "log" ? Math.log : (v: number) => v;
  const inv = scale === "log" ? Math.exp : (v: number) => v;
  const t = values.map(f);
  if (t.length === 1) return [inv(t[0] - 0.5), inv(t[0] + 0.5)];
  const mids = t.slice(1).map((v, k) => (v + t[k]) / 2);
  return [inv(t[0] - (t[1] - t[0]) / 2), ...mids.map(inv), inv(t[t.length - 1] + (t[t.length - 1] - t[t.length - 2]) / 2)].map(
    (v) => Number(v.toPrecision(10)),
  );
}

export interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** Pixel scales: x = O₂ mole fraction (linear), y = total pressure in psia (log, up = higher pressure). */
export function makeScales(m: AtmosphereMap, box: Box) {
  const xe = edges(m.axes.x.values, "linear");
  const ye = edges(m.axes.y.values, "log");
  const [x0, x1] = [xe[0], xe[xe.length - 1]];
  const [y0, y1] = [Math.log(ye[0]), Math.log(ye[ye.length - 1])];
  const x = (o2: number) => box.left + ((o2 - x0) / (x1 - x0)) * box.width;
  const y = (p: number) => box.top + (1 - (Math.log(p) - y0) / (y1 - y0)) * box.height;
  const inside = (o2: number, p: number) => o2 >= x0 && o2 <= x1 && p >= ye[0] && p <= ye[ye.length - 1];
  return { x, y, xEdges: xe, yEdges: ye, inside };
}

// ------------------------------------------------------------------ colour scale

/** Viridis (perceptually uniform, colour-blind safe, readable in greyscale), 9 stops from 0 to 1. */
export const VIRIDIS = ["#440154", "#472d7b", "#3b528b", "#2c728e", "#21918c", "#28ae80", "#5ec962", "#addc30", "#fde725"] as const;

function hexToRgb(h: string): [number, number, number] {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function viridis(t: number): string {
  const v = Math.min(1, Math.max(0, Number.isFinite(t) ? t : 0));
  const pos = v * (VIRIDIS.length - 1);
  const k = Math.min(VIRIDIS.length - 2, Math.floor(pos));
  const f = pos - k;
  const a = hexToRgb(VIRIDIS[k]);
  const b = hexToRgb(VIRIDIS[k + 1]);
  const c = a.map((x, idx) => Math.round(x + (b[idx] - x) * f));
  return `#${c.map((x) => x.toString(16).padStart(2, "0")).join("")}`;
}

export function isProbability(m: Pick<AtmosphereMap, "kind" | "unit">): boolean {
  return m.kind === "probability" || m.unit === "probability";
}

/** Colour domain: 0-1 for probabilities; the covered estimates' range for a quantity (M2, mm). */
export function colourDomain(m: AtmosphereMap): [number, number] {
  if (isProbability(m)) return [0, 1];
  const v = m.cells.filter((c) => c.covered && c.estimate !== null).map((c) => c.estimate as number);
  if (!v.length) return [0, 1];
  const lo = Math.min(...v);
  const hi = Math.max(...v);
  return hi > lo ? [lo, hi] : [lo, lo + 1];
}

/** Hatch rule: a cell with no evidence (outside the honesty gate, or no estimate) is hatched and never coloured. */
export function isHatched(c: MapCell): boolean {
  return !c.covered || c.estimate === null || !Number.isFinite(c.estimate);
}

/** Fill for a cell, or null when it must be hatched. */
export function cellFill(c: MapCell, domain: [number, number]): string | null {
  if (isHatched(c)) return null;
  return viridis(((c.estimate as number) - domain[0]) / (domain[1] - domain[0]));
}

function fmtMm(v: number): string {
  return Number(v.toPrecision(3)).toString();
}

/** Value text in the metric's unit: probabilities in %, M2 in mm. */
export function valueText(m: Pick<AtmosphereMap, "kind" | "unit">, v: number): string {
  if (isProbability(m)) return `${Math.round(v * 100)}%`;
  return `${fmtMm(v)} ${m.unit}`;
}

/** Legend ticks across the colour domain (5 for probabilities: 0%, 25% ... 100%). */
export function legendTicks(m: AtmosphereMap, domain: [number, number]): { t: number; label: string }[] {
  const n = 4;
  return Array.from({ length: n + 1 }, (_, k) => {
    const v = domain[0] + ((domain[1] - domain[0]) * k) / n;
    return { t: k / n, label: valueText(m, v) };
  });
}

export function shareText(share: number): string {
  return `${Math.round(share * 100)}%`;
}

export function o2Text(o2: number): string {
  return `${Number((o2 * 100).toFixed(1))}% O₂`;
}

export function psiaText(p: number): string {
  return `${Number(p.toPrecision(3))} psia`;
}

/** Plain description of one cell at this gravity (estimate and band, or no evidence with the gate distance). */
export function cellText(m: AtmosphereMap, c: MapCell): string {
  const where = `${o2Text(c.o2)} at ${psiaText(c.p_psia)}`;
  if (isHatched(c)) {
    return `${where}: no evidence (nearest test at distance ${Number(c.nearest_distance.toPrecision(3))}; the honesty gate is ${m.gate.max_distance}).`;
  }
  const band = c.band90 ? `, 90% band ${valueText(m, c.band90[0])} to ${valueText(m, c.band90[1])} at ${gravityInfo(m.gravity.id).label} gravity` : "";
  return `${where}: estimate ${valueText(m, c.estimate as number)}${band}.`;
}

// ------------------------------------------------------------------ crew limits

export interface CrewGeometry {
  kind: "path" | "area" | "point";
  d?: string;
  cx?: number;
  cy?: number;
  /** Where the numbered label sits. */
  anchor: [number, number];
}

type Scales = ReturnType<typeof makeScales>;

function pathD(pts: [number, number][], s: Scales): string {
  return pts.map(([o2, p], k) => `${k ? "L" : "M"} ${s.x(o2).toFixed(1)} ${s.y(p).toFixed(1)}`).join(" ");
}

/** SVG geometry for a crew line, straight from the artifact's polyline / polylines / point (no new values). */
export function crewLineGeometry(c: CrewLimit, s: Scales): CrewGeometry | null {
  if (c.polylines && c.polylines.length >= 2) {
    const [a, b] = c.polylines;
    const d = `${pathD(a, s)} ${pathD([...b].reverse(), s).replace(/^M/, "L")} Z`;
    const last = b[b.length - 1];
    return { kind: "area", d, anchor: [s.x(last[0]), s.y(last[1])] };
  }
  if (c.polyline && c.polyline.length >= 2) {
    const pts = c.polyline;
    const end = c.shape === "vline" || c.shape === "tick" ? pts.reduce((a, b) => (b[1] > a[1] ? b : a)) : pts[pts.length - 1];
    return { kind: "path", d: pathD(pts, s), anchor: [s.x(end[0]), s.y(end[1])] };
  }
  if (c.point) {
    const [o2, p] = c.point;
    if (!s.inside(o2, p)) return null;
    return { kind: "point", cx: s.x(o2), cy: s.y(p), anchor: [s.x(o2), s.y(p)] };
  }
  return null;
}

/** Short tag shown next to each crew line in the legend. */
export function crewTag(c: CrewLimit): string {
  if (c.role === "program baseline") return "2007 program baseline (materials)";
  if (c.shape === "band") return "target, not a limit";
  if (c.style === "dashed") return "absolute floor";
  return c.role;
}

/** Stroke dash for each crew line (shape, not colour, tells them apart; they never use the evidence colours). */
export function crewDash(c: CrewLimit): string | undefined {
  if (c.style === "dashed") return "7 4";
  if (c.role === "program baseline") return "9 3 2 3";
  if (c.shape === "band") return "2 3";
  return undefined;
}

// ------------------------------------------------------------------ markers and URL state

export interface MarkerGroup {
  key: string;
  o2: number;
  p_psia: number;
  items: MapMarker[];
}

/** On-map markers grouped by atmosphere (e.g. ISS and Earth share 21% O₂ at 14.7 psia). */
export function groupMarkers(items: MapMarker[]): MarkerGroup[] {
  const out = new Map<string, MarkerGroup>();
  for (const it of items) {
    if (!it.on_map) continue;
    const key = `${it.o2}|${it.p_psia}`;
    const g = out.get(key) ?? { key, o2: it.o2, p_psia: it.p_psia, items: [] };
    g.items.push(it);
    out.set(key, g);
  }
  return [...out.values()];
}

/** Habitat for a clicked cell: its O₂ and pressure, the map's gravity; vent speed and flame size unchanged. */
export function cellHabitat(c: Pick<MapCell, "o2" | "p_psia">, gravity: MapGravity, habitat: Habitat): Habitat {
  return { ...habitat, o2: c.o2, p_psia: c.p_psia, g_m_s2: gravityInfo(gravity).g_m_s2 };
}

/** Set ?metric= and ?gravity= on a query, keeping everything else (the habitat values). */
export function mapQuery(base: string | URLSearchParams, metric: MapMetric, gravity: MapGravity): string {
  const q = new URLSearchParams(base);
  q.set("metric", metric);
  q.set("gravity", gravity);
  return q.toString();
}

/** Arrow-key move over the grid (Home/End jump along the O₂ axis; up = higher pressure). */
export function moveCell(i: number, j: number, key: string, nx: number, ny: number): [number, number] {
  const clamp = (v: number, n: number) => Math.min(n - 1, Math.max(0, v));
  switch (key) {
    case "ArrowLeft":
      return [clamp(i - 1, nx), j];
    case "ArrowRight":
      return [clamp(i + 1, nx), j];
    case "ArrowUp":
      return [i, clamp(j + 1, ny)];
    case "ArrowDown":
      return [i, clamp(j - 1, ny)];
    case "Home":
      return [0, j];
    case "End":
      return [nx - 1, j];
    default:
      return [i, j];
  }
}

/** Grid indices of the cell closest to an atmosphere (for starting keyboard focus at the current habitat). */
export function nearestCellIndex(m: AtmosphereMap, o2: number, p: number): [number, number] {
  const near = (vals: number[], v: number, log: boolean) =>
    vals.reduce((best, x, k) => (Math.abs((log ? Math.log(x) : x) - (log ? Math.log(v) : v)) < Math.abs((log ? Math.log(vals[best]) : vals[best]) - (log ? Math.log(v) : v)) ? k : best), 0);
  return [near(m.axes.x.values, o2, false), near(m.axes.y.values, Math.max(p, 1e-6), true)];
}
