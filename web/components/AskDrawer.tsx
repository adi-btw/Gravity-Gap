"use client";

import { createContext, Suspense, useCallback, useContext, useEffect, useId, useRef, useState } from "react";
import { api, type Sourced } from "@/lib/api";
import { matchPreset } from "@/lib/habitat";
import type { AskAnswer } from "@/lib/types";
import { useHabitat } from "@/lib/useHabitat";
import { AskAnswerView } from "./AskAnswer";
import { ErrorState, Loading } from "./ui/States";

interface OpenArgs {
  question?: string;
  contextIds?: string[];
}

const AskContext = createContext<{ open: (args?: OpenArgs) => void }>({ open: () => {} });

export function useAsk() {
  return useContext(AskContext);
}

/** Mirrors the pre-generated demo questions in artifacts/ai_cache.json, so they also work offline. */
const SUGGESTED = [
  "Why is the lunar base in the mixed regime?",
  "Why is the M1 band wide for the lunar base?",
  "What should LUCI test first?",
  "Is the lunar rover safer with the fans off?",
  "Which experiments matter most for a Mars base?",
  // R1 real-fire replay demo questions (cached per incident by the AI role).
  "What does Gravity Gap say about the Mir fire?",
  "What would Gravity Gap say about Apollo 1's cabin air?",
  "Is Apollo 13 in scope?",
  // R2 suppression calculator demo questions.
  "How much CO₂ would it take to put out a flame in ISS air?",
  "Why can't Gravity Gap answer suppression for the lunar base?",
  // S4 habitat compare demo question.
  "What changes between ISS and the lunar base?",
];

/**
 * Persistent "Ask" assistant (F7). Opened from the header button or from any page via useAsk().open(...).
 * The provider holds only open/prefill state; the panel reads the habitat from the URL inside its own Suspense
 * boundary so the provider does not force the whole layout into client-only rendering.
 */
export function AskProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<{ n: number; question: string; contextIds: string[] } | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);

  const open = useCallback((args?: OpenArgs) => {
    returnFocus.current = document.activeElement as HTMLElement | null;
    setSession((prev) => ({
      n: (prev?.n ?? 0) + 1,
      question: args?.question ?? prev?.question ?? "",
      contextIds: args?.contextIds ?? [],
    }));
  }, []);

  const close = useCallback(() => {
    setSession(null);
    returnFocus.current?.focus?.();
  }, []);

  return (
    <AskContext.Provider value={{ open }}>
      {children}
      {session ? (
        <Suspense fallback={null}>
          <AskPanel key={session.n} initialQuestion={session.question} contextIds={session.contextIds} onClose={close} />
        </Suspense>
      ) : null}
    </AskContext.Provider>
  );
}

function AskPanel({
  initialQuestion,
  contextIds,
  onClose: close,
}: {
  initialQuestion: string;
  contextIds: string[];
  onClose: () => void;
}) {
  const [question, setQuestion] = useState(initialQuestion);
  const [state, setState] = useState<
    { s: "idle" } | { s: "loading" } | { s: "ok"; r: Sourced<AskAnswer> } | { s: "error"; e: Error }
  >({ s: "idle" });
  const { habitat } = useHabitat();
  const preset = matchPreset(habitat);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const titleId = useId();

  useEffect(() => {
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      // Keep Tab focus inside the dialog.
      if (e.key === "Tab" && dialogRef.current) {
        const f = dialogRef.current.querySelectorAll<HTMLElement>("button, a[href], textarea, input, [tabindex='0']");
        if (!f.length) return;
        const first = f[0];
        const last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const q = question.trim();
    if (!q) return;
    setState({ s: "loading" });
    try {
      setState({ s: "ok", r: await api.ask(q, habitat, contextIds) });
    } catch (err) {
      setState({ s: "error", e: err instanceof Error ? err : new Error(String(err)) });
    }
  };

  return (
        <div className="fixed inset-0 z-40 flex justify-end print:hidden">
          <button type="button" aria-label="Close assistant" className="absolute inset-0 bg-[#0f1011]/40" onClick={close} tabIndex={-1} />
          <aside
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="relative flex h-full w-full max-w-md flex-col gap-3 overflow-y-auto border-l border-line bg-surface p-5"
          >
            <div className="flex items-center justify-between">
              <h2 id={titleId} className="font-display text-xl font-medium">
                Ask Gravity Gap
              </h2>
              <button type="button" onClick={close} className="rounded border border-line px-2 py-0.5 text-sm hover:bg-surface-2">
                Close <span className="sr-only">assistant</span>
              </button>
            </div>
            <p className="text-xs text-muted">
              Answers are grounded in the engine outputs and the PSI catalog. Every number must appear in the context
              and every claim carries a citation. Habitat context:{" "}
              <span className="num text-fg">
                {preset ? preset.label : "custom"} · g {habitat.g_m_s2} m/s² · {habitat.p_psia} psia · O₂{" "}
                {(habitat.o2 * 100).toFixed(1)}% · vent {habitat.u_cm_s} cm/s
              </span>
              {contextIds.length ? (
                <>
                  {" "}· context: <span className="num">{contextIds.join(", ")}</span>
                </>
              ) : null}
            </p>
            <form onSubmit={submit} className="space-y-2">
              <label htmlFor={`${titleId}-q`} className="text-xs font-medium text-muted">
                Your question
              </label>
              <textarea
                id={`${titleId}-q`}
                ref={inputRef}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void submit();
                }}
                rows={3}
                className="w-full rounded-sm border border-line bg-bg p-2 text-sm"
                placeholder="e.g. Why is this band wide?"
              />
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="submit"
                  disabled={!question.trim() || state.s === "loading"}
                  className="btn-primary"
                >
                  Ask
                </button>
                <span className="text-[11px] text-muted">Ctrl+Enter to send · Esc to close</span>
              </div>
              <div className="flex flex-wrap gap-1" aria-label="Suggested questions">
                {SUGGESTED.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setQuestion(s)}
                    className="rounded-sm border border-line px-2 py-0.5 text-[11px] text-muted hover:text-fg"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </form>
            <div aria-live="polite">
              {state.s === "loading" ? <Loading label="Thinking with the engine outputs…" /> : null}
              {state.s === "error" ? <ErrorState error={state.e} /> : null}
              {state.s === "ok" ? <AskAnswerView answer={state.r.data} source={state.r.source} note={state.r.note} /> : null}
            </div>
            <p className="mt-auto text-[11px] text-muted">
              Out of scope: rocket propulsion, certification decisions, anything not in the PSI data.
            </p>
          </aside>
        </div>
  );
}

export function AskButton() {
  const { open } = useAsk();
  return (
    <button
      type="button"
      onClick={() => open()}
      className="rounded-sm border border-line px-3 py-1 text-xs text-fg transition-colors hover:border-line-strong hover:bg-surface-2"
    >
      Ask
    </button>
  );
}
