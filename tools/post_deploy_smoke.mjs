/* post_deploy_smoke.mjs — the COMPREHENSIVE post-deploy smoke (2026-09-04)
 *
 * The old runbook smoke was five flows (sign-in, logbook, one AI action, marketplace, log-watch).
 * That proves the critical PATH is alive; it says NOTHING about the other ~35 pages a person can
 * open. A deploy can leave the five happy-path surfaces green while a build error, a missing asset,
 * a stale _headers/CSP, or a bad edit dead-renders learn/*, resume, engineering-design, or an admin
 * console — and nobody sees it until a user does. Ian's instruction (2026-09-04): the post-deploy
 * smoke must cover the ENTIRE production surface, not a handful.
 *
 * WHAT IT DOES — two tiers over the WHOLE roster, reusing the proven checks from smoke_pages.mjs
 * (pageerror + console-error capture, the thin/stuck-skeleton catch that counts BOTH chars AND
 * controls, and the signed-out-is-not-broken guard):
 *
 *   TIER 1 — PUBLIC (anon): read BASE/sitemap.xml and load EVERY public URL (index, marketing,
 *     about/privacy/terms, public-feed, status, and all ~53 learn articles). Each must be 200,
 *     render (not a stuck skeleton), and log zero pageerrors. No auth — this is what an anon
 *     visitor and Googlebot see, and it is where a broken build shows first.
 *
 *   TIER 2 — APP (authed): sign in once with a prod test account, read its hive + role FROM THE SERVER, and load EVERY
 *     interactive app page. Each must render its own UI (not thin, not signed-out) and log zero
 *     errors. This is the coverage the five-flow smoke never had.
 *
 * IT IS BASE-URL CONFIGURABLE so it can be dry-run against the LOCAL stack before it is ever pointed
 * at prod (a smoke you cannot rehearse is theatre — ROLLBACK_RUNBOOK §7). Local rehearsal and the
 * real prod run are the SAME code, only the env differs.
 *
 * Usage:
 *   # prod (post-deploy):
 *   WH_SMOKE_BASE=https://workhiveph.com \
 *   WH_SMOKE_EMAIL=<prod test account> WH_SMOKE_PASS=<pw> WH_SMOKE_HIVE=<its bench hive id> \
 *   EXPECT_SW=<new sw.js version, e.g. v282> \
 *   node tools/post_deploy_smoke.mjs
 *
 *   # local rehearsal (verify the smoke itself works before trusting it on prod):
 *   WH_SMOKE_BASE=http://127.0.0.1:5000 \
 *   WH_SMOKE_EMAIL=leandromarquez@auth.workhiveph.com WH_SMOKE_PASS=test1234 \
 *   node tools/post_deploy_smoke.mjs
 *
 *   # scope to one tier while triaging: --tier=public | --tier=app | --tier=flows
 *   # sample learn articles instead of all (faster): --learn-sample=8
 *
 *   TIER 3 — FLOWS (BRH-AH, 2026-10-26): the runbook's Tier-0 critical paths, walked on production in the bench hive
 *     and undone - 1 sign in, 2 a logbook entry through the form at phone-390 and desktop-1280 (then trashed), 3 one AI
 *     action through ai-gateway, 4 a parts-staging recommendation accepted twice at once (one reservation; all of it
 *     removed after), 5 the production logs over the run for 54000 / 23505 / 5xx. It runs only with WH_SMOKE_HIVE set:
 *     its writes never land in a real tenant. Flow 5 reads the Management API with SUPABASE_ACCESS_TOKEN, or the
 *     token `supabase login` keeps in the Windows credential store (tools/supabase_cli_token.ps1); it goes nowhere else.
 *     Writes post_deploy_flows_report.json, held by tools/validate_prod_tier0_flows.py.
 *
 * Exit 0 = every page in scope loaded clean; exit 1 = at least one FAIL (report names which).
 * Writes post_deploy_smoke_report.json for the runbook record + rollback evidence.
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const BASE = (process.env.WH_SMOKE_BASE || 'https://workhiveph.com').replace(/\/$/, '');
const EMAIL = process.env.WH_SMOKE_EMAIL || '';
const PASS = process.env.WH_SMOKE_PASS || '';
const EXPECT_SW = process.env.EXPECT_SW || '';
const argv = process.argv.slice(2);
const TIER = (argv.find((a) => a.startsWith('--tier=')) || '').split('=')[1] || 'all';
const LEARN_SAMPLE = Number((argv.find((a) => a.startsWith('--learn-sample=')) || '').split('=')[1] || 0);
const THIN = 400;                 // body shorter than this AND under 5 controls rendered nothing
const SETTLE_PUBLIC = 3500;       // public pages paint fast
const SETTLE_APP = 7000;          // app pages fetch their own data first

/* TIER 2 roster — the interactive app pages that require a session. Kept explicit (not scraped)
 * because these are exactly the pages the sitemap does NOT list: they are app surfaces, not SEO
 * URLs. Tracks the nav-tools roster + the core authed surfaces; add a page here the day it ships. */
