// capability: alert_toast_inline
// capability: display_source_chip
// ─────────────────────────────────────────────
// utils.js — Shared utilities for WorkHive platform
// Loaded before page scripts on every page.
// ─────────────────────────────────────────────

// ── Native-app feel fallback (rubric class T · React-Native benchmark, 2026-07-18) ──────────
// tokens.css carries the native-feel baseline (touch-action:manipulation + overscroll-behavior:
// contain) for the ~35 pages that link it; this guard injects the SAME baseline ONLY where
// tokens.css did NOT reach, so the WHOLE family gets the native feel with no duplication. These
// are BEHAVIOURAL props (no FOUC). Cited: external-css-touch-action, external-css-overscroll-behavior.
(function whNativeFeelFallback() {
  function apply() {
    try {
      var ta = (getComputedStyle(document.documentElement).touchAction || '') + ' ' + (getComputedStyle(document.body).touchAction || '');
      if (/manipulation|none|pan/.test(ta)) return;   // tokens.css already applied it
      var s = document.createElement('style');
      s.setAttribute('data-wh-native-feel', '1');
      s.textContent = 'html,body{touch-action:manipulation;overscroll-behavior:contain}' +
        '#wh-hub-tiles,.wh-fb-body,.calendar-wrap,.sidebar-items,.table-scroll,.chat-messages,.modal,.modal-body,.sheet,[role="dialog"],[class*="scroll"],[class*="overflow-y-auto"],[class*="overflow-auto"]{overscroll-behavior:contain}';
      (document.head || document.documentElement).appendChild(s);
    } catch (_) { /* empty-catch-allow: best-effort native-feel baseline */ }
  }
  if (document.body) apply(); else document.addEventListener('DOMContentLoaded', apply);
})();


// ============================================================================
// i18n LOCALE FLOOR (rubric N1) -- the shared half of the design system
// ============================================================================
// NN/g: a design system is "a style guide PLUS a component library ... reducing
// REDUNDANCY and creating a SHARED LANGUAGE across pages". We had the style guide
// (tokens.css) and NOT the component library -- which is measurably why 29 of 32 family
// pages fail N1. The i18n ENGINE was pasted inline FOUR times (analytics / hive / index /
// analytics-report) while the SHARED chrome stayed English-only: nav-hub.js reaches 31
// pages, this file 35, and neither could translate a single word.
//
// Hoisting the locale STATE + translator here gives every utils.js page the mechanics for
// free -- the same lever this file already uses for the focus ring ("without editing 40+
// pages individually"). Concretely: a worker who picks Filipino on the home dashboard now
// keeps it across the whole platform's chrome instead of it snapping back to English on
// the next page.
//
// DEFENSIVE BY DESIGN -- this FILLS A GAP, it never clobbers. A page with its own engine
// (analytics/hive/index) defines _t/WH_LANG later in the body and still wins; both read the
// same `wh_lang` key, so they agree. Pages with no engine get a working pass-through
// instead of a ReferenceError.
// [external-design-system-adoption-scale-consistency-across-, external-atomic-design-...]
(function whLocaleFloor() {
  try {
    if (typeof window.WH_LANG === 'undefined') {
      window.WH_LANG = (localStorage.getItem('wh_lang') === 'fil') ? 'fil' : 'en';
    }
  } catch (_) { /* empty-catch-allow: locale persistence is best-effort (private mode) */
    if (typeof window.WH_LANG === 'undefined') window.WH_LANG = 'en';
  }
  if (typeof window._t !== 'function') {
    // _t(en, fil) -- the platform's translator signature. Falls back to EN when a phrase
    // has no FIL yet, so a partial dictionary can never blank a label.
    window._t = function _t(en, fil) {
      return (window.WH_LANG === 'fil' && fil) ? fil : en;
    };
  }
  // <html lang> must follow the locale or a screen reader pronounces Filipino with English
  // phonemes (WCAG 3.1.1). Pages with their own engine set this too; same value, no fight.
  try {
    document.documentElement.lang = (window.WH_LANG === 'fil') ? 'fil' : 'en';
  } catch (_) { /* empty-catch-allow: documentElement always exists; guard is belt-and-braces */ }
})();


// ─────────────────────────────────────────────
// a11y floor — global keyboard focus ring (WCAG 2.4.11 / SC 2.4.7 focus-visible)
// ─────────────────────────────────────────────
// utils.js loads on every page before page scripts, so injecting one :focus-visible
// rule here gives every interactive control a visible keyboard focus indicator
// platform-wide (clears the Arc-K deterministic focus-visible floor without editing
// 40+ pages individually). Scoped to :focus-visible so mouse clicks show no outline;
// !important defeats any stray `outline:none`. Idempotent (id-guarded).
(function whInjectFocusRing() {
  try {
    if (typeof document === 'undefined' || document.getElementById('wh-a11y-focus')) return;
    var css = 'a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,' +
      'textarea:focus-visible,summary:focus-visible,[tabindex]:focus-visible,[role="button"]:focus-visible,' +
      '[role="link"]:focus-visible,[role="tab"]:focus-visible,[contenteditable="true"]:focus-visible{' +
      'outline:2px solid #F7A21B !important;outline-offset:2px !important;border-radius:3px;}';
    var st = document.createElement('style');
    st.id = 'wh-a11y-focus';
    st.textContent = css;
    (document.head || document.documentElement).appendChild(st);
  } catch (_) { /* empty-catch-allow: a11y focus-ring injection is best-effort styling */ }
})();

// ── Arc W · W1 — GLOBAL ELEVATION (depth lens), platform-wide ───────────────────
// The platform read flat/coplanar (R1: depth_floor=789, ~0 box-shadow across 800+
// card-like els). components.css carries the canonical elevation rules but is only
// <link>ed on 12 pages; this injection (same dual-delivery pattern as the E2 skeleton
// CSS + the focus-ring above) reaches the OTHER ~16 pages so EVERY page gets layered
// depth. Selectors are wrapped in :where() = ZERO specificity, so this is a pure
// DEFAULT: any page rule that styles a card's box-shadow (e.g. analytics' translucent
// cards, a status-glow .feed-card) ALWAYS wins regardless of DOM order — we lift only
// the currently-flat surfaces, never override intentional styling. box-shadow +
// transform are layout-neutral (no CLS / tap-target / animation-budget cost).
// Idempotent (id-guarded); shadow tokens defined here too since non-components.css
// pages don't get its :root (tokens.css only supplies the navy ladder).
(function whInjectElevation() {
  try {
    if (typeof document === 'undefined' || document.getElementById('wh-elevation')) return;
    var css =
      ':root{--wh-shadow-1:0 1px 2px rgba(0,0,0,0.20),0 2px 6px rgba(0,0,0,0.16);' +
      '--wh-shadow-3:0 12px 32px rgba(0,0,0,0.34),0 4px 12px rgba(0,0,0,0.22);}' +
      // card/panel/tile/widget roles -> soft float (matches the Arc W probe's card roles)
      ':where(.simple-card,.action-card,.card,[class*="-card"],.panel,[class*="-panel"],' +
      '.tile,[class*="-tile"],.widget,[class*="-widget"],.wh-card){box-shadow:var(--wh-shadow-1);}' +
      // overlays/modals/sheets float highest
      ':where(.modal,.modal-content,.modal-overlay,.sheet-overlay,[role="dialog"]){box-shadow:var(--wh-shadow-3);}' +
      // surface-tint lift for the shared KPI card where the page hasn't themed it itself
      ':where(.simple-card){background:var(--wh-navy-mid);}' +
      // M/S press-feedback for gloved field workers (mobile-maestro rule #5)
      ':where(button,.btn,a.btn,[role="button"]):active{transform:scale(0.98);}' +
      // H lens (W3) — ONE hero KPI tile per dashboard dominates. NOT :where: a `hero` modifier the
      // page author opted into MUST win over the page's `.sc-hero` (0,1,0); 0,2,1 beats it.
      '.simple-card.hero .sc-hero{font-size:clamp(2rem,5.5vw,2.4rem);line-height:1.1;}';
    var st = document.createElement('style');
    st.id = 'wh-elevation';
    st.textContent = css;
    (document.head || document.documentElement).appendChild(st);
  } catch (_) { /* empty-catch-allow: elevation-shadow CSS injection is best-effort styling */ }
})();

// ─────────────────────────────────────────────
// Arc W · W5 — ONE icon system (inline-SVG), platform-wide emoji → SVG
// ─────────────────────────────────────────────
// Ian's call (2026-06-25): standardize the platform's icon glyphs to ONE inline-SVG system
// (the roadmap I-lens target), replacing the scattered emoji. Lucide-style 24×24 paths (MIT),
// stroke=currentColor so a mono icon inherits its text color; status dots carry their own fill.
// Exposed as window.whIcon(name,{label,cls}) for new markup, AND auto-applied: a guarded text-node
// walk swaps known emoji → <svg.wh-i>. SAFETY: runs on `load` (after page scripts have read any
// textContent during render); skips input/textarea/select/script/style/code/pre/svg/[contenteditable]
// + [data-no-iconify]; marks processed; a MutationObserver re-runs on injected subtrees (so JS-built
// lists convert too) with a guard against re-processing our own SVGs. Idempotent (id-guarded CSS).
(function whIconSystem() {
  if (typeof document === 'undefined') return;
  var NS = 'http://www.w3.org/2000/svg';
  // name -> { d: inner SVG markup, fill?: status color (filled, no stroke) }
  var ICONS = {
    check:        { d: '<path d="M20 6 9 17l-5-5"/>' },
    x:            { d: '<path d="M18 6 6 18M6 6l12 12"/>' },
    warning:      { d: '<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3z"/><path d="M12 9v4"/><path d="M12 17h.01"/>' },
    star:         { d: '<path d="M11.5 2.3a.5.5 0 0 1 1 0l2.3 4.7a2 2 0 0 0 1.6 1.1l5.1.8a.5.5 0 0 1 .3.9l-3.7 3.6a2 2 0 0 0-.6 1.9l.9 5.1a.5.5 0 0 1-.8.6l-4.6-2.4a2 2 0 0 0-2 0L6.4 21a.5.5 0 0 1-.8-.6l.9-5.1a2 2 0 0 0-.6-1.9L2.2 9.8a.5.5 0 0 1 .3-.9l5.1-.8a2 2 0 0 0 1.6-1.1z"/>', sfill: 1 },
    wrench:       { d: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>' },
    'thumbs-up':  { d: '<path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88z"/>' },
    'thumbs-down':{ d: '<path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88z"/>' },
    clipboard:    { d: '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>' },
    bot:          { d: '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2M20 14h2M15 13v2M9 13v2"/>' },
    package:      { d: '<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5M12 22V12"/>' },
    zap:          { d: '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>' },
    chart:        { d: '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><rect x="7" y="13" width="3" height="5"/><rect x="12" y="9" width="3" height="9"/><rect x="17" y="5" width="3" height="13"/>' },
    sparkles:     { d: '<path d="M9.94 14.5 12 21l2.06-6.5L20 12l-5.94-2.5L12 3l-2.06 6.5L4 12z"/>' },
    file:         { d: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/><path d="M14 2v5h5M8 13h8M8 17h8"/>' },
    search:       { d: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>' },
    calendar:     { d: '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M8 2v4M16 2v4M3 10h18"/>' },
    gear:         { d: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>' },
    save:         { d: '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7M7 3v4a1 1 0 0 0 1 1h7"/>' },
    eye:          { d: '<path d="M2.06 12.35a1 1 0 0 1 0-.7 10.75 10.75 0 0 1 19.88 0 1 1 0 0 1 0 .7 10.75 10.75 0 0 1-19.88 0"/><circle cx="12" cy="12" r="3"/>' },
    flame:        { d: '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.07-2.14-.71-3.9 1-5.5C9.5 5 11 6 12 6c1.5-1.5 2-3 2-3 2 2 4 4.5 4 8a6 6 0 0 1-12 0c0-1.5.5-2.5 1.5-3.5"/>' },
    pencil:       { d: '<path d="M21.17 6.83 17.17 2.83a2 2 0 0 0-2.83 0L3 14.17V21h6.83L21.17 9.66a2 2 0 0 0 0-2.83z"/>' },
    stop:         { d: '<path d="M2.59 7.91 7.9 2.6a2 2 0 0 1 1.42-.59h5.36a2 2 0 0 1 1.42.59l5.31 5.31a2 2 0 0 1 .59 1.42v5.36a2 2 0 0 1-.59 1.42l-5.31 5.31a2 2 0 0 1-1.42.59H9.32a2 2 0 0 1-1.42-.59L2.6 16.1a2 2 0 0 1-.59-1.42V9.32a2 2 0 0 1 .58-1.41z"/>' },
    lock:         { d: '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>' },
    factory:      { d: '<path d="M12 16h.01M16 16h.01M3 19a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8l-7 4V8l-7 4V4a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1z"/>' },
    globe:        { d: '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20M2 12h20"/>' },
    crystal:      { d: '<circle cx="12" cy="10" r="7"/><path d="M7 21h10M9 17l-1 4M15 17l1 4"/>' },
    bee:          { d: '<path d="M12 8a4 4 0 0 1 4 4v3a4 4 0 0 1-8 0v-3a4 4 0 0 1 4-4z"/><path d="M8 11h8M8 14h8M9 5 7 3M15 5l2-2"/>' },
    'arrow-down': { d: '<path d="M12 5v14M19 12l-7 7-7-7"/>' },
    'arrow-up':   { d: '<path d="M12 19V5M5 12l7-7 7 7"/>' },
    dot:          { d: '<circle cx="12" cy="12" r="9"/>', sfill: 1 },
    shield:       { d: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>' },
    target:       { d: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>' },
    user:         { d: '<circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/>' },
    chat:         { d: '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22z"/>' },
    refresh:      { d: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>' },
    mail:         { d: '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>' },
    bulb:         { d: '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>' },
    clock:        { d: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>' },
    camera:       { d: '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3z"/><circle cx="12" cy="13" r="3"/>' },
    trash:        { d: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>' },
    plus:         { d: '<path d="M5 12h14M12 5v14"/>' },
    compass:      { d: '<circle cx="12" cy="12" r="10"/><path d="m16.24 7.76-2.12 6.36-6.36 2.12 2.12-6.36z"/>' },
    droplet:      { d: '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C8 11.1 7 13 7 15a7 7 0 0 0 7 7z"/>' },
    award:        { d: '<circle cx="12" cy="8" r="6"/><path d="M15.5 12.5 17 22l-5-3-5 3 1.5-9.5"/>' },
    megaphone:    { d: '<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>' },
    help:         { d: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>' },
    heart:        { d: '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.29 1.51 4.04 3 5.5l7 7Z"/>', sfill: 1 },
    bug:          { d: '<path d="m8 2 1.88 1.88M14.12 3.88 16 2M9 7.13v-1a3.003 3.003 0 1 1 6 0v1"/><path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6M12 20v-9M6.53 9C4.6 8.8 3 7.1 3 5M6 13H2M3 21c0-2.1 1.7-3.9 3.8-4M20.97 5c0 2.1-1.6 3.8-3.5 4M22 13h-4M17.2 17c2.1.1 3.8 1.9 3.8 4"/>' },
    back:         { d: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5 5.5 5.5 0 0 1-5.5 5.5H11"/>' },
    thermometer:  { d: '<path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0z"/>' },
    battery:      { d: '<rect width="16" height="10" x="2" y="7" rx="2" ry="2"/><path d="M22 11v2"/>' },
    wind:         { d: '<path d="M12.8 19.6A2 2 0 1 0 14 16H2"/><path d="M17.5 8a2.5 2.5 0 1 1 2 4H2"/><path d="M9.8 4.4A2 2 0 1 1 11 8H2"/>' },
    plug:         { d: '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8z"/>' },
  };
  // emoji glyph -> icon name (or {name, fill} for colored status dots).
  var MAP = {
    '✓': 'check', '✔': 'check', '✅': 'check',
    '✗': 'x', '✕': 'x', '✖': 'x', '❌': 'x', '❎': 'x',
    '⚠': 'warning', '❗': 'warning', '❕': 'warning', '⁉': 'warning',
    '⭐': 'star', '★': 'star', '☆': 'star',
    '🔧': 'wrench', '🛠': 'wrench',
    '👍': 'thumbs-up', '👎': 'thumbs-down',
    '📋': 'clipboard', '📝': 'pencil', '✏': 'pencil', '✎': 'pencil', '✒': 'pencil',
    '🤖': 'bot', '📦': 'package',
    '⚡': 'zap', '📊': 'chart', '📈': 'chart', '📉': 'chart',
    '✨': 'sparkles', '📄': 'file', '📃': 'file', '📁': 'file',
    '🔍': 'search', '🔎': 'search',
    '📅': 'calendar', '📆': 'calendar', '🗓': 'calendar',
    '⚙': 'gear', '🔧️': 'wrench',
    '💾': 'save', '👁': 'eye', '👀': 'eye',
    '🔥': 'flame', '🛑': 'stop', '🔒': 'lock', '🔓': 'lock',
    '🏭': 'factory', '🌐': 'globe', '🔮': 'crystal', '🐝': 'bee',
    '⬇': 'arrow-down', '⬆': 'arrow-up',
    '📐': 'gear', '📏': 'gear',
    // long-tail (full coverage so every page reaches emoji=0 → one icon system)
    '🛡': 'shield', '🎯': 'target', '👤': 'user', '👷': 'user', '🧑': 'user',
    '💬': 'chat', '🗣': 'chat', '🔄': 'refresh', '🔁': 'refresh', '🔃': 'refresh',
    '✉': 'mail', '📧': 'mail', '📥': 'mail', '📤': 'mail', '📢': 'megaphone',
    '💡': 'bulb', '🕐': 'clock', '🕒': 'clock', '⏰': 'clock', '⏱': 'clock',
    '📷': 'camera', '📸': 'camera', '🗑': 'trash', '➕': 'plus', '🧭': 'compass',
    '🚰': 'droplet', '💧': 'droplet', '🏆': 'award', '🥇': 'award', '🥈': 'award',
    '🥉': 'award', '🎖': 'award', '🎉': 'sparkles', '❄': 'sparkles', '🚨': 'warning',
    '⛔': 'stop', '🧠': 'bot', '🌏': 'globe', '🌍': 'globe', '🧬': 'gear',
    '🧰': 'wrench', '🔩': 'wrench', '🏗': 'factory', '📂': 'file', '📚': 'file',
    '📖': 'file', '🖨': 'file', '📎': 'file', '✍': 'pencil', '👋': 'thumbs-up',
    '💪': 'thumbs-up', '👀': 'eye',
    // engineering-design domain glyphs (HVAC / electrical disciplines) + weather
    '🌡': 'thermometer', '🔋': 'battery', '🔌': 'plug', '💨': 'wind', '🌬': 'wind',
    '🌫': 'wind', '♻': 'refresh', '🌧': 'droplet', '🌦': 'droplet', '🧊': 'sparkles',
    '🪙': 'dot', '🪣': 'droplet', '🪨': 'dot', '🌀': 'refresh', '🔆': 'bulb', '☀': 'bulb',
    '❓': 'help', '❔': 'help', '🐞': 'bug', '🐛': 'bug', '🌊': 'droplet',
    '↩': 'back', '↪': 'back', '⤴': 'back', '⤵': 'back',
    '💛': 'heart', '💚': 'heart', '💙': 'heart', '❤': 'heart', '🧡': 'heart',
    '💜': 'heart', '🤍': 'heart', '🖤': 'heart', '💗': 'heart', '💖': 'heart',
    '\u{1FAD9}': 'package', '\u{1FA99}': 'dot', '\u{1F6E2}': 'droplet', '\u{1F525}': 'flame',
    // colored status dots
    '🔴': { n: 'dot', f: '#ef4444' }, '🟡': { n: 'dot', f: '#eab308' },
    '🟢': { n: 'dot', f: '#22c55e' }, '🔵': { n: 'dot', f: '#3b82f6' },
    '🟠': { n: 'dot', f: '#f97316' }, '⚫': { n: 'dot', f: '#6b7280' }, '⚪': { n: 'dot', f: '#d1d5db' },
  };
  function svgMarkup(name, opts) {
    var ic = ICONS[name]; if (!ic) return null;
    opts = opts || {};
    var fill = opts.fill || (ic.sfill ? 'currentColor' : 'none');
    var stroke = (ic.sfill || opts.fill) ? 'none' : 'currentColor';
    var label = opts.label || name;
    return '<svg class="wh-i' + (opts.cls ? ' ' + opts.cls : '') + '" viewBox="0 0 24 24" fill="' + fill + '" stroke="' + stroke +
      '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" role="img" aria-label="' + label + '">' + ic.d + '</svg>';
  }
  window.whIcon = function (name, opts) { return svgMarkup(name, opts) || ''; };

  // build a single regex of all mapped glyphs (+ optional VS16). Longest keys first so a
  // surrogate-pair-with-VS16 wins over the bare pair.
  var keys = Object.keys(MAP).sort(function (a, b) { return b.length - a.length; });
  var esc = function (s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); };
  var RE;
  try { RE = new RegExp('(?:' + keys.map(esc).join('|') + ')\\uFE0F?', 'gu'); }
  catch (e) { try { RE = new RegExp('(?:' + keys.map(esc).join('|') + ')\\uFE0F?', 'g'); } catch (e2) { return; } }
  var SKIP = { INPUT: 1, TEXTAREA: 1, SELECT: 1, SCRIPT: 1, STYLE: 1, CODE: 1, PRE: 1, SVG: 1, NOSCRIPT: 1 };
  function skip(el) {
    for (var n = el; n; n = n.parentElement) {
      if (!n.tagName) continue;
      if (SKIP[n.tagName.toUpperCase()]) return true;
      if (n.isContentEditable) return true;
      if (n.hasAttribute && (n.hasAttribute('data-no-iconify') || n.classList.contains('wh-i'))) return true;
    }
    return false;
  }
  function spanFor(glyph) {
    var m = MAP[glyph.replace(/️$/, '')] || MAP[glyph];
    var name = (typeof m === 'string') ? m : (m && m.n);
    var fill = (m && m.f) || null;
    var html = svgMarkup(name, { fill: fill, label: name });
    if (!html) return null;
    var span = document.createElement('span');
    span.className = 'wh-i-wrap'; span.setAttribute('aria-hidden', 'false');
    span.innerHTML = html;
    return span.firstChild;
  }
  function walk(root) {
    if (!root || skip(root.nodeType === 1 ? root : root.parentElement || document.body)) return;
    var tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (t) {
        if (!t.nodeValue || !RE.test(t.nodeValue)) return NodeFilter.FILTER_REJECT;
        RE.lastIndex = 0;
        return skip(t.parentElement) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
      }
    });
    var hits = [], t;
    while ((t = tw.nextNode())) hits.push(t);
    for (var i = 0; i < hits.length; i++) {
      var node = hits[i], text = node.nodeValue, frag = document.createDocumentFragment(), last = 0, m2; RE.lastIndex = 0;
      while ((m2 = RE.exec(text))) {
        if (m2.index > last) frag.appendChild(document.createTextNode(text.slice(last, m2.index)));
        var svg = spanFor(m2[0]);
        if (svg) frag.appendChild(svg); else frag.appendChild(document.createTextNode(m2[0]));
        last = m2.index + m2[0].length;
      }
      if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
      if (node.parentNode) node.parentNode.replaceChild(frag, node);
    }
  }
  function run() { try { walk(document.body); } catch (e) { /* empty-catch-allow: best-effort icon injection; a walk failure must never break the page */ } }
  // convert JS-injected subtrees (lists/cards built after load), guarded against our own SVGs.
  var mo = null;
  try {
    mo = new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        var added = muts[i].addedNodes;
        for (var j = 0; j < added.length; j++) {
          var nd = added[j];
          if (nd.nodeType === 1 && !(nd.classList && nd.classList.contains('wh-i')) && nd.tagName !== 'svg') walk(nd);
          else if (nd.nodeType === 3) walk(nd.parentElement || document.body);
        }
      }
    });
  } catch (e) { /* empty-catch-allow: MutationObserver is an optional UI enhancement */ }
  function start() {
    // Arc W · W5 REVERSED (2026-07-19, Ian: "I changed my mind, I prefer the emojis now").
    // The emoji→SVG auto-swap is DISABLED so the platform's ~430 authored emoji render AS
    // emoji (emoji-first, the colorful voice Ian prefers). window.whIcon() is retained for
    // any programmatic caller; the text-node walker + MutationObserver no longer run.
    // To restore the mono-SVG system, delete this early return.
    return;
    setTimeout(run, 0);                                   // initial pass once the static DOM is parsed
    if (mo) try { mo.observe(document.body, { childList: true, subtree: true }); } catch (e) { /* empty-catch-allow: observe is best-effort UI enhancement */ }
  }
  // run on DOMContentLoaded (+setTimeout so it follows page-init handlers that read textContent),
  // NOT `load`-`load` waits on all images and can land after first interaction / a probe window.
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
  // sizing/baseline CSS for inline icons (id-guarded).
  if (!document.getElementById('wh-icon-css')) {
    var st = document.createElement('style'); st.id = 'wh-icon-css';
    st.textContent = '.wh-i{display:inline-block;width:1em;height:1em;vertical-align:-0.125em;flex:none}';
    (document.head || document.documentElement).appendChild(st);
  }
})();

// ─────────────────────────────────────────────
// getDb() — shared Supabase client singleton
// ─────────────────────────────────────────────
// Calling `supabase.createClient()` more than once per page (or once per
// IIFE) triggers the "Multiple GoTrueClient instances detected" warning
// in the Supabase JS SDK. The clients race on the same localStorage auth
// key and may produce undefined behavior under concurrent reads.
//
// The fix: every script that needs a Supabase client should call
// `window.getDb(url, key)` instead. The first call creates the client;
// subsequent calls return the same instance for the page's lifetime.
//
// Validator: validate_supabase_singleton.py flags any HTML page with >1
// inline `supabase.createClient(...)` call.
window.getDb = function(url, key) {
  if (window._whSupabaseClient) return window._whSupabaseClient;
  if (!window.supabase || typeof window.supabase.createClient !== 'function') {
    throw new Error('getDb() called before @supabase/supabase-js loaded');
  }
  // Arc S F-lens (F-002/F-008): bound EVERY PostgREST/Auth/Storage request with a
  // timeout so a dead or slow backend FAILS FAST (caller gets an error -> degraded
  // UI) instead of hanging the tab forever on an open socket. One install here
  // covers all db.from()/db.rpc()/db.auth/db.storage calls platform-wide, so no
  // page reinvents it. Generous default (45s) leaves legit slow ops (2G upload,
  // big RPC) room to finish; tune via window.WH_DB_TIMEOUT_MS. A caller that
  // supplies its own AbortSignal keeps full control (we don't double-wrap).
  const TIMEOUT_MS = window.WH_DB_TIMEOUT_MS || 45000;
  const _timeoutFetch = (input, init) => {
    // Supabase client transport-fetch wrapper (not a data fetch): transport/abort errors
    // propagate into every query's {data, error}, handled by each caller — a .catch here
    // would swallow the error the client must surface. Hence fetch-error-allow on each.
    init = init || {};
    if (init.signal) return fetch(input, init); // fetch-error-allow: transport wrapper (see above)
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      try { ctrl.abort(new DOMException('WH_DB_TIMEOUT', 'TimeoutError')); }
      catch (_) { ctrl.abort(); } // older engines: abort() takes no reason
    }, TIMEOUT_MS);
    // fetch-error-allow: transport wrapper — error surfaces via the client's {data, error}
    return fetch(input, { ...init, signal: ctrl.signal }).finally(() => clearTimeout(t));
  };
  window._whSupabaseClient = window.supabase.createClient(url, key, {
    global: { fetch: _timeoutFetch },
    // Finding #6 (idle/expired-session robustness, 2026-07-06): make the refresh contract
    // explicit. autoRefreshToken keeps the access token fresh; persistSession restores it on
    // reload. The gap this addresses: a tab left idle for hours (its scheduled refresh timer
    // never fired while backgrounded) would fire its first authed read on the STALE token and
    // silently 401, leaving a broken "signed-in" dashboard. The visibilitychange handler below
    // refreshes on wake, before the user's next action.
    auth: { autoRefreshToken: true, persistSession: true, detectSessionInUrl: true },
  });
  // Finding #6: proactively refresh the session when the tab returns to the foreground after
  // being hidden — covers the "woke from hours of idle" case where the background refresh timer
  // didn't run, so queries after wake use a fresh token instead of 401-ing on the expired one.
  try {
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible' && window._whSupabaseClient) {
        // getSession() refreshes an expired access token when a valid refresh token exists.
        window._whSupabaseClient.auth.getSession().catch(function () { /* best-effort */ });
      }
    });
  } catch (_) { /* empty-catch-allow: visibilitychange unsupported */ }
  // Arc S D-lens (D-004): expose the project URL so the connectivity widget can
  // health-ping the backend (every page reaches the backend through getDb, so this
  // is the one reliable place to publish it). Publish the anon/publishable key too:
  // /auth/v1/health 401s WITHOUT an apikey on current Supabase, which false-degraded
  // the connectivity chip to "Backend down" on a healthy backend (live prod journey,
  // 2026-07-18). The publishable key is public-by-design (already shipped in the page).
  window.WH_SUPABASE_URL = url;
  window.WH_SUPABASE_ANON_KEY = key;
  return window._whSupabaseClient;
};

