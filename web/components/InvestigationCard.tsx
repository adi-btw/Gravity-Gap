"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { conditionRows, firstSentences } from "@/lib/catalog";
import type { CatalogRecord } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";
import { useHabitat } from "@/lib/useHabitat";
import { useAsk } from "./AskDrawer";
import { fuelStyle } from "./charts/GravitySpectrum";
import { Empty, ErrorState, Loading, SourceChip } from "./ui/States";

const PILLAR_STYLE: Record<string, string> = {
  prevention: "border-micro text-micro",
  detection: "border-normal text-normal",
  suppression: "border-partial text-partial",
};

/**
 * F7 investigation card. The build-time record (from the bundled catalog) renders immediately; without it the
 * card fetches the catalog from the API or the static artifact.
 */
export function InvestigationCard({
  id,
  initialRecord,
  names,
}: {
  id: string;
  initialRecord: CatalogRecord | null;
  names: Record<string, string | null>;
}) {
  const catalog = useAsync(
    async () =>
      initialRecord
        ? { data: { rec: initialRecord as CatalogRecord | undefined, names }, source: "offline" as const, note: "bundled at build time" }
        : api.catalog().then((r) => ({
            ...r,
            data: {
              rec: r.data.find((x) => x.id === id),
              names: Object.fromEntries(r.data.map((x) => [x.id, x.acronym])) as Record<string, string | null>,
            },
          })),
    `catalog|${id}`,
  );
  if (catalog.status === "loading") return <Loading label="Loading investigation…" />;
  if (catalog.status === "error") return <ErrorState error={catalog.error} onRetry={catalog.reload} />;
  const { rec, names: nm } = catalog.data.data;
  if (!rec) {
    return (
      <Empty>
        No investigation <span className="num">{id}</span> in the catalog.{" "}
        <Link href="/explore" className="text-micro underline">
          Back to the gravity spectrum
        </Link>
      </Empty>
    );
  }
  return <Card rec={rec} names={nm} fromBuild={!!initialRecord} source={catalog.data.source} />;
}

