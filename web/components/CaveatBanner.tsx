export function CaveatBanner({ children }: { children: React.ReactNode }) {
  return (
    <div
      role="note"
      className="flex items-start gap-2 rounded-md border border-warn bg-[var(--warn-fill)] px-3 py-2 text-sm"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" className="mt-0.5 shrink-0 text-warn">
        <path d="M12 3l10 18H2L12 3z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
        <path d="M12 10v5M12 18v.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
      <div>
        <span className="font-semibold text-warn">Caveat: </span>
        {children}
      </div>
    </div>
  );
}
