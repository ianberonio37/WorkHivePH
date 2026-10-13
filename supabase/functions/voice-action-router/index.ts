/**
// capability: voice_to_action_router
 * voice-action-router - Phase B.1: cross-page voice orchestrator.
 *
 * Takes a maintenance worker's spoken sentence and returns structured intents
 * the calling page can apply. Unlike voice-logbook-entry (logbook-specific)
 * and voice-report-intent (report-sender-specific), this router classifies
 * across the whole platform and resolves asset names via v_asset_truth (the
 * canonical source registered in canonical_sources).
 *
 * Input:  { transcript, hive_id?, context_page?, context_asset_id? }
 *         (no hive_id = a signed-in hive-less person; assets resolve against their own register)
 * Output: { transcript, intents[], asset_resolution?, remaining }
 *
 * Intent kinds (v1):
 *   logbook.create     - "I just replaced the V-belt on Pump P-5"
 *   inventory.deduct   - "Used 2 V-belts from stock"
 *   pm.complete        - "Done with the weekly inspection on the chiller"
 *   asset.lookup       - "What's the status of pump 5?"
 *   query.ask          - falls through to general assistant
 *
 * Asset resolution: any asset name mentioned is looked up against v_asset_truth
 * by tag or name (case-insensitive). When resolution is ambiguous (multiple
 * matches) or empty (no match), the calling page shows a confirmation chip.
 *
 * Skills consulted: ai-engineer (callAI shared chain, rate limit gate FIRST,
 * transcript cap at 500 chars, JSON-only output, structured prompt), security
 * (no service-role leak in errors, hive scoping on every read), architect
 * (canonical sources lookup pattern), data-engineer (narrow selects, ilike
 * with escaped wildcards), devops (getCorsHeaders dynamic CORS).
 */

import { serveObserved, failTracked } from "../_shared/observability.ts";
import { tracedReply } from "../_shared/trace-reply.ts";  // LM-E/LM-O: one trace id per request
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";
import { callAI } from "../_shared/ai-chain.ts";
import {
  checkAIRateLimit, checkRouteRateLimit, routeRateLimitedResponse,
  checkSoloRateLimit, soloRateLimitKey, soloRateLimitedResponse, limiterUnavailableResponse,
} from "../_shared/rate-limit.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// P2 Pillar C (Compute & Resilience): cache the deterministic Router LLM call.
import { cached } from "../_shared/cache.ts";
// Pillar O (Observability): expose a /health probe for the gateway status page.
import { handleHealth } from "../_shared/health.ts";
import { log } from "../_shared/logger.ts";
// Pillar I (Gateway Spine): verify hive membership before service-role asset/action reads.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
// Persona Contract: narrated-specialist mode — router returns its route
// JSON plus a `narration` field in the persona's voice.
// See WORKHIVE_PERSONA_CONTRACT.md.
import { clampPersona, buildPersonaBlock } from "../_shared/persona.ts";
// Deterministic routing core (Arc H H2 oracle). The kind allowlist, confidence
// clamp, slot-fill guard, and asset disambiguation live in _shared so the exact
// code the value-oracle (tests/voice-router-determinism.spec.ts) exercises is
// the code that runs in production — one source, zero drift.
import {
  sanitiseIntents, pickPrimaryCandidate,
  ASSET_REQUIRED_KINDS, SLOT_FILL_CEILING,
  type VoiceIntent, type AssetCandidate,
} from "../_shared/voice-router-core.ts";
// The router's own limiter is skipped ONLY for a call ai-gateway genuinely forwarded (it already limited the
// person) - proven by a header the gateway mints, never by a body field a caller can set.
import { isTrustedGatewayForward } from "../_shared/gateway-trust.ts";
// The narration is a PROPOSAL (nothing is saved until the person confirms): a past-tense "logged / saved /
// deducted" claim in it is false by construction and is replaced by an honest line.
import { honestProposalNarration } from "../_shared/action_provenance.ts";

// Warm module-scope Supabase client. Reused across request invocations
// in the same warm container. Per-request createClient calls below are
// being phased out (PRODUCTION_FIXES #46). Falls back to an empty
// client if env is missing so module import never throws.
const _WH_SUPABASE_URL_M = Deno.env.get("SUPABASE_URL") || "";
const _WH_SERVICE_KEY_M  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const _whWarmClient = _WH_SUPABASE_URL_M && _WH_SERVICE_KEY_M
  ? createClient(_WH_SUPABASE_URL_M, _WH_SERVICE_KEY_M)
  : null;
