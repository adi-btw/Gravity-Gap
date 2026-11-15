"use client";

import { useMemo } from "react";
import { evaluate, RI_BUOYANT_MIN, RI_FORCED_MAX, regime, richardson, buoyantVelocityCmS } from "@/lib/physics";
import { fmt, fmtSig, REGIME_EVIDENCE, REGIME_LABEL } from "@/lib/format";
import { gFraction, type Habitat } from "@/lib/habitat";
import { RegimeMap, ventForRi } from "./charts/RegimeMap";
import { RegimeBadge } from "./RegimeBadge";

function Stat({ label, value, unit, sub, testId }: { label: string; value: string; unit?: string; sub?: string; testId?: string }) {
  return (
    <div className="panel-tight">
      <div className="text-xs text-muted">{label}</div>
      <div className="num mt-1 text-2xl" data-testid={testId}>
        {value}
        {unit ? <span className="ml-1 text-sm text-muted">{unit}</span> : null}
      </div>
      {sub ? <div className="mt-1 text-[11px] text-muted">{sub}</div> : null}
    </div>
  );
}

/** F2 Flame Regime Calculator: u_b, Ri, regime badge and regime map, all computed client-side. */
export function RegimeCalculator({ habitat }: { habitat: Habitat }) {
  const { g_m_s2: g, p_psia, o2, u_cm_s: u, L_mm: L } = habitat;
  const e = useMemo(() => evaluate(g, p_psia, o2, u, L), [g, p_psia, o2, u, L]);

  const rows = useMemo(
    () =>
      [1, 3, 10, 30, 100].map((l) => {
        const ub = buoyantVelocityCmS(g, l);
        const ri = richardson(ub, u);
        return {
          L: l,
          ub,
          uBuoyant: ventForRi(g, l, RI_BUOYANT_MIN),
          uForced: ventForRi(g, l, RI_FORCED_MAX),
          ri,
          regime: regime(ri),
        };
      }),
    [g, u],
  );

  const toForced = ventForRi(g, L, RI_FORCED_MAX);
  const lunar = g > 1 && g < 2.5;

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-live="polite">
        <div className="flex flex-col justify-center panel-tight">
          <div className="text-xs text-muted">Flame regime</div>
          <div className="mt-2">
            <RegimeBadge regime={e.regime} large />
          </div>
          <div className="mt-2 text-[11px] text-muted">{REGIME_LABEL[e.regime]}</div>
        </div>
        <Stat label="Buoyant velocity u_b" value={fmt(e.u_b_cm_s, 2)} unit="cm/s" sub={`at ${gFraction(g).toFixed(3)} g, L = ${L} mm, ΔT/T = 4`} />
        <Stat
          label="Richardson number Ri = u_b² / u_f²"
          value={fmtSig(e.ri, 3)}
          testId="stat-ri"
          sub={e.ri === null ? "vent off under gravity: Ri → ∞" : "forced < 0.1 ≤ mixed ≤ 10 < buoyant"}
        />
        <Stat label="Effective flow u_eff" value={fmt(e.u_eff_cm_s, 2)} unit="cm/s" sub="bridge to microgravity data (k = 1)" />
      </div>

      <p className="rounded-md border border-line bg-surface-2 p-3 text-sm">
        <span className="font-medium">Which evidence applies: </span>
        {REGIME_EVIDENCE[e.regime]}{" "}
        {g > 0 && e.regime !== "forced"
          ? `Raising the vent above ${fmt(toForced, 1)} cm/s would put a ${L} mm flame in the forced regime, where ISS data transfers.`
          : null}
      </p>

      <aside className="rounded-md border-l-4 border-partial bg-surface p-3 text-sm" aria-label="Insight">
        <span className="font-medium text-partial">Insight: </span>
        At lunar gravity with 5–15 cm/s ventilation, typical cabin flames sit in the mixed regime, the least-tested
        condition.
        {g > 0
          ? ` At ${gFraction(g).toFixed(3)} g, a ${L} mm flame is mixed for vent speeds from ${fmt(ventForRi(g, L, RI_BUOYANT_MIN), 1)} to ${fmt(toForced, 1)} cm/s.`
          : " In orbit (g = 0) there is no buoyancy, so every flame is forced-flow dominated."}
        {lunar && e.regime === "mixed" ? " Your current habitat is one of them." : ""}
      </aside>

      <figure className="panel-tight">
        <figcaption className="mb-2 text-sm font-medium">
          <span className="fig-no">Fig. 1 ·</span>
          Regime map at g = {g.toFixed(2)} m/s² ({gFraction(g).toFixed(3)} g)
          <span className="ml-2 text-xs font-normal text-muted">
            Dashed lines: Ri = 10 (ochre) and Ri = 0.1 (blue). C_b = 1, ΔT/T = 4.
          </span>
        </figcaption>
        <RegimeMap g={g} u={u} L={L} />
        <div className="mt-2 flex flex-wrap gap-4 text-xs text-muted" aria-hidden="true">
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-sm bg-[var(--normal-fill)] ring-1 ring-normal" /> buoyant
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-sm bg-[var(--partial-fill)] ring-1 ring-partial" /> mixed
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-sm bg-[var(--micro-fill)] ring-1 ring-micro" /> forced
          </span>
        </div>
      </figure>

      <details className="panel-tight" open>
        <summary className="cursor-pointer text-sm font-medium">Data table: regime values at this gravity</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="num w-full text-left text-xs">
            <caption className="sr-only">
              Buoyant velocity, regime boundary vent speeds and regime at the current vent speed of {u} cm/s, by flame size
            </caption>
            <thead className="text-muted">
              <tr>
                <th scope="col" className="py-1 pr-3">L (mm)</th>
                <th scope="col" className="py-1 pr-3">u_b (cm/s)</th>
                <th scope="col" className="py-1 pr-3">Buoyant below u_f (Ri = 10)</th>
                <th scope="col" className="py-1 pr-3">Forced above u_f (Ri = 0.1)</th>
                <th scope="col" className="py-1 pr-3">Ri at u_f = {u}</th>
                <th scope="col" className="py-1">Regime</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.L} className="border-t border-line">
                  <th scope="row" className="py-1 pr-3 font-normal">{r.L}</th>
                  <td className="py-1 pr-3">{fmt(r.ub, 2)}</td>
                  <td className="py-1 pr-3">{fmt(r.uBuoyant, 2)}</td>
                  <td className="py-1 pr-3">{fmt(r.uForced, 2)}</td>
                  <td className="py-1 pr-3">{fmtSig(r.ri, 3)}</td>
                  <td className="py-1">{r.regime}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
