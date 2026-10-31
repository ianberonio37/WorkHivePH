// prove_hive_scale_lists — Wave HS (the hive at thirty), lenses L1 and L2, walked against a thirty-member hive.
//
//   L1  thirty members' items, read as a list: with the full hive's items on it, each item is legible at 390 and 1280 -
//       who made it, when, what - a count only when there is one, no line of unnamed controls, nothing fixed over it.
//   L2  each role sees the actions it may take: the actions an item offers a worker and a supervisor are exactly the
//       writes the database lets that person make on that item - nothing offered that the server refuses, no
//       supervisor action leaking to a worker.
//
// ★THE SUBJECTS ARE THE FULL HIVE (test-data-seeder/seeders/full_hive.py): Batangas Refinery Maintenance, thirty members,
// a year of their work. A list read in a five-person demo hive cannot show what Ian saw - his workmates' posts cluttered
// on a phone - so every reading here is taken against that hive, signed in as one of its workers and one of its
// supervisors, and the population is printed so an empty list can never pass as a clean one.
//
// ★THE ITEM IS READ WHERE THE PERSON READS IT. Each item is scrolled into view before it is judged, because the feed draws
// lazily and a fixed bar covers only what is under it at that scroll - the smoke's STUCK reading, per item.
//
// L2's other half is the database: each action an item's menu offers is replayed as that person, in a rolled-back
// transaction, and must take effect; each moderation action a worker is NOT offered must not take effect either.
//
//   node tools/prove_hive_scale_lists.mjs                    every page in SPECS
//   node tools/prove_hive_scale_lists.mjs community.html     one page
//   node tools/prove_hive_scale_lists.mjs --teeth            perturbs an expectation; must FAIL
import { chromium } from 'playwright';
import { writeFileSync, renameSync, readFileSync } from 'node:fs';
import { SEEDER, signIn, psql } from './prover_harness.mjs';

const HIVE = '30303030-3030-4030-8030-303030303030';           // Batangas Refinery Maintenance (full_hive.py)
const PEOPLE = {
  worker: { name: 'Joel Cruz', email: 'joelcruz@auth.workhiveph.com', role: 'worker', password: 'test1234', hive: HIVE },
  supervisor: { name: 'Ernesto Villareal', email: 'ernestovillareal@auth.workhiveph.com', role: 'supervisor', password: 'test1234', hive: HIVE },
};
const VIEWPORTS = [{ name: 'phone-390', width: 390, height: 844 }, { name: 'desktop-1280', width: 1280, height: 900 }];
const TEETH = process.argv.includes('--teeth');
// --l7: a member of two hives. The walk's worker and supervisor are made active members of a second hive holding one
// marked item in each main relation; RLS lets them read both hives, so only the page's own filter keeps that hive's
// items off the active hive's lists. Opt-in: the second membership is planted for this run and removed after it.
const L7 = process.argv.includes('--l7');
const L7_HIVE = '17171717-1717-4717-8717-171717171717', L7_MARK = 'HS-L7 other hive';
const ONLY = process.argv.slice(2).filter((a) => a.endsWith('.html'));
const REPORT = 'hive_scale_lists_report.json';
const MAX_MENUS = 6;          // menus opened per role per page view (own + others), enough to cover both ownerships

// the other lenses' rows of each list (L6 ...), from the registry: the census numbered every lens of a list by its page and
// unit, so a list's L1 row names its L6 row
const LENS = (() => {
  const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
  const byId = {}, byUnit = {};
  for (const t of reg.trajectories) { const h = t.hs || {}; if (h.kind !== 'hive-scale') continue; byId[t.id] = h; byUnit[`${h.page}|${h.unit}|${h.key}`] = t.id; }
  return (l1Row, key) => { const h = byId[l1Row]; return h ? byUnit[`${h.page}|${h.unit}|${key}`] || null : null; };
})();
// the hive's members who have left (deactivated, removed): their work stays on its lists (L5)
const FORMER = new Set(psql(`select string_agg(worker_name, '|') from hive_members where hive_id = '${HIVE}' and status <> 'active'`).split('|').filter(Boolean));
// the full hive's near-twins: a name cut short could be either
const TWINS = [['Mark Anthony Santos', 'Mark Anthony Santos Jr.'], ['Ana Reyes', 'Anna Reyes'], ['Joel Cruz', 'Joey Cruz']];
const MEMBERS = psql(`select string_agg(worker_name, '|') from hive_members where hive_id = '${HIVE}'`).split('|').filter(Boolean)
  // longest first: "Mark Anthony Santos Jr." must not be read as "Mark Anthony Santos" (thirty names hold near-twins)
  .sort((x, y) => y.length - x.length);

// as(person, sql): run sql as that member in a rolled-back transaction; answers the LAST t/f line it printed
const as = (person, sql) => {
  const out = psql(`begin; select set_config('request.jwt.claims', json_build_object('sub', (select auth_uid from hive_members `
    + `where worker_name = '${person.name}' and hive_id = '${HIVE}')::text, 'role', 'authenticated')::text, true); `
    + `set local role authenticated; ${sql}; rollback;`);
  const tf = out.split(/[\r\n]+/).map((l) => l.trim()).filter((l) => l === 't' || l === 'f');
  return tf.length ? tf[tf.length - 1] : '';
};

// took(stmt): did this write change a row, as the person? A trigger's raised refusal reads as f (not as no answer).
const took = (stmt) => `create temp table _took (v boolean) on commit drop; `
  + `do $do$ declare n int; begin ${stmt}; get diagnostics n = row_count; insert into _took values (n > 0); `
  + `exception when others then insert into _took values (false); end $do$; select v from _took`;

// ── what each community post action WRITES, replayed as the person: 't' when it took effect ─────────────────────────
const POST_WRITES = {
  // the words must change - a row coming back is not an edit (a supervisor's rewrite returns the row with the old words)
  edit: (id) => `with o as (select content from community_posts where id = '${id}'), u as (update community_posts set content = content || ' [e]' where id = '${id}' returning content) select exists (select 1 from u) and (select content from u) is distinct from (select content from o)`,
  // wh_trash answers a receipt or raises - a refusal prints no t at all
  delete: (id) => `select public.wh_trash('community_posts', '${id}') is not null`,
  pin: (id) => `with o as (select pinned from community_posts where id = '${id}'), u as (update community_posts set pinned = not pinned where id = '${id}' returning pinned) select (select pinned from u) is distinct from (select pinned from o) and exists (select 1 from u)`,
  share: (id) => `with o as (select public from community_posts where id = '${id}'), u as (update community_posts set public = not public where id = '${id}' returning public) select (select public from u) is distinct from (select public from o) and exists (select 1 from u)`,
  flag: (id) => `with o as (select flagged from community_posts where id = '${id}'), u as (update community_posts set flagged = not flagged where id = '${id}' returning flagged) select (select flagged from u) is distinct from (select flagged from o) and exists (select 1 from u)`,
  report: (id) => `select public.report_community_post('${id}')`,
};
const POST_LABEL = (label) => (/^Edit/.test(label) ? 'edit' : /^Delete/.test(label) ? 'delete' : /pin post$/i.test(label) ? 'pin'
  : /^Make post/.test(label) ? 'share' : /flag post$/i.test(label) ? 'flag' : /^Report/.test(label) ? 'report' : null);

// ── L2, declared per list: where an item's actions are, what each WRITES, and which permitted ones must be offered ──
//   label(text) -> action key | null          id(item) -> the row the action writes
//   writes[key](id) -> sql answering t/f as the person (rolled back)
//   rules[key](person, item) -> boolean       an action replaying it would really change something (a password) is
//                                             judged against the server's own stated rule, its refusals replayed live
//   candidates: actions the database may permit that the item must then OFFER
//   skip(act, mine): an action that does not apply (reporting your own post, removing yourself)
const POSTS_L2 = { label: POST_LABEL, id: (it) => it.dataId, writes: POST_WRITES, candidates: ['pin', 'share', 'delete', 'edit'],
  skip: (act, mine) => act === 'report' && mine, ownership: true };
