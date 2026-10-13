// _shared/gateway-trust.ts
// ============================================================================
// GATEWAY-FORWARD TRUST (2026-10-08).
//
// ai-gateway rate-limits a person ONCE (hive + per-user, or the solo bucket) and then forwards the call
// to a specialist carrying the person's OWN JWT, so the specialist can still prove hive membership. A
// specialist that skips its own limiter on that path (to avoid counting one request twice) therefore
// cannot tell the gateway from the person by the bearer: both send the same token.
//
// voice-action-router used to take the request BODY's word for it - `gateway: true` - and any direct
// caller can put that in a body. A signed-in person calling the router directly with `gateway: true`
// skipped every limiter on it (hive, per-surface and solo) and spent free-tier model calls without bound.
//
// The proof is a header only the gateway can mint: HMAC-SHA256, keyed on the service-role key (which
// never leaves the server), over the exact Authorization value the forward carries. Bound to that bearer,
// a leaked header value is worthless with any other token and dies with the JWT. It fails CLOSED: with no
// key configured nothing is minted and nothing verifies, so a misconfigured function rate-limits.
//
// Use: ai-gateway spreads `await gatewayForwardHeaders(<the Authorization it sends>)` into the forward's
// headers; a specialist skips its own limiter ONLY when `await isTrustedGatewayForward(req)` is true.
// Never read a body field (`gateway`, `internal`, `source`...) to decide whether a limiter runs.
// ============================================================================

export const GATEWAY_FORWARD_HEADER = "x-wh-gateway-forward";
const MAC_CONTEXT = "wh-gateway-forward:v1:";

function serviceKey(): string {
  try {
    return Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
  } catch {
    return "";
  }
}

async function forwardMac(key: string, authorization: string): Promise<string> {
  const enc = new TextEncoder();
  const k = await crypto.subtle.importKey(
    "raw", enc.encode(key), { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", k, enc.encode(MAC_CONTEXT + authorization)));
  return Array.from(sig, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** The headers ai-gateway adds to a specialist forward. `authorization` is the exact Authorization value sent. */
export async function gatewayForwardHeaders(authorization: string): Promise<Record<string, string>> {
  const key = serviceKey();
  if (!key || !authorization) return {};
  return { [GATEWAY_FORWARD_HEADER]: await forwardMac(key, authorization) };
}

/** True ONLY for a call ai-gateway forwarded - and therefore already rate-limited. Fails closed. */
export async function isTrustedGatewayForward(req: Request): Promise<boolean> {
  const got = req.headers.get(GATEWAY_FORWARD_HEADER) || "";
  const authorization = req.headers.get("Authorization") || "";
  const key = serviceKey();
  if (!got || !authorization || !key) return false;
  const want = await forwardMac(key, authorization);
  if (got.length !== want.length) return false;
  let diff = 0;
  for (let i = 0; i < want.length; i++) diff |= want.charCodeAt(i) ^ got.charCodeAt(i);
  return diff === 0;
}