// XSS escape — all 5 characters
function escHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// escJsAttr — XSS-safe for a value placed inside a JS STRING LITERAL that itself
// sits inside an HTML attribute, e.g.  onclick="fn('${escJsAttr(v)}')".
// escHtml ALONE is WRONG here: the HTML parser decodes &#39; back to ' BEFORE the
// handler compiles, so a value like  ' ),alert(1),('  breaks out of the string arg
// and runs — a stored, privilege-escalating XSS (Hive board, confirmed 2026-07-10).
// Fix = JS-escape FIRST (\ ' newlines) so the post-HTML-decode text is a valid JS
// string, THEN HTML-escape so the attribute stays well-formed and its entities
// decode back to exactly the JS-safe text. The IDEAL is event-delegation + dataset
// (no user data in code at all); use this when an inline handler must stay.
function escJsAttr(str) {
  return String(str == null ? '' : str)
    .replace(/\\/g, '\\\\')   // JS: backslash first (must precede the quote escape)
    .replace(/'/g, "\\'")      // JS: single quote → escaped quote
    .replace(/\r/g, '\\r')
    .replace(/\n/g, '\\n')
    .replace(/&/g, '&amp;')    // HTML: keep the attribute well-formed; these decode
    .replace(/</g, '&lt;')     // back to chars that are harmless inside a '…' JS string
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─────────────────────────────────────────────
// renderSourceChip — KPI source/window chip helper (Phase 3.1)
// ─────────────────────────────────────────────
// Every dashboard card that displays a canonical metric (MTBF, risk, PM
// compliance, etc.) must show WHERE the number came from and WHAT window it
// covers, so users never silently compare a 30-day live snapshot to a 365-day
// nightly snapshot. This function is the single visual contract. Pass an
// options object; returns a `<p>` string ready for innerHTML.
//
// Standard order: freshness . source . window . notes
//   - freshness: "Live data" | "Daily snapshot at 13:00 PHT" | "Live recomputation each refresh"
//   - source:    canonical view name (rendered in <code>), e.g. "v_risk_truth"
//   - window:    "365-day failure window" | "30-day overdue threshold" etc.
//   - notes:     additional clauses (array of strings)
//
// Skill alignment: analytics-engineer ("any custom composite must be labeled"),
// architect (one visual contract per concept), KPI_ENGINE.md rule 2.
//
// E1 (2026-06-14 — user-facing jargon audit, STREAMLINE §13/§14): the `source:`
// field is kept CANONICAL (raw view/table names) because validate_source_chip_truth.py
// verifies every v_*_truth in it against a real .from() read — that lineage check is
// load-bearing. But the user must NEVER see `v_logbook_truth` on the glass. So the
// chip TRANSLATES source through WH_SOURCE_LABELS at render time: the call keeps the
// canonical name, the worker reads plain language. Keep this map current when a new
// canonical view ships (validate_user_facing_jargon.py exempts the source: arg precisely
// because it is machine-translated here; it FAILs raw view/RPC/SQL jargon everywhere else).
var WH_SOURCE_LABELS = {
  'v_logbook_truth':            'logbook',
  'v_pm_scope_items_truth':     'PM schedule',
  'v_pm_compliance_truth':      'PM compliance',
  'v_inventory_items_truth':    'inventory',
  'v_risk_truth':               'risk scores',
  'v_asset_truth':              'asset records',
  'v_fmea_truth':               'failure analysis',
  'v_weibull_truth':            'reliability analysis',
  'v_maturity_truth':           'hive maturity',
  'v_knowledge_freshness_truth':'knowledge base',
  'v_ai_reports_truth':         'AI reports',
  'v_alert_truth':              'alerts',
  'v_hive_readiness_truth':     'hive readiness',
  'v_marketplace_sellers_truth':'seller ratings',
  'hive_adoption_score':        'adoption score',
  'hive_benchmarks':            'hive benchmarks',
  'network_benchmarks':         'network benchmarks',
  'hive_audit_log':             'activity log',
  'hive_retention_config':      'retention settings',
  'worker_achievements':        'achievements',
  'achievement_xp_log':         'XP history',
  'schedule_items':             'your schedule',
  'community_posts':            'community posts',
  'community_replies':          'replies',
  'community_reactions':        'reactions',
  'analytics_events':           'usage analytics',
  'marketplace_listings':       'marketplace listings',
  'marketplace_orders':         'orders',
  'marketplace_disputes':       'disputes',
  'marketplace_inquiries':      'inquiries',
  'ai_cost_log':                'AI usage',
  'pm_assets':                  'PM assets',
  'pm_scope_items':             'PM tasks',
  'pm_completions':             'PM completions',
  'inventory_items':            'inventory',
  'inventory_transactions':     'stock movements',
  'integration_configs':        'integrations',
  'external_sync':              'sync history',
  'engineering_calcs':          'saved calculations',
  'canonical_formulas':         'standard formulas',
  'canonical_standards':        'engineering standards',
  'projects':                   'projects',
  'project_items':              'project tasks',
  'shift_plans':                'shift plan',
  'skill_profiles':             'skills',
  'skill_badges':               'badges',
  'platform_health.json':       'platform health check',
  'manual':                     'your own entries',
  // Knowledge corpora — real data sources, shown to the user:
  'fault_knowledge':            'fault history',
  'skill_knowledge':            'skills',
  'pm_knowledge':               'PM knowledge',
  // Lineage-anchor tokens that validate_canonical_anchor.py requires in the chip
  // CALL (for panel→fuel traceability) but that are NOT data sources to show a
  // user — a tier label / an edge-fn name / a column / a schema registry. Kept in
  // the source: field (machine plane) and rendered to NOTHING here so the glass
  // stays plain:
  'at_risk':                    '',
  'benchmark-compute':          '',
  'canonical_agent_contracts':  '',
  'qty_on_hand':                '',
  'min_qty':                    '',
};

// Translate one source token (leading identifier of a "+"-segment) to a friendly
// label. Unknown tokens are humanized (drop v_ / _truth / .json, underscores → spaces)
// so a new table never leaks a raw name even before it's added to the map.
function _whFriendlySourceToken(tok) {
  tok = String(tok).trim();
  if (WH_SOURCE_LABELS.hasOwnProperty(tok)) return WH_SOURCE_LABELS[tok];
  return tok.replace(/^v_/, '').replace(/_truth$/, '').replace(/\.json$/, '').replace(/_/g, ' ').trim();
}

// Turn a canonical source string ("v_logbook_truth + v_risk_truth via Postgres RPCs")
// into a plain phrase ("logbook & risk scores"). Splits on "+", takes the LEADING
// identifier of each segment (ignoring trailing prose / parentheticals), translates,
// de-dupes, and joins with commas + an ampersand before the last.
function _whFriendlySource(src) {
  var segs = String(src).split('+');
  var out  = [];
  for (var i = 0; i < segs.length; i++) {
    var s = segs[i].trim();
    if (!s) continue;
    var m = s.match(/^[A-Za-z0-9_.-]+/);  // leading table/view identifier (hyphen for edge-fn anchor tokens)
    var label = _whFriendlySourceToken(m ? m[0] : s);
    if (label && out.indexOf(label) === -1) out.push(label);
  }
  if (out.length === 0) return '';
  if (out.length === 1) return out[0];
  return out.slice(0, -1).join(', ') + ' & ' + out[out.length - 1];
}

// ─────────────────────────────────────────────
// whI18nApply — ONE shared [data-i] swapper (N1)
// ─────────────────────────────────────────────
// Pages WITHOUT their own i18n engine (index/hive/analytics keep theirs) tag static
// labels with data-i and declare `window.WH_FIL_PAGE = { key: 'Filipino', … }`.
// utils.js already supplies WH_LANG + _t; this closes the loop for static markup.
// EN is the markup itself, so applying is one-way (fil) — a reload restores EN.
// WH_FIL_COMMON — the SHARED Filipino dictionary for labels that repeat on every page
// (N1 accelerator, 2026-07-16). A page tags a common control `data-i="cancel"` and it is
// translated from HERE — no per-page dict entry needed. Only genuinely page-UNIQUE labels
// go in that page's WH_FIL_PAGE. This is the centralized lever (METHOD LAW) for N1's common
// half: one edit here fixes the shared vocabulary across all pages; a page dict overrides
// per key where the local wording differs. Natural Taglish (English domain terms kept).
window.WH_FIL_COMMON = {
  cancel: 'Kanselahin', save: 'I-save', saved: 'Na-save', back: 'Bumalik', next: 'Susunod',
  more: 'Higit pa', less: 'Bawas', show: 'Ipakita', hide: 'Itago', showall: 'Ipakita Lahat',
  close: 'Isara', open: 'Buksan', search: 'Maghanap', searchteam: 'Hanapin sa Team',
  export: 'I-export', exportcsv: 'I-export sa CSV', edit: 'I-edit', 'delete': 'Burahin',
  remove: 'Alisin', add: 'Magdagdag', submit: 'Isumite', send: 'Ipadala', confirm: 'Kumpirmahin',
  refresh: 'I-refresh', filter: 'I-filter', filters: 'Mga Filter', clear: 'I-clear',
  clearform: 'I-clear ang form', clearfilters: 'I-clear ang mga filter', apply: 'Ilapat',
  done: 'Tapos', retry: 'Subukan Muli', viewall: 'Tingnan Lahat', settings: 'Mga Setting',
  help: 'Tulong', why: 'Bakit?', learnmore: 'Alamin Pa', getstarted: 'Magsimula',
  signin: 'Mag-sign In', signout: 'Mag-sign Out', myentries: 'Aking Mga Entry',
  teamfeed: 'Feed ng Team', loading: 'Naglo-load', today: 'Ngayon', thisweek: 'Ngayong Linggo',
  overdue: 'Lumipas na', duesoon: 'Malapit nang sumapit', ontrack: 'Nasa tamang landas',
  register: 'Irehistro', registerasset: 'Irehistro ang Asset', generate: 'I-generate',
  publish: 'I-publish', archive: 'I-archive', addcontact: 'Magdagdag ng Kontak',
  logwork: 'I-log ang trabaho', schedule: 'I-iskedyul', restock: 'Mag-restock',
  approve:"Aprubahan", reject:"Tanggihan", restore:"Ibalik", release:"I-release", refund:"I-refund", view:"Tingnan", showdetails: 'Ipakita ang detalye', hidedetails: 'Itago ang detalye', loadmore: 'Mag-load pa',
  viewinforum: 'Tingnan sa forum', route: 'Ruta', window: 'Window', status: 'Status',
  // Shared calendar/form vocabulary (2026-07-19): repeats across dayplanner/logbook/etc. — one entry
  // here fixes every page that tags these (was causing marked-but-untranslated FIL on dayplanner).
  day: 'Araw', week: 'Linggo', month: 'Buwan', year: 'Taon', category: 'Kategorya', notes: 'Mga Tala',
  // Shared maturity-gate headings (maturity-gate.js renders these on every gated surface).
  mg_unlocks_at: 'bubukas sa Stair', mg_hive_now: 'Ang hive mo ngayon',
};

function whI18nApply(dict) {
  if (typeof window !== 'undefined' && window.WH_LANG !== 'fil') return;
  // Page dict overrides the shared common dict per key.
  var merged = Object.assign({}, (typeof window !== 'undefined' && window.WH_FIL_COMMON) || {}, dict || {});
  if (!Object.keys(merged).length) return;
  document.querySelectorAll('[data-i]').forEach(function (el) {
    var k = el.getAttribute('data-i');
    if (merged[k] != null) el.textContent = merged[k];
  });
}
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', function () {
    // Apply whenever FIL is active — even a page with NO page dict gets its common labels
    // translated from WH_FIL_COMMON (that is the whole point of the shared dict).
    if (window.WH_FIL_PAGE || window.WH_FIL_COMMON) whI18nApply(window.WH_FIL_PAGE || {});
  });
}

