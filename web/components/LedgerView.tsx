"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtBand, fmtEstimate } from "@/lib/format";
import { parseLedger, verifyRecord, type LedgerRecord, type Verification } from "@/lib/ledger";
import { useAsync } from "@/lib/useAsync";
import { Empty, ErrorState, Loading, SourceChip } from "./ui/States";

const STATUS_STYLE: Record<string, string> = {
  open: "border-partial text-partial",
  confirmed: "border-micro text-micro",
  refuted: "border-warn text-warn",
  inconclusive: "border-line text-muted",
};

interface Row {
  rec: LedgerRecord;
  v: Verification | { error: string } | null;
}

function habitatText(h: unknown): string {
  if (!h || typeof h !== "object") return "–";
  const o = h as Record<string, unknown>;
  const label = (o.label as string) ?? (o.preset_id as string) ?? "custom";
  const g = typeof o.g_m_s2 === "number" ? `${o.g_m_s2} m/s²` : "";
  const p = typeof o.p_psia === "number" ? `${o.p_psia} psia` : "";
  const x = typeof o.o2 === "number" ? `O₂ ${(o.o2 * 100).toFixed(1)}%` : "";
  const u = typeof o.u_cm_s === "number" ? `vent ${o.u_cm_s} cm/s` : "";
  return `${label} · ${[g, p, x, u].filter(Boolean).join(" · ")}`;
}

export function LedgerView() {
  const ledger = useAsync(() => api.ledgerText(), "ledger");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [parseError, setParseError] = useState<Error | null>(null);

  useEffect(() => {
    if (ledger.status !== "ok") return;
    let alive = true;
    try {
      const recs = parseLedger(ledger.data.data.kind, ledger.data.data.text);
      setParseError(null);
      setRows(recs.map((rec) => ({ rec, v: null })));
      Promise.all(
        recs.map((r) =>
          verifyRecord(r.raw).catch((e: unknown) => ({ error: e instanceof Error ? e.message : String(e) })),
        ),
      ).then((vs) => alive && setRows(recs.map((rec, i) => ({ rec, v: vs[i] }))));
    } catch (e) {
      setParseError(e instanceof Error ? e : new Error(String(e)));
    }
    return () => {
      alive = false;
    };
  }, [ledger.status, ledger.data]);

  const nOk = rows?.filter((r) => r.v && "ok" in r.v && r.v.ok).length ?? 0;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wider text-partial">F5 · Prediction ledger</p>
          <h1 className="text-2xl font-semibold">Predictions we froze before anyone tested them</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Each line of <code className="num">ledger/predictions.jsonl</code> is append-only and carries a SHA-256 of
            its own content. Your browser recomputes every hash below; the git commit time of the line is the timestamp
            proof.
          </p>
        </div>
        {ledger.status === "ok" ? <SourceChip source={ledger.data.source} note={ledger.data.note} /> : null}
      </header>

      {ledger.status === "loading" ? <Loading label="Loading ledger…" /> : null}
      {ledger.status === "error" ? <ErrorState error={ledger.error} onRetry={ledger.reload} /> : null}
      {parseError ? <ErrorState error={parseError} title="The ledger file could not be parsed" /> : null}

      {rows && !parseError ? (
        rows.length ? (
          <section className="overflow-x-auto rounded-lg border border-line bg-surface p-4">
            <p className="mb-2 text-sm" aria-live="polite">
              <span className="num font-semibold">{nOk}</span> of <span className="num">{rows.length}</span> hashes
              verified in your browser.
            </p>
            <table className="w-full min-w-[56rem] text-left text-xs">
              <caption className="sr-only">Frozen predictions with in-browser hash verification</caption>
              <thead className="text-muted">
                <tr>
                  <th scope="col" className="py-1 pr-2">ID</th>
                  <th scope="col" className="py-1 pr-2">Created (UTC)</th>
                  <th scope="col" className="py-1 pr-2">Habitat</th>
                  <th scope="col" className="py-1 pr-2">Metric</th>
                  <th scope="col" className="py-1 pr-2">Estimate · 90% band</th>
                  <th scope="col" className="py-1 pr-2">Status</th>
                  <th scope="col" className="py-1">SHA-256 check</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ rec, v }, i) => {
                  const r = rec.record;
                  const metric = String(r.metric ?? "");
                  const kind = typeof r.estimate === "string" ? "category" : metric === "M2" ? "quantity" : "probability";
                  const status = String(r.status ?? "open");
                  return (
                    <tr key={String(r.id ?? i)} className="border-t border-line align-top">
                      <th scope="row" className="num py-1.5 pr-2 font-normal">{String(r.id ?? "–")}</th>
                      <td className="num py-1.5 pr-2">{String(r.created_at ?? "–").replace("+00:00", "Z")}</td>
                      <td className="py-1.5 pr-2">{habitatText(r.habitat)}</td>
                      <td className="num py-1.5 pr-2">{metric}</td>
                      <td className="num py-1.5 pr-2">
                        {r.estimate === null || r.estimate === undefined
                          ? r.applicable === false
                            ? "no estimate (extrapolation)"
                            : "–"
                          : `${fmtEstimate(r.estimate as number | string, kind, kind === "quantity" ? "mm" : null)} · ${fmtBand(
                              r.band90 as (number | string)[] | null,
                              kind,
                              kind === "quantity" ? "mm" : null,
                            )}`}
                      </td>
                      <td className="py-1.5 pr-2">
                        <span className={`rounded border px-1.5 py-px ${STATUS_STYLE[status] ?? "border-line"}`}>{status}</span>
                      </td>
                      <td className="py-1.5">
                        {v === null ? (
                          <span className="text-muted">checking…</span>
                        ) : "error" in v ? (
                          <span className="text-warn">cannot check: {v.error}</span>
                        ) : v.ok ? (
                          <span className="text-micro" title={`computed ${v.computed}`}>
                            ✓ verified <span className="num text-muted">{v.computed.slice(0, 12)}…</span>
                          </span>
                        ) : (
                          <span className="font-semibold text-warn" title={`stored ${v.expected ?? "none"} · computed ${v.computed}`}>
                            ✗ mismatch <span className="num font-normal">stored {(v.expected ?? "none").slice(0, 12)}… computed {v.computed.slice(0, 12)}…</span>
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
        ) : (
          <Empty>No predictions have been frozen yet.</Empty>
        )
      ) : null}

      <section className="rounded-lg border border-line bg-surface p-4 text-sm" aria-labelledby="luci-h">
        <h2 id="luci-h" className="mb-2 font-semibold">
          How to check this when LUCI reports
        </h2>
        <ol className="list-decimal space-y-1 pl-5">
          <li>Find the prediction for the habitat and metric LUCI (or FM2) actually tested: gravity, pressure, O₂, vent speed.</li>
          <li>
            Confirm the line is untouched: its hash above must read <em>verified</em>, and <code className="num">git log -p ledger/predictions.jsonl</code> shows when
            it was committed, before the test.
          </li>
          <li>
            Compare the measured outcome with the 90% band: inside the band means <em>confirmed</em>, outside means <em>refuted</em>, a
            test that did not measure this metric cleanly is <em>inconclusive</em>.
          </li>
          <li>Record the result as a new appended line; existing lines are never edited (CI rejects edits).</li>
        </ol>
        <p className="mt-2 text-xs text-muted">
          Recompute a hash yourself: <code className="num">sha256(json.dumps(record_without_sha256, sort_keys=True, separators=(&quot;,&quot;, &quot;:&quot;), ensure_ascii=False))</code>.
        </p>
      </section>
    </div>
  );
}
