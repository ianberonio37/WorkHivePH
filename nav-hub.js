/**
// capability: display_nav_hub
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

  // ─── Centralized behavioural patterns (wh-patterns.js · Axis 3): the canonical
  // launcher-defer / click-outside / reveal-decouple / panel-cap idioms the shared
  // chrome delegates to. Loaded FIRST so window.WHPatterns is present before any chrome
  // wires its events (clicks happen long after load; a defensive fallback covers the gap).
  if (!document.querySelector('script[data-wh-patterns]')) {
    const wp = document.createElement('script');
    wp.src = 'wh-patterns.js';
    wp.async = false;
    wp.setAttribute('data-wh-patterns', '1');
    document.head.appendChild(wp);
  }

  // ─── Canonical client RBAC SSOT (wh-roles.js · +RBAC): window.WHRoles — the ONE role
  // reader + capability map, replacing scattered `localStorage.getItem('wh_hive_role')` +
  // raw role-string checks. Client UX gate only (server RLS is the authority). Loaded early.
  if (!document.querySelector('script[data-wh-roles]')) {
    const wr = document.createElement('script');
    wr.src = 'wh-roles.js';
    wr.async = false;
    wr.setAttribute('data-wh-roles', '1');
    document.head.appendChild(wr);
  }

  // ─── Arc Y · Y1: Lazy-load the Wayfinding chrome (in-app Back + breadcrumb +
  // scroll-restore + deep-link highlight) so every page gets "where am I / how do
  // I get back" without per-page wiring. Closes the back:N on ~30 pages + fixes
  // asset-hub's hard-coded back in-place (finding F3). See wayfinding.js.
  if (!document.querySelector('script[data-wh-wayfind]')) {
    const wf = document.createElement('script');
    wf.src = 'wayfinding.js';
    wf.async = true;
    wf.setAttribute('data-wh-wayfind', '1');
    document.head.appendChild(wf);
  }

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

  // ─── Persona Contract Phase 4: shared TTS helper (speakPersona).
  // Lazy-loaded alongside voice-handler so any page with nav-hub.js gets
  // the audio playback path for free.
  if (!document.querySelector('script[data-wh-tts]')) {
    const t = document.createElement('script');
    t.src = 'wh-tts.js';
    t.async = true;
    t.setAttribute('data-wh-tts', '1');
    document.head.appendChild(t);
  }

  // ─── Persona Contract Phase 3: client-side companion-block builder.
  // Mirror of supabase/functions/_shared/persona.ts. Used by surfaces
  // that need the persona name on the client side (assistant.html,
  // and the companion launcher's persona-toggle UI). The launcher itself
  // sends just the persona NAME to ai-gateway; the agent then calls
  // buildPersonaBlock() server-side. See WORKHIVE_PERSONA_CONTRACT.md.
  if (!document.querySelector('script[data-wh-persona]')) {
    const p = document.createElement('script');
    p.src = 'wh-persona.js';
    p.async = false; // load before companion-launcher.js consumes window.getCompanionBlock
    p.setAttribute('data-wh-persona', '1');
    document.head.appendChild(p);
  }

  // ─── Universal Feedback FAB: floating bottom-right button + slide-in
  // panel for sending bugs / ideas / questions / reviews / praise. Posts
  // to platform_feedback (migration 20260519000002), surfaces in the
  // Founder Console's #sec-feel section. Free-tier: no email, no n8n —
  // Realtime subscription on the admin side handles routing.
  if (!document.querySelector('script[data-wh-feedback]') &&
      !document.querySelector('script[src*="wh-feedback-fab.js"]')) {
    const fb = document.createElement('script');
    fb.src = 'wh-feedback-fab.js';
    fb.async = true;
    fb.setAttribute('data-wh-feedback', '1');
    document.head.appendChild(fb);
  }

  // ─── Companion Streamline Steps A+C: companion-launcher.js (formerly
  // floating-ai.js) carries the Hezekiah/Zaniah avatar + chat panel + inline
  // mic on every nav-enabled page. Routes through ai-gateway with
  // agent="voice-journal" — same backend as voice-journal.html and
  // assistant.html, so the worker experiences ONE companion across
  // three entry points. assistant.html is the only page that opts out
  // (its inline init short-circuits when path includes /assistant).
  if (!document.querySelector('script[data-wh-companion-launcher]') &&
      !document.querySelector('script[src*="companion-launcher.js"]')) {
    const f = document.createElement('script');
    f.src = 'companion-launcher.js';
    f.async = false; // depends on wh-persona.js (loaded above) for the avatar
    f.setAttribute('data-wh-companion-launcher', '1');
    document.head.appendChild(f);
  }

  // ─── learn-link.js: connect this feature PAGE back to its /learn/ GUIDE
  // (Ian 2026-07-07: "my feature pages and landing page are complete strangers").
  // A one-tap, dismissible "Read the guide" pill on every tool page, sourced from
  // /learn_links.json. Absolute src so it loads at any page depth; the script
  // itself no-ops on the learn hub + inside articles. Defensive, never blocks.
  if (!document.querySelector('script[data-wh-learn-link]') &&
      !document.querySelector('script[src*="learn-link.js"]')) {
    const ll = document.createElement('script');
    ll.src = '/learn-link.js';
    ll.async = true;
    ll.setAttribute('data-wh-learn-link', '1');
    document.head.appendChild(ll);
  }

  // ─── Centralized design tokens (tokens.css): the SINGLE source of truth for the
  // brand palette / radii / type / shadows (var(--wh-*)). nav-hub loads on every page,
  // so injecting the token sheet here GUARANTEES the design-system vocabulary is present
  // for ALL shared chrome (this hub, the companion, feedback + connectivity widgets) —
  // so those components can consume var(--wh-orange) etc. instead of hardcoding hex that
  // drifts. Idempotent: ~28 pages already <link> it in <head>; this only fills the gap
  // on the rest. Mirrors the wh-icons.css centralisation just below.
  if (!document.querySelector('link[href*="tokens.css"]')) {
    const tk = document.createElement('link');
    tk.rel = 'stylesheet';
    tk.href = 'tokens.css';
    document.head.appendChild(tk);
  }

  // ─── Centralized icon library (wh-icons.css): nav-hub loads on every page, so
  // ensuring the emoji icon-library link here makes the `.ic ic-*` classes resolve
  // platform-wide without per-page wiring — the single source of truth for icons.
  if (!document.querySelector('link[href*="wh-icons.css"]')) {
    const ic = document.createElement('link');
    ic.rel = 'stylesheet';
    ic.href = 'wh-icons.css';
    document.head.appendChild(ic);
  }

  // ─── Tool Registry ────────────────────────────────────────────────────────────
  // section: null = no header (home only) | string = group label shown in All Tools grid
  // roles: undefined = universal (visible in every mode) | array = visible only in those modes
  //        Modes: 'field' | 'supervisor' | 'engineer'  ('all' shows everything)
  const TOOLS = [
    { label: 'Home',         href: 'index.html',        match: ['index', '/'],         section: null,
      icon: `<span class="ic ic-home" aria-hidden="true"></span>` },

    // ── Field Work: what you do every shift on the floor ─────────────────────
    { label: 'Logbook',      href: 'logbook.html',      match: ['logbook'],            section: 'Field Work', roles: ['field','supervisor'],
      icon: `<span class="ic ic-logbook" aria-hidden="true"></span>` },
    { label: 'Inventory',    href: 'inventory.html',    match: ['inventory'],          section: 'Field Work', roles: ['field','supervisor'],
      icon: `<span class="ic ic-parts" aria-hidden="true"></span>` },
    { label: 'Day Planner',  href: 'dayplanner.html',   match: ['dayplanner'],         section: 'Field Work', roles: ['field','supervisor'],
      icon: `<span class="ic ic-calendar" aria-hidden="true"></span>` },

    // ── Your Team: team operations and collaboration ──────────────────────────
    { label: 'WorkHive',     href: 'hive.html',         match: ['hive'],               section: 'Your Team', roles: ['supervisor'],
      icon: `<span class="ic ic-brand" aria-hidden="true"></span>` },
    { label: 'PM Scheduler', href: 'pm-scheduler.html', match: ['pm-scheduler'],       section: 'Your Team', roles: ['field','supervisor'],
      icon: `<span class="ic ic-maintenance" aria-hidden="true"></span>` },
    { label: 'Community',    href: 'community.html',    match: ['community'],          section: 'Your Team', /* universal */
      icon: `<span class="ic ic-community" aria-hidden="true"></span>` },

    // ── Intelligence: AI, analytics, and predictions ──────────────────────────
    // Analytics Report MUST be listed before Analytics — both paths contain
    // 'analytics', and getCurrentTool() returns the first match in iteration order.
    // Phase B: hidden from primary nav, accessible as a button inside analytics.html.
    { label: 'Reports', href: 'analytics-report.html', match: ['analytics-report', 'report-sender'], section: 'Intelligence', hidden: true, roles: ['supervisor','engineer'],
      icon: `<span class="ic ic-reports" aria-hidden="true"></span>` },
    { label: 'Analytics',    href: 'analytics.html',    match: ['analytics'],          section: 'Intelligence', roles: ['supervisor','engineer'],
      icon: `<span class="ic ic-analytics" aria-hidden="true"></span>` },
    // Phase 4 (2026-06-10): predictive.html RETIRED — delisted entirely. Its jobs
    // live in Asset Hub (per-asset risk 360, same v_risk_truth) and the Predictive
    // phase inside analytics.html. File kept on disk so old deep-links don't 404.
    // Phase 4.1 — AI Quality + ROI dashboard. Stair 2+ gated inside the page;
    // supervisor-only nav entry so workers don't see the link they can't act on.
    // Hidden from primary nav, surfaced via the "AI Quality" button on hive.html.
    { label: 'AI Quality + ROI', href: 'ai-quality.html', match: ['ai-quality'],       section: 'Intelligence', hidden: true, roles: ['supervisor'],
      icon: `<span class="ic ic-ai-quality" aria-hidden="true"></span>` },
    // Phase 5 Track C — Plant Connections Console. STREAMLINE F7 (2026-06-13):
    // folded into the unified "Connections" nav entry (section Connect, below) —
    // reached via the Connections tab bar on integrations.html. Page kept on disk
    // + cached (no sw.js change), so old deep-links + the tab still resolve.
    { label: 'AI Assistant', href: 'assistant.html',    match: ['assistant'],          section: 'Intelligence', /* universal */
      icon: `<span class="ic ic-ai" aria-hidden="true"></span>`,
      accent: true },
    // Phase H.2: hidden, surfaced via the Network tab inside analytics.html.
    { label: 'PH Intelligence', href: 'ph-intelligence.html', match: ['ph-intelligence'], section: 'Intelligence', hidden: true, roles: ['supervisor','engineer'],
      icon: `<span class="ic ic-ph-intel" aria-hidden="true"></span>` },
    { label: 'Asset Hub',    href: 'asset-hub.html',    match: ['asset-hub'],          section: 'Intelligence', roles: ['supervisor','engineer'],
      icon: `<span class="ic ic-asset" aria-hidden="true"></span>` },
    { label: 'Alert Hub',    href: 'alert-hub.html',    match: ['alert-hub'],          section: 'Intelligence', roles: ['supervisor'],
      icon: `<span class="ic ic-alert" aria-hidden="true"></span>` },
    // Phase H.2: hidden, surfaced via the "Audit Log" button on hive.html.
    { label: 'Audit Log',    href: 'audit-log.html',    match: ['audit-log'],          section: 'Intelligence', hidden: true, roles: ['supervisor'],
      icon: `<span class="ic ic-audit" aria-hidden="true"></span>` },
    // Phase H.2: hidden, surfaced via the "Voice Journal" button on logbook.html.
    { label: 'Voice Journal', href: 'voice-journal.html', match: ['voice-journal'],     section: 'Intelligence', hidden: true,
      icon: `<span class="ic ic-voice" aria-hidden="true"></span>` },
    // Phase H.2: hidden, surfaced via the Shift Brain tab inside analytics.html.
    { label: 'Shift Brain',  href: 'shift-brain.html',  match: ['shift-brain'],        section: 'Intelligence', hidden: true,
      icon: `<span class="ic ic-brain" aria-hidden="true"></span>` },

    // ── Build & Projects: engineering and project work ────────────────────────
    { label: 'Eng. Design',  href: 'engineering-design.html', match: ['engineering-design'], section: 'Build & Projects', roles: ['engineer'],
      icon: `<span class="ic ic-design" aria-hidden="true"></span>` },
    { label: 'Project Manager', href: 'project-manager.html', match: ['project-manager'], section: 'Build & Projects', roles: ['supervisor','engineer'],
      icon: `<span class="ic ic-project" aria-hidden="true"></span>` },
    // Phase B: hidden from primary nav, accessible as the "Print Report" button inside project-manager.html.
    { label: 'Project Report', href: 'project-report.html', match: ['project-report'],  section: 'Build & Projects', hidden: true, roles: ['supervisor','engineer'],
      icon: `<span class="ic ic-doc" aria-hidden="true"></span>` },

    // ── Grow: professional development ────────────────────────────────────────
    { label: 'Growth', href: 'skillmatrix.html',  match: ['skillmatrix', 'achievements'],        section: 'Grow',
      icon: `<span class="ic ic-growth" aria-hidden="true"></span>` },
    { label: 'Resume Builder', href: 'resume.html', match: ['resume'],               section: 'Grow',
      icon: `<span class="ic ic-resume" aria-hidden="true"></span>` },
    // STREAMLINE F5 (2026-06-13): Achievements folded into the unified "Growth" nav
    // entry (skillmatrix.html) — reached via the Growth tab bar. Page kept on disk + cached.

    // ── Connect: marketplace and integrations ─────────────────────────────────
    { label: 'Marketplace',  href: 'marketplace.html',  match: ['marketplace'],        section: 'Connect', /* universal */
      icon: `<span class="ic ic-cart" aria-hidden="true"></span>` },
    // Phase B: hidden from primary nav, accessible as the "Send" button inside analytics.html.
    // STREAMLINE F6 (2026-06-13): Report Sender folded into the unified "Reports" nav
    // entry (analytics-report.html) — reached via the Reports tab bar. Page kept on disk.
    { label: 'Connections', href: 'integrations.html', match: ['integrations', 'plant-connections'],  section: 'Connect', roles: ['supervisor'],
      icon: `<span class="ic ic-integrations" aria-hidden="true"></span>` },
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

  // Phase H.1 (2026-05-12 home streamline): on first load, default to the
  // user's HIVE_ROLE so a new worker doesn't see all 33 tools at once. The
  // 'all' fallback applies only when no role hint is in localStorage (solo
  // mode + new install). Existing users with an explicit choice keep it.
  function _defaultMode() {
    var role = localStorage.getItem('wh_hive_role') || '';
    // role-allow: nav display mode ('field' | 'supervisor' | 'engineer'), not an auth role
    if (role === 'supervisor') return 'supervisor'; // role-allow role-check-allow: nav-hub IS the role->mode SSOT (maps auth role to a display mode)
    if (role === 'engineer')   return 'engineer';   // role-allow role-check-allow: nav-hub IS the role->mode SSOT
    // Workers default to 'field'. Solo mode (no hive) gets 'field' too --
    // it's the tightest tool set and matches what a lone tech needs day-to-day.
    return 'field';
  }
  function getMode() {
    var v = localStorage.getItem(MODE_KEY);
    if (MODES.some(function(m){ return m.id === v; })) return v;
    // Persist the role-derived default so the analytics + chip surfaces
    // can read it the same way without re-deriving on every page.
    var d = _defaultMode();
    try { localStorage.setItem(MODE_KEY, d); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
    return d;
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
    } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
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

  // ─── Community activity badge (cross-page, mirrors the companion FAB nudge) ────
  // How many new community posts/replies (by OTHERS) have landed in this worker's
  // hive since they last opened community.html. Read-only, best-effort, hive-scoped.
  let _communityUnread = 0;

  // Real Supabase client resolver — same singleton discipline as companion-launcher's
  // _whClient(): prefer the page's built client, else build the getDb() singleton.
  // Returns null (→ no badge, no console 401) if supabase-js/getDb aren't ready.
  function _whNavClient() {
    try {
      if (typeof window === 'undefined') return null;
      if (window._whSupabaseClient && window._whSupabaseClient.functions) return window._whSupabaseClient;
      if (typeof window.getDb === 'function' && window.supabase) {
        const url = window.WH_SUPABASE_URL || 'https://hzyvnjtisfgbksicrouu.supabase.co';
        const key = window.WH_SUPABASE_ANON_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
        return window.getDb(url, key);
      }
    } catch (_) { /* empty-catch-allow: best-effort, fall back to no badge */ }
    return null;
  }

  // Paint (or clear) the FAB dot + Community-tile count pill from _communityUnread.
  // Idempotent + re-run after rebuildToolGrids() so a mode switch keeps the badge.
  function _paintCommunityBadges() {
    const hub = document.getElementById('wh-hub');
    if (!hub) return;
    const n = _communityUnread;
    const label = n > 9 ? '9+' : String(n);
    // Every Community tile in the panel (Recent quick row + All Tools grid).
    hub.querySelectorAll('a[href="community.html"]').forEach(function (tile) {
      let b = tile.querySelector('.wh-hub-tile-badge');
      if (n > 0) {
        if (!b) {
          if (getComputedStyle(tile).position === 'static') tile.style.position = 'relative';
          b = document.createElement('span');
          b.className = 'wh-hub-tile-badge';
          b.setAttribute('aria-hidden', 'true');
          tile.appendChild(b);
        }
        b.textContent = label;
      } else if (b) {
        b.remove();
      }
    });
    // FAB dot + accessible label (screen readers get the count via aria-label).
    const fab = document.getElementById('wh-hub-fab');
    if (fab) {
      let dot = document.getElementById('wh-hub-fab-dot');
      if (n > 0) {
        if (!dot) {
          dot = document.createElement('span');
          dot.id = 'wh-hub-fab-dot';
          dot.setAttribute('aria-hidden', 'true');
          fab.appendChild(dot);
        }
        fab.setAttribute('aria-label', 'Open navigation hub: ' + label + ' new in Community');
      } else {
        if (dot) dot.remove();
        fab.setAttribute('aria-label', 'Open navigation hub');
      }
    }
  }

  // Count new community activity (by others) since the per-hive last-seen stamp
  // written by community.html. Two COUNT-only queries (head:true) → cheap. Fails
  // closed (no session / no hive / client not ready) so signed-out + landing pages
  // never query or 401. Skips the badge on community.html itself (it self-clears).
  async function checkCommunityActivity() {
    try {
      if (current && Array.isArray(current.match) && current.match.indexOf('community') !== -1) return;
      const db = _whNavClient();
      if (!db || !db.from) return;
      const hiveId = localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id') || null;
      if (!hiveId) return;
      let sess = null;
      try { sess = (await db.auth.getSession())?.data?.session || null; } catch (_) { sess = null; }
      if (!sess) return; // fail closed — never fire an RLS-gated read without a JWT
      const worker = (typeof window.restoreIdentityFromSession === 'function')
        ? await window.restoreIdentityFromSession(db)
        : (localStorage.getItem('wh_last_worker') || '');
      // Baseline: if never seen, look back 3 days so a returning worker sees recent
      // activity without being flooded. community.html stamps the real time on visit.
      const seenKey = 'wh_community_last_seen:' + hiveId;
      let since = localStorage.getItem(seenKey);
      if (!since) since = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
      let postQ = db.from('v_community_posts_truth')
        .select('id', { count: 'exact', head: true })
        .eq('hive_id', hiveId).is('deleted_at', null).gt('created_at', since);
      // canonical-allow: community_replies is forum thread detail (unread-badge reply COUNT for the hive) - single-surface community data, not a cross-surface KPI/aggregate, so no v_*_truth wrapper applies.
      let replyQ = db.from('community_replies')
        .select('post_id', { count: 'exact', head: true })
        .eq('hive_id', hiveId).gt('created_at', since);
      if (worker) { postQ = postQ.neq('author_name', worker); replyQ = replyQ.neq('author_name', worker); }
      const [pr, rr] = await Promise.all([postQ, replyQ]);
      const pc = (pr && typeof pr.count === 'number') ? pr.count : 0;
      const rc = (rr && typeof rr.count === 'number') ? rr.count : 0;
      _communityUnread = Math.max(0, pc + rc);
      _paintCommunityBadges();
    } catch (_) { /* empty-catch-allow: activity badge is best-effort */ }
  }

  // Wait for the page to build its Supabase client (many pages create it lazily),
  // then run the activity check once. Bounded retries so it never spins.
  function scheduleCommunityCheck() {
    let tries = 0;
    (function attempt() {
      tries++;
      if (_whNavClient()) { checkCommunityActivity(); return; }
      if (tries < 4) setTimeout(attempt, 1200);
    })();
  }

  // ─── Build Widget ─────────────────────────────────────────────────────────────
  function buildWidget() {
    // N1 safe translator. utils.js installs the locale floor (window._t + WH_LANG) and
    // loads BEFORE this file on every page that has both, so _t is normally present; the
    // pass-through keeps a page that somehow lacks it rendering EN rather than throwing.
    // This nav hub is the platform's most-shared chrome (31 pages) -- translating it here
    // is the design-system lever: ONE edit, 31 pages, instead of 31 page edits that drift.
    // Brand ("WorkHive"), the Ctrl-K shortcut and the page label are DATA/identity: EN.
    const _tt = (typeof window._t === 'function') ? window._t : function (en) { return en; };
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
          font-family: var(--wh-font, 'Poppins', sans-serif);
        }

        /* ── FAB ── */
        #wh-hub-fab {
          width: 56px;
          height: 56px;
          border-radius: 16px;
          background: linear-gradient(135deg, var(--wh-navy, #162032), var(--wh-navy-mid, #1F2E45));
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
          border-color: var(--wh-orange, #F7A21B);
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

        /* ── Community activity: unread dot on the FAB + count pill on the tile ──
           Mirrors the companion FAB nudge. The dot signals "something new lives in
           your tools" without opening the hub; the tile pill says exactly where. */
        #wh-hub-fab-dot {
          position: absolute;
          top: -3px; right: -3px;
          width: 13px; height: 13px;
          border-radius: 50%;
          background: var(--wh-orange, #F7A21B);
          border: 2px solid var(--wh-navy, #162032);
          box-shadow: 0 0 0 0 rgba(247,162,27,0.5);
          animation: wh-hub-dot-pulse 1.8s ease-in-out infinite;
          pointer-events: none;
        }
        @keyframes wh-hub-dot-pulse {
          0%,100% { box-shadow: 0 0 0 0 rgba(247,162,27,0.45); }
          50%     { box-shadow: 0 0 0 5px rgba(247,162,27,0); }
        }
        @media (max-width: 767px) { #wh-hub-fab-dot { animation: none; } }
        .wh-hub-tile-badge {
          position: absolute;
          top: 5px; right: 5px;
          min-width: 16px; height: 16px;
          padding: 0 4px;
          border-radius: 8px;
          background: var(--wh-orange, #F7A21B);
          color: #10192B;
          font-size: 9px; font-weight: 700; line-height: 16px;
          text-align: center;
          font-family: var(--wh-font, 'Poppins', sans-serif);
          box-shadow: 0 1px 4px rgba(0,0,0,0.4);
        }

        /* ── Panel ── */
        #wh-hub-panel {
          position: absolute;
          bottom: 68px;
          right: 0;
          width: 400px;
          background: linear-gradient(160deg, var(--wh-navy-mid, #1F2E45) 0%, var(--wh-navy, #162032) 100%);
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 20px;
          box-shadow: 0 24px 64px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.03);
          padding: 16px;
          opacity: 0;
          transform: translateY(10px) scale(0.96);
          pointer-events: none;
          transition: opacity 0.2s ease, transform 0.2s ease-out;
          /* FAB-CONSOLIDATION: the panel now carries the header pill + Companion/Feedback
             row at the TOP, so on short viewports it must never clip them off-screen (the
             panel grows upward from the FAB). Cap to the viewport and scroll the whole
             panel — the header/action row are then always reachable at scrollTop 0. */
          max-height: var(--wh-panel-max-h, calc(100dvh - 100px));
          overflow-y: auto;
          overscroll-behavior: contain;
          scrollbar-width: thin;
          scrollbar-color: rgba(247,162,27,0.2) transparent;
        }
        #wh-hub-panel::-webkit-scrollbar { width: 4px; }
        #wh-hub-panel::-webkit-scrollbar-thumb { background: rgba(247,162,27,0.2); border-radius: 2px; }
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
          color: rgba(255,255,255,0.6); /* WCAG AA */
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }
        #wh-hub-panel-header strong {
          font-size: 11px;
          font-weight: 600;
          color: var(--wh-orange, #F7A21B);
          letter-spacing: 0.04em;
        }

        /* ── Section labels ── */
        .wh-hub-section-label {
          font-size: 10px; font-weight: 600; letter-spacing: 0.1em;
          text-transform: uppercase; color: rgba(255,255,255,0.6); /* WCAG AA contrast over dark bg */
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
        .wh-hub-quick-tile.active .wh-hub-quick-icon { color: var(--wh-orange, #F7A21B); }
        .wh-hub-quick-icon { color: rgba(255,255,255,0.7); display:flex; }
        .wh-hub-quick-label {
          font-size: 9px; color: rgba(255,255,255,0.72); font-weight: 500; /* WCAG AA: 0.6 measured 4.32:1 (<4.5), 0.72 clears it */
          text-align: center; line-height: 1.2; font-family: var(--wh-font, 'Poppins', sans-serif);
        }
        .wh-hub-quick-tile.active .wh-hub-quick-label { color: var(--wh-orange, #F7A21B); }

        /* ── Divider ── */
        .wh-hub-divider { height: 1px; background: rgba(255,255,255,0.06); margin: 10px 0 6px; }

        /* ── All Tools toggle ── */
        #wh-hub-all-toggle {
          width: 100%; display: flex; align-items: center; justify-content: space-between;
          padding: 6px 2px; background: none; border: none; cursor: pointer;
          color: rgba(255,255,255,0.35); font-size: 10px; font-weight: 600;
          text-transform: uppercase; letter-spacing: 0.1em;
          font-family: var(--wh-font, 'Poppins', sans-serif); margin-bottom: 2px;
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
          min-height: 44px;
          font-size: 16px; /* exact 16px — iOS Safari auto-zooms on any input < 16px */
          color: rgba(255,255,255,0.85);
          font-family: var(--wh-font, 'Poppins', sans-serif); outline: none;
          transition: border-color 0.15s, background 0.15s;
        }
        #wh-hub-search::placeholder { color: rgba(255,255,255,0.6); } /* WCAG AA */
        #wh-hub-search:focus {
          border-color: rgba(247,162,27,0.5); background: rgba(255,255,255,0.09);
        }
        #wh-hub-search-icon {
          position: absolute; left: 10px; top: 50%; transform: translateY(-50%);
          color: rgba(255,255,255,0.6); pointer-events: none; display: flex;
        }
        #wh-hub-search-kbd {
          position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
          background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12);
          border-radius: 4px; padding: 1px 5px; font-size: 9px; color: rgba(255,255,255,0.75); /* C2 AA: 0.6=4.41:1 on the chip bg */
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
        .wh-hub-tile.active .wh-hub-tile-icon { color: var(--wh-orange, #F7A21B); }
        .wh-hub-tile.active .wh-hub-tile-label { color: var(--wh-orange, #F7A21B); }

        /* AI accent tile */
        .wh-hub-tile.accent:not(.active) {
          background: rgba(41,182,217,0.07);
          border-color: rgba(41,182,217,0.2);
        }
        .wh-hub-tile.accent:not(.active) .wh-hub-tile-icon { color: var(--wh-blue, #29B6D9); }
        .wh-hub-tile.accent:not(.active) .wh-hub-tile-label { color: var(--wh-blue, #29B6D9); }
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
          color: rgba(255,255,255,0.72); /* C2 WCAG AA: 0.5 measured 4.32:1 (<4.5) on the panel; 0.72 clears it */
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
          background: var(--wh-orange, #F7A21B);
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
        /* W1 platform tap-target floor — opt-in base utility (Grounded Sweep critique
           sweep:platform-wide:interactive-min-height-rule). 44px = gloved-hand minimum,
           all viewports, no exceptions. Any new interactive control opts in via this class. */
        .wh-tappable { min-height: 44px; min-width: 44px; }
        .wh-hub-mode-btn {
          flex: 1;
          min-height: 44px;
          padding: 6px 4px;
          background: transparent;
          border: none;
          border-radius: 7px;
          color: rgba(255,255,255,0.6); /* WCAG AA contrast over dark bg */
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
          color: var(--wh-orange, #F7A21B);
        }
        .wh-hub-mode-icon { font-size: 11px; line-height: 1; }

        /* ── FAB-CONSOLIDATION (2026-07-20): connectivity status pill in the header ──
           Ian: "make the feedback, companion, and online widget be put in the nav-hub…
           they overlap" + "the goal is a centralize design and component library." So
           this chrome is built ENTIRELY on the design tokens (tokens.css, injected by
           nav-hub above) — brand colour via var(--wh-*) / rgba(var(--wh-*-rgb), a), radii
           via var(--wh-radius*), type via var(--wh-font), tap floor via var(--wh-control-h).
           No hardcoded brand hex → a palette change in tokens.css restyles this too. The
           pill mirrors the retired .wh-conn-chip states via the SEMANTIC tokens. */
        #wh-hub-conn-pill {
          display: inline-flex; align-items: center; gap: var(--wh-space-1, 4px);
          padding: 5px 10px; min-height: 30px;
          background: rgba(255,255,255,0.05);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: var(--wh-radius-pill, 999px);
          color: var(--wh-text-faint, rgba(255,255,255,0.72));
          font-family: var(--wh-font, 'Poppins', sans-serif); font-size: 10px; font-weight: 600;
          letter-spacing: 0.02em; cursor: pointer;
          transition: background 0.15s ease, border-color 0.15s ease;
        }
        #wh-hub-conn-pill:hover { background: rgba(255,255,255,0.09); border-color: rgba(255,255,255,0.2); }
        #wh-hub-conn-dot {
          width: 8px; height: 8px; border-radius: var(--wh-radius-pill, 999px); flex-shrink: 0;
          background: var(--wh-green, #4ade80); box-shadow: 0 0 6px rgba(74,222,128,0.6);
        }
        #wh-hub-conn-pill[data-state="offline"],
        #wh-hub-conn-pill[data-state="degraded"] {
          background: rgba(248,113,113,0.16); border-color: rgba(248,113,113,0.5); color: var(--wh-red-text, #fecaca);
        }
        #wh-hub-conn-pill[data-state="offline"] #wh-hub-conn-dot,
        #wh-hub-conn-pill[data-state="degraded"] #wh-hub-conn-dot {
          background: var(--wh-red, #f87171); box-shadow: 0 0 6px rgba(248,113,113,0.6);
        }
        #wh-hub-conn-pill[data-state="slow"] {
          background: rgba(var(--wh-orange-rgb, 247,162,27),0.16); border-color: rgba(var(--wh-orange-rgb, 247,162,27),0.5); color: #fde68a;
        }
        #wh-hub-conn-pill[data-state="slow"] #wh-hub-conn-dot {
          background: var(--wh-orange, #F7A21B); box-shadow: 0 0 6px rgba(var(--wh-orange-rgb, 247,162,27),0.6);
        }
        #wh-hub-conn-badge {
          min-width: 16px; padding: 0 4px; border-radius: var(--wh-radius-sm, 8px);
          background: rgba(var(--wh-orange-rgb, 247,162,27),0.9); color: var(--wh-navy, #162032);
          font-size: 9px; font-weight: 800; text-align: center; line-height: 16px;
        }

        /* Connectivity detail — folded in from the retired .wh-conn-popover, toggled by the pill */
        #wh-hub-conn-detail {
          margin: 0 0 var(--wh-space-3, 12px); padding: 10px 12px;
          background: rgba(0,0,0,0.22); border: 1px solid rgba(255,255,255,0.06);
          border-radius: var(--wh-radius, 12px); font-size: 11px;
        }
        #wh-hub-conn-detail.hidden { display: none; }
        #wh-hub-conn-detail .wh-hub-conn-row {
          display: flex; justify-content: space-between; gap: var(--wh-space-2, 8px); padding: 3px 0;
          border-top: 1px solid rgba(255,255,255,0.05);
        }
        #wh-hub-conn-detail .wh-hub-conn-row:first-child { border-top: 0; }
        #wh-hub-conn-detail .k { color: var(--wh-text-muted, rgba(255,255,255,0.62)); }
        #wh-hub-conn-detail .v { color: rgba(255,255,255,0.85); font-weight: 600; }
        #wh-hub-conn-detail .help { margin-top: 6px; color: var(--wh-text-muted, rgba(255,255,255,0.5)); font-size: 10px; line-height: 1.4; }

        /* ── FAB-CONSOLIDATION: Assistant action row (Companion + Feedback) — token-built ── */
        #wh-hub-assist-row {
          display: grid; grid-template-columns: 1fr 1fr; gap: var(--wh-space-2, 8px); margin: 0 0 var(--wh-space-3, 12px);
        }
        .wh-hub-assist-btn {
          display: flex; align-items: center; justify-content: center; gap: var(--wh-space-2, 8px);
          min-height: 48px; padding: 10px 12px; border-radius: var(--wh-radius, 12px);
          background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
          color: rgba(255,255,255,0.9); font-family: var(--wh-font, 'Poppins', sans-serif);
          font-size: 12px; font-weight: 600; cursor: pointer;
          transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease-out;
        }
        .wh-hub-assist-btn:hover  { transform: translateY(-2px); }
        .wh-hub-assist-btn:active { transform: scale(0.96); }
        .wh-hub-assist-btn .ic { font-size: 16px; }
        #wh-hub-open-companion {
          background: rgba(var(--wh-blue-rgb, 41,182,217),0.1); border-color: rgba(var(--wh-blue-rgb, 41,182,217),0.28); color: var(--wh-blue, #29B6D9);
        }
        #wh-hub-open-companion:hover { background: rgba(var(--wh-blue-rgb, 41,182,217),0.18); border-color: rgba(var(--wh-blue-rgb, 41,182,217),0.45); }
        #wh-hub-open-feedback {
          background: rgba(var(--wh-orange-rgb, 247,162,27),0.1); border-color: rgba(var(--wh-orange-rgb, 247,162,27),0.28); color: var(--wh-orange, #F7A21B);
        }
        #wh-hub-open-feedback:hover { background: rgba(var(--wh-orange-rgb, 247,162,27),0.18); border-color: rgba(var(--wh-orange-rgb, 247,162,27),0.45); }

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
        <span class="ic ic-apps" aria-hidden="true"></span>
      </button>

      <!-- Panel -->
      <div id="wh-hub-panel" role="dialog" aria-label="${_tt('Navigation hub', 'Nabigasyon')}">
        <div id="wh-hub-panel-header">
          <span>WorkHive</span>
          <!-- FAB-CONSOLIDATION: live connectivity status pill (was the corner .wh-conn-chip) -->
          <button type="button" id="wh-hub-conn-pill" data-state="online" aria-label="${_tt('Connection status', 'Katayuan ng koneksyon')}" title="${_tt('Connection status', 'Katayuan ng koneksyon')}">
            <span id="wh-hub-conn-dot" aria-hidden="true"></span>
            <span id="wh-hub-conn-label">Online</span>
            <span id="wh-hub-conn-badge" style="display:none;" aria-hidden="true"></span>
          </button>
        </div>

        <!-- FAB-CONSOLIDATION: connectivity detail, folded in from the retired popover (toggled by the pill) -->
        <div id="wh-hub-conn-detail" class="hidden" role="region" aria-label="${_tt('Connectivity detail', 'Detalye ng koneksyon')}">
          <div class="wh-hub-conn-row"><span class="k">${_tt('Status', 'Katayuan')}</span><span class="v" id="wh-hub-conn-status">Online</span></div>
          <div class="wh-hub-conn-row"><span class="k">${_tt('Network', 'Network')}</span><span class="v" id="wh-hub-conn-net">—</span></div>
          <div class="wh-hub-conn-row"><span class="k">${_tt('Pending writes', 'Naka-pila')}</span><span class="v" id="wh-hub-conn-queue">0</span></div>
          <div class="help">${_tt('Pending writes save to this device and send automatically when the connection returns. You can keep working offline.', 'Ang mga naka-pila ay naka-save sa device na ito at awtomatikong ipapadala pagbalik ng koneksyon. Puwede kang magpatuloy offline.')}</div>
        </div>

        <!-- FAB-CONSOLIDATION: Assistant actions — Companion + Feedback (consolidated from the corner FABs) -->
        <div id="wh-hub-assist-row">
          <button type="button" id="wh-hub-open-companion" class="wh-hub-assist-btn" aria-label="${_tt('Open companion', 'Buksan ang katulong')}">
            <span class="ic ic-ai" aria-hidden="true"></span>
            <span>${_tt('Companion', 'Katulong')}</span>
          </button>
          <button type="button" id="wh-hub-open-feedback" class="wh-hub-assist-btn" aria-label="${_tt('Send feedback', 'Magpadala ng feedback')}">
            <span aria-hidden="true">💬</span>
            <span>${_tt('Feedback', 'Feedback')}</span>
          </button>
        </div>

        <!-- Phase E.3c: Global Search trigger — opens Cmd+K overlay on mobile too -->
        <button type="button" id="wh-hub-global-search" style="display:flex; align-items:center; gap:8px; width:100%; min-height:44px; padding:10px 12px; margin:0 0 8px; background:rgba(247,162,27,0.08); border:1px solid rgba(247,162,27,0.2); border-radius:10px; color:var(--wh-orange, #F7A21B); font-family:inherit; font-size:12px; font-weight:600; cursor:pointer; text-align:left;" aria-label="Open global search">
          <span class="ic ic-search" aria-hidden="true"></span>
          <span style="flex:1;">${_tt('Search assets, jobs, parts, PMs', 'Maghanap ng assets, trabaho, parts, PM')}</span>
          <span style="font-size:9px; font-weight:700; padding:2px 5px; background:rgba(247,162,27,0.15); border:1px solid rgba(247,162,27,0.3); border-radius:4px;">⌘K</span>
        </button>

        <!-- Search bar -->
        <div id="wh-hub-search-wrap">
          <span id="wh-hub-search-icon">
            <span class="ic ic-search" aria-hidden="true"></span>
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
          <p class="wh-hub-section-label">${_tt('Recent', 'Kamakailan')}</p>
          <div id="wh-hub-quick-row">${quickHTML}</div>
        </div>

        <div class="wh-hub-divider"></div>

        <!-- All Tools — 4-col grid, always visible, scrollable -->
        <p class="wh-hub-section-label">${_tt('All Tools', 'Lahat ng Tools')}</p>
        <div id="wh-hub-no-results">${_tt('No tools match your search.', 'Walang tool na tumugma sa paghahanap.')}</div>
        <div id="wh-hub-tiles" role="region">${tilesHTML}</div>
      </div>
    `;

    document.body.appendChild(wrapper);
  }

  // ─── FAB-CONSOLIDATION: connectivity pill painter ─────────────────────────────
  // Reads the connectivity-widget snapshot (window.whConnectivitySnapshot, exposed
  // by connectivity-widget.js) and paints the header pill + inline detail rows. The
  // widget still mounts on every page (its chip is just hidden), so the snapshot is
  // normally present; if it hasn't mounted yet, fall back to navigator.onLine so the
  // pill is never blank. Best-effort — never throws into the hub open path.
  function paintConnPill() {
    var pill = document.getElementById('wh-hub-conn-pill');
    if (!pill) return;
    function apply(s) {
      pill.setAttribute('data-state', s.stateKey || 'online');
      var lbl = document.getElementById('wh-hub-conn-label'); if (lbl) lbl.textContent = s.label || 'Online';
      var badge = document.getElementById('wh-hub-conn-badge');
      if (badge) {
        if (s.depth > 0) { badge.style.display = 'inline-block'; badge.textContent = String(s.depth); }
        else badge.style.display = 'none';
      }
      var st = document.getElementById('wh-hub-conn-status');
      if (st) st.textContent = !s.online ? 'Offline'
        : !s.backendOk ? 'Online, backend unavailable'
        : s.slow ? 'Online (slow link)' : 'Online';
      var net = document.getElementById('wh-hub-conn-net');
      if (net) net.textContent = (!s.net || s.net === 'unknown') ? 'unknown' : String(s.net).toUpperCase();
      var q = document.getElementById('wh-hub-conn-queue'); if (q) q.textContent = String(s.depth || 0);
    }
    try {
      if (typeof window.whConnectivitySnapshot === 'function') {
        window.whConnectivitySnapshot().then(apply).catch(function () { /* empty-catch-allow: pill snapshot is best-effort */ });
      } else {
        apply({ stateKey: navigator.onLine ? 'online' : 'offline',
                label: navigator.onLine ? 'Online' : 'Offline',
                online: navigator.onLine, backendOk: true, slow: false, net: 'unknown', depth: 0 });
      }
    } catch (_) { /* empty-catch-allow: pill paint is best-effort */ }
  }

  // ─── Open / Close ─────────────────────────────────────────────────────────────
  function openHub() {
    isOpen = true;
    document.getElementById('wh-hub').classList.add('hub-open');
    document.getElementById('wh-hub-fab').classList.add('open');
    document.getElementById('wh-hub-fab').setAttribute('aria-expanded', 'true');
    document.getElementById('wh-hub-panel').classList.add('open');
    // Legacy hook (kept harmless): companion + conn-chip no longer react to this class
    // — the companion is now launched from the Companion row (body.wh-companion-open).
    document.body.classList.add('wh-hub-open');
    // Refresh the connectivity status pill each time the panel opens.
    paintConnPill();
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

  // A page's fixed bottom-nav must NEVER be covered by the bottom-right FAB stack (V1 no-collision).
  // The stack (hub + connectivity chip + companion trigger + guide + feedback FAB) is hard-anchored
  // relative to hub bottom:24px (e.g. the conn-chip sits at 5.5rem = 24+FAB+gap), so lifting ONE
  // member breaks the stack (raising the hub made it collide with the chip). Instead lift the WHOLE
  // stack uniformly with a shared CSS var (--wh-fab-lift) applied as margin-bottom — which raises a
  // bottom-anchored fixed element while PRESERVING its bottom value + the stack's relative spacing.
  // Nav-hub owns this because it is the stack's orchestrator (on every page; lazy-loads the feedback
  // FAB, so the rule is injected once and applies to the FAB whenever it later mounts).
  function liftFabStackAboveBottomNav() {
    try {
      const nav = document.querySelector('.bottom-nav');
      if (!nav) return;
      const cs = getComputedStyle(nav);
      if (cs.position !== 'fixed' || cs.display === 'none' || (parseFloat(cs.bottom) || 0) >= 8) return;
      const lift = Math.round(nav.getBoundingClientRect().height) + 8;   // clear the bar + an 8px gap
      document.documentElement.style.setProperty('--wh-fab-lift', lift + 'px');
      if (!document.getElementById('wh-fab-lift-style')) {
        const s = document.createElement('style');
        s.id = 'wh-fab-lift-style';
        s.textContent = '#wh-hub, .wh-conn-chip, .wh-conn-popover, .wh-fb-fab, #wh-guide-link, '
          + '#wh-ai-trigger, #fab, .wh-companion-trigger { margin-bottom: var(--wh-fab-lift, 0px) !important; }';
        document.head.appendChild(s);
      }
    } catch (_) { /* empty-catch-allow: best-effort stack lift */ }
  }

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
    } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
    applyPosition('right', 24);
  }

  function savePosition(side, bottom) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ side, bottom })); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
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

    // Axis-3 pattern: close-on-click-outside delegated to the canonical WHPatterns
    // helper. exceptSelector '#wh-ai-widget' is resolved at click-time so the async-
    // loaded companion (which lives OUTSIDE #wh-hub) never triggers closeHub() before
    // its own click handler fires. Inline fallback if wh-patterns.js isn't loaded yet.
    if (window.WHPatterns && typeof window.WHPatterns.clickOutside === 'function') {
      window.WHPatterns.clickOutside(document.getElementById('wh-hub'), function () { closeHub(); }, {
        isOpen: function () { return isOpen; },
        exceptSelector: '#wh-ai-widget'
      });
    } else {
      document.addEventListener('click', e => {
        const hub   = document.getElementById('wh-hub');
        const aiWgt = document.getElementById('wh-ai-widget');
        if (isOpen && hub && !hub.contains(e.target) && !(aiWgt && aiWgt.contains(e.target))) closeHub();
      });
    }

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

    /* ── FAB-CONSOLIDATION wiring ──────────────────────────────────────────────
       The header pill toggles the connectivity detail; the two Assistant buttons
       launch the companion + feedback panels that used to be corner FABs. Each
       stops propagation so the click never reaches the companion's / hub's own
       click-outside-to-close handlers, and defers the open one tick so the current
       click has fully finished dispatching before the target panel appears. */
    document.getElementById('wh-hub-conn-pill')?.addEventListener('click', function (e) {
      e.stopPropagation();
      const det = document.getElementById('wh-hub-conn-detail');
      if (det) det.classList.toggle('hidden');
      paintConnPill();
    });

    // Axis-3 pattern: delegate the launcher-defer idiom to the canonical WHPatterns
    // helper (falls back inline only if wh-patterns.js hasn't loaded yet — clicks
    // land long after load, so the fallback effectively never fires).
    function _launch(e, openFn) {
      if (window.WHPatterns && typeof window.WHPatterns.launchPanel === 'function') {
        window.WHPatterns.launchPanel(e, openFn, { before: closeHub });
      } else {
        if (e) e.stopPropagation();
        closeHub();
        setTimeout(function () { try { openFn(); } catch (_) { /* empty-catch-allow: launcher fallback */ } }, 0);
      }
    }
    document.getElementById('wh-hub-open-companion')?.addEventListener('click', function (e) {
      _launch(e, function () { if (window.WHAssistant && window.WHAssistant.open) window.WHAssistant.open(); });
    });
    document.getElementById('wh-hub-open-feedback')?.addEventListener('click', function (e) {
      _launch(e, function () { if (window.WHFeedback && window.WHFeedback.open) window.WHFeedback.open(); });
    });

    /* Keep the pill live if connectivity flips while the panel is open. */
    window.addEventListener('online',  paintConnPill);
    window.addEventListener('offline', paintConnPill);

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

      // Re-apply the community unread badge — the grid + Recent row were just
      // re-rendered, so the freshly-created Community tile has no badge yet.
      _paintCommunityBadges();
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
    // Lift the whole bottom-right FAB stack above a page's fixed bottom-nav (V1 no-collision).
    // Retry once deferred in case the bottom-nav renders a tick after nav-hub inits.
    liftFabStackAboveBottomNav();
    setTimeout(liftFabStackAboveBottomNav, 600);
    // Cross-page community unread badge — mirrors the companion FAB nudge. Deferred
    // so the page can finish building its Supabase client + restoring the session.
    setTimeout(scheduleCommunityCheck, 800);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
