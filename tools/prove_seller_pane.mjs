/* prove_seller_pane.mjs — the marketplace-seller "populated" oracle, executable.
 *
 * The 34 stale LM-*-seller-*-populated rows all claim one thing: on /workhive/marketplace-seller.html
 * the surface renders real rows and EVERY visible number matches its source of truth. A generic
 * structural walk cannot settle that — it can see that a number rendered and is not NaN, which is
 * the shape of a bank that becomes decoration — so merge_walk_results refuses those rows by design
 * ("behavioural oracle, structural probe"). This is the missing half, and it is deliberately a
 * SIBLING of tools/prove_services_pane.mjs rather than a new invention: same persona set, same
 * disciplines, same report shape, so the two cannot drift into disagreeing about one platform.
 *
 *   node tools/prove_seller_pane.mjs                     # all personas
 *   node tools/prove_seller_pane.mjs --persona seller
 *
 * WHY GATE-BACKED EVIDENCE AND NOT ANOTHER WALK. A live-walk row expires the moment any dep's sha
 * moves — utils.js alone backs 623 rows — so a walked green starts dying immediately. A row carried
 * by a registered gate is re-earned by RUNNING the gate. Measured 2026-09-07: the marketplace green
 * fell 389 -> 307 and 475 -> 259 purely because edits expired walked rows, while the gate-backed
 * ones held. So the point of this file is not to turn 34 rows green today; it is to put them on
 * footing that survives tomorrow's edit.
 *
 * THE FOUR NUMBERS THIS SURFACE SHOWS, each attributed to its OWN element rather than matched by
 * position (marketplace-seller.html:890-919):
 *   #badge-listings   / #ps-listings     the seller's own listings   -> v_marketplace_listings_truth
 *   #badge-inquiries                     pending inquiries            -> v_marketplace_inquiries_truth
 *   #ps-pending-inq                      pending inquiries again      -> the same truth, and the two
 *                                                                        must agree with each other
 *   #ps-sales                            completed sales              -> v_marketplace_sellers_truth
 *
 * Disciplines carried in from the bank's own lessons, each paid for once already:
 *  - an EM-DASH is a FAILED READ, never a zero. `_statOrGap` ships '—' exactly so an unknown count
 *    is not printed as 0, and a probe that reads it as 0 would call a broken page correct.
 *  - every DB truth is asked FROM THE PAGE under the caller's own jwt claims, because the truth
 *    views are security_invoker — asked as anybody else they answer for the wrong caller.
 *  - a check that cannot run FAILS; it never skips. A number still showing its placeholder is the
 *    page saying "I do not know", and a comparison that never happened must never read as agreement.
 *  - the adversarial personas hold no special grants, so for a RENDER-truth claim they are
 *    capability-identical to any signed-in member and the seller run is their measurement; their
 *    adversarial depth lives in the S-family's own non-populated rows.
 *
 * Output: per-check PASS/FAIL lines + seller_pane_report.json; exit 1 on any FAIL.
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const PERSONAS = {
  buyer:    { email: 'pabloaguilar@auth.workhiveph.com', pw: 'test1234' },
  provider: { email: 'bryangarcia@auth.workhiveph.com', pw: 'test1234' },
  admin:    { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234' },
  seller:   { email: 'jerichobonifacio@auth.workhiveph.com', pw: 'test1234' },
  anon:     null,
};

const args = process.argv.slice(2);
const only = (() => { const i = args.indexOf('--persona'); return i >= 0 ? args[i + 1] : null; })();
// A --persona spot-check must not overwrite the full sweep's verdicts: the bankers read this file
// and cannot tell one persona from all of them. Narrowed runs get their own report.
const REPORT = only ? `seller_pane_report.persona-${only}.json`.replace(/[^\w.-]+/g, '_')
                    : 'seller_pane_report.json';

const results = [];
function check(persona, name, pass, detail) {
  results.push({ persona, name, pass: !!pass, detail });
  console.log(`  ${pass ? 'PASS' : 'FAIL'} — ${persona} / ${name}: ${detail}`);
}

/** '—' (or '-') means the read failed. Anything else must parse as an integer to be comparable. */
function readNum(raw) {
  const t = (raw ?? '').trim();
  if (t === '' ) return { kind: 'absent' };
  if (/^[—–-]$/.test(t)) return { kind: 'gap' };
  const n = Number(t.replace(/[, ]/g, ''));
  return Number.isFinite(n) ? { kind: 'num', n } : { kind: 'unparsed', t };
}

