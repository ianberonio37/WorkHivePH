// ─────────────────────────────────────────────────────────────────────────────
// onboarding.js — Phase 3.3 of STRATEGIC_ROADMAP (in-product onboarding paths)
//
// Two role-specific onboarding paths the worker and supervisor see on hive.html
// the first time they land. Each step has a deterministic completion detector
// (a DB query OR a localStorage flag) so progress is reflected the moment a
// worker actually does the thing — not when they tick a self-report box.
//
// Worker path (5 steps):
//   1. Signed in              — auth.session exists
//   2. Joined a hive          — hive_members row
//   3. Logged first entry     — 1+ logbook row (worker_name match)
//   4. Uploaded a photo       — 1+ logbook row with photo
//   5. Completed a PM task    — 1+ pm_completions row
//
// Supervisor path (7 steps):
//   1. Signed in
//   2. Created or joined as supervisor
//   3. Approved a member      — 1+ approve_item audit_log row
//   4. Registered an asset    — 1+ asset_nodes row with status='approved'
//   5. Set a PM template      — 1+ pm_assets row
//   6. Reviewed the audit log — localStorage 'wh_onb_audit_visited'
//   7. Approved a daily brief — 1+ amc_briefings row with status='approved'
//
// API:
//   await whOnboardingProgress(db, { hiveId, workerName, role });
//   -> { role, total, completed, steps: [{ id, label, done }] }
//
//   whRenderOnboardingCard(containerSelector, progress);
//   -> renders the stepper card (idempotent; replaces existing content)
//
// The card is supervisor-visible OR worker-visible (each shows their own path).
// Hides itself when ALL steps are complete (avoid permanent clutter).
//
// Skills consulted:
//   community (start at "first concrete action", not "watch a tutorial")
//   frontend (deterministic detectors > self-report; stepper UI > checklist)
//   analytics-engineer (each step detector is a single, narrow .count() query)
//   designer (no badges for trivial steps; reward real work doctrine)
// ─────────────────────────────────────────────────────────────────────────────

