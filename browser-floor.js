// browser-floor.js — T119 (2026-08-25): the old-browser canary.
//
// The platform's de-facto JS floor is ES2020 (optional chaining `?.` and
// Promise.allSettled are pervasive — 470 uses of `?.` in engineering-design.js
// alone). On an older engine (pre-Chrome-80 WebView, ~2019 budget Androids) the
// page scripts fail to PARSE, so the user got a white page with zero words —
// a total failure discovered only by the person it happens to.
//
// This file is deliberately pure ES5 (it must parse everywhere), detects the
// floor by eval (a parse error in eval throws instead of killing the script),
// and paints a plain-language banner naming the remedy. It never touches
// anything else on a modern browser.
//
// Wiring: <script src="browser-floor.js"></script> EARLY in <head> or first in
// <body>. Rolled out to index first (the entry door); the full-page sweep is a
// wave-close item.
(function () {
  'use strict';
  var ok = true;
  try {
    // ES2020 canary: optional chaining + nullish coalescing.
    // eslint-disable-next-line no-eval
    eval('var _o = {}; var _v = _o?.a ?? 1;');
  } catch (e) { ok = false; }
  if (ok) return;
  function paint() {
    try {
      var d = document.createElement('div');
      d.setAttribute('role', 'alert');
      d.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483647;' +
        'background:#7c2d12;color:#fff;padding:14px 16px;font:14px/1.5 system-ui,Arial,sans-serif;text-align:center;';
      d.innerHTML = 'This browser is too old to run WorkHive (it needs a 2020-or-newer browser engine). ' +
        'Please update Chrome / Android System WebView from the Play Store, or open WorkHive in an updated browser. ' +
        'Masyadong luma ang browser na ito para sa WorkHive - i-update ang Chrome o ang Android System WebView.';
      document.body.insertBefore(d, document.body.firstChild);
    } catch (e2) { /* empty-catch-allow: nothing left to do on an engine this old - the banner itself failed to build */ }
  }
  if (document.body) { paint(); }
  else if (document.addEventListener) { document.addEventListener('DOMContentLoaded', paint, false); }
})();