// ─────────────────────────────────────────────
// whProgressStrip — ONE shared goal-gradient strip (H1, worker-daily pages)
// ─────────────────────────────────────────────
// Goal-gradient (Laws of UX): people accelerate toward a visible goal. Worker-daily
// pages (meta[name="worker-daily"]) show TODAY's real progress — never an invented
// quota. done/total MUST come from live page data; callers skip the strip when
// total===0 (an empty bar invents a journey — the A3 nothing-to-disclose error).
// Track+fill markup + role=progressbar keep it honest to AT and the rubric lens.
function whProgressStrip(label, done, total, opts) {
  opts = opts || {};
  if (!total || total < 0) return '';
  var e = escHtml;
  var _tt = (typeof window !== 'undefined' && typeof window._t === 'function') ? window._t : function (en) { return en; };
  var k = Math.max(0, Math.min(done || 0, total));
  var pct = Math.round((k / total) * 100);
  var fillCol = pct >= 100 ? '#86EFAC' : 'linear-gradient(90deg, var(--wh-orange), var(--wh-orange-light))';
  return '<div class="wh-progress-strip" role="progressbar" aria-valuemin="0" aria-valuemax="' + total + '" aria-valuenow="' + k + '"'
    + ' aria-label="' + e(_tt(label)) + ': ' + k + ' of ' + total + '"'
    + ' style="margin:0 0 12px;padding:10px 12px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:12px;">'
    + '<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px;">'
    +   '<span style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:rgba(255,255,255,0.62);">' + e(_tt(label)) + '</span>'
    +   '<span style="font-size:.72rem;font-weight:800;color:#F4F6FA;font-variant-numeric:tabular-nums;">' + k + ' <span style="font-weight:600;color:rgba(255,255,255,0.62);">' + e(_tt('of')) + ' ' + total + '</span></span>'
    + '</div>'
    + '<div class="wh-progress-track" style="height:6px;border-radius:999px;background:rgba(255,255,255,0.08);overflow:hidden;">'
    +   '<div class="wh-progress-fill" style="width:' + pct + '%;height:100%;border-radius:999px;background:' + fillCol + ';transition:width .4s;"></div>'
    + '</div>'
    + '</div>';
}

function renderSourceChip(opts) {
  opts = opts || {};
  // N1 safe _t fallback: pages without an i18n layer get the EN string unchanged,
  // so this shared renderer can translate without breaking them.
  var _tt = (typeof window !== 'undefined' && typeof window._t === 'function') ? window._t : function (en) { return en; };
  var source    = opts.source    || '';
  var freshness = opts.freshness || '';
  var win       = opts.window    || '';
  var notes     = Array.isArray(opts.notes) ? opts.notes : [];
  var method    = Array.isArray(opts.method) ? opts.method : [];

  var parts = [];
  if (freshness) parts.push(escHtml(freshness));
  if (source) {
    var friendly = _whFriendlySource(source);
    if (friendly) {
      // One whole template per locale with a single slot, rather than gluing a
      // prefix onto a noun -- the possessive sits differently in Filipino (N1).
      var f = escHtml(friendly);
      parts.push(/^your\b/.test(friendly)
        ? _tt('Based on ' + f,      'Batay sa ' + f)
        : _tt('Based on your ' + f, 'Batay sa iyong ' + f));
    }
  }
  if (win) parts.push(escHtml(win));
  for (var i = 0; i < notes.length; i++) {
    if (notes[i]) parts.push(escHtml(String(notes[i])));
  }

  // Arc L · L1 CLS: padding (not margin) for the top gap — a top-margin on this <p> collapses
  // through the empty source-chip slot + the shared <main>/.page scaffold, translating the whole
  // page down ~12px at first data-render (proven on predictive.html). padding never collapses;
  // with no background the 3px gap is visually identical.
  // G1 (Nielsen #1 "visibility of system status"): this in-content provenance/freshness chip IS the
  // page's system-status region ("Live · Based on your … · updated …"). role=status + aria-live make
  // it a genuine live region so the rubric's G1 finds it on EVERY page that renders a source chip
  // (central fix — pages whose only status affordance was this chip were failing G1 as bare <p>s).
  var chipHtml = '<p class="wh-source-chip" role="status" aria-live="polite" '
    + 'style="font-size:.62rem;color:rgba(255,255,255,0.6);margin:0;padding:3px 0 0;line-height:1.35;">'
    + parts.join(' &middot; ')
    + '</p>';

  // Arc P · FUSION 5 (P1/P5): methodology clauses collapse behind ONE plain-language
  // <details> disclosure instead of extending the grey meta-caption wall inline, so the
  // visible chip stays a single glance-first line. Real <details> = tap-openable on mobile
  // (mobile-maestro: never a hover/title tooltip). escHtml every clause — preserves the
  // callers' xss-allow invariant. Collapsed height ~0 beyond the reserved chip slot (CLS-safe).
  if (method.length) {
    var mItems = '';
    for (var j = 0; j < method.length; j++) {
      if (method[j]) mItems += '<li>' + escHtml(String(method[j])) + '</li>';
    }
    if (mItems) {
      chipHtml += '<details class="wh-method">'
        + '<summary>' + escHtml(_tt('How this is computed', 'Paano ito kinalkula')) + '</summary>'
        + '<ul>' + mItems + '</ul>'
        + '</details>';
    }
  }
  return chipHtml;
}

// ─────────────────────────────────────────────
// whListSkeleton / whListError — ONE shared loading + error state (STREAMLINE E2)
// ─────────────────────────────────────────────
// Every dynamic list shows a shimmer skeleton WHILE fetching and an inline
// error+retry on failure — never a blank panel (the P14 IDB-blank class, where a
// list silently emptied and the user couldn't tell "loading" from "broken").
// Pair with the page's existing #empty-state (no-data) + the catch→showToast.
// Styles live in components.css (.wh-skeleton / .wh-list-error). Pass the list's
// container element; for the error, pass an onRetry fn to wire the Retry button.
function whListSkeleton(el, rows) {
  if (!el) return;
  rows = rows || 3;
  var html = '<div class="wh-skeleton" aria-busy="true" aria-live="polite">';
  for (var i = 0; i < rows; i++) html += '<div class="wh-skeleton-row"></div>';
  html += '</div>';
  el.innerHTML = html;
}

// ─────────────────────────────────────────────
// whCardSkeleton — canonical CARD-shaped loading state (FF1 sibling of whListSkeleton)
// ─────────────────────────────────────────────
// Lifted 2026-07-17 from the page-local showSkeletons() copies in marketplace.html
// (grid listing card) and marketplace-admin.html (thumb-left row card) — the §10
// promote-up-a-layer move: the same pattern hand-rolled on page 2 gets lifted, never
// copied a third time. Use for card GRIDS where whListSkeleton's row shape would lie
// about the incoming layout. Self-injects its CSS once (zero setup on any page;
// no components.css dependency), aria-busy/aria-live like its sibling.
//   whCardSkeleton(gridEl, 8)                    // 'grid': image-top listing card
//   whCardSkeleton(areaEl, 4, { variant: 'row' })// 'row': thumb-left card w/ action bar
// ─────────────────────────────────────────────
// .wh-help — canonical inline-help disclosure (FI1 sibling of .wh-disclose)
// ─────────────────────────────────────────────
// Promoted 2026-07-17 from 9 byte-identical <details class="wh-help" style="…"> inline
// copies (assistant, marketplaces, ph-intelligence, project-report, public-feed,
// report-sender, status) — the §10 lift: same pattern on page 2+ becomes ONE shared rule.
// Self-injects (utils.js is the 31/32 shared surface; components.css is only linked on 11).
(function whHelpCSS() {
  if (typeof document === 'undefined' || document.getElementById('wh-help-css')) return;
  var st = document.createElement('style');
  st.id = 'wh-help-css';
  st.textContent =
    '.wh-help{margin:0.5rem 0 1rem;font-size:0.75rem;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:0.1rem 0.8rem 0.45rem}' +
    '.wh-help>summary{cursor:pointer;font-weight:700;color:rgba(255,255,255,0.72);min-height:44px;display:inline-flex;align-items:center}' +
    '.wh-help>p{margin:0.25rem 0 0.2rem;color:rgba(255,255,255,0.72);line-height:1.5}';
  (document.head || document.documentElement).appendChild(st);
})();

function whCardSkeleton(el, count, opts) {
  if (!el) return;
  count = count || 4;
  var variant = (opts && opts.variant) === 'row' ? 'row' : 'grid';
  if (!document.getElementById('wh-cardskel-css')) {
    var st = document.createElement('style');
    st.id = 'wh-cardskel-css';
    st.textContent =
      '.wh-cardskel{display:contents}' +
      '.wh-cardskel .wh-cs{background:rgba(255,255,255,0.07);border-radius:6px;animation:whCsPulse 1.4s ease-in-out infinite}' +
      '.wh-cardskel-card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:var(--wh-radius,12px);overflow:hidden}' +
      '.wh-cardskel-row{display:flex;flex-direction:column;gap:10px;padding:14px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:var(--wh-radius,12px)}' +
      '@keyframes whCsPulse{0%,100%{opacity:.55}50%{opacity:1}}' +
      '@media (prefers-reduced-motion: reduce){.wh-cardskel .wh-cs{animation:none;opacity:.7}}';
    document.head.appendChild(st);
  }
  var card;
  if (variant === 'row') {
    card = '<div class="wh-cardskel-row">'
      + '<div style="display:flex;gap:12px;align-items:flex-start;">'
      + '<div class="wh-cs" style="width:72px;height:72px;border-radius:10px;flex-shrink:0;"></div>'
      + '<div style="flex:1;">'
      + '<div class="wh-cs" style="height:14px;width:65%;margin-bottom:8px;"></div>'
      + '<div class="wh-cs" style="height:11px;width:80%;margin-bottom:8px;"></div>'
      + '<div class="wh-cs" style="height:10px;width:40%;"></div>'
      + '</div></div>'
      + '<div style="display:flex;gap:8px;">'
      + '<div class="wh-cs" style="flex:1;height:34px;border-radius:8px;"></div>'
      + '<div class="wh-cs" style="flex:1;height:34px;border-radius:8px;"></div>'
      + '</div></div>';
  } else {
    card = '<div class="wh-cardskel-card">'
      + '<div class="wh-cs" style="height:160px;border-radius:0;"></div>'
      + '<div style="padding:0.875rem;">'
      + '<div class="wh-cs" style="height:13px;width:80%;margin-bottom:8px;"></div>'
      + '<div class="wh-cs" style="height:11px;width:50%;margin-bottom:12px;"></div>'
      + '<div style="display:flex;justify-content:space-between;">'
      + '<div class="wh-cs" style="height:22px;width:55px;border-radius:999px;"></div>'
      + '<div class="wh-cs" style="height:26px;width:55px;border-radius:8px;"></div>'
      + '</div></div></div>';
  }
  var html = '<div class="wh-cardskel" aria-busy="true" aria-live="polite">';
  for (var i = 0; i < count; i++) html += card;
  html += '</div>';
  el.innerHTML = html;
}

// ─────────────────────────────────────────────────────────────────────────────
// whFreshnessChip — the SYSTEM-STATUS component (rubric G1), extracted 2026-07-15
// ─────────────────────────────────────────────────────────────────────────────
// Rubric G1 (visibility of system status) failed on 28/32 family pages, and the ruler
// was over-reporting it: `[class*="status"]` matched `.status-badge` (an ASSET's status,
// i.e. DATA), so pages "passed" for rendering "Overdue". Real G1 = telling the user how
// FRESH what they're looking at is — analytics' "Updated 6 min ago" bar was the only
// genuine instance. This EXTRACTS that pattern so any page adopts it in one call, instead
// of the family re-inventing 28 freshness bars (the §10 component-adoption thesis, applied).
//
//   whFreshnessChip('#my-anchor', tsMillis)   // or pass the element
//
// role="status" + aria-live="polite" make it announce to a screen reader WITHOUT stealing
// focus; the dot goes amber past an hour (stale). i18n via the shared _t. Self-contained —
// no page CSS needed. Call again on each refresh to re-stamp the time.
function whFreshnessChip(target, tsMillis, opts) {
  opts = opts || {};
  var el = (typeof target === 'string') ? document.querySelector(target) : target;
  if (!el) return;
  var _tt = (typeof window._t === 'function') ? window._t : function (en) { return en; };
  if (!tsMillis) { el.textContent = ''; el.removeAttribute('role'); return; }
  // ★THE CHIP MUST TICK OR IT LIES. A page that fetches once at open and never re-stamps
  // would show "Updated just now" forever — false after an hour. Each stamped element
  // remembers its timestamp and ONE shared 60s interval re-renders all of them, so the
  // text ("6 min ago") and the stale dot stay TRUE without any page writing a loop.
  // Pages with a real refresh cycle (alert-hub's 60s loadAll) simply re-stamp: the new
  // timestamp overwrites the old and the tick keeps counting from there.
  el.__whFreshTs = tsMillis;
  el.__whFreshOpts = { suffix: opts.suffix };
  if (!window.__whFreshTick) {
    window.__whFreshTick = setInterval(function () {
      var chips = document.querySelectorAll('[role="status"]');
      for (var i = 0; i < chips.length; i++) {
        if (chips[i].__whFreshTs) whFreshnessChip(chips[i], chips[i].__whFreshTs, chips[i].__whFreshOpts);
      }
    }, 60000);
  }
  // getTime() is used instead of Date.now() so the caller controls "now" (testable, and
  // the workflow-script Date.now() ban never bites a page — pages may use it freely, but
  // keeping the arithmetic caller-supplied makes this unit-testable).
  var nowMs = (typeof opts.nowMs === 'number') ? opts.nowMs : new Date().getTime();
  var mins = Math.round((nowMs - tsMillis) / 60000);
  var when = mins < 1 ? _tt('just now', 'ngayon lang')
    : mins < 60 ? _tt(mins + ' min ago', mins + ' min ang nakalipas')
    : _tt(Math.round(mins / 60) + 'h ago', Math.round(mins / 60) + ' oras ang nakalipas');
  var stale = mins > 60;
  // opts.suffix lets a page keep its own trailing note (e.g. "· Auto-refresh every minute")
  // while still routing freshness through this component for role=status + i18n + the dot.
  // escHtml it — a page might pass user-influenced text — reusing the shared escaper.
  var esc = (typeof window.escHtml === 'function') ? window.escHtml : function (x) { return x; };
  var suffix = opts.suffix ? ' <span class="wh-fresh-suffix">' + esc(opts.suffix) + '</span>' : '';
  el.setAttribute('role', 'status');
  el.setAttribute('aria-live', 'polite');
  el.innerHTML =
    '<span class="wh-fresh-dot" aria-hidden="true" style="width:8px;height:8px;border-radius:50%;'
    + 'display:inline-block;margin-right:6px;background:' + (stale ? 'var(--wh-orange)' : '#4ade80') + ';"></span>'
    + '<span class="wh-fresh-txt" style="font-size:0.72rem;color:rgba(255,255,255,0.6);">'
    + _tt('Updated', 'Na-update') + ' ' + when + suffix + '</span>';
}
if (typeof window !== 'undefined') window.whFreshnessChip = whFreshnessChip;

// whFreshnessFooter — the ONE-LINE adoption path for the family (roadmap F3).
// Creates (once) a right-aligned footer meta line at the end of .page and stamps it via
// whFreshnessChip. A page adopts G1 by calling this at the END of its real data-load —
// never at DOMContentLoaded, which would claim "Updated just now" even when the fetch
// FAILED (a lying chip is worse than no chip; same honesty bar as the tick).
// Re-calling on a refresh cycle re-stamps. Uniform placement = family resemblance (class R).
function whFreshnessFooter(opts) {
  var host = document.querySelector('.page') || document.querySelector('main') || document.body;
  if (!host) return;
  var el = document.getElementById('wh-fresh-footer');
  if (!el) {
    el = document.createElement('div');
    el.id = 'wh-fresh-footer';
    el.style.cssText = 'font-size:.62rem;text-align:right;margin-top:16px;';
    host.appendChild(el);
  }
  whFreshnessChip(el, new Date().getTime(), opts || {});
}
if (typeof window !== 'undefined') window.whFreshnessFooter = whFreshnessFooter;

