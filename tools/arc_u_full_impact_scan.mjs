// arc_u_full_impact_scan.mjs — Arc U (Accessibility) Phase-0 full-impact denominator.
//
// FB2's browser_ci_persona_walk floors on SERIOUS-level axe only (the persona-delta). Arc U
// (WCAG 2.2 AA) needs the FULL-impact scan — every impact level (minor/moderate/serious/critical)
// AND the WCAG 2.2 success criteria (target-size 2.5.8, focus-not-obscured 2.4.11, dragging 2.5.7).
// This scans all 35 live pages as the field-tech MOBILE persona (390x780 — the viewport where
// target-size + reflow matter most), reusing FB2's sign-in + page list. Report-only; writes
// .tmp/arcU_full_impact.json. No baseline mutation.
//
// Run:  node tools/arc_u_full_impact_scan.mjs   (local stack + :5000 seeder must be up)

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SUPABASE_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const AXE_CDN = 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js';

// field-tech mobile persona (mirror of browser_ci_persona_walk.mjs).
const PERSONA = {
  email: 'bryangarcia@auth.workhiveph.com', worker: 'Bryan Garcia', role: 'worker',
  hive: '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7', vw: 390, vh: 780,
};
const PAGE_QUERY = { 'marketplace-seller-profile.html': '?worker=Bryan%20Garcia' };
const PAGES = [
  'index.html','engineering-design.html','logbook.html','inventory.html','pm-scheduler.html',
  'voice-journal.html','dayplanner.html','resume.html','asset-hub.html','alert-hub.html',
  'analytics.html','analytics-report.html','shift-brain.html','ai-quality.html','ph-intelligence.html',
  'project-manager.html','project-report.html','skillmatrix.html','achievements.html','audit-log.html',
  'assistant.html','hive.html','community.html','public-feed.html','marketplace.html',
  'marketplace-seller.html','marketplace-seller-profile.html','marketplace-admin.html','integrations.html',
  'plant-connections.html','report-sender.html','status.html','founder-console.html',
  'llm-observability.html','agentic-rag-observability.html',
];
const WCAG_TAGS = ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa'];

async function signIn(context) {
  const page = await context.newPage();
  try {
    await page.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
    return await page.evaluate(async ({ email, password, hive, worker, role, surl }) => {
      try {
        const db = window._whSupabaseClient || window.getDb(surl, window.SUPABASE_KEY);
        const { data, error } = await db.auth.signInWithPassword({ email, password });
        localStorage.setItem('wh_active_hive_id', hive);
        localStorage.setItem('wh_last_worker', worker);
        localStorage.setItem('wh_hive_role', role);
        return { ok: !error && !!data?.session, err: error ? String(error.message || error) : null };
      } catch (e) { return { ok: false, err: String(e) }; }
    }, { email: PERSONA.email, password: PASSWORD, hive: PERSONA.hive, worker: PERSONA.worker, role: PERSONA.role, surl: SUPABASE_URL });
  } catch (e) { return { ok: false, err: String(e).slice(0, 120) }; }
  finally { await page.close().catch(() => {}); }
}

(async () => {
  // Fetch axe source once for a CSP-proof evaluate-inject fallback.
  let axeSource = '';
  try { axeSource = await (await fetch(AXE_CDN)).text(); } catch { /* fall back to addScriptTag url */ }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: PERSONA.vw, height: PERSONA.vh } });
  const si = await signIn(context);
  console.log(`signIn ${PERSONA.worker}: ${si.ok ? 'OK' : 'FAIL ' + si.err}`);

  const results = [];
  for (const pg of PAGES) {
    const page = await context.newPage();
    const rec = { page: pg, total: 0, byImpact: {}, violations: [], err: null };
    try {
      const q = PAGE_QUERY[pg] || '';
      await page.goto(`${SEEDER}/workhive/${pg}${q}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(1800);
      try { await page.addScriptTag({ url: AXE_CDN }); } catch { /* CSP — use evaluate-inject */ }
      let has = await page.evaluate(() => !!window.axe).catch(() => false);
      if (!has && axeSource) { await page.evaluate(axeSource).catch(() => {}); has = await page.evaluate(() => !!window.axe).catch(() => false); }
      if (!has) { rec.err = 'axe-inject-failed'; }
      else {
        const res = await page.evaluate(async (tags) => {
          const r = await window.axe.run(document, { runOnly: { type: 'tag', values: tags } });
          return r.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help }));
        }, WCAG_TAGS);
        rec.total = res.length;
        for (const v of res) rec.byImpact[v.impact] = (rec.byImpact[v.impact] || 0) + 1;
        rec.violations = res.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes, help: (v.help || '').slice(0, 90) }));
      }
    } catch (e) { rec.err = String(e).slice(0, 120); }
    finally { await page.close().catch(() => {}); }
    results.push(rec);
    console.log(`${rec.err ? 'ERR' : 'ok '} ${pg.padEnd(34)} total=${rec.total} ${JSON.stringify(rec.byImpact)}${rec.err ? ' :: ' + rec.err : ''}`);
  }
  await browser.close();

  const byRule = {};
  let grand = 0, errPages = 0;
  for (const r of results) {
    if (r.err) errPages++;
    grand += r.total;
    for (const v of r.violations) byRule[v.id] = (byRule[v.id] || 0) + 1;
  }
  console.log('\n================ FULL-IMPACT WCAG 2.2 AA (field-tech mobile 390x780) ================');
  console.log(`pages=${results.length}  scan-errors=${errPages}  GRAND violations=${grand}`);
  console.log('by rule:', JSON.stringify(byRule));
  writeFileSync('.tmp/arcU_full_impact.json', JSON.stringify({ persona: 'field-tech', viewport: '390x780', tags: WCAG_TAGS, grand, errPages, byRule, pages: results }, null, 2));
  console.log('-> .tmp/arcU_full_impact.json');
})();
