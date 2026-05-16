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

  // ── Bandwidth class ───────────────────────────────────────────────────────
  // Exposes window.whBandwidthClass()  -> '4g'|'3g'|'2g'|'slow-2g'|'unknown'
  // and        window.whIsSlowLink()    -> boolean (true on 2g/slow-2g/saveData)
  function bandwidthClass() {
    try {
      const c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      if (!c) return 'unknown';
      if (c.saveData) return '2g';
      if (typeof c.effectiveType === 'string') return c.effectiveType;  // '4g'|'3g'|'2g'|'slow-2g'
    } catch (_) {}
    return 'unknown';
  }
  function isSlowLink() {
    const cls = bandwidthClass();
    return cls === '2g' || cls === 'slow-2g';
  }
  window.whBandwidthClass = bandwidthClass;
  window.whIsSlowLink     = isSlowLink;

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
      font-family: 'Poppins', system-ui, sans-serif;
      font-size: 0.66rem;
      font-weight: 700;
      color: #F4F6FA;
      background: rgba(22, 32, 50, 0.82);
      border: 1px solid rgba(255, 255, 255, 0.08);
      backdrop-filter: blur(6px);
      cursor: pointer;
      transition: all 0.18s ease;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
    }
    .wh-conn-chip:hover { transform: translateY(-1px); border-color: rgba(255,255,255,0.18); }
    .wh-conn-dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: #4ade80;
      box-shadow: 0 0 6px rgba(74,222,128,0.6);
    }
    .wh-conn-chip[data-state="offline"] { background: rgba(248,113,113,0.18); border-color: rgba(248,113,113,0.45); color: #fecaca; }
    .wh-conn-chip[data-state="offline"] .wh-conn-dot { background: #f87171; box-shadow: 0 0 6px rgba(248,113,113,0.6); }
    .wh-conn-chip[data-state="slow"] { background: rgba(247,162,27,0.18); border-color: rgba(247,162,27,0.5); color: #fde68a; }
    .wh-conn-chip[data-state="slow"] .wh-conn-dot { background: #F7A21B; box-shadow: 0 0 6px rgba(247,162,27,0.6); }
    .wh-conn-badge {
      display: inline-block;
      min-width: 18px;
      padding: 0 5px;
      border-radius: 999px;
      background: rgba(247,162,27,0.85);
      color: #162032;
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
      font-family: 'Poppins', system-ui, sans-serif;
      color: #F4F6FA;
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
    .wh-conn-popover .wh-conn-help  { margin-top: 0.6rem; color: rgba(255,255,255,0.5); font-size: 0.62rem; }
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
    chip.setAttribute('aria-label', 'Connectivity status');
    chip.innerHTML = `
      <span class="wh-conn-dot"></span>
      <span id="wh-conn-label">Online</span>
      <span id="wh-conn-badge" class="wh-conn-badge" style="display:none;"></span>
    `;

    const pop = document.createElement('div');
    pop.id = 'wh-conn-popover';
    pop.className = 'wh-conn-popover hidden';
    pop.innerHTML = `
      <h4>Connectivity</h4>
      <div class="wh-conn-row"><span class="wh-conn-label">Status</span><span id="wh-conn-status" class="wh-conn-value">Online</span></div>
      <div class="wh-conn-row"><span class="wh-conn-label">Network</span><span id="wh-conn-net" class="wh-conn-value">unknown</span></div>
      <div class="wh-conn-row"><span class="wh-conn-label">Pending writes</span><span id="wh-conn-queue" class="wh-conn-value">0</span></div>
      <div class="wh-conn-help">Pending writes save to this device and drain automatically when the connection returns. You can keep working offline.</div>
    `;

    document.body.appendChild(chip);
    document.body.appendChild(pop);

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
    try {
      const c = navigator.connection;
      if (c && typeof c.addEventListener === 'function') {
        c.addEventListener('change', refresh);
      }
    } catch (_) {}

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
    } catch (_) {}

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
    try {
      if (typeof window.whGetQueueDepth === 'function') {
        const d = await window.whGetQueueDepth();
        depth = d.total || 0;
      }
    } catch (_) {}

    if (!online) {
      chip.setAttribute('data-state', 'offline');
      dotLbl.textContent = 'Offline';
    } else if (isSlowLink()) {
      chip.setAttribute('data-state', 'slow');
      dotLbl.textContent = 'Slow';
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

    if (statusEl) statusEl.textContent = online ? (isSlowLink() ? 'Online (slow link)' : 'Online') : 'Offline';
    if (netEl)    netEl.textContent    = net === 'unknown' ? 'unknown (browser does not report)' : net.toUpperCase();
    if (qEl)      qEl.textContent      = String(depth);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