// whCapRows — progressive disclosure for long tables (rubric A3, FAMILY roadmap F3).
// A3 failed on 31/32 pages for the same reason: every long table renders ALL rows at
// once (Miller/Hick: the reader pays for every row whether they need it or not). This
// caps a table at `max` rows behind a "Show all N" toggle — the analytics show-all
// pattern extracted as a shared organism. HONESTY BAR: call it only on tables whose
// rows are REAL overflow (the component no-ops under max+3 rows so a 9-row table isn't
// hidden behind a pointless click — a disclosure with nothing to disclose is decoration).
// aria-expanded mirrors state (same WCAG 4.1.2 rule as the analytics toggles).
function whCapRows(tableEl, max) {
  if (!tableEl) return;
  max = max || 8;
  var rows = tableEl.querySelectorAll('tbody tr');
  if (rows.length <= max + 2) return;             // not real overflow — no-op
  if (tableEl.__whCapped) return;                 // idempotent across re-renders
  tableEl.__whCapped = true;
  var _tt = (typeof window._t === 'function') ? window._t : function (en) { return en; };
  for (var i = max; i < rows.length; i++) rows[i].hidden = true;
  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'showall-toggle';
  btn.setAttribute('aria-expanded', 'false');
  btn.style.cssText = 'display:block;width:100%;margin-top:8px;min-height:44px;background:rgba(255,255,255,0.04);'
    + 'border:1px solid rgba(255,255,255,0.1);border-radius:var(--wh-radius-sm);color:rgba(255,255,255,0.7);'
    + 'font-family:inherit;font-size:0.75rem;font-weight:600;cursor:pointer;';
  var more = rows.length - max;
  var labelAll  = _tt('Show all ' + rows.length + ' ↓', 'Ipakita lahat ng ' + rows.length + ' ↓');
  var labelLess = _tt('Show less ↑', 'Ipakita ang mas kaunti ↑');
  btn.textContent = labelAll;
  btn.addEventListener('click', function () {
    var open = btn.getAttribute('aria-expanded') === 'true';
    for (var i = max; i < rows.length; i++) rows[i].hidden = open;
    btn.setAttribute('aria-expanded', open ? 'false' : 'true');
    btn.textContent = open ? labelAll : labelLess;
  });
  tableEl.insertAdjacentElement('afterend', btn);
}
if (typeof window !== 'undefined') window.whCapRows = whCapRows;

// AUTO-STAMP on successful data reads (G1 at family scale). Per-page call-site
// archaeology proved unreliable — pages boot through heterogeneous paths (an IIFE, a
// DOMContentLoaded handler, a tab switch, a restore flow), and stamping the wrong one
// means the chip never renders (measured: 5 of 19 first-pass adoptions missed the real
// boot path). Every page's data DOES flow through fetch() to the Supabase REST API, so
// ONE wrapper stamps on any SUCCESSFUL data response:
//   - fires only on response.ok  -> a failed fetch never claims "Updated" (the honesty bar);
//   - debounced 800ms            -> a burst of parallel reads stamps once;
//   - "last successful read" IS the freshness fact the chip reports — true by construction.
// Explicit per-page whFreshnessFooter() calls still work and simply re-stamp the same el.
(function whFreshnessAutoStamp() {
  if (typeof window === 'undefined' || !window.fetch || window.__whFreshHooked) return;
  window.__whFreshHooked = true;
  var origFetch = window.fetch;
  var t = null;
  window.fetch = function () {
    var p = origFetch.apply(this, arguments);
    try {
      var url = String(arguments[0] && arguments[0].url || arguments[0] || '');
      if (/\/rest\/v1\/|\/functions\/v1\/|supabase/.test(url)) {
        p.then(function (res) {
          if (res && res.ok) {
            clearTimeout(t);
            t = setTimeout(function () {
              try { whFreshnessFooter(); } catch (_) { /* empty-catch-allow: stamp is best-effort chrome */ }
            }, 800);
          }
        }).catch(function () { /* empty-catch-allow: observer only — never affect the caller's promise */ });
      }
    } catch (_) { /* empty-catch-allow: URL parse is best-effort */ }
    return p;
  };
})();
function whListError(el, message, onRetry) {
  if (!el) return;
  var e = escHtml;
  el.innerHTML =
    '<div class="wh-list-error" role="alert">'
    + '<div class="wh-list-error-icon" aria-hidden="true">⚠️</div>'
    + '<div>' + e(message || "Couldn’t load this. Check your connection and try again.") + '</div>'
    + (onRetry ? '<button type="button" class="wh-list-retry">Retry</button>' : '')
    + '</div>';
  if (onRetry) {
    var btn = el.querySelector('.wh-list-retry');
    if (btn) btn.addEventListener('click', onRetry);
  }
}
// Self-contained styles (STREAMLINE E2 rollout): inject the .wh-skeleton /
// .wh-list-error CSS once so whListSkeleton()/whListError() render correctly on
// ANY page that loads utils.js — not just the 11 that <link> components.css.
// The rules are theme-agnostic (white-alpha on the dark app surface, no page
// design tokens), so they're safe to inject globally. Idempotent (id-guarded);
// the components.css pages just get an identical, harmless duplicate rule set.
if (typeof document !== 'undefined' && !document.getElementById('wh-list-states-css')) {
  var whListStatesCss = document.createElement('style');
  whListStatesCss.id = 'wh-list-states-css';
  whListStatesCss.textContent =
    '.wh-skeleton{display:flex;flex-direction:column;gap:8px;padding:4px 0}' +
    '.wh-skeleton-row{height:44px;border-radius:10px;background:linear-gradient(100deg,rgba(255,255,255,0.04) 30%,rgba(255,255,255,0.09) 50%,rgba(255,255,255,0.04) 70%);background-size:200% 100%;animation:wh-shimmer 1.3s ease-in-out infinite}' +
    '@keyframes wh-shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}' +
    '@media (prefers-reduced-motion:reduce){.wh-skeleton-row{animation:none}}' +
    /* D1 U2: shared brief row-links (risk/pm-due/parts) were 39px tall (padding:8px) — bump to a 44px gloved-field tap target everywhere these render */
    '.wh-risk-row,.wh-pmdue-row,.wh-parts-row{min-height:44px;box-sizing:border-box}' +
    '.wh-list-error{text-align:center;padding:1.4rem 1rem;font-size:0.82rem;color:rgba(255,255,255,0.72);line-height:1.5}' +
    '.wh-list-error .wh-list-error-icon{font-size:1.4rem}' +
    '.wh-list-error button{margin-top:0.6rem;min-height:44px;padding:0 16px;border-radius:8px;border:1px solid rgba(255,255,255,0.18);background:transparent;color:#F4F6FA;font-family:inherit;font-size:0.78rem;font-weight:600;cursor:pointer}' +
    '.wh-list-error button:hover{border-color:rgba(255,255,255,0.32)}';
  (document.head || document.documentElement).appendChild(whListStatesCss);
}

// Arc P · FUSION 5: the .wh-method disclosure emitted by renderSourceChip() (methodology
// collapsed under a "How this is computed" toggle). Injected here so it reaches EVERY page
// that loads utils.js — components.css is <link>-ed on only ~12 pages, so a CSS-file-only
// rule would miss the Tailwind pages (pm-scheduler/inventory/skillmatrix). ONE source of truth.
if (typeof document !== 'undefined' && !document.getElementById('wh-method-css')) {
  var whMethodCss = document.createElement('style');
  whMethodCss.id = 'wh-method-css';
  whMethodCss.textContent =
    '.wh-method{margin:2px 0 0;font-size:.62rem;line-height:1.4}' +
    // 44px-tall tap zone (mobile-maestro floor) but visually a single small caption line;
    // marker hidden, replaced by an ⓘ so it reads as an info toggle, not a code affordance.
    '.wh-method>summary{display:flex;align-items:center;gap:5px;min-height:44px;cursor:pointer;list-style:none;color:rgba(255,255,255,0.6);font-weight:600;user-select:none}' +
    '.wh-method>summary::-webkit-details-marker{display:none}' +
    '.wh-method>summary::before{content:"\\24D8";font-weight:400;opacity:.75}' +
    '.wh-method>summary:hover,.wh-method[open]>summary{color:rgba(255,255,255,0.85)}' +
    '.wh-method>ul{margin:0 0 6px;padding:0 0 0 18px;color:rgba(255,255,255,0.55);line-height:1.5}' +
    '.wh-method>ul>li{margin:1px 0}';
  (document.head || document.documentElement).appendChild(whMethodCss);
}

// STREAMLINE E4: the brand palette is NOT injected from JS — it lives in
// tokens.css, which every page <link>s in <head> (directly, or via components.css
// which @imports it). A static render-blocking <link> can't FOUC the way a late
// JS injection would on a body-loaded utils.js, and it keeps ONE source of truth.

