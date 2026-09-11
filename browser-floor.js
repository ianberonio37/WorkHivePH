// browser-floor.js — dropped-resource canaries (same-origin script retry + supabase-client-missing).
// NOTE: the original T119 (2026-08-25) eval() "browser too old" canary was REMOVED 2026-09-12 — it was
// incompatible with the strict CSP and false-fired on every browser (see the removal note below).
//
// The platform's de-facto JS floor is ES2020 (optional chaining `?.` and
// Promise.allSettled are pervasive — 470 uses of `?.` in engineering-design.js
// alone). On an older engine (pre-Chrome-80 WebView, ~2019 budget Androids) the
// page scripts fail to PARSE, so the user got a white page with zero words —
// a total failure discovered only by the person it happens to.
//
// i18n-shared-allow: pure ES5 by necessity, so it inlines EN+FIL literally instead of calling the
// platform translator -- the one-line `_tt` arrow helper every other shared component uses would
// itself fail to parse on exactly the engines this file exists to reach, and utils.js (which
// installs window._t) is not guaranteed to have run when the banner paints.
//
// This file is deliberately pure ES5 (it must parse everywhere), detects the
// floor by eval (a parse error in eval throws instead of killing the script),
// and paints a plain-language banner naming the remedy. It never touches
// anything else on a modern browser.
//
// Wiring: <script src="browser-floor.js"></script> EARLY in <head> or first in
// <body>. Rolled out to index first (the entry door); the full-page sweep is a
// wave-close item.
// ★REMOVED 2026-09-12 — the eval() "browser too old" canary was INCOMPATIBLE with the platform's own
// Content-Security-Policy and false-fired on EVERY modern browser.
//   The check detected an old engine by `eval('... ?. ?? ...')` and treated ANY throw as "too old".
//   But the prod CSP is `script-src 'self' 'unsafe-inline' ...` with NO 'unsafe-eval' (vercel.json /
//   _headers), so the browser BLOCKS eval() and it throws on a perfectly current Chrome/Edge/Firefox.
//   The catch could not tell "old engine cannot parse ?." from "CSP forbids eval", so the moment the
//   CSP shipped, the red "This browser is too old to run WorkHive / Masyadong luma ang browser" banner
//   painted at the top of every page for every visitor. A capability probe that needs the one thing the
//   security policy forbids is self-defeating; there is no way to keep it AND the strict CSP.
//   Removed rather than rewritten: a genuinely old engine already fails to PARSE the ES2020 page scripts
//   (a white page), so this banner's real-world reach was marginal, and Ian asked for it gone. If
//   old-browser messaging is wanted later it must use CSP-safe FEATURE detection (e.g. checking
//   Promise.allSettled / Object.fromEntries), never eval. The two canaries below use no eval and stay.

// ─────────────────────────────────────────────────────────────────────────────
// The SECOND canary: the Supabase client never arrived (2026-09-10, W3-JN).
//
// ORIGINALLY: 37 pages loaded the client that does all auth and all data from
// `https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.110.0/...`, which was in NO SHELL_FILES
// entry (there were no cross-origin entries at all) and could never be held by the service worker,
// with no `onerror` on any tag. Lose that one request - a brownout, a blocked CDN, an SRI mismatch,
// a slow link dropping one request in twelve - and every page painted its shell and then threw
// `getDb() called before @supabase/supabase-js loaded` while the person looked at a blank screen.
//
// That single fact sat under three separately-filed findings: W3627 and W3579 ("the cast could not
// sign in", filed as cold-start artifacts), the offline-3g cluster (40% closed against 75-83% for
// every other condition), and the blank hive.html in W3512/W3654.
//
// THE FIX LANDED THE SAME DAY: the client is vendored to the origin
// (`vendor/supabase-js-2.110.0.min.js`, SHA-384-verified byte-identical to what the CDN served) and
// precached in SHELL_FILES, so there is no longer a third-party request in the critical path. Two
// paths needed swapping, not one: 36 static <script> tags, AND five founder-gate pages that
// injected the client from JS at a FLOATING `@2` with no integrity at all - the weaker contract was
// the one a root-only, tag-only sweep could not see. `validate_no_thirdparty_db_client.py` is the
// ratchet that keeps both shapes from coming back.
//
// THIS CANARY STAYS, because the dependency moved rather than vanished: the file can still fail to
// arrive (an evicted cache on a cold load, a bad deploy, a corrupted entry), and the failure looks
// identical to the person. It belongs HERE because this file is precached and pure ES5 - the one
// script guaranteed to be present and parseable at the moment the client is not.
/* ★AND THE CLIENT IS NOT THE ONLY FILE THAT CAN BE DROPPED (2026-09-10, W3-JN). The retry below the
   banner covers supabase-js because that is the file with a canary watching it. The same three
   offline-3g rows show the OTHER half: W3521's `hive -> skillmatrix` and W3618's
   `pm-scheduler -> analytics` reported hub=0 - no nav at all - while the hops on either side kept
   theirs. That is nav-hub.js losing its turn at the 1-in-12 abort, and nothing was watching it, so
   the person was left on a page with no way onward and no explanation.

   A resource error does NOT bubble, so a listener has to be in the CAPTURE phase to see it at all -
   which is also why this belongs in the file that loads first and parses everywhere. Same discipline
   as the client retry: same src, integrity and crossorigin carried across, SAME-ORIGIN only (a
   third-party script that fails is not ours to re-request), and each tag retried at most once - the
   replacement is marked before it is inserted, so if it fails too its own error event is ignored and
   a dropping line can never become a request loop. Late arrival is safe for these files by
   construction: the shell components initialise themselves on DOMContentLoaded or immediately, so a
   second copy that lands after the parser has moved on still paints. */
