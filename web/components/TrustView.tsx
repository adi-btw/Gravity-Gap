"use client";

import { api } from "@/lib/api";
import {
  HOLDOUT_METRICS,
  atmText,
  bandText,
  fmtCount,
  fmtInterval,
  fmtPct,
  mapPoints,
  markCounts,
  observedText,
  skipReasons,
  worstMissRows,
  type HoldoutArtifact,
  type HoldoutRate,
  type HoldoutResult,
} from "@/lib/holdout";
import { useAsync } from "@/lib/useAsync";
import { useQueryParam } from "@/lib/useQueryParam";
import { CaveatBanner } from "./CaveatBanner";
import { HoldoutMap, HoldoutMarker } from "./charts/HoldoutMap";
import { ErrorState, Loading, SourceChip } from "./ui/States";

type Scheme = "atmosphere" | "wide";

/** S2 "Can I trust it?" (ADR-0009): how often the bands held when the tests behind them were hidden. */
export function TrustView() {
  const state = useAsync(() => api.holdout(), "holdout");
  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="doc-label">S2 · Honesty test</p>
          <h1 className="page-title">Can I trust it?</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            We hid tests the models were trained on, refitted the models without them, and asked the app about those
            atmospheres exactly as you would. Then we checked whether the 90% band caught what the hidden tests really
            showed, and whether &ldquo;no evidence&rdquo; was the right call. The results are shown as they came out, misses
            included.
          </p>
        </div>
        {state.status === "ok" ? <SourceChip source={state.data.source} note={state.data.note} /> : null}
      </header>
      {state.status === "loading" ? <Loading label="Loading the honesty test…" /> : null}
      {state.status === "error" ? <ErrorState error={state.error} onRetry={state.reload} /> : null}
      {state.status === "ok" ? <Trust d={state.data.data} /> : null}
    </div>
  );
}

function Rate({ r, testid }: { r: HoldoutRate | null | undefined; testid?: string }) {
  if (!r || !r.n) return <span className="text-muted">no groups</span>;
  return (
    <span data-testid={testid}>
      <span className="num font-semibold">{fmtCount(r)}</span>{" "}
      <span className="num text-muted">
        ({fmtPct(r.rate)}, 90% interval {fmtInterval(r.interval90)})
      </span>
    </span>
  );
}

function WeakBadge() {
  return (
    <span className="ml-1 inline-block rounded border border-warn px-1.5 py-0.5 text-[11px] font-semibold uppercase text-warn" data-testid="weak-test">
      weak test
    </span>
  );
}

function Pooled({ r }: { r: HoldoutResult }) {
  const s = r.summary;
  if (r.kind === "probability" && s.brier_covered !== null && s.brier_covered !== undefined && s.brier_baseline_covered != null) {
    const better = s.brier_covered < s.brier_baseline_covered;
    return (
      <p className="text-xs">
        Pooled Brier score <span className="num">{s.brier_covered.toFixed(3)}</span> vs{" "}
        <span className="num">{s.brier_baseline_covered.toFixed(3)}</span> for the training average:{" "}
        <span className={better ? "" : "font-semibold text-warn"}>{better ? "better" : "worse"}</span> (lower is better).
      </p>
    );
  }
  if (s.tests_inside_band_covered) {
    const under = (s.tests_inside_band_covered.rate ?? 1) < 0.9;
    return (
      <p className="text-xs">
        Single diameters inside their own band: <Rate r={s.tests_inside_band_covered} />
        {under ? <span className="font-semibold text-warn"> under the nominal 90%</span> : null}.
      </p>
    );
  }
  return null;
}

