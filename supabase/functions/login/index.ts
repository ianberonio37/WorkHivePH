// login — server-side brute-force-protected sign-in proxy (Arc I · I7/A).
//
// THE ONE FRONT DOOR for password sign-in. A client-side "lock after N tries" is bypassable security
// theater (an attacker POSTs /auth/v1/token directly with the anon key), so the lockout MUST live here,
// server-side, before the credentials reach GoTrue:
//   1. check_login_lockout(identifier, ip)  -> if locked, 423 (never touches GoTrue; no oracle for the attacker)
//   2. forward to GoTrue /auth/v1/token?grant_type=password
//   3. on invalid creds -> record_login_failure (trips lockout at the threshold) -> 400 (generic)
//      on success        -> clear_login_attempts -> return the real GoTrue session
//
// ENUMERATION-SAFE: failures are recorded for ANY identifier (existing or not) and the messages are generic,
// so "valid-but-locked" is indistinguishable from "unknown user". Keyed on (identifier, ip) so a shared office
// NAT isn't locked out by one user, and one attacker IP spraying many usernames still trips per-(id,ip).
//
// Thresholds are env-tunable (WH_LOGIN_MAX_ATTEMPTS / WH_LOGIN_WINDOW_MIN / WH_LOGIN_LOCKOUT_MIN). verify_jwt
// is false (pre-auth by nature); the fn uses the SERVICE ROLE only to call the lockout RPCs (service-role-only
// grants) — it never exposes the service key to the client.
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { logRequestStart } from "../_shared/logger.ts";

const MAX_ATTEMPTS = Number(Deno.env.get("WH_LOGIN_MAX_ATTEMPTS") || 5);
const WINDOW_MIN   = Number(Deno.env.get("WH_LOGIN_WINDOW_MIN")   || 15);
const LOCKOUT_MIN  = Number(Deno.env.get("WH_LOGIN_LOCKOUT_MIN")  || 15);

function clientIp(req: Request): string {
  return (req.headers.get("x-forwarded-for") || "").split(",")[0].trim() || "";
}

serve(async (req: Request) => {
  const cors = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  logRequestStart(req, "login");
  const json = (code: number, body: unknown) =>
    new Response(JSON.stringify(body), { status: code, headers: { ...cors, "Content-Type": "application/json" } });

  if (req.method !== "POST") return json(405, { error: "method_not_allowed" });

  let email = "", password = "";
  try {
    const b = await req.json();
    email = String(b.email ?? b.username ?? "").trim();
    password = String(b.password ?? "");
  } catch { return json(400, { error: "invalid_request" }); }
  if (!email || !password) return json(400, { error: "missing_credentials" });

  const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
  const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const ANON_KEY     = Deno.env.get("SUPABASE_ANON_KEY")!;
  const ip = clientIp(req);
  const admin = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } });

  // 1. lockout gate (before GoTrue — a locked identifier never reaches the auth server)
  try {
    const { data: lk } = await admin.rpc("check_login_lockout", { p_identifier: email, p_ip: ip });
    const row = Array.isArray(lk) ? lk[0] : lk;
    if (row?.locked) {
      return json(423, { error: "account_locked",
        message: "Too many failed attempts. Try again later.",
        retry_after_seconds: row.retry_after_seconds ?? LOCKOUT_MIN * 60 });
    }
  } catch (_e) { /* lockout store unreachable — fail OPEN to GoTrue (availability), prod infra still limits */ }

  // 2. forward to GoTrue
  let gotrueCode = 500; let gotrueBody: unknown = { error: "server_error" };
  try {
    const r = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "apikey": ANON_KEY },
      body: JSON.stringify({ email, password }),
    });
    gotrueCode = r.status;
    gotrueBody = await r.json().catch(() => ({}));
  } catch (_e) {
    return json(502, { error: "auth_upstream_unreachable" });
  }

  // 3. record / clear by outcome
  if (gotrueCode === 200) {
    try { await admin.rpc("clear_login_attempts", { p_identifier: email, p_ip: ip }); } catch (_e) { /* best-effort */ }
    return json(200, gotrueBody);  // the real GoTrue session ({access_token, refresh_token, user, ...})
  }
  // any non-200 = failed credential attempt → count it
  let remaining: number | undefined;
  try {
    const { data: rec } = await admin.rpc("record_login_failure", {
      p_identifier: email, p_ip: ip, p_max_attempts: MAX_ATTEMPTS,
      p_window_minutes: WINDOW_MIN, p_lockout_minutes: LOCKOUT_MIN });
    const row = Array.isArray(rec) ? rec[0] : rec;
    if (row?.locked) {
      return json(423, { error: "account_locked",
        message: "Too many failed attempts. Try again later.", retry_after_seconds: LOCKOUT_MIN * 60 });
    }
    remaining = row?.fail_count != null ? Math.max(0, MAX_ATTEMPTS - row.fail_count) : undefined;
  } catch (_e) { /* best-effort */ }
  // generic invalid-credentials (enumeration-safe; do not echo GoTrue internals)
  return json(gotrueCode === 400 ? 400 : gotrueCode,
    { error: "invalid_credentials", message: "Wrong username or password.",
      ...(remaining !== undefined ? { attempts_remaining: remaining } : {}) });
});
