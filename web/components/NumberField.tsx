"use client";

import { useId, useState } from "react";

interface Props {
  label: string;
  unit: string;
  value: number;
  min: number;
  max: number;
  step: number;
  /** Display scale, e.g. 100 to edit a mole fraction as a percent. */
  scale?: number;
  decimals: number;
  onChange: (value: number) => void;
  hint?: React.ReactNode;
  tag?: string;
}

/** Slider plus numeric input, both labelled, both keyboard operable (plan/06 §4). */
export function NumberField({ label, unit, value, min, max, step, scale = 1, decimals, onChange, hint, tag }: Props) {
  const id = useId();
  const shown = Number((value * scale).toFixed(decimals));
  // Draft text so partially typed numbers ("0.", "") are not clobbered; resync when the value changes elsewhere.
  const [draft, setDraft] = useState(String(shown));
  const [lastShown, setLastShown] = useState(shown);
  if (shown !== lastShown) {
    setLastShown(shown);
    setDraft(String(shown));
  }

  const commit = (text: string) => {
    const n = Number(text);
    if (text.trim() !== "" && Number.isFinite(n)) onChange(n / scale);
  };

  return (
    <div className="flex min-w-0 flex-col gap-1 border-b border-r border-line bg-surface px-3 py-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5">
        <label htmlFor={`${id}-num`} className="text-xs font-medium text-muted">
          {label} <span className="num font-normal">({unit})</span>
        </label>
        {tag ? (
          <span className="num whitespace-nowrap rounded-sm border border-dashed border-partial px-1 text-[10px] uppercase tracking-wide text-partial">
            {tag}
          </span>
        ) : null}
      </div>
      <div className="flex items-center gap-2">
        <input
          id={`${id}-range`}
          type="range"
          aria-label={`${label} slider (${unit})`}
          min={min * scale}
          max={max * scale}
          step={step * scale}
          value={shown}
          onChange={(e) => onChange(Number(e.target.value) / scale)}
          className="w-full min-w-0"
        />
        <input
          id={`${id}-num`}
          type="number"
          inputMode="decimal"
          min={min * scale}
          max={max * scale}
          step={step * scale}
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            commit(e.target.value);
          }}
          onBlur={() => setDraft(String(shown))}
          className="num w-[4.75rem] shrink-0 rounded-sm border border-line bg-bg px-1.5 py-0.5 text-right text-sm"
        />
      </div>
      {hint ? <div className="num text-[11px] text-muted">{hint}</div> : null}
    </div>
  );
}