const sqlq = (v) => String(v).replace(/'/g, "''");
const memberCol = (name, col) => psql(`select ${col} from hive_members where hive_id = '${HIVE}' and worker_name = '${sqlq(name)}'`);
const MEMBERS_L2 = {
  label: (t) => (/^Remove$/.test(t) ? 'kick' : /^Reset PW$/.test(t) ? 'reset' : null),
  id: (it) => (it.author ? memberCol(it.author, 'id') : null),
  writes: { kick: (id) => `with u as (update hive_members set status = 'kicked' where id = '${id}' returning 1) select count(*) > 0 from u` },
  // supervisor-reset-password: "an ACTIVE supervisor of the SAME hive, and the target an active WORKER" (its own header)
  rules: { reset: (person, it) => person.role === 'supervisor' && !it.mine && memberCol(it.author, 'role') === 'worker'
    && memberCol(it.author, 'status') === 'active' },   // "the target an ACTIVE worker" - a member who has left is not offered it (L5)
  candidates: ['kick', 'reset'], skip: (act, mine) => mine, ownership: false };
// a logbook entry: only its author edits or deletes it (logbook_update / wh_trash under it) - the detail must agree
const ENTRIES_L2 = {
  // HS L5 (mig 20261030000012): a supervisor takes over a departed member's OPEN job - close it or assign it. Replayed as
  // a NON-author's write, so an author's own close (through Edit) is not mistaken for the take-over the page offers others
  label: (t) => (/^Edit Entry$/.test(t) ? 'edit' : /^Delete$/.test(t) ? 'delete'
    : /^Close this job$/.test(t) ? 'takeover_close' : /^Assign to a member$/.test(t) ? 'assign' : null),
  ignore: (t) => !t || /^(Close|×|✕|Copy|Share|Print|Ask|Open)/i.test(t),
  id: (it) => it.dataId,
  writes: {
    takeover_close: (id) => `with u as (update logbook set status = 'Closed', closed_at = now() where id = '${id}' and status = 'Open' and auth_uid is distinct from auth.uid() returning 1) select exists (select 1 from u)`,
    assign: (id) => `with u as (update logbook set wo_state = 'assigned', wo_assigned_to = (select worker_name from hive_members where hive_id = '${HIVE}' and status = 'active' and role = 'worker' order by worker_name limit 1) where id = '${id}' and status = 'Open' and auth_uid is distinct from auth.uid() returning 1) select exists (select 1 from u)`,
    edit: (id) => `with o as (select problem from logbook where id = '${id}'), u as (update logbook set problem = coalesce(problem, '') || ' [e]' where id = '${id}' returning problem) select exists (select 1 from u) and (select problem from u) is distinct from (select problem from o)`,
    delete: (id) => `select public.wh_trash('logbook', '${id}') is not null`,
  },
  candidates: ['edit', 'delete', 'takeover_close', 'assign'], ownership: true };
// a part on the hive's shelf: Use and Restock are any active member's (the RPCs' membership gate); Edit and Remove
// are its owner's or a supervisor's (inventory_items_write), and the approval guard keeps a worker from removing a
// signed-off part. Use is replayed with a quantity of 0 - the RPC's membership and status gates run, no stock moves.
const INV_L2 = {
  label: (t) => (/^Use Stock$/.test(t) ? 'use' : /^Restock$/.test(t) ? 'restock' : /^Edit$/.test(t) ? 'edit'
    : /^Remove from inventory$/.test(t) ? 'delete' : null),
  ignore: (t) => !t || /^(Close|×|✕|View photo|Photo)/i.test(t),
  id: (it) => it.dataId,
  writes: {
    use: (id) => `select public.inventory_deduct('${id}', 0) is not null`,
    restock: (id) => `select public.inventory_restock('${id}', 1) is not null`,
    edit: (id) => `with o as (select part_name from inventory_items where id = '${id}'), u as (update inventory_items set part_name = part_name || ' [e]' where id = '${id}' returning part_name) select exists (select 1 from u) and (select part_name from u) is distinct from (select part_name from o)`,
    delete: (id) => `select public.wh_trash('inventory_items', '${id}') is not null`,
  },
  candidates: ['edit', 'delete', 'use', 'restock'], ownership: true };
// the part moved by the most hands - its history is the longest list of members' movements. Parts tie (8 hands, 8
// movements) and an untied ORDER BY let Postgres pick a different one from run to run: one held Rodel's movement and
// one did not, so L5 passed on one day's pick and found "nothing to judge" on the next. The tie is broken on purpose
// - a part whose history holds a departed member's movement first (the window L5 must read), then hands, rows, id.
const TOP_ITEM = psql(`select item_id from inventory_transactions where hive_id = '${HIVE}' group by item_id `
  + `order by bool_or(worker_name in (select worker_name from hive_members where hive_id = '${HIVE}' and status <> 'active')) desc, `
  + `count(distinct worker_name) desc, count(*) desc, item_id limit 1`);
// asset-hub: a machine waiting for approval is a supervisor's to approve or reject (tg_guard_approval)
const PENDING_L2 = {
  label: (t) => (/^Approve$/.test(t) ? 'approve' : /^Reject$/.test(t) ? 'reject' : null),
  ignore: (t) => !t,
  id: (it) => it.dataId,
  writes: {
    approve: (id) => took(`update asset_nodes set status = 'approved', approved_at = now() where id = '${id}'`),
    reject: (id) => took(`update asset_nodes set status = 'rejected', approved_at = now(), rejection_reason = 'probe' where id = '${id}'`),
  },
  candidates: ['approve', 'reject'], ownership: false };
// a failure mode: a supervisor approves or deletes a pending one; a member changes only their own while it waits
const FMEA_L2 = {
  label: (t) => (/^Approve$/.test(t) ? 'approve' : /^Delete$/.test(t) ? 'delete' : null),
  ignore: (t) => !t,
  id: (it) => it.dataId,
  writes: {
    approve: (id) => took(`update rcm_fmea_modes set approved_at = now() where id = '${id}' and approved_at is null`),
    delete: (id) => took(`delete from rcm_fmea_modes where id = '${id}' and approved_at is null`),
  },
  candidates: ['approve', 'delete'], ownership: false };
const nodeOf = (tag) => psql(`select id from asset_nodes where hive_id = '${HIVE}' and tag = '${tag}'`);
const NODE_BUSY = psql(`select n.id from asset_nodes n join logbook l on l.asset_node_id = n.id where n.hive_id = '${HIVE}' group by n.id order by count(*) desc limit 1`);
const NODE_PENDING_FMEA = psql(`select asset_id from rcm_fmea_modes where hive_id = '${HIVE}' and approved_at is null group by asset_id order by count(*) desc limit 1`);
const openNode = async (p, id) => {
  await p.evaluate(async (nid) => {
    if (typeof openDetail === 'function') await openDetail(nid);
  }, id);
  await p.waitForTimeout(3500); return id;
};
const closeNode = async (p) => { await p.evaluate(() => { if (typeof closeDetail === 'function') closeDetail(); }); await p.waitForTimeout(400); };
// project-manager: a scope item is any member's to move and edit (project_items_hive_rw); a role is a supervisor's
// to remove (project_roles_supervisor_all); a pending change order is a supervisor's to decide and its raiser's or a
// supervisor's to cancel - the card offers exactly that, and the database must agree
const ITEMS_L2 = {
  label: (t) => (/^(pending|in progress|done|blocked)$/i.test(t) ? 'cycle' : /^Edit$/.test(t) ? 'edit' : null),
  ignore: (t) => !t, id: (it) => it.dataId,
  writes: {
    // the status chip writes the step's progress with its status (done 100, pending 0), so the replay does too
    cycle: (id) => took(`update project_items set status = case when status = 'done' then 'pending' else 'done' end, `
      + `pct_complete = case when status = 'done' then 0 else 100 end where id = '${id}'`),
    edit: (id) => took(`update project_items set title = title || ' ' where id = '${id}'`),
  },
  candidates: ['cycle', 'edit'], ownership: false };
const ROLES_L2 = {
  label: (t) => (/^×$/.test(t) || /^Remove /.test(t) ? 'remove' : null),
  ignore: (t) => !t, id: (it) => it.dataId,
  writes: { remove: (id) => `select public.wh_trash('project_roles', '${id}') is not null` },
  candidates: ['remove'], ownership: false };
const CO_L2 = {
  label: (t) => (/^Approve$/.test(t) ? 'approve' : /^Reject$/.test(t) ? 'reject' : /^Cancel request$/.test(t) ? 'cancel' : null),
  ignore: (t) => !t, id: (it) => it.dataId,
  // a decision belongs to a change order still waiting for one
  applies: (it) => /Pending review/.test(it.text + ' ' + (it.fullText || '')),
  writes: {
    approve: (id) => took(`update project_change_orders set status = 'approved', approved_at = now() where id = '${id}' and status = 'pending'`),
    reject: (id) => took(`update project_change_orders set status = 'rejected', approved_at = now(), rejection_reason = 'probe' where id = '${id}' and status = 'pending'`),
    cancel: (id) => took(`update project_change_orders set status = 'cancelled', approved_at = now() where id = '${id}' and status = 'pending'`),
  },
  candidates: ['approve', 'reject', 'cancel'], ownership: false };
const PROJ_BUSY = psql(`select p.id from projects p join project_change_orders c on c.project_id = p.id where p.hive_id = '${HIVE}' and c.status = 'pending' group by p.id order by count(*) desc, p.id limit 1`);
const openProject = async (p, pane) => {
  await p.evaluate(async ({ id, pane }) => {
    if (typeof openDetail === 'function') await openDetail(id);
    await new Promise((r) => setTimeout(r, 1500));
    // a pane exists only inside an opened project - when the project did not open (another hive is active), a person
    // has no tab to press, so the walk presses none
    const opened = document.getElementById('detail-view')?.classList.contains('open');
    if (opened && pane && typeof setActivePane === 'function') setActivePane(pane);
  }, { id: PROJ_BUSY, pane });
  await p.waitForTimeout(1200); return PROJ_BUSY;
};
const PM_BUSY = psql(`select asset_id from pm_completions where hive_id = '${HIVE}' group by asset_id order by count(distinct worker_name) desc, asset_id limit 1`);
// integrations: a CMMS conflict's WorkHive side is one member's entry - only its author sets it ("Use SAP" on one's own),
// and only a supervisor writes the sync pushed to SAP ("Keep WorkHive"; migration 20261030000005)
const CONFLICT_L2 = {
  label: (t) => (/^Use SAP/.test(t) ? 'usesap' : /^Keep WorkHive/.test(t) ? 'keep' : null),
  ignore: (t) => !t, id: (it) => it.dataId,
  writes: {
    usesap: (id) => took(`update logbook set status = status where id = '${id}'`),
    keep: (id) => took(`update external_sync set status = status where hive_id = '${HIVE}' and entity_type = 'work_order' and sync_payload->>'machine' = (select machine from logbook where id = '${id}')`),
  },
  candidates: ['usesap', 'keep'], ownership: false };
// the machine whose linked parts were used the most - its detail holds the longest list of members' part uses
const TOP_TAG = psql(`select n.tag from asset_nodes n join inventory_items i on n.id = any(i.linked_asset_node_ids) `
  + `join inventory_transactions t on t.item_id = i.id and t.type = 'use' where n.hive_id = '${HIVE}' group by n.tag order by count(*) desc limit 1`);
const openAssetDetail = async (p, tab) => {
  await p.evaluate(async ({ tag, tab }) => {
    const a = (typeof loadAssets === 'function' ? loadAssets() : []).find((x) => x.asset_id === tag || x.tag === tag);
    if (!a) return;
    openAssetDetail(a.id);
    for (let i = 0; i < 40 && !document.getElementById('asset-detail-loading')?.classList.contains('hidden'); i++) await new Promise((r) => setTimeout(r, 250));
    if (typeof switchDetailTab === 'function') switchDetailTab(tab);
  }, { tag: TOP_TAG, tab });
  await p.waitForTimeout(800); return null;
};
const closeAssetDetail = async (p) => { await p.evaluate(() => { const m = document.getElementById('asset-detail-modal'); if (m) m.style.display = 'none'; }); };

// a section a person opens before its list shows: a Show/Hide toggle, or the <details> holding the list
const openToggle = async (p, sel) => {
  await p.evaluate((s) => { const b = document.querySelector(s); if (b && b.getAttribute('aria-expanded') !== 'true') b.click(); }, sel);
  await p.waitForTimeout(1200); return null;
};
const openDetails = async (p, inner) => {
  await p.evaluate((s) => { const d = document.querySelector(s)?.closest('details'); if (d && !d.open) (d.querySelector('summary') || d).click(); }, inner);
  await p.waitForTimeout(1200); return null;
};

// ownReadsOnly(rel, ownSql, col): a relation the page reads only for the VIEWER - measured, not assumed. Every request the
// page sends on load is captured; each read of `rel` must filter on `col` (id / auth_uid / worker_name) and ask for the
// viewer's own values only, so nothing of the other members' rows can be asked for. With no read on load, the page draws
// nothing of the relation there - also said.
const ownReadsOnly = (rel, ownSql, col = 'id') => Object.assign(async (p, c) => {
  const seen = [];
  const onReq = (r) => { const u = r.url(); if (u.includes(`/rest/v1/${rel}?`) && r.method() === 'GET') seen.push(decodeURIComponent(u)); };
  p.on('request', onReq);
  await p.reload({ waitUntil: 'load', timeout: 45000 });
  await p.waitForTimeout(7000);
  p.off('request', onReq);
  const own = psql(ownSql(c.person)).split(/\s+/).filter(Boolean);
  for (const u of seen) {
    const m = u.match(new RegExp('[?&]' + col + '=(eq|in)\\.\\(?([^&)]*)\\)?'));
    const or = u.match(/[?&]or=\(([^&]*)\)/);
    const vals = m ? m[2].split(',').map((v) => v.replace(/^"|"$/g, '')) : null;
    if (!vals && !or) { c.fail(c.l1Row, `${c.tag}: read ${rel} with no filter on ${col} - every member's rows could come back (${u.slice(0, 140)})`); continue; }
    const foreign = (vals || []).filter((v) => !own.includes(v));
    if (foreign.length) c.fail(c.l1Row, `${c.tag}: read ${rel} for ${foreign.join(', ')} - not ${c.person.name}'s own`);
  }
  c.note(c.l1Row, seen.length
    ? `${c.tag}: ${seen.length} read(s) of ${rel}, each for ${c.person.name}'s own ${col} only (${own.length} own) - no other member's row is asked for`
    : `${c.tag}: no read of ${rel} on load - the page draws none of it until ${c.person.name} asks, and then only their own`);
  c.readings.actions = [String(seen.length)];
}, { ownReads: true });   // marked: two people's own reads differ by design, never compared

// aqTotal(rel, what, read, sql): a supervisor's page that TOTALS the hive's rows and lists none of them. The supervisor's
// figure is read off the screen (Engineering details opened, as a supervisor opens it) against the table; a worker is shown
// the supervisors-only gate, and the database returns them none of the other members' rows
const aqTotal = (rel, what, read, sql) => Object.assign(async (p, c) => {
  c.readings.actions = [];
  if (c.roleKey === 'worker') {
    const gated = await p.evaluate(() => !!document.querySelector('[data-wh-gate="supervisor-only"]') && !document.querySelector('.summary-row'));
    const others = as(c.person, `select exists (select 1 from ${rel} where hive_id = '${HIVE}' and auth_uid is distinct from (select auth.uid()))`);
    if (!gated) c.fail(c.l1Row, `${c.tag}: a worker is not shown the supervisors-only gate, or the hive's totals are drawn`);
    if (others !== 'f') c.fail(c.l1Row, `${c.tag}: the database ${others === 't' ? 'returns other members\' ' + rel : 'gave no answer'} to a worker`);
    if (gated && others === 'f') c.note(c.l1Row, `${c.tag}: shown "Supervisors only"; the database returns none of the other members' ${rel}`);
    return;
  }
  // ★the page opens at the hive's Stair 2 (maturity-gate.js, read from v_hive_readiness_truth); the full hive reads lower.
  // The lock is recorded as this hive gets it - a lock card, no figure, no member's item - and the totals are then read
  // as a Stair 2 hive sees them, that one view answered as Stair 2 (said in the reading, never hidden)
  if (await p.evaluate(() => /unlocks at Stair/.test(document.body.innerText))) {
    const figures = await p.evaluate(() => !!document.querySelector('.summary-row'));
    if (figures) c.fail(c.l1Row, `${c.tag}: the page is locked for this hive's stair, and still draws figures`);
    else c.note(c.l1Row, `${c.tag}: at this hive's own stair the page is locked (unlocks at Stair 2) - no figure, no member's item; read again as a Stair 2 hive sees it`);
    await p.route('**/rest/v1/v_hive_readiness_truth*', (r) => r.fulfill({ status: 200, contentType: 'application/json',
      body: JSON.stringify({ current_stair: 2, composite_score: 70, blocker_summary: '', evidence: {}, computed_at: new Date().toISOString() }) }));
    await p.reload({ waitUntil: 'load', timeout: 45000 });
  }
  // the page draws its cards once its reads return - the Engineering details button is the sign it has
  await p.waitForSelector('#details-toggle-btn', { timeout: 30000 }).catch(() => {});
  await openToggle(p, '#details-toggle-btn');
  const shown = await read(p), want = psql(sql);
  const people = psql(`select count(distinct worker_name) from ${rel} where hive_id = '${HIVE}' and created_at >= now() - interval '30 days'`);
  if (String(shown) !== String(want)) c.fail(c.l1Row, `${c.tag}: the page's ${what} reads ${shown}; the table holds ${want}`);
  else c.note(c.l1Row, `${c.tag}: the page's ${what} reads ${shown} - the table's, from ${people} members; no member's item is listed (totals only)`);
}, { lensNa: 'the page lists no member\'s item - it totals the hive\'s rows, so no name is drawn to mark or tell apart' });
// the harness runs psql through cmd's quoted -c: a newline in the SQL ends the command, so a fixture's SQL is one line
const psql1 = (sql) => psql(sql.replace(/\s*\n\s*/g, ' '));
// retiredGate(unit): a retired admin page reached by a hive member - nothing listed, nothing to act with
const retiredGate = (unit) => Object.assign(async (p, c) => {
  c.readings.actions = [];
  const r = await p.evaluate(() => {
    const ACT = /\b(approve|reject|suspend|verify|resolve|delete|ban|refund|release|archive|unpublish|reinstate)\b/i;
    const shown = (el) => el.checkVisibility && el.checkVisibility({ visibilityProperty: true, opacityProperty: true }) && !el.closest('[inert], [aria-hidden="true"]');
    const controls = [...document.querySelectorAll('button, [role="button"], a[href]')].filter((el) => shown(el) && !el.disabled && ACT.test(el.innerText || el.getAttribute('aria-label') || '')).length;
    const rows = [...document.querySelectorAll('table tbody tr, [data-listing-id], [data-order-id], [data-seller-id], [data-feedback-id], [data-trace-id]')].filter(shown).length;
    return { controls, rows };
  });
  if (r.controls || r.rows) c.fail(c.l1Row, `${c.tag}: ${r.rows} record row(s) and ${r.controls} control(s) on a member's screen of a retired page`);
  else c.note(c.l1Row, `${c.tag}: a retired page - no ${unit} record listed for a member, no control to act on one`);
}, { lensNa: 'a retired page lists no member\'s item - no name to mark or tell apart', l7Na: 'a retired page lists no hive\'s items - nothing to mix when the hive switches' });

// ── the pages and the relations they draw as a list ──────────────────────────────────────────────────────────────
// who / when: does the ask apply to this relation's item (a ranking of totals has no "when"; it says why).
const SPECS = {
  'community.html': {
    ready: '#feed-list .post-card',
    units: {
      community_posts: { rows: ['HS99', 'HS100'], item: '#feed-list .post-card', stub: '#feed-list .vcard-stub', more: '#feed-load-more button',
        who: true, when: true, menu: '.post-menu-btn', l2: POSTS_L2,
        population: `select count(*) from community_posts where hive_id = '${HIVE}' and deleted_at is null` },
      community_replies: { rows: ['HS106', 'HS107'], item: '#thread-replies .reply-card', who: true, when: true,
        // the population is the opened thread's own replies - that is the list on screen
        population: (opened) => `select count(*) from community_replies where hive_id = '${HIVE}' and post_id = '${opened}'`,
        // the post whose thread is the longest - the reply list a full hive actually produces
        open: async (p) => {
          const id = psql(`select post_id from community_replies where hive_id = '${HIVE}' group by post_id order by count(*) desc limit 1`);
          await p.evaluate((pid) => window.openThread && window.openThread(pid), id);
          await p.waitForSelector('#thread-replies .reply-card', { timeout: 15000 }).catch(() => {});
          await p.waitForTimeout(800);
          return id;
        },
        close: async (p) => { await p.keyboard.press('Escape').catch(() => {}); await p.waitForTimeout(300); } },
      community_xp: { rows: ['HS113', 'HS114'], item: '#leaderboard-list .lb-row', who: true,
        when: false, whenWhy: 'a ranking of XP totals, not a timeline - there is no single moment to show',
        population: `select count(*) from community_xp where hive_id = '${HIVE}'` },
      // the audit log on community is the reason a post was reported, shown to the supervisor who judges it. A worker
      // reads none of it - by design, and the database must agree - and a supervisor reads the Mod Queue, each card
      // saying why it was reported.
      hive_audit_log: { rows: ['HS120', 'HS121'], item: '#mod-list .post-card', who: true, when: true, menu: '.post-menu-btn',
        l2: { ...POSTS_L2, ownership: false },
        need: '[data-wh-report-reason]', needWhy: 'why it was reported', minPopulation: 1, minAuthors: 1,
        population: `select count(*) from community_posts where hive_id = '${HIVE}' and flagged and deleted_at is null`,
        none: { worker: { sel: '[data-wh-report-reason]', reads: `select exists (select 1 from hive_audit_log where hive_id = '${HIVE}')` } },
        open: async (p) => { await p.evaluate(() => window.switchTab && window.switchTab('mod')); await p.waitForTimeout(1500); return null; },
        close: async (p) => { await p.evaluate(() => window.switchTab && window.switchTab('feed')); await p.waitForTimeout(500); } },
    },
    // ★THE FIXTURE IS MADE THE WAY A PERSON MAKES IT. A hive of thirty has a post under review; the seeder does not make
    // one, so the first run reports a teammate's post as the worker, through the page's own menu and form - the RPC
    // raises the flag, the page writes the reason to the audit log. Later runs find it and reuse it.
    fixture: async (browser) => {
      const have = () => Number(psql(`select count(*) from community_posts p where p.hive_id = '${HIVE}' and p.flagged and p.deleted_at is null `
        + `and exists (select 1 from hive_audit_log a where a.hive_id = p.hive_id and a.action = 'report_post' and a.meta->>'target_id' = p.id::text)`)) || 0;
      // two under review, one of them neither subject's - so the supervisor's queue holds a teammate's post to judge
      if (have() >= 2) return `reported posts already under review (${have()})`;
      const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
      try {
        if (!(await signIn(ctx, PEOPLE.worker))) return 'the worker could not sign in to report a post';
        const p = await ctx.newPage();
        await p.goto(`${SEEDER}/workhive/community.html`, { waitUntil: 'load', timeout: 45000 });
        await p.waitForSelector('#feed-list .post-card .post-menu-btn', { timeout: 30000 });
        const card = p.locator('#feed-list .post-card')
          .filter({ hasNot: p.locator('.author-link', { hasText: PEOPLE.worker.name }) })
          .filter({ hasNot: p.locator('.author-link', { hasText: PEOPLE.supervisor.name }) }).first();
        await card.locator('.post-menu-btn').click();
        await card.getByRole('menuitem', { name: /Report this post/ }).click();
        await p.selectOption('#report-reason', 'unsafe');
        await p.fill('#report-details', 'The isolation step is missing - please check before anyone follows it.');
        await p.click('#btn-submit-report');
        await p.waitForTimeout(2500);
        return have() >= 2 ? 'reported a post through the page as the worker' : `the report did not reach the database (${have()} under review)`;
      } finally { await ctx.close(); }
    },
  },
  'hive.html': {
    ready: '#feed .feed-card',
    units: {
      // the roster: who is in the hive and how loaded they are. A roster is people, not events - no "when" to show.
      hive_members: { rows: ['HS147', 'HS148'], item: '#members-list [data-hv-rows] .rounded-xl:has(p.text-sm)', who: true,
        when: false, whenWhy: 'a roster of the people in the hive, not a timeline', authorSel: 'p.text-sm',
        buttons: 'button', l2: MEMBERS_L2, minPopulation: 25,
        population: `select count(*) from hive_members where hive_id = '${HIVE}' and status <> 'kicked'`,
        open: (p) => openToggle(p, '#btn-toggle-members') },
      // the activity feed: the hive's latest jobs and PMs, by whoever did them
      logbook: { rows: ['HS154', 'HS155'], item: '#feed > .feed-card:has(.ic-edit)', who: true, when: true, minPopulation: 3,
        population: `select count(*) from logbook where hive_id = '${HIVE}'`, open: (p) => openDetails(p, '#feed') },
      pm_completions: { rows: ['HS160', 'HS161'], item: '#feed > .feed-card:has(.ic-back)', who: true, when: true, minPopulation: 3,
        population: `select count(*) from pm_completions where hive_id = '${HIVE}' and status = 'done'`, open: (p) => openDetails(p, '#feed') },
      // community XP on hive.html is ONE member's figure, on that member's card - read one member at a time, never as a
      // list. What thirty members change is the names: near-twins ("Mark Anthony Santos" / "... Jr.", "Ana" / "Anna
      // Reyes", "Joel" / "Joey Cruz") must each get their own figure, and the card must name whose it is.
      community_xp: { rows: ['HS133', 'HS134'], lenses: { L6: 'the near-twins (Mark Anthony Santos / Jr., Ana / Anna Reyes, Joel / Joey Cruz) are each read for their own figure on their own card - a wrong figure or an unnamed card fails under L1' }, custom: async (p, c) => {
        const twins = ['Mark Anthony Santos', 'Mark Anthony Santos Jr.', 'Ana Reyes', 'Anna Reyes', 'Joel Cruz', 'Joey Cruz'];
        const offers = [];
        for (const name of twins) {
          const uid = memberCol(name, 'auth_uid');
          const want = psql(`select coalesce((select xp_total from community_xp where hive_id = '${HIVE}' and worker_name = '${sqlq(name)}'), 0)`);
          const got = await p.evaluate(async ({ name, uid }) => {
            if (typeof window._openWorkerProfileDrawer !== 'function') return { err: 'no profile card on this page' };
            window._openWorkerProfileDrawer(name, uid);
            for (let i = 0; i < 60; i++) {
              await new Promise((r) => setTimeout(r, 200));
              const panel = document.getElementById('wh-wp-panel');
              const xpLabel = [...(panel?.querySelectorAll('p') || [])].find((x) => x.textContent.trim() === 'Community XP');
              if (xpLabel) {
                const btns = [...panel.querySelectorAll('button')].map((b) => (b.innerText || b.getAttribute('aria-label') || '').trim());
                return { title: (panel.innerText || '').split('\n').map((s) => s.trim()).filter(Boolean)[0] || '', xp: xpLabel.nextElementSibling?.textContent.trim(), btns };
              }
            }
            return { err: 'the card never drew its figures' };
          }, { name, uid });
          await p.evaluate(() => { const d = document.getElementById('wh-worker-profile-drawer'); if (d) d.style.display = 'none'; });
          if (got.err) { c.fail(c.l1Row, `${c.tag}: ${name}'s card - ${got.err}`); continue; }
          if (!got.title.includes(name) || (name.length < 20 && twins.some((t) => t !== name && t.startsWith(name) && got.title.includes(t)))) {
            c.fail(c.l1Row, `${c.tag}: ${name}'s card is titled "${got.title}" - it does not say whose figure this is`);
          }
          if (String(got.xp) !== String(want)) c.fail(c.l1Row, `${c.tag}: ${name}'s card shows ${got.xp} XP; their own row holds ${want}`);
          if (L7 && name === 'Joel Cruz') {
            const r7 = LENS(c.l1Row, 'L7');
            if (r7 && String(got.xp) === '777') c.fail(r7, `${c.tag}: Joel's card shows 777 XP - the other hive's figure, not this hive's ${want}`);
            else if (r7) c.note(r7, `${c.tag}: Joel is a member of both hives; his card reads this hive's ${got.xp} XP, not the other hive's 777`);
          }
          offers.push(JSON.stringify(got.btns.sort()));
        }
        c.note(c.l1Row, `${c.tag}: ${twins.length} near-twin members' cards each show their own XP (${twins.join(', ')})`);
        c.readings.actions = [...new Set(offers)];
      } },
      // the audit log: the supervisor's record of who changed what. A worker reads none of it.
      hive_audit_log: { rows: ['HS140', 'HS141'], item: '#audit-log-list > div', who: true, when: true, minAuthors: 1,
        population: `select count(*) from hive_audit_log where hive_id = '${HIVE}'`,
        none: { worker: { sel: '#audit-log-list > div', reads: `select exists (select 1 from hive_audit_log where hive_id = '${HIVE}')` } },
        open: (p) => openToggle(p, '#btn-toggle-audit') },
    },
  },
  'logbook.html': {
    ready: '#view-toggle-bar',
    units: {
      // the Team Feed: the hive's entries in a date range, each opened to its detail where Edit and Delete live
      logbook: { rows: ['HS217', 'HS217'], item: '#entries-list .entry-card', who: true, when: true, minPopulation: 3,
        more: 'button[onclick="loadMoreLogbook()"]',
        modal: { open: 'openModal', idAttr: 'entryId', sel: '#modal-content button', close: "document.getElementById('modal').classList.add('hidden')" },
        l2: ENTRIES_L2,
        // the range is widened to 120 days so the walk reaches the subjects' OWN entries (a week held none of theirs)
        population: `select count(*) from logbook where hive_id = '${HIVE}' and deleted_at is null and (date at time zone 'Asia/Manila')::date >= (now() at time zone 'Asia/Manila')::date - 120`,
        open: async (p) => {
          await p.evaluate(() => { const b = document.getElementById('btn-view-team'); if (b && b.getAttribute('aria-pressed') !== 'true') b.click(); });
          await p.waitForTimeout(800);
          await p.evaluate(() => {
            const from = document.getElementById('filter-date-from');
            if (from) from.value = whManilaYmd(new Date(Date.now() - 120 * 86400000));
            document.getElementById('btn-search-team')?.click();
          });
          await p.waitForSelector('#entries-list .entry-card', { timeout: 20000 }).catch(() => {});
          await p.waitForTimeout(1000);
          return null;
        } },
      // the Team Feed's worker filter: every member by full name, near-twins told apart
      hive_members: { rows: ['HS199', 'HS200'], lenses: { L5: 'the filter still offers the member who left (checked under L1: "including one who left"), so their entries stay findable', L6: 'the near-twins (Mark Anthony Santos / Jr., Ana / Anna Reyes, Joel / Joey Cruz) are each read for their own option by full name - a twin missing or a name offered twice fails under L1' }, custom: async (p, c) => {
        await p.evaluate(() => { const b = document.getElementById('btn-view-team'); if (b && b.getAttribute('aria-pressed') !== 'true') b.click(); });
        await p.waitForTimeout(800);
        const opts = await p.evaluate(() => [...(document.getElementById('filter-worker')?.options || [])].map((o) => o.textContent.trim()).filter((t) => t !== 'All workers'));
        const shown = await p.evaluate(() => { const s = document.getElementById('filter-worker'); return !!s && s.checkVisibility(); });
        const want = psql(`select string_agg(worker_name, '|' order by worker_name) from hive_members where hive_id = '${HIVE}'`).split('|');
        if (!shown) c.fail(c.l1Row, `${c.tag}: the worker filter is not on screen`);
        const missing = want.filter((w) => !opts.includes(w)), extra = opts.filter((o) => !want.includes(o));
        if (missing.length) c.fail(c.l1Row, `${c.tag}: the filter leaves out ${missing.join(', ')}`);
        if (extra.length) c.fail(c.l1Row, `${c.tag}: the filter names ${extra.join(', ')}, who are not members`);
        if (new Set(opts).size !== opts.length) c.fail(c.l1Row, `${c.tag}: a name appears twice in the filter`);
        if (L7) {
          const r7 = LENS(c.l1Row, 'L7');
          if (r7 && opts.includes('Efren Dizon')) c.fail(r7, `${c.tag}: the worker filter offers Efren Dizon, a member of the OTHER hive only`);
          else if (r7) c.note(r7, `${c.tag}: ${c.person.name} is a member of both hives; the worker filter offers this hive's ${opts.length} members and not Efren Dizon, who belongs to the other one only`);
        }
        for (const [a, b] of [['Mark Anthony Santos', 'Mark Anthony Santos Jr.'], ['Ana Reyes', 'Anna Reyes'], ['Joel Cruz', 'Joey Cruz']]) {
          if (!opts.includes(a) || !opts.includes(b)) c.fail(c.l1Row, `${c.tag}: near-twins ${a} / ${b} are not both offered`);
        }
        c.note(c.l1Row, `${c.tag}: the worker filter offers ${opts.length} members by full name (the hive has ${want.length}, including one who left)`);
        c.readings.actions = [JSON.stringify(opts)];
      } },
      // an asset's detail: the parts used on it (inventory_transactions) and its fault history (logbook), both a list of
      // many members' work - opened on the machine whose parts were used the most
      inventory_transactions: { rows: ['HS211', 'HS212'], item: '#detail-consumption-list > .rounded-xl', who: true, when: true, minPopulation: 3,
        population: `select least(count(*), 50) from inventory_transactions t join inventory_items i on i.id = t.item_id where t.hive_id = '${HIVE}' and t.type = 'use' and (select id from asset_nodes where hive_id = '${HIVE}' and tag = '${TOP_TAG}') = any(i.linked_asset_node_ids)`,
        open: (p) => openAssetDetail(p, 'consumption'), close: closeAssetDetail },
      inventory_items: { rows: ['HS205', 'HS206'], item: '#detail-stocked-list > .rounded-xl', who: false,
        whoWhy: "a part on the hive's shelf, linked to this machine - the shelf, not a person, is whose it is",
        when: false, whenWhy: 'stock on hand now, not an event', minPopulation: 2, minAuthors: 0,
        population: `select count(*) from inventory_items where hive_id = '${HIVE}' and (select id from asset_nodes where hive_id = '${HIVE}' and tag = '${TOP_TAG}') = any(linked_asset_node_ids)`,
        open: (p) => openAssetDetail(p, 'stocked'), close: closeAssetDetail },
    },
  },
  'inventory.html': {
    ready: '#parts-list .part-card',
    units: {
      // the hive's shelf: each card says what the part is, how many and where; who added it is on its detail
      inventory_items: { rows: ['HS181', 'HS182'], item: '#parts-list .part-card', who: false,
        whoWhy: "a part on the hive's shelf - its card says what, how many and where; who added it is on its detail",
        when: false, whenWhy: 'stock on hand now, not an event', minAuthors: 0,
        modal: { open: 'openDetailModal', idAttr: 'partId', sel: '#detail-content button', close: 'closeDetailModal()' },
        l2: INV_L2, more: '#inv-load-more-wrap button',
        mineIds: (person) => `select string_agg(id::text, ' ') from inventory_items where hive_id = '${HIVE}' and worker_name = '${sqlq(person.name)}' and deleted_at is null`,
        population: `select count(*) from inventory_items where hive_id = '${HIVE}' and deleted_at is null` },
      // a part's history: every member's movements of it (HS L1: it was the viewer's own only)
      inventory_transactions: { rows: ['HS187', 'HS188'], item: '#detail-history .txn-row', who: true, when: true, minPopulation: 3,
        population: `select least(count(*), 20) from inventory_transactions where item_id = '${TOP_ITEM}'`,
        open: async (p) => { await p.evaluate((id) => openDetailModal(id), TOP_ITEM); await p.waitForTimeout(2500); return null; },
        close: async (p) => {
          if (!/inventory\.html/.test(p.url())) throw new Error(`inventory_transactions: opening the part's detail left inventory.html for ${p.url()}`);
          await p.evaluate(() => closeDetailModal()); } },
      // the asset linker in the part form: the hive's machines, each by tag and name
      asset_nodes: { rows: ['HS174', 'HS175'], lenses: { L5: 'the linker offers machines, not members - no departure to say', L6: 'the linker offers machines by tag and name, not members - no name to tell apart' }, custom: async (p, c) => {
        await p.evaluate(() => openAddModal());
        await p.waitForTimeout(1200);
        const tags = await p.evaluate(() => [...document.querySelectorAll('#asset-linker .asset-tag')].map((b) => ({
          t: (b.innerText || '').trim(), vis: b.checkVisibility(), over: b.getBoundingClientRect().right > innerWidth + 1 })));
        await p.evaluate(() => { if (typeof closeAddModal === 'function') closeAddModal(); });
        // approved machines, plus this person's OWN pending submissions (a worker links a part to the machine they just
        // registered before a supervisor approves it) - each role is held to its own set, never to the other's
        const want = psql(`select string_agg(tag || ': ' || name, '|' order by tag) from asset_nodes where hive_id = '${HIVE}' and deleted_at is null and (status = 'approved' or (status = 'pending' and auth_uid = (select auth_uid from hive_members where hive_id = '${HIVE}' and worker_name = '${sqlq(c.person.name)}')))`).split('|').filter(Boolean);
        const got = tags.map((x) => x.t);
        // L7: the second hive holds an approved machine of its own (HSL7-M1); a linker that read machines by membership
        // rather than by the hive in use would offer it here - it is named, not left to the "extra" check to imply
        if (L7) {
          const r7 = LENS(c.l1Row, 'L7');
          if (r7) {
            if (got.some((g) => g.startsWith('HSL7-M1'))) c.fail(r7, `${c.tag}: the linker offers the other hive's machine HSL7-M1 to ${c.person.name}, a member of both`);
            else c.note(r7, `${c.tag}: ${c.person.name} is a member of both hives; the linker offers this hive's ${got.length} machine(s) and not the other's HSL7-M1`);
          }
        }
        const extra = got.filter((g) => !want.includes(g));
        if (extra.length) c.fail(c.l1Row, `${c.tag}: the linker offers ${extra.join(', ')}, which this person may not link`);
        const missing = want.filter((w) => !got.includes(w));
        if (!tags.length) c.fail(c.l1Row, `${c.tag}: the part form links to no machine - the hive has ${want.length}`);
        if (missing.length) c.fail(c.l1Row, `${c.tag}: the linker leaves out ${missing.join(', ')}`);
        if (tags.some((x) => !x.vis)) c.fail(c.l1Row, `${c.tag}: ${tags.filter((x) => !x.vis).length} machine(s) in the linker cannot be seen`);
        if (tags.some((x) => x.over)) c.fail(c.l1Row, `${c.tag}: a machine in the linker runs past the screen's edge`);
        if (new Set(got).size !== got.length) c.fail(c.l1Row, `${c.tag}: a machine appears twice in the linker`);
        c.note(c.l1Row, `${c.tag}: the part form's linker offers the hive's ${got.length} machines by tag and name ("who/when" do not apply to a machine to link a part to)`);
        c.readings.actions = ['each role held to its own set above'];
      } },
    },
  },
  'asset-hub.html': {
    ready: '#asset-list .asset-card',
    units: {
      // the hive's machine register - machines, not a member's work: legible, not attributed
      asset_nodes: { rows: ['HS31', 'HS32'], item: '#asset-list .asset-card', who: false,
        whoWhy: "a machine of the hive's register, not a member's work item", when: false, whenWhy: 'a machine in service, not an event',
        minAuthors: 0, minPopulation: 8, idAttr: 'nodeId',
        population: `select count(*) from asset_nodes where hive_id = '${HIVE}' and status = 'approved' and deleted_at is null` },
      // the approval queue: a worker's submitted machine, approved or rejected by a supervisor
      asset_nodes_pending: { rows: ['HS32', 'HS32'], item: '#pending-assets-list .pending-row', who: true, when: false,
        whenWhy: 'a queue of machines waiting for a decision', minPopulation: 1, minAuthors: 1,
        buttons: 'button', idFrom: '[data-id]', l2: PENDING_L2,
        population: `select count(*) from asset_nodes where hive_id = '${HIVE}' and status = 'pending' and deleted_at is null`,
        none: { worker: { sel: '#pending-assets-list .pending-row button.approve',
          reads: () => took(`update asset_nodes set status = 'approved' where id = (select id from asset_nodes where hive_id = '${HIVE}' and status = 'pending' limit 1)`) } },
        open: async (p) => { await p.evaluate(() => { if (typeof loadPendingAssets === 'function') return loadPendingAssets(); }); await p.waitForTimeout(2000); return null; } },
      // a machine's history: its logbook entries and PM completions on one timeline, by whoever did them
      logbook: { rows: ['HS38', 'HS39'], item: '#timeline-list .tl-row', match: 'Logbook', who: true, when: true, minPopulation: 3,
        population: `select count(*) from logbook where asset_node_id = '${NODE_BUSY}' and deleted_at is null`,
        open: (p) => openNode(p, NODE_BUSY), close: closeNode },
      pm_completions: { rows: ['HS52', 'HS53'], item: '#timeline-list .tl-row', match: '\\bPM\\b', who: true, when: true, minPopulation: 3,
        population: `select count(*) from pm_completions c join asset_nodes n on n.pm_asset_id = c.asset_id where n.id = '${NODE_BUSY}'`,
        open: (p) => openNode(p, NODE_BUSY), close: closeNode },
      // listings for what the machine is - sold by the platform's sellers, not the hive's members
      marketplace_listings: { rows: ['HS45', 'HS46'], lenses: { L5: 'a marketplace listing names its seller on the platform, not a member of this hive - hive membership, and leaving it, is not what the card says' },  item: '#mk-list .mk-row', who: true, whoSel: '.mk-meta', when: true,
        minPopulation: 1, minAuthors: 1,
        population: `select count(*) from marketplace_listings where status = 'published' and category in ('Pumps', 'Mechanical')`,
        open: (p) => openNode(p, nodeOf('BRM-P-101')), close: closeNode },
      // the reliability record: each failure mode says who proposed it and who approved it, and when
      rcm_fmea_modes: { rows: ['HS59', 'HS60'], item: '#fmea-list .fmea-row', who: true, when: true, minPopulation: 1, minAuthors: 1,
        idAttr: 'modeId', buttons: '.fmea-row-actions button', l2: FMEA_L2,
        mineIds: (person) => `select string_agg(id::text, ' ') from rcm_fmea_modes where hive_id = '${HIVE}' and created_by = '${sqlq(person.name)}'`,
        population: `select count(*) from rcm_fmea_modes where asset_id = '${NODE_PENDING_FMEA}'`,
        // the reliability record sits behind the engineer view's toggle - opened the way a person opens it
        open: async (p) => { await openNode(p, NODE_PENDING_FMEA); await openToggle(p, '#asset-view-toggle'); return null; }, close: closeNode },
    },
    // a hive of thirty has a machine waiting for approval: one is submitted by the worker through the API, as the page's
    // register form writes it (an insert as the member), and later runs reuse it
    fixture: async () => {
      const have = () => Number(psql(`select count(*) from asset_nodes where hive_id = '${HIVE}' and status = 'pending' and deleted_at is null`)) || 0;
      if (have()) return `a machine already waits for approval (${have()})`;
      psql(`begin; select set_config('request.jwt.claims', json_build_object('sub', (select auth_uid from hive_members where worker_name = 'Joel Cruz' and hive_id = '${HIVE}')::text, 'role', 'authenticated')::text, true); `
        + `set local role authenticated; insert into asset_nodes (hive_id, auth_uid, worker_name, submitted_by, level, tag, name, iso_class, criticality, status) `
        + `values ('${HIVE}', auth.uid(), 'Joel Cruz', 'Joel Cruz', 'equipment', 'BRM-P-103', 'Spare crude charge pump P-103', 'Mechanical', 'medium', 'pending'); commit;`);
      return have() ? 'the worker submitted a machine for approval' : 'the submission did not reach the database';
    },
  },
  'project-manager.html': {
    ready: '#card-grid .pcard',
    units: {
      // the hive's projects - each card names its owner and its end date
      projects: { rows: ['HS363', 'HS364'], item: '#card-grid .pcard', who: true, when: true, minPopulation: 3, minAuthors: 2,
        population: `select count(*) from projects where hive_id = '${HIVE}' and deleted_at is null` },
      // a project's scope: who owns each step and when it is due; any member moves and edits a step
      project_items: { rows: ['HS349', 'HS350'], l7ById: true, item: '#pane-scope tr[data-item-id]', who: true, when: true, minPopulation: 3,
        idAttr: 'itemId', buttons: 'button', l2: ITEMS_L2,
        population: `select count(*) from project_items where project_id = '${PROJ_BUSY}'`,
        open: (p) => openProject(p, 'scope') },
      // the project's team: who holds each role, who assigned them, when; a supervisor removes a role
      // read by project membership, not hive membership (tenant_declarations): Joel Cruz is on no project's team
      project_roles: { rows: ['HS356', 'HS357'], l7ById: true, item: '#pane-roles .link-pill[data-role-id]', who: true, when: true, minPopulation: 3,
        none: { worker: { sel: '#pane-roles .link-pill[data-role-id]',
          reads: () => `select exists (select 1 from project_roles where project_id = '${PROJ_BUSY}')` } },
        idAttr: 'roleId', buttons: 'button', l2: ROLES_L2,
        population: `select count(*) from project_roles where project_id = '${PROJ_BUSY}' and deleted_at is null`,
        open: (p) => openProject(p, 'roles') },
      // the project's change orders: raised by the team, decided by a supervisor
      project_change_orders: { rows: ['HS342', 'HS343'], l7ById: true, item: '#pane-changes .co-card', who: true, when: true, minPopulation: 2,
        minAuthors: 1, idAttr: 'coId', buttons: 'button', l2: CO_L2,
        mineIds: (person) => `select string_agg(id::text, ' ') from project_change_orders where project_id = '${PROJ_BUSY}' and requested_by = '${sqlq(person.name)}'`,
        population: `select count(*) from project_change_orders where project_id = '${PROJ_BUSY}'`,
        open: (p) => openProject(p, 'changes') },
      // the member pickers: the owner FILTER offers everyone who ever worked here (a departed member's projects stay
      // findable); the pickers that hand out NEW work offer active members only
      hive_members: { rows: ['HS307', 'HS308'], lenses: { L5: 'new work is offered only to active members and the owner filter still finds a departed member\'s projects - both checked under L1', L6: 'the owner pickers offer each member by full name - near-twins both offered, read under L1' }, custom: async (p, c) => {
        const got = await p.evaluate(() => ({
          filter: [...(document.getElementById('filter-owner')?.options || [])].map((o) => o.value).filter(Boolean),
          scope: [...(document.getElementById('s-owner')?.options || [])].map((o) => o.value).filter(Boolean),
          project: [...(document.getElementById('f-owner')?.options || [])].map((o) => o.value).filter(Boolean) }));
        const all = psql(`select string_agg(worker_name, '|') from hive_members where hive_id = '${HIVE}'`).split('|').filter(Boolean);
        const active = psql(`select string_agg(worker_name, '|') from hive_members where hive_id = '${HIVE}' and status = 'active'`).split('|').filter(Boolean);
        const left = all.filter((n) => !active.includes(n));
        const miss = (have, want) => want.filter((w) => !have.includes(w));
        if (miss(got.filter, all).length) c.fail(c.l1Row, `${c.tag}: the owner filter leaves out ${miss(got.filter, all).join(', ')}`);
        for (const k of ['scope', 'project']) {
          if (miss(got[k], active).length) c.fail(c.l1Row, `${c.tag}: the ${k} owner picker leaves out ${miss(got[k], active).join(', ')}`);
          const gone = got[k].filter((n) => left.includes(n));
          if (gone.length) c.fail(c.l1Row, `${c.tag}: the ${k} owner picker offers ${gone.join(', ')}, who left the hive`);
        }
        for (const [a, b] of [['Mark Anthony Santos', 'Mark Anthony Santos Jr.'], ['Ana Reyes', 'Anna Reyes'], ['Joel Cruz', 'Joey Cruz']]) {
          if (!got.scope.includes(a) || !got.scope.includes(b)) c.fail(c.l1Row, `${c.tag}: near-twins ${a} / ${b} are not both offered`);
        }
        c.note(c.l1Row, `${c.tag}: the owner filter offers ${got.filter.length} (everyone, incl. ${left.join(', ') || 'no one'} who left); the scope and project pickers offer ${got.scope.length} active members`);
        if (L7) {
          const r7 = LENS(c.l1Row, 'L7');
          const leaked = ['filter', 'scope', 'project'].filter((k) => got[k].includes('Efren Dizon'));
          if (r7 && leaked.length) c.fail(r7, `${c.tag}: the ${leaked.join(' and ')} owner list offers Efren Dizon, a member of the OTHER hive only`);
          else if (r7) c.note(r7, `${c.tag}: ${c.person.name} is a member of both hives; the owner filter and both pickers offer this hive's members and not Efren Dizon, who belongs to the other one only`);
        }
        c.readings.actions = [JSON.stringify([got.filter.length, got.scope.length])];
      } },
      // the work a project can be linked to: each option says what, who and when (a picker's option is its item)
      ...Object.fromEntries([['logbook', 'HS321', 'HS322', 50], ['pm_completions', 'HS335', 'HS336', 50],
        ['engineering_calcs', 'HS300', 'HS301', 12], ['inventory_items', 'HS314', 'HS315', 40], ['asset_nodes', 'HS293', 'HS294', 10],
        ['marketplace_listings', 'HS328', 'HS329', 0]].map(([unit, r1, r2, n]) => [unit, { rows: [r1, r2], custom: async (p, c) => {
        const type = { logbook: 'logbook', pm_completions: 'pm_completion', engineering_calcs: 'engineering_calc', inventory_items: 'inventory_item',
          asset_nodes: 'asset', marketplace_listings: 'marketplace_listing' }[unit];
        await openProject(p, 'linked');
        const opts = await p.evaluate(async (t) => {
          if (typeof openModal === 'function') openModal('modal-link');
          const sel = document.getElementById('l-type'); if (!sel) return null;
          sel.value = t; sel.dispatchEvent(new Event('change'));
          if (typeof loadLinkOptions === 'function') await loadLinkOptions();
          await new Promise((r) => setTimeout(r, 600));
          const o = [...document.querySelectorAll('#l-picker option')].map((x) => x.textContent.trim()).filter(Boolean);
          if (typeof closeModal === 'function') closeModal('modal-link');
          return o;
        }, type);
        if (!opts) { c.fail(c.l1Row, `${c.tag}: the link form has no type picker`); return; }
        const dup = opts.length - new Set(opts).size;
        if (n && opts.length < Math.min(n, 3)) c.fail(c.l1Row, `${c.tag}: the ${type} picker offered ${opts.length} option(s) - the hive has ${n}`);
        if (dup) c.fail(c.l1Row, `${c.tag}: ${dup} of ${opts.length} ${type} options read exactly like another - a person cannot tell which to link`);
        if (['logbook', 'pm_completion', 'engineering_calc'].includes(type)) {
          const nameless = opts.filter((o) => !MEMBERS.some((m) => o.includes(m)));
          if (nameless.length) c.fail(c.l1Row, `${c.tag}: ${nameless.length} ${type} options say nobody's work (e.g. "${nameless[0]}")`);
        }
        // L7 on the picker (--l7): the person may read both hives, so the picker's own hive filter is all that keeps the
        // other hive's work out of what a project in THIS hive can be linked to
        const l7 = LENS(c.l1Row, 'L7');
        if (L7 && l7) {
          const leaked = opts.filter((o) => o.includes(L7_MARK));
          if (leaked.length) c.fail(l7, `${c.tag}: the ${type} picker offers ${leaked.length} item(s) of the person's OTHER hive (e.g. "${leaked[0]}")`);
          else c.note(l7, `${c.tag}: the person belongs to two hives; the ${type} picker offers ${opts.length} option(s), none of the other hive's - a project links only its own hive's work`);
        }
        // L5 / L6 on the picker: an option that names a departed member says so; an option's text is never cut, so a name
        // in it is whole (an option names parts, machines or listings for the other types - no member to mark)
        const l5 = LENS(c.l1Row, 'L5'), l6 = LENS(c.l1Row, 'L6');
        if (['logbook', 'pm_completion', 'engineering_calc'].includes(type)) {
          const gone = opts.filter((o) => [...FORMER].some((nm) => o.includes(nm)));
          const bare = gone.filter((o) => [...FORMER].some((nm) => o.includes(nm) && !o.includes(`${nm} (former member)`)));
          if (l5) {
            if (bare.length) c.fail(l5, `${c.tag}: ${bare.length} ${type} option(s) name a member who left as if still in the hive (e.g. "${bare[0]}")`);
            else if (gone.length) c.note(l5, `${c.tag}: ${gone.length} ${type} option(s) by a member who left, each says "(former member)"`);
            else c.fail(l5, `${c.tag}: no ${type} option by a member who has left - nothing to judge (one is owed in the picker's window)`);
          }
          if (l6) c.note(l6, `${c.tag}: each of ${opts.length} ${type} options names its member in full text (an option's text is never cut)`);
        } else {
          if (l5) c.note(l5, `${c.tag}: the ${type} options name the thing linked, not a member - no departure to say`);
          if (l6) c.note(l6, `${c.tag}: the ${type} options name the thing linked, not a member - no name to tell apart`);
        }
        c.note(c.l1Row, `${c.tag}: the ${type} picker offers ${opts.length} option(s), ${opts.length - dup} distinct`
          + (n === 0 ? ' - the hive lists nothing on the marketplace of its own, so an empty picker is the truth' : ''));
        c.readings.actions = [String(opts.length)];
      } }])),
    },
  },
  'pm-scheduler.html': {
    ready: '#asset-list .asset-card',
    units: {
      // the hive's PM programs: each card says whose program it is ("yours" for the viewer's) and when it is next due
      pm_assets: { rows: ['HS281', 'HS282'], item: '#asset-list .asset-card', who: true, when: true, minPopulation: 5, minAuthors: 2,
        population: `select count(*) from pm_assets where hive_id = '${HIVE}'` },
      // a program's history: each completion says which task, who did it and when
      pm_completions: { rows: ['HS287', 'HS288'], item: '#det-history .history-row', who: true, when: true, minPopulation: 3,
        need: 'p', needWhy: 'which task was done',
        population: `select count(*) from pm_completions where asset_id = '${PM_BUSY}'`,
        open: async (p) => { await p.evaluate((id) => openDetail(id), PM_BUSY); await p.waitForTimeout(1500); return PM_BUSY; } },
    },
  },
  'dayplanner.html': {
    ready: '[data-dp-lb-rows]',
    units: {
      // the planner's sidebar: the viewer's OWN open jobs, to drag onto the day
      // on a phone the sidebar starts closed - opened with its own toggle, as a person opens it
      logbook: { rows: ['HS127', 'HS128'], item: '[data-dp-lb-rows] > *', ownOnly: true, who: true, when: true, cap: 1000,
        open: (p) => openToggle(p, '#sidebar-toggle'),
        population: (_o, person) => `select count(*) from logbook where worker_name = '${sqlq(person.name)}' and deleted_at is null and status not in ('Closed', 'Resolved')` },
    },
  },
  'integrations.html': {
    ready: 'body',
    units: {
      // CMMS conflicts: SAP says one thing, a member's latest entry another - each card says whose entry and when; a
      // supervisor's tool (a worker meets a wall, and the database refuses a worker's write to the sync)
      logbook: { rows: ['HS167', 'HS168'], item: '.sync-conflict', who: true, when: true, minPopulation: 2, minAuthors: 2,
        idAttr: 'logId', buttons: 'button', l2: CONFLICT_L2,
        population: `select count(*) from external_sync e where e.hive_id = '${HIVE}' and e.entity_type = 'work_order' and e.status <> coalesce((select l.status from logbook l where l.hive_id = e.hive_id and l.machine = e.sync_payload->>'machine' and l.worker_name not in ('CMMS Sync', 'cmms-sync') and l.deleted_at is null order by l.date desc, l.id limit 1), e.status)`,
        none: { worker: { sel: '.sync-conflict',
          reads: () => took(`update external_sync set status = status where hive_id = '${HIVE}'`) } },
        open: async (p) => {
          // the conflicts live on the Live Sync tab: opened, then "Check Now" pressed, as a supervisor does
          await p.evaluate(async () => { document.getElementById('tab-sync')?.click(); await new Promise((r) => setTimeout(r, 400));
            const b = document.querySelector('button[onclick="loadConflicts()"]'); if (b) { b.scrollIntoView(); b.click(); } });
          await p.waitForSelector('.sync-conflict', { timeout: 15000 }).catch(() => {});
          await p.waitForTimeout(600); return null;
        } },
    },
  },
  'alert-hub.html': {
    ready: '.alert',
    units: {
      // low-stock alerts: one per PART - two bins of a same-named part are two alerts with two keys, so handling one
      // cannot hide the other (the dismissal and seen marks match on the key)
      inventory_items: { rows: ['HS24', 'HS25'], item: '.alert.kind-stock', who: false, minAuthors: 0, minPopulation: 2,
        whoWhy: "an alert about a part on the hive's shelf - the shelf, not a person, is whose it is", when: true,
        idAttr: 'alertKey', distinctIds: true, distinctWhy: 'handling one alert would hide the other (a name is not an identity)',
        population: `select count(*) from v_inventory_items_truth where hive_id = '${HIVE}' and (is_out_of_stock or is_critical_low or is_low_stock or qty_on_hand <= 0)` },
    },
    // a plant keeps the same part in two bins: a second, same-named bin of an at-risk part, empty
    fixture: async () => {
      const dupes = () => Number(psql(`select count(*) from (select part_name from v_inventory_items_truth where hive_id = '${HIVE}' and (is_out_of_stock or is_critical_low or is_low_stock or qty_on_hand <= 0) group by part_name having count(*) > 1) d`)) || 0;
      if (dupes()) return `a same-named part is already at risk in two bins (${dupes()})`;
      psql(`insert into inventory_items (id, hive_id, worker_name, auth_uid, submitted_by, part_name, part_number, bin_location, qty_on_hand, min_qty, unit, status) `
        + `select 'inv-hs-second-bin', hive_id, 'Joel Cruz', (select auth_uid from hive_members where worker_name = 'Joel Cruz' and hive_id = '${HIVE}'), 'Joel Cruz', `
        + `part_name, 'BRM-0041', 'Bay 9', 0, 2, 'pcs', 'approved' from v_inventory_items_truth where hive_id = '${HIVE}' `
        + `and (is_out_of_stock or is_critical_low or is_low_stock or qty_on_hand <= 0) order by part_name limit 1 on conflict (id) do nothing`);
      return dupes() ? 'a second bin of an at-risk part, same name, is on the shelf' : 'the second bin did not reach the database';
    },
  },
  'plant-connections.html': {
    ready: 'body',
    units: {
      // the gateway audit: the API calls the hive's integrations made this week - route, status, caller, when. A
      // supervisor's table (the page walls a worker off, and the read policy returns it to supervisors only)
      gateway_audit_log: { rows: ['HS259', 'HS260'], item: '.pc-table tbody tr', match: '/api/', who: true, when: true,
        minPopulation: 5, minAuthors: 2,
        // the audit table sits in the dashboard's "Show details" pane - opened the way a supervisor opens it
        open: (p) => openToggle(p, '#details-toggle-btn'),
        population: `select least(count(*), 10) from gateway_audit_log where hive_id = '${HIVE}' and created_at > now() - interval '7 days'`,
        none: { worker: { sel: '.pc-table tbody tr', reads: () => `select exists (select 1 from gateway_audit_log where hive_id = '${HIVE}')` } } },
    },
    // a plant's integrations call in all week: the historian on Ernesto Villareal's key, the CMMS bridge on Danilo
    // Pascual's. The card reads the last seven days, so the week is laid down when the walk runs.
    fixture: async () => {
      const recent = () => Number(psql(`select count(*) from gateway_audit_log where hive_id = '${HIVE}' and created_at > now() - interval '6 days'`)) || 0;
      if (recent() >= 10) return `this week's gateway calls are already there (${recent()})`;
      psql(`insert into gateway_audit_log (hive_id, worker_name, auth_uid, route, request_id, method, status_code, latency_ms, created_at) `
        + `select '${HIVE}', w.name, (select auth_uid from hive_members where hive_id = '${HIVE}' and worker_name = w.name), `
        + `w.route, 'hs-' || g || '-' || w.k, w.method, case when g % 11 = 0 then 429 when g % 13 = 0 then 401 else 200 end, 40 + (g * 37) % 400, `
        + `now() - (g || ' hours')::interval - (w.k || ' minutes')::interval `
        + `from generate_series(1, 12) g, (values (1, 'Ernesto Villareal', '/api/v1/readings', 'POST'), (2, 'Danilo Pascual', '/api/v1/work-orders', 'GET')) w(k, name, route, method)`);
      return recent() >= 10 ? 'the week of gateway calls is laid down' : 'the gateway calls did not reach the database';
    },
  },
  'project-report.html': {
    ready: '#exec-summary',
    units: {
      // with no project chosen, the report offers the hive's recent projects: each says whose and when it last moved
      project: { rows: ['HS370', 'HS371'], item: '#exec-summary li', who: true, when: true, minPopulation: 3, minAuthors: 2,
        population: `select least(count(*), 8) from projects where hive_id = '${HIVE}' and deleted_at is null` },
      // a project's report: its scope, each step with its owner and due date
      project_items: { rows: ['HS376', 'HS377'], l7ById: true, item: '#scope-section tbody tr', who: true, when: true, minPopulation: 3,
        population: `select count(*) from project_items where project_id = '${PROJ_BUSY}'`,
        open: async (p) => {
          await p.goto(`${SEEDER}/workhive/project-report.html?project_id=${PROJ_BUSY}`, { waitUntil: 'load', timeout: 45000 });
          await p.waitForSelector('#scope-section tbody tr', { timeout: 20000 }).catch(() => {});
          await p.waitForTimeout(800); return PROJ_BUSY;
        } },
    },
  },
  'assistant.html': {
    ready: 'body',
    // the census counted three ordered reads here - all inside buildSystemPrompt, whose call was removed (K1, 2026-07-12:
    // the client's context bundle is no longer sent). What a hive of thirty puts into the assistant is MEASURED: every
    // request the page sends on load is captured, and a list read (a GET of rows) of the relation must not be among them.
    units: Object.fromEntries([['inventory_items', 'v_inventory_items_truth', 'HS66', 'HS67'], ['logbook', 'v_logbook_truth', 'HS73', 'HS74'],
      ['voice_journal_entries', 'voice_journal_entries', 'HS80', 'HS81']].map(([unit, rel, r1, r2]) => [unit, { rows: [r1, r2], custom: Object.assign(async (p, c) => {
      const seen = [];
      const onReq = (r) => { const u = r.url(); if (u.includes(`/rest/v1/${rel}?`)) seen.push({ m: r.method(), u: decodeURIComponent(u).slice(0, 160) }); };
      p.on('request', onReq);
      await p.reload({ waitUntil: 'load', timeout: 45000 });
      await p.waitForTimeout(7000);
      p.off('request', onReq);
      const lists = seen.filter((x) => x.m === 'GET'), counts = seen.filter((x) => x.m === 'HEAD');
      if (lists.length) c.fail(c.l1Row, `${c.tag}: the page read ${lists.length} list(s) of ${rel} it never draws - e.g. ${lists[0].u}`);
      else c.note(c.l1Row, `${c.tag}: no list of ${rel} is read or drawn (${counts.length} count-only read(s)) - the census counted buildSystemPrompt, unreached since K1; nothing of the other ${MEMBERS.length - 1} members' ${unit} enters this page`);
      c.readings.actions = [String(lists.length)];
    }, { lensNa: 'the page draws no list of it - no name to mark or tell apart', l7Na: 'the page draws no list of it - nothing to mix when the hive switches' }) }])),
  },
  'marketplace-seller.html': {
    ready: 'body',
    units: {
      // the seller's inbox: buyers' questions about the viewer's own listings - teammates and outside buyers, each named
      // and dated
      marketplace_inquiries: { rows: ['HS238', 'HS239'], lenses: { L7: 'the inbox is the seller\'s own, for their listings in every hive - switching hives leaves it the same by design' }, item: '.inquiry-item', who: true, whoSel: '.inq-buyer', when: true,
        minPopulation: 3, minAuthors: 2,
        // marketplace-seller.html draws "Show contact" from inq.buyer_contact alone - no role in the condition
        byItem: /^Show contact$/,
        population: (_o, person) => `select count(*) from marketplace_inquiries where seller_name = '${sqlq(person.name)}'`,
        open: async (p) => { await p.evaluate(() => document.getElementById('tab-inquiries')?.click());
          await p.waitForSelector('.inquiry-item', { timeout: 15000 }).catch(() => {}); await p.waitForTimeout(500); return null; } },
      // the viewer's own provider profile - read by its own ids; a hive of thirty's other providers never enter
      service_provider: { rows: ['HS245', 'HS246'], custom: ownReadsOnly('v_service_provider_truth', (person) =>
        `select string_agg(id::text, ' ') from service_providers where auth_uid = (select auth_uid from hive_members where worker_name = '${sqlq(person.name)}' and hive_id = '${HIVE}')`) },
    },
  },
  'achievements.html': {
    ready: 'body',
    units: {
      // a provider's own standing card: the viewer's own provider profile, read by its own ids
      service_provider: { rows: ['HS1', 'HS2'], custom: ownReadsOnly('v_service_provider_truth', (person) =>
        `select string_agg(id::text, ' ') from service_providers where auth_uid = (select auth_uid from hive_members where worker_name = '${sqlq(person.name)}' and hive_id = '${HIVE}')`) },
    },
  },
  'marketplace.html': {
    ready: '.listing-card',
    units: {
      // the public marketplace: each listing names its seller and says when it was listed
      marketplace_listings_public: { rows: ['HS252', 'HS253'], lenses: { L7: 'the marketplace is the platform\'s, not one hive\'s - switching hives leaves it the same by design', L5: 'a marketplace listing names its seller on the platform, not a member of this hive - hive membership, and leaving it, is not what the card says' },  item: '.listing-card', who: true, whoSel: '.seller-link', when: true,
        minPopulation: 3, minAuthors: 2, idAttr: 'id',
        population: `select count(*) from marketplace_listings where status = 'published'` },
    },
  },
  'marketplace-seller-profile.html': {
    ready: 'body',
    units: {
      // a member's seller profile (Joel Cruz sells the plant's surplus): his listings, each dated
      marketplace_listings_public: { rows: ['HS232', 'HS233'], lenses: { L7: 'a seller profile is the person\'s, across hives - switching hives leaves it the same by design' }, item: '.listing-card', who: false,
        whoWho: 'one seller', whoWhy: "one seller's own listings - the profile says whose", when: true, minPopulation: 2, minAuthors: 0,
        population: `select count(*) from marketplace_listings where seller_name = 'Joel Cruz' and status = 'published'`,
        open: async (p) => { await p.goto(`${SEEDER}/workhive/marketplace-seller-profile.html?worker=${encodeURIComponent('Joel Cruz')}`, { waitUntil: 'load', timeout: 45000 });
          await p.waitForSelector('.listing-card', { timeout: 20000 }).catch(() => {}); await p.waitForTimeout(600); return null; } },
    },
  },
  'resume.html': {
    ready: 'body',
    units: {
      // the viewer's own resume: one document, read by their own account
      resume_documents: { rows: ['HS387', 'HS388'], custom: ownReadsOnly('resume_documents', (person) =>
        `select auth_uid::text from hive_members where worker_name = '${sqlq(person.name)}' and hive_id = '${HIVE}'`, 'auth_uid') },
      // the logbook feeds the resume's highlights only when the viewer asks it to fill them - and only their own entries
      logbook: { rows: ['HS382', 'HS383'], custom: ownReadsOnly('v_logbook_truth', (person) => `select '${sqlq(person.name)}'`, 'worker_name') },
    },
  },
  // ── the supervisor's record pages (2026-10-30): the registry filed them as founder pages, so this walk never read them.
  //    Both are the hive's supervisor's: a worker is shown "Supervisors only" and the database returns them nothing ─────
  'audit-log.html': {
    ready: 'body',
    units: {
      // the hive's own trail: who changed what, read as one timeline with the voice trail - its rows are those not said
      // "by voice"
      hive_audit_log: { rows: ['HS93', 'HS94'], item: '#feed .entry', match: '^(?![\\s\\S]*by voice)', who: true, whoSel: '.entry-actor', when: true,
        minPopulation: 10, minAuthors: 3,
        population: `select count(*) from hive_audit_log where hive_id = '${HIVE}'`,
        // the newest page is the supervisors' approvals; a supervisor reading further back presses Load more
        open: async (p) => { for (let k = 0; k < 3; k++) { const more = await p.evaluate(() => { const w = document.getElementById('audit-load-more-wrap');
          const b = w && !w.classList.contains('hidden') && w.querySelector('button'); if (!b) return false; b.click(); return true; }); if (!more) break; await p.waitForTimeout(1800); } return null; },
        readOnly: /^[▸▾]?\s*(Show|Hide) details$/,
        none: { worker: { sel: '#feed .entry', reads: `select exists (select 1 from hive_audit_log where hive_id = '${HIVE}')` } } },
      // the voice trail (ai_audit_log): every confirmed voice action, under the name of the member who spoke
      ai_audit_log: { rows: ['HS87', 'HS88'], item: '#feed .entry', match: 'by voice', who: true, whoSel: '.entry-actor', when: true,
        minPopulation: 3, minAuthors: 3,
        // the voice actions are the newest of the timeline: read from its top (a row far off screen has no text to match)
        open: async (p) => { await p.evaluate(() => window.scrollTo(0, 0)); await p.waitForTimeout(800); return null; },
        population: `select count(*) from ai_audit_log where hive_id = '${HIVE}'`,
        readOnly: /^[▸▾]?\s*(Show|Hide) details$/,
        none: { worker: { sel: '#feed .entry', reads: `select exists (select 1 from ai_audit_log where hive_id = '${HIVE}')` } } },
    },
    // a shift's voice actions, the newest of the trail: twelve members, the last two hours (an idempotent marker)
    fixture: async () => {
      const have = () => Number(psql(`select count(*) from ai_audit_log where hive_id = '${HIVE}' and payload->>'hs' = 'l1'`)) || 0;
      if (have() >= 12) return `the shift's voice actions are already in the trail (${have()})`;
      psql1(`insert into ai_audit_log (hive_id, worker_name, event, payload, source, created_at)
        select '${HIVE}', m.worker_name, (array['logbook.create', 'pm.complete', 'inventory.deduct', 'asset.lookup'])[1 + (m.n % 4)],
          jsonb_build_object('hs', 'l1'), 'voice-handler', now() - (m.n * 7 || ' minutes')::interval
        from (select worker_name, row_number() over (order by worker_name) n from hive_members where hive_id = '${HIVE}' and status = 'active' limit 12) m`);
      return have() >= 12 ? "twelve members' voice actions are in the trail" : 'the voice actions did not reach the database';
    },
  },
  'ai-quality.html': {
    ready: 'body',
    // the page draws no member's item: it reads the hive's AI calls and ratings only to total them (its reads select no
    // worker_name). What thirty members change is the totals - each is read off the screen against the table
    units: {
      ai_cost_log: { rows: ['HS12', 'HS13'], custom: aqTotal('ai_cost_log', 'AI calls (30d)',
        async (p) => p.evaluate(() => { const c = [...document.querySelectorAll('.summary-row .sum-card')].find((x) => /AI calls/.test(x.innerText));
          return c ? (c.querySelector('.sn') || {}).textContent : null; }),
        `select count(*) from ai_cost_log where hive_id = '${HIVE}' and created_at >= now() - interval '30 days'`) },
      ai_reply_feedback: { rows: ['HS18', 'HS19'], custom: aqTotal('ai_reply_feedback', 'thumbs up / down (30d)',
        async (p) => p.evaluate(() => { const h = [...document.querySelectorAll('h3')].find((x) => /Worker feedback/.test(x.textContent));
          const n = h ? [...h.parentElement.querySelectorAll('span')].filter((s) => /^\d+$/.test(s.textContent.trim())).map((s) => s.textContent.trim()) : [];
          return n.length >= 2 ? `${n[0]}/${n[1]}` : null; }),
        `select count(*) filter (where rating = 1) || '/' || count(*) filter (where rating = -1) from ai_reply_feedback where hive_id = '${HIVE}' and created_at >= now() - interval '30 days'`) },
    },
    // thirty members' use of the AI over three weeks: calls by 25 of them, ratings by 20 (an idempotent marker)
    fixture: async () => {
      const calls = () => Number(psql(`select count(*) from ai_cost_log where hive_id = '${HIVE}' and prompt_hash = 'hs-l1'`)) || 0;
      // (total_tokens is generated from the two counts)
      if (calls() < 50) psql1(`insert into ai_cost_log (fn, hive_id, worker_name, auth_uid, model, provider, prompt_tokens, output_tokens, cost_usd, latency_ms, status, prompt_hash, created_at)
        select (array['assistant', 'logbook-assist', 'voice-transcribe', 'marketplace-listing-assist'])[1 + (g % 4)], '${HIVE}', m.worker_name, m.auth_uid,
          'gemini-2.5-flash', 'gemini', 400 + g * 3, 120 + g, 0.0004 * (1 + g % 3), 600 + (g * 37) % 900,
          case when g % 17 = 0 then 'fallback' else 'success' end, 'hs-l1', now() - ((g % 20) || ' days')::interval - ((g * 13) % 600 || ' minutes')::interval
        from generate_series(1, 50) g join lateral (select worker_name, auth_uid from hive_members where hive_id = '${HIVE}' and status = 'active'
          order by worker_name offset (g % 25) limit 1) m on true`);
      const rated = () => Number(psql(`select count(*) from ai_reply_feedback where hive_id = '${HIVE}' and source = 'hs-l1'`)) || 0;
      if (rated() < 30) psql1(`insert into ai_reply_feedback (hive_id, auth_uid, worker_name, agent, source, question, rating, created_at)
        select '${HIVE}', m.auth_uid, m.worker_name, 'assistant', 'hs-l1', 'HS L1 rated answer ' || g, case when g % 4 = 0 then -1 else 1 end,
          now() - ((g % 18) || ' days')::interval
        from generate_series(1, 30) g join lateral (select worker_name, auth_uid from hive_members where hive_id = '${HIVE}' and status = 'active'
          order by worker_name offset (g % 20) limit 1) m on true`);
      return `calls ${calls()} and ratings ${rated()} by the hive's members are on the record`;
    },
  },
  // ── RETIRED admin pages: a member reaches them as a no-access gate - nothing of a hive of thirty is listed, and no
  //    control on the screen can act on a record ─────────────────────────────────────────────────────────────────────
  ...Object.fromEntries([['agentic-rag-observability.html', [['agentic_rag_traces', 'HS7', 'HS8']]],
    ['llm-observability.html', [['ai_cost_log', 'HS194', 'HS195']]],
    ['marketplace-admin.html', [['marketplace_listings', 'HS220', 'HS221'], ['marketplace_sellers', 'HS226', 'HS227']]],
    ['platform-actions.html', [['marketplace_listings', 'HS266', 'HS267'], ['marketplace_sellers', 'HS271', 'HS272'], ['platform_feedback', 'HS276', 'HS277']]]]
    .map(([pg, units]) => [pg, { ready: 'body', units: Object.fromEntries(units.map(([unit, r1, r2]) => [unit, { rows: [r1, r2], custom: retiredGate(unit) }])) }])),
};

// ── the in-page reading of one list, item by item ─────────────────────────────────────────────────────────────────
// ★A VIRTUALISED LIST IS READ BY WALKING IT. community's feed draws posts near the viewport and turns far ones back into
// stubs (.vcard-stub), expanded by an IntersectionObserver a frame later - so a one-pass querySelectorAll saw 4 of 20.
// The reader takes the next unread item, scrolls it to the centre (where a fixed bar would cover it), judges it and reads
// its menu while it is drawn, and asks the list for more ("Load more") when the viewer's own items have not appeared.
const READ_ITEMS = async ({ sel, stub, more, members, menu, me, maxMenus, need, buttons, authorSel, modal, mineIds, idAttr, idFrom, whoSel, match }) => {
  const vis = (e) => !!e && (e.checkVisibility ? e.checkVisibility({ visibilityProperty: true, opacityProperty: true }) : !!e.offsetParent);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const WHEN = /\b(just now|today|yesterday|\d+\s?(s|m|min|h|hr|d|w|mo|y)\b( ago)?|\d+ (second|minute|hour|day|week|month|year)s? ago|(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2}|\d{4}-\d{2}-\d{2})/i;
  const CTRL = 'button, a[href], [role="button"], [role="menuitem"], input, select';
  // an item without an id is known by its person or its text, never its position: a list that re-renders a row as its
  // counts arrive moved it, and a position-keyed reading counted one member twice ("45 drawn of 30")
  const keyOf = (it) => it.dataset.postId || it.id
    || (authorSel && (it.querySelector(authorSel)?.innerText || '').split(/\r?\n/)[0].replace(/\s*\((you|ikaw)\)\s*$/i, '').trim())   // a person's row: their name is unique in a hive
    || (it.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 160);
  const vw = innerWidth, vh = innerHeight;
  const seen = new Set(), out = [];
  let mores = 0, stubTries = 0, own = 0, other = 0;
  for (let guard = 0; guard < 400; guard++) {
    const _rx = match ? new RegExp(match) : null;
    // (a row far off screen has no innerText yet - its textContent carries the same words to match on)
    const all = [...document.querySelectorAll(sel)].filter(vis).filter((x) => !_rx || _rx.test(x.innerText || x.textContent || ''));
    // ★AN OFFSCREEN ROW CAN HAVE NO TEXT YET. A long list styled content-visibility:auto (whRenderRows long:true) skips
    // the rendering of rows far from the viewport, so their innerText is "" - the members list read 19 names and 11
    // blanks, and every blank shared one key. A row with nothing to key on is brought into view first.
    let idx = -1;
    for (let i = 0; i < all.length; i++) {
      let k = keyOf(all[i]);
      if (!k) { all[i].scrollIntoView({ block: 'center' }); await sleep(60); k = keyOf(all[i]); }
      if (k && !seen.has(k)) { idx = i; break; }
    }
    if (idx < 0) {
      // the next stub NOT yet read: as the walk goes down, cards above it collapse back into stubs of items already judged
      const st = stub ? [...document.querySelectorAll(stub)].find((x) => !seen.has(x.dataset.postId)) : null;
      if (st && stubTries < 6) { st.scrollIntoView({ block: 'center' }); stubTries++; await sleep(400); continue; }
      const b = more ? document.querySelector(more) : null;
      if ((menu || modal) && !own && b && vis(b) && mores < 4) { b.click(); mores++; stubTries = 0; await sleep(1800); continue; }
      break;
    }
    stubTries = 0;
    const it = all[idx];
    seen.add(keyOf(it, idx));
    it.scrollIntoView({ block: 'center' });
    await sleep(30);
    const r = it.getBoundingClientRect();
    // a wide row inside a horizontal scroller (a table on a phone) may extend past the screen - the SCROLLER must not
    let _sc = it.parentElement;
    while (_sc && _sc !== document.body && !['auto', 'scroll'].includes(getComputedStyle(_sc).overflowX)) _sc = _sc.parentElement;
    const _box = (_sc && _sc !== document.body) ? _sc.getBoundingClientRect() : r;
    const text = (it.innerText || '').replace(/\s+/g, ' ').trim();
    // nothing fixed over it: sample the item's own text-bearing children where they sit on screen
    const coveredAt = () => {
      const hits = [];
      for (const el of [...it.querySelectorAll('p, .author-link, span, button')].filter(vis).slice(0, 12)) {
      const b = el.getBoundingClientRect();
      if (b.width < 2 || b.height < 2 || b.bottom < 0 || b.top > vh) continue;
      const x = Math.min(vw - 1, Math.max(0, b.left + b.width / 2)), y = Math.min(vh - 1, Math.max(0, b.top + b.height / 2));
      const hit = document.elementFromPoint(x, y);
      if (hit && !it.contains(hit) && !hit.contains(it)) {
        let c = hit; while (c && c !== document.body && !['fixed', 'sticky'].includes(getComputedStyle(c).position)) c = c.parentElement;
        const who = (c && c !== document.body) ? c : hit;
        hits.push((who.id ? '#' + who.id : who.tagName.toLowerCase() + '.' + [...who.classList].slice(0, 2).join('.')) + ' over "' + (el.innerText || '').trim().slice(0, 24) + '"');
      }
      }
      return hits;
    };
    let covered = coveredAt();
    if (covered.length) {   // ...and where a person would scroll it to read it: the top of the screen
      it.scrollIntoView({ block: 'start' });
      await sleep(30);
      if (!coveredAt().length) covered = [];
      it.scrollIntoView({ block: 'center' });
    }
    // a count only when there is one: a control whose whole visible text is a zero
    const zero = [...it.querySelectorAll(CTRL)].filter(vis).filter((c) => !c.closest('.wh-fig') && !c.classList.contains('wh-fig'))
      .filter((c) => /^[^\p{L}\p{N}]*0$/u.test((c.innerText || '').trim()))
      .map((c) => c.getAttribute('aria-label') || c.className);
    // a line of unnamed controls: a row of the item made only of controls with nothing readable on them - an icon drawn
    // by CSS or SVG. An emoji or a count is read; the pin / globe / flag / bin row Ian saw on 2026-10-29 was four
    // controls with no glyph a person could read.
    const boxes = [];
    for (const c of [...it.querySelectorAll(CTRL)].filter(vis)) {
      const b = c.getBoundingClientRect(); if (b.width && b.height) boxes.push({ top: b.top, bottom: b.bottom, ctrl: true, named: !!(c.innerText || '').trim() });
    }
    const walker = document.createTreeWalker(it, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (!n.textContent.trim() || n.parentElement.closest(CTRL) || !vis(n.parentElement)) continue;
      const rg = document.createRange(); rg.selectNodeContents(n); const b = rg.getBoundingClientRect();
      if (b.width && b.height) boxes.push({ top: b.top, bottom: b.bottom, ctrl: false, named: true });
    }
    const lines = [];
    for (const b of boxes.sort((a, z) => a.top - z.top)) {
      const mid = (b.top + b.bottom) / 2;
      const ln = lines.find((l) => mid >= l.top - 2 && mid <= l.bottom + 2);
      if (ln) { ln.members.push(b); ln.top = Math.min(ln.top, b.top); ln.bottom = Math.max(ln.bottom, b.bottom); }
      else lines.push({ top: b.top, bottom: b.bottom, members: [b] });
    }
    const unnamedLines = lines.filter((l) => l.members.every((m) => m.ctrl && !m.named)).length;
    // names a person cannot read in full (L6's question, recorded here as a note)
    const cut = [...it.querySelectorAll('.author-link')].filter((a) => a.scrollWidth > a.clientWidth + 1).map((a) => a.innerText.trim());
    // the item's author as drawn, without the "(you)" a list adds to the viewer's own row
    const author = (it.querySelector(authorSel || '.author-link')?.innerText || '').split('\n')[0].replace(/\s*\((you|ikaw)\)\s*$/i, '').trim()
      || (modal && /(^|\s)(You|Ikaw)(\s|$)/.test(text) ? me : null) || (modal ? members.find((m) => text.includes(m)) : null) || null;
    // a list that marks the viewer's own item "You" rather than repeating their name names them all the same
    const who = whoSel ? ((it.querySelector(whoSel)?.innerText || '').trim().split(/\s*·\s*/)[0] || null)
      : members.find((m) => text.includes(m)) || (/(^|\s)(You|Ikaw|yours)(\s|$)/.test(text) || /\bby (you|ikaw)\b/i.test(text) ? me : null);   // inventory's history: "Stock after: 3 pcs · by you"
    // an item that names no one (a part on the shelf) is the viewer's by the database's account, not by its text
    const _id = it.dataset.postId || (modal ? it.dataset[modal.idAttr] : null) || (idAttr ? it.dataset[idAttr] : null)
      || (idFrom ? it.querySelector(idFrom)?.dataset.id : null) || null;
    // L6: is the name drawn whole? The element that holds it (or a box around it inside the item) may clip it - an ellipsis
    // keeps the full name in the text and shows a person only its start
    const nameCut = (() => {
      if (!who || who === me && !text.includes(me)) return false;
      const leaf = [...it.querySelectorAll('*')].filter((e) => vis(e) && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.includes(who)))[0];
      for (let n = leaf; n && n !== it.parentElement; n = n.parentElement) {
        const cs = getComputedStyle(n);
        if (['hidden', 'clip'].includes(cs.overflowX) && n.scrollWidth > n.clientWidth + 1) return true;
      }
      return false;
    })();
    const row = { fullText: text.slice(0, 400), id: _id, author, mine: mineIds ? mineIds.includes(String(_id)) : author === me, text: text.slice(0, 90), who, when: WHEN.test(text), nameCut,
      covered, zero, unnamedLines, overflow: _box.right > vw + 1 || _box.left < -1, cut, labels: null, menuShown: null, dataId: _id,
      controls: buttons ? [...it.querySelectorAll(buttons)].filter(vis).map((b) => (b.innerText || b.getAttribute('aria-label') || '').trim()) : null,
      needOk: need ? !!it.querySelector(need) : true };
    // ...or off the detail it opens to (a logbook entry's Edit and Delete live in its modal)
    if (modal && ((row.mine && own < maxMenus) || (!row.mine && other < maxMenus))) {
      const id = it.dataset[modal.idAttr];
      row.dataId = id || row.dataId;
      if (id && typeof window[modal.open] === 'function') {
        await window[modal.open](id); await sleep(500);
        row.labels = [...document.querySelectorAll(modal.sel)].filter(vis).map((b) => (b.innerText || b.getAttribute('aria-label') || '').trim());
        (0, eval)(modal.close); await sleep(150);
        row.mine ? own++ : other++;
      }
    }
    // the actions this item offers its viewer, read off its own menu while it is drawn (opened, read, closed)
    const btn = menu ? it.querySelector(menu) : null;
    if (btn && ((row.mine && own < maxMenus) || (!row.mine && other < maxMenus))) {
      btn.click(); await sleep(80);
      const m = document.getElementById(btn.getAttribute('aria-controls'));
      row.labels = [...(m?.querySelectorAll('[role="menuitem"]') || [])].map((x) => x.innerText.trim());
      // the menu that opened must be one the person can SEE - a duplicate id opens a hidden copy elsewhere on the page
      row.menuShown = !!m && vis(m) && it.contains(m);
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      row.mine ? own++ : other++;
    }
    out.push(row);
  }
  scrollTo(0, 0);
  return out;
};

