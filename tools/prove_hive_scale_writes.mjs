// prove_hive_scale_writes — Wave HS (the hive at thirty), lens W1: two members change the same item at once.
//
//   W1  both changes survive, or the second member is told - never a silent overwrite of a teammate's work.
//
// ★THE RACE IS REPLAYED IN THE DATABASE, AS THE TWO PEOPLE, WITH THE PAGE'S OWN WRITE. Each scenario runs in ONE
// transaction that is rolled back: member B makes their change first (as B - their JWT claims, role authenticated),
// then member A sends EXACTLY the write the page sends (the same filters, the same guard, the snapshot A's screen was
// holding) and the outcome is read: how many rows A's write changed, and whether B's change is still there. What the
// page then SAYS to A on a zero-row result is held by oc-guard-speaks and by each page's own zero-row branch (named in
// the scenario's `told`), so this file proves the database half and names the sentence.
//
// Three shapes, from the census of every W1 write (2026-10-30):
//   guarded   - a compare-and-set (updated_at snapshot, or "still pending / not yet approved"): A's write must change 0
//   append    - two members add rows to one item (replies, reactions, inquiries): both rows must land, and a repeat by
//               the same person is refused by the table's own unique key
//   owner     - a record only one person writes (their resume, their listing): a teammate's write must change 0, so
//               two members can never race on it
//
//   node tools/prove_hive_scale_writes.mjs            every scenario
//   node tools/prove_hive_scale_writes.mjs --teeth    plants an unguarded write; must FAIL
import { writeFileSync, renameSync } from 'node:fs';
import { execSync } from 'node:child_process';
// the SQL goes in on stdin: as a -c argument it crossed the Windows shell, whose quoting broke on the scenarios' quotes and
// <> operators, and -c prints only the last statement's result - 27 of 31 scenarios read as 'nothing'
const psqlIn = (sql) => { try { return execSync('docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA', { input: sql, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }); } catch (e) { return String(e.stdout || ''); } };

const H = '30303030-3030-4030-8030-303030303030';
const TEETH = process.argv.includes('--teeth');
const REPORT = 'hive_scale_writes_report.json';

const as = (name) => `select set_config('request.jwt.claims', json_build_object('sub', (select auth_uid from hive_members `
  + `where worker_name = '${name}' and hive_id = '${H}')::text, 'role', 'authenticated')::text, true); set local role authenticated;`;
const back = 'reset role;';
// a write that may be refused by RLS (0 rows) or by a trigger (an exception): counted either way, never aborting the run
const count = (key, stmt) => `do $w$ declare n int; begin ${stmt}; get diagnostics n = row_count; insert into _r values ('${key}', n::text); `
  + `exception when others then insert into _r values ('${key}', 'refused'); end $w$;`;
const pick = (sql) => `(${sql})`;
// fix(name, sql): the item both members act on is chosen ONCE, before either acts - a pick re-evaluated inside A's
// statement, after B's write, chose the NEXT pending row and the race was never run (HS455 read a guard that 'failed')
const fix = (name, sql) => `create temp table ${name} on commit drop as select (${sql}) as id; grant select on ${name} to authenticated;`;
const the = (name) => `(select id from ${name})`;

// ── the scenarios: one per W1 row ──────────────────────────────────────────────────────────────────────────────────
const S = [];
const add = (id, page, unit, shape, body, expect, told) => S.push({ id, page, unit, shape, body, expect, told });

const POST = pick(`select id from community_posts where hive_id = '${H}' and author_name = 'Joel Cruz' and deleted_at is null and not flagged order by created_at desc limit 1`);
add('HS401', 'community.html', 'community_posts', 'guarded',
  `create temp table _s on commit drop as select updated_at from community_posts where id = ${POST};
   ${as('Ernesto Villareal')} ${count('b_pin', `update community_posts set pinned = not pinned where id = ${POST}`)} ${back}
   ${as('Joel Cruz')} ${count('a_edit', `update community_posts set content = content || ' (edited)' where id = ${POST} and updated_at = (select updated_at from _s)${TEETH ? ' or true' : ''}`)} ${back}
   insert into _r select 'b_pin_kept', ((select pinned from community_posts where id = ${POST}) is distinct from (select pinned from community_posts p where false))::text;`,
  { b_pin: '1', a_edit: '0' }, 'community.html: "This post changed while you were editing it. Your text is still here - Save again to keep your version."');
