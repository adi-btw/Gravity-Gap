"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useHabitat } from "@/lib/useHabitat";
import { AskButton } from "./AskDrawer";
import { ThemeToggle } from "./ThemeToggle";

export const NAV_ITEMS = [
  { href: "/", label: "Home", group: 0 },
  { href: "/replay", label: "Replay", group: 0 },
  { href: "/explore", label: "Spectrum", group: 0 },
  { href: "/regime", label: "Regime", group: 0 },
  { href: "/bounds", label: "Bounds", group: 1 },
  { href: "/compare", label: "Compare", group: 1 },
  { href: "/atmospheres", label: "Air map", group: 1 },
  { href: "/briefing", label: "Briefing", group: 1 },
  { href: "/trust", label: "Trust", group: 1 },
  { href: "/suppression", label: "Put it out", group: 2 },
  { href: "/detection", label: "Detection", group: 2 },
  { href: "/ledger", label: "Ledger", group: 3 },
  { href: "/planner", label: "Planner", group: 3 },
  { href: "/data", label: "Data", group: 3 },
  { href: "/about", label: "About", group: 3 },
] as const;

/** Top navigation; links carry the habitat query so state follows the user. */
export function SiteNav() {
  const pathname = usePathname();
  const { queryString } = useHabitat();
  return (
    <div className="mx-auto max-w-6xl px-4 pt-3 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
        <Link href={`/?${queryString}`} className="flex items-baseline gap-2 text-fg">
          <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" className="self-center">
            <circle cx="12" cy="12" r="10.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
            <path d="M12 5c2 3 3 5 3 7a3 3 0 0 1-6 0c0-2 1-4 3-7z" fill="var(--accent)" />
          </svg>
          <span className="font-display text-[1.35rem] font-medium leading-none tracking-[-0.01em]">Gravity Gap</span>
        </Link>
        <div className="flex items-center gap-2">
          <AskButton />
          <ThemeToggle />
        </div>
      </div>
      <nav aria-label="Main" className="mt-2 border-t border-line">
        <ul className="-mx-1.5 flex flex-wrap items-center gap-x-0.5 text-[13px]">
          {NAV_ITEMS.map((item, k) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            // A thin rule between groups (story · habitat answers · fire response · records) keeps the long nav scannable.
            const newGroup = k > 0 && NAV_ITEMS[k - 1].group !== item.group;
            return (
              <li key={item.href} className={newGroup ? "ml-2 border-l border-line pl-2" : undefined}>
                <Link
                  href={`${item.href}?${queryString}`}
                  aria-current={active ? "page" : undefined}
                  className={`-mt-px block border-t-2 px-1.5 py-1.5 transition-colors ${
                    active ? "border-accent font-medium text-fg" : "border-transparent text-muted hover:text-fg"
                  }`}
                >
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
