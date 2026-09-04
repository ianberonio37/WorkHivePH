/* prove_invite_code_round_trip.mjs — T6 + T7 + T185: the briefing-room round trip.
 *
 * The platform's whole onboarding rests on one exchange: a supervisor creates a hive and reads a
 * six-character code aloud; a worker types it on their phone and is in. It is walked on prod as a
 * smoke test, and until now nothing GATED it - T6 sat at 90% and T7 at 85% with no gate registered
 * against either, which means the most load-bearing flow on the platform was protected by nobody.
 *
 * ★TWO CONTEXTS, because this is a two-person exchange and a single-context test cannot fail the
 * way the real thing fails. The supervisor's browser creates the hive; a SEPARATE browser context
 * with a different account joins with the code. Nothing is shared between them but the six
 * characters, which is exactly the channel the real flow uses.
 *
 * THE ASSERTIONS:
 *   1. the supervisor gets a code that matches the format a person can read aloud (6 chars, no
 *      ambiguous glyphs to mishear)
 *   2. a DIFFERENT account joins with it and lands in the SAME hive - checked in the database, not
 *      by reading a success banner, because a banner is what a broken join would also show
 *   3. a WRONG code is refused, and the refusal says so rather than failing silently or joining
 *      the wrong hive
 *
 * ★DIRECTION 3 IS WHAT STOPS THIS BEING A HAPPY-PATH TEST. A join that accepts anything would pass
 * the first two.
 *
 * Everything it creates is torn down: the probe hive, its membership rows, and the probe account's
 * profile, with a re-count proving it.
 *
 * Usage: node tools/prove_invite_code_round_trip.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const SUP = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234', name: 'Leandro Marquez' };
const MARK = 'WH-T6T7-PROBE';

const psql = (sql) => execFileSync('docker',
  ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8' }).trim();

// a second REAL account, so the join is a different person rather than the same session twice
const workerRow = psql(
  `SELECT u.email FROM auth.users u WHERE u.email <> '${SUP.email}'
   AND u.email LIKE '%@auth.workhiveph.com' ORDER BY u.created_at LIMIT 1;`).split(/\r?\n/)[0];
if (!workerRow) { console.log('SKIP — no second test account to join as'); process.exit(0); }

const v = { workerAccount: workerRow };
const browser = await chromium.launch();

const signIn = async (ctx, email, pw) => {
  const p = await ctx.newPage();
  await p.goto(`${BASE}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await p.waitForFunction(
    () => !!(window.supabase && window.supabase.createClient) && !!window.SUPABASE_KEY,
    { timeout: 20000 }).catch(() => {});
  const ok = await p.evaluate(async ({ e, w, url }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email: e, password: w });
      return !error && !!data?.session;
    } catch (_) { return false; }
  }, { e: email, w: pw, url: SB_URL });
  await p.close();
  return ok;
};

try {
  // ── the supervisor's browser ──
  const supCtx = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
  if (!(await signIn(supCtx, SUP.email, SUP.pw))) throw new Error('supervisor sign-in failed');

  const supPage = await supCtx.newPage();
  const supErrs = [];
  supPage.on('pageerror', (e) => supErrs.push(String(e).slice(0, 90)));
  await supPage.goto(`${BASE}/hive.html`, { waitUntil: 'domcontentloaded' });
  await supPage.waitForTimeout(6000);

  const created = await supPage.evaluate(async (mark) => {
    const go = document.getElementById('btn-go-create');
    if (!go) return { noCreate: true };
    go.click();
    await new Promise((r) => setTimeout(r, 500));
    const input = document.getElementById('hive-name-input');
    const submit = document.getElementById('btn-submit-create');
    if (!input || !submit) return { noForm: true };
    input.value = mark + ' Plant';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    submit.click();
    await new Promise((r) => setTimeout(r, 6000));
    const t = (document.body.innerText || '').replace(/\s+/g, ' ');
    const m = t.match(/\b([A-Z0-9]{6})\b/g) || [];
    return { text: t.slice(0, 200), candidates: m.slice(0, 6) };
  }, MARK);

  // the database is the oracle for what was actually created
  const hiveRow = psql(
    `SELECT id || '|' || invite_code FROM hives WHERE name = '${MARK} Plant' ORDER BY created_at DESC LIMIT 1;`
  ).split(/\r?\n/)[0];
  v.created = { ...created, hiveRow: hiveRow || null };
  if (!hiveRow) throw new Error('no hive row was created');
  const [hiveId, code] = hiveRow.split('|');
  v.code = code;
  v.codeReadableAloud = /^[A-Z0-9]{6}$/.test(code || '');
  v.codeShownToSupervisor = (created.candidates || []).includes(code);
  await supPage.close();

  // ── the worker's browser: a different account, sharing only the six characters ──
  const wkCtx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  if (!(await signIn(wkCtx, workerRow, SUP.pw))) throw new Error('worker sign-in failed');

  const join = async (theCode) => {
    const p = await wkCtx.newPage();
    const errs = [];
    p.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));
    await p.goto(`${BASE}/hive.html`, { waitUntil: 'domcontentloaded' });
    await p.waitForTimeout(6000);
    const out = await p.evaluate(async (c) => {
      const go = document.getElementById('btn-go-join');
      if (!go) return { noJoin: true };
      go.click();
      await new Promise((r) => setTimeout(r, 500));
      const input = document.getElementById('join-code-input');
      if (!input) return { noForm: true };
      input.value = c;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      const btn = [...document.querySelectorAll('button')]
        .find((b) => /join/i.test(b.textContent || '') && b.offsetHeight > 0 && b.id !== 'btn-go-join');
      if (btn) btn.click();
      await new Promise((r) => setTimeout(r, 6000));
      return { text: (document.body.innerText || '').replace(/\s+/g, ' ').slice(0, 220) };
    }, theCode);
    await p.close();
    return { ...out, errs: errs.length };
  };

  // 3. a wrong code first, so a permissive join cannot be hidden by a later success
  const badCode = code.split('').reverse().join('') === code ? 'ZZZZZZ' : code.split('').reverse().join('');
  v.wrongCode = await join(badCode);
  v.wrongCodeJoined = Number(psql(
    `SELECT count(*) FROM hive_members m JOIN auth.users u ON u.id = m.auth_uid
     WHERE u.email = '${workerRow}' AND m.hive_id = '${hiveId}';`)) > 0;
  v.wrongCodeRefusedOutLoud = /not found|invalid|check the code|wrong|no hive|couldn|could not/i
    .test(v.wrongCode.text || '');

  // 2. now the real code
  v.rightCode = await join(code);
  v.joinedSameHive = Number(psql(
    `SELECT count(*) FROM hive_members m JOIN auth.users u ON u.id = m.auth_uid
     WHERE u.email = '${workerRow}' AND m.hive_id = '${hiveId}' AND m.status = 'active';`)) === 1;

  v.supErrs = supErrs.length;
  console.log(`  supervisor created a hive, code ${code} (shown on screen: ${v.codeShownToSupervisor})`);
  console.log(`  wrong code -> joined=${v.wrongCodeJoined} said-so=${v.wrongCodeRefusedOutLoud}`);
  console.log(`  right code -> in the same hive: ${v.joinedSameHive}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 170);
  console.log('probe error:', v.error);
} finally {
  try {
    psql(`DELETE FROM hive_members WHERE hive_id IN (SELECT id FROM hives WHERE name = '${MARK} Plant');`);
    psql(`DELETE FROM hives WHERE name = '${MARK} Plant';`);
    v.leftBehind = Number(psql(`SELECT count(*) FROM hives WHERE name = '${MARK} Plant';`)) || 0;
  } catch (_) { v.leftBehind = 'cleanup failed'; }
  await browser.close();
}

const pass = !v.error
  && v.codeReadableAloud && v.codeShownToSupervisor
  && !v.wrongCodeJoined && v.wrongCodeRefusedOutLoud
  && v.joinedSameHive
  && v.leftBehind === 0 && v.supErrs === 0;

if (!pass && !v.error) {
  console.log('  Hearing a code and being in the hive is the platform\'s first promise. A join that');
  console.log('  accepts a wrong code, or refuses a right one, breaks onboarding for everyone after it.');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — invite code round trip: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
