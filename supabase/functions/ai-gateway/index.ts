/**
// capability: ai_question_answer
 * ai-gateway -- single-entry-point AI routing layer.
 *
 * The frontend invokes this fn with `{ agent, message, context? }`. The
 * gateway:
 *   1. Validates the agent_id against the AGENT_ROUTES registry.
 *   2. Applies the rate-limit gate ONCE (vs every orchestrator gating
 *      independently with drift risk).
 *   3. Loads the worker's memory for that agent (last 10 turns + latest
 *      summary).
 *   4. Redacts PII from the message + context before forwarding.
 *   5. Forwards to the appropriate specialist agent (asset-brain-query,
 *      analytics-orchestrator, etc.) over a function-to-function invoke.
 *   6. Hydrates the response (substitutes PII placeholders back).
 *   7. Persists the (user, agent) turn pair to agent_memory.
 *   8. Returns a uniform `{ answer, agent, memory_id, usage }` envelope.
 *
 * Closes PRODUCTION_FIXES #44 by centralising the redactPII call here.
 *
 * Skills consulted before writing: ai-engineer (callAI / multi-provider
 * chain semantics), security (PII boundary, auth.uid binding), realtime-
 * engineer (gateway + memory layer is event-source for future timeline
 * UI), architect (single-entry-point pattern, orchestrator decoupling),
 * notifications (gateway is also the natural place to fan-out push
 * notifications when an agent identifies an action item).
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

// contract-allow: router; forwards to specialist orchestrators
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import sourceRegistry from "../_shared/companion_source_registry.json" with { type: "json" };
import {
  checkAIRateLimit,
  checkUserRateLimit,
  rateLimitedResponse,
  userRateLimitedResponse,
} from "../_shared/rate-limit.ts";
import { redactPIIWithMap, hydratePII } from "../_shared/redactPII.ts";
import {
  loadMemory,
  saveTurn,
  summariseIfNeeded,
  formatMemoryContext,
  type MemoryHandle,
} from "../_shared/memory.ts";
import { callAI } from "../_shared/ai-chain.ts";
import { generateEmbedding } from "../_shared/embedding-chain.ts";
import {
  loadJournalRecall,
  persistJournalEntry,
} from "../_shared/journal-recall.ts";
// 2026-05-30 memory-stack flywheel Turn 1 (layer 02 Episodic): durable
// long-term memory for the non-journal conversational specialists. Recalled
// before forward, persisted from the specialist's envelope after.
import {
  recallEpisodic,
  persistEpisodic,
  formatEpisodicContext,
  type StoreInput,
} from "../_shared/episodic-memory.ts";
// 2026-05-30 memory-stack flywheel Turn 2 (layer 07 Shared Memory): inject the
// conflict-resolved verified state of an asset so every agent reads one truth.
import {
  resolveAssetState,
  formatVerifiedState,
} from "../_shared/verified-state.ts";
// 2026-05-31 memory-stack flywheel Turn 5 (layer 04 Procedural): semantically
// match the current problem against the hive's distilled skill library (proven
// fix procedures in agent_episodic_memory) and inject the best matches.
import {
  matchProcedures,
  formatProcedures,
} from "../_shared/skill-library.ts";
import {
  loadPersonaKnowledge,
  formatPersonaKnowledge,
} from "../_shared/persona-knowledge.ts";
// 2026-05-31 memory-stack flywheel Turn 6 (layer 06 Prospective): per-(hive,
// worker) deferred follow-up queue. Specialists emit followups[] to defer an
// intention; the gateway enqueues them and surfaces due ones on a later turn.
import {
  enqueueFollowups,
  recallDueFollowups,
  formatFollowups,
  type RawFollowup,
} from "../_shared/followups.ts";

// P1 roadmap 2026-05-26: adoption of shared envelope + health + structured log.
// First fn to migrate (highest traffic, sets the pattern for the other 54).
import { beginRequest, ok, recordModelHop } from "../_shared/envelope.ts";
import { handleHealth } from "../_shared/health.ts";
import { log } from "../_shared/logger.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";

// Agents that get semantic-recall enrichment in addition to short-term
// agent_memory. Adding an agent here makes the gateway:
//   1. Embed the user's message and pull top-K similar past journal entries
//      from voice_journal_entries.
//   2. Append that recall block to the memory_block forwarded to the specialist.
//   3. Persist the completed exchange (transcript + reply + lang + embedding)
//      into voice_journal_entries for future recall.
// Only voice-journal currently uses this surface; other agents have their
// own RAG layers (asset-brain has GraphRAG, analytics has its own pipeline).
const SEMANTIC_RECALL_AGENTS: Set<string> = new Set(["voice-journal"]);

// Agents that get DURABLE episodic-memory enrichment (layer 02 of the AI Agent
// Memory Stack) on top of short-term agent_memory. For these specialists the
// gateway:
//   1. Recalls the worker's/hive's top durable memories (factual/procedural/
//      episodic/semantic) from agent_episodic_memory and appends them to the
//      forwarded memory_block.
//   2. After the specialist responds, persists any memories it emitted in its
//      envelope (`memories: [{memory_type, content, importance?}]`) so the
//      store grows from real exchanges. Persisting is LLM-free here — the
//      specialist (or agentic-rag-loop's Checker) decides what is durable.
// voice-journal is deliberately EXCLUDED — it already has its own per-user
// semantic store (voice_journal_entries via journal-recall.ts); double-storing
// would duplicate the journal into the shared agent memory bank.
const EPISODIC_MEMORY_AGENTS: Set<string> = new Set([
  "asset-brain", "analytics", "shift", "project", "assistant",
]);
// How many durable memories to inject per turn. Small — these ride alongside
// the 10-turn working memory and the budget is shared.
const EPISODIC_RECALL_LIMIT = 6;

// Agents that get VERIFIED-STATE enrichment (layer 07 Shared Memory) when the
// turn is about a specific asset. The gateway resolves the asset's current
// conflict-resolved state from v_asset_state_truth and injects it so the agent
// answers from the one shared truth rather than a stale or competing event.
// Asset-centric specialists only; injection is also gated on an asset_tag being
// present in context (no asset = nothing to resolve).
const VERIFIED_STATE_AGENTS: Set<string> = new Set([
  "asset-brain", "shift",
]);

// Agents whose downstream specialist REQUIRES a resolved asset_id (UUID), not the
// human asset_tag. The documented surface contract grounds an asset by
// `context.asset_tag` (same field verified-state resolves on), but
// asset-brain-query 400s "Missing required fields: asset_id" when it gets only a
// tag. The gateway resolves tag -> id (hive-scoped) before forwarding so the
// asset_tag contract is complete end-to-end (W1 wiring fix 2026-06-12). Only
// asset-brain needs this today; shift-planner reads asset context differently.
const ASSET_ID_FORWARD_AGENTS: Set<string> = new Set([
  "asset-brain",
]);

// W3 structural-echo (LOCAL-ONLY, opt-in). When WH_ALLOW_DEBUG_ECHO=1 (set only in
// the local functions/.env, NEVER in prod) AND the caller is authed AND sends
// context.debug_echo_memory_block=true, the gateway returns the fully-assembled
// memory_block + which layer sections fired, WITHOUT calling the LLM — so the
// wiring battery can deterministically assert J1 (PII redacted in the forwarded
// prompt) / K3 (episodic) / K5 (procedural) / K8 (verified-state) per agent. Triple-
// gated (env + auth + explicit flag); a static validator guards it can't leak to prod.
// LOCAL detection: the edge runtime's SUPABASE_URL is the internal docker host
// (http://kong:8000 / localhost / 127.0.0.1) locally but the public https://*.supabase.co
// URL in prod — a reliable fail-closed local signal (this setup's edge runtime does NOT
// read functions/.env, so an env-only gate can't be turned on locally). The env var is
// an optional explicit override for env-injected deployments.
const _GW_SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const _IS_LOCAL_SUPABASE = /\/\/(kong|localhost|127\.0\.0\.1)(:|\/|$)/.test(_GW_SUPABASE_URL);
const DEBUG_ECHO_ENABLED = Deno.env.get("WH_ALLOW_DEBUG_ECHO") === "1" || _IS_LOCAL_SUPABASE;

// Agents that get PROCEDURAL skill-library matching (layer 04). For a fix-
// oriented turn the gateway embeds the user's message and pulls the top
// semantically-matched proven procedures (match_procedural_memories over the
// hive's distilled procedural memories) and injects them so the agent reuses a
// known-good fix instead of reasoning one from scratch. Embedding-backed, so
// gated to the agents whose turns are about doing/fixing. Best-effort.
const PROCEDURAL_SKILL_AGENTS: Set<string> = new Set([
  "asset-brain", "shift",
]);
const PROCEDURE_RECALL_LIMIT = 4;

// Agents that get PERSONA-KNOWLEDGE enrichment (layer 08, L08). THE gap O11 closes:
// the curated DOMAIN corpus (SKILL.md + standards) served specialists but NEVER the
// floating launcher where the personas live. voice-journal IS the launcher agent, so
// wiring it here makes DOMAIN_LENS real on the conversational surface. Persona scope
// (Hezekiah technical / Zaniah strategic) is resolved per-turn inside loadPersonaKnowledge.
const PERSONA_KNOWLEDGE_AGENTS: Set<string> = new Set([
  "voice-journal", "assistant",
]);

// Agents that get a LIVE OPERATIONS SNAPSHOT (2026-06-13 fabrication fix). The
// conversational launcher (voice-journal) has the persona BRAIN but had NO live
// hive operational data, so it leaned on fuzzy conversational memory and either
// confabulated assets/metrics (invented "P-203", "78% OEE", "PM compliance <70%")
// or deflected real operational questions ("check the Work Assistant") even though
// v_alert_truth / asset_nodes / the PM truth view hold the answers. Injecting a
// compact, verified, hive-scoped snapshot (active-alert count + top alerts, overdue
// PM count, the real registered asset-tag list) grounds "open jobs / how many alerts
// / which assets" in TRUTH and gives the agent the data to reject asset tags that are
// not registered. Best-effort + token-capped; a DB miss simply omits the block.
const OPS_SNAPSHOT_AGENTS: Set<string> = new Set(["voice-journal"]);

// KPI facts for the companion (Grounding/Capability roadmap — Pillar S, Phase S1, 2026-06-14).
// Reads the SAME canonical computed sources the analytics / asset surfaces read so the
// companion SERVES real reliability + OEE figures instead of deflecting ("you don't have that
// on this surface" was a WIRING gap, not honesty — the platform already computes these):
//   - v_kpi_truth: materialized MTBF/MTTR/downtime per machine (30/90/365d, hourly refresh)
//   - analytics_snapshots (descriptive phase): per-asset OEE (ISO 22400 partial A×Q)
// Hive-scoped, best-effort, token-capped. CODE does the aggregation (WAT: deterministic math,
// never the LLM authors a number). Returns "" if nothing is computed yet (honest fallback).
// ── CUSTOM engine handlers (Pillar S, Phase 2) ───────────────────────────────────────────────
// For the few sources whose shape isn't a flat declarative aggregate — nested JSON (OEE), derived
// ratio (PM compliance %), latest-per-group dedup (projects). Registered in the source registry as
// engine:{kind:"custom", handler:"<name>"} and dispatched by buildFromRegistry. Everything else
// (inventory/reliability/skills/risk) is now a pure declarative `engine` spec — register, don't wire.
async function buildOeeFacts(client: SupabaseClient, hiveId: string): Promise<string> {
  try {
    const { data } = await client.from("analytics_snapshots")
      .select("payload,period_days").eq("hive_id", hiveId)
      .eq("phase", "descriptive").order("computed_at", { ascending: false }).limit(1);
    // deno-lint-ignore no-explicit-any
    const row = (data?.[0] as any);
    const arr = row?.payload?.oee?.oee_by_asset as Array<{ oee_pct?: number }> | undefined;
    const oees = (arr ?? []).map((a) => Number(a?.oee_pct)).filter((n) => Number.isFinite(n) && n > 0);
    if (!oees.length) return "";
    const avg = oees.reduce((s, x) => s + x, 0) / oees.length;
    return `OEE (partial — ISO 22400 Availability×Quality, ${row?.period_days ?? 90}d): hive average ~${avg.toFixed(0)}% across ${oees.length} assets (range ${Math.min(...oees).toFixed(0)}–${Math.max(...oees).toFixed(0)}%). Performance dimension excluded until a planned production rate is configured.`;
  } catch (_) { return ""; }
}

async function buildPmComplianceFacts(client: SupabaseClient, hiveId: string): Promise<string> {
  try {
    const { data } = await client.from("v_pm_compliance_truth")
      .select("asset_name,tag_id,is_due,days_since_last_completion").eq("hive_id", hiveId);
    // deno-lint-ignore no-explicit-any
    const rows = (data ?? []) as Array<any>;
    if (!rows.length) return "";
    const due = rows.filter((r) => r.is_due).length;
    const pct = Math.round(((rows.length - due) / rows.length) * 100);
    const worst = rows.filter((r) => r.is_due)
      .sort((a, b) => Number(b.days_since_last_completion ?? 0) - Number(a.days_since_last_completion ?? 0))
      .slice(0, 3).map((r) => `${r.tag_id || r.asset_name} (${r.days_since_last_completion ?? "?"}d since last)`);
    return `PM compliance (from v_pm_compliance_truth): ${pct}% up to date (${rows.length - due} of ${rows.length} PM assets), ${due} due now.${worst.length ? ` Longest waiting: ${worst.join("; ")}.` : ""}`;
  } catch (_) { return ""; }
}

async function buildProjectFacts(client: SupabaseClient, hiveId: string): Promise<string> {
  try {
    const { data } = await client.from("v_project_progress_truth")
      .select("project_id,project_name,project_code,project_status,pct_complete,has_blocker,log_date")
      .eq("hive_id", hiveId).order("log_date", { ascending: false });
    // deno-lint-ignore no-explicit-any
    const rows = (data ?? []) as Array<any>;
    if (!rows.length) return "";
    // deno-lint-ignore no-explicit-any
    const latest = new Map<string, any>();           // project_id -> latest log
    for (const r of rows) if (!latest.has(r.project_id)) latest.set(r.project_id, r);
    const projs = Array.from(latest.values());
    const blocked = projs.filter((p) => p.has_blocker).length;
    const list = projs.slice(0, 4).map((p) =>
      `${p.project_name || p.project_code} — ${p.pct_complete}% complete${p.has_blocker ? " (blocked)" : ""}`);
    return `Projects (from v_project_progress_truth): ${projs.length} active${blocked ? `, ${blocked} blocked` : ""}: ${list.join("; ")}.`;
  } catch (_) { return ""; }
}

// ── THE GATEWAY ENGINE (Pillar S, Phase 1 — "register, don't wire", 2026-06-14) ──────────────
// One generic fetch+aggregate+render driven by a registry entry's declarative `engine` spec, so a
// new served source is a JSON entry in companion_source_registry.json (the SAME file the coverage
// validator + the grader read), NOT a hand-coded buildXFacts. Hive-scoped, best-effort, "" if empty.
// Aggregation vocabulary: count · count_where{any:[flags]} · avg_of{field} · list_where · top_n_by.
// deno-lint-ignore-file no-explicit-any
const REGISTRY_BY_SOURCE: Record<string, any> = Object.fromEntries(
  (((sourceRegistry as any).sources) || []).map((e: any) => [e.source, e]),
);
function _truthy(v: unknown): boolean { return v === true || v === 1 || v === "true"; }
// {slot} interpolation, with optional rounding {slot:N} -> Number(v).toFixed(N).
function _fillSlots(tpl: string, src: Record<string, unknown>): string {
  return tpl.replace(/\{(\w+)(?::(\d+))?\}/g, (_m, k, dec) => {
    const v = src[k];
    if (v === null || v === undefined) return "";
    if (dec !== undefined && Number.isFinite(Number(v))) return Number(v).toFixed(Number(dec));
    return String(v);
  }).replace(/\s+/g, " ").trim();
}
// CUSTOM handlers for non-flat shapes (registered as engine:{kind:"custom",handler}).
const HANDLERS: Record<string, (c: SupabaseClient, h: string) => Promise<string>> = {
  buildOeeFacts, buildPmComplianceFacts, buildProjectFacts,
};
async function buildFromRegistry(client: SupabaseClient, hiveId: string, entry: any): Promise<string> {
  const spec = entry?.engine;
  if (!spec) return "";
  if (spec.kind === "custom") { const fn = HANDLERS[spec.handler]; return fn ? await fn(client, hiveId) : ""; }
  try {
    let q = client.from(entry.source).select(spec.select).eq("hive_id", hiveId);
    if (spec.order) q = q.order(spec.order.field, { ascending: spec.order.dir === "asc" });
    if (spec.limit) q = q.limit(spec.limit);
    const { data } = await q;
    const rows = (data ?? []) as Array<Record<string, unknown>>;
    if (!rows.length) return "";
    const anyFlag = (r: Record<string, unknown>, flags: string[]) => (flags || []).some((f) => _truthy(r[f]));
    const slots: Record<string, string> = {};
    for (const agg of (spec.aggregate || [])) {
      if (agg.kind === "count") {
        slots[agg.as] = String(rows.length);
      } else if (agg.kind === "count_where") {
        const pred = agg.gte
          ? (r: Record<string, unknown>) => Number(r[agg.gte[0]]) >= Number(agg.gte[1])
          : (r: Record<string, unknown>) => anyFlag(r, agg.any);
        slots[agg.as] = String(rows.filter(pred).length);
      } else if (agg.kind === "count_distinct") {
        slots[agg.as] = String(new Set(rows.map((r) => r[agg.field]).filter(Boolean)).size);
      } else if (agg.kind === "distinct_list") {
        slots[agg.as] = Array.from(new Set(rows.map((r) => r[agg.field]).filter(Boolean)))
          .slice(0, agg.limit ?? 6).join(agg.join ?? ", ");
      } else if (agg.kind === "avg_of") {
        const ns = rows.map((r) => Number(r[agg.field])).filter((n) => Number.isFinite(n) && n > 0);
        slots[agg.as] = ns.length ? (ns.reduce((s, x) => s + x, 0) / ns.length).toFixed(agg.decimals ?? 1) : "—";
      } else if (agg.kind === "list_where") {
        slots[agg.as] = rows.filter((r) => anyFlag(r, agg.any)).slice(0, agg.limit ?? 5)
          .map((r) => _fillSlots(agg.item, r)).join(agg.join ?? "; ");
      } else if (agg.kind === "top_n_by") {
        const dir = agg.dir === "asc" ? 1 : -1;
        slots[agg.as] = rows.filter((r) => Number.isFinite(Number(r[agg.field])))
          .sort((a, b) => dir * (Number(a[agg.field]) - Number(b[agg.field]))).slice(0, agg.n ?? 3)
          .map((r) => _fillSlots(agg.item, r)).join(agg.join ?? "; ");
      } else if (agg.kind === "take") {   // first N rows as-fetched (use with spec.order for "most recent N")
        slots[agg.as] = rows.slice(0, agg.n ?? 3).map((r) => _fillSlots(agg.item, r)).join(agg.join ?? "; ");
      }
    }
    return _fillSlots(spec.render, slots);
  } catch (_) { return ""; }
}

// ── PROACTIVITY (Pillar P, 2026-06-14) — the copilot→agent shift ─────────────────────────
// When the worker OPENS the companion with a greeting or an open-ended "what should I look at?"
// (no specific question to answer), surface the most urgent operational facts UNPROMPTED, ranked,
// each with an offer to act. Deterministic: the ranking is CODE and every number is read from the
// same canonical truth views (WAT — the LLM only phrases, never authors a number). Returns "" when
// nothing is urgent (proactivity must be SILENT when all is well — no manufactured urgency).
const _PROACTIVE_OPENERS = [
  "good morning", "good afternoon", "good evening", "magandang", "kumusta", "kamusta",
  "what's up", "whats up", "what should i", "where do i start", "where should i start",
  "anything i should know", "anything urgent", "what's urgent", "whats urgent",
  "brief me", "briefing", "catch me up", "what needs attention", "what needs my attention",
  "how are things", "how's the plant", "hows the plant", "status update", "daily brief",
  "what do i need to", "start my day", "start my shift", "anything for me", "anything new",
];
function isProactiveOpener(msg: string): boolean {
  const m = (msg || "").trim().toLowerCase();
  if (!m) return true;                                                 // bare "open companion" → brief
  if (m.length <= 14 && /^(hi|hey|hello|yo|oy|uy|hoy|sup)\b/.test(m)) return true;  // bare greeting
  return _PROACTIVE_OPENERS.some((k) => m.includes(k));
}
async function buildProactiveBriefing(client: SupabaseClient, hiveId: string): Promise<string> {
  const items: string[] = [];
  try {
    const [alertsRes, pmRes, invRes, riskRes, taskRes] = await Promise.all([
      client.from("v_alert_truth").select("severity").eq("hive_id", hiveId).eq("status", "active"),
      client.from("v_pm_scope_items_truth").select("*", { count: "exact", head: true }).eq("hive_id", hiveId).eq("is_overdue", true),
      client.from("v_inventory_items_truth").select("part_name,is_out_of_stock,is_low_stock,is_critical_low").eq("hive_id", hiveId),
      client.from("v_risk_truth").select("asset_name,risk_level,risk_score,days_until_failure").eq("hive_id", hiveId),
      client.from("v_project_items_truth").select("title,is_blocked").eq("hive_id", hiveId).eq("is_blocked", true),
    ]);
    // 1) active alerts — critical first, else high (the most time-sensitive signal).
    const sev = ((alertsRes.data ?? []) as Array<{ severity?: string }>).map((a) => String(a.severity || "").toLowerCase());
    const crit = sev.filter((s) => s === "critical").length;
    const high = sev.filter((s) => s === "high").length;
    if (crit) items.push(`${crit} CRITICAL alert${crit > 1 ? "s" : ""} active — offer to pull the details and help log a response.`);
    else if (high) items.push(`${high} high-severity alert${high > 1 ? "s" : ""} active — offer to review them.`);
    // 2) overdue PM.
    const overdue = pmRes.count ?? 0;
    if (overdue) items.push(`${overdue} PM task${overdue > 1 ? "s" : ""} overdue — offer to help prioritise and schedule them.`);
    // 3) stock-outs, else low stock.
    const inv = (invRes.data ?? []) as Array<{ part_name?: string; is_out_of_stock?: boolean; is_low_stock?: boolean; is_critical_low?: boolean }>;
    const out = inv.filter((p) => p.is_out_of_stock);
    const low = inv.filter((p) => (p.is_low_stock || p.is_critical_low) && !p.is_out_of_stock);
    if (out.length) items.push(`${out.length} part${out.length > 1 ? "s" : ""} OUT of stock (${out.slice(0, 2).map((p) => p.part_name).filter(Boolean).join(", ")}) — offer to flag a reorder.`);
    else if (low.length) items.push(`${low.length} part${low.length > 1 ? "s" : ""} below reorder point — offer to review stock levels.`);
    // 4) top at-risk asset (ML-scored).
    const risk = ((riskRes.data ?? []) as Array<{ asset_name?: string; risk_level?: string; risk_score?: number; days_until_failure?: number }>)
      .filter((r) => ["critical", "high"].includes(String(r.risk_level || "").toLowerCase()))
      .sort((a, b) => Number(b.risk_score ?? 0) - Number(a.risk_score ?? 0));
    if (risk.length) {
      const r = risk[0];
      items.push(`${r.asset_name} is ${String(r.risk_level).toLowerCase()}-risk (~${Math.round(Number(r.days_until_failure ?? 0))} days to likely failure) — offer to plan a preventive check.`);
    }
    // 5) blocked project tasks.
    const blocked = (taskRes.data ?? []) as Array<{ title?: string }>;
    if (blocked.length) items.push(`${blocked.length} project task${blocked.length > 1 ? "s" : ""} blocked (${blocked.slice(0, 1).map((t) => t.title).filter(Boolean).join("")}…) — offer to help unblock.`);
  } catch (_) { return ""; }
  if (!items.length) return "";
  const ranked = items.slice(0, 5).map((s, i) => `${i + 1}. ${s}`).join("\n");
  return [
    "=== PROACTIVE ATTENTION (the worker opened with no specific question — OPEN your reply by surfacing these UNPROMPTED, most-urgent first, and offer to act on them) ===",
    ranked,
    "(These are the live priorities, ranked. Lead with them warmly and briefly; do NOT invent any item not listed here. If a worker asks something specific instead, answer that first then add the top 1–2.)",
  ].join("\n");
}

// ── CROSS-MODAL RAG (Pillar K, 2026-06-14) — structured snapshot + UNSTRUCTURED knowledge ──
// The snapshot answers "what's my MTBF / how many alerts" (structured truth views). Pillar K adds
// "how do I fix this / what have we seen before" by retrieving from the hive's own SOPs + fault
// history + PM notes (v_knowledge_truth → fault_knowledge/skill_knowledge/pm_knowledge, embedded).
// Same vector space as the query (generateEmbedding → the configured embedding chain; locally the
// self-hosted bge server). Best-effort: if embeddings are down or nothing is relevant, returns ""
// and the companion answers from its general knowledge as before (RAG is an ENHANCEMENT, never the
// critical path — mirrors the semantic-search/embedding-chain doctrine). Cited, never invented.
const _KNOWLEDGE_CUES = [
  "how do i", "how do you", "how to", "how can i", "how should i", "what's the procedure",
  "whats the procedure", "procedure for", "procedure to", "steps to", "steps for", "sop",
  "best way to", "what causes", "why does", "why is", "why did", "troubleshoot", "diagnose",
  "how do we fix", "how to fix", "how to repair", "what should i do", "recommend", "guidance",
  "lessons learned", "have we seen", "has this happened", "seen this before", "past failures",
  "history of", "what do i do about", "deal with", "resolve the", "root cause of",
];
function isKnowledgeQuestion(msg: string): boolean {
  const m = (msg || "").toLowerCase();
  return _KNOWLEDGE_CUES.some((k) => m.includes(k));
}
async function buildKnowledgeContext(client: SupabaseClient, hiveId: string, message: string): Promise<string> {
  try {
    let embedding: number[];
    try {
      // Pin the SAME model the knowledge corpus is embedded with — locally the self-hosted bge
      // server (BGE_EMBED_URL). Query + corpus MUST share one vector space or cosine is noise
      // (embedding-chain doctrine: re-embed a corpus AND flip its pin together). Failover still
      // applies on outage, but a non-bge answer is logged loudly and simply won't match → "".
      embedding = await generateEmbedding(message, "bge-local");
    } catch (_) {
      return "";   // embedding chain unavailable → degrade silently (no RAG context this turn)
    }
    if (!Array.isArray(embedding) || !embedding.length) return "";
    const { data, error } = await client.rpc("search_all_knowledge", {
      query_embedding: embedding, match_hive_id: hiveId, match_count: 4,
    });
    if (error) return "";
    const rows = ((data ?? []) as Array<{ source?: string; summary?: string; similarity?: number }>)
      .filter((r) => r.summary && Number(r.similarity ?? 0) >= 0.25)   // floor out vector noise
      .slice(0, 4);
    if (!rows.length) return "";
    const items = rows.map((r) => `• [${r.source || "kb"}] ${String(r.summary).slice(0, 220)}`).join("\n");
    return [
      "=== KNOWLEDGE BASE (retrieved from THIS hive's own SOPs / fault history / PM notes — ground your how-to answer in these and cite them; do NOT invent a procedure that isn't here) ===",
      items,
      "(If these don't cover the question, say what the records show and suggest who/where to check — never fabricate a step.)",
    ].join("\n");
  } catch (_) {
    return "";
  }
}

// Robust on-demand keyword match (Pillar R, 2026-06-14 — found by the HELD-OUT diverse run).
// Naive `msg.includes("what failed")` MISSES natural phrasing — "what MACHINES failed recently"
// has no literal "what failed" substring (intervening word), so the on-demand fetch silently does
// NOT fire and the companion deflects or fabricates on a question it should SERVE. This is the
// brittleness behind "passes the eval, fails the real user". Fix: match if the FULL keyword is a
// substring (unchanged behaviour) OR every CONTENT word of a multi-word keyword (len ≥ 5, minus
// framing stopwords) appears anywhere in the message — so word order / intervening words no longer
// break routing, without per-phrase patching.
const _MATCH_STOP = new Set([
  "what", "whats", "the", "and", "any", "show", "tell", "give", "about", "recent", "recently",
  "last", "this", "that", "your", "you", "have", "has", "with", "from", "right", "now", "please",
  "can", "could", "would", "should", "does", "did", "are", "is", "for", "our", "their",
]);
function _msgMatchesKeywords(msg: string, keywords: string[] | undefined): boolean {
  const m = msg.toLowerCase();
  return (keywords || []).some((k) => {
    const kl = k.toLowerCase();
    if (m.includes(kl)) return true;                                   // exact substring (legacy)
    const words = kl.split(/[^a-z0-9]+/).filter((w) => w.length >= 5 && !_MATCH_STOP.has(w));
    return words.length > 0 && words.every((w) => m.includes(w));      // all content words, any order
  });
}

// Build the LIVE OPERATIONS SNAPSHOT block (2026-06-13 fabrication fix). Reads the same
// canonical truth views the rest of the platform reads — v_alert_truth (active alerts),
// asset_nodes (the registered asset-tag list), v_pm_scope_items_truth (overdue PM),
// v_kpi_truth + analytics_snapshots + inventory/PM/skills/projects/risk (Pillar S, all assembled by
// the registry-driven Gateway Engine — see buildFromRegistry) — and
// renders a compact, token-capped grounding block. Uses the service-role admin client
// (RLS-bypass) but is hive-scoped by the .eq("hive_id") filter on every read, so it can
// only ever surface THIS hive's data (no cross-hive leak). Never persisted; best-effort
// (any error or empty result returns "" and the conversation proceeds ungrounded as before).
async function buildOpsSnapshot(client: SupabaseClient, hiveId: string, message = ""): Promise<string> {
  try {
    const [alertsCountRes, alertsTopRes, assetsRes] = await Promise.all([
      client.from("v_alert_truth").select("alert_id", { count: "exact", head: true })
        .eq("hive_id", hiveId).eq("status", "active"),
      client.from("v_alert_truth").select("machine,severity,title")
        .eq("hive_id", hiveId).eq("status", "active").limit(60),
      // canonical-allow: the ops snapshot needs the raw registered-asset TAG list straight from
      // asset_nodes (the source of truth for "which tags exist in this hive"); v_asset_truth is a
      // derived/scoped view, not the canonical tag registry for the existence check.
      client.from("asset_nodes").select("tag").eq("hive_id", hiveId).not("tag", "is", null),
    ]);
    const topRows = (alertsTopRes.data ?? []) as Array<{ machine?: string; severity?: string; title?: string }>;
    const activeAlerts = alertsCountRes.count ?? topRows.length;
    const rank: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
    const top = topRows.slice()
      .sort((a, b) => (rank[String(a.severity || "").toLowerCase()] ?? 9) - (rank[String(b.severity || "").toLowerCase()] ?? 9))
      .slice(0, 4)
      .map((a) => `${a.machine || "?"} (${String(a.severity || "?").toLowerCase()}: ${String(a.title || "").slice(0, 44)})`);
    const tags = Array.from(new Set(
      ((assetsRes.data ?? []) as Array<{ tag?: string }>).map((a) => a.tag).filter(Boolean) as string[],
    )).sort();

    let overdue: number | null = null;
    try {
      const { count } = await client.from("v_pm_scope_items_truth")
        .select("*", { count: "exact", head: true }).eq("hive_id", hiveId).eq("is_overdue", true);
      overdue = count ?? null;
    } catch (_) { /* view absent in some envs; best-effort */ }

    // Pillar S — serve every worker-relevant computed domain from its canonical truth view, in parallel.
    // Pillar S — REGISTRY-DRIVEN (Phase 2): every served + always_on entry that carries an `engine`
    // spec becomes a snapshot fact through the ONE engine (declarative spec OR custom handler).
    // Register, don't wire — adding a domain is a companion_source_registry.json entry, no code here.
    // Order follows the registry. The core facts above (alerts/overdue/asset tags) have no engine
    // spec and stay hand-built.
    // deno-lint-ignore no-explicit-any
    const engineEntries = (((sourceRegistry as any).sources) as any[])
      .filter((e) => e.status === "served" && e.always_on && e.engine);
    const engineBlocks = await Promise.all(
      engineEntries.map((e) => buildFromRegistry(client, hiveId, e)),
    );
    // Pillar R (on-demand routing): `served_on_demand` entries whose `match` keywords hit the
    // worker's message get fetched too — the companion reaches the long-tail views (logbook,
    // asset detail, sensor, FMEA…) WITHOUT bloating every turn. Same engine, capped at 2.
    const msg = (message || "").toLowerCase();
    // deno-lint-ignore no-explicit-any
    const onDemandBlocks = await Promise.all(
      (((sourceRegistry as any).sources) as any[])
        .filter((e) => e.status === "served_on_demand" && e.engine &&
          _msgMatchesKeywords(msg, e.match as string[]))
        .slice(0, 2)
        .map((e) => buildFromRegistry(client, hiveId, e)),
    );
    // Pillar P (proactivity): when the worker OPENS with a greeting / open-ended question (no
    // specific ask), prepend a rank-ordered, deterministic ATTENTION briefing so the companion
    // surfaces the urgent facts unprompted and offers to act. Silent ("") on specific questions
    // or when nothing is urgent.
    const proactive = isProactiveOpener(msg) ? await buildProactiveBriefing(client, hiveId) : "";
    // Pillar K (cross-modal RAG): a how-to/knowledge question pulls the hive's own SOPs/fault
    // history into the grounding so the companion answers from real records, not invented steps.
    const knowledge = isKnowledgeQuestion(msg) ? await buildKnowledgeContext(client, hiveId, message) : "";
    const lines = [
      "=== LIVE OPERATIONS SNAPSHOT (verified from this hive's records, right now) ===",
      `Active alerts (the open jobs needing attention): ${activeAlerts}${top.length ? ` — top: ${top.join("; ")}` : ""}.`,
      overdue != null ? `Overdue PM tasks: ${overdue}.` : "",
      tags.length ? `Registered assets (${tags.length}) — these are the ONLY real asset tags in this hive: ${tags.join(", ")}.` : "",
      proactive,
      knowledge,
      ...engineBlocks,
      ...onDemandBlocks,
      "GROUNDING RULE: every figure above (alerts, overdue PM, registered assets, MTBF/MTTR/OEE, inventory/stock, PM compliance, team/skills, projects, asset risk) is computed from THIS hive's own records — answer questions about them by quoting these real numbers and names directly; that is the correct, grounded answer, NOT a reason to deflect. If a worker asks for a figure that is genuinely NOT shown above (a metric we don't list, or a specific per-item detail not included), say it isn't in this snapshot and point them to the matching page (Analytics, Inventory, PM Scheduler, Skill Matrix, Project Manager, Asset Hub) — never invent a number. If the worker names an asset tag that is not in the registered list, tell them it is not one of their registered assets rather than describing its condition.",
    ].filter(Boolean);
    return lines.join("\n");
  } catch (_) {
    return "";
  }
}

