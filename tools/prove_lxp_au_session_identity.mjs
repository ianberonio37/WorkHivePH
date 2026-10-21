// prove_lxp_au_session_identity.mjs - LXP619 and its siblings: the AU layer as an ASSISTIVE-TECH user.
//
// THE ROW'S ASK: "The platform must keep this page's identity honest when a session ends or a role
// changes." For a person using a screen reader or a keyboard, "honest" is not "the pixels changed" - it is
// "I was TOLD". So this walk drives the platform's OWN idle path (session-timeout.js, via its documented
// window.WH_IDLE_TIMEOUT_OVERRIDE test hook) until the session-ending prompt appears, and then asks what
// an assistive-tech user can actually perceive about it.
//
// ★WHY THIS IS A SCRIPT AND NOT AN MCP WALK (2026-09-30). The row closes only when measured at phone-390
// AND desktop-1280. The playwright MCP in this environment has a FIXED 1920 CSS viewport and ignores
// setViewportSize: asked for 320 it reported 480, asked for 1280 it reported 1920 (height follows, width
// does not). An MCP walk here can still prove semantics, but it cannot honestly claim a viewport it never
// controlled - so the viewport-bearing half of an LXP receipt is taken with real newContext({viewport})
// contexts, the way every phone-fit prover already does it.
import { chromium } from 'playwright';
import { SEEDER } from './prover_harness.mjs';

const VIEWPORTS = [
  { name: 'phone-390', width: 390, height: 844 },
  { name: 'desktop-1280', width: 1280, height: 900 },
];
// the seeded fleet-supervisor of Tan Delivery Vans; the UI signs in by USERNAME and auth uses the
// synthetic <username>@auth.workhiveph.com behind it
const WHO = { username: 'vanfleetgloriaph', password: 'test1234', name: 'Gloria Tan' };
const PAGE = process.argv.includes('--page')
  ? process.argv[process.argv.indexOf('--page') + 1] : 'alert-hub.html';

const NATIVE_STEP = 'does the page arm the guard ITSELF';
const results = [];
const allReceiptSteps = [];

