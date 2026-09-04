/**
 * Does undoing an import remove THAT import — and only that import? (T135, 2026-08-28)
 *
 * The rollback matched target rows by worker_name + created_at BETWEEN the audit row's timestamp
 * and +5 minutes. Both halves are wrong, in opposite directions, and the result was a reversal that
 * did the reverse of its job:
 *
 *   * The audit row is written AFTER the data rows — measured 51ms for asset_nodes, 88ms for
 *     external_sync — so every row the import created sits just BEFORE the window and .gte()
 *     excludes it. MEASURED: two imported assets survived a rollback that said "Import rolled back
 *     successfully."
 *   * A logbook row from a work-order import carries the SOURCE system's created_at, often years
 *     old, so it can never land inside an import-time window at all.
 *   * Anything the same person creates in the following five minutes IS inside the window.
 *     MEASURED: a hand-made asset created 10s after an import was destroyed by undoing that import.
 *
 * So the control most likely to be reached for in a panic deleted the wrong data and reported
 * success. This asserts the corrected behaviour end to end, with a BYSTANDER row present for the
 * whole run — because "the import was removed" and "nothing else was" are two different claims and
 * the old code passed the first while failing the second.
 *
 * ★IT WRITES, AND IT CLEANS UP AFTER ITSELF. Every row it makes is tagged WH-PROBE-UNDOGATE and
 * removed in a finally block, and the run ends by asserting no such row survives — a probe that
 * leaves debris behind is a slow way to poison the fixture.
 *
 * USAGE:  node tools/prove_import_undo_removes_the_import.mjs
 * Exit 1 on any failed assertion.
 */
import { chromium } from 'playwright';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234', hiveName: 'Baguio' };
const TAGS = { a: 'WH-PROBE-UNDOGATE-1', b: 'WH-PROBE-UNDOGATE-2', bystander: 'WH-PROBE-UNDOGATE-BYSTANDER' };
const CSV = [`ASSETNUM,DESCRIPTION,LOCATION,ASSETTYPE`,
             `${TAGS.a},Undo gate one,Bay 1,Pump`,
             `${TAGS.b},Undo gate two,Bay 2,Fan`].join('\n');

