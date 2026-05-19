/**
 * Tier 7 — Offline & resilience (4 scenarios, P1)
 *
 * IndexedDB queue, service worker cache, CACHE_NAME bump, offline banner.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';
import { readFileSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(__dirname, '..');

test.describe('Tier 7 — Offline & resilience', () => {

  test('H1_offline_queue_helper_present: offline-queue.js exposes enqueue/drain over IndexedDB', async () => {
    // WHY: IndexedDB-backed queue is the canonical offline pattern (mobile-maestro skill)
    const helper = readFileSync(resolve(ROOT, 'offline-queue.js'), 'utf-8');
    expect(helper, 'must open IndexedDB').toMatch(/indexedDB\.open/);
    expect(helper, 'must declare enqueue API').toMatch(/enqueue\s*[:=]?\s*(function|\()/);
    // Per-identity enqueue (one worker's queue cannot leak another's)
    expect(helper, 'must scope queue per identity').toMatch(/per-identity|worker_name/i);
  });

  test('H2_service_worker_serves_offline_shell: sw.js fetch handler covers offline navigation', async () => {
    // WHY: PWA must serve cached HTML when offline; sw.js fetch handler must include network-first/cache fallback
    const sw = readFileSync(resolve(ROOT, 'sw.js'), 'utf-8');
    // Fetch event listener present
    expect(sw, 'sw.js must register a fetch handler').toMatch(/addEventListener\s*\(\s*['"]fetch['"]/);
    // Falls back to cache on network failure
    expect(sw, 'sw.js must fall back to caches.match on network error').toMatch(/caches\.match/);
    // SHELL_FILES (or equivalent precache list) declared
    expect(sw, 'sw.js must declare a precache list').toMatch(/SHELL_FILES|PRECACHE|cache\.addAll/);
  });

  test('H3_cache_name_versioned: sw.js has versioned CACHE_NAME', async () => {
    // WHY: bumping CACHE_NAME invalidates stale cache after deploy (mobile-maestro)
    // STATIC ASSERTION
    const sw = readFileSync(resolve(ROOT, 'sw.js'), 'utf-8');
    const m = sw.match(/CACHE_NAME\s*=\s*['"]([^'"]+)['"]/);
    expect(m, 'sw.js must declare CACHE_NAME').not.toBeNull();
    expect(m![1], 'CACHE_NAME must include a -v<N> suffix').toMatch(/-v\d+/);
  });

  test('H4_offline_banner_renders_pending_count: logbook ships #offline-banner with count badge', async () => {
    // WHY: visibility into the offline queue (mobile-maestro skill)
    const html = readFileSync(resolve(ROOT, 'logbook.html'), 'utf-8');
    expect(html, 'logbook must render #offline-banner').toMatch(/id\s*=\s*['"]offline-banner['"]/);
    expect(html, 'must render #offline-queue-count badge').toMatch(/id\s*=\s*['"]offline-queue-count['"]/);
    // offline-banner.js helper loaded
    expect(html, 'must load offline-banner.js helper').toMatch(/offline-banner\.js/);
  });
});