// ─────────────────────────────────────────────
// whFmt* — shared number / date / unit / ₱ formatters (STREAMLINE E6)
// ─────────────────────────────────────────────
// ONE Philippine-locale source of truth so currency (₱), dates (Asia/Manila),
// numbers, and hrs/days units render IDENTICALLY everywhere instead of per-page
// ad-hoc `'₱' + n` / bespoke toLocaleDateString. All null/NaN-safe (never print
// "₱NaN" / "Invalid Date" on the glass). Guarded by validate_user_facing_jargon
// sibling lint + the E6 formatter skill rule.
function whFmtPeso(n, opts) {
  var v = Number(n);
  if (!isFinite(v)) return '₱0';
  opts = opts || {};
  var dp = (opts.decimals != null) ? opts.decimals : (v % 1 === 0 ? 0 : 2);
  return '₱' + v.toLocaleString('en-PH', { minimumFractionDigits: dp, maximumFractionDigits: dp });
}
function whFmtNum(n, dp) {
  var v = Number(n);
  if (!isFinite(v)) return '0';
  return v.toLocaleString('en-PH', (dp != null) ? { minimumFractionDigits: dp, maximumFractionDigits: dp } : undefined);
}
function whFmtDate(d, opts) {
  var dt = (d instanceof Date) ? d : new Date(d);
  if (isNaN(dt.getTime())) return '-';
  opts = opts || {};
  var fmt = { year: 'numeric', month: opts.long ? 'long' : 'short', day: 'numeric', timeZone: 'Asia/Manila' };
  if (opts.year === false) delete fmt.year; // compact variant: same-week/shift contexts where the year is noise
  if (opts.weekday) fmt.weekday = opts.weekday; // 'short' | 'long'
  if (opts.time) { fmt.hour = '2-digit'; fmt.minute = '2-digit'; }
  if (opts.timeOnly) fmt = { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Manila' }; // clock-only variant
  if (opts.hour12 != null) fmt.hour12 = opts.hour12;
  return dt.toLocaleString('en-PH', fmt);
}
function whFmtDuration(value, unit) {
  var v = Number(value);
  if (!isFinite(v)) return '-';
  unit = unit || 'days';
  var singular = (Math.abs(v) === 1) ? unit.replace(/s$/, '') : unit;
  return whFmtNum(v) + ' ' + singular;
}
// whFmtAgo — canonical relative time ("just now" / Nm / Nh / Nd ago). Lifted 2026-07-17
// from 8 byte-equivalent page-local copies (hive/marketplace×4/audit-log/achievements/
// agentic-rag/alert-hub/asset-hub timeAgo·whenAgo·fmtRelative) — FULLSTACK_COMPONENT_LIBRARY
// FD1e. Page locals now DELEGATE here; keep their names, one source of truth for the math.
function whFmtAgo(d) {
  var dt = (d instanceof Date) ? d : new Date(d);
  if (!d || isNaN(dt.getTime())) return '';
  var s = (Date.now() - dt.getTime()) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return Math.floor(s / 60) + 'm ago';
  if (s < 86400) return Math.floor(s / 3600) + 'h ago';
  return Math.floor(s / 86400) + 'd ago';
}
if (typeof window !== 'undefined') {
  window.whFmtPeso = whFmtPeso; window.whFmtNum = whFmtNum;
  window.whFmtDate = whFmtDate; window.whFmtDuration = whFmtDuration;
  window.whFmtAgo = whFmtAgo;
}

// ─────────────────────────────────────────────
// renderRiskStrip — ONE shared "top at-risk assets" strip (STREAMLINE F2)
// ─────────────────────────────────────────────
// One renderer for the top-N at-risk asset list, reused by index (operational
// heartbeat), shift-brain (shift risk card), and alert-hub so the same asset-risk
// list cannot drift in look, ordering, or deep-link target across pages. Canonical
// home is asset-hub (the per-asset 360); every row deep-links back there.
//   rows : v_risk_truth rows, ALREADY band-filtered (high/critical) + ordered by
//          risk_score desc by the caller (registry top_risk_band rule stays at the
//          query). Each row needs asset_name, risk_score, risk_level, mtbf_days.
//   opts : { limit=3, title=null, ragTile='shared:risk_strip' }
//          - title set  -> returns a titled .oh-card with an "All assets →" link
//          - title unset -> returns the bare rows (for embedding in an existing card)
// Returns an HTML string (caller assigns to el.innerHTML), like renderSourceChip.
// Severity badge for the shared strips. The class alone was emitted for months with
// NO stylesheet anywhere defining it, so the chips inherited the parent <a>'s UA
// link-blue (rgb(0,0,238) — 1.24:1 on the card). Styles live inline like the rest
// of these renderers; text colors are the -300 tints that clear WCAG AA on dark.
function whOhBadge(lvl, text) {
  var c = {
    critical: ['rgba(252,165,165,0.16)', '#FECACA'],
    high:     ['rgba(253,186,116,0.16)', '#FDBA74'],
    medium:   ['rgba(253,224,71,0.14)',  '#FDE047'],
    low:      ['rgba(134,239,172,0.14)', '#86EFAC'],
  }[String(lvl || '').toLowerCase()] || ['rgba(255,255,255,0.08)', 'rgba(255,255,255,0.75)'];
  return '<span class="oh-badge oh-badge-' + escHtml(String(lvl || '')) + '" style="font-size:.58rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em;padding:.15rem .45rem;border-radius:999px;background:' + c[0] + ';color:' + c[1] + ';white-space:nowrap;">' + escHtml(String(text == null ? lvl : text)) + '</span>';
}

function renderRiskStrip(rows, opts) {
  opts = opts || {};
  var e = escHtml;
  // N1 i18n: safe translator — uses the host page's window._t when present (home/hive have the
  // EN/FIL toggle), else a pass-through so the ~18 pages without i18n never break. risk_level
  // badges + MTBF stay as standard technical terms (acceptable in EN, like the plain-language gate).
  var _tt = (typeof window !== 'undefined' && typeof window._t === 'function') ? window._t : function (en) { return en; };
  var limit = opts.limit || 3;
  var list = (rows || []).slice(0, limit);
  if (!list.length) return '';
  var rowsHtml = list.map(function (r) {
    var pct  = Math.round((Number(r.risk_score) || 0) * 100);
    var mtbf = (r.mtbf_days != null) ? ('MTBF ' + Math.round(r.mtbf_days) + 'd') : '';
    var href = 'asset-hub.html?tag=' + encodeURIComponent(r.asset_name || '');
    var lvl  = String(r.risk_level || '').toLowerCase();
    return '<a href="' + e(href) + '" class="wh-risk-row" style="display:flex;align-items:center;justify-content:space-between;gap:10px;text-decoration:none;padding:8px 10px;background:rgba(255,255,255,0.03);border-radius:8px;">'
      +   '<div style="display:flex;align-items:center;gap:8px;min-width:0;flex:1;">'
      +     whOhBadge(lvl, r.risk_level)
      +     '<span style="font-size:.78rem;font-weight:600;color:#F4F6FA;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + e(r.asset_name) + '</span>'
      +   '</div>'
      +   '<div style="display:flex;align-items:center;gap:10px;flex-shrink:0;">'
      +     '<span style="font-size:.65rem;color:rgba(255,255,255,.6);white-space:nowrap;">' + e(mtbf) + '</span>'
      +     '<span style="font-size:.72rem;font-weight:800;color:var(--wh-red-text,#FCA5A5);">' + pct + '%</span>'
      +   '</div>'
      + '</a>';
  }).join('');
  var inner = '<div style="display:flex;flex-direction:column;gap:8px;">' + rowsHtml + '</div>';
  if (!opts.title) return inner;
  return '<div class="oh-card" data-rag-tile="' + e(opts.ragTile || 'shared:risk_strip') + '" data-rag-label="' + e(opts.title) + '" style="padding:14px 16px;border-left:3px solid #f87171;">'
    +   '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
    +     '<p style="font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--wh-red-text,#FCA5A5);margin:0;">' + e(opts.title) + '</p>'
    +     '<a href="asset-hub.html" style="font-size:.62rem;color:rgba(255,255,255,.6);text-decoration:none;display:inline-flex;align-items:center;min-height:44px;">' + e(_tt('All assets', 'Lahat ng asset')) + ' &#8594;</a>'
    +   '</div>' + inner + '</div>';
}
if (typeof window !== 'undefined') window.renderRiskStrip = renderRiskStrip;

// ─────────────────────────────────────────────
// renderPmDueStrip — ONE shared PM overdue/due-soon strip (STREAMLINE F4)
// ─────────────────────────────────────────────
// One renderer for a frequency-aware PM list, reused by shift-brain (this-shift
// slice) and any page that lists PM scope items, so the overdue/due-soon rows
// share look + scope labelling and can't drift. After S1 the NUMBERS are already
// canonical (v_pm_scope_items_truth.is_overdue/is_due_soon); this makes the
// PRESENTATION single-source too. Owner page = pm-scheduler; every row deep-links there.
//   rows : v_pm_scope_items_truth-shaped rows; needs asset_name (or tag_id),
//          is_overdue, days_until_due; optional criticality, item_text.
//   opts : { limit=10, title=null, scope=null ('this shift'|'hive'|'yours'),
//            ragTile='shared:pm_due_strip' }
// Returns an HTML string (caller assigns to el.innerHTML).
function renderPmDueStrip(rows, opts) {
  opts = opts || {};
  var e = escHtml;
  var limit = opts.limit || 10;
  var list = (rows || []).slice(0, limit);
  if (!list.length) return '';
  var rowsHtml = list.map(function (r) {
    var name = r.asset_name || r.tag_id || r.asset_tag || 'asset';
    var over = (r.is_overdue === true);
    var d = (r.days_until_due != null) ? Math.abs(Math.round(Number(r.days_until_due))) : null;
    var status, badge;
    if (over) { badge = 'critical'; status = (d != null) ? ('Overdue by ' + d + 'd') : 'Overdue'; }
    else      { badge = 'high';     status = (d != null) ? ('Due in ' + d + 'd')     : 'Due soon'; }
    var crit = r.criticality || r.asset_criticality || '';
    // Arc X A1: deep-link to the NAMED PM asset (pm-scheduler.html reads ?asset= ->
    // opens that asset's PM detail + schedule action), so the strip hands off the
    // record instead of dumping the user on the full overdue list (Issue #2).
    var href = 'pm-scheduler.html?asset=' + encodeURIComponent(name);
    return '<a href="' + e(href) + '" class="wh-pmdue-row" style="display:flex;align-items:center;justify-content:space-between;gap:10px;text-decoration:none;padding:8px 10px;background:rgba(255,255,255,0.03);border-radius:8px;">'
      +   '<div style="display:flex;align-items:center;gap:8px;min-width:0;flex:1;">'
      +     whOhBadge(badge, over ? 'OVERDUE' : 'DUE')
      +     '<span style="font-size:.78rem;font-weight:600;color:#F4F6FA;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + e(name) + '</span>'
      +   '</div>'
      +   '<div style="display:flex;align-items:center;gap:10px;flex-shrink:0;">'
      +     (crit ? '<span style="font-size:.62rem;color:rgba(255,255,255,.6);white-space:nowrap;">' + e(crit) + '</span>' : '')
      +     '<span style="font-size:.68rem;font-weight:700;color:' + (over ? '#FCA5A5' : '#FDB94A') + ';white-space:nowrap;">' + e(status) + '</span>'
      +   '</div>'
      + '</a>';
  }).join('');
  var scopeChip = opts.scope
    ? '<span style="font-size:.55rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:rgba(255,255,255,.45);">' + e(opts.scope) + '</span>'
    : '';
  var inner = '<div style="display:flex;flex-direction:column;gap:8px;">' + rowsHtml + '</div>';
  if (!opts.title) return inner;
  return '<div class="oh-card" data-rag-tile="' + e(opts.ragTile || 'shared:pm_due_strip') + '" data-rag-label="' + e(opts.title) + '" style="padding:14px 16px;border-left:3px solid #29B6D9;">'
    +   '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
    +     '<p style="font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#29B6D9;margin:0;">' + e(opts.title) + '</p>'
    +     (scopeChip || '<a href="pm-scheduler.html" style="font-size:.62rem;color:rgba(255,255,255,.6);text-decoration:none;display:inline-flex;align-items:center;min-height:44px;">PM Scheduler &#8594;</a>')
    +   '</div>' + inner + '</div>';
}
if (typeof window !== 'undefined') window.renderPmDueStrip = renderPmDueStrip;

// ─────────────────────────────────────────────
// whStockSeverity — ONE canonical stock-state classifier (ASSET_ALERT_SHIFT reuse discipline)
// ─────────────────────────────────────────────
// Single source of truth for "how at-risk is this inventory row", reading the CANONICAL
// v_inventory_items_truth flags (is_out_of_stock / is_critical_low / is_low_stock) that
// migration 20260510000003 built expressly "so the same threshold logic does not get
// reimplemented across 10+ pages". Falls back to qty/reorder arithmetic only when the flags
// are absent (a non-canonical row). renderPartsStrip AND alert-hub's stock composer both call
// this so the low-stock band can never drift between the shift-brain strip and the alert inbox.
//   row : inventory-shaped; reads is_out_of_stock/is_critical_low/is_low_stock, qty_on_hand,
//         reorder_point (or min_qty as fallback).
//   returns { state:'out'|'critical_low'|'low'|'ok', severity:'critical'|'high'|'medium'|null,
//             label:'OUT'|'LOW'|null, atRisk:bool }
function whStockSeverity(row) {
  row = row || {};
  var qty = Number(row.qty_on_hand);
  var rpRaw = (row.reorder_point != null) ? row.reorder_point : row.min_qty;
  var rp = Number(rpRaw);
  var hasRp = !isNaN(rp) && rp > 0;
  var out  = (row.is_out_of_stock === true) || (!isNaN(qty) && qty <= 0);
  var crit = (row.is_critical_low === true) || (hasRp && !isNaN(qty) && qty <= rp / 2);
  var low  = (row.is_low_stock === true) || (hasRp && !isNaN(qty) && qty <= rp);
  if (out)  return { state: 'out',          severity: 'critical', label: 'OUT', atRisk: true };
  if (crit) return { state: 'critical_low', severity: 'high',     label: 'LOW', atRisk: true };
  if (low)  return { state: 'low',          severity: 'medium',   label: 'LOW', atRisk: true };
  return { state: 'ok', severity: null, label: null, atRisk: false };
}
if (typeof window !== 'undefined') window.whStockSeverity = whStockSeverity;

// renderPartsStrip — ONE shared parts-action list (STREAMLINE F3)
// ─────────────────────────────────────────────
// One renderer for an urgency-ranked parts list (out-of-stock first, then low /
// reorder), reused by shift-brain (parts pre-stage) and any page that lists
// at-risk parts, so the parts list shares look + ranking and can't drift. Owner
// page = inventory (the ledger + canonical is_low_stock/is_out_of_stock); every
// row deep-links there. (Count chips on index/hive already read the same flags.)
//   rows : inventory-shaped rows; needs part_name, qty_on_hand, min_qty; optional
//          is_out_of_stock / is_low_stock.
//   opts : { limit=10, title=null, ragTile='shared:parts_strip' }
function renderPartsStrip(rows, opts) {
  opts = opts || {};
  var e = escHtml;
  var limit = opts.limit || 10;
  var list = (rows || []).slice();
  // urgency rank: out-of-stock (qty<=0) before merely-low
  list.sort(function (a, b) {
    var ao = ((a.is_out_of_stock === true) || Number(a.qty_on_hand) <= 0) ? 0 : 1;
    var bo = ((b.is_out_of_stock === true) || Number(b.qty_on_hand) <= 0) ? 0 : 1;
    return ao - bo;
  });
  list = list.slice(0, limit);
  if (!list.length) return '';
  var rowsHtml = list.map(function (r) {
    var qty = Number(r.qty_on_hand) || 0, mn = Number(r.min_qty) || 0;
    // Canonical-reuse: classify through the shared whStockSeverity (same source alert-hub uses),
    // so the parts band can't diverge between this strip and the alert inbox.
    var st = whStockSeverity(r);
    var out = st.state === 'out';
    var badge = out ? 'critical' : 'high';
    var label = st.label || (out ? 'OUT' : 'LOW');
    var name = r.part_name || 'part';
    var meta = 'on hand ' + qty + ' / min ' + mn;
    // Arc X A1: deep-link to the NAMED part (inventory.html reads ?q= -> filters +
    // scrolls to it), so the strip hands off the record instead of a bare list.
    var href = 'inventory.html?q=' + encodeURIComponent(r.part_name || '');
    return '<a href="' + e(href) + '" class="wh-parts-row" style="display:flex;align-items:center;justify-content:space-between;gap:10px;text-decoration:none;padding:8px 10px;background:rgba(255,255,255,0.03);border-radius:8px;">'
      +   '<div style="display:flex;align-items:center;gap:8px;min-width:0;flex:1;">'
      +     whOhBadge(badge, label)
      +     '<span style="font-size:.78rem;font-weight:600;color:#F4F6FA;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + e(name) + '</span>'
      +   '</div>'
      +   '<span style="font-size:.62rem;color:rgba(255,255,255,.6);white-space:nowrap;flex-shrink:0;">' + e(meta) + '</span>'
      + '</a>';
  }).join('');
  var inner = '<div style="display:flex;flex-direction:column;gap:8px;">' + rowsHtml + '</div>';
  if (!opts.title) return inner;
  return '<div class="oh-card" data-rag-tile="' + e(opts.ragTile || 'shared:parts_strip') + '" data-rag-label="' + e(opts.title) + '" style="padding:14px 16px;border-left:3px solid #fb923c;">'
    +   '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
    +     '<p style="font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#fb923c;margin:0;">' + e(opts.title) + '</p>'
    +     '<a href="inventory.html" style="font-size:.62rem;color:rgba(255,255,255,.6);text-decoration:none;display:inline-flex;align-items:center;min-height:44px;">Inventory &#8594;</a>'
    +   '</div>' + inner + '</div>';
}
if (typeof window !== 'undefined') window.renderPartsStrip = renderPartsStrip;

// ─────────────────────────────────────────────
// renderActionBrief — ONE shared Action Brief renderer (STREAMLINE S6 / F1)
// ─────────────────────────────────────────────
// One renderer for the unified Action Brief produced by the analytics prescriptive
// engine (phase=prescriptive + horizon). Replaces the 3 bespoke brief renderers
// (alert-hub AMC card, shift-brain briefing, analytics action plan) so all three
// surfaces render time-scoped SLICES of the SAME brief in the SAME shape.
//   brief : the action_plan object { summary, this_week[], watch_list[], narration }
//           (analytics_action_plan_v1). Items may be strings or {action,why,...} objects.
//   opts  : { title='Action Brief', horizon=null, ragTile='shared:action_brief' }
// Returns an HTML string.
function renderActionBrief(brief, opts) {
  opts = opts || {};
  var e = escHtml;
  if (!brief || typeof brief !== 'object') return '';
  var summary = brief.summary || brief.narration || '';
  var asLine = function (it) {
    if (it == null) return '';
    if (typeof it === 'string') return e(it);
    // object form — prefer action/why, fall back to a compact join of values
    var a = it.action || it.task || it.item || it.title || '';
    var why = it.why || it.reason || it.detail || '';
    if (a || why) return '<strong>' + e(a) + '</strong>' + (why ? ' &middot; ' + e(why) : '');
    return e(Object.values(it).filter(function (v) { return typeof v === 'string'; }).join(' · '));
  };
  var listBlock = function (label, arr, color) {
    arr = Array.isArray(arr) ? arr.filter(Boolean) : [];
    if (!arr.length) return '';
    return '<div style="margin-top:10px;">'
      + '<p style="font-size:.58rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:' + color + ';margin:0 0 4px;">' + e(label) + '</p>'
      + '<ul style="margin:0;padding-left:16px;display:flex;flex-direction:column;gap:4px;">'
      + arr.slice(0, 8).map(function (it) { return '<li style="font-size:.74rem;color:rgba(255,255,255,.82);line-height:1.35;">' + asLine(it) + '</li>'; }).join('')
      + '</ul></div>';
  };
  var hChip = opts.horizon
    ? '<span style="font-size:.55rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:rgba(255,255,255,.72);">' + e(opts.horizon) + '</span>'
    : '';
  return '<div class="oh-card" data-rag-tile="' + e(opts.ragTile || 'shared:action_brief') + '" data-rag-label="' + e(opts.title || 'Action Brief') + '" style="padding:14px 16px;border-left:3px solid #a78bfa;">'
    +   '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">'
    +     '<p style="font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#a78bfa;margin:0;">' + e(opts.title || 'Action Brief') + '</p>' + hChip
    +   '</div>'
    +   (summary ? '<p style="font-size:.82rem;font-weight:600;color:#F4F6FA;margin:0;line-height:1.4;">' + e(summary) + '</p>' : '')
    +   listBlock(opts.horizon === 'strategic' ? 'This quarter' : opts.horizon === 'shift' ? 'This shift' : opts.horizon === 'today' ? 'Today' : 'This week', brief.this_week, '#f87171')
    +   listBlock('Watch list', brief.watch_list, '#F7A21B')
    + '</div>';
}
if (typeof window !== 'undefined') window.renderActionBrief = renderActionBrief;

// ─────────────────────────────────────────────
// wireDetailToggle — ONE shared "Show details" explainer toggle (STREAMLINE S10)
// ─────────────────────────────────────────────
// Every dashboard page carries a "How this is computed" explainer: a
// <button id="details-toggle-btn"> that shows/hides a <div role="region"> whose
// id is named in the button's aria-controls. The PANEL CONTENT stays static per
// page (each explains its own KPIs) — validate_rag_flywheel_locks.py +
// survey_ia_redundancy.py + tag_all_rag_tiles.py read the
// data-rag-tile="<page>:detail_panel" marker from the STATIC html, so moving the
// panel into JS would break those gates. What WAS copy-pasted on all 14 pages is
// the toggle HANDLER (a ~10-line IIFE) — collapsed here into one idempotent fn.
// Each page calls this once (replacing its old bespoke IIFE), typically at the
// end of its load/render. Explicit-call (not auto-run): the button id
// `details-toggle-btn` lives on ~19 pages, so an auto-runner would double-bind
// any page that still holds its own handler mid-rollout. The __whDetailWired
// guard still makes a duplicate call a safe no-op.
//   - reads the controlled pane from the button's aria-controls (so one fn
//     serves every page's differently-id'd `#X-summary-details` pane)
//   - toggles `.open` (matches each page's `#X-summary-details.open{display:block}` css)
//   - mirrors state into aria-expanded + swaps the label Show/Hide details
function wireDetailToggle() {
  if (typeof document === 'undefined') return;
  var btn = document.getElementById('details-toggle-btn');
  if (!btn || btn.__whDetailWired) return;
  var paneId = btn.getAttribute('aria-controls');
  var pane = paneId ? document.getElementById(paneId) : null;
  if (!pane) return;
  btn.__whDetailWired = true;
  btn.addEventListener('click', function () {
    var open = pane.classList.toggle('open');
    btn.setAttribute('aria-expanded', String(open));
    btn.textContent = open ? 'Hide details' : 'Show details';
  });
}
if (typeof window !== 'undefined') window.wireDetailToggle = wireDetailToggle;

// ─────────────────────────────────────────────
// resolveAssetNodeId — writer-side legacy-to-canonical bridge (Phase 5b)
// ─────────────────────────────────────────────
// Phase 5b dropped logbook.asset_ref_id (text) in favour of
// logbook.asset_node_id (uuid). The asset picker in legacy writer surfaces
// (logbook.html; parts-tracker.html deleted 2026-06-10, Phase 4) still queries the `assets` table, which
// is keyed by text. This helper looks up the corresponding canonical
// asset_nodes.id (uuid) via the legacy_asset_id bridge column so the writer
// can store the uuid FK on the new logbook column.
//
// Returns null when:
//   - hiveId is missing (solo mode -- asset_nodes is hive-scoped)
//   - legacyAssetId is missing
//   - no asset_node exists for that legacy id in the hive (e.g. user
//     registered an asset but the node wasn't created yet)
//
// Skill alignment: architect (parallel-cutover pattern), data-engineer
// (narrow .maybeSingle lookup, hive-scoped match), KPI_ENGINE.md Phase 5b.
async function resolveAssetNodeId(db, hiveId, assetIdOrLegacy) {
  if (!db || !hiveId || !assetIdOrLegacy) return null;
  // The Phase 5c asset picker passes the canonical asset_nodes uuid (exposed by
  // the view as `asset_id`); older callers may still pass a legacy text id
  // (`legacy_asset_id`). Match on whichever the value looks like.
  // IMPORTANT: v_asset_truth renames asset_nodes.id -> asset_id, so select('id')
  // / eq('id') 400s ("column v_asset_truth.id does not exist"). Always asset_id.
  const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(assetIdOrLegacy));
  try {
    let q = db.from('v_asset_truth').select('asset_id').eq('hive_id', hiveId);
    q = isUuid ? q.eq('asset_id', assetIdOrLegacy) : q.eq('legacy_asset_id', assetIdOrLegacy);
    const { data } = await q.maybeSingle();
    return data?.asset_id || null;
  } catch (_) {
    return null;
  }
}

// Inverse helper: given a canonical asset_node_id (uuid), return the
// legacy_asset_id (text) that still keys older systems like project_links.
// Used at use-site rather than rewriting the data model of every dependent.
async function resolveLegacyAssetId(db, assetNodeId) {
  if (!db || !assetNodeId) return null;
  try {
    // v_asset_truth renames asset_nodes.id -> asset_id; filtering eq('id') 400s
    // ("column v_asset_truth.id does not exist"). The canonical uuid is asset_id.
    const { data } = await db.from('v_asset_truth')
      .select('legacy_asset_id')
      .eq('asset_id', assetNodeId)
      .maybeSingle();
    return data?.legacy_asset_id || null;
  } catch (_) {
    return null;
  }
}

// ─────────────────────────────────────────────
// ocUpdate — optimistic-concurrency update helper (PRODUCTION_FIXES #43)
// ─────────────────────────────────────────────
// Adds an `.eq('updated_at', oldStamp)` guard so a multi-writer race is
// detected at the SQL layer instead of silently overwriting. Returns
// { ok, row, conflict, error }:
//   - ok=true, row=updated row  -> write succeeded
//   - ok=false, conflict=true   -> updated_at didn't match (someone else won)
//   - ok=false, error=Error     -> network / permission failure
//
// Callers wrap their save flow:
//   const { data: cur } = await db.from(t).select('id, updated_at').eq('id', id).single();
//   const res = await ocUpdate(db, t, id, updates, cur.updated_at);
//   if (res.conflict) showToast('Someone else just updated this. Refresh and try again.');
//
// Tables must have `updated_at timestamptz NOT NULL` + a touch trigger
// (see logbook_updated_at migration for the canonical recipe).
//
// Skills consulted: architect (OC pattern), data-engineer (single-statement
// guard, .select() return for conflict detection).
async function ocUpdate(db, table, id, updates, oldStamp) {
  if (!db || !table || !id) {
    return { ok: false, error: new Error('ocUpdate: missing args') };
  }
  try {
    const { data, error } = await db.from(table)
      .update(updates)
      .eq('id', id)
      .eq('updated_at', oldStamp)
      .select('id, updated_at');
    if (error) return { ok: false, error };
    if (!data || data.length === 0) {
      return { ok: false, conflict: true };
    }
    return { ok: true, row: data[0] };
  } catch (e) {
    return { ok: false, error: e };
  }
}

// ─── KPI Tile (Tier G capability: display_kpi_tile) ────────────────────────
// Shared KPI card renderer. Single source of truth for the RAG-coloured
// tile pattern across analytics.html, hive.html, asset-hub.html, predictive.
// Replaces 4 parallel implementations during the Tier G consolidation pass.
//
// opts:
//   - title    (required) "MTBF — Mean Time Between Failures"
//   - standard            "ISO 14224:2016 §9.3"
//   - value    (required) the hero number (string or number)
//   - unit                "days" | "%" | "h" | ...
//   - sublabel            small line under the hero number
//   - color               'green'|'yellow'|'red'|'grey' — RAG state
//   - detail              HTML string for the expandable section (optional)
//   - legend              footer note shown inside expanded detail
//   - autoOpen            override default-open behavior (red auto-opens)
//   - tileId              optional caller-supplied id; else auto-generated
//
// capability: display_kpi_tile
let _whKpiTileId = 0;
function renderKpiTile(opts) {
  opts = opts || {};
  const COLORS = {
    green:  { bg: 'rgba(74,222,128,0.08)',   border: 'rgba(74,222,128,0.3)',   text: '#4ade80',  label: '✓ Healthy'  },
    yellow: { bg: 'rgba(247,162,27,0.08)',   border: 'rgba(247,162,27,0.3)',   text: '#F7A21B',  label: '⚠ Watch'    },
    red:    { bg: 'rgba(248,113,113,0.08)',  border: 'rgba(248,113,113,0.3)',  text: '#f87171',  label: '✗ Critical' },
    grey:   { bg: 'rgba(255,255,255,0.03)',  border: 'rgba(255,255,255,0.08)', text: 'rgba(255,255,255,0.6)', label: 'No data' },
  };
  const c   = COLORS[opts.color] || COLORS.grey;
  const id  = opts.tileId || `kpi-${_whKpiTileId++}`;
  const autoOpen = opts.autoOpen !== undefined ? opts.autoOpen : (opts.color === 'red');
  const detail = opts.detail || '';
  const legend = opts.legend || '';

  // The tile's title is the card's HEADING: without it a screen-reader user has no
  // way to navigate a page of KPI cards (and axe cannot catch this -- heading-order
  // has nothing to fail on when there are no headings at all). An <h2> may not live
  // INSIDE a <button> (phrasing content only), so the heading WRAPS the button --
  // the ARIA Authoring Practices accordion pattern. Margins zeroed = pixel-identical.
  return `<div class="card" style="border-left:3px solid ${c.border};margin-bottom:1rem;">
    <h2 style="margin:0;font:inherit;color:inherit;">
    <button class="kpi-toggle" onclick="if(window.toggleKPI)toggleKPI('${id}')" style="min-height:${detail ? '72px' : '0'};">
      <div style="flex:1;text-align:left;">
        <div style="font-size:0.68rem;font-weight:700;color:rgba(255,255,255,0.6);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.25rem;">
          ${escHtml(opts.title || '')} <span style="font-size:0.58rem;font-weight:500;">${escHtml(opts.standard || '')}</span>
        </div>
        <div style="display:flex;align-items:baseline;gap:0.4rem;margin-bottom:0.15rem;">
          <!-- 1.5rem == the canonical KPI tier (.sc-hero in components.css). This tile
               rendered 1.9rem, a THIRD size for the same concept, which inverted the
               hierarchy on analytics: the DETAIL card values (30px) shouted louder than
               the SUMMARY roll-up (24px) and the page h1 (22px) -- "biggest = most
               important" backwards, and 3 "big" sizes where the rule allows 2. A KPI
               number is ONE tier whether it sits in a summary tile or a result card;
               .simple-card.hero is the deliberate second tier for the ONE key metric. -->
          <span style="font-size:1.5rem;font-weight:800;line-height:1.15;color:${c.text};font-variant-numeric:tabular-nums;">${escHtml(String(opts.value === undefined ? '-' : opts.value))}</span>
          <span style="font-size:0.78rem;color:rgba(255,255,255,0.6);">${escHtml(opts.unit || '')}</span>
        </div>
        ${opts.sublabel ? `<div style="font-size:0.67rem;color:rgba(255,255,255,0.6);">${escHtml(opts.sublabel)}</div>` : ''}
      </div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:0.4rem;flex-shrink:0;margin-left:0.75rem;">
        <span style="font-size:0.63rem;font-weight:700;padding:0.2rem 0.55rem;border-radius:999px;background:${c.bg};border:1px solid ${c.border};color:${c.text};white-space:nowrap;">${c.label}</span>
        ${detail ? `<span class="kpi-chevron${autoOpen ? ' open' : ''}" id="${id}-chevron">▼</span>` : ''}
      </div>
    </button>
    </h2>
    ${detail ? `
      <div class="kpi-detail${autoOpen ? ' open' : ''}" id="${id}" style="border-top:1px solid rgba(255,255,255,0.06);">
        ${detail}
        ${legend ? `<p style="font-size:0.62rem;color:rgba(255,255,255,0.6);margin-top:0.5rem;">${escHtml(legend)}</p>` : ''}
      </div>` : ''}
  </div>`;
}

