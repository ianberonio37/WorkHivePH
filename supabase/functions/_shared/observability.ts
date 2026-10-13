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

//
// ★EVERY MODEL CALL LEAVES ONE RECORD, ON THE ANSWER PATH TOO (LM-O, LM544, 2026-10-08). This wrapper also opens
// the request's model-call scope (_shared/model-calls.ts): the chain reports each call that served, and when the
// handler returns, settleModelCalls writes one ai_cost_log row per call with fn, hive, user, provider, model,
// tokens, latency, outcome and the trace id the reply carried (its x-wh-trace header). Before this, a function
// that answered left nothing an operator could read - wh_traces got a row only on an unhandled throw, and the
// only trace of a served call was the edge stdout line "[ai-chain] served by ...". The write is best-effort and
// runs after the reply is built (EdgeRuntime.waitUntil when the runtime has it): it can never change the reply.
// Each row also says what KIND of call it was (generation / embedding / rerank / transcription / speech), the slots
// the chain asked (providers_tried), the audio seconds of a transcription, and whether it was LATE (finished after
// the function stopped waiting or after the reply) - including a chain that exhausted every provider, which is one
// failed row (2026-10-08, migration 20261008000005).

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";
import { beginRequest, fail, newTraceId } from "./envelope.ts";
import { trackError } from "./error-tracker.ts";
import { newModelCallScope, takeModelCallRows, withModelCallScope, type ModelCallScope } from "./model-calls.ts";

// the same LOCAL test as ai-chain.ts's _AI_CHAIN_LOCAL: a local stack's functions reach postgres through kong; prod is
// *.supabase.co, where a request-asked test behaviour (x-wh-walk-no-model) is never honoured
const _OBS_LOCAL = /\/\/(kong|localhost|127\.0\.0\.1)(:|\/|$)/.test(Deno.env.get("SUPABASE_URL") || "");

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
    const modelCalls = newModelCallScope(route);
    // ★A WALK SPENDS NO MODEL CALL (model-calls.ts ModelCallScope.no_model): local runtime only, asked per request
    if (_OBS_LOCAL && req.headers.get("x-wh-walk-no-model") === "1") modelCalls.no_model = true;
    let res: Response;
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
      res = await withModelCallScope(modelCalls, () => handler(req));
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
        res = fail(ctx, "unhandled_error", "Something went wrong on our side. Try again in a moment.", { status: 500 });
      } catch {
        // Envelope minting failed -> bare 500 so the request never hangs.
        res = new Response(
          JSON.stringify({
            ok: false,
            error: { code: "unhandled_error", message: "Something went wrong on our side. Try again in a moment." },
            trace_id: ctx?.trace_id,
          }),
          { status: 500, headers: { "Content-Type": "application/json", "x-wh-trace": ctx?.trace_id || "" } },
        );
      }
    }
    // the model calls this request made (answers, refusals after a call, and a throw after a call alike)
    await settleModelCalls(modelCalls, req, res);
    return res;
  };
}