const findings = [];
const fail = (row, msg) => findings.push({ row, ok: false, msg });
const note = (row, msg) => findings.push({ row, ok: true, msg });
const readings = {};

// the second hive (L7): planted before the walk, every row of it removed after (triggers off both ways)
const l7Plant = () => psql1(`set session_replication_role = replica;
  insert into hives (id, name, invite_code, created_by) values ('${L7_HIVE}', '${L7_MARK}', 'HSL7HV', 'Ernesto Villareal') on conflict (id) do nothing;
  insert into hive_members (hive_id, worker_name, role, status, auth_uid)
    select '${L7_HIVE}', worker_name, role, 'active', auth_uid from hive_members where hive_id = '${HIVE}' and worker_name in ('Joel Cruz', 'Ernesto Villareal')
    on conflict do nothing;
  insert into logbook (id, hive_id, worker_name, date, machine, problem, status, created_at)
    values ('hs-l7-logbook', '${L7_HIVE}', 'Joel Cruz', now(), '${L7_MARK} machine', '${L7_MARK} fault', 'Open', now()) on conflict (id) do nothing;
  insert into community_posts (hive_id, author_name, content) values ('${L7_HIVE}', 'Joel Cruz', '${L7_MARK} post');
  insert into inventory_items (id, hive_id, worker_name, part_name, part_number, qty_on_hand, status)
    values ('hs-l7-part', '${L7_HIVE}', 'Joel Cruz', '${L7_MARK} part', 'HSL7-001', 0, 'approved') on conflict (id) do nothing;
  insert into projects (hive_id, worker_name, project_code, name, project_type, status, owner_name)
    values ('${L7_HIVE}', 'Ernesto Villareal', 'CON-2026-971', '${L7_MARK} project', 'contractor', 'active', 'Ernesto Villareal');
  insert into pm_assets (hive_id, worker_name, asset_name, category) values ('${L7_HIVE}', 'Ernesto Villareal', '${L7_MARK} asset', 'Pump');
  insert into asset_nodes (hive_id, tag, name, status) values ('${L7_HIVE}', 'HSL7-M1', '${L7_MARK} machine', 'approved');
  insert into community_xp (worker_name, hive_id, xp_total) values ('Joel Cruz', '${L7_HIVE}', 777) on conflict do nothing;
  insert into hive_members (hive_id, worker_name, role, status, auth_uid)
    select '${L7_HIVE}', 'Efren Dizon', 'worker', 'active', auth_uid from hive_members
     where worker_name = 'Efren Dizon' and hive_id not in ('${HIVE}', '${L7_HIVE}') and auth_uid is not null limit 1
    on conflict do nothing;
  insert into hive_audit_log (hive_id, actor, action, target_type, target_name) values ('${L7_HIVE}', 'Ernesto Villareal', 'add_project', 'projects', '${L7_MARK} project');`);
