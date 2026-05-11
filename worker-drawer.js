// worker-drawer.js — clickable worker-name mini-profile drawer.
//
// Closes PRODUCTION_FIXES #15. Pages just include this script + mark
// worker-name nodes with `data-worker-name="<name>"`. Click opens a
// slide-up drawer showing skill level, open jobs count, recent logbook
// activity, and low-stock items for that worker.
//
// The drawer self-injects its DOM + CSS once on first run. No per-page
// markup required beyond the data-attribute.
//
// Assumes `db` (the Supabase client) is globally available — every
// hive-scoped page already creates it for the realtime + auth flows.

(function () {
  'use strict';
  if (typeof window === 'undefined' || typeof document === 'undefined') return;
  if (window.__whWorkerDrawerLoaded) return;
  window.__whWorkerDrawerLoaded = true;

  const STYLE = `
    .wh-worker-drawer-overlay {
      position: fixed; inset: 0; background: rgba(0,0,0,0.5);
      z-index: 998; opacity: 0; pointer-events: none;
      transition: opacity 0.2s ease-out;
      backdrop-filter: blur(2px);
    }
    .wh-worker-drawer-overlay.open { opacity: 1; pointer-events: auto; }
    .wh-worker-drawer {
      position: fixed; bottom: 0; left: 0; right: 0;
      max-height: 80vh; overflow-y: auto;
      background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
      color: #e2e8f0; padding: 1.25rem 1rem 1.75rem;
      border-top: 1px solid rgba(255,255,255,0.12);
      border-radius: 1.25rem 1.25rem 0 0;
      transform: translateY(100%);
      transition: transform 0.22s ease-out;
      z-index: 999; box-shadow: 0 -10px 30px rgba(0,0,0,0.4);
    }
    .wh-worker-drawer.open { transform: translateY(0); }
    .wh-worker-drawer h3 { font-size: 1.05rem; font-weight: 700; margin: 0 0 0.85rem; }
    .wh-worker-drawer .row { display: flex; justify-content: space-between; padding: 0.45rem 0;
      border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 0.85rem; }
    .wh-worker-drawer .row span:first-child { color: rgba(255,255,255,0.6); }
    .wh-worker-drawer .row span:last-child  { font-weight: 600; }
    .wh-worker-drawer .close-btn { position: absolute; top: 0.5rem; right: 0.75rem;
      background: transparent; border: none; color: rgba(255,255,255,0.4);
      font-size: 1.4rem; cursor: pointer; padding: 0.25rem 0.5rem; }
    .wh-worker-drawer .close-btn:hover { color: white; }
    .wh-worker-drawer .empty { color: rgba(255,255,255,0.45); font-style: italic; padding: 1rem 0; }
    [data-worker-name] { cursor: pointer; text-decoration: underline dotted rgba(255,255,255,0.2);
      text-underline-offset: 3px; }
    [data-worker-name]:hover { color: #F7A21B; }
  `;

  let drawer = null, overlay = null;

  function inject() {
    const style = document.createElement('style');
    style.textContent = STYLE;
    document.head.appendChild(style);
    overlay = document.createElement('div');
    overlay.className = 'wh-worker-drawer-overlay';
    overlay.addEventListener('click', close);
    document.body.appendChild(overlay);
    drawer = document.createElement('div');
    drawer.className = 'wh-worker-drawer';
    drawer.setAttribute('role', 'dialog');
    drawer.setAttribute('aria-label', 'Worker profile');
    document.body.appendChild(drawer);
  }

  function close() {
    if (!drawer) return;
    drawer.classList.remove('open');
    overlay.classList.remove('open');
  }

  function escHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  async function open(workerName) {
    if (!drawer) inject();
    drawer.innerHTML = `
      <button class="close-btn" aria-label="Close">×</button>
      <h3>${escHtml(workerName)}</h3>
      <div class="empty">Loading...</div>
    `;
    drawer.querySelector('.close-btn').addEventListener('click', close);
    drawer.classList.add('open');
    overlay.classList.add('open');

    // Fetch worker data. `db` is assumed global per WorkHive convention.
    if (!window.db) {
      drawer.querySelector('.empty').textContent = 'Supabase client not available on this page.';
      return;
    }

    try {
      const [skillRes, jobsRes, lbRes, invRes] = await Promise.allSettled([
        window.db.from('skill_badges').select('discipline, level').eq('worker_name', workerName).limit(10),
        window.db.from('logbook').select('id', { count: 'exact', head: true })
          .eq('worker_name', workerName).eq('status', 'Open'),
        window.db.from('logbook').select('machine, problem, created_at')
          .eq('worker_name', workerName).order('created_at', { ascending: false }).limit(3),
        window.db.from('inventory_items').select('part_name, qty_on_hand, reorder_point')
          .eq('worker_name', workerName).order('qty_on_hand', { ascending: true }).limit(5),
      ]);

      const skills  = skillRes.status === 'fulfilled' ? (skillRes.value.data || []) : [];
      const openN   = jobsRes.status === 'fulfilled' ? (jobsRes.value.count || 0) : 0;
      const recents = lbRes.status === 'fulfilled' ? (lbRes.value.data || []) : [];
      const invs    = invRes.status === 'fulfilled' ? (invRes.value.data || []) : [];

      const skillLine = skills.length
        ? skills.map(s => `${escHtml(s.discipline)} L${s.level}`).join(' · ')
        : '<span style="opacity:0.5;">No skill profile</span>';

      const recentBlock = recents.length
        ? recents.map(r => `
          <div class="row">
            <span>${escHtml(r.machine || '—')}</span>
            <span style="font-weight:500;font-size:0.78rem;opacity:0.7;">${escHtml((r.problem || '').slice(0, 30))}</span>
          </div>`).join('')
        : '<div class="empty">No recent logbook activity</div>';

      const lowInv = invs.filter(i => (i.qty_on_hand || 0) <= (i.reorder_point || 0));
      const invBlock = lowInv.length
        ? lowInv.map(i => `
          <div class="row">
            <span>${escHtml(i.part_name)}</span>
            <span style="color:#f87171;">${i.qty_on_hand}/${i.reorder_point}</span>
          </div>`).join('')
        : '<div class="empty">No low-stock items assigned</div>';

      drawer.innerHTML = `
        <button class="close-btn" aria-label="Close">×</button>
        <h3>${escHtml(workerName)}</h3>
        <div class="row"><span>Skills</span><span style="font-weight:500;">${skillLine}</span></div>
        <div class="row"><span>Open jobs</span><span>${openN}</span></div>
        <h3 style="margin-top:1rem;font-size:0.9rem;">Recent logbook</h3>
        ${recentBlock}
        <h3 style="margin-top:1rem;font-size:0.9rem;">Low stock (assigned)</h3>
        ${invBlock}
      `;
      drawer.querySelector('.close-btn').addEventListener('click', close);
    } catch (err) {
      drawer.querySelector('.empty')?.remove();
      const errDiv = document.createElement('div');
      errDiv.className = 'empty';
      errDiv.textContent = 'Could not load worker profile: ' + (err.message || err);
      drawer.appendChild(errDiv);
    }
  }

  // Global delegation -- any element with data-worker-name opens the drawer.
  document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-worker-name]');
    if (!el) return;
    const name = el.dataset.workerName;
    if (!name) return;
    e.preventDefault();
    open(name);
  });

  // Close on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && drawer && drawer.classList.contains('open')) close();
  });

  // Expose for programmatic use
  window.openWorkerDrawer = open;
  window.closeWorkerDrawer = close;
})();