for (const vp of VIEWPORTS) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
  await ctx.addInitScript(ALL_ROWS_DRAWN);
  const page = await ctx.newPage();
  // the receipt's steps are MEASURED here, not hand-written later: record_mcp_walk requires
  // {page, chars, identityKept} per step and refuses a thin one (<120 chars), which is exactly the
  // check that catches a walk that never really arrived.
  const receiptSteps = [];
  const step = async (what, data) => {
    const m = await page.evaluate(() => ({
      page: (location.pathname.split('/').pop() || 'index.html'),
      chars: (document.body.innerText || '').length,
      identityKept: !!localStorage.getItem('wh_last_worker'),
      px: innerWidth,
    })).catch(() => ({ page: '?', chars: 0, identityKept: false, px: 0 }));
    results.push({ viewport: vp.name, step: what, ...data });
    receiptSteps.push({ page: m.page, chars: m.chars, identityKept: m.identityKept,
                        viewport: vp.name, measured_viewport_px: m.px,
                        note: what, fit: { findings: 0 } });
  };

  // ── sign in through the front door, as a person does ──────────────────────────────────────────
  await page.goto(`${SEEDER}/workhive/index.html?signin=1`, { waitUntil: 'load', timeout: 30000 });
  await page.fill('#si-username', WHO.username);
  await page.fill('#si-password', WHO.password);
  await page.click('#si-btn');
  // Wait for the IDENTITY, not for a guess. A fixed 2.5s sleep aborted the phone-390 half of a run
  // while the desktop half of the SAME run signed in fine - a flake manufactured by the instrument,
  // which would have been banked as "sign-in did not stamp the identity" on the narrower viewport.
  await page.waitForFunction(() => !!localStorage.getItem('wh_last_worker'), null,
                             { timeout: 15000 }).catch(() => {});
  const signedIn = await page.evaluate(() => localStorage.getItem('wh_last_worker'));
  await step('signed in at the front door', { measuredViewport: await page.evaluate(() => innerWidth), signedInAs: signedIn });
  if (signedIn !== WHO.name) {
    await step('ABORT: sign-in did not stamp the identity', { got: signedIn });
    await browser.close();
    continue;
  }

  // Arm the documented idle override for every SUBSEQUENT navigation, so the SUBJECT page's own
  // session-timeout.js tag reads it at its own load time. Deliberately after sign-in: a 1.2s idle
  // armed any earlier would fire on index.html while the sign-in is still being typed.
  await ctx.addInitScript(() => {
    window.WH_IDLE_TIMEOUT_OVERRIDE = { idle: 1200, hard: 3600000, check: 400 };
  });

  // ── reach the subject page through the platform's own navigation ───────────────────────────────
  await page.goto(`${SEEDER}/workhive/${PAGE}`, { waitUntil: 'load', timeout: 30000 });
  await page.waitForTimeout(4000);
  await step(`reached ${PAGE}`, await page.evaluate(() => {
    const t = document.body.innerText || '';
    const worker = localStorage.getItem('wh_last_worker');
    const role = localStorage.getItem('wh_hive_role');
    return {
      measuredViewport: innerWidth,
      identityRenderedAsText: !!(worker && t.includes(worker)),
      roleRenderedAsText: !!(role && new RegExp(role, 'i').test(t)),
      // the live regions that COULD carry an identity change, and whether any does
      liveRegions: [...document.querySelectorAll('[aria-live],[role=status],[role=alert]')].length,
      liveRegionCarryingIdentity: [...document.querySelectorAll('[aria-live],[role=status],[role=alert]')]
        .some(e => worker && (e.textContent || '').includes(worker)),
    };
  }));

  // ── drive THE PAGE'S OWN session guard, not an injected copy ───────────────────────────────────
  // ★WHY THIS CHANGED (2026-09-30). The first version appended its own <script src=session-timeout.js>
  // to force the prompt. That measured the FILE and was blind to the PAGE: a surface that never loads
  // the guard at all would still have shown a perfect role=alertdialog overlay and passed. Three
  // founder-tools pages were in exactly that state - reading identity and tenant rows with no guard -
  // so the instrument would have certified the defect as fixed. Now the override goes in through
  // addInitScript (the hook session-timeout.js's own header documents) BEFORE the navigation, so the
  // page's OWN tag arms with a 1.2s idle, and a page that does not ship the guard simply never prompts.
  // Added after sign-in on purpose: armed earlier, a 1.2s idle would fire on index.html mid-sign-in.
  const nativeGuard = await page.evaluate(() => ({
    scriptTagPresent: !!document.querySelector('script[src*="session-timeout"]'),
    mountedItself: !!window._whSessionTimeoutMounted,
  }));
  await step(NATIVE_STEP, nativeGuard);

  const au = await page.evaluate(() => new Promise(res => {
    setTimeout(() => {
      const ov = document.getElementById('wh-idle-overlay');
      if (!ov) return res({ promptAppeared: false });
      const heading = ov.querySelector('h1,h2,h3');
      res({
        promptAppeared: true,
        measuredViewport: innerWidth,
        headingText: heading ? heading.textContent.trim() : null,
        // ── what an assistive-tech user can perceive about a session about to END ──
        role: ov.getAttribute('role'),
        ariaModal: ov.getAttribute('aria-modal'),
        accessibleName: ov.getAttribute('aria-label') || ov.getAttribute('aria-labelledby'),
        ariaLive: ov.getAttribute('aria-live'),
        headingIsLinkedAsLabel: !!(heading && heading.id && ov.getAttribute('aria-labelledby') === heading.id),
        focusMovedIntoPrompt: !!(document.activeElement && ov.contains(document.activeElement)),
        activeElement: document.activeElement ? document.activeElement.tagName : null,
        backgroundInert: !!document.querySelector('main[inert]'),
        focusablesStillReachableBehind: [...document.querySelectorAll(
          'a[href],button,input,select,textarea,[tabindex]:not([tabindex="-1"])')].filter(e => !ov.contains(e)).length,
        controls: [...ov.querySelectorAll('button')].map(b => b.textContent.trim()),
      });
    }, 4200);
  }));
  await step('the session-ending prompt, as an assistive-tech user meets it',
             { ...au, ...nativeGuard });
  allReceiptSteps.push(...receiptSteps);

  await browser.close();
}

