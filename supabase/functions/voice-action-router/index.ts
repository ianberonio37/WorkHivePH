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
 * Input:  { transcript, hive_id, context_page?, context_asset_id? }
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

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
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

const VALID_KINDS = new Set([
  "logbook.create",
  "inventory.deduct",
  "pm.complete",
  "asset.lookup",
  "query.ask",
  "unknown",
]);

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
  "narration": <string - 1-2 sentence prose acknowledgement in your persona's voice; what the worker hears alongside the route decision. Paraphrase only what's in the intents above; never invent.>
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
6. If the sentence is unclear, return one intent of kind "unknown" with confidence 0.0 and the original transcript in params.question.`;

// ─── Types ────────────────────────────────────────────────────────────────────

interface AssetCandidate {
  asset_id: string;
  tag:      string;
  name:     string;
  hive_id:  string;
}

interface VoiceIntent {
  kind:        string;
  confidence:  number;
  params:      Record<string, unknown>;
}

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

async function checkAIRateLimit(
  db: SupabaseClient, hiveId: string, limitPerHour: number,
): Promise<{ allowed: boolean; remaining: number }> {
  const windowStart = new Date(Date.now() - 60 * 60 * 1000);

  const { data } = await db
    .from("ai_rate_limits")
    .select("call_count, window_start")
    .eq("hive_id", hiveId)
    .maybeSingle();

  if (!data || new Date(data.window_start) < windowStart) {
    await db.from("ai_rate_limits").upsert({
      hive_id:      hiveId,
      call_count:   1,
      window_start: new Date().toISOString(),
    });
    return { allowed: true, remaining: limitPerHour - 1 };
  }
  if (data.call_count >= limitPerHour) {
    return { allowed: false, remaining: 0 };
  }
  await db.from("ai_rate_limits")
    .update({ call_count: data.call_count + 1 })
    .eq("hive_id", hiveId);
  return { allowed: true, remaining: limitPerHour - data.call_count - 1 };
}

// ─── Asset resolution via v_asset_truth (canonical) ───────────────────────────

async function resolveAssetCandidates(
  db: SupabaseClient,
  hiveId: string,
  mentioned: string[],
): Promise<AssetCandidate[]> {
  if (!mentioned.length) return [];

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

  const { data } = await db.from("v_asset_truth")
    .select("asset_id, tag, name, hive_id")
    .eq("hive_id", hiveId)
    .or(orFilter)
    .limit(ASSET_CANDIDATE_CAP);

  return (data || []) as AssetCandidate[];
}

function pickPrimaryCandidate(
  candidates: AssetCandidate[],
  contextAssetId: string | null,
  mentioned: string[],
): { primary?: AssetCandidate; ambiguous: boolean } {
  if (!candidates.length) return { ambiguous: false };

  // 1. Page context wins if its asset_id appears in candidates.
  if (contextAssetId) {
    const ctx = candidates.find(c => c.asset_id === contextAssetId);
    if (ctx) return { primary: ctx, ambiguous: false };
  }

  // 2. Exact case-insensitive tag match wins next.
  for (const m of mentioned) {
    const lower = m.toLowerCase();
    const exact = candidates.find(
      c => (c.tag || "").toLowerCase() === lower || (c.name || "").toLowerCase() === lower,
    );
    if (exact) return { primary: exact, ambiguous: false };
  }

  // 3. Single candidate wins by default.
  if (candidates.length === 1) return { primary: candidates[0], ambiguous: false };

  // 4. Multiple candidates and no clear winner: ambiguous, page asks user.
  return { primary: candidates[0], ambiguous: true };
}

// ─── Validate / sanitise the AI's parsed JSON ────────────────────────────────

// Slot-fill guard (WAT, 2026-06-12): a write/lookup intent that names NO asset
// cannot be executed — a live A3 probe found "log a failure" (no machine) routed
// to a confident logbook.create @0.8 with machine=null, which would write a junk
// logbook entry against no asset. The router prompt already asks the LLM to be
// conservative, but it does not reliably demote a param-less write. So we enforce
// it deterministically here (WAT: the gate is code, not the model's confidence):
// for kinds whose REQUIRED slot is the asset, a missing/blank machine demotes
// confidence below the 0.5 confirmation floor so the page slot-fills ("which
// asset?") instead of silently writing. inventory.deduct is intentionally NOT in
// this set — its required slot is the part, not the machine (e.g. "pulled two
// seals from stock"), so guarding it on machine would break valid deductions.
const ASSET_REQUIRED_KINDS = new Set(["logbook.create", "pm.complete", "asset.lookup"]);
const SLOT_FILL_CEILING = 0.45; // just under the 0.5 confirmation floor

function sanitiseIntents(parsed: unknown): { intents: VoiceIntent[]; mentioned: string[] } {
  const obj = (parsed && typeof parsed === "object") ? parsed as Record<string, unknown> : {};
  const rawIntents = Array.isArray(obj.intents) ? obj.intents : [];
  const intents: VoiceIntent[] = [];

  for (const r of rawIntents) {
    const ri = (r && typeof r === "object") ? r as Record<string, unknown> : {};
    const kind = String(ri.kind || "unknown");
    if (!VALID_KINDS.has(kind)) continue;
    const conf = typeof ri.confidence === "number" ? ri.confidence : 0;
    const params = (ri.params && typeof ri.params === "object")
      ? ri.params as Record<string, unknown>
      : {};
    let confidence = Math.max(0, Math.min(1, conf));
    // Slot-fill demotion: asset-required intent with no machine -> below floor.
    const machine = params.machine;
    const hasAsset = typeof machine === "string" && machine.trim().length > 0;
    if (ASSET_REQUIRED_KINDS.has(kind) && !hasAsset) {
      confidence = Math.min(confidence, SLOT_FILL_CEILING);
      params._needs_asset = true; // hint for the page to ask "which asset?"
    }
    intents.push({ kind, confidence, params });
  }

  const mentioned = Array.isArray(obj.mentioned_assets)
    ? obj.mentioned_assets.filter((m: unknown) => typeof m === "string" && m.trim().length)
    : [];

  return { intents, mentioned: Array.from(new Set(mentioned as string[])) };
}

// ─── Handler ──────────────────────────────────────────────────────────────────

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  // Pillar O: /health probe (short-circuits before auth/body parsing).
  const healthResp = await handleHealth(req, "voice-action-router", async () => ({
    deps: [
      { name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) },
      { name: "ai-chain", ok: Boolean(Deno.env.get("GROQ_API_KEY") || Deno.env.get("CEREBRAS_API_KEY")) },
    ],
  }));
  if (healthResp) return healthResp;

  const _logCtx = beginRequest(req, { route: "voice-action-router" });
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
    const viaGateway = body.gateway === true;
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
    if (!hive_id) {
      return new Response(
        JSON.stringify({ error: "Missing required field: hive_id" }),
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
    // on a service-role client — verify membership. The ai-gateway/platform-
    // gateway forward is service-role and skips.
    {
      const { authUid, isServiceRole } = await resolveIdentity(db, req);
      if (!isServiceRole) {
        const t = await resolveTenancy(db, authUid, hive_id);
        if (!t.ok) {
          return new Response(
            JSON.stringify({ error: t.message, code: t.code }),
            { status: t.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
          );
        }
      }
    }

    // Rate limit gate FIRST. A rejected request must cost zero model tokens.
    // EXCEPTION: when invoked behind ai-gateway (gateway:true), the gateway has
    // ALREADY gated this call ONCE (hive + per-user). Re-gating here would
    // double-count the same request against the hive bucket. Skip our own gate
    // on the gateway path and let the gateway own rate-limiting (Step 4: "inherit
    // rate-limit for free"). Direct callers still get gated here.
    let remaining = -1;
    if (!viaGateway) {
      const rl = await checkAIRateLimit(db, hive_id, RATE_LIMIT_PER_HOUR);
      if (!rl.allowed) {
        return new Response(
          JSON.stringify({ error: "AI call limit reached for this hive. Try again in an hour." }),
          { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } },
        );
      }
      remaining = rl.remaining;
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
    const routeCacheKey = `voiceroute:${personaKey}::${userPrompt}`;
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
          error: "Could not parse model output as JSON",
          detail: raw.slice(0, 200),
        }),
        { status: 502, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    const { intents, mentioned } = sanitiseIntents(parsed);

    // Resolve any mentioned assets against v_asset_truth (canonical).
    const candidates = await resolveAssetCandidates(db, hive_id, mentioned);
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
    const narrationRaw = typeof parsed.narration === "string" ? parsed.narration.trim() : "";
    const narration = narrationRaw.slice(0, 280);

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
    const msg = err instanceof Error ? err.message : String(err);
    // Inline JSON.stringify({ error: ... }) for the static error-contract scan.
    return new Response(
      JSON.stringify({ error: "Internal error", detail: msg }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }
});
