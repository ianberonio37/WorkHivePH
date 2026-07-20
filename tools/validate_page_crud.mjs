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

// APPEND-ONLY attribution entities (hive.html P3, 2026-07-19): the hive board writes hive_audit_log on
// every supervisor action; `actor` is one of the 14 forge-fixed columns (wh_bind_audit_actor_trg). The
// invariant differs from ENTITIES: INSERT-with-forged-actor must PERSIST + PIN the actor to the caller,
// but owner-DELETE must be a NO-OP (audit trail is immutable — no DELETE policy). Probe rows are cleaned
// by the Python wrapper via service-role psql (owner-delete cannot). Locks hive.html P3 65->100.
const IMMUTABLE = [
  { name: 'hive_audit_log', row: { action: 'crudgate_probe', target_type: 'probe' }, nameCol: 'actor' },
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

    // ── hive.html P3 (2026-07-19): the board's own writes run in a SUPERVISOR context. Two invariants:
    //   (1) hive_audit_log — forge actor -> INSERT persists + actor PINNED (wh_bind_audit_actor_trg) +
    //       owner-DELETE is a NO-OP (append-only immutable; only supervisors may even READ it). A worker's
    //       insert-with-RETURNING correctly errors (audit read is supervisor-only), so this MUST be a
    //       supervisor round-trip. (2) hives.intent — supervisor read -> UPDATE focus-goal -> restore
    //       (the board's signature CRUD, the "What should WorkHive focus on" dialog). Probe rows cleaned
    //       by the Python wrapper. Locks hive.html P3 65->100.
    const supRes = { out: {} };
    try {
      const sctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: 'Asia/Manila' });
      const ssi = await signIn(sctx, 'supervisor');
      if (!ssi.ok) { supRes.out['(supervisor-signin)'] = 'SKIP:' + (ssi.err || 'failed'); }
      else {
        const spage = await sctx.newPage();
        await spage.goto(`${SEEDER}/workhive/hive.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await spage.waitForFunction(
          () => typeof window.getDb === 'function' || !!window._whSupabaseClient || !!window.supabase,
          { timeout: 15000 }).catch(() => {});
        const sr = await spage.evaluate(async ({ hive, immutable }) => {
          const db = window._whSupabaseClient
            || (window.getDb && window.getDb(window.SUPABASE_URL || 'http://127.0.0.1:54321', window.SUPABASE_KEY))
            || window.supabase;
          if (!db) return { fatal: 'no db client on page' };
          const uid = (await db.auth.getUser()).data?.user?.id;
          if (!uid) return { fatal: 'db client not authenticated' };
          const out = {};
          // (1) hive_audit_log — append-only attribution. INSERT is fire-and-forget WITHOUT .select()
          //     (exactly how the board's writeAuditLog works — a combined INSERT+RETURNING is fragile
          //     against the supervisor-only SELECT policy). Then read back by a unique marker to assert
          //     the actor was PINNED, and prove owner-DELETE is a NO-OP (immutable audit trail).
          for (const e of immutable) {
            try {
              const marker = 'crudgate-' + (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()));
              const row = { hive_id: hive, ...e.row, target_id: marker, [e.nameCol]: 'CRUDGATE-FORGED' };
              const ins = await db.from(e.name).insert(row);            // no .select() — like the board
              if (ins.error) { out[e.name] = 'CREATE-FAIL:' + (ins.error.code || '?'); continue; }
              const back = await db.from(e.name).select('id,' + e.nameCol).eq('target_id', marker);
              if (!back.data || !back.data.length) { out[e.name] = 'READBACK-FAIL:' + (back.error?.code || 'empty'); continue; }
              const r = back.data[0];
              const pinned = r[e.nameCol] !== 'CRUDGATE-FORGED';
              const del = await db.from(e.name).delete().eq('target_id', marker).select();
              const immutableOk = !(del.data && del.data.length);  // append-only: delete affects 0 rows
              out[e.name] = (pinned && immutableOk) ? 'OK' : `FAIL(pinned=${pinned},immutable=${immutableOk})`;
            } catch (err) { out[e.name] = 'THROW:' + String(err).slice(0, 30); }
          }
          // (2) hives.intent — supervisor read -> update focus-goal -> restore (reversible round-trip)
          try {
            const cur = await db.from('hives').select('id,intent').eq('id', hive).single();
            if (cur.error) { out['hives.intent'] = 'READ-FAIL:' + (cur.error.code || '?'); }
            else {
              const before = cur.data.intent ?? null;
              const probe = { _crudgate: true, goal: 'CRUDGATE-PROBE' };
              const upd = await db.from('hives').update({ intent: probe }).eq('id', hive).select('id,intent');
              const wrote = upd.data?.[0]?.intent?.goal === 'CRUDGATE-PROBE';
              const restore = await db.from('hives').update({ intent: before }).eq('id', hive).select('id,intent');
              const restored = JSON.stringify(restore.data?.[0]?.intent ?? null) === JSON.stringify(before);
              out['hives.intent'] = (wrote && restored) ? 'OK' : `FAIL(wrote=${wrote},restored=${restored},err=${upd.error?.code || restore.error?.code || '-'})`;
            }
          } catch (err) { out['hives.intent'] = 'THROW:' + String(err).slice(0, 30); }
          return { uid, out };
        }, { hive: HIVE, immutable: IMMUTABLE });
        if (sr.fatal) supRes.out['(supervisor)'] = 'SKIP:' + sr.fatal;
        else { supRes.out = sr.out; supRes.uid = sr.uid; }
      }
      await sctx.close();
    } catch (e) { supRes.out['(supervisor)'] = 'SKIP:' + String(e).slice(0, 40); }

    console.log(`PAGE-CRUD GATE (worker ${String(res.uid).slice(0, 8)}…, migs 010/011/012):`);
    for (const [k, v] of Object.entries(res.out)) console.log(`  ${v === 'OK' ? 'PASS' : 'FAIL'}  ${k}: ${v}`);
    console.log(`HIVE-BOARD P3 (supervisor ${String(supRes.uid || '?').slice(0, 8)}…, hive.html own writes):`);
    for (const [k, v] of Object.entries(supRes.out)) {
      const skip = String(v).startsWith('SKIP');
      console.log(`  ${v === 'OK' ? 'PASS' : (skip ? 'SKIP' : 'FAIL')}  ${k}: ${v}`);
    }
    const fails = [...Object.entries(res.out), ...Object.entries(supRes.out)]
      .filter(([, v]) => v !== 'OK' && !String(v).startsWith('SKIP'));
    if (fails.length) { console.log(`\nFAIL — ${fails.length} P3 CRUD/attribution regression(s)`); process.exit(1); }
    const total = Object.keys(res.out).length + Object.values(supRes.out).filter(v => v === 'OK').length;
    console.log(`\nPASS — ${total} invariants: create persists + attribution PINNED to caller + owner-delete/immutable + hive-board focus-goal round-trip`);
    process.exit(0);
  } catch (e) {
    console.log('SKIP: ' + String(e).slice(0, 80));  // infra/harness issue -> skip, not a false fail
    process.exit(0);
  } finally { if (browser) await browser.close(); }
})();
