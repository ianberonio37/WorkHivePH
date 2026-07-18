// validate_hive_battery.mjs — LIVE per-page battery gate for hive.html (PER_PAGE_BUGHUNT_ROADMAP).
//
// Locks P1 (Smoke), P2 (Console+Network), P8 (Visual/overflow) to a regression-FAILing gate:
//   P1  page loads signed-in as supervisor, renders REAL data (no undefined/NaN/[object Object]),
//       primary anchor stats (#stat-open, #stat-members) EQUAL the DB truth, not the empty state,
//       and ZERO console errors on the hive.html load.
//   P2  every Supabase REST/RPC/auth/functions response during the load is < 400 (no silent 4xx/5xx).
//   P8  no horizontal overflow at 390px (mobile) or 1280px (desktop).
//
// Reuses the live_page_journeys sign-in recipe (signInWithPassword + localStorage identity) and the
// docker-psql privileged reader (adminQuery) as the DB source of truth. Ground-truth identity is the
// REAL Baguio hive 636cf7e8 (the harness HIVE constant 9b4eaeac is stale for these seeded accounts).
//
// USAGE:  node tools/validate_hive_battery.mjs [--headed]
//   exit 0 = all invariants PASS · exit 1 = any FAIL
import { chromium } from 'playwright';
import { execSync } from 'child_process';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SUPABASE_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const HIVE = process.env.WH_TEST_HIVE || '636cf7e8-431a-4907-8a9f-43dd4cc216d6'; // Baguio Textile Mills (real)
const SUP = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234', worker: 'Leandro Marquez' };
const DB_CONTAINER = process.env.WH_DB_CONTAINER || 'supabase_db_workhive';
const HEADED = process.argv.includes('--headed');

function adminQuery(sql) {
  try { return execSync(`docker exec ${DB_CONTAINER} psql -U postgres -d postgres -t -A -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); }
  catch (e) { return null; }
}

const results = [];
function check(name, ok, detail) { results.push({ ok: !!ok, name, detail: detail || '' }); }

(async () => {
  const browser = await chromium.launch({ headless: !HEADED });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  const consoleErrors = [];
  const badResponses = [];
  const API_RE = /\/(rest\/v1|rpc|auth\/v1|functions\/v1)\b/;
  page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200)); });
  page.on('response', r => {
    const s = r.status(), u = r.url();
    if (s >= 400 && API_RE.test(u)) badResponses.push(`${s} ${u.split('?')[0].replace(SUPABASE_URL, '')}`);
  });

  try {
    // ── sign in as supervisor (reuse live_page_journeys recipe) ──
    await page.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
    const si = await page.evaluate(async ({ email, password, hive, worker, url }) => {
      try {
        const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
        const { data, error } = await db.auth.signInWithPassword({ email, password });
        localStorage.setItem('wh_active_hive_id', hive);
        localStorage.setItem('wh_hive_name', 'Baguio Textile Mills');
        localStorage.setItem('wh_hive_role', 'supervisor');
        localStorage.setItem('wh_nav_mode', 'supervisor');
        localStorage.setItem('wh_last_worker', worker);
        return { ok: !error && !!data?.session, err: error ? String(error.message || error) : null };
      } catch (e) { return { ok: false, err: String(e) }; }
    }, { email: SUP.email, password: SUP.pw, hive: HIVE, worker: SUP.worker, url: SUPABASE_URL });
    check('P1 sign-in supervisor', si.ok, si.err || '');
    if (!si.ok) throw new Error('sign-in failed — cannot run battery');

    // ── load hive.html clean (reset capture buffers so only the board load counts) ──
    consoleErrors.length = 0; badResponses.length = 0;
    await page.goto(`${SEEDER}/workhive/hive.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(4500); // settle async render (RPC + HEAD probes)

    // ── DB truth ──
    const dbOpen = parseInt(adminQuery(`select count(*) from v_logbook_truth where hive_id='${HIVE}' and lower(status)='open'`), 10);
    const dbMembers = parseInt(adminQuery(`select count(*) from hive_members where hive_id='${HIVE}' and status='active'`), 10);

    // ── P1 render assertions ──
    const dom = await page.evaluate(() => {
      const txt = document.body.innerText;
      const bad = {};
      for (const m of ['undefined', 'NaN', '[object Object]', 'null null']) {
        const c = (txt.match(new RegExp(m.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')) || []).length;
        if (c) bad[m] = c;
      }
      const num = id => { const el = document.getElementById(id); if (!el) return null; const m = (el.textContent || '').replace(/[, ]/g, '').match(/-?\d+/); return m ? parseInt(m[0], 10) : null; };
      return {
        bad,
        emptyState: /Join or create a team/i.test(txt),
        statOpen: num('stat-open'),
        statMembers: num('stat-members'),
      };
    });

    check('P1 not the no-hive empty state', !dom.emptyState);
    check('P1 no bad render markers (undefined/NaN/[object Object])', Object.keys(dom.bad).length === 0, JSON.stringify(dom.bad));
    check('P1 #stat-open renders a number', dom.statOpen !== null, `got ${dom.statOpen}`);
    check('P1 #stat-open == DB open WOs', dom.statOpen === dbOpen, `ui=${dom.statOpen} db=${dbOpen}`);
    check('P1 #stat-members == DB active members', dom.statMembers === dbMembers, `ui=${dom.statMembers} db=${dbMembers}`);
    check('P1 zero console errors on board load', consoleErrors.length === 0, consoleErrors.slice(0, 3).join(' | '));

    // ── P2 network assertions ──
    check('P2 no 4xx/5xx on Supabase REST/RPC/auth/functions', badResponses.length === 0, badResponses.slice(0, 5).join(' | '));

    // ── P8 overflow assertions (mobile + desktop) ──
    for (const [w, label] of [[390, 'mobile-390'], [1280, 'desktop-1280']]) {
      await page.setViewportSize({ width: w, height: 900 });
      await page.waitForTimeout(600);
      const ovf = await page.evaluate(() => {
        const de = document.documentElement;
        return { over: de.scrollWidth > de.clientWidth + 1, sw: de.scrollWidth, cw: de.clientWidth };
      });
      check(`P8 no horizontal overflow @ ${label}`, !ovf.over, `scrollW=${ovf.sw} clientW=${ovf.cw}`);
    }
  } catch (e) {
    check('battery ran to completion', false, String(e.message || e).slice(0, 160));
  } finally {
    await browser.close();
  }

  const failed = results.filter(r => !r.ok);
  console.log('\n── hive.html LIVE battery (P1/P2/P8) ──');
  for (const r of results) console.log(`  ${r.ok ? 'PASS' : 'FAIL'} · ${r.name}${r.detail ? '  [' + r.detail + ']' : ''}`);
  console.log(`\n${failed.length ? 'FAIL' : 'PASS'} · ${results.length - failed.length}/${results.length} invariants green`);
  process.exit(failed.length ? 1 : 0);
})();
