"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";
import { clampField, habitatFromQuery, habitatToQuery, type Habitat, type HabitatKey } from "./habitat";

/**
 * Habitat state lives in the URL query so every link is shareable.
 * Updates use window.history.replaceState, which Next.js (14.1+) syncs into
 * useSearchParams without a server round-trip, so physics panels update instantly.
 */
export function useHabitat() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const habitat = useMemo(() => habitatFromQuery(searchParams), [searchParams]);

  const setHabitat = useCallback(
    (next: Habitat) => {
      const q = habitatToQuery(next, new URLSearchParams(searchParams.toString()));
      window.history.replaceState(null, "", `${pathname}?${q.toString()}`);
    },
    [pathname, searchParams],
  );

  const setField = useCallback(
    (key: HabitatKey, value: number) => {
      setHabitat({ ...habitat, [key]: clampField(key, value) });
    },
    [habitat, setHabitat],
  );

  return { habitat, setHabitat, setField, queryString: habitatToQuery(habitat).toString() };
}
