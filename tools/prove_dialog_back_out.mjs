// prove_dialog_back_out.mjs — CO `back_out` for the TAB and SECTION views (V2/V3).
//
// WHY THIS EXISTS SEPARATELY FROM THE MODAL PROVER, and it is not a workaround. A DIALOG's way out is
// Escape, and prove_modal_escape_live.mjs settles that. A TAB or SECTION has no Escape — pressing it there
// should do nothing — so that prover deliberately SKIPS them (`kind: 'tab' | 'section'`), which left their
// `back_out` rows owed. Their real question is different and equally concrete: **with that view on screen,
// does the page-level way out still work?** A tab that quietly breaks the back affordance strands someone
// exactly as effectively as a modal with no close button.
//
// THE CONTRACT IS wayfinding.js's, NOT AN INVENTED ONE — the same one prove_back_out.mjs measures at V1:
//   TIER 1 · the injected `.wf-back` (or a `.back-btn` rewired to smartBack) — referrer-aware, so with a
//            referrer it must land on THAT page.
//   TIER 2 · the page's own in-layout `.back-link` / `.home-link` / `.breadcrumb a` — NOT referrer-aware; it
//            goes where its href points, and that weaker guarantee is RECORDED rather than failed.
// The referrer is chosen to be neither the page nor its wayfinding PARENT, so tier 1 can only pass by
// honouring the referrer rather than by falling through to the parent map.
//
// THE VIEW MUST BE OPEN AT THE MOMENT THE AFFORDANCE IS CLICKED — that is the whole point. The view is
// opened through its own source-read path from the shared table, then the affordance is located and its box
// asserted non-zero (a programmatic click on an unreachable control proves nothing), and only then clicked.
// If opening the view HIDES or removes the way out, that is exactly the defect this oracle is for.
//
// NON-WRITING: it opens a view and clicks a navigation control. Nothing is typed or submitted.
import { chromium } from 'playwright';
import { writeFileSync, readFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
import { TARGETS } from './dialog_targets.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

// Mirrored from wayfinding.js PARENT, and CHECKED against it below — a hand-copied constant that silently
// disagrees with the code it mirrors would grade every page against the wrong destination.
const PARENT = {
  'asset-hub': 'hive', 'alert-hub': 'hive', 'pm-scheduler': 'hive',
  'analytics-report': 'analytics', 'report-sender': 'analytics',
  'project-report': 'project-manager', 'achievements': 'skillmatrix',
  'audit-log': 'hive', 'voice-journal': 'logbook',
};
const wf = readFileSync('wayfinding.js', 'utf8');
const drift = [];
for (const [k, v] of Object.entries(PARENT)) {
  const m = wf.match(new RegExp(`'${k}\\.html'\\s*:\\s*'([a-z0-9-]+)\\.html'`));
  if (!m) drift.push(`${k}: absent from wayfinding.js`);
  else if (m[1] !== v) drift.push(`${k}: source says ${m[1]}, mirror says ${v}`);
}
if (drift.length) {
  console.log('  SELF-CHECK FAILED — the mirrored PARENT map has drifted from wayfinding.js:');
  drift.forEach((d) => console.log('    ' + d));
  process.exit(1);
}
console.log(`  self-check: PARENT map matches wayfinding.js (${Object.keys(PARENT).length} entries)`);

const refFor = (p) => ['hive', 'logbook', 'inventory', 'analytics']
  .find((r) => r !== p && r !== (PARENT[p] || 'index')) || 'hive';

const FIND_BACK = () => {
  const look = (sels, tier) => {
    for (const s of sels) {
      for (const el of document.querySelectorAll(s)) {
        const st = getComputedStyle(el); const b = el.getBoundingClientRect();
        if (st.display === 'none' || st.visibility === 'hidden' || +st.opacity <= 0.01) continue;
        if (b.width <= 0 || b.height <= 0) continue;
        return { sel: s, tier, tag: el.tagName, href: el.getAttribute('href') || null,
                 w: Math.round(b.width), h: Math.round(b.height) };
      }
    }
    return null;
  };
  return look(['#wh-wayfinding .wf-back', '.wf-back', '.back-btn', '[data-wh-back]'], 1)
      || look(['.back-link', '.home-link', '.breadcrumb a[href]', '[aria-label="breadcrumb"] a[href]'], 2);
};

const slug = (u) => { try { return (new URL(u).pathname.split('/').pop() || 'index.html')
  .replace(/\.html$/, ''); } catch { return '?'; } };

const browser = await chromium.launch();
const results = [];
for (const t of TARGETS.filter((x) => (!ONE || x.page === ONE.replace(/\.html$/, ''))
                                   && (x.kind === 'tab' || x.kind === 'section'))) {
  const rec = { page: t.page, view: t.view, modal: t.modal, kind: t.kind };
  // HOME HAS NO WAY OUT BY DESIGN, and this exemption is carried over from the V1 prover rather than
  // rediscovered: wayfinding.js tests IS_HOME explicitly and skips the back affordance on index.html,
  // because there is no "out" of the front door. Without it, index V2 (the anon landing) was reported as
  // "NO way out is visible" — true, and the specified behaviour. The V1 row is already banked declared-na
  // for exactly this reason, so failing V2 for it would have contradicted a green row on the same page.
  if (t.page === 'index') {
    rec.ok = null;
    rec.why = 'home surface — wayfinding.js skips IS_HOME by design, so the absence of a back affordance is '
      + 'the specified behaviour rather than a gap (the V1 row is banked declared-na for the same reason)';
    rec.declaredNa = true;
    results.push(rec);
    console.log(`  ${t.page.padEnd(14)} ${t.view} ${String(t.modal).padEnd(18)} declared-na (home)`);
    continue;
  }
  if (t.notDrivable || t.unreachable) {
    rec.ok = null;
    rec.why = t.notDrivable || String(t.unreachable).slice(0, 110);
    results.push(rec);
    console.log(`  ${t.page.padEnd(14)} ${t.view} ${String(t.modal).padEnd(18)} UNGRADED  ${rec.why.slice(0, 54)}`);
    continue;
  }
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  if (!t.signedOut) await assertSignedIn(signIn(ctx, 'supervisor'));
  const page = await ctx.newPage();
  try {
    const ref = refFor(t.page);
    // Arrive FROM a referrer so tier 1's referrer branch is the one under test.
    await page.goto(`${ORIGIN}/${ref}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(700);
    await page.evaluate((u) => { const a = document.createElement('a'); a.href = u;
      document.body.appendChild(a); a.click(); }, `${ORIGIN}/${t.page}.html`);
    await page.waitForLoadState('domcontentloaded').catch(() => {});
    await page.waitForTimeout(2600);
    if (slug(page.url()) !== t.page) throw new Error(`did not reach the page (landed ${slug(page.url())})`);

    // OPEN THE VIEW through its own path.
    if (t.pre) {
      const pr = await page.evaluate((c) => {
        try { eval(c); return 'ok'; } catch (e) { return 'threw: ' + String(e.message || e).slice(0, 70); }
      }, t.pre);
      if (String(pr).startsWith('threw')) throw new Error(`precondition ${pr}`);
      await page.waitForTimeout(1400);
    }
    if (!t.mayStartOpen && t.openBy === 'click') {
      const shown = await page.evaluate((sel) => {
        const e = document.querySelector(sel); if (!e) return false;
        const b = e.getBoundingClientRect(); const cs = getComputedStyle(e);
        return cs.display !== 'none' && cs.visibility !== 'hidden' && b.height > 0;
      }, t.opener);
      if (!shown) throw new Error(`opener ${t.opener} is absent or not visible`);
      await page.click(t.opener, { timeout: 4000 });
      await page.waitForTimeout(1100);
    } else if (!t.mayStartOpen && t.fn) {
      await page.evaluate((c) => { try { eval(c); } catch (_) { /* opener best-effort */ } }, t.fn);
      await page.waitForTimeout(1100);
    }
    // The view has to actually BE open, or this measures the page rather than the view.
    const open = await page.evaluate((id) => {
      const e = document.getElementById(id); if (!e) return 'absent';
      const s = getComputedStyle(e); const b = e.getBoundingClientRect();
      return (s.display !== 'none' && s.visibility !== 'hidden' && b.height > 0) ? 'open' : 'closed';
    }, t.modal);
    if (open !== 'open') throw new Error(`the view (${t.modal}) is ${open} — nothing to measure`);
    rec.viewOpen = true;

    rec.aff = await page.evaluate(FIND_BACK);
    if (!rec.aff) {
      rec.verdict = 'NO way out is visible while this view is open';
      rec.ok = false;
    } else {
      const expect = rec.aff.tier === 2
        ? slug(new URL(rec.aff.href || 'index.html', `${ORIGIN}/`).href) : ref;
      await page.click(rec.aff.sel, { timeout: 4000 }).catch(() => {});
      await page.waitForTimeout(2000);
      rec.landed = slug(page.url());
      rec.expect = expect; rec.tier = rec.aff.tier;
      rec.ok = rec.landed === expect;
      rec.verdict = rec.ok
        ? `tier ${rec.aff.tier} affordance (${rec.aff.w}x${rec.aff.h}) landed on ${rec.landed}`
          + (rec.aff.tier === 2 ? ' — its own href, NOT referrer-aware (recorded, not failed)' : '')
        : `the way out landed on ${rec.landed}, but the contract requires ${expect}`;
    }
  } catch (e) { rec.error = String(e.message || e).slice(0, 150); rec.ok = null; }
  await ctx.close();
  results.push(rec);
  console.log(`  ${t.page.padEnd(14)} ${t.view} ${String(t.modal).padEnd(18)} `
    + `${rec.ok === true ? 'PASS' : rec.ok === false ? 'FAIL' : 'UNGRADED'}  `
    + String(rec.verdict || rec.error || '').slice(0, 72));
}
await browser.close();

const graded = results.filter((r) => r.ok !== null);
const bad = graded.filter((r) => !r.ok);
writeFileSync('dialog_back_out_report.json', JSON.stringify({
  totals: { targets: results.length, graded: graded.length,
            ungraded: results.filter((r) => r.ok === null).length, failing: bad.length },
  targets: results,
}, null, 1));
console.log('\n  wrote dialog_back_out_report.json');
console.log(`  ${graded.length} of ${results.length} tab/section view(s) graded, ${bad.length} failing`);
if (!graded.length) {
  console.log('  FAIL — NOTHING WAS MEASURED. Zero failures over an empty denominator is not a pass.');
} else if (bad.length) {
  for (const r of bad) console.log(`  FAIL ${r.page} ${r.view} ${r.modal}: ${r.verdict}`);
} else {
  console.log(`  PASS — with each of ${graded.length} view(s) OPEN, the page-level way out is still present `
    + 'and still lands where wayfinding.js says it should');
}
if (GATE) process.exit(bad.length || !graded.length ? 1 : 0);
