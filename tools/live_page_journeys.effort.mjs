// live_page_journeys.effort.mjs — Arc V (EFFORTLESS) E·L·F·C scorers.
//
// WHY (EFFORTLESS_UX_ROADMAP.md): Arc K proves a job is COMPLETABLE; UFAI proves element
// FLOORS; neither measures whether the job is EFFORTLESS. This module turns the existing
// Arc-K journey drives into a FRICTION meter without rewriting a single drive():
//   E — Effort   : clicks + page-hops to goal vs `ideal` (NN/g Interaction Cost; Tesler)
//   F — Flow     : per-action latency vs Doherty 400ms; slow action w/ no busy affordance
//   (L — Load / C — Clarity are measured in the Critic pass; seeded here for later slices)
//
// MECHANISM: `instrumentHelpers(h)` returns a wrapper around makeHelpers() that counts every
// goto/click/clickText/fill and times it. The ~190 existing call-sites across the 102 JTBDs
// are counted FOR FREE — the drives don't change. `scoreEffort(counters, ideal)` then turns
// the counts into a per-journey friction record + excess-click DEBT (the ratchetable floor).
//
// HONESTY: a journey with NO seeded `ideal` contributes 0 debt and pass=null (excluded from
// the Effort floor) — we only assert debt where we have defined a target. The whole-platform
// ratchet (total click_hops ≤ baseline) needs NO ideals and locks total interaction cost as a
// ceiling, so any new friction (more clicks) fails the gate.

const nowMs = () => (globalThis.performance ? performance.now() : Date.now());

// ─── per-journey ideal targets (clicks + hops to complete the job) ──────────────
// Keyed by JTBD id. Seeded conservatively for the flagged worst-offenders; the rest are
// added as each sub-arc opens (until then: ideal=null → no debt asserted, honest baseline).
// engineering-design = 9 measured clicks → target ≤5 (decision-tree + smart-defaults).
export const IDEAL = {
  // V6.1 engineering-design (flagship FIX) — ids confirmed from the registry at seed time.
  // (left intentionally light for R0; per-page ideals are filled when each sub-arc starts)
};

// ─── F lens (Flow) busy-affordance watcher — installed in-page, NON-INVASIVELY ──────
// Doherty's Threshold: keep response <400ms OR show a busy affordance so the user knows the
// system is working. A slow action WITH feedback (spinner/skeleton/disabled-submit) is fine;
// a slow action that leaves a FROZEN screen is the real Flow violation. We detect feedback
// with a sticky MutationObserver flag — set true the instant any busy affordance becomes
// visible during an action window — grounded in the platform's ACTUAL loading classes
// (button-lock.js toggles `is-loading`; pages use .spinner/.loading/.skeleton/.ar-spinner).
// This is installed via page.evaluate AFTER each navigation; it never touches makeHelpers()
// (the shared Arc-K source), so the drives are unchanged and Arc K cannot regress.
export const FLOW_WATCH = () => {
  if (window.__fbusy) return; // survive re-install; navigation wipes it so goto re-installs
  const SEL = '.spinner,.loading,.loader,.loading-overlay,.skeleton,.is-loading,.btn-loading,.ar-spinner,[aria-busy="true"],[data-loading="true"],.busy,progress';
  const vis = (el) => { try { const b = el.getBoundingClientRect(); const s = getComputedStyle(el); return b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0'; } catch (e) { return false; } };
  const anyBusy = () => {
    try {
      const body = document.body; if (!body) return false;
      if (body.getAttribute('aria-busy') === 'true' || document.documentElement.getAttribute('aria-busy') === 'true') return true;
      const cur = getComputedStyle(body).cursor; if (cur === 'wait' || cur === 'progress') return true;
      return [...document.querySelectorAll(SEL)].some(vis);
    } catch (e) { return false; }
  };
  const state = { seen: false };
  const obs = new MutationObserver(() => { if (!state.seen && anyBusy()) state.seen = true; });
  try { obs.observe(document.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'aria-busy', 'style', 'disabled', 'data-loading'] }); } catch (e) { }
  window.__fbusy = { reset() { state.seen = false; }, read() { return state.seen || anyBusy(); } };
};