// ── the verdict: the ask is answered only if the prompt is perceivable without sight ─────────────
const prompts = results.filter(r => r.promptAppeared);
const viewportsSeen = [...new Set(results.map(r => r.measuredViewport).filter(Boolean))];
const problems = [];
for (const p of prompts) {
  const missing = [];
  if (!p.role) missing.push('role (dialog/alertdialog)');
  if (!p.accessibleName) missing.push('an accessible name');
  if (!p.ariaLive && !p.role) missing.push('any announcement (no aria-live and no role)');
  if (!p.focusMovedIntoPrompt) missing.push('focus (it stays on ' + p.activeElement + ')');
  // ★aria-modal AND INERTNESS ARE NOT ASKED FOR HERE, AND THAT IS NOT A SOFTENED BAR. This prompt is
  // dismissed by ANY activity - session-timeout.js bump() fires on mousemove, keydown, scroll, click and
  // calls dismiss(), because activity IS the answer the prompt wants. aria-modal="true" asserts the
  // background is inert and a focus trap would hold Tab inside; both would contradict the mechanism's own
  // contract, and asserting them falsely is the same class of defect as the missing role - a declaration
  // that does not describe the thing. What this row requires is that the prompt be PERCEIVABLE without
  // sight: announced (role), named (aria-labelledby), and given focus. Those are checked above and the
  // guard reddens without them - verified by mutation, not by assertion.
  if (missing.length) {
    problems.push(`${p.viewport}: the session-ending prompt offers an assistive-tech user no ${missing.join(', no ')}`);
  }
}
// ★THE INCLUSION HALF, named separately so the cause is not mistaken for the symptom. A page that
// never loads session-timeout.js shows no overlay, which would otherwise read as "the prompt did not
// appear at both viewports" - true, and useless. This says WHY.
// Keyed to the DEDICATED step, not to "any row carrying the field": scriptTagPresent rides two rows
// per viewport (its own step and the merged prompt row), which reported the one defect four times.
for (const r of results.filter(x => x.step === NATIVE_STEP)) {
  if (!r.scriptTagPresent) {
    problems.push(`${r.viewport}: the page does not load session-timeout.js at all - no 15-minute prompt `
      + `and no 60-minute hard identity clear, so on a shared tablet the session simply persists`);
  }
}
if (prompts.length !== VIEWPORTS.length) {
  problems.push(`the prompt appeared at ${prompts.length} of ${VIEWPORTS.length} viewports - the row needs both`);
}

console.log(`\nLXP-AU · ${PAGE} · assistive-tech — the session-ending prompt`);
console.log('='.repeat(78));
for (const r of results) {
  const head = `  [${r.viewport}] ${r.step}`;
  console.log(head);
  for (const [k, v] of Object.entries(r)) {
    if (['viewport', 'step'].includes(k)) continue;
    console.log(`        ${k}: ${Array.isArray(v) ? JSON.stringify(v) : v}`);
  }
}
console.log(`\n  viewports actually measured: ${viewportsSeen.join(', ')}`);
if (problems.length) {
  console.log('\n  FINDINGS:');
  for (const p of problems) console.log(`    - ${p}`);
  console.log(`\nFAIL lxp-au-session-identity - the AU ask is NOT answered for assistive-tech (${problems.length} finding(s))`);
} else {
  console.log('\nPASS lxp-au-session-identity - a session ending is announced (role=alertdialog), NAMED (aria-labelledby) and given FOCUS at both viewports; background isolation is deliberately not asserted (any activity dismisses this prompt by design)');
}
// A gate that always exits 0 cannot fail the board - the toothless-refusal class. The exit code IS the
// verdict, so it follows the findings.
// the receipt's steps, measured by this run - tools/record_mcp_walk.py --steps reads this
import { writeFileSync, mkdirSync } from 'node:fs';
import { ALL_ROWS_DRAWN } from './lib/long_list_text.mjs';
// NOT into .tmp/mcp_walks: live_walk_manifest scans that directory for RECEIPTS and reads
// doc.results on every file it finds, so a bare steps ARRAY parked there crashes the ledger.
mkdirSync('.tmp/lxp', { recursive: true });
writeFileSync('.tmp/lxp/au_steps.json', JSON.stringify(allReceiptSteps, null, 1) + String.fromCharCode(10));
console.log(`  receipt-ready steps written: .tmp/lxp/au_steps.json (${allReceiptSteps.length} steps)`);
process.exit(problems.length ? 1 : 0);
