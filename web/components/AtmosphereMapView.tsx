"use client";

import Link from "next/link";
import { useId, useMemo, useState } from "react";
import { api } from "@/lib/api";
import {
  MAP_GRAVITIES,
  MAP_METRICS,
  VIRIDIS,
  cellAt,
  cellFill,
  cellHabitat,
  cellText,
  colourDomain,
  crewDash,
  crewLineGeometry,
  crewTag,
  gravityInfo,
  groupMarkers,
  isHatched,
  isProbability,
  legendTicks,
  makeScales,
  moveCell,
  nearestCellIndex,
  o2Text,
  parseGravity,
  parseMetric,
  psiaText,
  shareText,
  valueText,
  type AtmosphereMap,
  type CrewLimit,
  type MapCell,
  type MapGravity,
} from "@/lib/atmosphereMap";
import { useAsync } from "@/lib/useAsync";
import { useHabitat } from "@/lib/useHabitat";
import { useQueryParam } from "@/lib/useQueryParam";
import { ErrorState, Loading, SourceChip } from "./ui/States";

const W = 760;
const H = 470;
const BOX = { left: 58, top: 12, width: W - 58 - 14, height: H - 12 - 46 };
const X_TICKS = [0.15, 0.2, 0.25, 0.3, 0.35, 0.4];
const Y_TICKS = [4, 5, 6, 8, 10, 12, 16];

type Overlay = "presets" | "incidents" | "tested" | "crew";
const OVERLAYS: { id: Overlay; label: string }[] = [
  { id: "presets", label: "Habitat presets" },
  { id: "incidents", label: "Real fire incidents" },
  { id: "tested", label: "Tested atmospheres" },
  { id: "crew", label: "Crew and materials limits (NASA sources)" },
];

