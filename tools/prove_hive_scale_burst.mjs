// prove_hive_scale_burst — Wave HS (the hive at thirty), lens W2: a shift of thirty writes at once (2026-10-30).
//
//   W2  at a shift change thirty members write in the same minutes: no honest write is refused by a per-person or
//       per-hive limit, the list keeps every item in its order, and a write that waits says so.
//
// THE BURST, AS THE THIRTY PEOPLE. Every active member of the 30-member hive signs in (their own account, their own
// JWT) and, for each unit a member writes, all of them send the page's write at the same moment through PostgREST - the
// path a page takes, so RLS, every trigger and every rate limit decides exactly as it would on a shift change. The read:
//   landed    - how many of the thirty writes the database kept
//   refused   - each refusal's status and sentence: a per-PERSON limit is honest, a per-HIVE limit that refuses one
//               member because the rest of the hive wrote is the W2 defect, and its sentence must say whose limit it was
//   order     - the rows read back newest-first come out in their created_at order, no gaps (the list's own order)
// Every row the burst writes carries a marker and is removed after (triggers off for the removal).
//
//   node tools/prove_hive_scale_burst.mjs [logbook community_posts ...]   -> hive_scale_burst_report.json; exit 1 on any failure
import { spawnSync } from 'child_process';
import { writeFileSync } from 'fs';

const SB = 'http://127.0.0.1:54321';
const KEY = 'sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH';   // the LOCAL stack's publishable key (public by design)
const HIVE = '30303030-3030-4030-8030-303030303030';
const OUT = 'hive_scale_burst_report.json';
const MARK = 'HS-W2 burst';
const ONLY = new Set(process.argv.slice(2).filter((a) => /^[a-z_]+$/.test(a)));
const TEETH = process.argv.includes('--teeth');
// a shift is not one millisecond: concurrent inserts each count the others as absent (their rows are not committed yet), so
// a per-hive cap never bites inside a true burst. The STAGGERED pass sends the same thirty writes one after another across
// a minute, which is how a shift change actually arrives - and where a limit shared by the whole hive shows itself.
const STAGGER_MS = 1500;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function psql(sql) {
  const r = spawnSync('docker', ['exec', '-i', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-At', '-v', 'ON_ERROR_STOP=1'],
    { input: sql, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 });
  if (r.status !== 0) throw new Error('psql: ' + (r.stderr || '').slice(0, 300));
  return (r.stdout || '').trim().split('\n').filter((l) => l && !/^(SET|INSERT|UPDATE|DELETE)/.test(l)).join('\n');
}

// the thirty, signed in as themselves
const people = psql(`select string_agg(hm.worker_name || '|' || wp.username || '|' || hm.auth_uid || '|' || hm.role, E'\\n' order by hm.worker_name)
  from hive_members hm join worker_profiles wp on wp.auth_uid = hm.auth_uid
  where hm.hive_id = '${HIVE}' and hm.status = 'active' and wp.username is not null`).split('\n').filter(Boolean)
  .map((l) => { const [name, user, uid, role] = l.split('|'); return { name, user, uid, role }; });
for (const p of people) {
  const r = await fetch(`${SB}/auth/v1/token?grant_type=password`, { method: 'POST', headers: { apikey: KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: `${p.user}@auth.workhiveph.com`, password: 'test1234' }) });
  const j = await r.json().catch(() => ({}));
  p.jwt = j.access_token || null;
  await sleep(120);   // the auth server's own pace - a sign-in storm is not what this measures
}
const signedIn = people.filter((p) => p.jwt);
// a token used in the same instant it was minted can be refused "JWT issued at future" (the auth and API containers' clocks
// differ by a hair) - a person signs in seconds before they write, so the burst does too
await sleep(3000);

async function rest(p, path, body, method = 'POST', prefer = '') {
  const r = await fetch(`${SB}/rest/v1/${path}`, { method, headers: { apikey: KEY, Authorization: `Bearer ${p.jwt}`,
    'Content-Type': 'application/json', Prefer: 'return=minimal' + prefer }, body: JSON.stringify(body) });
  let msg = '';
  if (r.status >= 300) { try { const j = await r.json(); msg = j.message || JSON.stringify(j); } catch (_) { msg = await r.text().catch(() => ''); } }
  return { status: r.status, msg };
}
// an RPC the page calls before its write (a project's code, a change order's number): at a shift change everyone presses
// at once, so these are called at once too - and their answers go into the rows
async function rpcValue(p, fn, args) {
  const r = await fetch(`${SB}/rest/v1/rpc/${fn}`, { method: 'POST', headers: { apikey: KEY, Authorization: `Bearer ${p.jwt}`,
    'Content-Type': 'application/json' }, body: JSON.stringify(args) });
  return r.ok ? r.json() : null;
}

