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

// ─────────────────────────────────────────────
// Achievement tier system
// ─────────────────────────────────────────────

const ACHIEVEMENT_TIERS = [
  { id: 'legend',   min: 91, color: '#F7A21B', label: 'Legend'   },
  { id: 'platinum', min: 76, color: '#29B6D9', label: 'Platinum' },
  { id: 'gold',     min: 51, color: '#F7A21B', label: 'Gold'     },
  { id: 'silver',   min: 26, color: '#94A3B8', label: 'Silver'   },
  { id: 'bronze',   min: 11, color: '#CD7F32', label: 'Bronze'   },
  { id: 'iron',     min:  0, color: '#7B8794', label: 'Iron'     },
];

function getWorkerTier(topLevel) {
  return ACHIEVEMENT_TIERS.find(t => (topLevel || 0) >= t.min)
    || ACHIEVEMENT_TIERS[ACHIEVEMENT_TIERS.length - 1];
}

// Render a tier-framed avatar circle.
// size: pixel width/height — 42, 36, 32, 28, 22
// Badge (level pill) shown only when size >= 32 and topLevel > 0.
function renderWorkerAvatar(workerName, topLevel, size) {
  const sz   = size || 32;
  const tier = getWorkerTier(topLevel || 0);
  const init = escHtml(
    String(workerName || '?').trim().split(/\s+/).map(function (w) { return w[0]; }).join('').slice(0, 2).toUpperCase()
  );
  const fs = sz >= 42 ? '0.95rem' : sz >= 32 ? '0.72rem' : sz >= 28 ? '0.65rem' : '0.55rem';
  const badge = (sz >= 32 && (topLevel || 0) > 0)
    ? '<span class="wh-avatar-lvl">' + (topLevel || 0) + '</span>'
    : '';
  return '<div class="wh-avatar wh-tier-' + tier.id + '" '
    + 'style="width:' + sz + 'px;height:' + sz + 'px;font-size:' + fs + ';--tier-clr:' + tier.color + ';" '
    + 'title="' + escHtml(workerName) + ' - ' + tier.label + ' Lv.' + (topLevel || 0) + '">'
    + init + badge + '</div>';
}

// Batch-load highest achievement level per worker.
// Returns { workerName: topLevel }. Safe to call when table does not exist yet.
async function loadWorkerTiers(db, workerNames) {
  if (!workerNames || !workerNames.length) return {};
  try {
    const { data } = await db
      .from('worker_achievements')
      .select('worker_name, current_level')
      .in('worker_name', workerNames);
    const map = {};
    for (const row of (data || [])) {
      if (!map[row.worker_name] || row.current_level > map[row.worker_name]) {
        map[row.worker_name] = row.current_level;
      }
    }
    return map;
  } catch (_) { return {}; }
}

// Inject tier CSS once — runs immediately when utils.js loads
(function () {
  if (document.getElementById('wh-tier-styles')) return;
  const s = document.createElement('style');
  s.id = 'wh-tier-styles';
  s.textContent = [
    '.wh-avatar{position:relative;border-radius:50%;flex-shrink:0;',
    'background:linear-gradient(135deg,#1F2E45,#2A3D58);',
    'display:flex;align-items:center;justify-content:center;',
    'font-family:"Poppins",sans-serif;font-weight:700;color:#F4F6FA;',
    'border:2.5px solid var(--tier-clr,#7B8794);}',

    '.wh-avatar-lvl{position:absolute;bottom:-7px;left:50%;transform:translateX(-50%);',
    'background:var(--tier-clr,#7B8794);color:#162032;',
    'font-size:8px;font-weight:800;padding:1px 4px;',
    'border-radius:999px;border:1.5px solid #162032;',
    'min-width:18px;text-align:center;line-height:1.5;',
    'pointer-events:none;white-space:nowrap;}',

    '.wh-tier-iron{border-color:#7B8794;}',
    '.wh-tier-bronze{border-color:#CD7F32;animation:wh-shimmer 3s ease-in-out infinite;}',
    '.wh-tier-silver{border-color:#94A3B8;animation:wh-sweep 2.5s linear infinite;}',
    '.wh-tier-gold{border-color:#F7A21B;animation:wh-glow-gold 2s ease-in-out infinite;}',
    '.wh-tier-platinum{border-color:#29B6D9;animation:wh-glow-blue 2s ease-in-out infinite;}',

    '.wh-tier-legend{border:2.5px solid transparent;}',
    '.wh-tier-legend::before{content:"";position:absolute;inset:-3px;border-radius:50%;',
    'background:conic-gradient(#F7A21B,#29B6D9,#F7A21B);',
    'animation:wh-spin 2s linear infinite;z-index:-1;}',

    '@keyframes wh-shimmer{0%,100%{box-shadow:0 0 4px rgba(205,127,50,0.2);}',
    '50%{box-shadow:0 0 10px rgba(205,127,50,0.6);}}',

    '@keyframes wh-sweep{0%,100%{box-shadow:0 0 0 rgba(148,163,184,0);}',
    '50%{box-shadow:0 0 10px rgba(148,163,184,0.5);}}',

    '@keyframes wh-glow-gold{0%,100%{box-shadow:0 0 4px rgba(247,162,27,0.3);}',
    '50%{box-shadow:0 0 14px rgba(247,162,27,0.7);}}',

    '@keyframes wh-glow-blue{0%,100%{box-shadow:0 0 4px rgba(41,182,217,0.3);}',
    '50%{box-shadow:0 0 14px rgba(41,182,217,0.7);}}',

    '@keyframes wh-spin{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}'
  ].join('');
  document.head.appendChild(s);
}());
