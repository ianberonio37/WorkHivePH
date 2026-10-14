// prove_logbook_hive_restore.mjs - a hive member whose device lost its stored hive still sees the hive's assets
// when the logbook is opened DIRECTLY (gate `logbook-hive-restore`, 2026-10-14).
//
// WHY. Ian, 2026-10-14: "I still can't find my registered assets, it is still missing, when I access the logbook.
// I thought we already sort it in trajectories roadmap." Read on production: his account is an active SUPERVISOR
// of one hive with 6 approved assets, all bound to his account, none personal. The 2026-10-04 fix
// (prove_logbook_asset_picker_identity.mjs) was for PERSONAL assets in solo mode, so it could not reach him.
// What did: until the 2026-10-13 release the logbook checked membership by NAME, and any drift between the name
// a device had stored and the membership row read as "no longer a member" - the page DELETED the stored hive.
// With no stored hive every page runs solo, where a hive's assets cannot appear, and only index.html refilled
// it. utils.js whEnsureHiveContext now refills it from the account on any page that asks.
//
// THE WALK (the subject has Ian's shape: one hive, approved hive assets bound to his account, no personal ones):
//   1. sign in on the home, which seats the hive;
//   2. do what the old logbook did - delete the stored hive - and drift the stored name by case;
//   3. open logbook.html DIRECTLY and read the page's own HIVE_ID and _assets.
//   PASS needs: the hive re-seated, and his asset in the picker's list.
// TEETH, same run: utils.js is served with the helper renamed away, and the same walk must come back SOLO with an
// empty list - otherwise the restore is not what makes the pass. VACUITY: his personal (hive-less) assets must be 0,
// or a solo page could show them and the empty-list half would mean nothing.
//
//   node tools/prove_logbook_hive_restore.mjs
import { chromium } from 'playwright';
import { SEEDER } from './prover_harness.mjs';

const WHO = { username: 'leandromarquez', password: 'test1234', real: 'Leandro Marquez' };
const HIVE = '084c113b-99c0-45c6-a8e8-b4b8349da46d';   // Baguio Textile Mills
const TAG = 'AC-002';                                  // one of his approved hive assets
const DRIFT = 'leandro marquez';                       // the same person, one case difference
const WIPE = ['wh_active_hive_id', 'wh_hive_id', 'wh_hive_name', 'wh_hive_role', 'wh_hives'];

const problems = [];
const notes = [];
const browser = await chromium.launch();

async function walk(disableHelper) {
  // serviceWorkers: 'block' - a page served by the service worker never reaches ctx.route, so the teeth walk
  // would get the real utils.js and "fail" for the wrong reason.
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  if (disableHelper) {
    await ctx.route('**/utils.js*', async (route) => {
      const res = await route.fetch();
      const body = (await res.text()).replace('async function whEnsureHiveContext(', 'async function whEnsureHiveContext_disabled(');
      await route.fulfill({ response: res, body });
    });
  }
  const page = await ctx.newPage();
  await page.goto(`${SEEDER}/workhive/index.html?signin=1`, { waitUntil: 'load', timeout: 30000 });
  await page.fill('#si-username', WHO.username);
  await page.fill('#si-password', WHO.password);
  await page.click('#si-btn');
  await page.waitForFunction(() => !!localStorage.getItem('wh_active_hive_id'), null, { timeout: 20000 }).catch(() => {});
  const seatedAtSignIn = await page.evaluate(() => localStorage.getItem('wh_active_hive_id'));
  await page.evaluate(([keys, drift]) => { keys.forEach((k) => localStorage.removeItem(k)); localStorage.setItem('wh_last_worker', drift); }, [WIPE, DRIFT]);
  await page.goto(`${SEEDER}/workhive/logbook.html`, { waitUntil: 'load', timeout: 45000 });
  // settle: the list is final once two one-second reads agree (an empty list must hold for 9s - a slow load is not "empty")
  const read = () => page.evaluate(() => ({
    hive: (typeof HIVE_ID !== 'undefined') ? HIVE_ID : 'undeclared',
    tags: (typeof _assets !== 'undefined' && Array.isArray(_assets)) ? _assets.map((a) => a.asset_id || a.tag || a.name) : null,
    stored: localStorage.getItem('wh_active_hive_id'),
  }));
  const t0 = Date.now();
  await page.waitForTimeout(3000);
  let prev = await read();
  let agree = 0;
  for (let i = 0; i < 24; i++) {
    await page.waitForTimeout(1000);
    const now = await read();
    const same = prev.tags !== null && now.tags !== null && prev.tags.length === now.tags.length && prev.hive === now.hive;
    agree = same ? agree + 1 : 0;
    prev = now;
    if (same && now.tags.length > 0 && agree >= 1) break;
    if (same && now.tags.length === 0 && agree >= 2 && Date.now() - t0 >= 9000) break;
  }
  let personal = null;
  if (!disableHelper) {
    personal = await page.evaluate(async () => {
      const uid = (await db.auth.getSession()).data.session.user.id;
      const r = await db.from('asset_nodes').select('id').eq('auth_uid', uid).is('hive_id', null);
      return r.error ? `error: ${r.error.message}` : (r.data || []).length;
    }).catch((e) => `error: ${String(e).slice(0, 80)}`);
  }
  // the same wipe again, then ASSET HUB opened directly: its register must list the hive's asset again
  await page.evaluate((keys) => keys.forEach((k) => localStorage.removeItem(k)), WIPE);
  await page.goto(`${SEEDER}/workhive/asset-hub.html`, { waitUntil: 'load', timeout: 45000 });
  let hub = { stored: null, listed: false };
  for (let i = 0; i < 20; i++) {
    await page.waitForTimeout(1000);
    hub = await page.evaluate((tag) => ({
      stored: localStorage.getItem('wh_active_hive_id'),
      listed: ((document.getElementById('asset-list') || {}).innerText || '').includes(tag),
    }), TAG);
    if (hub.listed) break;
  }
  // and a page with NO start-up restore of its own: pm-scheduler relies on utils.js whHiveRecovery, which seats the
  // hive after load and reloads once. Same wipe; the page must end in hive mode.
  await page.evaluate((keys) => { keys.forEach((k) => localStorage.removeItem(k)); sessionStorage.removeItem('wh_hive_recovered'); }, WIPE);
  await page.goto(`${SEEDER}/workhive/pm-scheduler.html`, { waitUntil: 'load', timeout: 45000 });
  let pm = { hive: null, stored: null };
  for (let i = 0; i < 25; i++) {
    await page.waitForTimeout(1000);
    try {
      pm = await page.evaluate(() => ({ hive: (typeof HIVE_ID !== 'undefined') ? HIVE_ID : 'undeclared', stored: localStorage.getItem('wh_active_hive_id') }));
    } catch (_) { continue; }   // mid-reload: the old document is gone, read again
    if (pm.hive === HIVE) break;
  }
  await ctx.close();
  return { seatedAtSignIn, ...prev, personal, hub, pm };
}

