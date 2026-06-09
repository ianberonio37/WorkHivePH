/**
 * maturity-gate.js — Phase 0.3 of STRATEGIC_ROADMAP.md.
 *
 * Shared helper that lets any Stair-gated page surface the gap honestly
 * instead of rendering a chart of garbage when the hive lacks the inputs.
 *
 * Doctrine (from STRATEGIC_ROADMAP §2):
 *   "We never promise predictive analytics on insufficient data.
 *    If a hive has insufficient history, the predictive tile says so
 *    honestly instead of producing charts of garbage."
 *
 * Usage on a Stair-3-gated page:
 *
 *   <script src="utils.js"></script>
 *   <script src="maturity-gate.js"></script>
 *   ...
 *   const gate = await checkMaturityGate(db, HIVE_ID, 3);
 *   if (gate.blocked) {
 *     renderMaturityHonestEmpty('#main-content', gate, {
 *       pageName: 'Predictive Maintenance',
 *       requiredStair: 3,
 *       requiredStairName: 'Predictive-Ready',
 *       why: 'Predictive analytics on insufficient data lies. We refuse to lie.',
 *     });
 *     return;   // skip the normal page render
 *   }
 *
 * The helper reads `v_hive_readiness_truth` (canonical view) and returns
 * `{ blocked, currentStair, blockerSummary, evidence }`. If the hive has
 * no readiness snapshot yet (fresh hive), it returns blocked=true with a
 * "snapshot pending" message — never silently passes.
 */