// Default toggle handler — pages that already define toggleKPI keep their own.
if (typeof window !== 'undefined' && !window.toggleKPI) {
  window.toggleKPI = function (id) {
    const detail  = document.getElementById(id);
    const chevron = document.getElementById(id + '-chevron');
    if (!detail) return;
    const isOpen = detail.classList.toggle('open');
    if (chevron) chevron.classList.toggle('open', isOpen);
  };
}


// ─── Compact Stat (Tier G capability: display_compact_stat) ────────────────
// Small inline label/value tile — the recurring "MTBF: 18d" pattern across
// asset-hub risk panel, hive benchmark rows, predictive count chips, shift
// brain top-of-shift stats. Distinct from renderKpiTile (which is the full
// RAG hero card); this is the compact variant for stat strips.
//
// opts:
//   - label    (required) "MTBF" | "Critical" | "Days to Failure"
//   - value    (required) hero number / text
//   - unit                "d" | "%" | "h" (optional, rendered small)
//   - color               'red'|'orange'|'yellow'|'green'|'blue'|'grey' OR a CSS color
//   - sublabel            small line under the value (optional)
//   - icon                emoji or single char prefix (optional)
//   - href                wrap whole tile in <a href> (optional)
//
// capability: display_compact_stat
function renderCompactStat(opts) {
  opts = opts || {};
  const PALETTE = {
    red:    '#f87171',
    orange: '#fb923c',
    yellow: '#facc15',
    green:  '#4ade80',
    blue:   '#60a5fa',
    grey:   'rgba(255,255,255,0.55)',
  };
  const color = PALETTE[opts.color] || opts.color || 'rgba(255,255,255,0.85)';

  const inner =
    `<div style="display:flex;flex-direction:column;align-items:flex-start;gap:0.15rem;padding:0.5rem 0.85rem;min-width:84px;">` +
      `<span style="font-size:0.6rem;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:rgba(255,255,255,0.6);">${escHtml(opts.label || '')}</span>` +
      `<span style="display:flex;align-items:baseline;gap:0.25rem;">` +
        (opts.icon ? `<span style="font-size:0.85rem;">${escHtml(opts.icon)}</span>` : '') +
        `<span style="font-size:1.05rem;font-weight:800;line-height:1;color:${color};">${escHtml(String(opts.value === undefined || opts.value === null ? '-' : opts.value))}</span>` +
        (opts.unit ? `<span style="font-size:0.7rem;color:rgba(255,255,255,0.45);">${escHtml(opts.unit)}</span>` : '') +
      `</span>` +
      (opts.sublabel ? `<span style="font-size:0.6rem;color:rgba(255,255,255,0.6);">${escHtml(opts.sublabel)}</span>` : '') +
    `</div>`;

  if (opts.href) {
    return `<a href="${escHtml(opts.href)}" style="text-decoration:none;color:inherit;">${inner}</a>`;
  }
  return inner;
}


// ─── Alert Preview (Tier G capability: display_alert_preview) ──────────────
// Shared alert-row renderer for cross-page previews of AMC briefings, failure
// signature matches, sensor anomalies, parts staging recommendations.
// Each preview links to alert-hub.html for the full filterable view.
//
// opts:
//   - kind:      'amc_briefing' | 'failure_signature' | 'sensor_anomaly' | 'parts_staging'
//   - title      e.g. "PMP-001 bearing failure pattern detected"
//   - severity   'critical' | 'high' | 'medium' | 'low'
//   - asset      asset_tag or machine name (optional)
//   - message    short body text (optional)
//   - created_at ISO timestamp (renders as relative time)
//   - href       link target (default: alert-hub.html)
//
// capability: display_alert_preview
function renderAlertPreview(opts) {
  opts = opts || {};
  const SEV = {
    critical: { bg: 'rgba(248,113,113,0.10)', border: '#f87171', label: '🔴 CRITICAL' },
    high:     { bg: 'rgba(247,162,27,0.10)',  border: '#F7A21B', label: '🟠 HIGH' },
    medium:   { bg: 'rgba(250,204,21,0.10)',  border: '#facc15', label: '🟡 MEDIUM' },
    low:      { bg: 'rgba(74,222,128,0.10)',  border: '#4ade80', label: '🟢 LOW' },
  };
  const s = SEV[opts.severity] || SEV.medium;
  const kindIcon = ({
    amc_briefing:      '☀️',
    failure_signature: '⚠',
    sensor_anomaly:    '📡',
    parts_staging:     '📦',
  })[opts.kind] || '🔔';

  let rel = '';
  if (opts.created_at) {
    try {
      const secs = (Date.now() - new Date(opts.created_at).getTime()) / 1000;
      if (secs < 60)        rel = 'just now';
      else if (secs < 3600) rel = `${Math.round(secs / 60)}m ago`;
      else if (secs < 86400) rel = `${Math.round(secs / 3600)}h ago`;
      else                  rel = `${Math.round(secs / 86400)}d ago`;
    } catch (_e) { rel = ''; }
  }

  const href = opts.href || 'alert-hub.html';
  return `<a href="${escHtml(href)}" class="alert-preview" style="display:block;padding:0.6rem 0.8rem;margin-bottom:0.4rem;background:${s.bg};border-left:3px solid ${s.border};border-radius:0.5rem;text-decoration:none;color:inherit;">
    <div style="display:flex;align-items:baseline;justify-content:space-between;gap:0.5rem;margin-bottom:0.15rem;">
      <span style="font-size:0.7rem;font-weight:700;letter-spacing:0.04em;">${kindIcon} ${escHtml(opts.title || 'Alert')}</span>
      <span style="font-size:0.6rem;color:rgba(255,255,255,0.6);white-space:nowrap;">${escHtml(s.label)}${rel ? ' · ' + escHtml(rel) : ''}</span>
    </div>
    ${opts.asset ? `<div style="font-size:0.62rem;color:rgba(255,255,255,0.5);">Asset: ${escHtml(opts.asset)}</div>` : ''}
    ${opts.message ? `<div style="font-size:0.65rem;color:rgba(255,255,255,0.55);margin-top:0.15rem;">${escHtml(opts.message)}</div>` : ''}
  </a>`;
}


// ─────────────────────────────────────────────
// fetchWithTimeout — bounded fetch wrapper (Phase 1.5 of STRATEGIC_ROADMAP)
// ─────────────────────────────────────────────
// Every cross-network call in WorkHive must have an upper bound. On a 2G/3G
// link in a Philippine plant, a missing timeout means a logbook entry,
// embed-entry POST, or assistant turn can hang for minutes while the user
// stares at a spinner and assumes the page is broken. AbortController gives us
// a hard ceiling and a recognisable AbortError caller code can branch on.
//
// Defaults: 30s timeout (matches Supabase Edge Functions cold-start budget).
// Callers can pass a smaller value for fire-and-forget telemetry (embed-entry
// is 8s — if the embed pipeline is overwhelmed we silently skip rather than
// block the user's save).
//
// Skills consulted: devops (network resilience), realtime-engineer (signal
// propagation), architect ("every fetch must be bounded").
//
// Usage:
//   const res = await fetchWithTimeout(url, { method: 'POST', body }, 20000);
//   if (res === null) { /* timed out — caller decides UX */ }
//   else if (!res.ok) { ... } else { const j = await res.json(); ... }
//
// Returns: a Response on success, or null on timeout/abort. Network errors
// (DNS failure, offline) still throw — caller wraps in try/catch as today.
async function fetchWithTimeout(url, options, timeoutMs) {
  const ms = (typeof timeoutMs === 'number' && timeoutMs > 0) ? timeoutMs : 30000;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    const opts = Object.assign({}, options || {}, { signal: ctrl.signal });
    return await fetch(url, opts);
  } catch (e) {
    if (e && (e.name === 'AbortError' || e.code === 20)) return null;
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

if (typeof window !== 'undefined') window.fetchWithTimeout = fetchWithTimeout;

// ─────────────────────────────────────────────
// whConfirm() / whPrompt() — styled async modals
// ─────────────────────────────────────────────
// Drop-in async replacements for native confirm() / prompt(). Both block
// the main thread, can't be styled, and on some mobile browsers are
// silently suppressed entirely. The platform toast/modal stack owns the
// UI shell; whConfirm/whPrompt are the gateway to it.
//
// Migration from native:
//   if (!confirm('Delete X?')) return;
//     -> if (!(await whConfirm('Delete X?'))) return;        // caller becomes async
//
//   const name = prompt('Enter name'); if (!name) return;
//     -> const name = await whPrompt('Enter name'); if (!name) return;
//
// Both return a Promise:
//   whConfirm: resolves true (OK) / false (Cancel or Esc / backdrop click)
//   whPrompt: resolves the entered string, or null if cancelled
//
// ── WH_STATUS_ENUMS — canonical per-table status enums (single source of truth) ──
// Grounded Sweep critique W3 (status-enum-constants). Hand-typed status string
// literals drift from the DB enum and silently miscount KPIs — the dayplanner
// "overdue" bug compared schedule_items.item_status against the literal 'closed',
// a value that does NOT exist in the enum (pending/in_progress/done/blocked/
// skipped), so DONE items were counted as overdue (live 6 vs DB 3). Reference THIS
// map instead of hand-typing status strings. validate_status_enum_drift.py asserts
// it can never silently diverge from the canonical capture contract in
// supabase/migrations (deterministic JS-constant-vs-DB comparison).
if (typeof window !== 'undefined' && !window.WH_STATUS_ENUMS) {
  window.WH_STATUS_ENUMS = {
    // schedule_items.item_status — capture_contracts_wave2 migration. 'done' is the
    // only terminal/closed state; everything else is OPEN (overdue if past due).
    schedule_item: ['pending', 'in_progress', 'done', 'blocked', 'skipped'],
  };
}

// ── whModalA11y — retrofit the dialog a11y bar onto a HAND-ROLLED modal ──────
// Grounded Sweep critique C7 / W2. whConfirm/whPrompt build their dialog in JS
// with the a11y bar already set; pages with static hand-rolled overlays (logbook,
// pm-scheduler, dayplanner, …) skip it. This helper adds the bar to an existing
// element WITHOUT touching its open/close call sites: it sets role=dialog +
// aria-modal + an accessible name, then a MutationObserver watches the element's
// class/style and — when it becomes visible — captures focus, traps Tab within
// the panel, and wires ESC; when it hides, it restores focus to the opener.
// Idempotent + opt-in. opts: { label?, labelledBy?, onClose? }.
//   whModalA11y(document.getElementById('my-modal'), { label: 'Edit asset', onClose: closeMyModal });
(function(){
  if (typeof window === 'undefined' || window.whModalA11y) return;

  var FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),' +
                  'select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

  // ─────────────────────────────────────────────
  // whToggleAria — canonical toggle-state announcer (Arc U, WCAG 4.1.2)
  // ─────────────────────────────────────────────
  // Toggleable filter/tab buttons flip an `.active` class but say nothing to a
  // screen reader — `aria-pressed` is what announces "pressed/not pressed". Rather
  // than hand-add it to every button on every page, this ONE shared helper (utils.js
  // is the 31/32 shared surface) sets aria-pressed from `.active` at init AND observes
  // class changes so a toggle stays announced. Genuinely correct: a screen reader
  // reads the RUNTIME DOM. Managed classes = the ones the a11y gate knows as toggleables.
  // 2026-07-18: extended after the thorough class-T (T8) sweep found stateful tabs/toggles on
  // engineering-design (.page-tab), pm-scheduler (.nav-tab), marketplace (.section-toggle-btn,
  // .btn-filter), analytics (.kpi-toggle) that show .active visually but exposed no aria-state.
  // Adding them here auto-wires aria-pressed (synced to .active by the MutationObserver) family-wide.
  window.WH_TOGGLE_CLASSES = ['filter-chip', 'tab-btn', 'reaction-btn', 'phase-tab', 'view-tab',
    'page-tab', 'nav-tab', 'section-toggle-btn', 'kpi-toggle', 'btn-filter', 'wh-toggle',
    'discipline-pill'];  // eng-design discipline chooser: 1 active = a SELECT, announce it (WCAG 4.1.2 + R3)
  function whToggleAria(root) {
    if (typeof document === 'undefined') return;
    root = root || document;
    var sel = window.WH_TOGGLE_CLASSES.map(function (c) { return 'button.' + c + ', .' + c + '[role="button"]'; }).join(', ');
    var btns = root.querySelectorAll(sel);
    if (!btns.length) return;
    var sync = function (el) {
      // radio-style tabs use aria-selected; a DISCLOSURE (declares aria-expanded, e.g. a
      // filter PANEL trigger) syncs aria-expanded; a POPUP/DIALOG trigger (declares
      // aria-haspopup, e.g. the community open-thread reply button) is a PRESS that opens a
      // dialog — it has no pressed-state, so it is left untouched; plain toggle chips use
      // aria-pressed. Giving a disclosure/popup-trigger aria-pressed would mislabel it a
      // stateful SELECT (R3 control-vocab: a panel/dialog opener must not share the select
      // silhouette) and is WCAG 4.1.2-wrong (expand→aria-expanded, popup→aria-haspopup).
      var attr = (el.getAttribute('role') === 'tab') ? 'aria-selected'
               : el.hasAttribute('aria-expanded') ? 'aria-expanded'
               : el.hasAttribute('aria-haspopup') ? null
               : 'aria-pressed';
      if (!attr) return;
      el.setAttribute(attr, el.classList.contains('active') ? 'true' : 'false');
    };
    btns.forEach(sync);
    // observe .active flips AND newly-inserted toggles so the announced state tracks the visual
    // state. 2026-07-18: data-driven pages render toggles AFTER load (analytics .kpi-toggle) — the
    // attribute-only observer never wired them, so add childList to catch dynamically-added ones.
    if (!window.__whToggleObs) {
      window.__whToggleObs = new MutationObserver(function (muts) {
        muts.forEach(function (m) {
          if (m.type === 'attributes' && m.attributeName === 'class') {
            var el = m.target;
            if (window.WH_TOGGLE_CLASSES.some(function (c) { return el.classList && el.classList.contains(c); })) sync(el);
          } else if (m.type === 'childList') {
            m.addedNodes.forEach(function (n) {
              if (n.nodeType !== 1) return;
              if (window.WH_TOGGLE_CLASSES.some(function (c) { return n.classList && n.classList.contains(c); })) sync(n);
              if (n.querySelectorAll) n.querySelectorAll(sel).forEach(sync);
            });
          }
        });
      });
      window.__whToggleObs.observe(document.body, { subtree: true, attributes: true, attributeFilter: ['class'], childList: true });
    }
  }
  window.whToggleAria = whToggleAria;
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { whToggleAria(); });
    else whToggleAria();
  }

  window.whModalA11y = function whModalA11y(modalEl, opts) {
    if (!modalEl || modalEl.__whModalA11y) return null;   // null el or already wired
    opts = opts || {};
    modalEl.__whModalA11y = true;

    if (!modalEl.getAttribute('role'))       modalEl.setAttribute('role', 'dialog');
    if (!modalEl.hasAttribute('aria-modal')) modalEl.setAttribute('aria-modal', 'true');
    if (opts.labelledBy)                     modalEl.setAttribute('aria-labelledby', opts.labelledBy);
    else if (opts.label && !modalEl.getAttribute('aria-label')) modalEl.setAttribute('aria-label', opts.label);

    var lastFocus = null, keyBound = false;

    function isOpen() {
      var cs = window.getComputedStyle(modalEl);
      // A retained `.hidden` class means CLOSED only when the COMPUTED style agrees.
      // logbook's 7 hand-rolled modals open via an inline `style.display:flex` that
      // OVERRIDES a `.hidden` class they never remove — visually open, but keying off
      // the class ALONE false-negatived isOpen(), so the ESC-close + Tab focus-trap +
      // focus-restore never armed (the retrofit silently no-op'd). Gate the class on the
      // computed display so an inline-override is correctly seen as open. (2026-07-13)
      if (modalEl.classList.contains('hidden') && cs.display === 'none') return false;
      // .sheet content panels (marketplace/community) slide via transform and
      // toggle a .open class; when closed they stay display:block + pointer-
      // events:auto (just translated off-screen), so the generic checks below
      // can't see "closed". Treat a transform-slide .sheet without .open as
      // closed, else whModalA11y would trap focus on page load. (2026-06-09)
      if (modalEl.classList.contains('sheet') && !modalEl.classList.contains('open')) return false;
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
      // Opacity/pointer-events open pattern (skillmatrix .modal-overlay,
      // marketplace/community .sheet-overlay, founder-console .fb-drawer-backdrop):
      // the overlay STAYS display:flex and toggles a .open class that flips
      // opacity + pointer-events. When closed it is pointer-events:none — detect
      // that so we don't treat a fully-invisible overlay as permanently open and
      // trap focus on page load. pointer-events flips instantly with the class;
      // opacity is transitioned, so reading opacity would mis-fire mid-animation.
      if (cs.pointerEvents === 'none') return false;
      return true;
    }
    function focusables() {
      return Array.prototype.filter.call(modalEl.querySelectorAll(FOCUSABLE), function(el) {
        return el.offsetParent !== null || el.getClientRects().length > 0;
      });
    }
    function onKey(e) {
      if (e.key === 'Escape') {
        e.stopPropagation();
        if (typeof opts.onClose === 'function') { opts.onClose(); return; }
        // No explicit close fn: click the modal's OWN close control so the page's
        // real close logic runs (removes .open / adds .hidden / clears state) — no
        // sticky inline display:none that would break the next open. Fall back to
        // adding .hidden only if the modal has no close affordance.
        var closer = null;
        try { closer = modalEl.querySelector('[data-wh-close],[aria-label="Close" i],.modal-close,.sheet-close'); }
        catch (_) { /* empty-catch-allow: querySelector case-flag unsupported */ }
        if (closer) closer.click();
        // No close affordance (e.g. a sheet whose content — and its Close button —
        // is injected on open, opened here while empty): close by the overlay's OWN
        // open-state class so it can't get stuck open. .sheet-overlay opens via
        // `.open`; some modals via `.active`/`.show`; display-toggle modals via
        // `.hidden`. Strip the open-state classes AND add .hidden — universal close.
        else { modalEl.classList.remove('open', 'active', 'show'); modalEl.classList.add('hidden'); }
      } else if (e.key === 'Tab') {
        var f = focusables();
        if (!f.length) return;
        var first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }
    function activate() {
      if (keyBound) return;
      keyBound = true;
      lastFocus = document.activeElement;
      document.addEventListener('keydown', onKey, true);
      // Respect a page that already autofocused something inside the modal
      // (e.g. dayplanner focuses #m-title) — only grab focus if it's outside.
      setTimeout(function() {
        if (!modalEl.contains(document.activeElement)) {
          var f = focusables();
          if (f.length) { try { f[0].focus(); } catch (_) { /* empty-catch-allow */ } }
        }
      }, 0);
    }
    function deactivate() {
      if (!keyBound) return;
      keyBound = false;
      try { document.removeEventListener('keydown', onKey, true); } catch (_) { /* empty-catch-allow */ }
      try { if (lastFocus && lastFocus.focus) lastFocus.focus(); } catch (_) { /* empty-catch-allow */ }
    }

    var obs = new MutationObserver(function() { isOpen() ? activate() : deactivate(); });
    obs.observe(modalEl, { attributes: true, attributeFilter: ['class', 'style'] });
    if (isOpen()) activate();   // already-open at wire time
    return { activate: activate, deactivate: deactivate };
  };

  // ─────────────────────────────────────────────
  // whSheetA11y — auto-wire the shared modal a11y to every bottom-sheet / overlay
  // ─────────────────────────────────────────────
  // The sheet/overlay focus-trap + Escape-close + focus-restore behaviour is ONE
  // shared primitive (whModalA11y above). Rather than each page calling it per
  // overlay, this finds every `.sheet-overlay` / `.modal-overlay` and wires it once,
  // and watches for overlays injected later. Idempotent — whModalA11y guards with
  // __whModalA11y, and only arms the trap when the overlay is actually open. This is
  // the Arc-U (WCAG 2.1.2 No-Keyboard-Trap-escape / 2.4.3 Focus-Order) shared lever.
  function whSheetA11y(root) {
    if (typeof document === 'undefined' || !window.whModalA11y) return;
    root = root || document;
    var els = root.querySelectorAll('.sheet-overlay, .modal-overlay');
    Array.prototype.forEach.call(els, function (el) {
      try { window.whModalA11y(el); } catch (_) { /* empty-catch-allow */ }
    });
  }
  window.whSheetA11y = whSheetA11y;
  if (typeof document !== 'undefined') {
    var _wireSheets = function () {
      whSheetA11y();
      if (!window.__whSheetObs && document.body) {
        window.__whSheetObs = new MutationObserver(function (muts) {
          for (var i = 0; i < muts.length; i++) {
            var added = muts[i].addedNodes;
            for (var j = 0; j < added.length; j++) {
              var n = added[j];
              if (!n || n.nodeType !== 1) continue;
              if (n.matches && n.matches('.sheet-overlay, .modal-overlay')) {
                try { window.whModalA11y(n); } catch (_) { /* empty-catch-allow */ }
              }
              if (n.querySelectorAll) whSheetA11y(n);
            }
          }
        });
        window.__whSheetObs.observe(document.body, { childList: true, subtree: true });
      }
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', _wireSheets);
    else _wireSheets();
  }
})();