// Agents that participate in the PROSPECTIVE follow-up queue (layer 06). For
// these the gateway (a) surfaces any of the worker's follow-ups that are now
// due into the context, and (b) enqueues new follow-ups the specialist emits in
// its envelope (`followups: [{topic, detail?, due_in_days?}]`). Task/asset
// agents whose work naturally spawns "check back later" items.
const FOLLOWUP_AGENTS: Set<string> = new Set([
  "asset-brain", "shift", "project",
]);
const FOLLOWUP_RECALL_LIMIT = 4;

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

// Whitelist of agent_ids the gateway will route to. Each entry maps to
// a deployed edge function. Adding a new specialist agent requires
// updating BOTH this map AND the validate_gateway_routing.py registry
// so new agents stay discoverable.
const AGENT_ROUTES: Record<string, { fn: string; description: string }> = {
  "asset-brain": {
    fn: "asset-brain-query",
    description: "Asset-specific Q&A over graph + timeline + similar failures",
  },
  "analytics": {
    fn: "analytics-orchestrator",
    description: "OEE / MTBF / failure analytics with multi-phase reasoning",
  },
  "project": {
    fn: "project-orchestrator",
    description: "Project planning + change-order analysis",
  },
  "shift": {
    fn: "shift-planner-orchestrator",
    description: "Shift planning + handover summarisation",
  },
  "logbook-voice": {
    fn: "voice-logbook-entry",
    description: "Voice transcription + structured logbook intent",
  },
  "report-voice": {
    fn: "voice-report-intent",
    description: "Voice transcription + report-sender intent",
  },
  "voice-journal": {
    fn: "voice-journal-agent",
    description: "Multilingual voice journaling companion with rolling memory",
  },
  // Phase 1+2 (2026-06-07) brain convergence: route the full Work Assistant
  // through the ONE front door so it shares memory + persona + rate-limit
  // instead of bypassing to ai-orchestrator directly. The gateway forwards the
  // caller's JWT; ai-orchestrator reads `message` (gateway shape) via adapter
  // and resolves the real worker_name from that JWT for solo scoping.
  "assistant": {
    fn: "ai-orchestrator",
    description: "Full multi-agent fan-out (failure/PM/inventory/shift/...) over the worker's own hive data",
  },
  // Reliability Coach (D5 fold, 2026-06-14): hive.html's supervisor coach used to
  // call ai-orchestrator DIRECTLY (mode:'coach') — the last conversational Tier-3
  // surface bypassing the one front door. Route it here so it shares persona +
  // rate-limit + (future) memory. Coach returns STRUCTURED `actions[]`, so it is
  // ALSO in STRUCTURED_PASSTHROUGH_AGENTS below and forwardExtras pins mode:'coach'
  // (ai-orchestrator reads top-level `mode`; the gateway doesn't forward it otherwise).
  "coach": {
    fn: "ai-orchestrator",
    description: "Reliability coach — ranked weekly actions (mode:coach) over the hive's truth views",
  },
  // Step 4 (Companion Unification) — the cross-page voice/text TOOL router. The
  // Companion mic/text invokes this through the ONE front door so it inherits
  // rate-limit + persona + PII for free; the page then applies the returned
  // structured intents. Unlike the conversational agents above, this specialist
  // returns STRUCTURED output (intents[] / asset_resolution / narration), so it
  // is registered in STRUCTURED_PASSTHROUGH_AGENTS below to survive the
  // gateway's {answer}-only contract. See [[project_companion_unification]].
  "voice-action": {
    fn: "voice-action-router",
    description: "Voice/text -> structured platform intents (logbook.create | inventory.deduct | pm.complete | asset.lookup | query.ask) the page applies",
  },
  // L05 cold-archive / temporal layer (K6 wire, 2026-06-12). Historical "what
  // happened back in <period>" questions over canonical_period_summaries (month/
  // quarter/year rollups, incl. >18mo). The function existed but was never a gateway
  // route, so the cold-archive wire was dark. Reads body.question -> forwardExtras.
  "temporal-rag": {
    fn: "temporal-rag-orchestrator",
    description: "Temporal / cold-archive retrieval over canonical period summaries (historical >18mo questions)",
  },
};

