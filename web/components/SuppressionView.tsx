"use client";

import { api } from "@/lib/api";
import { fmtSig } from "@/lib/format";
import { matchPreset, type Habitat } from "@/lib/habitat";
import {
  DEFAULT_SAFETY_NOTE,
  DILUENT_IDS,
  DILUENT_SHORT,
  DOSE_NOT_REACHED,
  STATIC_DILUENTS,
  binMid,
  doseLabel,
  fmtPct,
  isDrawable,
  parseDiluent,
  referenceFor,
  summaryLine,
  testedO2Range,
} from "@/lib/suppression";
import type { DiluentId, SuppressionCurve, SuppressionMetricPoint, SuppressionReferenceBin } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";
import { useHabitat } from "@/lib/useHabitat";
import { useQueryParam } from "@/lib/useQueryParam";
import { useAsk } from "./AskDrawer";
import { CaveatBanner } from "./CaveatBanner";
import { SuppressionCurveChart } from "./charts/SuppressionCurveChart";
import { TestedDilutionChart } from "./charts/TestedDilutionChart";
import { ErrorState, Loading, SourceChip } from "./ui/States";

const LABEL: Record<DiluentId, string> = { co2: "CO₂", he: "Helium" };

export function SuppressionView() {
  const { habitat, queryString } = useHabitat();
  const [raw, setDiluent] = useQueryParam("diluent", "co2");
  const diluent = parseDiluent(raw);
  const curve = useAsync(() => api.suppression(habitat, diluent), `${queryString}|${diluent}`);
  const reference = useAsync(() => api.suppressionReference(), "suppression-reference");
  const safety = curve.status === "ok" ? (curve.data.data.safety_note ?? DEFAULT_SAFETY_NOTE) : DEFAULT_SAFETY_NOTE;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="doc-label">R2 · Suppression calculator</p>
          <h1 className="page-title">Put it out: how dilution affects flames</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Adding carbon dioxide or helium to the air makes it harder for a flame to keep burning. This page shows what
            NASA&apos;s FLEX droplet-flame tests on the ISS say about that for your habitat, and where they say nothing at all.
          </p>
        </div>
        {curve.status === "ok" ? <SourceChip source={curve.data.source} note={curve.data.note} /> : null}
      </header>

      <CaveatBanner tone="warn" title="Safety note">
        <p data-testid="safety-note">{safety}</p>
      </CaveatBanner>

      <fieldset>
        <legend className="mb-1 text-xs font-medium text-muted">Diluent (replaces nitrogen; oxygen and pressure stay at the habitat&apos;s)</legend>
        <div className="flex flex-wrap gap-2">
          {DILUENT_IDS.map((d) => (
            <button
              key={d}
              type="button"
              aria-pressed={d === diluent}
              onClick={() => setDiluent(d)}
              className={`rounded-md border px-3 py-1.5 text-sm ${
                d === diluent ? "border-partial bg-surface-2 text-fg" : "border-line text-muted hover:text-fg"
              }`}
            >
              {LABEL[d]}
              <span className="sr-only"> ({STATIC_DILUENTS[d].label}, up to {fmtPct(STATIC_DILUENTS[d].max)})</span>
            </button>
          ))}
        </div>
      </fieldset>

      {curve.status === "loading" ? <Loading label="Computing the suppression curve…" /> : null}
      {curve.status === "error" ? <ErrorState error={curve.error} onRetry={curve.reload} /> : null}
      {curve.status === "ok" ? (
        <CurveView
          c={curve.data.data}
          habitat={habitat}
          reference={reference.status === "ok" ? reference.data.data.bins : null}
          referenceError={reference.status === "error" ? reference.error.message : null}
        />
      ) : null}
    </div>
  );
}

function statusText(m: SuppressionMetricPoint): string {
  if (isDrawable(m)) return "inside tested conditions";
  return `no evidence${m.reason ? `: ${m.reason}` : ""}`;
}

function fmtProb(v: number | null): string {
  return v === null ? "–" : `${Math.round(v * 100)}%`;
}

function fmtMm(v: number | null): string {
  return v === null ? "–" : `${fmtSig(v, 3)} mm`;
}

