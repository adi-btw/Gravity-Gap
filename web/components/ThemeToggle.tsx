"use client";

import { useSyncExternalStore } from "react";

type Theme = "dark" | "light";

function readTheme(): Theme {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

const listeners = new Set<() => void>();
function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function ThemeToggle() {
  const theme = useSyncExternalStore<Theme>(subscribe, readTheme, () => "dark");
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
      className="rounded border border-line px-2 py-1 text-xs text-muted hover:text-fg"
      aria-label={`Switch to ${next} theme`}
    >
      {theme === "dark" ? "Light theme" : "Dark theme"}
    </button>
  );
}
