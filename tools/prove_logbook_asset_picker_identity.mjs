// prove_logbook_asset_picker_identity.mjs — the logbook asset picker must find MY assets by IDENTITY,
// not by my display name.
//
// THE BUG THIS LOCKS (Ian, 2026-10-04): "in my logbook, in the select an asset, there is nothing there,
// but I can see it in my asset hub — why is it my old registered assets that I put cannot be seen in
// select asset but it can be seen in asset hub?"
//
// Two surfaces asked two different questions about the same rows:
//   asset-hub.html  scopeNodes()  ->  hive_id = HIVE OR (hive_id IS NULL AND auth_uid = me)
//   logbook.html    initAssets()  ->  hive_id = HIVE AND status='approved'  UNION  worker_name = <name>
// and asset-hub's own comment already stated the rule: "Scoped on auth_uid, not worker_name — the name
// is display text, the uid is the identity the row was bound to on insert (bind_asset_nodes_submitter)."
//
// Read that trigger and the asymmetry is exact. It ALWAYS sets NEW.auth_uid := auth.uid(), but it only
// overwrites worker_name when
//     SELECT worker_name FROM hive_members WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id
// returns a row — and for a PERSONAL asset NEW.hive_id is NULL, so `hive_id = NULL` is never true and
// v_name stays NULL. worker_name therefore keeps whatever the client sent at that moment and is frozen
// there, while auth_uid stays correct forever. WORKER_NAME in the page is
// localStorage.getItem('wh_last_worker') — free text with nothing binding it to the column, and a solo
// account has no hive_members row at all, so the server holds no record of their name to reconcile
// against. Any later divergence makes the asset visible in Asset Hub and invisible in the picker.
//
// THE SUBJECT: driverben / Ben Ocampo owns exactly one personal asset — BEN 4477, "2021 Mitsubishi
// Mirage GLX", hive_id NULL, approved. A personal vehicle on an account that also has a hive
// membership: the two-home case, and structurally what was reported.
//
// ★THE VACUITY GUARD. Asserting "the picker still shows it after I drift the name" proves nothing
// unless the drift genuinely breaks the OLD query — otherwise the test passes even with the fix
// reverted. So this also runs the old shape through the same authenticated client and REQUIRES it to
// return zero. If that ever stops being true the drift has stopped being a drift, and the test says so
// instead of going quietly green.
import { chromium } from 'playwright';
import { SEEDER } from './prover_harness.mjs';

const WHO = { username: 'driverben', password: 'test1234', real: 'Ben Ocampo' };
const DRIFT = 'ben ocampo';          // the same person, one case difference
const TAG = 'BEN 4477';              // his personal asset, hive_id NULL

const problems = [];
const notes = [];

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await ctx.newPage();

async function signIn() {
  await page.goto(`${SEEDER}/workhive/index.html?signin=1`, { waitUntil: 'load', timeout: 30000 });
  await page.fill('#si-username', WHO.username);
  await page.fill('#si-password', WHO.password);
  await page.click('#si-btn');
  await page.waitForFunction(() => !!localStorage.getItem('wh_last_worker'), null, { timeout: 15000 })
            .catch(() => {});
  return page.evaluate(() => localStorage.getItem('wh_last_worker'));
}

// Read what the PICKER actually holds, the way the page holds it.
//
// ★WAIT FOR THE READING TO SETTLE, NOT FOR THE SYMBOL TO EXIST (2026-10-04). The first version waited
// on `typeof _assets !== 'undefined'` and then slept. `_assets` is declared long before initAssets()
// finishes and is assigned more than once on the way (a localStorage list, then the DB union), so that
// wait resolved mid-flight and the same page read 9 assets on one pass and 0 on another - the prover
// reported a vanished asset that a flat-wait diagnostic showed present both times. The page's own
// completion signal cannot be used either: refreshAssetCountBadge() HIDES the badge when the count is
// 0, so it cannot tell "loaded, empty" from "still loading". So: poll until two readings one second
// apart agree, which is true for a populated list and for a genuinely empty one.
async function pickerAssets() {
  await page.goto(`${SEEDER}/workhive/logbook.html`, { waitUntil: 'load', timeout: 45000 });
  const read = () => page.evaluate(() => {
    const a = (typeof _assets !== 'undefined' && Array.isArray(_assets)) ? _assets : null;
    return a ? a.map(x => x.asset_id || x.tag || x.name) : null;
  });
  // ★AN EMPTY READING NEEDS MORE PROOF THAN A FULL ONE (2026-10-04). "Two equal readings a second apart"
  // settled on the INITIAL empty array: `_assets` is declared `[]` long before initAssets resolves, and
  // once the picker grew a third query a loaded host took >1s to answer, so two reads agreed at zero and
  // the prover reported BEN 4477 VANISHED on a page that a direct probe showed holding it. A non-empty
  // reading cannot be the pre-load state, so two agreements are enough; an empty one must also survive a
  // minimum wall-clock wait and three agreements, which keeps the genuinely-empty case (a page with no
  // guard at all - the teeth case) detectable instead of trading one flake for a blind spot.
  const MIN_EMPTY_MS = 9000;
  const t0 = Date.now();
  await page.waitForTimeout(3000);
  let prev = await read();
  let agree = 0;
  for (let i = 0; i < 24; i++) {
    await page.waitForTimeout(1000);
    const now = await read();
    const same = prev !== null && now !== null && prev.length === now.length
                 && prev.every((t, k) => t === now[k]);
    agree = same ? agree + 1 : 0;
    prev = now;
    if (!same) continue;
    if (now.length > 0 && agree >= 1) return now;
    if (now.length === 0 && agree >= 2 && Date.now() - t0 >= MIN_EMPTY_MS) return now;
  }
  notes.push('WARNING: the asset list never settled across 18 one-second reads; reporting the last one');
  return prev;
}

