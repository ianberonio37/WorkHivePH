/**
 * project-orchestrator — AI tasks for Project Manager
 *
 * POST /functions/v1/project-orchestrator
 * Body: {
 *   phase: 'narrative' | 'intent' | 'lessons_draft',
 *   project_id?: string,        // required for narrative + lessons_draft
 *   hive_id?: string,           // required for narrative + lessons_draft
 *   transcript?: string,        // required for intent
 * }
 *
 * Phases (mirrors analytics-orchestrator pattern):
 *   narrative      — Generates handover narrative (hero finding + executive
 *                    summary + lessons synthesis) for project-report.html.
 *                    Strict-only mode: refuses to invent values.
 *   intent         — Parses a free-text transcript ("Plan a 3-day pump
 *                    overhaul on PUMP-201 starting Monday") into a structured
 *                    wizard payload. Mirrors voice-report-intent pattern.
 *   lessons_draft  — Reads progress logs and drafts a lessons-learned text.
 *                    Worker can edit + save in Project Manager.
 *
 * AI infrastructure: uses _shared/ai-chain.ts (same multi-provider fallback
 * chain as analytics-orchestrator). All output text is tagged
 * `_ai_generated: true` by the caller for audit-trail purposes.
 *
 * Standards: PMBOK 7th ed., AACE 17R-97, IDCON 6-Phase, ISO 21500.
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { logRequestStart } from "../_shared/logger.ts";
// Pillar I (Gateway Spine): verify hive membership before service-role reads.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";

// contract-allow: project write coordinator
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { callAI } from '../_shared/ai-chain.ts';
// Persona Contract: narrated-specialist mode — each AI phase (narrative,
// intent, lessons) gains a `narration` field in the worker's persona voice.
// See WORKHIVE_PERSONA_CONTRACT.md.
import { clampPersona, buildPersonaBlock } from '../_shared/persona.ts';
import { loadMemory, saveTurn, formatMemoryContext } from "../_shared/memory.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
import { checkAIRateLimit, rateLimitedResponse } from '../_shared/rate-limit.ts';
import { getCorsHeaders } from '../_shared/cors.ts';

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

/* CORS handled by _shared/cors.ts (security skill rule -- 2026-05-18).
   Shared helper also matches http://127.0.0.1:* via its localhost check. */

function json(data: unknown, status: number, req: Request) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...getCorsHeaders(req) },
  });
}

function errJson(error: string, status: number, req: Request) {
  return new Response(JSON.stringify({ error: error }), {
    status,
    headers: { 'Content-Type': 'application/json', ...getCorsHeaders(req) },
  });
}

