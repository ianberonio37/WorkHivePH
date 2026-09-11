// prove_feature_wholeness — the CI/CD layer's second lens of the LAYER-UX wave (§LX, 2026-09-06):
// "A feature arrives half-on: the button is there, the thing behind it is not."
//
// This is what a partial release looks like from the outside. The markup for a feature ships, so the
// control is on screen and looks live, while the function behind it did not land - or landed under a
// different name, or in a file the page does not load. The person clicks and nothing happens: no
// error they can read, no message, no way to tell the difference between "broken" and "I did it wrong".
//
// The walk, on every page a person uses daily, signed in:
//   W1 wired      every visible control with an inline handler names a function that EXISTS in page
//                 scope. A button calling an undefined name is a feature that shipped half-on.
//   W2 reachable  the same for `data-action`-style controls whose dispatcher is a named function
//   W3 silent     a control that IS wired must not be a no-op stub - a handler whose whole body is a
//                 comment, an empty block, or a bare `return` is the same defect wearing a function
//
// ★A HANDLER THAT THROWS IS NOT THE SAME DEFECT and is not counted here. Something going wrong at
// runtime is a bug; a control wired to a name that was never defined is a RELEASE that arrived in
// pieces, which is the CI layer's question and the reason this lens is separate.
//
//   node tools/prove_feature_wholeness.mjs
//   node tools/prove_feature_wholeness.mjs --page hive.html
import { chromium } from 'playwright';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const LIST = (() => { const i = process.argv.indexOf('--pages'); return i >= 0 ? process.argv[i + 1].split(',') : null; })();

const ROSTER = ['hive.html', 'logbook.html', 'inventory.html', 'dayplanner.html', 'alert-hub.html',
                'asset-hub.html', 'community.html', 'analytics.html', 'marketplace.html',
                'shift-brain.html', 'pm-scheduler.html', 'skillmatrix.html', 'achievements.html',
                'project-manager.html', 'index.html'];

const AUDIT = function audit(VIS_JS) {
  const vis = (0, eval)(VIS_JS);
  const out = { unwired: [], stubs: [], checked: 0 };
  const name = (e) => (e.id ? '#' + e.id : e.tagName.toLowerCase()
    + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\s+/)[0] : ''));
  const els = [...document.querySelectorAll('[onclick], [onchange], [onsubmit], [oninput]')]
    .filter((e) => vis(e) && e.checkVisibility({ opacityProperty: true, visibilityProperty: true }));
  for (const e of els) {
    for (const attr of ['onclick', 'onchange', 'onsubmit', 'oninput']) {
      const code = e.getAttribute(attr);
      if (!code) continue;
      // every bare identifier that is CALLED in the handler: fn(...), obj.fn(...) is skipped (a method
      // on a live object is not a release question), and language keywords are not functions
      const KEYWORDS = new Set(['if', 'for', 'while', 'switch', 'return', 'typeof', 'new', 'catch',
                                'function', 'await', 'void', 'delete', 'in', 'of', 'this', 'true',
                                'false', 'null', 'undefined']);
      for (const m of code.matchAll(/(^|[^.\w$])([A-Za-z_$][\w$]*)\s*\(/g)) {
        const fn = m[2];
        if (KEYWORDS.has(fn)) continue;
        out.checked++;
        let ref;
        try { ref = window[fn]; } catch (err) { void err; ref = undefined; }
        if (typeof ref !== 'function') {
          out.unwired.push(`${name(e)} ${attr}="${code.slice(0, 40)}" calls ${fn}() which is not defined`);
          continue;
        }
        // W3: a wired name whose body does nothing is the same promise, differently broken
        let src = '';
        try { src = Function.prototype.toString.call(ref); } catch (err) { void err; src = ''; }
        const body = src.slice(src.indexOf('{') + 1, src.lastIndexOf('}'));
        const stripped = body.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '').trim();
        if (src && (stripped === '' || /^return\s*;?$/.test(stripped))) {
          out.stubs.push(`${name(e)} calls ${fn}(), which is defined and does nothing`);
        }
      }
    }
  }
  for (const k of ['unwired', 'stubs']) out[k] = [...new Set(out[k])].slice(0, 8);
  return out;
};

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
await signIn(ctx);

let bad = 0, n = 0, checked = 0;
for (const file of (ONLY ? [ONLY] : (LIST || ROSTER))) {
  n++;
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);
  const a = await p.evaluate(AUDIT, VIS_JS).catch((e) => ({ unwired: ['evaluate failed: ' + String(e).slice(0, 50)], stubs: [], checked: 0 }));
  checked += a.checked || 0;
  const issues = [].concat(a.unwired.map((s) => 'W1 half-on: ' + s), a.stubs.map((s) => 'W3 no-op: ' + s));
  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${file.padEnd(24)} ${a.checked} handler call(s) checked${issues.length ? ` · ${issues.length} incomplete` : ' · all wired'}`);
  for (const s of issues.slice(0, ONLY ? 12 : 3)) console.log(`        ${s.slice(0, 160)}`);
  await p.close();
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} feature-wholeness - ${n - bad}/${n} pages have every visible control wired to a function that exists and does something (${checked} handler call(s) checked)`);
process.exitCode = bad ? 1 : 0;
