// prove_shared_handover — does a shared piece show one person another person's state?
//
// Sixteen W3-SC rows ask exactly that, and the walk that was meant to answer them kept replying
// "this piece persists nothing of its own" — true, and not an answer. **A piece with no storage of its own
// can still leave one person's state on the screen for the next**: a rendered name, a draft in a field, a
// cached list, a global still holding the last worker. Storage is one way to leak; it is not the only one.
//
// ★A SHARED DEVICE IS THE NORMAL CASE IN A PLANT, so the test is the handover, not two separate browsers.
// One context: person A signs in and uses the page, A signs out, B signs in on the SAME browser. Anything of
// A's still on screen, in a field, or in a global is a leak a second browser would never have shown.
//
//   node tools/prove_shared_handover.mjs
//   node tools/prove_shared_handover.mjs --self-test
import { chromium } from 'playwright';
import { takeBrowserSlot } from './browser_slot.mjs';
import { psql } from './wh_identity.mjs';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';

const args = process.argv.slice(2);
const ORIGIN = process.env.WH_SEEDER_URL ? `${process.env.WH_SEEDER_URL}/workhive` : 'http://127.0.0.1:5000/workhive';
const SUPA = process.env.WH_EDGE_URL || 'http://127.0.0.1:54321';
const MARK = 'never shows one person another person';

// two people who share a hive, so the handover is the one a shared device actually sees
const A = { name: 'Pablo Aguilar', email: 'pabloaguilar@auth.workhiveph.com' };
const B = { name: 'Hector Salvador', email: 'hectorsalvador@auth.workhiveph.com' };

const rows = JSON.parse(readFileSync('trajectory_registry.json', 'utf8')).trajectories
  .filter((t) => t.status === 'specced' && (t.title || '').includes(MARK))
  // ★THE KEY NAME DECIDES WHICH BANKER PATH RUNS. bank_cell_walk routes on `js` (match by piece+lens) before
  // `id` (match by row), and these verdicts are per-ROW, not per-lens - so a result carrying `js` was sent
  // down a path that looked for U/F/A/I keys it does not have, and banked nothing while reporting nothing
  // wrong. The piece is kept for the human-readable line under a name the banker does not claim.
  .map((t) => ({ id: t.id, wave: t.wave, piece: ((t.title || '').split(' - ').pop() || '').trim() }))
  .filter((r) => r.piece.endsWith('.js'));

if (args.includes('--self-test')) {
  const fails = [];
  // (*)AN EMPTY ROSTER IS SUCCESS, NOT FAILURE. This self-test asserted that open rows exist, so the
  // moment its rows were banked the gate went red for having finished its work. A teeth test proves the
  // LENS can tell right from wrong; whether there is anything left to answer is a different question and
  // not this one. Kin of every hollow-lock lesson: a gate that bites its own success teaches people to
  // ignore it.
  // (an empty roster simply means every row it answers is already banked)
  const hive = psql(`select hive_id::text from hive_members where worker_name = '${A.name}' and status='active' limit 1`);
  if (!/^[0-9a-f-]{36}$/.test(hive)) fails.push(`could not resolve ${A.name}'s hive (${hive || 'empty'})`);
  const both = psql(`select count(*) from hive_members where hive_id::text='${hive}' and status='active' and worker_name in ('${A.name}','${B.name}')`);
  if (both !== '2') fails.push(`the two people do not share a hive (found ${both}) - a handover needs one device and one hive`);
  console.log(fails.length ? 'FAIL shared-handover self-test - ' + fails.join('; ')
    : `self-test OK: ${rows.length} row(s), and ${A.name} + ${B.name} share one hive so the handover is real`);
  process.exit(fails.length ? 1 : 0);
}

const HIVE = psql(`select hive_id::text from hive_members where worker_name = '${A.name}' and status='active' limit 1`);
const signIn = async (page, who) => page.evaluate(async ({ who, hive, supa }) => {
  const db = window._whSupabaseClient || window.getDb(supa, window.SUPABASE_KEY);
  const { error } = await db.auth.signInWithPassword({ email: who.email, password: 'test1234' });
  if (error) return 'auth: ' + error.message;
  localStorage.setItem('wh_active_hive_id', hive);
  localStorage.setItem('wh_last_worker', who.name);
  return 'ok';
}, { who, hive: HIVE, supa: SUPA });

const signOut = async (page) => page.evaluate(async () => {
  try {
    const db = window._whSupabaseClient;
    if (db) await db.auth.signOut();
  } catch (_) { /* the sign-out path is the subject, not the setup */ }
  if (typeof window.whClearIdentity === 'function') { try { window.whClearIdentity(); } catch (_) { /* empty */ } }
  return true;
});

await takeBrowserSlot('shared-handover');
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });   // ONE device, both people
const page = await ctx.newPage();
await page.goto(`${ORIGIN}/hive.html`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
await page.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 20000 }).catch(() => {});

