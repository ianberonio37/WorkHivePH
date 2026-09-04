/* prove_edge_refusal_survives_the_client.mjs — T82: the function's words must reach the person.
 *
 * supabase-js collapses EVERY non-2xx from functions.invoke into one FunctionsHttpError whose
 * message is the literal "Edge Function returned a non-2xx status code". The status and body
 * survive on `error.context`, but a caller reading only `error.message` never sees them.
 *
 * ★SO THE CLIENT SILENTLY UNDOES THE WORK THE BACKEND DID. rate-limit.ts answers a drained hive
 * with 429 and "AI call limit reached for this hive. Try again in an hour." - cause named,
 * clearing time named, exactly the bar the AI-error taxonomy exists to hold. Measured on
 * asset-hub, the worker instead read "Could not reach Asset Brain: Edge Function returned a
 * non-2xx status code": a CONNECTION-flavoured sentence for a QUOTA event, which sends them to
 * check their signal rather than wait an hour. whAiError could not rescue it either - it keys on
 * /429|rate.?limit|quota/ and the generic string carries none of them.
 *
 * THE ASSERTION: with the Asset Brain endpoints forced to the real 429 payload, the answer pane
 * shows the FUNCTION'S sentence (quota named), and never the generic non-2xx string. The 429 is
 * injected rather than waited for, so the probe is deterministic and spends no AI call.
 *
 * Usage: node tools/prove_edge_refusal_survives_the_client.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234' };
const QUOTA = 'AI call limit reached for this hive. Try again in an hour.';

const psql = (sql) => execFileSync('docker',
  ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8' }).trim();

const hive = psql(`SELECT hm.hive_id FROM hive_members hm JOIN auth.users u ON u.id=hm.auth_uid
                   WHERE u.email='${ACCT.email}' AND hm.status='active' LIMIT 1;`).split('\n')[0];
if (!hive) { console.log('SKIP — no active hive for the test account'); process.exit(0); }
const asset = psql(`SELECT asset_id FROM v_asset_truth WHERE hive_id='${hive}' LIMIT 1;`).split('\n')[0];
if (!asset) { console.log('SKIP — no asset in the fixture hive'); process.exit(0); }

const v = {};
const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });

  // sign in on a neutral page first — asset-hub bounces before a session exists, and the
  // navigation destroys any evaluate running against it
  const auth = await ctx.newPage();
  await auth.goto(`${BASE}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await auth.waitForFunction(
    () => !!(window.supabase && window.supabase.createClient) && !!window.SUPABASE_KEY,
    { timeout: 20000 }).catch(() => {});
  const signedIn = await auth.evaluate(async ({ acct, url, hiveId }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
      localStorage.setItem('wh_active_hive_id', hiveId);
      localStorage.setItem('wh_hive_id', hiveId);
      localStorage.setItem('wh_last_worker', 'Leandro Marquez');
      localStorage.setItem('wh_hive_role', 'supervisor');
      return !error && !!data?.session;
    } catch (_) { return false; }
  }, { acct: ACCT, url: SB_URL, hiveId: hive });
  await auth.close();
  if (!signedIn) throw new Error('sign-in failed');

  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));

  // both lanes refuse the way a drained hive really is refused: 429 + the function's own body
  for (const p of ['**/functions/v1/asset-brain-query*', '**/functions/v1/ai-gateway*']) {
    await page.route(p, (r) => r.fulfill({
      status: 429, contentType: 'application/json', body: JSON.stringify({ error: QUOTA, scope: 'hour' }),
    }));
  }

  await page.goto(`${BASE}/asset-hub.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(7000);

  v.read = await page.evaluate(async (assetId) => {
    if (typeof askAssetBrain !== 'function') return { noFn: true };
    const input = document.getElementById('ask-input');
    if (!input) return { noInput: true };
    input.value = 'What repairs has this asset had?';
    await askAssetBrain(assetId);
    await new Promise((r) => setTimeout(r, 4000));
    const t = (document.getElementById('ask-answer')?.innerText || '').replace(/\s+/g, ' ').trim();
    return {
      text: t.slice(0, 160),
      namesQuota: /limit reached|try again in an hour/i.test(t),
      leaksGeneric: /non-2xx|unknown error/i.test(t),
      hasHelper: typeof window.whFnError === 'function',
    };
  }, asset);
  v.read.errs = errs.length;
  console.log(`  answer pane -> ${v.read.text}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 170);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

const r = v.read || {};
const pass = !v.error && !r.noFn && !r.noInput && r.hasHelper
  && r.namesQuota && !r.leaksGeneric && r.errs === 0;
if (!pass && !v.error) {
  console.log('  The backend named the cause and when it clears. If the pane says "non-2xx" instead,');
  console.log('  the client threw that away and told a rate-limited worker to check their connection.');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — edge refusal survives the client: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
