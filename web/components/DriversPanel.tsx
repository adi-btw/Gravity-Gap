"use client";

import Link from "next/link";
import { api, type Sourced } from "@/lib/api";
import { fmtBand } from "@/lib/format";
import type { Habitat } from "@/lib/habitat";
import type { BoundsResult } from "@/lib/types";
import {
  basisText,
  drawnSources,
  driversSummary,
  plannerHref,
  roundShare5,
  shareLabel,
  sourceName,
  type DriverSource,
  type DriversApplicable,
} from "@/lib/uncertainty";
import { useAsync } from "@/lib/useAsync";
import { ErrorState, Loading, SourceChip } from "./ui/States";

/** Segment fill per source: basis sets the hue, a pattern separates the engineering inputs (colour is not the only cue). */
const STYLE: Record<string, { bg: string; swatch: string }> = {
  model_uncertainty: { bg: "var(--micro)", swatch: "var(--micro)" },
  gravity_widening: { bg: "var(--partial)", swatch: "var(--partial)" },
  C_b: { bg: "repeating-linear-gradient(45deg, var(--normal) 0 4px, var(--surface) 4px 6px)", swatch: "var(--normal)" },
  dT_over_T: { bg: "repeating-linear-gradient(-45deg, var(--normal) 0 4px, var(--surface) 4px 6px)", swatch: "var(--normal)" },
  L_mm: { bg: "repeating-linear-gradient(90deg, var(--normal) 0 4px, var(--surface) 4px 6px)", swatch: "var(--normal)" },
  k: { bg: "var(--normal)", swatch: "var(--normal)" },
  remainder: { bg: "repeating-linear-gradient(45deg, var(--nodata) 0 2px, transparent 2px 5px)", swatch: "var(--nodata)" },
};

function styleFor(s: DriverSource) {
  return STYLE[s.id] ?? { bg: "var(--nodata)", swatch: "var(--nodata)" };
}

/**
 * S3 "What makes this band wide" (ADR-0008) under a covered band on /bounds: a stacked bar of the band-width shares,
 * a legend with each share's basis in words, and the biggest lever with a link to the Planner.
 */
export function DriversSection({
  r,
  bounds,
  habitat,
  queryString,
}: {
  r: BoundsResult;
  bounds: Sourced<BoundsResult>;
  habitat: Habitat;
  queryString: string;
}) {
  const state = useAsync(() => api.drivers(habitat, r.metric, bounds), `drivers|${queryString}|${r.metric}|${bounds.source}`);
  if (!r.applicable) return null;
  if (state.status === "loading") return <Loading label="Loading the band-width breakdown…" />;
  if (state.status === "error") {
    const offline = (state.error as { offline?: boolean }).offline;
    return (
      <section className="rounded-lg border border-line bg-surface p-4" aria-labelledby="drivers-h" data-testid="drivers-unavailable">
        <h2 id="drivers-h" className="mb-1 text-sm font-semibold">What makes this band wide</h2>
        {offline ? <p className="text-sm text-muted">{state.error.message}</p> : <ErrorState error={state.error} onRetry={state.reload} />}
      </section>
    );
  }
  const d = state.data.data;
  if (!d.applicable) return null; // no evidence or a rule table: no band, so no bar
  return (
    <DriversView d={d} source={state.data.source} boundsSource={bounds.source} note={state.data.note} queryString={queryString} />
  );
}

function DriversView({
  d,
  source,
  boundsSource,
  note,
  queryString,
}: {
  d: DriversApplicable;
  source: "api" | "offline";
  boundsSource: "api" | "offline";
  note?: string;
  queryString: string;
}) {
  const drawn = drawnSources(d);
  const total = drawn.reduce((s, x) => s + x.share, 0) || 1;
  const href = plannerHref(d.lever?.planner_candidate, queryString);
  return (
    <section className="rounded-lg border border-line bg-surface p-4" aria-labelledby="drivers-h" data-testid="drivers">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="drivers-h" className="text-sm font-semibold">
          What makes this band wide
        </h2>
        {source === "offline" && boundsSource === "api" ? (
          // A live API that predates the `drivers` field: same engine output, read from the preset artifact.
          <span className="text-[11px] text-muted" data-testid="drivers-precomputed">
            {note}
          </span>
        ) : (
          <SourceChip source={source} note={note} />
        )}
      </div>
      <p className="mt-1 text-xs text-muted">
        Shares of the 90% band&apos;s width (<span className="num">{fmtBand(d.band90, d.kind, d.unit)}</span>) by where the
        uncertainty comes from, rounded to 5%. They split the width of the band, not the estimate: gravity, vent speed and
        the physics inputs never move the {d.metric} estimate, only the band.
      </p>

      <div
        className="mt-3 flex h-6 w-full overflow-hidden rounded border border-line"
        role="img"
        aria-label={driversSummary(d)}
        data-testid="drivers-bar"
      >
        {drawn.map((s) => {
          const w = (s.share / total) * 100;
          const pct = roundShare5(s.share);
          return (
            <span
              key={s.id}
              data-source={s.id}
              title={`${sourceName(s)}: ${shareLabel(s.share)} (${basisText(s.basis)})`}
              className="num flex items-center justify-center overflow-hidden text-[11px] font-semibold text-bg"
              style={{ width: `${w}%`, background: styleFor(s).bg }}
            >
              {w >= 12 && pct > 0 ? `${pct}%` : ""}
            </span>
          );
        })}
      </div>

      <ul className="mt-3 grid gap-1 text-xs sm:grid-cols-2" aria-label="Sources of the band width" data-testid="drivers-legend">
        {d.sources.map((s) => (
          <li key={s.id} className="flex items-start gap-2" data-source={s.id}>
            <span
              aria-hidden="true"
              className="mt-0.5 inline-block h-3 w-3 shrink-0 rounded-sm border border-line"
              style={{ background: s.reaches_band && s.share > 0 ? styleFor(s).bg : "transparent" }}
            />
            <span>
              <span className="font-medium">{sourceName(s)}</span>:{" "}
              <span className="num" data-testid={`share-${s.id}`}>
                {s.reaches_band ? shareLabel(s.share) : "0%"}
              </span>{" "}
              <span className="text-muted">
                · {s.reaches_band ? basisText(s.basis) : `never reaches this band (${basisText(s.basis)})`}
              </span>
            </span>
          </li>
        ))}
      </ul>

      {d.lever ? (
        <p className="mt-3 text-sm" data-testid="drivers-lever">
          <span className="font-semibold">Biggest lever: </span>
          {d.lever.text}{" "}
          {href ? (
            <Link href={href} className="text-micro underline hover:text-fg" data-testid="drivers-planner-link">
              Open Planner candidate #{d.lever.planner_candidate?.rank} →
            </Link>
          ) : d.lever.source === "model_uncertainty" ? (
            <Link href={`/planner?${queryString}`} className="text-micro underline hover:text-fg" data-testid="drivers-planner-link">
              Open the Planner →
            </Link>
          ) : null}
        </p>
      ) : null}
      <p className="mt-2 text-[11px] text-muted">
        How it is split: the unwidened model band is model uncertainty, the widening every plausible flame gets is the gravity
        honesty rule, and any extra widening is shared between the physics inputs by first-order variance shares (decision
        record ADR-0008).
      </p>
    </section>
  );
}
