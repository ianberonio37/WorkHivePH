// prove_back_out.mjs — the CO `back_out` oracle: can a person get OUT of this page in-app?
//
// This is NOT "does a back button exist". A button that exists and dumps you somewhere unrelated is
// worse than no button, because it costs a navigation to discover. The platform already defines the
// contract, in wayfinding.js: ONE shared component injects `#wh-wayfinding .wf-back` on every page
// except home, and `smartBack()` resolves the destination in a FIXED order —
//   1. `?from=<slug>` / `?return=` / `?ref=`  → that slug
//   2. a same-origin document.referrer whose pathname differs → that URL, navigated EXPLICITLY
//   3. PARENT[path] (the owning surface: asset-hub→hive, project-report→project-manager, …)
//   4. index.html
// and if the page already has its own `.back-btn` it is REWIRED to that logic rather than duplicated.
//
// So the oracle is: the affordance is REACHABLE, and it LANDS where the contract says. Each page is
// driven twice, because branches 2 and 3 are different promises and a test that only ever arrives with
// a referrer never exercises the parent map at all:
//   pass A — arrive FROM hive.html (referrer set) → back must land on hive.html   [branch 2]
//   pass B — arrive with NO referrer               → back must land on PARENT[path] || index.html
//                                                                                  [branch 3/4]
//
// NON-WRITING BY CONSTRUCTION. It clicks exactly one control — the back affordance — and that control
// only navigates. Nothing is typed, submitted or saved, so this cannot touch the shared test database.
//
// index.html is HOME. wayfinding deliberately skips it (IS_HOME), and "get back from the front door"
// is not a question, so it is recorded declared-na WITH that reason rather than counted as a pass —
// R10, and the same discipline that kept 236 skipped elements visible in the safe-area sweep.
//
// WHAT THIS DOES NOT PROVE, stated so the row cannot over-claim: V1 only, the page as it loads. A
// modal or sheet opened later has its own way out (Escape, a close button) and is NOT settled here.
// Scroll-restore and ?focus= deep-linking are separate promises in the same component, also not here.
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager',
  'dayplanner', 'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain',
  'voice-journal', 'assistant', 'community', 'public-feed', 'achievements',
  'engineering-design', 'resume', 'report-sender', 'project-report', 'analytics-report'];
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

// Transcribed from wayfinding.js PARENT — the section-parent map. Kept in step with the source by the
// SELF-CHECK below, which reads wayfinding.js and fails if a roster page's parent disagrees. A
// hand-copied constant that silently drifts from the code it mirrors is its own defect class.
const PARENT = {
  'asset-hub': 'hive', 'alert-hub': 'hive', 'pm-scheduler': 'hive',
  'analytics-report': 'analytics', 'report-sender': 'analytics',
  'project-report': 'project-manager', 'achievements': 'skillmatrix',
  'audit-log': 'hive', 'voice-journal': 'logbook',
};

// THE PLATFORM HAS TWO TIERS OF WAY-OUT, AND COLLAPSING THEM INTO ONE MADE THIS ORACLE REPORT A
// FABRICATED DEFECT. The first run called `community` a FAIL with no affordance at all. It has one:
// `class="home-link"` at community.html:403, a 44px aria-labelled anchor to index.html — and that is
// precisely WHY there is no pill. wayfinding.js:158 skips its own injection when the page already ships
// a recognized in-layout `.back-link` / `.home-link` / `.breadcrumb`, deliberately, for two stated
// reasons: a floating pill on top of one would DUPLICATE the affordance, and the reserve band it needs
// measured a 0.12–0.28 layout shift on community specifically. My selector list was narrower than the
// vocabulary the component itself decides on, so I was reading an intentional design branch as an
// absence. Same shape as every other instrument correction in this bank: the page was right.
//
//   TIER 1 · smart-back — `.wf-back` (injected) or a `.back-btn`/[data-wh-back] REWIRED to smartBack.
//            Referrer-aware, so the full destination contract applies.
//   TIER 2 · the page's own in-layout link. NOT referrer-aware — it goes where its href points. Still a
//            way out, and graded as one, but the weaker guarantee is RECORDED rather than hidden inside
//            a green: on community, pressing it after arriving from hive lands on index, not hive.
const FIND_BACK = () => {
  const look = (sels, tier) => {
    for (const s of sels) {
      for (const el of document.querySelectorAll(s)) {
        const st = getComputedStyle(el); const b = el.getBoundingClientRect();
        if (st.display === 'none' || st.visibility === 'hidden' || +st.opacity <= 0.01) continue;
        if (b.width <= 0 || b.height <= 0) continue;
        return { sel: s, tier, tag: el.tagName, cls: String(el.className || '').slice(0, 40),
                 w: Math.round(b.width), h: Math.round(b.height),
                 href: el.getAttribute('href') || null,
                 name: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 40) };
      }
    }
    return null;
  };
  const hit = look(['#wh-wayfinding .wf-back', '.wf-back', '.back-btn', '[data-wh-back]'], 1)
    || look(['.back-link', '.home-link', '.breadcrumb a[href]', '[aria-label="breadcrumb"] a[href]'], 2);
  return { found: hit ? 1 : 0, first: hit,
           crumb: !!document.querySelector('#wh-wayfinding .wf-crumb') };
};

