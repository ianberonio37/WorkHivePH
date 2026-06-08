/**
 * persona-golden-capture.spec.ts — Phase 8 §8.3 (Persona dimension live capture)
 *
 * Drives every probe in companion_persona_golden.json through the LIVE ai-gateway `voice-journal`
 * route (-> voice-journal-agent, the CONVERSATIONAL persona adopter) with context.persona TOGGLED
 * per probe, and captures the prose reply (body.data.answer) into a normalized observation map
 * .tmp/persona_golden_observed.json keyed by unit id: { answer }.
 *
 * WHY voice-journal + per-call persona: ai-gateway keeps a client-supplied context.persona (it only
 * defaults to the account persona when none is supplied), and voice-journal-agent reads ctx.persona
 * ('ctx.persona wins — per-call override') and wears the FULL persona block (tone + DOMAIN_LENS +
 * examples). So each probe can request Hezekiah or Zaniah independently, and the reply should carry
 * THAT persona's voice markers (name on identity probes, lane vocab / bridges on register probes).
 * It is a single LLM call (no fan-out), so it is light on the rate limit.
 *
 * Mirrors memory/rag/agent-golden-capture.spec.ts (whPage real-session fixture, in-page fetch with
 * the page's real JWT, gateway payload unwrapped from `.data`). NO mocking. That map feeds
 * `python tools/companion_persona_eval.py --observed`, after which 8.3 freezes the Persona baseline
 * on the locked-test split (only from a clean, non-rate-limited run).
 */
import { test, expect } from './_fixtures';
import { adminClient } from './_db-cleanup';
import * as fs from 'node:fs';
import * as path from 'node:path';

const GOLDEN_PATH = path.join(process.cwd(), 'companion_persona_golden.json');
const OUT_DIR = path.join(process.cwd(), '.tmp');
const OBSERVED_PATH = path.join(OUT_DIR, 'persona_golden_observed.json');
const RAW_PATH = path.join(OUT_DIR, 'persona_golden_raw.json');

const PACING_MS = 4000;

/** Reset the ephemeral local rate-limit counters + response cache so no reply is 429'd or cached. */
async function resetAiCounters() {
  try {
    const db = adminClient();
    await db.from('ai_rate_limits').delete().neq('hive_id', '00000000-0000-0000-0000-000000000000');
    await db.from('ai_user_rate_limits').delete().neq('user_id', '__none__');
    await db.from('ai_cache').delete().neq('key', '__none__');
  } catch { /* ephemeral infra tables — non-fatal */ }
}

/** Live ai-gateway `voice-journal` call with an explicit persona, from inside the page context. */
async function callVoiceJournal(page: any, message: string, persona: string, lang: string, hive_id: string | null) {
  return await page.evaluate(async ({ message, persona, lang, hive_id }: any) => {
    const t0 = performance.now();
    try {
      const SUPABASE_URL = 'http://127.0.0.1:54321';
      const SUPABASE_KEY = 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
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
      if (!accessToken) accessToken = SUPABASE_KEY;
      const resp = await fetch(`${SUPABASE_URL}/functions/v1/ai-gateway`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${accessToken}`, 'apikey': SUPABASE_KEY },
        body: JSON.stringify({ agent: 'voice-journal', message, context: { persona, lang }, hive_id }),
      });
      const latency_ms = Math.round(performance.now() - t0);
      const raw = await resp.text();
      let body: any = null;
      try { body = JSON.parse(raw); } catch { body = { raw }; }
      return { ok: resp.ok, status: resp.status, latency_ms, body };
    } catch (e: any) {
      return { ok: false, status: 0, latency_ms: Math.round(performance.now() - t0), body: { error: String(e?.message || e) } };
    }
  }, { message, persona, lang, hive_id });
}

/** Gateway wraps success under `.data`; voice-journal is conversational, so the reply is data.answer. */
function answerOf(body: any): string {
  const data = body?.data || body || {};
  return String(data?.answer ?? data?.route_result?.answer ?? '');
}

test.describe('Persona golden capture (Phase 8 §8.3)', () => {
  test.beforeAll(async () => {
    fs.mkdirSync(OUT_DIR, { recursive: true });
    await resetAiCounters();
  });

  test('drive the Persona golden set through the live voice-journal gateway (persona toggled)', async ({ whPage }) => {
    test.setTimeout(20 * 60 * 1000);
    const golden = JSON.parse(fs.readFileSync(GOLDEN_PATH, 'utf8'));
    const units: any[] = [...(golden.probes || [])];

    await whPage.goto('/workhive/index.html');
    const hive_id = await whPage.evaluate(
      () => localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id'),
    );

    const observed: Record<string, any> = {};
    const raw: any[] = [];
    let okCount = 0, callCount = 0, rateLimited = 0;

    for (const unit of units) {
      await resetAiCounters();
      const r = await callVoiceJournal(whPage, unit.utterance, unit.persona, unit.lang || 'auto', hive_id);
      callCount++; if (r.ok) okCount++; if (r.status === 429) rateLimited++;
      observed[unit.id] = { answer: answerOf(r.body) };
      raw.push({ id: unit.id, persona: unit.persona, ability: unit.ability, status: r.status, ok: r.ok,
                 latency_ms: r.latency_ms, body: r.body });
      await whPage.waitForTimeout(PACING_MS);
    }

    fs.writeFileSync(OBSERVED_PATH, JSON.stringify(observed, null, 2));
    fs.writeFileSync(RAW_PATH, JSON.stringify({ hive_id, callCount, okCount, rateLimited, total: units.length, raw }, null, 2));
    console.log(`[persona-capture] ${okCount}/${callCount} calls ok (${rateLimited} rate-limited) -> ${OBSERVED_PATH}`);
    if (rateLimited > 0) {
      console.warn(`[persona-capture] ${rateLimited} calls were rate-limited — do NOT freeze a baseline from this run.`);
    }

    expect(okCount, 'at least one voice-journal call should succeed (else stack/route is down)').toBeGreaterThan(0);
  });
});