add('HS403', 'community.html', 'community_reactions', 'append',
  `${as('Joel Cruz')} ${count('a_react', `insert into community_reactions (post_id, hive_id, worker_name, auth_uid, emoji) select ${POST}, '${H}', 'Joel Cruz', auth.uid(), 'eyes' where not exists (select 1 from community_reactions where post_id = ${POST} and worker_name = 'Joel Cruz' and emoji = 'eyes')`)} ${back}
   ${as('Ana Reyes')} ${count('b_react', `insert into community_reactions (post_id, hive_id, worker_name, auth_uid, emoji) select ${POST}, '${H}', 'Ana Reyes', auth.uid(), 'eyes' where not exists (select 1 from community_reactions where post_id = ${POST} and worker_name = 'Ana Reyes' and emoji = 'eyes')`)} ${back}
   ${as('Joel Cruz')} ${count('a_again', `insert into community_reactions (post_id, hive_id, worker_name, auth_uid, emoji) values (${POST}, '${H}', 'Joel Cruz', auth.uid(), 'eyes')`)} ${back}
   insert into _r select 'both_kept', (select count(*) from community_reactions where post_id = ${POST} and emoji = 'eyes' and worker_name in ('Joel Cruz', 'Ana Reyes'))::text;`,
  { both_kept: '2', a_again: 'refused' }, 'a second tap of the same reaction is refused by (post_id, worker_name, emoji)');
add('HS405', 'community.html', 'community_replies', 'append',
  `${as('Joel Cruz')} ${count('a_reply', `insert into community_replies (post_id, hive_id, author_name, auth_uid, content, created_at) values (${POST}, '${H}', 'Joel Cruz', auth.uid(), 'probe reply A', now() - interval '1 hour')`)} ${back}
   ${as('Ana Reyes')} ${count('b_reply', `insert into community_replies (post_id, hive_id, author_name, auth_uid, content, created_at) values (${POST}, '${H}', 'Ana Reyes', auth.uid(), 'probe reply B', now() - interval '1 hour')`)} ${back}
   insert into _r select 'both_kept', (select count(*) from community_replies where post_id = ${POST} and content like 'probe reply %')::text;`,
  { a_reply: '1', b_reply: '1', both_kept: '2' }, 'both replies land; the thread shows both');

const MEMBER = pick(`select id from hive_members where hive_id = '${H}' and worker_name = 'Wilson Ocampo'`);
add('HS407', 'hive.html', 'hive_members', 'guarded',
  `${as('Ernesto Villareal')} ${count('b_kick', `update hive_members set status = 'kicked' where hive_id = '${H}' and id = ${MEMBER} and status <> 'kicked'`)} ${back}
   ${as('Corazon Bautista')} ${count('a_kick', `update hive_members set status = 'kicked' where hive_id = '${H}' and id = ${MEMBER} and status <> 'kicked'${TEETH ? ' or true' : ''}`)}
   ${count('a_promote', `update hive_members set role = 'supervisor' where hive_id = '${H}' and id = ${MEMBER} and status = 'active'`)} ${back}`,
  { b_kick: '1', a_kick: '0', a_promote: '0' }, 'hive.html: "<name> was already removed by another supervisor." / "... is no longer active in this hive, so the role was not handed over."');
add('HS409', 'hive.html', 'logbook', 'guarded',
  `${as('Ernesto Villareal')} ${count('b_backfill', `update logbook set hive_id = '${H}' where worker_name in ('Joel Cruz') and hive_id is null`)} ${back}
   ${as('Corazon Bautista')} ${count('a_backfill', `update logbook set hive_id = '${H}' where worker_name in ('Joel Cruz') and hive_id is null`)} ${back}`,
  { a_backfill: '0' }, 'the backfill writes only rows with no hive - a second run has nothing to take (idempotent)');

