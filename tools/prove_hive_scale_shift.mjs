// prove_hive_scale_shift — Wave HS (the hive at thirty), lens W2, the BROWSER half: after a shift of thirty writes, does the
// page keep every item in its order? (2026-10-30)
//
// tools/prove_hive_scale_burst.mjs proves the writes land (no limit the rest of the hive spent refuses one, the ledger keeps
// every unit). This reads the page a person then opens: the 29 members of the 30-member hive write one after another
// through PostgREST, as a shift change arrives, and then a member opens the row's page at phone-390 and another at
// desktop-1280 and reads, from the screen, where each of the shift's items stands:
//   all      every item the page's window holds is on screen (a capped list must say there is more)
//   order    the items read in the page's own order - newest first for a feed, oldest first for a thread
// Every row the shift writes carries a marker and is removed after (triggers off for the removal).
//
//   node tools/prove_hive_scale_shift.mjs [HS402 ...]   -> hive_scale_shift_report.json; exit 1 on any failure
import { chromium } from 'playwright';
import { spawnSync } from 'child_process';
import { readFileSync, writeFileSync } from 'fs';

const ORIGIN = 'http://127.0.0.1:5000/workhive';
const SB = 'http://127.0.0.1:54321';
const KEY = 'sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH';   // the LOCAL stack's publishable key (public by design)
const HIVE = '30303030-3030-4030-8030-303030303030';
const OUT = 'hive_scale_shift_report.json';
const MARK = 'HS-W2 shift';
const ONLY = new Set(process.argv.slice(2).filter((a) => /^HS\d+$/.test(a)));
// --teeth: the import rows walked on the COMMITTED integrations.html (git HEAD, served in place of the working copy) - the
// fix is in the working copy only until it lands, so the committed page must fail the walk
const TEETH = process.argv.includes('--teeth');
const TEETH_PAGE = 'integrations.html';
// ★the page's source names the PRODUCTION project; the tester server (test-data-seeder/app.py) swaps in the local URL and
// key on every file it serves. A page fulfilled from git skips that server, so the swap is made here - without it the
// committed page booted against production (it did once, 2026-10-30: anonymous reads, an analytics insert refused)
const TEETH_HTML = TEETH ? spawnSync('git', ['show', `HEAD:${TEETH_PAGE}`], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }).stdout
  .replaceAll('https://hzyvnjtisfgbksicrouu.supabase.co', SB).replaceAll('sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ', KEY) : '';
if (TEETH && /hzyvnjtisfgbksicrouu/.test(TEETH_HTML)) throw new Error('teeth: the committed page still names the production project');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function psql(sql) {
  const r = spawnSync('docker', ['exec', '-i', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-At', '-v', 'ON_ERROR_STOP=1'],
    { input: sql, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 });
  if (r.status !== 0) throw new Error('psql: ' + (r.stderr || '').slice(0, 300));
  return (r.stdout || '').trim().split('\n').filter((l) => l && !/^(SET|INSERT|UPDATE|DELETE)/.test(l)).join('\n');
}

// the shift: every active member, signed in as themselves
const people = psql(`select string_agg(hm.worker_name || '|' || wp.username || '|' || hm.role, E'\\n' order by hm.worker_name)
  from hive_members hm join worker_profiles wp on wp.auth_uid = hm.auth_uid
  where hm.hive_id = '${HIVE}' and hm.status = 'active' and wp.username is not null`).split('\n').filter(Boolean)
  .map((l) => { const [name, user, role] = l.split('|'); return { name, user, role }; });
const tokens = {};
async function token(p) {
  if (tokens[p.user]) return tokens[p.user];
  const r = await fetch(`${SB}/auth/v1/token?grant_type=password`, { method: 'POST', headers: { apikey: KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: `${p.user}@auth.workhiveph.com`, password: 'test1234' }) });
  const j = await r.json().catch(() => ({}));
  await sleep(120);
  return (tokens[p.user] = j.access_token ? j : null);
}
for (const p of people) p.tok = await token(p);
const shift = people.filter((p) => p.tok);
async function rest(p, path, body, method = 'POST', prefer = '') {
  const r = await fetch(`${SB}/rest/v1/${path}`, { method, headers: { apikey: KEY, Authorization: `Bearer ${p.tok.access_token}`,
    'Content-Type': 'application/json', Prefer: 'return=minimal' + prefer }, body: JSON.stringify(body) });
  return r.status;
}
// an RPC the page calls before its write (a project's code, a change order's number) - its answer goes into the row
async function rpcValue(p, fn, args) {
  const r = await fetch(`${SB}/rest/v1/rpc/${fn}`, { method: 'POST', headers: { apikey: KEY, Authorization: `Bearer ${p.tok.access_token}`,
    'Content-Type': 'application/json' }, body: JSON.stringify(args) });
  return r.ok ? r.json() : null;
}

