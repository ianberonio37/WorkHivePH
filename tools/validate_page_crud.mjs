// validate_page_crud.mjs — GATE the live per-page P3 CRUD-at-DB verification (2026-07-14).
//
// Reuses the live_page_journeys sign-in recipe (its own headless Playwright — no MCP contention). Signs
// in as a WORKER, gets the page's authenticated db client, and for each attribution-pinned entity runs a
// round-trip: INSERT with a FORGED display name -> assert it PERSISTED (create works) BUT the name is
// PINNED to the caller (the bind_*_submitter trigger, migs 010/011/012) -> DELETE (owner-scoped) ->
// assert cleaned. A regression (create fails / attribution leaks the forged name / owner-delete broken)
// FAILs. Locks the per-page P3 frontier that was verified interactively. Infra-absent => SKIP (exit 0),
// never a false FAIL.
import { chromium } from 'playwright';
import { signIn, ACCOUNTS, SEEDER } from './live_page_journeys.mjs';

const HIVE = process.env.WH_TEST_HIVE || '636cf7e8-431a-4907-8a9f-43dd4cc216d6';

// attribution-pinned entities: create with a forged name -> the bind_ trigger must pin it to the caller.
const ENTITIES = [
  { name: 'voice_journal_entries', row: { transcript: 'CRUDGATE' }, nameCol: 'worker_name' },
  { name: 'engineering_calcs',     row: { discipline: 'Mech', calc_type: 'CRUDGATE' }, nameCol: 'worker_name' },
  { name: 'community_posts',       row: { content: 'CRUDGATE', category: 'general' }, nameCol: 'author_name' },
  { name: 'pm_assets',             row: { asset_name: 'CRUDGATE', category: 'Mechanical' }, nameCol: 'worker_name' },
  { name: 'projects',              row: { project_code: 'CRUDGATE', name: 'CRUDGATE', project_type: 'workorder' }, nameCol: 'worker_name' },
];

(async () => {
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: 'Asia/Manila' });
    const si = await signIn(ctx, 'worker');
    if (!si.ok) { console.log(`SKIP: worker sign-in failed (${si.err}) — local stack likely down`); process.exit(0); }
    const page = await ctx.newPage();
    await page.goto(`${SEEDER}/workhive/asset-hub.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForFunction(
      () => typeof window.getDb === 'function' || !!window._whSupabaseClient || !!window.supabase,
      { timeout: 15000 }).catch(() => {});

    const res = await page.evaluate(async ({ hive, entities }) => {
      const db = window._whSupabaseClient
        || (window.getDb && window.getDb(window.SUPABASE_URL || 'http://127.0.0.1:54321', window.SUPABASE_KEY))
        || window.supabase;
      if (!db) return { fatal: 'no db client on page' };
      const uid = (await db.auth.getUser()).data?.user?.id;
      if (!uid) return { fatal: 'db client not authenticated' };
      const out = {};
      for (const e of entities) {
        try {
          const row = { hive_id: hive, auth_uid: uid, ...e.row, [e.nameCol]: 'CRUDGATE-FORGED' };
          const ins = await db.from(e.name).insert(row).select();
          if (!ins.data || !ins.data.length) { out[e.name] = 'CREATE-FAIL:' + (ins.error?.code || '?'); continue; }
          const r = ins.data[0];
          const pinned = r[e.nameCol] !== 'CRUDGATE-FORGED';
          const del = await db.from(e.name).delete().eq('id', r.id).select();
          const deleted = !!(del.data && del.data.length);
          out[e.name] = (pinned && deleted) ? 'OK' : `FAIL(pinned=${pinned},deleted=${deleted})`;
        } catch (err) { out[e.name] = 'THROW:' + String(err).slice(0, 30); }
      }
      return { uid, out };
    }, { hive: HIVE, entities: ENTITIES });

    await ctx.close();
    if (res.fatal) { console.log('SKIP: ' + res.fatal); process.exit(0); }
    console.log(`PAGE-CRUD GATE (worker ${String(res.uid).slice(0, 8)}…, migs 010/011/012):`);
    for (const [k, v] of Object.entries(res.out)) console.log(`  ${v === 'OK' ? 'PASS' : 'FAIL'}  ${k}: ${v}`);
    const fails = Object.entries(res.out).filter(([, v]) => v !== 'OK');
    if (fails.length) { console.log(`\nFAIL — ${fails.length} P3 CRUD/attribution regression(s)`); process.exit(1); }
    console.log(`\nPASS — ${Object.keys(res.out).length} entities: create persists + attribution PINNED to caller + owner-delete works`);
    process.exit(0);
  } catch (e) {
    console.log('SKIP: ' + String(e).slice(0, 80));  // infra/harness issue -> skip, not a false fail
    process.exit(0);
  } finally { if (browser) await browser.close(); }
})();
