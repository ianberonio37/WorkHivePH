// prove_lxp_d_provenance.mjs — LXP-D x assistive-tech: can a person who cannot SEE the screen learn
// where this page's data came from and what wrote it last?
//
// THE ROW'S ASK: "The platform must be able to show where this page's data came from and what wrote it
// last." For a sighted reader that is a grey line under the figures. For a screen-reader user it only
// exists if it is IN THE ACCESSIBILITY TREE, carries a role that says what it is, and says BOTH halves -
// the SOURCE and the RECENCY. A chip that renders beautifully inside an aria-hidden wrapper, or that
// reads "Live" with no source, answers the ask for one person and not the other.
//
// ★WHY THIS IS A SCRIPT AND NOT AN MCP WALK, and why BOTH viewports. The row closes only when measured
// at phone-390 AND desktop-1280, and the playwright MCP in this environment has a FIXED 1920 CSS
// viewport that ignores setViewportSize (asked 320 it reported 480, asked 1280 it reported 1920). So the
// viewport-bearing half is taken with real newContext({viewport}) contexts, the way every phone-fit
// prover already does it.
//
// ★WHAT IT DOES NOT DO, said plainly. It does not judge whether the provenance is TRUE - that is
// validate_source_chip_freshness's job (a saved copy must not claim to be live) and canonical_status.py's
// (a chip must name views the page actually reads). This measures only whether the claim REACHES someone
// who cannot see it. Overlapping instruments that each own one property beat one that owns none.
//
// Shared chrome is graded ONCE: renderSourceChip is the platform's provenance renderer and its semantics
// are asserted statically by validate_source_chip_freshness clause 2. What is PAGE-SPECIFIC, and so what
// this walk measures, is whether a given surface renders provenance at all and whether its own copy is
// reachable - which is exactly where the three unannounced chips were found.
import { chromium } from 'playwright';
import { SEEDER } from './prover_harness.mjs';

const VIEWPORTS = [
  { name: 'phone-390', width: 390, height: 844 },
  { name: 'desktop-1280', width: 1280, height: 900 },
];
const WHO = { username: 'bryangarcia', password: 'test1234', real: 'Bryan Garcia' };
const PAGE = process.argv.includes('--page')
  ? process.argv[process.argv.indexOf('--page') + 1] : 'achievements.html';

const results = [];
const problems = [];
const notes = [];

// Measured INSIDE the page: what a screen reader can actually reach.
const PROBE = () => {
  const vis = (el) => {
    if (!el.checkVisibility) return true;
    return el.checkVisibility({ visibilityProperty: true, contentVisibilityAuto: true,
                                opacityProperty: true });
  };
  const hidden = (el) => {
    for (let n = el; n; n = n.parentElement) {
      if (n.getAttribute && n.getAttribute('aria-hidden') === 'true') return true;
      if (n.hasAttribute && n.hasAttribute('inert')) return true;
    }
    return false;
  };
  // Every candidate provenance surface: the platform's chip, a freshness footer, and anything whose own
  // text makes a provenance claim. Cast wide on purpose - a page that rolls its own must still count.
  const sel = '.wh-source-chip, [data-wh-fresh], .wh-freshness, [class*="freshness"], [class*="source-chip"]';
  const chips = [...document.querySelectorAll(sel)];
  const CLAIM = /based on|source|updated|refreshed|as of|live|cached|saved copy|snapshot|last\s+\w+\s+ago|\bago\b/i;
  const loose = [...document.querySelectorAll('p, span, div, footer, small')]
    .filter((e) => e.children.length === 0 && CLAIM.test(e.textContent || ''))
    .filter((e) => !chips.includes(e));

  const describe = (e) => ({
    text: (e.textContent || '').trim().slice(0, 160),
    cls: (e.className || '').toString().slice(0, 60),
    role: e.getAttribute('role') || null,
    ariaLive: e.getAttribute('aria-live') || null,
    reachable: vis(e) && !hidden(e),
    visible: vis(e),
    ariaHiddenAncestor: hidden(e),
  });

  const all = [...chips.map(describe), ...loose.map(describe)];
  const reach = all.filter((c) => c.reachable);
  const txt = reach.map((c) => c.text).join(' | ');
  return {
    chipCount: chips.length,
    looseCount: loose.length,
    reachableCount: reach.length,
    announced: reach.filter((c) => c.role === 'status' || c.ariaLive).length,
    // BOTH HALVES of the ask: where it came from, and when it last changed.
    saysSource: /based on|source|from your|from the/i.test(txt),
    // ★AN ORACLE'S VOCABULARY IS PART OF THE ORACLE (fixed on the first run, 2026-10-05). The first list
    // was updated|refreshed|as of|live|ago|cached|saved copy|snapshot, and analytics.html at phone-390 says
    // "Recomputed just now · Based on your logbook · last 90 days" - which states the recency perfectly and
    // matched none of those words. The prover reported a defect that was its own blind spot. These are the
    // phrasings this platform actually ships (grep renderSourceChip + _whFreshnessPhrase): a page is free to
    // say "recomputed", "computed", "generated" or "just now" instead of "updated".
    saysRecency: /updated|refreshed|recomputed|recompute|computed|generated|synced|as of|live|\bago\b|just now|moments ago|cached|saved copy|snapshot|today/i.test(txt),
    samples: reach.slice(0, 3).map((c) => c.text),
    hiddenButRendered: all.filter((c) => c.visible && c.ariaHiddenAncestor).length,
    renderedButInvisible: all.filter((c) => !c.visible).length,
  };
};

