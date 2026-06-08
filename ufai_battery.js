/* ============================================================================
 * ufai_battery.js  —  The reusable Grounded-Sweep UFAI battery  (v1.4.0)
 * ============================================================================
 * ONE injectable that you paste into the Playwright MCP `browser_evaluate`
 * `function` arg. It installs `window.__UFAI` and runs a MEASURED battery
 * across FIVE pillars — Usability · Functionality · Adaptability ·
 * Internal-Control · CORRECTNESS — returning numbers (rect sizes, font px, axe
 * violations, CWV, parity deltas) so every finding is regression-testable.
 *
 * CORRECTNESS (pillar C, added v1.2.0) is the anti-blindness axis: U/F/A/I prove
 * a tile is readable/tappable/wired; C proves the NUMBER is RIGHT and the
 * CONTROL behaves. T0 invariants (garbage/range/loader) + T1 annotations
 * ([data-count-of]/[data-sum-of]) run config-free inside referee(); T2 behavior
 * (tabs change the panel, filters narrow) + T3 oracle parity (rendered == the
 * EXACT oracle field — same-named ≠ same-derivation) run via
 * __UFAI.correctness(spec) / run({parity,behavior,tabs,filters}).
 *
 * DOCTRINE (workflows/grounded_mcp_sweep.md + memory reference-ufai-enhanced):
 *   - REUSE the 1307-test L2 suite; do NOT reinvent. This battery ADDS ONLY
 *     the 5 things those specs lack, live, per page:
 *       1. axe-core WCAG 2.2 AA scan   (contrast / labels / ARIA / names /
 *          target-size / heading-order / image-alt — CDN-injected)
 *       2. Core Web Vitals             (LCP / INP / CLS — buffered perf entries
 *          + web-vitals lib; survives LATE injection via buffered:true)
 *       3. focus-visible (SC 2.4.11)   (Tab-walk: visible focus ring on every
 *          interactive element)
 *       4. link-destination / prod-path(live /workhive/ in src/srcset = a real
 *          prod 404; internal <a href> resolve 200)
 *       5. true-dpr mobile measure     (per-element computed rect ≥44, inputs
 *          ≥16px — closes validate_mobile's class-parse blind spot)
 *   - Everything else (role-permission, CRUD-DB-verified, concurrent-edit,
 *     visual-regression, smoke) = call the existing L2 gate, not this battery.
 *
 * TWO PASSES, ONE LENS:
 *   - REFEREE  → __UFAI.referee()  : measured, objective. A DEFECT is fixed
 *                INLINE by the agent (axe violation, 28px CTA, /workhive/ src,
 *                missing aria, dead onclick).
 *   - CRITIC   → __UFAI.critic()   : opinionated signals (CTA density, choice
 *                count, duplicate-affordance) that FEED the agent's harsh-critic
 *                judgment. Emits candidate records in the sweep_critiques schema.
 *                NEVER auto-applied — routed to sweep_critiques.json → you dispose.
 *
 * FLAG TAXONOMY (the bridge): DEFECT → fix inline · TASTE → queue · CONTENT
 *   (user's own data) → queue. One run sorts itself into "fix now" vs "you decide".
 *
 * MCP-SIDE INPUTS the battery cannot see from page JS (it lists them under
 * `result.mcp_todo` so the agent runs them): console-error HISTORY before boot,
 * network 4xx/5xx (browser_network_requests), the role×experience re-seed loop,
 * page-specific canonical parity (read via window.db from v_*_truth), and the
 * offline / slow-3G adaptability probes (route-abort).
 *
 * USAGE (per page):
 *   1. boot:  browser_evaluate(fn = <this whole file>)            // installs
 *   2. boot:  browser_evaluate("async()=>await window.__UFAI.boot()")  // CDN libs
 *   3. run :  browser_evaluate("async()=>await window.__UFAI.run({pageId:'index',role:'supervisor',experience:'experienced'})")
 *   …drive a few real interactions (click/fill) then re-read CWV for INP:
 *   4. browser_evaluate("()=>window.__UFAI.cwv()")
 *
 * COMPONENT BATTERY (① altitude, added v1.4.0): __UFAI.component('.simple-card')
 * walks every instance of a primitive on THIS page, reports its modal shape +
 * per-instance drift (missing required sub-part / minority shape). Call with no
 * arg to audit the default primitives. Cross-page consistency = the Python
 * spine tools/survey_component_consistency.py. See BATTERY_ARCHITECTURE.md.
 *
 * IA-STREAMLINING (Layer A, added v1.3.0): __UFAI.inventory({pageId}) emits a
 * structured INTERFACE INVENTORY (info-units + affordances, each semantically
 * fingerprinted) for the CROSS-PAGE redundancy surveyor. Dump per page to
 * .tmp/ia_inventory/<pageId>.json; tools/survey_ia_redundancy.py (Layer B)
 * aggregates "the same KPI/action lives on N pages" — the semantic redundancy
 * jscpd's textual clone scan is blind to. SURFACES only; never collapses UI.
 *
 * The file is a single arrow function so it can be passed verbatim as the
 * `function` argument. It is idempotent (re-paste = no-op if same version).
 * ==========================================================================*/
