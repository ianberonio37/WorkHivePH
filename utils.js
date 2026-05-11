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

// ─────────────────────────────────────────────
// renderSourceChip — KPI source/window chip helper (Phase 3.1)
// ─────────────────────────────────────────────
// Every dashboard card that displays a canonical metric (MTBF, risk, PM
// compliance, etc.) must show WHERE the number came from and WHAT window it
// covers, so users never silently compare a 30-day live snapshot to a 365-day
// nightly snapshot. This function is the single visual contract. Pass an
// options object; returns a `<p>` string ready for innerHTML.
//
// Standard order: freshness . source . window . notes
//   - freshness: "Live data" | "Daily snapshot at 13:00 PHT" | "Live recomputation each refresh"
//   - source:    canonical view name (rendered in <code>), e.g. "v_risk_truth"
//   - window:    "365-day failure window" | "30-day overdue threshold" etc.
//   - notes:     additional clauses (array of strings)
//
// Skill alignment: analytics-engineer ("any custom composite must be labeled"),
// architect (one visual contract per concept), KPI_ENGINE.md rule 2.
function renderSourceChip(opts) {
  opts = opts || {};
  var source    = opts.source    || '';
  var freshness = opts.freshness || '';
  var win       = opts.window    || '';
  var notes     = Array.isArray(opts.notes) ? opts.notes : [];

  var parts = [];
  if (freshness) parts.push(escHtml(freshness));
  if (source) {
    parts.push(
      'Source: <code style="background:rgba(255,255,255,0.06);padding:1px 5px;border-radius:3px;font-size:.95em;">'
      + escHtml(source) + '</code>'
    );
  }
  if (win) parts.push(escHtml(win));
  for (var i = 0; i < notes.length; i++) {
    if (notes[i]) parts.push(escHtml(String(notes[i])));
  }

  return '<p class="wh-source-chip" '
    + 'style="font-size:.62rem;color:rgba(255,255,255,0.4);margin:3px 0 0;line-height:1.35;">'
    + parts.join(' &middot; ')
    + '</p>';
}

// ─────────────────────────────────────────────
// resolveAssetNodeId — writer-side legacy-to-canonical bridge (Phase 5b)
// ─────────────────────────────────────────────
// Phase 5b dropped logbook.asset_ref_id (text) in favour of
// logbook.asset_node_id (uuid). The asset picker in legacy writer surfaces
// (logbook.html, parts-tracker.html) still queries the `assets` table, which
// is keyed by text. This helper looks up the corresponding canonical
// asset_nodes.id (uuid) via the legacy_asset_id bridge column so the writer
// can store the uuid FK on the new logbook column.
//
// Returns null when:
//   - hiveId is missing (solo mode -- asset_nodes is hive-scoped)
//   - legacyAssetId is missing
//   - no asset_node exists for that legacy id in the hive (e.g. user
//     registered an asset but the node wasn't created yet)
//
// Skill alignment: architect (parallel-cutover pattern), data-engineer
// (narrow .maybeSingle lookup, hive-scoped match), KPI_ENGINE.md Phase 5b.
async function resolveAssetNodeId(db, hiveId, legacyAssetId) {
  if (!db || !hiveId || !legacyAssetId) return null;
  try {
    // canonical-allow: bridge helper needs the legacy_asset_id column on the raw graph table
    const { data } = await db.from('asset_nodes')
      .select('id')
      .eq('hive_id', hiveId)
      .eq('legacy_asset_id', legacyAssetId)
      .maybeSingle();
    return data?.id || null;
  } catch (_) {
    return null;
  }
}

