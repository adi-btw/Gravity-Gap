"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { api } from "@/lib/api";
import {
  CHIP_TEXT,
  chipLabel,
  gapsByKind,
  isPresetId,
  nextTestLine,
  resolveBriefingTarget,
  shortHash,
  type Briefing,
  type BriefingChip,
  type ChipValue,
} from "@/lib/briefing";
import { habitatToQuery, presetToHabitat } from "@/lib/habitat";
import { PRESETS_BY_ID } from "@/lib/presets";
import { useAsync } from "@/lib/useAsync";
import { useHabitat } from "@/lib/useHabitat";
import { ErrorState, Loading, SourceChip } from "./ui/States";

/** S1 one-page habitat fire-safety briefing (ADR-0010): composed engine outputs, printable on one page. */
export function BriefingView() {
  const { habitat } = useHabitat();
  const sp = useSearchParams();
  const pathname = usePathname();
  const param = sp.get("habitat");
  const target = resolveBriefingTarget(param, habitat);

  // ?habitat=<preset> is written back as habitat-bar values, so the bar shows the briefed habitat and edits to it apply.
  useEffect(() => {
    if (param === null) return;
    const q = new URLSearchParams(sp.toString());
    q.delete("habitat");
    const next = isPresetId(param) ? habitatToQuery(presetToHabitat(PRESETS_BY_ID[param]), q) : q;
    window.history.replaceState(null, "", `${pathname}?${next.toString()}`);
  }, [param, pathname, sp]);

  const key = target.presetId ?? JSON.stringify(target.habitat);
  const res = useAsync(() => api.briefing(target.presetId, target.habitat), `briefing|${key}`);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3 print:hidden">
        <div>
          <p className="doc-label">S1 · Fire-safety briefing</p>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Everything Gravity Gap can and cannot tell a designer about fire in this habitat, on one page. Change the habitat
            in the bar above; every number comes from the engine.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {res.status === "ok" ? <SourceChip source={res.data.source} note={res.data.note} /> : null}
          <button
            type="button"
            onClick={() => window.print()}
            className="btn-primary"
            data-testid="print-briefing"
          >
            Print / save as PDF
          </button>
        </div>
      </div>
      {res.status === "loading" ? <Loading label="Loading the briefing…" /> : null}
      {res.status === "error" ? <ErrorState error={res.error} onRetry={res.reload} /> : null}
      {res.status === "ok" ? <BriefingDoc b={res.data.data} /> : null}
    </div>
  );
}

function Cites({ ids }: { ids: string[] }) {
  if (!ids.length) return null;
  return <span className="num text-[10px] text-muted print:hidden"> [{ids.join(", ")}]</span>;
}

function Section({ id, title, children, className = "" }: { id: string; title: string; children: React.ReactNode; className?: string }) {
  return (
    <section aria-labelledby={`${id}-h`} className={`break-inside-avoid ${className}`} data-testid={`section-${id}`}>
      <h2 id={`${id}-h`} className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted print:mb-0.5 print:text-fg">
        {title}
      </h2>
      {children}
    </section>
  );
}

const CHIP_STYLE: Record<ChipValue, string> = {
  evidence: "border-2 border-solid border-micro",
  partial: "border-2 border-dashed border-partial",
  "no evidence": "border-2 border-dotted border-nodata hatch",
};

/** Shape, not colour: filled circle with a tick, half-filled circle, empty circle with a cross. */
function ChipIcon({ value }: { value: ChipValue }) {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true" className="shrink-0">
      {value === "evidence" ? (
        <>
          <circle cx="8" cy="8" r="7" fill="currentColor" />
          <path d="M4.5 8.2l2.3 2.3 4.7-4.9" fill="none" stroke="var(--surface)" strokeWidth="2" />
        </>
      ) : value === "partial" ? (
        <>
          <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <path d="M8 1.5a6.5 6.5 0 0 1 0 13z" fill="currentColor" />
        </>
      ) : (
        <>
          <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <path d="M5.3 5.3l5.4 5.4M10.7 5.3l-5.4 5.4" stroke="currentColor" strokeWidth="1.5" />
        </>
      )}
    </svg>
  );
}

function Chip({ c }: { c: BriefingChip }) {
  const t = CHIP_TEXT[c.value];
  return (
    <li className={`rounded-md p-2 print:p-1.5 ${CHIP_STYLE[c.value]}`} data-testid={`chip-${c.pillar}`} data-value={c.value} aria-label={chipLabel(c)}>
      <p className="flex items-center gap-1.5 text-sm font-semibold">
        <ChipIcon value={c.value} />
        <span>{c.label}</span>
        <span className="ml-auto rounded border border-current px-1.5 text-[11px] uppercase tracking-wide" data-testid="chip-value">
          {t.word}
        </span>
      </p>
      <p className="mt-1 text-xs" title={`Rule: ${c.rule}`}>
        {c.because}
        <Cites ids={c.citations} />
      </p>
      <details className="mt-1 text-xs print:hidden" data-testid="chip-rule">
        <summary className="cursor-pointer text-muted hover:text-fg">Rule for this chip</summary>
        <p className="mt-1">{c.rule}</p>
      </details>
    </li>
  );
}