const l7Clear = () => psql1(`set session_replication_role = replica;
  delete from hive_audit_log where hive_id = '${L7_HIVE}'; delete from pm_assets where hive_id = '${L7_HIVE}'; delete from asset_nodes where hive_id = '${L7_HIVE}'; delete from community_xp where hive_id = '${L7_HIVE}'; delete from projects where hive_id = '${L7_HIVE}';
  delete from inventory_items where hive_id = '${L7_HIVE}'; delete from community_posts where hive_id = '${L7_HIVE}'; delete from logbook where hive_id = '${L7_HIVE}';
  delete from hive_members where hive_id = '${L7_HIVE}'; delete from hive_quotas where hive_id = '${L7_HIVE}'; delete from hives where id = '${L7_HIVE}';`);
// L5's subject: the last day of work of a member who has since left (Rodel Ignacio, deactivated), laid on the subjects
// these lists read - the busiest machine, PM asset and project - so each list's window holds an item of his. Written
// triggers-off (no XP, no trail rows of its own), marked hs-l5, laid once and kept as part of the hive's history.
const L5_GONE = [...FORMER][0];
if (L5_GONE && psql(`select count(*) from logbook where id = 'hs-l5-logbook'`) === '0') {
  const scope = psql(`select id from pm_scope_items where asset_id = '${PM_BUSY}' order by id limit 1`);
  psql1(`set session_replication_role = replica;
    insert into logbook (id, hive_id, worker_name, auth_uid, date, machine, asset_node_id, problem, status, maintenance_type, category, created_at)
      select 'hs-l5-logbook', '${HIVE}', '${L5_GONE}', (select auth_uid from hive_members where hive_id = '${HIVE}' and worker_name = '${L5_GONE}'),
        now() - interval '1 day', coalesce(n.name, n.tag), n.id, 'Seal weep at the gland - logged the day before he left', 'Open', 'Breakdown / Corrective', 'Mechanical', now() - interval '1 day'
      from asset_nodes n where n.id = '${NODE_BUSY}';
    insert into pm_completions (asset_id, scope_item_id, hive_id, worker_name, auth_uid, status, notes, completed_at)
      values ('${PM_BUSY}', ${scope ? `'${scope}'` : 'null'}, '${HIVE}', '${L5_GONE}', (select auth_uid from hive_members where hive_id = '${HIVE}' and worker_name = '${L5_GONE}'), 'done', 'hs-l5 the day before he left', now() - interval '1 day');
    insert into project_progress_logs (project_id, hive_id, reported_by, notes, created_at)
      values ('${PROJ_BUSY}', '${HIVE}', '${L5_GONE}', 'hs-l5 his last progress report', now() - interval '1 day');
    insert into project_change_orders (project_id, hive_id, co_number, title, scope_change, cost_impact_php, schedule_impact_days, status, requested_by, requested_at, created_at)
      values ('${PROJ_BUSY}', '${HIVE}', 'CO-L5', 'hs-l5 his last change request', 'Replace the gland packing with a mechanical seal', 18500, 2, 'pending', '${L5_GONE}', now() - interval '1 day', now() - interval '1 day');
    insert into project_roles (project_id, hive_id, worker_name, role, assigned_by, notes, assigned_at)
      values ('${PROJ_BUSY}', '${HIVE}', '${L5_GONE}', 'reviewer', 'Ernesto Villareal', 'hs-l5', now() - interval '20 days');
    insert into rcm_fmea_modes (hive_id, asset_id, function_text, failure_mode, severity, occurrence, detection, created_by, created_at)
      values ('${HIVE}', '${NODE_PENDING_FMEA}', 'hs-l5 contain the process fluid', 'Gland packing leak (hs-l5)', 6, 5, 4, '${L5_GONE}', now() - interval '1 day');
    insert into hive_audit_log (hive_id, actor, action, target_type, target_name, meta, created_at)
      values ('${HIVE}', '${L5_GONE}', 'register_asset', 'assets', 'BRM-P-102', '{"hs": "l5"}', now() - interval '1 day');
    insert into ai_audit_log (hive_id, worker_name, event, payload, source, created_at)
      values ('${HIVE}', '${L5_GONE}', 'logbook.create', '{"hs": "l5"}', 'voice-handler', now() - interval '30 minutes');`);
  console.log(`L5: ${L5_GONE}'s last day of work is laid on the walk's subjects (${psql(`select count(*) from logbook where id = 'hs-l5-logbook'`)} logbook entry)`);
}
// ...and what he left open or under review, inside the windows the remaining lists read: a reply on the longest
// thread, a post a teammate reported, a task and a project he still owns, a trail entry from his last morning
if (L5_GONE && psql(`select count(*) from project_items where title = 'hs-l5 his open task'`) === '0') {
  const longest = psql(`select post_id from community_replies where hive_id = '${HIVE}' group by post_id order by count(*) desc limit 1`);
  const uid = psql(`select auth_uid from hive_members where hive_id = '${HIVE}' and worker_name = '${L5_GONE}'`);
  psql1(`set session_replication_role = replica;
    insert into community_replies (post_id, hive_id, author_name, content, created_at)
      values ('${longest}', '${HIVE}', '${L5_GONE}', 'hs-l5 Checked it on my last shift - the coupling guard was loose.', now() - interval '1 day');
    insert into community_posts (id, hive_id, author_name, content, category, flagged, created_at)
      values ('5a5a5a5a-5a5a-4a5a-8a5a-5a5a5a5a5a5a', '${HIVE}', '${L5_GONE}', 'hs-l5 Bypassed the low-oil trip to finish the run.', 'general', true, now() - interval '20 hours');
    insert into hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta, created_at)
      values ('${HIVE}', 'Joel Cruz', 'report_post', 'community_posts', '5a5a5a5a-5a5a-4a5a-8a5a-5a5a5a5a5a5a', 'Bypassed the low-oil trip... (by ${L5_GONE})',
        '{"page": "community", "author": "${L5_GONE}", "reason": "unsafe", "details": "Bypassing a trip is not a fix.", "target_id": "5a5a5a5a-5a5a-4a5a-8a5a-5a5a5a5a5a5a", "hs": "l5"}', now() - interval '19 hours');
    insert into project_items (project_id, hive_id, title, status, owner_name, sort_order, planned_start, planned_end)
      values ('${PROJ_BUSY}', '${HIVE}', 'hs-l5 his open task', 'pending', '${L5_GONE}', 1, current_date - 2, current_date + 5);
    insert into projects (hive_id, worker_name, project_code, name, project_type, status, owner_name, start_date, end_date)
      values ('${HIVE}', '${L5_GONE}', 'CON-2026-970', 'hs-l5 Pump seal upgrade', 'contractor', 'active', '${L5_GONE}', current_date - 14, current_date + 20);
    insert into hive_audit_log (hive_id, actor, action, target_type, target_name, meta, created_at)
      values ('${HIVE}', '${L5_GONE}', 'edit_asset', 'assets', 'BRM-P-102', '{"hs": "l5"}', now() - interval '3 hours');`);
  console.log(`L5: what ${L5_GONE} left open is laid in the remaining windows (${psql(`select count(*) from project_items where title = 'hs-l5 his open task'`)} task)`);
}
// ...a machine he submitted for approval the week before he left - still waiting in the supervisors' queue
if (L5_GONE && psql(`select count(*) from asset_nodes where tag = 'HSL5-P-210'`) === '0') {
  psql1(`set session_replication_role = replica;
    insert into asset_nodes (hive_id, worker_name, auth_uid, submitted_by, tag, name, level, status, created_at)
      values ('${HIVE}', '${L5_GONE}', (select auth_uid from hive_members where hive_id = '${HIVE}' and worker_name = '${L5_GONE}'), '${L5_GONE}',
        'HSL5-P-210', 'Condensate return pump (hs-l5)', 'equipment', 'pending', now() - interval '6 days');`);
}
// ...a question he asked a teammate selling surplus, and a call made on his API key in his last week
if (L5_GONE && psql(`select count(*) from marketplace_inquiries where message = 'hs-l5 Is the spare seal kit still available?'`) === '0') {
  psql1(`set session_replication_role = replica;
    insert into marketplace_inquiries (listing_id, hive_id, seller_name, buyer_name, buyer_contact, message, created_at)
      select id, hive_id, seller_name, '${L5_GONE}', '0917 000 0000', 'hs-l5 Is the spare seal kit still available?', now() - interval '1 day'
      from marketplace_listings where seller_name = 'Joel Cruz' and status = 'published' order by created_at limit 1;
    insert into gateway_audit_log (hive_id, worker_name, auth_uid, route, request_id, method, status_code, latency_ms, created_at)
      values ('${HIVE}', '${L5_GONE}', (select auth_uid from hive_members where hive_id = '${HIVE}' and worker_name = '${L5_GONE}'),
        '/api/v1/readings', 'hs-l5-call', 'POST', 200, 120, now() - interval '150 minutes');`);
}
// ...the PM program he set up for that pump while he stood in as supervisor (a program is a supervisor's write)
if (L5_GONE && psql(`select count(*) from pm_assets where tag_id = 'HSL5-P-210'`) === '0') {
  psql1(`set session_replication_role = replica;
    insert into pm_assets (hive_id, worker_name, auth_uid, asset_name, tag_id, category, criticality, created_at)
      select '${HIVE}', '${L5_GONE}', auth_uid, 'Condensate return pump (hs-l5)', 'HSL5-P-210', 'Pump', 'Major', now() - interval '40 days'
      from hive_members where hive_id = '${HIVE}' and worker_name = '${L5_GONE}';`);
}
// ...and he was the hive's top community contributor - the leaderboard keeps the XP he earned and his place (HS117)
if (L5_GONE) psql1(`set session_replication_role = replica;
  update community_xp set xp_total = greatest(xp_total, 655) where hive_id = '${HIVE}' and worker_name = '${L5_GONE}';`);
