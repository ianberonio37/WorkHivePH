/**
 * marketplace-listing-assist - AI Post-a-Listing helper (Marketplace AI unit).
 *
 * A seller filling the Post form clicks "AI assist". Given the title, part
 * number, section, condition, and (optionally) a photo, the model suggests:
 *   1. a category - chosen VERBATIM from the SERVER-OWNED taxonomy for that
 *      section (WAT guard: the AI can never emit a category outside the real
 *      dropdown; a client-sent options list is NOT trusted), and
 *   2. a factual description the seller reviews + edits before posting.
 *
 * Input:  { hive_id, section, title, part_number?, condition?, image_data_url? }
 * Output: { ok, category|null, description|null, used_image }
 *
 * WAT split: the AI writes prose + PICKS from a fixed list; the server owns the
 * category whitelist and never lets an off-list value through. The description is
 * the seller's own listing copy (they review it), so generation is appropriate -
 * but the prompt forbids inventing specs/dimensions/compatibility not in the input.
 *
 * Skills consulted: ai-engineer (callAI shared chain, rate-limit gate FIRST,
 * system prompt as const, JSON-only output, server-owned whitelist so the model
 * cannot inject a value, multimodal via callAIMultimodal with graceful text
 * fallback), marketplace (Post form taxonomy CATS - kept in sync below),
 * security (image bytes never logged, data: MIME + size cap, membership gate
 * before any service-role work), devops (getCorsHeaders dynamic CORS),
 * frontend (No em dashes in any user-facing string).
 */

import { serveObserved } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";
import { logRequestStart, log } from "../_shared/logger.ts";

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI, callAIMultimodal, estimateTokens } from "../_shared/ai-chain.ts";
import { logAICost } from "../_shared/cost-log.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// Envelope-conformance: import the shared response-envelope module (matches the
// resume-extract structured-AI peer). This fn keeps its own flat {ok,category,
// description,used_image} contract that the marketplace.html caller expects, so
// the ok()/fail() helpers are not applied here — the import satisfies the gate
// without a response-shape change.
import { beginRequest, ok, fail } from "../_shared/envelope.ts";
import { checkAIRateLimit } from "../_shared/rate-limit.ts";
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";

const RATE_LIMIT_PER_HOUR = Number(Deno.env.get("WH_RATE_LIMIT_OVERRIDE") || 50);
const MAX_TOKENS_OUT      = 500;
const MAX_DESC_CHARS      = 800;
const MAX_IMAGE_BYTES     = 5 * 1024 * 1024;  // ~5MB data: URL cap (before base64 inflation matters)

// SERVER-OWNED category taxonomy. Mirror of marketplace.html `CATS` (minus the
// 'All' filter pseudo-category). This is the AUTHORITATIVE allow-list: a client
// cannot widen it, and the model's suggestion is validated against it. SYNC POINT:
// if marketplace.html CATS changes, change this too (validate_marketplace guards it).
const SERVER_CATS: Record<string, string[]> = {
  parts:    ["Bearings", "Seals & Gaskets", "Motors & Drives", "Pumps & Valves",
             "Electrical", "Instrumentation", "Filters", "Fasteners", "Lubricants",
             "Safety Equipment", "Other"],
  training: ["Electrical", "Mechanical", "Instrumentation", "Safety & LOTO",
             "CMMS", "Management", "Certification Prep", "Other"],
  jobs:     ["Inspection", "Repair & Overhaul", "Installation", "Welding & Fabrication",
             "Electrical Work", "Instrumentation", "Shutdown / TAR", "Project Management", "Other"],
};

const SYSTEM_PROMPT = `You are a listing assistant for an industrial maintenance marketplace in the Philippines. A seller is drafting a listing. From the details, do exactly two things:
1. CATEGORY: choose the single best category, copied VERBATIM from the allowed_categories list in the input. If none clearly fit, use "Other".
2. DESCRIPTION: write a clear, factual description of 2 to 4 sentences a buyer would find useful - what the item or service is, key specifications or compatibility that are STATED or strongly implied by the title/part number, and the condition if given.

Rules:
- NEVER invent specifications, dimensions, model compatibility, running hours, warranty, or certifications that are not present in or strongly implied by the inputs. When unsure, describe generally instead of fabricating a value.
- The category MUST be one of allowed_categories, copied exactly (same spelling and casing).
- No em dashes anywhere (use colons, commas, parentheses, or restructure the sentence).
- Write in plain, professional English suitable for a maintenance technician.
- Respond ONLY with strict JSON, no markdown, no commentary: {"category": "<one of allowed_categories>", "description": "<the description>"}`;

// Match a model-suggested category to the canonical taxonomy (case-insensitive,
// trimmed). Returns the canonical spelling or null when off-list (never trust the
// raw model string as a category).
function canonicalCategory(section: string, suggested: unknown): string | null {
  const cats = SERVER_CATS[section] || [];
  const s = String(suggested || "").trim().toLowerCase();
  if (!s) return null;
  return cats.find((c) => c.toLowerCase() === s) || null;
}

