/**
 * asset-hub.html Live Telemetry tile — interaction-lock test.
 *
 * Locks the Physical AI Wave B1 surface:
 *   1. When sensor_readings exist for an asset, #telemetry-card renders.
 *   2. The per-parameter list shows entries (#telemetry-list children).
 *   3. The empty-state copy (#telemetry-empty) does NOT show when readings exist.
 *
 * Requires:
 *   - The sensor_readings seeder ran (30d x 3 params x N assets).
 *   - At least one asset on the page has readings.
 *
 * If no readings exist for any asset in the hive, the test seeds 5 minimal
 * readings via the admin client so the tile has something to render.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';
import { adminClient } from './_db-cleanup';

test.describe('asset-hub.html Live Telemetry tile', () => {
  test('renders when sensor_readings exist for the focused asset', async ({ whPage }) => {
    const db = adminClient();
    const hiveId = await whPage.evaluate(() => localStorage.getItem('wh_active_hive_id'));
    expect(hiveId, 'fixture must set wh_active_hive_id').toBeTruthy();

    // Find an asset that already has readings for this hive. Failing that,
    // pick any asset and seed 5 readings inline.
    const { data: anyReading } = await db.from('sensor_readings')
      .select('asset_id').eq('hive_id', hiveId).limit(1).maybeSingle();

    let targetAssetId: string | null = anyReading?.asset_id || null;

    if (!targetAssetId) {
      const { data: asset } = await db.from('asset_nodes')
        .select('id, name').eq('hive_id', hiveId).limit(1).maybeSingle();
      expect(asset?.id, 'no asset_nodes for this hive — seed first').toBeTruthy();
      targetAssetId = asset!.id;
      const now = new Date();
      const rows = Array.from({ length: 5 }).map((_, i) => {
        const t = new Date(now.getTime() - i * 30 * 60 * 1000);
        return {
          hive_id:      hiveId,
          asset_id:     targetAssetId,
          parameter:    'vibration',
          sensor_type:  'analog',
          unit:         'mm/s',
          quality_flag: 'good',
          value:        2.4 + Math.random() * 0.6,
          recorded_at:  t.toISOString(),
          source:       'sensor_test',
          external_key: `wh-pw-telemetry-${targetAssetId}-vibration-${t.toISOString()}`,
        };
      });
      const { error: insErr } = await db.from('sensor_readings').insert(rows);
      expect(insErr, `seed insert failed: ${insErr?.message}`).toBeNull();
    }

    // Navigate to asset-hub with the asset deep-linked. The hub uses
    // ?node_id=<uuid> per its existing deep-link contract — that triggers
    // openDetail(nodeId) which calls loadDetailTelemetry().
    await whPage.goto(`/workhive/asset-hub.html?node_id=${targetAssetId}`);
    await waitForPageReady(whPage);

    // The page hydrates the tile after pulling sensor_readings — give it
    // a generous window since v_sensor_recent is a view + the JS does some
    // post-processing for the anomaly chip.
    const tile = whPage.locator('#telemetry-card');
    await expect(tile).toBeVisible({ timeout: 12000 });

    // List should be non-empty (at least one parameter rendered).
    const list = whPage.locator('#telemetry-list > *');
    await expect(list.first()).toBeVisible({ timeout: 6000 });

    // Empty state must NOT be showing.
    const empty = whPage.locator('#telemetry-empty');
    await expect(empty).toBeHidden();
  });

  test('no page errors on load with telemetry data', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));

    await whPage.goto('/workhive/asset-hub.html');
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    const serious = errors.filter(e =>
      !e.toLowerCase().includes('failed to load resource'));
    expect(serious, `page errors: ${serious.join(' | ')}`).toEqual([]);
  });
});
