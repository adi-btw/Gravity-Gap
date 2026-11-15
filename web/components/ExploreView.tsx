"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { DEFAULT_WEIGHTS, type CatalogRecord, type RankWeights } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";
import { useHabitat } from "@/lib/useHabitat";
import { FUEL_STYLE, GravitySpectrum, Glyph, fuelStyle } from "./charts/GravitySpectrum";
import { Empty, ErrorState, Loading, PartBar, SourceChip } from "./ui/States";

const PART_LABEL: Record<string, string> = {
  atmosphere: "Atmosphere match",
  pillar: "Fire-safety pillar",
  fuel_realism: "Fuel realism",
  outcomes: "Outcome data",
  n_tests: "Number of tests",
  regime_fit: "Regime fit (g, vent)",
};

const PART_COLOR: Record<string, string> = {
  atmosphere: "var(--micro)",
  pillar: "var(--normal)",
  fuel_realism: "var(--partial)",
  outcomes: "var(--fg)",
  n_tests: "var(--muted)",
  regime_fit: "var(--warn)",
};

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function ExploreView() {
  const { habitat, queryString } = useHabitat();
  const [weights, setWeights] = useState<RankWeights>(DEFAULT_WEIGHTS);
  const debounced = useDebounced(weights, 250);
  const catalog = useAsync(() => api.catalog(), "catalog");
  const ranked = useAsync(() => api.rank(habitat, debounced), `${queryString}|${JSON.stringify(debounced)}`);

  const records: CatalogRecord[] = catalog.status === "ok" ? catalog.data.data : [];
  const byId = new Map(records.map((r) => [r.id, r]));
  const excluded = records.filter((r) => !r.is_combustion);
  const wSum = Object.values(weights).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="doc-label">F1 · Gravity spectrum</p>
          <h1 className="page-title">Where the fire evidence sits on the gravity axis</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Every PSI combustion investigation was run at 0 g (ISS, Cygnus) or 1 g (ground). Nothing sits in between.
            Select a mark to open its investigation card.
          </p>
        </div>
        {catalog.status === "ok" ? <SourceChip source={catalog.data.source} note={catalog.data.note} /> : null}
      </header>

      <figure className="rounded-lg border border-line bg-surface p-4">
        {catalog.status === "loading" ? <Loading label="Loading catalog…" /> : null}
        {catalog.status === "error" ? <ErrorState error={catalog.error} onRetry={catalog.reload} /> : null}
        {catalog.status === "ok" ? (
          records.length ? (
            <>
              <GravitySpectrum records={records} currentG={habitat.g_m_s2} queryString={queryString} />
              <figcaption className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-xs text-muted">
                <span className="fig-no mr-0">Fig. 1 ·</span>
                <span>Fuel phase:</span>
                {Object.entries(FUEL_STYLE).map(([k, s]) => (
                  <span key={k} className="inline-flex items-center gap-1">
                    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                      <Glyph x={7} y={7} phase={k} r={4.5} />
                    </svg>
                    {s.label}
                  </span>
                ))}
                <span className="inline-flex items-center gap-1">
                  <span aria-hidden="true" className="hatch inline-block h-3 w-5 rounded-sm border border-line" /> no direct data
                </span>
              </figcaption>
              <details className="mt-3 text-sm">
                <summary className="cursor-pointer text-xs text-muted">Table view of the spectrum</summary>
                <table className="mt-2 w-full text-left text-xs">
                  <caption className="sr-only">Investigations by gravity level</caption>
                  <thead className="text-muted">
                    <tr>
                      <th scope="col">Investigation</th>
                      <th scope="col">Gravity levels</th>
                      <th scope="col">Fuel phase</th>
                      <th scope="col">Platform</th>
                      <th scope="col">Tests</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records
                      .filter((r) => r.is_combustion)
                      .map((r) => (
                        <tr key={r.id} className="border-t border-line">
                          <th scope="row" className="font-normal">
                            <Link href={`/investigations/${r.id}?${queryString}`} className="text-micro underline">
                              {r.id}
                            </Link>{" "}
                            {r.acronym}
                          </th>
                          <td>{(r.gravity_levels ?? []).join(", ").replace(/_/g, " ")}</td>
                          <td>{fuelStyle(r.fuel_phase).label}</td>
                          <td>{r.platform ?? "–"}</td>
                          <td className="num">{r.n_tests}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </details>
            </>
          ) : (
            <Empty>The catalog is empty.</Empty>
          )
        ) : null}
      </figure>

      <div className="grid gap-4 lg:grid-cols-[1fr_2fr]">
        <section className="rounded-lg border border-line bg-surface p-4" aria-labelledby="weights-h">
          <h2 id="weights-h" className="text-sm font-semibold">
            Relevance weights
          </h2>
          <p className="mt-1 text-xs text-muted">
            score = Σ wₖ · partₖ / Σ wₖ. Edit the weights to re-rank (the API recomputes).
          </p>
          <div className="mt-3 space-y-3">
            {(Object.keys(DEFAULT_WEIGHTS) as (keyof RankWeights)[]).map((k) => (
              <div key={k}>
                <label htmlFor={`w-${k}`} className="flex justify-between text-xs">
                  <span>{PART_LABEL[k]}</span>
                  <span className="num">{weights[k].toFixed(2)}</span>
                </label>
                <input
                  id={`w-${k}`}
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={weights[k]}
                  onChange={(e) => setWeights({ ...weights, [k]: Number(e.target.value) })}
                  className="w-full"
                />
              </div>
            ))}
          </div>
          {wSum <= 0 ? <p className="mt-2 text-xs text-warn">At least one weight must be above 0.</p> : null}
          <button
            type="button"
            onClick={() => setWeights(DEFAULT_WEIGHTS)}
            className="mt-3 rounded border border-line px-2 py-1 text-xs hover:bg-surface-2"
          >
            Reset to defaults
          </button>
        </section>

        <section className="rounded-lg border border-line bg-surface p-4" aria-labelledby="rank-h">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="rank-h" className="text-sm font-semibold">
              Most relevant evidence for this habitat
            </h2>
            {ranked.status === "ok" ? <SourceChip source={ranked.data.source} note={ranked.data.note} /> : null}
          </div>
          <div aria-live="polite">
            {ranked.status === "loading" ? <Loading label="Ranking…" /> : null}
            {ranked.status === "error" ? <ErrorState error={ranked.error} onRetry={ranked.reload} /> : null}
            {ranked.status === "ok" && ranked.data.data === null ? (
              <>
                <p className="hatch mt-2 rounded border border-dashed border-line px-3 py-2 text-sm">
                  Offline: ranking needs the API. Showing the catalog in its original order, without scores.
                </p>
                <ol className="mt-2 space-y-1 text-sm">
                  {records
                    .filter((r) => r.is_combustion)
                    .map((r) => (
                      <li key={r.id}>
                        <Link href={`/investigations/${r.id}?${queryString}`} className="num text-micro underline">
                          {r.id}
                        </Link>{" "}
                        {r.acronym ?? r.title}
                      </li>
                    ))}
                </ol>
              </>
            ) : null}
            {ranked.status === "ok" && ranked.data.data !== null ? (
              ranked.data.data.length ? (
                <ol className="mt-2 space-y-3">
                  {ranked.data.data.map((item, i) => {
                    const rec = byId.get(item.id);
                    return (
                      <li key={item.id} className="rounded-md border border-line p-3">
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                          <Link href={`/investigations/${item.id}?${queryString}`} className="font-medium text-micro underline">
                            <span className="num">#{i + 1} {item.id}</span> {item.acronym ?? rec?.title ?? ""}
                          </Link>
                          <span className="num text-sm">score {item.score.toFixed(3)}</span>
                        </div>
                        {rec?.title && rec.title !== item.acronym ? <p className="text-xs text-muted">{rec.title}</p> : null}
                        <div className="mt-2 space-y-1" role="group" aria-label={`Score parts for ${item.id}`}>
                          {Object.entries(item.parts).map(([k, v]) => (
                            <PartBar key={k} label={PART_LABEL[k] ?? k} value={v} color={PART_COLOR[k]} />
                          ))}
                        </div>
                        {item.regime_fit_basis || item.atmosphere_basis ? (
                          <p className="mt-1 text-[11px] text-muted">
                            {[item.atmosphere_basis, item.regime_fit_basis].filter(Boolean).join(" · ")}
                          </p>
                        ) : null}
                      </li>
                    );
                  })}
                </ol>
              ) : (
                <Empty>No combustion investigations matched.</Empty>
              )
            ) : null}
          </div>
          {excluded.length ? (
            <details className="mt-4 text-sm">
              <summary className="cursor-pointer text-xs text-muted">
                Excluded: not combustion ({excluded.length})
              </summary>
              <ul className="mt-2 space-y-1 text-xs">
                {excluded.map((r) => (
                  <li key={r.id}>
                    <Link href={`/investigations/${r.id}?${queryString}`} className="num text-micro underline">
                      {r.id}
                    </Link>{" "}
                    {r.acronym ?? r.title} <span className="text-muted">({r.research_area ?? r.is_combustion_basis ?? "not combustion"})</span>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </section>
      </div>
    </div>
  );
}
