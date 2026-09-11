// probe_learn_touch_targets — WHICH controls on a learn article are under 44px, and which of them owe it.
//
// The W3-LN Adaptability lens reports "26 target(s) under 40px" on every learn article while all 60
// calculator pages report zero — the calculators were given `min-height: 44px`, `touch-action: manipulation`
// and `overscroll-behavior: contain` centrally in their generator, and the articles never were.
//
// ★BUT A COUNT IS NOT YET A FINDING, BECAUSE NOT EVERY SMALL LINK OWES 44px. WCAG 2.5.8 exempts a link that
// sits INLINE IN A SENTENCE: making a word inside a paragraph 44px tall would wreck the line box, and the
// standard says so explicitly. A lens that counts every small anchor therefore over-counts, and "26" mixes
// the genuinely-too-small nav chip with the perfectly-correct word in a sentence. This probe separates them
// before anything is changed, so the fix lands on the controls that actually owe the size and nowhere else.
//
//   node tools/probe_learn_touch_targets.mjs                 # a sample of articles
//   node tools/probe_learn_touch_targets.mjs --all
import { chromium } from 'playwright';
import { takeBrowserSlot } from './browser_slot.mjs';
import { readdirSync, existsSync, writeFileSync, mkdirSync } from 'node:fs';

const ORIGIN = process.env.WH_SEEDER_URL ? `${process.env.WH_SEEDER_URL}/workhive` : 'http://127.0.0.1:5000/workhive';
const args = process.argv.slice(2);
const ALL = args.includes('--all');

const pages = readdirSync('learn')
  .filter((d) => existsSync(`learn/${d}/index.html`) && d !== 'index.html')
  .map((d) => `learn/${d}/index.html`);
const roster = ALL ? pages : pages.slice(0, 6);

const MEASURE = () => {
  // ★COMPARE AGAINST THE SENTENCE, NOT THE TAG THAT HAPPENS TO WRAP THE LINK. The first version looked only
  // at the IMMEDIATE parent and demanded it be a prose tag, so it reported 47 false findings: a CTA written
  // as `<div class="callout"><strong><a>Try WorkHive free</a></strong>: Free at the worker tier, …</div>`
  // has <strong> as its parent - which contains nothing but the link - and a <div> above that, which was not
  // in the allowed list at all. Both readings said "stands alone" about a link plainly sitting in a
  // sentence. The exemption is about the TEXT AROUND the link, so walk up to the nearest BLOCK and ask there.
  const BLOCK = /^(P|LI|TD|TH|BLOCKQUOTE|DIV|SECTION|ARTICLE|FIGCAPTION|DD|DT|H[1-6])$/;
  const inSentence = (el) => {
    let b = el.parentElement;
    while (b && !BLOCK.test(b.tagName)) b = b.parentElement;
    if (!b) return false;
    const t = (b.textContent || '').trim();
    const own = (el.textContent || '').trim();
    return t.length > own.length + 12;   // the block carries meaningfully more text than the link itself
  };
  const where = (el) => {
    if (el.closest('nav')) return 'nav';
    if (el.closest('footer')) return 'footer';
    if (el.closest('header')) return 'header';
    if (inSentence(el)) return 'inline in a sentence (WCAG 2.5.8 exempt)';
    if (el.closest('article, main')) return 'article, standing alone';
    return 'elsewhere';
  };
  const vis = (e) => !!e && (typeof e.checkVisibility === 'function' ? e.checkVisibility({ visibilityProperty: true }) : e.offsetParent !== null);
  const out = {};
  for (const el of Array.from(document.querySelectorAll('a, button, [role="button"], input, select')).filter(vis)) {
    const r = el.getBoundingClientRect();
    if (r.width <= 0) continue;
    if (r.height >= 44 && r.width >= 44) continue;
    const k = where(el);
    (out[k] = out[k] || []).push({
      tag: el.tagName.toLowerCase(),
      cls: (el.getAttribute('class') || '').slice(0, 46),
      text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 28),
      h: Math.round(r.height), w: Math.round(r.width),
    });
  }
  return out;
};

