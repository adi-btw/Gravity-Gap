type Tone = "info" | "warn";

const TONES: Record<Tone, { box: string; icon: string; label: string }> = {
  info: { box: "border-line bg-surface-2", icon: "text-micro", label: "text-micro" },
  warn: { box: "border-warn bg-[var(--warn-fill)]", icon: "text-warn", label: "text-warn" },
};

/**
 * Always-visible note about the limits of a number. "info" (default) explains scope in plain language;
 * "warn" is reserved for real hazards (e.g. the non-monotonic flammability warning), so a scope note never
 * looks like an error.
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
    <div role="note" aria-label={title} className={`flex items-start gap-2 rounded-md border px-3 py-2 text-sm ${t.box}`}>
      <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" className={`mt-0.5 shrink-0 ${t.icon}`}>
        {tone === "warn" ? (
          <>
            <path d="M12 3l10 18H2L12 3z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
            <path d="M12 10v5M12 18v.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </>
        ) : (
          <>
            <circle cx="12" cy="12" r="9.5" fill="none" stroke="currentColor" strokeWidth="2" />
            <path d="M12 11v6M12 7.5v.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </>
        )}
      </svg>
      <div>
        <p className={`font-semibold ${t.label}`}>{title}</p>
        <div className="mt-0.5 space-y-1">{children}</div>
      </div>
    </div>
  );
}