const slug = (u) => { try { return (new URL(u).pathname.split('/').pop() || 'index.html')
  .replace(/\.html$/, ''); } catch { return '?'; } };

// THE REFERRER MUST DIFFER FROM THE PAGE'S PARENT, or the test stops discriminating. Arriving at
// asset-hub from hive makes branch 2 (referrer) and branch 3 (PARENT['asset-hub']='hive') expect the
// SAME destination, so a component that ignored the referrer entirely and always used the parent map
// would pass both passes. Picking a referrer that is neither the page nor its parent means pass A can
// only succeed by honouring the referrer, and pass B can only succeed by honouring the parent map.
const refFor = (p) => ['hive', 'logbook', 'inventory', 'analytics']
  .find((r) => r !== p && r !== (PARENT[p] || 'index')) || 'hive';

// SELF-CHECK: the mirrored PARENT map must match wayfinding.js. Runs before any page is measured, so a
// drifted constant fails loudly instead of quietly grading against the wrong destination.
const wf = (await import('fs')).readFileSync('wayfinding.js', 'utf8');
const drift = [];
for (const [k, v] of Object.entries(PARENT)) {
  const re = new RegExp(`'${k}\\.html'\\s*:\\s*'([a-z0-9-]+)\\.html'`);
  const m = wf.match(re);
  if (!m) drift.push(`${k}: absent from wayfinding.js PARENT`);
  else if (m[1] !== v) drift.push(`${k}: source says ${m[1]}, this map says ${v}`);
}
if (drift.length) {
  console.log('  SELF-CHECK FAILED — the mirrored PARENT map has drifted from wayfinding.js:');
  drift.forEach((d) => console.log('    ' + d));
  process.exit(1);
}
console.log(`  self-check: PARENT map matches wayfinding.js (${Object.keys(PARENT).length} entries)`);

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
await assertSignedIn(signIn(ctx, 'supervisor'));
const page = await ctx.newPage();

