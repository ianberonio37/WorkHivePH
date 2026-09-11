// capability: platform_gcash_receipt_intake
/**
 * gcash-receipt-inbound — the signal that makes top-up verification automatic.
 *
 * WHY THIS EXISTS. WorkHive has no business registration, therefore no GCash
 * merchant account, therefore no payment API and no callback. A P2P transfer to
 * the founder's personal number tells the platform nothing, so every top-up had
 * to be verified by hand: open GCash, find the reference, press Verify.
 *
 * But GCash already notifies the RECIPIENT of every payment received, by SMS and
 * by email. That notification is the missing signal. Forward it here once and a
 * matching top-up verifies itself. No merchant account, no new relationship with
 * GCash — the platform reads a receipt the founder already gets.
 *
 * WHAT THIS ENDPOINT MAY NOT DO. It does not mint credits. It records a receipt;
 * a trigger (match_gcash_receipt, mig 38) verifies the top-up the PROVIDER ALREADY
 * FILED, and only when reference AND amount agree. A forwarded notification is a
 * CLAIM — anyone who learned this URL could forge one — so the agreement of two
 * independent statements is what authorises credit, exactly as it did when a human
 * compared them. This function is a courier, not an authority.
 *
 * AUTH: HMAC-SHA256 over `${timestamp}.${rawBody}` in X-WorkHive-Signature, keyed
 * by GCASH_INBOUND_SECRET. FAIL CLOSED: no secret configured => 401, never "accept
 * unsigned". Same posture as cmms-webhook-receiver, which shipped that bug once.
 *
 * Input (either shape):
 *   { "text": "You have received PHP500.00 from JUAN D ... Ref. No. 1234567890123" }
 *   { "reference": "1234567890123", "amount": 500, "sender_name": "JUAN D" }
 * The raw text is ALWAYS stored, so a parse that gets it wrong stays recoverable.
 */
import { serveObserved } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";
import { beginRequest, ok, fail } from "../_shared/envelope.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.7";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log, logRequestStart } from "../_shared/logger.ts";

const FN_NAME = "gcash-receipt-inbound";

/* COMPOSED, not replaced. The shared helper decides the ORIGIN dynamically (a static "*" breaks
   file:// testing, where Chrome sends `Origin: null`, and every non-production client) but its
   Allow-Headers list does not know about this endpoint's signature headers. Swapping the whole block
   for getCorsHeaders(req) would have silently dropped x-workhive-signature and x-workhive-timestamp
   from the preflight, so any browser-based caller would fail on a header it is required to send.
   Take the origin decision from the platform, keep the headers this endpoint actually needs. */
function inboundCors(req: Request): Record<string, string> {
  return {
    ...getCorsHeaders(req),
    "Access-Control-Allow-Headers":
      "authorization, x-client-info, apikey, content-type, x-workhive-signature, x-workhive-timestamp",
  };
}

/** Constant-time-ish compare so a wrong signature cannot be probed byte by byte. */
function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function hmacHex(secret: string, message: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(message));
  return Array.from(new Uint8Array(sig)).map(b => b.toString(16).padStart(2, "0")).join("");
}

/**
 * Pull the reference and amount out of a GCash notification.
 *
 * The exact wording is GCash's and can change, which is precisely why raw_text is
 * stored and why a failed parse returns an error the founder can see rather than a
 * silent drop. Deliberately tolerant about spacing, currency spelling and label
 * ("Ref. No." / "Reference No" / "Ref No."), strict about the reference SHAPE — 13
 * digits, the same shape the filing form enforces, so the two can be compared at all.
 */
