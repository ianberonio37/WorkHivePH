/**
 * journey-notebooklm.spec.ts — NotebookLM Long-Form Lane UI journey.
 *
 * Verifies the in-dashboard NotebookLM panel that lives inside the
 * Flask video marketing app (port 5001 by default — distinct from the
 * WorkHive seeder on 5000). Tests both the happy path (panel renders +
 * existing artifacts stream) and every error category (auth expired,
 * quota exceeded, library missing) via API route mocking so we never
 * have to burn real NotebookLM quota or wait for a real expired session.
 *
 * Scenarios:
 *   - Sidebar lists ideas
 *   - Selecting an idea reveals the NotebookLM panel
 *   - Existing artifacts load from /api/ideas/<id>/notebooklm/status
 *   - Audio cards expose a working /api/notebooklm/<id>/<file> URL
 *   - Download link appends ?download=1
 *   - error_kind=auth_expired → 🔑 Re-authenticate Now button rendered
 *   - error_kind=quota_exceeded → amber "daily quota hit" banner rendered
 *   - error_kind=lib_missing → "notebooklm-py library missing" banner
 *   - Click Re-authenticate Now → /relogin called, awaiting state shown
 *   - Mocked relogin/status done + session-check valid → restored state
 *   - Mocked relogin/status error → error banner with output_tail snippet
 *
 * Run standalone (the video marketing app must be running):
 *   npx playwright test tests/journey-notebooklm.spec.ts --project chromium
 *
 * Override the dashboard URL or idea via env if not using defaults:
 *   $env:WH_VIDEO_MARKETING_URL = 'http://localhost:5001'
 *   $env:WH_TEST_IDEA_ID = 'idea_002'
 */
import { test, expect, Page } from '@playwright/test';

const DASHBOARD_URL    = process.env.WH_VIDEO_MARKETING_URL || 'http://localhost:5001';
const IDEA_WITH_ASSETS = process.env.WH_TEST_IDEA_ID || 'idea_002';

// Override baseURL just for this file so we hit the video marketing app
// instead of the WorkHive seeder configured in playwright.config.ts.
test.use({ baseURL: DASHBOARD_URL });

/** Wait until the idea list has rendered cards (not just the loader). */
async function waitForIdeaList(page: Page) {
  await page.waitForSelector('.ideas-list', { timeout: 10_000 });
  // Empty-state copy "Loading ideas..." flips to the real cards once
  // /api/ideas/backlog responds.
  await page.waitForFunction(() => {
    const list = document.getElementById('ideaList');
    if (!list) return false;
    return !list.textContent?.includes('Loading ideas');
  }, { timeout: 15_000 });
}

/** Click the idea card for IDEA_WITH_ASSETS and wait for the panel. */
async function openIdea(page: Page, ideaId: string) {
  // Click via the DOM id (`#card-idea_002`) — that's the reliable handle.
  // Earlier attempts used :has-text matching but the card-id text is
  // CSS-transformed uppercase while textContent stays lowercase.
  await page.locator(`#card-${ideaId}`).click();
  await page.waitForSelector(`#nlmCard-${ideaId}`, { timeout: 10_000 });
}