/* ── Phase: narrative ───────────────────────────────────────────────── */
async function runNarrative(
  db: ReturnType<typeof createClient>,
  project_id: string,
  hive_id: string,
  persona?: unknown,
): Promise<Record<string, unknown>> {
  const [projRes, itemsRes, logsRes] = await Promise.all([
    db.from('v_project_truth').select('*, id:project_id, end_date:target_end_date').eq('project_id', project_id).eq('hive_id', hive_id).maybeSingle(),
    db.from('v_project_items_truth').select('id, title, status, pct_complete, estimated_hours, actual_hours, planned_end, owner_name, notes')
      .eq('project_id', project_id).eq('hive_id', hive_id).order('sort_order'),
    db.from('v_project_progress_truth').select('log_date, reported_by, pct_complete, hours_worked, notes, blockers')
      .eq('project_id', project_id).eq('hive_id', hive_id).order('log_date', { ascending: false }).limit(20),
  ]);
  if (projRes.error || !projRes.data) {
    return { _unavailable: true, reason: 'Project not found' };
  }
  const project = projRes.data;
  const items   = itemsRes.data || [];
  const logs    = logsRes.data  || [];

  // Compute light rollup so the AI has the numbers it needs.
  const totalW = items.reduce((s, i) => s + ((i as Record<string, number>).estimated_hours || 1), 0) || 1;
  const pct = items.length
    ? Math.round(items.reduce((s, i) => s + (((i as Record<string, number>).pct_complete || 0) * ((i as Record<string, number>).estimated_hours || 1)), 0) / totalW)
    : 0;
  const itemsDone   = items.filter((i: Record<string, unknown>) => i.status === 'done').length;
  const blocked     = items.filter((i: Record<string, unknown>) => i.status === 'blocked').length;
  const recentBlockers = logs.filter((l: Record<string, unknown>) => ((l.blockers as string) || '').trim());

  const factPack = {
    code:         project.project_code,
    name:         project.name,
    type:         project.project_type,
    status:       project.status,
    pct_complete: pct,
    items_total:  items.length,
    items_done:   itemsDone,
    items_blocked: blocked,
    start_date:   project.start_date,
    end_date:     project.end_date,
    budget_php:   project.budget_php,
    owner:        project.owner_name,
    description:  project.description,
    blocked_titles: items.filter((i: Record<string, unknown>) => i.status === 'blocked').map((i: Record<string, string>) => i.title).slice(0, 5),
    pending_titles: items.filter((i: Record<string, unknown>) => i.status === 'pending').map((i: Record<string, string>) => i.title).slice(0, 5),
    in_progress_titles: items.filter((i: Record<string, unknown>) => i.status === 'in_progress').map((i: Record<string, string>) => i.title).slice(0, 3),
    next_pending_item: items.filter((i: Record<string, unknown>) => i.status === 'pending').map((i: Record<string, string>) => i.title)[0] || null,
    status_inconsistency: project.status === 'complete' && pct < 100
      ? `Project is marked 'complete' but ${items.length - itemsDone} of ${items.length} items are still pending — the supervisor should either close those items or revert the project status.`
      : null,
    recent_blocker_count: recentBlockers.length,
    recent_blocker_examples: recentBlockers.slice(0, 3).map((l: Record<string, string>) => l.blockers),
  };

  const systemPrompt = `You write strict-only project narratives for industrial maintenance handover packets in the Philippines. You receive a JSON fact pack and MUST produce three short sections that quote SPECIFIC facts. Never invent values, never reference data not present in the facts. Generic boilerplate is REJECTED.

Mandatory content rules. Your narrative will be considered FAILED if missing any of these:
1. hero_finding MUST quote the percentage AND the items_done/items_total fraction (e.g. "61% complete with 4 of 7 scope items closed").
2. executive_summary MUST mention progress %, hours_actual vs hours_estimated if both are non-zero, AND name a specific blocker verbatim if recent_blocker_count > 0. If next_pending_item is set, end with "Next: <next_pending_item>".
3. If status_inconsistency is non-null, mention it as a sign-off readiness flag in the executive_summary.
4. lessons_synthesis must paraphrase the recurring theme from recent_blocker_examples, or omit if no blockers.

Format rules:
1. Third person, present tense, plain industrial English. No emojis. No marketing language. No hedging ("might", "perhaps", "suggests").
2. If a fact is null or missing, OMIT that sentence. Do not say "unknown" or "TBD".
3. Philippine peso ₱ for any currency. Round to whole pesos.
4. Output STRICT JSON only. No prose outside the JSON.

Output schema:
{
  "hero_finding":        "string. One sentence. Must include % and items_done/total",
  "executive_summary":   "string. 2-4 sentences. Must include progress %, blocker quote if any, next item",
  "lessons_synthesis":   "string. 1-2 sentence pattern from blockers; null if no blockers",
  "narration":           "string. 1-2 sentence spoken summary in your persona's voice; quote the progress % verbatim"
}`;

  const userPrompt = `FACT PACK (the only source of truth):
${JSON.stringify(factPack, null, 2)}

Generate the JSON narrative.`;

  // Persona Contract: narrated-specialist — prepend persona so the model also
  // emits a `narration` field in the worker's voice. One chain call, additive.
  const personaKey = clampPersona(persona);
  const composedSystem = buildPersonaBlock(personaKey, 'narrated-specialist') + '\n\n' + systemPrompt;

  let aiResponse: string;
  try {
    aiResponse = await callAI(userPrompt, { systemPrompt: composedSystem, temperature: 0.05, maxTokens: 800, jsonMode: true });
  } catch (e) {
    return { _unavailable: true, reason: `AI providers all failed: ${(e as Error).message}` };
  }

  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(aiResponse);
  } catch {
    return { _unavailable: true, reason: 'AI returned non-JSON', raw: aiResponse.slice(0, 200) };
  }
  return {
    hero_finding:      parsed.hero_finding || null,
    executive_summary: parsed.executive_summary || null,
    lessons_synthesis: parsed.lessons_synthesis || null,
    narration:         String(parsed.narration || '').trim().slice(0, 280) || null,
    facts_used:        factPack,
    _ai_generated:     true,
    _ai_at:            new Date().toISOString(),
  };
}

