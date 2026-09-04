/* prove_g5d_reauth_restore.mjs — T8's G5d depth slice (2026-08-26).
 *
 * THE ORACLE: session expiry must cost one sign-in and ZERO context. G5a filter persistence is
 * localStorage-keyed (whAutoRememberFilters), so it survives a reload — this prover asserts it
 * survives the full RE-AUTH ROUND TRIP: set a filter -> the session dies -> ?signin=1&return=
 * carries the page -> sign-in -> land BACK on the page -> the filter is still applied.
 *
 * The threat this guards: anything in the re-auth path purging G5 keys (an over-eager identity
 * reset), or the return contract dropping the destination (T8's original jam: the cached name
 * made openSignIn toggle the user menu instead of the modal, swallowing the whole trip).
 *
 * SCOPE: logbook + pm-scheduler filters (the central-helper pages), PLUS T38's
 * work_survives_reauth WRITE case: the half-typed logbook entry itself (whAutoSaveDraft's
 * wh_logbook_draft_* key) rides the same round trip and restoreDraft puts the note back.
 * Bespoke-persistence pages (inventory INV_KEY, community chips) are LATER slices, not
 * covered claims — a one-page reading is never swept across views it did not measure.
 *
 * Usage: node tools/prove_g5d_reauth_restore.mjs
 */
import { chromium } from 'playwright';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const ACCT = { user: 'bryangarcia', pw: 'test1234', email: 'bryangarcia@auth.workhiveph.com', worker: 'Bryan Garcia' };

// kind 'select' picks option[pickIndex]; kind 'text' types a value (pm-scheduler's cat-filter
// is an <input list=...> with a datalist — el.options does not exist on it, which the first
// run of this prover misread as "no options rendered": the instrument's shape, not the page's).
const CASES = [
  { id: 'logbook', page: 'logbook.html', filterId: 'filter-category', kind: 'select', pickIndex: 1, storeName: 'logbook-filters' },
  { id: 'pm-scheduler', page: 'pm-scheduler.html', filterId: 'cat-filter', kind: 'text', typed: 'Mechanical', storeName: 'pm-filters' },
  // T8 (2026-08-27): inventory remembered NOTHING before today - three filter controls, no G5a
  // adoption, so a storeman who narrowed to a status and lost their session re-applied it by hand.
  // Its filter-status is a <select>, the same shape as logbook's, so the existing choreography
  // covers it; what is new is that the page is IN the roster at all.
  { id: 'inventory', page: 'inventory.html', filterId: 'filter-status', kind: 'select', pickIndex: 1,
    storeName: 'inventory-filters' },
  // T8 (2026-08-27): community remembered nothing either, and its durable state is CHIPS rather
  // than a <select> - a container of buttons with data-cat, restored by clicking so the page's own
  // setFilter() re-applies it. A worker who reads only Safety came back to All after a session
  // expiry with nothing saying the view had changed under them.
  { id: 'community', page: 'community.html', kind: 'chip', filterId: 'filter-chips',
    chipAttr: 'data-cat', chipValue: 'safety', storeName: 'community-category' },
  // T38's work_survives_reauth (WRITE side): the half-typed entry itself — not just a filter —
  // must ride the round trip. Fill f-problem, let whAutoSaveDraft's debounce write the
  // worker-scoped wh_logbook_draft_* key, die, re-auth, land: restoreDraft puts the note back.
  { id: 'logbook-draft', page: 'logbook.html', kind: 'draft', filterId: 'f-problem',
    typed: 'WH-T38-PROBE half-typed symptom before the session died',
    // ★THE KEY GAINED A HIVE SEGMENT AND THIS PROVER STILL ASKED FOR THE OLD ONE (2026-08-28).
    // logbook's DRAFT_KEY became 'wh_logbook_draft_' + (HIVE_ID || 'nohive') + '_' + WORKER_NAME
    // when drafts were hive-scoped (T51: a draft typed against hive A must not surface in hive B,
    // where it names machines that do not exist). The code improved; this gate kept asserting the
    // pre-fix key and went RED - "the G5a save never landed in wh_logbook_draft_Bryan Garcia" -
    // against a save that landed perfectly under a different name. Teach the gate, do not bend the
    // code back.
    // So it no longer RECONSTRUCTS the key: the hive id is a runtime value this prover cannot know,
    // and any format it hard-codes is a future red the day the format changes again. It RESOLVES
    // the real key from the page instead, matching the prefix and the worker suffix.
    storeKeyPrefix: 'wh_logbook_draft_' },
];

