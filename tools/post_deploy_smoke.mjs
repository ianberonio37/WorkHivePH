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
 *   TIER 2 — APP (authed): sign in once with a prod test account, seed hive + role, and load EVERY
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
 *   WH_SMOKE_EMAIL=<prod test account> WH_SMOKE_PASS=<pw> \
 *   EXPECT_SW=<new sw.js version, e.g. v282> \
 *   node tools/post_deploy_smoke.mjs
 *
 *   # local rehearsal (verify the smoke itself works before trusting it on prod):
 *   WH_SMOKE_BASE=http://127.0.0.1:5000 \
 *   WH_SMOKE_EMAIL=leandromarquez@auth.workhiveph.com WH_SMOKE_PASS=test1234 \
 *   node tools/post_deploy_smoke.mjs
 *
 *   # scope to one tier while triaging: --tier=public | --tier=app
 *   # sample learn articles instead of all (faster): --learn-sample=8
 *
 * Exit 0 = every page in scope loaded clean; exit 1 = at least one FAIL (report names which).
 * Writes post_deploy_smoke_report.json for the runbook record + rollback evidence.
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';

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

const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const WORKER = 'Leandro Marquez';

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
const results = { base: BASE, at: new Date().toISOString(), tier1: [], tier2: [] };
let bad = 0;
try {
  // ── TIER 1: public (anon) ────────────────────────────────────────────────
  if (TIER === 'all' || TIER === 'public') {
    // RECYCLE the context every RECYCLE_EVERY pages: one long-lived context accumulates memory and
    // Chrome dies mid-sweep on a small host (observed ~page 29 on an 8GB box — a healthy page then
    // read "browser has been closed"). A fresh context releases it so the full roster completes.
    const RECYCLE_EVERY = 20;
    let ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const urls = await publicUrls(ctx);
    log(`\nTIER 1 — PUBLIC (anon) · ${urls.length} URL(s) from ${BASE}/sitemap.xml`);
    let i = 0;
    for (const u of urls) {
      if (i > 0 && i % RECYCLE_EVERY === 0) {
        try { await ctx.close(); } catch (_) {}
        ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      }
      i++;
      let r = await loadOne(ctx, u, SETTLE_PUBLIC, { authed: false });
      // a browser/context death is NOT a page defect — recycle and retry once before believing it
      if (!r.ok && /browser has been closed|Target page|context or browser/i.test((r.errors || []).join(' '))) {
        try { await ctx.close(); } catch (_) {}
        ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
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
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      const boot = await ctx.newPage();
      await boot.goto(`${BASE}/shift-brain.html`, { waitUntil: 'domcontentloaded', timeout: 40000 });
      await boot.waitForFunction(() => !!(window.supabase && window.supabase.createClient), { timeout: 25000 });
      const signedIn = await boot.evaluate(async ({ email, password, hive, worker }) => {
        const db = (typeof getDb === 'function') ? getDb() : window.db;
        const { error } = await db.auth.signInWithPassword({ email, password });
        if (error) return { ok: false, err: error.message };
        localStorage.setItem('wh_active_hive_id', hive.id);
        localStorage.setItem('wh_active_hive_name', hive.name);
        localStorage.setItem('WORKER_NAME', worker);
        localStorage.setItem('wh_hive_role', 'supervisor');
        return { ok: true };
      }, { email: EMAIL, password: PASS, hive: HIVE, worker: WORKER }).catch((e) => ({ ok: false, err: String(e) }));
      await boot.close();
      if (!signedIn.ok) {
        log(`\nTIER 2 — APP (authed): SIGN-IN FAILED (${signedIn.err}) — the account/creds are wrong, `
          + `NOT a page defect. Fix creds and re-run.`);
        bad++;
      } else {
        log(`\nTIER 2 — APP (authed) · ${APP_PAGES.length} page(s) · signed in as ${WORKER}`);
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

const total = results.tier1.length + results.tier2.length;
results.summary = { total, failed: bad, passed: total - bad };
writeFileSync('post_deploy_smoke_report.json', JSON.stringify(results, null, 2));
log(`\n${bad ? 'FAIL' : 'PASS'} — ${total - bad}/${total} page(s) load clean across the roster `
  + `(report: post_deploy_smoke_report.json)`);
process.exit(bad ? 1 : 0);
