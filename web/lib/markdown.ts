/**
 * Minimal safe Markdown parser for AI answers. It produces a small AST that React renders as elements, so raw
 * HTML in the input is shown as text and never injected. Supported: #/##/### headings, paragraphs, - / * / 1.
 * lists, ``` code blocks, > quotes, **bold**, *italic*, `code`, [text](http(s) url), and citation tokens
 * ([PSI-69], [rec:PSI-69:FLEX:1], [doi:10.x/y], [eng:M1]) which become citation chips.
 */

export type Inline =
  | { t: "text"; v: string }
  | { t: "strong"; c: Inline[] }
  | { t: "em"; c: Inline[] }
  | { t: "code"; v: string }
  | { t: "link"; href: string; c: Inline[] }
  | { t: "cite"; id: string };

export type Block =
  | { t: "h"; level: 1 | 2 | 3; c: Inline[] }
  | { t: "p"; c: Inline[] }
  | { t: "ul"; items: Inline[][] }
  | { t: "ol"; items: Inline[][] }
  | { t: "code"; v: string }
  | { t: "quote"; c: Inline[] };

/** Citation id forms accepted by the AI validator (plan contracts: PSI-xx, rec:..., doi:...). */
export const CITATION_RE = /^(PSI-\d+|rec:[^\s\]]+|doi:[^\s\]]+|eng:[^\s\]]+)$/;

export function safeHref(href: string): string | null {
  const h = href.trim();
  if (/^https?:\/\//i.test(h) || /^mailto:/i.test(h)) return h;
  if (h.startsWith("/") && !h.startsWith("//")) return h;
  if (h.startsWith("#")) return h;
  return null;
}

export function parseInline(src: string): Inline[] {
  const out: Inline[] = [];
  let buf = "";
  const flush = () => {
    if (buf) out.push({ t: "text", v: buf });
    buf = "";
  };
  let i = 0;
  while (i < src.length) {
    const rest = src.slice(i);
    // `code`
    if (rest[0] === "`") {
      const end = rest.indexOf("`", 1);
      if (end > 0) {
        flush();
        out.push({ t: "code", v: rest.slice(1, end) });
        i += end + 1;
        continue;
      }
    }
    // **strong**
    if (rest.startsWith("**")) {
      const end = rest.indexOf("**", 2);
      if (end > 2) {
        flush();
        out.push({ t: "strong", c: parseInline(rest.slice(2, end)) });
        i += end + 2;
        continue;
      }
    }
    // *em* or _em_
    if ((rest[0] === "*" || rest[0] === "_") && rest[1] && rest[1] !== " " && rest[1] !== rest[0]) {
      const end = rest.indexOf(rest[0], 1);
      if (end > 1) {
        flush();
        out.push({ t: "em", c: parseInline(rest.slice(1, end)) });
        i += end + 1;
        continue;
      }
    }
    if (rest[0] === "[") {
      const close = rest.indexOf("]");
      if (close > 1) {
        const label = rest.slice(1, close);
        // [text](href)
        if (rest[close + 1] === "(") {
          // Matching ")" with nesting, so "(a(b))" is one URL.
          let depth = 0;
          let pend = -1;
          for (let k = close + 1; k < rest.length; k++) {
            if (rest[k] === "(") depth++;
            else if (rest[k] === ")" && --depth === 0) {
              pend = k;
              break;
            }
          }
          if (pend > close + 1) {
            const href = safeHref(rest.slice(close + 2, pend));
            flush();
            if (href) out.push({ t: "link", href, c: parseInline(label) });
            else out.push(...parseInline(label)); // unsafe scheme: keep the text, drop the link
            i += pend + 1;
            continue;
          }
        }
        // [PSI-69] or [PSI-69, rec:..] citation group
        const ids = label.split(/[,;]\s*/).map((s) => s.trim());
        if (ids.length && ids.every((s) => CITATION_RE.test(s))) {
          flush();
          ids.forEach((id) => out.push({ t: "cite", id }));
          i += close + 1;
          continue;
        }
      }
    }
    buf += rest[0];
    i++;
  }
  flush();
  return out;
}

export function parseMarkdown(src: string): Block[] {
  const lines = (src ?? "").replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  let para: string[] = [];
  const flushPara = () => {
    if (para.length) blocks.push({ t: "p", c: parseInline(para.join(" ")) });
    para = [];
  };
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();
    if (trimmed.startsWith("```")) {
      flushPara();
      const body: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) body.push(lines[i++]);
      i++; // closing fence (or EOF)
      blocks.push({ t: "code", v: body.join("\n") });
      continue;
    }
    if (trimmed === "") {
      flushPara();
      i++;
      continue;
    }
    const h = /^(#{1,6})\s+(.*)$/.exec(trimmed);
    if (h) {
      flushPara();
      const level = Math.min(3, h[1].length) as 1 | 2 | 3;
      blocks.push({ t: "h", level, c: parseInline(h[2]) });
      i++;
      continue;
    }
    if (/^[-*+]\s+/.test(trimmed) || /^\d+[.)]\s+/.test(trimmed)) {
      flushPara();
      const ordered = /^\d+[.)]\s+/.test(trimmed);
      const re = ordered ? /^\d+[.)]\s+/ : /^[-*+]\s+/;
      const items: Inline[][] = [];
      while (i < lines.length && re.test(lines[i].trim())) {
        items.push(parseInline(lines[i].trim().replace(re, "")));
        i++;
      }
      blocks.push(ordered ? { t: "ol", items } : { t: "ul", items });
      continue;
    }
    if (trimmed.startsWith(">")) {
      flushPara();
      const q: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) q.push(lines[i++].trim().replace(/^>\s?/, ""));
      blocks.push({ t: "quote", c: parseInline(q.join(" ")) });
      continue;
    }
    para.push(trimmed);
    i++;
  }
  flushPara();
  return blocks;
}

/** All citation ids found in a parsed document, in order of first appearance. */
export function collectCitations(blocks: Block[]): string[] {
  const seen: string[] = [];
  const walk = (xs: Inline[]) =>
    xs.forEach((x) => {
      if (x.t === "cite" && !seen.includes(x.id)) seen.push(x.id);
      if (x.t === "strong" || x.t === "em" || x.t === "link") walk(x.c);
    });
  blocks.forEach((b) => {
    if (b.t === "ul" || b.t === "ol") b.items.forEach(walk);
    else if (b.t !== "code") walk(b.c);
  });
  return seen;
}
