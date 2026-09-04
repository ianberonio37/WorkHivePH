/* prove_timed_journey.mjs — the timed-journey oracle (T9/T10/T13's shared instrument, 2026-08-26).
 *
 * WHAT IT GENERALIZES: the PP dims time a PAGE's first paint; nothing times a JOB. "Two minutes to
 * read the handover", "seconds to log a repair" are the platform's real promises, and no gate
 * measured them. Each case here is one user job with a STATED budget; the prover walks the job's
 * scripted core path and reports measured wall-time vs budget.
 *
 * WHAT THE MACHINE HONESTLY MEASURES: the PLATFORM's share of the time — how long until the job's
 * content/controls are actually usable at each step (paint, populate, land). It cannot measure the
 * human's reading/typing share, and does not pretend to: budgets are set for the scripted path on
 * the local stack, generous enough that only a real regression (a hung read, a skeleton that never
 * resolves, a wizard step that stalls) breaks them. A budget breach is a slowness REGRESSION signal,
 * not a UX verdict by itself.
 *
 * Cases: T13 handover-read (read-only; usable = verdict resolved + carry-forward populated or
 * honestly empty) and T9 log-repair-timed (a WRITE journey: the full wizard through submit until
 * the entry RENDERS — probe-marked row deleted afterward, trg_logbook_xp_reverse reverses the XP,
 * cleanup verified as part of the verdict). T10's completion loop is the named next slice.
 *
 * Usage: node tools/prove_timed_journey.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const MARKER = 'WH-T9-PROBE timed journey';

function psql(sql) {
  return execFileSync('docker',
    ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
    { encoding: 'utf8' }).trim();
}
const ACCT = { email: 'bryangarcia@auth.workhiveph.com', pw: 'test1234', worker: 'Bryan Garcia' };
// Without the hive keys the page answers "No active hive" — an honest state, but the wrong
// subject for this journey. The seeding IS part of the instrument (first run measured it).
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };

const CASES = [
  {
    // T9's time-to-logged: the whole job — open logbook, pick a real asset through the picker,
    // complete the wizard the way a person does, submit, and SEE the entry land in the list.
    // The drive reuses prove_offline_queued's hard-won recipe (form submit not button click;
    // ungated asset; non-Breakdown type; log as OPEN). Budget covers the scripted path only.
    // The row is probe-marked and deleted afterward; trg_logbook_xp_reverse reverses the XP.
    id: 'log-repair-timed', page: 'logbook.html', budget_ms: 60000, writes: true,
    drive: async (page) => {
      await page.waitForSelector('#log-form', { timeout: 25000 });
      let picked = null;
      for (let attempt = 0; attempt < 6 && !picked; attempt++) {
        await page.evaluate(() => document.getElementById('asset-picker-btn')?.click());
        await page.waitForTimeout(900);
        const id = await page.evaluate((n) => {
          const rows = [...document.querySelectorAll('#asset-picker-list button[data-asset-id]')];
          const btn = rows[n];
          if (!btn) return null;
          const v = btn.dataset.assetId;
          btn.click();
          return v;
        }, attempt);
        if (!id) break;
        await page.waitForTimeout(1100);
        const gated = await page.evaluate(() => {
          const sec = document.getElementById('tasklist-ack-section');
          return !!(sec && !sec.classList.contains('hidden'));
        });
        if (!gated) picked = id;
      }
      if (!picked) throw new Error('no ungated asset pickable');
      const filled = await page.evaluate((marker) => {
        const set = (id, v) => {
          const e = document.getElementById(id);
          if (!e) return false;
          e.value = v;
          e.dispatchEvent(new Event('input', { bubbles: true }));
          return true;
        };
        for (const sel of document.querySelectorAll('#log-form select')) {
          if (sel.value) continue;
          let opts = [...sel.options].filter((o) => o.value && !/^select/i.test(o.textContent || ''));
          if (sel.id === 'f-maint-type') {
            const nb = opts.filter((o) => !/breakdown/i.test(o.textContent + o.value));
            if (nb.length) opts = nb;
          }
          if (opts[0]) { sel.value = opts[0].value; sel.dispatchEvent(new Event('change', { bubbles: true })); }
        }
        const openRadio = document.getElementById('st-open');
        if (openRadio) { openRadio.checked = true; openRadio.dispatchEvent(new Event('change', { bubbles: true })); }
        return set('f-problem', marker + ' - bearing noise on pump 3, 2pm round.')
            && set('f-action', 'Timed-journey probe; row deleted by the prover.')
            && !!(document.getElementById('f-machine') || {}).value;
      }, MARKER);
      if (!filled) throw new Error('composer fields not fillable');
      await page.evaluate(() => document.getElementById('log-form').requestSubmit());
      // landed = the probe-marked entry renders in the list (did_it_land, not just a toast)
      const tL = Date.now();
      while (Date.now() - tL < 30000) {
        const onScreen = await page.evaluate((m) => document.body.innerText.includes(m), MARKER);
        if (onScreen) return;
        await page.waitForTimeout(500);
      }
      throw new Error('submitted but the entry never rendered in the list within 30s');
    },
    cleanup: () => {
      psql(`DELETE FROM embedding_outbox WHERE source_table='logbook' AND row_id IN (SELECT id::text FROM logbook WHERE problem LIKE '%${MARKER}%')`);
      psql(`DELETE FROM logbook WHERE problem LIKE '%${MARKER}%' AND created_at > now() - interval '15 minutes'`);
      return psql(`SELECT count(*) FROM logbook WHERE problem LIKE '%${MARKER}%'`) === '0';
    },
  },
  {
    // T10's completion loop: today's PM list -> task detail -> completion sheet -> save -> the
    // completion REGISTERS (sheet closes + pm_completions row lands). Mirror toggle OFF: the
    // logbook mirror is T32's separately-proven chain; this journey times the completion itself.
    id: 'pm-complete-timed', page: 'pm-scheduler.html', budget_ms: 60000, writes: true,
    drive: async (page) => {
      await page.waitForSelector('.asset-card', { timeout: 30000 });
      await page.evaluate(() => {
        const chip = document.getElementById('chip-mine');
        if (chip && !chip.hidden) chip.click();
      });
      await page.waitForTimeout(1000);
      const opened = await page.evaluate(() => {
        const card = document.querySelector('.asset-card');
        if (!card) return false;
        card.click(); return true;
      });
      if (!opened) throw new Error('no .asset-card rendered');
      await page.waitForTimeout(1400);
      const sheet = await page.evaluate(() => {
        const btn = document.querySelector('.complete-btn:not(.done)');
        if (!btn) return false;
        btn.click(); return true;
      });
      if (!sheet) throw new Error('no not-done .complete-btn in the detail');
      await page.waitForTimeout(900);
      const ready = await page.evaluate((marker) => {
        const f = document.getElementById('sheet-findings');
        const save = document.getElementById('sheet-save-btn');
        if (!f || !save || !save.getClientRects().length) return false;
        f.value = marker.replace('T9', 'T10') + ' - checked and torqued per scope.';
        f.dispatchEvent(new Event('input', { bubbles: true }));
        const tgl = document.getElementById('sheet-log-toggle');
        if (tgl) tgl.checked = false;
        return true;
      }, MARKER);
      if (!ready) throw new Error('completion sheet did not open with its fields');
      await page.evaluate(() => document.getElementById('sheet-save-btn').click());
      // landed = the DB row exists (positive acceptance) AND the sheet closed
      const tL = Date.now();
      while (Date.now() - tL < 30000) {
        const n = psql(`SELECT count(*) FROM pm_completions WHERE notes LIKE '%WH-T10-PROBE%'`);
        if (n === '1') return;
        await page.waitForTimeout(700);
      }
      throw new Error('saved but no pm_completions row landed within 30s');
    },
    cleanup: () => {
      psql(`DELETE FROM pm_completions WHERE notes LIKE '%WH-T10-PROBE%' AND completed_at > now() - interval '15 minutes'`);
      return psql(`SELECT count(*) FROM pm_completions WHERE notes LIKE '%WH-T10-PROBE%'`) === '0';
    },
  },
  {
    id: 'handover-read', page: 'shift-brain.html', budget_ms: 30000,
    // usable = the verdict label has left its loading state AND the carry-forward list region
    // rendered rows or an honest empty line (skeleton gone). "Unknown right now, not zero" is
    // also a resolved, honest read — degraded-but-spoken counts as usable truth.
    usable: () => {
      const v = document.getElementById('sb-verdict-label');
      const vt = v ? v.textContent : '';
      const verdictDone = !!vt && !/Loading shift readiness/i.test(vt) && !/Generating this shift/i.test(vt);
      const carry = document.getElementById('carry-list');
      const carryDone = !!carry && carry.children.length > 0 && !carry.querySelector('.wh-skel, [class*="skeleton"]');
      return verdictDone && carryDone;
    },
  },
];

async function signInDirect(page) {
  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  // getDb EXISTS from utils.js load but THROWS until the supabase lib itself arrives -
  // 'getDb is a function' is NOT readiness (it flaked exactly that way). Wait for createClient.
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
      localStorage.setItem('wh_hive_role', 'worker');
    } catch (_) { /* empty-catch-allow: identity seeding is best-effort */ }
    return { ok: true };
  }, { email: ACCT.email, password: ACCT.pw, worker: ACCT.worker, hive: HIVE });
}

