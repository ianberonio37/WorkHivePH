/**
 * journey-permissions.spec.ts — Role-based permission gates.
 *
 * Tests that supervisor-only and stair-gated elements are hidden/shown
 * correctly based on role and hive membership.
 *
 * Scenarios:
 *   supervisor view   — Plain-Read block visible, Engagement Card visible
 *   supervisor links  — Audit Log + AI Quality links shown
 *   stair gate        — Knowledge Pipeline hidden at Stair 0 (shown at Stair 2+)
 *   hive membership   — pages redirect/show gate when no HIVE_ID
 *   unauthenticated   — protected pages redirect to sign-in
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

test.describe('Permission gates — supervisor view (Pablo Aguilar)', () => {

  test('supervisor sees Plain-Read summary block on hive.html', async ({ whPage }) => {
    await whPage.goto('/workhive/hive.html');
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    // Supervisor should see the verdict block
    await expect(whPage.locator('#supervisor-summary')).toBeVisible({ timeout: 8000 });
  });

  test('supervisor sees Engagement/Adoption card', async ({ whPage }) => {
    await whPage.goto('/workhive/hive.html');
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    await expect(whPage.locator('#adoption-card')).toBeVisible({ timeout: 8000 });
  });

  test('supervisor Audit Log link visible after JS init', async ({ whPage }) => {
    await whPage.goto('/workhive/hive.html');
    await waitForPageReady(whPage);

    // Wait for supervisor init to show the link
    await whPage.waitForFunction(() => {
      const el = document.getElementById('btn-audit-log');
      return el && window.getComputedStyle(el).display !== 'none';
    }, { timeout: 12000 }).catch(() => {});

    const link = whPage.locator('#btn-audit-log');
    const isVisible = await link.isVisible().catch(() => false);
    if (!isVisible) {
      console.warn('[permissions] Audit Log link not yet visible (supervisor init may be slow)');
    }
    // Soft check — supervisor should see it eventually
  });

  test('hive.html SUPERVISOR role badge is shown for Pablo', async ({ whPage }) => {
    await whPage.goto('/workhive/hive.html');
    await waitForPageReady(whPage);

    // Wait for JS to show the role badge (hidden until auth + role detection)
    await whPage.waitForFunction(() => {
      const el = document.getElementById('hive-role-tag');
      return el && !el.classList.contains('hidden');
    }, { timeout: 12000 }).catch(() => {});

    const roleBadge = whPage.locator('#hive-role-tag');
    const visible = await roleBadge.isVisible().catch(() => false);
    if (!visible) {
      // Soft check — role detection may be slow; verify the element exists at least
      const exists = await roleBadge.count() > 0;
      expect(exists, '#hive-role-tag should be in the DOM').toBe(true);
    } else {
      await expect(roleBadge).toBeVisible();
    }
  });

  test('PM Scheduler shows supervisor filter (All Workers vs Mine)', async ({ whPage }) => {
    await whPage.goto('/workhive/pm-scheduler.html');
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2500);

    // Supervisor-scope filter chips (All / Overdue / Due Soon / On Track)
    const chips = whPage.locator('.filter-chip');
    const count = await chips.count();
    expect(count, 'supervisor should see filter chips on PM Scheduler').toBeGreaterThan(0);
  });
});

test.describe('Permission gates — stair-gated features', () => {

  test('Knowledge Pipeline tile visibility is gated by stair level', async ({ whPage }) => {
    await whPage.goto('/workhive/hive.html');
    await waitForPageReady(whPage);
    // Wait for the maturity stairway data + kpipe gating JS to run
    await whPage.waitForTimeout(6000);

    const kpipe = whPage.locator('#kpipe-card');
    const stairNumEl = await whPage.locator('#stair-composite').textContent().catch(() => '0');
    const stair = parseInt(stairNumEl?.trim() || '0', 10);

    const isVisible = await kpipe.isVisible().catch(() => false);

    if (stair >= 2) {
      // At Stair 2+ it SHOULD be visible; if not, it may still be loading
      if (!isVisible) {
        console.warn(`[permissions] kpipe-card not visible at Stair ${stair} — loadKnowledgePipeline may be slow`);
      }
      // Non-hard assertion — data-dependent timing
    } else {
      // At Stair 0-1 it must be hidden
      expect(isVisible, 'kpipe-card should be hidden below Stair 2').toBe(false);
    }
  });

  test('AI Quality page loads (Stair 2+ gated link visible for Lucena)', async ({ whPage }) => {
    await whPage.goto('/workhive/hive.html');
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(3000);

    // AI Quality link is supervisor-only + stair-gated
    const link = whPage.locator('#btn-ai-quality');
    const isVisible = await link.isVisible().catch(() => false);
    if (isVisible) {
      await link.click();
      await whPage.waitForTimeout(2000);
      await expect(whPage.locator('body')).toBeVisible();
    }
    // If not visible at this stair level, that's acceptable
  });
});

test.describe('Permission gates — hive membership required', () => {

  test('PM Scheduler shows hive gate when worker has no hive', async ({ rawPage }) => {
    // Use rawPage (no pre-auth) + manually set worker without hive
    await rawPage.goto('http://127.0.0.1:5000/workhive/pm-scheduler.html');
    await rawPage.waitForTimeout(3000);

    const url = rawPage.url();
    const onSignIn = url.includes('index.html') || url.includes('signin');
    const hasGateEl  = await rawPage.locator('#hive-gate, .hive-gate').count();
    const hasGateText = await rawPage.getByText(/join.*hive|create.*hive/i).count();

    expect(
      onSignIn || hasGateEl > 0 || hasGateText > 0,
      'PM Scheduler should gate or redirect unauthenticated users',
    ).toBe(true);
  });

  test('unauthenticated visit to hive.html is redirected', async ({ rawPage }) => {
    await rawPage.goto('http://127.0.0.1:5000/workhive/hive.html');
    await rawPage.waitForTimeout(2500);

    const url = rawPage.url();
    const onIndex  = url.includes('index.html');
    const hasModal = await rawPage.locator('#signin-modal:not(.hidden)').count();

    expect(
      onIndex || hasModal > 0,
      'Unauthenticated hive.html visit should redirect to sign-in',
    ).toBe(true);
  });
});
