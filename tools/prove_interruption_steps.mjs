/* prove_interruption_steps.mjs — T122: nothing lost, at EVERY step (2026-08-26).
 *
 * The first T122 walk injected an interruption at ONE step (the half-typed form) and found both
 * halves green. One step is a spot check: a multi-step wizard saves on its own schedule, and the
 * step where a draft is NOT yet written is invisible to a probe that only tests the step where it
 * is. A phone rings whenever it rings.
 *
 * THE SWEEP: fill the logbook wizard progressively, and at the END OF EACH STEP inject the harshest
 * realistic interruption — a FULL RELOAD, which is the OS killing a backgrounded tab — then assert
 * that everything typed so far is back.
 *
 * ★THE MECHANISM IS logbook's OWN saveDraft/restoreDraft, NOT whAutoSaveDraft. T122's first write-up
 * credited the shared helper; logbook does not use it. The distinction matters for more than tidiness:
 * the shared helper got OWNER STAMPING in T121 (so one worker's draft cannot surface for the next
 * person on a shared plant phone), and logbook missed that change entirely. Checked rather than
 * assumed — logbook is safe anyway, by a different route: DRAFT_KEY is 'wh_logbook_draft_' +
 * WORKER_NAME, so the next person's page computes a different key and simply cannot read it. Two
 * mechanisms, one guarantee. Worth knowing which is which before someone "unifies" them.
 *
 * ★AND THE PROBE TYPES INTO EVERY STEP BEFORE RELOADING IT, so a step whose fields are never saved
 * fails loudly instead of passing because there was nothing to lose.
 *
 * Non-writing: fills a form, reloads, reads it back. Never submits.
 *
 * Usage: node tools/prove_interruption_steps.mjs
 */
import { chromium } from 'playwright';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const WORKER = 'Bryan Garcia';

// what a worker has typed by the end of each step, and what must survive a kill at that point
const STEPS = [
  { step: 1, fields: { 'f-machine': 'WH-T122 Pump A', 'f-maint-type': null, 'f-category': null } },
  // f-root-cause is a <select>: assigning a value that is not one of its options silently yields "",
  // which the first run of this probe reported as "the draft lost f-root-cause" - a defect that did
  // not exist, in a field the draft saves and restores correctly. Use a REAL option value.
  { step: 2, fields: { 'f-problem': 'WH-T122 bearing noise at 62Hz', 'f-root-cause': 'Misalignment' } },
  { step: 3, fields: { 'f-action': 'WH-T122 replaced seal', 'f-knowledge': 'WH-T122 check torque next PM' } },
];

async function signIn(page) {
  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!(window.supabase && typeof window.supabase.createClient === 'function'), { timeout: 25000 });
  await page.evaluate(async ({ worker, hive }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    await db.auth.signInWithPassword({ email: 'bryangarcia@auth.workhiveph.com', password: 'test1234' });
    try {
      localStorage.setItem('wh_worker_name', worker);
      localStorage.setItem('wh_last_worker', worker);
      localStorage.setItem('wh_active_hive_id', hive.id);
      localStorage.setItem('wh_hive_id', hive.id);
      localStorage.setItem('wh_hive_name', hive.name);
    } catch (_) { /* empty-catch-allow: identity seeding is best-effort */ }
  }, { worker: WORKER, hive: HIVE });
}

const browser = await chromium.launch();
const results = [];
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  await signIn(page);

  // start from a clean draft so a leftover cannot make a step pass for free
  await page.goto(`${SEEDER}/logbook.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);
  await page.evaluate((w) => { try { localStorage.removeItem('wh_logbook_draft_' + w); } catch (_) {} }, WORKER);

  const typed = {};
  for (const s of STEPS) {
    await page.goto(`${SEEDER}/logbook.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(5000);
    const where = await page.evaluate(() => location.pathname);
    if (!/logbook\.html$/.test(where)) throw new Error(`not on logbook (${where}) — sign-in did not hold`);

    // re-type everything up to and including this step (a reload cleared the DOM, and the point is
    // to prove the DRAFT brings it back, not that the browser did)
    await page.evaluate((all) => {
      if (typeof stepGo === 'function') stepGo(1);
      for (const [id, val] of Object.entries(all)) {
        const el = document.getElementById(id);
        if (!el || val === null) continue;
        el.value = val;
        // A value that did not TAKE (a select without that option, a disabled control) must abort
        // rather than be measured: a field the probe never actually set cannot lose anything, and
        // would pass or fail for reasons that have nothing to do with the draft.
        if (el.value !== val) throw new Error(`could not set ${id} to ${JSON.stringify(val)} — it holds ${JSON.stringify(el.value)}`);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      }
      if (typeof saveDraft === 'function') saveDraft();
    }, Object.assign(typed, s.fields));

    await page.waitForTimeout(600);

    // THE INTERRUPTION: a full reload — the OS killing a backgrounded tab, the harshest realistic case
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(5500);

    const back = await page.evaluate((all) => {
      const out = {};
      for (const id of Object.keys(all)) {
        const el = document.getElementById(id);
        out[id] = el ? el.value : '<missing>';
      }
      return out;
    }, typed);

    const lost = Object.entries(typed)
      .filter(([id, val]) => val !== null && back[id] !== val)
      .map(([id, val]) => `${id} (typed ${JSON.stringify(val)}, back ${JSON.stringify(back[id])})`);
    results.push({ step: s.step, restored: lost.length === 0, lost });
    console.log(`  killed after step ${s.step}: ${lost.length === 0 ? 'everything restored' : 'LOST ' + lost.join('; ')}`);
  }

  await page.evaluate((w) => { try { localStorage.removeItem('wh_logbook_draft_' + w); } catch (_) {} }, WORKER);
} catch (e) {
  console.log('probe error:', String(e.message || e).slice(0, 200));
  results.push({ step: 'error', restored: false, lost: [String(e.message || e).slice(0, 120)] });
} finally {
  await browser.close();
}

const pass = results.length === STEPS.length && results.every((r) => r.restored);
console.log((pass ? 'PASS' : 'FAIL')
  + ` — interruption at every step: ${results.filter((r) => r.restored).length}/${STEPS.length} steps kept their work`);
process.exit(pass ? 0 : 1);
