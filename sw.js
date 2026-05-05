// WorkHive Report Sender — Service Worker
// Enables PWA installability and offline shell on Chrome/Android.

const CACHE_NAME  = 'report-sender-v10';
const SHELL_FILES = [
  '/report-sender.html',
  '/report-sender-manifest.json',
  '/nav-hub.js',
  '/brand_assets/workhive-logo-transparent.png',
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
