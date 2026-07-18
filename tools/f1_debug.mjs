// f1_debug.mjs — find the F1 offenders on a page at 390px + report tag/pos/container/size. USAGE: node tools/f1_debug.mjs dayplanner.html
import { chromium } from 'playwright';
const SEEDER = 'http://127.0.0.1:5000';
const EMAIL = 'pabloaguilar@auth.workhiveph.com', PASSWORD = 'test1234';
const HIVE = 'c9def338-fd73-4b19-8ef1-ee57625953d6', WORKER = 'Pablo Aguilar';
const file = process.argv[2];
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const s = await context.newPage();
await s.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
await s.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
await s.evaluate(async ({ email, password, hive, worker }) => {
  try { const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
    await db.auth.signInWithPassword({ email, password });
    localStorage.setItem('wh_active_hive_id', hive); localStorage.setItem('wh_last_worker', worker); localStorage.setItem('wh_hive_role', 'supervisor');
  } catch (e) {} }, { email: EMAIL, password: PASSWORD, hive: HIVE, worker: WORKER });
await s.close();
const page = await context.newPage();
await page.goto(`${SEEDER}/workhive/${file}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(4000);
await page.setViewportSize({ width: 390, height: 780 });
await page.waitForTimeout(900);
const out = await page.evaluate(() => {
  const inter = [...document.querySelectorAll('a, button, [role="button"], input, select, [onclick], [tabindex]')];
  const small = inter.filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && (r.width < 44 || r.height < 44) && e.offsetParent !== null; });
  return small.slice(0, 8).map((e) => {
    const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
    const cont = e.closest('.calendar-wrap, [class*="calendar"], [class*="timeline"], [class*="sched"]');
    return { tag: e.tagName, t: (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0, 20), w: Math.round(r.width), h: Math.round(r.height), pos: cs.position, cls: (typeof e.className === 'string' ? e.className : '').slice(0, 30), inCalendar: !!cont, contId: cont ? (cont.id || cont.className.slice(0, 20)) : '-' };
  });
});
out.forEach((o) => console.log(`${o.tag} "${o.t}" ${o.w}x${o.h} pos=${o.pos} inCal=${o.inCalendar}(${o.contId}) cls="${o.cls}"`));
await page.close();
await browser.close();
