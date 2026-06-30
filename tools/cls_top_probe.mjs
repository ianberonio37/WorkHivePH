// cls_top_probe.mjs — Arc L · L1: find the element that TRANSLATES (moves down) without
// itself growing — the residual CLS class that cls_reserve_probe (height-only) misses.
// Logs getBoundingClientRect().top at t0 (early, ~120ms) vs t1 (settled) for body's direct
// children + a key selector set, and reports who moved.  USAGE: node tools/cls_top_probe.mjs --page predictive.html
import { chromium } from 'playwright';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const EMAIL = process.env.WH_TEST_EMAIL || 'leandromarquez@auth.workhiveph.com';
const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const HIVE = '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7';
const WORKER = process.env.WH_TEST_WORKER || 'Leandro Marquez';
const args = process.argv.slice(2);
const PAGE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : 'predictive.html'; })();

const SNAP = `(() => {
  const out = {};
  const rec = (key, el) => { if (el) out[key] = Math.round(el.getBoundingClientRect().top); };
  let i = 0;
  for (const el of document.body.children) {
    const tag = el.tagName.toLowerCase();
    const id = el.id ? '#' + el.id : '';
    const cls = (el.className && typeof el.className === 'string') ? '.' + el.className.trim().split(/\\s+/)[0] : '';
    rec('body>' + (i++) + ' ' + tag + id + cls, el);
  }
  for (const sel of ['main', '.page', '#list-view', '.page-header', '#wh-source-chip', '#pr-verdict', '.verdict', '.simple-row', '.action-card', '#panel-ranking', '#ranking-table-wrap', 'h1', '#nav-hub', '#wh-nav', 'nav']) {
    const el = document.querySelector(sel); if (el) rec(sel, el);
  }
  return out;
})()`;

async function signIn(context) {
  const page = await context.newPage();
  await page.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
  await page.evaluate(async ({ email, password, hive, worker }) => {
    try {
      const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
      await db.auth.signInWithPassword({ email, password });
      localStorage.setItem('wh_active_hive_id', hive);
      localStorage.setItem('wh_last_worker', worker);
    } catch (e) {}
  }, { email: EMAIL, password: PASSWORD, hive: HIVE, worker: WORKER });
  await page.close();
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 780 } });
  await signIn(context);
  const page = await context.newPage();
  await page.goto(`${SEEDER}/workhive/${PAGE}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(120);
  const t0 = await page.evaluate(SNAP);
  await page.waitForTimeout(3800);
  const t1 = await page.evaluate(SNAP);
  const tree = await page.evaluate(`(() => {
    const out = [];
    const dump = (parentSel) => {
      const p = document.querySelector(parentSel); if (!p) return;
      const cs = getComputedStyle(p);
      out.push(parentSel + '  {pad-top:' + cs.paddingTop + ' mtop:' + cs.marginTop + ' display:' + cs.display + ' h:' + p.offsetHeight + '}');
      let i = 0;
      for (const c of p.children) {
        const s = getComputedStyle(c);
        const id = c.id ? '#'+c.id : '';
        const cls = (c.className && typeof c.className==='string') ? '.'+c.className.trim().split(/\\s+/)[0] : '';
        out.push('   '+(i++)+' '+c.tagName.toLowerCase()+id+cls+'  mtop:'+s.marginTop+' mbot:'+s.marginBottom+' display:'+s.display+' h:'+c.offsetHeight+' top:'+Math.round(c.getBoundingClientRect().top));
      }
    };
    dump('main'); dump('.page');
    return out.join('\\n');
  })()`);
  console.log('STRUCTURE @settled:\\n' + tree + '\\n');
  console.log(`TOP-position translation t0(~120ms) → t1(settled) for ${PAGE}:\n`);
  const keys = [...new Set([...Object.keys(t0), ...Object.keys(t1)])];
  for (const k of keys) {
    const a = t0[k], b = t1[k];
    if (a == null || b == null) { console.log(`    (only one snap) ${k}  t0=${a} t1=${b}`); continue; }
    const d = b - a;
    if (Math.abs(d) > 3) console.log(`    Δtop ${String(d).padStart(6)}px   ${k}   (${a}→${b})`);
  }
  await browser.close();
})();
