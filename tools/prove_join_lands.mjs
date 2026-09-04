/* prove_join_lands.mjs — T6+T7 paired instrument close (2026-08-26).
 *
 * THE ORACLE: when a worker joins a hive by invite code, the supervisor's roster TELLS them —
 * the join must LAND on the watching side, not only in the DB. Two contexts:
 *   ctx A: the hive's supervisor, signed in, hive.html board open, members list expanded.
 *   ctx B: an outside worker (member of a DIFFERENT hive), authed session, joins via the SAME
 *          server path the UI submit uses (join_hive_by_code RPC) — the joiner's UI door was
 *          already walked in T7 (prod smoke "YOU'RE IN"); THIS prover owns the WATCH side.
 *
 * Verdicts:
 *   realtime  — the name appears in ctx A's roster within WATCH_MS with NO reload (hive.html
 *               currently registers no postgres_changes channel on hive_members, so this is
 *               expected to be false; recorded honestly, never asserted).
 *   on_reload — after one reload the roster shows the new member. THIS is the PASS bar.
 *
 * Hygiene: the joiner row is a probe artifact — deleted afterward (scoped: exact hive+worker,
 * joined_at within the probe window), and the delete is verified. The RPC-side audit trail is
 * client-written (writeAuditLog in hive.html), so an RPC-only join writes none.
 *
 * Usage: node tools/prove_join_lands.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE_ID = '084c113b-99c0-45c6-a8e8-b4b8349da46d'; // Baguio Textile Mills (live-resolved 2026-08-26)
const CODE = 'YW43G7';
const SUP = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234', worker: 'Leandro Marquez' };
const JOINER = { email: 'jerichobonifacio@auth.workhiveph.com', pw: 'test1234', worker: 'Jericho Bonifacio' };
const WATCH_MS = 12000;

function psql(sql) {
  return execFileSync('docker',
    ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
    { encoding: 'utf8' }).trim();
}

async function pageSignIn(ctx, acct, seedHive) {
  const page = await ctx.newPage();
  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  // getDb EXISTS from utils.js load but THROWS until the supabase lib itself arrives -
  // 'getDb is a function' is NOT readiness (it flaked exactly that way). Wait for createClient.
  await page.waitForFunction(() => !!(window.supabase && typeof window.supabase.createClient === 'function'), { timeout: 25000 });
  const r = await page.evaluate(async ({ email, password, worker, hive, hiveName }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    const { data, error } = await db.auth.signInWithPassword({ email, password });
    if (error) return { ok: false, err: error.message };
    try {
      localStorage.setItem('wh_worker_name', worker);
      localStorage.setItem('wh_last_worker', worker);
      if (hive) {
        localStorage.setItem('wh_active_hive_id', hive);
        localStorage.setItem('wh_hive_id', hive);
        if (hiveName) localStorage.setItem('wh_hive_name', hiveName);
      }
    } catch (_) { /* empty-catch-allow: identity seeding is best-effort; the session is what matters */ }
    return { ok: true, uid: data.user?.id };
  }, { email: acct.email, password: acct.pw, worker: acct.worker, hive: seedHive?.id, hiveName: seedHive?.name });
  return { page, ...r };
}

async function rosterNames(page) {
  return page.evaluate(() => {
    const list = document.getElementById('members-list');
    return list ? list.innerText : '';
  });
}

const pre = psql(`SELECT count(*) FROM hive_members WHERE hive_id='${HIVE_ID}' AND worker_name='${JOINER.worker}'`);
if (pre !== '0') { console.log(`ABORT: joiner already has ${pre} row(s) in the target hive — refusing to probe on dirty state.`); process.exit(2); }

const browser = await chromium.launch();
let verdict = { realtime: false, on_reload: false, joined_db: false, cleanup_ok: false };
try {
  // ── ctx A: the watching supervisor ──
  const ctxA = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const a = await pageSignIn(ctxA, SUP, { id: HIVE_ID, name: 'Baguio Textile Mills' });
  if (!a.ok) throw new Error('supervisor sign-in failed: ' + a.err);
  await a.page.goto(`${SEEDER}/hive.html`, { waitUntil: 'domcontentloaded' });
  await a.page.waitForSelector('#view-board:not(.hidden)', { timeout: 25000 });
  await a.page.click('#btn-toggle-members').catch(() => {});
  await a.page.waitForFunction(() => {
    const l = document.getElementById('members-list');
    return l && l.innerText.trim().length > 0;
  }, { timeout: 20000 });
  const before = await rosterNames(a.page);
  if (before.includes(JOINER.worker)) throw new Error('joiner already on the rendered roster — dirty state');
  console.log('A: roster rendered, joiner absent (pre).');

  // ── ctx B: the outside worker joins via the same server path the UI uses ──
  const ctxB = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const b = await pageSignIn(ctxB, JOINER, null);
  if (!b.ok) throw new Error('joiner sign-in failed: ' + b.err);
  const join = await b.page.evaluate(async ({ code, worker }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    const { data, error } = await db.rpc('join_hive_by_code', { p_code: code, p_worker_name: worker });
    return { data, err: error && error.message };
  }, { code: CODE, worker: JOINER.worker });
  if (join.err) throw new Error('join RPC failed: ' + join.err);
  verdict.joined_db = psql(`SELECT count(*) FROM hive_members WHERE hive_id='${HIVE_ID}' AND worker_name='${JOINER.worker}' AND status='active'`) === '1';
  console.log('B: joined (db row present:', verdict.joined_db, ') status:', JSON.stringify(join.data));

  // ── watch: realtime window, no reload ──
  const t0 = Date.now();
  while (Date.now() - t0 < WATCH_MS) {
    if ((await rosterNames(a.page)).includes(JOINER.worker)) { verdict.realtime = true; break; }
    await a.page.waitForTimeout(1000);
  }
  console.log('A: realtime within', WATCH_MS / 1000, 's:', verdict.realtime);

  // ── the PASS bar: one reload shows the join ──
  if (!verdict.realtime) {
    await a.page.reload({ waitUntil: 'domcontentloaded' });
    await a.page.waitForSelector('#view-board:not(.hidden)', { timeout: 25000 });
    await a.page.click('#btn-toggle-members').catch(() => {});
    await a.page.waitForFunction((w) => {
      const l = document.getElementById('members-list');
      return l && l.innerText.includes(w);
    }, JOINER.worker, { timeout: 20000 }).then(() => { verdict.on_reload = true; }).catch(() => {});
  } else { verdict.on_reload = true; }
  console.log('A: join visible on reload:', verdict.on_reload);
} finally {
  // ── cleanup: remove the probe membership, verify ──
  psql(`DELETE FROM hive_members WHERE hive_id='${HIVE_ID}' AND worker_name='${JOINER.worker}' AND joined_at > now() - interval '15 minutes'`);
  verdict.cleanup_ok = psql(`SELECT count(*) FROM hive_members WHERE hive_id='${HIVE_ID}' AND worker_name='${JOINER.worker}'`) === '0';
  await browser.close();
}

console.log('cleanup verified:', verdict.cleanup_ok);
const pass = verdict.joined_db && verdict.on_reload && verdict.cleanup_ok;
console.log((pass ? 'PASS' : 'FAIL') + ` — join lands on the supervisor roster (realtime=${verdict.realtime}, on_reload=${verdict.on_reload}, cleanup=${verdict.cleanup_ok})`);
process.exit(pass ? 0 : 1);