// The modal mounts on document.body (so it works on any page without
// per-page setup), traps focus, and disposes on resolve. ARIA: role="dialog"
// + aria-labelledby + aria-modal so screen readers announce it.
(function(){
  if (typeof window === 'undefined' || window.whConfirm) return;

  function _mount(opts) {
    const {
      message,
      okLabel = 'OK',
      cancelLabel = 'Cancel',
      withInput = false,
      inputLabel = '',
      inputDefault = '',
      onResolve,
    } = opts;

    const ovId   = 'wh-modal-ov-' + Date.now() + '-' + Math.floor(Math.random()*1000);
    const titleId = ovId + '-title';
    const inputId = ovId + '-input';

    const overlay = document.createElement('div');
    overlay.id = ovId;
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', titleId);
    overlay.style.cssText =
      'position:fixed;inset:0;z-index:10001;background:rgba(0,0,0,0.6);' +
      'backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;' +
      'padding:16px;animation:wh-fade-in 0.12s ease-out;';

    overlay.innerHTML =
      '<div style="background:#162032;border:1px solid rgba(255,255,255,0.1);border-radius:14px;' +
        'padding:20px 22px;max-width:440px;width:100%;box-shadow:0 16px 48px rgba(0,0,0,0.5);">' +
        '<p id="' + escHtml(titleId) + '" style="font-size:0.95rem;font-weight:600;color:#F4F6FA;' +
          'margin:0 0 14px;line-height:1.45;">' + escHtml(message) + '</p>' +
        (withInput
          ? '<input id="' + escHtml(inputId) + '" type="text" ' +
            'aria-label="' + escHtml(inputLabel || message) + '" ' +
            'value="' + escHtml(inputDefault || '') + '" ' +
            'style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.12);' +
            'background:rgba(255,255,255,0.04);color:#F4F6FA;font-size:0.9rem;font-family:inherit;' +
            'margin-bottom:14px;min-height:44px;" />'
          : ''
        ) +
        '<div style="display:flex;gap:8px;justify-content:flex-end;">' +
          '<button type="button" data-wh-modal-cancel ' +
            'style="background:transparent;color:rgba(255,255,255,0.65);border:1px solid rgba(255,255,255,0.12);' +
            'border-radius:8px;padding:9px 16px;font-size:0.85rem;font-weight:600;cursor:pointer;' +
            'min-height:44px;font-family:inherit;">' + escHtml(cancelLabel) + '</button>' +
          '<button type="button" data-wh-modal-ok ' +
            'style="background:#F7A21B;color:#162032;border:none;border-radius:8px;padding:9px 16px;' +
            'font-size:0.85rem;font-weight:700;cursor:pointer;min-height:44px;font-family:inherit;">' +
            escHtml(okLabel) + '</button>' +
        '</div>' +
      '</div>';

    document.body.appendChild(overlay);

    const inputEl  = withInput ? overlay.querySelector('#' + CSS.escape(inputId)) : null;
    const cancelEl = overlay.querySelector('[data-wh-modal-cancel]');
    const okEl     = overlay.querySelector('[data-wh-modal-ok]');

    // Trap focus + autofocus the relevant control
    const focusTarget = inputEl || okEl;
    setTimeout(() => focusTarget && focusTarget.focus(), 0);

    function dispose(value) {
      try { document.removeEventListener('keydown', onKey, true); } catch (_) { /* empty-catch-allow: best-effort cleanup */ }
      try { overlay.remove(); } catch (_) { /* empty-catch-allow: best-effort cleanup */ }
      onResolve(value);
    }
    function onKey(e) {
      if (e.key === 'Escape') { e.stopPropagation(); dispose(withInput ? null : false); }
      else if (e.key === 'Enter' && (e.target === inputEl || e.target === okEl || !withInput)) {
        e.stopPropagation();
        dispose(withInput ? (inputEl.value || '') : true);
      }
    }
    document.addEventListener('keydown', onKey, true);

    cancelEl.addEventListener('click', () => dispose(withInput ? null : false));
    okEl.addEventListener('click',     () => dispose(withInput ? (inputEl.value || '') : true));
    overlay.addEventListener('click', (e) => { if (e.target === overlay) dispose(withInput ? null : false); });
  }

  window.whConfirm = function whConfirm(message, opts) {
    opts = opts || {};
    return new Promise((resolve) => {
      _mount({
        message,
        okLabel:     opts.okLabel || 'OK',
        cancelLabel: opts.cancelLabel || 'Cancel',
        withInput:   false,
        onResolve:   resolve,
      });
    });
  };

  window.whPrompt = function whPrompt(message, opts) {
    opts = opts || {};
    return new Promise((resolve) => {
      _mount({
        message,
        okLabel:      opts.okLabel || 'OK',
        cancelLabel:  opts.cancelLabel || 'Cancel',
        withInput:    true,
        inputLabel:   opts.inputLabel || '',
        inputDefault: opts.defaultValue || '',
        onResolve:    resolve,
      });
    });
  };

  // Inject the minimal fade-in keyframe (the same shell used elsewhere reuses
  // existing animations, but whConfirm is loaded on every page so it owns its
  // own animation to avoid a load-order dependency).
  try {
    if (!document.getElementById('wh-modal-anim-style')) {
      const s = document.createElement('style');
      s.id = 'wh-modal-anim-style';
      s.textContent = '@keyframes wh-fade-in{from{opacity:0;}to{opacity:1;}}';
      document.head.appendChild(s);
    }
  } catch (_) { /* empty-catch-allow: best-effort style inject; modal still works without anim */ }
})();

// ─────────────────────────────────────────────
// trimChatToTokenBudget — context-window compressor (Phase 1.8 of STRATEGIC_ROADMAP)
// ─────────────────────────────────────────────
// floating-ai and assistant.html both stuff a long system prompt (2k-2.7k
// tokens) into every turn, then append the conversation history. On the Groq
// 8K-32K free-tier models this leaves a thin budget for the actual user
// message. Without a compressor, a long voice transcription mid-thread can
// silently overflow the model context and either error out or truncate the
// system prompt (which is the LAST thing you want trimmed).
//
// Strategy: keep the most-recent turns and drop the oldest user/assistant
// pairs first. The system prompt is the caller's responsibility — pass its
// estimated token cost in `systemTokens` so the budget math is honest. We
// never drop the most recent user message (that's the turn being asked).
//
// Token heuristic: 1 token ≈ 4 chars (English). Identical to the heuristic
// used by _shared/cost-log.ts so observability and runtime agree.
//
// Args:
//   messages       array of {role, content} — your sessionMessages so far
//   opts.budget    total budget in tokens for the model context (default 7000
//                  to match Groq llama-3.3-70b-versatile minus a safety pad)
//   opts.systemTokens cost of the system prompt you'll prepend at send time
//   opts.reserveOut tokens reserved for the model's response (default 800)
//
// Returns: a NEW array (does not mutate input) trimmed to fit.
//
// Skills consulted: ai-engineer (context budget = system + history + output),
// performance (cheap O(n) walk, no expensive tokenizer).
function trimChatToTokenBudget(messages, opts) {
  opts = opts || {};
  const budget       = typeof opts.budget       === 'number' ? opts.budget       : 7000;
  const systemTokens = typeof opts.systemTokens === 'number' ? opts.systemTokens : 0;
  const reserveOut   = typeof opts.reserveOut   === 'number' ? opts.reserveOut   : 800;
  const limit = Math.max(200, budget - systemTokens - reserveOut);

  const list = Array.isArray(messages) ? messages.slice() : [];
  if (list.length <= 1) return list;

  const cost = (m) => Math.round(String(m && m.content || '').length / 4);

  // Walk from the end, keeping recent turns; drop the oldest once over budget.
  let total = 0;
  const kept = [];
  for (let i = list.length - 1; i >= 0; i--) {
    const c = cost(list[i]);
    if (total + c > limit && kept.length > 0) break;
    kept.unshift(list[i]);
    total += c;
  }
  return kept;
}

if (typeof window !== 'undefined') window.trimChatToTokenBudget = trimChatToTokenBudget;

// Debounce — delay fn execution until after `wait` ms of silence
function debounce(fn, wait) {
  let t;
  return function (...args) {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), wait);
  };
}

/* C4: Session restore — returns worker display_name from localStorage or auth session.
 * Call at the top of each page's async init before redirecting to signin.
 *
 *   const wn = await restoreIdentityFromSession(db);
 *   if (!wn) { location.assign('index.html?signin=1'); return; }
 *
 * (Block comment + `location.assign(...)` so the L2 admin_gate_not_commented
 * sentinel doesn't false-positive on the example line.)
 */
async function restoreIdentityFromSession(db) {
  const cached = localStorage.getItem('wh_last_worker')
               || /* storage-key-allow: legacy worker-name fallback (current writes use wh_last_worker) */ localStorage.getItem('wh_worker_name')
               || localStorage.getItem('workerName') || '';
  if (cached) return cached;
  try {
    const { data: { session } } = await db.auth.getSession();
    if (!session) return '';
    const { data: profile } = await db.from('v_worker_truth')
      .select('worker_name').eq('auth_uid', session.user.id).maybeSingle();
    if (profile?.worker_name) {
      localStorage.setItem('wh_last_worker', profile.worker_name);
      return profile.worker_name;
    }
  } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
  return '';
}

// ─────────────────────────────────────────────
// Founder Console — analytics event SDK (Phase 0)
// ─────────────────────────────────────────────
// Every page should call logPageView(db) once after identity restore. Feature
// pages also emit feature-level events via logEvent(db, name, props).
//
// Writes are fire-and-forget — never block the user action. Append-only:
// the analytics_events table has no UPDATE/DELETE policies. SELECT is
// restricted to platform admins (marketplace_platform_admins allowlist).
//
// Skill alignment: analytics-engineer (KPI source events), architect
// ("Audit Log Writes Must Be Fire-and-Forget"), security (no PII in props).
let _wh_session_id = null;
function _whSessionId() {
  if (_wh_session_id) return _wh_session_id;
  try {
    let s = sessionStorage.getItem('wh_session_id');
    if (!s) {
      s = (window.crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2);
      sessionStorage.setItem('wh_session_id', s);
    }
    _wh_session_id = s;
    return s;
  } catch (_) { return null; }
}

function logEvent(db, eventName, props) {
  if (!db || !eventName) return;
  try {
    const workerName = localStorage.getItem('wh_last_worker')
                    || /* storage-key-allow: legacy worker-name fallback (current writes use wh_last_worker) */ localStorage.getItem('wh_worker_name')
                    || localStorage.getItem('workerName') || null;
    const hiveId = localStorage.getItem('wh_active_hive_id')
                || localStorage.getItem('wh_hive_id') || null;
    const payload = {
      event_name: eventName,
      props: props || {},
      page: (props && props.page) || null,
      worker_name: workerName,
      hive_id: hiveId,
      session_id: _whSessionId(),
      user_agent: (navigator.userAgent || '').slice(0, 200),
    };
    // Try to attach auth_uid if a session exists - non-blocking.
    const insert = function () {
      /* attribution-allow: auth_uid is set dynamically at payload.auth_uid = session.user.id
         (getSession callback below) before this insert fires; statically invisible to the gate. */
      db.from('analytics_events').insert(payload).then(function (r) {
        if (r && r.error) console.warn('logEvent:', r.error.message);
      });
    };
    db.auth.getSession().then(function (res) {
      if (res && res.data && res.data.session) {
        payload.auth_uid = res.data.session.user.id;
      }
      insert();
    }).catch(insert);
  } catch (e) {
    console.warn('logEvent err:', e && e.message);
  }
}

// Convenience for the most common event - infers page name from URL.
function logPageView(db, extraProps) {
  const path = (location.pathname.split('/').pop() || 'index.html')
    .replace(/\.html$/i, '') || 'index';
  logEvent(db, 'page_view', Object.assign({ page: path }, extraProps || {}));
}

// ─────────────────────────────────────────────
// rtConn — realtime subscribe() connection-state guard (Arc J / realtime-engineer skill)
// ─────────────────────────────────────────────
// Supabase Realtime's subscribe() callback may NEVER fire (no SUBSCRIBED, no
// CHANNEL_ERROR, no TIMED_OUT) when the WebSocket silently fails to establish —
// common on weak plant-floor WiFi and corporate networks. Without a timeout the
// connection-state UI hangs at "Connecting…" forever. This factory returns a
// status callback for `channel.subscribe(rtConn(onState))` that:
//   • fires onState('offline') after `ms` if SUBSCRIBED never arrives,
//   • fires onState('live') on SUBSCRIBED, onState('offline') on error/timeout/close,
//   • is idempotent (settles once; clears its own timer).
// `onState` is optional — bare `rtConn()` just guards the silent freeze. For
// data-feed channels the page already rendered its initial DB query, so 'offline'
// simply means "live updates paused", not "no data".
function rtConn(onState, ms) {
  const cb = (typeof onState === 'function') ? onState : function () {};
  let settled = false;
  const timer = setTimeout(function () {
    if (!settled) { settled = true; cb('offline'); }
  }, ms || 8000);
  return function (status) {
    if (status === 'SUBSCRIBED') {
      settled = true; clearTimeout(timer); cb('live');
    } else if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT' || status === 'CLOSED') {
      settled = true; clearTimeout(timer); cb('offline');
    }
  };
}

// ─────────────────────────────────────────────
// isPlatformAdmin — gate util for founder-console.html (Phase 0)
// ─────────────────────────────────────────────
// Reuses marketplace_platform_admins so admin grants are a single source of
// truth. Returns false on no session, no profile, or worker not on allowlist.
async function isPlatformAdmin(db) {
  if (!db) return false;
  try {
    const { data: { session } } = await db.auth.getSession();
    if (!session) return false;
    const { data: profile } = await db.from('v_worker_truth')
      .select('worker_name').eq('auth_uid', session.user.id).maybeSingle();
    if (!profile || !profile.worker_name) return false;
    const { data: admin } = await db.from('marketplace_platform_admins')
      .select('worker_name').eq('worker_name', profile.worker_name).maybeSingle();
    return !!admin;
  } catch (_) { return false; }
}

// ─────────────────────────────────────────────
// Achievement tier system
// ─────────────────────────────────────────────

// tier.color is used as small TEXT ("Iron Technician" chip) as well as ring/tint —
// each value must clear WCAG AA 4.5:1 on the dark tints. Iron #7B8794 measured
// 3.08 and Bronze #CD7F32 2.6–3.3 as text (2026-07-16); lightened same-hue.
const ACHIEVEMENT_TIERS = [
  { id: 'legend',   min: 91, color: '#F7A21B', label: 'Legend'   },
  { id: 'platinum', min: 76, color: '#5FCCE8', label: 'Platinum' },
  { id: 'gold',     min: 51, color: '#F7A21B', label: 'Gold'     },
  { id: 'silver',   min: 26, color: '#94A3B8', label: 'Silver'   },
  { id: 'bronze',   min: 11, color: '#E8B27A', label: 'Bronze'   },
  { id: 'iron',     min:  0, color: '#A9B6C4', label: 'Iron'     },
];