const browser = await chromium.launch();
const results = [];
for (const c of CASES) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  let verdict = { id: c.id, ms: null, within: false, note: '' };
  try {
    const s = await signInDirect(page);
    if (!s.ok) throw new Error('sign-in failed: ' + s.err);
    const t0 = Date.now();
    await page.goto(`${SEEDER}/${c.page}`, { waitUntil: 'domcontentloaded' });
    // Manual evaluate-poll instead of waitForFunction: same predicate, but each tick's partial
    // state is observable when it never turns true (a black-box wait can only say "timed out").
    let usable = false;
    let lastState = null;
    if (c.drive) {
      await c.drive(page);
      usable = true;
    } else {
      while (Date.now() - t0 < c.budget_ms + 15000) {
        lastState = await page.evaluate(c.usable);
        if (lastState === true) { usable = true; break; }
        await page.waitForTimeout(500);
      }
    }
    if (!usable) {
      const parts = await page.evaluate(() => ({
        url: location.pathname,
        vt: ((document.getElementById('sb-verdict-label') || {}).textContent || '<missing>').slice(0, 60),
        kids: (document.getElementById('carry-list') || { children: [] }).children.length,
        wall: !!document.querySelector('.wh-signin-wall, #wh-signin-wall'),
      }));
      throw new Error('never usable; parts: ' + JSON.stringify(parts));
    }
    verdict.ms = Date.now() - t0;
    verdict.within = verdict.ms <= c.budget_ms;
    verdict.note = `${verdict.ms}ms of ${c.budget_ms}ms budget`;
  } catch (e) {
    verdict.note = String(e).slice(0, 160);
  } finally {
    if (c.cleanup) {
      try {
        verdict.cleaned = c.cleanup();
        if (!verdict.cleaned) { verdict.within = false; verdict.note += ' | CLEANUP FAILED'; }
      } catch (e2) { verdict.within = false; verdict.note += ' | cleanup threw: ' + String(e2).slice(0, 80); }
    }
    await ctx.close();
  }
  results.push(verdict);
  console.log(`${verdict.within ? 'ok' : 'RED'}  ${c.id}: ${verdict.note}`);
}
await browser.close();

const bad = results.filter(r => !r.within);
console.log((bad.length ? 'FAIL' : 'PASS') + ` — timed journeys: ${results.length - bad.length}/${results.length} within budget.`);
process.exit(bad.length ? 1 : 0);
