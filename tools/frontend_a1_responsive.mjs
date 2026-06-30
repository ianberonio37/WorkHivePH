// frontend_a1_responsive.mjs — Arc D / D3 Adaptability, the A1 bar:
// "adapts 360→1920 with no horizontal overflow / broken layout" (ISO adaptability,
// WCAG 1.4.10 Reflow). Signs in ONCE (the frontend_ufai_sweep recipe) so authed
// content renders, then measures document.scrollWidth vs clientWidth at 4 breakpoints
// per page. A page PASSES A1 if NO breakpoint overflows (>4px tolerance for scrollbar).
// Writes frontend_a1_responsive.json. Shell-parked off-screen elements (the
// wh-feedback-fab transform artifact) are excluded by measuring documentElement only.
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const EMAIL = process.env.WH_TEST_EMAIL || 'leandromarquez@auth.workhiveph.com';
const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const HIVE = '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7';
const BPS = [360, 768, 1280, 1920];
const TOL = 4; // px scrollbar tolerance

const PAGES = [
  'index','engineering-design','logbook','inventory','pm-scheduler','voice-journal','dayplanner',
  'asset-hub','alert-hub','analytics','analytics-report','shift-brain','predictive','ai-quality',
  'ph-intelligence','project-manager','project-report','skillmatrix','achievements','audit-log',
  'assistant','hive','community','public-feed','marketplace','marketplace-seller','marketplace-admin',
  'integrations','plant-connections','report-sender','status','founder-console','llm-observability',
  'agentic-rag-observability',
];

const browser = await chromium.launch();
const ctx = await browser.newContext();
const sp = await ctx.newPage();
await sp.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
await sp.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
await sp.evaluate(async ({ email, password, hive }) => {
  const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
  await db.auth.signInWithPassword({ email, password });
  localStorage.setItem('wh_active_hive_id', hive);
}, { email: EMAIL, password: PASSWORD, hive: HIVE });
await sp.close();

const out = [];
let passCount = 0;
for (const name of PAGES) {
  const page = await ctx.newPage();
  const rec = { page: name + '.html', bp: {} };
  try {
    await page.goto(`${SEEDER}/workhive/${name}.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(1800);
    for (const w of BPS) {
      await page.setViewportSize({ width: w, height: 900 });
      await page.waitForTimeout(450);
      const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
      rec.bp[w] = { sw: m.sw, cw: m.cw, over: m.sw - m.cw };
    }
    const overflows = BPS.filter(w => rec.bp[w].over > TOL);
    rec.pass = overflows.length === 0;
    rec.overflowAt = overflows.map(w => `${w}:${rec.bp[w].over}px`);
    if (rec.pass) passCount++;
  } catch (e) { rec.error = String(e).slice(0, 100); rec.pass = false; }
  await page.close();
  out.push(rec);
  console.log(`${(rec.pass?'PASS':'OVER').padEnd(5)} ${name.padEnd(30)} ${rec.pass ? 'no overflow 360-1920' : 'overflow@ ' + rec.overflowAt.join(' ')}`);
}
writeFileSync('frontend_a1_responsive.json', JSON.stringify({ generated: new Date().toISOString(), breakpoints: BPS, tolerance: TOL, pass: passCount, total: out.length, results: out }, null, 2));
console.log(`\n-> A1 responsive: ${passCount}/${out.length} pages no-overflow across 360/768/1280/1920. wrote frontend_a1_responsive.json`);
await browser.close();
