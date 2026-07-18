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

// Q4 (2026-07-05): a per-DAY ceiling alongside the hourly one. The LLM is the
// scarcest free-tier resource (Groq ~9,000 req/day SHARED across all hives); an
// hourly-only cap lets a hive sit just under the hourly limit all day and still
// drain a big slice of the shared daily budget. Default 300/day/hive keeps one
// hive from monopolising the pool while staying generous for a real team.
export const DEFAULT_RATE_LIMIT_PER_DAY =
  Number(Deno.env.get("WH_RATE_LIMIT_PER_DAY_OVERRIDE") || 300);

export interface RateLimitResult {
  allowed:   boolean;
  remaining: number;
  /** Set when the DENY was due to the per-day ceiling (vs the hourly window). */
  scope?:    "hour" | "day";
}

export async function checkAIRateLimit(
  db: SupabaseClient,
  hiveId: string,
  limitPerHour: number = DEFAULT_RATE_LIMIT_PER_HOUR,
  limitPerDay:  number = DEFAULT_RATE_LIMIT_PER_DAY,
): Promise<RateLimitResult> {
  if (!hiveId) {
    // Solo-worker mode (no hive context). Allow without tracking — these
    // calls are by definition single-user and bounded.
    return { allowed: true, remaining: limitPerHour };
  }
  const now     = Date.now();
  const hourAgo = new Date(now - 60 * 60 * 1000);
  const dayAgo  = new Date(now - 24 * 60 * 60 * 1000);
  const { data } = await db.from("ai_rate_limits")
    .select("call_count, window_start, day_count, day_window_start")
    .eq("hive_id", hiveId)
    .maybeSingle();

  // Each window resets independently once its start ages past its span.
  const hourFresh = Boolean(data && new Date(data.window_start) >= hourAgo);
  const dayFresh  = Boolean(data && data.day_window_start && new Date(data.day_window_start) >= dayAgo);
  const hourCount = hourFresh ? data!.call_count : 0;
  const dayCount  = dayFresh  ? (data!.day_count ?? 0) : 0;

  // Daily ceiling first — the scarcest budget. A hive that has burned its day is
  // blocked even when the hour is fresh.
  if (dayCount >= limitPerDay) {
    return { allowed: false, remaining: 0, scope: "day" };
  }
  if (hourCount >= limitPerHour) {
    return { allowed: false, remaining: 0, scope: "hour" };
  }
  const nowIso = new Date().toISOString();
  await db.from("ai_rate_limits").upsert({
    hive_id:          hiveId,
    call_count:       hourCount + 1,
    window_start:     hourFresh ? data!.window_start : nowIso,
    day_count:        dayCount + 1,
    day_window_start: dayFresh ? data!.day_window_start : nowIso,
  });
  return { allowed: true, remaining: limitPerHour - (hourCount + 1) };
}

export function rateLimitedResponse(
  corsHeaders: Record<string, string>,
  scope: "hour" | "day" = "hour",
): Response {
  const error = scope === "day"
    ? "Daily AI limit reached for this hive. Resets tomorrow."
    : "AI call limit reached for this hive. Try again in an hour.";
  return new Response(
    JSON.stringify({ error, scope }),
    { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } },
  );
}


// ── GLOBAL platform-wide LLM budget guard (Q6, 2026-07-05) ─────────────────
//
// The org-shared-pool layer. Every gate ABOVE keys on a tenant (hive/user/solo/
// route) — none protect the ONE resource that binds first at scale: the LLM
// provider budget is ORG-LEVEL, a single key shared across ALL tenants. Verified
// 2026 free-tier: Groq 30 RPM / 1,000 RPD good-models (org-level). Per-hive 300 +
// solo 100 caps do NOT sum-protect that shared pool (40 hives × 300 = 12k/day).
//
// This calls the ATOMIC consume_ai_global_budget() RPC (row-locked — a single hot
// counter row must not lose updates under the concurrent burst it exists to smooth;
// the per-tenant gates' read-then-upsert is racy but acceptable per-tenant, NOT here).
//
// Policy: day pool exhausted -> circuit-breaker (deny all); minute burst wall ->
// SHED background/deferrable calls, PASS interactive (voice). FAILS OPEN: a counter
// error must never block AI platform-wide.
export const DEFAULT_GLOBAL_RPM = Number(Deno.env.get("WH_GLOBAL_RPM") || 120);
export const DEFAULT_GLOBAL_RPD = Number(Deno.env.get("WH_GLOBAL_RPD") || 12000);

export interface GlobalBudgetResult {
  allowed:          boolean;
  scope?:           "global-day" | "global-minute";
  minute_remaining: number;
  day_remaining:    number;
}

/** Platform-wide LLM budget gate. Runs AFTER the per-tenant gate (so only calls a
 *  tenant is allowed to make consume the shared pool) and BEFORE the model call.
 *  `trafficClass` 'background' is shed at the per-minute wall; 'voice' passes. */
