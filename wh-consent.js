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
  // ★AT NARROW WIDTHS THE CARD MUST NOT COVER A CONTROL (C13, wave-4 narrow-320 nav-hub walk, 2026-09-14). As a
  // fixed bottom card (left/right 1rem, bottom 1rem) it grew to ~212px at 320 CSS px and sat ON the sign-in wall's
  // "Forgot your password?", "Create one for free", the SSO button and the whole bottom band where the hub FAB
  // lives - so a NEW person on a narrow phone (exactly who meets this card) could not recover a password, create an
  // account or open the nav until they found these buttons under everything else. Below 360px the card REFLOWS
  // INTO THE PAGE: position static at the top of <main> (under the fixed nav's own padding), pushing content down
  // and covering nothing - the "chrome makes room" rule the page-guide chip (C9) and the offline banner (C10-C12)
  // now follow. At 361px+ the bottom card fits beside these controls and is left exactly as designed. When the
  // sign-in modal is up it sits behind the modal (inert with the rest of the page) instead of on top of its
  // controls; a visitor who is not signing in sees it first, in flow. Best-effort: if anything here throws, the
  // fixed card still works as before.
  try {
    // ★AT EVERY WIDTH, NOT ONLY BELOW 360 (C25, the 390 walk of index.html as a SIGNED-IN host, 2026-09-14): with no
    // dialog open the fixed bottom card (16..374 x 635..828 at 390x844) sat ON the shared hub FAB (318..374 x
    // 764..820) - elementFromPoint at the FAB's centre returned the card's own <summary> - so the person could not
    // open the navigation at all until they answered the card; and under any overlay (global search, companion,
    // feedback) the card's own buttons read as covered because a fixed element stays painted beneath it. In the
    // flow the card pushes content down, covers nothing, and stands under an overlay like the rest of the page.
    if (true) {
      var host = document.querySelector('main') || document.body;
      box.style.position = 'static';
      box.style.left = 'auto'; box.style.right = 'auto'; box.style.bottom = 'auto';
      // ★THE RE-FLOW KEPT THE CARD OFF THE CONTROLS AND GAVE IT A 151-CHARACTER LINE (design lens craft,
      // 2026-09-17, W45924, measured at desktop-1280 on index.html). Everything above is right and stays.
      // This ONE line was collateral: the markup declares max-width:34rem with margin:0 auto, and moving the
      // card into the flow overrode it to none. At the width that motivated the move - 320, 360, 390 - that
      // override does nothing at all, because 34rem is 544px and the viewport is already narrower. At 1280 it
      // is the whole defect: the card spanned 1274px and its description ran to ONE LINE of 151 characters
      // (canvas-measured against its own 13.12px Poppins), the longest measure on the page by more than
      // double, on the notice that asks a person to make a privacy decision. The cap comes back - the value
      // the markup always asked for - and centres, so the card reads at about 66ch on a desktop and is
      // unchanged on every phone. Nothing about the covering fix depends on the width being unbounded.
      box.style.maxWidth = '34rem';
      box.style.margin = '0 auto 1rem';
      if (host.firstElementChild !== box) host.insertBefore(box, host.firstChild);
    }
    // ★THE 361px+ SENTENCE ABOVE WAS AN ASSUMPTION, AND THE CONFUSION WALK MEASURED IT FALSE (C13 lived again at
    // phone-390, 2026-09-14): "behind the modal" was true for the accessibility tree (inert) and false for the
    // EYES - the card is z-index 9000 and the sign-in dialog is z-50, so at 390x844 the card (358x193 at 16,635)
    // sat ON the dialog's "Enterprise SSO" (45,612) and "Create one for free" (204,672): elementFromPoint at each
    // returned the card. The nav-hub walks never saw it because they audit the host page after signing in; the
    // confusion row audits the wall itself. So, at EVERY width, while the sign-in dialog is open the card stands
    // down INTO THE FLOW (static; in-flow it lands at the end of the page, behind the dialog's backdrop, covering
    // nothing) and returns to its fixed place when the dialog closes - a CSS :has() rule, so it holds for a dialog
    // opened later by a tap as well as one opened by ?signin=1, with no observer. A browser without :has() ignores
    // the rule and keeps the previous behaviour.
    if (!document.getElementById('wh-consent-standdown')) {
      var st = document.createElement('style');
      st.id = 'wh-consent-standdown';
      // max-width holds here too, for the same reason as above: standing down behind the dialog is about
      // position, not about line length, and a 34rem cap changes nothing at the narrow widths this rule was
      // written for (2026-09-17, W45924).
      st.textContent = 'body:has(#signin-modal:not(.hidden)) #wh-consent{position:static!important;left:auto!important;right:auto!important;bottom:auto!important;max-width:34rem!important;margin:0 auto 1rem!important}';
      (document.head || document.documentElement).appendChild(st);
    }
  } catch (e) { void e; }  // empty-catch-allow: the reflow is a layout nicety; the card must never fail to show
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
