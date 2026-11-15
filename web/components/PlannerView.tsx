"use client";

import Link from "next/link";
import { useEffect } from "react";
import { api } from "@/lib/api";
import { G0 } from "@/lib/physics";
import { habitatToQuery } from "@/lib/habitat";
import { useAsync } from "@/lib/useAsync";
import { useHabitat } from "@/lib/useHabitat";
import { Empty, ErrorState, Loading, PartBar, SourceChip } from "./ui/States";

const PART_LABEL: Record<string, string> = {
  band_width: "Current band width",
  habitat_weight: "Habitat relevance",
  mixed_fraction: "Mixed-regime fraction",
};

export function PlannerView() {
  const { queryString, habitat } = useHabitat();
  const plan = useAsync(() => api.planner(), "planner");
  // Deep links such as /planner#candidate-6 (from the Bounds "biggest lever"): the list loads async, so scroll once it is there.
  useEffect(() => {
    if (plan.status !== "ok" || typeof window === "undefined" || !window.location.hash.startsWith("#candidate-")) return;
    document.getElementById(window.location.hash.slice(1))?.scrollIntoView({ block: "start" });
  }, [plan.status]);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="doc-label">F6 · Test planner</p>
          <h1 className="page-title">If LUCI or FM2 can run only 10 tests, run these</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Candidates are ranked by how much they would shrink today&apos;s uncertainty in habitat-relevant conditions.
          </p>
        </div>
        {plan.status === "ok" ? <SourceChip source={plan.data.source} note={plan.data.note} /> : null}
      </header>

      {plan.status === "loading" ? <Loading label="Loading test plan…" /> : null}
      {plan.status === "error" ? <ErrorState error={plan.error} onRetry={plan.reload} /> : null}
      {plan.status === "ok" ? (
        <>
          {plan.data.data.method ? (
            <p className="num rounded border border-line bg-surface px-3 py-2 text-xs text-muted">method: {plan.data.data.method}</p>
          ) : null}
          {plan.data.data.tests.length ? (
            <ol className="space-y-3">
              {plan.data.data.tests.map((t) => {
                const q = habitatToQuery({ g_m_s2: t.g_m_s2, p_psia: t.p_psia, o2: t.o2, u_cm_s: t.u_cm_s, L_mm: habitat.L_mm });
                q.set("metric", t.metric);
                return (
                  <li
                    key={`${t.rank}-${t.metric}`}
                    id={`candidate-${t.rank}`}
                    className="scroll-mt-4 panel target:border-2 target:border-partial"
                  >
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <h2 className="text-sm font-medium">
                        <span className="num">#{t.rank}</span> {t.metric} at{" "}
                        <span className="num">
                          {(t.g_m_s2 / G0).toFixed(3)} g · {t.p_psia} psia · O₂ {(t.o2 * 100).toFixed(1)}% · vent {t.u_cm_s} cm/s
                        </span>
                      </h2>
                      <span className="num text-sm">score {t.score.toFixed(3)}</span>
                    </div>
                    <p className="mt-1 text-sm">{t.rationale}</p>
                    <div className="mt-2 grid gap-1 md:max-w-lg" role="group" aria-label={`Score parts for test ${t.rank}`}>
                      {Object.entries(t.parts).map(([k, v]) => (
                        <PartBar key={k} label={PART_LABEL[k] ?? k} value={v} color={k === "mixed_fraction" ? "var(--partial)" : k === "band_width" ? "var(--warn)" : "var(--micro)"} />
                      ))}
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-1 text-xs">
                      <span className="text-muted">Extends:</span>
                      {t.extends.length
                        ? t.extends.map((id) => (
                            <Link key={id} href={`/investigations/${id}?${queryString}`} className="num rounded border border-line px-1.5 py-px text-micro hover:bg-surface-2">
                              {id}
                            </Link>
                          ))
                        : <span className="text-muted">none</span>}
                      <Link href={`/bounds?${q.toString()}`} className="ml-auto text-micro underline">
                        See today&apos;s bounds here →
                      </Link>
                    </div>
                  </li>
                );
              })}
            </ol>
          ) : (
            <Empty>The planner produced no candidate tests.</Empty>
          )}

          <section className="panel" aria-labelledby="impl-h">
            <h2 id="impl-h" className="mb-2 text-sm font-medium">
              Design implications for habitats
            </h2>
            {plan.data.data.design_implications.length ? (
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {plan.data.data.design_implications.map((d) => (
                  <li key={d}>{d}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted">No design implications in this plan.</p>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
