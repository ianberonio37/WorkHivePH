// validate_read_battery.mjs — LIVE per-page P3 read-correctness + P7 empty/error gate (PER_PAGE_BUGHUNT).
//
// Signs in ONCE as the Baguio supervisor (reuses the live_page_journeys / hive_battery recipe) and,
// for each READ-HEAVY page, locks the read path against regression by comparing what the page RENDERS
// to the DB truth (docker-psql admin) for the signed-in hive. Three assertion tiers:
//
//   exact-count      the page's primary list container renders EXACTLY the DB row count (capped at the
//                    page's own .limit()).  e.g. audit-log #feed == count(hive_audit_log) [<=500].
//   empty-consistency  DB has 0 rows -> page shows an EMPTY-STATE (not an error, not a stuck skeleton)
//                    and its hero counters read 0; DB has >0 -> NOT the empty state. (reseed-robust)
//   render-state     no error banner, no stuck skeleton after settle, and data-presence is consistent:
//                    DB>0 -> the primary data container renders >=1 real child; DB==0 -> empty-state.
//
// This is the render-layer complement to truth-view-read-isolation (which proves the DATA layer / RLS).
// A regression (page shows stale/dropped/mangled data, an error swallowed as empty, or a stuck skeleton)
// FAILs. Reseed-robust: every expectation is derived from a live DB count, never a hard-coded number.
//
// USAGE:  node tools/validate_read_battery.mjs [--headed]   ·  exit 0 = all PASS · exit 1 = any FAIL
import { chromium } from 'playwright';
import { execSync } from 'child_process';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SUPABASE_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
// RESOLVED, NOT PINNED. The old fallback `636cf7e8-…` had been reseeded out of existence, and every
// assertion here silently started measuring an EMPTY WORLD: six pages reported "DB empty -> empty-state
// (no error)" with db=0, which reads as six specific page defects and is really one dead UUID.
// A literal cannot survive a reseed, so resolve the signed-in supervisor's own most-populated hive and
// tie-break by id — deterministic, so two runs never disagree ([[feedback_resolving_live_is_not_enough_be_deterministic]]).
function resolveHive() {
  if (process.env.WH_TEST_HIVE) return process.env.WH_TEST_HIVE;
  try {
    const sql = "select hm.hive_id::text from hive_members hm "
      + "join worker_profiles wp on wp.auth_uid = hm.auth_uid "
      + "left join logbook l on l.hive_id = hm.hive_id "
      + "where wp.username = 'leandromarquez' and hm.status = 'active' "
      + "group by hm.hive_id order by count(l.id) desc, hm.hive_id asc limit 1";
    const out = execSync(
      `docker exec ${process.env.WH_DB_CONTAINER || 'supabase_db_workhive'} psql -U postgres -d postgres -t -A -c "${sql}"`,
      { encoding: 'utf8' }).trim();
    if (out) return out;
  } catch (_) { /* fall through: the guard below reports it rather than measuring nothing */ }
  return '';
}
const HIVE = resolveHive();
if (!HIVE) {
  console.error('FAIL: could not resolve a test hive. Refusing to run — a battery with no hive '
    + 'measures an empty world and reports every page as broken.');
  process.exit(1);
}
const SUP = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234', worker: 'Leandro Marquez' };
const DB = process.env.WH_DB_CONTAINER || 'supabase_db_workhive';
const HEADED = process.argv.includes('--headed');

// Per-page read-correctness spec. src = primary hive-scoped source; container = primary DATA region
// (nav chrome excluded). cap = the page's own .limit() (for exact-count).
const SPECS = [
  // cap is the PAGE SIZE, not the query limit. audit-log fetches .limit(500) but renders
  // _auditDisplayCount = 30 behind a "Load more" button, so comparing the rendered count to the full
  // row count asserted that pagination is a bug. 30-of-187 is the page working.
  { page: 'audit-log.html',         src: 'hive_audit_log',          type: 'exact-count',       container: '#feed',        cap: 30 },
  { page: 'integrations.html',      src: 'integration_configs',     type: 'empty-consistency', heroes: ['#it-active-hero', '#it-stale-hero', '#it-disabled-hero'], emptyIn: '#sync-configs-list' },
  // #wh-conn-queue never existed on this page. Its real regions are #content (the connections) and
  // #empty-state (the emptiness signal), so the claim is render-state, not a hero count.
  { page: 'plant-connections.html', src: 'v_external_sync_truth',   type: 'render-state',      container: '#content', emptyIn: '#empty-state', allowGate: true },
  { page: 'public-feed.html',       src: 'v_community_posts_truth', type: 'render-state',      container: '#feed-list' },
  { page: 'project-report.html',    src: 'v_project_truth',         type: 'render-state',      container: '#ar-print-wrapper' },
  { page: 'shift-brain.html',       src: 'shift_plans',             type: 'render-state',      container: '#carry-list' },
  { page: 'analytics.html',         src: 'v_logbook_truth',         type: 'render-state',      container: '#results-panel' },
  { page: 'ai-quality.html',        src: 'ai_cost_log',             type: 'render-state',      container: '#content', allowGate: true },
  { page: 'alert-hub.html',         src: 'v_alert_truth',           type: 'render-state',      container: '#feed', allowGate: true },
  { page: 'project-manager.html',   src: 'projects',                type: 'render-state',      container: '#card-grid' },
  { page: 'analytics-report.html',  src: 'v_logbook_truth',         type: 'render-state',      container: '#ar-report-mount', allowGate: true },
  { page: 'ph-intelligence.html',   src: 'ph_intelligence_reports', type: 'render-state',      container: '#exec-summary-card', noHive: true, allowGate: true },
  { page: 'index.html',             src: 'v_pm_compliance_truth',   type: 'render-state',      container: '#oh-stats', allowGate: true },
];

