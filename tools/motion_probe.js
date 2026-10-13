// motion_probe.js - read a page's running motion the way the motion lens judges it, through the Playwright MCP
// (2026-10-12). The design walker counts "slow / ease-in / animated" elements; a count cannot say whether a decoration
// animates transform or a layout property, loops forever, or stops when a person asks for less motion. This reads it
// from the browser's own animation objects - document.getAnimations() - per page, at 390 and 1280, and again under
// prefers-reduced-motion: reduce:
//   each animation: target, name, duration, iterations, easing, and the PROPERTIES its keyframes animate.
// Signed in as the args' cast when a user is given. Reads only. Args: .tmp/motion_probe_args.json
//   { pages: ['inventory.html', ...], user, pass }
//   browser_run_code_unsafe { filename: tools/motion_probe.js }
async (page) => {
  const base = 'http://localhost:5000/workhive';
  const A = await (await page.request.get(`${base}/.tmp/motion_probe_args.json`, { timeout: 8000 })).json();
  const browser = page.context().browser();
  const read = (p) => p.evaluate(() => {
    const desc = (el) => !el || !el.tagName ? '?' : el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
      (typeof el.className === 'string' && el.className.trim() ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '');
    const rows = {};
    for (const a of document.getAnimations()) {
      const eff = a.effect; if (!eff) continue;
      const t = eff.getTiming ? eff.getTiming() : {};
      let props = [];
      try { props = [...new Set(eff.getKeyframes().flatMap((k) => Object.keys(k).filter((x) => !['offset', 'easing', 'composite', 'computedOffset'].includes(x))))]; } catch (e) { void e; }
      const kind = a.constructor && a.constructor.name;   // CSSAnimation | CSSTransition | Animation
      const name = a.animationName || a.transitionProperty || a.id || '';
      const key = kind + '|' + name + '|' + props.join('/') + '|' + t.duration + '|' + t.iterations + '|' + t.easing;
      if (!rows[key]) rows[key] = { kind, name, props, duration: t.duration, iterations: t.iterations, easing: t.easing, count: 0, sample: desc(eff.target) };
      rows[key].count++;
    }
    return Object.values(rows);
  });
  const out = [];
  // items: [{ page, user, pass, query }] - each page as its own cast; or pages: [...] with one A.user for all
  const items = A.items || (A.pages || []).map((pg) => ({ page: pg, user: A.user, pass: A.pass }));
  for (const it of items) {
    const pg = it.page + (it.query || '');
    A.user = it.user; A.pass = it.pass;
    const res = { page: pg };
    for (const [w, h, vname, reduce] of [[390, 844, 'phone-390', false], [1280, 800, 'desktop-1280', false], [1280, 800, 'desktop-1280-reduced', true]]) {
      const ctx = await browser.newContext({ viewport: { width: w, height: h }, reducedMotion: reduce ? 'reduce' : 'no-preference' });
      const p = await ctx.newPage();
      try {
        if (A.user) {
          await p.goto(`${base}/index.html?signin=1`, { waitUntil: 'load', timeout: 30000 });
          await p.waitForSelector('#si-username', { state: 'visible', timeout: 15000 }).catch(() => {});
          await p.waitForTimeout(800);
          await p.fill('#si-username', A.user); await p.fill('#si-password', A.pass);
          const lr = p.waitForResponse((r) => /\/functions\/v1\/login/.test(r.url()), { timeout: 15000 }).catch(() => null);
          await p.press('#si-password', 'Enter'); await lr; await p.waitForTimeout(3000);
        }
        await p.goto(`${base}/${pg}`, { waitUntil: 'load', timeout: 30000 });
        await p.waitForTimeout(3500);
        res[vname] = await read(p);
      } catch (e) {
        res[vname] = { error: String(e.message || e).slice(0, 120) };
      } finally { await ctx.close(); }
    }
    out.push(res);
  }
  return out;
}