// Wrap a helpers object so interaction methods are counted + timed + FLOW-judged. Preserves
// every other helper (db/evalIn/adminQuery/qText/exists/count/waitFor/numFrom/resetRates/page)
// untouched. For each interactive action (click/fill) we reset the busy flag BEFORE timing and
// read it AFTER — so `busy` records whether the user got ANY feedback during a slow action.
export function instrumentHelpers(h) {
  const page = h.page;
  const counters = { clicks: 0, fills: 0, hops: 0, steps: 0, actions: [] };
  const evalSafe = async (fn) => { try { return await page.evaluate(fn); } catch (e) { return null; } };
  const wrap = (type, fn) => async (...a) => {
    const interactive = (type === 'click' || type === 'fill');
    if (interactive) await evalSafe(() => { if (window.__fbusy) window.__fbusy.reset(); }); // before t0 → no timing inflation
    const t0 = nowMs();
    let ok = true, r;
    try { r = await fn(...a); ok = (r !== false); }
    catch (e) { ok = false; r = false; }
    const ms = Math.round((nowMs() - t0) * 10) / 10;
    let busy = null;
    if (interactive) busy = await evalSafe(() => (window.__fbusy ? window.__fbusy.read() : null));
    counters.actions.push({ type, arg: String(a[0] ?? '').slice(0, 60), ms, ok, busy });
    counters.steps++;
    if (type === 'hop') counters.hops++;
    else if (type === 'click') counters.clicks++;
    else if (type === 'fill') counters.fills++;
    return r;
  };
  const gotoWrapped = wrap('hop', h.goto);
  const helpers = {
    ...h,
    // a navigation shows the browser's own load affordance (never "silent"), so it's not an
    // F-floor candidate — but we MUST (re)install the watcher after the new page settles.
    goto: async (...a) => { const r = await gotoWrapped(...a); await evalSafe(FLOW_WATCH); return r; },
    click: wrap('click', h.click),
    clickText: wrap('click', h.clickText),
    fill: wrap('fill', h.fill),
  };
  return { helpers, counters };
}

// The harness deliberately waits after each interaction so async render can settle (see
// makeHelpers: 800ms post-click, 2500ms post-goto). To get a HONEST Flow signal we subtract
// those known settle constants — an action is only "slow" if it took >400ms BEYOND the
// deliberate wait (a real Doherty-threshold breach, not the harness pacing itself).
const SETTLE = { hop: 2500, click: 800, fill: 0 };
const netMs = (a) => Math.max(0, a.ms - (SETTLE[a.type] || 0));

