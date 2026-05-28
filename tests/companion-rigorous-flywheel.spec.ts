/**
 * companion-rigorous-flywheel.spec.ts
 *
 * REAL flywheel — no mocks, no simulation. Drives every probe in
 * companion_probe_bank.json through the LIVE ai-gateway edge function
 * via page.evaluate(fetch), captures raw response + latency + status,
 * and writes per-probe artifacts to .tmp/flywheel-turn-<N>/ for an
 * INDEPENDENT Python grader to assess. This file does NOT grade —
 * separation of concerns is the whole point.
 *
 * Replaces the prior fake-simulator flywheels (run_companion_*.py) that
 * computed accuracy from a hardcoded sigmoid + random noise without
 * ever touching the companion code.
 *
 * Runs against the Flask seeder (http://127.0.0.1:5000) which rewrites
 * cloud Supabase URLs to local Docker — same edge functions, RLS, and
 * migrations as production.
 *
 * Env:
 *   FLYWHEEL_TURN          — turn number (controls output dir + seed)
 *   FLYWHEEL_PERSONA       — zaniah | hezekiah (rotates per turn)
 *   FLYWHEEL_HIVE_LABEL    — manila | baguio | cebu (rotates per turn)
 *   FLYWHEEL_ARTIFACT_DIR  — output dir override
 */
import { test, expect } from './_fixtures';
import * as fs from 'node:fs';
import * as path from 'node:path';

const TURN = parseInt(process.env.FLYWHEEL_TURN || '1', 10);
const PERSONA = (process.env.FLYWHEEL_PERSONA || 'zaniah').toLowerCase();
const HIVE_LABEL = (process.env.FLYWHEEL_HIVE_LABEL || 'manila').toLowerCase();
const ARTIFACT_DIR = process.env.FLYWHEEL_ARTIFACT_DIR
  || path.join(process.cwd(), '.tmp', `flywheel-turn-${TURN}`);

// Probe bank lives in tools/
const BANK_PATH = path.join(process.cwd(), 'tools', 'companion_probe_bank.json');

interface BaselineProbe {
  id: string;
  agent: string;
  transcript: string;
  expected_route: string;
  expected_keywords_any: string[];
  must_not_contain: string[];
  category: string;
}

interface AdversarialProbe extends BaselineProbe {
  expected_behavior: string;
}

interface HeldOutTemplate {
  id: string;
  agent: string;
  transcript_template: string;
  fillers: Record<string, string[]>;
  expected_route: string;
  expected_keywords_any: string[];
  category: string;
}

interface ProbeBank {
  baseline: BaselineProbe[];
  adversarial: AdversarialProbe[];
  held_out_templates: HeldOutTemplate[];
}

/** Deterministic per-turn PRNG so held-out probes are reproducible by turn
 *  number but vary across turns — the companion cannot memorise them. */
function seededPick<T>(arr: T[], seed: number): T {
  // xorshift32 for determinism
  let s = seed | 0;
  s ^= s << 13; s ^= s >>> 17; s ^= s << 5;
  const idx = Math.abs(s) % arr.length;
  return arr[idx];
}

function materializeHeldOut(tmpl: HeldOutTemplate, turn: number): BaselineProbe {
  let text = tmpl.transcript_template;
  let seed = turn * 1009 + tmpl.id.charCodeAt(0);
  for (const [key, options] of Object.entries(tmpl.fillers)) {
    seed = (seed * 31 + key.charCodeAt(0)) | 0;
    const chosen = seededPick(options, seed);
    text = text.replaceAll(`{${key}}`, chosen);
  }
  return {
    id: `${tmpl.id}-T${turn}`,
    agent: tmpl.agent,
    transcript: text,
    expected_route: tmpl.expected_route,
    expected_keywords_any: tmpl.expected_keywords_any,
    must_not_contain: [],
    category: tmpl.category,
  };
}

/** Hit the LIVE ai-gateway from inside the browser context. Real fetch,
 *  real edge function, real LLM (free-tier chain). No mocking. */
async function callGatewayInBrowser(
  page: any,
  agent: string,
  message: string,
  persona: string,
  hive_id: string | null,
): Promise<{ ok: boolean; status: number; latency_ms: number; body: any; raw: string }> {
  return await page.evaluate(async ({ agent, message, persona, hive_id }: any) => {
    const t0 = performance.now();
    try {
      // LOCAL Supabase — the Flask seeder runs the local Docker stack,
      // and the sign-in JWT is issued by local auth (iss=http://127.0.0.1:54321/auth/v1).
      // Hitting the cloud URL would 401 because the JWT is foreign to it.
      const SUPABASE_URL = 'http://127.0.0.1:54321';
      const SUPABASE_KEY = 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
      const url = `${SUPABASE_URL}/functions/v1/ai-gateway`;
      // Find the access token stashed in localStorage by the page's existing
      // supabase client (storage key: sb-{ref}-auth-token, Supabase JS v2).
      // Creating a new client here would have NO session data — the prior
      // turn-1 failure (401 Sign-in required on every probe) proved that.
      let accessToken: string | null = null;
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('sb-') && key.endsWith('-auth-token')) {
          try {
            const parsed = JSON.parse(localStorage.getItem(key) || 'null');
            accessToken = parsed?.access_token || parsed?.session?.access_token || parsed?.currentSession?.access_token || null;
            if (accessToken) break;
          } catch {}
        }
      }
      if (!accessToken) accessToken = SUPABASE_KEY; // fall through — will surface as 401
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type':  'application/json',
          'Authorization': `Bearer ${accessToken}`,
          'apikey':        SUPABASE_KEY,
        },
        body: JSON.stringify({
          agent,
          message,
          context: { persona, lang: 'auto' },
          hive_id,
        }),
      });
      const latency_ms = Math.round(performance.now() - t0);
      const raw = await resp.text();
      let body: any = null;
      try { body = JSON.parse(raw); } catch { body = { raw }; }
      return { ok: resp.ok, status: resp.status, latency_ms, body, raw };
    } catch (e: any) {
      const latency_ms = Math.round(performance.now() - t0);
      return { ok: false, status: 0, latency_ms, body: { error: String(e?.message || e) }, raw: '' };
    }
  }, { agent, message, persona, hive_id });
}

