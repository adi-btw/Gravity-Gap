"use client";

import { FIELDS, gFraction, matchPreset, nearestPresetAtmosphere, presetToHabitat } from "@/lib/habitat";
import { PRESETS } from "@/lib/presets";
import { useHabitat } from "@/lib/useHabitat";
import { NumberField } from "./NumberField";

/** FIELDS specs carry a `key` property; strip it so it is not spread as React's special `key` prop. */
function fieldProps<T extends { key: unknown }>(spec: T): Omit<T, "key"> {
  const { key: _ignored, ...rest } = spec;
  void _ignored;
  return rest;
}

/** Persistent habitat bar (F0): presets plus editable g · P · O₂ · vent · L, all stored in the URL. */
export function HabitatBar({ compact = false }: { compact?: boolean }) {
  const { habitat, setHabitat, setField } = useHabitat();
  const active = matchPreset(habitat);
  const sourcePreset = active ?? nearestPresetAtmosphere(habitat);

  return (
    <section aria-label="Habitat settings" className={`mx-auto max-w-6xl px-4 ${compact ? "py-0" : "py-3"}`}>
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Habitat presets">
        <span className="text-xs uppercase tracking-wider text-muted">Habitat</span>
        {PRESETS.map((p) => {
          const on = active?.id === p.id;
          return (
            <button
              key={p.id}
              type="button"
              aria-pressed={on}
              onClick={() => setHabitat(presetToHabitat(p))}
              className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                on ? "border-micro bg-surface-2 text-fg" : "border-line text-muted hover:text-fg"
              }`}
            >
              {p.label}
            </button>
          );
        })}
        {active ? null : (
          <span className="rounded-full border border-partial px-3 py-1 text-xs text-partial">Custom</span>
        )}
      </div>

      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-3">
        <NumberField
          {...fieldProps(FIELDS.g_m_s2)}
          value={habitat.g_m_s2}
          onChange={(v) => setField("g_m_s2", v)}
          hint={`= ${gFraction(habitat.g_m_s2).toFixed(3)} g (Earth)`}
        />
        <NumberField {...fieldProps(FIELDS.p_psia)} value={habitat.p_psia} onChange={(v) => setField("p_psia", v)} />
        <NumberField
          {...fieldProps(FIELDS.o2)}
          scale={100}
          decimals={1}
          value={habitat.o2}
          onChange={(v) => setField("o2", v)}
          hint={`mole fraction ${habitat.o2.toFixed(3)}`}
        />
        <NumberField
          {...fieldProps(FIELDS.u_cm_s)}
          value={habitat.u_cm_s}
          onChange={(v) => setField("u_cm_s", v)}
          tag="assumed, editable"
        />
        <NumberField
          {...fieldProps(FIELDS.L_mm)}
          value={habitat.L_mm}
          onChange={(v) => setField("L_mm", v)}
          tag="assumed, editable"
        />
      </div>

      <p className="mt-2 text-[11px] text-muted">
        <span className="font-medium">Source:</span>{" "}
        {sourcePreset
          ? `${sourcePreset.label}: ${sourcePreset.source}.`
          : "Custom values entered by the user."}{" "}
        Vent speed and flame size are engineering assumptions. The link in your address bar reproduces this habitat.
      </p>
    </section>
  );
}