// ...and a calculation he ran (project-manager's link picker offers a hive's calculations by who ran them)
if (L5_GONE && psql(`select count(*) from engineering_calcs where project_name = 'hs-l5 P-102 seal flush line'`) === '0') {
  psql1(`set session_replication_role = replica;
    insert into engineering_calcs (hive_id, worker_name, calc_type, project_name, discipline, created_at)
      values ('${HIVE}', '${L5_GONE}', 'Pipe Sizing', 'hs-l5 P-102 seal flush line', 'Mechanical', now() - interval '1 day');`);
}
if (L7) { l7Clear(); l7Plant();
  // the walk's two people belong to both hives; Efren belongs to the second one only (what a leak would show)
  const n = psql(`select count(*) from hive_members o where o.hive_id = '${L7_HIVE}' and exists (select 1 from hive_members h where h.hive_id = '${HIVE}' and h.worker_name = o.worker_name)`);
  const only = psql(`select count(*) from hive_members o where o.hive_id = '${L7_HIVE}' and not exists (select 1 from hive_members h where h.hive_id = '${HIVE}' and h.worker_name = o.worker_name)`);
  console.log(`L7: the second hive is planted - ${n} of the walk's people are members of both, ${only} member(s) of it alone, with its marked items`);
  if (n !== '2' || only !== '1') { l7Clear(); throw new Error('L7: the second hive did not take'); } }