const APP_PAGES = [
  'index', 'hive', 'asset-hub', 'pm-scheduler', 'logbook', 'inventory',
  'analytics', 'analytics-report', 'alert-hub', 'assistant', 'achievements',
  'community', 'dayplanner', 'shift-brain', 'skillmatrix', 'voice-journal',
  'project-manager', 'project-report', 'report-sender', 'resume', 'audit-log',
  'engineering-design', 'marketplace', 'marketplace-seller', 'integrations',
  'ph-intelligence',
];

/* ★WHO THE ACCOUNT IS COMES FROM THE SERVER (BRH-AF, 2026-10-24). This seeded a LOCAL hive's id, a worker name and the
 * supervisor role into storage before loading pages - against production that claims a hive the account is not in,
 * the "stored hive is a cache of a server fact" class inside the instrument. The account's own active membership is
 * read after sign-in; with WH_SMOKE_HIVE set (the bench hive production smoke uses) the run refuses any other hive, so
 * a smoke account can never walk a real tenant's pages. */
const BENCH_HIVE = process.env.WH_SMOKE_HIVE || '';

const log = (s) => process.stdout.write(s + '\n');

/* pull every <loc> from the live sitemap so the public tier tracks the real SEO surface, not a
 * hand-list that drifts. Falls back to a known core set if the sitemap cannot be read. */
async function publicUrls(ctx) {
  const core = ['', 'about/', 'privacy-policy/', 'terms-of-service/', 'public-feed.html',
    'status.html', 'learn/', 'feedback/'];
  try {
    const p = await ctx.newPage();
    const r = await p.goto(`${BASE}/sitemap.xml`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    const xml = await p.content();
    await p.close();
    if (!r || !r.ok()) throw new Error('sitemap ' + (r && r.status()));
    let locs = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1].trim());
    locs = locs.map((u) => u.replace(/^https?:\/\/[^/]+/, '')).map((u) => u.replace(/^\//, ''));
    if (!locs.length) throw new Error('sitemap had 0 <loc>');
    if (LEARN_SAMPLE > 0) {
      const learn = locs.filter((u) => u.includes('learn/') && u !== 'learn/');
      const rest = locs.filter((u) => !learn.includes(u));
      locs = [...rest, ...learn.slice(0, LEARN_SAMPLE)];
    }
    return [...new Set(locs)];
  } catch (e) {
    log(`  (sitemap unreadable: ${String(e).slice(0, 80)} — falling back to core public set)`);
    return core;
  }
}

async function loadOne(ctx, url, settle, { authed }) {
  const page = await ctx.newPage();
  const errs = [];
  let status = 0, sw = '';
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 160)); });
  page.on('pageerror', (e) => errs.push('PAGEERROR ' + String(e.message).slice(0, 160)));
  try {
    const r = await page.goto(`${BASE}/${url}`, { waitUntil: 'domcontentloaded', timeout: 40000 });
    status = r ? r.status() : 0;
    await page.waitForTimeout(settle);
  } catch (e) { errs.push('NAV ' + String(e).slice(0, 120)); }
  const seen = await page.evaluate(() => {
    const t = document.body ? (document.body.innerText || '') : '';
    let swv = '';
    try { swv = (window.CACHE_NAME || window.SW_VERSION || '') + ''; } catch (_) {}
    return {
      chars: t.length,
      controls: document.querySelectorAll('button, a[href], input, select, textarea').length,
      signedOut: /sign in required|you need to be signed in|please sign in to/i.test(t),
      sw: swv,
    };
  }).catch(() => ({ chars: 0, controls: 0, signedOut: false, sw: '' }));
  sw = seen.sw;
  await page.close();
  const thin = seen.chars < THIN && seen.controls < 5;
  const httpBad = status && status >= 400;
  // signed-out only counts against an AUTHED page; a public page is anon by design
  const wrongSignedOut = authed && seen.signedOut;
  const ok = !errs.length && !thin && !httpBad && !wrongSignedOut;
  return { url, status, chars: seen.chars, controls: seen.controls, sw,
    signedOut: seen.signedOut, thin, errors: errs, ok };
}