for (const vp of VIEWPORTS) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
  const page = await ctx.newPage();

  await page.goto(`${SEEDER}/workhive/index.html?signin=1`, { waitUntil: 'load', timeout: 30000 });
  await page.fill('#si-username', WHO.username);
  await page.fill('#si-password', WHO.password);
  await page.click('#si-btn');
  // Wait for the IDENTITY, never a fixed sleep: a 2.5s guess aborted the phone half of an earlier
  // prover's run while the desktop half of the SAME run signed in fine.
  await page.waitForFunction(() => !!localStorage.getItem('wh_last_worker'), null, { timeout: 15000 })
            .catch(() => {});
  const signedIn = await page.evaluate(() => localStorage.getItem('wh_last_worker'));
  if (signedIn !== WHO.real) {
    problems.push(`${vp.name}: sign-in stamped "${signedIn}", expected "${WHO.real}" - the walk never arrived`);
    await browser.close();
    continue;
  }

  await page.goto(`${SEEDER}/workhive/${PAGE}`, { waitUntil: 'load', timeout: 45000 });
  // Provenance is painted when the DATA lands, not at first paint, so settle rather than sleep once.
  let prev = null, reading = null;
  for (let i = 0; i < 14; i++) {
    await page.waitForTimeout(1000);
    reading = await page.evaluate(PROBE);
    if (prev && prev.reachableCount === reading.reachableCount && reading.reachableCount > 0) break;
    prev = reading;
  }
  const px = await page.evaluate(() => innerWidth);
  results.push({ viewport: vp.name, measured_viewport_px: px, ...reading });
  await browser.close();
}

for (const r of results) {
  if (r.reachableCount === 0) {
    problems.push(`${r.viewport}: NO provenance reaches the accessibility tree. ${r.chipCount} chip(s) and `
      + `${r.looseCount} claim-shaped line(s) exist in the DOM, of which ${r.hiddenButRendered} are visible `
      + `but inside an aria-hidden/inert ancestor and ${r.renderedButInvisible} are not rendered at all - so `
      + `a sighted reader may see where the figures came from while a screen-reader user cannot`);
    continue;
  }
  if (r.announced === 0) {
    problems.push(`${r.viewport}: provenance is reachable but ANNOUNCED by nothing - no role=status and no `
      + `aria-live on any of the ${r.reachableCount} reachable line(s). It is readable only by someone who `
      + `goes looking for it, and a page that REPAINTS it (a refresh, a period change) tells them nothing`);
  }
  if (!r.saysSource) {
    problems.push(`${r.viewport}: the provenance never says WHERE the data came from - no "based on" / `
      + `"source" phrasing in: ${JSON.stringify(r.samples)}`);
  }
  if (!r.saysRecency) {
    problems.push(`${r.viewport}: the provenance never says WHEN it last changed - no "updated" / "as of" / `
      + `"live" / "ago" in: ${JSON.stringify(r.samples)}`);
  }
}
if (results.length !== VIEWPORTS.length) {
  problems.push(`measured ${results.length} of ${VIEWPORTS.length} viewports - the row needs both`);
}

console.log(`\nLXP-D · ${PAGE} · assistive-tech — where did this page's data come from?`);
console.log('='.repeat(78));
for (const r of results) {
  console.log(`  [${r.viewport} @ ${r.measured_viewport_px}px]`);
  console.log(`      chips=${r.chipCount} loose=${r.looseCount} reachable=${r.reachableCount} `
            + `announced=${r.announced} source=${r.saysSource} recency=${r.saysRecency}`);
  if (r.hiddenButRendered) console.log(`      visible but aria-hidden/inert: ${r.hiddenButRendered}`);
  for (const t of r.samples) console.log(`      · ${t}`);
}
for (const n of notes) console.log(`  ${n}`);
if (problems.length) {
  console.log('\n  FINDINGS:');
  for (const p of problems) console.log(`    - ${p}`);
  console.log(`\nFAIL lxp-d-provenance - the D ask is NOT answered for assistive-tech (${problems.length})`);
} else {
  console.log('\nPASS lxp-d-provenance - the provenance is reachable, announced, and says BOTH where the '
            + 'data came from and when it last changed, at phone-390 AND desktop-1280');
}
process.exit(problems.length ? 1 : 0);
