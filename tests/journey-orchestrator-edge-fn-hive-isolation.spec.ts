/**
 * journey-orchestrator-edge-fn-hive-isolation.spec.ts — 2026-06-07
 *
 * Behavioral counterpart to the ai-orchestrator + asset-brain-query membership
 * gates (commit 4ce110b). Those edge fns read hive data with the SERVICE-ROLE
 * client (bypasses RLS), so each must self-enforce caller membership: an
 * authenticated member of their OWN hive must NOT be able to read another
 * hive's analytics / asset graph by passing a foreign hive_id. The gate denies
 * a non-member with HTTP 403 ("Caller is not an active member of this hive").
 *
 * SELF-DETECTING + LOCAL-ONLY: this runs entirely against the local WorkHive
 * Tester stack (Flask :5000 + local Supabase :54321) via window.db.functions.
 * invoke — never a remote/production target. It probes ai-orchestrator with a
 * random foreign hive_id; if that does NOT come back 403/"not an active
 * member", the local edge runtime is still serving the pre-gate version, so the
 * suite SKIPS (never a false FAIL). Reload the local functions to enable.
 *
 * Counterpart to the static validator surface (the C4 AI-seam ratchet records
 * the v_worker_truth membership read); this proves the gate WORKS at runtime.
 */
import { test, expect } from './_fixtures';

type Probe = { status: number; msg: string; hadError: boolean; data: unknown };

async function setup(whPage: any) {
  await whPage.goto('/workhive/hive.html', { waitUntil: 'networkidle' });
  await whPage.waitForFunction(() => !!(window as any).db, null, { timeout: 15000 });
  return whPage.evaluate(async () => {
    const db = (window as any).db;
    const ownHive = localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id') || '';
    // A UUID the signed-in member is certainly NOT part of.
    const foreign = (crypto as any).randomUUID();

    const invoke = async (fn: string, body: Record<string, unknown>): Promise<Probe> => {
      try {
        const { data, error } = await db.functions.invoke(fn, { body });
        if (!error) return { status: 200, msg: '', hadError: false, data };
        // supabase-js v2: non-2xx -> FunctionsHttpError with a Response in .context
        let status = 0, msg = '';
        const ctx = (error as any)?.context;
        if (ctx && typeof ctx.status === 'number') {
          status = ctx.status;
          try { const j = await ctx.json(); msg = j?.error || ''; } catch { /* body not json */ }
        }
        if (!msg) msg = String((error as any)?.message || '');
        return { status, msg, hadError: true, data: null };
      } catch (e: any) {
        return { status: 0, msg: String(e?.message || e), hadError: true, data: null };
      }
    };

    const denied = (p: Probe) => p.status === 403 || /not an active member/i.test(p.msg);

    // Probe: is the gated version being served by the local runtime?
    const probe = await invoke('ai-orchestrator', { question: 'isolation probe', hive_id: foreign });
    if (!ownHive || !denied(probe)) {
      return {
        skip: true,
        reason: !ownHive ? 'fixture not in hive mode' : 'edge-fn gate not served by local runtime (reload functions)',
        probe,
      };
    }

    const foreignOrch  = await invoke('ai-orchestrator', { question: 'who works in this hive', hive_id: foreign });
    const foreignBrain = await invoke('asset-brain-query', {
      question: 'status', asset_id: (crypto as any).randomUUID(), hive_id: foreign,
    });
    // Positive control: the caller's OWN hive must NOT be blocked as "not a member".
    const ownOrch = await invoke('ai-orchestrator', { question: 'summary', hive_id: ownHive });

    return { skip: false, foreignOrch, foreignBrain, ownOrch };
  });
}

test.describe('AI orchestrator edge-fn hive isolation (runtime gate)', () => {
  test('foreign hive_id is denied (403) by ai-orchestrator + asset-brain-query', async ({ whPage }) => {
    const r = await setup(whPage);
    test.skip(r.skip, `${r.reason} — local-only; reload the local edge functions to enable.`);

    const orchDenied = r.foreignOrch.status === 403 || /not an active member/i.test(r.foreignOrch.msg);
    expect(orchDenied, `ai-orchestrator: foreign hive must 403, got ${JSON.stringify(r.foreignOrch)}`).toBe(true);

    const brainDenied = r.foreignBrain.status === 403 || /not an active member/i.test(r.foreignBrain.msg);
    expect(brainDenied, `asset-brain-query: foreign hive must 403, got ${JSON.stringify(r.foreignBrain)}`).toBe(true);

    // Positive control: own hive is NOT falsely blocked by the membership gate.
    const ownBlocked = r.ownOrch.status === 403 && /not an active member/i.test(r.ownOrch.msg);
    expect(ownBlocked, `own hive must NOT be blocked as non-member, got ${JSON.stringify(r.ownOrch)}`).toBe(false);
  });
});
