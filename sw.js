// WorkHive Service Worker — Phase 2 (multi-page shell, 2026-05-11)
// Enables PWA installability + offline shell across the worker-critical
// surfaces (logbook, inventory, pm-scheduler, hive, asset-hub, shift-brain).
// Closes PRODUCTION_FIXES #54.

const CACHE_NAME  = 'workhive-shell-v55';
const SHELL_FILES = [
  // Original report-sender shell
  '/report-sender.html',
  '/report-sender-manifest.json',
  // Shared chrome
  '/nav-hub.js',
  '/button-lock.js',
  '/offline-banner.js',
  '/brand_assets/workhive-logo-transparent.png',
  // Phase 2 resilience helpers (shared across worker-critical surfaces)
  '/offline-queue.js',
  '/connectivity-widget.js',
  '/form-autosave.js',
  '/session-timeout.js',
  '/device-fingerprint.js',
  '/onboarding.js',
  // Worker-critical pages (offline-capable on cached page-shell)
  '/logbook.html',
  '/inventory.html',
  '/pm-scheduler.html',
  '/parts-tracker.html',
  '/shift-brain.html',
  '/asset-hub.html',
  '/hive.html',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL_FILES))
  );
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Network-first for API and font requests; cache-first for shell
self.addEventListener('fetch', e => {
  const url = e.request.url;
  if (url.includes('supabase.co') || url.includes('fonts.goog') || url.includes('fonts.gstatic')) {
    e.respondWith(fetch(e.request).catch(() => new Response('', { status: 503 })));
    return;
  }
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
