"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { STATIC_METRICS } from "@/lib/api";
import { fmtBand, fmtEstimate, humanize } from "@/lib/format";
import { gFraction } from "@/lib/habitat";
import { incidentHabitat, incidentHref } from "@/lib/incidents";
import type { Regime } from "@/lib/physics";
import type { Incident, IncidentMetric } from "@/lib/types";
import { useIncidents } from "@/lib/useIncidents";
import { RegimeBadge } from "./RegimeBadge";
import { Empty, ErrorState, Loading, SourceChip } from "./ui/States";

const FIELD_LABEL: Record<string, string> = {
  g_m_s2: "gravity",
  p_psia: "pressure",
  o2: "O₂",
  u_cm_s: "vent speed",
  L_mm: "flame size",
  date: "date",
  summary: "summary",
};

const REGIMES: Regime[] = ["forced", "mixed", "buoyant"];

/** R1: real spacecraft fire events, loaded into the engine with today's PSI data. */
export function ReplayView() {
  const state = useIncidents();
  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wider text-normal">Replay</p>
          <h1 className="text-2xl font-semibold">Real fires, today&apos;s data</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Each card holds the conditions of a real spacecraft fire event, as published by NASA, and runs them through
            the same engine as every other page: the flow regime, which PSI experiments apply, and where the honesty
            gate says there is no evidence. It shows what today&apos;s data can and cannot say about these conditions.
            It does not reconstruct the events or judge the decisions made at the time.
          </p>
        </div>
        {state.status === "ok" ? <SourceChip source={state.data.source} note={state.data.note} /> : null}
      </header>

      {state.status === "loading" ? <Loading label="Loading incidents…" /> : null}
      {state.status === "error" ? <ErrorState error={state.error} onRetry={state.reload} /> : null}
      {state.status === "ok" ? (
        state.data.data.incidents.length === 0 ? (
          <Empty>No incidents are available yet.</Empty>
        ) : (
          <ul className="grid gap-4 lg:grid-cols-2" aria-label="Incidents">
            {state.data.data.incidents.map((inc) => (
              <li key={inc.id}>
                <IncidentCard inc={inc} />
              </li>
            ))}
          </ul>
        )
      ) : null}
    </div>
  );
}

function AssumedTag() {
  return (
    <span className="ml-1 rounded border border-dashed border-partial px-1 text-[10px] uppercase tracking-wide text-partial">
      assumed
    </span>
  );
}

