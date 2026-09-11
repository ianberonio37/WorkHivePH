// prove_calc_handoff — the calculator SEO pages' hand-off, of the live-walk wave (2026-09-06).
//
// 58 trajectory rows carried the lens "Public calculator computes standalone", and walking it settled that the
// lens itself was wrong: the 60 pages under tools/<name>/index.html contain NO form and no button. They are
// content pages - "How it works", a worked example, an FAQ - and they are honest about it, ending with
// "Open the interactive <X> Calculator in WorkHive (free sign-in): free with a WorkHive account."
//
// So the real question, and this platform's own lens for it, is whether that HAND-OFF CARRIES CONTEXT. It did
// not. All 60 linked to the bare /engineering-design.html; that page read no parameter and its init ended with
// selectDiscipline('HVAC & Cooling'), so a person who searched for one named calculator, read its page and
// clicked its button arrived at step 1 of a different discipline, to hunt for it among 55 types across six.
// Two of the 60 were worse: the MTBF/MTTR and OEE pages promised an interactive calculator that exists nowhere
// in that registry - those are maintenance KPIs, computed on analytics.html.
//
//   H1 named        the page's CTA link carries ?calc=<slug>, or points at the surface that really computes it
//   H2 resolvable   that slug matches an id in CALC_TYPES_UI, the tool's declared sole source of truth
//   H3 arrives      following the link actually selects that calculator, live
//
//   node tools/prove_calc_handoff.mjs              # every page, static H1+H2; a sample walked live
//   node tools/prove_calc_handoff.mjs --live 6     # walk N of them live
import { chromium } from 'playwright';
import { readdirSync, existsSync, readFileSync } from 'node:fs';
import { SEEDER, signIn } from './prover_harness.mjs';

const LIVE = (() => { const i = process.argv.indexOf('--live'); return i >= 0 ? Number(process.argv[i + 1]) : 4; })();

const slug = (t) => String(t).toLowerCase().replace(/&/g, ' and ').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

// CALC_TYPES_UI is the tool's declared sole source of truth; read it rather than keeping a second copy here.
const js = readFileSync('engineering-design.js', 'utf8');
const open = js.indexOf('{', js.indexOf('const CALC_TYPES_UI = {'));
let depth = 0, close = open;
for (let i = open; i < js.length; i++) { if (js[i] === '{') depth++; else if (js[i] === '}') { depth--; if (!depth) { close = i; break; } } }
const block = js.slice(open, close + 1);
const IDS = new Set([...block.matchAll(/\{\s*id:\s*'([^']+)'/g)].map((m) => slug(m[1])));

// the surfaces that compute a metric the engineering tool does not offer
const ELSEWHERE = { '/analytics.html': /mtbf|mttr|oee/i };

const dirs = readdirSync('tools', { withFileTypes: true })
  .filter((d) => d.isDirectory() && existsSync(`tools/${d.name}/index.html`) && d.name.includes('calculator'))
  .map((d) => d.name);

let bad = 0;
const deep = [];
for (const name of dirs) {
  const src = readFileSync(`tools/${name}/index.html`, 'utf8');
  const cta = src.match(/href="(\/engineering-design\.html[^"]*|\/analytics\.html[^"]*)"/);
  const issues = [];
  if (!cta) issues.push('H1 no hand-off link to a surface that computes anything');
  else {
    const href = cta[1];
    if (href.startsWith('/analytics.html')) {
      const target = readFileSync('analytics.html', 'utf8');
      if (!ELSEWHERE['/analytics.html'].test(target)) issues.push(`H2 ${href} does not compute this metric`);
    } else {
      const q = href.match(/[?&]calc=([^&"]+)/);
      if (!q) issues.push(`H1 the CTA says "Open the interactive ..." and links to ${href} - the calculator it names is not in the link, so the person lands on step 1 of whatever the tool defaults to`);
      else if (!IDS.has(decodeURIComponent(q[1]))) issues.push(`H2 ?calc=${q[1]} matches no id in CALC_TYPES_UI`);
      else deep.push({ name, slug: decodeURIComponent(q[1]) });
    }
  }
  if (issues.length) { bad++; console.log(`  BAD ${name.padEnd(36)} ${issues[0].slice(0, 140)}`); }
}

// H3: follow a sample of the links for real - a slug that resolves in a file is not a person arriving
let liveBad = 0, liveRun = 0;
if (deep.length && LIVE > 0) {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
  await signIn(ctx);
  const step = Math.max(1, Math.floor(deep.length / LIVE));
  for (let i = 0; i < deep.length && liveRun < LIVE; i += step) {
    const d = deep[i];
    liveRun++;
    const p = await ctx.newPage();
    await p.goto(`${SEEDER}/workhive/engineering-design.html?calc=${d.slug}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
    await p.waitForTimeout(12000);
    const got = await p.evaluate(() => {
      const sel = document.querySelector('.calc-card.selected');
      const pill = document.querySelector('.discipline-pill.active');
      const lbl = document.getElementById('step-label');
      return { id: sel && sel.dataset.id, disc: pill && pill.dataset.disc, step: lbl && lbl.innerText.trim() };
    }).catch(() => ({}));
    const ok = got.id && slug(got.id) === d.slug;
    if (!ok) { liveBad++; bad++; }
    console.log(`  ${ok ? 'ok  ' : 'BAD '} ${d.name.padEnd(36)} -> ${got.id || '(nothing selected)'}${got.disc ? ' · ' + got.disc : ''}${got.step ? ' · ' + got.step : ''}`);
    await p.close();
  }
  await b.close();
}
console.log(`${bad ? 'FAIL' : 'PASS'} calc-handoff - ${dirs.length - bad}/${dirs.length} calculator pages hand a person to the calculator they NAMED (${deep.length} deep-link a type in CALC_TYPES_UI, ${liveRun - liveBad}/${liveRun} verified live end to end)`);
process.exitCode = bad ? 1 : 0;
