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
const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (b: unknown, s = 200) =>
  new Response(JSON.stringify(b), { status: s, headers: { ...cors, "Content-Type": "application/json" } });

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

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  let body: { image_data_url?: string };
  try { body = await req.json(); } catch { return json({ error: "Body is not JSON" }, 400); }

  let img: { bytes: Uint8Array; mime: string };
  try { img = decodeDataUrl(String(body.image_data_url || "")); }
  catch (e) { return json({ error: (e as Error).message }, 400); }

  // HONEST DEGRADE. With no OCR backend configured the answer is "we could not
  // read it", never a guessed reference — a wrong 13-digit number is worse than
  // no number, because it files a claim that can never match.
  if (!AZURE_ENDPOINT || !AZURE_KEY) {
    return json({
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
    if (!submit.ok) return json({ error: `OCR service refused the image (${submit.status})` }, 502);

    const op = submit.headers.get("operation-location");
    if (!op) return json({ error: "OCR service did not return an operation to poll" }, 502);

    let text = "";
    for (let i = 0; i < 12; i++) {
      await new Promise(r => setTimeout(r, 900));
      const poll = await fetch(op, { headers: { "Ocp-Apim-Subscription-Key": AZURE_KEY } });
      const data = await poll.json();
      if (data.status === "succeeded") { text = data?.analyzeResult?.content || ""; break; }
      if (data.status === "failed") return json({ error: "OCR could not read that image" }, 422);
    }
    if (!text) return json({ error: "OCR timed out on that image" }, 504);

    const parsed = parseGcashText(text);
    return json({
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
    return json({ error: `Could not read the receipt: ${(e as Error).message}` }, 500);
  }
});