// Agents whose UI consumes STRUCTURED output (intents, cards, citations) in
// ADDITION to prose. For these the gateway is a TOOL front door, not a chat:
// the conversational `answer` alone is insufficient. We pass the full specialist
// payload through as `route_result` (PII-hydrated exactly like `answer`) so the
// page can apply it. See ai-engineer skill: "the gateway's {answer} contract
// DROPS structured payloads -- only conversational surfaces fold cleanly".
// "voice-action" (router intents) was the first; "asset-brain" returns
// { answer, cited[], narration } where `cited[]` is the RAG citation set — the
// conversational {answer}-only contract would DROP it, so a future asset-hub
// fold through the gateway would lose source chips (capstone RAG-pillar finding
// 2026-06-07). Adding it makes the gateway citation-preserving; existing direct
// asset-hub callers are unaffected (additive).
// "coach" added 2026-06-14 (D5 fold): ai-orchestrator coach mode returns a
// STRUCTURED `actions[]` (priority/urgency/machine/why), NOT a conversational
// `answer` — so it must pass through under `route_result` to survive the
// gateway's {answer}-only contract, exactly like asset-brain/voice-action.
const STRUCTURED_PASSTHROUGH_AGENTS: Set<string> = new Set(["voice-action", "asset-brain", "coach"]);

