/**
 * test_sw_install_survives_loss.mjs — one lost request must not cost the whole service worker.
 *
 * WHAT THIS PINS. sw.js's install handler used `cache.addAll(SHELL_FILES)`, which is ATOMIC: any one
 * failed entry rejects, the rejection escapes waitUntil, and the worker goes from `installing` to
 * `redundant`. The person is then left with NO worker - no precache, no offline fallback, no
 * network-first copy - and nothing tells them. Proven in a browser under the journey prover's own
 * offline-3g emulation: `registered:true, state:installing, finalState:REDUNDANT`, with sw.js itself
 * never among the dropped requests.
 *
 * The arithmetic is why this is not merely a stress-test concern. The install survives only if every
 * one of the 65 entries lands, so at offline-3g's 1-in-12 that is (11/12)^65 = 0.35%; at an ordinary
 * 1% request loss it is (0.99)^65 = 52%, meaning half of real plant-floor installs fail completely.
 *
 * WHY A SOURCE TEST RATHER THAN A BROWSER ONE. The browser proof exists and was how this was found,
 * but it costs a launch, a serial slot on an 8GB host and about a minute; and the property that must
 * never come back is a SHAPE - "install does not reject when one entry fails". That shape is readable
 * in the file, and reading it costs milliseconds, so this can run on every board. The live proof is
 * recorded in the CACHE_NAME bump note beside the numbers it produced.
 *
 * Both directions are asserted: a file that tolerates losses passes, and each way of reintroducing the
 * atomic install fails. A test that only checks for the good shape would stay green if someone added
 * `cache.addAll` back beside the tolerant path.
 *
 *   node tools/test_sw_install_survives_loss.mjs
 */
import { readFileSync } from 'node:fs';

let failures = 0;
const check = (name, got, want) => {
  const ok = got === want;
  if (!ok) { failures++; console.log(`  FAIL ${name}\n       got ${got}, want ${want}`); }
  else console.log(`  ok   ${name}`);
};

/** The install handler's body, brace-matched from the listener so nothing outside it is read. */
function installBody(src) {
  const at = src.indexOf("addEventListener('install'");
  if (at < 0) return '';
  const open = src.indexOf('{', at);
  let depth = 0;
  for (let i = open; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(open, i + 1); }
  }
  return '';
}

const tolerant = (body) => ({
  // the install must not hand waitUntil a promise that rejects on one bad entry
  noAddAll: !/\bcache\.addAll\s*\(/.test(body) && !/\baddAll\s*\(\s*SHELL_FILES/.test(body),
  // it must add entries individually, so one can fail alone
  addsIndividually: /\bcache\.add\s*\(/.test(body),
  // and it must swallow the failure of one
  catchesPerFile: /catch\s*\(/.test(body),
  // over the whole list, not a hand-picked few
  coversWholeList: /SHELL_FILES\s*\.\s*map\s*\(/.test(body),
});

const SRC = readFileSync('sw.js', 'utf8');
const body = installBody(SRC);

console.log('the shipped worker:');
check('an install handler was found', body.length > 0, true);
const live = tolerant(body);
check('install does not use the atomic addAll', live.noAddAll, true);
check('install adds entries one at a time', live.addsIndividually, true);
check('a failed entry is caught, not thrown', live.catchesPerFile, true);
check('every SHELL_FILES entry is attempted', live.coversWholeList, true);
// a retry is what turned 65-of-65 into a real result under loss rather than a partial cache
check('a dropped entry is asked for again', /attempt\s*<\s*[2-9]|for\s*\(\s*let\s+attempt/.test(body), true);

// ── the other direction: each way of reintroducing the bug must be caught ─────
console.log('\ndeliberately broken workers:');
const BROKEN = {
  'the original atomic install':
    `{ e.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL_FILES))); self.skipWaiting(); }`,
  'addAll smuggled in beside the tolerant path':
    body.replace('const missed = [];', 'const missed = []; await cache.addAll(SHELL_FILES);'),
  'per-file add with the catch removed':
    `{ e.waitUntil(caches.open(CACHE_NAME).then(async (cache) => {
        await Promise.all(SHELL_FILES.map(async (f) => { await cache.add(f); })); })); }`,
  'only a hand-picked few precached':
    `{ e.waitUntil(caches.open(CACHE_NAME).then(async (cache) => {
        for (const f of ['/offline-fallback.html']) { try { await cache.add(f); } catch (e) {} } })); }`,
};
for (const [label, b] of Object.entries(BROKEN)) {
  const t = tolerant(b);
  const passes = t.noAddAll && t.addsIndividually && t.catchesPerFile && t.coversWholeList;
  check(`caught: ${label}`, passes, false);
}

console.log(failures === 0
  ? '\nself-test OK: one lost request cannot cost the whole install, and every way back to atomic is caught'
  : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
