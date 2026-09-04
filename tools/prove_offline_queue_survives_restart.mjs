/**
 * T14/T44: does an offline-queued entry survive the app being closed and reopened? (2026-08-28)
 *
 * The promise a dead-zone worker is relying on has three parts, and only the first was proven:
 * the entry is QUEUED, the app can be REOPENED while still offline, and the person is TOLD the
 * work is still pending. This walks all three in one run.
 *
 * MEASURED: queued while offline -> 1 pending; page CLOSED and a fresh one opened WITH THE NETWORK
 * STILL DOWN -> the service worker serves the logbook shell (the navigation simply succeeds) and
 * the queue still holds the entry; the offline badge is visible and reads "1 pending"; cleanup
 * leaves nothing behind.
 *
 * ★IT MUST RUN WITH serviceWorkers ENABLED. The first version blocked them out of habit — every
 * other probe here does — and the offline reload then failed with a navigation error, because
 * nothing was left to serve the shell. Blocking the worker in the one test whose subject is the
 * offline shell measures the absence of the thing under test.
 *
 * ★AND THE QUEUE'S API IS enqueue/getPending/remove, not put/all. The first version invented the
 * shorter names and got "q.put is not a function" — a reminder that reading offline-queue.js costs
 * less than guessing at it.
 *
 * USAGE:  node tools/prove_offline_queue_survives_restart.mjs
 */
import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:5000/workhive';
const SB = 'http://127.0.0.1:54321';
const A = { email: 'bryangarcia@auth.workhiveph.com', pw: 'test1234', worker: 'Bryan Garcia' };
const MARK = 'WH-PROBE-T14-QUEUE';

const browser = await chromium.launch();
// One PERSISTENT-ish context: closing the PAGE and opening a new one is the "reopen the app" case.
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });

const auth = await ctx.newPage();
await auth.goto(`${BASE}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
await auth.waitForFunction(() => !!(window.supabase && window.supabase.createClient) && !!window.SUPABASE_KEY,
                           { timeout: 20000 }).catch(() => {});
await auth.evaluate(async ({ acct, url }) => {
  const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
  const { data } = await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
  const uid = data?.session?.user?.id;
  const { data: m } = uid ? await db.from('hive_members').select('hive_id')
    .eq('auth_uid', uid).eq('status', 'active').limit(1).maybeSingle() : { data: null };
  if (m?.hive_id) { localStorage.setItem('wh_active_hive_id', m.hive_id); localStorage.setItem('wh_hive_id', m.hive_id); }
  localStorage.setItem('wh_last_worker', acct.worker);
}, { acct: A, url: SB });
await auth.close();

// ── 1. offline, queue an entry ───────────────────────────────────────────────
let p = await ctx.newPage();
await p.goto(`${BASE}/logbook.html`, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(6000);
await ctx.setOffline(true);

const queued = await p.evaluate(async (mark) => {
  if (typeof window.whCreateQueue !== 'function') return { err: 'no whCreateQueue' };
  const q = window._whLogQueue || window.whCreateQueue({ db: 'wh_logbook_offline', table: 'logbook' });
  try {
    await q.enqueue({ id: crypto.randomUUID(), machine: mark, problem: mark + ' probe entry',
                  date: new Date().toISOString(), status: 'Open', category: 'Mechanical' });
    const all = await q.getPending();
    return { queued: all.filter(r => (r.machine || '') === mark).length, total: all.length };
  } catch (e) { return { err: String(e).slice(0, 90) }; }
}, MARK);
console.log('1. queued while offline :', JSON.stringify(queued));

// ── 2. "close the app": drop the page entirely, open a fresh one ─────────────
await p.close();
p = await ctx.newPage();
await p.goto(`${BASE}/logbook.html`, { waitUntil: 'domcontentloaded' }).catch(e=>console.log("   (offline nav:", String(e).slice(0,60), ")"));
await p.waitForTimeout(6000);

const survived = await p.evaluate(async (mark) => {
  if (typeof window.whCreateQueue !== 'function') return { err: 'no whCreateQueue' };
  const q = window._whLogQueue || window.whCreateQueue({ db: 'wh_logbook_offline', table: 'logbook' });
  try {
    const all = await q.getPending();
    return { stillQueued: all.filter(r => (r.machine || '') === mark).length, total: all.length };
  } catch (e) { return { err: String(e).slice(0, 90) }; }
}, MARK);
console.log('2. after app restart    :', JSON.stringify(survived));

// ── 3. is the person TOLD there is queued work? ──────────────────────────────
console.log('3. badge/notice on load :', JSON.stringify(await p.evaluate(() => {
  const el = document.getElementById('offline-queue-count');
  const shown = el && el.getBoundingClientRect().height > 0 && getComputedStyle(el).display !== 'none';
  return { badgeExists: !!el, badgeVisible: !!shown, text: el ? (el.textContent || '').trim() : null };
})));

// ── cleanup: drop the probe row from the queue, restore connectivity ─────────
await p.evaluate(async (mark) => {
  const q = window._whLogQueue || window.whCreateQueue({ db: 'wh_logbook_offline', table: 'logbook' });
  const all = await q.getPending();
  for (const r of all) if ((r.machine || '') === mark && q.remove) await q.remove(r.id);
}, MARK).catch(() => {});
await ctx.setOffline(false);
console.log('4. cleanup              :', JSON.stringify(await p.evaluate(async (mark) => {
  const q = window._whLogQueue || window.whCreateQueue({ db: 'wh_logbook_offline', table: 'logbook' });
  const all = await q.getPending();
  return { leftBehind: all.filter(r => (r.machine || '') === mark).length };
}, MARK).catch(() => ({ leftBehind: 'unknown' }))));
await browser.close();
