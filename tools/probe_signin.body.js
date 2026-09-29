// Why does sign-in fail for driverben now, when all 30 hosts signed in an hour ago?
async (page) => {
  const out = { console: [], pageErrors: [], requests: [] };
  page.on('console', m => { if (out.console.length < 25) out.console.push(m.type() + ': ' + m.text().slice(0, 200)); });
  page.on('pageerror', e => out.pageErrors.push(String(e).slice(0, 300)));
  page.on('response', async r => {
    const u = r.url();
    if (/auth\/v1|token|signup/.test(u) && out.requests.length < 10) {
      let body = '';
      try { body = (await r.text()).slice(0, 300); } catch (_) {}
      out.requests.push(r.status() + ' ' + u.split('?')[0] + ' -> ' + body);
    }
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('http://localhost:5000/workhive/index.html?signin=1&return=dayplanner.html', { waitUntil: 'load' });
  await page.waitForSelector('#si-username', { state: 'visible', timeout: 30000 }).catch(() => {});
  out.wallVisible = await page.locator('#si-username').isVisible().catch(() => false);
  if (out.wallVisible) {
    await page.fill('#si-username', 'driverben');
    await page.fill('#si-password', 'test1234');
    await page.click('#si-btn').catch(e => out.pageErrors.push('click: ' + e.message.slice(0, 120)));
    await page.waitForTimeout(6000);
  }
  out.url = page.url();
  out.visibleError = await page.evaluate(() => {
    const t = [];
    document.querySelectorAll('[role="alert"], .error, #si-error, [id*="error"]').forEach(e => {
      const s = (e.textContent || '').replace(/\s+/g, ' ').trim();
      if (s && getComputedStyle(e).display !== 'none') t.push(s.slice(0, 160));
    });
    return t.slice(0, 5);
  });
  return out;
}
