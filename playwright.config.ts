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
  // RAG flywheel walk: per-page test can take up to 30 min (83 tiles × 5s
  // inter-tile delay + LLM latency). Disable retries for the flywheel spec
  // to prevent duplicate observations. CI retries restored via env var.
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  outputDir: './test-results',
  reporter: [
    ['list'],
    ['json', { outputFile: 'playwright-report.json' }],
  ],
  // 45 min per test: handles 83 tiles × (5s throttle + up to 90s LLM) worst-case
  timeout: 2_700_000,
  expect: { timeout: 8_000 },
  use: {
    // The Flask seeder serves WorkHive pages at /workhive/<file>.html, NOT
    // at root. Tests use `page.goto('/workhive/<file>.html')` accordingly.
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