/* ── Phase: intent ──────────────────────────────────────────────────── */
async function runIntent(transcript: string, persona?: unknown): Promise<Record<string, unknown>> {
  // Security: cap transcript length before passing to the LLM so a long
  // dictated prompt can't override the system prompt above. 500 chars
  // matches the canonical cap used in voice-logbook-entry +
  // voice-report-intent (mined by security_voice_transcript_length_cap).
  transcript = (transcript || '').trim().slice(0, 500);
  const systemPrompt = `You convert a project-creation transcript from a Philippine maintenance worker into a strict JSON wizard payload for the WorkHive Project Manager. The user typed or spoke a sentence describing a project they want to create.

Rules:
1. Map verb cues to project_type:
   - "shutdown", "turnaround", "outage" → shutdown
   - "capex", "install", "retrofit", "replace equipment" → capex
   - "contractor", "vendor", "outside firm", "subcontract" → contractor
   - everything else (single piece of work, fix, bundle WOs) → workorder
2. Map common templates:
   - pump overhaul / centrifugal pump → pump_overhaul (shutdown)
   - boiler annual / boiler inspection → boiler_annual (shutdown)
   - electrical substation → electrical_substation (shutdown)
   - heat exchanger cleaning → heat_exchanger_clean (shutdown)
   - capex with FEL gates / capital project → fel_full (capex)
   - equipment replacement → equipment_replace (capex)
   - DCS / PLC upgrade → instrumentation_upgrade (capex)
   - fabrication + install / fab job → fab_install (contractor)
   - OEM repair → oem_repair (contractor)
   - annual service / HVAC service → annual_service (contractor)
   - breakdown bundle / repair bundle → breakdown_bundle (workorder)
   - PM campaign → pm_campaign (workorder)
   - reliability study / RCA / FMEA → reliability_study (workorder)
   - if no match: leave template_id null
3. Parse Philippine date phrases ("starting Monday", "next week", "tomorrow") relative to today (${new Date().toISOString().slice(0, 10)}). Output ISO YYYY-MM-DD.
4. Asset tag like "PUMP-201" or "BLR-001" → put in asset_tag field. Do NOT put in name.
5. Output STRICT JSON only.

Output schema:
{
  "project_type": "workorder|shutdown|capex|contractor",
  "template_id":  "<one of the template ids above OR null if no match>",
  "name":         "<short project name; default to template name + asset tag>",
  "start_date":   "YYYY-MM-DD or null",
  "end_date":     "YYYY-MM-DD or null",
  "asset_tag":    "<tag like PUMP-201 or null>",
  "duration_days": <integer or null>,
  "priority":     "low|medium|high|critical",
  "description":  "<paraphrase of transcript intent in 1-2 sentences>",
  "narration":    "<1-2 sentence spoken confirmation in your persona's voice; name the project and start date if set>"
}`;

  const userPrompt = `TRANSCRIPT: "${transcript}"

Output the JSON payload.`;

  const personaKey = clampPersona(persona);
  const composedSystem = buildPersonaBlock(personaKey, 'narrated-specialist') + '\n\n' + systemPrompt;

  let aiResponse: string;
  try {
    aiResponse = await callAI(userPrompt, { systemPrompt: composedSystem, temperature: 0.1, maxTokens: 500, jsonMode: true });
  } catch (e) {
    return { _unavailable: true, reason: `AI providers all failed: ${(e as Error).message}` };
  }
  try {
    const parsed = JSON.parse(aiResponse);
    if (parsed && typeof parsed === 'object' && 'narration' in parsed) {
      (parsed as Record<string, unknown>).narration = String((parsed as Record<string, unknown>).narration || '').trim().slice(0, 280);
    }
    return { ...parsed, _ai_generated: true, _ai_at: new Date().toISOString() };
  } catch {
    return { _unavailable: true, reason: 'AI returned non-JSON', raw: aiResponse.slice(0, 200) };
  }
}

