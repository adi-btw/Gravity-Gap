# 05 · AI Layer ("Super Intelligence")

Back to [overview](00-overview.md). It serves F7 and E4 in [04-features.md](04-features.md) and [02-data-pipeline.md](02-data-pipeline.md).

## 1. Role of the AI (and what it must never do)
| AI does | AI never does |
|---|---|
| Summarize investigations from catalog text | Generate a number that isn't in its context |
| Explain engine outputs in plain language | Override the honesty gate ("extrapolation") |
| Extract candidate values from papers (offline, verbatim-gated) | Claim safety certification |
| Score fire-safety relevance with quoted evidence | Answer rocket/propellant questions as in-scope |
| Draft prediction rationales for the ledger (human approves) | Write to the ledger without human approval |

## 2. Model choice
- Runtime Q&A and explanations: the latest Sonnet-class Claude model (e.g. `claude-sonnet-5-5`). Use prompt caching for the static catalog context.
- Offline extraction and relevance scoring: an Opus-class model (e.g. `claude-opus-5-5`), run once at build time, with results cached into artifacts.
- Configured through environment variables; no keys in the repo.

## 3. Grounding architecture
1. **Context pack** for each request: the habitat state, the engine outputs (numbers with IDs), the top-k catalog records (by F1 relevance), and the evidence rows (record_ids + key fields).
2. **System prompt rules:**
   - Use only numbers in the context pack.
   - Cite each claim as `[PSI-xx]`, `[rec:PSI-69:FLEX:12]` or `[doi:…]`.
   - If the context lacks the answer, say so.
3. **Structured output:** JSON `{answer_markdown, citations[], numbers_used[]}`.
4. **Post-validator (deterministic code):**
   - Every number in `answer_markdown` must appear in `numbers_used`, and every `numbers_used` value must exist in the context pack (tolerance 0.5%).
   - Every citation ID must resolve.
   - On failure: one retry with the error message; then fall back to a template answer built from engine outputs.
5. **Offline cache:** answers for the demo's scripted questions are pre-generated and stored, so the demo survives an API outage (R4).

## 4. Prompts (versioned in `/engine/prompts/`)
- `summarize_investigation.v1`: 3 sentences + hazard pillars + Earth application, from the catalog record only.
- `relevance_score.v1`: per pillar, a score of 0–3 with a mandatory quote.
- `explain_bounds.v1`: explains the regime, the bounds, why the band is wide, and what test would narrow it.
- `extract_paper_values.v1`: quantity, value, unit, conditions, gravity, verbatim quote, page.
- `ledger_rationale.v1`: a draft for human edit.

## 5. Evaluations (run in CI on prompt or model change; see [08-testing-qa.md](08-testing-qa.md) T6)
| Eval | Set | Pass bar |
|---|---|---|
| Groundedness | 30 scripted questions | 100% of numbers validated |
| Citation validity | Same 30 | 100% of citations resolve |
| Refusal | 10 out-of-scope prompts | ≥ 9/10 refused correctly |
| Extraction precision | 40 hand-labeled paper values | ≥ 90% precision (recall is secondary) |
| Summary faithfulness | 11 investigations, human-graded | No contradictions with the source |

## 6. Safety, privacy, cost
- No user personal data is collected. Questions are logged without identity.
- Cost guard: the per-session token cap and the cached system context keep the expected demo-day cost under ~$5.
- Rate-limit handling: exponential backoff, then the cached fallback.
