// _shared/trace-reply.ts
// ★A "WRONG" COULD NOT NAME THE CALL IT JUDGED (LM-E, 2026-10-08). The "was this right?" row (utils.js whAiTrustRow)
// writes ai_reply_feedback.trace_id from the id the answering endpoint RETURNED. ai-gateway returned one on every
// answer; thirteen page surfaces called a specialist directly instead (analytics-orchestrator, shift-planner-
// orchestrator, resume-polish, voice-logbook-entry, visual-defect-capture, intelligence-report, project-orchestrator,
// scheduled-agents, engineering-calc-agent), and those functions either logged an id they never returned
// (analytics-orchestrator's beginRequest), logged a different throwaway id per line (logRequestStart's
// randomUUID().slice(0, 16) - dashed, so not even the shape the column admits), or had no id at all. Measured on the
// LM-E walk: a "wrong" on project-manager's AI-drafted lessons landed with trace_id NULL.
//
// tracedReply(route, handler) is the one place that fixes it for a function: it mints the request's trace id ONCE
// (beginRequest: adopts a well-formed inbound x-wh-trace - which is how an ai-gateway forward keeps the gateway's id
// for the whole turn - else 16 lowercase hex, the shape ai_reply_feedback_trace_id_shape admits), hands it to the
// handler for its own logging, makes every NESTED beginRequest(req) (failTracked, trackHandled) adopt the same id by
// passing the handler a request that carries it, and stamps it as a top-level `trace_id` on every JSON object reply -
// answers AND refusals - with an x-wh-trace header. A reply that already names a well-formed trace_id keeps its own.
// Preflights, /health probes, streams and non-object bodies pass through untouched.
//
//   serveObserved("my-fn", tracedReply("my-fn", async (req, trace) => {
//     log.info(trace, "request_start", { method: req.method });
//     ...
//   }));
//
// Gate: tools/validate_ai_feedback_carries_trace.py reads this file and every function wrapped by it.
//
// The same id names every model call the request makes (LM-O, 2026-10-08): it is noted into the request's model-call
// scope (serveObserved opened it), so the ai_cost_log row of each call carries the trace_id this reply returns.

import { beginRequest, type RequestContext } from "./envelope.ts";
import { isHealthRequest } from "./health.ts";
import { noteModelTrace } from "./model-calls.ts";
import { failTracked } from "./observability.ts";

const TRACE_SHAPE = /^(?:[0-9a-f]{8,32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/;

export type TracedHandler = (req: Request, trace: RequestContext) => Promise<Response>;

/** Wrap a handler so its request has ONE trace id and every JSON reply names it (see the header). */
export function tracedReply(route: string, handler: TracedHandler): (req: Request) => Promise<Response> {
  return async (req: Request): Promise<Response> => {
    const trace = beginRequest(req, { route });
    noteModelTrace(trace.trace_id);
    // a preflight or a liveness probe is not a call anyone rates: same handler, untouched reply
    if (req.method === "OPTIONS" || isHealthRequest(req)) return await handler(req, trace);
    const traced = adoptTrace(req, trace.trace_id);
    let res: Response;
    try {
      res = await handler(traced, trace);
    } catch (err) {
      // the same net serveObserved casts (trackError + a non-leaky 500), cast here so the 500 names THIS request's id
      res = await failTracked(traced, route, "unhandled_error", err);
    }
    return await stampTraceId(res, trace.trace_id);
  };
}

/** A request whose x-wh-trace is `traceId`, so a nested beginRequest(req) adopts it instead of minting a second id. */
function adoptTrace(req: Request, traceId: string): Request {
  if (req.headers.get("x-wh-trace") === traceId) return req;
  try {
    const headers = new Headers(req.headers);
    headers.set("x-wh-trace", traceId);
    return new Request(req, { headers });
  } catch {
    return req; // a request that cannot be re-headed keeps working; nested helpers mint their own id
  }
}

/** Add `trace_id` to a JSON object reply (an answer or a refusal); anything else is returned as it came. */
export async function stampTraceId(res: Response, traceId: string): Promise<Response> {
  if (res.body === null || !/\bjson\b/i.test(res.headers.get("content-type") || "")) return res;
  let body: unknown;
  try {
    body = JSON.parse(await res.clone().text());
  } catch {
    return res; // a body that is not JSON keeps its own bytes
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) return res;
  const own = (body as Record<string, unknown>).trace_id;
  const id = (typeof own === "string" && TRACE_SHAPE.test(own)) ? own : traceId;
  // every other header is kept; the length changes with the body, and the type is restated (a copied lowercase
  // content-type beside a literal Content-Type would be joined into one doubled value)
  const kept = Object.fromEntries([...res.headers].filter(([k]) => !/^content-(length|type)$/i.test(k)));
  return new Response(JSON.stringify({ ...(body as Record<string, unknown>), trace_id: id }), {
    status: res.status,
    statusText: res.statusText,
    headers: { ...kept, "x-wh-trace": id, "Content-Type": "application/json" },
  });
}
