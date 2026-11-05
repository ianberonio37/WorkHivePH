// prove_group_journeys - Wave GJ (the group journeys): the people of one scenario, each in their own browser, and every
// hand-off between them read from both ends (2026-11-04).
//
// The cube asks what ONE person can tell / may do / finds wired on a page. A team meets the hand-off: A acts, B must see
// it, C must not. This walks a scenario of tools/group_journey_census.py with one signed-in browser context per member
// (the accounts the census resolved from the database, read back from the registry rows' gj.cast), hop by hop:
//   act  the sender acts through the page's own controls (the LOG1-3 wizard for a logbook entry, the entry's own edit
//        modal for an assignment or a close, the page's own Refresh) - where a step is the platform's scheduler (the daily
//        failure-signature scan), it is triggered the way the platform lets a member trigger it, and the receipt says so
//   U    the receiver lands by the hop's channel (the page, or the URL the push carries) and the screen is read for the
//        sender's record: what moved, who did it, when
//   F    psql AS THE RECEIVER (role authenticated + their claims, RLS applies) finds the record the sender made; for a push
//        hop, the push itself is in service_outbox addressed to the receiver with the URL the hop lands on
//   I    the receiver may read it and a member of ANOTHER hive (resolved from the database, never typed) may not: 0 rows
//   A    the receiver's landing re-read under 3G (CDP throttling) while the sender's network is untouched
// Two passes, the members' viewports swapped between them (phone-390 / desktop-1280). Everything the walk writes is tagged
// and removed after; the rows it changes in place (today's analytics snapshot, the machine's alerts) are snapshotted
// first and restored (triggers off - a restore is not a member's act).
//
//   node tools/prove_group_journeys.mjs --scenario J2            -> group_journeys_report.json (+ .tmp/gj_walks/J2.json)
//   node tools/prove_group_journeys.mjs --scenario J2 --teeth    -> plants a push that never fires and a foreign member
//                                                                   who is let in; BOTH must read FAIL (exit 1 = teeth bite)
import { chromium } from 'playwright';
import { ALL_ROWS_DRAWN } from './lib/long_list_text.mjs';
import { logWizard } from './live_page_journeys.registry.mjs';
import { spawnSync } from 'child_process';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';

const ORIGIN = 'http://127.0.0.1:5000/workhive';
const SB = 'http://127.0.0.1:54321';
const KEY = 'sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH';   // the LOCAL stack's publishable key (public by design)
const REG = 'trajectory_registry_gj.json';
const OUT = 'group_journeys_report.json';
const arg = (n, d = null) => { const i = process.argv.indexOf(n); return i > 0 ? process.argv[i + 1] : d; };
const SCEN = arg('--scenario', 'J2');
const TEETH = process.argv.includes('--teeth');
const PASSES = TEETH ? ['a'] : (arg('--pass') ? [arg('--pass')] : ['a', 'b']);
const VP = { 'phone-390': { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
  'desktop-1280': { viewport: { width: 1280, height: 800 } } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const q = (s) => String(s).replace(/'/g, "''");

function psql(sql) {
  const r = spawnSync('docker', ['exec', '-i', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-At', '-F', '|', '-v', 'ON_ERROR_STOP=1'],
    { input: sql, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  if (r.status !== 0) throw new Error('psql: ' + (r.stderr || '').slice(0, 400));
  return (r.stdout || '').trim();
}
// a read AS a person: role authenticated with their claims, so every RLS policy applies exactly as it does to their page
function asUser(uid, sql) {
  const claims = JSON.stringify({ sub: uid, role: 'authenticated' });
  const out = psql(`begin;
set local role authenticated;
select set_config('request.jwt.claims', '${q(claims)}', true) is null;
select set_config('request.jwt.claim.sub', '${q(uid)}', true) is null;
select 'R|' || coalesce((${sql})::text, '');
rollback;`);
  const line = out.split('\n').find((l) => l.startsWith('R|'));
  return line ? line.slice(2) : null;
}

// ── the scenario, read from the rows the seeder wrote (gj.cast is what the census resolved from the database) ──────────
const rows = JSON.parse(readFileSync(REG, 'utf8')).trajectories.filter((r) => r.gj && r.gj.scenario === SCEN);
if (!rows.length) { console.error(`no GJ rows for scenario ${SCEN}`); process.exit(2); }
const CAST = rows[0].gj.cast;
const HOME = rows[0].gj.home;
const HOPS = [...new Map(rows.filter((r) => r.gj.handoff > 0).map((r) => [r.gj.handoff, r.gj])).values()]
  .sort((a, b) => a.handoff - b.handoff)
  .map((g) => ({ handoff: g.handoff, page: g.page, sender: g.sender, receiver: g.receiver, channel: g.channel, what: g.what }));
const HIVE_ID = psql(`select id from hives where name = '${q(HOME)}'`);

function member(key) {
  const c = CAST[key];
  // ★A PERSON WHO DOES NOT EXIST YET (2026-11-06, GJ M9 J1 / G-ONB): the census casts a new user as "minted" - the walk
  // signs them up through the front door, so they have no account, no name and no seat until their recipe makes them
  if (c.user === 'minted') return { key, ...c, user: null, uid: null, name: null, role: null, seatId: null, seatName: null, minted: true };
  const [uid, name] = psql(`select auth_uid, display_name from worker_profiles where username = '${q(c.user)}'`).split('|');
  // ★EACH PERSON STANDS IN THE HIVE THEY WERE DRAWN FROM (2026-11-05, G-MULTI): every session was seated in the home
  // hive, so G-MULTI's second supervisor - a member of the contractor's OTHER hive only - opened pages in a hive that
  // was not theirs. The census names each cast member's hive; the session is seated there.
  const seatName = c.hive && c.hive !== HOME ? c.hive : HOME;
  const seatId = seatName === HOME ? HIVE_ID : (psql(`select id from hives where name = '${q(seatName)}' limit 1`) || HIVE_ID);
  const role = psql(`select role from hive_members where hive_id = '${seatId}' and auth_uid = '${uid}' and status = 'active'`);
  return { key, ...c, uid, name, role, seatId, seatName };
}
// a member of ANOTHER hive, who belongs to nothing in this one - the I reading's third person (never typed)
// ★OUTSIDE EVERY HIVE THE SCENARIO STANDS IN (2026-11-05, G-MULTI): the witness was chosen only to be outside the home
// hive, and for a scenario that also stands in a second hive it was a member of THAT hive - it read hive B's entry and
// PM, and the I reading failed on a member who was allowed to read them. The witness belongs to none of the cast's hives.
function foreignWitness() {
  const names = [...new Set([HOME, ...Object.values(CAST).map((c) => c.hive).filter(Boolean)])].map((n) => `'${q(n)}'`).join(',');
  const [user, uid] = psql(`select w.username, w.auth_uid from hive_members m join worker_profiles w on w.auth_uid = m.auth_uid
    where m.status = 'active' and m.role = 'worker' and m.hive_id not in (select id from hives where name in (${names}))
      and not exists (select 1 from hive_members x where x.auth_uid = m.auth_uid and x.hive_id in (select id from hives where name in (${names})))
    order by w.username limit 1`).split('|');
  return { user, uid };
}

const H = (page) => ({
  click: async (sel) => { try { await page.click(sel, { timeout: 5000 }); await page.waitForTimeout(800); return true; } catch (_) { return false; } },
  fill: async (sel, v) => { try { await page.fill(sel, v, { timeout: 5000 }); return true; } catch (_) { return false; } },
  waitFor: async (sel, t = 6000) => { try { await page.waitForSelector(sel, { timeout: t, state: 'visible' }); return true; } catch (_) { return false; } },
  evalIn: (fn, a) => page.evaluate(fn, a),
});

async function session(browser, m, vpName) {
  const ctx = await browser.newContext({ ...VP[vpName], timezoneId: 'Asia/Manila', serviceWorkers: 'block' });
  await ctx.addInitScript(ALL_ROWS_DRAWN);
  // the invite link travels by the clipboard, as a supervisor's does
  await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: new URL(ORIGIN).origin }).catch(() => {});
  if (m.minted) return mintedSession(ctx, m, vpName);
  const tok = await (await fetch(`${SB}/auth/v1/token?grant_type=password`, { method: 'POST',
    headers: { apikey: KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: `${m.user}@auth.workhiveph.com`, password: 'test1234' }) })).json();
  if (!tok.access_token) throw new Error(`sign-in failed for ${m.user}`);
  await ctx.addInitScript(([t, hive, hiveName, name, r]) => {
    try {
      // a member the walk SIGNED OUT on this device (J19) stays signed out: the seat's token is not put back
      if (localStorage.getItem('wh_gj_signedout') === '1') return;
      if (!localStorage.getItem('sb-127-auth-token')) localStorage.setItem('sb-127-auth-token', JSON.stringify(t));
      // a member the walk has removed (J14, G-LEAVE) stands where the product put them, not where the walk seated them
      if (localStorage.getItem('wh_gj_noseat') === '1') return;
      localStorage.setItem('wh_last_worker', name);
      localStorage.setItem('wh_active_hive_id', hive); localStorage.setItem('wh_hive_name', hiveName);
      if (r) localStorage.setItem('wh_hive_role', r);
      Object.keys(localStorage).filter((k) => k.startsWith('wh_logbook_draft')).forEach((k) => localStorage.removeItem(k));
    } catch (_) { /* storage blocked */ }
  }, [tok, m.seatId || HIVE_ID, m.seatName || HOME, m.name, m.role]);
  // ★NO GROUP WALK SPENDS A MODEL CALL ON THE SHIFT BRIEFING (2026-11-05, G-SHIFT). shift-brain builds a plan on the
  // shift's first open, and the plan's briefing is an LLM call - J9's walks spent one per pass just by arriving. Every
  // member's request to the planner carries the LOCAL-ONLY debug_fault_inject flag (honoured only on a local runtime,
  // gate debug-hooks-prod-dead), so the plan is built from the real logbook, risk and PM rows with the deterministic
  // fallback briefing. No group walk is about the briefing's words.
  // ★AND NONE ON A REPORT OR A RECOMPUTE (2026-11-05, GJ M8): analytics-orchestrator ends its report and its
  // prescriptive recompute in a model-written action plan - J2/J3 spent one per pass on "Refresh" and "Generate Report".
  // It honours the same LOCAL-ONLY flag since M8 (gate debug-hooks-prod-dead); the plan then comes from the records.
  for (const fn of ['shift-planner-orchestrator', 'analytics-orchestrator']) {
    await ctx.route(`**/functions/v1/${fn}**`, async (route) => {
      if (route.request().method() !== 'POST') return route.continue();   // the CORS preflight passes as it was
      let body = {};
      try { body = JSON.parse(route.request().postData() || '{}'); } catch (_) { /* not JSON: sent as it was */ }
      await route.continue({ postData: JSON.stringify({ ...body, debug_fault_inject: true }) });
    });
  }
  const page = await ctx.newPage();
  page.on('dialog', (d) => d.accept().catch(() => {}));
  return { ctx, page, m, vp: vpName, token: tok.access_token };
}
// a minted person's browser: the same model-call routes, no account and no seat - their recipe signs them up
async function mintedSession(ctx, m, vpName) {
  for (const fn of ['shift-planner-orchestrator', 'analytics-orchestrator']) {
    await ctx.route(`**/functions/v1/${fn}**`, async (route) => {
      if (route.request().method() !== 'POST') return route.continue();
      let body = {};
      try { body = JSON.parse(route.request().postData() || '{}'); } catch (_) { /* not JSON: sent as it was */ }
      await route.continue({ postData: JSON.stringify({ ...body, debug_fault_inject: true }) });
    });
  }
  const page = await ctx.newPage();
  page.on('dialog', (d) => d.accept().catch(() => {}));
  return { ctx, page, m, vp: vpName, token: null };
}
// sign a minted person up through index.html's own form (from wherever the page has put them: the landing's
// "Sign Up", or the sign-in wall a link sent them to) and bind them to the walk: account id, name, user
async function signUpHere(P, who, pw) {
  if (!/index\.html/.test(P.page.url())) await go(P, 'index.html?signup=1');
  await P.page.evaluate(() => { if (typeof switchAuthTab === 'function') switchAuthTab('signup'); else if (typeof openSignUp === 'function') openSignUp(); });
  await sleep(700);
  await P.page.fill('#su-username', who.user).catch(() => {});
  await P.page.fill('#su-password', pw).catch(() => {});
  await P.page.fill('#su-confirm', pw).catch(() => {});
  await P.page.fill('#su-displayname', who.name).catch(() => {});
  await P.page.click('#su-btn').catch(() => P.page.evaluate(() => submitSignUp()));
  let uid = '';
  for (let t = 0; t < 30000 && !uid; t += 1000) { await sleep(1000); uid = psql(`select auth_uid from worker_profiles where username = '${q(who.user)}'`); }
  await sleep(3000);   // the success path then routes the person (their dashboard, or back to the link that sent them)
  Object.assign(P.m, { user: who.user, name: who.name, uid: uid || null });
  const err = await P.page.evaluate(() => { const e = document.getElementById('su-error'); return e && !e.classList.contains('hidden') ? e.textContent.trim() : ''; }).catch(() => '');
  return { ok: !!uid, err };
}

async function go(s, path) {
  // under 3G a heavy page needs longer than a minute to reach DOMContentLoaded (analytics.html: ~60 s at 390) - the A
  // reading sets s.gotoTimeout and records how long it took; everywhere else a minute is the page failing to load
  await s.page.goto(`${ORIGIN}/${path}`, { waitUntil: 'domcontentloaded', timeout: s.gotoTimeout || 60000 });
  await sleep(5000);
}
// the smallest visible element carrying the marker, and THE RECORD'S OWN CARD around it - what the person actually reads.
// ★THE "CARD" WAS ONCE THE LARGEST BLOCK UNDER 900 CHARACTERS (2026-11-04, the first J2 walk): on the logbook that was a
// container holding the "All workers" filter, so the sender's name was "found" in a dropdown and U's who-reading proved
// nothing. The card is now the nearest record-shaped ancestor of the marker (an entry card, a list item, a row, an
// article), never a block that merely contains it.
async function findText(s, marker, ms = 15000) {
  for (let t = 0; t < ms; t += 500) {
    const hit = await s.page.evaluate((mk) => {
      let best = null;
      for (const el of document.querySelectorAll('body *')) {
        if (!el.checkVisibility || !el.checkVisibility()) continue;
        const tx = (el.innerText || '').trim();
        if (tx.includes(mk) && (!best || tx.length < best.t.length)) best = { el, t: tx };
      }
      if (!best) return null;
      // climb until the node is one of a REPEATED set of siblings (a list's item: same tag and class beside it) - that is
      // the record; stop before a block grows past a card's size
      // a record that names itself (the logbook's cards carry data-entry-id) is the card; otherwise the sibling climb
      // (a change order's card and a scope item's row name themselves too - 2026-11-06, J8: the climb stopped at the
      // card's title row and read a CO as having no author while its card said "Raised by ... · date")
      const named = best.el.closest('[data-entry-id], [data-alert-id], [data-node-id], [data-record-id], [data-co-id], [data-item-id], [data-link-id]');
      if (named && (named.innerText || '').trim().length < 1500) return { text: best.t, card: (named.innerText || '').trim() };
      // a record opened in its own view (a dialog) IS that view - its author and date sit beside the marker, not in it
      const dlg = best.el.closest('[role="dialog"], [aria-modal="true"]');
      if (dlg && (dlg.innerText || '').trim().length < 2500) return { text: best.t, card: (dlg.innerText || '').trim() };
      let node = best.el;
      for (let i = 0; i < 10 && node.parentElement; i++) {
        const par = node.parentElement;
        const twins = [...par.children].filter((c) => c.tagName === node.tagName && c.className === node.className).length;
        // a repeated ROW has children of its own; two lines of text with the same class inside one row are not records
        if (twins >= 2 && node.children.length >= 2) break;
        const pl = (par.innerText || '').trim().length;
        // a lone record (one search result) has no twins: stop before the climb jumps to a much larger block
        if (pl > 1200 || pl > Math.max(400, 2.5 * (node.innerText || '').trim().length)) break;
        node = par;
      }
      return { text: best.t, card: (node.innerText || '').trim().slice(0, 1200) };
    }, marker).catch(() => null);
    if (hit) return hit;
    await sleep(500);
  }
  return null;
}
// the receiver's route, re-walked under 3G: `reach(s)` is the same route the U reading took (a page, or a page and the
// controls a person taps to bring the record up), so the A row asks exactly what U asked, on a bad network
async function under3G(s, reach) {
  const cdp = await s.ctx.newCDPSession(s.page);
  await cdp.send('Network.enable');
  await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 400, downloadThroughput: 50 * 1024, uploadThroughput: 50 * 1024 });
  const t0 = Date.now();
  try {
    // ★THE A PILLAR ASKS WHETHER THE HAND-OFF SURVIVES A BAD NETWORK, NOT WHETHER IT IS FAST (2026-11-04, J3 hand-off 4):
    // analytics.html reached DOMContentLoaded in ~60 s on slow 3G at 390 and the walk's one-minute navigation limit read
    // that as a failure. Navigation gets 150 s under 3G; the time is kept, and over a minute it is said as SLOW - a
    // reading for the performance lens, never hidden inside a pass.
    s.gotoTimeout = 150000;
    const hit = await reach(s);
    const ms = Date.now() - t0;
    return { ok: !!hit, ms, slow: ms > 60000,
      detail: hit ? `the record is on the receiver's screen on 3G${ms > 60000 ? ` - SLOW: ${Math.round(ms / 1000)} s` : ''}` : 'not on screen within 45 s on 3G' };
  } catch (e) {
    return { ok: false, ms: Date.now() - t0, detail: String(e.message || e).slice(0, 160) };
  } finally {
    s.gotoTimeout = 0;
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 }).catch(() => {});
  }
}
// open the logbook card carrying `marker` and its "Edit Entry", the controls a person taps
async function openEdit(s, marker) {
  await go(s, 'logbook.html');
  const openCard = () => s.page.evaluate((t) => {
    const card = [...document.querySelectorAll('#entries-list .entry-card, #entries-list [onclick*="openModal"], .entry-card')]
      .find((c) => (c.textContent || '').includes(t));
    if (!card) return false; (card.querySelector('[onclick*="openModal"]') || card).click(); return true;
  }, marker);
  let opened = await openCard();
  // a supervisor's logbook opens on the query-first Team Feed: a teammate's entry is reached by Search Team
  if (!opened) { await reachTeam(s, marker, 15000); opened = await openCard(); }
  await sleep(900);
  const edited = await s.page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => /edit entry/i.test(x.textContent) && /openEditModal/.test(x.getAttribute('onclick') || ''));
    if (b) { b.click(); return true; } return false;
  });
  await sleep(900);
  return opened && edited;
}

