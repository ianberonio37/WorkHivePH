/* provenance-hover.js — Phase E2 (INTERACTIVE_LINEAGE_ROADMAP).
 *
 * The "where did this come from?" affordance. Self-installing: include the
 * <script> on any page and it fetches display_provenance.json (built from
 * Phase B's resolved anchor chains), finds the resolved KPI element-ids that
 * exist on THIS page, and appends a small "ⓘ" button next to each. Tapping it
 * reveals the canonical provenance — source formula -> inputs -> standard ->
 * unit -> the view it reads — so every grounded number can answer "where did
 * this come from?" (Nielsen #1 visibility-of-status; W3C PROV-O). This makes the
 * analytics 4-phase engine the literal grounding spine for displays everywhere,
 * not just analytics.html.
 *
 * Reuse-first: pure data-driven, zero per-page wiring. A page gets the affordance
 * the moment it has resolved anchors in display_provenance.json — no code edits.
 * Degrades silently if the artifact is missing or the page has no resolved anchors.
 */
(function () {
  'use strict';
  if (window.__whProvenanceInstalled) return;
  window.__whProvenanceInstalled = true;

  var esc = (window.escHtml && typeof window.escHtml === 'function')
    ? window.escHtml
    : function (s) {
        return String(s == null ? '' : s)
          .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
      };

  var RUNG_COLOR = {
    descriptive:  '#9CA3AF',
    diagnostic:   '#F7A21B',
    predictive:   '#29B6D9',
    prescriptive: '#34D399',
  };

  function pageFile() {
    var p = (location.pathname || '').split('/').filter(Boolean).pop() || 'index.html';
    return p.indexOf('.') === -1 ? p + '.html' : p;
  }

  var _openPopover = null;
  function closePopover() {
    if (_openPopover) { _openPopover.remove(); _openPopover = null; }
    document.removeEventListener('keydown', onKey, true);
    document.removeEventListener('click', onDocClick, true);
  }
  function onKey(e) { if (e.key === 'Escape') closePopover(); }
  function onDocClick(e) {
    if (_openPopover && !_openPopover.contains(e.target) && !e.target.classList.contains('wh-prov-btn')) {
      closePopover();
    }
  }

  function openPopover(btn, entry) {
    closePopover();
    var pop = document.createElement('div');
    pop.className = 'wh-prov-pop';
    pop.setAttribute('role', 'dialog');
    pop.setAttribute('aria-label', 'Data provenance');
    var color = RUNG_COLOR[entry.rung] || RUNG_COLOR.descriptive;
    var rows = (entry.lines || []).map(function (ln) {
      var idx = ln.indexOf(':');
      var k = idx > -1 ? ln.slice(0, idx) : '';
      var v = idx > -1 ? ln.slice(idx + 1).trim() : ln;
      return '<div style="margin:2px 0;line-height:1.4;">'
        + (k ? '<span style="color:rgba(255,255,255,0.5);">' + esc(k) + ':</span> ' : '')
        + '<span style="color:rgba(255,255,255,0.92);">' + esc(v) + '</span></div>';
    }).join('');
    pop.innerHTML =
      '<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">'
      + '<span style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:0.05em;'
      + 'padding:2px 6px;border-radius:6px;background:' + color + '22;color:' + color + ';border:1px solid ' + color + '55;">'
      + esc(entry.rung_label || 'Current measure') + '</span>'
      + '<span style="font-size:10px;font-weight:700;color:rgba(255,255,255,0.55);">Where did this come from?</span>'
      + '</div>'
      + '<div style="font-size:11px;">' + rows + '</div>';
    pop.style.cssText =
      'position:absolute;z-index:9999;max-width:300px;min-width:200px;'
      + 'background:#10151c;border:1px solid rgba(255,255,255,0.14);border-radius:10px;'
      + 'padding:10px 12px;box-shadow:0 8px 28px rgba(0,0,0,0.45);'
      + 'font-family:inherit;';
    document.body.appendChild(pop);

    var r = btn.getBoundingClientRect();
    var top = r.bottom + window.scrollY + 6;
    var left = r.left + window.scrollX;
    // keep it on-screen
    var pw = pop.offsetWidth;
    if (left + pw > window.scrollX + document.documentElement.clientWidth - 8) {
      left = window.scrollX + document.documentElement.clientWidth - pw - 8;
    }
    pop.style.top = top + 'px';
    pop.style.left = Math.max(8, left) + 'px';

    _openPopover = pop;
    btn.setAttribute('aria-expanded', 'true');
    setTimeout(function () {
      document.addEventListener('keydown', onKey, true);
      document.addEventListener('click', onDocClick, true);
    }, 0);
  }

  function makeBtn(entry) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'wh-prov-btn';
    btn.setAttribute('aria-label', 'Where did this come from? Show data source.');
    btn.setAttribute('aria-expanded', 'false');
    btn.textContent = 'ⓘ';
    var color = RUNG_COLOR[entry.rung] || RUNG_COLOR.descriptive;
    // 44px hit area via padding while keeping the glyph compact (mobile-maestro).
    btn.style.cssText =
      'display:inline-flex;align-items:center;justify-content:center;'
      + 'min-width:24px;min-height:24px;padding:10px;margin:-10px 0 -10px 2px;'
      + 'background:transparent;border:none;cursor:pointer;'
      + 'font-size:12px;line-height:1;color:' + color + ';opacity:0.7;vertical-align:middle;';
    btn.addEventListener('mouseenter', function () { btn.style.opacity = '1'; });
    btn.addEventListener('mouseleave', function () { btn.style.opacity = '0.7'; });
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      if (_openPopover && btn.getAttribute('aria-expanded') === 'true') { closePopover(); btn.setAttribute('aria-expanded', 'false'); }
      else openPopover(btn, entry);
    });
    return btn;
  }

  function attach(map) {
    var ids = Object.keys(map);
    var attached = 0;
    ids.forEach(function (id) {
      var el = document.getElementById(id);
      if (!el || el.dataset.whProv) return;
      el.dataset.whProv = '1';
      var btn = makeBtn(map[id]);
      // place the marker right after the value element (footnote style)
      if (el.parentNode) { el.insertAdjacentElement('afterend', btn); attached++; }
    });
    window.__whProvenanceCount = attached;
    return attached;
  }

  function boot() {
    fetch('display_provenance.json', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.pages) return;
        var map = data.pages[pageFile()];
        if (!map) return;
        // retry once after a tick — many KPI elements render async after data load
        var n = attach(map);
        if (n < Object.keys(map).length) {
          setTimeout(function () { attach(map); }, 1500);
        }
      })
      .catch(function () { /* empty-catch-allow: progressive enhancement — the "where from?" hover is optional, a fetch failure must not break the page */ });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
