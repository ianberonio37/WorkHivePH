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
        // ...and the words of the page's Sources area (ENH-R, 2026-10-19). That area is the LAST thing on every page, so
        // at the bottom of the scroll there is nowhere further to move it out from under this chip: walked at 390, the
        // chip sat on logbook's and ph-intelligence's "Where these figures come from" and their first source line. They
        // are not controls, but they are the one content a person cannot scroll clear of, so the chip cedes to them too.
        var CTRL = 'a[href],button,[role="button"],[role="tab"],[role="menuitem"],input:not([type="hidden"]),'
          + 'select,textarea,summary,[tabindex],[data-wh-sources] h2,[data-wh-sources] .wh-source-chip';
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
        // ★A LONG LIST IS READ ROW BY ROW, AND A ROW THE BROWSER IS NOT DRAWING IS PASSED OVER WHOLE (SL LB3, 2026-10-21).
        // The pass below asked every control on the page - ~3,000 on a thousand-row logbook, each a style query - four
        // times a second. A long list's rows (whRenderRows long:true, class wh-rows-cv) report when the browser stops or
        // starts drawing them (contentvisibilityautostatechange), so a row known to be skipped is passed over without
        // opening it, and the controls outside the lists come from one query that passes over them.
        // ...and never the controls inside a dialog: while one is shown the chip stands down (dialogUp), and while it is
        // closed its controls are hidden - the logbook's two pickers held 1,500 of them, every one style-checked each pass
        var CTRL_OUT = CTRL.split(',').map(function (s) { return s.trim() + ':not(.wh-rows-cv *):not([role="dialog"] *):not(dialog *)'; }).join(',');
        document.addEventListener('contentvisibilityautostatechange', function (ev) {
          if (ev && ev.target) ev.target.__whSkipped = !!ev.skipped;
        }, true);
        // the controls outside the long lists, remembered until something outside a list is inserted or removed (the
        // observer) - appending rows to a list leaves them as they were, and the query was 7.7 s of an inventory walk
        var outCache = null, outGone = 0;
        // ...and they follow what is inserted instead of being thrown away (SL LB3, 2026-10-21): a list's "Showing N of M"
        // note is REPLACED on every press (utils.js whMoreNote), and dropping the cache for it made the next pass query the
        // whole page again with CTRL_OUT - 2.6 s of an 82-press inventory walk at phone speed. An inserted element's own
        // controls join the cache (one query over that element alone), a removed control is passed over when the pass
        // meets it (isConnected), and the cache is rebuilt only once removed ones pile up.
        function addOut(n) {
          if (!outCache || !n || n.nodeType !== 1) return;
          if (n.matches(CTRL_OUT) && outCache.indexOf(n) < 0) outCache.push(n);
          var cs = n.querySelectorAll(CTRL_OUT);
          for (var i = 0; i < cs.length; i++) if (outCache.indexOf(cs[i]) < 0) outCache.push(cs[i]);
        }
        function followOut(rec) {
          if (!outCache) return;
          for (var i = 0; i < rec.addedNodes.length; i++) addOut(rec.addedNodes[i]);
          for (var j = 0; j < rec.removedNodes.length; j++) if (rec.removedNodes[j].nodeType === 1) outGone++;
          if (outGone > 200) outCache = null;
        }
        function pageControls() {
          if (ctrlCache) return ctrlCache;
          var out = [], lists = document.getElementsByClassName('wh-rows-cv');
          if (!lists.length) takeControls(document.querySelectorAll(CTRL), out);
          else {
            if (!outCache) { outCache = Array.prototype.slice.call(document.querySelectorAll(CTRL_OUT)); outGone = 0; }
            takeControls(outCache, out);
            for (var l = 0; l < lists.length && out.length < 60; l++) {
              for (var row = lists[l].firstElementChild; row && out.length < 60; row = row.nextElementSibling) {
                if (row.__whSkipped === true) continue;   // not drawn: off screen, so nothing in it is under the chip
                if (row.matches(CTRL)) takeControls([row], out);
                takeControls(row.querySelectorAll(CTRL), out);
              }
            }
          }
          ctrlCache = out;
          return out;
        }
        function takeControls(list, out) {
          for (var i = 0; i < list.length && out.length < 60; i++) {
            var e = list[i];
            if (!e.isConnected) continue;   // removed since it was remembered (followOut)
            // ★A THOUSAND-ROW LIST MADE EVERY SCAN A FULL LAYOUT (SL LB3, 2026-10-21, CPU-profiled at 390 with the CPU
            // 4x slower). Long lists render their rows with content-visibility:auto (whRenderRows long:true), so a row
            // off screen is never laid out - until something reads a rect inside it. This loop read one for EVERY
            // control on the page, on every mutation burst: report-sender's 500 contacts became one 2.1 s task, and the
            // logbook spent 10 s of a thousand-row walk here. A row the browser is skipping is off screen by definition,
            // so it cannot sit under this fixed chip: it is passed over before any rect is read. The options are named
            // (a bare checkVisibility() checks none of them): display, visibility and skipped content - not opacity,
            // which visible() deliberately does not test either - so the set is exactly what the filters below keep.
            if (e.checkVisibility && !e.checkVisibility({ contentVisibilityAuto: true, visibilityProperty: true })) continue;
            var r = ctrlRect(e);
            if (r) out.push(r);
          }
        }
        // The box a control occupies for this rule, or null when it does not count. ONE definition, used by the full
        // pass above and by the instant check below, so the two can never disagree about the same control - a chip one
        // rule hides and the other puts back would be another every-frame loop (SL LB3).
        function ctrlRect(e) {
          if (e.getAttribute && e.getAttribute('tabindex') === '-1') return null;
          // ★RECT FIRST, COMPUTED STYLE LAST (Chrome DevTools MCP, ForcedReflow, 2026-09-15). visible() resolves a
          // computed style for EVERY candidate - 31 ms of the reflow - while a display:none element already reports
          // a 0x0 rect, so the size filter below excludes it for free. Only the survivors (a handful, not 60) need
          // the style resolve, and only to catch visibility:hidden. Exactly the same set, far fewer style reads:
          // the rect overlap test stays exact, because this rule protects controls and has failed twice before.
          var r = e.getBoundingClientRect();
          // the Sources area's words are measured by the TEXT, not the block: its heading's box runs the column's full
          // width (880px on analytics-report at 1280), which the "a big container" filter below would skip, and the
          // chip then sat on the heading at the bottom of the scroll (walked 2026-10-19)
          if (e.closest && e.closest('[data-wh-sources]') && document.createRange) {
            try { var rg = document.createRange(); rg.selectNodeContents(e); var tr = rg.getBoundingClientRect(); if (tr.width > 0) r = tr; } catch (_) { /* empty-catch-allow: the block rect stands */ }
          }
          if (r.width < 4 || r.height < 4 || r.width > 520) return null;   // a control, not a big container
          if (r.bottom < 0 || r.top > innerHeight) return null;            // off-screen: cannot be under a fixed chip
          // the chrome test walks every ancestor against a list of selectors, so it runs only for the few controls on
          // screen (SL LB3: it ran for every control on a thousand-row page)
          if (e === bar || bar.contains(e) || e.closest(CHROME)) return null;
          if (!visible(e)) return null;
          return r;
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
          // the box at lift 0 does not change when the chip is shown or hidden, so no write here drops it (SL LB3)
          if (display !== lastDisplay) { bar.style.display = display; lastDisplay = display; }
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
        // ★AND IT IS MEASURED WITHOUT BEING SHOWN (SL LB3, 2026-10-21). The cache now holds the chip's box at LIFT 0 - its
        // own lift taken off when it is measured - and it is kept across hiding, because a hidden fixed chip's box does
        // not move. sync() used to set display:flex just to measure, then display:none when no lift was clear: two style
        // writes on the chip, which this file's own observer read as "the chip changed" and answered with another
        // pass on the next frame. Measured live at 390 on the logbook with a card under the chip: 360 style writes in
        // 3 s of a page at rest, and with a thousand rows at phone speed, the pass behind every frame was a long task
        // (146 s of the walk's main thread). Now a chip that has been seen once is never shown merely to be measured.
        var homeCache = null;
        function invalidateBarRect() { homeCache = null; }
        function home() {
          if (!homeCache && lastDisplay !== 'none' && bar.isConnected) {
            var r = bar.getBoundingClientRect(), l = lastLift || 0;
            if (r.width || r.height) homeCache = { left: r.left, right: r.right, top: r.top + l, bottom: r.bottom + l };
          }
          return homeCache;   // null only for a chip not measured since its box last changed
        }
        // the chip's box at a given lift
        function at(h, lift) { return { left: h.left, right: h.right, top: h.top - lift, bottom: h.bottom - lift }; }
        // ★FROM THE BROWSER'S LIVE LISTS, NOT A DOCUMENT QUERY (SL LB3, 2026-10-21). Every DIALOGISH shape is a
        // [role="dialog"], a <dialog>, or carries the class "open"; the last two are live collections the browser keeps,
        // and the role dialogs are remembered until the observer sees one inserted or a role change. A query of the whole
        // page for seven selectors ran on every pass - 6 s of a thousand-row inventory walk at phone speed.
        var roleDialogs = null;
        function dialogUp() {
          if (!roleDialogs) roleDialogs = document.querySelectorAll('[role="dialog"]');
          var sets = [roleDialogs, document.getElementsByClassName('open'), document.getElementsByTagName('dialog')];
          for (var s = 0; s < sets.length; s++) {
            for (var i = 0; i < sets[s].length; i++) {
              var d = sets[s][i];
              if (d.isConnected && d.matches(DIALOGISH) && visible(d)) return true;
            }
          }
          return false;
        }
        // ★VACATE THE INSTANT A CONTROL IS INSERTED UNDER THE CHIP (2026-09-14). The full pass below LIFTS the chip clear,
        // but hive's shift-summary "Snooze" control renders LATE (several identity round-trips), and the per-step occlusion
        // audit read the chip over it before that pass had run. So an element inserted under the chip sends the chip down
        // before the frame is painted; the full pass afterwards decides whether it can come back at a clear lift.
        // ★AFTER THE FRAME'S OWN LAYOUT, AND ONLY WHAT WAS INSERTED (SL LB3, 2026-10-21, traced at 390 with the CPU 4x
        // slower). This ran from the observer as nine hit tests over the chip: they forced the layout of whatever the page
        // had just inserted - 119 ms of one logbook "Load More" press - and each walked a thousand list rows (a
        // content-visibility row is a paint layer of its own), 54 ms more. A ResizeObserver reports after the frame's
        // layout and before its paint, and observing the chip afresh asks for exactly one report: the check now reads a
        // layout the browser has already made, and a chip that must vacate is still down before the frame is painted. It
        // asks only about the elements inserted since the last check - one rect each, and a look inside only the ones
        // that reach the chip.
        var fresh = [];
        var afterLayout = typeof ResizeObserver === 'function'
          ? new ResizeObserver(function () { afterLayout.disconnect(); vacateFresh(); }) : null;
        function vacateSoon() {
          if (!afterLayout) { requestAnimationFrame(vacateFresh); return; }
          afterLayout.disconnect();
          afterLayout.observe(bar);
        }
        function vacateFresh() {
          var list = fresh;
          fresh = [];
          if (!bar.isConnected || bar.style.display === 'none') return;   /* gone, or already down */
          // the chip WHERE IT IS, at its current lift (SL LB3, 2026-10-21): testing its resting box hid a chip sync() had
          // just lifted clear of a control, and lifted it again on the next frame - every frame
          var h = home();
          if (!h) return;
          var cur = at(h, lastLift || 0);
          for (var i = 0; i < list.length; i++) {
            if (bringsControlUnder(list[i], cur)) { setState('none', lastLift || 0); return; }
          }
        }
        // Whether an element just inserted put a control under the chip's box. A long list's row is paint-contained
        // (content-visibility), so nothing in it reaches past its own box: one rect passes over a row away from the chip
        // without reading inside it - a rect read inside a skipped row would lay that row out. The same ctrlRect() the
        // full pass uses decides each control, so the two never disagree about one.
        function bringsControlUnder(el, cur) {
          if (!el.isConnected || el === bar || bar.contains(el)) return false;
          var under = function (c) { var r = ctrlRect(c); return !!r && overlapsAny(cur, [r]); };
          var list = el.parentElement && el.parentElement.closest('.wh-rows-cv');
          if (list) {
            var row = el;
            while (row.parentElement && row.parentElement !== list) row = row.parentElement;
            if (!overlapsAny(cur, [row.getBoundingClientRect()])) return false;
            if (el.matches(CTRL) && under(el)) return true;
            var rc = el.querySelectorAll(CTRL);
            for (var k = 0; k < rc.length; k++) if (under(rc[k])) return true;
            return false;
          }
          if (el.matches(CTRL_OUT) && under(el)) return true;
          var oc = el.querySelectorAll(CTRL_OUT);
          for (var o = 0; o < oc.length; o++) if (under(oc[o])) return true;
          // a long list that came in whole, rows and all: each row by its own box first
          var rows = el.querySelectorAll('.wh-rows-cv > *');
          for (var w = 0; w < rows.length; w++) if (bringsControlUnder(rows[w], cur)) return true;
          return false;
        }
        function sync() {
          queued = false;
          if (!bar.isConnected) { obs.disconnect(); return; }   /* dismissed: stand down for good */
          if (dialogUp()) { setState('none', lastLift || 0); return; }   /* a dialog is up: stand down */
          // the box at lift 0: from the cache, so a chip standing down is not shown just to be measured; one never
          // measured since its box last changed is shown at its resting place once
          var h = home();
          if (!h) { setState('flex', 0); h = home(); }
          if (!h) return;
          // measure at each candidate lift and take the first that occludes nothing
          var ctrls = pageControls();
          var LIFTS = [0, 84, 168, 252, 336];
          for (var k = 0; k < LIFTS.length; k++) {
            if (h.top - LIFTS[k] < 8) break;                     /* would leave the viewport top */
            if (!overlapsAny(at(h, LIFTS[k]), ctrls)) { setState('flex', LIFTS[k]); return; }
          }
          setState('none', lastLift || 0);                      /* nowhere clear: cede to the page */
        }
        // ★AT MOST FOUR FULL PASSES A SECOND (SL LB3, 2026-10-21). The full pass (every control and every dialog on the
        // page) ran on the frame after every mutation burst and every scroll; a page growing a thousand-row list at phone
        // speed spent ~24 s of its walk here. Vacating is the urgent direction and stays immediate (vacateFresh, after the
        // frame's layout); finding a clear lift to return to waits up to a quarter second - leave at once, return at
        // leisure.
        var SYNC_GAP = 250, lastSync = -1e9, fullTimer = 0, fullFrame = false;
        // a mutation INSIDE the chip (the i18n swapper rewriting its label) changes its own box
        function scheduleSelf() { invalidateBarRect(); schedule(); }
        // the instant check for what was just inserted, then the quarter-second pass
        function schedule() {
          if (fresh.length) vacateSoon();
          scheduleFull();
        }
        // ★AFTER THE PAINT, NOT BEFORE IT (SL LB3, 2026-10-22). The pass ran in a requestAnimationFrame callback, and a Load
        // More press's own insertion scheduled it - so it ran inside the press's frame, before the paint the press was
        // waiting for: 33-41 ms of every press at phone speed (one press traced near a thousand rows, logbook and
        // inventory). The frame's callback now hands it to a task, which runs once that frame is painted. Getting out of
        // a control's way stays immediate (vacateFresh, after the frame's layout).
        function runFull() {
          fullTimer = 0;
          if (fullFrame) return;
          fullFrame = true;
          requestAnimationFrame(function () {
            setTimeout(function () { fullFrame = false; ctrlCache = null; lastSync = performance.now(); sync(); }, 0);
          });
        }
        // the quarter-second pass alone
        function scheduleFull() {
          if (queued) return;
          queued = true;
          var wait = SYNC_GAP - (performance.now() - lastSync);
          if (wait > 0) fullTimer = setTimeout(runFull, wait); else runFull();
        }
        // ...and the pass at once, when the page has come to rest somewhere new
        function fullNow() {
          if (fullTimer) { clearTimeout(fullTimer); fullTimer = 0; }
          queued = true;
          runFull();
        }
        // a finished transition can MOVE a control, never insert one, so it only queues the quarter-second pass: it ran
        // the instant check (nine stacked hit tests) for every transition on the page - hover fades as a pointer crossed
        // a thousand cards - 91 and 101 ms of HitTest inside two of the logbook's longest tasks (traced at 390, SL LB3)
        document.addEventListener('transitionend', function () { scheduleFull(); }, true);
        // ★A SCROLL MOVES CONTROLS, IT INSERTS NONE (SL LB3, 2026-10-21). It ran the instant check - nine hit tests
        // through a thousand rows - on every frame of a scroll. The quarter-second pass keeps up while the page moves, and
        // the moment the scroll ends the place is settled at once, before a person can aim at what scrolled under the chip.
        window.addEventListener('scroll', function () { scheduleFull(); }, { passive: true });
        window.addEventListener('scrollend', fullNow, { passive: true });
        window.addEventListener('resize', function () { invalidateBarRect(); fullNow(); }, { passive: true });
        // ★childList, NOT ONLY attributes (2026-09-14): a page's controls often render AFTER this chip is
        // injected (hive's shift-summary tile arrives on a later identity round-trip), and a control ADDED to
        // the DOM is a childList mutation the attribute filter never saw - so the chip's collision check ran
        // once against an empty bottom-left and never re-ran, and the added Snooze button sat under it. Watch
        // childList too, and re-check while the page fills in.
        var obs = new MutationObserver(function (records) {
          // a mutation INSIDE the chip (the i18n swapper rewriting its label, the fold) changes the chip's own box, so
          // it drops the cached box; so does a style change on <html> or <body>, which is how nav-hub's shared
          // --wh-fab-lift moves every bottom chip. The chip's OWN style writes (setState's display and lift) are the
          // one kind skipped: answering them is what made this observer drive itself every frame (SL LB3).
          var moved = false, other = false, dialog = false, inserted = false;
          // elements inserted once the page has settled, while the chip is up, are kept for the instant check (vacateFresh);
          // while the document is still loading, its own render is the only thing mutating and the full pass places the
          // chip a frame later - so nothing is kept for the whole load burst, where it would cost the most and prove nothing
          var keep = document.readyState === 'complete' && bar.style.display !== 'none';
          for (var i = 0; i < records.length; i++) {
            var rec = records[i], t = rec.target;
            if (t === bar && rec.type === 'attributes' && rec.attributeName === 'style') continue;
            // a chart's drawing holds no control and moves none: its hundreds of SVG nodes were kept and checked one by one
            if (t && t.namespaceURI === 'http://www.w3.org/2000/svg') continue;
            if (t && (t === bar || (bar.contains && bar.contains(t)))) { moved = true; continue; }
            if ((t === document.documentElement || t === document.body) && rec.type === 'attributes'
                && rec.attributeName === 'style') moved = true;
            other = true;
            if (rec.type === 'childList') {
              // the controls outside the lists change only when an ELEMENT outside a list is inserted or removed: a label
              // rewriting its words swaps a text node and adds no control, yet inventory's "Showing N of M parts" threw the
              // remembered controls away on every press, and the next pass queried the whole page again
              var el = false;
              for (var ia = 0; ia < rec.addedNodes.length; ia++) {
                if (rec.addedNodes[ia].nodeType !== 1) continue;
                el = inserted = true;
                if (keep) fresh.push(rec.addedNodes[ia]);
              }
              for (var ir = 0; !el && ir < rec.removedNodes.length; ir++) if (rec.removedNodes[ir].nodeType === 1) el = true;
              if (el && !(t && t.closest && t.closest('.wh-rows-cv'))) followOut(rec);
            }
            // a role that makes a dialog hides the controls inside it, so the remembered set is rebuilt; any other role
            // change only adds the element if it is now a control - inventory's figure marking gives every stat number a
            // role on each press, and rebuilding the set for each re-ran the whole-page query (SL LB3)
            if (rec.attributeName === 'role') {
              var rv = t && t.getAttribute ? t.getAttribute('role') : null;
              if (rv === 'dialog' || rv === 'alertdialog') outCache = null;
              else if (outCache && t.matches && t.matches(CTRL_OUT) && outCache.indexOf(t) < 0) outCache.push(t);
            }
            // a dialog opening is caught where it happens - its own attribute change, or its insertion - and only then
            // is the page asked whether one is up (the full scan no longer runs on every burst)
            if (!dialog && t && t.nodeType === 1 && t.matches && t.matches(DIALOGISH)) dialog = true;
            // the remembered role dialogs go stale when one is inserted or a role changes (see dialogUp)
            if (rec.attributeName === 'role') roleDialogs = null;
            for (var q = 0; roleDialogs && rec.addedNodes && q < rec.addedNodes.length; q++) {
              var an = rec.addedNodes[q];
              if (an.nodeType === 1 && (an.matches('[role="dialog"]') || an.querySelector('[role="dialog"]'))) roleDialogs = null;
            }
            for (var a = 0; !dialog && rec.addedNodes && a < rec.addedNodes.length; a++) {
              var n = rec.addedNodes[a];
              if (n.nodeType === 1 && (n.matches(DIALOGISH) || n.querySelector(DIALOGISH))) dialog = true;
            }
          }
          if (dialog && bar.style.display !== 'none' && dialogUp()) setState('none', lastLift || 0);
          // the instant check is for an element INSERTED under the chip (its reason since 2026-09-14); a class or style
          // change only queues the quarter-second pass - on a thousand-row page each instant check after a write was a
          // forced layout (7.7 s of hit tests in an inventory walk at phone speed, SL LB3)
          if (moved) scheduleSelf();
          else if (inserted) schedule();
          else if (other) scheduleFull();
        });
        obs.observe(document.documentElement, { attributes: true, childList: true, subtree: true,
          attributeFilter: ['style', 'class', 'open', 'aria-hidden', 'hidden', 'role'] });
        sync();
        [300, 800, 1500, 2600, 4000, 6000, 9000, 12000].forEach(function (ms) { setTimeout(schedule, ms); });
      })();
    }).catch(function () { /* empty-catch-allow: best-effort; no guide bar if the map cannot load */ });
  } catch (e) { /* empty-catch-allow: never break the host page over an optional guide bar */ }
})();
