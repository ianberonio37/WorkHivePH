/* prove_repaint_spares_typing.mjs — T142: a live update must not evict a typist (2026-08-26).
 *
 * The recorded incident this guards against is precise: a 15-second poll rebuilt a region while
 * somebody was typing in it, and the repaint threw focus to <body>. The DRAFT survived - the text
 * was still there - which is exactly what made it hard to see, because the person kept typing into
 * nothing. Realtime is the same hazard with worse timing: the update arrives when a colleague acts,
 * not on a schedule you could learn.
 *
 * THE INVARIANT THAT MAKES IT SAFE, and it is structural rather than behavioural: a container that a
 * realtime handler REPLACES must not contain a typing surface. If the composer is not in the subtree
 * being rebuilt, no repaint can evict it, and no focus-restoration code is needed - which is better
 * than restoring focus correctly, because restoration has to be right every time.
 *
 * MEASURED, and both of T142's named subjects hold:
 *   community  updates a single card via _updateRenderedCard() for the ordinary case and rebuilds
 *              #feed-list only when a PIN moves (a genuine reorder). Both composers sit OUTSIDE that
 *              container - the post box on the page, the reply box inside #thread-overlay - so the
 *              rebuild cannot reach them.
 *   hive       realtime reloads targeted display cards (loadAdoptionCard, loadMaturityStairway),
 *              which hold no inputs at all.
 *
 * ★IT ASSERTS CONTAINMENT, NOT FOCUS SURVIVAL. Driving a real focus test needs the composer open and
 * a real update to land, and it would prove one path on one run. Containment is the property that
 * makes every path safe, and it is checkable every run.
 *
 * Usage: node tools/prove_repaint_spares_typing.mjs
 */
import { chromium } from 'playwright';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234',
               worker: 'Leandro Marquez', hiveName: 'Baguio Textile Mills' };

// container a realtime handler rebuilds -> it must hold no input/textarea
const SUBJECTS = [
  { page: 'community.html', containers: ['feed-list'] },
  { page: 'hive.html', containers: ['adoption-card', 'maturity-stairway', 'activity-log'] },
];

const browser = await chromium.launch();
const rows = [];
let fatal = null;
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
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

  for (const subj of SUBJECTS) {
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));
    await page.goto(`${BASE}/${subj.page}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(6000);
    const found = await page.evaluate((ids) => ids.map((id) => {
      const el = document.getElementById(id);
      if (!el) return { id, present: false };
      const typing = el.querySelectorAll('input:not([type=hidden]):not([type=button]):not([type=submit]), textarea');
      return {
        id, present: true, typingSurfaces: typing.length,
        names: Array.from(typing).slice(0, 3).map((t) => t.id || t.name || t.tagName),
      };
    }), subj.containers);
    await page.close();
    for (const f of found) {
      rows.push({ page: subj.page, ...f, errs: errs.length });
      console.log(`  ${subj.page.padEnd(18)} #${f.id.padEnd(20)} `
        + (f.present ? `typing surfaces inside: ${f.typingSurfaces}`
          + (f.typingSurfaces ? ' :: ' + f.names.join(', ') : '')
          : '(not on this page)'));
    }
  }
} catch (e) {
  fatal = String(e.message || e).slice(0, 160);
  console.log('probe error:', fatal);
} finally {
  await browser.close();
}

const seen = rows.filter((r) => r.present);
const unsafe = seen.filter((r) => r.typingSurfaces > 0);
console.log(`  rebuilt containers checked: ${seen.length} | holding a typing surface: ${unsafe.length}`);
const pass = !fatal && seen.length > 0 && unsafe.length === 0;
if (unsafe.length) {
  console.log(`  ${unsafe.map((r) => `${r.page}#${r.id}(${r.names.join('/')})`).join(', ')}`);
  console.log('  A realtime update rebuilding this container will evict whoever is typing in it, and');
  console.log('  the draft survives while the focus does not - so they keep typing into nothing. Move');
  console.log('  the composer out of the rebuilt subtree, or update the card in place.');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — repaint spares typing: ${JSON.stringify({ checked: seen.length, unsafe: unsafe.length, fatal })}`);
process.exit(pass ? 0 : 1);
