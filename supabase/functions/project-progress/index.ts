/**
 * project-progress — deterministic project rollup + earned-value + critical path
 *
 * POST /functions/v1/project-progress
 * Body: { project_id: string, hive_id: string }
 *
 * Returns:
 *  {
 *    rollup:        { pct_complete, items_total, items_done, hours_estimated, hours_actual, days_elapsed, days_total },
 *    earned_value:  { pv, ev, ac, sv, cv, spi, cpi, status },        // null if no budget/dates
 *    critical_path: { item_ids, total_days, slack_per_item },
 *    latest_logs:   [{ log_date, reported_by, pct_complete, notes, blockers, acknowledged_by }]
 *  }
 *
 * Standards basis:
 *  - Earned Value: PMI PMBOK 7th ed., AACE 80R-13 (project performance measurement)
 *  - Critical Path Method: PMI PMBOK §6.5.2.2
 *  - Status thresholds (Green/Amber/Red) per AACE EV interpretation guidance
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

/* ── Math helpers ──────────────────────────────────────────────────────── */
type Item = {
  id: string;
  pct_complete: number;
  estimated_hours: number | null;
  actual_hours: number | null;
  predecessors: string[];
  planned_start: string | null;
  planned_end: string | null;
  status: string;
};

function weightedRollup(items: Item[]): number {
  if (!items.length) return 0;
  const totalWeight = items.reduce((s, it) => s + (it.estimated_hours || 1), 0);
  if (totalWeight === 0) {
    // Fallback: simple average if no estimates
    return Math.round(items.reduce((s, it) => s + (it.pct_complete || 0), 0) / items.length);
  }
  const weightedSum = items.reduce(
    (s, it) => s + ((it.pct_complete || 0) * (it.estimated_hours || 1)),
    0,
  );
  return Math.round(weightedSum / totalWeight);
}

function daysBetween(a: string | null, b: string | null): number {
  if (!a || !b) return 0;
  const d1 = new Date(a).getTime();
  const d2 = new Date(b).getTime();
  return Math.max(1, Math.ceil((d2 - d1) / 86400000));
}

/* Critical Path Method (CPM) — forward + backward pass on a DAG of items.
 * Returns the chain of item ids with zero (or near-zero) slack. */
function criticalPath(items: Item[]): { item_ids: string[]; total_days: number; slack: Record<string, number> } {
  const byId: Record<string, Item> = {};
  items.forEach(i => { byId[i.id] = i; });

  const duration = (i: Item) => {
    if (i.planned_start && i.planned_end) return daysBetween(i.planned_start, i.planned_end);
    if (i.estimated_hours) return Math.max(1, Math.ceil(i.estimated_hours / 8)); // 8h workday
    return 1;
  };

  // Topological sort — items with no predecessors first
  const inDegree: Record<string, number> = {};
  items.forEach(i => { inDegree[i.id] = (i.predecessors || []).filter(p => byId[p]).length; });
  const queue: string[] = items.filter(i => inDegree[i.id] === 0).map(i => i.id);
  const order: string[] = [];
  const visited = new Set<string>();
  while (queue.length) {
    const id = queue.shift()!;
    if (visited.has(id)) continue;
    visited.add(id);
    order.push(id);
    items.forEach(child => {
      if ((child.predecessors || []).includes(id)) {
        inDegree[child.id] -= 1;
        if (inDegree[child.id] <= 0) queue.push(child.id);
      }
    });
  }
  // If we couldn't visit everything (cycle), fall back to original order
  if (order.length < items.length) {
    items.forEach(i => { if (!visited.has(i.id)) order.push(i.id); });
  }

  // Forward pass — earliest start / finish
  const ES: Record<string, number> = {};
  const EF: Record<string, number> = {};
  for (const id of order) {
    const item = byId[id];
    const preds = (item.predecessors || []).filter(p => byId[p]);
    ES[id] = preds.length ? Math.max(...preds.map(p => EF[p] || 0)) : 0;
    EF[id] = ES[id] + duration(item);
  }
  const projectFinish = Math.max(0, ...Object.values(EF));

  // Backward pass — latest start / finish
  const LF: Record<string, number> = {};
  const LS: Record<string, number> = {};
  const reverseOrder = [...order].reverse();
  for (const id of reverseOrder) {
    const item = byId[id];
    const successors = items.filter(c => (c.predecessors || []).includes(id)).map(c => c.id);
    LF[id] = successors.length ? Math.min(...successors.map(s => LS[s] || projectFinish)) : projectFinish;
    LS[id] = LF[id] - duration(item);
  }

  // Slack = LS - ES; critical = slack === 0
  const slack: Record<string, number> = {};
  items.forEach(i => { slack[i.id] = (LS[i.id] || 0) - (ES[i.id] || 0); });
  const criticalIds = items
    .filter(i => slack[i.id] === 0)
    .sort((a, b) => (ES[a.id] || 0) - (ES[b.id] || 0))
    .map(i => i.id);

  return { item_ids: criticalIds, total_days: projectFinish, slack };
}

