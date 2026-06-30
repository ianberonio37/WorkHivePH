/**
// capability: display_wayfinding
 * WorkHive Wayfinding Chrome — Arc Y (THE INTUITION GRADIENT) · Y1
 * ───────────────────────────────────────────────────────────────
 * The platform-wide "where am I / how do I get BACK" fuse. ONE shared component,
 * lazy-loaded by nav-hub.js, so every page gets the SAME in-app Back affordance +
 * breadcrumb without per-page wiring — closing Ian's "you can't even press back"
 * (finding F3) and the back:N on ~30 pages the Y0.5 audit measured.
 *
 * What it gives every page (except the home root):
 *   1. A referrer-aware in-app BACK control (fixed top-left pill, 44px, safe-area aware).
 *      - ?from=<slug> deep-link hand-off  -> back to that slug
 *      - else same-origin document.referrer (not self) -> history.back()
 *      - else the page's parent (nav section home, or index.html)
 *      If the page ALREADY has a .back-btn (e.g. asset-hub's hard-coded one), we
 *      REWIRE it to this smart logic instead of adding a duplicate — fixing F3
 *      (asset-hub hard-coded hive.html) in-place, platform-wide.
 *   2. A breadcrumb: Home > <current page label> (label from document.title),
 *      so a novice always sees where they are + a tap-home escape.
 *   3. Scroll-restore: returning to a list lands where you left it.
 *   4. Deep-link scroll-to-highlight: ?focus=<id> / #<id> scrolls to + pulses the record.
 *
 * Drop nothing per page — nav-hub.js loads this. (Standalone: add
 * <script src="wayfinding.js"></script> before </body>.)
 */