const browser = await chromium.launch();
/* ★THE SMOKE IS NOT A VISITOR (BRH-AF, 2026-10-26). Every page logs a page_view to analytics_events, and the founder
 * console counts active hives, MAU and anonymous sessions from that table - so each post-deploy run added ~120 anonymous
 * sessions and, signed in, a bench hive and account to production's growth figures. The smoke's contexts answer those
 * inserts themselves and never send them. Page errors still reach client_errors: those would be real defects. */
async function quietContext(browser) {
  const c = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await c.route(/\/rest\/v1\/analytics_events/, (route) =>
    route.request().method() === 'POST' ? route.fulfill({ status: 201, body: '' }) : route.continue());
  return c;
}

/* sign in once and cache WHO the account is as the server answers it (shared by the app tier and the flows tier) */
async function signIn(ctx) {
  const boot = await ctx.newPage();
  await boot.goto(`${BASE}/shift-brain.html`, { waitUntil: 'domcontentloaded', timeout: 40000 });
  await boot.waitForFunction(() => !!(window.supabase && window.supabase.createClient), { timeout: 25000 });
  const signedIn = await boot.evaluate(async ({ email, password, bench }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    const { data: auth, error } = await db.auth.signInWithPassword({ email, password });
    if (error) return { ok: false, err: error.message };
    // the account's own active memberships, as the server answers them - never a hive the smoke assumes
    const { data: rows, error: mErr } = await db.from('hive_members')
      .select('hive_id, role, worker_name').eq('auth_uid', auth.user.id).eq('status', 'active');
    if (mErr) return { ok: false, err: `membership read refused: ${mErr.message}` };
    const mine = (rows || []).filter((r) => !bench || r.hive_id === bench);
    if (mine.length !== 1) {
      return { ok: false, err: bench ? `the account is not an active member of the bench hive ${bench}`
        : `the account holds ${(rows || []).length} active memberships - set WH_SMOKE_HIVE to the one to walk` };
    }
    const m = mine[0];
    const { data: h } = await db.from('hives').select('name').eq('id', m.hive_id).maybeSingle();
    ['wh_active_hive_id', 'wh_active_hive_name', 'wh_hive_role', 'WORKER_NAME'].forEach((k) => localStorage.removeItem(k));
    localStorage.setItem('wh_active_hive_id', m.hive_id);       // a cache of the answer just read, not an assumption
    if (h && h.name) localStorage.setItem('wh_active_hive_name', h.name);
    localStorage.setItem('wh_hive_role', m.role);
    localStorage.setItem('WORKER_NAME', m.worker_name || '');
    return { ok: true, hive: m.hive_id, hiveName: (h && h.name) || '', role: m.role, worker: m.worker_name || '' };
  }, { email: EMAIL, password: PASS, bench: BENCH_HIVE }).catch((e) => ({ ok: false, err: String(e) }));
  await boot.close();
  return signedIn;
}

