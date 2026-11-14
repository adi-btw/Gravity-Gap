import { describe, expect, it } from "vitest";
import { collectCitations, parseInline, parseMarkdown, safeHref } from "./markdown";

describe("safe markdown renderer", () => {
  it("keeps raw HTML as plain text", () => {
    const blocks = parseMarkdown('<script>alert(1)</script> <img src=x onerror="x()">');
    expect(blocks).toEqual([{ t: "p", c: [{ t: "text", v: '<script>alert(1)</script> <img src=x onerror="x()">' }] }]);
  });

  it("drops unsafe link schemes but keeps the label", () => {
    expect(parseInline("[click](javascript:alert(1))")).toEqual([{ t: "text", v: "click" }]);
    expect(safeHref("javascript:alert(1)")).toBeNull();
    expect(safeHref("data:text/html,x")).toBeNull();
    expect(safeHref("//evil.example")).toBeNull();
    expect(safeHref("https://doi.org/10.1/x")).toBe("https://doi.org/10.1/x");
    expect(safeHref("/investigations/PSI-69")).toBe("/investigations/PSI-69");
  });

  it("parses emphasis, code and links", () => {
    expect(parseInline("**Regime: mixed.** and *low* `Ri`")).toEqual([
      { t: "strong", c: [{ t: "text", v: "Regime: mixed." }] },
      { t: "text", v: " and " },
      { t: "em", c: [{ t: "text", v: "low" }] },
      { t: "text", v: " " },
      { t: "code", v: "Ri" },
    ]);
  });

  it("turns citation tokens into chips, including grouped ones", () => {
    const xs = parseInline("u_b is 25.5 cm/s [eng:physics] from [PSI-69, rec:PSI-69:FLEX:20] and [doi:10.1/abc]");
    expect(xs.filter((x) => x.t === "cite")).toEqual([
      { t: "cite", id: "eng:physics" },
      { t: "cite", id: "PSI-69" },
      { t: "cite", id: "rec:PSI-69:FLEX:20" },
      { t: "cite", id: "doi:10.1/abc" },
    ]);
  });

  it("leaves ordinary brackets alone", () => {
    expect(parseInline("range [0.1, 10] is mixed")).toEqual([{ t: "text", v: "range [0.1, 10] is mixed" }]);
  });

  it("parses headings, lists, quotes and code fences", () => {
    const md = "## Why\n\n- one [PSI-10]\n- two\n\n1. first\n2. second\n\n> note\n\n```\n<b>x</b>\n```\npara\nline two";
    const blocks = parseMarkdown(md);
    expect(blocks.map((b) => b.t)).toEqual(["h", "ul", "ol", "quote", "code", "p"]);
    expect(blocks[4]).toEqual({ t: "code", v: "<b>x</b>" });
    expect(blocks[5]).toEqual({ t: "p", c: [{ t: "text", v: "para line two" }] });
    expect(collectCitations(blocks)).toEqual(["PSI-10"]);
  });

  it("handles empty input", () => {
    expect(parseMarkdown("")).toEqual([]);
  });
});
