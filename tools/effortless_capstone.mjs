// effortless_capstone.mjs — Arc V (EFFORTLESS) family capstones (V2★–V7★).
//
// WHY: the single-page sweep proves each PAGE is effortless; it does NOT prove a multi-page JOB
// is — friction (and lost context) ACCUMULATES across hops (NN/g: an interaction-cost chain).
// `journey_battery.js` already proves cross-page VALUE coherence (same metric, same number on
// two pages). This adds the other half: the cumulative HOP-COST of a realistic cross-page flow
// + CONTINUITY (the session/hive context survives every hop — no re-auth, no empty/sign-in bounce).
//
// READ-ONLY by design (pure navigation + reads) — no DB writes, so it never pollutes the shared
// test DB and needs no cleanup. Reuses signIn/makeHelpers + instrumentHelpers (one source of truth).
//
// USAGE: node tools/effortless_capstone.mjs            (all chains)
//        node tools/effortless_capstone.mjs --chain V3

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, makeHelpers, SEEDER } from './live_page_journeys.mjs';
import { instrumentHelpers } from './live_page_journeys.effort.mjs';

const args = process.argv.slice(2);
const CHAIN_ONLY = (() => { const i = args.indexOf('--chain'); return i >= 0 ? args[i + 1] : null; })();
const ACCEPT = args.includes('--accept'); // bank the baseline (continuity_breaks=0 forever; excess_hops ceiling)
const BASELINE = 'arc_v_capstone_baseline.json';

// A universal "this is an authed, rendered WorkHive page" marker: every live page mounts the
// nav-hub FAB (#wh-hub-fab / .wh-hub) and is NOT the sign-in screen. That's the continuity check —
// if a hop lands on sign-in or a bare page, context was lost.
const CONTINUITY = `(${(() => {
  const url = location.href;
  if (/signin|sign-in|login/i.test(url)) return { ok: false, why: 'bounced to sign-in' };
  const hub = document.querySelector('#wh-hub-fab, .wh-hub, [id^="wh-hub"]');
  const hasMain = document.querySelector('main, #main-content, [role="main"], .app, #app, .container');
  if (!hub && !hasMain) return { ok: false, why: 'no nav-hub / main content (blank?)' };
  return { ok: true };
}).toString()})()`;

// Capstone chains: a realistic cross-page JOB as an ordered list of page hops. `ideal` = the
// fewest hops a user should need (one goto per surface in the chain; clicks within are counted too).
const CHAINS = [
  // V2★ "Close a job" — TRAVERSAL half measured here (hop-cost + continuity across the job's pages);
  // the WRITE state-carry half (create->persist->close, numbers update coherently) is covered by the
  // Arc-K LOG1/LOG3 drives + journey_battery.js value-coherence (assertEqual across pages).
  { id: 'V2', title: 'Close a job: logbook -> asset-hub -> pm-scheduler', role: 'worker',
    pages: ['logbook.html', 'asset-hub.html', 'pm-scheduler.html'], idealHops: 3 },
  { id: 'V3', title: 'Analyze health: analytics -> asset -> report -> benchmark', role: 'supervisor',
    pages: ['analytics.html', 'asset-hub.html', 'analytics-report.html', 'ph-intelligence.html'], idealHops: 4 },
  { id: 'V4', title: 'Supervise: hive -> audit -> ai-quality', role: 'supervisor',
    pages: ['hive.html', 'audit-log.html', 'ai-quality.html'], idealHops: 3 },
  { id: 'V7', title: 'Source/integrate: marketplace -> seller -> integrations -> plant-connections', role: 'supervisor',
    pages: ['marketplace.html', 'marketplace-seller.html', 'integrations.html', 'plant-connections.html'], idealHops: 4 },
  { id: 'V5', title: 'Build culture: skillmatrix -> achievements -> community', role: 'worker',
    pages: ['skillmatrix.html', 'achievements.html', 'community.html'], idealHops: 3 },
  { id: 'V6', title: 'Deliver project: engineering-design -> project-manager -> project-report', role: 'supervisor',
    pages: ['engineering-design.html', 'project-manager.html', 'project-report.html'], idealHops: 3 },
  { id: 'Vmorning', title: 'Morning rounds: index -> logbook -> pm-scheduler -> alert-hub -> dayplanner', role: 'worker',
    pages: ['index.html', 'logbook.html', 'pm-scheduler.html', 'alert-hub.html', 'dayplanner.html'], idealHops: 5 },
];

(async () => {
  const chains = CHAINS.filter(c => !CHAIN_ONLY || c.id === CHAIN_ONLY);
  const browser = await chromium.launch({ headless: true });
  const results = [];
  for (const chain of chains) {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: 'Asia/Manila' });
    const si = await signIn(ctx, chain.role);
    const page = await ctx.newPage();
    const { helpers, counters } = instrumentHelpers(makeHelpers(page));
    const steps = [];
    for (const pg of chain.pages) {
      let cont = { ok: false, why: 'goto failed' };
      try { await helpers.goto(pg); cont = await page.evaluate(CONTINUITY); }
      catch (e) { cont = { ok: false, why: String(e).slice(0, 60) }; }
      steps.push({ page: pg, continuity: cont.ok, why: cont.why || null });
    }
    await page.close(); await ctx.close();
    const hops = counters.hops;
    const clicks = counters.clicks;
    const continuityOk = steps.every(s => s.continuity);
    const excessHops = Math.max(0, hops - chain.idealHops);
    results.push({ id: chain.id, title: chain.title, role: chain.role, signin: si.ok && !si.anon,
      pages: chain.pages.length, hops, clicks, ideal_hops: chain.idealHops, excess_hops: excessHops,
      cumulative_cost: hops + clicks, continuity_ok: continuityOk, steps,
      verdict: (continuityOk && excessHops === 0) ? 'EFFORTLESS' : (!continuityOk ? 'CONTINUITY-BREAK' : 'EXCESS-HOPS') });
    console.log(`[${chain.id}] ${chain.title}`);
    console.log(`   hops=${hops} (ideal ${chain.idealHops}, excess ${excessHops}) · clicks=${clicks} · cost=${hops + clicks} · continuity=${continuityOk ? 'OK all ' + chain.pages.length + ' pages' : 'BREAK'} -> ${results[results.length - 1].verdict}`);
    for (const s of steps.filter(s => !s.continuity)) console.log(`     ! ${s.page}: ${s.why}`);
  }
  await browser.close();
  const out = { ran: new Date().toISOString(), seeder: SEEDER, chains: results,
    summary: { chains: results.length, effortless: results.filter(r => r.verdict === 'EFFORTLESS').length,
      continuity_breaks: results.filter(r => !r.continuity_ok).length, total_excess_hops: results.reduce((s, r) => s + r.excess_hops, 0) } };
  writeFileSync('arc_v_capstone_results.json', JSON.stringify(out, null, 2));
  console.log(`\n  -> ${out.summary.effortless}/${out.summary.chains} chains EFFORTLESS · ${out.summary.continuity_breaks} continuity-breaks · ${out.summary.total_excess_hops} total excess hops`);
  console.log('  -> wrote arc_v_capstone_results.json');
  if (ACCEPT && !CHAIN_ONLY) {
    writeFileSync(BASELINE, JSON.stringify({ continuity_breaks: 0, total_excess_hops: out.summary.total_excess_hops, chains: out.summary.chains, set: new Date().toISOString() }, null, 2));
    console.log(`  -> baseline banked: continuity_breaks must stay 0, excess_hops <= ${out.summary.total_excess_hops}, chains >= ${out.summary.chains}`);
  }
})();
