import type { CSSProperties } from "react";
import type { StoryData } from "./data";

type Vars = CSSProperties & Record<`--${string}`, string | number>;

/**
 * Fig. 4, the peak: every combustion investigation in the PSI catalog placed on a gravity axis drawn to scale in
 * m/s². The scroll extends the axis through the empty span; the Moon and Mars then drop into it. All motion comes
 * from CSS vars in story.css (.gg-gap); the static state of this markup is the finished, true figure.
 * Two compositions: horizontal (desktop) and vertical (phone), switched in CSS.
 */
export function GapFigure({ data }: { data: StoryData }) {
  const { orbit, earth, g } = data;
  const desc =
    `Gravity axis from 0 to ${g.earth} m/s², drawn to scale. ${orbit.items.length} combustion investigations in NASA's PSI catalog ` +
    `were run in microgravity (${orbit.platforms.join(", ")}) and ${earth.items.length} have Earth-gravity data. ` +
    `${data.partialCount === 0 ? "None was" : `${data.partialCount} were`} run at any gravity in between. ` +
    `The Moon, ${g.moon} m/s², and Mars, ${g.mars} m/s², fall in that untested span.`;
  return (
    <>
      <Horizontal data={data} desc={desc} />
      <Vertical data={data} desc={desc} />
    </>
  );
}

const hatch = (id: string) => (
  <pattern id={id} width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
    <line x1="0" y1="0" x2="0" y2="9" stroke="var(--s-nodata)" strokeWidth="2.2" />
  </pattern>
);

function Horizontal({ data, desc }: { data: StoryData; desc: string }) {
  const { orbit, earth, g } = data;
  const X0 = 150;
  const X1 = 1090;
  const RUN = X1 - X0;
  const AY = 300;
  const xOf = (v: number) => X0 + (v / g.earth) * RUN;
  const markTop = (i: number) => AY - 14 - i * 10;
  const ticks = [1, 2, 3, 4, 5, 6, 7, 8, 9];
  return (
    <svg
      className="gg-gap__h"
      viewBox="0 0 1200 420"
      role="img"
      aria-labelledby="gg-gap-h-t gg-gap-h-d"
      style={{ "--ox": `${X0}px`, "--oy": `${AY}px`, "--run": RUN } as Vars}
    >
      <title id="gg-gap-h-t">Fig. 4: where NASA has tested fire, by gravity</title>
      <desc id="gg-gap-h-d">{desc}</desc>
      <defs>{hatch("gg-hatch-h")}</defs>

      {/* the run of the axis: hatch and line extend together with the scroll */}
      <g className="gg-axis-run">
        <rect x={X0 + 34} y={96} width={RUN - 68} height={AY - 100} fill="url(#gg-hatch-h)" />
        <line x1={X0} x2={X1} y1={AY} y2={AY} stroke="var(--s-ink)" strokeWidth="1.5" />
      </g>
      <text x={xOf(6.9)} y={190} textAnchor="middle" fontSize="15" fill="var(--s-ink)" className="gg-tick" style={{ "--at": 0.8 } as Vars}>
        No fire test at any gravity in this span
      </text>

      {/* scale */}
      <g fontSize="14" fill="var(--s-soft)">
        <line x1={X0} x2={X0} y1={AY} y2={AY + 8} stroke="var(--s-ink)" />
        <text x={X0} y={AY + 28} textAnchor="middle">0</text>
        {ticks.map((t) => (
          <g key={t} className="gg-tick" style={{ "--at": t / g.earth } as Vars}>
            <line x1={xOf(t)} x2={xOf(t)} y1={AY} y2={AY + 6} stroke="var(--s-soft)" />
            <text x={xOf(t)} y={AY + 28} textAnchor="middle">{t}</text>
          </g>
        ))}
        <text x={X1 + 18} y={AY + 28} textAnchor="start" fill="var(--s-ink)">{g.earth} m/s²</text>
      </g>

      {/* the travelling tip: what the line finds as it goes */}
      <g className="gg-tip">
        <line x1={X0} x2={X0} y1={AY - 26} y2={AY + 2} stroke="var(--s-flame)" strokeWidth="2" />
        <text x={X0 + 8} y={AY - 34} fontSize="17" fill="var(--s-flame)">0 tests here</text>
      </g>

      {/* orbit column: present from the first frame (the plate's ground) */}
      <g>
        {orbit.items.map((it, i) => (
          <rect key={it.id} x={X0 - 24} y={markTop(i)} width={48} height={7} fill="var(--s-micro)">
            <title>{it.name}</title>
          </rect>
        ))}
        <text x={X0} y={AY + 58} textAnchor="middle" fontSize="14" fill="var(--s-micro)">Orbit, ~0</text>
        <text x={X0} y={AY + 78} textAnchor="middle" fontSize="13" fill="var(--s-soft)">
          {orbit.items.length} investigations
        </text>
      </g>

      {/* Earth column: arrives when the line does */}
      <g className="gg-earthcol">
        {earth.items.map((it, i) => (
          <rect key={it.id} x={X1 - 24} y={markTop(i)} width={48} height={7} fill="var(--s-normal)">
            <title>{it.name}</title>
          </rect>
        ))}
        <text x={X1} y={AY + 58} textAnchor="middle" fontSize="14" fill="var(--s-normal)">Earth, 1 g</text>
        <text x={X1} y={AY + 78} textAnchor="middle" fontSize="13" fill="var(--s-soft)">
          {earth.items.length} investigations
        </text>
      </g>

      {/* the drop */}
      {[
        { cls: "gg-drop-moon", v: g.moon, name: "Moon" },
        { cls: "gg-drop-mars", v: g.mars, name: "Mars" },
      ].map(({ cls, v, name }) => (
        <g key={name} className={cls}>
          <line x1={xOf(v)} x2={xOf(v)} y1={64} y2={AY} stroke="var(--s-flame)" strokeWidth="3" />
          <circle cx={xOf(v)} cy={AY} r={6} fill="var(--s-flame)" />
          <text x={xOf(v)} y={30} textAnchor="middle" fontSize="17" fontWeight="500" fill="var(--s-flame)">{name}</text>
          <text x={xOf(v)} y={52} textAnchor="middle" fontSize="15" fill="var(--s-ink)">{v} m/s²</text>
        </g>
      ))}
    </svg>
  );
}

