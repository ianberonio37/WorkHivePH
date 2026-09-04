/* prove_numeric_paste.mjs — T123: what a pasted quantity actually does (2026-08-26).
 *
 * ★THIS FILE EXISTS BECAUSE THE FIRST FINDING WAS WRONG, AND THE RESURRECTION CAUGHT IT.
 *
 * The first measurement set `el.value = "1,500"` directly and watched the field go empty with
 * validity VALID — the HTML value-sanitization algorithm doing exactly what it is specified to do.
 * I wrote that up as "pasting a thousands separator silently empties the box". Then the resurrection
 * ran the finished prover against the PRE-FIX utils.js and four of the five cases passed anyway:
 * with a REAL clipboard, Chromium's paste pipeline already strips the comma, the spaces and the
 * trailing unit before the value is sanitized. ASSIGNING a value and PASTING one are different
 * mechanisms, and only one of them is what a person does.
 *
 * WHAT IS ACTUALLY MEASURED, pre-fix, on the real page with a real clipboard:
 *   "450"    -> 450     fine
 *   "1,500"  -> 1500    Chromium already normalizes
 *   " 12 "   -> 12      already normalizes
 *   "12 pcs" -> 12      already normalizes
 *   "abc"    -> ""      EMPTIED IN SILENCE — the one real defect
 *
 * So the measured defect is narrow and worth fixing on its own terms: an unparseable paste blanks
 * the box and says nothing, in a field where the blank is easy to miss and the consequence is
 * submitting no quantity. whCleanNumericPaste now announces instead.
 *
 * The normalization the helper also performs is HARDENING, NOT A MEASURED FIX, and is labelled that
 * way deliberately: it makes the platform's behaviour its own rather than depending on one engine's
 * undocumented paste filtering. Whether other engines empty the field instead is UNMEASURED here —
 * only Chromium is installed — and this file does not claim otherwise.
 *
 * ★AND THE PROBE USES A REAL CLIPBOARD, NEVER A SYNTHETIC EVENT. Dispatching
 * `new ClipboardEvent('paste', {clipboardData})` works for the dirty cases but not the clean one:
 * for an already-clean value the handler deliberately does nothing and lets the browser paste
 * natively, and a synthetic event has no clipboard behind it, so the field came back empty and
 * looked like a regression. That was the second false reading in this one trajectory.
 *
 * FIVE CASES: 450 -> 450 (the native path still works), 1,500 -> 1500, " 12 " -> 12, 12 pcs -> 12,
 * and abc -> "" WITH AN ANNOUNCEMENT — the last being the assertion that encodes the real defect.
 *
 * Non-writing: opens the Add Part modal, types into a field, submits nothing.
 *
 * Usage: node tools/prove_numeric_paste.mjs
 */
import { chromium } from 'playwright';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };

const CASES = [
  { paste: '450',     expect: '450'  },
  { paste: '1,500',   expect: '1500' },
  { paste: ' 12 ',    expect: '12'   },
  { paste: '12 pcs',  expect: '12'   },
  { paste: 'abc',     expect: ''     , mustAnnounce: true },
];

const browser = await chromium.launch();
const v = { cases: [], announced: null };
try {
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 }, serviceWorkers: 'block',
    permissions: ['clipboard-read', 'clipboard-write'],
  });
  const page = await ctx.newPage();

  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!(window.supabase && typeof window.supabase.createClient === 'function'), { timeout: 25000 });
  await page.evaluate(async ({ hive }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    await db.auth.signInWithPassword({ email: 'bryangarcia@auth.workhiveph.com', password: 'test1234' });
    try {
      localStorage.setItem('wh_worker_name', 'Bryan Garcia');
      localStorage.setItem('wh_last_worker', 'Bryan Garcia');
      localStorage.setItem('wh_active_hive_id', hive.id);
      localStorage.setItem('wh_hive_id', hive.id);
      localStorage.setItem('wh_hive_name', hive.name);
    } catch (_) { /* empty-catch-allow: identity seeding is best-effort */ }
  }, { hive: HIVE });

  await page.goto(`${SEEDER}/inventory.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  // AUTH IS PART OF THE INSTRUMENT: signed out this page bounces to the sign-in wall and #f-qty
  // does not exist, which an earlier run of this probe hit. Assert where we actually are.
  const path = await page.evaluate(() => location.pathname);
  if (!/inventory\.html$/.test(path)) throw new Error(`not on inventory (${path}) — sign-in did not hold`);

  await page.evaluate(() => openAddModal());
  await page.waitForTimeout(800);
  if (!(await page.isVisible('#f-qty'))) throw new Error('#f-qty not visible — the Add Part modal did not open');

  for (const c of CASES) {
    await page.evaluate(async (val) => {
      await navigator.clipboard.writeText(val);
      document.getElementById('f-qty').value = '';
      window.__whToasts = [];
      if (typeof showToast === 'function' && !showToast.__whWrapped) {
        const orig = showToast;
        window.showToast = function (msg) { window.__whToasts.push(String(msg)); return orig.apply(this, arguments); };
        window.showToast.__whWrapped = true;
      }
    }, c.paste);
    await page.click('#f-qty');
    await page.keyboard.press('Control+V');
    await page.waitForTimeout(300);
    const got = await page.inputValue('#f-qty');
    const toasts = await page.evaluate(() => window.__whToasts || []);
    const ok = got === c.expect && (!c.mustAnnounce || toasts.length > 0);
    v.cases.push({ paste: c.paste, expect: c.expect, got, announced: toasts.length > 0, ok });
    console.log(`  ${JSON.stringify(c.paste).padEnd(10)} -> ${JSON.stringify(got).padEnd(8)} `
      + `(expected ${JSON.stringify(c.expect)})${c.mustAnnounce ? ` announced=${toasts.length > 0}` : ''}  ${ok ? 'OK' : 'WRONG'}`);
  }
} catch (e) {
  v.error = String(e.message || e).slice(0, 200);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

const pass = !v.error && v.cases.length === CASES.length && v.cases.every((c) => c.ok);
console.log((pass ? 'PASS' : 'FAIL') + ` — numeric paste: ${v.cases.filter((c) => c.ok).length}/${CASES.length} cases`);
process.exit(pass ? 0 : 1);