// Turn raw counters into the per-journey EFFORT + FLOW-seed record.
export function scoreEffort(counters, ideal) {
  const clickHops = counters.clicks + counters.hops;
  const slow = counters.actions.filter(a => netMs(a) > 400); // Doherty threshold, settle-adjusted (F-lens seed)
  // ── F lens (Flow / Doherty) — calibrated like the L lens (discriminating signal gated, noisy
  //    signal informational). Two Flow signals, by stability:
  //   • dead_ends (GATED)        — an interactive action that DIDN'T LAND (click/fill returned
  //                                false): the user is stuck, no path forward. DETERMINISTIC
  //                                (same elements present/absent each run vs seeded state), so it
  //                                ratchets cleanly → 0. This IS a Flow breach per our definition
  //                                ("…· dead-ends").
  //   • slow_silent (INFO only)  — slow (>400ms net) AND silent (busy===false: the watcher saw no
  //                                spinner/skeleton/disabled-submit). A real Doherty pain signal,
  //                                but TIMING-NOISY at the 400ms boundary (jitters ±3 run-to-run),
  //                                so — exactly like the L-lens raw `density` — it is tracked for
  //                                fix-TARGETING (ranks where to add a busy affordance) but NOT
  //                                gated; gating noise would cry wolf. busy===null = watcher absent
  //                                (pre-nav) → not judged. busy===true = feedback shown = Doherty-OK.
  const interactive = counters.actions.filter(a => a.type === 'click' || a.type === 'fill');
  const slowSilent = interactive.filter(a => a.ok && netMs(a) > 400 && a.busy === false);
  const deadEnds = interactive.filter(a => !a.ok); // a click/fill that didn't land = the user is stuck
  const out = {
    clicks: counters.clicks,
    fills: counters.fills,
    hops: counters.hops,
    steps: counters.steps,
    click_hops: clickHops,               // the primary "few clicks" metric
    interaction_cost: clickHops + counters.fills,
    net_latency_ms: Math.round(counters.actions.reduce((s, a) => s + netMs(a), 0)), // settle-adjusted
    slow_actions: slow.length,           // > Doherty 400ms, settle-adjusted (raw seed, incl. navigations)
    failed_actions: counters.actions.filter(a => !a.ok).length, // a click/fill/hop that didn't land = friction
    flow: {
      dead_ends: deadEnds.length,        // GATED Flow floor — deterministic, ratchets → 0
      flow_floor: deadEnds.length,       // the ratcheted F-floor (dead-ends only; slow_silent is INFO)
      slow_silent: slowSilent.length,    // INFORMATIONAL — Doherty slow+silent, ranks fix targets (noisy, not gated)
      slow_with_busy: interactive.filter(a => a.ok && netMs(a) > 400 && a.busy === true).length, // INFO — slow but feedback shown = Doherty-OK
    },
  };
  if (ideal && (ideal.clicks != null || ideal.hops != null)) {
    const idC = ideal.clicks ?? 0, idH = ideal.hops ?? 0;
    out.ideal = { clicks: idC, hops: idH };
    out.excess_clicks = Math.max(0, counters.clicks - idC);
    out.excess_hops = Math.max(0, counters.hops - idH);
    out.debt = out.excess_clicks + out.excess_hops; // excess-click DEBT — ratchets → 0
    out.pass = out.debt === 0;
  } else {
    out.ideal = null;
    out.debt = 0;
    out.pass = null; // ideal not defined yet → excluded from the Effort floor (honest)
  }
  return out;
}