() => {
  const V = '1.6.1';
  if (window.__UFAI && window.__UFAI._v === V && window.__UFAI._installed) {
    return { already: true, _v: V };
  }

  // ── tunables (kept in lock-step with the static gate) ───────────────────
  const MIN_TAP = 44;            // validate_mobile.MIN_TOUCH_PX (gloved hand)
  const MIN_INPUT_PX = 16;       // iOS Safari auto-zoom floor
  const OVERFLOW_TOL = 2;        // px slack on horizontal overflow
  const FOCUS_SAMPLE = 40;       // cap the focus-visible tab-walk (perf)
  // Shell widgets this battery does NOT own — excluded from page-scoped checks.
  // (The companion + nav-hub are swept once as the shared shell, not per page.)
  const SHELL_SEL = '[id^="wh-ai"],[id^="wh-hub"],[class*="wh-ai-"],[class*="wh-hub-"],#wh-companion,nav-hub';
  const AXE_CDN = 'https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js';
  const WV_CDN  = 'https://unpkg.com/web-vitals@4?module';
  // 2026 Google CWV "good" thresholds.
  const CWV_GOOD = { LCP: 2500, INP: 200, CLS: 0.1 };

  const _state = {
    console: [],          // errors/warns captured AFTER boot (past ones = MCP)
    cwv: { LCP: null, INP: null, CLS: null },
    booted: false,
  };

  // ── small helpers ────────────────────────────────────────────────────────
  const isShell = (el) => !!(el.closest && el.closest(SHELL_SEL));
  const vis = (el) => {
    if (!el || !el.checkVisibility) {
      const r = el.getBoundingClientRect ? el.getBoundingClientRect() : { width: 0, height: 0 };
      const cs = getComputedStyle(el);
      return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0;
    }
    return el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true });
  };
  const sel = (el) => {
    if (!el) return '?';
    if (el.id) return '#' + el.id;
    const cls = (el.className && el.className.toString().trim().split(/\s+/).slice(0, 2).join('.')) || '';
    const txt = (el.textContent || '').trim().slice(0, 24).replace(/\s+/g, ' ');
    return el.tagName.toLowerCase() + (cls ? '.' + cls : '') + (txt ? `["${txt}"]` : '');
  };
  const round = (n, d = 1) => (n == null ? null : Math.round(n * 10 ** d) / 10 ** d);
  const loadScript = (src, asModule = false) => new Promise((res, rej) => {
    const s = document.createElement('script');
    if (asModule) s.type = 'module';
    s.src = src; s.onload = () => res(true); s.onerror = () => rej(new Error('load ' + src));
    document.head.appendChild(s);
  });

  // A DEFECT record (referee): the agent fixes these inline.
  const defect = (pillar, check, el, measured, expected, fixHint, severity = 'Major') => ({
    pillar, check, severity,
    selector: el ? sel(el) : null,
    measured, expected, fixHint,
  });

  // ════════════════════════════════════════════════════════════════════════
  // BOOT — load axe-core + web-vitals, start buffered CWV observers, hook
  // console. Idempotent. LATE injection note: LCP/CLS are recovered from
  // buffered PerformanceObserver entries that persist past load; INP needs a
  // real interaction (drive one, then call cwv()).
  // ════════════════════════════════════════════════════════════════════════
  async function boot() {
    if (_state.booted) return { axe: !!window.axe, webVitals: !!window.__wv, already: true };

    // console + uncaught-error hook (forward-looking; past errors come from MCP)
    const push = (level, args) => _state.console.push({ level, t: Date.now(), msg: args.map(String).join(' ').slice(0, 300) });
    ['error', 'warn'].forEach((lv) => {
      const orig = console[lv].bind(console);
      console[lv] = (...a) => { push(lv, a); orig(...a); };
    });
    window.addEventListener('error', (e) => push('uncaught', [e.message, e.filename + ':' + e.lineno]));
    window.addEventListener('unhandledrejection', (e) => push('promise', [String(e.reason)]));

    // buffered CWV via raw PerformanceObserver (works even injected late)
    try {
      new PerformanceObserver((l) => {
        const es = l.getEntries(); const last = es[es.length - 1];
        if (last) _state.cwv.LCP = round(last.renderTime || last.loadTime || last.startTime, 0);
      }).observe({ type: 'largest-contentful-paint', buffered: true });
    } catch (_) { /* empty-catch-allow: best-effort guard (test-only battery) */ }
    try {
      let cls = 0;
      new PerformanceObserver((l) => {
        for (const e of l.getEntries()) if (!e.hadRecentInput) cls += e.value;
        _state.cwv.CLS = round(cls, 3);
      }).observe({ type: 'layout-shift', buffered: true });
    } catch (_) { /* empty-catch-allow: best-effort guard (test-only battery) */ }
    try {
      const inter = {};
      new PerformanceObserver((l) => {
        for (const e of l.getEntries()) {
          if (e.interactionId) inter[e.interactionId] = Math.max(inter[e.interactionId] || 0, e.duration);
        }
        const vals = Object.values(inter);
        if (vals.length) _state.cwv.INP = round(Math.max(...vals), 0);
      }).observe({ type: 'event', buffered: true, durationThreshold: 16 });
    } catch (_) { /* empty-catch-allow: best-effort guard (test-only battery) */ }

    // CDN libs — best effort; the battery degrades gracefully if blocked.
    let axe = !!window.axe, wv = false;
    try { if (!axe) { await loadScript(AXE_CDN); axe = !!window.axe; } } catch (_) { /* empty-catch-allow: best-effort guard (test-only battery) */ }
    try {
      const m = await import(/* webpackIgnore:true */ WV_CDN);
      window.__wv = m;
      m.onLCP((x) => { _state.cwv.LCP = round(x.value, 0); }, { reportAllChanges: true });
      m.onCLS((x) => { _state.cwv.CLS = round(x.value, 3); }, { reportAllChanges: true });
      m.onINP((x) => { _state.cwv.INP = round(x.value, 0); }, { reportAllChanges: true });
      wv = true;
    } catch (_) { /* empty-catch-allow: best-effort guard (test-only battery) */ }

    _state.booted = true;
    return { axe, webVitals: wv };
  }

  // ════════════════════════════════════════════════════════════════════════
  // U — USABILITY
  // ════════════════════════════════════════════════════════════════════════
  async function usability() {
    const defects = []; const metrics = {};
    const dpr = window.devicePixelRatio || 1;
    metrics.viewport = { css: innerWidth, dpr, physical: round(innerWidth * dpr, 0) };

    // 1+5. axe-core WCAG 2.2 AA (contrast/labels/aria/names/target-size/heading/alt)
    let axe = { ran: false };
    if (window.axe) {
      try {
        const r = await window.axe.run(
          { exclude: [['[id^="wh-ai"]'], ['[id^="wh-hub"]'], ['#wh-companion']] },
          { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } }
        );
        axe = {
          ran: true, violations: r.violations.length,
          byImpact: r.violations.reduce((a, v) => ((a[v.impact || 'n/a'] = (a[v.impact || 'n/a'] || 0) + 1), a), {}),
        };
        for (const v of r.violations) {
          defects.push(defect('U', 'axe:' + v.id, null,
            `${v.nodes.length} node(s): ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`,
            'no WCAG 2.2 AA violation', v.help + ' — ' + v.helpUrl,
            v.impact === 'critical' || v.impact === 'serious' ? 'Major' : 'Minor'));
        }
      } catch (e) { axe = { ran: false, err: String(e) }; }
    }
    metrics.axe = axe;

    // 2+? tap targets ≥44 (per-element COMPUTED rect — closes class-parse blind spot)
    // EXCLUDE two genuine non-targets so the signal isn't drowned in noise:
    //  · sr-only / clip(1px) a11y labels (intentionally 1×1, not tappable)
    //  · pure display:inline <a> = a link inline in a sentence/block of text,
    //    which WCAG 2.5.8 (Target Size Minimum, AA) EXPRESSLY EXEMPTS. These are
    //    counted separately (inlineTextLinksUnder44_exempt) so they stay VISIBLE
    //    for the design critic without being reported as a conformance DEFECT.
    const srOnly = (el) => {
      const c = el.classList;
      if (c && (c.contains('sr-only') || c.contains('visually-hidden'))) return true;
      const r = el.getBoundingClientRect();
      return r.width <= 1 && r.height <= 1;
    };
    const inlineTextLink = (el) => el.tagName === 'A' && getComputedStyle(el).display === 'inline';
    // inert elements (e.g. an off-screen CTA hidden via [inert]) are intentionally
    // non-interactive in their current state → not a tap/focus target right now.
    const isInert = (el) => !!(el.inert || (el.closest && el.closest('[inert]')));
    // a DISABLED control (e.g. a stepper − at min, + at max) is not a current
    // tap/focus target — it can't be focused, so "no focus ring" on it is
    // expected, not a defect (was a false-positive source on stepper UIs).
    const isDisabled = (el) => el.disabled === true || el.getAttribute('aria-disabled') === 'true' || (el.matches && el.matches(':disabled'));
    // A <label> is only a TAP target when it toggles a checkbox/radio (the
    // hidden-radio "segmented button" pattern). A field text-label (for a
    // select / text input) is an accessible NAME — the CONTROL is the target,
    // not the label — so don't flag the 17px label as a sub-44 tap failure.
    const labelIsTapTarget = (el) => {
      if (el.tagName !== 'LABEL') return true;
      const c = el.querySelector('input[type=checkbox],input[type=radio]') || (el.htmlFor && document.getElementById(el.htmlFor));
      return !!(c && /^(checkbox|radio)$/.test(c.type || ''));
    };
    const clickSel = 'button,a[href],[onclick],[role="button"],[role="tab"],input[type="button"],input[type="submit"],input[type="checkbox"],input[type="radio"],summary,label[for],.chip,.pill,.btn,.btn-icon,.view-tab,.filter-chip,.shift-pill';
    const interactive = [...document.querySelectorAll(clickSel)].filter((el) => vis(el) && !isShell(el) && !srOnly(el) && !isInert(el) && !isDisabled(el));
    const tappable = interactive.filter((el) => !inlineTextLink(el) && labelIsTapTarget(el));
    const textLinks = interactive.filter(inlineTextLink);
    let tapFail = 0;
    for (const el of tappable) {
      const r = el.getBoundingClientRect();
      // a small control inside a ≥44 hit-row passes (parent hitbox). A
      // checkbox/radio inside a <label> is tapped via the label (WCAG 2.5.8),
      // so a ≥44px wrapping label counts as the hit target.
      const par = el.closest('li,tr,.row,[role="listitem"],label');
      const ph = par ? par.getBoundingClientRect().height : 0;
      if ((r.height < MIN_TAP - 0.5 || r.width < MIN_TAP - 0.5) && ph < MIN_TAP - 0.5) {
        tapFail++;
        if (tapFail <= 25) defects.push(defect('U', 'tap-target<44', el,
          `${round(r.width)}×${round(r.height)}px`, `≥${MIN_TAP}×${MIN_TAP}px`,
          'add min-height/min-width:44px (or a ≥44 row hitbox)', r.height < 30 ? 'Major' : 'Minor'));
      }
    }
    const textLinkUnder44 = textLinks.filter((el) => el.getBoundingClientRect().height < MIN_TAP - 0.5).length;
    metrics.tapTargets = { checked: tappable.length, under44: tapFail, inlineTextLinksUnder44_exempt: textLinkUnder44 };

    // 3. inputs ≥16px (iOS zoom)
    const inputs = [...document.querySelectorAll('input:not([type="hidden"]),textarea,select')].filter((el) => vis(el) && !isShell(el));
    let inpFail = 0;
    for (const el of inputs) {
      const fs = parseFloat(getComputedStyle(el).fontSize);
      if (fs < MIN_INPUT_PX - 0.1) {
        inpFail++;
        defects.push(defect('U', 'input-font<16', el, `${round(fs)}px`, `≥${MIN_INPUT_PX}px`,
          'bump font-size to ≥16px to stop iOS auto-zoom', 'Minor'));
      }
    }
    metrics.inputs = { checked: inputs.length, under16: inpFail };

    // 4. focus-visible (SC 2.4.11) — focus a sample, compare outline/shadow vs blurred.
    // Only check elements that are ACTUALLY focusable: natively-focusable tags or a
    // non-negative tabindex. A <label>/<div> isn't in the tab order, so "no focus
    // ring" on it is expected, not a defect (was a false-positive source).
    const isFocusable = (el) => {
      const ti = el.getAttribute('tabindex');
      if (ti !== null) return ti !== '-1';
      return el.matches('a[href],button,input:not([type="hidden"]),select,textarea,summary,[contenteditable="true"]');
    };
    const focusables = tappable.filter(isFocusable).slice(0, FOCUS_SAMPLE);
    // Deterministic backstop: programmatic .focus() does NOT reliably trigger
    // :focus-visible (Chromium's heuristic depends on prior KEYBOARD interaction,
    // so a sequential .focus() loop intermittently misses correct :focus-visible
    // rules). So ALSO precompute every selector that ships a focus RING via a
    // :focus / :focus-visible rule; an element matching one HAS an indicator.
    const focusRingSelectors = [];
    for (const ss of document.styleSheets) {
      let rules; try { rules = ss.cssRules; } catch (_) { continue; }
      for (const rule of rules) {
        const selText = rule.selectorText; if (!selText || !/:focus(-visible)?\b/.test(selText)) continue;
        const st = rule.style; if (!st) continue;
        const ring = (st.outlineStyle && st.outlineStyle !== 'none') || (parseFloat(st.outlineWidth) || 0) > 0
          || (st.boxShadow && st.boxShadow !== 'none') || (st.outline && st.outline.trim() && !/\bnone\b/.test(st.outline))
          || (st.border && st.border.trim() && !/\bnone\b/.test(st.border));
        if (!ring) continue;
        for (const part of selText.split(',')) {
          const bare = part.replace(/:focus-visible/g, '').replace(/:focus/g, '').trim();
          if (bare) focusRingSelectors.push(bare);
        }
      }
    }
    const hasFocusRule = (el) => focusRingSelectors.some((s) => { try { return el.matches(s); } catch (_) { return false; } });
    let noFocusRing = 0; const active = document.activeElement;
    for (const el of focusables) {
      try {
        const before = getComputedStyle(el);
        const b = { o: before.outlineStyle, ow: parseFloat(before.outlineWidth) || 0, bs: before.boxShadow };
        el.focus({ preventScroll: true });
        const af = getComputedStyle(el);
        const ringByOutline = af.outlineStyle !== 'none' && (parseFloat(af.outlineWidth) || 0) >= 1.5;
        const ringByShadow = af.boxShadow && af.boxShadow !== 'none' && af.boxShadow !== b.bs;
        const ringByOutlineChange = af.outlineStyle !== b.o || (parseFloat(af.outlineWidth) || 0) > b.ow;
        if (!(ringByOutline || ringByShadow || ringByOutlineChange) && !hasFocusRule(el)) {
          noFocusRing++;
          if (noFocusRing <= 12) defects.push(defect('U', 'focus-not-visible', el,
            `outline:${af.outlineStyle} ${af.outlineWidth}`, 'visible focus ring ≥2px on Tab (SC 2.4.11)',
            'add :focus-visible{outline:2px solid …;outline-offset:2px}', 'Minor'));
        }
      } catch (_) { /* empty-catch-allow: best-effort guard (test-only battery) */ }
    }
    if (active && active.focus) try { active.focus({ preventScroll: true }); } catch (_) { /* empty-catch-allow: best-effort guard (test-only battery) */ }
    metrics.focusVisible = { checked: focusables.length, missing: noFocusRing };

    // horizontal overflow at current viewport (true-dpr if MCP set physical width)
    const overflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
    metrics.horizOverflow = round(overflow, 0);
    if (overflow > OVERFLOW_TOL) defects.push(defect('U', 'horiz-overflow', document.documentElement,
      `${round(overflow)}px past viewport`, '0 (no horizontal scroll @390)',
      'find the overflowing child (often a fixed-width row or long token)', 'Minor'));

    // CLS (visual stability) read from buffered observer
    if (_state.cwv.CLS != null && _state.cwv.CLS > CWV_GOOD.CLS) {
      defects.push(defect('U', 'CLS>0.1', null, _state.cwv.CLS, `≤${CWV_GOOD.CLS}`,
        'reserve space for late content (img dims / skeleton) to stop layout jump', 'Minor'));
    }
    metrics.cls = _state.cwv.CLS;

    return { defects, metrics };
  }

  // ════════════════════════════════════════════════════════════════════════
  // F — FUNCTIONALITY
  // ════════════════════════════════════════════════════════════════════════
  async function functionality() {
    const defects = []; const metrics = {};

    // F0 (static half) — wired & alive: every inline onclick → a defined fn;
    // dead href flagged. The LIVE click-and-assert half is MCP-driven.
    const clickables = [...document.querySelectorAll('button,a,[onclick],[role="button"],summary,input[type="button"],input[type="submit"]')].filter((el) => vis(el) && !isShell(el));
    let deadFn = 0, deadHref = 0;
    for (const el of clickables) {
      const oc = el.getAttribute('onclick');
      if (oc) {
        for (const m of oc.matchAll(/([A-Za-z_$][\w$]*)\s*\(/g)) {
          const fn = m[1];
          // skip METHOD calls (obj.fn(), e.g. history.back(), console.log(), this.x()) —
          // those resolve on an object, not as a global window.fn (was a false positive).
          if (m.index > 0 && oc[m.index - 1] === '.') continue;
          if (['if', 'for', 'while', 'return', 'function', 'switch', 'catch', 'typeof', 'new', 'void', 'event'].includes(fn)) continue;
          if (typeof window[fn] !== 'function') {
            deadFn++;
            defects.push(defect('F', 'onclick→undefined-fn', el, `onclick="${oc.slice(0, 40)}" → window.${fn} is ${typeof window[fn]}`,
              'inline onclick must call a defined global fn', `define window.${fn} or fix the handler name`, 'Major'));
            break;
          }
        }
      }
      const href = el.getAttribute && el.getAttribute('href');
      if (el.tagName === 'A' && !oc && (href === '#' || href === '' || /^javascript:\s*void/.test(href || ''))) {
        deadHref++;
        if (deadHref <= 12) defects.push(defect('F', 'dead-href', el, `href="${href}"`, 'a real destination or an onclick',
          'point the link at a page, or convert to a <button>', 'Minor'));
      }
    }
    metrics.wiring = { clickables: clickables.length, deadFn, deadHref };

    // link-destination / PROD-PATH — live /workhive/ inside src/srcset = real
    // prod 404 (the dev bridge rewrites <a href> only, never src). Matches
    // validate_prod_path_leak.py's class, observed in the LIVE DOM.
    let prodSrc = 0;
    for (const el of document.querySelectorAll('[src],[srcset]')) {
      const v = (el.getAttribute('src') || '') + ' ' + (el.getAttribute('srcset') || '');
      if (v.includes('/workhive/')) {
        prodSrc++;
        defects.push(defect('F', 'prod-path-in-src', el, v.trim().slice(0, 60), 'root-relative asset path (no /workhive/)',
          'commit src as "/..." (bridge only rewrites <a href>, not src) → 404s in prod', 'Major'));
      }
    }
    metrics.prodPathSrc = prodSrc;

    // internal <a href> destination resolves 200 (un-bridge /workhive/ first)
    const origin = location.origin;
    const hrefs = new Set();
    for (const a of document.querySelectorAll('a[href]')) {
      if (isShell(a)) continue;
      let h = a.getAttribute('href') || '';
      if (!h || h.startsWith('#') || /^(mailto:|tel:|javascript:|https?:\/\/(?!127\.0\.0\.1|localhost))/.test(h)) continue;
      hrefs.add(h);
    }
    const broken = [];
    await Promise.all([...hrefs].slice(0, 40).map(async (h) => {
      try {
        const url = new URL(h, location.href);
        // use the page's bounded fetch so a hung server can't strand the link sweep
        const _f = (typeof window.fetchWithTimeout === 'function') ? window.fetchWithTimeout : ((u, o) => fetch(u, o));
        const r = await _f(url.href, { method: 'HEAD' }, 5000);
        if (r && r.status >= 400) broken.push({ href: h, status: r.status });
      } catch (e) { broken.push({ href: h, status: 'fetch-err' }); }
    }));
    for (const b of broken) defects.push(defect('F', 'broken-internal-link', null, `${b.href} → ${b.status}`, '200', 'fix or remove the dead internal link', 'Major'));
    metrics.links = { checked: Math.min(hrefs.size, 40), broken: broken.length };

    // console errors captured since boot (past = MCP browser_console_messages)
    const errs = _state.console.filter((c) => c.level === 'error' || c.level === 'uncaught' || c.level === 'promise');
    metrics.consoleErrorsSinceBoot = errs.length;
    if (errs.length) defects.push(defect('F', 'console-error', null, errs.slice(0, 3).map((e) => e.msg).join(' || '), '0 console errors', 'fix the throwing code path', 'Major'));

    return { defects, metrics };
  }

  // ════════════════════════════════════════════════════════════════════════
  // A — ADAPTABILITY  (CWV + multi-breakpoint; offline/throttle are MCP-driven)
  // ════════════════════════════════════════════════════════════════════════
  async function adaptability() {
    const defects = []; const metrics = {};
    const c = cwv();
    metrics.cwv = c;
    if (c.LCP != null && c.LCP > CWV_GOOD.LCP) defects.push(defect('A', 'LCP>2.5s', null, `${c.LCP}ms`, `≤${CWV_GOOD.LCP}ms`, 'optimize the largest paint (hero img/text); preconnect; defer non-critical JS', 'Minor'));
    if (c.INP != null && c.INP > CWV_GOOD.INP) defects.push(defect('A', 'INP>200ms', null, `${c.INP}ms`, `≤${CWV_GOOD.INP}ms`, 'break up long tasks on the main thread; yield after input', 'Minor'));
    // CLS already reported under U; mirror the metric here for the pillar score.
    metrics.cls = c.CLS;
    if (c.CLS != null && c.CLS > CWV_GOOD.CLS) defects.push(defect('A', 'CLS>0.1', null, c.CLS, `≤${CWV_GOOD.CLS}`, 'reserve space for late content', 'Minor'));

    metrics.reducedMotionHonored = matchMedia('(prefers-reduced-motion: reduce)').matches ? 'OS-on' : 'OS-off';
    metrics.note = 'offline / slow-3G / route-abort + 768/1280 breakpoints are MCP-driven (see mcp_todo)';
    return { defects, metrics };
  }

  // ════════════════════════════════════════════════════════════════════════
  // I — INTERNAL CONTROL  (token exposure + undo/confirm + source chips;
  // role×experience matrix + cross-hive IDOR are MCP-driven re-seed loops)
  // ════════════════════════════════════════════════════════════════════════
  async function internalControl() {
    const defects = []; const metrics = {};

    // secret/token exposure — JWT/sk-/private-key shapes in DOM text or storage.
    // The Supabase ANON key is PUBLIC by design → not a leak; flag other shapes.
    const secretRe = /\b(sk-[A-Za-z0-9]{20,}|sk_live_[A-Za-z0-9]{10,}|AIza[0-9A-Za-z\-_]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|service_role)\b/;
    const exposures = [];
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i); const val = localStorage.getItem(k) || '';
        if (secretRe.test(val)) exposures.push({ where: 'localStorage:' + k, hit: val.match(secretRe)[0].slice(0, 12) + '…' });
      }
    } catch (_) { /* empty-catch-allow: best-effort guard (test-only battery) */ }
    const bodyTxt = document.body ? document.body.innerHTML : '';
    const m = bodyTxt.match(secretRe);
    if (m) exposures.push({ where: 'DOM', hit: m[0].slice(0, 12) + '…' });
    for (const ex of exposures) defects.push(defect('I', 'secret-exposed', null, ex.where + ' → ' + ex.hit, 'no secret/service_role key in DOM or storage', 'move secrets server-side; never ship service_role to the browser', 'Major'));
    metrics.secretExposures = exposures.length;

    // destructive controls that should carry undo/confirm (heuristic surface signal)
    const destructiveRe = /\b(delete|remove|clear|reset|discard|wipe|sign\s?out|log\s?out)\b/i;
    const destructive = [...document.querySelectorAll('button,[role="button"],a')]
      .filter((el) => vis(el) && !isShell(el) && destructiveRe.test((el.textContent || '') + ' ' + (el.getAttribute('aria-label') || '')));
    metrics.destructiveControls = destructive.length;

    // provenance / source chips present where KPIs render (signal, not a gate)
    metrics.sourceChips = document.querySelectorAll('[data-source],.source-chip,[class*="source-chip"],[data-canonical]').length;

    // identity snapshot (for the role×experience loop the MCP harness runs)
    metrics.identity = window.WHShell ? {
      mode: window.WHShell.mode(), role: window.WHShell.role(), hiveId: window.WHShell.hiveId() ? '(set)' : '(none)',
    } : { note: 'no window.WHShell seam' };
    metrics.note = 'role×experience matrix + cross-hive IDOR + owner-only deny are MCP-driven (re-seed wh_hive_role, re-run); see mcp_todo';

    return { defects, metrics };
  }

  // ════════════════════════════════════════════════════════════════════════
  // C — CORRECTNESS  (the anti-blindness pillar: is the DISPLAY right + do the
  // FUNCTIONS behave?). U/F/A/I prove a tile is READABLE / TAPPABLE / WIRED;
  // none prove the NUMBER is RIGHT or that a control DOES what it claims. This
  // pillar closes that gap so the MCP critic is no longer blind to WHAT.
  // Four tiers, increasing grounding:
  //   T0 invariants  (config-free) : garbage values (NaN/undefined/[object Object]/
  //        null-with-unit), %-out-of-range, stuck loader. Always run (in referee).
  //   T1 annotations (page opt-in) : [data-count-of="sel"] number == rows matched;
  //        [data-sum-of="rowSel"][data-sum-col=i] total == Σ rows (tol). Always run.
  //   T2 behavior    (semi-auto)   : every tab must CHANGE the panel (a dead tab is
  //        a defect); a declared filter must not INCREASE its row count. MUTATES →
  //        only via __UFAI.correctness({behavior:true|tabs|filters}).
  //   T3 parity      (oracle)      : the agent supplies {dom→value(s)} + the EXACT
  //        {oracle field} — the battery does the keyed compare. LESSON (analytics
  //        RC-001): a same-NAMED field is NOT the same DERIVATION (OEE availability
  //        96.1% ≠ reliability availability 99.2%). A mismatch is flagged
  //        VERIFY-MAPPING, carrying BOTH values, for the agent to adjudicate
  //        wrong-field vs wrong-value BEFORE calling it a render bug (qa-tester:
  //        "the dominant failure mode was field-name mismatch — verify the mapping").
  // ════════════════════════════════════════════════════════════════════════

  // a value-bearing LEAF (a stat/badge/cell), not a sentence of prose — so
  // "null hypothesis" in a paragraph never trips the garbage scan.
  const isValueLeaf = (el) => {
    if (!el || !el.children) return false;
    const t = (el.textContent || '').trim();
    if (!t || t.length > 48) return false;
    for (const c of el.children) if ((c.textContent || '').trim().length > 0) return false;
    return true;
  };
  const VALUE_TAGS = 'span,b,strong,em,dd,dt,td,th,p,h1,h2,h3,h4,h5,h6,li,small,code,output,.stat,.kpi,.value,.metric,.tile';
  // garbage: [object X], bare NaN/undefined/Infinity as a value, $NaN, NaN%, or
  // "null" immediately followed by a unit (null days / null% = a failed calc).
  const GARBAGE_RE = /\[object [A-Za-z]+\]|(?:^|[\s:>(])(?:NaN|undefined|Infinity|-Infinity)(?=[\s%<).,]|$)|\$\s*NaN|NaN\s*%|\bnull\s*(?:%|days?|hrs?|hours?|min|mins?)\b/;
  const PURE_PCT_RE = /^-?\d+(?:\.\d+)?\s*%$/;
  const _num = (s) => { const m = String(s).replace(/[, ]/g, '').match(/-?\d+(?:\.\d+)?/); return m ? parseFloat(m[0]) : null; };

  // T0 + T1 — config-free + annotation-driven. Pure read, safe in referee().
  function correctnessInvariants() {
    const defects = []; const metrics = {};
    const leaves = [...document.querySelectorAll(VALUE_TAGS)]
      .filter((el) => vis(el) && !isShell(el) && isValueLeaf(el)
        && !el.matches('input,textarea,select,[contenteditable="true"]'));

    // T0.1 garbage values
    let garbage = 0;
    for (const el of leaves) {
      const t = (el.textContent || '').trim();
      if (GARBAGE_RE.test(t)) {
        garbage++;
        if (garbage <= 15) defects.push(defect('C', 'garbage-value', el, t.slice(0, 40),
          'a real value (no NaN/undefined/[object Object]/null-unit)',
          'guard the calc (|| 0 on optional numerics — NaN cascades to null) or fix the render mapping', 'Major'));
      }
    }
    metrics.garbageValues = garbage;

    // T0.2 out-of-range % (pure-value tiles only → prose "120% of target" is skipped)
    let pctBad = 0;
    for (const el of leaves) {
      const t = (el.textContent || '').trim();
      if (!PURE_PCT_RE.test(t)) continue;
      const v = parseFloat(t);
      if (v < 0 || v > 100) {
        pctBad++;
        defects.push(defect('C', 'percent-out-of-range', el, t, '0–100%',
          'a rate <0% or >100% usually means a wrong denominator or a count miscast as a %', v < 0 ? 'Major' : 'Minor'));
      }
    }
    metrics.percentOutOfRange = pctBad;

    // T0.3 stuck loader (battery runs post-load → a visible spinner = unresolved fetch)
    const spinners = [...document.querySelectorAll('.spinner,[class*="spinner"],[class*="skeleton"],[aria-busy="true"]')]
      .filter((el) => vis(el) && !isShell(el));
    metrics.visibleLoaders = spinners.length;
    if (spinners.length) defects.push(defect('C', 'stuck-loader', spinners[0], spinners.length + ' visible loader(s)',
      '0 (content resolved)', 'a spinner/skeleton still on screen after load = a fetch that never resolved or a missing hide', 'Minor'));

    // T1.1 [data-count-of="sel"] : rendered integer == rows matched by sel
    let countMiss = 0, countChecked = 0;
    for (const el of document.querySelectorAll('[data-count-of]')) {
      if (!vis(el) || isShell(el)) continue;
      const want = el.getAttribute('data-count-of');
      const scope = el.getAttribute('data-count-scope');
      const root = scope ? (document.querySelector(scope) || document) : document;
      let n; try { n = root.querySelectorAll(want).length; } catch (_) { continue; }
      const shown = parseInt(((el.textContent || '').match(/-?\d[\d,]*/) || ['x'])[0].replace(/,/g, ''), 10);
      countChecked++;
      if (!Number.isNaN(shown) && shown !== n) {
        countMiss++;
        defects.push(defect('C', 'count!=rows', el, `shows ${shown}, "${want}" matches ${n}`,
          'the count badge equals the rows it summarizes',
          'the count drifted from the list it labels (filter/derivation mismatch — cf. dayplanner overdue 6 vs 3)', 'Major'));
      }
    }
    metrics.countAttrs = { checked: countChecked, mismatched: countMiss };

    // T1.2 [data-sum-of="rowSel"][data-sum-col=i?] : total == Σ rows (tol)
    let sumMiss = 0, sumChecked = 0;
    for (const el of document.querySelectorAll('[data-sum-of]')) {
      if (!vis(el) || isShell(el)) continue;
      const rowSel = el.getAttribute('data-sum-of');
      const col = el.hasAttribute('data-sum-col') ? parseInt(el.getAttribute('data-sum-col'), 10) : null;
      const tol = el.hasAttribute('data-sum-tol') ? parseFloat(el.getAttribute('data-sum-tol')) : 0.5;
      let rows; try { rows = [...document.querySelectorAll(rowSel)]; } catch (_) { continue; }
      let sum = 0;
      for (const r of rows) {
        const cell = col != null ? r.querySelectorAll('td,th,[data-cell]')[col] : r;
        const v = _num(cell ? cell.textContent : r.textContent); if (v != null) sum += v;
      }
      const shown = _num(el.textContent);
      sumChecked++;
      if (shown != null && Math.abs(shown - sum) > tol) {
        sumMiss++;
        defects.push(defect('C', 'total!=sum-of-rows', el, `shows ${round(shown, 2)}, Σrows=${round(sum, 2)}`,
          'the headline total equals the sum of its rows',
          'a total that disagrees with its own rows = a roll-up bug (double-count / filtered rows / stale cache)', 'Major'));
      }
    }
    metrics.sumAttrs = { checked: sumChecked, mismatched: sumMiss };

    return { defects, metrics };
  }

  // T2 BEHAVIOR — functions must DO what they say. MUTATES page state → NOT in
  // referee(); call __UFAI.correctness({behavior:true|tabs|filters}). Auto-
  // discovers tabs; a tab that doesn't change the panel content is a dead tab.
  async function correctnessBehavior(spec = {}) {
    const defects = []; const metrics = {};
    const wait = spec.wait || 1200;
    const panel = document.querySelector(spec.panel || '#results-panel,[role="main"],main,#app') || document.body;
    const sig = () => { const t = (panel.innerText || '').replace(/\s+/g, ' ').trim(); return t.length + '|' + t.slice(0, 90) + '|' + t.slice(-90); };

    const tabEls = (spec.tabs ? [...document.querySelectorAll(spec.tabs)]
      : enumerateStates().tabs.map((t) => (t.sel.startsWith('#') ? document.querySelector(t.sel) : null)
        || [...document.querySelectorAll('[role="tab"],.phase-tab,.view-tab,.tab-btn')].find((e) => (e.textContent || '').trim().slice(0, 28) === t.label)))
      .filter((el) => el && vis(el) && !isShell(el));
    let deadTabs = 0;
    const original = document.querySelector('[role="tab"][aria-selected="true"],.phase-tab.active,.view-tab.active,.tab-btn.active');
    for (const tab of tabEls) {
      if (tab.matches('.active,[aria-selected="true"]')) continue;
      const before = sig();
      try { tab.click(); } catch (_) { continue; }
      await new Promise((r) => setTimeout(r, wait));
      const after = sig();
      if (after === before) {
        deadTabs++;
        defects.push(defect('C', 'dead-tab', tab, 'panel unchanged after click', 'tab swaps the panel content',
          'a tab that does not change the content region is wired wrong (or renders identical data) — verify the handler', 'Major'));
      } else if ((panel.innerText || '').trim().length < 5) {
        defects.push(defect('C', 'tab-empty-panel', tab, 'panel empty after click', 'tab shows its content',
          'the tab cleared the panel and rendered nothing — a fetch/render failure on that tab', 'Major'));
      }
    }
    if (original) { try { original.click(); await new Promise((r) => setTimeout(r, wait)); } catch (_) { /* empty-catch-allow */ } }
    metrics.tabs = { checked: tabEls.length, dead: deadTabs };

    if (spec.filters) {
      let filterBad = 0;
      for (const f of spec.filters) {
        const rows = () => { try { return document.querySelectorAll(f.rows).length; } catch (_) { return null; } };
        const before = rows();
        const trig = typeof f.apply === 'string' ? document.querySelector(f.apply) : null;
        if (!trig) continue;
        try { trig.click(); } catch (_) { continue; }
        await new Promise((r) => setTimeout(r, wait));
        const after = rows();
        if (before != null && after != null && after > before) {
          filterBad++;
          defects.push(defect('C', 'filter-increases-rows', trig, `${before} → ${after} rows`, 'a filter narrows (≤) the set',
            'applying a filter GREW the row count — the predicate is inverted or not applied', 'Major'));
        }
      }
      metrics.filters = { checked: spec.filters.length, increased: filterBad };
    }
    return { defects, metrics };
  }

  // T3 PARITY — rendered value == the EXACT oracle derivation. The agent supplies
  // the mapping (the battery cannot guess which of several same-named fields a
  // renderer reads). spec.parity = [{ name, dom, oracle, tol? }] where dom/oracle
  // are each a scalar OR an array of {key,value} / object map.
  function correctnessParity(spec = {}) {
    const defects = []; const metrics = { checks: [] };
    const toMap = (x) => {
      if (Array.isArray(x)) { const m = {}; x.forEach((e) => { m[e.key ?? e.k ?? e.asset ?? e.machine ?? e.name] = (e.value ?? e.v ?? e.val); }); return m; }
      return x;
    };
    const eq = (a, b, tol) => (typeof a === 'number' || typeof b === 'number')
      ? Math.abs(Number(a) - Number(b)) <= tol : String(a).trim() === String(b).trim();
    for (const p of (spec.parity || [])) {
      const tol = p.tol == null ? 0.1 : p.tol;
      if (p.dom && typeof p.dom === 'object') {
        const d = toMap(p.dom), o = toMap(p.oracle) || {};
        let matched = 0; const mism = [];
        for (const k of Object.keys(d)) {
          if (o[k] == null) { mism.push({ key: k, dom: d[k], oracle: '(absent in oracle)' }); continue; }
          if (eq(d[k], o[k], tol)) matched++; else mism.push({ key: k, dom: d[k], oracle: o[k] });
        }
        metrics.checks.push({ name: p.name, total: Object.keys(d).length, matched, mismatched: mism.length });
        if (mism.length) defects.push(defect('C', 'parity:' + (p.name || '?'), null,
          `${mism.length}/${Object.keys(d).length} differ e.g. ${JSON.stringify(mism.slice(0, 3))}`,
          'rendered == oracle for every key',
          'VERIFY-MAPPING FIRST: a same-NAMED oracle field is not the same DERIVATION (analytics RC-001 OEE-availability 96.1% ≠ reliability-availability 99.2%). Confirm the renderer reads THIS field BEFORE concluding a render bug; then it is a real WHAT defect.', 'Major'));
      } else {
        const ok = eq(p.dom, p.oracle, tol);
        metrics.checks.push({ name: p.name, scalar: true, dom: p.dom, oracle: p.oracle, ok });
        if (!ok) defects.push(defect('C', 'parity:' + (p.name || '?'), null, `dom=${p.dom} oracle=${p.oracle}`,
          'rendered == oracle', 'VERIFY-MAPPING FIRST (same-named ≠ same-derivation); then a real WHAT defect.', 'Major'));
      }
    }
    return { defects, metrics };
  }

  // Public: full correctness pass. Invariants always run (config-free + T1).
  // Behavior (mutating) + parity (oracle) run only when their inputs are given.
  async function correctness(spec = {}) {
    const inv = correctnessInvariants();
    const par = correctnessParity(spec);
    const beh = (spec.behavior || spec.tabs || spec.filters) ? await correctnessBehavior(spec) : { defects: [], metrics: { skipped: 'pass behavior:true | tabs | filters to run interaction checks' } };
    const defects = [...inv.defects, ...par.defects, ...beh.defects];
    return {
      defects,
      metrics: { invariants: inv.metrics, parity: par.metrics, behavior: beh.metrics },
      major: defects.filter((d) => d.severity === 'Major' || d.severity === 'Blocker').length,
    };
  }

  // ── CWV snapshot (call again after driving an interaction for INP) ────────
  function cwv() {
    // top up from buffered entries each call
    try {
      const lcp = performance.getEntriesByType('largest-contentful-paint').slice(-1)[0];
      if (lcp) _state.cwv.LCP = round(lcp.renderTime || lcp.loadTime || lcp.startTime, 0);
    } catch (_) { /* empty-catch-allow: best-effort guard (test-only battery) */ }
    const r = { ...(_state.cwv) };
    r.ratings = {
      LCP: r.LCP == null ? 'n/a' : r.LCP <= CWV_GOOD.LCP ? 'good' : r.LCP <= 4000 ? 'needs-improvement' : 'poor',
      INP: r.INP == null ? 'n/a' : r.INP <= CWV_GOOD.INP ? 'good' : r.INP <= 500 ? 'needs-improvement' : 'poor',
      CLS: r.CLS == null ? 'n/a' : r.CLS <= CWV_GOOD.CLS ? 'good' : r.CLS <= 0.25 ? 'needs-improvement' : 'poor',
    };
    return r;
  }

  // ════════════════════════════════════════════════════════════════════════
  // INVENTORY (Layer A of the IA-streamlining surveyor) — emit a structured
  // INTERFACE INVENTORY for THIS page: the info-units it shows + the
  // affordances it offers, each with a normalized SEMANTIC fingerprint so the
  // cross-page aggregator (tools/survey_ia_redundancy.py, Layer B) can find
  // "the same KPI/action lives on N pages" redundancy that jscpd (TEXTUAL code
  // clones) is structurally blind to. Method = Brad Frost Interface Inventory +
  // NN/g content-audit unit harvest. Pure READ (safe in any rendered state).
  // DOCTRINE: this SURFACES redundancy only — it never collapses UI. Dump the
  // result to .tmp/ia_inventory/<pageId>.json; the Python aggregator merges the
  // live values/CTAs this harvester sees but a static HTML parse cannot.
  // ════════════════════════════════════════════════════════════════════════
  // normKey: a semantic comparison key — lowercase, strip punctuation/parenthetical
  // qualifiers, collapse whitespace. So "Pending approval" == "pending approval"
  // and "OEE (avg, partial)" keys on "oee avg partial" → cross-page dedup is by
  // MEANING, not by exact markup (the whole point vs. textual clone detection).
  function _normKey(s) {
    return String(s == null ? '' : s).toLowerCase()
      .replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
  }
  function inventory({ pageId = 'page' } = {}) {
    const norm = (s) => String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
    // the value a tile renders (its first value-leaf) — enriches the fingerprint
    // with the LIVE source a static parse can't see (e.g. "3 overdue" vs "—").
    const valueOf = (el) => {
      const v = el.querySelector('.sc-hero,.stat-value,.kpi-value,[data-value],output,.value,.metric-value,.hero-num');
      return v ? norm(v.textContent).slice(0, 40) : null;
    };

    // ── info units ─────────────────────────────────────────────────────────
    const infoUnits = [];
    // (a) explicitly tagged tiles = the canonical info-unit registry
    for (const el of document.querySelectorAll('[data-rag-tile]')) {
      if (isShell(el)) continue;
      const unitId = el.getAttribute('data-rag-tile') || '';
      const label = norm(el.getAttribute('data-rag-label') || '');
      const keySuffix = unitId.includes(':') ? unitId.split(':').slice(1).join(':') : unitId;
      infoUnits.push({
        kind: 'rag-tile', unitId, keySuffix, label, value: valueOf(el),
        labelKey: _normKey(label), keyKey: _normKey(keySuffix.replace(/_/g, ' ')),
        fingerprint: _normKey(label) || _normKey(keySuffix.replace(/_/g, ' ')),
      });
    }
    // (b) KPI tiles NOT rag-tagged — untagged dashboard stats the static parse
    // would miss (label = the .sc-label / .stat-label child). Skip any already
    // inside a tagged tile so we never double-count.
    for (const card of document.querySelectorAll('.simple-card,.sum-card,.stat-card,.kpi-card')) {
      if (isShell(card) || card.hasAttribute('data-rag-tile') || card.closest('[data-rag-tile]')) continue;
      const lab = card.querySelector('.sc-label,.stat-label,.kpi-label,.card-label');
      const label = lab ? norm(lab.textContent) : '';
      if (!label) continue;
      infoUnits.push({
        kind: 'kpi-untagged', unitId: pageId + ':(untagged)', keySuffix: null,
        label, value: valueOf(card), labelKey: _normKey(label), keyKey: null,
        fingerprint: _normKey(label),
      });
    }

    // ── affordances (CTAs) ───────────────────────────────────────────────────
    // page-body actions only: the shared nav-hub + companion are global BY
    // DESIGN (excluded via isShell), so what remains is page-authored. dest =
    // the page an <a> targets, or the handler fn an onclick invokes (the "what
    // it does") → cross-page "same action reachable from N places" (Hick's law).
    const affordances = []; const seenAff = new Set();
    for (const el of document.querySelectorAll('button,a[href],[role="button"],[onclick]')) {
      if (isShell(el) || !vis(el)) continue;
      const label = norm(el.getAttribute('aria-label') || el.textContent).slice(0, 40);
      if (!label) continue;
      let dest = null, destKind = null;
      const href = el.getAttribute('href');
      if (href && /\.html\b/.test(href)) { dest = href.split(/[?#]/)[0].replace(/^.*\//, ''); destKind = 'page'; }
      else {
        const m = (el.getAttribute('onclick') || '').match(/([A-Za-z_$][\w$]*)\s*\(/);
        if (m && m.index !== undefined) dest = m[1] + '()', destKind = 'fn';
      }
      const fp = _normKey(label) + '∷' + (dest || '');
      if (seenAff.has(fp)) continue; seenAff.add(fp);
      affordances.push({ kind: 'cta', label, dest, destKind, labelKey: _normKey(label), fingerprint: fp });
    }

    return {
      pageId, url: location.href, ts: new Date().toISOString(),
      counts: { infoUnits: infoUnits.length, affordances: affordances.length },
      infoUnits, affordances,
      note: 'Layer A interface inventory (UFAI v' + V + '). Dump to .tmp/ia_inventory/' + pageId + '.json; tools/survey_ia_redundancy.py (Layer B) aggregates cross-page. SURFACE-only — never auto-collapses UI.',
    };
  }

  // ════════════════════════════════════════════════════════════════════════
  // COMPONENT (① the altitude BELOW the page) — the DOM-accurate confirm for the
  // component battery. The page battery sees ONE page; tools/survey_component_
  // consistency.py sees the class-level shape cross-page (static, windowed). This
  // walks the REAL DOM children of every instance of a primitive ON THIS PAGE and
  // reports its shape (which sub-parts present), per-instance tap size + a11y
  // name, the MODAL shape, and any minority/missing-required drift. Pure READ.
  // Default (no selector) audits the known design-system primitives.
  // ════════════════════════════════════════════════════════════════════════
  const PRIMITIVE_DEFAULTS = {
    '.simple-card': ['sc-label', 'sc-hero'],   // required sub-parts (sc-sub/sc-tag optional)
    '.sum-card': ['sn', 'sl'],
  };
  function component(selector, opts = {}) {
    // batch mode: audit every default primitive, return a map
    if (!selector) {
      const out = {};
      for (const [s, req] of Object.entries(PRIMITIVE_DEFAULTS)) out[s] = component(s, { required: req });
      return { _v: V, primitives: out, note: 'live DOM component audit — modal shape + drift per primitive on THIS page' };
    }
    const required = opts.required || PRIMITIVE_DEFAULTS[selector] || [];
    let nodes;
    try { nodes = [...document.querySelectorAll(selector)]; } catch (_) { return { selector, error: 'bad selector' }; }
    nodes = nodes.filter((el) => !isShell(el) && vis(el));
    const defects = [];
    const shapeCount = {};
    const instances = nodes.map((el, i) => {
      // shape = the recognized sub-part classes present among DOM descendants
      const childClasses = new Set();
      el.querySelectorAll('[class]').forEach((c) => c.classList.forEach((k) => childClasses.add(k)));
      const shapeArr = [...childClasses].filter((k) => /^(sc-|sum-|sn$|sl$)/.test(k) || k === 'sn' || k === 'sl').sort();
      const shapeKey = shapeArr.join('+');
      shapeCount[shapeKey] = (shapeCount[shapeKey] || 0) + 1;
      const missing = required.filter((rq) => !childClasses.has(rq));
      const r = el.getBoundingClientRect();
      const name = (el.getAttribute('aria-label') || el.textContent || '').trim();
      if (missing.length) defects.push(defect('C', 'component-missing-part', el,
        `shape [${shapeArr.join(', ')}] missing required ${missing.map((x) => '.' + x).join(', ')}`,
        `every ${selector} has ${required.map((x) => '.' + x).join(', ')}`,
        'this primitive instance drifts from the component contract — add the sub-part or justify the variant', 'Minor'));
      return { idx: i, selector: sel(el), shape: shapeArr, missingRequired: missing,
        rect: { w: round(r.width), h: round(r.height) }, hasName: !!name };
    });
    // modal shape + minority drift (INTRA-page; cross-page is the Python tool)
    const ranked = Object.entries(shapeCount).sort((a, b) => b[1] - a[1]);
    const modal = ranked.length ? ranked[0][0] : '';
    const minority = ranked.slice(1).map(([shape, n]) => ({ shape: shape.split('+'), count: n }));
    if (minority.length) defects.push(defect('C', 'component-shape-drift', null,
      `${ranked.length} shapes on this page; modal "${modal}" (${ranked[0][1]}), minority ${JSON.stringify(minority)}`,
      `one consistent ${selector} shape per page`,
      'a primitive rendering ≥2 shapes on one page is inconsistent — converge or document the variant', 'Minor'));
    return {
      selector, count: nodes.length,
      modalShape: modal ? modal.split('+') : [], distinctShapes: ranked.length,
      minorityShapes: minority, instances,
      defects, major: 0,
      note: 'INTRA-page component consistency. Cross-page = tools/survey_component_consistency.py.',
    };
  }

  // ════════════════════════════════════════════════════════════════════════
  // CRITIC — opinionated SIGNALS that feed the agent's harsh-critic judgment.
  // These are NOT auto-applied. They surface measurable cues (Hick's law choice
  // count, CTA density, duplicate-affordance) so the agent can author grounded
  // "should-be" recs into sweep_critiques.json. Returns candidate records in
  // that schema (key/page/wave/title/pillar/severity/effort/flag/should_be).
  // ════════════════════════════════════════════════════════════════════════
  function critic({ pageId = 'page', wave = 0 } = {}) {
    const candidates = []; const signals = {};
    const ctas = [...document.querySelectorAll('button,a[href],[role="button"]')].filter((el) => vis(el) && !isShell(el));
    signals.visibleCTAs = ctas.length;

    // duplicate-affordance (overlap, Phase 4.7): same accessible label reachable
    // multiple times → candidate redundancy. Count label collisions.
    const labelCount = {};
    for (const el of ctas) {
      const lbl = ((el.getAttribute('aria-label') || el.textContent || '').trim().toLowerCase()).slice(0, 40);
      if (lbl) labelCount[lbl] = (labelCount[lbl] || 0) + 1;
    }
    const dupes = Object.entries(labelCount).filter(([, n]) => n >= 3).map(([l, n]) => ({ label: l, count: n }));
    signals.duplicateAffordances = dupes;

    // Hick's law: top-level nav/choice count
    const navChoices = document.querySelectorAll('nav a,[role="navigation"] a,[role="menuitem"]').length;
    signals.navChoices = navChoices;

    // form length (Tesler / progressive disclosure cue)
    signals.maxFormFields = Math.max(0, ...[...document.querySelectorAll('form')].map((f) => f.querySelectorAll('input,select,textarea').length));

    if (ctas.length > 50) candidates.push({
      key: `sweep:${pageId}:cta-density`, page: pageId + '.html', wave,
      title: `${ctas.length} visible CTAs on the page`, pillar: 'U', severity: 'Polish', effort: 'L', flag: 'TASTE',
      should_be: 'Hick\'s law: high choice count slows decisions. If this is a marketing landing it may be fine (Jakob); on a task page, prioritize ONE primary action + progressive disclosure. Logged for the agent to judge — not a defect.',
    });
    for (const d of dupes) candidates.push({
      key: `sweep:${pageId}:dup-affordance-${d.label.replace(/\W+/g, '-').slice(0, 20)}`, page: pageId + '.html', wave,
      title: `"${d.label}" reachable ${d.count}× on this page`, pillar: 'U/IA', severity: 'Minor', effort: 'M', flag: 'TASTE',
      should_be: `Overlap (Phase 4.7): the same affordance appears ${d.count} times. Confirm each instance earns its place; collapse duplicates or differentiate. Agent to verify it's redundancy, not legitimate repetition (e.g. per-row actions).`,
    });
    return { candidates, signals, note: 'CRITIC signals are CANDIDATES — the agent authors the grounded should-be + you dispose via promotion_dispositions.json. Cross-page redundancy (Phase 4.7) needs the function_inventory, not one page.' };
  }

  // ════════════════════════════════════════════════════════════════════════
  // STATE ENUMERATION — a single run() scans ONLY the rendered DOM. A board
  // page hides most of its surface behind tabs/toggles/accordions/modals/detail
  // views. This lists those state-changers so the verdict can be HONEST about
  // what it did NOT see, and so sweepAll() can visit them. Destructive controls
  // (delete/leave/sign-out) are EXCLUDED — sweepAll must never click them.
  // ════════════════════════════════════════════════════════════════════════
  const DESTRUCTIVE_RE = /\b(delete|remove|clear|reset|discard|wipe|leave|sign\s?out|log\s?out|archive|unpublish|kick)\b/i;
  function enumerateStates() {
    const out = { tabs: [], toggles: [], modalTriggers: [], switches: [] };
    const safe = (el) => vis(el) && !isShell(el) && !DESTRUCTIVE_RE.test((el.textContent || '') + ' ' + (el.getAttribute('aria-label') || ''));
    const rec = (el) => ({ sel: sel(el), label: (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 28) });
    document.querySelectorAll('[role="tab"],.phase-tab,.view-tab,.tab-btn').forEach((el) => { if (safe(el)) out.tabs.push(rec(el)); });
    document.querySelectorAll('[aria-expanded],summary,.accordion-toggle,[data-toggle]').forEach((el) => { if (safe(el)) out.toggles.push(rec(el)); });
    document.querySelectorAll('[data-modal],[data-drawer],[onclick*="open"],[onclick*="Modal"],[onclick*="Drawer"],[onclick*="Detail"],[onclick*="Drawer"]').forEach((el) => { if (safe(el)) out.modalTriggers.push(rec(el)); });
    document.querySelectorAll('.role-btn,[onclick*="setRole"],[onclick*="setView"],[onclick*="setPhase"]').forEach((el) => { if (safe(el)) out.switches.push(rec(el)); });
    out.total = out.tabs.length + out.toggles.length + out.modalTriggers.length + out.switches.length;
    return out;
  }

  // ════════════════════════════════════════════════════════════════════════
  // RUN — REFEREE across all four pillars + a scored summary + the MCP to-do.
  // ════════════════════════════════════════════════════════════════════════
  async function referee({ pageId = 'page', role = '?', experience = '?' } = {}) {
    const [U, F, A, I] = await Promise.all([usability(), functionality(), adaptability(), internalControl()]);
    // C = display-CORRECTNESS, config-free tier (T0 garbage/range/loader + T1
    // count/sum annotations). The mutating (behavior) + oracle (parity) tiers
    // run via __UFAI.correctness(spec) / run({parity,…}) — see mcp_todo.
    const C = correctnessInvariants();
    const pillars = { U, F, A, I, C };
    const allDefects = [];
    const scores = {};
    for (const [k, p] of Object.entries(pillars)) {
      const major = p.defects.filter((d) => d.severity === 'Major' || d.severity === 'Blocker').length;
      scores[k] = { defects: p.defects.length, major, metrics: p.metrics };
      for (const d of p.defects) allDefects.push({ ...d, _id: `${pageId}:${k}:${allDefects.length}` });
    }
    const majorTotal = allDefects.filter((d) => d.severity === 'Major' || d.severity === 'Blocker').length;
    // ── COVERAGE HONESTY ──────────────────────────────────────────────────
    // This referee saw ONE rendered state. Surface how much it did NOT see so a
    // clean verdict can never be misread as "page swept." (2026-06-07: a single
    // run() was mistaken for a full sweep — analytics declared 4/4 having scanned
    // 1 of 3 phases.) complete is ALWAYS false here — only sweepAll()+the deep
    // half (parity/click-all/roles/console/network) earns a real all-clear.
    const _states = enumerateStates();
    const _allClick = 'button,a[href],[onclick],[role="button"],[role="tab"],summary';
    const _domClickable = document.querySelectorAll(_allClick).length;
    const _visClickable = [...document.querySelectorAll(_allClick)].filter((el) => vis(el) && !isShell(el)).length;
    return {
      meta: {
        battery: 'UFAI v' + V, pageId, role, experience,
        url: location.href, ts: new Date().toISOString(),
        viewport: U.metrics.viewport, axeRan: U.metrics.axe && U.metrics.axe.ran,
        identity: I.metrics.identity,
      },
      verdict: {
        totalDefects: allDefects.length, major: majorTotal,
        pillarsClean: Object.values(scores).filter((s) => s.defects === 0).length + '/' + Object.keys(scores).length,
        complete: false,   // a single run is NEVER a complete sweep — see coverage
        coverage: {
          statesScanned: 1,
          otherStatesFound: _states.total,
          tabs: _states.tabs.length, toggles: _states.toggles.length,
          modalTriggers: _states.modalTriggers.length, switches: _states.switches.length,
          domClickables: _domClickable, visibleScanned: _visClickable,
          hiddenClickables: Math.max(0, _domClickable - _visClickable),
        },
        incomplete_reason: `STATIC scan of 1 rendered state. ${_states.total} more state-changer(s) (tabs/toggles/modals/switches) + ${Math.max(0, _domClickable - _visClickable)} hidden clickable(s) NOT scanned. REQUIRED before all-clear: __UFAI.sweepAll() (multi-state) + canonical parity (tiles==DB via window.db) + click-all + role×experience + console/network — see mcp_todo.`,
        states: _states,
      },
      scores, defects: allDefects,
      cwv: cwv(),
      mcp_todo: [
        'console HISTORY before boot → browser_console_messages (battery only sees post-boot)',
        'network 4xx/5xx → browser_network_requests (status codes invisible to page JS)',
        'role×experience loop → re-seed localStorage wh_hive_role ∈ {worker,supervisor} + signout-for-solo, re-run referee each; assert role-gated UI per PERMISSION_MATRIX, no cross-hive leak',
        'CORRECTNESS parity (pillar C, T3) → read the page\'s oracle (server JSON or v_*_truth via window.db, IN-browser not mcp__postgres) then call __UFAI.run({parity:[{name,dom:<scraped map>,oracle:<EXACT field map>,tol}]}). MUST map each tile to the field the RENDERER reads (same-named ≠ same-derivation — analytics OEE-avail 96.1 ≠ reliability-avail 99.2). The battery does the keyed compare + flags VERIFY-MAPPING.',
        'adaptability probes → offline (context.setOffline) + slow-3G route throttle + 768/1280 breakpoints: calm fallback, no stuck spinner, no overflow',
        'CORRECTNESS behavior (pillar C, T2) → __UFAI.correctness({behavior:true, panel:"#sel", filters:[{apply,rows}]}): every tab must CHANGE the panel (dead-tab defect); a filter must not GROW its row count. Annotate count/total tiles with [data-count-of]/[data-sum-of] so T1 enforces them every run.',
        'INP → drive a real click, then re-call __UFAI.cwv()',
      ],
    };
  }

  // full run = referee (incl. C-invariants) + critic candidates. If the caller
  // supplies a correctness spec (parity / behavior / tabs / filters), the full
  // CORRECTNESS pass (oracle + mutating tiers) is attached under ref.correctness.
  async function run(opts = {}) {
    const ref = await referee(opts);
    ref.critic = critic(opts);
    if (opts.parity || opts.behavior || opts.tabs || opts.filters || opts.correctness) {
      ref.correctness = await correctness(opts.correctness && typeof opts.correctness === 'object' ? opts.correctness : opts);
    }
    return ref;
  }

  // ════════════════════════════════════════════════════════════════════════
  // SWEEP-ALL — drive every SAFE tab + accordion/toggle, re-run referee per
  // state, aggregate UNIQUE defects with a state label. This turns multi-state
  // coverage from "the agent remembers to do it" into one call. It does NOT
  // cover modals/detail-views/role-switches (those need page-specific open +
  // close + re-seed) — those stay in mcp_todo and the agent drives them, but
  // result.states still lists them so they can't be forgotten. Destructive
  // controls are excluded by enumerateStates. wait: ms to let a state render.
  // ════════════════════════════════════════════════════════════════════════
  async function sweepAll(opts = {}) {
    const wait = opts.wait || 1400;
    const seen = new Set(); const states = [];
    const record = async (label) => {
      const r = await referee(opts);
      const fresh = r.defects.filter((d) => { const k = d.pillar + '|' + d.check + '|' + d.selector; if (seen.has(k)) return false; seen.add(k); return true; });
      states.push({
        state: label,
        total: r.defects.length, major: r.verdict.major, newDefects: fresh.length,
        axeViolations: (r.scores.U.metrics.axe || {}).violations,
        tapUnder44: r.scores.U.metrics.tapTargets ? r.scores.U.metrics.tapTargets.under44 : null,
        cls: r.cwv.CLS,
        defects: fresh.map((d) => ({ p: d.pillar, check: d.check, sel: d.selector, sev: d.severity, measured: d.measured })),
      });
    };
    await record('default');
    // tabs (click each, let it render, scan)
    const clickAll = async (nodes, prefix, w) => {
      for (const n of nodes) {
        try {
          const el = document.querySelector(n.sel.startsWith('#') ? n.sel : null) ||
            [...document.querySelectorAll('[role="tab"],.phase-tab,.view-tab,.tab-btn,[aria-expanded],summary')]
              .find((e) => ((e.textContent || '').trim().slice(0, 28) === n.label) && vis(e) && !isShell(e));
          if (!el || !vis(el)) continue;
          el.click();
          await new Promise((r) => setTimeout(r, w));
          await record(prefix + ':' + (n.label || sel(el)));
        } catch (_) { /* empty-catch-allow: best-effort guard (test-only battery) */ }
      }
    };
    const st = enumerateStates();
    await clickAll(st.tabs, 'tab', wait);
    await clickAll(st.toggles.filter((t) => /show|expand|more|details|view/i.test(t.label) || t.label === ''), 'expand', 600);
    return {
      battery: 'UFAI v' + V, pageId: opts.pageId, statesScanned: states.length,
      enumerated: { tabs: st.tabs.length, toggles: st.toggles.length, modalTriggers: st.modalTriggers.length, switches: st.switches.length },
      totalUniqueDefects: seen.size,
      states,
      still_mcp_driven: ['modals/detail-views (open+scan+close)', 'role×experience re-seed', 'canonical parity (tiles==DB)', 'click-all WHERE/WHAT assert', 'console/network', 'offline/throttle'],
    };
  }

  // ── Gap 2: FORM-FIELD audit — the input/select/textarea checks the referee lacks.
  // Programmatic label (placeholder ≠ label), right input type (mobile keyboard +
  // validation), iOS-zoom font floor, autocomplete on identity fields. Call directly
  // (like component/inventory); not auto-folded into run() so it's opt-in per page.
  function formAudit() {
    const SKIP = ['hidden', 'submit', 'button', 'reset', 'image'];
    const fields = [...document.querySelectorAll('input,select,textarea')].filter(
      (el) => vis(el) && !isShell(el) && !SKIP.includes((el.type || '').toLowerCase()));
    const progName = (el) => {                 // programmatic label ONLY (never placeholder)
      const al = el.getAttribute('aria-label'); if (al && al.trim()) return al.trim();
      const lb = el.getAttribute('aria-labelledby');
      if (lb) { const s = lb.split(/\s+/).map((id) => (document.getElementById(id) || {}).textContent || '').join(' ').trim(); if (s) return s; }
      if (el.id) { const l = document.querySelector('label[for="' + (window.CSS && CSS.escape ? CSS.escape(el.id) : el.id) + '"]'); if (l && l.textContent.trim()) return l.textContent.trim(); }
      const w = el.closest('label'); if (w && w.textContent.trim()) return w.textContent.trim();
      const t = el.getAttribute('title'); return t && t.trim() ? t.trim() : '';
    };
    const expectedType = (el) => {
      if (el.tagName !== 'INPUT') return null;
      const hay = [el.id, el.name, el.placeholder, progName(el)].join(' ').toLowerCase();
      if (/\be-?mail\b/.test(hay)) return 'email';
      if (/\b(phone|mobile|tel|contact ?(no|number)|cell(phone)?)\b/.test(hay)) return 'tel';
      if (/\b(qty|quantity|count|hours?|days?|cost|price|amount|\bage\b|year|number of|kw|watts?|rpm|psi|°c|temp(erature)?)\b/.test(hay)) return 'number';
      if (/\b(url|website|web ?site|link)\b/.test(hay)) return 'url';
      return null;
    };
    const defects = [];
    const rows = fields.map((el) => {
      const cr = ['checkbox', 'radio'].includes((el.type || '').toLowerCase());
      const name = progName(el);
      const fs = parseFloat(getComputedStyle(el).fontSize) || 16;
      const exp = expectedType(el);
      const cur = (el.type || el.tagName.toLowerCase());
      if (!name && !cr)
        defects.push(defect('F', 'form:unlabeled-field', el,
          `no <label>/aria-label (placeholder="${(el.placeholder || '').slice(0, 24)}")`,
          'a programmatic label (label[for] / aria-label / aria-labelledby)',
          'a placeholder vanishes on focus and is invisible to screen readers — the field becomes anonymous', 'Major'));
      if (exp && (el.type || 'text').toLowerCase() === 'text')
        defects.push(defect('F', 'form:wrong-input-type', el,
          `type=text, expected type=${exp}`, `type="${exp}" (or inputmode)`,
          `a ${exp} field as plain text gives the wrong mobile keyboard and no built-in validation`, 'Minor'));
      if (!cr && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') && fs < MIN_INPUT_PX)
        defects.push(defect('F', 'form:input-font<16', el, `${fs}px`, '≥16px on text inputs',
          'iOS auto-zooms a focused input below 16px', 'Minor'));
      if (exp && (exp === 'email' || exp === 'tel') && !el.getAttribute('autocomplete'))
        defects.push(defect('F', 'form:missing-autocomplete', el, `${exp} field, no autocomplete`,
          `autocomplete="${exp === 'email' ? 'email' : 'tel'}"`, 'the worker retypes identity data every visit', 'Polish'));
      return { sel: sel(el), type: cur, name: name || null, fontPx: fs, expectedType: exp, required: !!(el.required || el.getAttribute('aria-required') === 'true') };
    });
    return { battery: 'UFAI formAudit v' + V, fieldsChecked: fields.length, major: defects.filter((d) => d.severity === 'Major').length, defects, fields: rows };
  }

  // ── Gap 1: CLICKABLE audit — purpose, not just existence. Accessible name,
  // dead-ends, and TARGET-keyed redundancy (R-FP1): redundancy is (name × resolved
  // target) and EXCLUDES per-list-item siblings (13 "Save" on 13 cards = a list,
  // not a duplicated affordance — the old name-only counter's false-positive).
  function clickAudit() {
    const SEL = 'a[href],button,[role="button"],[onclick],input[type="button"],input[type="submit"],summary';
    const dis = (el) => el.disabled === true || el.getAttribute('aria-disabled') === 'true' || (el.matches && el.matches(':disabled'));
    const inert = (el) => !!(el.inert || (el.closest && el.closest('[inert]')));
    const els = [...document.querySelectorAll(SEL)].filter((el) => vis(el) && !isShell(el) && !dis(el) && !inert(el));
    const aName = (el) => {
      const al = el.getAttribute('aria-label'); if (al && al.trim()) return al.trim();
      const t = (el.textContent || '').replace(/\s+/g, ' ').trim(); if (t) return t;
      const ti = el.getAttribute('title'); if (ti && ti.trim()) return ti.trim();
      const im = el.querySelector('img[alt]'); if (im && im.alt.trim()) return im.alt.trim();
      const st = el.querySelector('svg title'); if (st && st.textContent.trim()) return st.textContent.trim();
      const vt = el.value; if (vt && String(vt).trim()) return String(vt).trim();
      return '';
    };
    const target = (el) => {
      if (el.tagName === 'A' && el.getAttribute('href')) { const h = el.getAttribute('href'); return h.replace(/^https?:\/\/[^/]+/, '').replace(/[#?].*$/, '') || h; }
      const oc = el.getAttribute('onclick'); if (oc) { const m = oc.match(/([a-zA-Z_$][\w$]*)\s*\(([^)]*)/); return m ? 'fn:' + m[1] + '(' + (m[2] || '').trim().slice(0, 24) + ')' : 'onclick'; }
      const da = el.getAttribute('data-action') || el.getAttribute('data-target'); if (da) return 'data:' + da;
      return null;
    };
    // Walk the FULL ancestor chain — a clickable is a per-list-item action if ANY
    // ancestor is one of ≥2 same-template siblings (same tag + same first-class
    // token). `closest('[class*=card]')` is wrong: it stops at the nearest "card-ish"
    // sub-part (e.g. div.card-image, 2 siblings), not the REPEATED unit
    // (article.listing-card, 13 siblings) — which is why 13 per-card "Save" buttons
    // leaked through as redundancy.
    const firstClass = (n) => String(n.className || '').trim().split(/\s+/)[0] || '';
    const isListItem = (el) => {
      let n = el.parentElement;
      for (let i = 0; i < 9 && n && n !== document.body; i++) {
        const p = n.parentElement, fc = firstClass(n);
        if (p && fc) {
          const sibs = [...p.children].filter((x) => x.tagName === n.tagName && firstClass(x) === fc);
          if (sibs.length >= 2) return true;
        }
        n = p;
      }
      return false;
    };
    // a NATIVE control (a/button/summary/input/select/textarea) is keyboard-operable
    // for free; a div/span carrying its OWN onclick is not unless it is made focusable
    // (tabindex>=0 / contentEditable). This is the keyboard-dead `<div onclick>` the
    // name+dead-end checks MISS when the div has text (e.g. clickable asset-cards) —
    // statesAudit only catches the styling symptom. WCAG 2.1.1.
    const nativeInteractive = (el) => /^(a|button|summary|input|select|textarea)$/.test(el.tagName.toLowerCase());
    const keyboardReachable = (el) => nativeInteractive(el) || (el.tabIndex >= 0) || el.isContentEditable;
    const defects = [];
    const rows = els.map((el) => {
      const name = aName(el), tgt = target(el), li = isListItem(el);
      const deadHref = el.tagName === 'A' && /^(#|javascript:(void\(0\)?)?;?)$/i.test((el.getAttribute('href') || '').trim());
      if (!name)
        defects.push(defect('F', 'click:no-accessible-name', el, `<${el.tagName.toLowerCase()}> has no text/aria-label/title`,
          'an accessible name (text, aria-label, or title)', 'an icon-only control with no name is unusable by screen readers and ambiguous to everyone', 'Major'));
      if (deadHref && !el.getAttribute('onclick') && !el.getAttribute('role'))
        defects.push(defect('F', 'click:dead-end', el, `href="${(el.getAttribute('href') || '').trim()}" with no handler`,
          'a real destination or an onclick handler', 'a link that goes nowhere and does nothing', 'Minor'));
      if (el.hasAttribute('onclick') && !nativeInteractive(el) && !keyboardReachable(el))
        defects.push(defect('F', 'click:not-keyboard-operable', el, `<${el.tagName.toLowerCase()}> has its own onclick but no tabindex — mouse-only`,
          'role="button" + tabindex="0" + an Enter/Space keydown handler', 'a keyboard / switch / screen-reader user cannot reach or activate this control (WCAG 2.1.1)', 'Major'));
      return { sel: sel(el), name: name || null, target: tgt, listItem: li, keyboard: keyboardReachable(el) };
    });
    // R-FP1: target-keyed redundancy. ONLY group NON-list clickables with a RESOLVED
    // target — an unresolved target (addEventListener, no onclick attr) must NOT
    // collapse distinct controls (9 different modal-close buttons share the name
    // "close" but each closes its own modal → not redundant). Conservative by design:
    // it can MISS a real dup whose target it can't resolve, but it never invents one.
    const groups = {};
    rows.forEach((r) => {
      if (r.listItem || !r.name || !r.target) return;   // require a resolved target
      const k = r.name.toLowerCase() + ' ⇒ ' + r.target;
      (groups[k] = groups[k] || []).push(r.sel);
    });
    const redundant = Object.entries(groups).filter(([, v]) => v.length >= 2).map(([k, v]) => ({ affordance: k, count: v.length, where: v.slice(0, 6) }));
    redundant.forEach((g) =>
      defects.push(defect('F', 'click:redundant-affordance', null, `"${g.affordance}" reachable ${g.count}× (same name → same RESOLVED target, non-list)`,
        'one affordance per (name × target) in non-list context', 'the same action is offered multiple times from one screen — pick one home', 'Minor')));
    return {
      battery: 'UFAI clickAudit v' + V, checked: els.length,
      major: defects.filter((d) => d.severity === 'Major').length,
      listItemsExcluded: rows.filter((r) => r.listItem).length,
      redundant, defects,
    };
  }

  // ── Gap 4: INTERACTION-STATE audit. Three things the shape/focus checks miss:
  // (1) SELECTED distinctness — a `.tab.active` that computes the same style as
  //     `.tab` = an invisible selection (user can't tell what's on). [Major]
  // (2) HOVER / FOCUS affordance — an interactive primitive with NO `:hover` and
  //     NO `:focus`/`:focus-visible` RULE gives no feedback on point/keyboard. [Minor]
  // (3) DISABLED distinctness — a `:disabled`/`.disabled` instance must look
  //     different from enabled, or the user taps a dead control. [Minor]
  function statesAudit() {
    const FAM = [
      { base: '.filter-chip', active: '.filter-chip.active' },
      { base: '.chip', active: '.chip.active' },
      { base: '.pill', active: '.pill.active' },
      { base: '.pill-btn', active: '.pill-btn.active' },
      { base: '.tab', active: '.tab.active' },
      { base: '.page-tab', active: '.page-tab.active' },
      { base: '.view-tab', active: '.view-tab.active' },
      { base: '.shift-pill', active: '.shift-pill.active' },
      { base: '.phase-tab', active: '.phase-tab.active' },
      { base: '.btn', active: '.btn.active' },
      { base: '.asset-card', active: '.asset-card.active' },
      { base: '[role="tab"]', active: '[role="tab"][aria-selected="true"]' },
    ];
    const sig = (el) => { const c = getComputedStyle(el); return [c.backgroundColor, c.color, c.borderColor, c.borderBottomColor, c.fontWeight, c.boxShadow, c.outlineStyle, c.textDecorationLine, c.opacity].join('|'); };
    // collect every selectorText once (skip cross-origin sheets that throw)
    const selectorTexts = [];
    for (const ss of document.styleSheets) {
      let rules; try { rules = ss.cssRules; } catch (_) { continue; }
      for (const r of rules || []) { if (r.selectorText) selectorTexts.push(r.selectorText); }
    }
    const hasPseudo = (base, pseudo) => selectorTexts.some((s) => s.includes(base) && s.includes(pseudo));
    const defects = [], checked = [];
    for (const f of FAM) {
      let base, act, instances;
      try {
        instances = [...document.querySelectorAll(f.base)].filter((el) => vis(el) && !isShell(el));
        base = instances.find((el) => !el.matches(f.active));
        act = [...document.querySelectorAll(f.active)].find((el) => vis(el) && !isShell(el));
      } catch (_) { continue; }
      if (!instances.length) continue;
      const row = { family: f.base, instances: instances.length };
      // (1) selected distinctness
      if (base && act) { row.distinct = sig(base) !== sig(act);
        if (!row.distinct) defects.push(defect('U', 'state:selected-not-distinct', act,
          `${f.active} computes an identical style to ${f.base}`,
          'the active/selected state must differ visibly', 'a user cannot tell which option is selected', 'Major')); }
      // (2) hover / focus affordance (RULE existence)
      // A NATIVE interactive element (button/a/input/select/textarea) carries a UA
      // default focus ring, so absence of an explicit `.cls:focus` rule is NOT a
      // missing-focus defect (e.g. `.filter-chip` is a <button> → visible orange ring
      // for free). Only a non-native primitive with no focus rule is genuinely blind.
      const rep = base || instances[0];
      const repNative = !!rep && /^(a|button|input|select|textarea|summary)$/.test(rep.tagName.toLowerCase());
      row.nativeFocus = repNative;
      row.hasHover = hasPseudo(f.base, ':hover');
      row.hasFocus = hasPseudo(f.base, ':focus');
      if (!row.hasHover) defects.push(defect('U', 'state:no-hover-feedback', base || instances[0],
        `${f.base} has no :hover style rule`, 'a :hover state so the control reacts to pointing',
        'the control gives no hover feedback — feels dead on desktop', 'Minor'));
      if (!row.hasFocus && !repNative) defects.push(defect('U', 'state:no-focus-style', base || instances[0],
        `${f.base} has no :focus / :focus-visible rule (non-native primitive)`, 'a :focus-visible ring for keyboard users',
        'a keyboard user cannot see which control is focused (WCAG 2.4.7)', 'Minor'));
      // (3) disabled distinctness
      let dis; try { dis = document.querySelector(`${f.base}:disabled, ${f.base}.disabled, ${f.base}[aria-disabled="true"]`); } catch (_) { dis = null; }
      if (dis && base && vis(dis)) { row.disabledDistinct = sig(base) !== sig(dis);
        if (!row.disabledDistinct) defects.push(defect('U', 'state:disabled-not-distinct', dis,
          `disabled ${f.base} looks identical to enabled`, 'a disabled control must look inactive (opacity/colour)',
          'the user taps a dead control because it looks enabled', 'Minor')); }
      checked.push(row);
    }
    return { battery: 'UFAI statesAudit v' + V, familiesChecked: checked.length, checked, defects, major: defects.filter((d) => d.severity === 'Major').length };
  }

  // ── Gap 6 + ENTRY POINT: full() runs the ENTIRE interface subject-axis for one
  // page in a single call — referee (U/F/A/I/C) + formAudit + clickAudit +
  // statesAudit + component — and returns a consolidated verdict. This is the
  // "full Layer-3 battery per page" the comprehensive scenario run drives. The
  // OTHER two subject-axes compose ON TOP, live: AI-behaviour = companion_battery.js
  // (window.__CSB), DATA = analytics_correctness.js. sweepAll() + modal drills +
  // journeys remain MCP-orchestrated (multi-state / cross-page can't run in one tick).
  async function full(opts = {}) {
    const r = await run(opts);
    const fa = formAudit(), ca = clickAudit(), sa = statesAudit(), comp = component();
    const compDefects = comp && comp.primitives ? Object.values(comp.primitives).flatMap((p) => p.defects || []) : [];
    const isMajor = (d) => d.severity === 'Major' || d.severity === 'Blocker';
    const buckets = {
      referee:   { major: r.verdict.major,                       defects: r.defects || [] },
      form:      { major: fa.major,                              defects: fa.defects },
      click:     { major: ca.major,                              defects: ca.defects },
      states:    { major: sa.major,                              defects: sa.defects },
      component: { major: compDefects.filter(isMajor).length,    defects: compDefects },
    };
    const totalMajor = Object.values(buckets).reduce((a, b) => a + b.major, 0);
    const allMajor = Object.values(buckets).flatMap((b) => (b.defects || []).filter(isMajor));
    return {
      battery: 'UFAI full v' + V, pageId: opts.pageId || 'page', role: opts.role, experience: opts.experience,
      totalMajor, byBucket: Object.fromEntries(Object.entries(buckets).map(([k, v]) => [k, v.major])),
      counts: { fieldsChecked: fa.fieldsChecked, clickablesChecked: ca.checked, listItemsExcluded: ca.listItemsExcluded, stateFamilies: sa.familiesChecked },
      majorDefects: allMajor.map((d) => `[${d.pillar || '?'}] ${d.check}: ${('' + d.measured).slice(0, 64)}`),
      cwv: r.cwv, coverage: r.verdict && r.verdict.coverage,
      note: 'INTERFACE axis (run+form+click+states+component). AI-behaviour=__CSB (companion_battery.js); DATA=analytics_correctness.js. sweepAll()+modals+journeys still MCP-driven.',
    };
  }

  window.__UFAI = {
    _v: V, _installed: true,
    boot, run, full, referee, critic, cwv, enumerateStates, sweepAll,
    usability, functionality, adaptability, internalControl,
    correctness, correctnessInvariants, correctnessParity, correctnessBehavior,
    inventory, // Layer A of the IA-streamlining surveyor (cross-page redundancy)
    component, // ① component battery — live DOM-accurate per-primitive shape audit
    formAudit, // Gap 2 — input/select/textarea: label, type, autocomplete, iOS-font
    clickAudit, // Gap 1 — clickable purpose + R-FP1 target-keyed redundancy
    statesAudit, // Gap 4 — selected/active variant must be visually distinct from base
    _state, // exposed for debugging / MCP inspection
  };
  return { installed: true, _v: V, hint: 'await window.__UFAI.boot() then await window.__UFAI.run({pageId,role,experience})' };
}