test.describe(`companion rigorous flywheel — turn ${TURN}`, () => {

  test.beforeAll(() => {
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  });

  test('drive all probes through the live ai-gateway', async ({ whPage }) => {
    test.setTimeout(45 * 60 * 1000); // 45 min — many probes × LLM latency
    const bank = JSON.parse(fs.readFileSync(BANK_PATH, 'utf8')) as ProbeBank;

    // Get the seeded hive_id from localStorage (set by fixture sign-in)
    await whPage.goto('/workhive/index.html');
    const hive_id = await whPage.evaluate(
      () => localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id')
    );

    // Materialize held-out probes for this turn
    const held = bank.held_out_templates.map(t => materializeHeldOut(t, TURN));
    const allProbes = [...bank.baseline, ...bank.adversarial, ...held];

    const turnStart = Date.now();
    let rateLimitedStreak = 0;
    const results: any[] = [];

    for (let i = 0; i < allProbes.length; i++) {
      const probe = allProbes[i];
      const probeStart = Date.now();

      // Live call — real edge function, real LLM
      const result = await callGatewayInBrowser(
        whPage, probe.agent, probe.transcript, PERSONA, hive_id,
      );

      results.push({
        probe_id:    probe.id,
        category:    probe.category,
        agent:       probe.agent,
        transcript:  probe.transcript,
        expected:    {
          route:    probe.expected_route,
          keywords_any: probe.expected_keywords_any,
          must_not_contain: probe.must_not_contain,
          ...(('expected_behavior' in probe) ? { behavior: (probe as any).expected_behavior } : {}),
        },
        persona:     PERSONA,
        hive_label:  HIVE_LABEL,
        hive_id,
        turn:        TURN,
        probe_idx:   i,
        status:      result.status,
        ok:          result.ok,
        latency_ms:  result.latency_ms,
        response:    result.body,
        raw_excerpt: (result.raw || '').slice(0, 800),
        elapsed_ms:  Date.now() - probeStart,
        ts:          new Date().toISOString(),
      });

      // Rate-limit awareness — back off if we see consecutive 429s
      if (result.status === 429) {
        rateLimitedStreak += 1;
        if (rateLimitedStreak >= 3) {
          console.log(`[flywheel] 3 consecutive 429s — pausing 30s`);
          await whPage.waitForTimeout(30_000);
          rateLimitedStreak = 0;
        }
      } else {
        rateLimitedStreak = 0;
      }

      // Pacing — avoid hammering the free-tier chain. Widened to 4s after
      // V2 (10-turn) showed turns 4+ accruing 2 rate-limited probes each
      // even with WH_RATE_LIMIT_OVERRIDE=500. Trading ~36s per turn of
      // wallclock for cleaner signal.
      await whPage.waitForTimeout(4000);
    }

    const summary = {
      turn:         TURN,
      persona:      PERSONA,
      hive_label:   HIVE_LABEL,
      hive_id,
      probe_count:  allProbes.length,
      duration_ms:  Date.now() - turnStart,
      ok_count:     results.filter(r => r.ok).length,
      err_count:    results.filter(r => !r.ok).length,
      rate_limited: results.filter(r => r.status === 429).length,
      avg_latency_ms: Math.round(
        results.filter(r => r.ok).reduce((a, r) => a + r.latency_ms, 0)
        / Math.max(1, results.filter(r => r.ok).length)
      ),
      ts: new Date().toISOString(),
    };

    fs.writeFileSync(
      path.join(ARTIFACT_DIR, 'probes.json'),
      JSON.stringify(results, null, 2),
    );
    fs.writeFileSync(
      path.join(ARTIFACT_DIR, 'summary.json'),
      JSON.stringify(summary, null, 2),
    );

    console.log(`[flywheel] turn ${TURN} complete — ${summary.ok_count}/${summary.probe_count} ok, ${summary.rate_limited} rate-limited, avg ${summary.avg_latency_ms}ms`);

    // Soft assertion — we want the spec to pass even with some 429s
    // (rate limits are honest signal, not test failure). Only fail if
    // EVERY probe errored — that means the stack is broken, not the AI.
    expect(summary.ok_count, 'at least one probe should have succeeded — if all failed, stack is broken').toBeGreaterThan(0);
  });

});
