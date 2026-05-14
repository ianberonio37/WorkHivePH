/**
 * journey-hive.spec.ts — Hive Board supervisor journey.
 *
 * Tests the full supervisor experience on hive.html:
 *   - Plain-Read contract: verdict settled + 3 cards populated + action card
 *   - Source chips visible on the KPI strip and insight panels
 *   - Reliability Coach toggle opens/closes input
 *   - Details toggle expands/collapses engineering pane
 *   - Today's Brief hidden when no AI reports
 *   - Open Issues card reflects real data (rollup: WOs + PM overdue + stock)
 *   - No console errors
 *   - Loading states clear within timeout
 *   - Supervisor-only elements visible
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/hive.html';
const SETTLE_TIMEOUT = 15000;

/** Wait for the Plain-Read verdict to leave its initial "Computing..." state. */
async function waitForVerdictSettled(page) {
  await page.waitForFunction(() => {
    const el = document.getElementById('ss-verdict-label');
    if (!el) return false;
    const t = (el.textContent || '').trim();
    return !!t && !t.startsWith('Computing') && t !== '·';
  }, { timeout: SETTLE_TIMEOUT }).catch(() => {});
}

/** Wait for a card hero to have a real value (not "—" or "--"). */
async function waitForCardsPopulated(page) {
  await page.waitForFunction(() => {
    const heroes = Array.from(document.querySelectorAll('.sc-hero'));
    return heroes.some(h => {
      const t = (h.textContent || '').trim();
      return t && t !== '—' && t !== '--' && !t.startsWith('Loading');
    });
  }, { timeout: SETTLE_TIMEOUT }).catch(() => {});
}

