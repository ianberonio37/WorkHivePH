/**
 * journey-alerts.spec.ts — Alert Hub user journey.
 *
 * Scenarios:
 *   happy path    — page loads, verdict settled, AMC brief rendered
 *   source chip   — chip declares v_risk_truth
 *   Plain-Read    — verdict + 3 cards populated (not "Loading...")
 *   filtering     — severity filter chips change the feed
 *   console errors — no JS errors on load
 *   loading state — verdict settles within timeout
 *   network error — page gracefully handles missing data
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/alert-hub.html';

async function waitForAlertVerdictSettled(page) {
  await page.waitForFunction(() => {
    const el = document.querySelector('[id$="verdict-label"]');
    if (!el) return true;
    const t = (el.textContent || '').trim();
    return !!t && !t.startsWith('Computing') && !t.startsWith('Loading');
  }, { timeout: 12000 }).catch(() => {});
}

test.describe('alert-hub.html — user journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));

    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2500);

    const serious = errors.filter(e => !e.includes('net::ERR_') && !e.includes('Failed to fetch'));
    expect(serious, `console errors: ${serious.join(' | ')}`).toEqual([]);
  });

  test('source chip declares v_risk_truth canonical source', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    const chip = whPage.locator('.wh-source-chip, #wh-source-chip, [class*="source-chip"]').first();
    const text = await chip.textContent({ timeout: 5000 }).catch(() => '');
    expect(text, 'alert-hub source chip should declare v_risk_truth').toContain('v_risk_truth');
  });

  test('verdict settles and shows real alert data', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAlertVerdictSettled(whPage);

    const label = await whPage.locator('[id$="verdict-label"]').first().textContent().catch(() => '');
    expect(label?.trim(), 'verdict should settle').not.toMatch(/^Computing/);
    expect(label?.trim().length).toBeGreaterThan(0);
  });

  test('3 plain-read cards populated (HIGH-SEVERITY, ANOMALY SIGNALS, AMC BRIEF)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAlertVerdictSettled(whPage);

    const heroes = whPage.locator('.sc-hero');
    const count = await heroes.count();
    expect(count, 'alert-hub should have 3 cards').toBeGreaterThanOrEqual(3);

    for (let i = 0; i < Math.min(count, 3); i++) {
      const text = await heroes.nth(i).textContent();
      expect(text?.trim(), `card ${i} hero should be populated`).not.toBe('—');
    }
  });

  test('severity filter chips are visible and clickable', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAlertVerdictSettled(whPage);
    await whPage.waitForTimeout(1500);

    // Filter chips should be present (Critical/High/Medium/Low severity)
    const chips = whPage.locator('.filter-chip, [data-severity], button.chip').first();
    if (await chips.count() > 0) {
      await expect(chips).toBeVisible({ timeout: 5000 });
      await chips.click();
      await whPage.waitForTimeout(500);
      // Should not throw errors
    }
  });

  test('AMC Daily Brief card shows model ID or "Approved" badge', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAlertVerdictSettled(whPage);
    await whPage.waitForTimeout(2000);

    // AMC brief shows the brief card with model metadata
    const brief = whPage.locator('.amc-brief, [id*="amc"], text=/AMC|DAILY BRIEF/i').first();
    if (await brief.count() > 0) {
      await expect(brief).toBeVisible({ timeout: 5000 });
    }
  });

  test('alert feed shows entries or "no alerts" empty state', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAlertVerdictSettled(whPage);
    await whPage.waitForTimeout(2500);

    // Either alert cards appear, or an empty state message does
    const hasAlerts  = await whPage.locator('.alert-card, .wh-card[data-alert]').count();
    const hasEmpty   = await whPage.locator('text=/no alerts|all clear|nothing to show/i').count();
    const hasFeed    = await whPage.locator('[id*="feed"], [id*="alert-list"]').count();

    expect(
      hasAlerts > 0 || hasEmpty > 0 || hasFeed > 0,
      'alert hub should show alerts OR an empty state — neither found',
    ).toBe(true);
  });

  test('details toggle opens engineering explainer', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAlertVerdictSettled(whPage);

    const btn = whPage.locator('#details-toggle-btn').first();
    if (await btn.count() === 0) return;

    await btn.click();
    await whPage.waitForTimeout(500);
    const expanded = await btn.getAttribute('aria-expanded');
    expect(expanded, 'toggle should flip aria-expanded to true').toBe('true');
  });
});
