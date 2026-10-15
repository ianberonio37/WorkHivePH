// prove_scope_empty.mjs - BRH-E (2026-10-15): an empty state never speaks for the wrong list.
//
// WHY. Ian's logbook said "No assets registered yet." - true of the PERSONAL list the page had fallen into when the device
// lost its stored hive, and silent about the hive's six assets. bug_hunt_inventory class E counted every "No ... yet."
// sentence on a page with a hive mode and a personal mode (116). The sentence misleads in exactly one state: no hive stored
// on the device while the account belongs to a hive that holds X. Since BRH-H every such page seats the hive in its own
// start-up (whStartupHive), so that state should no longer reach a person. This prover measures each row's OWN sentence:
//
//   per row, at 390 and 1280, as a MEMBER of a hive that holds data (Bryan Garcia, Baguio Textile Mills), fresh context each:
//     BASE   the device as it normally is
//     WIPED  wh_active_hive_id, wh_hive_id, wh_hive_name, wh_hive_role, wh_hives removed before any page script
//   verdict per row
//     reproduced  (--before, on the page as it was before BRH-H: git show <BASE_REF>:<page>) the sentence is on screen WIPED
//                 and NOT on BASE - the person is told "No X yet." about a list the hive fills
//     fixed       (current page) the sentence is not on screen WIPED - the hive was seated before anything rendered
//     true-empty  the sentence is on screen on BASE as well: the hive's own list is empty - the sentence is true
//     not-reached the sentence is on screen in neither state on load (a tab or a state the load does not open)
//
//   node tools/prove_scope_empty.mjs [--page a.html,...] [--viewport 390] [--json .tmp/scope_empty_results.json]
//        [--before]   read the pages as they were before BRH-H (WH_PREFIX_BASE, default 8090d050)
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname } from 'node:path';
import { SEEDER, HIVE, signIn, stubModelCalls, PAGE_QUERY } from './prover_harness.mjs';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const OUT = arg('--json', '.tmp/scope_empty_results.json');
const REVERT = process.argv.includes('--revert');   // the reproduction: today's pages with the start-up seat reverted
const BEFORE = process.argv.includes('--before') || REVERT;
const BASE_REF = process.env.WH_PREFIX_BASE || '8090d050';
const VPS = (arg('--viewport') ? [Number(arg('--viewport'))] : [390, 1280]).map((w) => [w, w === 390 ? 844 : 800]);
const WIPE = ['wh_active_hive_id', 'wh_hive_id', 'wh_hive_name', 'wh_hive_role', 'wh_hives'];

const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
const wanted = arg('--page') ? new Set(arg('--page').split(',')) : null;
const ROWS = reg.trajectories.filter((t) => t.brh && t.brh.cls === 'E' && t.status !== 'descoped' && (!wanted || wanted.has(t.brh.page)))
  .map((t) => ({ id: t.id, page: t.brh.page, key: String(t.brh.key || '').trim() }));
const PAGES = [...new Set(ROWS.map((r) => r.page))].sort();
const ACCT = { name: 'Bryan Garcia', first: 'Bryan', role: 'worker', email: 'bryangarcia@auth.workhiveph.com', password: 'test1234' };