// ★THE SKEW WALK (2026-10-14, the MCP journey of Ian's phone): an old utils.js held in the HTTP cache, served to every
// <script src> until the page fetch()es the file past the cache - the logbook's self-heal - and the real file after.
async function skewWalk() {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const seen = [];
  let fresh = false;
  await ctx.route('**/utils.js*', async (route) => {
    const kind = route.request().resourceType();
    if (kind === 'fetch') fresh = true;
    const res = await route.fetch();
    let body = await res.text();
    if (!fresh) body = body.replace('async function whEnsureHiveContext(', 'async function whEnsureHiveContext_disabled(');
    seen.push(`${kind}:${fresh ? 'fresh' : 'stale'}`);
    await route.fulfill({ response: res, body });
  });
  const page = await ctx.newPage();
  await page.goto(`${SEEDER}/workhive/index.html?signin=1`, { waitUntil: 'load', timeout: 30000 });
  await page.fill('#si-username', WHO.username);
  await page.fill('#si-password', WHO.password);
  await page.click('#si-btn');
  await page.waitForFunction(() => !!localStorage.getItem('wh_active_hive_id'), null, { timeout: 20000 }).catch(() => {});
  await page.evaluate((keys) => { keys.forEach((k) => localStorage.removeItem(k)); sessionStorage.clear(); }, WIPE);
  seen.length = 0; fresh = false;
  await page.goto(`${SEEDER}/workhive/logbook.html`, { waitUntil: 'load', timeout: 45000 });
  let st = { hive: null, tags: null, guard: null };
  for (let i = 0; i < 25; i++) {
    await page.waitForTimeout(1000);
    try {
      st = await page.evaluate(() => ({
        hive: (typeof HIVE_ID !== 'undefined') ? HIVE_ID : 'undeclared',
        tags: (typeof _assets !== 'undefined' && Array.isArray(_assets)) ? _assets.map((a) => a.asset_id || a.tag || a.name) : null,
        guard: sessionStorage.getItem('wh_utils_refetched'),
      }));
    } catch (_) { continue; }   // mid-reload
    if (st.hive === HIVE && st.tags && st.tags.includes(TAG)) break;
  }
  await ctx.close();
  return { ...st, seen: seen.slice() };
}

const fixed = await walk(false);
notes.push(`with the restore: signed in to ${fixed.seatedAtSignIn === HIVE ? 'his hive' : fixed.seatedAtSignIn}; after the wipe + name drift the logbook `
  + `read HIVE_ID=${fixed.hive === HIVE ? 'his hive' : fixed.hive}, ${fixed.tags ? fixed.tags.length : 'no'} asset(s), ${TAG} present: ${fixed.tags ? fixed.tags.includes(TAG) : 'n/a'}`);
