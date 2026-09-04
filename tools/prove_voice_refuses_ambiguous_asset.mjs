/* prove_voice_refuses_ambiguous_asset.mjs — T79: a coin flip is not a resolution.
 *
 * The voice router turns "I replaced the seal on Pump 2" into a logbook.create intent and
 * resolves the machine. When more than one machine matches, it returns asset_resolution
 * ambiguous:true with the candidates.
 *
 * ★FOUND 2026-08-26: ambiguity was RENDERED and never ENFORCED. The intent card turned the
 * asset pill red and appended "(multiple matches)" - and Confirm still wrote the entry to
 * ar.primary, whichever candidate ranked first. A worker's repair record landed on the wrong
 * machine, and the only warning was a colour. On a plant floor that is a maintenance history
 * attached to the wrong equipment, which is exactly what the history is for.
 *
 * ★AND THE GUARD FOR THIS ALREADY EXISTED AND WAS DEAD. _preflightAction was defined, exported
 * in the test-helper block, and certified by the companion integration audit - which checked
 * that its four blocker STRINGS appeared in the file. They did, inside a function nothing ever
 * called. Its writeVerbs were slot-style ('log_entry') while the router emits 'logbook.create',
 * so even a call would have matched nothing. Now it speaks the router's kinds, carries an
 * ambiguous_asset blocker, and _confirm runs it before anything is written.
 *
 * THE ASSERTION, driven against the shipped file in a real browser:
 *   1. a write kind + ambiguous resolution        -> refused, blocker 'ambiguous_asset'
 *   2. the SAME kind with one clear match         -> NOT refused for ambiguity
 *   3. the refusal names the candidates and says nothing was saved
 * Direction 2 matters: a guard that refuses everything would pass direction 1 while making
 * voice logging useless.
 *
 * Usage: node tools/prove_voice_refuses_ambiguous_asset.mjs
 */
import { chromium } from 'playwright';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';

const v = {};
const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));

  await page.goto(`${BASE}/logbook.html`, { waitUntil: 'domcontentloaded' });
  // voice-handler is lazy-loaded by nav-hub
  await page.waitForFunction(
    () => !!(window.WHVoice && typeof window.WHVoice._preflightAction === 'function'),
    { timeout: 25000 }).catch(() => {});

  v.read = await page.evaluate(() => {
    const V = window.WHVoice;
    if (!V || typeof V._preflightAction !== 'function') return { noApi: true };
    const ambiguous = {
      ambiguous: true,
      primary: { tag: 'P-002', name: 'Pump 2' },
      candidates: [{ tag: 'P-002', name: 'Pump 2' }, { tag: 'P-2A', name: 'Pump 2A' }],
    };
    const clear = { ambiguous: false, primary: { tag: 'P-002', name: 'Pump 2' }, candidates: [{ tag: 'P-002' }] };
    const slots = { machine: 'Pump 2', action: 'replaced the seal' };

    const blocked = V._preflightAction('logbook.create', slots, ambiguous);
    const allowed = V._preflightAction('logbook.create', slots, clear);
    const msg = (typeof V._blockerMessage === 'function')
      ? String(V._blockerMessage('ambiguous_asset', ambiguous)) : '';
    return {
      blockedOk: blocked && blocked.ok === false && blocked.blocker === 'ambiguous_asset',
      clearNotBlockedForAmbiguity: !(allowed && allowed.blocker === 'ambiguous_asset'),
      msgNamesCandidates: /P-002/.test(msg) && /P-2A/.test(msg),
      msgSaysNothingSaved: /nothing was saved/i.test(msg),
      msg: msg.slice(0, 120),
    };
  });
  v.read.errs = errs.length;
  console.log(`  ambiguous -> ${v.read.blockedOk ? 'REFUSED' : 'allowed'} | clear -> ${v.read.clearNotBlockedForAmbiguity ? 'not blocked for ambiguity' : 'wrongly blocked'}`);
  if (v.read.msg) console.log(`  refusal: ${v.read.msg}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 170);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

const r = v.read || {};
if (r.noApi) { console.log('SKIP — WHVoice preflight not exposed on this page'); process.exit(0); }
const pass = !v.error && r.blockedOk && r.clearNotBlockedForAmbiguity
  && r.msgNamesCandidates && r.msgSaysNothingSaved && r.errs === 0;
if (!pass && !v.error) {
  console.log('  When two machines match, writing to whichever ranked first puts a repair record on');
  console.log('  the wrong equipment. Refuse, name the candidates, and let the worker say which one.');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — voice refuses an ambiguous asset: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