/* ── Phase: lessons_draft ──────────────────────────────────────────── */
async function runLessonsDraft(
  db: ReturnType<typeof createClient>,
  project_id: string,
  hive_id: string,
  persona?: unknown,
): Promise<Record<string, unknown>> {
  const [projRes, logsRes] = await Promise.all([
    db.from('v_project_truth').select('project_code, name, project_type, status').eq('project_id', project_id).eq('hive_id', hive_id).maybeSingle(),
    db.from('v_project_progress_truth').select('log_date, reported_by, pct_complete, hours_worked, notes, blockers')
      .eq('project_id', project_id).eq('hive_id', hive_id).order('log_date', { ascending: false }).limit(40),
  ]);
  if (projRes.error || !projRes.data) {
    return { _unavailable: true, reason: 'Project not found' };
  }
  const logs = logsRes.data || [];
  if (!logs.length) {
    return { _unavailable: true, reason: 'No progress logs to draft from' };
  }

  const project = projRes.data;
  const blockers = logs.filter(l => ((l as Record<string, string>).blockers || '').trim()).map((l: Record<string, string>) => l.blockers);
  const notes    = logs.filter(l => ((l as Record<string, string>).notes || '').trim()).map((l: Record<string, string>) => l.notes);

  const systemPrompt = `You draft "lessons learned" entries for an industrial maintenance project handover packet, written in plain Philippine industrial English. Output 3-6 bullet points using the format below. Never invent details.

Rules:
1. Each bullet starts with one of: "What went well:" / "What to fix:" / "Watch next time:".
2. If the data shows no blockers, focus on what went well.
3. If blockers dominate, focus on what to fix.
4. Skip the bullet if the underlying data is too thin to support it.
5. Output STRICT JSON: { "lessons_text": "string with newline-separated bullets", "narration": "1-2 sentence spoken summary in your persona's voice" }`;

  const userPrompt = `Project: ${project.project_code} - ${project.name}
Status: ${project.status}, type: ${project.project_type}
Number of progress logs: ${logs.length}
Blockers reported (verbatim): ${JSON.stringify(blockers.slice(0, 8))}
Recent notes (verbatim): ${JSON.stringify(notes.slice(0, 8))}

Draft the lessons-learned bullets.`;

  const personaKey = clampPersona(persona);
  const composedSystem = buildPersonaBlock(personaKey, 'narrated-specialist') + '\n\n' + systemPrompt;

  let aiResponse: string;
  try {
    aiResponse = await callAI(userPrompt, { systemPrompt: composedSystem, temperature: 0.25, maxTokens: 500, jsonMode: true });
  } catch (e) {
    return { _unavailable: true, reason: `AI providers all failed: ${(e as Error).message}` };
  }
  try {
    const parsed = JSON.parse(aiResponse);
    return { lessons_text: parsed.lessons_text, narration: String(parsed.narration || '').trim().slice(0, 280) || null, _ai_generated: true, _ai_at: new Date().toISOString() };
  } catch {
    return { _unavailable: true, reason: 'AI returned non-JSON', raw: aiResponse.slice(0, 200) };
  }
}

/* ── Handler ────────────────────────────────────────────────────────── */
serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: getCorsHeaders(req) });
  }
  logRequestStart(req, "project-orchestrator");  // I6 observability (structured request_start line)
  if (req.method !== 'POST') {
    return errJson('Method not allowed', 405, req);
  }

  let body: { phase?: string; project_id?: string; hive_id?: string; transcript?: string; persona?: unknown };
  try { body = await req.json(); }
  catch { return errJson('Invalid JSON body', 400, req); }

  const phase = (body.phase || '').toLowerCase().trim();
  if (!phase) return errJson('phase is required', 400, req);

  const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
  const serviceKey  = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
  const db = createClient(supabaseUrl, serviceKey);

  // Pillar I: narrative/lessons phases read project data scoped by the client
  // hive_id on a service-role client. Verify membership when a hive is claimed
  // (the intent phase is hive-less). Service-role (gateway-forwarded) calls skip.
  if (body.hive_id) {
    const { authUid, isServiceRole } = await resolveIdentity(db, req);
    if (!isServiceRole) {
      const tenancy = await resolveTenancy(db, authUid, body.hive_id);
      if (!tenancy.ok) return errJson(tenancy.message, tenancy.status, req);
    }
  }

  // Rate-gate FIRST per ai-engineer skill — every phase that runs callAI
  // (narrative / intent / brief) is paid; without the gate a button-mash
  // burns budget. body.hive_id is optional for the intent phase, so we
  // pass "" → solo-worker mode (gate is no-op for that case).
  const rl = await checkAIRateLimit(db, body.hive_id || "");
  if (!rl.allowed) return rateLimitedResponse(getCorsHeaders(req));

  try {
    if (phase === 'narrative') {
      if (!body.project_id || !body.hive_id) return errJson('project_id and hive_id are required for narrative', 400, req);
      const out = await runNarrative(db, body.project_id, body.hive_id, body.persona);
      return json(out, 200, req);
    }
    if (phase === 'intent') {
      if (!body.transcript) return errJson('transcript is required for intent', 400, req);
      const out = await runIntent(body.transcript, body.persona);
      return json(out, 200, req);
    }
    if (phase === 'lessons_draft') {
      if (!body.project_id || !body.hive_id) return errJson('project_id and hive_id are required for lessons_draft', 400, req);
      const out = await runLessonsDraft(db, body.project_id, body.hive_id, body.persona);
      return json(out, 200, req);
    }
    return errJson(`Unknown phase '${phase}'. Available: narrative, intent, lessons_draft`, 400, req);
  } catch (e) {
    return errJson(`Backend error: ${(e as Error).message}`, 500, req);
  }
});