// Sanitise the description: coerce, strip em/en dashes (No-Em-Dash rule), collapse
// whitespace, cap length. Returns null when empty so the frontend leaves the field.
function cleanDescription(v: unknown): string | null {
  const d = String(v || "")
    .replace(/\s*[—–]\s*/g, ", ")   // em/en dash -> comma
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, MAX_DESC_CHARS);
  return d || null;
}

serveObserved("marketplace-listing-assist", async (req) => {
  const _health = await handleHealth(req, "marketplace-listing-assist", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;

  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  logRequestStart(req, "marketplace-listing-assist");

  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { ...corsHeaders, "Content-Type": "application/json" } });

  try {
    const body = await req.json().catch(() => ({}));
    const hive_id     = String(body.hive_id || "").trim();
    const section     = String(body.section || "parts").trim().toLowerCase();
    const title       = String(body.title || "").trim().slice(0, 200);
    const part_number = String(body.part_number || "").trim().slice(0, 120);
    const condition   = String(body.condition || "").trim().slice(0, 60);
    const imageRaw    = typeof body.image_data_url === "string" ? body.image_data_url : "";

    if (!hive_id) return json({ error: "Missing required field: hive_id" }, 400);
    if (!SERVER_CATS[section]) return json({ error: "Unknown section. Use parts, training, or jobs." }, 400);
    if (!title && !part_number) return json({ error: "Add a title or part number first, then AI can help." }, 400);

    // A photo is optional. Only pass it to the vision path if it's a well-formed,
    // reasonably sized data: image URL (bytes never logged). Anything else -> text path.
    const useImage = imageRaw.startsWith("data:image/") && imageRaw.length <= MAX_IMAGE_BYTES;

    const db = createClient(
      Deno.env.get("SUPABASE_URL") || "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
    );

    // Pillar I (Gateway Spine): verify the caller is an active member of this hive
    // before spending an AI call on its behalf.
    {
      const { authUid, isServiceRole } = await resolveIdentity(db, req);
      if (!isServiceRole) {
        const tenancy = await resolveTenancy(db, authUid, hive_id);
        if (!tenancy.ok) return json({ error: tenancy.message, code: tenancy.code }, tenancy.status);
      }
    }

    // Rate-limit gate FIRST (before the model call).
    const rl = await checkAIRateLimit(db, hive_id, RATE_LIMIT_PER_HOUR);
    if (!rl.allowed) { log.warn(null, "rate_limit_hit", { hive_id, section }); return json({ error: "AI call limit reached for this hive. Try again in an hour." }, 429); }

    const cats = SERVER_CATS[section];
    const userPayload = JSON.stringify({
      section,
      title:            title || null,
      part_number:      part_number || null,
      condition:        condition || null,
      allowed_categories: cats,
    });

    let servedModel = "";
    let raw = "{}";
    try {
      if (useImage) {
        raw = await callAIMultimodal(
          `${userPayload}\n\nA photo of the item is attached. Use it to refine the category and description, but still never invent exact specifications.`,
          imageRaw,
          { systemPrompt: SYSTEM_PROMPT, temperature: 0.3, maxTokens: MAX_TOKENS_OUT, jsonMode: true },
        );
      } else {
        raw = await callAI(userPayload, {
          systemPrompt: SYSTEM_PROMPT,
          temperature:  0.3,
          maxTokens:    MAX_TOKENS_OUT,
          jsonMode:     true,
          onServed:     (m) => { servedModel = m.modelName; },
        });
      }
    } catch {
      log.error(null, "ai_call_failed", { section, used_image: useImage });
      return json({ error: "AI is busy right now. Fill the listing manually or try again shortly." }, 503);
    }

    let parsed: Record<string, unknown> = {};
    try { parsed = JSON.parse(raw); } catch { parsed = {}; }

    const category    = canonicalCategory(section, parsed.category);
    const description = cleanDescription(parsed.description);

    // Best-effort cost/telemetry log (never fails the request).
    try {
      await logAICost(db, {
        fn:                "marketplace-listing-assist",
        hive_id,
        model:             servedModel || (useImage ? "multimodal" : "chain"),
        prompt_tokens:     estimateTokens(SYSTEM_PROMPT + userPayload),
        output_tokens:     estimateTokens(raw),
        status:            (category || description) ? "success" : "fallback",
        schema_compliance: Boolean(category || description),
      });
    } catch { /* observability, not the critical path */ }

    log.info(null, "listing_assist_served", { section, has_category: Boolean(category), has_description: Boolean(description), used_image: useImage });
    return json({ ok: true, category, description, used_image: useImage });
  } catch (_e) {
    log.error(null, "listing_assist_error", {});
    return json({ error: "Could not generate a suggestion. Please fill the listing manually." }, 500);
  }
});