(function () {
  if (typeof window === 'undefined') return;
  if (window.whOnboardingProgress) return;

  const WORKER_STEPS = [
    { id: 'signed_in',        label: 'Sign in',                    check: ctx => !!ctx.workerName },
    { id: 'joined_hive',      label: 'Join a hive',                check: ctx => !!ctx.hiveId },
    { id: 'first_log',        label: 'Log your first entry',       check: async ctx => await _has(ctx.db, 'logbook', { hive_id: ctx.hiveId, worker_name: ctx.workerName }) },
    { id: 'first_photo',      label: 'Upload a photo',             check: async ctx => await _has(ctx.db, 'logbook', { hive_id: ctx.hiveId, worker_name: ctx.workerName }, 'photo', 'not.is', null) },
    { id: 'first_pm',         label: 'Complete a PM task',         check: async ctx => await _has(ctx.db, 'pm_completions', { hive_id: ctx.hiveId, worker_name: ctx.workerName }) },
  ];

  const SUPERVISOR_STEPS = [
    { id: 'signed_in',        label: 'Sign in',                    check: ctx => !!ctx.workerName },
    { id: 'created_hive',     label: 'Lead a hive',                check: ctx => !!ctx.hiveId && ctx.role === 'supervisor' },
    { id: 'approved_member',  label: 'Approve a member',           check: async ctx => await _has(ctx.db, 'hive_audit_log', { hive_id: ctx.hiveId, action: 'approve_item' }) },
    { id: 'registered_asset', label: 'Register an asset',          check: async ctx => await _has(ctx.db, 'asset_nodes', { hive_id: ctx.hiveId, status: 'approved' }) },
    { id: 'set_pm',           label: 'Set a PM template',          check: async ctx => await _has(ctx.db, 'pm_assets', { hive_id: ctx.hiveId }) },
    { id: 'reviewed_audit',   label: 'Review the audit log',       check: ctx => _flag('wh_onb_audit_visited') },
    { id: 'approved_brief',   label: 'Approve a daily brief',      check: async ctx => await _has(ctx.db, 'amc_briefings', { hive_id: ctx.hiveId, status: 'approved' }) },
  ];

  async function _has(db, table, eqMap, col, op, val) {
    try {
      let q = db.from(table).select('id', { count: 'exact', head: true });
      for (const [k, v] of Object.entries(eqMap || {})) {
        if (v == null) continue;
        q = q.eq(k, v);
      }
      // Optional extra filter (e.g. photo is not null).
      if (col && op === 'not.is') q = q.not(col, 'is', val);
      const { count } = await q;
      return (count || 0) > 0;
    } catch (_) {
      return false;
    }
  }
  function _flag(key) {
    try { return !!localStorage.getItem(key); } catch (_) { return false; }
  }

  async function whOnboardingProgress(db, opts) {
    opts = opts || {};
    const role = opts.role === 'supervisor' ? 'supervisor' : 'worker';
    const ctx  = { db, hiveId: opts.hiveId, workerName: opts.workerName, role };
    const steps = role === 'supervisor' ? SUPERVISOR_STEPS : WORKER_STEPS;
    const results = [];
    for (const s of steps) {
      let done = false;
      try {
        const v = typeof s.check === 'function' ? s.check(ctx) : false;
        done = (v && typeof v.then === 'function') ? !!(await v) : !!v;
      } catch (_) { done = false; }
      results.push({ id: s.id, label: s.label, done });
    }
    const completed = results.filter(r => r.done).length;
    return { role, total: steps.length, completed, steps: results };
  }

  function whRenderOnboardingCard(selector, progress) {
    const host = typeof selector === 'string' ? document.querySelector(selector) : selector;
    if (!host) return;
    if (!progress || progress.completed >= progress.total) {
      host.classList.add('hidden');
      host.innerHTML = '';
      return;
    }
    host.classList.remove('hidden');
    const pct = Math.round(100 * progress.completed / progress.total);
    const title = progress.role === 'supervisor'
      ? 'Supervisor setup'
      : 'Get started';
    const subtitle = `${progress.completed} of ${progress.total} steps complete`;

    const items = progress.steps.map(s => `
      <li style="display:flex; align-items:center; gap:8px; padding:6px 0; font-size:11.5px; color:${s.done ? 'rgba(255,255,255,0.55)' : 'rgba(255,255,255,0.85)'};">
        <span aria-hidden="true" style="display:inline-flex; align-items:center; justify-content:center; width:18px; height:18px; border-radius:50%; flex-shrink:0;
          background:${s.done ? 'rgba(74,222,128,0.18)' : 'rgba(255,255,255,0.06)'};
          color:${s.done ? '#4ade80' : 'rgba(255,255,255,0.45)'};
          border:1px solid ${s.done ? 'rgba(74,222,128,0.4)' : 'rgba(255,255,255,0.08)'};
          font-weight:800; font-size:11px;">${s.done ? '✓' : '·'}</span>
        <span style="${s.done ? 'text-decoration:line-through;' : ''}">${_esc(s.label)}</span>
      </li>
    `).join('');

    host.innerHTML = `
      <div style="padding:14px 16px;">
        <div style="display:flex; align-items:center; justify-content:space-between; gap:8px; flex-wrap:wrap;">
          <div style="display:flex; align-items:center; gap:10px;">
            <span style="display:inline-flex; align-items:center; gap:6px; padding:4px 10px; border-radius:999px; font-size:10px; font-weight:800; letter-spacing:0.06em; text-transform:uppercase; background:rgba(247,162,27,0.18); color:#F7A21B;">${_esc(title)}</span>
            <span style="font-size:11px; color:rgba(255,255,255,0.55);">${_esc(subtitle)}</span>
          </div>
          <span style="font-size:14px; font-weight:800; color:#F7A21B;">${pct}%</span>
        </div>
        <div style="height:5px; background:rgba(255,255,255,0.06); border-radius:3px; margin:8px 0; overflow:hidden;">
          <div style="height:100%; width:${pct}%; background:linear-gradient(90deg,#F7A21B,#FDB94A); border-radius:3px; transition:width 0.4s ease;"></div>
        </div>
        <ul style="list-style:none; padding:0; margin:6px 0 0;">${items}</ul>
      </div>
    `;
  }

  function _esc(s) {
    return String(s || '').replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[c]);
  }

  window.whOnboardingProgress    = whOnboardingProgress;
  window.whRenderOnboardingCard  = whRenderOnboardingCard;
})();
