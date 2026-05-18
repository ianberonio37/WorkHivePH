// capability: ai_specialist_equipment_label
/**
 * equipment-label-ocr — extract manufacturer / model / serial_no from a
 * photo of an equipment nameplate, for the logbook.html asset register flow.
 *
 * Distinct from visual-defect-capture (which classifies defects from photos
 * of damaged equipment and extracts an asset_tag). This function targets a
 * worker photographing a clean nameplate to register a NEW asset.
 *
 * Pipeline:
 *   1. Submit the image to Azure Doc Intelligence (prebuilt-read OCR).
 *   2. Poll the operation URL until status=succeeded.
 *   3. Regex-parse the OCR text for manufacturer / model / serial_no /
 *      rated_power / voltage (mirrors tools/day3_equipment_label_ocr.py).
 *   4. If hive_id provided, try to match against asset_nodes — return the
 *      matched id so the worker confirms instead of registering a duplicate.
 *
 * Input:
 *   {
 *     image_data_url: string,    // "data:image/jpeg;base64,..." (preferred)
 *                                // OR a public https URL Azure can fetch
 *     hive_id?: string,          // for asset_nodes match attempt
 *   }
 *
 * Output:
 *   {
 *     parsed: {
 *       manufacturer:  string | null,
 *       model:         string | null,
 *       serial_no:     string | null,
 *       rated_power:   string | null,
 *       voltage:       string | null,
 *     },
 *     matched_asset:  { id, tag, name, manufacturer, model } | null,
 *     ocr_chars:      number,
 *     azure_unavailable?: boolean,
 *   }
 *
 * Skills consulted:
 *   ai-engineer (one-shot Azure artifact, not runtime LLM call — different
 *     contract than callAI/callAIMultimodal which route through the free chain)
 *   security (MIME whitelist, 5 MB cap, only data:image or https URL accepted)
 *   multitenant-engineer (hive-scoped match; service-role read)
 *   devops (getCorsHeaders dynamic CORS; AbortSignal at 60s)
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
// contract-allow: enriches asset_nodes register flow; no new artifact table
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";

const AZURE_ENDPOINT = Deno.env.get("AZURE_DOC_INTELLIGENCE_ENDPOINT") || "";
const AZURE_KEY      = Deno.env.get("AZURE_DOC_INTELLIGENCE_KEY")      || "";
const SUPABASE_URL   = Deno.env.get("SUPABASE_URL")                    || "";
const SERVICE_KEY    = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")       || "";

const MAX_IMAGE_BYTES = 5_000_000;   // 5 MB cap on the decoded payload
const ALLOWED_MIME = new Set(["image/jpeg", "image/png", "image/webp", "image/bmp"]);

// Regex patterns mirror tools/day3_equipment_label_ocr.py.
// Order matters: longer/more-specific patterns first so "Model No." wins
// over "Model".
const PATTERNS: Record<string, RegExp[]> = {
  manufacturer: [
    /(?:manufacturer|mfg|brand|make)\s*[:\-]\s*([A-Z][\w &\-]{2,40})/i,
  ],
  model: [
    /\bmodel\s*no\.?\s*[:\-]?\s*([A-Z0-9][\w\-./]{2,30})/i,
    /\bcat\.?\s*no\.?\s*[:\-]?\s*([A-Z0-9][\w\-./]{2,30})/i,
    /\b(?:model|type)\s*[:\-]\s*([A-Z0-9][\w\-./]{2,30})/i,
  ],
  serial_no: [
    /\b(?:s\/?n|serial\s*(?:no\.?)?|ser\.?)\s*[:\-]?\s*([A-Z0-9][\w\-]{3,30})/i,
  ],
  rated_power: [
    /\b(\d+(?:\.\d+)?)\s*(?:kW|HP|W|kVA)\b/i,
  ],
  voltage: [
    /\b(\d{2,4})\s*V(?:AC|DC)?\b/,
  ],
};

function parseNameplate(text: string): Record<string, string | null> {
  const out: Record<string, string | null> = {
    manufacturer: null, model: null, serial_no: null, rated_power: null, voltage: null,
  };
  for (const [field, patterns] of Object.entries(PATTERNS)) {
    for (const pat of patterns) {
      const m = pat.exec(text);
      if (m && m[1]) {
        const val = m[1].trim().replace(/[.,;:]+$/, "");
        if (val) { out[field] = val; break; }
      }
    }
  }
  return out;
}

interface ParsedFields {
  manufacturer: string | null;
  model:        string | null;
  serial_no:    string | null;
  rated_power:  string | null;
  voltage:      string | null;
}

async function submitImageBytes(bytes: Uint8Array, contentType: string): Promise<string> {
  const url = `${AZURE_ENDPOINT.replace(/\/+$/, "")}/documentintelligence/documentModels/prebuilt-read:analyze?api-version=2024-11-30`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Ocp-Apim-Subscription-Key": AZURE_KEY,
      "Content-Type":              contentType,
    },
    body:   bytes,
    signal: AbortSignal.timeout(60_000),
  });
  if (res.status !== 200 && res.status !== 202) {
    const errBody = (await res.text()).slice(0, 200);
    throw new Error(`Azure submit ${res.status}: ${errBody}`);
  }
  const op = res.headers.get("Operation-Location") || res.headers.get("operation-location");
  if (!op) throw new Error("Azure response missing Operation-Location header");
  return op;
}

async function pollResult(opLocation: string, maxMs = 30_000): Promise<string> {
  const start = Date.now();
  let delay = 1500;
  while (true) {
    if (Date.now() - start > maxMs) throw new Error("Azure poll timeout");
    const r = await fetch(opLocation, {
      headers: { "Ocp-Apim-Subscription-Key": AZURE_KEY },
      signal:  AbortSignal.timeout(15_000),
    });
    if (!r.ok) throw new Error(`Azure poll ${r.status}`);
    const data = await r.json();
    const status = (data?.status || "").toLowerCase();
    if (status === "succeeded") return data?.analyzeResult?.content || "";
    if (status === "failed" || status === "canceled") throw new Error(`Azure analysis ${status}`);
    await new Promise((res) => setTimeout(res, delay));
    delay = Math.min(delay + 500, 4000);
  }
}

function decodeDataUrl(dataUrl: string): { bytes: Uint8Array; contentType: string } {
  const m = /^data:([^;]+);base64,(.+)$/.exec(dataUrl);
  if (!m) throw new Error("image_data_url must be a base64 data URL");
  const contentType = m[1].toLowerCase();
  if (!ALLOWED_MIME.has(contentType)) {
    throw new Error(`unsupported image MIME: ${contentType}`);
  }
  const binary = atob(m[2]);
  if (binary.length > MAX_IMAGE_BYTES) {
    throw new Error(`image exceeds ${MAX_IMAGE_BYTES} bytes`);
  }
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return { bytes, contentType };
}

async function fetchPublicUrl(url: string): Promise<{ bytes: Uint8Array; contentType: string }> {
  if (!/^https:\/\//i.test(url)) throw new Error("image URL must be https");
  const r = await fetch(url, { signal: AbortSignal.timeout(15_000) });
  if (!r.ok) throw new Error(`image fetch ${r.status}`);
  const contentType = (r.headers.get("Content-Type") || "image/jpeg").toLowerCase().split(";")[0].trim();
  if (!ALLOWED_MIME.has(contentType)) throw new Error(`unsupported image MIME: ${contentType}`);
  const bytes = new Uint8Array(await r.arrayBuffer());
  if (bytes.length > MAX_IMAGE_BYTES) throw new Error(`image exceeds ${MAX_IMAGE_BYTES} bytes`);
  return { bytes, contentType };
}

async function matchAssetNodes(
  client: ReturnType<typeof createClient>,
  hiveId: string,
  parsed: ParsedFields,
): Promise<{ id: string; tag: string; name: string; manufacturer: string; model: string } | null> {
  // Prefer serial_no exact, then model+manufacturer, then model alone.
  const tryQuery = async (filter: Record<string, string>) => {
    let q = client.from("asset_nodes")
      .select("id, tag, name, manufacturer, model")
      .eq("hive_id", hiveId)
      .limit(1);
    for (const [col, val] of Object.entries(filter)) {
      q = q.ilike(col, val);
    }
    const { data, error } = await q;
    if (error || !data || !data.length) return null;
    return data[0] as { id: string; tag: string; name: string; manufacturer: string; model: string };
  };

  if (parsed.serial_no) {
    const hit = await tryQuery({ serial_no: `%${parsed.serial_no}%` });
    if (hit) return hit;
  }
  if (parsed.model && parsed.manufacturer) {
    const hit = await tryQuery({ model: `%${parsed.model}%`, manufacturer: `%${parsed.manufacturer}%` });
    if (hit) return hit;
  }
  if (parsed.model) {
    const hit = await tryQuery({ model: `%${parsed.model}%` });
    if (hit) return hit;
  }
  return null;
}

serve(async (req) => {
  const cors = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { headers: cors });

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "method_not_allowed" }), {
      status: 405, headers: { ...cors, "Content-Type": "application/json" },
    });
  }

  if (!AZURE_ENDPOINT || !AZURE_KEY) {
    return new Response(JSON.stringify({
      error:             "azure_not_configured",
      azure_unavailable: true,
      parsed:            { manufacturer: null, model: null, serial_no: null, rated_power: null, voltage: null },
      matched_asset:     null,
      ocr_chars:         0,
    }), {
      status: 200, headers: { ...cors, "Content-Type": "application/json" },
    });
  }

  let body: { image_data_url?: string; image_url?: string; hive_id?: string };
  try { body = await req.json(); } catch {
    return new Response(JSON.stringify({ error: "bad_json" }), {
      status: 400, headers: { ...cors, "Content-Type": "application/json" },
    });
  }

  let bytes: Uint8Array;
  let contentType: string;
  try {
    if (body.image_data_url) {
      ({ bytes, contentType } = decodeDataUrl(body.image_data_url));
    } else if (body.image_url) {
      ({ bytes, contentType } = await fetchPublicUrl(body.image_url));
    } else {
      throw new Error("missing image_data_url or image_url");
    }
  } catch (err) {
    return new Response(JSON.stringify({ error: (err as Error).message }), {
      status: 400, headers: { ...cors, "Content-Type": "application/json" },
    });
  }

  let ocrText = "";
  try {
    const opLoc = await submitImageBytes(bytes, contentType);
    ocrText = await pollResult(opLoc);
  } catch (err) {
    return new Response(JSON.stringify({
      error:             "azure_ocr_failed",
      detail:            (err as Error).message,
      azure_unavailable: true,
      parsed:            { manufacturer: null, model: null, serial_no: null, rated_power: null, voltage: null },
      matched_asset:     null,
      ocr_chars:         0,
    }), {
      status: 200, headers: { ...cors, "Content-Type": "application/json" },
    });
  }

  const parsedRaw = parseNameplate(ocrText);
  const parsed: ParsedFields = {
    manufacturer: parsedRaw.manufacturer ?? null,
    model:        parsedRaw.model ?? null,
    serial_no:    parsedRaw.serial_no ?? null,
    rated_power:  parsedRaw.rated_power ?? null,
    voltage:      parsedRaw.voltage ?? null,
  };

  let matched_asset = null;
  if (body.hive_id && SUPABASE_URL && SERVICE_KEY) {
    try {
      const client = createClient(SUPABASE_URL, SERVICE_KEY);
      matched_asset = await matchAssetNodes(client, body.hive_id, parsed);
    } catch (err) {
      console.warn("[equipment-label-ocr] asset match failed:", (err as Error).message);
    }
  }

  return new Response(JSON.stringify({
    parsed,
    matched_asset,
    ocr_chars: ocrText.length,
  }), {
    status: 200, headers: { ...cors, "Content-Type": "application/json" },
  });
});
