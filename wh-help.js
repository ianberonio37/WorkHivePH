// ─────────────────────────────────────────────────────────────────────────────
// wh-help.js — Plain-language tooltips powered by canonical_sources.
//
// New supervisors should not have to guess what "Acknowledge", "WATCH 39/100",
// or "Stair 2 · Disciplined" means. The platform already stores plain-text
// descriptions of every canonical concept in the `canonical_sources` table
// (one row per domain). This helper surfaces those descriptions inline.
//
// Three layers:
//
//   1. A small static fallback map for concepts that aren't canonical_sources
//      rows (UI lifecycle states, severity bands, etc.) so a tooltip always
//      has something useful to say even on a fresh stack.
//
//   2. On first hover/tap of a `[data-help="..."]` element, fetch the
//      matching canonical_sources row from the DB. Cache it in memory for
//      the rest of the session.
//
//   3. Render a small popover with the description + a "Source" line. Tap
//      anywhere outside to dismiss. The popover is keyboard + screen reader
//      friendly (role="tooltip" + aria-describedby).
//
// Usage on any page:
//   <script defer src="wh-help.js"></script>
//   ...then any element gets a tooltip just by tagging it:
//   <button data-help="anomaly_signals">Anomaly Engine 2.0</button>
//   <span   data-help="anomaly_acknowledged" tabindex="0">Acknowledge</span>
//
// The data-help value matches canonical_sources.domain OR a key in the
// STATIC_HELP map below. Domain takes priority; static fallback is used
// only when DB lookup returns nothing.
//
// Skills consulted: designer (low-chrome inline help), community (new-user
// orientation), knowledge-manager (canonical_sources is the glossary).
// ─────────────────────────────────────────────────────────────────────────────

