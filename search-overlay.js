/**
 * WorkHive Global Search Overlay
 * ─────────────────────────────────────────────────────────────────────────────
 * Cmd+K / Ctrl+K command palette that searches across hive-scoped data:
 *   - Assets   (asset_nodes by tag, name, location)
 *   - Jobs     (logbook by machine, problem, action)
 *   - Parts    (inventory_items by part_name, part_number)
 *   - PMs      (pm_assets by asset_name)
 *
 * Results group by type, click jumps to the source page.
 *
 * Public API:
 *   WHSearch.open()   — show the overlay (programmatic trigger)
 *   WHSearch.close()  — hide it
 *
 * Skills consulted: data-engineer (narrow selects, .limit(), .or() with escaped
 * input), security (ilike escaping, escHtml on display), mobile-maestro (44px
 * targets, viewport-fit safe areas, 16px input font, :active feedback),
 * frontend (?. on getElementById, debounce, keyboard nav), architect (single
 * shared module, lazy queries, hive scoping).
 */

(function () {
  'use strict';

  const SUPABASE_URL = 'https://hzyvnjtisfgbksicrouu.supabase.co';
  const SUPABASE_KEY = 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
  let _db = null;
  function _getDb() {
    if (!_db && window.supabase) {
      _db = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY);
    }
    return _db;
  }

  let _overlay = null;
  let _isOpen  = false;
  let _searchInput = null;
  let _resultsEl = null;
  let _emptyEl   = null;
  let _statusEl  = null;
  let _debounceTimer = null;
  let _activeIndex = -1;
  let _flatResults = [];

  // ── Public API ────────────────────────────────────────────────────────────
  window.WHSearch = {
    open: openOverlay,
    close: closeOverlay,
  };

  // ── Global keyboard shortcut: Ctrl+K / Cmd+K ──────────────────────────────
  // Registered ONCE at module load (this script loads via nav-hub.js on every page).
  document.addEventListener('keydown', function (ev) {
    if ((ev.ctrlKey || ev.metaKey) && (ev.key === 'k' || ev.key === 'K')) {
      ev.preventDefault();
      if (_isOpen) closeOverlay();
      else openOverlay();
    } else if (_isOpen && ev.key === 'Escape') {
      closeOverlay();
    } else if (_isOpen && ev.key === 'ArrowDown') {
      ev.preventDefault();
      _moveSelection(1);
    } else if (_isOpen && ev.key === 'ArrowUp') {
      ev.preventDefault();
      _moveSelection(-1);
    } else if (_isOpen && ev.key === 'Enter') {
      ev.preventDefault();
      _activateSelected();
    }
  });

  function openOverlay() {
    if (_isOpen) return;
    _isOpen = true;
    if (!_overlay) buildOverlay();
    document.body.appendChild(_overlay);
    document.body.style.overflow = 'hidden';
    setTimeout(() => _searchInput && _searchInput.focus(), 30);
    _renderEmptyHint();
  }

  function closeOverlay() {
    if (!_isOpen) return;
    _isOpen = false;
    clearTimeout(_debounceTimer);
    if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay);
    _overlay = null; _searchInput = null; _resultsEl = null; _emptyEl = null; _statusEl = null;
    _activeIndex = -1; _flatResults = [];
    document.body.style.overflow = '';
  }

  // ── Overlay DOM ───────────────────────────────────────────────────────────
  function buildOverlay() {
    _overlay = document.createElement('div');
    _overlay.id = 'wh-search-overlay';
    _overlay.setAttribute('role', 'dialog');
    _overlay.setAttribute('aria-modal', 'true');
    _overlay.setAttribute('aria-label', 'Global search');
    _overlay.innerHTML = `
      <style>
        #wh-search-overlay {
          position: fixed; inset: 0; z-index: 9999;
          background: rgba(8,14,22,0.85);
          backdrop-filter: blur(4px);
          display: flex; flex-direction: column;
          padding-top: max(80px, env(safe-area-inset-top, 0px));
          padding-bottom: env(safe-area-inset-bottom, 0px);
          font-family: 'Poppins', system-ui, -apple-system, sans-serif;
          color: #F4F6FA;
        }
        #wh-search-overlay .ws-shell {
          width: 100%; max-width: 640px; margin: 0 auto;
          background: rgba(22,32,50,0.96);
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 14px;
          display: flex; flex-direction: column;
          max-height: calc(100vh - 100px - env(safe-area-inset-bottom, 0px));
          overflow: hidden;
        }
        #wh-search-overlay .ws-input-row {
          display: flex; align-items: center; gap: 10px;
          padding: 14px 16px;
          border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        #wh-search-overlay .ws-input-row svg {
          color: rgba(255,255,255,0.45); flex-shrink: 0;
        }
        #wh-search-overlay input {
          flex: 1; min-width: 0;
          background: transparent; border: none; outline: none;
          color: #F4F6FA; font-family: inherit; font-size: 16px; font-weight: 500;
        }
        #wh-search-overlay input::placeholder { color: rgba(255,255,255,0.35); }
        #wh-search-overlay .ws-kbd-hint {
          display: inline-flex; gap: 4px; align-items: center;
          font-size: 10px; font-weight: 700; color: rgba(255,255,255,0.4);
        }
        #wh-search-overlay .ws-kbd {
          padding: 2px 6px; min-width: 22px; text-align: center;
          background: rgba(255,255,255,0.06);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 4px; font-size: 10px;
        }
        #wh-search-overlay .ws-status {
          padding: 8px 16px; font-size: 11px; color: rgba(255,255,255,0.4);
          border-bottom: 1px solid rgba(255,255,255,0.04);
          min-height: 1.2em;
        }
        #wh-search-overlay .ws-results {
          overflow-y: auto; flex: 1; padding: 6px 0;
        }
        #wh-search-overlay .ws-section {
          font-size: 10px; font-weight: 700; letter-spacing: 0.08em;
          text-transform: uppercase; color: rgba(255,255,255,0.3);
          padding: 10px 16px 4px;
        }
        #wh-search-overlay .ws-row {
          display: flex; align-items: center; justify-content: space-between;
          gap: 10px; padding: 10px 16px;
          cursor: pointer; text-decoration: none;
          color: inherit;
          transition: background 0.1s;
          min-height: 44px;
        }
        #wh-search-overlay .ws-row:hover,
        #wh-search-overlay .ws-row.active {
          background: rgba(247,162,27,0.1);
        }
        #wh-search-overlay .ws-row:active { background: rgba(247,162,27,0.18); }
        #wh-search-overlay .ws-row-main {
          display: flex; align-items: center; gap: 10px; min-width: 0; flex: 1;
        }
        #wh-search-overlay .ws-row-icon {
          width: 28px; height: 28px; flex-shrink: 0;
          display: flex; align-items: center; justify-content: center;
          background: rgba(255,255,255,0.04); border-radius: 6px;
          font-size: 13px;
        }
        #wh-search-overlay .ws-row-text { min-width: 0; flex: 1; }
        #wh-search-overlay .ws-row-title {
          font-size: 13.5px; font-weight: 600; color: #F4F6FA;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        #wh-search-overlay .ws-row-meta {
          font-size: 11px; color: rgba(255,255,255,0.4); margin-top: 1px;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        #wh-search-overlay .ws-row-arrow {
          flex-shrink: 0; color: rgba(255,255,255,0.3); font-size: 14px;
        }
        #wh-search-overlay .ws-empty {
          padding: 28px 20px; text-align: center;
          color: rgba(255,255,255,0.4); font-size: 13px;
        }
        #wh-search-overlay .ws-footer {
          display: flex; gap: 16px; padding: 8px 16px;
          border-top: 1px solid rgba(255,255,255,0.06);
          font-size: 10px; color: rgba(255,255,255,0.4);
        }
        #wh-search-overlay .ws-footer .ws-kbd { font-size: 10px; padding: 1px 5px; }
        @media (max-width: 480px) {
          #wh-search-overlay { padding: 8px; padding-top: env(safe-area-inset-top, 8px); }
          #wh-search-overlay .ws-shell { max-height: calc(100vh - 16px - env(safe-area-inset-bottom, 0px)); }
          #wh-search-overlay .ws-kbd-hint { display: none; }
        }
      </style>
      <div class="ws-shell">
        <div class="ws-input-row">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input id="ws-input" type="search" placeholder="Search assets, jobs, parts, PMs..." autocomplete="off" spellcheck="false" />
          <span class="ws-kbd-hint"><span class="ws-kbd">esc</span></span>
        </div>
        <div id="ws-status" class="ws-status"></div>
        <div id="ws-results" class="ws-results"></div>
        <div id="ws-empty" class="ws-empty" style="display:none;"></div>
        <div class="ws-footer">
          <span><span class="ws-kbd">↑</span><span class="ws-kbd">↓</span> Navigate</span>
          <span><span class="ws-kbd">↵</span> Open</span>
          <span><span class="ws-kbd">esc</span> Close</span>
        </div>
      </div>
    `;
    _searchInput = _overlay.querySelector('#ws-input');
    _resultsEl   = _overlay.querySelector('#ws-results');
    _emptyEl     = _overlay.querySelector('#ws-empty');
    _statusEl    = _overlay.querySelector('#ws-status');

    // Click outside the shell closes
    _overlay.addEventListener('click', function (ev) {
      if (ev.target === _overlay) closeOverlay();
    });

    _searchInput.addEventListener('input', function () {
      const q = (this.value || '').trim();
      clearTimeout(_debounceTimer);
      if (q.length < 2) { _renderEmptyHint(); return; }
      _statusEl.textContent = 'Searching...';
      _debounceTimer = setTimeout(() => runSearch(q), 220);
    });
  }

  // ── Search execution ──────────────────────────────────────────────────────
  async function runSearch(query) {
    const HIVE_ID = localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id') || '';
    const WORKER  = localStorage.getItem('wh_last_worker') || '';
    const db      = _getDb();
    if (!db) {
      _statusEl.textContent = 'Search unavailable (Supabase not loaded on this page).';
      return;
    }

    // Escape ilike wildcards (security skill rule)
    const safe = String(query).replace(/%/g, '\\%').replace(/_/g, '\\_').slice(0, 100);

    const scopeFilter = HIVE_ID ? { col: 'hive_id', val: HIVE_ID }
                                 : { col: 'worker_name', val: WORKER };

    const [assetsRes, jobsRes, partsRes, pmsRes] = await Promise.allSettled([
      db.from('asset_nodes')
        .select('id, tag, name, level, location, criticality')
        .eq('hive_id', HIVE_ID)
        .or(`tag.ilike.%${safe}%,name.ilike.%${safe}%,location.ilike.%${safe}%`)
        .limit(8),
      db.from('v_logbook_truth')   // canonical: logbook_truth
        .select('id, machine, problem, status, maintenance_type, created_at')
        .eq(scopeFilter.col, scopeFilter.val)
        .or(`machine.ilike.%${safe}%,problem.ilike.%${safe}%,action.ilike.%${safe}%`)
        .order('created_at', { ascending: false })
        .limit(8),
      // Canonical: inventory_items_truth — exposes reorder_point as alias
      // for min_qty (the underlying table has no reorder_point column, so
      // the pre-fix select returned null silently for that field).
      db.from('v_inventory_items_truth')
        .select('id, part_name, part_number, qty_on_hand, reorder_point')
        .eq(scopeFilter.col, scopeFilter.val)
        .or(`part_name.ilike.%${safe}%,part_number.ilike.%${safe}%`)
        .limit(8),
      db.from('pm_assets')
        .select('id, asset_name, category, criticality')
        .eq(scopeFilter.col, scopeFilter.val)
        .ilike('asset_name', `%${safe}%`)
        .limit(8),
    ]);

    const assets = assetsRes.status === 'fulfilled' ? (assetsRes.value.data || []) : [];
    const jobs   = jobsRes.status   === 'fulfilled' ? (jobsRes.value.data   || []) : [];
    const parts  = partsRes.status  === 'fulfilled' ? (partsRes.value.data  || []) : [];
    const pms    = pmsRes.status    === 'fulfilled' ? (pmsRes.value.data    || []) : [];

    renderResults({ assets, jobs, parts, pms });
  }

  function renderResults(r) {
    const e = (s) => String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

    _flatResults = [];
    let html = '';

    if (r.assets.length) {
      html += `<p class="ws-section">Assets · ${r.assets.length}</p>`;
      for (const a of r.assets) {
        const idx = _flatResults.length;
        _flatResults.push({ kind: 'asset', href: `asset-hub.html?node_id=${encodeURIComponent(a.id)}` });
        const meta = [a.tag, a.location, a.level].filter(Boolean).join(' · ');
        html += `<a class="ws-row" href="asset-hub.html?node_id=${e(a.id)}" data-idx="${idx}">
          <div class="ws-row-main">
            <div class="ws-row-icon">⚙️</div>
            <div class="ws-row-text">
              <div class="ws-row-title">${e(a.name || a.tag || 'Unnamed asset')}</div>
              <div class="ws-row-meta">${e(meta)}</div>
            </div>
          </div>
          <span class="ws-row-arrow">→</span>
        </a>`;
      }
    }
    if (r.jobs.length) {
      html += `<p class="ws-section">Jobs · ${r.jobs.length}</p>`;
      for (const j of r.jobs) {
        const idx = _flatResults.length;
        _flatResults.push({ kind: 'job', href: `logbook.html?id=${encodeURIComponent(j.id)}` });
        const meta = [j.status, j.maintenance_type, _ago(j.created_at)].filter(Boolean).join(' · ');
        html += `<a class="ws-row" href="logbook.html?id=${e(j.id)}" data-idx="${idx}">
          <div class="ws-row-main">
            <div class="ws-row-icon">📋</div>
            <div class="ws-row-text">
              <div class="ws-row-title">${e((j.machine || 'Unknown machine') + ': ' + (j.problem || '').slice(0, 60))}</div>
              <div class="ws-row-meta">${e(meta)}</div>
            </div>
          </div>
          <span class="ws-row-arrow">→</span>
        </a>`;
      }
    }
    if (r.parts.length) {
      html += `<p class="ws-section">Parts · ${r.parts.length}</p>`;
      for (const p of r.parts) {
        const idx = _flatResults.length;
        _flatResults.push({ kind: 'part', href: 'inventory.html?q=' + encodeURIComponent(p.part_number || p.part_name || '') });
        const meta = `${p.part_number || ''}${p.qty_on_hand != null ? ' · ' + p.qty_on_hand + ' on hand' : ''}`;
        html += `<a class="ws-row" href="inventory.html?q=${encodeURIComponent(p.part_number || p.part_name || '')}" data-idx="${idx}">
          <div class="ws-row-main">
            <div class="ws-row-icon">📦</div>
            <div class="ws-row-text">
              <div class="ws-row-title">${e(p.part_name || 'Unnamed part')}</div>
              <div class="ws-row-meta">${e(meta)}</div>
            </div>
          </div>
          <span class="ws-row-arrow">→</span>
        </a>`;
      }
    }
    if (r.pms.length) {
      html += `<p class="ws-section">PM Tasks · ${r.pms.length}</p>`;
      for (const p of r.pms) {
        const idx = _flatResults.length;
        _flatResults.push({ kind: 'pm', href: 'pm-scheduler.html' });
        const meta = [p.category, p.criticality].filter(Boolean).join(' · ');
        html += `<a class="ws-row" href="pm-scheduler.html" data-idx="${idx}">
          <div class="ws-row-main">
            <div class="ws-row-icon">🛠️</div>
            <div class="ws-row-text">
              <div class="ws-row-title">${e(p.asset_name || 'Unnamed asset')}</div>
              <div class="ws-row-meta">${e(meta)}</div>
            </div>
          </div>
          <span class="ws-row-arrow">→</span>
        </a>`;
      }
    }

    if (!_flatResults.length) {
      _resultsEl.innerHTML = '';
      _emptyEl.style.display = 'block';
      _emptyEl.textContent = 'No matches. Try a shorter or different query.';
      _statusEl.textContent = '';
      return;
    }

    _emptyEl.style.display = 'none';
    _resultsEl.innerHTML = html;
    _statusEl.textContent = `${_flatResults.length} result${_flatResults.length === 1 ? '' : 's'}`;
    _activeIndex = 0;
    _highlightActive();

    // Mouse hover updates active index for visual consistency with keyboard
    _resultsEl.querySelectorAll('.ws-row').forEach(function (row) {
      row.addEventListener('mouseenter', function () {
        _activeIndex = Number(row.getAttribute('data-idx'));
        _highlightActive();
      });
    });
  }

  function _renderEmptyHint() {
    if (!_resultsEl || !_emptyEl) return;
    _resultsEl.innerHTML = '';
    _emptyEl.style.display = 'block';
    _emptyEl.textContent = 'Type at least 2 characters to search across assets, jobs, parts, and PMs.';
    if (_statusEl) _statusEl.textContent = 'Tip: results are scoped to your current hive.';
    _flatResults = [];
    _activeIndex = -1;
  }

  function _moveSelection(delta) {
    if (!_flatResults.length) return;
    _activeIndex = (_activeIndex + delta + _flatResults.length) % _flatResults.length;
    _highlightActive();
    const row = _resultsEl.querySelector(`.ws-row[data-idx="${_activeIndex}"]`);
    if (row) row.scrollIntoView({ block: 'nearest' });
  }

  function _activateSelected() {
    const r = _flatResults[_activeIndex];
    if (!r) return;
    window.location.href = r.href;
  }

  function _highlightActive() {
    if (!_resultsEl) return;
    _resultsEl.querySelectorAll('.ws-row').forEach(function (row) {
      const i = Number(row.getAttribute('data-idx'));
      row.classList.toggle('active', i === _activeIndex);
    });
  }

  function _ago(iso) {
    if (!iso) return '';
    const d = (Date.now() - new Date(iso).getTime()) / 1000;
    if (d < 60)    return 'just now';
    if (d < 3600)  return Math.floor(d / 60) + 'm ago';
    if (d < 86400) return Math.floor(d / 3600) + 'h ago';
    return Math.floor(d / 86400) + 'd ago';
  }

})();
