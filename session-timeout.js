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

  // Production defaults: 15-min soft prompt, 60-min hard clear, 30s tick.
  // A TEST harness may shrink these via window.WH_IDLE_TIMEOUT_OVERRIDE
  // (= { idle, hard, check } in ms) set BEFORE this script runs — e.g.
  // Playwright addInitScript — so the idle→prompt→hard-clear sequence is
  // observable without waiting an hour (Arc I I2/A test-hook). Production
  // never sets the override, so behaviour is byte-identical to before. Each
  // value is sanity-floored to a POSITIVE number, so a bad/zero override
  // can NEVER disable the protection (it falls back to the default).
  const _idleOverride = (typeof window !== 'undefined' && window.WH_IDLE_TIMEOUT_OVERRIDE) || {};
  const _posMs = (v, dflt) => (typeof v === 'number' && v > 0 ? v : dflt);
  const IDLE_LIMIT_MS      = _posMs(_idleOverride.idle,  15 * 60 * 1000); // soft prompt at 15 min
  const IDLE_HARD_LIMIT_MS = _posMs(_idleOverride.hard,  60 * 60 * 1000); // hard clear at 60 min
  const CHECK_INTERVAL_MS  = _posMs(_idleOverride.check, 30 * 1000);      // tick every 30s

  // Pages that share the same auth identity. The hard-clear redirects here.
  // T2/T8 (2026-08-24): carry the CURRENT page as ?return= so re-auth lands the person back
  // where they were working — index's resolver + both submit paths honor it (T1). Computed at
  // redirect time (not load time), inline rather than via utils.js: this file is precached
  // shell and must not depend on load order.
  const SIGN_IN_URL = 'index.html?signin=1';
  /* T8 (2026-08-26): carry the REASON, not just the destination. Arriving at a sign-in modal with no
     explanation is indistinguishable from being logged out at random - the worker was mid-task, and
     the question in their head is "did I lose what I was doing?". The answer is no, and it can be
     said truthfully: clearIdentityHard wipes only the IDENTITY keys (wh_last_worker, the hive keys),
     never the whAutoSaveDraft entries, and anything already saved is in the database. */
  const _signInUrlWithReturn = (reason) => SIGN_IN_URL + (reason ? '&reason=' + reason : '')
    + '&return=' + encodeURIComponent(
      (window.location.pathname.split('/').pop() || 'index.html')
      + window.location.search + window.location.hash);

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
      return whWorker()
        || /* storage-key-allow: legacy worker-name fallback (current writes use wh_last_worker) */ whWorker()
        || '';
    } catch (_) { return ''; }
  }

  /* T8: the reason is a PARAMETER because this one function serves three different events - an
     automatic idle timeout, the worker deliberately pressing Sign out, and a sign-out in another
     tab. They are not the same thing to the person arriving at the sign-in screen, and telling a
     worker who just pressed Sign out that their session 'timed out' is simply false. */
  function clearIdentityHard(reason) {
    try {
      [
        'wh_last_worker', 'wh_worker_name', 'workerName',
        'wh_active_hive_id', 'wh_hive_id', 'wh_hive_name', 'wh_hive_role', 'wh_hive_code',
      ].forEach((k) => localStorage.removeItem(k));
    } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
    try {
      // Best-effort Supabase signOut. If the global isn't available we
      // just navigate; the signin page handles a stale session.
      if (window.db && window.db.auth && typeof window.db.auth.signOut === 'function') {
        window.db.auth.signOut();
      }
    } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
    window.location.href = _signInUrlWithReturn(reason);
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
      'font-family:var(--wh-font, "Poppins",system-ui,sans-serif)', 'color:var(--wh-cloud, #F4F6FA)',
    ].join(';');

    const card = document.createElement('div');
    card.style.cssText = [
      'background:var(--wh-navy, #162032)', 'border:1px solid rgba(255,255,255,0.12)',
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
        <button id="wh-idle-continue" type="button" style="flex:1;padding:0.7rem;border-radius:0.6rem;font-weight:700;font-size:0.8rem;color:var(--wh-navy, #162032);background:linear-gradient(135deg,var(--wh-orange, #F7A21B),var(--wh-orange-light, #FDB94A));border:0;cursor:pointer;min-height:44px;">Continue</button>
        <button id="wh-idle-signout" type="button" style="flex:1;padding:0.7rem;border-radius:0.6rem;font-weight:700;font-size:0.8rem;color:var(--wh-cloud, #F4F6FA);background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);cursor:pointer;min-height:44px;">Sign out</button>
      </div>
    `;
    overlay.appendChild(card);
    document.body.appendChild(overlay);

    document.getElementById('wh-idle-continue').addEventListener('click', () => {
      bump(); dismiss();
    });
    // no reason: this one was deliberate, and the sign-in screen should not explain it away
    document.getElementById('wh-idle-signout').addEventListener('click', () => clearIdentityHard());
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
      clearIdentityHard('idle');
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
  /* Captured AT MOUNT, because by the time the storage event fires localStorage already holds
     the NEW hive - reading it then would compare the new value against itself and never fire. */
  var _mountedHiveId = '', _mountedHiveName = '';
  try {
    _mountedHiveId   = localStorage.getItem('wh_active_hive_id') || '';
    _mountedHiveName = localStorage.getItem('wh_hive_name') || '';
  } catch (_) { /* empty-catch-allow: private mode -> the notice simply never fires */ }

  function mount() {
    _attachActivityListeners();
    _whIdleTickTimer = setInterval(tick, CHECK_INTERVAL_MS);
    window.addEventListener('beforeunload', () => {
      if (_whIdleTickTimer) clearInterval(_whIdleTickTimer);
    });
    // T148 (2026-08-25): sign-out in ANOTHER TAB clears the shared identity keys, but this tab
    // used to sit painted-and-stale, looking signed in while identity was gone (measured: worker
    // null, no banner, page content still up). The storage event is the cross-tab signal; route
    // it through the SAME return-carrying redirect the idle path uses, so the person comes back
    // to this exact page after signing in again. Writes were already guarded (T38); this closes
    // the silent-looking half.
    window.addEventListener('storage', (e) => {
      if (e.key === 'wh_last_worker' && !e.newValue && !activeWorker()) {
        window.location.href = _signInUrlWithReturn('othertab');
      }
      /* T148 (2026-08-27): the HIVE SWITCH had the same shape and no handler. Measured with two
         tabs: switching hive in tab A left tab B rendering the OTHER hive's figures while storage
         already said the new one - the cross-tenant confusion T51 exists to prevent, and worse than
         a stale number because the person just switched and believes they are looking at the new
         plant.
         ★IT TELLS RATHER THAN RELOADS, deliberately. Auto-reloading somebody's other tab would
         discard a half-typed entry to fix a display problem, and this platform's whole posture on
         interruption is that typed work survives. So: name the mismatch, name BOTH hives so the
         reader knows which numbers they are looking at, and let them choose the moment. */
      if (e.key === 'wh_active_hive_id' && e.newValue && e.newValue !== _mountedHiveId && !document.getElementById('wh-hive-switch-notice')) {
        /* ★DEFER THE READ: a hive switch writes SEVERAL keys, and the storage events arrive one per
           key in write order. Reading wh_hive_name the instant the ID event lands read the name the
           switch had not replaced yet, and the notice said 'You switched to Baguio... still showing
           Baguio' - naming the same hive twice, which is worse than silence because it reads like a
           bug in the switch rather than a stale tab. One tick lets the sibling write land. */
        setTimeout(function () { _showHiveSwitchNotice(); }, 250);
      }
    });
  }

  function _showHiveSwitchNotice() {
    if (document.getElementById('wh-hive-switch-notice')) return;
    (function () {
        var was = _mountedHiveName || 'another hive';
        var now = '';
        try { now = localStorage.getItem('wh_hive_name') || ''; } catch (_) { now = ''; }
        /* If the name still matches what this tab mounted with, the sibling write has not landed or
           only the id moved - say it neutrally rather than naming one hive twice. */
        if (!now || now === was) now = 'another hive';
        var n = document.createElement('div');
        n.id = 'wh-hive-switch-notice';
        n.setAttribute('role', 'status');
        n.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:9998;padding:0.7rem 1rem;'
          + 'background:rgba(247,162,27,0.14);border-top:1px solid rgba(247,162,27,0.4);'
          + 'color:var(--wh-orange-text,#F7A21B);font-size:0.76rem;line-height:1.45;text-align:center;';
        n.textContent = 'You switched to ' + now + ' in another tab. This tab is still showing '
          + was + '. Reload to catch up.';
        var r = document.createElement('button');
        r.type = 'button';
        r.textContent = 'Reload';
        r.style.cssText = 'margin-left:0.6rem;min-height:44px;padding:0 0.9rem;border-radius:0.5rem;cursor:pointer;'
          + 'background:rgba(247,162,27,0.2);border:1px solid rgba(247,162,27,0.5);color:inherit;font:inherit;';
        r.addEventListener('click', function () { window.location.reload(); });
        n.appendChild(r);
        document.body.appendChild(n);
    })();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
