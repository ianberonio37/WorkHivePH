/**
 * Test DB cleanup helper.
 *
 * Tests pollute the DB with rows tagged by the per-test `testMarker`
 * fixture (a unique short token embedded in `machine`, `part_name`,
 * `title`, `body` etc.). This module provides a fixture-friendly
 * cleanup function that deletes those rows using the local-Supabase
 * service-role key, so subsequent test runs start from a clean state.
 *
 * Why service role: tests need to delete rows regardless of RLS
 * (the test worker may not own every row their flow created — e.g.
 * a project_link side-effect insert). Service role bypasses RLS.
 *
 * Keys: read from env first (WH_TEST_SUPABASE_URL +
 * WH_TEST_SERVICE_KEY), fall back to the well-known local Docker
 * keys that ship unchanged from the Supabase CLI. NEVER commit
 * production service keys here.
 */
import { createClient, SupabaseClient } from '@supabase/supabase-js';

// Well-known local Supabase keys (from `npx supabase status -o env`).
// These are static across local Docker installs — safe to embed.
const LOCAL_URL = 'http://127.0.0.1:54321';
const LOCAL_SERVICE_KEY =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU';

let _client: SupabaseClient | null = null;
export function adminClient(): SupabaseClient {
  if (_client) return _client;
  const url = process.env.WH_TEST_SUPABASE_URL || LOCAL_URL;
  const key = process.env.WH_TEST_SERVICE_KEY  || LOCAL_SERVICE_KEY;
  _client = createClient(url, key, { auth: { persistSession: false } });
  return _client;
}

/**
 * Delete every row across the platform's writable tables that contains
 * the given test marker in one of its text fields. The marker is the
 * per-test unique tag (e.g. "WH-PW-0-mxyz") that tests embed in
 * `machine`, `part_name`, `title`, `body`, `description` etc.
 *
 * Tables that DON'T accept the marker pattern (e.g. enum-only columns)
 * are skipped silently — best-effort cleanup, not exhaustive.
 */
export async function cleanupByMarker(marker: string): Promise<{ deleted: Record<string, number> }> {
  const db = adminClient();
  const deleted: Record<string, number> = {};

  // Map table -> (text columns to match against)
  const TARGETS: Array<[string, string[]]> = [
    ['logbook',                  ['machine', 'problem', 'action', 'knowledge']],
    ['inventory_items',          ['part_number', 'part_name', 'notes']],
    ['inventory_transactions',   ['note']],
    ['pm_completions',           ['notes']],
    ['schedule_items',           ['title', 'notes']],
    ['community_posts',          ['body']],
    ['community_replies',        ['body']],
    ['projects',                 ['name', 'description']],
    ['project_items',            ['title', 'notes']],
    ['marketplace_listings',     ['title', 'description']],
    ['marketplace_inquiries',    ['message']],
    ['skill_exam_attempts',      []],  // no text fields to match on
    ['voice_journal_entries',    ['transcript', 'summary']],
  ];

  for (const [table, cols] of TARGETS) {
    if (!cols.length) continue;
    let total = 0;
    for (const col of cols) {
      try {
        const { error, count } = await db
          .from(table)
          .delete({ count: 'exact' })
          .ilike(col, `%${marker}%`);
        if (!error && typeof count === 'number') total += count;
      } catch (_e) { /* table may not exist in older test DBs */ }
    }
    if (total > 0) deleted[table] = total;
  }

  return { deleted };
}
