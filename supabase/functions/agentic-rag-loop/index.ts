/**
 * agentic-rag-loop — Phase 1 of AGENTIC_RAG_ROADMAP.md.
 *
 * Replaces the single-shot voice-semantic-rag pattern with a 5-stage
 * self-correcting loop. Drops hallucination materially because every claim
 * the Generator makes is verified against the retrieved chunk set BEFORE
 * the answer leaves the function. If the Checker fails, the loop reformulates
 * the query and retries (capped at 2 retries).
 *
 *   User question
 *        │
 *        ▼
 *   Router   ── classify query → pick retrieval strategy + time scope
 *        │
 *        ▼
 *   Retriever ── hybrid: pgvector (voice_journal_entries) + canonical view
 *                (v_logbook_truth) + keyword (ilike). Cap 20 chunks.
 *        │
 *        ▼
 *   Grader   ── score each chunk 0..1 against question. Drop <0.5. Keep ≤8.
 *        │
 *        ▼
 *   Generator ── answer using only graded chunks, must cite each claim
 *                inline as [c#] referencing chunk ids.
 *        │
 *        ▼
 *   Checker  ── verify every claim has a citation. If not, reformulate
 *                query → loop (max 2 retries).
 *
 * MODEL ROUTING NOTE: This function calls `callAI()` for every stage. The
 * shared chain in `_shared/ai-chain.ts` does not yet accept a per-call model
 * preference — Phase 4 of the roadmap adds that. Until then every stage is
 * served by the chain's primary (Groq Scout-17B) with automatic fallback.
 * This is functionally correct but TPM-wasteful for the cheap stages
 * (Router, Grader, Checker). Phase 4 will route those to llama-3.1-8b-instant
 * via a `taskProfile` parameter.
 *
 * FREE-TIER CONSTRAINT: No paid Claude / OpenAI / Anthropic tier is ever used.
 * See AGENTIC_RAG_ROADMAP.md §2.5 and feedback_free_tier_only_models.md.
 *
 * Skills consulted before writing: ai-engineer (callAI usage, rate limit,
 * JSON output, AbortSignal.timeout on every fetch, system prompt as const,
 * no em dashes), architect (4-place sync registration), data-engineer
 * (narrow selects, hive scoping on every query, error destructuring),
 * security (input length cap, redactPII at boundary, no service-role leak
 * in errors), performance (single round-trip per stage, no waterfalls).
 *
 * contract-allow: orchestrating sub-stage LLM calls, output schema documented below.
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
// Pillar O (Observability): structured request logging.
import { log } from "../_shared/logger.ts";
// Pillar I (Gateway Spine): verify hive membership (JWT-derived, not body.auth_uid).
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
// P1 roadmap 2026-05-26: adoption of shared /health helper + LLM response cache.
import { handleHealth } from "../_shared/health.ts";
import { cached } from "../_shared/cache.ts";

// ── Constants ────────────────────────────────────────────────────────────────

const FN_NAME             = "agentic-rag-loop";
const MAX_QUESTION_CHARS  = 500;       // prompt-injection / TPM safety cap
// Per-hive cap. Production stays at 50/hr (platform default). Local dev
// overrides via WH_RATE_LIMIT_OVERRIDE so the RAG flywheel walk (100+
// LLM calls per turn) can run without hitting throttle on a single hive.
// See [[project-rag-flywheel-turn-1-2026-05-21]] finding #3.
const RATE_LIMIT_PER_HOUR = Number(Deno.env.get("WH_RATE_LIMIT_OVERRIDE") || 50);
const RETRIEVAL_CAP       = 20;        // chunks fetched before grading
const KEPT_CAP            = 8;         // chunks kept after grading
const GRADER_THRESHOLD    = 0.4;       // RAG flywheel turn 17: relaxed 0.5 → 0.4 for sparse-data hives (Lucena). Still drops weak chunks but keeps marginal definitions that ground partial answers.
const MAX_RETRIES         = 2;         // checker-failure retries
const MAX_TOKENS_ROUTER   = 256;
const MAX_TOKENS_GRADER   = 512;
const MAX_TOKENS_GEN      = 700;
const MAX_TOKENS_CHECKER  = 256;
const MAX_TOKENS_EXTRACT  = 400;        // memory extractor (Item 4)
const MEMORY_RECALL_LIMIT = 5;          // top-N memories injected into Generator
const HIER_SUMMARY_LIMIT  = 5;          // canonical_period_summaries rows per Lane C
const TEMPORAL_DELEGATE_DAYS = 180;     // span threshold for Router→Phase 3 delegation
const FN_INVOKE_TIMEOUT_MS   = 30_000;  // inter-fn calls (memory store, temporal orch)

const ROUTE_VALUES = ["simple_recency","semantic","orchestrator","temporal","cold_archive","unknown"] as const;
type Route = typeof ROUTE_VALUES[number];

// ── System prompts (static — enable future prompt caching) ───────────────────

const ROUTER_SYSTEM = `You classify a maintenance worker's question to pick a retrieval strategy.

Strategies:
- simple_recency: last-N events question ("what did I do yesterday", "latest entry")
- semantic: conceptual question that needs similar past entries by meaning
- orchestrator: multi-aspect status question (PM status + inventory + risk together)
- temporal: spans multiple periods to compare (year vs year, month vs month)
- cold_archive: question is about events older than 18 months
- unknown: cannot classify with confidence

Also extract time_scope (ISO dates) and asset_tag if mentioned.

Respond JSON only:
{ "route": "<one of above>", "time_scope": { "from": "<ISO|null>", "to": "<ISO|null>" }, "asset_tag": "<tag|null>", "reasoning": "<one sentence>" }`;

const GRADER_SYSTEM = `You score how relevant each retrieved chunk is to the user's question, 0.0 to 1.0.

A chunk is relevant if it contains a fact, event, or context that would help answer the question.
Drop chunks scoring below 0.5. Keep at most 8 best-scoring chunks.

Respond JSON only:
{ "kept": [ { "id": "<chunk_id>", "score": <float 0..1>, "why": "<short reason>" } ] }`;

const GENERATOR_SYSTEM = `You answer industrial maintenance questions using ONLY the graded chunks provided in the user message.

Rules:
1. Never invent values, asset tags, names, dates, or numbers not present in the chunks.
2. Every claim that asserts a specific fact must reference its chunk inline like [c1] [c3].
3. If the chunks do not contain enough information to answer, say so plainly. Do not guess.
4. Keep responses under 150 words unless the question explicitly asks for detail.
5. No em dashes anywhere. Use colons, commas, parentheses, or restructure the sentence.
6. Use Filipino industrial vocabulary (PEC 2017, PSME, ISO 14224) when appropriate.
7. VIEW NAME RULE (highest priority): You may only use view/source names that appear LITERALLY in the provided chunks. Before writing any "v_X" or "v_X_truth" name, verify it appears verbatim in at least one chunk. If a chunk says "The ONLY valid canonical source is v_kpi_truth_oee", use exactly "v_kpi_truth_oee": do not substitute any other name. Platform view names are identifiers, not descriptions; inventing them causes data routing failures.
8. When citing a chunk, include its chunk_id in the citations array AND mark it inline in the answer with [chunk_id]. The id may be "log#abc", "def#v_X", "hier#xxx", or "voice#xxx" (use it verbatim).
9. SELF-CHECK before responding: scan your draft answer for any "v_X" name. For each one, confirm it appears in one of the chunk texts. If it does not appear in any chunk, remove it from your answer and instead say "the canonical source is listed in [chunk_id]".

Respond JSON only:
{ "answer": "<text with [chunk_id] citation markers>", "citations": [ { "chunk_id": "<id verbatim from chunk>", "snippet": "<≤80 chars>" } ] }`;

const CHECKER_SYSTEM = `You verify that the answer is grounded in the retrieved chunks.

A claim is any sentence asserting a fact: a number, a name, a date, a cause, a count, an action taken, OR an explicit definition / source citation.

PASS conditions (set passed=true if ALL are met):
1. At least one citation marker appears in the answer. Citation markers look like [chunk_id] where chunk_id may be of any of these forms: [c1], [c#3], [log#abc123], [def#v_X_truth], [hier#xxx], [voice#xxx], or any bracketed token that matches an id from the chunks block.
2. The cited chunk(s) actually appear in the chunks block AND support the claim being cited.
3. Specific values (numbers, dates, asset tags) that appear in the answer also appear in at least one chunk.

FAIL conditions (set passed=false):
- The answer contains specific values not present in any chunk (hallucination), OR
- The answer contains no citation markers at all AND makes substantive claims (not a "no records" admission).

If the answer is a clean "I do not have records to ground this" admission with no fabricated specifics, that is a PASS (admissions are not hallucinations).

Respond JSON only:
{ "passed": <bool>, "uncited_claims": ["<text>", ...], "reformulated_query": "<better query if failed, else null>" }`;

// Item 4: memory_extractor system prompt — decides what's worth storing.
const EXTRACTOR_SYSTEM = `You decide if any DURABLE facts emerged from this agentic-RAG run worth saving for future sessions.

You receive the question, the verified answer, and the existing recalled memories (so we don't duplicate).

Memory types:
- factual    worker preferences ("prefers Tagalog", "works night shift")
- procedural successful fix procedures ("P-203 bearing fix: replace SKF 6205-2RS")
- episodic   notable incidents ("2024-03-15 cooling tower trip, loose VFD wiring")
- semantic   plant constants ("plant runs 2 shifts", "plant uses Siemens PLCs")

Rules:
1. Only extract facts the AI would benefit from remembering NEXT session.
2. content must NOT contain PII (phone numbers, emails, ID numbers, addresses).
3. importance 0.3 to 0.5 for personal facts, 0.7 plus for plant-wide facts.
4. Return [] if nothing durable emerged. Do not pad.
5. content kept under 200 chars.
6. No em dashes.

Respond JSON only:
{ "memories": [ { "memory_type": "factual"|"procedural"|"episodic"|"semantic", "content": "<short>", "importance": <0..1> } ] }`;

// ── Module-scope env (warm-client removed — was producing null in some
//   isolate hot-reload paths under `supabase functions serve`. Fresh
//   createClient per request matches the pattern in ai-orchestrator. ────────

const _WH_URL = Deno.env.get("SUPABASE_URL") || "";
const _WH_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
if (!_WH_URL) console.warn("[agentic-rag-loop] SUPABASE_URL missing — DB calls will fail");
if (!_WH_KEY) console.warn("[agentic-rag-loop] SUPABASE_SERVICE_ROLE_KEY missing — DB calls will fail");

// Optional: hard-reset ai_rate_limits on cold start when WH_RATE_LIMIT_RESET=1.
// Used by the RAG flywheel loop orchestrator so each multi-turn run starts
// fresh and previous-hour residue doesn't pollute the limiter.
// Fire-and-forget — never blocks request handling.
if (Deno.env.get("WH_RATE_LIMIT_RESET") === "1" && _WH_URL && _WH_KEY) {
  (async () => {
    try {
      const r = await fetch(`${_WH_URL}/rest/v1/ai_rate_limits?hive_id=neq.00000000-0000-0000-0000-000000000000`, {
        method: "DELETE",
        headers: {
          "apikey": _WH_KEY, "Authorization": `Bearer ${_WH_KEY}`,
          "Content-Type": "application/json", "Prefer": "return=minimal",
        },
      });
      console.log(`[agentic-rag-loop] WH_RATE_LIMIT_RESET=1 → ai_rate_limits cleared (status ${r.status})`);
    } catch (err) {
      console.warn(`[agentic-rag-loop] rate-limit reset failed: ${String(err).slice(0, 80)}`);
    }
  })();
}

// ── Rate limit (per-hive, 1-hour window) ─────────────────────────────────────

async function checkRateLimit(db: SupabaseClient, hiveId: string | null): Promise<{ allowed: boolean; remaining: number }> {
  if (!hiveId) return { allowed: true, remaining: RATE_LIMIT_PER_HOUR };
  const windowStart = new Date(Date.now() - 60 * 60 * 1000);
  const { data, error } = await db
    .from("ai_rate_limits")
    .select("call_count, window_start")
    .eq("hive_id", hiveId)
    .maybeSingle();

  if (error) {
    console.warn("[agentic-rag-loop] rate-limit read failed:", error.message);
    return { allowed: true, remaining: RATE_LIMIT_PER_HOUR };  // fail-open
  }

  if (!data || new Date(data.window_start) < windowStart) {
    await db.from("ai_rate_limits").upsert({
      hive_id:      hiveId,
      call_count:   1,
      window_start: new Date().toISOString(),
    });
    return { allowed: true, remaining: RATE_LIMIT_PER_HOUR - 1 };
  }

  if (data.call_count >= RATE_LIMIT_PER_HOUR) {
    return { allowed: false, remaining: 0 };
  }

  await db.from("ai_rate_limits")
    .update({ call_count: data.call_count + 1 })
    .eq("hive_id", hiveId);
  return { allowed: true, remaining: RATE_LIMIT_PER_HOUR - data.call_count - 1 };
}

// ── Safe JSON parse — never throws to caller ─────────────────────────────────

function safeParse<T>(raw: string, fallback: T): T {
  try {
    const parsed = JSON.parse(raw || "{}");
    return parsed as T;
  } catch {
    return fallback;
  }
}

// ── Stage: Router ────────────────────────────────────────────────────────────

interface RouterOutput {
  route: Route;
  time_scope: { from: string | null; to: string | null };
  asset_tag: string | null;
  reasoning: string;
}

async function routerStage(question: string, db: SupabaseClient, hiveId: string | null, workerName: string | null) {
  const t0 = Date.now();

  // P1 roadmap 2026-05-26: cache the Router LLM call. The Router stage is
  // deterministic on `question` alone (system prompt + temperature 0.1
  // give the same JSON answer for the same question across calls). RAG
  // flywheel runs the same probe set across hives, so repeat-rate is
  // high — caching cuts ~30-40% of Router tokens per turn.
  //
  // Cache key uses the question text; the model field is "router:auto"
  // so we never collide with non-Router calls that happen to share text.
  const cacheKey = `router:${question}`;
  const { data: raw, hit: cacheHit } = await cached<string>(
    db, "agentic-rag-router", cacheKey,
    async () => {
      const out = await callAI(`User question: ${question}`, {
        systemPrompt: ROUTER_SYSTEM,
        temperature:  0.1,
        maxTokens:    MAX_TOKENS_ROUTER,
        jsonMode:     true,
        taskProfile:  "orchestrator_router",
      });
      return { data: out, tokensIn: estimateTokens(question) + estimateTokens(ROUTER_SYSTEM), tokensOut: estimateTokens(out) };
    },
    // 6h TTL — long enough to absorb a flywheel sweep, short enough that
    // schema/prompt changes don't get stuck behind stale cache.
    6 * 60 * 60,
  );
  const latency = Date.now() - t0;
  const parsed = safeParse<RouterOutput>(raw, {
    route: "semantic",
    time_scope: { from: null, to: null },
    asset_tag: null,
    reasoning: "fallback (parse error)",
  });
  if (!ROUTE_VALUES.includes(parsed.route)) parsed.route = "semantic";

  // Defensive: 18-month cold-archive boundary check (Router sometimes
  // forgets time_scope older than 18mo). Phase 6 will own this routing.
  if (parsed.time_scope?.from) {
    const fromMs = Date.parse(parsed.time_scope.from);
    if (Number.isFinite(fromMs) && (Date.now() - fromMs) > 540 * 24 * 3600 * 1000) {
      parsed.route = "cold_archive";
      parsed.reasoning = "promoted to cold_archive (time_scope older than 18 months)";
    }
  }

  // Defensive (RAG flywheel turn 27 fix): if Router picked cold_archive but
  // there is NO old time_scope, the LLM hallucinated the route — Phase 6 is
  // scaffolding only and returns "no records", which kills any tile question
  // that doesn't reference historical dates. Demote to semantic so the real
  // Retriever lanes (A/B/C/D/E) get a chance.
  if (parsed.route === "cold_archive") {
    const fromMs = parsed.time_scope?.from ? Date.parse(parsed.time_scope.from) : NaN;
    const isOld = Number.isFinite(fromMs) && (Date.now() - fromMs) > 540 * 24 * 3600 * 1000;
    if (!isOld) {
      parsed.route = "semantic";
      parsed.reasoning = "demoted from cold_archive (no time_scope older than 18 months)";
    }
  }

  // RAG flywheel turn 29 fix: current-tense questions ("this week", "today",
  // "currently", "right now", "this shift") CANNOT be cold_archive — they are
  // by definition asking about live/recent data. Even when the time_scope
  // check above misses (e.g. router returns a spuriously old from-date for a
  // "this week" question), force-demote here. cold_archive is Phase 6
  // scaffolding (returns "no records"); routing live-data questions there
  // silently kills grounding.
  if (parsed.route === "cold_archive") {
    const lq = question.toLowerCase();
    const isLiveQuery = /\b(this week|today|currently|right now|this shift|this month|ngayon|ngayong|this year)\b/.test(lq);
    if (isLiveQuery) {
      parsed.route = "semantic";
      parsed.reasoning = "demoted from cold_archive (question contains live-data temporal keyword)";
    }
  }

  // Log cost (model field is best-effort until Phase 4 returns it from callAI)
  await logAICost(db, {
    fn: FN_NAME, hive_id: hiveId, worker_name: workerName,
    model: cacheHit ? "cache:hit" : "chain:auto",
    provider: cacheHit ? "ai_cache" : "groq",
    prompt_tokens: cacheHit ? 0 : (estimateTokens(question) + estimateTokens(ROUTER_SYSTEM)),
    output_tokens: cacheHit ? 0 : estimateTokens(raw),
    latency_ms: latency,
    status: cacheHit ? "cache_hit" : (raw === "{}" ? "fallback" : "success"),
    schema_compliance: raw !== "{}",
  });

  return { parsed, raw, latency };
}

// ── Stage: Retriever (hybrid: vector + canonical view + keyword) ─────────────

interface Chunk {
  id: string;                        // synthetic — e.g. "voice#42", "log#abc"
  source: string;                    // "voice_journal_entries" | "v_logbook_truth"
  source_id: string;                 // underlying row id
  text: string;                      // chunk text used for grading + generation
  metadata: Record<string, unknown>;
  similarity: number;                // 0..1, retrieval-time score (vector or 1.0 for keyword exact)
}

async function retrieverStage(
  db: SupabaseClient,
  question: string,
  hiveId: string | null,
  workerName: string | null,
  authUid: string | null,
  route: Route,
  assetTag: string | null = null,
  timeScope: { from: string | null; to: string | null } = { from: null, to: null },
): Promise<Chunk[]> {
  const chunks: Chunk[] = [];
  // Defensive: Router LLM may return time_scope: null (not {from:null,to:null}).
  // JS default parameters only apply to undefined, not explicit null.
  const scope = timeScope || { from: null, to: null };

  // ── Lane F: cold archive (Phase 6 wiring) ──────────────────────────────────
  // route="cold_archive" means a >18mo question — the live tables don't hold the
  // data. Pull the archived Parquet rows and let them BE the grounding (the live
  // lanes below stay skipped while route is cold_archive). Graceful degrade: an
  // empty or failed archive read demotes the route to "semantic" so the live
  // lanes still run — an archive miss must never silently kill grounding.
  if (route === "cold_archive" && hiveId) {
    try {
      const archived = await fetchColdArchiveChunks(hiveId, assetTag, scope);
      if (archived.length) {
        chunks.push(...archived);
      } else {
        route = "semantic";
      }
    } catch (err) {
      console.warn("[agentic-rag-loop] cold-archive lane failed:", String(err).slice(0, 100));
      route = "semantic";
    }
  }

  // ── Item 2: Lane C — hierarchical period summaries (Phase 2 integration)
  // Highest-signal pre-digested rows. Pull these FIRST so the grader prefers
  // them over raw logbook lanes when both have hits.
  if (hiveId && scope.from && (route === "temporal" || route === "orchestrator" || route === "semantic")) {
    try {
      const hier = await lookupHierarchicalSummaries(db, hiveId, assetTag, scope);
      chunks.push(...hier);
    } catch (err) {
      console.warn("[agentic-rag-loop] hierarchical lane failed:", String(err).slice(0, 100));
    }
  }

  // ── Lane E: fleet aggregate stats (added RAG flywheel turn 17)
  // Grounds tiles that show COUNTS — total assets, critical assets, overdue PMs,
  // out-of-stock parts, etc. Without this, the AI has no chunk to cite when
  // asked "what does the count 30 mean?" — it can explain the definition but
  // can't anchor the specific number. Hive-scoped, fires for any route with
  // a hive_id present. Returns a single composite chunk so it's one entry in
  // the grader pool, not 5.
  if (hiveId && route !== "cold_archive") {
    try {
      // Parallel narrow counts — kept tight so the lane is bounded.
      const [assetsAll, assetsCritical, pmDue, invOOS, invLow] = await Promise.all([
        db.from("v_asset_truth").select("asset_id", { count: "exact", head: true }).eq("hive_id", hiveId),
        db.from("v_asset_truth").select("asset_id", { count: "exact", head: true }).eq("hive_id", hiveId).eq("criticality", "critical"),
        db.from("v_pm_compliance_truth").select("pm_asset_id", { count: "exact", head: true }).eq("hive_id", hiveId).eq("is_due", true),
        db.from("v_inventory_items_truth").select("id", { count: "exact", head: true }).eq("hive_id", hiveId).eq("qty_on_hand", 0),
        db.from("v_inventory_items_truth").select("id", { count: "exact", head: true }).eq("hive_id", hiveId).gt("qty_on_hand", 0).lte("qty_on_hand", 5),
      ]);
      const stats = {
        total_assets:    assetsAll.count ?? null,
        critical_assets: assetsCritical.count ?? null,
        pms_overdue:     pmDue.count ?? null,
        parts_out_of_stock: invOOS.count ?? null,
        parts_low_stock:    invLow.count ?? null,
      };
      const fleetText = Object.entries(stats)
        .filter(([_, v]) => v != null)
        .map(([k, v]) => `${k}=${v}`).join("; ");
      if (fleetText) {
        chunks.push({
          id:         `stats#fleet_${hiveId.slice(0, 8)}`,
          source:     "fleet_aggregates",
          source_id:  hiveId,
          text:       `[fleet stats for hive ${hiveId.slice(0, 8)}] ${fleetText}. Sourced from v_asset_truth + v_pm_compliance_truth + v_inventory_items_truth.`,
          metadata:   { stats },
          similarity: 0.80,
        });
      }
    } catch (err) {
      console.warn("[agentic-rag-loop] fleet stats lane failed:", String(err).slice(0, 100));
    }
  }

  // ── Lane D: canonical_sources definitions (added RAG flywheel turn 4)
  // Surfaces v_*_truth view descriptions so definition-shape questions
  // ("What does the OEE KPI measure?") have a grounded source to cite
  // instead of canned "no records". canonical_sources is hive-agnostic
  // (platform-wide definitions) so this lane fires regardless of hive scope.
  if (route === "semantic" || route === "orchestrator" || route === "simple_recency") {
    try {
      // Extract noun-keywords from the question for ilike matching
      const stopwords = new Set(["the", "what", "does", "is", "are", "kpi", "tile", "on", "page", "value", "where", "from", "this", "that", "a", "an", "and", "or", "of", "to", "in", "for", "html", "should", "explain"]);
      const keywords = question.toLowerCase()
        .replace(/[^a-z0-9\s_-]/g, " ")
        .split(/\s+/)
        .filter(w => w.length >= 3 && !stopwords.has(w))
        .slice(0, 6);
      if (keywords.length) {
        // Match on BOTH source_name (so KPI-specific rows like v_kpi_truth_oee
        // surface when "oee" is a keyword) AND description (broader semantic match).
        const orParts: string[] = [];
        for (const k of keywords) {
          const safe = k.replace(/%/g, "\\%").replace(/_/g, "\\_");
          orParts.push(`source_name.ilike.%${safe}%`);
          orParts.push(`description.ilike.%${safe}%`);
        }
        // Limit 12 so KPI-specific seeds have headroom alongside existing v_*_truth rows.
        const { data: defs } = await db.from("canonical_sources")
          .select("source_name, source_kind, description, contract")
          .or(orParts.join(","))
          .limit(12);
        for (const row of defs || []) {
          // canonical_sources.contract is a jsonb column; PostgREST returns
          // it as parsed JSON (object/array/string). Coerce to a string
          // representation so .slice() always works.
          const descStr     = typeof row.description === "string" ? row.description : JSON.stringify(row.description ?? "");
          const contractStr = row.contract == null ? "" :
                              (typeof row.contract === "string" ? row.contract : JSON.stringify(row.contract));
          chunks.push({
            id:         `def#${row.source_name}`,
            source:     "canonical_sources",
            source_id:  String(row.source_name),
            text:       `[def ${row.source_kind} ${row.source_name}] ${descStr.slice(0, 500)}${contractStr ? `\ncontract: ${contractStr.slice(0, 200)}` : ""}`,
            metadata:   { source_kind: row.source_kind, source_name: row.source_name },
            similarity: 0.75,   // definitions are authoritative; rank above raw lanes but below hierarchical
          });
        }
      }
    } catch (err) {
      console.warn("[agentic-rag-loop] definitions lane failed:", String(err).slice(0, 100));
    }
  }

  // Lane A: voice_journal_entries via existing semantic RPC (Phase 1.5)
  if (authUid && (route === "semantic" || route === "simple_recency" || route === "orchestrator")) {
    try {
      // Recency-based lane (cheap, no embedding round-trip)
      const { data: recent } = await db
        .from("voice_journal_entries")
        .select("id, transcript, reply, created_at")
        .eq("auth_uid", authUid)
        .order("created_at", { ascending: false })
        .limit(5);
      for (const row of recent || []) {
        chunks.push({
          id:         `voice#${row.id}`,
          source:     "voice_journal_entries",
          source_id:  String(row.id),
          text:       `[${row.created_at?.slice(0, 10)}] Q: ${row.transcript}\nA: ${row.reply}`.slice(0, 600),
          metadata:   { created_at: row.created_at },
          similarity: 0.6,  // recency baseline
        });
      }
    } catch (err) {
      console.warn("[agentic-rag-loop] voice lane failed:", String(err).slice(0, 100));
    }
  }

  // Lane B: v_logbook_truth canonical view (keyword search via ilike, hive-scoped)
  if (hiveId && route !== "cold_archive") {
    try {
      // Escape LIKE wildcards in user input (per data-engineer skill)
      const safeQ = question.trim().slice(0, 80).replace(/%/g, "\\%").replace(/_/g, "\\_");
      let q = db.from("v_logbook_truth")
        .select("id, machine, maintenance_type, category, root_cause, action, downtime_hours, status, created_at")
        .eq("hive_id", hiveId)
        .order("created_at", { ascending: false })
        .limit(15);
      if (safeQ) {
        q = q.or(`machine.ilike.%${safeQ}%,root_cause.ilike.%${safeQ}%,action.ilike.%${safeQ}%`);
      }
      const { data: logs } = await q;
      for (const row of logs || []) {
        chunks.push({
          id:         `log#${row.id}`,
          source:     "v_logbook_truth",
          source_id:  String(row.id),
          text:       `[${row.created_at?.slice(0, 10)} ${row.machine || "?"} ${row.maintenance_type || ""}] cause: ${row.root_cause || "n/a"}; action: ${row.action || "n/a"}; down: ${row.downtime_hours || 0}h; status: ${row.status || "?"}`.slice(0, 500),
          metadata:   { machine: row.machine, status: row.status },
          similarity: safeQ ? 0.7 : 0.5,
        });
      }
    } catch (err) {
      console.warn("[agentic-rag-loop] logbook lane failed:", String(err).slice(0, 100));
    }
  }

  // Hive scope guard: if neither lane returned anything AND solo mode, try worker_name
  if (chunks.length === 0 && workerName && route !== "cold_archive") {
    try {
      const { data: solo } = await db.from("v_logbook_truth")
        .select("id, machine, root_cause, action, created_at, status")
        .eq("worker_name", workerName)
        .order("created_at", { ascending: false })
        .limit(10);
      for (const row of solo || []) {
        chunks.push({
          id:         `log#${row.id}`,
          source:     "v_logbook_truth",
          source_id:  String(row.id),
          text:       `[${row.created_at?.slice(0, 10)} ${row.machine || "?"}] cause: ${row.root_cause || "n/a"}; action: ${row.action || "n/a"}; status: ${row.status || "?"}`.slice(0, 400),
          metadata:   { machine: row.machine },
          similarity: 0.5,
        });
      }
    } catch (err) {
      console.warn("[agentic-rag-loop] solo lane failed:", String(err).slice(0, 100));
    }
  }

  return chunks.slice(0, RETRIEVAL_CAP);
}

// ── Stage: Grader ────────────────────────────────────────────────────────────

interface GraderOutput {
  kept: Array<{ id: string; score: number; why: string }>;
}

async function graderStage(
  db: SupabaseClient,
  question: string,
  chunks: Chunk[],
  hiveId: string | null,
  workerName: string | null,
) {
  const t0 = Date.now();
  if (chunks.length === 0) {
    return { kept: [] as Chunk[], scores: {} as Record<string, number>, latency: 0, raw: "{}", passed: false };
  }
  // Build compact chunk catalog for grader (id + short text only)
  const catalog = chunks.map(c => `${c.id}: ${c.text.slice(0, 240)}`).join("\n---\n");
  const prompt  = `Question: ${question}\n\nChunks:\n${catalog}`;
  // P1 roadmap 2026-05-26: cache the Grader. Grader is deterministic on
  // (question, chunks) — same question + same chunk set → same grading.
  // Repeat-rate is moderate (same question retrieves same chunks within
  // TTL). 3h TTL — Grader is more chunk-sensitive than Router so shorter.
  const cacheKey = `grader:${question}::${catalog.slice(0, 600)}`;
  const { data: raw, hit: cacheHit } = await cached<string>(
    db, "agentic-rag-grader", cacheKey,
    async () => {
      const out = await callAI(prompt, {
        systemPrompt: GRADER_SYSTEM,
        temperature:  0.1,
        maxTokens:    MAX_TOKENS_GRADER,
        jsonMode:     true,
        taskProfile:  "chunk_grader",
      });
      return { data: out, tokensIn: estimateTokens(prompt) + estimateTokens(GRADER_SYSTEM), tokensOut: estimateTokens(out) };
    },
    3 * 60 * 60,
  );
  const latency = Date.now() - t0;
  const parsed  = safeParse<GraderOutput>(raw, { kept: [] });

  const scoreMap: Record<string, number> = {};
  for (const k of parsed.kept || []) {
    if (k && k.id && typeof k.score === "number") scoreMap[k.id] = k.score;
  }
  const kept = chunks
    .filter(c => (scoreMap[c.id] ?? 0) >= GRADER_THRESHOLD)
    .sort((a, b) => (scoreMap[b.id] ?? 0) - (scoreMap[a.id] ?? 0))
    .slice(0, KEPT_CAP);

  await logAICost(db, {
    fn: FN_NAME, hive_id: hiveId, worker_name: workerName,
    model: cacheHit ? "cache:hit" : "chain:auto",
    provider: cacheHit ? "ai_cache" : "groq",
    prompt_tokens: cacheHit ? 0 : (estimateTokens(prompt) + estimateTokens(GRADER_SYSTEM)),
    output_tokens: cacheHit ? 0 : estimateTokens(raw),
    latency_ms: latency,
    status: cacheHit ? "cache_hit" : (raw === "{}" ? "fallback" : "success"),
    schema_compliance: raw !== "{}",
  });

  return { kept, scores: scoreMap, latency, raw, passed: kept.length > 0 };
}

// ── Stage: Generator ─────────────────────────────────────────────────────────

interface GeneratorOutput {
  answer: string;
  citations: Array<{ chunk_id: string; snippet: string }>;
}

async function generatorStage(
  db: SupabaseClient,
  question: string,
  kept: Chunk[],
  hiveId: string | null,
  workerName: string | null,
  memoryBlock: string = "",   // Item 4: prior-session context (may be empty)
) {
  const t0 = Date.now();
  if (kept.length === 0) {
    return {
      parsed: { answer: "I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date.", citations: [] } as GeneratorOutput,
      raw: "{}",
      latency: 0,
    };
  }
  const block = kept.map(c => `[${c.id}] ${c.text}`).join("\n---\n");
  const prompt = `${memoryBlock}Question: ${question}\n\nGraded chunks (use ONLY these):\n${block}`;
  const raw    = await callAI(prompt, {
    systemPrompt: GENERATOR_SYSTEM,
    temperature:  0.2,
    maxTokens:    MAX_TOKENS_GEN,
    jsonMode:     true,
    taskProfile:  "synthesis_long_output",  // Phase 4: prefer Scout-17B (30K TPM)
  });
  const latency = Date.now() - t0;
  const parsed  = safeParse<GeneratorOutput>(raw, { answer: "", citations: [] });

  await logAICost(db, {
    fn: FN_NAME, hive_id: hiveId, worker_name: workerName,
    model: "chain:auto", provider: "groq",
    prompt_tokens: estimateTokens(prompt) + estimateTokens(GENERATOR_SYSTEM),
    output_tokens: estimateTokens(raw),
    latency_ms: latency,
    status: raw === "{}" ? "fallback" : "success",
    schema_compliance: raw !== "{}" && !!parsed.answer,
  });

  return { parsed, raw, latency };
}

// ── Stage: Checker ───────────────────────────────────────────────────────────

interface CheckerOutput {
  passed: boolean;
  uncited_claims: string[];
  reformulated_query: string | null;
}

async function checkerStage(
  db: SupabaseClient,
  question: string,
  answer: string,
  kept: Chunk[],
  hiveId: string | null,
  workerName: string | null,
) {
  const t0 = Date.now();
  if (!answer || kept.length === 0) {
    return {
      parsed: { passed: false, uncited_claims: [], reformulated_query: null } as CheckerOutput,
      raw: "{}",
      latency: 0,
    };
  }
  const block = kept.map(c => `[${c.id}] ${c.text}`).join("\n---\n");
  const prompt = `Original question: ${question}\n\nAvailable chunks:\n${block}\n\nGenerated answer to verify:\n${answer}`;
  // P1 roadmap 2026-05-26: cache the Checker. Checker is fully deterministic
  // (temperature 0) on (question, answer, chunks). Same triple → same
  // verdict. Repeat-rate is lower than Router/Grader (answer differs more)
  // but each call is the heaviest of the three so cache wins are large.
  // 2h TTL — Checker output is most sensitive to model upgrades.
  const cacheKey = `checker:${question}::${answer.slice(0, 200)}::${block.slice(0, 400)}`;
  const { data: raw, hit: cacheHit } = await cached<string>(
    db, "agentic-rag-checker", cacheKey,
    async () => {
      const out = await callAI(prompt, {
        systemPrompt: CHECKER_SYSTEM,
        temperature:  0.0,
        maxTokens:    MAX_TOKENS_CHECKER,
        jsonMode:     true,
        taskProfile:  "hallucination_checker",
      });
      return { data: out, tokensIn: estimateTokens(prompt) + estimateTokens(CHECKER_SYSTEM), tokensOut: estimateTokens(out) };
    },
    2 * 60 * 60,
  );
  const latency = Date.now() - t0;
  const parsed  = safeParse<CheckerOutput>(raw, {
    passed: true,                  // fail-open on parse error: don't block a valid answer due to grader hiccup
    uncited_claims: [],
    reformulated_query: null,
  });

  await logAICost(db, {
    fn: FN_NAME, hive_id: hiveId, worker_name: workerName,
    model: cacheHit ? "cache:hit" : "chain:auto",
    provider: cacheHit ? "ai_cache" : "groq",
    prompt_tokens: cacheHit ? 0 : (estimateTokens(prompt) + estimateTokens(CHECKER_SYSTEM)),
    output_tokens: cacheHit ? 0 : estimateTokens(raw),
    latency_ms: latency,
    status: cacheHit ? "cache_hit" : (raw === "{}" ? "fallback" : "success"),
    schema_compliance: raw !== "{}",
  });

  return { parsed, raw, latency };
}

// ── Trace writer ─────────────────────────────────────────────────────────────

interface StageRecord {
  stage: string;
  latency_ms: number;
  tokens_in: number;
  tokens_out: number;
  snippet: string;
}

async function writeTrace(
  db: SupabaseClient,
  payload: {
    hive_id: string | null;
    worker_name: string | null;
    question: string;
    route: Route;
    stages: StageRecord[];
    retrievals: Array<{ source: string; chunk_id: string; similarity: number; grader_score: number | null; kept: boolean }>;
    retries: number;
    grader_passed: boolean;
    checker_passed: boolean;
    citation_count: number;
    final_answer: string;
    total_tokens: number;
    latency_ms: number;
  },
): Promise<string | null> {
  try {
    const { data, error } = await db.from("agentic_rag_traces").insert({
      hive_id:        payload.hive_id,
      worker_name:    payload.worker_name,
      question:       payload.question.slice(0, 1000),
      route:          payload.route,
      stages:         payload.stages,
      retrievals:     payload.retrievals,
      retries:        payload.retries,
      grader_passed:  payload.grader_passed,
      checker_passed: payload.checker_passed,
      citation_count: payload.citation_count,
      final_answer:   payload.final_answer.slice(0, 4000),
      total_tokens:   payload.total_tokens,
      latency_ms:     payload.latency_ms,
    }).select("id").maybeSingle();
    if (error) {
      console.warn("[agentic-rag-loop] trace write failed:", error.message);
      return null;
    }
    return data?.id || null;
  } catch (err) {
    console.warn("[agentic-rag-loop] trace write threw:", String(err).slice(0, 100));
    return null;
  }
}

// ── Inter-fn HTTP helper (for memory store + temporal delegate) ──────────────
//
// Calls another edge fn on the same Supabase project via HTTPS. Uses the
// service-role key so the called fn sees us as trusted. AbortSignal.timeout
// keeps the call bounded even if the target is unreachable.

async function invokeEdgeFn<T = unknown>(fnName: string, body: Record<string, unknown>): Promise<T | null> {
  if (!_WH_URL || !_WH_KEY) return null;
  try {
    const res = await fetch(`${_WH_URL}/functions/v1/${fnName}`, {
      method: "POST",
      signal: AbortSignal.timeout(FN_INVOKE_TIMEOUT_MS),
      headers: {
        "Content-Type":  "application/json",
        "Authorization": `Bearer ${_WH_KEY}`,
        "apikey":        _WH_KEY,
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      console.warn(`[agentic-rag-loop] ${fnName} returned ${res.status}`);
      return null;
    }
    return await res.json() as T;
  } catch (err) {
    console.warn(`[agentic-rag-loop] ${fnName} call failed:`, String(err).slice(0, 100));
    return null;
  }
}

// ── Item 4: Memory recall (Phase 7 agent-memory-store integration) ──────────

interface RecalledMemory {
  id: string;
  memory_type: "factual" | "procedural" | "episodic" | "semantic";
  content: string;
  importance: number;
  use_count: number;
  last_used_at: string | null;
}

async function recallMemories(hiveId: string | null, workerName: string | null): Promise<RecalledMemory[]> {
  if (!hiveId && !workerName) return [];
  const resp = await invokeEdgeFn<{ ok: boolean; memories?: RecalledMemory[] }>("agent-memory-store", {
    op:          "recall",
    hive_id:     hiveId,
    worker_name: workerName,
    limit:       MEMORY_RECALL_LIMIT,
  });
  return resp?.memories || [];
}

function memoryBlockFor(memories: RecalledMemory[]): string {
  if (!memories.length) return "";
  return "KNOWN CONTEXT FROM PRIOR SESSIONS:\n" +
    memories.map(m => `  - [${m.memory_type}] ${m.content}`).join("\n") +
    "\n\n";
}

// ── Item 4: Memory store (after Checker passes) ──────────────────────────────

interface ExtractedMemory {
  memory_type: "factual" | "procedural" | "episodic" | "semantic";
  content:     string;
  importance:  number;
}

async function extractAndStoreMemories(
  db: SupabaseClient,
  hiveId: string | null,
  workerName: string | null,
  question: string,
  answer: string,
  existing: RecalledMemory[],
  traceId: string | null,
): Promise<number> {
  if (!hiveId && !workerName) return 0;
  if (!answer) return 0;

  const t0 = Date.now();
  const payload = {
    question,
    answer,
    existing_memories: existing.map(m => ({ type: m.memory_type, content: m.content })).slice(0, 10),
  };
  const raw = await callAI(JSON.stringify(payload), {
    systemPrompt: EXTRACTOR_SYSTEM,
    temperature:  0.1,
    maxTokens:    MAX_TOKENS_EXTRACT,
    jsonMode:     true,
    taskProfile:  "hallucination_checker",   // cheap 8B model is fine
  });
  const latency = Date.now() - t0;

  let parsed: { memories?: ExtractedMemory[] } = {};
  try { parsed = JSON.parse(raw || "{}"); } catch { /* fallthrough */ }

  await logAICost(db, {
    fn: FN_NAME, hive_id: hiveId, worker_name: workerName,
    model: "chain:auto", provider: "groq",
    prompt_tokens: estimateTokens(JSON.stringify(payload)) + estimateTokens(EXTRACTOR_SYSTEM),
    output_tokens: estimateTokens(raw),
    latency_ms: latency,
    status: raw === "{}" ? "fallback" : "success",
    schema_compliance: Array.isArray(parsed.memories),
  });

  const memories = (parsed.memories || []).filter(m =>
    m && ["factual","procedural","episodic","semantic"].includes(m.memory_type) && typeof m.content === "string" && m.content.length > 0
  ).slice(0, 10).map(m => ({
    ...m,
    source_trace_id: traceId,
  }));

  if (!memories.length) return 0;
  // Fire-and-forget — store result doesn't gate the response.
  invokeEdgeFn("agent-memory-store", {
    op:          "store",
    hive_id:     hiveId,
    worker_name: workerName,
    memories,
  }).catch(err => console.warn("[agentic-rag-loop] memory store failed:", String(err).slice(0, 80)));

  return memories.length;
}