function getWorkerTier(topLevel) {
  return ACHIEVEMENT_TIERS.find(t => (topLevel || 0) >= t.min)
    || ACHIEVEMENT_TIERS[ACHIEVEMENT_TIERS.length - 1];
}

// Render a tier-framed avatar circle.
// size: pixel width/height — 42, 36, 32, 28, 22
// Badge (level pill) shown only when size >= 32 and topLevel > 0.
function renderWorkerAvatar(workerName, topLevel, size) {
  const sz   = size || 32;
  const tier = getWorkerTier(topLevel || 0);
  const init = escHtml(
    String(workerName || '?').trim().split(/\s+/).map(function (w) { return w[0]; }).join('').slice(0, 2).toUpperCase()
  );
  const fs = sz >= 42 ? '0.95rem' : sz >= 32 ? '0.72rem' : sz >= 28 ? '0.65rem' : '0.55rem';
  const badge = (sz >= 32 && (topLevel || 0) > 0)
    ? '<span class="wh-avatar-lvl">' + (topLevel || 0) + '</span>'
    : '';
  return '<div class="wh-avatar wh-tier-' + tier.id + '" '
    + 'style="width:' + sz + 'px;height:' + sz + 'px;font-size:' + fs + ';--tier-clr:' + tier.color + ';" '
    + 'title="' + escHtml(workerName) + ' - ' + tier.label + ' Lv.' + (topLevel || 0) + '">'
    + init + badge + '</div>';
}

// Batch-load highest achievement level per worker.
// Returns { workerName: topLevel }. Safe to call when table does not exist yet.
async function loadWorkerTiers(db, workerNames) {
  if (!workerNames || !workerNames.length) return {};
  try {
    const { data } = await db
      .from('v_worker_achievements_truth')
      .select('worker_name, current_level')
      .in('worker_name', workerNames);
    const map = {};
    for (const row of (data || [])) {
      if (!map[row.worker_name] || row.current_level > map[row.worker_name]) {
        map[row.worker_name] = row.current_level;
      }
    }
    return map;
  } catch (_) { return {}; }
}

// Inject tier CSS once — runs immediately when utils.js loads
(function () {
  if (document.getElementById('wh-tier-styles')) return;
  const s = document.createElement('style');
  s.id = 'wh-tier-styles';
  s.textContent = [
    /* Base avatar with border-box so all tiers render at the same outer size */
    /* regardless of border thickness/style. Metallic inset shadows give depth. */
    '.wh-avatar{position:relative;border-radius:50%;flex-shrink:0;',
    'box-sizing:border-box;',
    'background:linear-gradient(135deg,#1F2E45,#2A3D58);',
    'display:flex;align-items:center;justify-content:center;',
    'font-family:"Poppins",sans-serif;font-weight:700;color:#F4F6FA;',
    'border:4px solid var(--tier-clr,#7B8794);',
    'box-shadow:inset 1px 1px 2px rgba(255,255,255,0.18),',
    '           inset -1px -1px 2px rgba(0,0,0,0.45);}',

    '.wh-avatar-lvl{position:absolute;bottom:-8px;left:50%;transform:translateX(-50%);',
    'background:var(--tier-clr,#7B8794);color:#162032;',
    'font-size:9px;font-weight:800;padding:1px 5px;',
    'border-radius:999px;border:2px solid #162032;',
    'min-width:20px;text-align:center;line-height:1.5;',
    'pointer-events:none;white-space:nowrap;z-index:3;',
    'box-shadow:0 2px 6px rgba(0,0,0,0.45),',
    '           inset 0 1px 0 rgba(255,255,255,0.3);}',

    /* ── IRON: DASHED border (incomplete/starting feel) + slow breathing ──── */
    '.wh-tier-iron{border:4px dashed #7B8794;animation:wh-breathe-iron 4s ease-in-out infinite;}',

    /* ── BRONZE: RIDGE border (3D embossed metal) + warm shimmer ─────────── */
    '.wh-tier-bronze{border:4px ridge #CD7F32;animation:wh-shimmer 3s ease-in-out infinite;}',

    /* ── SILVER: solid + COMET light sweeping around the rim ─────────────── */
    '.wh-tier-silver{border:4px solid #94A3B8;}',
    '.wh-tier-silver::after{content:"";position:absolute;inset:-4px;border-radius:50%;',
    'pointer-events:none;z-index:0;',
    'background:conic-gradient(from 0deg,transparent 0deg,transparent 300deg,',
    '  rgba(255,255,255,0.4) 330deg,rgba(255,255,255,0.95) 358deg,rgba(255,255,255,0.2) 360deg);',
    '-webkit-mask:radial-gradient(circle,transparent 56%,black 60%);',
    'mask:radial-gradient(circle,transparent 56%,black 60%);',
    'animation:wh-spin 3s linear infinite;}',

    /* ── GOLD: solid + 4 SPARKLE DOTS rotating like a crown ──────────────── */
    '.wh-tier-gold{border:4px solid #F7A21B;animation:wh-glow-gold 2.4s ease-in-out infinite;}',
    '.wh-tier-gold::after{content:"";position:absolute;inset:-3px;border-radius:50%;',
    'pointer-events:none;z-index:0;',
    'background:',
    '  radial-gradient(circle 1.8px at 50% 0%,rgba(255,255,255,1),transparent 60%),',
    '  radial-gradient(circle 1.8px at 100% 50%,rgba(255,255,255,1),transparent 60%),',
    '  radial-gradient(circle 1.8px at 50% 100%,rgba(255,255,255,1),transparent 60%),',
    '  radial-gradient(circle 1.8px at 0% 50%,rgba(255,255,255,1),transparent 60%);',
    'animation:wh-spin 4s linear infinite;}',

    /* ── PLATINUM: CONCENTRIC — solid inner + outer rotating dashed ring ─── */
    '.wh-tier-platinum{border:4px solid #29B6D9;animation:wh-glow-blue 2.4s ease-in-out infinite;}',
    '.wh-tier-platinum::after{content:"";position:absolute;inset:-7px;border-radius:50%;',
    'border:2px dashed rgba(41,182,217,0.85);',
    'pointer-events:none;z-index:0;',
    'animation:wh-spin 6s linear infinite;}',

    /* ── LEGEND: animated multi-color gradient ring + halo ───────────────── */
    '.wh-tier-legend{border:4px solid transparent;}',
    '.wh-tier-legend::before{content:"";position:absolute;inset:-4px;border-radius:50%;',
    'background:conic-gradient(#F7A21B,#FDB94A,#29B6D9,#5FCCE8,#F7A21B);',
    'animation:wh-spin 2s linear infinite;z-index:-1;',
    'filter:drop-shadow(0 0 10px rgba(247,162,27,0.6));}',
    '.wh-tier-legend::after{content:"";position:absolute;inset:-10px;border-radius:50%;',
    'border:1px solid rgba(247,162,27,0.25);pointer-events:none;z-index:0;',
    'animation:wh-spin 8s linear infinite reverse;}',

    /* Keyframes — only Iron/Bronze/Gold/Platinum animate the parent box-shadow. */
    /* Silver uses ::after only (rotating mask). Legend uses ::before/::after.   */
    '@keyframes wh-breathe-iron{0%,100%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.18), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 0 rgba(123,135,148,0);}',
    '50%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.18), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 8px rgba(180,195,210,0.35);}}',

    '@keyframes wh-shimmer{0%,100%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.2), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 6px rgba(205,127,50,0.45);}',
    '50%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.32), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 18px rgba(205,127,50,0.9);}}',

    '@keyframes wh-glow-gold{0%,100%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.22), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 8px rgba(247,162,27,0.55);}',
    '50%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.32), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 22px rgba(247,162,27,0.95);}}',

    '@keyframes wh-glow-blue{0%,100%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.22), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 8px rgba(41,182,217,0.55);}',
    '50%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.32), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 22px rgba(41,182,217,0.95);}}',

    '@keyframes wh-spin{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}'
  ].join('');
  document.head.appendChild(s);
}());

// ── whCompressImage — Arc L scale-out (2026-06-23): client-side image compression ──
// At a million users, raw ~0.35-3 MB phone photos are tens of TB of object storage and
// egress. Resizing to a sane max dimension + re-encoding to WebP cuts that ~5-10x while
// keeping a defect photo (rust/leak/crack/burn) perfectly legible — 1600px is plenty.
// Robust: a File OR a dataURL in; ALWAYS returns a dataURL; on ANY failure (unsupported
// codec, decode error, or a result that isn't smaller) it returns the ORIGINAL unharmed.
//   const small = await whCompressImage(fileOrDataUrl, { maxDim: 1600, quality: 0.82 });
function _whFileToDataUrl(file) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(r.result);
    r.onerror = rej;
    r.readAsDataURL(file);
  });
}
async function whCompressImage(input, opts) {
  opts = opts || {};
  const maxDim  = opts.maxDim  || 1600;
  const quality = opts.quality || 0.82;
  const mime    = opts.type    || 'image/webp';
  const origP   = (typeof input === 'string') ? Promise.resolve(input) : _whFileToDataUrl(input);
  try {
    const srcUrl = (typeof input === 'string') ? input : URL.createObjectURL(input);
    const img = await new Promise((res, rej) => {
      const im = new Image();
      im.onload = () => res(im);
      im.onerror = rej;
      im.src = srcUrl;
    });
    if (typeof input !== 'string') { try { URL.revokeObjectURL(srcUrl); } catch (_e) { /* empty-catch-allow: best-effort object-URL cleanup */ } }
    const w = img.naturalWidth || img.width, h = img.naturalHeight || img.height;
    if (!w || !h) return await origP;
    const scale = Math.min(1, maxDim / Math.max(w, h));   // never upscale
    const cw = Math.max(1, Math.round(w * scale)), ch = Math.max(1, Math.round(h * scale));
    const canvas = document.createElement('canvas');
    canvas.width = cw; canvas.height = ch;
    canvas.getContext('2d').drawImage(img, 0, 0, cw, ch);
    let out = canvas.toDataURL(mime, quality);
    if (out.indexOf('data:' + mime) !== 0) out = canvas.toDataURL('image/jpeg', quality);  // WebP unsupported -> JPEG
    const orig = await origP;
    return (out && out.length < orig.length) ? out : orig;   // never regress size
  } catch (_e) {
    return await origP;   // decode/codec failure -> original, never break the upload
  }
}
if (typeof window !== 'undefined') { window.whCompressImage = whCompressImage; }

// ── whPoll — Arc L scale-out (2026-06-23): visibility-aware polling fallback ──
// The 1M realtime decision (Ian: "reduce + poll-fallback, no new infra"): Supabase
// Realtime caps ~10K concurrent channels, so at 20K peak-concurrent users a per-user
// WebSocket subscription is a hard wall. For NON-safety-critical surfaces, replace the
// `.channel().subscribe()` with this: it re-runs the page's load fn on an interval,
// PAUSES while the tab is hidden (no wasted reads/egress on background tabs — the key
// to it scaling), runs once immediately, and returns a handle with .stop().
//   const h = whPoll(loadAlertsPanel, 20000);   // refresh every 20s while visible
//   // later / on teardown: h.stop();
function whPoll(loadFn, intervalMs, opts) {
  opts = opts || {};
  const ms = Math.max(5000, intervalMs || 30000);   // floor 5s — never hammer
  let timer = null, stopped = false, inFlight = false;
  async function tick() {
    if (stopped || inFlight) return;
    if (typeof document !== 'undefined' && document.hidden) return;  // skip while backgrounded
    inFlight = true;
    try { await loadFn(); } catch (_e) { /* empty-catch-allow: a transient load error must not kill the loop */ }
    finally { inFlight = false; }
  }
  function start() {
    if (timer) return;
    timer = setInterval(tick, ms);
  }
  function onVis() { if (!document.hidden) tick(); }   // refresh immediately on tab refocus
  if (opts.immediate !== false) tick();                // run once now (matches realtime's initial state)
  start();
  if (typeof document !== 'undefined') document.addEventListener('visibilitychange', onVis);
  return {
    stop() {
      stopped = true;
      if (timer) { clearInterval(timer); timer = null; }
      if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', onVis);
    },
    refresh: tick,
  };
}
if (typeof window !== 'undefined') { window.whPoll = whPoll; }

// ── whRealtimeSubscribe — Q5 (2026-07-05): per-client channel CAP + graceful poll degrade ──
// GROUNDED (Step 0, VERIFIED not memory): Supabase FREE tier = **200 concurrent realtime
// connections PLATFORM-WIDE** — far tighter than the ~10K the whPoll note assumed. That 200 is
// shared across ALL users (like the LLM org-pool), so one heavy client opening many channels
// eats a disproportionate slice. This wrapper (a) bounds channels PER CLIENT (default 5 — a
// single user rarely needs more live surfaces at once), and (b) gracefully DEGRADES overflow —
// and offline — to whPoll, so a surface ALWAYS updates: live when there's headroom, polled when
// there isn't. Composes the two existing primitives: rtConn (silent-freeze guard) + whPoll.
// `buildChannel()` must return an UNSUBSCRIBED channel (e.g. supabase.channel(x).on(...)); this
// calls .subscribe() so it can wrap the state callback.
//   const h = whRealtimeSubscribe('alerts',
//               () => supabase.channel('alerts:'+hive).on('postgres_changes', {...}, reload),
//               reload, { pollMs: 20000 });
//   // teardown: h.stop();
var WH_MAX_CLIENT_CHANNELS = 5;   // per-client concurrent realtime cap (window/opts override)
function whRealtimeSubscribe(name, buildChannel, reloadFn, opts) {
  opts = opts || {};
  var max = opts.max
    || (typeof window !== 'undefined' && window.WH_MAX_CLIENT_CHANNELS)
    || WH_MAX_CLIENT_CHANNELS;
  var pollMs = opts.pollMs || 30000;
  var reg = (typeof window !== 'undefined')
    ? (window.__whChannels || (window.__whChannels = new Set()))
    : (whRealtimeSubscribe._reg || (whRealtimeSubscribe._reg = new Set()));

  function degradeToPoll(reason) {
    var ph = whPoll(reloadFn, pollMs, { immediate: opts.immediate });
    return { mode: 'poll', reason: reason, stop: function () { ph.stop(); }, refresh: ph.refresh };
  }

  // (a) per-client channel cap reached, or no builder -> poll (graceful degrade, surface still live-ish)
  if (reg.size >= max) return degradeToPoll('cap');
  if (typeof buildChannel !== 'function') return degradeToPoll('no-builder');

  var channel, pollHandle = null;
  try {
    channel = buildChannel();
    reg.add(channel);
    // (b) offline -> spin up a poll fallback; recovered -> stop polling. rtConn guards the
    // silent-freeze case where subscribe() never fires any status.
    channel.subscribe(rtConn(function (state) {
      if (state === 'offline' && !pollHandle) {
        pollHandle = whPoll(reloadFn, pollMs, { immediate: false });
      } else if (state === 'live' && pollHandle) {
        pollHandle.stop(); pollHandle = null;
      }
      if (opts.onState) opts.onState(state);
    }));
  } catch (_e) {
    if (channel) reg.delete(channel);
    return degradeToPoll('subscribe-error');
  }

  return {
    mode: 'realtime',
    stop: function () {
      reg.delete(channel);                       // free the per-client slot
      if (pollHandle) { pollHandle.stop(); pollHandle = null; }
      try {
        if (typeof window !== 'undefined' && window.supabase && window.supabase.removeChannel) {
          window.supabase.removeChannel(channel);
        } else if (channel && channel.unsubscribe) {
          channel.unsubscribe();
        }
      } catch (_e) { /* empty-catch-allow: teardown best-effort, never throw on cleanup */ }
    },
  };
}
if (typeof window !== 'undefined') {
  window.whRealtimeSubscribe = whRealtimeSubscribe;
  // Telemetry / graceful-429 signal: how many live channels this client currently holds.
  window.__whChannelCount = function () { return (window.__whChannels && window.__whChannels.size) || 0; };
}

// ── Keyboard-a11y polyfill for mouse-only clickables (dim-8) ─────────────────────────────────
// A `<div|span|li onclick=...>` with no role=button / no keyboard path is mouse-only: keyboard +
// screen-reader users can't reach or activate it. Rather than retrofit dozens of elements by hand,
// this upgrades EVERY such element (static + dynamically-rendered) to keyboard-operable: focusable,
// announced as a button, and activated by Enter/Space. Progressive enhancement — it only matters
// when JS is running, and the onclick it mirrors also needs JS, so keyboard reaches parity with mouse.
(function whClickableKbdA11y() {
  if (typeof document === 'undefined') return;
  var CLICKABLE = 'div[onclick],span[onclick],li[onclick]';
  var SKIP_ROLE = /^(button|tab|menuitem|link|checkbox|switch|option|radio|combobox)$/;
  function enhance(el) {
    if (!el || el.__whKbd || el.nodeType !== 1) return;
    if (!el.hasAttribute('onclick')) return;
    var role = el.getAttribute('role');
    if (role && SKIP_ROLE.test(role)) return;                 // already an interactive role
    if (el.hasAttribute('tabindex') && el.hasAttribute('onkeydown')) return; // author already handled it
    // Skip containers whose real action is an INNER interactive control (adding role=button here
    // would nest interactives + the inner control is already keyboard-accessible).
    if (el.querySelector('a[href],button,input,select,textarea,[role="button"],[role="link"],[tabindex]')) return;
    el.__whKbd = true;
    el.classList.add('wh-kbd-a11y');   // gets the injected focus-visible ring (WCAG 2.4.7)
    if (!role) el.setAttribute('role', 'button');
    if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '0');
    el.addEventListener('keydown', function (e) {
      if ((e.key === 'Enter' || e.key === ' ') && e.target === el) { e.preventDefault(); el.click(); }
    });
  }
  function injectFocusStyle() {
    // Keyboard-focusable is only useful if focus is VISIBLE (WCAG 2.4.7). Guarantee a focus ring on
    // the elements we upgrade, scoped to them (:focus-visible = keyboard focus only, not mouse click).
    try {
      if (document.getElementById('wh-kbd-a11y-style')) return;
      var s = document.createElement('style');
      s.id = 'wh-kbd-a11y-style';
      s.textContent = '.wh-kbd-a11y:focus-visible{outline:2px solid var(--wh-orange,#F7A21B);outline-offset:2px;border-radius:4px;}';
      (document.head || document.documentElement).appendChild(s);
    } catch (_) { /* empty-catch-allow: best-effort a11y style injection; page works without it */ }
  }
  function scan(root) {
    try { (root.querySelectorAll ? root.querySelectorAll(CLICKABLE) : []).forEach(enhance); } catch (_) { /* empty-catch-allow: best-effort a11y enhancement; never block a render */ }
  }
  function boot() {
    injectFocusStyle();
    scan(document);
    try {
      new MutationObserver(function (muts) {
        for (var i = 0; i < muts.length; i++) {
          var added = muts[i].addedNodes;
          for (var j = 0; j < added.length; j++) {
            var n = added[j];
            if (n.nodeType !== 1) continue;
            if (n.matches && n.matches(CLICKABLE)) enhance(n);
            scan(n);
          }
        }
      }).observe(document.body, { childList: true, subtree: true });
    } catch (_) { /* empty-catch-allow: MutationObserver unsupported; the initial scan still covers static markup */ }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
  if (typeof window !== 'undefined') window.whEnhanceClickableA11y = scan;  // pages can re-scan after a manual render
})();
