// w4_cwv_mcp.js - the audit lens's performance reading, taken through the Playwright MCP over a CDP session (2026-10-13).
//
// The audit lens names two instruments: the Playwright MCP for the rendered page, and Chrome DevTools for what only the
// protocol can see. A full DevTools MCP trace per page re-sends ~6K tokens of format text each time; this drives the
// same protocol from the MCP's own browser, one fresh context per page, and returns only the numbers the lens scores:
//   - a phone: 390x844 at dpr 3, mobile, touch;
//   - the network throttled over CDP (Network.emulateNetworkConditions) to DevTools' Slow 4G profile - 562.5ms RTT,
//     ~1.47 Mbps down, ~0.68 Mbps up - and the CPU slowed 4x (Emulation.setCPUThrottlingRate);
//   - LCP and CLS observed from NAVIGATION START (addInitScript, buffered observers - a late observer over-counts),
//     FCP from the paint timeline, and every resource the browser marked render-blocking with its time and size.
// Reads only. Signed in first when the row's args carry a user. Args: .tmp/w4_cwv_args.json
//   [{ id, page, query?, user?, pass? }]
//   browser_run_code_unsafe { filename: tools/w4_cwv_mcp.js }
async (page) => {
  const base = 'http://localhost:5000/workhive';
  const A = await (await page.request.get(`${base}/.tmp/w4_cwv_args.json`, { timeout: 8000 })).json();
  const browser = page.context().browser();
  const SLOW_4G = { offline: false, latency: 562.5, downloadThroughput: Math.round(1.6 * 1024 * 1024 / 8 * 0.9), uploadThroughput: Math.round(750 * 1024 / 8 * 0.9) };
  const OBSERVE = () => {
    window.__cwv = { lcp: 0, lcpEl: '', cls: 0 };
    try {
      new PerformanceObserver((l) => { for (const e of l.getEntries()) { window.__cwv.lcp = e.startTime; const el = e.element; window.__cwv.lcpEl = el ? (el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (typeof el.className === 'string' && el.className.trim() ? '.' + el.className.trim().split(/\s+/)[0] : '')) : ''; } })
        .observe({ type: 'largest-contentful-paint', buffered: true });
      new PerformanceObserver((l) => { for (const e of l.getEntries()) { if (!e.hadRecentInput) window.__cwv.cls += e.value; } })
        .observe({ type: 'layout-shift', buffered: true });
    } catch (e) { void e; }
  };
  const out = [];
  for (const R of A) {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true });
    const p = await ctx.newPage();
    const rec = { id: R.id, page: R.page };
    try {
      if (R.user) {   // sign in un-throttled - the reading is the page's, not the wall's
        await p.goto(`${base}/index.html?signin=1`, { waitUntil: 'load', timeout: 30000 });
        await p.waitForSelector('#si-username', { state: 'visible', timeout: 15000 }).catch(() => {});
        await p.waitForTimeout(800);
        await p.fill('#si-username', R.user); await p.fill('#si-password', R.pass);
        const lr = p.waitForResponse((r) => /\/functions\/v1\/login/.test(r.url()), { timeout: 15000 }).catch(() => null);
        await p.press('#si-password', 'Enter'); await lr; await p.waitForTimeout(3000);
      }
      const cdp = await ctx.newCDPSession(p);
      await cdp.send('Network.enable');
      await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });
      await cdp.send('Network.emulateNetworkConditions', SLOW_4G);
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
      await p.addInitScript(OBSERVE);
      const t0 = Date.now();
      await p.goto(`${base}/${R.page}${R.query || ''}`, { waitUntil: 'load', timeout: 90000 });
      rec.loadMs = Date.now() - t0;
      await p.waitForTimeout(3000);
      Object.assign(rec, await p.evaluate(() => {
        const fcpE = performance.getEntriesByType('paint').find((e) => e.name === 'first-contentful-paint');
        const res = performance.getEntriesByType('resource');
        const blocking = res.filter((r) => r.renderBlockingStatus === 'blocking')
          .map((r) => ({ name: r.name.replace(/^https?:\/\/[^/]+/, (m) => (/localhost|127\.0\.0\.1/.test(m) ? '' : m)).slice(0, 70), ms: Math.round(r.duration), kb: Math.round((r.transferSize || r.encodedBodySize || 0) / 1024) }));
        const kb = Math.round(res.reduce((a, r) => a + (r.transferSize || 0), 0) / 1024);
        return { lcp: Math.round(window.__cwv ? window.__cwv.lcp : 0), lcpEl: window.__cwv ? window.__cwv.lcpEl : '', cls: Math.round((window.__cwv ? window.__cwv.cls : 0) * 1000) / 1000,
          fcp: fcpE ? Math.round(fcpE.startTime) : null, blocking, requests: res.length, kb };
      }));
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 }).catch(() => {});
    } catch (e) {
      rec.error = String(e.message || e).slice(0, 140);
    } finally {
      await ctx.close();
    }
    out.push(rec);
  }
  return out;
}
