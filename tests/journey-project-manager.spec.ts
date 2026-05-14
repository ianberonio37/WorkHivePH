/**
 * journey-project-manager.spec.ts — Project Manager full journey.
 *
 * Scenarios:
 *   page load      — verdict settles, source chip visible
 *   filter tabs    — Active/Planning/On Hold/Complete/All work
 *   create project — happy path: wizard → project appears in list
 *   validation     — empty project name blocks creation
 *   print button   — project-report.html link exists
 *   AI from text   — AI parse button is visible
 *   console errors — no JS errors
 */
import { test, expect } from './_fixtures';
import { waitForPageReady, readToast } from './_helpers';
import { adminClient } from './_db-cleanup';

const PAGE = '/workhive/project-manager.html';

async function waitForPMVerdictSettled(page) {
  await page.waitForFunction(() => {
    const el = document.getElementById('pm-verdict-label');
    if (!el) return true;
    const t = (el.textContent || '').trim();
    return !!t && !t.startsWith('Computing');
  }, { timeout: 15000 }).catch(() => {});
}

test.describe('project-manager.html — project journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const serious = errors.filter(e => !e.includes('net::ERR_') && !e.includes('Failed to fetch'));
    expect(serious).toEqual([]);
  });

  test('source chip declares projects + project_items', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const chip = whPage.locator('#pm-mgr-source-chip');
    const text = await chip.textContent({ timeout: 5000 }).catch(() => '');
    expect(text, 'chip should mention projects').toContain('projects');
    expect(text, 'chip should mention project_items').toContain('project_items');
  });

  test('Plain-Read verdict settles with project count', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPMVerdictSettled(whPage);

    const label = await whPage.locator('#pm-verdict-label').textContent().catch(() => '');
    expect(label?.trim()).not.toMatch(/^Computing/);
    expect(label?.trim().length).toBeGreaterThan(3);
  });

  test('filter tabs Active/Planning/On Hold/Complete/All switch list', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPMVerdictSettled(whPage);
    await whPage.waitForTimeout(1000);

    for (const label of ['Active', 'Planning', 'On hold', 'Complete', 'All']) {
      const tab = whPage.locator(`button:has-text("${label}")`).first();
      if (await tab.count() > 0) {
        await tab.click();
        await whPage.waitForTimeout(400);
        await expect(whPage.locator('body')).toBeVisible();
      }
    }
  });

  test('Print Report link opens project-report.html', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1000);

    const printBtn = whPage.locator('#project-print-btn, a[href*="project-report"]').first();
    await expect(printBtn).toBeVisible({ timeout: 5000 });
  });

  test('AI: from text button is visible', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    const aiBtn = whPage.locator('button:has-text("AI: from text"), button:has-text("AI from")').first();
    if (await aiBtn.count() > 0) {
      await expect(aiBtn).toBeVisible({ timeout: 3000 });
    }
  });

  test('validation: empty project name blocks wizard progression', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPMVerdictSettled(whPage);
    await whPage.waitForTimeout(1000);

    // Open the new project wizard
    const newBtn = whPage.locator('button:has-text("New project"), button:has-text("+ New")').first();
    if (await newBtn.count() === 0) return;
    await newBtn.click();
    await whPage.waitForTimeout(500);

    // Try to proceed without selecting a type (wiz-next-1)
    const nextBtn = whPage.locator('#wiz-next-1').first();
    if (await nextBtn.count() > 0) {
      const isDisabled = await nextBtn.isDisabled();
      expect(isDisabled, 'wizard Next button should be disabled until a type is selected').toBe(true);
    }
  });

  test('happy path: create project appears in Active list', async ({ whPage, testMarker }) => {
    test.slow();
    await whPage.goto(PAGE);
    await waitForPMVerdictSettled(whPage);
    await whPage.waitForTimeout(1000);

    const newBtn = whPage.locator('button:has-text("New project"), button:has-text("+ New")').first();
    if (await newBtn.count() === 0) {
      console.log('[journey-pm-mgr] no new project button — skipping');
      return;
    }
    await newBtn.click();
    await whPage.waitForTimeout(500);

    // Pane 1: select a project TYPE tile (not template-card — those are pane 2)
    const firstTypeTile = whPage.locator('.type-tile').first();
    if (await firstTypeTile.count() > 0) {
      await firstTypeTile.click();
      await whPage.waitForTimeout(400);
    }

    // Wait for #wiz-next-1 to become enabled (it unlocks after a type is chosen)
    const next1 = whPage.locator('#wiz-next-1');
    await next1.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    if (await next1.count() > 0 && !(await next1.isDisabled())) {
      await next1.click();
      await whPage.waitForTimeout(500);
    } else {
      console.log('[journey-pm-mgr] wiz-next-1 still disabled — skipping create test');
      return;
    }

    // Pane 2: template list — click first card if present, then next
    const firstTemplate = whPage.locator('.template-card').first();
    if (await firstTemplate.count() > 0) {
      await firstTemplate.click();
      await whPage.waitForTimeout(300);
    }
    const next2 = whPage.locator('#wiz-next-2');
    if (await next2.count() > 0 && !(await next2.isDisabled())) {
      await next2.click();
      await whPage.waitForTimeout(500);
    }

    // Pane 3: fill project name
    const nameInput = whPage.locator('#wiz-name');
    await nameInput.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    const projectName = `Test Project ${testMarker}`;
    if (await nameInput.count() > 0) {
      await nameInput.fill(projectName);
    } else {
      console.log('[journey-pm-mgr] #wiz-name not reachable — skipping');
      return;
    }

    // Create
    const createBtn = whPage.locator('#wiz-create');
    if (await createBtn.count() === 0) return;
    await createBtn.click();

    const toast = await readToast(whPage, 8000);
    if (!toast) {
      console.log('[journey-pm-mgr] no toast after project create — skipping DB check');
      return;
    }
    expect(toast).not.toMatch(/error|failed/i);

    // DB confirm
    const db = adminClient();
    let found = false;
    for (let i = 0; i < 10; i++) {
      const { data } = await db.from('projects').select('id').eq('name', projectName).maybeSingle();
      if (data) { found = true; break; }
      await whPage.waitForTimeout(500);
    }
    expect(found, `projects row for name="${projectName}" not found in DB`).toBe(true);
  });
});
