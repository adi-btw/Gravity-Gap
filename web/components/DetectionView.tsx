"use client";

import { api } from "@/lib/api";
import {
  binMaterials,
  fmtNm,
  fmtShare,
  logDomain,
  pickBinSeries,
  simCases,
  simForCase,
  sourceText,
  type DetectionArtifact,
  type DetectionSource,
  type SimSeries,
} from "@/lib/detection";
import { fmtSig } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";
import { useQueryParam } from "@/lib/useQueryParam";
import { useState } from "react";
import { CaveatBanner } from "./CaveatBanner";
import { LogLineChart, LogLineLegend, type LogLineSeries } from "./charts/LogLineChart";
import { LogStripChart, StripLegend, type StripKind, type StripRow } from "./charts/LogStripChart";
import { ErrorState, Loading, SourceChip } from "./ui/States";

const X_NM = "particle diameter (nm, log scale)";

/** R3: what the PSI files say about smoke particle sizes (reduced scope, ADR-0007). */
export function DetectionView() {
  const state = useAsync(() => api.detection(), "detection");
  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="doc-label">R3 · Smoke detection</p>
          <h1 className="page-title">Detection evidence</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Smoke detectors react to particles in the air, and how well they work depends on particle size. This page
            shows how big the smoke particles from heated spacecraft materials were in NASA tests, how that compares
            with one test dust on one size measure, and what a computer model says gravity does to smoke sizes.
          </p>
        </div>
        {state.status === "ok" ? <SourceChip source={state.data.source} note={state.data.note} /> : null}
      </header>

      {state.status === "loading" ? <Loading label="Loading detection evidence…" /> : null}
      {state.status === "error" ? <ErrorState error={state.error} onRetry={state.reload} /> : null}
      {state.status === "ok" ? <Evidence d={state.data.data} /> : null}
    </div>
  );
}

function SourceLine({ source, label = "Source" }: { source: DetectionSource; label?: string }) {
  return (
    <p className="mt-2 break-words text-xs text-muted" data-testid="source-line">
      {label}: <span className="num">{sourceText(source)}</span>
    </p>
  );
}

function Toggle({ pressed, onClick, children }: { pressed: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={`rounded-md border px-3 py-1.5 text-sm ${pressed ? "border-micro bg-surface-2 text-fg" : "border-line text-muted hover:text-fg"}`}
    >
      {children}
    </button>
  );
}

