/**
 * test_prover_signin_key.mjs — the shared sign-in waits for the credential it is about to use, and
 * says something true when the page offers none.
 *
 * WHY THIS EXISTS. `tools/prover_harness.mjs` is the sign-in for 48 provers, and its fallback builds a
 * client from `window.SUPABASE_KEY`. That property exists only because shift-brain.html declares its
 * key with `var`: a top-level `const` creates no window property, and 23 of the platform's 27
 * key-declaring pages use `const`. So the line worked by luck, and the failure it would produce is the
 * worst kind - supabase-js answers "supabaseKey is required.", which names an argument while the real
 * cause is that the page had not run. That message cost this session a config hunt for a problem that
 * did not exist, which is precisely why the fix needs a test and not just a comment.
 *
 * The harness's own self-test is browser-free by design (~2 s, psql + PAGE_QUERY + VIS_JS) and does not
 * touch sign-in at all, so without this file the change would sit behind a gate that cannot see it -
 * a lock that looks closed. A stub is the right instrument here rather than a walk: the behaviour is a
 * predicate and a guard, the page surface it touches is four calls wide (goto, waitForFunction,
 * evaluate, close), and reaching it live would need a browser, a serial slot on an 8GB host, and a
 * degraded connection to make the fallback fire at all.
 *
 * Both directions are asserted. A sign-in that always returns the honest note is as broken as one that
 * never does, and only the pair tells a working guard from a silenced one.
 *
 *   node tools/test_prover_signin_key.mjs
 */
import { readFileSync } from 'node:fs';
import { signIn } from './prover_harness.mjs';

let failures = 0;
const check = (name, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.log(`  FAIL ${name}\n       got  ${JSON.stringify(got)}\n       want ${JSON.stringify(want)}`); }
  else console.log(`  ok   ${name}`);
};

// ── the fake page ────────────────────────────────────────────────────────────
// `signIn` calls goto, then waitForFunction, then evaluate, then close. The stub captures the
// predicate so it can be exercised on its own, and runs the evaluate body against a fake window.
function makeCtx(win) {
  const captured = {};
  const store = {};
  const page = {
    async goto() { captured.went = true; },
    async waitForFunction(fn) { captured.pred = fn; },
    async evaluate(fn, arg) {
      const prevWin = globalThis.window;
      const prevLs = globalThis.localStorage;
      globalThis.window = win;
      globalThis.localStorage = { setItem: (k, v) => { store[k] = v; }, getItem: (k) => store[k] ?? null };
      try { return await fn(arg); }
      finally { globalThis.window = prevWin; globalThis.localStorage = prevLs; }
    },
    async close() { captured.closed = true; },
  };
  return { ctx: { async newPage() { return page; } }, captured, store };
}

// a client that reports a successful sign-in and a named hive
const goodClient = (spy) => ({
  auth: { signInWithPassword: async () => { if (spy) spy.signedIn = true; return { error: null }; } },
  from: () => ({ select: () => ({ eq: () => ({ maybeSingle: async () => ({ data: { name: 'Manila Electronics Assembly' } }) }) }) }),
});

// ── 1. the page built its own client, and exposes NO key ──────────────────────
// the common healthy case, and the one the old code got right by accident: the cached client
// short-circuits before the key is ever read.
{
  const spy = {};
  const win = { _whSupabaseClient: goodClient(spy) };            // no SUPABASE_KEY at all
  const { ctx, store } = makeCtx(win);
  const out = await signIn(ctx);
  check('client present, no key -> signs in', out, true);
  check('client present -> the cached client was used', spy.signedIn === true, true);
  check('client present -> hive name is stored', store.wh_hive_name, 'Manila Electronics Assembly');
}

// ── 2. no client yet, but the page exposes a key ──────────────────────────────
// the fallback path. getDb must receive the page's key, not undefined.
{
  const spy = {};
  const seen = {};
  const win = {
    SUPABASE_KEY: 'sb_publishable_test',
    supabase: { createClient: () => ({}) },
    getDb: (url, key) => { seen.url = url; seen.key = key; return goodClient(spy); },
  };
  const { ctx } = makeCtx(win);
  const out = await signIn(ctx);
  check('key present, no client -> signs in', out, true);
  check('key present -> getDb got the page key', seen.key, 'sb_publishable_test');
  check('key present -> getDb got a url', typeof seen.url === 'string' && seen.url.length > 0, true);
}

// ── 3. the page offers NEITHER ────────────────────────────────────────────────
// the case the library would describe as a missing argument. The harness must name the real cause,
// and must not reach getDb at all - calling it here is what produced the misleading message.
{
  let reached = false;
  const win = { supabase: { createClient: () => ({}) }, getDb: () => { reached = true; return goodClient(); } };
  const { ctx } = makeCtx(win);
  const out = await signIn(ctx);
  check('neither -> returns an honest note, not false', typeof out === 'string' && out.includes('no key'), true);
  check('neither -> getDb is never called', reached, false);
}

// ── 4. the WAIT predicate itself ──────────────────────────────────────────────
// the actual behavioural change. The old predicate was satisfied by getDb + supabase alone, which is
// the exact moment the key may still be missing - so it let the walk proceed into the bad call.
{
  const { ctx, captured } = makeCtx({ _whSupabaseClient: goodClient() });
  await signIn(ctx);
  const pred = captured.pred;
  check('a predicate was passed to waitForFunction', typeof pred === 'function', true);

  const run = (w) => {
    const prev = globalThis.window;
    globalThis.window = w;
    try { return !!pred(); } finally { globalThis.window = prev; }
  };
  check('satisfied by the page client alone', run({ _whSupabaseClient: {} }), true);
  check('satisfied by getDb + supabase + key', run({ getDb: () => {}, supabase: {}, SUPABASE_KEY: 'k' }), true);
  // ↓ the regression this file exists for: this combination used to pass the wait
  check('NOT satisfied by getDb + supabase with no key', run({ getDb: () => {}, supabase: {} }), false);
  check('not satisfied by an empty window', run({}), false);
}

// ── 5. the coupling 44 OTHER tools still rest on ────────────────────────────
// The harness above no longer depends on it, but a repo-wide count found 44 tools that build a client
// from `window.SUPABASE_KEY` WITHOUT waiting for it, against 27 that wait. Every one of them signs in
// on shift-brain.html, and they work only because that page declares its key with `var` - the 4-of-27
// minority style. The day someone makes that line match the majority (`const`, which creates no window
// property) all 44 lose their fallback silently, and a prover that cannot sign in does not fail loudly:
// it walks the product SIGNED OUT. Editing 44 files would be the expensive fix for a one-line coupling,
// so the coupling itself is pinned here, where the reason for it is already written down.
{
  const signInPage = readFileSync('shift-brain.html', 'utf8');
  const declaresVar = /^\s*var\s+SUPABASE_KEY\s*=/m.test(signInPage);
  const declaresConst = /^\s*const\s+SUPABASE_KEY\s*=/m.test(signInPage);
  check('the sign-in page still exposes SUPABASE_KEY on window (declared with var)', declaresVar, true);
  check('the sign-in page has not switched to const, which exposes nothing', declaresConst, false);
}

console.log(failures === 0
  ? '\nself-test OK: the shared sign-in waits for the credential it uses, and names the real cause when there is none'
  : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
