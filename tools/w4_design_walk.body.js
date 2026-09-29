// w4_design_walk.body.js - ONE served page seen through a design lens, walked through the Playwright MCP as the
// person (2026-09-15). Loaded by tools/w4_design_walk.js; parameters from .tmp/w4_args.json (served by the seeder):
//   { id: 'W45839', page: 'achievements.html', lens: 'slop', user: 'christinedizon', pass: 'test1234',
//     castName: 'Christine Dizon', lang: 'en', shotDir: 'C:/.../.tmp/w4_design', origin: 'http://localhost:5000/workhive' }
//
// What it records, per Impeccable's own verify rule ("one batched round, desktop and mobile together"): the page at
// phone-390 AND desktop-1280 in one browser context - each with the per-step overlap/occlusion record (the same
// tools/phone_fit_audit.browser.js every W4 walk injects), the live measures the lenses read (smallest visible font,
// text under 11 / 12 px, tap targets under 44, declared motion that is slow or ease-in, the body measure in ch,
// heading skips, horizontal spill) and a full-page screenshot for the design review. The lens's JUDGEMENT is made
// in the conversation on this evidence; tools/bank_mcp_design_walk.py then runs the detector and banks the row.
// It never writes to the platform: a design walk reads.
async (mcpPage) => {
  // ★INIT SCRIPTS ACCUMULATE ON THE MCP'S PERSISTENT PAGE (W45845, 2026-09-15): a language init script registered by an
  // earlier walk kept running on every later document, so the Filipino pass rendered English. Each walk runs on a
  // page of its own - fresh init scripts, fresh routes - and closes it; the MCP's own page is left untouched.
  const page = await mcpPage.context().newPage();
  try {
    return await walkOn(page);
  } finally {
    try { await page.close(); } catch (e) { void e; }
  }
  async function walkOn(page) {
  let P = globalThis.__W4 || {};
  try {
    const ar = await page.request.get('http://localhost:5000/workhive/.tmp/w4_args.json', { timeout: 5000 });
    if (ar.ok()) P = Object.assign({}, await ar.json(), P);
  } catch (e) { void e; }
  const origin = P.origin || 'http://localhost:5000/workhive';
  const LANG = P.lang || 'en';
  const VPS = [{ name: 'phone-390', w: 390, h: 844 }, { name: 'desktop-1280', w: 1280, h: 800 }];
  const out = { id: P.id, page: P.page, lens: P.lens, steps: [], problems: [] };
  if (!P.page) { out.problems.push('no page in .tmp/w4_args.json'); return out; }
  // the overlap/occlusion audit, re-armed from the served file when its sha moves (as the nav-hub walker does)
  try {
    const ar = await page.request.get(`${origin}/tools/phone_fit_audit.browser.js`, { timeout: 5000 });
    if (ar.ok()) {
      const body = await ar.text();
      const sha = (body.match(/\(sha ([0-9a-f]{6,})\)/) || [])[1] || String(body.length);
      if (page.__w4AuditSha !== sha) { await page.addInitScript({ content: body }); page.__w4AuditSha = sha; }
    }
  } catch (e) { void e; }
  try { if (typeof page.unrouteAll === 'function') await page.unrouteAll({ behavior: 'ignoreErrors' }); } catch (e) { void e; }

  const read = () => page.evaluate(() => ({ url: location.pathname.split('/').pop(), worker: localStorage.getItem('wh_last_worker'), lang: document.documentElement.lang, chars: (document.body.innerText || '').replace(/\s+/g, ' ').trim().length }));
  const A = async (step) => page.evaluate((s) => { if (!window.__W4_AUDIT) return { step: s, error: 'audit not installed', findings: 0 }; const r = window.__W4_AUDIT(null, { step: s }); return Object.assign({ step: s }, r); }, step);
  const compact = (f) => f ? { findings: f.findings || 0, occlusion: (f.occlusion || []).slice(0, 4), overflowEl: (f.overflowEl || []).slice(0, 2), wrapped: (f.wrapped || []).slice(0, 2), outside: (f.outside || []).slice(0, 2), error: f.error } : { findings: 0 };
  // the live measures every lens reads from the RENDERED page (the detector reads the source; this reads the eyes)
  const measure = () => page.evaluate(() => {
    const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
    const texts = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) { if (!n.nodeValue.trim()) continue; const el = n.parentElement; if (!el || !vis(el)) continue; if (/^(SCRIPT|STYLE|NOSCRIPT)$/.test(el.tagName)) continue; const cs = getComputedStyle(el); texts.push({ px: parseFloat(cs.fontSize), fam: (cs.fontFamily || '').split(',')[0].replace(/["']/g, '').trim(), t: n.nodeValue.trim().slice(0, 40) }); }
    const under11 = texts.filter((t) => t.px < 11), under12 = texts.filter((t) => t.px < 12);
    const ctl = [...document.querySelectorAll('button, a[href], input, select, textarea, [role="button"], [role="tab"]')].filter(vis);
    const small = ctl.filter((e) => { const r = e.getBoundingClientRect(); return r.width < 44 || r.height < 44; });
    const all = [...document.querySelectorAll('body *')].filter(vis);
    const motion = []; for (const e of all) { const cs = getComputedStyle(e); const slow = (cs.transitionDuration || '0s').split(',').some((d) => parseFloat(d) > 0.3); const easeIn = /(^|,)\s*ease-in\s*(,|$)/.test(cs.transitionTimingFunction || ''); const anim = cs.animationName && cs.animationName !== 'none'; if (slow || easeIn || anim) motion.push({ el: e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : ''), slow, easeIn, anim: anim ? cs.animationName : null }); }
    const para = [...document.querySelectorAll('main p, article p, section p, p')].filter(vis).sort((a, b) => b.textContent.length - a.textContent.length)[0];
    let measureCh = 0; if (para) { const r = para.getBoundingClientRect(); measureCh = Math.round(r.width / (parseFloat(getComputedStyle(para).fontSize) * 0.55)); }   // Poppins "0" is ~0.55em: the ch unit, not half an em
    // the words a person reads on the controls and in the page's states - the copy lens's evidence (en and fil walks)
    const controlNames = ctl.slice(0, 40).map((e) => (e.getAttribute('aria-label') || e.value || e.textContent || e.getAttribute('placeholder') || '').replace(/\s+/g, ' ').trim().slice(0, 40)).filter(Boolean);
    // ★THIS COLLECTOR MANUFACTURED A RUN-TOGETHER (2026-09-18, W46038). Reading textContent here made
    // shift-brain's verdict report "Kayang-kaya ang shift, may ilang priority2 PM." and sent me hunting
    // a fourth Label-in-Name defect. Measured: the <small> is display:block, innerText carries the line
    // break ("...priority\n2 PM."), the two lines sit 21.6px apart, and NO ancestor has a role, an
    // aria-live or an aria-label — so nothing computes an accessible name over that subtree and no
    // reader ever hears them joined. textContent is the wrong instrument for a claim about what a page
    // READS LIKE; innerText is the rendered text, and a block boundary survives it as whitespace. Real
    // run-togethers (inline siblings with no separator) still report joined, which is the point.
    // controlNames above is deliberately NOT changed: an accessible NAME is computed from flattened
    // text, so textContent is the right instrument there.
    const _rendered = (e) => (typeof e.innerText === 'string' && e.innerText) || e.textContent || '';
    const stateTexts = [...document.querySelectorAll('[role="alert"], [role="status"], .empty-note, .verdict-text, .action-card, [id*="empty"], [class*="empty"], [class*="error"]')].filter(vis).map((e) => _rendered(e).replace(/\s+/g, ' ').trim().slice(0, 90)).filter(Boolean).slice(0, 12);
    // THE LEVEL A SCREEN READER ANNOUNCES, NOT THE TAG (2026-09-16). aria-level overrides the implicit
    // level for assistive tech and for axe, and this codebase uses it deliberately - the learn articles
    // style their TOC label and CTA heading as <h4> and declare the real outline with aria-level="2"/"3"
    // (tools/fix_learn_heading_order.py). Reading the tag alone reported 2 skips on a page whose outline
    // is continuous, which is the same mistake the static detector made on 69 findings.
    const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(vis).map((h) => { const a = parseInt(h.getAttribute('aria-level'), 10); return (a >= 1 && a <= 6) ? a : +h.tagName[1]; }); let skips = 0; for (let i = 1; i < hs.length; i++) if (hs[i] > hs[i - 1] + 1) skips++;
    const fams = {}; for (const t of texts) fams[t.fam] = (fams[t.fam] || 0) + 1;
    // live contrast (the craft floor: body >= 4.5:1, large text >= 3:1) - the effective background is the first
    // ancestor with an opaque background-color; a gradient or an image is read as the page ground (#162032)
    const lum = (r, g, b) => { const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
    const rgb = (str) => { const m = /rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/.exec(str || ''); return m ? [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]] : null; };
    const ground = [22, 32, 50];
    // a gradient background is read at its FIRST colour stop (the amber CTA is amber, not the page ground)
    const bgOf = (el) => { let e = el; while (e && e !== document.documentElement) { const cs = getComputedStyle(e); const c = rgb(cs.backgroundColor); if (c && c[3] >= 0.95) return c.slice(0, 3); if (c && c[3] > 0) { return [0, 1, 2].map((i) => Math.round(c[i] * c[3] + ground[i] * (1 - c[3]))); } if (cs.backgroundImage && cs.backgroundImage !== 'none') { const g = rgb(cs.backgroundImage); if (g && g[3] >= 0.5) return g.slice(0, 3); return ground; } e = e.parentElement; } return ground; };
    const low = []; let gradText = 0; const gradSample = [];
    const w2 = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n2; let sampled = 0;
    while ((n2 = w2.nextNode()) && sampled < 400) { if (!n2.nodeValue.trim()) continue; const el = n2.parentElement; if (!el || !vis(el) || /^(SCRIPT|STYLE|NOSCRIPT)$/.test(el.tagName)) continue; sampled++; const cs = getComputedStyle(el); const fg = rgb(cs.color); if (!fg) continue;
      // GRADIENT-CLIPPED TEXT IS PAINTED BY ITS BACKGROUND, NOT BY `color` (2026-09-16). With
      // -webkit-text-fill-color: transparent + background-clip: text, `color` is never painted, so comparing it
      // against the backdrop measures a colour pair that does not exist. learn/index.html's h1 span reported
      // 2.07:1 "white on rgb(247,162,27)"; live, its fill is rgba(0,0,0,0) and the amber gradient renders on
      // #162032 at 7.8:1. Counted separately rather than dropped - a gradient heading is still a taste question
      // the slop lens owns, and silence would hide it.
      if (/transparent|rgba\(0, 0, 0, 0\)/.test(cs.webkitTextFillColor || '') && /text/.test(cs.webkitBackgroundClip || cs.backgroundClip || '')) { gradText++; if (gradSample.length < 4) gradSample.push(`${Math.round(parseFloat(cs.fontSize))}px "${n2.nodeValue.trim().slice(0, 24)}"`); continue; }
      const bg = bgOf(el); const fgc = fg[3] < 1 ? [0, 1, 2].map((i) => Math.round(fg[i] * fg[3] + bg[i] * (1 - fg[3]))) : fg; const L1 = lum(...fgc), L2 = lum(...bg); const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05); const px = parseFloat(cs.fontSize); const bold = parseInt(cs.fontWeight, 10) >= 700; const large = px >= 24 || (px >= 18.66 && bold); const floor = large ? 3 : 4.5; if (ratio < floor) low.push({ t: n2.nodeValue.trim().slice(0, 28), ratio: Math.round(ratio * 100) / 100, px, fg: cs.color, bg: `rgb(${bg.join(',')})` }); }
    const contrastLow = low.length; const contrastSample = low.slice(0, 4).map((x) => `${x.ratio}:1 "${x.t}" ${x.px}px ${x.fg} on ${x.bg}`);
    // the craft lens (impeccable craft-floor Verify): the type ramp and weights actually rendered, the spacing rhythm
    // (share of vertical margins/paddings on the 4px grid), depth (a bordered rounded box inside another), and
    // numerals that would jitter (a digit-bearing node without tabular figures)
    const ramp = {}; const wts = {}; for (const t of texts) { const k = String(Math.round(t.px * 10) / 10); ramp[k] = (ramp[k] || 0) + 1; }
    const wtEls = [...document.querySelectorAll('body *')].filter(vis).filter((e) => [...e.childNodes].some((c) => c.nodeType === 3 && c.nodeValue.trim()));
    for (const e of wtEls) { const wv = getComputedStyle(e).fontWeight; wts[wv] = (wts[wv] || 0) + 1; }
    let onGrid = 0, offGrid = 0; const offBy = {};
    for (const e of all.slice(0, 1500)) { const cs = getComputedStyle(e); for (const prop of ['marginTop', 'marginBottom', 'paddingTop', 'paddingBottom']) { const v = parseFloat(cs[prop]); if (!v) continue; if (Math.abs(v / 4 - Math.round(v / 4)) < 0.01 || Math.abs(v / 2 - Math.round(v / 2)) < 0.01 && v < 8) onGrid++; else { offGrid++; const k = `${e.tagName.toLowerCase()}${e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : (e.id ? '#' + e.id : '')} ${prop} ${Math.round(v * 10) / 10}px`; offBy[k] = (offBy[k] || 0) + 1; } } }
    const offSample = Object.entries(offBy).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([k, c]) => `${k} x${c}`);   // the off-grid rules, by count - a fix is a rule, not an element
    const isCard = (e) => { const cs = getComputedStyle(e); const rad = parseFloat(cs.borderTopLeftRadius) || 0; const bordered = cs.borderTopStyle !== 'none' && parseFloat(cs.borderTopWidth) > 0; const bg = rgb(cs.backgroundColor); return rad >= 8 && (bordered || (bg && bg[3] > 0)); };
    const cards = all.filter(isCard); let nested = 0; const nestedSample = [];
    for (const c of cards) { let a = c.parentElement; while (a && a !== document.body) { if (isCard(a) && a.tagName !== 'BUTTON' && c.tagName !== 'BUTTON' && !/^(A|SPAN|SMALL|LABEL)$/.test(c.tagName)) { nested++; if (nestedSample.length < 4) nestedSample.push(`${c.tagName.toLowerCase()}${typeof c.className === 'string' && c.className ? '.' + c.className.split(' ')[0] : ''} in ${a.tagName.toLowerCase()}${typeof a.className === 'string' && a.className ? '.' + a.className.split(' ')[0] : ''}`); break; } a = a.parentElement; } }
    let numNodes = 0, numNoTab = 0; const numSample = [];
    for (const t of texts) { if (!/\d{2,}/.test(t.t)) continue; numNodes++; }
    // A NUMERAL DISPLAY IS DIGIT-DOMINANT (2026-09-16): a stat tile, a metric readout, a table cell. "contains 2+
    // digits at >=20px" is not that - on free-engineering-calculators it flagged 7 HEADINGS ("All 60 calculators",
    // "Electrical & Power (15)", "Worked example: HVAC duct sizing for a 100 kW office cooling load"), 2-4 digits
    // against 11-68 letters each. Tabular figures align columns and stop a live number jittering; inside a sentence
    // they align nothing, so the flag would have bought an edit that made the prose worse. Digits >= letters in the
    // element's OWN text keeps "1,240 hrs" and "67/100" and drops every heading that merely carries a count.
    const ownText = (e) => [...e.childNodes].filter((c) => c.nodeType === 3).map((c) => c.nodeValue).join(' ');
    const numEls = wtEls.filter((e) => { const t = ownText(e); return /\d{2,}/.test(t) && (t.match(/\d/g) || []).length >= (t.match(/[A-Za-z]/g) || []).length; });
    for (const e of numEls) { const fv = getComputedStyle(e).fontVariantNumeric || ''; const ff = getComputedStyle(e).fontFeatureSettings || ''; if (!/tabular/.test(fv) && !/tnum/.test(ff)) { const big = parseFloat(getComputedStyle(e).fontSize) >= 20; if (big) { numNoTab++; if (numSample.length < 4) numSample.push(`${Math.round(parseFloat(getComputedStyle(e).fontSize))}px "${e.textContent.replace(/\s+/g, ' ').trim().slice(0, 24)}"`); } } }
    const craft = { typeRamp: Object.entries(ramp).sort((a, b) => +a[0] - +b[0]).map(([k, c]) => `${k}px x${c}`), rampSizes: Object.keys(ramp).length,
      weights: Object.entries(wts).sort((a, b) => +a[0] - +b[0]).map(([k, c]) => `${k} x${c}`),
      rhythmOnGrid: onGrid, rhythmOffGrid: offGrid, rhythmOffSample: offSample, cards: cards.length, nestedCards: nested, nestedSample,
      bigNumerals: numEls.filter((e) => parseFloat(getComputedStyle(e).fontSize) >= 20).length, bigNumeralsNotTabular: numNoTab, bigNumeralsSample: numSample };
    return { textNodes: texts.length, minFontPx: texts.length ? Math.min(...texts.map((t) => t.px)) : 0,
      under11: under11.length, under11Sample: under11.slice(0, 4).map((t) => `${t.px}px "${t.t}"`),
      under12: under12.length, controls: ctl.length, tapUnder44: small.length,
      tapUnder44Sample: small.slice(0, 4).map((e) => { const r = e.getBoundingClientRect(); return `${e.tagName.toLowerCase()} "${(e.getAttribute('aria-label') || e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 24)}" ${Math.round(r.width)}x${Math.round(r.height)}`; }),
      motion: motion.length, motionSample: motion.slice(0, 5), bodyMeasureCh: measureCh, headings: hs.length, headingSkips: skips,
      contrastLow, contrastSample, contrastSampled: sampled, gradientText: gradText, gradientTextSample: gradSample, controlNames, stateTexts,
      fonts: Object.entries(fams).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([f, c]) => `${f} x${c}`),
      craft,
      spill: document.documentElement.scrollWidth - innerWidth, innerW: innerWidth, h1: (document.querySelector('h1') || {}).textContent ? document.querySelector('h1').textContent.replace(/\s+/g, ' ').trim().slice(0, 60) : '' };
  });
  const atPath = (h) => new RegExp('/' + h.split('.').join('[.]') + '(?:[?#]|$)');
  const gated = !/^(index|about|feedback|privacy-policy|terms-of-service)/.test(P.page) && !/^(tools|learn)\//.test(P.page) && P.gated !== false;

  // ── measure the SHIPPED shell, not the one this browser installed last time ───────────────────
  // ★THE SERVICE WORKER SERVED THE PREVIOUS WALK'S SHELL (2026-09-15, W45839 x3): utils.js edits made after a
  // CACHE_NAME bump kept measuring at the old values (9px avatar numbers) because the MCP's persistent browser held
  // the precache the bump had installed, and the next bump's install lands AFTER the pages this walk audits. A
  // design lens judges the page as shipped, so the walker unregisters the worker and drops its caches first; the
  // worker re-registers on the next load and installs the current shell. (The nav-hub / fit walks keep the
  // installed shell on purpose - that is what a person mid-update sees; C28 is verified by its own predicate.)
  // ...and through CDP FIRST, on the blank page, so the first navigation is never intercepted by a worker mid-update:
  // two 1800 s hangs today (W45854, W45855) began at this goto, each right after sw.js changed, at 0.33 GB free.
  try { const cdp0 = await page.context().newCDPSession(page); await cdp0.send('Storage.clearDataForOrigin', { origin: origin.replace(/\/workhive\/?$/, ''), storageTypes: 'service_workers,cache_storage' }); out.cdpReset = 'ok'; }
  catch (e) { out.cdpReset = String(e.message || e).slice(0, 60); }
  await page.goto(`${origin}/index.html`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  try {
    const reset = await page.evaluate(async () => {
      const rs = navigator.serviceWorker ? await navigator.serviceWorker.getRegistrations() : [];
      await Promise.all(rs.map((r) => r.unregister()));
      const ks = (typeof caches !== 'undefined') ? await caches.keys() : [];
      await Promise.all(ks.map((k) => caches.delete(k)));
      return { workers: rs.length, caches: ks.length };
    });
    out.shellReset = reset;
  } catch (e) { out.problems.push('could not reset the service worker: ' + String(e.message || e).slice(0, 80)); }
  // ...and the browser's own HTTP cache, which the seeder's cache headers can keep for an hour after the worker is gone
  try { const cdp = await page.context().newCDPSession(page); await cdp.send('Network.setCacheDisabled', { cacheDisabled: true }); out.httpCache = 'disabled'; }
  catch (e) { out.httpCache = 'could not disable: ' + String(e.message || e).slice(0, 60); }
  // ── arrive as the person, at phone-390 first ─────────────────────────────────────────────────
  await page.setViewportSize({ width: 390, height: 844 });
  // ★THE LANGUAGE IS SET, NEVER ASSUMED (W45845, 2026-09-15): the copy lens's Filipino pass left wh_lang=fil in this
  // persistent browser and the next English-axis walk measured a Filipino page. Every walk writes its own axis's
  // language before the first load, whichever it is, and records the language the page actually rendered.
  // (an extra-language pass sets a sessionStorage lock so this init script stops re-asserting the axis language)
  await page.addInitScript((l) => { try { if (sessionStorage.getItem('w4_lang_lock') !== '1') localStorage.setItem('wh_lang', l); } catch (e) { void e; } }, LANG);
  await page.evaluate((l) => { try { sessionStorage.removeItem('w4_lang_lock'); localStorage.setItem('wh_lang', l); } catch (e) { void e; } }, LANG).catch(() => {});
  if (gated) {
    await page.goto(`${origin}/index.html?signin=1&return=${P.page}`, { waitUntil: 'load' });
    await page.waitForSelector('#si-username', { state: 'visible', timeout: 45000 }).catch(() => {});
    const wall = await page.locator('#si-username').isVisible().catch(() => false);
    if (wall) {
      const wr = await read();
      out.steps.push({ page: 'index.html', chars: wr.chars, identityKept: true, lang: wr.lang, fit: compact(await A('index.html wall at phone-390')) });
      await page.fill('#si-username', P.user || 'christinedizon', { timeout: 8000 });
      await page.fill('#si-password', P.pass || 'test1234', { timeout: 8000 });
      await page.click('#si-btn', { timeout: 10000 }).catch(async () => { out.problems.push('the sign-in submit did not become clickable in 10s; pressed Enter instead'); await page.press('#si-password', 'Enter', { timeout: 4000 }).catch(() => {}); });
      try { await page.waitForURL(atPath(P.page), { timeout: 25000 }); }
      catch (e) { out.problems.push('sign-in did not reach the page in 25s: ' + await page.evaluate(() => (document.querySelector('#signin-modal') || {}).innerText || '').then((t) => String(t).replace(/\s+/g, ' ').slice(0, 120))); return out; }
    } else if (!atPath(P.page).test(page.url())) {
      await page.goto(`${origin}/${P.page}`, { waitUntil: 'load' });
    }
  } else {
    await page.goto(`${origin}/${P.page}`, { waitUntil: 'load' });
  }
  if (LANG === 'fil') await page.goto(`${origin}/${P.page}`, { waitUntil: 'load' });
  await page.waitForTimeout(4000);
  let r = await read(); let looks = 0;
  while (r.chars < 300 && looks < 3) { await page.waitForTimeout(3000); r = await read(); looks++; }

  // ── the batched round: both viewports, same context ────────────────────────────────────────
  for (const vp of VPS) {
    await page.setViewportSize({ width: vp.w, height: vp.h });
    await page.waitForTimeout(1500);
    await page.evaluate(() => window.scrollTo(0, 0));
    const vw = await page.evaluate(() => innerWidth);
    if (vw !== vp.w) { out.problems.push(`viewport is ${vw} CSS px, not ${vp.w}`); }
    r = await read();
    const fit = compact(await A(`${P.page} at ${vp.name}`));
    const m = await measure();
    let shot = null;
    if (P.shotDir) { shot = `${P.shotDir}/${P.id}_${vp.name}.png`; try { await page.screenshot({ path: shot, fullPage: true, timeout: 20000 }); } catch (e) { out.problems.push(`screenshot at ${vp.name} failed: ${String(e.message || e).slice(0, 80)}`); shot = null; } }
    out.steps.push({ page: P.page, viewport: vp.name, chars: r.chars, identityKept: gated ? r.worker === (P.castName || 'Christine Dizon') : true, lang: r.lang, fit, measures: m, screenshot: shot });
  }
  // the ONWARD HOP - a public page's second page (2026-09-16). A gated walk arrives through the sign-in wall and
  // records it; a calculator or a learn article is reached by a link someone shared, so nothing precedes it. The
  // design lens still needs more than one page in the receipt, and the honest one is where this page's OWN public
  // navigation goes next - which is also what the row's story says ("through the platform's own navigation").
  // Read off the RENDERED page, followed, and measured; never asserted. Recording the index.html load the walker
  // performs to drop the stale service worker would describe a walk mechanic as the person's journey.
  if (!gated) {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(600);
    // ★A ROOT-ABSOLUTE LINK MEANS "THIS SITE'S /x", AND LOCALLY THAT IS /workhive/x (2026-09-16, W46283). These
    // pages are written for production, where the site IS the origin root; the harness mounts the app under
    // /workhive/ and answers the bare origin with its own dev console. Following `href="/"` verbatim loaded
    // <title>WorkHive Test Seeder</title> and the step would have been written up as index.html - a receipt
    // naming a page of the product, measured on a test harness. The link is resolved against the app's BASE,
    // the raw href is kept beside it, and the hop is then VERIFIED rather than assumed.
    const section = (P.page.indexOf('/') > 0) ? P.page.slice(0, P.page.indexOf('/') + 1) : '';
    const onward = await page.evaluate((here) => {
      const bad = /^(#|mailto:|tel:|javascript:)/i;
      const found = [];
      for (const a of [...document.querySelectorAll('a[href]')]) {
        const r = a.getBoundingClientRect(); const cs = getComputedStyle(a);
        if (!(r.width > 0 && r.height > 0) || cs.visibility === 'hidden' || cs.display === 'none') continue;
        const raw = a.getAttribute('href') || '';
        if (bad.test(raw) || /^https?:/i.test(raw)) continue;      // an absolute URL is the canonical / an outbound
        let u; try { u = new URL(a.href, location.href); } catch (e) { void e; continue; }
        if (u.origin !== location.origin || u.search) continue;    // ?signin=1 / ?signup=1 open the wall, not a page
        let p = u.pathname.replace(/\/$/, '/index.html');
        if (!/[.]html$/.test(p)) continue;                         // /learn-print.css, /manifest.json are not pages
        found.push({ raw, path: p, text: (a.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40) });
      }
      return found;
    }, P.page);
    // the app's own base, and the row's own section first: a calculator's next calculator, an article's next
    // article - the navigation the row's story describes - before the front door
    // the app's base as a STRING - the outer half of this walker runs in the Playwright server process, which has
    // no `URL` global (only page.evaluate bodies run in the browser, where it exists)
    const basePath = origin.replace(/^https?:[/][/][^/]+/, '').replace(/[/]+$/, '') + '/';
    const baseRel = basePath.replace(/^[/]/, '');
    const rels = [];
    for (const f of onward) {
      let rel = f.path.replace(/^\//, '');
      if (baseRel && rel.indexOf(baseRel) === 0) rel = rel.slice(baseRel.length);
      if (rel === P.page) continue;
      rels.push({ rel, raw: f.raw, text: f.text, sameSection: !!section && rel.indexOf(section) === 0 });
    }
    const pick = rels.filter((x) => x.sameSection)[0] || rels[0] || null;
    if (pick) {
      const url = `${origin.replace(/\/$/, '')}/${pick.rel}`;
      let status = 0;
      const resp = await page.goto(url, { waitUntil: 'load', timeout: 30000 }).catch((e) => { out.problems.push('the onward hop to ' + pick.rel + ' did not load: ' + String(e.message || e).slice(0, 80)); return null; });
      if (resp) status = resp.status();
      await page.waitForTimeout(2500);
      // VERIFY it is the app's page and not whatever else the harness answers on that path
      const ident = await page.evaluate(() => {
        const vis = (e) => { if (!e) return false; const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
        return { title: document.title, path: location.pathname, search: location.search,
          // EITHER marker identifies a page of this site: the app's shared chrome, or - for the deliberately
          // self-contained public calculator / article pages, which ship no chrome at all - the canonical link
          // to workhiveph.com. The harness's own dev console carries neither, which is the case this guards.
          shell: !!(document.querySelector('link[rel="canonical"][href*="workhiveph.com"], link[href*="tokens.css"], script[src*="utils.js"], meta[name="theme-color"]')),
          wall: vis(document.querySelector('#si-username')) };
      });
      const ok = status === 200 && ident.path.indexOf(pick.rel.replace(/index[.]html$/, '')) >= 0 && ident.shell;
      // ★THE SIGN-IN WALL IS AN ARRIVAL, NOT A FAILED HOP (2026-09-17, W45923). A PUBLIC page's own navigation
      // routinely points at GATED pages - index.html's tools list links straight to hive.html, logbook.html and
      // the rest - and the product's correct answer to a signed-out visitor following one is to land them on
      // index.html?signin=1&return=<that page> with the wall open and the destination remembered. Measured: the
      // modal is visible, #si-username is focusable, and return=hive.html is preserved. The old check compared
      // only the landed PATH to the requested one, so it wrote the product working as designed up as "did not
      // land on the app" - a problem entry, which refuses the bank. It is a step now, and the step SAYS it is a
      // gate rather than the page. The guard does not widen: the wall must actually be VISIBLE and the return
      // parameter must name the page we asked for, so the case this check exists to catch - a link that silently
      // dumps a visitor back on the home page with no explanation - still fails exactly as before.
      const gateOk = !ok && status === 200 && ident.shell && ident.wall &&
        /(^|[?&])signin=1(&|$)/.test(ident.search) &&
        ident.search.indexOf('return=' + pick.rel) >= 0;
      if (!ok && !gateOk) {
        out.problems.push('the onward hop to ' + pick.rel + ' did not land on the app: HTTP ' + status +
          ' at ' + ident.path + ' "' + String(ident.title).slice(0, 40) + '"' + (ident.shell ? '' : ' (no app shell)'));
      } else if (gateOk) {
        const rg = await read();
        out.steps.push({ page: 'index.html', viewport: 'phone-390', onward: true, onwardFrom: P.page,
          gatedTarget: pick.rel, linkHref: pick.raw, linkText: pick.text, title: ident.title,
          signInWall: true, returnPreserved: pick.rel, chars: rg.chars, identityKept: true, lang: rg.lang,
          fit: compact(await A('the sign-in wall reached by following ' + pick.rel + ' from ' + P.page + ' at phone-390')) });
      } else {
        const ro = await read();
        out.steps.push({ page: pick.rel, viewport: 'phone-390', onward: true, onwardFrom: P.page,
          linkHref: pick.raw, linkText: pick.text, title: ident.title, chars: ro.chars, identityKept: true, lang: ro.lang,
          fit: compact(await A(pick.rel + ' (onward from ' + P.page + ') at phone-390')) });
      }
      await page.goto(`${origin}/${P.page}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
      await page.waitForTimeout(1500);
    } else {
      out.noOnwardLink = true;
    }
  }
  // ── the copy lens's passes: the other language, and the page with its reads ABORTED (harden.md's error handling) ─
  // Each extra pass is a phone-390 step of its own: the words on the controls, the state texts and the notices a person
  // reads in that language / in that failure. Reads are aborted with a route on the Supabase REST + functions paths,
  // never a mutation; the route is removed before the next pass.
  const extra = [];
  if (P.degraded) extra.push({ lang: LANG, degraded: true });
  for (const l of (P.langs || [])) { if (l !== LANG) { extra.push({ lang: l }); if (P.degraded) extra.push({ lang: l, degraded: true }); } }
  for (const x of extra) {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate((l) => { try { sessionStorage.setItem('w4_lang_lock', '1'); localStorage.setItem('wh_lang', l); } catch (e) { void e; } }, x.lang);
    const abortReads = (route) => route.abort();
    if (x.degraded) {
      // the worker re-registered on the first load and would answer the aborted reads from its runtime cache (the
      // offline design working) - a degraded pass must reach the NETWORK failure, so drop the worker again first
      try { await page.evaluate(async () => { const rs = navigator.serviceWorker ? await navigator.serviceWorker.getRegistrations() : []; await Promise.all(rs.map((r) => r.unregister())); const ks = (typeof caches !== 'undefined') ? await caches.keys() : []; await Promise.all(ks.map((k) => caches.delete(k))); }); } catch (e) { void e; }
      await page.route(/\/rest\/v1\/|\/functions\/v1\//, abortReads);
    }
    await page.goto(`${origin}/${P.page}`, { waitUntil: 'load' }).catch(() => {});
    await page.waitForTimeout(x.degraded ? 7000 : 4500);
    await page.evaluate(() => window.scrollTo(0, 0));
    const r2 = await read();
    const fit2 = compact(await A(`${P.page} ${x.lang}${x.degraded ? ' degraded' : ''} at phone-390`));
    const m2 = await measure();
    const notices = await page.evaluate(() => [...document.querySelectorAll('[id$="-notice"], .wh-notice, [role="alert"]')].filter((e) => e.getBoundingClientRect().height > 0).map((e) => e.textContent.replace(/\s+/g, ' ').trim().slice(0, 160)).slice(0, 4));
    let shot2 = null;
    if (P.shotDir) { shot2 = `${P.shotDir}/${P.id}_${x.lang}${x.degraded ? '-degraded' : ''}_phone-390.png`; try { await page.screenshot({ path: shot2, fullPage: true, timeout: 20000 }); } catch (e) { shot2 = null; } }
    out.steps.push({ page: P.page, viewport: 'phone-390', lang: r2.lang, langWalked: x.lang, degraded: !!x.degraded, chars: r2.chars,
      identityKept: gated ? r2.worker === (P.castName || 'Christine Dizon') : true, fit: fit2,
      measures: { under11: m2.under11, contrastLow: m2.contrastLow, spill: m2.spill, controlNames: m2.controlNames, stateTexts: m2.stateTexts, notices, h1: m2.h1 }, screenshot: shot2 });
    if (x.degraded) { try { await page.unroute(/\/rest\/v1\/|\/functions\/v1\//, abortReads); } catch (e) { void e; } }
  }
  if (extra.length) await page.evaluate((l) => { try { sessionStorage.removeItem('w4_lang_lock'); localStorage.setItem('wh_lang', l); } catch (e) { void e; } }, LANG);
  if (out.steps[0]) out.steps[0].problems = out.problems;
  try {
    const base = origin.replace(/\/workhive\/?$/, '');
    const res = await page.request.post(`${base}/api/w4/steps`, { data: { id: P.id || 'walk', steps: out.steps, records: [] } });
    out.wrote = res.ok() ? (await res.json()).path : `POST /api/w4/steps -> ${res.status()}`;
  } catch (e) { out.writeError = String(e.message || e).slice(0, 120); }
  return { id: P.id, page: P.page, lens: P.lens, wrote: out.wrote, writeError: out.writeError, problems: out.problems, shellReset: out.shellReset, httpCache: out.httpCache,
    steps: out.steps.map((s) => ({ page: s.page, viewport: s.viewport || 'arrival', lang: s.langWalked || s.lang, degraded: s.degraded || false, chars: s.chars, identityKept: s.identityKept, findings: s.fit && s.fit.findings, occlusion: s.fit && s.fit.occlusion, overflowEl: s.fit && s.fit.overflowEl, measures: s.measures, screenshot: s.screenshot })) };
}
}
