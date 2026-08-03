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
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.7";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-workhive-signature, x-workhive-timestamp",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

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

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  const secret = Deno.env.get("GCASH_INBOUND_SECRET") || "";
  // FAIL CLOSED. An intake with no shared secret cannot authenticate its caller, and
  // this one can cause credits to be minted. Refuse rather than accept unsigned.
  if (!secret) return json({ error: "Inbound receipts are not configured", code: "no_secret" }, 401);

  const raw = await req.text();
  if (raw.length > 100_000) return json({ error: "Payload too large", code: "too_large" }, 413);

  const sig = req.headers.get("X-WorkHive-Signature") || "";
  const ts  = req.headers.get("X-WorkHive-Timestamp") || "";
  const tsNum = Number(ts);
  if (!ts || !isFinite(tsNum)) return json({ error: "Missing timestamp" }, 401);
  // Replay window: a captured (sig, ts, body) triple must not work forever.
  if (Math.abs(Date.now() - tsNum) > 10 * 60 * 1000) {
    return json({ error: "Timestamp outside the accepted window", code: "stale" }, 401);
  }
  const expect = await hmacHex(secret, `${ts}.${raw}`);
  if (!safeEqual(expect, sig.toLowerCase())) return json({ error: "Invalid signature" }, 401);

  let body: { text?: string; reference?: string; amount?: number; sender_name?: string; source?: string };
  try { body = JSON.parse(raw); } catch { return json({ error: "Body is not JSON" }, 400); }

  const parsed = body.text ? parseGcashText(body.text) : { reference: null, amount: null, sender: null };
  const reference = String(body.reference || parsed.reference || "").trim();
  const amount    = Number(body.amount ?? parsed.amount ?? NaN);
  const rawText   = body.text || raw;

  // A receipt we cannot read is NOT discarded silently — it is refused loudly, so the
  // founder learns the format drifted instead of wondering why credits stopped.
  if (!/^\d{13}$/.test(reference) || !isFinite(amount) || amount <= 0) {
    return json({
      error: "Could not read a 13-digit reference and an amount from this notification",
      code: "unparsed",
      got: { reference: reference || null, amount: isFinite(amount) ? amount : null },
      hint: "Send { reference, amount } explicitly if the notification wording has changed.",
    }, 422);
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
      return json({ ok: true, duplicate: true, note: "This reference was already recorded." }, 200);
    }
    return json({ error: error.message }, 500);
  }

  return json({ ok: true, receipt: data });
});