/** S5 "Air map": where the PSI evidence reaches across cabin O₂ and pressure (ADR-0011). It never ranks atmospheres. */
export function AtmosphereMapView() {
  const { habitat } = useHabitat();
  const [metricRaw, setMetric] = useQueryParam("metric", "M1");
  const [gravityRaw, setGravity] = useQueryParam("gravity", "");
  const metric = parseMetric(metricRaw);
  const gravity = parseGravity(gravityRaw, habitat.g_m_s2);
  const res = useAsync(() => api.atmosphereMap(metric, gravity), `${metric}|${gravity}`);
  const [overlays, setOverlays] = useState<Record<Overlay, boolean>>({ presets: true, incidents: true, tested: false, crew: true });

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wider text-partial">S5 · Atmosphere evidence map</p>
          <h1 className="text-2xl font-semibold">Which cabin air does the evidence cover?</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Each cell is one cabin atmosphere (oxygen share across, total pressure up). A coloured cell has NASA test evidence
            and shows the engine&rsquo;s estimate there; a hatched cell has no evidence. The map does not rank atmospheres or
            pick one: the metrics measure different things, and crew limits are a separate question, drawn as lines from
            cited NASA documents.
          </p>
        </div>
        {res.status === "ok" ? <SourceChip source={res.data.source} note={res.data.note} /> : null}
      </header>

      <div className="flex flex-wrap items-start gap-x-6 gap-y-3 rounded-lg border border-line bg-surface p-3">
        <div role="group" aria-label="Metric" className="flex flex-col gap-1">
          <span className="text-xs font-medium text-muted">What the colour shows</span>
          <div className="flex flex-wrap gap-1">
            {MAP_METRICS.map((m) => (
              <button
                key={m.id}
                type="button"
                aria-pressed={metric === m.id}
                onClick={() => setMetric(m.id)}
                className={`rounded-md border px-2 py-1 text-xs ${metric === m.id ? "border-micro bg-surface-2 text-fg" : "border-line text-muted hover:text-fg"}`}
              >
                {m.label} <span className="num">({m.id})</span>
              </button>
            ))}
          </div>
        </div>
        <div role="group" aria-label="Gravity" className="flex flex-col gap-1">
          <span className="text-xs font-medium text-muted">Gravity (changes only the 90% band)</span>
          <div className="flex flex-wrap gap-1">
            {MAP_GRAVITIES.map((g) => (
              <button
                key={g.id}
                type="button"
                aria-pressed={gravity === g.id}
                onClick={() => setGravity(g.id)}
                className={`rounded-md border px-2 py-1 text-xs ${gravity === g.id ? "border-micro bg-surface-2 text-fg" : "border-line text-muted hover:text-fg"}`}
              >
                {g.label}
              </button>
            ))}
          </div>
        </div>
        <fieldset className="flex flex-col gap-1">
          <legend className="text-xs font-medium text-muted">Show on the map</legend>
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {OVERLAYS.map((o) => (
              <label key={o.id} className="flex items-center gap-1 text-xs">
                <input
                  type="checkbox"
                  checked={overlays[o.id]}
                  onChange={(e) => setOverlays((s) => ({ ...s, [o.id]: e.target.checked }))}
                  data-testid={`overlay-${o.id}`}
                />
                {o.label}
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      {res.status === "loading" ? <Loading label="Loading the map…" /> : null}
      {res.status === "error" ? <ErrorState error={res.error} onRetry={res.reload} /> : null}
      {res.status === "ok" ? <MapBody m={res.data.data} gravity={gravity} overlays={overlays} /> : null}
    </div>
  );
}

function MapBody({ m, gravity, overlays }: { m: AtmosphereMap; gravity: MapGravity; overlays: Record<Overlay, boolean> }) {
  const { habitat, setHabitat, queryString } = useHabitat();
  const s = useMemo(() => makeScales(m, BOX), [m]);
  const domain = useMemo(() => colourDomain(m), [m]);
  const nx = m.axes.x.values.length;
  const ny = m.axes.y.values.length;
  const [sel, setSel] = useState<[number, number]>(() => nearestCellIndex(m, habitat.o2, habitat.p_psia));
  const [hover, setHover] = useState<[number, number] | null>(null);
  const [loaded, setLoaded] = useState<MapCell | null>(null);
  const [table, setTable] = useState(false);
  const hatchId = `hatch-${useId().replace(/:/g, "")}`;
  const liveId = useId();
  const selected = cellAt(m, sel[0], sel[1]);
  const shown = (hover && cellAt(m, hover[0], hover[1])) || selected;
  const g = gravityInfo(gravity);
  const crew = m.overlays.crew_limits;
  const lines = (crew?.drawn ?? []).filter((c) => c.shape !== "marker");
  const refs = (crew?.drawn ?? []).filter((c) => c.shape === "marker");
  const presetGroups = groupMarkers(m.overlays.presets);
  const incidentGroups = groupMarkers(m.overlays.incidents);
  const share = m.summary;
  const metricInfo = MAP_METRICS.find((x) => x.id === m.metric);

  const load = (c: MapCell) => {
    setSel([c.i, c.j]);
    setHabitat(cellHabitat(c, gravity, habitat));
    setLoaded(c);
  };

  const cellFromEvent = (e: React.MouseEvent): MapCell | undefined => {
    const el = (e.target as Element).closest("[data-i]");
    if (!el) return undefined;
    return cellAt(m, Number(el.getAttribute("data-i")), Number(el.getAttribute("data-j")));
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (selected) load(selected);
      return;
    }
    const next = moveCell(sel[0], sel[1], e.key, nx, ny);
    if (next[0] !== sel[0] || next[1] !== sel[1]) {
      e.preventDefault();
      setHover(null);
      setSel(next);
    }
  };

  const habitatOnMap = s.inside(habitat.o2, habitat.p_psia);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <p className="text-sm" data-testid="evidence-share">
          <span className="num text-2xl font-semibold">{shareText(share.evidence_share)}</span> of this map has evidence for{" "}
          {m.metric} ({share.n_covered} of {share.n_cells} cells);{" "}
          <span className="font-medium">{shareText(share.no_evidence_share)} has no evidence</span>.
        </p>
      </div>
      <p className="max-w-4xl text-sm" data-testid="map-reading">
        {m.reading}
      </p>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_19rem]">
        <figure className="space-y-2">
          <div
            tabIndex={0}
            role="group"
            aria-label={`Map cells for ${m.metric}. Arrow keys move between cells; Enter loads the selected atmosphere into the habitat bar.`}
            aria-describedby={liveId}
            onKeyDown={onKey}
            className="rounded-md"
            data-testid="map-keyboard"
          >
            <svg
              viewBox={`0 0 ${W} ${H}`}
              className="h-auto w-full"
              role="img"
              aria-label={`${m.label}: evidence map at ${g.label} gravity. ${share.n_covered} of ${share.n_cells} cells have evidence and are coloured by the estimate; hatched cells have no evidence.`}
              data-testid="atmosphere-map"
            >
              <defs>
                <pattern id={hatchId} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                  <rect width="6" height="6" fill="var(--surface)" />
                  <line x1="0" y1="0" x2="0" y2="6" stroke="var(--nodata)" strokeWidth="2" />
                </pattern>
              </defs>
              <g
                onClick={(e) => {
                  const c = cellFromEvent(e);
                  if (c) load(c);
                }}
                onMouseMove={(e) => {
                  const c = cellFromEvent(e);
                  if (c && (!hover || hover[0] !== c.i || hover[1] !== c.j)) setHover([c.i, c.j]);
                }}
                onMouseLeave={() => setHover(null)}
                style={{ cursor: "pointer" }}
                data-testid="map-cells"
              >
                {m.cells.map((c) => {
                  const fill = cellFill(c, domain);
                  const x0 = s.x(s.xEdges[c.i]);
                  const x1 = s.x(s.xEdges[c.i + 1]);
                  const y0 = s.y(s.yEdges[c.j + 1]);
                  const y1 = s.y(s.yEdges[c.j]);
                  return (
                    <rect
                      key={`${c.i}-${c.j}`}
                      x={x0}
                      y={y0}
                      width={x1 - x0}
                      height={y1 - y0}
                      fill={fill ?? `url(#${hatchId})`}
                      data-i={c.i}
                      data-j={c.j}
                      data-hatch={fill ? undefined : "true"}
                      data-covered={c.covered ? "true" : "false"}
                    />
                  );
                })}
              </g>

              <g aria-hidden="true">
                {X_TICKS.map((t) => (
                  <text key={`x${t}`} x={s.x(t)} y={BOX.top + BOX.height + 16} fontSize={11} textAnchor="middle" fill="var(--muted)" className="num">
                    {Math.round(t * 100)}%
                  </text>
                ))}
                {Y_TICKS.map((t) => (
                  <text key={`y${t}`} x={BOX.left - 6} y={s.y(t) + 4} fontSize={11} textAnchor="end" fill="var(--muted)" className="num">
                    {t}
                  </text>
                ))}
                <text x={BOX.left + BOX.width / 2} y={H - 6} fontSize={11} textAnchor="middle" fill="var(--muted)">
                  oxygen (% of the cabin air)
                </text>
                <text transform={`translate(14 ${BOX.top + BOX.height / 2}) rotate(-90)`} fontSize={11} textAnchor="middle" fill="var(--muted)">
                  total pressure (psia, log scale)
                </text>
              </g>

              {overlays.tested ? (
                <g data-testid="overlay-tested-layer">
                  {m.overlays.tested
                    .filter((t) => t.on_map)
                    .map((t, k) => (
                      <g key={k}>
                        <title>{`Tested: ${o2Text(t.o2)} at ${psiaText(t.p_psia)}, ${t.n} tests (${t.investigation_id})`}</title>
                        <path
                          d={`M ${s.x(t.o2) - 3} ${s.y(t.p_psia) - 3} L ${s.x(t.o2) + 3} ${s.y(t.p_psia) + 3} M ${s.x(t.o2) - 3} ${s.y(t.p_psia) + 3} L ${s.x(t.o2) + 3} ${s.y(t.p_psia) - 3}`}
                          stroke="var(--fg)"
                          strokeWidth={1.4}
                        />
                      </g>
                    ))}
                </g>
              ) : null}

              {overlays.crew ? (
                <g data-testid="overlay-crew-layer">
                  {lines.map((c, k) => (
                    <CrewShape key={c.id} c={c} n={k + 1} s={s} />
                  ))}
                  {refs.map((c) =>
                    c.point && s.inside(c.point[0], c.point[1]) ? (
                      <g key={c.id} data-crew={c.id}>
                        <title>{`${c.label}: ${c.source.title}, “${c.quote}”`}</title>
                        <RefGlyph x={s.x(c.point[0])} y={s.y(c.point[1])} hollow={!!c.hollow} />
                      </g>
                    ) : null,
                  )}
                </g>
              ) : null}

              {overlays.incidents ? (
                <g data-testid="overlay-incidents-layer">
                  {incidentGroups.map((grp) => (
                    <g key={grp.key} data-incident={grp.items.map((i) => i.id).join(",")}>
                      <title>
                        {grp.items
                          .map((i) => `${i.label} (${i.date?.slice(0, 4)}): ${o2Text(i.o2)} at ${psiaText(i.p_psia)}${i.atmosphere_assumed ? ", assumed atmosphere" : ""}`)
                          .join("; ")}
                      </title>
                      <Diamond x={s.x(grp.o2)} y={s.y(grp.p_psia)} assumed={grp.items.every((i) => i.atmosphere_assumed)} />
                    </g>
                  ))}
                </g>
              ) : null}

              {overlays.presets ? (
                <g data-testid="overlay-presets-layer">
                  {presetGroups.map((grp) => {
                    const x = s.x(grp.o2);
                    const y = s.y(grp.p_psia);
                    const right = x < BOX.left + BOX.width * 0.6;
                    const label = grp.items.map((i) => i.label).join(" · ");
                    return (
                      <g key={grp.key} data-preset={grp.items.map((i) => i.id).join(",")}>
                        <circle cx={x} cy={y} r={4.5} fill="var(--surface)" stroke="var(--fg)" strokeWidth={2} />
                        <text
                          x={right ? x + 9 : x - 9}
                          y={y - 7}
                          fontSize={11}
                          fontWeight={600}
                          textAnchor={right ? "start" : "end"}
                          fill="var(--fg)"
                          style={{ paintOrder: "stroke", stroke: "var(--surface)", strokeWidth: 3, strokeLinejoin: "round" }}
                        >
                          {label}
                        </text>
                      </g>
                    );
                  })}
                </g>
              ) : null}

              {habitatOnMap ? (
                <g aria-hidden="true" data-testid="habitat-marker">
                  <circle cx={s.x(habitat.o2)} cy={s.y(habitat.p_psia)} r={8} fill="none" stroke="var(--surface)" strokeWidth={4} />
                  <circle cx={s.x(habitat.o2)} cy={s.y(habitat.p_psia)} r={8} fill="none" stroke="var(--fg)" strokeWidth={1.5} strokeDasharray="3 2" />
                </g>
              ) : null}

              {selected ? (
                <rect
                  aria-hidden="true"
                  x={s.x(s.xEdges[selected.i])}
                  y={s.y(s.yEdges[selected.j + 1])}
                  width={s.x(s.xEdges[selected.i + 1]) - s.x(s.xEdges[selected.i])}
                  height={s.y(s.yEdges[selected.j]) - s.y(s.yEdges[selected.j + 1])}
                  fill="none"
                  stroke="var(--fg)"
                  strokeWidth={2.5}
                  pointerEvents="none"
                  data-testid="selected-cell"
                />
              ) : null}
              <rect x={BOX.left} y={BOX.top} width={BOX.width} height={BOX.height} fill="none" stroke="var(--fg)" strokeWidth={1} pointerEvents="none" aria-hidden="true" />
            </svg>
          </div>
          <figcaption className="text-xs text-muted">
            {m.label} ({m.investigation_id}), vent {m.gravity.u_cm_s} cm/s and flame size {m.gravity.L_mm} mm. Click a cell, or
            focus the map and use the arrow keys and Enter, to load that atmosphere into the habitat bar.
          </figcaption>
          <ColourLegend m={m} domain={domain} hatchId={hatchId} />
        </figure>

        <aside className="space-y-3">
          <div className="rounded-lg border border-line bg-surface p-3 text-sm">
            <p className="text-xs font-medium uppercase tracking-wider text-muted">{hover ? "Under the pointer" : "Selected cell"}</p>
            <p id={liveId} aria-live="polite" className="mt-1" data-testid="cell-info">
              {shown ? cellText(m, shown) : "–"}
            </p>
            {selected ? (
              <button
                type="button"
                onClick={() => load(selected)}
                className="mt-2 rounded-md border border-line bg-surface-2 px-2 py-1 text-xs hover:text-fg"
              >
                Load {o2Text(selected.o2)} at {psiaText(selected.p_psia)} into the habitat bar
              </button>
            ) : null}
            {loaded ? (
              <div className="mt-2 border-t border-line pt-2 text-xs" data-testid="loaded-links">
                <p>
                  Loaded {o2Text(loaded.o2)} at {psiaText(loaded.p_psia)}, {g.label} gravity, into the habitat bar. Open it in:
                </p>
                <p className="mt-1 flex flex-wrap gap-3">
                  <Link href={`/bounds?${queryString}`} className="text-micro underline">
                    Bounds
                  </Link>
                  <Link href={`/compare?a=iss&b=current&${queryString}`} className="text-micro underline">
                    Compare
                  </Link>
                  <Link href={`/briefing?${queryString}`} className="text-micro underline">
                    Briefing
                  </Link>
                </p>
              </div>
            ) : null}
          </div>
          <div className="rounded-lg border border-line bg-surface p-3 text-xs" data-testid="gravity-note">
            <p className="font-medium">Gravity changes only the band</p>
            <p className="mt-1">
              {m.what_varies} At {g.label} gravity the band is widened by a factor of{" "}
              <span className="num">{m.gravity.widen_factor}</span>; the coloured cells are the same at every gravity.
            </p>
          </div>
          <MarkerLegend m={m} />
        </aside>
      </div>

      {crew ? <CrewLegend lines={lines} refs={refs} notDrawn={crew.not_drawn} note={crew.note} /> : null}

      <div className="space-y-2">
        <button
          type="button"
          aria-expanded={table}
          onClick={() => setTable((t) => !t)}
          className="rounded-md border border-line px-3 py-1.5 text-sm text-muted hover:text-fg"
          data-testid="table-toggle"
        >
          {table ? "Hide table view" : "Show table view"}
        </button>
        {table ? <MapTable m={m} label={metricInfo?.label ?? m.label} /> : null}
      </div>
      <p className="text-xs text-muted">
        {m.rule} Honesty gate: {m.gate.text}
      </p>
    </div>
  );
}

