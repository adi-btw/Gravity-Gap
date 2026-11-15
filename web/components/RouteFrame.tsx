"use client";

import { usePathname } from "next/navigation";
import { HabitatBar } from "./HabitatBar";

/** The story page at "/" is full-bleed and carries its own habitat framing, so the app chrome steps aside there. */
function useIsStory() {
  return usePathname() === "/";
}

/** Habitat "test conditions" strip, shown on every route except the story page. */
export function HabitatSlot() {
  return useIsStory() ? null : <HabitatBar />;
}

/** Main content frame: the report measure on app routes, the full viewport width on the story page. */
export function MainFrame({ children }: { children: React.ReactNode }) {
  const story = useIsStory();
  return (
    <main
      id="main"
      data-frame={story ? "story" : "app"}
      className={story ? "w-full print:p-0" : "mx-auto max-w-6xl px-4 pb-10 pt-8 sm:px-6 print:max-w-none print:p-0"}
    >
      {children}
    </main>
  );
}

/** Footer line; on the story page it spans the same full width as the page. */
export function FooterFrame({ children }: { children: React.ReactNode }) {
  const story = useIsStory();
  return (
    <footer
      className={`border-t border-line print:hidden ${story ? "" : "mt-6"}`}
    >
      <div className="num mx-auto flex max-w-6xl flex-wrap gap-x-4 gap-y-1 px-4 py-5 text-[11px] text-muted sm:px-6">
        {children}
      </div>
    </footer>
  );
}
