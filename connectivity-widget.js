// ─────────────────────────────────────────────────────────────────────────────
// connectivity-widget.js — Phase 2.5 + 2.2 of STRATEGIC_ROADMAP
//
// One-glance "network weather report" the worker can trust during a brownout.
// Renders a small chip in the lower-right that surfaces three signals the
// Filipino industrial reality demands:
//
//   1. Online vs offline (navigator.onLine + ping fallback)
//   2. Effective bandwidth class (4g | 3g | 2g | slow-2g) via the
//      NetworkInformation API where available, with a heuristic fallback.
//   3. Aggregate offline-queue depth across all registered queues
//      (whGetQueueDepth from offline-queue.js).
//
// The widget is a passive observer. It does NOT throttle or block work; it
// tells the worker what state the platform is in so the worker can decide
// whether to wait or keep writing into the offline queue. Pages still need
// to expose the queue (offline-queue.js) and degrade their own behaviour
// for slow links — this widget is just the visible indicator.
//
// Wire on any page:
//   <script defer src="offline-queue.js"></script>
//   <script defer src="connectivity-widget.js"></script>
//   (no per-page init needed; the widget self-mounts on DOMContentLoaded)
//
// Skills consulted:
//   mobile-maestro (always-visible status, touch-friendly tap target)
//   devops (NetworkInformation API quirks; not available on iOS Safari)
//   designer (minimal chrome, low contrast when healthy, accent on degraded)
// ─────────────────────────────────────────────────────────────────────────────

