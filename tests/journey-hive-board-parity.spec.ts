/**
 * Hive Board fan-out parity — get_hive_board_dashboard == the separate loaders.
 * =============================================================================
 * hive.html initBoard() collapses 5 hive-scoped plain-read loaders (members,
 * feed, PM-health, team-stock, approval-queue) into ONE get_hive_board_dashboard
 * RPC (Phase 1). This gate proves the consolidated payload is equal to running
 * those loaders' queries individually, through the page's own authed session.
 *
 * If this FAILS, the board would render numbers/lists that differ from canonical.
 */
import { test, expect } from './_fixtures';

const sortStr = (a: any[]) => a.map(String).sort();

test('get_hive_board_dashboard equals the separate hive-board loader queries', async ({ whPage }) => {
  await whPage.goto('/workhive/hive.html', { waitUntil: 'networkidle' });
  await whPage.waitForFunction(() => !!(window as any).db, null, { timeout: 15000 });

  const r = await whPage.evaluate(async () => {
    const db = (window as any).db;
    const HIVE_ID = localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id') || '';
    if (!HIVE_ID) return { fatal: 'no HIVE_ID — fixture must run in hive mode' };

    const rpc = await db.rpc('get_hive_board_dashboard', { p_hive_id: HIVE_ID });

    const [membersRes, openWorkersRes, feedLogRes, openCountRes, feedPmRes,
           pmScopeRes, teamInvRes, pendAssetsRes, pendPartsRes] = await Promise.all([
      db.from('hive_members').select('worker_name, role, status')
        .eq('hive_id', HIVE_ID).neq('status', 'kicked').order('joined_at'),
      db.from('v_logbook_truth').select('worker_name').eq('hive_id', HIVE_ID).eq('status', 'Open'),
      db.from('v_logbook_truth').select('id, worker_name, date, machine, category, problem, status, created_at')
        .eq('hive_id', HIVE_ID).order('created_at', { ascending: false }).limit(40),
      db.from('v_logbook_truth').select('*', { count: 'exact', head: true })
        .eq('hive_id', HIVE_ID).eq('status', 'Open'),
      db.from('pm_completions')
        .select('id, completed_at, pm_assets(asset_name), pm_scope_items(item_text, frequency)')
        .eq('hive_id', HIVE_ID).eq('status', 'done').order('completed_at', { ascending: false }).limit(20),
      db.from('v_pm_scope_items_truth').select('scope_item_id, is_overdue, is_due_soon').eq('hive_id', HIVE_ID),
      db.from('v_inventory_items_truth').select('worker_name, part_name, qty_on_hand, min_qty')
        .eq('hive_id', HIVE_ID).eq('status', 'approved'),
      db.from('asset_nodes').select('id').eq('hive_id', HIVE_ID).eq('status', 'pending'),
      db.from('v_inventory_items_truth').select('id').eq('hive_id', HIVE_ID).eq('status', 'pending'),
    ]);

    const pmCount = (arr: any[]) => ({
      overdue:  arr.filter(x => x.is_overdue).length,
      dueSoon:  arr.filter(x => !x.is_overdue && x.is_due_soon).length,
    });
    const invKey = (i: any) => `${i.worker_name}|${i.part_name}|${i.qty_on_hand}|${i.min_qty}`;
    const sepPmAsset: Record<string, string> = {};
    (feedPmRes.data || []).forEach((e: any) => { sepPmAsset[e.id] = e.pm_assets?.asset_name || ''; });

    return {
      fatal: null,
      rpcError: rpc.error ? rpc.error.message : null,
      rpc: rpc.data,
      sep: {
        members_names: (membersRes.data || []).map((m: any) => m.worker_name),
        members_sups:  (membersRes.data || []).filter((m: any) => m.role === 'supervisor').map((m: any) => m.worker_name),
        open_workers:  (openWorkersRes.data || []).map((w: any) => w.worker_name),
        feed_log_ids:  (feedLogRes.data || []).map((l: any) => l.id),
        open_count:    openCountRes.count || 0,
        feed_pm_ids:   (feedPmRes.data || []).map((p: any) => p.id),
        feed_pm_asset: sepPmAsset,
        pm:            pmCount(pmScopeRes.data || []),
        team_inv_keys: (teamInvRes.data || []).map(invKey),
        pend_asset_ids:(pendAssetsRes.data || []).map((a: any) => a.id),
        pend_part_ids: (pendPartsRes.data || []).map((p: any) => p.id),
      },
    };
  });

  expect(r.fatal, r.fatal || '').toBeNull();
  expect(r.rpcError, `RPC errored: ${r.rpcError}`).toBeNull();
  const rpc = r.rpc, sep = r.sep;
  expect(rpc, 'RPC returned no payload').toBeTruthy();

  // members
  expect(sortStr((rpc.members || []).map((m: any) => m.worker_name)), 'member names').toEqual(sortStr(sep.members_names));
  expect(sortStr((rpc.members || []).filter((m: any) => m.role === 'supervisor').map((m: any) => m.worker_name)), 'supervisors').toEqual(sortStr(sep.members_sups));
  expect(sortStr((rpc.open_jobs_workers || []).map((w: any) => w.worker_name)), 'open-job workers').toEqual(sortStr(sep.open_workers));

  // feed + open count
  expect(Number(rpc.open_count), 'open_count').toBe(Number(sep.open_count));
  expect(sortStr((rpc.feed_logbook || []).map((l: any) => l.id)), 'feed logbook ids').toEqual(sortStr(sep.feed_log_ids));
  expect(sortStr((rpc.feed_pm || []).map((p: any) => p.id)), 'feed pm ids').toEqual(sortStr(sep.feed_pm_ids));
  // flattened nested join parity (asset_name)
  (rpc.feed_pm || []).forEach((p: any) => {
    expect(p.asset_name || '', `pm ${p.id} asset_name`).toBe(sep.feed_pm_asset[p.id] || '');
  });

  // PM health counts
  const rpcPm = {
    overdue: (rpc.pm_scope || []).filter((x: any) => x.is_overdue).length,
    dueSoon: (rpc.pm_scope || []).filter((x: any) => !x.is_overdue && x.is_due_soon).length,
  };
  expect(rpcPm.overdue, 'pm overdue').toBe(sep.pm.overdue);
  expect(rpcPm.dueSoon, 'pm due-soon').toBe(sep.pm.dueSoon);

  // team inventory (full approved set; client filters self downstream)
  const invKey = (i: any) => `${i.worker_name}|${i.part_name}|${i.qty_on_hand}|${i.min_qty}`;
  expect(sortStr((rpc.team_inventory || []).map(invKey)), 'team inventory').toEqual(sortStr(sep.team_inv_keys));

  // approval queue
  expect(sortStr((rpc.pending_assets || []).map((a: any) => a.id)), 'pending asset ids').toEqual(sortStr(sep.pend_asset_ids));
  expect(sortStr((rpc.pending_parts || []).map((p: any) => p.id)), 'pending part ids').toEqual(sortStr(sep.pend_part_ids));
});