export function parseGcashText(text: string): { reference: string | null; amount: number | null; sender: string | null } {
  const t = (text || "").replace(/ /g, " ");
  const refM = t.match(/(?:ref(?:erence)?\.?\s*(?:no\.?|number)?\s*[:\-]?\s*)(\d{13})/i)
            || t.match(/(?<!\d)(\d{13})(?!\d)/);
  const amtM = t.match(/(?:php|₱|p)\s*([\d,]+(?:\.\d{1,2})?)/i);
  const sndM = t.match(/from\s+([A-Za-z][A-Za-z .'\-]{1,60}?)(?=\s+(?:ref|on|\.|,|$))/i);
  const amount = amtM ? Number(amtM[1].replace(/,/g, "")) : null;
  return {
    reference: refM ? refM[1] : null,
    amount: (amount != null && isFinite(amount) && amount > 0) ? amount : null,
    sender: sndM ? sndM[1].trim() : null,
  };
}

/* serveObserved, not a bare Deno.serve: an unhandled throw here leaks and is INVISIBLE to the SLO
   alerting — on the endpoint that decides whether credits get minted, silence is the worst failure
   mode available. /health answers "is the intake actually armed" without reading logs: with no
   shared secret it reports NOT ok, which is also the resting state until Ian sets one. */
serveObserved(FN_NAME, async (req: Request) => {
  const cors = inboundCors(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  /* Structured ndjson log line per request. This endpoint DECIDES WHETHER CREDITS MINT, so it is
     the last place on the platform that should be silent: a forwarder that starts sending a
     changed payload, or an attacker probing signatures, is invisible without a per-request record.
     serveObserved nets an unhandled throw; this nets the ordinary traffic around it. */
  logRequestStart(req, FN_NAME);

  const healthResp = await handleHealth(req, FN_NAME, async () => ({
    deps: [
      { name: "inbound_secret", ok: Boolean(Deno.env.get("GCASH_INBOUND_SECRET")) },
      { name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) },
    ],
  }));
  if (healthResp) return healthResp;

  /* The platform response contract: every reply carries ok/data or ok/code/message plus
     a trace id, so a caller (and the SLO dashboard) can correlate one request across
     function, logs and DB. I hand-rolled JSON here and skipped it. */
  const ctx = beginRequest(req, { route: FN_NAME });

  if (req.method !== "POST") return fail(ctx, "method_not_allowed", "That request method is not allowed. Reload the page and try again.", { status: 405 });

  const secret = Deno.env.get("GCASH_INBOUND_SECRET") || "";
  // FAIL CLOSED. An intake with no shared secret cannot authenticate its caller, and
  // this one can cause credits to be minted. Refuse rather than accept unsigned.
  if (!secret) return fail(ctx, "no_secret", "Inbound receipts are not configured", { status: 401 });

  const raw = await req.text();
  if (raw.length > 100_000) return fail(ctx, "too_large", "Payload too large", { status: 413 });

  const sig = req.headers.get("X-WorkHive-Signature") || "";
  const ts  = req.headers.get("X-WorkHive-Timestamp") || "";
  const tsNum = Number(ts);
  if (!ts || !isFinite(tsNum)) return fail(ctx, "missing_timestamp", "Missing timestamp", { status: 401 });
  // Replay window: a captured (sig, ts, body) triple must not work forever.
  if (Math.abs(Date.now() - tsNum) > 10 * 60 * 1000) {
    return fail(ctx, "stale", "Timestamp outside the accepted window", { status: 401 });
  }
  const expect = await hmacHex(secret, `${ts}.${raw}`);
  if (!safeEqual(expect, sig.toLowerCase())) {
    /* A REJECTED SIGNATURE IS THE SECURITY EVENT ON THIS ENDPOINT. Someone is POSTing receipts
       that do not verify -- a misconfigured forwarder, or a probe. Either way it must be visible
       WITHOUT reading raw logs. Deliberately records neither the signature nor the body: the first
       would hand an attacker an oracle, the second would put payment text in the log. */
    log.warn(ctx, "gcash_inbound_bad_signature", { body_bytes: raw.length, ts_skew_ms: Math.abs(Date.now() - tsNum) });
    return fail(ctx, "bad_signature", "That signature did not match. Check the webhook secret and try again.", { status: 401 });
  }

  let body: { text?: string; reference?: string; amount?: number; sender_name?: string; source?: string };
  try { body = JSON.parse(raw); } catch { return fail(ctx, "bad_json", "That request could not be read. Reload the page and try again.", { status: 400 }); }

  const parsed = body.text ? parseGcashText(body.text) : { reference: null, amount: null, sender: null };
  const reference = String(body.reference || parsed.reference || "").trim();
  const amount    = Number(body.amount ?? parsed.amount ?? NaN);
  const rawText   = body.text || raw;

  // A receipt we cannot read is NOT discarded silently — it is refused loudly, so the
  // founder learns the format drifted instead of wondering why credits stopped.
  /* W3-FN (2026-09-09): one sentence used to cover three different failures, and it named the wrong one
     whenever the fields were PRESENT. A signed probe sending reference "WALKPROBE0001" with amount 250.5
     was told "Could not find a reference number and an amount" while the detail block directly beneath it
     read got: { reference: "WALKPROBE0001", amount: 250.5 } - the message contradicting its own evidence.
     The real rule is that a GCash reference is exactly 13 DIGITS, which the sentence never said, so an
     integrator whose reference is merely the wrong SHAPE goes hunting for a field that was never missing.
     Same refusal, same status; it now names which of the three actually happened. */
  const refMissing = !reference;
  const refWrongShape = !refMissing && !/^\d{13}$/.test(reference);
  const amountBad = !isFinite(amount) || amount <= 0;
  if (refMissing || refWrongShape || amountBad) {
    /* Say which of the two rules the reference broke, not just its length. The first draft of this
       reported reference.length against "13 digits" and produced "Expected 13 digits, got 13." for
       WALKPROBE0001 - thirteen CHARACTERS, none of them the problem. A length is not a character
       class, and a diagnostic that conflates them is no better than the vague sentence it replaced. */
    const nonDigits = reference.replace(/\d/g, "").length > 0;
    const said = refWrongShape && !amountBad
      ? (nonDigits
          ? `That reference number is not a GCash reference: it must be digits only, and this one contains other characters.`
          : `That reference number is not a GCash reference: it must be exactly 13 digits, and this one has ${reference.length}.`)
      : refMissing && !amountBad
        ? "Could not find a reference number. Send the reference field."
        : !refMissing && !refWrongShape
          ? "Could not find a usable amount. Send the amount field as a positive number."
          : "Could not find a reference number and an amount. Send them directly.";
    return fail(ctx, "unparsed", said, {
      status: 422,
      detail: {
        got: { reference: reference || null, amount: isFinite(amount) ? amount : null },
        expected: { reference: "13 digits", amount: "a positive number" },
        hint: "Send the reference and amount fields. The wording may have changed.",
      },
    });
  }

  const db = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false } });

  const { data, error } = await db.from("gcash_inbound_receipts").insert({
    reference, amount,
    sender_name: body.sender_name || parsed.sender || null,
    raw_text: rawText,
    source: body.source === "sms" ? "sms" : body.source === "manual" ? "manual" : "email",
  }).select("id, match_state, match_note, matched_topup").single();

  if (error) {
    // A duplicate reference is the FORWARDER RETRYING, which is expected and safe —
    // the unique index is what makes replay harmless. Report it as accepted-already,
    // not as a failure, or a retrying forwarder will keep retrying.
    if (/duplicate|unique/i.test(error.message)) {
      return ok(ctx, { duplicate: true, note: "This reference was already recorded." });
    }
    return fail(ctx, "insert_failed", error.message, { status: 500 });
  }

  return ok(ctx, { receipt: data });
});
