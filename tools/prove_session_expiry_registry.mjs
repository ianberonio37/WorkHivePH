/* prove_session_expiry.mjs — the U-recovery session_expiry oracle, executable.
 *
 * The claim (four registry rows, market_svc x2 personas + seller x2): the session dies BETWEEN
 * typing and submitting — the write is refused, the person is told their session expired and that
 * NOTHING was sent, and a bare "try again" is not offered when retrying would fail identically.
 *
 * Mechanics, carried from the hand-walk that first earned these rows:
 *  - the 401 is the REAL dead-session shape (PGRST301 "JWT expired"), injected only AFTER the form
 *    is filled — the flow must be mid-flight, not born dead;
 *  - probeActuallyFired is asserted BEFORE the wording is read: a click whose write never reaches
 *    the network proves nothing about how the page handles a refusal (non-vacuity);
 *  - the typed input must SURVIVE the refusal — losing the draft is its own failure;
 *  - "try again" alone (with no sign-in instruction) fails: retrying a dead session fails
 *    identically forever.
 *
 * Run:  node tools/prove_session_expiry.mjs [--case market_svc|seller]
 * Output: per-case PASS/FAIL + session_expiry_walk_report.json; exit 1 on any FAIL.
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const ACCTS = {
  buyer:    { email: 'pabloaguilar@auth.workhiveph.com', pw: 'test1234',
              hive: 'b4f7fe63-92e1-4f8d-b96e-625c3f85ba61', worker: 'Pablo Aguilar' },
  provider: { email: 'bryangarcia@auth.workhiveph.com', pw: 'test1234',
              hive: '636cf7e8-431a-4907-8a9f-43dd4cc216d6', worker: 'Bryan Garcia' },
};

const CASES = {
  market_svc: {
    url: '/marketplace.html?section=services',
    writePattern: /service_requests|rpc\/(svc_|hail|create_service)/,
    field: '#svc-hail-address', typed: 'Session probe site',
    async reach(p) {
      await p.evaluate(() => document.querySelector('.section-tab[data-section="services"]')?.click());
      await p.waitForTimeout(2500);
      for (let i = 0; i < 15; i++) {
        await p.waitForTimeout(1000);
        const ok = await p.evaluate(() => {
          const go = document.getElementById('svc-hail-go');
          if (!go || go.getBoundingClientRect().width === 0) return false;
          const sel = document.getElementById('svc-hail-item');
          if (sel && sel.options.length > 1 && !sel.value) {
            sel.selectedIndex = 1; sel.dispatchEvent(new Event('change', { bubbles: true }));
          }
          const addr = document.getElementById('svc-hail-address');
          if (addr && !addr.value) { addr.value = 'Session probe site'; addr.dispatchEvent(new Event('input', { bubbles: true })); }
          return true;
        });
        if (ok) return { ok: true, control: '#svc-hail-go' };
      }
      return { ok: false, why: 'hail form never rendered' };
    },
  },
  seller: {
    url: '/marketplace-seller.html',
    writePattern: /marketplace_sellers/,
    field: '#messenger-input', typed: 'session.probe.username',
    async reach(p) {
      for (let i = 0; i < 15; i++) {
        await p.waitForTimeout(1000);
        const ok = await p.evaluate(() => {
          const b = document.getElementById('btn-save-messenger');
          const f = document.getElementById('messenger-input');
          if (!b || !f || b.getBoundingClientRect().width === 0) return false;
          f.value = 'session.probe.username'; f.dispatchEvent(new Event('input', { bubbles: true }));
          return true;
        });
        if (ok) return { ok: true, control: '#btn-save-messenger' };
      }
      return { ok: false, why: 'messenger save control never rendered' };
    },
  },
};

const args = process.argv.slice(2);
const onlyCase = (() => { const i = args.indexOf('--case'); return i >= 0 ? args[i + 1] : null; })();
const results = [];
const browser = await chromium.launch();

for (const [name, c] of Object.entries(CASES)) {
  if (onlyCase && name !== onlyCase) continue;
  for (const [persona, acct] of Object.entries(ACCTS)) {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const p = await ctx.newPage();
    await p.goto(`${ORIGIN}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
    await p.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
    const s = await p.evaluate(async ({ email, pw, hive, worker }) => {
      try {
        const db = window._whSupabaseClient || window.getDb(undefined, window.SUPABASE_KEY);
        const { data, error } = await db.auth.signInWithPassword({ email, password: pw });
        localStorage.setItem('wh_active_hive_id', hive);
        localStorage.setItem('wh_last_worker', worker);
        return { ok: !error && !!data?.session, err: error?.message || null };
      } catch (e) { return { ok: false, err: String(e).slice(0, 120) }; }
    }, acct);
    if (!s.ok) {
      results.push({ case: name, persona, pass: false, detail: `sign-in failed: ${s.err} - harness` });
      console.log(`  FAIL — ${name}/${persona}: sign-in (harness)`); await ctx.close(); continue;
    }
    await p.goto(`${ORIGIN}${c.url}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(5000);
    const reached = await c.reach(p);
    if (!reached.ok) {
      results.push({ case: name, persona, pass: false, detail: `unreachable: ${reached.why}` });
      console.log(`  FAIL — ${name}/${persona}: ${reached.why}`); await ctx.close(); continue;
    }
    // THE SESSION DIES NOW — after typing, before submitting. Writes answer 401/PGRST301.
    let fired = 0;
    await ctx.route(/\/rest\/v1\/|\/functions\/v1\//, r => {
      if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(r.request().method())
          && c.writePattern.test(r.request().url())) {
        fired++;
        return r.fulfill({ status: 401, contentType: 'application/json',
          body: JSON.stringify({ code: 'PGRST301', message: 'JWT expired' }) });
      }
      return r.continue();
    });
    await p.evaluate(sel => document.querySelector(sel)?.click(), reached.control);
    await p.waitForTimeout(3500);
    const read = await p.evaluate((fieldSel) => {
      const t = (document.body.innerText || '').replace(/\s+/g, ' ');
      const f = document.querySelector(fieldSel);
      return {
        namesSession: /session (has )?expired|sign ?in again|signed out|log ?in again/i.test(t),
        saysNothingSent: /nothing was (sent|saved)|not sent|no changes were|wasn['’]t (sent|saved)/i.test(t),
        bareTryAgain: /try again/i.test(t) && !/session|sign ?in|expired/i.test(t),
        typedSurvives: !!f && f.value.length > 0,
      };
    }, c.field);
    await ctx.unroute(/\/rest\/v1\/|\/functions\/v1\//).catch(() => {});
    const vacuous = fired === 0;
    const pass = !vacuous && read.namesSession && read.saysNothingSent && !read.bareTryAgain && read.typedSurvives;
    results.push({ case: name, persona, pass, fired,
      detail: vacuous
        ? 'VACUOUS: the write never reached the network - the guard refused earlier or the click did nothing; nothing proven about 401 handling'
        : `fired=${fired} namesSession=${read.namesSession} saysNothingSent=${read.saysNothingSent} bareTryAgain=${read.bareTryAgain} typedSurvives=${read.typedSurvives}` });
    console.log(`  ${pass ? 'PASS' : 'FAIL'} — ${name}/${persona}: ${results[results.length - 1].detail}`);
    await ctx.close();
  }
}
await browser.close();
const failed = results.filter(r => !r.pass);
writeFileSync('session_expiry_walk_report.json', JSON.stringify({
  ran_at: new Date().toISOString(), checks: results, pass: results.length - failed.length, fail: failed.length,
}, null, 1));
console.log(`\n  ${results.length - failed.length}/${results.length} hold — session_expiry_walk_report.json`);
process.exit(failed.length ? 1 : 0);
