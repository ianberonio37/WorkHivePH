/**
 * Tier 9 — AI-assisted flows (5 scenarios, P1)
 *
 * ai-gateway routing, voice (Whisper), RAG citations, visual defect,
 * PII redaction. All depend on edge fns being reachable + AI chain configured.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';
import { readFileSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(__dirname, '..');

test.describe('Tier 9 — AI-assisted flows', () => {

  test('J1_assistant_invokes_orchestrator: assistant.html reaches ai-orchestrator (gateway routing)', async () => {
    // WHY: ai-orchestrator/ai-gateway are the single-entry-point routers (architecture)
    const html = readFileSync(resolve(ROOT, 'assistant.html'), 'utf-8');
    const callsOrchestrator =
      /functions\/v1\/ai-orchestrator/.test(html) ||
      /invoke\s*\(\s*['"]ai-orchestrator['"]/.test(html) ||
      /functions\/v1\/ai-gateway/.test(html) ||
      /invoke\s*\(\s*['"]ai-gateway['"]/.test(html);
    expect(callsOrchestrator, 'assistant must route through ai-orchestrator or ai-gateway').toBeTruthy();
    // Memory layer present (agent_memory referenced in copy)
    expect(html, 'must reference agent_memory persistence').toMatch(/agent_memory/);
  });

  test('J2_voice_multilingual_declared: voice-journal advertises Tagalog/Cebuano/multilingual', async () => {
    // WHY: Whisper auto-detects language; voice-journal page must surface multilingual support
    const html = readFileSync(resolve(ROOT, 'voice-journal.html'), 'utf-8');
    const mentions = ['Tagalog', 'Cebuano', 'Filipino', 'multilingual'];
    const found = mentions.filter((m) => new RegExp(m, 'i').test(html));
    expect(found.length, `voice-journal must mention at least 1 PH language; found: ${found.join(', ') || 'none'}`).toBeGreaterThanOrEqual(1);
  });

  test('J3_assistant_calls_semantic_search: RAG path goes through semantic-search edge fn', async () => {
    // WHY: semantic_search RPC queries kb_chunks + industry_standards_chunks (Azure Day 4)
    const html = readFileSync(resolve(ROOT, 'assistant.html'), 'utf-8');
    expect(html, 'assistant must call semantic-search edge fn').toMatch(
      /functions\/v1\/semantic-search|invoke\s*\(\s*['"]semantic-search['"]/
    );
  });

  test('J4_equipment_label_ocr_matches_asset_nodes: OCR fn fuzzy-matches asset_nodes', async () => {
    // WHY: equipment-label-ocr uses fuzzy match on serial_no / manufacturer / model
    const fn = readFileSync(resolve(ROOT, 'supabase', 'functions', 'equipment-label-ocr', 'index.ts'), 'utf-8');
    expect(fn, 'OCR fn must query asset_nodes for match').toMatch(/asset_nodes/);
    // Returns matched_asset shape
    expect(fn, 'must return matched_asset response shape').toMatch(/matched_asset/);
    // Extracts serial_no field
    expect(fn, 'must parse serial_no from OCR text').toMatch(/serial_no/);
  });

  test('J5_pii_redaction_imported_and_called: ai-gateway uses redactPII before forwarding', async () => {
    // WHY: redactPII.ts ensures specialists never see raw identity (security skill, PRODUCTION_FIXES #44)
    // STATIC: ai-gateway/index.ts must import + invoke redactPII helpers
    const fn = readFileSync(resolve(ROOT, 'supabase', 'functions', 'ai-gateway', 'index.ts'), 'utf-8');
    expect(fn, 'must import redactPII helpers').toMatch(/from\s+['"]\.\.\/_shared\/redactPII\.ts['"]/);
    expect(fn, 'must call redactPIIWithMap or equivalent before forwarding').toMatch(/redactPIIWithMap\s*\(|redactPII\s*\(/);
    // And hydrate back on response.
    expect(fn, 'must call hydratePII on response').toMatch(/hydratePII\s*\(/);
  });
});