function evStatus(spi: number | null, cpi: number | null): string {
  if (spi === null && cpi === null) return 'unknown';
  const minVal = Math.min(spi ?? 1, cpi ?? 1);
  if (minVal >= 0.95) return 'green';
  if (minVal >= 0.85) return 'amber';
  return 'red';
}

/* ── Handler ────────────────────────────────────────────────────────────── */
serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: getCorsHeaders(req) });
  }
  if (req.method !== 'POST') {
    return errJson('Method not allowed', 405, req);
  }

  let body: { project_id?: string; hive_id?: string };
  try {
    body = await req.json();
  } catch {
    return errJson('Invalid JSON body', 400, req);
  }
  const { project_id, hive_id } = body;
  if (!project_id || !hive_id) {
    return errJson('project_id and hive_id are required', 400, req);
  }

  const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
  const serviceKey  = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
  const db = createClient(supabaseUrl, serviceKey);

  /* ── Load project + items + latest logs in parallel ──────────────── */
  const [projRes, itemsRes, logsRes] = await Promise.all([
    db.from('projects')
      .select('id, hive_id, project_type, status, start_date, end_date, budget_php, created_at')
      .eq('id', project_id)
      .eq('hive_id', hive_id)
      .is('deleted_at', null)
      .maybeSingle(),
    db.from('project_items')
      .select('id, pct_complete, estimated_hours, actual_hours, predecessors, planned_start, planned_end, status')
      .eq('project_id', project_id)
      .eq('hive_id', hive_id)
      .order('sort_order', { ascending: true }),
    db.from('project_progress_logs')
      .select('log_date, reported_by, pct_complete, notes, blockers, acknowledged_by, acknowledged_at')
      .eq('project_id', project_id)
      .eq('hive_id', hive_id)
      .order('log_date', { ascending: false })
      .limit(10),
  ]);

  if (projRes.error || !projRes.data) {
    return errJson('Project not found or not accessible', 404, req);
  }
  const project = projRes.data;
  const items: Item[] = (itemsRes.data || []).map(r => ({
    id: r.id,
    pct_complete: r.pct_complete || 0,
    estimated_hours: r.estimated_hours,
    actual_hours: r.actual_hours,
    predecessors: Array.isArray(r.predecessors) ? r.predecessors : [],
    planned_start: r.planned_start,
    planned_end: r.planned_end,
    status: r.status || 'pending',
  }));

  /* ── Rollup ─────────────────────────────────────────────────────── */
  const pctComplete   = weightedRollup(items);
  const itemsTotal    = items.length;
  const itemsDone     = items.filter(i => i.status === 'done').length;
  const hoursEst      = items.reduce((s, i) => s + (i.estimated_hours || 0), 0);
  const hoursActual   = items.reduce((s, i) => s + (i.actual_hours    || 0), 0);
  const daysElapsed   = project.start_date ? daysBetween(project.start_date, new Date().toISOString()) : 0;
  const daysTotal     = (project.start_date && project.end_date) ? daysBetween(project.start_date, project.end_date) : 0;

  /* ── Earned Value (only when budget + start_date are known) ────────── */
  let earnedValue: any = null;
  if (project.budget_php && project.start_date && project.end_date) {
    const BAC = Number(project.budget_php);                                   // Budget at Completion
    const plannedPct = daysTotal > 0 ? Math.min(1, daysElapsed / daysTotal) : 0;
    const PV  = BAC * plannedPct;                                             // Planned Value
    const EV  = BAC * (pctComplete / 100);                                    // Earned Value
    // Approximation: AC = labor_rate × hoursActual + linked parts cost.
    // For v1 we proxy AC from hoursActual at a hive-level default rate (₱200/hr).
    // Extension: pull worker rates from worker_profiles when that column exists.
    const AC  = hoursActual * 200;                                            // Actual Cost (proxy)
    const SV  = EV - PV;                                                      // Schedule Variance
    const CV  = EV - AC;                                                      // Cost Variance
    const SPI = PV > 0 ? EV / PV : null;                                      // Schedule Performance Index
    const CPI = AC > 0 ? EV / AC : null;                                      // Cost Performance Index
    earnedValue = {
      bac: Math.round(BAC),
      pv:  Math.round(PV),
      ev:  Math.round(EV),
      ac:  Math.round(AC),
      sv:  Math.round(SV),
      cv:  Math.round(CV),
      spi: SPI ? Number(SPI.toFixed(2)) : null,
      cpi: CPI ? Number(CPI.toFixed(2)) : null,
      status: evStatus(SPI, CPI),
    };
  }

  /* ── Critical path (only meaningful when items have predecessors / dates) */
  let cp: any = { item_ids: [], total_days: 0, slack: {} };
  if (items.length > 0) {
    cp = criticalPath(items);
  }

  return json({
    project_id,
    rollup: {
      pct_complete:    pctComplete,
      items_total:     itemsTotal,
      items_done:      itemsDone,
      hours_estimated: hoursEst,
      hours_actual:    hoursActual,
      days_elapsed:    daysElapsed,
      days_total:      daysTotal,
    },
    earned_value:  earnedValue,
    critical_path: { item_ids: cp.item_ids, total_days: cp.total_days, slack_per_item: cp.slack },
    latest_logs:   logsRes.data || [],
  }, 200, req);
});
