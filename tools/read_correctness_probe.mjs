// read_correctness_probe.mjs — DISCOVERY probe for the P3 read-correctness gate (PER_PAGE_BUGHUNT).
//
// Signs in ONCE as the Baguio supervisor (reuses the live_page_journeys / hive_battery recipe), then
// per read-heavy page: computes the DB-truth count (docker psql admin) for the page's primary source,
// loads the page, and AUTO-DISCOVERS render anchors = DOM elements whose integer textContent EQUALS
// that DB count. Prints, per page, the candidate anchor selectors + the primary repeated-container
// child count + whether an error/empty state is showing. Output feeds the encoded gate specs.
//
// USAGE:  node tools/read_correctness_probe.mjs [--headed]
import { chromium } from 'playwright';
import { execSync } from 'child_process';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SUPABASE_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const HIVE = process.env.WH_TEST_HIVE || '636cf7e8-431a-4907-8a9f-43dd4cc216d6';
const SUP = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234', worker: 'Leandro Marquez' };
const DB = process.env.WH_DB_CONTAINER || 'supabase_db_workhive';
const HEADED = process.argv.includes('--headed');

// page -> primary hive-scoped source. kind: 'count' (list length) | 'aggregate' (KPI number)
const PAGES = [
  { page: 'audit-log.html',      src: 'hive_audit_log',            kind: 'count' },
  { page: 'project-report.html', src: 'v_project_truth',           kind: 'count' },
  { page: 'shift-brain.html',    src: 'shift_plans',               kind: 'count' },
  { page: 'public-feed.html',    src: 'v_community_posts_truth',   kind: 'count' },
  { page: 'ai-quality.html',     src: 'ai_cost_log',               kind: 'aggregate' },
  { page: 'analytics.html',      src: 'v_logbook_truth',           kind: 'aggregate' },
  { page: 'integrations.html',   src: 'integration_configs',       kind: 'count' },
  { page: 'plant-connections.html', src: 'v_external_sync_truth',  kind: 'count' },
];

function adminQuery(sql) {
  try { return execSync(`docker exec ${DB} psql -U postgres -d postgres -t -A -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); }
  catch { return null; }
}

(async () => {
  const browser = await chromium.launch({ headless: !HEADED });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  try {
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
    console.log(`sign-in: ${si.ok ? 'OK' : 'FAIL ' + si.err}`);
    if (!si.ok) throw new Error('sign-in failed');

    for (const spec of PAGES) {
      const dbCount = parseInt(adminQuery(`select count(*) from ${spec.src} where hive_id='${HIVE}'`) ?? 'NaN', 10);
      await page.goto(`${SEEDER}/workhive/${spec.page}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(4200);
      const dom = await page.evaluate((target) => {
        const txt = document.body.innerText || '';
        const inChrome = (el) => el.closest('#wh-hub-tiles, header, nav, footer, #wh-nav, .wh-nav, #wh-app-header, #toast');
        // anchors: elements whose integer text EXACTLY equals the DB count
        const anchors = [];
        if (Number.isFinite(target)) {
          for (const el of document.querySelectorAll('*')) {
            if (el.children.length || inChrome(el)) continue; // leaf, non-chrome
            const t = (el.textContent || '').replace(/[, ]/g, '').trim();
            if (/^-?\d+$/.test(t) && parseInt(t, 10) === target) {
              anchors.push(el.id ? `#${el.id}` : `${el.tagName.toLowerCase()}${el.className && typeof el.className==='string' ? '.'+el.className.trim().split(/\s+/)[0] : ''}`);
            }
          }
        }
        // primary DATA containers (exclude nav/chrome): rank by repeated-child count
        const containers = [];
        for (const el of document.querySelectorAll('div[id],ul[id],tbody,section[id],div.card-body,div.results,#results-panel')) {
          if (inChrome(el)) continue;
          const kids = Array.from(el.children).filter(k => (k.textContent || '').trim().length);
          if (kids.length < 1) continue;
          const sel = el.id ? '#' + el.id : (el.tagName.toLowerCase() + (el.className && typeof el.className==='string' ? '.'+el.className.trim().split(/\s+/)[0] : ''));
          containers.push({ sel, kids: kids.length });
        }
        containers.sort((a, b) => b.kids - a.kids);
        const skeletons = document.querySelectorAll('.skeleton,.shimmer,[class*="skeleton"],[class*="loading"]');
        const visSkel = Array.from(skeletons).filter(s => s.offsetParent !== null).length;
        return {
          anchors: [...new Set(anchors)].slice(0, 6),
          containers: containers.slice(0, 5),
          visSkel,
          errBanner: /failed to load|unexpected error|something went wrong|could not load/i.test(txt),
          emptyState: /no .* (yet|found)|nothing here|get started|no results|is empty|no data/i.test(txt),
        };
      }, dbCount);
      console.log(`\n== ${spec.page}  [${spec.src}]  dbCount=${dbCount}  kind=${spec.kind}`);
      console.log(`   anchors(text==${dbCount}): ${dom.anchors.length ? dom.anchors.join(' , ') : '(none)'}`);
      console.log(`   data-containers: ${dom.containers.map(c => c.sel + ' x' + c.kids).join('  |  ') || '(none)'}`);
      console.log(`   visibleSkeletons=${dom.visSkel}  errBanner=${dom.errBanner}  emptyStateText=${dom.emptyState}`);
    }
  } catch (e) {
    console.log('PROBE ERROR:', String(e.message || e).slice(0, 200));
  } finally {
    await browser.close();
  }
})();
