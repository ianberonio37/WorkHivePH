// ─────────────────────────────────────────────────────────────────────────────
// session-timeout.js — Phase 2.4 of STRATEGIC_ROADMAP (shared device pattern)
//
// On a shared Filipino plant tablet, worker A finishes their shift and
// worker B picks up the same device. Without a session timeout, worker B
// continues writing as worker A — every logbook entry mis-attributed,
// every PM completion under the wrong name. This is a real adoption
// blocker, not a theoretical one.
//
// Behaviour:
//   1. Track last activity (mousemove, keydown, touchstart, click).
//   2. After IDLE_LIMIT_MS of no activity, show a non-blocking modal:
//      "Are you still <name>? Tap continue to keep working, tap switch to
//      let someone else sign in."
//   3. After IDLE_HARD_LIMIT_MS (longer), force-clear identity and redirect
//      to signin (no modal: assume the tablet was abandoned).
//
// Defaults are conservative: 15-min soft prompt, 60-min hard clear. The
// numbers reflect Filipino industrial shift reality where workers often
// step away from the tablet for 5-10 min for an inspection round.
//
// To opt-out on a single page (e.g. assistant.html where the worker may
// be reading without typing for long stretches):
//   window._whSessionTimeoutDisabled = true;
//
// Skills consulted:
//   security (next-worker-inherits-previous-identity risk on shared tablet)
//   mobile-maestro (shared-tablet hand-over, conservative idle thresholds)
//   notifications (non-blocking modal, not toast — the worker MUST see it)
// ─────────────────────────────────────────────────────────────────────────────

(function () {
  if (typeof window === 'undefined') return;
  if (window._whSessionTimeoutMounted) return;
  window._whSessionTimeoutMounted = true;

  const IDLE_LIMIT_MS      = 15 * 60 * 1000;   // soft prompt at 15 min
  const IDLE_HARD_LIMIT_MS = 60 * 60 * 1000;   // hard clear at 60 min
  const CHECK_INTERVAL_MS  = 30 * 1000;        // tick every 30s

  // Pages that share the same auth identity. The hard-clear redirects here.
  const SIGN_IN_URL = 'index.html?signin=1';

  let lastActivity = Date.now();
  let modalShown = false;

  function bump() {
    lastActivity = Date.now();
    // If the modal is up and the user just interacted, dismiss it
    // (the activity counts as "yes I'm still here").
    if (modalShown) dismiss();
  }

  function activeWorker() {
    try {
      return localStorage.getItem('wh_last_worker')
        || localStorage.getItem('wh_worker_name')
        || localStorage.getItem('workerName')
        || '';
    } catch (_) { return ''; }
  }

  function clearIdentityHard() {
    try {
      [
        'wh_last_worker', 'wh_worker_name', 'workerName',
        'wh_active_hive_id', 'wh_hive_id', 'wh_hive_name', 'wh_hive_role', 'wh_hive_code',
      ].forEach((k) => localStorage.removeItem(k));
    } catch (_) {}
    try {
      // Best-effort Supabase signOut. If the global isn't available we
      // just navigate; the signin page handles a stale session.
      if (window.db && window.db.auth && typeof window.db.auth.signOut === 'function') {
        window.db.auth.signOut();
      }
    } catch (_) {}
    window.location.href = SIGN_IN_URL;
  }

  function showPrompt() {
    if (modalShown) return;
    if (window._whSessionTimeoutDisabled) return;
    const name = activeWorker();
    if (!name) return;   // nothing to protect

    modalShown = true;
    const overlay = document.createElement('div');
    overlay.id = 'wh-idle-overlay';
    overlay.style.cssText = [
      'position:fixed', 'inset:0', 'z-index:99999',
      'display:flex', 'align-items:center', 'justify-content:center',
      'background:rgba(11,15,26,0.78)', 'backdrop-filter:blur(4px)',
      'font-family:"Poppins",system-ui,sans-serif', 'color:#F4F6FA',
    ].join(';');

    const card = document.createElement('div');
    card.style.cssText = [
      'background:#162032', 'border:1px solid rgba(255,255,255,0.12)',
      'border-radius:1rem', 'padding:1.5rem 1.25rem',
      'max-width:340px', 'width:calc(100vw - 2rem)',
      'box-shadow:0 12px 40px rgba(0,0,0,0.55)', 'text-align:center',
    ].join(';');
    card.innerHTML = `
      <div style="font-size:1.85rem;margin-bottom:0.4rem;">🛡️</div>
      <h3 style="margin:0 0 0.4rem;font-size:1.0rem;font-weight:800;">Are you still ${_esc(name)}?</h3>
      <p style="margin:0 0 1.1rem;font-size:0.78rem;color:rgba(255,255,255,0.7);line-height:1.45;">
        This tablet has been idle for 15 minutes. Confirm you are still working, or sign out so the next worker can take over.
      </p>
      <div style="display:flex;gap:0.5rem;">
        <button id="wh-idle-continue" type="button" style="flex:1;padding:0.7rem;border-radius:0.6rem;font-weight:700;font-size:0.8rem;color:#162032;background:linear-gradient(135deg,#F7A21B,#FDB94A);border:0;cursor:pointer;min-height:44px;">Continue</button>
        <button id="wh-idle-signout" type="button" style="flex:1;padding:0.7rem;border-radius:0.6rem;font-weight:700;font-size:0.8rem;color:#F4F6FA;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);cursor:pointer;min-height:44px;">Sign out</button>
      </div>
    `;
    overlay.appendChild(card);
    document.body.appendChild(overlay);

    document.getElementById('wh-idle-continue').addEventListener('click', () => {
      bump(); dismiss();
    });
    document.getElementById('wh-idle-signout').addEventListener('click', clearIdentityHard);
  }

  function dismiss() {
    const overlay = document.getElementById('wh-idle-overlay');
    if (overlay) overlay.remove();
    modalShown = false;
  }

  function tick() {
    if (window._whSessionTimeoutDisabled) return;
    if (!activeWorker()) return;
    const idle = Date.now() - lastActivity;
    if (idle >= IDLE_HARD_LIMIT_MS) {
      clearIdentityHard();
      return;
    }
    if (idle >= IDLE_LIMIT_MS) {
      showPrompt();
    }
  }

  function _esc(s) {
    return String(s || '').replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[c]);
  }

  function _attachActivityListeners() {
    const evts = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll', 'click'];
    for (let i = 0; i < evts.length; i++) {
      window.addEventListener(evts[i], bump, { passive: true });
    }
  }

  // Mount when the page is ready. Timer is stored in a named global so it
  // can be cleared on unload (defence-in-depth against leaked timers).
  let _whIdleTickTimer = null;
  function mount() {
    _attachActivityListeners();
    _whIdleTickTimer = setInterval(tick, CHECK_INTERVAL_MS);
    window.addEventListener('beforeunload', () => {
      if (_whIdleTickTimer) clearInterval(_whIdleTickTimer);
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
