// _shared/cost-log.ts -- log every callAI() invocation to ai_cost_log
//
// Usage:
//   import { callAI } from "../_shared/ai-chain.ts";
//   import { logAICost } from "../_shared/cost-log.ts";
//
//   const t0 = Date.now();
//   const raw = await callAI(prompt, { systemPrompt, maxTokens: 1024 });
//   await logAICost(db, {
//     fn: "asset-brain-query",
//     hive_id, worker_name,
//     model: "groq:llama-3.3-70b",  // returned from callAI in future iteration
//     prompt_tokens: Math.round(prompt.length / 4),  // heuristic until token counts returned
//     output_tokens: Math.round((raw || "").length / 4),
//     latency_ms: Date.now() - t0,
//   });
//
// Closes PRODUCTION_FIXES #55. Best-effort logging -- errors don't
// fail the parent request (cost log is observability, not the
// critical path). Cost per token is computed downstream by the
// ai-cost.html dashboard via a lookup table per provider.

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

export interface AICostEntry {
  fn:             string;
  hive_id?:       string | null;
  worker_name?:   string | null;
  model:          string;
  provider?:      string;
  prompt_tokens?: number;
  output_tokens?: number;
  cost_usd?:      number;
  latency_ms?:    number;
  status?:        "success" | "failed" | "fallback";
}

export async function logAICost(
  db: SupabaseClient,
  entry: AICostEntry,
): Promise<void> {
  try {
    const row = {
      fn:            entry.fn,
      hive_id:       entry.hive_id || null,
      worker_name:   entry.worker_name || null,
      model:         entry.model,
      provider:      entry.provider || entry.model.split(":")[0] || null,
      prompt_tokens: entry.prompt_tokens || null,
      output_tokens: entry.output_tokens || null,
      cost_usd:      entry.cost_usd || null,
      latency_ms:    entry.latency_ms || null,
      status:        entry.status || "success",
    };
    const { error } = await db.from("ai_cost_log").insert(row);
    if (error) {
      console.warn("logAICost failed:", error.message);
    }
  } catch (err) {
    // Best-effort -- never block the calling request on cost logging.
    console.warn(
      "logAICost threw:",
      err instanceof Error ? err.message : String(err),
    );
  }
}

/**
 * Token-count heuristic: 1 token ≈ 4 characters for English text.
 * Cheap approximation when the provider doesn't return usage stats.
 */
export function estimateTokens(s: string): number {
  if (!s) return 0;
  return Math.round(s.length / 4);
}