function Vertical({ data, desc }: { data: StoryData; desc: string }) {
  const { orbit, earth, g } = data;
  const AX = 58;
  const Y0 = 40;
  const Y1 = 566;
  const RUN = Y1 - Y0;
  const yOf = (v: number) => Y0 + (v / g.earth) * RUN;
  const ticks = [1, 2, 3, 4, 5, 6, 7, 8, 9];
  return (
    <svg
      className="gg-gap__v"
      viewBox="0 0 360 620"
      role="img"
      aria-labelledby="gg-gap-v-t gg-gap-v-d"
      style={{ "--ox": `${AX}px`, "--oy": `${Y0}px`, "--run": RUN } as Vars}
    >
      <title id="gg-gap-v-t">Fig. 4: where NASA has tested fire, by gravity</title>
      <desc id="gg-gap-v-d">{desc}</desc>
      <defs>{hatch("gg-hatch-v")}</defs>
      <g className="gg-axis-run" style={{ transformOrigin: `${AX}px ${Y0}px` }}>
        <rect x={AX + 6} y={Y0 + 22} width={300 - AX} height={RUN - 44} fill="url(#gg-hatch-v)" />
        <line x1={AX} x2={AX} y1={Y0} y2={Y1} stroke="var(--s-ink)" strokeWidth="1.5" />
      </g>
      <g fontSize="15" fill="var(--s-soft)">
        <text x={AX - 12} y={Y0 + 5} textAnchor="end">0</text>
        {ticks.map((t) => (
          <g key={t} className="gg-tick" style={{ "--at": t / g.earth } as Vars}>
            <line x1={AX - 6} x2={AX} y1={yOf(t)} y2={yOf(t)} stroke="var(--s-soft)" />
            <text x={AX - 12} y={yOf(t) + 5} textAnchor="end">{t}</text>
          </g>
        ))}
        <text x={AX - 12} y={Y1 + 5} textAnchor="end" fill="var(--s-ink)">9.81</text>
        <text x={AX - 12} y={Y1 + 26} textAnchor="end" fontSize="13">m/s²</text>
      </g>
      <text x={204} y={404} fontSize="15" fill="var(--s-ink)" className="gg-tick" style={{ "--at": 0.72 } as Vars}>
        <tspan x={204}>No fire test</tspan>
        <tspan x={204} dy={20}>at any gravity</tspan>
        <tspan x={204} dy={20}>in this span</tspan>
      </text>
      <g className="gg-tip">
        <line x1={AX - 2} x2={AX + 28} y1={Y0} y2={Y0} stroke="var(--s-flame)" strokeWidth="2" />
      </g>
      <g>
        {orbit.items.map((it, i) => (
          <rect key={it.id} x={AX + 6 + i * 6.4} y={Y0 - 16} width={4} height={14} fill="var(--s-micro)">
            <title>{it.name}</title>
          </rect>
        ))}
        <text x={AX + 6 + orbit.items.length * 6.4 + 8} y={Y0 - 4} fontSize="14" fill="var(--s-micro)">
          Orbit · {orbit.items.length}
        </text>
      </g>
      <g className="gg-earthcol">
        {earth.items.map((it, i) => (
          <rect key={it.id} x={AX + 6 + i * 6.4} y={Y1 + 2} width={4} height={14} fill="var(--s-normal)">
            <title>{it.name}</title>
          </rect>
        ))}
        <text x={AX + 6 + earth.items.length * 6.4 + 8} y={Y1 + 14} fontSize="14" fill="var(--s-normal)">
          Earth, 1 g · {earth.items.length}
        </text>
      </g>
      {[
        { cls: "gg-drop-moon", v: g.moon, name: "Moon" },
        { cls: "gg-drop-mars", v: g.mars, name: "Mars" },
      ].map(({ cls, v, name }) => (
        <g key={name} className={cls}>
          <line x1={AX} x2={196} y1={yOf(v)} y2={yOf(v)} stroke="var(--s-flame)" strokeWidth="3" />
          <circle cx={AX} cy={yOf(v)} r={5.5} fill="var(--s-flame)" />
          <text x={204} y={yOf(v) - 2} fontSize="17" fontWeight="500" fill="var(--s-flame)">{name}</text>
          <text x={204} y={yOf(v) + 18} fontSize="15" fill="var(--s-ink)">{v} m/s²</text>
        </g>
      ))}
    </svg>
  );
}
