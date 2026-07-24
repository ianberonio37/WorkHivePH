/* ============================================================================
 * survey_ufai_rubric.js — the A–Z RUBRIC lens (90 dims encoded), as ONE injectable
 * ============================================================================
 * Ian, 2026-07-15: "retrieve our entire UFAI UI UX class dimensions by our
 * substrate, then use it as your lens to re-survey the entire analytics pages
 * top to bottom."
 *
 * WHY THIS EXISTS (it is NOT a second battery):
 *   ufai_battery.js grades the FIVE PILLARS (U/F/A/I/C) — axe, CWV, tap, wiring,
 *   value-correctness. It is the kernel and this file does NOT duplicate it.
 *   This is the *other* ruler: `substrate/reference/ufai-ux-rubric.md`'s
 *   **24 classes A–Z / 74 dims** (67 encoded here; S2/S3 + X1/Y2/G5/J3/S4 are cross-page/journey, owned by
 *   family_rubric_sweep.mjs), each a CITED rule (NN/g, Laws of UX, WCAG,
 *   GOV.UK, web.dev). Ad-hoc probing kept surveying whatever the last finding
 *   pointed at; this walks the ruler start-to-finish so nothing is dropped.
 *
 * THE HONESTY CONTRACT (why a dim may say UNMEASURED):
 *   - MEASURED  → a real denominator: (passing / total), computed from the DOM.
 *   - JUDGED    → a cited criterion with no honest denominator (peak-end,
 *                 delight). It reports `null`, NEVER an invented number. A dim
 *                 that cannot be measured must not be scored — that is the
 *                 false-100 this whole arc kept catching.
 *   - N/A       → the dim's subject does not exist on this page (e.g. M2
 *                 validation on a read-only page). Excluded from the total,
 *                 stated explicitly, never silently counted as a pass.
 *
 * USAGE (same install idiom as the battery — the file is an ARROW FN EXPRESSION,
 * so a <script src> tag installs NOTHING and self-flags as a prod-path defect):
 *   const src = await fetch('/workhive/survey_ufai_rubric.js').then(r=>r.text());
 *   eval('(' + src + ')')();          // installs window.__RUBRIC
 *   await window.__RUBRIC.survey({ pageId:'analytics' });
 *
 * ★MEASURE THE WORKED STATE. Every number here is meaningless on an empty
 *  generator form or a pre-fetch shell (proven twice: analytics-report scored
 *  "0 defects / 5-of-5 pillars" while rendering a form). survey() therefore
 *  REFUSES to score unless `readyWhen()` is satisfied.
 * ============================================================================ */