(function () {
  'use strict';
  if (window.__whWayfinding) return;            // idempotent
  window.__whWayfinding = true;

  var path = (location.pathname.split('/').pop() || 'index.html').toLowerCase();
  var IS_HOME = path === '' || path === 'index.html' || location.pathname.endsWith('/');

  // ─── smart BACK target resolution ──────────────────────────────────────────
  // Section-parent map: when there's no usable history, go to the most sensible
  // owning surface rather than dumping the user on a generic page.
  var PARENT = {
    'asset-hub.html': 'hive.html', 'alert-hub.html': 'hive.html', 'pm-scheduler.html': 'hive.html',
    'analytics-report.html': 'analytics.html', 'report-sender.html': 'analytics.html',
    'predictive.html': 'analytics.html', 'ph-intelligence.html': 'analytics.html',
    'project-report.html': 'project-manager.html', 'achievements.html': 'skillmatrix.html',
    'marketplace-seller.html': 'marketplace.html', 'marketplace-seller-profile.html': 'marketplace.html',
    'marketplace-admin.html': 'marketplace.html', 'plant-connections.html': 'integrations.html',
    'audit-log.html': 'hive.html', 'voice-journal.html': 'logbook.html',
  };

  function param(name) { try { return new URLSearchParams(location.search).get(name); } catch (e) { return null; } }
  function sameOrigin(url) { try { return new URL(url, location.href).origin === location.origin; } catch (e) { return false; } }

  function smartBack(e) {
    if (e) { e.preventDefault(); e.stopPropagation(); }
    var from = param('from') || param('return') || param('ref');
    if (from && /^[a-z0-9._-]+\.html$/i.test(from)) { location.href = from; return; }
    // Same-origin referrer → navigate to it EXPLICITLY (deterministic; always lands
    // on the page they came from — unlike history.back(), which can pop a fresh tab's
    // blank entry or a cross-site referrer). scroll-restore + Arc X URL-state rehydrate it.
    var ref = document.referrer;
    if (ref && sameOrigin(ref)) {
      var rp = new URL(ref).pathname;
      if (rp !== location.pathname) { location.href = ref; return; }
    }
    location.href = PARENT[path] || 'index.html';
  }

  // ─── DOM build ───────────────────────────────────────────────────────────────
  function pageLabel() {
    // document.title is "<Page> · WorkHive" / "WorkHive — <Page>" on these pages; take the human part.
    var t = (document.title || '').replace(/\s*[·|—-]\s*WorkHive.*$/i, '').replace(/^WorkHive\s*[·|—-]\s*/i, '').trim();
    return t || 'This page';
  }

  function injectCSS() {
    if (document.getElementById('wh-wayfinding-css')) return;
    var css = document.createElement('style');
    css.id = 'wh-wayfinding-css';
    css.textContent = [
      '#wh-wayfinding{position:fixed;z-index:9000;top:max(10px,env(safe-area-inset-top));left:max(10px,env(safe-area-inset-left));display:flex;align-items:center;gap:8px;pointer-events:none;font-family:inherit}',
      '#wh-wayfinding .wf-back,#wh-wayfinding .wf-crumb{pointer-events:auto;display:inline-flex;align-items:center;min-height:44px;background:rgba(17,24,39,.72);color:#f3f4f6;border:1px solid rgba(255,255,255,.12);border-radius:12px;backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);box-shadow:0 2px 10px rgba(0,0,0,.25)}',
      '#wh-wayfinding .wf-back{min-width:44px;justify-content:center;gap:6px;padding:0 14px 0 10px;font-size:14px;font-weight:600;cursor:pointer;text-decoration:none}',
      '#wh-wayfinding .wf-back:hover{background:rgba(31,41,55,.92)}',
      '#wh-wayfinding .wf-back:active{transform:scale(.96)}',
      '#wh-wayfinding .wf-back svg{flex:0 0 auto}',
      '#wh-wayfinding .wf-crumb{padding:0 12px;font-size:12px;color:#cbd5e1;gap:6px;max-width:52vw;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}',
      '#wh-wayfinding .wf-crumb a{color:#93c5fd;text-decoration:none;font-weight:600}',
      '#wh-wayfinding .wf-crumb .wf-sep{opacity:.5}',
      '@media (max-width:380px){#wh-wayfinding .wf-back span{display:none}#wh-wayfinding .wf-crumb{max-width:44vw}}',
      '@media (prefers-reduced-motion:reduce){#wh-wayfinding .wf-back:active{transform:none}}',
      '.wf-focus-pulse{animation:wfPulse 1.6s ease-out 1}',
      '@keyframes wfPulse{0%{box-shadow:0 0 0 0 rgba(59,130,246,.55)}100%{box-shadow:0 0 0 14px rgba(59,130,246,0)}}',
    ].join('\n');
    (document.head || document.documentElement).appendChild(css);
  }

  var CHEVRON = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>';

  function build() {
    if (IS_HOME) return;                         // home is the root — no back-to-nowhere
    injectCSS();

    // If the page already ships its own top chrome (a .back-btn), it owns the
    // top-left corner — just REWIRE that back to the smart referrer-aware logic
    // (fixes F3: asset-hub's hard-coded hive.html in-place) and DON'T inject our
    // floating pill/breadcrumb on top of it (that caused a header overlap).
    var existing = document.querySelector('.back-btn,[data-wh-back]');
    if (existing) {
      existing.addEventListener('click', smartBack, true);
      if (!existing.getAttribute('aria-label')) existing.setAttribute('aria-label', 'Back');
      return;
    }

    // Bare page: inject the full Back pill + breadcrumb top-left.
    var wrap = document.createElement('div');
    wrap.id = 'wh-wayfinding';

    var back = document.createElement('button');  // a <button>, NOT <a href="#"> — avoids a dead-link (L6)
    back.type = 'button';
    back.className = 'wf-back back-btn';          // back-btn class => harness L5 detector + style hooks
    back.setAttribute('aria-label', 'Back to previous page');
    back.innerHTML = CHEVRON + '<span>Back</span>';
    back.addEventListener('click', smartBack);
    wrap.appendChild(back);

    if (!document.querySelector('.breadcrumb,[aria-label="breadcrumb"],nav.crumbs')) {
      var crumb = document.createElement('nav');
      crumb.className = 'wf-crumb breadcrumb';
      crumb.setAttribute('aria-label', 'breadcrumb');
      crumb.innerHTML = '<a href="index.html">Home</a><span class="wf-sep">›</span><span aria-current="page">' +
        pageLabel().replace(/[<>&]/g, '') + '</span>';
      wrap.appendChild(crumb);
    }

    document.body.appendChild(wrap);
  }

  // ─── scroll-restore (list -> detail -> back lands where you left) ─────────────
  function scrollKey() { return 'wf_scroll_' + path; }
  function saveScroll() { try { sessionStorage.setItem(scrollKey(), String(window.scrollY || 0)); } catch (e) {} /* empty-catch-allow: sessionStorage best-effort (private mode/quota) */ }
  function restoreScroll() {
    try {
      var nav = (performance.getEntriesByType && performance.getEntriesByType('navigation')[0]) || {};
      var isBack = nav.type === 'back_forward';
      var y = parseInt(sessionStorage.getItem(scrollKey()) || '0', 10);
      if (isBack && y > 0) setTimeout(function () { window.scrollTo(0, y); }, 350);
    } catch (e) {}  // empty-catch-allow: sessionStorage/perf API unavailable — restore is best-effort
  }
  window.addEventListener('pagehide', saveScroll);
  window.addEventListener('beforeunload', saveScroll);

  // ─── deep-link scroll-to-highlight (?focus=<id> or #<id>) ─────────────────────
  function focusDeepLink() {
    var id = param('focus') || (location.hash ? location.hash.slice(1) : '');
    if (!id) return;
    var safe = id.replace(/[^a-zA-Z0-9_-]/g, '');
    if (!safe) return;
    setTimeout(function () {
      var el = document.getElementById(safe) || document.querySelector('[data-focus-id="' + safe + '"]');
      if (!el) return;
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.classList.add('wf-focus-pulse');
      setTimeout(function () { el.classList.remove('wf-focus-pulse'); }, 1800);
    }, 600);
  }

  function init() { build(); restoreScroll(); focusDeepLink(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  // expose for pages that want to emit a hand-off link or trigger back programmatically
  window.WHWayfind = { back: smartBack, parentOf: function (p) { return PARENT[p] || 'index.html'; } };
})();
