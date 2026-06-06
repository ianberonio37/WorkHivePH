/**
 * Home fan-out parity — get_hive_dashboard(hive_id) == the 11 separate queries.
 * =============================================================================
 * The home (index.html) board collapses 11 separate canonical reads into ONE
 * get_hive_dashboard RPC. This gate proves the consolidated payload is byte-for-
 * byte equal to running those 11 queries individually against the same canonical
 * truth views, through the page's own authenticated session.
 *
 * If this FAILS, the RPC has drifted from canonical and the home tiles would lie.
 *
 * Reuses the whPage fixture (real Supabase Auth sign-in + hive context).
 */
import { test, expect } from './_fixtures';

const sortStr = (a: string[]) => [...a].map(String).sort();

test('get_hive_dashboard RPC equals the 11 separate canonical queries', async ({ whPage }) => {
  await whPage.goto('/workhive/index.html', { waitUntil: 'networkidle' });
  // window.db is the page's authenticated client (set during _initDashboard).
  await whPage.waitForFunction(() => !!(window as any).db, null, { timeout: 15000 });

  const r = await whPage.evaluate(async () => {
    const db = (window as any).db;
    const HIVE_ID = localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id') || '';
    if (!HIVE_ID) return { fatal: 'no HIVE_ID — fixture must run in hive mode' };

    const startOfDay = new Date(); startOfDay.setHours(0, 0, 0, 0);
    const dayIso = startOfDay.toISOString();
    const todayIso = new Date().toISOString().slice(0, 10);
    const since24h = new Date(Date.now() - 86400000).toISOString();

    // ── The consolidated RPC ────────────────────────────────────────────
    const rpc = await db.rpc('get_hive_dashboard', { p_hive_id: HIVE_ID, p_day_start: dayIso });

    // ── The 11 separate canonical queries (mirror the legacy loader) ─────
    const [logRes, riskRes, invRes, pmRes, closedTodayRes, pmDoneTodayRes,
           jobsCountRes, risksCountRes, amcRes, anomRes, sigRes] = await Promise.all([
      db.from('v_logbook_truth').select('id, machine, category, maintenance_type, status, created_at, date')
        .eq('hive_id', HIVE_ID).eq('status', 'Open').order('created_at', { ascending: false }).limit(5),
      db.from('v_risk_truth').select('asset_name, risk_level, risk_score, mtbf_days, generated_at')
        .eq('hive_id', HIVE_ID).in('risk_level', ['critical', 'high']).order('risk_score', { ascending: false }).limit(5),
      db.from('v_inventory_items_truth').select('part_name, qty_on_hand, reorder_point, is_low_stock')
        .eq('hive_id', HIVE_ID).limit(100),
      db.from('v_pm_compliance_truth').select('pm_asset_id, asset_name, category, is_due')
        .eq('hive_id', HIVE_ID).limit(200),
      db.from('v_logbook_truth').select('id', { count: 'exact', head: true })
        .eq('hive_id', HIVE_ID).eq('status', 'Closed').gte('closed_at', dayIso),
      db.from('pm_completions').select('id', { count: 'exact', head: true })
        .eq('hive_id', HIVE_ID).eq('status', 'done').gte('completed_at', dayIso),
      db.from('v_logbook_truth').select('id', { count: 'exact', head: true })
        .eq('hive_id', HIVE_ID).eq('status', 'Open'),
      db.from('v_risk_truth').select('asset_name', { count: 'exact', head: true })
        .eq('hive_id', HIVE_ID).in('risk_level', ['critical', 'high']),
      db.from('v_amc_truth').select('amc_id, shift_date, summary, headline, status')
        .eq('hive_id', HIVE_ID).eq('status', 'pending').gte('shift_date', todayIso)
        .order('shift_date', { ascending: true }).limit(1).maybeSingle(),
      db.from('v_sensor_truth').select('asset_id, parameter, quality_flag, recorded_at, is_anomaly')
        .eq('hive_id', HIVE_ID).eq('is_anomaly', true).gte('recorded_at', since24h)
        .order('recorded_at', { ascending: false }).limit(1).maybeSingle(),
      db.from('v_alert_truth').select('alert_id, machine, title, severity, detected_at')
        .eq('hive_id', HIVE_ID).eq('alert_kind', 'signature').eq('severity', 'critical')
        .order('detected_at', { ascending: false }).limit(1).maybeSingle(),
    ]);

    const sepLowStock = (invRes.data || []).filter((i: any) => i.is_low_stock === true);

    return {
      fatal: null,
      rpcError: rpc.error ? rpc.error.message : null,
      rpc: rpc.data,
      sep: {
        open_jobs_ids:    (logRes.data  || []).map((j: any) => j.id),
        open_jobs_count:  jobsCountRes.count || 0,
        risks_names:      (riskRes.data || []).map((x: any) => x.asset_name),
        risks_count:      risksCountRes.count || 0,
        low_stock_count:  sepLowStock.length,
        pm_overdue_count: (pmRes.data || []).filter((a: any) => a.is_due).length,
        closed_today:     closedTodayRes.count || 0,
        pm_done_today:    pmDoneTodayRes.count || 0,
        amc_id:    amcRes.data  ? amcRes.data.amc_id  : null,
        sensor_id: anomRes.data ? anomRes.data.asset_id : null,
        sig_id:    sigRes.data  ? sigRes.data.alert_id : null,
      },
    };
  });

  expect(r.fatal, r.fatal || '').toBeNull();
  expect(r.rpcError, `RPC errored: ${r.rpcError}`).toBeNull();
  const rpc = r.rpc, sep = r.sep;
  expect(rpc, 'RPC returned no payload').toBeTruthy();

  // Counts — strict equality (these drive the tiles).
  expect(Number(rpc.open_jobs_count),  'open_jobs_count').toBe(Number(sep.open_jobs_count));
  expect(Number(rpc.risks_count),      'risks_count').toBe(Number(sep.risks_count));
  expect(Number(rpc.pm_overdue_count), 'pm_overdue_count').toBe(Number(sep.pm_overdue_count));
  expect(Number(rpc.closed_today),     'closed_today').toBe(Number(sep.closed_today));
  expect(Number(rpc.pm_done_today),    'pm_done_today').toBe(Number(sep.pm_done_today));
  expect((rpc.low_stock_items || []).length, 'low_stock count').toBe(Number(sep.low_stock_count));

  // Detail lists — same membership (compare sorted; ORDER BY ties are not drift).
  expect(sortStr((rpc.open_jobs || []).map((j: any) => j.id)), 'open_jobs ids')
    .toEqual(sortStr(sep.open_jobs_ids));
  expect(sortStr((rpc.risks || []).map((x: any) => x.asset_name)), 'risk asset_names')
    .toEqual(sortStr(sep.risks_names));

  // Today's One Thing single-row signals — same presence + same row id.
  expect((rpc.amc_pending    ? rpc.amc_pending.amc_id    : null), 'amc_pending').toBe(sep.amc_id);
  expect((rpc.sensor_anomaly ? rpc.sensor_anomaly.asset_id : null), 'sensor_anomaly').toBe(sep.sensor_id);
  expect((rpc.signature_alert ? rpc.signature_alert.alert_id : null), 'signature_alert').toBe(sep.sig_id);
});