// a post for the replies and reactions to land on; a project for the progress logs and tasks
const POST = psql(`select id from community_posts where hive_id = '${HIVE}' and deleted_at is null order by created_at desc limit 1`);
const PROJECT = psql(`select id from projects where hive_id = '${HIVE}' and deleted_at is null order by project_code limit 1`);
const NODE = psql(`select id from asset_nodes where hive_id = '${HIVE}' and status = 'approved' and deleted_at is null order by tag limit 1`);
const LISTING = psql(`select id from marketplace_listings where seller_name = 'Joel Cruz' and status = 'published' order by created_at limit 1`);
// a fresh hive the shift joins (hive_members), planted and removed by the unit
const JOIN_HIVE = '0f0f0f0f-0f0f-4f0f-8f0f-0f0f0f0f0f0f';
// change orders and roles belong to a planned project (a work-order bundle carries none - project-manager.html hides them)
const PROJ_NW = psql(`select id from projects where hive_id = '${HIVE}' and deleted_at is null and project_type <> 'workorder' order by project_code limit 1`);
const PMA = psql(`select id from pm_assets where hive_id = '${HIVE}' and asset_name = 'Instrument air compressor K-901' limit 1`);
const PMA_TASK = psql(`select id from pm_scope_items where asset_id = '${PMA}' order by id limit 1`);

