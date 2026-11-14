const PARTS = [
  { key: "forced", label: "forced", color: "var(--micro)", pattern: "" },
  { key: "mixed", label: "mixed", color: "var(--partial)", pattern: "" },
  { key: "buoyant", label: "buoyant", color: "var(--normal)", pattern: "" },
] as const;

/** Mini stacked bar of Monte Carlo regime fractions, with a text legend (color is not the only signal). */
export function RegimeFractionsBar({ fractions }: { fractions: { forced: number; mixed: number; buoyant: number } }) {
  const total = PARTS.reduce((s, p) => s + (fractions[p.key] ?? 0), 0) || 1;
  const label = PARTS.map((p) => `${p.label} ${Math.round(((fractions[p.key] ?? 0) / total) * 100)}%`).join(", ");
  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded" role="img" aria-label={`Regime fractions across uncertainty samples: ${label}`}>
        {PARTS.map((p) => (
          <span key={p.key} style={{ width: `${((fractions[p.key] ?? 0) / total) * 100}%`, background: p.color }} />
        ))}
      </div>
      <p className="num mt-1 flex flex-wrap gap-x-3 text-[11px] text-muted">
        {PARTS.map((p) => (
          <span key={p.key}>
            <span aria-hidden="true" className="mr-1 inline-block h-2 w-2 rounded-sm" style={{ background: p.color }} />
            {p.label} {(((fractions[p.key] ?? 0) / total) * 100).toFixed(0)}%
          </span>
        ))}
      </p>
    </div>
  );
}