function BriefingDoc({ b }: { b: Briefing }) {
  const { queryString } = useHabitat();
  const gaps = gapsByKind(b.gaps);
  const hash = shortHash(b.footer.manifest?.artifact_set_sha256);
  const models = Object.entries(b.footer.model_versions ?? {});
  return (
    <article
      aria-labelledby="briefing-title"
      data-testid="briefing"
      className="briefing space-y-3 rounded-lg border border-line bg-surface p-4 text-sm print:space-y-1.5 print:rounded-none print:border-0 print:p-0"
    >
      <header>
        <p className="doc-label print:text-fg">Gravity Gap · Habitat fire-safety briefing</p>
        <h1 id="briefing-title" className="text-xl font-semibold print:text-base">
          {b.habitat.label}: what the evidence can and cannot say about fire
        </h1>
        <p className="mt-1" data-testid="briefing-habitat">
          {b.habitat.line}
        </p>
        <p className="text-xs text-muted">
          Source: {b.habitat.source}. Values marked &ldquo;assumed&rdquo; are engineering assumptions.
        </p>
      </header>

      <Section id="verdicts" title="Verdict per pillar (each chip follows a written rule)">
        <ul className="grid gap-2 sm:grid-cols-2 print:grid-cols-2 print:gap-1.5" data-testid="verdicts">
          {b.verdicts.map((c) => (
            <Chip key={c.pillar} c={c} />
          ))}
        </ul>
      </Section>

      <div className="grid gap-3 md:grid-cols-2 print:grid-cols-2 print:gap-2">
        <Section id="numbers" title="Key numbers (metrics with evidence only)">
          {b.key_numbers.length ? (
            <ul className="space-y-0.5 text-xs" data-testid="key-numbers">
              {b.key_numbers.map((k) => (
                <li key={k.metric} data-testid={`number-${k.metric}`}>
                  {k.text}
                  <Cites ids={k.citations} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs">No metric has evidence at this habitat, so no number is given.</p>
          )}
        </Section>
        <Section id="drivers" title="What drives the uncertainty">
          {b.drivers.length ? (
            <ul className="space-y-0.5 text-xs" data-testid="drivers-lever">
              {b.drivers.map((d) => (
                <li key={d.metric}>
                  <span className="font-medium">{d.metric}:</span> {d.text}
                  <Cites ids={d.citations} />
                  {d.planner_candidate ? (
                    <>
                      {" "}
                      <Link href={`/planner?${queryString}#candidate-${d.planner_candidate.rank}`} className="text-micro underline print:hidden">
                        Planner #{d.planner_candidate.rank} →
                      </Link>
                    </>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs">No band to break down: no droplet or gas-flame model has evidence here.</p>
          )}
        </Section>
      </div>

      <Section id="gaps" title="Known gaps (no number is given for these)">
        <ul className="space-y-1 text-xs md:columns-2 md:gap-4 print:columns-2 print:gap-3 print:space-y-0.5" data-testid="gaps">
          {[...gaps.metric, ...gaps.detection, ...gaps.suppression].map((g) => (
            <li key={g.id} className="break-inside-avoid" data-testid={`gap-${g.id}`} data-kind={g.kind}>
              {g.kind === "metric" ? <span className="font-semibold">{g.metric} · </span> : null}
              {g.kind === "detection" ? <span className="font-semibold">Detection · </span> : null}
              {g.kind === "suppression" ? <span className="font-semibold">Suppression · </span> : null}
              {g.kind === "metric" ? g.text.replace(new RegExp(`^${g.metric}\\s+`), "") : g.text}
              {g.safety_note ? <span className="italic"> {g.safety_note}</span> : null}
              <Cites ids={g.citations} />
            </li>
          ))}
        </ul>
      </Section>

      <Section id="next" title="Recommended next tests (Planner)">
        <ol className="space-y-0.5 text-xs" data-testid="next-tests">
          {b.next_tests.items.map((t) => (
            <li key={t.rank}>
              <span className="font-medium">Planner #{t.rank}:</span> {nextTestLine(t)}
              <Cites ids={t.citations} />
              <details className="print:hidden">
                <summary className="cursor-pointer text-muted hover:text-fg">Why this test</summary>
                <p className="mt-0.5">{t.rationale}</p>
              </details>
            </li>
          ))}
        </ol>
        {b.next_tests.note ? <p className="text-xs">{b.next_tests.note}</p> : null}
        <p className="text-xs text-muted print:hidden">
          {b.next_tests.rule}{" "}
          <Link href={`/planner?${queryString}`} className="text-micro underline">
            Open the Planner →
          </Link>
        </p>
      </Section>

      <div className="grid gap-3 md:grid-cols-2 print:grid-cols-2 print:gap-2">
        <Section id="history" title="History check">
          <p className="text-xs" data-testid="history">
            {b.history.text}
            <Cites ids={b.history.citations} />
          </p>
        </Section>
        <Section id="trust" title="How far to trust this">
          <p className="text-xs" data-testid="trust-line">
            {b.trust.text}
            <Cites ids={b.trust.citations} />{" "}
            <Link href={`/trust?${queryString}`} className="text-micro underline print:hidden">
              Can I trust it? →
            </Link>
          </p>
        </Section>
      </div>

      <footer className="border-t border-line pt-2 text-[11px] print:pt-1 print:text-[0.75rem]" data-testid="briefing-footer">
        <p className="font-semibold">{b.footer.disclaimer}</p>
        <p className="text-muted print:text-fg">
          Models {models.map(([m, v]) => `${m} ${v}`).join(", ")}; engine {b.footer.engine_version}
          {hash ? (
            <>
              ; artifact set at build time <span className="num">{hash}</span>
            </>
          ) : null}
          ; generated {b.footer.date}. Sources cited: {b.citations.filter((c) => c !== "eng:briefing").join(", ")}.
        </p>
      </footer>
    </article>
  );
}
