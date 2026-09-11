// prove_public_bilingual — a Filipino-first reader actually gets Filipino on the public pages.
//
// ★MARKUP IS NOT TRANSLATION. Every calculator page carried a complete Filipino dictionary and called the
// swapper, and not one of them loaded the file that defines it - so `typeof whI18nApply === 'function'` was
// permanently false and a Filipino reader met English on all 60. Nothing errored. The lens that graded this
// asked `document.querySelector('[data-i]')`, which is a question about ATTRIBUTES, and attributes were
// exactly what was present while the translation was exactly what was missing.
//
// So this asks the only question that cannot be satisfied by decoration: set the language the way a person
// sets it, load the page, and check that the words CHANGED.
//
//   node tools/prove_public_bilingual.mjs              # a sample of learn + calculator pages
//   node tools/prove_public_bilingual.mjs --all
//   node tools/prove_public_bilingual.mjs --self-test  # no browser
import { chromium } from 'playwright';
import { takeBrowserSlot } from './browser_slot.mjs';
import { readdirSync, existsSync, writeFileSync, mkdirSync } from 'node:fs';

const args = process.argv.slice(2);
const ALL = args.includes('--all');
const BASE = (process.env.WH_SEEDER_URL || 'http://127.0.0.1:5000').replace(/\/workhive$/, '');

const learn = readdirSync('learn').filter((d) => existsSync(`learn/${d}/index.html`) && d !== 'index.html').map((d) => `learn/${d}/index.html`);
const calc = readdirSync('tools').filter((d) => existsSync(`tools/${d}/index.html`)).map((d) => `tools/${d}/index.html`);
// --kind narrows the walk. The calculator half of this gate cannot pass until Ian promotes the staged pages
// (the generator writes to seo_assets/calc_pages_staging, which the dev server does not serve at all - a
// 404 that read as "0 labelled elements" until the HTTP code was checked). So the registered gate walks the
// LIVE learn articles, where the same mechanism is already in place and provable today, and the calculator
// half joins it the moment those pages are promoted.
const KIND = (args.indexOf('--kind') >= 0) ? args[args.indexOf('--kind') + 1] : null;
const pool = KIND === 'learn' ? learn : KIND === 'calc' ? calc : [...learn, ...calc];
const roster = ALL ? pool : (KIND ? pool.slice(0, 8) : [...learn.slice(0, 4), ...calc.slice(0, 4)]);

if (args.includes('--self-test')) {
  // the reading this prover depends on: a page is bilingual when the SAME element's text differs by language
  const en = { home: 'Home', faq: 'FAQ' };
  const fil = { home: 'Home', faq: 'Mga madalas itanong' };
  const changed = Object.keys(en).filter((k) => en[k] !== fil[k]);
  const fails = [];
  if (changed.length !== 1 || changed[0] !== 'faq') fails.push('the difference test does not isolate the label that changed');
  if (!roster.length) fails.push('the roster is empty');
  console.log(fails.length ? 'FAIL public-bilingual self-test - ' + fails.join('; ')
    : `self-test OK: the test compares the SAME element across languages, and the roster holds ${roster.length} page(s)`);
  process.exit(fails.length ? 1 : 0);
}

const READ = () => {
  const out = {};
  for (const el of document.querySelectorAll('[data-i]')) {
    const k = el.getAttribute('data-i');
    if (el.children.length === 0) out[k] = (el.textContent || '').replace(/\s+/g, ' ').trim();
  }
  return out;
};

await takeBrowserSlot('public-bilingual');
const browser = await chromium.launch();
const results = [];
let bad = 0;
for (const f of roster) {
  const url = `${BASE}/${f}`;
  const read = async (lang) => {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    await ctx.addInitScript((l) => { try { localStorage.setItem('wh_lang', l); } catch (_) {} }, lang);
    const page = await ctx.newPage();
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(900);
    const labels = await page.evaluate(READ);
    await ctx.close();
    return labels;
  };
  try {
    const en = await read('en');
    const fil = await read('fil');
    const keys = Object.keys(en);
    const changed = keys.filter((k) => en[k] !== fil[k]);
    const same = keys.filter((k) => en[k] === fil[k]);
    const r = keys.length === 0
      ? { verdict: 'BAD', line: 'carries no labelled text at all - nothing a translator could act on' }
      : changed.length === 0
        ? { verdict: 'BAD', line: `${keys.length} labelled element(s) and NOT ONE changes under fil - the dictionary never reaches the page` }
        : { verdict: 'ok', line: `${changed.length} of ${keys.length} label(s) change under fil (e.g. "${en[changed[0]]}" -> "${fil[changed[0]]}")${same.length ? `; ${same.length} identical by design` : ''}` };
    if (r.verdict === 'BAD') bad++;
    results.push({ page: f, ...r, labels: keys.length, changed: changed.length });
    console.log(`  ${r.verdict === 'ok' ? 'ok ' : 'BAD'} ${f.replace(/\/index\.html$/, '').padEnd(56)} ${r.line.slice(0, 96)}`);
  } catch (e) {
    bad++;
    results.push({ page: f, verdict: 'BAD', line: 'could not be read: ' + String(e.message).slice(0, 60) });
    console.log(`  BAD ${f.padEnd(56)} could not be read: ${String(e.message).slice(0, 50)}`);
  }
}
await browser.close();
mkdirSync('.tmp', { recursive: true });
writeFileSync('.tmp/public_bilingual.json', JSON.stringify({ walked: roster.length, bad, results }, null, 1));
console.log(`${bad ? 'FAIL' : 'PASS'} public-bilingual - ${roster.length - bad}/${roster.length} public page(s) actually change language  ·  .tmp/public_bilingual.json`);
process.exit(bad ? 1 : 0);