const BROWSER = await chromium.launch();
let STATE = null;
{
  const ctx = await BROWSER.newContext({ serviceWorkers: 'block' });
  if (await signIn(ctx, { ...ACCT, hive: HIVE })) {
    const p = await ctx.newPage();
    await p.goto(`${SEEDER}/workhive/index.html`, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
    await p.waitForTimeout(2000);
    STATE = await ctx.storageState();
  }
  await ctx.close();
}
if (!STATE) { console.log('FAIL scope-empty - sign-in failed'); process.exit(1); }

// one load per (page, viewport, state) reads EVERY row's sentence on that page
async function readPage(page, [w, h], wiped, revert = REVERT) {
  const ctx = await BROWSER.newContext({ serviceWorkers: 'block', storageState: STATE });
  await stubModelCalls(ctx);
  await ctx.route('**/functions/v1/**', (r) => r.request().method() === 'OPTIONS' ? r.fallback()
    : r.fallback({ headers: { ...r.request().headers(), 'x-wh-walk-no-model': '1' } }));
  if (BEFORE && !REVERT) {
    // what git holds is what the SEEDER serves only after its rewrite (test-data-seeder/app.py _rewrite: the cloud
    // Supabase URL and key -> the local stack's). Served raw, an old page talked to production with a local session and
    // every reading was the sign-in wall - the reproduction must be the page as the seeder would have served it.
    const seed = (s) => s.split('https://hzyvnjtisfgbksicrouu.supabase.co').join('http://127.0.0.1:54321')
      .split('sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ').join('sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH');
    const old = seed(execFileSync('git', ['show', `${BASE_REF}:${page}`], { encoding: 'utf8', maxBuffer: 64 << 20 }));
    const oldUtils = seed(execFileSync('git', ['show', `${BASE_REF}:utils.js`], { encoding: 'utf8', maxBuffer: 64 << 20 }));
    await ctx.route(new RegExp(`/workhive/${page.replace(/\./g, '\\.')}(\\?.*)?$`), (r) =>
      r.request().resourceType() === 'document' ? r.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: old }) : r.fallback());
    // --page-only: the old PAGE with today's utils.js - separates what the page did from what the shared script did
    if (!process.argv.includes('--page-only')) {
      await ctx.route('**/utils.js*', (r) => r.fulfill({ status: 200, contentType: 'application/javascript', body: oldUtils }));
    }
  }
  if (revert) {
    // THE FIX REVERTED, through the seeder's own pipeline: today's pages and utils.js as served, with whStartupHive unset
    // at the end of utils.js - every page's `typeof whStartupHive === 'function'` guard then skips the start-up seat, as
    // the pages did before BRH-H. (Serving old pages from git, rewritten by hand, rendered less than the seeder served
    // even with the hive intact - hive.html 1,506 characters against 2,142 - so its readings were the harness's.)
    // The skew-heal block will refetch utils.js once and reload; the refetch answers the same, so it then carries on.
    await ctx.route('**/utils.js*', async (route) => {
      const resp = await route.fetch();
      const body = (await resp.text()) + '\n;window.whStartupHive = undefined;\n';
      return route.fulfill({ response: resp, body, headers: { ...resp.headers(), 'cache-control': 'no-store' } });
    });
  }
  if (wiped) {
    // the seat's account lookups answer 1.5 s late (the race shift-brain lost: a no-hive gate decided before the seat)
    await ctx.route(/\/rest\/v1\/(v_worker_truth|v_hives_truth)/, async (r) => { await new Promise((ok) => setTimeout(ok, 1500)); return r.fallback(); });
    // the after-load recovery SPENT for this tab (wh_hive_recovered set): the state Ian met - a page left in personal
    // mode with nothing coming to put it right. A pre-BRH-H page stays solo; a current page seats the hive in its own
    // start-up and never asks the recovery. Reading after an unspent recovery would read the page it reloaded into.
    await ctx.addInitScript((wipe) => {
      try {
        if (sessionStorage.getItem('__prove_seeded')) return;
        sessionStorage.setItem('__prove_seeded', '1');
        sessionStorage.setItem('wh_hive_recovered', 'none');
        wipe.forEach((k) => localStorage.removeItem(k));
      } catch (e) { void e; }
    }, WIPE);
  }
  const p = await ctx.newPage();
  await p.setViewportSize({ width: w, height: h });
  const q = PAGE_QUERY[page] ? PAGE_QUERY[page] + '&' : '?';
  await p.goto(`${SEEDER}/workhive/${page}${q}t=${Date.now()}`, { waitUntil: 'load', timeout: 60000 }).catch(() => {});
  await p.waitForTimeout(8000);   // the pre-fix pages' after-load recovery reloads inside this window: read AFTER it
  const text = await p.evaluate(() => (document.body ? document.body.innerText : '')).catch(() => '');
  // the MODE the page settled in: with no hive on the device at the end, every list it shows is the personal one - the
  // condition under which any of its "No X yet." sentences speaks for the wrong list
  const hive = await p.evaluate(() => { try { return localStorage.getItem('wh_active_hive_id'); } catch (e) { return null; } }).catch(() => null);
  const file = await p.evaluate(() => location.pathname.split('/').pop()).catch(() => '');
  await ctx.close();
  return { text, hive, file };
}

