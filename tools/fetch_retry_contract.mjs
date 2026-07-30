// Teeth test for the fetchWithTimeout retry. Four cases, and the two that must NOT retry matter most:
// a retried POST is how one payment becomes two, and a silently doubled timeout budget breaks the contract
// every caller reasons about.
import fs from 'node:fs';

// Read utils.js relative to this file, never by absolute path: the repo lives under a directory containing an
// ampersand, and hard-coded paths through it are how tooling in this project breaks.
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const __root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const src = fs.readFileSync(path.join(__root, 'utils.js'), 'utf8');

// Lift just the helper + its delay constant out of utils.js, so the test exercises the SHIPPED text rather
// than a copy that can drift from it.
const start = src.indexOf('const _FWT_RETRY_DELAY_MS');
const end = src.indexOf('if (typeof window !== \'undefined\') window.fetchWithTimeout');
if (start < 0 || end < 0) { console.log('FAIL could not locate fetchWithTimeout in utils.js'); process.exit(1); }
const body = src.slice(start, end);

let calls = [];
globalThis.fetch = async (url, opts) => {
  calls.push({ method: (opts && opts.method) || 'GET' });
  const plan = globalThis.__plan.shift();
  if (plan === 'transport') throw new TypeError('Failed to fetch');
  if (plan === 'abort') { const e = new Error('aborted'); e.name = 'AbortError'; throw e; }
  return { ok: true, status: 200, _n: calls.length };
};

const fn = new Function(body + '; return fetchWithTimeout;')();

let pass = 0, fail = 0;
const check = (name, cond, detail) => {
  if (cond) { pass++; console.log(`  PASS  ${name}`); }
  else { fail++; console.log(`  FAIL  ${name} — ${detail}`); }
};

// 1. GET + one transport blip -> retried once, resolves on the second attempt. This is the flake the whole
//    change exists for.
calls = []; globalThis.__plan = ['transport', 'ok'];
let r = await fn('http://x/read', { method: 'GET' }, 5000);
check('GET retries once on a transport failure and succeeds', r && r.ok && calls.length === 2,
      `attempts=${calls.length} result=${JSON.stringify(r)}`);

// 2. POST + the same blip -> NOT retried, the error propagates. A retried write is the failure mode that
//    matters, so this is the assertion that licenses the whole feature.
calls = []; globalThis.__plan = ['transport', 'ok'];
let threw = null;
try { await fn('http://x/write', { method: 'POST', body: '{}' }, 5000); } catch (e) { threw = e; }
check('POST is NEVER retried', threw instanceof TypeError && calls.length === 1,
      `attempts=${calls.length} threw=${threw && threw.name}`);

// 3. A timeout still returns null on the FIRST attempt. Retrying here would silently double a budget the
//    caller chose, and three callers were recently fixed for mis-handling exactly this null.
calls = []; globalThis.__plan = ['abort', 'ok'];
r = await fn('http://x/read', { method: 'GET' }, 5000);
check('AbortError returns null without retrying', r === null && calls.length === 1,
      `attempts=${calls.length} result=${r}`);

// 4. A persistently dead endpoint fails fast — exactly two attempts, not a loop. The recursion guard is the
//    only thing standing between "one retry" and an unbounded budget.
calls = []; globalThis.__plan = ['transport', 'transport'];
threw = null;
try { await fn('http://x/read', {}, 5000); } catch (e) { threw = e; }
check('a dead endpoint stops after exactly 2 attempts (no method = GET)',
      threw instanceof TypeError && calls.length === 2, `attempts=${calls.length}`);

console.log(`\n  ${pass} pass · ${fail} fail`);
process.exit(fail ? 1 : 0);
