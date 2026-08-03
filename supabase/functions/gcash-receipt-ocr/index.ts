// capability: platform_gcash_receipt_ocr
/**
 * gcash-receipt-ocr — read a GCash receipt SCREENSHOT so nobody types 13 digits.
 *
 * Ian, 2026-08-03: "they can just upload the receipt, for getting a credit."
 *
 * Both sides of every payment already HAVE the receipt — it is a screenshot in
 * their gallery. The provider filing a top-up and the buyer confirming a job
 * payment were both being asked to read an amount and a 13-digit reference off
 * that image and retype them into a form. That is the worst moment in the flow
 * and a mistyped digit is exactly what makes a payment unmatchable later.
 *
 * Upload the image; the fields fill themselves; the person CHECKS rather than
 * transcribes. Pasting the receipt TEXT remains the other option (whGcashPaste
 * in utils.js) — some people copy text, some screenshot, and both should work.
 *
 * WHAT THIS DOES NOT DO. It does not mint credits and it does not verify
 * anything. It reads an image and returns two fields for a HUMAN to confirm and
 * submit. Credit still requires the provider's filing to agree with the
 * founder's own GCash receipt (mig 38) — an uploaded screenshot is the
 * uploader's claim about their own payment, and a screenshot is forgeable.
 * Treating OCR output as proof would be exactly the mistake mig 38 exists to
 * avoid.
 *
 * Pipeline mirrors equipment-label-ocr, which already does this safely:
 *   1. submit to Azure Doc Intelligence (prebuilt-read)
 *   2. poll the operation URL until it succeeds
 *   3. parse the text with the SAME regexes utils.js and the inbound receipt
 *      endpoint use — three readers of one format must not disagree
 */
import { serveObserved } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";
import { beginRequest, ok, fail } from "../_shared/envelope.ts";
import { getCorsHeaders } from "../_shared/cors.ts";

const FN_NAME = "gcash-receipt-ocr";

const AZURE_ENDPOINT = Deno.env.get("AZURE_DOC_INTELLIGENCE_ENDPOINT") || "";
const AZURE_KEY = Deno.env.get("AZURE_DOC_INTELLIGENCE_KEY") || "";

const ALLOWED_MIME = new Set(["image/jpeg", "image/png", "image/webp", "image/bmp"]);
const MAX_BYTES = 5 * 1024 * 1024;

/** Identical to utils.js whGcashParse and the inbound endpoint's parseGcashText. */
export function parseGcashText(text: string): { reference: string | null; amount: number | null } {
  const t = (text || "").replace(/ /g, " ");
  const refM = t.match(/(?:ref(?:erence)?\.?\s*(?:no\.?|number)?\s*[:\-]?\s*)(\d{13})/i)
            || t.match(/(?:^|[^\d])(\d{13})(?![\d])/);
  const amtM = t.match(/(?:php|₱|p)\s*([\d,]+(?:\.\d{1,2})?)/i);
  const amount = amtM ? Number(amtM[1].replace(/,/g, "")) : null;
  return {
    reference: refM ? refM[refM.length - 1] : null,
    amount: (amount != null && isFinite(amount) && amount > 0) ? amount : null,
  };
}

function decodeDataUrl(dataUrl: string): { bytes: Uint8Array; mime: string } {
  const m = /^data:([^;]+);base64,(.+)$/.exec(dataUrl || "");
  if (!m) throw new Error("Send the image as a base64 data URL");
  const mime = m[1].toLowerCase();
  if (!ALLOWED_MIME.has(mime)) throw new Error(`That file type is not supported (${mime})`);
  const bin = atob(m[2]);
  if (bin.length > MAX_BYTES) throw new Error("That image is larger than 5 MB");
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return { bytes, mime };
}

/* serveObserved, not a bare Deno.serve: an unhandled throw in a bare serve() leaks and is INVISIBLE
   to the SLO alerting, which is how an edge function fails quietly for a week. /health reports
   whether the OCR backend is actually configured, so "uploads stopped working" is answerable
   without reading logs. Both were missed when this shipped — the platform's edge conventions are a
   checklist and I wrote two functions without running it. */
