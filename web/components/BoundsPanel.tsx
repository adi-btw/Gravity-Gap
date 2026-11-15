"use client";

import Link from "next/link";
import { useState } from "react";
import { api, type Sourced } from "@/lib/api";
import { fmtBand, fmtEstimate, fmtSig, humanize } from "@/lib/format";
import { G0 } from "@/lib/physics";
import { compareQuery, compareWithTarget } from "@/lib/compare";
import { coverageStatus } from "@/lib/coverage";
import { matchPreset, type Habitat } from "@/lib/habitat";
import type { AskAnswer, BoundsResult, MetricInfo, RefPoint, SensitivityRow } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";
import { useHabitat } from "@/lib/useHabitat";
import { useQueryParam } from "@/lib/useQueryParam";
import { AskAnswerView } from "./AskAnswer";
import { useAsk } from "./AskDrawer";
import { BandChart, type BandPoint } from "./charts/BandChart";
import { CoverageChart } from "./charts/CoverageChart";
import { RegimeFractionsBar } from "./charts/RegimeFractionsBar";
import { TornadoChart } from "./charts/TornadoChart";
import { DriversSection } from "./DriversPanel";
import { EvidenceList } from "./EvidenceList";
import { Empty, ErrorState, Loading, SourceChip } from "./ui/States";

const CONF_STYLE: Record<string, string> = {
  high: "border-micro text-micro",
  medium: "border-normal text-normal",
  low: "border-warn text-warn",
};

function isNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function numBand(b: RefPoint["band90"]): [number, number] | null {
  return b && isNum(b[0]) && isNum(b[1]) ? [b[0], b[1]] : null;
}

export function BoundsPanel() {
  const { habitat, queryString } = useHabitat();
  const [metric, setMetric] = useQueryParam("metric", "M1");
  const metrics = useAsync(() => api.metrics(), "metrics");
  const key = `${queryString}|${metric}`;
  const bounds = useAsync(() => api.bounds(habitat, metric), key);

  const list: MetricInfo[] = metrics.status === "ok" ? metrics.data.data : [];

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="doc-label">F4 · Bounds panel</p>
          <h1 className="page-title">What happens to a fire in this habitat?</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            A partial-gravity estimate with its 90% band, next to the microgravity (0 g) and Earth (1 g) references.
            Every estimate traces to the training tests listed below.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Link href={`/suppression?${queryString}`} className="text-sm text-micro underline hover:text-fg">
            How much CO₂ would put it out? →
          </Link>
          <Link
            href={`/compare?${compareQuery(compareWithTarget(habitat).a, compareWithTarget(habitat).b, queryString)}`}
            className="text-sm text-micro underline hover:text-fg"
          >
            Compare with another habitat →
          </Link>
          <Link href={`/trust?${queryString}`} className="text-sm text-micro underline hover:text-fg" data-testid="trust-link">
            How often are these bands right? →
          </Link>
          {bounds.status === "ok" ? <SourceChip source={bounds.data.source} note={bounds.data.note} /> : null}
        </div>
      </header>

      <fieldset>
        <legend className="mb-1 text-xs font-medium text-muted">Metric</legend>
        {metrics.status === "loading" ? <Loading label="Loading metrics…" /> : null}
        {metrics.status === "error" ? <ErrorState error={metrics.error} onRetry={metrics.reload} /> : null}
        <div className="flex flex-wrap gap-2">
          {list.map((m) => (
            <button
              key={m.id}
              type="button"
              aria-pressed={m.id === metric}
              onClick={() => setMetric(m.id)}
              title={m.data}
              className={`rounded-md border px-3 py-1.5 text-left text-[13px] transition-colors ${
                m.id === metric ? "border-fg bg-fg text-bg" : "border-line text-muted hover:border-line-strong hover:text-fg"
              }`}
            >
              <span className="num font-medium">{m.id}</span> {m.label}
            </button>
          ))}
        </div>
      </fieldset>

      {bounds.status === "loading" ? <Loading label="Computing bounds…" /> : null}
      {bounds.status === "error" ? <ErrorState error={bounds.error} onRetry={bounds.reload} /> : null}
      {bounds.status === "ok" ? (
        <BoundsView r={bounds.data.data} sourced={bounds.data} metricInfo={list.find((m) => m.id === metric)} queryString={queryString} habitat={habitat} />
      ) : null}
    </div>
  );
}

