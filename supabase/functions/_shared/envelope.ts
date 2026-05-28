// _shared/envelope.ts
// Standard response envelope for every WorkHive edge function.
// Shape:
//   { ok, data, error, trace_id, latency_ms, model_chain, hive_id, route, served_at }
//
// Why a single envelope: today every fn returns its own ad-hoc shape, which
// makes frontend retry/fallback logic re-implement parsing per route. A single
// envelope lets the frontend treat any edge fn uniformly + lets gates assert
// contract conformance from a single helper.
//
// Usage (inside an edge fn):
//   import { ok, fail, beginRequest } from "../_shared/envelope.ts";
//   const ctx = beginRequest(req, { route: "ai-gateway" });
//   try {
//     const data = await doWork(ctx);
//     return ok(ctx, data);
//   } catch (e) {
//     return fail(ctx, "internal_error", e?.message ?? "unknown");
//   }
//
// The envelope is intentionally JSON-stable: only optional fields are
// omitted, no field is ever renamed across versions.

import { getCorsHeaders } from "./cors.ts";

export interface RequestContext {
  trace_id:    string;
  route:       string;
  started_at:  number;            // performance.now()
  hive_id?:    string;
  user_id?:    string;
  model_chain: string[];          // appended to as ai-chain.ts fires
  origin?:     string;
  cors:        Record<string, string>;  // dynamic per-request CORS (doctrine: never static origin)
}

export interface Envelope<T = unknown> {
  ok:           boolean;
  data?:        T;
  error?:       { code: string; message: string; detail?: unknown };
  trace_id:     string;
  latency_ms:   number;
  model_chain?: string[];
  hive_id?:     string;
  route:        string;
  served_at:    string;           // ISO timestamp
}

/** Generate a 16-char trace-id (no dashes — easier to grep across logs). */
export function newTraceId(): string {
  const a = crypto.getRandomValues(new Uint8Array(8));
  return Array.from(a, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** Extract or mint a trace-id from request headers (frontend should pass `x-wh-trace`). */
export function beginRequest(
  req: Request,
  opts: { route: string; hive_id?: string; user_id?: string },
): RequestContext {
  const inbound = req.headers.get("x-wh-trace") || "";
  const traceId = /^[a-f0-9]{8,32}$/.test(inbound) ? inbound : newTraceId();
  return {
    trace_id:    traceId,
    route:       opts.route,
    started_at:  performance.now(),
    hive_id:     opts.hive_id,
    user_id:     opts.user_id,
    model_chain: [],
    origin:      req.headers.get("origin") || undefined,
    cors:        getCorsHeaders(req),
  };
}

/** Record that a model in the chain was tried (success or fallback). */
export function recordModelHop(ctx: RequestContext, model: string): void {
  ctx.model_chain.push(model);
}

function baseEnvelope(ctx: RequestContext): Omit<Envelope, "ok"> {
  return {
    trace_id:    ctx.trace_id,
    latency_ms:  Math.round(performance.now() - ctx.started_at),
    model_chain: ctx.model_chain.length ? ctx.model_chain : undefined,
    hive_id:     ctx.hive_id,
    route:       ctx.route,
    served_at:   new Date().toISOString(),
  };
}

/** Successful response — `data` is whatever the caller produced. */
export function ok<T>(ctx: RequestContext, data: T, extraHeaders?: Record<string, string>): Response {
  const body: Envelope<T> = { ok: true, data, ...baseEnvelope(ctx) };
  return new Response(JSON.stringify(body), {
    status:  200,
    headers: {
      ...ctx.cors,
      "Content-Type": "application/json",
      "x-wh-trace":   ctx.trace_id,
      ...(extraHeaders || {}),
    },
  });
}

/** Failure response — `code` is a stable machine-readable error code. */
export function fail(
  ctx: RequestContext,
  code: string,
  message: string,
  opts: { status?: number; detail?: unknown; extraHeaders?: Record<string, string> } = {},
): Response {
  const status = opts.status ?? 500;
  const body: Envelope = {
    ok:    false,
    error: { code, message, detail: opts.detail },
    ...baseEnvelope(ctx),
  };
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      ...ctx.cors,
      "Content-Type": "application/json",
      "x-wh-trace":   ctx.trace_id,
      ...(opts.extraHeaders || {}),
    },
  });
}