// Inverse helper: given a canonical asset_node_id (uuid), return the
// legacy_asset_id (text) that still keys older systems like project_links.
// Used at use-site rather than rewriting the data model of every dependent.
async function resolveLegacyAssetId(db, assetNodeId) {
  if (!db || !assetNodeId) return null;
  try {
    // canonical-allow: bridge helper needs the legacy_asset_id column on the raw graph table
    const { data } = await db.from('asset_nodes')
      .select('legacy_asset_id')
      .eq('id', assetNodeId)
      .maybeSingle();
    return data?.legacy_asset_id || null;
  } catch (_) {
    return null;
  }
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
    /* Base avatar with border-box so all tiers render at the same outer size */
    /* regardless of border thickness/style. Metallic inset shadows give depth. */
    '.wh-avatar{position:relative;border-radius:50%;flex-shrink:0;',
    'box-sizing:border-box;',
    'background:linear-gradient(135deg,#1F2E45,#2A3D58);',
    'display:flex;align-items:center;justify-content:center;',
    'font-family:"Poppins",sans-serif;font-weight:700;color:#F4F6FA;',
    'border:4px solid var(--tier-clr,#7B8794);',
    'box-shadow:inset 1px 1px 2px rgba(255,255,255,0.18),',
    '           inset -1px -1px 2px rgba(0,0,0,0.45);}',

    '.wh-avatar-lvl{position:absolute;bottom:-8px;left:50%;transform:translateX(-50%);',
    'background:var(--tier-clr,#7B8794);color:#162032;',
    'font-size:9px;font-weight:800;padding:1px 5px;',
    'border-radius:999px;border:2px solid #162032;',
    'min-width:20px;text-align:center;line-height:1.5;',
    'pointer-events:none;white-space:nowrap;z-index:3;',
    'box-shadow:0 2px 6px rgba(0,0,0,0.45),',
    '           inset 0 1px 0 rgba(255,255,255,0.3);}',

    /* ── IRON: DASHED border (incomplete/starting feel) + slow breathing ──── */
    '.wh-tier-iron{border:4px dashed #7B8794;animation:wh-breathe-iron 4s ease-in-out infinite;}',

    /* ── BRONZE: RIDGE border (3D embossed metal) + warm shimmer ─────────── */
    '.wh-tier-bronze{border:4px ridge #CD7F32;animation:wh-shimmer 3s ease-in-out infinite;}',

    /* ── SILVER: solid + COMET light sweeping around the rim ─────────────── */
    '.wh-tier-silver{border:4px solid #94A3B8;}',
    '.wh-tier-silver::after{content:"";position:absolute;inset:-4px;border-radius:50%;',
    'pointer-events:none;z-index:0;',
    'background:conic-gradient(from 0deg,transparent 0deg,transparent 300deg,',
    '  rgba(255,255,255,0.4) 330deg,rgba(255,255,255,0.95) 358deg,rgba(255,255,255,0.2) 360deg);',
    '-webkit-mask:radial-gradient(circle,transparent 56%,black 60%);',
    'mask:radial-gradient(circle,transparent 56%,black 60%);',
    'animation:wh-spin 3s linear infinite;}',

    /* ── GOLD: solid + 4 SPARKLE DOTS rotating like a crown ──────────────── */
    '.wh-tier-gold{border:4px solid #F7A21B;animation:wh-glow-gold 2.4s ease-in-out infinite;}',
    '.wh-tier-gold::after{content:"";position:absolute;inset:-3px;border-radius:50%;',
    'pointer-events:none;z-index:0;',
    'background:',
    '  radial-gradient(circle 1.8px at 50% 0%,rgba(255,255,255,1),transparent 60%),',
    '  radial-gradient(circle 1.8px at 100% 50%,rgba(255,255,255,1),transparent 60%),',
    '  radial-gradient(circle 1.8px at 50% 100%,rgba(255,255,255,1),transparent 60%),',
    '  radial-gradient(circle 1.8px at 0% 50%,rgba(255,255,255,1),transparent 60%);',
    'animation:wh-spin 4s linear infinite;}',

    /* ── PLATINUM: CONCENTRIC — solid inner + outer rotating dashed ring ─── */
    '.wh-tier-platinum{border:4px solid #29B6D9;animation:wh-glow-blue 2.4s ease-in-out infinite;}',
    '.wh-tier-platinum::after{content:"";position:absolute;inset:-7px;border-radius:50%;',
    'border:2px dashed rgba(41,182,217,0.85);',
    'pointer-events:none;z-index:0;',
    'animation:wh-spin 6s linear infinite;}',

    /* ── LEGEND: animated multi-color gradient ring + halo ───────────────── */
    '.wh-tier-legend{border:4px solid transparent;}',
    '.wh-tier-legend::before{content:"";position:absolute;inset:-4px;border-radius:50%;',
    'background:conic-gradient(#F7A21B,#FDB94A,#29B6D9,#5FCCE8,#F7A21B);',
    'animation:wh-spin 2s linear infinite;z-index:-1;',
    'filter:drop-shadow(0 0 10px rgba(247,162,27,0.6));}',
    '.wh-tier-legend::after{content:"";position:absolute;inset:-10px;border-radius:50%;',
    'border:1px solid rgba(247,162,27,0.25);pointer-events:none;z-index:0;',
    'animation:wh-spin 8s linear infinite reverse;}',

    /* Keyframes — only Iron/Bronze/Gold/Platinum animate the parent box-shadow. */
    /* Silver uses ::after only (rotating mask). Legend uses ::before/::after.   */
    '@keyframes wh-breathe-iron{0%,100%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.18), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 0 rgba(123,135,148,0);}',
    '50%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.18), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 8px rgba(180,195,210,0.35);}}',

    '@keyframes wh-shimmer{0%,100%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.2), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 6px rgba(205,127,50,0.45);}',
    '50%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.32), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 18px rgba(205,127,50,0.9);}}',

    '@keyframes wh-glow-gold{0%,100%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.22), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 8px rgba(247,162,27,0.55);}',
    '50%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.32), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 22px rgba(247,162,27,0.95);}}',

    '@keyframes wh-glow-blue{0%,100%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.22), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 8px rgba(41,182,217,0.55);}',
    '50%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.32), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 22px rgba(41,182,217,0.95);}}',

    '@keyframes wh-spin{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}'
  ].join('');
  document.head.appendChild(s);
}());
