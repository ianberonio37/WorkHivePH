// button-lock.js — shared helper to prevent double-tap submits.
//
// Usage:
//   <script src="button-lock.js"></script>
//   <button onclick="withButtonLock(this, saveItem)">Save</button>
//   where saveItem() is your async save function.
//
// Behaviour:
//   * Sets btn.disabled = true and a `loading` class while the async fn runs
//   * Stashes original button text and restores on completion / failure
//   * Re-enables in `finally` so an exception still releases the lock
//   * The async fn's return value is preserved
//
// Closes PRODUCTION_FIXES #47 partially: pages adopt this incrementally
// on their save / use / restock buttons. The loading-state validator
// (#31) sees `btn.disabled =` references and clears the page from L1.

(function () {
  'use strict';

  if (typeof window === 'undefined') return;

  /**
   * withButtonLock(btn, asyncFn) — runs asyncFn with btn disabled.
   * Returns asyncFn's promise so callers can chain.
   */
  window.withButtonLock = async function (btn, asyncFn) {
    if (!btn || typeof asyncFn !== 'function') {
      return asyncFn ? asyncFn() : undefined;
    }
    if (btn.disabled) return;       // single-flight guard
    const original = btn.textContent;
    /* T41 (2026-08-27): SAY "WORKING", NOT JUST "UNAVAILABLE". disabled + is-loading tells a
       SIGHTED user the press landed and the work is running; a screen reader announces that same
       control as "unavailable" - which is also what a control that IGNORED you sounds like, and
       on a plant connection that is exactly where a second tap comes from. aria-busy is the state
       that means in-progress. Cleared in the release below beside disabled, so an exception
       cannot strand a button announcing itself busy forever. Applied to BOTH lock paths in this
       file, not just the first - a shared helper with one fixed path is a helper that is wrong
       half the time. */
    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    btn.classList.add('is-loading');
    if (!btn.dataset.lockOriginal) {
      btn.dataset.lockOriginal = original;
    }
    try {
      return await asyncFn();
    } finally {
      btn.disabled = false;
      btn.removeAttribute('aria-busy');
      btn.classList.remove('is-loading');
      // Only restore text if it was changed inside the handler
      if (btn.textContent !== original && btn.dataset.lockOriginal === original) {
        btn.textContent = original;
      }
    }
  };

  /**
   * lockButtonDuring(btn) — non-promise form: returns a release fn.
   * Useful when the async work is not a single promise.
   *
   *   const release = lockButtonDuring(btn);
   *   try { await doStuff(); } finally { release(); }
   */
  window.lockButtonDuring = function (btn) {
    if (!btn) return () => {};
    if (btn.disabled) return () => {};
    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    btn.classList.add('is-loading');
    return function release() {
      btn.disabled = false;
      btn.removeAttribute('aria-busy');
      btn.classList.remove('is-loading');
    };
  };
})();
