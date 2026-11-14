"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useRef } from "react";
import { useHabitat } from "@/lib/useHabitat";
import { PressureGravityExplorer } from "./PressureGravityExplorer";
import { RegimeCalculator } from "./RegimeCalculator";

const TABS = [
  { id: "regime", label: "F2 · Flame regime" },
  { id: "pressure", label: "F3 · Pressure × gravity" },
] as const;
type TabId = (typeof TABS)[number]["id"];

/** /regime tabs; the active tab is kept in ?tab= so links stay shareable. */
export function RegimeTabs() {
  const { habitat } = useHabitat();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const tab: TabId = searchParams.get("tab") === "pressure" ? "pressure" : "regime";
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const select = (id: TabId, focus = false) => {
    const q = new URLSearchParams(searchParams.toString());
    q.set("tab", id);
    window.history.replaceState(null, "", `${pathname}?${q.toString()}`);
    if (focus) refs.current[id]?.focus();
  };

  return (
    <div>
      <div role="tablist" aria-label="Regime tools" className="mb-4 flex gap-1 border-b border-line">
        {TABS.map((t, i) => {
          const on = t.id === tab;
          return (
            <button
              key={t.id}
              ref={(el) => {
                refs.current[t.id] = el;
              }}
              role="tab"
              id={`tab-${t.id}`}
              aria-selected={on}
              aria-controls={`panel-${t.id}`}
              tabIndex={on ? 0 : -1}
              onClick={() => select(t.id)}
              onKeyDown={(e) => {
                if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                  const next = TABS[(i + (e.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length];
                  select(next.id, true);
                }
              }}
              className={`-mb-px rounded-t border-b-2 px-3 py-2 text-sm ${
                on ? "border-micro text-fg" : "border-transparent text-muted hover:text-fg"
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "regime" ? <RegimeCalculator habitat={habitat} /> : <PressureGravityExplorer habitat={habitat} />}
      </div>
    </div>
  );
}
