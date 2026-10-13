/**
 * marketplace-listing-assist - AI Post-a-Listing helper (Marketplace AI unit).
 * contract-allow: a listing draft in a flat {ok, category, description, used_image} shape, documented below at the
 * envelope note; the category is chosen from the server-owned taxonomy. Future Tier C: listing_draft_v1.
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
import { tracedReply } from "../_shared/trace-reply.ts";  // LM-E/LM-O: one trace id per request
import { handleHealth } from "../_shared/health.ts";
import { log } from "../_shared/logger.ts";

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";
import { callAI, callAIMultimodal, estimateTokens, aiAnswered } from "../_shared/ai-chain.ts";
import { logAICost } from "../_shared/cost-log.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// Envelope-conformance: import the shared response-envelope module (matches the
// resume-extract structured-AI peer). This fn keeps its own flat {ok,category,
// description,used_image} contract that the marketplace.html caller expects, so
// the ok()/fail() helpers are not applied here — the import satisfies the gate
// without a response-shape change.
import { beginRequest, ok, fail } from "../_shared/envelope.ts";
import {
  checkAIRateLimit, checkRouteRateLimit, routeRateLimitedResponse, rateLimitedResponse,
  checkSoloRateLimit, peekSoloRateLimit, soloRateLimitKey, soloRateLimitedResponse, DEFAULT_RATE_LIMIT_PER_DAY,
  type RateLimitResult,
} from "../_shared/rate-limit.ts";
import { isTrustedGatewayForward } from "../_shared/gateway-trust.ts";
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

serveObserved("marketplace-listing-assist", tracedReply("marketplace-listing-assist", async (req, trace) => {
  // one trace id per request (tracedReply): every JSON reply returns it, and every model call's ai_cost_log row
  // carries the same id (LM-O, 2026-10-08)
  const _health = await handleHealth(req, "marketplace-listing-assist", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;

  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  log.info(trace, "request_start", { method: req.method });

  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { ...corsHeaders, "Content-Type": "application/json" } });

  try {
    const body = await req.json().catch(() => ({}));

    // ── SERVICE_HAILING P7: triage mode (the coach-fold pattern — reuse THIS AI fn
    // rather than minting another). Given a free-text problem description + the LIVE
    // catalog categories, suggest { category, urgency, mode } for the hail composer.
    // Server-owned whitelists: the model picks FROM lists it cannot widen; anything
    // off-list falls back to nulls (the composer simply leaves the field untouched).
    if (String(body.mode || "") === "service_triage") {
      const desc = String(body.message || body.description || "").trim().slice(0, 500);
      if (!desc) return json({ error: "Missing required field: message (describe the problem)" }, 400);
      const _db = createClient(
        Deno.env.get("SUPABASE_URL") || "",
        Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
      );
      // L6 posture (the fn's catalogued open frontier must not WIDEN): triage requires a
      // resolvable identity (user JWT via the gateway, or service-role) and rate-limits on
      // the AUTH UID (Pillar P: never an unverified hive_id; consumers are hive-less).
      const ident = await resolveIdentity(_db, req);
      if (!ident.authUid && !ident.isServiceRole) {
        return json({ error: "Sign in to use AI triage." }, 401);
      }
      if (ident.authUid) {
        // ★A PERSON'S BUDGET LIVES ON THE PER-PERSON LIMITER (2026-10-08). This wrote the auth uid into
        // ai_rate_limits.hive_id, a column with a foreign key to hives: every upsert failed, the error was never read,
        // and the triage limit never counted a single call. The person's own bucket (keyed on the VERIFIED uid) holds it.
        // That is the bucket ai-gateway counts for its service-triage agent, so a call it forwarded (proven by the
        // header it mints, never a body field) is held to triage's tighter ceiling by READING the count - counting it
        // again would spend the person's allowance twice for one question.
        const triageViaGateway = await isTrustedGatewayForward(req);
        let trl: RateLimitResult;
        if (triageViaGateway) {
          trl = await peekSoloRateLimit(_db, soloRateLimitKey(ident.authUid, null), 20, 100);
        } else {
          trl = await checkSoloRateLimit(_db, soloRateLimitKey(ident.authUid, null), 20, 100, null, true);
        }
        if (!trl.allowed) return soloRateLimitedResponse(corsHeaders, trl.retry_after_seconds, trl.scope);
      }
      const { data: catRows } = await _db.from("v_service_catalog_truth")
        .select("category").limit(200);
      const cats = [...new Set((catRows || []).map((r: { category: string }) => r.category))];
      const URGENCIES = ["low", "normal", "high", "critical"];
      const sys = "You triage industrial/home service requests for a PH maintenance platform. "
        + "Reply ONLY a JSON object {\"category\":string,\"urgency\":string,\"mode\":string}. "
        + "category MUST be one of: " + cats.join(", ") + ". "
        + "urgency MUST be one of: low, normal, high, critical (critical = production down / safety). "
        + "mode is \"instant\" for a standard single-visit job, \"quote\" for large/complex/multi-day work.";
      let aiRaw = "{}";
      try {
        aiRaw = await callAI(desc, { systemPrompt: sys, temperature: 0.1, maxTokens: 120, jsonMode: true });
      } catch { /* chain down: fall through to nulls, the composer stays untouched */ }
      // ★NO ANSWER IS NO SUGGESTION, NOT "NO CLEAR MATCH" (2026-10-12, UFAI edge walk W4578). With the chain down (or a
      // walk's no-model switch) aiRaw is "{}", the three fields came back null, and the page said "No clear match; pick
      // the fields yourself." - as if the AI had weighed the job and found nothing. triage:null is the page's own
      // honest branch ("No suggestion this time. Pick the fields yourself."), and an empty answer is not remembered.
      if (!aiAnswered(aiRaw)) return json({ answer: "", triage: null });
      let out: { category?: string; urgency?: string; mode?: string } = {};
      try { out = JSON.parse(String(aiRaw || "{}").replace(/```json|```/g, "").trim()); } catch { /* fall through to nulls */ }
      const category = cats.includes(String(out.category)) ? String(out.category) : null;
      const urgency = URGENCIES.includes(String(out.urgency)) ? String(out.urgency) : null;
      const mode = ["instant", "quote"].includes(String(out.mode)) ? String(out.mode) : null;
      return json({ answer: "Suggested: " + (category || "no clear category") + (urgency ? ", " + urgency + " urgency" : "") + (mode ? ", " + mode + " flow" : ""),
                    triage: { category, urgency, mode } });
    }

    const hive_id     = String(body.hive_id || "").trim();
    const section     = String(body.section || "parts").trim().toLowerCase();
    const title       = String(body.title || "").trim().slice(0, 200);
    const part_number = String(body.part_number || "").trim().slice(0, 120);
    const condition   = String(body.condition || "").trim().slice(0, 60);
    const imageRaw    = typeof body.image_data_url === "string" ? body.image_data_url : "";

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
    // ★A SIGNED-IN SELLER WITH NO HIVE WAS TOLD TO "SIGN IN" (LM-A walk, LM389, 2026-10-07): posting a listing
    // needs only an account, but the draft needed a hive, so a solo owner who opened the post sheet and pressed
    // AI assist got the sign-in card. A person with no hive is now served on their own verified identity and
    // rate-limited on it (Pillar P - the key is the AUTH UID, never a client-sent id), exactly as this function's
    // triage path already serves hive-less consumers. A hive_id that IS sent is still proven by membership.
    let soloUid: string | null = null;          // the VERIFIED person a hive-less draft is limited on
    let verifiedHiveId: string | null = null;   // the hive the limiters count on: membership-proven, or a service caller's
    {
      const { authUid, isServiceRole } = await resolveIdentity(db, req);
      if (!isServiceRole) {
        if (hive_id) {
          const tenancy = await resolveTenancy(db, authUid, hive_id);
          if (!tenancy.ok) return json({ error: tenancy.message, code: tenancy.code }, tenancy.status);
          verifiedHiveId = tenancy.hive_id || hive_id;
        } else {
          if (!authUid) return json({ error: "Sign in to use AI assist." }, 401);
          soloUid = authUid;
        }
      } else if (!hive_id) {
        return json({ error: "Missing required field: hive_id" }, 400);
      } else {
        verifiedHiveId = hive_id;   // a service-role caller is trusted with the hive it names
      }
    }

    // Rate-limit gate FIRST (before the model call).
    // D12 per-SURFACE quota, OBSERVE-mode (mirrors the shared gateway pattern). Always counts into
    // (hive, route, hour) via hive_route_calls so per-surface AI pressure is VISIBLE - the
    // hive-wide cap alone cannot show which surface is burning the budget. It does NOT deny:
    // checkRouteRateLimit only enforces when an explicit hive_route_quotas row exists, and
    // none do, so this is a no-op behaviour change. Wrapped: quota bookkeeping must never
    // fail a real request.
    if (verifiedHiveId) try {
      const _rq = await checkRouteRateLimit(db, verifiedHiveId, "marketplace-listing-assist");
      // Denies ONLY when an explicit hive_route_quotas row exists (rq.per_route), so this stays
      // a no-op until an admin sets a cap - while always counting for attribution.
      if (_rq.per_route && !_rq.allowed) return routeRateLimitedResponse(corsHeaders, "marketplace-listing-assist", _rq.cap, _rq.retry_after_seconds, _rq.scope);
    } catch { /* empty-catch-allow: per-surface quota bookkeeping must never fail a real request */ }
    // ★A HIVE-LESS SELLER WAS NEVER COUNTED (2026-10-08). Their auth uid went to checkAIRateLimit as if it were a hive:
    // ai_rate_limits.hive_id has a foreign key to hives, so every upsert failed, the error was discarded, and each call
    // saw an empty bucket - an unmetered AI endpoint for anyone with an account and no hive. A hive caller still draws
    // on the hive's bucket; a person with no hive draws on their OWN (the per-person limiter, keyed on the verified
    // uid) with the budget a single-person hive gets: RATE_LIMIT_PER_HOUR an hour, the hive default a day. A limiter
    // that cannot count refuses (503), it never waves the call through.
    const rl = verifiedHiveId
      ? await checkAIRateLimit(db, verifiedHiveId, RATE_LIMIT_PER_HOUR)
      : await checkSoloRateLimit(db, soloRateLimitKey(soloUid, null), RATE_LIMIT_PER_HOUR, DEFAULT_RATE_LIMIT_PER_DAY, null, true);
    if (!rl.allowed) {
      log.warn(null, "rate_limit_hit", { hive_id: verifiedHiveId, section, scope: rl.scope ?? null });
      return verifiedHiveId
        ? rateLimitedResponse(corsHeaders, rl.scope ?? "hour", rl.retry_after_seconds)
        : soloRateLimitedResponse(corsHeaders, rl.retry_after_seconds, rl.scope);
    }

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

    // ★"NO SUGGESTION" FROM AN AI THAT NEVER ANSWERED (2026-10-12, UFAI edge walk W4580). callAI degrades to "{}" when
    // every provider fails (or a walk asked for no model), and this answered ok:true with no category and no description -
    // so the seller read "No suggestion this time", a verdict about their item from a model that never saw it. The reply
    // says whether a model answered; the page says the assist could not answer.
    const answered = aiAnswered(raw);
    let parsed: Record<string, unknown> = {};
    try { parsed = JSON.parse(raw); } catch { parsed = {}; }

    const category    = canonicalCategory(section, parsed.category);
    const description = cleanDescription(parsed.description);

    // Best-effort cost/telemetry log (never fails the request).
    try {
      await logAICost(db, {
        fn:                "marketplace-listing-assist",
        hive_id:           hive_id || null,
        model:             servedModel || (useImage ? "multimodal" : "chain"),
        prompt_tokens:     estimateTokens(SYSTEM_PROMPT + userPayload),
        output_tokens:     estimateTokens(raw),
        status:            !answered ? "failed" : (category || description) ? "success" : "fallback",
        schema_compliance: Boolean(category || description),
      });
    } catch { /* observability, not the critical path */ }

    log.info(null, "listing_assist_served", { section, has_category: Boolean(category), has_description: Boolean(description), used_image: useImage });
    return json({ ok: true, answered, category, description, used_image: useImage });
  } catch (_e) {
    log.error(null, "listing_assist_error", {});
    return json({ error: "Could not generate a suggestion. Please fill the listing manually." }, 500);
  }
}));