const fails = [];
const check = (ok, what, got) => {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${what}${ok ? '' : `  (got: ${got})`}`);
  if (!ok) fails.push(what);
};

console.log('import-undo-removes-the-import - does undo remove that import, and only that import?\n');

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
let page = null;

try {
  const auth = await ctx.newPage();
  await auth.goto(`${BASE}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await auth.waitForFunction(() => !!(window.supabase && window.supabase.createClient) && !!window.SUPABASE_KEY,
                             { timeout: 20000 }).catch(() => {});
  const hive = await auth.evaluate(async ({ acct, url }) => {
    const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
    const { data } = await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
    const uid = data?.session?.user?.id;
    const { data: m } = uid ? await db.from('hive_members').select('hive_id')
      .eq('auth_uid', uid).eq('status', 'active').limit(1).maybeSingle() : { data: null };
    if (m?.hive_id) { localStorage.setItem('wh_active_hive_id', m.hive_id); localStorage.setItem('wh_hive_id', m.hive_id); }
    // The DISPLAY name, which is what the rows carry — seeding the username here silently
    // decouples audit.triggered_by from asset_nodes.worker_name and fakes a failure.
    localStorage.setItem('wh_last_worker', 'Leandro Marquez');
    localStorage.setItem('wh_hive_name', acct.hiveName);
    localStorage.setItem('wh_hive_role', 'supervisor');
    return m?.hive_id || null;
  }, { acct: ACCT, url: SB_URL });
  await auth.close();
  if (!hive) { console.log('  FAIL  sign-in / hive'); process.exitCode = 1; }

  page = await ctx.newPage();
  await page.goto(`${BASE}/workhive/integrations.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  await page.click('.source-card[data-type="maximo"]'); await page.waitForTimeout(400);
  await page.click('.source-card[data-entity="asset"]'); await page.waitForTimeout(300);
  await page.click('#btn-s1-next'); await page.waitForTimeout(400);
  await page.setInputFiles('#file-input', { name: 'u.csv', mimeType: 'text/csv', buffer: Buffer.from(CSV, 'utf-8') });
  await page.waitForTimeout(1800);
  await page.click('#btn-s2-next'); await page.waitForTimeout(700);
  await page.click('button:has-text("Auto-suggest")'); await page.waitForTimeout(900);
  await page.click('button:has-text("Preview →")'); await page.waitForTimeout(900);
  await page.evaluate(() => Array.from(document.querySelectorAll('#step-4 button'))
    .find(x => (x.getAttribute('onclick') || '').includes('startImport')).click());
  await page.waitForTimeout(10000);

  const imported = await page.evaluate(async (tags) => {
    const db = window._whSupabaseClient;
    const { data } = await db.from('asset_nodes').select('tag').in('tag', [tags.a, tags.b]);
    return (data || []).length;
  }, TAGS);
  check(imported === 2, 'the import landed its two rows', String(imported));

  // A bystander the same person creates right after — untouched by this import in every sense.
  const made = await page.evaluate(async ({ hive, tags }) => {
    const db = window._whSupabaseClient;
    const { error } = await db.from('asset_nodes').insert({
      tag: tags.bystander, name: 'Unrelated hand-made asset', iso_class: 'General', location: 'not the import',
      criticality: 'medium', level: 'equipment', status: 'approved', hive_id: hive,
      worker_name: 'Leandro Marquez', submitted_by: 'Leandro Marquez',
      approved_by: 'Leandro Marquez', approved_at: new Date().toISOString(),
    });
    return error ? error.message.slice(0, 80) : 'ok';
  }, { hive, tags: TAGS });
  check(made === 'ok', 'a bystander row exists during the rollback', made);

  const said = await page.evaluate(async () => {
    const db = window._whSupabaseClient;
    const { data } = await db.from('cmms_audit_log')
      .select('batch_id,entity_type,triggered_by,created_at')
      .eq('operation', 'file_import').order('created_at', { ascending: false }).limit(1);
    const bt = data && data[0];
    if (!bt) return '(no batch)';
    window.whConfirm = () => Promise.resolve(true);
    await rollbackBatch(bt.batch_id, bt.entity_type, bt.triggered_by || '', bt.created_at);
    await new Promise((r) => setTimeout(r, 3500));
    const t = document.querySelector('#toast, .toast, [role=alert]');
    return t ? (t.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 140) : '(no toast)';
  });

  const after = await page.evaluate(async (tags) => {
    const db = window._whSupabaseClient;
    const { data } = await db.from('asset_nodes').select('tag').in('tag', [tags.a, tags.b, tags.bystander]);
    return (data || []).map((r) => r.tag);
  }, TAGS);

  check(!after.includes(TAGS.a) && !after.includes(TAGS.b),
        'the imported rows are gone', after.join(', ') || '(none)');
  check(after.includes(TAGS.bystander),
        'the unrelated row the same person made SURVIVES', after.join(', ') || '(none)');
  check(/2 imported rows removed/.test(said),
        'the message states how many rows it actually removed', said);
  check(!/rolled back successfully\.$/.test(said),
        'it no longer claims bare success without a count', said);
} catch (e) {
  console.log('  FAIL  probe error:', String(e.message || e).slice(0, 140));
  fails.push('probe error');
} finally {
  // Clean up everything this made, whatever happened above.
  try {
    const p2 = page && !page.isClosed() ? page : await ctx.newPage();
    if (!page || page.isClosed()) {
      await p2.goto(`${BASE}/workhive/integrations.html`, { waitUntil: 'domcontentloaded' });
      await p2.waitForTimeout(2500);
    }
    const left = await p2.evaluate(async () => {
      const db = window._whSupabaseClient;
      if (!db) return -1;
      await db.from('asset_nodes').delete().like('tag', 'WH-PROBE-UNDOGATE%');
      await db.from('external_sync').delete().like('external_id', 'WH-PROBE-UNDOGATE%');
      // ★THE AUDIT ROWS THESE DELETES CAUSE ARE PERMANENT, AND THAT IS CORRECT. asset_nodes carries
      // trg_asset_node_delete_audit, so every row this probe removes writes a hive_audit_log entry
      // naming a WH-PROBE asset. I tried to clean those too and the delete was REFUSED — silently,
      // as an RLS-filtered delete always is (0 rows, no error). Checking the policies explains it:
      // hive_audit_log has an INSERT policy and two SELECT policies and NO delete or update policy
      // at all, so the trail is append-only to every client. That is the property the whole
      // DOLE/ISO story rests on, and a test probe is not the thing that should be allowed to bend
      // it. So this asserts only what the probe legitimately owns; the audit entries stay, and
      // clearing them from a local fixture is a psql chore, not something the browser can do.
      const { data } = await db.from('asset_nodes').select('tag').like('tag', 'WH-PROBE-UNDOGATE%');
      return (data || []).length;
    });
    check(left === 0, 'the probe left no rows behind (audit entries stay: the trail is append-only)', String(left));
  } catch (e) { check(false, 'cleanup ran', String(e.message || e).slice(0, 80)); }
  await browser.close();
}

console.log(`\n  ${fails.length ? `FAIL: ${fails.length} assertion(s)`
  : 'PASS: undo removes the import it names, and leaves everything else alone'}`);
process.exit(fails.length ? 1 : 0);