function BoundsView({
  r,
  sourced,
  metricInfo,
  queryString,
  habitat,
}: {
  r: BoundsResult;
  sourced: Sourced<BoundsResult>;
  metricInfo?: MetricInfo;
  queryString: string;
  habitat: Habitat;
}) {
  const habitatG = habitat.g_m_s2;
  const kind = r.kind ?? metricInfo?.kind ?? "quantity";
  const isCategory = kind === "category" || typeof r.estimate === "string";
  const gLabel = `${(habitatG / G0).toFixed(3)} g`;
  const evidenceIds = r.evidence.slice(0, 4).map((e) => e.record_id).join(", ");
  const trace = `${r.n_train} training tests; nearest evidence ${evidenceIds || "none"}`;

  return (
    <div className="space-y-4">
      {r.nonmonotonic_flag ? (
        <div role="alert" className="flex gap-2 rounded-lg border border-warn bg-[var(--warn-fill)] px-4 py-3 text-sm">
          <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" className="mt-0.5 shrink-0 text-warn">
            <path d="M12 3l10 18H2L12 3z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
            <path d="M12 10v5M12 18v.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <div>
            <p className="font-medium text-warn">Non-monotonic warning: partial gravity may be worse than both references</p>
            <p className="mt-1">{r.nonmonotonic_note ?? "The effective flow sits near the flammability peak."}</p>
          </div>
        </div>
      ) : null}

      <section className="panel" aria-labelledby="estimate-h">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="estimate-h" className="text-base font-medium">
            <span className="num">{r.metric}</span> · {r.label}
          </h2>
          <span className="num text-[11px] text-muted">
            model {r.model_version} · n_train {r.n_train}
          </span>
        </div>

        {!r.applicable ? (
          <div className="hatch mt-3 rounded-md border border-dashed border-line p-4" role="status" data-testid="bounds-extrapolation">
            <p className="text-sm font-medium">Extrapolation: no evidence</p>
            <p className="mt-1 text-sm">{r.reason ?? "The habitat is outside every tested condition for this metric."}</p>
            <p className="mt-2 text-xs text-muted">
              No number is shown on purpose. The chart shows every atmosphere this metric was actually tested in; your
              habitat (diamond) sits outside the shaded zone where the engine is allowed to estimate. The test planner
              lists experiments that would close this gap.
            </p>
            <CoverageSection metric={r.metric} habitat={habitat} inline />
          </div>
        ) : isCategory ? (
          <CategoryColumns r={r} gLabel={gLabel} />
        ) : (
          <NumericChart r={r} kind={kind} gLabel={gLabel} trace={trace} />
        )}
      </section>

      {r.applicable && !isCategory ? <DriversSection r={r} bounds={sourced} habitat={habitat} queryString={queryString} /> : null}

      {r.applicable ? <CoverageSection metric={r.metric} habitat={habitat} /> : null}

      <div className="grid gap-4 md:grid-cols-2">
        <section className="panel" aria-labelledby="transfer-h">
          <h2 id="transfer-h" className="mb-2 text-sm font-medium">
            Does microgravity evidence transfer here?
          </h2>
          {r.transfer ? (
            <>
              <span
                className={`inline-block rounded-sm border px-2 py-0.5 text-xs font-medium ${CONF_STYLE[r.transfer.confidence] ?? "border-line"}`}
              >
                transfer confidence: {r.transfer.confidence}
              </span>
              <p className="mt-2 text-sm">{r.transfer.basis}</p>
            </>
          ) : (
            <p className="text-sm text-muted">No transfer basis reported.</p>
          )}
          {r.regime_fractions ? (
            <div className="mt-3">
              <h3 className="mb-1 text-xs font-medium text-muted">Flame regime across uncertainty samples</h3>
              <RegimeFractionsBar fractions={r.regime_fractions} />
            </div>
          ) : null}
          {r.u_eff_summary ? (
            <p className="num mt-2 text-xs text-muted">
              u_eff p05 {fmtSig(r.u_eff_summary.p05)} · p50 {fmtSig(r.u_eff_summary.p50)} · p95 {fmtSig(r.u_eff_summary.p95)} cm/s
            </p>
          ) : null}
        </section>

        <section className="panel" aria-labelledby="sens-h">
          <h2 id="sens-h" className="mb-2 text-sm font-medium">
            Sensitivity
          </h2>
          <details data-testid="one-at-a-time">
            <summary className="cursor-pointer text-sm text-micro hover:text-fg">One-at-a-time view</summary>
            <p className="mt-1 mb-2 text-xs text-muted">
              Each input moved alone from its low to its high value while the others stay put. It is not the same as the
              band-width shares in &ldquo;What makes this band wide&rdquo;, which split the band itself.
            </p>
            <Sensitivity rows={r.sensitivity} kind={kind} unit={r.unit} />
          </details>
        </section>
      </div>

      <section className="panel" aria-labelledby="ev-h">
        <h2 id="ev-h" className="mb-2 text-sm font-medium">
          Evidence ({r.evidence.length} nearest training record{r.evidence.length === 1 ? "" : "s"})
        </h2>
        <EvidenceList rows={r.evidence} queryString={queryString} />
      </section>

      <Explain r={r} />
    </div>
  );
}

