// copy_offenders.mjs - every sentence and block the rubric's B3/B1 fail on a page, untruncated, from the REAL lens (Wave CF).
//
// The survey's scored offender lists stop at 8/5/5 and 110 characters, and tools/b3_diagnostic.mjs is an older hand-copied
// mirror of B3 (ownText, not the lens's flowText). A rewrite has to start from the exact text the critic graded, so this
// runs survey_ufai_rubric.js itself with { full: true } and writes .tmp/copy/<slug>.json:
//   { page, failing, b3: { long:[...], passive:[...], overGrade:[{grade,text}] }, b1: [block text ...] }
// Signed out by default (the learn guides are public); a page's reveal and own-JS are loaded the way the walkers do.
//
//   node tools/copy_offenders.mjs learn/what-is-oee-how-to-calculate/index.html [more pages...] [--width 390]
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { PAGE_QUERY, PAGE_REVEAL, revealWorkedState, loadPageOwnJs } from './page_walk_state.mjs';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const wi = args.indexOf('--width');
const WIDTH = wi >= 0 ? parseInt(args[wi + 1], 10) : 1280;
const pages = args.filter((a, i) => !a.startsWith('--') && !(wi >= 0 && i === wi + 1));
const RUBRIC = readFileSync('survey_ufai_rubric.js', 'utf8');
mkdirSync('.tmp/copy', { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: WIDTH, height: 900 }, serviceWorkers: 'block' });
for (const rel of pages) {
  const page = await ctx.newPage();
  await page.goto(`${SEEDER}/workhive/${rel}${PAGE_QUERY[rel] || ''}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(1500);
  if (PAGE_REVEAL[rel]) await revealWorkedState(page, rel);
  await loadPageOwnJs(page);
  const parts = rel.split('/');
  const pid = parts[parts.length - 1] === 'index.html' && parts.length > 1 ? parts[parts.length - 2] : parts[parts.length - 1].replace(/\.html$/, '');
  const s = await page.evaluate(({ src, pid }) => {
    (0, eval)('(' + src + ')')();
    return window.__RUBRIC.survey({ pageId: pid, full: true });
  }, { src: RUBRIC, pid });
  const out = { page: rel, width: WIDTH, failing: s.failing, b3: s.b3_full || null, b1: s.b1_full || [] };
  writeFileSync(`.tmp/copy/${pid}.json`, JSON.stringify(out, null, 1));
  const b = out.b3 || { long: [], passive: [], overGrade: [] };
  console.log(`${rel} @${WIDTH}: long ${b.long.length} · passive ${b.passive.length} · grade>8 ${b.overGrade.length} · blocks>60w ${out.b1.length}`
    + `  -> .tmp/copy/${pid}.json   failing: ${(s.failing || []).map((f) => String(f).split(':')[0]).join(', ') || 'none'}`);
  await page.close();
}
await browser.close();
