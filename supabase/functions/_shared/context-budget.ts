// _shared/context-budget.ts -- bound retrieved RAG context to a token budget.
//
// Closes Phase 1.3 of the roadmap. RAG context grows naively: top-10
// chunks at 800 tokens each = 8k tokens shipped per call. Free providers
// cap at ~8k. This helper enforces a budget before context reaches the
// prompt -- it greedily includes chunks in order until the budget is
// exhausted, then drops the remainder.
//
// Use it after `rerank()` and before assembling the final system prompt.

import { estimateTokens } from "./cost-log.ts";

export interface BudgetedChunk {
  text:           string;
  /** Whatever metadata the caller wants paired with the chunk. */
  meta?:          Record<string, unknown>;
  /** Computed by the budgeter: tokens consumed by THIS chunk. */
  tokens?:        number;
}

export interface BudgetResult<T extends BudgetedChunk> {
  /** Chunks that fit within the budget, in input order. */
  kept:           T[];
  /** Chunks that exceeded the budget and were dropped. */
  dropped:        T[];
  /** Total tokens of the kept set. */
  tokens_used:    number;
  /** Caller's budget cap. */
  tokens_budget:  number;
}

/**
 * Enforce a token budget on a list of chunks.
 *
 * The default budget (4000 tokens) leaves room for ~1500 tokens of
 * user message + 2000-token model output within an 8k-token context
 * window. Tune via the second arg for higher-context providers.
 *
 * @param chunks  candidates in priority order (usually reranker output)
 * @param budget  max tokens to spend on context; defaults to 4000
 */
export function budgetContext<T extends BudgetedChunk>(
  chunks: T[],
  budget: number = 4000,
): BudgetResult<T> {
  const kept:    T[] = [];
  const dropped: T[] = [];
  let used = 0;
  for (const chunk of chunks) {
    const t = estimateTokens(chunk.text);
    if (used + t > budget) {
      dropped.push(chunk);
      continue;
    }
    used += t;
    kept.push({ ...chunk, tokens: t });
  }
  return { kept, dropped, tokens_used: used, tokens_budget: budget };
}

/**
 * Format a budgeted chunk array as a single context block ready to
 * concatenate into a prompt. Optionally tags each chunk with a source
 * label drawn from chunk.meta.source.
 */
export function formatContextBlock<T extends BudgetedChunk>(
  chunks: T[],
  header: string = "Retrieved context:",
): string {
  if (!chunks.length) return "";
  const lines: string[] = [header, ""];
  chunks.forEach((c, i) => {
    const src = c.meta?.source ? ` [${c.meta.source}]` : "";
    lines.push(`(${i + 1})${src} ${c.text}`);
    lines.push("");
  });
  return lines.join("\n");
}
