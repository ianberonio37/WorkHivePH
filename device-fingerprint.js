// ───────────────────────────────────────────────────────────────────────────
// device-fingerprint.js — Phase 2.7 of STRATEGIC_ROADMAP (cybersecurity baseline)
//
// First-step anomalous-login detection without third-party geolocation. The supervisor sees a 'new_device' row in the
// hive audit log when a worker's identity is suddenly active from a device that person has not used before - "someone
// else is logged in as Juan from a different device" - without blocking legitimate work. This is NOT 2FA (real MFA +
// SSO is Phase 5 Track B); it is the cheap detective control.
//
// ★THE CONTROL WAS INVERTED UNTIL 2026-10-13 (found by the design-lens critique of audit-log.html). It compared each
// load's fingerprint with the previous one stored in THIS BROWSER's localStorage. A genuinely new device has empty
// storage, so it took the first-run path and recorded itself silently - the one event the control exists for never
// fired - while the same browser changing its window size, its monitor or its version number DID fire, so the
// supervisor's log filled with identical false alarms ("new device" x26 in six hours, all one browser flipping between
// 1280x720 and 390x844). "Is this device new for this PERSON" cannot be answered from the device's own storage. The
// answer now lives on the server: note_device() (migration 20261013000001) keeps each person's known devices, decides,
// and writes the audit row itself - its actor bound to the caller by wh_bind_audit_actor.
//
// What we hash - STABLE properties only, so the same device keeps one fingerprint (no PII, no third-party calls):
//   - the User-Agent with every version number stripped (a browser update is not a new device)
//   - whether the device has a touch screen (a phone vs a PC; screen PIXELS are gone - a window, a second monitor
//     or a rotated phone changes them, which is how one browser became "a new device" every few minutes)
//   - colour depth and hardware concurrency (CPU cores reported)
//   - the time zone (IANA name) and the browser's language
// Reported once per session per hive; the raw inputs ride in the audit row so a supervisor triaging it sees WHAT the
// device is.
//
// Skills consulted:
//   security (detective vs preventive controls; light baseline before MFA; server-side decisions)
//   notifications (no toast — write to audit log so supervisor reviews)
//   multitenant-engineer (hive_id required; the RPC checks the caller is in the hive it reports to)
// ───────────────────────────────────────────────────────────────────────────

(function () {
  if (typeof window === 'undefined') return;
  if (window._whDeviceFingerprintMounted) return;
  window._whDeviceFingerprintMounted = true;

  const NOTED_KEY = 'wh_device_noted';   // sessionStorage: "fp|hive" already reported in this session
  const OLD_FP_KEY = 'wh_device_fp';     // the browser-local comparison the inverted control used; no longer read

  async function _sha256Hex(input) {
    try {
      if (!window.crypto || !window.crypto.subtle) return null;
      const enc = new TextEncoder().encode(input);
      const buf = await window.crypto.subtle.digest('SHA-256', enc);
      return Array.from(new Uint8Array(buf))
        .map((b) => b.toString(16).padStart(2, '0')).join('');
    } catch (_) { return null; }
  }

  function _fingerprintInputs() {
    let tz = '';
    try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
    return {
      ua:    (navigator.userAgent || '').replace(/\d+(?:[._]\d+)*/g, '').slice(0, 200),
      touch: (navigator.maxTouchPoints || 0) > 0,
      depth: screen ? screen.colorDepth : 0,
      hc:    navigator.hardwareConcurrency || 0,
      tz,
      lang:  navigator.language || '',
    };
  }

  async function _computeFingerprint() {
    const inputs = _fingerprintInputs();
    const seed = [inputs.ua, inputs.touch ? 'touch' : 'pointer', inputs.depth, inputs.hc, inputs.tz, inputs.lang].join('|');
    const hash = await _sha256Hex(seed);
    return { fp: hash ? hash.slice(0, 32) : null, inputs };
  }

  function _activeWorker() {
    try {
      return whWorker()
        || /* storage-key-allow: legacy worker-name fallback (current writes use wh_last_worker) */ whWorker() || '';
    } catch (_) { return ''; }
  }
  function _activeHive() {
    try {
      return whHiveId() || '';
    } catch (_) { return ''; }
  }

  async function check() {
    const worker = _activeWorker();
    const hive   = _activeHive();
    if (!worker || !hive) return;          // no identity, nothing to protect

    try { localStorage.removeItem(OLD_FP_KEY); } catch (_) { /* empty-catch-allow: legacy key cleanup is best-effort */ }

    const next = await _computeFingerprint();
    if (!next.fp) return;                   // subtle.digest unavailable

    const stamp = next.fp + '|' + hive;
    let noted = null;
    try { noted = sessionStorage.getItem(NOTED_KEY); } catch (_) { /* empty-catch-allow: storage blocked - report again */ }
    if (noted === stamp) return;            // already reported this session for this hive

    // The server decides whether this device is new for this PERSON and writes the audit row itself.
    // The client is the page's shared singleton (utils.js getDb() keeps it on window._whSupabaseClient): most pages
    // never expose a window.db, so the old `window.db` guard silently skipped them - audit-log.html among them.
    try {
      const db = window._whSupabaseClient || window.db;
      if (!db || !db.rpc) return;
      const { error } = await db.rpc('note_device', { p_hive_id: hive, p_fp: next.fp, p_inputs: next.inputs });
      if (!error) {
        try { sessionStorage.setItem(NOTED_KEY, stamp); } catch (_) { /* empty-catch-allow: storage blocked */ }
      }
    } catch (_) { /* empty-catch-allow: a detective control never blocks the page */ }
  }

  // Run once after the page settles. Wait 2s so window.db has time to mount
  // on pages that init Supabase late (most pages do).
  function _start() {
    setTimeout(() => { check().catch(() => {}); }, 2000);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _start);
  } else {
    _start();
  }

  window.whDeviceFingerprint = { check };
})();
