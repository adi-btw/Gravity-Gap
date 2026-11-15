"use client";

import Link from "next/link";
import { briefingQuery } from "@/lib/briefing";
import { FIELDS, gFraction, matchPreset, nearestPresetAtmosphere, presetToHabitat } from "@/lib/habitat";
import { incidentHabitat, incidentYear, matchIncident } from "@/lib/incidents";
import { PRESETS } from "@/lib/presets";
import type { Incident } from "@/lib/types";
import { useHabitat } from "@/lib/useHabitat";
import { useIncidents } from "@/lib/useIncidents";
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
  const incidentsState = useIncidents();
  // History chips: in-scope incidents only; the group is hidden when the incidents data is unavailable.
  const history: Incident[] =
    incidentsState.status === "ok"
      ? incidentsState.data.data.incidents.filter((i) => incidentHabitat(i) !== null)
      : [];
  // Several incidents can share one habitat (e.g. assumed sea-level air in orbit): all matching chips show pressed.
  const activeIncident = matchIncident(habitat, history);
  const activeIds = new Set(history.filter((i) => matchIncident(habitat, [i])).map((i) => i.id));

  return (
    <section aria-label="Habitat settings" className={`mx-auto max-w-6xl px-4 sm:px-6 ${compact ? "py-0" : "pb-3 pt-2"}`}>
      <div className="flex flex-wrap items-center gap-1.5 border-t border-line pt-3" role="group" aria-label="Habitat presets">
        <span className="label-mono mr-2">Habitat</span>
        {PRESETS.map((p) => {
          const on = active?.id === p.id;
          return (
            <button
              key={p.id}
              type="button"
              aria-pressed={on}
              onClick={() => setHabitat(presetToHabitat(p))}
              className={`chip ${on ? "chip-on" : ""}`}
            >
              {p.label}
            </button>
          );
        })}
        {active || activeIncident ? null : (
          <span className="chip border-partial text-partial">Custom</span>
        )}
        <Link
          href={`/briefing?${briefingQuery(habitat)}`}
          className="btn ml-auto"
          data-testid="briefing-button"
        >
          <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M3 1.5h7l3 3v10H3z M10 1.5v3h3 M5 8h6 M5 10.5h6 M5 13h4" fill="none" stroke="currentColor" strokeWidth="1.3" />
          </svg>
          Briefing
        </Link>
      </div>

      {history.length > 0 ? (
        <div className="mt-2 flex flex-wrap items-center gap-1.5" role="group" aria-label="Real fire incidents">
          <span className="label-mono mr-2">History</span>
          {history.map((inc) => {
            const h = incidentHabitat(inc);
            const on = activeIds.has(inc.id);
            return (
              <button
                key={inc.id}
                type="button"
                aria-pressed={on}
                onClick={() => h && setHabitat(h)}
                title={`${inc.name} (${inc.date}): ${inc.phase}`}
                className={`chip border-dashed ${on ? "chip-on" : ""}`}
              >
                {inc.name} <span className="num">{incidentYear(inc.date)}</span>
              </button>
            );
          })}
        </div>
      ) : null}

      <div className="mt-3 grid grid-cols-2 border-l border-t border-line sm:grid-cols-3 lg:grid-cols-5">
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

      <p className="mt-2 max-w-[100ch] text-[11px] leading-relaxed text-muted">
        <span className="font-medium">Source:</span>{" "}
        {sourcePreset
          ? `${sourcePreset.label}: ${sourcePreset.source}.`
          : activeIncident
            ? `${activeIncident.name} (${activeIncident.date}): values and sources on the Replay page.`
            : "Custom values entered by the user."}{" "}
        Vent speed and flame size are engineering assumptions. The link in your address bar reproduces this habitat.
      </p>
    </section>
  );
}