// the sentence as a person reads it: the row's key with its trailing period optional and whitespace collapsed
const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim();
const has = (text, key) => { const k = norm(key).replace(/\.$/, ''); return k.length > 3 && norm(text).includes(k); };

const results = [];
for (const page of PAGES) {
  const rows = ROWS.filter((r) => r.page === page);
  for (const vp of VPS) {
    const base = await readPage(page, vp, false);
    const wiped = await readPage(page, vp, true);
    // the page's MODE decides it: a member left in personal mode (no hive at the end) is the defect's condition for every
    // sentence on the page; a seated hive removes it. The sentence's own text is read too - when the load reaches it.
    const personal = !wiped.hive;
    // a reading that ENDED ON ANOTHER PAGE did not measure this one: the page sent the member away (community's redirect
    // to hive.html, which then seated them) - H's defect, not this sentence's
    const away = wiped.file && wiped.file !== page;
    for (const r of rows) {
      const onBase = has(base.text, r.key), onWiped = has(wiped.text, r.key);
      let verdict;
      if (BEFORE) verdict = away ? 'redirected-away' : personal ? (onWiped && !onBase ? 'reproduced-shown' : 'reproduced-mode') : 'seats-itself';
      // and the page itself, not only its mode: seated but showing a no-hive gate read 849 of 3,428 characters
      else verdict = personal ? 'STILL-PERSONAL' : (onWiped && !onBase ? 'STILL-SHOWN'
        : (base.text.length && wiped.text.length < 0.85 * base.text.length ? 'STILL-SHORT' : 'fixed'));
      results.push({ ...r, vp: vp[0], personal, onBase, onWiped, verdict, baseChars: base.text.length, wipedChars: wiped.text.length });
    }
    console.log(`${page.padEnd(30)} ${String(vp[0]).padEnd(5)} base=${base.text.length} wiped=${wiped.text.length} hive_at_end=${wiped.hive ? 'seated' : 'NONE'}${away ? ' ended_on=' + wiped.file : ''} `
      + rows.map((r) => r.id + ':' + results.find((x) => x.id === r.id && x.vp === vp[0]).verdict).join(' '));
  }
}
// TEETH (outside the reproduction): inventory at 390 with the start-up seat reverted must leave the member in personal
// mode - if it does not, this prover can no longer see the state it exists to rule out, and it fails itself
let teeth = null;
if (!BEFORE) {
  const t = await readPage('inventory.html', [390, 844], true, true);
  teeth = { page: 'inventory.html', hive_at_end: t.hive, bit: !t.hive };
  console.log(`  teeth - inventory.html with the seat reverted: ${t.hive ? 'SEATED (no teeth)' : 'left in personal mode, as it must'}`);
}
await BROWSER.close();
mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify({ _doc: 'prove_scope_empty.mjs - BRH-E readings, one per (row, viewport)', generated: new Date().toISOString(),
  before: BEFORE, revert: REVERT, results, teeth }, null, 1));
const tally = results.reduce((a, r) => { a[r.verdict] = (a[r.verdict] || 0) + 1; return a; }, {});
console.log(`\n${results.length} reading(s): ${JSON.stringify(tally)}; written to ${OUT}`);
const still = results.filter((r) => r.verdict.startsWith('STILL'));
if (!BEFORE && teeth && !teeth.bit) { console.log('FAIL scope-empty - NO TEETH: with the seat reverted the page still seated the hive'); process.exit(1); }
if (!BEFORE && still.length) { console.log(`FAIL scope-empty - ${still.length} reading(s) still leave a member in personal mode or show "No X yet." about a list their hive fills`); process.exit(1); }
if (BEFORE) {
  // with the fix reverted a page either left the member in personal mode (the defect's condition: reproduced), restored
  // the membership itself (seats-itself: hive.html's own recovery), or sent them to another page (redirected-away)
  const odd = results.filter((r) => !r.verdict.startsWith('reproduced'));
  console.log(odd.length ? `not reproduced on ${odd.length} (${[...new Set(odd.map((r) => r.page + ':' + r.verdict))].join(', ')})` : `REPRODUCED - every row's page left a member in personal mode`);
  process.exit(0);
}
console.log('PASS scope-empty - with the stored hive wiped (and the recovery spent) every page settles in the member\'s hive, and no sentence the load reaches says "No X yet." about a list the hive fills');