function NumericChart({ r, kind, gLabel, trace }: { r: BoundsResult; kind: string; gLabel: string; trace: string }) {
  const est = isNum(r.estimate) ? r.estimate : null;
  const points: BandPoint[] = [
    {
      key: "0g",
      label: "0 g reference",
      sublabel: "ISS / Cygnus",
      estimate: r.ref_0g && isNum(r.ref_0g.estimate) ? r.ref_0g.estimate : null,
      band: r.ref_0g ? numBand(r.ref_0g.band90) : null,
      color: "var(--micro)",
      fill: "var(--micro-fill)",
    },
    {
      key: "partial",
      label: "Your habitat",
      sublabel: gLabel,
      estimate: est,
      band: numBand(r.band90),
      color: "var(--partial)",
      fill: "var(--partial-fill)",
      trace: `Partial-g estimate ${fmtEstimate(est, kind, r.unit)}, 90% band ${fmtBand(r.band90, kind, r.unit)}. ${trace}`,
    },
    {
      key: "1g",
      label: "1 g reference",
      sublabel: r.ref_1g ? "Earth" : "no 1 g basis",
      estimate: r.ref_1g && isNum(r.ref_1g.estimate) ? r.ref_1g.estimate : null,
      band: r.ref_1g ? numBand(r.ref_1g.band90) : null,
      color: "var(--normal)",
      fill: "var(--normal-fill)",
    },
  ];
  const prob = kind === "probability";
  const rows = [
    ["0 g reference", r.ref_0g],
    [`Your habitat (${gLabel})`, { estimate: r.estimate, band90: r.band90 }],
    ["1 g reference", r.ref_1g],
  ] as const;
  return (
    <div className="mt-3 grid gap-4 lg:grid-cols-[3fr_2fr]">
      <BandChart
        points={points}
        unit={prob ? "probability" : r.unit}
        domain={prob ? [0, 1] : undefined}
        ariaLabel={`${r.label}: 0 g reference ${fmtEstimate(points[0].estimate, kind, r.unit)}, your habitat ${fmtEstimate(est, kind, r.unit)} with 90% band ${fmtBand(r.band90, kind, r.unit)}, 1 g reference ${r.ref_1g ? fmtEstimate(points[2].estimate, kind, r.unit) : "not available"}.`}
      />
      <div>
        <p className="text-sm">
          Estimate <span className="num text-2xl font-medium text-partial" data-testid="bounds-estimate">{fmtEstimate(est, kind, r.unit)}</span>
        </p>
        <p className="text-sm text-muted">
          90% band <span className="num text-fg" data-testid="bounds-band">{fmtBand(r.band90, kind, r.unit)}</span>
        </p>
        <table className="mt-3 w-full text-left text-xs">
          <caption className="sr-only">Estimates and 90% bands (table alternative to the chart)</caption>
          <thead className="text-muted">
            <tr>
              <th scope="col" className="py-1 pr-2">Reference</th>
              <th scope="col" className="py-1 pr-2">Estimate</th>
              <th scope="col" className="py-1">90% band</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([name, ref]) => (
              <tr key={name} className="border-t border-line">
                <th scope="row" className="py-1 pr-2 font-normal">{name}</th>
                <td className="num py-1 pr-2">{ref ? fmtEstimate(ref.estimate, kind, r.unit) : "no basis"}</td>
                <td className="num py-1">{ref ? fmtBand(ref.band90, kind, r.unit) : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CategoryColumns({ r, gLabel }: { r: BoundsResult; gLabel: string }) {
  const cols = [
    { name: "0 g reference", ref: r.ref_0g, cls: "border-micro text-micro" },
    { name: `Your habitat (${gLabel})`, ref: { estimate: r.estimate, band90: r.band90 } as RefPoint, cls: "border-partial text-partial" },
    { name: "1 g reference", ref: r.ref_1g, cls: "border-normal text-normal" },
  ];
  return (
    <div className="mt-3 grid gap-3 sm:grid-cols-3" role="list" aria-label="Outcome at 0 g, your habitat and 1 g">
      {cols.map((c) => (
        <div key={c.name} role="listitem" className={`rounded-sm border border-l-[3px] bg-surface p-3 ${c.cls}`}>
          <p className="text-xs font-medium">{c.name}</p>
          {c.ref && c.ref.estimate !== null ? (
            <>
              <p className="mt-1 text-lg font-medium capitalize text-fg">{fmtEstimate(c.ref.estimate, "category")}</p>
              <p className="text-xs text-muted">
                range: <span className="num">{fmtBand(c.ref.band90, "category")}</span>
              </p>
            </>
          ) : (
            <p className="mt-1 text-sm text-muted">no basis</p>
          )}
        </div>
      ))}
    </div>
  );
}

function Sensitivity({ rows, kind, unit }: { rows: SensitivityRow[]; kind: string; unit: string | null }) {
  const numeric = rows.filter((x) => isNum(x.low) && isNum(x.high)) as (SensitivityRow & { low: number; high: number })[];
  const categorical = rows.filter((x) => typeof x.low === "string" || typeof x.high === "string");
  if (!numeric.length && !categorical.length) {
    return <Empty>No sensitivity is reported (no estimate at this habitat).</Empty>;
  }
  const groups = new Map<string, typeof numeric>();
  numeric.forEach((x) => {
    const q = x.quantity ?? "estimate";
    groups.set(q, [...(groups.get(q) ?? []), x]);
  });
  return (
    <div className="space-y-3">
      {[...groups.entries()].map(([q, rs]) => {
        const base = rs.find((x) => isNum(x.baseline))?.baseline;
        const title = q === "band_width" ? "Effect on the 90% band width" : "Effect on the estimate";
        return (
          <div key={q}>
            <h3 className="text-xs font-medium text-muted">{title}</h3>
            <TornadoChart
              rows={rs.map((x) => ({ param: x.param, low: x.low, high: x.high }))}
              base={isNum(base) ? base : null}
              unit={q === "band_width" ? null : kind === "probability" ? null : unit}
              ariaLabel={`${title}: ${rs.map((x) => `${x.param} from ${fmtSig(x.low)} to ${fmtSig(x.high)}`).join("; ")}`}
            />
            <table className="w-full text-left text-[11px]">
              <caption className="sr-only">{title} (table)</caption>
              <thead className="text-muted">
                <tr>
                  <th scope="col">Parameter</th>
                  <th scope="col">Input low → high</th>
                  <th scope="col">Value at low</th>
                  <th scope="col">Value at high</th>
                </tr>
              </thead>
              <tbody className="num">
                {rs.map((x) => (
                  <tr key={x.param} className="border-t border-line">
                    <th scope="row" className="font-normal">{x.param}</th>
                    <td>{isNum(x.input_low) && isNum(x.input_high) ? `${fmtSig(x.input_low)} → ${fmtSig(x.input_high)}` : "–"}</td>
                    <td>{fmtSig(x.low)}</td>
                    <td>{fmtSig(x.high)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
      {categorical.length ? (
        <table className="w-full text-left text-xs">
          <caption className="mb-1 text-left text-xs font-medium text-muted">Outcome at each parameter&apos;s low and high setting</caption>
          <thead className="text-muted">
            <tr>
              <th scope="col">Parameter</th>
              <th scope="col">Low</th>
              <th scope="col">High</th>
            </tr>
          </thead>
          <tbody>
            {categorical.map((x) => (
              <tr key={x.param} className="border-t border-line">
                <th scope="row" className="num font-normal">{x.param}</th>
                <td>{x.low === null ? "–" : humanize(String(x.low))}</td>
                <td>{x.high === null ? "–" : humanize(String(x.high))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}

function Explain({ r }: { r: BoundsResult }) {
  const { habitat } = useHabitat();
  const { open } = useAsk();
  const [state, setState] = useState<
    { s: "idle" } | { s: "loading" } | { s: "ok"; r: Sourced<AskAnswer> } | { s: "error"; e: Error }
  >({ s: "idle" });
  const preset = matchPreset(habitat);
  const where = preset ? `the ${preset.label.toLowerCase()}` : "this habitat";
  // Phrased like the pre-generated demo questions so the offline cache can answer it.
  const question = r.applicable ? `Why is the ${r.metric} band wide for ${where}?` : `Why is there no ${r.metric} estimate for ${where}?`;
  const contextIds = [r.metric, ...new Set(r.evidence.map((e) => e.investigation_id))];

  const run = async () => {
    setState({ s: "loading" });
    try {
      setState({ s: "ok", r: await api.ask(question, habitat, contextIds) });
    } catch (e) {
      setState({ s: "error", e: e instanceof Error ? e : new Error(String(e)) });
    }
  };

  return (
    <section className="panel" aria-labelledby="explain-h">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="explain-h" className="text-sm font-medium">
          Explain this prediction
        </h2>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={run}
            disabled={state.s === "loading"}
            className="rounded-md border border-partial px-3 py-1.5 text-sm text-partial hover:bg-surface-2 disabled:opacity-50"
          >
            Explain
          </button>
          <button
            type="button"
            onClick={() => open({ question, contextIds })}
            className="rounded-md border border-line px-3 py-1.5 text-sm text-muted hover:text-fg"
          >
            Ask a follow-up
          </button>
        </div>
      </div>
      <p className="mt-1 text-xs text-muted">
        Asks: <q>{question}</q> for {preset ? preset.label : "this custom habitat"}, with {r.metric} and its evidence as context.
      </p>
      <div className="mt-3" aria-live="polite">
        {state.s === "loading" ? <Loading label="Explaining…" /> : null}
        {state.s === "error" ? <ErrorState error={state.e} onRetry={run} /> : null}
        {state.s === "ok" ? <AskAnswerView answer={state.r.data} source={state.r.source} note={state.r.note} /> : null}
      </div>
    </section>
  );
}

/** "Where does this metric have evidence?" Tested O2 x pressure points vs the habitat (same rule as the engine gate). */
function CoverageSection({ metric, habitat, inline = false }: { metric: string; habitat: Habitat; inline?: boolean }) {
  const cov = useAsync(() => api.coverage(metric), `coverage|${metric}`);
  const label = matchPreset(habitat)?.label ?? "Your habitat";
  const body =
    cov.status === "loading" ? (
      <Loading label="Loading tested conditions…" />
    ) : cov.status === "error" ? (
      <ErrorState error={cov.error} onRetry={cov.reload} />
    ) : (
      (() => {
        const c = cov.data.data;
        const s = coverageStatus(c, habitat.o2, habitat.p_psia);
        const assumed = c.points.find((p) => p.assumed)?.assumed;
        return (
          <div className="grid gap-x-10 gap-y-3 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:items-end">
            <div className="max-w-[680px]">
              <CoverageChart cov={c} status={s} habitatLabel={label} />
            </div>
            <div>
            <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted" aria-label="Chart legend">
              <li>
                <span aria-hidden="true" className="mr-1 inline-block h-2.5 w-2.5 rounded-full bg-micro align-middle" />
                tested condition (bigger dot = more tests)
              </li>
              <li>
                <span aria-hidden="true" className="mr-1 inline-block h-2.5 w-4 rounded-sm bg-[var(--micro-fill)] align-middle" />
                zone where the engine gives a number
              </li>
              <li>
                <span aria-hidden="true" className="mr-1 inline-block h-2.5 w-2.5 rotate-45 bg-partial align-middle" />
                your habitat
              </li>
            </ul>
            <p className="mt-2 text-xs">
              <span className="font-medium">{c.note}</span> across {c.points.length} tested atmosphere
              {c.points.length === 1 ? "" : "s"}. {c.rule.text}
              {s.nearest && s.nearestDistance !== null ? (
                <>
                  {" "}
                  Nearest test: <span className="num">{(s.nearest.o2 * 100).toFixed(1)}% O₂</span> at{" "}
                  <span className="num">{(s.nearest.p_atm * 14.696).toFixed(1)} psia</span> ({s.nearest.investigation_id}), atmosphere
                  distance <span className="num">{s.nearestDistance.toFixed(2)}</span>.
                </>
              ) : null}
            </p>
            {assumed ? <p className="mt-1 text-[11px] text-muted">Hollow dots: {assumed}.</p> : null}
            </div>
          </div>
        );
      })()
    );
  if (inline) {
    return (
      <div className="mt-3 panel-tight" aria-label="Tested conditions for this metric">
        {body}
      </div>
    );
  }
  return (
    <section className="panel" aria-labelledby="coverage-h">
      <h2 id="coverage-h" className="mb-2 text-sm font-medium">
        Where this metric has evidence
      </h2>
      {body}
    </section>
  );
}
