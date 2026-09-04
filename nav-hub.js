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

  // ─── Shared <head> BRAND BOILERPLATE SSOT (PLATFORM_CENTRALIZATION C-P4 · shared-<head> wave).
  // The SEO-critical <head> (title / meta description / canonical / og: / JSON-LD) stays STATIC
  // per-page — crawlers need it in the served HTML and it is per-page CONTENT, so it is NEVER
  // injected here. Only the brand BOILERPLATE — favicons (assets exist at root; were linked on
  // 0/32 pages) + theme-color (drifted across 3 values: orange/navy/violet) — is centralized so it
  // is ONE source instead of 32 drifting copies. Each is added ONLY IF ABSENT (a page that declares
  // its own wins), so this is idempotent and never duplicates.
  (function injectHeadBoilerplate() {
    const head = document.head || document.documentElement;
    const addLink = (rel, href, attrs) => {
      if (document.querySelector('link[rel="' + rel + '"]')) return;
      const l = document.createElement('link');
      l.rel = rel; l.href = href;
      if (attrs) Object.keys(attrs).forEach(k => l.setAttribute(k, attrs[k]));
      head.appendChild(l);
    };
    addLink('icon', 'favicon.svg', { type: 'image/svg+xml' });   // modern SVG favicon
    addLink('alternate icon', 'favicon.ico');                    // .ico fallback (older browsers)
    addLink('apple-touch-icon', 'workhive-logo-tight.png');      // iOS home-screen icon
    // theme-color (mobile browser chrome) — the canonical brand orange; change it HERE, once.
    if (!document.querySelector('meta[name="theme-color"]')) {
      const m = document.createElement('meta');
      m.name = 'theme-color'; m.content = '#F7A21B'; // purity-allow: a <meta> attribute value can't be a CSS var(); this literal = --wh-orange (the canonical, one place)
      head.appendChild(m);
    }
  })();

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
    // T173 (2026-08-25): was roles:['supervisor'] — the findability benchmark FAILED
    // "Where is my team's live board?" for a WORKER, yet hive.html itself declares
    // <meta name="worker-daily"> (presence, handover, feed, standings are worker-daily
    // surfaces, and the T7 join flow LANDS workers there). Same unhide shape as
    // shift-brain's earlier fix. Label carries 'board' so both mental models match.
    { label: 'Hive Board',   href: 'hive.html',         match: ['hive', 'board', 'team'], section: 'Your Team', roles: ['field','supervisor'],
      icon: `<span class="ic ic-brand" aria-hidden="true"></span>` },
    { label: 'PM Scheduler', href: 'pm-scheduler.html', match: ['pm-scheduler'],       section: 'Your Team', roles: ['field','supervisor'],
      icon: `<span class="ic ic-maintenance" aria-hidden="true"></span>` },
    { label: 'Community',    href: 'community.html',    match: ['community'],          section: 'Your Team', /* universal */
      icon: `<span class="ic ic-community" aria-hidden="true"></span>` },

    // ── Intelligence: AI, analytics, and predictions ──────────────────────────
    // Analytics Report MUST be listed before Analytics — both paths contain
    // 'analytics', and getCurrentTool() returns the first match in iteration order.
    // Phase B: hidden from primary nav, accessible as a button inside analytics.html.
    // T173 (2026-08-25): was hidden:true — the report SENDER (email-my-boss, the supervisor's
    // outward tool) invisible in the supervisor's own spine; reachable only via analytics' Send
    // button. Same unhide class as Voice Journal: hidden is for internal pages.
    { label: 'Reports', href: 'report-sender.html', match: ['analytics-report', 'report-sender', 'report'], section: 'Intelligence', roles: ['supervisor','engineer'],
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
    // T173 (2026-08-25): was hidden:true — a WORKER-DAILY capture surface (T12's whole story)
    // invisible in the 'get anywhere fast' spine, reachable only via index QA + logbook links.
    // hidden: is for genuinely internal pages (audit-log, ai-quality); a daily tool is not one.
    { label: 'Voice Journal', href: 'voice-journal.html', match: ['voice-journal', 'voice'], section: 'Intelligence', roles: ['field','supervisor'],
      icon: `<span class="ic ic-voice" aria-hidden="true"></span>` },
    // Phase H.2 hid this behind the Shift Brain tab inside analytics.html - a SUPERVISOR door.
    // T13 (2026-08-25) walked the page as the crew's clock-in read: it leads with [SAFETY] active
    // isolations + permit numbers and addresses the shift directly, yet a field worker had no route
    // to it (analytics is not their surface). A safety brief nobody can reach is write-only.
    { label: 'Shift Brain',  href: 'shift-brain.html',  match: ['shift-brain'],        section: 'Intelligence', roles: ['field','supervisor'],
      icon: `<span class="ic ic-brain" aria-hidden="true"></span>` },

    // ── Build & Projects: engineering and project work ────────────────────────
    // T173 (2026-08-25): +supervisor — no separate engineer auth exists (the engineer persona IS
    // supervisors in practice, T52); a supervisor needing a calc could not find Eng. Design here.
    { label: 'Eng. Design',  href: 'engineering-design.html', match: ['engineering-design', 'design', 'calc'], section: 'Build & Projects', roles: ['engineer','supervisor'],
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
    // T55 (2026-08-28): the seller's OWN dashboard had no registry entry AT ALL — not hidden,
    // absent. So it was missing from the All Tools grid and ALSO unfindable by search, because
    // search-overlay reads this very registry and filters `!t.hidden`: no query for "seller",
    // "listings" or "my listings" could reach it from anywhere on the platform. The only route
    // was remembering to open Marketplace and spotting the "My Listings" pill in its header.
    // For the supplier persona this page IS their platform, which is exactly the "a daily tool
    // is not an internal page" class that unhid Voice Journal and Shift Brain under T173.
    // Universal like Marketplace itself, because anyone may sell — that is T104's whole premise.
    // ★MUST PRECEDE Marketplace, for the same reason Analytics Report precedes Analytics:
    // getCurrentTool() returns the FIRST match in iteration order and 'marketplace' is a
    // substring of this page's path, so listing it after would highlight the wrong entry.
    // ★AND THE MATCH CARRIES '.html' DELIBERATELY: bare 'marketplace-seller' is also a substring
    // of marketplace-seller-profile.html — the PUBLIC profile a BUYER reads, a different page
    // with a different job — and would have mis-claimed it. Label matches the in-marketplace
    // pill, and its icon, so the two affordances read as one destination.
    // ★hidden: true IS THE POINT, NOT A RETREAT — and it only became the right answer today.
    // Registering this universally pushed the home-stack budget over for TWO roles at once (field
    // 14/13, supervisor 21/20); both were deliberately AT budget, because the cap exists to protect
    // how many choices a person faces in a primary nav. A seller's dashboard is a real destination
    // but it is not a daily tool for the plant worker or the supervisor whose slots it would take.
    // `hidden` used to mean UNFINDABLE — the entry would have vanished from the grid AND from
    // search, which is the orphaning this whole change set out to fix. It no longer does:
    // search-overlay now indexes hidden entries (T78, same session), so this page is reachable by
    // typing "seller", "listings" or "my listings", keeps its correct current-page resolution, and
    // costs nobody a nav slot. That is exactly the remedy the home-stack gate recommends — hide it
    // and deep-link from the parent — and the parent link already exists as marketplace.html's
    // "My Listings" pill.
    { label: 'My Listings',  href: 'marketplace-seller.html', match: ['marketplace-seller.html'], section: 'Connect', hidden: true, /* universal */
      icon: `<span class="ic ic-list" aria-hidden="true"></span>` },
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

  /* T173/T78 (2026-08-26): expose the tool registry as the ONE page index. The global search
     overlay indexed DATA only (assets/jobs/parts/PMs), so a wayfinding question - "where are the
     plant KPIs?" - dead-ended in a records palette while the answer was a PAGE. Rather than
     duplicating a page list there (clone debt, and two lists drift), publish this registry and
     let search read it. Read-only copy: callers get the entries, not the array we render from. */
  try {
    window.WHNavTools = TOOLS.map(function (t) {
      return { label: t.label, href: t.href, section: t.section || '', hidden: !!t.hidden,
               roles: t.roles ? t.roles.slice() : null, match: t.match ? t.match.slice() : [] };
    });
  } catch (_) { /* empty-catch-allow: the hub still works if the index cannot be published */ }

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
      const hiveId = whHiveId();
      if (!hiveId) return;
      let sess = null;
      try { sess = (await db.auth.getSession())?.data?.session || null; } catch (_) { sess = null; }
      if (!sess) return; // fail closed — never fire an RLS-gated read without a JWT
      const worker = (typeof window.restoreIdentityFromSession === 'function')
        ? await window.restoreIdentityFromSession(db)
        : (whWorker() || '');
      // Baseline: if never seen, look back 3 days so a returning worker sees recent
      // activity without being flooded. community.html stamps the real time on visit.
      const seenKey = 'wh_community_last_seen:' + hiveId;
      let since = localStorage.getItem(seenKey);
      if (!since) since = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
      let postQ = db.from('v_community_posts_truth')
        .select('id', { count: 'exact', head: true })
        .eq('hive_id', hiveId).is('deleted_at', null).gt('created_at', since);
      // T149 (2026-08-28): a FLAGGED post is removed from a worker's feed by the CLIENT
      // (community.html renderEntries adds .or('flagged.eq.false,author_name.eq.<me>') for
      // non-supervisors) -- RLS does NOT do it: the member branch of community_posts_read is
      // `auth.uid() IS NOT NULL AND hive_id IN (my active hives)` with no flagged test, so a
      // moderated post is still readable and still COUNTABLE here. Unfiltered, this badge
      // credits activity the tap cannot show: "3 new" that opens to 2, and a post a supervisor
      // REMOVED from worker view still announces itself to every worker. The badge already
      // excludes the reader's own posts (neq author_name below), so the feed's author-sees-
      // their-own exception needs no mirror -- plain flagged=false is the whole rule. A
      // supervisor's feed DOES show flagged posts, so their badge must keep counting them.
      // Absent WHRoles we filter (under-count) rather than resurrect a moderated post.
      const _isSup = !!(window.WHRoles && typeof window.WHRoles.isSupervisor === 'function'
        && window.WHRoles.isSupervisor());
      if (!_isSup) postQ = postQ.eq('flagged', false);
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

  /* T144 (2026-08-28): the badge was computed ONCE per page load and never again -- no
     storage/visibility/focus listener, no interval, one call site. localStorage is shared
     across a browser's tabs, so when community.html stamps wh_community_last_seen on visit
     the FACT reaches every other tab immediately; nothing was listening. A worker with the
     dashboard and community both open therefore read the posts and kept seeing "3 new" on
     the dashboard until they reloaded it -- a badge advertising work already done.
     The `storage` event fires only in the OTHER tabs, which is exactly the gap: the visiting
     tab recomputes on its own next load. Debounced because a re-check issues two counted
     reads, and left event-driven on purpose -- no polling (a timer here would re-read on
     every open page forever to serve chrome that is best-effort by design). KNOWN REMAINING:
     this converges a tab whose data went STALE, not one that missed NEW activity; a
     long-lived page (a wall-mounted display) still shows the count it loaded with. */
  let _seenDebounce = null;
  window.addEventListener('storage', function (e) {
    if (!e || !e.key || e.key.indexOf('wh_community_last_seen:') !== 0) return;
    clearTimeout(_seenDebounce);
    _seenDebounce = setTimeout(function () {
      if (_whNavClient()) checkCommunityActivity();
    }, 400);
  });

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
          /* A11Y — WCAG 2.2 SC 2.4.11 Focus Not Obscured / rubric Q2 "no phantom focus stop"
             (live-MCP keyboard walk, 2026-07-23). opacity:0 + pointer-events:none hides the CLOSED
             panel from sighted and mouse users but NOT from the keyboard: visibility stayed "visible",
             so all 28 nav links/buttons inside stayed IN THE TAB ORDER. A keyboard user tabbing the
             page walked through 28 invisible controls before reaching real content. axe scores this
             CLEAN (it only treats display:none / visibility:hidden / aria-hidden as hidden), which is
             how the arc-wide "0 violations" was true while this shipped on every page. visibility:hidden
             removes the subtree from the tab order AND the a11y tree; the 0.2s delay lets the fade-out
             finish first so the open/close animation is unchanged. */
          visibility: hidden;
          transition: opacity 0.2s ease, transform 0.2s ease-out, visibility 0s linear 0.2s;
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
          /* Must reset BOTH: the base rule hides the closed panel from the tab order
             (visibility:hidden, delayed 0.2s). Without these two lines the panel could
             never become visible or focusable again. */
          visibility: visible;
          transition-delay: 0s;
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
          <button type="button" id="wh-hub-conn-pill" data-state="online" style="display:none;" aria-label="${_tt('Connection status', 'Katayuan ng koneksyon')}" title="${_tt('Connection status', 'Katayuan ng koneksyon')}">
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

    /* ★THE FAB SAT ON TOP OF DIALOG ACTION ROWS, AND IT WINS EVERY TIME.
       #wh-hub is position:fixed bottom-right at z-index 9998; a dialog on this platform sits at 50-60. So
       any dialog whose primary control lands bottom-right is unreachable. Measured on community at 390x844:
       #btn-submit-reply ("Reply") is 80x44 centred at (314, 784) inside #thread-sheet (z 51); #wh-hub-fab is
       56x56 at top 764, left 303, z 9998; document.elementFromPoint(314, 784) returns #wh-hub-fab, NOT the
       button. The textarea in the same overlay hit-tests to itself, so the dialog looks perfectly healthy —
       a person can type a reply and simply be unable to send it.
       This is the second shared-chrome component found doing this (learn-link.js's page-guide chip was the
       first, over pm-scheduler's Save Changes), which is why the fix is the same behavioural rule rather
       than another z-index nudge: while a dialog is up, page-level chrome stands down. It is also the
       correct a11y posture — a modal traps focus, so a nav control behind it must not be reachable at all.
       Deliberately identical in contract to learn-link.js's version, including the two modal conventions
       this platform uses (display:flex modals and .open sheets), so the two cannot drift apart. */
    (function standDownWhileDialogOpen() {
      var DIALOGISH = '[role="dialog"],dialog[open],.sheet.open,.modal.open,[id$="-sheet"].open,'
        + '[id$="-modal"].open,.sheet-overlay.open';
      var hidden = false, queued = false;
      function visible(el) {
        var cs = getComputedStyle(el);
        /* NOT opacity: a dialog mid-fade reports opacity 0 on the first frame after its class flips, and
           rejecting it there left the chrome up over an OPENING dialog — with no further mutation to
           re-trigger the check, it stayed up for the dialog's whole life. Measured on community: the thread
           overlay was open and the hub still hit-tested over #btn-submit-reply. display and visibility are
           the properties that actually mean "not there"; standing down a frame early is harmless. */
        if (cs.display === 'none' || cs.visibility === 'hidden') return false;
        var r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      }
      function sync() {
        queued = false;
        if (!wrapper.isConnected) { obs.disconnect(); return; }
        var open = false, all = document.querySelectorAll(DIALOGISH);
        for (var i = 0; i < all.length; i++) { if (visible(all[i])) { open = true; break; } }
        if (open === hidden) return;
        hidden = open;
        /* visibility, not display: the hub's own panel logic reads and writes display on its children, and
           blanking the wrapper's display would fight it. visibility:hidden removes it from hit-testing and
           from the a11y tree while leaving that logic untouched. */
        wrapper.style.visibility = open ? 'hidden' : '';
        wrapper.setAttribute('aria-hidden', open ? 'true' : 'false');
      }
      function schedule() { if (!queued) { queued = true; requestAnimationFrame(sync); } }
      /* A dialog that settles via a CSS transition emits no further mutation, so listen for the transition
         too — belt and braces against the one-frame race above. */
      document.addEventListener('transitionend', schedule, true);
      var obs = new MutationObserver(schedule);
      obs.observe(document.documentElement, { attributes: true, subtree: true,
        attributeFilter: ['style', 'class', 'open', 'aria-hidden', 'hidden'] });
      sync();
    })();
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
      // Silence-is-golden (2026-07-22, Ian: remove the redundant "Online" pill): the connectivity
      // pill is pure noise in the healthy state — hide it, surface it ONLY when the link is degraded
      // (offline / slow / backend down / pending writes queued). Symmetric with the realtime "Live"
      // pill on the hive & community boards. The detail rows below still populate for when it shows.
      var healthy = s.online && (s.backendOk !== false) && !s.slow && !((s.depth || 0) > 0);
      pill.style.display = healthy ? 'none' : '';
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
  // SAFE AREA, added 2026-08-04 and folded into this same rule rather than living beside it.
  // Measured live at a verified innerWidth of 390: #wh-hub computed `bottom: 24px` with
  // `inset: auto 16px 24px auto` set INLINE, which beat the stylesheet rule two hundred lines up --
  // `@media (max-width: 480px) { #wh-hub { bottom: max(16px, env(safe-area-inset-bottom)) } }`.
  // The media query matched and the rule was in the CSSOM; it simply never won, because
  // loadSavedPosition() calls applyPosition('right', 24) on EVERY load when nothing is stored, which
  // is the default path for essentially every user. So the env() rule was dead code on every page,
  // and on a notched phone the home indicator (~34px) covered the bottom of the FAB stack.
  // The fix belongs HERE, on the shared margin, because margin-bottom raises a bottom-anchored fixed
  // element while preserving the stack's relative spacing -- the same reason --wh-fab-lift works.
  // Adding env() to the hub's own bottom instead would raise the hub past the chip anchored below it.
  // Both terms live in one calc so the two lifts add rather than one overwriting the other, and the
  // rule is injected UNCONDITIONALLY now: the home indicator exists whether or not the page has a
  // bottom-nav, and the old early-return meant pages without one got no clearance at all.
  // #wh-ai-widget, not #wh-ai-trigger. The trigger is `position: relative` inside the fixed
  // #wh-ai-widget (bottom: 24px), so the margin was being applied one level too low: driving the
  // lift to 34px moved the hub and the guide link by 34px but the AI trigger by only 24px,
  // inverting their order and changing the gap by 10px. That is the collision this shared-lift
  // mechanism exists to prevent -- it was simply invisible while the rule only ever mounted on
  // pages that have a .bottom-nav. A lift has to land on the element that owns the `bottom`.
  const FAB_STACK_SEL = '#wh-hub, .wh-conn-chip, .wh-conn-popover, .wh-fb-fab, #wh-guide-link, '
    + '#wh-ai-widget, #fab, .wh-companion-trigger';

  // ── THE BAR THAT COVERS THE CONTENT SHOULD BE THE THING THAT RESERVES FOR IT ────────────────────
  // #wh-hub is fixed across the bottom 56px of every page, and 11 of the 22 production pages computed
  // `body { padding-bottom: 0 }`, so at MAXIMUM scroll - the position a reader cannot scroll past -
  // content sat underneath it: index (footer + main, 79.7px under), logbook (80px, including the
  // logbook grid), inventory (80.4), pm-scheduler (145 - the worst, the whole dashboard screen),
  // dayplanner (48.5, its "About this dashboard" disclosure), voice-journal (80.4, its source chip),
  // assistant (80.4, the chat input area), community (79.6), public-feed (80.4), engineering-design
  // (79.8) and hive (64.5). The other 11 pages already reserve 80-96px, which is why this never
  // showed up as a pattern: it looked like a per-page oversight each time it was found.
  //
  // I fixed two of them page-by-page earlier in this session before measuring the other twenty, and
  // that was the wrong altitude: this is one shared bar, so it takes one shared reserve, exactly as
  // wayfinding.js reserves the top band for its own pill. Placing it here also means a page added
  // later inherits the reserve instead of shipping the bug again.
  //
  // MAX, not a flat set: a page that already reserves MORE (alert-hub 90, resume 96) keeps its own
  // value, because those pages stack extra chrome above the bar. `max()` is doing the same job as
  // wayfinding's `if (band > cur)` check, declaratively. Print resets it - paper has no fixed bar.
  function ensureHubReserveStyle() {
    if (document.getElementById('wh-hub-reserve-style')) return;
    const s = document.createElement('style');
    s.id = 'wh-hub-reserve-style';
    s.textContent =
      // --wh-fab-lift is IN the sum, not ignored, and pm-scheduler is why. That page has its OWN
      // `.bottom-nav`, so nav-hub lifts the hub above it (the lift logic below) and the hub's top sat
      // at 700 instead of the 765 every other page reports. The occluded band there is bottom-nav +
      // hub, and it measured 145px - so a flat 80px reserve cleared ten pages and left that one still
      // hiding its dashboard. Reusing the variable this file already maintains for that exact bar
      // makes the reserve track the chrome instead of guessing at it.
      'body { padding-bottom: max(' +
        'var(--wh-hub-reserve, 80px),' +
        ' calc(80px + var(--wh-fab-lift, 0px) + env(safe-area-inset-bottom, 0px))) !important; }'
      + ' @media print { body { padding-bottom: 0 !important; } }';
    document.head.appendChild(s);
  }

  function ensureFabStackLiftStyle() {
    if (document.getElementById('wh-fab-lift-style')) return;
    const s = document.createElement('style');
    s.id = 'wh-fab-lift-style';
    s.textContent = FAB_STACK_SEL
      + ' { margin-bottom: calc(var(--wh-fab-lift, 0px) + env(safe-area-inset-bottom)) !important; }'
      // Belt and braces: if a stack member is ever nested inside another, it must not add a second
      // lift on top of the one it already inherits from its moving ancestor.
      + ' #wh-hub ' + FAB_STACK_SEL.split(', ').join(', #wh-hub ')
      + ' { margin-bottom: 0 !important; }';
    document.head.appendChild(s);
  }

  // ── THE SCROLLBAR GUTTER IS PART OF THE FAB'S ADDRESS (T184, 2026-08-26) ───────────────────────
  // The hub FAB is the platform's ONE piece of muscle memory: the same corner on all 24 pages, found
  // by thumb without looking. It was landing in THREE different columns at 390 - x = 303, 312 and 318,
  // a 15px spread - and the cause was not in this file or in any page's hub styling. Every page had
  // an identical `#wh-hub { right: 16px }` and an identical 56px FAB.
  //
  // A `position: fixed` right-anchored element is measured from the SCROLLPORT, and the reserved
  // scrollbar gutter narrows it. A virgin `fixed; right: 0` probe proved it directly: its right edge
  // sat at 375 on community, 384 on inventory, 390 on logbook - while documentElement.clientWidth
  // read 390 on all three, which is why nothing in the DOM showed the difference. The spread was the
  // CROSS-PRODUCT of two unrelated per-page decisions:
  //     components.css:231 `html { scrollbar-gutter: stable }`  - linked by some pages, not others
  //     `::-webkit-scrollbar { width: 6px }`                    - declared inline by some pages
  // reserve 15px (gutter, default bar) -> 303 · 6px (gutter + thin bar) -> 312 · none -> 318.
  // Neither decision was ever made with the FAB in mind, and together they moved it.
  //
  // So the rule belongs HERE, for the same reason ensureHubReserveStyle() above lives here and says
  // so: this is one shared stack, so it takes one shared rule, and a page added later inherits it
  // instead of shipping the drift again. Both halves must be set together - the gutter alone still
  // leaves 303-vs-312, because the gutter's WIDTH is the scrollbar's width. 6px + a visible thumb is
  // not a new choice: it is the idiom inventory and logbook already carry verbatim.
  // Element-level overrides (marketplace's `scrollbar-width: none` strips, community's presence bar)
  // are more specific and keep winning.
  function ensureScrollGutterStyle() {
    if (document.getElementById('wh-scroll-gutter-style')) return;
    const s = document.createElement('style');
    s.id = 'wh-scroll-gutter-style';
    s.textContent =
      'html { scrollbar-gutter: stable; }'
      + '::-webkit-scrollbar { width: 6px; }'
      + '::-webkit-scrollbar-track { background: transparent; }'
      + '::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }';
    document.head.appendChild(s);
  }

  function liftFabStackAboveBottomNav() {
    try {
      ensureScrollGutterStyle();   // the gutter sets the FAB's column; reserve it identically everywhere
      ensureHubReserveStyle();     // the bar covers the page's last 56px; reserve for it once, here
      ensureFabStackLiftStyle();   // safe-area clearance is owed regardless of any bottom-nav
      const nav = document.querySelector('.bottom-nav');
      if (!nav) return;
      const cs = getComputedStyle(nav);
      if (cs.position !== 'fixed' || cs.display === 'none' || (parseFloat(cs.bottom) || 0) >= 8) return;
      const lift = Math.round(nav.getBoundingClientRect().height) + 8;   // clear the bar + an 8px gap
      document.documentElement.style.setProperty('--wh-fab-lift', lift + 'px');
    } catch (_) { /* empty-catch-allow: best-effort stack lift */ }
  }

  function applyPosition(side, bottomPx) {
    const hub   = document.getElementById('wh-hub');
    const panel = document.getElementById('wh-hub-panel');
    const label = document.getElementById('wh-hub-current-label');
    snapSide = side;

    hub.style.left   = side === 'left'  ? '16px' : 'auto';
    hub.style.right  = side === 'right' ? '16px' : 'auto';
    // NOTE: this stays a plain px value ON PURPOSE. Raising the hub alone breaks the stack -- the
    // conn-chip and friends are anchored relative to hub bottom:24px, so lifting one member makes it
    // collide with the next (that regression is recorded above). The home-indicator clearance the
    // hub needs is applied to the WHOLE stack uniformly in liftFabStack() below.
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
    // ★T78 (2026-08-26): THIS CLICK COULD DO NOTHING AT ALL, SILENTLY. search-overlay.js is
    // lazy-loaded async from this file, so window.WHSearch is briefly absent on every page and
    // PERMANENTLY absent if that request fails - a cache miss, a bad deploy, a flaky connection.
    // The handler's only branch was the happy one, so the button simply ignored the press.
    // Measured with search-overlay.js answered 404: overlay never opened, nothing was said, and
    // zero page errors - the exact shape of a control that looks alive and is not, on the one
    // element that appears on every page.
    //
    // Try once more (the usual cause is a request that had not landed yet), then say so. A search
    // that cannot open is a small failure; a button that swallows the press teaches the worker the
    // platform is broken and gives them nothing to do about it.
    document.getElementById('wh-hub-global-search')?.addEventListener('click', function () {
      if (window.WHSearch && typeof window.WHSearch.open === 'function') {
        closeHub();              // tidy: hide the nav-hub before showing the overlay
        window.WHSearch.open();
        return;
      }
      const btn = this;
      const label = btn.textContent;
      btn.disabled = true;
      const say = function (msg) {
        if (typeof window.showToast === 'function') { window.showToast(msg, 'info'); }
        else { btn.textContent = msg; setTimeout(function () { btn.textContent = label; }, 3000); }
      };
      // one retry: drop the marker so the loader below re-injects, then re-check
      const old = document.querySelector('script[data-wh-search]');
      if (old) old.remove();
      const s2 = document.createElement('script');
      s2.src = 'search-overlay.js';
      s2.async = true;
      s2.setAttribute('data-wh-search', '1');
      s2.onload = function () {
        btn.disabled = false;
        if (window.WHSearch && typeof window.WHSearch.open === 'function') {
          closeHub();
          window.WHSearch.open();
        } else {
          say('Search could not start. Reload the page and try again.');
        }
      };
      s2.onerror = function () {
        btn.disabled = false;
        say('Search is unavailable right now. Check your connection, then reload.');
      };
      document.head.appendChild(s2);
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
    /* T126/T144 (2026-08-28): regaining the network is the one moment a long-lived page KNOWS its
       data may be stale, and it was the only such moment nobody used -- this listener repainted the
       connectivity pill and nothing else, so a tab that sat through a blip kept showing the count it
       loaded with. That matters most where nobody is holding the device: an unattended wall display
       cannot press Retry, so its recovery has to be automatic or it does not happen. Reuses the same
       debounce as the cross-tab path, and checkCommunityActivity already fails closed without a
       session, so a reconnect on a signed-out page costs nothing. */
    window.addEventListener('online', function () {
      clearTimeout(_seenDebounce);
      _seenDebounce = setTimeout(function () {
        if (_whNavClient()) checkCommunityActivity();
      }, 400);
    });
    /* Silence-is-golden: evaluate connectivity ONCE on load so a genuinely-degraded-on-load link
       surfaces the pill even before the user opens the hub (healthy stays hidden via the markup default). */
    paintConnPill();

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
    // Identity reconcile runs BEFORE the community check so the badge path reads a true worker name.
    setTimeout(reconcileIdentity, 400);
    // Cross-page community unread badge — mirrors the companion FAB nudge. Deferred
    // so the page can finish building its Supabase client + restoring the session.
    setTimeout(scheduleCommunityCheck, 800);
  }

  // Identity reconcile (marketplace deepwalk 2026-07-24, J15).
  // whWorker() reads a localStorage cache, and on a shared device that cache can belong to a PRIOR
  // user, so every page has to reconcile it against the live session. That reconcile used to happen
  // ONLY as a side effect of scheduleCommunityCheck, which returns early when whHiveId() is empty.
  // On pages where it is empty (marketplace-seller-profile.html, caught live) the reconcile never
  // ran, so whWorker() kept returning the previous user's name while a DIFFERENT account held the
  // session: measured as worker "Pablo Aguilar" under christinedizon's JWT. Anything that role-gates
  // or attributes on that name was reading the wrong person. Identity is not a feature's side
  // effect, so it now runs unconditionally on every page that loads nav-hub, needing only a client.
  async function reconcileIdentity() {
    try {
      if (typeof window.restoreIdentityFromSession !== 'function') return;
      const db = _whNavClient();
      if (!db || !db.auth) return;
      await window.restoreIdentityFromSession(db);
    } catch (_) { /* empty-catch-allow: best-effort. restoreIdentityFromSession already fails closed (clears the cache) when signed out; a client that is not ready yet simply retries on the next page load. */ }
  }

  // ─── T44 (2026-08-25): central service-worker registration ────────────────────────────
  // The PWA installs from index (manifest + install button live there), but a repo-wide grep
  // found exactly ONE root-scope `serviceWorker.register` — on report-sender.html, a
  // supervisor surface a field worker may never open. So an installed app had NO shell
  // precache, NO offline-fallback navigation shell, and `navigator.serviceWorker.ready`
  // hung forever on every other page (the marketplace-seller push-alerts hang, 2026-07-30,
  // was this same hole). Registering here puts the worker on every page that loads nav-hub.
  //
  // The path is DERIVED, never hardcoded: locally the Flask tester serves the app under
  // /workhive/ while production serves the repo root ([[feedback_workhive_url_prefix]]) —
  // a hardcoded '/workhive/sw.js' 404s in prod, a hardcoded '/sw.js' misses the local scope.
  function whSwRoot() {
    return location.pathname.startsWith('/workhive/') ? '/workhive/' : '/';
  }
  window.whSwRoot = whSwRoot;
  (function registerSw() {
    try {
      if (!('serviceWorker' in navigator)) return;
      if (!/^https?:$/.test(location.protocol)) return;
      const root = whSwRoot();
      navigator.serviceWorker.register(root + 'sw.js', { scope: root })
        .catch(function () { /* offline first load or unsupported context — the next online load retries */ });
    } catch (_) { /* empty-catch-allow: registration is progressive enhancement; the page works without it */ }
  })();

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
