type Tone = "info" | "warn";

const TONES: Record<Tone, { box: string; label: string }> = {
  info: { box: "border-line border-l-line-strong bg-surface", label: "text-fg" },
  warn: { box: "border-warn bg-[var(--warn-fill)]", label: "text-warn" },
};

/**
 * Always-visible note about the limits of a number, set like a ruled note in a test report. "info" (default)
 * explains scope in plain language; "warn" is reserved for real hazards (e.g. the non-monotonic flammability
 * warning), so a scope note never looks like an error.
 */
export function CaveatBanner({
  children,
  title = "Good to know",
  tone = "info",
}: {
  children: React.ReactNode;
  title?: string;
  tone?: Tone;
}) {
  const t = TONES[tone];
  return (
    <div role="note" aria-label={title} className={`rounded-sm border border-l-2 px-4 py-3 text-sm ${t.box}`}>
      <p className={`flex items-center gap-1.5 text-[13px] font-semibold ${t.label}`}>
        {tone === "warn" ? (
          <svg width="12" height="12" viewBox="0 0 24 24" aria-hidden="true" className="shrink-0">
            <path d="M12 3l10 18H2L12 3z" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinejoin="round" />
            <path d="M12 10v5M12 18v.5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
          </svg>
        ) : null}
        {title}
      </p>
      <div className="mt-1.5 max-w-[78ch] space-y-1 leading-relaxed">{children}</div>
    </div>
  );
}