const PENDING_NODE = pick(`select id from asset_nodes where hive_id = '${H}' and status = 'pending' limit 1`);
add('HS395', 'asset-hub.html', 'asset_nodes', 'guarded',
  `${fix('_tpn', PENDING_NODE.slice(1, -1))}
   ${as('Ernesto Villareal')} ${count('b_approve', `update asset_nodes set status = 'approved', approved_at = now() where id = ${the('_tpn')} and status = 'pending'`)} ${back}
   ${as('Corazon Bautista')} ${count('a_reject', `update asset_nodes set status = 'rejected', approved_at = now(), rejection_reason = 'probe' where id = ${the('_tpn')} and hive_id = '${H}' and status = 'pending'`)} ${back}`,
  { b_approve: '1', a_reject: '0' }, 'asset-hub.html: "That asset was already handled by another supervisor."');
const MODE = pick(`select id from rcm_fmea_modes where hive_id = '${H}' and approved_at is null limit 1`);
add('HS397', 'asset-hub.html', 'rcm_fmea_modes', 'guarded',
  `${fix('_tmo', MODE.slice(1, -1))}
   ${as('Ernesto Villareal')} ${count('b_approve', `update rcm_fmea_modes set approved_at = now(), approved_by = 'Ernesto Villareal' where id = ${the('_tmo')} and approved_at is null`)} ${back}
   ${as('Corazon Bautista')} ${count('a_approve', `update rcm_fmea_modes set approved_at = now(), approved_by = 'Corazon Bautista' where id = ${the('_tmo')} and hive_id = '${H}' and approved_at is null`)} ${back}
   insert into _r select 'approver_kept', (select approved_by from rcm_fmea_modes where id = ${the('_tmo')});`,
  { b_approve: '1', a_approve: '0', approver_kept: 'Ernesto Villareal' }, 'asset-hub.html approveFmeaMode: the zero-row branch says the mode was already approved');

add('HS393', 'alert-hub.html', 'alert_dismissals', 'guarded',
  `${as('Ernesto Villareal')} ${count('b_handle', `insert into alert_dismissals (hive_id, alert_key, action, actor) values ('${H}', 'hs-w1-probe', 'handled', 'x')`)} ${back}
   ${as('Joel Cruz')} ${count('a_insert', `insert into alert_dismissals (hive_id, alert_key, action, actor) values ('${H}', 'hs-w1-probe', 'snoozed', 'x') on conflict (hive_id, alert_key) do ${TEETH ? `update set action = excluded.action, actor = excluded.actor` : 'nothing'}`)}
   ${count('a_renew', `update alert_dismissals set action = 'snoozed' where hive_id = '${H}' and alert_key = 'hs-w1-probe' and action = 'snoozed' and snooze_until < now()`)} ${back}
   insert into _r select 'actor_kept', (select actor from alert_dismissals where hive_id = '${H}' and alert_key = 'hs-w1-probe');`,
  { b_handle: '1', a_insert: '0', a_renew: '0', actor_kept: 'Ernesto Villareal' }, 'alert-hub.html: "<name> already handled this alert for the hive - nothing was recorded under your name."');

add('HS399', 'assistant.html', 'ai_reply_feedback', 'append',
  `${as('Joel Cruz')} ${count('a_fb', `insert into ai_reply_feedback (hive_id, auth_uid, worker_name, agent, source, question, rating) values ('${H}', auth.uid(), 'Joel Cruz', 'assistant', 'probe', 'probe question', 1)`)} ${back}
   ${as('Ana Reyes')} ${count('b_fb', `insert into ai_reply_feedback (hive_id, auth_uid, worker_name, agent, source, question, rating) values ('${H}', auth.uid(), 'Ana Reyes', 'assistant', 'probe', 'probe question', -1)`)} ${back}
   insert into _r select 'both_kept', (select count(*) from ai_reply_feedback where source = 'probe' and question = 'probe question')::text;`,
  { both_kept: '2' }, "each member's rating is their own row");

