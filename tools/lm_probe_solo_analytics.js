// lm_probe_solo_analytics.js - LM-R verification for LM60 (2026-10-07), run with browser_run_code_unsafe { filename }.
// A person with NO hive opens analytics.html twice in one tab. Before the fix every open ran analytics-orchestrator for
// all four phases (one of them a model call); after it, the second open must render from the tab's saved copy and call
// nothing. The first open is LIVE (one real prescriptive call), as Ian approved for Routing; writes are not possible
// here (the page only reads). Signs in through the product's own wall as the seeded solo owner (junvanowner).
async (page) => {
  const ORIGIN = 'http://localhost:5000/workhive';
  const browser = page.context().browser();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true,
    deviceScaleFactor: 2, serviceWorkers: 'block', locale: 'en-PH' });
  const calls = [];
  await ctx.route('**/functions/v1/**', async (route) => {
    const fn = (route.request().url().split('/functions/v1/')[1] || '').split(/[?/#]/)[0];
    if (/send|push|notify|email|export|reset|invite|payment|webhook/i.test(fn)) {
      return route.fulfill({ status: 503, contentType: 'application/json', body: '{"error":"blocked by the probe"}' });
    }
    if (fn === 'analytics-orchestrator') {
      let phase = null;
      try { phase = JSON.parse(route.request().postData() || '{}').phase; } catch (e) { void e; }
      calls.push({ open: calls.openNo || 0, phase });
    }
    return route.fallback();
  });
  const p = await ctx.newPage();
  const out = { opens: [] };
  try {
    await p.goto(`${ORIGIN}/index.html?signin=1&return=analytics.html`, { waitUntil: 'load', timeout: 45000 });
    await p.waitForSelector('#si-username', { state: 'visible', timeout: 45000 });
    await p.fill('#si-username', 'junvanowner');
    await p.fill('#si-password', 'test1234');
    await p.click('#si-btn').catch(() => p.press('#si-password', 'Enter'));
    await p.waitForURL(/analytics[.]html/, { timeout: 30000 }).catch(() => {});
    if (!/analytics[.]html/.test(p.url())) await p.goto(`${ORIGIN}/analytics.html`, { waitUntil: 'load', timeout: 45000 });
    for (const openNo of [1, 2, 3]) {
      calls.openNo = openNo;
      if (openNo > 1) await p.goto(`${ORIGIN}/analytics.html`, { waitUntil: 'load', timeout: 45000 });
      // wait until all four phases are saved for the tab (the live prescriptive call can take a while; the first
      // run of this probe measured before it finished, so the second open rightly asked for it again)
      for (let i = 0; i < 60; i++) {
        const n = await p.evaluate(() => Object.keys(sessionStorage).filter((k) => k.startsWith('wh_solo_analytics:'))
          .reduce((m, k) => Math.max(m, Object.keys(JSON.parse(sessionStorage.getItem(k) || '{}')).length), 0)).catch(() => 0);
        if (n >= 4 && i > 2) break;
        await p.waitForTimeout(2000);
      }
      const st = await p.evaluate(() => ({
        hive: localStorage.getItem('wh_active_hive_id'),
        status: (document.getElementById('status-text') || {}).textContent || '',
        saved: Object.keys(sessionStorage).filter((k) => k.startsWith('wh_solo_analytics:')).map((k) => Object.keys(JSON.parse(sessionStorage.getItem(k) || '{}'))),
      })).catch(() => ({}));
      out.opens.push({ open: openNo, orchestratorCalls: calls.filter((c) => c.open === openNo).map((c) => c.phase), ...st });
    }
  } catch (e) { out.error = String(e.message || e).slice(0, 200); }
  await ctx.close();
  out.verdict = out.opens.length === 3 && out.opens[0].orchestratorCalls.length > 0
    && out.opens[1].orchestratorCalls.length === 0 && out.opens[2].orchestratorCalls.length === 0
    ? 'HOLDS: after the first open saved all four phases, later opens called nothing' : 'DOES NOT HOLD';
  return out;
}
