/**
 * _seed-helper.ts — idempotent test-data seeding helper.
 *
 * The whPage fixture in _fixtures.ts looks up the seeded Pablo Aguilar
 * worker_profiles row to drive sign-in. If the table is empty (fresh
 * Supabase, reset, etc.), the fixture throws and every spec using
 * whPage fails.
 *
 * Call ensureSeeded() in a beforeAll() at the top of any spec that
 * uses whPage so the suite self-heals. Fires the Flask seeder
 * /api/seed/hives_workers endpoint if no worker_profiles row exists,
 * then polls until rows show up.
 *
 * Idempotent: skips the POST + poll when worker_profiles is already
 * populated. Safe to call from every spec.
 */
import { adminClient } from './_db-cleanup';

const SEEDER_BASE = process.env.WH_TEST_SEEDER_URL || 'http://127.0.0.1:5000';

let _seededInThisProcess = false;

export async function ensureSeeded(): Promise<void> {
  if (_seededInThisProcess) return;
  const db = adminClient();
  const { count, error } = await db.from('worker_profiles')
    .select('username', { count: 'exact', head: true });
  if (!error && (count || 0) > 0) {
    _seededInThisProcess = true;
    return;
  }
  // Empty (or unreachable) — fire the seeder
  // eslint-disable-next-line no-console
  console.log('[seed-helper] worker_profiles empty — POST /api/seed/hives_workers');
  const res = await fetch(`${SEEDER_BASE}/api/seed/hives_workers`, { method: 'POST' });
  if (!res.ok) {
    throw new Error(`seed-helper: Flask seeder responded ${res.status}; cannot run whPage-dependent specs`);
  }
  // Poll for rows to appear (seeder runs async — give it up to 30s)
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    await new Promise(r => setTimeout(r, 1500));
    const probe = await db.from('worker_profiles')
      .select('username', { count: 'exact', head: true });
    if ((probe.count || 0) > 0) {
      _seededInThisProcess = true;
      // eslint-disable-next-line no-console
      console.log(`[seed-helper] seeded ${probe.count} worker_profiles row(s)`);
      return;
    }
  }
  throw new Error('seed-helper: seeder fired but worker_profiles still empty after 30s');
}
