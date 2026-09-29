// offline-banner.js — shared offline / online banner.
// capability: display_offline_banner
//
// Renders a small fixed banner at the top of the page when the device
// loses network. Closes PRODUCTION_FIXES #54 (per-page offline-event
// adoption). Pages just include the script; no per-page wiring needed.
//
// Behaviour:
//   * Uses navigator.onLine + window addEventListener('offline'|'online')
//   * Banner: red bar "You are offline. Some actions may not work." when offline
//   * Banner: green bar "Back online" for 2s when reconnecting, then hides
//   * Injects its own DOM + CSS once on first run; no styling required from page
//
// The banner is rendered into <body> at z-index 9999 so it sits above
// modals + drawers. CSS uses inline styles to avoid clashing with page
// stylesheets.

(function () {
  'use strict';

  /* W3-SC (2026-09-09): losing the network is the moment a plant-floor worker most needs to read the
     message, and this banner reaches more pages (35) than any other shared surface. It spoke only
     English. window._t(en, fil) is the platform locale floor utils.js installs; resolved at CALL time
     because the banner paints on a network event, long after a page with its own engine has defined
     its richer _t. Falls back to EN, so a page without the floor still gets a sentence, never a blank. */
  const _tt = (en, fil) =>
    (typeof window !== 'undefined' && typeof window._t === 'function') ? window._t(en, fil) : en;

  if (typeof window === 'undefined' || typeof document === 'undefined') return;
  if (window.__whOfflineBannerLoaded) return;
  window.__whOfflineBannerLoaded = true;

  const STYLE = `
    .wh-offline-banner {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      padding: 0.55rem 0.85rem;
      font-size: 0.85rem;
      font-weight: 600;
      text-align: center;
      color: #fff;
      z-index: 9999;
      transform: translateY(-100%);
      transition: transform 0.18s ease-out;
      pointer-events: auto;
      box-shadow: 0 2px 10px rgba(0,0,0,0.18);
    }
    .wh-offline-banner.show { transform: translateY(0); }
    .wh-offline-banner.offline { background: #c53030; }
    .wh-offline-banner.online  { background: #2f855a; }
    /* ★AND PUSH THE PAGE'S OWN TOP CONTENT DOWN, not only the wayfinding chrome (2026-09-14). The var
       --wh-offline-banner-h offsets the fixed wayfinding pill; an IN-FLOW top control (hive's own "Back"
       link at the very top) still sat under the banner. While the banner is up, the body drops by the
       banner's height so nothing at the top is covered - a margin (not padding) so a page's own top
       padding is preserved, and fixed elements (the FAB stack) are unaffected. A margin, and a transition,
       so it slides with the banner rather than jumping. */
    html.wh-offline-banner-open body { margin-top: var(--wh-offline-banner-h, 0px); }
    body { transition: margin-top 0.18s ease-out; }
    /* ★AND DROP THE PAGE'S OWN FIXED TOP NAV TOO (W41399, wave-4 ratchet on hive.html, 2026-09-14). A body
       margin moves in-flow content, but a page's <nav class="fixed top-0"> (hive, and every page built on the
       same Tailwind header) is position:fixed and does not move - so its Back link / logo / bell still sat UNDER
       the banner (elementFromPoint at hive's "Back" @20,6 returned .wh-offline-banner). Same fix wayfinding.js got
       in v385: while the banner is up, a fixed top nav/header drops by the banner's height. Specificity
       (html.class nav.class) beats Tailwind's .top-0, and the transition matches the banner's slide. */
    html.wh-offline-banner-open nav.fixed,
    html.wh-offline-banner-open header.fixed { top: var(--wh-offline-banner-h, 0px); transition: top 0.18s ease-out; }
  `;

  function inject() {
    const style = document.createElement('style');
    style.textContent = STYLE;
    document.head.appendChild(style);

    const banner = document.createElement('div');
    banner.className = 'wh-offline-banner';
    banner.setAttribute('role', 'alert');
    banner.setAttribute('aria-live', 'polite');
    banner.setAttribute('data-offline', '1');
    document.body.appendChild(banner);

    return banner;
  }

  let banner = null;
  let onlineTimer = null;

  // ★THE BANNER COVERED THE BACK BUTTON (Wave-4 nav-hub ratchet, 2026-09-14). This full-width strip is
  // position:fixed top:0 z-index:9999; the wayfinding back button (#wh-wayfinding .wf-back) is fixed top:10
  // left:10 z-index:9000 - so whenever the banner shows, it sits ON the back button (measured on ai-quality,
  // alert-hub and every host: elementFromPoint at the back button's centre returned .wh-offline-banner), and
  // an offline person cannot go back. The banner publishes its height as --wh-offline-banner-h on the root;
  // the top-anchored chrome (wayfinding) drops below it by that much, so nothing at the top is covered.
  function _publishHeight() {
    try {
      var shown = !!(banner && banner.classList.contains('show'));
      var h = shown ? Math.round(banner.getBoundingClientRect().height) : 0;
      document.documentElement.style.setProperty('--wh-offline-banner-h', h + 'px');
      document.documentElement.classList.toggle('wh-offline-banner-open', shown);
    } catch (_) { /* empty-catch-allow: the offset is best-effort */ }
  }

  function show(kind, text) {
    if (!banner) banner = inject();
    banner.classList.remove('offline', 'online');
    banner.classList.add(kind);
    banner.textContent = text;
    requestAnimationFrame(() => { banner.classList.add('show'); requestAnimationFrame(_publishHeight); });
  }

  function hide() {
    if (!banner) return;
    banner.classList.remove('show');
    _publishHeight();
  }

  function onOffline() {
    if (onlineTimer) { clearTimeout(onlineTimer); onlineTimer = null; }
    show('offline', _tt('You are offline. Some actions may not work.',
                        'Offline ka ngayon. May mga bagay na hindi gagana.'));
  }

  function onOnline() {
    show('online', _tt('Back online.', 'Online ka na ulit.'));
    onlineTimer = setTimeout(hide, 2000);
  }

  // Initial state
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initOnce);
  } else {
    initOnce();
  }

  function initOnce() {
    if (!navigator.onLine) onOffline();
    window.addEventListener('offline', onOffline);
    window.addEventListener('online',  onOnline);
  }
})();
