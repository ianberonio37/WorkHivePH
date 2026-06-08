// capability: alert_toast_inline
// capability: display_source_chip
// ─────────────────────────────────────────────
// utils.js — Shared utilities for WorkHive platform
// Loaded before page scripts on every page.
// ─────────────────────────────────────────────

// ─────────────────────────────────────────────
// getDb() — shared Supabase client singleton
// ─────────────────────────────────────────────
// Calling `supabase.createClient()` more than once per page (or once per
// IIFE) triggers the "Multiple GoTrueClient instances detected" warning
// in the Supabase JS SDK. The clients race on the same localStorage auth
// key and may produce undefined behavior under concurrent reads.
//
// The fix: every script that needs a Supabase client should call
// `window.getDb(url, key)` instead. The first call creates the client;
// subsequent calls return the same instance for the page's lifetime.
//
// Validator: validate_supabase_singleton.py flags any HTML page with >1
// inline `supabase.createClient(...)` call.
window.getDb = function(url, key) {
  if (window._whSupabaseClient) return window._whSupabaseClient;
  if (!window.supabase || typeof window.supabase.createClient !== 'function') {
    throw new Error('getDb() called before @supabase/supabase-js loaded');
  }
  window._whSupabaseClient = window.supabase.createClient(url, key);
  return window._whSupabaseClient;
};

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
    + 'style="font-size:.62rem;color:rgba(255,255,255,0.6);margin:3px 0 0;line-height:1.35;">'
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
async function resolveAssetNodeId(db, hiveId, assetIdOrLegacy) {
  if (!db || !hiveId || !assetIdOrLegacy) return null;
  // The Phase 5c asset picker passes the canonical asset_nodes uuid (exposed by
  // the view as `asset_id`); older callers may still pass a legacy text id
  // (`legacy_asset_id`). Match on whichever the value looks like.
  // IMPORTANT: v_asset_truth renames asset_nodes.id -> asset_id, so select('id')
  // / eq('id') 400s ("column v_asset_truth.id does not exist"). Always asset_id.
  const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(assetIdOrLegacy));
  try {
    let q = db.from('v_asset_truth').select('asset_id').eq('hive_id', hiveId);
    q = isUuid ? q.eq('asset_id', assetIdOrLegacy) : q.eq('legacy_asset_id', assetIdOrLegacy);
    const { data } = await q.maybeSingle();
    return data?.asset_id || null;
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
    // v_asset_truth renames asset_nodes.id -> asset_id; filtering eq('id') 400s
    // ("column v_asset_truth.id does not exist"). The canonical uuid is asset_id.
    const { data } = await db.from('v_asset_truth')
      .select('legacy_asset_id')
      .eq('asset_id', assetNodeId)
      .maybeSingle();
    return data?.legacy_asset_id || null;
  } catch (_) {
    return null;
  }
}

// ─────────────────────────────────────────────
// ocUpdate — optimistic-concurrency update helper (PRODUCTION_FIXES #43)
// ─────────────────────────────────────────────
// Adds an `.eq('updated_at', oldStamp)` guard so a multi-writer race is
// detected at the SQL layer instead of silently overwriting. Returns
// { ok, row, conflict, error }:
//   - ok=true, row=updated row  -> write succeeded
//   - ok=false, conflict=true   -> updated_at didn't match (someone else won)
//   - ok=false, error=Error     -> network / permission failure
//
// Callers wrap their save flow:
//   const { data: cur } = await db.from(t).select('id, updated_at').eq('id', id).single();
//   const res = await ocUpdate(db, t, id, updates, cur.updated_at);
//   if (res.conflict) showToast('Someone else just updated this. Refresh and try again.');
//
// Tables must have `updated_at timestamptz NOT NULL` + a touch trigger
// (see logbook_updated_at migration for the canonical recipe).
//
// Skills consulted: architect (OC pattern), data-engineer (single-statement
// guard, .select() return for conflict detection).
async function ocUpdate(db, table, id, updates, oldStamp) {
  if (!db || !table || !id) {
    return { ok: false, error: new Error('ocUpdate: missing args') };
  }
  try {
    const { data, error } = await db.from(table)
      .update(updates)
      .eq('id', id)
      .eq('updated_at', oldStamp)
      .select('id, updated_at');
    if (error) return { ok: false, error };
    if (!data || data.length === 0) {
      return { ok: false, conflict: true };
    }
    return { ok: true, row: data[0] };
  } catch (e) {
    return { ok: false, error: e };
  }
}

