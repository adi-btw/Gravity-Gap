import Link from "next/link";
import type { EvidenceRow } from "@/lib/types";

/** Group evidence rows by investigation, keeping first-seen order. */
export function groupEvidence(rows: EvidenceRow[]): [string, EvidenceRow[]][] {
  const m = new Map<string, EvidenceRow[]>();
  rows.forEach((r) => {
    const k = r.investigation_id ?? r.record_id.split(":")[0];
    m.set(k, [...(m.get(k) ?? []), r]);
  });
  return [...m.entries()];
}

/** Evidence chips grouped by investigation; hover or keyboard focus reveals the full record id and distance. */
export function EvidenceList({ rows, queryString }: { rows: EvidenceRow[]; queryString?: string }) {
  if (!rows.length) return <p className="text-sm text-muted">No training rows are attached to this estimate.</p>;
  return (
    <ul className="space-y-2">
      {groupEvidence(rows).map(([inv, items]) => (
        <li key={inv}>
          <Link href={`/investigations/${inv}${queryString ? `?${queryString}` : ""}`} className="num text-sm text-micro underline">
            {inv}
          </Link>{" "}
          <span className="text-xs text-muted">
            ({items.length} record{items.length === 1 ? "" : "s"})
          </span>
          <div className="mt-1 flex flex-wrap gap-1">
            {items.map((r) => {
              const short = r.record_id.split(":").slice(1).join(":") || r.record_id;
              const tip = `${r.record_id}${r.distance !== undefined && r.distance !== null ? ` · atmosphere distance ${r.distance.toFixed(2)}` : ""}`;
              const tipId = `ev-tip-${r.record_id.replace(/[^A-Za-z0-9_-]/g, "-")}`;
              return (
                <span key={r.record_id} className="group relative">
                  <span
                    tabIndex={0}
                    aria-describedby={tipId}
                    className="num inline-block cursor-default rounded border border-line px-1.5 py-px text-[11px] hover:border-micro focus:border-micro"
                  >
                    {short}
                  </span>
                  <span
                    id={tipId}
                    role="tooltip"
                    className="num pointer-events-none absolute bottom-full left-0 z-10 mb-1 hidden whitespace-nowrap rounded border border-line bg-surface-2 px-2 py-1 text-[11px] shadow group-hover:block group-focus-within:block"
                  >
                    {tip}
                  </span>
                </span>
              );
            })}
          </div>
        </li>
      ))}
    </ul>
  );
}
