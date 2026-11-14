import type { AskAnswer } from "@/lib/types";
import type { DataSource } from "@/lib/api";
import { CitationChip, Markdown } from "./Markdown";
import { SourceChip } from "./ui/States";

const MODE_LABEL: Record<string, string> = {
  claude: "Claude (live)",
  cached: "cached answer",
  template: "template (no LLM)",
};

/** An AI answer: safe markdown, citation chips, validation status and generation mode. */
export function AskAnswerView({ answer, source, note }: { answer: AskAnswer; source: DataSource; note?: string }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span
          className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 ${
            answer.validated ? "border-micro text-micro" : "border-warn text-warn"
          }`}
        >
          <span aria-hidden="true">{answer.validated ? "✓" : "!"}</span>
          {answer.validated ? "validated: every number and citation traced" : "not validated: treat with care"}
        </span>
        <span className="rounded-full border border-line px-2 py-0.5 text-muted">
          mode: {MODE_LABEL[answer.mode] ?? answer.mode}
        </span>
        <SourceChip source={source} note={note} />
      </div>
      <Markdown source={answer.answer_markdown} />
      {answer.citations?.length ? (
        <div>
          <h4 className="mb-1 text-xs font-medium text-muted">Citations</h4>
          <div className="flex flex-wrap gap-1">
            {answer.citations.map((c) => (
              <CitationChip key={c} id={c} />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