// ─── KPI Tile (Tier G capability: display_kpi_tile) ────────────────────────
// Shared KPI card renderer. Single source of truth for the RAG-coloured
// tile pattern across analytics.html, hive.html, asset-hub.html, predictive.
// Replaces 4 parallel implementations during the Tier G consolidation pass.
//
// opts:
//   - title    (required) "MTBF — Mean Time Between Failures"
//   - standard            "ISO 14224:2016 §9.3"
//   - value    (required) the hero number (string or number)
//   - unit                "days" | "%" | "h" | ...
//   - sublabel            small line under the hero number
//   - color               'green'|'yellow'|'red'|'grey' — RAG state
//   - detail              HTML string for the expandable section (optional)
//   - legend              footer note shown inside expanded detail
//   - autoOpen            override default-open behavior (red auto-opens)
//   - tileId              optional caller-supplied id; else auto-generated
//
// capability: display_kpi_tile
let _whKpiTileId = 0;
function renderKpiTile(opts) {
  opts = opts || {};
  const COLORS = {
    green:  { bg: 'rgba(74,222,128,0.08)',   border: 'rgba(74,222,128,0.3)',   text: '#4ade80',  label: '✓ Healthy'  },
    yellow: { bg: 'rgba(247,162,27,0.08)',   border: 'rgba(247,162,27,0.3)',   text: '#F7A21B',  label: '⚠ Watch'    },
    red:    { bg: 'rgba(248,113,113,0.08)',  border: 'rgba(248,113,113,0.3)',  text: '#f87171',  label: '✗ Critical' },
    grey:   { bg: 'rgba(255,255,255,0.03)',  border: 'rgba(255,255,255,0.08)', text: 'rgba(255,255,255,0.4)', label: '— No data' },
  };
  const c   = COLORS[opts.color] || COLORS.grey;
  const id  = opts.tileId || `kpi-${_whKpiTileId++}`;
  const autoOpen = opts.autoOpen !== undefined ? opts.autoOpen : (opts.color === 'red');
  const detail = opts.detail || '';
  const legend = opts.legend || '';

  return `<div class="card" style="border-left:3px solid ${c.border};margin-bottom:1rem;">
    <button class="kpi-toggle" onclick="if(window.toggleKPI)toggleKPI('${id}')" style="min-height:${detail ? '72px' : '0'};">
      <div style="flex:1;text-align:left;">
        <div style="font-size:0.68rem;font-weight:700;color:rgba(255,255,255,0.3);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.25rem;">
          ${escHtml(opts.title || '')} <span style="font-size:0.58rem;font-weight:500;">${escHtml(opts.standard || '')}</span>
        </div>
        <div style="display:flex;align-items:baseline;gap:0.4rem;margin-bottom:0.15rem;">
          <span style="font-size:1.9rem;font-weight:800;line-height:1;color:${c.text};">${escHtml(String(opts.value === undefined ? '—' : opts.value))}</span>
          <span style="font-size:0.78rem;color:rgba(255,255,255,0.45);">${escHtml(opts.unit || '')}</span>
        </div>
        ${opts.sublabel ? `<div style="font-size:0.67rem;color:rgba(255,255,255,0.38);">${escHtml(opts.sublabel)}</div>` : ''}
      </div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:0.4rem;flex-shrink:0;margin-left:0.75rem;">
        <span style="font-size:0.63rem;font-weight:700;padding:0.2rem 0.55rem;border-radius:999px;background:${c.bg};border:1px solid ${c.border};color:${c.text};white-space:nowrap;">${c.label}</span>
        ${detail ? `<span class="kpi-chevron${autoOpen ? ' open' : ''}" id="${id}-chevron">▼</span>` : ''}
      </div>
    </button>
    ${detail ? `
      <div class="kpi-detail${autoOpen ? ' open' : ''}" id="${id}" style="border-top:1px solid rgba(255,255,255,0.06);">
        ${detail}
        ${legend ? `<p style="font-size:0.62rem;color:rgba(255,255,255,0.2);margin-top:0.5rem;">${escHtml(legend)}</p>` : ''}
      </div>` : ''}
  </div>`;
}

// Default toggle handler — pages that already define toggleKPI keep their own.
if (typeof window !== 'undefined' && !window.toggleKPI) {
  window.toggleKPI = function (id) {
    const detail  = document.getElementById(id);
    const chevron = document.getElementById(id + '-chevron');
    if (!detail) return;
    const isOpen = detail.classList.toggle('open');
    if (chevron) chevron.classList.toggle('open', isOpen);
  };
}


