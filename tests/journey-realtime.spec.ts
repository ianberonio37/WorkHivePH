/**
 * Tier 10 — Realtime (4 scenarios, P1)
 *
 * Supabase Realtime: INSERT/DELETE on watched tables propagates to UI
 * within ~3s without manual refresh. Presence channel for live status.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';
import { readFileSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(__dirname, '..');

test.describe('Tier 10 — Realtime', () => {

  test('K1_logbook_insert_subscription_present: hive.html subscribes to INSERT on logbook', async () => {
    // WHY: realtime live-board UX (skill: realtime-engineer)
    // STATIC: hive.html bootstrap must wire postgres_changes INSERT subscription on logbook
    const hive = readFileSync(resolve(ROOT, 'hive.html'), 'utf-8');
    // JS object literal keys are unquoted: { event: 'INSERT', ... }
    expect(hive, 'must subscribe to postgres_changes').toMatch(/postgres_changes/);
    expect(hive, 'must cover INSERT').toMatch(/event\s*:\s*['"]INSERT['"]/);
    expect(hive, 'must filter by hive_id').toMatch(/filter\s*:\s*['"]hive_id=eq\./);
    // Channel cleanup on beforeunload must exist (skill rule).
    expect(hive, 'channel cleanup on beforeunload').toMatch(/beforeunload[\s\S]{0,800}removeChannel/);
  });

  test('K2_logbook_delete_subscription_safe: DELETE handler uses payload.old?.id pattern', async () => {
    // WHY: REPLICA IDENTITY default = PK only (security skill); must use optional chaining on payload.old
    const hive = readFileSync(resolve(ROOT, 'hive.html'), 'utf-8');
    expect(hive, 'must handle DELETE event').toMatch(/event\s*:\s*['"]DELETE['"]/);
    // payload.old?.id is the canonical safe access pattern.
    expect(hive, 'must use payload.old?.id pattern').toMatch(/payload\.old\?\.id/);
  });

  test('K3_presence_channel_declared: hive.html sets up presence channel + presence chip UI', async () => {
    // WHY: presence channel powers the live-board worker chips (realtime-engineer skill)
    const html = readFileSync(resolve(ROOT, 'hive.html'), 'utf-8');
    // Declare a presence channel variable + cleanup on unmount
    expect(html, 'must declare presenceChannel binding').toMatch(/presenceChannel\s*=/);
    expect(html, 'must clean up presenceChannel on teardown').toMatch(/removeChannel\s*\(\s*presenceChannel/);
    // UI surface: presence-bar + presence-chip + online/offline dot states
    expect(html, 'must render presence-bar UI').toMatch(/presence-bar/);
    expect(html, 'must distinguish online vs offline presence dot').toMatch(/presence-dot\.online/);
  });

  test('K4_low_stock_signal_consumed: alert-hub reads is_low_stock from canonical inventory view', async () => {
    // WHY: low-stock is derived in v_inventory_items_truth (is_low_stock); alert-hub consumes it directly
    const html = readFileSync(resolve(ROOT, 'alert-hub.html'), 'utf-8');
    expect(html, 'alert-hub must read is_low_stock pre-derived flag').toMatch(/is_low_stock/);
    expect(html, 'alert-hub must read is_out_of_stock pre-derived flag').toMatch(/is_out_of_stock/);
  });
});