// integrations: the CMMS import's ledger is the arbiter (claim, then write only what was claimed)
add('HS415', 'integrations.html', 'logbook', 'append',
  `${as('Ernesto Villareal')} ${count('b_claim', `insert into external_sync (hive_id, system_type, external_id, entity_type, status) values ('${H}', 'generic', 'WO-HS-PROBE', 'work_order', 'Open') on conflict (hive_id, system_type, external_id, entity_type) do nothing`)} ${back}
   ${as('Danilo Pascual')} ${count('a_claim', `insert into external_sync (hive_id, system_type, external_id, entity_type, status) values ('${H}', 'generic', 'WO-HS-PROBE', 'work_order', 'Open') on conflict (hive_id, system_type, external_id, entity_type) do nothing`)} ${back}`,
  { b_claim: '1', a_claim: '0' }, 'integrations.html: the second import claims nothing for WO-HS-PROBE, so it writes no second logbook entry');
add('HS411', 'integrations.html', 'asset_nodes', 'append',
  `${as('Ernesto Villareal')} ${count('b_import', `insert into asset_nodes (hive_id, auth_uid, worker_name, tag, name, level, criticality, status) values ('${H}', auth.uid(), 'Ernesto Villareal', 'BRM-X-PROBE', 'probe', 'equipment', 'medium', 'approved') on conflict (hive_id, tag) do update set name = excluded.name`)} ${back}
   ${as('Danilo Pascual')} ${count('a_import', `insert into asset_nodes (hive_id, auth_uid, worker_name, tag, name, level, criticality, status) values ('${H}', auth.uid(), 'Danilo Pascual', 'BRM-X-PROBE', 'probe', 'equipment', 'medium', 'approved') on conflict (hive_id, tag) do update set name = excluded.name`)} ${back}
   insert into _r select 'one_row', (select count(*) from asset_nodes where hive_id = '${H}' and tag = 'BRM-X-PROBE')::text;`,
  { one_row: '1' }, 'the import upserts on (hive_id, tag): one machine, however many supervisors import it');
add('HS413', 'integrations.html', 'inventory_items', 'append',
  `${as('Ernesto Villareal')} ${count('b_import', `insert into inventory_items (id, hive_id, auth_uid, worker_name, part_name, part_number, qty_on_hand, unit, status) values ('inv-hs-probe-b', '${H}', auth.uid(), 'Ernesto Villareal', 'probe part', 'BRM-PROBE', 1, 'pcs', 'approved') on conflict (part_number, hive_id) do update set part_name = excluded.part_name`)} ${back}
   ${as('Danilo Pascual')} ${count('a_import', `insert into inventory_items (id, hive_id, auth_uid, worker_name, part_name, part_number, qty_on_hand, unit, status) values ('inv-hs-probe-a', '${H}', auth.uid(), 'Danilo Pascual', 'probe part', 'BRM-PROBE', 1, 'pcs', 'approved') on conflict (part_number, hive_id) do update set part_name = excluded.part_name`)} ${back}
   insert into _r select 'one_row', (select count(*) from inventory_items where hive_id = '${H}' and part_number = 'BRM-PROBE')::text;`,
  { one_row: '1' }, 'the import upserts on (part_number, hive_id): one part');
add('HS417', 'integrations.html', 'pm_assets', 'append',
  `${as('Ernesto Villareal')} ${count('b_add', `insert into pm_assets (hive_id, auth_uid, worker_name, asset_name, tag_id, category) values ('${H}', auth.uid(), 'Ernesto Villareal', 'probe vehicle', 'PLATE-PROBE-1', 'Vehicles')`)} ${back}
   ${as('Danilo Pascual')} ${count('a_add', `insert into pm_assets (hive_id, auth_uid, worker_name, asset_name, tag_id, category) values ('${H}', auth.uid(), 'Danilo Pascual', 'probe vehicle 2', 'PLATE-PROBE-2', 'Vehicles')`)} ${back}`,
  { b_add: '1', a_add: '1' }, "each supervisor's vehicle is its own program - two adds, two rows");