function MetricCard({ r, wide }: { r: HoldoutResult; wide?: HoldoutResult }) {
  const s = r.summary;
  return (
    <li className="rounded-lg border border-line bg-surface p-3" data-testid={`score-${r.metric}`}>
      <h3 className="text-sm font-semibold">
        <span className="num">{r.metric}</span> · {r.label}{" "}
        <span className="num text-xs font-normal text-muted">({r.investigation_id}, {s.n_tests} tests in {s.n_groups} groups)</span>
        {s.weak_test ? <WeakBadge /> : null}
      </h3>
      <p className="mt-1 text-sm">
        Band held (overlap rule): <Rate r={s.band_coverage} testid={`coverage-${r.metric}`} />
      </p>
      {r.kind === "probability" ? (
        <p className="text-sm">
          Strict rule (observed share inside the band): <Rate r={s.strict_coverage} testid={`strict-${r.metric}`} />
        </p>
      ) : null}
      <Pooled r={r} />
      {wide ? (
        <div className="mt-2 border-t border-line pt-2 text-xs" data-testid={`wide-${r.metric}`}>
          <p className="font-medium">
            Wide check{wide.summary.weak_test ? <WeakBadge /> : null}
          </p>
          <p>
            <span className="num">{wide.summary.n_covered}</span> covered, <span className="num">{wide.summary.n_not_covered}</span>{" "}
            no evidence, <span className="num">{wide.summary.n_skipped}</span> skipped
            {skipReasons(wide).map((x) => (
              <span key={x.reason} data-testid={`skip-reason-${r.metric}`}>
                {" "}
                (<span className="num">{x.n}</span>: {x.reason})
              </span>
            ))}
            . Band held: <Rate r={wide.summary.band_coverage} />.
          </p>
          <Pooled r={wide} />
        </div>
      ) : null}
    </li>
  );
}

