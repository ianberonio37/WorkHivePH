// WorkHive Service Worker — Phase 2 (multi-page shell, 2026-05-11)
// Enables PWA installability + offline shell across the worker-critical
// surfaces (logbook, inventory, pm-scheduler, hive, asset-hub, shift-brain).
// Closes PRODUCTION_FIXES #54.

const CACHE_NAME  = 'workhive-shell-v119';  // bump 2026-05-21: flywheel turns 16-25 — index.html auth-form wrapper (password-manager autofill) + 3 explicit button types; achievements.html back-button <a href=javascript:> -> <button>; parts-tracker.html meta-refresh-allow marker; integrations.html Bearer-token password-input-allow; project-manager.html timer-cleanup-allow. Re-prime cache so PWA users get the auth-form + a11y fixes.
// const CACHE_NAME  = 'workhive-shell-v118';  // bump 2026-05-21: voice-handler.js Phase 4.67-4.76 seventh 10-turn flywheel (turns #65-#74, ORCHESTRATION + INTEGRATION): PDF export detector points to Report Sender, per-device pronunciation library, voice-execute safety lock (default OFF), persona portrait animation (idle/listening/thinking/speaking/urgent), cross-hive benchmark RPC fn_cross_hive_benchmark wiring (5-min cache), daily-digest mode (5-line briefing), push notification readiness (capability + permission request), multi-worker concurrency lock (per-hive advisory), accent / voice signature adaptation (tagalog density estimate + persisted pref), streaming SSE indicator. Re-prime cache for all PWA users.
// const CACHE_NAME  = 'workhive-shell-v117';  // bump 2026-05-21: voice-handler.js Phase 4.54-4.66 sixth 10-turn flywheel (turns #55-#64, WORKFLOW + PERSONALIZATION): proactive companion turn (open() accepts alert payload), maturity-stair gating (Stair <2 → no predictive promises), per-slot expiry windows (asset_tag 60m / machine_status 30m / time_window 2h), action replay ('same fix on P-205'), language opt-in (tagalog / english / cebuano persisted), brevity preference (brief / full mode), timer follow-up ('remind me in 20 min'), URL-context pre-fill (?asset=P-203 → context_slots), mic quality meter (AnalyserNode warns on low volume), multi-step action queue ('log entry then start PM then notify'). Re-prime cache for all PWA users.
// const CACHE_NAME  = 'workhive-shell-v116';  // bump 2026-05-21: voice-handler.js Phase 4.44-4.53 fifth 10-turn flywheel (turns #45-#54, RESILIENCE + MEMORY + TRUST OPS): offline degradation tracker, 10-min reply cache (LRU 16), feedback escalation (3+ thumbs-down in 7d → ai_quality_escalation upsert), custom plant terminology fuzzy-match against v_asset_truth, conversation branching stack ('back to the X thing'), multi-modal photo intent (offers Visual Defect Capture), avatar emotion state (urgent/celebratory/concerned/helpful → data-avatar-state attribute), cross-hive anonymised benchmark anchor, summary-on-demand mode, identity drift tracker (warns on worker_name change mid-session). Re-prime cache for all PWA users.
// const CACHE_NAME  = 'workhive-shell-v115';  // bump 2026-05-21: voice-handler.js Phase 4.34-4.43 fourth 10-turn flywheel (turns #35-#44, COLLABORATION + WELLBEING): action-confirmation detector (write-verb utterances require yes/no before voice-action-router executes), wellbeing nudge on graveyard shift, encouragement anchor for completed PMs / closed logbooks, skill-gap nudge from v_worker_skill_truth, shift-handover mode (structured 4-line block), batch-action parser (log X, Y, Z), explainability anchor (source view + row count + timestamp), co-worker mention detector for logbook tagging, fatigue signal detector (pagod / ayoko / frustrated → softer tone), transcript export detector routes to Report Sender. Re-prime cache for all PWA users.
// const CACHE_NAME  = 'workhive-shell-v114';  // bump 2026-05-21: flywheel turns 8 + 12 — logbook.html + inventory.html + dayplanner.html JSON.parse safety wrappers (corrupt localStorage no longer crashes the page); platform-health.html setInterval cleanup on beforeunload + 2 fetch() chains given .catch fallbacks; project-manager.html documented timer-cleanup-allow marker. Re-prime cache so PWA users get the new try/catch wrappers + error handlers.
// const CACHE_NAME  = 'workhive-shell-v113';  // bump 2026-05-21: voice-handler.js Phase 4.24-4.33 third 10-turn flywheel (turns #25-#34, CONTEXT AWARENESS + INTELLIGENCE): shift-context anchor (06:00 / 14:00 / 22:00 PHT with UTC+8 math), repeated-issue surface (chronic machines from v_logbook_truth), standards lookup detector (ISO/SAE/SMRP/IEC/ASHRAE/NFPA), voice command shortcuts (open logbook / show analytics / schedule PM → page nav), AI quality thumbs UI on every reply (persisted to ai_cost_log.quality_rating), worker-discipline biasing in prompt, goodbye detector ('tapos na' / 'yun lang' → clean session end), confidence-calibration anchor (hedge on small samples), long-session pacing (>=10 turns nudges break), proactive-alerts override (critical alerts FIRST sentence). Re-prime cache for all PWA users.
// const CACHE_NAME  = 'workhive-shell-v112';  // bump 2026-05-20: voice-handler.js + wh-tts.js Phase 4.19-4.23 second 10-turn flywheel (turns #15-#24, TRUST + AUDIO QUALITY + OBSERVABILITY + CROSS-SURFACE): hallucination guard prompt anchor, citation rule, mic-tap interrupts in-flight audio, TTS latency ratchet, ai-gateway rate-limit + fallback UX, acronym SSML spell-out (MTBF/OEE/PM/RPN read as letters), assistant.html cross-surface journal pull, ai_cost_log surfaced, conversation-end ack on overlay close. Re-prime cache for all PWA users.
// const CACHE_NAME  = 'workhive-shell-v111';  // bump 2026-05-20: voice-handler.js Phase 4.9-4.18 10-turn flywheel expansion (turns #5-#14): persona-switch utterance, stale-state guard (15-min threshold), topic-interruption signal, thanks/ack short-circuit, asset-context auto-priming from logbook, first-turn greeting, code-switch anchor in prompt, sensitive-topic redirect (HR/legal/financial → supervisor), worker-name personalization with 'kapatid' fallback, repeat-that handler ("ulit nga" replays last reply). Re-prime cache for all PWA users.
// const CACHE_NAME  = 'workhive-shell-v110';  // bump 2026-05-20: voice-handler.js Phase 4.7 clarification-recovery routing — bare "logbook" / "PM" / "analytics" / "asset hub" replies after the streak-ceiling "what page would help?" prompt now route DIRECTLY to that intent (high confidence, clarification_pending cleared) instead of dead-ending in another clarify loop. Re-prime cache for all PWA users.
// const CACHE_NAME  = 'workhive-shell-v109';  // bump 2026-05-20: voice-handler.js Phase 4.5/4.6 dialog continuity — PRIOR TOPIC HANDLE block in the system prompt (pronoun resolution: 'it' / 'that' / 'yan' / 'yun' resolved to the prior intent) + natural-language SLOT ENUMERATION ('You already know: asset tag = P-203') replacing the raw JSON dump. Multi-turn continuity now deterministic. Re-prime cache for all PWA users.
// const CACHE_NAME  = 'workhive-shell-v108';  // bump 2026-05-20: voice-handler.js Phase 4.2/4.3/4.4 sister handlers — negation bypass (no / cancel / wala / hindi exits the topic and clears dialog state), noise transcript guard (empty / 1-2 char / "uh" / "um" skips the LLM call and renders "didn't catch that"), clarification-loop ceiling (after 2 consecutive clarifies, switch prompt shape + hard reset). Re-prime cache for all PWA users.
// const CACHE_NAME  = 'workhive-shell-v107';  // bump 2026-05-20: voice-handler.js Phase 4.1 follow-up affirmation detector ("Yes, the details" bypasses topic-switch UI) + hive.html realtime listeners moved from dead `assets` table to `asset_nodes` + signal-trust fixes (pm-scheduler/index/logbook) + 33 L0 bug-class validators wired. Re-prime cache for all PWA users.
// const CACHE_NAME  = 'workhive-shell-v106';  // bump 2026-05-20: canonical drift flywheel turn 11 — 27 v_*_truth views shipped + 70 consumer SELECTs migrated to view reads (HTML + edge fns); inventory.html stockStatus refactored to trust is_low_stock from the view; agent_memory phase-2 collision fixed; voice-handler.js cleared. Re-prime cache.
// const CACHE_NAME  = 'workhive-shell-v105';  // bump 2026-05-20: AI Prompt Regression L4 — voice-handler.js system prompt now carries the Platform Metric Anchors block (MTBF/MTTR -> ISO 14224, OEE -> ISO 22400-2 / Nakajima, PM -> SMRP, RPN -> IEC 60812, RCM -> SAE JA1011, anomaly -> Z-Score). Re-prime cache for voice answers to be standards-anchored.
// const CACHE_NAME  = 'workhive-shell-v104';  // bump 2026-05-20: Tier-S citation visibility 52% -> 100% — 8 pages now cite their registered standard short_name (marketplace + marketplace-seller-profile + marketplace-seller + skillmatrix + achievements + founder-console + hive maturity-stair). Re-prime cache for the chip text.
// const CACHE_NAME  = 'workhive-shell-v103';  // bump 2026-05-20: massive L2 expansion — 6 dashboards added manifest link (analytics/analytics-report/platform-health/achievements/founder-console/ph-intelligence); asset-hub FMEA cites IEC 60812:2018; hive adoption-risk cites WorkHive Adoption Risk; platform-health verdict cites WorkHive Platform Health. Re-prime cache so PWA users see the chip + manifest fixes.
// const CACHE_NAME  = 'workhive-shell-v102';  // bump 2026-05-20: drift wiring — index.html ops-home Today's One Thing now reads v_amc_truth + v_sensor_truth + v_alert_truth; hive.html pattern-alerts panel + asset-hub anomaly banner now read truth views. Re-prime cache so PWA users see the canonical-wired renderers.
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
  // 12KB each; full-res source PNGs are at /brand_assets/{James,Rosa}.png).
  // Filenames retain the original "james"/"rosa" suffixes after the
  // 2026-05-20 Hezekiah/Zaniah rename — same artwork, same files.
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