function Diamond({ x, y, assumed }: { x: number; y: number; assumed: boolean }) {
  const r = 8;
  const d = `M ${x} ${y - r} L ${x + r} ${y} L ${x} ${y + r} L ${x - r} ${y} Z`;
  return (
    <g>
      <path d={d} fill="none" stroke="var(--surface)" strokeWidth={4} />
      <path d={d} fill={assumed ? "none" : "var(--fg)"} stroke="var(--fg)" strokeWidth={1.6} strokeDasharray={assumed ? "3 2" : undefined} />
    </g>
  );
}

function RefGlyph({ x, y, hollow }: { x: number; y: number; hollow: boolean }) {
  return hollow ? (
    <circle cx={x} cy={y} r={3.5} fill="none" stroke="var(--fg)" strokeWidth={1.4} />
  ) : (
    <path d={`M ${x - 4} ${y} L ${x + 4} ${y} M ${x} ${y - 4} L ${x} ${y + 4}`} stroke="var(--fg)" strokeWidth={1.6} />
  );
}

/** One crew line: neutral ink with a halo, its own dash pattern, and a numbered tag matching the legend. */
function CrewShape({ c, n, s }: { c: CrewLimit; n: number; s: ReturnType<typeof makeScales> }) {
  const geo = crewLineGeometry(c, s);
  if (!geo) return null;
  const dash = crewDash(c);
  const ax = Math.min(BOX.left + BOX.width - 9, Math.max(BOX.left + 9, geo.anchor[0]));
  const ay = Math.min(BOX.top + BOX.height - 9, Math.max(BOX.top + 9, geo.anchor[1]));
  return (
    <g data-crew={c.id}>
      <title>{`${c.label} (${crewTag(c)}). Source: ${c.source.title}: “${c.quote}”${c.caveat ? ` ${c.caveat}` : ""}`}</title>
      {geo.kind === "area" ? (
        <path d={geo.d} fill="var(--fg)" fillOpacity={0.16} stroke="var(--fg)" strokeWidth={1} strokeDasharray={dash} />
      ) : geo.kind === "path" ? (
        <>
          <path d={geo.d} fill="none" stroke="var(--surface)" strokeWidth={c.shape === "tick" ? 6 : 4} />
          <path d={geo.d} fill="none" stroke="var(--fg)" strokeWidth={c.shape === "tick" ? 3 : 1.8} strokeDasharray={dash} />
        </>
      ) : (
        <rect x={(geo.cx ?? 0) - 4} y={(geo.cy ?? 0) - 4} width={8} height={8} fill="var(--surface)" stroke="var(--fg)" strokeWidth={1.8} />
      )}
      <circle cx={ax} cy={ay} r={7} fill="var(--surface)" stroke="var(--fg)" strokeWidth={1} />
      <text x={ax} y={ay + 3.5} fontSize={9.5} textAnchor="middle" fill="var(--fg)" className="num" aria-hidden="true">
        {n}
      </text>
    </g>
  );
}

