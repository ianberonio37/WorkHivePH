// _shared/rate-limit.ts
// AI rate-limit gate. Every edge function that calls callAI() (or any other
// paid model API) must invoke checkAIRateLimit BEFORE the model call.
// Without this gate a buggy or malicious hive can burn the entire budget
// in seconds.
//
// Usage:
//   import { checkAIRateLimit, rateLimitedResponse } from "../_shared/rate-limit.ts";
//   const rl = await checkAIRateLimit(db, hive_id);
//   if (!rl.allowed) return rateLimitedResponse(corsHeaders);
//   // ... callAI(...) goes here
//
// The function is idempotent within a 1-hour window: each successful gate
// increments call_count for the hive; the window resets after 60 minutes.

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

export const DEFAULT_RATE_LIMIT_PER_HOUR = 50;

export interface RateLimitResult {
  allowed:   boolean;
  remaining: number;
}

export async function checkAIRateLimit(
  db: SupabaseClient,
  hiveId: string,
  limitPerHour: number = DEFAULT_RATE_LIMIT_PER_HOUR,
): Promise<RateLimitResult> {
  if (!hiveId) {
    // Solo-worker mode (no hive context). Allow without tracking — these
    // calls are by definition single-user and bounded.
    return { allowed: true, remaining: limitPerHour };
  }
  const windowStart = new Date(Date.now() - 60 * 60 * 1000);
  const { data } = await db.from("ai_rate_limits")
    .select("call_count, window_start")
    .eq("hive_id", hiveId)
    .maybeSingle();
  if (!data || new Date(data.window_start) < windowStart) {
    await db.from("ai_rate_limits").upsert({
      hive_id:      hiveId,
      call_count:   1,
      window_start: new Date().toISOString(),
    });
    return { allowed: true, remaining: limitPerHour - 1 };
  }
  if (data.call_count >= limitPerHour) {
    return { allowed: false, remaining: 0 };
  }
  await db.from("ai_rate_limits")
    .update({ call_count: data.call_count + 1 })
    .eq("hive_id", hiveId);
  return { allowed: true, remaining: limitPerHour - data.call_count - 1 };
}

export function rateLimitedResponse(corsHeaders: Record<string, string>): Response {
  return new Response(
    JSON.stringify({
      error: "AI call limit reached for this hive. Try again in an hour.",
    }),
    { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } },
  );
}