const browser = await chromium.launch();
for (const [persona, acct] of Object.entries(PERSONAS)) {
  if (only && persona !== only) continue;
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const p = await ctx.newPage();

  if (acct) {
    // sign in through the page's own client so the session lands in the page's storage
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

  await p.goto(`${ORIGIN}/marketplace-seller.html`, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await p.waitForTimeout(4000);
  // let the lists finish; showSkeletons() paints into #content-area and the renderers replace it
  await p.waitForFunction(() => {
    const a = document.getElementById('content-area');
    return a && !a.querySelector('.skel, .wh-cardskel');
  }, { timeout: 20000 }).catch(() => {});

  const reading = await p.evaluate(async () => {
    const txt = (document.body.innerText || '');
    const el = id => document.getElementById(id);
    const shown = {
      badgeListings:  el('badge-listings')?.textContent ?? null,
      badgeInquiries: el('badge-inquiries')?.textContent ?? null,
      psListings:     el('ps-listings')?.textContent ?? null,
      psPendingInq:   el('ps-pending-inq')?.textContent ?? null,
      psSales:        el('ps-sales')?.textContent ?? null,
    };
    const gapNoteShown = (() => { const g = el('ps-gap-note'); return g ? !g.hidden : null; })();
    // ANON: PRESENT IN THE DOM IS NOT SHOWN TO A PERSON. marketplace-seller.html renders its
    // whole dashboard markup and gates it behind 'Sign In Required — You need to be signed in
    // to view your seller dashboard', so #badge-listings EXISTS carrying '0' while nobody can
    // see it. A DOM-presence check called that a defect; the page is doing exactly the right
    // thing. Ask what the visitor can actually read, the same correction the busy-indicator
    // lens needed for display:contents skeletons earlier today.
    const vis = e => { if (!e) return false; const r = e.getBoundingClientRect();
      const st = getComputedStyle(e);
      return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none'; };
    const saysSignInRequired = /sign(ed)? in (required|to)|you need to be signed in/i.test(txt);
    const anyFigureVisible = ['badge-listings','badge-inquiries','ps-listings','ps-pending-inq','ps-sales']
      .some(id => vis(el(id)));
    const signInInvite = saysSignInRequired && !anyFigureVisible;

    // truth, asked from the page as THIS caller (security_invoker views answer for auth.uid())
    const db = window._whSupabaseClient || (typeof window.getDb === 'function' ? window.getDb(undefined, window.SUPABASE_KEY) : null);
    const truth = { name: null, listings: null, pending: null, sales: null, err: null };
    try {
      const { data: u } = await db.auth.getUser();
      const uid = u?.user?.id || null;
      // WORKER_NAME is a page-scoped `let`, not a window property, so reading window.WORKER_NAME
      // returns undefined and every comparison below would run against 'null' — page-scoped
      // symbols defeat probes. The page derives it from whWorker(), which is the shared helper
      // over wh_last_worker in localStorage; ask the same source the page asked.
      const worker = (typeof window.whWorker === 'function' ? window.whWorker() : null)
                     || localStorage.getItem('wh_last_worker') || null;
      truth.name = worker;
      if (uid && worker) {
        const { count: lc, error: e1 } = await db.from('v_marketplace_listings_truth')
          .select('id', { count: 'exact', head: true }).eq('seller_name', worker);
        if (e1) truth.err = e1.message; else truth.listings = lc ?? null;

        const { count: pc, error: e2 } = await db.from('v_marketplace_inquiries_truth')
          .select('id', { count: 'exact', head: true }).eq('seller_name', worker).eq('status', 'pending');
        if (e2) truth.err = truth.err || e2.message; else truth.pending = pc ?? null;

        const { data: srow, error: e3 } = await db.from('v_marketplace_sellers_truth')
          .select('total_sales').eq('worker_name', worker).limit(1);
        if (e3) truth.err = truth.err || e3.message;
        else truth.sales = srow && srow.length ? Number(srow[0].total_sales ?? 0) : 0;
      }
    } catch (e) { truth.err = String(e).slice(0, 160); }
    return { shown, truth, gapNoteShown, signInInvite, saysSignInRequired, anyFigureVisible, chars: txt.length };
  });

  if (!acct) {
    // anon owns no seller console; the honest render is an invitation, not a page of zeros.
    check(persona, 'anon-invite', reading.signInInvite,
          `a signed-out visitor is told to sign in and is shown no seller figure `
          + `(saysSignInRequired=${reading.saysSignInRequired}, anyFigureVisible=${reading.anyFigureVisible}) — `
          + `the dashboard markup may EXIST behind the gate, it just may not be readable`);
    await ctx.close();
    continue;
  }

  check(persona, 'identity-resolved', !!reading.truth.name,
        `the page resolved its own WORKER_NAME=${JSON.stringify(reading.truth.name)} — without it every `
        + `comparison below would be against the wrong question`);

  if (reading.truth.err) {
    check(persona, 'truth-readable', false,
          `the truth views would not answer for this caller: ${reading.truth.err} — instrument, not the surface`);
    await ctx.close();
    continue;
  }

  // Each number against ITS OWN source. A gap is a stated failure, and it is only honest when the
  // page also raises its gap note — a dash with no explanation is the defect _statOrGap exists to avoid.
  const pairs = [
    ['badge-listings',  reading.shown.badgeListings,  reading.truth.listings, 'listings this seller owns'],
    ['ps-listings',     reading.shown.psListings,     reading.truth.listings, 'listings this seller owns'],
    ['badge-inquiries', reading.shown.badgeInquiries, reading.truth.pending,  'inquiries still pending'],
    ['ps-pending-inq',  reading.shown.psPendingInq,   reading.truth.pending,  'inquiries still pending'],
    ['ps-sales',        reading.shown.psSales,        reading.truth.sales,    'completed sales'],
  ];
  for (const [id, raw, want, label] of pairs) {
    const got = readNum(raw);
    if (got.kind === 'absent') {
      check(persona, `${id}-attributed`, false,
            `#${id} is not on this surface, so the ${label} it should carry was never shown — not judged, not passed`);
      continue;
    }
    if (got.kind === 'gap') {
      // A dash is legitimate ONLY as a stated failure, and the page must say so beside it.
      check(persona, `${id}-attributed`, reading.gapNoteShown === true,
            `#${id} shows an em-dash (read failed) and the gap note is ${reading.gapNoteShown ? 'raised' : 'NOT raised'} — `
            + `an unknown count must say it is unknown, never stand as a number`);
      continue;
    }
    if (got.kind !== 'num') {
      check(persona, `${id}-attributed`, false, `#${id} shows ${JSON.stringify(got.t)}, which is neither a number nor a stated gap`);
      continue;
    }
    check(persona, `${id}-attributed`, want !== null && got.n === want,
          `#${id}='${got.n}' vs ${label} for ${reading.truth.name}=${want === null ? 'UNREAD' : want} `
          + `(em-dash = failed read, not 0)`);
  }

  // The same figure rendered twice must agree with ITSELF, or one of the two is lying to whoever
  // happens to be looking at that half of the screen.
  const a = readNum(reading.shown.badgeInquiries), b = readNum(reading.shown.psPendingInq);
  check(persona, 'pending-agrees-with-itself',
        a.kind === b.kind && (a.kind !== 'num' || a.n === b.n),
        `#badge-inquiries=${JSON.stringify((reading.shown.badgeInquiries || '').trim())} vs `
        + `#ps-pending-inq=${JSON.stringify((reading.shown.psPendingInq || '').trim())} — one screen, one number`);

  await ctx.close();
}
await browser.close();

writeFileSync(REPORT, JSON.stringify({ generated: new Date().toISOString(), results }, null, 1));
const pass = results.filter(r => r.pass).length;
console.log(`\n  ${pass}/${results.length} hold — ${REPORT}`);
process.exit(pass === results.length ? 0 : 1);