function Scorecard({ d }: { d: HoldoutArtifact }) {
  const ov = d.overall;
  const wide = d.wide_check;
  const nej = wide?.overall.no_evidence_justified;
  const sf = d.saffire_hindcast;
  const constant = sf?.scores?.baseline_always_more_at_1g_capped;
  return (
    <section className="space-y-3" aria-labelledby="score-h">
      <h2 id="score-h" className="text-lg font-semibold">
        Scorecard
      </h2>
      <div className="grid gap-3 lg:grid-cols-3">
        <div className="rounded-lg border border-line bg-surface p-3" data-testid="score-overall">
          <h3 className="text-sm font-semibold">Do the bands hold? (one tested atmosphere hidden at a time)</h3>
          <p className="mt-1 text-sm">
            Band held for <Rate r={ov.band_coverage} testid="coverage-overall" /> held-out groups. Target:{" "}
            <span className="num">{fmtPct(ov.target_coverage)}</span>.
            {ov.weak_test ? <WeakBadge /> : null}
          </p>
          <p className="mt-1 text-xs text-muted">
            This headline uses a lenient rule that flatters groups of 1 to 3 tests. Read it with the strict rate and the
            pooled checks under each metric.
          </p>
        </div>
        <div className="rounded-lg border border-line bg-surface p-3" data-testid="score-gate">
          <h3 className="text-sm font-semibold">Is &ldquo;no evidence&rdquo; the right call? (wide check)</h3>
          {wide && nej ? (
            <>
              <p className="mt-1 text-sm">
                <span className="num font-semibold">{nej.n}</span> groups got &ldquo;no evidence&rdquo; when a whole O₂ band of
                tests was hidden. For <span className="num font-semibold">{nej.k}</span> of them the band, had it been shown,
                would have missed.
              </p>
              <p className="mt-1 text-xs" data-testid="wide-what">{wide.what}</p>
              <p className="mt-1 text-xs text-muted">
                So the gate was cautious rather than wrong here. The one-at-a-time test cannot check this: it gave
                &ldquo;no evidence&rdquo; for <span className="num">{ov.n_not_covered}</span> of{" "}
                <span className="num">{ov.n_groups}</span> groups, because every hidden group still had a tested neighbour.
              </p>
            </>
          ) : (
            <p className="mt-1 text-sm text-muted">The wide check is not in this artifact.</p>
          )}
        </div>
        <div className="rounded-lg border border-line bg-surface p-3" data-testid="score-saffire">
          <h3 className="text-sm font-semibold">Across investigations: SAFFIRE-II hindcast (M4)</h3>
          {sf?.available && sf.headline ? (
            <>
              <p className="mt-1 text-sm">
                <span className="num font-semibold">
                  {sf.headline.hits} of {sf.headline.n}
                </span>{" "}
                samples called right
                {constant ? (
                  <>
                    ; the constant rule &ldquo;1 g always burns more&rdquo; also gets{" "}
                    <span className="num">
                      {constant.hits} of {constant.n}
                    </span>
                  </>
                ) : null}
                .
              </p>
              <p className="mt-1 text-xs font-medium text-warn" data-testid="saffire-caveat">
                {sf.caveat}
              </p>
            </>
          ) : (
            <p className="mt-1 text-sm text-muted">The SAFFIRE hindcast is not available in this build.</p>
          )}
        </div>
      </div>
      <ul className="grid gap-3 lg:grid-cols-3" aria-label="Results per metric">
        {HOLDOUT_METRICS.filter((m) => d.metrics[m]).map((m) => (
          <MetricCard key={m} r={d.metrics[m]} wide={wide?.metrics[m]} />
        ))}
      </ul>
    </section>
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

function MapSection({ d }: { d: HoldoutArtifact }) {
  const [metricRaw, setMetric] = useQueryParam("metric", "M1");
  const [schemeRaw, setScheme] = useQueryParam("scheme", "atmosphere");
  const metric = d.metrics[metricRaw] ? metricRaw : "M1";
  const scheme: Scheme = schemeRaw === "wide" && d.wide_check ? "wide" : "atmosphere";
  const res = scheme === "wide" ? d.wide_check?.metrics[metric] : d.metrics[metric];
  if (!res) return null;
  const points = mapPoints(res);
  const c = markCounts(points);
  const schemeText = scheme === "wide" ? "a whole O₂ band of tests hidden at once" : "one tested atmosphere hidden at a time";
  const aria = `Held-out ${metric} groups, ${schemeText}, on oxygen and cabin pressure: ${c.hit} band held (filled circles), ${c.miss} band missed (hollow circles with a cross), ${c.noEvidence} no evidence (grey squares), ${c.skipped} skipped (grey dashed rings).`;
  return (
    <section className="rounded-lg border border-line bg-surface p-4" aria-labelledby="map-h">
      <h2 id="map-h" className="text-lg font-semibold">
        Where the held-out tests were
      </h2>
      <div className="mt-2 flex flex-wrap gap-4">
        <div role="group" aria-label="Metric" className="flex flex-wrap gap-2">
          {HOLDOUT_METRICS.filter((m) => d.metrics[m]).map((m) => (
            <Toggle key={m} pressed={m === metric} onClick={() => setMetric(m)}>
              {m}
            </Toggle>
          ))}
        </div>
        <div role="group" aria-label="Test" className="flex flex-wrap gap-2">
          <Toggle pressed={scheme === "atmosphere"} onClick={() => setScheme(null)}>
            One atmosphere at a time
          </Toggle>
          {d.wide_check ? (
            <Toggle pressed={scheme === "wide"} onClick={() => setScheme("wide")}>
              Wide check
            </Toggle>
          ) : null}
        </div>
      </div>
      <p className="mt-2 text-xs text-muted">
        {res.label}, {schemeText}. Groups with the same O₂ and pressure but different CO₂ or helium sit on top of each
        other; misses are drawn on top. The misses table below lists every miss.
      </p>
      <div className="mt-2">
        <HoldoutMap points={points} ariaLabel={aria} />
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs" aria-label="Map legend" data-testid="map-legend">
        {(
          [
            ["hit", undefined, `band held (${c.hit})`],
            ["miss", undefined, `band missed (${c.miss})`],
            ["grey", "no_evidence", `no evidence, no band shown (${c.noEvidence})`],
            ["grey", "skipped", `skipped (${c.skipped})`],
          ] as const
        ).map(([mark, grey, text]) => (
          <li key={text} className="flex items-center gap-1">
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <HoldoutMarker p={{ mark, greyReason: grey }} cx={8} cy={8} r={5} />
            </svg>
            <span className="num">{text}</span>
          </li>
        ))}
      </ul>
      {c.skipped ? (
        <p className="mt-1 text-xs" data-testid="map-skipped">
          Skipped:{" "}
          {skipReasons(res)
            .map((x) => `${x.n} group${x.n === 1 ? "" : "s"}: ${x.reason}`)
            .join("; ")}
          .
        </p>
      ) : null}
    </section>
  );
}

function MissesTable({ d }: { d: HoldoutArtifact }) {
  const [schemeRaw] = useQueryParam("scheme", "atmosphere");
  const wide = schemeRaw === "wide" && d.wide_check;
  const source = wide ? d.wide_check!.metrics : d.metrics;
  const rows = HOLDOUT_METRICS.filter((m) => source[m]).flatMap((m) => worstMissRows(source[m]).map((x) => ({ ...x, r: source[m] })));
  return (
    <section className="rounded-lg border border-line bg-surface p-4" aria-labelledby="miss-h">
      <h2 id="miss-h" className="text-lg font-semibold">
        Worst misses ({wide ? "wide check" : "one atmosphere at a time"})
      </h2>
      <p className="mt-1 text-xs text-muted">
        Up to five per metric, largest gap between the band and the observed result first. Each row names the PSI test rows
        that were hidden.
      </p>
      {rows.length ? (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-xs" data-testid="misses-table">
            <caption className="sr-only">Held-out groups whose band missed the observed result</caption>
            <thead className="text-muted">
              <tr>
                <th scope="col" className="py-1 pr-2">Metric</th>
                <th scope="col" className="py-1 pr-2">Hidden atmosphere</th>
                <th scope="col" className="py-1 pr-2">Tests</th>
                <th scope="col" className="py-1 pr-2">Band shown</th>
                <th scope="col" className="py-1 pr-2">Observed</th>
                <th scope="col" className="py-1 pr-2">Gap</th>
                <th scope="col" className="py-1">PSI rows</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ miss, group, r }) => (
                <tr key={`${r.metric}-${miss.id}`} className="border-t border-line align-top" data-testid="miss-row">
                  <th scope="row" className="num py-1 pr-2 font-normal">{r.metric}</th>
                  <td className="py-1 pr-2">{atmText(miss.atmosphere)}</td>
                  <td className="num py-1 pr-2">{miss.n_tests}</td>
                  <td className="num py-1 pr-2">{bandText(r.kind, miss.band90)}</td>
                  <td className="num py-1 pr-2">{observedText(miss.observed)}</td>
                  <td className="num py-1 pr-2">{r.kind === "probability" ? (miss.gap < 0.005 ? "under 1%" : fmtPct(miss.gap)) : `${miss.gap.toFixed(2)} mm`}</td>
                  <td className="num py-1 break-words" data-testid="psi-rows">
                    {(group?.psi_rows ?? []).map((p) => (
                      <span key={p.record_id} className="block" title={`${p.source_file}, row ${p.source_row}`}>
                        {p.record_id}
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-2 text-sm text-muted">No misses in this test.</p>
      )}
    </section>
  );
}

function HowToRead({ d }: { d: HoldoutArtifact }) {
  return (
    <CaveatBanner title="How to read this">
      <p>
        <strong>Band held</strong> means the result the hidden tests really showed fits the 90% band the app gave without
        them. A good band holds about 90% of the time: much less means it is too narrow, much more on its own proves little.
      </p>
      <p>
        <strong>Groups are small.</strong> Most hidden atmospheres had 1 to 3 tests, so each rate carries a 90% interval and
        the headline rule is lenient. Where fewer than {d.settings.weak_below_groups ?? 10} groups could be scored the page
        says <strong>weak test</strong>.
      </p>
      <p>
        <strong>The rules in words:</strong>
      </p>
      <ul className="list-disc pl-5" data-testid="hit-rules">
        {HOLDOUT_METRICS.filter((m) => d.metrics[m]).map((m) => (
          <li key={m}>
            <span className="num">{m}</span>: {d.metrics[m].hit_rule}
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted">
        Nothing on this page changed the engine: bands and the honesty gate stay as they are, and any change needs its own
        decision record ({d.adr}). {d.method}
      </p>
    </CaveatBanner>
  );
}

function Trust({ d }: { d: HoldoutArtifact }) {
  return (
    <div className="space-y-4">
      <HowToRead d={d} />
      <Scorecard d={d} />
      <MapSection d={d} />
      <MissesTable d={d} />
      <p className="num text-[11px] text-muted">
        {d.settings.n_boot ? `${d.settings.n_boot} bootstrap refits per hidden group` : null}
        {d.settings.interval ? ` · intervals: ${d.settings.interval}` : null}
        {d.generated_at ? ` · generated ${d.generated_at}` : null}
      </p>
    </div>
  );
}
