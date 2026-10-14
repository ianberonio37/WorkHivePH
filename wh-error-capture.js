// capability: report_uncaught_errors
// ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
// wh-error-capture.js - the uncaught-error net for every page that does not load utils.js (SL sub-layer L1, 2026-10-14).
//
// utils.js carries the platform's capture backbone: whLogError() plus the global 'error' / 'unhandledrejection'
// listeners, writing to our own client_errors table. That trail is what told us, on 2026-10-14, why Ian's logbook had
// been dying on his iPhone for a month. But the 119 public pages (every learn guide, every calculator, about / feedback
// / privacy / terms) never load utils.js, and client_errors accepted only signed-in members - so an anonymous visitor's
// error went nowhere, on exactly the pages where a new crew first meets the platform.
//
// This is the same net without utils.js or supabase-js: one fetch to the table's anonymous insert (migration
// 20261014000002, which lets an anonymous row carry ONLY the two uncaught contexts and no hive, name or account).
// It stands down wherever the backbone exists, so a page never reports an error twice.
//
// DIAGNOSTICS ONLY, the backbone's own rules: the message, a truncated stack, the pathname and a coarse user agent -
// never a form value, a row, a token or the query string (it can carry ids). Deduped, at most 20 per page load,
// silent on failure: a logger that throws, blocks or loops would be worse than the dark it replaces.
//
// Loaded, idempotently, by wh-i18n-lite.js (synchronous, in <head>, so it is listening early) and by
// wh-feedback-fab.js (on every public page, and lazy-loaded by nav-hub.js on app pages).
// Gate: error-capture-everywhere (tools/prove_error_capture_everywhere.mjs).
// ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
(function whErrorNet() {
  if (window.__whErrorNet) return;
  window.__whErrorNet = true;
  var BASE = 'https://hzyvnjtisfgbksicrouu.supabase.co';
  var KEY = 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
  var sent = 0, seen = Object.create(null), CAP = 20;

  function report(context, err) {
    try {
      // utils.js's backbone owns a page only where it can SEND: a page that loads utils.js but never builds a client
      // (the design system, the status page) hands its uncaught errors here instead (utils.js whLogError)
      var db = window._whSupabaseClient;
      if (typeof window.whLogError === 'function' && db && typeof db.from === 'function') return;
      if (sent >= CAP) return;                                   // a crash loop must not flood the table
      var msg = '';
      try { msg = String((err && (err.message || err.reason || err)) || ''); } catch (_) { msg = 'unstringifiable error'; }
      if (!msg) return;
      var key = context + '|' + msg.slice(0, 120);
      if (seen[key]) return;                                     // dedupe identical errors per load
      seen[key] = 1;
      sent++;
      var stack = '';
      try { stack = String((err && err.stack) || ''); } catch (_) { /* empty-catch-allow: a stack is optional */ }
      fetch(BASE + '/rest/v1/client_errors', {
        method: 'POST',
        keepalive: true,                                         // survives the page unloading mid-report
        headers: { apikey: KEY, 'Content-Type': 'application/json', Prefer: 'return=minimal' },
        body: JSON.stringify({
          context: context,
          message: msg.slice(0, 2000),
          stack: stack ? stack.slice(0, 4000) : null,
          page: String((location && location.pathname) || '').slice(0, 300),   // pathname ONLY, never the query
          user_agent: String((navigator && navigator.userAgent) || '').slice(0, 300)
        })
      }).then(function () {}, function () {});                    // swallow: never surface a logging failure
    } catch (_) { /* empty-catch-allow: error reporting must never itself throw */ }
  }

  try {
    window.addEventListener('error', function (e) {
      report('uncaught-error', (e && (e.error || e.message)) || e);
    });
    window.addEventListener('unhandledrejection', function (e) {
      report('unhandled-rejection', (e && e.reason) || e);
    });
  } catch (_) { /* empty-catch-allow: a browser without listeners simply keeps the old dark */ }

  // the backbone's hand-off: errors it caught with no client to send through, including the one that loaded this file
  window.__whErrorNetReport = report;
  try {
    var pending = window.__whErrorNetPending || [];
    window.__whErrorNetPending = [];
    for (var i = 0; i < pending.length; i++) report(pending[i][0], pending[i][1]);
  } catch (_) { /* empty-catch-allow: a malformed queue entry must not stop the net */ }
})();
