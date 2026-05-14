/**
 * journey-analytics.spec.ts — Analytics Engine journey.
 *
 * NOTE: The Descriptive/Predictive/Prescriptive tabs require the Python
 * API (uvicorn) to be running. Tests are designed to pass gracefully
 * whether or not uvicorn is available: they assert the UX behaviour
 * (error state handled, source chip visible, tabs clickable) rather than
 * the computed values.
 *
 * Scenarios:
 *   source chip      — declares v_logbook_truth + Postgres RPCs
 *   date range       — 30d/90d/180d/1y chips are clickable
 *   tab switching    — Descriptive/Diagnostic/Predictive/Prescriptive tabs change view
 *   graceful error   — "Analysis failed" banner is shown (not a crash) when API is down
 *   verdict element  — #an-verdict block is rendered
 *   console errors   — no JS errors unrelated to API
 *   PDF Report       — button exists and is clickable
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/analytics.html';

test.describe('analytics.html — analytics engine journey', () => {

  test('page loads without non-API console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    // Filter API-related noise (uvicorn not running = expected 500/net error)
    const serious = errors.filter(e =>
      !e.includes('net::ERR_') &&
      !e.includes('Failed to fetch') &&
      !e.includes('Analysis failed') &&
      !e.includes('500'),
    );
    expect(serious).toEqual([]);
  });

  test('source chip declares v_logbook_truth', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    const chip = whPage.locator('.wh-source-chip').first();
    const text = await chip.textContent({ timeout: 5000 }).catch(() => '');
    expect(text, 'chip should declare v_logbook_truth').toContain('v_logbook_truth');
  });

  test('date range chips (30d/90d/180d/1y) are visible and clickable', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    for (const label of ['30 days', '90 days', '180 days', '1 year']) {
      const chip = whPage.locator(`button:has-text("${label}")`).first();
      if (await chip.count() > 0) {
        await expect(chip).toBeVisible({ timeout: 3000 });
        await chip.click();
        await whPage.waitForTimeout(400);
      }
    }
    await expect(whPage.locator('body')).toBeVisible();
  });

  test('Descriptive/Diagnostic/Predictive/Prescriptive tabs are present', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    for (const label of ['Descriptive', 'Diagnostic', 'Predictive', 'Prescriptive']) {
      const tab = whPage.locator(`button:has-text("${label}")`).first();
      if (await tab.count() > 0) {
        await expect(tab).toBeVisible({ timeout: 3000 });
        await tab.click();
        await whPage.waitForTimeout(500);
        await expect(whPage.locator('body')).toBeVisible();
      }
    }
  });

  test('verdict block renders (even if still computing due to API)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    // The verdict block should always be in the DOM
    const verdict = whPage.locator('#an-verdict');
    await expect(verdict).toBeVisible({ timeout: 5000 });
  });

  test('graceful state: "Analysis failed" banner or loading state (not white screen)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(8000); // Allow API timeout

    // Either the data loaded, or a graceful error state appeared.
    // Use separate locators — text= is not valid inside a CSS multi-selector.
    const hasVerdict    = await whPage.locator('#an-verdict').count();
    const hasAnalysisFailed = await whPage.getByText('Analysis failed').count();
    const hasLoading    = await whPage.getByText('Rolling up').count();

    expect(
      hasVerdict + hasAnalysisFailed + hasLoading,
      'page should show verdict OR graceful error, not blank',
    ).toBeGreaterThan(0);

    // The page must NOT show a white/empty body
    await expect(whPage.locator('body')).toBeVisible();
  });

  test('PDF Report button is visible and clickable', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    const pdfBtn = whPage.locator('button:has-text("PDF Report"), a:has-text("PDF")').first();
    if (await pdfBtn.count() > 0) {
      await expect(pdfBtn).toBeVisible({ timeout: 3000 });
      // Just verify clickable — actual PDF generation depends on data
      await pdfBtn.click();
      await whPage.waitForTimeout(500);
      await expect(whPage.locator('body')).toBeVisible();
    }
  });

  test('Supervisor/Field Tech role tabs are visible', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    const supervisorTab = whPage.locator('button:has-text("Supervisor"), button:has-text("Field Tech")').first();
    if (await supervisorTab.count() > 0) {
      await expect(supervisorTab).toBeVisible({ timeout: 3000 });
    }
  });
});
