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

  // ─── Phase E.3c: Lazy-load Global Search overlay so Cmd+K works everywhere
  // nav-hub.js loads on every page, so attaching the search-overlay loader here
  // makes the keyboard shortcut available platform-wide without per-page wiring.
  if (!document.querySelector('script[data-wh-search]')) {
    const s = document.createElement('script');
    s.src = 'search-overlay.js';
    s.async = true;
    s.setAttribute('data-wh-search', '1');
    document.head.appendChild(s);
  }

  // ─── Phase B.3: Lazy-load Voice Handler so the mic button is on every page.
  // voice-handler.js mounts a floating mic button + overlay, calls voice-transcribe
  // then voice-action-router, and dispatches structured intents to per-page
  // handlers registered via WHVoice.register(kind, fn).
  if (!document.querySelector('script[data-wh-voice]')) {
    const v = document.createElement('script');
    v.src = 'voice-handler.js';
    v.async = true;
    v.setAttribute('data-wh-voice', '1');
    document.head.appendChild(v);
  }

  // ─── Tool Registry ────────────────────────────────────────────────────────────
  // section: null = no header (home only) | string = group label shown in All Tools grid
  // roles: undefined = universal (visible in every mode) | array = visible only in those modes
  //        Modes: 'field' | 'supervisor' | 'engineer'  ('all' shows everything)
  const TOOLS = [
    { label: 'Home',         href: 'index.html',        match: ['index', '/'],         section: null,
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H4a1 1 0 01-1-1V9.5z"/><path d="M9 21V12h6v9"/></svg>` },

    // ── Field Work: what you do every shift on the floor ─────────────────────
    { label: 'Logbook',      href: 'logbook.html',      match: ['logbook'],            section: 'Field Work', roles: ['field','supervisor'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/><line x1="8" y1="7" x2="16" y2="7"/><line x1="8" y1="11" x2="16" y2="11"/><line x1="8" y1="15" x2="12" y2="15"/></svg>` },
    { label: 'Inventory',    href: 'inventory.html',    match: ['inventory'],          section: 'Field Work', roles: ['field','supervisor'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>` },
    { label: 'Day Planner',  href: 'dayplanner.html',   match: ['dayplanner'],         section: 'Field Work', roles: ['field','supervisor'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="8" y1="14" x2="8" y2="14" stroke-width="3" stroke-linecap="round"/><line x1="12" y1="14" x2="12" y2="14" stroke-width="3" stroke-linecap="round"/><line x1="16" y1="14" x2="16" y2="14" stroke-width="3" stroke-linecap="round"/></svg>` },

    // ── Your Team: team operations and collaboration ──────────────────────────
    { label: 'WorkHive',     href: 'hive.html',         match: ['hive'],               section: 'Your Team', roles: ['supervisor'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>` },
    { label: 'PM Scheduler', href: 'pm-scheduler.html', match: ['pm-scheduler'],       section: 'Your Team', roles: ['field','supervisor'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><path d="M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"/></svg>` },
    { label: 'Community',    href: 'community.html',    match: ['community'],          section: 'Your Team', /* universal */
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/><line x1="12" y1="21" x2="12" y2="21" stroke-width="3" stroke-linecap="round"/></svg>` },

    // ── Intelligence: AI, analytics, and predictions ──────────────────────────
    // Analytics Report MUST be listed before Analytics — both paths contain
    // 'analytics', and getCurrentTool() returns the first match in iteration order.
    // Phase B: hidden from primary nav, accessible as a button inside analytics.html.
    { label: 'Analytics Report', href: 'analytics-report.html', match: ['analytics-report'], section: 'Intelligence', hidden: true, roles: ['supervisor','engineer'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/><line x1="9" y1="9" x2="11" y2="9"/></svg>` },
    { label: 'Analytics',    href: 'analytics.html',    match: ['analytics'],          section: 'Intelligence', roles: ['supervisor','engineer'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg>` },
    { label: 'Predictive ML', href: 'predictive.html',  match: ['predictive'],         section: 'Intelligence', roles: ['supervisor','engineer'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>` },
    { label: 'AI Assistant', href: 'assistant.html',    match: ['assistant'],          section: 'Intelligence', /* universal */
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/><line x1="9" y1="10" x2="9" y2="10" stroke-width="3" stroke-linecap="round"/><line x1="12" y1="10" x2="12" y2="10" stroke-width="3" stroke-linecap="round"/><line x1="15" y1="10" x2="15" y2="10" stroke-width="3" stroke-linecap="round"/></svg>`,
      accent: true },
    { label: 'PH Intelligence', href: 'ph-intelligence.html', match: ['ph-intelligence'], section: 'Intelligence', roles: ['supervisor','engineer'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>` },
    { label: 'Asset Hub',    href: 'asset-hub.html',    match: ['asset-hub'],          section: 'Intelligence', roles: ['supervisor','engineer'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="9"/><line x1="12" y1="3" x2="12" y2="9"/><line x1="12" y1="15" x2="12" y2="21"/><line x1="3" y1="12" x2="9" y2="12"/><line x1="15" y1="12" x2="21" y2="12"/></svg>` },
    { label: 'Alert Hub',    href: 'alert-hub.html',    match: ['alert-hub'],          section: 'Intelligence', roles: ['supervisor'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 00-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>` },
    { label: 'Audit Log',    href: 'audit-log.html',    match: ['audit-log'],          section: 'Intelligence', roles: ['supervisor'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/><circle cx="12" cy="9.5" r="1"/></svg>` },
    { label: 'Shift Brain',  href: 'shift-brain.html',  match: ['shift-brain'],        section: 'Intelligence',
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/><path d="M12 3v2M21 12h-2M12 21v-2M3 12h2"/></svg>` },

    // ── Build & Projects: engineering and project work ────────────────────────
    { label: 'Eng. Design',  href: 'engineering-design.html', match: ['engineering-design'], section: 'Build & Projects', roles: ['engineer'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 20h20"/><path d="M5 20V10l7-7 7 7v10"/><path d="M9 20v-5h6v5"/></svg>` },
    { label: 'Project Manager', href: 'project-manager.html', match: ['project-manager'], section: 'Build & Projects', roles: ['supervisor','engineer'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>` },
    // Phase B: hidden from primary nav, accessible as the "Print Report" button inside project-manager.html.
    { label: 'Project Report', href: 'project-report.html', match: ['project-report'],  section: 'Build & Projects', hidden: true, roles: ['supervisor','engineer'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>` },

    // ── Grow: professional development ────────────────────────────────────────
    { label: 'Skill Matrix', href: 'skillmatrix.html',  match: ['skillmatrix'],        section: 'Grow',
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"/></svg>` },
    { label: 'Achievements', href: 'achievements.html', match: ['achievements'],       section: 'Grow',
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="6"/><path d="M15.477 12.89L17 22l-5-3-5 3 1.523-9.11"/></svg>` },

    // ── Connect: marketplace and integrations ─────────────────────────────────
    { label: 'Marketplace',  href: 'marketplace.html',  match: ['marketplace'],        section: 'Connect', /* universal */
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/></svg>` },
    // Phase B: hidden from primary nav, accessible as the "Send" button inside analytics.html.
    { label: 'Report Sender', href: 'report-sender.html', match: ['report-sender'],    section: 'Connect', hidden: true, roles: ['supervisor'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>` },
    { label: 'CMMS Integration', href: 'integrations.html', match: ['integrations'],  section: 'Connect', roles: ['supervisor'],
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>` },
    // public-feed.html: public read-only page — linked from index.html, not the app nav
  ];

  // ─── Role Mode (Phase D) ──────────────────────────────────────────────────────
  // Persisted user choice for which subset of tools to show.
  // 'all' is the default — existing users see everything until they switch.
  // 'field' / 'supervisor' / 'engineer' filter to role-tagged tools.
  // Tools without a `roles` array are universal (always visible).
  var MODE_KEY = 'wh_nav_mode';
  var MODES = [
    { id: 'all',        label: 'All',        icon: '⊞' },
    { id: 'field',      label: 'Field',      icon: '🔧' },
    { id: 'supervisor', label: 'Supervisor', icon: '👷' },
    { id: 'engineer',   label: 'Engineer',   icon: '📐' },
  ];

  function getMode() {
    var v = localStorage.getItem(MODE_KEY);
    return MODES.some(function(m){ return m.id === v; }) ? v : 'all';
  }
  function setMode(id) {
    if (!MODES.some(function(m){ return m.id === id; })) return;
    localStorage.setItem(MODE_KEY, id);
  }

  function isVisibleInMode(tool, mode) {
    if (tool.hidden) return false;            // Phase B: kept reachable via parent buttons only
    if (mode === 'all') return true;
    if (!tool.roles || !tool.roles.length) return true;  // universal tool
    return tool.roles.indexOf(mode) !== -1;
  }

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
    // Phase B: hidden tools never appear in the Recent quick row.
    // Phase D: also filter by current role mode so the recent row matches the All Tools grid.
    var mode = getMode();
    var visible = TOOLS.filter(function(t){ return isVisibleInMode(t, mode); });
    try {
      var c = JSON.parse(localStorage.getItem(CLICK_KEY) || '{}');
      return visible.slice()
        .sort(function(a, b) { return (c[b.href] || 0) - (c[a.href] || 0); })
        .slice(0, n);
    } catch (_) {
      return visible.slice(0, n);
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

    /* All-tools grid — with section headers spanning full width.
       Phase B: tools marked hidden:true don't appear (reachable via parent buttons).
       Phase D: tools are also filtered by current role mode. Section headers
       only render when the section actually has at least one visible tool. */
    const _mode = getMode();
    const VISIBLE_TOOLS = TOOLS.filter(t => isVisibleInMode(t, _mode));
    let _lastSection = null;
    const tilesHTML = VISIBLE_TOOLS.reduce((acc, t) => {
      // Insert section header when section changes (skip null = Home)
      if (t.section && t.section !== _lastSection) {
        _lastSection = t.section;
        acc += `<p class="wh-hub-section-label wh-hub-section-break">${t.section}</p>`;
      }
      const isCurrent = t === current;
      acc += `<a href="${t.href}" class="wh-hub-tile${isCurrent ? ' active' : ''}${t.accent ? ' accent' : ''}" ${isCurrent ? 'aria-current="page"' : ''}>
        <span class="wh-hub-tile-icon">${t.icon}</span>
        <span class="wh-hub-tile-label">${t.label}</span>
        ${isCurrent ? '<span class="wh-hub-tile-dot"></span>' : ''}
      </a>`;
      return acc;
    }, '');

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
          width: 400px;
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
        /* Section breaks inside the all-tools grid span all columns */
        .wh-hub-section-break {
          grid-column: 1 / -1;
          margin-top: 14px;
          padding-top: 12px;
          border-top: 1px solid rgba(255,255,255,0.05);
        }
        .wh-hub-section-break:first-child,
        #wh-hub-tiles > .wh-hub-section-break:first-child {
          margin-top: 0; padding-top: 0; border-top: none;
        }
        .wh-hub-section-break.hidden { display: none !important; }

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

        /* ── Search bar ── */
        #wh-hub-search-wrap {
          position: relative; margin-bottom: 10px;
        }
        #wh-hub-search {
          width: 100%; background: rgba(255,255,255,0.06);
          border: 1px solid rgba(255,255,255,0.1); border-radius: 10px;
          padding: 8px 32px 8px 32px;
          font-size: 16px; /* exact 16px — iOS Safari auto-zooms on any input < 16px */
          color: rgba(255,255,255,0.85);
          font-family: 'Poppins', sans-serif; outline: none;
          transition: border-color 0.15s, background 0.15s;
        }
        #wh-hub-search::placeholder { color: rgba(255,255,255,0.3); }
        #wh-hub-search:focus {
          border-color: rgba(247,162,27,0.5); background: rgba(255,255,255,0.09);
        }
        #wh-hub-search-icon {
          position: absolute; left: 10px; top: 50%; transform: translateY(-50%);
          color: rgba(255,255,255,0.3); pointer-events: none; display: flex;
        }
        #wh-hub-search-kbd {
          position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
          background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12);
          border-radius: 4px; padding: 1px 5px; font-size: 9px; color: rgba(255,255,255,0.3);
          font-family: monospace; pointer-events: none;
        }
        #wh-hub-no-results {
          text-align: center; padding: 16px 0; font-size: 11px; color: rgba(255,255,255,0.3);
          display: none;
        }

        /* ── All Tools grid — 4 columns, always visible ── */
        #wh-hub-tiles {
          display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;
          max-height: 260px; overflow-y: auto; scrollbar-width: thin;
          scrollbar-color: rgba(247,162,27,0.2) transparent;
          margin-top: 6px;
        }
        #wh-hub-tiles::-webkit-scrollbar { width: 4px; }
        #wh-hub-tiles::-webkit-scrollbar-thumb { background: rgba(247,162,27,0.2); border-radius: 2px; }
        .wh-hub-tile.hidden { display: none; }

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

        /* ── Role mode switcher (Phase D) ── */
        #wh-hub-mode {
          display: flex;
          gap: 4px;
          padding: 4px;
          background: rgba(0,0,0,0.25);
          border: 1px solid rgba(255,255,255,0.05);
          border-radius: 10px;
          margin: 0 0 10px;
        }
        .wh-hub-mode-btn {
          flex: 1;
          padding: 6px 4px;
          background: transparent;
          border: none;
          border-radius: 7px;
          color: rgba(255,255,255,0.4);
          font-family: inherit;
          font-size: 10px;
          font-weight: 600;
          letter-spacing: 0.02em;
          cursor: pointer;
          transition: background 0.15s, color 0.15s;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 4px;
          white-space: nowrap;
        }
        .wh-hub-mode-btn:hover { color: rgba(255,255,255,0.7); }
        .wh-hub-mode-btn.active {
          background: rgba(247,162,27,0.15);
          color: #F7A21B;
        }
        .wh-hub-mode-icon { font-size: 11px; line-height: 1; }

        /* ── Mobile ── */
        @media (max-width: 480px) {
          #wh-hub { bottom: max(16px, env(safe-area-inset-bottom)); right: 16px; }
          #wh-hub-panel { width: calc(100vw - 32px); }
          #wh-hub-tiles { grid-template-columns: repeat(3, 1fr); }
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
          <span>WorkHive</span>
          <strong>${current.label}</strong>
        </div>

        <!-- Phase E.3c: Global Search trigger — opens Cmd+K overlay on mobile too -->
        <button type="button" id="wh-hub-global-search" style="display:flex; align-items:center; gap:8px; width:100%; min-height:44px; padding:10px 12px; margin:0 0 8px; background:rgba(247,162,27,0.08); border:1px solid rgba(247,162,27,0.2); border-radius:10px; color:#F7A21B; font-family:inherit; font-size:12px; font-weight:600; cursor:pointer; text-align:left;" aria-label="Open global search">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <span style="flex:1;">Search assets, jobs, parts, PMs</span>
          <span style="font-size:9px; font-weight:700; padding:2px 5px; background:rgba(247,162,27,0.15); border:1px solid rgba(247,162,27,0.3); border-radius:4px;">⌘K</span>
        </button>

        <!-- Search bar -->
        <div id="wh-hub-search-wrap">
          <span id="wh-hub-search-icon">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
          </span>
          <input id="wh-hub-search" type="search" placeholder="Search tools…" autocomplete="off" aria-label="Search tools">
          <span id="wh-hub-search-kbd">Ctrl K</span>
        </div>

        <!-- Role mode switcher (Phase D) — filters which tools show below -->
        <div id="wh-hub-mode" role="tablist" aria-label="Tool view mode">
          ${MODES.map(function(m){
            var active = m.id === getMode() ? ' active' : '';
            return '<button type="button" class="wh-hub-mode-btn' + active +
                   '" data-mode="' + m.id + '" role="tab" aria-selected="' + (active ? 'true' : 'false') + '">' +
                   '<span class="wh-hub-mode-icon">' + m.icon + '</span>' + m.label + '</button>';
          }).join('')}
        </div>

        <!-- Recent row -->
        <div id="wh-hub-quick">
          <p class="wh-hub-section-label">Recent</p>
          <div id="wh-hub-quick-row">${quickHTML}</div>
        </div>

        <div class="wh-hub-divider"></div>

        <!-- All Tools — 4-col grid, always visible, scrollable -->
        <p class="wh-hub-section-label">All Tools</p>
        <div id="wh-hub-no-results">No tools match your search.</div>
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
    // Reveal floating-AI button alongside the panel (floating-ai.js listens to this class)
    document.body.classList.add('wh-hub-open');
  }

  function closeHub() {
    isOpen = false;
    document.getElementById('wh-hub').classList.remove('hub-open');
    document.getElementById('wh-hub-fab').classList.remove('open');
    document.getElementById('wh-hub-fab').setAttribute('aria-expanded', 'false');
    document.getElementById('wh-hub-panel').classList.remove('open');
    document.body.classList.remove('wh-hub-open');
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
      if (e.key === 'Escape' && isOpen) {
        const q = document.getElementById('wh-hub-search');
        if (q && q.value) { q.value = ''; filterTools(''); }
        else closeHub();
        return;
      }
      // Ctrl+K / Cmd+K — open hub + focus search
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (!isOpen) openHub();
        setTimeout(() => document.getElementById('wh-hub-search')?.focus(), 60);
      }
    });

    document.addEventListener('click', e => {
      const hub   = document.getElementById('wh-hub');
      const aiWgt = document.getElementById('wh-ai-widget');
      // Don't close the hub when clicking the floating-AI widget — the AI
      // button lives outside #wh-hub so would otherwise trigger closeHub()
      // before the AI click handler could fire, making the button disappear.
      if (isOpen && hub && !hub.contains(e.target) && !(aiWgt && aiWgt.contains(e.target))) closeHub();
    });

    /* Search — real-time filter on All Tools grid */
    const searchInput = document.getElementById('wh-hub-search');
    const noResults   = document.getElementById('wh-hub-no-results');
    if (searchInput) {
      searchInput.addEventListener('input', function() { filterTools(this.value); });
      // Clear search when panel closes
      document.getElementById('wh-hub-fab')?.addEventListener('click', function() {
        setTimeout(() => { if (!isOpen && searchInput) { searchInput.value = ''; filterTools(''); } }, 50);
      });
    }

    /* Phase E.3c: Global Search trigger inside the nav-hub panel.
       Mobile users have no Cmd+K so they need a tappable entry point. */
    document.getElementById('wh-hub-global-search')?.addEventListener('click', function () {
      if (window.WHSearch && typeof window.WHSearch.open === 'function') {
        closeHub();              // tidy: hide the nav-hub before showing the overlay
        window.WHSearch.open();
      }
    });

    /* Mode switcher — Phase D. Click changes mode, persists, and rebuilds the
       grid + Recent row in place so the user sees the filtered view immediately. */
    document.querySelectorAll('#wh-hub-mode .wh-hub-mode-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var newMode = btn.getAttribute('data-mode');
        if (newMode === getMode()) return;
        setMode(newMode);
        // Update active state on all buttons
        document.querySelectorAll('#wh-hub-mode .wh-hub-mode-btn').forEach(function(b) {
          var on = b.getAttribute('data-mode') === newMode;
          b.classList.toggle('active', on);
          b.setAttribute('aria-selected', on ? 'true' : 'false');
        });
        // Rebuild only the grid + recent row (faster than re-rendering the whole panel)
        rebuildToolGrids();
      });
    });

    function rebuildToolGrids() {
      var mode = getMode();
      var visible = TOOLS.filter(function(t) { return isVisibleInMode(t, mode); });

      // Recent row
      var quickRow = document.getElementById('wh-hub-quick-row');
      if (quickRow) {
        var quickTools = getQuickTools(4);
        quickRow.innerHTML = quickTools.map(function(t) {
          var isCurrent = t === current;
          var shortLabel = t.label.length > 8 ? t.label.split(' ')[0] : t.label;
          return '<a href="' + t.href + '" class="wh-hub-quick-tile' + (isCurrent ? ' active' : '') +
                 '" ' + (isCurrent ? 'aria-current="page"' : '') + ' title="' + t.label + '">' +
                 '<span class="wh-hub-quick-icon">' + t.icon + '</span>' +
                 '<span class="wh-hub-quick-label">' + shortLabel + '</span></a>';
        }).join('');
      }

      // All Tools grid
      var tilesEl = document.getElementById('wh-hub-tiles');
      if (tilesEl) {
        var lastSec = null;
        var html = visible.reduce(function(acc, t) {
          if (t.section && t.section !== lastSec) {
            lastSec = t.section;
            acc += '<p class="wh-hub-section-label wh-hub-section-break">' + t.section + '</p>';
          }
          var isCurrent = t === current;
          acc += '<a href="' + t.href + '" class="wh-hub-tile' + (isCurrent ? ' active' : '') +
                 (t.accent ? ' accent' : '') + '" ' + (isCurrent ? 'aria-current="page"' : '') + '>' +
                 '<span class="wh-hub-tile-icon">' + t.icon + '</span>' +
                 '<span class="wh-hub-tile-label">' + t.label + '</span>' +
                 (isCurrent ? '<span class="wh-hub-tile-dot"></span>' : '') + '</a>';
          return acc;
        }, '');
        tilesEl.innerHTML = html;
      }

      // Empty state — if mode filter eliminates everything visible (rare)
      if (noResults) noResults.style.display = visible.length ? 'none' : 'block';
    }

    function filterTools(q) {
      const tiles  = document.querySelectorAll('#wh-hub-tiles .wh-hub-tile');
      const breaks = document.querySelectorAll('#wh-hub-tiles .wh-hub-section-break');
      const query  = q.trim().toLowerCase();
      let visible  = 0;
      tiles.forEach(tile => {
        const label = (tile.querySelector('.wh-hub-tile-label')?.textContent || '').toLowerCase();
        const href  = (tile.getAttribute('href') || '').toLowerCase();
        const match = !query || label.includes(query) || href.includes(query);
        tile.classList.toggle('hidden', !match);
        if (match) visible++;
      });
      // Hide section break headers while searching (grid becomes a flat filtered list)
      breaks.forEach(b => b.classList.toggle('hidden', !!query));
      if (noResults) noResults.style.display = (query && visible === 0) ? 'block' : 'none';
      // Also hide Recent row when searching (search shows all matches in the grid)
      const quickSection = document.getElementById('wh-hub-quick');
      if (quickSection) quickSection.style.display = query ? 'none' : '';
      const divider = document.querySelector('.wh-hub-divider');
      if (divider) divider.style.display = query ? 'none' : '';
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
