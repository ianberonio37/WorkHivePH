// WorkHive Service Worker — Phase 2 (multi-page shell, 2026-05-11)
// Enables PWA installability + offline shell across the worker-critical
// surfaces (logbook, inventory, pm-scheduler, hive, asset-hub, shift-brain).
// Closes PRODUCTION_FIXES #54.

const CACHE_NAME  = 'workhive-shell-v102';  // bump 2026-05-20: drift wiring — index.html ops-home Today's One Thing now reads v_amc_truth + v_sensor_truth + v_alert_truth; hive.html pattern-alerts panel + asset-hub anomaly banner now read truth views. Re-prime cache so PWA users see the canonical-wired renderers.
// const CACHE_NAME  = 'workhive-shell-v101';  // 3 truth-view wrappers + OEE RPC
// const CACHE_NAME  = 'workhive-shell-v100';  // bump 2026-05-19: Calm Dashboard hideZeroStat wiring pass — stat-update sites now dim 0/— values across hive (welcome + members + pulse), alert-hub (AMC briefing setStat), asset-hub (asset-360 strip), predictive (4 risk-tier counts), achievements (3 XP stats), founder-console (setStat), platform-health (health-num + streak)
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
  '/wh-help.js',
  // Persona Contract Phase 3+4 shared helpers
  '/wh-persona.js',
  '/wh-tts.js',
  // Voice Companion handler (Phase 1-11 orchestrator)
  '/voice-handler.js',
  // Companion Streamline Step B: persona portraits (compressed JPEGs;
  // 12KB each; full-res source PNGs are at /brand_assets/{James,Rosa}.png)
  '/brand_assets/james-256.jpg',
  '/brand_assets/rosa-256.jpg',
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
