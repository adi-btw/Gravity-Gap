"use client";

import { useState } from "react";
import { api, type TestsFilters } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { Empty, ErrorState, Loading, SourceChip } from "./ui/States";

const PAGE = 50;
const OUTCOMES = [
  "extinction",
  "self_extinguished",
  "flow_terminated",
  "disruption",
  "no_ignition",
  "completion",
  "flash_only",
  "no_sustained_burn",
  "partial_burn",
  "complete_burn",
];
const COLUMNS: { key: string; label: string; num?: boolean }[] = [
  { key: "record_id", label: "Record" },
  { key: "investigation", label: "Investigation" },
  { key: "fuel", label: "Fuel" },
  { key: "o2_mole_fraction", label: "O₂", num: true },
  { key: "pressure_atm", label: "P (atm)", num: true },
  { key: "flow_speed_cm_s", label: "Flow (cm/s)", num: true },
  { key: "size_mm", label: "Size (mm)", num: true },
  { key: "outcome", label: "Outcome" },
  { key: "quality_flags", label: "Flags" },
];

function cell(v: unknown, key: string): string {
  if (v === null || v === undefined || v === "") return "–";
  if (typeof v === "number") return key === "o2_mole_fraction" ? `${(v * 100).toFixed(1)}%` : String(Number(v.toPrecision(4)));
  return String(v).replace(/_/g, " ");
}

