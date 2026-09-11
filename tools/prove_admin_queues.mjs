/* prove_admin_queues.mjs — the platform-actions "populated" oracle, executable.
 *
 * The 25 stale LM-*-admin-*-populated rows claim that on /workhive/platform-actions.html the surface
 * renders real rows and EVERY visible number matches its source of truth. A generic structural walk
 * cannot settle that, so merge_walk_results refuses those rows by design. Third sibling of
 * tools/prove_services_pane.mjs and tools/prove_seller_pane.mjs — same personas, same disciplines,
 * same report shape, deliberately not a new invention.
 *
 *   node tools/prove_admin_queues.mjs                 # all personas
 *   node tools/prove_admin_queues.mjs --persona admin
 *
 * ★ THE HARDEST THING THIS CONSOLE HAS TO GET RIGHT IS NOT A NUMBER, IT IS A ZERO IT CANNOT TRUST.
 * marketplace_platform_admins holds two names (Pablo Aguilar, Leandro Marquez). For anyone else the
 * queues are filtered to nothing by RLS — no error, just no rows — so "0 waiting" and "you are not
 * allowed to see what is waiting" are byte-identical at the client. The page's own source calls this
 * out ("a false all-clear is the most expensive empty state the platform can show") and answers it
 * with #local-bypass-note. So this prover splits its personas by CAPABILITY: an admin's counts are
 * compared to truth; a non-admin's screen must NAME the limitation rather than present the empty
 * queues as fact. A prover that only ever ran as an admin would never see that half.
 *
 * THE FOUR COUNTS, each attributed to its OWN element and to the predicate the page actually issues:
 *   #svc-topups-count      v_service_credit_topups_truth, status=pending_verification   (cap 50)
 *   #mkt-listings-count    v_marketplace_listings_truth,  status=draft                  (cap 50)
 *   #mkt-sellers-count     v_marketplace_sellers_truth, and NOT simply the .or() the query sends —
 *                          the badge counts sellers with an ACTIONABLE button, i.e. kyb_verified is
 *                          false, OR cert_verified is false AND they actually have certifications.
 *                          A seller who is unverified with nothing to verify renders no button and
 *                          is not counted, so comparing against the raw .or() would fail a correct page.
 *   #gcash-receipts-count  v_gcash_receipts_needing_eyes, EXACT server count (the list shows 20)
 *
 * A CAP IS NOT A TOTAL. Three of those reads are .limit(50) and the page prints "50+" when full;
 * that is the honest render, so "50+" is checked as "truth >= 50" rather than parsed as a number.
 *
 * NOT COMPARED HERE, and said plainly rather than quietly skipped:
 *   #cp-cover        cash-in / credits-owed, summed from v_service_credit_ledger_truth by entry_type
 *                    across four terms. Re-implementing that arithmetic in a probe would make the
 *                    probe a second, unreviewed source of truth — so only its DISCIPLINE is asserted:
 *                    it carries its unit (a bare "1.32" beside peso figures reads as money) and an
 *                    unknown cover is a gap, never a 0, because 0 is the reading that says insolvent.
 *   #fb-count-badge  the feedback queue's own family owns it.
 *
 * Output: per-check PASS/FAIL lines + admin_queues_report.json; exit 1 on any FAIL.
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
// Capability, not job title: buyer and admin are BOTH in marketplace_platform_admins here.
const PERSONAS = {
  buyer:    { email: 'pabloaguilar@auth.workhiveph.com',   pw: 'test1234', platformAdmin: true },
  admin:    { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234', platformAdmin: true },
  provider: { email: 'bryangarcia@auth.workhiveph.com',    pw: 'test1234', platformAdmin: false },
  seller:   { email: 'jerichobonifacio@auth.workhiveph.com', pw: 'test1234', platformAdmin: false },
  anon:     null,
};

const args = process.argv.slice(2);
const only = (() => { const i = args.indexOf('--persona'); return i >= 0 ? args[i + 1] : null; })();
const REPORT = only ? `admin_queues_report.persona-${only}.json`.replace(/[^\w.-]+/g, '_')
                    : 'admin_queues_report.json';

const results = [];
function check(persona, name, pass, detail) {
  results.push({ persona, name, pass: !!pass, detail });
  console.log(`  ${pass ? 'PASS' : 'FAIL'} — ${persona} / ${name}: ${detail}`);
}

/** '—' is a stated failed read; '50+' is a disclosed cap; anything else must parse. */
function readCount(raw) {
  const t = (raw ?? '').trim();
  if (t === '') return { kind: 'absent' };
  if (/^[—–-]$/.test(t)) return { kind: 'gap' };
  if (/^\d+\+$/.test(t)) return { kind: 'capped', n: Number(t.slice(0, -1)) };
  const n = Number(t.replace(/[, ]/g, ''));
  return Number.isFinite(n) ? { kind: 'num', n } : { kind: 'unparsed', t };
}

