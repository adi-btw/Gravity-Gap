"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { StoryData } from "./data";

type Vars = CSSProperties & Record<`--${string}`, string | number>;

/**
 * The signature move: Fig. 6, the lunar base metric by metric. The press prints M1 and M3, then tries M2 while a
 * needle measures how far the lunar-base air is from the nearest tested air. When the needle crosses the honesty
 * gate the press stops and stamps the field. Scroll drives --press (from the act's --sc-p); "Try to print M2
 * again" drives it on a clock. Every value and distance comes from artifacts/bounds/lunar_base_M*.json.
 */
export function RefusalPress({ data }: { data: StoryData }) {
  const { m2, rows, lunarBase } = data;
  const pressRef = useRef<HTMLDivElement>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const frame = useRef(0);

  useEffect(() => () => cancelAnimationFrame(frame.current), []);

  function replay() {
    const el = pressRef.current;
    if (!el) return;
    cancelAnimationFrame(frame.current);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setStatus("");
    if (reduce) {
      setStatus(`Tried again. Distance ${m2.distance.toFixed(2)} is past the gate at ${m2.gate.toFixed(2)}: no evidence, so no number.`);
      return;
    }
    setBusy(true);
    const t0 = performance.now();
    const DUR = 2600;
    const step = (now: number) => {
      const t = Math.min(1, (now - t0) / DUR);
      // Ease out so the needle slows as it approaches the gate, the way a real gauge settles.
      const e = 1 - Math.pow(1 - t, 2.2);
      el.style.setProperty("--press", (0.18 + e * 0.82).toFixed(4));
      if (t < 1) {
        frame.current = requestAnimationFrame(step);
      } else {
        el.style.removeProperty("--press");
        setBusy(false);
        setStatus(`Tried again. Distance ${m2.distance.toFixed(2)} is past the gate at ${m2.gate.toFixed(2)}: no evidence, so no number.`);
      }
    };
    frame.current = requestAnimationFrame(step);
  }

  // Gauge geometry: 0 to 3 atmosphere-distance units across x 24..576.
  const X0 = 24;
  const X1 = 576;
  const MAX = 3;
  const xOf = (d: number) => X0 + (d / MAX) * (X1 - X0);
  const run = xOf(m2.distance) - X0;

  return (
    <div className="gg-press" ref={pressRef}>
      <div className="gg-wrap gg-refusal__grid">
        <div className="gg-refusal__copy gg-stack">
          <h2 id="refusal-title" className="gg-h2">
            Where the evidence stops, the numbers stop.
          </h2>
          <p className="gg-soft">
            Before it prints anything, the engine measures how far the habitat&apos;s air is from the nearest air that was
            actually tested. Past a distance of <span className="gg-num">{m2.gate.toFixed(2)}</span> it prints nothing
            and names the nearest test instead.
          </p>
          <p className="gg-you">You scrolled for a number. There is no test close enough to print one.</p>
          <div>
            <button type="button" className="gg-again" onClick={replay} disabled={busy}>
              Try to print M2 again
            </button>
            <p className="gg-status" role="status" aria-live="polite">
              {status}
            </p>
          </div>
        </div>

        <figure aria-labelledby="refusal-fig">
          <table className="gg-metrics">
            <caption id="refusal-fig">
              <span className="gg-fig-no">Fig. 6</span>
              <span className="gg-label" style={{ textTransform: "none", letterSpacing: "0.01em" }}>
                Lunar base ({data.g.moon} m/s², {lunarBase.p_psia} psia, {lunarBase.o2Pct}% O₂): five fire metrics
              </span>
            </caption>
            <thead>
              <tr>
                <th scope="col">Metric</th>
                <th scope="col" className="gg-col-what">What it estimates</th>
                <th scope="col">Value</th>
                <th scope="col">90% band</th>
                <th scope="col" className="gg-col-conf">Transfer</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.metric} className={r.metric === "M2" ? "gg-row-m2" : undefined}>
                  <th scope="row">{r.metric}</th>
                  <td className="gg-col-what">{r.label}</td>
                  <td className="gg-val">
                    {r.value ? (
                      <span className="gg-print">{r.value}</span>
                    ) : (
                      <span className={`gg-nil ${r.metric === "M2" ? "gg-nil--m2" : "gg-nil--late"}`}>No evidence</span>
                    )}
                  </td>
                  <td className="gg-val">{r.band ? <span className="gg-print">{r.band}</span> : <span className="gg-soft">none</span>}</td>
                  <td className="gg-col-conf">{r.confidence}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="gg-instr" data-testid="refusal-instrument">
            <p className="gg-label" id="m2-field-label">
              M2 · droplet extinction diameter at the lunar base
            </p>
            <div className="gg-field" role="group" aria-labelledby="m2-field-label">
              <span className="gg-field__slot" aria-hidden="true">
                <span className="gg-field__caret" />
              </span>
              <span className="gg-field__unit" aria-hidden="true">mm</span>
              <span className="gg-field__strike" aria-hidden="true" />
              <span className="gg-stamp" data-testid="refusal-stamp">No evidence</span>
            </div>
            <div className="gg-gauge">
              <svg viewBox="0 0 600 92" role="img" aria-labelledby="gauge-t gauge-d" style={{ "--run": run } as Vars}>
                <title id="gauge-t">Distance from the lunar-base air to the nearest tested air</title>
                <desc id="gauge-d">
                  {`Lunar-base air is ${lunarBase.o2Pct}% O2 at ${m2.queryAtm.toFixed(2)} atm. The nearest M2 test is ${m2.nearestInvestigation} ${m2.nearestId}, ${m2.nearestO2Pct.toFixed(0)}% O2 at ${m2.nearestAtm.toFixed(2)} atm, at a distance of ${m2.distance.toFixed(2)}. The honesty gate is ${m2.gate.toFixed(2)}, so no value is printed.`}
                </desc>
                <defs>
                  <pattern id="gg-hatch-g" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                    <line x1="0" y1="0" x2="0" y2="7" stroke="var(--s-warn)" strokeWidth="1.6" strokeOpacity="0.55" />
                  </pattern>
                </defs>
                <rect className="gg-beyond" x={xOf(m2.gate)} y={44} width={X1 - xOf(m2.gate)} height={16} fill="url(#gg-hatch-g)" />
                <line x1={X0} x2={X1} y1={60} y2={60} stroke="var(--s-ink)" strokeWidth="1.25" />
                {[0, 0.5, 1, 1.5, 2, 2.5, 3].map((t) => (
                  <g key={t}>
                    <line x1={xOf(t)} x2={xOf(t)} y1={60} y2={t % 1 === 0 ? 68 : 65} stroke="var(--s-soft)" />
                    {t % 1 === 0 ? (
                      <text x={xOf(t)} y={84} textAnchor="middle" fontSize="13" fill="var(--s-soft)">
                        {t}
                      </text>
                    ) : null}
                  </g>
                ))}
                <line x1={xOf(m2.gate)} x2={xOf(m2.gate)} y1={22} y2={68} stroke="var(--s-warn)" strokeWidth="2" />
                <text x={xOf(m2.gate) - 6} y={18} textAnchor="end" fontSize="13" fill="var(--s-warn)">
                  gate {m2.gate.toFixed(2)}
                </text>
                <g className="gg-nearest">
                  <path d={`M ${xOf(m2.distance)} 52 l 6 8 l -6 8 l -6 -8 z`} fill="var(--s-ink)" />
                  <text x={xOf(m2.distance) + 10} y={40} fontSize="13" fill="var(--s-ink)">
                    {m2.distance.toFixed(2)}
                  </text>
                </g>
                <g className="gg-needle">
                  <line x1={X0} x2={X0} y1={30} y2={60} stroke="var(--s-flame)" strokeWidth="2.5" />
                  <path d={`M ${X0} 60 l -6 -9 h 12 z`} fill="var(--s-flame)" />
                </g>
              </svg>
              <p className="gg-gauge__notes">
                <span>
                  Lunar-base air: {lunarBase.o2Pct}% O₂, {m2.queryAtm.toFixed(2)} atm
                </span>
                <span>
                  Nearest test: {m2.nearestInvestigation} {m2.nearestId.split(":").slice(1).join(" test ")},{" "}
                  {m2.nearestO2Pct.toFixed(0)}% O₂, {m2.nearestAtm.toFixed(2)} atm
                </span>
              </p>
            </div>
          </div>
        </figure>
      </div>
    </div>
  );
}
