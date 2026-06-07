/* ============================================================================
 * ufai_battery.js  —  The reusable Grounded-Sweep UFAI battery  (v1.0.0)
 * ============================================================================
 * ONE injectable that you paste into the Playwright MCP `browser_evaluate`
 * `function` arg. It installs `window.__UFAI` and runs a MEASURED battery
 * across the four pillars — Usability · Functionality · Adaptability ·
 * Internal-Control — returning numbers (rect sizes, font px, axe violations,
 * CWV) so every finding is regression-testable.
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
 * The file is a single arrow function so it can be passed verbatim as the
 * `function` argument. It is idempotent (re-paste = no-op if same version).
 * ==========================================================================*/
() => {
  const V = '1.0.0';
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
      // a small control inside a ≥44 hit-row passes (parent hitbox)
      const par = el.closest('li,tr,.row,[role="listitem"]');
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
  // RUN — REFEREE across all four pillars + a scored summary + the MCP to-do.
  // ════════════════════════════════════════════════════════════════════════
  async function referee({ pageId = 'page', role = '?', experience = '?' } = {}) {
    const [U, F, A, I] = await Promise.all([usability(), functionality(), adaptability(), internalControl()]);
    const pillars = { U, F, A, I };
    const allDefects = [];
    const scores = {};
    for (const [k, p] of Object.entries(pillars)) {
      const major = p.defects.filter((d) => d.severity === 'Major' || d.severity === 'Blocker').length;
      scores[k] = { defects: p.defects.length, major, metrics: p.metrics };
      for (const d of p.defects) allDefects.push({ ...d, _id: `${pageId}:${k}:${allDefects.length}` });
    }
    const majorTotal = allDefects.filter((d) => d.severity === 'Major' || d.severity === 'Blocker').length;
    return {
      meta: {
        battery: 'UFAI v' + V, pageId, role, experience,
        url: location.href, ts: new Date().toISOString(),
        viewport: U.metrics.viewport, axeRan: U.metrics.axe && U.metrics.axe.ran,
        identity: I.metrics.identity,
      },
      verdict: { totalDefects: allDefects.length, major: majorTotal, pillarsClean: Object.values(scores).filter((s) => s.defects === 0).length + '/4' },
      scores, defects: allDefects,
      cwv: cwv(),
      mcp_todo: [
        'console HISTORY before boot → browser_console_messages (battery only sees post-boot)',
        'network 4xx/5xx → browser_network_requests (status codes invisible to page JS)',
        'role×experience loop → re-seed localStorage wh_hive_role ∈ {worker,supervisor} + signout-for-solo, re-run referee each; assert role-gated UI per PERMISSION_MATRIX, no cross-hive leak',
        'canonical parity → read the page\'s v_*_truth via window.db in a follow-up browser_evaluate; assert every rendered tile == DB (page-specific, not generic)',
        'adaptability probes → offline (context.setOffline) + slow-3G route throttle + 768/1280 breakpoints: calm fallback, no stuck spinner, no overflow',
        'F0 LIVE half → click/fill every SAFE clickable; assert WHERE/WHAT/WHEN/WHO landed (battery did the static wiring scan only)',
        'INP → drive a real click, then re-call __UFAI.cwv()',
      ],
    };
  }

  // full run = referee + critic candidates in one object
  async function run(opts = {}) {
    const ref = await referee(opts);
    ref.critic = critic(opts);
    return ref;
  }

  window.__UFAI = {
    _v: V, _installed: true,
    boot, run, referee, critic, cwv,
    usability, functionality, adaptability, internalControl,
    _state, // exposed for debugging / MCP inspection
  };
  return { installed: true, _v: V, hint: 'await window.__UFAI.boot() then await window.__UFAI.run({pageId,role,experience})' };
}
