// _shared/health.ts
// Standard /health sub-route helper. Drop-in for any edge fn:
//
//   import { handleHealth } from "../_shared/health.ts";
//   const h = handleHealth(req, "ai-gateway", async () => ({
//     deps: [
//       { name: "supabase", ok: true },
//       { name: "groq",     ok: await pingGroq() },
//     ],
//   }));
//   if (h) return h;   // matched + handled
//
// Returns null if the request was not a /health probe — fall through to
// the rest of your handler.

import { getCorsHeaders } from "./cors.ts";
// which code this function is (tools/stamp_functions.py): reported as `build` so a running function serving old code - a
// stale runtime cache, or not redeployed after a _shared change - is caught by tools/verify_function_builds.py (2026-10-26)
import { BUILD_STAMPS } from "./build_stamps.ts";

export interface HealthDep {
  name:    string;
  ok:      boolean;
  latency_ms?: number;
  detail?: string;
}

export interface HealthCheck {
  deps: HealthDep[];
}

export function isHealthRequest(req: Request): boolean {
  try {
    const url = new URL(req.url);
    if (url.pathname.endsWith("/health")) return true;
    if (url.searchParams.get("probe") === "health") return true;
  } catch { /* fall through */ }
  return false;
}

export async function handleHealth(
  req:     Request,
  surface: string,
  probe:   () => Promise<HealthCheck>,
): Promise<Response | null> {
  if (!isHealthRequest(req)) return null;
  const corsHeaders = getCorsHeaders(req);  // dynamic per-request origin (doctrine: never static)
  const t0 = performance.now();
  let result: HealthCheck;
  try {
    result = await probe();
  } catch (e) {
    console.error(`health check failed for ${surface}:`, String(e));
    return new Response(JSON.stringify({
      // the exception text is the operator's, and it goes to the log; the payload carries a code (2026-09-06)
      ok: false, surface, error: "check_failed", build: BUILD_STAMPS[surface] ?? null, checked_at: new Date().toISOString(),
    }), { status: 503, headers: { ...corsHeaders, "Content-Type": "application/json" } });
  }
  const allOk = result.deps.every((d) => d.ok);
  const anyOk = result.deps.some((d) => d.ok);
  const status = allOk ? "ok" : (anyOk ? "degraded" : "down");
  return new Response(JSON.stringify({
    ok:         allOk,
    surface,
    build:      BUILD_STAMPS[surface] ?? null,
    status,
    deps:       result.deps,
    latency_ms: Math.round(performance.now() - t0),
    checked_at: new Date().toISOString(),
  }), {
    status:  allOk ? 200 : 503,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}
