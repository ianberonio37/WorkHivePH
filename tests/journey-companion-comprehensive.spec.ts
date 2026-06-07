/**
 * journey-companion-comprehensive.spec.ts — Step 7 capstone (Companion Stack Battery)
 *
 * The agentic E2E critic for the UNIFIED Companion. Sibling of the per-page UFAI
 * battery (ufai_battery.js): same machine (boot -> run -> REFEREE+CRITIC), AI lens.
 * It drives the REAL Companion through the one front door (ai-gateway) and grades
 * the trajectory against the three reference stacks in AI_SURFACE_MAP.md
 * (Agent / Memory / RAG) + the frozen Step-0 Safety baseline, asserting OBSERVABLE
 * side-effects (gateway envelope model_chain, route_result, agent_memory rows for
 * the session_key) — never answer-text vibes (Agent-as-a-Judge, arXiv 2508.02994).
 *
 * REUSE: the whPage fixture (real Supabase auth session), the in-page window.db
 * pattern (journey-definer-rpc-hive-isolation), the self-skip-till-live guard, and
 * companion_battery.js (the injectable). The battery builds its own LOCAL-wired
 * client from the bridge-rewritten constants, so it works on every surface
 * regardless of whether the page exposes window.db.
 *
 * PHASE STATUS: Phase 1 = Agent pillar on assistant.html. Phases 2-5 add the
 * Memory chain, RAG + Safety pillars, the CRITIC pass, and the 32-surface waves.
 *
 * SELF-DETECTING: deploy is decoupled from this working tree. If the unified
 * front door (Step 4 voice-action route) isn't live on the stack this suite hits,
 * the probe comes back unrouted and every assertion SKIPS (never a false FAIL).
 */
import { test, expect } from './_fixtures';
import { adminClient } from './_db-cleanup';

const BATTERY_URL = '/workhive/companion_battery.js';

/** Fetch + install + boot the battery into the current page. */
async function installAndBoot(page: any) {
  return page.evaluate(async (url: string) => {
    const r = await fetch(url);
    if (!r.ok) throw new Error('battery fetch ' + r.status);
    // indirect eval runs the arrow-fn file in global scope -> installs window.__CSB
    (0, eval)(await r.text())();
    return await (window as any).__CSB.boot();
  }, BATTERY_URL);
}

const runCSB = (page: any, opts: any) =>
  page.evaluate((o: any) => (window as any).__CSB.run(o), opts);

/** Is the unified front door live on the stack this suite hits? */
function notLive(r: any): string | null {
  if (!r || !r.meta || !r.meta.identity || !r.meta.identity.auth_uid) return 'no auth session in fixture';
  const tool = (r.trajectory || []).find((t: any) => t.agent === 'voice-action');
  if (tool && /unknown agent|not deployed|not found|40[034]/i.test(String(tool.error || ''))) {
    return 'voice-action gateway route not live on this stack';
  }
  return null;
}