// ─── Compact Stat (Tier G capability: display_compact_stat) ────────────────
// Small inline label/value tile — the recurring "MTBF: 18d" pattern across
// asset-hub risk panel, hive benchmark rows, predictive count chips, shift
// brain top-of-shift stats. Distinct from renderKpiTile (which is the full
// RAG hero card); this is the compact variant for stat strips.
//
// opts:
//   - label    (required) "MTBF" | "Critical" | "Days to Failure"
//   - value    (required) hero number / text
//   - unit                "d" | "%" | "h" (optional, rendered small)
//   - color               'red'|'orange'|'yellow'|'green'|'blue'|'grey' OR a CSS color
//   - sublabel            small line under the value (optional)
//   - icon                emoji or single char prefix (optional)
//   - href                wrap whole tile in <a href> (optional)
//
// capability: display_compact_stat
function renderCompactStat(opts) {
  opts = opts || {};
  const PALETTE = {
    red:    '#f87171',
    orange: '#fb923c',
    yellow: '#facc15',
    green:  '#4ade80',
    blue:   '#60a5fa',
    grey:   'rgba(255,255,255,0.55)',
  };
  const color = PALETTE[opts.color] || opts.color || 'rgba(255,255,255,0.85)';

  const inner =
    `<div style="display:flex;flex-direction:column;align-items:flex-start;gap:0.15rem;padding:0.5rem 0.85rem;min-width:84px;">` +
      `<span style="font-size:0.6rem;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:rgba(255,255,255,0.6);">${escHtml(opts.label || '')}</span>` +
      `<span style="display:flex;align-items:baseline;gap:0.25rem;">` +
        (opts.icon ? `<span style="font-size:0.85rem;">${escHtml(opts.icon)}</span>` : '') +
        `<span style="font-size:1.05rem;font-weight:800;line-height:1;color:${color};">${escHtml(String(opts.value === undefined || opts.value === null ? '—' : opts.value))}</span>` +
        (opts.unit ? `<span style="font-size:0.7rem;color:rgba(255,255,255,0.45);">${escHtml(opts.unit)}</span>` : '') +
      `</span>` +
      (opts.sublabel ? `<span style="font-size:0.6rem;color:rgba(255,255,255,0.6);">${escHtml(opts.sublabel)}</span>` : '') +
    `</div>`;

  if (opts.href) {
    return `<a href="${escHtml(opts.href)}" style="text-decoration:none;color:inherit;">${inner}</a>`;
  }
  return inner;
}


// ─── Alert Preview (Tier G capability: display_alert_preview) ──────────────
// Shared alert-row renderer for cross-page previews of AMC briefings, failure
// signature matches, sensor anomalies, parts staging recommendations.
// Each preview links to alert-hub.html for the full filterable view.
//
// opts:
//   - kind:      'amc_briefing' | 'failure_signature' | 'sensor_anomaly' | 'parts_staging'
//   - title      e.g. "PMP-001 bearing failure pattern detected"
//   - severity   'critical' | 'high' | 'medium' | 'low'
//   - asset      asset_tag or machine name (optional)
//   - message    short body text (optional)
//   - created_at ISO timestamp (renders as relative time)
//   - href       link target (default: alert-hub.html)
//
// capability: display_alert_preview
function renderAlertPreview(opts) {
  opts = opts || {};
  const SEV = {
    critical: { bg: 'rgba(248,113,113,0.10)', border: '#f87171', label: '🔴 CRITICAL' },
    high:     { bg: 'rgba(247,162,27,0.10)',  border: '#F7A21B', label: '🟠 HIGH' },
    medium:   { bg: 'rgba(250,204,21,0.10)',  border: '#facc15', label: '🟡 MEDIUM' },
    low:      { bg: 'rgba(74,222,128,0.10)',  border: '#4ade80', label: '🟢 LOW' },
  };
  const s = SEV[opts.severity] || SEV.medium;
  const kindIcon = ({
    amc_briefing:      '☀️',
    failure_signature: '⚠',
    sensor_anomaly:    '📡',
    parts_staging:     '📦',
  })[opts.kind] || '🔔';

  let rel = '';
  if (opts.created_at) {
    try {
      const secs = (Date.now() - new Date(opts.created_at).getTime()) / 1000;
      if (secs < 60)        rel = 'just now';
      else if (secs < 3600) rel = `${Math.round(secs / 60)}m ago`;
      else if (secs < 86400) rel = `${Math.round(secs / 3600)}h ago`;
      else                  rel = `${Math.round(secs / 86400)}d ago`;
    } catch (_e) { rel = ''; }
  }

  const href = opts.href || 'alert-hub.html';
  return `<a href="${escHtml(href)}" class="alert-preview" style="display:block;padding:0.6rem 0.8rem;margin-bottom:0.4rem;background:${s.bg};border-left:3px solid ${s.border};border-radius:0.5rem;text-decoration:none;color:inherit;">
    <div style="display:flex;align-items:baseline;justify-content:space-between;gap:0.5rem;margin-bottom:0.15rem;">
      <span style="font-size:0.7rem;font-weight:700;letter-spacing:0.04em;">${kindIcon} ${escHtml(opts.title || 'Alert')}</span>
      <span style="font-size:0.6rem;color:rgba(255,255,255,0.6);white-space:nowrap;">${escHtml(s.label)}${rel ? ' · ' + escHtml(rel) : ''}</span>
    </div>
    ${opts.asset ? `<div style="font-size:0.62rem;color:rgba(255,255,255,0.5);">Asset: ${escHtml(opts.asset)}</div>` : ''}
    ${opts.message ? `<div style="font-size:0.65rem;color:rgba(255,255,255,0.55);margin-top:0.15rem;">${escHtml(opts.message)}</div>` : ''}
  </a>`;
}