// ─── L lens (Load / cognitive density) — an in-page DOM probe, run once per page ──────
// Measures cognitive load behaviorally (Cognitive Load Theory): how much the user must take
// in + decide on ONE screen. Serialized into the browser like the Critic detectors.
//   density          — visible interactive elements above the fold (the "how much at once")
//   max_choices      — the largest single choice-set (Hick's Law: decision time ∝ log(options))
//   miller_violations— choice-sets with >7 options shown at once (Miller's 7±2 working-memory)
//   competing_primary— >1 element styled as a primary CTA visible at once (split attention)
export const LOAD_PROBE = () => {
  // ANCESTOR-AWARE visibility: an element's OWN computed style can read "visible" while an ancestor
  // hides it (e.g. a `.modal-overlay { opacity:0; pointer-events:none }` — the child button's own
  // opacity is 1). checkVisibility() walks ancestors for opacity/visibility/display/content-visibility,
  // killing that false-positive (caught a phantom "competing primary" on skillmatrix's closed modals).
  const vis = (el) => { const b = el.getBoundingClientRect(); const s = getComputedStyle(el); if (!(b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && s.display !== 'none')) return false; return !el.checkVisibility || el.checkVisibility({ opacityProperty: true, visibilityProperty: true, contentVisibilityAuto: true }); };
  const aboveFold = (el) => { const b = el.getBoundingClientRect(); return b.top < (window.innerHeight || 800) && b.bottom > 0; };
  const inter = [...document.querySelectorAll('button,a[href],[role="button"],[onclick],input:not([type="hidden"]),select,textarea')].filter(vis);
  const density = inter.filter(aboveFold).length;
  // choice-sets: each <select> + each radio group + each visible pill/chip group. Miller's 7±2 is
  // about SIMULTANEOUS undifferentiated options; two real mitigations lower the EFFECTIVE decision
  // load and are credited here, so search-ifying/grouping a long dropdown CLEARS the violation (the
  // FIX registers, not just the option-count): (1) optgroup CHUNKING — the user scans group-by-group,
  // so the load is the largest group, not the flat total; (2) a SEARCHABLE combobox (typeahead) —
  // the user types to filter (O(1) recall, not O(n) scan) → exempt regardless of option count. (Inert
  // on the 2026-06-24 baseline: no live <select> is grouped/searchable yet, so load-floor stays 9.)
  const choiceSets = [];
  const isSearchable = (el) => el.hasAttribute('data-searchable') || el.getAttribute('role') === 'combobox' || el.hasAttribute('list') || (el.closest('[data-searchable],[data-combobox]') != null);
  for (const sel of document.querySelectorAll('select')) {
    if (!vis(sel) || isSearchable(sel)) continue;                  // searchable select (typeahead) → exempt
    const groups = sel.querySelectorAll('optgroup');
    if (groups.length >= 2) {                                      // chunked → effective load = largest group
      let largest = 0; for (const g of groups) largest = Math.max(largest, g.querySelectorAll('option').length);
      const ungrouped = [...sel.children].filter(c => c.tagName === 'OPTION').length; // loose options outside any group
      choiceSets.push(Math.max(largest, ungrouped));
    } else {
      choiceSets.push(sel.querySelectorAll('option').length);
    }
  }
  const radioGroups = {};
  for (const r of document.querySelectorAll('input[type="radio"]')) { if (vis(r)) radioGroups[r.name] = (radioGroups[r.name] || 0) + 1; }
  for (const n in radioGroups) choiceSets.push(radioGroups[n]);
  const maxChoices = choiceSets.length ? Math.max(...choiceSets) : 0;
  const millerViolations = choiceSets.filter(n => n > 7).length;
  // competing primaries: the platform's ACTUAL dominant-CTA class only (a broad [class*=primary]
  // / inline-background match over-counts — calibration lesson 2026-06-24). >1 above-fold = split attention.
  const primaries = [...document.querySelectorAll('.btn-primary')].filter(el => vis(el) && aboveFold(el));
  return { density, max_choices: maxChoices, choice_sets: choiceSets.length, miller_violations: millerViolations, competing_primary: primaries.length };
};

// Threshold the raw Load probe into a per-page L record + floor (ratchets → 0).
// CALIBRATION (2026-06-24): density>25 flagged 24/25 pages — a mobile dashboard legitimately
// shows 30+ controls, so density is NOT a floor, only an informational ranking signal. The
// floor gates the DISCRIMINATING, UX-law-grounded violations: Miller (>7-option choice-set =
// decision overload, Hick), a genuine "wall of controls" (>40 above-fold), and >1 primary CTA.
export function scoreLoad(raw) {
  const dense = raw.density > 40;
  return {
    ...raw,
    dense_screen: dense,
    load_floor: (raw.miller_violations || 0) + Math.max(0, (raw.competing_primary || 0) - 1) + (dense ? 1 : 0),
  };
}

