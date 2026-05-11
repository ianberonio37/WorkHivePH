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
    btn.disabled = true;
    btn.classList.add('is-loading');
    if (!btn.dataset.lockOriginal) {
      btn.dataset.lockOriginal = original;
    }
    try {
      return await asyncFn();
    } finally {
      btn.disabled = false;
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
    btn.classList.add('is-loading');
    return function release() {
      btn.disabled = false;
      btn.classList.remove('is-loading');
    };
  };
})();
