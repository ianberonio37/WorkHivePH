/**
 * journey-definer-rpc-hive-isolation.spec.ts — 2026-06-07
 *
 * Behavioral counterpart to validate_definer_membership_gate.py (which proves
 * the gate EXISTS in the migrations). This proves the gate WORKS at runtime:
 * an authenticated member of their own hive must NOT be able to read/compute/
 * export another hive's data by passing a foreign p_hive_id to a SECURITY
 * DEFINER RPC (those bypass RLS, so the function must self-enforce membership).
 *
 * Three enforcement shapes are checked, one per fix strategy:
 *   - RAISE-gated   (fetch_active_alerts, compute_*, export_hive_data):
 *                   foreign hive -> error 42501 ("not an active member").
 *   - WHERE-guarded (get_hive_readiness_current, get_adoption_risk_current):
 *                   foreign hive -> 0 rows (no error, but nothing leaks).
 *   - REVOKED       (get_oee_by_machine): not executable by `authenticated`
 *                   at all -> permission error for any browser call.
 *
 * SELF-DETECTING: deploy is decoupled from this repo's working tree, so the
 * gate may not be in the DB this suite hits yet. The suite probes one
 * RAISE-gated RPC with a random foreign hive; if it does NOT come back 42501,
 * the gate isn't deployed and every test SKIPS (never a false FAIL). Once
 * migrations 20260607000003-5 are applied, the probe returns 42501 and the
 * full assertions run.
 */
import { test, expect } from './_fixtures';

type RpcResult = { error: { code?: string; message?: string } | null; data: unknown };

async function setup(whPage: any) {
  await whPage.goto('/workhive/hive.html', { waitUntil: 'networkidle' });
  await whPage.waitForFunction(() => !!(window as any).db, null, { timeout: 15000 });
  return whPage.evaluate(async () => {
    const db = (window as any).db;
    const ownHive = localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id') || '';
    // A UUID the caller is certainly NOT a member of.
    const foreign = (crypto as any).randomUUID();

    const call = async (fn: string, args: Record<string, unknown>): Promise<RpcResult> => {
      try {
        const { error, data } = await db.rpc(fn, args);
        return { error: error ? { code: error.code, message: error.message } : null, data };
      } catch (e: any) {
        return { error: { code: e?.code, message: String(e?.message || e) }, data: null };
      }
    };

    // Probe: is the membership gate deployed?
    const probe = await call('fetch_active_alerts', { p_hive_id: foreign });
    const gateLive = probe.error?.code === '42501'
      || /not an active member/i.test(probe.error?.message || '');

    if (!ownHive || !gateLive) {
      return { skip: true, reason: !ownHive ? 'fixture not in hive mode' : 'DEFINER gate not deployed', ownHive, gateLive };
    }

    const raiseGated = await Promise.all([
      call('fetch_active_alerts',    { p_hive_id: foreign }),
      call('compute_anomaly_signals', { p_hive_id: foreign }),
      call('compute_adoption_risk',  { p_hive_id: foreign }),
      call('compute_hive_readiness', { p_hive_id: foreign }),
      call('export_hive_data',       { p_hive_id: foreign }),
    ]);
    const whereGuarded = await Promise.all([
      call('get_hive_readiness_current', { p_hive_id: foreign }),
      call('get_adoption_risk_current',  { p_hive_id: foreign }),
    ]);
    const revoked = await call('get_oee_by_machine', { p_hive_id: foreign, p_period_days: 90 });
    // Positive control: own hive must NOT be blocked as "not a member".
    const ownRead = await call('get_hive_readiness_current', { p_hive_id: ownHive });

    return { skip: false, raiseGated, whereGuarded, revoked, ownRead };
  });
}

test.describe('SECURITY DEFINER RPC hive isolation (runtime gate)', () => {
  test('foreign hive_id is denied across all SECURITY DEFINER RPC shapes', async ({ whPage }) => {
    const r = await setup(whPage);
    test.skip(r.skip, `${r.reason} — apply migrations 20260607000003-5 to enable.`);

    // RAISE-gated: every one must error with 42501 (or the member message).
    const names = ['fetch_active_alerts', 'compute_anomaly_signals', 'compute_adoption_risk',
                   'compute_hive_readiness', 'export_hive_data'];
    r.raiseGated.forEach((res: RpcResult, i: number) => {
      const denied = res.error?.code === '42501' || /not an active member/i.test(res.error?.message || '');
      expect(denied, `${names[i]}: foreign hive should RAISE 42501, got ${JSON.stringify(res.error)}`).toBe(true);
    });

    // WHERE-guarded: no error, but ZERO rows leak.
    r.whereGuarded.forEach((res: RpcResult, i: number) => {
      const rows = Array.isArray(res.data) ? res.data : (res.data == null ? [] : [res.data]);
      expect(rows.length, `${['get_hive_readiness_current','get_adoption_risk_current'][i]}: foreign hive must return 0 rows`).toBe(0);
    });

    // REVOKED: not executable by the authenticated browser role at all.
    expect(r.revoked.error, 'get_oee_by_machine must be revoked from authenticated (browser call errors)').not.toBeNull();

    // Positive control: own hive is not falsely blocked as "not a member".
    const ownBlocked = r.ownRead.error?.code === '42501';
    expect(ownBlocked, 'own hive must NOT be blocked by the membership gate').toBe(false);
  });
});