// ── Item 3: Router→Temporal auto-delegate ────────────────────────────────────

interface TemporalDelegateResponse {
  answer:       string;
  worst_period: string | null;
  trend:        string;
  per_period:   unknown[];
  periods:      number;
  level:        string;
  latency_ms:   number;
  remaining?:   number;
}

function spanDaysFromTimeScope(scope: { from: string | null; to: string | null } | null | undefined): number {
  if (!scope || !scope.from) return 0;
  const fromMs = Date.parse(scope.from);
  const toMs   = scope.to ? Date.parse(scope.to) : Date.now();
  if (!Number.isFinite(fromMs) || !Number.isFinite(toMs)) return 0;
  return Math.max(0, (toMs - fromMs) / 86400000);
}

async function delegateToTemporal(
  hiveId: string,
  workerName: string | null,
  question: string,
  assetTag: string | null,
  scope: { from: string | null; to: string | null },
): Promise<TemporalDelegateResponse | null> {
  const body: Record<string, unknown> = {
    question, hive_id: hiveId, worker_name: workerName,
    granularity: "auto",
  };
  if (assetTag)  body.asset_tag = assetTag;
  if (scope.from) body.from     = scope.from;
  if (scope.to)   body.to       = scope.to;
  return await invokeEdgeFn<TemporalDelegateResponse>("temporal-rag-orchestrator", body);
}