serveObserved(FN_NAME, async (req: Request) => {
  /* getCorsHeaders(req), not a hardcoded "*". A static origin breaks file:// local testing (Chrome
     sends `Origin: null`) and every non-production client, and the shared helper is what the rest of
     the platform's 58 functions use. I hand-rolled the header block when this shipped -- the same
     "wrote a new edge function without running the conventions checklist" miss that also left it
     out of the deploy script and its secret undeclared. */
  const cors = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  const healthResp = await handleHealth(req, FN_NAME, async () => ({
    deps: [{ name: "azure_doc_intelligence", ok: Boolean(AZURE_ENDPOINT && AZURE_KEY) }],
  }));
  if (healthResp) return healthResp;

  /* The platform response contract: every reply carries ok/data or ok/code/message plus
     a trace id, so a caller (and the SLO dashboard) can correlate one request across
     function, logs and DB. I hand-rolled JSON here and skipped it. */
  const ctx = beginRequest(req, { route: FN_NAME });

  if (req.method !== "POST") return fail(ctx, "method_not_allowed", "POST only", { status: 405 });

  let body: { image_data_url?: string };
  try { body = await req.json(); } catch { return fail(ctx, "bad_json", "Body is not JSON", { status: 400 }); }

  let img: { bytes: Uint8Array; mime: string };
  try { img = decodeDataUrl(String(body.image_data_url || "")); }
  catch (e) { return fail(ctx, "bad_image", (e as Error).message, { status: 400 }); }

  // HONEST DEGRADE. With no OCR backend configured the answer is "we could not
  // read it", never a guessed reference — a wrong 13-digit number is worse than
  // no number, because it files a claim that can never match.
  if (!AZURE_ENDPOINT || !AZURE_KEY) {
    return ok(ctx, {
      azure_unavailable: true,
      parsed: { reference: null, amount: null },
      note: "Receipt reading is not configured on this deployment. Type the amount and reference, "
          + "or paste the receipt text instead.",
    });
  }

  try {
    const submit = await fetch(
      `${AZURE_ENDPOINT.replace(/\/$/, "")}/documentintelligence/documentModels/prebuilt-read:analyze?api-version=2024-02-29-preview`,
      { method: "POST", headers: { "Ocp-Apim-Subscription-Key": AZURE_KEY, "Content-Type": img.mime },
        body: img.bytes });
    if (!submit.ok) return fail(ctx, "ocr_refused", `OCR service refused the image (${submit.status})`, { status: 502 });

    const op = submit.headers.get("operation-location");
    if (!op) return fail(ctx, "ocr_no_operation", "OCR service did not return an operation to poll", { status: 502 });

    let text = "";
    for (let i = 0; i < 12; i++) {
      await new Promise(r => setTimeout(r, 900));
      const poll = await fetch(op, { headers: { "Ocp-Apim-Subscription-Key": AZURE_KEY } });
      const data = await poll.json();
      if (data.status === "succeeded") { text = data?.analyzeResult?.content || ""; break; }
      if (data.status === "failed") return fail(ctx, "ocr_unreadable", "OCR could not read that image", { status: 422 });
    }
    if (!text) return fail(ctx, "ocr_timeout", "OCR timed out on that image", { status: 504 });

    const parsed = parseGcashText(text);
    return ok(ctx, {
      parsed,
      ocr_chars: text.length,
      // Say when the image was read but the FIELDS were not found — a blank result
      // with no explanation reads as a broken upload rather than an unclear photo.
      note: (!parsed.reference && parsed.amount == null)
        ? "The image was read but no 13-digit reference or amount was found. Try a clearer "
          + "screenshot of the receipt, or type the details."
        : undefined,
    });
  } catch (e) {
    return fail(ctx, "ocr_failed", `Could not read the receipt: ${(e as Error).message}`, { status: 500 });
  }
});
