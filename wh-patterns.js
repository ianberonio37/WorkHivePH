/**
 * wh-patterns.js — centralized BEHAVIOURAL idioms (PLATFORM_CENTRALIZATION_ROADMAP · Axis 3).
 * ─────────────────────────────────────────────────────────────────────────────
 * The FAB-consolidation session hand-rolled the same four interaction idioms across
 * nav-hub / companion / feedback / connectivity. A behaviour written twice is ONE
 * unadopted pattern (the METHOD LAW applied to behaviour, not just CSS). These are the
 * canonical helpers; the shared chrome delegates to them so the idiom lives in ONE place.
 *
 * Loaded early (sync) by nav-hub.js so window.WHPatterns is present platform-wide before
 * any chrome wires its events. Defensive throughout — never throws into a caller.
 *
 * GOV.UK "when to use / when NOT" contract per helper below.
 */
(function () {
  'use strict';
  if (typeof window === 'undefined' || window.WHPatterns) return;

  var WHPatterns = {
    /**
     * launchPanel(e, openFn, opts) — open ANOTHER panel from a click without that same
     * click bubbling into the target panel's own click-outside-to-close handler.
     * WHEN: a menu row / button that opens a separate overlay (hub → companion/feedback).
     * WHEN NOT: opening a panel this element already lives inside (no cross-panel race).
     * How: stopPropagation (the click never reaches other document handlers) + a one-tick
     * defer (the current click fully finishes dispatching before the target appears).
     */
    launchPanel: function (e, openFn, opts) {
      try { if (e && typeof e.stopPropagation === 'function') e.stopPropagation(); } catch (_) { /* empty-catch-allow: best-effort */ }
      if (opts && typeof opts.before === 'function') { try { opts.before(); } catch (_) { /* empty-catch-allow */ } }
      setTimeout(function () { try { if (typeof openFn === 'function') openFn(); } catch (_) { /* empty-catch-allow */ } }, 0);
    },

    /**
     * clickOutside(el, closeFn, opts) — call closeFn when a click lands OUTSIDE `el`
     * (and outside any opts.except[] elements), gated by opts.isOpen so it no-ops while closed.
     * Returns a disposer that removes the listener.
     * WHEN: any dismissible popover/menu/panel. WHEN NOT: a modal with its own backdrop.
     */
    clickOutside: function (el, closeFn, opts) {
      opts = opts || {};
      var isOpen = typeof opts.isOpen === 'function' ? opts.isOpen : function () { return true; };
      var except = opts.except || [];
      // exceptSelector is resolved at CLICK time (via closest) — use it for an "except"
      // element that mounts AFTER this handler is wired (e.g. an async-loaded widget).
      var exceptSel = opts.exceptSelector || null;
      function onDoc(e) {
        try {
          if (!isOpen()) return;
          if (el && el.contains(e.target)) return;
          if (exceptSel && e.target && e.target.closest && e.target.closest(exceptSel)) return;
          for (var i = 0; i < except.length; i++) {
            var ex = except[i];
            if (ex && ex.contains && ex.contains(e.target)) return;
          }
          if (typeof closeFn === 'function') closeFn(e);
        } catch (_) { /* empty-catch-allow: dismiss is best-effort */ }
      }
      document.addEventListener('click', onDoc);
      return function () { document.removeEventListener('click', onDoc); };
    },

    /**
     * revealVia(bodyClass, on) — a widget reveals/tucks ITSELF via its OWN body class
     * (toggled in its open/close), independent of any OTHER widget's open state.
     * WHEN: a launcher-driven widget (companion). WHEN NOT: a widget that should mirror
     * another's state on purpose. Root fix for the "piggyback on another widget's reveal"
     * collision that started the FAB consolidation (companion rode body.wh-hub-open).
     */
    revealVia: function (bodyClass, on) {
      try { document.body.classList[on ? 'add' : 'remove'](bodyClass); } catch (_) { /* empty-catch-allow */ }
    },

    /**
     * capPanel(el) — cap a bottom-anchored panel to the viewport + scroll, so a top
     * header/action row is never clipped off-screen (the panel grows upward from a FAB).
     * The CSS token --wh-panel-max-h is the DECLARATIVE form; use this for panels sized
     * dynamically in JS. WHEN: a corner panel taller than a short viewport.
     */
    capPanel: function (el) {
      if (!el) return;
      try {
        el.style.maxHeight = 'var(--wh-panel-max-h, calc(100dvh - 100px))';
        el.style.overflowY = 'auto';
        el.style.overscrollBehavior = 'contain';
      } catch (_) { /* empty-catch-allow */ }
    }
  };

  window.WHPatterns = WHPatterns;
})();
