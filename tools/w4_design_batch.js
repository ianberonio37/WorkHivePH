// w4_design_batch.js - run SEVERAL design-lens rows through the Playwright MCP in one `browser_run_code_unsafe
// { filename }` call (2026-10-12). Each row is still its own walk - its own fresh page, its own receipt POSTed to the
// seeder - exactly as tools/w4_design_walk.js would run it; the batch saves the round trips and returns the compact
// measures each lens is judged on. Parameters: .tmp/w4_design_batch.json = [ <one args object per row> ], written by
// .tmp/design_driver.py --batch-arm.
async (page) => {
  const base = 'http://localhost:5000/workhive';
  const res = await page.request.get(`${base}/tools/w4_design_walk.body.js`, { timeout: 8000 });
  if (!res.ok()) return { problems: [`could not load the walker body: HTTP ${res.status()}`] };
  const src = await res.text();
  const br = await page.request.get(`${base}/.tmp/w4_design_batch.json`, { timeout: 8000 });
  if (!br.ok()) return { problems: [`no batch file: HTTP ${br.status()}`] };
  const batch = await br.json();
  const out = [];
  // ★A BATCH MUST LEAVE THE BROWSER AS IT FOUND IT (2026-10-12): after ~250 walks the MCP's Chrome held 130 processes and
  // 10.9 GB of committed memory, and the host ran out of commit (MemoryError in every Python process). Every page and
  // context a walk leaves behind is closed after its row and COUNTED, so the leak names its walker instead of hiding.
  const sweep = async () => {
    let pages = 0, contexts = 0;
    for (const ctx of page.context().browser().contexts()) {
      if (ctx !== page.context()) { try { await ctx.close(); contexts++; } catch (e) { void e; } continue; }
      for (const pg of ctx.pages()) {
        if (pg !== page) { try { await pg.close(); pages++; } catch (e) { void e; } }
      }
    }
    return { pages, contexts };
  };
  for (const args of batch) {
    globalThis.__W4 = Object.assign({}, args, { compact: true });
    let r;
    try {
      const walk = eval('(' + src + '\n)');
      r = await walk(page);
    } catch (e) {
      r = { id: args.id, problems: ['the walk threw: ' + String(e.message || e).slice(0, 120)] };
    } finally {
      globalThis.__W4 = undefined;
    }
    const left = await sweep();
    if (left.pages || left.contexts) r.leaked = left;
    out.push(r);
  }
  return out;
}