/* flow 2 - a logbook entry through the page's own form, then moved to the trash the way the page does it */
async function flowLogbook(ctx, viewport) {
  const page = await ctx.newPage();
  await page.setViewportSize(viewport.size);
  const errs = [];
  page.on('pageerror', (e) => errs.push('PAGEERROR ' + String(e.message).slice(0, 160)));
  try {
    await page.goto(`${BASE}/logbook.html`, { waitUntil: 'load', timeout: 40000 });
    await page.waitForFunction(() => typeof openModal === 'function' && !!document.getElementById('log-form'), null, { timeout: 30000 });
    await page.waitForTimeout(2500);
    const r = await page.evaluate(async (vp) => {
      const tag = `TIER0-BENCH-${vp}-${Date.now()}`;
      document.getElementById('f-machine').value = tag;
      document.getElementById('f-maint-type').value = 'Inspection';
      document.getElementById('f-problem').value = 'Tier-0 smoke: a logbook entry is accepted';
      document.getElementById('f-action').value = 'Recorded and removed by the post-deploy check';
      const cat = document.getElementById('f-category');
      cat.value = Array.from(cat.options).find((o) => o.value).value;
      const open = document.querySelector('input[name="f-status"][value="Open"]');
      if (open) open.checked = true;
      document.getElementById('log-form').requestSubmit();
      const db = getDb();
      let row = null;
      for (let i = 0; i < 30 && !row; i++) {
        await new Promise((res) => setTimeout(res, 500));
        const { data } = await db.from('logbook').select('id, machine').eq('machine', tag).maybeSingle();
        row = data;
      }
      if (!row) return { ok: false, tag, err: 'no row after submit' };
      // undone the way the page undoes it: an update setting deleted_at is refused by logbook_hides_deleted
      const t = await whTrash(db, 'logbook', row.id, {});
      const { data: left } = await db.from('logbook').select('id').eq('id', row.id);
      return { ok: true, tag, saved: row.id, trashed: !!(t && t.ok), left: (left || []).length };
    }, viewport.name);
    return { flow: 2, viewport: viewport.name, ...r, ok: r.ok && r.trashed && r.left === 0 && !errs.length, errors: errs };
  } catch (e) {
    return { flow: 2, viewport: viewport.name, ok: false, errors: [...errs, 'NAV ' + String(e).slice(0, 160)] };
  } finally { await page.close(); }
}

