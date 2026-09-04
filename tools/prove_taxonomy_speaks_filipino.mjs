/* prove_taxonomy_speaks_filipino.mjs — T45: the shared failure voice is bilingual (2026-08-27).
 *
 * Every page is bilingual through _t(en, fil). The error taxonomy they all delegate to was not, so
 * a worker running the FIL toggle got Filipino chrome and an ENGLISH sentence at the exact moment
 * something failed and precision mattered most.
 *
 * THE ORACLE: drive each helper twice - once under WH_LANG='en', once under 'fil' - and require the
 * translated branches to actually DIFFER. Run in the page, because _t reads window.WH_LANG and the
 * helpers live on window; a source grep for "_t(" would only prove the call was written, not that
 * the string changes.
 *
 * ★AND TWO THINGS MUST NOT TRANSLATE, asserted as SAME rather than ignored:
 *   - the caller-supplied `fallback` is the PAGE's own English sentence to own.
 *   - whWriteError's deliberate-guard passthrough returns a policy refusal that explained itself
 *     ("Listing needs PHP50 credits held and you have 0 available"). Rewriting someone else's
 *     explanation in another language is replacement, not translation.
 * A gate that only checked "everything differs" would call both of those defects.
 *
 * Read-only: loads a page, calls pure functions. Writes nothing.
 *
 * Usage: node tools/prove_taxonomy_speaks_filipino.mjs
 */
import { chromium } from 'playwright';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';

const browser = await chromium.launch();
let rows = [];
try {
  const page = await (await browser.newContext()).newPage();
  await page.goto(`${SEEDER}/index.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForFunction(() => typeof window._t === 'function'
    && typeof window.whAiError === 'function', { timeout: 20000 });

  rows = await page.evaluate(async () => {
    // AWAITED: whFnError is async (it reads the FunctionsHttpError body), so a synchronous call
    // stringifies to "[object Promise]" and every comparison becomes meaningless-but-equal. The
    // sync helpers are unaffected by awaiting a non-promise, so one shape covers both.
    const both = async (fn) => {
      window.WH_LANG = 'en'; const en = await fn();
      window.WH_LANG = 'fil'; const fil = await fn();
      window.WH_LANG = 'en';
      return { en: String(en), fil: String(fil) };
    };
    const cases = [
      // [name, callable, mustDiffer]
      ['ai:session',   () => window.whAiError({ message: '401 unauthorized' }, 'F.'), true],
      ['ai:quota',     () => window.whAiError({ message: '429 rate limit' }, 'F.'), true],
      ['ai:busy',      () => window.whAiError({ message: '503 unavailable' }, 'F.'), true],
      ['ai:network',   () => window.whAiError({ message: 'failed to fetch' }, 'F.'), true],
      ['read:session', () => window.whReadError({ message: 'JWT expired' }, 'the activity log'), true],
      ['read:denied',  () => window.whReadError({ code: '42501', message: 'permission denied' }, 'the activity log'), true],
      ['read:network', () => window.whReadError({ message: 'failed to fetch' }, 'the activity log'), true],
      ['write:session', () => window.whWriteError({ message: 'JWT expired' }, 'Save failed.'), true],
      ['write:collision', () => window.whWriteError({ code: '23505', message: 'duplicate key value' }, 'Save failed.'), true],
      ['voice:denied', () => window.whVoiceError('not-allowed'), true],
      ['voice:nomic',  () => window.whVoiceError('audio-capture'), true],
      ['voice:network', () => window.whVoiceError('network'), true],
      // whFnError owns exactly one sentence; its other paths return the function's own message
      // or delegate to whAiError. No fallback passed, so its own string is what comes back.
      ['fn:generic',   () => window.whFnError({}, ''), true],
      // MUST NOT translate:
      ['keep:fallback', () => window.whWriteError({ message: 'something odd' }, 'Save failed.'), false],
      ['keep:guard',    () => window.whWriteError({ code: 'P0001', message: 'Listing needs PHP50 credits held and you have 0 available' }, 'F.'), false],
    ];
    const out = [];
    for (const [name, fn, mustDiffer] of cases) {
      const r = await both(fn);
      out.push({ name, mustDiffer, differs: r.en !== r.fil, fil: r.fil.slice(0, 70) });
    }
    return out;
  });
} catch (e) {
  console.log('probe error:', String(e).slice(0, 200));
} finally {
  await browser.close();
}

const bad = rows.filter((r) => r.differs !== r.mustDiffer);
for (const r of rows) {
  const ok = r.differs === r.mustDiffer ? 'ok ' : 'RED';
  console.log(`  ${ok} ${r.name.padEnd(16)} differs=${String(r.differs).padEnd(5)} ${r.fil}`);
}
console.log(`\n${(!rows.length || bad.length) ? 'FAIL' : 'PASS'} — taxonomy speaks Filipino: `
  + `${rows.length - bad.length}/${rows.length} branches behave`
  + (rows.length ? '' : ' (nothing measured - helpers never loaded)'));
process.exit((!rows.length || bad.length) ? 1 : 0);
