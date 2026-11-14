"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useHabitat } from "@/lib/useHabitat";
import { AskButton } from "./AskDrawer";
import { ThemeToggle } from "./ThemeToggle";

export const NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/explore", label: "Spectrum" },
  { href: "/regime", label: "Regime" },
  { href: "/bounds", label: "Bounds" },
  { href: "/ledger", label: "Ledger" },
  { href: "/planner", label: "Planner" },
  { href: "/data", label: "Data" },
  { href: "/about", label: "About" },
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
          {NAV_ITEMS.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <li key={item.href}>
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
