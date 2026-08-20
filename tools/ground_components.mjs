// ground_components.mjs — resolve each page's CK components to LIVE selectors, by looking at what the
// page actually renders.
//
// WHY THIS EXISTS. CK ui-state is 226 owed rows keyed by COMPONENT (C1/C2/C3 per page), and a prover
// cannot assert "this component shows a loading state" until it can find the component. Of the 66
// components in `page_bank_anatomy/`, only 8 carry a `#selector`; the other 57 cite `file:line`.
//
// THE SHORTCUT WAS TRIED AND REJECTED, WHICH IS WHY THIS IS A BROWSER TOOL AND NOT A PARSER. Scraping the
// selector out of the cited source line yielded 26 of 66, and the 26 were not trustworthy:
//   · community C3 "reaction bar"  -> `.reaction-btn${d.mine`  — a template-literal FRAGMENT, because the
//     line is JS assembling markup, so the harvested "class" is half an interpolation.
//   · dayplanner C2 "item modal"   -> `#dp-week-hero`          — a DIFFERENT element; the ±2-line window
//     caught a neighbouring id, and nothing in the output says so.
// Source PROXIMITY is not identity: a line number records where a component was written, not what it
// renders. A scraped selector that silently names the wrong node is worse than none, because a CK prover
// would then assert loading/skeleton/busy against an unrelated element and report it confidently.
//
// SO: enumerate what is really on the page. This emits an inventory per page — repeated structures (the
// rows and cards a list is built from), and id-bearing blocks — each with a stable selector, an instance
// count and sample text. That inventory is the raw material a human (or a careful matching pass) uses to
// bind "C2 = entry row" to a real selector, exactly as `tools/dialog_targets.mjs` was built by OPENING
// each dialog rather than by reading about it. Four provers now share that table because it was grounded
// once, properly; this is its sibling for components.
//
// NON-WRITING: pages are loaded and read. Nothing is clicked, typed or submitted.
import { chromium } from 'playwright';
import { writeFileSync, readFileSync, existsSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager', 'dayplanner',
  'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain', 'voice-journal', 'assistant',
  'community', 'public-feed', 'achievements', 'engineering-design', 'resume', 'report-sender',
  'project-report', 'analytics-report'];

const INVENTORY = () => {
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  // ★ RANK BY MEANING, NOT BY COUNT — the first version sorted purely on how often a class repeated, and
  // on a utility-CSS page that surfaces the CSS FRAMEWORK instead of the product. For logbook it returned
  // `.flex.items-center` (n=4) and `.text-white/80` (n=3) while the three components actually wanted —
  // entry row, capture form, parts picker — never appeared at all. Utility classes are the most repeated
  // things on the page precisely because they carry no identity.
  // So a class is only a candidate NAME if it reads like a component (row/card/item/tile/entry/…), and a
  // `data-*` hook beats any class, because an authored data attribute is the closest thing to a declared
  // component identity this codebase has.
  const SEMANTIC = /(row|card|item|tile|entry|cell|badge|chip|list|panel|modal|sheet|form|picker|bar)/i;
  const UTILITY = /^(flex|grid|items|justify|text|bg|border|p[xytblr]?-|m[xytblr]?-|w-|h-|gap|space|rounded|shadow|font|leading|tracking|overflow|absolute|relative|fixed|sticky|block|inline|hidden|min|max|top|left|right|bottom|z-|opacity|transition|hover|focus|sm|md|lg|xl)/;
  const clean = (el) => {
    for (const a of el.attributes || []) {
      if (a.name.startsWith('data-') && a.value && a.value.length < 30 && !/^\d+$/.test(a.value)) {
        return `[${a.name}]`;                       // an authored hook: the strongest identity available
      }
    }
    const cls = (el.className || '').toString().trim().split(/\s+/)
      .filter((c) => c && !/^(ng-|is-|has-)/.test(c) && !UTILITY.test(c));
    const semantic = cls.filter((c) => SEMANTIC.test(c));
    return (semantic.length ? semantic : cls).slice(0, 2).join('.');
  };
  const txt = (el) => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60);

  // ── repeated structures: the row/card a list is actually built from. A component in this bank is
  // almost always "the thing that repeats" (entry row, part row, alert row, achievement tile), so the
  // count is the strongest signal that a node IS the component rather than its container.
  const groups = {};
  for (const el of document.querySelectorAll('*')) {
    if (!vis(el) || !el.parentElement) continue;
    const cls = clean(el);
    if (!cls) continue;
    const key = `${el.parentElement.tagName.toLowerCase()}>${el.tagName.toLowerCase()}${cls}`;
    const sel = cls.startsWith('[') ? cls : `.${cls}`;
    (groups[key] = groups[key] || { sel, tag: el.tagName.toLowerCase(), n: 0, sample: '' });
    groups[key].n++;
    if (!groups[key].sample) groups[key].sample = txt(el);
  }
  const repeated = Object.values(groups).filter((g) => g.n >= 2 && g.sample)
    .sort((a, b) => b.n - a.n).slice(0, 14);

  // ── id-bearing blocks: singleton components (a hero card, a verdict panel, a composer).
  const ids = [...document.querySelectorAll('[id]')].filter((el) => vis(el) && el.children.length <= 12)
    .map((el) => ({ sel: `#${el.id}`, tag: el.tagName.toLowerCase(), kids: el.children.length,
                    sample: txt(el) }))
    .filter((x) => x.sample).slice(0, 26);

  return { repeated, ids };
};

const browser = await chromium.launch();
const out = {};
for (const p of (ONE ? [ONE.replace(/\.html$/, '')] : PAGES)) {
  try {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    await assertSignedIn(signIn(ctx, 'supervisor'));
    const page = await ctx.newPage();
    await page.goto(`${ORIGIN}/${p}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(4200);
    const landed = (page.url().split('/').pop() || '').split('#')[0].split('?')[0].replace(/\.html$/, '');
    if (landed !== p) {
      out[p] = { error: `landed on ${landed} — inventory would describe the wrong page` };
    } else {
      out[p] = await page.evaluate(INVENTORY);
      // What the anatomy SAYS this page's components are, carried alongside so the binding is done with
      // both halves visible rather than from memory.
      const fp = `page_bank_anatomy/${p}.json`;
      if (existsSync(fp)) {
        const a = JSON.parse(readFileSync(fp, 'utf8'));
        out[p].wanted = (a.components || []).map((c) => `${c.key}: ${c.name}`);
      }
    }
    await ctx.close();
  } catch (e) { out[p] = { error: String(e.message || e).slice(0, 120) }; }
  const r = out[p];
  console.log(`  ${p.padEnd(20)} ${r.error ? 'ERR ' + r.error
    : `${r.repeated.length} repeated · ${r.ids.length} id-blocks · wants ${(r.wanted || []).length}`}`);
}
await browser.close();
writeFileSync('component_inventory.json', JSON.stringify(out, null, 1));
console.log('\n  wrote component_inventory.json — raw material for binding CK components to live nodes.');
console.log('  NOT an answer by itself: each binding still has to be chosen and recorded with its reason,');
console.log('  the way dialog_targets.mjs records why each of its 43 targets opens the way it does.');