const ITEM = pick(`select id from inventory_items where hive_id = '${H}' and worker_name = 'Joel Cruz' and deleted_at is null order by part_number limit 1`);
add('HS421', 'inventory.html', 'inventory_items', 'guarded',
  `create temp table _s on commit drop as select updated_at from inventory_items where id = ${ITEM};
   ${as('Ernesto Villareal')} ${count('b_edit', `update inventory_items set bin_location = 'Bay 2' where id = ${ITEM}`)} ${back}
   ${as('Joel Cruz')} ${count('a_edit', `update inventory_items set bin_location = 'Bay 7' where id = ${ITEM} and updated_at = (select updated_at from _s)`)} ${back}
   insert into _r select 'b_kept', (select bin_location from inventory_items where id = ${ITEM});`,
  { b_edit: '1', a_edit: '0', b_kept: 'Bay 2' }, 'inventory.html ocUpdate: "Someone else just updated this."');
add('HS423', 'inventory.html', 'inventory_transactions', 'guarded',
  `${as('Joel Cruz')} ${count('a_use', `perform public.inventory_deduct(${ITEM}, (select qty_on_hand from inventory_items where id = ${ITEM}))`)} ${back}
   ${as('Ana Reyes')} ${count('b_use', `perform public.inventory_deduct(${ITEM}, 1, null, null, 'use', 'hs-w1-second-use')`)} ${back}
   insert into _r select 'stock_left', (select qty_on_hand from inventory_items where id = ${ITEM})::text;
   insert into _r select 'second_moved', (select qty_change from inventory_transactions where id = 'hs-w1-second-use')::text;`,
  { a_use: '1', stock_left: '0', second_moved: '0' },
  'inventory.html: the deduct clamps and its ledger row records that nothing moved - the page reads that row back and tells the second member the shelf was empty (last-unit-race-is-told)');
add('HS419', 'inventory.html', 'asset_nodes', 'append',
  `${as('Joel Cruz')} ${count('a_merge', `insert into asset_nodes (id, hive_id, auth_uid, worker_name, tag, name, level, criticality, status) values ('11111111-2222-4333-8444-555555555555', '${H}', auth.uid(), 'Joel Cruz', 'BRM-MERGE-PROBE', 'probe', 'equipment', 'medium', 'pending') on conflict (id) do nothing`)}
   ${count('a_again', `insert into asset_nodes (id, hive_id, auth_uid, worker_name, tag, name, level, criticality, status) values ('11111111-2222-4333-8444-555555555555', '${H}', auth.uid(), 'Joel Cruz', 'BRM-MERGE-PROBE', 'probe', 'equipment', 'medium', 'pending') on conflict (id) do nothing`)} ${back}`,
  { a_merge: '1', a_again: '0' }, "the offline migration merges by the row's own id - a second merge adds nothing");

const NODE = pick(`select id from asset_nodes where hive_id = '${H}' and status = 'approved' and tag = 'BRM-P-101'`);
add('HS425', 'logbook.html', 'asset_nodes', 'guarded',
  `create temp table _s on commit drop as select updated_at from asset_nodes where id = ${NODE};
   ${as('Ernesto Villareal')} ${count('b_edit', `update asset_nodes set location = 'Unit 1 pump house' where id = ${NODE}`)} ${back}
   ${as('Corazon Bautista')} ${count('a_edit', `update asset_nodes set location = 'Tank farm' where id = ${NODE} and updated_at = (select updated_at from _s)${TEETH ? ' or true' : ''}`)} ${back}
   insert into _r select 'b_kept', (select location from asset_nodes where id = ${NODE});`,
  { b_edit: '1', a_edit: '0', b_kept: 'Unit 1 pump house' }, 'logbook.html saveEditAsset: "Someone changed this asset while you were editing it ... Your changes are still on the form"');
