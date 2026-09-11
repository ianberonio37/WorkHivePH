// prove_nav_mode - W3-JN's first product finding, locked (2026-09-08).
//
// THE DEFECT. nav-hub derives a display mode from wh_hive_role and PERSISTS it in wh_nav_mode; getMode()
// then preferred that stored value for ever. The first page a person meets renders the hub while nobody is
// signed in, so the derivation ran with NO role, returned 'field', and stored it. Measured live: a
// supervisor of Manila Electronics, signed in, wh_hive_role=supervisor, navigating with wh_nav_mode=field
// and a hub of 17 links holding NO Analytics, NO Alert Hub and NO Reports - three surfaces their own
// journeys end at. Every one of those pages works when you arrive by URL, which is why no per-page test
// could see it; only a walk from one page to the next can find that there is no way to GET there.
//
// THE REPAIR keeps the original intent - "existing users with an explicit choice keep it" - by recording
// WHY the mode was stored (wh_nav_mode_src: chosen | derived | guess). A chosen mode is never touched; a
// mode guessed before the role was known is re-derived once the role arrives.
//
// TEETH IN BOTH DIRECTIONS, because a repair that hands everyone the supervisor menu is a worse defect:
//   1. a WORKER still gets the tight field set
//   2. a SUPERVISOR who CHOSE Field keeps Field
//   3. a SUPERVISOR who chose nothing gets Analytics, the Alert Hub and Reports back
//
//   node tools/prove_nav_mode.mjs
import { chromium } from 'playwright';
import { takeBrowserSlot } from './browser_slot.mjs';

const ORIGIN = process.env.WH_SEEDER_URL ? `${process.env.WH_SEEDER_URL}/workhive` : 'http://127.0.0.1:5000/workhive';
const HIVE = 'b4f7fe63-92e1-4f8d-b96e-625c3f85ba61';
const WORKER = { name: 'Isidro Suarez', email: 'isidrosuarez@auth.workhiveph.com', role: 'worker' };
const BOSS = { name: 'Hector Salvador', email: 'hectorsalvador@auth.workhiveph.com', role: 'supervisor' };
// this host has one browser slot and the suite runs gates concurrently - queue, do not race
await takeBrowserSlot('nav-mode');
const browser = await chromium.launch();

async function check(label, who, chooseMode) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const s = await ctx.newPage();
  await s.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await s.waitForTimeout(4000);                                   // the hub renders while signed out
  await s.goto(`${ORIGIN}/shift-brain.html`, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await s.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 25000 }).catch(() => {});
  await s.evaluate(async ({ hive, w, choose }) => {
    const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
    await db.auth.signInWithPassword({ email: w.email, password: 'test1234' });
    localStorage.setItem('wh_active_hive_id', hive);
    localStorage.setItem('wh_last_worker', w.name);
    localStorage.setItem('wh_hive_role', w.role);
    if (choose) { localStorage.setItem('wh_nav_mode', choose); localStorage.setItem('wh_nav_mode_src', 'chosen'); }
  }, { hive: HIVE, w: who, choose: chooseMode || null });
  await s.close();

  const p = await ctx.newPage();
  await p.goto(`${ORIGIN}/logbook.html`, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await p.waitForTimeout(8000);
  const r = await p.evaluate(() => {
    const hub = document.querySelector('#wh-hub');
    const hrefs = hub ? Array.from(hub.querySelectorAll('a[href]')).map((a) => a.getAttribute('href')) : [];
    return { mode: localStorage.getItem('wh_nav_mode'), src: localStorage.getItem('wh_nav_mode_src'),
             role: localStorage.getItem('wh_hive_role'), links: hrefs.length,
             analytics: hrefs.includes('analytics.html'), alertHub: hrefs.includes('alert-hub.html') };
  });
  console.log(`  ${label.padEnd(34)} role=${r.role} mode=${r.mode} src=${r.src} links=${r.links} analytics=${r.analytics} alert-hub=${r.alertHub}`);
  await p.close();
  await ctx.close();
  return r;
}

const w = await check('a WORKER, no choice made', WORKER, null);
const c = await check('a SUPERVISOR who chose Field', BOSS, 'field');
const b = await check('a SUPERVISOR, no choice made', BOSS, null);
const fails = [];
if (w.mode !== 'field' || w.analytics) fails.push('a worker was handed the supervisor menu');
if (c.mode !== 'field') fails.push('an explicit choice was overwritten');
if (b.mode !== 'supervisor' || !b.analytics || !b.alertHub) fails.push('a supervisor still has no Analytics or Alert Hub');
console.log(fails.length ? '\nFAIL nav-mode repair - ' + fails.join('; ')
  : '\nPASS nav-mode repair - a worker keeps the field set, an explicit choice is kept, and a supervisor gets their own surfaces back');
await browser.close();
process.exitCode = fails.length ? 1 : 0;
