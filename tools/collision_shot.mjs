// collision_shot.mjs — screenshot the chrome-collision states. USAGE: node tools/collision_shot.mjs
import { chromium } from 'playwright';
const S = 'http://127.0.0.1:5000', E = 'pabloaguilar@auth.workhiveph.com', P = 'test1234', H = 'c9def338-fd73-4b19-8ef1-ee57625953d6';
const OUT = process.argv[2] || '.';
const b = await chromium.launch(); const c = await b.newContext({ viewport: { width: 1280, height: 900 } });
const s = await c.newPage();
await s.goto(`${S}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
await s.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
await s.evaluate(async ({ e, p, h }) => { try { const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY); await db.auth.signInWithPassword({ email: e, password: p }); localStorage.setItem('wh_active_hive_id', h); localStorage.setItem('wh_last_worker', 'Pablo Aguilar'); localStorage.setItem('wh_hive_role', 'supervisor'); } catch (x) {} }, { e: E, p: P, h: H });
await s.close();
for (const file of ['dayplanner.html', 'logbook.html']) {
  const pg = await c.newPage();
  await pg.goto(`${S}/workhive/${file}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await pg.waitForTimeout(6000);
  const nm = file.replace('.html', '');
  await pg.screenshot({ path: `${OUT}/shot_${nm}_default.png` });
  // report fixed/floating elements + their boxes (the chrome that collides)
  const fixed = await pg.evaluate(() => {
    const out = [];
    document.querySelectorAll('*').forEach((e) => {
      const cs = getComputedStyle(e);
      if ((cs.position === 'fixed' || cs.position === 'sticky') && cs.opacity !== '0' && cs.visibility !== 'hidden' && e.offsetParent !== null) {
        const r = e.getBoundingClientRect();
        if (r.width > 6 && r.height > 6 && r.width < 700) out.push({ id: e.id || '', cls: (typeof e.className === 'string' ? e.className : '').slice(0, 24), t: (e.innerText || '').trim().slice(0, 18), x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) });
      }
    });
    return out;
  });
  console.log(`\n=== ${file} fixed/floating elements ===`);
  fixed.forEach((f) => console.log(`  ${f.id || f.cls || '?'} "${f.t}" @(${f.x},${f.y}) ${f.w}x${f.h}`));
  // open the nav-hub (reveals companion) + re-shot
  await pg.evaluate(() => { const f = document.querySelector('#wh-hub-fab, .wh-hub-fab, [data-nav-hub]'); if (f) f.click(); });
  await pg.waitForTimeout(1200);
  await pg.screenshot({ path: `${OUT}/shot_${nm}_hubopen.png` });
  await pg.close();
}
await b.close();
