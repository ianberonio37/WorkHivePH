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
    try { if (localStorage.getItem(DISMISS_KEY)) return; } catch (e) { /* empty-catch-allow: localStorage blocked (private mode); show the bar */ }

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
        'background:rgba(22,32,50,0.96);border:1px solid rgba(247,162,27,0.35);border-radius:12px;' +
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
        try { localStorage.setItem(DISMISS_KEY, '1'); } catch (e) { /* empty-catch-allow: localStorage blocked; dismissal is best-effort */ }
        bar.remove();
      });

      bar.appendChild(a); bar.appendChild(x);
      (document.body || document.documentElement).appendChild(bar);
    }).catch(function () { /* empty-catch-allow: best-effort; no guide bar if the map cannot load */ });
  } catch (e) { /* empty-catch-allow: never break the host page over an optional guide bar */ }
})();
