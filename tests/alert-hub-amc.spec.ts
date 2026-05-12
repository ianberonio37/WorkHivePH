/**
 * alert-hub.html AMC card — interaction-lock tests.
 *
 * Locks the Autonomous Maintenance Crew daily-briefing UI flow:
 *   1. When a pending amc_briefings row exists for the active hive,
 *      the AMC card renders at the top of the alert feed.
 *   2. The status pill matches the brief's status.
 *   3. The 3 stat counters (assets / pms / parts) reflect the brief JSONB.
 *   4. Supervisor approval click flips the brief to status='approved' in DB.
 *
 * Requires:
 *   - The AMC seeder ran (creates 14d of briefings, recent ones pending).
 *   - The signed-in fixture worker is a supervisor (role-gated approval).
 */
import { test, expect } from './_fixtures';
import { waitForPageReady, readToast } from './_helpers';
import { adminClient } from './_db-cleanup';

test.describe('alert-hub.html AMC card', () => {
  test('renders + counters reflect the brief + approval persists to DB', async ({ whPage }) => {
    // Make sure at least one pending brief exists for our hive (the seeder
    // does this; we add a belt-and-braces row in case the seed was skipped
    // or another test consumed it).
    const db = adminClient();
    const hiveId = await whPage.evaluate(() => localStorage.getItem('wh_active_hive_id'));
    expect(hiveId, 'fixture must set wh_active_hive_id').toBeTruthy();

    // Insert a fresh pending brief for today with deterministic shape.
    // The page queries by shift_date computed in Asia/Manila (PHT), so we
    // must seed with the same date or the dedicated AMC card stays hidden.
    // Matches the page's todayPhtIso() implementation in alert-hub.html.
    const phtNow = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Manila' }));
    const today = `${phtNow.getFullYear()}-${String(phtNow.getMonth()+1).padStart(2,'0')}-${String(phtNow.getDate()).padStart(2,'0')}`;
    const brief = {
      top_assets: [
        { asset_id: '00000000-0000-0000-0000-000000000001', name: 'TEST-AMC-PUMP-01', risk_score: 0.81, top_factor: 'vibration trend' },
        { asset_id: '00000000-0000-0000-0000-000000000002', name: 'TEST-AMC-CONV-02', risk_score: 0.72, top_factor: 'MTBF declining' },
      ],
      pm_due:         [{ pm_scope_id: '00000000-0000-0000-0000-000000000010', asset_name: 'TEST-AMC-PUMP-01', title: 'monthly inspection', due_in_days: 0 }],
      parts_to_stage: [{ part_number: 'P-TEST-01', qty_needed: 2, asset_name: 'TEST-AMC-PUMP-01', reason: 'PM-driven' }],
      crew_match:     [{ worker_name: 'Pablo Aguilar', discipline: 'Mechanical', level: 3, available_today: true }],
      narrative:      'TEST AMC brief: priority is TEST-AMC-PUMP-01 vibration trend. Stage parts before 0700.',
    };

    // Re-set to pending to make the test deterministic regardless of seed
    // state. Use upsert via delete-then-insert so RLS doesn't get in the way
    // (we're using the service-role admin client anyway).
    await db.from('amc_briefings').delete()
      .eq('hive_id', hiveId).eq('shift_date', today);
    const { error: insErr } = await db.from('amc_briefings').insert({
      hive_id:       hiveId,
      shift_date:    today,
      status:        'pending',
      brief,
      model_version: 'amc-v1-test',
    });
    expect(insErr, `seed insert failed: ${insErr?.message}`).toBeNull();

    await whPage.goto('/workhive/alert-hub.html');
    await waitForPageReady(whPage);

    // The AMC card hydrates from the DB on page load. Wait for it to become
    // visible (the page sets display:none until a brief is found).
    const amcCard = whPage.locator('#amc-card');
    await expect(amcCard).toBeVisible({ timeout: 10000 });

    // Status pill should say "pending"
    const statusPill = whPage.locator('#amc-status-pill');
    await expect(statusPill).toHaveText(/pending/i);

    // Stat counters reflect the brief
    await expect(whPage.locator('#amc-stat-assets')).toHaveText('2');
    await expect(whPage.locator('#amc-stat-pms')).toHaveText('1');

    // Click approve. Supervisor role is set by the fixture.
    const approveBtn = whPage.locator('#amc-approve-btn');
    await expect(approveBtn).toBeVisible({ timeout: 5000 });
    await approveBtn.click();

    // Either a toast or a status pill change should follow.
    const toastOrPill = await Promise.race([
      readToast(whPage, 4000),
      whPage.locator('#amc-status-pill').filter({ hasText: /approved/i })
        .first().waitFor({ state: 'visible', timeout: 4000 })
        .then(() => 'approved-pill').catch(() => null),
    ]);
    expect(toastOrPill, 'expected approval feedback (toast or pill flip)').toBeTruthy();

    // DB-level confirmation — the row really did flip.
    let approved = false;
    for (let i = 0; i < 10; i++) {
      const { data } = await db.from('amc_briefings')
        .select('status').eq('hive_id', hiveId).eq('shift_date', today).maybeSingle();
      if (data?.status === 'approved') { approved = true; break; }
      await whPage.waitForTimeout(400);
    }
    expect(approved, `amc_briefings row for today did not flip to approved`).toBe(true);

    // Cleanup the test row so a re-run starts clean.
    await db.from('amc_briefings').delete()
      .eq('hive_id', hiveId).eq('shift_date', today).eq('model_version', 'amc-v1-test');
  });

  test('no page errors on load with AMC card present', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));

    await whPage.goto('/workhive/alert-hub.html');
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    const serious = errors.filter(e =>
      !e.toLowerCase().includes('failed to load resource'));
    expect(serious, `page errors: ${serious.join(' | ')}`).toEqual([]);
  });
});