(function () {
  if (typeof window === 'undefined') return;
  if (window._whConnectivityMounted) return;
  window._whConnectivityMounted = true;

  /* W3-SC (2026-09-09): this widget ships on 33 pages and its help sentence is the one that tells a
     person whether their offline work is SAFE -- the exact sentence the 2026-08-04 marketplace finding
     showed people act on. It spoke only English. window._t(en, fil) is the platform locale floor
     utils.js installs; resolved at CALL time inside refresh(), which re-runs on every connectivity
     change and on wh-locale-change, so switching language re-paints the widget in the new language. */
  const _tt = (en, fil) =>
    (typeof window._t === 'function') ? window._t(en, fil) : en;

  /* escHtml in scope, for the SAME reason `_tt` is resolved at call time rather than bound at load:
     this widget ships on 33 pages and utils.js (which installs both) is loaded at the BOTTOM of most of
     them. Everything this file interpolates today is a literal - `${_tt('unknown','hindi alam')}` - so
     nothing here is currently escapable user data. It is declared anyway because validate_xss's
     `esc_html_available` check is right about the direction of travel: a file that has learned to
     interpolate into innerHTML will be edited again, on a widget every page carries, and the moment a
     queue depth or a network name arrives from anywhere but a constant it must go through this. The
     fallback is the conservative one - if utils.js has not landed, escape here rather than trust.
     Named `escHtml` rather than the usual one-letter `e` shorthand: this is a module-scope declaration
     inside the widget's IIFE, not the in-function alias the pages use, and it delegates to
     `window.escHtml` explicitly - so the name is the accurate one and no recursion is possible. */
  const escHtml = (v) => (typeof window.escHtml === 'function')
    ? window.escHtml(v)
    : String(v == null ? '' : v).replace(/[&<>"']/g, (c) =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // The popover's fixed labels, repainted at inject and on every language change.
  function paintStaticLabels() {
    const set = (id, en, fil) => {
      const el = document.getElementById(id);
      if (el) el.textContent = _tt(en, fil);
    };
    set('wh-conn-title',   'Connectivity',   'Koneksyon');
    set('wh-conn-l-status', 'Status',        'Katayuan');
    set('wh-conn-l-queue', 'Pending writes', 'Nakabinbin na i-save');
  }

  // ── Bandwidth class ───────────────────────────────────────────────────────
  // Exposes window.whBandwidthClass()  -> '4g'|'3g'|'2g'|'slow-2g'|'unknown'
  // and        window.whIsSlowLink()    -> boolean (true on 2g/slow-2g/saveData)
  function bandwidthClass() {
    try {
      const c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      if (!c) return 'unknown';
      if (c.saveData) return '2g';
      if (typeof c.effectiveType === 'string') return c.effectiveType;  // '4g'|'3g'|'2g'|'slow-2g'
    } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
    return 'unknown';
  }
  function isSlowLink() {
    const cls = bandwidthClass();
    return cls === '2g' || cls === 'slow-2g';
  }
  window.whBandwidthClass = bandwidthClass;
  window.whIsSlowLink     = isSlowLink;

  // ── Backend health (Arc S D-004) ────────────────────────────────────────────
  // navigator.onLine only knows the DEVICE link, not whether Supabase is reachable.
  // A brownout where the device is "online" but the backend is 5xx/unreachable would
  // otherwise read as "Online" while every read/write silently fails. We ping a
  // public health endpoint (throttled to ~25s, 3.5s timeout) and expose a degraded
  // state so the chip + any page can react (read-only banner, "writes will queue").
  let _backendOk = true, _lastPing = 0;
  async function pingBackend() {
    const url = window.WH_SUPABASE_URL;
    if (!url) return true;                 // can't probe -> never false-degrade
    if (!navigator.onLine) { _backendOk = false; return false; }
    const now = Date.now();
    if (now - _lastPing < 25000) return _backendOk;   // throttle
    _lastPing = now;
    try {
      // Use the canonical timeout helper (utils.js global) so a hung server can't
      // strand the probe; fall back to a plain fetch only if it isn't loaded yet.
      const fwt = (typeof window.fetchWithTimeout === 'function')
        ? window.fetchWithTimeout
        : ((u, o) => fetch(u, o));
      // Send the anon key: /auth/v1/health 401s WITHOUT an apikey on current Supabase, which
      // false-degraded a HEALTHY backend to "Backend down" for every user (live prod journey,
      // 2026-07-18). And judge reachability by status < 500, not r.ok: a 401/403/404 means the
      // server ANSWERED (it's up, the request just lacked auth) — only a 5xx brownout, a network
      // error, or a timeout (the catch below) is a real outage.
      const _key = window.WH_SUPABASE_ANON_KEY;
      const r = await fwt(url.replace(/\/$/, '') + '/auth/v1/health',
                          _key ? { headers: { apikey: _key } } : {}, 3500);
      _backendOk = !!(r && r.status < 500);
    } catch (_) { _backendOk = false; }   // timeout / network = backend unreachable
    return _backendOk;
  }
  // Pages read this to render a read-only / "writes will queue" banner when degraded.
  window.whConnectivityState = function () {
    return { online: navigator.onLine, slow: isSlowLink(),
             backendOk: _backendOk, degraded: navigator.onLine && !_backendOk };
  };

  // FAB-CONSOLIDATION (2026-07-20): the standalone corner chip is retired — the
  // connectivity status now renders as a live pill inside the nav-hub panel. The
  // hub calls this one async snapshot (computed exactly like refresh()) to paint the
  // pill + the Status / Network / Pending-writes detail rows. Kept here so the
  // network logic (ping throttle, bandwidth class, queue depth) has a single owner.
  window.whConnectivitySnapshot = async function () {
    const online = navigator.onLine;
    const net    = bandwidthClass();
    let depth = 0;
    try {
      if (typeof window.whGetQueueDepth === 'function') {
        const d = await window.whGetQueueDepth();
        depth = d.total || 0;
      }
    } catch (_) { /* empty-catch-allow: queue depth is best-effort */ }
    const backendOk = online ? await pingBackend() : false;
    const stateKey = !online ? 'offline' : !backendOk ? 'degraded' : isSlowLink() ? 'slow' : 'online';
    const label    = !online ? 'Offline' : !backendOk ? 'Backend down' : isSlowLink() ? 'Slow' : 'Online';
    return { online, backendOk, slow: isSlowLink(), net, depth, label, stateKey };
  };

  const STYLE = `
    .wh-conn-chip {
      position: fixed;
      right: 0.85rem;
      /* sit ABOVE the nav-hub FAB (bottom:24px + ~50px FAB + 12px gap = ~88px).
         Walkthrough 2026-05-13: chip was at bottom:0.75rem and overlapped the
         FAB at same z-index, hiding the connectivity status behind the hub. */
      bottom: 5.5rem;
      z-index: 9998;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.35rem 0.65rem;
      min-height: 44px;
      border-radius: 999px;
      font-family: var(--wh-font, 'Poppins', system-ui, sans-serif);
/* ★BELOW THE PLATFORM'S OWN 12px FLOOR ON EVERY PAGE (design lens critique W45908, measured
       live on dayplanner at 390 and 1280, 2026-09-15). Found by sweeping one page's text nodes; none
       of the five offenders belonged to that page - they are all shared chrome. */
      font-size: 0.75rem;
      font-weight: 700;
      color: var(--wh-cloud, #F4F6FA);
      background: rgba(22, 32, 50, 0.82);
      border: 1px solid rgba(255, 255, 255, 0.08);
      backdrop-filter: blur(6px);
      cursor: pointer;
      transition: all 0.18s ease;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
    }
    .wh-conn-chip:hover { transform: translateY(-1px); border-color: rgba(255,255,255,0.18); }
    /* ★V1 (Ian's screenshot: the "Online" chip overlapped the companion avatar). When the nav-hub
       reveals the companion trigger it springs from bottom:24px to bottom:96px (tops out ~152px); the
       chip at 5.5rem/88px then collides with it. Raise the chip + popover ABOVE the sprung trigger. */
    body.wh-hub-open .wh-conn-chip { bottom: 10.5rem; }
    body.wh-hub-open .wh-conn-popover { bottom: 13rem; }
    .wh-conn-dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: var(--wh-green, #4ade80);
      box-shadow: 0 0 6px rgba(74,222,128,0.6);
    }
    .wh-conn-chip[data-state="offline"] { background: rgba(248,113,113,0.18); border-color: rgba(248,113,113,0.45); color: #fecaca; }
    .wh-conn-chip[data-state="offline"] .wh-conn-dot { background: var(--wh-red, #f87171); box-shadow: 0 0 6px rgba(248,113,113,0.6); }
    .wh-conn-chip[data-state="slow"] { background: rgba(247,162,27,0.18); border-color: rgba(247,162,27,0.5); color: #fde68a; }
    .wh-conn-chip[data-state="slow"] .wh-conn-dot { background: var(--wh-orange, #F7A21B); box-shadow: 0 0 6px rgba(247,162,27,0.6); }
    /* Arc S D-004: backend-degraded (device online but Supabase unreachable/5xx) */
    .wh-conn-chip[data-state="degraded"] { background: rgba(248,113,113,0.18); border-color: rgba(248,113,113,0.55); color: #fecaca; }
    .wh-conn-chip[data-state="degraded"] .wh-conn-dot { background: var(--wh-red, #f87171); box-shadow: 0 0 6px rgba(248,113,113,0.6); }
    .wh-conn-badge {
      display: inline-block;
      min-width: 18px;
      padding: 0 5px;
      border-radius: 999px;
      background: rgba(247,162,27,0.85);
      color: var(--wh-navy, #162032);
      font-size: 0.58rem;
      font-weight: 800;
      text-align: center;
    }
    .wh-conn-popover {
      position: fixed;
      right: 0.85rem;
      /* anchored above the chip (bottom:5.5rem + chip height ~1.6rem + 0.4rem gap). */
      bottom: 8rem;
      z-index: 9999;
      width: min(280px, calc(100vw - 1.5rem));
      padding: 0.85rem;
      background: rgba(22,32,50,0.96);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 0.75rem;
      backdrop-filter: blur(10px);
      box-shadow: 0 8px 24px rgba(0,0,0,0.45);
      font-family: var(--wh-font, 'Poppins', system-ui, sans-serif);
      color: var(--wh-cloud, #F4F6FA);
      font-size: 0.72rem;
      line-height: 1.45;
    }
    .wh-conn-popover.hidden { display: none; }
    .wh-conn-popover h4 {
      margin: 0 0 0.5rem; font-size: 0.78rem; font-weight: 800; letter-spacing: 0.04em;
    }
    .wh-conn-popover .wh-conn-row {
      display: flex; justify-content: space-between; gap: 0.5rem; padding: 0.2rem 0;
      border-top: 1px solid rgba(255,255,255,0.06);
    }
    .wh-conn-popover .wh-conn-row:first-of-type { border-top: 0; }
    .wh-conn-popover .wh-conn-label { color: rgba(255,255,255,0.55); }
    .wh-conn-popover .wh-conn-value { font-weight: 700; }
    /* ★THE SENTENCE SAYING YOUR WORK WILL NOT BE SAVED WAS THE SMALLEST TEXT ON THE SCREEN
       (9.92px, measured 2026-09-15). It is written for a technician on a phone in a plant, and it was
       set below every other string around it. Also lifted off 0.5 alpha: a warning at half opacity is
       the same decision twice. */
    .wh-conn-popover .wh-conn-help  { margin-top: 0.6rem; color: rgba(255,255,255,0.80); font-size: 0.75rem; }

    /* FAB-CONSOLIDATION (2026-07-20): the standalone corner chip + popover are
       retired — connectivity status now lives as a live pill inside the nav-hub
       panel (fed by window.whConnectivitySnapshot()). They stay in the DOM (the
       refresh loop still updates whConnectivityState() for pages' read-only banners)
       but are hidden so the bottom-right corner holds only the single hub FAB. */
    .wh-conn-chip, .wh-conn-popover { display: none !important; }
  `;

  function mount() {
    if (document.getElementById('wh-conn-chip')) return;
    const style = document.createElement('style');
    style.id = 'wh-conn-styles';
    style.textContent = STYLE;
    document.head.appendChild(style);

    const chip = document.createElement('button');
    chip.id = 'wh-conn-chip';
    chip.type = 'button';
    chip.className = 'wh-conn-chip';
    chip.setAttribute('aria-label', _tt('Connectivity status', 'Katayuan ng koneksyon'));
    chip.innerHTML = `
      <span class="wh-conn-dot"></span>
      <span id="wh-conn-label">Online</span>
      <span id="wh-conn-badge" class="wh-conn-badge" style="display:none;"></span>
    `;

    const pop = document.createElement('div');
    pop.id = 'wh-conn-popover';
    pop.className = 'wh-conn-popover hidden';
    pop.innerHTML = `
      <h3 id="wh-conn-title"></h3>
      <div class="wh-conn-row"><span class="wh-conn-label" id="wh-conn-l-status"></span><span id="wh-conn-status" class="wh-conn-value">Online</span></div>
      <div class="wh-conn-row"><span class="wh-conn-label">Network</span><span id="wh-conn-net" class="wh-conn-value">${_tt('unknown', 'hindi alam')}</span></div>
      <div class="wh-conn-row"><span class="wh-conn-label" id="wh-conn-l-queue"></span><span id="wh-conn-queue" class="wh-conn-value">0</span></div>
      <!-- Filled by refresh(), because the sentence is only TRUE on a page that registers a queue.
           This widget ships on every page and used to promise, everywhere, that "pending writes save
           to this device and drain automatically ... you can keep working offline." Six pages earn
           that (asset-hub, community, dayplanner, inventory, logbook, project-manager). The four
           marketplace surfaces do NOT register a queue at all -- and three of them load
           offline-queue.js without ever calling it -- so on exactly the screens where money moves,
           the widget was telling a provider their work was safe while an offline Save fired into a
           dead network and was lost. Proven live 2026-08-04: offline, the seller's Save issued
           POST marketplace_sellers and POST hive_audit_log, whGetQueueDepth() stayed
           {total:0, perSurface:{}}, and the banner still said "you can keep working offline". -->
      <div class="wh-conn-help" id="wh-conn-help"></div>
    `;

    document.body.appendChild(chip);
    document.body.appendChild(pop);
    paintStaticLabels();

    chip.addEventListener('click', () => {
      pop.classList.toggle('hidden');
      if (!pop.classList.contains('hidden')) refresh();
    });
    document.addEventListener('click', (e) => {
      if (e.target === chip || chip.contains(e.target)) return;
      if (pop.contains(e.target)) return;
      pop.classList.add('hidden');
    });

    window.addEventListener('online',  refresh);
    window.addEventListener('offline', refresh);
    /* The popover's own labels are painted ONCE at inject; refresh() only rewrites the VALUES. So a
       language toggle would leave "Connectivity / Status / Pending writes" stranded in the old
       language beside freshly-translated values. Repaint the labels too, then refresh the values.
       Repaint in place rather than re-injecting: a re-inject would re-bind every listener above and
       lose whether the person had the popover open.
       On DOCUMENT, not window: the three pages that dispatch it (analytics, hive, index) send a
       CustomEvent with no bubbles flag, so it never reaches window -- document is the same target
       onboarding.js and hive.html already listen on. */
    document.addEventListener('wh-locale-change', () => { paintStaticLabels(); refresh(); });
    try {
      const c = navigator.connection;
      if (c && typeof c.addEventListener === 'function') {
        c.addEventListener('change', refresh);
      }
    } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }

    // Periodic queue-depth refresh while popover is open OR offline.
    // Stored so it can be cleared if the page navigates away (defence-in-depth
    // against leaked timers — the page typically unloads first).
    window._whConnRefreshTimer = setInterval(() => {
      if (!pop.classList.contains('hidden') || !navigator.onLine) refresh();
    }, 4000);
    window.addEventListener('beforeunload', () => {
      if (window._whConnRefreshTimer) clearInterval(window._whConnRefreshTimer);
    });

    // Cross-tab broadcasts from offline-queue.js
    try {
      if (typeof BroadcastChannel !== 'undefined') {
        // The queue broadcasts on per-db channel names; we can't subscribe
        // to all dynamically, but page-level queues typically share these
        // common names. Listening on the generic one is enough to refresh.
        const ch = new BroadcastChannel('wh-offline-queue:wh_offline');
        ch.onmessage = () => refresh();
      }
    } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }

    refresh();
  }

  async function refresh() {
    const chip   = document.getElementById('wh-conn-chip');
    const dotLbl = document.getElementById('wh-conn-label');
    const badge  = document.getElementById('wh-conn-badge');
    const statusEl = document.getElementById('wh-conn-status');
    const netEl    = document.getElementById('wh-conn-net');
    const qEl      = document.getElementById('wh-conn-queue');
    if (!chip) return;

    const online = navigator.onLine;
    const net    = bandwidthClass();
    let depth = 0;
    let queuesOnThisPage = 0;
    try {
      if (typeof window.whGetQueueDepth === 'function') {
        const d = await window.whGetQueueDepth();
        depth = d.total || 0;
        // perSurface is keyed by whatever this PAGE registered. Empty means nothing on this screen
        // is queued, whatever offline-queue.js being loaded might suggest.
        //
        // ★A REGISTERED QUEUE IS NOT A WORKING QUEUE, and counting KEYS could not tell them apart
        // (2026-09-10). whGetQueueDepth already distinguishes them: when a queue cannot be read it
        // writes `perSurface[name] = -1` rather than a count, which happens whenever indexedDB.open
        // fails - private browsing, site data blocked, or a quota exceeded on a shared plant tablet.
        // Counting the KEYS treated that -1 as a present, healthy queue, so the help text below
        // promised "pending writes save to this device ... you can keep working offline" on a page
        // whose queue could not accept a single write. That is the SAME false promise this widget was
        // built to stop on 2026-08-04, arriving through a different door: not "this page never had a
        // queue", but "this page has one and it is broken". The sentinel was already there and nobody
        // was reading it. Only a queue that ANSWERED counts, so a page whose storage is refused now
        // gets the honest sentence - do not submit without a connection - instead of a promise it
        // cannot keep.
        //
        // AND A SINGLE BROKEN QUEUE SILENCES THE PROMISE FOR THE WHOLE PAGE, which is this file's own
        // rule applied consistently rather than a new one: "a promise of safety is worse than no
        // promise on a screen that does not keep it". A page with two surfaces where one can queue and
        // one cannot does not save your work - it saves some of it, and the person has no way to know
        // which. The honest sentence is the cautious one.
        const _depths = Object.values(d.perSurface || {});
        const _broken = _depths.some((n) => !(typeof n === 'number' && n >= 0));
        queuesOnThisPage = _broken ? 0 : _depths.length;
      }
    } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }

    // Say the true thing for THIS page. A promise of safety is worse than no promise on a screen
    // that does not keep it: it is the difference between a provider retrying and a provider
    // walking away believing their top-up was filed.
    const helpEl = document.getElementById('wh-conn-help');
    if (helpEl) {
      helpEl.textContent = queuesOnThisPage > 0
        ? _tt('Pending writes save to this device and drain automatically when the connection returns. You can keep working offline.',
              'Ang mga nakabinbin na i-save ay nasa device na ito at awtomatikong ipapadala pagbalik ng koneksyon. Puwede kang magpatuloy kahit offline.')
        : _tt('This page does not save work offline. Anything you submit without a connection will not be sent, so wait until you are back online.',
              'Hindi nagse-save offline ang page na ito. Ang isusumite mo nang walang koneksyon ay hindi maipapadala, kaya maghintay munang bumalik ang koneksyon.');
    }

    const backendOk = online ? await pingBackend() : false;
    if (!online) {
      chip.setAttribute('data-state', 'offline');
      dotLbl.textContent = 'Offline';
    } else if (!backendOk) {
      // Arc S D-004: device online but Supabase unreachable — distinct from offline.
      chip.setAttribute('data-state', 'degraded');
      dotLbl.textContent = _tt('Backend down', 'Down ang backend');
    } else if (isSlowLink()) {
      chip.setAttribute('data-state', 'slow');
      dotLbl.textContent = _tt('Slow', 'Mabagal');
    } else {
      chip.setAttribute('data-state', 'online');
      dotLbl.textContent = 'Online';
    }

    if (depth > 0) {
      badge.style.display = 'inline-block';
      badge.textContent = String(depth);
    } else {
      badge.style.display = 'none';
    }

    if (statusEl) statusEl.textContent = !online ? 'Offline'
      : !backendOk ? _tt('Online, but backend unavailable', 'Online, pero hindi maabot ang backend')
      : isSlowLink() ? _tt('Online (slow link)', 'Online (mabagal ang koneksyon)') : 'Online';
    if (netEl)    netEl.textContent    = net === 'unknown'
      ? _tt('unknown (browser does not report)', 'hindi alam (hindi nagsasabi ang browser)')
      : net.toUpperCase();
    if (qEl)      qEl.textContent      = String(depth);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
