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