function IncidentCard({ inc }: { inc: Incident }) {
  const router = useRouter();
  const habitat = incidentHabitat(inc);
  const boundsHref = incidentHref(inc, "/bounds");
  const regimeHref = incidentHref(inc, "/regime");
  const headingId = `incident-${inc.id}`;
  const assumed = new Set(inc.assumed);
  // The scope note is shown on its own; do not repeat it in the findings list.
  const findings = (inc.findings ?? []).filter((f) => f !== inc.scope_note);
  const regime = typeof inc.physics?.regime === "string" && REGIMES.includes(inc.physics.regime as Regime)
    ? (inc.physics.regime as Regime)
    : null;

  return (
    <article
      aria-labelledby={headingId}
      data-testid={`incident-${inc.id}`}
      className={`flex h-full flex-col gap-3 rounded-lg border bg-surface p-4 ${inc.in_scope ? "border-line" : "hatch border-dashed border-line"}`}
    >
      <header>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id={headingId} className="text-lg font-semibold">
            {inc.name}
          </h2>
          <time dateTime={inc.date} className="num text-xs text-muted">
            {inc.date}
          </time>
        </div>
        <p className="text-xs text-muted">{inc.phase}</p>
        {!inc.in_scope ? (
          <p className="mt-2">
            <span className="rounded-full border border-warn px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-warn">
              Outside scope
            </span>
          </p>
        ) : null}
      </header>

      <p className="text-sm">{inc.summary}</p>
      {!inc.in_scope && inc.scope_note ? (
        <p className="rounded-md border border-dashed border-line px-3 py-2 text-sm" data-testid="scope-note">
          {inc.scope_note}
        </p>
      ) : null}

      {habitat ? (
        <section aria-label={`${inc.name} conditions`}>
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted">Conditions</h3>
          <dl className="num mt-1 grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 text-sm">
            <dt className="font-sans text-xs text-muted">Gravity</dt>
            <dd>
              {gFraction(habitat.g_m_s2).toFixed(2)} g{" "}
              <span className="text-xs text-muted">({habitat.g_m_s2} m/s²)</span>
              {assumed.has("g_m_s2") ? <AssumedTag /> : null}
            </dd>
            <dt className="font-sans text-xs text-muted">Pressure</dt>
            <dd>
              {habitat.p_psia} psia{assumed.has("p_psia") ? <AssumedTag /> : null}
            </dd>
            <dt className="font-sans text-xs text-muted">O₂</dt>
            <dd>
              {Number((habitat.o2 * 100).toFixed(1))}%{assumed.has("o2") ? <AssumedTag /> : null}
            </dd>
            <dt className="font-sans text-xs text-muted">Vent speed</dt>
            <dd>
              {habitat.u_cm_s} cm/s{assumed.has("u_cm_s") ? <AssumedTag /> : null}
            </dd>
            <dt className="font-sans text-xs text-muted">Flame size</dt>
            <dd>
              {habitat.L_mm} mm{assumed.has("L_mm") ? <AssumedTag /> : null}
            </dd>
          </dl>
          {inc.assumed_note ? (
            <p className="mt-2 text-xs" data-testid="assumed-note">
              <span className="font-medium">Assumptions:</span> {inc.assumed_note}
            </p>
          ) : null}
        </section>
      ) : null}

      {regime ? (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          Flow regime: <RegimeBadge regime={regime} />
        </div>
      ) : null}

      {findings.length > 0 ? (
        <section aria-label={`What the engine says about ${inc.name}`}>
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted">What today&apos;s data says</h3>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
            {findings.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {inc.metrics ? <MetricStrip inc={inc} metrics={inc.metrics} /> : null}

      {inc.sources.length > 0 ? (
        <section aria-label={`Sources for ${inc.name}`}>
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted">Sources</h3>
          <ul className="mt-1 space-y-2 text-xs">
            {inc.sources.map((s, i) => (
              <li key={i}>
                <span className="text-muted">{FIELD_LABEL[s.field] ?? humanize(s.field)}: </span>
                {s.url ? (
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="break-all text-micro underline">
                    {s.url.replace(/^https?:\/\//, "")}
                  </a>
                ) : (
                  <cite className="not-italic">{s.source ?? "Unlinked source"}</cite>
                )}
                {s.quote ? <blockquote className="mt-0.5 border-l-2 border-line pl-2 italic">“{s.quote}”</blockquote> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {boundsHref && regimeHref ? (
        <div className="mt-auto flex flex-wrap items-center gap-3 pt-1">
          <button
            type="button"
            onClick={() => router.push(boundsHref)}
            className="rounded-md border border-micro px-3 py-1.5 text-sm text-micro hover:bg-surface-2"
          >
            Load this habitat<span className="sr-only">: {inc.name}</span>
          </button>
          <Link href={regimeHref} className="text-sm text-muted underline hover:text-fg">
            See its flow regime<span className="sr-only"> for {inc.name}</span>
          </Link>
        </div>
      ) : null}
    </article>
  );
}

function MetricStrip({ inc, metrics }: { inc: Incident; metrics: Record<string, IncidentMetric> }) {
  return (
    <section aria-label={`${inc.name} metrics M1 to M5`}>
      <h3 className="text-xs font-medium uppercase tracking-wider text-muted">Metrics M1–M5</h3>
      <ul className="mt-1 grid grid-cols-1 gap-1 sm:grid-cols-5" data-testid="metric-strip">
        {STATIC_METRICS.map((info) => {
          const m = metrics[info.id];
          const ok = m?.applicable === true;
          return (
            <li
              key={info.id}
              title={ok ? info.label : (m?.reason ?? "No result for this metric.")}
              className={`rounded border px-2 py-1 text-xs ${ok ? "border-line" : "hatch border-dashed border-line"}`}
              data-testid={`metric-${info.id}`}
            >
              <span className="num font-semibold">{info.id}</span>{" "}
              {ok && m ? (
                <>
                  <span className="num">{fmtEstimate(m.estimate, info.kind, info.unit)}</span>
                  {m.band90 ? (
                    <span className="num block text-[11px] text-muted">
                      90%: {fmtBand(m.band90 as readonly (number | string)[], info.kind, info.unit)}
                    </span>
                  ) : null}
                </>
              ) : (
                <span className="block text-[11px] font-medium">no evidence</span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