const browser = await chromium.launch();
try {
  for (const [page, spec] of Object.entries(SPECS)) {
    if (ONLY.length && !ONLY.includes(page)) continue;
    if (spec.fixture) console.log(`fixture ${page}: ${await spec.fixture(browser)}`);
    for (const [roleKey, person] of Object.entries(PEOPLE)) {
      for (const vp of VIEWPORTS) {
        const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1 });
        if (!(await signIn(ctx, person))) { fail('*', `${person.name} could not sign in - no reading is possible`); await ctx.close(); continue; }
        const p = await ctx.newPage();
        await p.goto(`${SEEDER}/workhive/${page}`, { waitUntil: 'load', timeout: 45000 });
        await p.waitForSelector(spec.ready, { timeout: 30000 }).catch(() => {});
        await p.waitForTimeout(2500);
        const hiveShown = await p.evaluate(() => localStorage.getItem('wh_active_hive_id'));
        if (hiveShown !== HIVE) fail('*', `${page} as ${person.name}: the page is not on the full hive (${hiveShown})`);
        for (const [unit, u] of Object.entries(spec.units)) {
          const [l1Row, l2Row] = u.rows;
          // a relation this role reads none of, by design: nothing of it is drawn, and the database returns none of it
          if (u.none && u.none[roleKey]) {
            if (u.open) await u.open(p);   // the place it would be drawn is opened first - an unopened pane draws nothing anyway
            const n = await p.evaluate((sel) => document.querySelectorAll(sel).length, u.none[roleKey].sel);
            const reads = as(person, typeof u.none[roleKey].reads === 'function' ? u.none[roleKey].reads() : u.none[roleKey].reads);
            if (n) fail(l1Row, `${page} ${unit} as ${roleKey} at ${vp.name}: ${n} item(s) drawn of a relation this role does not read`);
            if (reads !== 'f') fail(l1Row, `${page} ${unit} as ${roleKey}: the database ${reads === 't' ? 'returns rows of it' : 'gave no answer'} - the page hiding it is not the boundary`);
            if (!n && reads === 'f') note(l1Row, `${page} ${unit} as ${roleKey} at ${vp.name}: none drawn, and the database returns none to ${person.name} - a ${roleKey} does not read it`);
            continue;
          }
          // a unit that is not a list (one member's figure on their card) declares its own reading
          if (u.custom) {
            const readingsOf = (readings[`${page}|${unit}|${roleKey}|${vp.name}`] = { drawn: 1, population: 1 });
            await u.custom(p, { person, roleKey, vp, l1Row, l2Row, fail, note, readings: readingsOf, tag: `${page} ${unit} as ${roleKey} at ${vp.name}` });
            // L5 / L6 on a unit that is not a list of members' items: its own declaration, or why the lens has nothing to read
            for (const k of (L7 ? ['L5', 'L6', 'L7'] : ['L5', 'L6'])) {
              const r = LENS(l1Row, k); if (!r) continue;
              const why = (u.lenses && u.lenses[k]) || (k === 'L7'
                ? (u.custom.ownReads ? `the page reads only ${person.name}'s own, by account - no hive's list to mix` : u.custom.l7Na)
                : (u.custom.ownReads ? `the page reads only ${person.name}'s own - no other member's item, departed or alike-named, enters it` : u.custom.lensNa));
              if (why) note(r, `${page} ${unit} as ${roleKey} at ${vp.name}: ${why}`);
            }
            continue;
          }
          const opened = u.open ? await u.open(p) : null;
          const items = await p.evaluate(READ_ITEMS, { sel: u.item, stub: u.stub || null, more: u.more || null, members: MEMBERS,
            menu: u.menu || null, me: person.name, maxMenus: MAX_MENUS, need: u.need || null, buttons: u.buttons || null,
            authorSel: u.authorSel || null, modal: u.modal || null,
            mineIds: u.mineIds ? psql(u.mineIds(person)).split(/\s+/).filter(Boolean) : null,
            idAttr: u.idAttr || null, idFrom: u.idFrom || null, whoSel: u.whoSel || null, match: u.match || null });
          const population = Number(psql(typeof u.population === 'function' ? u.population(opened, person) : u.population)) || 0;
          const key = `${page}|${unit}|${roleKey}|${vp.name}`;
          const authors = new Set(items.map((i) => i.who).filter(Boolean));
          readings[key] = { drawn: items.length, population, authors: authors.size };
          const tag = `${page} ${unit} as ${roleKey} at ${vp.name}`;
          if (u.ownOnly) {
            // a list of the viewer's OWN items: a hive of thirty must add none of the others' - exactly theirs, all of it
            if (items.length !== Math.min(population, u.cap || population)) fail(l1Row, `${tag}: drew ${items.length} item(s); ${person.name} has ${population} - a list of one's own work shows exactly that`);
            else note(l1Row, `${tag}: ${items.length} of ${person.name}'s own ${population} - none of the other ${MEMBERS.length - 1} members' work enters it`);
          } else if (!items.length || population < (u.minPopulation ?? (opened ? 3 : 10))) fail(l1Row, `${tag}: drew ${items.length} item(s) from a population of ${population} - nothing a full hive's list can be judged on`);
          else if (u.who !== false && authors.size < (u.minAuthors ?? 3)) fail(l1Row, `${tag}: ${items.length} items name only ${authors.size} member(s) - not a thirty-member list`);
          for (const [i, it] of items.entries()) {
            const where = `${tag} item ${i + 1} "${it.text.slice(0, 40)}"`;
            if (u.who && !u.ownOnly && !it.who) fail(l1Row, `${where}: does not say who made it`);
            if (u.ownOnly && it.who && it.who !== person.name) fail(l1Row, `${where}: names ${it.who} - another member's work in ${person.name}'s own list`);
            if (u.when && !it.when) fail(l1Row, `${where}: does not say when`);
            if (it.covered.length) fail(l1Row, `${where}: covered - ${it.covered.join('; ')}`);
            if (it.zero.length) fail(l1Row, `${where}: a count of 0 shown on ${it.zero.join(', ')}`);
            if (it.unnamedLines) fail(l1Row, `${where}: ${it.unnamedLines} line(s) of unnamed controls`);
            if (it.overflow) fail(l1Row, `${where}: runs past the screen's edge`);
            if (!it.needOk) fail(l1Row, `${where}: does not say ${u.needWhy}`);
            if (it.menuShown === false) fail(l2Row || l1Row, `${where}: its actions button opened nothing the person can see`);
            if (it.cut.length) note(l1Row, `${where}: name shown cut - ${it.cut.join(', ')} (L6, thirty names)`);
          }
          if (u.distinctIds) {
            const ids = items.map((i) => i.dataId).filter(Boolean), dup = ids.length - new Set(ids).size;
            if (dup) fail(l1Row, `${tag}: ${dup} item(s) share a key with another - ${u.distinctWhy}`);
            else note(l1Row, `${tag}: ${ids.length} item(s), ${ids.length} distinct keys - ${u.distinctWhy.replace(/^.* - /, '')}`);
          }
          // L6, thirty names: every member the list names is drawn whole, a near-twin never cut to the start they share
          const l6Row = LENS(l1Row, 'L6');
          if (l6Row && u.lenses && u.lenses.L6) note(l6Row, `${tag}: ${u.lenses.L6}`);
          else if (l6Row && u.who !== false && items.length) {
            const twinOf = (n) => (TWINS.find((pair) => pair.includes(n)) || []).find((x) => x !== n);
            const cutNames = [...new Set(items.filter((x) => x.nameCut && x.who).map((x) => x.who))];
            for (const n of cutNames) {
              const tw = twinOf(n);
              if (tw) fail(l6Row, `${tag}: ${n}'s name is drawn cut - it cannot be told from ${tw}`);
              else note(l6Row, `${tag}: ${n}'s name is drawn cut, though no other member shares its start`);
            }
            const pairs = TWINS.filter(([a, b]) => authors.has(a) && authors.has(b));
            note(l6Row, `${tag}: ${authors.size} member(s) named${cutNames.length ? '' : ', every name drawn whole'}`
              + (pairs.length ? `; near-twins told apart: ${pairs.map((pair) => pair.join(' / ')).join(', ')}` : '')
              + (u.l2 && u.l2.ownership ? "; 'mine' (a member's own items' actions) is decided by the account - L2 replays each as that person" : ''));
          } else if (l6Row && u.who === false) note(l6Row, `${tag}: the list names no member (${u.whoWhy || 'not a person\'s item'}) - no name to tell apart`);
          // L7, a member of two hives (--l7): the database lets this person read both hives, so the list's own hive filter
          // is all that keeps the other hive's items off it
          const l7Row = LENS(l1Row, 'L7');
          if (L7 && l7Row && u.lenses && u.lenses.L7) note(l7Row, `${tag}: ${u.lenses.L7}`);
          else if (L7 && l7Row && items.length) {
            const leaked = items.filter((x) => (x.fullText || '').includes(L7_MARK));
            if (leaked.length) fail(l7Row, `${tag}: ${leaked.length} item(s) of ${person.name}'s OTHER hive on this hive's list - "${leaked[0].text}"`);
            else note(l7Row, `${tag}: ${person.name} is an active member of two hives and may read both - the list holds only this hive's ${items.length} item(s), none of the other's`);
            // ...and switching hives replaces the list whole: the active hive set to the other one (as the hive switcher
            // does) and the page reloaded, the list must hold none of THIS hive's items - then switched back
            const setHive = async (h) => { await p.evaluate((x) => { localStorage.setItem('wh_active_hive_id', x); localStorage.setItem('wh_hive_id', x); }, h);
              // the page's own address, not a reload: a reload kept ?thread=<id> and re-opened the thread over the next list
              await p.goto(`${SEEDER}/workhive/${page}`, { waitUntil: 'load', timeout: 45000 }); await p.waitForTimeout(3000); };
            await setHive(L7_HIVE);
            const onHive = await p.evaluate(() => localStorage.getItem('wh_active_hive_id'));
            if (u.open && !u.l7ById) await u.open(p).catch(() => null);
            const other = await p.evaluate(READ_ITEMS, { sel: u.item, stub: u.stub || null, more: null, members: MEMBERS, menu: null, me: person.name,
              maxMenus: 0, need: null, buttons: null, authorSel: u.authorSel || null, modal: null, mineIds: null, idAttr: u.idAttr || null,
              idFrom: u.idFrom || null, whoSel: u.whoSel || null, match: u.match || null });
            // an item of the other hive carries its mark - or, on a roster, is one of its members (the walk's two people
            // belong to both hives, so both rosters rightly name them)
            // the second hive's roster is read from the database: the walk's two people AND the member of it alone (Efren)
            const otherRoster = unit === 'hive_members'
              ? psql(`select string_agg(worker_name, '|') from hive_members where hive_id = '${L7_HIVE}'`).split('|').filter(Boolean) : [];
            const ofOther = (x) => (x.fullText || '').includes(L7_MARK)
              || (unit === 'hive_members' && otherRoster.some((n) => (x.fullText || '').includes(n)));
            const mixed = other.filter((x) => !ofOther(x));
            if (onHive !== L7_HIVE) fail(l7Row, `${tag}: switching to the other hive did not hold - the page put ${onHive} back`);
            else if (mixed.length) fail(l7Row, `${tag}: switched to the other hive, the list still holds ${mixed.length} item(s) of this one - "${mixed[0].text}"`);
            else note(l7Row, `${tag}: switched to the other hive, the list holds ${other.length} item(s), all of that hive's - replaced whole, never a mix`);
            await setHive(HIVE);
          }
          // L5, a member who has left: an item they made still names them, and says they have left
          const l5Row = LENS(l1Row, 'L5');
          if (l5Row && u.lenses && u.lenses.L5) note(l5Row, `${tag}: ${u.lenses.L5}`);
          else if (l5Row && u.ownOnly) note(l5Row, `${tag}: a list of ${person.name}'s own work - no other member's item, departed or not, enters it`);
          else if (l5Row && u.who !== false && items.length) {
            // every item that NAMES a member who has left is judged - as its author, owner, assignee or actor - not only
            // the one name the reader took as "who" (a role pill names its holder and who assigned it)
            // (case-blind: innerText carries a style's text-transform - the audit log draws its actors in capitals)
            const lc = (x) => (x.fullText || '').toLowerCase();
            const named = (x) => [...FORMER].filter((n) => lc(x).includes(n.toLowerCase()));
            const gone = items.filter((x) => named(x).length).map((x) => Object.assign({}, x, { who: named(x)[0] }));
            const bare = gone.filter((x) => named(x).some((n) => !lc(x).includes(`${n} (former member)`.toLowerCase())));
            if (bare.length) fail(l5Row, `${tag}: ${bare.length} item(s) by ${[...new Set(bare.map((x) => x.who))].join(', ')}, who left the hive, name them as if still in it`);
            else if (gone.length) note(l5Row, `${tag}: ${gone.length} item(s) by ${[...new Set(gone.map((x) => x.who))].join(', ')}, who left the hive - each says "(former member)"`);
            else fail(l5Row, `${tag}: no item by a member who has left is in the list as read - nothing to judge (a departed member's item is owed in its window; read e.g. "${(items[0].fullText || '').slice(0, 70)}", departed: ${[...FORMER].join(', ') || 'none'})`);
          } else if (l5Row && u.who === false) note(l5Row, `${tag}: the list names no member (${u.whoWhy || 'not a person\'s item'}) - no one's departure to say`);
          if (u.when === false) note(l1Row, `${tag}: "when" does not apply - ${u.whenWhy}`);
          if (u.who === false) note(l1Row, `${tag}: "who" does not apply - ${u.whoWhy}`);
          if (!u.ownOnly) note(l1Row, `${tag}: ${items.length} drawn of ${population}, by ${authors.size} members`);

          // L2: the actions each item offers, against what the database lets this person write on it
          if (u.l2 && vp.name === 'phone-390') {
            const L = u.l2;
            let own = 0, other = 0, flipped = false;
            for (const it of items) {
              const labels = it.labels ?? it.controls;
              if (!labels) continue;
              const mine = it.mine;
              if ((mine && own >= MAX_MENUS) || (!mine && other >= MAX_MENUS)) continue;
              const id = L.id(it);
              if (!id) { fail(l2Row, `${tag}: item "${it.text.slice(0, 30)}" - no row found to replay its actions against`); continue; }
              mine ? own++ : other++;
              const whose = mine ? 'own' : (it.author || 'another member') + "'s";
              const offered = new Set(labels.map(L.label).filter(Boolean));
              for (const lab of labels) if (!L.label(lab) && !(L.ignore && L.ignore(lab))) fail(l2Row, `${tag}: ${whose} item offers "${lab}", which this prover cannot map to a write`);
              const allowed = {};
              for (const act of Object.keys(L.writes || {})) {
                if (L.skip && L.skip(act, mine)) continue;
                allowed[act] = as(person, L.writes[act](id)) === 't';
              }
              for (const act of Object.keys(L.rules || {})) {
                if (L.skip && L.skip(act, mine)) continue;
                allowed[act] = !!L.rules[act](person, it);
              }
              if (TEETH && !flipped) { const k = Object.keys(allowed)[0]; if (k) { allowed[k] = !allowed[k]; flipped = true; } }
              for (const act of offered) {
                if (!allowed[act]) fail(l2Row, `${tag}: ${whose} item offers ${act}, and the database refuses it`);
              }
              for (const act of L.candidates || []) {
                if (L.skip && L.skip(act, mine)) continue;
                if (L.applies && !L.applies(it)) continue;
                if (allowed[act] && !offered.has(act)) fail(l2Row, `${tag}: ${whose} item - the database lets a ${roleKey} ${act} it, and the item does not offer it`);
              }
            }
            note(l2Row, `${tag}: ${own} own and ${other} others' items' actions read against the database`);
            if (L.ownership && (!own || !other)) fail(l2Row, `${tag}: the actions read covered ${own} own and ${other} others' items - both ownerships are needed`);
            if (!other) fail(l2Row, `${tag}: no other member's item was read - the role boundary is not shown`);
          }
          if (!u.l2 && l2Row) {
            // a list with no per-item actions: what each role is offered on an item must be the same
            const labels = await p.evaluate(({ sel, names }) => [...new Set([...document.querySelectorAll(sel + ' button, ' + sel + ' a[href]')]
              // a control far off screen has no innerText yet (content-visibility) - its textContent is the same words
              .map((b) => (b.getAttribute('aria-label') || b.innerText || b.textContent || '').replace(/\s+/g, ' ').replace(/[A-Z][a-z]+( [A-Z][a-z.]+)*'s/g, "<member>'s")
              // a relative time is the clock, not an offer: "updated 34m ago" read a minute apart is the same link
              .replace(/\b(just now|\d+\s?(s|m|min|h|hr|d|w|mo|y)( ago)?|\d+ (second|minute|hour|day|week|month|year)s? ago)\b/gi, '<when>')
              // a person named in a label ("Close this inquiry from Hazel Torres") is the item, not the offer
              .trim()).map((t) => names.reduce((acc, n) => acc.split(n).join('<someone>'), t)
                .replace(/\bfrom [A-Z][\w.'-]*( [A-Z][\w.'-]*)*( \(outside buyer\))?/g, 'from <someone>')))], { sel: u.item, names: MEMBERS });
            readings[key].actions = labels;
          }
          if (u.close) await u.close(p);
        }
        await ctx.close();
      }
    }
    // L2 for item lists with no menu: a supervisor and a worker are offered the same actions on them
    for (const [unit, u] of Object.entries(spec.units)) {
      if (u.l2 || !u.rows[1]) continue;
      const w = readings[`${page}|${unit}|worker|phone-390`]?.actions || [], s = readings[`${page}|${unit}|supervisor|phone-390`]?.actions || [];
      // an offer the ITEM's own data draws (u.byItem - "Show contact" exists only when the buyer left one) is the item,
      // not the reader's role: two people's windows hold different items, so it is set aside before the roles are compared
      const roleOffers = (a) => (u.byItem ? a.filter((t) => !u.byItem.test(String(t).trim())) : a);
      const ws = JSON.stringify([...roleOffers(w)].sort()), ss = JSON.stringify([...roleOffers(s)].sort());
      if (unit === 'community_replies') continue;   // replies differ by design (Mark as answer) - judged below
      if (u.custom && u.custom.ownReads) { note(u.rows[1], `${page} ${unit}: each role reads only its own ${unit} - two people's own reads are not one list to compare`); continue; }
      const drawnW = readings[`${page}|${unit}|worker|phone-390`]?.drawn || 0, drawnS = readings[`${page}|${unit}|supervisor|phone-390`]?.drawn || 0;
      if (!u.none && (!drawnW || !drawnS)) { fail(u.rows[1], `${page} ${unit}: ${drawnW} item(s) read as the worker and ${drawnS} as the supervisor - the roles' offers cannot be compared on nothing`); continue; }
      if (u.none && !drawnS) { fail(u.rows[1], `${page} ${unit}: the supervisor's list drew nothing - its actions cannot be read`); continue; }
      // a list a worker is shown none of: there is nothing to compare - the supervisor's offers must each be a read-only
      // disclosure (u.readOnly), never a write the worker is merely kept from
      if (u.none && u.none.worker && u.readOnly) {
        const writes = s.filter((t) => t && !u.readOnly.test(t.trim()));
        if (writes.length) fail(u.rows[1], `${page} ${unit}: a supervisor's item offers ${JSON.stringify(writes)} - not a read-only control`);
        else note(u.rows[1], `${page} ${unit}: a worker is shown none of it; a supervisor's item offers only ${JSON.stringify([...new Set(s.filter(Boolean))])} - read-only, no write`);
        continue;
      }
      if (ws !== ss) fail(u.rows[1], `${page} ${unit}: a worker is offered ${ws} and a supervisor ${ss} - a list with no role actions must offer both the same`);
      else note(u.rows[1], `${page} ${unit}: both roles are offered ${ws}`);
    }
  }

  // L2 for replies: "Mark as answer" belongs to the person who asked and to supervisors, and the database agrees
  if (!ONLY.length || ONLY.includes('community.html')) {
    const other = psql(`select r.id from community_replies r join community_posts p on p.id = r.post_id where r.hive_id = '${HIVE}' and p.author_name not in ('Joel Cruz') limit 1`);
    const mine = psql(`select r.id from community_replies r join community_posts p on p.id = r.post_id where r.hive_id = '${HIVE}' and p.author_name = 'Joel Cruz' limit 1`);
    // the RPC returns void and raises on a refusal: reaching the next statement IS the permission
    const mark = (id) => `select public.set_community_best_answer('${id}', true); select true`;
    const wOther = as(PEOPLE.worker, mark(other)), wMine = mine ? as(PEOPLE.worker, mark(mine)) : 'n/a', sOther = as(PEOPLE.supervisor, mark(other));
    if (wOther === 't') fail('HS107', 'a worker can mark the best answer on another member\'s thread through the database');
    if (sOther !== 't') fail('HS107', `a supervisor cannot mark the best answer on a member's thread (${sOther || 'error'}) though the page offers it`);
    if (mine && wMine !== 't') fail('HS107', `a worker cannot mark the best answer on their OWN thread (${wMine || 'error'}) though the page offers it`);
    note('HS107', `best answer: worker on another's thread ${wOther || 'refused'}, on their own ${wMine}, supervisor ${sOther}`);
  }
} finally {
  await browser.close();
  if (L7) { l7Clear(); console.log(`L7: the second hive is removed (${psql(`select count(*) from hive_members where hive_id = '${L7_HIVE}'`)} memberships left)`); }
  // what the fixtures' rows PAID goes with them (the harness psql is one-line -c, so this file goes in on stdin)
  (await import('node:child_process')).spawnSync('docker', ['exec', '-i', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-At', '-v', 'ON_ERROR_STOP=1'],
    { input: readFileSync('tools/hs_paid_residue.sql', 'utf8'), encoding: 'utf8' });
}

const rows = {};
for (const f of findings) { rows[f.row] = rows[f.row] || { ok: true, failures: [], notes: [] }; if (f.ok) rows[f.row].notes.push(f.msg); else { rows[f.row].ok = false; rows[f.row].failures.push(f.msg); } }
const result = { generated: new Date().toISOString(), hive: HIVE, members: MEMBERS.length, teeth: TEETH, rows, readings };
writeFileSync(REPORT + '.tmp', JSON.stringify(result, null, 2)); renameSync(REPORT + '.tmp', REPORT);
for (const [id, r] of Object.entries(rows).sort()) {
  console.log(`${r.ok ? 'PASS' : 'FAIL'} ${id}`);
  for (const m of r.failures.slice(0, 12)) console.log('   x ' + m);
  if (r.failures.length > 12) console.log(`   ... ${r.failures.length - 12} more`);
  for (const m of r.notes.slice(0, 4)) console.log('   - ' + m);
}
const bad = Object.values(rows).filter((r) => !r.ok).length;
console.log(`${bad ? 'FAIL' : 'PASS'} hive-scale lists: ${Object.keys(rows).length} rows read against a ${MEMBERS.length}-member hive, ${bad} failing`);
process.exit(bad ? 1 : 0);