// ─────────────────────────────────────────────
// fetchWithTimeout — bounded fetch wrapper (Phase 1.5 of STRATEGIC_ROADMAP)
// ─────────────────────────────────────────────
// Every cross-network call in WorkHive must have an upper bound. On a 2G/3G
// link in a Philippine plant, a missing timeout means a logbook entry,
// embed-entry POST, or assistant turn can hang for minutes while the user
// stares at a spinner and assumes the page is broken. AbortController gives us
// a hard ceiling and a recognisable AbortError caller code can branch on.
//
// Defaults: 30s timeout (matches Supabase Edge Functions cold-start budget).
// Callers can pass a smaller value for fire-and-forget telemetry (embed-entry
// is 8s — if the embed pipeline is overwhelmed we silently skip rather than
// block the user's save).
//
// Skills consulted: devops (network resilience), realtime-engineer (signal
// propagation), architect ("every fetch must be bounded").
//
// Usage:
//   const res = await fetchWithTimeout(url, { method: 'POST', body }, 20000);
//   if (res === null) { /* timed out — caller decides UX */ }
//   else if (!res.ok) { ... } else { const j = await res.json(); ... }
//
// Returns: a Response on success, or null on timeout/abort. Network errors
// (DNS failure, offline) still throw — caller wraps in try/catch as today.
async function fetchWithTimeout(url, options, timeoutMs) {
  const ms = (typeof timeoutMs === 'number' && timeoutMs > 0) ? timeoutMs : 30000;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    const opts = Object.assign({}, options || {}, { signal: ctrl.signal });
    return await fetch(url, opts);
  } catch (e) {
    if (e && (e.name === 'AbortError' || e.code === 20)) return null;
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

if (typeof window !== 'undefined') window.fetchWithTimeout = fetchWithTimeout;

// ─────────────────────────────────────────────
// whConfirm() / whPrompt() — styled async modals
// ─────────────────────────────────────────────
// Drop-in async replacements for native confirm() / prompt(). Both block
// the main thread, can't be styled, and on some mobile browsers are
// silently suppressed entirely. The platform toast/modal stack owns the
// UI shell; whConfirm/whPrompt are the gateway to it.
//
// Migration from native:
//   if (!confirm('Delete X?')) return;
//     -> if (!(await whConfirm('Delete X?'))) return;        // caller becomes async
//
//   const name = prompt('Enter name'); if (!name) return;
//     -> const name = await whPrompt('Enter name'); if (!name) return;
//
// Both return a Promise:
//   whConfirm: resolves true (OK) / false (Cancel or Esc / backdrop click)
//   whPrompt: resolves the entered string, or null if cancelled
//
// ── WH_STATUS_ENUMS — canonical per-table status enums (single source of truth) ──
// Grounded Sweep critique W3 (status-enum-constants). Hand-typed status string
// literals drift from the DB enum and silently miscount KPIs — the dayplanner
// "overdue" bug compared schedule_items.item_status against the literal 'closed',
// a value that does NOT exist in the enum (pending/in_progress/done/blocked/
// skipped), so DONE items were counted as overdue (live 6 vs DB 3). Reference THIS
// map instead of hand-typing status strings. validate_status_enum_drift.py asserts
// it can never silently diverge from the canonical capture contract in
// supabase/migrations (deterministic JS-constant-vs-DB comparison).
if (typeof window !== 'undefined' && !window.WH_STATUS_ENUMS) {
  window.WH_STATUS_ENUMS = {
    // schedule_items.item_status — capture_contracts_wave2 migration. 'done' is the
    // only terminal/closed state; everything else is OPEN (overdue if past due).
    schedule_item: ['pending', 'in_progress', 'done', 'blocked', 'skipped'],
  };
}

// ── whModalA11y — retrofit the dialog a11y bar onto a HAND-ROLLED modal ──────
// Grounded Sweep critique C7 / W2. whConfirm/whPrompt build their dialog in JS
// with the a11y bar already set; pages with static hand-rolled overlays (logbook,
// pm-scheduler, dayplanner, …) skip it. This helper adds the bar to an existing
// element WITHOUT touching its open/close call sites: it sets role=dialog +
// aria-modal + an accessible name, then a MutationObserver watches the element's
// class/style and — when it becomes visible — captures focus, traps Tab within
// the panel, and wires ESC; when it hides, it restores focus to the opener.
// Idempotent + opt-in. opts: { label?, labelledBy?, onClose? }.
//   whModalA11y(document.getElementById('my-modal'), { label: 'Edit asset', onClose: closeMyModal });
(function(){
  if (typeof window === 'undefined' || window.whModalA11y) return;

  var FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),' +
                  'select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

  window.whModalA11y = function whModalA11y(modalEl, opts) {
    if (!modalEl || modalEl.__whModalA11y) return null;   // null el or already wired
    opts = opts || {};
    modalEl.__whModalA11y = true;

    if (!modalEl.getAttribute('role'))       modalEl.setAttribute('role', 'dialog');
    if (!modalEl.hasAttribute('aria-modal')) modalEl.setAttribute('aria-modal', 'true');
    if (opts.labelledBy)                     modalEl.setAttribute('aria-labelledby', opts.labelledBy);
    else if (opts.label && !modalEl.getAttribute('aria-label')) modalEl.setAttribute('aria-label', opts.label);

    var lastFocus = null, keyBound = false;

    function isOpen() {
      if (modalEl.classList.contains('hidden')) return false;
      var cs = window.getComputedStyle(modalEl);
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
      // Opacity/pointer-events open pattern (skillmatrix .modal-overlay,
      // marketplace/community .sheet-overlay, founder-console .fb-drawer-backdrop):
      // the overlay STAYS display:flex and toggles a .open class that flips
      // opacity + pointer-events. When closed it is pointer-events:none — detect
      // that so we don't treat a fully-invisible overlay as permanently open and
      // trap focus on page load. pointer-events flips instantly with the class;
      // opacity is transitioned, so reading opacity would mis-fire mid-animation.
      if (cs.pointerEvents === 'none') return false;
      return true;
    }
    function focusables() {
      return Array.prototype.filter.call(modalEl.querySelectorAll(FOCUSABLE), function(el) {
        return el.offsetParent !== null || el.getClientRects().length > 0;
      });
    }
    function onKey(e) {
      if (e.key === 'Escape') {
        e.stopPropagation();
        if (typeof opts.onClose === 'function') { opts.onClose(); return; }
        // No explicit close fn: click the modal's OWN close control so the page's
        // real close logic runs (removes .open / adds .hidden / clears state) — no
        // sticky inline display:none that would break the next open. Fall back to
        // adding .hidden only if the modal has no close affordance.
        var closer = null;
        try { closer = modalEl.querySelector('[data-wh-close],[aria-label="Close" i],.modal-close,.sheet-close'); }
        catch (_) { /* empty-catch-allow: querySelector case-flag unsupported */ }
        if (closer) closer.click();
        else modalEl.classList.add('hidden');
      } else if (e.key === 'Tab') {
        var f = focusables();
        if (!f.length) return;
        var first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }
    function activate() {
      if (keyBound) return;
      keyBound = true;
      lastFocus = document.activeElement;
      document.addEventListener('keydown', onKey, true);
      // Respect a page that already autofocused something inside the modal
      // (e.g. dayplanner focuses #m-title) — only grab focus if it's outside.
      setTimeout(function() {
        if (!modalEl.contains(document.activeElement)) {
          var f = focusables();
          if (f.length) { try { f[0].focus(); } catch (_) { /* empty-catch-allow */ } }
        }
      }, 0);
    }
    function deactivate() {
      if (!keyBound) return;
      keyBound = false;
      try { document.removeEventListener('keydown', onKey, true); } catch (_) { /* empty-catch-allow */ }
      try { if (lastFocus && lastFocus.focus) lastFocus.focus(); } catch (_) { /* empty-catch-allow */ }
    }

    var obs = new MutationObserver(function() { isOpen() ? activate() : deactivate(); });
    obs.observe(modalEl, { attributes: true, attributeFilter: ['class', 'style'] });
    if (isOpen()) activate();   // already-open at wire time
    return { activate: activate, deactivate: deactivate };
  };
})();

// The modal mounts on document.body (so it works on any page without
// per-page setup), traps focus, and disposes on resolve. ARIA: role="dialog"
// + aria-labelledby + aria-modal so screen readers announce it.
(function(){
  if (typeof window === 'undefined' || window.whConfirm) return;

  function _mount(opts) {
    const {
      message,
      okLabel = 'OK',
      cancelLabel = 'Cancel',
      withInput = false,
      inputLabel = '',
      inputDefault = '',
      onResolve,
    } = opts;

    const ovId   = 'wh-modal-ov-' + Date.now() + '-' + Math.floor(Math.random()*1000);
    const titleId = ovId + '-title';
    const inputId = ovId + '-input';

    const overlay = document.createElement('div');
    overlay.id = ovId;
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', titleId);
    overlay.style.cssText =
      'position:fixed;inset:0;z-index:10001;background:rgba(0,0,0,0.6);' +
      'backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;' +
      'padding:16px;animation:wh-fade-in 0.12s ease-out;';

    overlay.innerHTML =
      '<div style="background:#162032;border:1px solid rgba(255,255,255,0.1);border-radius:14px;' +
        'padding:20px 22px;max-width:440px;width:100%;box-shadow:0 16px 48px rgba(0,0,0,0.5);">' +
        '<p id="' + escHtml(titleId) + '" style="font-size:0.95rem;font-weight:600;color:#F4F6FA;' +
          'margin:0 0 14px;line-height:1.45;">' + escHtml(message) + '</p>' +
        (withInput
          ? '<input id="' + escHtml(inputId) + '" type="text" ' +
            'aria-label="' + escHtml(inputLabel || message) + '" ' +
            'value="' + escHtml(inputDefault || '') + '" ' +
            'style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.12);' +
            'background:rgba(255,255,255,0.04);color:#F4F6FA;font-size:0.9rem;font-family:inherit;' +
            'margin-bottom:14px;min-height:44px;" />'
          : ''
        ) +
        '<div style="display:flex;gap:8px;justify-content:flex-end;">' +
          '<button type="button" data-wh-modal-cancel ' +
            'style="background:transparent;color:rgba(255,255,255,0.65);border:1px solid rgba(255,255,255,0.12);' +
            'border-radius:8px;padding:9px 16px;font-size:0.85rem;font-weight:600;cursor:pointer;' +
            'min-height:44px;font-family:inherit;">' + escHtml(cancelLabel) + '</button>' +
          '<button type="button" data-wh-modal-ok ' +
            'style="background:#F7A21B;color:#162032;border:none;border-radius:8px;padding:9px 16px;' +
            'font-size:0.85rem;font-weight:700;cursor:pointer;min-height:44px;font-family:inherit;">' +
            escHtml(okLabel) + '</button>' +
        '</div>' +
      '</div>';

    document.body.appendChild(overlay);

    const inputEl  = withInput ? overlay.querySelector('#' + CSS.escape(inputId)) : null;
    const cancelEl = overlay.querySelector('[data-wh-modal-cancel]');
    const okEl     = overlay.querySelector('[data-wh-modal-ok]');

    // Trap focus + autofocus the relevant control
    const focusTarget = inputEl || okEl;
    setTimeout(() => focusTarget && focusTarget.focus(), 0);

    function dispose(value) {
      try { document.removeEventListener('keydown', onKey, true); } catch (_) { /* empty-catch-allow: best-effort cleanup */ }
      try { overlay.remove(); } catch (_) { /* empty-catch-allow: best-effort cleanup */ }
      onResolve(value);
    }
    function onKey(e) {
      if (e.key === 'Escape') { e.stopPropagation(); dispose(withInput ? null : false); }
      else if (e.key === 'Enter' && (e.target === inputEl || e.target === okEl || !withInput)) {
        e.stopPropagation();
        dispose(withInput ? (inputEl.value || '') : true);
      }
    }
    document.addEventListener('keydown', onKey, true);

    cancelEl.addEventListener('click', () => dispose(withInput ? null : false));
    okEl.addEventListener('click',     () => dispose(withInput ? (inputEl.value || '') : true));
    overlay.addEventListener('click', (e) => { if (e.target === overlay) dispose(withInput ? null : false); });
  }

  window.whConfirm = function whConfirm(message, opts) {
    opts = opts || {};
    return new Promise((resolve) => {
      _mount({
        message,
        okLabel:     opts.okLabel || 'OK',
        cancelLabel: opts.cancelLabel || 'Cancel',
        withInput:   false,
        onResolve:   resolve,
      });
    });
  };

  window.whPrompt = function whPrompt(message, opts) {
    opts = opts || {};
    return new Promise((resolve) => {
      _mount({
        message,
        okLabel:      opts.okLabel || 'OK',
        cancelLabel:  opts.cancelLabel || 'Cancel',
        withInput:    true,
        inputLabel:   opts.inputLabel || '',
        inputDefault: opts.defaultValue || '',
        onResolve:    resolve,
      });
    });
  };

  // Inject the minimal fade-in keyframe (the same shell used elsewhere reuses
  // existing animations, but whConfirm is loaded on every page so it owns its
  // own animation to avoid a load-order dependency).
  try {
    if (!document.getElementById('wh-modal-anim-style')) {
      const s = document.createElement('style');
      s.id = 'wh-modal-anim-style';
      s.textContent = '@keyframes wh-fade-in{from{opacity:0;}to{opacity:1;}}';
      document.head.appendChild(s);
    }
  } catch (_) { /* empty-catch-allow: best-effort style inject; modal still works without anim */ }
})();

// ─────────────────────────────────────────────
// trimChatToTokenBudget — context-window compressor (Phase 1.8 of STRATEGIC_ROADMAP)
// ─────────────────────────────────────────────
// floating-ai and assistant.html both stuff a long system prompt (2k-2.7k
// tokens) into every turn, then append the conversation history. On the Groq
// 8K-32K free-tier models this leaves a thin budget for the actual user
// message. Without a compressor, a long voice transcription mid-thread can
// silently overflow the model context and either error out or truncate the
// system prompt (which is the LAST thing you want trimmed).
//
// Strategy: keep the most-recent turns and drop the oldest user/assistant
// pairs first. The system prompt is the caller's responsibility — pass its
// estimated token cost in `systemTokens` so the budget math is honest. We
// never drop the most recent user message (that's the turn being asked).
//
// Token heuristic: 1 token ≈ 4 chars (English). Identical to the heuristic
// used by _shared/cost-log.ts so observability and runtime agree.
//
// Args:
//   messages       array of {role, content} — your sessionMessages so far
//   opts.budget    total budget in tokens for the model context (default 7000
//                  to match Groq llama-3.3-70b-versatile minus a safety pad)
//   opts.systemTokens cost of the system prompt you'll prepend at send time
//   opts.reserveOut tokens reserved for the model's response (default 800)
//
// Returns: a NEW array (does not mutate input) trimmed to fit.
//
// Skills consulted: ai-engineer (context budget = system + history + output),
// performance (cheap O(n) walk, no expensive tokenizer).
function trimChatToTokenBudget(messages, opts) {
  opts = opts || {};
  const budget       = typeof opts.budget       === 'number' ? opts.budget       : 7000;
  const systemTokens = typeof opts.systemTokens === 'number' ? opts.systemTokens : 0;
  const reserveOut   = typeof opts.reserveOut   === 'number' ? opts.reserveOut   : 800;
  const limit = Math.max(200, budget - systemTokens - reserveOut);

  const list = Array.isArray(messages) ? messages.slice() : [];
  if (list.length <= 1) return list;

  const cost = (m) => Math.round(String(m && m.content || '').length / 4);

  // Walk from the end, keeping recent turns; drop the oldest once over budget.
  let total = 0;
  const kept = [];
  for (let i = list.length - 1; i >= 0; i--) {
    const c = cost(list[i]);
    if (total + c > limit && kept.length > 0) break;
    kept.unshift(list[i]);
    total += c;
  }
  return kept;
}

if (typeof window !== 'undefined') window.trimChatToTokenBudget = trimChatToTokenBudget;

// Debounce — delay fn execution until after `wait` ms of silence
function debounce(fn, wait) {
  let t;
  return function (...args) {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), wait);
  };
}

