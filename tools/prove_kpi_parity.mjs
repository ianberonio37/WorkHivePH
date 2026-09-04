/* prove_kpi_parity.mjs — T22's drill-basis + cross-surface KPI parity oracle, slice 1 (2026-08-26).
 *
 * THE ORACLE: one datum, one story. A headline KPI rendered on two surfaces must show the SAME
 * figure, and each rendering must carry its BASIS (window + standard) so a supervisor can stand
 * behind the number without leaving the glass (T47's meeting-proof bar, T133's numeric-parity
 * shape). Both pages read get_pm_compliance_smrp (p_period_days 90) by design — this locks the
 * one-source discipline so a future fork (a local recompute, a different window) cannot silently
 * split the number the way worst-MTBF once split (the two-windows-one-metric memory).
 *
 * Slice 1 — PM compliance (SMRP 2.1.1):
 *   analytics #an-pm-hero  = "N%"  (the KPI card)
 *   pm-scheduler #pm-ontrack-sub contains "N% PM compliance (SMRP, last 90 days)" — the SAME N,
 *   with the window NAMED on the glass.
 *
 * Usage: node tools/prove_kpi_parity.mjs
 */
import { chromium } from 'playwright';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234', worker: 'Leandro Marquez' };

async function signInDirect(page) {
  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  // getDb EXISTS from utils.js load but THROWS until the supabase lib arrives — wait for createClient.
  await page.waitForFunction(() => !!(window.supabase && typeof window.supabase.createClient === 'function'), { timeout: 25000 });
  return page.evaluate(async ({ email, password, worker, hive }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    const { error } = await db.auth.signInWithPassword({ email, password });
    if (error) return { ok: false, err: error.message };
    try {
      localStorage.setItem('wh_worker_name', worker);
      localStorage.setItem('wh_last_worker', worker);
      localStorage.setItem('wh_active_hive_id', hive.id);
      localStorage.setItem('wh_hive_id', hive.id);
      localStorage.setItem('wh_hive_name', hive.name);
      localStorage.setItem('wh_hive_role', 'supervisor');
    } catch (_) { /* empty-catch-allow: identity seeding is best-effort */ }
    return { ok: true };
  }, { email: ACCT.email, password: ACCT.pw, worker: ACCT.worker, hive: HIVE });
}

async function pollText(page, fn, timeoutMs, arg) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const v = await page.evaluate(fn, arg);   // arg is undefined for the slice-1 callers, which take none
    if (v) return v;
    await page.waitForTimeout(700);
  }
  return null;
}

/* ★A COMPARISON ALONE CANNOT BE RESURRECTION-PROVEN HERE (2026-08-26). Disabling the canonical
   patch and re-running left this GREEN: the orchestrator snapshot happened to agree that minute,
   because the divergence it was built to catch is INTERMITTENT - it appears only when the sliding
   90-day window moves between the snapshot and the live read (measured 78 vs 77 at birth). A gate
   that only fires when a race happens to be losing is a weak gate. So assert the MECHANISM too:
   the page must actually read the canonical RPC. The live comparison stays - it is the symptom
   check, and it catches divergences the source check cannot imagine - but the source check is what
   makes a regression deterministic. */
import { readFileSync } from 'node:fs';
const analyticsSrc = readFileSync('analytics.html', 'utf8');
const mechanismOk = /get_pm_compliance_smrp/.test(analyticsSrc)
  && /an-pm-hero/.test(analyticsSrc)
  && !/if \(true \|\| live === pmPct\)/.test(analyticsSrc);
console.log('mechanism: analytics reads the canonical RPC and patches the hero:', mechanismOk);