/* flows 3 + 4 - one AI action through the gateway (budget guard on), and a staging recommendation accepted twice at once */
async function flowServer(ctx, hive) {
  const page = await ctx.newPage();
  try {
    await page.goto(`${BASE}/index.html`, { waitUntil: 'domcontentloaded', timeout: 40000 });
    await page.waitForFunction(() => typeof getDb === 'function', null, { timeout: 25000 });
    const ai = await page.evaluate(async (hive) => {
      const db = getDb(); const t0 = Date.now();
      const { data, error } = await db.functions.invoke('ai-gateway', {
        body: { agent: 'assistant', message: 'In one sentence: what does MTBF measure?', hive_id: hive } });
      const d = (data && data.data) || data || {};
      const answer = d.answer || d.reply || d.text || '';
      // a reply is not an answer: the orchestrator's no-sources deflection for a basic maintenance question means
      // retrieval reached nothing (2026-10-26: production's corpus was empty and its embedder refused)
      const deflected = /none of my sources returned|couldn't pull that from your hive/i.test(answer);
      return { flow: 3, ok: !error && !!answer && !deflected, deflected, ms: Date.now() - t0,
        err: error ? (error.message || String(error)) : (deflected ? 'the assistant deflected a basic question: retrieval reached nothing' : null),
        answer: String(answer).slice(0, 160), model_chain: (data && data.model_chain) || null };
    }, hive);
    const parts = await page.evaluate(async (hive) => {
      const db = getDb(); const stamp = Date.now();
      const itemId = 'inv-tier0' + stamp.toString(16);
      const { error: iErr } = await db.from('inventory_items').insert({ id: itemId, hive_id: hive, part_name: 'Tier-0 bench part',
        part_number: 'T0-' + stamp, qty_on_hand: 5, min_qty: 0, unit: 'pcs', category: 'Bearing',
        worker_name: localStorage.getItem('WORKER_NAME'), status: 'approved' });
      if (iErr) return { flow: 4, ok: false, step: 'part', err: iErr.message };
      const recId = crypto.randomUUID();
      const { error: rErr } = await db.from('parts_staging_recommendations').insert({ id: recId, hive_id: hive,
        asset_name: 'TIER0-BENCH-PUMP', failure_mode: 'Tier-0 check', risk_score: 0.5,
        parts: [{ item_id: itemId, qty_avg: 1, in_stock: 5, part_name: 'Tier-0 bench part', confidence: 0.9 }],
        rationale: 'post-deploy Tier-0 check', confidence: 0.9, status: 'pending',
        expires_at: new Date(Date.now() + 3600e3).toISOString() });
      if (rErr) { await db.from('inventory_items').delete().eq('id', itemId); return { flow: 4, ok: false, step: 'recommendation', err: rErr.message }; }
      const both = await Promise.all([1, 2].map(() => db.rpc('accept_parts_staging', { p_recommendation_id: recId, p_item_ids: [itemId] })));
      const { data: resv } = await db.from('parts_staged_reservations').select('id').eq('recommendation_id', recId);
      const answers = both.map((x) => x.data || (x.error && x.error.message) || null);
      // undone: the reservation, the recommendation and the part
      const undo = [
        await db.from('parts_staged_reservations').delete().eq('recommendation_id', recId),
        await db.from('parts_staging_recommendations').delete().eq('id', recId),
        await db.from('inventory_items').delete().eq('id', itemId),
      ].map((u) => (u.error ? u.error.message : 'ok'));
      const { data: leftR } = await db.from('parts_staged_reservations').select('id').eq('recommendation_id', recId);
      const { data: leftI } = await db.from('inventory_items').select('id').eq('id', itemId);
      const accepted = answers.filter((a) => a && a.ok).length;
      const left = (leftR || []).length + (leftI || []).length;
      return { flow: 4, ok: (resv || []).length === 1 && accepted === 1 && left === 0, reservations: (resv || []).length,
        accepted, answers, undo, left };
    }, hive);
    return [ai, parts];
  } finally { await page.close(); }
}

/* flow 5 - the production logs over the run (and the 15 minutes before it, the deploy's own wake) */
function managementToken() {
  if (process.env.SUPABASE_ACCESS_TOKEN) return process.env.SUPABASE_ACCESS_TOKEN;
  if (process.platform !== 'win32') return '';
  try {
    return execFileSync('powershell', ['-NoProfile', '-File', 'tools/supabase_cli_token.ps1'], { encoding: 'utf8' }).trim();
  } catch (_) { return ''; }
}
async function flowLogs(fromIso, toIso) {
  const ref = (BASE === 'https://workhiveph.com') ? 'hzyvnjtisfgbksicrouu' : '';
  if (!ref) return { flow: 5, ok: false, skipped: 'logs are read only for production' };
  const token = managementToken();
  if (!token) return { flow: 5, ok: false, skipped: 'no SUPABASE_ACCESS_TOKEN and no `supabase login` token' };
  const ask = async (sql) => {
    const u = `https://api.supabase.com/v1/projects/${ref}/analytics/endpoints/logs?sql=${encodeURIComponent(sql)}`
      + `&iso_timestamp_start=${fromIso}&iso_timestamp_end=${toIso}`;
    const r = await fetch(u, { headers: { Authorization: `Bearer ${token}` } });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(`logs ${r.status}: ${JSON.stringify(j).slice(0, 160)}`);
    return j.result || [];
  };
  try {
    const [counts] = await ask(`select
      countIf(source = 'postgres_logs' and (event_message like '%54000%' or event_message like '%statement timeout%' or event_message like '%stack depth%')) as pg_54000,
      countIf(source = 'postgres_logs' and (event_message like '%23505%' or event_message like '%duplicate key%')) as pg_23505,
      countIf(source = 'edge_logs' and toInt32OrZero(toString(log_attributes['response.status_code'])) >= 500) as edge_5xx,
      countIf(source = 'function_edge_logs' and toInt32OrZero(toString(log_attributes['response.status_code'])) >= 500) as fn_5xx
      from logs`);
    const fives = await ask(`select timestamp, toString(log_attributes['response.status_code']) as status,
      substring(toString(log_attributes['request.url']), 1, 100) as url from logs
      where source in ('function_edge_logs', 'edge_logs') and toInt32OrZero(toString(log_attributes['response.status_code'])) >= 500
      order by timestamp desc limit 10`);
    const c = counts || {};
    const sum = ['pg_54000', 'pg_23505', 'edge_5xx', 'fn_5xx'].reduce((n, k) => n + Number(c[k] || 0), 0);
    return { flow: 5, ok: sum === 0, window: [fromIso, toIso], counts: c, five_xx: fives };
  } catch (e) {
    return { flow: 5, ok: false, err: String(e).slice(0, 200) };
  }
}