function Card({ rec, names, fromBuild, source }: { rec: CatalogRecord; names: Record<string, string | null>; fromBuild: boolean; source: "api" | "offline" }) {
  const { queryString } = useHabitat();
  const { open } = useAsk();
  const summary = firstSentences(rec.objective, 2);
  const conds = conditionRows(rec.conditions);
  const invLink = (iid: string) => (
    <Link key={iid} href={`/investigations/${iid}?${queryString}`} className="num rounded border border-line px-1.5 py-px text-xs text-micro hover:bg-surface-2">
      {iid}
      {names[iid] ? ` ${names[iid]}` : ""}
    </Link>
  );
  const reuses = rec.lineage?.reuses ?? [];
  const reanalyzed = rec.reanalyzed_by ?? [];
  const related = (rec.related ?? []).filter((r) => !reuses.includes(r) && !reanalyzed.includes(r));

  return (
    <article className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="doc-label">
            {rec.id} · {rec.platform ?? "platform unknown"}
          </p>
          <h1 className="page-title">{rec.acronym ?? rec.title}</h1>
          {rec.acronym && rec.title ? <p className="text-sm text-muted">{rec.title}</p> : null}
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            {rec.doi ? (
              <a href={`https://doi.org/${rec.doi}`} target="_blank" rel="noreferrer" className="num rounded border border-micro px-2 py-0.5 text-micro">
                DOI {rec.doi}
              </a>
            ) : (
              <span className="rounded border border-line px-2 py-0.5 text-muted">no dataset DOI</span>
            )}
            {!rec.is_combustion ? <span className="rounded border border-warn px-2 py-0.5 text-warn">not combustion: excluded from ranking</span> : null}
            {fromBuild ? null : <SourceChip source={source} />}
          </div>
        </div>
        <button
          type="button"
          onClick={() => open({ question: `What does ${rec.acronym ?? rec.id} (${rec.id}) tell us about fire in this habitat?`, contextIds: [rec.id] })}
          className="rounded-md border border-partial px-3 py-1.5 text-sm text-partial hover:bg-surface-2"
        >
          Ask about this
        </button>
      </header>

      <section className="rounded-lg border border-line bg-surface p-4">
        <h2 className="text-sm font-semibold">
          Summary <span className="ml-1 rounded border border-line px-1.5 text-[10px] font-normal uppercase text-muted">from PSI metadata</span>
        </h2>
        <p className="mt-1 text-sm">{summary || "The PSI metadata has no objective text for this investigation."}</p>
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-lg border border-line bg-surface p-4">
          <h2 className="mb-2 text-sm font-semibold">Facts</h2>
          <dl className="grid grid-cols-[9rem_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-muted">Hardware</dt>
            <dd>{rec.hardware ?? "–"}</dd>
            <dt className="text-muted">Platform</dt>
            <dd>{rec.platform ?? "–"}</dd>
            <dt className="text-muted">Gravity</dt>
            <dd>{(rec.gravity_levels ?? []).join(", ").replace(/_/g, " ") || "–"}</dd>
            <dt className="text-muted">Fuel phase</dt>
            <dd>{fuelStyle(rec.fuel_phase).label}</dd>
            <dt className="text-muted">Tests in table</dt>
            <dd className="num">{rec.n_tests}</dd>
            <dt className="text-muted">Outcomes</dt>
            <dd>{rec.outcomes_available ? "available per test" : "not recorded"}</dd>
            {rec.ground_reference_note ? (
              <>
                <dt className="text-muted">1 g reference</dt>
                <dd>{rec.ground_reference_note}</dd>
              </>
            ) : null}
          </dl>
        </section>
        <section className="rounded-lg border border-line bg-surface p-4">
          <h2 className="mb-2 text-sm font-semibold">Conditions covered (computed from the test table)</h2>
          {conds.length ? (
            <table className="w-full text-left text-sm">
              <tbody>
                {conds.map((c) => (
                  <tr key={c.key} className="border-t border-line">
                    <th scope="row" className="py-1 pr-2 font-normal text-muted">{c.label}</th>
                    <td className="num py-1">{c.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-muted">No condition ranges recorded.</p>
          )}
        </section>
      </div>

      <section className="rounded-lg border border-line bg-surface p-4">
        <h2 className="mb-2 text-sm font-semibold">Fire-safety pillars</h2>
        {rec.hazard_pillars?.length ? (
          <ul className="flex flex-wrap gap-3">
            {rec.hazard_pillars.map((p) => (
              <li key={p} className={`rounded-md border-2 px-2 py-1 text-xs ${PILLAR_STYLE[p] ?? "border-line"}`}>
                <span className="font-semibold uppercase">{p}</span>
                {rec.pillar_evidence?.[p]?.length ? (
                  <span className="ml-1 text-fg">· keywords: {rec.pillar_evidence[p].join(", ")}</span>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">No pillar evidence in the metadata.</p>
        )}
      </section>

      {rec.hypothesis ? (
        <section className="rounded-lg border border-line bg-surface p-4">
          <h2 className="mb-1 text-sm font-semibold">Hypothesis</h2>
          <p className="whitespace-pre-line text-sm">{rec.hypothesis}</p>
        </section>
      ) : null}
      {rec.impacts ? (
        <section className="rounded-lg border border-line bg-surface p-4">
          <h2 className="mb-1 text-sm font-semibold">Earth applications</h2>
          <p className="whitespace-pre-line text-sm">{rec.impacts}</p>
        </section>
      ) : null}

      <section className="rounded-lg border border-line bg-surface p-4">
        <h2 className="mb-2 text-sm font-semibold">Lineage</h2>
        {reuses.length || reanalyzed.length || related.length ? (
          <dl className="space-y-2 text-sm">
            {reuses.length ? (
              <div>
                <dt className="text-xs text-muted">Reanalyzes data from</dt>
                <dd className="mt-1 flex flex-wrap gap-1">{reuses.map(invLink)}</dd>
              </div>
            ) : null}
            {reanalyzed.length ? (
              <div>
                <dt className="text-xs text-muted">Reanalyzed by (ground studies)</dt>
                <dd className="mt-1 flex flex-wrap gap-1">{reanalyzed.map(invLink)}</dd>
              </div>
            ) : null}
            {related.length ? (
              <div>
                <dt className="text-xs text-muted">Related</dt>
                <dd className="mt-1 flex flex-wrap gap-1">{related.map(invLink)}</dd>
              </div>
            ) : null}
            {rec.lineage?.evidence ? <p className="text-xs text-muted">Basis: {rec.lineage.evidence}</p> : null}
          </dl>
        ) : (
          <p className="text-sm text-muted">No lineage links in the metadata.</p>
        )}
      </section>

      <section className="rounded-lg border border-line bg-surface p-4">
        <h2 className="mb-2 text-sm font-semibold">Publications ({rec.publications?.length ?? 0})</h2>
        {rec.publications?.length ? (
          <ul className="space-y-1 text-sm">
            {rec.publications.map((p, i) => (
              <li key={`${p.doi}-${i}`}>
                {p.title ?? "Untitled"}
                {p.doi ? (
                  <>
                    {" "}
                    <a href={`https://doi.org/${p.doi}`} target="_blank" rel="noreferrer" className="num text-xs text-micro underline">
                      doi:{p.doi}
                    </a>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">No publications listed.</p>
        )}
      </section>
    </article>
  );
}
