// offline-banner.js — shared offline / online banner.
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

  function show(kind, text) {
    if (!banner) banner = inject();
    banner.classList.remove('offline', 'online');
    banner.classList.add(kind);
    banner.textContent = text;
    requestAnimationFrame(() => banner.classList.add('show'));
  }

  function hide() {
    if (!banner) return;
    banner.classList.remove('show');
  }

  function onOffline() {
    if (onlineTimer) { clearTimeout(onlineTimer); onlineTimer = null; }
    show('offline', 'You are offline. Some actions may not work.');
  }

  function onOnline() {
    show('online', 'Back online.');
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
