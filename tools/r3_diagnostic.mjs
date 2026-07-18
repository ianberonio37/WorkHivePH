// r3_diagnostic.mjs — dump each control's ROLE (press/select/navigate) + SILHOUETTE (shape)
// + class, and the SAME-SHAPE-DIFFERENT-JOB collisions, per page. Mirrors survey R3's roleOf/
// shapeV so the fix (give select-chips a distinct pill shape from press-buttons) is targeted.
// USAGE: node tools/r3_diagnostic.mjs index.html marketplace.html ...
import { chromium } from 'playwright';
const SEEDER = 'http://127.0.0.1:5000';
const EMAIL = 'pabloaguilar@auth.workhiveph.com', PASSWORD = 'test1234';
const HIVE = 'c9def338-fd73-4b19-8ef1-ee57625953d6', WORKER = 'Pablo Aguilar';
const QUERY = { 'marketplace-seller-profile.html': '?worker=Bryan%20Garcia' };
const pages = process.argv.slice(2);

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

for (const file of pages) {
  const page = await context.newPage();
  await page.goto(`${SEEDER}/workhive/${file}${QUERY[file] || ''}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(3200);
  const out = await page.evaluate(() => {
    const $$ = (s, r) => [...(r || document).querySelectorAll(s)];
    const vis = (e) => { if (!e || e.offsetParent === null) return false; const s = getComputedStyle(e); return s.display !== 'none' && s.visibility !== 'hidden'; };
    const rgb = (s) => { const m = (s || '').match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/); return m ? { a: m[4] === undefined ? 1 : +m[4] } : null; };
    const cands = ['.page', '#ar-print-wrapper', '#ar-page', 'main'].map((sel) => document.querySelector(sel)).filter((el) => el && el.children.length > 0);
    const weigh = (el) => (el.innerText || '').trim().length + el.querySelectorAll('h1,h2,h3,table').length * 40;
    const R = cands.length ? cands.reduce((b, e) => (weigh(e) > weigh(b) ? e : b), cands[0]) : document.body;
    const shape = (e) => { const raw = getComputedStyle(e).borderTopLeftRadius; if (raw.includes('%')) return 'round'; const r = Math.round(parseFloat(raw) || 0); const h = e.getBoundingClientRect().height; return (h && r >= h / 2 - 1) ? 'pill' : `${r}px`; };
    const roleOf = (e) => {
      if (e.getAttribute('role') === 'tab' || e.closest('[role="tablist"]')) return 'navigate';
      if (e.hasAttribute('aria-pressed') && e.parentElement) { const st = getComputedStyle(e.parentElement); const joined = (st.gap === '0px' || st.gap === 'normal') && e.parentElement.children.length >= 2 && [...e.parentElement.children].every((c) => c.tagName === e.tagName); if (joined && parseFloat(getComputedStyle(e).borderRadius) === 0) return 'navigate'; }
      if (e.hasAttribute('aria-pressed') || e.hasAttribute('aria-selected')) return 'select';
      return 'press';
    };
    const isCardAnatomy = (e) => { const card = e.closest('.card, .simple-card, .board-card'); return card && e.getBoundingClientRect().width >= card.getBoundingClientRect().width * 0.9; };
    const drawsShape = (e) => { const st = getComputedStyle(e); const bg = rgb(st.backgroundColor); return parseFloat(st.borderTopWidth) > 0 || (bg && bg.a > 0.03) || (st.backgroundImage || '').includes('gradient'); };
    const shapeV = (e) => (roleOf(e) === 'navigate' ? 'bar' : shape(e));
    const ctrls = $$('button, a.refresh-btn, [role="tab"]', R).filter(vis).filter((e) => !isCardAnatomy(e) && drawsShape(e));
    const byShape = {};
    ctrls.forEach((e) => { (byShape[shapeV(e)] = byShape[shapeV(e)] || new Set()).add(roleOf(e)); });
    const collisions = Object.entries(byShape).filter(([, set]) => set.size > 1).map(([sh, set]) => `${sh}=${[...set].join('+')}`);
    // for each collision shape, list the offending controls (role, class, text)
    const detail = {};
    Object.keys(byShape).filter((sh) => byShape[sh].size > 1).forEach((sh) => {
      detail[sh] = ctrls.filter((e) => shapeV(e) === sh).map((e) => ({ role: roleOf(e), cls: String(e.className).slice(0, 26), txt: (e.textContent || '').trim().slice(0, 14) }));
    });
    // FULL per-control map (dedup by role|shape|class) so a fix can be planned without whack-a-mole
    const full = {};
    ctrls.forEach((e) => {
      const key = roleOf(e) + '|' + shapeV(e) + '|' + String(e.className).slice(0, 24) + '|' + (e.id || '');
      if (!full[key]) full[key] = { role: roleOf(e), shape: shapeV(e), cls: String(e.className).slice(0, 24), id: e.id || '', txt: (e.textContent || '').trim().slice(0, 14), n: 0 };
      full[key].n++;
    });
    return { silhouettes: [...new Set(ctrls.map(shapeV))], collisions, full: Object.values(full) };
  });
  console.log(`\n=== ${file} ===  silhouettes=[${out.silhouettes.join(',')}]  collisions=[${out.collisions.join(', ')}]`);
  out.full.sort((a, b) => (a.shape + a.role).localeCompare(b.shape + b.role)).forEach((c) => {
    console.log(`  ${c.shape.padEnd(6)} ${c.role.padEnd(8)} #${(c.id || '-').padEnd(16)} .${c.cls.padEnd(24)} "${c.txt}" x${c.n}`);
  });
  await page.close();
}
await browser.close();