const results = { base: BASE, at: new Date().toISOString(), tier1: [], tier2: [] };
let bad = 0;
try {
  // ── TIER 1: public (anon) ────────────────────────────────────────────────
  if (TIER === 'all' || TIER === 'public') {
    // RECYCLE the context every RECYCLE_EVERY pages: one long-lived context accumulates memory and
    // Chrome dies mid-sweep on a small host (observed ~page 29 on an 8GB box — a healthy page then
    // read "browser has been closed"). A fresh context releases it so the full roster completes.
    const RECYCLE_EVERY = 20;
    let ctx = await quietContext(browser);
    const urls = await publicUrls(ctx);
    log(`\nTIER 1 — PUBLIC (anon) · ${urls.length} URL(s) from ${BASE}/sitemap.xml`);
    let i = 0;
    for (const u of urls) {
      if (i > 0 && i % RECYCLE_EVERY === 0) {
        try { await ctx.close(); } catch (_) {}
        ctx = await quietContext(browser);
      }
      i++;
      let r = await loadOne(ctx, u, SETTLE_PUBLIC, { authed: false });
      // a browser/context death is NOT a page defect — recycle and retry once before believing it
      if (!r.ok && /browser has been closed|Target page|context or browser/i.test((r.errors || []).join(' '))) {
        try { await ctx.close(); } catch (_) {}
        ctx = await quietContext(browser);
        r = await loadOne(ctx, u, SETTLE_PUBLIC, { authed: false });
      }
      results.tier1.push(r);
      if (!r.ok) bad++;
      log(`  ${r.ok ? 'ok  ' : 'FAIL'} ${String(r.status).padStart(3)} ${(u || '/').padEnd(42)}`
        + `${String(r.chars).padStart(6)}c ${String(r.controls).padStart(3)}ctl`
        + (r.thin ? ' · THIN' : '') + (r.errors.length ? ` · ${r.errors.length} err` : ''));
      for (const e of r.errors.slice(0, 2)) log(`        ${e}`);
    }
    await ctx.close();
  }
  // ── TIER 2: app (authed) ─────────────────────────────────────────────────
  if (TIER === 'all' || TIER === 'app') {
    if (!EMAIL || !PASS) {
      log('\nTIER 2 — APP (authed): SKIPPED — set WH_SMOKE_EMAIL + WH_SMOKE_PASS (prod test account).');
    } else {
      const ctx = await quietContext(browser);
      const signedIn = await signIn(ctx);
      if (!signedIn.ok) {
        log(`\nTIER 2 — APP (authed): SIGN-IN FAILED (${signedIn.err}) — the account/creds are wrong, `
          + `NOT a page defect. Fix creds and re-run.`);
        bad++;
      } else {
        log(`\nTIER 2 — APP (authed) · ${APP_PAGES.length} page(s) · signed in as ${signedIn.worker} (${signedIn.role}) in `
          + `${signedIn.hiveName || signedIn.hive}, as the server answered`);
        for (const name of APP_PAGES) {
          const r = await loadOne(ctx, `${name}.html`, SETTLE_APP, { authed: true });
          results.tier2.push(r);
          if (!r.ok) bad++;
          log(`  ${r.ok ? 'ok  ' : 'FAIL'} ${String(r.status).padStart(3)} ${(name + '.html').padEnd(30)}`
            + `${String(r.chars).padStart(6)}c ${String(r.controls).padStart(3)}ctl`
            + (r.signedOut ? ' · SIGNED-OUT(probe never got in — re-run)' : '')
            + (r.thin ? ' · THIN' : '') + (r.errors.length ? ` · ${r.errors.length} err` : ''));
          for (const e of r.errors.slice(0, 2)) log(`        ${e}`);
        }
      }
      await ctx.close();
    }
  }
  // ── TIER 3: Tier-0 flows (authed, bench hive only, undone) ───────────────
  if (TIER === 'all' || TIER === 'flows') {
    if (!EMAIL || !PASS || !BENCH_HIVE) {
      log('\nTIER 3 — FLOWS: SKIPPED — needs WH_SMOKE_EMAIL + WH_SMOKE_PASS + WH_SMOKE_HIVE (its writes land only in the bench).');
    } else {
      const t0 = new Date(Date.now() - 15 * 60e3).toISOString();
      const ctx = await quietContext(browser);
      const signedIn = await signIn(ctx);
      const flows = [{ flow: 1, ok: !!signedIn.ok, role: signedIn.role || null, worker: signedIn.worker || null,
        hive: signedIn.hive || null, err: signedIn.err || null }];
      if (signedIn.ok) {
        for (const vp of [{ name: 'phone-390', size: { width: 390, height: 844 } }, { name: 'desktop-1280', size: { width: 1280, height: 900 } }]) {
          flows.push(await flowLogbook(ctx, vp));
        }
        flows.push(...await flowServer(ctx, signedIn.hive));
      }
      await ctx.close();
      // logs reach the analytics store about a minute late: wait before reading the run's window
      await new Promise((r) => setTimeout(r, 75000));
      flows.push(await flowLogs(t0, new Date().toISOString()));
      const rep = { base: BASE, at: new Date().toISOString(), hive: signedIn.hive || null, flows,
        summary: { flows: flows.length, failed: flows.filter((f) => !f.ok).length } };
      writeFileSync('post_deploy_flows_report.json', JSON.stringify(rep, null, 2));
      log(`\nTIER 3 — FLOWS · in the bench hive, undone after`);
      for (const f of flows) {
        bad += f.ok ? 0 : 1;
        log(`  ${f.ok ? 'ok  ' : 'FAIL'} flow ${f.flow}${f.viewport ? ' ' + f.viewport : ''}`
          + (f.err ? ` · ${String(f.err).slice(0, 120)}` : '') + (f.skipped ? ` · ${f.skipped}` : '')
          + (f.counts ? ` · ${JSON.stringify(f.counts)}` : ''));
      }
    }
  }
} finally {
  await browser.close();
}