void _whWarmClient;

// ─── Constants ────────────────────────────────────────────────────────────────

const MAX_TRANSCRIPT_CHARS = 500;
const RATE_LIMIT_PER_HOUR  = Number(Deno.env.get("WH_RATE_LIMIT_OVERRIDE") || 50);
const MAX_TOKENS_OUT       = 800;
const ASSET_CANDIDATE_CAP  = 5;

// VALID_KINDS, ASSET_REQUIRED_KINDS, SLOT_FILL_CEILING, sanitiseIntents,
// pickPrimaryCandidate, and the AssetCandidate/VoiceIntent types now live in
// ../_shared/voice-router-core.ts (imported above) — the deterministic routing
// core, value-oracle-tested by tests/voice-router-determinism.spec.ts.

const ROUTER_SYSTEM = `You are the WorkHive Voice Action Router for a Philippine industrial maintenance platform.
A worker spoke a sentence. Identify the action(s) and extract entities. Respond ONLY with JSON, no markdown.

Output schema:
{
  "intents": [
    {
      "kind": "logbook.create" | "inventory.deduct" | "pm.complete" | "asset.lookup" | "query.ask" | "unknown",
      "confidence": <0..1>,
      "params": { ...kind-specific... }
    }
  ],
  "mentioned_assets": [<string>...],
  "narration": <string - 1-2 sentences in your persona's voice that the worker hears alongside the route decision. It is a PROPOSAL, because NOTHING IS SAVED when they hear it: say what WILL happen once they confirm, in future or conditional tense, for example "I can log a <hours>-hour <job> on <machine>. Confirm to fill the form." Paraphrase only what's in the intents above; never invent.>
}

Kind contracts (params shape per kind):

logbook.create — worker described a job they did or are doing
  params: {
    machine: <string|null>,        // equipment tag or name as spoken
    maintenance_type: <"Breakdown / Corrective" | "Preventive" | "Inspection" | "Other" | null>,
    problem: <string|null>,         // what was wrong
    action: <string|null>,          // what they did
    root_cause: <string|null>,
    downtime_hours: <number|null>,  // numeric only
    parts_used: [{ part_name: <string>, qty: <number> }, ...] | [],
    is_loto: <true|false|null>,
    status: <"Open"|"Closed"|null>
  }

inventory.deduct — worker pulled parts from stock
  params: {
    parts: [{ part_name: <string>, qty: <number> }, ...]
  }

pm.complete — worker finished a PM task
  params: {
    machine: <string|null>,
    task_summary: <string|null>     // what scope item or PM was done
  }

asset.lookup — worker asked for info about an asset (no write)
  params: {
    machine: <string|null>,
    question: <string>              // what they want to know
  }

query.ask — fall through to the general assistant
  params: {
    question: <string>
  }

Rules:
1. Be conservative on confidence. < 0.5 means the page should ask for confirmation.
2. mentioned_assets is a flat array of every asset/equipment tag or name in the sentence (deduplicated).
3. Never invent values. If the worker did not say a number, return null.
4. No em dashes in any string. Use colons, commas, parentheses, or restructure.
5. Filipino industrial vocabulary is fine (PEC, PSME, ISO 14224 terms).
6. If the sentence is unclear, return one intent of kind "unknown" with confidence 0.0 and the original transcript in params.question.
7. The narration never says the platform already did something. You only read the sentence: nothing is logged, saved, deducted, recorded or marked complete until the worker confirms on the page. Use "I can log", "Confirm and I will deduct", "Ready to mark the PM complete once you confirm", never "logged", "you logged", "saved", "deducted", "marked complete" or "Done". The worker's OWN physical work may stay in the past tense (they did replace the part).`;

// ─── Types ────────────────────────────────────────────────────────────────────
// AssetCandidate and VoiceIntent are imported from _shared/voice-router-core.ts.

interface RouterResponse {
  transcript:        string;
  intents:           VoiceIntent[];
  mentioned_assets:  string[];
  // Persona narration (1-2 sentences in Hezekiah/Zaniah voice). The frontend
  // plays / displays this alongside the structured route decision.
  narration:         string;
  asset_resolution?: {
    primary?:    AssetCandidate;
    candidates:  AssetCandidate[];
    ambiguous:   boolean;
  };
  remaining:         number;
}

// ─── Rate limit gate ──────────────────────────────────────────────────────────

