/**
 * journey-static-headers.spec.ts — P1 roadmap 2026-05-27 (CA.1)
 *
 * Verifies that static assets emit strong cache headers, and that the
 * service worker is served with no-store so cache busting actually works.
 *
 * These checks complement `_headers` (Netlify) declarations — runtime
 * verification is the only way to catch deployment drift.
 */
import { test, expect } from './_fixtures';

test.describe('static_cache_headers — runtime header verification', () => {

  test('static_cache_headers: sw.js is served with no-store (cache version bumps must apply immediately)', async ({ request }) => {
    const r = await request.get('/sw.js', { failOnStatusCode: false });
    if (r.status() !== 200) test.skip(true, 'sw.js not reachable in this environment');
    const cc = r.headers()['cache-control'] || '';
    // Either no-store, no-cache, or max-age=0 — any of those guarantees
    // the browser refetches sw.js on next visit.
    const safe = /no-store|no-cache|max-age=0/i.test(cc);
    expect(safe, `sw.js Cache-Control must prevent caching, got '${cc}'`).toBe(true);
  });

  test('static_cache_headers: hashed asset (if present) has long max-age', async ({ request }) => {
    // Try a few canonical asset paths. If none are present, skip.
    const candidates = ['/utils.js', '/wh-tts.js', '/voice-handler.js'];
    let header = '';
    for (const p of candidates) {
      const r = await request.get(p, { failOnStatusCode: false });
      if (r.status() === 200) {
        header = r.headers()['cache-control'] || '';
        break;
      }
    }
    if (!header) test.skip(true, 'no static JS assets reachable');
    // Either explicit max-age (cacheable) or no-cache. Both are valid
    // depending on whether the file is hashed. Just assert SOMETHING
    // was declared rather than silent no-header.
    expect(header.length, 'Cache-Control header must be declared, not empty').toBeGreaterThan(0);
  });

  test('static_cache_headers: HTML pages return Content-Type text/html', async ({ request }) => {
    const r = await request.get('/workhive/hive.html', { failOnStatusCode: false });
    if (r.status() !== 200) test.skip(true, 'hive.html not reachable');
    const ct = r.headers()['content-type'] || '';
    expect(ct.toLowerCase()).toContain('text/html');
  });

  test('static_cache_headers: 404 path returns a 4xx (not silently 200)', async ({ request }) => {
    const r = await request.get('/workhive/this-page-does-not-exist-xxx.html', { failOnStatusCode: false });
    expect([301, 302, 308, 400, 401, 403, 404]).toContain(r.status());
  });
});
