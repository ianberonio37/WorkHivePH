// ─────────────────────────────────────────────────────────────────────────────
// form-autosave.js — Phase 2.3 of STRATEGIC_ROADMAP (brownout-safe state)
//
// Auto-persists form state to localStorage on a heartbeat so a brownout,
// browser crash, or accidental tab close mid-entry never loses the
// worker's in-progress writing. On next load the form is restored
// SILENTLY (no prompt — the doctrine says "the product bends to the plant,
// not the other way round").
//
// API:
//   whAutosave({
//     formSelector: '#entry-form',  // form OR container whose inputs to track
//     key:          'wh_logbook_draft',
//     intervalMs:   5000,           // default 5s
//     fields:       ['machine','problem','action'],  // optional whitelist
//     onRestore:    (data) => {...} // optional callback after restore
//   });
//
//   window.whClearAutosave('wh_logbook_draft');  // call on successful submit
//
// Skills consulted:
//   mobile-maestro (brownout reality: no prompts, silent recovery)
//   security (no PII to remote storage; localStorage is per-device, per-origin)
//   frontend (works on input + textarea + select; ignores type=password,
//     type=file because those can't be safely restored)
// ─────────────────────────────────────────────────────────────────────────────

(function () {
  if (typeof window === 'undefined') return;
  if (window.whAutosave) return;

  const _timers = new Map();
  const _instances = new Map();

  function _collect(container, fieldWhitelist) {
    const out = {};
    if (!container) return out;
    const nodes = container.querySelectorAll('input, textarea, select');
    for (const el of nodes) {
      if (!el.name && !el.id) continue;
      const key = el.name || el.id;
      if (fieldWhitelist && !fieldWhitelist.includes(key)) continue;
      const t = (el.type || '').toLowerCase();
      if (t === 'password' || t === 'file') continue;
      if (t === 'checkbox' || t === 'radio') {
        if (!el.checked) continue;
        out[key] = el.value;
      } else {
        if (el.value === '') continue;
        out[key] = el.value;
      }
    }
    return out;
  }

  function _restore(container, data) {
    if (!container || !data) return;
    for (const [key, value] of Object.entries(data)) {
      const el = container.querySelector(
        `[name="${CSS.escape(key)}"], #${CSS.escape(key)}`
      );
      if (!el) continue;
      const t = (el.type || '').toLowerCase();
      if (t === 'checkbox' || t === 'radio') {
        el.checked = (el.value === value);
      } else {
        el.value = value;
      }
      try { el.dispatchEvent(new Event('input', { bubbles: true })); } catch (_) {}
    }
  }

  function whAutosave(opts) {
    opts = opts || {};
    const sel = opts.formSelector || opts.selector;
    const key = opts.key;
    if (!sel || !key) {
      console.warn('whAutosave: formSelector + key are required');
      return null;
    }
    const intervalMs = typeof opts.intervalMs === 'number' ? opts.intervalMs : 5000;
    const fields    = Array.isArray(opts.fields) ? opts.fields : null;
    const onRestore = typeof opts.onRestore === 'function' ? opts.onRestore : null;

    const container = typeof sel === 'string'
      ? document.querySelector(sel)
      : sel;
    if (!container) {
      console.warn('whAutosave: container not found for', sel);
      return null;
    }

    // Silent restore on mount. The doctrine: no prompt. If there's a draft,
    // it just appears. Worker can edit or clear; nothing pops up demanding
    // a yes/no decision under brownout conditions.
    try {
      const raw = localStorage.getItem(key);
      if (raw) {
        const data = JSON.parse(raw);
        if (data && typeof data === 'object') {
          _restore(container, data);
          if (onRestore) {
            try { onRestore(data); } catch (_) {}
          }
        }
      }
    } catch (_) {}

    const tick = () => {
      try {
        const snap = _collect(container, fields);
        if (Object.keys(snap).length === 0) {
          // Don't write an empty object on every tick — clear once instead.
          localStorage.removeItem(key);
        } else {
          localStorage.setItem(key, JSON.stringify(snap));
        }
      } catch (_) {}
    };

    // Heartbeat + on-blur capture (which fires sooner than the 5s tick).
    const timer = setInterval(tick, intervalMs);
    container.addEventListener('change', tick);
    container.addEventListener('input',  _debounce(tick, 800));

    _timers.set(key, timer);
    _instances.set(key, { container, fields });
    return { stop: () => { clearInterval(timer); _timers.delete(key); _instances.delete(key); } };
  }

  function whClearAutosave(key) {
    try { localStorage.removeItem(key); } catch (_) {}
    const t = _timers.get(key);
    if (t) clearInterval(t);
    _timers.delete(key);
    _instances.delete(key);
  }

  function _debounce(fn, ms) {
    let h = null;
    return function (...args) {
      clearTimeout(h);
      h = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  window.whAutosave      = whAutosave;
  window.whClearAutosave = whClearAutosave;
})();
