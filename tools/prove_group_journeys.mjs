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
  const [uid, name] = psql(`select auth_uid, display_name from worker_profiles where username = '${q(c.user)}'`).split('|');
  const role = psql(`select role from hive_members where hive_id = '${HIVE_ID}' and auth_uid = '${uid}' and status = 'active'`);
  return { key, ...c, uid, name, role };
}
// a member of ANOTHER hive, who belongs to nothing in this one - the I reading's third person (never typed)
function foreignWitness() {
  const [user, uid] = psql(`select w.username, w.auth_uid from hive_members m join worker_profiles w on w.auth_uid = m.auth_uid
    where m.status = 'active' and m.role = 'worker' and m.hive_id <> '${HIVE_ID}'
      and not exists (select 1 from hive_members x where x.auth_uid = m.auth_uid and x.hive_id = '${HIVE_ID}')
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
  const tok = await (await fetch(`${SB}/auth/v1/token?grant_type=password`, { method: 'POST',
    headers: { apikey: KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: `${m.user}@auth.workhiveph.com`, password: 'test1234' }) })).json();
  if (!tok.access_token) throw new Error(`sign-in failed for ${m.user}`);
  await ctx.addInitScript(([t, hive, hiveName, name, r]) => {
    try {
      if (!localStorage.getItem('sb-127-auth-token')) localStorage.setItem('sb-127-auth-token', JSON.stringify(t));
      localStorage.setItem('wh_last_worker', name);
      localStorage.setItem('wh_active_hive_id', hive); localStorage.setItem('wh_hive_name', hiveName);
      if (r) localStorage.setItem('wh_hive_role', r);
      Object.keys(localStorage).filter((k) => k.startsWith('wh_logbook_draft')).forEach((k) => localStorage.removeItem(k));
    } catch (_) { /* storage blocked */ }
  }, [tok, HIVE_ID, HOME, m.name, m.role]);
  const page = await ctx.newPage();
  page.on('dialog', (d) => d.accept().catch(() => {}));
  return { ctx, page, m, vp: vpName, token: tok.access_token };
}
async function go(s, path) {
  await s.page.goto(`${ORIGIN}/${path}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await sleep(5000);
}
// the smallest visible element carrying the marker, and the card around it - what the person actually reads
async function findText(s, marker, ms = 15000) {
  for (let t = 0; t < ms; t += 500) {
    const hit = await s.page.evaluate((mk) => {
      let best = null;
      for (const el of document.querySelectorAll('body *')) {
        if (!el.checkVisibility || !el.checkVisibility()) continue;
        const tx = (el.innerText || '').trim();
        if (tx.includes(mk) && (!best || tx.length < best.length)) best = tx;
      }
      if (!best) return null;
      let card = null;
      for (const el of document.querySelectorAll('body *')) {
        const tx = (el.innerText || '').trim();
        if (tx.includes(mk) && tx.length < 900 && (!card || tx.length > card.length)) card = tx;
      }
      return { text: best, card: card || best };
    }, marker).catch(() => null);
    if (hit) return hit;
    await sleep(500);
  }
  return null;
}
async function under3G(s, path, marker) {
  const cdp = await s.ctx.newCDPSession(s.page);
  await cdp.send('Network.enable');
  await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 400, downloadThroughput: 50 * 1024, uploadThroughput: 50 * 1024 });
  const t0 = Date.now();
  try {
    await s.page.goto(`${ORIGIN}/${path}`, { waitUntil: 'domcontentloaded', timeout: 90000 });
    const hit = marker ? await findText(s, marker, 45000) : true;
    return { ok: !!hit, ms: Date.now() - t0, detail: hit ? 'the record is on the receiver\'s screen on 3G' : 'not on screen within 45 s on 3G' };
  } catch (e) {
    return { ok: false, ms: Date.now() - t0, detail: String(e.message || e).slice(0, 160) };
  } finally {
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 }).catch(() => {});
  }
}
// open the logbook card carrying `marker` and its "Edit Entry", the controls a person taps
async function openEdit(s, marker) {
  await go(s, 'logbook.html');
  const opened = await s.page.evaluate((t) => {
    const card = [...document.querySelectorAll('#entries-list .entry-card, #entries-list [onclick*="openModal"], .entry-card')]
      .find((c) => (c.textContent || '').includes(t));
    if (!card) return false; (card.querySelector('[onclick*="openModal"]') || card).click(); return true;
  }, marker);
  await sleep(900);
  const edited = await s.page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => /edit entry/i.test(x.textContent) && /openEditModal/.test(x.getAttribute('onclick') || ''));
    if (b) { b.click(); return true; } return false;
  });
  await sleep(900);
  return opened && edited;
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
      const live = await findText(s, X.tag, 15000);             // no reload: did the feed bring it?
      return { act: { ok: !!id, detail: `logbook wizard as ${w.m.name}: ${r.toast || 'no toast'}${id ? ` -> entry ${id} on ${machine}` : ' -> NO ROW'}` },
        marker: X.tag, path: 'logbook.html', live: !!live, preRead: live, rec: { table: 'logbook', id } };
    },
    2: async (X) => {   // the supervisor assigns the work order; the worker is pushed and lands on the open list
      const { w, s } = X.S;
      const e = X.rec.entry;
      let ok = false;
      if (!X.faults.has('push-never-fires')) {
        ok = await openEdit(s, X.tag);
        await s.page.evaluate(() => {
          const st = document.getElementById('f-wo-state');
          if (st) { st.value = 'assigned'; st.dispatchEvent(new Event('change', { bubbles: true })); }
        });
        await sleep(400);
        await s.page.evaluate((n) => {
          const wrap = document.getElementById('wo-assigned-wrap'); if (wrap) wrap.style.display = '';
          const f = document.getElementById('f-wo-assigned-to');
          if (f) { f.value = n; f.dispatchEvent(new Event('input', { bubbles: true })); f.dispatchEvent(new Event('change', { bubbles: true })); }
        }, w.m.name);
        await s.page.evaluate(() => { const b = document.getElementById('save-entry-btn'); if (b) b.click(); });
        await sleep(3500);
      }
      const got = psql(`select coalesce(wo_assigned_to,'') || '|' || coalesce(wo_state,'') from logbook where id = '${q(e.id)}'`);
      const push = psql(`select count(*) from service_outbox where consumer = 'notify-push' and created_at >= '${X.t0}'
        and payload->'auth_uids' ? '${w.m.uid}' and payload->>'title' = 'Work order assigned to you' and payload->>'url' = '/logbook.html?status=Open'`);
      return { act: { ok: ok && got.startsWith(w.m.name), detail: `assigned through the entry's own edit modal as ${s.m.name}: wo_assigned_to|wo_state = ${got}` },
        marker: X.tag, path: 'logbook.html?status=Open', rec: { table: 'logbook', id: e.id },
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
      const before = psql(`select coalesce(max(updated_at)::text,'') from analytics_snapshots where hive_id = '${HIVE_ID}'`);
      const tapped = await s.page.evaluate(() => {
        const b = [...document.querySelectorAll('button')].find((x) => /refresh|recompute/i.test((x.innerText || '') + ' ' + (x.getAttribute('aria-label') || '')));
        if (b) { b.click(); return (b.innerText || b.getAttribute('aria-label') || '').trim(); } return null;
      });
      let after = before;
      for (let t = 0; t < 90000 && after === before; t += 3000) {
        await sleep(3000);
        after = psql(`select coalesce(max(updated_at)::text,'') from analytics_snapshots where hive_id = '${HIVE_ID}'`);
      }
      return { act: { ok: !!tapped && after !== before, detail: `the page's own "${tapped || 'no Refresh control'}" as ${s.m.name}: snapshot ${before || 'none'} -> ${after || 'none'}` },
        marker: null, path: 'analytics.html', freshnessRx: /recomputed|just now|updated|minute|today/i,
        rec: { table: 'analytics_snapshots', idCol: 'hive_id', id: HIVE_ID, where: `and updated_at >= '${X.t0}'` } };
    },
    5: async (X) => {   // a repeat of the same breakdown raises the failure-signature alert the supervisor reads
      const { w, s } = X.S;
      const e = X.rec.entry;
      // the worker logs the same breakdown twice more with the first one's root cause, through the API the page writes to
      psql(`update logbook set root_cause = 'Wear' where id = '${q(e.id)}'`);
      for (let i = 1; i <= 2; i++) {
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
      return { act: { ok: !!aid, detail: `3 Wear breakdowns on ${e.machine} as ${w.m.name}; failure-signature-scan as ${s.m.name}: HTTP ${scan.status} ${body}` },
        marker: e.machine, markerRx: /repeat/i, path: 'alert-hub.html', rec: { table: 'v_alert_truth', idCol: 'alert_id', id: aid }, alertTitle: title };
    },
  },
};

