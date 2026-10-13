// w4_action_batch.js - run SEVERAL wave-4 action groups through the Playwright MCP in one `browser_run_code_unsafe
// { filename }` call (2026-10-08). Each group is still its own walk - its own fresh page, its own clean origin, its own
// receipt POSTed to the seeder - exactly as tools/w4_action_walk.js would run it; the batch only saves the round trip.
// Parameters: .tmp/w4_args_batch.json = [ <one .tmp/w4_args.json object per group> ], written by a driver's `batch`.
async (page) => {
  const base = 'http://localhost:5000/workhive';
  const res = await page.request.get(`${base}/tools/w4_action_walk.body.js`, { timeout: 8000 });
  if (!res.ok()) return { problems: [`could not load the walker body: HTTP ${res.status()}`] };
  const src = await res.text();
  const br = await page.request.get(`${base}/.tmp/w4_args_batch.json`, { timeout: 8000 });
  if (!br.ok()) return { problems: [`no batch file: HTTP ${br.status()}`] };
  const batch = await br.json();
  const out = [];
  for (const args of batch) {
    globalThis.__W4 = args;   // the body merges its args file UNDER this, so each group walks with its own
    const walk = eval('(' + src + '\n)');
    const p = await page.context().newPage();
    try {
      const r = await walk(p);
      // a clean group reports one line; anything open or odd reports in full (the receipt on disk has everything)
      const allOk = !(r.problems || []).length && (r.answers || []).every((a) => a.ok);
      const short = (r.steps || []).filter((s) => (s.chars || 0) < 400).map((s) => `${s.page}:${s.chars}`);
      out.push(allOk ? `${r.id} OK${short.length ? ' (short pages: ' + short.join(' ') + ')' : ''}`
        : { id: r.id, pages: (r.steps || []).map((s) => `${s.page}:${s.chars}`).join(' '), problems: r.problems,
            answers: (r.answers || []).map((a) => `${a.id} ${a.ok ? 'OK' : 'OPEN'}: ${String(a.note || '').slice(0, 260)}`) });
    } catch (e) {
      out.push({ id: args.id, problems: ['the walk threw: ' + String(e.message || e).slice(0, 120)] });
    } finally {
      globalThis.__W4 = undefined;
      try { if (!p.isClosed()) await p.close(); } catch (e) { void e; }
    }
  }
  return out;
}