const TASK = pick(`select id from pm_scope_items where hive_id = '${H}' order by item_text, id limit 1`);
const TASK_ASSET = pick(`select asset_id from pm_scope_items where hive_id = '${H}' order by item_text, id limit 1`);
for (const [id, page] of [['HS427', 'logbook.html'], ['HS453', 'pm-scheduler.html']]) {
  add(id, page, 'pm_completions', 'append',
    `${as('Joel Cruz')} ${count('a_done', `insert into pm_completions (hive_id, worker_name, auth_uid, asset_id, scope_item_id, completed_at, status) values ('${H}', 'Joel Cruz', auth.uid(), ${TASK_ASSET}, ${TASK}, now(), 'done')`)} ${back}
     ${as('Ana Reyes')} ${count('b_done', `insert into pm_completions (hive_id, worker_name, auth_uid, asset_id, scope_item_id, completed_at, status) values ('${H}', 'Ana Reyes', auth.uid(), ${TASK_ASSET}, ${TASK}, now(), 'done')`)} ${back}
     ${as('Joel Cruz')} ${count('a_again', `insert into pm_completions (hive_id, worker_name, auth_uid, asset_id, scope_item_id, completed_at, status) values ('${H}', 'Joel Cruz', auth.uid(), ${TASK_ASSET}, ${TASK}, now(), 'done')`)} ${back}`,
    { a_done: '1', b_done: '1', a_again: 'refused' }, 'two members who both did the task each have their completion; the same member twice in a day is refused by (scope_item_id, worker_name, day)');
}

const INQ = pick(`select id from marketplace_inquiries where hive_id = '${H}' and seller_name = 'Joel Cruz' and status = 'pending' limit 1`);
add('HS434', 'marketplace-seller.html', 'marketplace_inquiries', 'owner',
  `${as('Ana Reyes')} ${count('teammate_reply', `update marketplace_inquiries set status = 'replied', reply_text = 'not mine' where id = ${INQ}`)} ${back}
   ${as('Joel Cruz')} ${count('seller_reply', `update marketplace_inquiries set status = 'replied', reply_text = 'mine' where id = ${INQ}`)} ${back}`,
  { teammate_reply: '0', seller_reply: '1' }, "an inquiry is answered by its seller only - a teammate's reply is refused");
const LISTING = pick(`select id from marketplace_listings where hive_id = '${H}' and seller_name = 'Joel Cruz' limit 1`);
add('HS436', 'marketplace-seller.html', 'marketplace_listings', 'owner',
  `${as('Ana Reyes')} ${count('teammate_edit', `update marketplace_listings set price = 1 where id = ${LISTING}`)} ${back}`,
  { teammate_edit: '0' }, "a listing is its seller's - a teammate's edit is refused (the seller's own two devices meet the updated_at guard)");
add('HS438', 'marketplace-seller.html', 'marketplace_sellers', 'owner',
  `${as('Ana Reyes')} ${count('teammate_edit', `update marketplace_sellers set messenger_username = 'not mine' where worker_name = 'Joel Cruz'`)} ${back}`,
  { teammate_edit: '0' }, "a seller profile is its seller's");
add('HS440', 'marketplace-seller.html', 'service_providers', 'owner',
  `${as('Ana Reyes')} ${count('teammate_edit', `update service_providers set availability = 'online' where worker_name = 'Joel Cruz'`)} ${back}`,
  { teammate_edit: '0' }, "a provider profile is its provider's");
