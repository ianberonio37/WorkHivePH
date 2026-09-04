/* prove_feedback_round_trip.mjs — T157: the feedback loop actually goes somewhere (2026-08-26).
 *
 * "Email us with corrections" and a feedback button are trust claims. A widget that thanks somebody
 * and stores nothing is the worst version of this: the person believes they were heard, nobody was
 * told, and the silence reads as being ignored rather than as a bug.
 *
 * MEASURED FROM THE PUBLIC /about/ PAGE, anonymously — the hardest case, because an anon insert has
 * to pass RLS with no session behind it.
 *
 * FOUR ASSERTIONS:
 *   lands       a completed submission reaches platform_feedback (the row is read back by id)
 *   refuses     an INCOMPLETE one (no kind chosen) is refused BEFORE any network call
 *   saysWhy     the refusal names what is missing - "Pick what kind of feedback this is." - in a
 *               visible element, not a console warning
 *   keepsDraft  the refusal does not clear what was typed
 *
 * ★THE REFUSAL ASSERTIONS ARE THE POINT. A loop that works when you fill everything in is easy; the
 * failure that costs trust is a submit that quietly does nothing, which is exactly what the first
 * run of this probe LOOKED like - it clicked send without choosing a kind, got no row, and could
 * have been written up as "public feedback does not reach the table". It reached nothing because
 * the widget correctly refused, and said so in an element the probe was not reading.
 *
 * The probe row is marked WH-T157-PROBE and deleted, and the deletion is re-counted.
 *
 * Usage: node tools/prove_feedback_round_trip.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const MARK = 'WH-T157-PROBE';

const psql = (sql) => execFileSync('docker',
  ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8' }).trim();

const count = () => psql(`SELECT count(*) FROM platform_feedback WHERE subject LIKE '%${MARK}%'`);

if (count() !== '0') { console.log('ABORT: leftover probe feedback — refusing to measure on dirty state.'); process.exit(2); }

const browser = await chromium.launch();
const v = {};
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  const calls = [];
  page.on('response', (r) => { if (/platform_feedback/.test(r.url())) calls.push(r.status()); });

  await page.goto(`${SEEDER}/about/`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);

  // ── the INCOMPLETE submit: must be refused, out loud, without losing the draft ──
  const refusal = await page.evaluate(async () => {
    if (!window.WHFeedback) return { err: 'widget absent' };
    WHFeedback.open({ subject: 'kindless probe', body: 'Submitted without choosing a kind.' });
    await new Promise((r) => setTimeout(r, 700));
    const btn = Array.from(document.querySelectorAll('button')).find((x) => /send feedback/i.test(x.textContent));
    if (!btn) return { err: 'no send button' };
    btn.click();
    await new Promise((r) => setTimeout(r, 1000));
    const s = document.getElementById('wh-fb-status');
    return {
      status: s ? s.textContent.trim() : '',
      visible: s ? s.getBoundingClientRect().height > 0 : false,
      draft: (document.getElementById('wh-fb-subject') || {}).value || '',
    };
  });
  v.refuses = calls.length === 0;                       // refused BEFORE any network call
  v.saysWhy = /kind/i.test(refusal.status || '') && refusal.visible === true;
  v.keepsDraft = (refusal.draft || '') !== '';
  console.log(`  incomplete submit -> "${refusal.status}" (visible ${refusal.visible}, draft kept ${v.keepsDraft}, network calls ${calls.length})`);

  // ── the COMPLETE submit: must land ──
  // ★A FRESH PAGE LOAD, because WHFeedback.open(prefill) deliberately fills only EMPTY fields - it
  // must never clobber what somebody has already typed. Reusing the panel from the refusal case
  // therefore kept the OLD subject, the row landed under that name, and the probe read "rows 0" and
  // very nearly recorded "a public submission never reaches the table" against a working product.
  // The prefill behaviour is correct; the probe was reusing dirty state.
  await page.goto(`${SEEDER}/about/`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3500);
  await page.evaluate(async (mark) => {
    WHFeedback.open({ subject: mark + ' round trip', body: 'Probe: does a public submission land?' });
    await new Promise((r) => setTimeout(r, 600));
    const kind = Array.from(document.querySelectorAll('button')).find((x) => /Bug/i.test(x.textContent));
    if (kind) kind.click();
    await new Promise((r) => setTimeout(r, 300));
    const btn = Array.from(document.querySelectorAll('button')).find((x) => /send feedback/i.test(x.textContent));
    btn.click();
    await new Promise((r) => setTimeout(r, 2500));
  }, MARK);

  v.lands = count() === '1';
  v.landedAsNew = v.lands && psql(
    `SELECT status FROM platform_feedback WHERE subject LIKE '%${MARK}%' LIMIT 1`).split('\n')[0] === 'new';
  console.log(`  complete submit   -> rows ${count()}, status new: ${v.landedAsNew}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 180);
  console.log('probe error:', v.error);
} finally {
  psql(`DELETE FROM platform_feedback WHERE subject LIKE '%${MARK}%'`);
  v.cleanup = count() === '0';
  await browser.close();
}

const pass = !v.error && v.lands && v.landedAsNew && v.refuses && v.saysWhy && v.keepsDraft && v.cleanup;
console.log((pass ? 'PASS' : 'FAIL') + ` — feedback round trip: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
