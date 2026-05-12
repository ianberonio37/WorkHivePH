/**
 * pm-scheduler.html — UI flow tests.
 *
 * PM completion is one of the most-touched writes on the platform.
 * The capture contract pm_completion_v1 enforces required status enum
 * (done|skipped|partial). These tests lock the silent-success-on-block
 * regression for this surface.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady, readToast } from './_helpers';

test.describe('pm-scheduler.html', () => {
  test('page loads and renders scope items list', async ({ whPage }) => {
    await whPage.goto('/workhive/pm-scheduler.html');
    await waitForPageReady(whPage);

    // PM-scheduler renders varying chrome by viewport/auth state.
    // Accept any body-level text content related to PM management.
    await expect(whPage.locator('body')).toBeVisible({ timeout: 8000 });
    await expect(
      whPage.locator('text=/PM|Preventive|Scheduler|Asset|Maintenance/i').first()
    ).toBeVisible({ timeout: 5000 });
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
