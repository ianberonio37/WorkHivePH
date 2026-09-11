// prove_tagalog_first — the EX-TL wave: a Filipino technician who reads Tagalog first (2026-09-07).
//
// This platform's users are maintenance crews in Philippine plants. Only 10 of 39 root pages carried a
// single `_t()` string when this wave was seeded; the other 27 were English-only to a person whose
// working language is Tagalog. The platform already has the machinery - `_t(en, fil)` for JS strings,
// `data-i` + `whI18nApply` for static markup, `localStorage.wh_lang = 'fil'` to choose - so the
// question per page is not "can it be done" but "was it done here".
//
//   L1 the page reads     switching to Filipino CHANGES what a person sees on this page - measured by
//                         walking it twice, en then fil, and counting the visible text that moved
//   L2 errors in Tagalog  the sentences a person meets when something fails go through _t() or data-i
//   L3 empties in Tagalog the sentences a person meets when there is nothing to show do too
//   L4 confirms & CTAs    the words on the controls a person presses do too
//
// ★MEASURED TWO WAYS, AND THE LIVE ONE DECIDES. The static census (L2-L4) counts strings that never went
// through a translation path; the live walk (L1) counts what actually changed on screen when the
// language did. A page can carry a hundred _t() calls and still show a person nothing in Tagalog if
// the switch never reaches them - so L1 is the verdict and L2-L4 say where the work is.
//
//   node tools/prove_tagalog_first.mjs
//   node tools/prove_tagalog_first.mjs --page inventory.html
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const read = (f) => { try { return readFileSync(f, 'utf8'); } catch { return ''; } };

// the roster is the wave's own: every EX-TL row's page, read from the registry rather than re-measured
const ROSTER = (() => {
  try {
    const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
    return [...new Set(reg.trajectories.filter((t) => t.wave === 'EX-TL').flatMap((t) => t.pages || []))];
  } catch { return []; }
})();

