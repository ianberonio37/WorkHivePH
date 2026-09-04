/* prove_market_attribution.mjs — the NUMBER-HALF of the marketplace surfaces' populated oracles.
 *
 * walk_owed_scenarios' populated probe proves the STRUCTURAL half (rows render, no junk, no raw
 * enum) and says plainly it cannot know a surface's truth query. This is that other half, per
 * surface, the way the 2026-08-06 hand-walks did it: every visible number is attributed to ITS OWN
 * LABEL, then compared to the view the page itself reads, asked from the page under the caller's
 * own jwt claims (they are security_invoker views — asked as anyone else they answer for the wrong
 * caller). An em-dash is a failed read, never 0.
 *
 *   node tools/prove_market_attribution.mjs                    # all four surfaces
 *   node tools/prove_market_attribution.mjs --surface market
 *
 * Surfaces and their anchors (grounded in each page's own source):
 *   market   /marketplace.html            count-parts/-training/-jobs badges vs
 *                                         v_marketplace_listings_truth published counts per section
 *                                         (marketplace.html:1583-1586, the page's own reads)
 *   seller   /marketplace-seller.html     #cw-available vs rpc provider_credit_balance — the page
 *                                         renders Number(data) (marketplace-seller.html:1981)
 *   profile  /marketplace-seller-profile  #stat-rating vs v_marketplace_sellers_truth.rating_avg
 *                                         (rendered avg.toFixed(1)+'★' or 'Not rated'; MK1: the
 *                                         canonical column only, never recomputed from reviews)
 *   admin    /platform-actions.html       #mkt-listings-count vs the draft-moderation read the pane
 *                                         itself makes (v_marketplace_listings_truth status=draft,
 *                                         limit 50 — platform-actions.html:419)
 *
 * Output: per-check PASS/FAIL + market_attribution_report.json; exit 1 on any FAIL.
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const ACCTS = {
  // hive/worker seeded into localStorage the way walk_owed_scenarios does it: pages resolve
  // identity from whWorker()/whHiveId() (localStorage), and a session alone leaves HIVE_ID '' -
  // community then bounces to hive.html BY DESIGN (the hive picker). Pablo's b4f7fe63 is the
  // fixture hive the rest of the harnesses use (50 community posts).
  buyer:  { email: 'pabloaguilar@auth.workhiveph.com', pw: 'test1234',
            hive: 'b4f7fe63-92e1-4f8d-b96e-625c3f85ba61', worker: 'Pablo Aguilar' },
  seller: { email: 'bryangarcia@auth.workhiveph.com', pw: 'test1234',
            hive: '084c113b-99c0-45c6-a8e8-b4b8349da46d', worker: 'Bryan Garcia' },
  admin:  { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234',
            hive: '084c113b-99c0-45c6-a8e8-b4b8349da46d', worker: 'Leandro Marquez' },
};

const args = process.argv.slice(2);
const only = (() => { const i = args.indexOf('--surface'); return i >= 0 ? args[i + 1] : null; })();
// A --surface spot-check must not overwrite the full sweep's verdicts: bank_prover_reports.py reads
// this file and cannot tell one surface from all of them. Narrowed runs get their own report.
const REPORT = only ? `market_attribution_report.surface-${only}.json`.replace(/[^\w.-]+/g, '_')
                    : 'market_attribution_report.json';
const results = [];
const check = (surface, name, pass, detail) => {
  results.push({ surface, name, pass: !!pass, detail });
  console.log(`  ${pass ? 'PASS' : 'FAIL'} — ${surface} / ${name}: ${detail}`);
};

const browser = await chromium.launch();
async function signedPage(acct, viewport) {
  const ctx = await browser.newContext({ viewport: viewport || { width: 390, height: 844 } });
  const p = await ctx.newPage();
  await p.goto(`${ORIGIN}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await p.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
  const s = await p.evaluate(async ({ email, pw, hive, worker }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(undefined, window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email, password: pw });
      if (hive) localStorage.setItem('wh_active_hive_id', hive);
      if (worker) localStorage.setItem('wh_last_worker', worker);
      return { ok: !error && !!data?.session, err: error?.message || null };
    } catch (e) { return { ok: false, err: String(e).slice(0, 120) }; }
  }, acct);
  return { ctx, p, signedIn: s.ok, err: s.err };
}

// ── market: the section tab badges, each against the page's own truth query ──────────────────────
if (!only || only === 'market') {
  const { ctx, p, signedIn, err } = await signedPage(ACCTS.buyer);
  if (!signedIn) check('market', 'sign-in', false, `harness: ${err}`);
  else {
    await p.goto(`${ORIGIN}/marketplace.html`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(6000);
    const r = await p.evaluate(async () => {
      const db = window._whSupabaseClient || window.getDb(undefined, window.SUPABASE_KEY);
      const badge = id => document.getElementById(id)?.textContent?.trim() ?? null;
      const truthCount = async (section) => {
        const { count, error } = await db.from('v_marketplace_listings_truth')
          .select('id', { count: 'exact', head: true }).eq('status', 'published').eq('section', section);
        return error ? null : count;
      };
      return {
        parts: { shown: badge('count-parts'), truth: await truthCount('parts') },
        training: { shown: badge('count-training'), truth: await truthCount('training') },
        jobs: { shown: badge('count-jobs'), truth: await truthCount('jobs') },
      };
    });
    for (const [sec, v] of Object.entries(r)) {
      check('market', `badge-${sec}`,
        v.shown !== null && v.shown !== '—' && v.truth !== null && String(v.truth) === v.shown,
        `#count-${sec}='${v.shown}' vs v_marketplace_listings_truth published ${sec}=${v.truth}`);
    }
    // every price painted on the grid must exist in the truth view - compared as a SET, the same
    // discipline the 2026-08-06 hand-walk used, so nothing matches by position or by luck
    const pr = await p.evaluate(async () => {
      const db = window._whSupabaseClient || window.getDb(undefined, window.SUPABASE_KEY);
      // TOP-LEVEL grid children only: [class*="card"] over main swept the services rate card and
      // nested nodes, whose figures are fees/rates, not listing prices (16 false orphans, first run)
      const painted = [...document.querySelectorAll('#listing-grid > *')]
        .map(el => (el.innerText.match(/₱\s?(\d[\d,]*(?:\.\d{1,2})?)/) || [])[1])
        .filter(Boolean).map(s => Number(s.replace(/,/g, '')));
      const { data, error } = await db.from('v_marketplace_listings_truth')
        .select('price').eq('status', 'published').limit(500);
      return { painted: painted.slice(0, 40), truth: error ? null : (data || []).map(x => Number(x.price)),
               why: error?.message || null };
    });
    if (pr.truth !== null && pr.painted.length) {
      const truthSet = new Set(pr.truth.map(n => n.toFixed(2)));
      const orphans = pr.painted.filter(n => !truthSet.has(n.toFixed(2)));
      check('market', 'prices-in-truth-set', orphans.length === 0,
        `${pr.painted.length} painted prices checked as a set against the truth view: ${orphans.length} orphan(s)${orphans.length ? ' ' + JSON.stringify(orphans.slice(0, 3)) : ''}`);
    } else {
      check('market', 'prices-in-truth-set', false,
        `nothing to compare (painted=${pr.painted.length}, truth=${pr.truth === null ? 'READ FAILED: ' + pr.why : pr.truth.length})`);
    }
  }
  await ctx.close();
}

// ── seller: the credit wallet, against the same RPC the page calls ───────────────────────────────
if (!only || only === 'seller') {
  const { ctx, p, signedIn, err } = await signedPage(ACCTS.seller);
  if (!signedIn) check('seller', 'sign-in', false, `harness: ${err}`);
  else {
    await p.goto(`${ORIGIN}/marketplace-seller.html`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(7000);
    const r = await p.evaluate(async () => {
      const db = window._whSupabaseClient || window.getDb(undefined, window.SUPABASE_KEY);
      const shown = document.getElementById('cw-available')?.textContent?.trim() ?? null;
      // the page resolves its provider id from the signed-in identity; replay that resolution
      const { data: u } = await db.auth.getUser();
      const uid = u?.user?.id || null;
      const { data: mem } = await db.from('hive_members').select('worker_name')
        .eq('auth_uid', uid).limit(1).maybeSingle();
      const { data: prov } = await db.from('service_providers').select('id')
        .eq('worker_name', mem?.worker_name || '').limit(1).maybeSingle();
      if (!prov?.id) return { shown, truth: null, why: 'no provider row for this identity' };
      const { data: bal, error } = await db.rpc('provider_credit_balance', { p_provider_id: prov.id });
      return { shown, truth: error ? null : Number(bal), why: error?.message || null };
    });
    const shownNum = r.shown === null ? null : Number(String(r.shown).replace(/[^\d.-]/g, ''));
    check('seller', 'wallet-available',
      r.shown !== null && r.shown !== '-' && r.truth !== null && Number.isFinite(shownNum)
        && Math.abs(shownNum - r.truth) < 0.005,
      `#cw-available='${r.shown}' vs provider_credit_balance=${r.truth}${r.why ? ' (' + r.why + ')' : ''} - to the centavo`);
    // the dashboard's headline stats, each against the read the page itself makes
    const st2 = await p.evaluate(async () => {
      const db = window._whSupabaseClient || window.getDb(undefined, window.SUPABASE_KEY);
      const el = id => document.getElementById(id)?.textContent?.trim() ?? null;
      const { data: u } = await db.auth.getUser();
      const { data: mem } = await db.from('hive_members').select('worker_name')
        .eq('auth_uid', u?.user?.id || '').limit(1).maybeSingle();
      const who = mem?.worker_name || '';
      const { data: seller } = await db.from('v_marketplace_sellers_truth')
        .select('total_sales').eq('worker_name', who).limit(1).maybeSingle();
      const { count } = await db.from('v_marketplace_listings_truth')
        .select('id', { count: 'exact', head: true }).eq('seller_name', who);
      return { sales: el('ps-sales'), listings: el('ps-listings'),
               truthSales: seller ? Number(seller.total_sales || 0) : null, truthListings: count };
    });
    check('seller', 'stat-sales',
      st2.sales !== null && st2.sales !== '—' && st2.truthSales !== null && String(st2.truthSales) === st2.sales,
      `#ps-sales='${st2.sales}' vs v_marketplace_sellers_truth.total_sales=${st2.truthSales}`);
    check('seller', 'stat-listings',
      st2.listings !== null && st2.listings !== '—' && st2.truthListings !== null && String(st2.truthListings) === st2.listings,
      `#ps-listings='${st2.listings}' vs the seller's listings count=${st2.truthListings}`);
  }
  await ctx.close();
}

// ── profile: the headline rating, against the canonical column only ──────────────────────────────
if (!only || only === 'profile') {
  const { ctx, p, signedIn, err } = await signedPage(ACCTS.buyer);
  if (!signedIn) check('profile', 'sign-in', false, `harness: ${err}`);
  else {
    await p.goto(`${ORIGIN}/marketplace-seller-profile.html?worker=Pablo%20Aguilar`,
                 { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(7000);
    const r = await p.evaluate(async () => {
      const db = window._whSupabaseClient || window.getDb(undefined, window.SUPABASE_KEY);
      const shown = document.getElementById('stat-rating')?.textContent?.trim() ?? null;
      const { data, error } = await db.from('v_marketplace_sellers_truth')
        .select('rating_avg, rating_count, active_listings_count')
        .eq('worker_name', 'Pablo Aguilar').limit(1).maybeSingle();
      // top-level children, not every nested [class*="card"] node (12 nodes for 2 cards, first run)
      const cards = [...document.querySelectorAll('#listing-grid > *')]
        .filter(el => el.getBoundingClientRect().width > 0 && !/^(p|P)$/.test(el.tagName)).length;
      const { count } = await db.from('v_marketplace_listings_truth')
        .select('id', { count: 'exact', head: true })
        .eq('seller_name', 'Pablo Aguilar').eq('status', 'published');
      return { shown, truth: error ? null : data, cards, truthListings: count };
    });
    const avg = Number(r.truth?.rating_avg || 0), cnt = Number(r.truth?.rating_count || 0);
    const expected = (avg && cnt) ? avg.toFixed(1) + '★' : 'Not rated';
    check('profile', 'headline-rating', r.shown !== null && r.truth !== null && r.shown === expected,
      `#stat-rating='${r.shown}' vs canonical rating_avg=${r.truth?.rating_avg}/count=${r.truth?.rating_count} -> expected '${expected}'`);
    check('profile', 'listing-cards', r.truthListings !== null && r.cards === Math.min(r.truthListings, 60),
      `rendered cards=${r.cards} vs truth published listings=${r.truthListings} (page cap 60)`);
  }
  await ctx.close();
}

// ── admin: the moderation queue count, against the pane's own read ───────────────────────────────
if (!only || only === 'admin') {
  const { ctx, p, signedIn, err } = await signedPage(ACCTS.admin);
  if (!signedIn) check('admin', 'sign-in', false, `harness: ${err}`);
  else {
    await p.goto(`${ORIGIN}/platform-actions.html`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(8000);
    const r = await p.evaluate(async () => {
      const db = window._whSupabaseClient || window.getDb(undefined, window.SUPABASE_KEY);
      const badge = id => document.getElementById(id)?.textContent?.trim() ?? null;
      const out = {};
      { const { count, error } = await db.from('v_marketplace_listings_truth')
          .select('id', { count: 'exact', head: true }).eq('status', 'draft');
        out.drafts = { shown: badge('mkt-listings-count'), truth: error ? null : Math.min(count, 50) }; }
      { const { data, error } = await db.from('v_marketplace_sellers_truth')
          .select('worker_name').or('kyb_verified.eq.false,cert_verified.eq.false').limit(50);
        out.sellers = { shown: badge('mkt-sellers-count'), truth: error ? null : (data || []).length }; }
      { // the header badge counts what is WAITING (new+triaged+in_progress), the pane's own rule
        const { data, error } = await db.from('platform_feedback').select('status').limit(500);
        const w = (data || []).filter(x => ['new', 'triaged', 'in_progress'].includes(x.status)).length;
        out.feedback = { shown: badge('fb-count-badge'), truth: error ? null : w }; }
      { const { data, error } = await db.from('v_service_credit_topups_truth')
          .select('id').eq('status', 'pending_verification').limit(50);
        out.topups = { shown: badge('svc-topups-count'), truth: error ? null : (data || []).length }; }
      return out;
    });
    const label = { drafts: '#mkt-listings-count vs draft listings (limit 50)',
                    sellers: '#mkt-sellers-count vs sellers awaiting verification (limit 50)',
                    feedback: '#fb-count-badge vs platform_feedback WAITING (new+triaged+in_progress)',
                    topups: '#svc-topups-count vs pending_verification top-ups (limit 50)' };
    for (const [k, v] of Object.entries(r)) {
      check('admin', `queue-${k}`,
        v.shown !== null && v.shown !== '—' && v.truth !== null && String(v.truth) === v.shown,
        `${label[k]}: shown='${v.shown}' truth=${v.truth}`);
    }
  }
  await ctx.close();
}

// ── money anchors for the surfaces the BC money_matches_ledger rows name ─────────────────────────
// profile: every ₱ painted on the listing cards exists in the truth view, to the centavo.
if (!only || only === 'profile_money') {
  const { ctx, p, signedIn, err } = await signedPage(ACCTS.buyer);
  if (!signedIn) check('profile_money', 'sign-in', false, `harness: ${err}`);
  else {
    await p.goto(`${ORIGIN}/marketplace-seller-profile.html?worker=Pablo%20Aguilar`,
                 { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(7000);
    const r = await p.evaluate(async () => {
      const db = window._whSupabaseClient || window.getDb(undefined, window.SUPABASE_KEY);
      const painted = [...document.querySelectorAll('#listing-grid > *')]
        .map(el => ((el.innerText || '').match(/₱\s?(\d[\d,]*(?:\.\d{1,2})?)/) || [])[1])
        .filter(Boolean).map(s => Number(s.replace(/,/g, '')));
      const { data, error } = await db.from('v_marketplace_listings_truth')
        .select('price').eq('seller_name', 'Pablo Aguilar').eq('status', 'published').limit(100);
      return { painted, truth: error ? null : (data || []).map(x => Number(x.price)), why: error?.message || null };
    });
    const truthSet = new Set((r.truth || []).map(n => n.toFixed(2)));
    const orphans = r.painted.filter(n => !truthSet.has(n.toFixed(2)));
    check('profile_money', 'card-prices-in-truth',
      r.truth !== null && r.painted.length > 0 && orphans.length === 0,
      `${r.painted.length} painted ₱ vs the seller's published truth prices: ${orphans.length} orphan(s)${r.why ? ' (' + r.why + ')' : ''}`);
  }
  await ctx.close();
}
// admin: every ₱ amount in the top-up queue equals its truth row, to the centavo.
if (!only || only === 'admin_money') {
  const { ctx, p, signedIn, err } = await signedPage(ACCTS.admin);
  if (!signedIn) check('admin_money', 'sign-in', false, `harness: ${err}`);
  else {
    await p.goto(`${ORIGIN}/platform-actions.html`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(8000);
    const r = await p.evaluate(async () => {
      const db = window._whSupabaseClient || window.getDb(undefined, window.SUPABASE_KEY);
      // climb from each Verify button until an element's text carries a ₱ - the nearest div is
      // .mod-actions (buttons only) and holds none (first run: 0 painted for 1 pending row)
      const painted = [...document.querySelectorAll('[data-topup-act="verify"]')]
        .map(b => { let el = b; for (let i = 0; i < 5 && el; i++) {
                      const m = (el.innerText || '').match(/₱\s?(\d[\d,]*(?:\.\d{1,2})?)/);
                      if (m) return m[1]; el = el.parentElement; } return null; })
        .filter(Boolean).map(s => Number(s.replace(/,/g, '')));
      const { data, error } = await db.from('v_service_credit_topups_truth')
        .select('amount').eq('status', 'pending_verification').limit(50);
      return { painted, truth: error ? null : (data || []).map(x => Number(x.amount)), why: error?.message || null };
    });
    const truthSet = new Set((r.truth || []).map(n => n.toFixed(2)));
    const orphans = r.painted.filter(n => !truthSet.has(n.toFixed(2)));
    check('admin_money', 'topup-amounts-in-truth',
      r.truth !== null && (r.truth.length === 0 || (r.painted.length > 0 && orphans.length === 0)),
      `${r.painted.length} painted top-up ₱ vs ${r.truth ? r.truth.length : '?'} pending truth amounts: ${orphans.length} orphan(s)${r.why ? ' (' + r.why + ')' : ''}`);
  }
  await ctx.close();
}
// market_svc: the rate card's ₱ figures equal v_service_catalog_truth.base_rate, to the centavo.
if (!only || only === 'market_svc_money') {
  const { ctx, p, signedIn, err } = await signedPage(ACCTS.buyer);
  if (!signedIn) check('market_svc_money', 'sign-in', false, `harness: ${err}`);
  else {
    await p.goto(`${ORIGIN}/marketplace.html?section=services`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(4000);
    await p.evaluate(() => document.querySelector('.section-tab[data-section="services"]')?.click());
    await p.waitForTimeout(3500);
    const r = await p.evaluate(async () => {
      const db = window._whSupabaseClient || window.getDb(undefined, window.SUPABASE_KEY);
      const pane = document.getElementById('services-pane');
      const painted = ((pane?.innerText || '').match(/₱\s?\d[\d,]*(?:\.\d{1,2})?/g) || [])
        .map(s => Number(s.replace(/[₱,\s]/g, '')));
      // window.HIVE_ID is IIFE-scoped on this page - the page's own segment choice follows its
      // resolved hive, which the harness seeded into localStorage; consumer was the wrong subject
      const seg = localStorage.getItem('wh_active_hive_id') ? 'industrial' : 'consumer';
      const { data, error } = await db.from('v_service_catalog_truth')
        .select('base_rate').eq('segment', seg).limit(200);
      return { painted, seg, truth: error ? null : (data || []).map(x => Number(x.base_rate)), why: error?.message || null };
    });
    const truthSet = new Set((r.truth || []).map(n => n.toFixed(2)));
    const orphans = r.painted.filter(n => !truthSet.has(n.toFixed(2)));
    check('market_svc_money', 'rate-card-in-truth',
      r.truth !== null && r.painted.length > 0 && orphans.length === 0,
      `${r.painted.length} painted service ₱ vs catalog base rates: ${orphans.length} orphan(s)${orphans.length ? ' ' + JSON.stringify(r.painted.filter(n => !truthSet.has(n.toFixed(2))).slice(0, 3)) : ''}${r.why ? ' (' + r.why + ')' : ''}`);
  }
  await ctx.close();
}

// ── admin topup queue: reachable to a thumb, and never all-clear on a dead session ───────────────
if (!only || only === 'admin_queue') {
  const { ctx, p, signedIn, err } = await signedPage(ACCTS.admin);
  if (!signedIn) check('admin_queue', 'sign-in', false, `harness: ${err}`);
  else {
    await p.goto(`${ORIGIN}/platform-actions.html`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(8000);
    // R-topup-queue-reachable: the Verify button on the queue that mints every credit must be a
    // real 44px target AND actually hittable (elementFromPoint at its centre returns the button
    // itself, scrolled into view first) - a covered control passes a rect check and fails a finger.
    const reach = await p.evaluate(() => {
      const b = document.querySelector('[data-topup-act="verify"]');
      if (!b) return { present: false };
      b.scrollIntoView({ block: 'center' });
      const r = b.getBoundingClientRect();
      const at = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
      return { present: true, w: Math.round(r.width), h: Math.round(r.height),
               hit: at === b || b.contains(at) };
    });
    check('admin_queue', 'verify-reachable',
      reach.present && reach.w >= 44 && reach.h >= 44 && reach.hit,
      reach.present
        ? `Verify measures ${reach.w}x${reach.h}px and elementFromPoint at its centre ${reach.hit ? 'returns it' : 'returns SOMETHING ELSE (covered)'}`
        : 'no pending top-up row rendered a Verify button - nothing to measure');
    // R-topup-false-allclear: with every queue read answered by a REAL dead-session shape
    // (401/PGRST301, not a bare 42501 which would make this a permission test), the page must not
    // assert an all-clear - an empty-looking queue on a dead session is the most expensive lie
    // this console can tell.
    await ctx.route(/\/rest\/v1\//, r => {
      // READ-shaped RPCs travel as POSTs - a dead session answers RPC reads 401 too, and leaving
      // them alive under this induction under-tests the queue the probe is accusing.
      const _m = r.request().method();
      if (/GET|HEAD/i.test(_m) || (/POST/i.test(_m) && r.request().url().includes('/rpc/'))) {
        return r.fulfill({ status: 401, contentType: 'application/json',
          body: JSON.stringify({ code: 'PGRST301', message: 'JWT expired' }) });
      }
      return r.continue();
    });
    await p.reload({ waitUntil: 'domcontentloaded' }).catch(() => {});
    await p.waitForTimeout(5000);
    const dead = await p.evaluate(() => {
      const t = (document.body.innerText || '').replace(/\s+/g, ' ');
      return {
        allClear: /all clear|nothing waiting|no top-?ups waiting|queue is empty/i.test(t) &&
                  !/session|sign in|expired|couldn/i.test(t),
        namesSession: /session|sign ?in|expired/i.test(t),
        sample: t.slice(0, 160),
      };
    });
    await ctx.unroute(/\/rest\/v1\//).catch(() => {});
    check('admin_queue', 'no-false-allclear-on-dead-session',
      !dead.allClear && dead.namesSession,
      `injected 401/PGRST301 into every queue read: asserts all-clear=${dead.allClear}, names the session=${dead.namesSession}`);
  }
  await ctx.close();
}

// ── community: the profile card's own two numbers, vs the page's own queries ─────────────────────
if (!only || only === 'community') {
  const { ctx, p, signedIn, err } = await signedPage(ACCTS.buyer);
  if (!signedIn) check('community', 'sign-in', false, `harness: ${err}`);
  else {
    await p.goto(`${ORIGIN}/community.html`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(8000);
    const r = await p.evaluate(async () => {
      const db = window._whSupabaseClient || window.getDb(undefined, window.SUPABASE_KEY);
      const el = id => document.getElementById(id)?.textContent?.trim() ?? null;
      const { data: u } = await db.auth.getUser();
      // the SUBJECT is the page's own resolution: whHiveId()/whWorker() (seeded at sign-in), never
      // a limit(1) guess over a multi-hive membership - the wrong hive is the wrong subject
      const hive = localStorage.getItem('wh_active_hive_id');
      const worker = localStorage.getItem('wh_last_worker');
      if (!hive || !worker) return { why: 'identity keys not seeded' };
      const { count } = await db.from('v_community_posts_truth').select('id', { count: 'exact', head: true })
        .eq('hive_id', hive).eq('author_name', worker).is('deleted_at', null);
      const { data: xp } = await db.from('community_xp').select('xp_total')
        .eq('hive_id', hive).eq('worker_name', worker).maybeSingle();
      return { posts: el('profile-posts'), xp: el('profile-xp'),
               truthPosts: count, truthXp: xp?.xp_total ?? 0 };
    });
    check('community', 'profile-posts', r.posts !== null && r.posts !== '-' && r.truthPosts !== null
      && String(r.truthPosts) === r.posts,
      `#profile-posts='${r.posts}' vs caller's undeleted posts in their hive=${r.truthPosts}${r.why ? ' (' + r.why + ')' : ''}`);
    check('community', 'profile-xp', r.xp !== null && r.xp !== '-' && String(r.truthXp) === r.xp,
      `#profile-xp='${r.xp}' vs community_xp.xp_total=${r.truthXp}`);
  }
  await ctx.close();
}

// ── achievements: the composite score, recomputed from the truth view ────────────────────────────
if (!only || only === 'achievements') {
  const { ctx, p, signedIn, err } = await signedPage(ACCTS.buyer);
  if (!signedIn) check('achievements', 'sign-in', false, `harness: ${err}`);
  else {
    await p.goto(`${ORIGIN}/achievements.html`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(8000);
    const r = await p.evaluate(async () => {
      const db = window._whSupabaseClient || window.getDb(undefined, window.SUPABASE_KEY);
      const shown = document.getElementById('stat-composite')?.textContent?.trim() ?? null;
      const { data: u } = await db.auth.getUser();
      const { data: mem } = await db.from('hive_members').select('worker_name')
        .eq('auth_uid', u?.user?.id || '').eq('status', 'active').limit(1).maybeSingle();
      const { data, error } = await db.from('v_worker_achievements_truth')
        .select('current_level').eq('worker_name', mem?.worker_name || '');
      const truth = error ? null : (data || []).reduce((s, a) => s + (a.current_level || 0), 0);
      return { shown, truth, why: error?.message || null };
    });
    check('achievements', 'composite-score',
      r.shown !== null && r.shown !== '-' && r.truth !== null && String(r.truth) === r.shown,
      `#stat-composite='${r.shown}' vs sum(current_level) over the caller's rows=${r.truth}${r.why ? ' (' + r.why + ')' : ''}`);
  }
  await ctx.close();
}

// ── public_feed: the anon page, its cards vs its own exact public query ──────────────────────────
if (!only || only === 'public_feed') {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const p = await ctx.newPage();
  await p.goto(`${ORIGIN}/public-feed.html`, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await p.waitForTimeout(7000);
  const r = await p.evaluate(async () => {
    const db = window._whSupabaseClient || (typeof window.getDb === 'function' ? window.getDb(undefined, window.SUPABASE_KEY) : null);
    // .post-card exactly: [class*="post"] matched every nested post-head/post-content (75 for 15)
    const cards = document.querySelectorAll('#feed-list > .post-card').length;
    const { count, error } = await db.from('v_community_posts_truth')
      .select('id', { count: 'exact', head: true })
      .eq('public', true).eq('flagged', false).is('deleted_at', null);
    return { cards, truth: error ? null : Math.min(count, 20), why: error?.message || null };
  });
  check('public_feed', 'feed-cards', r.truth !== null && r.cards === r.truth,
    `first page renders ${r.cards} cards vs public+unflagged+undeleted truth (PAGE_SIZE 20 cap)=${r.truth}${r.why ? ' (' + r.why + ')' : ''}`);
  await ctx.close();
}

// ── handoffs: a flow that spans surfaces carries its context across (BJ cross_surface rows) ──────
if (!only || only === 'handoff_seller') {
  const { ctx, p, signedIn, err } = await signedPage(ACCTS.buyer);
  if (!signedIn) check('handoff_seller', 'sign-in', false, `harness: ${err}`);
  else {
    await p.goto(`${ORIGIN}/marketplace.html`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(6000);
    // `:visible` before .first(): document order alone picked a hidden pane's link once
    const link = p.locator('a.seller-link:visible').first();
    const href = await link.getAttribute('href').catch(() => null);
    const who = href ? decodeURIComponent((href.match(/worker=([^&]+)/) || [])[1] || '') : '';
    if (!who) check('handoff_seller', 'context-in-url', false, `no visible seller link with a worker param (href=${href})`);
    else {
      await link.click();
      await p.waitForTimeout(6000);
      const dest = await p.evaluate((w) => {
        const t = (document.body.innerText || '');
        const others = ['Pablo Aguilar', 'Leandro Marquez', 'Leonardo Romero', 'Dennis Aquino']
          .filter(n => n !== w && t.includes(n) === false ? false : n !== w && t.split(n).length > 2);
        return { title: document.title, namesWho: t.includes(w), url: location.pathname + location.search };
      }, who);
      check('handoff_seller', 'context-carried',
        /marketplace-seller-profile/.test(dest.url) && dest.namesWho && dest.title.includes(who),
        `card link carried worker=${who}; destination ${dest.url} titles '${dest.title}' and names them on the page`);
    }
  }
  await ctx.close();
}
if (!only || only === 'handoff_admin') {
  const { ctx, p, signedIn, err } = await signedPage(ACCTS.admin);
  if (!signedIn) check('handoff_admin', 'sign-in', false, `harness: ${err}`);
  else {
    await p.goto(`${ORIGIN}/marketplace.html`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(6000);
    const admin = await p.evaluate(() => {
      const a = document.getElementById('btn-admin-link');
      if (!a) return { present: false };
      const cs = getComputedStyle(a);
      return { present: true, visible: cs.display !== 'none', href: a.getAttribute('href') };
    });
    if (!admin.present || !admin.visible) {
      check('handoff_admin', 'admin-link-shown', false,
        `#btn-admin-link present=${admin.present} visible=${admin.visible} for a signed-in platform admin`);
    } else {
      await p.goto(`${ORIGIN}/${admin.href}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await p.waitForTimeout(8000);
      const dest = await p.evaluate(() => {
        const el = document.elementFromPoint(innerWidth / 2, innerHeight / 2);
        const overlay = el?.closest?.('#wh-retired-overlay');
        const queue = document.getElementById('mkt-listings-count');
        return { landed: location.pathname, deadEnd: !!overlay,
                 queueReachable: !!queue && queue.getBoundingClientRect !== undefined };
      });
      check('handoff_admin', 'moderation-reachable',
        /platform-actions/.test(dest.landed) && !dest.deadEnd && dest.queueReachable,
        `Admin link lands on ${dest.landed}; retired-overlay dead-end=${dest.deadEnd}; the moderation queue renders (its count badge exists)`);
    }
  }
  await ctx.close();
}

await browser.close();
const failed = results.filter(r => !r.pass);
writeFileSync(REPORT, JSON.stringify({
  ran_at: new Date().toISOString(), origin: ORIGIN,
  checks: results, pass: results.length - failed.length, fail: failed.length,
}, null, 1));
console.log(`\n  ${results.length - failed.length}/${results.length} hold — market_attribution_report.json`);
process.exit(failed.length ? 1 : 0);
