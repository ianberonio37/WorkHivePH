// ─────────────────────────────────────────────
// utils.js — Shared utilities for WorkHive platform
// Loaded before page scripts on every page.
// ─────────────────────────────────────────────

// XSS escape — all 5 characters
function escHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Debounce — delay fn execution until after `wait` ms of silence
function debounce(fn, wait) {
  let t;
  return function (...args) {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), wait);
  };
}

// C4: Session restore — returns worker display_name from localStorage or auth session.
// Call at the top of each page's async init before redirecting to signin.
// Usage:  WORKER_NAME = await restoreIdentityFromSession(db);
//         if (!WORKER_NAME) { window.location.href = 'index.html?signin=1'; return; }
async function restoreIdentityFromSession(db) {
  const cached = localStorage.getItem('wh_last_worker')
               || localStorage.getItem('wh_worker_name')
               || localStorage.getItem('workerName') || '';
  if (cached) return cached;
  try {
    const { data: { session } } = await db.auth.getSession();
    if (!session) return '';
    const { data: profile } = await db.from('worker_profiles')
      .select('display_name').eq('auth_uid', session.user.id).maybeSingle();
    if (profile?.display_name) {
      localStorage.setItem('wh_last_worker', profile.display_name);
      return profile.display_name;
    }
  } catch (_) {}
  return '';
}
