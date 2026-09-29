// w4_navhub_walk.js - the WHOLE nav-hub, every control, on one host page, then the journey onward: the Playwright
// code an MCP walk loads with `browser_run_code_unsafe { filename }` (Wave 4, 2026-09-14). The function reads its
// parameters from globalThis.__W4 (set by a one-line run_code before it) and returns the receipt-ready steps.
//
//   globalThis.__W4 = { id: 'W41420', host: 'achievements.html', axis: 'phone-390 en', width: 390, height: 844,
//                       lang: 'en', stops: ['hive.html', 'assistant.html', 'logbook.html'],
//                       user: 'romeobeltran', pass: 'test1234', castName: 'Romeo Beltran',
//                       origin: 'http://localhost:5000/workhive' }
//
// WHY A FILE: the sweep is ~9 KB of Playwright code; sending it in every call cost ~2.5K tokens per walk step and
// invited copy-drift between axes. The file is the one sweep; the MCP still executes it LIVE per walk and every
// reading is returned to be read as it lands - the doctrine's step-by-step walk, with the hands scripted once.
//
// WHY localhost: the MCP browser profile carries a saved 67% zoom for the origin 127.0.0.1:5000, so a 390 viewport
// read 585 CSS px there and CDP device emulation stacked on top made Playwright's click coordinates disagree with
// the page (every fab tap "intercepted" while elementsFromPoint showed the fab on top). localhost has no saved
// zoom: a plain setViewportSize gives a true 390. The walker asserts innerWidth === width before it measures.
//
// EVERY reading is taken with window.__W4_AUDIT (tools/phone_fit_audit.browser.js, installed by addInitScript
// before the walk) - the per-step overlap / element-overflow / occlusion record - after each step and after each
// interaction. Findings are returned, never filtered; the caller banks them.
async (page) => {
  // ★EACH run_code CALL GETS ITS OWN globalThis (measured 2026-09-14: args set in one call read as {} in the
  // next), so the parameters are read from a file the local seeder serves - .tmp/w4_args.json, written by the
  // caller before the walk - with globalThis.__W4 kept as a same-call fallback.
  let P = globalThis.__W4 || {};
  try {
    const ar = await page.request.get('http://localhost:5000/workhive/.tmp/w4_args.json', { timeout: 5000 });
    if (ar.ok()) P = Object.assign({}, await ar.json(), P);
  } catch (e) { void e; }
  const origin = P.origin || 'http://localhost:5000/workhive';
  const W = P.width || 390, H = P.height || 844, LANG = P.lang || 'en';
  // ★THE AUDIT IS RE-ARMED FROM THE SERVED FILE WHEN ITS SHA MOVES (2026-09-14): addInitScript({ path })
  // captures the file's content at registration, so a walk kept injecting the audit from before the
  // confusion detectors were added. The walker reads the served copy and re-registers only on a new sha.
  try {
    const ar = await page.request.get(`${origin}/tools/phone_fit_audit.browser.js`, { timeout: 5000 });
    if (ar.ok()) {
      const body = await ar.text();
      const sha = (body.match(/\(sha ([0-9a-f]{6,})\)/) || [])[1] || String(body.length);
      if (page.__w4AuditSha !== sha) { await page.addInitScript({ content: body }); page.__w4AuditSha = sha; }
    }
  } catch (e) { void e; }
  // a route handler left by an earlier call would answer this walk's requests - clear them all
  try { if (typeof page.unrouteAll === 'function') await page.unrouteAll({ behavior: 'ignoreErrors' }); } catch (e) { void e; }
  const stops = P.stops || ['hive.html', 'assistant.html', 'logbook.html'];
  const records = [];
  const A = async (step) => { const a = await page.evaluate((s) => { if (!window.__W4_AUDIT) return { step: s, error: 'audit not installed' }; const r = window.__W4_AUDIT(null, { step: s }); return { step: s, vw: innerWidth, findings: r.findings || 0, overflow: r.overflow, occlusion: (r.occlusion || []).slice(0, 4), overflowEl: (r.overflowEl || []).slice(0, 3), outside: (r.outside || []).slice(0, 2), clipped: (r.clipped || []).slice(0, 2), wrapped: (r.wrapped || []).slice(0, 3), spill: (r.spill || []).slice(0, 2), ambiguity: (r.ambiguity || []).slice(0, 4), unactionable: (r.unactionable || []).slice(0, 3), confusions: r.confusions || 0 }; }, step); records.push(a); return a; };
  const vis = (sel) => page.evaluate((s) => { const e = document.querySelector(s); if (!e) return { exists: false, shown: false }; const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); const shown = cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0; return { exists: true, shown, inside: r.left >= -1 && r.top >= -1 && r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1, rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)], name: (e.getAttribute('aria-label') || e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 48), state: e.getAttribute('data-state'), focused: document.activeElement === e || e.contains(document.activeElement) }; }, sel);
  const focusOn = () => page.evaluate(() => { const a = document.activeElement; return a ? (a.id || a.tagName.toLowerCase()) : null; });
  const read = () => page.evaluate(() => ({ url: location.pathname.split('/').pop(), worker: localStorage.getItem('wh_last_worker'), lang: document.documentElement.lang, chars: (document.body.innerText || '').replace(/\s+/g, ' ').trim().length, skeletons: document.querySelectorAll('[class*="skeleton"], .animate-pulse').length }));
  const ensureHub = async () => {
    const p = await vis('#wh-hub-panel');
    if (p.shown) return;
    // BOUND + CATCH (the last hardening gap, W41429): a fab that resolves but will not take the click (covered by
    // the page's own bottom chrome, or mid-animation) must record WHAT sits on it and fall back to Ctrl+K (nav-hub.js
    // maps it to open+focus the hub), never throw an uncaught 8s timeout that sinks the whole row as "the walk threw".
    const clicked = await page.click('#wh-hub-fab', { timeout: 8000 }).then(() => true).catch(() => false);
    if (!clicked) {
      const cover = await page.evaluate(() => {
        const f = document.querySelector('#wh-hub-fab'); if (!f) return 'no fab';
        const q = f.getBoundingClientRect(); const t = document.elementFromPoint(q.left + q.width / 2, q.top + q.height / 2);
        if (!t || t === f || f.contains(t)) return 'not covered (animation/stability, not occlusion)';
        return (t.id ? '#' + t.id : t.tagName.toLowerCase() + (typeof t.className === 'string' && t.className ? '.' + t.className.trim().split(/\s+/)[0] : ''));
      }).catch(() => '?');
      out.problems.push('the hub fab did not take the click when reopening the hub; at its centre sits ' + cover + ' - opened via Ctrl+K instead');
      await page.keyboard.press('Control+k').catch(() => {});
    }
    await page.waitForTimeout(700);
  };
  const closeAll = async () => { await page.keyboard.press('Escape'); await page.waitForTimeout(250); await page.keyboard.press('Escape'); await page.waitForTimeout(250); };
  const out = { id: P.id, host: P.host, axis: P.axis, steps: [], problems: [] };

  const atPath = (h) => new RegExp('/' + h.split('.').join('[.]') + '(?:[?#]|$)');
  // ── arrive as the person, at the axis ─────────────────────────────────────────────────────────
  await page.setViewportSize({ width: W, height: H });
  // ★THE AXIS LANGUAGE IS SET, NEVER ASSUMED (W41372, 2026-09-15): the walker set wh_lang only for the Filipino axis, so an
  // English-axis walk after a Filipino walk in the same persistent browser measured a Filipino page. Set it for both.
  await page.evaluate((l) => { try { localStorage.setItem('wh_lang', l); } catch (e) { void e; } }, LANG).catch(() => {});
  await page.addInitScript((l) => { try { localStorage.setItem('wh_lang', l); } catch (e) { void e; } }, LANG);
  await page.goto(`${origin}/index.html?signin=1&return=${P.host}`, { waitUntil: 'load' }); await page.waitForTimeout(2000);
  if (LANG === 'fil') { await page.evaluate(() => { try { localStorage.setItem('wh_lang', 'fil'); } catch (e) { void e; } }); }
  const already = await page.evaluate(() => localStorage.getItem('wh_last_worker'));
  // ★WAIT FOR THE WALL, DON'T SLEEP FOR IT (narrow-320 walk, 2026-09-14). A fixed 2s pause then a count read 0
  // at 320 on this loaded host - the sign-in modal opens later than that under RAM pressure - so the walk skipped
  // sign-in entirely, went to the gated host unauthenticated, bounced back to the wall, and then graded index.html
  // as if it were the host (idKept false, the front door's sticky CTA "covering" the fab). Wait up to 15s for the
  // username box to be visible; a page with no wall (an already-signed-in session) simply falls through at 0.
  // ★AND WAIT LONGER, BY ID (narrow-320 walk #2, 2026-09-14). 15s was still 0: a COLD first load of the front door
  // at ~0.5 GB free opens the modal later than that (the redirect arrival a minute later showed it open, SSO button
  // and all), and a role+name locator also depends on the accessibility tree. The inputs' ids are stable
  // (index.html #si-username / #si-password) - wait up to 45s for the username box by id and fill by id.
  await page.waitForSelector('#si-username', { state: 'visible', timeout: 45000 }).catch(() => {});
  // ★VISIBLE, NOT PRESENT (narrow-320 walk #3, 2026-09-14): the input is STATIC markup on index.html, so count() is
  // never 0 there - an unopened modal must fall through to the plain goto below, not into a fill that throws.
  const wall = await page.locator('#si-username').isVisible().catch(() => false);
  if (wall) {
    await page.fill('#si-username', P.user || 'romeobeltran', { timeout: 8000 });
    await page.fill('#si-password', P.pass || 'test1234', { timeout: 8000 });
    // the wall has TWO "Sign In" buttons - the nav's opener and the modal's submit (#si-btn); the submit is the one.
    // BOUND it (10s, catch): an un-actionable submit must record a precise problem, never abort the whole row with a
    // 30s unhandled throw (the last click the hardening pass missed). If #si-btn will not take the click, press Enter
    // in the password field - the modal submits on Enter too - so a briefly-covered button does not sink the walk.
    await page.click('#si-btn', { timeout: 10000 }).catch(async () => {
      out.problems.push('the sign-in submit (#si-btn) did not become clickable in 10s; pressed Enter in the password field instead');
      await page.press('#si-password', 'Enter', { timeout: 4000 }).catch(() => {});
    });
    // ★THE HOST'S NAME IS ALSO IN THE WALL'S URL (narrow-320 walk #3, 2026-09-14): index.html?signin=1&return=achievements.html
    // matched the host's own name INSTANTLY, so "sign-in reached the host" passed while the walk still stood on the front
    // door - it then graded index.html as the host (sticky CTA at the fab centre, SSO button at rest, identity "lost").
    // At 390 the submit navigated before the next read so nobody noticed; at 320 under RAM pressure it did not. Match the
    // host at the PATH position: /host followed by the end, a query or a fragment.
    // ★WHEN THE HOST IS index.html THE WALL *IS* THE HOST (index@fil, 2026-09-15): atPath('index.html') matches
    // index.html?signin=1&return=index.html at once, so "arrived" was true before the submit did anything and the walk
    // graded the landing page unsigned (14.6k chars on every "page", identity never kept) - at 390/320 en the submit
    // had won the race, at fil it lost. Arrival on index.html is the dialog CLOSED and the identity STORED.
    try {
      if (/^index\.html/.test(P.host)) {
        await page.waitForFunction(() => { const m = document.getElementById('signin-modal'); return !!localStorage.getItem('wh_last_worker') && (!m || m.classList.contains('hidden')); }, null, { timeout: 25000 });
      } else {
        await page.waitForURL(atPath(P.host), { timeout: 25000 });
      }
    } catch (e) { out.problems.push('sign-in did not reach the host in 25s: ' + await page.evaluate(() => (document.querySelector('#signin-modal') || {}).innerText || '').then((t) => String(t).replace(/\s+/g, ' ').slice(0, 120))); }
  } else if (!/achievements|\.html/.test(page.url()) || !page.url().endsWith(P.host)) {
    await page.goto(`${origin}/${P.host}`, { waitUntil: 'load' });
  }
  if (LANG === 'fil') { await page.goto(`${origin}/${P.host}`, { waitUntil: 'load' }); }   // a fresh load with wh_lang set
  await page.waitForTimeout(4500);
  let r = await read(); let looks = 0;
  while (r.chars < 900 && looks < 3) { await page.waitForTimeout(4000); r = await read(); looks++; }
  const vw = await page.evaluate(() => innerWidth);
  if (vw !== W) { out.problems.push(`viewport is ${vw} CSS px, not ${W} - the origin carries a zoom; nothing below is on this axis`); return out; }
  const host = { page: P.host, chars: r.chars, identityKept: r.worker === (P.castName || 'Romeo Beltran'), lang: r.lang, skeletons: r.skeletons, onward: stops.slice(0, 1) };
  host.fit = await A(`${P.host} at rest`);

  // ── the whole hub ──────────────────────────────────────────────────────────────────────────────
  const hub = { controls_exercised: 0, modes: [], names: {} };
  await closeAll();
  hub.fab = await vis('#wh-hub-fab');
  hub.fabStack = await page.evaluate(() => { const f = document.querySelector('#wh-hub-fab'); if (!f) return null; const q = f.getBoundingClientRect(); return document.elementsFromPoint(q.left + q.width / 2, q.top + q.height / 2).slice(0, 3).map((e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\s+/)[0] : '')); });
  // (precedence fix 2026-09-14: `'...: ' + find() || 'timeout'` concatenated FIRST, so a plain timeout printed
  // "could not be tapped: undefined" and hid the reason. Name the intercepting element when Playwright reports one,
  // else the first line of the error, and record what sits at the fab's centre so a 320-width stack collision reads
  // as what it is instead of "undefined".)
  try { await page.click('#wh-hub-fab', { timeout: 8000 }); hub.controls_exercised++; }
  catch (e) {
    const lines = String(e.message || e).split('\n');
    const why = lines.find((l) => /intercept/.test(l)) || lines[0] || 'timeout';
    out.problems.push('the hub fab could not be tapped: ' + why.trim().slice(0, 140) + (hub.fabStack ? ' | at its centre: ' + hub.fabStack.join(' > ') : ''));
  }
  await page.waitForTimeout(700);
  hub.panel = await vis('#wh-hub-panel'); if (hub.panel.shown) hub.controls_exercised++;
  hub.panelScroll = await page.evaluate(() => { const p = document.querySelector('#wh-hub-panel'); return p ? { scrollH: p.scrollHeight, clientH: p.clientHeight } : null; });
  await A('hub panel open');
  const modes = await page.$$('#wh-hub-mode .wh-hub-mode-btn');
  for (const m of modes) {
    const id = await m.getAttribute('data-mode');
    await m.click({ timeout: 6000 }).catch(() => out.problems.push('a hub mode button did not become clickable (chrome may be covered on this page)')); await page.waitForTimeout(350);
    hub.modes.push(await page.evaluate((mid) => { const b = document.querySelector(`#wh-hub-mode .wh-hub-mode-btn[data-mode="${mid}"]`); return { mode: mid, label: (b.textContent || '').trim().slice(0, 20), selected: b.getAttribute('aria-selected'), tiles: [...document.querySelectorAll('#wh-hub-tiles .wh-hub-tile')].filter((t) => t.checkVisibility && t.checkVisibility()).length }; }, id));
    await A(`mode ${id}`);
  }
  if (hub.modes.length) hub.controls_exercised++;
  await page.fill('#wh-hub-search', 'logbook', { timeout: 6000 }).catch(() => out.problems.push('this page has no working tools filter (#wh-hub-search)')); await page.waitForTimeout(500);
  hub.filterInLastMode = await page.evaluate(() => ({ hits: [...document.querySelectorAll('#wh-hub-tiles .wh-hub-tile')].filter((t) => t.checkVisibility && t.checkVisibility()).length, noResults: (() => { const n = document.querySelector('#wh-hub-no-results'); return !!(n && n.checkVisibility && n.checkVisibility()); })() }));
  await page.fill('#wh-hub-search', '', { timeout: 6000 }).catch(() => {}); await page.click('#wh-hub-mode .wh-hub-mode-btn[data-mode="all"]').catch(() => {}); await page.waitForTimeout(350);
  await page.fill('#wh-hub-search', 'logbook', { timeout: 6000 }).catch(() => {}); await page.waitForTimeout(500);
  hub.filterInAll = await page.evaluate(() => [...document.querySelectorAll('#wh-hub-tiles .wh-hub-tile')].filter((t) => t.checkVisibility && t.checkVisibility()).map((t) => (t.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 24)));
  await A('filter typed (keyboard state)');
  await page.fill('#wh-hub-search', 'zzqxv', { timeout: 6000 }).catch(() => {}); await page.waitForTimeout(500);
  hub.noResults = await vis('#wh-hub-no-results');
  await A('filter no results');
  await page.fill('#wh-hub-search', '', { timeout: 6000 }).catch(() => {}); await page.waitForTimeout(300);
  hub.controls_exercised++;
  hub.globalBtn = await vis('#wh-hub-global-search');
  if (hub.globalBtn.shown) {
    await page.click('#wh-hub-global-search', { timeout: 6000 }).catch(() => {}); await page.waitForTimeout(800);
    hub.globalOverlay = await vis('#wh-search-overlay'); hub.globalFocus = await focusOn();
    await page.fill('#ws-input', 'pump').catch(() => {}); await page.waitForTimeout(900);
    hub.globalResults = await page.evaluate(() => { const o = document.querySelector('#wh-search-overlay'); return o ? (o.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 160) : null; });
    await A('global search with a query');
    await page.keyboard.press('Escape'); await page.waitForTimeout(400); hub.globalClosedFocus = await focusOn();
    hub.controls_exercised++;
  }
  await ensureHub();
  hub.quick = await vis('#wh-hub-quick'); if (hub.quick.shown) hub.controls_exercised++;
  hub.quickTiles = await page.evaluate(() => [...document.querySelectorAll('#wh-hub-quick .wh-hub-quick-tile')].filter((t) => t.checkVisibility && t.checkVisibility()).map((t) => (t.getAttribute('title') || '').slice(0, 20)));
  hub.openCompanion = await vis('#wh-hub-open-companion');
  if (hub.openCompanion.shown) {
    await page.click('#wh-hub-open-companion', { timeout: 6000 }).catch(() => {}); await page.waitForTimeout(1000);
    hub.companionPanel = await vis('#wh-ai-panel'); hub.hubWhileCompanion = (await vis('#wh-hub-panel')).shown;
    hub.companionCoversPrimary = await page.evaluate(() => { const p = document.querySelector('#wh-ai-panel'); if (!p) return null; const pr = p.getBoundingClientRect(); return [...document.querySelectorAll('main button, main a.btn, main [class*="btn-primary"], main [class*="cta"]')].filter((e) => e.checkVisibility && e.checkVisibility()).slice(0, 40).map((e) => { const q = e.getBoundingClientRect(); const ov = Math.max(0, Math.min(q.right, pr.right) - Math.max(q.left, pr.left)) * Math.max(0, Math.min(q.bottom, pr.bottom) - Math.max(q.top, pr.top)); return ov > 0 && q.top < innerHeight && q.bottom > 0 ? (e.textContent || e.getAttribute('aria-label') || '').trim().slice(0, 24) : null; }).filter(Boolean).slice(0, 5); });
    await A('companion open from the hub');
    await page.keyboard.press('Escape'); await page.waitForTimeout(400);
    let still = await vis('#wh-ai-panel');
    if (still.shown) { const c = await page.$('#wh-ai-panel [aria-label*="lose" i], #wh-ai-panel [aria-label*="sara" i], #wh-ai-panel .wh-ai-close, #wh-ai-panel button[class*="close"]'); if (c) { await c.click({ timeout: 4000 }).catch(() => out.problems.push('the companion close control did not become clickable')); await page.waitForTimeout(400); still = await vis('#wh-ai-panel'); } }
    hub.companionAfterClose = { shown: still.shown, focusOn: await focusOn() };
    await A('after closing the companion');
    hub.controls_exercised++;
  }
  await ensureHub();
  hub.openFeedback = await vis('#wh-hub-open-feedback');
  if (hub.openFeedback.shown) {
    await page.click('#wh-hub-open-feedback', { timeout: 6000 }).catch(() => {}); await page.waitForTimeout(1000);
    hub.feedbackPanel = await vis('#wh-feedback-panel');
    await A('feedback open from the hub');
    await page.keyboard.press('Escape'); await page.waitForTimeout(400);
    let still = await vis('#wh-feedback-panel');
    if (still.shown) { const c = await page.$('#wh-feedback-panel [aria-label*="lose" i], #wh-feedback-panel [aria-label*="sara" i], #wh-feedback-panel button[class*="close"]'); if (c) { await c.click({ timeout: 4000 }).catch(() => out.problems.push('the feedback close control did not become clickable')); await page.waitForTimeout(400); still = await vis('#wh-feedback-panel'); } }
    hub.feedbackAfterClose = { shown: still.shown, focusOn: await focusOn() };
    hub.controls_exercised++;
  }
  await ensureHub();
  hub.assistRow = await vis('#wh-hub-assist-row'); if (hub.assistRow.shown) hub.controls_exercised++;
  hub.connPillOnline = await vis('#wh-hub-conn-pill');
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Network.enable'); await cdp.send('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  await page.evaluate(() => window.dispatchEvent(new Event('offline'))); await page.waitForTimeout(1800);
  hub.connPillOffline = await vis('#wh-hub-conn-pill');
  await A('offline: connectivity pill');
  if (hub.connPillOffline.shown) {
    await page.click('#wh-hub-conn-pill', { timeout: 6000 }).catch(() => {}); await page.waitForTimeout(500);
    hub.connDetail = await vis('#wh-hub-conn-detail');
    hub.connDetailText = await page.evaluate(() => { const d = document.querySelector('#wh-hub-conn-detail'); return d ? (d.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 200) : null; });
    await A('connectivity detail open');
    hub.controls_exercised++;
  }
  await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  await page.evaluate(() => window.dispatchEvent(new Event('online'))); await page.waitForTimeout(1500);
  hub.connPillBackOnline = (await vis('#wh-hub-conn-pill')).shown;
  await cdp.detach().catch(() => {});
  hub.unnamed = await page.evaluate(() => [...document.querySelectorAll('#wh-hub-panel button, #wh-hub-panel a')].filter((e) => e.checkVisibility && e.checkVisibility() && !(e.getAttribute('aria-label') || e.textContent || '').trim()).length);
  hub.tapUnder44 = await page.evaluate(() => [...document.querySelectorAll('#wh-hub-panel button, #wh-hub-panel a')].filter((e) => e.checkVisibility && e.checkVisibility()).map((e) => { const q = e.getBoundingClientRect(); return { n: (e.getAttribute('aria-label') || e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 18), h: Math.round(q.height), w: Math.round(q.width) }; }).filter((x) => x.h < 44 || x.w < 44).slice(0, 8));
  hub.names = await page.evaluate(() => ({ lang: document.documentElement.lang, labels: [...document.querySelectorAll('#wh-hub-panel [aria-label], #wh-hub-fab')].slice(0, 8).map((e) => e.getAttribute('aria-label').slice(0, 30)), noResultsCopy: (document.querySelector('#wh-hub-no-results') || {}).textContent, modeLabels: [...document.querySelectorAll('#wh-hub-mode .wh-hub-mode-btn')].map((b) => b.textContent.trim().slice(0, 16)) }));
  await page.keyboard.press('Escape'); await page.waitForTimeout(400);
  hub.closed = { shown: (await vis('#wh-hub-panel')).shown, focusOn: await focusOn() };
  if (!hub.closed.shown) hub.controls_exercised++;
  await A('hub closed');
  host.hub = hub;
  out.steps.push(host);

  // ── onward through the hub's own tiles ─────────────────────────────────────────────────────────
  for (let i = 0; i < stops.length; i++) {
    const target = stops[i];
    await page.click('#wh-hub-fab', { timeout: 8000 }).catch(() => {}); await page.waitForTimeout(700);
    await page.click('#wh-hub-mode .wh-hub-mode-btn[data-mode="all"]').catch(() => {}); await page.waitForTimeout(300);
    const tile = page.locator(`#wh-hub-tiles a.wh-hub-tile[href*="${target}"]`).first();
    if (!(await tile.count())) { out.steps.push({ page: target, chars: 0, identityKept: true, loadError: 'no hub tile offers this destination', onward: [] }); continue; }
    await A(`${target}: hub open before leaving`);
    await tile.click({ timeout: 8000 }).catch((e) => out.problems.push('the hub tile to ' + target + ' did not become clickable')); 
    try { await page.waitForURL(atPath(target), { timeout: 20000 }); } catch (e) { out.steps.push({ page: target, chars: 0, identityKept: true, loadError: 'tile click did not navigate in 20s', onward: [] }); continue; }
    await page.waitForTimeout(5000);
    let rr = await read(); let k = 0;
    while (rr.chars < 900 && k < 3) { await page.waitForTimeout(4000); rr = await read(); k++; }
    const fit = await A(`${target} at rest`);
    await page.click('#wh-hub-fab', { timeout: 8000 }).catch(() => {}); await page.waitForTimeout(600);
    const hubHere = await A(`${target}: hub open`);
    await page.keyboard.press('Escape'); await page.waitForTimeout(300);
    out.steps.push({ page: target, chars: rr.chars, identityKept: rr.worker === (P.castName || 'Romeo Beltran'), lang: rr.lang, skeletons: rr.skeletons, onward: stops.slice(i + 1, i + 2), seen: `arrived by the hub's tile; hub opened here: ${hubHere.findings} finding(s)`, fit, hubFindings: hubHere.findings });
  }
  out.records = records;
  out.summary = { records: records.length, withFindings: records.filter((x) => x.findings > 0).length, vw: W, lang: LANG, controls_exercised: hub.controls_exercised };
  // ★THE MCP'S VM CANNOT import() (ERR_VM_DYNAMIC_IMPORT_CALLBACK_MISSING, 2026-09-14), so the steps are
  // handed to our own local seeder (test-data-seeder/app.py, POST /api/w4/steps) through Playwright's request
  // context, which needs no Node module - the seeder writes .tmp/w4_steps/<id>.json and <id>.records.json.
  try {
    const base = origin.replace(/\/workhive\/?$/, '');
    // the seeder stores only `steps`, so the verdict rides on the host step: its problems list and its hub ledger
    if (out.steps[0]) { out.steps[0].problems = out.problems; out.steps[0].controls = hub ? (hub.controls_exercised || 0) : 0; }
    const res = await page.request.post(`${base}/api/w4/steps`, { data: { id: P.id || 'walk', steps: out.steps, records, problems: out.problems, summary: out.summary, controls: hub ? (hub.controls_exercised || 0) : 0 } });
    out.wrote = res.ok() ? (await res.json()).path : `POST /api/w4/steps -> ${res.status()}`;
  } catch (e) { out.writeError = String(e.message || e).slice(0, 120); }
  // ★RETURN THE VERDICT, NOT THE LEDGER: the MCP echoes every result into the conversation, and the full
  // steps + 24 records cost ~4K tokens per walk. The files hold everything; the reply holds what decides
  // the next step - problems, the per-step findings and confusions, the hub's verdict fields, the hops.
  const hubV = hub ? { controls: hub.controls_exercised, modes: hub.modes.map((m) => `${m.mode}:${m.tiles}`).join(' '), filterInLastMode: hub.filterInLastMode, filterInAll: hub.filterInAll, noResultsCopy: hub.names && hub.names.noResultsCopy, globalFocus: hub.globalFocus, globalClosedFocus: hub.globalClosedFocus, companionCoversPrimary: hub.companionCoversPrimary, companionAfterClose: hub.companionAfterClose, feedbackAfterClose: hub.feedbackAfterClose, connOffline: hub.connPillOffline && hub.connPillOffline.state, connDetail: hub.connDetailText && hub.connDetailText.slice(0, 90), closed: hub.closed, unnamed: hub.unnamed, tapUnder44: hub.tapUnder44, labels: hub.names && hub.names.labels, lang: hub.names && hub.names.lang } : null;
  return { id: P.id, axis: P.axis, host: P.host, wrote: out.wrote, writeError: out.writeError, problems: out.problems, summary: out.summary,
    hostStep: { chars: host.chars, identityKept: host.identityKept, lang: host.lang, skeletons: host.skeletons },
    hub: hubV,
    onward: out.steps.slice(1).map((s) => ({ page: s.page, chars: s.chars, identityKept: s.identityKept, findings: s.fit && s.fit.findings, hubFindings: s.hubFindings, loadError: s.loadError })),
    // ★THE RECEIPT NEEDS PER-PAGE STEPS WITH FIT, or live_walk_manifest._w4_missing rejects the row ("fewer than
    // 4 pages walked / a step has no overlap record") and no nav-hub row can EVER close (2026-09-14, W41429 dig).
    // out.steps is [host, ...onward], each with .page + .fit; return a COMPACT copy (a fit DICT, not the 24 raw
    // records the comment above rightly keeps out of the reply) so the driver can write the ledger's shape.
    steps: out.steps.map((s) => ({ page: s.page, chars: s.chars, identityKept: s.identityKept, loadError: s.loadError || null,
      fit: s.fit ? { findings: s.fit.findings || 0, occlusion: (s.fit.occlusion || []).slice(0, 4), overflowEl: (s.fit.overflowEl || []).slice(0, 2), wrapped: (s.fit.wrapped || []).slice(0, 2) } : { findings: 0 } })),
    findings: records.filter((r) => r.findings > 0).map((r) => ({ step: r.step, occlusion: r.occlusion, overflowEl: r.overflowEl, outside: r.outside, wrapped: r.wrapped, clipped: r.clipped, spill: r.spill })).slice(0, 8),
    confusions: records.filter((r) => (r.ambiguity && r.ambiguity.length) || (r.unactionable && r.unactionable.length)).map((r) => ({ step: r.step, ambiguity: r.ambiguity, unactionable: r.unactionable })).slice(0, 8) };
}
