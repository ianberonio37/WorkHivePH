/**
 * WorkHive Navigation Hub
 * ─────────────────────────────────────────────
 * Single draggable FAB that expands into a tool switcher panel.
 * Replaces floating-ai.js on all pages.
 * AI Assistant tile navigates to assistant.html.
 *
 * Drop one <script src="nav-hub.js"></script> before </body>.
 */

(function () {
  'use strict';

  // ─── Tool Registry ────────────────────────────────────────────────────────────
  const TOOLS = [
    { label: 'Home',         href: 'index.html',        match: ['index', '/'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H4a1 1 0 01-1-1V9.5z"/><path d="M9 21V12h6v9"/></svg>` },
    { label: 'Logbook',      href: 'logbook.html',      match: ['logbook'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/><line x1="8" y1="7" x2="16" y2="7"/><line x1="8" y1="11" x2="16" y2="11"/><line x1="8" y1="15" x2="12" y2="15"/></svg>` },
    { label: 'Inventory',    href: 'inventory.html',    match: ['inventory'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>` },
    { label: 'Day Planner',  href: 'dayplanner.html',   match: ['dayplanner'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="8" y1="14" x2="8" y2="14" stroke-width="3" stroke-linecap="round"/><line x1="12" y1="14" x2="12" y2="14" stroke-width="3" stroke-linecap="round"/><line x1="16" y1="14" x2="16" y2="14" stroke-width="3" stroke-linecap="round"/></svg>` },
    { label: 'WorkHive',     href: 'hive.html',         match: ['hive'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>` },
    { label: 'AI Assistant', href: 'assistant.html',    match: ['assistant'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/><line x1="9" y1="10" x2="9" y2="10" stroke-width="3" stroke-linecap="round"/><line x1="12" y1="10" x2="12" y2="10" stroke-width="3" stroke-linecap="round"/><line x1="15" y1="10" x2="15" y2="10" stroke-width="3" stroke-linecap="round"/></svg>`,
      accent: true },
    { label: 'Skill Matrix',  href: 'skillmatrix.html', match: ['skillmatrix'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"/></svg>` },
    { label: 'Eng. Design',  href: 'engineering-design.html', match: ['engineering-design'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 20h20"/><path d="M5 20V10l7-7 7 7v10"/><path d="M9 20v-5h6v5"/></svg>` },
    { label: 'PM Scheduler', href: 'pm-scheduler.html', match: ['pm-scheduler'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><path d="M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"/></svg>` },
    { label: 'Analytics', href: 'analytics.html', match: ['analytics'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg>` },
    { label: 'Report Sender', href: 'report-sender.html', match: ['report-sender'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>` },
  ];

  // ─── Click Tracking (recents) ────────────────────────────────────────────────
  var CLICK_KEY = 'wh-tool-clicks';

  function trackToolClick(href) {
    try {
      var c = JSON.parse(localStorage.getItem(CLICK_KEY) || '{}');
      c[href] = (c[href] || 0) + 1;
      localStorage.setItem(CLICK_KEY, JSON.stringify(c));
    } catch (_) {}
  }

  function getQuickTools(n) {
    try {
      var c = JSON.parse(localStorage.getItem(CLICK_KEY) || '{}');
      return TOOLS.slice()
        .sort(function(a, b) { return (c[b.href] || 0) - (c[a.href] || 0); })
        .slice(0, n);
    } catch (_) {
      return TOOLS.slice(0, n);
    }
  }

  // ─── Current Page Detection ───────────────────────────────────────────────────
  function getCurrentTool() {
    const path = window.location.pathname.toLowerCase();
    for (const t of TOOLS) {
      for (const m of t.match) {
        if (m === '/' ? (path === '/' || path.endsWith('/index.html') || path === '') : path.includes(m)) return t;
      }
    }
    return TOOLS[0];
  }

  // ─── State ────────────────────────────────────────────────────────────────────
  let isOpen   = false;
  const current = getCurrentTool();

  // ─── Build Widget ─────────────────────────────────────────────────────────────
  function buildWidget() {
    const wrapper = document.createElement('div');
    wrapper.id = 'wh-hub';

    /* All-tools grid (collapsed by default) */
    const tilesHTML = TOOLS.map(t => {
      const isCurrent = t === current;
      return `
        <a href="${t.href}" class="wh-hub-tile${isCurrent ? ' active' : ''}${t.accent ? ' accent' : ''}" ${isCurrent ? 'aria-current="page"' : ''}>
          <span class="wh-hub-tile-icon">${t.icon}</span>
          <span class="wh-hub-tile-label">${t.label}</span>
          ${isCurrent ? '<span class="wh-hub-tile-dot"></span>' : ''}
        </a>`;
    }).join('');

    /* Quick access row — top 4 by recent usage */
    const quickTools = getQuickTools(4);
    const quickHTML = quickTools.map(t => {
      const isCurrent = t === current;
      const shortLabel = t.label.length > 8 ? t.label.split(' ')[0] : t.label;
      return `<a href="${t.href}" class="wh-hub-quick-tile${isCurrent ? ' active' : ''}" ${isCurrent ? 'aria-current="page"' : ''} title="${t.label}">
        <span class="wh-hub-quick-icon">${t.icon}</span>
        <span class="wh-hub-quick-label">${shortLabel}</span>
      </a>`;
    }).join('');

    wrapper.innerHTML = `
      <style>
        #wh-hub {
          position: fixed;
          bottom: 24px;
          right: 24px;
          z-index: 9998;
          font-family: 'Poppins', sans-serif;
        }

        /* ── FAB ── */
        #wh-hub-fab {
          width: 56px;
          height: 56px;
          border-radius: 16px;
          background: linear-gradient(135deg, #162032, #1F2E45);
          border: 1.5px solid rgba(247,162,27,0.35);
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 4px 20px rgba(0,0,0,0.4), 0 0 0 0 rgba(247,162,27,0.2);
          transition: transform 0.18s ease-out, box-shadow 0.2s ease, border-color 0.18s ease;
          position: relative;
          user-select: none;
        }
        #wh-hub-fab:hover {
          transform: scale(1.1);
          border-color: rgba(247,162,27,0.6);
          box-shadow: 0 6px 28px rgba(0,0,0,0.45), 0 0 0 4px rgba(247,162,27,0.08);
        }
        #wh-hub-fab:active {
          transform: scale(0.93);
          transition: transform 0.1s ease;
        }
        #wh-hub-fab.open {
          border-color: #F7A21B;
          box-shadow: 0 6px 28px rgba(0,0,0,0.45), 0 0 0 4px rgba(247,162,27,0.12);
        }
        #wh-hub-fab svg { pointer-events: none; transition: transform 0.22s ease; }
        #wh-hub-fab.open svg { transform: rotate(45deg); }

        /* ── Current page badge on FAB ── */
        #wh-hub-current-label {
          position: absolute;
          right: 64px;
          top: 50%;
          transform: translateY(-50%);
          background: rgba(22,32,50,0.96);
          border: 1px solid rgba(247,162,27,0.25);
          color: rgba(255,255,255,0.7);
          font-size: 11px;
          font-weight: 500;
          padding: 5px 10px;
          border-radius: 8px;
          white-space: nowrap;
          pointer-events: none;
          opacity: 0;
          transition: opacity 0.18s;
        }
        #wh-hub:not(.hub-open) #wh-hub-fab:hover #wh-hub-current-label { opacity: 1; }

        /* ── Panel ── */
        #wh-hub-panel {
          position: absolute;
          bottom: 68px;
          right: 0;
          width: 300px;
          background: linear-gradient(160deg, #1F2E45 0%, #162032 100%);
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 20px;
          box-shadow: 0 24px 64px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.03);
          padding: 16px;
          opacity: 0;
          transform: translateY(10px) scale(0.96);
          pointer-events: none;
          transition: opacity 0.2s ease, transform 0.2s ease-out;
        }
        #wh-hub-panel.open {
          opacity: 1;
          transform: translateY(0) scale(1);
          pointer-events: all;
        }

        /* ── Panel header ── */
        #wh-hub-panel-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 12px;
          padding-bottom: 10px;
          border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        #wh-hub-panel-header span {
          font-size: 11px;
          font-weight: 600;
          color: rgba(255,255,255,0.3);
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }
        #wh-hub-panel-header strong {
          font-size: 11px;
          font-weight: 600;
          color: #F7A21B;
          letter-spacing: 0.04em;
        }

        /* ── Section labels ── */
        .wh-hub-section-label {
          font-size: 10px; font-weight: 600; letter-spacing: 0.1em;
          text-transform: uppercase; color: rgba(255,255,255,0.25);
          margin: 0 0 8px;
        }

        /* ── Quick access row (4 icon + short label tiles) ── */
        #wh-hub-quick { margin-bottom: 4px; }
        #wh-hub-quick-row {
          display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;
        }
        .wh-hub-quick-tile {
          display: flex; flex-direction: column;
          align-items: center; justify-content: center;
          gap: 5px; padding: 10px 4px; border-radius: 12px;
          background: rgba(255,255,255,0.05);
          border: 1px solid rgba(255,255,255,0.08);
          text-decoration: none; cursor: pointer; min-height: 54px;
          transition: background 0.15s ease, border-color 0.15s ease, transform 0.18s ease-out;
        }
        .wh-hub-quick-tile:hover {
          background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.18);
          transform: translateY(-5px) scale(1.06);
        }
        .wh-hub-quick-tile:active { transform: scale(0.9); transition: transform 0.08s ease; }
        .wh-hub-quick-tile.active {
          background: rgba(247,162,27,0.12); border-color: rgba(247,162,27,0.35);
        }
        .wh-hub-quick-tile.active .wh-hub-quick-icon { color: #F7A21B; }
        .wh-hub-quick-icon { color: rgba(255,255,255,0.7); display:flex; }
        .wh-hub-quick-label {
          font-size: 9px; color: rgba(255,255,255,0.45); font-weight: 500;
          text-align: center; line-height: 1.2; font-family: 'Poppins', sans-serif;
        }
        .wh-hub-quick-tile.active .wh-hub-quick-label { color: #F7A21B; }

        /* ── Divider ── */
        .wh-hub-divider { height: 1px; background: rgba(255,255,255,0.06); margin: 10px 0 6px; }

        /* ── All Tools toggle ── */
        #wh-hub-all-toggle {
          width: 100%; display: flex; align-items: center; justify-content: space-between;
          padding: 6px 2px; background: none; border: none; cursor: pointer;
          color: rgba(255,255,255,0.35); font-size: 10px; font-weight: 600;
          text-transform: uppercase; letter-spacing: 0.1em;
          font-family: 'Poppins', sans-serif; margin-bottom: 2px;
          transition: color 0.2s ease;
        }
        #wh-hub-all-toggle:hover { color: rgba(255,255,255,0.65); }
        #wh-hub-all-toggle svg {
          transition: transform 0.2s ease-out;
        }
        #wh-hub-all-toggle.open svg { transform: rotate(180deg); }

        /* ── All Tools grid (collapsible) ── */
        #wh-hub-tiles {
          display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
          overflow: hidden; max-height: 0; opacity: 0; margin-top: 0;
          transition: max-height 0.25s ease-out, opacity 0.2s ease, margin-top 0.2s ease;
        }
        #wh-hub-tiles.open { max-height: 600px; opacity: 1; margin-top: 6px; }

        /* ── Tile ── */
        .wh-hub-tile {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 6px;
          padding: 12px 8px 10px;
          border-radius: 12px;
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.06);
          text-decoration: none;
          cursor: pointer;
          transition: background 0.15s ease, border-color 0.15s ease, transform 0.18s ease-out;
          position: relative;
        }
        .wh-hub-tile:hover {
          background: rgba(255,255,255,0.09);
          border-color: rgba(255,255,255,0.16);
          transform: translateY(-5px) scale(1.03);
        }
        .wh-hub-tile:active {
          transform: scale(0.93);
          transition: transform 0.08s ease;
        }

        /* Active / current page tile */
        .wh-hub-tile.active {
          background: rgba(247,162,27,0.1);
          border-color: rgba(247,162,27,0.3);
        }
        .wh-hub-tile.active .wh-hub-tile-icon { color: #F7A21B; }
        .wh-hub-tile.active .wh-hub-tile-label { color: #F7A21B; }

        /* AI accent tile */
        .wh-hub-tile.accent:not(.active) {
          background: rgba(41,182,217,0.07);
          border-color: rgba(41,182,217,0.2);
        }
        .wh-hub-tile.accent:not(.active) .wh-hub-tile-icon { color: #29B6D9; }
        .wh-hub-tile.accent:not(.active) .wh-hub-tile-label { color: #29B6D9; }
        .wh-hub-tile.accent:not(.active):hover {
          background: rgba(41,182,217,0.13);
          border-color: rgba(41,182,217,0.35);
        }

        .wh-hub-tile-icon {
          color: rgba(255,255,255,0.5);
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .wh-hub-tile-label {
          font-size: 10px;
          font-weight: 600;
          color: rgba(255,255,255,0.5);
          text-align: center;
          letter-spacing: 0.02em;
          line-height: 1.2;
        }

        /* Current-page dot */
        .wh-hub-tile-dot {
          position: absolute;
          top: 6px;
          right: 6px;
          width: 5px;
          height: 5px;
          border-radius: 50%;
          background: #F7A21B;
        }

        /* ── Mobile ── */
        @media (max-width: 480px) {
          #wh-hub { bottom: max(16px, env(safe-area-inset-bottom)); right: 16px; }
          #wh-hub-panel { width: calc(100vw - 32px); }
        }
      </style>

      <!-- FAB button -->
      <button id="wh-hub-fab" aria-label="Open navigation hub" aria-expanded="false">
        <span id="wh-hub-current-label">${current.label}</span>
        <!-- Grid / apps icon — rotates to X when open -->
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#F7A21B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="7" height="7" rx="1"/>
          <rect x="14" y="3" width="7" height="7" rx="1"/>
          <rect x="3" y="14" width="7" height="7" rx="1"/>
          <rect x="14" y="14" width="7" height="7" rx="1"/>
        </svg>
      </button>

      <!-- Panel -->
      <div id="wh-hub-panel" role="dialog" aria-label="Navigation hub">
        <div id="wh-hub-panel-header">
          <span>Tools</span>
          <strong>${current.label}</strong>
        </div>

        <!-- Quick Access Row -->
        <div id="wh-hub-quick">
          <p class="wh-hub-section-label">Quick Access</p>
          <div id="wh-hub-quick-row">${quickHTML}</div>
        </div>

        <div class="wh-hub-divider"></div>

        <!-- All Tools (collapsible) -->
        <button id="wh-hub-all-toggle" aria-expanded="false" aria-controls="wh-hub-tiles">
          All Tools
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
        <div id="wh-hub-tiles" role="region">${tilesHTML}</div>
      </div>
    `;

    document.body.appendChild(wrapper);
  }

  // ─── Open / Close ─────────────────────────────────────────────────────────────
  function openHub() {
    isOpen = true;
    document.getElementById('wh-hub').classList.add('hub-open');
    document.getElementById('wh-hub-fab').classList.add('open');
    document.getElementById('wh-hub-fab').setAttribute('aria-expanded', 'true');
    document.getElementById('wh-hub-panel').classList.add('open');
  }

  function closeHub() {
    isOpen = false;
    document.getElementById('wh-hub').classList.remove('hub-open');
    document.getElementById('wh-hub-fab').classList.remove('open');
    document.getElementById('wh-hub-fab').setAttribute('aria-expanded', 'false');
    document.getElementById('wh-hub-panel').classList.remove('open');
  }

  // ─── Drag + Snap (same pattern as floating-ai.js) ─────────────────────────────
  const STORAGE_KEY = 'wh-hub-position';
  let snapSide = 'right';

  function applyPosition(side, bottomPx) {
    const hub   = document.getElementById('wh-hub');
    const panel = document.getElementById('wh-hub-panel');
    const label = document.getElementById('wh-hub-current-label');
    snapSide = side;

    hub.style.left   = side === 'left'  ? '16px' : 'auto';
    hub.style.right  = side === 'right' ? '16px' : 'auto';
    hub.style.bottom = bottomPx + 'px';
    hub.style.top    = 'auto';

    // Flip panel so it always stays on screen
    panel.style.left  = side === 'left'  ? '0'    : 'auto';
    panel.style.right = side === 'right' ? '0'    : 'auto';

    // Flip tooltip label
    if (label) {
      label.style.left  = side === 'left'  ? '64px' : 'auto';
      label.style.right = side === 'right' ? '64px' : 'auto';
    }
  }

  function loadSavedPosition() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (saved && (saved.side === 'left' || saved.side === 'right') && typeof saved.bottom === 'number') {
        applyPosition(saved.side, Math.max(16, Math.min(saved.bottom, window.innerHeight - 80)));
        return;
      }
    } catch (_) {}
    applyPosition('right', 24);
  }

  function savePosition(side, bottom) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ side, bottom })); } catch (_) {}
  }

  function makeDraggable() {
    const fab = document.getElementById('wh-hub-fab');
    let dragging = false;
    let didDrag  = false;
    let startX, startY, startBottom, startLeft, startRight;

    function onStart(e) {
      const touch = e.touches ? e.touches[0] : e;
      dragging = true; didDrag = false;
      startX = touch.clientX; startY = touch.clientY;
      const hub  = document.getElementById('wh-hub');
      const rect = hub.getBoundingClientRect();
      startBottom = window.innerHeight - rect.bottom;
      startLeft   = rect.left;
      startRight  = window.innerWidth - rect.right;
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup',   onEnd);
      document.addEventListener('touchmove', onMove, { passive: false });
      document.addEventListener('touchend',  onEnd);
    }

    function onMove(e) {
      if (!dragging) return;
      if (e.cancelable) e.preventDefault();
      const touch = e.touches ? e.touches[0] : e;
      const dx = touch.clientX - startX;
      const dy = touch.clientY - startY;
      if (Math.abs(dx) > 4 || Math.abs(dy) > 4) didDrag = true;
      if (!didDrag) return;
      const hub    = document.getElementById('wh-hub');
      const newBot = Math.max(16, Math.min(startBottom - dy, window.innerHeight - 80));
      if (snapSide === 'right') hub.style.right = Math.max(0, startRight - dx) + 'px';
      else                      hub.style.left  = Math.max(0, startLeft  + dx) + 'px';
      hub.style.bottom = newBot + 'px';
    }

    function onEnd() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup',   onEnd);
      document.removeEventListener('touchmove', onMove);
      document.removeEventListener('touchend',  onEnd);
      if (!didDrag) { dragging = false; return; }
      dragging = false;
      const hub  = document.getElementById('wh-hub');
      const rect = hub.getBoundingClientRect();
      const side = (rect.left + rect.width / 2) < (window.innerWidth / 2) ? 'left' : 'right';
      applyPosition(side, window.innerHeight - rect.bottom);
      savePosition(side, window.innerHeight - rect.bottom);
    }

    fab.addEventListener('mousedown',  onStart);
    fab.addEventListener('touchstart', onStart, { passive: true });
    fab.addEventListener('click', () => {
      if (didDrag) { didDrag = false; return; }
      isOpen ? closeHub() : openHub();
    });
  }

  // ─── Event Wiring ─────────────────────────────────────────────────────────────
  function wireEvents() {
    makeDraggable();

    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && isOpen) closeHub();
    });

    document.addEventListener('click', e => {
      const hub = document.getElementById('wh-hub');
      if (isOpen && hub && !hub.contains(e.target)) closeHub();
    });

    /* All Tools expand/collapse */
    const allToggle = document.getElementById('wh-hub-all-toggle');
    const allGrid   = document.getElementById('wh-hub-tiles');
    if (allToggle && allGrid) {
      allToggle.addEventListener('click', function() {
        const opening = !allGrid.classList.contains('open');
        allGrid.classList.toggle('open');
        allToggle.classList.toggle('open');
        allToggle.setAttribute('aria-expanded', opening);
      });
    }

    /* Track clicks on any tile (quick or all-tools) to update recents */
    const panel = document.getElementById('wh-hub-panel');
    if (panel) {
      panel.addEventListener('click', function(e) {
        const tile = e.target.closest('a[href]');
        if (tile) trackToolClick(tile.getAttribute('href'));
      });
    }
  }

  // ─── Init ─────────────────────────────────────────────────────────────────────
  function init() {
    buildWidget();
    loadSavedPosition();
    wireEvents();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
