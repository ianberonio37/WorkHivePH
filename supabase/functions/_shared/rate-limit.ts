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

// 2026-05-26: honor WH_RATE_LIMIT_OVERRIDE at module load so EVERY caller of
// checkAIRateLimit (including specialists like voice-logbook-entry and
// voice-report-intent which don't pass an explicit limit) picks up the test
// override. Previously the gateway honored the override but downstream
// specialists kept the hardcoded 50 cap and 429'd after the 51st call —
// V2 flywheel run showed 2 rate-limited probes/turn from turn 4 onward
// because the ai_rate_limits row is shared per hive across all callers.
export const DEFAULT_RATE_LIMIT_PER_HOUR =
  Number(Deno.env.get("WH_RATE_LIMIT_OVERRIDE") || 50);

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


// ── Per-User Rate Limiting (P1 roadmap 2026-05-26) ─────────────────────────
//
// `checkAIRateLimit` is per-hive (whole-hive bucket). `checkRouteRateLimit`
// is per-(hive, route). Neither protects a hive from a single noisy worker
// inside it: one user can burn the hive's hourly budget and starve their
// teammates.
//
// `checkUserRateLimit` enforces a per-user soft cap inside the per-hive cap.
// The soft cap is typically a fraction of the hive cap (e.g. hive cap 200 →
// per-user soft cap 50). On breach, the call is denied *for that user only*;
// other hive members keep their budget.
//
// Counter table: ai_user_rate_limits.
//   user_id TEXT PK, hive_id TEXT, call_count INT, window_start TIMESTAMPTZ
//
// The hive-level gate runs first. If hive is blocked, we never check user.
// If hive is allowed, we then check user. If user is blocked, hive count is
// NOT incremented (caller never made the underlying AI call).

export interface UserRateLimitResult extends RateLimitResult {
  user_cap:        number;
  hive_remaining:  number;
}

export const DEFAULT_USER_RATE_LIMIT_PER_HOUR =
  Number(Deno.env.get("WH_USER_RATE_LIMIT_OVERRIDE") || 25);

export async function checkUserRateLimit(
  db:     SupabaseClient,
  hiveId: string,
  userId: string,
  hiveLimit: number = DEFAULT_RATE_LIMIT_PER_HOUR,
  userLimit: number = DEFAULT_USER_RATE_LIMIT_PER_HOUR,
): Promise<UserRateLimitResult> {
  // Hive gate first.
  const hive = await checkAIRateLimit(db, hiveId, hiveLimit);
  if (!hive.allowed) {
    return {
      allowed:        false,
      remaining:      0,
      user_cap:       userLimit,
      hive_remaining: 0,
    };
  }
  // Solo / system calls — no user bucket needed.
  if (!userId) {
    return {
      allowed:        true,
      remaining:      userLimit,
      user_cap:       userLimit,
      hive_remaining: hive.remaining,
    };
  }
  const windowStart = new Date(Date.now() - 60 * 60 * 1000);
  // canonical-allow: ai_user_rate_limits is an infrastructure counter table (per-user budget inside the per-hive bucket); not a user-facing KPI source. Registered in canonical_sources as domain='rate_limit_infra'.
  const { data } = await db.from("ai_user_rate_limits")
    .select("call_count, window_start")
    .eq("user_id", userId)
    .maybeSingle();
  if (!data || new Date(data.window_start) < windowStart) {
    // canonical-allow: ai_user_rate_limits infrastructure counter (see lookup site).
    await db.from("ai_user_rate_limits").upsert({
      user_id:      userId,
      hive_id:      hiveId,
      call_count:   1,
      window_start: new Date().toISOString(),
    });
    return {
      allowed:        true,
      remaining:      userLimit - 1,
      user_cap:       userLimit,
      hive_remaining: hive.remaining,
    };
  }
  if (data.call_count >= userLimit) {
    return {
      allowed:        false,
      remaining:      0,
      user_cap:       userLimit,
      hive_remaining: hive.remaining,
    };
  }
  // canonical-allow: ai_user_rate_limits infrastructure counter (see lookup site).
  await db.from("ai_user_rate_limits")
    .update({ call_count: data.call_count + 1 })
    .eq("user_id", userId);
  return {
    allowed:        true,
    remaining:      userLimit - data.call_count - 1,
    user_cap:       userLimit,
    hive_remaining: hive.remaining,
  };
}