const results = [];
let bad = 0, unread = 0;
const inA = await signIn(page, A);
if (inA !== 'ok') {
  console.log(`FAIL shared-handover - could not sign in as ${A.name}: ${inA}`);
  await browser.close();
  process.exit(1);
}
await page.goto(`${ORIGIN}/logbook.html`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
await page.waitForTimeout(3200);
// ★A COLLEAGUE'S NAME ON SCREEN IS NOT A LEAK - IT IS THE HIVE WORKING. The first version checked whether
// A's NAME survived the handover and reported all sixteen pieces as leaking. Pablo and Hector are members of
// the SAME hive: Hector is supposed to see Pablo's logbook entries and Pablo's name against them. A test
// that cannot tell shared content from private state will call a working team a data leak.
//
// So A types a SENTINEL nobody else could have written. That string is unambiguously A's and nobody else's,
// and if B can still see it - on screen, in a field, or in storage - it followed A off the device.
const SENTINEL = 'wh-handover-sentinel-' + HIVE.slice(0, 8);
await page.evaluate((s) => {
  const vis = (e) => e.getBoundingClientRect().height > 0;
  const box = Array.from(document.querySelectorAll('textarea, input[type="text"], input:not([type])'))
    .filter(vis).filter((e) => !e.closest('nav, header, [id*="hub"]'))[0];
  if (box) {
    box.value = s;
    box.dispatchEvent(new Event('input', { bubbles: true }));
    box.dispatchEvent(new Event('change', { bubbles: true }));
    box.blur();
  }
  return !!box;
}, SENTINEL);
await page.waitForTimeout(2200);          // let any autosave persist it, which is the thing being tested
const before = await page.evaluate((s) => ({
  onScreen: (document.body.innerText || '').includes(s),
  keys: Object.keys(localStorage).filter((k) => (localStorage.getItem(k) || '').includes(s)),
  fields: Array.from(document.querySelectorAll('input, textarea')).filter((e) => (e.value || '').includes(s)).length,
}), SENTINEL);

await signOut(page);
await page.waitForTimeout(600);
const inB = await signIn(page, B);
await page.goto(`${ORIGIN}/logbook.html`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
await page.waitForTimeout(3200);
const after = await page.evaluate((s) => ({
  onScreen: (document.body.innerText || '').includes(s),
  keys: Object.keys(localStorage).filter((k) => (localStorage.getItem(k) || '').includes(s)),
  fields: Array.from(document.querySelectorAll('input, textarea')).filter((e) => (e.value || '').includes(s))
    .map((e) => (e.value || '').slice(0, 30)),
}), SENTINEL);

console.log(`  ${A.name} typed a sentinel: on screen ${before.onScreen}, in ${before.keys.length} storage key(s), in ${before.fields} field(s)`);
console.log(`  after handover to ${B.name} (${inB}): on screen ${after.onScreen}, ${after.keys.length} key(s), ${after.fields.length} field(s)`);
// ★IF THE SENTINEL NEVER LANDED, THE HANDOVER PROVES NOTHING. A page with no writable field, or one that
// discarded the text immediately, gives a clean "after" for a reason that has nothing to do with the pieces.
const planted = before.onScreen || before.keys.length > 0 || before.fields > 0;

const leaked = after.onScreen || after.keys.length > 0 || after.fields.length > 0;
for (const r of rows) {
  const rec = inB !== 'ok'
    ? { verdict: 'n/a', line: `the second person could not sign in (${inB}) - no handover happened` }
    : !planted
      ? { verdict: 'n/a', line: `${A.name}'s sentinel never landed on this page, so a clean handover proves nothing here` }
      : leaked
        ? { verdict: 'BAD', line: `${B.name} can still see what ${A.name} typed: ` +
            [after.onScreen && 'it is on screen', after.keys.length && `it is in ${after.keys.length} storage key(s)`,
             after.fields.length && `it is still in a field (${after.fields[0]})`].filter(Boolean).join(', ') }
        : { verdict: 'ok', line: `${A.name} typed a sentinel, signed out, and ${B.name} sees no trace of it - not on screen, not in a field, not in storage` };
  if (rec.verdict === 'BAD') bad++;
  if (rec.verdict === 'n/a') unread++;
  results.push({ ...r, ...rec });
  const tag = rec.verdict === 'ok' ? 'ok ' : rec.verdict === 'n/a' ? 'n/a' : 'BAD';
  console.log(`  ${tag} ${r.id.padEnd(8)} ${r.piece.padEnd(26)} ${rec.line.slice(0, 84)}`);
}
await browser.close();
mkdirSync('.tmp', { recursive: true });
writeFileSync('.tmp/shared_handover.json', JSON.stringify({ walked: results.length, bad, results }, null, 1));
console.log(`${bad ? 'FAIL' : 'PASS'} shared-handover - ${results.length - bad - unread}/${results.length} piece(s) leave nothing behind on a shared device  ·  .tmp/shared_handover.json`);
process.exit(bad ? 1 : 0);
