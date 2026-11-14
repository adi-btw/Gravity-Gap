"use client";

import Link from "next/link";
import { evaluate } from "@/lib/physics";
import { matchPreset } from "@/lib/habitat";
import { useHabitat } from "@/lib/useHabitat";
import { fmt, fmtSig, REGIME_EVIDENCE } from "@/lib/format";
import { GapHero } from "./charts/GapHero";
import { RegimeBadge } from "./RegimeBadge";

export function HomePicker() {
  const { habitat, queryString } = useHabitat();
  const e = evaluate(habitat.g_m_s2, habitat.p_psia, habitat.o2, habitat.u_cm_s, habitat.L_mm);
  const preset = matchPreset(habitat);
  return (
    <>
      <figure className="rounded-lg border border-line bg-surface p-4">
        <figcaption className="mb-2 text-sm font-medium">The gap</figcaption>
        <GapHero currentG={habitat.g_m_s2} />
      </figure>

      <section aria-labelledby="quick-read" className="rounded-lg border border-line bg-surface p-4">
        <h2 id="quick-read" className="text-sm font-medium">
          Quick read for {preset ? preset.label : "your custom habitat"}
        </h2>
        <p className="mt-1 text-xs text-muted">Pick a habitat or edit the values in the bar above.</p>
        <div className="mt-3 flex flex-wrap items-center gap-4" aria-live="polite">
          <RegimeBadge regime={e.regime} large />
          <dl className="num grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
            <dt className="font-sans text-xs text-muted">u_b</dt>
            <dd>{fmt(e.u_b_cm_s, 1)} cm/s</dd>
            <dt className="font-sans text-xs text-muted">Ri</dt>
            <dd>{fmtSig(e.ri, 3)}</dd>
            <dt className="font-sans text-xs text-muted">G*</dt>
            <dd>{fmtSig(e.g_star, 3)}</dd>
            <dt className="font-sans text-xs text-muted">p_O₂</dt>
            <dd>{fmt(e.p_o2_psia, 2)} psia</dd>
          </dl>
        </div>
        <p className="mt-3 text-sm">{REGIME_EVIDENCE[e.regime]}</p>
        <Link
          href={`/regime?${queryString}`}
          className="mt-3 inline-block rounded-md border border-micro px-3 py-1.5 text-sm text-micro hover:bg-surface-2"
        >
          Open the regime calculator →
        </Link>
      </section>
    </>
  );
}