// the rows the walk changes in place: today's snapshot and the machine's alerts (restored after); the rest it made is tagged
function snapshotInPlace() {
  return { snaps: psql(`select coalesce(json_agg(row_to_json(t)), '[]') from analytics_snapshots t where hive_id = '${HIVE_ID}'`),
    alerts: psql(`select coalesce(json_agg(row_to_json(t)), '[]') from failure_signature_alerts t where hive_id = '${HIVE_ID}'`) };
}
// ★EVERY STEP OF THE CLEANUP RUNS ON ITS OWN (2026-11-04, the first teeth run): one psql script with ON_ERROR_STOP died
// on a wrong column at its fourth line, and the audit lines, the XP and the restores after it never ran - the walk left
// three audit rows, an XP row and two "new device" registrations behind. A failing step is now recorded in the receipt's
// notes and the rest still run; each restore is ONE transaction, so a failed insert can never leave the rows deleted.
// What a walk leaves besides its own tagged rows: the XP the entry earned (achievement_xp_log, keyed by worker_name +
// earned_at), the audit lines it wrote, and the headless browser each member signed in from (worker_known_devices).
function cleanup(X, kept) {
  const uids = Object.values(X.S).map((s) => `'${s.m.uid}'`).join(',');
  const names = Object.values(X.S).map((s) => `'${q(s.m.name)}'`).join(',');
  const R = 'set session_replication_role = replica;\n';
  const steps = [
    ['tagged logbook rows', `delete from logbook where hive_id = '${HIVE_ID}' and (problem like '${q(X.tag)}%' or id like '${q(X.tag)}%');`],
    ['tagged pushes', `delete from service_outbox where consumer = 'notify-push' and created_at >= '${X.t0}' and payload::text like '%${q(X.tag)}%';`],
    ['assignment pushes', `delete from service_outbox where consumer = 'notify-push' and created_at >= '${X.t0}'
      and payload->>'title' = 'Work order assigned to you' and payload->'auth_uids' ?| array[${uids}];`],
    ['XP the walk earned', `delete from achievement_xp_log where earned_at >= '${X.t0}' and worker_name in (${names});`],
    ['audit lines', `delete from hive_audit_log where hive_id = '${HIVE_ID}' and created_at >= '${X.t0}';`],
    ['the walk\'s devices', `delete from worker_known_devices where first_seen_at >= '${X.t0}' and auth_uid in (${uids});`],
    ['failure alerts restored', `begin; delete from failure_signature_alerts where hive_id = '${HIVE_ID}';
      insert into failure_signature_alerts select * from json_populate_recordset(null::failure_signature_alerts, '${q(kept.alerts)}'); commit;`],
    ['analytics snapshots restored', `begin; delete from analytics_snapshots where hive_id = '${HIVE_ID}';
      insert into analytics_snapshots select * from json_populate_recordset(null::analytics_snapshots, '${q(kept.snaps)}'); commit;`],
  ];
  for (const [what, sql] of steps) {
    try { psql(R + sql); } catch (e) { X.notes.push(`cleanup step "${what}" failed: ${String(e.message || e).slice(0, 200)}`); }
  }
  if (X.notes.some((n) => n.startsWith('cleanup step'))) console.log('  CLEANUP INCOMPLETE: ' + X.notes.filter((n) => n.startsWith('cleanup step')).join(' | '));
}

