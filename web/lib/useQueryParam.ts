"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useCallback } from "react";

/** A single page-local URL query value (e.g. ?metric=M3), kept alongside the habitat query. */
export function useQueryParam(name: string, fallback: string): [string, (v: string | null) => void] {
  const sp = useSearchParams();
  const pathname = usePathname();
  const value = sp.get(name) ?? fallback;
  const set = useCallback(
    (v: string | null) => {
      const q = new URLSearchParams(sp.toString());
      if (v === null || v === "") q.delete(name);
      else q.set(name, v);
      window.history.replaceState(null, "", `${pathname}?${q.toString()}`);
    },
    [sp, pathname, name],
  );
  return [value, set];
}
