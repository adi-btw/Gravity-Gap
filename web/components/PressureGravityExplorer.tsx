"use client";

import { gStar, o2PartialPressurePsia } from "@/lib/physics";
import { fmtSig } from "@/lib/format";
import { gFraction, type Habitat } from "@/lib/habitat";
import { PRESETS } from "@/lib/presets";
import { CaveatBanner } from "./CaveatBanner";
import { GStarMap, type Marker } from "./charts/GStarMap";

const MARKERS: Marker[] = [
  { id: "iss", label: "ISS", g: 0, p: 14.7 },
  { id: "exploration", label: "Exploration", g: 0, p: 10.2 },
  { id: "lunar", label: "Moon base/rover", g: 1.62, p: 8.2, above: true },
  { id: "mars", label: "Mars base", g: 3.71, p: 8.2 },
  { id: "earth", label: "Earth", g: 9.81, p: 14.7 },
];

/** F3 Pressure × Gravity Explorer: G* heat map, p_O₂ table and the always-visible caveat. */
export function PressureGravityExplorer({ habitat }: { habitat: Habitat }) {
  const gs = gStar(habitat.g_m_s2, habitat.p_psia);
  return (
    <div className="space-y-5">
      <CaveatBanner>
        G* is valid for laminar buoyant flow structure only; radiation and chemistry do not scale this way.
      </CaveatBanner>

      <div className="grid gap-3 sm:grid-cols-3" aria-live="polite">
        <div className="rounded-md border border-line bg-surface p-3">
          <div className="text-xs text-muted">G* = (g/g₀)(P/P₀)² for your habitat</div>
          <div className="num mt-1 text-2xl">{fmtSig(gs, 3)}</div>
          <div className="mt-1 text-[11px] text-muted">
            {gFraction(habitat.g_m_s2).toFixed(3)} g × ({habitat.p_psia} / 14.7)²
          </div>
        </div>
        <div className="rounded-md border border-line bg-surface p-3">
          <div className="text-xs text-muted">O₂ partial pressure p_O₂</div>
          <div className="num mt-1 text-2xl">
            {o2PartialPressurePsia(habitat.o2, habitat.p_psia).toFixed(2)}
            <span className="ml-1 text-sm text-muted">psia</span>
          </div>
          <div className="mt-1 text-[11px] text-muted">Earth sea level: 3.09 psia</div>
        </div>
        <div className="rounded-md border border-line bg-surface p-3 text-sm">
          <div className="text-xs text-muted">Reading this</div>
          Buoyant flow strength scales as g·P², so a lunar cabin at 8.2 psia has about 5% of Earth&apos;s buoyancy.
          Ri does not depend on P; Gr and Re do.
        </div>
      </div>

      <figure className="rounded-md border border-line bg-surface p-3">
        <figcaption className="mb-2 text-sm font-medium">
          G* over gravity × pressure
          <span className="ml-2 text-xs font-normal text-muted">Diamonds: habitats. Ring: your habitat. Dashed: iso-G*.</span>
        </figcaption>
        <GStarMap markers={MARKERS} current={{ g: habitat.g_m_s2, p: habitat.p_psia }} />
      </figure>

      <div className="overflow-x-auto rounded-md border border-line bg-surface p-3">
        <table className="num w-full text-left text-xs">
          <caption className="mb-2 text-left font-sans text-sm font-medium text-fg">
            Oxygen partial pressure and G* per habitat preset
          </caption>
          <thead className="text-muted">
            <tr>
              <th scope="col" className="py-1 pr-3">Habitat</th>
              <th scope="col" className="py-1 pr-3">g (m/s²)</th>
              <th scope="col" className="py-1 pr-3">P (psia)</th>
              <th scope="col" className="py-1 pr-3">O₂ (%)</th>
              <th scope="col" className="py-1 pr-3">p_O₂ (psia)</th>
              <th scope="col" className="py-1">G*</th>
            </tr>
          </thead>
          <tbody>
            {PRESETS.map((p) => (
              <tr key={p.id} className="border-t border-line">
                <th scope="row" className="py-1 pr-3 font-sans font-normal">{p.label}</th>
                <td className="py-1 pr-3">{p.g_m_s2.toFixed(2)}</td>
                <td className="py-1 pr-3">{p.p_psia.toFixed(1)}</td>
                <td className="py-1 pr-3">{(p.o2 * 100).toFixed(1)}</td>
                <td className="py-1 pr-3">{o2PartialPressurePsia(p.o2, p.p_psia).toFixed(2)}</td>
                <td className="py-1">{gStar(p.g_m_s2, p.p_psia).toFixed(3)}</td>
              </tr>
            ))}
            <tr className="border-t-2 border-line font-semibold">
              <th scope="row" className="py-1 pr-3 font-sans">Your habitat</th>
              <td className="py-1 pr-3">{habitat.g_m_s2.toFixed(2)}</td>
              <td className="py-1 pr-3">{habitat.p_psia.toFixed(1)}</td>
              <td className="py-1 pr-3">{(habitat.o2 * 100).toFixed(1)}</td>
              <td className="py-1 pr-3">{o2PartialPressurePsia(habitat.o2, habitat.p_psia).toFixed(2)}</td>
              <td className="py-1">{gs.toFixed(3)}</td>
            </tr>
          </tbody>
        </table>
        <p className="mt-2 font-sans text-[11px] text-muted">
          Raising O₂ fraction while lowering pressure keeps p_O₂ near sea level for breathing, but higher O₂ mole
          fraction raises flammability. The X_O₂ vs P flammability overlay arrives in phase 2.
        </p>
      </div>
    </div>
  );
}