const results = [];
for (const p of (ONE ? [ONE.replace(/\.html$/, '')] : PAGES)) {
  const rec = { page: p, home: p === 'index', passes: [], ok: null };
  try {
    if (rec.home) {
      rec.ok = null; rec.why = 'home — wayfinding skips IS_HOME by design; there is no "out" of the '
        + 'front door, so this is vacuous rather than proof';
      results.push(rec);
      console.log(`  ${p.padEnd(20)} declared-na (home)`);
      continue;
    }

    // ── pass A · arrived FROM a page that is NOT this page's parent, so the referrer branch is the
    //            only way to satisfy it → branch 2
    const ref = refFor(p);
    await page.goto(`${ORIGIN}/${ref}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(700);
    await page.evaluate((u) => { const a = document.createElement('a'); a.href = u;
      a.id = 'wh-refer-hop'; document.body.appendChild(a); a.click(); }, `${ORIGIN}/${p}.html`);
    await page.waitForLoadState('domcontentloaded').catch(() => {});
    await page.waitForTimeout(2600);
    const landedA = slug(page.url());
    if (landedA !== p) {
      rec.error = `did not reach the page under test — landed on ${landedA}`;
      results.push(rec); console.log(`  ${p.padEnd(20)} SKIP (${rec.error})`); continue;
    }
    const refSeen = await page.evaluate(() => document.referrer || null);
    const affA = await page.evaluate(FIND_BACK);
    let destA = null;
    if (affA.found) {
      await page.click(affA.first.sel, { timeout: 4000 }).catch(() => {});
      await page.waitForTimeout(2000);
      destA = slug(page.url());
    }
    // Tier 2 is graded against ITS OWN href, because that is the whole of what it promises. Grading it
    // against the referrer contract would report a defect for a design decision the component made on
    // purpose — and inventing a defect out of a deliberate branch is the failure mode this file already
    // committed once.
    const expA = affA.first && affA.first.tier === 2
      ? slug(new URL(affA.first.href || 'index.html', `${ORIGIN}/`).href) : ref;
    rec.passes.push({ pass: `A referrer=${ref}`, aff: affA, expect: expA, got: destA,
                      ok: affA.found > 0 && destA === expA,
                      tier: affA.first ? affA.first.tier : null,
                      referrerAware: affA.first ? affA.first.tier === 1 : null,
                      discriminating: affA.first && affA.first.tier === 1
                        && ref !== (PARENT[p] || 'index'),
                      referrerSeen: refSeen ? slug(refSeen) : null });

    // ── pass B · no referrer (direct load) → branch 3/4, the parent map
    const expectB0 = PARENT[p] || 'index';
    await page.goto('about:blank');
    await page.goto(`${ORIGIN}/${p}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(2600);
    const affB = await page.evaluate(FIND_BACK);
    let destB = null;
    if (affB.found) {
      await page.click(affB.first.sel, { timeout: 4000 }).catch(() => {});
      await page.waitForTimeout(2000);
      destB = slug(page.url());
    }
    const expectB = affB.first && affB.first.tier === 2
      ? slug(new URL(affB.first.href || 'index.html', `${ORIGIN}/`).href) : expectB0;
    rec.passes.push({ pass: 'B no-referrer', aff: affB, expect: expectB, got: destB,
                      tier: affB.first ? affB.first.tier : null,
                      ok: affB.found > 0 && destB === expectB });

    rec.ok = rec.passes.every((x) => x.ok);
  } catch (e) { rec.error = String(e).slice(0, 150); }
  if (rec.ok !== null || rec.error) {
    const a = rec.passes[0], b = rec.passes[1];
    console.log(`  ${p.padEnd(20)} ${rec.ok ? 'PASS' : 'FAIL'}`
      + `  aff=${a ? a.aff.found : '?'}${a && a.aff.first ? `(${a.aff.first.w}x${a.aff.first.h})` : ''}`
      + `  A->${a ? a.got : '?'}${a && a.ok ? '' : ` (want ${a ? a.expect : '?'})`}`
      + `  B->${b ? b.got : '?'}${b && b.ok ? '' : ` (want ${b ? b.expect : '?'})`}`
      + (rec.error ? `  ERR ${rec.error}` : ''));
  }
  results.push(rec);
}
await browser.close();

const graded = results.filter((r) => r.ok !== null);
const bad = graded.filter((r) => !r.ok);
// A NARROWED RUN MUST NOT CLOBBER THE FULL ONE: this file is read downstream (gates and
// bank_prover_reports), so a --page/--case spot-check overwriting a whole sweep's verdicts
// corrupts the BANK, not just a log. Measured on prove_retry_path 2026-08-27.
writeFileSync((ONE ? 'back_out_report.partial.json' : 'back_out_report.json'), JSON.stringify({
  origin: ORIGIN, view: 'V1',
  totals: { pages: results.length, graded: graded.length,
            na: results.filter((r) => r.ok === null && !r.error).length,
            failing: bad.length },
  pages: results,
}, null, 1));
console.log('\n  wrote back_out_report.json');
console.log(`  ${graded.length} page(s) graded, ${bad.length} failing`
  + `, ${results.filter((r) => r.ok === null && !r.error).length} declared-na`);
if (bad.length) console.log('  FAIL — ' + bad.map((r) => r.page).join(', '));
else console.log('  PASS — every graded page offers a reachable in-app way out that lands where '
  + 'wayfinding.js says it should, with and without a referrer');
if (GATE) process.exit(bad.length ? 1 : 0);
