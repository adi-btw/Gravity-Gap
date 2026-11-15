"use client";

import { useSyncExternalStore } from "react";

type Theme = "dark" | "light";

function readTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

const listeners = new Set<() => void>();
function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function ThemeToggle() {
  const theme = useSyncExternalStore<Theme>(subscribe, readTheme, () => "light");
  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      onClick={() => {
        document.documentElement.dataset.theme = next;
        try {
          localStorage.setItem("gg-theme", next);
        } catch {
          // storage unavailable (private mode); theme still applies for this page view
        }
        listeners.forEach((l) => l());
      }}
      className="rounded-sm border border-line px-2 py-1 text-xs text-muted transition-colors hover:border-line-strong hover:text-fg"
      aria-label={`Switch to ${next} theme`}
    >
      {theme === "dark" ? "Light theme" : "Dark theme"}
    </button>
  );
}
