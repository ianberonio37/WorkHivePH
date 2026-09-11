// prove_release_visibility — the CI/CD layer's first lens of the LAYER-UX wave (§LX, 2026-09-06):
// "You cannot tell which version you are on when you report that something broke."
//
// Measured before the fix: NOT ONE page on the platform carried a build or version identifier a person
// could find and quote. A report arrived as "it broke on my screen" with no way for anyone to know
// whether that screen was even running the code that had been fixed - which makes every "cannot
// reproduce" ambiguous between a fixed bug and a stale client.
//
// ★THE VERSION MUST BE THE ONE THE PERSON IS RUNNING, NOT THE ONE THAT SHOULD BE DEPLOYED. A constant
// stamped at build time answers a different question - it says what the server shipped, and it says it
// identically to someone whose browser is serving a shell from three deploys ago. The service worker
// names its cache `workhive-shell-vNNN` and bumps it on every shell change, so the cache the browser
// actually holds IS the answer, and it disagrees with the build constant exactly when that matters.
//
//   V1 available   whBuildVersion() exists platform-wide (it ships in utils.js, which every page loads)
//   V2 visible     a person can SEE the version somewhere without opening devtools
//   V3 truthful    the version shown equals the shell cache the browser is serving from
//   V4 current     that cache name matches sw.js's active CACHE_NAME, so the number is not a fossil
//
//   node tools/prove_release_visibility.mjs
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { SEEDER, PAGE_QUERY } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();

// where a person in trouble actually looks: the public trust surface, plus the pages they live on
const SHOWS_VERSION = ['status.html'];
const LOADS_HELPER = ['hive.html', 'logbook.html', 'inventory.html', 'dayplanner.html', 'alert-hub.html',
                      'asset-hub.html', 'community.html', 'analytics.html', 'marketplace.html',
                      'shift-brain.html', 'pm-scheduler.html', 'skillmatrix.html', 'achievements.html',
                      'project-manager.html', 'index.html'];

// the version sw.js declares right now - the active line, not the commented bump history above it
const swSrc = readFileSync('sw.js', 'utf8');
const active = swSrc.split(/\r?\n/).find((l) => /^const CACHE_NAME/.test(l)) || '';
const DECLARED = (active.match(/'(workhive-shell-v[\d.]+)'/) || [, ''])[1];

// service workers must RUN here: the thing under test is the cache the browser holds
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });

let bad = 0, n = 0;
{
  const warm = await ctx.newPage();
  await warm.goto(`${SEEDER}/workhive/index.html`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await warm.waitForTimeout(9000);
  await warm.reload({ waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await warm.waitForTimeout(7000);
  const primed = await warm.evaluate(async () => ('caches' in window ? (await caches.keys()).filter((k) => /workhive-shell/.test(k)) : [])).catch(() => []);
  console.log(`  warm  primed the shell by opening the app once: ${primed.join(', ') || '(none cached - the worker did not install)'}`);
  await warm.close();
}
if (!DECLARED) {
  console.log('  BAD (sw.js)                    no active CACHE_NAME line - the shell has no declared version');
  bad++;
}

for (const file of (ONLY ? [ONLY] : SHOWS_VERSION)) {
  n++;
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(9000);                       // the service worker has to install and claim first
  await p.reload({ waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(6000);
  const r = await p.evaluate(async () => {
    const el = document.getElementById('build-version');
    const keys = ('caches' in window) ? await caches.keys() : [];
    return {
      helper: typeof window.whBuildVersion,
      shown: el ? (el.textContent || '').trim() : null,
      visible: !!(el && el.checkVisibility && el.checkVisibility({ opacityProperty: true, visibilityProperty: true })),
      shell: keys.filter((k) => /^workhive-shell-v/.test(k)).sort().pop() || '',
    };
  }).catch(() => ({ helper: 'missing', shown: null, visible: false, shell: '' }));

  const issues = [];
  if (r.helper !== 'function') issues.push('V1 whBuildVersion() is not available on this page');
  if (r.shown === null) issues.push('V2 no version is rendered anywhere a person can see');
  else if (!r.visible) issues.push('V2 the version element exists but is not visible');
  if (r.shell) {
    const want = r.shell.replace('workhive-shell-', '');
    if (r.shown && !r.shown.includes(want)) issues.push(`V3 shows "${r.shown}" while the browser is serving ${r.shell}`);
    if (DECLARED && r.shell !== DECLARED) issues.push(`V4 the browser holds ${r.shell} while sw.js declares ${DECLARED} - a person would quote a fossil`);
  } else if (r.shown && !/unknown/i.test(r.shown)) {
    issues.push(`V3 shows "${r.shown}" with no cached shell to back it - a version that cannot be true`);
  }

  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${file.padEnd(22)} shows "${r.shown ?? '(nothing)'}" · browser holds ${r.shell || '(no shell cached yet)'}`);
  for (const s of issues) console.log(`        ${s.slice(0, 160)}`);
  await p.close();
}

// the helper has to be reachable from the pages people live on, not only where it is displayed
let missing = [];
for (const file of LOADS_HELPER) {
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(3500);
  const ok = await p.evaluate(() => typeof window.whBuildVersion === 'function').catch(() => false);
  if (!ok) missing.push(file);
  await p.close();
}
if (missing.length) { bad++; console.log(`  BAD helper missing on ${missing.length} page(s): ${missing.slice(0, 6).join(', ')}`); }
else console.log(`  ok  whBuildVersion() reachable on all ${LOADS_HELPER.length} daily pages`);

await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} release-visibility - a person can find and quote the version they are actually running (sw.js declares ${DECLARED || 'nothing'})`);
process.exitCode = bad ? 1 : 0;