// Rate limiting uses the SHARED limiter (see the _shared/rate-limit.ts import above), not a local copy.
// WHY (2026-07-23, §12 flywheel D12 walk): the local copy tracked ONLY the hourly window and never
// incremented `day_count`, so this surface silently BYPASSED the hive's DAILY AI ceiling - a real
// free-tier cost bound, not style drift. The shared limiter enforces hour AND day in one place and is
// a drop-in swap (same .allowed/.remaining used below). This REPLACES an existing limit rather than
// adding one, so it introduces NO double-limiting on this gateway-routed specialist (the A-P3
// "don't double-limit a gateway-routed fn" rule is respected). Do not re-inline a local copy.

// ─── Asset resolution via v_asset_truth (canonical) ───────────────────────────

// ★A PERSON WITH NO HIVE HAS A REGISTER TOO (LM-V walk, LM473, 2026-10-07). A solo owner's machines are
// asset_nodes rows with hive_id NULL and their own auth_uid - the same scope asset-hub, logbook and
// pm-scheduler already read for them. So the lookup takes EITHER a proven hive OR the caller's VERIFIED
// uid (never a client-sent id), and with neither it reads nothing: this runs on the service-role client,
// so an unscoped query here would search every hive's register at once.
async function resolveAssetCandidates(
  db: SupabaseClient,
  hiveId: string,
  mentioned: string[],
  ownerUid: string | null = null,
): Promise<AssetCandidate[]> {
  if (!mentioned.length) return [];
  if (!hiveId && !ownerUid) return [];

  // Escape LIKE wildcards on each mention so user-controlled input cannot
  // over-match (per security skill rule).
  const safeMentions = mentioned
    .map(m => m.trim())
    .filter(Boolean)
    .map(m => m.replace(/%/g, "\\%").replace(/_/g, "\\_"))
    .slice(0, 8);
  if (!safeMentions.length) return [];

  // Canonical: v_asset_truth (domain=asset_truth in canonical_sources).
  // Build an .or() filter that searches tag and name for each mention.
  const ors: string[] = [];
  for (const m of safeMentions) {
    ors.push(`tag.ilike.%${m}%`);
    ors.push(`name.ilike.%${m}%`);
  }
  const orFilter = ors.join(",");

  const base = db.from("v_asset_truth").select("asset_id, tag, name, hive_id");
  const scoped = hiveId
    ? base.eq("hive_id", hiveId)
    : base.is("hive_id", null).eq("auth_uid", ownerUid as string);
  const { data } = await scoped
    .or(orFilter)
    .order("tag")       // a tie between two of a person's machines resolves the same way every time
    .limit(ASSET_CANDIDATE_CAP);

  return (data || []) as AssetCandidate[];
}

// sanitiseIntents() and pickPrimaryCandidate() — the deterministic routing core
// (kind allowlist, confidence clamp, slot-fill guard, asset disambiguation) —
// are imported from ../_shared/voice-router-core.ts and value-oracle-tested by
// tests/voice-router-determinism.spec.ts (Arc H H2). ASSET_REQUIRED_KINDS and
// SLOT_FILL_CEILING (used by the handler below) are imported from there too.

// ─── Handler ──────────────────────────────────────────────────────────────────