// sw.js version check (informational unless EXPECT_SW set)
if (EXPECT_SW) {
  const swSeen = [...results.tier1, ...results.tier2].map((r) => r.sw).filter(Boolean);
  const wrong = swSeen.filter((v) => v && !v.includes(EXPECT_SW));
  if (swSeen.length && wrong.length) {
    log(`\n⚠ sw.js: expected "${EXPECT_SW}" but saw ${[...new Set(wrong)].slice(0, 3).join(', ')} `
      + `— stale build may be cached. (informational)`);
  } else if (swSeen.length) {
    log(`\nsw.js: "${EXPECT_SW}" confirmed on ${swSeen.length} page(s).`);
  }
}

// the page report is written only by a run that walked pages: a flows-only run must not blank the last page report
if (TIER !== 'flows') {
  const total = results.tier1.length + results.tier2.length;
  const pageBad = [...results.tier1, ...results.tier2].filter((r) => !r.ok).length;
  results.summary = { total, failed: pageBad, passed: total - pageBad };
  writeFileSync('post_deploy_smoke_report.json', JSON.stringify(results, null, 2));
  log(`\n${pageBad ? 'FAIL' : 'PASS'} — ${total - pageBad}/${total} page(s) load clean across the roster `
    + `(report: post_deploy_smoke_report.json)`);
}
if (TIER === 'all' || TIER === 'flows') log(`(flows report: post_deploy_flows_report.json)`);
process.exit(bad ? 1 : 0);
