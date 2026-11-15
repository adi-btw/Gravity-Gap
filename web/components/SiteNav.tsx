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
    <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 pt-3">
      <Link href={`/?${queryString}`} className="flex items-center gap-2 font-semibold tracking-tight">
        <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="10" fill="none" stroke="var(--micro)" strokeWidth="2" />
          <path d="M12 5c2 3 3 5 3 7a3 3 0 0 1-6 0c0-2 1-4 3-7z" fill="var(--normal)" />
        </svg>
        <span>Gravity Gap</span>
      </Link>
      <nav aria-label="Main" className="flex-1">
        <ul className="flex flex-wrap gap-1 text-sm">
          {NAV_ITEMS.map((item, k) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            // A thin divider between groups (story · habitat answers · fire response · records) keeps the long nav scannable.
            const newGroup = k > 0 && NAV_ITEMS[k - 1].group !== item.group;
            return (
              <li key={item.href} className={newGroup ? "ml-1 border-l border-line pl-1" : undefined}>
                <Link
                  href={`${item.href}?${queryString}`}
                  aria-current={active ? "page" : undefined}
                  className={`rounded px-2 py-1 transition-colors ${
                    active ? "bg-surface-2 text-fg" : "text-muted hover:text-fg"
                  }`}
                >
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <AskButton />
      <ThemeToggle />
    </div>
  );
}