(function () {
  if (typeof window === 'undefined') return;
  if (window._whHelpMounted) return;
  window._whHelpMounted = true;

  // Plain-language fallbacks. Used when no canonical_sources row exists
  // for the key (UI states, severity bands, etc.) OR while the DB lookup
  // is still in flight on first hover.
  const STATIC_HELP = {
    // Anomaly Engine 2.0 lifecycle
    anomaly_acknowledged: {
      title:  'Acknowledged',
      detail: 'A supervisor saw this anomaly and is on it, but has not closed it yet. Other supervisors know not to duplicate work. This is a coordination signal, not a fix.',
    },
    anomaly_resolved: {
      title:  'Resolved',
      detail: 'The supervisor closed this anomaly. Either the underlying issue was fixed, or the signal was a false positive. Resolved anomalies fall out of the top-5 panel.',
    },
    // Severity bands (Anomaly Engine 2.0)
    severity_watch: {
      title:  'WATCH severity',
      detail: 'Composite score 25-49. Worth keeping an eye on; not yet urgent. Often one or two signal sources fired.',
    },
    severity_warning: {
      title:  'WARNING severity',
      detail: 'Composite score 50-74. Two or more sources agree this asset is drifting. Plan corrective work this shift.',
    },
    severity_critical: {
      title:  'CRITICAL severity',
      detail: 'Composite score 75+. Multiple independent signals agree. Treat as urgent: stage parts, brief crew, intervene before the next shift.',
    },
    // Maturity stairs
    stair_0: { title: 'Stair 0 · Paper',          detail: 'Just signed up. Register 10 assets and document one SOP to unlock Stair 1.' },
    stair_1: { title: 'Stair 1 · Digital Logbook', detail: 'Five active workers writing entries each week. Five PM templates registered. Logbook discipline is forming.' },
    stair_2: { title: 'Stair 2 · Disciplined',    detail: 'PM compliance and logbook hygiene above target. Supervisor approving five actions a week. Predictive analytics suppressed until enough history accumulates.' },
    stair_3: { title: 'Stair 3 · Predictive-Ready', detail: '90+ days of logbook history OR live sensors. Anomaly Engine 2.0 unlocks. AI Quality + ROI surface available.' },
    stair_4: { title: 'Stair 4 · Industry Leader', detail: 'Sensor pipeline live, RCM strategies approved, audit trail compliant, federated benchmarks opted-in. Top of the stack.' },
    // Adoption risk tiers
    tier_healthy:  { title: 'Healthy adoption',  detail: 'Workers are active, the supervisor is engaged, the hive is moving. Composite risk below 35.' },
    tier_at_risk:  { title: 'At-risk adoption',  detail: 'One or two adoption signals are slipping. Read the Why? drawer to see which.' },
    tier_critical: { title: 'Critical adoption', detail: 'Multiple signals show the hive is losing momentum. Composite risk 65+. Take action this week.' },
  };

  // Cached DB lookups: { domain: row|null }
  const _cache = new Map();

  const STYLE = `
    [data-help] { cursor: help; }
    [data-help]:hover { text-decoration: underline dotted rgba(255,255,255,0.25); }
    .wh-help-pop {
      position: fixed; z-index: 9999;
      max-width: min(300px, calc(100vw - 1rem));
      background: rgba(22, 32, 50, 0.98);
      color: #F4F6FA;
      border: 1px solid rgba(247,162,27,0.4);
      border-radius: 0.65rem;
      padding: 0.7rem 0.85rem;
      font-family: 'Poppins', system-ui, sans-serif;
      font-size: 0.72rem;
      line-height: 1.5;
      box-shadow: 0 8px 24px rgba(0,0,0,0.45);
      backdrop-filter: blur(8px);
    }
    .wh-help-pop h4 {
      margin: 0 0 0.25rem;
      font-size: 0.78rem;
      font-weight: 800;
      color: #F7A21B;
    }
    .wh-help-pop p { margin: 0; color: rgba(255,255,255,0.82); }
    .wh-help-pop .wh-help-source {
      display: block;
      margin-top: 0.5rem;
      font-size: 0.6rem;
      color: rgba(255,255,255,0.35);
    }
    .wh-help-pop .wh-help-source code {
      background: rgba(255,255,255,0.06);
      padding: 1px 4px;
      border-radius: 3px;
    }
  `;

  function _mountStyles() {
    if (document.getElementById('wh-help-styles')) return;
    const s = document.createElement('style');
    s.id = 'wh-help-styles';
    s.textContent = STYLE;
    document.head.appendChild(s);
  }

  function _esc(s) {
    return String(s || '').replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[c]);
  }

  async function _fetchCanonical(key) {
    if (_cache.has(key)) return _cache.get(key);
    try {
      if (!window.db || !window.db.from) {
        _cache.set(key, null);
        return null;
      }
      const { data } = await window.db.from('canonical_sources')
        .select('domain, source_kind, source_name, description')
        .eq('domain', key)
        .maybeSingle();
      _cache.set(key, data || null);
      return data || null;
    } catch (_) {
      _cache.set(key, null);
      return null;
    }
  }

  let _activePop = null;

  function _dismiss() {
    if (!_activePop) return;
    _activePop.remove();
    _activePop = null;
  }

  function _renderPop(anchor, content) {
    _dismiss();
    const pop = document.createElement('div');
    pop.className = 'wh-help-pop';
    pop.setAttribute('role', 'tooltip');
    pop.innerHTML = content;
    document.body.appendChild(pop);
    _activePop = pop;
    // Position near the anchor, clamped to viewport.
    const r = anchor.getBoundingClientRect();
    const popR = pop.getBoundingClientRect();
    let top  = r.bottom + 8;
    let left = r.left;
    if (top + popR.height > window.innerHeight - 8) top = r.top - popR.height - 8;
    if (left + popR.width > window.innerWidth - 8) left = window.innerWidth - popR.width - 8;
    if (left < 8) left = 8;
    pop.style.top  = top + 'px';
    pop.style.left = left + 'px';
  }

  async function _show(anchor) {
    const key = anchor.getAttribute('data-help');
    if (!key) return;
    const fallback = STATIC_HELP[key] || null;
    // Render fallback immediately so the popover feels instant; upgrade to
    // the canonical_sources description if the DB row exists.
    if (fallback) {
      _renderPop(anchor, `
        <h4>${_esc(fallback.title)}</h4>
        <p>${_esc(fallback.detail)}</p>
      `);
    }
    const row = await _fetchCanonical(key);
    if (row && anchor.matches(':hover') || (_activePop && _activePop.dataset.key !== key)) {
      const title  = (fallback && fallback.title) || row.domain;
      const detail = row.description || (fallback && fallback.detail) || '';
      _renderPop(anchor, `
        <h4>${_esc(title)}</h4>
        <p>${_esc(detail)}</p>
        <span class="wh-help-source">Source: <code>${_esc(row.source_name)}</code> (${_esc(row.source_kind)})</span>
      `);
      if (_activePop) _activePop.dataset.key = key;
    } else if (!fallback && !row) {
      _renderPop(anchor, `<p style="color:rgba(255,255,255,0.5);">No description available for "${_esc(key)}".</p>`);
    }
  }

  function _bind() {
    _mountStyles();
    document.addEventListener('mouseover', (e) => {
      const t = e.target.closest('[data-help]');
      if (!t) return;
      _show(t);
    });
    document.addEventListener('mouseout', (e) => {
      const t = e.target.closest('[data-help]');
      if (t && _activePop) _dismiss();
    });
    document.addEventListener('focusin', (e) => {
      const t = e.target.closest('[data-help]');
      if (t) _show(t);
    });
    document.addEventListener('focusout', _dismiss);
    // Mobile / tap: click on a help anchor opens it; click elsewhere closes.
    document.addEventListener('click', (e) => {
      const t = e.target.closest('[data-help]');
      if (t) { _show(t); return; }
      if (_activePop && !_activePop.contains(e.target)) _dismiss();
    });
    window.addEventListener('scroll', _dismiss, { passive: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _bind);
  } else {
    _bind();
  }
})();
