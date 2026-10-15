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
    /* ★A THIRD KIND: SLOW, WHICH IS NOT OFFLINE AND MUST NOT LOOK LIKE IT (2026-10-05). Measured by walking
       LXP195 through the chrome-devtools MCP with PostgREST genuinely stopped: the page showed "Loading…" with
       no failure language for ~42 SECONDS before it could say anything. The cause is not the page - its error
       path fires the instant an error arrives - it is that the gateway takes 41.8s to give up (measured: Kong
       connects in 0.02s, returns 500 at 41.8s) and utils.js's platform-wide transport timeout is 45s. That 45s
       is deliberate and must NOT be lowered: its own comment explains it "leaves legit slow ops (2G upload, big
       RPC) room to finish", and 2G is exactly who this platform is for.
       So the fix separates INFORMING from ABORTING: the read keeps its full budget, and after a few seconds the
       person is simply told the connection is slow. Amber, not the offline red - this is a wait, not a failure,
       and dressing a wait as a failure teaches people to ignore the red one. Navy text because amber at this
       weight needs a dark foreground to clear 4.5:1 (#fff on #D97706 is 2.8:1 and would have been a contrast
       regression on a strip that exists to be read). */
    .wh-offline-banner.slow    { background: #D97706; color: #1A202C; }
    /* ★AND PUSH THE PAGE'S OWN TOP CONTENT DOWN, not only the wayfinding chrome (2026-09-14). The var
       --wh-offline-banner-h offsets the fixed wayfinding pill; an IN-FLOW top control (hive's own "Back"
       link at the very top) still sat under the banner. While the banner is up, the body drops by the
       banner's height so nothing at the top is covered - a margin (not padding) so a page's own top
       padding is preserved, and fixed elements (the FAB stack) are unaffected.
       ★THE MARGIN MOVES IN ONE STEP; ONLY THE BANNER SLIDES (K, 2026-10-15). Transitioning margin-top re-laid out
       the whole page on every frame of the slide - on the low-end phones this banner exists for - and a transform
       on <body> is not a substitute: it makes the body the containing block of every position:fixed element under
       it (the FAB stack, the toasts, this banner). The banner's own transform slide carries the motion into the
       space the content has already given it. */
    html.wh-offline-banner-open body { margin-top: var(--wh-offline-banner-h, 0px); }
    @media (prefers-reduced-motion: reduce) { .wh-offline-banner { transition: none; } }
    /* ★AND DROP THE PAGE'S OWN FIXED TOP NAV TOO (W41399, wave-4 ratchet on hive.html, 2026-09-14). A body
       margin moves in-flow content, but a page's <nav class="fixed top-0"> (hive, and every page built on the
       same Tailwind header) is position:fixed and does not move - so its Back link / logo / bell still sat UNDER
       the banner (elementFromPoint at hive's "Back" @20,6 returned .wh-offline-banner). Same fix wayfinding.js got
       in v385: while the banner is up, a fixed top nav/header drops by the banner's height. Specificity
       (html.class nav.class) beats Tailwind's .top-0. It moves in the same single step as the body (a transition
       on top is a layout animation too). NO BACKTICKS in this sheet: it is a JS template literal. */
    html.wh-offline-banner-open nav.fixed,
    html.wh-offline-banner-open header.fixed { top: var(--wh-offline-banner-h, 0px); }
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

  /* ★HIDDEN FOR THE EYE, STILL READ ALOUD (2026-10-06, achievements x assistive-tech, PostgREST stopped). hide() only
     slid the banner off-screen (translateY to y=-58): it stayed display:block, visible, role=alert, with its last
     sentence inside - so a screen-reader user moving through the page met "Still loading..." or "You are offline"
     that no sighted person could see. The same lesson as a closed sheet left in layout. hide() now takes it out of
     the accessibility tree and show() puts it back.
     ★AND THE KINDS MUST NOT STACK. show() cleared 'offline'/'online' but never 'slow', so a slow hint followed by
     going offline left class="slow offline" - and whSlowRead.clear(), which hides whenever 'slow' is present, would
     then hide the OFFLINE banner when the reads settled. Every kind is cleared before the new one is set. */
  function show(kind, text) {
    if (!banner) banner = inject();
    banner.classList.remove('offline', 'online', 'slow');
    banner.classList.add(kind);
    banner.textContent = text;
    banner.removeAttribute('aria-hidden');
    requestAnimationFrame(() => { banner.classList.add('show'); requestAnimationFrame(_publishHeight); });
  }

  function hide() {
    if (!banner) return;
    banner.classList.remove('show');
    banner.setAttribute('aria-hidden', 'true');
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

  // ★THE SLOW-READ HOOK, EXPOSED SO utils.js CAN DRIVE IT FROM THE ONE PLACE EVERY READ PASSES (2026-10-05).
  // utils.js wraps the supabase client's transport for every db.from()/rpc()/auth/storage call and already
  // owns the 45s timeout; this lets that same wrapper say "it is slow" without touching 26 pages, which is the
  // argument its own comment makes for living there ("no page reinvents it").
  //
  // ★WHAT THIS IS NOT, stated because this file's history is exactly that mistake: it is a PASSIVE NOTICE and
  // it does NOT gate anything. Two gates once proved the offline banner was adopted on every page while 14 of
  // 17 user-triggered WRITES fired into a dead network - a passive warning does not stop a button
  // ([[feedback_banner_adoption_is_not_write_refusal]]). Guarding a write is whRequireOnline's job and remains
  // so. This only answers "why has this been spinning for ten seconds", which is a READ, already handled
  // correctly, whose only defect was silence.
  //
  // never shown when the device is simply offline - that banner is more specific and already up.
  window.whSlowRead = {
    show: function () {
      try {
        if (!navigator.onLine) return;
        if (banner && banner.classList.contains('offline')) return;
        // ★AND IT YIELDS TO THE MORE SPECIFIC NOTICE, the way it yields to the offline banner (2026-10-06, achievements
        // x assistive-tech, PostgREST stopped). After the page's own read failed, shared chrome kept issuing
        // background reads (companion follow-ups, the Community unread count, identity) that stayed in flight to
        // ~94s - so "Still loading ... Nothing is lost" stood beside "Couldn't load your achievements - Try again":
        // wait, or retry? Once utils.js has said the server could not be reached (#wh-connection-notice - removed when
        // the service that failed answers again, or after its 30s lifetime), a generic wait hint only contradicts it.
        if (document.getElementById('wh-connection-notice')) return;
        // ★IT NEVER KNEW THE CONNECTION WAS SLOW (2026-10-06). This notice only shows while navigator.onLine is TRUE
        // (the guard above), so "the connection is slow" was a cause the code never measured - and on the walk that
        // found this, the network was fine and a server function was the slow part. It now says only what it knows.
        show('slow', _tt('Still loading - this is taking longer than usual. Nothing is lost.',
                         'Naglo-load pa - mas matagal kaysa karaniwan. Walang nawawala.'));
      } catch (_) { /* empty-catch-allow: a hint must never break the read it is describing */ }
    },
    clear: function () {
      try {
        if (banner && banner.classList.contains('slow')) hide();
      } catch (_) { /* empty-catch-allow */ }
    }
  };
})();