const ELISTING = pick(`select id from marketplace_listings where hive_id = '${H}' and seller_name = 'Ernesto Villareal' limit 1`);
add('HS442', 'marketplace.html', 'marketplace_inquiries', 'append',
  `${as('Joel Cruz')} ${count('a_ask', `insert into marketplace_inquiries (listing_id, hive_id, buyer_name, buyer_auth_uid, message) values (${ELISTING}, '${H}', 'Joel Cruz', auth.uid(), 'probe A')`)} ${back}
   ${as('Ana Reyes')} ${count('b_ask', `insert into marketplace_inquiries (listing_id, hive_id, buyer_name, buyer_auth_uid, message) values (${ELISTING}, '${H}', 'Ana Reyes', auth.uid(), 'probe B')`)} ${back}
   insert into _r select 'both_kept', (select count(*) from marketplace_inquiries where listing_id = ${ELISTING} and message like 'probe %')::text;`,
  { both_kept: '2' }, "two buyers' questions both reach the seller");
add('HS444', 'marketplace.html', 'marketplace_listings', 'append',
  `${as('Joel Cruz')} ${count('a_list', `insert into marketplace_listings (hive_id, seller_name, auth_uid, section, title, status) values ('${H}', 'Joel Cruz', auth.uid(), 'parts', 'probe A', 'draft')`)} ${back}
   ${as('Ana Reyes')} ${count('b_list', `insert into marketplace_listings (hive_id, seller_name, auth_uid, section, title, status) values ('${H}', 'Ana Reyes', auth.uid(), 'parts', 'probe B', 'draft')`)} ${back}`,
  { a_list: '1', b_list: '1' }, "two members' listings are two listings");

const CO = pick(`select c.id from project_change_orders c where c.hive_id = '${H}' and c.status = 'pending' order by c.id limit 1`);
add('HS455', 'project-manager.html', 'project_change_orders', 'guarded',
  `${fix('_tco', CO.slice(1, -1))}
   ${as('Ernesto Villareal')} ${count('b_approve', `update project_change_orders set status = 'approved', approved_at = now() where id = ${the('_tco')} and status = 'pending'`)} ${back}
   ${as('Corazon Bautista')} ${count('a_reject', `update project_change_orders set status = 'rejected', approved_at = now(), rejection_reason = 'probe' where id = ${the('_tco')} and status = 'pending'`)} ${back}`,
  { b_approve: '1', a_reject: '0' }, 'project-manager.html approveCO/rejectCO: the zero-row branch says it was already decided');
const PITEM = pick(`select id from project_items where hive_id = '${H}' and status = 'pending' order by id limit 1`);
add('HS457', 'project-manager.html', 'project_items', 'guarded',
  `${fix('_tpi', PITEM.slice(1, -1))}
   ${as('Ana Reyes')} ${count('b_done', `update project_items set status = 'done', pct_complete = 100 where id = ${the('_tpi')} and status = 'pending'`)} ${back}
   ${as('Joel Cruz')} ${count('a_cycle', `update project_items set status = 'in_progress', pct_complete = 50 where id = ${the('_tpi')} and status = 'pending'${TEETH ? ' or true' : ''}`)} ${back}
   insert into _r select 'b_kept', (select status from project_items where id = ${the('_tpi')});`,
  { b_done: '1', a_cycle: '0', b_kept: 'done' }, 'project-manager.html cycleScopeStatus: "Someone moved this task to done while you were looking"');
const PLOG = pick(`select id from project_progress_logs where hive_id = '${H}' and acknowledged_at is null order by id limit 1`);
add('HS459', 'project-manager.html', 'project_progress_logs', 'guarded',
  `${fix('_tpl', PLOG.slice(1, -1))}
   ${as('Ernesto Villareal')} ${count('b_ack', `update project_progress_logs set acknowledged_by = 'Ernesto Villareal', acknowledged_at = now() where id = ${the('_tpl')} and acknowledged_at is null`)} ${back}
   ${as('Corazon Bautista')} ${count('a_ack', `update project_progress_logs set acknowledged_by = 'Corazon Bautista', acknowledged_at = now() where id = ${the('_tpl')} and acknowledged_at is null`)} ${back}
   insert into _r select 'ack_kept', (select acknowledged_by from project_progress_logs where id = ${the('_tpl')});`,
  { b_ack: '1', a_ack: '0', ack_kept: 'Ernesto Villareal' }, 'project-manager.html ackLog: the zero-row branch says it was already acknowledged');
