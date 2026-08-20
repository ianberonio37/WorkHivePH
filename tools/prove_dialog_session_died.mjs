// prove_dialog_session_died.mjs — CO `session_died` for the V2/V3 views.
//
// V1 is settled by prove_session_died.mjs (does the PAGE present a dead session as signed-in data). This
// asks the same question one level in: with the session gone, what happens to the DIALOG, TAB or SECTION?
// It reuses the shared open-path table (tools/dialog_targets.mjs), so the views are the same ones the layout
// and a11y provers measure and there is no second list to drift.
//
// THREE HONEST OUTCOMES, and the first is the one most pages give — which is why it must be recognised as a
// PASS rather than mistaken for a failure to reach the view:
//   1. UNREACHABLE — the page redirects (or refuses) before the view can be opened at all. With no session
//      there is no view, so there is nothing to mislead anyone with. This is the correct behaviour and the
//      most common one; the V1 sweep already showed 10 of 22 pages redirect to index on a dead session.
//   2. OPENS AND EXPLAINS — the view opens but says something honest (a sign-in prompt that was not there
//      before, or an empty state that states its reason).
//   3. OPENS EMPTY WITH NO FIGURES — nothing on screen that could be mistaken for real data.
// The FAILURE is the fourth: the view opens and still shows values that survived the session, or bare zeros
// with no explanation, exactly as `feedback_a_zero_that_was_never_a_fallback` describes.
//
// THE SESSION IS KILLED IN localStorage, NOT COOKIES — supabase-js persists `sb-<ref>-auth-token` there, so
// clearCookies would leave the page signed in and the whole probe would measure nothing while reporting a
// pass. Every `sb-*` / auth-token / supabase key in both storages is swept rather than one hardcoded ref.
//
// THE SIGNED-IN READING IS THE CONTROL, taken first: a target whose view cannot be opened even WITH a
// session is UNGRADED, never passed — otherwise "unreachable" would be indistinguishable from "unreachable
// because the session is gone", which is the whole question.
//
// NON-WRITING: it opens a view, clears client-side storage in its own context, reloads and reads. Nothing is
// typed or submitted.
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
import { TARGETS } from './dialog_targets.mjs';
import { SIGNED_OUT_SRC, REASONED_EMPTY_SRC } from './session_signals.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

const KILL = () => {
  const killed = [];
  for (const store of [localStorage, sessionStorage]) {
    for (const k of Object.keys(store)) {
      if (/^sb-|auth-token|supabase/i.test(k)) { killed.push(k); store.removeItem(k); }
    }
  }
  return killed;
};

const READ_VIEW = ({ id, soSrc, reSrc }) => {
  // WIDENED after two FALSE findings. analytics explains itself clearly on a dead session —
  // #results-panel renders "Authentication required", the verdict reads "Analytics unavailable" —
  // and the first vocabulary recognised NEITHER, so the page was reported as silently empty when it
  // was arguably the most explicit page in the roster. An oracle that only accepts the phrasings its
  // author happened to think of measures the author, not the product.
  const SAYS_SIGNED_OUT = new RegExp(soSrc, 'i');
  const SAYS_REASONED_EMPTY = new RegExp(reSrc, 'i');
  const el = document.getElementById(id);
  const bodyTxt = (document.body.innerText || '').replace(/\s+/g, ' ').trim();
  if (!el) return { present: false, bodySaysSignedOut: SAYS_SIGNED_OUT.test(bodyTxt) };
  const s = getComputedStyle(el); const b = el.getBoundingClientRect();
  const visible = s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.01 && b.height > 0;
  const nums = [];
  for (const n of el.querySelectorAll('*')) {
    if (n.children.length) continue;
    const t = (n.textContent || '').trim();
    if (!/^[₱$]?\s*\d[\d,.]*\s*%?$/.test(t)) continue;
    const ns = getComputedStyle(n);
    if (ns.display === 'none' || ns.visibility === 'hidden') continue;
    nums.push({ t, cls: String(n.className || '').slice(0, 26) });
  }
  const txt = (el.innerText || '').replace(/\s+/g, ' ').trim();
  return { present: true, visible, chars: txt.length,
           nums: nums.length, nonZero: nums.filter((n) => /[1-9]/.test(n.t)).length,
           nonZeroSample: nums.filter((n) => /[1-9]/.test(n.t)).slice(0, 5)
             .map((n) => `${n.t}${n.cls ? ' .' + n.cls : ''}`),
           saysSignedOut: SAYS_SIGNED_OUT.test(txt), saysReasonedEmpty: SAYS_REASONED_EMPTY.test(txt),
           bodySaysSignedOut: SAYS_SIGNED_OUT.test(bodyTxt),
           hasAuthForm: !!document.querySelector('input[type="password"]') };
};

