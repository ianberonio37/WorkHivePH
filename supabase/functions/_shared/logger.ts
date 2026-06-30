// _shared/logger.ts
// Structured JSON log lines (one per line, ndjson-friendly) for every edge fn.
// Replaces ad-hoc console.log("...", obj) which today produces ungreppable
// multi-line output on Supabase logs.
//
// Shape (keys ordered for column-friendly tailing):
//   { ts, level, trace_id, route, hive_id, user_id, msg, ...extra }
//
// Levels: debug | info | warn | error
// Default level = info. Set WH_LOG_LEVEL=debug to enable debug lines.

import { RequestContext } from "./envelope.ts";

const LEVELS = ["debug", "info", "warn", "error"] as const;
type Level = typeof LEVELS[number];

const ENV_LEVEL = (Deno.env.get("WH_LOG_LEVEL") || "info").toLowerCase() as Level;
const ENV_RANK  = LEVELS.indexOf(ENV_LEVEL) >= 0 ? LEVELS.indexOf(ENV_LEVEL) : 1;

function emit(level: Level, ctx: RequestContext | null, msg: string, extra?: Record<string, unknown>): void {
  if (LEVELS.indexOf(level) < ENV_RANK) return;
  const line: Record<string, unknown> = {
    ts:       new Date().toISOString(),
    level,
    trace_id: ctx?.trace_id ?? null,
    route:    ctx?.route    ?? null,
    hive_id:  ctx?.hive_id  ?? null,
    user_id:  ctx?.user_id  ?? null,
    msg,
  };
  if (extra) {
    for (const [k, v] of Object.entries(extra)) {
      if (k in line) continue;  // never let extras overwrite the spine fields
      line[k] = v;
    }
  }
  // One JSON line per log entry — works with `supabase functions logs` tail
  // and any downstream aggregator (Sentry, Vector, Vector→S3).
  const fn = level === "error" || level === "warn" ? console.error : console.log;
  try { fn(JSON.stringify(line)); }
  catch { fn(JSON.stringify({ ts: line.ts, level, msg: "log_serialize_failed" })); }
}

export const log = {
  debug: (ctx: RequestContext | null, msg: string, extra?: Record<string, unknown>) => emit("debug", ctx, msg, extra),
  info:  (ctx: RequestContext | null, msg: string, extra?: Record<string, unknown>) => emit("info",  ctx, msg, extra),
  warn:  (ctx: RequestContext | null, msg: string, extra?: Record<string, unknown>) => emit("warn",  ctx, msg, extra),
  error: (ctx: RequestContext | null, msg: string, extra?: Record<string, unknown>) => emit("error", ctx, msg, extra),
};

// Reusable per-request observability one-liner (the missing abstraction — until now each fn
// hand-wrote `log.info(ctx, "request_start", …)`, so only ~9 of 59 had it). Adds I6 observability
// with ONE call at the top of a handler:  const t0 = logRequestStart(req, "my-fn");
// …and optionally at the end:            logRequestEnd(req, "my-fn", t0, status);
// Returns a high-res start time so the end line can carry latency_ms. Never throws.
export function logRequestStart(req: Request, route: string): number {
  const t0 = (typeof performance !== "undefined" ? performance.now() : Date.now());
  try {
    const ctx = { trace_id: crypto.randomUUID().slice(0, 16), route } as unknown as RequestContext;
    emit("info", ctx, "request_start", { method: req.method });
  } catch { /* observability must never break the request */ }
  return t0;
}

export function logRequestEnd(req: Request, route: string, t0: number, status: number): void {
  try {
    const now = (typeof performance !== "undefined" ? performance.now() : Date.now());
    const ctx = { route } as unknown as RequestContext;
    emit("info", ctx, "request_end", { method: req.method, status, latency_ms: Math.round(now - t0) });
  } catch { /* never break the request */ }
}