function adminQuery(sql) {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const out = execSync(`docker exec ${DB} psql -U postgres -d postgres -t -A -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim();
      if (out !== '') return out; // empty = transient (expensive view under load) -> retry once
    } catch { /* retry */ }
  }
  return null;
}

const results = [];
const check = (name, ok, detail) => results.push({ ok: !!ok, name, detail: detail || '' });
const skip  = (name, detail) => results.push({ ok: true, skipped: true, name, detail: detail || '' });

// A 429 is a real SERVER ANSWER, not render drift. The hive's AI ceiling is 300 calls/day
// (DEFAULT_RATE_LIMIT_PER_DAY, _shared/rate-limit.ts) on a rolling 24h window, and a day of local
// suite runs spends it — measured 2026-08-20: day_count 300/300, window resetting 19:06 UTC. When
// that happened this gate failed alert-hub and printed "a read-correctness regression (render
// drift / swallowed error / stuck skeleton)", which is a cause it never measured: the page read
// correctly, the quota simply said no. Classifying it honestly keeps the gate believable.
// TEETH ARE PRESERVED: only rate-limit lines are excused, and ONLY when every captured error is
// one. Any other console error still FAILs, and a 429 mixed with a real error still FAILs.
const isRateLimit = (t) => /\b429\b|too many requests|rate.?limit/i.test(t || '');

(async () => {
  const browser = await chromium.launch({ headless: !HEADED });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 160)); });

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
    check('sign-in supervisor', si.ok, si.err || '');
    if (!si.ok) throw new Error('sign-in failed — cannot run read battery');

    for (const spec of SPECS) {
      const countSql = spec.noHive ? `select count(*) from ${spec.src}` : `select count(*) from ${spec.src} where hive_id='${HIVE}'`;
      const dbCount = parseInt(adminQuery(countSql) ?? 'NaN', 10);
      consoleErrors.length = 0;
      await page.goto(`${SEEDER}/workhive/${spec.page}`, { waitUntil: 'domcontentloaded' });
      // Wait for the primary data region to actually populate (or an intentional empty/gate state to
      // settle) before reading — deterministic vs. a bare fixed timeout under browser load. Best-effort.
      if (spec.container && dbCount > 0) {
        await page.waitForFunction((sel) => {
          const el = document.querySelector(sel);
          const populated = el && Array.from(el.children).some(k => (k.textContent || '').trim().length);
          const alt = /reach stair|stair 2|maturity|no .* (yet|found)|is empty|no data/i.test(document.body.innerText || '');
          return populated || alt;
        }, spec.container, { timeout: 6000 }).catch(() => {});
      }
      await page.waitForTimeout(2600);
      const dom = await page.evaluate(({ container, heroes, emptyIn }) => {
        const txt = document.body.innerText || '';
        const errBanner = /failed to load|unexpected error|something went wrong|could not load|couldn.t load/i.test(txt);
        const EMPTY_RE = /no .* (yet|found)|nothing here|no results|is empty|no data|no activity/i;
        // Scoped: a page may legitimately carry several secondary empty panels while its PRIMARY data
        // renders. `emptyIn` names the region whose emptiness is the claim; without it we fall back to
        // the whole document, which is what produced a false failure on a page that was working.
        const emptyScope = emptyIn ? document.querySelector(emptyIn) : null;
        const emptyState = EMPTY_RE.test(emptyScope ? (emptyScope.innerText || '') : txt);
        // an intentional maturity/honest-empty gate is a VALID render (not a bug) — feedback_platform_intentional_blank_states
        const gateShown = /reach stair|stair 2|maturity|activates with real|needs real signal|this page fills|log 30 days/i.test(txt);
        const visSkel = Array.from(document.querySelectorAll('.skeleton,.shimmer,[class*="skeleton"]')).filter(s => s.offsetParent !== null).length;
        let childCount = null, containerFound = false;
        if (container) {
          const el = document.querySelector(container);
          if (el) { containerFound = true; childCount = Array.from(el.children).filter(k => (k.textContent || '').trim().length).length; }
        }
        const heroVals = (heroes || []).map(h => { const el = document.querySelector(h); const m = el ? (el.textContent || '').replace(/[, ]/g, '').match(/-?\d+/) : null; return m ? parseInt(m[0], 10) : null; });
        // A hero selector that does not exist yields 0 and accuses the page of rendering nothing —
        // `#wh-conn-queue` was named for a page whose ids are content/details-pane/empty-state. An
        // instrument must know when its own selector is gone rather than report a phantom zero.
        const missingSel = (heroes || []).filter(sel => !document.querySelector(sel));
        return { errBanner, emptyState, gateShown, visSkel, childCount, containerFound, heroVals, missingSel };
      }, { container: spec.container, heroes: spec.heroes, emptyIn: spec.emptyIn });

      const tag = `${spec.page} [db=${dbCount}]`;
      // universal: no swallowed error, no stuck skeleton, no console error on load
      check(`${tag} · every declared selector exists on the page`,
            (dom.missingSel || []).length === 0,
            `missing=${(dom.missingSel || []).join(',')} — the SPEC is stale, not the page`);
      check(`${tag} · no error banner`, !dom.errBanner);
      check(`${tag} · no stuck skeleton after settle`, dom.visSkel === 0, `visibleSkeletons=${dom.visSkel}`);
      const rl = consoleErrors.filter(isRateLimit);
      if (consoleErrors.length > 0 && rl.length === consoleErrors.length) {
        skip(`${tag} · zero console errors on load`,
             `SKIPPED — every error is the hive's AI day-ceiling answering 429, not a read defect: ` +
             consoleErrors.slice(0, 2).join(' | '));
      } else {
        check(`${tag} · zero console errors on load`, consoleErrors.length === 0, consoleErrors.slice(0, 2).join(' | '));
      }

      if (spec.type === 'exact-count') {
        const expected = Math.min(dbCount, spec.cap ?? dbCount);
        check(`${tag} · ${spec.container} found`, dom.containerFound);
        check(`${tag} · rendered ${spec.container} count == DB (${dom.childCount} == ${expected})`, dom.childCount === expected, `ui=${dom.childCount} db=${expected}`);
      } else if (spec.type === 'empty-consistency') {
        if (dbCount === 0) {
          check(`${tag} · DB empty -> empty-state shown`, dom.emptyState);
          for (let i = 0; i < (spec.heroes || []).length; i++) check(`${tag} · hero ${spec.heroes[i]} reads 0`, dom.heroVals[i] === 0, `got ${dom.heroVals[i]}`);
        } else {
          check(`${tag} · DB has ${dbCount} -> NOT empty-state`, !dom.emptyState);
          check(`${tag} · at least one hero > 0`, dom.heroVals.some(v => (v || 0) > 0), `heroes=${dom.heroVals.join(',')}`);
        }
      } else { // render-state
        if (dbCount > 0) {
          const rendered = (dom.containerFound && (dom.childCount || 0) >= 1) || (spec.allowGate && dom.gateShown);
          check(`${tag} · ${spec.container} renders data OR intentional gate (DB>0)`, rendered, `found=${dom.containerFound} kids=${dom.childCount} gate=${dom.gateShown}`);
        } else if (dbCount === 0) {
          check(`${tag} · DB empty -> empty-state (no error)`, (dom.emptyState || (spec.allowGate && dom.gateShown)) && !dom.errBanner);
        } else { // count unavailable (NaN) — assert the page rendered SOME valid non-error state
          const validState = (dom.containerFound && (dom.childCount || 0) >= 1) || dom.emptyState || (spec.allowGate && dom.gateShown);
          check(`${tag} · rendered a valid state (count unavailable)`, validState && !dom.errBanner, `found=${dom.containerFound} kids=${dom.childCount} empty=${dom.emptyState} gate=${dom.gateShown}`);
        }
      }
    }
  } catch (e) {
    check('read battery ran to completion', false, String(e.message || e).slice(0, 160));
  } finally {
    await browser.close();
  }

  const failed = results.filter(r => !r.ok);
  console.log('\n── read-correctness battery (P3 rendered==DB · P7 empty/error) ──');
  const skipped = results.filter(r => r.skipped);
  // A SKIP must not read as a PASS. It is an invariant that was NOT decided, and printing it as
  // green is how a gate quietly shrinks its own coverage.
  for (const r of results) console.log(`  ${r.skipped ? 'SKIP' : (r.ok ? 'PASS' : 'FAIL')} · ${r.name}${r.detail ? '  [' + r.detail + ']' : ''}`);
  console.log(`\n${failed.length ? 'FAIL' : 'PASS'} · ${results.length - failed.length - skipped.length}/${results.length - skipped.length} invariants green` + (skipped.length ? ` · ${skipped.length} SKIPPED (rate-limited, not decided)` : ''));
  process.exit(failed.length ? 1 : 0);
})();
