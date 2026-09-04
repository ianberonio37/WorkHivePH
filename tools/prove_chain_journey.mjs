/* prove_chain_journey.mjs — T29's chain-journey harness, slice 1 (2026-08-26).
 *
 * THE ORACLE: a multi-page chain must CARRY ITS CONTEXT at every hop, and Back must walk the
 * chain in reverse — no hop may cost a re-find. Single-page journeys can all be green while the
 * chain between them drops the subject (the cross_surface_handoff owed-rows class).
 *
 * Slice 1 — the diagnostic chain's first two hops + the return:
 *   HOP 1: alert-hub renders a PM alert whose action link NAMES its asset
 *          (pm-scheduler.html?asset=<name>).
 *   HOP 2: following it lands with THAT asset's detail OPEN (#screen-detail active,
 *          #det-name = the alert's asset) — context carried, no re-find.
 *   BACK:  one browser Back returns to alert-hub with the alert list rendered (JA3 -
 *          departure and return both clean, no blank shell).
 *
 * State-dependent: needs at least one PM alert in the fixture hive (28 overdue assets seed
 * plenty). ABORTs (exit 2) if none — never invents a subject.
 *
 * Usage: node tools/prove_chain_journey.mjs
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

const browser = await chromium.launch();
let verdict = { hop1: false, hop2: false, back: false, hop3: false, hop4: false, note: '' };
try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();
  const s = await signInDirect(page);
  if (!s.ok) throw new Error('sign-in failed: ' + s.err);

  // ── HOP 1: the alert names its subject and links it ──
  await page.goto(`${SEEDER}/alert-hub.html`, { waitUntil: 'domcontentloaded' });
  let link = null;
  const t0 = Date.now();
  while (Date.now() - t0 < 30000 && !link) {
    link = await page.evaluate(() => {
      const a = document.querySelector('a[href*="pm-scheduler.html?asset="]');
      if (!a) return null;
      const u = new URL(a.href);
      return { href: a.getAttribute('href'), asset: decodeURIComponent(u.searchParams.get('asset') || '') };
    });
    if (!link) await page.waitForTimeout(800);
  }
  if (!link) { console.log('ABORT: no PM alert with an asset-named action link rendered.'); process.exit(2); }
  verdict.hop1 = !!link.asset;
  console.log(`HOP1 ok: alert links its asset ("${link.asset}")`);

  // ── HOP 2: follow it — the landing opens THAT asset's detail ──
  await page.click(`a[href*="pm-scheduler.html?asset="]`);
  await page.waitForURL(/pm-scheduler\.html/, { timeout: 25000 });
  const t1 = Date.now();
  while (Date.now() - t1 < 30000) {
    const st = await page.evaluate(() => ({
      detailActive: !!document.querySelector('#screen-detail.active, #screen-detail[style*="block"]')
        || (document.getElementById('screen-detail') || {}).offsetParent !== null,
      name: (document.getElementById('det-name') || {}).textContent || '',
    }));
    if (st.detailActive && st.name) {
      verdict.hop2 = st.name.trim().toLowerCase() === link.asset.trim().toLowerCase();
      console.log(`HOP2 ${verdict.hop2 ? 'ok' : 'RED'}: detail open for "${st.name}" (expected "${link.asset}")`);
      break;
    }
    await page.waitForTimeout(700);
  }
  if (!verdict.hop2 && !verdict.note) verdict.note = 'detail never opened for the named asset';

  // ── BACK: one gesture returns to a rendered alert-hub ──
  await page.goBack({ waitUntil: 'domcontentloaded' });
  const t2 = Date.now();
  while (Date.now() - t2 < 25000) {
    const ok = await page.evaluate(() =>
      /alert-hub\.html/.test(location.pathname) &&
      !!document.querySelector('a[href*="pm-scheduler.html?asset="]'));
    if (ok) { verdict.back = true; break; }
    await page.waitForTimeout(700);
  }
  console.log(`BACK ${verdict.back ? 'ok' : 'RED'}: returned to a rendered alert-hub`);

  // ── HOP 3 (T15's point-of-use + T29's history hop): asset -> its logbook history, one door ──
  // A worker about to open P-001 must reach "has this failed before" without a manual query:
  // asset-hub.html?tag=<tag> opens the detail, and its timeline renders the asset's logbook/PM
  // events (P-001 carries 70 linked entries in the fixture hive).
  await page.goto(`${SEEDER}/asset-hub.html?tag=P-001`, { waitUntil: 'domcontentloaded' });
  const t3 = Date.now();
  while (Date.now() - t3 < 35000) {
    const st = await page.evaluate(() => {
      const tl = document.getElementById('timeline-list');
      const rows = tl ? tl.querySelectorAll('.tl-row').length : 0;
      const txt = tl ? tl.innerText : '';
      return { rows, hasLogbook: /Logbook/i.test(txt), loading: /Loading timeline/i.test(txt) };
    });
    if (st.rows > 0 && st.hasLogbook) { verdict.hop3 = true; break; }
    if (!st.loading && st.rows === 0 && Date.now() - t3 > 20000) break;
    await page.waitForTimeout(800);
  }
  console.log(`HOP3 ${verdict.hop3 ? 'ok' : 'RED'}: asset P-001's timeline renders its logbook history`);

  // ── HOP 4 (T29's schedule consequence): the alert's landing must let the supervisor SCHEDULE
  // the corrective work for THAT asset, without re-finding it. Diagnosis that dead-ends at
  // "now go start over and locate this machine again" is where a chain silently costs a re-find,
  // which is the whole cross_surface_handoff class. Re-walks the alert link so the assertion is
  // made on the landing a supervisor actually arrives at, not on a hand-typed URL.
  await page.goto(`${SEEDER}/alert-hub.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('a[href*="pm-scheduler.html?asset="]', { timeout: 30000 });
  await page.click('a[href*="pm-scheduler.html?asset="]');
  await page.waitForURL(/pm-scheduler\.html/, { timeout: 25000 });
  const t4 = Date.now();
  while (Date.now() - t4 < 30000) {
    const st = await page.evaluate(() => {
      const nm = (document.getElementById('det-name') || {}).textContent || '';
      const btn = [...document.querySelectorAll('button')]
        .find(b => /openAddTaskSheet/.test(b.getAttribute('onclick') || ''));
      return { name: nm.trim(), hasBtn: !!btn, btnVisible: !!(btn && btn.offsetParent !== null) };
    });
    if (st.name && st.hasBtn) {
      if (st.btnVisible) {
        await page.evaluate(() => {
          const b = [...document.querySelectorAll('button')]
            .find(x => /openAddTaskSheet/.test(x.getAttribute('onclick') || ''));
          if (b) b.click();
        });
        await page.waitForTimeout(700);
        const after = await page.evaluate(() => ({
          open: !!document.querySelector('#add-task-sheet.open'),
          // the sheet carries no asset argument — it acts on whichever detail is open, so the
          // proof that context survived is that the detail STILL names the alerted asset.
          stillNamed: ((document.getElementById('det-name') || {}).textContent || '').trim(),
        }));
        verdict.hop4 = after.open && after.stillNamed.toLowerCase() === link.asset.trim().toLowerCase();
        console.log(`HOP4 ${verdict.hop4 ? 'ok' : 'RED'}: schedule sheet opens on "${after.stillNamed}" (open=${after.open})`);
      } else {
        verdict.note = verdict.note || 'schedule control present but not reachable on the landing';
        console.log('HOP4 RED: the add-task control exists but is not visible on the alert landing');
      }
      break;
    }
    await page.waitForTimeout(700);
  }
  if (!verdict.hop4 && !verdict.note) verdict.note = 'no schedule control on the alert landing';
} catch (e) {
  verdict.note = String(e).slice(0, 160);
} finally {
  await browser.close();
}
const pass = verdict.hop1 && verdict.hop2 && verdict.back && verdict.hop3 && verdict.hop4;
console.log((pass ? 'PASS' : 'FAIL') + ` — chain alert->pm-detail->back + asset->history + schedule (hop1=${verdict.hop1}, hop2=${verdict.hop2}, back=${verdict.back}, hop3=${verdict.hop3}, hop4=${verdict.hop4})${verdict.note ? ' ' + verdict.note : ''}`);
process.exit(pass ? 0 : 1);
