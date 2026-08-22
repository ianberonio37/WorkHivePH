// view_pass.mjs — the SHARED V2/V3 view-opening harness for the page-bank provers.
//
// WHY THIS EXISTS (2026-08-22). 728 view-scoped bank rows sit stale because most provers grade V1
// only: each family that learned views so far (a11y_states, session_expiry_read, failure_injection)
// re-implemented the same open-the-view dance around tools/dialog_targets.mjs, and every port
// re-learned the same traps. This file is the dance, once:
//
//   - REACH THE VIEW FIRST, THEN INDUCE. For a non-default view the read/write under test is the
//     one the view issues when it OPENS or is DRIVEN - inducing up front measures "the view never
//     opened", which is not what any family's oracle asks (session_expiry_read's deferral, kept).
//   - The `pre` snippet is a PRECONDITION: its failure is UNGRADED, never a page defect.
//   - openBy 'fn' means focus-at-open is <body>; callers must not assert focus-restore there.
//   - `unreachable` / `notDrivable` entries stay in the DENOMINATOR as named abstentions - dropping
//     them is the silent-scope-claim class.
//
// USAGE (per family):
//   import { viewTargets, openView } from './view_pass.mjs';
//   for (const t of viewTargets(pageName)) {
//     const opened = await openView(page, t);       // { ok, why, focusAssertable }
//     if (!opened.ok) { record UNGRADED/abstain with opened.why; continue; }
//     ...install the family's induction, drive, read, judge...
//   }
import { TARGETS } from './dialog_targets.mjs';

export function viewTargets(page, view) {
  return TARGETS.filter((t) => t.page === page && (!view || t.view === view));
}

// Open one target's view on a live page. Returns:
//   { ok: true,  focusAssertable, target }                  - the view is up, induce away
//   { ok: false, kind: 'abstain'|'precondition'|'error', why }
export async function openView(p, t, opts) {
  const settle = (opts && opts.settleMs) || 1800;
  if (t.unreachable) {
    return { ok: false, kind: 'abstain', why: `unreachable BY SOURCE: ${t.ref || t.unreachable}` };
  }
  if (t.notDrivable) {
    return { ok: false, kind: 'abstain', why: `no read-only path in (notDrivable): ${t.ref || ''}` };
  }
  try {
    if (t.pre) {
      // A precondition that throws is a fact about the page's current DATA, not a defect.
      const pre = await p.evaluate((src) => {
        try { eval(src); return { ok: true }; }
        catch (e) { return { ok: false, why: String(e.message || e).slice(0, 140) }; }
      }, t.pre);
      if (!pre.ok) return { ok: false, kind: 'precondition', why: pre.why };
      await p.waitForTimeout(1200);
    }
    if (t.mayStartOpen) {
      const already = await p.evaluate((sel) => {
        const el = document.getElementById(sel) || document.querySelector(`#${CSS.escape(sel)}, .${CSS.escape(sel)}`);
        return !!el && el.getBoundingClientRect().width > 0;
      }, t.modal).catch(() => false);
      if (already) return { ok: true, focusAssertable: false, target: t };
    }
    if (t.openBy === 'click') {
      const loc = p.locator(`${t.opener}:visible`).first();
      const n = await loc.count().catch(() => 0);
      if (!n) {
        // fall back to a synthetic click on the (possibly hidden-styled) opener before abstaining
        const clicked = await p.evaluate((sel) => {
          const el = document.querySelector(sel);
          if (!el) return false;
          el.click(); return true;
        }, t.opener);
        if (!clicked) return { ok: false, kind: 'precondition', why: `opener ${t.opener} not present` };
      } else {
        await loc.click().catch(() => {});
      }
    } else if (t.openBy === 'fn') {
      // The fn field is a CALL EXPRESSION ("openSheet()", "openModal('lesson-modal')", even a
      // two-statement marketplace opener) - it must be EVALUATED, exactly as `pre` is. The first
      // cut resolved it as a dotted property path, so window["openSheet()"] was undefined and
      // EVERY fn-opened target in every view family abstained as "not on window" when the only
      // page-scoped symbol involved was the probe's own resolver.
      const ran = await p.evaluate((src) => {
        try { eval(src); return { ok: true }; }
        catch (e) { return { ok: false, why: String(e.message || e).slice(0, 100) }; }
      }, t.fn);
      if (!ran.ok) return { ok: false, kind: 'precondition', why: `opener fn ${t.fn} threw: ${ran.why} (page-scoped symbols defeat probes)` };
    }
    await p.waitForTimeout(settle);
    const up = await p.evaluate((sel) => {
      const el = document.getElementById(sel) || document.querySelector(`.${CSS.escape(sel)}`);
      if (!el) return false;
      // PAINTED VISIBILITY NEEDS ALL THREE TERMS plus the class signal (2026-08-22): sheets on this
      // platform hide by opacity/translate with width intact, and toggle a `.open` class - a
      // width+display check reads a closed sheet as open and (mid-transition) an open one as closed.
      if (el.classList.contains('open')) return true;
      const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
      // Viewport intersection is owed only by FIXED overlays: a translate-hidden sheet parks
      // itself off-viewport (that IS its closed state), but an in-flow tab container below the
      // fold (dayplanner's calendar-wrap, analytics' results panel) is open and merely scrolled -
      // requiring intersection of those manufactured three precondition abstains in one run.
      const inViewport = r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth;
      if (cs.position === 'fixed' && !inViewport) return false;
      return r.width > 0 && cs.display !== 'none' && cs.visibility !== 'hidden'
        && Number(cs.opacity) > 0.05;
    }, t.modal).catch(() => false);
    if (!up) return { ok: false, kind: 'precondition', why: `view ${t.modal} did not become visible after the open` };
    return { ok: true, focusAssertable: t.openBy === 'click', target: t };
  } catch (e) {
    return { ok: false, kind: 'error', why: String(e.message || e).slice(0, 150) };
  }
}