serveObserved("voice-action-router", tracedReply("voice-action-router", async (req, trace) => {
  // one trace id per request (tracedReply): every JSON reply returns it, and every model call's ai_cost_log row
  // carries the same id (LM-O, 2026-10-08)
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  // Pillar O: /health probe (short-circuits before auth/body parsing).
  const healthResp = await handleHealth(req, "voice-action-router", async () => ({
    deps: [
      { name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) },
      { name: "ai-chain", ok: Boolean(Deno.env.get("GROQ_API_KEY") || Deno.env.get("GEMINI_API_KEY") || Deno.env.get("MISTRAL_API_KEY") || Deno.env.get("OPENROUTER_API_KEY")) },
    ],
  }));
  if (healthResp) return healthResp;

  const _logCtx = trace;
  log.info(_logCtx, "request_start", { method: req.method });

  try {
    const body = await req.json().catch(() => ({}));
    // The gateway (Companion Unification Step 4) forwards `message` + `transcript`
    // and nests page/asset/persona inside a `context` object, whereas direct
    // callers send `transcript` + flat `context_page`/`context_asset_id`/`persona`.
    // Accept BOTH shapes so this fn works direct AND behind ai-gateway.
    const ctxObj = (body.context && typeof body.context === "object")
      ? body.context as Record<string, unknown>
      : {};
    // (`body.gateway` is NOT read here: whether this call skips its own limiter is decided below from a header
    // only ai-gateway can mint - any caller can write `gateway: true` into a body.)
    const transcript_raw = String(body.transcript || body.message || "").trim();
    const hive_id        = String(body.hive_id || "").trim();
    const context_page   =
      (body.context_page ? String(body.context_page) : (ctxObj.page ? String(ctxObj.page) : "")).trim() || null;
    const context_asset_id =
      (body.context_asset_id ? String(body.context_asset_id) : (ctxObj.asset_id ? String(ctxObj.asset_id) : "")).trim() || null;

    if (!transcript_raw) {
      return new Response(
        JSON.stringify({ error: "Missing required field: transcript" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
    // Cap transcript per ai-engineer skill (prompt-injection / TPM guard).
    const transcript = transcript_raw.slice(0, MAX_TRANSCRIPT_CHARS);

    const db = createClient(
      Deno.env.get("SUPABASE_URL") || "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
    );

    // Pillar I: resolves assets/actions for a hive scoped by the client hive_id
    // on a service-role client — verify membership. The ai-gateway forwards the
    // caller's own JWT, so a person behind the gateway is checked here too; only a
    // genuine service-role caller skips.
    // ★A SIGNED-IN PERSON WITH NO HIVE WAS REFUSED AFTER THEY HAD SPOKEN (LM-V walk, LM473, 2026-10-07). This
    // function answered every hive-less call 400 "Missing required field: hive_id" - and the companion, knowing it
    // would, told a solo owner "Voice needs a hive" only once they had finished recording. Classifying a sentence
    // needs no hive: the prompt carries no hive data and the route cache is hive-independent. The one hive read is
    // asset resolution, and a hive-less person has their own register for that (resolveAssetCandidates). So a person
    // with no hive is served on their VERIFIED identity (the LM389 precedent, marketplace-listing-assist): no
    // identity, no service; a hive that IS sent is still proven by membership exactly as before.
    // Every hive-scoped step below (both limiters, the asset reads) keys on verifiedHiveId - the hive membership PROVED
    // (or a trusted service-role caller named), never the raw body field (Pillar P; the visual-defect-capture fix,
    // 2026-10-08). "" = no hive: the hive-less person in soloUid.
    let verifiedHiveId = "";
    let soloUid: string | null = null;
    {
      const { authUid, isServiceRole } = await resolveIdentity(db, req);
      if (hive_id) {
        if (!isServiceRole) {
          const t = await resolveTenancy(db, authUid, hive_id);
          if (!t.ok) {
            return new Response(
              JSON.stringify({ error: t.message, code: t.code }),
              { status: t.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
            );
          }
          verifiedHiveId = t.hive_id || "";
        } else {
          verifiedHiveId = hive_id;   // a trusted internal caller (service role) names the hive it already holds
        }
      } else if (authUid) {
        soloUid = authUid;
      } else {
        // a service-role caller names nobody, and an anonymous one names no records to resolve against
        return new Response(
          JSON.stringify(isServiceRole
            ? { error: "Missing required field: hive_id" }
            : { error: "Sign in to use voice commands. They work with or without a hive.", code: "auth_required" }),
          { status: isServiceRole ? 400 : 401, headers: { ...corsHeaders, "Content-Type": "application/json" } },
        );
      }
    }

    // Rate limit gate FIRST. A rejected request must cost zero model tokens.
    // EXCEPTION: when invoked behind ai-gateway, the gateway has ALREADY gated this call ONCE (hive + per-user,
    // or the solo bucket). Re-gating here would double-count the same request. Skip our own gate on the gateway
    // path and let the gateway own rate-limiting (Step 4: "inherit rate-limit for free").
    // ★THE SKIP WAS A BODY FIELD (2026-10-08). It used to be `body.gateway === true` - and the gateway forwards the
    // person's OWN JWT, so a direct caller and the gateway look identical by bearer: anyone signed in could send
    // `gateway: true` straight to this function and skip every limiter on it (hive, per-surface and solo) with
    // free-tier model calls behind each request. The skip now needs the HMAC header ai-gateway mints over the
    // exact bearer it forwards (_shared/gateway-trust.ts); a direct call - with or without `gateway: true` - is
    // rate-limited like any other.
    const viaGateway = await isTrustedGatewayForward(req);
    let remaining = -1;
    if (!viaGateway && soloUid) {
      // a hive-less person's own bucket, keyed on the VERIFIED uid (Pillar P) - the same solo bucket
      // ai-gateway draws on for them, so one human has one budget whichever door they came through
      const _ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
      const srl = await checkSoloRateLimit(db, soloRateLimitKey(soloUid, _ip), undefined, undefined, _ip || null);
      if (!srl.allowed) return soloRateLimitedResponse(corsHeaders, srl.retry_after_seconds, srl.scope);
      remaining = srl.remaining;
    } else if (!soloUid) {
      // D12 per-SURFACE quota, OBSERVE-mode (mirrors the shared gateway pattern). Always counts into
      // (hive, route, hour) via hive_route_calls so per-surface AI pressure is VISIBLE - the
      // hive-wide cap alone cannot show which surface is burning the budget. It does NOT deny:
      // checkRouteRateLimit only enforces when an explicit hive_route_quotas row exists, and
      // none do, so this is a no-op behaviour change. Wrapped: quota bookkeeping must never
      // fail a real request.
      // It runs on BOTH doors (2026-10-08), like every other gateway target's: it is keyed on THIS function's name, a
      // bucket ai-gateway never counts (the gateway's own route row is keyed on the agent id, "voice-action"), so a cap an
      // admin sets on this surface now holds whichever door the call came through. Only the hive bucket below is the
      // gateway's own, and only that is skipped on a proven forward.
      try {
        const _rq = await checkRouteRateLimit(db, verifiedHiveId, "voice-action-router");
        // Denies ONLY when an explicit hive_route_quotas row exists (rq.per_route), so this stays
        // a no-op until an admin sets a cap - while always counting for attribution.
        if (_rq.per_route && !_rq.allowed) return routeRateLimitedResponse(corsHeaders, "voice-action-router", _rq.cap, _rq.retry_after_seconds, _rq.scope);
      } catch { /* empty-catch-allow: per-surface quota bookkeeping must never fail a real request */ }
      if (!viaGateway) {
        const rl = await checkAIRateLimit(db, verifiedHiveId, RATE_LIMIT_PER_HOUR);
        if (!rl.allowed) {
          if (rl.scope === "unavailable") return limiterUnavailableResponse(corsHeaders);
          return new Response(
            JSON.stringify({ error: "AI call limit reached for this hive. Try again in an hour." }),
            { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } },
          );
        }
        remaining = rl.remaining;
      }
    }

    // Build the prompt with page/asset context so the model can disambiguate
    // "this asset" or "the pump" against what the worker is currently viewing.
    const userPrompt = JSON.stringify({
      transcript,
      context: {
        page:     context_page,
        asset_id: context_asset_id,
      },
    });

    // Persona Contract: prepend the narrated-specialist block so the
    // model returns its route JSON AND a `narration` field in the
    // chosen persona's voice. One chain call.
    // Persona may arrive flat (direct caller: body.persona) or nested inside
    // the gateway's context object (ctxObj.persona, which the gateway defaults to
    // the caller's account-level preferred_persona). Two-step clamp->build is
    // required by validate_persona_contract (it does not match a nested call).
    const personaInput = (body as Record<string, unknown>).persona ?? ctxObj.persona;
    const personaKey = clampPersona(personaInput);
    const personaBlock = buildPersonaBlock(personaKey, "narrated-specialist");
    const composedSystem = personaBlock + "\n\n" + ROUTER_SYSTEM;

    // P2 Pillar C: cache the Router LLM call. Like the agentic-rag Router, the
    // intent JSON + persona narration are deterministic on (transcript, page,
    // asset_id, persona) — ALL captured in the key below (userPrompt encodes
    // transcript+page+asset_id; personaKey prefixes it). Hive assets are NOT in
    // the prompt — they're resolved AFTER this call against v_asset_truth — so
    // the cached value is hive-independent: the same spoken command across hives
    // is a cache hit with ZERO cross-hive leakage, and the per-hive asset
    // resolution + slot-fill confirm-floor (Family P) still run fresh on every
    // call downstream of the cache. The companion battery + flywheel replay the
    // same probe transcripts → high repeat-rate. 6h TTL: absorbs a sweep, short
    // enough that prompt/schema changes don't stick behind stale cache.
    // v2 (2026-10-08): the narration contract changed from an acknowledgement to a PROPOSAL (rule 7). A v1 entry
    // may hold a past-tense "you logged ..." narration for up to 6h, so the key moves rather than serve it again.
    const routeCacheKey = `voiceroute:v2:${personaKey}::${userPrompt}`;
    let raw: string;
    try {
      const cr = await cached<string>(
        db, "voice-action-router", routeCacheKey,
        async () => {
          const out = await callAI(userPrompt, {
            systemPrompt: composedSystem,
            temperature:  0.2,
            maxTokens:    MAX_TOKENS_OUT,
            jsonMode:     true,
          });
          return {
            data:      out,
            tokensIn:  estimateTokens(userPrompt) + estimateTokens(composedSystem),
            tokensOut: estimateTokens(out),
          };
        },
        6 * 60 * 60,
      );
      raw = cr.data;
      if (cr.hit) console.log("[voice-action-router] router cache hit");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return new Response(
        JSON.stringify({ error: "AI providers all at capacity. Try again shortly.", detail: msg }),
        { status: 503, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    let parsed: unknown;
    try { parsed = JSON.parse(raw); }
    catch {
      return new Response(
        JSON.stringify({
          error: "The AI reply came back unreadable. Try again.",
          detail: raw.slice(0, 200),
        }),
        { status: 502, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    const { intents, mentioned } = sanitiseIntents(parsed);

    // Resolve any mentioned assets against v_asset_truth (canonical): the proven hive's register, or a
    // hive-less person's own.
    const candidates = await resolveAssetCandidates(db, verifiedHiveId, mentioned, soloUid);
    const { primary, ambiguous } = pickPrimaryCandidate(candidates, context_asset_id, mentioned);

    // P7 unresolved-asset slot-fill (2026-06-14, Family P finding). The blank-asset guard in
    // sanitiseIntents only catches an EMPTY machine; a non-blank but NON-EXISTENT tag ("Log a
    // failure on P-203" when only AC-001..030 exist) slipped through at confidence 0.95, forming a
    // confident write against an asset in no hive. Here — AFTER canonical resolution — demote any
    // asset-required write whose machine resolves to NO real asset below the confirm floor, so the
    // page slot-fills ("did you mean a registered asset?") exactly like the blank case. Conservative:
    // a tag that resolves (exact or fuzzy name/tag match) is UNTOUCHED, so a legit write to a real
    // (or newly-mentioned-but-resolved) asset is never demoted. Non-destructive: demotion only adds a
    // confirmation step on the page; it never blocks or rewrites.
    const _knownTags = new Set(candidates.map((c) => String(c.tag || "").toUpperCase()).filter(Boolean));
    const _knownNames = candidates.map((c) => String(c.name || "").toUpperCase()).filter(Boolean);
    for (const it of intents) {
      if (!ASSET_REQUIRED_KINDS.has(it.kind)) continue;
      const machine = String((it.params as Record<string, unknown>).machine || "").trim();
      if (!machine) continue;  // empty machine already demoted in sanitiseIntents
      const m = machine.toUpperCase();
      const resolved = _knownTags.has(m) || _knownNames.some((nm) => nm.includes(m) || m.includes(nm));
      if (!resolved && it.confidence >= SLOT_FILL_CEILING) {
        it.confidence = Math.min(it.confidence, SLOT_FILL_CEILING);
        (it.params as Record<string, unknown>)._unresolved_asset = true;
        (it.params as Record<string, unknown>)._needs_asset = true;
      }
    }

    // Pull narration from the parsed JSON (capped to keep responses sane).
    // ★IT SAID "YOU LOGGED" WHEN NOTHING WAS SAVED (2026-10-07). This function only classifies; the page writes
    // nothing until the person confirms. The model narrated "Naks, you logged a 2 hour brake pad replacement" anyway,
    // and the platform's false-done rail never saw it: the gateway applies that rail only to advisory agents, and
    // listed this route as an executor whose "logged" is true. The prompt now asks for a proposal (rule 7); this is
    // the deterministic half - any past-tense platform-write claim is removed and an honest line takes its place,
    // on the direct path and behind the gateway alike (the gateway passes this narration through unchanged).
    const narrationRaw = typeof (parsed as Record<string, unknown>).narration === "string"
      ? String((parsed as Record<string, unknown>).narration).trim() : "";
    const honest = honestProposalNarration(narrationRaw, 280);
    const narration = honest.narration;
    if (honest.stripped.length) {
      log.info(_logCtx, "proposal_done_claim_stripped", { stripped: honest.stripped.length });
    }

    const response: RouterResponse = {
      transcript,
      intents,
      mentioned_assets: mentioned,
      narration,
      remaining,
    };

    if (candidates.length) {
      response.asset_resolution = {
        primary,
        candidates,
        ambiguous,
      };
    }

    return new Response(JSON.stringify(response), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "voice-action-router", "voice_action_router_error", err);
  }
}));
