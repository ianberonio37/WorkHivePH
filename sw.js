/* ═══════════════════════════════════════════
   WorkHive Service Worker
   Cache-first for static assets.
   Network-first for everything else.
═══════════════════════════════════════════ */

const CACHE = 'workhive-v1';

const PRECACHE = [
  '/',
  '/index.html',
  '/manifest.json',
  '/brand_assets/workhive-logo-transparent.png',
  '/utils.js',
  '/nav-hub.js',
];

/* ── Install: pre-cache shell ── */
self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(CACHE).then(function(cache) {
      return cache.addAll(PRECACHE);
    })
  );
  self.skipWaiting();
});

/* ── Activate: clean old caches ── */
self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE; })
            .map(function(k) { return caches.delete(k); })
      );
    })
  );
  self.clients.claim();
});

/* ── Fetch: cache-first for same-origin, network-first for external ── */
self.addEventListener('fetch', function(e) {
  var url = new URL(e.request.url);

  /* Skip non-GET, supabase calls, CDN, and browser extensions */
  if (e.request.method !== 'GET') return;
  if (url.hostname.includes('supabase')) return;
  if (url.hostname.includes('googleapis')) return;
  if (url.hostname.includes('tailwindcss')) return;
  if (url.hostname.includes('jsdelivr')) return;
  if (url.protocol === 'chrome-extension:') return;

  /* Same-origin: cache-first */
  if (url.origin === location.origin) {
    e.respondWith(
      caches.match(e.request).then(function(cached) {
        if (cached) return cached;
        return fetch(e.request).then(function(response) {
          if (!response || response.status !== 200) return response;
          var clone = response.clone();
          caches.open(CACHE).then(function(cache) { cache.put(e.request, clone); });
          return response;
        });
      })
    );
    return;
  }

  /* External: network-only (CDN, fonts, etc.) */
  e.respondWith(fetch(e.request));
});