// unit -> what one member writes (the page's own write, reduced to its columns), and how its burst is read back
const UNITS = {
  logbook: { table: 'logbook', body: (p, i) => ({ hive_id: HIVE, worker_name: p.name, machine: `${MARK} machine ${i}`, problem: MARK, status: 'Open', date: new Date().toISOString() }),
    mine: `machine like '${MARK} machine %'` },
  community_posts: { table: 'community_posts', body: (p, i) => ({ hive_id: HIVE, author_name: p.name, content: `${MARK} post ${i}`, category: 'general' }),
    mine: `content like '${MARK} post %'` },
  community_replies: { table: 'community_replies', body: (p, i) => ({ post_id: POST, hive_id: HIVE, author_name: p.name, content: `${MARK} reply ${i}` }),
    mine: `content like '${MARK} reply %'` },
  community_reactions: { table: 'community_reactions', body: (p) => ({ post_id: POST, hive_id: HIVE, worker_name: p.name, emoji: 'fire' }),
    mine: `post_id = '${POST}' and emoji = 'fire'`, after: true },
  marketplace_listings: { table: 'marketplace_listings', body: (p, i) => ({ hive_id: HIVE, seller_name: p.name, section: 'parts', title: `${MARK} listing ${i}`,
    description: MARK, price: 100 + i, category: 'Bearings', status: 'draft' }), mine: `title like '${MARK} listing %'`,
    // a BUSY day: twenty teammates' listings already published in the last 24 hours. The limit runs as the member, so its
    // count passes through RLS and sees only what that member may see - a teammate's draft is invisible, a published
    // listing is not. Without this the hive-wide count never saw anyone else and could not bite.
    plant: () => psql(`set session_replication_role = replica;
      insert into marketplace_listings (hive_id, seller_name, auth_uid, section, title, description, price, category, status, created_at)
      select '${HIVE}', hm.worker_name, hm.auth_uid, 'parts', '${MARK} busy ' || row_number() over (), '${MARK}', 300, 'Bearings', 'published', now() - interval '2 hours'
      from (select * from hive_members where hive_id = '${HIVE}' and status = 'active' order by worker_name desc limit 20) hm;`),
    unplant: () => psql(`set session_replication_role = replica; delete from marketplace_listings where title like '${MARK} busy %';`) },
  marketplace_inquiries: { table: 'marketplace_inquiries', body: (p, i) => ({ listing_id: LISTING, buyer_name: p.name, buyer_contact: '0917 000 0000', message: `${MARK} question ${i}` }),
    mine: `message like '${MARK} question %'` },
  ai_reply_feedback: { table: 'ai_reply_feedback', body: (p, i) => ({ hive_id: HIVE, worker_name: p.name, agent: 'assistant', source: 'probe', question: `${MARK} q ${i}`, rating: 1 }),
    mine: `question like '${MARK} q %'` },
  project_progress_logs: { table: 'project_progress_logs', body: (p, i) => ({ project_id: PROJECT, hive_id: HIVE, reported_by: p.name, notes: `${MARK} log ${i}` }),
    mine: `notes like '${MARK} log %'` },
  project_items: { table: 'project_items', body: (p, i) => ({ project_id: PROJECT, hive_id: HIVE, title: `${MARK} task ${i}`, status: 'pending' }),
    mine: `title like '${MARK} task %'`, supervisors: true },
  asset_nodes: { table: 'asset_nodes', body: (p, i) => ({ hive_id: HIVE, worker_name: p.name, tag: `HSW2-${String(i).padStart(2, '0')}`, name: `${MARK} machine ${i}`, level: 'equipment', status: 'pending' }),
    mine: `tag like 'HSW2-%'` },
  inventory_items: { table: 'inventory_items', body: (p, i) => ({ hive_id: HIVE, worker_name: p.name, part_number: `HSW2-P${String(i).padStart(2, '0')}`, part_name: `${MARK} part ${i}`, qty_on_hand: 1, status: 'pending' }),
    mine: `part_number like 'HSW2-P%'` },
  rcm_fmea_modes: { table: 'rcm_fmea_modes', body: (p, i) => ({ hive_id: HIVE, asset_id: NODE, function_text: MARK, failure_mode: `${MARK} mode ${i}`, created_by: p.name }),
    mine: `failure_mode like '${MARK} mode %'` },
  platform_feedback: { table: 'platform_feedback', body: (p, i) => ({ kind: 'idea', subject: `${MARK} ${i}`, body: MARK, worker_name: p.name }),
    mine: `subject like '${MARK} %'` },
  // ── the rest of the W2 tables a page writes (2026-10-30, with the shift walk's second batch) ─────────────────────────
  // a new project: the page asks generate_project_code for the next code, then inserts with it
  projects: { table: 'projects', body: async (p, i) => ({ hive_id: HIVE, name: `${MARK} project ${i}`, project_type: 'contractor', status: 'planning', owner_name: p.name,
      project_code: await rpcValue(p, 'generate_project_code', { p_hive_id: HIVE, p_type: 'contractor', p_year: new Date().getFullYear() }) }),
    mine: `name like '${MARK} project %'`,
    // the counter the burst advanced goes too: the next real project is numbered from the codes that exist
    unplant: () => psql(`delete from code_counters where scope like 'project:${HIVE}:%'`) },
  // a change order: generate_change_order_number for the project, then the request
  project_change_orders: { table: 'project_change_orders', body: async (p, i) => ({ project_id: PROJ_NW, hive_id: HIVE, title: `${MARK} change ${i}`, scope_change: MARK,
      status: 'pending', requested_by: p.name, co_number: await rpcValue(p, 'generate_change_order_number', { p_project_id: PROJ_NW }) }),
    mine: `title like '${MARK} change %'`, unplant: () => psql(`delete from code_counters where scope = 'change_order:${PROJ_NW}'`) },
  // the supervisors put the whole shift on a project at once (a role is a supervisor's write); each row is a member's
  project_roles: { table: 'project_roles', by: (i) => { const s = signedIn.filter((x) => x.role === 'supervisor'); return s[i % s.length]; },
    held: `select worker_name from project_roles where project_id = '${PROJ_NW}' and role = 'reviewer' and deleted_at is null`,
    body: (p, i) => ({ project_id: PROJ_NW, hive_id: HIVE, worker_name: p.name, role: 'reviewer', notes: `${MARK} role ${i}` }),
    mine: `notes like '${MARK} role %'`, stamp: 'assigned_at',
    reset: () => `delete from hive_audit_log where target_id::text in (select id::text from project_roles where notes like '${MARK} role %');
      delete from project_roles where notes like '${MARK} role %';` },
  // the shift checks off the same PM task (one per task, person and day); a completion pays XP and queues an embedding,
  // both put back. Its time is the device's, so the marker alone counts the rows
  pm_completions: { table: 'pm_completions', stamp: false, order_col: 'completed_at',
    body: (p, i) => ({ asset_id: PMA, scope_item_id: PMA_TASK, hive_id: HIVE, worker_name: p.name, auth_uid: p.uid, status: 'done', notes: `${MARK} pm ${i}`,
      completed_at: new Date().toISOString() }),
    held: `select worker_name from pm_completions where scope_item_id = '${PMA_TASK}' and (completed_at at time zone 'UTC')::date = (now() at time zone 'UTC')::date`,
    mine: `notes like '${MARK} pm %'`,
    plant: () => { PM_XP = psql(`select coalesce(json_agg(row_to_json(w)), '[]') from worker_achievements w where achievement_id = 'uptime_guardian'`); },
    reset: () => `delete from embedding_outbox where source_table = 'pm_completions' and row_id::text in (select id::text from pm_completions where notes like '${MARK} pm %');
      delete from achievement_xp_log where source_id in (select id::text from pm_completions where notes like '${MARK} pm %');
      delete from pm_completions where notes like '${MARK} pm %';`,
    unplant: () => { const j = PM_XP.replace(/'/g, "''"); psql(`set session_replication_role = replica;
      update worker_achievements w set xp_total = s.xp_total, current_level = s.current_level, last_action_at = s.last_action_at
        from json_populate_recordset(null::worker_achievements, '${j}') s where w.worker_name = s.worker_name and w.achievement_id = s.achievement_id;
      delete from worker_achievements w where w.achievement_id = 'uptime_guardian'
        and not exists (select 1 from json_populate_recordset(null::worker_achievements, '${j}') s where s.worker_name = w.worker_name);`); } },
  // a PM program is a supervisor's write (pm_assets_insert_guard): the hive's supervisors add theirs at once
  pm_assets: { table: 'pm_assets', body: (p, i) => ({ hive_id: HIVE, worker_name: p.name, asset_name: `${MARK} asset ${i}`, category: 'Pump' }),
    mine: `asset_name like '${MARK} asset %'`, supervisors: true },
  // the shift marks the hive's alerts seen at once: 29 marks on 14 alerts (the hub's count for this hive). One record per
  // hive and alert, written insert-unless-present (alert-hub's own upsert, ignoreDuplicates): 14 rows, nobody refused
  alert_dismissals: { table: 'alert_dismissals', path: 'alert_dismissals?on_conflict=hive_id,alert_key', prefer: ',resolution=ignore-duplicates',
    body: (p, i) => ({ hive_id: HIVE, alert_key: `pm:hsw2-burst-${i % 14}`, action: 'acknowledged', actor: p.name }),
    mine: `hive_id = '${HIVE}' and alert_key like 'pm:hsw2-burst-%'`, expect: () => 14 },
  // the day a hive starts: its supervisor shares the invite code and the shift joins at once (hive.html's join_hive_by_code)
  hive_members: { table: 'hive_members', path: 'rpc/join_hive_by_code', body: (p) => ({ p_code: 'HSW2JN', p_worker_name: p.name }),
    held: `select worker_name from hive_members where hive_id = '${JOIN_HIVE}'`,
    mine: `hive_id = '${JOIN_HIVE}' and role = 'worker' and status = 'active'`, stamp: false, order_col: 'joined_at',
    plant: () => psql(`set session_replication_role = replica;
      insert into hives (id, name, invite_code, created_by) values ('${JOIN_HIVE}', 'HS-W2 burst hive', 'HSW2JN', 'Ernesto Villareal');
      insert into hive_members (hive_id, worker_name, role, status, auth_uid)
        select '${JOIN_HIVE}', worker_name, 'supervisor', 'active', auth_uid from hive_members where hive_id = '${HIVE}' and worker_name = 'Ernesto Villareal';`),
    reset: () => `delete from hive_audit_log where hive_id = '${JOIN_HIVE}'; delete from hive_members where hive_id = '${JOIN_HIVE}' and role = 'worker';`,
    unplant: () => psql(`set session_replication_role = replica; delete from hive_audit_log where hive_id = '${JOIN_HIVE}';
      delete from hive_members where hive_id = '${JOIN_HIVE}'; delete from hive_quotas where hive_id = '${JOIN_HIVE}'; delete from hives where id = '${JOIN_HIVE}';`) },
  // each member registers as a freelance service provider (marketplace-seller's svcRegister); one already is
  service_providers: { table: 'service_providers', held: `select worker_name from service_providers where provider_type = 'freelancer' and worker_name is not null`,
    body: (p, i) => ({ provider_type: 'freelancer', auth_uid: p.uid, worker_name: p.name, display_name: `${MARK} provider ${i}`, categories: ['Mechanical'],
      service_areas: ['Batangas'], availability: 'offline' }),
    mine: `display_name like '${MARK} provider %'`,
    reset: () => `delete from hive_audit_log where target_id::text in (select id::text from service_providers where display_name like '${MARK} provider %');
      delete from service_providers where display_name like '${MARK} provider %';` },
  // each member saves a resume (their own; the page opens one only when its document has basics)
  resume_documents: { table: 'resume_documents', body: (p, i) => ({ auth_uid: p.uid, worker_name: p.name, hive_id: HIVE, title: `${MARK} resume ${i}`, template: 'ats-plain',
      doc: { basics: { name: p.name }, meta: { title: `${MARK} resume ${i}` } } }),
    mine: `title like '${MARK} resume %'` },
  // each member saves a Messenger handle - the seller page's own upsert on worker_name: two already sell, 27 become sellers
  marketplace_sellers: { table: 'marketplace_sellers', path: 'marketplace_sellers?on_conflict=worker_name', prefer: ',resolution=merge-duplicates',
    body: (p, i) => ({ worker_name: p.name, auth_uid: p.uid, messenger_username: `${MARK}.handle.${i}`.replace(/ /g, '.'), updated_at: new Date().toISOString() }),
    mine: `messenger_username like '${MARK.replace(/ /g, '.')}.handle.%'`, stamp: false, order_col: 'updated_at',
    plant: () => { SELLERS = psql(`select string_agg(quote_literal(worker_name), ',') from marketplace_sellers`); },
    reset: () => `delete from marketplace_sellers where messenger_username like '${MARK.replace(/ /g, '.')}.handle.%' and worker_name not in (${SELLERS});
      update marketplace_sellers set messenger_username = null where messenger_username like '${MARK.replace(/ /g, '.')}.handle.%';` },
};
let PM_XP = '[]', SELLERS = "''";

const MIGRATION = 'supabase/migrations/20261030000006_a_shift_of_thirty_is_not_one_seller.sql';
if (TEETH) {
  const cur = psql(`select pg_get_functiondef('public.check_listing_rate'::regproc)`);
  const old = cur.replace(/\n\s*-- per MEMBER within the hive[^\n]*/, '')
    .replace(/\n\s*AND \(\(NEW\.auth_uid IS NOT NULL AND auth_uid = NEW\.auth_uid\)\n\s*OR \(NEW\.auth_uid IS NULL AND seller_name = NEW\.seller_name\)\)/, '');
  if (old === cur) throw new Error('teeth: could not reinstate the hive-wide count');
  psql(old + ';');
  const swapped = psql(`select prosrc not like '%per MEMBER%' from pg_proc where proname = 'check_listing_rate'`);
  console.log(`teeth: hive-wide count in place: ${swapped}`);
  if (swapped !== 't') throw new Error('teeth: the hive-wide count did not take');
  ONLY.clear(); ONLY.add('marketplace_listings');
}
const report = { ran: new Date().toISOString(), hive: HIVE, teeth: TEETH, members: signedIn.length, units: {} };
let failed = 0;
// ── inventory_transactions: thirty members each take ONE of the same part. The page's write is the inventory_deduct RPC
// (balance and ledger row in one transaction); concurrent takes must neither lose a decrement (a lost update leaves the
// shelf over-counted) nor refuse one while stock remains.
if (!ONLY.size || ONLY.has('inventory_transactions')) {
  const ITEM = psql(`select id from inventory_items where hive_id = '${HIVE}' and status = 'approved' order by qty_on_hand desc, id limit 1`);
  const before = psql(`select row_to_json(t) from inventory_items t where id = '${ITEM}'`);
  const tStart = psql('select now()');
  // a delivery stocks the shelf for the shift: a supervisor's count adjustment (a ledger row), never a raw write to the
  // ledger-derived balance, which its trigger would put back
  const sup = signedIn.find((p) => p.role === 'supervisor');
  await rest(sup, 'rpc/inventory_adjust', { p_item_id: ITEM, p_expected_qty: Number(psql(`select qty_on_hand from inventory_items where id = '${ITEM}'`)),
    p_new_qty: 100, p_note: 'HS W2 burst: stocked for the shift' });
  const q0 = Number(psql(`select qty_on_hand from inventory_items where id = '${ITEM}'`));
  const pass = async (label, fire) => {
    const t = psql('select now()');
    const q = Number(psql(`select qty_on_hand from inventory_items where id = '${ITEM}'`));
    const res = await fire();
    const q1 = Number(psql(`select qty_on_hand from inventory_items where id = '${ITEM}'`));
    const moved = Number(psql(`select coalesce(-sum(qty_change), 0) from inventory_transactions where item_id = '${ITEM}' and created_at >= '${t}'`));
    const refused = res.filter((r) => r.status >= 300);
    return { label, before: q, after: q1, ledger_moved: moved, refused: refused.length, msg: refused[0] ? refused[0].msg.slice(0, 120) : '' };
  };
  const take = (p, i) => rest(p, 'rpc/inventory_deduct', { p_item_id: ITEM, p_qty: 1, p_type: 'use', p_job_ref: `HSW2-${i}` });
  const a = await pass('at once', () => Promise.all(signedIn.map((p, i) => take(p, i))));
  const b = await pass('one after another', async () => { const out = []; for (let i = 0; i < signedIn.length; i++) { out.push(await take(signedIn[i], i)); await sleep(150); } return out; });
  const n = signedIn.length;
  const okOne = (x) => x.refused === 0 && x.before - x.after === n && x.ledger_moved === n;
  const ok = q0 >= 2 * n ? (okOne(a) && okOne(b)) : false;
  if (!ok) failed++;
  report.units.inventory_transactions = { ok, item: ITEM, members: n, passes: [a, b], stock_was: q0 };
  console.log(`${ok ? 'PASS' : 'FAIL'} inventory_transactions: ${[a, b].map((x) => `${x.label} ${x.before}->${x.after}, ledger ${x.ledger_moved}${x.refused ? ', refused ' + x.refused + ' (' + x.msg + ')' : ''}`).join('; ')}${q0 < 2 * n ? ` - the part holds ${q0}, under the ${2 * n} two passes need` : ''}`);
  psql(`set session_replication_role = replica; delete from inventory_transactions where item_id = '${ITEM}' and created_at >= '${tStart}';
    update inventory_items t set qty_on_hand = (('${before.replace(/'/g, "''")}')::json->>'qty_on_hand')::numeric, updated_at = (('${before.replace(/'/g, "''")}')::json->>'updated_at')::timestamptz where id = '${ITEM}';`);
}
for (const [unit, u] of Object.entries(UNITS)) {
  if (ONLY.size && !ONLY.has(unit)) continue;
  if (u.plant) u.plant();   // first: what it plants can be what makes a member already hold the row
  // u.held: members who already hold this one-per-person row are not part of the shift's writes
  const held = u.held ? new Set(psql(u.held).split(/\r?\n/).filter(Boolean)) : new Set();
  const who = (u.supervisors ? signedIn.filter((p) => p.role === 'supervisor') : signedIn).filter((p) => !held.has(p.name));
  // u.by: who presses the button when the row is about someone else; u.path/u.prefer: the page's upsert; u.stamp: the
  // column a row's time lives in (false: the device's own clock wrote it - the marker alone counts the rows)
  const send = async (p, i) => rest(u.by ? u.by(i) : p, u.path || u.table, await u.body(p, i), 'POST', u.prefer || '');
  const since = (t) => (u.stamp === false ? '' : ` and ${u.stamp || 'created_at'} >= '${t}'`);
  // the rows go, and first the trail entries their INSERT triggers wrote about them (audit_shared_change's add_* rows):
  // a cleanup that left those behind filled the hive's audit log with entries for rows that no longer exist
  const clear = (t) => psql(`set session_replication_role = replica; ${u.reset ? u.reset() : `delete from hive_audit_log where hive_id = '${HIVE}'
    and target_id::text in (select id::text from ${u.table} where ${u.mine}${since(t)}); delete from ${u.table} where ${u.mine}${since(t)};`}`);
  const t0 = psql('select now()');
  // the shift change: everyone at once ...
  const results = await Promise.all(who.map((p, i) => send(p, i)));
  const burstLanded = Number(psql(`select count(*) from ${u.table} where ${u.mine}${since(t0)}`)) || 0;
  clear(t0);
  // ... and then as the minutes of a shift change: one after another
  const t1 = psql('select now()');
  const staggered = [];
  for (let i = 0; i < who.length; i++) { staggered.push(await send(who[i], i)); await sleep(STAGGER_MS / 10); }
  results.push(...staggered.map((r) => ({ ...r, staggered: true })));
  const landed = Number(psql(`select count(*) from ${u.table} where ${u.mine}${since(t1)}`)) || 0;
  const refusals = results.filter((r) => r.status >= 300);
  const byMsg = {};
  for (const r of refusals) byMsg[`${r.status} ${r.msg.slice(0, 120)}`] = (byMsg[`${r.status} ${r.msg.slice(0, 120)}`] || 0) + 1;
  // the list's own order: newest first by created_at, then id, with nothing missing
  // the list's own order: read newest-first, the created_at sequence never runs backwards and nothing is missing
  const oc = u.order_col || u.stamp || 'created_at';
  const seq = psql(`select string_agg(to_char(${oc}, 'HH24:MI:SS.US'), ',' order by ${oc} desc, id) from ${u.table}
    where ${u.mine}${since(t1)}`).split(',').filter(Boolean);
  const inOrder = seq.every((v, i) => i === 0 || v <= seq[i - 1]);
  // u.expect: a one-per-key record keeps one row a key, however many write it (alerts: 29 marks on 14 alerts -> 14)
  const want = u.expect ? u.expect(who) : who.length;
  const ok = burstLanded === want && landed === want && refusals.length === 0 && inOrder;
  if (!ok) failed++;
  report.units[unit] = { ok, sent: who.length, expected: want, burst_landed: burstLanded, staggered_landed: landed, refused: refusals.length, refusals: byMsg, in_order: inOrder };
  console.log(`${ok ? 'PASS' : 'FAIL'} ${unit}: at once ${burstLanded}/${who.length}, one after another ${landed}/${who.length}${want !== who.length ? ` (one record a key: ${want} expected)` : ''}${refusals.length ? '; refused ' + JSON.stringify(byMsg) : ''}${inOrder ? '' : '; OUT OF ORDER'}`);
  clear(t1);
  if (u.unplant) u.unplant();
  await sleep(500);
}
// what the rows PAID goes with them: clear() deletes with triggers off, so the XP their INSERT triggers paid stood for
// rows that no longer existed (Rowena read 630 community XP for one real post) until this took it back
psql((await import('fs')).readFileSync('tools/hs_paid_residue.sql', 'utf8'));
if (TEETH) {
  spawnSync('docker', ['exec', '-i', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1'],
    { input: (await import('fs')).readFileSync(MIGRATION, 'utf8'), encoding: 'utf8' });
  const back = psql(`select prosrc like '%per MEMBER within the hive%' from pg_proc where proname = 'check_listing_rate'`);
  console.log(`teeth: the hive-wide count reinstated for the run, the per-member limit put back (${back === 't' ? 'confirmed' : 'NOT CONFIRMED'})`);
  writeFileSync('hive_scale_burst_teeth.json', JSON.stringify(report, null, 1));
  console.log(`${failed ? 'PASS' : 'FAIL'} hive-scale-burst teeth: the hive-wide listing limit ${failed ? 'refused members once the hive had listed twenty' : 'refused nobody - the teeth did not bite'}`);
  process.exit(failed ? 0 : 1);
}
// a run of named units merges into the day's receipt (the others keep their own reading)
if (ONLY.size) {
  try { const prior = JSON.parse((await import('fs')).readFileSync(OUT, 'utf8'));
    if (Date.now() - Date.parse(prior.ran) < 3 * 3600 * 1000 && !prior.teeth) report.units = { ...prior.units, ...report.units }; } catch (_) { /* first run */ }
  failed = Object.values(report.units).filter((x) => !x.ok).length;
}
writeFileSync(OUT, JSON.stringify(report, null, 1));
const n = Object.keys(report.units).length;
console.log(`${failed ? 'FAIL' : 'PASS'} hive-scale-burst: ${n - failed}/${n} units took a shift of ${signedIn.length} members writing at once`);
process.exitCode = failed ? 1 : 0;