(function () {
  'use strict';
  if (!window.addEventListener || !document.createElement) return;   // guard on what this IIFE actually uses
  window.addEventListener('error', function (ev) {
    try {
      var t = ev && ev.target;
      if (!t || t.tagName !== 'SCRIPT' || !t.src) return;                 // not a script that failed to load
      if (t.getAttribute('data-wh-retried')) return;                      // already had its second chance
      if (t.src.indexOf(window.location.origin) !== 0) return;            // ours to re-ask for, or nobody's
      t.setAttribute('data-wh-retried', '1');
      var again = document.createElement('script');
      again.setAttribute('data-wh-retried', '1');                         // marked BEFORE insertion: no loop
      again.src = t.src;
      var integ = t.getAttribute('integrity');
      if (integ) again.setAttribute('integrity', integ);                  // the pin survives the retry
      var cross = t.getAttribute('crossorigin');
      if (cross) again.setAttribute('crossorigin', cross);
      if (t.getAttribute('type')) again.setAttribute('type', t.getAttribute('type'));
      (document.head || document.documentElement).appendChild(again);
    } catch (e) { /* empty-catch-allow: a retry that cannot be built must not become a second failure */ }
  }, true);
})();

(function () {
  'use strict';
  if (!document.querySelectorAll || !document.addEventListener) return;   // pre-ES5 DOM: the floor banner above owns that case
  function check() {
    try {
      // Only pages that ASK for the client can be missing it - the public learn/ and tools/ pages
      // legitimately never load it, and warning there would be a false alarm on 114 surfaces.
      var tags = document.querySelectorAll('script[src*="supabase-js"], script[src*="supabase.min.js"]');
      if (!tags.length) return;
      if (window.supabase) return;                                        // it arrived; nothing to say
      if (document.getElementById('wh-client-missing')) return;
      // ★ASK ONCE MORE BEFORE TELLING THE PERSON IT FAILED (2026-09-10, W3-JN). Three journey rows
      // died on this banner - W3559 (J9), W3521 (J25) and W3618 (J22), all on the `offline-3g`
      // condition, which delays every request and ABORTS about one in twelve. On a line like that a
      // file does not fail because it is unavailable; it fails because THAT attempt was the unlucky
      // one, and the very next attempt usually succeeds. The banner was right that the file did not
      // arrive and wrong to treat one drop as the end of the story: a person on a plant floor was
      // told to check their connection and reload the whole page to recover a single request the
      // page could simply ask for again.
      // The retry is deliberately narrow. It re-requests only THIS tag's own src, carries the
      // integrity and crossorigin attributes across so the pin still holds (a retry that drops SRI
      // would be a downgrade dressed as resilience), fires at most once per page, and runs at
      // DOMContentLoaded - after every parser-blocking tag has had its turn - so it cannot reorder
      // anything. If the second attempt also fails, the banner paints exactly as before: this makes
      // the message rarer and truer, never quieter.
      if (!window.__whClientRetried) {
        window.__whClientRetried = 1;
        var orig = tags[0];
        var again = document.createElement('script');
        again.src = orig.src;
        var integ = orig.getAttribute('integrity');
        if (integ) again.setAttribute('integrity', integ);
        var cross = orig.getAttribute('crossorigin');
        if (cross) again.setAttribute('crossorigin', cross);
        again.onload = function () { if (!window.supabase) check(); };    // arrived but still no global: say so
        again.onerror = function () { check(); };                         // genuinely gone: paint the banner
        document.head.appendChild(again);
        return;                                                           // decide after the second answer
      }
      var d = document.createElement('div');
      d.id = 'wh-client-missing';
      d.setAttribute('role', 'alert');
      d.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483646;' +
        'background:#7c2d12;color:#fff;padding:14px 16px;font:14px/1.5 system-ui,Arial,sans-serif;text-align:center;';
      // Says what happened, what it is NOT (their data is safe), and the one action that helps.
      d.innerHTML = 'WorkHive could not finish loading - a file it needs did not arrive. ' +
        'Nothing you have saved is affected. Check your connection and reload the page. ' +
        'Hindi nakumpleto ang pag-load ng WorkHive - may kailangang file na hindi dumating. ' +
        'Ligtas ang lahat ng na-save mo. Tingnan ang koneksyon at i-reload ang page.';
      document.body.insertBefore(d, document.body.firstChild);
    } catch (e) { /* empty-catch-allow: a banner that cannot be built must not become a second failure */ }
  }
  // The CDN tag is parser-blocking (no defer), so by DOMContentLoaded it has either run or failed.
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', check, false); }
  else { check(); }
})();
