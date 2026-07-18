// b3_diagnostic.mjs — dump the exact B3 offenders (sentences >20 words OR FK grade >8) per
// page, so a static one can be reworded and an AI-generated one traced to its prompt. Mirrors
// the survey's B3 grader. Reuses family_rubric_sweep's sign-in.
// USAGE: node tools/b3_diagnostic.mjs asset-hub.html ph-intelligence.html ...
import { chromium } from 'playwright';
const SEEDER = 'http://127.0.0.1:5000';
const EMAIL = 'pabloaguilar@auth.workhiveph.com', PASSWORD = 'test1234';
const HIVE = 'c9def338-fd73-4b19-8ef1-ee57625953d6', WORKER = 'Pablo Aguilar';
const QUERY = { 'marketplace-seller-profile.html': '?worker=Bryan%20Garcia' };
const REVEAL = { 'project-report.html': /generate/i };
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
  if (REVEAL[file]) { await page.evaluate((re) => { const rx = new RegExp(re, 'i'); const b = [...document.querySelectorAll('button,[onclick]')].find((el) => el.offsetParent && rx.test(el.textContent || '')); if (b) b.click(); }, REVEAL[file].source); await page.waitForTimeout(2000); }
  const out = await page.evaluate(() => {
    const vis = (e) => { if (!e || e.offsetParent === null) return false; const s = getComputedStyle(e); return s.display !== 'none' && s.visibility !== 'hidden'; };
    const ownText = (e) => [...e.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent.trim()).join(' ').trim();
    const cands = ['.page', '#ar-print-wrapper', '#ar-page', 'main'].map((sel) => document.querySelector(sel)).filter((el) => el && el.children.length > 0);
    const weigh = (el) => (el.innerText || '').trim().length + el.querySelectorAll('h1,h2,h3,table').length * 40;
    const R = cands.length ? cands.reduce((b, e) => (weigh(e) > weigh(b) ? e : b), cands[0]) : document.body;
    const textEls = [...R.querySelectorAll('*')].filter((e) => vis(e) && ownText(e).split(/\s+/).length >= 6);
    const syllables = (w) => { w = w.toLowerCase().replace(/[^a-z]/g, ''); if (w.length <= 3) return 1; w = w.replace(/(?:[^laeiouy]es|ed|[^laeiouy]e)$/, '').replace(/^y/, ''); const m = w.match(/[aeiouy]{1,2}/g); return m ? m.length : 1; };
    const fk = (str) => { const words = str.split(/\s+/).filter(Boolean); const syl = words.reduce((a, w) => a + syllables(w), 0); return 0.39 * words.length + 11.8 * (syl / Math.max(words.length, 1)) - 15.59; };
    const stripCite = (t) => t.replace(/\b(ISO|SMRP|SAE|JA)\s?[\d.:-]+(?:-\d+)?(?::\d{4})?/gi, '').replace(/\bBest Practices v[\d.]+/gi, '').replace(/§[\d.]+/g, '').replace(/\s{2,}/g, ' ').replace(/^[\s·:.-]+/, '').trim();
    const long = [], over = [];
    textEls.forEach((e) => {
      const raw = ownText(e);
      if ((raw.match(/·/g) || []).length >= 2) return;
      if (/\S\s*=\s*\S/.test(raw) && /[×÷*/+%]|\d/.test(raw)) return;
      raw.split(/(?<=[.!?])\s+/).forEach((sen) => {
        const t = sen.trim(); if (t.split(/\s+/).length < 4) return;
        if (t.split(/\s+/).length > 20) long.push(t);
        const st = stripCite(t); if (st.split(/\s+/).length >= 12 && fk(st) > 8) over.push({ g: +fk(st).toFixed(1), t: st });
      });
    });
    return { long, over };
  });
  console.log(`\n=== ${file} ===`);
  out.long.forEach((t) => console.log(`  >20w: "${t.slice(0, 100)}"`));
  out.over.forEach((o) => console.log(`  grade ${o.g}: "${o.t.slice(0, 110)}"`));
  if (!out.long.length && !out.over.length) console.log('  (clean now)');
  await page.close();
}
await browser.close();
