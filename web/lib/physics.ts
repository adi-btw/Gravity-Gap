/**
 * Gravity Gap core physics (E1): a function-for-function port of engine/physics.py.
 * Parity with Python is checked against tests/fixtures/physics_reference.json.
 *
 * Units (plan/contracts.md): g in m/s², pressure in psia (atmosphereDistance takes atm),
 * O₂ as a mole fraction, speeds in cm/s, sizes in mm.
 * Every output is an order-of-magnitude scaling estimate, not a resolved flame simulation.
 */

export const G0 = 9.81;
export const P0_PSIA = 14.7;
export const PSIA_PER_ATM = 14.696;

export const RI_FORCED_MAX = 0.1;
export const RI_BUOYANT_MIN = 10.0;

const X_SCALE = 0.05;
const LNP_SCALE = 0.3;

export type Regime = "forced" | "mixed" | "buoyant";

function requireNonNegative(name: string, value: number): void {
  if (Number.isNaN(value) || value < 0) {
    throw new RangeError(`${name} must be a non-negative number, got ${value}`);
  }
}

/** u_b = C_b · sqrt(g · L · ΔT/T), L converted to metres inside, result in cm/s. g = 0 → 0. */
export function buoyantVelocityCmS(
  g_m_s2: number,
  L_mm: number,
  dT_over_T = 4.0,
  C_b = 1.0,
): number {
  requireNonNegative("g_m_s2", g_m_s2);
  requireNonNegative("L_mm", L_mm);
  requireNonNegative("dT_over_T", dT_over_T);
  requireNonNegative("C_b", C_b);
  if (g_m_s2 === 0 || L_mm === 0) return 0;
  const L_m = L_mm / 1000.0;
  return C_b * Math.sqrt(g_m_s2 * L_m * dT_over_T) * 100.0;
}

/** Ri = u_b² / u_f². u_b = 0 → 0 (even if u_f = 0); u_f = 0 and u_b > 0 → Infinity. */
export function richardson(u_b_cm_s: number, u_f_cm_s: number): number {
  requireNonNegative("u_b_cm_s", u_b_cm_s);
  requireNonNegative("u_f_cm_s", u_f_cm_s);
  if (u_b_cm_s === 0) return 0;
  if (u_f_cm_s === 0) return Infinity;
  return (u_b_cm_s * u_b_cm_s) / (u_f_cm_s * u_f_cm_s);
}

/** "forced" (Ri < 0.1) | "mixed" (0.1 ≤ Ri ≤ 10) | "buoyant" (Ri > 10, including ∞). */
export function regime(ri: number): Regime {
  if (Number.isNaN(ri) || ri < 0) {
    throw new RangeError(`ri must be a non-negative number, got ${ri}`);
  }
  if (ri < RI_FORCED_MAX) return "forced";
  if (ri > RI_BUOYANT_MIN) return "buoyant";
  return "mixed";
}

/** G* = (g/G0) · (p/P0_PSIA)². Valid for laminar buoyant flow structure only. */
export function gStar(g_m_s2: number, p_psia: number): number {
  requireNonNegative("g_m_s2", g_m_s2);
  requireNonNegative("p_psia", p_psia);
  return (g_m_s2 / G0) * (p_psia / P0_PSIA) ** 2;
}

/** p_O₂ = X_O₂ · P in psia. */
export function o2PartialPressurePsia(o2: number, p_psia: number): number {
  requireNonNegative("o2", o2);
  requireNonNegative("p_psia", p_psia);
  if (o2 > 1) throw new RangeError(`o2 is a mole fraction in [0, 1], got ${o2}`);
  return o2 * p_psia;
}

/** Bridge model u_eff = sqrt(u_f² + (k · u_b)²), cm/s. */
export function effectiveFlowCmS(u_f_cm_s: number, u_b_cm_s: number, k = 1.0): number {
  requireNonNegative("u_f_cm_s", u_f_cm_s);
  requireNonNegative("u_b_cm_s", u_b_cm_s);
  requireNonNegative("k", k);
  const kb = k * u_b_cm_s;
  return Math.sqrt(u_f_cm_s * u_f_cm_s + kb * kb);
}

/** d = sqrt(((X − X_t)/0.05)² + ((ln P − ln P_t)/0.3)²), pressures in atm (> 0). */
export function atmosphereDistance(
  o2: number,
  p_atm: number,
  o2_t: number,
  p_t_atm: number,
): number {
  if (p_atm <= 0 || p_t_atm <= 0) {
    throw new RangeError("pressures must be > 0 atm for atmosphereDistance");
  }
  const dx = (o2 - o2_t) / X_SCALE;
  const dp = (Math.log(p_atm) - Math.log(p_t_atm)) / LNP_SCALE;
  return Math.sqrt(dx * dx + dp * dp);
}

export interface Evaluation {
  u_b_cm_s: number;
  /** null means Ri = ∞ (vent off under gravity), exactly as engine.physics.evaluate returns None. */
  ri: number | null;
  regime: Regime;
  g_star: number;
  p_o2_psia: number;
  u_eff_cm_s: number;
}

export function evaluate(
  g_m_s2: number,
  p_psia: number,
  o2: number,
  u_cm_s: number,
  L_mm: number,
  dT_over_T = 4.0,
  C_b = 1.0,
  k = 1.0,
): Evaluation {
  const u_b = buoyantVelocityCmS(g_m_s2, L_mm, dT_over_T, C_b);
  const ri = richardson(u_b, u_cm_s);
  return {
    u_b_cm_s: u_b,
    ri: Number.isFinite(ri) ? ri : null,
    regime: regime(ri),
    g_star: gStar(g_m_s2, p_psia),
    p_o2_psia: o2PartialPressurePsia(o2, p_psia),
    u_eff_cm_s: effectiveFlowCmS(u_cm_s, u_b, k),
  };
}
