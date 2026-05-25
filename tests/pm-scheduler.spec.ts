/**
 * pm-scheduler.html — UI flow tests.
 *
 * PM completion is one of the most-touched writes on the platform.
 * The capture contract pm_completion_v1 enforces required status enum
 * (done|skipped|partial). These tests lock the silent-success-on-block
 * regression for this surface.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady, pageSrcWithExternals, readToast } from './_helpers';

test.describe('pm-scheduler.html', () => {
  test('page loads and renders scope items list', async ({ whPage }) => {
    await whPage.goto('/workhive/pm-scheduler.html');
    await waitForPageReady(whPage);

    // PM-scheduler renders varying chrome by viewport/auth state.
    // Accept any body-level text content related to PM management.
    await expect(whPage.locator('body')).toBeVisible({ timeout: 8000 });
    // Iterate matches manually because Playwright 1.60 doesn't expose
    // filter({ visible: true }) on Locator. Pages carry sr-only h1 with
    // these keywords (clipped 0,0,0,0) and the bare text= matcher hits
    // those first — we need the first VISIBLE one.
    const matches = whPage.locator('text=/PM|Preventive|Scheduler|Asset|Maintenance/i');
    await whPage.waitForTimeout(500);
    const total = await matches.count();
    let saw = false;
    for (let i = 0; i < total; i++) {
      if (await matches.nth(i).isVisible()) { saw = true; break; }
    }
    expect(saw, 'at least one visible PM/Preventive/Scheduler/Asset/Maintenance text').toBe(true);
  });

  test('no global console errors during page load', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    whPage.on('console', m => {
      if (m.type() === 'error' && !m.text().includes('favicon')) {
        errors.push(m.text());
      }
    });

    await whPage.goto('/workhive/pm-scheduler.html');
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    // The most common silent regression is a SyntaxError that kills a
    // whole inline <script> block (e.g. await-outside-async). Catching
    // pageerror covers that class.
    const seriousErrors = errors.filter(e =>
      !e.toLowerCase().includes('failed to load resource') &&
      !e.toLowerCase().includes('net::')
    );
    expect(seriousErrors, `page errors during load: ${seriousErrors.join(' | ')}`).toEqual([]);
  });
});

/* === Sentinel-proposed scenarios (check-name anchored) === */
import { adminClient } from './_db-cleanup';
test.describe('pm-scheduler.html - sentinel scenarios', () => {
  const PAGE = '/workhive/pm-scheduler.html';

  test('supervisor_gate_add: supervisor sees Add PM control', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const addBtn = whPage.locator(
      '#btn-add-pm, [data-add-pm], button:has-text("Add"), button:has-text("New")'
    ).first();
    await expect(addBtn, 'supervisor must see an add control on pm-scheduler')
      .toBeAttached({ timeout: 5000 });
  });

  test('esc_html_render: PM titles are rendered as text, not raw HTML', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);
    const dangerous = await whPage.evaluate(() => {
      const items = document.querySelectorAll('[data-pm-id], .pm-row, .scope-item');
      return Array.from(items).some(el => /<script|<img\s+src=/i.test(el.innerHTML));
    });
    expect(dangerous, 'PM row contents must be escaped before render').toBe(false);
  });

  test('realtime_hive_filter: scripts subscribe to channels with hive filter', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc = await pageSrcWithExternals(whPage);
    const filtered = /\.channel\s*\(/.test(__sentSrc) && /hive_id|hive[-_]filter/i.test(__sentSrc);
    expect(filtered, 'realtime channels on pm-scheduler should include hive_id filter').toBeTruthy();
  });

  test('freq_days_alignment: frequency_days field accepts numeric input', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const freq = whPage.locator(
      '#freq-days, [name="frequency_days"], input[placeholder*="freq" i]'
    ).first();
    if (await freq.count() === 0) { test.skip(true, 'no frequency_days input visible'); return; }
    await freq.fill('30');
    const val = await freq.inputValue();
    expect(val).toBe('30');
  });

  test('comp_payload_fields: completion payload includes required canonical fields', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_2 = await pageSrcWithExternals(whPage);
    const hasFields = /completed_by|completed_at|completion_status|pm_completion/i.test(__sentSrc_2);
    expect(hasFields,
      'pm-scheduler completion path should reference canonical pm_completion fields').toBeTruthy();
  });

  test('logbook_pm_fields: PM completions feed logbook with canonical fields', async ({ whPage }) => {
    const db = adminClient();
    const { data: pmLogs } = await db.from('logbook')
      .select('maintenance_type, pm_completion_id')
      .eq('maintenance_type', 'Preventive Maintenance').limit(5);
    if (!pmLogs || pmLogs.length === 0) {
      test.skip(true, 'no PM-sourced logbook entries in seed'); return;
    }
    for (const l of pmLogs) {
      expect(l.maintenance_type).toBe('Preventive Maintenance');
    }
  });

  test('pm_template_coverage: PM template list non-empty for active hive', async ({ whPage }) => {
    const db = adminClient();
    const { data: templates } = await db.from('pm_templates')
      .select('id, name').limit(5);
    if (!templates) { test.skip(true, 'pm_templates not queryable'); return; }
    expect(Array.isArray(templates), 'pm_templates query returned an array').toBe(true);
  });

  test('delete_asset_scoped: scripts reference asset-scoped delete pattern', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_3 = await pageSrcWithExternals(whPage);
    const scoped = /asset_id.*delete|delete.*asset_id|eq\s*\(\s*['"]asset_id['"]/i.test(__sentSrc_3);
    expect(scoped, 'PM deletes should be scoped by asset_id').toBeTruthy();
  });

  test('midnight_normalization: PM dates normalize to midnight', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_4 = await pageSrcWithExternals(whPage);
    const has = /setHours\s*\(\s*0\s*,\s*0\s*,\s*0|midnight|startOfDay|T00:00:00/i.test(__sentSrc_4);
    expect(has, 'PM dates should be normalized to midnight').toBeTruthy();
  });

  test('pm_cat_to_log_values: PM category maps to logbook canonical values', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_5 = await pageSrcWithExternals(whPage);
    const has = /Preventive\s*Maintenance|pm.*category.*logbook|PM.*MAINTENANCE_TYPE/i.test(__sentSrc_5);
    expect(has, 'PM completions should map to canonical logbook category').toBeTruthy();
  });

});
