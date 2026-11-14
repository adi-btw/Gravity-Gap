import type { DataSource } from "@/lib/api";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-2 py-6 text-sm text-muted">
      <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" className="animate-spin">
        <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="3" strokeDasharray="40 20" />
      </svg>
      {label}
    </div>
  );
}

/** Error panel. Offline-unavailable errors render as a neutral notice, real failures as a warning. */
export function ErrorState({ error, onRetry, title }: { error: Error; onRetry?: () => void; title?: string }) {
  const offline = (error as { offline?: boolean }).offline === true;
  return (
    <div
      role={offline ? "status" : "alert"}
      className={`rounded-md border px-4 py-3 text-sm ${offline ? "hatch border-dashed border-line" : "border-warn bg-[var(--warn-fill)]"}`}
    >
      <p className={`font-semibold ${offline ? "text-fg" : "text-warn"}`}>
        {title ?? (offline ? "Live API needed" : "Could not load this panel")}
      </p>
      <p className="mt-1">{error.message}</p>
      {offline ? (
        <p className="mt-1 text-xs text-muted">
          Start it with <code className="num">python -m uvicorn api.main:app --port 8000</code> from the repo root.
        </p>
      ) : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded border border-line px-2 py-1 text-xs hover:bg-surface-2"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="rounded-md border border-dashed border-line px-4 py-3 text-sm text-muted">{children}</p>;
}

/** Small chip telling the user the panel uses precomputed artifacts instead of the live API. */
export function SourceChip({ source, note }: { source: DataSource; note?: string }) {
  if (source === "api") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5 text-[11px] text-muted">
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-micro" />
        live API
      </span>
    );
  }
  return (
    <span
      title={note}
      className="inline-flex items-center gap-1 rounded-full border border-dashed border-normal px-2 py-0.5 text-[11px] text-normal"
    >
      <svg width="10" height="10" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 3l18 18M8.5 16.5a5 5 0 0 1 7 0M5 13a10 10 0 0 1 5-2.7M19 13a10 10 0 0 0-2-1.6M12 20h.01" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
      </svg>
      offline data
      <span className="sr-only">: {note}</span>
    </span>
  );
}

/** Horizontal 0..1 bar with a text value, used for score parts. */
export function PartBar({ label, value, color = "var(--micro)" }: { label: string; value: number; color?: string }) {
  const v = Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
  return (
    <div className="grid grid-cols-[7.5rem_1fr_2.75rem] items-center gap-2 text-xs">
      <span className="truncate text-muted">{label}</span>
      <span className="h-2 overflow-hidden rounded bg-surface-2" aria-hidden="true">
        <span className="block h-full rounded" style={{ width: `${v * 100}%`, background: color }} />
      </span>
      <span className="num text-right">{Number.isFinite(value) ? value.toFixed(2) : "–"}</span>
    </div>
  );
}