// ai_cost_log_trace_id_shape admits these two shapes (the 16-hex request id, and agentic-rag-loop's uuid trace)
const TRACE_ID_SHAPE = /^(?:[0-9a-f]{8,32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/;
const MODEL_CALL_WRITE_BUDGET_MS = 3000;

/** The id the page received: the reply's x-wh-trace (tracedReply / ok() / fail() set it), else the id the request
 *  carried or tracedReply noted, else a fresh one so the calls of one request still group together. */
function replyTraceId(scope: ModelCallScope, req: Request, res: Response | undefined): string {
  const fromReply = (res?.headers.get("x-wh-trace") || "").trim();
  if (TRACE_ID_SHAPE.test(fromReply)) return fromReply;
  if (scope.trace_id && TRACE_ID_SHAPE.test(scope.trace_id)) return scope.trace_id;
  const inbound = (req.headers.get("x-wh-trace") || "").trim();
  if (/^[a-f0-9]{8,32}$/.test(inbound)) return inbound;
  return newTraceId();
}

/** The person behind the bearer, VERIFIED by auth (never decoded from the token), for a function that noted none. */
async function bearerUser(db: SupabaseClient, req: Request): Promise<string | null> {
  const h = req.headers.get("authorization") || "";
  const bearer = /^bearer\s+/i.test(h) ? h.replace(/^bearer\s+/i, "").trim() : "";
  if (!bearer || bearer === (Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "\0")) return null;
  try {
    const { data } = await db.auth.getUser(bearer);
    return data?.user?.id ?? null;
  } catch {
    return null;
  }
}

// columns 20261008000005 added; a function that reaches a database without them still records the call
const RECORD_V2_COLUMNS = ["kind", "providers_tried", "audio_seconds", "late"];

async function writeModelCalls(scope: ModelCallScope, req: Request): Promise<void> {
  let rows = takeModelCallRows(scope, scope.trace_id);
  if (!rows.length) return;
  const db = obsClient();
  if (!db) {
    console.warn(JSON.stringify({ level: "warn", route: scope.fn, trace_id: scope.trace_id,
      msg: "model_call_record_unwritten: no service credentials", calls: rows.length }));
    return;
  }
  if (scope.caller.auth_uid === undefined && rows.some((r) => r.auth_uid === null)) {
    const uid = await bearerUser(db, req);
    scope.caller.auth_uid = uid;
    for (const r of rows) if (r.auth_uid === null) r.auth_uid = uid;
  }
  // a hive the request only CLAIMED is stamped once the verified user is proven an active member of it
  const claimed = scope.caller.claimed_hive_id;
  if (claimed && scope.caller.hive_id === undefined && rows.some((r) => r.hive_id === null && r.auth_uid)) {
    const uid = rows.find((r) => r.auth_uid)?.auth_uid as string;
    // canonical-allow: v_worker_truth is the canonical hive-scoped identity view (a row == an active membership)
    const { data: mem } = await db.from("v_worker_truth").select("worker_name")
      .eq("auth_uid", uid).eq("hive_id", claimed).eq("hive_status", "active").maybeSingle();
    if (mem) for (const r of rows) if (r.hive_id === null && r.auth_uid === uid) r.hive_id = claimed;
  }
  // canonical-allow: ai_cost_log is the per-call model ledger (one row per model call, written here only)
  let { error } = await db.from("ai_cost_log").insert(rows);
  if (error && (error.code === "PGRST204" || error.code === "42703")) {
    // a database the kind/late migration has not reached yet: keep the call, drop the columns it does not have
    rows = rows.map((r) => Object.fromEntries(Object.entries(r).filter(([k]) => !RECORD_V2_COLUMNS.includes(k))));
    ({ error } = await db.from("ai_cost_log").insert(rows));
  }
  if (error && error.code === "23503") {
    // a hive or account deleted mid-request: keep the call, drop the key that no longer resolves
    ({ error } = await db.from("ai_cost_log").insert(rows.map((r) => ({ ...r, hive_id: null, auth_uid: null }))));
  }
  if (error) {
    console.warn(JSON.stringify({ level: "warn", route: scope.fn, trace_id: scope.trace_id,
      msg: `model_call_record_failed: ${error.message}`, calls: rows.length }));
  }
}

/** Bounded + fail-quiet; handed to EdgeRuntime.waitUntil when the runtime has it, so the reply is not held. */
function runModelCallWrite(scope: ModelCallScope, req: Request): Promise<void> {
  let timer: number | undefined;
  const bounded = Promise.race([
    writeModelCalls(scope, req).catch((e) => {
      console.warn(JSON.stringify({ level: "warn", route: scope.fn, trace_id: scope.trace_id,
        msg: `model_call_record_threw: ${String(e).slice(0, 200)}` }));
    }),
    new Promise<void>((r) => { timer = setTimeout(r, MODEL_CALL_WRITE_BUDGET_MS); }),
  ]).finally(() => { if (timer !== undefined) clearTimeout(timer); });
  const rt = (globalThis as { EdgeRuntime?: { waitUntil?: (p: Promise<unknown>) => void } }).EdgeRuntime;
  if (rt && typeof rt.waitUntil === "function") {
    try { rt.waitUntil(bounded); return Promise.resolve(); } catch { /* empty-catch-allow: fall back to awaiting */ }
  }
  return bounded;
}

/** Close the request's model-call scope: stamp the reply's trace id and write the calls it collected. A call that
 *  serves after this (a promise the handler did not await) is written on its own as it lands. Never throws. */
export async function settleModelCalls(scope: ModelCallScope, req: Request, res: Response | undefined): Promise<void> {
  try {
    scope.trace_id = replyTraceId(scope, req, res);
    scope.closed = true;
    // a request that asked for no model call attempted none: a logAICost "failed" row after its "{}" would record a
    // call that never happened (ModelCallScope.no_model)
    if (scope.no_model) { scope.calls.length = 0; return; }
    scope.late = (s) => { void runModelCallWrite(s, req); };
    if (scope.calls.length) await runModelCallWrite(scope, req);
  } catch { /* empty-catch-allow: a record must never break the reply it describes */ }
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
    return fail(ctx, code, "Something went wrong on our side. Try again in a moment.", { status: 500 });
  } catch {
    return new Response(
      JSON.stringify({ ok: false, error: { code, message: "Something went wrong on our side. Try again in a moment." }, trace_id: ctx?.trace_id }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
}
