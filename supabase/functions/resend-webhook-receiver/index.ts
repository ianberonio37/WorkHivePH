/**
 * resend-webhook-receiver — asynchronous delivery outcomes for sent reports.
 *
 * WHY THIS EXISTS. report-sender already reports a SEND-TIME rejection: a bad address comes back
 * from the API call itself and the sender sees `failed: Invalid \`to\` field`. But most real
 * undeliverables are not send-time. A full mailbox, a retired address, a domain that greylists and
 * then gives up: the API returns 200, the supervisor sees "sent", and the report never lands. That
 * outcome arrives minutes or hours later as a webhook, and WorkHive had nowhere to receive it.
 *
 * Configure in the Resend dashboard (Webhooks -> Add endpoint):
 *   https://[project].supabase.co/functions/v1/resend-webhook-receiver
 * and set RESEND_WEBHOOK_SECRET to the signing secret it shows.
 *
 * Until that endpoint is registered nothing will call this, which is exactly why the correlation
 * key had to be fixed first: send-report-email now writes `[resend_id=...]` into its automation_log
 * detail, so an event that arrives later can be joined to the send that caused it.
 *
 * Resend signs with Svix headers:
 *   svix-id, svix-timestamp, svix-signature ("v1,<base64>" — possibly several, space separated)
 *   signed payload: "{svix-id}.{svix-timestamp}.{raw_body}"
 *   secret: "whsec_<base64>" — the part after the underscore is the base64 key
 *
 * Events handled: email.bounced, email.complained, email.delivery_delayed.
 */

import { serveObserved } from "../_shared/observability.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { beginRequest, ok, fail } from "../_shared/envelope.ts";
import { log } from "../_shared/logger.ts";
import { handleHealth } from "../_shared/health.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";

function b64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/**
 * Constant-time compare. A plain === leaks how many leading bytes matched through timing, which is
 * enough to forge a signature one byte at a time.
 */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function verifySvix(
  body: string, id: string, ts: string, sigHeader: string, secret: string,
): Promise<boolean> {
  if (!body || !id || !ts || !sigHeader || !secret) return false;

  // Replay window: Svix recommends rejecting anything older than five minutes.
  const age = Math.abs(Math.floor(Date.now() / 1000) - Number(ts));
  if (!Number.isFinite(age) || age > 300) return false;

  const keyB64 = secret.startsWith("whsec_") ? secret.slice(6) : secret;
  const key = await crypto.subtle.importKey(
    "raw", b64ToBytes(keyB64), { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(`${id}.${ts}.${body}`));
  const expected = btoa(String.fromCharCode(...new Uint8Array(mac)));

  // The header may carry several versioned signatures during a secret rotation; any match passes.
  return sigHeader.split(" ").some((part) => {
    const [ver, sig] = part.split(",");
    return ver === "v1" && sig !== undefined && timingSafeEqual(sig, expected);
  });
}

const HANDLED: Record<string, string> = {
  "email.bounced":         "bounced",
  "email.complained":      "marked as spam",
  "email.delivery_delayed": "delayed",
};

serveObserved("resend-webhook-receiver", async (req: Request) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  // Arc T/T1 liveness, the same probe every other fn on this platform exposes. It ships
  // BEFORE the body is read: /health is a GET with no Svix headers, so letting it fall through
  // would consume the request body and then fail signature verification -- a health check that
  // reports a webhook as broken is worse than none.
  // It reports whether the SIGNING SECRET is present, because that is this function's real
  // readiness: without RESEND_WEBHOOK_SECRET it authenticates nothing and fails closed on every
  // event, which is the intended degrade but is invisible from outside.
  const _health = await handleHealth(req, "resend-webhook-receiver", async () => ({
    deps: [
      { name: "signing_secret", ok: Boolean(Deno.env.get("RESEND_WEBHOOK_SECRET")) },
      { name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) },
    ],
  }));
  if (_health) return _health;

  const ctx = beginRequest(req, { route: "resend-webhook-receiver" });

  const body = await req.text();
  const secret = Deno.env.get("RESEND_WEBHOOK_SECRET") || "";

  const valid = await verifySvix(
    body,
    req.headers.get("svix-id") || "",
    req.headers.get("svix-timestamp") || "",
    req.headers.get("svix-signature") || "",
    secret,
  );
  if (!valid) {
    // Deliberately terse: a detailed reason tells a forger which half they got wrong.
    // log is an OBJECT of level methods (logger.ts:44), not a callable — a bare log(...) here was a
    // TypeError waiting for the first rejected webhook; the structured-log ratchet caught it pre-deploy.
    log.warn(ctx, "rejected unsigned or stale webhook");
    return fail(ctx, "invalid_signature", "invalid signature", { status: 401 });
  }

  let evt: Record<string, unknown>;
  try { evt = JSON.parse(body); }
  catch {
    return fail(ctx, "invalid_json", "invalid json", { status: 400 });
  }

  const type  = String(evt.type || "");
  const outcome = HANDLED[type];
  // An unhandled event is ACKed, not errored: returning non-2xx makes Resend retry something we
  // will never handle, and a retry storm is worse than an ignored event.
  if (!outcome) {
    return ok(ctx, { ignored: type });
  }

  const data      = (evt.data || {}) as Record<string, unknown>;
  const messageId = String(data.email_id || data.id || "");
  const to        = Array.isArray(data.to) ? data.to.join(", ") : String(data.to || "unknown");
  const reason    = String(data.reason || (data.bounce as Record<string, unknown>)?.message || "");

  const db = createClient(SUPABASE_URL, SERVICE_KEY);

  // Resolve the hive from the send this event belongs to. Without the resend_id written by
  // send-report-email there is nothing to join on, so the row is still recorded (an undeliverable
  // report matters more than its tidiness) but its hive stays null and it will not reach a board.
  let hiveId: string | null = null;
  if (messageId) {
    const { data: sent } = await db
      .from("automation_log")
      .select("hive_id")
      .eq("job_name", "send_report_email")
      // messageId comes from the webhook PAYLOAD, so it is provider-supplied input going into a
      // LIKE pattern. An unescaped % or _ would widen the match and could resolve the WRONG
      // hive for a bounce. Escape the LIKE metacharacters (and the escape char itself first).
      .ilike("detail", `%resend_id=${messageId.replace(/\\/g, "\\\\").replace(/[%_]/g, (m) => "\\" + m)}%`)
      .order("triggered_at", { ascending: false })
      .limit(1);
    hiveId = sent?.[0]?.hive_id ?? null;
  }

  await db.from("automation_log").insert({
    job_name: "report_email_bounce",
    hive_id:  hiveId,
    status:   type === "email.delivery_delayed" ? "warning" : "failure",
    detail:   `Report to ${to} ${outcome}${reason ? `: ${reason}` : ""} [resend_id=${messageId}]`,
  });

  log.info(ctx, "webhook_recorded", { type, to });
  return ok(ctx, { recorded: type });
});
