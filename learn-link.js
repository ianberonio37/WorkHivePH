/* learn-link.js — connects a feature PAGE back to its /learn/ GUIDE.
 *
 * Ian (2026-07-07): "my feature pages and landing page are complete strangers."
 * Every tool page now offers a one-tap link to the in-depth guide about it, so a
 * worker on logbook.html can jump straight to "How to start a digital logbook",
 * and the landing / learn hub / feature pages form one connected library.
 *
 * Data source: /learn_links.json (generated from wh_pages.LEARN_ARTICLES:
 * { "<page>.html": [ {slug, title}, ... ] }). Defensive + dependency-free:
 * fixed bottom-LEFT pill (clear of the bottom-right companion/feedback FABs),
 * dismissible per page (remembered in localStorage), no-op if no guide exists. */
(function () {
  try {
    var page = (location.pathname.split('/').pop() || 'index.html').toLowerCase();
    if (page.indexOf('.html') === -1) page = 'index.html';
    // Never show it on the learn hub or inside an article (already in the library).
    if (location.pathname.indexOf('/learn/') !== -1) return;
    var DISMISS_KEY = 'wh_guide_link_dismissed_' + page;
    /* T121 (2026-08-28): owner-stamped. This chip rides EVERY page, so an unowned flag was the
       widest of the three dismissal leaks - a worker who dismissed the guide on eight pages left
       the next person on that station tablet with no page-guide affordance anywhere, and nothing
       on screen to explain why. whIsDismissed treats a legacy '1' as not-dismissed, so the chip
       returns once per page for its rightful owner too. */
    try {
      if (typeof whIsDismissed === 'function') { if (whIsDismissed(DISMISS_KEY)) return; }
      else if (localStorage.getItem(DISMISS_KEY)) return;
    } catch (e) { /* empty-catch-allow: localStorage blocked (private mode); show the bar */ }

    fetch('/learn_links.json').then(function (r) { return r.json(); }).then(function (map) {
      var guides = map && map[page];
      if (!guides || !guides.length) return;
      var g = guides[0];
      var title = g.title.length > 44 ? g.title.slice(0, 42) + '…' : g.title;

      var bar = document.createElement('div');
      bar.id = 'wh-guide-link';
      // a11y: this floating helper is a top-level body child; give it a landmark so all its
      // content sits inside a region (axe 'region' rule, WCAG 1.3.1 / best practice).
      bar.setAttribute('role', 'complementary');
      bar.setAttribute('aria-label', 'Page guide');
      bar.style.cssText =
        /* ★V1: bottom:84px put this onboarding pill ON TOP of bottom-left page FABs (at ~68-120px) —
           V1 caught pm-scheduler fab × wh-guide-link. Raise it clear of the page-FAB zone (Ian: colliding widgets). */
        'position:fixed;left:12px;bottom:calc(132px + env(safe-area-inset-bottom,0px));z-index:60;' +
        'max-width:min(320px,calc(100vw - 24px));display:flex;align-items:center;gap:8px;' +
        // OPAQUE, so this chip's contrast is a property of the chip and not of whatever scrolled under
        // it. At 0.96 alpha the three labels here measure 5.06:1, 7.89:1 and 6.67:1 against the
        // composited chip, so nothing was FAILING - but axe abstained on all three, on every page,
        // because the element is position:fixed and a fixed element's true backdrop is whatever the
        // page happens to have scrolled beneath it, which no static tool can resolve. Those
        // abstentions were the last nodes on five walked pages judged by NEITHER axe nor the APCA lens
        // (which excludes shared chrome by design), so they were the residue blocking contrast_wcag
        // from being fully dispositioned. 0.96 -> 1 is imperceptible (it removes a 4% bleed-through)
        // and converts an unjudgeable node into a judgeable one. Same reasoning as wayfinding.js's
        // crumb chip this session, where the translucency was the actual defect at 3.89:1.
        // var(--wh-navy), not the raw rgb(22,32,50) it was: that value IS the canonical brand navy
        // token (tokens.css:56), and the centralization roadmap counts this file's one raw literal in
        // its purity table. Using the token makes the fix satisfy both rules at once instead of trading
        // one debt for another. The fallback keeps the chip opaque if the sheet ever fails to load.
        'background:var(--wh-navy,#162032);border:1px solid rgba(247,162,27,0.35);border-radius:12px;' +
        'padding:9px 10px 9px 12px;box-shadow:0 8px 24px rgba(0,0,0,0.35);' +
        'font:600 0.78rem/1.25 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;';
      var a = document.createElement('a');
      a.href = '/learn/' + g.slug + '/';
      // min-height 44 = the tap-target floor (F1). The two stacked caption lines
      // only measured 29px tall, so the whole guide link was under-size on every
      // page that renders it.
      a.style.cssText = 'display:flex;align-items:center;gap:8px;color:var(--wh-orange, #F7A21B);text-decoration:none;flex:1;min-width:0;min-height:44px;';
      a.innerHTML = '<span aria-hidden="true" style="font-size:1rem;">📖</span>' +
        '<span style="min-width:0;"><span style="display:block;color:rgba(255,255,255,0.5);font-weight:500;font-size:0.68rem;">New to this page?</span>' +
        '<span style="display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">Read the guide</span></span>';
      a.setAttribute('aria-label', 'Read the guide: ' + g.title);
      a.title = g.title;

      var x = document.createElement('button');
      x.type = 'button';
      x.setAttribute('aria-label', 'Dismiss guide link');
      x.textContent = '×';
      // 44x44 is the tap-target floor (F1) -- this dismiss button was 28x28, and F1
      // fails on the MIN dimension, so both axes must clear it.
      x.style.cssText = 'flex:0 0 auto;display:flex;align-items:center;justify-content:center;background:none;border:none;color:rgba(255,255,255,0.6);font-size:1.1rem;line-height:1;cursor:pointer;padding:4px;min-width:44px;min-height:44px;';
      x.addEventListener('click', function () {
        try {
          if (typeof whSetDismissed === 'function') whSetDismissed(DISMISS_KEY);
          else localStorage.setItem(DISMISS_KEY, '1');
        } catch (e) { /* empty-catch-allow: localStorage blocked; dismissal is best-effort */ }
        bar.remove();
      });

      bar.appendChild(a); bar.appendChild(x);
      (document.body || document.documentElement).appendChild(bar);

      /* ★A FLOATING HELPER MUST NOT INTERCEPT A DIALOG'S OWN BUTTONS.
         The V1 fix above moved this chip clear of the bottom-left page FABs by raising it to bottom:132px
         — which put it squarely over the ACTION ROW of every modal on the platform. Measured on
         pm-scheduler at 390x844: #pm-edit-save-btn ("Save Changes") centres at (95, 606); this chip
         occupies x 12-207, y 583-647; document.elementFromPoint(95, 606) returned a <span> inside
         #wh-guide-link, NOT the button. #pm-edit-modal and this chip are BOTH z-index 60, and equal
         z-index resolves by DOM order — the chip is appended last, so it wins. A supervisor could not
         save a PM asset edit at all, and the modal's own inputs tested fine, so nothing about the
         dialog looked broken.
         Raising the modals instead would be a third round of the same nudge (Ian: colliding widgets),
         and it would only hold until the next widget. The rule is behavioural: while a dialog is up,
         a page-level guide is irrelevant, so it stands down entirely — no tap interception, no focus
         stop inside a modal's trap, no contrast question over a backdrop. It returns when the dialog
         closes. Cheap: attribute-only observer, one rAF-debounced check, and it disconnects itself if
         the chip is dismissed (dismissal calls bar.remove()). */
      (function standDownWhileDialogOpen() {
        // Kept identical to nav-hub.js's list on purpose: two copies of one rule that drift are how a
        // component gets fixed on one surface and stays broken on the next. .sheet-overlay.open is
        // community's convention and was missing here.
        var DIALOGISH = '[role="dialog"],dialog[open],.sheet.open,.modal.open,[id$="-sheet"].open,'
          + '[id$="-modal"].open,.sheet-overlay.open';
        var shown = true, queued = false;
        function visible(el) {
          var cs = getComputedStyle(el);
          // NOT opacity: a dialog mid-fade reports opacity 0 on the first frame after its class flips,
          // and with no further mutation to re-trigger the check the chrome stays up for the dialog's
          // whole life. Found on nav-hub.js's copy of this rule; fixed here too so the two cannot drift.
          if (cs.display === 'none' || cs.visibility === 'hidden') return false;
          var r = el.getBoundingClientRect();
          return r.width > 0 && r.height > 0;
        }
        function sync() {
          queued = false;
          if (!bar.isConnected) { obs.disconnect(); return; }   /* dismissed: stand down for good */
          var open = false, all = document.querySelectorAll(DIALOGISH);
          for (var i = 0; i < all.length; i++) { if (visible(all[i])) { open = true; break; } }
          if (open === !shown) return;                          /* already in the right state */
          shown = !open;
          bar.style.display = open ? 'none' : 'flex';
        }
        function schedule() { if (!queued) { queued = true; requestAnimationFrame(sync); } }
        document.addEventListener('transitionend', schedule, true);
        var obs = new MutationObserver(schedule);
        obs.observe(document.documentElement, { attributes: true, subtree: true,
          attributeFilter: ['style', 'class', 'open', 'aria-hidden', 'hidden'] });
        sync();
      })();
    }).catch(function () { /* empty-catch-allow: best-effort; no guide bar if the map cannot load */ });
  } catch (e) { /* empty-catch-allow: never break the host page over an optional guide bar */ }
})();
