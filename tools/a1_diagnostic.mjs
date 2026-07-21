// a1_diagnostic.mjs — per-page A1 breakdown: the distinct >=20px font sizes (the `big`
// scatter that fails big<=2) AND the CTA candidates the lens sees (to tell a real "no primary
// action" gap from a lens miss). Reuses family_rubric_sweep's sign-in.
// USAGE: node tools/a1_diagnostic.mjs analytics.html hive.html ...
import { chromium } from 'playwright';
const SEEDER = 'http://127.0.0.1:5000';
const EMAIL = 'pabloaguilar@auth.workhiveph.com', PASSWORD = 'test1234';
const HIVE = 'c9def338-fd73-4b19-8ef1-ee57625953d6', WORKER = 'Pablo Aguilar'; // hive fallback only — signIn resolves live membership
const pages = process.argv.slice(2);

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const s = await context.newPage();
await s.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
await s.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
await s.evaluate(async ({ email, password, hive, worker }) => {
  try { const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
    const { data } = await db.auth.signInWithPassword({ email, password });
    // resolve the REAL hive from the live membership; the constant is a stale-known fallback
    let realHive = hive;
    try {
      const uid = data?.session?.user?.id;
      const { data: mem } = uid ? await db.from('hive_members').select('hive_id')
        .eq('auth_uid', uid).eq('status', 'active').limit(1).maybeSingle() : { data: null };
      if (mem && mem.hive_id) realHive = mem.hive_id;
    } catch (_) {}
    localStorage.setItem('wh_active_hive_id', realHive); localStorage.setItem('wh_last_worker', worker); localStorage.setItem('wh_hive_role', 'supervisor');
  } catch (e) {} }, { email: EMAIL, password: PASSWORD, hive: HIVE, worker: WORKER });
await s.close();

for (const file of pages) {
  const page = await context.newPage();
  await page.goto(`${SEEDER}/workhive/${file}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(3200);
  const r = await page.evaluate(() => {
    const $$ = (s, r) => [...(r || document).querySelectorAll(s)];
    const vis = (e) => { if (!e || e.offsetParent === null) return false; const s = getComputedStyle(e); return s.display !== 'none' && s.visibility !== 'hidden'; };
    const rgb = (s) => { const m = (s || '').match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/); return m ? { r:+m[1],g:+m[2],b:+m[3],a: m[4]===undefined?1:+m[4] } : null; };
    const cands = ['.page', '#ar-print-wrapper', '#ar-page', 'main'].map((sel) => document.querySelector(sel)).filter((el) => el && el.children.length > 0);
    const weigh = (el) => (el.innerText || '').trim().length + el.querySelectorAll('h1,h2,h3,table,.card,.simple-card').length * 40;
    const R = cands.length ? cands.reduce((b, e) => (weigh(e) > weigh(b) ? e : b), cands[0]) : document.body;
    const textEls = $$('*', R).filter((e) => vis(e) && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 1));
    const sizes = [...new Set(textEls.map((e) => Math.round(parseFloat(getComputedStyle(e).fontSize))))].filter((n) => n >= 20).sort((a, b) => b - a);
    const isFilled = (e) => { const st = getComputedStyle(e); const c = rgb(st.backgroundColor); const sat = c && c.a > 0.5 && Math.max(c.r,c.g,c.b) - Math.min(c.r,c.g,c.b) > 40; return sat || (st.backgroundImage || '').includes('gradient'); };
    const isSelection = (e) => e.getAttribute('role') === 'tab' || e.hasAttribute('aria-pressed') || /(^|\s)(view-tab|phase-tab|period-btn|tab-btn|seg-btn|segmented|toggle-opt)/.test(typeof e.className === 'string' ? e.className : '') || !!e.closest('[role="tablist"]');
    const pageFabs = $$('button[id^="fab-"], .fab', document.body).filter(vis).filter((f) => !/^wh-/.test(f.id || ''));
    const primaryRaw = $$('.ac-cta, .btn-generate, [class*="primary"]', R).filter(vis).concat($$('button, a[href]', R).filter(vis).filter(isFilled)).concat(pageFabs).filter((e) => !isSelection(e));
    const cta = [...new Map(primaryRaw.map((e) => [((e.innerText || '').trim().slice(0, 24) + '|' + String(e.className)), e])).values()];
    // ALSO list all buttons/links to see what a natural primary would be
    const allActions = $$('button, a[href]', R).filter(vis).filter((e) => (e.innerText || '').trim().length > 1 && !isSelection(e))
      .slice(0, 8).map((e) => ({ txt: (e.innerText || '').trim().slice(0, 20), cls: String(e.className).slice(0, 22), filled: isFilled(e) }));
    return { bigSizes: sizes, ctaCount: cta.length, cta: cta.map((e) => (e.innerText || '').trim().slice(0, 18)), actions: allActions };
  });
  console.log(`\n=== ${file} ===`);
  console.log(`  big(>=20px) distinct sizes = [${r.bigSizes.join(',')}]  (fails if >2)`);
  console.log(`  primaryCta = ${r.ctaCount}  ${r.cta.length ? '(' + r.cta.join(' | ') + ')' : ''}`);
  console.log(`  actions on page: ${r.actions.map((a) => a.txt + (a.filled ? '*' : '')).join(' · ') || '(none)'}`);
  await page.close();
}
await browser.close();