async function walkPass(browser, pass, foreign) {
  const keys = Object.keys(CAST);
  const vps = ['phone-390', 'desktop-1280'];
  const S = {};
  for (let i = 0; i < keys.length; i++) S[keys[i]] = await session(browser, member(keys[i]), vps[(i + (pass === 'b' ? 1 : 0)) % 2]);
  const X = { S, tag: `GJ-${SCEN}-${pass}-${Date.now()}`, t0: psql('select now()'), rec: {}, notes: [],
    faults: new Set(TEETH ? ['push-never-fires', 'foreign-let-in'] : []) };
  const kept = snapshotInPlace();
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
      // U - the receiver lands by the hop's channel and reads the screen
      let seen = r.preRead || null;
      if (!seen) { await go(R, r.path); seen = r.marker ? await findText(R, r.marker, 20000) : null; }
      if (r.marker) {
        const card = seen ? seen.card : '';
        const who = S[hop.sender].m.name.split(' ')[0];
        const hasWho = new RegExp(who, 'i').test(card);
        const hasWhen = /\d{1,2}:\d{2}|ago|today|just now|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w* \d{1,2}|\d{4}-\d{2}-\d{2}/i.test(card);
        const rxOk = r.markerRx ? r.markerRx.test(card) : true;
        res.U = { ok: !!seen && hasWho && hasWhen && rxOk, live: r.live ?? null, who: hasWho, when: hasWhen,
          said: seen ? card.replace(/\s+/g, ' ').slice(0, 300) : null };
        if (seen && !hasWho) res.U.why = `the screen shows the record but not who did it (${S[hop.sender].m.name})`;
      } else {
        const page = await R.page.evaluate(() => document.body.innerText || '');
        const fresh = page.split('\n').find((l) => r.freshnessRx.test(l) && l.length < 160) || null;
        res.U = { ok: !!fresh, said: fresh };
      }
      // F - psql as the receiver finds the sender's record (or the recipe's own F, e.g. the push)
      const idCol = r.rec.idCol || 'id';
      const recvRows = r.rec.id ? Number(asUser(R.m.uid, `select count(*) from ${r.rec.table} where ${idCol}::text = '${q(r.rec.id)}' ${r.rec.where || ''}`)) : 0;
      res.F = r.F ? r.F() : { ok: recvRows >= 1, detail: `${r.rec.table} ${r.rec.id || '(none)'} read as ${R.m.name} through RLS: ${recvRows} row(s)` };
      // I - the receiver may, a member of another hive may not
      const witness = X.faults.has('foreign-let-in') ? { user: R.m.user, uid: R.m.uid } : foreign;
      const forRows = r.rec.id ? Number(asUser(witness.uid, `select count(*) from ${r.rec.table} where ${idCol}::text = '${q(r.rec.id)}'`)) : -1;
      res.I = { ok: recvRows >= 1 && forRows === 0, receiver_rows: recvRows, foreign: witness.user, foreign_rows: forRows };
      // A - the receiver's landing on 3G, the sender's network untouched
      res.A = await under3G(R, r.path, r.marker);
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
const cells = ['act', 'U', 'F', 'I', 'A'];
const hopOk = (h) => !h.unbuilt && cells.every((c) => h[c] && h[c].ok);
const report = { generated: new Date().toISOString(), instrument: 'tools/prove_group_journeys.mjs (playwright, one browser context per member) + postgres (psql as the receiver)',
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