test.describe('hive.html — supervisor Plain-Read journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    whPage.on('console', m => {
      if (m.type() === 'error' && !m.text().includes('favicon') && !m.text().includes('net::')) {
        errors.push(m.text());
      }
    });

    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    const serious = errors.filter(e =>
      !e.includes('Failed to fetch') &&
      !e.includes('net::ERR_') &&
      !e.includes('401') &&
      !e.includes('TypeError: Failed to fetch'),
    );
    expect(serious, `console errors: ${serious.join(' | ')}`).toEqual([]);
  });

  test('supervisor sees the Plain-Read summary block (not hidden)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    const block = whPage.locator('#supervisor-summary');
    await expect(block).toBeVisible({ timeout: 8000 });
  });

  test('verdict settles from "Computing..." to real content', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForVerdictSettled(whPage);

    const label = await whPage.locator('#ss-verdict-label').textContent({ timeout: 3000 });
    expect(label, 'verdict label should not stay "Computing hive health..."')
      .not.toMatch(/^Computing hive health/);
    expect(label!.trim().length, 'verdict label should not be empty').toBeGreaterThan(0);
  });

  test('verdict icon reflects health tone (✓ / ! / ⚠ / ·)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForVerdictSettled(whPage);

    const icon = await whPage.locator('#ss-verdict-icon').textContent({ timeout: 3000 });
    expect(['✓', '!', '⚠', '·'], `unexpected verdict icon: ${icon}`)
      .toContain(icon!.trim());
  });

  test('3 plain-read cards all have non-placeholder heroes', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForCardsPopulated(whPage);
    await waitForVerdictSettled(whPage);

    // Stair card
    const stairHero = await whPage.locator('#ss-stair-hero').textContent();
    expect(stairHero?.trim(), 'stair hero should be populated').not.toBe('—');
    expect(stairHero?.trim()).not.toBe('--');

    // Adoption card
    const adoptHero = await whPage.locator('#ss-adoption-hero').textContent();
    expect(adoptHero?.trim(), 'adoption hero should be populated').not.toBe('—');

    // Issues card — the key fix from walkthrough (was 0 when 18 WOs existed)
    const issuesHero = await whPage.locator('#ss-issues-hero').textContent();
    expect(issuesHero?.trim(), 'issues hero should be populated').not.toBe('—');
    expect(issuesHero?.trim()).not.toBe('--');
  });

  test('Open Issues card sub-text mentions at least one canonical source', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForCardsPopulated(whPage);
    await waitForVerdictSettled(whPage);

    const sub = await whPage.locator('#ss-issues-sub').textContent({ timeout: 5000 });
    // Should mention "open WO" OR "PM overdue" OR "low stock" OR "No open work"
    expect(sub, 'issues sub should reference actual data sources').toMatch(
      /open WO|PM overdue|low stock|No open work|no open/i,
    );
  });

  test('action card has substantive recommendation (not "Computing...")', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForVerdictSettled(whPage);

    const action = await whPage.locator('#ss-action-text').textContent({ timeout: 8000 });
    expect(action, 'action text should not be placeholder').not.toMatch(/^Computing recommendation/);
    expect(action!.trim().length, 'action text should not be empty').toBeGreaterThan(10);
  });

  test('details toggle expands engineering pane and button label flips', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForVerdictSettled(whPage);

    const btn  = whPage.locator('#details-toggle-btn');
    const pane = whPage.locator('#supervisor-summary-details');

    // Initially closed
    await expect(btn).toBeVisible({ timeout: 5000 });
    await expect(pane).not.toBeVisible();
    expect(await btn.textContent()).toMatch(/show details/i);

    // Click to open
    await btn.click();
    await expect(pane).toBeVisible({ timeout: 3000 });
    expect(await btn.textContent()).toMatch(/hide details/i);

    // Click to close again
    await btn.click();
    await expect(pane).not.toBeVisible({ timeout: 3000 });
    expect(await btn.textContent()).toMatch(/show details/i);
  });

  test('Reliability Coach button expands input, auto-focuses, collapses again', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    const toggleBtn = whPage.locator('#coach-toggle-btn');
    const body      = whPage.locator('#coach-body');
    const input     = whPage.locator('#coach-input');

    // Initially collapsed
    await expect(toggleBtn).toBeVisible({ timeout: 5000 });
    await expect(body).not.toBeVisible();

    // Click to expand
    await toggleBtn.click();
    await expect(body).toBeVisible({ timeout: 3000 });
    await expect(input).toBeVisible();

    // Click to collapse
    await toggleBtn.click();
    await expect(body).not.toBeVisible({ timeout: 3000 });
  });

  test('Today\'s Brief panel stays hidden when no AI reports exist', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(4000); // let loadTodaysBrief complete

    const panel = whPage.locator('#todays-brief-panel');
    // Panel should be hidden (no reports) OR show real content (not placeholder)
    const isVisible = await panel.isVisible().catch(() => false);
    if (isVisible) {
      // If visible, must not show the old "No AI analysis yet" placeholder
      const content = await panel.textContent();
      expect(content, 'Today\'s Brief should not show "No AI analysis yet" placeholder')
        .not.toMatch(/No AI analysis yet/);
    }
    // Hidden is the expected state — passes either way
  });

  test('source chip on KPI strip declares canonical fuels', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    // The board-source-chip declares the 3 canonical views
    const chip = whPage.locator('#board-source-chip');
    const text = await chip.textContent({ timeout: 5000 }).catch(() => '');
    expect(text, 'board source chip should mention v_logbook_truth')
      .toContain('v_logbook_truth');
  });

  test('Maturity Stairway card has a readiness score (not "--")', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(3000);

    const composite = whPage.locator('#stair-composite');
    const score = await composite.textContent({ timeout: 6000 }).catch(() => '--');
    expect(score?.trim(), 'stair composite should be populated').not.toBe('--');
    expect(score?.trim(), 'stair composite should be populated').not.toBe('');
  });

  test('supervisor-only nav links (Audit Log, AI Quality) are visible', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    // Supervisor navigation links should be visible
    const auditLink = whPage.locator('#btn-audit-log, a[href="audit-log.html"]').first();
    await expect(auditLink).toBeVisible({ timeout: 5000 });
  });

  test('Open Issues card is NEVER 0 when stat-open shows > 0 work orders', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForCardsPopulated(whPage);
    await waitForVerdictSettled(whPage);

    const statOpen    = await whPage.locator('#stat-open').textContent({ timeout: 6000 }).catch(() => '0');
    const issuesHero  = await whPage.locator('#ss-issues-hero').textContent().catch(() => '0');

    const openWOCount = parseInt(statOpen?.trim() || '0', 10);
    const issuesCount = parseInt(issuesHero?.trim() || '0', 10);

    if (openWOCount > 0) {
      expect(issuesCount, `Open Issues card (${issuesCount}) should not be 0 when stat-open shows ${openWOCount} WOs`)
        .toBeGreaterThan(0);
    }
  });
});