async function signInDirect(page) {
  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  // getDb EXISTS from utils.js load but THROWS until the supabase lib itself arrives -
  // 'getDb is a function' is NOT readiness (it flaked exactly that way). Wait for createClient.
  await page.waitForFunction(() => !!(window.supabase && typeof window.supabase.createClient === 'function'), { timeout: 25000 });
  return page.evaluate(async ({ email, password, worker }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    const { error } = await db.auth.signInWithPassword({ email, password });
    if (error) return { ok: false, err: error.message };
    try {
      localStorage.setItem('wh_worker_name', worker);
      localStorage.setItem('wh_last_worker', worker);
      // The HIVE half of the identity, not just the worker half. community renders its feed (and
      // therefore its filter chips) only once an active hive is seeded - without it the page sits
      // on the hive picker and #filter-chips never becomes visible, which the first run of the
      // community case reported as a 25s timeout on a page that is in fact working.
      localStorage.setItem('wh_active_hive_id', '084c113b-99c0-45c6-a8e8-b4b8349da46d');
      localStorage.setItem('wh_hive_id', '084c113b-99c0-45c6-a8e8-b4b8349da46d');
      localStorage.setItem('wh_hive_name', 'Baguio Textile Mills');
    } catch (_) { /* empty-catch-allow: identity seeding is best-effort */ }
    return { ok: true };
  }, { email: ACCT.email, password: ACCT.pw, worker: ACCT.worker });
}