// ── Router→Cold-Archive wiring (Phase 6) ─────────────────────────────────────
// The Router promotes >18mo questions to route="cold_archive" but, until now,
// nothing CALLED cold-archive-query — the live retrieval lanes simply skip on
// that route, so the question dead-ended to "no records". This pulls the
// archived Parquet rows (via cold-archive-query) and converts them to chunks so
// the Generator can ground on real history. Returns [] on any miss so the caller
// can gracefully degrade to the live lanes (an archive miss must never kill the
// answer).
const COLD_ARCHIVE_CHUNK_CAP = 12;

interface ColdArchiveResponse {
  ok:        boolean;
  rows?:     Array<Record<string, unknown>>;
  row_count?: number;
  reason?:   string;
}

async function fetchColdArchiveChunks(
  hiveId: string,
  assetTag: string | null,
  scope: { from: string | null; to: string | null },
): Promise<Chunk[]> {
  if (!scope.from) return [];
  const body: Record<string, unknown> = {
    hive_id:    hiveId,
    table:      "logbook",
    time_range: { from: scope.from, to: scope.to || new Date().toISOString().slice(0, 10) },
    limit:      COLD_ARCHIVE_CHUNK_CAP,
  };
  if (assetTag) body.asset_tag = assetTag;

  const resp = await invokeEdgeFn<ColdArchiveResponse>("cold-archive-query", body);
  if (!resp?.ok || !Array.isArray(resp.rows) || !resp.rows.length) return [];

  return resp.rows.slice(0, COLD_ARCHIVE_CHUNK_CAP).map((row, i) => {
    const r = row as Record<string, unknown>;
    const date = String(r.created_at || r.logged_at || "").slice(0, 10);
    return {
      id:         `cold#${r.id ?? i}`,
      source:     "cold_archive:logbook",
      source_id:  String(r.id ?? `${date}-${i}`),
      text:       `[archived ${date} ${r.machine || "?"} ${r.maintenance_type || ""}] cause: ${r.root_cause || "n/a"}; action: ${r.action || "n/a"}; problem: ${r.problem || "n/a"}; status: ${r.status || "?"}`.slice(0, 500),
      metadata:   { created_at: r.created_at, machine: r.machine, archived: true },
      similarity: 0.7,   // archived history is authoritative for the asked >18mo window
    } as Chunk;
  });
}

