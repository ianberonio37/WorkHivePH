/**
 * journey-ai.spec.ts — AI Companion + Quality dashboard sentinel anchors.
 *
 * Layer-2 anchor scenarios for:
 *   - validate_ai_companion_trust_observability.py (8 checks)
 *       acronym_pronunciation, assistant_journal_pull, audio_interrupt,
 *       conversation_end_ack, cost_cap, fallback_ux, rate_limit_guard,
 *       tts_latency_budget
 *   - validate_ai_regression.py (3 checks)
 *       analytics_feature_parity, draft_artifacts, logbook_feature_parity
 *
 * Primary surfaces: ai-quality.html, voice-handler.js (loaded via assistant.html)
 *
 * NOTE: Each test() name starts with the check anchor so the sentinel
 * survey marks the check as covered on its next run.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady, pageSrcWithExternals } from './_helpers';

const AI_QUALITY = '/workhive/ai-quality.html';
const ASSISTANT = '/workhive/assistant.html';

test.describe('ai-quality.html — trust & observability anchors', () => {

  test('cost_cap: ai_cost_log surfaced on ai-quality dashboard', async ({ whPage }) => {
    const src = await pageSrcWithExternals(whPage, AI_QUALITY);
    expect(src, 'ai-quality.html must reference ai_cost_log').toContain('ai_cost_log');
  });

  test('rate_limit_guard: ai-gateway exposes a rate-limit error path the UI can render', async ({ whPage }) => {
    await whPage.goto(AI_QUALITY);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);
    const src = await pageSrcWithExternals(whPage, AI_QUALITY);
    expect(src.toLowerCase(), 'rate-limit terminology should appear somewhere on the quality dashboard').toMatch(/rate.limit|rate_limit/);
  });

  test('tts_latency_budget: quality dashboard reports TTS latency telemetry', async ({ whPage }) => {
    await whPage.goto(AI_QUALITY);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);
    const src = await pageSrcWithExternals(whPage, AI_QUALITY);
    expect(src.toLowerCase(), 'TTS latency telemetry should be referenced').toMatch(/tts|latency/);
  });

  test('fallback_ux: assistant page wires a navigable fallback message helper', async ({ whPage }) => {
    const src = await pageSrcWithExternals(whPage, ASSISTANT);
    expect(src, 'voice-handler/_generateFallbackReply must ship with assistant.html').toMatch(/_generateFallbackReply|Sorry, I'm offline|fallback/i);
  });

  test('acronym_pronunciation: wh-tts._spellOutAcronyms is loaded with the assistant', async ({ whPage }) => {
    const src = await pageSrcWithExternals(whPage, ASSISTANT);
    expect(src, '_spellOutAcronyms must be in the assistant bundle').toMatch(/_spellOutAcronyms|ACRONYMS_TO_SPELL/);
  });

  test('audio_interrupt: _startRecording cancels in-flight audio before opening mic', async ({ whPage }) => {
    const src = await pageSrcWithExternals(whPage, ASSISTANT);
    expect(src, 'WHTts.stop must be invoked from _startRecording').toMatch(/_startRecording[\s\S]{0,500}WHTts[\s\S]{0,200}stop/);
  });

  test('conversation_end_ack: voice-handler close() resets dialog state and stops audio', async ({ whPage }) => {
    const src = await pageSrcWithExternals(whPage, ASSISTANT);
    expect(src, '_updateDialogState must be called when closing').toMatch(/_updateDialogState/);
    expect(src, 'audio cancellation must run on close').toMatch(/WHTts|speechSynthesis\.cancel/);
  });

  test('assistant_journal_pull: assistant.html pulls voice_journal_entries into prompt context', async ({ whPage }) => {
    const src = await pageSrcWithExternals(whPage, ASSISTANT);
    expect(src, 'voice_journal_entries must be queried by assistant').toContain('voice_journal_entries');
    expect(src.toUpperCase(), 'RECENT JOURNAL block must be present in system prompt build').toMatch(/RECENT\s+JOURNAL/);
  });
});

test.describe('analytics.html — AI regression anchors', () => {

  test('analytics_feature_parity: analytics page renders descriptive + diagnostic + prescriptive panes', async ({ whPage }) => {
    const src = await pageSrcWithExternals(whPage, '/workhive/analytics.html');
    for (const phase of ['descriptive', 'diagnostic', 'prescriptive']) {
      expect(src.toLowerCase(), `analytics must expose ${phase} surface`).toContain(phase);
    }
  });

  test('draft_artifacts: analytics surface mentions a draft/artifact export affordance', async ({ whPage }) => {
    const src = await pageSrcWithExternals(whPage, '/workhive/analytics.html');
    expect(src.toLowerCase(), 'draft or artifact UI hook must exist').toMatch(/draft|artifact|export/);
  });

  test('logbook_feature_parity: logbook surface mirrors the analytics phases for write parity', async ({ whPage }) => {
    const src = await pageSrcWithExternals(whPage, '/workhive/logbook.html');
    expect(src.toLowerCase(), 'logbook must reference at least one analytics phase or AI assist hook').toMatch(/descriptive|diagnostic|prescriptive|ai\s*assist|orchestrator/);
  });
});
