import Link from "next/link";
import { parseMarkdown, type Block, type Inline } from "@/lib/markdown";

/** Citation chip: PSI ids open the investigation card, DOIs open doi.org, record ids show their id. */
export function CitationChip({ id }: { id: string }) {
  const cls =
    "num mx-0.5 inline-flex items-center rounded border border-micro px-1.5 py-px align-baseline text-[11px] text-micro hover:bg-surface-2";
  const psi = /^(?:rec:)?(PSI-\d+)/.exec(id);
  if (id.startsWith("doi:")) {
    return (
      <a href={`https://doi.org/${id.slice(4)}`} target="_blank" rel="noreferrer" className={cls} title={id}>
        {id}
      </a>
    );
  }
  if (psi && !id.startsWith("rec:")) {
    return (
      <Link href={`/investigations/${psi[1]}`} className={cls} title={`Investigation ${psi[1]}`}>
        {id}
      </Link>
    );
  }
  if (id.startsWith("eng:")) {
    return (
      <span className={`${cls.replace("border-micro text-micro", "border-partial text-partial")}`} title={`Engine output ${id.slice(4)}`} tabIndex={0}>
        {id}
      </span>
    );
  }
  return (
    <span className={cls} title={`Test record ${id.replace(/^rec:/, "")}`} tabIndex={0}>
      {id.replace(/^rec:/, "")}
    </span>
  );
}

function Inlines({ xs }: { xs: Inline[] }) {
  return (
    <>
      {xs.map((x, i) => {
        switch (x.t) {
          case "text":
            return <span key={i}>{x.v}</span>;
          case "strong":
            return (
              <strong key={i}>
                <Inlines xs={x.c} />
              </strong>
            );
          case "em":
            return (
              <em key={i}>
                <Inlines xs={x.c} />
              </em>
            );
          case "code":
            return (
              <code key={i} className="num rounded bg-surface-2 px-1 text-[0.9em]">
                {x.v}
              </code>
            );
          case "link":
            return (
              <a key={i} href={x.href} className="text-micro underline" target={x.href.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
                <Inlines xs={x.c} />
              </a>
            );
          case "cite":
            return <CitationChip key={i} id={x.id} />;
        }
      })}
    </>
  );
}

function BlockView({ b }: { b: Block }) {
  switch (b.t) {
    case "h": {
      const cls = b.level === 1 ? "text-lg font-medium" : b.level === 2 ? "text-base font-medium" : "text-sm font-medium";
      const H = (`h${b.level + 2}` as "h3" | "h4" | "h5");
      return (
        <H className={cls}>
          <Inlines xs={b.c} />
        </H>
      );
    }
    case "p":
      return (
        <p>
          <Inlines xs={b.c} />
        </p>
      );
    case "ul":
    case "ol": {
      const L = b.t === "ul" ? "ul" : "ol";
      return (
        <L className={`${b.t === "ul" ? "list-disc" : "list-decimal"} space-y-1 pl-5`}>
          {b.items.map((it, i) => (
            <li key={i}>
              <Inlines xs={it} />
            </li>
          ))}
        </L>
      );
    }
    case "code":
      return <pre className="num overflow-x-auto rounded bg-surface-2 p-2 text-xs">{b.v}</pre>;
    case "quote":
      return (
        <blockquote className="border-l-2 border-line pl-3 text-muted">
          <Inlines xs={b.c} />
        </blockquote>
      );
  }
}

export function Markdown({ source }: { source: string }) {
  const blocks = parseMarkdown(source);
  return (
    <div className="space-y-2 text-sm leading-relaxed">
      {blocks.map((b, i) => (
        <BlockView key={i} b={b} />
      ))}
    </div>
  );
}
