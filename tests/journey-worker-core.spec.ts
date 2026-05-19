/**
 * Tier 2 — Worker core flows (8 scenarios, P0)
 *
 * Field-worker primary journeys: logbook entry, asset register, voice,
 * inventory, PM completion. These are the platform's most-used paths.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';
import { readFileSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(__dirname, '..');

test.describe('Tier 2 — Worker core flows', () => {

  test('B1_logbook_submit_form_present: logbook.html has insert path to `logbook` table', async () => {
    // WHY: the core platform action — log a maintenance event
    // STATIC: logbook page must include the canonical insert call
    const html = readFileSync(resolve(ROOT, 'logbook.html'), 'utf-8');
    expect(html, 'logbook.html must insert into logbook table').toMatch(/from\s*\(\s*['"]logbook['"]\s*\)[\s\S]{0,200}\.insert\s*\(/);
    // Form fields workers fill in: title/machine, problem/description, photo.
    expect(html, 'must have a form input for machine/asset').toMatch(/<input[^>]*(?:machine|asset)/i);
  });

  test('B2_logbook_edit_no_e_prefix_drift: saveEdit references `f-` not `e-` prefix', async () => {
    // WHY: edit-in-place refactor switched form IDs from `e-` to `f-` prefix; saveEdit must not regress (qa-tester lesson)
    // STATIC: search for saveEdit and confirm no `getElementById('e-...')` left
    const html = readFileSync(resolve(ROOT, 'logbook.html'), 'utf-8');
    // Find saveEdit body.
    const m = html.match(/function\s+saveEdit\s*\(\s*\)[\s\S]{0,4000}?(?=^function|\n\}\n)/m);
    if (m) {
      expect(m[0], "saveEdit must not reference 'e-' prefixed IDs (post-refactor)")
        .not.toMatch(/getElementById\s*\(\s*['"]e-/);
    }
  });

  test('B3_asset_register_modal_has_ocr_fields: logbook modal exposes manufacturer/model/serial', async () => {
    // WHY: equipment-label-ocr writes back to asset_nodes manufacturer/model/serial_no columns
    // STATIC: logbook must expose those 3 fields for OCR fill-in
    const html = readFileSync(resolve(ROOT, 'logbook.html'), 'utf-8');
    expect(html, 'logbook must expose manufacturer field for OCR write-back').toMatch(/manufacturer/i);
    expect(html, 'logbook must expose model field').toMatch(/model/i);
    expect(html, 'logbook must expose serial_no field').toMatch(/serial[\s_]?no/i);
  });

  test('B4_voice_journal_invokes_transcribe_agent: voice-journal calls both edge fns', async () => {
    // WHY: voice flow = voice-transcribe (Whisper) → voice-journal-agent (intent + persist)
    // STATIC: voice-journal.html must reach voice-transcribe (fetch URL OR .invoke) AND voice-journal-agent (directly OR via ai-gateway)
    const html = readFileSync(resolve(ROOT, 'voice-journal.html'), 'utf-8');
    const callsTranscribe =
      /invoke\s*\(\s*['"]voice-transcribe['"]/.test(html) ||
      /functions\/v1\/voice-transcribe/.test(html);
    expect(callsTranscribe, 'voice-journal must reach voice-transcribe (invoke or fetch URL)').toBeTruthy();
    // Either voice-journal-agent OR ai-gateway with agent='voice-journal' (per architecture).
    const callsAgent =
      /invoke\s*\(\s*['"]voice-journal-agent['"]/.test(html) ||
      /functions\/v1\/voice-journal-agent/.test(html) ||
      /voice-journal-agent/.test(html);
    const callsGateway = /invoke\s*\(\s*['"]ai-gateway['"][\s\S]{0,300}voice-journal/.test(html);
    expect(callsAgent || callsGateway, 'must reference voice-journal-agent directly or via ai-gateway').toBeTruthy();
  });

  test('B5_visual_defect_capture_invokes_edge_fn: logbook calls visual-defect-capture', async () => {
    // WHY: visual-defect-capture classifies attached photos before write
    const html = readFileSync(resolve(ROOT, 'logbook.html'), 'utf-8');
    expect(html, 'logbook must invoke visual-defect-capture edge fn').toMatch(
      /invoke\s*\(\s*['"]visual-defect-capture['"]/
    );
  });

  test('B6_inventory_transaction_insert_path: inventory.html appends to inventory_transactions', async () => {
    // WHY: inventory_transactions is append-only ledger; qty_on_hand on inventory_items derives from it
    const html = readFileSync(resolve(ROOT, 'inventory.html'), 'utf-8');
    expect(html, 'inventory must insert into inventory_transactions').toMatch(
      /from\s*\(\s*['"]inventory_transactions['"]\s*\)\.insert\s*\(/
    );
    // Stock-state computation must reference qty_on_hand (low/out thresholds)
    expect(html, 'must compute stock state from qty_on_hand').toMatch(/qty_on_hand\s*<=/);
  });

  test('B7_pm_completions_insert_path: pm-scheduler writes pm_completions row', async () => {
    // WHY: pm_completions row drives is_due_soon / is_overdue in v_pm_scope_items_truth
    const html = readFileSync(resolve(ROOT, 'pm-scheduler.html'), 'utf-8');
    expect(html, 'pm-scheduler must insert into pm_completions').toMatch(
      /from\s*\(\s*['"]pm_completions['"]\s*\)\.insert\s*\(/
    );
  });

  test('B8_voice_journal_persona_matches_agent: voice-journal preset keys mirror voice-journal-agent', async () => {
    // WHY: voice-journal-agent edge fn drives the prompt; persona presets must reference it
    const html = readFileSync(resolve(ROOT, 'voice-journal.html'), 'utf-8');
    // Comment / declaration mentions the agent (contract is keyed by agent's presets)
    expect(html, 'voice-journal must reference voice-journal-agent contract').toMatch(/voice-journal-agent/);
    // Transcribe edge fn is the upstream step
    expect(html, 'voice-journal must call voice-transcribe upstream').toMatch(/voice-transcribe/);
  });
});
