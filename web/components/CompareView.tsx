"use client";

import { api } from "@/lib/api";
import {
  CURRENT_LABEL,
  DEFAULT_A,
  DEFAULT_B,
  REGIME_WORDS,
  compareQuery,
  compareQuestion,
  fmtValue,
  parseSide,
  resolveSide,
  sharedDomain,
  type CompareResult,
  type CompareSide,
  type MetricCompare,
  type Regime,
  type SideKey,
} from "@/lib/compare";
import { fmtBand, fmtEstimate } from "@/lib/format";
import { G0 } from "@/lib/physics";
import { PRESETS } from "@/lib/presets";
import { useAsync } from "@/lib/useAsync";
import { useHabitat } from "@/lib/useHabitat";
import { useQueryParam } from "@/lib/useQueryParam";
import { useAsk } from "./AskDrawer";
import { BandChart, type BandPoint } from "./charts/BandChart";
import { ErrorState, Loading, SourceChip } from "./ui/States";

const REGIME_STYLE: Record<Regime, string> = {
  forced: "border-micro text-micro",
  mixed: "border-partial text-partial",
  buoyant: "border-normal text-normal",
};

function isNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function numBand(b: CompareSide["band90"]): [number, number] | null {
  return b && isNum(b[0]) && isNum(b[1]) ? [b[0], b[1]] : null;
}