const browser = await chromium.launch();
const results = [];
for (const t of TARGETS.filter((x) => !ONE || x.page === ONE.replace(/\.html$/, ''))) {
  const rec = { page: t.page, view: t.view, modal: t.modal, kind: t.kind || 'dialog' };
  // A target that is already un-drivable WITH a session cannot answer this question either.
  if (t.notDrivable || t.unreachable || t.signedOut || t.inject || t.syntheticContent) {
    rec.ok = null;
    rec.why = t.syntheticContent
            ? 'this view is opened by a synthetic call whose ARGUMENTS become its content, so a value found '
              + 'in it after the kill is the input this probe supplied, not data that outlived the session '
              + '— it cannot answer this oracle'
            : t.signedOut ? 'this view is a SIGNED-OUT view by design, so "the session died" is not a '
                          + 'state change for it — the V1 row owns that question'
            : t.inject ? 'this view is reached by controlling the read, so a killed session is not the '
                       + 'variable under test here'
            : (t.notDrivable || String(t.unreachable).slice(0, 110));
    results.push(rec);
    console.log(`  ${t.page.padEnd(14)} ${t.view} ${String(t.modal).padEnd(18)} UNGRADED  ${rec.why.slice(0, 56)}`);
    continue;
  }
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const page = await ctx.newPage();
  try {
    const open = async () => {
      await page.goto(`${ORIGIN}/${t.page}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
      await page.waitForTimeout(2800);
      const landed = (page.url().split('/').pop() || '').replace(/\.html.*$/, '');
      if (landed !== t.page) return { landed };
      if (t.pre) {
        await page.evaluate((c) => { try { eval(c); } catch (_) { /* precondition best-effort */ } }, t.pre);
        await page.waitForTimeout(1400);
      }
      if (!t.mayStartOpen) {
        if (t.openBy === 'click') {
          const shown = await page.evaluate((sel) => {
            const e = document.querySelector(sel); if (!e) return false;
            const b = e.getBoundingClientRect(); const cs = getComputedStyle(e);
            return cs.display !== 'none' && cs.visibility !== 'hidden' && b.height > 0;
          }, t.opener);
          if (shown) await page.click(t.opener, { timeout: 4000 }).catch(() => {});
        } else if (t.fn) {
          await page.evaluate((c) => { try { eval(c); } catch (_) { /* opener best-effort */ } }, t.fn);
        }
        await page.waitForTimeout(1100);
      }
      return { landed };
    };

    // ── CONTROL: the view must be openable WITH a session, or this question cannot be asked.
    await open();
    rec.before = await page.evaluate(READ_VIEW, { id: t.modal, soSrc: SIGNED_OUT_SRC, reSrc: REASONED_EMPTY_SRC });
    if (!rec.before.present || !rec.before.visible) {
      throw new Error('the view could not be opened even WITH a session, so a dead-session reading would '
        + 'not be attributable to the missing session');
    }

    // ── kill and retry the same open path from cold
    rec.killedKeys = await page.evaluate(KILL);
    if (!rec.killedKeys.length) throw new Error('no session key found to remove');
    const { landed } = await open();
    rec.landedAfter = landed;
    rec.after = await page.evaluate(READ_VIEW, { id: t.modal, soSrc: SIGNED_OUT_SRC, reSrc: REASONED_EMPTY_SRC });

    const a = rec.after;
    if (landed !== t.page) {
      rec.verdict = `redirected-to-${landed}-before-the-view-could-open`; rec.ok = true;
    } else if (!a.present || !a.visible) {
      rec.verdict = 'the view does not open at all without a session'; rec.ok = true;
    } else if (a.hasAuthForm && !rec.before.hasAuthForm) {
      rec.verdict = 'opens, and renders a sign-in form it was not rendering before'; rec.ok = true;
    } else if (a.saysSignedOut && !rec.before.saysSignedOut) {
      rec.verdict = 'opens, and says signed-out in words that appeared after the kill'; rec.ok = true;
    } else if (a.bodySaysSignedOut && !rec.before.bodySaysSignedOut) {
      // THE EXPLANATION DOES NOT HAVE TO BE INSIDE THE VIEW. A section can be legitimately empty while the
      // PAGE around it says "sign in" — the person has been told, which is the thing the oracle is about.
      // Checking only the view's own text reported analytics V2/V3 as unexplained-empty while the page had
      // already changed to a signed-out state around them.
      rec.verdict = 'opens empty, and the PAGE says signed-out in words that appeared after the kill';
      rec.ok = true;
    } else if (a.nonZero > 0) {
      rec.verdict = `OPENS AND STILL SHOWS ${a.nonZero} non-zero value(s) with no session and no `
        + `explanation: ${a.nonZeroSample.join('; ')}`;
      rec.ok = false;
    } else if (a.saysReasonedEmpty) {
      rec.verdict = 'opens empty, with a stated reason'; rec.ok = true;
    } else if (rec.before.nonZero === 0) {
      rec.verdict = 'no figures WITH a session either, so this view has nothing a dead session could '
        + 'misrepresent — not gradable';
      rec.ok = null;
    } else {
      rec.verdict = `opens with ${a.nums} number(s), all zero/blank, and nothing saying the data could not `
        + 'be loaded';
      rec.ok = false;
    }
  } catch (e) { rec.error = String(e.message || e).slice(0, 160); rec.ok = null; }
  await ctx.close();
  results.push(rec);
  console.log(`  ${t.page.padEnd(14)} ${t.view} ${String(t.modal).padEnd(18)} `
    + `${rec.ok === true ? 'PASS' : rec.ok === false ? 'FAIL' : 'UNGRADED'}  `
    + String(rec.verdict || rec.error || '').slice(0, 74));
}
await browser.close();

const graded = results.filter((r) => r.ok !== null);
const bad = graded.filter((r) => !r.ok);
writeFileSync('dialog_session_died_report.json', JSON.stringify({
  totals: { targets: results.length, graded: graded.length,
            ungraded: results.filter((r) => r.ok === null).length, failing: bad.length },
  targets: results,
}, null, 1));
console.log('\n  wrote dialog_session_died_report.json');
console.log(`  ${graded.length} of ${results.length} view(s) graded, ${bad.length} failing`);
if (!graded.length) {
  console.log('  FAIL — NOTHING WAS MEASURED. Zero failures over an empty denominator is not a pass.');
} else if (bad.length) {
  for (const r of bad) console.log(`  FAIL ${r.page} ${r.view} ${r.modal}: ${r.verdict}`);
} else {
  console.log(`  PASS — ${graded.length} view(s) measured; none opens and presents a dead session as real `
    + 'data (unreachable-without-a-session counts, and is the honest answer most pages give)');
}
if (GATE) process.exit(bad.length || !graded.length ? 1 : 0);
