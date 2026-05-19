/**
 * Layer 2 Sentinel coverage for the KG facts scope split.
 *
 * The validator (validate_kg_scope_split.py) catches static regressions
 * (table missing, RPC missing, voice-handler dropping one of the two
 * stores, a future migration re-introducing the broadcast). These tests
 * cross-check the same invariants at the test layer so Sentinel's
 * convention-based matcher (`test('check_name: ...', ...)`) graduates
 * coverage automatically.
 *
 * Test names mirror the validator's layer keys so Sentinel pairs the
 * static check with the runtime check.
 */
import { test, expect } from '@playwright/test';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const PROJECT_ROOT = join(__dirname, '..');

function readMigrations(): string {
  const dir = join(PROJECT_ROOT, 'supabase', 'migrations');
  return readdirSync(dir)
    .filter((f) => f.endsWith('.sql'))
    .map((f) => readFileSync(join(dir, f), 'utf-8'))
    .join('\n\n');
}

function readVoiceHandler(): string {
  return readFileSync(join(PROJECT_ROOT, 'voice-handler.js'), 'utf-8');
}

test.describe('KG facts scope split — HIVE vs PLATFORM', () => {

  test('kg_scope_split_table_present: platform_knowledge_graph_facts is defined in a migration', async () => {
    const sql = readMigrations();
    // Match the CREATE TABLE for the platform-scoped sibling. Tolerant of
    // IF NOT EXISTS and the public. prefix.
    const re = /CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+(?:public\.)?platform_knowledge_graph_facts\s*\(/i;
    expect(sql).toMatch(re);
  });

  test('kg_scope_split_rpc_present: semantic_search_platform_kg_facts function is defined', async () => {
    const sql = readMigrations();
    const re = /CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:public\.)?semantic_search_platform_kg_facts\b/i;
    expect(sql).toMatch(re);
  });

  test('kg_scope_split_voice_queries_both: voice-handler.js queries both hive + platform KG RPCs', async () => {
    const js = readVoiceHandler();
    const hasHive     = js.includes('semantic_search_kg_facts');
    const hasPlatform = js.includes('semantic_search_platform_kg_facts');
    // If the hive RPC is referenced, the platform RPC must be too. If neither
    // is referenced (e.g. an extreme refactor removed KG retrieval entirely),
    // the test passes vacuously.
    if (hasHive) {
      expect(hasPlatform, 'voice-handler.js references hive RPC but not platform RPC; canon citations will silently drop').toBe(true);
    } else {
      expect(hasHive, 'voice-handler.js no longer queries KG facts at all (vacuously OK)').toBe(false);
    }
  });

  test('kg_scope_split_no_broadcast: no migration broadcasts platform-canon across hives', async () => {
    // The regression to prevent: someone writes
    //   INSERT INTO knowledge_graph_facts ... CROSS JOIN hives
    // to triplicate platform-canon rows across all hives instead of using
    // platform_knowledge_graph_facts. The audit reflex memory entry
    // documents the 2026-05-19 violation that motivated the split.
    const dir = join(PROJECT_ROOT, 'supabase', 'migrations');
    const offenders: string[] = [];
    for (const f of readdirSync(dir)) {
      if (!f.endsWith('.sql')) continue;
      const text = readFileSync(join(dir, f), 'utf-8');
      // Tolerate whitespace; anchor on INSERT INTO knowledge_graph_facts
      // and require CROSS JOIN hives within the next ~400 chars.
      const re = /INSERT\s+INTO\s+(?:public\.)?knowledge_graph_facts[\s\S]{0,400}?CROSS\s+JOIN\s+(?:public\.)?hives/i;
      if (re.test(text)) offenders.push(f);
    }
    expect(offenders, `Broadcast pattern in: ${offenders.join(', ')} — use platform_knowledge_graph_facts instead`).toEqual([]);
  });

});
