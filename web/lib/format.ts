import type { Regime } from "./physics";

export function fmt(n: number | null, digits = 2): string {
  if (n === null || !Number.isFinite(n)) return "∞";
  return n.toFixed(digits);
}

/** Significant-figure formatting for values spanning orders of magnitude (Ri, G*). */
export function fmtSig(n: number | null, sig = 3): string {
  if (n === null || !Number.isFinite(n)) return "∞";
  if (n === 0) return "0";
  const abs = Math.abs(n);
  if (abs >= 1e4 || abs < 1e-3) return n.toExponential(sig - 1);
  return Number(n.toPrecision(sig)).toString();
}

export const REGIME_LABEL: Record<Regime, string> = {
  forced: "Forced-flow dominated",
  mixed: "Mixed convection",
  buoyant: "Buoyancy dominated",
};

export const REGIME_EVIDENCE: Record<Regime, string> = {
  forced:
    "Microgravity tests at matching forced flow (BASS, SAFFIRE, SPICE) transfer well.",
  mixed:
    "Neither 0 g nor 1 g data alone applies. This is the least-tested condition and has the highest uncertainty.",
  buoyant: "Normal-gravity behavior is the better guide, with a pressure correction.",
};

/** "complete_burn" -> "complete burn". */
export function humanize(s: string): string {
  return s.replace(/_/g, " ");
}

/** Format a bounds estimate by metric kind: probabilities as %, quantities with unit, categories as words. */
export function fmtEstimate(v: number | string | null | undefined, kind: string, unit?: string | null): string {
  if (v === null || v === undefined) return "–";
  if (typeof v === "string") return humanize(v);
  if (!Number.isFinite(v)) return "–";
  if (kind === "probability" || unit === "fraction" || unit === "probability") return `${(v * 100).toFixed(v < 0.1 && v > 0 ? 1 : 0)}%`;
  return `${fmtSig(v, 3)}${unit && unit !== "category" ? ` ${unit}` : ""}`;
}

export function fmtBand(b: readonly (number | string)[] | null | undefined, kind: string, unit?: string | null): string {
  if (!b) return "–";
  const [lo, hi] = b;
  if (typeof lo === "string" || typeof hi === "string") {
    return lo === hi ? humanize(String(lo)) : `${humanize(String(lo))} … ${humanize(String(hi))}`;
  }
  return `${fmtEstimate(lo, kind, null)} – ${fmtEstimate(hi, kind, unit)}`;
}
