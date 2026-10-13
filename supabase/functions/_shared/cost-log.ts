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
//
// ★INSIDE A REQUEST THIS NO LONGER WRITES A ROW OF ITS OWN (LM-O, 2026-10-08). Every served model call is now
// recorded once by the shared collector (_shared/model-calls.ts: the chain reports it, serveObserved writes it with
// fn, hive, user, the provider and model that actually served, tokens, latency and the reply's trace id). A call
// here inside a serveObserved request ANNOTATES the served call it follows - schema_compliance, prompt_hash, a
// fallback/failed status the function decided - or, when nothing served, records that attempt as one failed row.
// So a function that still calls logAICost no longer double-counts, and its hand-typed `model` ("chain:auto") never
// overwrites the model that really answered. Outside a request scope (a script, a test) it inserts as before.

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";
import { absorbCostEntry } from "./model-calls.ts";

export interface AICostEntry {
  fn:                 string;
  hive_id?:           string | null;
  worker_name?:       string | null;
  model:              string;
  provider?:          string;
  prompt_tokens?:     number;
  output_tokens?:     number;
  cost_usd?:          number;
  latency_ms?:        number;
  status?:            "success" | "failed" | "fallback";
  // 2026-05-11 extensions: telemetry shape for #54 Layer 4 teeth.
  schema_compliance?: boolean | null;   // JSON-mode payload parsed cleanly?
  user_feedback?:     -1 | 0 | 1 | null; // thumbs-down / neutral / thumbs-up
  prompt_hash?:       string | null;     // sha-256(prompt+system) for drift detection
}

export async function logAICost(
  db: SupabaseClient,
  entry: AICostEntry,
): Promise<void> {
  // inside a request: the collector holds this call's record; annotate it rather than write a second row
  if (absorbCostEntry(entry)) return;
  try {
    const row = {
      fn:                entry.fn,
      hive_id:           entry.hive_id || null,
      worker_name:       entry.worker_name || null,
      model:             entry.model,
      provider:          entry.provider || entry.model.split(":")[0] || null,
      prompt_tokens:     entry.prompt_tokens || null,
      output_tokens:     entry.output_tokens || null,
      cost_usd:          entry.cost_usd || null,
      latency_ms:        entry.latency_ms || null,
      status:            entry.status || "success",
      schema_compliance: entry.schema_compliance ?? null,
      user_feedback:     entry.user_feedback ?? null,
      prompt_hash:       entry.prompt_hash ?? null,
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