/** F8: filterable, paginated view of psi_tests.csv with DOI-cited CSV/JSON export through the API. */
export function DataExplorer() {
  const [inv, setInv] = useState("");
  const [o2min, setO2min] = useState("");
  const [o2max, setO2max] = useState("");
  const [outcome, setOutcome] = useState("");
  const [offset, setOffset] = useState(0);
  const catalog = useAsync(() => api.catalog(), "catalog");

  const pct = (s: string) => (s.trim() === "" || !Number.isFinite(Number(s)) ? undefined : Number(s) / 100);
  // outcome= is passed to the API (phase 3 exact-match filter) so downloads include it. The rows are also
  // filtered here over the full filtered set (under 2,000 rows), which keeps the table correct against an
  // older API that ignores the parameter; against a new API the second filter is a no-op.
  const filters: TestsFilters = {
    investigation_id: inv || undefined,
    o2_min: pct(o2min),
    o2_max: pct(o2max),
    outcome: outcome || undefined,
  };
  const key = JSON.stringify({ ...filters, outcome, offset });
  const page = useAsync(async () => {
    if (!outcome) return api.tests({ ...filters, limit: PAGE, offset });
    const all: Record<string, unknown>[] = [];
    let source: "api" | "offline" = "api";
    for (let off = 0; ; off += 1000) {
      const r = await api.tests({ ...filters, limit: 1000, offset: off });
      source = r.source;
      all.push(...r.data.rows);
      if (off + 1000 >= r.data.total) break;
    }
    const matched = all.filter((row) => row.outcome === outcome);
    return { source, data: { total: matched.length, limit: PAGE, offset, rows: matched.slice(offset, offset + PAGE) } };
  }, key);
  const withData = catalog.status === "ok" ? catalog.data.data.filter((r) => r.n_tests > 0) : [];
  const reset = <T,>(set: (v: T) => void) => (v: T) => {
    set(v);
    setOffset(0);
  };

  const total = page.status === "ok" ? page.data.data.total : 0;
  const rows = page.status === "ok" ? page.data.data.rows : [];

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="doc-label">F8 · Data explorer</p>
          <h1 className="page-title">Every PSI test row behind the predictions</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Filter the cleaned test table and download exactly what you see. Exports start with a citation block that
            lists the DOI of every included investigation.
          </p>
        </div>
        {page.status === "ok" ? <SourceChip source={page.data.source} /> : null}
      </header>

      <form className="flex flex-wrap items-end gap-3 panel" onSubmit={(e) => e.preventDefault()} aria-label="Filters">
        <div className="flex flex-col gap-1">
          <label htmlFor="f-inv" className="text-xs text-muted">Investigation</label>
          <select id="f-inv" value={inv} onChange={(e) => reset(setInv)(e.target.value)} className="rounded border border-line bg-bg px-2 py-1 text-sm">
            <option value="">All</option>
            {withData.map((r) => (
              <option key={r.id} value={r.id}>
                {r.id} {r.acronym ?? ""}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="f-o2min" className="text-xs text-muted">O₂ min (%)</label>
          <input id="f-o2min" type="number" min={0} max={100} step={0.5} value={o2min} onChange={(e) => reset(setO2min)(e.target.value)} className="w-24 rounded border border-line bg-bg px-2 py-1 text-sm" />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="f-o2max" className="text-xs text-muted">O₂ max (%)</label>
          <input id="f-o2max" type="number" min={0} max={100} step={0.5} value={o2max} onChange={(e) => reset(setO2max)(e.target.value)} className="w-24 rounded border border-line bg-bg px-2 py-1 text-sm" />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="f-out" className="text-xs text-muted">Outcome</label>
          <select id="f-out" value={outcome} onChange={(e) => reset(setOutcome)(e.target.value)} className="rounded border border-line bg-bg px-2 py-1 text-sm">
            <option value="">All</option>
            {OUTCOMES.map((o) => (
              <option key={o} value={o}>
                {o.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={() => {
            setInv("");
            setO2min("");
            setO2max("");
            setOutcome("");
            setOffset(0);
          }}
          className="rounded border border-line px-2 py-1 text-xs hover:bg-surface-2"
        >
          Clear
        </button>
        <div className="ml-auto flex gap-2">
          {(["csv", "json"] as const).map((f) => (
            <a
              key={f}
              href={page.status === "ok" ? api.exportUrl(filters, f) : undefined}
              aria-disabled={page.status !== "ok"}
              download
              className={`rounded-md border px-3 py-1.5 text-sm ${page.status === "ok" ? "border-micro text-micro hover:bg-surface-2" : "pointer-events-none border-line text-muted opacity-50"}`}
            >
              Download {f.toUpperCase()}
            </a>
          ))}
        </div>
      </form>

      <section aria-live="polite" className="panel">
        {page.status === "loading" ? <Loading label="Loading tests…" /> : null}
        {page.status === "error" ? <ErrorState error={page.error} onRetry={page.reload} /> : null}
        {page.status === "ok" ? (
          rows.length ? (
            <>
              {outcome ? (
                <p className="mb-2 text-xs text-muted">
                  Outcome filter: <span className="num">{outcome}</span>. Downloads pass it to the API as{" "}
                  <code className="num">outcome=</code> (exact match).
                </p>
              ) : null}
              <div className="overflow-x-auto">
                <table className="w-full min-w-[48rem] text-left text-xs">
                  <caption className="sr-only">PSI test rows matching the filters</caption>
                  <thead className="text-muted">
                    <tr>
                      {COLUMNS.map((c) => (
                        <th key={c.key} scope="col" className={`py-1 pr-2 ${c.num ? "text-right" : ""}`}>
                          {c.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => (
                      <tr key={String(r.record_id ?? i)} className="border-t border-line">
                        {COLUMNS.map((c) => (
                          <td key={c.key} className={`py-1 pr-2 ${c.num || c.key === "record_id" ? "num" : ""} ${c.num ? "text-right" : ""}`}>
                            {cell(r[c.key], c.key)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <nav aria-label="Pagination" className="mt-3 flex items-center gap-3 text-sm">
                <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))} className="rounded border border-line px-2 py-1 disabled:opacity-40">
                  ← Previous
                </button>
                <span className="num text-xs text-muted">
                  {offset + 1}–{Math.min(offset + PAGE, total)} of {total}
                </span>
                <button type="button" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)} className="rounded border border-line px-2 py-1 disabled:opacity-40">
                  Next →
                </button>
              </nav>
            </>
          ) : (
            <Empty>No test rows match these filters.</Empty>
          )
        ) : null}
      </section>
    </div>
  );
}