test.describe('NotebookLM Long-Form Lane — dashboard journey', () => {

  test('sidebar lists ideas without console errors', async ({ page }) => {
    const errs: string[] = [];
    page.on('pageerror', e => errs.push(e.message));
    await page.goto('/');
    await waitForIdeaList(page);
    // Should have at least 1 idea card visible.
    const count = await page.locator('.idea-card').count();
    expect(count, 'sidebar should render at least 1 idea card').toBeGreaterThan(0);
    // Filter out network-only noise (the dashboard occasionally retries
    // /api/* during loading); only fail on real JS errors.
    const serious = errs.filter(e => !e.includes('Failed to fetch') && !e.includes('net::ERR_'));
    expect(serious, 'no uncaught JS errors on dashboard load').toEqual([]);
  });

  test('selecting an idea reveals the NotebookLM panel', async ({ page }) => {
    await page.goto('/');
    await waitForIdeaList(page);
    await openIdea(page, IDEA_WITH_ASSETS);

    // Card heading must be present.
    await expect(page.locator(`#nlmCard-${IDEA_WITH_ASSETS} .nlm-title`)).toContainText('NotebookLM Long-Form Lane');

    // Profile dropdown and primary buttons.
    await expect(page.locator(`#nlmProfile-${IDEA_WITH_ASSETS}`)).toBeVisible();
    await expect(page.locator(`#nlmRunBtn-${IDEA_WITH_ASSETS}`)).toBeVisible();
    await expect(page.locator(`#nlmPrepBtn-${IDEA_WITH_ASSETS}`)).toBeVisible();
  });

  test('existing artifacts render with playable audio + download links', async ({ page }) => {
    // Mock the status endpoint with a known shape so the assertion is
    // deterministic regardless of what's actually on disk for this idea.
    // NOTE: the file paths use forward slashes so loadNlmStatus's
    // split(/[\\/]/) works on both Windows backslash and unix forward
    // slash. JSON-escaped backslashes via the wire sometimes get
    // collapsed by Playwright's body serialization — fwd slashes dodge
    // the issue entirely.
    let statusHits = 0;
    await page.route(`**/api/ideas/${IDEA_WITH_ASSETS}/notebooklm/status`, route => {
      statusHits += 1;
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          idea_id: IDEA_WITH_ASSETS,
          notebook_id: 'test-nb-id',
          title: 'Test idea',
          last_run: 1779576523,
          artifacts: {
            'audio:DEEP_DIVE:james:en': {
              file: `.tmp/notebooklm/${IDEA_WITH_ASSETS}/artifacts/${IDEA_WITH_ASSETS}_audio_deep_dive_long_james_en.mp3`,
              size_bytes: 4766256,
              generated: 1779576171,
            },
            'report:BLOG_POST:en': {
              file: `.tmp/notebooklm/${IDEA_WITH_ASSETS}/artifacts/${IDEA_WITH_ASSETS}_report_blog_post_en.md`,
              size_bytes: 8841,
              generated: 1779576507,
            },
            'mindmap': {
              file: `.tmp/notebooklm/${IDEA_WITH_ASSETS}/artifacts/${IDEA_WITH_ASSETS}_mindmap.json`,
              size_bytes: 3699,
              generated: 1779576523,
            },
          },
        }),
      });
    });

    const consoleErrors: string[] = [];
    page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });
    page.on('pageerror', e => consoleErrors.push('PAGE_ERROR: ' + e.message));

    await page.goto('/');
    await waitForIdeaList(page);
    await openIdea(page, IDEA_WITH_ASSETS);

    // The panel renders TWICE: once on initial selectIdea, again after
    // the script content loads (which re-runs renderProductionKit and
    // re-invokes loadNlmStatus). The second render races with the first
    // render's DOM, so we poll for a stable artifact count rather than
    // racing on a single response.
    await expect.poll(
      () => page.locator(`#nlmArtifacts-${IDEA_WITH_ASSETS} .nlm-artifact`).count(),
      { timeout: 20_000, intervals: [250, 500, 1000] },
    ).toBe(3);
    const grid = page.locator(`#nlmArtifacts-${IDEA_WITH_ASSETS}`);

    // Audio card: filename + KB + audio element + Download link.
    await expect(grid.locator('audio')).toHaveCount(1);
    await expect(grid.locator('audio')).toHaveAttribute('src', /idea_002_audio_deep_dive_long_james_en\.mp3/);

    const audioCard = grid.locator('.nlm-artifact').filter({ hasText: 'audio_deep_dive_long_james_en.mp3' });
    await expect(audioCard).toContainText('AUDIO');

    // Diagnostic — surface if status was never hit or if JS errored.
    expect(statusHits, 'status mock should fire at least once').toBeGreaterThan(0);
    expect(consoleErrors.filter(e => !e.includes('Failed to load resource'))).toEqual([]);

    // Download link must end in ?download=1 (otherwise browser tries to
    // stream inline and the "Download" action doesn't trigger save).
    const dl = audioCard.locator('a:has-text("Download")');
    await expect(dl).toHaveAttribute('href', /\?download=1$/);

    // Mind map and Blog cards have no inline player — just metadata + link.
    const blog = grid.locator('.nlm-artifact').filter({ hasText: 'report_blog_post_en.md' });
    await expect(blog).toContainText('BLOG/REPORT');
    const mindmap = grid.locator('.nlm-artifact').filter({ hasText: 'mindmap.json' });
    await expect(mindmap).toContainText('MIND MAP');
  });

  test('audio file URL is streamable (HTTP 200, audio/mpeg)', async ({ page, request }) => {
    // Hit the real download endpoint without ?download=1 — verifies
    // (a) absolute path resolution works, (b) Flask returns audio/mpeg
    // so <audio> can stream it inline.
    const url = `${DASHBOARD_URL}/api/notebooklm/${IDEA_WITH_ASSETS}/${IDEA_WITH_ASSETS}_audio_deep_dive_long_james_en.mp3`;
    const res = await request.get(url);
    // Either the file exists (200 audio/mpeg) or it's been pruned (404).
    // We accept both — the assertion is just "no 500 internal error".
    expect(res.status(), `download endpoint should not 500 for ${url}`).not.toBe(500);
    if (res.status() === 200) {
      const ct = res.headers()['content-type'] || '';
      expect(ct).toMatch(/audio\/mpeg|audio\/mp4/);
    }
  });

  test('error_kind=auth_expired → Re-authenticate Now button appears', async ({ page }) => {
    // Mock the campaign run + status to simulate an auth-expired result.
    let jobId = '';
    await page.route(`**/api/notebooklm/doctor`, route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ library_installed: true, session_file_ready: true, library_version: '0.4.1' }),
      });
    });
    await page.route(`**/api/ideas/${IDEA_WITH_ASSETS}/notebooklm/run`, route => {
      jobId = 'mock_auth_' + Date.now();
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, job_id: jobId }) });
    });
    await page.route(/\/api\/notebooklm-jobs\//, route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true, status: 'error', error_kind: 'auth_expired',
          message: 'NotebookLM session expired. Reauth via launcher.',
          stage: 'done',
        }),
      });
    });

    await page.goto('/');
    await waitForIdeaList(page);
    await openIdea(page, IDEA_WITH_ASSETS);
    await page.locator(`#nlmRunBtn-${IDEA_WITH_ASSETS}`).click();

    // The banner should show the re-authenticate button.
    await expect(page.locator(`#nlmReloginBtn-${IDEA_WITH_ASSETS}`)).toBeVisible({ timeout: 15_000 });
    await expect(page.locator(`#nlmMsg-${IDEA_WITH_ASSETS}`)).toContainText('session expired', { ignoreCase: true });
  });

  test('error_kind=quota_exceeded → amber quota banner (no re-auth button)', async ({ page }) => {
    await page.route(`**/api/notebooklm/doctor`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ library_installed: true, session_file_ready: true }) });
    });
    await page.route(`**/api/ideas/${IDEA_WITH_ASSETS}/notebooklm/run`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, job_id: 'mock_quota_' + Date.now() }) });
    });
    await page.route(/\/api\/notebooklm-jobs\//, route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true, status: 'error', error_kind: 'quota_exceeded',
          message: 'NotebookLM daily quota hit. Resets at UTC midnight.',
          stage: 'done',
        }),
      });
    });

    await page.goto('/');
    await waitForIdeaList(page);
    await openIdea(page, IDEA_WITH_ASSETS);
    await page.locator(`#nlmRunBtn-${IDEA_WITH_ASSETS}`).click();

    const msg = page.locator(`#nlmMsg-${IDEA_WITH_ASSETS}`);
    await expect(msg).toContainText('quota', { ignoreCase: true, timeout: 15_000 });
    // The quota banner should NOT show the re-auth button.
    await expect(page.locator(`#nlmReloginBtn-${IDEA_WITH_ASSETS}`)).toHaveCount(0);
  });

  test('error_kind=lib_missing → setup hint banner', async ({ page }) => {
    await page.route(`**/api/notebooklm/doctor`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ library_installed: false, session_file_ready: false, library_error: 'No module named notebooklm' }) });
    });
    await page.goto('/');
    await waitForIdeaList(page);
    await openIdea(page, IDEA_WITH_ASSETS);
    await page.locator(`#nlmRunBtn-${IDEA_WITH_ASSETS}`).click();

    const msg = page.locator(`#nlmMsg-${IDEA_WITH_ASSETS}`);
    // Library-missing message is rendered immediately by nlmRun's doctor
    // check (no job started). The banner mentions the setup command.
    await expect(msg).toContainText('notebooklm', { ignoreCase: true, timeout: 8_000 });
  });

  test('Re-authenticate Now → /relogin called → awaiting state shown', async ({ page }) => {
    // Trip the auth-expired banner first, then click re-auth and verify
    // the panel transitions into "awaiting sign-in".
    let reloginHit = false;
    await page.route(`**/api/notebooklm/doctor`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ library_installed: true, session_file_ready: true }) });
    });
    await page.route(`**/api/ideas/${IDEA_WITH_ASSETS}/notebooklm/run`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, job_id: 'mock_relogin_' + Date.now() }) });
    });
    await page.route(/\/api\/notebooklm-jobs\//, route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true, status: 'error', error_kind: 'auth_expired',
          message: 'Session expired.', stage: 'done',
        }),
      });
    });
    await page.route(`**/api/notebooklm/relogin`, route => {
      reloginHit = true;
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, pid: 12345, message: 'Chromium will open.' }) });
    });
    // Keep status polling silent (running, no transition) so the test
    // can assert the awaiting state without races.
    await page.route(`**/api/notebooklm/relogin/status`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ state: 'running', elapsed_s: 1.2, pid: 12345 }) });
    });
    await page.route(`**/api/notebooklm/session-check`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ valid: false, reason: 'expired', returncode: 2 }) });
    });

    await page.goto('/');
    await waitForIdeaList(page);
    await openIdea(page, IDEA_WITH_ASSETS);
    await page.locator(`#nlmRunBtn-${IDEA_WITH_ASSETS}`).click();

    const reloginBtn = page.locator(`#nlmReloginBtn-${IDEA_WITH_ASSETS}`);
    await expect(reloginBtn).toBeVisible({ timeout: 15_000 });
    await reloginBtn.click();

    expect(reloginHit, 'POST /api/notebooklm/relogin was called').toBe(true);

    // Awaiting state shows the "Sign in to NotebookLM" instruction.
    const msg = page.locator(`#nlmMsg-${IDEA_WITH_ASSETS}`);
    await expect(msg).toContainText('Sign in to NotebookLM', { timeout: 8_000 });
    // Elapsed counter should appear within ~2 seconds.
    await expect(page.locator(`#nlmReloginElapsed-${IDEA_WITH_ASSETS}`)).toBeVisible();
  });

  test('relogin status=done + session valid → restored banner + Run re-enabled', async ({ page }) => {
    let reloginStatusCalls = 0;
    await page.route(`**/api/notebooklm/doctor`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ library_installed: true, session_file_ready: true }) });
    });
    await page.route(`**/api/ideas/${IDEA_WITH_ASSETS}/notebooklm/run`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, job_id: 'mock_restore_' + Date.now() }) });
    });
    await page.route(/\/api\/notebooklm-jobs\//, route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true, status: 'error', error_kind: 'auth_expired',
          message: 'Session expired.', stage: 'done',
        }),
      });
    });
    await page.route(`**/api/notebooklm/relogin`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, pid: 12345 }) });
    });
    // First status poll = still running, second = done success.
    await page.route(`**/api/notebooklm/relogin/status`, route => {
      reloginStatusCalls += 1;
      if (reloginStatusCalls === 1) {
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ state: 'running', elapsed_s: 2.5, pid: 12345 }) });
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ state: 'done', returncode: 0, elapsed_s: 18.3, output_tail: '[saved] ok' }) });
    });
    // session-check returns valid once relogin is done.
    let sessionCheckCalls = 0;
    await page.route(`**/api/notebooklm/session-check`, route => {
      sessionCheckCalls += 1;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ valid: sessionCheckCalls >= 1, reason: 'ok', returncode: 0 }),
      });
    });

    await page.goto('/');
    await waitForIdeaList(page);
    await openIdea(page, IDEA_WITH_ASSETS);
    await page.locator(`#nlmRunBtn-${IDEA_WITH_ASSETS}`).click();
    await page.locator(`#nlmReloginBtn-${IDEA_WITH_ASSETS}`).click();

    // Restored state: panel says "Session restored", Run button re-enabled.
    const msg = page.locator(`#nlmMsg-${IDEA_WITH_ASSETS}`);
    await expect(msg).toContainText('Session restored', { timeout: 30_000 });
    const runBtn = page.locator(`#nlmRunBtn-${IDEA_WITH_ASSETS}`);
    await expect(runBtn).toBeEnabled();
    await expect(runBtn).toContainText('Run Campaign');
  });

  test('relogin helper exits with non-zero code → error banner shows output tail', async ({ page }) => {
    await page.route(`**/api/notebooklm/doctor`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ library_installed: true, session_file_ready: true }) });
    });
    await page.route(`**/api/ideas/${IDEA_WITH_ASSETS}/notebooklm/run`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, job_id: 'mock_helpfail_' + Date.now() }) });
    });
    await page.route(/\/api\/notebooklm-jobs\//, route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true, status: 'error', error_kind: 'auth_expired',
          message: 'Session expired.', stage: 'done',
        }),
      });
    });
    await page.route(`**/api/notebooklm/relogin`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, pid: 12345 }) });
    });
    // Helper exits immediately with code 4 (Playwright I/O error).
    await page.route(`**/api/notebooklm/relogin/status`, route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          state: 'error', returncode: 4, elapsed_s: 1.1,
          output_tail: '[error] Browser profile dir locked by another process',
        }),
      });
    });
    await page.route(`**/api/notebooklm/session-check`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ valid: false, reason: 'expired', returncode: 2 }) });
    });

    await page.goto('/');
    await waitForIdeaList(page);
    await openIdea(page, IDEA_WITH_ASSETS);
    await page.locator(`#nlmRunBtn-${IDEA_WITH_ASSETS}`).click();
    await page.locator(`#nlmReloginBtn-${IDEA_WITH_ASSETS}`).click();

    const msg = page.locator(`#nlmMsg-${IDEA_WITH_ASSETS}`);
    // Error banner should surface the output_tail snippet so we can
    // diagnose Playwright-side failures without opening the helper window.
    await expect(msg).toContainText('exited with code 4', { timeout: 15_000 });
    await expect(msg).toContainText('Browser profile dir locked', { timeout: 5_000 });
    // Try again button is the recovery affordance.
    await expect(msg.locator('button:has-text("Try again")')).toBeVisible();
  });
});