(function (root) {
  'use strict';

  const STAIR_NAMES = ['Paper', 'Digital Logbook', 'Disciplined', 'Predictive-Ready', 'Industry Leader'];
  const STAIR_COLOR = ['#4A9FD4', '#00C4B4', '#9B59E8', '#F7A21B', '#FFB800'];

  /**
   * checkMaturityGate(db, hiveId, requiredStair)
   *
   * Returns:
   *   {
   *     blocked: boolean,
   *     currentStair: number | null,
   *     currentStairName: string,
   *     requiredStair: number,
   *     requiredStairName: string,
   *     blockerSummary: string,
   *     evidence: object,
   *     compositeScore: number | null,
   *   }
   */
  async function checkMaturityGate(db, hiveId, requiredStair) {
    if (!db || !hiveId) {
      return {
        blocked: true,
        currentStair: null,
        currentStairName: 'Unknown',
        requiredStair,
        requiredStairName: STAIR_NAMES[requiredStair] || 'Unknown',
        blockerSummary: 'No hive context — join or create a hive first.',
        evidence: {},
        compositeScore: null,
      };
    }
    try {
      const { data, error } = await db.from('v_hive_readiness_truth')
        .select('current_stair, composite_score, blocker_summary, evidence')
        .eq('hive_id', hiveId)
        .maybeSingle();
      if (error && error.code !== 'PGRST116') {
        // PGRST116 = no rows; treat as fresh hive, not error
        console.warn('[maturity-gate] check failed:', error.message);
      }
      const cs = data && typeof data.current_stair === 'number' ? data.current_stair : 0;
      const blocked = cs < requiredStair;
      return {
        blocked,
        currentStair: data ? cs : null,
        currentStairName: STAIR_NAMES[cs] || 'Paper',
        requiredStair,
        requiredStairName: STAIR_NAMES[requiredStair] || 'Industry Leader',
        blockerSummary: data
          ? (data.blocker_summary || `Reach Stair ${requiredStair} to unlock this surface.`)
          : 'No readiness snapshot yet for your hive — the daily compute will populate it.',
        evidence: (data && data.evidence) || {},
        compositeScore: data ? Number(data.composite_score) : null,
      };
    } catch (err) {
      console.warn('[maturity-gate] threw:', err && err.message ? err.message : err);
      return {
        blocked: true,
        currentStair: null,
        currentStairName: 'Unknown',
        requiredStair,
        requiredStairName: STAIR_NAMES[requiredStair] || 'Industry Leader',
        blockerSummary: 'Could not reach readiness service. Try refreshing in a minute.',
        evidence: {},
        compositeScore: null,
      };
    }
  }

  /**
   * renderMaturityHonestEmpty(selector, gate, opts)
   *
   * Replaces the container's contents with the honesty banner.
   * opts: {
   *   pageName: string,
   *   why: string,                  // one-line "why this gate exists"
   *   linkBack: string,             // default 'hive.html#maturity-stairway-card'
   *   alternateSuggestion?: string, // optional: closest available capability
   * }
   */
  function renderMaturityHonestEmpty(selectorOrEl, gate, opts) {
    opts = opts || {};
    const el = typeof selectorOrEl === 'string'
      ? document.querySelector(selectorOrEl)
      : selectorOrEl;
    if (!el) return;

    const esc = (root.escHtml || (s => String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;')));

    const cur = gate.currentStair == null ? '—' : String(gate.currentStair);
    const compChip = gate.compositeScore == null
      ? ''
      : `<span style="font-size:11px;color:rgba(255,255,255,0.5);margin-left:8px;">composite ${gate.compositeScore}/100</span>`;

    const altLine = opts.alternateSuggestion
      ? `<p style="font-size:12px;color:rgba(255,255,255,0.6);margin-top:10px;line-height:1.55;">In the meantime: ${esc(opts.alternateSuggestion)}</p>`
      : '';

    el.innerHTML = `
      <div style="max-width:680px;margin:32px auto;padding:24px;border-radius:16px;
                   background:linear-gradient(150deg, rgba(42,61,88,0.55), rgba(22,32,50,0.88));
                   border:1px solid rgba(255,255,255,0.08);">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
          <span style="display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;
                       font-size:10px;font-weight:800;letter-spacing:0.06em;text-transform:uppercase;
                       background:rgba(255,184,0,0.16);color:#FDB94A;">
            Honest Empty State
          </span>
          <span style="font-size:11px;color:rgba(255,255,255,0.45);">
            ${esc(opts.pageName || 'This surface')} unlocks at Stair ${esc(String(gate.requiredStair))} — ${esc(gate.requiredStairName)}
          </span>
        </div>
        <h1 style="font-size:1.15rem;font-weight:800;color:#F4F6FA;margin:6px 0 12px;">
          We won't fake this.
        </h1>
        <p style="font-size:13px;color:rgba(255,255,255,0.75);line-height:1.6;margin:0 0 14px;">
          ${esc(opts.why || 'Producing this output on insufficient data would mislead you. WorkHive surfaces the gap honestly instead.')}
        </p>
        <div style="background:rgba(0,0,0,0.22);border:1px solid rgba(255,255,255,0.06);
                     border-radius:10px;padding:12px 14px;margin:14px 0;">
          <p style="font-size:11px;font-weight:800;letter-spacing:0.05em;text-transform:uppercase;
                     color:rgba(255,255,255,0.45);margin:0 0 6px;">Your hive right now</p>
          <p style="font-size:13px;color:#F4F6FA;line-height:1.55;margin:0;">
            <strong>Stair ${esc(cur)} · ${esc(gate.currentStairName)}</strong>${compChip}
          </p>
          <p style="font-size:12px;color:rgba(255,255,255,0.65);line-height:1.55;margin:8px 0 0;">
            ${esc(gate.blockerSummary)}
          </p>
        </div>
        ${altLine}
        <div style="display:flex;gap:8px;margin-top:18px;flex-wrap:wrap;">
          <a href="${esc(opts.linkBack || 'hive.html')}#maturity-stairway-card"
             style="display:inline-flex;align-items:center;min-height:44px;padding:10px 18px;border-radius:10px;
                    background:linear-gradient(135deg,#F7A21B,#FDB94A);color:#162032;
                    font-size:12px;font-weight:800;text-decoration:none;">
            Open Maturity Stairway →
          </a>
          <a href="hive.html"
             style="display:inline-flex;align-items:center;min-height:44px;padding:10px 18px;border-radius:10px;
                    background:rgba(255,255,255,0.04);color:rgba(255,255,255,0.65);
                    border:1px solid rgba(255,255,255,0.08);
                    font-size:12px;font-weight:700;text-decoration:none;">
            Back to Hive Board
          </a>
        </div>
      </div>
    `;
  }

  root.checkMaturityGate          = checkMaturityGate;
  root.renderMaturityHonestEmpty  = renderMaturityHonestEmpty;
  root.MATURITY_STAIR_NAMES       = STAIR_NAMES;
  root.MATURITY_STAIR_COLORS      = STAIR_COLOR;
})(window);
