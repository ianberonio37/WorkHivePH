/**
// capability: display_wayfinding
 * WorkHive Wayfinding Chrome: Arc Y (THE INTUITION GRADIENT) · Y1
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
    // document.title is "<Page> · WorkHive" / "WorkHive: <Page>" on these pages; take the human part.
    var t = (document.title || '').replace(/\s*[·|—:-]\s*WorkHive.*$/i, '').replace(/^WorkHive\s*[—·|:-]\s*/i, '').trim();   // ':' too - inventory's title is "Spare-Parts Inventory: WorkHive" and the crumb spilled past its box on a phone (2026-09-06)
    return t || 'This page';
  }

  function injectCSS() {
    if (document.getElementById('wh-wayfinding-css')) return;
    var css = document.createElement('style');
    css.id = 'wh-wayfinding-css';
    css.textContent = [
      /* ★DROP BELOW THE OFFLINE BANNER (Wave-4 ratchet, 2026-09-14): the offline banner (offline-banner.js)
         is a full-width fixed strip at top:0 z-index:9999 and covered this z-index:9000 back button whenever
         it showed, so an offline person could not go back. The banner publishes its height as
         --wh-offline-banner-h; add it to this top offset (0 when no banner) and slide, so nothing here is
         ever under the banner. */
      '#wh-wayfinding{position:fixed;z-index:9000;top:max(10px,env(safe-area-inset-top));transform:translateY(var(--wh-offline-banner-h,0px));left:max(10px,env(safe-area-inset-left));display:flex;align-items:center;gap:8px;pointer-events:none;font-family:inherit;transition:transform 0.18s var(--wh-ease-out,cubic-bezier(0.23,1,0.32,1))}',
      /* .72 -> .92: the chip's own translucency was the contrast defect, not the link colour.
         This chrome is fixed over WHATEVER the page puts behind it, and on a light surface
         (analytics-report's white document) rgba(17,24,39,.72) composites to about rgb(84,88,99) —
         so #93c5fd on the crumb link measured 3.89:1 against a 4.5 requirement, and axe flagged it
         as the page's only serious violation. Lightening the link would have fixed this one page and
         left the ratio a function of whatever each of the other 21 pages happens to render
         underneath. At .92 the chip is effectively opaque (about rgb(36,42,58) over white), which
         puts the link at roughly 7.9:1 — AAA — and, more importantly, makes the ratio a property of
         the chrome rather than of the page behind it. The glass look survives: backdrop-filter still
         blurs, and .wf-back:hover already sat at .92, so this is the resting state matching the
         hover state rather than a new value. */
      '#wh-wayfinding .wf-back,#wh-wayfinding .wf-crumb{pointer-events:auto;display:inline-flex;align-items:center;min-height:44px;background:rgba(17,24,39,.92);color:#f3f4f6;border:1px solid rgba(255,255,255,.12);border-radius:12px;backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);box-shadow:0 2px 10px rgba(0,0,0,.25)}',
      '#wh-wayfinding .wf-back{min-width:44px;justify-content:center;gap:6px;padding:0 14px 0 10px;font-size:14px;font-weight:600;cursor:pointer;text-decoration:none}',
      '#wh-wayfinding .wf-back:hover{background:rgba(31,41,55,.92)}',
      '#wh-wayfinding .wf-back:active{transform:scale(.96)}',
      '#wh-wayfinding .wf-back svg{flex:0 0 auto}',
      '#wh-wayfinding .wf-crumb{padding:0 12px;font-size:12px;color:#cbd5e1;gap:6px;max-width:52vw;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}',
      /* Arc U U5: the crumb container is 44px, but the inner <a>Home</a> is measured on
         its OWN box (~33x14) — give the anchor a 44x44 min hit area. justify-center keeps
         the short label centred; the container is already 44px tall so the row is unchanged. */
      '#wh-wayfinding .wf-crumb a{color:#93c5fd;text-decoration:none;font-weight:600;display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px;box-sizing:border-box}',
      '#wh-wayfinding .wf-crumb .wf-sep{opacity:.5}',
      '#wh-wayfinding .wf-crumb [aria-current]{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',   // the current-page span ellipsizes itself: text-overflow on an inline-flex box does not reach a child span (phone fit, 2026-09-06)
      '@media (max-width:380px){#wh-wayfinding .wf-back span{display:none}#wh-wayfinding .wf-crumb{max-width:44vw}}',
      '@media (prefers-reduced-motion:reduce){#wh-wayfinding .wf-back:active{transform:none}}',
      '.wf-focus-pulse{animation:wfPulse 1.6s ease-out 1}',
      '@keyframes wfPulse{0%{box-shadow:0 0 0 0 rgba(59,130,246,.55)}100%{box-shadow:0 0 0 14px rgba(59,130,246,0)}}',
    ].join('\n');
    (document.head || document.documentElement).appendChild(css);
  }

  var CHEVRON = '<span class="ic ic-back" aria-hidden="true"></span>';

  // ─── Skip-link (WCAG 2.4.1 Bypass Blocks, Level A) ───────────────────────────
  // First focusable element on EVERY page (incl. home); visually hidden until a
  // keyboard user tabs to it, then jumps focus past the nav/chrome to <main>. Self-
  // contained inline styles (injectCSS is home-skipped). A bare #hash only scrolls, so
  // we also move real focus into main (tabindex=-1) — the true intent of "skip to content".
  function injectSkipLink() {
    try {
      if (document.querySelector('.wh-skip-link')) return;
      var main = document.querySelector('main, [role="main"], #main-content, #content, #app');
      if (!main) { var h1 = document.querySelector('h1'); main = h1 ? (h1.closest('section,header,div') || h1) : null; }
      if (!main) return;
      if (!main.id) main.id = 'wh-main-content';
      var skip = document.createElement('a');
      skip.className = 'wh-skip-link';
      skip.href = '#' + main.id;
      // ★THE FIRST THING ANNOUNCED ON 21 PAGES WAS THE ONE STRING NOBODY TRANSLATED (walked 2026-09-11,
      // FIL, as Jun Salvador). This file's own comment calls it "the first focusable element on EVERY
      // page" - so for a Filipino keyboard or screen-reader user it is the first control they meet, and
      // wayfinding.js used _t() exactly zero times. No shipped Filipino existed for it either, in any
      // i18n/*.json: the string had never been in scope for the swappers, which is the shared-chrome
      // blind spot again [[feedback_shared_chrome_was_outside_every_i18n_gate]].
      // Read directly from WH_LANG with an English floor rather than calling _t(), because this runs
      // early and must not depend on utils.js having defined the translator yet; and the element
      // declares its own lang when swapped, the same language-of-parts rule as wh-i18n-lite's applier
      // (WCAG 3.1.2 - the whole document's lang is not this file's call to make).
      var _skipFil = 'Laktawan papunta sa main content';   // Taglish, matching WH_FIL_PUBLIC's register
      var _wantFil = false;
      try {
        _wantFil = (window.WH_LANG === 'fil') || (localStorage.getItem('wh_lang') === 'fil');
      } catch (_) { _wantFil = (window.WH_LANG === 'fil'); }
      skip.textContent = _wantFil ? _skipFil : 'Skip to main content';
      if (_wantFil) skip.lang = 'fil';
      skip.style.cssText = 'position:fixed;top:0;left:0;z-index:10001;transform:translateY(-120%);' +
        /* 18px was the only off-grid inset on the first focusable element of every page (design lens craft,
         2026-09-17, W45924). 20px: on the 4px rhythm, and the roomier of the two neighbours for a control
         that only ever appears under keyboard focus. */
        'background:var(--wh-orange, #F7A21B);color:var(--wh-navy, #162032);padding:0 20px;min-height:44px;display:inline-flex;align-items:center;' +
        'font-family:inherit;font-weight:700;font-size:14px;text-decoration:none;border-radius:0 0 10px 0;' +
        // ★THE FIRST FOCUSABLE ELEMENT ON EVERY PAGE MOVED ON THE WRONG CURVE (2026-09-19, W46053
        // motion lens on status.html, where it is the ONLY animated element in the document). `ease` is
        // the CSS default and it is an ease-IN-out: the motion starts slowly. This is the control that
        // drops into view the instant a keyboard user presses Tab on a page they have just opened, so a
        // slow start reads as the page not having responded - the one moment where arriving fast
        // matters most. 150ms was already well under the 300ms ceiling and the property was already
        // transform, compositable and reflowing nothing; only the curve was wrong, which is the defect
        // a declaration cannot show you because there is no wrong value written down.
        'box-shadow:0 4px 16px rgba(0,0,0,.35);transition:transform var(--wh-dur-fast, .15s) var(--wh-ease-out, ease-out);box-sizing:border-box;';
      skip.addEventListener('focus', function () { skip.style.transform = 'translateY(0)'; });
      skip.addEventListener('blur', function () { skip.style.transform = 'translateY(-120%)'; });
      skip.addEventListener('click', function () { main.setAttribute('tabindex', '-1'); main.focus(); });
      document.body.insertBefore(skip, document.body.firstChild);
    } catch (e) { /* empty-catch-allow: progressive enhancement — skip-link is best-effort */ }
  }

  function build() {
    if (IS_HOME) return;                         // home is the root — no back-to-nowhere
    injectCSS();

    // If the page already ships its own top chrome (a .back-btn), it owns the
    // top-left corner — just REWIRE that back to the smart referrer-aware logic
    // (fixes F3: asset-hub's hard-coded hive.html in-place) and DON'T inject our
    // floating pill/breadcrumb on top of it (that caused a header overlap).
    // ★.wh-back-link IS THE SAME CLAIM ON THE SAME CORNER UNDER A DIFFERENT NAME (2026-09-18, W46051
    // audit lens on status.html). The selector listed two spellings of "this page owns its own back
    // control" and the platform has three; status.html ships a .wh-back-link ("← Home") and therefore
    // could not load this file at all without getting a floating pill on top of its own. Which meant it
    // also went without the SKIP LINK this file injects before build() ever runs - so the page a person
    // opens when something is broken was the one page with no way for a keyboard user to jump the
    // header. Measured before adding it: exactly 2 pages carry .wh-back-link and NEITHER loads this
    // file, so the new alternative changes nothing for anything shipping today and simply lets those
    // two adopt the shared chrome instead of cloning it.
    var existing = document.querySelector('.back-btn,.wh-back-link,[data-wh-back]');
    if (existing) {
      existing.addEventListener('click', smartBack, true);
      // ★THIS LINE RENAMED A CONTROL THAT ALREADY HAD A NAME, IN THE WRONG LANGUAGE, AND BROKE LABEL
      // IN NAME DOING IT (2026-09-19, W46052 copy lens on status.html). The page's back control reads
      // "← Home". This gave it aria-label="Back", and an aria-label REPLACES the visible text as the
      // accessible name - so a screen reader announced "Back", a Filipino reader heard an English word
      // on a page whose other controls had all been translated, and anyone driving by voice who said
      // "click Home" was talking about a control the machine now called something else (WCAG 2.5.3:
      // the accessible name must CONTAIN the visible label). The label was written for an ICON-only
      // back button, where there is no visible text to preserve and a name is genuinely missing. It
      // now applies only in that case - measured by the control's own visible text - and when it does
      // apply it speaks the reader's language, read straight from WH_LANG like the skip link above,
      // because this file runs before utils.js may have defined the translator.
      // "Has visible text" means WORDS, not marks: a control reading only "←" or "⟵" has a glyph and
      // no name, and leaving it unlabelled would announce as the arrow character - which is how the
      // aria-label-only anti-pattern gets fixed into a different broken name. So the test asks for a
      // letter or a digit, and an arrow-only button still gets the label it needs.
      if (!existing.getAttribute('aria-label') && !/[\p{L}\p{N}]/u.test(existing.textContent || '')) {
        var _backFil = 'Bumalik';
        var _bWantFil = false;
        try {
          _bWantFil = (window.WH_LANG === 'fil') || (localStorage.getItem('wh_lang') === 'fil');
        } catch (_) { _bWantFil = (window.WH_LANG === 'fil'); }
        existing.setAttribute('aria-label', _bWantFil ? _backFil : 'Back');
        // No per-element lang here, unlike the skip link above, and the difference is measured rather
        // than assumed: the skip link is injected before utils.js has set the document's language, so
        // it can be the one Filipino string in an English document and must declare itself. This
        // control is labelled from build(), by which time document.documentElement.lang already reads
        // "fil" (measured on asset-hub), so an element-level lang would restate what the document
        // already says. A first draft did set it; it was removed after the probe read the attribute
        // back as null - shipping a line that does nothing is the same defect as the dead palette this
        // row's page just lost.
      }
      return;
    }
    // ★I1/CLS + dedup: the page ALSO owns its top-left corner (so a floating pill would DUPLICATE
    // the back affordance the whole-artifact discipline bans, AND the reserve-band below would push
    // the whole page down 64px AFTER first paint = a 0.12-0.28 layout shift, which failed I1 on
    // community/marketplace-seller/marketplace-seller-profile) when it already ships a recognized
    // in-layout back/home link. Skip the pill entirely — but ONLY for affordances the W1 rubric also
    // credits by class (back-link/home-link/breadcrumb), so we never suppress the pill on a page that
    // has no real way back (a bare fixed nav does NOT count — that regressed public-feed W1 to 0).
    if (document.querySelector('.back-link,.home-link,.breadcrumb,[aria-label="breadcrumb"]')) return;

    // Bare page: inject the full Back pill + breadcrumb top-left.
    var wrap = document.createElement('div');
    wrap.id = 'wh-wayfinding';

    var back = document.createElement('button');  // a <button>, NOT <a href="#"> — avoids a dead-link (L6)
    back.type = 'button';
    back.className = 'wf-back back-btn';          // back-btn class => harness L5 detector + style hooks
    back.setAttribute('aria-label', (typeof window._t === 'function') ? window._t('Back to previous page', 'Bumalik sa nakaraang page') : 'Back to previous page');   // the pill speaks the page's language (copy lens, 2026-09-15)
    /* ★AND ITS VISIBLE WORD STAYED ENGLISH (design lens copy on dayplanner, 2026-09-15). The line above
       translates the accessible NAME; this one drew the word a sighted reader actually sees, and it read
       "Back" on every page in both languages. The platform's own lesson, inverted. */
    back.innerHTML = CHEVRON + '<span>'
      + ((typeof window._t === 'function') ? window._t('Back', 'Bumalik') : 'Back') + '</span>';
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

    // ★V1 (Ian's screenshot: the breadcrumb COVERED the dayplanner header title). The pill is
    // position:fixed, so it floats ON TOP of the page's in-flow header. RESERVE a top band by pushing
    // the page's in-flow content down by the pill's height + a gap, so the header sits BELOW it instead
    // of behind it. Fixed elements ignore body padding, so the pill stays put while content shifts.
    // Reserve the band so the fixed pill doesn't cover the page header. A page can PRE-reserve this
    // statically (body padding-top / a scroll-margin band) to avoid the post-paint shift entirely — this
    // check skips when the page already reserves >= the band (that is how the I1 CLS on dayplanner/
    // alert-hub is fixed: they ship a static top reserve, so this never fires).
    requestAnimationFrame(function () {
      var band = Math.ceil(wrap.getBoundingClientRect().bottom) + 8;
      var cur = parseFloat(getComputedStyle(document.body).paddingTop) || 0;
      if (band > cur) document.body.style.paddingTop = band + 'px';
    });
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

  function init() { injectSkipLink(); build(); restoreScroll(); focusDeepLink(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  // expose for pages that want to emit a hand-off link or trigger back programmatically
  window.WHWayfind = { back: smartBack, parentOf: function (p) { return PARENT[p] || 'index.html'; } };
})();
