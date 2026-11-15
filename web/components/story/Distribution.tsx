"use client";

import Link from "next/link";
import { matchPreset, presetToHabitat } from "@/lib/habitat";
import { evaluate } from "@/lib/physics";
import { PRESETS } from "@/lib/presets";
import { REGIME_LABEL, fmtSig } from "@/lib/format";
import { useHabitat } from "@/lib/useHabitat";

/** The one action, labelled the same everywhere on the page. */
export const CTA_LABEL = "Open the tool";

/**
 * The close: a distribution sheet. The reader marks which habitat their copy is for (the app's own preset state,
 * written to the URL exactly as the HabitatBar does), and one line of running text opens the tool on it.
 */
export function Distribution() {
  const { habitat, setHabitat, queryString } = useHabitat();
  const active = matchPreset(habitat);
  const e = evaluate(habitat.g_m_s2, habitat.p_psia, habitat.o2, habitat.u_cm_s, habitat.L_mm);
  return (
    <div className="gg-dist__grid">
      <div className="gg-stack">
        <h2 id="distribution-title" className="gg-h2">
          Choose the habitat for your copy
        </h2>
        <p className="gg-soft">
          Every page of the tool opens on the habitat you mark here, and the link in your address bar carries it, so
          the same report can be sent to someone else.
        </p>
        <p className="gg-cta-line">
          <Link className="gg-cta" href={`/bounds?${queryString}`}>
            {CTA_LABEL}
          </Link>
        </p>
        <p className="gg-soft">
          New to the problem?{" "}
          <Link href={`/replay?${queryString}`}>Start with a real fire</Link>: the conditions of real spacecraft
          fires, and what today&apos;s data can and cannot say about them.
        </p>
      </div>

      <div>
        <p className="gg-label" id="presets-label">
          Habitat for this copy
        </p>
        <div className="gg-presets" role="group" aria-label="Habitat presets" style={{ marginTop: "0.6rem" }}>
          {PRESETS.map((p) => {
            const on = active?.id === p.id;
            return (
              <button
                key={p.id}
                type="button"
                className="gg-preset"
                aria-pressed={on}
                onClick={() => setHabitat(presetToHabitat(p))}
              >
                <span className="gg-preset__box" aria-hidden="true" />
                <span className="gg-preset__name">{p.label}</span>
                <span className="gg-preset__vals" aria-hidden="true">
                  {p.g_m_s2} m/s² · {p.p_psia} psia · {+(p.o2 * 100).toFixed(1)}% O₂
                </span>
              </button>
            );
          })}
        </div>
        <p className="gg-readout" aria-live="polite">
          <strong>{active ? active.label : "Custom habitat"}</strong>: {REGIME_LABEL[e.regime].toLowerCase()} regime,
          Richardson number {fmtSig(e.ri, 3)} at a vent speed of {habitat.u_cm_s} cm/s (assumed, editable in the tool).
        </p>
      </div>
    </div>
  );
}
