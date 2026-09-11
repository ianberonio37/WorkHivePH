// wh-consent.js — the analytics consent choice, offered once (T165, 2026-09-07).
//
// This lives in its own file rather than inline in index.html for a reason the CSP ratchet enforces:
// index.html's un-nonced inline <script> count is FROZEN and forward-only, on the way to a strict
// Content-Security-Policy. Adding a fourteenth inline block to ask a privacy question would have
// weakened the security posture in order to improve the privacy posture, which is not a trade worth
// making when an external file costs nothing.
//
// The consent DEFAULT is declared as denied up in <head>, before the gtag config, so nothing is
// collected while this notice waits for an answer. That ordering is the whole point: a banner that
// appears after collection has begun is asking permission for something already done.
(function () {
  var box = document.getElementById('wh-consent');
  if (!box) return;
  // A browser that refuses storage must not be re-asked forever AND must not be measured: the throw
  // lands on "leave it denied and say nothing", which is the quiet, honest side of the failure.
  var stored = null;
  try { stored = localStorage.getItem('wh_analytics_consent'); } catch (e) { return; }
  if (stored === 'granted' || stored === 'denied') return;
  box.hidden = false;
  var answer = function (choice) {
    try { localStorage.setItem('wh_analytics_consent', choice); } catch (e) { void e; }
    if (choice === 'granted' && typeof window.gtag === 'function') {
      window.gtag('consent', 'update', { analytics_storage: 'granted' });
    }
    box.hidden = true;
  };
  var yes = document.getElementById('wh-consent-yes');
  var no = document.getElementById('wh-consent-no');
  if (yes) yes.addEventListener('click', function () { answer('granted'); });
  if (no) no.addEventListener('click', function () { answer('denied'); });
})();
