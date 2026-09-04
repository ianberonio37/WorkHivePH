/* smoke_pages.mjs — did my edit break the page? (2026-08-27)
 *
 * A 60-second signed-in load of the pages you just touched, failing on any error the page logs.
 * NOT a gate and deliberately not registered: page-level JS errors are already caught roster-wide
 * by page_battery.mjs and family_rubric_sweep.mjs, which listen for pageerror across the whole
 * roster. What those cannot give you is an answer in a minute, and the full board takes hours.
 *
 * ★IT EARNED ITS PLACE THE DAY IT WAS WRITTEN. A render edit to marketplace-seller emitted
 * `onclick="_svcJobGuard(this,'Turning on…',...)"` with its backslashes eaten in transit, so the
 * surrounding JS string literal closed early and the page threw
 * `SyntaxError: Unexpected identifier 'Turning'` at parse time. Every static check passed: the XSS
 * validator was green, `node --check` does not read HTML, and every symbol the new code referenced
 * was verified to exist. The page still painted its chrome, so it did not look broken. Only loading
 * it said so.
 *
 * ★AND A THIN PAGE FAILS TOO, error or not. A page whose body renders almost nothing has failed
 * even when nothing was logged - the stuck-skeleton class, invisible to a console listener.
 *
 * Usage:  node tools/smoke_pages.mjs logbook project-manager marketplace-seller
 *         node tools/smoke_pages.mjs            (defaults to the core write surfaces)
 */
import { chromium } from 'playwright';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', worker: 'Leandro Marquez', role: 'supervisor' };
const THIN = 400;   // a body shorter than this rendered nothing worth calling a page

const pages = process.argv.slice(2).filter((a) => !a.startsWith('-'));
const PAGES = pages.length ? pages : ['index', 'logbook', 'inventory', 'pm-scheduler', 'asset-hub'];

const browser = await chromium.launch();
const out = [];
try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const boot = await ctx.newPage();
  await boot.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await boot.waitForFunction(() => !!(window.supabase && window.supabase.createClient), { timeout: 25000 });
  await boot.evaluate(async ({ email, worker, hive, role }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    await db.auth.signInWithPassword({ email, password: 'test1234' });
    localStorage.setItem('wh_active_hive_id', hive.id);
    localStorage.setItem('wh_active_hive_name', hive.name);
    localStorage.setItem('WORKER_NAME', worker);
    /* ★SEED THE ROLE OR ROLE-GATED PAGES LOOK BROKEN. Without wh_hive_role, integrations rendered
       its "Supervisor access only" notice for an account the DATABASE lists as a supervisor, and
       this smoke reported the page as having rendered almost nothing - a false negative from the
       instrument, not a defect in the page. Real navigation writes this key when a hive is picked;
       a probe that jumps straight to a URL has to write it too. */
    localStorage.setItem('wh_hive_role', role);
  }, { email: ACCT.email, worker: ACCT.worker, hive: HIVE, role: ACCT.role });
  await boot.close();

  for (const name of PAGES) {
    const page = await ctx.newPage();
    const errs = [];
    page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 160)); });
    page.on('pageerror', (e) => errs.push('PAGEERROR ' + String(e.message).slice(0, 160)));
    try {
      await page.goto(`${SEEDER}/${name}.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(7000);
    } catch (e) { errs.push('NAV ' + String(e).slice(0, 120)); }
    /* ★THIN MEANS "NOTHING TO USE", NOT "FEW CHARACTERS" (2026-08-27). A char count alone called
       analytics-report broken at 371 chars - but that page is generate-on-demand and its resting
       state is a period selector, an audience selector and a Generate button, which is a complete
       and correct UI. A stuck skeleton has neither text NOR controls; a compact page has controls.
       Counting both keeps the skeleton catch and stops punishing pages for being terse. */
    /* ★AND CHECK THE PAGE IS ACTUALLY SIGNED IN. A signed-out page is not a broken page - it has
       chrome, controls and no errors - so it passes every check above while showing none of what
       was edited. It happened: under load the local stack returned 503s, the sign-in silently did
       not take, and marketplace-seller came back 317 chars of "Sign In Required" while an edit to
       its wallet was being verified. The honest reading of that run was "the probe never got in",
       not "the page shrank", and only naming the signed-out state tells them apart. */
    const seen = await page.evaluate(() => {
      const t = document.body.innerText || '';
      return {
        chars: t.length,
        controls: document.querySelectorAll('button, a[href], input, select, textarea').length,
        signedOut: /sign in required|you need to be signed in|please sign in to/i.test(t),
      };
    }).catch(() => ({ chars: 0, controls: 0, signedOut: false }));
    out.push({ page: name, errors: errs, chars: seen.chars, controls: seen.controls,
               signedOut: seen.signedOut });
    await page.close();
  }
} finally {
  await browser.close();
}

let bad = 0;
for (const r of out) {
  const thin = r.chars < THIN && r.controls < 5;
  const ok = !r.errors.length && !thin && !r.signedOut;
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${r.page.padEnd(20)} ${String(r.chars).padStart(6)} chars`
    + `  ${String(r.controls).padStart(3)} controls`
    + (r.signedOut ? '  · SIGNED OUT (the probe never got in - re-run, do not read this as a defect)' : '')
    + (thin ? '  · RENDERED ALMOST NOTHING' : '')
    + (r.errors.length ? `  · ${r.errors.length} error(s)` : ''));
  for (const e of r.errors.slice(0, 3)) console.log(`        ${e}`);
}
console.log(`\n${bad ? 'FAIL' : 'PASS'} — ${out.length - bad}/${out.length} page(s) load clean`);
process.exit(bad ? 1 : 0);