// ─── C lens (Clarity / Jakob) — an in-page DOM probe, run once per page (like L) ──────────
// Measures whether the user can tell WHAT to do and HOW to recover (Jakob's Law = match
// conventions; Krug = don't-make-me-think). Built INFORMATIONAL first (v1, NOT gated): the
// signals over-flag on familiar verbs ("Save"/"Next" are clear in context), so — exactly like
// the L-lens raw density and the F-lens slow-silent — C is measured + ranked for fix-targeting,
// and a discriminating sub-signal is only promoted to a gate AFTER calibration. Signals:
//   vague_ctas       — buttons/links whose ENTIRE accessible label is a contextless verb
//                      (ok/submit/go/yes/click…): the user can't predict the outcome (Krug)
//   icon_only_unlabeled — an interactive control with NO text AND no aria-label/title: unguessable
//   competing_primary— >1 `.btn-primary` above the fold (which one do I press? — split attention)
//   error_affordances— count of inline error/validation containers present (recovery infra; a
//                      POSITIVE signal — its absence on a form-heavy page is the clarity risk)
export const CLARITY_PROBE = () => {
  // ancestor-aware visibility (see LOAD_PROBE) — excludes opacity:0/hidden-ancestor controls (closed modals).
  const vis = (el) => { const b = el.getBoundingClientRect(); const s = getComputedStyle(el); if (!(b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && s.display !== 'none')) return false; return !el.checkVisibility || el.checkVisibility({ opacityProperty: true, visibilityProperty: true, contentVisibilityAuto: true }); };
  const aboveFold = (el) => { const b = el.getBoundingClientRect(); return b.top < (window.innerHeight || 800) && b.bottom > 0; };
  const acc = (el) => (el.getAttribute('aria-label') || el.getAttribute('title') || (el.textContent || '').trim() || '').replace(/\s+/g, ' ').trim();
  // genuinely contextless tokens only — NOT next/back/save/close/continue/done (those are clear
  // Jakob conventions; flagging them would be the L-lens over-flag mistake).
  const GENERIC = new Set(['ok', 'submit', 'go', 'yes', 'no', 'click', 'click here', 'button', 'tap', 'select', '...', '…', '?', '!']);
  const ctas = [...document.querySelectorAll('button,.btn,a.btn,[role="button"]')].filter(vis);
  const vague = ctas.filter(el => GENERIC.has(acc(el).toLowerCase())).length;
  const iconOnly = ctas.filter(el => acc(el) === '').length;
  const primaries = [...document.querySelectorAll('.btn-primary')].filter(el => vis(el) && aboveFold(el)).length;
  const errAffordances = document.querySelectorAll('[role="alert"],.error,.field-error,.invalid-feedback,.form-error,[data-error]').length;
  return { vague_ctas: vague, icon_only_unlabeled: iconOnly, competing_primary: primaries, error_affordances: errAffordances };
};
// Threshold the raw Clarity probe into a per-page record. `clarity_signal` is the negative-signal
// sum (vague + unlabeled) used for RANKING fix targets — informational, NOT a gated floor (v1).
export function scoreClarity(raw) {
  return { ...raw, clarity_signal: (raw.vague_ctas || 0) + (raw.icon_only_unlabeled || 0) };
}

// Roll per-journey effort records into the program scoreboard numbers.
export function rollupEffort(records) {
  const ok = records.filter(r => !r.err);
  const sum = (k) => ok.reduce((s, r) => s + (r.effort[k] || 0), 0);
  const sumFlow = (k) => ok.reduce((s, r) => s + ((r.effort.flow && r.effort.flow[k]) || 0), 0);
  const withIdeal = ok.filter(r => r.effort.pass !== null);
  return {
    journeys: records.length,
    measured: ok.length,
    errored: records.length - ok.length,
    total_click_hops: sum('click_hops'),       // the whole-platform interaction-cost ceiling
    total_interaction_cost: sum('interaction_cost'),
    total_steps: sum('steps'),
    total_debt: sum('debt'),                   // excess vs ideals (where seeded)
    total_slow_actions: sum('slow_actions'),
    total_failed_actions: sum('failed_actions'),
    total_slow_silent: sumFlow('slow_silent'), // F lens: slow + no busy affordance
    total_dead_ends: sumFlow('dead_ends'),     // F lens: interactive action that failed
    total_flow_floor: sumFlow('flow_floor'),   // F lens floor (ratchets → 0)
    total_slow_with_busy: sumFlow('slow_with_busy'), // informational (slow but with feedback = OK)
    journeys_with_ideal: withIdeal.length,
    effort_pass: withIdeal.filter(r => r.effort.pass === true).length,
    effort_pct: withIdeal.length ? Math.round(1000 * withIdeal.filter(r => r.effort.pass === true).length / withIdeal.length) / 10 : null,
  };
}