function Evidence({ d }: { d: DetectionArtifact }) {
  const lunar = d.gaps.find((g) => g.id === "lunar_dust");
  const others = d.gaps.filter((g) => g.id !== "lunar_dust");
  return (
    <div className="space-y-4">
      <CaveatBanner title="Scope of this page">
        <p data-testid="scope-note">{d.scope_note}</p>
      </CaveatBanner>

      <section aria-labelledby="gaps-h" className="space-y-2">
        <h2 id="gaps-h" className="text-base font-medium">
          What these data cannot tell you
        </h2>
        {lunar ? (
          <CaveatBanner tone="warn" title="Not answered: could lunar dust fool a smoke detector?">
            <p data-testid="gap-lunar_dust">{lunar.text}</p>
          </CaveatBanner>
        ) : null}
        <ul className="list-disc space-y-1 rounded-lg border border-line bg-surface py-3 pl-8 pr-4 text-sm" data-testid="gaps-list">
          {others.map((g) => (
            <li key={g.id} data-testid={`gap-${g.id}`}>
              {g.text}
            </li>
          ))}
        </ul>
      </section>

      <SizeDefinitions d={d} />
      <SmokeBins d={d} />
      <SmokeRunsSection d={d} />
      <AverageMass d={d} />
      <Simulation d={d} />

      <details className="panel text-xs">
        <summary className="cursor-pointer text-muted">Files used to build this page ({d.generated_from.length})</summary>
        <ul className="mt-2 space-y-1">
          {d.generated_from.map((f) => (
            <li key={f.file} className="break-all">
              <span className="num">{f.file}</span> <span className="text-muted">sha256 {f.sha256.slice(0, 12)}…</span>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

function SizeDefinitions({ d }: { d: DetectionArtifact }) {
  const defs = Object.entries(d.size_definitions);
  if (!defs.length) return null;
  return (
    <section aria-labelledby="defs-h" className="panel">
      <h2 id="defs-h" className="text-base font-medium">
        Four ways to measure &ldquo;size&rdquo;
      </h2>
      <p className="mb-2 text-xs text-muted">
        They give different numbers for the same smoke, so each chart below uses only one of them.
      </p>
      <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
        {defs.map(([key, def]) => (
          <div key={key} className="contents">
            <dt className="font-medium">{def.label}</dt>
            <dd className="text-muted">{def.note}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

// ------------------------------------------------------------------ 1. TEM size distributions

function SmokeBins({ d }: { d: DetectionArtifact }) {
  const materials = binMaterials(d);
  const [rawMat, setMat] = useQueryParam("material", materials[0]?.material ?? "");
  const [rawVar, setVar] = useQueryParam("cut", "all");
  const material = materials.some((m) => m.material === rawMat) ? rawMat : (materials[0]?.material ?? "");
  const variant = rawVar === "big_only" ? "big_only" : "all";
  const s = pickBinSeries(d, material, variant);
  if (!s) return null;
  const def = d.size_definitions[s.size_definition];
  const xDomain = logDomain(d.smoke_bins.flatMap((b) => b.diameter_nm));
  const series: LogLineSeries[] = [{ id: s.id, label: s.label, x: s.diameter_nm, y: s.fraction, color: "var(--micro)", marker: "circle" }];
  const aria = `${s.label}. Share of ${Math.round(s.stats.particle_count)} counted particles in each size bin, against particle diameter in nanometres on a log scale (${def?.label ?? s.size_definition}). Count median ${fmtNm(s.stats.count_median_diameter_nm)}, geometric mean ${fmtNm(s.stats.geometric_mean_diameter_nm)}. Source: ${sourceText(s.source)}.`;

  return (
    <section className="panel" aria-labelledby="bins-h">
      <h2 id="bins-h" className="text-base font-medium">
        How big are smoke particles? Microscope counts
      </h2>
      <p className="mb-3 text-xs text-muted">
        Size measure: {def?.label ?? s.size_definition}. One test run per material.
      </p>
      <div className="flex flex-wrap gap-4">
        <fieldset>
          <legend className="mb-1 text-xs font-medium text-muted">Material burned</legend>
          <div className="flex flex-wrap gap-2">
            {materials.map((m) => (
              <Toggle key={m.material} pressed={m.material === material} onClick={() => setMat(m.material)}>
                {m.label}
              </Toggle>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend className="mb-1 text-xs font-medium text-muted">Particles shown</legend>
          <div className="flex flex-wrap gap-2">
            {(["all", "big_only"] as const).map((v) => {
              const vs = pickBinSeries(d, material, v);
              return (
                <Toggle key={v} pressed={variant === v} onClick={() => setVar(v)}>
                  {vs && vs.variant === v ? vs.variant_label : v === "all" ? "All particles counted" : "Larger particles only"}
                </Toggle>
              );
            })}
          </div>
        </fieldset>
      </div>
      <h3 className="mt-3 text-sm font-medium" data-testid="bins-title">
        {s.label}
      </h3>
      <div className="max-w-3xl">
        <LogLineChart
          testId="bins-chart"
          series={series}
          xDomain={xDomain}
          xLabel={X_NM}
          yLabel="share of particles in the bin (%)"
          ariaLabel={aria}
        />
        <LogLineLegend series={series} />
      </div>
      <p className="mt-2 text-sm">{s.note}</p>
      <div className="mt-2 overflow-x-auto">
        <table className="text-sm" data-testid="bins-stats">
          <caption className="sr-only">Summary numbers for {s.label}</caption>
          <tbody className="num">
            <tr>
              <th scope="row" className="pr-4 text-left font-sans text-xs font-normal text-muted">Particles counted</th>
              <td>{Math.round(s.stats.particle_count).toLocaleString("en-US")}</td>
            </tr>
            <tr>
              <th scope="row" className="pr-4 text-left font-sans text-xs font-normal text-muted">Middle size (half smaller, half bigger)</th>
              <td>{fmtNm(s.stats.count_median_diameter_nm)}</td>
            </tr>
            <tr>
              <th scope="row" className="pr-4 text-left font-sans text-xs font-normal text-muted">Geometric mean size</th>
              <td>
                {fmtNm(s.stats.geometric_mean_diameter_nm)}
                {s.workbook_reported ? (
                  <span className="ml-2 font-sans text-xs text-muted">
                    (workbook cells {s.workbook_reported.cells}: {fmtNm(s.workbook_reported.geometric_mean_diameter_nm)})
                  </span>
                ) : null}
              </td>
            </tr>
            <tr>
              <th scope="row" className="pr-4 text-left font-sans text-xs font-normal text-muted">Spread (geometric standard deviation, no unit)</th>
              <td>{fmtSig(s.stats.geometric_std, 3)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <SourceLine source={s.source} />
    </section>
  );
}

// ------------------------------------------------------------------ 2. per-run moments

const AGE_KINDS: Record<string, StripKind> = {
  unaged: { label: "Fresh smoke (filled circle)", color: "var(--micro)", shape: "circle" },
  aged: { label: "Aged smoke, measured again later (hollow diamond)", color: "var(--normal)", shape: "diamond", hollow: true },
};

function SmokeRunsSection({ d }: { d: DetectionArtifact }) {
  const r = d.smoke_runs;
  const def = d.size_definitions[r.size_definition];
  const labelOf = (m: string) => r.material_labels[m] ?? m;
  const rows: StripRow[] = r.materials.map((m) => ({
    key: m,
    label: labelOf(m),
    points: r.points
      .filter((p) => p.material === m)
      .map((p) => ({
        value: p.value_nm,
        kind: p.aged ? "aged" : "unaged",
        title: `${labelOf(m)} run ${p.run}${p.aged ? " (aged)" : ""}: ${fmtNm(p.value_nm)}${p.description ? `, ${p.description}` : ""} (row ${p.row})`,
      })),
  }));
  const n = r.points.length;
  const nAged = r.points.filter((p) => p.aged).length;
  const aria = `${r.label}: ${n} test runs (${nAged} aged), one dot per run, grouped by material (${r.materials.map(labelOf).join(", ")}), against middle size in nanometres on a log scale (${def?.label ?? r.size_definition}). ${r.by_material
    .filter((b) => !b.aged)
    .map((b) => `${b.material_label} fresh median ${fmtNm(b.dg_nm.median)}`)
    .join("; ")}. Source: ${sourceText(r.source)}.`;

  return (
    <section className="panel" aria-labelledby="runs-h">
      <h2 id="runs-h" className="text-base font-medium">
        Smoke size in every test run
      </h2>
      <p className="mb-2 text-xs text-muted">Size measure: {def?.label ?? r.size_definition}. {def?.note}</p>
      <div className="max-w-3xl">
        <LogStripChart testId="runs-chart" rows={rows} kinds={AGE_KINDS} xLabel={`middle size per run, ${X_NM}`} ariaLabel={aria} />
        <StripLegend kinds={AGE_KINDS} />
      </div>
      <p className="mt-2 text-sm">{r.note}</p>
      <details className="mt-2 text-xs">
        <summary className="cursor-pointer text-muted">Show per-material numbers as a table</summary>
        <div className="overflow-x-auto">
          <table className="mt-2 w-full text-left text-xs" data-testid="runs-table">
            <caption className="sr-only">Smoke middle size by material, fresh and aged</caption>
            <thead className="text-muted">
              <tr>
                <th scope="col" className="py-1 pr-3 font-medium">Material</th>
                <th scope="col" className="py-1 pr-3 font-medium">Smoke</th>
                <th scope="col" className="py-1 pr-3 font-medium">Runs</th>
                <th scope="col" className="py-1 pr-3 font-medium">Middle size, median (min–max)</th>
                <th scope="col" className="py-1 pr-3 font-medium">Spread, median (no unit)</th>
              </tr>
            </thead>
            <tbody className="num">
              {r.by_material.map((b) => (
                <tr key={`${b.material}-${b.aged}`} className="border-t border-line">
                  <td className="py-1 pr-3 font-sans">{b.material_label}</td>
                  <td className="py-1 pr-3 font-sans">{b.aged ? "aged" : "fresh"}</td>
                  <td className="py-1 pr-3">{b.n_runs}</td>
                  <td className="py-1 pr-3">
                    {fmtNm(b.dg_nm.median)} ({fmtNm(b.dg_nm.min)}–{fmtNm(b.dg_nm.max)})
                  </td>
                  <td className="py-1 pr-3">{fmtSig(b.geometric_std_median, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <SourceLine source={r.source} />
    </section>
  );
}

// ------------------------------------------------------------------ 3. like-for-like smoke vs dust

const AMC_KINDS: Record<string, StripKind> = {
  smoke: { label: "Smoke, one test run (circle)", color: "var(--micro)", shape: "circle" },
  dust: { label: "Arizona Road Dust (DAFT), one dust bag (square)", color: "var(--normal)", shape: "square" },
};

function AverageMass({ d }: { d: DetectionArtifact }) {
  const c = d.average_mass_comparison;
  const def = d.size_definitions[c.size_definition];
  const density = c.dust.assumed_density_g_per_cm3;
  const rows: StripRow[] = [
    {
      key: "smoke",
      label: "Smoke (SAME-R)",
      points: c.smoke.points.map((p) => ({
        value: p.value_nm,
        kind: "smoke",
        title: `${d.smoke_runs.material_labels[p.material] ?? p.material} run ${p.run}${p.aged ? " (aged)" : ""}: ${fmtNm(p.value_nm)} (row ${p.row})`,
      })),
    },
    {
      key: "dust",
      label: c.dust.label,
      note: `assumes density ${density} g/cm³`,
      points: c.dust.points.map((p) => ({ value: p.value_nm, kind: "dust", title: `${c.dust.label}, bag ${p.bag}: ${fmtNm(p.value_nm)}` })),
    },
  ];
  const aria = `${def?.label ?? c.size_definition} in nanometres on a log scale. ${c.smoke.label}: ${c.smoke.points.length} runs from ${fmtNm(c.smoke.range_nm.min)} to ${fmtNm(c.smoke.range_nm.max)}. ${c.dust.label}: ${c.dust.points.length} bags from ${fmtNm(c.dust.range_nm.min)} to ${fmtNm(c.dust.range_nm.max)}, assuming a density of ${density} g/cm³. Sources: ${sourceText(c.smoke.source)}; ${sourceText(c.dust.source)}.`;

  return (
    <section className="panel" aria-labelledby="amc-h">
      <h2 id="amc-h" className="text-base font-medium">
        Smoke and dust on the same size measure
      </h2>
      <p className="mb-2 text-xs text-muted">Size measure: {def?.label ?? c.size_definition}. {def?.note}</p>
      <div className="grid gap-3 lg:grid-cols-[1fr_18rem]">
        <div>
          <LogStripChart
            testId="amc-chart"
            rows={rows}
            kinds={AMC_KINDS}
            rowHeight={56}
            xLabel={`diameter of average mass, ${X_NM}`}
            ariaLabel={aria}
          />
          <StripLegend kinds={AMC_KINDS} />
        </div>
        <CaveatBanner title={`${c.dust.label}: density assumption`}>
          <p data-testid="density-note">{c.dust.density_note}</p>
        </CaveatBanner>
      </div>
      <p className="mt-2 text-sm">{c.note}</p>
      <p className="mt-2 text-sm">
        {c.smoke.label}: <span className="num">{fmtNm(c.smoke.range_nm.min)}</span> to{" "}
        <span className="num">{fmtNm(c.smoke.range_nm.max)}</span> over {c.smoke.points.length} runs. {c.dust.label}:{" "}
        <span className="num">{fmtNm(c.dust.range_nm.min)}</span> to <span className="num">{fmtNm(c.dust.range_nm.max)}</span> over{" "}
        {c.dust.points.length} bags.
      </p>
      <p className="mt-2 text-xs">
        <span className="text-muted">What the dust was, quoted from the DAFT table:</span> <q>{c.dust.material_text}</q>
      </p>
      <div className="mt-2 overflow-x-auto">
        <table className="text-left text-xs" data-testid="dust-table">
          <caption className="sr-only">{c.dust.label}, per bag</caption>
          <thead className="text-muted">
            <tr>
              <th scope="col" className="py-1 pr-3 font-medium">Dust bag</th>
              <th scope="col" className="py-1 pr-3 font-medium">Diameter of average mass</th>
              <th scope="col" className="py-1 pr-3 font-medium">Particles (per cm³)</th>
              <th scope="col" className="py-1 pr-3 font-medium">Mass (mg per m³)</th>
            </tr>
          </thead>
          <tbody className="num">
            {c.dust.points.map((p) => (
              <tr key={p.bag} className="border-t border-line">
                <td className="py-1 pr-3">{p.bag}</td>
                <td className="py-1 pr-3">{fmtNm(p.value_nm)}</td>
                <td className="py-1 pr-3">{p.number_per_cm3 !== undefined ? Number(fmtSig(p.number_per_cm3, 3)).toLocaleString("en-US") : "–"}</td>
                <td className="py-1 pr-3">{p.mass_mg_per_m3 !== undefined ? fmtSig(p.mass_mg_per_m3, 3) : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <SourceLine label="Smoke source" source={c.smoke.source} />
      <SourceLine label="Dust source" source={c.dust.source} />
      <SourceLine label="Dust material source" source={c.dust.material_source} />
    </section>
  );
}

// ------------------------------------------------------------------ 4. PSI-115 simulation

function simStyle(s: SimSeries): Pick<LogLineSeries, "color" | "dash" | "marker"> {
  if (s.variant !== "base") return { color: "var(--partial)", dash: "2 3", marker: "none" };
  return s.gravity === "earth" ? { color: "var(--normal)", marker: "square" } : { color: "var(--micro)", dash: "6 4", marker: "circle" };
}

function Simulation({ d }: { d: DetectionArtifact }) {
  const [variants, setVariants] = useState(false);
  const cases = simCases(d);
  if (!cases.length) return null;
  const hasVariants = d.simulation.some((s) => s.variant !== "base");
  const first = d.simulation[0];
  const xDomain = logDomain(d.simulation.flatMap((s) => s.diameter_nm));

  return (
    <section className="rounded-lg border border-dashed border-partial bg-surface p-4" aria-labelledby="sim-h">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-sm border border-partial px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-partial">
          Simulation
        </span>
        <h2 id="sim-h" className="text-base font-medium">
          What gravity does to smoke sizes, in a computer model
        </h2>
      </div>
      <p className="mt-1 text-sm">{first.note}</p>
      <p className="mt-1 text-xs text-muted">
        Stand-in smoke: {first.surrogate}, at t = {first.time_s} s. Shapes only: the curves are never compared with the
        measured smoke above.
      </p>
      {hasVariants ? (
        <div className="mt-3">
          <Toggle pressed={variants} onClick={() => setVariants((v) => !v)}>
            Also show model checks (one effect switched off)
          </Toggle>
        </div>
      ) : null}
      <div className="mt-3 grid gap-4 lg:grid-cols-2">
        {cases.map((c) => {
          const curves = simForCase(d, c.case, variants);
          const series: LogLineSeries[] = curves.map((s) => ({ id: s.id, label: s.label, x: s.diameter_nm, y: s.fraction, ...simStyle(s) }));
          const aria = `Simulation, case ${c.case} (${c.case_label}): share of particle count per size class against size-class diameter in nanometres on a log scale. ${curves
            .map((s) => `${s.label}: peak at ${fmtNm(s.stats.peak_diameter_nm)}, ${fmtShare(s.stats.share_of_count_above_20um)} of the count above 20 µm`)
            .join(". ")}. Source: ${curves.map((s) => sourceText(s.source)).join("; ")}.`;
          return (
            <div key={c.case} data-testid={`sim-case-${c.case}`}>
              <h3 className="text-sm font-medium">
                Simulation, case {c.case} ({c.case_label})
              </h3>
              <LogLineChart
                testId={`sim-chart-${c.case}`}
                series={series}
                xDomain={xDomain}
                xLabel={`size class in the simulation (nm, log scale)`}
                yLabel="share of particle count (%)"
                ariaLabel={aria}
              />
              <LogLineLegend series={series} />
              <div className="mt-2 overflow-x-auto">
                <table className="w-full text-left text-xs" data-testid={`sim-table-${c.case}`}>
                  <caption className="sr-only">Simulation case {c.case} summary per curve</caption>
                  <thead className="text-muted">
                    <tr>
                      <th scope="col" className="py-1 pr-3 font-medium">Curve</th>
                      <th scope="col" className="py-1 pr-3 font-medium">Peak size</th>
                      <th scope="col" className="py-1 pr-3 font-medium">Share above 20 µm (20,000 nm)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {curves.map((s) => (
                      <tr key={s.id} className="border-t border-line">
                        <td className="py-1 pr-3">
                          {s.gravity === "earth" ? "Earth gravity" : "Microgravity"}
                          {s.variant === "no_settling" ? ", settling off" : s.variant === "no_thermophoresis" ? ", thermophoresis off" : ""}
                        </td>
                        <td className="num py-1 pr-3">{fmtNm(s.stats.peak_diameter_nm)}</td>
                        <td className="num py-1 pr-3" data-testid={`share20-${s.id}`}>
                          {fmtShare(s.stats.share_of_count_above_20um)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {Array.from(new Map(curves.map((s) => [sourceText(s.source), s.source])).values()).map((src) => (
                <SourceLine key={src.file} source={src} />
              ))}
            </div>
          );
        })}
      </div>
    </section>
  );
}
