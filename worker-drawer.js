// worker-drawer.js — clickable worker-name mini-profile drawer.
// capability: display_worker_drawer
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

  /* W3-SC (2026-09-09): the drawer a supervisor opens on one of their own workers, and it spoke only
     English. window._t(en, fil) is the platform locale floor utils.js installs; resolved at CALL time
     because open() runs on a tap, long after load. Note the FOUR distinct states below stay four
     sentences in Filipino too -- "could not be loaded" and "none assigned" are different claims about
     a worker's shelf, and collapsing them in translation would undo the 2026-08 fix that split them. */
  const _tt = (en, fil) =>
    (typeof window._t === 'function') ? window._t(en, fil) : en;

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
      <button class="close-btn" aria-label="${escHtml(_tt('Close', 'Isara'))}">×</button>
      <h3>${escHtml(workerName)}</h3>
      <div class="empty">${escHtml(_tt('Loading...', 'Naglo-load...'))}</div>
    `;
    drawer.querySelector('.close-btn').addEventListener('click', close);
    drawer.classList.add('open');
    overlay.classList.add('open');

    // Fetch worker data. `db` is assumed global per WorkHive convention.
    if (!window.db) {
      drawer.querySelector('.empty').textContent =
        _tt('Supabase client not available on this page.',
            'Walang Supabase client sa page na ito.');
      return;
    }

    try {
      const [skillRes, jobsRes, lbRes, invRes] = await Promise.allSettled([
        window.db.from('skill_badges').select('discipline, level').eq('worker_name', workerName).limit(10),
        window.db.from('logbook').select('id', { count: 'exact', head: true })
          .eq('worker_name', workerName).eq('status', 'Open'),
        window.db.from('logbook').select('machine, problem, created_at')
          .eq('worker_name', workerName).order('created_at', { ascending: false }).order('id').limit(3),
        // ★`reorder_point` IS NOT A COLUMN ON inventory_items, and PostgREST rejects the WHOLE read with a
        // 400 when a select names one that does not exist. supabase-js resolves that rather than throwing,
        // so `fulfilled` was true, `data || []` gave an empty array, and this drawer has always told
        // supervisors "No low-stock items assigned" - a claim about a worker's shelf, made on a read that
        // never succeeded. The platform already fixed this class in 2026-05: v_inventory_items_truth
        // exists BECAUSE "multiple consumers query for a reorder_point column that does NOT exist", and it
        // aliases min_qty plus bakes in the low-stock rule the block below reimplements by hand.
        window.db.from('v_inventory_items_truth').select('part_name, qty_on_hand, reorder_point, is_low_stock')
          .eq('worker_name', workerName).eq('is_low_stock', true)
          .order('qty_on_hand', { ascending: true }).order('id').limit(5),
      ]);

      const skillFailed = !(skillRes.status === 'fulfilled' && skillRes.value && !skillRes.value.error);
      const skills  = skillFailed ? [] : (skillRes.value.data || []);
      // A head:true COUNT resolves with {count:null, error} rather than rejecting, so 'fulfilled'
      // does not mean it worked — `count || 0` reported "Open jobs 0" for a worker whose jobs
      // simply could not be read. null renders as a gap below.
      const openN   = (jobsRes.status === 'fulfilled' && jobsRes.value && !jobsRes.value.error &&
                       jobsRes.value.count !== null && jobsRes.value.count !== undefined)
                       ? jobsRes.value.count : null;
      // ★THE COMMENT ABOVE IS RIGHT AND THESE TWO LINES IGNORED IT. `fulfilled` means the promise settled,
      // not that the read worked: a refusal, a 400, an RLS filter all resolve with { error }. So a failed
      // read became `[]` and rendered as "No recent logbook activity" / "No low-stock items assigned" -
      // statements about a person's work made at the moment the platform could not check. Same rule as the
      // count above: an unknown says so.
      const recFailed = !(lbRes.status === 'fulfilled' && lbRes.value && !lbRes.value.error);
      const invFailed = !(invRes.status === 'fulfilled' && invRes.value && !invRes.value.error);
      const recents = recFailed ? [] : (lbRes.value.data || []);
      const invs    = invFailed ? [] : (invRes.value.data || []);

      const skillLine = skills.length
        ? skills.map(s => `${escHtml(s.discipline)} L${s.level}`).join(' · ')
        : (skillFailed
            ? `<span style="opacity:0.5;">${escHtml(_tt('Skills could not be loaded', 'Hindi ma-load ang mga kasanayan'))}</span>`
            : `<span style="opacity:0.5;">${escHtml(_tt('No skill profile', 'Walang skill profile'))}</span>`);

      const recentBlock = recents.length
        ? recents.map(r => `
          <div class="row">
            <span>${escHtml(r.machine || '-')}</span>
            <span style="font-weight:500;font-size:0.78rem;opacity:0.7;">${escHtml((r.problem || '').slice(0, 30))}</span>
          </div>`).join('')
        : (recFailed
            ? `<div class="empty">${escHtml(_tt('Recent activity could not be loaded', 'Hindi ma-load ang kamakailang aktibidad'))}</div>`
            : `<div class="empty">${escHtml(_tt('No recent logbook activity', 'Walang kamakailang aktibidad sa logbook'))}</div>`);

      // The view already applied the platform's low-stock rule (min_qty > 0 AND qty <= min_qty), so this
      // no longer re-derives it. The hand-rolled test here was `qty <= reorder_point`, which counts an
      // item with no threshold set at all as low the moment it hits zero - a different rule from the one
      // inventory.html shows, for the same shelf.
      const invBlock = invFailed
        ? `<div class="empty">${escHtml(_tt('Stock could not be loaded', 'Hindi ma-load ang stock'))}</div>`
        : (invs.length
          ? invs.map(i => `
          <div class="row">
            <span>${escHtml(i.part_name)}</span>
            <span style="color:#f87171;">${i.qty_on_hand}/${i.reorder_point}</span>
          </div>`).join('')
          : `<div class="empty">${escHtml(_tt('No low-stock items assigned', 'Walang naka-assign na kulang sa stock'))}</div>`);

      drawer.innerHTML = `
        <button class="close-btn" aria-label="${escHtml(_tt('Close', 'Isara'))}">×</button>
        <h3>${escHtml(workerName)}</h3>
        <div class="row"><span>${escHtml(_tt('Skills', 'Mga kasanayan'))}</span><span style="font-weight:500;">${skillLine}</span></div>
        <div class="row"><span>${escHtml(_tt('Open jobs', 'Bukas na trabaho'))}</span><span>${openN === null ? '&mdash;' : openN}</span></div>
        <h3 style="margin-top:1rem;font-size:0.9rem;">${escHtml(_tt('Recent logbook', 'Kamakailang logbook'))}</h3>
        ${recentBlock}
        <h3 style="margin-top:1rem;font-size:0.9rem;">${escHtml(_tt('Low stock (assigned)', 'Kulang sa stock (naka-assign)'))}</h3>
        ${invBlock}
      `;
      drawer.querySelector('.close-btn').addEventListener('click', close);
    } catch (err) {
      drawer.querySelector('.empty')?.remove();
      const errDiv = document.createElement('div');
      errDiv.className = 'empty';
      errDiv.textContent = _tt('Could not load worker profile: ',
                               'Hindi ma-load ang profile ng manggagawa: ') + (err.message || err);
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