export async function checkGlobalAIBudget(
  db:           SupabaseClient,
  trafficClass: TrafficClass = "voice",
  rpm:          number = DEFAULT_GLOBAL_RPM,
  rpd:          number = DEFAULT_GLOBAL_RPD,
): Promise<GlobalBudgetResult> {
  try {
    // canonical-allow: ai_global_budget is the platform-wide LLM pool counter (rate_limit_infra), not a user-facing KPI source.
    const { data, error } = await db.rpc("consume_ai_global_budget", {
      p_rpm: rpm,
      p_rpd: rpd,
      p_is_background: trafficClass === "background",
    });
    const row = Array.isArray(data) ? data[0] : data;
    if (error || !row) {
      // Fail OPEN — a global chokepoint must never hard-fail all AI on a counter glitch.
      return { allowed: true, minute_remaining: rpm, day_remaining: rpd };
    }
    return {
      allowed:          row.allowed,
      scope:            row.scope ?? undefined,
      minute_remaining: row.minute_remaining,
      day_remaining:    row.day_remaining,
    };
  } catch {
    return { allowed: true, minute_remaining: rpm, day_remaining: rpd };
  }
}

export function globalBudgetResponse(
  corsHeaders: Record<string, string>,
  scope: "global-day" | "global-minute" = "global-minute",
): Response {
  const error = scope === "global-day"
    ? "The platform's shared AI budget for today is fully used. Please try again tomorrow."
    : "AI is handling a burst of activity right now. Please retry in a few seconds.";
  // 503 (transient, retry-soon) for the per-minute burst; 429 (rate) for the daily pool.
  const status = scope === "global-minute" ? 503 : 429;
  const extra  = scope === "global-minute" ? { "Retry-After": "5" } : {};
  return new Response(
    JSON.stringify({ error, scope }),
    { status, headers: { ...corsHeaders, "Content-Type": "application/json", ...extra } },
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
  // canonical-allow: hive_route_quotas is rate-limiter control-plane config (per-route quota), not a user-facing cross-surface KPI value — no v_*_truth wrapper applies.
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
  // canonical-allow: hive_route_calls is the rate-limiter's control-plane per-hour counter, not a user-facing cross-surface KPI value — no v_*_truth wrapper applies.
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


// ── Solo / Personal-Feature Rate Limiting (Resume Builder, 2026-06-05) ──────
//
// `checkAIRateLimit` keys on hive_id, so it does NOTHING for a solo phone
// worker with no hive — the Resume Builder's core audience. `ai_rate_limits`
// keys on hive_id (uuid); passing a synthetic key type-errors. This gate closes
// that hole: it caps a SINGLE identity (a signed-in worker by auth_uid, or — for
// an anonymous caller hitting the public fn URL since verify_jwt=false — by
// client IP) so neither an honest retry loop nor a bot can drain the free-tier
// LLM budget.
//
// Counter table: reuses ai_user_rate_limits (user_id TEXT PK) — no migration.
// Solo keys never corrupt in-hive per-user keys: a signed-in person shares ONE
// bucket across solo + hive contexts (same human — correct), and IP keys are
// namespaced `ip:` so they cannot collide with a uuid.
//
// Why auth_uid FIRST, IP only as fallback: Philippine mobile traffic is heavily
// CGNAT'd, so many distinct phone workers share one carrier IP. An IP-primary
// key would make them starve each other. auth_uid is per-person and
// collision-free; IP is the floor only for callers with no session.
//
// Residual risk (documented, acceptable pre-prod): a caller could rotate a
// spoofed auth_uid in the body to mint fresh buckets; the IP floor only engages
// when auth_uid is absent. The realistic abuse vector — an anonymous script on
// the public URL — IS floored by IP. A future hardening could layer an
// always-on IP ceiling (CGNAT-aware, higher cap) on top of the per-identity cap.

export const DEFAULT_SOLO_RATE_LIMIT_PER_HOUR =
  Number(Deno.env.get("WH_SOLO_RATE_LIMIT_OVERRIDE") || 30);

// Q4 (2026-07-05): per-day ceiling for solo/anon identities too. The public
// (verify_jwt=false) fns are the prime LLM-drain surface for a bot rotating
// under the hourly cap; 100/day/identity bounds the daily damage.
export const DEFAULT_SOLO_RATE_LIMIT_PER_DAY =
  Number(Deno.env.get("WH_SOLO_RATE_LIMIT_PER_DAY_OVERRIDE") || 100);

/** Build the namespaced solo rate-limit key from the best available identity.
 *  Prefers auth_uid (per-person); falls back to a namespaced client IP. Returns
 *  "" when neither is available (degenerate — caller should fail open, there is
 *  nothing to bucket on). */
export function soloRateLimitKey(authUid?: string | null, clientIp?: string | null): string {
  const uid = String(authUid ?? "").trim();
  if (uid) return uid;                       // per-person bucket (shared with hive ctx — same human)
  const ip = String(clientIp ?? "").trim();
  if (ip) return `ip:${ip}`;                 // namespaced so it can never collide with a uuid
  return "";
}

// I5 (2026-07-09): CGNAT-aware IP CEILING multiplier. The always-on per-IP ceiling is
// this many times the per-identity cap, so many distinct phone workers behind ONE CGNAT
// carrier IP rarely hit it, but a single IP rotating spoofed auth_uids DOES. Env-tunable.
export const SOLO_IP_CEILING_MULTIPLIER =
  Number(Deno.env.get("WH_SOLO_IP_CEILING_MULTIPLIER") || 5);

/** Check + increment ONE ai_user_rate_limits bucket (hour + day windows). Returns the
 *  gate result; does NOT increment when already over a cap. */
async function bumpSoloBucket(
  db: SupabaseClient, key: string, limitPerHour: number, limitPerDay: number,
): Promise<RateLimitResult> {
  const now     = Date.now();
  const hourAgo = new Date(now - 60 * 60 * 1000);
  const dayAgo  = new Date(now - 24 * 60 * 60 * 1000);
  // canonical-allow: ai_user_rate_limits is an infrastructure counter table (rate_limit_infra), not a KPI source.
  const { data } = await db.from("ai_user_rate_limits")
    .select("call_count, window_start, day_count, day_window_start")
    .eq("user_id", key)
    .maybeSingle();

  const hourFresh = Boolean(data && new Date(data.window_start) >= hourAgo);
  const dayFresh  = Boolean(data && data.day_window_start && new Date(data.day_window_start) >= dayAgo);
  const hourCount = hourFresh ? data!.call_count : 0;
  const dayCount  = dayFresh  ? (data!.day_count ?? 0) : 0;

  if (dayCount >= limitPerDay)   return { allowed: false, remaining: 0, scope: "day" };
  if (hourCount >= limitPerHour) return { allowed: false, remaining: 0, scope: "hour" };

  const nowIso = new Date().toISOString();
  // canonical-allow: ai_user_rate_limits infrastructure counter (see lookup site).
  await db.from("ai_user_rate_limits").upsert({
    user_id:          key,
    hive_id:          null,
    call_count:       hourCount + 1,
    window_start:     hourFresh ? data!.window_start : nowIso,
    day_count:        dayCount + 1,
    day_window_start: dayFresh ? data!.day_window_start : nowIso,
  });
  return { allowed: true, remaining: limitPerHour - (hourCount + 1) };
}

/** Per-identity rate-limit gate for solo / personal features with NO hive
 *  context. Keyed by `soloRateLimitKey(auth_uid, ip)`. Mirrors checkAIRateLimit
 *  but on ai_user_rate_limits (user_id TEXT PK), so no hive_id uuid is needed.
 *
 *  I5: pass `clientIp` to ALSO enforce an always-on CGNAT-aware IP ceiling on top of
 *  the per-identity cap. Without it, a caller rotating a spoofed auth_uid in the request
 *  body mints a fresh per-identity bucket each call and is effectively unlimited on the
 *  public (verify_jwt=false) URL. */
export async function checkSoloRateLimit(
  db:           SupabaseClient,
  identityKey:  string,
  limitPerHour: number = DEFAULT_SOLO_RATE_LIMIT_PER_HOUR,
  limitPerDay:  number = DEFAULT_SOLO_RATE_LIMIT_PER_DAY,
  clientIp:     string | null = null,
): Promise<RateLimitResult> {
  if (!identityKey) {
    // No identity AND no IP header — nothing to bucket on. Fail open; rare
    // degenerate case (no session + no x-forwarded-for).
    return { allowed: true, remaining: limitPerHour };
  }
  // Primary per-identity cap (auth_uid-first; the anon path already passes an `ip:` key).
  const primary = await bumpSoloBucket(db, identityKey, limitPerHour, limitPerDay);
  if (!primary.allowed) return primary;

  // I5: always-on CGNAT-aware IP ceiling ON TOP of the per-identity cap. Only when the
  // identity is a real uid (not already an `ip:` key — that bucket IS the primary, no
  // double count) and we have an IP to bucket on. The ceiling is well ABOVE the per-user
  // cap, so co-located phone workers rarely hit it but a rotating-uuid script does.
  const ip = String(clientIp ?? "").trim();
  if (ip && !identityKey.startsWith("ip:")) {
    const ipGate = await bumpSoloBucket(db, `ip:${ip}`,
      limitPerHour * SOLO_IP_CEILING_MULTIPLIER, limitPerDay * SOLO_IP_CEILING_MULTIPLIER);
    if (!ipGate.allowed) return { allowed: false, remaining: 0, scope: ipGate.scope };
  }
  return primary;
}

export function soloRateLimitedResponse(corsHeaders: Record<string, string>): Response {
  return new Response(
    JSON.stringify({
      error: "AI call limit reached. Please try again in an hour.",
      scope: "solo",
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