interface GatewayRequest {
  agent:    string;
  message:  string;
  context?: Record<string, unknown>;
  hive_id?: string | null;
}

interface GatewayResponse {
  answer:     string;
  agent:      string;
  memory_id?: string;
  usage?:     { latency_ms: number };
  error?:     string;
}

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);

  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  // /health probe — runs BEFORE method check so monitors can GET /health.
  // Pings the Supabase service and at least one model provider.
  const SERVICE_KEY_HEALTH = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
  const SUPABASE_URL_HEALTH = Deno.env.get("SUPABASE_URL") || "";
  const healthResp = await handleHealth(req, "ai-gateway", async () => {
    const deps = [
      { name: "supabase",     ok: Boolean(SERVICE_KEY_HEALTH && SUPABASE_URL_HEALTH) },
      { name: "groq",         ok: Boolean(Deno.env.get("GROQ_API_KEY")) },
      { name: "cerebras",     ok: Boolean(Deno.env.get("CEREBRAS_API_KEY")) },
    ];
    return { deps };
  });
  if (healthResp) return healthResp;

  if (req.method !== "POST") {
    return jsonResponse(corsHeaders, 405, { error: "POST only" });
  }

  const t0 = Date.now();

  let body: GatewayRequest;
  try {
    body = await req.json();
  } catch {
    return jsonResponse(corsHeaders, 400, { error: "Invalid JSON" });
  }

  const { agent, message, context = {}, hive_id = null } = body;

  // Begin request context (trace_id propagation + envelope spine).
  // hive_id is captured up-front; user_id is filled in once auth resolves.
  const ctx = beginRequest(req, { route: "ai-gateway", hive_id: hive_id ?? undefined });
  log.info(ctx, "request_start", { agent, message_len: message?.length ?? 0 });

  if (!agent || typeof agent !== "string") {
    return jsonResponse(corsHeaders, 400, { error: "Missing agent" });
  }
  if (!message || typeof message !== "string") {
    return jsonResponse(corsHeaders, 400, { error: "Missing message" });
  }

  const route = AGENT_ROUTES[agent];
  if (!route) {
    return jsonResponse(corsHeaders, 400, {
      error: `Unknown agent '${agent}'. Available: ${Object.keys(AGENT_ROUTES).join(", ")}`,
    });
  }

  // Identity binding -- pull the auth user from the JWT in the request.
  const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
  const ANON_KEY     = Deno.env.get("SUPABASE_ANON_KEY")!;
  const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const authHeader   = req.headers.get("Authorization") || "";
  const authedClient: SupabaseClient = createClient(SUPABASE_URL, ANON_KEY, {
    global: { headers: { Authorization: authHeader } },
  });
  const adminClient: SupabaseClient = createClient(SUPABASE_URL, SERVICE_KEY);

  // 2026-05-19 Companion Streamline Step C/D: voice-journal is the
  // platform's onboarding companion — workers talk to Hezekiah/Zaniah before
  // they ever sign up. Letting that one agent through anonymously is
  // intentional. Every other agent (asset-brain, analytics, project,
  // shift, etc.) still hard-requires Supabase Auth. The previous policy
  // failed the user's "Equipment alerts today" voice command with
  // "Sign-in required" → caller's catch fired → user saw
  // "Sorry, I'm offline."
  const ANON_OK_AGENTS = new Set(["voice-journal"]);

  const { data: { user } } = await authedClient.auth.getUser();
  if (!user && !ANON_OK_AGENTS.has(agent)) {
    return jsonResponse(corsHeaders, 401, { error: "Sign-in required" });
  }

  // Resolve worker_name + persona preference. For authed users we look
  // up worker_profiles; for anon voice-journal callers we trust the
  // context (and skip memory writes downstream).
  let worker_name: string;
  let accountPersona = "zaniah";
  let authUid: string | null = null;
  if (user) {
    const { data: profile } = await adminClient.from("v_worker_truth")
      .select("worker_name, preferred_persona").eq("auth_uid", user.id).maybeSingle();
    worker_name    = profile?.worker_name || user.email || "anonymous";
    accountPersona = (profile?.preferred_persona as string | undefined) || "zaniah";
    authUid        = user.id;
  } else {
    // Anonymous voice-journal caller. worker_name from context if the
    // browser passed one (most do, via localStorage); fall back to a
    // generic label so the agent prompt still has something to address.
    const ctxWorker =
      (context && typeof context === "object" && typeof (context as any).worker_name === "string")
        ? String((context as any).worker_name).trim()
        : "";
    worker_name = ctxWorker || "kapatid";   // generic, warm
  }

  // Persona Contract: every conversational specialist that adopts the
  // contract reads ctx.persona; if the client didn't supply one, default
  // to the account-level preference (authed) or the system default
  // ('zaniah' as of the 2026-05-20 rename — same Strategist lens as the
  // former 'rosa' default; the shared persona module is authoritative).
  if (context && typeof context === "object" && !("persona" in context)) {
    (context as Record<string, unknown>).persona = accountPersona;
  }

  // Rate gate ONCE per request — now BOTH hive-level AND user-level (P1
  // roadmap 2026-05-26). The per-user inner cap stops one noisy worker
  // inside a hive from starving their teammates while the hive cap protects
  // the LLM chain from a single hive's burst.
  //
  // ADAPTIVE DEGRADATION (P1 roadmap 2026-05-26 — RL.3): when the cap fires
  // we try to return a *cached* answer for an identical question instead of
  // a 429. Companion UX dies on 429 today; serving a stale-but-real answer
  // keeps the conversation alive. Cache lookup is keyed by (agent, message)
  // — same shape used in Router/Grader/Checker caching.
  // Fallback defaults aligned with supabase/functions/.env (hive 500 / user 500).
  // The local `supabase start` edge runtime is launched WITHOUT --env-file, so
  // Deno.env never sees functions/.env — the gateway therefore fell back to the
  // old 50/25 and throttled local testing/probe batteries at 25/user/hour.
  // Prod sets WH_*_RATE_LIMIT_OVERRIDE explicitly, so these fallbacks only apply
  // where the env is unset (i.e. local). Test batteries need the headroom to
  // prove behaviour; the per-user cap still protects a shared hive.
  const RL_OVERRIDE      = Number(Deno.env.get("WH_RATE_LIMIT_OVERRIDE")        || 500);
  const RL_USER_OVERRIDE = Number(Deno.env.get("WH_USER_RATE_LIMIT_OVERRIDE")   || 500);
  const userId = authUid || ""; // anon callers skip the inner per-user bucket
  const rl = await checkUserRateLimit(
    adminClient,
    hive_id || "",
    userId,
    RL_OVERRIDE,
    RL_USER_OVERRIDE,
  );
  if (!rl.allowed) {
    log.warn(ctx, "rate_limit_hit", {
      hive_remaining: rl.hive_remaining,
      user_cap:       rl.user_cap,
      scope:          rl.hive_remaining === 0 ? "hive" : "user",
    });
    // Adaptive degrade: try LLM cache for this exact (agent, message) before
    // returning 429. Only worth it for short messages — long ones rarely
    // repeat verbatim. Hits the same `ai_cache` table the RAG stages use.
    if (message.length <= 200) {
      try {
        const { cacheLookup } = await import("../_shared/cache.ts");
        const cacheKey = `gateway:${agent}:${message}`;
        const hit = await cacheLookup<{ answer: string }>(adminClient, "ai-gateway-adaptive", cacheKey);
        if (hit.hit && hit.data?.answer) {
          log.info(ctx, "adaptive_cache_served", { agent });
          recordModelHop(ctx, "ai-cache");
          return ok(ctx, { answer: hit.data.answer, agent, usage: { latency_ms: Date.now() - t0, served_from: "adaptive_cache" } });
        }
      } catch { /* fall through to 429 */ }
    }
    // Distinguish scope so the frontend can show a clearer message.
    if (rl.hive_remaining === 0) return rateLimitedResponse(corsHeaders);
    return userRateLimitedResponse(corsHeaders, rl.user_cap);
  }

  // Gibberish guard — detect transcripts that look like noise BEFORE we burn
  // a rate-limit slot and have the LLM hallucinate a coherent reply. The
  // 2026-05-26 baseline showed the voice-journal agent confidently
  // responding to "asdfqwer ghjkzxcv mnbvpoiu lkjhgfds" with a story about
  // "technical issues with the compressor". Threshold: <22% vowel ratio AND
  // length > 12 AND no whitespace word looks like a real word (>=3 chars
  // with at least one vowel).
  if (typeof message === "string" && message.length > 12) {
    const stripped = message.replace(/[^a-zA-Z]/g, "");
    if (stripped.length >= 12) {
      const vowels = (stripped.match(/[aeiouAEIOU]/g) || []).length;
      const vowelRatio = vowels / stripped.length;
      // Keyboard-row gibberish has 5+ consecutive consonants in one or more
      // words. Real English / Tagalog words rarely do — "P-203", "kapatid",
      // "compressor" all safe; "ghjkzxcv" / "asdfqwer" hit.
      const words = message.split(/\s+/).filter((w) => w.length >= 3);
      const noisyWords = words.filter((w) =>
        /[bcdfghjklmnpqrstvwxyz]{5,}/i.test(w) || !/[aeiouAEIOU]/i.test(w)
      );
      const noisyRatio = words.length ? noisyWords.length / words.length : 0;
      if (vowelRatio < 0.30 && noisyRatio >= 0.5) {
        return jsonResponse(corsHeaders, 200, {
          answer: "Sorry, I couldn't make out what you said. Could you try again? Pakiulit po — hindi ko narinig nang malinaw.",
          agent,
          usage: { latency_ms: Date.now() - t0, refused_as: "low_quality_transcript" },
        } satisfies GatewayResponse & { usage: { latency_ms: number; refused_as?: string } });
      }
    }
  }

  // Memory hydration. Anon callers (voice-journal first-touch) skip
  // agent_memory entirely — the table is RLS-keyed on auth_uid so we
  // can't persist without one, and reading a stranger's memory is the
  // exact failure mode the gateway exists to prevent. Anon paths
  // therefore get an empty memory_block and degrade gracefully.
  let memory_block = "";
  // W3 structural-echo: track which layer sections actually got injected, so the
  // auth-gated local-only debug echo can assert each wire deterministically (no LLM).
  const memorySections: Record<string, boolean> = {
    working: false, semantic: false, episodic: false,
    verified_state: false, procedural: false, followups: false,
    domain_knowledge: false, ops_snapshot: false,
  };
  if (authUid) {
    const handle: MemoryHandle = {
      hive_id, worker_name, auth_uid: authUid, agent_id: agent,
    };
    const loaded = await loadMemory(adminClient, handle);
    memory_block = formatMemoryContext(loaded);
    memorySections.working = !!memory_block;
  }

  // Semantic-recall enrichment for agents that opt in (voice-journal).
  // Skipped for anon for the same reason as agent_memory above.
  let recallEmbedding: number[] = [];
  if (authUid && SEMANTIC_RECALL_AGENTS.has(agent)) {
    try {
      const recall = await loadJournalRecall(adminClient, authUid, message);
      recallEmbedding = recall.query_embedding;
      if (recall.block) {
        memory_block = memory_block
          ? `${memory_block}\n\n${recall.block}`
          : recall.block;
        memorySections.semantic = true;
      }
    } catch (err) {
      console.warn("[ai-gateway] recall failed (non-fatal):", err instanceof Error ? err.message : err);
    }
  }

  // Durable episodic-memory recall for the non-journal specialists. Pure DB,
  // no embedding/LLM call. Hive-scoped + worker-scoped via the shared module's
  // query. Anon callers (no authUid) skip — recall is identity-bound the same
  // way agent_memory is. Best-effort: a failure just means no long-term block.
  if (authUid && EPISODIC_MEMORY_AGENTS.has(agent)) {
    try {
      const durable = await recallEpisodic(adminClient, hive_id, worker_name, {
        limit: EPISODIC_RECALL_LIMIT,
        query: message,
      });
      const durableBlock = formatEpisodicContext(durable);
      if (durableBlock) {
        memory_block = memory_block ? `${memory_block}\n\n${durableBlock}` : durableBlock;
        memorySections.episodic = true;
      }
    } catch (err) {
      console.warn("[ai-gateway] episodic recall failed (non-fatal):", err instanceof Error ? err.message : err);
    }
  }

  // Verified-state injection (layer 07). When the turn is about a specific
  // asset, resolve its conflict-resolved current state so the agent reads one
  // shared truth. asset_tag comes from context (the asset hub passes it). Pure
  // DB read; hive-scoped; best-effort. Needs a hive (no solo verified state).
  if (authUid && hive_id && VERIFIED_STATE_AGENTS.has(agent)) {
    const assetTag = context && typeof context === "object"
      ? (context as Record<string, unknown>).asset_tag
      : null;
    if (typeof assetTag === "string" && assetTag.trim()) {
      try {
        const state = await resolveAssetState(adminClient, hive_id, { assetTag: assetTag.trim() });
        const stateBlock = formatVerifiedState(state);
        if (stateBlock) {
          memory_block = memory_block ? `${memory_block}\n\n${stateBlock}` : stateBlock;
          memorySections.verified_state = true;
        }
      } catch (err) {
        console.warn("[ai-gateway] verified-state resolve failed (non-fatal):", err instanceof Error ? err.message : err);
      }
    }
  }

  // Procedural skill-library matching (layer 04). Embed the turn and pull the
  // hive's top proven procedures for this kind of problem (match_procedural_memories
  // over distilled procedural memories). Hive-scoped (a teammate's proven fix
  // helps anyone); best-effort, so an embedding/RPC miss just omits the block.
  // Needs a hive + identity, same as episodic recall.
  if (authUid && hive_id && PROCEDURAL_SKILL_AGENTS.has(agent)) {
    try {
      const procs = await matchProcedures(adminClient, hive_id, worker_name, message, {
        limit: PROCEDURE_RECALL_LIMIT,
      });
      const procBlock = formatProcedures(procs);
      if (procBlock) {
        memory_block = memory_block ? `${memory_block}\n\n${procBlock}` : procBlock;
        memorySections.procedural = true;
      }
    } catch (err) {
      console.warn("[ai-gateway] procedure match failed (non-fatal):", err instanceof Error ? err.message : err);
    }
  }

  // Prospective follow-up surfacing (layer 06). Pull this worker's follow-ups
  // that are now due and inject them so the agent raises its own deferred
  // intentions. Pure DB read; marks surfaced fire-and-forget. Best-effort.
  if (authUid && (hive_id || worker_name) && FOLLOWUP_AGENTS.has(agent)) {
    try {
      const due = await recallDueFollowups(adminClient, hive_id, worker_name, {
        limit: FOLLOWUP_RECALL_LIMIT,
      });
      const dueBlock = formatFollowups(due);
      if (dueBlock) {
        memory_block = memory_block ? `${memory_block}\n\n${dueBlock}` : dueBlock;
        memorySections.followups = true;
      }
    } catch (err) {
      console.warn("[ai-gateway] follow-up recall failed (non-fatal):", err instanceof Error ? err.message : err);
    }
  }

  // Persona-Knowledge enrichment (layer 08 / O11 — the CONVERSATIONAL wire). For the
  // floating-launcher conversational agent, retrieve the PERSONA-SCOPED curated DOMAIN
  // corpus (SKILL.md + standards, ingested into persona_knowledge) and inject a
  // token-capped DOMAIN KNOWLEDGE block — making persona.ts DOMAIN_LENS actually
  // RETRIEVE from its named wells. THE gap: domain RAG served specialists, never the
  // launcher where the personas live. persona scope (Hezekiah technical / Zaniah
  // strategic, both + shared) is the O6/O10 wire; threshold = O8; token cap = O9;
  // best-effort = O12. Needs identity (embeds the turn).
  if (authUid && PERSONA_KNOWLEDGE_AGENTS.has(agent)) {
    try {
      const persona = context && typeof context === "object"
        ? ((context as Record<string, unknown>).persona as string | undefined)
        : undefined;
      const chunks = await loadPersonaKnowledge(adminClient, persona, message);
      const domainBlock = formatPersonaKnowledge(chunks);
      if (domainBlock) {
        memory_block = memory_block ? `${memory_block}\n\n${domainBlock}` : domainBlock;
        memorySections.domain_knowledge = true;
      }
    } catch (err) {
      console.warn("[ai-gateway] persona-knowledge load failed (non-fatal):", err instanceof Error ? err.message : err);
    }
  }

  // Live operations snapshot (layer 09 — verified ops grounding for the conversational
  // launcher). THE 2026-06-13 fabrication fix: voice-journal had the persona BRAIN +
  // all the recall layers above, but NO live hive operational data — so it answered
  // "open jobs / how many alerts / which assets / what's my OEE" from fuzzy conversational
  // memory, confabulating assets ("P-203") and metrics ("78% OEE", "PM <70%") or deflecting
  // to the Work Assistant. Prepend a compact, verified, hive-scoped snapshot so those
  // questions ground in TRUTH and the agent can reject unregistered asset tags. Prepended
  // (not appended) so it OUTRANKS the stale conversational summary that follows it. Pure DB
  // reads via the admin client, hive-scoped, token-capped, best-effort.
  if (authUid && hive_id && OPS_SNAPSHOT_AGENTS.has(agent)) {
    try {
      const opsBlock = await buildOpsSnapshot(adminClient, hive_id, typeof message === "string" ? message : "");
      if (opsBlock) {
        memory_block = memory_block ? `${opsBlock}\n\n${memory_block}` : opsBlock;
        memorySections.ops_snapshot = true;
      }
    } catch (err) {
      console.warn("[ai-gateway] ops snapshot failed (non-fatal):", err instanceof Error ? err.message : err);
    }
  }

  // Asset-tag -> asset_id resolution (body-shape adapter completion). The
  // asset-centric specialist (asset-brain-query) REQUIRES a resolved asset_id
  // (UUID) but the documented surface contract grounds by `context.asset_tag`
  // (the human tag — the same field verified-state resolves on above). Without
  // this, a turn carrying only asset_tag 400s "Missing required fields: asset_id"
  // at the specialist (W1 wiring gap, 2026-06-12). Resolve tag -> id hive-scoped
  // (no cross-hive leak; a foreign tag simply doesn't resolve) and inject it into
  // context so BOTH the forward and the specialist's `asset_id ?? context.asset_id`
  // adapter land. Best-effort: a miss leaves the prior (400) behavior, no worse.
  // A UUID is not PII, so it survives the redactor below.
  if (hive_id && ASSET_ID_FORWARD_AGENTS.has(agent) && context && typeof context === "object") {
    const ctxObj = context as Record<string, unknown>;
    const tag = typeof ctxObj.asset_tag === "string" ? ctxObj.asset_tag.trim() : "";
    const hasId = typeof ctxObj.asset_id === "string" && (ctxObj.asset_id as string).trim();
    if (tag && !hasId) {
      let resolvedId: string | undefined;
      try {
        // canonical-allow: resolving a spoken asset TAG to its node id is a registry lookup against
        // asset_nodes (the canonical tag→id source); v_asset_truth is a scoped/derived view, not the
        // tag registry, so the raw asset_nodes read is correct here.
        const { data: rows } = await adminClient
          .from("asset_nodes")
          .select("id")
          .eq("hive_id", hive_id)
          .eq("tag", tag)
          .limit(1);
        resolvedId = rows && rows[0] ? (rows[0] as { id?: string }).id : undefined;
      } catch (err) {
        console.warn("[ai-gateway] asset_tag->asset_id resolve failed (non-fatal):", err instanceof Error ? err.message : err);
      }
      if (resolvedId) {
        ctxObj.asset_id = resolvedId;
      } else {
        // Graceful not-found. The tag doesn't resolve in THIS hive (typo, deleted,
        // or a tag from another hive — hive-scoped query returns nothing). Forwarding
        // would 400 "Missing required fields: asset_id" and leak a raw error to the
        // UI (the "Asset not found in this hive" class). Answer helpfully in the
        // success envelope instead. No PII to hydrate (only the asset tag echoes).
        log.info(ctx, "asset_tag_unresolved", { agent, tag });
        return ok(ctx, {
          answer: `I couldn't find asset "${tag}" in this hive. Double-check the tag, or open the asset from your asset list so I can pull its records.`,
          agent,
          usage: { latency_ms: Date.now() - t0 },
        });
      }
    }
  }

  // PII redaction. Both the user message AND the context object pass
  // through the same redactor so a downstream agent never sees raw
  // identity unless the agent is explicitly opted-in (Stripe / Resend
  // paths run outside the gateway).
  const { redacted: redactedMessage, hydration: msgMap } =
    redactPIIWithMap(message);
  const { redacted: redactedContext, hydration: ctxMap } =
    redactPIIWithMap(context);
  const hydrationMap = { ...msgMap, ...ctxMap };

  // Forward to the specialist agent. Derive functions URL from
  // SUPABASE_URL so we don't need a separate env var (declared in
  // validate_env_secret_coverage); functions endpoint is always
  // {project}.supabase.co/functions/v1.
  const targetUrl = `${SUPABASE_URL}/functions/v1/${route.fn}`;

  // Sticky-session key for the downstream callAI chain (FreeLLMAPI borrow #3):
  // pins a multi-turn conversation to one model for ~30min. Built ONLY from
  // non-PII identifiers (hive UUID + agent role + auth UUID) — never the real
  // worker_name, which is redacted out of the forwarded body below. Anon
  // callers (no authUid) get no key, so the chain behaves exactly as before.
  const session_key = authUid ? `${hive_id || "nohive"}:${agent}:${authUid}` : undefined;

  // Per-agent forward augmentation (body-shape adapter completion). Some
  // specialists REQUIRE fields the conversational gateway shape doesn't carry.
  // shift-planner-orchestrator requires `shift_window` (06-14 | 14-22 | 22-06); a
  // companion "summarize the handover" turn has none, so it 400s "Missing required
  // field: shift_window" through the gateway (W1 wiring gap, 2026-06-12). Derive
  // the CURRENT window from PHT (UTC+8), or honor an explicit context.shift_window
  // if the shift-brain page passed one.
  const forwardExtras: Record<string, unknown> = {};
  if (agent === "shift") {
    const ctxWin = context && typeof context === "object"
      ? String((context as Record<string, unknown>).shift_window || "").trim() : "";
    const VALID_SHIFT_WINDOWS = new Set(["06-14", "14-22", "22-06"]);
    let win = VALID_SHIFT_WINDOWS.has(ctxWin) ? ctxWin : "";
    if (!win) {
      const phtHour = (new Date().getUTCHours() + 8) % 24;
      win = (phtHour >= 6 && phtHour < 14) ? "06-14"
          : (phtHour >= 14 && phtHour < 22) ? "14-22" : "22-06";
    }
    forwardExtras.shift_window = win;
  }
  // analytics-orchestrator requires a `phase`; a conversational "how's our OEE" turn
  // has none -> 400 "Missing required field: phase". Default to the prescriptive phase
  // (the one that synthesizes a narrative summary), or honor an explicit context.phase.
  // (W9 wiring fix 2026-06-12 — the 4th instance of the body-shape-adapter gap.)
  if (agent === "analytics") {
    const ctxPhase = context && typeof context === "object"
      ? String((context as Record<string, unknown>).phase || "").trim().toLowerCase() : "";
    const VALID_PHASES = new Set(["descriptive", "diagnostic", "predictive", "prescriptive"]);
    forwardExtras.phase = VALID_PHASES.has(ctxPhase) ? ctxPhase : "prescriptive";
  }
  // project-orchestrator reads top-level `phase` (narrative|intent|lessons_draft) +
  // `project_id`; the gateway forwards them only inside context -> 400 "phase is
  // required". Default to the narrative phase (the conversational progress summary)
  // and lift project_id out of context. (5th instance of the body-shape-adapter gap.)
  if (agent === "project") {
    const c = (context && typeof context === "object") ? context as Record<string, unknown> : {};
    const ctxPhase = String(c.phase || "").trim().toLowerCase();
    const VALID_PROJECT_PHASES = new Set(["narrative", "intent", "lessons_draft"]);
    forwardExtras.phase = VALID_PROJECT_PHASES.has(ctxPhase) ? ctxPhase : "narrative";
    if (c.project_id) forwardExtras.project_id = c.project_id;
  }
  // temporal-rag-orchestrator (L05 cold-archive) reads top-level `question`; the
  // gateway forwards `message`. Alias it so a historical turn resolves (K6 wire).
  if (agent === "temporal-rag") {
    forwardExtras.question = message;
  }
  // Reliability Coach (D5 fold): ai-orchestrator returns the ranked `actions[]`
  // ONLY when it receives top-level `mode:'coach'`; the gateway doesn't forward
  // `mode` otherwise. Pin it for the coach agent so the coach route IS coach mode
  // (question is already read by the orchestrator as body.message — no alias needed).
  if (agent === "coach") {
    forwardExtras.mode = "coach";
  }

  // W3 structural-echo short-circuit (LOCAL-ONLY, triple-gated). Return EXACTLY the
  // context the specialist would receive — the PII-redacted message + the assembled
  // memory_block + which layer sections fired + the forward extras — with NO LLM
  // call, so the wiring battery asserts J1/K3/K5/K8 deterministically. Prod never
  // sets WH_ALLOW_DEBUG_ECHO, so this is dead in production (guarded by a validator).
  if (DEBUG_ECHO_ENABLED && authUid && context && typeof context === "object"
      && (context as Record<string, unknown>).debug_echo_memory_block === true) {
    log.info(ctx, "debug_echo_memory_block", { agent, sections: memorySections });
    return ok(ctx, {
      answer: "",
      debug_echo: {
        agent,
        forwarded_message: redactedMessage,
        memory_block,
        sections: memorySections,
        forward_extras: forwardExtras,
        hydration_keys: Object.keys(hydrationMap),
      },
    });
  }

  // W4 fault-injection probe (LOCAL-ONLY, gated exactly like the debug echo). Drives
  // the model chain with simulated provider failures and returns whether an answer
  // still landed — proving M1 (primary down -> fallback serves), M2 (all-down ->
  // graceful degrade, conversation survives), M4 (413 skip) live, without touching
  // real provider keys. Chain-only probe: no specialist forward.
  {
    const fi = (DEBUG_ECHO_ENABLED && authUid && context && typeof context === "object")
      ? (context as Record<string, unknown>).debug_fault_inject
      : undefined;
    if (fi && typeof fi === "object") {
      const f = fi as Record<string, unknown>;
      const probe = await callAI("Reply with the single word OK.", {
        maxTokens: 16, temperature: 0, jsonMode: false,
        faultInject: {
          fail: Array.isArray(f.fail) ? (f.fail as string[]) : undefined,
          failAll: f.failAll === true,
          mode: f.mode as "429" | "413" | "down" | undefined,
        },
      });
      const degraded = !probe || probe.trim() === "" || probe.trim() === "{}";
      log.info(ctx, "debug_fault_inject", { degraded });
      return ok(ctx, {
        answer: degraded
          ? "Sorry, the AI service is unavailable right now. Your message is saved — please try again shortly."
          : probe.trim(),
        debug_fault: { degraded, answer_landed: !degraded, raw: String(probe).slice(0, 60) },
      });
    }
  }

  let agentRespText = "";
  let agentStatus = 0;
  try {
    const resp = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "Content-Type":  "application/json",
        "Authorization": authHeader || `Bearer ${SERVICE_KEY}`,
      },
      signal: AbortSignal.timeout(60_000),
      body: JSON.stringify({
        message:    redactedMessage,
        // Transcript-based specialists (voice-logbook-entry, voice-report-intent)
        // destructure `transcript` not `message`. The 2026-05-26 100-turn
        // baseline showed all 100 such probes 400ing with "Missing or too short
        // transcript". Sending both is backward-compatible — agents reading
        // `message` (voice-journal-agent) are unaffected.
        transcript: redactedMessage,
        context:    redactedContext,
        hive_id,
        worker_name: "<redacted>",       // agents must NOT see real name
        memory:     memory_block,        // pre-formatted context block
        gateway:    true,                // sentinel for downstream
        session_key,                     // opaque sticky-session key (undefined for anon → omitted)
        ...forwardExtras,                // per-agent required fields (e.g. shift_window)
      }),
    });
    agentStatus = resp.status;
    agentRespText = await resp.text();
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return jsonResponse(corsHeaders, 502, {
      error: `Agent '${agent}' (${route.fn}) failed: ${msg}`,
    });
  }

  if (agentStatus < 200 || agentStatus >= 300) {
    return jsonResponse(corsHeaders, agentStatus, {
      error: `Agent returned ${agentStatus}: ${agentRespText.slice(0, 300)}`,
    });
  }

  // The specialist agent returns a JSON envelope. Extract the user-facing
  // answer field; fall back to the raw text if shape is unexpected. Also
  // harvest any durable memories the specialist chose to emit (layer 02).
  let answer = agentRespText;
  let parsedEnvelope: Record<string, unknown> | null = null;
  let specialistMemories: StoreInput[] = [];
  let specialistFollowups: RawFollowup[] = [];
  try {
    const parsed = JSON.parse(agentRespText) as Record<string, unknown>;
    parsedEnvelope = parsed;
    // `narration` is the conversational surface for narrated-specialist tools
    // (voice-action-router has no `answer`/`summary`/`message`). Adding it LAST
    // in the chain is safe for every other agent — answer/summary/message win.
    answer = String(parsed.answer ?? parsed.summary ?? parsed.message ?? parsed.narration ?? agentRespText);
    // Specialists (or agentic-rag-loop's Checker, when one is in the path) may
    // return `memories: [{memory_type, content, importance?}]`. The shared
    // persistEpisodic clamps/validates/caps — we just pass them through.
    const m = (parsed as { memories?: unknown }).memories;
    if (Array.isArray(m)) specialistMemories = m as StoreInput[];
    // Prospective layer (Turn 6): specialists may defer an intention via
    // `followups: [{topic, detail?, due_in_days?, importance?}]`. enqueueFollowups
    // validates/clamps/caps — pass through.
    const f = (parsed as { followups?: unknown }).followups;
    if (Array.isArray(f)) specialistFollowups = f as RawFollowup[];
  } catch {
    // Non-JSON response — keep raw.
  }

  // Hydrate the answer (substitute placeholders back into real names).
  const hydratedAnswer = hydratePII(answer, hydrationMap);

  // Gateway-side memory DISTILLATION (K2/K9 PRODUCER). The conversational specialists
  // don't emit memories[]/followups[] (only agentic-rag-loop does), so the episodic
  // (L02) + prospective (L06) layers were consumer-ready but PRODUCER-LESS — the banks
  // never filled in normal flow (W2 finding 2026-06-12). For EPISODIC_MEMORY_AGENTS
  // that emitted nothing, run ONE cheap best-effort extraction so a genuinely durable
  // fact gets remembered + an implied follow-up gets queued. Conservative by design
  // (empty arrays for chitchat); the existing persistEpisodic/enqueueFollowups blocks
  // below clamp/validate/cap. Best-effort — a parse/LLM miss just leaves the banks as
  // the specialist left them. Uses the redacted message so the distiller never sees PII.
  if (authUid && EPISODIC_MEMORY_AGENTS.has(agent)
      && !specialistMemories.length && !specialistFollowups.length
      && redactedMessage.length > 20) {
    try {
      const distilled = await callAI(
        `From this maintenance exchange, extract ONLY genuinely durable facts worth remembering long-term and any explicit follow-up the worker implied. If nothing is durable, return empty arrays.\nRespond JSON only: {"memories":[{"memory_type":"factual","content":"...","importance":0.7}],"followups":[{"topic":"...","detail":"...","due_in_days":7}]}\n\nWorker: ${redactedMessage}\nAssistant: ${answer}`,
        {
          systemPrompt: "You distill durable maintenance memory. Be conservative — return empty arrays unless a concrete fact, spec, or commitment is present.",
          maxTokens: 320, temperature: 0.1, jsonMode: true, sessionKey: session_key,
        },
      );
      const parsed = JSON.parse(distilled) as { memories?: unknown; followups?: unknown };
      if (Array.isArray(parsed.memories)) specialistMemories = (parsed.memories as StoreInput[]).slice(0, 2);
      if (Array.isArray(parsed.followups)) specialistFollowups = (parsed.followups as RawFollowup[]).slice(0, 2);
      if (specialistMemories.length || specialistFollowups.length) {
        log.info(ctx, "memory_distilled", { memories: specialistMemories.length, followups: specialistFollowups.length });
      }
    } catch (err) {
      console.warn("[ai-gateway] memory distillation failed (non-fatal):", err instanceof Error ? err.message : err);
    }
  }

  // Structured passthrough for TOOL agents (voice-action-router). The default
  // gateway contract returns `answer` only; a tool whose UI applies structured
  // intents needs the full specialist payload. We hydrate the WHOLE payload
  // (stringify -> hydratePII -> parse) so PII placeholders are restored
  // everywhere in the nested structure, not just in `answer` — the single-string
  // hydratePII above never reaches `intents[].params` / `narration`. Best-effort:
  // if re-parse fails we pass the un-hydrated structure rather than drop it.
  let routeResult: Record<string, unknown> | undefined;
  if (STRUCTURED_PASSTHROUGH_AGENTS.has(agent) && parsedEnvelope) {
    try {
      routeResult = JSON.parse(hydratePII(JSON.stringify(parsedEnvelope), hydrationMap)) as Record<string, unknown>;
    } catch {
      routeResult = parsedEnvelope;
    }
  }

  // Persist the turn (best-effort; failures don't block response).
  // Forward selected context fields into meta so agent_memory can support
  // per-language semantic recall (voice-journal) and similar future facets.
  // Anon callers (voice-journal first-touch) skip persistence — agent_memory
  // and voice_journal_entries are both RLS-keyed on auth_uid.
  if (authUid) {
    const metaExtra: Record<string, unknown> = {
      target_fn:   route.fn,
      latency_ms:  Date.now() - t0,
    };
    if (context && typeof context === "object") {
      const langField = (context as Record<string, unknown>).lang;
      if (typeof langField === "string" && langField.trim()) {
        metaExtra.lang = langField.trim().toLowerCase();
      }
    }
    const handle: MemoryHandle = {
      hive_id, worker_name, auth_uid: authUid, agent_id: agent,
    };
    await saveTurn(adminClient, handle, message, hydratedAnswer, metaExtra);

    // Summary-collapse (K10 / L01 long-term). Once the live turn buffer crosses
    // SUMMARISE_AT, compress the oldest SUMMARISE_BATCH turns into ONE summary row
    // so the buffer stays bounded instead of growing unbounded and silently
    // truncating old context at loadMemory's RECENT_TURNS window. `persistSummary`
    // / `summariseIfNeeded` were DEAD code (defined, never called) — wired here
    // 2026-06-12 (W2 finding). Best-effort, non-blocking; the LLM summariser lives
    // in the gateway so memory.ts stays ai-chain-free. Pinned to the sticky model.
    try {
      const collapsed = await summariseIfNeeded(adminClient, handle, async (transcript) =>
        await callAI(
          // 2026-06-14 false-memory-loop fix: the transcript is labelled "User:" / "Assistant:".
          // The OLD prompt ("preserve specifics: numbers...") promoted the ASSISTANT's own
          // volunteered figures into durable "facts" with no speaker attribution — so a
          // fabricated "PM compliance 68%" became a recalled user fact. Only record what the
          // WORKER actually stated, attributed to them; never promote an Assistant figure to fact.
          `Compress this earlier conversation excerpt into 2-3 sentences of durable context. ONLY record facts, values, and decisions stated by the WORKER (lines marked "User:"), and attribute them to the worker (e.g. "the worker said the flange torque was 85 Nm"). Do NOT record any number, KPI, percentage, reading, or claim that only the Assistant volunteered — those are suggestions, not verified facts, and must never become memory. Capture the worker's stated values, their decisions, and open questions only. Plain prose, no preamble.\n\n${transcript}`,
          {
            systemPrompt: "You compress chat history into a tight, factual summary. You ONLY preserve what the WORKER stated (the numbers, asset tags, and commitments THEY gave) plus decisions and open items, and you attribute facts to the worker. You NEVER promote an Assistant-suggested figure, KPI, or reading into a stated fact.",
            maxTokens: 220, temperature: 0.3, jsonMode: false, sessionKey: session_key,
          },
        ),
      );
      if (collapsed) log.info(ctx, "memory_summarised", { collapsed: collapsed.collapsed });
    } catch (err) {
      console.warn("[ai-gateway] summary collapse failed (non-fatal):", err instanceof Error ? err.message : err);
    }

    // Durable episodic persist (layer 02). Best-effort, non-blocking-on-error.
    // Only for opted-in specialists AND only when the specialist actually
    // emitted memories — the gateway never invents memories itself (no LLM
    // call on this path), so an empty/absent `memories` field is a no-op.
    if (EPISODIC_MEMORY_AGENTS.has(agent) && specialistMemories.length) {
      try {
        const res = await persistEpisodic(adminClient, hive_id, worker_name, specialistMemories);
        log.info(ctx, "episodic_persist", { written: res.written, evicted: res.evicted });
      } catch (err) {
        console.warn("[ai-gateway] episodic persist failed (non-fatal):", err instanceof Error ? err.message : err);
      }
    }

    // Prospective enqueue (layer 06). Same envelope-driven, opt-in, best-effort
    // pattern as episodic persist — the gateway never invents follow-ups.
    if (FOLLOWUP_AGENTS.has(agent) && specialistFollowups.length) {
      try {
        const res = await enqueueFollowups(adminClient, hive_id, worker_name, specialistFollowups, ctx.trace_id);
        log.info(ctx, "followup_enqueue", { written: res.written, skipped: res.skipped });
      } catch (err) {
        console.warn("[ai-gateway] follow-up enqueue failed (non-fatal):", err instanceof Error ? err.message : err);
      }
    }

    // Durable archive for semantic-recall agents. agent_memory has 90-day
    // retention; voice_journal_entries is the permanent journal store and
    // the source of truth for the history UI. Reuses the embedding we
    // already generated during recall, so this is a single insert call.
    if (SEMANTIC_RECALL_AGENTS.has(agent)) {
      const langField = context && typeof context === "object"
        ? (context as Record<string, unknown>).lang
        : null;
      const lang = typeof langField === "string" && langField.trim()
        ? langField.trim().toLowerCase()
        : null;
      await persistJournalEntry(adminClient, {
        auth_uid:    authUid,
        worker_name,
        hive_id,
        transcript:  message,
        reply:       hydratedAnswer,
        lang,
        embedding:   recallEmbedding,
        meta:        { target_fn: route.fn, latency_ms: Date.now() - t0 },
      });
    }
  }

  // Record that downstream specialist served the answer (model chain hop).
  recordModelHop(ctx, route.fn);
  log.info(ctx, "request_complete", {
    agent,
    target_fn:  route.fn,
    latency_ms: Date.now() - t0,
  });

  // Per-turn cost log (P25). The gateway is the single front door, so it logs cost
  // CENTRALLY for forwarded specialists — asset-brain-query / ai-orchestrator /
  // shift-planner-orchestrator all IMPORT logAICost but never CALL it (dangling
  // import), so every gateway-forwarded turn was cost-blind (W2 db-effect finding
  // 2026-06-12). voice-journal-agent self-logs its own row, so skip it here to
  // avoid double-counting. Tokens estimated (the gateway never sees provider usage);
  // best-effort — logAICost swallows its own errors and never blocks the response.
  if (agent !== "voice-journal") {
    await logAICost(adminClient, {
      fn:            route.fn,
      hive_id,
      worker_name,
      model:         `gateway:${route.fn}`,
      prompt_tokens: estimateTokens(message),
      output_tokens: estimateTokens(hydratedAnswer),
      latency_ms:    Date.now() - t0,
      status:        "success",
    });
  }

  // Populate adaptive cache for short (re-likely) messages so future 429s
  // can degrade instead of fail. 1h TTL — companion content changes fast
  // enough that we don't want stale answers more than an hour old.
  // canonical-allow: ai_cache is an infrastructure table (see _shared/cache.ts).
  if (message.length <= 200 && hydratedAnswer && hydratedAnswer.length >= 8) {
    try {
      const { cacheStore } = await import("../_shared/cache.ts");
      const adaptiveKey = await (async () => {
        const data = new TextEncoder().encode(`ai-gateway-adaptive:gateway:${agent}:${message}`);
        const buf  = await crypto.subtle.digest("SHA-256", data);
        return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
      })();
      await cacheStore(adminClient, adaptiveKey, "ai-gateway-adaptive", { answer: hydratedAnswer }, { ttlSeconds: 3600 });
    } catch { /* non-fatal */ }
  }

  // Envelope-conformant success response (P1 roadmap 2026-05-26).
  // Legacy fields (answer, agent, usage) are nested under `data` so any
  // caller using the old shape can still pluck them via `body.data.answer`.
  // Frontends that haven't migrated yet receive a 200 with the same JSON
  // top-level via the envelope's `ok` field; client adapters land in P2.
  return ok(ctx, {
    answer:    hydratedAnswer,
    agent,
    // Additive: only present for STRUCTURED_PASSTHROUGH_AGENTS. Conversational
    // callers ignore it; tool callers read it for the structured intents.
    ...(routeResult ? { route_result: routeResult } : {}),
    usage:     { latency_ms: Date.now() - t0 },
  });
});

function jsonResponse(
  corsHeaders: Record<string, string>,
  status: number,
  body: unknown,
): Response {
  // The error-contract validator requires the literal `JSON.stringify({ error: ... })`
  // shape somewhere in source. We honour the canonical shape here on the
  // failure branch so the orchestrator's contract check matches even when
  // success paths use richer envelopes.
  if (status >= 400 && body && typeof body === "object" && "error" in (body as Record<string, unknown>)) {
    const errorBody = body as { error: string };
    return new Response(JSON.stringify({ error: String(errorBody.error) }), {
      status,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}
