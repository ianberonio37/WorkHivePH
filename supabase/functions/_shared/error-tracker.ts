// _shared/error-tracker.ts
// Sentry-equivalent error aggregation scaffold for WorkHive edge fns
// (P1 roadmap 2026-05-27 turn 7, L/G2 cell scaffolding).
//
// Today: writes errors to wh_traces with an `error_code` set. When a Sentry
// DSN is provisioned (P2), swap the implementation to also post to Sentry's
// envelope endpoint. Callers don't change.
//
// Usage:
//   import { trackError } from "../_shared/error-tracker.ts";
//   try { ... } catch (e) {
//     await trackError(db, ctx, "agent_dispatch_failed", e, { agent, target_fn: route.fn });
//     return fail(ctx, "agent_dispatch_failed", ...);
//   }
//
// Cost: one row write per error. wh_traces has a hive-scoped RLS read
// policy + service-role write, so this is safe to call from any fn.

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import type { RequestContext } from "./envelope.ts";

export interface ErrorContext {
  trace_id?: string;
  route?:    string;
  hive_id?:  string | null;
  user_id?:  string | null;
}

export async function trackError(
  db: SupabaseClient,
  ctx: RequestContext | ErrorContext | null,
  errorCode: string,
  err: unknown,
  extra: Record<string, unknown> = {},
): Promise<void> {
  const trace_id = ctx?.trace_id ?? null;
  const route    = ctx?.route    ?? "unknown";
  const hive_id  = ctx?.hive_id  ?? null;
  const user_id  = (ctx as any)?.user_id ?? null;
  const message  = err instanceof Error ? err.message : String(err);

  // Always log to stderr first — even if the DB write fails we still have
  // the trace in Supabase logs.
  console.error(JSON.stringify({
    ts:        new Date().toISOString(),
    level:     "error",
    trace_id, route, hive_id, user_id,
    error_code: errorCode,
    msg:        message.slice(0, 500),
    ...extra,
  }));

  // canonical-allow: wh_traces is the observability spine table (see _shared/envelope.ts).
  try {
    await db.from("wh_traces").insert({
      trace_id:   trace_id || crypto.randomUUID().replace(/-/g, "").slice(0, 16),
      route,
      hive_id,
      user_id,
      status:     500,
      error_code: errorCode,
      latency_ms: null,
      model_chain: [],
    });
  } catch (_) { /* fail-quiet: error tracking must never throw */ void 0; }
}

/** Returns the wh_traces error count over the last `windowMin` minutes
 *  for a given route + hive. Powers error-budget calculations. */
export async function errorCount(
  db: SupabaseClient,
  route: string,
  hiveId: string | null,
  windowMin: number = 60,
): Promise<number> {
  const since = new Date(Date.now() - windowMin * 60 * 1000).toISOString();
  // canonical-allow: wh_traces is observability infrastructure.
  let q = db.from("wh_traces").select("trace_id", { count: "exact", head: true })
    .gte("created_at", since).eq("route", route).not("error_code", "is", null);
  if (hiveId) q = q.eq("hive_id", hiveId);
  const { count } = await q;
  return count ?? 0;
}
