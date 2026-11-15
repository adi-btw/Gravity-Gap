"use client";
/* eslint-disable @next/next/no-img-element -- the cover planes and figures are pre-sized WebP files the scroll engine positions directly; next/image wrappers would break the plane alignment. */
/* eslint-disable @next/next/no-css-tags -- the scroll-craft engine stylesheet must load only while this route is mounted. */

import Script from "next/script";
import { Suspense, useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import type { StoryData } from "./data";
import { Distribution } from "./Distribution";
import { GapFigure } from "./GapFigure";
import { RefusalPress } from "./RefusalPress";
import { CREDITS, INDEPENDENCE_LINE } from "./credits";
import "./story.css";

type Vars = CSSProperties & Record<`--${string}`, string | number>;

interface ScrollCraftApi {
  destroy(): void;
  layout(): void;
}
declare global {
  interface Window {
    ScrollCraft?: { mount(root: Element, opts?: object): ScrollCraftApi };
  }
}

const CHAPTERS = [
  { id: "hazard", title: "The hazard" },
  { id: "two-gravities", title: "Two gravities" },
  { id: "gap", title: "The gap" },
  { id: "bridge", title: "The bridge" },
  { id: "refusal", title: "The refusal" },
  { id: "distribution", title: "Your copy" },
] as const;

/** Sections drawn on the dark "space" ground; the margin contents steps aside over them. */
const DARK = new Set(["cover", "gap"]);

const PLATFORM_NAMES: Record<string, string> = { ISS: "ISS", Cygnus: "Cygnus cargo ships", ground: "ground labs" };

/**
 * The story page at "/": a flight-test report in eight sections (scrollcraft/builds/gravity-gap/SCORE.md).
 * The scroll-craft engine (public/scrollcraft, unmodified) is loaded only here and destroyed on leaving.
 * Parallax (unslop/AUDIT.md exception): transform-only, a few dozen pixels, engine-driven and off under reduced motion,
 * on the cover planes and title, the hazard photographs and the candle pair.
 */
export function StoryPage({ data }: { data: StoryData }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const apiRef = useRef<ScrollCraftApi | null>(null);

  const mount = useCallback(() => {
    if (apiRef.current || !rootRef.current || !window.ScrollCraft) return;
    apiRef.current = window.ScrollCraft.mount(rootRef.current);
  }, []);

  useEffect(() => {
    mount();
    return () => {
      apiRef.current?.destroy();
      apiRef.current = null;
    };
  }, [mount]);

  const fmtInt = (n: number) => n.toLocaleString("en-US");
  const lb = data.lunarBase;

  return (
    <div className="gg-story" ref={rootRef}>
      {/* Engine floor, scoped to this route: rendered here so it unmounts with the page. */}
      <link rel="stylesheet" href="/scrollcraft/scrollcraft.css" />
      <Script src="/scrollcraft/scrollcraft.js" strategy="afterInteractive" onReady={mount} />

      <ReportContents />

      {/* 1 · cover ------------------------------------------------------------------------------------- */}
      <section id="cover" className="gg-sec gg-space gg-cover" data-sc-act="flow" aria-labelledby="cover-title">
        <div className="gg-cover__scene" aria-hidden="true">
          <div className="gg-cover__plane gg-cover__earth" data-sc-parallax="0.9">
            <img src="/story/cover-earth.webp" alt="" width={1920} height={1920} fetchPriority="high" />
          </div>
          <div className="gg-cover__plane gg-cover__moon" data-sc-parallax="-1.6">
            <img src="/story/cover-moon.webp" alt="" width={1920} height={1920} fetchPriority="high" />
          </div>
        </div>
        <div className="gg-cover__copy" data-sc-parallax="0.45">
          <div className="gg-wrap">
            <p className="gg-label">Evidence report, NASA Space Apps 2026</p>
            <h1 id="cover-title" className="gg-h1">
              NASA&apos;s fire data stops at two gravities
            </h1>
            <p className="gg-lede">
              Orbit and Earth. The Moon and Mars sit between them, and that is where crews will live next.
            </p>
          </div>
        </div>
        <p className="gg-cover__credit">
          Earth over the lunar horizon, Apollo 11, July 1969. NASA, AS11-44-6549
        </p>
      </section>

      {/* 2 · hazard ------------------------------------------------------------------------------------ */}
      <section id="hazard" className="gg-sec gg-hazard" data-sc-act="flow" aria-labelledby="hazard-title">
        <div className="gg-wrap gg-hazard__grid">
          <div className="gg-stack" data-sc-in data-sc-stagger="70">
            <h2 id="hazard-title" className="gg-h2">
              Fire is the emergency every crew plans for
            </h2>
            <p>
              A spacecraft cannot be evacuated like a building. So NASA burns things on purpose, in orbit, long before a
              crew needs the answer: fuel droplets, gas flames, acrylic slabs, large fabric samples.
            </p>
            <p className="gg-soft">
              The results are public, in NASA&apos;s Physical Sciences Informatics archive. Gravity Gap reads all of it.
            </p>
            <dl className="gg-ledger">
              <div>
                <dt>Combustion investigations in the PSI catalog</dt>
                <dd>{data.combustionInvestigations}</dd>
              </div>
              <div>
                <dt>Individual tests, cleaned from {data.cleanedInvestigations} of them</dt>
                <dd>{fmtInt(data.cleanedTests)}</dd>
              </div>
              <div>
                <dt>Where they ran</dt>
                <dd style={{ fontSize: "0.875rem" }}>{data.platforms.map((p) => PLATFORM_NAMES[p] ?? p).join(", ")}</dd>
              </div>
            </dl>
          </div>
          <div className="gg-hazard__figs">
            <figure className="gg-hazard__fig1" data-sc-parallax="0.2">
              <img
                className="gg-photo"
                src="/story/iss-cir-epps.webp"
                width={1600}
                height={1066}
                alt="Astronaut Jeanette Epps, in gloves, holds a component of the Combustion Integrated Rack open in front of her inside the space station's Destiny lab."
                loading="lazy"
              />
              <figcaption>
                <span className="gg-fig-no">Fig. 1</span>
                Jeanette Epps services the Combustion Integrated Rack aboard the ISS before a series of fire safety
                investigations, 3 September 2024. NASA, iss071e582160.
              </figcaption>
            </figure>
            <figure className="gg-hazard__inset" data-sc-parallax="-0.55">
              <img
                className="gg-photo"
                src="/story/bass2-flame.webp"
                width={1240}
                height={820}
                alt="A rounded blue and pink flame burning off the end of a thin acrylic slab in microgravity, against black."
                loading="lazy"
              />
              <figcaption>
                <span className="gg-fig-no">Fig. 2</span>
                A BASS-II flame on an acrylic slab, ISS, 23 July 2014. NASA / Reid Wiseman, iss040e072900.
              </figcaption>
            </figure>
          </div>
        </div>
      </section>

      {/* 3 · two gravities ----------------------------------------------------------------------------- */}
      <section id="two-gravities" className="gg-sec gg-two" data-sc-act="flow" aria-labelledby="two-title">
        <div className="gg-wrap gg-two__grid">
          <figure className="gg-two__fig" data-sc-parallax="-0.3">
            <div className="gg-candles__labels gg-label" aria-hidden="true">
              <span>1 g · Earth</span>
              <span>0 g · orbit</span>
            </div>
            <div className="gg-candles">
              <div>
                <img
                  src="/story/candle-1g.webp"
                  width={813}
                  height={1327}
                  alt="On Earth: a tall, bright yellow candle flame, blue only at its base."
                  loading="lazy"
                />
              </div>
              <div data-sc-reveal="right" data-sc-reveal-at="0.36 0.62">
                <img
                  src="/story/candle-0g.webp"
                  width={813}
                  height={1327}
                  alt="In microgravity: the same candle burning as a small, dim, blue dome around the wick."
                  loading="lazy"
                />
              </div>
            </div>
            <figcaption>
              <span className="gg-fig-no">Fig. 3</span>
              The same candle on Earth and in microgravity. NASA Glenn Research Center (then Lewis), GRC-1998-C-00486.
            </figcaption>
          </figure>
          <div className="gg-two__copy gg-stack" data-sc-in data-sc-stagger="70">
            <h2 id="two-title" className="gg-h2">
              Every one of those tests burned at one of two gravities
            </h2>
            <p>
              On Earth hot gas rises, so a candle stands tall, yellow and sooty. In orbit nothing rises: the same candle
              burns as a dim blue dome, fed only by slow diffusion.
            </p>
            <dl className="gg-ledger">
              <div>
                <dt>Run in microgravity ({data.orbit.platforms.join(", ")})</dt>
                <dd>{data.orbit.items.length}</dd>
              </div>
              <div>
                <dt>With Earth-gravity (1 g) data</dt>
                <dd>{data.earth.items.length}</dd>
              </div>
              <div className="gg-ledger__zero">
                <dt>Run at any gravity in between</dt>
                <dd>{data.partialCount}</dd>
              </div>
            </dl>
          </div>
        </div>
      </section>

      {/* 4 · silence (authored) ------------------------------------------------------------------------ */}
      <section className="gg-sec gg-tint gg-between" aria-label="Between orbit and Earth">
        <div className="gg-wrap">
          <p data-sc-in>Between those two, the archive is empty</p>
        </div>
      </section>

      {/* 5 · the gap (peak) ---------------------------------------------------------------------------- */}
      <section id="gap" className="gg-sec gg-space gg-gap" data-sc-act="pin" data-sc-span="3.6" aria-labelledby="gap-title">
        <div className="gg-gap__stage" data-sc-stage>
          <div className="gg-wrap gg-gap__head">
            <h2 id="gap-title" className="gg-h2" style={{ maxWidth: "15ch" }}>
              Two ends, and nothing in the middle
            </h2>
            <p className="gg-label">
              <span className="gg-fig-no">Fig. 4</span>
              Every combustion investigation in the PSI catalog, placed at the gravity it was tested at, in m/s² (to
              scale)
            </p>
          </div>
          <div className="gg-wrap gg-gap__plot">
            <GapFigure data={data} />
          </div>
          <div className="gg-wrap gg-gap__cap">
            <p>
              The Moon, at <em className="gg-num">{data.g.moon} m/s²</em>, and Mars, at{" "}
              <em className="gg-num">{data.g.mars} m/s²</em>, land in the span where no fire has been tested.
            </p>
            <p className="gg-soft" style={{ fontSize: "0.9375rem" }}>
              Habitats there are planned at {lb.p_psia} psia and {lb.o2Pct}% oxygen. The next two figures follow the lunar
              base into that span.
            </p>
          </div>
        </div>
      </section>

      {/* 6 · bridge ------------------------------------------------------------------------------------ */}
      <section id="bridge" className="gg-sec gg-bridge" data-sc-act="flow" aria-labelledby="bridge-title">
        <div className="gg-wrap gg-bridge__grid">
          <div className="gg-stack" data-sc-in data-sc-stagger="70">
            <h2 id="bridge-title" className="gg-h2">
              Gravity Gap carries the orbit tests across, and pays for it in width
            </h2>
            <p>
              At a lunar base, with the cabin fan at 10 cm/s (an assumption you can edit), a small flame is in the{" "}
              {lb.regime} regime: its own buoyancy and the fan push about equally, Richardson number{" "}
              <span className="gg-num">{lb.ri.toFixed(2)}</span>. Across the uncertainty sampling it is{" "}
              <span className="gg-num">{lb.mixedPct.toFixed(1)}%</span> mixed and{" "}
              <span className="gg-num">{lb.buoyantPct.toFixed(1)}%</span> buoyant. The ISS tests never felt that
              buoyancy.
            </p>
            <p className="gg-soft">
              So the estimate keeps its centre and its 90% band is widened{" "}
              <span className="gg-num">×{data.m1.widen}</span>. Transfer confidence: low, and the tool says so next to
              the number.
            </p>
          </div>
          <figure>
            <div className="gg-bands" data-sc-in>
              <Band
                label="Orbit tests, as measured (0 g)"
                band={data.m1.band0g}
                est={data.m1.estimate}
              />
              <Band label="Carried to the lunar base" band={data.m1.band} est={data.m1.estimate} wide />
              <div className="gg-bands__axis gg-label" aria-hidden="true">
                <span>0%</span>
                <span>50%</span>
                <span>100%</span>
              </div>
            </div>
            <figcaption>
              <span className="gg-fig-no">Fig. 5</span>
              Chance that a fuel droplet&apos;s flame goes out before the droplet burns away (metric M1), estimate{" "}
              {(data.m1.estimate * 100).toFixed(1)}% with its 90% band. Trained on {data.m1.nTrain} FLEX tests (PSI-69).
            </figcaption>
          </figure>
        </div>
      </section>

      {/* 7 · the refusal (signature move) -------------------------------------------------------------- */}
      <section id="refusal" className="gg-sec gg-refusal" data-sc-act="pin" data-sc-span="2.6" aria-labelledby="refusal-title">
        <div className="gg-refusal__stage" data-sc-stage>
          <RefusalPress data={data} />
        </div>
      </section>

      {/* 8 · distribution (close) ---------------------------------------------------------------------- */}
      <section id="distribution" className="gg-sec gg-dist" aria-labelledby="distribution-title">
        <div className="gg-wrap">
          <Suspense fallback={null}>
            <Distribution />
          </Suspense>
          <footer className="gg-colophon">
            <div>
              <h3>Photographs</h3>
              <ul>
                {CREDITS.map((c) => (
                  <li key={c.id}>
                    {c.use}: &ldquo;{c.title}&rdquo;, {c.center}, {c.date}. {c.credit},{" "}
                    <a href={`https://images.nasa.gov/details/${c.id}`}>{c.id}</a>.
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Data</h3>
              <p>
                NASA Physical Sciences Informatics (<a href="https://psi.nasa.gov">psi.nasa.gov</a>), CC0-1.0, cleaned by
                Gravity Gap. Every number in this report is read from the project&apos;s committed artifacts.
              </p>
              <p className="gg-indep" data-testid="independence-line">
                {INDEPENDENCE_LINE}
              </p>
            </div>
          </footer>
        </div>
      </section>
    </div>
  );
}

function Band({ label, band, est, wide = false }: { label: string; band: [number, number]; est: number; wide?: boolean }) {
  const p = (x: number) => `${(x * 100).toFixed(1)}%`;
  return (
    <div className={`gg-band${wide ? " gg-band--wide" : ""}`}>
      <div className="gg-band__head">
        <span>{label}</span>
        <span className="gg-num">
          {p(band[0])} to {p(band[1])}
        </span>
      </div>
      <div className="gg-band__track" style={{ "--lo": band[0], "--hi": band[1], "--est": est } as Vars} aria-hidden="true">
        <span className="gg-band__bar" />
        <span className="gg-band__dot" />
      </div>
    </div>
  );
}

/** The report's nav: a contents column in the left margin, chapter titles only, the current one ruled. */
function ReportContents() {
  const [current, setCurrent] = useState<string>("cover");
  useEffect(() => {
    const ids = ["cover", ...CHAPTERS.map((c) => c.id)];
    const els = ids.map((id) => document.getElementById(id)).filter((e): e is HTMLElement => !!e);
    const extra = document.querySelector<HTMLElement>(".gg-between");
    const io = new IntersectionObserver(
      (entries) => {
        // The section crossing the middle of the viewport is the current one.
        for (const e of entries) if (e.isIntersecting) setCurrent(e.target.id || "between");
      },
      { rootMargin: "-50% 0px -50% 0px" },
    );
    els.forEach((e) => io.observe(e));
    if (extra) io.observe(extra);
    return () => io.disconnect();
  }, []);
  const hidden = DARK.has(current) || current === "between";
  return (
    <nav className="gg-contents" aria-label="Report contents" data-hidden={hidden ? "true" : "false"}>
      <p className="gg-label">Contents</p>
      <ol>
        {CHAPTERS.map((c) => (
          <li key={c.id}>
            <a href={`#${c.id}`} aria-current={current === c.id ? "true" : undefined}>
              {c.title}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
