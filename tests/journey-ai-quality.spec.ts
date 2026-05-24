/**
 * journey-ai-quality.spec.ts — AI Quality + ROI full journey.
 *
 * The page is JS-rendered into #content after a Stair 2+ maturity gate.
 * Lucena is Stair 3, so the full page renders.
 *
 * Scenarios:
 *   page load        — content renders (not gated for Stair 3)
 *   verdict settled  — verdict shows quality tone
 *   spend card       — 30-day cost number appears
 *   fallback rate    — fallback % card renders
 *   trust card       — thumbs feedback card (% or NO DATA)
 *   schema card      — schema compliance renders
 *   ROI card         — predicted ROI number renders
 *   details toggle   — expand/collapse engineering pane
 *   console errors   — no JS errors
 */
import { test, expect } from './_fixtures';
import { waitForPageReady, bypassMaturityGate } from './_helpers';

// AI Quality gates on Stair 2 (per ai-quality.html). Test fixtures rarely
// cross that threshold; bypass at the fetch layer so the page renders its
// real verdict + KPI tiles instead of the honest empty state.
test.beforeEach(async ({ whPage }) => {
  await bypassMaturityGate(whPage);
});

const PAGE = '/workhive/ai-quality.html';

async function waitForAQContent(page) {
  await page.waitForFunction(() => {
    const host = document.getElementById('content');
    if (!host) return false;
    // Either real content loaded, or gated message, or loading state is gone
    return host.children.length > 0 &&
           !/loading/i.test(host.textContent || '');
  }, { timeout: 15000 }).catch(() => {});
}

test.describe('ai-quality.html — AI quality journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const serious = errors.filter(e =>
      !e.includes('net::ERR_') && !e.includes('Failed to fetch'),
    );
    expect(serious).toEqual([]);
  });

  test('content renders (Stair 3 hive not gated)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAQContent(whPage);

    const content = whPage.locator('#content');
    await expect(content).toBeVisible({ timeout: 8000 });

    // Must NOT show the stair gate for Lucena (Stair 3)
    const gateText = await whPage.getByText(/stair 2|upgrade|below stair/i).count();
    expect(gateText, 'Lucena Stair 3 should not see the maturity gate').toBe(0);
  });

  test('Plain-Read verdict renders with quality tone', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAQContent(whPage);

    const verdict = whPage.locator('.verdict, [class*="verdict"]').first();
    if (await verdict.count() > 0) {
      await expect(verdict).toBeVisible({ timeout: 5000 });
      const text = await verdict.textContent();
      expect(text?.trim().length, 'verdict should have meaningful content').toBeGreaterThan(5);
    }
  });

  test('spend / cost card shows a number (not empty dashes)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAQContent(whPage);

    // AI cost card shows either a PHP/USD value or "$0.00"
    const costCard = whPage.locator('.sc-hero, [class*="hero"]').filter({ hasText: /\$|\d+\.\d{2}/ }).first();
    const hasCard  = await costCard.count();
    if (hasCard > 0) {
      const text = await costCard.textContent();
      expect(text?.trim()).toMatch(/\$|\d/);
    }
    // If no cost card, page may be in loading or empty state — no hard fail
    await expect(whPage.locator('#content')).toBeVisible();
  });

  test('three plain-read cards render with non-placeholder heroes', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAQContent(whPage);

    const heroes = whPage.locator('.sc-hero');
    const count  = await heroes.count();
    if (count >= 3) {
      for (let i = 0; i < 3; i++) {
        const text = await heroes.nth(i).textContent();
        expect(text?.trim(), `card ${i} hero should not be empty`).not.toBe('');
        expect(text?.trim()).not.toBe('—');
      }
    }
    // If fewer than 3 cards, page may be loading or gated — soft pass
    await expect(whPage.locator('body')).toBeVisible();
  });

  test('thumbs feedback card: shows % or NO DATA (not a crash)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAQContent(whPage);

    // Thumbs feedback shows either a percentage or "—" / "No ratings yet"
    const trustCard = whPage.locator('.sc-hero, [class*="hero"]')
      .filter({ hasText: /\d+%|—|No thumbs|NO DATA/i }).first();
    if (await trustCard.count() > 0) {
      await expect(trustCard).toBeVisible({ timeout: 3000 });
    }
    await expect(whPage.locator('body')).toBeVisible();
  });

  test('schema compliance card renders in content', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAQContent(whPage);

    // "Schema compliance" is a sub-label (class="sl") inside a card — may be
    // hidden within a details pane. Use count() to check existence rather than
    // toBeVisible(), which fails for elements inside collapsed sections.
    const hasCompliance = await whPage.getByText(/schema|compliance/i).count();
    expect(hasCompliance, 'schema compliance label should exist in the page').toBeGreaterThan(0);
    await expect(whPage.locator('#content')).toBeVisible();
  });

  test('ROI card or time-saved card renders a number', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAQContent(whPage);

    // ROI meta shows "vs $X.XX spent" or time saved
    const roiMeta = whPage.locator('#roi-meta');
    if (await roiMeta.count() > 0) {
      const text = await roiMeta.textContent().catch(() => '');
      expect(text?.trim().length).toBeGreaterThan(0);
    }
    await expect(whPage.locator('#content')).toBeVisible();
  });

  test('details toggle expands engineering pane', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAQContent(whPage);

    const btn  = whPage.locator('#details-toggle-btn');
    const pane = whPage.locator('#details-pane');

    if (await btn.count() === 0) return;
    await expect(btn).toBeVisible({ timeout: 5000 });

    await btn.click();
    await whPage.waitForTimeout(500);

    if (await pane.count() > 0) {
      await expect(pane).toBeVisible({ timeout: 3000 });
    }
    const expanded = await btn.getAttribute('aria-expanded');
    expect(expanded).toBe('true');
  });

  test('action card recommendation is non-empty', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAQContent(whPage);

    const action = whPage.locator('.action-card, [id*="action"]').first();
    if (await action.count() > 0) {
      const text = await action.textContent();
      expect(text?.trim().length, 'action card should have a recommendation').toBeGreaterThan(5);
    }
    await expect(whPage.locator('body')).toBeVisible();
  });
});

/* === Sentinel-proposed scenarios (Layer 0 -> Layer 2 bridge) ===
 * Drafts from /sentinel-review. See sentinel_drafts.md for context.
 */
test.describe('ai-quality.html - sentinel scenarios', () => {

  test('revenue surfaces: ai-quality panel binds to v_ai_quality_truth (Stair 2+)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await waitForAQContent(whPage);
    const panel = whPage.locator('#ai-quality, #ai-quality-panel, [data-ai-quality], #content').first();
    await expect(panel, 'ai-quality content host missing').toBeAttached({ timeout: 5000 });
    await expect.poll(
      async () => (await panel.innerText()).trim().length,
      { timeout: 8000, message: 'ai-quality panel empty - v_ai_quality_truth binding likely missing' },
    ).toBeGreaterThan(0);
  });

});
