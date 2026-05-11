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


// ── Per-Route Rate Limiting (Phase 2.2) ───────────────────────────────────
//
// `checkAIRateLimit` above is a single global cap per hive. Non-AI routes
// (cheap reads) compete with expensive AI calls under one number. This
// per-route variant looks up (hive, route) -> hourly_cap from
// hive_route_quotas; falls back to the global default when no row exists.
//
// Counter table: hive_route_calls. Rows are keyed by (hive, route, hour).
// Insertion path:
//   1. Lookup hourly_cap from hive_route_quotas. Fallback to DEFAULT.
//   2. Compute hour_bucket = date_trunc('hour', now()).
//   3. Read current call_count for (hive, route, hour_bucket).
//   4. If >= cap AND enforce -> deny. Else upsert call_count + 1.

export interface RouteRateLimitResult extends RateLimitResult {
  /** Effective cap that was applied (per-route override OR default). */
  cap:      number;
  /** True when a hive_route_quotas row was found. */
  per_route: boolean;
  /** When false the call is logged but not blocked. */
  enforce:  boolean;
}

export async function checkRouteRateLimit(
  db:    SupabaseClient,
  hiveId: string,
  route:  string,
): Promise<RouteRateLimitResult> {
  if (!hiveId) {
    return {
      allowed:   true,
      remaining: DEFAULT_RATE_LIMIT_PER_HOUR,
      cap:       DEFAULT_RATE_LIMIT_PER_HOUR,
      per_route: false,
      enforce:   true,
    };
  }
  // Look up per-route quota.
  const { data: q } = await db
    .from("hive_route_quotas")
    .select("hourly_cap, enforce")
    .eq("hive_id", hiveId)
    .eq("route", route)
    .maybeSingle();
  const cap     = q?.hourly_cap ?? DEFAULT_RATE_LIMIT_PER_HOUR;
  const enforce = q?.enforce    ?? true;
  const perRoute = Boolean(q);

  // Compute hour bucket (truncate to the hour).
  const bucket = new Date();
  bucket.setMinutes(0, 0, 0);
  const bucketIso = bucket.toISOString();

  // Read current counter.
  const { data: c } = await db
    .from("hive_route_calls")
    .select("call_count")
    .eq("hive_id", hiveId)
    .eq("route", route)
    .eq("hour_bucket", bucketIso)
    .maybeSingle();
  const currentN = c?.call_count ?? 0;

  if (currentN >= cap) {
    // Increment anyway so dashboards see the over-cap pressure, but
    // only deny when enforce is true.
    await db.from("hive_route_calls").upsert({
      hive_id:     hiveId,
      route,
      hour_bucket: bucketIso,
      call_count:  currentN + 1,
      updated_at:  new Date().toISOString(),
    });
    return {
      allowed:   !enforce,
      remaining: 0,
      cap,
      per_route: perRoute,
      enforce,
    };
  }
  // Under cap: increment and allow.
  await db.from("hive_route_calls").upsert({
    hive_id:     hiveId,
    route,
    hour_bucket: bucketIso,
    call_count:  currentN + 1,
    updated_at:  new Date().toISOString(),
  });
  return {
    allowed:   true,
    remaining: cap - currentN - 1,
    cap,
    per_route: perRoute,
    enforce,
  };
}

export function routeRateLimitedResponse(
  corsHeaders: Record<string, string>,
  route: string,
  cap:   number,
): Response {
  return new Response(
    JSON.stringify({
      error: `Hourly call limit reached for route '${route}' (${cap}/hour). Try again later.`,
      route,
      cap,
    }),
    { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } },
  );
}
