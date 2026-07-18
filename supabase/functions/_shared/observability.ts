// _shared/observability.ts
// Arc T (T2 keystone): the shared error-AGGREGATION net for every edge fn.
//
// The gap it closes: logger.ts (56/56) already gives error VISIBILITY (stderr),
// but an UNHANDLED throw in a handler produced only Deno's generic 500 with NO
// row in wh_traces -- so the error-budget SLI (errorCount() over wh_traces)
// silently under-counted real failures. error-tracker.ts::trackError() was
// built for exactly this but had 0 adoption (dead code). This wrapper makes any
// uncaught error land a wh_traces error row AND return a clean, non-leaky
// envelope to the client -- reaching all 56 fns from one shared edit (the same
// shared-keystone leverage as the skip-link).
//
// Adoption is one line per fn (handler body unchanged):
//   import { serveObserved } from "../_shared/observability.ts";
//   serveObserved("my-fn", async (req) => { ... });   // was: serve(async (req) => { ... })
//
// Design guarantees:
//  - Transparent: success + OPTIONS + /health responses pass straight through;
//    the wrapper only engages on a thrown error (the rare path), zero overhead
//    on the happy path.
//  - Non-leaky (security): the client gets a generic message + trace_id (support
//    can correlate); the full error text/stack goes to stderr + wh_traces only,
//    never to the caller. This is stricter than fail(ctx, code, err.message).
//  - Fail-quiet: trackError() self-catches and never throws; if even minting the
//    envelope fails we still return a bare 500 so the request can never hang.

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { beginRequest, fail } from "./envelope.ts";
import { trackError } from "./error-tracker.ts";

// Lazy service-role client, created once per isolate. wh_traces has a
// service-role write policy, so the error net can always record a row.
let _obsDb: SupabaseClient | null = null;
function obsClient(): SupabaseClient | null {
  if (_obsDb) return _obsDb;
  const url = Deno.env.get("SUPABASE_URL") || "";
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
  if (!url || !key) return null; // no creds -> stderr-only (trackError still logs)
  _obsDb = createClient(url, key);
  return _obsDb;
}

/**
 * Wrap a handler so any uncaught throw is aggregated to wh_traces + returned as
 * a clean envelope. Returns a handler with the SAME `(req) => Response` shape,
 * so it is a drop-in for the argument to `serve()`.
 */
export function withObservability(
  route: string,
  handler: (req: Request) => Promise<Response>,
): (req: Request) => Promise<Response> {
  return async (req: Request): Promise<Response> => {
    try {
      // Chaos hook to PROVE the error net end-to-end (roadmap T2/T4 fault-
      // injection exit criteria). Must live INSIDE the try so it takes the same
      // catch->trackError path a real handler throw takes. Prod-safe: it needs
      // the explicit `x-wh-fault-inject` header AND either the local WH_CHAOS
      // flag OR a service-role caller (already fully trusted + RLS-bypassing).
      // An anon/user caller can never trip it; a service-role fault just yields
      // a clean 500 + one wh_traces row. This keeps the fault-walk env-free.
      if (req.headers.get("x-wh-fault-inject") && (
        Deno.env.get("WH_CHAOS") === "1" ||
        req.headers.get("authorization") === `Bearer ${Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "\0"}`
      )) {
        throw new Error(`chaos_fault_injection: ${route}`);
      }
      return await handler(req);
    } catch (err) {
      // Minimal ctx for attribution (route + trace-id + per-request CORS).
      const ctx = beginRequest(req, { route });
      const db = obsClient();
      if (db) {
        try { await trackError(db, ctx, "unhandled_error", err); }
        catch { /* the error net must never throw */ }
      } else {
        // No service creds reachable -> at least keep the stderr trace.
        console.error(JSON.stringify({
          ts: new Date().toISOString(),
          level: "error",
          route,
          trace_id: ctx.trace_id,
          error_code: "unhandled_error",
          msg: (err instanceof Error ? err.message : String(err)).slice(0, 500),
        }));
      }
      // Non-leaky client response: generic message + trace_id only.
      try {
        return fail(ctx, "unhandled_error", "An unexpected error occurred.", { status: 500 });
      } catch {
        // Envelope minting failed -> bare 500 so the request never hangs.
        return new Response(
          JSON.stringify({
            ok: false,
            error: { code: "unhandled_error", message: "An unexpected error occurred." },
            trace_id: ctx?.trace_id,
          }),
          { status: 500, headers: { "Content-Type": "application/json" } },
        );
      }
    }
  };
}

/**
 * `serve()` + `withObservability()` in one call. Drop-in replacement for
 * `serve(handler)` that adds edge-fn error aggregation with a single-line change.
 */
export function serveObserved(
  route: string,
  handler: (req: Request) => Promise<Response>,
): void {
  serve(withObservability(route, handler));
}

/**
 * T2b (shape-preserving): aggregate a HANDLED internal error to wh_traces WITHOUT
 * returning a Response — for 500 sites whose response shape must stay as-is (a
 * structured batch result like `{ok:false,written,…}`, a missing-env guard, or an
 * envelope `fail()` return). Call it, then return the fn's existing response:
 *   catch (err) { await trackHandled(req, "my-fn", "my_code", err); return <existing 500>; }
 * Fire-and-forget-safe (never throws). The trace_id lives in wh_traces + stderr.
 */
export async function trackHandled(
  req: Request,
  route: string,
  code: string,
  err: unknown,
): Promise<void> {
  const ctx = beginRequest(req, { route });
  const db = obsClient();
  if (db) {
    try { await trackError(db, ctx, code, err); } catch { /* the error net must never throw */ }
  } else {
    console.error(JSON.stringify({
      ts: new Date().toISOString(), level: "error", route, trace_id: ctx.trace_id,
      error_code: code, msg: (err instanceof Error ? err.message : String(err)).slice(0, 500),
    }));
  }
}

/**
 * T2b: aggregate a HANDLED internal error + return a non-leaky 500, for `catch`
 * sites that return their own error Response instead of letting the throw reach
 * the serveObserved wrapper. Mints its own minimal ctx (route + trace-id + CORS)
 * and service client, so a fn without envelope `ctx`/`db` in scope can adopt it
 * with one line:  `catch (err) { return await failTracked(req, "my-fn", "my_code", err); }`
 * Only for genuine 500-class failures — NOT expected 4xx validation (those stay
 * as-is). Fail-quiet: trackError self-catches; the client never sees internals.
 */
export async function failTracked(
  req: Request,
  route: string,
  code: string,
  err: unknown,
): Promise<Response> {
  const ctx = beginRequest(req, { route });
  const db = obsClient();
  if (db) {
    try { await trackError(db, ctx, code, err); } catch { /* the error net must never throw */ }
  } else {
    console.error(JSON.stringify({
      ts: new Date().toISOString(), level: "error", route, trace_id: ctx.trace_id,
      error_code: code, msg: (err instanceof Error ? err.message : String(err)).slice(0, 500),
    }));
  }
  try {
    return fail(ctx, code, "An unexpected error occurred.", { status: 500 });
  } catch {
    return new Response(
      JSON.stringify({ ok: false, error: { code, message: "An unexpected error occurred." }, trace_id: ctx?.trace_id }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
}