if (fixed.seatedAtSignIn !== HIVE) problems.push(`sign-in did not seat ${WHO.real} in his hive (got ${fixed.seatedAtSignIn}) - the walk cannot start from Ian's state`);
if (fixed.hive !== HIVE) problems.push(`the logbook did not re-seat the hive after the stored one was wiped (HIVE_ID=${fixed.hive}) - a member opening it directly runs solo`);
if (!fixed.tags || !fixed.tags.includes(TAG)) problems.push(`${TAG} is not in the picker's list after the wipe - the hive's assets vanished, as they did for Ian`);
if (fixed.stored !== HIVE) problems.push(`the restored hive was not written back to the device (wh_active_hive_id=${fixed.stored}), so the next page starts solo again`);
notes.push(`with the restore, Asset Hub opened directly after the same wipe: hive ${fixed.hub.stored === HIVE ? 're-seated' : 'NOT re-seated'}, ${TAG} listed: ${fixed.hub.listed}`);
if (fixed.hub.stored !== HIVE || !fixed.hub.listed) problems.push(`Asset Hub opened directly after the wipe did not list ${TAG} (stored hive ${fixed.hub.stored}) - the register is solo and empty`);
notes.push(`with the recovery, PM Scheduler opened directly after the same wipe: HIVE_ID ${fixed.pm.hive === HIVE ? '= his hive (re-seated, one reload)' : fixed.pm.hive}`);
if (fixed.pm.hive !== HIVE) problems.push(`PM Scheduler (no start-up restore of its own) stayed solo after the wipe (HIVE_ID=${fixed.pm.hive}) - utils.js whHiveRecovery did not re-seat it`);
if (fixed.personal !== 0) problems.push(`VACUOUS: ${WHO.real} has ${fixed.personal} personal asset(s); a solo page could list those, so the empty-list half proves nothing (pick a subject with none)`);

const sk = await skewWalk();
notes.push(`skew (an old utils.js cached until the page fetches it past the cache): utils requests [${sk.seen.join(', ')}]; `
  + `HIVE_ID ${sk.hive === HIVE ? '= his hive' : sk.hive}, ${TAG} listed: ${!!(sk.tags && sk.tags.includes(TAG))}, guard ${sk.guard}`);
if (!(sk.hive === HIVE && sk.tags && sk.tags.includes(TAG))) problems.push(`with an old utils.js cached the logbook did not heal itself (HIVE_ID=${sk.hive}) - the page Ian saw: personal mode, "No assets registered yet."`);
// The once-per-tab guard now belongs to the generated skew-heal block (tools/render_skew_heal.py, BRH-D 2026-10-14), which
// CLEARS it after a clean reload so a later deploy can heal again - so after a SUCCESSFUL heal it reads empty by design,
// and reading it here proved nothing. What the guard is for - no reload loop when no fresh copy exists - is proven where
// the heal cannot succeed (skew-heal-live's stuck walk; a mutant without the guard reloaded 41 times in 12 s). Here the
// heal must be ONE refetch.
const _refetches = sk.seen.filter((x) => x.startsWith('fetch:')).length;
if (_refetches > 1) problems.push(`the self-heal refetched utils.js ${_refetches} times in one walk - a heal is one refetch, then one reload`);
if (!sk.seen.some((x) => x.startsWith('fetch:'))) problems.push('VACUOUS skew walk: the page never fetched utils.js past the cache, so the walk did not exercise the heal');

const bare = await walk(true);
notes.push(`teeth (helper renamed away): HIVE_ID=${bare.hive === null ? 'null (solo)' : bare.hive}, ${bare.tags ? bare.tags.length : 'no'} asset(s)`);
if (!(bare.hive === null && bare.tags && bare.tags.length === 0)) {
  problems.push(`NO TEETH: with whEnsureHiveContext removed the logbook still read HIVE_ID=${bare.hive} and ${bare.tags ? bare.tags.length : 'no'} asset(s) - `
    + 'something other than the restore re-seated the hive, so this gate does not prove the fix');
}

notes.push(`teeth on PM Scheduler: HIVE_ID=${bare.pm.hive === null ? 'null (solo)' : bare.pm.hive}`);
if (bare.pm.hive !== null) problems.push(`NO TEETH on PM Scheduler: without the helper it still read HIVE_ID=${bare.pm.hive}`);
notes.push(`teeth on Asset Hub: hive ${bare.hub.stored ? 're-seated by something else' : 'not re-seated'}, ${TAG} listed: ${bare.hub.listed}`);
if (bare.hub.listed || bare.hub.stored) problems.push(`NO TEETH on Asset Hub: without the helper it still listed ${TAG} / re-seated ${bare.hub.stored}`);

await browser.close();
console.log(`\nLOGBOOK · a wiped stored hive is re-seated from the account · ${WHO.real}`);
console.log('='.repeat(78));
for (const n of notes) console.log(`  ${n}`);
if (problems.length) {
  console.log('\n  FINDINGS:');
  for (const p of problems) console.log(`    - ${p}`);
  console.log(`\nFAIL logbook-hive-restore - ${problems.length} finding(s)`);
} else {
  console.log('\nPASS logbook-hive-restore - opened directly with its stored hive deleted and its name drifted, the logbook and Asset Hub re-seat the hive from the account at start-up '
    + '(and list the hive\'s assets), PM Scheduler after one reload; with the restore removed every walk is solo and empty');
}
process.exit(problems.length ? 1 : 0);