export function userRateLimitedResponse(
  corsHeaders: Record<string, string>,
  userCap: number,
): Response {
  return new Response(
    JSON.stringify({
      error:    `Per-user AI call limit reached (${userCap}/hour). Other hive members are unaffected.`,
      user_cap: userCap,
      scope:    "user",
    }),
    { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } },
  );
}


// ── Voice vs Background Quota Split (P1 roadmap 2026-05-27 turn 7) ────────
//
// Voice (interactive, latency-sensitive) and background (RAG flywheel,
// embeddings, batch scoring) currently share one per-hive bucket. When the
// flywheel spikes, voice users get 429. Splitting the quota gives voice
// guaranteed headroom regardless of background activity.
//
// `traffic_class`:
//   "voice"      → interactive user-facing calls (companion turns, gateway)
//   "background" → batch / flywheel / embedding fills / scheduled work
//
// Counter rows: ai_rate_limits is reused; add `traffic_class` column?
// For now, keep this in-process: traffic_class is a multiplier on the cap.
// VOICE_QUOTA_RATIO = 0.7 means voice gets 70% of the per-hive cap; bg 30%.
// When a class hits its share, the OTHER class still flows freely up to
// the global cap.

export const VOICE_QUOTA_RATIO      = Number(Deno.env.get("WH_VOICE_QUOTA_RATIO") || 0.7);
export type TrafficClass = "voice" | "background";

export interface ClassedRateLimitResult extends RateLimitResult {
  cap_for_class: number;
  traffic_class: TrafficClass;
}

/** Check a per-hive cap PARTITIONED by traffic class. Voice and background
 *  get separate ceilings inside the same hive bucket. Background bursts
 *  cannot starve voice. */
export async function checkClassedRateLimit(
  db:           SupabaseClient,
  hiveId:       string,
  trafficClass: TrafficClass,
  globalCap:    number = DEFAULT_RATE_LIMIT_PER_HOUR,
): Promise<ClassedRateLimitResult> {
  if (!hiveId) {
    return {
      allowed:        true,
      remaining:      globalCap,
      cap_for_class:  globalCap,
      traffic_class:  trafficClass,
    };
  }
  // The class cap is a share of the global cap.
  const ratio = trafficClass === "voice" ? VOICE_QUOTA_RATIO : (1 - VOICE_QUOTA_RATIO);
  const capForClass = Math.max(1, Math.floor(globalCap * ratio));

  // Use the existing per-hive bucket; the class ceiling is enforced ON TOP.
  // Background callers are also allowed to "borrow" up to the global cap
  // when voice usage is low, but voice callers always have their share
  // reserved (their check gates on capForClass even if global usage is low).
  const result = await checkAIRateLimit(db, hiveId, globalCap);
  // For voice: must have remaining ≥ (globalCap - capForClass) — i.e. at
  // least the bg-share-floor must still be available. For background:
  // total usage must not exceed (globalCap - voice-share-reservation).
  const used = globalCap - result.remaining;
  const bgFloor = globalCap - capForClass;  // floor that background usage must not push BELOW for voice's share

  let allowed = result.allowed;
  if (trafficClass === "background") {
    // Background must leave the voice reservation intact.
    const voiceReservation = Math.floor(globalCap * VOICE_QUOTA_RATIO);
    if (used > (globalCap - voiceReservation)) allowed = false;
  } else {
    // Voice gets its share regardless; only deny when used > globalCap.
    allowed = used <= globalCap;
  }

  return {
    allowed,
    remaining:      result.remaining,
    cap_for_class:  capForClass,
    traffic_class:  trafficClass,
  };
}