const browser = await chromium.launch();
for (const [persona, acct] of Object.entries(PERSONAS)) {
  if (only && persona !== only) continue;
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();

  if (acct) {
    await p.goto(`${ORIGIN}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
    await p.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
    const s = await p.evaluate(async ({ email, pw }) => {
      try {
        const db = window._whSupabaseClient || window.getDb(undefined, window.SUPABASE_KEY);
        const { data, error } = await db.auth.signInWithPassword({ email, password: pw });
        return { ok: !error && !!data?.session, err: error?.message || null };
      } catch (e) { return { ok: false, err: String(e).slice(0, 120) }; }
    }, acct);
    if (!s.ok) { check(persona, 'sign-in', false, `sign-in failed: ${s.err} — harness, not the surface`); await ctx.close(); continue; }
  }

  await p.goto(`${ORIGIN}/platform-actions.html`, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await p.waitForTimeout(5000);
  await p.waitForFunction(() => {
    const sync = document.getElementById('last-sync');
    return sync && !/Refreshing/i.test(sync.textContent || '');
  }, { timeout: 25000 }).catch(() => {});

  const reading = await p.evaluate(async () => {
    const el = id => document.getElementById(id);
    const txt = document.body.innerText || '';
    const vis = e => { if (!e) return false; const r = e.getBoundingClientRect(); const st = getComputedStyle(e);
      return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none'; };
    const shown = {
      topups:   el('svc-topups-count')?.textContent ?? null,
      listings: el('mkt-listings-count')?.textContent ?? null,
      sellers:  el('mkt-sellers-count')?.textContent ?? null,
      gcash:    el('gcash-receipts-count')?.textContent ?? null,
      cover:    el('cp-cover')?.textContent ?? null,
    };
    const bypassNote = (() => { const n = el('local-bypass-note'); return n && vis(n) ? (n.textContent || '').trim() : null; })();

    const db = window._whSupabaseClient || (typeof window.getDb === 'function' ? window.getDb(undefined, window.SUPABASE_KEY) : null);
    const truth = { topups: null, listings: null, sellers: null, gcash: null, err: null, isAdmin: null };
    try {
      const worker = (typeof window.whWorker === 'function' ? window.whWorker() : null)
                     || localStorage.getItem('wh_last_worker') || null;
      if (worker) {
        const { data: adm } = await db.from('marketplace_platform_admins').select('worker_name').eq('worker_name', worker).limit(1);
        truth.isAdmin = !!(adm && adm.length);
      }
      const { count: tc, error: e1 } = await db.from('v_service_credit_topups_truth')
        .select('id', { count: 'exact', head: true }).eq('status', 'pending_verification');
      if (e1) truth.err = e1.message; else truth.topups = tc ?? null;

      const { count: lc, error: e2 } = await db.from('v_marketplace_listings_truth')
        .select('id', { count: 'exact', head: true }).eq('status', 'draft');
      if (e2) truth.err = truth.err || e2.message; else truth.listings = lc ?? null;

      // the badge counts ACTIONABLE sellers, so the truth query must ask the same question
      const { data: srows, error: e3 } = await db.from('v_marketplace_sellers_truth')
        .select('worker_name,kyb_verified,cert_verified,certifications')
        .or('kyb_verified.eq.false,cert_verified.eq.false').limit(200);
      if (e3) truth.err = truth.err || e3.message;
      else truth.sellers = (srows || []).filter(s => !s.kyb_verified || (!s.cert_verified && s.certifications)).length;

      const { count: gc, error: e4 } = await db.from('v_gcash_receipts_needing_eyes')
        .select('reference', { count: 'exact', head: true });
      if (e4) truth.err = truth.err || e4.message; else truth.gcash = gc ?? null;
    } catch (e) { truth.err = String(e).slice(0, 160); }
    return { shown, truth, bypassNote, chars: txt.length };
  });

  if (!acct) {
    check(persona, 'anon-not-a-false-all-clear',
          reading.bypassNote !== null || reading.shown.topups === null,
          `a signed-out visitor is either told the queues are not theirs to see, or shown no queue `
          + `count at all (bypassNote=${JSON.stringify((reading.bypassNote || '').slice(0, 60))})`);
    await ctx.close();
    continue;
  }

  // The page's own admin determination must agree with the table. If it does not, every verdict
  // below is about the wrong screen.
  check(persona, 'capability-agrees',
        reading.truth.isAdmin === acct.platformAdmin,
        `marketplace_platform_admins says isAdmin=${reading.truth.isAdmin}, this prover expected `
        + `${acct.platformAdmin} — the persona table and the database must not disagree`);

  if (!acct.platformAdmin) {
    // The whole point: an empty queue a non-admin cannot see must NOT read as "nothing waiting".
    check(persona, 'names-the-limitation', !!reading.bypassNote,
          reading.bypassNote
            ? `the console says so: "${reading.bypassNote.slice(0, 110)}"`
            : `the queues render with NO notice that this caller cannot see what is waiting — a zero `
              + `here is indistinguishable from an all-clear, which is the most expensive empty state `
              + `this console can show`);
    await ctx.close();
    continue;
  }

  if (reading.truth.err) {
    check(persona, 'truth-readable', false,
          `the truth views would not answer for this admin: ${reading.truth.err} — instrument, not the surface`);
    await ctx.close();
    continue;
  }

  const pairs = [
    ['svc-topups-count',     reading.shown.topups,   reading.truth.topups,   'top-ups awaiting verification', 50],
    ['mkt-listings-count',   reading.shown.listings, reading.truth.listings, 'listings still in draft',       50],
    ['mkt-sellers-count',    reading.shown.sellers,  reading.truth.sellers,  'sellers with something to verify', 50],
    ['gcash-receipts-count', reading.shown.gcash,    reading.truth.gcash,    'GCash receipts needing eyes',   null],
  ];
  for (const [id, raw, want, label, cap] of pairs) {
    const got = readCount(raw);
    if (got.kind === 'absent') {
      check(persona, `${id}-attributed`, false,
            `#${id} is not on this surface, so the ${label} it should carry was never shown — not judged, not passed`);
      continue;
    }
    if (got.kind === 'gap') {
      check(persona, `${id}-attributed`, false,
            `#${id} shows an em-dash: the read failed for an admin who is entitled to it — a stated `
            + `gap is honest, but it is not this oracle holding`);
      continue;
    }
    if (got.kind === 'capped') {
      check(persona, `${id}-attributed`, cap !== null && want !== null && want >= cap,
            `#${id}='${got.n}+' discloses the ${cap}-row cap, and ${label}=${want} — a cap is not a total, `
            + `so this holds only while the truth is at least ${cap}`);
      continue;
    }
    if (got.kind !== 'num') {
      check(persona, `${id}-attributed`, false, `#${id} shows ${JSON.stringify(got.t)}, neither a number nor a stated gap`);
      continue;
    }
    check(persona, `${id}-attributed`, want !== null && got.n === want,
          `#${id}='${got.n}' vs ${label}=${want === null ? 'UNREAD' : want}`);
  }

  // The cover's ARITHMETIC is not re-derived here (see the header); its discipline is.
  const cover = (reading.shown.cover ?? '').trim();
  check(persona, 'cover-carries-its-unit-or-states-its-gap',
        /^[—–-]$/.test(cover) || /^\d+(\.\d+)?x$/.test(cover),
        `#cp-cover='${cover}' — a ratio must carry its ×/x beside peso figures, and an unknown cover `
        + `must be a stated gap, never a 0 (0 is the reading that says the platform is insolvent)`);

  await ctx.close();
}
await browser.close();

writeFileSync(REPORT, JSON.stringify({ generated: new Date().toISOString(), results }, null, 1));
const pass = results.filter(r => r.pass).length;
console.log(`\n  ${pass}/${results.length} hold — ${REPORT}`);
process.exit(pass === results.length ? 0 : 1);