/** Side picker: the six presets plus the habitat currently in the habitat bar (URL). */
function SidePicker({ id, label, value, onChange, currentLabel }: {
  id: string;
  label: string;
  value: SideKey;
  onChange: (v: SideKey) => void;
  currentLabel: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-muted">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(parseSide(e.target.value, value))}
        className="rounded-md border border-line bg-surface-2 px-2 py-1.5 text-sm text-fg"
      >
        <option value="current">Current habitat ({currentLabel})</option>
        {PRESETS.map((p) => (
          <option key={p.id} value={p.id}>
            {p.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export function CompareView() {
  const { habitat, queryString } = useHabitat();
  const [aRaw, setA] = useQueryParam("a", DEFAULT_A);
  const [bRaw, setB] = useQueryParam("b", DEFAULT_B);
  const aKey = parseSide(aRaw, DEFAULT_A);
  const bKey = parseSide(bRaw, DEFAULT_B);
  const a = resolveSide(aKey, habitat);
  const b = resolveSide(bKey, habitat);
  const currentLabel = resolveSide("current", habitat).label;
  const key = `${aKey}|${bKey}|${a.presetId ?? JSON.stringify(a.habitat)}|${b.presetId ?? JSON.stringify(b.habitat)}`;
  const res = useAsync(() => api.compare(a, b), key);
  const { open } = useAsk();

  const swap = () => {
    const q = new URLSearchParams(compareQuery(bKey, aKey, queryString));
    window.history.replaceState(null, "", `/compare?${q.toString()}`);
  };

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="doc-label">S4 · Compare</p>
          <h1 className="page-title">Compare two habitats side by side</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Each row puts both habitats on one axis, so the estimates and the widths of their 90% bands can be compared
            by eye. When one side has no evidence, no difference is shown.
          </p>
        </div>
        {res.status === "ok" ? <SourceChip source={res.data.source} note={res.data.note} /> : null}
      </header>

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-line bg-surface p-3" role="group" aria-label="Habitats to compare">
        <SidePicker id="compare-a" label="Habitat A" value={aKey} onChange={setA} currentLabel={currentLabel} />
        <button
          type="button"
          onClick={swap}
          className="rounded-md border border-line px-3 py-1.5 text-sm text-muted hover:text-fg"
        >
          Swap A and B
        </button>
        <SidePicker id="compare-b" label="Habitat B" value={bKey} onChange={setB} currentLabel={currentLabel} />
        {a.presetId && b.presetId && a.presetId !== b.presetId ? (
          <button
            type="button"
            onClick={() => open({ question: compareQuestion(a.presetId!, b.presetId!), contextIds: [] })}
            className="ml-auto rounded-md border border-partial px-3 py-1.5 text-sm text-partial hover:bg-surface-2"
          >
            Ask about this comparison
          </button>
        ) : null}
      </div>
      {a.key === "current" || b.key === "current" ? (
        <p className="text-xs text-muted">
          &ldquo;Current habitat&rdquo; is the habitat in the bar above
          {currentLabel === CURRENT_LABEL ? " (custom values)" : ` (${currentLabel})`}. Change it there and this page follows.
        </p>
      ) : null}

      {res.status === "loading" ? <Loading label="Computing both habitats…" /> : null}
      {res.status === "error" ? <ErrorState error={res.error} onRetry={res.reload} /> : null}
      {res.status === "ok" ? <CompareBody r={res.data.data} /> : null}
    </div>
  );
}

function CompareBody({ r }: { r: CompareResult }) {
  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-line bg-surface p-4" aria-labelledby="what-changed-h">
        <h2 id="what-changed-h" className="text-sm font-semibold">
          What changes
        </h2>
        <p className="mt-1 text-sm" data-testid="compare-summary">
          {r.summary}
        </p>
      </section>
      {r.metrics.map((m) => (
        <MetricRow key={m.metric} m={m} labelA={r.a.label} labelB={r.b.label} gA={r.a.g_m_s2} gB={r.b.g_m_s2} />
      ))}
    </div>
  );
}

function SideCard({ name, side, m, testId, tone }: { name: string; side: CompareSide; m: MetricCompare; testId: string; tone: string }) {
  return (
    <div data-testid={testId} data-applicable={side.applicable ? "true" : "false"} className={`rounded-sm border border-l-[3px] bg-surface p-3 ${tone}`}>
      <p className="text-xs font-medium">{name}</p>
      {side.applicable ? (
        <>
          <p className="mt-1 text-lg font-semibold text-fg">
            <span className="num">{fmtEstimate(side.estimate, m.kind, m.unit)}</span>
          </p>
          <p className="text-xs text-muted">
            90% band <span className="num text-fg">{fmtBand(side.band90, m.kind, m.unit)}</span>
          </p>
        </>
      ) : (
        <p className="mt-1 text-sm font-semibold text-fg">No evidence</p>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
        <span
          className={`rounded-sm border px-2 py-0.5 ${side.applicable ? "border-micro text-micro" : "hatch border-dashed border-line text-fg"}`}
        >
          {side.applicable ? "covered by tests" : "no evidence"}
        </span>
        {side.regime ? (
          <span className={`rounded-sm border px-2 py-0.5 ${REGIME_STYLE[side.regime]}`}>regime: {REGIME_WORDS[side.regime]}</span>
        ) : null}
        {side.applicable && side.transfer ? (
          <span className="rounded-sm border border-line px-2 py-0.5 text-muted">transfer confidence: {side.transfer.confidence}</span>
        ) : null}
      </div>
      {!side.applicable && side.reason ? <p className="mt-2 text-xs text-muted">{side.reason}</p> : null}
    </div>
  );
}

function diffLine(m: MetricCompare, labelB: string): string {
  const d = m.diff;
  const parts: string[] = [];
  if (d.estimate && d.estimate.a !== null && d.estimate.b !== null) {
    const va = fmtValue(m.kind, m.unit, d.estimate.a);
    const vb = fmtValue(m.kind, m.unit, d.estimate.b);
    parts.push(
      d.estimate.direction === "same"
        ? `Same estimate on both sides (${va}).`
        : d.estimate.direction === "changed"
          ? `Changes from ${va} to ${vb}.`
          : `${d.estimate.direction === "higher" ? "Higher" : "Lower"} at ${labelB}: ${va} → ${vb}.`,
    );
    if (d.band_width && d.band_width.direction !== "same") parts.push(`The 90% band is ${d.band_width.direction} at ${labelB}.`);
  } else if (d.estimate_note) {
    parts.push(d.estimate_note);
  }
  if (d.regime.changed && d.regime.a && d.regime.b) parts.push(`Regime: ${REGIME_WORDS[d.regime.a]} → ${REGIME_WORDS[d.regime.b]}.`);
  return parts.join(" ");
}

function MetricRow({ m, labelA, labelB, gA, gB }: { m: MetricCompare; labelA: string; labelB: string; gA: number; gB: number }) {
  const isCategory = m.kind === "category" || typeof m.a.estimate === "string" || typeof m.b.estimate === "string";
  const headingId = `cmp-${m.metric}-h`;
  const point = (key: string, label: string, g: number, s: CompareSide, color: string, fill: string): BandPoint => ({
    key,
    label,
    sublabel: `${(g / G0).toFixed(3)} g`,
    estimate: s.applicable && isNum(s.estimate) ? s.estimate : null,
    band: s.applicable ? numBand(s.band90) : null,
    color,
    fill,
    emptyLabel: "no evidence",
    trace: s.applicable
      ? `${label}: estimate ${fmtEstimate(s.estimate, m.kind, m.unit)}, 90% band ${fmtBand(s.band90, m.kind, m.unit)}`
      : `${label}: no evidence`,
  });
  const points = [
    point("a", labelA, gA, m.a, "var(--micro)", "var(--micro-fill)"),
    point("b", labelB, gB, m.b, "var(--partial)", "var(--partial-fill)"),
  ];
  const prob = m.kind === "probability" || m.unit === "fraction";
  return (
    <section className="rounded-lg border border-line bg-surface p-4" aria-labelledby={headingId} data-testid={`compare-row-${m.metric}`}>
      <h2 id={headingId} className="text-base font-semibold">
        <span className="num">{m.metric}</span> · {m.label}
      </h2>
      <p className="mt-1 text-sm" data-testid={`compare-diff-${m.metric}`}>
        {diffLine(m, labelB)}
      </p>
      <div className={`mt-3 grid gap-4 ${isCategory ? "" : "lg:grid-cols-[3fr_2fr]"}`}>
        {isCategory ? null : (
          <BandChart
            points={points}
            unit={prob ? "probability" : m.unit}
            domain={sharedDomain(m)}
            ariaLabel={`${m.metric} on one shared axis: ${points.map((p) => p.trace).join("; ")}.`}
          />
        )}
        <div className={`grid gap-3 sm:grid-cols-2 ${isCategory ? "" : "lg:grid-cols-1"}`}>
          <SideCard name={`A · ${labelA}`} side={m.a} m={m} testId={`side-a-${m.metric}`} tone="border-micro" />
          <SideCard name={`B · ${labelB}`} side={m.b} m={m} testId={`side-b-${m.metric}`} tone="border-partial" />
        </div>
      </div>
    </section>
  );
}