async function session(browser, p, vp, hive = HIVE) {
  const ctx = await browser.newContext({ ...(vp === 'phone-390' ? { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }
    : { viewport: { width: 1280, height: 800 } }), timezoneId: 'Asia/Manila', serviceWorkers: 'block' });
  await ctx.addInitScript(([t, hive, name, role]) => {
    try {
      if (!localStorage.getItem('sb-127-auth-token')) localStorage.setItem('sb-127-auth-token', JSON.stringify(t));
      localStorage.setItem('wh_active_hive_id', hive); localStorage.setItem('wh_last_worker', name); localStorage.setItem('wh_hive_role', role);
    } catch (_) { /* storage blocked */ }
  }, [p.tok, hive, p.name, p.role]);
  const page = await ctx.newPage();
  page.on('dialog', (d) => d.accept().catch(() => {}));
  return { ctx, page, p, vp };
}
async function tap(s, sel) {
  const loc = s.page.locator(sel).first();
  await loc.waitFor({ state: 'attached', timeout: 15000 });
  try { await loc.scrollIntoViewIfNeeded({ timeout: 3000 }); await loc.click({ timeout: 4000 }); } catch (_) { await loc.evaluate((el) => el.click()); }
}
async function modalOk(s, ms = 4000) {
  const ok = s.page.locator('[data-wh-modal-ok]').first();
  try { await ok.waitFor({ state: 'visible', timeout: ms }); } catch (_) { return false; }
  await ok.click();
  return true;
}
// ── the CMMS import, as a supervisor walks it during the shift: a plant-sized file (150 rows) through the page's own wizard
// (source, kind, the file, the column mapping, the preview, Import), then the results screen read against the database.
// The daily row caps count the shift's writes and the import's own rows alike, so a big import can meet one: every row
// that FITS must land, and the rows left out must be told with the limit's own sentence - checked against the counts.
const IMPORT_N = 150;
const IMPORTS = {
  asset: { table: 'asset_nodes', head: 'Tag,Name,Type,Location', row: (t, n) => `${t}-${n},HS-W2 import machine ${n},Pump,Bay 9`,
    map: { external_id: 'Tag', name: 'Name', type: 'Type', location: 'Location' }, mine: (t) => `tag like '${t}-%'`, clean: (t) => [`delete from asset_nodes where tag like '${t}-%';`] },
  inventory: { table: 'inventory_items', head: 'Part,Name,Qty,Unit', row: (t, n) => `${t}-${n},HS-W2 import part ${n},4,PC`,
    map: { external_id: 'Part', name: 'Name', qty_on_hand: 'Qty', unit: 'Unit' }, mine: (t) => `part_number like '${t}-%'`,
    clean: (t) => [`delete from inventory_transactions where item_id in (select id from inventory_items where part_number like '${t}-%');`, `delete from inventory_items where part_number like '${t}-%';`] },
  work_order: { table: 'logbook', head: 'Order,Equipment,Status,Problem', row: (t, n) => `${t}-${n},HS-W2 import compressor ${t},Closed,HS-W2 import fault ${n}`,
    map: { external_id: 'Order', machine: 'Equipment', status: 'Status', problem: 'Problem' }, mine: (t) => `machine = 'HS-W2 import compressor ${t}'`,
    clean: (t) => [`delete from logbook where machine = 'HS-W2 import compressor ${t}';`] },
  pm_schedule: { table: 'pm_assets', head: 'Plan,Asset,Task,Days', row: (t, n) => `${t}-${n},${t}-A${n},HS-W2 import task ${n},30`,
    map: { external_id: 'Plan', asset_tag: 'Asset', task: 'Task', interval_days: 'Days' }, mine: (t) => `asset_name like '${t}-A%'`,
    clean: (t) => [`delete from pm_scope_items where asset_id in (select id from pm_assets where asset_name like '${t}-A%');`, `delete from pm_assets where asset_name like '${t}-A%';`] },
};
const DAY0 = `(date_trunc('day', now() at time zone 'Asia/Manila')) at time zone 'Asia/Manila'`;
async function importWalk(s, entity, tag) {
  const imp = IMPORTS[entity];
  const f = `.tmp/hsw2_import_${tag}.csv`;
  writeFileSync(f, [imp.head, ...Array.from({ length: IMPORT_N }, (_, n) => imp.row(tag, n))].join('\n') + '\n');
  await s.page.evaluate((e) => { selectSource('generic'); selectEntity(e); goStep(2); }, entity);
  await sleep(600);
  await s.page.setInputFiles('#file-input', f);
  await sleep(3000);
  await s.page.evaluate(() => goStep(3));
  await sleep(800);
  for (const [k, col] of Object.entries(imp.map)) await s.page.selectOption(`select[data-field="${k}"]`, col);
  await s.page.evaluate(() => goStep(4)); await sleep(1500);
  await s.page.evaluate(() => startImport()); await modalOk(s, 2500);
  await s.page.locator('#import-results-state').waitFor({ state: 'visible', timeout: 120000 });
  await sleep(1200);
  const screen = await s.page.evaluate(() => ({ sub: document.getElementById('results-subtitle').textContent,
    err: (() => { const e = document.getElementById('import-error-section'); return e && !e.classList.contains('hidden') ? document.getElementById('error-detail').textContent : ''; })() }));
  const shownIn = Number(((screen.sub.match(/^([\d,]+) /) || [])[1] || '-1').replace(/,/g, ''));
  const landed = Number(psql(`select count(*) from ${imp.table} where ${imp.mine(tag)}`));
  const left = IMPORT_N - landed;
  const shownLeft = Number(((screen.err.match(/^([\d,]+) /) || [])[1] || '0').replace(/,/g, ''));
  // every row that fit landed: a limit named on screen must really be spent now (the person's own, or the hive's)
  let spent = true, which = '';
  const mPerson = screen.err.match(/You have reached today's free limit \((\d+)\)/);
  const mHive = screen.err.match(/Your hive has reached today's free limit of (\d+)/);
  if (mPerson) { which = `the person's ${mPerson[1]}`; spent = Number(psql(`select count(*) from ${imp.table} where worker_name = '${s.p.name}' and created_at >= ${DAY0}`)) >= Number(mPerson[1]); }
  if (mHive) { which = `the hive's ${mHive[1]}`; spent = Number(psql(`select count(*) from ${imp.table} where hive_id = '${HIVE}' and created_at >= ${DAY0}`)) >= Number(mHive[1]); }
  const told = left === 0 ? !screen.err : (shownLeft === left && !!(mPerson || mHive) && spent);
  const ok = shownIn === landed && told;
  return { ok, says: `imported ${landed} of ${IMPORT_N}; the screen says ${shownIn} imported` + (left ? `, ${shownLeft} left out - "${screen.err.slice(0, 150)}"${which ? `; ${which} is spent: ${spent}` : ''}` : ', nothing left out'),
    clean: imp.clean(tag) };
}
// a feed that draws its cards as they scroll in (.vcard-stub, expanded by an IntersectionObserver): every stub brought into
// view until none is left, as a person scrolling the list would - a one-pass read saw 4 of 20
async function drawAll(s, listSel) {
  for (let round = 0; round < 8; round++) {
    const left = await s.page.evaluate(async (sel) => {
      const stubs = [...document.querySelectorAll(`${sel} .vcard-stub`)];
      for (const st of stubs) { st.scrollIntoView({ block: 'center' }); await new Promise((r) => setTimeout(r, 70)); }
      return document.querySelectorAll(`${sel} .vcard-stub`).length;
    }, listSel);
    if (!left) return;
    await sleep(300);
  }
}
// ...and a feed that also COLLAPSES cards back into stubs once they are 1500px away cannot be read at the end: each card
// is brought in and read in turn, in the list's order, and the reading kept as it goes
async function collectFeed(s, listSel, word) {
  const ids = await s.page.evaluate((sel) => [...document.querySelectorAll(`${sel} [data-post-id]`)].map((el) => el.getAttribute('data-post-id')), listSel);
  const out = [];
  for (const id of ids) {
    const m = await s.page.evaluate(async ([sel, pid, mk, w]) => {
      const pick = () => document.querySelector(`${sel} [data-post-id="${pid}"]`);
      for (let i = 0; i < 25; i++) {
        const el = pick();
        if (!el) return null;
        el.scrollIntoView({ block: 'center' });
        if (!el.classList.contains('vcard-stub')) {
          const hit = (el.innerText || '').match(new RegExp(mk + ' ' + w + ' (\\d+)\\b'));
          return hit ? Number(hit[1]) : -1;
        }
        await new Promise((r) => setTimeout(r, 60));
      }
      return null;
    }, [listSel, id, MARK, word]);
    if (m !== null && m >= 0) out.push(m);
    if (process.env.SHIFT_DEBUG && id === ids[0]) console.log('first card', id, m);
  }
  return out;
}
// ...and a list whose cards are content-visibility:auto renders nothing of a card off screen (its innerText is empty): each
// card is scrolled in and read, in the list's order
async function readCards(s, cardSel, word) {
  const n = await s.page.evaluate((sel) => document.querySelectorAll(sel).length, cardSel);
  const out = [];
  for (let i = 0; i < n; i++) {
    const m = await s.page.evaluate(async ([sel, k, mk, w]) => {
      const el = document.querySelectorAll(sel)[k];
      if (!el) return -1;
      el.scrollIntoView({ block: 'center' });
      await new Promise((r) => setTimeout(r, 40));
      const re = new RegExp(mk + ' ' + w + ' ([0-9]+)(?![0-9])');
      const hit = (el.innerText || '').match(re);
      return hit ? Number(hit[1]) : -1;
    }, [cardSel, i, MARK, word]);
    if (m >= 0) out.push(m);
  }
  return out;
}
// the shift's markers as the screen shows them, in reading order (index numbers, as written)
const readMarkers = (s, word, custom) => s.page.evaluate(([m, w, c]) => {
  const re = new RegExp(c || (m + ' ' + w + ' (\\d+)\\b'), 'g');
  // the text a person reads, and what the form fields on the page hold (a profile's own values sit in its inputs)
  const NL = String.fromCharCode(10);
  const fields = [...document.querySelectorAll('input, textarea')].filter((el) => el.checkVisibility && el.checkVisibility()).map((el) => el.value).join(NL);
  return [...((document.body.innerText || '') + NL + fields).matchAll(re)].map((x) => Number(x[1]));
}, [MARK, word, custom || null]);
const descending = (xs) => xs.every((v, i) => i === 0 || v < xs[i - 1]);
const ascending = (xs) => xs.every((v, i) => i === 0 || v > xs[i - 1]);
const uniq = (xs) => xs.filter((v, i) => xs.indexOf(v) === i);

// a post every member's feed shows: a flagged one is under review and leaves a worker's feed (a supervisor still sees it)
const POST = psql(`select id from community_posts where hive_id = '${HIVE}' and deleted_at is null and not coalesce(flagged, false) and not coalesce(pinned, false) order by created_at desc limit 1`);
const PROJECT = psql(`select id from projects where hive_id = '${HIVE}' and deleted_at is null and project_type <> 'workorder' order by project_code limit 1`);
const LISTING = psql(`select id from marketplace_listings where seller_name = 'Joel Cruz' and status = 'published' order by created_at limit 1`);
const NODE = psql(`select id from asset_nodes where hive_id = '${HIVE}' and status = 'approved' and deleted_at is null order by tag limit 1`);
const PART = psql(`select id from inventory_items where hive_id = '${HIVE}' and status = 'approved' order by qty_on_hand desc, id limit 1`);
// two PM machines: one whose history the scheduler lists, one whose overdue task the logbook's PM panel shows
const PMA = psql(`select id from pm_assets where hive_id = '${HIVE}' and asset_name = 'Instrument air compressor K-901' limit 1`);
const PMA_TASK = psql(`select id from pm_scope_items where asset_id = '${PMA}' order by id limit 1`);
const PMB_NAME = 'Storage tank T-501';
// a fresh hive the shift joins (HS408), planted and removed by the walk
const JOIN_HIVE = '0f0f0f0f-0f0f-4f0f-8f0f-0f0f0f0f0f0f';
const PMB_TASK = psql(`select v.scope_item_id from v_pm_scope_items_truth v join pm_assets a on a.id = v.asset_id
  where v.hive_id = '${HIVE}' and a.asset_name = '${PMB_NAME}' order by v.days_until_due nulls last, v.scope_item_id limit 1`);
// a completion pays XP (trg_pm_achievement_xp) and queues an embedding: both are put back as they were after the shift
let PM_XP = '[]';
const pmSnap = async () => { PM_XP = psql(`select coalesce(json_agg(row_to_json(w)), '[]') from worker_achievements w where achievement_id = 'uptime_guardian'`); };
const pmClean = (mine) => `delete from embedding_outbox where source_table = 'pm_completions' and row_id::text in (select id::text from pm_completions where ${mine});
  delete from achievement_xp_log where source_id in (select id::text from pm_completions where ${mine});
  delete from pm_completions where ${mine};`;
const pmUnsnap = () => { const j = PM_XP.replace(/'/g, "''");
  psql(`set session_replication_role = replica;
    update worker_achievements w set xp_total = s.xp_total, current_level = s.current_level, last_action_at = s.last_action_at
      from json_populate_recordset(null::worker_achievements, '${j}') s where w.worker_name = s.worker_name and w.achievement_id = s.achievement_id;
    delete from worker_achievements w where w.achievement_id = 'uptime_guardian'
      and not exists (select 1 from json_populate_recordset(null::worker_achievements, '${j}') s where s.worker_name = w.worker_name);`); };
// the logbook PM panel's words for a task, from the view the panel reads (logbook.html daysLabel)
const pmLabel = (r) => r.is_overdue ? `${Math.abs(r.days_until_due)} day${Math.abs(r.days_until_due) === 1 ? '' : 's'} overdue`
  : r.is_due_soon ? `due in ${r.days_until_due} day${r.days_until_due === 1 ? '' : 's'}`
  : !r.next_due_date ? 'no history'
  : `next: ${new Date(r.next_due_date).toLocaleDateString('en-PH', { timeZone: 'Asia/Manila', month: 'short', day: 'numeric' })}`;

// a row: the unit the shift writes, the page that lists it, who reads it, and how the screen is read
const SHIFTS = [
  { id: 'HS402', table: 'community_posts', page: 'community.html', word: 'post', readers: ['Ana Reyes', 'Ernesto Villareal'],
    body: (p, i) => ({ hive_id: HIVE, author_name: p.name, content: `${MARK} post ${i}`, category: 'general' }),
    mine: `content like '${MARK} post %'`, order: 'newest first', window: 20,
    collect: async (s) => collectFeed(s, '#feed-list', 'post') },
  { id: 'HS406', table: 'community_replies', page: 'community.html', word: 'reply', readers: ['Ana Reyes', 'Ernesto Villareal'],
    body: (p, i) => ({ post_id: POST, hive_id: HIVE, author_name: p.name, content: `${MARK} reply ${i}` }),
    mine: `content like '${MARK} reply %'`, order: 'oldest first',
    open: async (s) => { await s.page.evaluate((i) => openThread(i), POST); await sleep(2500); } },
  { id: 'HS404', table: 'community_reactions', page: 'community.html', readers: ['Ana Reyes', 'Ernesto Villareal'],
    body: (p) => ({ post_id: POST, hive_id: HIVE, worker_name: p.name, emoji: 'fire' }),
    mine: `post_id = '${POST}' and emoji = 'fire'`, count: true,
    held: `select worker_name from community_reactions where post_id = '${POST}' and emoji = 'fire'`,
    // the post's card, brought into view and drawn (a stub keeps its data-post-id), then its count read
    open: async (s) => { for (let i = 0; i < 30; i++) {
        const drawn = await s.page.evaluate((pid) => { const c = document.querySelector(`[data-post-id="${pid}"]`); if (!c) return false;
          c.scrollIntoView({ block: 'center' }); return !c.classList.contains('vcard-stub') && !!document.getElementById(`rxn-fire-${pid}`); }, POST);
        if (drawn) break; await sleep(150); }
      await sleep(1500); },
    // the post's fire count, as the reader's card shows it, against the table
    read: async (s) => s.page.evaluate((i) => (document.getElementById(`rxn-fire-${i}`) || {}).textContent || '', POST),
    expect: () => psql(`select count(*) from community_reactions where post_id = '${POST}' and emoji = 'fire'`) },
  { id: 'HS460', table: 'project_progress_logs', page: 'project-manager.html', word: 'log', readers: ['Corazon Bautista', 'Ernesto Villareal'],
    body: (p, i) => ({ project_id: PROJECT, hive_id: HIVE, reported_by: p.name, notes: `${MARK} log ${i}` }),
    mine: `notes like '${MARK} log %'`, order: 'newest first',
    open: async (s) => { await s.page.evaluate((i) => openDetail(i), PROJECT); await sleep(3000); await tap(s, '#detail-tabs button[data-pane="progress"]'); await sleep(2000); } },
  { id: 'HS435', table: 'marketplace_inquiries', page: 'marketplace-seller.html', word: 'question', readers: ['Joel Cruz', 'Joel Cruz'],
    body: (p, i) => ({ listing_id: LISTING, buyer_name: p.name, buyer_contact: '0917 000 0000', message: `${MARK} question ${i}` }),
    mine: `message like '${MARK} question %'`, order: 'newest first', skipSelf: 'Joel Cruz',
    open: async (s) => { await tap(s, '#tab-inquiries'); await sleep(3000); } },
  { id: 'HS410', table: 'logbook', page: 'hive.html', word: 'machine', readers: ['Joel Cruz', 'Ernesto Villareal'],
    body: (p, i) => ({ hive_id: HIVE, worker_name: p.name, machine: `${MARK} machine ${i}`, problem: MARK, status: 'Open', maintenance_type: 'Inspection',
      category: 'Mechanical', date: new Date().toISOString() }),
    mine: `machine like '${MARK} machine %'`, order: 'newest first', window: 'page',
    // the hive's feed sits in a <details> a person opens
    open: async (s) => { await s.page.evaluate(() => { const d = document.querySelector('#feed')?.closest('details'); if (d && !d.open) { (d.querySelector('summary') || d).click(); if (!d.open) d.open = true; } }); await sleep(2500);
    },
    collect: async (s) => readCards(s, '#feed > .feed-card', 'machine') },
  { id: 'HS398', table: 'rcm_fmea_modes', page: 'asset-hub.html', word: 'mode', readers: ['Corazon Bautista', 'Ernesto Villareal'],
    body: (p, i) => ({ hive_id: HIVE, asset_id: NODE, function_text: MARK, failure_mode: `${MARK} mode ${i}`, created_by: p.name }),
    mine: `failure_mode like '${MARK} mode %'`, order: 'any',
    // the machine opened, then the reliability record behind the engineer view's toggle - as a person reaches it
    open: async (s) => { await s.page.evaluate(async (n) => { if (typeof openDetail === 'function') await openDetail(n); }, NODE); await sleep(3500);
      await s.page.evaluate(() => { const t = document.getElementById('asset-view-toggle'); if (t && t.getAttribute('aria-pressed') !== 'true' && t.getAttribute('aria-expanded') !== 'true') t.click(); }); await sleep(2500); } },
  { id: 'HS424', table: 'inventory_transactions', page: 'inventory.html', word: 'take', readers: ['Joel Cruz', 'Ernesto Villareal'],
    // the page's own write is the deduct RPC (balance and ledger row together); a delivery stocks the shelf first
    rpc: 'rpc/inventory_deduct', body: (p, i) => ({ p_item_id: PART, p_qty: 1, p_type: 'use', p_note: `${MARK} take ${i}` }),
    mine: `item_id = '${PART}' and note like '${MARK} take %'`, order: 'newest first', window: 20,
    plant: async () => { const sup = shift.find((x) => x.role === 'supervisor');
      HS424_BEFORE = psql(`select row_to_json(t) from inventory_items t where id = '${PART}'`);
      HS424_T = psql('select now()');
      await rest(sup, 'rpc/inventory_adjust', { p_item_id: PART, p_expected_qty: Number(psql(`select qty_on_hand from inventory_items where id = '${PART}'`)), p_new_qty: 100, p_note: 'HS W2 shift: stocked' }); },
    unplant: () => psql(`set session_replication_role = replica; delete from inventory_transactions where item_id = '${PART}' and created_at >= '${HS424_T}';
      update inventory_items set qty_on_hand = (('${HS424_BEFORE.replace(/'/g, "''")}')::json->>'qty_on_hand')::numeric where id = '${PART}';`),
    open: async (s) => { await s.page.evaluate((i) => openDetailModal(i), PART); await sleep(3500); } },
  { id: 'HS396', table: 'asset_nodes', page: 'asset-hub.html', word: 'machine', readers: ['Corazon Bautista', 'Ernesto Villareal'],
    body: (p, i) => ({ hive_id: HIVE, worker_name: p.name, tag: `HSW2-${String(i).padStart(2, '0')}`, name: `${MARK} machine ${i}`, level: 'equipment', status: 'pending' }),
    mine: `tag like 'HSW2-%'`, order: 'any',
    // the approval queue a supervisor opens
    open: async (s) => { await s.page.evaluate(() => { if (typeof loadPendingAssets === 'function') return loadPendingAssets(); }); await sleep(2500); },
    collect: async (s) => readCards(s, '#pending-assets-list .pending-row', 'machine') },
  { id: 'HS422', table: 'inventory_items', page: 'inventory.html', word: 'part', readers: ['Corazon Bautista', 'Ernesto Villareal'],
    body: (p, i) => ({ hive_id: HIVE, worker_name: p.name, part_number: `HSW2-P${String(i).padStart(2, '0')}`, part_name: `${MARK} part ${i}`, qty_on_hand: 1, status: 'pending' }),
    mine: `part_number like 'HSW2-P%'`, order: 'any',
    // the parts awaiting approval, behind the page's own Pending filter
    open: async (s) => { await s.page.evaluate(() => { if (typeof invShowPending === 'function') invShowPending(); }); await sleep(2000); },
    loadMore: '#inv-load-more-wrap', collect: async (s) => readCards(s, '#parts-list .part-card', 'part') },
  { id: 'HS458', table: 'project_items', page: 'project-manager.html', word: 'task', readers: ['Joel Cruz', 'Ernesto Villareal'],
    // the page's own write numbers a new task after the last one; the scope list reads by that number
    body: (p, i) => ({ project_id: PROJECT, hive_id: HIVE, title: `${MARK} task ${i}`, status: 'pending', sort_order: 9000 + i }),
    mine: `title like '${MARK} task %'`, order: 'oldest first',
    open: async (s) => { await s.page.evaluate((i) => openDetail(i), PROJECT); await sleep(3000); await tap(s, '#detail-tabs button[data-pane="scope"]'); await sleep(2000); },
    collect: async (s) => readCards(s, '#pane-scope tr[data-item-id]', 'task') },
  { id: 'HS452', table: 'pm_assets', page: 'pm-scheduler.html', word: 'asset', readers: ['Joel Cruz', 'Ernesto Villareal'],
    // a hive's PM program is set up by its supervisors (pm_assets_insert_guard) - the shift's writers are the supervisors
    body: (p, i) => ({ hive_id: HIVE, worker_name: p.name, asset_name: `${MARK} asset ${i}`, category: 'Pump' }), supervisorsOnly: true,
    mine: `asset_name like '${MARK} asset %'`, order: 'any',
    loadMore: '#pm-load-more-wrap', collect: async (s) => readCards(s, '#asset-list .asset-card', 'asset') },
  { id: 'HS445', table: 'marketplace_listings', page: 'marketplace.html', word: 'listing', readers: ['Ana Reyes', 'Ernesto Villareal'],
    // the page's own Post: a draft, submitted for review (a member cannot self-publish - guard_marketplace_listing_status)
    body: (p, i) => ({ hive_id: HIVE, seller_name: p.name, section: 'parts', title: `${MARK} listing ${i}`, description: MARK, price: 100 + i,
      category: 'Bearings', condition: 'new', status: 'draft', seller_verified: false, completed_sales: 0 }),
    mine: `title like '${MARK} listing %'`, order: 'newest first',
    // WorkHive's review publishes the day's submissions (the reviewer's act, not a member's - triggers off for it); the
    // marketplace then lists every one, newest first, 24 a page
    after: (t0) => psql(`set session_replication_role = replica; update marketplace_listings set status = 'published' where title like '${MARK} listing %' and created_at >= '${t0}';`),
    loadMore: '#btn-load-more', collect: async (s) => readCards(s, '.listing-card', 'listing') },
  // a machine register on two more pages - both list the hive's APPROVED machines plus the reader's own. Right after the
  // shift submits (logbook's Register form) each member's list holds their own pending machine and none of the other 28;
  // once a supervisor has approved them (asset-hub's queue, HS396) inventory's machine picker offers all 29
  { id: 'HS426', table: 'asset_nodes', page: 'logbook.html', word: 'machine', readers: ['Joel Cruz', 'Ernesto Villareal'], own: true,
    body: (p, i) => ({ hive_id: HIVE, worker_name: p.name, tag: `HSW2-${String(i).padStart(2, '0')}`, name: `${MARK} machine ${i}`, level: 'equipment', status: 'pending' }),
    mine: `tag like 'HSW2-%'`,
    open: async (s) => { await s.page.evaluate(() => { openAssetModal('manage'); if (typeof renderAssetList === 'function') renderAssetList(); }); await sleep(1500); } },
  { id: 'HS420', table: 'asset_nodes', page: 'inventory.html', word: 'machine', readers: ['Joel Cruz', 'Ernesto Villareal'],
    body: (p, i) => ({ hive_id: HIVE, worker_name: p.name, tag: `HSW2-${String(i).padStart(2, '0')}`, name: `${MARK} machine ${i}`, level: 'equipment', status: 'pending' }),
    mine: `tag like 'HSW2-%'`, order: 'any',
    // the supervisors' approval (walked on asset-hub as HS396) - the review's act, triggers off for it
    after: (t0) => psql(`set session_replication_role = replica; update asset_nodes set status = 'approved' where tag like 'HSW2-%' and created_at >= '${t0}';`),
    // the machine picker a person meets in Add Part
    open: async (s) => { await s.page.evaluate(() => openAddModal()); await sleep(1500); },
    collect: async (s) => readCards(s, '#asset-linker .asset-tag', 'machine') },
  // ── the CMMS import (integrations.html), a supervisor's write into the tables the shift is writing: after the shift's
  //    29, two supervisors each import a plant-sized file (phone-390, then desktop-1280) - the second meets what the shift
  //    and the first import already spent of the hive's daily limits ──────────────────────────────────────────────────
  { id: 'HS412', table: 'asset_nodes', page: 'integrations.html', readers: ['Corazon Bautista', 'Ernesto Villareal'], importing: 'asset',
    body: (p, i) => ({ hive_id: HIVE, worker_name: p.name, tag: `HSW2-${String(i).padStart(2, '0')}`, name: `${MARK} machine ${i}`, level: 'equipment', status: 'pending' }),
    mine: `tag like 'HSW2-%'` },
  { id: 'HS414', table: 'inventory_items', page: 'integrations.html', readers: ['Corazon Bautista', 'Ernesto Villareal'], importing: 'inventory',
    body: (p, i) => ({ hive_id: HIVE, worker_name: p.name, part_number: `HSW2-P${String(i).padStart(2, '0')}`, part_name: `${MARK} part ${i}`, qty_on_hand: 1, status: 'pending' }),
    mine: `part_number like 'HSW2-P%'` },
  { id: 'HS416', table: 'logbook', page: 'integrations.html', readers: ['Corazon Bautista', 'Ernesto Villareal'], importing: 'work_order',
    body: (p, i) => ({ hive_id: HIVE, worker_name: p.name, machine: `${MARK} machine ${i}`, problem: MARK, status: 'Open', maintenance_type: 'Inspection',
      category: 'Mechanical', date: new Date().toISOString() }),
    mine: `machine like '${MARK} machine %'` },
  { id: 'HS418', table: 'pm_assets', page: 'integrations.html', readers: ['Corazon Bautista', 'Ernesto Villareal'], importing: 'pm_schedule',
    // a PM program is a supervisor's write (pm_assets_insert_guard): the shift's writers are the supervisors
    body: (p, i) => ({ hive_id: HIVE, worker_name: p.name, asset_name: `${MARK} asset ${i}`, category: 'Pump' }), supervisorsOnly: true,
    mine: `asset_name like '${MARK} asset %'` },
  { id: 'HS454', table: 'pm_completions', page: 'pm-scheduler.html', word: 'pm', readers: ['Joel Cruz', 'Ernesto Villareal'],
    // the shift each checks off the same task on one machine (one per task, person and day - pm_completions_dedup_uidx)
    body: (p, i) => ({ asset_id: PMA, scope_item_id: PMA_TASK, hive_id: HIVE, worker_name: p.name, auth_uid: p.tok.user.id, status: 'done',
      notes: `${MARK} pm ${i}`, completed_at: new Date().toISOString() }),
    held: `select worker_name from pm_completions where scope_item_id = '${PMA_TASK}' and (completed_at at time zone 'UTC')::date = (now() at time zone 'UTC')::date`,
    mine: `notes like '${MARK} pm %'`, stamp: false,   // the time is the device's (its clock is not the database's); the marker alone counts them
    order: 'newest first',
    plant: pmSnap, restore: pmClean(`notes like '${MARK} pm %'`), unplant: pmUnsnap,
    // the machine's history, five a page behind its own Load more
    open: async (s) => { await s.page.evaluate((a) => openDetail(a), PMA); await sleep(2500); },
    loadMore: '#det-history-more', collect: async (s) => readCards(s, '#det-history .history-row', 'pm') },
  { id: 'HS428', table: 'pm_completions', page: 'logbook.html', readers: ['Joel Cruz', 'Ernesto Villareal'], count: true,
    // the logbook's own PM write: each member logs the overdue task on the tank as done
    body: (p, i) => ({ asset_id: psql(`select asset_id from pm_scope_items where id = '${PMB_TASK}'`), scope_item_id: PMB_TASK, hive_id: HIVE, worker_name: p.name,
      auth_uid: p.tok.user.id, status: 'done', notes: `${MARK} pm ${i} - Logged via Logbook: ${PMB_NAME}`, completed_at: new Date().toISOString() }),
    held: `select worker_name from pm_completions where scope_item_id = '${PMB_TASK}' and (completed_at at time zone 'UTC')::date = (now() at time zone 'UTC')::date`,
    mine: `notes like '${MARK} pm %'`, stamp: false,   // the time is the device's (its clock is not the database's); the marker alone counts them
   
    plant: pmSnap, restore: pmClean(`notes like '${MARK} pm %'`), unplant: pmUnsnap,
    // a person starting a PM entry for the tank: the panel lists its tasks (the on-track ones behind their own toggle)
    open: async (s) => { await s.page.evaluate(async (m) => { document.getElementById('f-maint-type').value = 'Preventive Maintenance';
        document.getElementById('f-machine').value = m; await loadPMTasksForAsset(); }, PMB_NAME); await sleep(1500);
      await s.page.evaluate((t) => { if (!document.querySelector(`.pm-task-check[data-item-id="${t}"]`) && typeof togglePMOnTrack === 'function') togglePMOnTrack(); }, PMB_TASK);
      await sleep(800); },
    // the task's own line on screen, against the view's words for it - and the view must have counted the shift
    read: async (s) => s.page.evaluate((t) => { const cb = document.querySelector(`.pm-task-check[data-item-id="${t}"]`); const row = cb && cb.closest('label');
      const sp = row && row.querySelector('.flex.items-center.gap-1\\.5'); return sp ? (sp.lastElementChild && sp.children.length > 1 ? sp.lastElementChild.textContent : '') : 'task not on screen'; }, PMB_TASK),
    expect: () => { const r = JSON.parse(psql(`select row_to_json(v) from v_pm_scope_items_truth v where scope_item_id = '${PMB_TASK}'`));
      return r.is_overdue ? `STILL OVERDUE - the shift's ${r.days_until_due} did not count` : pmLabel(r); },
    label: (shown, want) => `the tank's task reads "${shown}"; the view says "${want}"` },
  { id: 'HS464', table: 'projects', page: 'project-manager.html', word: 'project', readers: ['Joel Cruz', 'Ernesto Villareal'],
    // the page's own create: a code from generate_project_code, then the row, in Planning
    body: async (p, i) => ({ hive_id: HIVE, project_code: await rpcValue(p, 'generate_project_code', { p_hive_id: HIVE, p_type: 'contractor', p_year: new Date().getFullYear() }),
      name: `${MARK} project ${i}`, project_type: 'contractor', status: 'planning', owner_name: p.name }),
    mine: `name like '${MARK} project %'`, order: 'newest first', unplant: () => psql(`delete from code_counters where scope like 'project:${HIVE}:%'`),
    // the list opens on Active; a new project is in Planning - the tab a person taps, 30 cards a page
    open: async (s) => { await tap(s, '#status-tabs button[data-status="planning"]'); await sleep(1500); },
    loadMore: '#pm-load-more-wrap', collect: async (s) => readCards(s, '#card-grid .pcard', 'project') },
  { id: 'HS456', table: 'project_change_orders', page: 'project-manager.html', word: 'change', readers: ['Joel Cruz', 'Ernesto Villareal'],
    // the page's own submit: the number from generate_change_order_number, then the request, pending a supervisor
    body: async (p, i) => ({ project_id: PROJECT, hive_id: HIVE, co_number: await rpcValue(p, 'generate_change_order_number', { p_project_id: PROJECT }),
      title: `${MARK} change ${i}`, scope_change: MARK, status: 'pending', requested_by: p.name }),
    mine: `title like '${MARK} change %'`, order: 'newest first', unplant: () => psql(`delete from code_counters where scope = 'change_order:${PROJECT}'`),
    open: async (s) => { await s.page.evaluate((i) => openDetail(i), PROJECT); await sleep(3000); await tap(s, '#detail-tabs button[data-pane="changes"]'); await sleep(2000); },
    collect: async (s) => readCards(s, '#pane-changes .co-card', 'change') },
  { id: 'HS462', table: 'project_roles', page: 'project-manager.html', readers: ['Joel Cruz', 'Ernesto Villareal'],
    // the hive's supervisors put the whole shift on a project as reviewers, one after another (a role is a supervisor's
    // write - project_roles_supervisor_all); the Roles pane then lists the team, newest assignment first
    by: (i) => { const sups = shift.filter((x) => x.role === 'supervisor'); return sups[i % sups.length]; },
    held: `select worker_name from project_roles where project_id = '${PROJECT}' and role = 'reviewer' and deleted_at is null`,
    body: (p, i) => ({ project_id: PROJECT, hive_id: HIVE, worker_name: p.name, role: 'reviewer', notes: `${MARK} role ${i}` }),
    mine: `project_id = '${PROJECT}' and notes like '${MARK} role %'`, stamp: 'assigned_at', order: 'newest first',
    restore: `delete from hive_audit_log where target_id::text in (select id::text from project_roles where notes like '${MARK} role %');
      delete from project_roles where notes like '${MARK} role %';`,
    open: async (s) => { await s.page.evaluate((i) => openDetail(i), PROJECT); await sleep(3000); await tap(s, '#detail-tabs button[data-pane="roles"]'); await sleep(2000); },
    // a role pill names its person: the reviewers as the screen lists them, each read back to the order they were added
    // (the Reviewer group only: a member who also holds an owner or planner role is listed there too)
    collect: async (s) => { const names = await s.page.evaluate(() => {
        const h = [...document.querySelectorAll('#pane-roles h4')].find((x) => /^reviewer$/i.test(x.textContent.trim()));
        return h ? [...h.parentElement.querySelectorAll('[data-role-id]')].map((el) => (el.firstChild && el.firstChild.textContent || el.textContent || '').trim()) : []; });
      return names.map((n) => HS462_ORDER.indexOf(n)).filter((x) => x >= 0); } },
  // ── OWN: a record each member writes for themselves. After the shift, a member's page holds THEIR item and none of the
  //    other 28 - the list it keeps is one person's, and nothing of a teammate's leaks into it ────────────────────────────
  { id: 'HS437', table: 'marketplace_listings', page: 'marketplace-seller.html', word: 'listing', readers: ['Joel Cruz', 'Ernesto Villareal'], own: true,
    body: (p, i) => ({ hive_id: HIVE, seller_name: p.name, section: 'parts', title: `${MARK} listing ${i}`, description: MARK, price: 100 + i, category: 'Bearings', status: 'draft' }),
    mine: `title like '${MARK} listing %'` },
  { id: 'HS466', table: 'resume_documents', page: 'resume.html', word: 'resume', readers: ['Joel Cruz', 'Ana Reyes'], own: true,
    // a real (minimal) JSON Resume: the page opens a stored resume only when its document has basics
    body: (p, i) => ({ auth_uid: p.tok.user.id, worker_name: p.name, hive_id: HIVE, title: `${MARK} resume ${i}`, template: 'ats-plain',
      doc: { basics: { name: p.name, label: `${MARK} resume ${i}` }, meta: { title: `${MARK} resume ${i}`, template: 'ats-plain' } } }),
    mine: `title like '${MARK} resume %'` },
  { id: 'HS439', table: 'marketplace_sellers', page: 'marketplace-seller.html', word: 'handle', readers: ['Joel Cruz', 'Ernesto Villareal'], own: true,
    // the whole shift saves a Messenger handle in the same minutes, the page's own upsert: the two who already sell edit
    // their row, the other 27 become sellers by it
    upsert: 'marketplace_sellers?on_conflict=worker_name',
    plant: async () => { HS439_BEFORE = psql(`select string_agg(quote_literal(worker_name), ',') from marketplace_sellers`); },
    body: (p, i) => ({ worker_name: p.name, auth_uid: p.tok.user.id, messenger_username: `${MARK} handle ${i}`.replace(/ /g, '.'), updated_at: new Date().toISOString() }),
    re: 'HS-W2\\.shift\\.handle\\.(\\d+)\\b', mine: `messenger_username like '${MARK.replace(/ /g, '.')}.handle.%'`,
    unplant: () => psql(`set session_replication_role = replica;
      delete from marketplace_sellers where messenger_username like '${MARK.replace(/ /g, '.')}.handle.%' and worker_name not in (${HS439_BEFORE});
      update marketplace_sellers set messenger_username = null where messenger_username like '${MARK.replace(/ /g, '.')}.handle.%';`) },
  { id: 'HS394', table: 'alert_dismissals', page: 'alert-hub.html', readers: ['Joel Cruz', 'Ernesto Villareal'],
    // the shift marks the hive's alerts SEEN in the same minutes - 29 people, 14 alerts, cycling: the first to act on an
    // alert holds it (one record per hive and alert; a later write is ignored, never a replacement - HS393's fix)
    plant: async () => {
      const s = await session(browser, shift.find((x) => x.name === 'Ernesto Villareal'), 'desktop-1280');
      await s.page.goto(`${ORIGIN}/alert-hub.html`, { waitUntil: 'domcontentloaded', timeout: 45000 }); await sleep(8000);
      HS394_KEYS = await s.page.evaluate(() => [...document.querySelectorAll('.alert[data-alert-key]')].map((e) => e.getAttribute('data-alert-key')));
      await s.ctx.close();
    },
    upsert: 'alert_dismissals?on_conflict=hive_id,alert_key', upsertPrefer: ',resolution=ignore-duplicates',
    body: (p, i) => ({ hive_id: HIVE, alert_key: HS394_KEYS[i % HS394_KEYS.length], action: 'acknowledged', actor: p.name }),
    get mine() { return `hive_id = '${HIVE}' and action = 'acknowledged' and alert_key in (${HS394_KEYS.map((k) => `'${k.replace(/'/g, "''")}'`).join(',') || "''"})`; },
    expectLanded: () => HS394_KEYS.length,
    // each alert's card, as the reader's feed shows it: dimmed, "Seen by" the member who acted on it first
    check: async (s, writers) => {
      const seen = await s.page.evaluate(() => Object.fromEntries([...document.querySelectorAll('.alert[data-alert-key]')].map((e) =>
        [e.getAttribute('data-alert-key'), ((e.querySelector('.alert-seen-badge') || {}).textContent || '').replace(/^Seen by\s*/i, '').trim()])));
      const wrong = HS394_KEYS.filter((k, j) => seen[k] !== writers[j].name);
      return { ok: HS394_KEYS.length > 0 && wrong.length === 0,
        says: `${HS394_KEYS.length - wrong.length} of the ${HS394_KEYS.length} alerts read "Seen by" the member who acted first` + (wrong.length
          ? ` - WRONG: ${wrong.slice(0, 3).map((k) => `${k} reads "${seen[k] || '(not on screen)'}"`).join('; ')}` : `; the other ${writers.length - HS394_KEYS.length} members' later marks replaced none`) };
    } },
  { id: 'HS408', table: 'hive_members', page: 'hive.html', readers: ['Ernesto Villareal', 'Joel Cruz'],
    // the day a hive starts: its supervisor shares the invite code and the shift joins within minutes (join_hive_by_code,
    // the page's own join). A fresh hive, planted with its supervisor; the roster then must list every member
    get hive() { return JOIN_HIVE; },
    plant: async () => psql(`set session_replication_role = replica;
      insert into hives (id, name, invite_code, created_by) values ('${JOIN_HIVE}', 'HS-W2 shift hive', 'HSW2JN', 'Ernesto Villareal');
      insert into hive_members (hive_id, worker_name, role, status, auth_uid)
        select '${JOIN_HIVE}', worker_name, 'supervisor', 'active', auth_uid from hive_members where hive_id = '${HIVE}' and worker_name = 'Ernesto Villareal';`),
    skipSelf: 'Ernesto Villareal', rpc: 'rpc/join_hive_by_code', body: (p) => ({ p_code: 'HSW2JN', p_worker_name: p.name }),
    mine: `hive_id = '${JOIN_HIVE}' and role = 'worker' and status = 'active'`, stamp: false,
    restore: `delete from hive_audit_log where hive_id = '${JOIN_HIVE}'; delete from hive_members where hive_id = '${JOIN_HIVE}';
      delete from hive_quotas where hive_id = '${JOIN_HIVE}'; delete from hives where id = '${JOIN_HIVE}';`,
    // the roster, opened as a person opens it: every member who joined, and the supervisor, by name - and its count
    check: async (s, writers) => {
      if (await s.page.evaluate(() => (document.getElementById('btn-toggle-members') || {}).getAttribute?.('aria-expanded') !== 'true')) await tap(s, '#btn-toggle-members');
      await sleep(1500);
      // a row off screen is drawn only when near (content-visibility): each is brought into view and read in turn
      const r = await s.page.evaluate(async () => { const rows = [...document.querySelectorAll('#members-list > [data-hv-rows] > *')];
        const out = [];
        for (const row of rows) { row.scrollIntoView({ block: 'center' }); await new Promise((res) => setTimeout(res, 60)); out.push(row.innerText); }
        return { text: out.join('\n') || (document.getElementById('members-list') || {}).innerText || '',
        shown: getComputedStyle(document.getElementById('members-list')).display,
        count: ((document.getElementById('roster-count') || {}).textContent || '').replace(/[^0-9]/g, '') }; });
      const want = ['Ernesto Villareal', ...writers.map((x) => x.name)];
      const missing = want.filter((n) => !r.text.includes(n));
      return { ok: missing.length === 0 && r.count === String(want.length),
        says: `the roster lists ${want.length - missing.length} of the hive's ${want.length} members by name and counts ${r.count || '(none)'}` + (missing.length ? ` - MISSING: ${missing.slice(0, 4).join(', ')} (list display ${r.shown}, ${r.text.length} chars)` : '') };
    } },
  { id: 'HS441', table: 'service_providers', page: 'marketplace-seller.html', word: 'provider', readers: ['Ana Reyes', 'Ernesto Villareal'], own: true,
    // the shift each registers as a freelance provider (svcRegister's insert); a member who already is one is not part of it
    held: `select worker_name from service_providers where provider_type = 'freelancer' and worker_name is not null`,
    body: (p, i) => ({ provider_type: 'freelancer', auth_uid: p.tok.user.id, worker_name: p.name, display_name: `${MARK} provider ${i}`,
      categories: ['Mechanical'], service_areas: ['Batangas'], availability: 'offline' }),
    mine: `display_name like '${MARK} provider %'`,
    restore: `delete from hive_audit_log where target_id::text in (select id::text from service_providers where display_name like '${MARK} provider %');
      delete from service_providers where display_name like '${MARK} provider %';`,
    // the provider console, behind the Services tab
    open: async (s) => { await tap(s, '#tab-services'); await sleep(3500); } },
  { id: 'HS443', table: 'marketplace_inquiries', page: 'marketplace.html', word: 'question', readers: ['Ana Reyes', 'Ernesto Villareal'], own: true, skipSelf: 'Joel Cruz',
    body: (p, i) => ({ listing_id: LISTING, buyer_name: p.name, buyer_contact: '0917 000 0000', message: `${MARK} question ${i}` }),
    mine: `message like '${MARK} question %'` },
  // the assistant lists no ratings at all, to anyone: a rating is a note to the team that improves it
  { id: 'HS400', table: 'ai_reply_feedback', page: 'assistant.html', word: 'q', readers: ['Joel Cruz', 'Ana Reyes'], nolist: true,
    body: (p, i) => ({ hive_id: HIVE, worker_name: p.name, agent: 'assistant', source: 'probe', question: `${MARK} q ${i}`, rating: 1 }),
    mine: `question like '${MARK} q %'` },
  // ── RETIRED admin pages: a member reaches them as a no-access gate - the shift's records are never listed there, and no
  //    control on the screen can act on one ───────────────────────────────────────────────────────────────────────────
  ...[['HS431', 'marketplace-admin.html', 'marketplace_orders'], ['HS433', 'marketplace-admin.html', 'marketplace_sellers'],
      ['HS447', 'platform-actions.html', 'marketplace_listings'], ['HS449', 'platform-actions.html', 'marketplace_sellers'],
      ['HS451', 'platform-actions.html', 'platform_feedback']].map(([rid, pg, tbl]) => ({
    id: rid, table: tbl, page: pg, readers: ['Joel Cruz', 'Ana Reyes'], retired: true })),
];
let HS424_BEFORE = '', HS424_T = '', HS439_BEFORE = '', HS462_ORDER = [], HS394_KEYS = [];
const IMPORT_CLEAN = [];

const browser = await chromium.launch({ headless: true });
const report = { ran: new Date().toISOString(), hive: HIVE, members: shift.length, rows: {} };
let failed = 0;
for (const sc of SHIFTS) {
  if (ONLY.size && !ONLY.has(sc.id)) continue;
  // a member who already holds this one-per-person row (a reaction they made before) is not part of this shift's writes
  const already = sc.held ? new Set(psql(sc.held).split(/\r?\n/).filter(Boolean)) : new Set();
  const writers = shift.filter((p) => p.name !== sc.skipSelf && !already.has(p.name) && (!sc.supervisorsOnly || p.role === 'supervisor')
    && (!sc.writersSql || psql(sc.writersSql).split(/\r?\n/).includes(p.name)));
  if (sc.plant) await sc.plant();
  if (sc.id === 'HS462') HS462_ORDER = writers.map((x) => x.name);
  const t0 = psql('select now()');
  const statuses = [];
  if (sc.patch) { for (let i = 0; i < writers.length; i++) { statuses.push(await rest(writers[i], sc.patch(writers[i]), sc.body(writers[i], i), 'PATCH')); await sleep(150); } }
  else if (sc.upsert) { for (let i = 0; i < writers.length; i++) { statuses.push(await rest(writers[i], sc.upsert, sc.body(writers[i], i), 'POST', sc.upsertPrefer || ',resolution=merge-duplicates')); await sleep(150); } }
  // sc.by: who presses the button when it is not the person the row is about (a supervisor assigns a member's role)
  else if (!sc.retired) for (let i = 0; i < writers.length; i++) { statuses.push(await rest(sc.by ? sc.by(i) : writers[i], sc.rpc || sc.table, await sc.body(writers[i], i))); await sleep(150); }
  const stamp = sc.stamp || 'created_at';
  if (sc.after) sc.after(t0);
  const landed = sc.retired ? 0 : (Number(psql(`select count(*) from ${sc.table} where ${sc.mine}${sc.patch || sc.upsert || sc.stamp === false ? '' : ` and ${stamp} >= '${t0}'`}`)) || 0);
  const walks = [];
  for (const [who, vp] of [[sc.readers[0], 'phone-390'], [sc.readers[1], 'desktop-1280']]) {
    const p = shift.find((x) => x.name === who);
    const s = await session(browser, p, vp, sc.hive || HIVE);
    const w = { reader: `${who} @ ${vp}` };
    try {
      if (TEETH && sc.page === TEETH_PAGE) await s.page.route(`**/${TEETH_PAGE}*`, (r) => r.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: TEETH_HTML }));
      await s.page.goto(`${ORIGIN}/${sc.page}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await sleep(6000);
      if (sc.open) await sc.open(s);
      // a windowed list: its own Load more, pressed until it goes away - the whole list, as a person reaches it
      if (sc.loadMore) {
        for (let k = 0; k < 25; k++) {
          const more = await s.page.evaluate((sel) => { const w = document.querySelector(sel);
            const b = w && (w.matches('button') ? w : !w.classList.contains('hidden') && w.querySelector('button:not(.hidden)'));
            if (!b || (b.checkVisibility && !b.checkVisibility())) return false; b.scrollIntoView({ block: 'center' }); b.click(); return true; }, sc.loadMore);
          if (!more) break;
          await sleep(700);
        }
      }
      if (sc.check) {
        const r = await sc.check(s, writers);
        w.ok = r.ok; w.says = r.says;
      } else if (sc.importing) {
        const tag = `HSW2I${sc.id.slice(2)}${walks.length ? 'B' : 'A'}`;
        const r = await importWalk(s, sc.importing, tag);
        IMPORT_CLEAN.push(...r.clean, `delete from external_sync where hive_id = '${HIVE}' and external_id like '${tag}-%';`);
        w.ok = r.ok; w.says = r.says;
      } else if (sc.retired) {
        const r = await s.page.evaluate(() => {
          const ACT = /\b(approve|reject|suspend|verify|resolve|delete|ban|refund|release|archive|unpublish|reinstate)\b/i;
          const live = [...document.querySelectorAll('button, [role="button"], a[href]')].filter((el) => el.checkVisibility && el.checkVisibility({ visibilityProperty: true, opacityProperty: true })
            && !el.closest('[inert], [aria-hidden="true"]') && !el.disabled && ACT.test(el.innerText || el.getAttribute('aria-label') || ''));
          const rows = [...document.querySelectorAll('table tbody tr, [data-listing-id], [data-order-id], [data-seller-id], [data-feedback-id]')]
            .filter((el) => el.checkVisibility && el.checkVisibility() && !el.closest('[inert], [aria-hidden="true"]'));
          return { controls: live.length, rows: rows.length };
        });
        w.ok = r.controls === 0 && r.rows === 0;
        w.says = w.ok ? 'a retired admin page: no record listed for a member, no control to act on one' : `${r.rows} record row(s) and ${r.controls} control(s) on a member's screen`;
      } else if (sc.nolist) {
        const seen = uniq(await readMarkers(s, sc.word));
        w.ok = seen.length === 0;
        w.says = seen.length ? `${seen.length} of the shift's ${landed} ratings are listed on a member's screen` : `the page lists no ratings; none of the shift's ${landed} appears`;
      } else if (sc.own) {
        const seen = uniq(await readMarkers(s, sc.word, sc.re));
        const mine = writers.findIndex((x) => x.name === s.p.name);
        const others = seen.filter((v) => v !== mine);
        w.ok = mine >= 0 && seen.includes(mine) && others.length === 0;
        w.says = `${s.p.name}'s own item ${seen.includes(mine) ? 'is' : 'is NOT'} on screen; ${others.length} of the other ${landed - 1} members' items ${others.length ? 'LEAK into it' : 'are not'}`;
      } else if (sc.count) {
        const shown = (await sc.read(s)).replace('+', '').trim();
        const want = sc.expect();
        w.ok = shown === want; w.says = sc.label ? sc.label(shown, want) : `the card counts ${shown || '0'}; the table holds ${want}`;
      } else {
        const seen = uniq(sc.collect ? await sc.collect(s) : await readMarkers(s, sc.word));
        const win = typeof sc.window === 'number' ? sc.window : null;
        const want = Math.min(landed, win || landed);
        const orderOk = sc.order === 'any' ? true : sc.order === 'oldest first' ? ascending(seen) : descending(seen);
        // 'page': a timeline that shows the newest of everything - the shift's newest must lead and none may be skipped
        const contiguous = sc.window === 'page' ? (seen.length > 0 && seen[0] === landed - 1 && seen.every((v, i) => v === landed - 1 - i))
          : sc.order === 'any' ? seen.length >= want
          : seen.length >= want && (sc.order === 'oldest first' ? seen[0] === 0 : seen[0] === landed - 1);
        const moreSaid = !win || landed <= win || await s.page.evaluate(() => !!document.querySelector('[data-wh-more-note], .load-more, #btn-load-more, button[onclick*="loadMore"]'));
        w.ok = orderOk && contiguous && moreSaid;
        w.says = `${seen.length} of the shift's ${landed} on screen (${sc.order}${win ? ', a window of ' + win : sc.window === 'page' ? ', the newest of the page' : ''}): ${seen.slice(0, 6).join(', ')}${seen.length > 6 ? ' ...' : ''}${orderOk ? '' : ' - OUT OF ORDER'}${moreSaid ? '' : ' - no word that more exist'}`;
      }
    } catch (e) { w.ok = false; w.says = 'walk error: ' + String(e.message || e).slice(0, 160); }
    finally { await s.ctx.close().catch(() => {}); }
    walks.push(w);
    console.log(`  ${w.ok ? 'ok ' : 'BAD'} ${sc.id} ${w.reader}: ${w.says}`);
  }
  // the imports' rows, their ledger entries, the import log and what the imports queued for embedding
  if (IMPORT_CLEAN.length) {
    psql(`set session_replication_role = replica; ${IMPORT_CLEAN.join(' ')}
      delete from cmms_audit_log where hive_id = '${HIVE}' and created_at >= '${t0}';
      delete from embedding_outbox o where o.enqueued_at >= '${t0}' and o.source_table in ('logbook', 'asset_nodes', 'inventory_items', 'pm_assets')
        and not exists (select 1 from logbook l where o.source_table = 'logbook' and l.id::text = o.row_id::text)
        and not exists (select 1 from asset_nodes a where o.source_table = 'asset_nodes' and a.id::text = o.row_id::text)
        and not exists (select 1 from inventory_items v where o.source_table = 'inventory_items' and v.id::text = o.row_id::text)
        and not exists (select 1 from pm_assets m where o.source_table = 'pm_assets' and m.id::text = o.row_id::text);`);
    IMPORT_CLEAN.length = 0;
  }
  if (sc.restore) psql(`set session_replication_role = replica; ${sc.restore}`);
  // the rows go, and first the trail entries their INSERT triggers wrote about them (audit_shared_change's add_* rows)
  else if (!sc.retired) psql(`set session_replication_role = replica; delete from hive_audit_log where target_id::text in (select id::text from ${sc.table}
    where ${sc.mine} and ${stamp} >= '${t0}'); delete from ${sc.table} where ${sc.mine} and ${stamp} >= '${t0}';`);
  if (sc.unplant) sc.unplant();
  // a shift whose writes meet a one-per-key record (alerts: 29 marks, 14 alerts) lands one row a key, not one a write
  const ok = (sc.retired || landed === (sc.expectLanded ? sc.expectLanded() : writers.length)) && walks.every((w) => w.ok);
  if (!ok) failed++;
  report.rows[sc.id] = { ok, table: sc.table, page: sc.page, wrote: writers.length, landed, refused: statuses.filter((x) => x >= 300).length, walks };
  console.log(`${ok ? 'PASS' : 'FAIL'} ${sc.id} ${sc.page} ${sc.table}: ${landed}/${writers.length} landed; ${walks.map((w) => w.says).join(' | ')}`);
}
await browser.close();
// what the shift's rows PAID goes with them - the cleanups delete with triggers off, so the XP they paid stayed standing
psql(readFileSync('tools/hs_paid_residue.sql', 'utf8'));
if (TEETH) {
  // the walk read the COMMITTED page: it must fail there (the import that refused a whole file and said "Check console")
  writeFileSync('hive_scale_shift_teeth.json', JSON.stringify(report, null, 1));
  console.log(`${failed ? 'PASS' : 'FAIL'} hive-scale-shift teeth: on the committed ${TEETH_PAGE} the walk ${failed ? 'failed, as it must' : 'PASSED - the teeth did not bite'}`);
  process.exit(failed ? 0 : 1);
}
if (ONLY.size) {
  try { const prior = JSON.parse(readFileSync(OUT, 'utf8')); if (Date.now() - Date.parse(prior.ran) < 3 * 3600 * 1000) report.rows = { ...prior.rows, ...report.rows }; } catch (_) { /* first run */ }
  failed = Object.values(report.rows).filter((r) => !r.ok).length;
}
writeFileSync(OUT, JSON.stringify(report, null, 1));
const n = Object.keys(report.rows).length;
console.log(`${failed ? 'FAIL' : 'PASS'} hive-scale-shift: ${n - failed}/${n} pages kept a shift of ${shift.length} writes in order`);
process.exitCode = failed ? 1 : 0;