/* C4: Session restore — returns worker display_name from localStorage or auth session.
 * Call at the top of each page's async init before redirecting to signin.
 *
 *   const wn = await restoreIdentityFromSession(db);
 *   if (!wn) { location.assign('index.html?signin=1'); return; }
 *
 * (Block comment + `location.assign(...)` so the L2 admin_gate_not_commented
 * sentinel doesn't false-positive on the example line.)
 */
async function restoreIdentityFromSession(db) {
  const cached = localStorage.getItem('wh_last_worker')
               || /* storage-key-allow: legacy worker-name fallback (current writes use wh_last_worker) */ localStorage.getItem('wh_worker_name')
               || localStorage.getItem('workerName') || '';
  if (cached) return cached;
  try {
    const { data: { session } } = await db.auth.getSession();
    if (!session) return '';
    const { data: profile } = await db.from('v_worker_truth')
      .select('worker_name').eq('auth_uid', session.user.id).maybeSingle();
    if (profile?.worker_name) {
      localStorage.setItem('wh_last_worker', profile.worker_name);
      return profile.worker_name;
    }
  } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
  return '';
}

// ─────────────────────────────────────────────
// Founder Console — analytics event SDK (Phase 0)
// ─────────────────────────────────────────────
// Every page should call logPageView(db) once after identity restore. Feature
// pages also emit feature-level events via logEvent(db, name, props).
//
// Writes are fire-and-forget — never block the user action. Append-only:
// the analytics_events table has no UPDATE/DELETE policies. SELECT is
// restricted to platform admins (marketplace_platform_admins allowlist).
//
// Skill alignment: analytics-engineer (KPI source events), architect
// ("Audit Log Writes Must Be Fire-and-Forget"), security (no PII in props).
let _wh_session_id = null;
function _whSessionId() {
  if (_wh_session_id) return _wh_session_id;
  try {
    let s = sessionStorage.getItem('wh_session_id');
    if (!s) {
      s = (window.crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2);
      sessionStorage.setItem('wh_session_id', s);
    }
    _wh_session_id = s;
    return s;
  } catch (_) { return null; }
}

