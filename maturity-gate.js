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
  /* ★T187 (2026-08-26): THIS SYSTEM WAS ONE-DIRECTIONAL. maturity-gate told a hive what it could
     not have yet - "unlocks at Stair 2", "reach Stair 3" - on every gated surface, and said nothing
     whatsoever when the hive CROSSED one. A plant that spent three months building logbook history
     earned Stair 2 in silence: the refusal simply stopped appearing, which nobody notices, because
     noticing an absence is not how people work. The whole promise of the maturity ladder is that
     patience is rewarded, and the reward was never announced.

     Detected centrally rather than per-page, because every gated surface already calls
     checkMaturityGate and only the FIRST one after a crossing should speak. The last stair seen is
     device-local on purpose (it is a "have you been told" flag, not a fact about the hive - see the
     account-vs-device split in state_scope_registry.json), and it is keyed by hive so switching
     hives cannot make one hive's progress announce the other's.

     ★IT ONLY EVER ANNOUNCES A RISE. A stair that goes DOWN - readiness decays if logging stops - is
     recorded silently: telling someone they have been demoted, unprompted, on whatever page they
     happened to open, is a different feature and a crueller one. The refusal messages already
     explain what is missing when they next hit a gate. */
  function _noteStairProgress(hiveId, cs) {
    try {
      if (typeof cs !== 'number' || !hiveId) return;
      var K = 'wh_last_stair_seen_' + hiveId;
      var raw = localStorage.getItem(K);
      var prev = raw === null ? null : Number(raw);
      localStorage.setItem(K, String(cs));
      if (prev === null || !isFinite(prev)) return;   // first sight: record, never announce
      if (cs <= prev) return;                         // no rise, or a decay we stay quiet about
      var name = STAIR_NAMES[cs] || ('Stair ' + cs);
      if (typeof window !== 'undefined' && typeof window.showToast === 'function') {
        window.showToast('Your hive reached Stair ' + cs + ': ' + name +
                         '. The surfaces that were waiting on this are open now.', 'success');
      }
    } catch (_) {
      /* empty-catch-allow: an unlock notice must never be the reason a gate check fails */
    }
  }

  async function checkMaturityGate(db, hiveId, requiredStair) {
    if (!db || !hiveId) {
      return {
        blocked: true,
        currentStair: null,
        currentStairName: 'Unknown',
        requiredStair,
        requiredStairName: STAIR_NAMES[requiredStair] || 'Unknown',
        blockerSummary: 'No hive context: join or create a hive first.',
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
        // The fourth state (2026-09-05): a FAILED readiness read used to fall through as 'stair 0' and LOCK the surface
        // with 'No readiness snapshot yet' - a network error dressed as a maturity verdict. Fail OPEN and say why.
        return {
          blocked: false, readFailed: true,
          currentStair: null, currentStairName: 'unknown',
          requiredStair, requiredStairName: STAIR_NAMES[requiredStair] || 'Industry Leader',
          blockerSummary: "Could not check your hive's readiness (" + (error.message || 'read failed') + "). This page opens unlocked; reload to re-check.",
          evidence: {}, compositeScore: null,
        };
      }
      const cs = data && typeof data.current_stair === 'number' ? data.current_stair : 0;
      const blocked = cs < requiredStair;
      // only with a genuine snapshot: a missing one reads as 0 and would announce a fake climb
      if (data && typeof data.current_stair === 'number') _noteStairProgress(hiveId, cs);
      return {
        blocked,
        currentStair: data ? cs : null,
        currentStairName: STAIR_NAMES[cs] || 'Paper',
        requiredStair,
        requiredStairName: STAIR_NAMES[requiredStair] || 'Industry Leader',
        blockerSummary: data
          ? (data.blocker_summary || `Reach Stair ${requiredStair} to unlock this surface.`)
          : 'No readiness snapshot yet for your hive: the daily compute will populate it.',
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

    // EX-TL (2026-09-07): this gate is the WHOLE page a locked surface shows (ai-quality read 2 of 15
    // visible strings in Filipino), so its own words go through the platform translator when present.
    //
    // ★AND ONE STRING STILL WASN'T, TWO PASSES LATER (2026-09-18, W45972 slop on ph-intelligence).
    // "Back to Hive Board" was the single literal left outside T() in a panel where every other word
    // goes through it - the exact partial-fix shape the 2026-09-07 pass was itself repairing. It is
    // worth naming rather than just fixing: the reason a translator pass misses one string is that
    // nothing MEASURES the ratio, so "most of the panel is bilingual" reads as done. The Filipino walk
    // is what reads 14 of 15 and says so.
    //
    // ★THIS PANEL *IS* THE PAGE, SO ITS TYPE RAMP IS THE PAGE'S TYPE RAMP (same row). ph-intelligence
    // measured minFontPx 11, five ramp steps at phone and EIGHT at desktop, and rhythmOffGrid 11 - and
    // every one of those numbers was THIS FILE, because a gated surface replaces <main> with this and
    // renders nothing else. The page's own stylesheet was never in evidence. Brought onto DESIGN.md's
    // declared ramp and the 4px grid: the composite chip and .wh-source-chip 11px -> 12px (the floor);
    // the why-sentence and the stair line 13px -> 14px (the body step, 0.875rem); the h1 1.15rem ->
    // 1.125rem (the headline step, which 1.15rem was a hair off for no reason anyone recorded); and the
    // 10 / 14 / 18px margins and paddings to 8 / 16 / 16. The 12px floor gate cannot see any of this -
    // it walks served PAGES, and a module that injects markup into every page is not a page - which is
    // the same "a glob is a claim about coverage" gap, one layer out.
    //
    // ★AND THE BREADTH OF THIS FILE, COUNTED RATHER THAN ASSERTED (2026-09-18). I called this panel "the
    // whole visible surface of every stair-gated page" in three receipts before counting the call sites,
    // and an isolated assessor handed the claim back measured. renderMaturityHonestEmpty has exactly TWO
    // live callers - ai-quality.html:196 (Stair 2) and ph-intelligence.html:337 (Stair 3); every other
    // hit is a backup or a working copy. checkMaturityGate has two more that never render this panel
    // (alert-hub.html:1146, hive.html:4275). So the repairs here pay on TWO pages, not sixty. Every
    // finding is unchanged and each reproduces on both - it is the NUMBER that was mine, and it was a
    // guess wearing the word "platform-wide", which is the same error as a glob that describes where you
    // looked rather than where the thing lives.
    //
    // ★AND THE MEASURE, MEASURED PROPERLY (2026-09-18, W45973 craft). The walk's own bodyMeasureCh read
    // 53 at desktop while the widest prose paragraph on the same screen ran 81ch. Which element the
    // metric sampled is not recoverable from its output - and that is the point: it reports ONE number
    // from ONE paragraph, the longest by CHARACTER COUNT, which is not the widest by BOX, so a passing
    // reading says nothing about the paragraph beside it. Re-measured per paragraph, with
    // the advance taken from each element's OWN computed font through canvas rather than an assumed
    // constant, in this 680px card at 1280: the why-sentence 631px = 81ch = 100 LETTERS a line, and
    // "In the meantime:" 631px = 94ch = 114 letters. The craft floor asks for 65-75. A reader loses the
    // start of the next line somewhere past 80, which is the whole reason the band exists. Every prose
    // paragraph here is now capped at 68ch - the unit the cap belongs in, since `ch` IS the 0-advance
    // and so tracks each paragraph's own size instead of freezing one pixel width. At phone the card is
    // already narrower than the cap, so nothing moves there: measured 53 letters before and after.
    const T = (typeof root._t === 'function') ? root._t : ((en) => en);
    const cur = gate.currentStair == null ? '-' : String(gate.currentStair);
    const compChip = gate.compositeScore == null
      ? ''
      : `<span style="font-size:12px;color:rgba(255,255,255,0.72);margin-left:8px;">${T('readiness', 'readiness')} ${gate.compositeScore}/100 · ${T('higher is better', 'mas mataas, mas mabuti')}</span>`;

    /* ★THE EVIDENCE WAS FETCHED, CARRIED, AND THROWN AWAY (2026-09-18, W45978 critique - BOTH isolated
       assessments found this independently, and it is the finding that turns this panel from a verdict
       into a task). checkMaturityGate selects `evidence`, returns it on the gate object, and this
       renderer never read it - while hive.html renders ten lines from the SAME object, including the
       denominator this panel was missing. So a supervisor was told "0 of 5 active workers writing
       entries this week" with no way to know whether 5 is even reachable: if her hive has three members
       it is not, and the number of members was sitting in the object in hand.

       ★AND THE BLOCKER IS THE NEXT STAIR'S, NEVER THE TARGET'S. compute_hive_readiness assigns
       v_blocker inside its stair ladder, so the sentence always describes the step from the CURRENT
       stair to the one above it. On a page gating at Stair 3, a hive at Stair 1 reads the Stair-1-to-2
       blocker under an h1 naming Stair 3 - so clearing it, at real cost, lands her one stair short with
       a new sentence waiting. Nothing said so. `nextStepLabel` says it now, and the criteria rows below
       price the step before it is spent. */
    const _crit = [
      ['need_assets',                  'asset_count',            T('Assets registered', 'Mga asset na nakarehistro'), ''],
      ['need_active_workers',          'active_workers_7d',      T('People writing entries this week', 'Mga taong nagsusulat ngayong linggo'), ''],
      ['need_pm_templates',            'pm_template_count',      T('PM templates', 'Mga PM template'), ''],
      ['need_pm_compliance_pct',       'pm_compliance_30d_pct',  T('PM work done on time', 'PM na natapos sa oras'), '%'],
      ['need_logbook_hygiene_pct',     'logbook_hygiene_pct',    T('Entries filled in properly', 'Mga entry na kumpleto'), '%'],
      ['need_supervisor_actions_week', 'supervisor_actions_7d',  T('Supervisor sign-offs this week', 'Mga sign-off ng supervisor ngayong linggo'), ''],
      ['need_history_days',            'history_days',           T('Days of history', 'Araw ng kasaysayan'), ''],
      ['need_rcm_approved',            'fmea_modes_approved',    T('Approved RCM strategies', 'Mga aprubadong RCM na estratehiya'), ''],
    ];
    const _ev = (gate.evidence && typeof gate.evidence === 'object') ? gate.evidence : {};
    const _inputs = _ev.inputs || {};
    const _need = _ev.thresholds_for_next_stair || {};
    const _rows = _crit.reduce((acc, [needKey, inKey, label, unit]) => {
      if (!(needKey in _need)) return acc;
      const want = Number(_need[needKey]);
      const have = Number(_inputs[inKey]);
      if (!isFinite(want) || !isFinite(have)) return acc;
      const done = have >= want;
      // The unmet ones are what she can act on; a met one still earns its line, because "2 of 3 done"
      // is a different feeling from a list of failures, and both numbers are true.
      return acc + `<li style="display:flex;gap:8px;align-items:baseline;margin:4px 0;">
        <span aria-hidden="true" style="flex:0 0 auto;color:${done ? 'var(--wh-green, #4ADE80)' : 'var(--wh-orange-light, #FDB94A)'};">${done ? '✓' : '•'}</span>
        <span style="flex:1 1 auto;">${esc(label)}</span>
        <span style="flex:0 0 auto;font-weight:700;font-variant-numeric:tabular-nums;">${esc(String(Math.round(have)))}${unit} ${T('of', 'sa')} ${esc(String(want))}${unit}</span>
      </li>`;
    }, '');
    const criteriaRows = _rows
      ? `<ul style="list-style:none;margin:8px 0 0;padding:0;font-size:12px;color:rgba(255,255,255,0.80);max-width:68ch;">${_rows}</ul>`
      : '';
    // Only say "first step" when the target really is more than one stair away; otherwise it is THE step.
    const _gap = (typeof gate.currentStair === 'number' && typeof gate.requiredStair === 'number')
      ? gate.requiredStair - gate.currentStair : 1;
    const nextStepLabel = _gap > 1
      ? `<strong>${esc(T('Your next step (one of ' + _gap + '):', 'Susunod mong hakbang (isa sa ' + _gap + '):'))}</strong>`
      : `<strong>${esc(T('Your next step:', 'Susunod mong hakbang:'))}</strong>`;

    /* ★THE ONE THING SHE COULD DO IN THE NEXT TWO MINUTES WAS TEXT, NOT A CONTROL (2026-09-18, W45978 -
       both assessments, and the second corrected the first's prescription). alternateSuggestion goes
       through esc(), so it can never become a link: "use the Analytics Engine on your own data" was a
       destination spelled out for someone to go and find in a nav menu, mid-shift, on a phone. A single
       alternateHref would have fitted this page and NOT the other caller - ai-quality names THREE tasks
       ("log 30 days of fault history. Add your top 5 assets. Finish at least one PM.") and makes all
       three untappable - so the contract takes a LIST. Each entry is rendered as a real secondary
       control at the platform's 44px floor. A refusal that names a destination and links it is a
       redirect; one that names it and does not is a dead end with good manners. */
    const _acts = Array.isArray(opts.alternateActions) ? opts.alternateActions : [];
    const altActions = _acts.length
      ? `<div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;">` + _acts.map((a) => (
          a && a.href && a.label
            ? `<a href="${esc(a.href)}" style="display:inline-flex;align-items:center;min-height:44px;
                 padding:12px 20px;border-radius:10px;background:rgba(255,255,255,0.04);
                 color:var(--wh-steel-bright, #A8B3C4);border:1px solid rgba(255,255,255,0.08);
                 font-size:12px;font-weight:700;text-decoration:none;">${esc(a.label)}</a>`
            : '')).join('') + `</div>`
      : '';

    const altLine = opts.alternateSuggestion
      ? `<p style="font-size:12px;color:rgba(255,255,255,0.72);margin-top:8px;line-height:1.55;max-width:68ch;">${T('In the meantime:', 'Sa ngayon:')} ${esc(opts.alternateSuggestion)}</p>`
      : '';

    // ★THE WHOLE PAGE WAS ONE LIVE REGION (2026-09-18, W45974 audit). role="status" aria-live="polite"
    // sat on the outer card, and this card IS <main> on a gated page - measured 879 of 879 characters,
    // 99% of main. role="status" is for a brief message about what just changed; wrapping the entire
    // surface in one means a screen reader is read the whole page as an interruption, and any later
    // touch of the DOM re-announces all of it. But removing it outright would be wrong too, and that is
    // the part worth getting right: this panel REPLACES main's content after an async readiness read, so
    // somebody already reading the page does have it swapped under them and deserves to be told. The
    // correct idiom is to announce the CHANGE and leave the detail as navigable content - so the live
    // region now scopes to the chip row plus the h1 (about 75 characters: "Locked - Maturity Stairway -
    // PH Intelligence unlocks at Stair 3: Predictive-Ready") and the body below it is ordinary prose.
    el.innerHTML = `
      <div style="max-width:680px;margin:32px auto;padding:24px;border-radius:16px;
                   background:linear-gradient(150deg, rgba(42,61,88,0.55), rgba(22,32,50,0.88));
                   border:1px solid rgba(255,255,255,0.08);">
        <div role="status" aria-live="polite">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
          <span style="display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;
                       font-size:12px;font-weight:700;   /* 12px floor, sentence case: the 10px all-caps pill was the smallest type on every gated page (design lens slop on ai-quality, 2026-09-15) */
                       background:rgba(255,184,0,0.16);color:var(--wh-orange-light, #FDB94A);">
            ${T('Locked', 'Naka-lock')}
          </span>
          <span style="font-size:12px;color:rgba(255,255,255,0.80);">
            ${T('Maturity Stairway', 'Maturity Stairway')}
          </span>
        </div>
        <h1 style="font-size:1.125rem;font-weight:800;color:var(--wh-cloud, #F4F6FA);margin:8px 0 12px;">
          ${esc(opts.pageName || 'This surface')} <span data-i="mg_unlocks_at">unlocks at Stair</span> ${esc(String(gate.requiredStair))}: ${esc(gate.requiredStairName)}
        </h1>
        </div><!-- /role=status: the announcement ends here; everything below is navigable content -->
        <p style="font-size:14px;color:rgba(255,255,255,0.75);line-height:1.6;margin:0 0 16px;max-width:68ch;">
          ${esc(opts.why || T('This view fills in once your hive has enough real data to make it accurate.', 'Mapupunan ang view na ito kapag sapat na ang totoong data ng hive mo para maging tumpak ito.'))}
        </p>
        <div style="background:rgba(0,0,0,0.22);border:1px solid rgba(255,255,255,0.06);
                     border-radius:10px;padding:12px 16px;margin:16px 0;">
          <h2 data-i="mg_hive_now" style="font-size:12px;font-weight:700;
                     color:rgba(255,255,255,0.80);margin:0 0 6px;">Your hive right now</h2>   <!-- 12px, sentence case: no all-caps tracked eyebrow as a heading (critique lens on ai-quality, 2026-09-15) -->
          <p style="font-size:14px;color:var(--wh-cloud, #F4F6FA);line-height:1.55;margin:0;">
            <!-- The space before the chip is LOAD-BEARING: margin-left is a visual gap and contributes
                 nothing to textContent, so this line announced as "Digital Logbookcomposite 63/100".
                 Second instance of the same defect in this one row - the other was a <br> inside
                 ph-intelligence's h1. A separator a reader sees has to exist in the TEXT as well. -->
            <strong>Stair ${esc(cur)} · ${esc(gate.currentStairName)}</strong> ${compChip}
          </p>
          <p style="font-size:14px;color:var(--wh-cloud, #F4F6FA);line-height:1.55;margin:8px 0 0;max-width:68ch;">
            ${nextStepLabel} ${esc(gate.blockerSummary)}
          </p>
          ${criteriaRows}
        </div>
        ${altLine}
        ${altActions}
        <details class="wh-help" style="margin:12px 0 0;font-size:12px;">
          <summary style="cursor:pointer;font-weight:700;color:rgba(255,255,255,0.72);">${T('How the stairway works', 'Paano gumagana ang stairway')}</summary>
          <p style="margin:4px 0 0;color:rgba(255,255,255,0.72);line-height:1.55;max-width:68ch;">
            ${T('Each stair is earned by real records, and the snapshot recomputes on its own. Stair 1 needs your assets registered. Stair 2 needs a steady logbook habit - five people writing entries in a week, and five PM templates. Stair 3 needs PM discipline: preventive work done on time, entries filled in properly, and a supervisor signing off each week.',
                'Bawat stair ay nakukuha sa totoong record. Kailangan ng Stair 1 ng tuloy-tuloy na logbook habit. Kailangan ng Stair 2 ng tuloy-tuloy na PM discipline. Kailangan ng Stair 3 ng sapat na kasaysayan para sa tumpak na analytics. Magpatuloy sa pag-log at kusang gagalaw ang snapshot.')}
          </p>
        </details>
        <p class="wh-source-chip" style="font-size:12px;color:rgba(255,255,255,0.72);margin:8px 0 0;line-height:1.4;">
          ${T('Readiness &middot; from your hive&#39;s live records', 'Readiness &middot; mula sa live na record ng hive mo')}
        </p>
        <div style="display:flex;gap:8px;margin-top:16px;flex-wrap:wrap;">
          <a href="${esc(opts.linkBack || 'hive.html')}#maturity-stairway-card"
             style="display:inline-flex;align-items:center;min-height:44px;padding:12px 20px;border-radius:10px;
                    background:linear-gradient(135deg,var(--wh-orange, #F7A21B),var(--wh-orange-light, #FDB94A));color:var(--wh-navy, #162032);
                    font-size:12px;font-weight:800;text-decoration:none;">
            ${T('Open Maturity Stairway →', 'Buksan ang Maturity Stairway →')}
          </a>
          <a href="hive.html"
             style="display:inline-flex;align-items:center;min-height:44px;padding:12px 20px;border-radius:10px;
                    background:rgba(255,255,255,0.04);color:rgba(255,255,255,0.72);
                    border:1px solid rgba(255,255,255,0.08);
                    font-size:12px;font-weight:700;text-decoration:none;">
            ${T('Back to Hive Board', 'Bumalik sa Hive Board')}
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