// the sentences a person meets at the three moments that matter, found in the page's own source
const ERR = /(could not|couldn.t|failed|not allowed|try again|something went wrong|refused|unavailable)[^'"`]{0,80}/gi;
const EMPTY = /(no (entries|posts|items|listings|assets|alerts|results|data|tasks)[^'"`]{0,60}|nothing (here|to show|logged|found)[^'"`]{0,60})/gi;
const CTA = /<button[^>]*>([^<]{2,40})<\/button>|okLabel:\s*['"]([^'"]{2,30})['"]|whConfirm\(\s*['"`]([^'"`]{10,120})/gi;

// ★A SENTENCE A PERSON MEETS LIVES INSIDE QUOTES. The first census matched the failure vocabulary anywhere
// in the source and reported "61 of 61 failure sentences untranslated" on report-sender - and a sample of
// eight on inventory.html was seven comments and a variable named _invReadFailed. A person never reads a
// comment. So: comments are stripped first, console.* lines are skipped, and a hit only counts when it
// sits inside a quoted string. The live half of this prover (L1) never had this problem - it reads the
// screen - which is why L1 is the verdict and the census only says where the work is.
// ★A STRING A PERSON NEVER READS IS NOT A SENTENCE EITHER (second census, 2026-09-07). After the wrap, the
// residue was 91 "failure sentences" - and a third of them were `console.warn('[analytics] snapshot read
// failed:', e)` INSIDE a .catch (not at line start, so the line rule missed them), `querySelector('#read-
// failed-state p.text-xs')` (a selector), and thrown Error messages like 'Canvas 2D context unavailable'
// that the page catches itself. So the whole console call is removed wherever it sits, selector lookups
// are removed, and a string that is an identifier or a selector (leading [ # . or an underscore inside)
// is not a sentence. The live half (L1) is unchanged - it reads the screen.
const stripComments = (s) => s
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/^[ \t]*\/\/.*$/gm, ' ')
  // a trailing comment after code (`x(); // don't`) - its apostrophe opened a fake string that swallowed
  // the next real sentence ("t load disputes. Try again."). A URL's :// has no space before it.
  .replace(/[ \t]\/\/ .*$/gm, ' ')
  .replace(/console\.[a-z]+\((?:[^()'"`]|'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*`|\((?:[^()]|\([^()]*\))*\))*\)/g, ' ')
  .replace(/(?:querySelector(?:All)?|getElementById|closest|matches|classList\.\w+)\(\s*(['"`])(?:\\.|(?!\1)[^\\])*\1/g, ' ');
const notASentence = (t) => /^[\[#.]|_|\(\)/.test(t);
const QUOTED = /(['"`])((?:\\.|(?!\1)[^\\])*)\1/g;
const censusOf = (raw) => {
  const src = stripComments(raw);
  const throughT = (s) => /_t\(|\bT\(|data-i=/.test(s);
  // every quoted string, with where it sits, so the translation-path test looks at the call around it
  const strings = [];
  let q;
  while ((q = QUOTED.exec(src))) {
    if (q[2].length >= 8 && q[2].length <= 240 && !notASentence(q[2])) strings.push({ text: q[2], at: q.index });
  }
  // `missing` names what was counted and not translated - the instrument must explain its own number
  const count = (rx) => {
    let total = 0, translated = 0;
    const seen = new Set(), missing = [];
    for (const s of strings) {
      if (!rx.test(s.text)) { rx.lastIndex = 0; continue; }
      rx.lastIndex = 0;
      const key = s.text.slice(0, 48);
      if (seen.has(key)) continue;
      seen.add(key);
      total++;
      if (throughT(src.slice(Math.max(0, s.at - 40), s.at + 4))) translated++; else missing.push(s.text);
    }
    return { total, translated, missing };
  };
  // CTAs are markup as well as strings: a <button> label or a whConfirm okLabel
  const ctaTotal = new Set(), ctaTranslated = new Set();
  let m;
  const btn = /<button[^>]*>([^<]{2,40})<\/button>/gi;
  while ((m = btn.exec(src))) {
    const label = m[1].trim(); if (!label) continue;
    // `${escHtml(row.worker_name)}` / `' + nxt[1] + '` is DATA painted into a button, not a label to translate
    if (/\$\{|['"] \+ /.test(label)) continue;
    ctaTotal.add(label);
    if (/data-i=/.test(m[0]) || /_t\(|\bT\(/.test(src.slice(Math.max(0, m.index - 60), m.index))) ctaTranslated.add(label);
  }
  const ok = count(new RegExp(/okLabel:\s*['"`]([^'"`]{2,30})/.source, 'gi'));
  return {
    err: count(/(could not|couldn.t|failed to|not allowed|try again|something went wrong|refused|unavailable|did not go through)/i),
    empty: count(/(no (entries|posts|items|listings|assets|alerts|results|data|tasks|parts)\b|nothing (here|to show|logged|found|yet))/i),
    cta: {
      total: ctaTotal.size + ok.total, translated: ctaTranslated.size + ok.translated,
      missing: [...ctaTotal].filter((l) => !ctaTranslated.has(l)).concat(ok.missing),
    },
  };
};

// --census-only: the static half alone, in seconds - where the work is, before the walk that judges it
if (process.argv.includes('--census-only')) {
  let tE = 0, tEm = 0, tC = 0;
  for (const file of (ONLY ? [ONLY] : ROSTER)) {
    const c = censusOf(read(file));
    tE += c.err.total - c.err.translated; tEm += c.empty.total - c.empty.translated; tC += c.cta.total - c.cta.translated;
    console.log(`  ${file.padEnd(34)} err ${c.err.translated}/${c.err.total} · empty ${c.empty.translated}/${c.empty.total} · cta ${c.cta.translated}/${c.cta.total}`);
    // --list: name every string behind the count, so the fix is authored against the exact text
    if (process.argv.includes('--list')) {
      for (const [k, v] of [['err', c.err], ['empty', c.empty], ['cta', c.cta]]) for (const t of v.missing) console.log(`      ${k.padEnd(5)} ${JSON.stringify(t).slice(0, 400)}`);
    }
  }
  console.log(`  untranslated across the roster: ${tE} failure sentence(s) · ${tEm} empty state(s) · ${tC} control label(s)`);
  process.exit(0);
}

const b = await chromium.launch();
let bad = 0, n = 0;
for (const file of (ONLY ? [ONLY] : ROSTER)) {
  n++;
  const src = read(file);
  const c = censusOf(src);
  const hasMachinery = /_t\(|data-i=|whI18nApply/.test(src) || /utils\.js/.test(src);

  // the live walk: the same page, en then fil, in one signed-in context
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  await signIn(ctx);
  const p = await ctx.newPage();
  const url = `${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`;
  const grab = async () => p.evaluate((VIS_JS) => {
    const vis = (0, eval)(VIS_JS);
    const main = document.querySelector('main, [role="main"], #app, #root') || document.body;
    const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
    const out = [];
    let node;
    while ((node = walker.nextNode())) {
      const t = (node.nodeValue || '').replace(/\s+/g, ' ').trim();
      if (t.length >= 4 && node.parentElement && vis(node.parentElement) && !/^[\d\W]+$/.test(t)) out.push(t);
    }
    return out;
  }, VIS_JS).catch(() => []);

  await p.goto(url, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.evaluate(() => { try { localStorage.setItem('wh_lang', 'en'); } catch (e) { void e; } });
  await p.reload({ waitUntil: 'load' }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);
  const en = await grab();
  await p.evaluate(() => { try { localStorage.setItem('wh_lang', 'fil'); } catch (e) { void e; } });
  await p.reload({ waitUntil: 'load' }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);
  const fil = await grab();
  await p.evaluate(() => { try { localStorage.setItem('wh_lang', 'en'); } catch (e) { void e; } });
  await ctx.close();

  const enSet = new Set(en);
  const moved = fil.filter((t) => !enSet.has(t)).length;
  const share = en.length ? moved / en.length : 0;
  const issues = [];
  if (en.length === 0) issues.push('L1 the page rendered no visible text in either language, so nothing was measured');
  else if (share < 0.15) issues.push(`L1 switching to Filipino changed ${moved} of ${en.length} visible strings (${Math.round(share * 100)}%) - a Tagalog-first person sees an English page`);
  if (c.err.total && c.err.translated < c.err.total) issues.push(`L2 ${c.err.total - c.err.translated} of ${c.err.total} failure sentence(s) never go through a translation path`);
  if (c.empty.total && c.empty.translated < c.empty.total) issues.push(`L3 ${c.empty.total - c.empty.translated} of ${c.empty.total} empty-state sentence(s) never go through a translation path`);
  if (c.cta.total && c.cta.translated < c.cta.total * 0.5) issues.push(`L4 ${c.cta.total - c.cta.translated} of ${c.cta.total} control label(s) never go through a translation path`);
  if (!hasMachinery) issues.push('L1 the page loads no translation machinery at all');

  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${file.padEnd(34)} fil moved ${moved}/${en.length} (${Math.round(share * 100)}%) · err ${c.err.translated}/${c.err.total} · empty ${c.empty.translated}/${c.empty.total} · cta ${c.cta.translated}/${c.cta.total}`);
  for (const s of issues.slice(0, ONLY ? 8 : 2)) console.log(`        ${s.slice(0, 158)}`);
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} tagalog-first - ${n - bad}/${n} page(s) show a Tagalog-first person a page in their language, with failures, empties and controls translated`);
process.exitCode = bad ? 1 : 0;
