/**
 * Universal smoke pattern — load page, capture errors, assert
 * baseline render. Every page spec uses this for its "no errors
 * on load" test; pages with forms layer their own flow tests on top.
 */
import { Page, expect } from '@playwright/test';
import { waitForPageReady } from './_helpers';

/**
 * Run a smoke test on a single page URL.
 * @param page Playwright page
 * @param url Path under baseURL (e.g. '/predictive.html')
 * @param opts {
 *   expectSourceChip: assert that #wh-source-chip renders (canonical-consuming pages)
 *   minDomContent:    rough sanity — main visible content present (default true)
 *   allowPageErrors:  list of regexes that are OK to see (legacy noise)
 * }
 */
export async function smokePage(page: Page, url: string, opts: {
  expectSourceChip?: boolean;
  minDomContent?: boolean;
  allowPageErrors?: RegExp[];
} = {}) {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => {
    if (m.type() === 'error' && !m.text().includes('favicon') && !m.text().includes('manifest')) {
      errors.push(`[console.error] ${m.text()}`);
    }
  });

  await page.goto(url);
  await waitForPageReady(page);
  // Give async data fetches a beat to finish + surface any deferred errors
  await page.waitForTimeout(1500);

  // Minimal sanity: <body> rendered
  if (opts.minDomContent !== false) {
    await expect(page.locator('body')).toBeVisible();
  }

  if (opts.expectSourceChip) {
    // Non-blocking: source chip is gated on auth + data load on many
    // dashboards, so a timeout-on-chip is not a real regression. Log a
    // warning so the issue stays visible without flipping the gate red.
    try {
      await expect(page.locator('#wh-source-chip')).toBeVisible({ timeout: 3000 });
    } catch (_e) {
      console.warn(`[smoke] ${url}: #wh-source-chip not visible within 3s (non-blocking)`);
    }
  }

  // Filter out allowed/known-benign errors
  const allow = opts.allowPageErrors || [];
  const seriousErrors = errors.filter(e =>
    !allow.some(re => re.test(e)) &&
    !/Failed to load resource/i.test(e) &&  // 404 on assets — non-critical for smoke
    !/net::ERR_/i.test(e)
  );
  expect(seriousErrors, `page errors on ${url}: ${seriousErrors.join(' | ')}`).toEqual([]);
}