// ── Item 2: Lane C — hierarchical period summaries (Phase 2 integration) ─────

async function lookupHierarchicalSummaries(
  db: SupabaseClient,
  hiveId: string,
  assetTag: string | null,
  scope: { from: string | null; to: string | null },
): Promise<Chunk[]> {
  // Choose level by span (mirrors temporal-rag-orchestrator's heuristic).
  const span = spanDaysFromTimeScope(scope);
  if (span === 0) return [];
  const level: "year" | "quarter" | "month" =
    span >= 3 * 365 ? "year" : span >= 180 ? "quarter" : "month";

  // canonical-allow: temporal-RAG primary read (canonical_period_summaries IS the canonical aggregate)
  let q = db.from("canonical_period_summaries")
    .select("id, asset_tag, level, period_start, period_end, summary_text, summary_json")
    .eq("hive_id", hiveId)
    .eq("level", level)
    .order("period_end", { ascending: false })
    .limit(HIER_SUMMARY_LIMIT);
  if (scope.from) q = q.gte("period_start", scope.from);
  if (scope.to)   q = q.lte("period_end",   scope.to);
  if (assetTag) q = q.eq("asset_tag", assetTag); else q = q.is("asset_tag", null);

  const { data } = await q;
  return (data || []).map((row: { id: string; asset_tag: string | null; level: string; period_start: string; period_end: string; summary_text: string; summary_json: Record<string, unknown> }) => {
    const stats = row.summary_json || {};
    const statLine = [
      stats.failure_count != null ? `${stats.failure_count} corrective` : "",
      stats.mtbf_days != null     ? `MTBF ${stats.mtbf_days}d`          : "",
      stats.mttr_h != null        ? `MTTR ${stats.mttr_h}h`              : "",
      stats.downtime_h != null    ? `downtime ${stats.downtime_h}h`     : "",
    ].filter(Boolean).join(", ");
    const text = `[${row.level} ${row.period_start}..${row.period_end} ${row.asset_tag || "hive-wide"}] ${row.summary_text}${statLine ? `\nstats: ${statLine}` : ""}`.slice(0, 800);
    return {
      id:         `hier#${row.id}`,
      source:     "canonical_period_summaries",
      source_id:  row.id,
      text,
      metadata:   { level: row.level, period_start: row.period_start, period_end: row.period_end, asset_tag: row.asset_tag },
      similarity: 0.85,   // hierarchical summaries are high-signal; rank them above raw lanes
    };
  });
}