const browser = await chromium.launch();
let verdict = { analytics: null, pm: null, windowNamed: false, agree: false, note: '', mechanism: mechanismOk };
try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();
  const s = await signInDirect(page);
  if (!s.ok) throw new Error('sign-in failed: ' + s.err);

  await page.goto(`${SEEDER}/analytics.html`, { waitUntil: 'domcontentloaded' });
  const heroTxt = await pollText(page, () => {
    const h = document.getElementById('an-pm-hero');
    const t = h ? (h.textContent || '').trim() : '';
    return /^\d+%$/.test(t) ? t : null;
  }, 35000);
  if (!heroTxt) throw new Error('analytics #an-pm-hero never rendered a percentage');
  verdict.analytics = Number(heroTxt.replace('%', ''));
  console.log('analytics PM compliance:', heroTxt);

  await page.goto(`${SEEDER}/pm-scheduler.html`, { waitUntil: 'domcontentloaded' });
  const sub = await pollText(page, () => {
    const el = document.getElementById('pm-ontrack-sub');
    const t = el ? (el.textContent || '') : '';
    return /PM compliance/.test(t) ? t : null;
  }, 35000);
  if (!sub) throw new Error('pm-scheduler #pm-ontrack-sub never rendered the compliance line');
  const m = sub.match(/(\d+)% PM compliance/);
  verdict.pm = m ? Number(m[1]) : null;
  verdict.windowNamed = /SMRP, last 90 days/.test(sub);
  console.log('pm-scheduler line:', JSON.stringify(sub.trim().slice(0, 100)));

  verdict.agree = verdict.pm !== null && verdict.pm === verdict.analytics;

  /* SLICE 2 (T22, 2026-08-27) — OVERDUE PM ASSETS across pm-scheduler and the hive board.
     Chosen because this platform has ALREADY shipped a disagreement on exactly this datum: the
     dayplanner rail printed its 30-row display slice as the count while 80 were due, so the same
     figure read 30 on one surface and 80 on another. A count that disagrees is worse than a count
     that is missing, because a supervisor plans a shift against it. Both surfaces roll up to
     distinct ASSETS, so they are genuinely the same question and must give the same answer. */
  /* ★POLL FOR A STABLE VALUE, NOT FOR "A DIGIT". These stat tiles paint a PLACEHOLDER 0 and then
     patch it when the read answers, so a poll that accepts the first digit it sees captures the
     placeholder: the first run of this slice reported pm-scheduler 0 vs hive 29 and would have
     been filed as a cross-surface disagreement, when a direct read of the same element moments
     earlier had shown 29 on both. A count that is still loading is not a count that disagrees.
     Zero is also a LEGITIMATE value for a hive with nothing overdue, so "wait for non-zero" would
     be wrong too - the honest condition is that the number has stopped moving. */
  const overdueOf = async (path, sel) => {
    await page.goto(`${SEEDER}/${path}`, { waitUntil: 'domcontentloaded' });
    let last = null, stable = 0;
    for (let i = 0; i < 40; i++) {
      await page.waitForTimeout(700);
      const t = await page.evaluate((s) => {
        const el = document.querySelector(s);
        return el ? (el.textContent || '').trim() : '';
      }, sel);
      const mm = t.match(/(\d+)/);
      const v = mm ? Number(mm[1]) : null;
      if (v !== null && v === last) { stable++; if (stable >= 3) return v; } else { stable = 0; }
      last = v;
    }
    return last;
  };
  verdict.overduePm   = await overdueOf('pm-scheduler.html', '#stat-overdue');
  verdict.overdueHive = await overdueOf('hive.html', '#pulse-pm-overdue');
  /* The hive board must also NAME what it is counting. '29' alone is the naked-number failure this
     platform already fixed once on the tiles; the noun is what makes it checkable by a reader. */
  verdict.overdueNounNamed = await page.evaluate(() => {
    const e = document.getElementById('pm-overdue-text');
    return !!(e && /asset/i.test(e.textContent || ''));
  });
  verdict.overdueAgree = verdict.overduePm !== null && verdict.overduePm === verdict.overdueHive;
  console.log('overdue PM assets: pm-scheduler', verdict.overduePm, 'vs hive', verdict.overdueHive,
              '(noun named:', verdict.overdueNounNamed + ')');
} catch (e) {
  verdict.note = String(e).slice(0, 160);
} finally {
  await browser.close();
}
const pass = verdict.agree && verdict.windowNamed && verdict.mechanism
  && verdict.overdueAgree && verdict.overdueNounNamed;
console.log((pass ? 'PASS' : 'FAIL') + ` — KPI parity: compliance analytics ${verdict.analytics}% vs pm-scheduler ${verdict.pm}%; overdue assets pm-scheduler ${verdict.overduePm} vs hive ${verdict.overdueHive} (window named: ${verdict.windowNamed})${verdict.note ? ' ' + verdict.note : ''}`);
process.exit(pass ? 0 : 1);