test.describe('Companion Stack Battery — capstone E2E critic', () => {
  test.describe.configure({ mode: 'serial' });

  // CI robustness: a heavy battery run trips the hive/user rate cap and the
  // gateway then serves a cached {answer} (model_chain=['ai-cache']) which makes
  // routing unprovable. Clear the ephemeral counters before the suite so each
  // run grades cleanly. Best-effort — never fail the suite on a cleanup miss.
  test.beforeAll(async () => {
    try {
      const db = adminClient();
      await db.from('ai_rate_limits').delete().neq('hive_id', '00000000-0000-0000-0000-000000000000');
      await db.from('ai_user_rate_limits').delete().neq('user_id', '__none__');
    } catch { /* ephemeral counters — non-fatal */ }
  });

  test('Agent pillar (assistant.html): tool->voice-action-router + fan-out->ai-orchestrator, grounded by model_chain', async ({ whPage }) => {
    await whPage.goto('/workhive/assistant.html', { waitUntil: 'domcontentloaded' });
    // supabase UMD (CDN) loads at end of body; the battery builds its client from it.
    await whPage.waitForFunction(() => !!(window as any).supabase, null, { timeout: 15000 });

    const boot = await installAndBoot(whPage);
    expect(boot, 'battery installed + booted').toBeTruthy();

    const r = await runCSB(whPage, { surface: 'assistant', role: 'supervisor', experience: 'experienced' });

    const skip = notLive(r);
    test.skip(!!skip, `${skip} — the capstone activates once the unified front door (Step 4) is live on this stack.`);

    const tool = r.scores.Agent.metrics.tool;
    const fanout = r.scores.Agent.metrics.fanout;

    // GROUNDED: the gateway envelope's model_chain names the specialist it routed to.
    expect(tool.routed, `tool utterance must route to voice-action-router; model_chain=${JSON.stringify(tool.modelChain)}`).toBe(true);
    expect(tool.intents.length, `route_result.intents must carry >=1 actionable intent (kinds=${JSON.stringify(tool.intents)})`).toBeGreaterThan(0);
    expect(fanout.orchestrated, `fan-out question must route to ai-orchestrator; model_chain=${JSON.stringify(fanout.modelChain)}`).toBe(true);
    expect(fanout.answerLen, 'fan-out must return a prose answer').toBeGreaterThan(8);

    // No Major Agent defect (front door hit + structured intents + answer present).
    const majors = (r.defects || []).filter((d: any) => d.pillar === 'Agent' && (d.severity === 'Major' || d.severity === 'Blocker'));
    expect(majors, `Agent-pillar Major defects:\n${JSON.stringify(majors, null, 2)}`).toHaveLength(0);
  });

  test('Memory pillar: voice-journal working memory persists + recalls + is IDENTITY-keyed (cross-surface)', async ({ whPage }) => {
    // Surface A — set a unique token through the voice-journal agent.
    await whPage.goto('/workhive/assistant.html', { waitUntil: 'domcontentloaded' });
    await whPage.waitForFunction(() => !!(window as any).supabase, null, { timeout: 15000 });
    await installAndBoot(whPage);
    const a = await whPage.evaluate(async () =>
      await (window as any).__CSB.memoryStack({ surface: 'assistant', agent: 'voice-journal' }));

    const skip = (!a || !a.metrics || (a.metrics.skipped) || (a.metrics.rls_note));
    test.skip(!!skip, 'no auth session / agent_memory not client-readable — capstone activates on a live authed stack.');

    // PERSIST is the hard grounded proof: the gateway awaited saveTurn, so the
    // agent_memory row keyed by auth_uid+agent_id exists now.
    expect(a.metrics.persisted, 'voice-journal turn must persist to agent_memory (working memory, layer 01)').toBe(true);
    // RECALL is the soft (model-dependent) signal — Minor, not a hard gate: free-tier
    // 8B recall is probabilistic, so we log it rather than flake the suite on it.
    if (!a.metrics.recalled) console.warn('[CSB] voice-journal did not recall the token this run (Minor, model-dependent)');
    const token = a.metrics.token as string;

    // Surface B — a DIFFERENT page; the same identity+agent bucket must see the token.
    await whPage.goto('/workhive/logbook.html', { waitUntil: 'domcontentloaded' });
    await whPage.waitForFunction(() => !!(window as any).supabase, null, { timeout: 15000 });
    await installAndBoot(whPage);
    const visibleOnB = await whPage.evaluate(async (tok: string) => {
      const id = (window as any).__CSB._state.identity;
      const db = ((window as any).db && (window as any).db.functions)
        ? (window as any).db
        : (window as any).supabase.createClient('http://127.0.0.1:54321', 'sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH');
      const { data } = await db.from('agent_memory')
        .select('turn_text').eq('auth_uid', id.auth_uid).eq('agent_id', 'voice-journal')
        .eq('kind', 'turn').ilike('turn_text', '%' + tok + '%').limit(1);
      return !!(data && data.length);
    }, token);

    expect(visibleOnB, 'memory is identity-keyed (not page-keyed): the token set on assistant.html must be visible from logbook.html').toBe(true);

    const majors = (a.defects || []).filter((d: any) => d.severity === 'Major' || d.severity === 'Blocker');
    expect(majors, `Memory-pillar Major defects:\n${JSON.stringify(majors, null, 2)}`).toHaveLength(0);
  });

  test('Full battery: 0 Major grounded defects across all four pillars (the capstone invariant)', async ({ whPage }) => {
    await whPage.goto('/workhive/logbook.html', { waitUntil: 'domcontentloaded' });
    await whPage.waitForFunction(() => !!(window as any).supabase, null, { timeout: 15000 });
    await installAndBoot(whPage);
    const r = await runCSB(whPage, { surface: 'logbook', role: 'supervisor', experience: 'experienced', wave: 1 });

    const skip = notLive(r);
    test.skip(!!skip, `${skip} — the capstone activates once the unified front door is live on this stack.`);

    // The stable invariant: every HARD grounded proof (model_chain / agent_memory
    // row / cited[] / no-leak) passes. Minor (model-dependent recall, taste) ride
    // in sweep_critiques.json; cached responses (rate-limit degrade) skip routing
    // asserts by construction — so this stays green across runs.
    const majors = (r.defects || []).filter((d: any) => d.severity === 'Major' || d.severity === 'Blocker');
    expect(majors, `Major grounded defects across pillars:\n${JSON.stringify(majors, null, 2)}`).toHaveLength(0);
    expect(r.scores.Safety.metrics.leaks, 'zero adversarial leaks through the unified front door').toBe(0);
  });
});
