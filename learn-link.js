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
    /* T121 (2026-08-28): owner-stamped. This chip rides EVERY page, so an unowned flag was the
       widest of the three dismissal leaks - a worker who dismissed the guide on eight pages left
       the next person on that station tablet with no page-guide affordance anywhere, and nothing
       on screen to explain why. whIsDismissed treats a legacy '1' as not-dismissed, so the chip
       returns once per page for its rightful owner too. */
    try {
      if (typeof whIsDismissed === 'function') { if (whIsDismissed(DISMISS_KEY)) return; }
      else if (localStorage.getItem(DISMISS_KEY)) return;
    } catch (e) { /* empty-catch-allow: localStorage blocked (private mode); show the bar */ }

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
        // OPAQUE, so this chip's contrast is a property of the chip and not of whatever scrolled under
        // it. At 0.96 alpha the three labels here measure 5.06:1, 7.89:1 and 6.67:1 against the
        // composited chip, so nothing was FAILING - but axe abstained on all three, on every page,
        // because the element is position:fixed and a fixed element's true backdrop is whatever the
        // page happens to have scrolled beneath it, which no static tool can resolve. Those
        // abstentions were the last nodes on five walked pages judged by NEITHER axe nor the APCA lens
        // (which excludes shared chrome by design), so they were the residue blocking contrast_wcag
        // from being fully dispositioned. 0.96 -> 1 is imperceptible (it removes a 4% bleed-through)
        // and converts an unjudgeable node into a judgeable one. Same reasoning as wayfinding.js's
        // crumb chip this session, where the translucency was the actual defect at 3.89:1.
        // var(--wh-navy), not the raw rgb(22,32,50) it was: that value IS the canonical brand navy
        // token (tokens.css:56), and the centralization roadmap counts this file's one raw literal in
        // its purity table. Using the token makes the fix satisfy both rules at once instead of trading
        // one debt for another. The fallback keeps the chip opaque if the sheet ever fails to load.
        'background:var(--wh-navy,#162032);border:1px solid rgba(247,162,27,0.35);border-radius:12px;' +
        /* 10px right / 12px left was an asymmetry the 4px rhythm does not allow and nothing needed: the
           dismiss button carries its own 44px box and 4px inset, so the chip does not have to shave its
           right edge for it (design lens craft, 2026-09-17, W45924). */
        'padding:8px 12px;box-shadow:0 8px 24px rgba(0,0,0,0.35);' +
        'font-weight:600;font-size:0.8rem;line-height:1.25;font-family:var(--wh-font, Poppins,system-ui,-apple-system,Segoe UI,Roboto,sans-serif);';   // the page's own typeface, on its ramp (design lens craft, 2026-09-15: the chip was the only system-ui text on every page)
      var a = document.createElement('a');
      a.href = '/learn/' + g.slug + '/';
      // min-height 44 = the tap-target floor (F1). The two stacked caption lines
      // only measured 29px tall, so the whole guide link was under-size on every
      // page that renders it.
      a.style.cssText = 'display:flex;align-items:center;gap:8px;color:var(--wh-orange, #F7A21B);text-decoration:none;flex:1;min-width:0;min-height:44px;';
      var T = function (en, fil) { return (typeof window._t === 'function') ? window._t(en, fil) : en; };   // the chip speaks the page's language (design lens copy, 2026-09-15)
      a.innerHTML = '<span aria-hidden="true" style="font-size:1rem;">📖</span>' +
        '<span style="min-width:0;"><span style="display:block;color:rgba(255,255,255,0.80);font-weight:500;font-size:0.75rem;">' + T('New to this page?', 'Bago ka sa page na ito?') + '</span> ' +
        '<span style="display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + T('Read the guide', 'Basahin ang gabay') + '</span></span>';
      // ★LABEL IN NAME: THE CHIP'S ACCESSIBLE NAME LEFT OUT ITS OWN VISIBLE WORDS (WCAG 2.5.3, design
      // lens audit, 2026-09-17, W45925; caught by Lighthouse 13.4.1 as label-content-name-mismatch, the
      // one failing audit of 61 on index.html). The chip SHOWS two lines - 'New to this page?' above
      // 'Read the guide' - and its aria-label was only the second one plus the guide's title. Success
      // criterion 2.5.3 requires the accessible name to CONTAIN the visible label text, because someone
      // driving the browser by voice says what they can see: 'New to this page' matched nothing.
      // The eyebrow is added to the NAME rather than hidden from it with aria-hidden, which is the other
      // way to satisfy the rule: that line is the only thing on the chip explaining why it appeared, and a
      // screen-reader user needs it as much as a sighted one. 'Read the guide' is still a substring, so
      // voice control matches either phrase. Both languages, since T() supplies both.
      // AND the two lines are joined by a SPACE, which is the half of this that took a measurement to see.
      // axe builds an element's visible label by concatenating its text nodes, and these two lines are
      // sibling display:block spans that sat directly against each other in the markup - so the visible
      // label was the run-on 'New to this page?Read the guide', which with punctuation stripped is
      // 'new to this pageread the guide' and cannot be a substring of any name containing a space.
      // Marking the eyebrow aria-hidden was tried first and did NOT fix it, which is the useful part: this
      // criterion compares the name against what is VISIBLE, and aria-hidden changes what is announced,
      // not what is on screen. The single space between the two closing and opening spans is invisible
      // (adjacent block boxes) and makes the visible label 'New to this page? Read the guide', which the
      // aria-label above contains verbatim.
      a.setAttribute('aria-label', T('New to this page?', 'Bago ka sa page na ito?') + ' ' +
        T('Read the guide', 'Basahin ang gabay') + ': ' + g.title);
      a.title = g.title;

      var x = document.createElement('button');
      x.type = 'button';
      x.setAttribute('aria-label', T('Dismiss guide link', 'Isara ang link ng gabay'));
      x.textContent = '×';
      // 44x44 is the tap-target floor (F1) -- this dismiss button was 28x28, and F1
      // fails on the MIN dimension, so both axes must clear it.
      x.style.cssText = 'flex:0 0 auto;display:flex;align-items:center;justify-content:center;background:none;border:none;color:rgba(255,255,255,0.6);font-size:1.125rem;line-height:1;cursor:pointer;padding:4px;min-width:44px;min-height:44px;';
      x.addEventListener('click', function () {
        try {
          if (typeof whSetDismissed === 'function') whSetDismissed(DISMISS_KEY);
          else localStorage.setItem(DISMISS_KEY, '1');
        } catch (e) { /* empty-catch-allow: localStorage blocked; dismissal is best-effort */ }
        bar.remove();
      });

      bar.appendChild(a); bar.appendChild(x);
      (document.body || document.documentElement).appendChild(bar);

      /* ★THE CHIP COVERED THE THIRD TILE'S NUMBER IN THE FIRST PHONE VIEWPORT (ledger C34, 2026-09-15, seen by the
         design-lens walks of achievements and ai-quality through the Playwright MCP: the Total level sub-line, the
         ₱0.00 cost hero). After 8 s at rest or the first scroll the chip folds to its 44x44 icon so the numbers stay
         readable; a tap on the folded chip unfolds it (the second tap follows the link); the dismiss stays as it was. */
      var textBlock = a.children[1] || null;
      var folded = false;
      var fold = function () {
        if (folded || !document.body.contains(bar)) return;
        folded = true;
        if (textBlock) textBlock.style.display = 'none';
        x.style.display = 'none';
        bar.style.gap = '0';
        // the folded link is still a target: the icon alone measured 22x44 at 1280 (W45855, 2026-09-15), so the anchor
        // keeps the 44px floor on both sides and centres its icon
        a.style.minWidth = '44px'; a.style.justifyContent = 'center';
        bar.setAttribute('data-wh-folded', '1');
        a.setAttribute('aria-expanded', 'false');
      };
      var unfold = function () {
        if (!folded) return;
        folded = false;
        if (textBlock) textBlock.style.display = '';
        x.style.display = '';
        bar.style.gap = '8px';
        a.style.minWidth = '0'; a.style.justifyContent = '';
        bar.removeAttribute('data-wh-folded');
        a.setAttribute('aria-expanded', 'true');
      };
      a.addEventListener('click', function (ev) { if (folded) { ev.preventDefault(); unfold(); } });
      setTimeout(fold, 8000);
      window.addEventListener('scroll', fold, { once: true, passive: true });

      /* ★A FLOATING HELPER MUST NOT INTERCEPT A DIALOG'S OWN BUTTONS.
         The V1 fix above moved this chip clear of the bottom-left page FABs by raising it to bottom:132px
         — which put it squarely over the ACTION ROW of every modal on the platform. Measured on
         pm-scheduler at 390x844: #pm-edit-save-btn ("Save Changes") centres at (95, 606); this chip
         occupies x 12-207, y 583-647; document.elementFromPoint(95, 606) returned a <span> inside
         #wh-guide-link, NOT the button. #pm-edit-modal and this chip are BOTH z-index 60, and equal
         z-index resolves by DOM order — the chip is appended last, so it wins. A supervisor could not
         save a PM asset edit at all, and the modal's own inputs tested fine, so nothing about the
         dialog looked broken.
         Raising the modals instead would be a third round of the same nudge (Ian: colliding widgets),
         and it would only hold until the next widget. The rule is behavioural: while a dialog is up,
         a page-level guide is irrelevant, so it stands down entirely — no tap interception, no focus
         stop inside a modal's trap, no contrast question over a backdrop. It returns when the dialog
         closes. Cheap: attribute-only observer, one rAF-debounced check, and it disconnects itself if
         the chip is dismissed (dismissal calls bar.remove()). */
      (function standDownWhileDialogOpen() {
        // Kept identical to nav-hub.js's list on purpose: two copies of one rule that drift are how a
        // component gets fixed on one surface and stays broken on the next. .sheet-overlay.open is
        // community's convention and was missing here.
        var DIALOGISH = '[role="dialog"],dialog[open],.sheet.open,.modal.open,[id$="-sheet"].open,'
          + '[id$="-modal"].open,.sheet-overlay.open';
        var queued = false, lastLift = null, lastDisplay = null;
        function visible(el) {
          var cs = getComputedStyle(el);
          // NOT opacity: a dialog mid-fade reports opacity 0 on the first frame after its class flips,
          // and with no further mutation to re-trigger the check the chrome stays up for the dialog's
          // whole life. Found on nav-hub.js's copy of this rule; fixed here too so the two cannot drift.
          if (cs.display === 'none' || cs.visibility === 'hidden') return false;
          var r = el.getBoundingClientRect();
          return r.width > 0 && r.height > 0;
        }
        // ★AND IT MUST NOT COVER A PAGE CONTROL EITHER (Wave-4 nav-hub walk of hive.html as a supervisor,
        // 2026-09-14). This is the SECOND time this fixed chip has occluded an interactive control: the
        // first was pm-scheduler's modal Save (handled above by standing down while a dialog is up); this
        // one is AT REST — hive's shift-summary "Snooze this tile" (44x44) sits in the bottom-left zone the
        // chip is anchored to, and elementFromPoint at the snooze centre returned #wh-guide-link. Repositioning
        // once "holds until the next widget" (the memory's warning), so the rule is behavioural and general:
        // on every layout the chip tries a few LIFTS clear of the page's own controls and takes the first that
        // occludes nothing; if none is clear it stands down, exactly as it does for a dialog. It cedes to the
        // page's controls because it is optional onboarding and the nav-hub still offers the guide.
        var CTRL = 'a[href],button,[role="button"],[role="tab"],[role="menuitem"],input:not([type="hidden"]),'
          + 'select,textarea,summary,[tabindex]';
        var CHROME = '#wh-hub,#wh-guide-link,.wh-conn-chip,.wh-conn-popover,.wh-fb-fab,#wh-ai-widget,'
          + '#wh-ai-launcher,#wh-feedback-fab,[id^="wh-hub-"],header,[role="banner"]';
        // ★ONE CONTROLS SCAN PER FRAME (Chrome DevTools MCP, ForcedReflow insight, 2026-09-15). This walks up
        // to 60 controls and reads a computed style AND a rect for each - up to 120 forced layout reads - and
        // it ran TWICE per frame (the synchronous vacate, then the rAF placement) for every mutation burst of
        // a 30-row feed render. Measured 149 ms of forced reflow on a 4x-throttled phone, 110 ms of it here.
        // Both callers run inside one frame and need the same rects, so the scan is memoised per frame and
        // cleared in the rAF callback; a write between them is the page's own render, which the NEXT frame
        // re-measures anyway.
        var ctrlCache = null;
        function pageControls() {
          if (ctrlCache) return ctrlCache;
          var out = [], list = document.querySelectorAll(CTRL);
          for (var i = 0; i < list.length && out.length < 60; i++) {
            var e = list[i];
            if (e === bar || bar.contains(e) || e.closest(CHROME)) continue;
            if (e.getAttribute && e.getAttribute('tabindex') === '-1') continue;
            // ★RECT FIRST, COMPUTED STYLE LAST (Chrome DevTools MCP, ForcedReflow, 2026-09-15). visible() resolves a
            // computed style for EVERY candidate - 31 ms of the reflow - while a display:none element already reports
            // a 0x0 rect, so the size filter below excludes it for free. Only the survivors (a handful, not 60) need
            // the style resolve, and only to catch visibility:hidden. Exactly the same set, far fewer style reads:
            // the rect overlap test stays exact, because this rule protects controls and has failed twice before.
            var r = e.getBoundingClientRect();
            if (r.width < 4 || r.height < 4 || r.width > 520) continue;   // a control, not a big container
            if (r.bottom < 0 || r.top > innerHeight) continue;            // off-screen: cannot be under a fixed chip
            if (!visible(e)) continue;
            out.push(r);
          }
          ctrlCache = out;
          return out;
        }
        function overlapsAny(rect, ctrls) {
          for (var i = 0; i < ctrls.length; i++) {
            var c = ctrls[i];
            var ix = Math.min(rect.right, c.right) - Math.max(rect.left, c.left);
            var iy = Math.min(rect.bottom, c.bottom) - Math.max(rect.top, c.top);
            if (ix > 2 && iy > 2) return true;
          }
          return false;
        }
        function setState(display, lift) {
          if (display !== lastDisplay) { bar.style.display = display; lastDisplay = display; invalidateBarRect(); }
          if (lift !== lastLift) { bar.style.transform = lift ? ('translateY(-' + lift + 'px)') : ''; lastLift = lift; }
        }
        // Where the chip currently sits, with its own lift removed — the geometry both the immediate hide
        // and the deferred lift reason about.
        // ★A FIXED ELEMENT'S RECT DOES NOT CHANGE WHEN THE PAGE BEHIND IT RENDERS (Chrome DevTools MCP,
        // ForcedReflow, 2026-09-15: 59 ms of the remaining 87 ms was here). This chip is position:fixed, so the
        // feed painting 30 rows underneath cannot move it - yet its rect was re-read, and therefore layout
        // re-forced, on every single mutation burst. The rect is cached and invalidated only by the things that
        // CAN move it: this code changing its display or lift, the chip folding or unfolding, its text being
        // swapped to the other language, and the viewport resizing.
        var barRectCache = null;
        function invalidateBarRect() { barRectCache = null; }
        function baseRect() {
          if (!barRectCache) {
            var r = bar.getBoundingClientRect();
            barRectCache = { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
          }
          return { left: barRectCache.left, right: barRectCache.right,
                   top: barRectCache.top + (lastLift || 0), bottom: barRectCache.bottom + (lastLift || 0) };
        }
        function dialogUp() {
          var all = document.querySelectorAll(DIALOGISH);
          for (var i = 0; i < all.length; i++) { if (visible(all[i])) return true; }
          return false;
        }
        // ★HIDE SYNCHRONOUSLY THE INSTANT A CONTROL IS UNDER THE CHIP (2026-09-14). The deferred sync below
        // LIFTS the chip clear, but it runs on the next animation frame — and hive's shift-summary "Snooze"
        // control renders LATE (several identity round-trips), so the per-step occlusion audit could read the
        // overlap in the ~16ms window before the rAF fired. So the observer (which fires in the same microtask
        // as the control's insertion) hides the chip RIGHT THEN if it is over a control or a dialog; the
        // deferred sync afterwards decides whether it can come back at a clear lift. The gate-satisfying action
        // (vacate) is synchronous; only the re-appearance is deferred.
        function hideIfOccluding() {
          if (!bar.isConnected) return;
          if (bar.style.display === 'none') return;                       /* already down */
          if (dialogUp() || overlapsAny(baseRect(), pageControls())) setState('none', lastLift || 0);
        }
        function sync() {
          queued = false;
          if (!bar.isConnected) { obs.disconnect(); return; }   /* dismissed: stand down for good */
          if (dialogUp()) { setState('none', 0); return; }      /* a dialog is up: stand down */
          // measure at each candidate lift and take the first that occludes nothing
          setState('flex', lastLift || 0);
          var ctrls = pageControls();
          var base = bar.getBoundingClientRect(), baseTop = base.top + (lastLift || 0);   // top with lift removed
          var LIFTS = [0, 84, 168, 252, 336];
          for (var k = 0; k < LIFTS.length; k++) {
            if (baseTop - LIFTS[k] < 8) break;                   /* would leave the viewport top */
            var probe = { left: base.left, right: base.right, top: baseTop - LIFTS[k], bottom: base.bottom - (lastLift || 0) - LIFTS[k] };
            if (!overlapsAny(probe, ctrls)) { setState('flex', LIFTS[k]); return; }
          }
          setState('none', 0);                                  /* nowhere clear: cede to the page */
        }
        // ★113 ms OF FORCED REFLOW ON A THROTTLED PHONE (Chrome DevTools MCP, ForcedReflow insight, 2026-09-15:
        // top frame `schedule @ learn-link.js`, 87 ms inside baseRect, 58 ms inside visible). hideIfOccluding
        // reads the bar's rect, then a computed style + rect for every dialog-ish node, then every page
        // control - and it ran on EVERY mutation burst, so a feed rendering 30 rows forced layout dozens of
        // times, each read invalidated by the page's next write. The invariant survives intact: the FIRST
        // burst in a frame still measures and vacates synchronously (that is what keeps the chip off a
        // control inserted in the same microtask); later bursts in the SAME frame skip the re-measure,
        // because the rAF pass one frame later settles the placement authoritatively anyway.
        var measuredThisFrame = false;
        // a mutation INSIDE the chip (the i18n swapper rewriting its label) changes its own box
        function scheduleSelf() { invalidateBarRect(); schedule(); }
        function schedule() {
          // the synchronous vacate exists for a control inserted in the same microtask AFTER the page has
          // settled (hive's shift-summary Snooze). While the document is still loading, its own render is
          // the only thing mutating and the rAF pass one frame later places the chip correctly - so the
          // expensive read is skipped for the whole load burst, where it cost the most and proved nothing.
          if (document.readyState === 'complete' && !measuredThisFrame) { measuredThisFrame = true; hideIfOccluding(); }
          if (!queued) {
            queued = true;
            requestAnimationFrame(function () { measuredThisFrame = false; ctrlCache = null; sync(); });
          }
        }
        document.addEventListener('transitionend', schedule, true);
        window.addEventListener('scroll', schedule, { passive: true });
        window.addEventListener('resize', function () { invalidateBarRect(); schedule(); }, { passive: true });
        // ★childList, NOT ONLY attributes (2026-09-14): a page's controls often render AFTER this chip is
        // injected (hive's shift-summary tile arrives on a later identity round-trip), and a control ADDED to
        // the DOM is a childList mutation the attribute filter never saw - so the chip's collision check ran
        // once against an empty bottom-left and never re-ran, and the added Snooze button sat under it. Watch
        // childList too, and re-check while the page fills in.
        var obs = new MutationObserver(function (records) {
          // a mutation INSIDE the chip (the i18n swapper rewriting its label) is the one kind that changes the
          // chip's own box, so it is also the one kind that must drop the cached rect
          for (var i = 0; i < records.length; i++) {
            var t = records[i].target;
            if (t && (t === bar || (bar.contains && bar.contains(t)))) { scheduleSelf(); return; }
          }
          schedule();
        });
        obs.observe(document.documentElement, { attributes: true, childList: true, subtree: true,
          attributeFilter: ['style', 'class', 'open', 'aria-hidden', 'hidden'] });
        sync();
        [300, 800, 1500, 2600, 4000, 6000, 9000, 12000].forEach(function (ms) { setTimeout(schedule, ms); });
      })();
    }).catch(function () { /* empty-catch-allow: best-effort; no guide bar if the map cannot load */ });
  } catch (e) { /* empty-catch-allow: never break the host page over an optional guide bar */ }
})();
