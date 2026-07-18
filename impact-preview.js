/* impact-preview.js — Phase D2 (INTERACTIVE_LINEAGE_ROADMAP).
 *
 * The PRE-COMMIT "this will update N pages" hint (Nielsen #5 error-prevention +
 * Norman's Gulf of Execution). Self-installing: include the <script> on a
 * high-blast WRITE surface and it fetches field_impact_preview.json (built from
 * Phase A blast radius), and if the page is a high-blast surface, inserts a
 * subtle NON-BLOCKING line just above the primary save button naming the ripple
 * the save will cause. Tap it to see the full page list + recompute chain.
 *
 * Non-blocking by design (no interstitial / no extra click to save) — it informs,
 * it doesn't gate. Config-anchored (SURFACE_ANCHORS) so it attaches to the right
 * button without fragile heuristics. Degrades silently if the artifact, the
 * surface entry, or the anchor button is absent.
 */
(function () {
  'use strict';
  if (window.__whImpactInstalled) return;
  window.__whImpactInstalled = true;

  // surface (page file, no .html) -> CSS selector of its primary save/submit button
  var SURFACE_ANCHORS = {
    'logbook':      '#save-entry-btn',    // <form id="log-form"> Save Entry (always visible)
    'inventory':    '#part-submit-btn',   // add-part modal — Save Part
    'pm-scheduler': '#sheet-save-btn',    // completion sheet — Save Completion
    'marketplace':  '#btn-submit-post',   // new-listing form — Post Listing
  };

  var esc = (window.escHtml && typeof window.escHtml === 'function')
    ? window.escHtml
    : function (s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); };

  function surfaceKey() {
    var p = (location.pathname || '').split('/').filter(Boolean).pop() || 'index.html';
    return p.replace(/\.html$/, '');
  }

  var _pop = null;
  function closePop() { if (_pop) { _pop.remove(); _pop = null; } document.removeEventListener('keydown', onKey, true); }
  function onKey(e) { if (e.key === 'Escape') closePop(); }

  // Turn a page slug ("pm-scheduler") into a readable name ("PM Scheduler") so the
  // popover never shows raw slugs. Known acronyms stay upper-case.
  var ACR = { pm: 'PM', ph: 'PH', ai: 'AI', amc: 'AMC', rfq: 'RFQ', cmms: 'CMMS', oee: 'OEE' };
  function prettyPage(slug) {
    return String(slug || '').split('-').map(function (w) {
      return ACR[w] || (w.charAt(0).toUpperCase() + w.slice(1));
    }).join(' ');
  }

  function showDetail(anchorEl, info) {
    closePop();
    var pop = document.createElement('div');
    pop.setAttribute('role', 'dialog');
    pop.setAttribute('aria-label', 'Save impact detail');
    var pageList = (info.pages || []).map(function (p) { return '<li style="margin:1px 0;">' + esc(prettyPage(p)) + '</li>'; }).join('');
    // USER-VOICE: render the plain cascade names, never raw table names. Cap the list.
    var cascList = info.cascades_plain || [];
    var cascShown = cascList.slice(0, 6).join(', ') + (cascList.length > 6 ? ', +' + (cascList.length - 6) + ' more' : '');
    var casc = cascList.length
      ? '<div style="margin-top:6px;color:rgba(255,255,255,0.55);">Also updates: ' + esc(cascShown) + '</div>' : '';
    pop.innerHTML =
      '<div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.05em;color:#F7A21B;margin-bottom:4px;">Saving here updates ' + info.page_count + ' pages</div>'
      + '<ul style="margin:0;padding-left:16px;font-size:11px;color:rgba(255,255,255,0.9);">' + pageList + '</ul>' + casc;
    pop.style.cssText = 'position:absolute;z-index:9999;max-width:280px;background:#10151c;border:1px solid rgba(247,162,27,0.35);border-radius:10px;padding:10px 12px;box-shadow:0 8px 28px rgba(0,0,0,0.45);';
    document.body.appendChild(pop);
    var r = anchorEl.getBoundingClientRect();
    pop.style.top = (r.bottom + window.scrollY + 6) + 'px';
    pop.style.left = Math.max(8, r.left + window.scrollX) + 'px';
    _pop = pop;
    setTimeout(function () { document.addEventListener('keydown', onKey, true); }, 0);
  }

  function attach(info) {
    var sel = SURFACE_ANCHORS[surfaceKey()];
    if (!sel) return;
    var btn = document.querySelector(sel);
    if (!btn || btn.dataset.whImpact) return;
    btn.dataset.whImpact = '1';
    var hint = document.createElement('button');
    hint.type = 'button';
    hint.className = 'wh-impact-hint';
    hint.setAttribute('aria-label', 'Saving updates ' + info.page_count + ' pages: tap for the list');
    hint.title = info.headline;
    hint.innerHTML = '<span aria-hidden="true">↗</span> Saving updates <b>' + info.page_count + ' pages</b> across the platform · <span style="text-decoration:underline;">what</span>';
    hint.style.cssText = 'display:block;width:100%;text-align:left;margin:0 0 8px 0;padding:7px 10px;min-height:44px;box-sizing:border-box;'
      + 'background:rgba(247,162,27,0.08);border:1px solid rgba(247,162,27,0.25);border-radius:8px;'
      + 'color:rgba(247,162,27,0.95);font-size:11px;font-weight:600;cursor:pointer;font-family:inherit;';
    hint.addEventListener('click', function (e) {
      e.preventDefault(); e.stopPropagation();
      if (_pop) closePop(); else showDetail(hint, info);
    });
    // place the hint right above the save button
    btn.parentNode.insertBefore(hint, btn);
    window.__whImpactAttached = true;
  }

  function boot() {
    fetch('field_impact_preview.json', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.surfaces) return;
        var info = data.surfaces[surfaceKey()];
        if (!info) return;
        attach(info);
        if (!window.__whImpactAttached) setTimeout(function () { attach(info); }, 1500);
      })
      .catch(function () { /* empty-catch-allow: progressive enhancement — the save-impact hint is optional, a fetch failure must not break the save flow */ });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
