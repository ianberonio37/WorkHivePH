/**
 * project-progress — thin proxy to python-api/projects/
 *
 * POST /functions/v1/project-progress
 * Body: { project_id: string, hive_id: string }
 *
 * Flow:
 *   1. Verify project belongs to hive (no leakage between hives).
 *   2. Load project + items + links + recent progress logs in parallel.
 *   3. POST those rows to ${PYTHON_API_URL}/project/progress.
 *   4. Return the Python response.
 *
 * Math (rollup, EVM, CPM via networkx, EAC forecast) lives in:
 *   python-api/projects/{descriptive,diagnostic,predictive,prescriptive}.py
 *
 * If PYTHON_API_URL is not configured (e.g. local Tester without the API
 * running), the endpoint returns a graceful 'unavailable' payload and the
 * front-end falls back to its client-side rollup.
 *
 * Standards: PMBOK 7th ed., AACE 17R-97, IDCON 6-Phase, ISO 21500.
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

/* ── CORS ──────────────────────────────────────────────────────────────── */
function getCorsHeaders(req: Request): Record<string, string> {
  const origin = req.headers.get('origin') || '';
  const allowed = [
    'https://workhiveph.com',
    'https://www.workhiveph.com',
    'http://localhost',
    'http://127.0.0.1:5000',
    'null', // file:// local testing
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

/* ── Call the Python Project API ─────────────────────────────────────── */
async function callPythonProject(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const PYTHON_URL = Deno.env.get('PYTHON_API_URL');
  if (!PYTHON_URL) {
    return {
      error: 'Python Project API not configured.',
      hint: 'Set PYTHON_API_URL in Supabase Edge Function secrets.',
      _unavailable: true,
    };
  }
  const res = await fetch(`${PYTHON_URL}/project/progress`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(90000),  // 90s — Render cold start can take 50s+
  });
  if (res.status === 404) {
    return { error: 'Python project endpoint not yet deployed.', _unavailable: true };
  }
  if (!res.ok) {
    const body = await res.text().catch(() => 'no body');
    throw new Error(`Python API ${res.status}: ${body}`);
  }
  return await res.json();
}

/* ── Handler ────────────────────────────────────────────────────────────── */
serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: getCorsHeaders(req) });
  }
  if (req.method !== 'POST') {
    return errJson('Method not allowed', 405, req);
  }

  let body: { project_id?: string; hive_id?: string; labor_rate_php_per_hour?: number };
  try {
    body = await req.json();
  } catch {
    return errJson('Invalid JSON body', 400, req);
  }
  const { project_id, hive_id, labor_rate_php_per_hour } = body;
  if (!project_id || !hive_id) {
    return errJson('project_id and hive_id are required', 400, req);
  }

  const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
  const serviceKey  = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
  const db = createClient(supabaseUrl, serviceKey);

  /* ── Load project + items + links + logs in parallel ───────────────── */
  const [projRes, itemsRes, linksRes, logsRes] = await Promise.all([
    db.from('projects')
      .select('id, hive_id, project_type, status, start_date, end_date, budget_php, created_at')
      .eq('id', project_id)
      .eq('hive_id', hive_id)
      .is('deleted_at', null)
      .maybeSingle(),
    db.from('project_items')
      .select('id, title, status, pct_complete, estimated_hours, actual_hours, predecessors, planned_start, planned_end, owner_name, notes, sort_order')
      .eq('project_id', project_id)
      .eq('hive_id', hive_id)
      .order('sort_order', { ascending: true }),
    db.from('project_links')
      .select('id, link_type, link_id, label')
      .eq('project_id', project_id)
      .eq('hive_id', hive_id),
    db.from('project_progress_logs')
      .select('log_date, reported_by, pct_complete, hours_worked, notes, blockers, acknowledged_by, acknowledged_at')
      .eq('project_id', project_id)
      .eq('hive_id', hive_id)
      .order('log_date', { ascending: false })
      .limit(30),
  ]);

  if (projRes.error || !projRes.data) {
    return errJson('Project not found or not accessible', 404, req);
  }

  /* ── Forward to Python ──────────────────────────────────────────────── */
  try {
    const pythonPayload = {
      project: projRes.data,
      items:   itemsRes.data || [],
      links:   linksRes.data || [],
      logs:    logsRes.data  || [],
      labor_rate_php_per_hour: labor_rate_php_per_hour ?? null,
    };
    const result = await callPythonProject(pythonPayload);
    // Tag the project_id for round-trip safety
    if (typeof result === 'object' && result !== null) {
      (result as Record<string, unknown>).project_id = project_id;
    }
    return json(result, 200, req);
  } catch (e) {
    return errJson(`Backend error: ${(e as Error).message}`, 502, req);
  }
});
