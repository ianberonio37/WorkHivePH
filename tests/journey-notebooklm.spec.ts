/**
 * journey-notebooklm.spec.ts — NotebookLM Long-Form Lane UI journey.
 *
 * Layered like the existing WorkHive L2 test framework:
 *   Smoke              (~5s)  — panel renders, endpoints respond
 *   Concurrent edit    (~5s)  — double-click Run doesn't fire two jobs
 *   CRUD / DB-verified (~10s) — Prepare writes 6 source files to disk
 *   UI Locks           (~5s)  — Run button disables in-flight, re-enables after
 *   Visual regression  (~5s)  — banner DOM snapshots for auth/quota/lib-missing
 *   Plus the original journey scenarios (re-auth, error categories, etc.)
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

    // The dashboard re-renders the panel twice (initial + after script
    // content loads). The first render populates the grid, the second
    // wipes + repopulates. We force a third loadNlmStatus call after
    // both renders settle so the test asserts against a stable state
    // regardless of which render was last.
    await page.waitForTimeout(1500);
    await page.evaluate((id) => (window as any).loadNlmStatus?.(id), IDEA_WITH_ASSETS);
    await expect.poll(
      () => page.locator(`#nlmArtifacts-${IDEA_WITH_ASSETS} .nlm-artifact`).count(),
      { timeout: 15_000, intervals: [200, 400, 800] },
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

  test('error_kind=quota_exceeded → amber rate-limit banner WITH re-auth offer', async ({ page }) => {
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
    // Banner mentions rate-limit (Google's USER_DISPLAYABLE_ERROR is a
    // per-session-token throttle, not an account quota). The re-auth
    // button is the recommended remedy since fresh tokens get fresh
    // budget — so we EXPECT to see the button here.
    await expect(msg).toContainText(/rate-limit|quota/i, { timeout: 15_000 });
    await expect(page.locator(`#nlmReloginBtn-${IDEA_WITH_ASSETS}`)).toBeVisible();
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

  test('status pill turns green when health endpoint reports ready', async ({ page }) => {
    await page.route('**/api/notebooklm/health', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'green', summary: 'ready',
          library_installed: true, library_version: '0.4.1',
          session_file_ready: true, session_age_min: 12.4,
          artifact_count: 6, last_campaign_at: 1779576523,
          checked_at: 1779600000,
        }),
      });
    });
    await page.goto('/');
    await waitForIdeaList(page);
    await openIdea(page, IDEA_WITH_ASSETS);
    const pill = page.locator(`#nlmStatus-${IDEA_WITH_ASSETS}`);
    await expect(pill).toHaveClass(/green/, { timeout: 10_000 });
    await expect(pill).toContainText('ready');
    // Tooltip should expose library + session age for hover diagnostics.
    const title = await pill.getAttribute('title');
    expect(title).toContain('0.4.1');
    expect(title).toContain('12.4');
  });

  test('status pill turns red when library is missing', async ({ page }) => {
    await page.route('**/api/notebooklm/health', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'red', summary: 'library missing',
          library_installed: false, library_version: null,
          session_file_ready: false, session_age_min: null,
          artifact_count: 0, last_campaign_at: null,
        }),
      });
    });
    await page.goto('/');
    await waitForIdeaList(page);
    await openIdea(page, IDEA_WITH_ASSETS);
    const pill = page.locator(`#nlmStatus-${IDEA_WITH_ASSETS}`);
    await expect(pill).toHaveClass(/red/, { timeout: 10_000 });
    await expect(pill).toContainText('library missing');
  });

  test('status pill turns amber when session is aging', async ({ page }) => {
    await page.route('**/api/notebooklm/health', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'amber', summary: 'session 7h old — may need re-auth',
          library_installed: true, library_version: '0.4.1',
          session_file_ready: true, session_age_min: 432,
          artifact_count: 5, last_campaign_at: 1779576523,
        }),
      });
    });
    await page.goto('/');
    await waitForIdeaList(page);
    await openIdea(page, IDEA_WITH_ASSETS);
    const pill = page.locator(`#nlmStatus-${IDEA_WITH_ASSETS}`);
    await expect(pill).toHaveClass(/amber/, { timeout: 10_000 });
    await expect(pill).toContainText('re-auth');
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

  // ────────────────────────────────────────────────────────────────────────
  // L2 CATEGORY: CONCURRENT-EDIT
  // ────────────────────────────────────────────────────────────────────────
  test('concurrent: double-click Run Campaign only fires one job', async ({ page }) => {
    let runCalls = 0;
    await page.route(`**/api/notebooklm/doctor`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ library_installed: true, session_file_ready: true }) });
    });
    // Delay the run response so the second click would race in if not gated.
    await page.route(`**/api/ideas/${IDEA_WITH_ASSETS}/notebooklm/run`, async route => {
      runCalls += 1;
      await new Promise(r => setTimeout(r, 600));
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, job_id: 'mock_concurrent_' + runCalls }) });
    });
    await page.route(/\/api\/notebooklm-jobs\//, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, status: 'running', stage: 'prepare', message: '...' }) });
    });

    await page.goto('/');
    await waitForIdeaList(page);
    await openIdea(page, IDEA_WITH_ASSETS);
    const runBtn = page.locator(`#nlmRunBtn-${IDEA_WITH_ASSETS}`);

    // Fire two clicks back-to-back. UI must disable the button on first click.
    await runBtn.click();
    await runBtn.click({ force: true }).catch(() => {});

    // Wait long enough for both mock responses to settle.
    await page.waitForTimeout(1500);
    expect(runCalls, 'Run endpoint should only have been called once').toBe(1);
  });

  // ────────────────────────────────────────────────────────────────────────
  // L2 CATEGORY: CRUD / DISK-VERIFIED — Prepare writes source files to disk
  // ────────────────────────────────────────────────────────────────────────
  test('crud: Prepare Sources writes 6 source files reported by the endpoint', async ({ page, request }) => {
    // Hit the real endpoint (no mock) — this is a DB-verified style test:
    // we assert the endpoint reports the correct number of source files
    // and exposes their sizes (proxy for "files exist on disk").
    const res = await request.post(`${DASHBOARD_URL}/api/ideas/${IDEA_WITH_ASSETS}/notebooklm/prepare`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.success, body.error || '').toBe(true);
    expect(body.count, 'prepare should report 6 source files (brand_voice, product_overview, platform_context, idea_brief, video_script, narration_and_music)').toBe(6);
    expect(Array.isArray(body.sources)).toBe(true);
    // Each source has a name + size_kb >= 0.
    for (const s of body.sources) {
      expect(s.name).toMatch(/\.md$/);
      expect(typeof s.size_kb).toBe('number');
    }
    // The 6 canonical filenames must all be present (order-independent).
    const names = body.sources.map((s: any) => s.name).sort();
    expect(names).toEqual([
      '01_brand_voice.md',
      '02_product_overview.md',
      '03_platform_context.md',
      '04_idea_brief.md',
      '05_video_script.md',
      '06_narration_and_music.md',
    ]);
  });

  // ────────────────────────────────────────────────────────────────────────
  // L2 CATEGORY: UI LOCKS — Run button must disable during a job
  // ────────────────────────────────────────────────────────────────────────
  test('ui-lock: Run button disables while a job is in-flight + re-enables on terminal state', async ({ page }) => {
    let jobStatus = 'running';
    await page.route(`**/api/notebooklm/doctor`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ library_installed: true, session_file_ready: true }) });
    });
    await page.route(`**/api/ideas/${IDEA_WITH_ASSETS}/notebooklm/run`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, job_id: 'mock_uilock_' + Date.now() }) });
    });
    await page.route(/\/api\/notebooklm-jobs\//, route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          status: jobStatus,
          stage: jobStatus === 'running' ? 'prepare' : 'done',
          message: jobStatus === 'running' ? 'Building source bundle…' : '1/1 artifacts produced',
        }),
      });
    });

    await page.goto('/');
    await waitForIdeaList(page);
    await openIdea(page, IDEA_WITH_ASSETS);
    const runBtn = page.locator(`#nlmRunBtn-${IDEA_WITH_ASSETS}`);

    // Wait for the panel to fully settle — script-content fetch + the
    // second renderProductionKit run both touch the button. Without this
    // stabilization step, an in-flight panel re-render can clobber the
    // disabled state set by nlmRun.
    await expect(runBtn).toBeEnabled({ timeout: 8_000 });
    await page.waitForTimeout(800);

    // Click → button must immediately enter a disabled state.
    await runBtn.click();
    await expect(runBtn).toBeDisabled({ timeout: 5_000 });

    // Flip the mocked job to complete. The polling loop should detect it
    // and re-enable the button.
    jobStatus = 'complete';
    await expect(runBtn).toBeEnabled({ timeout: 10_000 });
    await expect(runBtn).toContainText(/Run Campaign Again|Run Campaign/);
  });

  // ────────────────────────────────────────────────────────────────────────
  // L2 CATEGORY: VISUAL REGRESSION — banner DOM snapshots
  // Uses textContent + class snapshots rather than pixel diffs so the
  // assertion survives font-rendering noise across machines but still
  // catches any structural drift in the error banners.
  // ────────────────────────────────────────────────────────────────────────
  test('visual-regression: auth_expired banner DOM matches the canonical structure', async ({ page }) => {
    await page.route(`**/api/notebooklm/doctor`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ library_installed: true, session_file_ready: true }) });
    });
    await page.route(`**/api/ideas/${IDEA_WITH_ASSETS}/notebooklm/run`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, job_id: 'mock_vr_auth_' + Date.now() }) });
    });
    await page.route(/\/api\/notebooklm-jobs\//, route => {
      route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({ success: true, status: 'error', error_kind: 'auth_expired', message: 'Session expired.', stage: 'done' }),
      });
    });

    await page.goto('/');
    await waitForIdeaList(page);
    await openIdea(page, IDEA_WITH_ASSETS);
    await page.locator(`#nlmRunBtn-${IDEA_WITH_ASSETS}`).click();

    const reloginBtn = page.locator(`#nlmReloginBtn-${IDEA_WITH_ASSETS}`);
    await expect(reloginBtn).toBeVisible({ timeout: 15_000 });

    // Snapshot the canonical structure for the auth banner. Any change
    // to the banner HTML will fail this and require a deliberate update.
    const msg = page.locator(`#nlmMsg-${IDEA_WITH_ASSETS}`);
    const warn = msg.locator('.nlm-doctor-warn');
    await expect(warn).toBeVisible();
    await expect(warn).toContainText('NotebookLM session expired');
    await expect(warn).toContainText('Google sessions only last');
    await expect(warn.locator(`#nlmReloginBtn-${IDEA_WITH_ASSETS}`)).toBeVisible();
    await expect(warn.locator(`#nlmReloginBtn-${IDEA_WITH_ASSETS}`)).toContainText('Re-authenticate Now');
  });

  test('visual-regression: quota_exceeded banner DOM matches the canonical structure', async ({ page }) => {
    await page.route(`**/api/notebooklm/doctor`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ library_installed: true, session_file_ready: true }) });
    });
    await page.route(`**/api/ideas/${IDEA_WITH_ASSETS}/notebooklm/run`, route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, job_id: 'mock_vr_quota_' + Date.now() }) });
    });
    await page.route(/\/api\/notebooklm-jobs\//, route => {
      route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({ success: true, status: 'error', error_kind: 'quota_exceeded', message: 'NotebookLM daily quota hit. Resets at UTC midnight.', stage: 'done' }),
      });
    });

    await page.goto('/');
    await waitForIdeaList(page);
    await openIdea(page, IDEA_WITH_ASSETS);
    await page.locator(`#nlmRunBtn-${IDEA_WITH_ASSETS}`).click();

    const msg = page.locator(`#nlmMsg-${IDEA_WITH_ASSETS}`);
    const warn = msg.locator('.nlm-doctor-warn');
    await expect(warn).toBeVisible({ timeout: 15_000 });
    await expect(warn).toContainText(/rate-limit|quota/i);
    // Banner offers re-auth as the fast remedy (fresh tokens reset the
    // per-session throttle). It also notes that notebooklm.google.com is
    // unaffected so the user knows the account itself is healthy.
    await expect(warn.locator(`#nlmReloginBtn-${IDEA_WITH_ASSETS}`)).toBeVisible();
    await expect(warn).toContainText('notebooklm.google.com');
  });

  test('visual-regression: status pill renders all three traffic-light states correctly', async ({ page }) => {
    // Cycle through green → amber → red on the same panel by changing the
    // mocked /health response between page evaluates. Snapshot each.
    let mocked = 'green';
    await page.route('**/api/notebooklm/health', route => {
      const bodies = {
        green: { status: 'green', summary: 'ready', library_installed: true, library_version: '0.4.1', session_file_ready: true, session_age_min: 5, artifact_count: 3, last_campaign_at: null },
        amber: { status: 'amber', summary: 'session 7h old — may need re-auth', library_installed: true, library_version: '0.4.1', session_file_ready: true, session_age_min: 420, artifact_count: 3, last_campaign_at: null },
        red:   { status: 'red',   summary: 'no session — log in', library_installed: true, library_version: '0.4.1', session_file_ready: false, session_age_min: null, artifact_count: 0, last_campaign_at: null },
      };
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify((bodies as any)[mocked]) });
    });

    await page.goto('/');
    await waitForIdeaList(page);
    await openIdea(page, IDEA_WITH_ASSETS);
    const pill = page.locator(`#nlmStatus-${IDEA_WITH_ASSETS}`);

    // Green initial
    await expect(pill).toHaveClass(/green/, { timeout: 8_000 });

    // Force amber via re-evaluation
    mocked = 'amber';
    await page.evaluate((id) => (window as any).refreshNlmStatus?.(id), IDEA_WITH_ASSETS);
    await expect(pill).toHaveClass(/amber/, { timeout: 5_000 });
    await expect(pill).toContainText('re-auth');

    // Force red
    mocked = 'red';
    await page.evaluate((id) => (window as any).refreshNlmStatus?.(id), IDEA_WITH_ASSETS);
    await expect(pill).toHaveClass(/red/, { timeout: 5_000 });
    await expect(pill).toContainText('no session');
  });
});
