/* prove_partial_metric_declares_itself.mjs — T47: a partial OEE must say so (2026-08-26).
 *
 * OEE is a product of three factors: Availability x Performance x Quality. Computing two of them
 * and calling the result "OEE" is not a rounding difference - it is a DIFFERENT AND HIGHER number,
 * because the missing factor can only reduce it. A plant that reports 88% to management when the
 * three-factor figure would be lower has not made a small error; it has made a claim it cannot
 * defend the moment somebody asks how it was computed. That is exactly the reader T47 is about.
 *
 * THE PLATFORM GETS THIS RIGHT and this gate keeps it right. analytics renders:
 *   "OEE (AVG, PARTIAL) 88% · Avg across 20 assets · WORLD CLASS · ISO 22400-2:2014 ·
 *    Availability x Quality only. Add each asset's cycle time to include Performance."
 * Value, denominator, standard, WHICH FACTORS ARE IN IT, and what to do about the missing one -
 * a skeptic can hand-check the arithmetic and knows precisely what they are hand-checking.
 *
 * THE ASSERTION: wherever a headline OEE figure is rendered, the same card names its factor basis.
 * Either the label carries a partial marker and says which factors are included, or the card states
 * the full three-factor product. What it may never do is show a bare "OEE 88%".
 *
 * ★IT DOES NOT ASSERT THE VALUE OR DEMAND FULL OEE. Whether this hive has cycle times is a data
 * question, not a defect - the honest response to missing data is to say what is missing, which is
 * what the card does. The failure being gated is silence about the basis, not the partiality.
 *
 * Usage: node tools/prove_partial_metric_declares_itself.mjs
 */
import { chromium } from 'playwright';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234',
               worker: 'Leandro Marquez', hiveName: 'Baguio Textile Mills' };

const browser = await chromium.launch();
const v = {};
try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
  const auth = await ctx.newPage();
  await auth.goto(`${BASE}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await auth.waitForFunction(
    () => !!(window.supabase && window.supabase.createClient) && !!window.SUPABASE_KEY,
    { timeout: 20000 }).catch(() => {});
  const ok = await auth.evaluate(async ({ acct, url }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
      const uid = data?.session?.user?.id;
      const { data: m } = uid ? await db.from('hive_members').select('hive_id')
        .eq('auth_uid', uid).eq('status', 'active').limit(1).maybeSingle() : { data: null };
      if (m?.hive_id) {
        localStorage.setItem('wh_active_hive_id', m.hive_id);
        localStorage.setItem('wh_hive_id', m.hive_id);
      }
      localStorage.setItem('wh_last_worker', acct.worker);
      localStorage.setItem('wh_hive_name', acct.hiveName);
      localStorage.setItem('wh_hive_role', 'supervisor');
      return !error && !!data?.session;
    } catch (e) { return false; }
  }, { acct: ACCT, url: SB_URL });
  await auth.close();
  if (!ok) throw new Error('sign-in failed');

  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));
  await page.goto(`${BASE}/analytics.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(9000);

  Object.assign(v, await page.evaluate(() => {
    const card = document.getElementById('an-card-oee');
    if (!card) return { cardMissing: true };
    const text = (card.innerText || '').replace(/\s+/g, ' ').trim();
    const hasFigure = /\d+\s*%/.test(text);
    const partial = /partial|only\b/i.test(text);
    // which factors it says it used, or a full three-factor statement
    const namesFactors = /availab/i.test(text) && (/quality/i.test(text) || /performance/i.test(text));
    const namesStandard = /ISO\s*22400/i.test(text);
    const saysHowToComplete = /add .*cycle time|include performance/i.test(text);
    return { text: text.slice(0, 240), hasFigure, partial, namesFactors, namesStandard, saysHowToComplete };
  }));
  v.pageerrors = errs.length;
  await page.close();
  console.log(`  OEE card: ${v.text || '(absent)'}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 160);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

// a figure with no factor basis is the failure; a partial one that names its factors is fine
const declares = v.namesFactors && (!v.partial || v.saysHowToComplete);
const pass = !v.error && !v.cardMissing && v.hasFigure && declares && v.pageerrors === 0;
if (!pass && !v.error) {
  console.log('  A headline OEE that does not name its factor basis reads as the full three-factor');
  console.log('  product. Availability x Quality is a HIGHER number than Availability x Performance x');
  console.log('  Quality, so the omission always flatters - say which factors are in it.');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — partial metric declares itself: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
