// w4_design_audit.body.js - the audit lens's instrument (impeccable audit.md: five dimensions scored 0-4), measured on the
// RENDERED page through the Playwright MCP at phone-390 and desktop-1280 (2026-09-15). Loaded by tools/w4_design_audit.js;
// parameters from .tmp/w4_args.json ({ id, page, lang }). It writes .tmp/w4_steps/<id>_audit.json through the seeder's
// POST /api/w4/steps so the numbers the scores rest on are on disk beside the walk. The SCORES stay the reader's
// (bank_mcp_design_walk.py takes --scores); this hands the reader what each dimension asks for:
//   a11y        - landmarks, lang, skip link, named controls, images without alt, inputs without labels, heading skips,
//                 toggles without state, clickable divs, a reduced-motion rule, focus rings drawn while tabbing
//   performance - LCP, layout shift, long tasks, nodes, resources + transfer, elements animating at rest, will-change,
//                 heavy blurs, images loaded lazily
//   theming     - raw hex literals vs var(--) references in the page's own <style> rules, inline hex, color-scheme
//   responsive  - spill, elements past the right edge, controls under 44px, fixed widths wider than the viewport,
//                 media queries present, and the same page at a 125% text size
//   integrity   - page errors and console errors on load (the detector runs on the bank side)
// plus what still animates when the person asked for reduced motion.
async (mcpPage) => {
  const base = 'http://localhost:5000/workhive';
  let P = {};
  try { const ar = await mcpPage.request.get(`${base}/.tmp/w4_args.json`, { timeout: 5000 }); if (ar.ok()) P = await ar.json(); } catch (e) { void e; }
  if (!P.page) return { problems: ['no page in .tmp/w4_args.json'] };
  const out = { id: P.id, page: P.page, lens: 'audit', lang: P.lang || 'en', viewports: [], problems: [] };
  const page = await mcpPage.context().newPage();
  try {
    // the shell the last walk installed must not serve this one: drop the service worker, its caches and the HTTP cache
    try { const cdp0 = await page.context().newCDPSession(page); await cdp0.send('Storage.clearDataForOrigin', { origin: 'http://localhost:5000', storageTypes: 'service_workers,cache_storage' }); out.cdpReset = 'ok'; } catch (e) { out.cdpReset = String(e && e.message || e).slice(0, 60); }
    await page.goto(`${base}/index.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    out.shellReset = await page.evaluate(async () => { let w = 0, c = 0; try { const rs = await navigator.serviceWorker.getRegistrations(); for (const r of rs) { await r.unregister(); w++; } const ks = await caches.keys(); for (const k of ks) { await caches.delete(k); c++; } } catch (e) { void e; } return { workers: w, caches: c }; });
    try { const cdp = await page.context().newCDPSession(page); await cdp.send('Network.enable'); await cdp.send('Network.setCacheDisabled', { cacheDisabled: true }); out.httpCache = 'disabled'; } catch (e) { out.httpCache = 'not disabled: ' + String(e && e.message || e).slice(0, 60); }
    const LANG = P.lang || 'en';
    await page.evaluate((l) => { try { localStorage.setItem('wh_lang', l); } catch (e) { void e; } }, LANG);
    await page.addInitScript((l) => {
      try { localStorage.setItem('wh_lang', l); } catch (e) { void e; }
      window.__W4A = { lcp: 0, cls: 0, longTasks: 0, errors: [], shifts: [] };
      try { new PerformanceObserver((list) => { for (const e of list.getEntries()) window.__W4A.lcp = Math.round(e.renderTime || e.loadTime || e.startTime); }).observe({ type: 'largest-contentful-paint', buffered: true }); } catch (e) { void e; }
      try { new PerformanceObserver((list) => { for (const e of list.getEntries()) { if (e.hadRecentInput) continue; window.__W4A.cls += e.value; const src = (e.sources || []).map((x) => { const n = x.node; if (!n || !n.tagName) return '?'; return n.tagName.toLowerCase() + (n.id ? '#' + n.id : '') + (typeof n.className === 'string' && n.className ? '.' + n.className.split(' ')[0] : ''); }).slice(0, 3).join(', '); window.__W4A.shifts.push(Math.round(e.value * 1000) / 1000 + ' @' + Math.round(e.startTime) + 'ms ' + src); } }).observe({ type: 'layout-shift', buffered: true }); } catch (e) { void e; }
      try { new PerformanceObserver((list) => { window.__W4A.longTasks += list.getEntries().length; }).observe({ type: 'longtask', buffered: true }); } catch (e) { void e; }
      window.addEventListener('error', (ev) => window.__W4A.errors.push(String(ev.message || ev).slice(0, 120)));
    }, LANG);
    const consoleErrors = []; page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 140)); });
    const pageErrors = []; page.on('pageerror', (e) => pageErrors.push(String(e && e.message || e).slice(0, 140)));

    const measure = () => page.evaluate(() => {
      const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
      const A = window.__W4A || {};
      const tag = (e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className ? '.' + e.className.split(' ')[0] : '');
      // 1. accessibility
      const ctl = [...document.querySelectorAll('button, a[href], input, select, textarea, [role="button"], [role="tab"]')].filter(vis);
      const nameOf = (e) => (e.getAttribute('aria-label') || e.getAttribute('title') || (e.labels && e.labels[0] && e.labels[0].textContent) || e.textContent || e.value || e.getAttribute('placeholder') || (e.querySelector('img[alt]') && e.querySelector('img[alt]').alt) || '').replace(/\s+/g, ' ').trim();
      const unnamed = ctl.filter((e) => !nameOf(e));
      const imgs = [...document.querySelectorAll('img')].filter(vis);
      const inputs = [...document.querySelectorAll('input:not([type=hidden]), select, textarea')].filter(vis);
      const inputNoLabel = inputs.filter((i) => !(i.labels && i.labels.length) && !i.getAttribute('aria-label') && !i.getAttribute('aria-labelledby'));
      const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(vis).map((h) => +h.tagName[1]); let skips = 0; for (let i = 1; i < hs.length; i++) if (hs[i] > hs[i - 1] + 1) skips++;
      const toggles = [...document.querySelectorAll('[aria-controls]')].filter(vis); const togglesNoState = toggles.filter((t) => !t.hasAttribute('aria-expanded') && !t.hasAttribute('aria-pressed') && !t.hasAttribute('aria-selected'));
      const clickDivs = [...document.querySelectorAll('div[onclick], span[onclick], li[onclick]')].filter(vis).filter((e) => !e.getAttribute('role') && !e.hasAttribute('tabindex'));
      const sheets = [...document.styleSheets]; const rulesOf = (ss) => { try { return [...ss.cssRules]; } catch (e) { return []; } };
      const reduceRule = sheets.some((ss) => rulesOf(ss).some((r) => r.media && /prefers-reduced-motion/.test(r.media.mediaText)));
      const a11y = { landmarks: { main: !!document.querySelector('main, [role=main]'), nav: !!document.querySelector('nav, [role=navigation]'), header: !!document.querySelector('header, [role=banner]'), h1: document.querySelectorAll('h1').length, skipLink: !!document.querySelector('a.wh-skip-link, a[href^="#main"], a[href="#content"]'), lang: document.documentElement.lang || '' },
        controls: ctl.length, unnamed: unnamed.length, unnamedSample: unnamed.slice(0, 6).map(tag), images: imgs.length, imagesNoAlt: imgs.filter((i) => !i.hasAttribute('alt')).length,
        inputs: inputs.length, inputsNoLabel: inputNoLabel.length, inputsNoLabelSample: inputNoLabel.slice(0, 4).map(tag), headings: hs.length, headingSkips: skips,
        toggles: toggles.length, togglesNoState: togglesNoState.length, togglesNoStateSample: togglesNoState.slice(0, 4).map(tag), clickableDivs: clickDivs.length, clickableDivSample: clickDivs.slice(0, 4).map(tag), reducedMotionRule: reduceRule };
      // 2. performance
      const all = [...document.querySelectorAll('body *')].filter(vis);
      let animAtRest = 0, willChange = 0, heavyBlur = 0; const animSample = [];
      for (const e of all) { const cs = getComputedStyle(e); if (cs.animationName !== 'none' && parseFloat(cs.animationDuration) > 0 && cs.animationIterationCount === 'infinite' && cs.animationPlayState !== 'paused') { animAtRest++; if (animSample.length < 4) animSample.push(tag(e) + ' ' + cs.animationName); } if (cs.willChange && cs.willChange !== 'auto') willChange++; const mm = /blur\(([\d.]+)px\)/.exec((cs.filter || '') + ' ' + (cs.backdropFilter || '')); if (mm && +mm[1] > 20) heavyBlur++; }
      const res = performance.getEntriesByType('resource');
      const perf = { lcpMs: A.lcp || 0, cls: Math.round((A.cls || 0) * 1000) / 1000, shifts: (A.shifts || []).sort((a, b) => parseFloat(b) - parseFloat(a)).slice(0, 5), longTasks: A.longTasks || 0, nodes: document.querySelectorAll('*').length, resources: res.length, transferKB: Math.round(res.reduce((a, r) => a + (r.transferSize || 0), 0) / 1024),
        animatingAtRest: animAtRest, animatingSample: animSample, willChange, heavyBlur, images: imgs.length, imagesLazy: imgs.filter((i) => i.loading === 'lazy').length, imagesBelowFoldNotLazy: imgs.filter((i) => i.loading !== 'lazy' && i.getBoundingClientRect().top > innerHeight).length };
      // 3. theming - the page's own <style> rules
      let rawHex = 0, tokenRefs = 0, rules = 0; const rawHexSample = [];
      for (const ss of sheets) { if (!ss.ownerNode || ss.ownerNode.tagName !== 'STYLE') continue; for (const r of rulesOf(ss)) { const t = r.cssText || ''; rules++; const hx = t.match(/#[0-9a-fA-F]{3,8}\b/g) || []; rawHex += hx.length; if (hx.length && rawHexSample.length < 6) rawHexSample.push(((r.selectorText || r.cssText) + '').slice(0, 40) + ' ' + hx.slice(0, 3).join(' ')); tokenRefs += (t.match(/var\(--/g) || []).length; } }
      const inlineHex = all.filter((e) => /#[0-9a-fA-F]{3,8}\b/.test(e.getAttribute('style') || '')).length;
      const theming = { pageRules: rules, rawHex, rawHexSample, tokenRefs, inlineHex, colorScheme: getComputedStyle(document.documentElement).colorScheme, themeTokensDefined: getComputedStyle(document.documentElement).getPropertyValue('--wh-navy').trim() !== '' };
      // 4. responsive
      // ★WCAG 2.5.8 EXEMPTS A TARGET THAT IS A WORD IN A SENTENCE ("Inline" exception). achievements.html's
      // 'Every badge you earn here lands on your Resume automatically' link measured 57x19 and was counted as
      // a violation, which would have had me pad prose into a button (2026-09-15). An inline-displayed control
      // inside a paragraph is reported separately, and counted as what it is - not as a failure.
      const isInlineInProse = (e) => {
        const d = getComputedStyle(e).display;
        if (d !== 'inline' && d !== 'inline-block') return false;
        const par = e.closest('p, li, blockquote, figcaption, td, dd');
        if (!par) return false;
        const own = (e.textContent || '').trim().length;
        return (par.textContent || '').trim().length > own + 20;   // the control is a fragment of a sentence
      };
      const smallAll = ctl.filter((e) => { const r = e.getBoundingClientRect(); return r.width < 44 || r.height < 44; });
      const inlineExempt = smallAll.filter(isInlineInProse);
      const small = smallAll.filter((e) => !isInlineInProse(e));
      const over = all.filter((e) => e.getBoundingClientRect().right > innerWidth + 1 && getComputedStyle(e).position !== 'fixed');
      const fixedWide = all.filter((e) => { const w = getComputedStyle(e).width; return /px$/.test(w) && parseFloat(w) > innerWidth; });
      const mq = sheets.reduce((n, ss) => n + rulesOf(ss).filter((r) => r.media && /max-width|min-width/.test(r.media.mediaText)).length, 0);
      const responsive = { innerWidth, spill: document.documentElement.scrollWidth - innerWidth, pastRightEdge: over.length, pastRightEdgeSample: over.slice(0, 4).map(tag), controlsUnder44: small.length, inlineTextLinksExempt: inlineExempt.length, inlineTextLinksSample: inlineExempt.slice(0, 3).map((e) => (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 30)), controlsUnder44Sample: small.slice(0, 4).map((e) => { const r = e.getBoundingClientRect(); return `${tag(e)} ${Math.round(r.width)}x${Math.round(r.height)}`; }), fixedWiderThanViewport: fixedWide.length, mediaQueries: mq };
      // 5. integrity - what the browser itself reported while the page loaded
      const integrity = { windowErrors: (A.errors || []).length, windowErrorSample: (A.errors || []).slice(0, 4), h1: (document.querySelector('h1') || {}).textContent ? document.querySelector('h1').textContent.replace(/\s+/g, ' ').trim().slice(0, 60) : '', chars: (document.body.innerText || '').replace(/\s+/g, ' ').trim().length };
      return { a11y, perf, theming, responsive, integrity };
    });
    const textScale = () => page.evaluate(() => {
      const root = document.documentElement; const was = root.style.fontSize; root.style.fontSize = '125%';
      const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
      const all = [...document.querySelectorAll('body *')].filter(vis);
      const clippedEls = all.filter((e) => { const cs = getComputedStyle(e); return cs.overflow === 'hidden' && e.scrollHeight > e.clientHeight + 2 && e.clientHeight > 1 && cs.textOverflow !== 'ellipsis' && /^(P|SPAN|DIV|LI|H[1-6]|SMALL|LABEL|BUTTON)$/.test(e.tagName) && e.children.length === 0; });
      const r = { spill: document.documentElement.scrollWidth - innerWidth, pastRightEdge: all.filter((e) => e.getBoundingClientRect().right > innerWidth + 1 && getComputedStyle(e).position !== 'fixed').length, clipped: clippedEls.length, clippedSample: clippedEls.slice(0, 4).map((e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className ? '.' + e.className.split(' ')[0] : '') + ' "' + e.textContent.replace(/\s+/g, ' ').trim().slice(0, 30) + '" ' + e.clientHeight + '/' + e.scrollHeight) };
      root.style.fontSize = was; return r;
    });

    // arrive as the person: a session the idle timer has ended is signed in again with the cast's credentials
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${base}/${P.page}`, { waitUntil: 'load', timeout: 45000 });
    await page.waitForTimeout(2500);
    const wall = await page.locator('#si-username').isVisible().catch(() => false);
    if (wall || /signin=1/.test(page.url())) {
      await page.waitForSelector('#si-username', { state: 'visible', timeout: 30000 }).catch(() => {});
      await page.fill('#si-username', P.user || 'christinedizon', { timeout: 8000 });
      await page.fill('#si-password', P.pass || 'test1234', { timeout: 8000 });
      await page.click('#si-btn', { timeout: 10000 }).catch(async () => { await page.press('#si-password', 'Enter', { timeout: 4000 }).catch(() => {}); });
      const atPage = new RegExp('/' + P.page.split('.').join('[.]') + '(?:[?#]|$)');
      try { await page.waitForURL(atPage, { timeout: 25000 }); out.signedIn = 'again, as ' + (P.user || 'christinedizon'); }
      catch (e) { out.problems.push('sign-in did not reach the page in 25s'); return out; }
    } else { out.signedIn = 'session held'; }
    for (const vp of [{ name: 'phone-390', w: 390, h: 844 }, { name: 'desktop-1280', w: 1280, h: 800 }]) {
      consoleErrors.length = 0; pageErrors.length = 0;
      await page.setViewportSize({ width: vp.w, height: vp.h });
      await page.emulateMedia({ reducedMotion: 'no-preference' });
      const t0 = Date.now();
      await page.goto(`${base}/${P.page}`, { waitUntil: 'load', timeout: 45000 });
      await page.waitForTimeout(7000);
      if (await page.locator('#si-username').isVisible().catch(() => false) || /signin=1/.test(page.url())) { out.problems.push(`${vp.name}: the session ended and the sign-in wall rendered instead of ${P.page}`); break; }
      const m = await measure();
      // keyboard: tab through the first eight focusables and read whether a ring is drawn on each
      const rings = [];
      for (let i = 0; i < 8; i++) {
        await page.keyboard.press('Tab');
        const r = await page.evaluate(() => { const a = document.activeElement; if (!a || a === document.body) return null; const cs = getComputedStyle(a); const ring = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) || (!!cs.boxShadow && cs.boxShadow !== 'none'); return { el: a.tagName.toLowerCase() + (a.id ? '#' + a.id : '') + (typeof a.className === 'string' && a.className ? '.' + a.className.split(' ')[0] : ''), name: (a.getAttribute('aria-label') || a.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 30), ring }; });
        if (r) rings.push(r);
      }
      const scaled = await textScale();
      // what still moves when the person asked for less motion
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.waitForTimeout(500);
      const rm = await page.evaluate(() => { const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; }; let anim = 0, slow = 0; const sample = []; for (const e of document.querySelectorAll('body *')) { if (!vis(e)) continue; const cs = getComputedStyle(e); if (cs.animationName !== 'none' && parseFloat(cs.animationDuration) > 0 && cs.animationPlayState !== 'paused') { anim++; if (sample.length < 4) sample.push(e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className ? '.' + e.className.split(' ')[0] : '') + ' ' + cs.animationName); } if ((cs.transitionDuration || '0s').split(',').some((d) => parseFloat(d) > 0.3)) slow++; } return { animatingUnderReduce: anim, animatingSample: sample, slowTransitionsUnderReduce: slow }; });
      await page.emulateMedia({ reducedMotion: 'no-preference' });
      out.viewports.push(Object.assign({ viewport: vp.name, loadMs: Date.now() - t0 }, m, { focusRings: rings, focusRingsDrawn: rings.filter((r) => r.ring).length, textScale125: scaled, reducedMotion: rm, consoleErrors: consoleErrors.slice(0, 5), consoleErrorCount: consoleErrors.length, pageErrors: pageErrors.slice(0, 5), pageErrorCount: pageErrors.length }));
    }
    const res = await page.request.post('http://localhost:5000/api/w4/steps', { data: { id: `${P.id}_audit`, steps: out, records: [] } });   // the seeder's API lives at its root, not under /workhive
    out.wrote = res.ok() ? (await res.json()).path : `POST /api/w4/steps -> ${res.status()}`;
  } catch (e) { out.problems.push(String(e && e.message || e).slice(0, 240)); }
  finally { try { await page.close(); } catch (e) { void e; } }
  return out;
}