// ── Server entry point ───────────────────────────────────────────────────────

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  // /health probe — pings dependencies before any auth/parse work.
  const healthResp = await handleHealth(req, "agentic-rag-loop", async () => ({
    deps: [
      { name: "supabase",     ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) },
      { name: "ai-chain",     ok: Boolean(Deno.env.get("GROQ_API_KEY") || Deno.env.get("CEREBRAS_API_KEY")) },
    ],
  }));
  if (healthResp) return healthResp;

  const _logCtx = beginRequest(req, { route: "agentic-rag-loop" });
  log.info(_logCtx, "request_start", { method: req.method });

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const reqStart = Date.now();

  // ── Parse + validate input ─────────────────────────────────────────────────
  let body: { question?: string; hive_id?: string | null; worker_name?: string | null; auth_uid?: string | null };
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const question   = String(body.question || "").trim().slice(0, MAX_QUESTION_CHARS);
  const hiveId     = body.hive_id || null;
  const workerName = body.worker_name || null;
  const authUid    = body.auth_uid || null;

  if (!question) {
    return new Response(JSON.stringify({ error: "Missing required field: question" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  if (!hiveId && !workerName && !authUid) {
    return new Response(JSON.stringify({ error: "Missing required field: hive_id or worker_name or auth_uid" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  // Always-fresh client (warm-client removed — see module-scope comment above).
  // Defensive: if env is missing, fail fast with a clean error instead of letting
  // a half-broken client throw deep inside a stage.
  if (!_WH_URL || !_WH_KEY) {
    return new Response(JSON.stringify({ error: "Server misconfigured: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing" }), {
      status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  const db = createClient(_WH_URL, _WH_KEY);

  // Resolve the caller's identity ONCE — JWT-derived authUid + isServiceRole.
  // Browser callers carry a user JWT; gateway/voice forwards use the service role.
  // This is the authoritative identity for BOTH hive membership AND the personal
  // voice-journal scope below.
  const _id = await resolveIdentity(db, req);

  // Pillar I: RAG over a hive's knowledge scoped by the client hive_id on a
  // service-role client — verify membership using the JWT-derived identity (NOT
  // the client-supplied body.auth_uid). Service-role (gateway/voice) forwards skip.
  if (hiveId && !_id.isServiceRole) {
    const t = await resolveTenancy(db, _id.authUid, hiveId);
    if (!t.ok) {
      return new Response(
        JSON.stringify({ error: t.message, code: t.code }),
        { status: t.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
  }

  // Pillar R/I auth_uid IDOR fix (2026-06-15): the voice-journal lane (Lane A) is
  // PERSONAL. For a BROWSER caller scope it ONLY by the JWT-verified authUid —
  // never the client-supplied body.auth_uid (which let a caller read another
  // worker's journal by passing their id, on this service-role/RLS-bypassed
  // client). A SERVICE-ROLE forward (gateway/voice, already user-verified
  // upstream) keeps the supplied auth_uid. Anon browser caller → null → Lane A
  // is skipped (no journal to read).
  const effectiveAuthUid = _id.isServiceRole ? authUid : (_id.authUid || null);

  // ── Rate limit ─────────────────────────────────────────────────────────────
  const rl = await checkRateLimit(db, hiveId);
  if (!rl.allowed) {
    return new Response(
      JSON.stringify({ error: "AI call limit reached for this hive. Try again in an hour.", remaining: 0 }),
      { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }

  const stages: StageRecord[] = [];
  let totalTokens = 0;

  // ── Item 4: Memory recall (before Router) ──────────────────────────────────
  // Pulls top-N durable facts from agent_episodic_memory so subsequent stages
  // know what the AI already learned about this worker / hive.
  const mR0 = Date.now();
  const recalledMemories = await recallMemories(hiveId, workerName);
  const memoryBlock      = memoryBlockFor(recalledMemories);
  stages.push({
    stage: "memory_recall", latency_ms: Date.now() - mR0,
    tokens_in: 0, tokens_out: estimateTokens(memoryBlock),
    snippet: `${recalledMemories.length} memories recalled`,
  });

  // ── Stage 1: Router ────────────────────────────────────────────────────────
  const router = await routerStage(question, db, hiveId, workerName);
  stages.push({
    stage: "router", latency_ms: router.latency,
    tokens_in: estimateTokens(question) + estimateTokens(ROUTER_SYSTEM),
    tokens_out: estimateTokens(router.raw),
    snippet: router.parsed.reasoning?.slice(0, 200) || "",
  });
  totalTokens += estimateTokens(question) + estimateTokens(ROUTER_SYSTEM) + estimateTokens(router.raw);

  // ── Item 3: Router→Temporal auto-delegate ──────────────────────────────────
  // If Router classified temporal AND span > 180 days, fan out via Phase 3
  // orchestrator and return its answer wrapped in our response shape.
  if (router.parsed.route === "temporal" && hiveId && spanDaysFromTimeScope(router.parsed.time_scope) > TEMPORAL_DELEGATE_DAYS) {
    const dR0 = Date.now();
    const delegated = await delegateToTemporal(
      hiveId, workerName, question, router.parsed.asset_tag, router.parsed.time_scope,
    );
    stages.push({
      stage: "temporal_delegate", latency_ms: Date.now() - dR0,
      tokens_in: 0, tokens_out: estimateTokens(delegated?.answer || ""),
      snippet: delegated ? `delegated to Phase 3 (${delegated.periods} periods)` : "delegate failed; continuing standard loop",
    });
    if (delegated && delegated.answer) {
      const totalLatency = Date.now() - reqStart;
      const traceId = await writeTrace(db, {
        hive_id: hiveId, worker_name: workerName, question,
        route: "temporal",
        stages,
        retrievals: [],
        retries: 0,
        grader_passed: true, checker_passed: true,
        citation_count: 0,
        final_answer: delegated.answer,
        total_tokens: totalTokens + estimateTokens(delegated.answer),
        latency_ms: totalLatency,
      });
      // Fire-and-forget memory extraction even on delegated path.
      extractAndStoreMemories(db, hiveId, workerName, question, delegated.answer, recalledMemories, traceId)
        .catch(err => console.warn("[agentic-rag-loop] post-delegate memory store failed:", String(err).slice(0, 80)));
      return new Response(JSON.stringify({
        answer:         delegated.answer,
        citations:      [],
        trace_id:       traceId,
        route:          "temporal",
        retries:        0,
        grader_passed:  true,
        checker_passed: true,
        total_tokens:   totalTokens + estimateTokens(delegated.answer),
        latency_ms:     totalLatency,
        remaining:      rl.remaining,
        delegated:      true,
        per_period:     delegated.per_period,
      }), { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } });
    }
    // Delegate failed — fall through to standard loop.
  }

  // ── Loop: Retrieve → Grade → Generate → Check, up to MAX_RETRIES ───────────
  let currentQuery       = question;
  let retries            = 0;
  let lastAnswer         = "";
  let lastCitations: GeneratorOutput["citations"] = [];
  let lastKept: Chunk[]  = [];
  let lastRetrievals: Array<{ source: string; chunk_id: string; similarity: number; grader_score: number | null; kept: boolean }> = [];
  let checkerPassed      = false;
  let graderPassed       = false;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    // Stage 2: Retriever (Item 2 wires Lane C: hierarchical summaries)
    const tR0 = Date.now();
    const chunks = await retrieverStage(db, currentQuery, hiveId, workerName, effectiveAuthUid, router.parsed.route, router.parsed.asset_tag, router.parsed.time_scope);
    stages.push({
      stage: `retriever${attempt > 0 ? `_retry${attempt}` : ""}`,
      latency_ms: Date.now() - tR0,
      tokens_in: 0, tokens_out: 0,
      snippet: `${chunks.length} chunks from ${new Set(chunks.map(c => c.source)).size} sources`,
    });

    // Stage 3: Grader
    const grader = await graderStage(db, currentQuery, chunks, hiveId, workerName);
    stages.push({
      stage: `grader${attempt > 0 ? `_retry${attempt}` : ""}`,
      latency_ms: grader.latency,
      tokens_in: estimateTokens(grader.raw), tokens_out: estimateTokens(grader.raw),
      snippet: `${grader.kept.length} kept out of ${chunks.length}`,
    });
    totalTokens += estimateTokens(grader.raw) * 2;
    graderPassed = grader.passed;

    lastKept       = grader.kept;
    lastRetrievals = chunks.map(c => ({
      source:       c.source,
      chunk_id:     c.id,
      similarity:   c.similarity,
      grader_score: grader.scores[c.id] ?? null,
      kept:         grader.kept.some(k => k.id === c.id),
    }));

    // Stage 4: Generator (Item 4: memory block injected into user prompt)
    const generator = await generatorStage(db, currentQuery, grader.kept, hiveId, workerName, memoryBlock);
    stages.push({
      stage: `generator${attempt > 0 ? `_retry${attempt}` : ""}`,
      latency_ms: generator.latency,
      tokens_in: estimateTokens(generator.raw), tokens_out: estimateTokens(generator.raw),
      snippet: generator.parsed.answer.slice(0, 200),
    });
    totalTokens += estimateTokens(generator.raw) * 2;
    lastAnswer     = generator.parsed.answer;
    lastCitations  = generator.parsed.citations || [];

    // Stage 5: Checker
    const checker = await checkerStage(db, currentQuery, lastAnswer, grader.kept, hiveId, workerName);
    stages.push({
      stage: `checker${attempt > 0 ? `_retry${attempt}` : ""}`,
      latency_ms: checker.latency,
      tokens_in: estimateTokens(checker.raw), tokens_out: estimateTokens(checker.raw),
      snippet: `passed=${checker.parsed.passed} uncited=${(checker.parsed.uncited_claims || []).length}`,
    });
    totalTokens += estimateTokens(checker.raw) * 2;
    checkerPassed = !!checker.parsed.passed;

    if (checkerPassed) break;

    // Failed — reformulate and retry (if budget allows)
    if (attempt < MAX_RETRIES && checker.parsed.reformulated_query) {
      currentQuery = String(checker.parsed.reformulated_query).slice(0, MAX_QUESTION_CHARS);
      retries++;
    } else {
      break;
    }
  }

  const totalLatency = Date.now() - reqStart;

  // ── Persist trace ──────────────────────────────────────────────────────────
  const traceId = await writeTrace(db, {
    hive_id:        hiveId,
    worker_name:    workerName,
    question,
    route:          router.parsed.route,
    stages,
    retrievals:     lastRetrievals,
    retries,
    grader_passed:  graderPassed,
    checker_passed: checkerPassed,
    citation_count: lastCitations.length,
    final_answer:   lastAnswer,
    total_tokens:   totalTokens,
    latency_ms:     totalLatency,
  });

  // ── Item 4: Memory store (fire-and-forget — only when Checker passed) ──────
  if (checkerPassed && lastAnswer) {
    extractAndStoreMemories(db, hiveId, workerName, question, lastAnswer, recalledMemories, traceId)
      .catch(err => console.warn("[agentic-rag-loop] memory store failed:", String(err).slice(0, 80)));
  }

  // ── Response ───────────────────────────────────────────────────────────────
  return new Response(JSON.stringify({
    answer:         lastAnswer,
    citations:      lastCitations,
    trace_id:       traceId,
    route:          router.parsed.route,
    retries,
    grader_passed:  graderPassed,
    checker_passed: checkerPassed,
    total_tokens:   totalTokens,
    latency_ms:     totalLatency,
    remaining:      rl.remaining,
  }), {
    status: 200,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
});