function LineSample({ c }: { c: CrewLimit }) {
  const dash = crewDash(c);
  return (
    <svg width="34" height="12" viewBox="0 0 34 12" aria-hidden="true" className="shrink-0">
      {c.shape === "band" ? (
        <rect x="1" y="2" width="32" height="8" fill="var(--fg)" fillOpacity={0.16} stroke="var(--fg)" strokeDasharray={dash} />
      ) : c.shape === "point" ? (
        <rect x="13" y="2" width="8" height="8" fill="var(--surface)" stroke="var(--fg)" strokeWidth={1.8} />
      ) : (
        <line x1="1" y1="6" x2="33" y2="6" stroke="var(--fg)" strokeWidth={c.shape === "tick" ? 3 : 1.8} strokeDasharray={dash} />
      )}
    </svg>
  );
}

function SourceDetails({ c }: { c: CrewLimit }) {
  return (
    <details className="mt-0.5">
      <summary className="cursor-pointer text-muted hover:text-fg">Source</summary>
      <p className="mt-1" data-testid="crew-source">
        {c.source.url ? (
          <a href={c.source.url} target="_blank" rel="noreferrer" className="text-micro underline">
            {c.source.title}
          </a>
        ) : (
          c.source.title
        )}
        {c.source.org ? `, ${c.source.org}` : ""}
        {c.source.id_or_number ? ` (${c.source.id_or_number})` : ""}
        {c.source.page_or_section ? `, ${c.source.page_or_section}` : ""}.
      </p>
      <p className="mt-0.5 italic">&ldquo;{c.quote}&rdquo;</p>
      {c.caveat ? <p className="mt-0.5">Caveat: {c.caveat}</p> : null}
      <p className="num mt-0.5 text-muted">{c.citation}</p>
    </details>
  );
}

