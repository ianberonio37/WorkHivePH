// supervisor-reset-password — Arc I I3/I (supervisor-assisted recovery, Ian's primary pick).
//
// Industrial reality: field technicians often have NO reachable email (their auth identity is a synthetic
// username@auth.workhiveph.com), so the standard email-reset link can't reach them. The hive SUPERVISOR is
// the trust anchor: they reset a worker's password in person and hand over a one-time temp password.
//
// SECURITY (this is a privileged capability, gated hard):
//   • caller must be an ACTIVE SUPERVISOR of the named hive (checkSupervisor via JWT → v_worker_truth).
//   • target must be an ACTIVE member of the SAME hive AND role='worker' — a supervisor may NOT reset another
//     supervisor (prevents a lateral takeover of a peer admin). No cross-hive reach (membership is re-checked).
//   • the password change uses the GoTrue admin API (service role) — never exposed to the client.
//   • every reset is audit-logged (who reset whom, when) to hive_audit_log.
// Returns a freshly generated temp password to the SUPERVISOR only (over their authed channel); the worker
// changes it on next sign-in (client nudge). verify_jwt stays ON (a real supervisor session is required).
import { serveObserved } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { logRequestStart } from "../_shared/logger.ts";
// A5 (FULLSTACK_COMPONENT_LIBRARY Layer A): tight per-actor limit on this privileged action.
import { checkSoloRateLimit, soloRateLimitKey } from "../_shared/rate-limit.ts";

function tempPassword(): string {
  // 14 chars, mixed classes, no ambiguous 0/O/1/l — readable when dictated in a noisy plant.
  const A = "ABCDEFGHJKMNPQRSTUVWXYZ", a = "abcdefghijkmnpqrstuvwxyz", d = "23456789", s = "!@#$%&*";
  const all = A + a + d + s; const pick = (set: string) => set[Math.floor(Math.random() * set.length)];
  const base = [pick(A), pick(a), pick(d), pick(s)];
  for (let i = 0; i < 10; i++) base.push(pick(all));
  return base.sort(() => Math.random() - 0.5).join("");
}

serveObserved("supervisor-reset-password", async (req) => {
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "supervisor-reset-password", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const cors = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  logRequestStart(req, "supervisor-reset-password");
  const json = (code: number, body: unknown) =>
    new Response(JSON.stringify(body), { status: code, headers: { ...cors, "Content-Type": "application/json" } });
  if (req.method !== "POST") return json(405, { error: "method_not_allowed" });

  let hive_id = "", target = "";
  try {
    const b = await req.json();
    hive_id = String(b.hive_id ?? "").trim();
    target = String(b.target_worker_name ?? b.worker_name ?? "").trim();
  } catch { return json(400, { error: "invalid_request" }); }
  if (!hive_id || !target) return json(400, { error: "missing_hive_or_target" });

  const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
  const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const admin = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } });
  const jwt = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");

  // 1. caller must be an ACTIVE SUPERVISOR of this hive
  const { data: who } = await admin.auth.getUser(jwt);
  if (!who?.user) return json(401, { error: "unauthenticated" });
  const actorUid = who.user.id;
  const { data: actor } = await admin.from("v_worker_truth")
    .select("role, hive_status, worker_name").eq("hive_id", hive_id).eq("auth_uid", actorUid).maybeSingle();
  if (!actor || actor.hive_status !== "active" || actor.role !== "supervisor") {
    return json(403, { error: "not_supervisor", message: "Only an active supervisor of this hive can reset a member's password." });
  }

  // A5: password resets are rare for a legit supervisor — a tight per-actor bucket
  // (5/hour, 20/day) contains a compromised supervisor account mass-resetting members.
  const _ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
  const _rl = await checkSoloRateLimit(admin, soloRateLimitKey(actorUid, _ip), 5, 20, _ip);
  if (!_rl.allowed) return json(429, { error: "rate_limited", message: "Too many password resets. Try again later." });

  // 2. target must be an ACTIVE WORKER of the SAME hive (never another supervisor; never cross-hive)
  const { data: tgt } = await admin.from("v_worker_truth")
    .select("auth_uid, role, hive_status").eq("hive_id", hive_id).eq("worker_name", target).maybeSingle();
  if (!tgt || !tgt.auth_uid) return json(404, { error: "member_not_found", message: "No such active member in this hive." });
  if (tgt.hive_status !== "active") return json(409, { error: "member_inactive" });
  if (tgt.role === "supervisor") return json(403, { error: "cannot_reset_supervisor", message: "A supervisor cannot reset another supervisor's password." });

  // 3. set a fresh temp password via the admin API (service role)
  const pw = tempPassword();
  const { error: upErr } = await admin.auth.admin.updateUserById(tgt.auth_uid, { password: pw });
  if (upErr) return json(502, { error: "reset_failed", message: upErr.message });

  // 4. audit-log the privileged action (best-effort; never block the reset on a log failure)
  try {
    await admin.from("hive_audit_log").insert({
      hive_id, action: "supervisor_password_reset", actor: actor.worker_name,
      target_type: "worker", target_id: tgt.auth_uid, target_name: target,
      meta: { actor_auth_uid: actorUid },
    });
  } catch (_e) { /* audit best-effort */ }

  return json(200, { ok: true, worker_name: target, temp_password: pw,
    message: "Temporary password set. Share it with the worker; they should change it after signing in." });
});