const PROJ = pick(`select project_id from project_change_orders where id = ${CO}`);
add('HS461', 'project-manager.html', 'project_roles', 'append',
  `${as('Ernesto Villareal')} ${count('b_assign', `insert into project_roles (project_id, hive_id, worker_name, role) values (${PROJ}, '${H}', 'Wilson Ocampo', 'reviewer')`)} ${back}
   ${as('Corazon Bautista')} ${count('a_assign', `insert into project_roles (project_id, hive_id, worker_name, role) values (${PROJ}, '${H}', 'Wilson Ocampo', 'reviewer')`)} ${back}
   insert into _r select 'one_row', (select count(*) from project_roles where project_id = ${PROJ} and worker_name = 'Wilson Ocampo' and role = 'reviewer' and deleted_at is null)::text;`,
  { b_assign: '1', a_assign: 'refused', one_row: '1' }, 'the same role to the same person twice is refused by (project_id, worker_name, role)');
add('HS463', 'project-manager.html', 'projects', 'guarded',
  `create temp table _s on commit drop as select updated_at from projects where id = ${PROJ};
   ${as('Ernesto Villareal')} ${count('b_edit', `update projects set priority = 'high' where id = ${PROJ}`)} ${back}
   ${as('Corazon Bautista')} ${count('a_edit', `update projects set priority = 'low' where id = ${PROJ} and updated_at = (select updated_at from _s)`)} ${back}`,
  { b_edit: '1', a_edit: '0' }, 'project-manager.html: the project save is guarded by its updated_at snapshot');
add('HS465', 'resume.html', 'resume_documents', 'owner',
  `${as('Ana Reyes')} ${count('teammate_edit', `update resume_documents set title = 'not mine' where auth_uid = (select auth_uid from hive_members where worker_name = 'Joel Cruz' and hive_id = '${H}')`)} ${back}`,
  { teammate_edit: '0' }, "a resume is its owner's - a teammate's write reaches nothing");

// ── run ────────────────────────────────────────────────────────────────────────────────────────────────────────────
const rows = {};
for (const s of S) {
  // the snapshot table _s is made as postgres - member A must be able to read the snapshot their screen was holding
  const body = s.body.replace(/(create temp table _s on commit drop as [^;]*;)/, '$1 grant select on _s to authenticated;');
  const out = psqlIn(`begin; create temp table _r (k text, v text) on commit drop; grant all on _r to authenticated;
${body}
`
    + `select 'R|' || k || '|' || coalesce(v, '') from _r; rollback;
`);
  const got = {};
  for (const ln of out.split(/\r?\n/)) { const m = ln.trim().match(/^R\|([^|]+)\|(.*)$/); if (m) got[m[1]] = m[2]; }
  const bad = Object.entries(s.expect).filter(([k, v]) => got[k] !== v).map(([k, v]) => `${k}: expected ${v}, got ${got[k] ?? 'nothing'}`);
  rows[s.id] = { ok: !bad.length, page: s.page, unit: s.unit, shape: s.shape, got, failures: bad, told: s.told };
}
const result = { generated: new Date().toISOString(), hive: H, teeth: TEETH, rows };
writeFileSync(REPORT + '.tmp', JSON.stringify(result, null, 2)); renameSync(REPORT + '.tmp', REPORT);
for (const [id, r] of Object.entries(rows).sort()) {
  console.log(`${r.ok ? 'PASS' : 'FAIL'} ${id} ${r.page} ${r.unit} (${r.shape}) ${JSON.stringify(r.got)}`);
  for (const f of r.failures) console.log('   x ' + f);
}
const nbad = Object.values(rows).filter((r) => !r.ok).length;
console.log(`${nbad ? 'FAIL' : 'PASS'} hive-scale writes: ${Object.keys(rows).length} two-member races replayed as the members, ${nbad} failing`);
process.exit(nbad ? 1 : 0);
