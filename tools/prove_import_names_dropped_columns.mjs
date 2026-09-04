/**
 * Does the import preview say what it is about to THROW AWAY? (T135, 2026-08-28)
 *
 * The CMMS import's step-4 preview warned when a WORKHIVE FIELD had no source column, and never
 * when a SOURCE COLUMN had no WorkHive field. The first protects the schema; the second protects
 * the user's data — and carrying data across is the entire purpose of a legacy import.
 *
 * MEASURED against the real wizard: a 4-column Maximo export whose EQTYPE header is in neither
 * dictionary imported three assets that all landed iso_class 'General' — the equipment type simply
 * gone — under a preview reading "3 rows · 3 ready to import · all valid" and an EMPTY warnings
 * box. The dictionary was right to decline to guess at a header it does not recognise; the silence
 * about having dropped the column is the defect. Someone bringing five years of plant history
 * across has no other moment to notice that a column did not make the trip.
 *
 * ★IT ASSERTS THE CLEAN CASE TOO, and that half is the one that keeps the notice trustworthy: the
 * same file with Maximo's real ASSETTYPE header maps all four columns and must produce NO notice.
 * A warning that fires on every import is furniture, and people stop reading furniture.
 *
 * ★READ-ONLY BY CONSTRUCTION. It stops at the preview and never presses Import, so it asserts the
 * consent surface without writing a row — the reason this is safe to run on every board.
 *
 * USAGE:  node tools/prove_import_names_dropped_columns.mjs
 * Exit 1 on any failed assertion.
 */
import { chromium } from 'playwright';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234',
               worker: 'leandromarquez', hiveName: 'Baguio' };

const rows = ['WH-PROBE-IMP-A,Probe Pump Alpha,Utility Room,Pump',
              'WH-PROBE-IMP-B,Probe Fan Bravo,Roof Deck,Fan'];
const CSV_DROPS = ['ASSETNUM,DESCRIPTION,LOCATION,EQTYPE', ...rows].join('\n');      // EQTYPE: unknown
const CSV_CLEAN = ['ASSETNUM,DESCRIPTION,LOCATION,ASSETTYPE', ...rows].join('\n');   // all four known

const fails = [];
const check = (ok, what, got) => {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${what}${ok ? '' : `  (got: ${got})`}`);
  if (!ok) fails.push(what);
};

console.log('import-names-dropped-columns - does the preview say what it will discard?\n');

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });

const auth = await ctx.newPage();
await auth.goto(`${BASE}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
await auth.waitForFunction(() => !!(window.supabase && window.supabase.createClient) && !!window.SUPABASE_KEY,
                           { timeout: 20000 }).catch(() => {});
const signedIn = await auth.evaluate(async ({ acct, url }) => {
  try {
    const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
    const { data, error } = await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
    const uid = data?.session?.user?.id;
    const { data: m } = uid ? await db.from('hive_members').select('hive_id')
      .eq('auth_uid', uid).eq('status', 'active').limit(1).maybeSingle() : { data: null };
    if (m?.hive_id) { localStorage.setItem('wh_active_hive_id', m.hive_id); localStorage.setItem('wh_hive_id', m.hive_id); }
    localStorage.setItem('wh_last_worker', acct.worker);
    localStorage.setItem('wh_hive_name', acct.hiveName);
    localStorage.setItem('wh_hive_role', 'supervisor');
    return !error && !!data?.session;
  } catch (e) { return false; }
}, { acct: ACCT, url: SB_URL });
await auth.close();
if (!signedIn) { console.log('  FAIL  sign-in'); await browser.close(); process.exit(1); }

// Drive steps 1-4 and read the warnings box. ★The order matters and is not obvious:
// #entity-section is display:none until a SOURCE is chosen, so entity must follow source.
async function previewWarnings(csv) {
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));
  await p.goto(`${BASE}/workhive/integrations.html`, { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(3000);
  await p.click('.source-card[data-type="maximo"]');
  await p.waitForTimeout(400);
  await p.click('.source-card[data-entity="asset"]');
  await p.waitForTimeout(300);
  await p.click('#btn-s1-next');
  await p.waitForTimeout(400);
  await p.setInputFiles('#file-input', { name: 'probe.csv', mimeType: 'text/csv', buffer: Buffer.from(csv, 'utf-8') });
  await p.waitForTimeout(1800);
  await p.click('#btn-s2-next');
  await p.waitForTimeout(700);
  await p.click('button:has-text("Auto-suggest")');
  await p.waitForTimeout(900);
  await p.click('button:has-text("Preview →")');
  await p.waitForTimeout(900);
  const out = {
    warn: ((await p.textContent('#preview-warnings').catch(() => '')) || '').replace(/\s+/g, ' ').trim(),
    meta: ((await p.textContent('#preview-meta').catch(() => '')) || '').trim(),
    errs,
  };
  await p.close();
  return out;
}

const dropped = await previewWarnings(CSV_DROPS);
check(/EQTYPE/.test(dropped.warn), 'an unmapped source column is NAMED in the preview', dropped.warn || '(empty)');
check(/not be imported|will not be/i.test(dropped.warn), 'it says the data will not be imported', dropped.warn || '(empty)');
check(/Step 3/i.test(dropped.warn), 'it points at the step that can fix it', dropped.warn || '(empty)');
check(dropped.errs.length === 0, 'no page errors on the dropped-column path', dropped.errs.join(' | '));

const clean = await previewWarnings(CSV_CLEAN);
check(!/not be imported/i.test(clean.warn), 'a fully-mapped file raises NO dropped-column notice',
      clean.warn || '(empty)');
check(/ready to import/.test(clean.meta), 'the clean file still previews normally', clean.meta);

await browser.close();
console.log(`\n  ${fails.length ? `FAIL: ${fails.length} assertion(s)`
  : 'PASS: the preview names what it will discard, and stays quiet when it discards nothing'}`);
process.exit(fails.length ? 1 : 0);
