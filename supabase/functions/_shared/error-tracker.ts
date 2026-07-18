// _shared/error-tracker.ts
// Sentry-equivalent error aggregation scaffold for WorkHive edge fns
// (P1 roadmap 2026-05-27 turn 7, L/G2 cell scaffolding).
//
// Today: writes errors to wh_traces with an `error_code` set AND (when a GlitchTip/
// Sentry DSN is provisioned via the GLITCHTIP_DSN env var) posts the error to the
// GlitchTip ingest endpoint so it appears as a grouped, stack-trace-bearing issue in
// the App-Errors Grafana board. Callers don't change; if the DSN is unset the GlitchTip
// post is skipped (fail-quiet), so this is safe with or without GlitchTip running.
// (Grafana G4.3 app-error observability, 2026-07-18 — the "P2 swap" this scaffold noted.)
//
// Usage:
//   import { trackError } from "../_shared/error-tracker.ts";
//   try { ... } catch (e) {
//     await trackError(db, ctx, "agent_dispatch_failed", e, { agent, target_fn: route.fn });
//     return fail(ctx, "agent_dispatch_failed", ...);
//   }
//
// Cost: one row write per error + (if DSN set) one fire-and-forget HTTP POST. wh_traces
// has a hive-scoped RLS read policy + service-role write, so this is safe from any fn.

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import type { RequestContext } from "./envelope.ts";

export interface ErrorContext {
  trace_id?: string;
  route?:    string;
  hive_id?:  string | null;
  user_id?:  string | null;
}

/** Post an error to GlitchTip (Sentry-compatible) if GLITCHTIP_DSN is configured.
 *  DSN form: http(s)://<public_key>@<host>/<project_id>. Fail-quiet by design —
 *  error tracking must never throw or block the caller's error path. */
async function reportToGlitchtip(
  errorCode: string,
  message: string,
  ctx: RequestContext | ErrorContext | null,
  extra: Record<string, unknown>,
): Promise<void> {
  try {
    const dsn = (globalThis as any).Deno?.env?.get?.("GLITCHTIP_DSN");
    if (!dsn) return;
    const m = String(dsn).match(/^(https?):\/\/([^@]+)@([^/]+)\/(\d+)$/);
    if (!m) return;
    const [, proto, key, host, projectId] = m;
    const url = `${proto}://${host}/api/${projectId}/store/`;
    const event = {
      event_id: crypto.randomUUID().replace(/-/g, ""),
      timestamp: new Date().toISOString(),
      platform: "javascript",
      level: "error",
      logentry: { message: `${errorCode}: ${message}`.slice(0, 500) },
      exception: { values: [{ type: errorCode, value: message.slice(0, 500) }] },
      transaction: ctx?.route ?? "unknown",
      server_name: "supabase-edge",
      tags: {
        error_code: errorCode,
        route: ctx?.route ?? "unknown",
        hive_id: (ctx?.hive_id ?? "none") as string,
      },
      extra,
    };
    // Short timeout so a slow/unreachable GlitchTip never delays the fn response.
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 2000);
    await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Sentry-Auth": `Sentry sentry_version=7, sentry_key=${key}, sentry_client=workhive-edge/1.0`,
      },
      body: JSON.stringify(event),
      signal: ctrl.signal,
    }).finally(() => clearTimeout(t));
  } catch (_) { /* fail-quiet: error tracking must never throw */ void 0; }
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

  // Also surface to GlitchTip (grouped issues + App-Errors Grafana board) when a DSN
  // is configured. No-op + fail-quiet when GLITCHTIP_DSN is unset.
  await reportToGlitchtip(errorCode, message, ctx, extra);
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
