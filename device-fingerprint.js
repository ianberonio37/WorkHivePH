// ─────────────────────────────────────────────────────────────────────────────
// device-fingerprint.js — Phase 2.7 of STRATEGIC_ROADMAP (cybersecurity baseline)
//
// First-step anomalous-login detection without third-party geolocation. On
// every page load with an authenticated worker, computes a deterministic
// client-side fingerprint and writes a 'new_device' audit event when the
// fingerprint changes. The supervisor sees these in the hive audit log:
// if a worker's identity is suddenly active from a different browser /
// device / time zone, that's a signal worth investigating.
//
// What we capture (no PII, no third-party calls):
//   - User-Agent string (truncated)
//   - Screen size (W x H)
//   - Color depth
//   - Hardware concurrency (CPU cores reported)
//   - Time zone IANA name (Intl.DateTimeFormat)
//   - Language tag
//
// Hashed with subtle.digest('SHA-256') into a hex fingerprint. The raw
// values are stored in audit meta so the supervisor sees WHAT changed
// (UA bump vs different timezone vs different screen) when triaging.
//
// This is NOT 2FA. Real MFA + SSO is deferred to Phase 5 Track B (Enterprise
// Auth). This module's job is the cheap detective control that catches
// "someone else is logged in as Juan from a different device" without
// blocking legitimate worker activity.
//
// Skills consulted:
//   security (detective vs preventive controls; light baseline before MFA)
//   notifications (no toast — write to audit log so supervisor reviews)
//   multitenant-engineer (hive_id required for audit log)
// ─────────────────────────────────────────────────────────────────────────────

(function () {
  if (typeof window === 'undefined') return;
  if (window._whDeviceFingerprintMounted) return;
  window._whDeviceFingerprintMounted = true;

  const FP_KEY = 'wh_device_fp';

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
      ua:    (navigator.userAgent || '').slice(0, 200),
      sw:    screen ? screen.width  : 0,
      sh:    screen ? screen.height : 0,
      depth: screen ? screen.colorDepth : 0,
      hc:    navigator.hardwareConcurrency || 0,
      tz,
      lang:  navigator.language || '',
    };
  }

  async function _computeFingerprint() {
    const inputs = _fingerprintInputs();
    const seed = [inputs.ua, inputs.sw, inputs.sh, inputs.depth, inputs.hc, inputs.tz, inputs.lang].join('|');
    const hash = await _sha256Hex(seed);
    return { hash, inputs };
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

  // Diff helper so the audit-log meta tells the supervisor WHAT changed.
  function _diffInputs(prev, next) {
    const out = {};
    for (const k of Object.keys(next)) {
      if (!prev || prev[k] !== next[k]) {
        out[k] = { from: prev ? prev[k] : null, to: next[k] };
      }
    }
    return out;
  }

  async function check() {
    const worker = _activeWorker();
    const hive   = _activeHive();
    if (!worker || !hive) return;          // no identity, nothing to protect

    const next = await _computeFingerprint();
    if (!next.hash) return;                 // subtle.digest unavailable

    let prev = null;
    try { prev = JSON.parse(localStorage.getItem(FP_KEY) || 'null'); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }

    const isFirst = !prev || !prev.hash;
    if (isFirst) {
      try { localStorage.setItem(FP_KEY, JSON.stringify(next)); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
      return;
    }

    if (prev.hash === next.hash) return;     // same device, nothing to do

    const changed = _diffInputs(prev.inputs || {}, next.inputs || {});
    try { localStorage.setItem(FP_KEY, JSON.stringify(next)); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }

    // Best-effort audit-log write. Schema matches hive.html writeAuditLog().
    try {
      if (!window.db || !window.db.from) return;
      await window.db.from('hive_audit_log').insert({
        hive_id:     hive,
        actor:       worker,
        action:      'new_device',
        target_type: 'worker_profiles',
        target_id:   null,
        target_name: worker,
        meta:        { changed_fields: changed, fp: next.hash.slice(0, 16) },
      });
    } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
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
