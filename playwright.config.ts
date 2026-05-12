import { defineConfig, devices } from '@playwright/test';

/**
 * WorkHive Playwright config.
 *
 * Tests run against the Flask seeder at http://127.0.0.1:5000 which serves
 * every live HTML page and rewrites cloud Supabase URLs -> local Docker
 * (memory: "Local Supabase URL rewrite"). Local Supabase MUST be running
 * (docker ps -> supabase_db_workhive healthy). The seeder gives us a real
 * end-to-end environment with the same edge functions, RLS, and migrations
 * production sees.
 *
 * The validator wrapper validate_playwright_smoke.py runs the suite
 * (npx playwright test --reporter=json) and parses results so the
 * platform guardian catches UI regressions the same way it catches
 * schema/code regressions.
 *
 * Skills consulted: qa (test isolation, fixture lifecycles), frontend
 * (real DOM + form submit paths), platform-guardian (parseable output,
 * forward-only ratchet via baseline lockfile if needed).
 */
export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.ts',
  fullyParallel: false,        // tests share a hive + worker; keep serial
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [
    ['list'],
    ['json', { outputFile: 'playwright-report.json' }],
  ],
  timeout: 30_000,
  expect: { timeout: 5_000 },
  use: {
    baseURL: process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000',
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 8_000,
    navigationTimeout: 15_000,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
