// brp_drift_walk.js - the BRP class-A drift walk through the Playwright MCP (2026-10-12).
//
// A BRP-A row says: this surface asks who owns its rows by DISPLAY NAME where the table carries auth_uid, so "drift the
// signed-in display name by one character and the person's own rows vanish from this surface". The fix unions the
// auth_uid query in beside the name query. This walk makes the reproduction run, as the person, at both viewports:
//
//   1. a fresh browser context at the viewport; sign in through the wall as the row's cast (a seeded local worker);
//   2. walk the row's own pages in order - the arrival the row's story describes;
//   3. on the row's page, record EVERY PostgREST read of the row's table: its filter, its status, how many rows came back;
//   4. drift the display name by ONE character, client side - localStorage wh_last_worker, which is where every page
//      reads WORKER_NAME from - and reload: the same reads again;
//   5. restore the name, close the context.
//
// Nothing is written to the database: the drift is the browser's own copy of the name, exactly what a stale device or a
// rename presents. Per-step records are POSTed to the seeder (.tmp/w4_steps/<id>.json + .records.json) for
// tools/brp_drift_drive.py to judge and bank. Parameters: .tmp/brp_args.json, written by `brp_drift_drive.py prep`.
//
//   browser_run_code_unsafe { filename: tools/brp_drift_walk.js }
async (page) => {
  const base = 'http://localhost:5000/workhive';
  const ar = await page.request.get(`${base}/.tmp/brp_args.json`, { timeout: 8000 });
  if (!ar.ok()) return { problems: [`no args file: HTTP ${ar.status()}`] };
  const A = await ar.json();
  const browser = page.context().browser();
  const VIEWPORTS = A.viewports || [[390, 844, 'phone-390'], [1280, 800, 'desktop-1280']];
  const out = [];
  const textOf = (p) => p.evaluate(() => {
    const t = (document.body && document.body.innerText) || '';
    return { chars: t.replace(/\s+/g, ' ').trim().length, title: document.title, path: location.pathname,
      removed: /removed from (your|the|this) hive|you have been removed|no longer a member/i.test(t),
      wall: !!(document.querySelector('#si-username') && document.querySelector('#si-username').getBoundingClientRect().width) };
  });
  // the press a row's read sits behind (2026-10-13, tools/brp_drift_drive.py ACTIONS): {click: css} / {wait: ms}, run once
  // under the stored name and once after the drift, so the read is made both times; a press that cannot land is a problem
  // on the record, never a silent skip
  // a step carrying `only` runs in that phase alone (2026-10-13, BRP78): a bulk action that empties its own fixtures in
  // one press - "remove every unavailable save" - would leave the drifted phase nothing to act on if the stored phase
  // pressed it too, so the stored phase opens the view and only the drifted phase presses
  const runActions = async (p, acts, rec, phase) => {
    for (const s of (acts || [])) {
      if (s.only && s.only !== phase) continue;
      if (s.wait) { await p.waitForTimeout(s.wait); continue; }
      if (s.select) {
        try { await p.locator(s.select).first().selectOption(s.value, { timeout: 8000 }); }
        catch (e) { rec.problems.push(phase + ': could not choose "' + s.value + '" in ' + s.select + ' (' + String(e.message || e).slice(0, 70) + ')'); return; }
        continue;
      }
      if (s.click) {
        try { await p.locator(s.click).first().click({ timeout: 8000 }); }
        catch (e) { rec.problems.push(phase + ': could not press ' + s.click + ' (' + String(e.message || e).slice(0, 70) + ')'); return; }
      }
    }
  };
  for (const R of A.rows) {
    const steps = [];
    const records = { id: R.id, table: R.table, page: R.page, cast: R.cast, stored: R.stored, drifted: R.drifted, viewports: {} };
    for (const [w, h, vname] of VIEWPORTS) {
      const ctx = await browser.newContext({ viewport: { width: w, height: h } });
      const p = await ctx.newPage();
      const cur = { phase: 'signin' };
      const reads = [];
      // ★A WRITE ROW IS PROVED BY ITS WRITE (2026-10-13, BRP16/BRP17 - inventory's delete guards): the site is a DELETE,
      // so the record is the request the page's own Remove button sent - its method, status and filter - not a read
      const writes = [];
      const tableRx = new RegExp('/rest/v1/' + R.table + '([?]|$)');
      p.on('response', async (resp) => {
        const url = resp.url();
        if (!tableRx.test(url)) return;
        const method = resp.request().method();
        // ★A COUNT IS A READ TOO (2026-10-13, BRP73): `select('id', {count:'exact', head:true})` goes out as HEAD, with no
        // body - the number is in content-range ("*/3" or "0-2/3"), so that is where n comes from
        if (method === 'HEAD') {
          const cr = resp.headers()['content-range'] || '';
          const cm = cr.match(/\/(\d+)$/);
          let hq = '';
          try { hq = decodeURIComponent(url.split('?')[1] || ''); } catch (e) { hq = url.split('?')[1] || ''; }
          reads.push({ phase: cur.phase, status: resp.status(), n: cm ? Number(cm[1]) : null, head: true,
            byName: /worker_name=eq|worker_name\.eq|worker_name=ilike|worker_name\.ilike/.test(hq),
            byIdentity: /auth_uid=eq|auth_uid\.eq/.test(hq),
            q: hq.replace(/select=[^&]*&?/, '').slice(0, 220) });
          return;
        }
        if (method !== 'GET') {
          if (!['DELETE', 'PATCH', 'POST'].includes(method)) return;
          let wq = '';
          try { wq = decodeURIComponent(url.split('?')[1] || ''); } catch (e) { wq = url.split('?')[1] || ''; }
          writes.push({ phase: cur.phase, method, status: resp.status(),
            byName: /worker_name=eq|worker_name\.eq/.test(wq), byIdentity: /auth_uid=eq|auth_uid\.eq/.test(wq),
            q: wq.replace(/select=[^&]*&?/, '').slice(0, 220) });
          return;
        }
        const phase = cur.phase;
        let n = null;
        try { const j = await resp.json(); n = Array.isArray(j) ? j.length : (j ? 1 : 0); } catch (e) { void e; }
        let q = '';
        try { q = decodeURIComponent(url.split('?')[1] || ''); } catch (e) { q = url.split('?')[1] || ''; }
        reads.push({ phase, status: resp.status(), n,
          byName: /worker_name=eq|worker_name\.eq|worker_name=ilike|worker_name\.ilike/.test(q),
          byIdentity: /auth_uid=eq|auth_uid\.eq/.test(q),
          q: q.replace(/select=[^&]*&?/, '').slice(0, 220) });
      });
      const rec = { viewport: vname, signedIn: false, stored: null, drifted: null, problems: [] };
      try {
        // ★A SUBMIT THAT NEVER FIRED IS NOT A SIGN-IN (2026-10-12, BRP7/BRP23 at 1280): the login function logged 6
        // requests for 8 sign-ins - Enter landed before the wall's form was wired, the page stayed on the wall, and
        // the walk read "0 reads of the table" as if the page had made none. Wait for the field, wait for the login
        // RESPONSE, retry up to three times, and say so when it still does not take.
        let who = '', loginStatus = null, attempts = 0;
        while (!who && attempts < 3) {
          attempts++;
          await p.goto(`${base}/index.html?signin=1`, { waitUntil: 'load', timeout: 30000 });
          await p.waitForSelector('#si-username', { state: 'visible', timeout: 15000 }).catch(() => {});
          await p.waitForTimeout(800);
          await p.fill('#si-username', R.user);
          await p.fill('#si-password', R.pass);
          const lr = p.waitForResponse((r) => /\/functions\/v1\/login/.test(r.url()) && r.request().method() === 'POST', { timeout: 15000 }).catch(() => null);
          await p.press('#si-password', 'Enter');
          const resp = await lr;
          loginStatus = resp ? resp.status() : null;
          await p.waitForTimeout(3500);
          who = await p.evaluate(() => { try { return localStorage.getItem('wh_last_worker') || localStorage.getItem('wh_worker_name') || ''; } catch (e) { return ''; } });
        }
        rec.signedIn = !!who;
        rec.nameOnDevice = who;
        rec.signInAttempts = attempts;
        if (!who) rec.problems.push('the sign-in did not take after ' + attempts + ' attempt(s) (login response ' + loginStatus + ')');
        if (who && who !== R.stored) rec.problems.push('signed in as "' + who + '", the receipt expects "' + R.stored + '"');
        // the arrival the row's story describes, page by page
        cur.phase = 'walk';
        for (const pg of R.pages) {
          if (pg === R.page) continue;
          await p.goto(`${base}/${pg}`, { waitUntil: 'load', timeout: 30000 }).catch((e) => rec.problems.push('could not load ' + pg + ': ' + String(e.message || e).slice(0, 60)));
          await p.waitForTimeout(2500);
          const t = await textOf(p);
          steps.push({ page: pg, viewport: vname, chars: t.chars, title: t.title, identityKept: !t.wall, landed: t.path });
        }
        // the page under study, under the name the database stored
        cur.phase = 'stored';
        await p.goto(`${base}/${R.page}`, { waitUntil: 'load', timeout: 30000 });
        await p.waitForTimeout(5000);
        await runActions(p, R.actions, rec, 'stored');
        rec.stored = await textOf(p);
        steps.push({ page: R.page, viewport: vname, chars: rec.stored.chars, title: rec.stored.title, identityKept: !rec.stored.wall, phase: 'stored' });
        // ONE character of drift, on the device - then the same page again
        await p.evaluate((d) => {
          localStorage.setItem('wh_last_worker', d);
          if (localStorage.getItem('wh_worker_name') !== null) localStorage.setItem('wh_worker_name', d);
        }, R.drifted);
        cur.phase = 'drifted';
        await p.reload({ waitUntil: 'load', timeout: 30000 });
        await p.waitForTimeout(5000);
        await runActions(p, R.actions, rec, 'drifted');
        rec.drifted = await textOf(p);
        steps.push({ page: R.page, viewport: vname, chars: rec.drifted.chars, title: rec.drifted.title, identityKept: !rec.drifted.wall && !rec.drifted.removed, phase: 'drifted', driftedName: R.drifted });
        await p.evaluate((s) => {
          localStorage.setItem('wh_last_worker', s);
          if (localStorage.getItem('wh_worker_name') !== null) localStorage.setItem('wh_worker_name', s);
        }, R.stored);
      } catch (e) {
        rec.problems.push('the walk threw: ' + String(e.message || e).slice(0, 120));
      } finally {
        await ctx.close();
      }
      rec.reads = reads;
      rec.writes = writes;
      records.viewports[vname] = rec;
    }
    // the seeder's API sits at the server root, not under the /workhive/ mount (a POST there is a 405)
    // post_id (2026-10-13): a row walked one viewport at a time (`prep --viewport`) records each part under its own name,
    // <id>__<viewport> (the seeder keeps only [A-Za-z0-9_-] of an id), and `brp_drift_drive.py bank` merges the parts
    const post = await page.request.post(`${base.replace(/\/workhive$/, '')}/api/w4/steps`, { data: { id: R.post_id || R.id, steps, records } });
    const sum = {};
    for (const [vname, rec] of Object.entries(records.viewports)) {
      const by = (ph) => (rec.reads || []).filter((x) => x.phase === ph);
      const tot = (xs) => xs.reduce((a, x) => a + (x.n || 0), 0);
      sum[vname] = { stored: [by('stored').length, tot(by('stored'))], drifted: [by('drifted').length, tot(by('drifted'))],
        nameOnly: (rec.reads || []).filter((x) => x.byName && !x.byIdentity).length, identity: (rec.reads || []).filter((x) => x.byIdentity).length,
        removed: !!(rec.drifted && rec.drifted.removed), problems: rec.problems,
        ...((rec.writes || []).length ? { writes: rec.writes.map((x) => x.phase + ' ' + x.method + ' ' + x.status + (x.byIdentity ? ' by-identity' : '') + (x.byName ? ' by-name' : '')) } : {}) };
    }
    // ★LEAVE THE BROWSER AS IT WAS FOUND (2026-10-12, 130 leaked Chrome processes, 10.9 GB committed): close and COUNT
    // anything this row left open, so a leak names itself
    let leakedPages = 0, leakedContexts = 0;
    for (const c of browser.contexts()) {
      if (c !== page.context()) { try { await c.close(); leakedContexts++; } catch (e) { void e; } continue; }
      for (const pg of c.pages()) { if (pg !== page) { try { await pg.close(); leakedPages++; } catch (e) { void e; } } }
    }
    out.push({ id: R.id, table: R.table, page: R.page, wrote: post.ok(), sum,
      ...((leakedPages || leakedContexts) ? { leaked: { pages: leakedPages, contexts: leakedContexts } } : {}) });
  }
  return out;
}