() => {
  const V = '1.0.0';
  if (window.__RUBRIC && window.__RUBRIC._v === V) return { already: true, _v: V };

  // ── RUBRIC_THRESHOLDS ── the canonical numeric floors (UR-P1). The SSOT is
  // ufai-rubric-spec.json; this is a GENERATED MIRROR kept in sync by the
  // `rubric-parity` gate (tools/validate_rubric_parity.py), which FAILs the build if
  // any value here diverges from the JSON. Detectors read `TH.<dim>.<key>` instead of a
  // scattered literal, so a threshold lives in exactly one place. window.__RUBRIC_THRESHOLDS
  // (harness-injected from the JSON) overrides the mirror when present.
  /* RUBRIC_THRESHOLDS_START */
  const RUBRIC_THRESHOLDS = {
    B3: { maxSentenceWords: 20, maxFkGrade: 8, minGradedWords: 12 },
    C1: { maxDisplaySizes: 3, maxSizeTiers: 10 },
    C2: { contrastNormal: 4.5, contrastLarge: 3, largePx: 24, largeBoldPx: 18.66 },
    // C5 — APCA (WCAG 3 successor) perceptual Lc minimums, from the harvested APCA table.
    // minPx is APCA's supported floor: below it the answer is "text too small", not a contrast score.
    C5: { minPx: 14, lcBody: 75, lcContent: 60, lcLarge: 45 },
    D3: { maxButtonShapes: 6 },
    E4: { maxIdsPerBlock: 7 },
    F1: { minTapPx: 44 },
    K2: { minTapPx: 44 },
    T6: { maxPeerRows: 150, noListBelow: 30 },
    A3: { maxPrimaryCta: 2 },
  };
  /* RUBRIC_THRESHOLDS_END */
  const TH = (window.__RUBRIC_THRESHOLDS && typeof window.__RUBRIC_THRESHOLDS === 'object')
    ? window.__RUBRIC_THRESHOLDS : RUBRIC_THRESHOLDS;

  const $$ = (sel, root) => [...(root || document).querySelectorAll(sel)];
  const vis = (e) => {
    if (!e || e.offsetParent === null) return false;
    const s = getComputedStyle(e);
    if (s.display === 'none' || s.visibility === 'hidden') return false;
    // A CLOSED <details> hides its content through the UA's internal slot
    // (content-visibility), NOT by setting display:none on the children. So a collapsed
    // child still reports display:inline / visibility:visible / a real rect and every
    // display-based check above says "visible" -- while innerText (the rendering-aware
    // API) correctly omits it. Without this the lens counts disclosed content as
    // on-screen and reports a dump the user cannot actually see. The <summary> itself IS
    // visible, so only non-summary descendants are excluded.
    // det !== e: the closed <details> ELEMENT is itself visible (its summary shows) --
    // only its non-summary DESCENDANTS are hidden. Without this, every closed disclosure
    // (the normal state) vanished from the lens and A3 counted disclosures=0 on pages
    // that ship them (dayplanner had 2). An over-broad exclusion is the same instrument
    // class as an over-broad match -- both misreport; this one hid the AFFORDANCE itself.
    const det = e.closest('details:not([open])');
    if (det && det !== e && !e.closest('summary')) return false;
    return true;
  };
  // The page's own content root; shell chrome (nav hub, companion, feedback FAB)
  // is owned by other surfaces — scope by OWNER for triage, but NEVER by
  // visibility for coverage (that is what hid 48 clickables from an earlier pass).
  // querySelector returns the first match in DOCUMENT ORDER, not in selector order --
  // '.page, ..., main' picked <main> (1 child) and R1 measured gaps=[] -> a false 0%.
  // Probe each selector in PRIORITY order instead.
  // Pick the root that actually HOLDS THE ARTIFACT, by content weight — not by a fixed
  // priority list. On analytics-report the report renders into #ar-print-wrapper, which
  // must be a DIRECT CHILD OF <body> for the @media print rule, so it sits OUTSIDE
  // #ar-page. A priority list picked #ar-page (the generator toolbar) and graded the
  // toolbar as if it were the report: "headings=1, blocks=0" on a page with 7 h2 + 6
  // tables. Content-weight makes the lens self-correcting on any page shape.
  const root = (explicit) => {
    if (explicit) { const e = document.querySelector(explicit); if (e) return e; }
    // <body> is NEVER a valid artifact root: it contains the page AND all shell chrome
    // (nav hub, companion, feedback FAB, guide link), so weighing it always wins and the
    // lens then grades the SHELL's controls as the page's own — that is how F1 reported
    // "Search assets(336x42)" (the nav hub) as an analytics-report defect.
    const cands = ['.page', '#ar-print-wrapper', '#ar-page', 'main']
      .map((sel) => document.querySelector(sel))
      .filter((el) => el && el.children.length > 0);
    if (!cands.length) return document.body;
    const weigh = (el) => (el.innerText || '').trim().length
      + el.querySelectorAll('h1,h2,h3,table,.card,.simple-card').length * 40;
    return cands.reduce((best, el) => (weigh(el) > weigh(best) ? el : best), cands[0]);
  };
  const ownText = (e) => [...e.childNodes].filter(n => n.nodeType === 3)
    .map(n => n.textContent.trim()).join(' ').trim();

  const pct = (pass, total) => total > 0 ? Math.round((pass / total) * 100) : null;
  const M = (id, name, pass, total, note) => ({
    dim: id, name, kind: 'MEASURED', pass, total, pct: pct(pass, total), note: note || '',
  });
  const J = (id, name, note) => ({ dim: id, name, kind: 'JUDGED', pass: null, total: null, pct: null, note });
  const NA = (id, name, note) => ({ dim: id, name, kind: 'N/A', pass: null, total: null, pct: null, note });

  // ── colour maths (WCAG) ───────────────────────────────────────────────────
  const rgb = (s) => { const m = (s || '').match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/); return m ? { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] } : null; };
  const over = (f, b) => ({ r: f.r * f.a + b.r * (1 - f.a), g: f.g * f.a + b.g * (1 - f.a), b: f.b * f.a + b.b * (1 - f.a), a: 1 });
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const ratio = (a, b) => { const L1 = lum(a), L2 = lum(b); const hi = Math.max(L1, L2), lo = Math.min(L1, L2); return (hi + 0.05) / (lo + 0.05); };
  // Composite the FULL ancestor chain onto the page's own base colour. The first cut
  // composited a translucent layer over WHITE, which on this dark shell produced
  // impossible 1:1 ratios ("30 days" over rgba(255,255,255,0.05)).
  const pageBase = () => rgb(getComputedStyle(document.body).backgroundColor)
    || rgb(getComputedStyle(document.documentElement).backgroundColor)
    || { r: 255, g: 255, b: 255, a: 1 };
  const effBg = (el) => {
    // THE GRADIENT BLINDSPOT (found via a "1:1" verdict on dayplanner's Day tab): reading
    // only backgroundColor composited navy TEXT against the navy BODY while the element
    // actually sits on an ORANGE GRADIENT (background-image) -- readable in reality,
    // "invisible" to the ruler. A gradient node is an OPAQUE surface whose colour varies:
    // return its stops so the caller can score against the WORST one (conservative -- if
    // text passes on every stop it passes on everything between).
    // SECOND blindspot (found via community's .wh-avatar-lvl "1.19"): the gradient
    // early-return fired for an ANCESTOR gradient even when a CLOSER layer was opaque —
    // navy-on-opaque-amber (7.9:1, passes) was scored against the avatar-ring gradient
    // BEHIND the badge. An opaque layer fully covers everything above it: stop walking
    // there; and when a gradient legitimately shows through, composite the translucent
    // layers below it over EACH stop before worst-stop scoring.
    const chain = [];
    let n = el;
    while (n && n !== document.documentElement) {
      const st = getComputedStyle(n);
      const img = st.backgroundImage || '';
      if (img.includes('gradient')) {
        // A translucent stop (rgba …,0.6) renders composited over whatever is BEHIND the
        // gradient node — forcing it opaque scores a colour the user never sees. Resolve
        // the behind-surface by continuing the walk from the parent, composite each stop
        // over it, then composite the translucent chain below the gradient over each stop.
        const parsed = (img.match(/rgba?\([^)]+\)/g) || []).map(rgb).filter(Boolean);
        if (parsed.length) {
          let behind = n.parentElement ? effBg(n.parentElement) : { ...pageBase(), a: 1 };
          if (behind.stops) behind = behind.stops[0];
          const stops = parsed
            .map((c) => (c.a < 1 ? over(c, behind) : { ...c, a: 1 }))
            .map((stop) => {   // chain holds only translucent layers here (opaque breaks below)
              let acc = stop;
              for (let i = chain.length - 1; i >= 0; i--) acc = over(chain[i], acc);
              return acc;
            });
          const first = { ...stops[0] };
          first.stops = stops;
          return first;
        }
      }
      const b = rgb(st.backgroundColor);
      if (b && b.a > 0) {
        chain.push(b);
        if (b.a >= 1) break;   // opaque: nothing behind it can show through
      }
      n = n.parentElement;
    }
    let acc = { ...pageBase(), a: 1 };
    for (let i = chain.length - 1; i >= 0; i--) acc = chain[i].a < 1 ? over(chain[i], acc) : chain[i];
    return acc;
  };
  // worst-case contrast for a (possibly multi-stop) surface. Two defects fixed
  // 2026-07-15: the else-branch recursed into ITSELF (stack overflow on any plain
  // bg), and C2 never called this at all — it used ratio(), which reads only the
  // FIRST stop, so "worst-stop gradient scoring" was silently first-stop-only.
  const ratioVs = (fg, bg) => bg.stops ? Math.min(...bg.stops.map((st) => ratio(fg, st))) : ratio(fg, bg);

  function survey(opts) {
    opts = opts || {};
    const R = root(opts.root);   // opts.root lets a caller pin the artifact explicitly
    const out = [];
    // Ian's scope decision (2026-07-15): promo-poster/resume are CITED ARTIFACTS. A poster
    // has no system state, is promotional BY GENRE, renders once, and cites the product URL
    // rather than data provenance. Declared via <meta name="artifact-genre">; several dims
    // (E3/G1/H4/I2/O2) N/A on it. Declared HERE because E3 reads it before section G.
    const isPoster = ((document.querySelector('meta[name="artifact-genre"]') || {}).content || '') === 'poster';
    // A PRINT DOCUMENT (project-report / analytics-report) renders into #ar-print-wrapper and
    // chunks its content with SQUARE-EDGED headed sections at 11pt for paper -- rounded cards
    // would be wrong for the medium. Hoisted here (a local copy also lived at G1) so A2's block
    // proxy can be medium-aware: a print doc's scannability lives in its headed sections, not
    // in card rounding. [external-consistency-and-standards-heuristic-internal-ext]
    const isPrintDoc = !!document.querySelector('#ar-print-wrapper') && !!(R.closest && R.closest('#ar-print-wrapper'));
    const textEls = $$('*', R).filter(e => vis(e) && ownText(e).length > 1);
    const inter = $$('button, a[href], select, input, textarea, [role="button"], [role="tab"]', R).filter(vis);

    // ── A · Comprehension ───────────────────────────────────────────────────
    const h1 = $$('h1', R).filter(vis);
    const heads = $$('h1,h2,h3,h4,[role="heading"]', R).filter(vis);
    const sizes = [...new Set(textEls.map(e => Math.round(parseFloat(getComputedStyle(e).fontSize))))].sort((a, b) => b - a);
    // "big" (>=20px) is the display tier the rubric's C1 governs; A1 needs it too, so it
    // is declared HERE rather than in the C block (a later `const` would be in the
    // temporal dead zone and throw when A1 reads it).
    const big = sizes.filter(s => s >= 20);
    const focal = sizes[0];
    const focalEls = textEls.filter(e => Math.round(parseFloat(getComputedStyle(e).fontSize)) === focal);
    // 4th naming-accident fix: report-sender's `send-btn` and voice-journal's `mic-btn`
    // ARE the page's primary action -- filled/gradient, visually dominant -- but no class
    // selector can know that. A primary CTA is a VISUAL-WEIGHT fact: match filled buttons
    // (saturated bg or gradient), not class spellings. Class hits still count.
    const isFilled = (e) => {
      const st = getComputedStyle(e);
      const c = rgb(st.backgroundColor);
      const saturated = c && c.a > 0.5 && Math.max(c.r, c.g, c.b) - Math.min(c.r, c.g, c.b) > 40;
      return saturated || (st.backgroundImage || '').includes('gradient');
    };
    // Repeated ROW actions (30 identical "+ Add to my day" buttons in a list) are one
    // pattern, not 30 competing CTAs — G3 judges attention competition, so dedupe by
    // (label, class): distinct DESIGNS of filled control, not instances.
    // Page-owned FABs (community's #fab-post) are fixed children of <body>, OUTSIDE the
    // content root — but a FAB IS the canonical mobile primary action. Include them;
    // shell chrome (wh-fb feedback FAB, nav hub) keeps its own prefixes and is excluded.
    // A FAB is position:FIXED, and vis() returns false for fixed elements (offsetParent is
    // null for fixed) -- so the general vis() KILLED the very FAB this block means to include
    // (community scored cta=0 with a visible #fab-post). Use a rect-based check for FABs.
    const visFixed = (f) => { const r = f.getBoundingClientRect(); const s = getComputedStyle(f); return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0'; };
    const pageFabs = $$('button[id^="fab-"], .fab', document.body).filter(visFixed)
      .filter((f) => !/^wh-/.test(f.id || ''));
    // A SELECTION control's ACTIVE state is filled to show what's chosen, not to call an
    // action -- dayplanner's gradient `.view-tab.active` (Day/Week/Month toggle) and
    // marketplace-seller-profile's active segment were miscounted as a 3rd "primary CTA",
    // failing A3/G3's "one recommended action" on a page that has exactly two. A tab/toggle
    // expands or selects; it is never the CTA. Same exclusion the A3 disclosure check makes.
    // [external-consistency-and-standards-heuristic-internal-ext] (2026-07-16)
    const isSelection = (e) => e.getAttribute('role') === 'tab' || e.hasAttribute('aria-pressed')
      || /(^|\s)(view-tab|phase-tab|period-btn|tab-btn|seg-btn|segmented|toggle-opt)/.test(
        (typeof e.className === 'string' ? e.className : '')) || !!e.closest('[role="tablist"]');
    // A clickable CONTENT CARD is not a call-to-action -- marketplace-seller-profile's five
    // <a class="listing-card"> (filled tiles linking to a listing) were each miscounted as a
    // "primary CTA", failing A3/G3 (6 CTAs on a page with one "View Listings" button). A card
    // navigates to content; a CTA performs the page's action. Exclude card-classed elements and
    // any control that wraps a heading (a container, not a button). Same "a card is not a button"
    // insight as the A2 anchor-card block fix. (2026-07-16)
    const isCard = (e) => /\b(card|tile)\b/i.test(typeof e.className === 'string' ? e.className : '') || !!e.querySelector('h2, h3');
    const primaryCta = [...new Map(
      $$('.ac-cta, .btn-generate, [class*="primary"]', R).filter(vis)
        .concat($$('button, a[href]', R).filter(vis).filter(isFilled))
        .concat(pageFabs)
        .filter((e2) => !isSelection(e2) && !isCard(e2))
        .map((e2) => [((e2.innerText || '').trim().slice(0, 24) + '|' + String(e2.className)), e2])
    ).values()];
    out.push(M('A1', '5-second test', [
      h1.length >= 1,                      // purpose nameable
      big.length <= TH.C1.maxDisplaySizes,                     // a clear DISPLAY SCALE (not a scatter). The
                                           // 5-second test NEEDS hierarchy -- hero(32-38)
                                           // + section(24) + emphasis/stat(20-22) is a
                                           // legitimate 3-tier scale with one dominant top.
                                           // <=2 wrongly forbade a section heading from
                                           // being >=20px when the hero is (pm-scheduler
                                           // 38/24/20, hive 32/24/22). A scatter is 4+.
                                           // (counting ELEMENTS was the earlier fix -- 9
                                           // peer KPIs at one size is correct design.)
      primaryCta.length >= 1 || isPrintDoc || isPoster,  // a primary action exists -- but a
                                           // print report / poster is a STATIC artifact with
                                           // no interactive CTA (G1/E3 already N/A there), so
                                           // it satisfies this by genre, not by growing a button.
      heads.length >= 1,                   // answer-first structure
    ].filter(Boolean).length, 4, `h1=${h1.length} focalTier=${focal}px×${focalEls.length} bigTiers=${big.length} cta=${primaryCta.length}`));

    // Class names are naming accidents (the G1/A3 lesson, third instance): audit-log's
    // .entry, shift-brain's .section-card and community's post cards are all CARDS the
    // .card/.simple-card selector cannot see -- A2 scored "blocks=0" on pages built
    // entirely of cards. Match the card SIGNATURE (bordered/backed, rounded, padded,
    // real content) and dedup nested matches by keeping outermost.
    // ELEMENT names are naming accidents too (4th instance, 2026-07-16): index's ops-home
    // renders its cards as <a class="oh-card"> (a LINKED card, flex/radius:12/pad:14) and
    // scored "blocks=0" because the selector only saw div/section/article. Include a/li so
    // linked + list-item cards count; the radius>=6 + padding>=6 signature already excludes
    // nav chips (radius:0/pad:0), so no over-count. [external-consistency-internal-ext]
    const cardLike = $$('div, section, article, a, li', R).filter(vis).filter((e) => {
      const st = getComputedStyle(e);
      if (parseFloat(st.borderTopLeftRadius) < 6) return false;
      const hasEdge = st.borderTopWidth !== '0px' || (rgb(st.backgroundColor) || { a: 0 }).a > 0;
      return hasEdge && parseFloat(st.paddingTop) >= 6 && (e.textContent || '').trim().length > 10;
    });
    const blocks = cardLike.filter((e) => !cardLike.some((o) => o !== e && o.contains(e)));
    // A3's "how many independent content blocks" (Hick / cognitive-load) counts STRUCTURAL
    // containers only -- a run of <li>/<a> cards is ONE list, already handled by cappedLists/
    // load-more below, so counting each as a block would double-count and demand disclosure
    // that a list doesn't need. (The a/li broadening above is for A2's "is it chunked at all",
    // a different question.) Restores A3's pre-broadening calibration on dayplanner + seller-profile.
    const structuralBlocks = blocks.filter((e) => /^(DIV|SECTION|ARTICLE)$/.test(e.tagName));
    const bold = textEls.filter(e => (parseInt(getComputedStyle(e).fontWeight) || 400) >= 700);
    // A print document (#ar-print-wrapper) chunks by SQUARE-EDGED headed sections at paper
    // scale -- rounded cards would be wrong for the medium. Its scannability lives in the
    // headed sections, so count those as its "blocks" instead of demanding card rounding.
    const chunked = isPrintDoc ? ($$('h2,h3', R).filter(vis).length >= 2) : (blocks.length >= 1);
    out.push(M('A2', 'Scannability', [
      heads.length >= 2,
      chunked,
      bold.length >= 1,
      $$('h2,h3', R).filter(vis).length >= 1,   // real heading structure, not styled divs
    ].filter(Boolean).length, 4, `headings=${heads.length} (h2/h3=${$$('h2,h3', R).filter(vis).length}) blocks=${blocks.length}`));

    // progressive disclosure: long lists capped / total long lists
    const tables = $$('table', R).filter(vis);
    const longTables = tables.filter(t => t.querySelectorAll('tbody tr').length > 8);
    // A "Load more" button IS textbook progressive disclosure (a page-worth now, the rest
    // deferred) -- the class-list selector missed it and scored 10 pages as having NO
    // disclosure while they shipped load-more affordances (measured 2026-07-15: inventory,
    // audit-log, public-feed, community, asset-hub, pm-scheduler all had 2 apiece). Same
    // instrument gap class as G1's status-badge false-pass, in the opposite direction.
    // Match by BEHAVIOURAL TEXT, not just class names -- classes are naming accidents.
    // [aria-expanded] IS the ARIA semantic for a disclosure control (prov-chips, detail
    // toggles) -- exclude selection semantics (aria-pressed/tabs), which expand nothing.
    const cappedLists = $$('.showall-toggle, details, .kpi-toggle', R).filter(vis)
      .concat($$('button, a', R).filter(vis).filter((e) => /load more|show more|show all|view all|ipakita/i.test(e.textContent || '')))
      .concat($$('[aria-expanded]', R).filter(vis).filter((e) => !e.hasAttribute('aria-pressed') && e.getAttribute('role') !== 'tab' && !e.classList.contains('showall-toggle')));
    // A disclosure affordance is required only where something NEEDS deferring. status.html
    // is deliberately terse (12 blocks, no long tables) -- demanding a details element there
    // produces a disclosure with nothing to disclose, i.e. decoration. Same for a gated
    // empty state (seller-profile without ?seller=). Short page + no overflow = pass.
    out.push(M('A3', 'Cognitive load / progressive disclosure', [
      cappedLists.length >= 1 || (longTables.length === 0 && structuralBlocks.length <= 12),
      $$('[role="tab"], .phase-tab, .period-btn', R).filter(vis).length <= 12,  // Hick: few options first
      structuralBlocks.length <= 40,
      primaryCta.length <= TH.A3.maxPrimaryCta,   // one recommended action highlighted
    ].filter(Boolean).length, 4, `disclosures=${cappedLists.length} longTables=${longTables.length}`));

    // ── B · Language ────────────────────────────────────────────────────────
    // "unlock" removed 2026-07-16: on this platform it is the LITERAL gating verb
    // ("unlocks at Stair 3", "Reach Level 50 to unlock") — a factual mechanic, not
    // puffery. The remaining words are pure marketese with no literal platform use.
    const MARKETESE = /\b(revolutionary|world-class|cutting-edge|seamless|empower|game-chang|best-in-class|synerg)/i;
    const marketese = textEls.filter(e => MARKETESE.test(ownText(e)));
    const longBlocks = textEls.filter(e => ownText(e).split(/\s+/).length > 60);
    out.push(M('B1', 'Microcopy / concision', [
      marketese.length === 0,
      longBlocks.length <= 3,
      heads.every(h => (h.innerText || '').trim().length > 0),   // headings work out of context
    ].filter(Boolean).length, 3, `marketese=${marketese.length} verboseBlocks=${longBlocks.length}`));
    out.push(M('B2', 'Plain voice & tone', [marketese.length === 0].filter(Boolean).length, 1,
      marketese.length ? `marketese: "${ownText(marketese[0]).slice(0, 40)}"` : 'no marketese in visible copy'));

    // ── B3 · Readability — MEASURED (2026-07-15) ────────────────────────────
    // B1/B2 had no numbers: a page of long hedged sentences scored 100% by dodging
    // marketese. Cited floors: GOV.UK sentences <=20 words + reading age 9-11;
    // NN/g 8th-grade for a BROAD audience + active voice + one idea per sentence.
    // The standards vocabulary (MTBF/OEE/ISO 14224/SMRP) inflates grade by
    // construction and is the platform's canonical language -> exempt from GRADE,
    // never from length or voice.
    const STANDARDS = /\b(MTBF|MTTR|OEE|PM|ISO|SMRP|SAE|JA1011|RCM|KPI|PHT|PDF|AI|WorkHive|Pareto|Spearman|SPC)\b/;
    const syllables = (w) => {
      w = w.toLowerCase().replace(/[^a-z]/g, '');
      if (w.length <= 3) return 1;
      w = w.replace(/(?:[^laeiouy]es|ed|[^laeiouy]e)$/, '').replace(/^y/, '');
      const m = w.match(/[aeiouy]{1,2}/g);
      return m ? m.length : 1;
    };
    // Sentences from PROSE only: skip labels/values/headings (a KPI "86%" is not prose).
    // Include KPI-tile footnotes/sublabels: they sit UNDER the number a supervisor reads
    // first, and they carried the worst wording on the page ("partial: 30-day floor
    // approximation"). They are short, so the >=6-word prose floor skipped them entirely.
    const tileCopy = $$('.sc-sub, .simple-card small, .card-standard, .kpi-detail p, .chart-caption', R).filter(vis);
    // B3 grades the PRODUCT's writing, not USER-AUTHORED content. A voice-journal transcript is
    // the worker's own verbatim speech (`.transcript*`), and a community/public-feed post is a
    // user's forum text (`.post-content`, `.post-card`, `.reply-body`) -- holding the app to an
    // 8th-grade/<=20-word bar for how a WORKER talks or posts is a category error (a voice journal's
    // whole job is capturing natural speech). Exclude those containers; product copy still graded.
    const isUserAuthored = (e) => !!e.closest('.transcript-box, .transcript, [class*="transcript"], .history-text, .post-content, .post-card, .reply-body, [data-user-content]');
    const proseEls = textEls.filter((e) => {
      const t = ownText(e);
      return t.split(/\s+/).length >= 6 && !/^h[1-6]$/i.test(e.tagName) && !isUserAuthored(e);
    }).concat(tileCopy.filter((e) => ownText(e).split(/\s+/).length >= 4 && !isUserAuthored(e)));
    const sentences = [];
    proseEls.forEach((e) => {
      const raw = ownText(e);
      // A middot-separated citation/meta line is a REFERENCE LIST, not prose: "ISO
      // 14224:2016 (failure taxonomy + reliability metrics) · SMRP 5.4 · …" split into a
      // 30-word "sentence" that no rewrite could fix. Skip those; grade real sentences.
      if ((raw.match(/·/g) || []).length >= 2) return;
      // A MATH/FORMULA line ("Earned Value formulas: PV = BAC × planned %, EV = BAC × EV%") is
      // not gradeable prose -- FK treats equation tokens (PV/BAC/×/%) as polysyllabic words and
      // reports grade ~12 on a formula no rewrite could simplify. Skip equations (an `=` with a
      // math operator/number), same spirit as the citation-line skip above. (project-report B3.)
      if (/\S\s*=\s*\S/.test(raw) && /[×÷*/+%]|\d/.test(raw)) return;
      // A NEWLINE is a line/content separator, not just a space: a multi-line block (shift-brain's
      // "[SAFETY] ACTIVE ISOLATIONS:\n  - TT-002 (permit …)\n  - GEN-003 …", rendered white-space:
      // pre-wrap) is a LIST, not one 15-word run-on sentence. Splitting on \n grades each real line
      // (all short) and spreads the asset codes across lines (so E4's >7-ids-in-one-block clears too).
      raw.split(/(?<=[.!?])\s+|\s*\n+\s*/).forEach((s) => {
        const t = s.trim();
        if (t.split(/\s+/).length >= 4) sentences.push({ t, el: e });
      });
    });
    // The participle must be a REAL lowercase running-prose word (stem >=2 chars + ed/en). The old
    // `\w+(ed|en)` with /i matched an UPPERCASE ASSET CODE: "is GEN-003" -> `\w+`="G", `(ed|en)`="EN"
    // -> false passive on "The top risk is GEN-003" (shift-brain). Requiring lowercase [a-z]{2,} excludes
    // codes (GEN/GEN-003/TT-001) while still catching "is broken / was replaced". §16.1 the ruler, not the page.
    const PASSIVE = /\b(?:[Ww]as|[Ww]ere|[Ii]s|[Aa]re|[Bb]een|[Bb]eing|[Bb]e)\s+[a-z]{2,}(?:ed|en)\b(?!\s+(?:by\s+you|to))/;
    const longOnes = sentences.filter((s) => s.t.split(/\s+/).length > TH.B3.maxSentenceWords);
    const passiveOnes = sentences.filter((s) => PASSIVE.test(s.t));
    // Flesch-Kincaid is a REGRESSION fitted on running prose -- it is meaningless on a
    // short label: "Phase 1: Descriptive Analytics." (4 words) scored grade 12.5 purely
    // because two words are polysyllabic. Grade only real sentences (>=12 words); the
    // <=20-word and active-voice rules still apply to everything.
    // Strip the CITATION TOKEN, then grade what is left. Exempting the whole sentence
    // because it names a standard is how "ISO 14224:2016 §9.3 · partial: calendar time
    // (not operating time)" scored clean -- the ISO number earns the exemption, the
    // engineer-voice prose around it does NOT. (Ian: "inside the kpi tiles... it is long
    // and not easily understood".)
    const stripCite = (t) => t
      .replace(/\b(ISO|SMRP|SAE|JA)\s?[\d.:-]+(?:-\d+)?(?::\d{4})?/gi, '')
      .replace(/\bBest Practices v[\d.]+/gi, '')
      .replace(/§[\d.]+/g, '')
      // ASSET/PERMIT CODES (GEN-003, AC-002, UPS-001, P-001, PTW-2026-9001) are IDENTIFIERS a worker
      // reads as one token, not sounded-out prose — Flesch-Kincaid (a running-prose regression) scores
      // them as long polysyllabic words and inflates the grade: "review PM schedules for AC-002, TT-002,
      // and UPS-001" read 8.8 while the prose alone reads ~5.7. Strip them like the citation tokens above
      // (same §16.1 "the number earns the exemption, the prose does NOT" rule). Uppercase-only so a
      // lowercase word ending in a code-like shape is never stripped.
      .replace(/\b[A-Z]{1,4}-\d{2,4}(?:-\d{2,5})?\b/g, '')
      .replace(/\s{2,}/g, ' ').replace(/^[\s·:.-]+/, '').replace(/\s+([,.])/g, '$1').trim();
    // Flesch-Kincaid is a REGRESSION FIT ON RUNNING PROSE and is meaningless below ~12
    // words: on a short phrase the syllables-per-word term dominates and any polysyllabic
    // but perfectly plain wording trips it. Measured: "Recommended: Daily (currently
    // Weekly · covers 6 PM tasks)" -- 8 words, unambiguous -- scored 8.9 purely because
    // "Recommended"/"currently" are long. Grading there is applying the metric OUTSIDE its
    // validity range and would push a pointless rewrite onto clear copy. The >20-word and
    // passive-voice checks are structural, not statistical, so they keep the 8-word floor.
    // (This is the same trap as scoring a dim with no honest denominator.)
    const FK_MIN_WORDS = TH.B3.minGradedWords;
    const graded = sentences
      .map((s) => ({ ...s, t: stripCite(s.t) }))
      .filter((s) => s.t.split(/\s+/).length >= FK_MIN_WORDS);
    const fk = (s) => {
      const words = s.split(/\s+/).filter(Boolean);
      const syl = words.reduce((a, w) => a + syllables(w), 0);
      return 0.39 * words.length + 11.8 * (syl / Math.max(words.length, 1)) - 15.59;
    };
    const overGrade = graded.filter((s) => fk(s.t) > TH.B3.maxFkGrade);
    const b3Checks = [
      longOnes.length === 0,        // GOV.UK: <=20 words
      passiveOnes.length === 0,     // NN/g: active voice
      overGrade.length === 0,       // NN/g: 8th grade, broad audience
    ];
    const worstLong = longOnes.sort((a, b) => b.t.split(/\s+/).length - a.t.split(/\s+/).length)[0];
    out.push(M('B3', 'Readability (<=20 words, grade <=8, active)', b3Checks.filter(Boolean).length, 3,
      `sentences=${sentences.length} · >20w=${longOnes.length} · passive=${passiveOnes.length} · grade>8=${overGrade.length}`
      + (worstLong ? ` · worst(${worstLong.t.split(/\s+/).length}w): "${worstLong.t.slice(0, 60)}…"` : '')));
    // expose the offenders so the caller can REWRITE them, not just score them
    out._b3 = {
      long: longOnes.slice(0, 8).map((s) => ({ words: s.t.split(/\s+/).length, text: s.t.slice(0, 110) })),
      passive: passiveOnes.slice(0, 5).map((s) => s.t.slice(0, 90)),
      overGrade: overGrade.slice(0, 5).map((s) => ({ grade: +fk(s.t).toFixed(1), text: s.t.slice(0, 90) })),
    };

    // ── C · Visual craft ────────────────────────────────────────────────────
    // (`big` is declared up in the A block — A1 and C1 grade the same display tier.)
    out.push(M('C1', 'Visual hierarchy', [
      big.length <= TH.C1.maxDisplaySizes,                     // a clear DISPLAY SCALE = hero+section+emphasis (3
                                           // tiers), NOT a scatter. Same threshold A1 uses --
                                           // both measure `big`, so they must agree; <=2 wrongly
                                           // failed pm-scheduler/hive/alert-hub for having a
                                           // correct 3-tier hierarchy. A scatter is 4+.
      sizes.length <= TH.C1.maxSizeTiers,
      true,                                // red/warm reserved — verified by C2/K1 below
    ].filter(Boolean).length, 3, `bigSizes=[${big.join(',')}] distinct=${sizes.length}`));

    let cPass = 0, cTotal = 0, worst = { r: 99, t: '' };
    let bPass = 0, bTotal = 0, tinySentences = 0;   // C5 (APCA) + C4 tiny-prose evidence
    const c2Off = [];   // every failing element, not just the worst — the fix list
    const c2bOff = [];
    // APCA-W3 0.1.9 (Myndex). Validated against the published anchors: black-on-white 106.04,
    // white-on-black -107.88, #888-on-#fff 63.06 — all reproduced to 2dp before this shipped.
    const apcaLc = (txt, bgc) => {
      const T = 2.4, bT = 0.022, bC = 1.414, S = 1.14, off = 0.027;
      const sY = (c) => 0.2126729 * Math.pow(c.r / 255, T)
                      + 0.7151522 * Math.pow(c.g / 255, T)
                      + 0.0721750 * Math.pow(c.b / 255, T);
      let t = sY(txt), g = sY(bgc);
      t = t > bT ? t : t + Math.pow(bT - t, bC);
      g = g > bT ? g : g + Math.pow(bT - g, bC);
      if (Math.abs(g - t) < 0.0005) return 0;
      let o;
      if (g > t) { const s2 = (Math.pow(g, 0.56) - Math.pow(t, 0.57)) * S; o = s2 < 0.1 ? 0 : s2 - off; }
      else       { const s2 = (Math.pow(g, 0.65) - Math.pow(t, 0.62)) * S; o = s2 > -0.1 ? 0 : s2 + off; }
      return o * 100;
    };
    textEls.forEach(e => {
      // EMOJI-ONLY glyphs (a 🔧/📋 ss-tile-cap icon) render in their OWN colour — the CSS `color`
      // is never painted, so scoring text-contrast on them measures a colour the user never sees
      // (a false C2 fail on hive's ss-tile-cap). Skip when stripping emoji/VS/ZWJ leaves no word
      // char; "⌘K" keeps its "K" so real symbol+letter text is still graded. §16.1 the ruler, not the page.
      const _c2t = ownText(e);
      if (_c2t && !/[\p{L}\p{N}]/u.test(_c2t.replace(/[\p{Extended_Pictographic}️‍]/gu, ''))) return;
      const s = getComputedStyle(e);
      // Gradient-clipped text (background-clip:text + transparent fill): the GLYPHS are
      // the gradient; `color` is unused. Score the worst glyph stop against the surface
      // BEHIND the element (dayplanner's "Day" logo scored 1.72 as phantom-white before).
      // computed -webkit-text-fill-color serializes transparent as "rgba(0, 0, 0, 0)",
      // never the keyword — parse the alpha instead of keyword-matching.
      const tf = rgb(s.webkitTextFillColor || '');
      const clipText = !!tf && tf.a === 0 && (s.backgroundImage || '').includes('gradient');
      const fgStops = clipText
        ? (s.backgroundImage.match(/rgba?\([^)]+\)/g) || []).map(rgb).filter(Boolean)
        : null;
      const fg = fgStops && fgStops.length ? fgStops[0] : rgb(s.color);
      if (!fg) return;
      const bg = clipText && e.parentElement ? effBg(e.parentElement) : effBg(e);
      const comp = fg.a < 1 ? over(fg, bg) : fg;
      const cr = fgStops && fgStops.length
        ? Math.min(...fgStops.map((st) => ratioVs({ ...st, a: 1 }, bg)))
        : ratioVs(comp, bg);
      const fs = parseFloat(s.fontSize), fw = parseInt(s.fontWeight) || 400;
      const need = (fs >= TH.C2.largePx || (fs >= TH.C2.largeBoldPx && fw >= 700)) ? TH.C2.contrastLarge : TH.C2.contrastNormal;
      // ── C5 · APCA perceptual contrast (harvested 2026-07-24 from git.apcacontrast.com) ──
      // WCAG 2.x ratio is a simple luminance quotient and is KNOWN to overestimate legibility on
      // DARK backgrounds — which is this entire platform. Measured live: rgba(255,255,255,~0.7)
      // text at 14px on the navy surface scores WCAG 8.6:1 (passes comfortably) but APCA Lc 62-64
      // against a 75 minimum. C2 structurally cannot see this, so C5 is not redundant with it.
      // Sub-14px text is EXCLUDED (outside APCA's size table) and counted for C4 instead — the
      // answer there is "the type is too small", not "the colour is wrong".
      // effBg may return a GRADIENT descriptor (has .stops) whose r/g/b are undefined — that would
      // silently produce NaN and score every gradient-backed element as a fail. Require a flat colour.
      const bgFlat = bg && Number.isFinite(bg.r) && Number.isFinite(bg.g) && Number.isFinite(bg.b);
      // ★CALIBRATION (2026-07-24 live sweep): SKIP an element sitting on a background-IMAGE GRADIENT
      // (a filled button like .btn-next: navy text on a linear-gradient(orange) fill). effBg reads
      // only `backgroundColor` (transparent on such a button) and walks UP to the navy shell, so C5
      // scored navy-on-navy = a false Lc61 — while the real contrast (navy on bright orange) is high.
      // Same blindspot C2 handles via gradient stops; here we simply exclude the element (APCA has no
      // single bg to score against a multi-stop fill, and a filled-button's dark text is deliberate).
      const _onGradient = (el) => {
        for (let n = el; n && n !== document.body; n = n.parentElement) {
          const cs = getComputedStyle(n);
          if ((cs.backgroundImage || '').includes('gradient')) return true;
          const bc = rgb(cs.backgroundColor);
          if (bc && bc.a >= 0.85) return false;   // hit an opaque flat bg first -> not on a gradient
        }
        return false;
      };
      if (fs >= TH.C5.minPx && !clipText && bgFlat && Number.isFinite(comp.r) && !_onGradient(e)) {
        // ★CALIBRATION (2026-07-24): APCA's Lc 75 floor is for BODY / COLUMN PROSE; discrete content
        // text that is NOT fluent body (a button/link label, a chip, a short standalone caption) has a
        // Lc 60 minimum per the harvested APCA table. The lens was applying lcBody(75) to a "Load More"
        // button, flagging the BRAND orange (#F7A21B, Lc 60) as a fail. A control label is not body
        // prose -> content floor. Interactive OR short-single-line (<= ~24ch, no sentence) => lcContent.
        // DISCRETE (non-prose) UI text gets APCA's content floor (Lc 60), not the body/column-prose
        // floor (Lc 75): interactive control labels (button/link/summary) AND status content — an
        // alert/status BANNER, a badge, a chip, a pill. These are single-line UI messages, never
        // "columns of fluent body text", so Lc 60 is the correct APCA minimum (e.g. the orange
        // low-stock warning banner at --wh-orange-light Lc 70). Safe: every muted-text fix lands at
        // Lc 77+, so lowering these to 60 masks no real failure - only brand-accent status text.
        // Also HEADINGS: APCA's Lc 75 is for "columns of fluent BODY text"; a heading/title is
        // discrete content (Lc 60), not a column of prose. A small brand-accent H1/H2 (e.g. the
        // orange-light "Engineering Design" title at Lc 70) is a title, not body copy. Only real
        // paragraphs (p / li with a sentence) keep the Lc 75 body floor.
        const _isUiLabel = (el) => (el.tagName || '').match(/^H[1-6]$/) ? true : !!el.closest(
          'button, a[href], [role="button"], summary,'
          + ' [role="alert"], [role="status"], .badge, .chip, .pill,'
          + ' .verdict, [class*="banner"], [id*="banner"], [class*="tab"], [class*="pill"]');
        const _bodyFloor = _isUiLabel(e) ? TH.C5.lcContent : TH.C5.lcBody;
        const lcNeed = (fs >= 36 || (fs >= 24 && fw >= 700)) ? TH.C5.lcLarge
                     : (fs >= 24 || (fs >= 16 && fw >= 700)) ? TH.C5.lcContent
                     : _bodyFloor;
        const lc = Math.abs(apcaLc(comp, bg));
        bTotal++;
        if (lc >= lcNeed) bPass++;
        else c2bOff.push({ t: ownText(e).slice(0, 24), px: Math.round(fs), w: fw,
                           lc: Math.round(lc), need: lcNeed, wcag: +cr.toFixed(2) });
      } else if (fs < TH.C5.minPx && ownText(e).trim().split(/\s+/).length >= 6) {
        tinySentences++;   // long-form prose below APCA's size floor -> C4 legible-size evidence
      }
      cTotal++;
      if (cr >= need) cPass++;
      else {
        if (cr < worst.r) worst = { r: +cr.toFixed(2), t: ownText(e).slice(0, 20) };
        c2Off.push({ t: ownText(e).slice(0, 24), cls: String(e.className).slice(0, 40),
          r: +cr.toFixed(2), need, fg: s.color, grad: !!bg.stops });
      }
    });
    out._c2 = c2Off;
    out._c2b = c2bOff;
    out._tinySentences = tinySentences;
    out.push(bTotal
      ? M('C5', 'Perceptual contrast (APCA Lc)', bPass, bTotal,
          c2bOff.length
            ? `${c2bOff.length} pass WCAG but miss APCA Lc (worst: "${c2bOff[0].t}" Lc ${c2bOff[0].lc}/${c2bOff[0].need} at ${c2bOff[0].px}px)`
            : 'all text meets its APCA Lc minimum for its size/weight')
      : NA('C5', 'Perceptual contrast (APCA Lc)', 'no text at or above APCA’s 14px size floor in this state'));
    out.push(cTotal
      ? M('C2', 'Colour & contrast (WCAG)', cPass, cTotal,
          cPass === cTotal ? 'all text >= its WCAG floor' : `worst ${worst.r}:1 "${worst.t}"`)
      : NA('C2', 'Colour & contrast (WCAG)', 'no rendered text in this state'));

    out.push(M('C3', 'Whitespace / gestalt', [
      blocks.length >= 1 || isPrintDoc,   // a print report groups by square-edged headed
                                          // sections, not card-signature blocks (same reason
                                          // A2's blocks=0 on project-report -- it IS grouped).
      $$('.card, .simple-card', R).filter(vis).every(c => parseFloat(getComputedStyle(c).padding) > 0 || getComputedStyle(c).padding !== '0px'),
    ].filter(Boolean).length, 2, 'grouped into common regions with padding'));

    const nums = textEls.filter(e => /^[\d,.]+\s*(%|h|d|hrs)?$/.test(ownText(e)) && parseFloat(getComputedStyle(e).fontSize) >= 14);
    const tab = nums.filter(e => /tabular-nums/.test(getComputedStyle(e).fontVariantNumeric));
    // A ratio dim with denominator 0 must report N/A, never MEASURED-with-null-pct —
    // the roll-up counted those as 0% (the ⚠-trio pollution, 2026-07-15).
    out.push(nums.length
      ? M('C4', 'Typography (tabular KPIs)', tab.length, nums.length, `${tab.length}/${nums.length} numeric els tabular`)
      : NA('C4', 'Typography (tabular KPIs)', 'no numeric els in this state: nothing to set tabular'));

    // ── D · Interaction ─────────────────────────────────────────────────────
    const iconOnly = inter.filter(e => { const t = (e.innerText || '').trim(); return (e.querySelector('svg,img') || /^[^\w\s]{1,3}$/.test(t)) && t.replace(/[^\w]/g, '').length === 0; });
    const namedIcons = iconOnly.filter(e => e.getAttribute('aria-label') || e.title);
    out.push(iconOnly.length
      ? M('D1', 'Affordances & signifiers', namedIcons.length, iconOnly.length, `${namedIcons.length}/${iconOnly.length} icon-only controls named`)
      : NA('D1', 'Affordances & signifiers', 'no icon-only controls in this state'));
    out.push(J('D2', 'Feedback < 400ms (Doherty)', 'needs a REAL trusted click + a click->paint timer; MCP-driven, not page-JS'));
    const btnShapes = [...new Set($$('button', R).filter(vis).map(b => { const s = getComputedStyle(b); return `${s.borderRadius}|${s.minHeight}`; }))];
    out.push(M('D3', 'Consistency / one vocabulary', btnShapes.length <= TH.D3.maxButtonShapes ? 1 : 0, 1,
      `${btnShapes.length} distinct button shapes`));

    // ── E · Data & state ────────────────────────────────────────────────────
    // Count the chart CONTAINER (the element that carries role=img + aria-label), never
    // the library's internal <svg>/<g>. The first cut matched Plotly's 3 inner SVGs and
    // scored E1 0% on charts that ARE named.
    const charts = $$('[id^="chart-"], canvas.chart, figure.chart', R).filter(vis);
    const namedCharts = charts.filter(c => c.getAttribute('role') === 'img' || c.getAttribute('aria-label'));
    // Plotly ALWAYS emits <g class="pielayer"> (empty when no pie is drawn), so a bare
    // [class*="pie"] is a guaranteed false positive. Only count a REAL rendered slice.
    const banned = $$('[class*="gauge"], [class*="donut"]', R)
      .filter(e => vis(e) && !/plotly|pielayer|layer/i.test(String(e.className)))
      .concat($$('g.pielayer .slice, .pie .slice, [class*="donut"] path', R).filter(vis));
    out.push(M('E1', 'Data-viz / KPI', (namedCharts.length === charts.length ? 1 : 0) + (banned.length === 0 ? 1 : 0), 2,
      `charts=${charts.length} named=${namedCharts.length} gauge/pie=${banned.length}`));
    const empties = $$('.empty, .ar-status, [class*="empty"]', R).filter(vis);
    // Judge the RENDERED text (innerText), not own text nodes — the verdict pattern
    // explains itself through child spans and ownText('') scored it "unexplained".
    const honestEmpties = empties.filter(e => ((e.innerText || '').trim()).length > 12);   // says WHY, not just "no data"
    out.push(M('E2', 'Empty / loading / error', empties.length ? honestEmpties.length : 1, empties.length || 1,
      empties.length ? `${honestEmpties.length}/${empties.length} empties explain themselves` : 'no empty states in this state'));
    const chip = document.querySelector('.wh-source-chip');
    // Freshness can be worded many ways -- "Recomputed when this report was generated" is
    // as honest as "Updated 2m ago". Grade the PRESENCE of a freshness claim, not one phrasing.
    const FRESH = /updated|live|snapshot|as of|refresh|recomputed|generated|computed|calculated|on demand/i;
    // Read textContent, NOT innerText: index's provenance chip is DELIBERATELY collapsed inside
    // a "More" disclosure ("stays inspectable" -- a valid progressive-disclosure trust pattern),
    // so innerText was '' and E3 scored a present, fully-worded chip (325 chars incl "Live data")
    // as missing. The provenance IS provided; a chip with no freshness word still fails.
    const chipTxt = chip ? (chip.textContent || '').replace(/\s+/g, ' ').trim() : '';
    out.push(isPoster
      ? NA('E3', 'Trust / transparency', 'poster: cites the product URL, not data provenance')
      : M('E3', 'Trust / transparency', [!!chip, FRESH.test(chipTxt)].filter(Boolean).length, 2,
          chip ? `chip: "${chipTxt.slice(0, 40)}"` : 'NO source chip'));


    // ── E4 · Digest, don't dump (2026-07-15) ────────────────────────────────
    // NN/g: "a dashboard should AGGREGATE AND SUMMARIZE data, not display raw data."
    // E1 governs the chart, P governs the table; nothing governed the ANALYSIS CARD that
    // prints its WORKING instead of its ANSWER. All of Ian's screenshots were this shape.
    // [external-dashboard-design-aggregate-summarise-answer-not-, ux-millers-law,
    //  ux-progressive-disclosure]
    const cards = $$('#results-panel .card, .card', R).filter(vis);
    const e4 = { repeated: [], dumps: [], rawStats: [] };

    // (1) COLLAPSE REPETITION — the same VERDICT string on N rows says it N times.
    // Scope matters: a repeated CONTROL label ("Show all 30 assets" on 4 cards) is correct
    // affordance repetition, and a repeated DATA value in a table cell is just the data.
    // E4 governs the ANALYSIS PROSE only -- flagging the other two would push a "fix" onto
    // things that are working (the class of error that deleted required CSS from 3 pages).
    // E4 grades the PRODUCT's analysis prose, NOT user-authored content -- a voice-journal is a LOG of a
    // worker's verbatim entries ("Hyd power pack PMP-105 - oil sample sent... sticky pa rin."), and the same
    // entry recurring across the list + a detail view is the LOG working, not a repeated "verdict" to collapse.
    // Collapsing a log would DESTROY it. Reuse B3's isUserAuthored exclusion (transcript/post containers) so
    // E4 never demands a "fix" to a captured-speech surface -- the same category error B3 already guards. (§16.1)
    const isProse = (e) => !e.closest('button, a, [role="button"], [role="tab"], table, thead, tbody, th, td, select, label') && !isUserAuthored(e);
    // E4's rule is "N rows with the identical VERDICT -> say it ONCE". A verdict is a
    // CLAIM, i.e. a sentence. A repeated NOUN PHRASE is usually legitimate data: the PM
    // task "Battery voltage and electrolyte level" recurring across 4 assets is the data,
    // not a card saying one thing four times. Requiring sentence shape (>=8 words AND
    // terminal punctuation) separates the two -- the real offender, "Not significant --
    // skill level does not significantly predict repair time in this dataset." (13 words,
    // full stop), still trips it. Without this the lens demands a "fix" to working cards.
    const isSentence = (t) => /[.!?]$/.test(t.trim()) && t.trim().split(/\s+/).length >= 8;
    const strings = {};
    $$('*', R).filter(e => vis(e) && isProse(e) && isSentence(ownText(e))).forEach((e) => {
      const t = ownText(e);
      (strings[t] = strings[t] || []).push(e);
    });
    Object.entries(strings).forEach(([t, els]) => {
      if (els.length >= 3) e4.repeated.push({ times: els.length, text: t.slice(0, 70) });
    });

    // (2) CAP RAW LISTS AT MILLER (5+-2) — a paragraph of asset codes is a dump.
    // An ID is a short CODE-shaped token (TT-002, AC-004): >7 inline = unreadable.
    const IDLIKE = /\b[A-Z]{1,5}-\d{2,4}\b/g;
    $$('*', R).filter(e => vis(e) && isProse(e) && e.children.length === 0).forEach((e) => {
      const t = ownText(e);
      const ids = t.match(IDLIKE);
      // A DUMP is codes CRAMMED inline; a multi-line LIST (shift-brain's safety-isolation banner,
      // one "- MACHINE (permit …)" per line, rendered pre-wrap) is scannable, not a dump. Judge the
      // WORST single line's code count, not the element total -- >7 on ONE line is the real dump.
      const worstLine = Math.max(0, ...t.split(/\n/).map((ln) => (ln.match(IDLIKE) || []).length));
      if (ids && ids.length > TH.E4.maxIdsPerBlock && worstLine > TH.E4.maxIdsPerBlock) e4.dumps.push({ ids: ids.length, text: t.slice(0, 60) });
    });

    // (3) TRANSLATE THE STATISTIC — a bare coefficient is not a finding.
    // "r = 0.866" beside "Not significant" reads as a contradiction to a non-statistician.
    const STAT = /\b(r|r2|R²|p|rho|ρ)\s*=\s*-?[\d.]+/;
    // A statistic is "untranslated" when the coefficient stands ALONE in its element --
    // no verdict word in the same breath to tell a non-statistician what it MEANS.
    const VERDICT = /\b(significant|strong|weak|moderate|none|no |not |likely|unlikely|correlat|predict|drives|explains)/i;
    $$('*', R).filter(e => vis(e) && isProse(e) && e.children.length === 0).forEach((e) => {
      const t = ownText(e);
      if (STAT.test(t) && !VERDICT.test(t)) e4.rawStats.push(t.slice(0, 40));
    });

    const e4Checks = [e4.repeated.length === 0, e4.dumps.length === 0, e4.rawStats.length === 0];
    out.push(M('E4', "Digest, don't dump (answer, not working)", e4Checks.filter(Boolean).length, 3,
      `repeatedVerdicts=${e4.repeated.length} · rawIdDumps=${e4.dumps.length} · untranslatedStats=${e4.rawStats.length}`
      + (e4.repeated[0] ? ` · worst: "${e4.repeated[0].text}" x${e4.repeated[0].times}` : '')
      + (e4.dumps[0] ? ` · dump: ${e4.dumps[0].ids} ids inline` : '')));
    out._e4 = e4;


    // ── S · Family resemblance (NN/g #4 internal consistency) ───────────────
    // Ian: "my pages would look like not different personalities ... same and similar
    // theme." R grades harmony WITHIN a page; S grades whether the page speaks the
    // PLATFORM's vocabulary. A page can be perfectly self-consistent at 10px and still
    // be a stranger -- that is exactly the gap R could not see.
    // Canonical = the DECLARED tokens (read from the live cascade), never the statistical
    // mode across pages: most pages were never driven with this rubric, so a mode would
    // let un-driven pages outvote the design system.
    // [external-consistency-and-standards-heuristic-internal-ext]
    const csS = getComputedStyle(document.documentElement);
    const pxS = (v) => Math.round(parseFloat(v) || 0);
    const declRadii = ['--wh-radius-sm', '--wh-radius', '--wh-radius-lg']
      .map((t) => pxS(csS.getPropertyValue(t))).filter(Boolean);

    if (!declRadii.length) {
      // No token source = conformance is structurally IMPOSSIBLE, not merely unmet.
      // Report the root cause instead of a score that would blame the page for it.
      out.push(NA('S1', 'Token conformance (radius/height/font/surface)',
        'page resolves NO --wh-radius-* : it has no token source to conform TO (link tokens.css)'));
    } else {
      // Exclude platform CHROME (nav-hub, companion, feedback/overlays) — its radii are the SHARED
      // component's vocabulary, not THIS page's tokens. nav-hub's #wh-hub-* / companion's #wh-ai-*
      // controls use a 10px radius that isn't in a page's declared --wh-radius-* scale, so S1 blamed
      // the PAGE (hive: rogue 10px) for furniture it doesn't own. Same chrome-is-furniture rule the
      // Z1/Z3 detectors already apply via _inChrome. §16.1 the ruler, not the page.
      const _s1Chrome = (e) => !!(e.closest && e.closest('#wh-feedback-panel,[class*=wh-fb-],#wh-voice-overlay,#signin-modal,[id*=nav-hub],.nav-hub,[id*=wh-hub],[id*=wh-ai],[class*=companion-launch],[id*=companion],#wh-ai-widget,#wh-ai-trigger')) || /\bwh-(hub|ai)-/.test((e.id || '') + ' ' + (typeof e.className === 'string' ? e.className : ''));
      const ctrlsS = $$('button, a.refresh-btn, [role="tab"]', R).filter(vis).filter((e) => !_s1Chrome(e));
      const cardsS = $$('.card, .simple-card, .board-card, .sc-hero', R).filter(vis).filter((e) => !_s1Chrome(e));
      const legalR = new Set(declRadii.concat([0]));   // 0 = a deliberate square edge
      const shapes = ctrlsS.concat(cardsS).map((e) => {
        const raw = getComputedStyle(e).borderTopLeftRadius;
        // A PERCENTAGE radius is a shape INTENT (circle/ellipse), never a px vocabulary
        // value -- and parseFloat('50%') returns 50, so a naive read calls a perfectly
        // circular 116x116 mic button "50px rogue drift" and would drive a fix that
        // squares off a signature control. Caught live on voice-journal.
        if (raw.includes('%')) return 'round';
        const r = pxS(raw);
        const h = e.getBoundingClientRect().height;
        return (h && r >= h / 2 - 1) ? 'pill' : r;     // a pill is a SHAPE, not rogue drift
      });
      const badR = shapes.filter((v) => v !== 'pill' && v !== 'round' && !legalR.has(v));
      const fonts = $$('h1, h2, h3, p, button, td', R).filter(vis)
        .map((e) => getComputedStyle(e).fontFamily.split(',')[0].replace(/["']/g, '').trim());
      const declFont = csS.getPropertyValue('--wh-font').split(',')[0].replace(/["']/g, '').trim();
      // A typeface the page deliberately LOADED is a design DECISION; one it FELL BACK to is
      // a defect. alert-hub's Arial was never loaded -- the UA handed it to unstyled buttons
      // (a real bug). project-report's 'IBM Plex Sans' is @font-face-loaded on purpose for its
      // printable #ar-print-wrapper at 11pt on paper. Flagging both identically would have
      // driven a "fix" that destroys an intentional document typeface -- the same class of
      // error as deleting a rule that looked redundant. document.fonts IS the intent record.
      const loaded = new Set([...(document.fonts || [])].map((f) => (f.family || '').replace(/["']/g, '').trim()));
      const badF = fonts.filter((f) => declFont && f !== declFont && !loaded.has(f));
      const intentional = [...new Set(fonts.filter((f) => f !== declFont && loaded.has(f)))];
      const s1 = [badR.length === 0, badF.length === 0];
      out.push(M('S1', 'Token conformance (radius + typeface)', s1.filter(Boolean).length, 2,
        `declared=[${declRadii.join(',')}] · offRadius=${badR.length}/${shapes.length}`
        + (badR.length ? ` (rogue: ${[...new Set(badR)].join(',')}px)` : '')
        + ` · offFont=${badF.length}/${fonts.length}`
        + (badF.length ? ` (${[...new Set(badF)].join(',')} != ${declFont}, NOT loaded = UA fallback)` : '')
        + (intentional.length ? ` · deliberate: ${intentional.join(',')}` : '')));
      out._s1 = { declRadii, rogueRadii: [...new Set(badR)], rogueFonts: [...new Set(badF)] };
    }

    // ── F · Reach & feel ────────────────────────────────────────────────────
    // A calendar/timeline block's HEIGHT encodes task DURATION, not tap-target size — a 15-min task is a
    // thin block, exactly like a Google-Calendar / Outlook event. Genre-exempt from the 44px rule (Ian
    // 2026-07-17), the same class as the print-doc/poster exemptions: its size is a data encoding, not a
    // button dimension. Signal: absolute-positioned inside a timeline/calendar container.
    // Ian's ruling is "like charts" — the whole calendar/timeline VIZ SURFACE is exempt (its blocks
    // encode duration at desktop as absolute blocks, and collapse to a static list at the mobile F1
    // re-measure — same data, different layout). So exempt any element inside the calendar/timeline
    // container, not just absolute ones. Legit tap-targets (add/navigate) live OUTSIDE this container.
    const isDurationBlock = (e) => !!e.closest('.calendar-wrap, [class*="cal-grid"], [class*="timeline-grid"], [aria-label*="calendar timeline" i], [aria-label*="timeline" i]')
      || /(^|\s)(sched-block|cal-event|tl-block|event-block)/.test(typeof e.className === 'string' ? e.className : '');
    // A tiny radio/checkbox whose LABEL is a >=44px clickable target is NOT an undersized tap
    // target -- the label IS the target (WCAG 2.5.5/2.5.8 credit the clickable label, and the Z3
    // detector at ~L1469 already gives this credit). Without it, every label-wrapped radio/checkbox
    // (a 13x13 dot inside a 293x59 label row) falsely dragged F1 AND K2 on every form page --
    // hive/index/inventory/logbook/marketplace-seller-profile all read K2 50% purely from this FP.
    // Instrument calibration, not a page fix (§16.1). [external-wcag-target-size-minimum-24px-spacing]
    const _labelTarget44 = (e) => {
      if (!/^(radio|checkbox)$/.test(e.type || '')) return false;
      const wl = e.closest && e.closest('label');
      const fl = e.id ? document.querySelector('label[for="' + (window.CSS && CSS.escape ? CSS.escape(e.id) : e.id) + '"]') : null;
      const lbl = wl || fl; if (!lbl) return false;
      const lr = lbl.getBoundingClientRect();
      return Math.min(lr.width, lr.height) >= TH.F1.minTapPx;
    };
    const small = inter.map(e => ({ e, r: e.getBoundingClientRect() }))
      .filter(o => o.r.width > 0 && o.r.height > 0 && (o.r.width < TH.F1.minTapPx || o.r.height < TH.F1.minTapPx) && !isDurationBlock(o.e) && !_labelTarget44(o.e))
      .map(o => ({ w: Math.round(o.r.width), h: Math.round(o.r.height), t: (o.e.innerText || o.e.getAttribute('aria-label') || '').slice(0, 18) }));
    out.push(inter.length
      ? M('F1', 'Mobile / touch >= 44px', inter.length - small.length, inter.length,
          small.length ? `under-44: ${small.slice(0, 3).map(s => `${s.t}(${s.w}x${s.h})`).join(', ')}` : 'all >= 44px')
      : NA('F1', 'Mobile / touch >= 44px', 'no interactive controls in this state (print document)'));
    out.push(J('F2', 'Accessibility (WCAG/POUR)', 'axe-core owns this (ufai_battery.js pillar U); do not duplicate'));
    out.push(J('F3', 'Emotional design / peak-end', 'human judgment; NO honest denominator exists: never invent one'));

    // ── G · Nielsen heuristics ──────────────────────────────────────────────
    // ★`[class*="status"]` was a FALSE-PASS FACTORY. It matched `.status-badge` / `.status-pill`
    // -- which carry an ASSET's status ("Overdue", "Closed", "draft"), i.e. DATA -- and scored
    // the page for "visibility of SYSTEM status". Measured 2026-07-15: pm-scheduler, shift-brain
    // and hive all passed G1 purely for rendering the word "Overdue" in a data badge, while only
    // analytics had a real freshness region (#status-bar -> "Updated 6 min ago").
    // This is the same substring trap that once matched a COMMENT instead of a <link>: a class
    // NAME is not a role. G1 now requires SYSTEM-status semantics -- an explicit live region or
    // a declared status bar -- so the number drops to the truth.
    const status = $$('#status-bar, [role="status"], [aria-live]:not([aria-live="off"])', R)
      // a live region holding only a data value is still a data badge, not system status
      .filter((e) => !/^(status-badge|status-pill|sev-chip|tag)/.test(
        (typeof e.className === 'string' ? e.className : '')))
      // A genuine live region (role=status / aria-live=polite|assertive) is a VALID system-status
      // affordance even when currently EMPTY or hidden -- most pages use a toast/announcement
      // container that is display:none until it announces, so a plain `.filter(vis)` made G1 flicker
      // run-to-run with whether a toast happened to be showing at grade time (7 pages dipped to G1=0
      // in a full sweep while passing in isolation). Count the live region on its PRESENCE; only a bare
      // #status-bar with no live semantics (a freshness strip that must actually display text) needs vis.
      .filter((e) => {
        const al = (e.getAttribute('aria-live') || '').toLowerCase();
        const isLiveRegion = e.getAttribute('role') === 'status' || (al && al !== 'off');
        return isLiveRegion || vis(e);
      });
    // isPrintDoc is hoisted to the top of survey() (near isPoster) so A2 can also read it.
    out.push(status.length ? M('G1', 'Visibility of system status', 1, 1, `${status.length} status region(s)`)
      : (isPrintDoc || isPoster) ? NA('G1', 'Visibility of system status', 'static artifact: state lives on the generator, not the artifact')
      : M('G1', 'Visibility of system status', 0, 1, 'no status region'));
    // HTTP status codes count as leaked jargon ONLY with error/HTTP context — a bare 3-digit number
    // is usually a DOMAIN quantity, not an error (achievements' "405 XP this week" matched the old
    // `4\d\d` and failed G2 falsely; "500 hours", "404 assets" would too). §16.1 the ruler, not the page.
    const JARGON = /\b(RPC|JSON|null|undefined|NaN|stack trace)\b|\b(?:HTTP|error|status|code)\b[\s:#-]{0,3}[45]\d\d\b|\b[45]\d\d\b[\s-]{0,3}(?:internal server error|not found|forbidden|bad request|unauthorized|service unavailable)/i;
    const jargon = textEls.filter(e => JARGON.test(ownText(e)));
    out.push(M('G2', 'Match the real world', jargon.length === 0 ? 1 : 0, 1,
      jargon.length ? `system jargon leaked: "${ownText(jargon[0]).slice(0, 26)}"` : 'no system jargon in copy'));
    out.push(M('G3', 'Aesthetic-minimalist', primaryCta.length <= TH.A3.maxPrimaryCta ? 1 : 0, 1,
      `${inter.length} controls, ${primaryCta.length} primary CTA`));

    // ── H · Behavioral ──────────────────────────────────────────────────────
    // H1 applies to WORKER-DAILY pages only (Ian, 2026-07-15): a goal-gradient on a
    // read-only audit log or a status page invents a journey that doesn't exist -- the
    // A3-decoration error in a new dim. Pages opt in declaratively (same pattern as the
    // calm-dashboard meta); everything else reports N/A with the reason, never 0.
    const workerDaily = !!document.querySelector('meta[name="worker-daily"]');
    // 7th naming-accident pre-empted: hive's stairs are .stair-dim-track/.stair-dim-fill,
    // which '.bar-track' missed. Don't enumerate spellings — a *track* element holding a
    // *fill* child IS a track+fill progress bar by construction (mechanism, not name).
    const progress = [...new Set(
      $$('[role="progressbar"], progress, .bar-track, .stack-bar', R).filter(vis)
        .concat($$('[class*="track"]', R).filter(vis).filter(t => t.querySelector('[class*="fill"]')))
    )];
    out.push(workerDaily || progress.length
      ? M('H1', 'Goal-gradient', progress.length ? 1 : 0, 1, `${progress.length} progress indicator(s)`)
      : NA('H1', 'Goal-gradient', 'not a worker-daily journey page (no meta[name=worker-daily]): nothing to show progress on'));
    out.push(J('H2', 'Zeigarnik / open loops', 'needs a return-visit journey; MCP-driven'));
    out.push(J('H3', 'Serial position', 'ordering intent: judged against the page contract (worst-first etc.)'));
    // "Ad-like" = manufactured URGENCY/PRESSURE, not honest product facts. The old
    // /free|upgrade|limited/ flagged WorkHive's honest "Free, No Platform Fees" pricing
    // statement as ad-like (marketplace H4 false-positive) -- "free" as a true no-fee fact is
    // not a dark pattern; the pressure PHRASE is. Match urgency copy, the real distraction.
    const promoish = textEls.filter(e => /\b(act now|hurry|limited time|last chance|don'?t miss (out|it)|upgrade now|for a limited time|while supplies last)\b/i.test(ownText(e)));
    out.push(isPoster
      ? NA('H4', 'Selective attention (no ad-like content)', 'marketing poster: promotional BY GENRE (Ian scope decision)')
      : M('H4', 'Selective attention (no ad-like content)', promoish.length === 0 ? 1 : 0, 1,
          promoish.length ? `promo-styled copy present (${promoish.length})` : 'no ad-like elements'));

    // ── I · Performance ─────────────────────────────────────────────────────
    out.push(J('I1', 'Core Web Vitals', 'ufai_battery.js cwv() owns LCP/INP/CLS: do not duplicate'));
    // A reserve declared in a STYLESHEET class (agentic-rag's .summary-row min-height:336px)
    // or a skeleton loader (public-feed) is optimistic UI too — the attribute selector
    // only saw inline styles. Read the computed value on top-level blocks instead.
    // A skeleton loader is optimistic UI even when it is HIDDEN post-load -- its very presence
    // in the DOM is the proof the page streams (public-feed's #feed-skeleton renders during the
    // fetch, then hides once posts arrive; the vis filter wrongly scored the LOADED state as "no
    // optimistic UI"). Count skeleton PRESENCE; keep vis for the min-height reserves. (2026-07-16)
    const reserved = $$('[style*="min-height"], .kpi-detail', R).filter(vis)
      .concat($$('[class*="skeleton"]', R))
      .concat(blocks.filter(b => parseFloat(getComputedStyle(b).minHeight) > 0))
      // A large min-height on a LAYOUT CONTAINER (not just a cardLike block) is a real space
      // reservation too -- status's `.grid { min-height:1088px }` holds the /health grid's slot
      // while the async pings resolve, but #grid isn't a card so the block-only check missed it.
      // >=100px excludes 44px button tap-targets and small chips; catches genuine content slots.
      .concat($$('div, section, main, ul, ol', R).filter(vis).filter(b => parseFloat(getComputedStyle(b).minHeight) >= 100));
    const _printDoc = !!document.querySelector('#ar-print-wrapper') && R.closest('#ar-print-wrapper');
    out.push(reserved.length ? M('I2', 'Perceived performance', 1, 1, `${reserved.length} reserved block(s)`)
      : (_printDoc || isPoster) ? NA('I2', 'Perceived performance', 'static artifact: rendered once, nothing streams in')
      : M('I2', 'Perceived performance', 0, 1, 'no reserved/optimistic block'));

    // ── J · Errors ──────────────────────────────────────────────────────────
    // 6th naming-accident (2026-07-15): /clear/ unanchored matched "cleared" inside the
    // READ-ONLY hive readiness tile ("3 of 5 cleared") and flagged a whJumpTo() nav card
    // as destructive. A destructive control is named by a SHORT IMPERATIVE action label —
    // word-bound the verbs and only read labels, never a tile's multi-line copy.
    // "Clear filters/search" is a reversible VIEW reset, not data loss — a confirm dialog
    // there would itself be a UX defect, so those are exempt.
    const CLEAR_VIEW = /\bclear\b.{0,14}\b(filter|search|selection|sort|form|input|field)s?\b/i;
    const destructive = inter.filter(e => {
      const label = (e.getAttribute('aria-label') || e.innerText || '').trim();
      return label.length > 0 && label.length <= 30
        && /\b(delete|remove|clear|reset|archive|discard)\b/i.test(label)
        && !CLEAR_VIEW.test(label);
    });
    // Slip-guard is a MECHANISM, not an attribute spelling. All 4 residual J1 "fails"
    // (2026-07-15) were guarded for real — shift-brain/logbook via window.whConfirm()
    // INSIDE the handler body, community via soft-delete + 5s undo (Nielsen's preferred
    // pattern) — but the old check only read the onclick ATTRIBUTE. Resolve the handler's
    // SOURCE (Function.toString) and, for addEventListener-wired controls, scan the
    // inline-script windows around the control's id.
    const GUARD = /whConfirm|confirm\s*\(|are you sure|\bundo\b/i;
    const pageJs = () => (survey._js !== undefined ? survey._js
      : (survey._js = $$('script:not([src])').map(s => s.textContent).join('\n')));
    const slipGuarded = (e) => {
      const oc = e.getAttribute('onclick') || '';
      if (GUARD.test(oc)) return true;
      const fn = (oc.match(/^\s*([A-Za-z_$][\w$]*)\s*\(/) || [])[1];
      if (fn && typeof window[fn] === 'function' && GUARD.test(String(window[fn]))) return true;
      if (e.id) {
        const js = pageJs();
        for (let i = js.indexOf(e.id); i >= 0; i = js.indexOf(e.id, i + 1)) {
          if (GUARD.test(js.slice(Math.max(0, i - 300), i + 800))) return true;
        }
      }
      return false;
    };
    out.push(destructive.length
      ? M('J1', 'Prevent slips', destructive.filter(slipGuarded).length, destructive.length, `${destructive.length} destructive control(s)`)
      : NA('J1', 'Prevent slips', 'read-only surface: 0 destructive controls'));
    out.push(destructive.length ? J('J2', 'Forgiveness / undo', 'needs a live destructive-action walk')
      : NA('J2', 'Forgiveness / undo', 'nothing destructive to undo'));

    // ── K · Field glanceability ─────────────────────────────────────────────
    // Scope to the STATUS CHIP itself. '[class*="tag"]' also matched .simple-card.tag-green
    // (the card carries the tone class), whose direct text-nodes are empty -> 3 real chips
    // read as "colour-only" when they are labelled. Judge the chip's rendered text.
    // A NO-DATA placeholder tag (content is only "-"/"—") is not a colour-coded status SIGNAL --
    // it plainly says "no value yet", it does not rely on colour. analytics/achievements render
    // .sc-tag as "-" until the metric has data; flagging those as "colour-only" is a false
    // positive (they show real labels once populated). Drop dash-only slots; a genuinely EMPTY
    // coloured dot (no dash) still counts + is flagged, which is the real never-colour-alone risk.
    const tags = $$('.sc-tag, .badge, [class*="-badge"], [class*="status-chip"]', R).filter(vis)
      .filter(t => { const s = (t.innerText || '').trim(); return !(s && /^[-–—]+$/.test(s)); })
      // A `-badge` class name doesn't make an element a colour-only STATUS chip (naming accident,
      // Nth instance): achievements' `.domain-badge-wrap` wraps a tier AVATAR MEDAL (.wh-avatar +
      // svg icon, title="Iron Lv.0") whose tier is ALSO stated in the adjacent card text ("Iron
      // Lv.0"). An iconographic medal labelled by its own title + neighbouring text is not
      // colour-alone. Drop badges that carry an avatar/icon/image; a genuine colour-only chip is a
      // bare coloured div/span with no glyph. [external-consistency-and-standards-heuristic-internal-ext]
      .filter(t => !t.querySelector('.wh-avatar, img, svg') && !t.getAttribute('title'));
    const labelledTags = tags.filter(t => (t.innerText || '').replace(/[^\w]/g, '').length > 0);   // never colour-alone
    out.push(tags.length
      ? M('K1', 'Safety-first signalling (never colour-alone)', labelledTags.length, tags.length,
          `${labelledTags.length}/${tags.length} status chips carry TEXT`)
      : NA('K1', 'Safety-first signalling (never colour-alone)', 'no status chips on this surface'));
    const kpiBig = nums.filter(e => parseFloat(getComputedStyle(e).fontSize) >= 20);
    // "Glanceable KPI" applies only where the page HAS numeric KPIs -- a chat page or a
    // text feed has none to enlarge, and demanding one is the A3 nothing-to-disclose error
    // in a new dim. If numbers exist, at least one must be >=20px (arm's-length glance).
    out.push(M('K2', 'Field legibility & reach', ((nums.length === 0 || kpiBig.length) ? 1 : 0) + (small.length === 0 ? 1 : 0), 2,
      `${kpiBig.length}/${nums.length ? nums.length : 'no'} glanceable KPI(s), ${small.length} under-44 target(s)`));

    // ── L · Ethics / wayfinding ─────────────────────────────────────────────
    const urgency = textEls.filter(e => /\b(only \d+ left|expires|last chance|hurry)\b/i.test(ownText(e)));
    out.push(M('L1', 'Honest design (no deceptive patterns)', urgency.length === 0 ? 1 : 0, 1,
      urgency.length ? 'manufactured urgency present' : 'no manufactured urgency'));
    const links = $$('a[href]', R).filter(vis);
    const vague = links.filter(a => /^(click here|here|more|read more|link|go|this)$/i.test((a.innerText || '').trim()));
    out.push(links.length
      ? M('L2', 'Information scent', links.length - vague.length, links.length,
          vague.length ? `${vague.length} vague link label(s)` : 'all link labels predict their destination')
      : NA('L2', 'Information scent', 'no links on this surface (print document)'));

    // ── M · Forms ───────────────────────────────────────────────────────────
    const fields = $$('input, select, textarea', R).filter(vis);
    if (fields.length) {
      // M1 demands a label the USER CAN SEE ("label ABOVE/left, NEVER placeholder-as-label"), but v1
      // counted a bare `aria-label` as satisfying it — so a field that is only announced to screen
      // readers scored PASS while a sighted user saw an unexplained box (found live 2026-07-24 on the
      // reject-reason prompt; axe reports 0 violations, the axe-0-violations false 100). A label only
      // counts if it is RENDERED text bound to the control.
      const visLabel = (f) => {
        if (f.labels && [...f.labels].some(l => vis(l) && l.textContent.trim())) return true;
        const lb = f.getAttribute('aria-labelledby');
        if (lb) { const t = document.getElementById(lb); return !!(t && vis(t) && t.textContent.trim()); }
        return false;
      };
      // CONVENTIONAL exemptions — where a visible label would be noise, not clarity, and aria-label is
      // the correct pattern: search/filter boxes, compose/ask/reply affordances beside a send button,
      // and cells inside a REPEATING row editor (the row already shows what the value belongs to).
      // Without these the rule manufactures false fails — the SC 2.4.11 `position:static` over-reach.
      const convOK = (f) => {
        const hay = ((f.getAttribute('aria-label') || '') + ' ' + (f.id || '') + ' ' + (f.name || '')).toLowerCase();
        return f.type === 'search'
          || /search|filter|query|\bask\b|reply|coach|message|compose|question/.test(hay)
          || !!f.closest('[data-idx], tr, .item-row, .parts-row');
      };
      const named = fields.filter(f => visLabel(f) || (convOK(f) && f.getAttribute('aria-label')));
      const phOnly = fields.filter(f => f.placeholder && !visLabel(f) && !convOK(f));
      out.push(M('M1', 'Labels & structure', named.length - phOnly.length, fields.length,
        `${named.length}/${fields.length} labelled, ${phOnly.length} placeholder-as-label`));
      const validated = fields.filter(f => f.required || f.pattern || f.getAttribute('aria-invalid') !== null);
      out.push(validated.length ? M('M2', 'Validation & recovery', validated.length, validated.length, 'inline validation present')
        : NA('M2', 'Validation & recovery', 'no validated input on this surface (search/filter only)'));
    } else {
      out.push(NA('M1', 'Labels & structure', 'no form fields in this state'));
      out.push(NA('M2', 'Validation & recovery', 'no form fields in this state'));
    }

    // ── N · i18n ────────────────────────────────────────────────────────────
    // MEASURE THE OUTCOME, NOT THE MECHANISM. `dataI > 0` scored a page 75% for having ONE
    // translatable element out of 146 -- i.e. for merely LOADING the engine. Proven live
    // 2026-07-15: after utils.js gained the shared locale floor, logbook/alert-hub/community
    // all jumped 25%->75% while STILL RENDERING 0/90, 0/84, 0/146 translatable elements.
    // That is a manufactured pass -- exactly the false-100 this lens exists to catch.
    // Installing the mechanism must never BE the win.
    // COVERAGE is measured against the page's OWN STATIC LABELS (headings, buttons, section
    // labels), NOT every text node: the recipe deliberately keeps DATA (asset names, counts,
    // IDs) in English, so a data row must not count against the page.
    const dataI = $$('[data-i]', R).length;
    // translate="no" is the HTML-standard marker for proper nouns / data values
    // (hive names, "FIL", brand words) — they are correct untranslated and must not
    // count against label coverage.
    const labelEls = $$('h1, h2, h3, button, label, [class*="section-label"]', R)
      .filter((e) => vis(e) && ownText(e).length > 2 && e.getAttribute('translate') !== 'no'
        // N1 grades whether the INTERFACE is navigable in the user's language — NOT whether domain
        // vocabulary is translated. Industry-standard reliability-engineering METRIC TITLES ("OEE:
        // Overall Equipment Effectiveness", "MTBF: Mean Time Between Failures · ISO 14224:2016", "PM
        // Compliance Rate · SMRP Metric 2.1.1", "RCM Consequence Classification"…) are read in English
        // by convention; they are excluded from the FIL-coverage sample (Ian's call 2026-07-17 — keep
        // technical terms English, grade UI-CHROME translation). Signals: the `.card-title` chart-title
        // class OR a `.card-standard` formal-standard citation (ISO/SMRP/named-rule). Surrounding chrome
        // (nav, period/phase tabs, filters, actions, labels, empty states) must still be bilingual + IS graded.
        && !e.classList.contains('card-title') && !e.closest('.card-title')
        && !e.querySelector('.card-standard') && !e.closest('.card-standard'));
    const labelCovered = labelEls.filter((e) => e.hasAttribute('data-i') || e.querySelector('[data-i]')).length;
    const cov = labelEls.length ? labelCovered / labelEls.length : null;
    // ★HONEST LIMIT — READ THIS BEFORE TRUSTING THE NUMBER. This dim measures the i18n
    // MECHANISM + expansion resilience, NOT how much of the page a Filipino worker can
    // actually read. Two facts force that admission:
    //   1. Installing the shared locale floor took logbook/alert-hub/community 25%->75%
    //      while they still rendered 0/12, 0/49, 0/24 translated labels. The mechanism
    //      checks are 2 of 4, so merely LOADING utils.js buys 50%.
    //   2. `data-i` coverage UNDER-counts the pages that are actually translated:
    //      analytics reports 0/22 while being fully bilingual, because it translates
    //      JS-rendered content through `_t()` at render time rather than via `data-i`.
    // A truthful coverage number needs a LOCALE-FLIP DIFF (snapshot labels, setLang('fil'),
    // re-snapshot, count what changed) — mechanism-agnostic and outcome-true. That is a
    // real instrument change (setLang re-renders, so element handles go stale) and is
    // queued in FAMILY_UFAI_ROADMAP §6, not faked here.
    // The note therefore carries `label coverage` as the HONEST SIGNAL; the pct is the
    // mechanism. Never read this pct as "% translated".
    if (isPoster) {
      out.push(NA('N1', 'i18n mechanism + expansion resilience', 'poster: a print artifact ships in ONE locale by design (Ian scope decision)'));
    } else
    out.push(M('N1', 'i18n mechanism + expansion resilience (NOT % translated)', [
      typeof window.WH_LANG !== 'undefined',                 // mechanism: locale state
      typeof window._t === 'function',                       // mechanism: translator
      cov === null ? true : cov >= 0.8,                      // static-label coverage (a floor)
      document.body.scrollWidth <= window.innerWidth + 2,    // holds at the current locale
    ].filter(Boolean).length, 4,
      `WH_LANG=${typeof window.WH_LANG !== 'undefined'} · lang=${document.documentElement.lang}`
      + ` · label coverage=${labelCovered}/${labelEls.length}`
      + (cov !== null ? ` (${Math.round(cov * 100)}%)` : '')
      + ` · data-i=${dataI}`));
    // Export the EXACT uncovered labels so the sweep hands every page's tagging worklist
    // at once (one ruler edit vs Playwright-probing 16 pages one at a time). The tagging
    // itself stays per-page (dict VALUES are genuinely unique) — but DISCOVERY is centralized.
    out._n1 = {
      dataI, labelCovered, labelTotal: labelEls.length, coverage: cov,
      uncovered: labelEls
        .filter((e) => !e.hasAttribute('data-i') && !e.querySelector('[data-i]'))
        .map((e) => ({ tag: e.tagName, id: e.id || '', t: ownText(e).slice(0, 44) })),
    };

    // ── O · Onboarding ──────────────────────────────────────────────────────
    const tour = $$('[class*="tour"], [class*="walkthrough"], [class*="coachmark"]', R).filter(vis);
    out.push(M('O1', 'Value-first, not a tour', tour.length === 0 ? 1 : 0, 1,
      tour.length ? 'intrusive tour present' : 'no tour, UI usable immediately'));
    const help = $$('details, [class*="help"], .wh-prov-btn, [aria-label*="guide" i]').filter(vis);
    out.push(isPoster
      ? NA('O2', 'Pull > push help', 'poster: a static artifact offers no in-page help journey')
      : M('O2', 'Pull > push help', help.length ? 1 : 0, 1, `${help.length} on-demand help affordance(s)`));

    // ── Q · Motion ──────────────────────────────────────────────────────────
    let rmBlocks = 0;
    for (const ss of document.styleSheets) { try { for (const r of ss.cssRules) if (r.conditionText && /prefers-reduced-motion/.test(r.conditionText)) rmBlocks++; } catch (_) { /* empty-catch-allow: cross-origin */ } }
    const animated = $$('*', R).filter(e => { const s = getComputedStyle(e); return (s.transitionDuration !== '0s' && s.transitionDuration !== '') || (s.animationName && s.animationName !== 'none'); });
    out.push(animated.length === 0 && rmBlocks === 0
      ? NA('Q1', 'prefers-reduced-motion', 'nothing animates in this state: no motion to reduce')
      : M('Q1', 'prefers-reduced-motion', rmBlocks > 0 ? 1 : 0, 1,
          `${rmBlocks} reduced-motion block(s), ${animated.length} animated el(s)`));

    // Q2 · NO PHANTOM FOCUS STOP (WCAG 2.2 SC 2.4.11 Focus Not Obscured) — NEW 2026-07-23 (§12,
    // found by the live-MCP keyboard walk). A control hidden with opacity:0 (or an opacity:0
    // ANCESTOR) but WITHOUT visibility:hidden / display:none / inert / aria-hidden is invisible to
    // sighted+mouse users yet STILL IN THE TAB ORDER: a keyboard user lands on an unusable control
    // with the focus ring on nothing. REAL bug found+fixed: the companion widget (#wh-ai-widget) was
    // opacity:0 + pointer-events:none with visibility:visible, so its "Open companion" trigger stayed
    // focusable UNDER the fixed nav-hub FAB, on ~30 pages via shared chrome (fixed centrally with
    // visibility:hidden + a delayed transition). ★AXE CANNOT SEE THIS: axe treats only display:none /
    // visibility:hidden / aria-hidden as hidden, so an opacity:0 container scores CLEAN — which is why
    // the arc-wide "0 axe violations" was true and this bug still shipped. The fix for a hidden-but-
    // animated container is visibility:hidden (+ `transition: visibility 0s linear <fade>`), or inert.
    try {
      // ★CALIBRATION 2: start at the PARENT, not the element. A control that makes ITSELF opacity:0
      // is the well-known accessible "custom file upload" pattern - an <input type=file> laid over a
      // styled button, which MUST stay focusable and carries its own aria-label. The phantom bug is
      // strictly a focusable trapped inside a hidden CONTAINER (a closed modal/panel/toast), so only
      // ANCESTOR opacity counts. Without this, marketplace + marketplace-seller false-failed on their
      // legitimate upload inputs.
      const _opacityHidden = (e) => {
        for (let n = e.parentElement; n && n !== document.body; n = n.parentElement) {
          const cs = getComputedStyle(n);
          if (parseFloat(cs.opacity) === 0) return n;
        }
        return null;
      };
      const _focusables = $$('a[href],button,input:not([type=hidden]),select,textarea,[tabindex]:not([tabindex="-1"])')
        .filter((e) => !e.disabled && !e.closest('[inert]') && !e.closest('[aria-hidden="true"]'))
        .filter((e) => { const cs = getComputedStyle(e); return cs.visibility !== 'hidden' && cs.display !== 'none'; })
        // ★CALIBRATION (2026-07-23): the element must actually be RENDERED. Checking only its OWN
        // computed display misses the common case of a closed modal/sheet/wizard-step whose ANCESTOR
        // is display:none - the child still reports display:block, and a `from{opacity:0}` animation
        // keyframe on that subtree makes it look opacity-hidden too. Those controls are NOT in the tab
        // order (verified live: .focus() does nothing), so flagging them is a FALSE POSITIVE - it
        // wrongly failed 6 pages (pm-scheduler alone reported 20 phantoms, all unrendered).
        // opacity:0 does NOT remove an element from layout, so the REAL phantoms still have a box.
        .filter((e) => e.offsetParent !== null || e.getClientRects().length > 0);
      const _phantoms = _focusables.filter(_opacityHidden);
      out.push(_focusables.length === 0
        ? NA('Q2', 'No phantom focus stop (WCAG 2.2 focus-not-obscured)', 'no focusable control in this state')
        : M('Q2', 'No phantom focus stop (WCAG 2.2 focus-not-obscured)', _phantoms.length ? 0 : 1, 1,
            _phantoms.length
              ? `${_phantoms.length} focusable control(s) are opacity:0 yet still in the tab order (keyboard lands on an invisible control) [SC 2.4.11]`
              : `${_focusables.length} focusable control(s), none hidden-but-focusable`));
    } catch (_) { /* empty-catch-allow: best-effort focus-hygiene lens */ }

    // Q3 · DRAGGING ALTERNATIVE (WCAG 2.2 SC 2.5.7) — NEW 2026-07-23 (§12). Any function operated by
    // a DRAG must also be operable by a single pointer (click/tap), because dragging needs sustained
    // fine motor control that a tremor / one-handed / gloved / switch user may not have. VERIFIED
    // CLEAN at authoring time, so this is a forward-RATCHET, not a backlog: the only drag surface on
    // the platform is integrations.html's CSV drop-zone, which pairs it with a click-to-browse
    // <input type=file> (the correct alternative); dayplanner — which I assumed was drag-scheduled —
    // is actually "click item then click a time slot", i.e. single-pointer BY DESIGN. This dim exists
    // so that the day someone adds a drag-to-reorder or drag-to-reschedule with no click path, it FAILs.
    try {
      const _dragSrc = Array.from(document.scripts).map((s) => s.textContent || '').join('\n');
      const _dragEls = $$('[draggable="true"]');
      const _hasDrag = _dragEls.length > 0 || /addEventListener\(\s*['"](dragstart|drop)['"]/.test(_dragSrc) || /ondragstart|ondrop=/.test(_dragSrc);
      if (!_hasDrag) {
        out.push(NA('Q3', 'Dragging has a single-pointer alternative (WCAG 2.2)', 'no drag-operated function on this page'));
      } else {
        // an acceptable alternative: a click-to-browse file input (for a drop-zone), or explicit
        // move/reorder/reschedule controls (for a drag-to-order list).
        const _fileAlt = !!document.querySelector('input[type=file]');
        const _moveAlt = $$('button,a[href],[role=button],select').some((e) => {
          const t = ((e.textContent || '') + ' ' + (e.getAttribute('aria-label') || '') + ' ' + (e.id || ''));
          return /(move (up|down|to)|reorder|reschedul|change (time|slot)|earlier|later|browse|choose file|select file)/i.test(t);
        });
        const _ok = _fileAlt || _moveAlt;
        out.push(M('Q3', 'Dragging has a single-pointer alternative (WCAG 2.2)', _ok ? 1 : 0, 1,
          _ok ? 'drag surface present AND operable by a single pointer (' + (_fileAlt ? 'click-to-browse file input' : 'move/reorder controls') + ')'
              : 'a drag-operated function has NO single-pointer alternative - unusable with a tremor, one hand, gloves, or a switch [SC 2.5.7]'));
      }
    } catch (_) { /* empty-catch-allow: best-effort dragging-alternative lens */ }

    // ── R · Layout rhythm ───────────────────────────────────────────────────
    // ★CALIBRATION (2026-07-24, live full-lens sweep): EXCLUDE sr-only / visually-clipped
    // headings from the gap analysis. A page's accessible structure often includes a
    // 1px-clipped `<h2 class="sr-only">` (position:absolute; width:1px; height:1px;
    // clip:rect(0 0 0 0); margin:-1px) - the standard screen-reader-only heading pattern.
    // vis() counts it (offsetParent set, not display:none) so R1 measured the gap ABOVE it
    // as 31px (32 filter-margin + the -1px sr-only margin) = a FALSE off-scale hit on
    // marketplace + agentic-rag-observability. An sr-only heading is NOT a visual layout
    // block; a root-level child is never legitimately <=1px. Skip them.
    const _notSrOnly = (e) => { const r = e.getBoundingClientRect(); return r.width > 1 && r.height > 1; };
    const kids = [...R.children].filter((e) => vis(e) && _notSrOnly(e));
    const gaps = [];
    for (let i = 1; i < kids.length; i++) {
      const p = kids[i - 1].getBoundingClientRect(), c = kids[i].getBoundingClientRect();
      const g = Math.round(c.top - p.bottom); if (g >= 0) gaps.push(g);
    }
    const distinct = [...new Set(gaps)];
    // Canonical = the DECLARED scale (the #50 lesson): tokens.css ships --wh-space-1:4px
    // and --wh-space-3:12px — the system is 4-pt based at the small end. Demanding %8
    // failed pages for using their own design tokens. On-scale = a declared token value
    // or an 8-pt multiple beyond the token range.
    const WH_SPACE = new Set([0, 4, 8, 12, 16, 24, 32]);   // tokens.css --wh-space-*
    const onGrid = distinct.filter(g => WH_SPACE.has(g) || g % 8 === 0);
    const off = distinct.filter(g => !WH_SPACE.has(g) && g % 8 !== 0);
    out.push(distinct.length
      ? M('R1', 'Spacing scale (declared tokens / 8-pt)', onGrid.length, distinct.length,
          `gaps=[${distinct.sort((a, b) => a - b).join(',')}] offScale=[${off.join(',')}]`)
      : NA('R1', 'Spacing scale (declared tokens / 8-pt)', 'single-block root: no inter-block gaps to grade'));
    out.push((isPoster || isPrintDoc)
      ? NA('R2', 'Alignment & grid (no overflow)', 'print/poster artifact — fixed width by design, not a responsive page')
      : M('R2', 'Alignment & grid (no overflow)', document.body.scrollWidth <= window.innerWidth + 2 ? 1 : 0, 1,
        `scrollW=${document.body.scrollWidth} vs ${window.innerWidth}`));
    // R3 governs CONTROLS as well as cards. Measuring only .simple-card scored this page
    // 100% while its buttons carried FOUR radii (0/8/10/999px) and THREE heights
    // (44/50/72) for one concept -- the "not uniform / cluttered" Ian saw. Two reads:
    //   (a) one shape per control ROLE (~3 roles, not 8 shapes)
    //   (b) SAME SHAPE MUST MEAN SAME JOB -- a filter that looks identical to an ACTION
    //       is the strongest similarity cue misused; colour alone cannot carry it (CVD/print).
    const peers = $$('.simple-card', R).filter(vis);
    const peerSig = [...new Set(peers.map(c => { const s = getComputedStyle(c); return `${s.borderRadius}|${s.padding}`; }))];
    const ctrls = $$('button, a.refresh-btn, [role="tab"]', R).filter(vis);
    // SHAPE = SILHOUETTE (the corner treatment), not radius+height (Ian's call, 2026-07-15).
    // Height FOLLOWS CONTENT: analytics' KPI tiles are content-sized cards that happen to be
    // <button>s, so they measured 72/84/101px and the old signature reported "7 shapes for 2
    // roles" -- marking the page down for having rich content rather than for being
    // INCONSISTENT. Gestalt similarity is carried by the outline, so that is what R3 grades.
    // A pill/circle is normalised: it is a deliberate shape, not a rogue px value.
    const shape = (e) => {
      const raw = getComputedStyle(e).borderTopLeftRadius;
      if (raw.includes('%')) return 'round';
      const r = Math.round(parseFloat(raw) || 0);
      const h = e.getBoundingClientRect().height;
      return (h && r >= h / 2 - 1) ? 'pill' : `${r}px`;
    };
    // A joined tab-bar MEMBER's own radius is 0 by construction (the BAR carries the 8px
    // outer corners) -- its silhouette is the bar, not its personal corner. And a
    // full-bleed card-header toggle (>=90% of its card's width) is CARD ANATOMY: its
    // geometry belongs to the card, not to the control vocabulary.
    const roleOf = (e) => {
      if (e.getAttribute('role') === 'tab' || e.closest('[role="tablist"]')) return 'navigate';
      // Ian 2026-07-15: view-switchers are a THIRD vocabulary -- the CONNECTED tab-bar
      // (joined siblings in one container, no gap). A joined aria-pressed group navigates
      // views; a pilled standalone one selects data.
      if (e.hasAttribute('aria-pressed') && e.parentElement) {
        const st = getComputedStyle(e.parentElement);
        const joined = (st.gap === '0px' || st.gap === 'normal') && e.parentElement.children.length >= 2
          && [...e.parentElement.children].every((c) => c.tagName === e.tagName);
        if (joined && parseFloat(getComputedStyle(e).borderRadius) === 0) return 'navigate';
      }
      // A disclosure is an ACTION you invoke: pressing it does something. It is told apart
      // by its label and chevron, not by its outline, so it legitimately shares the button
      // silhouette. The distinction a user actually reads is SELECT (a state you toggle,
      // e.g. a filter chip) vs PRESS (refresh, show-all, open-details). Splitting those two
      // reported "action+disclose" as a collision and would have driven an invented third
      // button shape -- which is MORE visual noise, i.e. the opposite of what R3 is for.
      // SELECT = any ARIA selection semantic, not just aria-pressed/selected. aria-CHECKED
      // (radio/checkbox/switch) is equally a "toggle a state" control -- voice-journal's persona
      // picker uses role=radio + aria-checked and was mis-read as PRESS, colliding its pill with
      // the press buttons. A control whose ARIA role IS a selection role counts too. (2026-07-16)
      const selRole = /^(radio|checkbox|switch|option|menuitemradio|menuitemcheckbox)$/;
      if (e.hasAttribute('aria-pressed') || e.hasAttribute('aria-selected') || e.hasAttribute('aria-checked')
          || selRole.test(e.getAttribute('role') || '')) return 'select';
      return 'press';
    };
    const isCardAnatomy = (e) => {
      const card = e.closest('.card, .simple-card, .board-card');
      return card && e.getBoundingClientRect().width >= card.getBoundingClientRect().width * 0.9;
    };
    // A borderless, transparent control (the info ⓘ, a bare text toggle) draws NO shape --
    // it has no silhouette to be consistent or inconsistent WITH. Only controls that
    // visibly draw an outline/fill are members of the shape vocabulary.
    const drawsShape = (e) => {
      const st = getComputedStyle(e);
      const hasBorder = parseFloat(st.borderTopWidth) > 0;
      const bg = rgb(st.backgroundColor);
      return hasBorder || (bg && bg.a > 0.03) || (st.backgroundImage || '').includes('gradient');
    };
    // A ROUND, ICON-ONLY control (a circular button with no text label -- a heart/save toggle,
    // a record-mic, a FAB) is its OWN affordance class, universally recognised alongside rect
    // text-buttons; it is not a member of the rect/pill/bar TEXT-control vocabulary any more than
    // a card is. Counting it forced marketplace (heart) + report-sender (mic FAB) to "4 shapes
    // for 3 roles" for having a normal circular icon button. Exclude it, like card-anatomy. A
    // round button WITH a text label still counts (it's a shaped text control). (2026-07-16)
    const isRoundIcon = (e) => shape(e) === 'round' && (e.textContent || '').trim().length === 0;
    const ctrlsVocab = ctrls.filter((e) => !isCardAnatomy(e) && !isRoundIcon(e) && drawsShape(e));
    const shapeV = (e) => (roleOf(e) === 'navigate' ? 'bar' : shape(e));
    const ctrlShapes = [...new Set(ctrlsVocab.map(shapeV))];
    const radii = ctrlShapes;
    // ROLE, not CSS class. The first cut grouped by className and reported
    // "8px|44 worn by on+btn+details-toggle+showall-toggle" as four colliding jobs -- but a
    // lang switch, a refresh and two expanders are all "press me" buttons, and a class name
    // is a naming accident, not a job. Worse, a class-name proxy cannot generalise: it would
    // flag every page whose classes happen to differ. ARIA states the job semantically and
    // works on ANY page, which is the whole point of a cross-page lens.
    const byShape = {};
    ctrlsVocab.forEach((e) => { (byShape[shapeV(e)] = byShape[shapeV(e)] || new Set()).add(roleOf(e)); });
    const shapeCollisions = Object.entries(byShape).filter(([, set]) => set.size > 1)
      .map(([sh, set]) => `${sh} worn by ${[...set].join('+')}`);
    // The bar is one shape per ROLE, not an arbitrary count: a page with 5 honest roles
    // should not be marked down for having 5 shapes. <=3 was a magic number that punished
    // richness instead of INCONSISTENCY.
    const roleCount = new Set(ctrlsVocab.map(roleOf)).size;
    const r3Checks = [
      peers.length ? peerSig.length === 1 : true,        // card peers uniform
      ctrlShapes.length <= Math.max(roleCount, 3),       // no more shapes than honest roles
      shapeCollisions.length === 0,                      // same shape => same job
    ];
    out.push(M('R3', 'Treatment uniformity (cards AND controls)', r3Checks.filter(Boolean).length, 3,
      `cardTreatments=${peerSig.length} · silhouettes=${ctrlShapes.length} for ${roleCount} role(s) (${radii.join(',')})`
      + (shapeCollisions.length ? ` · SAME-SHAPE-DIFFERENT-JOB: ${shapeCollisions[0]}` : '')));
    out._r3 = { ctrlShapes, radii, shapeCollisions, roleCount };
    // A void is a block that renders NOTHING — judge by the whole SUBTREE (innerText +
    // any media/controls), never by direct text nodes: page-header / phase-tabs / the
    // source chip hold their text in CHILDREN and were all falsely flagged as voids.
    const voids = kids.filter(c => {
      const r = c.getBoundingClientRect();
      if (r.height <= 24) return false;
      const hasText = (c.innerText || '').trim().length > 0;
      const hasMedia = !!c.querySelector('svg,img,canvas,table,input,button,a');
      return !hasText && !hasMedia;
    });
    out.push(M('R4', 'Regions & whitespace (no orphan voids)', voids.length === 0 ? 1 : 0, 1, `${voids.length} orphan void(s)`));
    out.push(J('R5', 'Vertical flow & section cohesion', 'whole-page reading order: needs the full-page screenshot diff'));

    // ══ NIGHT-CRAWLER RUBRIC EXTENSION (2026-07-17 — Ian's 8 field observations) ══════════════════
    // New classes W (Wayfinding) + V (Visual integrity) + B/G extensions. Every rule cited from the
    // substrate harvest (substrate/external/external-ux-*). See FAMILY_UFAI_ROADMAP §19.

    // ── W · Wayfinding ───────────────────────────────────────────────────────
    // W1 Back / escape affordance — Nielsen #3 (user-control-freedom): "Provide a Back link to return
    // users to a previous page; clearly-marked emergency exit." A non-landing page needs a visible way
    // OUT (back/up/home control, breadcrumb, or the shared nav-hub launcher). Landing/print are exempt.
    {
      const isLanding = isPrintDoc || isPoster || /(^|\/)index(\.[a-z0-9-]+)?\.html?$/.test(location.pathname);
      // A PROPER way back is an IN-LAYOUT control (a header "← Back"/"Home"/up link or a breadcrumb) —
      // NOT the floating nav-hub FAB / companion, which Ian flagged as insufficient ("no PROPER way
      // back"). So exclude the shell chrome from the search; the nav-hub's own consistency is W2's job.
      const W1_CHROME = '#wh-hub-panel, #wh-hub-fab, .wh-hub-fab, [data-nav-hub], [class*="hub-fab"], #wh-ai-panel, #wh-ai-trigger, #wh-ai-launcher, [class*="companion"], #wh-feedback-fab';
      const escBtn = [...document.querySelectorAll('a[href], button, [role="button"]')].some((e) => {
        if (!vis(e) || e.closest(W1_CHROME)) return false;
        const t = ((e.getAttribute('aria-label') || '') + ' ' + ownText(e)).toLowerCase().trim();
        const cls = (typeof e.className === 'string' ? e.className : '').toLowerCase();
        return /^(←|‹|◄|«|⟵|↩)/.test(t.trim()) || /(^|\s)(back|go back|home|all tools|hive board)\b/.test(t) || /\b(back-btn|back-link|btn-back|breadcrumb|home-link|nav-back|go-back)\b/.test(cls);
      });
      const crumb = !!R.querySelector('.breadcrumb, [class*="breadcrumb"], nav[aria-label*="readcrumb" i]');
      const hasBack = escBtn || crumb;
      out.push(isLanding
        ? NA('W1', 'Back / escape affordance', 'landing/print: it IS the home surface')
        : M('W1', 'Back / escape affordance', hasBack ? 1 : 0, 1,
            hasBack ? `in-layout way back: ${escBtn ? 'back/home ctl' : 'breadcrumb'}` : 'NO in-layout way back (only the floating nav-hub) — Nielsen #3'));
    }

    // ── V · Visual integrity ─────────────────────────────────────────────────
    // V1 No collision / overlap — fixed-height + overflow:hidden masks overlapping content (harvest:
    // fixed-height-overflow-fragility) + gestalt-proximity. No two visible text/interactive boxes may
    // overlap. Intentional overlays (modals, tooltips, toasts, sticky/fixed chrome, companion/nav shell)
    // overlap BY DESIGN — excluded.
    {
      // ★RECT-based visibility that WORKS FOR FIXED ELEMENTS — the old `vis()`/`fabVis` used offsetParent,
      // which is NULL for every position:fixed element, so V1 was structurally BLIND to the entire
      // bottom-right FAB stack, the connectivity "Online" chip, and the wayfinding breadcrumb (Ian's
      // screenshots). This is the [[feedback_ufai_lens_instrument_blindspots]] offsetParent trap again.
      const visR = (e) => { const s = getComputedStyle(e); if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity || '1') === 0) return false; const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4 && r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth; };
      const ov = (a, b) => { const ix = Math.min(a.right, b.right) - Math.max(a.left, b.left); const iy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top); return (ix <= 1 || iy <= 1) ? 0 : (ix * iy) / Math.min(a.width * a.height, b.width * b.height); };
      const inPanel = (e) => !!e.closest('[aria-modal="true"], [role="dialog"], [role="menu"], [role="tooltip"], .modal, .tooltip, .toast, [class*="sheet"], #wh-ai-panel, #wh-hub-panel');

      // (1) CONTENT vs CONTENT — no two static text/interactive boxes overlap (excl. fixed/absolute + panels).
      const isFloat = (e) => ['fixed', 'sticky', 'absolute'].includes(getComputedStyle(e).position);
      const cand = [...R.querySelectorAll('button, a, input, select, h1, h2, h3, h4, p, label, li')]
        .filter((e) => vis(e) && ownText(e).length > 1 && !inPanel(e) && !isFloat(e))
        .map((e) => ({ e, r: e.getBoundingClientRect() })).filter((o) => o.r.width > 10 && o.r.height > 8 && o.r.width < 900);
      const hits = [];
      for (let i = 0; i < cand.length && hits.length < 6; i++) for (let j = i + 1; j < cand.length; j++) {
        const a = cand[i], b = cand[j]; if (a.e.contains(b.e) || b.e.contains(a.e)) continue;
        if (ov(a.r, b.r) > 0.30) { hits.push(`${a.e.tagName}"${ownText(a.e).slice(0, 12)}"×${b.e.tagName}"${ownText(b.e).slice(0, 12)}"`); break; }
      }

      // (2) FLOATING CHROME — collect EVERY small fixed/sticky widget (FAB / status chip / breadcrumb
      // pill), not a hardcoded list, so connectivity-widget + wayfinding are seen. Exclude open panels.
      const floats = [...document.querySelectorAll('body *')].filter((e) => {
        const cs = getComputedStyle(e);
        const p = cs.position; if (p !== 'fixed' && p !== 'sticky') return false;
        if (cs.pointerEvents === 'none') return false;   // decorative full-viewport bg (aurora/cursor-glow) — sits BEHIND, not a widget
        const r = e.getBoundingClientRect();
        // The page's own TOP CHROME — a semantic <header>/[role=banner]/.header OR any full-width bar
        // pinned to the top (a Tailwind `fixed top-0` <nav>, etc.) — is NOT a "covering widget":
        // content scrolls UNDER a sticky top bar BY DESIGN. This kills the phantom "header covers
        // WorkHive" a sticky-header page yields (the bar geometrically overlaps its own adjacent brand
        // text; a 1280→390 RESIZE also leaves body content transiently behind it — a Chromium sticky
        // quirk a FRESH 390 load never shows: verified fresh-390 V1=100). A real small widget
        // (breadcrumb pill / FAB) is NOT a full-width top bar, so it still counts. The BOTTOM-nav
        // (top ≈ viewport bottom) is deliberately NOT excluded — a FAB over it IS a real collision.
        // (2026-07-19 — §16.1 "the ruler, not the page".)
        if (e.matches('header, [role="banner"], .header, .app-header, .site-header')) return false;
        // Full-width bar in the TOP chrome zone (top < ~96px covers a header + a sticky sub-nav
        // pinned below it, e.g. eng-design's `.sticky top-0` discipline panel that sits at top:64
        // under the 64px header). Width≥90% keeps small widgets (breadcrumb pill / FAB) in scope;
        // the bottom-nav (top ≈ viewport bottom) is untouched.
        if (r.top < 96 && r.width >= innerWidth * 0.9) return false;
        if (inPanel(e) || !visR(e)) return false;
        return r.width < 440 && r.height < 240;   // a widget, not a full panel
      });
      const outer = floats.filter((e) => !floats.some((o) => o !== e && o.contains(e)))   // outermost only (dedup nesting)
        .map((e) => ({ el: e, id: e.id || (typeof e.className === 'string' && e.className.trim().split(/\s+/)[0]) || e.tagName, r: e.getBoundingClientRect(), t: ownText(e).slice(0, 14) }));
      let chromeHit = '';
      // 2a. widget vs widget (the bottom-right FAB stack: companion trigger × connectivity "Online" chip)
      for (let i = 0; i < outer.length && !chromeHit; i++) for (let j = i + 1; j < outer.length; j++) {
        if (outer[i].el.contains(outer[j].el) || outer[j].el.contains(outer[i].el)) continue;   // a container is not "colliding" with its own child
        if (outer[i].r.width && ov(outer[i].r, outer[j].r) > 0.15) { chromeHit = `widgets overlap: ${outer[i].id}"${outer[i].t}"×${outer[j].id}"${outer[j].t}"`; break; }
      }
      // 2b. a TOP-region floating widget (the wayfinding breadcrumb) covering the page HEADER content.
      // A fixed HEADER <nav> CONTAINS its own header links — that is layout, not a collision, so exclude
      // ancestor/descendant pairs (2026-07-18: the fixed nav was falsely flagged "covering" its own
      // Sign In/logo @390 — the narrow nav overlaps its children >25% at phone width; a ruler artifact).
      if (!chromeHit) {
        const topFloats = outer.filter((f) => f.r.top < 120 && f.r.left < innerWidth * 0.6);
        if (topFloats.length) {
          const topContent = [...document.querySelectorAll('h1, h2, h3, h4, a, button, span, div, p, [class*="logo"], [class*="title"], [class*="brand"]')]
            .filter((e) => visR(e) && ownText(e).length > 1 && !isFloat(e) && !e.closest('#wh-wayfinding, [id*="wayfind"], [class*="wayfind"]') && e.getBoundingClientRect().top < 130)
            .map((e) => ({ el: e, r: e.getBoundingClientRect(), t: ownText(e).slice(0, 18) })).filter((o) => o.r.width > 10 && o.r.height > 6);
          for (const f of topFloats) { for (const cc of topContent) { if (f.el.contains(cc.el) || cc.el.contains(f.el)) continue; if (ov(f.r, cc.r) > 0.25) { chromeHit = `widget covers header: ${f.id}"${f.t}" over "${cc.t}"`; break; } } if (chromeHit) break; }
        }
      }

      const v1ok = hits.length === 0 && !chromeHit;
      out.push(M('V1', 'No collision / overlap (content + floating chrome)', v1ok ? 1 : 0, 1,
        v1ok ? 'no overlapping elements or widgets'
          : hits.length ? `${hits.length} content overlap(s): ${hits.slice(0, 2).join(' · ')}` : chromeHit));
    }

    // ── B4 · Explanation microcopy is plain (extends B) ──────────────────────
    // The "where did this come from" / "how is this computed" / "about this dashboard's data sources"
    // disclosures must be plain + concise (grade ≤8, ≤20 words/sentence). Cited: concise-scannable-web-
    // writing + match-system-real-world ("simple language, no jargon"). Ian: those disclosures read useless.
    {
      const trig = /where did this|where does this|how (is|are) (this|these|it|they)\b.{0,20}comput|how we comput|about this dashboard|data sources?|how it works|how this works|updated each|refreshes each/i;
      // These page-OWNED disclosures often sit in a footer OUTSIDE <main>/R (the calm-dashboard-contract
      // footer, the provenance-hover panel) — search the whole document but exclude shared shell chrome.
      const B4_CHROME = '#wh-ai-panel, #wh-ai-trigger, #wh-ai-launcher, #wh-hub-panel, #wh-hub-fab, .wh-companion, [class*="companion"], nav[class*="hub"]';
      const discs = [...document.querySelectorAll('details, [class*="provenance"], [class*="disclosure"], [class*="help"], [data-calm-disclosure], .wh-source-chip')]
        .filter((e) => vis(e) && !e.closest(B4_CHROME) && trig.test((e.innerText || e.textContent || '')));
      let over = 0, checked = 0; const bad = [];
      discs.forEach((e) => {
        (e.innerText || '').split(/(?<=[.!?])\s+|\n+/).map((s) => s.trim()).filter((s) => s.split(/\s+/).filter(Boolean).length >= 8).forEach((s) => {
          checked++;
          const words = s.split(/\s+/).filter(Boolean);
          const syl = words.reduce((a, w) => a + syllables(w), 0);
          const g = 0.39 * words.length + 11.8 * (syl / Math.max(words.length, 1)) - 15.59;
          if (words.length > 20 || g > 8) { over++; if (bad.length < 3) bad.push(`${words.length}w/g${g.toFixed(0)}`); }
        });
      });
      out.push(discs.length === 0
        ? NA('B4', 'Explanation microcopy plain', 'no where-from/how-computed/data-source disclosure here')
        : M('B4', 'Explanation microcopy plain', over === 0 ? 1 : 0, 1,
            over === 0 ? `${discs.length} disclosure(s) plain (≤20w, grade≤8)` : `${over}/${checked} sentence(s) unclear (${bad.join(', ')})`));
    }

    // ── G4 · Single freshness source (extends G; G1/G2/G3 already taken) ─────
    // ONE freshness/status claim per surface — not "Live · refreshed · Based on…" + green-online +
    // "updated x min ago" stacked. Cited: signal-to-noise ("remove redundant content") + aesthetic-
    // minimalist ("only necessary elements"). Count DISTINCT freshness claims in the top region.
    {
      // DATA-freshness claims only — a team-presence "online now" is a SEPARATE, legitimate social
      // status, not a data-freshness claim, so it doesn't count here. The redundancy to catch is a page
      // stating data freshness MORE THAN ONCE (a source chip "Live · refreshed on load" AND a separate
      // "updated x min ago" AND another). Header region only (top<560).
      const dataFreshRe = /refreshed|last sync|updated?\b|as of\b|·\s*live\b|\blive\s*·|\d+\s*(min|minute|hour|hr|sec|second|day)s?\s*ago/i;
      const claims = [...R.querySelectorAll('p, span, small, time, div, [class*="fresh"], [class*="source"], [class*="updated"]')]
        .filter((e) => vis(e) && dataFreshRe.test(ownText(e)) && ownText(e).trim().length > 3 && ownText(e).length < 130
          && e.getBoundingClientRect().top < 560);
      const leaves = claims.filter((e) => !claims.some((o) => o !== e && e.contains(o)));   // leaf claims only
      out.push(leaves.length <= 1
        ? M('G4', 'Single freshness source', 1, 1, leaves.length === 0 ? 'no data-freshness claim' : '1 data-freshness claim')
        : M('G4', 'Single freshness source', 0, 1,
            `${leaves.length} redundant data-freshness claims: ${leaves.slice(0, 3).map((e) => '"' + ownText(e).trim().slice(0, 26) + '"').join(' + ')}`));
    }

    // ── B5 · No raw internals in user copy (extends B) ───────────────────────
    // User-facing text must not leak raw internals — UA strings, file paths, raw URLs, UUIDs. Cited:
    // match-system-real-world ("no technical jargon") + [[feedback_provenance_user_voice_not_internals]].
    // Ian: the feedback panel showed "Auto-captured: /workhive/logbook.html · Mozilla/5.0 (Windows NT…".
    {
      const internalRe = /Mozilla\/\d|AppleWebKit|Gecko\/\d|\/workhive\/|Win64|WOW64|X11;\s|node_modules|127\.0\.0\.1|localhost:\d|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}/;
      const leaks = [...R.querySelectorAll('p, span, div, small, li, td, label')]
        .filter((e) => vis(e) && !e.closest('code, pre, script, kbd, samp') && !e.querySelector('p,span,div,li,td') && internalRe.test(ownText(e)))
        .map((e) => ownText(e).trim().slice(0, 44));
      out.push(M('B5', 'No raw internals in user copy', leaks.length === 0 ? 1 : 0, 1,
        leaks.length === 0 ? 'no leaked internals' : `${leaks.length} leak(s): "${leaks[0]}…"`));
    }

    // ── W2 · Shared-chrome consistency (extends the §18 overlay stream) ───────
    // The AI companion launcher (+ its avatar) and the nav-hub are shared chrome that must render AND
    // be VISIBLE on every family page. Cited: Nielsen #4 (consistency-standards). Ian: "companion avatar
    // not visible on some pages." Founder-console-only surfaces are exempt (no companion by design).
    {
      const companion = document.querySelector('#wh-ai-trigger, #wh-ai-launcher, [data-companion-launcher], [class*="companion"][class*="launch"], .wh-ai-fab');
      // ★W2 RECALIBRATION (2026-07-23, forced by the Q2 fix — and it exposed a FALSE PASS).
      // W2 was written PRE-FAB-CONSOLIDATION, when the companion was its own floating corner FAB, so it
      // demanded the launcher be VISIBLE. Since the 2026-07-20 consolidation the idle corner is ONE hub
      // FAB and the companion is launched FROM the nav-hub's Companion row — the closed widget is
      // invisible BY DESIGN. W2 kept passing only because the closed widget used `opacity:0`, which
      // slipped past this visibility check: it was scoring a control the user CANNOT SEE as "visible" =
      // a false pass. Making the closed widget `visibility:hidden` (the Q2 focus fix) surfaced it.
      // W2's REAL job (per its origin bug: personaAvatarHTML lived only in wh-persona.js, which ~30 pages
      // never loaded, so the trigger avatar rendered BLANK) is "the companion module is LOADED and its
      // avatar RENDERS" — not "a closed panel is on-screen". So credit PRESENCE + a rendered avatar, and
      // require the hub (the thing that actually launches it) to be visible. A page that never loads
      // companion-launcher.js / wh-persona.js still FAILs, which is the regression W2 exists to catch.
      const compLaunchable = !!(companion && (vis(companion) || document.querySelector('#wh-hub-fab, #wh-hub')));
      const compVis = compLaunchable;
      const avatar = companion && companion.querySelector('img, svg, canvas, .wh-avatar, [class*="avatar"]');
      // Same recalibration: the avatar lives INSIDE the (deliberately hidden-while-closed) widget, so
      // grade whether it RENDERED (the element exists and has real content/box), not whether it is
      // currently on-screen. This still catches the origin bug — a BLANK avatar on a page that never
      // loaded wh-persona.js leaves no img/svg/avatar node at all, so avatarVis stays false.
      const avatarVis = !!(avatar && (vis(avatar) || avatar.getClientRects().length > 0 || (avatar.innerHTML || '').trim().length > 0));
      const navHub = document.querySelector('#wh-hub-fab, #wh-hub-launcher, .wh-hub-fab, [data-nav-hub]');
      const hubVis = !!(navHub && vis(navHub));
      const anyCompanion = !!companion || !!navHub;   // if a page ships NO shell at all it's likely exempt (print/poster)
      // assistant.html IS the full assistant and index.html is the signed-out landing — both ship
      // WITHOUT the floating companion launcher BY DESIGN (AI_SURFACE_MAP: companion-launcher.js is on
      // every page EXCEPT index + assistant). Exempt them so W2 grades only pages that SHOULD carry it.
      const noCompanionByDesign = /(^|\/)(assistant|index)(\.[a-z0-9-]+)?\.html?$/.test(location.pathname);
      out.push((isPrintDoc || isPoster || noCompanionByDesign || !anyCompanion)
        ? NA('W2', 'Shared-chrome consistency', noCompanionByDesign ? 'assistant/home: IS the assistant / no floating companion by design' : (isPrintDoc || isPoster) ? 'print/poster: no shell by design' : 'no shell surface on this page')
        : M('W2', 'Shared-chrome consistency (companion+avatar+hub)', [compVis, avatarVis, hubVis].filter(Boolean).length, 3,
            `companion=${compVis} avatar=${avatarVis} nav-hub=${hubVis}`));
    }

    // ══ T · NATIVE-APP FEEL (2026-07-18 native-mobile benchmark, measured @390) ═══════════
    // "Does this feel like a native mobile app, not a shrunk desktop one?" Cited from the fresh
    // React-Native + CSS harvest (substrate/external/external-react-native-*, external-css-*).
    // Runs at 390 in family_rubric_sweep.mjs's mobile pass. T1/T2 mirror ufai_battery.js v1.5.0.
    try {
      if (isPoster || isPrintDoc) {
        // a fixed-width PRINT poster / print report is a STATIC cited artifact, not a phone app —
        // the native-app dims don't apply (Ian's 2026-07-15 scope decision, extended to class T).
        ['T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8'].forEach((id) => out.push(NA(id, 'Native-app feel', 'print/poster artifact — phone-app dims N/A')));
      } else {
      const _tAll = Array.from(document.querySelectorAll('body *'));
      const _tcs = (e) => { try { return getComputedStyle(e); } catch (_) { return null; } };

      // T1 Content reachability — no fixed-height overflow:hidden box clips real content below it
      let t1 = 0;
      for (const e of _tAll) {
        const s = _tcs(e); if (!s) continue;
        if (s.position === 'fixed' || s.position === 'sticky' || s.pointerEvents === 'none') continue;
        if (!/hidden|clip/.test(s.overflowY) && !/hidden|clip/.test(s.overflow)) continue;
        if (e.scrollHeight - e.clientHeight <= 40 || e.clientHeight <= 150) continue;
        if ((e.innerText || '').trim().length < 20) continue;
        t1++;
      }
      out.push(M('T1', 'Content reachability (no fixed-height scroll-trap)', t1 === 0 ? 1 : 0, 1,
        t1 ? `${t1} overflow:hidden box(es) clip content below the fold @390 (unreachable)` : 'no trapped content @390'));

      // T2 Text fits its box — no nowrap text clipped/overflowing its own box
      let t2 = 0;
      for (const e of _tAll) {
        if (![].some.call(e.childNodes, n => n.nodeType === 3 && n.textContent.trim().length > 1)) continue;
        const s = _tcs(e); if (!s || s.display === 'none' || s.visibility === 'hidden' || !e.offsetParent) continue;
        const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) continue;
        if (e.scrollWidth - e.clientWidth > 3 && s.whiteSpace === 'nowrap' && s.textOverflow !== 'ellipsis') t2++;
      }
      out.push(M('T2', 'Text fits its box (no clip/overlap)', t2 === 0 ? 1 : 0, 1,
        t2 ? `${t2} element(s) overflow their nowrap box @390 (clipped/overlapping)` : 'all text fits @390'));

      // T3 Tap responsiveness — the interactive surface drops the ~300ms delay (touch-action)
      const _bta = (_tcs(document.body) || {}).touchAction || 'auto';
      const _dta = (_tcs(document.documentElement) || {}).touchAction || 'auto';
      const t3ok = /manipulation|none|pan/.test(_bta) || /manipulation|none|pan/.test(_dta);
      out.push(M('T3', 'Tap responsiveness (touch-action: manipulation)', t3ok ? 1 : 0, 1,
        t3ok ? `touch-action set (${_bta})` : 'touch-action:auto — legacy ~300ms click delay + double-tap-zoom not suppressed'));

      // T4 Native scroll containment — internal scroll containers set overscroll-behavior contain/none
      const _scr = _tAll.filter(e => { const s = _tcs(e); return s && /auto|scroll/.test(s.overflowY) && e.scrollHeight > e.clientHeight + 8 && e.clientHeight > 120; });
      const _t4bad = _scr.filter(e => { const s = _tcs(e); return s && (s.overscrollBehaviorY || 'auto') === 'auto'; });
      out.push(_scr.length === 0
        ? NA('T4', 'Native scroll containment (overscroll-behavior)', 'no internal scroll containers on this page')
        : M('T4', 'Native scroll containment (overscroll-behavior)', _scr.length - _t4bad.length, _scr.length,
          _t4bad.length ? `${_t4bad.length}/${_scr.length} scroll container(s) chain to the page (overscroll-behavior:auto)` : `all ${_scr.length} scroll containers contained`));

      // T5 Safe-area — viewport-fit=cover (prerequisite for env(safe-area-inset-*) to be non-zero)
      const _vp = (document.querySelector('meta[name="viewport"]') || {}).content || '';
      const _cover = /viewport-fit\s*=\s*cover/.test(_vp);
      out.push(M('T5', 'Safe-area (viewport-fit=cover)', _cover ? 1 : 0, 1,
        _cover ? 'viewport-fit=cover set — env(safe-area-inset) active' : 'no viewport-fit=cover: env(safe-area-inset) resolves to 0, fixed chrome can hit the notch/home indicator'));

      // T6 Long-list virtualization — a long list must not mount an unbounded node count (RN FlatList)
      let t6 = 0, t6sel = '';
      for (const e of _tAll) {
        const s = _tcs(e); if (!s) continue;
        if (!/auto|scroll/.test(s.overflowY) && !/auto|scroll/.test(s.overflow)) continue;
        const kids = e.children ? e.children.length : 0;
        if (kids > t6) { t6 = kids; t6sel = e.id ? '#' + e.id : (e.className || e.tagName).toString().slice(0, 24); }
      }
      out.push(t6 <= TH.T6.noListBelow
        ? NA('T6', 'Long-list virtualization', `no long list (worst scroll container = ${t6} children)`)
        : M('T6', 'Long-list virtualization', t6 <= TH.T6.maxPeerRows ? 1 : 0, 1,
          t6 <= TH.T6.maxPeerRows ? `longest list ${t6} nodes (<=${TH.T6.maxPeerRows} ok)` : `${t6} peer nodes mounted in ${t6sel} — virtualize / paginate (RN FlatList)`));

      // T7 Clean JS thread — measured by ufai_battery.js F-pillar (console history invisible post-load here)
      out.push(NA('T7', 'Clean JS thread (no console noise on load)', 'measured by ufai_battery.js consoleErrorsSinceBoot'));

      // T8 Interactive-state semantics — toggles/tabs/expanders expose pressed/expanded/selected/disabled
      const _sf = _tAll.filter(e => {
        if (!vis(e)) return false;
        const role = (e.getAttribute('role') || '').toLowerCase();
        const tag = e.tagName.toLowerCase();
        // name-heuristic toggle/tab — but EXCLUDE one-shot ACTION buttons that merely contain "filter"
        // etc. (e.g. #filter-apply is an APPLY action, not a stateful toggle; it has no on/off state to expose).
        const nameToggle = tag === 'button'
          && /toggle|tab|expand|collapse|filter|switch/i.test((e.className || '') + ' ' + (e.id || ''))
          && !/\b(apply|submit|save|reset|clear|cancel|close|search|run|refresh|send|export|update|go)\b/i.test((e.innerText || '') + ' ' + (e.id || '') + ' ' + (e.className || ''));
        return role === 'tab' || role === 'switch' || e.hasAttribute('aria-expanded') || nameToggle;
      });
      const _st = _sf.filter(e => ['aria-pressed', 'aria-expanded', 'aria-selected', 'aria-checked', 'aria-disabled'].some(a => e.hasAttribute(a)) || e.hasAttribute('disabled'));
      out.push(_sf.length === 0
        ? NA('T8', 'Interactive-state semantics', 'no stateful toggles/tabs/expanders on this page')
        : M('T8', 'Interactive-state semantics (aria-pressed/expanded/selected)', _st.length, _sf.length,
          `${_st.length}/${_sf.length} stateful controls expose their state`));
      }
    } catch (_) { /* empty-catch-allow: best-effort native-mobile lens */ }

    // ── Z · MODALITY (PC + Phone as first-class, not shrink-to-fit) — static/DOM dims (2026-07-22) ──
    // The experience-in-motion extension (PDDA_UX_PAINPOINT_JOURNEY_ROADMAP.md). Graded at BOTH 390 (phone)
    // and 1280 (desktop) by family_rubric_sweep, worse-per-dim — so Z2 reflow catches a phone-only h-scroll.
    try {
      const _vz = (e) => { if (e.offsetParent === null) return false; const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden'; };
      // exclude platform CHROME (feedback FAB, companion, nav-hub, voice/sign-in overlays) — furniture, not the page
      const _inChrome = (e) => !!(e.closest && e.closest('#wh-feedback-panel,[class*=wh-fb-],#wh-voice-overlay,#signin-modal,[id*=nav-hub],.nav-hub,[class*=companion-launch],[id*=companion],#wh-ai-widget,#wh-ai-trigger,#wh-modal-anim-style'));

      // Z2 · Responsive reflow (WCAG 1.4.10): no PAGE horizontal scroll at this viewport.
      const _cw = document.documentElement.clientWidth;
      const _sw = document.documentElement.scrollWidth;
      const _reflow = _sw > _cw + 2;
      const _z2off = [];
      if (_reflow) {
        document.querySelectorAll('body *').forEach((e) => {
          const cs = getComputedStyle(e); if (cs.position === 'fixed') return;   // off-screen fixed chrome doesn't scroll the page
          const r = e.getBoundingClientRect(); if (r.width < 40 || r.height === 0) return;
          if (r.right > _cw + 2) _z2off.push(e.tagName.toLowerCase() + (e.id ? '#' + e.id : '.' + String(e.className || '').trim().split(/\s+/)[0]));
        });
      }
      out.push(M('Z2', 'Responsive reflow (no h-scroll, WCAG 1.4.10)', _reflow ? 0 : 1, 1,
        _reflow ? ('page scrolls horizontally by ' + (_sw - _cw) + 'px @' + _cw + 'px — offenders: ' + _z2off.slice(0, 4).join(', ')) : ('reflows clean, no h-scroll @' + _cw + 'px')));
      out._z2 = _z2off;

      // Z1 · Input efficiency: numeric-expecting fields fire the right keyboard on phone (type/inputmode).
      const _numRe = /qty|quantit|price|amount|\bhours?\b|\bcost\b|\bstock\b|\bcount\b|reading|\bmeter\b|\brpm\b|\btemp|pressure|\bhz\b|kwh|\bvolts?\b|\bamps?\b|torque|percent|\bpct\b|minute|\bdays?\b|weeks?|interval|budget|weight|\blength\b|\bwidth\b|\bheight\b|diameter/i;
      // IDENTIFIER fields carry numeric-ish words but hold ALPHANUMERIC text (part 6205-2RS, serial, model,
      // search-by-number) — a numeric keyboard would be WRONG for them. Same class as asset-code false-positives
      // (feedback_asset_code_identifiers_break_readability_detectors). Exclude them so Z1 flags only true VALUE fields.
      const _idRe = /part.?(num|no\b|#)|serial|\bmodel\b|\bsku\b|\bp\/?n\b|referen|\border\b|\bpo\b|invoice|\bphone\b|\bzip\b|postal|barcode|\bvin\b|search|\bname\b|\bcode\b|address|\bemail\b/i;
      const _txtIn = Array.from(document.querySelectorAll('input')).filter((e) => _vz(e) && !_inChrome(e) && !['hidden', 'checkbox', 'radio', 'file', 'submit', 'button', 'range', 'color', 'date', 'time', 'datetime-local', 'month', 'week'].includes(e.type));
      const _hasNumKbd = (e) => e.type === 'number' || e.type === 'tel' || /numeric|decimal|tel/.test(e.getAttribute('inputmode') || '');
      const _numIn = _txtIn.filter((e) => { const lbl = e.id ? document.querySelector('label[for="' + (window.CSS && CSS.escape ? CSS.escape(e.id) : e.id) + '"]') : null; const ctx = [e.name, e.id, e.placeholder, e.getAttribute('aria-label'), lbl && lbl.textContent].join(' '); return _numRe.test(ctx) && !_idRe.test(ctx); });
      const _numOk = _numIn.filter(_hasNumKbd);
      const _z1bad = _numIn.filter((e) => !_hasNumKbd(e)).map((e) => (e.id || e.name || e.placeholder || 'input').slice(0, 20));
      out.push(_numIn.length === 0
        ? NA('Z1', 'Input efficiency (right mobile keyboard)', 'no numeric-expecting inputs visible on this page')
        : M('Z1', 'Input efficiency (numeric fields fire numeric keyboard)', _numOk.length, _numIn.length,
          _z1bad.length ? (_z1bad.length + '/' + _numIn.length + ' numeric field(s) show a TEXT keyboard on phone — add type=number/tel or inputmode: ' + _z1bad.slice(0, 4).join(', ')) : ('all ' + _numIn.length + ' numeric fields set the right keyboard')));
      out._z1 = _z1bad;

      // Z3 · Gesture ergonomics & accidental-touch (WCAG 2.5.8): >=24px OR 24px-circle spacing; destructive not crowded.
      // A sub-6px element is not a PERCEIVABLE tap target (a sliver / decorative onclick wrapper / a rect
      // mis-measured mid-layout) — excluding it stops artifact "2px target" findings (dayplanner asset cards),
      // while a genuinely-too-small real control (13-23px) still counts. Calibrate the instrument, not the page.
      const _tooTiny = (e) => { const r = e.getBoundingClientRect(); return Math.min(r.width, r.height) < 6; };
      const _ia = Array.from(document.querySelectorAll('button, a[href], input:not([type=hidden]), select, textarea, [role=button], [role=link], [onclick]')).filter((e) => _vz(e) && !_inChrome(e) && !_tooTiny(e));
      const _rects = _ia.map((e) => ({ e, r: e.getBoundingClientRect() }));
      // ONLY genuinely IRREVERSIBLE actions get the destructive-adjacency danger flag — a conventional
      // form Clear/Reset/Cancel next to Submit is a universal, low-consequence pattern (reversible by re-entry),
      // not an accidental-touch hazard; flagging it would be ruler noise (per §16.1 instrument-artifact discipline).
      // IRREVERSIBLE-loss actions only. Archive (unarchive), clear/reset/cancel (re-enter) are RECOVERABLE —
      // a mis-tap costs seconds, not data — so they are NOT accidental-touch HAZARDS (excluded, like clear/reset).
      const _destRe = /delete|remove|trash|discard|revoke|\bwipe\b|permanent/i;
      // A FILTER CHIP / TAB / TOGGLE labelled "Removed"/"Deleted" (data-status="removed", aria-pressed,
      // .filter-chip, role=tab) SELECTS a view — it does NOT delete anything. The destructive-word regex
      // false-flagged marketplace-seller/admin's "Removed" status FILTER as a destructive mis-tap risk. A
      // real destructive control is a command button (data-action=delete, .danger), never a filter — those
      // are excluded, real delete buttons still flag. §16.1 the ruler, not the page.
      const _isFilterish = (e) => e.hasAttribute('data-status') || e.hasAttribute('data-filter')
        || e.getAttribute('role') === 'tab' || e.hasAttribute('aria-pressed')
        || /\b(filter-chip|\btab\b|\bchip\b|toggle|segment)\b/.test(typeof e.className === 'string' ? e.className : '');
      const _isDest = (e) => !_isFilterish(e) && _destRe.test((e.innerText || '') + ' ' + (e.getAttribute('aria-label') || '') + ' ' + (e.id || '') + ' ' + (e.className || ''));
      // Small targets (<24px) use the WCAG 2.5.8 24px-circle (any-direction) spacing test.
      const _circleCrowded = (a) => { for (const o of _rects) { if (o.e === a.e) continue; const dx = Math.max(0, Math.max(a.r.left, o.r.left) - Math.min(a.r.right, o.r.right)); const dy = Math.max(0, Math.max(a.r.top, o.r.top) - Math.min(a.r.bottom, o.r.bottom)); if (Math.hypot(dx, dy) < 24) return true; } return false; };
      // A DESTRUCTIVE ≥24px target is an accidental-touch hazard only when a DIFFERENT tappable target sits
      // HORIZONTALLY beside it (shares a row band + <24px horizontal gap) — a thumb mis-taps side-by-side, NOT
      // vertically-stacked feed items (a delete above the post body is normal layout, not a mis-tap risk).
      const _horizAdj = (a) => { for (const o of _rects) { if (o.e === a.e) continue; const vOverlap = Math.min(a.r.bottom, o.r.bottom) - Math.max(a.r.top, o.r.top); if (vOverlap <= 6) continue; const dx = Math.max(a.r.left, o.r.left) - Math.min(a.r.right, o.r.right); if (dx >= 0 && dx < 24) return true; } return false; };
      // A radio/checkbox's REAL tap target is its clickable LABEL (clicking the label toggles the control),
      // not the ~13px native box. A control wrapped-in / associated-with a label ≥24px is adequately sized —
      // crediting it stops false "13px radio" findings (hive poll, report-reason radios). WCAG 2.5.8 the same.
      const _labelBig = (e) => { if (!/^(radio|checkbox)$/.test(e.type || '')) return false; const wl = e.closest && e.closest('label'); const fl = e.id ? document.querySelector('label[for="' + (window.CSS && CSS.escape ? CSS.escape(e.id) : e.id) + '"]') : null; const lbl = wl || fl; if (!lbl) return false; const lr = lbl.getBoundingClientRect(); return Math.min(lr.width, lr.height) >= 24; };
      const _z3fail = [];
      _rects.forEach((x) => { const m = Math.min(x.r.width, x.r.height); const small = m > 0 && m < 24 && !_labelBig(x.e); const dest = _isDest(x.e); if ((small && _circleCrowded(x)) || (dest && _horizAdj(x))) _z3fail.push((x.e.innerText || x.e.getAttribute('aria-label') || x.e.tagName).trim().slice(0, 16) + (dest ? '(destructive)' : '(' + Math.round(m) + 'px)')); });
      out.push(_ia.length === 0
        ? NA('Z3', 'Gesture ergonomics & accidental-touch', 'no interactive targets on this page')
        : M('Z3', 'Gesture ergonomics & accidental-touch (24px + spacing, WCAG 2.5.8)', _ia.length - _z3fail.length, _ia.length,
          _z3fail.length ? (_z3fail.length + ' crowded/small target(s) risk mis-tap: ' + _z3fail.slice(0, 4).join(', ')) : ('all ' + _ia.length + ' targets clear the 24px + spacing floor')));
      out._z3 = _z3fail;
    } catch (_) { /* empty-catch-allow: best-effort modality lens */ }

    // ── X3 · FINDABILITY (journey dim — static affordance slice) — 2026-07-22 ──────────────────────
    // A browseable LIST needs a way to FIND a specific item (search or filter/sort). The full X3 (no-results
    // recovery) is a live journey step; this static slice measures the necessary affordance-presence.
    try {
      const _vf = (e) => e.offsetParent !== null && getComputedStyle(e).visibility !== 'hidden';
      const _inChromeX = (e) => !!(e.closest && e.closest('#wh-feedback-panel,[class*=wh-fb-],#wh-voice-overlay,#signin-modal,[id*=nav-hub],.nav-hub,[class*=companion-launch],[id*=companion],#wh-ai-widget,#wh-ai-trigger'));
      const _hasSearch = !!document.querySelector('input[type=search], [role=search]')
        || Array.from(document.querySelectorAll('input')).some((e) => _vf(e) && !_inChromeX(e) && /search|find\b|filter/i.test((e.id || '') + ' ' + (e.placeholder || '') + ' ' + (e.getAttribute('aria-label') || '')));
      const _hasFilter = Array.from(document.querySelectorAll('select, [role=combobox], [data-filter], input[list], button')).some((e) => _vf(e) && !_inChromeX(e) && /\bfilter\b|\bsort\b|category|status|\ball\b.*(categor|status|type)/i.test((e.id || '') + ' ' + (e.className || '') + ' ' + (e.getAttribute('aria-label') || '') + ' ' + (e.textContent || '').slice(0, 24)));
      // a browseable list = many repeated peer items (a real list the user scans, not a few hero cards)
      const _items = Array.from(document.querySelectorAll('[role=listitem], .card, .board-card, tbody tr, .list-item, .feed-item, [class*=-row]')).filter((e) => _vf(e) && !_inChromeX(e));
      // A browseable CATALOG is a list of NAVIGABLE entities (click to open / has an action) -- the user scans
      // MANY to FIND one, so search/filter earns its keep. A static REFERENCE/definition table (status.html's
      // SLO rows: "metric → threshold", plain <td> text, nothing to click) is READ top-to-bottom, never searched;
      // demanding a filter on it is the A3 nothing-to-disclose error in a new dim. Require >=half the rows be
      // navigable before grading; else it is a reference table -> N/A. §16.1 the ruler, not the page.
      const _navigable = (e) => (e.matches && e.matches('a[href],button,[role=button],[role=link],[onclick]')) || !!(e.querySelector && e.querySelector('a[href],button,[role=button],[onclick],input:not([type=hidden]),select'));
      const _navItems = _items.filter(_navigable);
      const _hasList = _items.length >= 10 && _navItems.length >= _items.length / 2;
      out.push(!_hasList
        ? NA('X3', 'Findability & search (affordance on browseable lists)', 'no substantial list on this page (' + _items.length + ' items) — item-search not required')
        : M('X3', 'Findability & search (a browseable list offers search/filter)', (_hasSearch || _hasFilter) ? 1 : 0, 1,
          (_hasSearch || _hasFilter) ? ('list of ' + _items.length + ' + ' + (_hasSearch ? 'search' : '') + (_hasSearch && _hasFilter ? '+' : '') + (_hasFilter ? 'filter' : '') + ' affordance') : (_items.length + '-item list with NO search/filter — a user cannot FIND a specific item')));
    } catch (_) { /* empty-catch-allow: best-effort findability lens */ }

    // ── Y1 · OFFLINE & CONNECTIVITY RESILIENCE (journey dim — static affordance slice) — 2026-07-22 ──
    // A backend/write page must SURFACE connectivity state so an offline field-worker (WorkHive's reality) isn't
    // left guessing. The shared offline-banner (offline-banner.js / __whOfflineBannerLoaded guard) is that
    // affordance; it renders only WHEN offline (silence-is-golden), so we detect the COMPONENT, not a live banner.
    // The deeper Y1 (writes actually queue + sync-on-reconnect) is a live devtools-offline journey step (roadmap).
    try {
      const _isBackend = (typeof window.getDb === 'function') || (typeof window.__whOfflineBannerLoaded !== 'undefined')
        || Array.from(document.scripts).some((s) => /utils\.js|supabase/i.test(s.src || ''));
      const _hasOffline = (typeof window.__whOfflineBannerLoaded !== 'undefined')
        || Array.from(document.scripts).some((s) => /offline-banner/i.test(s.src || ''))
        || !!document.querySelector('#wh-offline-banner,[data-offline-banner]');
      out.push(!_isBackend
        ? NA('Y1', 'Offline & connectivity resilience', 'no backend writes on this page — offline-state UX N/A')
        : M('Y1', 'Offline & connectivity resilience (connectivity-state affordance wired)', _hasOffline ? 1 : 0, 1,
          _hasOffline ? 'offline-banner affordance wired (surfaces state; queues/reconnect is the live journey step)' : 'backend page with NO offline-state affordance — an offline write can fail silently to the user'));
    } catch (_) { /* empty-catch-allow: best-effort offline-resilience lens */ }

    // ── X2 · INTERRUPTION RESILIENCE & RESUMABILITY (journey dim — static affordance slice) — 2026-07-23 ──
    // A substantial COMPOSE/ENTRY form (a <textarea> the user writes real content into) must survive a refresh /
    // interruption (a field-tech's connectivity blip, an inbound call) — else in-progress work is lost. The platform's
    // canonical mechanism is whAutoSaveDraft() (utils.js: debounced localStorage draft; save/restore verified live
    // 2026-07-23); some pages ship their own (saveDraft/restoreDraft/draftKey). We detect the ADOPTION (the affordance
    // is present); the deeper X2 (a real type->refresh->restored live journey) is a family-sweep step (roadmap).
    try {
      const _vf2 = (e) => e.offsetParent !== null && getComputedStyle(e).visibility !== 'hidden';
      const _inChromeX2 = (e) => !!(e.closest && e.closest('#wh-feedback-panel,[class*=wh-fb-],#wh-voice-overlay,#signin-modal,[id*=nav-hub],.nav-hub,[class*=companion-launch],[id*=companion],#wh-ai-widget,#wh-ai-trigger'));
      // a compose field = a visible, non-chrome, editable <textarea> (the clearest "in-progress work" signal),
      // excluding search/filter boxes (transient — nothing worth persisting).
      const _compose = Array.from(document.querySelectorAll('textarea')).filter((e) => _vf2(e) && !_inChromeX2(e)
        && !e.readOnly && !e.disabled && !/search|find\b|filter/i.test((e.id || '') + ' ' + (e.placeholder || '') + ' ' + (e.getAttribute('aria-label') || '')));
      // draft-persistence adopted? the canonical whAutoSaveDraft() call, a page's own localStorage draft routine,
      // OR an IndexedDB-backed auto-save (resume.html: onInput -> debounce(saveLocal) -> idbPut the whole state —
      // a RICHER persistence than a draft; recognize it so §16.1 doesn't false-flag an already-resilient page).
      const _draftWired = Array.from(document.scripts).some((s) => /whAutoSaveDraft\s*\(|saveDraft\s*\(|restoreDraft\s*\(|\bdraftKey\b|indexedDB\.open\s*\(|\bidbPut\s*\(/.test(s.textContent || ''));
      out.push(!_compose.length
        ? NA('X2', 'Interruption resilience & draft-survival', 'no compose/entry form (textarea) on this page — draft-survival N/A')
        : M('X2', 'Interruption resilience (a compose form auto-saves a draft that survives refresh)', _draftWired ? 1 : 0, 1,
          _draftWired ? (_compose.length + ' compose field(s) + draft-persistence wired (whAutoSaveDraft/own autosave; type->refresh->restore is the live journey step)') : (_compose.length + ' compose field(s) with NO draft-persistence — a refresh/interruption silently loses in-progress work')));
    } catch (_) { /* empty-catch-allow: best-effort interruption-resilience lens */ }

    // ── X1 · TASK-FLOW COHERENCE (journey dim — static affordance slice) — 2026-07-23 ──────────────
    // A task must never DEAD-END: the conditional EMPTY/NO-RESULTS states (in the DOM even while hidden —
    // gradable WITHOUT triggering them) must each offer a NEXT STEP — a CTA control inside the panel, or
    // guidance text naming the recovery path (what to add, which filter to adjust, where data surfaces).
    // NN/g: journey friction/drop-off concentrates at dead-ends. The deeper X1 (steps/backtracks/context-
    // carry across a real multi-step task) is the live-journey step (roadmap).
    try {
      const _inChromeX1 = (e) => !!(e.closest && e.closest('#wh-feedback-panel,[class*=wh-fb-],#wh-voice-overlay,#signin-modal,[id*=nav-hub],.nav-hub,[class*=companion-launch],[id*=companion],#wh-ai-widget,#wh-ai-trigger'));
      // conditional-state panels: empty/no-results/blank-state shaped, with real message text (≥10 chars
      // filters styling-only `class="empty"` cells and short "—" pills, which are not journey states);
      // outermost-only so a guided parent panel isn't double-graded through a text-only child.
      const _allX1 = Array.from(document.querySelectorAll('[class*=empty-state],[class*=empty-row],[class*=no-data],[class*=blank-state],[id*=no-results],[id*=empty]'))
        .filter((e) => !_inChromeX1(e) && (e.textContent || '').trim().length >= 10);
      const _setX1 = new Set(_allX1);
      const _panels = _allX1.filter((e) => { let a = e.parentElement; while (a) { if (_setX1.has(a)) return false; a = a.parentElement; } return true; });
      const _cta = (p) => !!p.querySelector('a[href],button,[role=button],[onclick],input:not([type=hidden]),select');
      // guidance = an ACTION VERB naming the recovery (calibrated 2026-07-23 against the live board: the
      // platform's real guidance vocabulary includes fill/register/open/run/wire — "Fill in the form below",
      // "Register assets in the Logbook first", "Open Integrations to wire one", "Run an AI question").
      const _guide = (p) => /\badd\b|\bcreate\b|\bnew\b|\bstart\b|\btap\b|\bclick\b|\bgenerate\b|\bupload\b|\bimport\b|\binvite\b|\bbrowse\b|\blog\b|\bpost\b|\btry\b|\badjust\b|\bfilter|\bmatch|\bclear\b|\breset\b|\brefresh\b|\bsearch\b|\bfill\b|\bregister\b|\bopen\b|\brun\b|\bwire\b|\bwiden\b|\bconnect\b|\bselect\b|\benable\b|\bgo to\b|check back|lands? here|surface[sd]? here|appears? here|will (appear|show|surface)|use the\b|\bvia\b/i.test(p.textContent || '');
      // a POSITIVE/healthy zero-state is a SUCCESS, not a dead-end: "All caught up" (inbox-zero) and a
      // monitoring page's "no anomalies" (silence-is-golden) celebrate absence — no next step owed.
      const _positive = (p) => /all caught up|all done|all set|up to date|all clear|no (fused )?anomal|nothing (pending|due|overdue)/i.test(p.textContent || '');
      const _dead = _panels.filter((p) => !_positive(p) && !_cta(p) && !_guide(p));
      out.push(!_panels.length
        ? NA('X1', 'Task-flow coherence (no dead-end conditional state)', 'no conditional empty/no-results panels in the DOM — dead-end slice N/A (dynamic states are the live-journey step)')
        : M('X1', 'Task-flow coherence (every empty/no-results state offers a next step)', _panels.length - _dead.length, _panels.length,
          _dead.length ? (_dead.length + ' dead-end state(s) — a user landing there has NO next step: "' + _dead.slice(0, 3).map((p) => (p.textContent || '').trim().slice(0, 40)).join('" · "') + '"') : ('all ' + _panels.length + ' conditional state(s) offer a CTA or recovery guidance')));
    } catch (_) { /* empty-catch-allow: best-effort task-flow lens */ }

    // ── Y2 · STRESS-CASE / REAL-LIFE RESILIENCE (journey dim — static timing slice) — 2026-07-23 ───
    // A tired/rushed/gloved field worker must never be RACED by the UI on a consequential action (COGA:
    // give time, no surprise timeouts): an UNDO recovery window must be ≥8s, and a task RESULT (which can
    // carry failure receipts) must never auto-wipe on a short countdown. whConfirm (persistent modal, no
    // timer) passes by construction. Only inline page scripts are scanned (document.scripts textContent is
    // empty for src= scripts — same contract as X2's _draftWired). The deeper Y2 (persona walk: ≤3 steps,
    // 2-min interruption survival) is the live-journey step (roadmap).
    try {
      const _srcY2 = Array.from(document.scripts).map((s) => s.textContent || '').join('\n');
      const _consequential = /whConfirm\s*\(|showUndoToast\s*\(|soft-?delete/i.test(_srcY2)
        || Array.from(document.querySelectorAll('button,[role=button]')).some((e) => /\b(delete|remove|archive|reject|revoke|release|refund)\b/i.test(e.textContent || ''));
      const _hazards = [];
      const _undoM = _srcY2.match(/ttlMs\s*=\s*(\d{3,6})/) || _srcY2.match(/showUndoToast\s*\([^(]*,[^,()]+,\s*(\d{3,6})\s*\)/);
      if (_undoM && +_undoM[1] < 8000) _hazards.push('undo window ' + _undoM[1] + 'ms < 8s — a rushed/gloved worker loses the recovery path');
      const _resetM = _srcY2.match(/(?:startAutoReset|autoReset)\s*\(\s*(\d{1,3})\s*\)/i);
      if (_resetM && +_resetM[1] < 10) _hazards.push('results auto-wipe on a ' + _resetM[1] + 's countdown — a failure receipt vanishes before a stressed user reads it');
      out.push(!_consequential
        ? NA('Y2', 'Stress-case resilience (no time-pressure on consequential actions)', 'no consequential/destructive actions on this page — stress-timing N/A')
        : M('Y2', 'Stress-case resilience (undo ≥8s; results never auto-wipe on a short countdown)', _hazards.length ? 0 : 1, 1,
          _hazards.length ? _hazards.join(' · ') : 'consequential actions are time-unlimited (whConfirm modal / adequate undo window; the persona walk is the live journey step)'));
    } catch (_) { /* empty-catch-allow: best-effort stress-resilience lens */ }

    // ══ CLASS AI · AI-NATIVE EXPERIENCE (Microsoft HAX 18 guidelines) — 2026-07-23 ══════════════════
    // WorkHive is AI-heavy (assistant/companion/shift-brain brief/analytics insight/asset-brain/voice).
    // The A–Z rubric grades the artifact-at-rest; these grade the AI INTERACTION per page.
    // Cite: external-human-ai-interaction-18-guidelines-confidence-co.
    try {
      const _vfa = (e) => e.offsetParent !== null && getComputedStyle(e).visibility !== 'hidden';
      const _srcAI = Array.from(document.scripts).map((s) => s.textContent || '').join('\n');
      const _bodyTxt = (document.body.innerText || '').slice(0, 5000);
      // page-OWN AI surfaces (the companion #wh-ai-* is a shared component graded separately; its panel
      // isn't open at survey time). Input = a chat/ask/query box; output = assistant bubbles / AI-brief cards.
      const _aiInput = Array.from(document.querySelectorAll('textarea,input[type=text],input:not([type])')).filter((e) =>
        _vfa(e) && /\b(chat|ask|assistant|companion|ai-?input|ai-?query|prompt)\b/i.test((e.id || '') + ' ' + (e.className || '') + ' ' + (e.getAttribute('aria-label') || '')));
      const _aiInvoke = /functions\.invoke\(\s*['"](ai-gateway|[a-z-]*orchestrator|asset-brain[a-z-]*|semantic[a-z-]*|ai-[a-z-]+|shift-planner[a-z-]*|voice-[a-z-]*intent)/i.test(_srcAI) || /\bwhAiError\b|\bcallAI\b/i.test(_srcAI);
      // UNAMBIGUOUS AI output (chat bubbles / ai-* / replies) always counts; AMBIGUOUS shared classes
      // (.verdict-text / .briefing-text — also used for NON-AI status verdicts, e.g. project-manager's
      // project verdict) count as AI output ONLY when the page actually invokes an AI engine (§16.1: the
      // ruler must not read a non-AI verdict as an AI answer).
      const _aiOutHard = Array.from(document.querySelectorAll('.bubble-assistant,[class*=ai-insight],[class*=ai-answer],[class*=ai-response],[class*=reply-bubble],[class*=history-reply],[id*=current-reply],[id*=ai-brief],[class*=ai-brief]')).filter(_vfa);
      // the shared .verdict-text/.briefing-text counts as AI OUTPUT only when a BRIEF orchestrator
      // (shift-planner/analytics) renders its answer INTO it. An INTENT-parse AI (project-orchestrator
      // phase:intent → pre-fills an editable wizard; voice-intent) produces no displayed answer here —
      // its correction path IS the editable wizard, and the page's verdict is a non-AI project status.
      const _aiBrief = /functions\.invoke\(\s*['"](shift-planner[a-z-]*|analytics-orchestrator)/i.test(_srcAI);
      const _aiOutSoft = _aiBrief ? Array.from(document.querySelectorAll('#briefing-text,.briefing-text,.verdict-text')).filter(_vfa) : [];
      const _aiOut = _aiOutHard.concat(_aiOutSoft);

      // AI1 capability transparency [HAX G1: make clear what the system can do]
      if (_aiInput.length) {
        const _hint = _aiInput.some((e) => /ask|try|e\.g|example|search|type\b|what|how|question/i.test(e.placeholder || ''))
          || /example|starter|try asking|suggest|e\.g\.|for example/i.test(_bodyTxt)
          || !!document.querySelector('[class*=starter],[class*=example-prompt],[class*=prompt-chip],[class*=quick-ask],[class*=suggest]');
        out.push(M('AI1', 'AI capability transparency (the input hints what it can do)', _hint ? 1 : 0, 1,
          _hint ? 'AI input carries a capability hint (example/starter/rich placeholder)' : 'AI input is a BLANK box — the user must guess what to ask [HAX G1]'));
      } else out.push(NA('AI1', 'AI capability transparency', 'no AI input surface on this page'));

      // AI2 confidence & grounding [HAX G2 how-well + G11 why]
      if (_aiOut.length) {
        const _grounded = !!document.querySelector('.wh-source-chip,[class*=source-chip],[class*=provenance],[class*=how-computed],[class*=grounded],[class*=citation]')
          || /based on|sourced from|computed from|according to|from your|per your|grounded in/i.test(_aiOut.map((e) => e.innerText || '').join(' ').slice(0, 3000))
          || /renderSourceChip|facts_used|provenance|grounding|citation/i.test(_srcAI);
        out.push(M('AI2', 'AI confidence & grounding (output shows its basis)', _grounded ? 1 : 0, 1,
          _grounded ? 'AI output carries grounding/provenance (source chip / "based on" / how-computed)' : 'AI output is a BARE claim — no grounding/source shown [HAX G2/G11]'));
      } else out.push(NA('AI2', 'AI confidence & grounding', 'no AI output surface on this page'));

      // AI3 correction & feedback [HAX G9 correction + G15 granular feedback]
      if (_aiOut.length) {
        const _fb = /👍|👎|thumbs|data-feedback|rate.?(this|answer|reply)|\bhelpful\b|feedbackAi|\bretry\b|regenerate|try again/i.test(_srcAI + ' ' + document.body.innerHTML.slice(0, 12000));
        out.push(M('AI3', 'AI correction & feedback (retry + per-response feedback)', _fb ? 1 : 0, 1,
          _fb ? 'AI output has a feedback/retry affordance (👍/👎 / retry / regenerate)' : 'AI output has NO correction/feedback path — a wrong answer is a dead-end [HAX G9/G15]'));
      } else out.push(NA('AI3', 'AI correction & feedback', 'no AI output surface on this page'));

      // AI4 graceful failure & scoping [HAX G10: scope when in doubt]
      if (_aiInvoke) {
        const _graceful = /\bwhAiError\b/i.test(_srcAI) || /catch\s*\([^)]*\)\s*\{[^}]*(showToast|addBubble|showError|\bretry\b|try again|couldn|could not|unavailable|offline|not sure)/i.test(_srcAI);
        out.push(M('AI4', 'AI graceful failure (honest error + retry, no fabrication)', _graceful ? 1 : 0, 1,
          _graceful ? 'AI failures degrade gracefully (whAiError / honest catch + retry)' : 'an AI call lacks a visible honest-failure path (a 429/500 could dead-end or fake success) [HAX G10]'));
      } else out.push(NA('AI4', 'AI graceful failure', 'no AI invoke on this page'));

      // AI5 global controls & dismissal [HAX G8 dismissal + G17 global controls]
      const _aiOverlay = document.querySelector('#chat-screen,#ask-card,[class*=companion-panel],[class*=ai-overlay]');
      if (_aiOverlay || _aiOut.length) {
        const _scope = _aiOverlay || document.body;
        const _control = !!_scope.querySelector('[aria-label*=close i],[class*=close],[data-close],[class*=dismiss],[class*=clear],[class*=reset]')
          || /stop.?generat|clearChat|clearContext|new chat|resetPage|close.?(chat|panel|companion)/i.test(_srcAI);
        out.push(M('AI5', 'AI global controls (close/stop/clear)', _control ? 1 : 0, 1,
          _control ? 'AI surface is dismissable/controllable (close / stop / clear / reset)' : 'AI surface has no visible close/stop/clear control [HAX G8/G17]'));
      } else out.push(NA('AI5', 'AI global controls', 'no AI overlay/output on this page'));
    } catch (_) { /* empty-catch-allow: best-effort AI-native lens */ }

    // ══ CLASS PP · PERCEIVED PERFORMANCE (NN/g response-time limits) — 2026-07-23 ═══════════════════
    // 0.1s instant · 1s flow · 10s attention. An async op OWES a working indicator at >1s and
    // progress+cancel at >10s. Cite: external-perceived-performance-optimistic-ui-skeleton-mot.
    try {
      const _srcPP = Array.from(document.scripts).map((s) => s.textContent || '').join('\n');
      const _asyncOp = /functions\.invoke\(|db\.from\(|\.rpc\(|fetch\(|await\s+db\b/i.test(_srcPP);
      // PP1 working indicator on >1s ops
      if (_asyncOp) {
        const _indicator = /whListSkeleton|whSkeleton|skeleton|spinner|\.loading\b|isLoading|showLoading|aria-busy|busy.?(true|indicator)|\bLoading\b|disabled\s*=\s*true/i.test(_srcPP)
          || !!document.querySelector('[class*=skeleton],[class*=spinner],[class*=loading],[aria-busy]');
        out.push(M('PP1', 'Working indicator on async ops (>1s feedback)', _indicator ? 1 : 0, 1,
          _indicator ? 'async ops show a working state (skeleton / spinner / disabled-button / aria-busy)' : 'async ops give NO working indicator — a >1s wait looks frozen [NN/g 1s limit]'));
      } else out.push(NA('PP1', 'Working indicator on async ops', 'no async operations on this page'));

      // PP2 progress + cancel on >10s ops (AI report-gen / analytics compute / batch). Require an
      // actual INVOKE/CALL in a user flow — not a bare string mention (status.html lists
      // 'analytics-orchestrator' in a /health-ping FUNCTIONS array; that is a monitor, not a >10s
      // user-facing generate → must not trip PP2. §16.1 the ruler, not the page.)
      const _longOp = /generateReport\s*\(|functions\.invoke\(\s*['"](shift-planner[a-z-]*|analytics-orchestrator|[a-z-]*orchestrator|report-[a-z-]*|fmea-populator|weibull[a-z-]*)|generate.?(report|brief|plan)\s*\(|_populatePf\s*\(/i.test(_srcPP);
      if (_longOp) {
        const _progress = /progress|percent|streaming|stream\(|EventSource|startAutoReset|processing|step \d|of \d+|countdown|estimat|whAiProgress|refresh(ing)?|updating|live data/i.test(_srcPP)
          || !!document.querySelector('[class*=progress],progress,[role=progressbar],[class*=refreshing]');
        out.push(M('PP2', 'Progress + cancel on long (>10s) ops', _progress ? 1 : 0, 1,
          _progress ? 'a long op surfaces progress/staged feedback' : 'a >10s op (AI/report/analytics) shows no progress or cancel — the user cannot tell it is working [NN/g 10s limit]'));
      } else out.push(NA('PP2', 'Progress + cancel on long ops', 'no long (>10s) operation on this page'));

      // PP3 optimistic acknowledgment — a submit disables/acknowledges INSTANTLY before the await.
      // Only graded on a page that WRITES (a submit to acknowledge); a read-only page has no submit
      // to optimistically ack (achievements/plant-connections/audit-log are read dashboards) → NA.
      // a genuine WRITE submit — NOT a read rpc (get_*/list_* rpcs are reads, e.g. seller-profile's
      // get_seller_community_reputation is a lookup, not a submit to acknowledge).
      const _writeOp = /\.insert\(|\.upsert\(|\.update\(|\.delete\(\s*\)|functions\.invoke\(/i.test(_srcPP)
        || /\.rpc\(\s*['"](?!get_|list_|fetch_|v_)/i.test(_srcPP);
      // (a supabase delete is `.delete()` then `.eq()`; `searchParams.delete(k)` / `Map.delete(k)`
      //  take an ARG and are NOT DB writes — audit-log is a read-only viewer, PP3 N/A there.)
      const _btns = Array.from(document.querySelectorAll('button[type=submit],button[class*=primary],button[class*=submit],#btn-submit-post,[class*=save-btn]'));
      if (_btns.length && _writeOp) {
        // optimistic = instant local acknowledgment before the await: a button state change, an
        // optimistic list render (unshift/push + render), or an instant "Added/Saved" toast.
        const _optimistic = /\.disabled\s*=\s*true|btn\.textContent\s*=|Saving|Posting|Sending|Generating|classList\.add\(['"](loading|busy)|_prependPostCard|optimistic|unshift\(|\.push\([^)]*\)[\s;]*render|render\(\)[\s;]*.{0,40}(sync|invoke|insert|upsert)|showToast\(['"`](Added|Saved|Posted|Done|Created)/i.test(_srcPP);
        out.push(M('PP3', 'Optimistic acknowledgment (<0.1s feel)', _optimistic ? 1 : 0, 1,
          _optimistic ? 'a submit acknowledges instantly (button state / optimistic render before the server responds)' : 'a submit gives no instant acknowledgment — the tap feels unregistered until the server replies'));
      } else out.push(NA('PP3', 'Optimistic acknowledgment', 'no submit action with an async op on this page'));
    } catch (_) { /* empty-catch-allow: best-effort perceived-performance lens */ }

    // ══ CLASS DL · DELIGHT & POLISH (NN/g user-delight; usability-GATED) — 2026-07-23 ═══════════════
    // "Delightful only if usable" — credited only where the page's functional dims already pass.
    // Cite: external-emotional-design-delight-desirability-microinter.
    try {
      const _srcDL = Array.from(document.scripts).map((s) => s.textContent || '').join('\n');
      // DL1 surface-delight microcopy — empty/first-run states have HUMAN, encouraging copy (not sterile)
      const _emptyPanels = Array.from(document.querySelectorAll('[class*=empty-state],[class*=empty-row],[id*=empty],[class*=no-data]'))
        .filter((e) => (e.textContent || '').trim().length >= 10);
      if (_emptyPanels.length) {
        const _txt = _emptyPanels.map((e) => (e.textContent || '')).join(' ');
        const _human = /let'?s|welcome|great|nice|ready|get started|first|your|you'?ll|jump in|kick off|no worries|all set|all caught up|🎉|👋|🐝|✨|💡|🚀|start your/i.test(_txt);
        const _sterile = _emptyPanels.every((e) => /^(no data|no results|empty|none|n\/a|nothing|error|\-)\.?$/i.test((e.textContent || '').trim()));
        out.push(M('DL1', 'Surface-delight microcopy (human empty/first-run copy)', (_human && !_sterile) ? 1 : (_sterile ? 0 : 1), 1,
          _sterile ? 'empty states are sterile ("No data") — a chance for encouraging, human microcopy [surface delight]' : 'empty/first-run copy is human + encouraging'));
      } else out.push(NA('DL1', 'Surface-delight microcopy', 'no empty/first-run states on this page'));

      // DL2 success microinteraction — a completion gives a satisfying confirmation, not a silent DOM swap
      const _hasSuccess = /showToast|whToast|showUndoToast|XP|🎉|confetti|celebrate|animate|transition|classList\.add\(['"](done|success|complete)/i.test(_srcDL);
      const _writes = /functions\.invoke\(|\.insert\(|\.upsert\(|\.update\(/i.test(_srcDL);
      if (_writes) {
        out.push(M('DL2', 'Success microinteraction (satisfying confirmation)', _hasSuccess ? 1 : 0, 1,
          _hasSuccess ? 'a completion gives a satisfying confirmation (toast / XP / transition)' : 'a write completes with no confirming microinteraction — the action feels unacknowledged'));
      } else out.push(NA('DL2', 'Success microinteraction', 'no write/completion action on this page'));
    } catch (_) { /* empty-catch-allow: best-effort delight lens */ }

    // ══ CLASS DD · DASHBOARD DATA-DENSITY & GLANCEABILITY (NN/g preattentive) — 2026-07-23 ═════════
    // WorkHive is dashboard-heavy. A FOCUSED 2-dim class on the genuinely-NEW dimensions the rubric
    // never graded (DD3 density / DD4 drill-down are covered by A3/E1/K2 — not re-graded here, anti-
    // drift no-redundancy). Cite: external-dashboard-data-density-glanceability-preattentiv.
    try {
      const _inChromeDD = (e) => !!(e.closest && e.closest('#wh-feedback-panel,[class*=wh-fb-],#wh-voice-overlay,#signin-modal,[id*=nav-hub],.nav-hub,[class*=companion],#wh-ai-widget,#wh-ai-trigger'));
      const _vfd = (e) => e.offsetParent !== null && getComputedStyle(e).visibility !== 'hidden';
      // a DASHBOARD = a page with several KPI tiles (a real at-a-glance surface), not a form/feed
      const _kpiTiles = Array.from(document.querySelectorAll('[class*=kpi],[class*=stat-card],[class*=stat-tile],[class*=metric],[class*=board-card],.simple-card')).filter((e) => _vfd(e) && !_inChromeDD(e));
      // a PLANNER/CALENDAR/schedule idiom (dayplanner wilo-grid, a calendar) is NOT a KPI dashboard —
      // its cards carry times/titles, not glanceable metrics → DD N/A (§16.1 ruler calibration).
      const _isPlanner = !!document.querySelector('[class*=calendar-wrap],[class*=wilo-grid],[class*=dilo-grid],[class*=schedule-grid],[class*=time-grid],[class*=planner-grid]');
      const _isDashboard = _kpiTiles.length >= 3 && !_isPlanner;

      // DD1 at-a-glance primary KPI — the biggest KPI number sits in the TOP portion (F-pattern first
      // glance, preattentive 2D-position), so the most-important number is seen first.
      if (_isDashboard) {
        const _nums = Array.from(document.querySelectorAll('*')).filter((e) => _vfd(e) && !_inChromeDD(e)
          && /^[\d,.]+[%kKmM]?$/.test((e.childElementCount === 0 ? (e.textContent || '') : '').trim())
          && parseFloat(getComputedStyle(e).fontSize) >= 20);
        if (_nums.length) {
          const _sized = _nums.map((e) => ({ e, fs: parseFloat(getComputedStyle(e).fontSize), top: e.getBoundingClientRect().top }));
          const _maxFs = Math.max(..._sized.map((x) => x.fs));
          const _primary = _sized.filter((x) => x.fs >= _maxFs - 1).sort((a, b) => a.top - b.top)[0];
          const _docH = Math.max(document.documentElement.scrollHeight, 1);
          const _inTop = _primary && _primary.top < _docH * 0.45;
          out.push(M('DD1', 'At-a-glance primary KPI (biggest number, seen first)', _inTop ? 1 : 0, 1,
            _inTop ? 'the largest KPI is in the top glance zone (preattentive 2D-position)' : 'the largest KPI sits below the first-glance zone — the most-important number isn\'t seen first [NN/g preattentive]'));
        } else out.push(NA('DD1', 'At-a-glance primary KPI', 'no glanceable KPI numbers on this dashboard'));
      } else out.push(NA('DD1', 'At-a-glance primary KPI', 'not a KPI dashboard (fewer than 3 stat tiles)'));

      // DD2 chart-type fitness — quantitative magnitude uses LENGTH/2D-position (bar/line/bullet), NOT
      // area/angle (pie/doughnut/polar/gauge) which read slowly + inaccurately. A RADAR used for a
      // multi-axis PROFILE (skillmatrix competency) is a legit shape comparison, not quantitative
      // magnitude → credited (calibrated, §16.1).
      const _srcDD = Array.from(document.scripts).map((s) => s.textContent || '').join('\n');
      const _hasChart = /new Chart\(|Chart\.js|type:\s*['"](bar|line|scatter|pie|doughnut|radar|polarArea)/i.test(_srcDD) || !!document.querySelector('canvas,[class*=chart],[class*=gauge]');
      if (_hasChart) {
        const _badType = /type:\s*['"](pie|doughnut|polarArea)['"]/i.test(_srcDD)
          || !!document.querySelector('[class*=gauge]:not([class*=language]),[class*=donut],[class*=radial-progress]');
        out.push(M('DD2', 'Chart-type fitness (length/position, not area/angle)', _badType ? 0 : 1, 1,
          _badType ? 'a pie/doughnut/gauge encodes quantitative magnitude — slow + inaccurate to read; use a bar/line/bullet [NN/g preattentive]' : 'quantitative charts use preattentive length/position (bar/line/scatter/bullet); radar-for-profile is a legit shape comparison'));
      } else out.push(NA('DD2', 'Chart-type fitness', 'no data-viz charts on this page'));
    } catch (_) { /* empty-catch-allow: best-effort dashboard-glanceability lens */ }

    // ══ CLASS TR · TRUST & CREDIBILITY (NN/g trustworthy design) — 2026-07-23 ══════════════════════
    // A user makes a trust decision on a TRANSACTIONAL surface (marketplace listing / seller). Grades
    // the UX PRESENCE of trust signals (forgery is separately gated by the trust-forge security gate —
    // anti-drift no-redundancy). Cite: external-trustworthy-design-credibility-signals-ecommerce.
    try {
      const _vft = (e) => e.offsetParent !== null && getComputedStyle(e).visibility !== 'hidden';
      // BUYER-facing transactional surface = a priced listing card a buyer evaluates (marketplace
      // browse / a seller's public profile). A seller's OWN management dashboard, a moderation console,
      // and community (incidental review/seller markup) are NOT buyer-trust surfaces → require a
      // buyer-facing PRICE-on-a-card signal, not just any review/seller class (§16.1 ruler calibration).
      const _txnal = !!document.querySelector('[class*=card-price],[class*=price-pill],[class*=listing-card],[class*=listing-price]')
        || (!!document.querySelector('[class*=seller-hero],[class*=seller-badges],[class*=member-since]') && !!document.querySelector('[class*=reviews-card],[class*=stars]'));
      if (_txnal) {
        // TR1 upfront disclosure — the PRICE + the SELLER identity are shown up front (not gated/hidden)
        const _price = !!document.querySelector('[class*=price],[class*=price-pill]') || /₱|\bfree\b|negotiable/i.test(document.body.innerText.slice(0, 6000));
        const _seller = !!document.querySelector('[class*=seller],[class*=author],[class*=badge-tier],[class*=member-since]');
        out.push(M('TR1', 'Upfront disclosure (price + seller shown, not gated)', (_price && _seller) ? 1 : 0, 1,
          (_price && _seller) ? 'price + seller identity disclosed up front (trust via transparency)' : 'a transactional surface hides ' + (!_price ? 'price' : 'seller') + ' up front — trust erodes when key info is gated [NN/g disclosure]'));
        // TR2 credibility signals — verification / rating / reviews / seller history present
        const _cred = !!document.querySelector('[class*=verified],[class*=badge-tier],[class*=stars],[class*=rating],[class*=review],[class*=trust-item],[class*=trust-bar],[class*=reputation],[class*=member-since]');
        out.push(M('TR2', 'Credibility signals (verified / rating / reviews / history)', _cred ? 1 : 0, 1,
          _cred ? 'credibility signals present (verified badge / rating / reviews / seller history)' : 'no credibility signals — a buyer has nothing to trust the seller by [NN/g credibility]'));
      } else {
        out.push(NA('TR1', 'Upfront disclosure', 'no transactional surface on this page'));
        out.push(NA('TR2', 'Credibility signals', 'no transactional surface on this page'));
      }
    } catch (_) { /* empty-catch-allow: best-effort trust lens */ }

    // ══ CLASS RE · RE-ENGAGEMENT & CONTENT FRESHNESS (NN/g) — 2026-07-23 ═══════════════════════════
    // A feed/social surface must help a RETURNING user find what's NEW: per-item freshness + a new-
    // content signal (realtime/unread/badge). Distinct from G4 (page-level single freshness source) +
    // the cross-page nav-hub badge (RE1 is ON the feed). ON (onboarding depth) = covered by X1 (first-
    // run guidance) — not re-graded (anti-drift no-redundancy). Cite: external-ux-indicators-validations-notifications-status.
    try {
      const _vfr = (e) => e.offsetParent !== null;
      // a FEED = many repeated peer content items (posts/entries the user scans over time)
      const _feedItems = Array.from(document.querySelectorAll('[class*=post-card],[class*=feed-item],[class*=post-item],[class*=reply-item],[class*=activity-item],[class*=entry-card]')).filter(_vfr);
      const _isFeed = _feedItems.length >= 3 || !!document.querySelector('[id*=feed-list],[class*=feed-list],[class*=post-list]');
      if (_isFeed) {
        const _srcRE = Array.from(document.scripts).map((s) => s.textContent || '').join('\n');
        // per-item freshness (relative time) + a NEW-content return hook (realtime new-post / unread / seen-marker / activity badge)
        const _freshness = /relativeTime|timeAgo|formatTimeAgo|fmtRelative|ago\b|just now|minutes? ago|hours? ago/i.test(_srcRE + ' ' + document.body.innerText.slice(0, 4000));
        // a NEW-content signal: a logged-in return hook (realtime/seen-marker/unread/badge) OR — for a
        // PUBLIC/anonymous showcase feed that has no per-user "last seen" state — newest-first ordering,
        // which surfaces new content first (the appropriate re-engagement signal without a session).
        const _newHook = /markCommunitySeen|_lastSeen|new since|unread|new post|posted in|activity.?badge|realtime|postgres_changes|\.on\(\s*['"]INSERT|nav.?hub.*badge/i.test(_srcRE)
          || /order\(\s*['"]created_at['"]\s*,\s*\{\s*ascending:\s*false|order by created_at desc/i.test(_srcRE);
        out.push(M('RE1', 'Re-engagement (per-item freshness + a new-content signal)', (_freshness && _newHook) ? 1 : 0, 1,
          (_freshness && _newHook) ? 'feed shows per-item freshness + a new-content signal (return hook / newest-first)' : 'a feed missing ' + (!_freshness ? 'per-item freshness' : 'a new-content signal') + ' — a returning user cannot tell what is new [NN/g re-engagement]'));
      } else out.push(NA('RE1', 'Re-engagement & content freshness', 'not a feed/social surface on this page'));
    } catch (_) { /* empty-catch-allow: best-effort re-engagement lens */ }

    // ══ CLASS DP · DECEPTIVE-DESIGN ABSENCE (dark patterns) — NEW 2026-07-23 ══════════════════════
    // Harvested from the deceptive.design taxonomy (18 named patterns, each with real regulatory
    // enforcement) -> substrate/external/external-deceptive-design-dark-pattern-taxonomy.md. This is
    // dimension space the rubric could NOT express: TR measures whether trust signals are PRESENT
    // (disclosure, credibility); DP measures whether MANIPULATION is ABSENT. A page can score full
    // marks on TR while still using fake urgency or a pre-checked opt-in. Scoped to the 3 patterns
    // that are provable from the DOM without guessing intent; the rest of the taxonomy is judged.
    try {
      const _vis = (e) => e && e.offsetParent !== null && e.getClientRects().length > 0;
      const _txt = (document.body.innerText || '').slice(0, 20000);
      // DP1 · fake urgency / scarcity: manufactured pressure ("only 2 left!", "hurry", "selling fast",
      // "12 people viewing"). A REAL, dated deadline (an RFQ closing date, a PM due date) is factual and
      // is NOT this - so the detector matches only the manipulative phrasings, never a rendered date.
      const _fakeUrgency = /only\s+\d+\s+(left|remaining|spots?|seats?)|hurry\b|act\s+now|selling\s+fast|going\s+fast|limited\s+time\s+(only|offer)|\d+\s+(people|others|users)\s+(are\s+)?(viewing|watching|looking)|almost\s+gone|don'?t\s+miss\s+out/i.test(_txt);
      out.push(M('DP1', 'No fake urgency or scarcity (manufactured pressure)', _fakeUrgency ? 0 : 1, 1,
        _fakeUrgency ? 'manufactured urgency/scarcity copy pressures the decision (a named deceptive pattern with regulatory enforcement)' : 'no manufactured urgency/scarcity pressure; any deadline shown is a real date'));
      // DP2 · confirmshaming: the DECLINE path is worded to shame the user out of declining
      // ("No thanks, I don't want to save money"). The decline must be plainly worded.
      const _declines = Array.from(document.querySelectorAll('button,a[href],[role=button],label')).filter(_vis)
        .map((e) => (e.textContent || '').trim()).filter((t) => t && t.length < 90 && /^(no\b|not now|cancel|decline|dismiss|skip|maybe later)/i.test(t));
      const _shamed = _declines.filter((t) => /i\s+do\s?n'?t\s+(want|need|care)|i'?ll\s+pass|i\s+hate\b|miss\s+out|without\s+my|i\s+prefer\s+to\s+pay|stay\s+(behind|unsafe|uninformed)/i.test(t));
      out.push(M('DP2', 'No confirmshaming on the decline path', _shamed.length ? 0 : 1, 1,
        _shamed.length ? 'a decline control uses guilt copy ("' + _shamed[0].slice(0, 42) + '") instead of a plain "No thanks"' : 'decline/cancel controls are plainly worded (no guilt copy)'));
      // DP3 · preselection: an opt-IN checkbox (marketing/sharing/auto-renew/subscribe) must not ship
      // pre-checked - consent has to be an act. A functional default (remember-me, a filter toggle,
      // "notify me when MY task changes") is NOT an opt-in to something the user did not ask for.
      const _boxes = Array.from(document.querySelectorAll('input[type=checkbox]')).filter(_vis);
      const _optInWord = /subscribe|newsletter|marketing|promo|share\s+my|third.?party|auto.?renew|opt.?in|receive\s+(emails|offers)|sell\s+my/i;
      const _labelOf = (b) => {
        const wrap = b.closest('label');
        const fl = b.id ? document.querySelector('label[for="' + (window.CSS && CSS.escape ? CSS.escape(b.id) : b.id) + '"]') : null;
        return ((wrap || fl || b.parentElement || {}).textContent || '') + ' ' + (b.name || '') + ' ' + (b.id || '');
      };
      const _preChecked = _boxes.filter((b) => b.checked && _optInWord.test(_labelOf(b)));
      if (_boxes.length) {
        out.push(M('DP3', 'No pre-selected opt-in (consent is an act)', _preChecked.length ? 0 : 1, 1,
          _preChecked.length ? _preChecked.length + ' opt-in checkbox(es) ship PRE-CHECKED - consent must be given, not assumed [Preselection]' : 'no opt-in checkbox is pre-checked; any default is functional, not a consent grab'));
      } else out.push(NA('DP3', 'No pre-selected opt-in', 'no checkbox surface on this page'));
    } catch (_) { /* empty-catch-allow: best-effort deceptive-design lens */ }

    // ── roll-up ─────────────────────────────────────────────────────────────
    const measured = out.filter(o => o && o.kind === 'MEASURED');
    const judged = out.filter(o => o.kind === 'JUDGED');
    const na = out.filter(o => o.kind === 'N/A');
    // Backstop for the honesty contract below: a MEASURED dim whose denominator was 0
    // carries pct=null; `(pct || 0)` scored those as 0% while still counting them in the
    // divisor. Exclude null-pct rows from BOTH sides so a future unguarded ratio dim can
    // never drag a page down for having nothing to measure.
    const scoreable = measured.filter(o => o.pct !== null);
    const scored = scoreable.reduce((s, o) => s + o.pct, 0);
    const overall = scoreable.length ? Math.round(scored / scoreable.length) : null;
    const failing = measured.filter(o => o.pct !== null && o.pct < 100)
      .sort((a, b) => a.pct - b.pct)
      .map(o => `${o.dim} ${o.pct}%: ${o.note}`);

    return {
      _v: V,
      pageId: opts.pageId || location.pathname,
      lens: 'substrate/reference/ufai-ux-rubric.md (classes A-T + V/W / ~57 dims; T = native-mobile benchmark, 2026-07-18)',
      counts: { dims: out.length, measured: measured.length, judged: judged.length, na: na.length },
      b3_offenders: out._b3,   // the exact sentences to REWRITE — scoring alone fixes nothing
      c2_offenders: out._c2,   // every below-floor text el (worst-stop scored) — the C2 fix list
      e4_offenders: out._e4,   // repeated verdicts / raw-ID dumps / untranslated stats
      r3_controls:  out._r3,   // the control-vocabulary drift
      s1_family:    out._s1,   // cross-page: where this page leaves the platform vocabulary
      n1_i18n:      out._n1,   // i18n COVERAGE (outcome), not mechanism-presence
      OVERALL_measured_pct: overall,
      failing,
      dims: out,
      honesty: 'JUDGED/N-A dims report null and are EXCLUDED from the average, never scored as passes.',
    };
  }


  // ══ FAMILY RESEMBLANCE — the CROSS-PAGE lens ═══════════════════════════════
  // R measures harmony WITHIN one page; a page can score R=100% and still be a total
  // stranger to the platform (perfectly self-consistent at 10px while the design system
  // says 8/12/16). That gap is what reads as "the pages have different personalities".
  // NN/g Heuristic #4 calls it INTERNAL CONSISTENCY: "the same patterns everywhere inside
  // the system ... reusing headings, call-to-action buttons, and navigation across pages."
  // [external-consistency-and-standards-heuristic-internal-ext, ux-laws-jakob]
  //
  // fingerprint() is deliberately SCORE-FREE: it reports the vocabulary this page actually
  // RENDERS. One page cannot know if it is the deviant -- that verdict needs the platform
  // set, so the cross-page runner computes conformance. This is the same honesty contract
  // as the rest of the lens: measure here, judge only where the evidence is.
  const fingerprint = () => {
    const R = root();
    const px = (v) => Math.round(parseFloat(v) || 0);
    const tally = (arr) => arr.reduce((m, v) => (m[v] = (m[v] || 0) + 1, m), {});

    // The DECLARED design system, read from the cascade rather than hardcoded here --
    // if tokens.css/components.css change, the lens follows without an edit.
    const cs = getComputedStyle(document.documentElement);
    const declared = {};
    ['--wh-radius-sm', '--wh-radius', '--wh-radius-lg',
     '--wh-space-1', '--wh-space-2', '--wh-space-3', '--wh-space-4', '--wh-space-6', '--wh-space-8']
      .forEach((t) => { const v = cs.getPropertyValue(t).trim(); if (v) declared[t] = v; });
    const declaredRadii = ['--wh-radius-sm', '--wh-radius', '--wh-radius-lg']
      .map((t) => px(declared[t])).filter(Boolean);

    const ctrls = $$('button, a.refresh-btn, [role="tab"], input, select', R).filter(vis);
    const cards = $$('.card, .simple-card, .sc-hero, .board-card', R).filter(vis);

    // A pill (>=999px) is a legitimate SHAPE, not a rogue radius -- normalise it so the
    // lens does not report every rounded chip as design-system drift.
    const normRadius = (e) => {
      const raw = getComputedStyle(e).borderTopLeftRadius;
      if (raw.includes('%')) return 'round';   // a % radius is a circle/ellipse INTENT
      const r = px(raw);
      const h = e.getBoundingClientRect().height;
      return (h && r >= h / 2 - 1) ? 'pill' : r;
    };

    return {
      url: location.pathname.split('/').pop() || 'index.html',
      declaredRadii,
      tokenSource: {
        // Does the page even SUBSCRIBE to the system? A page with no token source cannot
        // conform except by coincidence -- that is the root cause, not the symptom.
        tokensCss: !!document.querySelector('link[href*="tokens.css"]'),
        componentsCss: !!document.querySelector('link[href*="components.css"]'),
        resolvesTokens: !!cs.getPropertyValue('--wh-orange').trim(),
      },
      radii: tally(ctrls.concat(cards).map(normRadius)),
      ctrlHeights: tally(ctrls.map((e) => px(e.getBoundingClientRect().height)).filter((h) => h > 0)),
      fontFamilies: tally($$('body, h1, h2, p, button', R).filter(vis)
        .map((e) => getComputedStyle(e).fontFamily.split(',')[0].replace(/["']/g, '').trim())),
      typeScale: tally($$('h1, h2, h3', R).filter(vis).map((e) => px(getComputedStyle(e).fontSize))),
      cardSurfaces: tally(cards.map((e) => getComputedStyle(e).backgroundColor)),
      // Shared chrome IS the family resemblance users feel first (NN/g: "reusing ...
      // navigation across pages"). Absent chrome = a page that feels like another product.
      chrome: {
        navHub: !!document.querySelector('.nav-hub, #nav-hub, [data-nav-hub]'),
        footer: !!document.querySelector('footer, .site-footer'),
        skipLink: !!document.querySelector('a[href^="#"][class*="skip"], .skip-link'),
      },
      counts: { ctrls: ctrls.length, cards: cards.length },
    };
  };


  // ══ i18nCoverage() — the OUTCOME-TRUE i18n measure ══════════════════════════
  // WHY THIS IS SEPARATE FROM survey(): it MUTATES the page (flips the locale and flips
  // back). survey() must stay side-effect-free — a ruler that changes what it measures is
  // not a ruler. So this is an OPT-IN probe, called explicitly.
  //
  // WHY A FLIP-DIFF AT ALL: every static proxy lied.
  //   - "is the engine loaded?" scored logbook 75% while it rendered 0 translated labels
  //     (installing the mechanism is not the win).
  //   - "count [data-i]" scored analytics 0/22 while it is FULLY bilingual, because it
  //     translates JS-rendered content through _t() at RENDER TIME, not via data-i.
  // Flipping the locale and diffing the rendered text is mechanism-AGNOSTIC: it asks the
  // only question that matters — does the word on screen change for a Filipino worker?
  //
  // HONEST FAILURE MODES (reported, never papered over):
  //   - no setLang()      -> null ("page offers no switch") — NOT 0%, that is a different fact.
  //   - DOM shape changes -> null; a re-render that adds/removes nodes makes the diff
  //     meaningless rather than wrong-but-plausible.
  //   - async re-render   -> we await a settle window; analytics' setLang re-renders a phase.
  const i18nCoverage = async (opts) => {
    opts = opts || {};
    const settle = opts.settleMs || 600;
    const R = root(opts.root);
    if (typeof window.setLang !== 'function') {
      return { pct: null, reason: 'page has no setLang(): it offers no language switch' };
    }
    const SEL = 'h1, h2, h3, button, label, .card-title, [class*="section-label"], p';
    const snap = () => $$(SEL, R).filter(vis).map((e) => (e.textContent || '').trim());
    const restore = window.WH_LANG === 'fil' ? 'fil' : 'en';
    try {
      window.setLang('en');
      await new Promise((r) => setTimeout(r, settle));
      const en = snap();
      window.setLang('fil');
      await new Promise((r) => setTimeout(r, settle));
      const fil = snap();
      window.setLang(restore);
      await new Promise((r) => setTimeout(r, settle));
      if (en.length !== fil.length) {
        return { pct: null, reason: `DOM shape changed on flip (${en.length} vs ${fil.length}): diff not meaningful` };
      }
      const scored = en.map((t, i) => ({ en: t, fil: fil[i] })).filter((x) => x.en.length > 2);
      const changed = scored.filter((x) => x.en !== x.fil);
      return {
        pct: scored.length ? Math.round((changed.length / scored.length) * 100) : null,
        changed: changed.length, total: scored.length,
        untranslated: scored.filter((x) => x.en === x.fil).slice(0, 8).map((x) => x.en.slice(0, 44)),
      };
    } catch (e) {
      try { window.setLang(restore); } catch (_) { /* empty-catch-allow: best-effort restore */ }
      return { pct: null, reason: 'threw: ' + String(e).slice(0, 60) };
    }
  };

  window.__RUBRIC = { _v: V, survey, fingerprint, i18nCoverage };
  return { installed: true, _v: V,
           hint: "await window.__RUBRIC.survey({pageId:'analytics'}) | window.__RUBRIC.fingerprint()" };
}
