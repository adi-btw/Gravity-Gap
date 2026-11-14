import type { Regime } from "@/lib/physics";
import { REGIME_LABEL } from "@/lib/format";

const STYLE: Record<Regime, string> = {
  forced: "border-micro text-micro",
  mixed: "border-partial text-partial",
  buoyant: "border-normal text-normal",
};

/** Icon shapes differ per regime so color is never the only signal. */
export function RegimeIcon({ regime, size = 16 }: { regime: Regime; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", "aria-hidden": true as const, fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  if (regime === "forced") {
    // horizontal flow arrows
    return (
      <svg {...common}>
        <path d="M3 8h14M13 4l4 4-4 4M3 16h14M13 12l4 4-4 4" />
      </svg>
    );
  }
  if (regime === "buoyant") {
    // rising plume arrow
    return (
      <svg {...common}>
        <path d="M12 21V4M6 10l6-6 6 6" />
      </svg>
    );
  }
  // mixed: diagonal arrow from both
  return (
    <svg {...common}>
      <path d="M4 20L19 5M10 5h9v9" />
      <path d="M4 12h5" />
    </svg>
  );
}

export function RegimeBadge({ regime, large = false }: { regime: Regime; large?: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border-2 bg-surface font-semibold uppercase tracking-wide ${STYLE[regime]} ${
        large ? "px-3 py-1.5 text-lg" : "px-2 py-0.5 text-xs"
      }`}
      title={REGIME_LABEL[regime]}
      data-testid="regime-badge"
    >
      <RegimeIcon regime={regime} size={large ? 22 : 14} />
      {regime}
    </span>
  );
}
