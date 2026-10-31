// prove_hive_scale_races — Wave HS (the hive at thirty), lens W1, the BROWSER half: two members change the same item at
// once, each in their own browser, and the page tells the one who lost (2026-10-30).
//
// tools/prove_hive_scale_writes.mjs replays each race in the database, as the two people, with the page's own write, and
// proves the guard holds (A's write changes 0 rows, B's change survives). It names the sentence the page then says, but it
// cannot see a screen. This walks it: member A opens the item in one browser, member B changes it in another, and A acts -
// through the page's own controls - and then the walk reads two things:
//   told   - A's screen carries the page's sentence for the loser (never a success toast over a write that did nothing)
//   kept   - the database still holds B's change (never a silent overwrite)
// A is walked at phone-390 and B at desktop-1280, then the two swap viewports, so each row is measured at both.
// Every row the race touches is snapshotted first and restored after (triggers off for the restore), so the 30-member
// hive the other gates read is left as it was.
//
//   node tools/prove_hive_scale_races.mjs [HS401 HS407 ...]    -> hive_scale_races_report.json; exit 1 on any failure
import { chromium } from 'playwright';
import { spawnSync } from 'child_process';
import { readFileSync, writeFileSync } from 'fs';

const ORIGIN = 'http://127.0.0.1:5000/workhive';
const SB = 'http://127.0.0.1:54321';
const KEY = 'sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH';   // the LOCAL stack's publishable key (public by design)
const HIVE = '30303030-3030-4030-8030-303030303030';
const OUT = 'hive_scale_races_report.json';
const ONLY = new Set(process.argv.slice(2).filter((a) => /^(HS\d+|X-[A-Z]+)$/.test(a)));
const VP = { 'phone-390': { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }, 'desktop-1280': { viewport: { width: 1280, height: 800 } } };
const USER = { 'Joel Cruz': 'joelcruz', 'Ana Reyes': 'anareyes', 'Ernesto Villareal': 'ernestovillareal', 'Corazon Bautista': 'corazonbautista', 'Danilo Pascual': 'danilopascual',
  'Jun Salvador': 'junvanowner' };   // a solo owner: no hive, no machines in the database yet
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let BROWSER = null;   // a third person's session, for a race whose claim is about who else may touch the record
const sqlq = (s) => String(s).replace(/'/g, "''");

function psql(sql) {
  const r = spawnSync('docker', ['exec', '-i', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-At', '-v', 'ON_ERROR_STOP=1'],
    { input: sql, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 });
  if (r.status !== 0) throw new Error('psql: ' + (r.stderr || '').slice(0, 300));
  return (r.stdout || '').trim().split('\n').filter((l) => l && !/^(SET|INSERT|UPDATE|DELETE)/.test(l)).join('\n');
}
// one row as JSON, and its restore (every column, triggers off - a restore is not a member's act)
const snap = (table, id) => psql(`select row_to_json(t) from ${table} t where id = '${sqlq(id)}'`);
function restore(table, json) {
  if (!json) return;
  psql(`set session_replication_role = replica;
    update ${table} t set (${cols(table).join(', ')}) = (select ${cols(table).map((c) => 'r.' + c).join(', ')}
      from json_populate_record(null::${table}, '${sqlq(json)}') r) where t.id = (('${sqlq(json)}')::json->>'id')::${idType(table)};`);
}
const _cols = {};
function cols(table) {
  if (!_cols[table]) _cols[table] = psql(`select string_agg(quote_ident(column_name), ',' order by ordinal_position) from information_schema.columns
    where table_schema = 'public' and table_name = '${table}' and is_generated = 'NEVER' and column_name <> 'id'`).split(',');
  return _cols[table];
}
const idType = (table) => psql(`select data_type from information_schema.columns where table_schema='public' and table_name='${table}' and column_name='id'`) === 'uuid' ? 'uuid' : 'text';

async function session(browser, person, vpName) {
  const ctx = await browser.newContext({ ...VP[vpName], timezoneId: 'Asia/Manila', serviceWorkers: 'block' });
  const tok = await (await fetch(`${SB}/auth/v1/token?grant_type=password`, { method: 'POST',
    headers: { apikey: KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: `${USER[person]}@auth.workhiveph.com`, password: 'test1234' }) })).json();
  if (!tok.access_token) throw new Error(`sign-in failed for ${person}`);
  const role = psql(`select role from hive_members where hive_id = '${HIVE}' and worker_name = '${sqlq(person)}' and status = 'active'`);
  await ctx.addInitScript(([t, hive, name, r]) => {
    try {
      if (!localStorage.getItem('sb-127-auth-token')) localStorage.setItem('sb-127-auth-token', JSON.stringify(t));
      localStorage.setItem('wh_last_worker', name);
      if (r) { localStorage.setItem('wh_active_hive_id', hive); localStorage.setItem('wh_hive_role', r); }
      else { localStorage.removeItem('wh_active_hive_id'); localStorage.removeItem('wh_hive_role'); }   // a solo account
    } catch (_) { /* storage blocked */ }
  }, [tok, HIVE, person, role]);
  const page = await ctx.newPage();
  page.on('dialog', (d) => d.accept().catch(() => {}));   // a confirm() is the person saying yes
  const said = [];
  await page.exposeFunction('__whSaid', (t) => said.push(t));
  await page.addInitScript(() => {
    // every message the page shows the person: a toast, a status line, an inline alert - recorded as it appears
    const seen = new WeakMap();
    new MutationObserver(() => {
      for (const el of document.querySelectorAll('#toast, .toast, [role="alert"], [role="status"], [aria-live]')) {
        const t = (el.innerText || '').trim();
        if (t && seen.get(el) !== t) { seen.set(el, t); try { window.__whSaid(t); } catch (_) { /* not yet exposed */ } }
      }
    }).observe(document, { subtree: true, childList: true, characterData: true });
  });
  return { ctx, page, said, person, vpName };
}

async function open(s, file) {
  await s.page.goto(`${ORIGIN}/${file}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await sleep(6000);
}
async function waitSaid(s, rx, ms = 10000) {
  for (let t = 0; t < ms; t += 250) {
    const hit = s.said.find((x) => rx.test(x));
    // a live region can be a whole chat log: quote the line that carries the sentence, not the log
    if (hit) return hit.split(/\r?\n/).find((l) => rx.test(l)) || hit;
    // ...or a sentence the page writes into a form's own error line, which is not a live region
    const onScreen = await s.page.evaluate((src) => {
      const re = new RegExp(src, 'i');
      let best = null;   // the SMALLEST element that carries the sentence is the sentence, not its container
      for (const el of document.querySelectorAll('p, div, span, li')) {
        if (el.children.length > 3 || !el.checkVisibility || !el.checkVisibility()) continue;
        const t = (el.innerText || '').trim();
        if (t && t.length < 400 && re.test(t) && (!best || t.length < best.length)) best = t;
      }
      return best;
    }, rx.source).catch(() => null);
    if (onScreen) return onScreen;
    await sleep(250);
  }
  return null;
}
// a tap on the control the person would tap (scrolled to, then clicked); a control the layout hides falls back to its own click()
async function tap(s, sel) {
  const loc = s.page.locator(sel).first();
  await loc.waitFor({ state: 'attached', timeout: 15000 }).catch(() => { throw new Error(`${s.person} @ ${s.vpName}: no ${sel} on screen`); });
  try { await loc.scrollIntoViewIfNeeded({ timeout: 3000 }); await loc.click({ timeout: 4000 }); }
  catch (_) { await loc.evaluate((el) => el.click()); }
}
// the shared confirm / prompt modal (utils.js whConfirm / whPrompt): a reason where it asks for one, then its OK
async function modalOk(s, ms = 4000) {
  const ok = s.page.locator('[data-wh-modal-ok]').first();
  try { await ok.waitFor({ state: 'visible', timeout: ms }); } catch (_) { return false; }
  const field = s.page.locator('[role="dialog"] input:visible, [role="dialog"] textarea:visible, [aria-modal="true"] input:visible, [aria-modal="true"] textarea:visible').first();
  if (await field.count()) await field.fill('Race walk - two supervisors at once').catch(() => {});
  await ok.click();
  return true;
}
// rows a race left behind in tables it does not own (an audit line, a dismissal, a ledger row) - triggers off
function sweep(t0, tables) {
  psql('set session_replication_role = replica;\n' + tables.map((t) => (/^delete /.test(t)
    ? t : `delete from ${t} where hive_id = '${HIVE}' and created_at >= '${t0}';`)).join('\n'));
}

// ── the races ────────────────────────────────────────────────────────────────────────────────────────────────────────
// a: the one who acts second (and must be told); b: the one who acts first. pick(): the item, chosen ONCE before either acts.
const RACES = [
  {
    id: 'HS401', page: 'community.html', table: 'community_posts', a: 'Ana Reyes', b: 'Ernesto Villareal',
    claim: "the author's edit after a supervisor pinned the post: the author is told, the pin stays",
    // the author can only edit a post their feed has loaded - picked from A's own screen
    pick: async (A) => A.page.evaluate((me) => (allPosts.find((p) => p.author_name === me && !p.pinned) || {}).id || '', A.person),
    aOpen: async (A, id) => { await A.page.evaluate((i) => openEditor(i), id); await sleep(800); },
    bAct: async (B, id) => { await B.page.evaluate((i) => togglePin(i, false), id); await sleep(2500); },
    aAct: async (A) => {
      await A.page.fill('#post-content', 'Edited during the race - HS401 walk');
      await A.page.click('#btn-submit-post');
    },
    told: /changed while you were editing/i,
    kept: (id) => psql(`select pinned::text || '|' || (content = 'Edited during the race - HS401 walk')::text from community_posts where id = '${id}'`) === 'true|false',
    keptSays: 'the pin stays and the post keeps its pinned text',
  },
  {
    id: 'HS407', page: 'hive.html', table: 'hive_members', a: 'Corazon Bautista', b: 'Ernesto Villareal',
    claim: 'two supervisors remove the same member: the second is told, the trail records one removal',
    pick: async () => psql(`select id || '|' || worker_name from hive_members where hive_id = '${HIVE}' and status = 'active' and role = 'worker'
      and worker_name not in ('Joel Cruz', 'Ana Reyes') order by worker_name limit 1`),
    snapId: (v) => v.split('|')[0],
    aOpen: async () => {},
    bAct: async (B, v) => { const [mid, name] = v.split('|'); const run = B.page.evaluate(([i, n]) => kickMember(i, n), [mid, name]); await modalOk(B); await run; await sleep(1500); },
    aAct: async (A, v) => { const [mid, name] = v.split('|'); const run = A.page.evaluate(([i, n]) => kickMember(i, n), [mid, name]); await modalOk(A); await run; },
    told: /already removed by another supervisor/i,
    kept: (v) => psql(`select status || '|' || (select count(*) from hive_audit_log where target_id = '${v.split('|')[0]}' and action = 'kick_member'
      and created_at > now() - interval '5 minutes') from hive_members where id = '${v.split('|')[0]}'`) === 'kicked|1',
    keptSays: 'the member is removed once, and the trail holds one removal',
    cleanup: (t0) => sweep(t0, ['hive_audit_log']),
  },
  {
    id: 'HS395', page: 'asset-hub.html', table: 'asset_nodes', a: 'Corazon Bautista', b: 'Ernesto Villareal',
    claim: 'one supervisor approves a machine while another rejects it: the second is told, the approval stands',
    pick: async () => psql(`select id from asset_nodes where hive_id = '${HIVE}' and status = 'pending' and deleted_at is null order by created_at limit 1`),
    aOpen: async () => {},
    bAct: async (B, id) => { await tap(B, `button[data-action="asset-approve"][data-id="${id}"]`); await modalOk(B, 1500); await sleep(2500); },
    aAct: async (A, id) => { await tap(A, `button[data-action="asset-reject"][data-id="${id}"]`); await modalOk(A); },
    told: /already handled by another supervisor/i,
    kept: (id) => psql(`select status from asset_nodes where id = '${id}'`) === 'approved',
    keptSays: 'the machine stays approved',
    cleanup: (t0) => sweep(t0, ['hive_audit_log', 'pm_assets']),
  },
  {
    id: 'HS393', page: 'alert-hub.html', table: 'alert_dismissals', a: 'Joel Cruz', b: 'Ernesto Villareal',
    claim: 'a supervisor handles an alert while a worker snoozes it: the worker is told who handled it, nothing is recorded under their name',
    pick: async (A) => A.page.evaluate(() => { const b = document.querySelector('button[data-dismiss-key]'); return b ? b.getAttribute('data-dismiss-key') : ''; }),
    snapId: () => null,
    aOpen: async () => {},
    bAct: async (B, key) => { await B.page.waitForSelector(`button[data-dismiss-key="${key}"]`, { state: 'attached', timeout: 15000 });
      await B.page.evaluate((k) => dismissAlert(k, 'handled'), key); await sleep(2500); },
    aAct: async (A, key) => { await tap(A, `button[data-dismiss-key="${key}"]`); },
    told: /already handled this alert/i,
    kept: (key) => psql(`select actor from alert_dismissals where hive_id = '${HIVE}' and alert_key = '${sqlq(key)}'`) === 'Ernesto Villareal',
    keptSays: "the dismissal stays Ernesto's",
    cleanup: (t0) => sweep(t0, ['alert_dismissals', 'hive_audit_log']),
  },
  {
    id: 'HS421', page: 'inventory.html', table: 'inventory_items', a: 'Corazon Bautista', b: 'Ernesto Villareal',
    claim: "two supervisors edit the same part: the second save is refused and said, the first one's bin stays",
    pick: async () => psql(`select id from inventory_items where hive_id = '${HIVE}' and status = 'approved' and coalesce(qty_on_hand, 0) > 2 order by part_number limit 1`),
    aOpen: async (A, id) => { await A.page.evaluate((i) => openAddModal(i), id); await sleep(800); },
    bAct: async (B, id) => { await B.page.evaluate((i) => openAddModal(i), id); await sleep(800);
      await B.page.fill('#f-location', 'Bay 2'); await B.page.evaluate(() => submitPart()); await sleep(3000); },
    aAct: async (A) => { await A.page.fill('#f-location', 'Bay 7'); await A.page.evaluate(() => submitPart()); },
    told: /just edited this part|just updated this|someone else/i,
    kept: (id) => psql(`select bin_location from inventory_items where id = '${id}'`) === 'Bay 2',
    keptSays: 'the part keeps Bay 2',
    state: (id) => psql(`select bin_location || ' @ ' || updated_at from inventory_items where id = '${id}'`),
    cleanup: (t0) => sweep(t0, ['hive_audit_log']),
  },
  {
    id: 'HS423', page: 'inventory.html', table: 'inventory_items', a: 'Joel Cruz', b: 'Ana Reyes',
    claim: 'two members take the last unit: the second is told the shelf was empty, and no movement is recorded for them',
    pick: async () => psql(`select id from inventory_items where hive_id = '${HIVE}' and status = 'approved' and coalesce(qty_on_hand, 0) > 2 order by part_number desc limit 1`),
    // the shelf holds ONE: set inside the snapshot window, put back by the restore
    // staged the way the product stages it: a supervisor's count adjustment (a ledger row), never a raw write to a
    // ledger-derived balance - that one was reverted and the race ran on 22 units (feedback: staging a ledger-derived column)
    aOpen: async (A, id) => { psql(`begin; select set_config('request.jwt.claims', json_build_object('sub', (select auth_uid from hive_members
        where hive_id = '${HIVE}' and worker_name = 'Ernesto Villareal'), 'role', 'authenticated')::text, true);
      set local role authenticated;
      select public.inventory_adjust(p_item_id => '${id}', p_expected_qty => (select qty_on_hand from inventory_items where id = '${id}'), p_new_qty => 1, p_note => 'race walk: one left');
      commit;`);
      await A.page.reload({ waitUntil: 'domcontentloaded' }); await sleep(6000);
      await A.page.evaluate((i) => openUseModal(i), id); await sleep(800); await A.page.fill('#use-qty', '1'); },
    bAct: async (B, id) => { await B.page.reload({ waitUntil: 'domcontentloaded' }); await sleep(6000);
      await B.page.evaluate((i) => openUseModal(i), id); await sleep(800); await B.page.fill('#use-qty', '1');
      await B.page.evaluate(() => submitUse()); await sleep(3000); },
    aAct: async (A) => { await A.page.evaluate(() => submitUse()); },
    // two truthful tellings: a screen the live update already reached refuses before sending ("Only 0 pcs on hand.");
    // a stale one sends, the deduct clamps, and the page reads back that nothing moved ("... Someone took it first")
    told: /Only 0 (?:pcs|units?)? ?(?:of 1 )?(?:on hand|.*on the shelf)|Someone took it first/i,
    kept: (id) => psql(`select qty_on_hand || '|' || (select count(*) filter (where type = 'use' and qty_change <> 0) || '|'
        || count(*) filter (where worker_name = 'Joel Cruz' and qty_change <> 0) from inventory_transactions
        where item_id = '${id}' and created_at > now() - interval '5 minutes') from inventory_items where id = '${id}'`) === '0|1|0',
    keptSays: "the shelf reads 0, one use moved stock, and nothing moved for the second member",
    state: (id) => psql(`select qty_on_hand from inventory_items where id = '${id}'`) + ' / ' + psql(`select string_agg(worker_name || ':' || qty_change, ', ' order by created_at) from inventory_transactions where item_id = '${id}' and created_at > now() - interval '5 minutes'`),
    cleanup: (t0, id) => sweep(t0, [`delete from inventory_transactions where item_id = '${id}' and created_at >= '${t0}';`, 'hive_audit_log']),
  },
  {
    id: 'HS425', page: 'logbook.html', table: 'asset_nodes', a: 'Corazon Bautista', b: 'Ernesto Villareal',
    claim: 'two supervisors edit the same machine in the logbook: the second save is refused and said, the first location stays',
    pick: async () => psql(`select id from asset_nodes where hive_id = '${HIVE}' and status = 'approved' and tag = 'BRM-P-101'`),
    aOpen: async (A, id) => { await A.page.evaluate((i) => openEditAsset(i), id); await sleep(800); },
    bAct: async (B, id) => { await B.page.evaluate((i) => openEditAsset(i), id); await sleep(800);
      await B.page.fill('#edit-asset-location', 'Unit 1 pump house'); await B.page.evaluate(() => saveEditAsset()); await sleep(3000); },
    aAct: async (A) => { await A.page.fill('#edit-asset-location', 'Tank farm'); await A.page.evaluate(() => saveEditAsset()); },
    told: /changed this asset while you were editing/i,
    kept: (id) => psql(`select location from asset_nodes where id = '${id}'`) === 'Unit 1 pump house',
    keptSays: 'the machine keeps Unit 1 pump house',
    cleanup: (t0) => sweep(t0, ['hive_audit_log']),
  },
  {
    id: 'HS455', page: 'project-manager.html', table: 'project_change_orders', a: 'Corazon Bautista', b: 'Ernesto Villareal',
    claim: 'one supervisor approves a change order while another rejects it: the second is told it was already decided',
    pick: async () => psql(`select id || '|' || project_id from project_change_orders where hive_id = '${HIVE}' and status = 'pending' order by id limit 1`),
    snapId: (v) => v.split('|')[0],
    aOpen: async (A, v) => { await A.page.evaluate((p) => openDetail(p), v.split('|')[1]); await sleep(3000); await tap(A, '#detail-tabs button[data-pane="changes"]'); await sleep(1500); },
    bAct: async (B, v) => { await B.page.evaluate((p) => openDetail(p), v.split('|')[1]); await sleep(3000);
      await tap(B, '#detail-tabs button[data-pane="changes"]'); await sleep(1500);
      await tap(B, `[onclick="approveCO('${v.split('|')[0]}')"]`); await modalOk(B, 1500); await sleep(3000); },
    aAct: async (A, v) => { await tap(A, `[onclick="rejectCO('${v.split('|')[0]}')"]`); await modalOk(A); },
    told: /already decided by another supervisor/i,
    kept: (v) => psql(`select status from project_change_orders where id = '${v.split('|')[0]}'`) === 'approved',
    keptSays: 'the change order stays approved',
    cleanup: (t0) => sweep(t0, ['hive_audit_log']),
  },
  {
    id: 'HS457', page: 'project-manager.html', table: 'project_items', a: 'Joel Cruz', b: 'Ana Reyes',
    claim: 'two members move the same task: the second is told where it went, and the first move stands',
    pick: async (A) => {
      const proj = psql(`select project_id from project_items where hive_id = '${HIVE}' and status = 'pending' group by project_id order by count(*) desc limit 1`);
      await A.page.evaluate((p) => openDetail(p), proj); await sleep(3000);
      await tap(A, '#detail-tabs button[data-pane="scope"]'); await sleep(1500);
      const ids = psql(`select string_agg(id::text, ',') from project_items where project_id = '${proj}' and status = 'pending'`).split(',');
      const it = await A.page.evaluate((want) => { for (const b of document.querySelectorAll('button[onclick^="cycleScopeStatus("]')) {
        const i = b.getAttribute('onclick').match(/'([^']+)'/)[1]; if (want.includes(i)) return i; } return ''; }, ids);
      return it ? it + '|' + proj : '';
    },
    snapId: (v) => v.split('|')[0],
    // A's phone has lost its live connection (a basement, a dead cell): the screen A taps still says pending. With the
    // connection up the move reaches A first and A's tap is an honest next move - that path is not a race.
    aOpen: async (A) => { await A.page.evaluate(() => db.removeAllChannels()); await sleep(500); },
    bAct: async (B, v) => { await B.page.evaluate((p) => openDetail(p), v.split('|')[1]); await sleep(3000);
      await tap(B, '#detail-tabs button[data-pane="scope"]'); await sleep(1500);
      await tap(B, `button[onclick^="cycleScopeStatus('${v.split('|')[0]}'"]`); await sleep(3000); },
    aAct: async (A, v) => { await tap(A, `button[onclick^="cycleScopeStatus('${v.split('|')[0]}'"]`); },
    told: /while you were looking/i,
    kept: (v) => psql(`select status from project_items where id = '${v.split('|')[0]}'`) === 'in_progress',
    keptSays: 'the task stays where the first member moved it',
    state: (v) => psql(`select status || ' @ ' || updated_at from project_items where id = '${v.split('|')[0]}'`),
    cleanup: (t0) => sweep(t0, ['hive_audit_log']),
  },
  {
    id: 'HS459', page: 'project-manager.html', table: 'project_progress_logs', a: 'Corazon Bautista', b: 'Ernesto Villareal',
    claim: 'two supervisors acknowledge the same progress report: the second is told, the first acknowledgement stands',
    // the report is one A's Daily log actually offers to acknowledge (the pane shows the newest; an older one is not on screen)
    pick: async (A) => {
      const proj = psql(`select project_id from project_progress_logs where hive_id = '${HIVE}' and acknowledged_at is null group by project_id order by count(*) desc limit 1`);
      await A.page.evaluate((p) => openDetail(p), proj); await sleep(3000);
      await tap(A, '#detail-tabs button[data-pane="progress"]'); await sleep(1500);
      const log = await A.page.evaluate(() => { const b = document.querySelector('[onclick^="ackLog("]'); return b ? b.getAttribute('onclick').match(/'([^']+)'/)[1] : ''; });
      return log ? log + '|' + proj : '';
    },
    snapId: (v) => v.split('|')[0],
    // with the connection up, B's acknowledgement reaches A's screen and its button leaves it (measured) - the race needs a
    // screen that has not heard yet
    aOpen: async (A) => { await A.page.evaluate(() => db.removeAllChannels()); await sleep(500); },
    bAct: async (B, v) => { await B.page.evaluate((p) => openDetail(p), v.split('|')[1]); await sleep(3000);
      await tap(B, '#detail-tabs button[data-pane="progress"]'); await sleep(1500);
      await tap(B, `[onclick="ackLog('${v.split('|')[0]}')"]`); await sleep(3000); },
    aAct: async (A, v) => { await tap(A, `[onclick="ackLog('${v.split('|')[0]}')"]`); },
    told: /already acknowledged by someone else/i,
    kept: (v) => psql(`select acknowledged_by from project_progress_logs where id = '${v.split('|')[0]}'`) === 'Ernesto Villareal',
    keptSays: "the acknowledgement stays Ernesto's",
    cleanup: (t0) => sweep(t0, ['hive_audit_log']),
  },
  {
    id: 'HS463', page: 'project-manager.html', table: 'projects', a: 'Corazon Bautista', b: 'Ernesto Villareal',
    claim: "two supervisors edit the same project: the second save is refused and said, the first one's edit stays",
    pick: async () => psql(`select project_id from project_change_orders where hive_id = '${HIVE}' order by id limit 1`),
    aOpen: async (A, id) => { await A.page.evaluate((p) => openDetail(p), id); await sleep(3000); await A.page.evaluate(() => openEditProject()); await sleep(800); },
    bAct: async (B, id) => { await B.page.evaluate((p) => openDetail(p), id); await sleep(3000); await B.page.evaluate(() => openEditProject()); await sleep(800);
      await B.page.locator('#form-project input[type="text"]').first().fill("Race walk - Ernesto's name");
      await B.page.evaluate(() => saveProject()); await sleep(3000); },
    aAct: async (A) => { await A.page.locator('#form-project input[type="text"]').first().fill("Race walk - Corazon's name");
      await A.page.evaluate(() => saveProject()); },
    told: /modified by someone else/i,
    kept: (id) => psql(`select name from projects where id = '${id}'`) === "Race walk - Ernesto's name",
    keptSays: "the project keeps Ernesto's edit",
    cleanup: (t0) => sweep(t0, ['hive_audit_log']),
  },
  {
    id: 'HS397', page: 'asset-hub.html', table: 'rcm_fmea_modes', a: 'Corazon Bautista', b: 'Ernesto Villareal',
    claim: "two supervisors approve the same proposed failure mode: the second is told, the first approver's name stays",
    pick: async () => psql(`select id || '|' || asset_id from rcm_fmea_modes where hive_id = '${HIVE}' and approved_at is null order by created_at limit 1`),
    snapId: (v) => v.split('|')[0],
    // the machine opened the way a shared link opens it (?node_id=), its FMEA tab the one that opens first
    aOpen: async (A, v) => { await A.page.goto(`${ORIGIN}/asset-hub.html?node_id=${v.split('|')[1]}`, { waitUntil: 'domcontentloaded' }); await sleep(6000);
      await A.page.evaluate(() => (window.db && window.db.removeAllChannels) ? window.db.removeAllChannels() : null).catch(() => {}); },
    bAct: async (B, v) => { await B.page.goto(`${ORIGIN}/asset-hub.html?node_id=${v.split('|')[1]}`, { waitUntil: 'domcontentloaded' }); await sleep(6000);
      await tap(B, `button[data-action="approve"][data-id="${v.split('|')[0]}"]`); await modalOk(B, 1500); await sleep(3000); },
    aAct: async (A, v) => { await tap(A, `button[data-action="approve"][data-id="${v.split('|')[0]}"]`); await modalOk(A, 1500); },
    told: /already approved/i,
    kept: (v) => psql(`select approved_by from rcm_fmea_modes where id = '${v.split('|')[0]}'`) === 'Ernesto Villareal',
    keptSays: "the mode keeps Ernesto as its approver",
    cleanup: (t0) => sweep(t0, ['hive_audit_log']),
  },
  {
    id: 'HS409', page: 'hive.html', table: 'logbook', a: 'Corazon Bautista', b: 'Ernesto Villareal',
    claim: "two supervisors open the hive board at once: a member's hive-less entry stays theirs - no page load moves it into the hive",
    // a member's personal entry (no hive): planted, then both supervisors load the board together
    pick: async () => psql(`set session_replication_role = replica;
      insert into logbook (id, worker_name, auth_uid, machine, problem, status, date, created_at)
      select 'hs-race-personal-entry', 'Joel Cruz', auth_uid, 'Home garage compressor', 'personal note - race walk', 'Open', now(), now()
      from hive_members where hive_id = '${HIVE}' and worker_name = 'Joel Cruz'
      on conflict (id) do nothing;
      select 'hs-race-personal-entry';`),
    aOpen: async () => {},
    bAct: async (B) => { await B.page.reload({ waitUntil: 'domcontentloaded' }); },
    aAct: async (A) => { await A.page.reload({ waitUntil: 'domcontentloaded' }); await sleep(8000); },
    told: null,   // nothing is written, so there is nothing to tell
    kept: (id) => psql(`select coalesce(hive_id::text, 'personal') from logbook where id = '${id}'`) === 'personal',
    keptSays: "Joel's personal entry stays personal after both supervisors' board loads (runHiveIdBackfill writes nothing)",
    cleanup: () => psql(`set session_replication_role = replica; delete from logbook where id = 'hs-race-personal-entry';`),
  },
  // ── APPEND: both changes land, and each member's screen shows the other's ─────────────────────────────────────────
  {
    id: 'HS403', page: 'community.html', table: 'community_reactions', a: 'Ana Reyes', b: 'Ernesto Villareal',
    claim: "two members react to the same post at once: both reactions land, and each screen counts both",
    pick: async (A) => {
      const ids = await A.page.evaluate(() => allPosts.slice(0, 20).map((p) => p.id));
      for (const pid of ids) {
        const n = psql(`select count(*) from community_reactions where post_id = '${pid}' and emoji = 'wrench' and worker_name in ('Ana Reyes', 'Ernesto Villareal')`);
        if (n === '0') return pid;
      }
      return '';
    },
    snapId: () => null,
    aOpen: async () => {},
    bAct: async (B, id) => { await B.page.evaluate(([i, h]) => toggleReaction(i, h, 'wrench'), [id, HIVE]); await sleep(2500); },
    aAct: async (A, id) => { await A.page.evaluate(([i, h]) => toggleReaction(i, h, 'wrench'), [id, HIVE]); await sleep(4000); },
    told: null,
    kept: (id) => psql(`select count(*) from community_reactions where post_id = '${id}' and emoji = 'wrench' and worker_name in ('Ana Reyes', 'Ernesto Villareal')`) === '2',
    keptSays: 'both wrenches are on the post',
    // A's own count: the post's wrench total as A's screen shows it, against the table
    seen: async (A, id) => {
      const shown = await A.page.evaluate((i) => (document.getElementById(`rxn-wrench-${i}`) || {}).textContent || '', id);
      const total = psql(`select count(*) from community_reactions where post_id = '${id}' and emoji = 'wrench'`);
      return { ok: shown.replace('+', '') === total, says: `A's screen counts ${shown || '0'} wrench(es); the table holds ${total}` };
    },
    cleanup: (t0, id) => sweep(t0, [`delete from community_reactions where post_id = '${id}' and emoji = 'wrench' and created_at >= '${t0}';`]),
  },
  {
    id: 'HS405', page: 'community.html', table: 'community_replies', a: 'Ana Reyes', b: 'Ernesto Villareal',
    claim: "two members reply to the same post at once: both replies land, and the thread shows both",
    pick: async (A) => A.page.evaluate(() => (allPosts[0] || {}).id || ''),
    snapId: () => null,
    aOpen: async (A, id) => { await A.page.evaluate((i) => openThread(i), id); await sleep(2000); },
    bAct: async (B, id) => { await B.page.evaluate((i) => openThread(i), id); await sleep(2000);
      await B.page.fill('#reply-content', "Ernesto's reply - race walk"); await B.page.evaluate(() => submitReply()); await sleep(3000); },
    aAct: async (A) => { await A.page.fill('#reply-content', "Ana's reply - race walk"); await A.page.evaluate(() => submitReply()); await sleep(4000); },
    told: null,
    kept: (id) => psql(`select count(*) from community_replies where post_id = '${id}' and content in ('Ernesto''s reply - race walk', 'Ana''s reply - race walk')`) === '2',
    keptSays: 'both replies are on the post',
    seen: async (A) => {
      const t = await A.page.evaluate(() => document.body.innerText);
      const both = t.includes("Ernesto's reply - race walk") && t.includes("Ana's reply - race walk");
      return { ok: both, says: both ? "Ana's open thread shows Ernesto's reply beside her own" : "Ana's thread does not show both replies" };
    },
    cleanup: (t0, id) => sweep(t0, [`delete from community_replies where post_id = '${id}' and created_at >= '${t0}';`]),
  },
  {
    id: 'HS461', page: 'project-manager.html', table: 'project_roles', a: 'Corazon Bautista', b: 'Ernesto Villareal',
    claim: "two supervisors give the same person the same project role: one row, and the second is told",
    pick: async () => psql(`select p.id from projects p where p.hive_id = '${HIVE}' and p.deleted_at is null and p.project_type <> 'workorder'
      and not exists (select 1 from project_roles r where r.project_id = p.id and r.worker_name = 'Wilson Ocampo' and r.role = 'reviewer' and r.deleted_at is null)
      order by p.project_code limit 1`),
    snapId: () => null,
    aOpen: async (A, id) => { await A.page.evaluate((p) => openDetail(p), id); await sleep(3000); await tap(A, '#detail-tabs button[data-pane="roles"]'); await sleep(1500);
      await A.page.evaluate(() => openAddRole()); await sleep(800);
      await A.page.selectOption('#r-worker', 'Wilson Ocampo'); await A.page.selectOption('#r-role', 'reviewer'); },
    bAct: async (B, id) => { await B.page.evaluate((p) => openDetail(p), id); await sleep(3000); await tap(B, '#detail-tabs button[data-pane="roles"]'); await sleep(1500);
      await B.page.evaluate(() => openAddRole()); await sleep(800);
      await B.page.selectOption('#r-worker', 'Wilson Ocampo'); await B.page.selectOption('#r-role', 'reviewer');
      await B.page.evaluate(() => saveRole()); await sleep(3000); },
    aAct: async (A) => { await A.page.evaluate(() => saveRole()); },
    told: /already has the reviewer role on this project/i,
    kept: (id) => psql(`select count(*) from project_roles where project_id = '${id}' and worker_name = 'Wilson Ocampo' and role = 'reviewer' and deleted_at is null`) === '1',
    keptSays: 'Wilson Ocampo holds the reviewer role once',
    cleanup: (t0, id) => sweep(t0, [`delete from project_roles where project_id = '${id}' and assigned_at >= '${t0}';`, 'hive_audit_log']),
  },
  {
    id: 'HS453', page: 'pm-scheduler.html', table: 'pm_completions', a: 'Joel Cruz', b: 'Ana Reyes',
    claim: "two members complete the same PM task the same day: each keeps their completion, and a repeat by the same person is told it is already recorded",
    pick: async () => psql(`select s.id || '|' || s.asset_id from pm_scope_items s join pm_assets a on a.id = s.asset_id
      where s.hive_id = '${HIVE}' and a.deleted_at is null and not exists (select 1 from pm_completions c where c.scope_item_id = s.id
      and c.worker_name in ('Joel Cruz', 'Ana Reyes') and c.completed_at > now() - interval '1 day') order by s.item_text limit 1`),
    snapId: () => null,
    aOpen: async (A, v) => { const [sid, aid] = v.split('|');
      await A.page.evaluate(([a, s]) => { openDetail(a); markDone(s); document.getElementById('sheet-log-toggle').checked = false; }, [aid, sid]); await sleep(1000); },
    bAct: async (B, v) => { const [sid, aid] = v.split('|');
      await B.page.evaluate(([a, s]) => { openDetail(a); markDone(s); document.getElementById('sheet-log-toggle').checked = false; }, [aid, sid]); await sleep(1000);
      await B.page.evaluate(() => submitCompletion()); await sleep(3500); },
    // A saves what they were holding (their own completion lands beside B's), then - the same day - does it once more
    aAct: async (A, v) => { const [sid, aid] = v.split('|');
      await A.page.evaluate(() => submitCompletion()); await sleep(3500);
      await A.page.evaluate(([a, s]) => { openDetail(a); markDone(s); document.getElementById('sheet-log-toggle').checked = false; }, [aid, sid]); await sleep(1000);
      await A.page.evaluate(() => submitCompletion()); },
    told: /Already recorded for this task today/i,
    kept: (v) => psql(`select string_agg(worker_name || ':' || n, ',' order by worker_name) from (select worker_name, count(*) n from pm_completions
      where scope_item_id = '${v.split('|')[0]}' and completed_at > now() - interval '10 minutes' group by worker_name) x`) === 'Ana Reyes:1,Joel Cruz:1',
    keptSays: "Joel and Ana each hold one completion of the task; Joel's repeat added none",
    cleanup: (t0, v) => sweep(t0, [`delete from pm_completions where scope_item_id = '${v.split('|')[0]}' and completed_at >= '${t0}';`, 'hive_audit_log']),
  },
  {
    id: 'HS427', page: 'logbook.html', table: 'pm_completions', a: 'Joel Cruz', b: 'Ana Reyes',
    claim: "two members log the same PM task from the logbook the same day: each keeps their completion, and a repeat is told it already counts",
    // a task the panel offers: it lists what is due (overdue / due soon), not what is on track
    pick: async () => psql(`select v.scope_item_id || '|' || a.asset_name from v_pm_scope_items_truth v join pm_assets a on a.id = v.asset_id
      where v.hive_id = '${HIVE}' and a.deleted_at is null and (v.is_overdue or v.is_due_soon) and not exists (select 1 from pm_completions c
      where c.scope_item_id = v.scope_item_id and c.worker_name in ('Joel Cruz', 'Ana Reyes') and c.completed_at > now() - interval '1 day')
      order by a.asset_name limit 1`),
    snapId: () => null,
    aOpen: async (A, v) => { await fillPmEntry(A, v); },
    bAct: async (B, v) => { await fillPmEntry(B, v); await B.page.evaluate(() => document.getElementById('log-form').requestSubmit()); await sleep(5000); },
    aAct: async (A, v) => { await A.page.evaluate(() => document.getElementById('log-form').requestSubmit()); await sleep(5000);
      A.said.length = 0;
      // a second, different visit the same day (an identical one within 30 s is a refresh-retry, and saves nothing)
      await fillPmEntry(A, v, 'Second PM visit - race walk'); await A.page.evaluate(() => document.getElementById('log-form').requestSubmit());
      // the entry guard asks first ("<machine> already logged today. Submit again to save anyway.") - Joel saves anyway
      await waitSaid(A, /already logged today/i, 8000);
      await A.page.evaluate(() => document.getElementById('log-form').requestSubmit()); },
    told: /already recorded for you today/i,
    kept: (v) => psql(`select string_agg(worker_name || ':' || n, ',' order by worker_name) from (select worker_name, count(*) n from pm_completions
      where scope_item_id = '${v.split('|')[0]}' and completed_at > now() - interval '10 minutes' group by worker_name) x`) === 'Ana Reyes:1,Joel Cruz:1',
    keptSays: "Joel and Ana each hold one completion; Joel's second entry saved without a second completion",
    cleanup: (t0, v) => sweep(t0, [`delete from pm_completions where scope_item_id = '${v.split('|')[0]}' and completed_at >= '${t0}';`,
      `delete from logbook where hive_id = '${HIVE}' and worker_name in ('Joel Cruz', 'Ana Reyes') and created_at >= '${t0}';`, 'hive_audit_log']),
  },
  // ── the CMMS import: two supervisors import the same export at once ────────────────────────────────────────────────
  ...[
    { id: 'HS411', entity: 'asset', table: 'asset_nodes', what: 'machine',
      csv: 'Tag,Name,Type,Location\nHS-RACE-ASSET,Race walk feed pump,Pump,Bay 9\n',
      map: { external_id: 'Tag', name: 'Name', type: 'Type', location: 'Location' },
      count: `select count(*) from asset_nodes where hive_id = '${HIVE}' and tag = 'HS-RACE-ASSET' and deleted_at is null`,
      clean: [`delete from asset_nodes where hive_id = '${HIVE}' and tag = 'HS-RACE-ASSET';`] },
    { id: 'HS413', entity: 'inventory', table: 'inventory_items', what: 'part',
      csv: 'Part,Name,Qty,Unit\nHS-RACE-PART,Race walk gasket,4,PC\n',
      map: { external_id: 'Part', name: 'Name', qty_on_hand: 'Qty', unit: 'Unit' },
      count: `select count(*) from inventory_items where hive_id = '${HIVE}' and part_number = 'HS-RACE-PART'`,
      clean: [`delete from inventory_transactions where item_id in (select id from inventory_items where hive_id = '${HIVE}' and part_number = 'HS-RACE-PART');`,
              `delete from inventory_items where hive_id = '${HIVE}' and part_number = 'HS-RACE-PART';`] },
    { id: 'HS415', entity: 'work_order', table: 'logbook', what: 'work order',
      csv: 'Order,Equipment,Status,Problem\nWO-HS-RACE,Race walk compressor,Open,Race walk - imported fault\n',
      map: { external_id: 'Order', machine: 'Equipment', status: 'Status', problem: 'Problem' },
      count: `select count(*) from logbook where hive_id = '${HIVE}' and machine = 'Race walk compressor'`,
      clean: [`delete from logbook where hive_id = '${HIVE}' and machine = 'Race walk compressor';`] },
  ].map((imp) => ({
    id: imp.id, page: 'integrations.html', table: imp.table, a: 'Corazon Bautista', b: 'Ernesto Villareal',
    claim: `two supervisors import the same CMMS ${imp.what} at once: it lands once, and the second import says what it did`,
    pick: async () => imp.id,
    snapId: () => null,
    aOpen: async (A) => { await importTo(A, imp, 4); },
    bAct: async (B) => { await importTo(B, imp, 4); await B.page.evaluate(() => startImport()); await modalOk(B, 1500); await sleep(6000); },
    aAct: async (A) => { A.said.length = 0; await A.page.evaluate(() => startImport()); await modalOk(A, 1500); await sleep(6000); },
    // the second import is an upsert of the same CMMS record: it says what is in the hive now - one, not two
    told: /Import complete: 1 (?:asset|inventory item|work order) is in your/i,
    kept: () => psql(imp.count) === '1',
    keptSays: `one ${imp.what}, however many supervisors imported it`,
    cleanup: (t0) => sweep(t0, [...imp.clean, `delete from external_sync where hive_id = '${HIVE}' and external_id in ('HS-RACE-ASSET', 'HS-RACE-PART', 'WO-HS-RACE');`,
      'hive_audit_log']),
  })),
  {
    id: 'HS417', page: 'integrations.html', table: 'pm_assets', a: 'Corazon Bautista', b: 'Ernesto Villareal',
    claim: "two supervisors add a vehicle at the same moment: each gets the program they made, and neither is lost",
    pick: async () => 'HS417',
    snapId: () => null,
    aOpen: async (A) => { await vehForm(A, 'Corazon'); },
    bAct: async (B) => { await vehForm(B, 'Ernesto'); await B.page.evaluate(() => vehCreate()); await sleep(6000); },
    aAct: async (A) => { await A.page.evaluate(() => vehCreate()); await sleep(6000); },
    told: null,
    kept: () => psql(`select string_agg(worker_name, ',' order by worker_name) from pm_assets where hive_id = '${HIVE}' and asset_name like '2019 Racewalk Hilux%'
      and deleted_at is null`) === 'Corazon Bautista,Ernesto Villareal',
    keptSays: "both vehicles are programs, each under the supervisor who added it",
    seen: async (A) => {
      const t = await A.page.evaluate(() => { const r = document.getElementById('veh-receipt'); return r && r.checkVisibility() ? r.innerText : ''; });
      return { ok: !!t, says: t ? `Corazon's receipt: "${t.replace(/\s+/g, ' ').slice(0, 90)}"` : "Corazon saw no receipt for her vehicle" };
    },
    cleanup: (t0) => sweep(t0, [
      `delete from pm_scope_items where asset_id in (select id from pm_assets where hive_id = '${HIVE}' and asset_name like '2019 Racewalk Hilux%');`,
      `delete from asset_nodes where pm_asset_id in (select id from pm_assets where hive_id = '${HIVE}' and asset_name like '2019 Racewalk Hilux%');`,
      `delete from pm_assets where hive_id = '${HIVE}' and asset_name like '2019 Racewalk Hilux%';`, 'hive_audit_log']),
  },
  {
    id: 'HS419', page: 'inventory.html', table: 'asset_nodes', a: 'Jun Salvador', b: 'Jun Salvador',
    claim: "one owner's phone and laptop merge the same old local machine list at the same moment: one machine, not two",
    pick: async () => 'JUN-RACE-PUMP',
    snapId: () => null,
    // both devices hold the same pre-database machine list, and the database holds none of Jun's machines yet
    aOpen: async (A, tag, B) => {
      for (const s of [A, B]) await s.page.evaluate(([t]) => localStorage.setItem('wh_assets_Jun Salvador',
        JSON.stringify([{ id: 'legacy-jun-1', asset_id: t, name: 'Jun race pump', type: 'Pump', criticality: 'high' }])), [tag]);
    },
    bAct: async () => {},
    aAct: async (A, tag, B) => { await Promise.all([A.page.reload({ waitUntil: 'domcontentloaded' }), B.page.reload({ waitUntil: 'domcontentloaded' })]); await sleep(9000); },
    told: null,
    kept: (tag) => psql(`select count(*) from asset_nodes where tag = '${tag}' and auth_uid = (select auth_uid from worker_profiles where username = 'junvanowner')`) === '1',
    keptSays: "Jun's two devices merged the machine into ONE row",
    state: (tag) => psql(`select count(*) from asset_nodes where tag = '${tag}'`),
    cleanup: (t0, tag) => sweep(t0, [`delete from asset_nodes where tag = '${tag}';`]),
  },
  // ── OWNER: one person's record. The only race is that person's own two devices; a teammate holds no control over it ──
  {
    id: 'HS436', page: 'marketplace-seller.html', table: 'marketplace_listings', a: 'Joel Cruz', b: 'Joel Cruz',
    claim: "a seller edits one listing on a phone and a laptop: the second save is refused and said - and no teammate can edit it at all",
    pick: async (A) => { await A.page.waitForSelector('button[data-action="edit"][data-id]', { state: 'attached', timeout: 15000 }).catch(() => {});
      return A.page.evaluate(() => { const b = document.querySelector('button[data-action="edit"][data-id]'); return b ? b.getAttribute('data-id') : ''; }); },
    aOpen: async (A, id) => { await tap(A, `button[data-action="edit"][data-id="${id}"]`); await sleep(1200); },
    bAct: async (B, id) => { await tap(B, `button[data-action="edit"][data-id="${id}"]`); await sleep(1200);
      await B.page.fill('#edit-price', '1234'); await B.page.evaluate(() => document.getElementById('form-edit').requestSubmit()); await sleep(4000); },
    aAct: async (A) => { await A.page.fill('#edit-price', '999'); await A.page.evaluate(() => document.getElementById('form-edit').requestSubmit()); },
    told: /saved from another tab or device/i,
    kept: (id) => psql(`select price::int from marketplace_listings where id = '${id}'`) === '1234',
    keptSays: "the laptop's price stands",
    // ...and a teammate's seller page holds no edit for it (a third person, read on their own screen)
    seen: async (A, id) => {
      const T = await session(BROWSER, 'Ana Reyes', 'phone-390');
      try { await open(T, 'marketplace-seller.html');
        const n = await T.page.evaluate((i) => document.querySelectorAll(`button[data-action="edit"][data-id="${i}"]`).length, id);
        return { ok: n === 0, says: n === 0 ? "Ana's seller page offers no edit for Joel's listing" : "Ana's seller page offers an edit for Joel's listing" };
      } finally { await T.ctx.close().catch(() => {}); }
    },
    cleanup: (t0) => sweep(t0, ['hive_audit_log']),
  },
  {
    id: 'HS434', page: 'marketplace-seller.html', table: 'marketplace_inquiries', a: 'Ernesto Villareal', b: 'Joel Cruz',
    claim: "a buyer's question on Joel's listing is answered by Joel: a teammate who also sells holds no reply for it",
    // one of Joel's inquiries, made waiting again for the walk (the snapshot puts it back)
    pick: async () => psql(`select i.id from marketplace_inquiries i join marketplace_listings l on l.id = i.listing_id
      where l.seller_name = 'Joel Cruz' order by i.created_at desc limit 1`),
    aOpen: async (A, id, B) => { psql(`set session_replication_role = replica; update marketplace_inquiries set status = 'pending', reply_text = null, replied_at = null where id = '${id}';`);
      await Promise.all([A.page.reload({ waitUntil: 'domcontentloaded' }), B.page.reload({ waitUntil: 'domcontentloaded' })]); await sleep(6000);
      for (const x of [A, B]) { await tap(x, '#tab-inquiries'); } await sleep(2500); },
    bAct: async (B, id) => { await B.page.waitForSelector(`.reply-textarea[data-inq-id="${id}"]`, { state: 'attached', timeout: 15000 });
      await B.page.evaluate((i) => { const t = document.querySelector(`.reply-textarea[data-inq-id="${i}"]`); t.value = 'Yes, still available - race walk'; }, id);
      await tap(B, `[data-action="reply"][data-id="${id}"]`); await sleep(3000); },
    aAct: async () => {},
    told: null,
    kept: (id) => psql(`select status || '|' || coalesce(reply_text, '') from marketplace_inquiries where id = '${id}'`) === 'replied|Yes, still available - race walk',
    keptSays: "Joel's reply is the inquiry's answer",
    seen: async (A, id) => {
      const n = await A.page.evaluate((i) => document.querySelectorAll(`[data-action="reply"][data-id="${i}"], .reply-textarea[data-inq-id="${i}"]`).length, id);
      return { ok: n === 0, says: n === 0 ? "Ernesto's seller page holds no reply for Joel's inquiry" : "Ernesto's seller page offers a reply on Joel's inquiry" };
    },
  },
  {
    id: 'HS438', page: 'marketplace-seller.html', table: 'marketplace_sellers', a: 'Ernesto Villareal', b: 'Joel Cruz',
    claim: "two sellers save their profiles at the same moment: each profile keeps its own owner's change",
    pick: async () => psql(`select id from marketplace_sellers where worker_name = 'Joel Cruz'`),
    aOpen: async () => {},
    bAct: async (B) => { await B.page.fill('#messenger-input', 'joel.racewalk'); await tap(B, '#btn-save-messenger'); await sleep(3000); },
    aAct: async (A) => { await A.page.fill('#messenger-input', 'ernesto.racewalk'); await tap(A, '#btn-save-messenger'); await sleep(3000); },
    told: null,
    kept: () => psql(`select string_agg(worker_name || '=' || coalesce(messenger_username, ''), ',' order by worker_name) from marketplace_sellers
      where worker_name in ('Joel Cruz', 'Ernesto Villareal')`) === 'Ernesto Villareal=ernesto.racewalk,Joel Cruz=joel.racewalk',
    keptSays: "each seller's profile holds its own handle",
    seen: async (A) => { const v = await A.page.evaluate(() => (document.getElementById('messenger-input') || {}).value || '');
      return { ok: !/joel/i.test(v), says: `Ernesto's form holds "${v}", never Joel's` }; },
    cleanup: () => psql(`set session_replication_role = replica; update marketplace_sellers set messenger_username = null where worker_name = 'Ernesto Villareal' and messenger_username = 'ernesto.racewalk';`),
  },
  {
    id: 'HS440', page: 'marketplace-seller.html', table: 'service_providers', a: 'Ernesto Villareal', b: 'Joel Cruz',
    claim: "a provider goes online from their own page: a teammate's page holds no switch for it",
    pick: async () => psql(`select id from service_providers where worker_name = 'Joel Cruz' limit 1`),
    aOpen: async () => {},
    bAct: async (B, id) => { await B.page.evaluate(([i]) => svcToggleAvail(i, 'online'), [id]); await sleep(3000); },
    aAct: async () => {},
    told: null,
    kept: (id) => psql(`select availability from service_providers where id = '${id}'`) === 'online',
    keptSays: 'Joel is online, by his own switch',
    seen: async (A, id) => { const n = await A.page.evaluate((i) => [...document.querySelectorAll('[onclick*="svcToggleAvail"]')].filter((b) => b.getAttribute('onclick').includes(i)).length, id);
      return { ok: n === 0, says: n === 0 ? "Ernesto's page holds no switch for Joel's provider profile" : "Ernesto's page holds Joel's availability switch" }; },
  },
  {
    id: 'HS465', page: 'resume.html', table: 'resume_documents', a: 'Ana Reyes', b: 'Joel Cruz',
    claim: "a member's resume is theirs: a teammate's resume page never loads it, so there is nothing of it to change",
    // Joel's resume, planted for the walk (he had none), and removed after
    pick: async () => psql(`set session_replication_role = replica;
      insert into resume_documents (id, auth_uid, worker_name, title, doc, template)
      select 'a5e51dbc-0000-4000-8000-000000000465'::uuid, auth_uid, 'Joel Cruz', 'Joel Cruz - Maintenance Technician (race walk)', '{}'::jsonb, 'classic'
      from worker_profiles where username = 'joelcruz' on conflict (id) do nothing;
      select 'a5e51dbc-0000-4000-8000-000000000465';`),
    snapId: () => null,
    aOpen: async (A) => { await A.page.reload({ waitUntil: 'domcontentloaded' }); await sleep(6000); },
    bAct: async () => {},
    aAct: async () => {},
    told: null,
    kept: (id) => psql(`select title from resume_documents where id = '${id}'`) === 'Joel Cruz - Maintenance Technician (race walk)',
    keptSays: "Joel's resume is untouched",
    seen: async (A) => { const t = await A.page.evaluate(() => document.body.innerText + ' ' + [...document.querySelectorAll('input, textarea')].map((e) => e.value).join(' '));
      return { ok: !/race walk/i.test(t), says: /race walk/i.test(t) ? "Ana's resume page shows Joel's resume" : "Ana's resume page holds only her own" }; },
    cleanup: (t0, id) => psql(`set session_replication_role = replica; delete from resume_documents where id = '${id}';`),
  },
  {
    id: 'HS442', page: 'marketplace.html', table: 'marketplace_inquiries', a: 'Ana Reyes', b: 'Ernesto Villareal',
    claim: "two buyers ask about the same listing at once: both questions reach the seller",
    // one of Joel's listings, as it shows in the buyers' grid
    pick: async (A) => {
      const ids = psql(`select string_agg(id::text, ',') from marketplace_listings where seller_name = 'Joel Cruz' and status = 'published'`).split(',');
      await A.page.waitForSelector('.listing-card[data-id]', { state: 'attached', timeout: 15000 }).catch(() => {});
      return A.page.evaluate((want) => { for (const c of document.querySelectorAll('.listing-card[data-id]')) if (want.includes(c.dataset.id)) return c.dataset.id; return ''; }, ids);
    },
    snapId: () => null,
    aOpen: async (A, id) => { await askSeller(A, id, false); },
    bAct: async (B, id) => { await askSeller(B, id, true); await sleep(3500); },
    aAct: async (A) => { await A.page.evaluate(() => document.getElementById('form-inquiry').requestSubmit()); await sleep(3500); },
    told: null,
    kept: (id) => psql(`select string_agg(buyer_name, ',' order by buyer_name) from marketplace_inquiries where listing_id = '${id}'
      and created_at > now() - interval '5 minutes'`) === 'Ana Reyes,Ernesto Villareal',
    keptSays: "both buyers' questions are on the listing",
    // ...as the seller reads them: Joel's own inquiries tab
    seen: async (A, id) => {
      const J = await session(BROWSER, 'Joel Cruz', 'desktop-1280');
      try { await open(J, 'marketplace-seller.html'); await tap(J, '#tab-inquiries'); await sleep(2500);
        const t = await J.page.evaluate(() => document.body.innerText);
        const both = t.includes('Ana Reyes') && t.includes('Ernesto Villareal');
        return { ok: both, says: both ? "Joel's inquiries tab lists both buyers" : "Joel's inquiries tab is missing a buyer" };
      } finally { await J.ctx.close().catch(() => {}); }
    },
    cleanup: (t0, id) => sweep(t0, [`delete from marketplace_inquiries where listing_id = '${id}' and created_at >= '${t0}';`]),
  },
  {
    id: 'HS444', page: 'marketplace.html', table: 'marketplace_listings', a: 'Ana Reyes', b: 'Ernesto Villareal',
    claim: "two members list the same kind of part at the same moment: two listings, each its seller's",
    pick: async () => 'HS444',
    snapId: () => null,
    aOpen: async (A) => { await postForm(A, false); },
    bAct: async (B) => { await postForm(B, true); await sleep(4000); },
    aAct: async (A) => { await A.page.evaluate(() => document.getElementById('form-post').requestSubmit()); await sleep(4000); },
    told: null,
    kept: () => psql(`select string_agg(seller_name, ',' order by seller_name) from marketplace_listings where title = 'Race walk - SKF 6205 bearing, sealed'
      and created_at > now() - interval '5 minutes'`) === 'Ana Reyes,Ernesto Villareal',
    keptSays: 'two listings, each under the member who posted it',
    cleanup: (t0) => sweep(t0, [`delete from marketplace_listings where title = 'Race walk - SKF 6205 bearing, sealed' and created_at >= '${t0}';`]),
  },
  {
    id: 'HS399', page: 'assistant.html', table: 'ai_reply_feedback', a: 'Joel Cruz', b: 'Ana Reyes',
    claim: "two members rate the assistant's answer to the same question at once: each rating is its own row, and each is told it was noted",
    pick: async () => 'HS399',
    snapId: () => null,
    // the model's answer is answered here (the walk spends no model call); the question, the answer on screen and the
    // thumbs are the page's own
    aOpen: async (A, id, B) => { for (const x of [A, B]) { await stubAnswer(x); await askAssistant(x); } },
    bAct: async (B) => { await tap(B, '[data-rate="-1"]'); await sleep(2500); },
    aAct: async (A) => { A.said.length = 0; await tap(A, '[data-rate="1"]'); await sleep(2500); },
    told: /Noted - this goes to the team/i,
    kept: () => psql(`select string_agg(worker_name || ':' || rating, ',' order by worker_name) from ai_reply_feedback
      where worker_name in ('Joel Cruz', 'Ana Reyes') and created_at > now() - interval '5 minutes'`) === 'Ana Reyes:-1,Joel Cruz:1',
    keptSays: "Joel's thumbs-up and Ana's thumbs-down are two rows, each its rater's",
    cleanup: (t0) => sweep(t0, [`delete from ai_reply_feedback where worker_name in ('Joel Cruz', 'Ana Reyes') and created_at >= '${t0}';`]),
  },
  // ── the same bug class, found by sweeping every updated_at guard after HS421 (not W1 rows - held by this gate) ──────
  {
    id: 'X-STRATEGY', page: 'asset-hub.html', table: 'rcm_strategies', a: 'Corazon Bautista', b: 'Ernesto Villareal',
    claim: "two supervisors set the strategy for the same failure mode: the second is told, the first one's strategy stands",
    pick: async () => psql(`select m.id || '|' || m.asset_id from rcm_fmea_modes m where m.hive_id = '${HIVE}' and m.approved_at is not null
      and not exists (select 1 from rcm_strategies s where s.fmea_mode_id = m.id) order by m.created_at limit 1`),
    snapId: () => null,
    aOpen: async (A, v) => { await A.page.goto(`${ORIGIN}/asset-hub.html?node_id=${v.split('|')[1]}`, { waitUntil: 'domcontentloaded' }); await sleep(6000);
      await tap(A, `button[data-action="strat-edit"][data-mode-id="${v.split('|')[0]}"]`); await sleep(800); await strategyForm(A, 'scheduled_on_condition', 'Vibration route - Corazon'); },
    bAct: async (B, v) => { await B.page.goto(`${ORIGIN}/asset-hub.html?node_id=${v.split('|')[1]}`, { waitUntil: 'domcontentloaded' }); await sleep(6000);
      await tap(B, `button[data-action="strat-edit"][data-mode-id="${v.split('|')[0]}"]`); await sleep(800);
      await strategyForm(B, 'scheduled_restoration', 'Overhaul at 8000 h - Ernesto'); await tap(B, '#rcm-save'); await sleep(4000); },
    aAct: async (A) => { await tap(A, '#rcm-save'); },
    told: /Another supervisor set a strategy for this failure mode|changed since you opened it/i,
    kept: (v) => psql(`select task_text from rcm_strategies where fmea_mode_id = '${v.split('|')[0]}'`) === 'Overhaul at 8000 h - Ernesto',
    keptSays: "the mode keeps Ernesto's strategy",
    cleanup: (t0, v) => sweep(t0, [`delete from rcm_strategies where fmea_mode_id = '${v.split('|')[0]}' and created_at >= '${t0}';`, 'hive_audit_log']),
  },
  {
    id: 'X-LESSONS', page: 'project-manager.html', table: 'projects', a: 'Corazon Bautista', b: 'Ernesto Villareal',
    claim: "two supervisors write a project's lessons learned: the second is told and keeps their text, the first one's lessons stand",
    pick: async () => psql(`select id from projects where hive_id = '${HIVE}' and deleted_at is null order by project_code limit 1`),
    aOpen: async (A, id) => { await A.page.evaluate((p) => openDetail(p), id); await sleep(3000); await tap(A, '#detail-tabs button[data-pane="signoff"]'); await sleep(1500);
      await A.page.locator('#lessons-text').fill("Corazon's lessons - race walk"); },
    bAct: async (B, id) => { await B.page.evaluate((p) => openDetail(p), id); await sleep(3000); await tap(B, '#detail-tabs button[data-pane="signoff"]'); await sleep(1500);
      await B.page.locator('#lessons-text').fill("Ernesto's lessons - race walk"); await B.page.evaluate(() => saveLessons()); await sleep(4000); },
    aAct: async (A) => { await A.page.evaluate(() => saveLessons()); await sleep(1500); },
    told: /Someone saved this project while you were writing/i,
    kept: (id) => psql(`select meta->>'lessons_learned' from projects where id = '${id}'`) === "Ernesto's lessons - race walk",
    keptSays: "the project keeps Ernesto's lessons",
    seen: async (A) => { const v = await A.page.evaluate(() => (document.getElementById('lessons-text') || {}).value || '');
      return { ok: v === "Corazon's lessons - race walk", says: v === "Corazon's lessons - race walk" ? "Corazon's text is still in her box" : "Corazon's text was wiped from her box" }; },
    cleanup: (t0) => sweep(t0, ['hive_audit_log']),
  },
  {
    id: 'X-RETRY', page: 'logbook.html', table: 'inventory_items', a: 'Joel Cruz', b: 'Ana Reyes',
    claim: "an entry that used a part is sent again within seconds (a refresh mid-save, then a retry): it is recognised, and the part leaves the shelf once",
    pick: async () => psql(`select id from inventory_items where hive_id = '${HIVE}' and status = 'approved' and qty_on_hand >= 5 order by part_number limit 1`),
    aOpen: async (A, id) => { await retryEntry(A, id); },
    bAct: async () => {},
    aAct: async (A, id) => {
      await A.page.evaluate(() => document.getElementById('log-form').requestSubmit()); await sleep(5000);
      A.said.length = 0;
      await retryEntry(A, id);   // the same entry, again - what a retry after a refresh sends
      await A.page.evaluate(() => document.getElementById('log-form').requestSubmit());
      // the day's guard asks first ("<machine> already logged today. Submit again to save anyway.") - the retry presses again
      await waitSaid(A, /already logged today/i, 8000);
      await A.page.evaluate(() => document.getElementById('log-form').requestSubmit()); await sleep(5000);
    },
    told: /no duplicate created/i,
    kept: (id) => psql(`select (select count(*) from logbook where hive_id = '${HIVE}' and problem = 'Retry walk - bearing swap' and created_at > now() - interval '5 minutes')
      || '|' || (select coalesce(-sum(qty_change), 0) from inventory_transactions where item_id = '${id}' and created_at > now() - interval '5 minutes')`) === '1|1',
    keptSays: 'one entry, and the part left the shelf once',
    state: (id) => psql(`select (select count(*) from logbook where hive_id = '${HIVE}' and problem = 'Retry walk - bearing swap' and created_at > now() - interval '5 minutes')
      || ' entries, ' || (select coalesce(-sum(qty_change), 0) from inventory_transactions where item_id = '${id}' and created_at > now() - interval '5 minutes') || ' taken'`),
    cleanup: (t0, id) => sweep(t0, [`delete from inventory_transactions where item_id = '${id}' and created_at >= '${t0}';`,
      `delete from logbook where hive_id = '${HIVE}' and problem = 'Retry walk - bearing swap' and created_at >= '${t0}';`, 'hive_audit_log']),
  },
  // ── W1 rows on RETIRED admin pages: a worker reaches them only as a no-access gate, so there is nothing to race on ────
  ...[
    ['HS429', 'marketplace-admin.html', 'marketplace_listings'], ['HS430', 'marketplace-admin.html', 'marketplace_orders'],
    ['HS432', 'marketplace-admin.html', 'marketplace_sellers'], ['HS446', 'platform-actions.html', 'marketplace_listings'],
    ['HS448', 'platform-actions.html', 'marketplace_sellers'], ['HS450', 'platform-actions.html', 'platform_feedback'],
  ].map(([rid, page, table]) => ({
    id: rid, page, table, a: 'Joel Cruz', b: 'Ana Reyes',
    claim: `two workers open ${page} at once: it is a retired admin page, a worker meets its no-access gate, and no control exists to change ${table}`,
    pick: async () => rid,
    snapId: () => null,
    aOpen: async () => {},
    bAct: async () => {},
    aAct: async () => {},
    told: null,
    kept: () => psql(`select count(*) from ${table} where coalesce(updated_at, created_at) > now() - interval '3 minutes'`) === '0',
    keptSays: `nothing in ${table} moved while both workers had the page open`,
    seen: async (A, id, B) => {
      const read = (x) => x.page.evaluate(() => {
        const ACT = /\b(approve|reject|suspend|verify|resolve|delete|ban|refund|release|archive|unpublish|reinstate)\b/i;
        const live = [...document.querySelectorAll('button, [role="button"], a[href]')]
          .filter((el) => el.checkVisibility && el.checkVisibility({ visibilityProperty: true, opacityProperty: true })
            && !el.closest('[inert], [aria-hidden="true"]') && !el.disabled && ACT.test(el.innerText || el.getAttribute('aria-label') || ''));
        return { n: live.length, first: live.slice(0, 2).map((el) => (el.innerText || '').trim().slice(0, 40)) };
      });
      const ra = await read(A), rb = await read(B);
      const ok = ra.n === 0 && rb.n === 0;
      return { ok, says: ok ? 'neither worker\'s screen offers a single moderation control' : `a worker's screen offers ${JSON.stringify(ra.first.concat(rb.first))}` };
    },
  })),
];
// a corrective entry that used one unit of a part, filled as a person fills it
async function retryEntry(s, partId) {
  const part = psql(`select part_name || '|' || part_number || '|' || coalesce(unit, 'pcs') from inventory_items where id = '${partId}'`).split('|');
  await s.page.evaluate(([pid, name, num, unit]) => {
    const set = (k, v) => { const el = document.getElementById(k); if (!el) return; el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
    set('f-machine', 'Crude charge pump P-101');   // a machine in the hive's register (the form takes one from the list)
    set('f-maint-type', 'Inspection');
    const cat = [...document.getElementById('f-category').options].find((o) => o.value); if (cat) set('f-category', cat.value);
    set('f-problem', 'Retry walk - bearing swap');
    set('f-action', 'Replaced the drive-end bearing');
    selectPart(pid, name, num, unit);
  }, [partId, ...part]);
  await sleep(500);
}
async function strategyForm(s, decision, task) {
  await s.page.evaluate(([d, t]) => {
    const set = (k, v) => { const el = document.getElementById(k); if (!el) return; el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
    set('rcm-decision', d);
    const iv = document.getElementById('rcm-interval'); if (iv) { const o = [...iv.options].find((x) => x.value && x.value !== 'custom'); if (o) set('rcm-interval', o.value); }
    set('rcm-task', t);
  }, [decision, task]);
}
async function stubAnswer(s) {
  await s.page.route('**/functions/v1/ai-gateway', (route) => route.fulfill({ status: 200, contentType: 'application/json',
    body: JSON.stringify({ ok: true, trace_id: '0123456789abcdef', data: { agent: 'assistant',
      answer: 'Check the coupling alignment first, then the bearing temperature - a hot drive-end bearing usually means misalignment.' } }) }));
}
async function askAssistant(s) {
  await s.page.fill('#chat-input', 'Why does the feed pump bearing run hot?');
  await tap(s, '#send-btn');
  await s.page.waitForSelector('[data-rate="1"]', { state: 'attached', timeout: 20000 })
    .catch(() => { throw new Error(`${s.person} @ ${s.vpName}: no answer with thumbs on screen`); });
  await sleep(500);
}
// the Sell sheet as a member fills it - the same part, the same words, at the same moment
async function postForm(s, send) {
  await tap(s, '#fab-post'); await sleep(1500);   // the Sell button (openPostSheet lives in the page's closure)
  await s.page.evaluate(() => {
    const set = (k, v) => { const el = document.getElementById(k); if (!el) return; el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
    set('post-title', 'Race walk - SKF 6205 bearing, sealed');
    const cat = document.getElementById('post-category'); if (cat) { const o = [...cat.options].find((x) => x.value); if (o) set('post-category', o.value); }
    const con = document.getElementById('post-condition'); if (con) { const o = [...con.options].find((x) => x.value); if (o) set('post-condition', o.value); }
    set('post-desc', 'Spare from a pump overhaul, still in the box.');
    set('post-price', '450');
    set('post-location', 'Batangas');
    set('post-contact', '0917 000 0000');
  });
  if (send) await s.page.evaluate(() => document.getElementById('form-post').requestSubmit());
}
// a buyer opens the listing, presses Contact, and writes the question (sent now, or held for the race)
async function askSeller(s, id, send) {
  await tap(s, `.listing-card[data-id="${id}"]`); await sleep(1500);
  await tap(s, '#btn-detail-contact'); await sleep(1500);
  await s.page.evaluate((who) => {
    const set = (k, v) => { const el = document.getElementById(k); if (el) { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); } };
    if (!document.getElementById('inq-name').value) set('inq-name', who);
    set('inq-contact', '0917 000 0000');
    set('inq-message', 'Is this still available? - race walk');
  }, s.person);
  if (send) await s.page.evaluate(() => document.getElementById('form-inquiry').requestSubmit());
}
// the vehicle wizard's own fields, the vehicle a hive vehicle (scope: the hive)
async function vehForm(s, who) {
  await tap(s, '#veh-open');   // "Add my vehicle" opens the wizard
  await sleep(800);
  await s.page.evaluate((w) => {
    const set = (id, v) => { const el = document.getElementById(id); if (!el) return; el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    set('veh-make', 'Racewalk'); set('veh-model', 'Hilux ' + w); set('veh-year', '2019'); set('veh-plate', 'HSR ' + w.slice(0, 3).toUpperCase());
    set('veh-odo', '42000');
    const h = document.getElementById('veh-scope-hive'); if (h) { h.checked = true; h.dispatchEvent(new Event('change', { bubbles: true })); }
  }, who);
  await sleep(500);
}
// the import wizard as a supervisor walks it: source, kind, the file, the column mapping, the preview (step 4)
async function importTo(s, imp, step) {
  const { writeFileSync: wf } = await import('fs');
  const f = `.tmp/race_${imp.entity}.csv`;
  wf(f, imp.csv);
  await s.page.evaluate((e) => { selectSource('generic'); selectEntity(e); goStep(2); }, imp.entity);
  await sleep(600);
  await s.page.setInputFiles('#file-input', f);
  await sleep(3000);
  await s.page.evaluate(() => goStep(3));
  await sleep(800);
  for (const [k, col] of Object.entries(imp.map)) {
    await s.page.selectOption(`select[data-field="${k}"]`, col).catch(() => { throw new Error(`${s.person} @ ${s.vpName}: no mapping for ${k}`); });
  }
  if (step >= 4) { await s.page.evaluate(() => goStep(4)); await sleep(1500); }
}
// a Preventive Maintenance entry on the task's machine, its PM task ticked - the form as a person fills it
async function fillPmEntry(s, v, problem = 'Scheduled PM - race walk') {
  const [sid, assetName] = [v.split('|')[0], v.split('|').slice(1).join('|')];
  await s.page.evaluate(([name, prob]) => {
    const set = (id, val) => { const el = document.getElementById(id); el.value = val; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
    set('f-maint-type', 'Preventive Maintenance');
    set('f-machine', name);
    const cat = [...document.getElementById('f-category').options].find((o) => o.value);
    if (cat) set('f-category', cat.value);
    set('f-problem', prob);
    set('f-action', 'Completed the PM task');
  }, [assetName, problem]);
  await s.page.evaluate(() => loadPMTasksForAsset());
  await s.page.waitForSelector(`.pm-task-check[data-item-id="${sid}"]`, { state: 'attached', timeout: 15000 })
    .catch(() => { throw new Error(`${s.person} @ ${s.vpName}: the PM task is not offered for ${assetName}`); });
  // the panel pre-ticks every task that is due; only the raced task stays ticked, so nothing else is written
  await s.page.evaluate((i) => { for (const cb of document.querySelectorAll('.pm-task-check')) { cb.checked = cb.getAttribute('data-item-id') === i; cb.dispatchEvent(new Event('change', { bubbles: true })); } }, sid);
}

async function race(browser, r, aVp, bVp) {
  const A = await session(browser, r.a, aVp), B = await session(browser, r.b, bVp);
  const out = { a: `${r.a} @ ${aVp}`, b: `${r.b} @ ${bVp}` };
  let before = null, id = null;
  const t0 = psql('select now()');
  try {
    await Promise.all([open(A, r.page), open(B, r.page)]);
    id = await r.pick(A, B);     // chosen ONCE, before either acts
    out.item = id;
    if (!id) throw new Error('no item to race on');
    const sid = r.snapId ? r.snapId(id) : id;
    before = sid ? snap(r.table, sid) : null;
    await r.aOpen(A, id, B);     // A is now holding the item
    await r.bAct(B, id);         // B changes it first
    A.said.length = 0;
    await r.aAct(A, id, B);      // A acts on what they were holding
    out.told = r.told ? await waitSaid(A, r.told) : '(nothing written, nothing to tell)';
    out.a_saw = A.said.slice(-4);
    out.kept = r.kept(id);
    if (r.seen) { const sv = await r.seen(A, id, B); out.seen = sv.says; if (!sv.ok) out.kept = false; }
    if (r.state) out.state = r.state(id);   // the raw end state, for the reader of a failure
    out.ok = !!out.told && out.kept;
    out.why = out.ok ? `${r.a} was told "${out.told.slice(0, 110)}"; ${r.keptSays}${out.seen ? '; ' + out.seen : ''}`
      : (!out.told ? `${r.a} was NOT told (saw ${JSON.stringify(out.a_saw)})` : (out.seen ? out.seen + ' / ' : '') + `the database lost ${r.b}'s change`);
  } catch (e) {
    out.ok = false; out.why = 'walk error: ' + String(e.message || e).slice(0, 200);
  } finally {
    await A.ctx.close().catch(() => {}); await B.ctx.close().catch(() => {});
    try { if (before) restore(r.table, before); } catch (e) { out.restore_error = String(e.message || e).slice(0, 160); }
    try { if (r.cleanup && id) r.cleanup(t0, (r.snapId && r.snapId(id)) || id); } catch (e) { out.cleanup_error = String(e.message || e).slice(0, 160); }
  }
  return out;
}

const browser = await chromium.launch({ headless: true });
BROWSER = browser;
const report = { ran: new Date().toISOString(), hive: HIVE, rows: {} };
let failed = 0;
for (const r of RACES) {
  if (ONLY.size && !ONLY.has(r.id)) continue;
  const walks = [];
  for (const [aVp, bVp] of [['phone-390', 'desktop-1280'], ['desktop-1280', 'phone-390']]) {
    const w = await race(browser, r, aVp, bVp);
    walks.push(w);
    console.log(`  ${w.ok ? 'ok ' : 'BAD'} ${r.id} A ${aVp} / B ${bVp}: ${w.why}`);
  }
  const ok = walks.every((w) => w.ok);
  if (!ok) failed++;
  report.rows[r.id] = { ok, page: r.page, table: r.table, claim: r.claim, walks };
  console.log(`${ok ? 'PASS' : 'FAIL'} ${r.id} ${r.page} ${r.table}: ${r.claim}`);
}
await browser.close();
// what the races' rows PAID goes with them - sweep() deletes with triggers off, so the XP they paid stayed standing
psql(readFileSync('tools/hs_paid_residue.sql', 'utf8'));
if (ONLY.size) {
  try {
    const prior = JSON.parse(readFileSync(OUT, 'utf8'));
    if (Date.now() - Date.parse(prior.ran) < 3 * 3600 * 1000) report.rows = { ...prior.rows, ...report.rows };
  } catch (_) { /* no prior report - this run stands alone */ }
  failed = Object.values(report.rows).filter((x) => !x.ok).length;
}
writeFileSync(OUT, JSON.stringify(report, null, 1));
const n = Object.keys(report.rows).length;
console.log(`${failed ? 'FAIL' : 'PASS'} hive-scale-races: ${n - failed}/${n} races told the member who lost, and kept the other's change`);
process.exitCode = failed ? 1 : 0;
