/**
 * test_browser_floor_retry.mjs — browser-floor.js asks a second time before it tells a person the
 * page failed, and it keeps the integrity pin when it does.
 *
 * WHY THIS EXISTS AS A UNIT TEST RATHER THAN A WALK. The behaviour under test only appears when a
 * request is DROPPED, and the only instrument that can drop one is the journey prover's `offline-3g`
 * condition (it aborts about one request in twelve) - which needs a browser, a serial slot on an 8GB
 * host, and roughly forty minutes to reach the page in question. That is a long way to go to learn
 * whether an if-statement fired. The DOM this file touches is four calls wide (querySelectorAll,
 * createElement, getAttribute/setAttribute, appendChild), so a stub reproduces it exactly and the
 * walk stays the check on whether the PERSON gets their page - which is what a walk is good at.
 *
 * Both directions are asserted, because a retry that always paints the banner and a retry that never
 * paints it are equally broken, and only the pair distinguishes a working fix from a silenced one.
 *
 *   node tools/test_browser_floor_retry.mjs
 */
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const SRC = 'vendor/supabase-js-2.110.0.min.js';
const SRI = 'sha384-DjOvX/sJLsmbMrw4wTvf6l3kiGBjdxyOO6X2MTFwOOXGkjN/mE08BoDzrpaaIjil';

function makeDom({ clientArrives }) {
  const appended = [];
  const banners = [];
  const originalTag = {
    src: SRC,
    getAttribute: (k) => (k === 'integrity' ? SRI : k === 'crossorigin' ? 'anonymous' : null),
  };
  const doc = {
    readyState: 'complete',
    body: { firstChild: null, insertBefore: (el) => banners.push(el) },
    head: { appendChild: (el) => { appended.push(el); } },
    addEventListener() {},
    getElementById: (id) => banners.find((b) => b.id === id) || null,
    querySelectorAll: (sel) => (sel.indexOf('supabase') >= 0 ? [originalTag] : []),
    createElement: () => ({
      setAttribute(k, v) { this[k] = v; },
      getAttribute(k) { return this[k] ?? null; },
      set innerHTML(v) { this._html = v; },
      get innerHTML() { return this._html; },
      style: { cssText: '' },
    }),
  };
  const win = { document: doc, location: { origin: 'http://127.0.0.1:5000' }, addEventListener() {} };
  const ctx = vm.createContext({ window: win, document: doc, setTimeout, clearTimeout, console });
  ctx.window.document = doc;
  vm.runInContext(readFileSync('browser-floor.js', 'utf8'), ctx);
  return { ctx, appended, banners, clientArrives };
}

let failures = 0;
const check = (label, cond) => { if (!cond) { failures++; console.log(`  FAIL ${label}`); } else console.log(`  ok   ${label}`); };

// ── 1. the client is missing: it must RETRY and stay silent, not warn on the first drop ──────────
const a = makeDom({ clientArrives: false });
check('a retry script was appended', a.appended.length === 1);
check('the retry asks for the SAME src', a.appended[0] && a.appended[0].src === SRC);
check('the retry KEEPS the integrity pin', a.appended[0] && a.appended[0].integrity === SRI);
check('the retry keeps crossorigin', a.appended[0] && a.appended[0].crossorigin === 'anonymous');
check('no banner while the second attempt is in flight', a.banners.length === 0);

// ── 2. the retry SUCCEEDS: the person is never told anything ──────────────────────────────────────
a.ctx.window.supabase = {};
a.appended[0].onload();
check('a successful retry paints no banner', a.banners.length === 0);

// ── 3. the retry FAILS: the banner must still appear - rarer and truer, never quieter ─────────────
const b = makeDom({ clientArrives: false });
b.appended[0].onerror();
check('a failed retry still warns the person', b.banners.length === 1);
check('the warning is the wh-client-missing banner', b.banners[0] && b.banners[0].id === 'wh-client-missing');
check('it still names the remedy in both languages',
  b.banners[0] && /did not arrive/.test(b.banners[0].innerHTML) && /hindi dumating/i.test(b.banners[0].innerHTML));

// ── 4. it retries at most ONCE - a dropped line must not become a request loop ────────────────────
const before = b.appended.length;
b.appended[0].onerror();
check('a second failure does not queue another retry', b.appended.length === before);

// ── 5. ANY dropped shell script gets one more chance, not just the client ─────────────────────────
// W3521 (hive -> skillmatrix) and W3618 (pm-scheduler -> analytics) both reported hub=0 - no nav at
// all - while the hops on either side kept theirs. That is nav-hub.js losing its turn at the 1-in-12
// abort, and nothing was watching it. A resource error does not bubble, so this only works from the
// CAPTURE phase; these cases pin that, and pin that a foreign script is left alone.
function domWithErrorListener() {
  const appended = [];
  let handler = null;
  const doc = {
    readyState: 'complete',
    body: { firstChild: null, insertBefore() {} },
    head: { appendChild: (el) => appended.push(el) },
    documentElement: { appendChild: (el) => appended.push(el) },
    addEventListener() {},
    getElementById: () => null,
    querySelectorAll: () => [],
    createElement: () => ({
      attrs: {},
      setAttribute(k, v) { this.attrs[k] = v; this[k] = v; },
      getAttribute(k) { return this.attrs[k] ?? null; },
      style: { cssText: '' },
    }),
  };
  const win = {
    document: doc,
    location: { origin: 'http://127.0.0.1:5000' },
    addEventListener(type, fn, capture) { if (type === 'error' && capture === true) handler = fn; },
  };
  const ctx = vm.createContext({ window: win, document: doc, setTimeout, clearTimeout, console });
  vm.runInContext(readFileSync('browser-floor.js', 'utf8'), ctx);
  return { fire: (target) => handler && handler({ target }), appended, armed: () => handler !== null };
}
const scriptTag = (src, extra = {}) => {
  const attrs = { ...extra };
  return { tagName: 'SCRIPT', src, getAttribute: (k) => attrs[k] ?? null, setAttribute: (k, v) => { attrs[k] = v; } };
};

const c = domWithErrorListener();
check('the retry listener is armed in the CAPTURE phase', c.armed());
c.fire(scriptTag('http://127.0.0.1:5000/nav-hub.js'));
check('a dropped nav-hub.js is re-requested', c.appended.length === 1 && /nav-hub\.js$/.test(c.appended[0].src));
check('the replacement is marked so it cannot loop', c.appended[0] && c.appended[0].getAttribute('data-wh-retried') === '1');

const already = scriptTag('http://127.0.0.1:5000/utils.js', { 'data-wh-retried': '1' });
const n1 = c.appended.length;
c.fire(already);
check('a tag that already retried is left alone', c.appended.length === n1);

c.fire(scriptTag('https://cdn.example.com/thing.js'));
check('a third-party script is NOT re-requested', c.appended.length === n1);

c.fire(scriptTag('http://127.0.0.1:5000/utils.js', { integrity: SRI, crossorigin: 'anonymous' }));
const last = c.appended[c.appended.length - 1];
check('a shell retry carries its integrity pin', last && last.getAttribute('integrity') === SRI);

c.fire({ tagName: 'IMG', src: 'http://127.0.0.1:5000/logo.png', getAttribute: () => null, setAttribute() {} });
check('a failed IMAGE is not treated as a script', c.appended.length === n1 + 1);

console.log(failures ? `\nFAIL browser-floor retry (${failures})` : '\nPASS browser-floor retry — asks twice, keeps the pin, still warns when it is genuinely gone, and any dropped shell script gets one more chance');
process.exit(failures ? 1 : 0);