await takeBrowserSlot('learn-touch-targets');
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
const totals = {};
const results = [];
for (const f of roster) {
  const page = await ctx.newPage();
  try {
    await page.goto(`${ORIGIN.replace(/\/workhive$/, '')}/${f}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(1500);
    const groups = await page.evaluate(MEASURE);
    results.push({ page: f, groups });
    for (const [k, v] of Object.entries(groups)) totals[k] = (totals[k] || 0) + v.length;
    const line = Object.entries(groups).map(([k, v]) => `${v.length} ${k}`).join(' · ') || 'none under 44px';
    console.log(`  ${f.replace(/\/index\.html$/, '').padEnd(56)} ${line}`);
  } catch (e) {
    console.log(`  ${f.padEnd(56)} could not be read: ${String(e.message).slice(0, 50)}`);
  }
  await page.close();
}
await browser.close();

console.log('\n  across ' + roster.length + ' article(s), controls under 44px by where they sit:');
for (const [k, n] of Object.entries(totals).sort((a, b) => b[1] - a[1])) console.log(`    ${String(n).padStart(4)}  ${k}`);
const owed = Object.entries(totals).filter(([k]) => !/exempt/.test(k)).reduce((s, [, n]) => s + n, 0);
const exempt = (totals['inline in a sentence (WCAG 2.5.8 exempt)'] || 0);
console.log(`\n  ${owed} control(s) genuinely owe 44px; ${exempt} are inline links in a sentence, which do not.`);

// ★TWO THRESHOLDS, BECAUSE THE STANDARD HAS TWO. WCAG 2.5.8 (AA) requires 24x24; 2.5.5 (AAA) requires 44x44.
// A feature link measuring 38x44 in a grid clears AA comfortably and misses AAA by six pixels on one axis -
// treating that identically to a 117x17 link, which fails even AA, would bury the one that actually hurts
// under seven that do not. The gate FAILS on the AA floor and REPORTS the AAA gap.
const flat = [];
for (const r of results) for (const [k, v] of Object.entries(r.groups || {})) {
  if (/exempt/.test(k)) continue;
  for (const x of v) flat.push({ page: r.page, ...x });
}
const belowAA = flat.filter((x) => x.w < 24 || x.h < 24);
const aaaGap = flat.filter((x) => !(x.w < 24 || x.h < 24));
if (belowAA.length) {
  console.log(`\n  BELOW the WCAG 2.5.8 AA floor of 24x24 - these are the ones a thumb actually misses:`);
  for (const x of belowAA) console.log(`    ${x.w}x${x.h}  ${x.page.replace(/^learn\/|\/index\.html$/g, '')}  ${JSON.stringify(x.text)}`);
}
if (aaaGap.length) {
  console.log(`\n  between 24x24 and 44x44 - clears AA, misses AAA (${aaaGap.length}), reported not failed:`);
  for (const x of aaaGap.slice(0, 6)) console.log(`    ${x.w}x${x.h}  ${x.page.replace(/^learn\/|\/index\.html$/g, '')}  ${JSON.stringify(x.text)}`);
}
console.log(`${belowAA.length ? 'FAIL' : 'PASS'} learn-touch-targets - ${roster.length} article(s): `
  + `${belowAA.length} standalone control(s) below the 24x24 AA floor, ${aaaGap.length} in the AAA gap, `
  + `${exempt} inline links correctly exempt`);
mkdirSync('.tmp', { recursive: true });
writeFileSync('.tmp/learn_touch_targets.json', JSON.stringify({ walked: roster.length, totals, results }, null, 1));
console.log('  .tmp/learn_touch_targets.json');
process.exit(belowAA.length ? 1 : 0);