const browser = await chromium.launch();
const results = [];
for (const c of CASES) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  let verdict = { id: c.id, set: null, returned: false, restored: false, note: '' };
  try {
    const s = await signInDirect(page);
    if (!s.ok) throw new Error('sign-in failed: ' + s.err);

    // 1. open the page, pick a non-default filter value (the change event fires the G5a save).
    //    The draft case's #f-problem lives on a LATER wizard step (hidden at load) - the draft
    //    machinery is step-agnostic (input events fire on hidden fields too), so 'attached'
    //    is the right readiness there; visible waits are for the filter controls.
    await page.goto(`${SEEDER}/${c.page}`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#' + c.filterId, { timeout: 25000, state: c.kind === 'draft' ? 'attached' : 'visible' });
    // Self-verifying set: the pages wire whAutoRememberFilters DEEP inside an async init()
    // (pm-scheduler reaches it seconds after #cat-filter is parseable), so a set-once probe
    // fires before the save listener exists and reads its own race as a page defect. Retry
    // the set until the G5 store actually holds it — positive evidence the save landed.
    // ★RESOLVED AT READ TIME, NOT BEFORE THE WRITE. A first cut looked the key up once up front,
    // which is too early by construction: nothing matches the prefix until the debounced save has
    // actually landed, so it always fell back to the historic name and the gate stayed red for the
    // reason it was already red. The prefix travels INTO the page and the lookup happens on every
    // poll, beside the read it informs.
    const storeKey = c.storeKeyFn ? c.storeKeyFn(ACCT.worker) : `wh_view_${c.page}_${c.storeName}`;
    const storeKeyPrefix = c.storeKeyPrefix || null;
    const storeKeySuffix = ACCT.worker;
    const tSet = Date.now();
    while (Date.now() - tSet < 20000 && !verdict.set) {
      const got = await page.evaluate(({ fid, kind, idx, typed, key, attr, keyPre, keySuf }) => {
        // find the live key when a PREFIX was given, else use the exact key
        const resolveKey = () => {
          if (!keyPre) return key;
          try {
            const hit = Object.keys(localStorage).filter((k) => k.indexOf(keyPre) === 0 && k.endsWith(keySuf));
            return hit[0] || key;
          } catch (_) { return key; }
        };
        const el = document.getElementById(fid);
        if (!el) return null;
        // A CHIP filter is a container of buttons, not a form control - there is no .value to set
        // and no change event to fire. Click the real chip so the page's own handler runs, then
        // read whichever chip ended up active. Same reason the helper restores by clicking.
        if (kind === 'chip') {
          const target = el.querySelector('[' + attr + '="' + typed + '"]');
          if (!target) return null;
          target.click();
          const act = el.querySelector('.active,[aria-pressed="true"]');
          let saved0 = null;
          try { saved0 = localStorage.getItem(resolveKey()); } catch (_) { /* empty-catch-allow */ }
          return { value: act ? act.getAttribute(attr) : null, saved: saved0 };
        }
        if (kind === 'select') {
          if (!el.options || el.options.length <= idx) return null;
          el.selectedIndex = idx;
        } else {
          el.value = typed;
        }
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        let saved = null;
        try { saved = localStorage.getItem(resolveKey()); } catch (_) { /* empty-catch-allow: storage read is best-effort */ }
        return { value: el.value, saved };
      }, { fid: c.filterId, kind: c.kind, idx: c.pickIndex, typed: c.typed || c.chipValue, key: storeKey,
           attr: c.chipAttr, keyPre: storeKeyPrefix, keySuf: storeKeySuffix });
      if (got && got.saved && got.saved.includes(got.value)) { verdict.set = got.value; break; }
      await page.waitForTimeout(700);
    }
    if (!verdict.set) throw new Error('the G5a save never landed in ' + storeKey + ' within 20s');

    // 2. the session dies (token gone; G5 keys are NOT auth keys and must survive)
    await page.evaluate(async () => {
      const db = (typeof getDb === 'function') ? getDb() : window.db;
      await db.auth.signOut();
    });

    // 3. the T8 return contract: sign in via the modal, land back on the page
    await page.goto(`${SEEDER}/index.html?signin=1&return=${c.page}`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#si-username', { state: 'visible', timeout: 20000 });
    await page.fill('#si-username', ACCT.user);
    await page.fill('#si-password', ACCT.pw);
    await Promise.all([
      // ANCHOR THE ARRIVAL TO THE PATH, NOT THE WHOLE URL (2026-08-28). The old regex was the bare
      // filename, and the URL we start from is `index.html?signin=1&return=logbook.html` - which
      // CONTAINS 'logbook.html' in its query string. So `returned` went true while the browser had
      // never left index.html, and the real failure then surfaced as "the filter is not visible",
      // pointing at the page instead of at the arrival that never happened. Require a leading '/'
      // and a path boundary, so the return PARAMETER can never satisfy the check it is the input to.
      page.waitForURL(new RegExp('/' + c.page.replace('.', '\.') + '($|[?#])'), { timeout: 30000 }),
      page.click('#si-btn'),
    ]);
    verdict.returned = true;

    // 4. the filter is still applied after the round trip (poll: restore() timing differs per
    //    page — a fixed 1200ms once misread pm-scheduler; patience is part of the instrument)
    await page.waitForSelector('#' + c.filterId, { timeout: 25000, state: c.kind === 'draft' ? 'attached' : 'visible' });
    let after = null;
    const tR = Date.now();
    while (Date.now() - tR < 8000) {
      after = await page.evaluate(({ fid, kind, attr }) => {
        const el = document.getElementById(fid);
        if (!el) return null;
        if (kind === 'chip') {
          const act = el.querySelector('.active,[aria-pressed="true"]');
          return act ? act.getAttribute(attr) : null;
        }
        return el.value;
      }, { fid: c.filterId, kind: c.kind, attr: c.chipAttr });
      if (after === verdict.set) break;
      await page.waitForTimeout(500);
    }
    verdict.restored = after === verdict.set;
    verdict.note = `set='${verdict.set}' after='${after}'`;
  } catch (e) {
    verdict.note = String(e).slice(0, 160);
  } finally {
    await ctx.close();
  }
  results.push(verdict);
  console.log(`${verdict.returned && verdict.restored ? 'ok' : 'RED'}  ${c.id}: returned=${verdict.returned} restored=${verdict.restored}  ${verdict.note}`);
}
await browser.close();

const bad = results.filter(r => !(r.returned && r.restored));
console.log((bad.length ? 'FAIL' : 'PASS') + ` — G5d re-auth restore: ${results.length - bad.length}/${results.length} pages keep their filter across the auth round trip.`);
process.exit(bad.length ? 1 : 0);
