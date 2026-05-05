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
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { callAI } from '../_shared/ai-chain.ts';

/* ── CORS ──────────────────────────────────────────────────────────────── */
function getCorsHeaders(req: Request): Record<string, string> {
  const origin = req.headers.get('origin') || '';
  const allowed = [
    'https://workhiveph.com',
    'https://www.workhiveph.com',
    'http://localhost',
    'http://127.0.0.1:5000',
    'null',
  ];
  const allowedOrigin = allowed.includes(origin) ? origin : allowed[0];
  return {
    'Access-Control-Allow-Origin':  allowedOrigin,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  };
}

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
): Promise<Record<string, unknown>> {
  const [projRes, itemsRes, logsRes] = await Promise.all([
    db.from('projects').select('*').eq('id', project_id).eq('hive_id', hive_id).is('deleted_at', null).maybeSingle(),
    db.from('project_items').select('id, title, status, pct_complete, estimated_hours, actual_hours, planned_end, owner_name, notes')
      .eq('project_id', project_id).eq('hive_id', hive_id).order('sort_order'),
    db.from('project_progress_logs').select('log_date, reported_by, pct_complete, hours_worked, notes, blockers')
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
    recent_blocker_count: recentBlockers.length,
    recent_blocker_examples: recentBlockers.slice(0, 3).map((l: Record<string, string>) => l.blockers),
  };

  const systemPrompt = `You write strict-only project narratives for industrial maintenance handover packets in the Philippines. You receive a JSON fact pack and must produce three short sections — never invent values, never reference data not present in the facts.

Rules:
1. Write in the third person, present tense, plain industrial English.
2. If a fact is null or missing, OMIT that sentence — do not say "unknown" or "TBD".
3. Use Philippine peso ₱ for any currency. Round to whole pesos.
4. No emojis. No marketing language. No hedging ("might", "perhaps").
5. Output STRICT JSON only — no prose outside the JSON.

Output schema:
{
  "hero_finding":        "ONE sentence that summarises where the project stands.",
  "executive_summary":   "2-3 sentences for management — progress, blockers, what's next.",
  "lessons_synthesis":   "1-2 sentence pattern from the progress log blockers (skip if no blockers)."
}`;

  const userPrompt = `FACT PACK (the only source of truth):
${JSON.stringify(factPack, null, 2)}

Generate the JSON narrative.`;

  let aiResponse: string;
  try {
    aiResponse = await callAI(userPrompt, { systemPrompt, temperature: 0.15, maxTokens: 600, jsonMode: true });
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
    facts_used:        factPack,
    _ai_generated:     true,
    _ai_at:            new Date().toISOString(),
  };
}

/* ── Phase: intent ──────────────────────────────────────────────────── */
async function runIntent(transcript: string): Promise<Record<string, unknown>> {
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
  "description":  "<paraphrase of transcript intent in 1-2 sentences>"
}`;

  const userPrompt = `TRANSCRIPT: "${transcript}"

Output the JSON payload.`;

  let aiResponse: string;
  try {
    aiResponse = await callAI(userPrompt, { systemPrompt, temperature: 0.1, maxTokens: 400, jsonMode: true });
  } catch (e) {
    return { _unavailable: true, reason: `AI providers all failed: ${(e as Error).message}` };
  }
  try {
    const parsed = JSON.parse(aiResponse);
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
): Promise<Record<string, unknown>> {
  const [projRes, logsRes] = await Promise.all([
    db.from('projects').select('project_code, name, project_type, status').eq('id', project_id).eq('hive_id', hive_id).is('deleted_at', null).maybeSingle(),
    db.from('project_progress_logs').select('log_date, reported_by, pct_complete, hours_worked, notes, blockers')
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

  const systemPrompt = `You draft "lessons learned" entries for an industrial maintenance project handover packet, written in plain Philippine industrial English. Output 3-6 bullet points using the format below — never invent details.

Rules:
1. Each bullet starts with one of: "What went well:" / "What to fix:" / "Watch next time:".
2. If the data shows no blockers, focus on what went well.
3. If blockers dominate, focus on what to fix.
4. Skip the bullet if the underlying data is too thin to support it.
5. Output STRICT JSON: { "lessons_text": "string with newline-separated bullets" }`;

  const userPrompt = `Project: ${project.project_code} - ${project.name}
Status: ${project.status}, type: ${project.project_type}
Number of progress logs: ${logs.length}
Blockers reported (verbatim): ${JSON.stringify(blockers.slice(0, 8))}
Recent notes (verbatim): ${JSON.stringify(notes.slice(0, 8))}

Draft the lessons-learned bullets.`;

  let aiResponse: string;
  try {
    aiResponse = await callAI(userPrompt, { systemPrompt, temperature: 0.25, maxTokens: 500, jsonMode: true });
  } catch (e) {
    return { _unavailable: true, reason: `AI providers all failed: ${(e as Error).message}` };
  }
  try {
    const parsed = JSON.parse(aiResponse);
    return { lessons_text: parsed.lessons_text, _ai_generated: true, _ai_at: new Date().toISOString() };
  } catch {
    return { _unavailable: true, reason: 'AI returned non-JSON', raw: aiResponse.slice(0, 200) };
  }
}

/* ── Handler ────────────────────────────────────────────────────────── */
serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: getCorsHeaders(req) });
  }
  if (req.method !== 'POST') {
    return errJson('Method not allowed', 405, req);
  }

  let body: { phase?: string; project_id?: string; hive_id?: string; transcript?: string };
  try { body = await req.json(); }
  catch { return errJson('Invalid JSON body', 400, req); }

  const phase = (body.phase || '').toLowerCase().trim();
  if (!phase) return errJson('phase is required', 400, req);

  const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
  const serviceKey  = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
  const db = createClient(supabaseUrl, serviceKey);

  try {
    if (phase === 'narrative') {
      if (!body.project_id || !body.hive_id) return errJson('project_id and hive_id are required for narrative', 400, req);
      const out = await runNarrative(db, body.project_id, body.hive_id);
      return json(out, 200, req);
    }
    if (phase === 'intent') {
      if (!body.transcript) return errJson('transcript is required for intent', 400, req);
      const out = await runIntent(body.transcript);
      return json(out, 200, req);
    }
    if (phase === 'lessons_draft') {
      if (!body.project_id || !body.hive_id) return errJson('project_id and hive_id are required for lessons_draft', 400, req);
      const out = await runLessonsDraft(db, body.project_id, body.hive_id);
      return json(out, 200, req);
    }
    return errJson(`Unknown phase '${phase}'. Available: narrative, intent, lessons_draft`, 400, req);
  } catch (e) {
    return errJson(`Backend error: ${(e as Error).message}`, 500, req);
  }
});