const signedAs = await signIn();
if (signedAs !== WHO.real) problems.push(`sign-in stamped "${signedAs}", expected "${WHO.real}"`);

// ── 1 · baseline, with the stored name intact ────────────────────────────────────────────────────
const before = await pickerAssets();
notes.push(`baseline (name "${WHO.real}"): ${before ? before.length : 'no _assets'} asset(s), `
         + `${TAG} present: ${before ? before.includes(TAG) : 'n/a'}`);
if (!before) problems.push('the picker never populated _assets at all on the baseline load');
else if (!before.includes(TAG)) problems.push(`${TAG} is missing from the picker even with the name intact`);

// ── 2 · drift ONLY the display name in localStorage; nothing server-side is touched ──────────────
await page.evaluate((d) => localStorage.setItem('wh_last_worker', d), DRIFT);
const after = await pickerAssets();
notes.push(`after drift (name "${DRIFT}"): ${after ? after.length : 'no _assets'} asset(s), `
         + `${TAG} present: ${after ? after.includes(TAG) : 'n/a'}`);
if (!after) problems.push('the picker never populated _assets after the name drift');
else if (!after.includes(TAG)) {
  problems.push(`${TAG} VANISHED from the picker when only the display name changed - the picker is `
              + `keyed on worker_name, so a renamed person loses their own assets while Asset Hub, `
              + `which keys on auth_uid, still shows them`);
}

// ── 3 · the vacuity guard: the OLD query must really be broken by this drift ─────────────────────
const probe = await page.evaluate(async (drift) => {
  const out = {};
  try {
    // `db` is declared `const db = getDb(...)` at the top level of a CLASSIC script, which binds it in
    // the global LEXICAL environment - reachable as a bare identifier, never as window.db. Reaching for
    // window.db returned undefined and the vacuity guard refused the run rather than passing on an
    // unverified probe, which is the behaviour that caught this.
    const client = (typeof db !== 'undefined') ? db : window.db;
    if (!client) return { probeError: 'no Supabase client reachable as `db` or window.db' };
    const uid = (await client.auth.getSession()).data.session.user.id;
    const oldQ = await client.from('asset_nodes').select('id').eq('worker_name', drift).is('hive_id', null);
    const newQ = await client.from('asset_nodes').select('id').eq('auth_uid', uid).is('hive_id', null);
    out.oldNameRows = oldQ.error ? `error: ${oldQ.error.message}` : (oldQ.data || []).length;
    out.newUidRows  = newQ.error ? `error: ${newQ.error.message}` : (newQ.data || []).length;
  } catch (e) { out.probeError = String(e).slice(0, 160); }
  return out;
}, DRIFT);
notes.push(`same client, old shape (worker_name="${DRIFT}", hive_id IS NULL): ${probe.oldNameRows} row(s); `
         + `new shape (auth_uid=me, hive_id IS NULL): ${probe.newUidRows} row(s)`
         + (probe.probeError ? `  [probe error: ${probe.probeError}]` : ''));
if (probe.probeError) problems.push(`the in-page probe could not run (${probe.probeError}), so the `
  + `vacuity guard could not be evaluated - an unverified guard is treated as failing, not as passing`);
if (probe.oldNameRows !== 0) {
  problems.push(`VACUOUS TEST: the old name-keyed query still returned ${probe.oldNameRows} row(s) under `
              + `the drifted name, so this run would pass even with the fix reverted. Pick a drift the `
              + `column genuinely does not match.`);
}
if (probe.newUidRows === 0) {
  problems.push(`the identity-keyed query returned 0 rows - the subject owns no personal asset by uid, `
              + `so there is nothing for this test to protect (reseed ${TAG} for ${WHO.real})`);
}

await browser.close();

console.log(`\nLOGBOOK ASSET PICKER · identity, not display name · ${WHO.real}`);
console.log('='.repeat(78));
for (const n of notes) console.log(`  ${n}`);
if (problems.length) {
  console.log('\n  FINDINGS:');
  for (const p of problems) console.log(`    - ${p}`);
  console.log(`\nFAIL logbook-asset-picker-identity - ${problems.length} finding(s)`);
} else {
  console.log('\nPASS logbook-asset-picker-identity - the picker finds this person\'s own asset by '
            + 'auth_uid, so it survives a display-name change that empties the name-keyed query');
}
process.exit(problems.length ? 1 : 0);