function logEvent(db, eventName, props) {
  if (!db || !eventName) return;
  try {
    const workerName = localStorage.getItem('wh_last_worker')
                    || /* storage-key-allow: legacy worker-name fallback (current writes use wh_last_worker) */ localStorage.getItem('wh_worker_name')
                    || localStorage.getItem('workerName') || null;
    const hiveId = localStorage.getItem('wh_active_hive_id')
                || localStorage.getItem('wh_hive_id') || null;
    const payload = {
      event_name: eventName,
      props: props || {},
      page: (props && props.page) || null,
      worker_name: workerName,
      hive_id: hiveId,
      session_id: _whSessionId(),
      user_agent: (navigator.userAgent || '').slice(0, 200),
    };
    // Try to attach auth_uid if a session exists - non-blocking.
    const insert = function () {
      db.from('analytics_events').insert(payload).then(function (r) {
        if (r && r.error) console.warn('logEvent:', r.error.message);
      });
    };
    db.auth.getSession().then(function (res) {
      if (res && res.data && res.data.session) {
        payload.auth_uid = res.data.session.user.id;
      }
      insert();
    }).catch(insert);
  } catch (e) {
    console.warn('logEvent err:', e && e.message);
  }
}

// Convenience for the most common event - infers page name from URL.
function logPageView(db, extraProps) {
  const path = (location.pathname.split('/').pop() || 'index.html')
    .replace(/\.html$/i, '') || 'index';
  logEvent(db, 'page_view', Object.assign({ page: path }, extraProps || {}));
}

// ─────────────────────────────────────────────
// isPlatformAdmin — gate util for founder-console.html (Phase 0)
// ─────────────────────────────────────────────
// Reuses marketplace_platform_admins so admin grants are a single source of
// truth. Returns false on no session, no profile, or worker not on allowlist.
async function isPlatformAdmin(db) {
  if (!db) return false;
  try {
    const { data: { session } } = await db.auth.getSession();
    if (!session) return false;
    const { data: profile } = await db.from('v_worker_truth')
      .select('worker_name').eq('auth_uid', session.user.id).maybeSingle();
    if (!profile || !profile.worker_name) return false;
    const { data: admin } = await db.from('marketplace_platform_admins')
      .select('worker_name').eq('worker_name', profile.worker_name).maybeSingle();
    return !!admin;
  } catch (_) { return false; }
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
      .from('v_worker_achievements_truth')
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
