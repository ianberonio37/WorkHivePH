/**
 * shift-brain.html freshness + integrity — interaction-lock test
 * (ASSET_ALERT_SHIFT_DEEP_ARC F14/F15).
 *
 * Locks the three plan-honesty contracts the Asset/Alert/Shift arc added:
 *   1. STALE (F15): a plan whose shift_date is NOT the current shift renders a #brief-stale
 *      badge and an honest source chip — never a hardcoded "Live" claim over a week-old plan.
 *   2. DEGRADED (F14): a plan the orchestrator flagged degraded (payload.degraded / fetch_errors)
 *      renders a #brief-degraded warning — an empty section from a failed fetch must not read
 *      as "all clear" (silent-zero guard).
 *   3. ARCHIVE-HIDE (F15): an archived plan is not selected as the active plan (loadPlan
 *      filters status<>archived), so it can't re-render under an "archived" pill.
 *
 * Seeds plans in the 22-06 window (least likely to be the current local window, so the page's
 * compute-on-first-view auto-generate does NOT overwrite the seeded fixture). Cleans up after.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';
import { adminClient } from './_db-cleanup';

const WINDOW = '22-06';

async function seedPlan(db: any, hiveId: string, shiftDate: string, payload: any, briefing: string) {
  await db.from('shift_plans').upsert({
    hive_id: hiveId, shift_window: WINDOW, shift_date: shiftDate, status: 'draft',
    generated_at: new Date().toISOString(), generated_by: 'shift-planner-orchestrator',
    briefing, payload,
  }, { onConflict: 'hive_id,shift_date,shift_window' });
}

async function openNightWindow(whPage: any) {
  await whPage.goto('/workhive/shift-brain.html');
  await waitForPageReady(whPage);
  await whPage.getByRole('button', { name: /-06 Night/ }).click();
  await whPage.waitForTimeout(2500);
}

test.describe('shift-brain.html plan freshness + integrity', () => {
  test('a stale plan shows the STALE badge, not a "Live" claim', async ({ whPage }) => {
    const db = adminClient();
    const hiveId = await whPage.evaluate(() => localStorage.getItem('wh_active_hive_id'));
    expect(hiveId).toBeTruthy();

    // A week-old plan for the night window (definitely not the current shift).
    await seedPlan(db, hiveId!, '2026-07-05',
      { risk_top: [], pms_due: [], carry_forward: [], parts_prestage: [] },
      'Stale fixture.');
    try {
      await openNightWindow(whPage);
      // If the page auto-regenerated (22-06 happened to be the live window in CI), skip —
      // the fixture would have been replaced by a fresh plan, which is correct behavior.
      const briefDate = await whPage.locator('#brief-date').textContent();
      test.skip(!/jul 5|jul 05/i.test(briefDate || ''), '22-06 auto-regenerated (live window in CI)');
      await expect(whPage.locator('#brief-stale')).toBeVisible();
      const chip = (await whPage.locator('#shift-source-chip').textContent() || '').toLowerCase();
      expect(chip.includes('stale'), `source chip should say STALE, got: "${chip}"`).toBeTruthy();
    } finally {
      await db.from('shift_plans').delete().eq('hive_id', hiveId!).eq('shift_date', '2026-07-05').eq('shift_window', WINDOW);
    }
  });

  test('a degraded plan shows the incomplete-data warning (silent-zero guard)', async ({ whPage }) => {
    const db = adminClient();
    const hiveId = await whPage.evaluate(() => localStorage.getItem('wh_active_hive_id'));
    // Today PHT so it is "fresh" (isolates the degraded banner from the stale badge).
    const phtToday = new Date(Date.now() + 8 * 3600 * 1000).toISOString().slice(0, 10);
    await seedPlan(db, hiveId!, phtToday,
      { risk_top: [], pms_due: [], carry_forward: [], parts_prestage: [], fetch_errors: ['risk_top', 'pms_due'], degraded: true },
      'Degraded fixture.');
    try {
      await openNightWindow(whPage);
      const briefText = await whPage.locator('#brief-text').textContent();
      test.skip(!/degraded fixture/i.test(briefText || ''), '22-06 auto-regenerated (live window in CI)');
      const banner = whPage.locator('#brief-degraded');
      await expect(banner).toBeVisible();
      expect((await banner.textContent() || '').toLowerCase()).toContain('incomplete');
    } finally {
      await db.from('shift_plans').delete().eq('hive_id', hiveId!).eq('shift_date', phtToday).eq('shift_window', WINDOW);
    }
  });

  test('an archived plan is not selected as the active plan', async ({ whPage }) => {
    const db = adminClient();
    const hiveId = await whPage.evaluate(() => localStorage.getItem('wh_active_hive_id'));
    const phtToday = new Date(Date.now() + 8 * 3600 * 1000).toISOString().slice(0, 10);
    // Seed an archived plan for today's night window.
    await db.from('shift_plans').upsert({
      hive_id: hiveId!, shift_window: WINDOW, shift_date: phtToday, status: 'archived',
      generated_at: new Date().toISOString(), generated_by: 'shift-planner-orchestrator',
      briefing: 'Archived fixture — must not render.',
      payload: { risk_top: [], pms_due: [], carry_forward: [], parts_prestage: [] },
    }, { onConflict: 'hive_id,shift_date,shift_window' });
    try {
      await openNightWindow(whPage);
      // The archived briefing text must never appear (loadPlan filters status<>archived).
      const body = await whPage.locator('#brief-text').textContent();
      expect((body || '').includes('Archived fixture'),
        'an archived plan must not render as the active plan').toBeFalsy();
    } finally {
      await db.from('shift_plans').delete().eq('hive_id', hiveId!).eq('shift_date', phtToday).eq('shift_window', WINDOW).eq('status', 'archived');
    }
  });
});