function CurveView({
  c,
  habitat,
  reference,
  referenceError,
}: {
  c: SuppressionCurve;
  habitat: Habitat;
  reference: SuppressionReferenceBin[] | null;
  referenceError: string | null;
}) {
  const { open } = useAsk();
  const preset = matchPreset(habitat);
  const habitatLabel = preset ? (preset.id === "iss" ? "ISS air" : preset.label.toLowerCase()) : "your habitat";
  const chartLabel = preset?.label ?? "Your habitat";
  const name = DILUENT_SHORT[c.diluent];
  const xMax = Math.max(STATIC_DILUENTS[c.diluent].max, ...c.points.map((p) => p.fraction));
  const range = testedO2Range(c);
  const refBins = referenceFor(reference ? { bins: reference } : null, c.diluent, habitat.o2, range);
  const dose = c.dose_for_p90;
  const label = doseLabel(dose, c.diluent);
  const summary = summaryLine(c, habitatLabel, habitat.o2);
  const diluted = c.points.filter((p) => p.fraction > 0);
  const noEvidence = diluted.length > 0 && diluted.every((p) => !isDrawable(p.M1));
  const question =
    preset?.id === "lunar_base" || (noEvidence && preset)
      ? `Why can't Gravity Gap answer suppression for the ${preset.label.toLowerCase()}?`
      : `How much ${name} would it take to put out a flame in ${preset?.id === "iss" ? "ISS air" : habitatLabel}?`;

  return (
    <div className="space-y-4">
      <section className="panel" aria-labelledby="supp-summary-h">
        <h2 id="supp-summary-h" className="sr-only">
          Summary
        </h2>
        <p className="text-base" data-testid="suppression-summary">
          {summary}
        </p>
        <p className="mt-2 text-sm">
          Dose for 90%:{" "}
          <span className="num font-medium text-partial" data-testid="suppression-dose">
            {dose ? label : DOSE_NOT_REACHED}
          </span>
        </p>
        {dose?.note ? <p className="mt-1 text-xs text-muted">{dose.note}</p> : null}
        {noEvidence && range ? (
          <p className="mt-2 text-sm" data-testid="o2-ceiling">
            Every FLEX test with {name} added had between <span className="num">{fmtPct(range[0])}</span> and{" "}
            <span className="num">{fmtPct(range[1])}</span> oxygen. This habitat has <span className="num">{fmtPct(habitat.o2)}</span>, above the{" "}
            <span className="num">{fmtPct(range[1])}</span> O₂ ceiling of the dilution tests, so no diluted point gets a number.
          </p>
        ) : null}
        {c.gate_note ? <p className="mt-2 text-xs text-muted">{c.gate_note}</p> : null}
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => open({ question, contextIds: ["M1", "M2", "PSI-69"] })}
            className="rounded-md border border-line px-3 py-1.5 text-sm text-muted hover:text-fg"
          >
            Ask about this
          </button>
          <span className="text-xs text-muted">
            Asks: <q>{question}</q>
          </span>
        </div>
      </section>

      <section className="panel" aria-labelledby="m1-h">
        <h2 id="m1-h" className="text-base font-medium">
          Chance the flame goes out on its own before burning out <span className="num text-xs text-muted">(M1)</span>
        </h2>
        <p className="mb-2 text-xs text-muted">
          Line = model estimate, shaded = 90% band, hatched = no evidence (no number is drawn there, and the line is never
          joined across it). Dashed vertical line = the 90% dose.
        </p>
        <SuppressionCurveChart
          testId="m1-chart"
          points={c.points}
          metric="M1"
          domain={[0, 1]}
          yLabel="chance of self-extinction"
          xLabel={`${name} added (% of the gas, replacing nitrogen)`}
          xMax={xMax}
          dose={dose ? { fraction: dose.fraction, label } : null}
          reference={refBins}
          ariaLabel={`M1 chance of self-extinction versus ${name} fraction at ${chartLabel}. ${summary} ${refBins.length ? `${refBins.length} raw FLEX reference bins shown.` : "No raw FLEX reference bins for this oxygen level."}`}
        />
        <Legend reference={refBins.length > 0} />
        <ReferenceNote bins={refBins} reference={reference} error={referenceError} name={name} />
        <details className="mt-2 text-xs">
          <summary className="cursor-pointer text-muted">Show M1 as a table</summary>
          <CurveTable c={c} metric="M1" name={name} fmt={fmtProb} />
          {refBins.length ? <ReferenceTable bins={refBins} name={name} /> : null}
        </details>
      </section>

      <section className="panel" aria-labelledby="m2-h">
        <h2 id="m2-h" className="text-base font-medium">
          Droplet size when the flame went out <span className="num text-xs text-muted">(M2, extinction diameter)</span>
        </h2>
        <p className="mb-2 text-xs text-muted">Same gap rule as above. A larger extinction diameter means the flame gave up earlier.</p>
        <SuppressionCurveChart
          testId="m2-chart"
          points={c.points}
          metric="M2"
          yLabel="extinction diameter (mm)"
          xLabel={`${name} added (% of the gas, replacing nitrogen)`}
          xMax={xMax}
          color="var(--micro)"
          fill="var(--micro-fill)"
          ariaLabel={`M2 extinction diameter versus ${name} fraction at ${chartLabel}: ${countText(c, "M2")}.`}
        />
        <details className="mt-2 text-xs">
          <summary className="cursor-pointer text-muted">Show M2 as a table</summary>
          <CurveTable c={c} metric="M2" name={name} fmt={fmtMm} />
        </details>
      </section>

      <section className="panel" aria-labelledby="tested-h">
        <h2 id="tested-h" className="text-base font-medium">
          Where dilution was tested
        </h2>
        <p className="mb-2 text-xs text-muted">
          Each dot is a group of FLEX tests with {name} added (bigger = more tests). The orange line is your habitat&apos;s
          oxygen.
        </p>
        {c.tested.length ? (
          <>
            <TestedDilutionChart
              tested={c.tested}
              habitatO2={habitat.o2}
              habitatLabel={chartLabel}
              xMax={xMax}
              diluentName={name}
              ariaLabel={`FLEX tests with ${name}: ${c.tested.reduce((s, t) => s + t.n, 0)} tests${range ? ` between ${fmtPct(range[0])} and ${fmtPct(range[1])} oxygen` : ""}. ${chartLabel} is at ${fmtPct(habitat.o2)} oxygen${range && habitat.o2 > range[1] ? ", above every diluted test" : ""}.`}
            />
            <details className="mt-2 text-xs">
              <summary className="cursor-pointer text-muted">Show tested conditions as a table</summary>
              <table className="mt-2 w-full text-left">
                <caption className="sr-only">FLEX tests with {name} added (table alternative to the chart)</caption>
                <thead className="text-muted">
                  <tr>
                    <th scope="col" className="py-1 pr-2">{name}</th>
                    <th scope="col" className="py-1 pr-2">O₂</th>
                    <th scope="col" className="py-1 pr-2">Pressure</th>
                    <th scope="col" className="py-1 pr-2">Tests</th>
                    <th scope="col" className="py-1">Extinctions</th>
                  </tr>
                </thead>
                <tbody className="num">
                  {c.tested.map((t, i) => (
                    <tr key={i} className="border-t border-line">
                      <td className="py-1 pr-2">{fmtPct(t.fraction)}</td>
                      <td className="py-1 pr-2">{fmtPct(t.o2)}</td>
                      <td className="py-1 pr-2">{Number.isFinite(t.p_atm) ? `${fmtSig(t.p_atm, 3)} atm` : "–"}</td>
                      <td className="py-1 pr-2">{t.n}</td>
                      <td className="py-1">{t.extinctions ?? "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </>
        ) : (
          <p className="text-sm text-muted">The engine reported no FLEX tests with {name} added.</p>
        )}
      </section>

      <p className="num text-[11px] text-muted">
        {c.label}
        {c.model_version ? ` · model ${c.model_version}` : ""} · {c.points.length} fractions
      </p>
    </div>
  );
}

function countText(c: SuppressionCurve, metric: "M1" | "M2"): string {
  const ok = c.points.filter((p) => isDrawable(p[metric])).length;
  return `${ok} of ${c.points.length} fractions inside tested conditions, ${c.points.length - ok} with no evidence`;
}

function Legend({ reference }: { reference: boolean }) {
  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted" aria-label="Chart legend">
      <li>
        <span aria-hidden="true" className="mr-1 inline-block h-2.5 w-4 rounded-sm bg-[var(--partial-fill)] align-middle" />
        model estimate with 90% band
      </li>
      <li>
        <span aria-hidden="true" className="hatch mr-1 inline-block h-2.5 w-4 rounded-sm border border-dashed border-nodata align-middle" />
        no evidence (gated)
      </li>
      {reference ? (
        <li>
          <span aria-hidden="true" className="mr-1 inline-block h-2.5 w-2.5 rounded-sm border-2 border-normal align-middle" />
          FLEX tests (raw): share extinguished, with interval
        </li>
      ) : null}
    </ul>
  );
}

function ReferenceNote({
  bins,
  reference,
  error,
  name,
}: {
  bins: SuppressionReferenceBin[];
  reference: SuppressionReferenceBin[] | null;
  error: string | null;
  name: string;
}) {
  if (error) return <p className="mt-1 text-[11px] text-muted">Raw FLEX reference not available: {error}</p>;
  if (!reference) return null;
  if (!bins.length) {
    return <p className="mt-1 text-[11px] text-muted">No raw FLEX {name} tests in this oxygen band, so no reference dots are drawn.</p>;
  }
  const fuels = [...new Set(bins.map((b) => b.fuel ?? "all fuels"))];
  const band = bins[0].o2_band_label;
  const wilson = bins.some((b) => b.interval_source === "wilson90");
  return (
    <p className="mt-1 text-[11px] text-muted" data-testid="reference-note">
      FLEX tests (raw), {band}: {fuels.join(", ")} ({fuels.length > 1 ? "circle, square = fuel" : "one fuel"}).
      {wilson ? " Interval: Wilson 90% from the test counts." : ""} These are counts, not model output.
    </p>
  );
}

function CurveTable({
  c,
  metric,
  name,
  fmt,
}: {
  c: SuppressionCurve;
  metric: "M1" | "M2";
  name: string;
  fmt: (v: number | null) => string;
}) {
  return (
    <table className="mt-2 w-full text-left" data-testid={`${metric.toLowerCase()}-table`}>
      <caption className="sr-only">
        {metric} versus {name} fraction (table alternative to the chart)
      </caption>
      <thead className="text-muted">
        <tr>
          <th scope="col" className="py-1 pr-2">{name}</th>
          <th scope="col" className="py-1 pr-2">Estimate</th>
          <th scope="col" className="py-1 pr-2">90% band</th>
          <th scope="col" className="py-1">Evidence</th>
        </tr>
      </thead>
      <tbody>
        {c.points.map((p) => {
          const m = p[metric];
          const ok = isDrawable(m);
          return (
            <tr key={p.fraction} className="border-t border-line" data-fraction={p.fraction} data-applicable={ok ? "true" : "false"}>
              <th scope="row" className="num py-1 pr-2 font-normal">{fmtPct(p.fraction)}</th>
              <td className="num py-1 pr-2">{ok ? fmt(m.estimate) : "–"}</td>
              <td className="num py-1 pr-2">{ok && m.band90 ? `${fmt(m.band90[0])} – ${fmt(m.band90[1])}` : "–"}</td>
              <td className="py-1">{statusText(m)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function ReferenceTable({ bins, name }: { bins: SuppressionReferenceBin[]; name: string }) {
  return (
    <table className="mt-3 w-full text-left" data-testid="reference-table">
      <caption className="mb-1 text-left font-medium text-muted">FLEX tests (raw), {bins[0].o2_band_label}</caption>
      <thead className="text-muted">
        <tr>
          <th scope="col" className="py-1 pr-2">Fuel</th>
          <th scope="col" className="py-1 pr-2">{name} bin</th>
          <th scope="col" className="py-1 pr-2">Tests</th>
          <th scope="col" className="py-1 pr-2">Extinguished</th>
          <th scope="col" className="py-1">Interval</th>
        </tr>
      </thead>
      <tbody className="num">
        {bins.map((b, i) => (
          <tr key={i} className="border-t border-line" title={b.record_ids.slice(0, 12).join(", ")}>
            <td className="py-1 pr-2">{b.fuel ?? "all"}</td>
            <td className="py-1 pr-2">
              {b.fraction[0] === b.fraction[1] ? fmtPct(b.fraction[0]) : `${fmtPct(b.fraction[0])}–${fmtPct(b.fraction[1])}`}
              <span className="sr-only"> (midpoint {fmtPct(binMid(b))})</span>
            </td>
            <td className="py-1 pr-2">{b.n}</td>
            <td className="py-1 pr-2">
              {b.extinctions ?? "–"} ({fmtProb(b.extinction_rate)})
            </td>
            <td className="py-1">{b.interval ? `${fmtProb(b.interval[0])} – ${fmtProb(b.interval[1])}` : "–"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