// A supervisor's logbook opens on the TEAM feed, which is query-first by design: a teammate's new entry raises the live
// "N new team entries" badge and is never prepended under the reader (logbook.html subscribeLogbookRealtime). So the
// route to a teammate's record is: the logbook, Team Feed, Search Team (or the badge, which runs the same search).
async function reachTeam(R, marker, ms) {
  await go(R, 'logbook.html');
  await R.page.evaluate(() => { const t = document.getElementById('btn-view-team'); if (t && t.getAttribute('aria-pressed') !== 'true') t.click(); });
  await sleep(800);
  await R.page.evaluate(() => { const b = document.getElementById('btn-search-team'); if (b) b.click(); });
  return findText(R, marker, ms);
}
// ★A HAND-OFF THAT MUST NOT ARRIVE (2026-11-05, GJ M8 G-ADV): a member of another hive holding a record's link must be
// REFUSED IN WORDS - the record never drawn, and a sentence that says why. Read from the first moment after the link
// lands (a refusal is often a toast, read as it appears), then once more after it settles: the record must not be drawn
// late either. `r.refused` is the sentence's shape; `r.marker` is the record's own text, which must never appear.
async function readRefusal(R, r, ms = 20000) {
  await R.page.goto(`${ORIGIN}/${r.path}`, { waitUntil: 'domcontentloaded', timeout: R.gotoTimeout || 60000 });
  let said = null, leaked = false;
  for (let t = 0; t < ms && !said; t += 250) {
    const txt = await R.page.evaluate(() => document.body.innerText || '').catch(() => '');
    said = txt.split('\n').map((l) => l.trim()).find((l) => l.length < 400 && r.refused.test(l)) || null;
    if (r.marker && txt.includes(r.marker)) leaked = true;
    if (!said) await sleep(250);
  }
  await sleep(2500);
  const after = await R.page.evaluate(() => document.body.innerText || '').catch(() => '');
  if (r.marker && after.includes(r.marker)) leaked = true;
  return { ok: !!said && !leaked, refused: true, said, leaked,
    ...(said ? {} : { why: 'no sentence said why the record was not shown' }), ...(leaked ? { why: 'the record was drawn for a reader outside its hive' } : {}) };
}
// ★A NAME THAT MUST NO LONGER BE LISTED (2026-11-05, GJ M8 G-LEAVE hand-off 4): the roster the remaining worker reads
// must list the hive (`presentRx` - it loaded) and must not list the removed member (`nameRx`).
async function readAbsence(R, r) {
  await go(R, r.path);
  if (r.prepare) await r.prepare(R);
  const got = await R.page.evaluate((sel) => { const el = document.querySelector(sel); return el && el.checkVisibility && el.checkVisibility() ? (el.innerText || '').trim() : null; }, r.absent.container).catch(() => null);
  const present = !!got && r.absent.presentRx.test(got);
  const gone = !!got && !r.absent.nameRx.test(got);
  return { ok: present && gone, said: got ? got.replace(/\s+/g, ' ').slice(0, 300) : null, present, gone,
    ...(got ? {} : { why: 'the roster was not on screen' }), ...(got && !gone ? { why: 'the roster still lists the removed member' } : {}) };
}
// the receiver's report, asked of the same engine the page asks (analytics-orchestrator, phase report, the page's 90
// days), with the walk's no-model flag: the figures BEFORE the sender acts, so the page's figure after is judged against
// them (J4: the worker's breakdown is one more failure; J24: their safety-risk job is one more safety-risk failure)
async function reportFigures(S, period = 90) {
  const r = await fetch(`${SB}/functions/v1/analytics-orchestrator`, { method: 'POST',
    headers: { apikey: KEY, Authorization: `Bearer ${S.token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ phase: 'report', hive_id: S.m.seatId || HIVE_ID, worker_name: S.m.name, period_days: period, debug_fault_inject: true }) });
  if (!r.ok) return { error: `HTTP ${r.status} ${(await r.text()).slice(0, 120)}` };
  const d = await r.json();
  const pick = (k) => (d && d[k] && typeof d[k] === 'object') ? d[k] : {};
  const ff = (pick('descriptive').failure_frequency || {}).failure_frequency || [];
  const dist = (pick('diagnostic').rcm_consequence || {}).distribution || [];
  return { failures: ff.reduce((a, x) => a + (Number(x.failure_count) || 0), 0),
    safety: Number((dist.find((x) => (x.consequence || x.label) === 'Safety risk') || {}).count || 0),
    plan: d.action_plan || null };
}

// the live badge on an open logbook: its words, or null when nothing arrived within `ms`
async function liveBadge(s, ms = 15000) {
  for (let t = 0; t < ms; t += 500) {
    const txt = await s.page.evaluate(() => {
      const b = document.getElementById('logbook-live-badge');
      return b && !b.classList.contains('hidden') && b.checkVisibility && b.checkVisibility() ? (b.innerText || '').trim() : null;
    }).catch(() => null);
    if (txt) return txt;
    await sleep(500);
  }
  return null;
}

// ── the recipes: per scenario, per hand-off. Each returns { act, land, marker, rec:{table,id}, F(), extra } ───────────
const RECIPES = {
  J2: {
    1: async (X) => {   // the worker's breakdown entry reaches the supervisor's logbook as it lands (logbook-feed)
      const { w, s } = X.S;
      await go(s, 'logbook.html');                              // the supervisor is already looking
      await go(w, 'logbook.html');
      const r = await logWizard(w.page, H(w.page), { tag: X.tag, maintType: 'Breakdown / Corrective', status: 'Open', problem: 'bearing noise drive end' });
      const [id, machine, node] = psql(`select id, machine, asset_node_id from logbook where problem like '${q(X.tag)}%' and hive_id = '${HIVE_ID}' order by created_at limit 1`).split('|');
      X.rec.entry = { id, machine, node };
      // no reload: did the feed tell the supervisor? The badge is the page's live signal; tapping it runs the team search
      const badge = await liveBadge(s, 15000);
      let seen = null;
      if (badge) {
        await s.page.evaluate(() => { const b = document.getElementById('logbook-live-badge'); if (b) b.click(); });
        seen = await findText(s, X.tag, 15000);
      }
      return { act: { ok: !!id, detail: `logbook wizard as ${w.m.name}: ${r.toast || 'no toast'}${id ? ` -> entry ${id} on ${machine}` : ' -> NO ROW'}` },
        marker: X.tag, path: 'logbook.html', live: !!badge, liveSaid: badge, preRead: seen,
        reach: (R2, ms) => reachTeam(R2, X.tag, ms), rec: { table: 'logbook', id } };
    },
    2: async (X) => {   // the supervisor assigns the work order; the worker is pushed and lands on the open list
      const { w, s } = X.S;
      const e = X.rec.entry;
      // a supervisor cannot edit a teammate's entry (logbook's UPDATE is the author's); the entry's view offers the
      // supervisor "Move the work order" (set_logbook_wo, mig 20261104000001) - the control this hop exists to prove
      let ok = false, toast = '';
      if (!X.faults.has('push-never-fires')) {
        await reachTeam(s, X.tag, 15000);
        ok = await s.page.evaluate((t) => {
          const card = [...document.querySelectorAll('#entries-list .entry-card, #entries-list [onclick*="openModal"], .entry-card')]
            .find((c) => (c.textContent || '').includes(t));
          if (!card) return false; (card.querySelector('[onclick*="openModal"]') || card).click(); return true;
        }, X.tag);
        await sleep(900);
        const moved = await s.page.evaluate(() => { const b = document.querySelector('#wo-actions button'); if (b) { b.click(); return true; } return false; });
        await sleep(1500);
        await s.page.selectOption('#wo-move-state', 'assigned').catch(() => {});
        await s.page.selectOption('#wo-move-who', w.m.name).catch(() => {});
        await s.page.click('#wo-actions .btn-primary', { timeout: 5000 }).catch(() => {});
        await sleep(2500);
        toast = await s.page.evaluate(() => { const t = document.getElementById('toast-text'); return t ? t.textContent.trim() : ''; }).catch(() => '');
        ok = ok && moved;
      }
      const got = psql(`select coalesce(wo_assigned_to,'') || '|' || coalesce(wo_state,'') from logbook where id = '${q(e.id)}'`);
      const push = psql(`select count(*) from service_outbox where consumer = 'notify-push' and created_at >= '${X.t0}'
        and payload->'auth_uids' ? '${w.m.uid}' and payload->>'title' = 'Work order assigned to you' and payload->>'url' like '/logbook.html?status=Open%'`);
      const pushSaid = psql(`select coalesce(payload->>'title','') || ': ' || coalesce(payload->>'body','') from service_outbox
        where consumer = 'notify-push' and created_at >= '${X.t0}' and payload->'auth_uids' ? '${w.m.uid}' order by created_at desc limit 1`);
      return { act: { ok: ok && got.startsWith(w.m.name), detail: `"Move the work order" on the entry's view as ${s.m.name} (toast: ${toast || 'none'}): wo_assigned_to|wo_state = ${got}` },
        marker: X.tag, path: 'logbook.html?status=Open', channelSaid: pushSaid || null, rec: { table: 'logbook', id: e.id },
        F: () => ({ ok: Number(push) >= 1 && got.startsWith(w.m.name),
          detail: `service_outbox notify-push to ${w.m.name} with /logbook.html?status=Open: ${push}; the entry reads assigned to ${got.split('|')[0] || 'nobody'}` }) };
    },
    3: async (X) => {   // the worker's closed repair is in the machine's history
      const { w } = X.S;
      const e = X.rec.entry;
      const ok = await openEdit(w, X.tag);
      await w.page.evaluate(() => { const r = document.getElementById('st-closed'); if (r) { r.checked = true; r.click(); r.dispatchEvent(new Event('change', { bubbles: true })); } });
      await w.page.evaluate(() => { const b = document.getElementById('extras-toggle-btn'); if (b) b.click(); });
      await sleep(300);
      await w.page.evaluate(() => { const el = document.getElementById('f-downtime'); if (el) { el.value = '2.5'; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); } });
      await w.page.evaluate(() => { const b = document.getElementById('save-entry-btn'); if (b) b.click(); });
      await sleep(3500);
      const st = psql(`select status || '|' || coalesce(downtime_hours::text,'') from logbook where id = '${q(e.id)}'`);
      return { act: { ok: ok && /^closed/i.test(st), detail: `closed through the entry's own edit modal as ${w.m.name}: status|downtime = ${st}` },
        marker: X.tag, path: e.node ? `asset-hub.html?node_id=${e.node}` : 'asset-hub.html',
        rec: { table: 'v_logbook_truth', id: e.id, where: `and status = 'Closed'` } };
    },
    4: async (X) => {   // the repair counts in the supervisor's downtime and repair time - after the page's own Refresh
      const { s } = X.S;
      await go(s, 'analytics.html');
      const before = psql(`select coalesce(max(computed_at)::text,'') from analytics_snapshots where hive_id = '${HIVE_ID}'`);
      const tapped = await s.page.evaluate(() => {
        const b = [...document.querySelectorAll('button')].find((x) => /refresh|recompute/i.test((x.innerText || '') + ' ' + (x.getAttribute('aria-label') || '')));
        if (b) { b.click(); return (b.innerText || b.getAttribute('aria-label') || '').trim(); } return null;
      });
      let after = before;
      for (let t = 0; t < 90000 && after === before; t += 3000) {
        await sleep(3000);
        after = psql(`select coalesce(max(computed_at)::text,'') from analytics_snapshots where hive_id = '${HIVE_ID}'`);
      }
      return { act: { ok: !!tapped && after !== before, detail: `the page's own "${tapped || 'no Refresh control'}" as ${s.m.name}: snapshot ${before || 'none'} -> ${after || 'none'}` },
        marker: null, path: 'analytics.html', freshnessRx: /recomputed|just now|updated|minute|today/i,
        rec: { table: 'analytics_snapshots', idCol: 'hive_id', id: HIVE_ID, where: `and computed_at >= '${X.t0}'` } };
    },
    5: async (X) => {   // a repeat of the same breakdown raises the failure-signature alert the supervisor reads
      const { w, s } = X.S;
      // ★ON A MACHINE WITH NO STANDING ALERT (2026-11-04, the third J2 walk): the hop-1 machine already carried a
      // repeat-failure alert from the seed, and the scan keeps a standing alert's first-detected date by design - so the
      // walk re-confirmed an October alert instead of raising one, and the hop's premise was never exercised. The machine
      // is the home hive's first asset with no signature alert of any rule (read from the database, never typed).
      const quiet = psql(`select a.id || '|' || a.tag from asset_nodes a where a.hive_id = '${HIVE_ID}' and a.deleted_at is null
        and a.tag is not null and not exists (select 1 from failure_signature_alerts f where f.hive_id = a.hive_id and f.machine = a.tag)
        order by a.tag limit 1`);
      const [qnode, qmachine] = quiet ? quiet.split('|') : [null, null];
      const e = { machine: qmachine, node: qnode };
      if (!qmachine) X.notes.push('hand-off 5: the hive has no asset without a standing signature alert');
      // the worker logs the same breakdown three times, through the API the logbook writes to
      for (let i = 1; i <= 3; i++) {
        const r = await fetch(`${SB}/rest/v1/logbook`, { method: 'POST', headers: { apikey: KEY, Authorization: `Bearer ${w.token}`,
          'Content-Type': 'application/json', Prefer: 'return=minimal' },
          body: JSON.stringify({ id: `${X.tag}-r${i}`, worker_name: w.m.name, auth_uid: w.m.uid, hive_id: HIVE_ID, machine: e.machine,
            asset_node_id: e.node || null, maintenance_type: 'Breakdown / Corrective', category: 'Mechanical', root_cause: 'Wear',
            problem: `${X.tag} repeat ${i}: bearing noise drive end`, status: 'Closed', date: new Date().toISOString() }) });
        if (!r.ok) X.notes.push(`repeat entry ${i}: HTTP ${r.status} ${(await r.text()).slice(0, 120)}`);
      }
      // the scan the daily cron runs, triggered the way the function lets a hive member trigger it for their own hive
      const scan = await fetch(`${SB}/functions/v1/failure-signature-scan`, { method: 'POST',
        headers: { apikey: KEY, Authorization: `Bearer ${s.token}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ hive_id: HIVE_ID }) });
      const body = (await scan.text()).slice(0, 160);
      const alert = psql(`select id || '|' || alert_title from failure_signature_alerts where hive_id = '${HIVE_ID}' and machine = '${q(e.machine)}'
        and rule_id = 'repeat_failure' and status in ('active','acknowledged') order by detected_at desc limit 1`);
      const [aid, title] = alert ? alert.split('|') : [null, null];
      return { act: { ok: !!aid, detail: `3 Wear breakdowns on ${e.machine} (no standing alert before) as ${w.m.name}; failure-signature-scan as ${s.m.name}: HTTP ${scan.status} ${body}` },
        // the feed lists 30, critical before high: a new "high" pattern sits under older criticals, so the route is the
        // page's own Patterns filter (#filters .chip[data-kind=pattern]), the view a supervisor checking patterns takes
        reach: async (R2, ms) => {
          await go(R2, 'alert-hub.html');
          await R2.page.click('#filters .chip[data-kind="pattern"]', { timeout: 8000 }).catch(() => {});
          await sleep(1200);
          // ...and a "high" pattern can still sit under 30 older criticals: the page's own Load more, as a person pages
          for (let i = 0; i < 5; i++) {
            const hit = await findText(R2, title || e.machine, i === 0 ? Math.min(ms, 8000) : 4000);
            if (hit) { X.notes.push(`hand-off 5: the new alert was reached after ${i} "Load more" tap(s) under the Patterns filter`); return hit; }
            const more = await R2.page.evaluate(() => { const b = document.querySelector('#alert-load-more-wrap:not(.hidden) button'); if (b) { b.click(); return true; } return false; });
            if (!more) break;
            await sleep(1200);
          }
          return null;
        },
        // a system-raised hand-off: the alert names no person (the daily scan raised it) - its "who" is where it came
        // from, the repeats it counts; the marker is the alert's own title, so a second rule's alert on the same machine
        // ("Increasing failure rate") is never read in its place
        marker: title || e.machine, whoRx: /\d+\s*×|repeat/i, markerRx: /repeat/i, hint: 'repeat|signature|failure|' + e.machine, path: 'alert-hub.html', rec: { table: 'v_alert_truth', idCol: 'alert_id', id: aid }, alertTitle: title };
    },
  },
};

// ── J3 · the PM month: the supervisor schedules it, it falls due in the worker's day, the worker completes it, the
// supervisor's compliance and the month's report count it. The asset is the walk's own (tagged), anchored 31 days back
// so its tasks are due today.
// pm-scheduler's way to one machine among a plant's hundreds is its own search box (#pm-search, "Find a machine by name,
// tag or location") - the dashboard does not draw every asset by name
async function findPmAsset(s, name, ms, path = 'pm-scheduler.html') {
  await go(s, path);
  await s.page.fill('#pm-search', name).catch(() => {});
  await sleep(1500);
  return findText(s, name, ms);
}
async function openPmAsset(s, name) {
  await findPmAsset(s, name, 8000);
  return s.page.evaluate((nm) => {
    const el = [...document.querySelectorAll('[onclick], button, a, .asset-card, li')].find((c) => (c.innerText || '').includes(nm)
      && (c.getAttribute('onclick') || c.tagName === 'BUTTON' || c.tagName === 'A'));
    if (!el) return false; el.click(); return true;
  }, name);
}
RECIPES.J3 = {
  1: async (X) => {   // the PM the supervisor scheduled is on the worker's list
    const { s } = X.S;
    const name = X.pmName || `${X.tag} pump`;
    await go(s, 'pm-scheduler.html');
    await s.page.evaluate(() => { const b = document.getElementById('tab-add'); if (b) b.click(); });
    await sleep(1500);
    await s.page.fill('#w-name', name).catch(() => {});
    await s.page.fill('#w-tag', X.tag.slice(-10)).catch(() => {});
    await s.page.fill('#w-location', 'Line 1').catch(() => {});
    const cat = await s.page.evaluate(() => {
      const sel = document.getElementById('w-category'); if (!sel) return null;
      const opt = [...sel.options].find((o) => o.value); if (!opt) return null;
      sel.value = opt.value; sel.dispatchEvent(new Event('change', { bubbles: true })); return opt.value;
    });
    await sleep(1500);
    for (const st of [2, 3]) { await s.page.evaluate((n) => { if (typeof goStep === 'function') goStep(n); }, st); await sleep(900); }
    // ★400 DAYS BACK, NOT 31 (2026-11-04, the first J3 walk): the day planner's rail is "the 30 most urgent of N", most
    // overdue first, and Manila's older overdue PMs outranked a machine anchored a month back - the walk's PM never reached
    // the worker's day, a premise the data did not exercise. A machine onboarded with its last service over a year ago
    // is a real case, and it is the most urgent on the rail.
    const anchor = new Date(Date.now() + 8 * 3600e3 - 400 * 86400e3).toISOString().slice(0, 10);
    await s.page.evaluate((d) => { const a = document.getElementById('w-anchor'); if (a) { a.value = d; a.dispatchEvent(new Event('change', { bubbles: true })); } }, anchor);
    await s.page.evaluate(() => { if (typeof goStep === 'function') goStep(4); });
    await sleep(900);
    await s.page.evaluate(() => { const b = document.getElementById('btn-save-asset'); if (b) b.click(); });
    await sleep(4000);
    const row = psql(`select a.id || '|' || (select count(*) from pm_scope_items p where p.asset_id = a.id) from pm_assets a
      where a.hive_id = '${X.pmHive || HIVE_ID}' and a.asset_name = '${q(name)}' and a.deleted_at is null limit 1`);
    const [aid, ntasks] = row ? row.split('|') : [null, '0'];
    X.rec.pm = { id: aid, name };
    return { act: { ok: !!aid && Number(ntasks) > 0, detail: `the Add Asset wizard as ${s.m.name}: category ${cat || 'none'}, anchor ${anchor} -> pm_assets ${aid || 'NO ROW'} with ${ntasks} task(s)` },
      marker: name, path: 'pm-scheduler.html', reach: (R2, ms) => findPmAsset(R2, name, ms), rec: { table: 'pm_assets', id: aid } };
  },
  2: async (X) => {   // the PM falls due in the worker's day
    const p = X.rec.pm || {};
    return { act: { ok: !!p.id, detail: `the PM scheduled at hand-off 1 (${p.name}), anchored 400 days back - overdue, the most urgent` },
      // a due PM is the schedule's doing, not a person's: the day names the asset and that it is a PM due
      marker: p.name, whoRx: /\bPM\b|preventive|due|overdue/i, path: 'dayplanner.html',
      // the rail of due PMs sits behind "Open items" (#sidebar-toggle, collapsed by default) - the tap a person makes
      reach: async (R2, ms) => {
        await go(R2, 'dayplanner.html');
        await R2.page.evaluate(() => { const t = document.getElementById('sidebar-toggle'); if (t && t.getAttribute('aria-expanded') !== 'true') t.click(); });
        await sleep(1200);
        return findText(R2, p.name, ms);
      },
      rec: { table: 'v_pm_scope_items_truth', idCol: 'asset_id', id: p.id } };
  },
  3: async (X) => {   // the worker's completion moves the supervisor's PM compliance
    const { w } = X.S;
    const p = X.rec.pm || {};
    const opened = await openPmAsset(w, p.name);
    await sleep(1500);
    const marked = await w.page.evaluate(() => { const b = document.querySelector('[onclick^="markDone"]'); if (b) { b.click(); return true; } return false; });
    await sleep(1000);
    const findings = `${X.tag} bearings checked`;
    await w.page.fill('#sheet-findings', findings).catch(() => {});
    await w.page.evaluate(() => { const b = document.getElementById('sheet-save-btn'); if (b) b.click(); });
    await sleep(3500);
    const comp = psql(`select c.id || '|' || coalesce(c.worker_name,'') from pm_completions c where c.asset_id = '${q(p.id || '00000000-0000-0000-0000-000000000000')}'
      order by c.completed_at desc limit 1`);
    const [cid, by] = comp ? comp.split('|') : [null, null];
    X.rec.pmComp = cid;
    return { act: { ok: opened && marked && !!cid, detail: `the asset's own "done" sheet as ${w.m.name}: pm_completions ${cid || 'NO ROW'} by ${by || 'nobody'}` },
      // the supervisor opens the asset and reads its completion: the worker's findings, who, when
      marker: findings, path: 'pm-scheduler.html',
      reach: async (R2, ms) => { await openPmAsset(R2, p.name); await sleep(1800); return findText(R2, findings, ms); },
      rec: { table: 'pm_completions', id: cid } };
  },
  4: (X) => RECIPES.J2[4](X),   // the completion counts in the supervisor's compliance figures (the page's own Refresh)
  5: async (X) => {   // the completion is in the month's report
    const { s } = X.S;
    await go(s, 'analytics-report.html');
    return { act: { ok: true, detail: `the month's report opened as ${s.m.name} after hand-off 4's recompute` },
      marker: null, path: 'analytics-report.html', freshnessRx: /Generated:|Period:|Report Date:/,
      // the report is built on the person's own tap: "Generate Report" (#generate-btn), then its header states the date
      prepare: async (P) => {
        await P.page.click('#generate-btn', { timeout: 10000 }).catch(() => P.page.evaluate(() => { const b = document.getElementById('generate-btn'); if (b) b.click(); }));
        for (let t = 0; t < 60000; t += 1000) {
          const ok = await P.page.evaluate(() => /Generated:/.test(document.body.innerText || '')).catch(() => false);
          if (ok) return; await sleep(1000);
        }
      },
      rec: { table: 'analytics_snapshots', idCol: 'hive_id', id: HIVE_ID, where: `and computed_at >= '${X.t0}'` } };
  },
};

// ── J9 · the supervisor's week: a job raised and handed to the worker, the shift plan published, a worker's post in the
// supervisor's view, a machine the worker submitted waiting for approval, and the decision pushed back.
RECIPES.J9 = {
  1: async (X) => {   // the work order the supervisor assigned is in the worker's day
    const { w, s } = X.S;
    await go(s, 'logbook.html');
    const r = await logWizard(s.page, H(s.page), { tag: X.tag, maintType: 'Breakdown / Corrective', status: 'Open', problem: 'conveyor belt tracking off' });
    const id = psql(`select id from logbook where problem like '${q(X.tag)}%' and hive_id = '${HIVE_ID}' order by created_at limit 1`);
    // the author raises it and hands it on through the entry's own work-order fields (an author may; the guard checks the role)
    const opened = await openEdit(s, X.tag);
    await s.page.evaluate(() => { const st = document.getElementById('f-wo-state'); if (st) { st.value = 'assigned'; st.dispatchEvent(new Event('change', { bubbles: true })); } });
    await sleep(500);
    await s.page.evaluate((n) => {
      const wrap = document.getElementById('wo-assigned-wrap'); if (wrap) wrap.style.display = '';
      const f = document.getElementById('f-wo-assigned-to'); if (f) { f.value = n; f.dispatchEvent(new Event('input', { bubbles: true })); f.dispatchEvent(new Event('change', { bubbles: true })); }
    }, w.m.name);
    await s.page.evaluate(() => { const b = document.getElementById('save-entry-btn'); if (b) b.click(); });
    await sleep(3500);
    const got = psql(`select coalesce(wo_assigned_to,'') || '|' || coalesce(wo_state,'') from logbook where id = '${q(id || '')}'`);
    X.rec.job = { id };
    return { act: { ok: !!id && opened && got.startsWith(w.m.name), detail: `raised by ${s.m.name} through the wizard (${r.toast || 'no toast'}) and handed on in its own edit: wo_assigned_to|wo_state = ${got}` },
      marker: X.tag, path: 'dayplanner.html',
      reach: async (R2, ms) => {
        await go(R2, 'dayplanner.html');
        await R2.page.evaluate(() => { const t = document.getElementById('sidebar-toggle'); if (t && t.getAttribute('aria-expanded') !== 'true') t.click(); });
        await sleep(1200);
        return findText(R2, X.tag, ms);
      },
      rec: { table: 'v_logbook_truth', id } };
  },
  2: async (X) => {   // the shift plan the supervisor published is the worker's briefing
    const { s } = X.S;
    // SETUP: the shift's plan starts unpublished, so the publish is the walk's own act (Baguio's night plan was already
    // published when J29 first walked, and there was nothing left to publish). The snapshot taken before the walk puts
    // every plan back exactly as it was.
    // (shift_plans_forward_only_status refuses published -> draft for every writer, rightly; a fixture set up for the
    // walk and restored after it is not a writer's act, so it runs with triggers off, like the restore)
    const reset = psql(`set session_replication_role = replica;
      with u as (update shift_plans set status = 'draft', published_at = null, published_by = null
      where hive_id = '${HIVE_ID}' and status = 'published' and shift_date >= current_date - 1 returning 1) select count(*) from u`).split('\n').pop();
    if (Number(reset)) X.notes.push(`hand-off 2 setup: ${reset} already-published plan(s) set back to draft for the walk (restored after)`);
    await go(s, 'shift-brain.html');
    for (let t = 0; t < 40000; t += 1000) {   // the plan is built on the shift's first open; Publish needs it loaded
      const ready = await s.page.evaluate(() => /handover ready|published|shift plan/i.test(document.body.innerText || '')).catch(() => false);
      if (ready) break; await sleep(1000);
    }
    await s.page.evaluate(() => { const b = document.getElementById('publish-btn'); if (b) b.click(); });
    await sleep(800);
    await s.page.click('[data-wh-modal-ok]', { timeout: 6000 }).catch(() => {});
    await sleep(3000);
    const plan = psql(`select id || '|' || coalesce(published_by,'') from shift_plans where hive_id = '${HIVE_ID}' and status = 'published'
      and published_at >= '${X.t0}' order by published_at desc limit 1`);
    const [pid, by] = plan ? plan.split('|') : [null, null];
    return { act: { ok: !!pid && by === s.m.name, detail: `"Publish to crew" as ${s.m.name}, confirmed: shift_plans ${pid || 'NONE'} published by ${by || 'nobody'}` },
      // ★THE PILL'S OWN WORDS, NOT THE NAME ALONE (2026-11-05, G-SHIFT hand-off 2): the reader takes the smallest element
      // carrying the marker, and in Manila the carry-over rows read "opened ... by <the supervisor>" for the supervisor's
      // own open jobs - the name alone landed on a carried job, and the publish was never read
      marker: `Published by ${s.m.name}`, markerRx: /publish/i, path: 'shift-brain.html', rec: { table: 'shift_plans', id: pid } };
  },
  3: async (X) => {   // the worker's post is in the supervisor's moderation view
    const { w } = X.S;
    await go(w, 'community.html');
    await w.page.evaluate(() => { if (typeof openComposer === 'function') openComposer(); });
    await sleep(1000);
    const text = `${X.tag} spare V-belts for line 2 are back in stock`;
    await w.page.fill('#post-content', text).catch(() => {});
    await w.page.evaluate(() => { const b = document.getElementById('btn-submit-post'); if (b) b.click(); });
    await sleep(3500);
    const pid = psql(`select id from community_posts where hive_id = '${HIVE_ID}' and content like '${q(X.tag)}%' order by created_at desc limit 1`);
    return { act: { ok: !!pid, detail: `"Post to Hive" as ${w.m.name}: community_posts ${pid || 'NO ROW'}` },
      marker: X.tag, path: 'community.html', rec: { table: 'community_posts', id: pid } };
  },
  4: async (X) => {   // the machine the worker submitted waits in the supervisor's approvals
    const { w } = X.S;
    await go(w, 'logbook.html');
    await w.page.evaluate(() => { if (typeof openAssetModal === 'function') openAssetModal(); });
    await sleep(1200);
    const name = `${X.tag} motor`;
    await w.page.fill('#a-asset-id', X.tag).catch(() => {});
    await w.page.fill('#a-name', name).catch(() => {});
    await w.page.evaluate(() => { const t = document.getElementById('a-type'); if (t) { const o = [...t.options].find((x) => x.value); if (o) { t.value = o.value; t.dispatchEvent(new Event('change', { bubbles: true })); } } });
    await w.page.fill('#a-location', 'Line 2').catch(() => {});
    await w.page.evaluate(() => { const b = document.getElementById('asset-submit-btn'); if (b) b.click(); });
    await sleep(3500);
    const node = psql(`select id || '|' || status || '|' || coalesce(submitted_by,'') from asset_nodes where hive_id = '${HIVE_ID}' and name = '${q(name)}' limit 1`);
    const [nid, st, by] = node ? node.split('|') : [null, null, null];
    X.rec.node = { id: nid, name };
    return { act: { ok: !!nid && st === 'pending', detail: `the logbook's add-asset form as ${w.m.name}: asset_nodes ${nid || 'NO ROW'} ${st || ''} submitted by ${by || 'nobody'}` },
      marker: name, path: 'hive.html', rec: { table: 'asset_nodes', id: nid } };
  },
  5: async (X) => {   // the supervisor's decision is pushed to the worker
    const { w, s } = X.S;
    const n = X.rec.node || {};
    await go(s, 'hive.html');
    const tapped = await s.page.evaluate((id) => {
      const b = [...document.querySelectorAll('#approval-queue button[onclick^="approveItem"]')].find((x) => (x.getAttribute('onclick') || '').includes(id));
      if (b) { b.click(); return true; } return false;
    }, n.id || '---');
    await sleep(800);
    await s.page.click('[data-wh-modal-ok]', { timeout: 4000 }).catch(() => {});
    await sleep(3000);
    const st = psql(`select status from asset_nodes where id::text = '${q(n.id || '')}'`);
    const pushSaid = psql(`select coalesce(payload->>'title','') || ': ' || coalesce(payload->>'body','') || ' -> ' || coalesce(payload->>'url','') from service_outbox
      where consumer = 'notify-push' and created_at >= '${X.t0}' and payload->'auth_uids' ? '${w.m.uid}' and payload->>'title' like 'Submission%'
      order by created_at desc limit 1`);
    const url = (pushSaid.split(' -> ')[1] || '').replace(/^\//, '');
    return { act: { ok: tapped && st === 'approved', detail: `Approve on hive.html's approval queue as ${s.m.name}: asset_nodes status ${st || 'unknown'}` },
      marker: n.name, channelSaid: pushSaid.split(' -> ')[0] || null, path: url || 'logbook.html',
      rec: { table: 'asset_nodes', id: n.id, where: `and status = 'approved'` },
      F: () => ({ ok: !!pushSaid && st === 'approved', detail: `the push to ${w.m.name}: ${pushSaid || 'NONE'}; the machine reads ${st}` }) };
  },
};

// ── J22 · one machine's whole life: the supervisor commissions it (the logbook's asset form, then the hive's approval
// queue - the product's own two steps), the worker works on it, the supervisor sets its PM plan, its repairs count, and
// the trail names who did what.
async function fileMachine(s, tag, name) {   // the logbook's add-asset form; a hive machine starts pending
  await go(s, 'logbook.html');
  await s.page.evaluate(() => { if (typeof openAssetModal === 'function') openAssetModal(); });
  await sleep(1200);
  await s.page.fill('#a-asset-id', tag).catch(() => {});
  await s.page.fill('#a-name', name).catch(() => {});
  await s.page.evaluate(() => { const t = document.getElementById('a-type'); if (t) { const o = [...t.options].find((x) => x.value); if (o) { t.value = o.value; t.dispatchEvent(new Event('change', { bubbles: true })); } } });
  await s.page.fill('#a-location', 'Line 3').catch(() => {});
  await s.page.evaluate(() => { const b = document.getElementById('asset-submit-btn'); if (b) b.click(); });
  await sleep(3500);
  const node = psql(`select id || '|' || status from asset_nodes where hive_id = '${HIVE_ID}' and name = '${q(name)}' limit 1`);
  return node ? { id: node.split('|')[0], status: node.split('|')[1] } : { id: null, status: null };
}
async function approveInQueue(s, nodeId) {   // hive.html's approval queue, as a supervisor taps it
  await go(s, 'hive.html');
  const tapped = await s.page.evaluate((id) => {
    const b = [...document.querySelectorAll('#approval-queue button[onclick^="approveItem"]')].find((x) => (x.getAttribute('onclick') || '').includes(id));
    if (b) { b.click(); return true; } return false;
  }, nodeId || '---');
  await sleep(800);
  await s.page.click('[data-wh-modal-ok]', { timeout: 4000 }).catch(() => {});
  await sleep(3000);
  return tapped;
}
// the picker is searched by what a person would type: the machine's name (G-SENSOR's real machine), or the walk's tag
// when the walk made the machine and named it with the tag (J22)
async function logOnMachine(p, tag, nodeId, problem, search = tag) {   // the logbook wizard, the machine chosen through the picker's search
  await go(p, 'logbook.html');
  await p.page.click('#asset-picker-btn', { timeout: 6000 }).catch(() => {});
  await sleep(800);
  await p.page.fill('#asset-picker-search', search).catch(() => {});
  await sleep(900);
  await p.page.click(`button[data-asset-ref="${nodeId}"]`, { timeout: 6000 }).catch(() => {});
  await sleep(600);
  await p.page.selectOption('#f-maint-type', { label: 'Breakdown / Corrective' }).catch(() => p.page.selectOption('#f-maint-type', { value: 'Breakdown' }).catch(() => {}));
  await p.page.fill('#f-problem', `${tag} ${problem}`).catch(() => {});
  await p.page.selectOption('#f-category', { label: 'Mechanical' }).catch(() => {});
  await p.page.click('.btn-next:visible').catch(() => {});
  await sleep(450);
  await p.page.fill('#f-action', 'replaced the seal, ran for 30 minutes, no leak').catch(() => {});
  await p.page.evaluate(() => { const b = [...document.querySelectorAll('.consequence-btn')].find((x) => /stopped production/i.test((x.getAttribute('data-value') || '') + ' ' + x.textContent)); if (b) b.click(); });
  await p.page.click('#save-entry-btn').catch(() => {});
  await sleep(3500);
  return psql(`select id || '|' || coalesce(asset_node_id::text,'') from logbook where problem like '${q(tag)}%' and hive_id = '${HIVE_ID}' order by created_at desc limit 1`);
}
RECIPES.J22 = {
  1: async (X) => {   // the machine the supervisor commissioned is in the worker's list
    const { s } = X.S;
    const name = `${X.tag} pump`;
    const filed = await fileMachine(s, X.tag, name);
    const approved = await approveInQueue(s, filed.id);
    const st = psql(`select status from asset_nodes where id::text = '${q(filed.id || '')}'`);
    X.rec.node = { id: filed.id, name };
    return { act: { ok: !!filed.id && approved && st === 'approved', detail: `filed on the logbook's asset form (${filed.status || 'no row'}) and approved in hive.html's queue by ${s.m.name}: ${st || 'unknown'}` },
      // the list card is lean (name, place, criticality); the machine's own page says "Added and approved by <name> on
      // <date>" - the worker searches the list, opens the machine, and reads that line
      marker: `by ${s.m.name}`, path: 'asset-hub.html',
      reach: async (R2, ms) => {
        await go(R2, 'asset-hub.html');
        await R2.page.fill('#asset-search', name).catch(() => {});
        await sleep(1500);
        await R2.page.evaluate((nm) => {
          const el = [...document.querySelectorAll('[onclick], button, a, [role="button"], li')].find((c) => (c.innerText || '').includes(nm) && (c.innerText || '').length < 400);
          if (el) el.click();
        }, name);
        await sleep(2000);
        return findText(R2, `by ${s.m.name}`, ms);
      },
      rec: { table: 'asset_nodes', id: filed.id, where: `and status = 'approved'` } };
  },
  2: async (X) => {   // the worker's work on it reads on the supervisor's logbook
    const { w } = X.S;
    const n = X.rec.node || {};
    const row = await logOnMachine(w, X.tag, n.id, 'pump seal weeping at the gland');
    const [id, node] = row ? row.split('|') : [null, null];
    return { act: { ok: !!id && node === n.id, detail: `the logbook wizard on ${n.name} (chosen through the picker's search) as ${w.m.name}: entry ${id || 'NO ROW'} on node ${node || 'none'}` },
      marker: X.tag, path: 'logbook.html', reach: (R2, ms) => reachTeam(R2, X.tag, ms), rec: { table: 'logbook', id } };
  },
  3: (X) => RECIPES.J3[1](X),   // the PM plan the supervisor set is the worker's (the same machine name, the Add Asset wizard)
  4: (X) => RECIPES.J2[4](X),   // its failures and repairs in the supervisor's numbers (the page's own Refresh)
  5: async (X) => {   // the trail names who did what across its life
    const { w } = X.S;
    const line = psql(`select id || '|' || actor from hive_audit_log where hive_id = '${HIVE_ID}' and created_at >= '${X.t0}'
      and action = 'create_logbook_entry' and actor = '${q(w.m.name)}' order by created_at desc limit 1`);
    const [aid, actor] = line ? line.split('|') : [null, null];
    return { act: { ok: !!aid, detail: `the trail line the worker's entry wrote: ${aid || 'NONE'} by ${actor || 'nobody'}` },
      marker: X.tag, path: 'audit-log.html', rec: { table: 'hive_audit_log', id: aid } };
  },
};

// ── J23 · one spare part: the supervisor adds it to the shelf, the worker issues it against a job, the count moves for the
// supervisor, and the machine's history carries the job.
async function openPart(p, name, id) {   // inventory's own search, then the part's "Open item details" button
  await go(p, 'inventory.html');
  await p.page.fill('#search-input', name).catch(() => {});
  await sleep(1500);
  await p.page.evaluate(([nm, pid]) => {
    const btn = pid && document.querySelector(`button[onclick="openDetailModal('${pid}')"]`);
    if (btn) { btn.click(); return; }
    const el = [...document.querySelectorAll('[onclick], button, [role="button"]')].find((c) => (c.innerText || '').includes(nm) && (c.innerText || '').length < 500);
    if (el) el.click();
  }, [name, id || '']);
  await sleep(1800);
}
RECIPES.J23 = {
  1: async (X) => {   // the part the supervisor received is on the worker's shelf
    const { s } = X.S;
    const name = `${X.tag} V-belt B52`;
    await go(s, 'inventory.html');
    await s.page.click('#btn-add-part', { timeout: 6000 }).catch(() => s.page.evaluate(() => { if (typeof openAddModal === 'function') openAddModal(); }));
    await sleep(1000);
    await s.page.fill('#f-part-name', name).catch(() => {});
    await s.page.fill('#f-part-number', X.tag.slice(-10)).catch(() => {});
    await s.page.fill('#f-qty', '10').catch(() => {});
    await s.page.fill('#f-min-qty', '2').catch(() => {});
    await s.page.click('#part-submit-btn', { timeout: 6000 }).catch(() => {});
    await sleep(3500);
    const row = psql(`select id || '|' || coalesce(qty_on_hand::text,'') || '|' || coalesce(status,'') from inventory_items where hive_id = '${HIVE_ID}' and part_name = '${q(name)}' limit 1`);
    const [id, qty, st] = row ? row.split('|') : [null, null, null];
    X.rec.part = { id, name, qty: Number(qty) };
    return { act: { ok: !!id, detail: `inventory's Add Part as ${s.m.name}: inventory_items ${id || 'NO ROW'} qty ${qty || '?'} ${st || ''}` },
      marker: `Added by ${s.m.name}`, path: 'inventory.html',
      reach: async (R2, ms) => { await openPart(R2, name, id); return findText(R2, `Added by ${s.m.name}`, ms); },
      rec: { table: 'inventory_items', id } };
  },
  2: async (X) => {   // the part the worker issued is on the job entry
    const { w } = X.S;
    const pt = X.rec.part || {};
    await go(w, 'logbook.html');
    await w.page.click('#asset-picker-btn', { timeout: 6000 }).catch(() => {});
    await sleep(800);
    await w.page.click('button[data-asset-id]', { timeout: 6000 }).catch(() => {});
    await sleep(600);
    await w.page.selectOption('#f-maint-type', { label: 'Breakdown / Corrective' }).catch(() => {});
    await w.page.fill('#f-problem', `${X.tag} belt slipping on the drive`).catch(() => {});
    await w.page.selectOption('#f-category', { label: 'Mechanical' }).catch(() => {});
    await w.page.click('.btn-next:visible').catch(() => {});
    await sleep(450);
    await w.page.fill('#f-action', 'replaced the V-belt and re-tensioned').catch(() => {});
    // the part used: the form's own picker, searched by name
    await w.page.evaluate(() => { if (typeof openPartsPicker === 'function') openPartsPicker(); });
    await sleep(900);
    await w.page.fill('#parts-picker-search', pt.name || '').catch(() => {});
    await sleep(900);
    const picked = await w.page.evaluate(([nm, pid]) => {
      // the picker's rows are button[data-part-id] with listeners (renderPartsPickerList), not onclick attributes
      const rows = [...document.querySelectorAll('button[data-part-id]')];
      const b = rows.find((x) => x.dataset.partId === pid || (x.dataset.partName || '').includes(nm));
      if (b) { b.click(); return true; }
      return rows.length;
    }, [pt.name || '---', pt.id || '---']);
    if (picked !== true) X.notes.push(`hand-off 2: the parts picker did not offer ${pt.name} (${picked} part(s) listed)`);
    await sleep(600);
    await w.page.evaluate(() => { const b = [...document.querySelectorAll('.consequence-btn')].find((x) => /stopped production/i.test((x.getAttribute('data-value') || '') + ' ' + x.textContent)); if (b) b.click(); });
    await w.page.click('#save-entry-btn').catch(() => {});
    await sleep(4000);
    const row = psql(`select id || '|' || coalesce(asset_node_id::text,'') || '|' || coalesce(parts_used::text,'') from logbook where problem like '${q(X.tag)}%' and hive_id = '${HIVE_ID}' order by created_at desc limit 1`);
    const [id, node, parts] = row ? [row.split('|')[0], row.split('|')[1], row.split('|').slice(2).join('|')] : [null, null, ''];
    X.rec.entry = { id, node };
    return { act: { ok: !!id && (parts || '').includes(pt.name || '---'), detail: `the logbook wizard with the part picked from its own picker, as ${w.m.name}: entry ${id || 'NO ROW'}, parts_used ${parts ? parts.slice(0, 120) : 'none'}` },
      marker: pt.name, path: 'logbook.html',
      // the supervisor finds the job on the team feed and opens it: the part is on the entry
      reach: async (R2, ms) => {
        await reachTeam(R2, X.tag, 15000);
        await R2.page.evaluate((t) => {
          const card = [...document.querySelectorAll('#entries-list .entry-card, #entries-list [onclick*="openModal"], .entry-card')].find((c) => (c.textContent || '').includes(t));
          if (card) (card.querySelector('[onclick*="openModal"]') || card).click();
        }, X.tag);
        await sleep(1200);
        return findText(R2, pt.name, ms);
      },
      rec: { table: 'logbook', id } };
  },
  3: async (X) => {   // the issue moved the count the supervisor reads
    const { w } = X.S;
    const pt = X.rec.part || {};
    const now = psql(`select coalesce(qty_on_hand::text,'') from inventory_items where id = '${q(pt.id || '')}'`);
    const tx = psql(`select id || '|' || coalesce(qty_after::text,'') || '|' || coalesce(worker_name,'') from inventory_transactions where item_id = '${q(pt.id || '')}'
      and created_at >= '${X.t0}' order by created_at desc limit 1`);
    const [tid, after, by] = tx ? tx.split('|') : [null, null, null];
    return { act: { ok: !!tid && Number(now) === pt.qty - 1, detail: `the issue at hand-off 2 moved ${pt.name}: ${pt.qty} -> ${now}; transaction ${tid || 'NONE'} (stock after ${after}) by ${by || 'nobody'}` },
      marker: `Stock after: ${after}`, path: 'inventory.html',
      reach: async (R2, ms) => { await openPart(R2, pt.name, pt.id); return findText(R2, `Stock after: ${after}`, ms); },
      rec: { table: 'inventory_transactions', id: tid } };
  },
  4: async (X) => {   // the part shows in the machine's history
    const e = X.rec.entry || {};
    const pt = X.rec.part || {};
    return { act: { ok: !!e.id && !!e.node, detail: `the job of hand-off 2 (entry ${e.id || 'none'}) on node ${e.node || 'none'}` },
      marker: X.tag, markerRx: new RegExp(String(pt.name || '---').replace(/[.*+?^${}()|[\]\\]/g, '\\$&').split(' ').slice(-2).join(' '), 'i'),
      path: e.node ? `asset-hub.html?node_id=${e.node}` : 'asset-hub.html', rec: { table: 'v_logbook_truth', id: e.id } };
  },
};

// ── J29 · typhoon season: the storm job handed on by push, the worker's entry made with no network synced later, the storm
// shift plan published, the week's downtime counted.
RECIPES.J29 = {
  1: async (X) => {   // the storm work order the supervisor assigned is pushed to the worker
    const { w } = X.S;
    const r = await RECIPES.J9[1](X);   // raised by the supervisor, handed on in its own edit (the same act as J9)
    const pushSaid = psql(`select coalesce(payload->>'title','') || ': ' || coalesce(payload->>'body','') from service_outbox
      where consumer = 'notify-push' and created_at >= '${X.t0}' and payload->'auth_uids' ? '${w.m.uid}' and payload->>'title' = 'Work order assigned to you'
      order by created_at desc limit 1`);
    return { act: r.act, marker: X.tag, path: 'logbook.html?status=Open', channelSaid: pushSaid || null, rec: r.rec,
      F: () => ({ ok: !!pushSaid, detail: `the push to ${w.m.name}: ${pushSaid || 'NONE'}` }) };
  },
  2: async (X) => {   // the worker's entries made offline sync into the supervisor's logbook
    const { w } = X.S;
    const tag2 = `${X.tag}-off`;
    await go(w, 'logbook.html');
    await w.ctx.setOffline(true);   // the network goes with the storm: the page is open, the entry is written without it
    const r = await logWizard(w.page, H(w.page), { tag: tag2, maintType: 'Breakdown / Corrective', status: 'Open', problem: 'flooded motor pit, pump tripped' });
    const queued = await w.page.evaluate(() => (document.getElementById('toast-text') || {}).textContent || '').catch(() => '');
    const before = psql(`select count(*) from logbook where problem like '${q(tag2)}%' and hive_id = '${HIVE_ID}'`);
    await sleep(1500);
    await w.ctx.setOffline(false);  // the network returns; the page's own drain sends the queued entry
    let id = null;
    for (let t = 0; t < 45000 && !id; t += 1500) {
      await sleep(1500);
      id = psql(`select id from logbook where problem like '${q(tag2)}%' and hive_id = '${HIVE_ID}' order by created_at limit 1`) || null;
    }
    return { act: { ok: Number(before) === 0 && !!id, detail: `logged with the network off as ${w.m.name} (${(r.toast || queued || 'no toast').slice(0, 80)}): ${before} row(s) while offline, then ${id ? 'synced as ' + id : 'NEVER SYNCED'} when it returned` },
      marker: tag2, path: 'logbook.html', reach: (R2, ms) => reachTeam(R2, tag2, ms), rec: { table: 'logbook', id } };
  },
  3: (X) => RECIPES.J9[2](X),   // the storm shift plan the supervisor published (the same act as J9)
  4: (X) => RECIPES.J2[4](X),   // the week's downtime in the supervisor's account of it (the page's own Refresh)
};

// ── J17 · sensor to work order: the plant bridge posts a machine's readings (a baseline, then a spike), the anomaly
// composer turns them into the worker's alert, and the machine's page and the worker's home carry it.
function serviceKey() {   // the bridge holds the service key (sensor-readings-ingest admits only a service-role caller)
  const r = spawnSync('docker', ['exec', 'supabase_edge_runtime_workhive', 'printenv', 'SUPABASE_SERVICE_ROLE_KEY'], { encoding: 'utf8' });
  return (r.stdout || '').trim();
}
// ★A BRIDGE REPORTS OVER TIME, AND THE INGEST JUDGES A READING AGAINST WHAT CAME BEFORE IT (2026-11-05, J17 pass a):
// the first walk posted the baseline and the spike in ONE batch, the ingest's baseline (the PRIOR 30 days only) was
// empty, and nothing was flagged. The walk posts the way a plant bridge does: the hours of normal running first, then
// the spike, each reading stamped at the minute it was taken.
async function postReadings(X, nodeId, parameter, values, minutesApart, endMinutesAgo = 0) {
  const key = serviceKey();
  const now = Date.now();
  const readings = values.map((v, i) => ({ asset_id: nodeId, parameter, value: v, source: 'mqtt', meta: { walk: X.tag },
    recorded_at: new Date(now - (endMinutesAgo + (values.length - 1 - i) * minutesApart) * 60000).toISOString() }));
  // a bridge retries a gateway error (502/503/504, or no answer) - J17's first pass met the edge runtime mid-restart
  let r = null;
  for (let t = 0; t < 6; t++) {
    r = await fetch(`${SB}/functions/v1/sensor-readings-ingest`, { method: 'POST',
      headers: { apikey: key, Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ hive_id: HIVE_ID, readings }) })
      .catch(() => null);
    if (r && ![502, 503, 504].includes(r.status)) break;
    await sleep(5000);
  }
  if (!r) return { status: 0, body: 'no answer after 6 tries' };
  return { status: r.status, body: (await r.text()).slice(0, 160) };
}
RECIPES.J17 = {
  1: async (X) => {   // the reading the machine posted raises the worker's anomaly alert
    const { w } = X.S;
    // a machine of the hive with no readings and no anomaly yet, so the alert is this walk's (read from the database)
    const quiet = psql(`select a.id || '|' || a.name from asset_nodes a where a.hive_id = '${HIVE_ID}' and a.deleted_at is null and a.status = 'approved'
      and a.name is not null and not exists (select 1 from sensor_readings s where s.asset_id = a.id)
      and (select count(*) from asset_nodes o where o.hive_id = a.hive_id and o.name = a.name and o.deleted_at is null) = 1
      and not exists (select 1 from anomaly_signals n where n.hive_id = a.hive_id and n.machine = a.name) order by a.name limit 1`);
    const [nid, machine] = quiet ? quiet.split('|') : [null, null];
    // twelve hours of normal running, a reading every 20 minutes (2.0-2.2 mm/s), then five readings of a bearing going
    const baseline = Array.from({ length: 36 }, (_, i) => 2.0 + ((i * 7) % 5) * 0.05);
    const base = nid ? await postReadings(X, nid, 'vibration', baseline, 20, 15) : { status: 0, body: 'no quiet machine' };
    const spike = nid ? await postReadings(X, nid, 'vibration', [11.8, 12.4, 12.9, 13.1, 13.6], 2, 0) : { status: 0, body: '' };
    const flagged = Number(psql(`select count(*) from sensor_readings where asset_id = '${q(nid || '00000000-0000-0000-0000-000000000000')}' and is_anomaly`));
    // the composer runs hourly from the page (and daily from the cron); triggered here the way a member may trigger it
    const comp = await fetch(`${SB}/rest/v1/rpc/compute_anomaly_signals`, { method: 'POST',
      headers: { apikey: KEY, Authorization: `Bearer ${w.token}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ p_hive_id: HIVE_ID }) });
    const sig = psql(`select id || '|' || sensor_zscore_score from anomaly_signals where hive_id = '${HIVE_ID}' and machine = '${q(machine || '')}'
      and status in ('active','acknowledged') order by computed_at desc limit 1`);
    X.rec.sensor = { node: nid, machine, signal: sig ? sig.split('|')[0] : null };
    return { act: { ok: flagged === 5, detail: `the bridge posted 36 normal vibration readings on ${machine || 'NO MACHINE'} (HTTP ${base.status} ${base.body}), then 5 high ones (HTTP ${spike.status} ${spike.body}); ${flagged} flagged; the composer as ${w.m.name}: HTTP ${comp.status} -> signal ${sig || 'NONE'}` },
      marker: machine, markerRx: /anomal/i, whoRx: /sensor|reading|vibration/i, path: 'alert-hub.html',
      // the fused engine (Stair 3+) lists the strongest five first: a person taps Show all to reach the rest
      reach: async (R2, ms) => {
        await go(R2, 'alert-hub.html');
        const more = R2.page.locator('#anomaly-engine-panel .wh-more-btn');
        await more.first().waitFor({ state: 'visible', timeout: 8000 }).catch(() => {});
        if (await more.count().catch(() => 0)) await more.first().click().catch(() => {});
        return findText(R2, machine, ms);
      },
      rec: { table: 'v_sensor_truth', idCol: 'asset_id', id: nid, where: 'and is_anomaly' } };
  },
  2: async (X) => {   // the reading is on the machine's page
    const sn = X.rec.sensor || {};
    return { act: { ok: !!sn.node, detail: `the readings of hand-off 1 on ${sn.machine || 'none'}` },
      marker: 'reading 3-sigma off baseline', markerRx: /vibration/i, whoRx: /sensor|reading/i,
      path: sn.node ? `asset-hub.html?node_id=${sn.node}` : 'asset-hub.html',
      rec: { table: 'v_sensor_truth', idCol: 'asset_id', id: sn.node, where: 'and is_anomaly' } };
  },
  3: async (X) => {   // the alert is on the worker's home
    const sn = X.rec.sensor || {};
    return { act: { ok: !!sn.node, detail: `the flagged reading of hand-off 1 on ${sn.machine || 'none'}` },
      marker: sn.machine, markerRx: /out of band|anomal/i, whoRx: /sensor|reading|vibration/i, path: 'index.html',
      rec: { table: 'v_sensor_truth', idCol: 'asset_id', id: sn.node, where: 'and is_anomaly' } };
  },
};

// ── G-SHIFT · the shift changes hands: the outgoing worker's open job carried into the handover the incoming worker reads,
// the plan the supervisor published, the job on the incoming worker's logbook, their work on it in the supervisor's.
// the shift running now in Manila (06-14, 14-22, 22-06) and the instant it began (UTC+8, no daylight saving)
function shiftNow(now = new Date()) {
  const m = new Date(now.getTime() + 8 * 3600e3);
  const h = m.getUTCHours();
  const id = h >= 6 && h < 14 ? '06-14' : (h >= 14 && h < 22 ? '14-22' : '22-06');
  let start = Date.UTC(m.getUTCFullYear(), m.getUTCMonth(), m.getUTCDate(), Number(id.slice(0, 2))) - 8 * 3600e3;
  if (start > now.getTime()) start -= 86400e3;   // a night shift read after midnight began the day before
  return { id, start: new Date(start).toISOString(), before: new Date(start - 40 * 60e3).toISOString() };
}
RECIPES['G-SHIFT'] = {
  1: async (X) => {   // the outgoing worker's open job is carried into the handover the incoming worker reads
    const { o, i } = X.S;
    await go(o, 'logbook.html');
    const r = await logWizard(o.page, H(o.page), { tag: X.tag, maintType: 'Breakdown / Corrective', status: 'Open', problem: 'hydraulic hose weeping at the press' });
    const row = psql(`select id || '|' || coalesce(machine,'') || '|' || coalesce(asset_node_id::text,'') from logbook
      where problem like '${q(X.tag)}%' and hive_id = '${HIVE_ID}' order by created_at limit 1`);
    const [id, machine, node] = row ? row.split('|') : [null, null, null];
    X.rec.entry = { id, machine, node };
    const sh = shiftNow();
    // SETUP - the shift changes hands. The entry was made in the outgoing shift, so its time moves to 40 minutes before
    // this shift began (triggers off, like every fixture; the tagged row is deleted after the walk).
    if (id) psql(`set session_replication_role = replica; update logbook set created_at = '${sh.before}' where id = '${q(id)}'`);
    // the incoming shift's plan is built on its first open, so the window's existing plan is set aside (the snapshot
    // taken before the walk puts it back)
    const aside = psql(`set session_replication_role = replica; with d as (delete from shift_plans where hive_id = '${HIVE_ID}'
      and shift_window = '${sh.id}' and shift_date >= (now() at time zone 'Asia/Manila')::date - 1 returning 1) select count(*) from d`).split('\n').pop();
    await go(i, 'shift-brain.html');
    let plan = null;
    for (let t = 0; t < 120000 && !plan; t += 3000) {
      await sleep(3000);
      plan = psql(`select id from shift_plans where hive_id = '${HIVE_ID}' and shift_window = '${sh.id}' and created_at >= '${X.t0}'
        and payload->'carry_forward' @> '[{"id": "${q(id || '-')}"}]' limit 1`) || null;
    }
    const built = psql(`select count(*) from shift_plans where hive_id = '${HIVE_ID}' and shift_window = '${sh.id}' and created_at >= '${X.t0}'`);
    return { act: { ok: !!id && !!plan, detail: `the logbook wizard as ${o.m.name}: ${r.toast || 'no toast'} -> entry ${id || 'NONE'} on ${machine || '?'}, `
        + `its time moved to ${sh.before} (before the ${sh.id} shift began); ${aside} plan(s) of the window set aside; ${i.m.name}'s first open of `
        + `shift-brain built ${built} plan(s), ${plan ? 'plan ' + plan + ' carrying the job' : 'NONE carrying the job'} (the briefing's model call taken down by the local-only flag)` },
      marker: X.tag, path: 'shift-brain.html', rec: { table: 'shift_plans', id: plan } };
  },
  2: (X) => RECIPES.J9[2](X),   // the plan the supervisor published is what the incoming worker works from (the J9 act)
  3: async (X) => {   // the job the handover names is on the incoming worker's logbook
    const e = X.rec.entry || {};
    return { act: { ok: !!e.id, detail: `the entry of hand-off 1 (${e.id || 'none'}), carried in the handover` },
      marker: X.tag, path: 'logbook.html', reach: (R2, ms) => reachTeam(R2, X.tag, ms), rec: { table: 'logbook', id: e.id } };
  },
  4: async (X) => {   // the incoming worker's work on the carried-over job is in the supervisor's logbook
    const { i } = X.S;
    const e = X.rec.entry || {};
    // the supervisor hands the carried job to the incoming worker ("Move the work order", the J2 act) ...
    const asg = await RECIPES.J2[2]({ ...X, S: { ...X.S, w: i } });
    // ... and the incoming worker opens it from "Assigned to you" and taps Started
    await go(i, 'logbook.html');
    let opened = false;
    for (let t = 0; t < 15000 && !opened; t += 1000) {
      opened = await i.page.evaluate((id) => { const c = document.querySelector(`#open-jobs-list [onclick*="${id}"]`); if (c) { c.click(); return true; } return false; }, e.id || '-').catch(() => false);
      if (!opened) await sleep(1000);
    }
    await sleep(1200);
    const started = await i.page.evaluate(() => {
      const b = document.querySelector('#wo-assignee-actions button[onclick*="in_progress"]');
      if (b) { b.click(); return true; } return false;
    }).catch(() => false);
    await sleep(2500);
    const st = psql(`select coalesce(wo_state,'') || '|' || coalesce(wo_assigned_to,'') from logbook where id = '${q(e.id || '')}'`);
    return { act: { ok: asg.act.ok && opened && started && st === `in_progress|${i.m.name}`,
        detail: `${asg.act.detail}; then as ${i.m.name}: opened from "Assigned to you" ${opened}, Started ${started} -> wo_state|assigned_to = ${st}` },
      marker: X.tag, markerRx: /in progress/i, whoRx: new RegExp(i.m.name.split(' ')[0], 'i'), path: 'logbook.html',
      reach: (R2, ms) => reachTeam(R2, X.tag, ms), rec: { table: 'logbook', id: e.id, where: `and wo_state = 'in_progress'` } };
  },
  5: async (X) => {   // the printed shift handover report names the incoming technician
    const { o, i } = X.S;
    const e = X.rec.entry || {};
    const read = await printHandoverAs(o, i.m.name);
    return { act: { ok: read.generated && read.printed && read.text.includes(i.m.name),
        detail: `hive.html "Generate Shift Handover Report" as ${o.m.name} ${read.generated}, "Handover to" ${i.m.name}, Print ${read.printed} -> `
          + `the printed page names ${read.text.includes(i.m.name) ? i.m.name : 'NOBODY'} as incoming and ${read.text.includes(o.m.name) ? o.m.name : 'nobody'} as outgoing` },
      // the receiver reads paper: the printed page is what they are handed (its route on a bad network is the outgoing
      // worker's phone producing it - the A reading runs on the sender's connection)
      marker: X.tag, markerRx: new RegExp(i.m.name, 'i'), whoRx: new RegExp(o.m.name.split(' ')[0], 'i'),
      preRead: read.text.includes(X.tag) ? { card: read.text.replace(/\s+/g, ' ').slice(0, 1500) } : null,
      path: 'hive.html', aOnSender: true,
      reach: async (S2) => { const r2 = await printHandoverAs(S2, i.m.name); return r2.text.includes(X.tag) && r2.text.includes(i.m.name); },
      rec: { table: 'logbook', id: e.id } };
  },
};
// the outgoing worker's printed handover: hive.html's own Generate and Print, with the print window the page writes taken
// as the page (a printer cannot be read - the document the page sends to it can)
async function printHandoverAs(sx, incoming) {
  await go(sx, 'hive.html');
  await sx.page.evaluate(() => {
    window.__whPrinted = null;
    window.open = () => { const d = { h: '', write(x) { this.h += x; }, close() { window.__whPrinted = this.h; } }; return { document: d, close() {} }; };
  }).catch(() => {});
  let generated = false;
  for (let t = 0; t < 20000 && !generated; t += 1000) {
    generated = await sx.page.evaluate(() => { const b = document.querySelector('.handover-btn'); if (b && b.offsetParent) { b.click(); return true; } return false; }).catch(() => false);
    if (!generated) await sleep(1000);
  }
  await sleep(1500);
  await sx.page.fill('#ho-handover-to', incoming).catch(() => {});
  const printed = await sx.page.evaluate(() => { const b = document.querySelector('#handover-sheet button[onclick="printHandover()"]'); if (b) { b.click(); return true; } return false; }).catch(() => false);
  await sleep(1500);
  const text = await sx.page.evaluate(() => {
    const h = window.__whPrinted || '';
    const d = new DOMParser().parseFromString(h, 'text/html');
    return (d.body && d.body.textContent) || '';
  }).catch(() => '');
  return { generated, printed, text };
}

// ── G-SENSOR · reading to PM: the machine's alert, the worker's acknowledgement on the supervisor's alert, the PM the
// supervisor scheduled from it on the worker's list, the worker's job on the machine in the supervisor's logbook.
RECIPES['G-SENSOR'] = {
  1: (X) => RECIPES.J17[1](X),   // the machine's reading raises the worker's alert (the J17 act: a bridge's normal hours, then the spike)
  2: async (X) => {   // the worker's acknowledgement is on the supervisor's alert
    const { w } = X.S;
    const sn = X.rec.sensor || {};
    await go(w, 'alert-hub.html');
    let marked = false;
    for (let t = 0; t < 20000 && !marked; t += 1000) {
      marked = await w.page.evaluate((nid) => {
        const b = document.querySelector(`#anomaly-engine-list [data-sensor-seen^="sensor:${nid}:"]`);
        if (b && b.getAttribute('aria-pressed') !== 'true') { b.click(); return true; } return false;
      }, sn.node || '-').catch(() => false);
      if (!marked) await sleep(1000);
    }
    await sleep(2500);
    const row = psql(`select id || '|' || alert_key || '|' || coalesce(actor,'') from alert_dismissals where hive_id = '${HIVE_ID}'
      and action = 'acknowledged' and alert_key like 'sensor:${q(sn.node || '-')}:%' order by created_at desc limit 1`);
    const [did, key, actor] = row ? row.split('|') : [null, null, null];
    return { act: { ok: marked && actor === w.m.name, detail: `"Mark seen" on ${sn.machine || 'NO MACHINE'}'s card as ${w.m.name} ${marked} -> alert_dismissals ${did || 'NONE'} (${key || '-'}) by ${actor || 'nobody'}` },
      marker: sn.machine, markerRx: /seen by/i, path: 'alert-hub.html', rec: { table: 'alert_dismissals', id: did } };
  },
  // the PM the supervisor scheduled for the machine that alerted (the J3 act, named for that machine)
  3: async (X) => { X.pmName = `${X.tag} ${(X.rec.sensor || {}).machine || 'machine'}`; return RECIPES.J3[1](X); },
  4: async (X) => {   // the worker's job on the machine closes the alert's loop for the supervisor
    const { w } = X.S;
    const sn = X.rec.sensor || {};
    const row = await logOnMachine(w, X.tag, sn.node, 'vibration traced to a worn coupling insert, replaced', sn.machine || X.tag);
    const [id, node] = row ? row.split('|') : [null, null];
    return { act: { ok: !!id && node === sn.node, detail: `the logbook wizard on ${sn.machine || '?'} (chosen through the picker's search) as ${w.m.name}: entry ${id || 'NO ROW'} on node ${node || 'none'}` },
      marker: X.tag, path: 'logbook.html', reach: (R2, ms) => reachTeam(R2, X.tag, ms), rec: { table: 'logbook', id } };
  },
};

// ── G-MULTI · one person in two hives (a contractor serving two plants): each supervisor sees only their own hive's
// record of them, a push from hive A opens in hive A wherever the contractor last stood, a PM of hive B is on their list
// only while they stand in B, and their changes in A are in A's trail and not B's.
RECIPES['G-MULTI'] = {
  1: async (X) => {   // the contractor's entry in hive A is in supervisor A's logbook
    const { c } = X.S;
    const tag = `${X.tag}-A`;
    await go(c, 'logbook.html');
    const r = await logWizard(c.page, H(c.page), { tag, maintType: 'Breakdown / Corrective', status: 'Open', problem: 'gearbox oil seal weeping' });
    const row = psql(`select id || '|' || coalesce(machine,'') from logbook where problem like '${q(tag)}%' and hive_id = '${HIVE_ID}' order by created_at limit 1`);
    const [id, machine] = row ? row.split('|') : [null, null];
    X.rec.entryA = { id, tag, machine };
    return { act: { ok: !!id, detail: `the logbook wizard in ${HOME} as ${c.m.name}: ${r.toast || 'no toast'} -> entry ${id || 'NONE'} on ${machine || '?'}` },
      marker: tag, path: 'logbook.html', reach: (R2, ms) => reachTeam(R2, tag, ms), rec: { table: 'logbook', id } };
  },
  2: async (X) => {   // the contractor's entry in hive B is in supervisor B's logbook, and A's is not
    const { c, b } = X.S;
    const hiveB = b.m.seatId;
    const tag = `${X.tag}-B`;
    const a = X.rec.entryA || {};
    // the contractor crosses to the other plant by a link that names hive B (the way a push now carries its hive)
    await go(c, `logbook.html?hive=${hiveB}`);
    const seated = await c.page.evaluate(() => localStorage.getItem('wh_active_hive_id')).catch(() => null);
    const r = await logWizard(c.page, H(c.page), { tag, maintType: 'Breakdown / Corrective', status: 'Open', problem: 'cooling fan bearing rumble' });
    const id = psql(`select id from logbook where problem like '${q(tag)}%' and hive_id = '${hiveB}' order by created_at limit 1`) || null;
    return { act: { ok: seated === hiveB && !!id, detail: `crossed by a link naming ${b.m.seatName}: the page seated ${seated === hiveB ? b.m.seatName : (seated || 'nothing')}; `
        + `the wizard as ${c.m.name}: ${r.toast || 'no toast'} -> entry ${id || 'NONE'} in ${b.m.seatName}` },
      marker: tag, path: 'logbook.html',
      // supervisor B's team search finds the B entry, and finds nothing for the contractor's entry in A
      reach: async (R2, ms) => { const leak = await reachTeam(R2, a.tag || '-', 6000); const hit = await reachTeam(R2, tag, ms); return leak ? null : hit; },
      rec: { table: 'logbook', id },
      F: () => {
        const mine = Number(asUser(b.m.uid, `select count(*) from logbook where id = '${q(id || '-')}'`));
        const theirs = Number(asUser(b.m.uid, `select count(*) from logbook where id = '${q(a.id || '-')}'`));
        return { ok: mine === 1 && theirs === 0, detail: `as ${b.m.name} through RLS: the ${b.m.seatName} entry ${mine} row(s), the ${HOME} entry ${theirs} row(s)` };
      } };
  },
  3: async (X) => {   // supervisor A's work order is pushed to the contractor and opens in hive A
    const { c, a } = X.S;
    // its own tag: J9's act finds its entry by the tag's prefix, and hop 1's "<tag>-A" entry would answer for it
    const tagWO = `${X.tag}-WO`;
    const r = await RECIPES.J9[1]({ ...X, tag: tagWO, S: { ...X.S, w: c, s: a } });
    const push = psql(`select coalesce(payload->>'url','') || '|' || coalesce(payload->>'title','') || ': ' || coalesce(payload->>'body','') from service_outbox
      where consumer = 'notify-push' and created_at >= '${X.t0}' and payload->'auth_uids' ? '${c.m.uid}' and payload->>'title' = 'Work order assigned to you'
      order by created_at desc limit 1`);
    const url = push ? push.split('|')[0] : null;
    const said = push ? push.split('|').slice(1).join('|') : null;
    const path = String(url || '/logbook.html?status=Open').replace(/^\//, '');
    const standing = await c.page.evaluate(() => localStorage.getItem('wh_active_hive_id')).catch(() => null);
    return { act: { ok: r.act.ok && !!url, detail: `${r.act.detail}; the push to ${c.m.name} links ${url || 'NOTHING'}, and the contractor last stood in ${standing === HIVE_ID ? HOME : 'the other hive'}` },
      marker: tagWO, path, channelSaid: said || null, rec: { table: 'v_logbook_truth', id: (X.rec.job || {}).id },
      reach: async (R2, ms) => { await go(R2, path); return findText(R2, tagWO, ms); },
      F: () => ({ ok: !!url && url.includes(`hive=${HIVE_ID}`), detail: `the push carries ${url || 'no link'} (it must name ${HOME})` }) };
  },
  4: async (X) => {   // supervisor B's PM is on the contractor's list only while standing in hive B
    const { b } = X.S;
    const hiveB = b.m.seatId;
    X.pmHive = hiveB;
    const r = await RECIPES.J3[1]({ ...X, S: { ...X.S, s: b } });
    X.pmHive = null;
    const name = (X.rec.pm || {}).name;
    return { act: r.act, marker: name, path: `pm-scheduler.html?hive=${hiveB}`, rec: r.rec,
      // standing in hive A, B's PM is not on the list; standing in B it is
      reach: async (R2, ms) => {
        const leak = await findPmAsset(R2, name, 6000, `pm-scheduler.html?hive=${HIVE_ID}`);
        const hit = await findPmAsset(R2, name, ms, `pm-scheduler.html?hive=${hiveB}`);
        return leak ? null : hit;
      } };
  },
  5: async (X) => {   // the contractor's changes in hive A are in A's trail and not B's
    const { c, a, b } = X.S;
    const e = X.rec.entryA || {};
    const aid = psql(`select id from hive_audit_log where hive_id = '${HIVE_ID}' and actor = '${q(c.m.name)}' and action = 'create_logbook_entry'
      and target_id = '${q(e.id || '-')}' order by created_at desc limit 1`) || null;
    return { act: { ok: !!aid, detail: `${c.m.name}'s hand-off-1 entry wrote ${aid ? 'audit line ' + aid : 'NO audit line'} in ${HOME}'s trail` },
      marker: e.machine || c.m.name, whoRx: new RegExp(c.m.name.split(' ')[0], 'i'), path: 'audit-log.html', rec: { table: 'hive_audit_log', id: aid },
      // the trail's own search, by the entry's id (an older line on the same machine must not stand in for this one)
      reach: async (R2, ms) => {
        await go(R2, 'audit-log.html');
        await R2.page.fill('#search-input', e.id || '-').catch(() => {});
        await R2.page.press('#search-input', 'Enter').catch(() => {});
        await sleep(2500);
        return findText(R2, e.machine || c.m.name, ms);
      },
      F: () => {
        const ra = Number(asUser(a.m.uid, `select count(*) from hive_audit_log where id::text = '${q(aid || '-')}'`));
        const rb = Number(asUser(b.m.uid, `select count(*) from hive_audit_log where id::text = '${q(aid || '-')}'`));
        return { ok: ra === 1 && rb === 0, detail: `the line through RLS: as ${a.m.name} (${HOME}) ${ra} row(s), as ${b.m.name} (${b.m.seatName}) ${rb} row(s)` };
      } };
  },
};

// the rows the walk changes in place: today's snapshot and the machine's alerts (restored after); the rest it made is tagged

// ══ M8 · the record's hand-offs (2026-11-05) ═════════════════════════════════════════════════════════════════════════
// the shared confirm modal (utils.js whConfirm): its OK, as a person taps it
async function modalOk(s, ms = 5000) {
  const ok = s.page.locator('[data-wh-modal-ok]').first();
  try { await ok.waitFor({ state: 'visible', timeout: ms }); } catch (_) { return false; }
  await ok.click().catch(() => ok.evaluate((el) => el.click()));
  await sleep(1200);
  return true;
}
// analytics-report builds on the person's own tap: "Generate Report", then its header says when
async function generateReport(P) {
  await P.page.click('#generate-btn', { timeout: 10000 }).catch(() => P.page.evaluate(() => { const b = document.getElementById('generate-btn'); if (b) b.click(); }));
  for (let t = 0; t < 90000; t += 1000) {
    const ok = await P.page.evaluate(() => /Generated:/.test(document.body.innerText || '')).catch(() => false);
    if (ok) { await sleep(800); return; }
    await sleep(1000);
  }
}
// the supervisor's Remove on the hive's roster, as tapped: Show, the member's Remove, the confirm's OK
async function removeMember(X, s, l) {
  const mid = psql(`select id from hive_members where hive_id = '${HIVE_ID}' and auth_uid = '${l.m.uid}' and status = 'active'`);
  if (!mid) { X.notes.push(`remove: ${l.m.name} is not an active member of ${HOME}`); return false; }
  await go(s, 'hive.html');
  await s.page.evaluate(() => { const b = document.getElementById('btn-toggle-members'); if (b && b.getAttribute('aria-expanded') !== 'true') b.click(); });
  await sleep(1200);
  const tapped = await s.page.evaluate((id) => {
    const b = [...document.querySelectorAll('#members-list button')].find((x) => (x.getAttribute('onclick') || '').includes(id));
    if (b) { b.click(); return true; } return false;
  }, mid);
  if (!tapped) { X.notes.push(`remove: no Remove control for ${l.m.name} on the roster`); return false; }
  const ok = await modalOk(s);
  await sleep(2000);
  // from here the removed member's own page decides where they stand (the init script stops seating them)
  if (l.page) await l.page.evaluate(() => { try { localStorage.setItem('wh_gj_noseat', '1'); } catch (_) { /* storage blocked */ } }).catch(() => {});
  return ok;
}
// a job logged under a lock-out and a permit, through the wizard's own Safety Isolation section
const lotoBeforeSave = (ref) => async (page) => {
  await page.evaluate((r) => {
    const cb = document.getElementById('f-loto');
    if (cb && !cb.checked) cb.click();   // its onchange (toggleLotoPermit) opens the permit field
    const f = document.getElementById('f-permit-ref');
    if (f) { f.value = r; f.dispatchEvent(new Event('input', { bubbles: true })); f.dispatchEvent(new Event('change', { bubbles: true })); }
  }, ref);
};
const reEsc = (t) => String(t).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
// the hive's trail shows each line's details behind its own "Show details" - the tap a person makes on the line they are
// reading (the row is found by its own id; Load more pages back if the line is older than the first page)
const auditReach = (aid, marker) => async (R2, ms) => {
  await go(R2, 'audit-log.html');
  for (let i = 0; i < 5; i++) {
    const tapped = await R2.page.evaluate((id) => {
      const row = document.querySelector(`.entry[data-entry-id="${id}"]`);
      if (!row) return false;
      const b = [...row.querySelectorAll('button')].find((x) => x.hasAttribute('aria-expanded'));
      if (b && b.getAttribute('aria-expanded') !== 'true') b.click();
      return true;
    }, String(aid || ''));
    if (tapped) break;
    const more = await R2.page.evaluate(() => { const b = document.querySelector('#audit-load-more-wrap:not(.hidden) button'); if (b) { b.click(); return true; } return false; });
    if (!more) break;
    await sleep(1500);
  }
  await sleep(800);
  return findText(R2, marker, ms);
};

// ── J4 · audit season: the worker's entries are the supervisor's defence in front of an inspector
RECIPES.J4 = {
  1: async (X) => {   // the worker's entry reaches the supervisor (and the report's figures are taken before it lands)
    X.rec.before = await reportFigures(X.S.s);
    if (X.rec.before.error) X.notes.push(`the report before the worker logged: ${X.rec.before.error}`);
    return RECIPES.J2[1](X);
  },
  2: async (X) => {   // the worker amends their entry; the supervisor's trail says what it said before and after
    const { w } = X.S;
    const e = X.rec.entry || {};
    const amended = `${X.tag} bearing noise drive end - coupling found loose`;
    const opened = await openEdit(w, X.tag);
    await w.page.evaluate((v) => { const el = document.getElementById('f-problem'); if (el) { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); } }, amended);
    await w.page.evaluate(() => { const b = document.getElementById('save-entry-btn'); if (b) b.click(); });
    await sleep(3500);
    const row = psql(`select id || '|' || coalesce(meta->'changed_fields'->'problem'->>'from','') || '|' || coalesce(meta->'changed_fields'->'problem'->>'to','')
      from hive_audit_log where hive_id = '${HIVE_ID}' and action = 'edit_logbook_entry' and target_id = '${q(e.id || '')}' order by created_at desc limit 1`);
    const [aid, from, to] = row ? row.split('|') : [null, '', ''];
    return { act: { ok: opened && !!aid && to === amended, detail: `the entry's own Edit as ${w.m.name}: audit ${aid || 'NO ROW'}, problem "${from}" -> "${to}"` },
      marker: amended, markerRx: /→/, path: 'audit-log.html', reach: auditReach(aid, amended), rec: { table: 'hive_audit_log', id: aid } };
  },
  3: async (X) => {   // the machine's history an inspector reads names the worker's job
    const e = X.rec.entry || {};
    return { act: { ok: !!e.node, detail: `the entry logged at hand-off 1 on ${e.machine} (${e.node || 'no machine'})` },
      marker: X.tag, path: e.node ? `asset-hub.html?node_id=${e.node}` : 'asset-hub.html', rec: { table: 'v_logbook_truth', id: e.id } };
  },
  4: async (X) => {   // the worker's breakdown is one more failure in the report the supervisor generates
    const b = X.rec.before || {};
    return { act: { ok: b.failures != null, detail: `the report's engine before the worker logged: ${b.failures ?? 'unread'} failures in 90 days` },
      marker: null, path: 'analytics-report.html', prepare: generateReport,
      figure: async (R) => {
        const v = await R.page.evaluate(() => {
          const c = [...document.querySelectorAll('.kpi-cell')].find((x) => /Total Failures/i.test(x.innerText || ''));
          const n = c && c.querySelector('.kpi-value');
          return n ? Number((n.innerText || '').replace(/[^\d]/g, '')) : null;
        }).catch(() => null);
        const gen = await R.page.evaluate(() => ((document.body.innerText || '').match(/Generated:[^\n]{0,60}/) || [])[0] || null).catch(() => null);
        const ok = v != null && b.failures != null && v === b.failures + 1 && !!gen;
        return { ok, said: `Total Failures ${v} · ${gen || 'no "Generated" line'}`, before: b.failures ?? null,
          ...(ok ? {} : { why: v == null ? 'the report states no Total Failures' : `the report says ${v}; before the worker's breakdown the engine said ${b.failures}` }) };
      },
      rec: { table: 'v_logbook_truth', id: (X.rec.entry || {}).id } };
  },
};

// ── J24 · a safety incident: the worker's lock-out becomes the supervisor's record and an inspector's trail
RECIPES.J24 = {
  1: async (X) => {   // the worker's lock-out entry reaches the supervisor, badge and permit on it
    const { w, s } = X.S;
    X.rec.before = await reportFigures(s);
    if (X.rec.before.error) X.notes.push(`the report before the worker logged: ${X.rec.before.error}`);
    X.rec.permit = `PTW-${X.tag.slice(-7)}`;
    await go(s, 'logbook.html');
    await go(w, 'logbook.html');
    const r = await logWizard(w.page, H(w.page), { tag: X.tag, problem: 'conveyor drive guard off for a belt change', consequence: 'safety',
      beforeSave: lotoBeforeSave(X.rec.permit) });
    const row = psql(`select id || '|' || machine || '|' || coalesce(asset_node_id::text,'') || '|' || loto_applied || '|' || coalesce(permit_reference,'') || '|' || coalesce(failure_consequence,'')
      from logbook where problem like '${q(X.tag)}%' and hive_id = '${HIVE_ID}' order by created_at limit 1`);
    const [id, machine, node, loto, permit, cons] = row ? row.split('|') : [];
    X.rec.entry = { id, machine, node };
    // psql renders this boolean as 'true' inside the || concat (an output function, not the 't' of a bare column)
    return { act: { ok: !!id && /^t(rue)?$/.test(loto || '') && permit === X.rec.permit && /safety/i.test(cons || ''),
      detail: `logbook wizard as ${w.m.name}, LOTO under ${X.rec.permit}: ${r.toast || 'no toast'} -> ${id || 'NO ROW'} loto=${loto} permit=${permit} consequence=${cons}` },
      marker: X.tag, markerRx: /LOTO/, path: 'logbook.html', reach: (R2, ms) => reachTeam(R2, X.tag, ms), rec: { table: 'logbook', id } };
  },
  2: async (X) => {   // the machine's history says it was locked out, under which permit
    const e = X.rec.entry || {};
    return { act: { ok: !!e.node, detail: `the lock-out logged at hand-off 1 on ${e.machine}` },
      marker: X.tag, markerRx: /locked out/i, path: e.node ? `asset-hub.html?node_id=${e.node}` : 'asset-hub.html', rec: { table: 'v_logbook_truth', id: e.id } };
  },
  3: async (X) => {   // the trail an inspector reads keeps the isolation and the permit
    const e = X.rec.entry || {};
    const aid = psql(`select id from hive_audit_log where hive_id = '${HIVE_ID}' and action = 'create_logbook_entry' and target_id = '${q(e.id || '')}' order by created_at desc limit 1`);
    return { act: { ok: !!aid, detail: `the entry's line in the hive's trail: ${aid || 'NO ROW'}` },
      marker: X.rec.permit, markerRx: /LOTO|lock/i, path: 'audit-log.html', reach: auditReach(aid, X.rec.permit), rec: { table: 'hive_audit_log', id: aid } };
  },
  4: async (X) => {   // the incident is one more safety-risk failure in the report
    const b = X.rec.before || {};
    return { act: { ok: b.safety != null, detail: `the report's engine before the worker logged: ${b.safety ?? 'unread'} failures classified as a safety risk` },
      marker: null, path: 'analytics-report.html', prepare: generateReport,
      figure: async (R) => {
        const line = await R.page.evaluate(() => ((document.body.innerText || '').match(/(\d+) failures classified as a safety risk/) || [])[0] || null).catch(() => null);
        const v = line ? Number(line.match(/\d+/)[0]) : null;
        const ok = v != null && b.safety != null && v === b.safety + 1;
        return { ok, said: line, before: b.safety ?? null,
          ...(ok ? {} : { why: v == null ? 'the report states no safety-risk count' : `the report says ${v}; before the worker's lock-out job the engine said ${b.safety}` }) };
      },
      rec: { table: 'v_logbook_truth', id: (X.rec.entry || {}).id } };
  },
};

// ── J14 · leaving: the supervisor removes a member, and what remains is honest to both
RECIPES.J14 = {
  1: async (X) => {   // the leaver's own job first, then the removal: the leaver reads who, when, and what stays theirs
    const { s, l } = X.S;
    X.rec.permit = `PTW-${X.tag.slice(-7)}`;
    await go(l, 'logbook.html');
    const r = await logWizard(l.page, H(l.page), { tag: X.tag, problem: 'gearbox oil top-up, sight glass cracked', beforeSave: lotoBeforeSave(X.rec.permit) });
    const row = psql(`select id || '|' || machine || '|' || coalesce(asset_node_id::text,'') from logbook where problem like '${q(X.tag)}%' and hive_id = '${HIVE_ID}' order by created_at limit 1`);
    const [id, machine, node] = row ? row.split('|') : [];
    X.rec.entry = { id, machine, node };
    const removed = await removeMember(X, s, l);
    const mrow = psql(`select id || '|' || status || '|' || coalesce(removed_by,'') || '|' || coalesce(removed_at::text,'') from hive_members where hive_id = '${HIVE_ID}' and auth_uid = '${l.m.uid}'`);
    const [mid, st, by, at] = mrow ? mrow.split('|') : [];
    X.rec.member = mid;
    return { act: { ok: !!id && removed && st === 'kicked' && by === s.m.name,
      detail: `${l.m.name} logged ${id || 'NO ROW'} (${r.toast || 'no toast'}); Remove on the roster as ${s.m.name}: status ${st}, removed_by ${by || '(none)'} at ${at || '(none)'}` },
      marker: 'removed from', markerRx: /stay yours|still yours/i, path: 'hive.html',
      rec: { table: 'hive_members', id: mid, where: `and status = 'kicked'` } };
  },
  2: async (X) => {   // the leaver's entries stay in the supervisor's logbook, still theirs
    const e = X.rec.entry || {};
    return { act: { ok: !!e.id, detail: `${X.S.l.m.name}'s entry, logged before the removal` },
      marker: X.tag, path: 'logbook.html', reach: (R2, ms) => reachTeam(R2, X.tag, ms), rec: { table: 'logbook', id: e.id } };
  },
  3: async (X) => {   // the trail keeps the leaver's work under their name
    const e = X.rec.entry || {};
    const aid = psql(`select id from hive_audit_log where hive_id = '${HIVE_ID}' and action = 'create_logbook_entry' and target_id = '${q(e.id || '')}' order by created_at desc limit 1`);
    return { act: { ok: !!aid, detail: `the line the trail kept for ${X.S.l.m.name}'s entry: ${aid || 'NO ROW'}` },
      marker: X.rec.permit, path: 'audit-log.html', reach: auditReach(aid, X.rec.permit), rec: { table: 'hive_audit_log', id: aid } };
  },
  4: async (X) => {   // the leaver's own achievements stay theirs: the XP their job earned is on their page
    const { l } = X.S;
    const xp = psql(`select count(*) || '|' || coalesce(sum(xp_earned),0) from achievement_xp_log where worker_name = '${q(l.m.name)}' and earned_at >= '${X.t0}'`);
    const [n, pts] = (xp || '0|0').split('|');
    return { act: { ok: Number(n) >= 1, detail: `${l.m.name}'s XP since the walk began: ${n} line(s), ${pts} XP` },
      marker: null, path: 'achievements.html',
      figure: async (R) => {
        // the newest XP row (the list opens with a "Last 7 days" head line, then one .activity-row per action, newest first)
        const first = await R.page.evaluate(() => { const c = document.querySelector('#recent-list .activity-row'); return c ? (c.innerText || '').replace(/\s+/g, ' ').trim() : null; }).catch(() => null);
        // the row prints its XP as its amount ("+20"), not the word: the line is the job's own when it carries the points
        // the walk's job earned and a time from today
        const ok = !!first && new RegExp('\\+' + Number(pts) + '\\b').test(first) && /just now|ago|today|\d{1,2}:\d{2}/i.test(first) && Number(n) >= 1;
        return { ok, said: first, ...(ok ? {} : { why: first ? 'the newest XP line is not the job logged before the removal' : 'no Recent XP line on the page' }) };
      },
      rec: { table: 'v_worker_achievements_truth', idCol: 'auth_uid', id: l.m.uid } };
  },
};

// ── G-LEAVE · a member removed: their open work reassigned, their history kept, the roster honest to all three
RECIPES['G-LEAVE'] = {
  1: (X) => RECIPES.J14[1](X),   // the leaver's open job, then the removal - read by the leaver
  2: async (X) => {   // the supervisor hands the departed member's open job to the remaining worker - pushed to them
    const { s, w } = X.S;
    const e = X.rec.entry || {};
    // the entry's view offers a supervisor a departed member's open job: "Close this job" / "Assign to a member"
    const seen = await reachTeam(s, X.tag, 15000);
    const opened = await s.page.evaluate((t) => {
      const card = [...document.querySelectorAll('#entries-list .entry-card, #entries-list [onclick*="openModal"], .entry-card')]
        .find((c) => (c.textContent || '').includes(t));
      if (!card) return false; (card.querySelector('[onclick*="openModal"]') || card).click(); return true;
    }, X.tag);
    await sleep(1200);
    const picked = await s.page.evaluate(() => { const b = [...document.querySelectorAll('#departed-actions button')].find((x) => /assign to a member/i.test(x.innerText || '')); if (b) { b.click(); return true; } return false; });
    await sleep(1500);
    await s.page.selectOption('#departed-assignee', w.m.name).catch(() => {});
    await s.page.evaluate(() => { const b = [...document.querySelectorAll('#departed-actions button')].find((x) => /^assign$/i.test((x.innerText || '').trim())); if (b) b.click(); });
    await sleep(2500);
    const toast = await s.page.evaluate(() => { const t = document.getElementById('toast-text'); return t ? t.textContent.trim() : ''; }).catch(() => '');
    const got = psql(`select coalesce(wo_assigned_to,'') || '|' || coalesce(wo_state,'') from logbook where id = '${q(e.id || '')}'`);
    const push = () => psql(`select count(*) from service_outbox where consumer = 'notify-push' and created_at >= '${X.t0}'
      and payload->'auth_uids' ? '${w.m.uid}' and payload->>'title' = 'Work order assigned to you' and payload->>'url' like '/logbook.html?status=Open%'`);
    const pushSaid = psql(`select coalesce(payload->>'title','') || ': ' || coalesce(payload->>'body','') from service_outbox
      where consumer = 'notify-push' and created_at >= '${X.t0}' and payload->'auth_uids' ? '${w.m.uid}' order by created_at desc limit 1`);
    return { act: { ok: !!seen && opened && picked && got.startsWith(w.m.name), detail: `the departed member's job, "Assign to a member" -> ${w.m.name} as ${s.m.name} (toast: ${toast || 'none'}): wo_assigned_to|wo_state = ${got}` },
      marker: X.tag, path: 'logbook.html?status=Open', channelSaid: pushSaid || null, rec: { table: 'logbook', id: e.id },
      F: () => { const n = Number(push()); return { ok: n >= 1 && got.startsWith(w.m.name),
        detail: `service_outbox notify-push to ${w.m.name} with /logbook.html?status=Open: ${n}; the entry reads assigned to ${got.split('|')[0] || 'nobody'}` }; } };
  },
  3: async (X) => {   // the leaver's job, as the one who carries it on reads it: still under the leaver's name
    const e = X.rec.entry || {};
    return { act: { ok: !!e.id, detail: `${X.S.l.m.name}'s job, now ${X.S.w.m.name}'s to carry on` },
      marker: X.tag, path: 'logbook.html?status=Open', rec: { table: 'logbook', id: e.id } };
  },
  4: async (X) => {   // the roster the remaining worker reads no longer lists the leaver
    const { s, l } = X.S;
    return { act: { ok: !!X.rec.member, detail: `${l.m.name} removed at hand-off 1 (member ${X.rec.member || 'unknown'})` },
      absent: { container: '#members-list', presentRx: new RegExp(reEsc(s.m.name.split(' ')[0]), 'i'), nameRx: new RegExp(reEsc(l.m.name), 'i') },
      path: 'hive.html',
      prepare: async (R) => { await R.page.evaluate(() => { const b = document.getElementById('btn-toggle-members'); if (b && b.getAttribute('aria-expanded') !== 'true') b.click(); }); await sleep(1500); },
      rec: { table: 'hive_members', id: X.rec.member, where: `and status = 'active'` } };
  },
};

// ── J19 · locked out and back to work: the supervisor lets the worker in without handing over a password for good
// (cast: w = Wilfredo Malabanan, returner, worker; s = Ramon Castillo, supervisor; Baguio Textile Mills)
// The walk's own fixtures, put back in cleanup: the worker's password returns to the seed's and the reset stamp is
// cleared (auth.users), so every later walk seats them as before.
const modalText = (P) => P.page.evaluate(() => {
  const ok = document.querySelector('[data-wh-modal-ok]');
  const card = ok && ok.parentElement && ok.parentElement.parentElement;
  return card ? (card.innerText || '').trim() : '';
}).catch(() => '');
async function modalFill(P, value, ms = 8000) {
  const inp = P.page.locator('[data-wh-modal-ok]').first().locator('xpath=../..').locator('input').first();
  try { await inp.waitFor({ state: 'visible', timeout: ms }); } catch (_) { return false; }
  await inp.fill(value);
  return modalOk(P);
}
async function modalCancel(P, ms = 5000) {
  const c = P.page.locator('[data-wh-modal-cancel]').first();
  try { await c.waitFor({ state: 'visible', timeout: ms }); } catch (_) { return false; }
  await c.click().catch(() => c.evaluate((el) => el.click()));
  await sleep(800);
  return true;
}
const tokenFor = async (user, pw) => {
  const r = await (await fetch(`${SB}/auth/v1/token?grant_type=password`, { method: 'POST',
    headers: { apikey: KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: `${user}@auth.workhiveph.com`, password: pw }) })).json().catch(() => ({}));
  return !!r.access_token;
};
// a member signed out on this device: the seat's own token is not put back (wh_gj_signedout, read by session())
async function signOutHere(P) {
  await P.page.evaluate(() => {
    try {
      localStorage.setItem('wh_gj_signedout', '1');
      ['sb-127-auth-token', 'wh_last_worker', 'wh_active_hive_id', 'wh_hive_name', 'wh_hive_role'].forEach((k) => localStorage.removeItem(k));
    } catch (_) { /* storage blocked */ }
  });
}

RECIPES.J19 = {
  1: async (X) => {   // the supervisor resets the worker's password; the worker signs in with it and is told to set their own
    const { s, w } = X.S;
    X.restores = [...(X.restores || []), [`${w.m.name}'s password back to the seed's, the reset stamp cleared`,
      `update auth.users set encrypted_password = extensions.crypt('test1234', extensions.gen_salt('bf')),
         raw_user_meta_data = coalesce(raw_user_meta_data, '{}'::jsonb) - 'password_reset_by' - 'password_reset_at'
       where id = '${w.m.uid}';`]];
    // the supervisor's own control: the roster's "Reset password" on the worker's row
    await go(s, 'hive.html');
    await s.page.evaluate(() => { const b = document.getElementById('btn-toggle-members'); if (b && b.getAttribute('aria-expanded') !== 'true') b.click(); });
    await sleep(1500);
    // the row's own "Reset PW" (its handler names the member: resetMemberPassword('<name>'))
    const pressed = await s.page.evaluate((nm) => {
      const b = [...document.querySelectorAll('button[onclick^="resetMemberPassword("]')].find((x) => (x.getAttribute('onclick') || '').includes(nm));
      if (b) { b.scrollIntoView({ block: 'center' }); b.click(); return true; } return false;
    }, w.m.name);
    const asked = pressed ? await modalOk(s) : false;            // "Reset <name>'s password?" -> Reset password
    let shown = '';
    for (let t = 0; t < 20000 && !/Temporary password for/i.test(shown); t += 1000) { await sleep(1000); shown = await modalText(s); }
    // the dialog's <p> collapses the message's newlines: "Temporary password for <name>: <pw> Give this to ..."
    const temp = ((shown.match(/Temporary password for [^:]+:\s*(\S+)\s+Give this/i) || [])[1] || '').trim();
    await modalOk(s);                                              // Done
    const stamp = psql(`select coalesce(raw_user_meta_data->>'password_reset_by','') || '|' || coalesce(raw_user_meta_data->>'password_reset_at','') from auth.users where id = '${w.m.uid}'`);
    X.rec.temp = temp;
    // the worker, signed out on their own device, signs in through the front door with what they were handed
    await signOutHere(w);
    await go(w, 'index.html');
    await w.page.evaluate(() => { if (typeof openSignIn === 'function') openSignIn(null, true); });
    await sleep(800);
    await w.page.fill('#si-username', w.m.user).catch(() => {});
    await w.page.fill('#si-password', temp).catch(() => {});
    await w.page.click('#si-btn').catch(() => w.page.evaluate(() => submitSignIn()));
    let told = '';
    for (let t = 0; t < 30000 && !/reset your password/i.test(told); t += 1000) { await sleep(1000); told = await modalText(w); }
    // the worker's own record of the reset is the stamp on their account, read with their OWN session (the trail is the
    // supervisor's: a worker cannot read hive_audit_log, by design)
    const wtok = await w.page.evaluate(() => { try { return JSON.parse(localStorage.getItem('sb-127-auth-token') || '{}').access_token || ''; } catch (_) { return ''; } });
    const me = wtok ? await (await fetch(`${SB}/auth/v1/user`, { headers: { apikey: KEY, Authorization: `Bearer ${wtok}` } })).json().catch(() => ({})) : {};
    const ownStamp = (me.user_metadata || {}).password_reset_by || '';
    // "Later": the notice above the day's verdict keeps saying it - the 3G reading below reads that
    await modalCancel(w);
    const audit = psql(`select id from hive_audit_log where action = 'supervisor_password_reset' and target_name = '${q(w.m.name)}'
      and created_at >= '${X.t0}' order by created_at desc limit 1`);
    X.rec.audit = audit;
    return { act: { ok: pressed && asked && temp.length >= 8 && stamp.startsWith(s.m.name + '|'),
        detail: `"Reset password" on ${w.m.name}'s roster row as ${s.m.name} (asked ${asked}); a ${temp.length}-character temporary password shown once; the account stamp reads ${stamp || 'nothing'}` },
      preRead: told ? { card: told } : null,
      marker: 'reset your password', markerRx: /set your own/i, path: 'index.html',
      rec: { table: 'hive_audit_log', id: audit },
      // F: the account itself carries who reset it (the stamp the page reads), and the reset is a trail line
      F: () => ({ ok: stamp.startsWith(s.m.name + '|') && !!audit,
        detail: `auth.users ${w.m.user} user_metadata.password_reset_by|_at = ${stamp || 'none'}; hive_audit_log supervisor_password_reset ${audit || 'MISSING'}` }),
      // I: the worker reads the reset on their own account; the supervisor reads it in the trail; another hive reads neither
      I: (witness) => {
        const supRows = audit ? Number(asUser(s.m.uid, `select count(*) from hive_audit_log where id = '${q(audit)}'`)) : 0;
        // the teeth fault "a foreign member let in" puts someone INSIDE the boundary in the witness's place: here the trail's
        // own reader, so a boundary that admitted them would read 1 row and fail
        const reader = X.faults.has('foreign-let-in') ? s.m : witness;
        const forRows = audit ? Number(asUser(reader.uid, `select count(*) from hive_audit_log where id = '${q(audit)}'`)) : -1;
        return { ok: ownStamp === s.m.name && supRows >= 1 && forRows === 0, worker_reads_own_stamp: ownStamp || null,
          supervisor_trail_rows: supRows, foreign: witness.user, foreign_rows: forRows };
      } };
  },
  2: async (X) => {   // the worker sets their own, and their open work is still theirs
    const { w } = X.S;
    await go(w, 'index.html');
    const box = await w.page.waitForSelector('#oh-pwreset-notice button', { timeout: 20000 }).catch(() => null);
    if (box) await box.click().catch(() => {});
    const mine = `GJ19-${Date.now().toString(36)}`;
    const a = await modalFill(w, mine);                            // the new password
    const b = a ? await modalFill(w, mine) : false;                // once more
    let said = '';
    for (let t = 0; t < 20000 && !/password changed/i.test(said); t += 1000) { await sleep(1000); said = await modalText(w); }
    await modalOk(w);
    const stamp = psql(`select coalesce(raw_user_meta_data->>'password_reset_by','') from auth.users where id = '${w.m.uid}'`);
    const newOk = await tokenFor(w.m.user, mine);
    const tempOk = X.rec.temp ? await tokenFor(w.m.user, X.rec.temp) : true;
    await sleep(500);
    const noticeGone = await (async () => { await go(w, 'index.html'); await sleep(2500); return !(await w.page.$('#oh-pwreset-notice')); })();
    // their open work, as they left it before the reset
    const job = psql(`select l.id || '|' || coalesce(l.machine, '') || '|' || coalesce(l.problem, '') from logbook l
      where l.hive_id = '${HIVE_ID}' and l.worker_name = '${q(w.m.name)}' and l.status = 'Open' order by l.created_at desc limit 1`);
    const [jid, jmach, jprob] = job.split('|');
    const untouched = jid ? psql(`select (updated_at < '${X.t0}')::text from logbook where id = '${q(jid)}'`) : '';
    return { act: { ok: !!box && a && b && /password changed/i.test(said) && stamp === '' && newOk && !tempOk && noticeGone,
        detail: `"Set my password" on the home notice: set (${said.replace(/\s+/g, ' ').slice(0, 80) || 'no answer'}); stamp now "${stamp}"; the new password signs in ${newOk}, the temporary one ${tempOk}; the notice gone on reload ${noticeGone}` },
      // whose it is, on the worker's own screen: the job sits under "My open jobs" (or carries their name)
      marker: (jmach || jprob || '').slice(0, 40) || null, whoRx: new RegExp('my open jobs|' + reEsc(w.m.name.split(' ')[0]), 'i'),
      path: 'logbook.html?status=Open',
      rec: { table: 'logbook', id: jid, where: `and worker_name = '${q(w.m.name)}' and status = 'Open'` },
      F: () => ({ ok: !!jid && untouched === 'true', detail: `${w.m.name}'s open entry ${jid || 'NONE'} still theirs, not written since the reset began: ${untouched}` }) };
  },
  3: async (X) => {   // the reset is in the trail with who did it - read by the supervisor
    const { s, w } = X.S;
    return { act: { ok: !!X.rec.audit, detail: `hive_audit_log ${X.rec.audit || 'MISSING'}: supervisor_password_reset of ${w.m.name} by ${s.m.name}` },
      marker: 'Reset member password', markerRx: new RegExp(reEsc(w.m.name.split(' ')[0]), 'i'),
      whoRx: new RegExp(reEsc(s.m.name.split(' ')[0]), 'i'), path: 'audit-log.html',
      rec: { table: 'hive_audit_log', id: X.rec.audit } };
  },
};

// ── J1 · onboard to first value: a hive is born, a colleague joins by its link, the first machine and entry are real
// (cast: n = a new person who will be the supervisor, i = a new person invited; both MINTED through the real sign-up form)
// Everything the walk makes is the walk's own and is removed after: the hive (and every row in it), the two accounts,
// their profiles, and anything else keyed on them - a re-count of each proves it.
function j1People(X) {
  if (X.rec.people) return X.rec.people;
  const stamp = Date.now().toString(36).slice(-6);
  const sfx = stamp.replace(/[0-9]/g, (d) => 'ABCDEFGHIJ'[Number(d)]).toUpperCase().slice(-3);
  X.rec.people = {
    pw: `Wh!${stamp}Qz9#`,
    n: { user: `gjn${stamp}`, name: `Lorna Villamor ${sfx}` },
    i: { user: `gji${stamp}`, name: `Dante Pascual ${sfx}` },
    // G-ONB's third person, the screen-reader joiner (minted the same way; cleaned up with the others)
    t: { user: `gjt${stamp}`, name: `Mila Ocampo ${sfx}` },
    // the hive is named WITHOUT the walk's tag: a page header carrying the hive's name would otherwise match the tag the
    // entry's reading looks for, before the entry's own card does
    hive: `Villamor Plant ${stamp}`,
  };
  const P = X.rec.people;
  // the cleanup is registered BEFORE anything is made, and resolves by name at cleanup time, so a walk that dies
  // halfway leaves nothing behind either
  const users = `('${q(P.n.user)}','${q(P.i.user)}','${q(P.t.user)}')`;
  const uids = `(select auth_uid from worker_profiles where username in ${users})`;
  const hive = `(select id from hives where name = '${q(P.hive)}')`;
  // ★A CASCADE DOES NOT REACH EVERY ROW (2026-11-06): 25 tables keep their rows with hive_id NULLED when a hive goes
  // (logbook, pm_completions, auth_session_events, ai_cost_log, ...) and 24 do the same for an account - a list of
  // named deletes would leave the walk's rows behind, unowned. The sweep reads those foreign keys from the catalog and
  // removes the walk's rows from each by the hive and by the two accounts, then the hive and the accounts themselves.
  X.restores = [...(X.restores || []), [`the walk's hive (${P.hive}) and its two new people, everything they wrote`,
    `DO $gj$
     DECLARE r record; h uuid; u uuid[]; pass int;
     BEGIN
       SELECT id INTO h FROM public.hives WHERE name = '${q(P.hive)}';
       SELECT array_agg(auth_uid) INTO u FROM public.worker_profiles WHERE username IN ${users};
       FOR pass IN 1..3 LOOP
         IF h IS NOT NULL THEN
           FOR r IN SELECT c.conrelid::regclass AS t, a.attname AS col FROM pg_constraint c
                      JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
                     WHERE c.confrelid = 'public.hives'::regclass AND c.contype = 'f' LOOP
             BEGIN EXECUTE format('DELETE FROM %s WHERE %I = %L', r.t, r.col, h); EXCEPTION WHEN others THEN NULL; END;
           END LOOP;
         END IF;
         IF u IS NOT NULL THEN
           FOR r IN SELECT c.conrelid::regclass AS t, a.attname AS col FROM pg_constraint c
                      JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
                     WHERE c.confrelid = 'auth.users'::regclass AND c.contype = 'f' AND c.conrelid <> 'public.worker_profiles'::regclass LOOP
             BEGIN EXECUTE format('DELETE FROM %s WHERE %I = ANY(%L::uuid[])', r.t, r.col, u); EXCEPTION WHEN others THEN NULL; END;
           END LOOP;
         END IF;
       END LOOP;
       IF h IS NOT NULL THEN DELETE FROM public.hives WHERE id = h; END IF;
       DELETE FROM public.achievement_xp_log WHERE worker_name IN ('${q(P.n.name)}', '${q(P.i.name)}', '${q(P.t.name)}');
       DELETE FROM public.early_access_emails WHERE lower(email) LIKE '${q(P.n.user)}%' OR lower(email) LIKE '${q(P.i.user)}%' OR lower(email) LIKE '${q(P.t.user)}%';
       IF u IS NOT NULL THEN
         DELETE FROM public.worker_profiles WHERE auth_uid = ANY(u);
         DELETE FROM auth.users WHERE id = ANY(u);
       END IF;
     END $gj$;`]];
  return P;
}
async function readClipboard(P) {
  return P.page.evaluate(() => navigator.clipboard.readText().catch(() => '')).catch(() => '');
}

RECIPES.J1 = {
  1: async (X) => {   // the new supervisor's invite link lands the new worker in the hive
    const { n, i } = X.S;
    const P = j1People(X);
    // n: signs up, then creates the hive
    const nUp = await signUpHere(n, P.n, P.pw);
    await go(n, 'hive.html');
    await n.page.evaluate(() => { const b = document.getElementById('btn-go-create'); if (b) b.click(); });
    await sleep(800);
    await n.page.fill('#hive-name-input', P.hive).catch(() => {});
    await n.page.evaluate(() => { const b = document.getElementById('btn-submit-create'); if (b) b.click(); });
    let code = '';
    for (let t = 0; t < 20000 && !/^[A-Z0-9]{6}$/.test(code); t += 1000) {
      await sleep(1000);
      code = await n.page.evaluate(() => (document.getElementById('code-value') || {}).textContent || '').catch(() => '');
      code = (code || '').trim();
    }
    const hid = psql(`select id from hives where name = '${q(P.hive)}'`);
    X.rec.hive = { id: hid, name: P.hive, code };   // (the link is kept below, for the next joiner)
    // the link, the way the supervisor sends it: "Copy invite link" on the screen that just showed the code
    await n.page.evaluate(() => { const b = document.getElementById('btn-copy-code-link'); if (b) b.click(); });
    await sleep(1200);
    const link = (await readClipboard(n)).trim();
    X.rec.link = link || `${ORIGIN}/hive.html?join=${code}`;
    // i: never signed up, opens the link - the wall, then "create a free account", then back to the link
    await i.page.goto(link || `${ORIGIN}/hive.html?join=${code}`, { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {});
    await sleep(4000);
    const wallSaid = await i.page.evaluate(() => { const r = document.getElementById('si-reason'); return r && !r.classList.contains('hidden') ? r.textContent.trim() : ''; }).catch(() => '');
    const iUp = await signUpHere(i, P.i, P.pw);
    let note = '';
    for (let t = 0; t < 20000 && !note; t += 1000) {
      await sleep(1000);
      note = await i.page.evaluate(() => { const e = document.getElementById('join-invite-note'); return e && !e.classList.contains('hidden') ? e.textContent.trim() : ''; }).catch(() => '');
    }
    const filled = await i.page.evaluate(() => (document.getElementById('join-code-input') || {}).value || '').catch(() => '');
    await i.page.evaluate(() => { const b = document.getElementById('btn-submit-join'); if (b) b.click(); });
    let welcome = '';
    for (let t = 0; t < 20000 && !/You're In/i.test(welcome); t += 1000) {
      await sleep(1000);
      welcome = await i.page.evaluate(() => { const v = document.getElementById('view-welcome'); return v && !v.classList.contains('hidden') ? v.innerText : ''; }).catch(() => '');
    }
    const mid = i.m.uid ? psql(`select id from hive_members where hive_id = '${q(hid)}' and auth_uid = '${i.m.uid}' and status = 'active'`) : '';
    X.rec.member = mid;
    return { act: { ok: nUp.ok && !!hid && /^[A-Z0-9]{6}$/.test(code) && /join=/.test(link) && iUp.ok && filled === code && !!mid,
        detail: `${P.n.name} signed up (${nUp.ok}${nUp.err ? ': ' + nUp.err : ''}) and created "${P.hive}" (code ${code || 'NONE'}); "Copy invite link" gave ${link || 'NOTHING'}; `
          + `${P.i.name}, signed out, opened it - the wall said "${wallSaid || 'nothing about an invite'}" - signed up (${iUp.ok}${iUp.err ? ': ' + iUp.err : ''}), `
          + `came back to the join form with the code filled in (${filled || 'empty'}; "${note || 'no invite line'}") and joined: membership ${mid || 'NONE'}` },
      preRead: welcome ? { card: welcome } : null,
      marker: P.hive, path: 'hive.html', rec: { table: 'hive_members', id: mid } };
  },
  2: async (X) => {   // the joiner is on the new supervisor's roster, with when they joined
    const { i } = X.S;
    // the ROSTER's row, not the smallest thing on the page bearing the name (the "on shift now" strip names them too)
    const rosterRow = async (R2, ms) => {
      await go(R2, 'hive.html');
      await R2.page.evaluate(() => { const b = document.getElementById('btn-toggle-members'); if (b && b.getAttribute('aria-expanded') !== 'true') b.click(); });
      for (let t = 0; t < ms; t += 500) {
        const card = await R2.page.evaluate((nm) => {
          const list = document.getElementById('members-list'); if (!list) return null;
          const row = [...list.querySelectorAll('div')].filter((d) => (d.innerText || '').includes(nm) && d.querySelector('[data-wh-joined], .text-sm'))
            .sort((a, b) => (a.innerText || '').length - (b.innerText || '').length)[0];
          return row ? row.innerText.trim() : null;
        }, i.m.name).catch(() => null);
        if (card) return { text: i.m.name, card };
        await sleep(500);
      }
      return null;
    };
    return { act: { ok: !!X.rec.member, detail: `${i.m.name} joined at hand-off 1 (membership ${X.rec.member || 'NONE'})` },
      marker: i.m.name, markerRx: /joined/i, path: 'hive.html', reach: rosterRow,
      rec: { table: 'hive_members', id: X.rec.member } };
  },
  3: async (X) => {   // the first machine the supervisor registered (and approved) is in the worker's list
    const { n } = X.S;
    const name = `${X.tag} air compressor`;
    const hid = (X.rec.hive || {}).id || '';
    // registered where a machine is registered - logbook's "Register Asset" - which in a hive lands for approval
    await go(n, 'logbook.html');
    await n.page.evaluate(() => { if (typeof openAssetModal === 'function') openAssetModal('register'); });
    await sleep(900);
    await n.page.fill('#a-asset-id', `CMP-${X.tag.slice(-4)}`).catch(() => {});
    await n.page.fill('#a-name', name).catch(() => {});
    await n.page.evaluate(() => { const sel = document.getElementById('a-type'); if (!sel) return; const o = [...sel.options].find((x) => x.value); if (o) { sel.value = o.value; sel.dispatchEvent(new Event('change', { bubbles: true })); } });
    await n.page.fill('#a-location', 'Compressor room').catch(() => {});
    await n.page.evaluate(() => { const b = document.getElementById('asset-submit-btn'); if (b) b.click(); });
    await sleep(3000);
    const before = psql(`select id || '|' || coalesce(status,'') from asset_nodes where hive_id = '${q(hid)}' and name = '${q(name)}' limit 1`);
    const nid = before ? before.split('|')[0] : '';
    const was = before ? before.split('|')[1] : '-';
    // ...and approved in asset-hub's queue, by the supervisor's own Approve
    await go(n, 'asset-hub.html');
    const pressed = nid ? await n.page.evaluate((id) => { const b = document.querySelector(`button[data-action="asset-approve"][data-id="${id}"]`); if (b) { b.scrollIntoView({ block: 'center' }); b.click(); return true; } return false; }, nid) : false;
    if (pressed) await modalOk(n, 3000);
    await sleep(2500);
    const st = nid ? psql(`select coalesce(status,'') from asset_nodes where id = '${q(nid)}'`) : '';
    X.rec.node = nid;
    return { act: { ok: !!nid && st === 'approved', detail: `"Register Asset" in logbook as ${n.m.name} -> asset_nodes ${nid || 'NO ROW'} (${was}); "Approve" in asset-hub (pressed ${pressed}) -> ${st || '-'}` },
      marker: name, path: 'asset-hub.html', rec: { table: 'asset_nodes', id: nid } };
  },
  4: async (X) => {   // the worker's first entry is in the supervisor's logbook
    const { i } = X.S;
    await go(i, 'logbook.html');
    const r = await logWizard(i.page, H(i.page), { tag: X.tag, maintType: 'Breakdown / Corrective', status: 'Open', problem: 'compressor tripping on high temperature' });
    const hid = (X.rec.hive || {}).id || '';
    const id = psql(`select id from logbook where problem like '${q(X.tag)}%' and hive_id = '${q(hid)}' order by created_at limit 1`);
    // an entry saved anywhere else says where (no hive, another hive) - the receipt explains itself
    const elsewhere = id ? '' : psql(`select coalesce(hive_id::text, 'no hive') || ' / ' || coalesce(machine, 'no machine') from logbook where problem like '${q(X.tag)}%' order by created_at limit 1`);
    X.rec.entry = { id };
    const where = id ? ` -> entry ${id}` : (elsewhere ? ` -> NOT in the hive (saved under ${elsewhere})` : ' -> NOT in the hive, and nowhere else');
    return { act: { ok: !!id, detail: `logbook wizard as ${i.m.name} (machine picked: ${r.machineSet}): ${r.toast || 'no toast'}${where}` },
      marker: X.tag, path: 'logbook.html', reach: (R2, ms) => reachTeam(R2, X.tag, ms), rec: { table: 'logbook', id } };
  },
  5: async (X) => {   // the first PM the supervisor set is the worker's
    const { n } = X.S;
    const name = `${X.tag} cooling pump`;
    await go(n, 'pm-scheduler.html');
    await n.page.evaluate(() => { const b = document.getElementById('tab-add'); if (b) b.click(); });
    await sleep(1500);
    await n.page.fill('#w-name', name).catch(() => {});
    await n.page.fill('#w-tag', `PMP-${X.tag.slice(-4)}`).catch(() => {});
    await n.page.fill('#w-location', 'Cooling tower').catch(() => {});
    const cat = await n.page.evaluate(() => {
      const sel = document.getElementById('w-category'); if (!sel) return null;
      const opt = [...sel.options].find((o) => o.value); if (!opt) return null;
      sel.value = opt.value; sel.dispatchEvent(new Event('change', { bubbles: true })); return opt.value;
    });
    await sleep(1500);
    for (const st of [2, 3]) { await n.page.evaluate((k) => { if (typeof goStep === 'function') goStep(k); }, st); await sleep(900); }
    const anchor = new Date(Date.now() + 8 * 3600e3 - 400 * 86400e3).toISOString().slice(0, 10);
    await n.page.evaluate((d) => { const a = document.getElementById('w-anchor'); if (a) { a.value = d; a.dispatchEvent(new Event('change', { bubbles: true })); } }, anchor);
    await n.page.evaluate(() => { if (typeof goStep === 'function') goStep(4); });
    await sleep(900);
    await n.page.evaluate(() => { const b = document.getElementById('btn-save-asset'); if (b) b.click(); });
    await sleep(4000);
    const hid = (X.rec.hive || {}).id || '';
    const row = psql(`select a.id || '|' || (select count(*) from pm_scope_items p where p.asset_id = a.id) from pm_assets a
      where a.hive_id = '${q(hid)}' and a.asset_name = '${q(name)}' and a.deleted_at is null limit 1`);
    const pm = row ? row.split('|')[0] : '';
    const ntasks = row ? row.split('|')[1] : '0';
    return { act: { ok: !!pm && Number(ntasks) > 0, detail: `PM Scheduler's Add Asset as ${n.m.name}: category ${cat || 'none'}, anchor ${anchor} -> pm_assets ${pm || 'NO ROW'} with ${ntasks} task(s)` },
      marker: name, path: 'pm-scheduler.html', reach: (R2, ms) => findPmAsset(R2, name, ms), rec: { table: 'pm_assets', id: pm } };
  },
};

// ── J31 · the portable portfolio: what the worker chose to share, read by a stranger, and nothing more
// (cast: w = the worker who shares, x = a stranger with no account - a signed-out browser that READS)
const anonGet = async (path) => {
  const res = await fetch(`${SB}/rest/v1/${path}`, { headers: { apikey: KEY } }).catch(() => null);
  if (!res) return { status: 0, rows: null };
  const body = await res.json().catch(() => null);
  return { status: res.status, rows: Array.isArray(body) ? body : null, body };
};
RECIPES.J31 = {
  1: async (X) => {   // the shared post shows only what the owner chose - nothing of the hive, nothing private
    const { w } = X.S;
    const post = psql(`select id || '|' || left(regexp_replace(content, '\\s+', ' ', 'g'), 40) from community_posts
      where auth_uid = '${w.m.uid}' and public and not flagged and deleted_at is null order by created_at desc limit 1`);
    const pid = post ? post.split('|')[0] : '';
    const words = post ? post.split('|').slice(1).join('|').trim() : '';
    // the worker reaches their own post in the feed and copies its public link from the post's own menu
    await go(w, 'community.html');
    for (let k = 0; k < 14; k++) {
      const drawn = await w.page.evaluate((id) => !!document.getElementById('post-' + id), pid);
      if (drawn) break;
      await w.page.evaluate(() => window.scrollBy(0, Math.round(window.innerHeight * 0.9)));
      await sleep(600);
    }
    await w.page.evaluate((id) => { const c = document.getElementById('post-' + id); if (c) c.scrollIntoView({ block: 'center' }); }, pid);
    await sleep(400);
    const opened = await w.page.evaluate((id) => {
      const card = document.getElementById('post-' + id);
      const b = card && card.querySelector('button[aria-haspopup="menu"]');
      if (!b) return false; b.click(); return true;
    }, pid);
    await sleep(600);
    const tapped = opened ? await w.page.evaluate(() => {
      const it = [...document.querySelectorAll('[role="menuitem"]')].find((b) => /copy public link/i.test(b.innerText || '') && b.checkVisibility && b.checkVisibility());
      if (it) { it.click(); return true; } return false;
    }) : false;
    await sleep(1200);
    const link = (await readClipboard(w)).trim();
    X.rec.post = { id: pid, words };
    // F and I, as the stranger: the post through the public read, and nothing behind it
    const pub = await anonGet(`v_community_posts_truth?id=eq.${pid}&public=eq.true&flagged=eq.false&deleted_at=is.null&select=id,author_name,content,category,created_at`);
    const hidden = await anonGet(`v_community_posts_truth?id=eq.${pid}&select=hive_id,auth_uid`);
    const priv = psql(`select id from community_posts where auth_uid = '${w.m.uid}' and not public and deleted_at is null limit 1`);
    const privRead = priv ? await anonGet(`v_community_posts_truth?id=eq.${priv}&select=id`) : { rows: [] };
    const hiddenLeak = (hidden.rows || []).some((r) => r.hive_id || r.auth_uid);
    return { act: { ok: !!pid && tapped && new RegExp(`public-feed\\.html\\?post=${pid}`).test(link),
        detail: `${w.m.name}'s public post ${pid || 'NONE'}, its menu's "Copy public link" (menu ${opened}, item ${tapped}) gave ${link || 'NOTHING'}` },
      reach: async (R2, ms) => {
        await R2.page.goto(link || `${ORIGIN}/public-feed.html?post=${pid}`, { waitUntil: 'domcontentloaded', timeout: R2.gotoTimeout || 60000 });
        await sleep(4000);
        // the post the link opened, first and labelled - not the same words found further down the feed
        for (let t = 0; t < ms; t += 500) {
          const card = await R2.page.evaluate(() => { const b = document.getElementById('shared-post'); const c = b && b.querySelector('.post-card'); return c ? (b.innerText || '').trim() : null; }).catch(() => null);
          if (card) return { text: card, card };
          await sleep(500);
        }
        return null;
      },
      marker: words.slice(0, 30), path: `public-feed.html?post=${pid}`,
      // nothing of the hive on a stranger's screen
      mustNotSay: new RegExp(reEsc(HOME), 'i'),
      rec: { table: 'v_community_posts_truth', id: pid },
      F: () => ({ ok: (pub.rows || []).length === 1, detail: `as a stranger (anon key, no session) the public read of post ${pid}: ${(pub.rows || []).length} row(s), columns ${pub.rows && pub.rows[0] ? Object.keys(pub.rows[0]).join(',') : '-'}` }),
      I: () => ({ ok: !hiddenLeak && ((privRead.rows || []).length === 0), stranger_reads_hive_or_account: hiddenLeak,
        hidden_read_status: hidden.status, private_post_rows: (privRead.rows || []).length, private_post: priv || null }) };
  },
  2: async (X) => {   // the public profile a stranger reads
    const { w } = X.S;
    const pub = await anonGet(`v_marketplace_sellers_public?worker_name=eq.${encodeURIComponent(w.m.name)}&select=worker_name`);
    // ★THE BOUNDARY IS THE CONTACT, NOT THE ROW (2026-11-06): a stranger may read a seller who has a published listing - a
    // public marketplace shows who sells (policy mkt_sellers_read_anon). What they must never read is the contact the
    // public view masks; the first walk found the table handing it over underneath the view (fixed: mig 20261106000002)
    const contact = await anonGet(`marketplace_sellers?worker_name=eq.${encodeURIComponent(w.m.name)}&select=messenger_username`);
    const viewContact = await anonGet(`v_marketplace_sellers_public?worker_name=eq.${encodeURIComponent(w.m.name)}&select=messenger_username`);
    const contactLeaks = (contact.rows || []).some((r) => r.messenger_username) || (viewContact.rows || []).some((r) => r.messenger_username);
    const path = `marketplace-seller-profile.html?worker=${encodeURIComponent(w.m.name)}`;
    return { act: { ok: true, detail: `${w.m.name}'s seller profile, opened by its own link (${path})` },
      // a stranger is shown no join date (masked by design); what is dated on their screen is the seller's listings
      reach: async (R2, ms) => {
        await go(R2, path);
        for (let t = 0; t < ms; t += 500) {
          const card = await R2.page.evaluate((nm) => {
            const hero = document.getElementById('hero-name');
            if (!hero || !(hero.textContent || '').includes(nm)) return null;
            const head = (hero.closest('section, header, .card, div') || hero).innerText.trim();
            const listed = (document.body.innerText || '').split('\n').map((l) => l.trim()).find((l) => /^listed \d+\s*\w+ ago$|^listed (today|yesterday|just now)$/i.test(l)) || '';
            return head + (listed ? ' || newest listing: ' + listed : '');
          }, w.m.name).catch(() => null);
          if (card) return { text: w.m.name, card };
          await sleep(500);
        }
        return null;
      },
      marker: w.m.name, path,
      rec: { table: 'v_marketplace_sellers_public', idCol: 'worker_name', id: w.m.name },
      F: () => ({ ok: (pub.rows || []).length >= 1, detail: `as a stranger, the public profile read: ${(pub.rows || []).length} row(s)` }),
      I: () => ({ ok: !contactLeaks && contact.status !== 200, stranger_reads_contact: contactLeaks, table_contact_status: contact.status,
        view_contact: (viewContact.rows || []).map((r) => r.messenger_username) }) };
  },
};

// ── G-MOD · a post flagged and moderated: poster, flagger and supervisor each read what happened
// (cast: p = the worker who posted, f = the worker who reports it, s = the supervisor who decides)
async function gmodNews(R2, words, ms) {
  await go(R2, 'community.html');
  for (let t = 0; t < ms; t += 500) {
    const li = await R2.page.evaluate((w) => {
      const box = document.getElementById('mod-news');
      if (!box || box.hidden) return null;
      const it = [...box.querySelectorAll('li')].find((x) => (x.innerText || '').includes(w));
      return it ? it.innerText.trim() : null;
    }, words).catch(() => null);
    if (li) return { text: li, card: li };
    await sleep(500);
  }
  return null;
}
RECIPES['G-MOD'] = {
  1: async (X) => {   // the flag is in the supervisor's moderation queue - who reported it, when, why
    const { p, f } = X.S;
    const text = `${X.tag} selling my own spare bearings at half price, message me`;
    X.restores = [...(X.restores || []), ['the walk\'s post', `delete from community_posts where content like '${q(X.tag)}%';`]];
    // the poster's post: a fixture written with triggers off (no XP to clean), in the poster's own words and name
    const pid = psql(`set session_replication_role = replica;
      insert into community_posts (hive_id, author_name, auth_uid, content, category)
      values ('${HIVE_ID}', '${q(p.m.name)}', '${p.m.uid}', '${q(text)}', 'general') returning id;`)
      .split('\n').find((l) => /^[0-9a-f-]{36}$/.test(l.trim())) || null;
    X.rec.post = { id: pid, words: text.slice(0, 40) };
    await go(f, 'community.html');
    for (let k = 0; k < 12; k++) {
      if (await f.page.evaluate((id) => !!document.getElementById('post-' + id), pid)) break;
      await f.page.evaluate(() => window.scrollBy(0, Math.round(window.innerHeight * 0.9)));
      await sleep(600);
    }
    await f.page.evaluate((id) => { const c = document.getElementById('post-' + id); if (c) c.scrollIntoView({ block: 'center' }); }, pid);
    await sleep(400);
    const viaMenu = await f.page.evaluate((id) => {
      const card = document.getElementById('post-' + id);
      const b = card && card.querySelector('button[aria-haspopup="menu"]');
      if (!b) return false; b.click(); return true;
    }, pid);
    await sleep(600);
    const tapped = viaMenu ? await f.page.evaluate(() => {
      const it = [...document.querySelectorAll('[role="menuitem"]')].find((b) => /report this post/i.test(b.innerText || '') && b.checkVisibility && b.checkVisibility());
      if (it) { it.click(); return true; } return false;
    }) : false;
    await sleep(900);
    await f.page.selectOption('#report-reason', 'spam').catch(() => {});
    await f.page.fill('#report-details', 'Personal sales in the plant feed').catch(() => {});
    await f.page.evaluate(() => { const b = document.getElementById('btn-submit-report'); if (b) b.click(); });
    await sleep(3000);
    const flagged = psql(`select flagged from community_posts where id = '${q(pid)}'`);
    const acct = psql(`select count(*) from hive_audit_log where action = 'report_post' and target_id = '${q(pid)}' and meta->>'actor_auth_uid' = '${f.m.uid}'`);
    return { act: { ok: flagged === 't' && tapped && Number(acct) >= 1,
        detail: `"Report this post" on ${p.m.name}'s post as ${f.m.name} (reason spam): flagged = ${flagged}; the report's trail line carries the reporter's account: ${acct}` },
      marker: X.tag, markerRx: /Reported by/i, path: 'community.html',
      reach: async (R2, ms) => {
        await go(R2, 'community.html');
        await R2.page.evaluate(() => { const t = document.getElementById('tab-mod'); if (t) t.click(); });
        await sleep(1500);
        return findText(R2, X.tag, ms);
      },
      rec: { table: 'community_posts', id: pid, where: 'and flagged' } };
  },
  2: async (X) => {   // the supervisor removes it, with a reason - and the poster reads what was done to their post
    const { s, p } = X.S;
    const post = X.rec.post || {};
    const reason = 'Personal sales are not allowed in the plant feed';
    await go(s, 'community.html');
    await s.page.evaluate(() => { const t = document.getElementById('tab-mod'); if (t) t.click(); });
    await sleep(1500);
    const opened = await s.page.evaluate((id) => {
      const card = document.getElementById('post-' + id);
      if (card) card.scrollIntoView({ block: 'center' });
      const b = card && card.querySelector('button[aria-haspopup="menu"]');
      if (!b) return false; b.click(); return true;
    }, post.id);
    await sleep(600);
    const tapped = opened ? await s.page.evaluate(() => {
      const it = [...document.querySelectorAll('[role="menuitem"]')].find((b) => /^remove post$/i.test((b.innerText || '').trim()) && b.checkVisibility && b.checkVisibility());
      if (it) { it.click(); return true; } return false;
    }) : false;
    const asked = tapped ? await modalFill(s, reason) : false;
    await sleep(3000);
    const row = psql(`select coalesce(moderation_outcome,'') || '|' || coalesce(moderated_by,'') || '|' || (deleted_at is not null)::text from community_posts where id = '${q(post.id)}'`);
    const [outcome, by, gone] = (row || '||').split('|');
    const pushP = () => psql(`select count(*) from service_outbox where created_at >= '${X.t0}' and payload->'auth_uids' ? '${p.m.uid}' and payload->>'title' = 'Your post was removed'`);
    const pushSaid = psql(`select coalesce(payload->>'title','') || ': ' || coalesce(payload->>'body','') from service_outbox
      where created_at >= '${X.t0}' and payload->'auth_uids' ? '${p.m.uid}' and payload->>'title' = 'Your post was removed' order by created_at desc limit 1`);
    return { act: { ok: tapped && asked && outcome === 'removed' && by === s.m.name && /^t(rue)?$/.test(gone || ''),
        detail: `the post's menu "Remove post" in the Mod Queue as ${s.m.name}, reason "${reason}": outcome ${outcome || '-'} by ${by || '-'}, in Recently deleted ${gone}` },
      marker: post.words, path: 'community.html', reach: (R2, ms) => gmodNews(R2, post.words, ms), channelSaid: pushSaid || null,
      rec: { table: 'community_posts', id: post.id },
      // the poster's record of it: the push, and what they read back (their own removed post is no longer theirs to read)
      F: () => {
        const n = Number(pushP());
        const back = asUser(p.m.uid, `select coalesce(outcome,'') || '|' || coalesce(note,'') from public.my_moderation_news() where kind = 'your_post' and post_id = '${q(post.id)}'`);
        return { ok: n >= 1 && back.startsWith('removed|') && back.includes(reason), detail: `push "Your post was removed" to ${p.m.name}: ${n}; my_moderation_news as ${p.m.name}: ${back || 'nothing'}` };
      },
      I: (witness) => {
        const mine = asUser(p.m.uid, `select count(*) from public.my_moderation_news() where post_id = '${q(post.id)}'`);
        const theirs = asUser(witness.uid, `select count(*) from public.my_moderation_news() where post_id = '${q(post.id)}'`);
        return { ok: Number(mine) >= 1 && Number(theirs) === 0, receiver_rows: Number(mine), foreign: witness.user, foreign_rows: Number(theirs) };
      } };
  },
  3: async (X) => {   // the person who reported it reads the outcome of their report
    const { f } = X.S;
    const post = X.rec.post || {};
    const pushF = () => psql(`select count(*) from service_outbox where created_at >= '${X.t0}' and payload->'auth_uids' ? '${f.m.uid}' and payload->>'title' = 'Your report was reviewed'`);
    const pushSaid = psql(`select coalesce(payload->>'title','') || ': ' || coalesce(payload->>'body','') from service_outbox
      where created_at >= '${X.t0}' and payload->'auth_uids' ? '${f.m.uid}' and payload->>'title' = 'Your report was reviewed' order by created_at desc limit 1`);
    return { act: { ok: !!post.id, detail: `the decision at hand-off 2 on the post ${f.m.name} reported` },
      marker: post.words, markerRx: /your report/i, path: 'community.html', reach: (R2, ms) => gmodNews(R2, post.words, ms), channelSaid: pushSaid || null,
      rec: { table: 'community_posts', id: post.id },
      F: () => {
        const n = Number(pushF());
        const back = asUser(f.m.uid, `select coalesce(outcome,'') || '|' || coalesce(moderated_by,'') from public.my_moderation_news() where kind = 'your_report' and post_id = '${q(post.id)}'`);
        return { ok: n >= 1 && back.startsWith('removed|'), detail: `push "Your report was reviewed" to ${f.m.name}: ${n}; my_moderation_news as ${f.m.name}: ${back || 'nothing'}` };
      },
      I: (witness) => {
        const theirs = asUser(witness.uid, `select count(*) from public.my_moderation_news() where post_id = '${q(post.id)}'`);
        return { ok: Number(theirs) === 0, foreign: witness.user, foreign_rows: Number(theirs) };
      } };
  },
};

// ── G-ONB · a hive born and joined: each joiner's first screen is the hive, not the landing
// (cast: n = the new supervisor, i = the first joiner, t = a screen-reader joiner - all three MINTED; J1's machinery)
// every visible control on the screen with no accessible name (what a screen reader would say nothing for)
async function unnamedControls(P) {
  return P.page.evaluate(() => {
    // ★A CLOSED SHEET IS NOT ON THE SCREEN (2026-11-06, the first G-ONB walk): the nav hub's closed sheet is
    // visibility:hidden, and checkVisibility() without options calls it visible - its eight tiles read as "unnamed"
    // because innerText of hidden text is empty. Visibility and opacity are asked for, as a screen reader meets them.
    const vis = (e) => e.checkVisibility && e.checkVisibility({ visibilityProperty: true, checkVisibilityCSS: true, opacityProperty: true, checkOpacity: true });
    const nameOf = (e) => {
      const al = e.getAttribute('aria-label'); if (al && al.trim()) return al.trim();
      const lb = e.getAttribute('aria-labelledby');
      if (lb) { const t = lb.split(/\s+/).map((id) => (document.getElementById(id) || {}).textContent || '').join(' ').trim(); if (t) return t; }
      if (e.id) { const l = document.querySelector(`label[for="${e.id}"]`); if (l && l.textContent.trim()) return l.textContent.trim(); }
      const wrap = e.closest('label'); if (wrap && wrap.textContent.trim()) return wrap.textContent.trim();
      // a button or link - native, or by role (a provenance figure is role=button) - is named by its own content
      if ((/^(BUTTON|A|SUMMARY)$/.test(e.tagName) || /^(button|link|tab|menuitem)$/.test(e.getAttribute('role') || '')) && (e.textContent || '').trim()) return e.textContent.trim();
      const ti = e.getAttribute('title'); if (ti && ti.trim()) return ti.trim();
      if (e.tagName === 'INPUT' && e.placeholder) return null;   // a placeholder is not a name
      return null;
    };
    return [...document.querySelectorAll('button, a[href], input:not([type="hidden"]), select, textarea, [role="button"], [tabindex]:not([tabindex="-1"])')]
      .filter(vis).filter((e) => !nameOf(e)).map((e) => `${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''}${e.className && typeof e.className === 'string' ? '.' + e.className.split(/\s+/)[0] : ''}`).slice(0, 8);
  }).catch(() => ['(could not read the screen)']);
}
RECIPES['G-ONB'] = {
  1: (X) => RECIPES.J1[1](X),   // the invite lands the first joiner in the hive (J1's hand-off 1, the same people)
  2: async (X) => {   // the invite lands the screen-reader joiner in the hive, every control named
    const { t } = X.S;
    const P = j1People(X);
    const hid = (X.rec.hive || {}).id || '';
    await t.page.goto(X.rec.link || `${ORIGIN}/hive.html`, { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {});
    await sleep(4000);
    const up = await signUpHere(t, P.t, P.pw);
    let note = '';
    for (let k = 0; k < 20 && !note; k++) {
      await sleep(1000);
      note = await t.page.evaluate(() => { const e = document.getElementById('join-invite-note'); return e && !e.classList.contains('hidden') ? e.textContent.trim() : ''; }).catch(() => '');
    }
    // the landing as a screen reader meets it: every control named, and the focus already on the one that joins
    const unnamed = await unnamedControls(t);
    const focused = await t.page.evaluate(() => (document.activeElement && document.activeElement.id) || '').catch(() => '');
    await t.page.keyboard.press('Enter');
    let welcome = '';
    for (let k = 0; k < 20 && !/You're In/i.test(welcome); k++) {
      await sleep(1000);
      welcome = await t.page.evaluate(() => { const v = document.getElementById('view-welcome'); return v && !v.classList.contains('hidden') ? v.innerText : ''; }).catch(() => '');
    }
    const unnamedWelcome = welcome ? await unnamedControls(t) : ['(no welcome)'];
    const mid = t.m.uid ? psql(`select id from hive_members where hive_id = '${q(hid)}' and auth_uid = '${t.m.uid}' and status = 'active'`) : '';
    X.rec.memberT = mid;
    return { act: { ok: up.ok && !!mid && focused === 'btn-submit-join' && unnamed.length === 0 && unnamedWelcome.length === 0,
        detail: `${P.t.name}, signed out, opened the invite link, signed up (${up.ok}${up.err ? ': ' + up.err : ''}) and landed on the join form ("${note || 'no invite line'}"); `
          + `focus on ${focused || 'nothing'}; unnamed controls on the join form: ${unnamed.length ? unnamed.join(', ') : 'none'}; joined with Enter -> membership ${mid || 'NONE'}; `
          + `unnamed controls on the welcome: ${unnamedWelcome.length ? unnamedWelcome.join(', ') : 'none'}` },
      preRead: welcome ? { card: welcome } : null,
      marker: P.hive, path: 'hive.html', rec: { table: 'hive_members', id: mid } };
  },
  3: async (X) => {   // the joiners on the new supervisor's roster
    const r = await RECIPES.J1[2](X);
    const t = X.S.t;
    return { ...r, act: { ok: !!X.rec.member && !!X.rec.memberT, detail: `${X.S.i.m.name} and ${t.m.name} joined at hand-offs 1 and 2 (memberships ${X.rec.member || 'NONE'}, ${X.rec.memberT || 'NONE'})` } };
  },
  4: async (X) => {   // the screen-reader joiner's first entry is in the supervisor's logbook
    const { t } = X.S;
    // the hive's first machine (registered and approved by the supervisor, J1's hand-off 3), so the entry has one
    await RECIPES.J1[3](X);
    await go(t, 'logbook.html');
    const unnamed = await unnamedControls(t);
    const r = await logWizard(t.page, H(t.page), { tag: X.tag, maintType: 'Breakdown / Corrective', status: 'Open', problem: 'compressor tripping on high temperature' });
    const hid = (X.rec.hive || {}).id || '';
    const id = psql(`select id from logbook where problem like '${q(X.tag)}%' and hive_id = '${q(hid)}' order by created_at limit 1`);
    X.rec.entry = { id };
    return { act: { ok: !!id, detail: `logbook wizard as ${t.m.name} (machine picked: ${r.machineSet}): ${r.toast || 'no toast'}${id ? ` -> entry ${id}` : ' -> NOT in the hive'}; unnamed controls on the logbook: ${unnamed.length ? unnamed.join(', ') : 'none'}` },
      marker: X.tag, path: 'logbook.html', reach: (R2, ms) => reachTeam(R2, X.tag, ms), rec: { table: 'logbook', id } };
  },
};

// ── J7 · a question answered: the asker asks, a teammate answers, the asker chooses it, the answer earns its credit
// (cast: a = the worker who asks, r = the worker who answers)
async function openThreadAs(P, pid) {
  await go(P, `community.html?post=${pid}`);
  await sleep(1500);
  const open = await P.page.evaluate(() => { const o = document.getElementById('thread-overlay'); return !!(o && o.classList.contains('open')); }).catch(() => false);
  if (!open) await P.page.evaluate((id) => { if (typeof openThread === 'function') openThread(id); }, pid);
  await sleep(1500);
}
RECIPES.J7 = {
  1: async (X) => {   // the question reaches the answerer
    const { a, r } = X.S;
    // the XP totals the walk's post, reply and chosen answer move are the cast's own: put back exactly as they were
    const names = `('${q(a.m.name)}','${q(r.m.name)}')`;
    const wa = psql(`select coalesce(json_agg(row_to_json(t)), '[]') from worker_achievements t where worker_name in ${names}`);
    const cx = psql(`select coalesce(json_agg(row_to_json(t)), '[]') from community_xp t where worker_name in ${names}`);
    X.restores = [...(X.restores || []), ['the cast\'s XP totals put back', `begin;
      delete from worker_achievements where worker_name in ${names};
      insert into worker_achievements select * from json_populate_recordset(null::worker_achievements, '${q(wa)}');
      delete from community_xp where worker_name in ${names};
      insert into community_xp select * from json_populate_recordset(null::community_xp, '${q(cx)}');
      commit;`],
      ['the walk\'s XP ledgers', `delete from community_reply_xp_awards where post_id in (select id from community_posts where content like '${q(X.tag)}%');
      delete from community_post_xp_awards where post_id in (select id from community_posts where content like '${q(X.tag)}%');
      delete from community_reaction_xp_awards where post_id in (select id from community_posts where content like '${q(X.tag)}%');`]];
    await go(a, 'community.html');
    await a.page.evaluate(() => { if (typeof openComposer === 'function') openComposer(); });
    await sleep(1000);
    const text = `${X.tag} how do you align a coupling without a laser kit?`;
    await a.page.fill('#post-content', text).catch(() => {});
    await a.page.selectOption('#post-category', 'technical').catch(() => {});
    await a.page.evaluate(() => { const b = document.getElementById('btn-submit-post'); if (b) b.click(); });
    await sleep(3500);
    const pid = psql(`select id from community_posts where hive_id = '${HIVE_ID}' and content like '${q(X.tag)}%' order by created_at desc limit 1`);
    X.rec.post = { id: pid, text };
    return { act: { ok: !!pid, detail: `"Post to Hive" (Technical) as ${a.m.name}: community_posts ${pid || 'NO ROW'}` },
      marker: X.tag, path: 'community.html', rec: { table: 'community_posts', id: pid } };
  },
  2: async (X) => {   // the answer is pushed to the asker
    const { a, r } = X.S;
    const post = X.rec.post || {};
    await openThreadAs(r, post.id);
    const reply = `${X.tag} rim and face with two dial indicators, check sag first`;
    await r.page.fill('#reply-content', reply).catch(() => {});
    await r.page.evaluate(() => { const b = document.getElementById('btn-submit-reply'); if (b) b.click(); });
    await sleep(3500);
    const rid = psql(`select id from community_replies where post_id = '${q(post.id)}' and content like '${q(X.tag)}%' order by created_at desc limit 1`);
    X.rec.reply = { id: rid, text: reply };
    const push = () => psql(`select count(*) from service_outbox where created_at >= '${X.t0}' and payload->'auth_uids' ? '${a.m.uid}' and payload->>'title' like '%answered your question'`);
    const pushSaid = psql(`select coalesce(payload->>'title','') || ': ' || coalesce(payload->>'body','') from service_outbox
      where created_at >= '${X.t0}' and payload->'auth_uids' ? '${a.m.uid}' and payload->>'title' like '%answered your question' order by created_at desc limit 1`);
    return { act: { ok: !!rid, detail: `the thread's reply box as ${r.m.name}: community_replies ${rid || 'NO ROW'}` },
      marker: reply.slice(0, 40), path: `community.html?post=${post.id}`, channelSaid: pushSaid || null,
      reach: async (R2, ms) => { await openThreadAs(R2, post.id); return findText(R2, reply.slice(0, 40), ms); },
      rec: { table: 'community_replies', id: rid },
      F: () => { const n = Number(push()); return { ok: n >= 1, detail: `push "<answerer> answered your question" to ${a.m.name}: ${n}` }; } };
  },
  3: async (X) => {   // the accepted answer is told to the answerer
    const { a, r } = X.S;
    const post = X.rec.post || {};
    const rep = X.rec.reply || {};
    await openThreadAs(a, post.id);
    const marked = await a.page.evaluate((id) => {
      const b = [...document.querySelectorAll('button[onclick^="markAnswer("]')].find((x) => (x.getAttribute('onclick') || '').includes(id));
      if (b) { b.click(); return true; } return false;
    }, rep.id);
    await sleep(3000);
    const acc = psql(`select is_accepted::text || '|' || coalesce(accepted_by,'') from community_replies where id = '${q(rep.id)}'`);
    const push = () => psql(`select count(*) from service_outbox where created_at >= '${X.t0}' and payload->'auth_uids' ? '${r.m.uid}' and payload->>'title' = 'Your answer was chosen'`);
    const pushSaid = psql(`select coalesce(payload->>'title','') || ': ' || coalesce(payload->>'body','') from service_outbox
      where created_at >= '${X.t0}' and payload->'auth_uids' ? '${r.m.uid}' and payload->>'title' = 'Your answer was chosen' order by created_at desc limit 1`);
    return { act: { ok: marked && /^t(rue)?\|/.test(acc) && acc.endsWith('|' + a.m.name), detail: `"Best answer" on ${r.m.name}'s reply as ${a.m.name} (pressed ${marked}): is_accepted|accepted_by = ${acc}` },
      marker: rep.text.slice(0, 40), markerRx: /chosen by/i, path: `community.html?post=${post.id}`, channelSaid: pushSaid || null,
      reach: async (R2, ms) => { await openThreadAs(R2, post.id); return findText(R2, rep.text.slice(0, 40), ms); },
      rec: { table: 'community_replies', id: rep.id, where: 'and is_accepted' },
      F: () => { const n = Number(push()); return { ok: n >= 1, detail: `push "Your answer was chosen" to ${r.m.name}: ${n}` }; } };
  },
  4: async (X) => {   // the credit the accepted answer earned, on the answerer's achievements
    const { r } = X.S;
    const rep = X.rec.reply || {};
    const xp = psql(`select coalesce(sum(xp_earned), 0) from achievement_xp_log where source_action = 'best_answer' and source_id = '${q(rep.id)}' and reversed_at is null`);
    return { act: { ok: Number(xp) === 30, detail: `achievement_xp_log best_answer for ${r.m.name}'s chosen reply ${rep.id}: +${xp}` },
      marker: 'Your answer was chosen as the best', whoRx: /\+30\b/, path: 'achievements.html',
      rec: { table: 'v_achievement_xp_log', idCol: 'source_id', id: rep.id, where: `and source_action = 'best_answer'` } };
  },
};

// ── J25 · a new worker proves a skill and gets their first supervised job
// (cast: w = the new worker, s = the supervisor)
// ★RE-PREMISED ON THE PRODUCT'S REAL MODEL (2026-11-06): the census said "the skill the new worker proved is on the
// supervisor's team view" - but skill badges are PRIVATE to the worker who earned them (RLS auth_uid = auth.uid(); the
// skill matrix promises "not your supervisor or teammates"). Hand-off 1 walks that promise: the badge is earned, and the
// supervisor's view of the worker says it is kept private (it said "No badges yet" until 2026-11-06). Making a badge
// shareable with a supervisor is Ian's decision, not a walk's.
async function openProfileFromTeam(P, name, uid) {
  await go(P, 'hive.html');
  const tapped = await P.page.evaluate((nm) => {
    const chip = [...document.querySelectorAll('.presence-chip')].find((c) => (c.getAttribute('onclick') || '').includes(nm));
    if (chip) { chip.click(); return true; } return false;
  }, name).catch(() => false);
  if (!tapped) await P.page.evaluate(([nm, id]) => { if (typeof _openWorkerProfileDrawer === 'function') _openWorkerProfileDrawer(nm, id); }, [name, uid]);
  await sleep(2500);
  return tapped;
}
RECIPES.J25 = {
  1: async (X) => {   // the skill the new worker proved is theirs: the supervisor's view of them says it is kept private
    const { w, s } = X.S;
    X.restores = [...(X.restores || []), ['the walk\'s exam and badge', `delete from skill_badges where auth_uid = '${w.m.uid}' and earned_at >= '${X.t0}';
      delete from skill_exam_attempts where auth_uid = '${w.m.uid}' and attempted_at >= '${X.t0}';`]];
    await go(w, 'skillmatrix.html');
    await w.page.evaluate(() => { if (typeof openLesson === 'function') openLesson('Electrical', 1); });
    await sleep(900);
    // the lesson is read to its end first: "Take Exam" stays disabled until the lesson has been scrolled through (a tall
    // screen shows it whole at once; a phone has to scroll - the first J25 walk at 390 never reached the exam)
    for (let k = 0; k < 12; k++) {
      const done = await w.page.evaluate(() => {
        const sc = document.getElementById('lesson-body-scroll'); const b = document.getElementById('lesson-exam-btn');
        if (!sc || !b) return true;
        if (!b.disabled) return true;
        sc.scrollTop = Math.min(sc.scrollHeight, sc.scrollTop + Math.round(sc.clientHeight * 0.9));
        sc.dispatchEvent(new Event('scroll'));
        return false;
      }).catch(() => true);
      if (done) break;
      await sleep(250);
    }
    await w.page.evaluate(() => { const b = document.getElementById('lesson-exam-btn'); if (b) b.click(); });
    await sleep(900);
    // the worker answers each question (the page holds each question's answer for its instant score; the server grades)
    for (let k = 0; k < 10; k++) {
      await w.page.evaluate(() => {
        const qn = (typeof _examQuestions !== 'undefined' && typeof _currentQuestion !== 'undefined') ? _examQuestions[_currentQuestion] : null;
        const opts = document.querySelectorAll('.exam-option');
        if (qn && opts[qn.answer]) opts[qn.answer].click();
      }).catch(() => {});
      await sleep(250);
      await w.page.evaluate(() => { const b = document.getElementById('exam-next-btn'); if (b && !b.disabled) b.click(); }).catch(() => {});
      await sleep(350);
    }
    await sleep(3000);
    const said = await w.page.evaluate(() => (document.getElementById('result-msg') || {}).textContent || '').catch(() => '');
    const badge = psql(`select id from skill_badges where auth_uid = '${w.m.uid}' and discipline = 'Electrical' and level = 1 and earned_at >= '${X.t0}' limit 1`);
    X.rec.badge = badge;
    return { act: { ok: !!badge, detail: `the Electrical Level 1 exam on skillmatrix as ${w.m.name}: "${said.replace(/\s+/g, ' ').slice(0, 120)}" -> skill_badges ${badge || 'NONE'}` },
      // the supervisor opens the worker's profile from the team strip: the worker is there, the badge is not, and it
      // says the badges are private rather than that there are none
      absent: { container: '#wh-wp-panel', presentRx: new RegExp('Kept private by ' + reEsc(w.m.name.split(' ')[0]), 'i'), nameRx: /Electrical L\d/i },
      path: 'hive.html',
      prepare: async (R) => { await openProfileFromTeam(R, w.m.name, w.m.uid); },
      rec: { table: 'v_skill_badges_truth', id: badge } };
  },
  2: async (X) => {   // the supervisor's first supervised job is pushed to the new worker
    const { s, w } = X.S;
    // the supervisor logs the job, then - it is their OWN entry - hands it on through its edit form: "assigned", and the
    // member picked from the hive's list (a supervisor's "Move the work order" is for a teammate's entry)
    await go(s, 'logbook.html');
    const r = await logWizard(s.page, H(s.page), { tag: X.tag, maintType: 'Breakdown / Corrective', status: 'Open', problem: 'panel breaker tripping under load' });
    const [id, machine, node] = psql(`select id, machine, asset_node_id from logbook where problem like '${q(X.tag)}%' and hive_id = '${HIVE_ID}' order by created_at limit 1`).split('|');
    X.rec.entry = { id, machine, node };
    const opened = await openEdit(s, X.tag);
    await s.page.evaluate(() => { const b = document.getElementById('extras-toggle-btn'); if (b && b.getAttribute('aria-expanded') !== 'true') b.click(); });
    await sleep(400);
    await s.page.selectOption('#f-wo-state', 'assigned').catch(() => {});
    await s.page.evaluate(() => { const el = document.getElementById('f-wo-state'); if (el) el.dispatchEvent(new Event('change', { bubbles: true })); });
    await sleep(1200);
    const offered = await s.page.evaluate(() => [...document.querySelectorAll('#wo-assignee-options option')].map((o) => o.value)).catch(() => []);
    await s.page.fill('#f-wo-assigned-to', w.m.name).catch(() => {});
    await s.page.evaluate(() => { const b = document.getElementById('save-entry-btn'); if (b) b.click(); });
    await sleep(3500);
    const got = psql(`select coalesce(wo_assigned_to,'') || '|' || coalesce(wo_state,'') from logbook where id = '${q(id)}'`);
    const push = () => psql(`select count(*) from service_outbox where consumer = 'notify-push' and created_at >= '${X.t0}'
      and payload->'auth_uids' ? '${w.m.uid}' and payload->>'title' = 'Work order assigned to you'`);
    const pushSaid = psql(`select coalesce(payload->>'title','') || ': ' || coalesce(payload->>'body','') from service_outbox
      where consumer = 'notify-push' and created_at >= '${X.t0}' and payload->'auth_uids' ? '${w.m.uid}' and payload->>'title' = 'Work order assigned to you' order by created_at desc limit 1`);
    return { act: { ok: !!id && opened && got.startsWith(w.m.name + '|assigned') && offered.includes(w.m.name),
        detail: `logged by ${s.m.name} (${r.toast || 'no toast'}); its edit form: "assigned" to ${w.m.name}, picked from the ${offered.length} members offered -> wo_assigned_to|wo_state = ${got}` },
      marker: X.tag, path: 'logbook.html?status=Open', channelSaid: pushSaid || null, rec: { table: 'logbook', id },
      F: () => { const n = Number(push()); return { ok: n >= 1 && got.startsWith(w.m.name), detail: `push "Work order assigned to you" to ${w.m.name}: ${n}; the entry reads assigned to ${got.split('|')[0] || 'nobody'}` }; } };
  },
  3: async (X) => {   // the new worker's first job is in the supervisor's logbook
    const { w } = X.S;
    // its own tag, so it is never confused with the supervisor's job above (both would match the walk's tag)
    const tag2 = X.tag.replace(/^GJ-/, 'GW-');
    X.restores = [...(X.restores || []), ['the worker\'s entry', `delete from logbook where hive_id = '${HIVE_ID}' and problem like '${q(tag2)}%';`]];
    await go(w, 'logbook.html');
    const r = await logWizard(w.page, H(w.page), { tag: tag2, maintType: 'Breakdown / Corrective', status: 'Open', problem: 'motor bearing running hot' });
    const id = psql(`select id from logbook where problem like '${q(tag2)}%' and hive_id = '${HIVE_ID}' order by created_at limit 1`);
    return { act: { ok: !!id, detail: `logbook wizard as ${w.m.name}: ${r.toast || 'no toast'}${id ? ` -> entry ${id}` : ' -> NO ROW'}` },
      marker: tag2, path: 'logbook.html', reach: (R2, ms) => reachTeam(R2, tag2, ms), rec: { table: 'logbook', id } };
  },
};

// ── J5 · shortage to shelf: a part sourced from another hive, asked for, answered and reviewed
// (cast: b = the buyer, v = the seller; the seller's own published listing is what is walked to)
function j5Listing(X) {
  if (X.rec.listing) return X.rec.listing;
  const row = psql(`select id || '|' || title from marketplace_listings where seller_name = '${q(X.S.v.m.name)}' and status = 'published' order by created_at desc limit 1`);
  const [id, title] = row ? [row.split('|')[0], row.split('|').slice(1).join('|')] : ['', ''];
  // the seller's response stats move when they answer: their row is kept and put back exactly
  const sel = psql(`select coalesce(json_agg(row_to_json(t)), '[]') from marketplace_sellers t where worker_name = '${q(X.S.v.m.name)}'`);
  X.restores = [...(X.restores || []), ['the walk\'s inquiry and review', `delete from marketplace_inquiries where message like '${q(X.tag)}%';
      delete from marketplace_reviews where comment like '${q(X.tag)}%';`],
    ['the seller\'s stats put back', `begin; delete from marketplace_sellers where worker_name = '${q(X.S.v.m.name)}';
      insert into marketplace_sellers select * from json_populate_recordset(null::marketplace_sellers, '${q(sel)}'); commit;`]];
  return (X.rec.listing = { id, title });
}
// a listing is opened as a person opens it: found by its title in the search, then its card tapped
async function openListing(P, id, title) {
  await go(P, 'marketplace.html');
  if (title) {
    await P.page.fill('#search-input', title.split(/\s+/).slice(0, 3).join(' ')).catch(() => {});
    await P.page.keyboard.press('Enter').catch(() => {});
    await sleep(2000);
  }
  await P.page.evaluate((lid) => { const c = document.querySelector(`article.listing-card[data-id="${lid}"]`); if (c) { c.scrollIntoView({ block: 'center' }); c.click(); } }, id);
  await sleep(2000);
}
RECIPES.J5 = {
  1: async (X) => {   // the seller's listing is what the buyer finds
    const { b } = X.S;
    const L = j5Listing(X);
    await go(b, 'marketplace.html');
    const words = L.title.split(/\s+/).slice(0, 3).join(' ');
    await b.page.fill('#search-input', words).catch(() => {});
    await b.page.keyboard.press('Enter').catch(() => {});
    await sleep(2500);
    const found = await b.page.evaluate((id) => !!document.querySelector(`article.listing-card[data-id="${id}"]`), L.id).catch(() => false);
    // the marketplace is the platform's one cross-hive surface: a published listing is FOR other hives to find. Its
    // boundary is the seller's contact, which a stranger and another hive's member must not read off the table
    const contact = await anonGet(`marketplace_sellers?worker_name=eq.${encodeURIComponent(X.S.v.m.name)}&select=messenger_username`);
    return { act: { ok: !!L.id && found, detail: `${X.S.v.m.name}'s published listing "${L.title}" (${L.id || 'NONE'}); "${words}" in the marketplace search as ${b.m.name}: card shown ${found}` },
      marker: L.title, path: 'marketplace.html',
      reach: async (R2, ms) => {
        await go(R2, 'marketplace.html');
        await R2.page.fill('#search-input', words).catch(() => {});
        await R2.page.keyboard.press('Enter').catch(() => {});
        await sleep(2000);
        return findText(R2, L.title, ms);
      },
      rec: { table: 'v_marketplace_listings_public', id: L.id },
      I: (witness) => {
        const other = Number(asUser(witness.uid, `select count(*) from v_marketplace_listings_public where id = '${q(L.id)}'`));
        return { ok: other === 1 && contact.status !== 200, cross_hive_listing_rows: other, stranger_contact_status: contact.status,
          note: 'a published listing is cross-hive by design; the boundary read is the seller contact' };
      } };
  },
  2: async (X) => {   // the buyer's inquiry is in the seller's console
    const { b } = X.S;
    const L = j5Listing(X);
    await openListing(b, L.id, L.title);
    await b.page.evaluate(() => { const c = document.getElementById('btn-detail-contact'); if (c) c.click(); });
    await sleep(1500);
    const msg = `${X.tag} is the set of 8 still available? Need it for the boiler room this week.`;
    await b.page.fill('#inq-name', b.m.name).catch(() => {});
    await b.page.fill('#inq-contact', '0917 555 0142').catch(() => {});
    await b.page.fill('#inq-message', msg).catch(() => {});
    await b.page.evaluate(() => { const s = document.getElementById('btn-submit-inquiry'); if (s) s.click(); });
    await sleep(3000);
    const inq = psql(`select id from marketplace_inquiries where message like '${q(X.tag)}%' order by created_at desc limit 1`);
    X.rec.inq = inq;
    return { act: { ok: !!inq, detail: `"Contact seller" -> the inquiry form on "${L.title}" as ${b.m.name}: marketplace_inquiries ${inq || 'NO ROW'}` },
      marker: X.tag, path: 'marketplace-seller.html',
      reach: async (R2, ms) => {
        await go(R2, 'marketplace-seller.html');
        await R2.page.evaluate(() => { const t = document.getElementById('tab-inquiries'); if (t) t.click(); });
        await sleep(2000);
        return findText(R2, X.tag, ms);
      },
      rec: { table: 'v_marketplace_inquiries_truth', id: inq } };
  },
  3: async (X) => {   // the seller's answer is on the buyer's inquiry
    const { v } = X.S;
    const inq = X.rec.inq;
    await go(v, 'marketplace-seller.html');
    await v.page.evaluate(() => { const t = document.getElementById('tab-inquiries'); if (t) t.click(); });
    await sleep(2000);
    const reply = `${X.tag}-R yes, all 8 in stock, you can pick them up Friday morning`;
    await v.page.fill(`.reply-textarea[data-inq-id="${inq}"]`, reply).catch(() => {});
    await v.page.evaluate((id) => { const b = document.querySelector(`[data-action="reply"][data-id="${id}"]`); if (b) b.click(); }, inq);
    await sleep(3000);
    const got = psql(`select status || '|' || coalesce(reply_text,'') from marketplace_inquiries where id = '${q(inq)}'`);
    return { act: { ok: got.startsWith('replied|' + X.tag), detail: `"Send Reply" on the inquiry in the seller console as ${v.m.name}: ${got.slice(0, 90)}` },
      marker: reply.slice(0, 30), path: 'marketplace.html',
      reach: async (R2, ms) => { await go(R2, 'marketplace.html'); await sleep(1500); return findText(R2, reply.slice(0, 30), ms); },
      rec: { table: 'v_marketplace_inquiries_truth', id: inq } };
  },
  4: async (X) => {   // the buyer's review is on the seller's public profile
    const { b, v } = X.S;
    const L = j5Listing(X);
    await openListing(b, L.id, L.title);
    await b.page.evaluate(() => { const o = document.getElementById('btn-open-review'); if (o) o.click(); });
    await sleep(800);
    await b.page.selectOption('#review-rating', '5').catch(() => {});
    const comment = `${X.tag} quick reply and the cartridges were exactly as listed`;
    await b.page.fill('#review-comment', comment).catch(() => {});
    await b.page.evaluate(() => { const s = document.getElementById('btn-submit-review'); if (s) s.click(); });
    await sleep(3000);
    const rid = psql(`select id from marketplace_reviews where comment like '${q(X.tag)}%' order by created_at desc limit 1`);
    return { act: { ok: !!rid, detail: `"Write a review" (5 stars) on "${L.title}" as ${b.m.name}: marketplace_reviews ${rid || 'NO ROW'}` },
      marker: X.tag, path: `marketplace-seller-profile.html?worker=${encodeURIComponent(v.m.name)}`,
      rec: { table: 'marketplace_reviews', id: rid },
      // a review on a public seller profile is public by design (that is what a review is for); the boundary is the
      // reviewer's ACCOUNT, which a stranger must not read off the table
      I: (witness) => {
        const other = Number(asUser(witness.uid, `select count(*) from marketplace_reviews where id = '${q(rid)}'`));
        const acct = psql(`select has_column_privilege('anon', 'public.marketplace_reviews', 'reviewer_auth_uid', 'SELECT')::text`);
        return { ok: other === 1 && acct === 'false', other_hive_reads_the_public_review: other, stranger_may_read_reviewer_account: acct };
      } };
  },
};

// ── J12 / G-PUBLIC · stranger to member - RE-PREMISED ON THE PRODUCT'S REAL MODEL (2026-11-06)
// The census said "the newcomer's join REQUEST is on the supervisor's hive page" and "the supervisor's APPROVAL is the
// newcomer's first screen". A code join is ADMISSION: join_hive_by_code seats the member at once ("Anyone with this code
// can join your hive"); there is no request and no approval for people (the approval queue is for machines and parts).
// Walked as the product works: the supervisor's invite link; the newcomer's JOIN on the supervisor's roster, with when
// (mig 20261106000001); the newcomer's first screen is the hive, naming its supervisor. An approval gate for people would
// be Ian's product decision, not a walk's.
function newcomer(X, key, first, last) {
  X.rec.newcomers = X.rec.newcomers || {};
  if (X.rec.newcomers[key]) return X.rec.newcomers[key];
  const stamp = Date.now().toString(36).slice(-6);
  const sfx = stamp.replace(/[0-9]/g, (d) => 'ABCDEFGHIJ'[Number(d)]).toUpperCase().slice(-3);
  const who = { user: `gj${key}${stamp}`, name: `${first} ${last} ${sfx}`, pw: `Wh!${stamp}Nc7#` };
  // the newcomer joins a REAL hive, so the sweep is by their account only - never by the hive
  X.restores = [...(X.restores || []), [`the newcomer ${who.name}, everything they wrote`, `DO $gj$
     DECLARE r record; u uuid; pass int;
     BEGIN
       SELECT auth_uid INTO u FROM public.worker_profiles WHERE username = '${q(who.user)}';
       IF u IS NULL THEN RETURN; END IF;
       DELETE FROM public.logbook WHERE auth_uid = u;
       FOR pass IN 1..3 LOOP
         FOR r IN SELECT c.conrelid::regclass AS t, a.attname AS col FROM pg_constraint c
                    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
                   WHERE c.confrelid = 'auth.users'::regclass AND c.contype = 'f' AND c.conrelid <> 'public.worker_profiles'::regclass LOOP
           BEGIN EXECUTE format('DELETE FROM %s WHERE %I = %L', r.t, r.col, u); EXCEPTION WHEN others THEN NULL; END;
         END LOOP;
       END LOOP;
       DELETE FROM public.hive_members WHERE auth_uid = u;
       DELETE FROM public.achievement_xp_log WHERE worker_name = '${q(who.name)}';
       DELETE FROM public.worker_achievements WHERE worker_name = '${q(who.name)}';
       DELETE FROM public.early_access_emails WHERE lower(email) LIKE '${q(who.user)}%';
       DELETE FROM public.worker_profiles WHERE auth_uid = u;
       DELETE FROM auth.users WHERE id = u;
     END $gj$;`]];
  return (X.rec.newcomers[key] = who);
}
// the supervisor's invite link, the way they send it: the hive menu's "Show Invite Code", then "Copy invite link"
async function copyInviteLink(s) {
  await go(s, 'hive.html');
  await s.page.evaluate(() => { const m = document.getElementById('btn-hive-menu'); if (m) m.click(); });
  await sleep(600);
  await s.page.evaluate(() => { const b = document.getElementById('btn-show-code'); if (b) b.click(); });
  await sleep(2500);
  await s.page.evaluate(() => { const b = document.getElementById('btn-copy-invite'); if (b) b.click(); });
  await sleep(1200);
  return (await readClipboard(s)).trim();
}
async function joinByLink(X, P, who, link) {
  await P.page.goto(link, { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {});
  await sleep(4000);
  const up = await signUpHere(P, who, who.pw);
  let note = '';
  for (let k = 0; k < 20 && !note; k++) {
    await sleep(1000);
    note = await P.page.evaluate(() => { const e = document.getElementById('join-invite-note'); return e && !e.classList.contains('hidden') ? e.textContent.trim() : ''; }).catch(() => '');
  }
  await P.page.evaluate(() => { const b = document.getElementById('btn-submit-join'); if (b) b.click(); });
  let welcome = '';
  for (let k = 0; k < 20 && !/You're In/i.test(welcome); k++) {
    await sleep(1000);
    welcome = await P.page.evaluate(() => { const v = document.getElementById('view-welcome'); return v && !v.classList.contains('hidden') ? v.innerText : ''; }).catch(() => '');
  }
  const mid = P.m.uid ? psql(`select id from hive_members where hive_id = '${HIVE_ID}' and auth_uid = '${P.m.uid}' and status = 'active'`) : '';
  return { up, note, welcome, mid };
}
function rosterReach(name) {
  return async (R2, ms) => {
    await go(R2, 'hive.html');
    await R2.page.evaluate(() => { const b = document.getElementById('btn-toggle-members'); if (b && b.getAttribute('aria-expanded') !== 'true') b.click(); });
    for (let t = 0; t < ms; t += 500) {
      const card = await R2.page.evaluate((nm) => {
        const list = document.getElementById('members-list'); if (!list) return null;
        const row = [...list.querySelectorAll('div')].filter((d) => (d.innerText || '').includes(nm) && d.querySelector('[data-wh-joined], .text-sm'))
          .sort((a, b) => (a.innerText || '').length - (b.innerText || '').length)[0];
        return row ? row.innerText.trim() : null;
      }, name).catch(() => null);
      if (card) return { text: name, card };
      await sleep(500);
    }
    return null;
  };
}
RECIPES.J12 = {
  1: async (X) => {   // the newcomer's join is on the supervisor's roster, with when
    const { n, s } = X.S;
    const who = newcomer(X, 'n', 'Rhea', 'Lagman');
    const link = await copyInviteLink(s);
    X.rec.link = link;
    const j = await joinByLink(X, n, who, link || `${ORIGIN}/hive.html`);
    X.rec.member = j.mid;
    X.rec.welcome = j.welcome;
    return { act: { ok: /join=/.test(link) && j.up.ok && !!j.mid,
        detail: `${s.m.name}'s "Copy invite link" gave ${link || 'NOTHING'}; ${who.name}, signed out, opened it, signed up (${j.up.ok}${j.up.err ? ': ' + j.up.err : ''}), read "${j.note || 'no invite line'}" and joined: membership ${j.mid || 'NONE'}` },
      marker: who.name, markerRx: /joined/i, path: 'hive.html', reach: rosterReach(who.name),
      rec: { table: 'hive_members', id: j.mid } };
  },
  2: async (X) => {   // the newcomer's first screen is the hive - not a landing - and names who runs it
    const { n } = X.S;
    return { act: { ok: !!X.rec.member, detail: `${n.m.name} joined at hand-off 1; the screen the join landed on is read` },
      preRead: X.rec.welcome ? { card: X.rec.welcome } : null,
      marker: HOME, markerRx: /supervisor/i, path: 'hive.html', rec: { table: 'hive_members', id: X.rec.member } };
  },
  3: async (X) => {   // the newcomer's first entry is in the supervisor's logbook
    const { n } = X.S;
    await go(n, 'logbook.html');
    const r = await logWizard(n.page, H(n.page), { tag: X.tag, maintType: 'Breakdown / Corrective', status: 'Open', problem: 'conveyor belt slipping at the drive pulley' });
    const id = psql(`select id from logbook where problem like '${q(X.tag)}%' and hive_id = '${HIVE_ID}' order by created_at limit 1`);
    return { act: { ok: !!id, detail: `logbook wizard as ${n.m.name}: ${r.toast || 'no toast'}${id ? ` -> entry ${id}` : ' -> NO ROW'}` },
      marker: X.tag, path: 'logbook.html', reach: (R2, ms) => reachTeam(R2, X.tag, ms), rec: { table: 'logbook', id } };
  },
};

// ── G-PUBLIC · a shared result brings a stranger in: the link, the sign-up, the join (re-premised as J12: a code join is
// admission, so "the join request" is the join on the roster and "the approval" is the newcomer's first screen)
// (cast: w = the worker who shares, x = the stranger (MINTED when they sign up), s = the supervisor)
async function calcFigures(P) {
  return P.page.evaluate(() => {
    const said = (document.querySelector('.kc-said') || {}).textContent || '';
    const figs = [...document.querySelectorAll('.wh-kc li')].map((li) => (li.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean).slice(0, 4);
    return { said: said.trim(), figs };
  }).catch(() => ({ said: '', figs: [] }));
}
RECIPES['G-PUBLIC'] = {
  1: async (X) => {   // the shared result opens for the stranger with the numbers in it
    const { w, x } = X.S;
    if (!x.m.name) x.m.name = 'a stranger, not signed up yet';
    await go(w, 'tools/oee-calculator/index.html');
    // the worker's own numbers: the planned time changed from the default, as a person working out their shift would
    await w.page.evaluate(() => {
      const inp = document.querySelector('.wh-kc input[type="number"]');
      if (inp) { inp.value = String(Number(inp.value || 0) + 37); inp.dispatchEvent(new Event('input', { bubbles: true })); inp.dispatchEvent(new Event('change', { bubbles: true })); }
    });
    await sleep(800);
    const mine = await calcFigures(w);
    await w.page.evaluate(() => { const b = [...document.querySelectorAll('.wh-kc button')].find((x) => /copy share link/i.test(x.textContent || '')); if (b) b.click(); });
    await sleep(1200);
    const link = (await readClipboard(w)).trim();
    X.rec.calcLink = link;
    // the stranger, with no account, opens it
    await x.page.goto(link || `${ORIGIN}/tools/oee-calculator/index.html`, { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {});
    await sleep(3500);
    const theirs = await calcFigures(x);
    const same = mine.figs.length > 0 && mine.figs[0] === theirs.figs[0];
    const carriesNoOne = !!link && !link.includes(encodeURIComponent(w.m.name)) && !link.includes(w.m.name) && !link.includes(HIVE_ID);
    return { act: { ok: /#kpi=/.test(link) && same, detail: `"Copy share link" on the OEE calculator as ${w.m.name}: ${link ? link.slice(0, 90) + '...' : 'NOTHING'}; the stranger read ${theirs.figs[0] || 'nothing'} (the worker's: ${mine.figs[0] || 'nothing'})` },
      preRead: theirs.said ? { card: theirs.said + ' || ' + theirs.figs.join(' | ') } : null,
      marker: 'shared link', whoRx: /shared link/i, path: 'tools/oee-calculator/index.html',
      reach: async (R2, ms) => {
        await R2.page.goto(link, { waitUntil: 'domcontentloaded', timeout: R2.gotoTimeout || 60000 }).catch(() => {});
        for (let t = 0; t < ms; t += 500) {
          const f = await calcFigures(R2);
          if (f.said && f.figs.length) return { text: f.said, card: f.said + ' || ' + f.figs.join(' | ') };
          await sleep(500);
        }
        return null;
      },
      rec: { table: 'hives', id: null },
      F: () => ({ ok: same, detail: `the stranger's first figure "${theirs.figs[0] || '-'}" is the worker's "${mine.figs[0] || '-'}" - the link carries the whole calculation` }),
      I: () => ({ ok: carriesNoOne, link_names_the_worker_or_hive: !carriesNoOne, note: 'a shared calculation carries the numbers and nothing of who made it' }) };
  },
  2: async (X) => {   // the stranger's join is on the supervisor's roster, with when
    const { x, s } = X.S;
    const who = newcomer(X, 'x', 'Arvin', 'Mendoza');
    const link = await copyInviteLink(s);
    const j = await joinByLink(X, x, who, link || `${ORIGIN}/hive.html`);
    X.rec.member = j.mid;
    X.rec.welcome = j.welcome;
    return { act: { ok: /join=/.test(link) && j.up.ok && !!j.mid,
        detail: `the stranger, ${who.name}, opened ${s.m.name}'s invite link, signed up (${j.up.ok}${j.up.err ? ': ' + j.up.err : ''}) and joined: membership ${j.mid || 'NONE'}` },
      marker: who.name, markerRx: /joined/i, path: 'hive.html', reach: rosterReach(who.name),
      rec: { table: 'hive_members', id: j.mid } };
  },
  3: async (X) => {   // the newcomer's first screen is the hive, naming who runs it
    const { x } = X.S;
    return { act: { ok: !!X.rec.member, detail: `${x.m.name} joined at hand-off 2; the screen the join landed on is read` },
      preRead: X.rec.welcome ? { card: X.rec.welcome } : null,
      marker: HOME, markerRx: /supervisor/i, path: 'hive.html', rec: { table: 'hive_members', id: X.rec.member } };
  },
};

// ── J8 · the project: the engineer's BOM on the project, the manager's change order to the engineer, the progress back
// (cast: e = the engineer, p = the project manager (a supervisor))
// ★A FIXTURE, SAID IN THE RECEIPT: "the BOM the engineer generated" is generated in Engineering Design by the BOM agent - a
// model call no walk spends. The engineer's saved calculation WITH its BOM is written for the walk (as the agent would
// have left it in their history) and removed after; everything from the import on is walked through the page.
function j8Project(X) {
  if (X.rec.project) return X.rec.project;
  const row = psql(`select id || '|' || name from projects where hive_id = '${HIVE_ID}' and deleted_at is null order by created_at limit 1`);
  const [id, name] = row ? [row.split('|')[0], row.split('|').slice(1).join('|')] : ['', ''];
  X.restores = [...(X.restores || []), ['the walk\'s calculation, scope items, change order and progress', `set session_replication_role = replica;
      delete from project_items where project_id = '${q(id)}' and (title like '${q(X.tag)}%' or notes like '%${q(X.tag)}%');
      delete from project_change_orders where project_id = '${q(id)}' and title like '${q(X.tag)}%';
      delete from project_progress_logs where project_id = '${q(id)}' and notes like '${q(X.tag)}%';
      delete from engineering_calcs where project_name like '${q(X.tag)}%';`]];
  return (X.rec.project = { id, name });
}
// a project opened as a person opens it, then the detail's own tab for what they came to read
async function openProject(P, id, tab = null) {
  await go(P, 'project-manager.html');
  await P.page.evaluate((pid) => { if (typeof openDetail === 'function') openDetail(pid); }, id);
  await sleep(2500);
  if (tab) {
    await P.page.evaluate((t) => {
      const b = [...document.querySelectorAll('#detail-view button, #detail-view [role="tab"]')].find((x) => (x.textContent || '').trim().toLowerCase() === t.toLowerCase());
      if (b) b.click();
    }, tab);
    await sleep(1500);
  }
}
RECIPES.J8 = {
  1: async (X) => {   // the BOM the engineer generated is on the project
    const { e } = X.S;
    const prj = j8Project(X);
    const bom = [{ item: `${X.tag} centrifugal pump, 50 kW`, qty: 1, unit: 'set', spec: 'TDH 42 m' }, { item: `${X.tag} gate valve DN150`, qty: 2, unit: 'pc', spec: 'PN16' }];
    psql(`insert into engineering_calcs (hive_id, worker_name, auth_uid, calc_type, project_name, inputs, results, bom_data)
      values ('${HIVE_ID}', '${q(e.m.name)}', '${e.m.uid}', 'Pump Sizing (TDH)', '${q(X.tag)} cooling water pump', '{}'::jsonb, '{}'::jsonb, '${q(JSON.stringify(bom))}'::jsonb)`);
    await openProject(e, prj.id);
    await e.page.evaluate(() => { if (typeof openBomImport === 'function') openBomImport(); });
    await sleep(2500);
    const picked = await e.page.evaluate((t) => {
      const b = [...document.querySelectorAll('#modal-bom-import button')].find((x) => (x.textContent || '').includes(t));
      if (b) { b.click(); return true; } return false;
    }, `${X.tag} cooling water pump`);
    await sleep(3000);
    const n = psql(`select count(*) from project_items where project_id = '${q(prj.id)}' and title like '${q(X.tag)}%'`);
    return { act: { ok: picked && Number(n) === 2, detail: `"Import BOM from Eng. Design" on "${prj.name}" as ${e.m.name}, the saved Pump Sizing calculation picked (${picked}): ${n} scope item(s)` },
      marker: `${X.tag} centrifugal pump`, path: 'project-manager.html',
      reach: async (R2, ms) => { await openProject(R2, prj.id, 'Scope / WBS'); return findText(R2, `${X.tag} centrifugal pump`, ms); },
      rec: { table: 'project_items', id: psql(`select id from project_items where project_id = '${q(prj.id)}' and title like '${q(X.tag)} centrifugal%' limit 1`) } };
  },
  2: async (X) => {   // the change order the manager raised reaches the engineer
    const { p } = X.S;
    const prj = j8Project(X);
    await openProject(p, prj.id);
    await p.page.evaluate(() => { if (typeof openNewCO === 'function') openNewCO(); });
    await sleep(1200);
    const title = `${X.tag} add a standby pump`;
    await p.page.fill('#co-title', title).catch(() => {});
    await p.page.fill('#co-scope', 'Add a second 50 kW pump as a standby so the cooling water loop survives a single pump trip.').catch(() => {});
    await p.page.evaluate(() => { const s = document.getElementById('co-reason'); if (s) { const o = [...s.options].find((x) => x.value); if (o) { s.value = o.value; s.dispatchEvent(new Event('change', { bubbles: true })); } } });
    await p.page.fill('#co-cost', '185000').catch(() => {});
    await p.page.fill('#co-days', '6').catch(() => {});
    await p.page.evaluate(() => { const f = document.getElementById('form-co'); if (f) f.requestSubmit ? f.requestSubmit() : f.submit(); });
    await sleep(3000);
    const co = psql(`select id from project_change_orders where project_id = '${q(prj.id)}' and title = '${q(title)}' limit 1`);
    return { act: { ok: !!co, detail: `"Raise change order" on "${prj.name}" as ${p.m.name}: project_change_orders ${co || 'NO ROW'}` },
      marker: title, path: 'project-manager.html',
      reach: async (R2, ms) => { await openProject(R2, prj.id, 'Change orders'); return findText(R2, title, ms); },
      rec: { table: 'project_change_orders', id: co } };
  },
  3: async (X) => {   // the engineer's progress in the manager's report
    const { e } = X.S;
    const prj = j8Project(X);
    await openProject(e, prj.id);
    await e.page.evaluate(() => { if (typeof openProgressLog === 'function') openProgressLog(); });
    await sleep(1200);
    const note = `${X.tag} pump base poured, anchor bolts set`;
    await e.page.fill('#p-pct', '35').catch(() => {});
    await e.page.fill('#p-hours', '6').catch(() => {});
    await e.page.fill('#p-notes', note).catch(() => {});
    await e.page.evaluate(() => { const f = document.getElementById('form-progress'); if (f) f.requestSubmit ? f.requestSubmit() : f.submit(); });
    await sleep(3000);
    const log = psql(`select id from project_progress_logs where project_id = '${q(prj.id)}' and notes like '${q(X.tag)}%' limit 1`);
    return { act: { ok: !!log, detail: `"+ Log progress" (35%) on "${prj.name}" as ${e.m.name}: project_progress_logs ${log || 'NO ROW'}` },
      marker: note.slice(0, 40), path: `project-report.html?project_id=${prj.id}`,
      rec: { table: 'project_progress_logs', id: log } };
  },
};

// ── J30 · the engineer's calculation on the project, and in the report management acts on
// (cast: e = the engineer, s = the supervisor)
RECIPES.J30 = {
  1: async (X) => {   // the engineer's saved calculation is on the project the supervisor reads
    const { e } = X.S;
    const prj = psql(`select id || '|' || name from projects where hive_id = '${HIVE_ID}' and deleted_at is null order by created_at limit 1`);
    const [pid, pname] = prj ? [prj.split('|')[0], prj.split('|').slice(1).join('|')] : ['', ''];
    const calc = psql(`select id || '|' || coalesce(calc_type,'') || '|' || coalesce(project_name,'') from engineering_calcs
      where hive_id = '${HIVE_ID}' and worker_name = '${q(e.m.name)}' order by created_at desc limit 1`);
    const [cid, ctype, cproj] = calc ? calc.split('|') : ['', '', ''];
    X.restores = [...(X.restores || []), ['the walk\'s link', `delete from project_links where project_id = '${q(pid)}' and link_id = '${q(cid)}' and created_at >= '${X.t0}';`]];
    X.rec.prj = { id: pid, name: pname };
    await openProject(e, pid, 'Linked work');
    await e.page.evaluate(() => { const b = [...document.querySelectorAll('button')].find((x) => /openModal\('modal-link'\)/.test(x.getAttribute('onclick') || '')); if (b) b.click(); });
    await sleep(1200);
    await e.page.selectOption('#l-type', 'engineering_calc').catch(() => {});
    await e.page.evaluate(() => { const t = document.getElementById('l-type'); if (t) t.dispatchEvent(new Event('change', { bubbles: true })); if (typeof loadLinkOptions === 'function') loadLinkOptions(); });
    await sleep(2500);
    const chosen = await e.page.evaluate((id) => {
      const sel = document.getElementById('l-picker'); if (!sel) return null;
      const o = [...sel.options].find((x) => x.value === id); if (!o) return null;
      sel.value = id; sel.dispatchEvent(new Event('change', { bubbles: true })); return o.textContent.trim();
    }, cid);
    await e.page.evaluate(() => { if (typeof saveLink === 'function') saveLink(); });
    await sleep(3000);
    const link = psql(`select id || '|' || coalesce(label,'') || '|' || coalesce(linked_by,'') from project_links where project_id = '${q(pid)}' and link_id = '${q(cid)}' and created_at >= '${X.t0}' limit 1`);
    const [lid, label, by] = link ? link.split('|') : ['', '', ''];
    X.rec.link = { id: lid, label };
    return { act: { ok: !!lid && by === e.m.name, detail: `"Link work" -> Engineering calc on "${pname}" as ${e.m.name}: picked "${chosen || 'NOTHING'}" (${ctype} ${cproj}) -> project_links ${lid || 'NO ROW'}, linked_by ${by || '-'}` },
      marker: (label || '').slice(0, 30), path: 'project-manager.html',
      reach: async (R2, ms) => { await openProject(R2, pid, 'Linked work'); return findText(R2, (label || '').slice(0, 30), ms); },
      rec: { table: 'project_links', id: lid } };
  },
  2: async (X) => {   // the report management acts on carries it, with who linked it
    const { prj, link } = X.rec;
    return { act: { ok: !!(link && link.id), detail: `the project report of "${prj && prj.name}" (project-report.html?project_id=...)` },
      marker: ((link && link.label) || '').slice(0, 30), path: `project-report.html?project_id=${prj && prj.id}`,
      rec: { table: 'project_links', id: link && link.id } };
  },
};

// ── G-ADV · the record reached for from outside: the hand-off stays inside its hive, refused in words
RECIPES['G-ADV'] = {
  1: (X) => RECIPES.J2[1](X),
  2: async (X) => {   // a member of another hive holding the entry's own link is refused in words
    const e = X.rec.entry || {};
    return { act: { ok: !!e.id, detail: `the entry's link (logbook.html?id=${e.id}) opened by ${X.S.a.m.name}, a member of ${X.S.a.m.seatName}` },
      refused: /couldn.t find .* in a hive you belong to|not a member|not in your hive|do not have access/i,
      marker: X.tag, path: `logbook.html?id=${e.id}`, rec: { table: 'logbook', id: e.id } };
  },
  3: async (X) => {   // the supervisor's machine record is refused to the foreign member, in words
    const e = X.rec.entry || {};
    const nm = e.node ? psql(`select name from asset_nodes where id = '${q(e.node)}'`) : '';
    // the machine's name is the record's text - unless the other hive happens to have one of the same name
    const clash = nm ? Number(psql(`select count(*) from asset_nodes where hive_id = '${X.S.a.m.seatId}' and name = '${q(nm)}'`)) : 0;
    if (clash) X.notes.push(`hand-off 3: ${X.S.a.m.seatName} also has a machine called "${nm}" - the refusal is read without the name check`);
    return { act: { ok: !!e.node, detail: `the machine's link (asset-hub.html?node_id=${e.node}) opened by ${X.S.a.m.name}` },
      refused: /could not be resolved in this hive|not in your hive|do not have access|couldn.t find/i,
      marker: clash ? null : nm, path: `asset-hub.html?node_id=${e.node}`, rec: { table: 'asset_nodes', id: e.node } };
  },
};

// ── J21 · benchmark to decision: one hive shares, another hive reads, nobody loses their numbers
RECIPES.J21 = {
  1: async (X) => {   // the supervisor turns benchmark sharing on; the members are told, by whom and when
    const { s } = X.S;
    await go(s, 'hive.html');
    await s.page.evaluate(() => { const m = document.getElementById('btn-hive-menu'); if (m) m.click(); });
    await sleep(700);
    const pressed = await s.page.evaluate(() => { const b = document.getElementById('btn-benchmark-sharing'); if (b && b.getAttribute('aria-checked') !== 'true') { b.click(); return true; } return false; });
    const confirmed = pressed ? await modalOk(s) : false;
    await sleep(2500);
    const row = psql(`select federated_benchmark_opted_in || '|' || coalesce(federated_opt_in_by,'') || '|' || coalesce(federated_opt_in_at::text,'') from hives where id = '${HIVE_ID}'`);
    const [on, by] = row.split('|');
    return { act: { ok: /^t(rue)?$/.test(on || '') && by === s.m.name, detail: `"Share benchmarks" on the hive menu as ${s.m.name} (pressed ${pressed}, confirmed ${confirmed}): ${row}` },
      marker: 'shares its anonymised figures', path: 'hive.html', rec: { table: 'hives', id: HIVE_ID, where: 'and federated_benchmark_opted_in' } };
  },
  2: async (X) => {   // the hive's contribution reaches the sector view another hive's supervisor reads - as a count, never a name
    const { f, s } = X.S;
    // ★A FIXTURE, SAID IN THE RECEIPT: ph-intelligence opens for a hive at Stair 3 (maturity-gate.js), and no local hive
    // is above Stair 1 - so the reader's hive is shown at Stair 3 for the walk (its latest readiness row) and put back
    // in cleanup. The hop is about what a Stair-3 hive's supervisor reads of another hive's contribution.
    const rd = psql(`select id || '|' || current_stair from hive_readiness where hive_id = '${f.m.seatId}' order by snapshot_date desc, computed_at desc limit 1`);
    if (rd) {
      const [rdId, rdStair] = rd.split('|');
      if (Number(rdStair) < 3) {
        psql(`update hive_readiness set current_stair = 3 where id = '${rdId}'`);
        X.restores = [...(X.restores || []), [`${f.m.seatName}'s stair back to ${rdStair}`, `update hive_readiness set current_stair = ${Number(rdStair)} where id = '${rdId}';`]];
        X.notes.push(`hand-off 2: ${f.m.seatName} was shown at Stair 3 for the walk (it is at Stair ${rdStair}); ph-intelligence opens at Stair 3`);
      }
    }
    await go(f, 'ph-intelligence.html');
    const pressed = await f.page.evaluate(() => {
      const b = document.getElementById('ph-regenerate-btn')
        || [...document.querySelectorAll('button')].find((x) => /generate/i.test(x.innerText || '') && x.checkVisibility && x.checkVisibility());
      if (b) { b.click(); return (b.innerText || b.id || '').trim(); } return null;
    });
    let rid = null;
    for (let t = 0; t < 60000 && !rid; t += 2000) { await sleep(2000); rid = psql(`select id from ph_intelligence_reports where generated_at >= '${X.t0}' order by generated_at desc limit 1`) || null; }
    const said = rid ? psql(`select coalesce(narrative->>'executive_summary','') from ph_intelligence_reports where id = '${rid}'`) : '';
    return { act: { ok: !!rid, detail: `"${pressed || 'no Generate control'}" on ph-intelligence as ${f.m.name}: report ${rid || 'NOT GENERATED'} - ${said.slice(0, 140)}` },
      marker: 'needed have opted in', whoRx: /\b\d+ of the \d+ needed have opted in/i,
      mustNotSay: new RegExp([HOME, HOME.split(' ')[0], s.m.name].map(reEsc).join('|'), 'i'),
      path: 'ph-intelligence.html', rec: { table: 'ph_intelligence_reports', id: rid },
      // anonymised: the reader of the sector view may not read the contributing hive's own row or its own figures
      I: () => {
        const a = Number(asUser(f.m.uid, `select count(*) from hives where id = '${HIVE_ID}'`));
        const b = Number(asUser(f.m.uid, `select count(*) from hive_benchmarks where hive_id = '${HIVE_ID}'`));
        return { ok: a === 0 && b === 0, detail: `as ${f.m.name} (${f.m.seatName}): ${HOME}'s hive row ${a}, its own benchmark rows ${b} - both must be 0` };
      } };
  },
  3: async (X) => {   // the supervisor shares the decision with the hive
    const { s } = X.S;
    await go(s, 'community.html');
    await s.page.evaluate(() => { if (typeof openComposer === 'function') openComposer(); });
    await sleep(1000);
    const text = `${X.tag} we now share our anonymised figures with the PH benchmarks - totals only, never names or machines`;
    await s.page.fill('#post-content', text).catch(() => {});
    await s.page.evaluate(() => { const b = document.getElementById('btn-submit-post'); if (b) b.click(); });
    await sleep(3500);
    const pid = psql(`select id from community_posts where hive_id = '${HIVE_ID}' and content like '${q(X.tag)}%' order by created_at desc limit 1`);
    return { act: { ok: !!pid, detail: `"Post to Hive" as ${s.m.name}: community_posts ${pid || 'NO ROW'}` },
      marker: X.tag, path: 'community.html', rec: { table: 'community_posts', id: pid } };
  },
};

// ── G-ESC · a problem the supervisor cannot settle: it reaches the platform (hand-offs 2-3 are M10's, the public board)
RECIPES['G-ESC'] = {
  1: async (X) => {   // the worker reports a post; it is in the supervisor's Mod Queue - who reported it, when, and why
    const { w, s } = X.S;
    // the post is a third member's (neither the reporter nor the supervisor), read from the hive, never typed
    const arow = psql(`select m.auth_uid || '|' || p.display_name from hive_members m join worker_profiles p on p.auth_uid = m.auth_uid
      where m.hive_id = '${HIVE_ID}' and m.status = 'active' and m.role = 'worker' and m.auth_uid not in ('${w.m.uid}', '${s.m.uid}') order by p.display_name limit 1`);
    const [auid, aname] = (arow || '|').split('|');
    // a fixture, written with triggers off: it earns its author no XP (the cleanup removes the CAST's XP only)
    const pid = psql(`set session_replication_role = replica;
      insert into community_posts (hive_id, author_name, auth_uid, content, category)
      values ('${HIVE_ID}', '${q(aname)}', '${auid}', '${q(X.tag)} selling my own spare bearings at half price, message me', 'general') returning id;`)
      .split('\n').find((l) => /^[0-9a-f-]{36}$/.test(l.trim())) || null;
    await go(w, 'community.html');
    // the feed draws its cards as the person scrolls (the pinned ones first): scroll down to the post, as they would
    for (let i = 0; i < 12; i++) {
      const drawn = await w.page.evaluate((id) => !!document.getElementById('post-' + id), pid);
      if (drawn) break;
      await w.page.evaluate(() => window.scrollBy(0, Math.round(window.innerHeight * 0.9)));
      await sleep(600);
    }
    await w.page.evaluate((id) => { const c = document.getElementById('post-' + id); if (c) c.scrollIntoView({ block: 'center' }); }, pid);
    await sleep(400);
    // the post's own menu ("⋯") and its "Report this post", as a person taps them
    const viaMenu = await w.page.evaluate((id) => {
      const card = document.getElementById('post-' + id);
      const trigger = card && [...card.querySelectorAll('.post-head button')].find((b) => b.getAttribute('aria-haspopup') || /more|menu|options/i.test(b.getAttribute('aria-label') || ''));
      if (!trigger) return false;
      trigger.click(); return true;
    }, pid);
    await sleep(600);
    const tappedItem = viaMenu ? await w.page.evaluate(() => {
      const it = [...document.querySelectorAll('[role="menuitem"], [role="menu"] button')].find((b) => /report this post/i.test(b.innerText || '') && b.checkVisibility && b.checkVisibility());
      if (it) { it.click(); return true; } return false;
    }) : false;
    let opened = tappedItem;
    if (!opened) {
      X.notes.push('hand-off 1: the post menu\'s "Report this post" was not reached by taps - the report sheet was opened by its own function');
      opened = await w.page.evaluate((id) => { if (typeof openReport === 'function') { openReport(id); return true; } return false; }, pid);
    }
    await sleep(900);
    await w.page.selectOption('#report-reason', 'spam').catch(() => {});
    await w.page.fill('#report-details', 'Personal sales in the plant feed').catch(() => {});
    await w.page.evaluate(() => { const b = document.getElementById('btn-submit-report'); if (b) b.click(); });
    await sleep(3000);
    const flagged = psql(`select flagged from community_posts where id = '${q(pid)}'`);
    return { act: { ok: flagged === 't' && opened, detail: `"Report Post" on ${aname}'s post as ${w.m.name} (reason spam): flagged = ${flagged}` },
      marker: X.tag, markerRx: /Reported by/i, path: 'community.html',
      reach: async (R2, ms) => {
        await go(R2, 'community.html');
        await R2.page.evaluate(() => { const t = document.getElementById('tab-mod'); if (t) t.click(); });
        await sleep(1500);
        return findText(R2, X.tag, ms);
      },
      rec: { table: 'community_posts', id: pid, where: 'and flagged' } };
  },
};

function snapshotInPlace() {
  return { snaps: psql(`select coalesce(json_agg(row_to_json(t)), '[]') from analytics_snapshots t where hive_id = '${HIVE_ID}'`),
    alerts: psql(`select coalesce(json_agg(row_to_json(t)), '[]') from failure_signature_alerts t where hive_id = '${HIVE_ID}'`),
    // a publish changes the hive's shift plan in place (status, published_by, published_at)
    plans: psql(`select coalesce(json_agg(row_to_json(t)), '[]') from shift_plans t where hive_id = '${HIVE_ID}'`),
    // the anomaly composer rewrites every signal of the hive (computed_at, scores)
    anomalies: psql(`select coalesce(json_agg(row_to_json(t)), '[]') from anomaly_signals t where hive_id = '${HIVE_ID}'`),
    // a supervisor's Remove (J14, G-LEAVE) changes a membership in place: every member row of the home hive comes back
    members: psql(`select coalesce(json_agg(row_to_json(t)), '[]') from hive_members t where hive_id = '${HIVE_ID}'`),
    // a supervisor's "Share benchmarks" (J21) changes the hive's consent and its stamp - every hive's, so a walk seated
    // anywhere gives it back
    optin: psql(`select coalesce(json_agg(json_build_object('id', id, 'federated_benchmark_opted_in', federated_benchmark_opted_in,
      'federated_opt_in_at', federated_opt_in_at, 'federated_opt_in_by', federated_opt_in_by)), '[]') from hives`),
    // a Generate on ph-intelligence (J21) upserts the network's report for the period - one table for every hive
    reports: psql(`select coalesce(json_agg(row_to_json(t)), '[]') from ph_intelligence_reports t`) };
}
// ★EVERY STEP OF THE CLEANUP RUNS ON ITS OWN (2026-11-04, the first teeth run): one psql script with ON_ERROR_STOP died
// on a wrong column at its fourth line, and the audit lines, the XP and the restores after it never ran - the walk left
// three audit rows, an XP row and two "new device" registrations behind. A failing step is now recorded in the receipt's
// notes and the rest still run; each restore is ONE transaction, so a failed insert can never leave the rows deleted.
// What a walk leaves besides its own tagged rows: the XP the entry earned (achievement_xp_log, keyed by worker_name +
// earned_at), the audit lines it wrote, and the headless browser each member signed in from (worker_known_devices).
function cleanup(X, kept) {
  const people = Object.values(X.S).filter((s) => s.m.uid);
  const uids = people.map((s) => `'${s.m.uid}'`).join(',') || `'00000000-0000-0000-0000-000000000000'`;
  const names = people.map((s) => `'${q(s.m.name)}'`).join(',') || `''`;
  const R = 'set session_replication_role = replica;\n';
  const steps = [
    ['tagged logbook rows', `delete from logbook where hive_id = '${HIVE_ID}' and (problem like '${q(X.tag)}%' or id like '${q(X.tag)}%');`],
    ['tagged pushes', `delete from service_outbox where consumer = 'notify-push' and created_at >= '${X.t0}' and payload::text like '%${q(X.tag)}%';`],
    ['assignment pushes', `delete from service_outbox where consumer = 'notify-push' and created_at >= '${X.t0}'
      and payload->>'title' = 'Work order assigned to you' and payload->'auth_uids' ?| array[${uids}];`],
    // ★CHILDREN BEFORE PARENTS - THE CLEANUP RUNS WITH TRIGGERS OFF, SO NO FOREIGN KEY WILL SAY IT (2026-11-04): a PM
    // completion saved on pm-scheduler is mirrored into the logbook (id pm-..., pm_completion_id), and deleting the
    // completions first left eight logbook rows pointing at nothing - found by the psql-probe-suite
    // (logbook__queue_drains_once could no longer update the newest row). The mirrors go first, by their link.
    ['tagged PM rows', `delete from logbook where pm_completion_id in (select c.id from pm_completions c join pm_assets a on a.id = c.asset_id
        where a.hive_id = '${HIVE_ID}' and a.asset_name like '${q(X.tag)}%');
      delete from pm_completions where asset_id in (select id from pm_assets where hive_id = '${HIVE_ID}' and asset_name like '${q(X.tag)}%');
      delete from pm_scope_items where asset_id in (select id from pm_assets where hive_id = '${HIVE_ID}' and asset_name like '${q(X.tag)}%');
      delete from pm_assets where hive_id = '${HIVE_ID}' and asset_name like '${q(X.tag)}%';`],
    ['XP the walk earned', `delete from achievement_xp_log where earned_at >= '${X.t0}' and worker_name in (${names});`],
    ...(kept.xpNames ? [['the cast\'s XP totals put back', `begin;
      delete from worker_achievements where worker_name in ${kept.xpNames};
      insert into worker_achievements select * from json_populate_recordset(null::worker_achievements, '${q(kept.xpTotals)}');
      delete from community_xp where worker_name in ${kept.xpNames};
      insert into community_xp select * from json_populate_recordset(null::community_xp, '${q(kept.cxTotals)}');
      commit;`]] : []),
    ['audit lines', `delete from hive_audit_log where hive_id = '${HIVE_ID}' and created_at >= '${X.t0}';`],
    ['the walk\'s acknowledgements', `delete from alert_dismissals where hive_id = '${HIVE_ID}' and created_at >= '${X.t0}';`],
    ['the walk\'s devices', `delete from worker_known_devices where first_seen_at >= '${X.t0}' and auth_uid in (${uids});`],
    ['failure alerts restored', `begin; delete from failure_signature_alerts where hive_id = '${HIVE_ID}';
      insert into failure_signature_alerts select * from json_populate_recordset(null::failure_signature_alerts, '${q(kept.alerts)}'); commit;`],
    ['the bridge\'s readings', `delete from sensor_readings where hive_id = '${HIVE_ID}' and meta->>'walk' = '${q(X.tag)}';`],
    ['anomaly signals restored', `begin; delete from anomaly_signals where hive_id = '${HIVE_ID}';
      insert into anomaly_signals select * from json_populate_recordset(null::anomaly_signals, '${q(kept.anomalies)}'); commit;`],
    ['tagged parts and their movements', `delete from inventory_transactions where item_id in (select id from inventory_items where hive_id = '${HIVE_ID}' and part_name like '${q(X.tag)}%');
      delete from inventory_items where hive_id = '${HIVE_ID}' and part_name like '${q(X.tag)}%';`],
    ['tagged posts and machines', `delete from community_posts where hive_id = '${HIVE_ID}' and content like '${q(X.tag)}%';
      delete from asset_nodes where hive_id = '${HIVE_ID}' and name like '${q(X.tag)}%';`],
    // ★A PLAN THE PRODUCT MADE IS KEPT, UNPUBLISHED (2026-11-04, J9 pass b): shift-brain builds the shift's plan on its
    // first open (a model call), and deleting it with the restore left pass b with no plan to publish and no fresh build.
    // The plans that existed before the walk come back exactly; one the walk caused stays, set back to draft.
    ['shift plans restored', `begin;
      update shift_plans set status = 'draft', published_at = null, published_by = null where hive_id = '${HIVE_ID}' and created_at >= '${X.t0}';
      delete from shift_plans where hive_id = '${HIVE_ID}' and created_at < '${X.t0}';
      -- a plan the walk built in a window the snapshot holds (G-SHIFT sets the window's plan aside) gives the window back
      delete from shift_plans p where p.hive_id = '${HIVE_ID}' and p.created_at >= '${X.t0}' and exists (select 1
        from json_populate_recordset(null::shift_plans, '${q(kept.plans)}') k where k.shift_date = p.shift_date and k.shift_window = p.shift_window);
      insert into shift_plans select * from json_populate_recordset(null::shift_plans, '${q(kept.plans)}'); commit;`],
    ['analytics snapshots restored', `begin; delete from analytics_snapshots where hive_id = '${HIVE_ID}';
      insert into analytics_snapshots select * from json_populate_recordset(null::analytics_snapshots, '${q(kept.snaps)}'); commit;`],
    // ★A REMOVED MEMBER IS A MEMBER AGAIN AFTER THE WALK (2026-11-05, GJ M8 J14 / G-LEAVE): the removal is the walk's
    // act; the person is a member of the plant's demo hive in every other scenario. Status, role and the removal stamp
    // come back exactly (triggers off: a restore is not a supervisor's re-approval).
    ['memberships restored', `update hive_members m set status = k.status, role = k.role, removed_at = k.removed_at, removed_by = k.removed_by
      from json_populate_recordset(null::hive_members, '${q(kept.members)}') k where m.id = k.id
        and (m.status, m.role, m.removed_at, m.removed_by) is distinct from (k.status, k.role, k.removed_at, k.removed_by);`],
    ['benchmark consent restored', `update hives h set federated_benchmark_opted_in = k.federated_benchmark_opted_in,
        federated_opt_in_at = k.federated_opt_in_at, federated_opt_in_by = k.federated_opt_in_by
      from json_populate_recordset(null::hives, '${q(kept.optin)}') k where h.id = k.id
        and (h.federated_benchmark_opted_in, h.federated_opt_in_at, h.federated_opt_in_by)
          is distinct from (k.federated_benchmark_opted_in, k.federated_opt_in_at, k.federated_opt_in_by);`],
    ['PH reports restored', `begin; delete from ph_intelligence_reports where generated_at >= '${X.t0}';
      insert into ph_intelligence_reports select * from json_populate_recordset(null::ph_intelligence_reports, '${q(kept.reports)}')
        on conflict do nothing; commit;`],
    ['report pushes', `delete from service_outbox where consumer = 'notify-push' and created_at >= '${X.t0}'
      and payload->>'title' = 'A post was reported' and payload->'auth_uids' ?| array[${uids}];`],
    // a recipe's own fixture, set for the walk and named in its receipt, is put back here (J21: the reader's stair)
    ...(X.restores || []),
  ];
  // a member seated in ANOTHER hive (G-MULTI's second supervisor) means the walk made rows there too: the tag- and
  // time-keyed removals run in each such hive as well (the in-place restores are the home hive's alone)
  for (const h of [...new Set(people.map((p2) => p2.m.seatId).filter((h2) => h2 && h2 !== HIVE_ID))]) {
    steps.push(
      [`tagged logbook rows in ${h}`, `delete from logbook where hive_id = '${h}' and (problem like '${q(X.tag)}%' or id like '${q(X.tag)}%');`],
      [`tagged PM rows in ${h}`, `delete from logbook where pm_completion_id in (select c.id from pm_completions c join pm_assets a on a.id = c.asset_id
          where a.hive_id = '${h}' and a.asset_name like '${q(X.tag)}%');
        delete from pm_completions where asset_id in (select id from pm_assets where hive_id = '${h}' and asset_name like '${q(X.tag)}%');
        delete from pm_scope_items where asset_id in (select id from pm_assets where hive_id = '${h}' and asset_name like '${q(X.tag)}%');
        delete from pm_assets where hive_id = '${h}' and asset_name like '${q(X.tag)}%';`],
      [`audit lines in ${h}`, `delete from hive_audit_log where hive_id = '${h}' and created_at >= '${X.t0}';`],
      [`acknowledgements in ${h}`, `delete from alert_dismissals where hive_id = '${h}' and created_at >= '${X.t0}';`]);
  }
  for (const [what, sql] of steps) {
    try { psql(R + sql); } catch (e) { X.notes.push(`cleanup step "${what}" failed: ${String(e.message || e).slice(0, 200)}`); }
  }
  if (X.notes.some((n) => n.startsWith('cleanup step'))) console.log('  CLEANUP INCOMPLETE: ' + X.notes.filter((n) => n.startsWith('cleanup step')).join(' | '));
}

async function walkPass(browser, pass, foreign) {
  const keys = Object.keys(CAST);
  const vps = ['phone-390', 'desktop-1280'];
  const S = {};
  for (let i = 0; i < keys.length; i++) {
    const c = CAST[keys[i]];
    // ★A STRANGER WHO READS (2026-11-06, GJ M9 J31): a stranger has no account, but J31's stranger is the one who READS the
    // shared post - so they get a signed-out browser of their own (a machine still only acts)
    if (c.user === 'anon') {
      S[keys[i]] = await session(browser, { key: keys[i], ...c, user: null, uid: null, name: 'a stranger', role: null, minted: true, anon: true }, vps[(i + (pass === 'b' ? 1 : 0)) % 2]);
      continue;
    }
    // a machine (the plant bridge) has no account and no screen of the walk's: it acts, it does not read
    if (String(c.user).startsWith('api-key@')) {
      S[keys[i]] = { m: { key: keys[i], ...c, uid: null, name: c.user === 'anon' ? 'a stranger' : `the plant bridge (${c.hive})` },
        vp: 'n/a', page: null, ctx: { close: async () => {} } };
      continue;
    }
    S[keys[i]] = await session(browser, member(keys[i]), vps[(i + (pass === 'b' ? 1 : 0)) % 2]);
  }
  const X = { S, tag: `GJ-${SCEN}-${pass}-${Date.now()}`, t0: psql('select now()'), rec: {}, notes: [],
    faults: new Set(TEETH ? ['push-never-fires', 'foreign-let-in'] : []) };
  const kept = snapshotInPlace();
  // ★THE LOG ROWS WENT, THE TOTALS THEY FED STAYED (2026-11-06, found walking J7): the cleanup deletes the XP lines a walk
  // earned, but worker_achievements.xp_total and community_xp had already been raised by them - every walk left its cast a
  // little richer. The cast's totals are kept here, before anything happens, and put back exactly in the cleanup.
  {
    const castNames = Object.values(S).map((s) => s.m && s.m.name).filter((n) => n && n !== 'a stranger' && !/^the plant bridge/.test(n));
    if (castNames.length) {
      const inList = '(' + castNames.map((n) => `'${q(n)}'`).join(',') + ')';
      kept.xpNames = inList;
      kept.xpTotals = psql(`select coalesce(json_agg(row_to_json(t)), '[]') from worker_achievements t where worker_name in ${inList}`);
      kept.cxTotals = psql(`select coalesce(json_agg(row_to_json(t)), '[]') from community_xp t where worker_name in ${inList}`);
    }
  }
  const out = [];
  try {
    for (const hop of HOPS) {
      if (TEETH && hop.handoff > 2) break;
      const recipe = (RECIPES[SCEN] || {})[hop.handoff];
      const R = S[hop.receiver];
      const res = { handoff: hop.handoff, page: hop.page, sender: `${hop.sender}:${S[hop.sender].m.name}@${S[hop.sender].vp}`,
        receiver: `${hop.receiver}:${R.m.name}@${R.vp}`, channel: hop.channel, what: hop.what };
      if (!recipe) { out.push({ ...res, unbuilt: true }); continue; }
      let r;
      try { r = await recipe(X); } catch (e) { out.push({ ...res, act: { ok: false, detail: String(e.message || e).slice(0, 200) } }); continue; }
      res.act = r.act;
      res.sender = `${hop.sender}:${S[hop.sender].m.name}@${S[hop.sender].vp}`;
      res.receiver = `${hop.receiver}:${R.m.name}@${R.vp}`;
      if (r.refused || r.absent) {
        // a hand-off that must not arrive: U reads the refusal (or the absence), F and I read that the receiver's own
        // session gets NO row, A asks the same on 3G
        res.U = r.refused ? await readRefusal(R, r) : await readAbsence(R, r);
        const idColR = (r.rec && r.rec.idCol) || 'id';
        const recvR = r.rec && r.rec.id ? Number(asUser(R.m.uid, `select count(*) from ${r.rec.table} where ${idColR}::text = '${q(r.rec.id)}' ${r.rec.where || ''}`)) : -1;
        const forR = r.rec && r.rec.id ? Number(asUser(foreign.uid, `select count(*) from ${r.rec.table} where ${idColR}::text = '${q(r.rec.id)}'`)) : -1;
        res.F = r.F ? r.F() : { ok: recvR === 0, detail: `${r.rec.table} ${r.rec.id} read as ${R.m.name}${r.refused ? ' (another hive)' : ''} through RLS${r.rec.where ? ' ' + r.rec.where : ''}: ${recvR} row(s) - must be 0` };
        res.I = r.I ? r.I(foreign) : { ok: recvR === 0 && forR === 0, receiver_rows: recvR, foreign: foreign.user, foreign_rows: forR };
        res.A = await under3G(R, async (S2) => (r.refused ? (await readRefusal(S2, r, 45000)).ok : (await readAbsence(S2, r)).ok) || null);
        out.push(res);
        console.log(`  ${SCEN} pass ${pass} hand-off ${hop.handoff} ${hop.page}: act ${res.act.ok ? 'ok' : 'FAIL'} · U ${res.U.ok ? 'ok' : 'FAIL'} · F ${res.F.ok ? 'ok' : 'FAIL'} · I ${res.I.ok ? 'ok' : 'FAIL'} · A ${res.A.ok ? 'ok' : 'FAIL'}`);
        continue;
      }
      // U - the receiver lands by the hop's channel and reads the screen (the recipe's own route when it has one)
      const reach = r.reach || (async (S2, ms) => { await go(S2, r.path); return r.marker ? findText(S2, r.marker, ms) : true; });
      let seen = r.preRead || null;
      // a page whose statement needs the person's own tap first (analytics-report's "Generate Report") says so in prepare()
      if (!seen) { if (r.marker) seen = await reach(R, 20000); else { await go(R, r.path); if (r.prepare) await r.prepare(R); } }
      if (r.marker) {
        // a receiver who arrives by a push reads the push first: its words are part of what they were told
        const card = (seen ? seen.card : '') + (r.channelSaid ? ` || the push: ${r.channelSaid}` : '');
        const who = S[hop.sender].m.name.split(' ')[0];
        const hasWho = r.whoRx ? r.whoRx.test(card) : new RegExp(who, 'i').test(card);
        // a push is delivered with its own time on the device - a receiver who arrives by one is told when by it
        const hasWhen = /\d{1,2}:\d{2}|ago|today|just now|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w* \d{1,2}|\d{4}-\d{2}-\d{2}/i.test(card)
          || !!r.channelSaid;
        const rxOk = r.markerRx ? r.markerRx.test(card) : true;
        res.U = { ok: !!seen && hasWho && hasWhen && rxOk, live: r.live ?? null, live_said: r.liveSaid || null, who: hasWho, when: hasWhen,
          said: seen ? card.replace(/\s+/g, ' ').slice(0, 300) : null };
        if (seen && !hasWho) res.U.why = `the screen shows the record but not who did it (${S[hop.sender].m.name})`;
        // ★AN ANONYMISED HAND-OFF MUST STAY ANONYMOUS (2026-11-05, GJ M8 J21): what the receiver must NOT be told (the
        // contributing hive's name, its supervisor's) is read off the whole screen, not only the card
        if (r.mustNotSay && seen) {
          const whole = await R.page.evaluate(() => document.body.innerText || '').catch(() => '');
          const leak = (whole.match(r.mustNotSay) || [])[0] || null;
          if (leak) { res.U.ok = false; res.U.leaked = leak; res.U.why = `the screen names what it must not: "${leak}"`; }
        }
        // a reading that found nothing says what WAS on the screen, so the receipt explains itself (the closest lines)
        if (!seen) res.U.screen = await R.page.evaluate((src) => {
          const re = new RegExp(src, 'i');
          return [...new Set((document.body.innerText || '').split('\n').map((l) => l.trim()).filter((l) => l && l.length < 200 && re.test(l)))].slice(0, 8);
        }, r.hint || r.marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).catch(() => null);
      } else if (r.figure) {
        // a figure the receiver's page must state, judged against what the engine said before the sender acted
        res.U = await r.figure(R);
      } else {
        const page = await R.page.evaluate(() => document.body.innerText || '');
        // ★A LABEL IS NOT A READING (2026-11-04, J3 hand-off 5): analytics-report's toolbar word "Period" matched, and U
        // read green on a line that states no period at all. The line must carry its value - a number, or "just now".
        const fresh = page.split('\n').find((l) => r.freshnessRx.test(l) && l.length < 160 && /\d|just now/i.test(l)) || null;
        res.U = { ok: !!fresh, said: fresh };
      }
      // F - psql as the receiver finds the sender's record (or the recipe's own F, e.g. the push)
      const idCol = r.rec.idCol || 'id';
      // a receiver with no account (a stranger) is read by the recipe's own F, through the public key
      const recvRows = (r.rec.id && R.m.uid) ? Number(asUser(R.m.uid, `select count(*) from ${r.rec.table} where ${idCol}::text = '${q(r.rec.id)}' ${r.rec.where || ''}`)) : 0;
      res.F = r.F ? r.F() : { ok: recvRows >= 1, detail: `${r.rec.table} ${r.rec.id || '(none)'} read as ${R.m.name} through RLS: ${recvRows} row(s)` };
      // I - the receiver may, a member of another hive may not
      const witness = X.faults.has('foreign-let-in') ? { user: R.m.user, uid: R.m.uid } : foreign;
      const forRows = r.rec.id ? Number(asUser(witness.uid, `select count(*) from ${r.rec.table} where ${idCol}::text = '${q(r.rec.id)}'`)) : -1;
      res.I = r.I ? r.I(witness) : { ok: recvRows >= 1 && forRows === 0, receiver_rows: recvRows, foreign: witness.user, foreign_rows: forRows };
      // A - the receiver's landing on 3G, the sender's network untouched
      // ★A MARKER-LESS PAGE'S A READING USED TO BE "IT LOADED" (2026-11-04): it returned true after the navigation, so a
      // figure page passed on 3G without its statement ever being read. It now reads the same dated line U read.
      res.A = await under3G(r.aOnSender ? S[hop.sender] : R, async (S2) => {
        if (r.marker) return reach(S2, 45000);
        await go(S2, r.path);
        if (r.prepare) await r.prepare(S2);
        if (r.figure) return (await r.figure(S2)).ok || null;
        for (let t = 0; t < 45000; t += 1000) {
          const txt = await S2.page.evaluate(() => document.body.innerText || '').catch(() => '');
          if (txt.split('\n').some((l) => r.freshnessRx.test(l) && l.length < 160 && /\d|just now/i.test(l))) return true;
          await sleep(1000);
        }
        return null;
      });
      // a receiver handed paper: the bad network is the sender's, whose phone produces it - said in the receipt
      if (r.aOnSender && res.A) res.A.detail = `on ${S[hop.sender].m.name}'s connection (the paper is made on their phone): ${res.A.detail}`;
      out.push(res);
      console.log(`  ${SCEN} pass ${pass} hand-off ${hop.handoff} ${hop.page}: act ${res.act.ok ? 'ok' : 'FAIL'} · U ${res.U.ok ? 'ok' : 'FAIL'} · F ${res.F.ok ? 'ok' : 'FAIL'} · I ${res.I.ok ? 'ok' : 'FAIL'} · A ${res.A.ok ? 'ok' : 'FAIL'}`);
    }
  } finally {
    cleanup(X, kept);
    for (const s of Object.values(S)) await s.ctx.close().catch(() => {});
  }
  return { pass, tag: X.tag, viewports: Object.fromEntries(Object.entries(S).map(([k, s]) => [k, s.vp])), hops: out, notes: X.notes };
}

const browser = await chromium.launch();
const foreign = foreignWitness();
const passes = [];
try {
  for (const p of PASSES) passes.push(await walkPass(browser, p, foreign));
} finally { await browser.close(); }
// ★ONE PASS RE-WALKED KEEPS THE OTHER (2026-11-05, J17): a pass lost to a cause outside the product (the edge runtime
// still restarting when the walk's first request went out) was re-walked with --pass a, and the receipt it wrote held
// pass a alone - the banker needs both viewports, so pass b's good walk was thrown away and had to be walked again.
// A single-pass walk now merges with the receipt on disk when that receipt is a real walk (not teeth) under the
// banker's freshness limit, and the merged receipt keeps the OLDER time, so the limit is judged on the older pass.
let mergedFrom = null;
if (arg('--pass') && !TEETH && existsSync(`.tmp/gj_walks/${SCEN}.json`)) {
  try {
    const prev = JSON.parse(readFileSync(`.tmp/gj_walks/${SCEN}.json`, 'utf8'));
    const ageH = (Date.now() - Date.parse(prev.generated)) / 3600000;
    const others = (prev.passes || []).filter((p) => p.pass !== arg('--pass'));
    if (!prev.teeth && ageH < 3 && others.length) {
      passes.unshift(...others);
      passes.sort((x, y) => String(x.pass).localeCompare(String(y.pass)));
      mergedFrom = prev.generated;
    }
  } catch (_) { /* an unreadable receipt is replaced, as it always was */ }
}
const cells = ['act', 'U', 'F', 'I', 'A'];
const hopOk = (h) => !h.unbuilt && cells.every((c) => h[c] && h[c].ok);
const report = { generated: mergedFrom || new Date().toISOString(), ...(mergedFrom ? { merged: `pass ${arg('--pass')} re-walked ${new Date().toISOString()} onto the receipt of ${mergedFrom}` } : {}), instrument: 'tools/prove_group_journeys.mjs (playwright, one browser context per member) + postgres (psql as the receiver)',
  scenario: SCEN, home: HOME, cast: CAST, foreign_witness: foreign.user, teeth: TEETH, passes,
  hops: HOPS.map((h) => ({ ...h, ok: passes.every((p) => { const x = p.hops.find((y) => y.handoff === h.handoff); return x && hopOk(x); }),
    cells: Object.fromEntries(cells.map((c) => [c, passes.every((p) => { const x = p.hops.find((y) => y.handoff === h.handoff); return !!(x && x[c] && x[c].ok); })])) })) };
report.ok = report.hops.every((h) => h.ok);
if (TEETH) {
  const p = passes[0].hops;
  const bitPush = p.find((h) => h.handoff === 2)?.F?.ok === false;
  const bitForeign = p.find((h) => h.handoff === 1)?.I?.ok === false;
  report.teeth_result = { push_never_fires_read_FAIL: bitPush, foreign_let_in_read_FAIL: bitForeign };
  console.log(`  teeth: a push that never fires -> F ${bitPush ? 'FAIL (bites)' : 'ok (NO TEETH)'}; a foreign member let in -> I ${bitForeign ? 'FAIL (bites)' : 'ok (NO TEETH)'}`);
  writeFileSync(`.tmp/gj_teeth_${SCEN}.json`, JSON.stringify(report, null, 1));
  process.exit(bitPush && bitForeign ? 1 : 0);
}
mkdirSync('.tmp/gj_walks', { recursive: true });
writeFileSync(`.tmp/gj_walks/${SCEN}.json`, JSON.stringify(report, null, 1));
const all = existsSync(OUT) ? JSON.parse(readFileSync(OUT, 'utf8')) : { scenarios: {} };
all.generated = report.generated; all.scenarios[SCEN] = report;
writeFileSync(OUT, JSON.stringify(all, null, 1) + '\n');
console.log(`  ${SCEN}: ${report.hops.filter((h) => h.ok).length}/${report.hops.length} hand-offs hold at both viewports -> ${OUT}`);
process.exit(report.ok ? 0 : 1);
