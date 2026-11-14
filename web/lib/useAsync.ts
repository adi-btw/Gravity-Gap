"use client";

import { useEffect, useRef, useState } from "react";

export type AsyncState<T> =
  | { status: "loading"; data?: undefined; error?: undefined }
  | { status: "ok"; data: T; error?: undefined }
  | { status: "error"; data?: undefined; error: Error };

/**
 * Run `fn` whenever `key` changes; stale results from an earlier key are dropped.
 * `fn` is read through a ref so callers can pass inline closures.
 */
export function useAsync<T>(fn: () => Promise<T>, key: string): AsyncState<T> & { reload: () => void } {
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const [nonce, setNonce] = useState(0);
  const [state, setState] = useState<{ key: string; s: AsyncState<T> }>({ key: "", s: { status: "loading" } });

  useEffect(() => {
    let alive = true;
    setState({ key, s: { status: "loading" } });
    fnRef
      .current()
      .then((data) => alive && setState({ key, s: { status: "ok", data } }))
      .catch((e: unknown) =>
        alive && setState({ key, s: { status: "error", error: e instanceof Error ? e : new Error(String(e)) } }),
      );
    return () => {
      alive = false;
    };
  }, [key, nonce]);

  const s: AsyncState<T> = state.key === key ? state.s : { status: "loading" };
  return { ...s, reload: () => setNonce((n) => n + 1) } as AsyncState<T> & { reload: () => void };
}