function CrewLegend({ lines, refs, notDrawn, note }: { lines: CrewLimit[]; refs: CrewLimit[]; notDrawn: CrewLimit[]; note: string }) {
  return (
    <section aria-labelledby="crew-h" className="rounded-lg border border-line bg-surface p-3" data-testid="crew-legend">
      <h2 id="crew-h" className="text-sm font-semibold">
        Crew and materials limits on the map
      </h2>
      <p className="mt-1 text-xs text-muted">
        {note} They are drawn in plain ink, never in the evidence colours. Turn them off with &ldquo;Crew and materials
        limits&rdquo; above.
      </p>
      <ol className="mt-2 grid gap-2 text-xs md:grid-cols-2">
        {lines.map((c, k) => (
          <li key={c.id} className="flex gap-2" data-testid={`crew-${c.id}`}>
            <span className="num mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-fg text-[10px]">
              {k + 1}
            </span>
            <LineSample c={c} />
            <div className="min-w-0">
              <p>
                {c.label} <span className="font-medium">· {crewTag(c)}</span>
              </p>
              <SourceDetails c={c} />
            </div>
          </li>
        ))}
        {refs.map((c) => (
          <li key={c.id} className="flex gap-2" data-testid={`crew-${c.id}`}>
            <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true" className="mt-0.5 shrink-0">
              <RefGlyph x={8} y={6} hollow={!!c.hollow} />
            </svg>
            <div className="min-w-0">
              <p>
                {c.label} <span className="font-medium">· {c.role}</span>
              </p>
              <SourceDetails c={c} />
            </div>
          </li>
        ))}
      </ol>
      {notDrawn.length ? (
        <ul className="mt-2 text-xs text-muted">
          {notDrawn.map((c) => (
            <li key={c.id}>
              Not drawn: {c.label} ({c.reason}).
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function ColourLegend({ m, domain, hatchId }: { m: AtmosphereMap; domain: [number, number]; hatchId: string }) {
  const ticks = legendTicks(m, domain);
  const gradient = `linear-gradient(to right, ${VIRIDIS.join(", ")})`;
  return (
    <div className="flex flex-wrap items-end gap-x-6 gap-y-2 text-xs" data-testid="colour-legend">
      <div className="min-w-[16rem] flex-1">
        <p className="mb-1">
          Estimate where there is evidence: {m.label} {isProbability(m) ? "(%)" : `(${m.unit})`}
        </p>
        <div className="h-3 rounded-sm" style={{ background: gradient }} aria-hidden="true" />
        <div className="num mt-0.5 flex justify-between text-muted">
          {ticks.map((t) => (
            <span key={t.t}>{t.label}</span>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <svg width="28" height="16" aria-hidden="true">
          <rect width="28" height="16" fill={`url(#${hatchId})`} stroke="var(--line)" />
        </svg>
        <span>No evidence (outside the honesty gate): no colour, no number</span>
      </div>
    </div>
  );
}

function MarkerLegend({ m }: { m: AtmosphereMap }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-3 text-xs" data-testid="marker-legend">
      <p className="font-medium">Markers</p>
      <ul className="mt-1 space-y-1">
        <li className="flex items-center gap-2">
          <svg width="16" height="16" aria-hidden="true">
            <circle cx="8" cy="8" r="4.5" fill="var(--surface)" stroke="var(--fg)" strokeWidth="2" />
          </svg>
          Habitat presets (labelled)
        </li>
        <li className="flex items-center gap-2">
          <svg width="16" height="16" aria-hidden="true">
            <circle cx="8" cy="8" r="6" fill="none" stroke="var(--fg)" strokeWidth="1.5" strokeDasharray="3 2" />
          </svg>
          The habitat in the bar above
        </li>
        <li className="flex items-center gap-2">
          <svg width="16" height="16" aria-hidden="true">
            <path d="M8 1 L15 8 L8 15 L1 8 Z" fill="none" stroke="var(--fg)" strokeWidth="1.5" strokeDasharray="3 2" />
          </svg>
          Real fire incident, assumed atmosphere (hollow, dashed)
        </li>
        <li className="flex items-center gap-2">
          <svg width="16" height="16" aria-hidden="true">
            <path d="M5 5 L11 11 M5 11 L11 5" stroke="var(--fg)" strokeWidth="1.4" />
          </svg>
          Tested atmosphere ({m.investigation_id})
        </li>
      </ul>
      <ul className="mt-2 space-y-0.5" data-testid="incident-list">
        {m.overlays.incidents.map((i) => (
          <li key={i.id}>
            {i.label} ({i.date?.slice(0, 4)}): {o2Text(i.o2)} at {psiaText(i.p_psia)}
            {i.atmosphere_assumed ? ", assumed atmosphere" : ""}
            {i.on_map ? "" : ", off this map"}.
          </li>
        ))}
      </ul>
    </div>
  );
}

function MapTable({ m, label }: { m: AtmosphereMap; label: string }) {
  const xs = m.axes.x.values;
  const ys = [...m.axes.y.values.keys()].reverse();
  return (
    <div tabIndex={0} role="region" aria-label="Table view of the map" className="overflow-x-auto rounded-lg border border-line" data-testid="map-table">
      <table className="num min-w-full text-[11px]">
        <caption className="p-2 text-left font-sans text-xs text-muted">
          {label} ({m.metric}) estimate per cell; &ldquo;–&rdquo; means no evidence. Rows: total pressure (psia); columns:
          O₂ (% of the air).
        </caption>
        <thead>
          <tr>
            <th scope="col" className="px-1 py-0.5 text-left">
              psia
            </th>
            {xs.map((x) => (
              <th key={x} scope="col" className="px-1 py-0.5">
                {Math.round(x * 100)}%
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ys.map((j) => (
            <tr key={j} className="border-t border-line">
              <th scope="row" className="px-1 py-0.5 text-left">
                {Number(m.axes.y.values[j].toPrecision(3))}
              </th>
              {xs.map((_, i) => {
                const c = cellAt(m, i, j)!;
                return (
                  <td key={i} className="px-1 py-0.5 text-center">
                    {isHatched(c) ? (
                      <>
                        <span aria-hidden="true">–</span>
                        <span className="sr-only">no evidence</span>
                      </>
                    ) : (
                      valueText(m, c.estimate as number)
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
