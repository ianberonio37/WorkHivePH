// page_battery.mjs — the reusable per-page mechanical battery (PER_PAGE_BUGHUNT_ROADMAP §5).
//
// WHY: the per-page bug-hunt scores 8 phases per page. Four of them are PAGE-AGNOSTIC and
// mechanically sweepable across every page in ONE headless run — this harness owns those:
//   P1 Smoke      — page loads signed-in, renders real content, 0 console ERRORS on load
//   P2 Con/Net    — every console msg + every network response captured; flag warns + non-2xx/3xx
//   P4 Inputs*    — SAFE reflected-XSS + input-handler-crash probe (fills payloads, does NOT
//                   click arbitrary submits — submit-path P4 stays MCP-interactive per roadmap)
//   P8 Visual     — horizontal-overflow @390 + @1280 (the "0 overflow" invariant) + screenshot
// P3/P5/P6/P7 stay MCP-interactive (judgment per entity) — this harness does NOT touch them.
//
// REUSE (WAT How-to-Operate #1 — don't reinvent): imports signIn + makeHelpers + ACCOUNTS +
// SEEDER from live_page_journeys.mjs (ONE sign-in recipe, no drift). Uses its OWN in-process
// Playwright (chromium) so it does NOT contend with the Playwright MCP browser the main loop
// drives for the interactive phases.
//
// SAFETY: P4 is NON-DESTRUCTIVE — it types payloads into visible inputs and observes reflection
// + console, but never clicks submit/delete (avoids polluting the shared local DB —
// feedback_live_mcp_writes_pollute_test_db). Reflected-XSS while typing (live search/preview)
// and input-handler exceptions are caught without any write.
//
// USAGE:
//   WH_TEST_HIVE=636cf7e8-431a-4907-8a9f-43dd4cc216d6 node tools/page_battery.mjs
//   node tools/page_battery.mjs --page hive.html            # one page
//   node tools/page_battery.mjs --headed
// Emits page_battery_results.json (per-page P1/P2/P4/P8 signals + candidate findings).

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, makeHelpers, ACCOUNTS, SEEDER } from './live_page_journeys.mjs';

const args = process.argv.slice(2);
const HEADED = args.includes('--headed');
const GATE = args.includes('--gate'); // exit 1 if any sev>=3 regression (broken load / 5xx / XSS / mobile overflow)
const PAGE_ONLY = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
// Persona: which role signs in. Role-specific bugs (a page that throws for a worker but not a
// supervisor) are invisible to a single-identity sweep — run both. Default supervisor (widest access).
const ROLE = (() => { const i = args.indexOf('--role'); return i >= 0 ? args[i + 1] : 'supervisor'; })();
const RESULTS = ROLE === 'supervisor' ? 'page_battery_results.json' : `page_battery_results_${ROLE}.json`;

// Canonical interactive page list (the roadmap §3 scoreboard, predictive RETIRED).
const PAGES = [
  'index.html', 'hive.html', 'logbook.html', 'inventory.html', 'pm-scheduler.html',
  'asset-hub.html', 'alert-hub.html', 'analytics.html', 'analytics-report.html',
  'achievements.html', 'ai-quality.html', 'skillmatrix.html', 'resume.html',
  'community.html', 'public-feed.html', 'marketplace.html', 'marketplace-seller.html',
  'dayplanner.html', 'engineering-design.html', 'assistant.html', 'report-sender.html',
  'project-manager.html', 'project-report.html', 'integrations.html', 'ph-intelligence.html',
  'plant-connections.html', 'shift-brain.html', 'audit-log.html', 'voice-journal.html',
  'founder-console.html',
  // v3 L1/L2 residual (registered 2026-07-20, per-page bughunt §7.9): real app pages whose
  // BACKEND columns are already covered by the platform-wide gates, added here for render coverage.
  'marketplace-seller-profile.html', 'marketplace-admin.html', 'platform-actions.html',
  // user-reachable UI-only pages (2026-07-20 §7.12 anti-drift): PWA offline page + status page.
  'offline-fallback.html', 'status.html',
];

// Known-benign console noise (do NOT count these as P1/P2 defects) — favicon 404s, third-party
// analytics that are intentionally absent locally, Chrome DevTools autofill notices.
const BENIGN_CONSOLE = [
  /favicon\.ico/i, /Download the React DevTools/i, /\[HMR\]/i,
  /net::ERR_INTERNET_DISCONNECTED/i, // only appears in the P4 offline sub-probe if any
];
// Network requests we EXPECT can be non-2xx and are not defects: HEAD existence probes,
// auth token refresh 400 on anon, favicon.
const BENIGN_NET = [/favicon\.ico/i];

// XSS payload that sets a global flag IF it executes (containment check — flag must stay unset).
const XSS = `"><img src=x onerror="window.__wh_xss_fired=1">`;
const OVERSIZE = 'A'.repeat(5000);
const UNICODE = '🔧你好​مرحبا😀ñ'; // emoji + zero-width + RTL + surrogate + accent

function isBenign(list, s) { return list.some(re => re.test(s || '')); }

async function runPage(context, pageFile) {
  const rec = {
    page: pageFile, ok: false,
    P1: { score: 0, notes: [] }, P2: { score: 0, consoleErrors: [], consoleWarns: [], badNet: [] },
    P4: { score: 0, xssReflected: false, xssExecuted: false, inputsFuzzed: 0, handlerErrors: [] },
    P8: { score: 0, overflow390: null, overflow1280: null, scrollW390: null },
    P9: { score: 0, imgsNoAlt: 0, namedlessControls: 0 },
    P12: { score: 0, unhandledRejections: 0, leakedStack: false },
    findings: [],
  };
  const page = await context.newPage();
  // P12 (error-handling, 2026-07-19): capture UNHANDLED promise rejections on load — a page that leaves a
  // promise rejection unhandled has an error path that fails OPEN (no catch), the exact P12 defect class.
  // Injected before any page script runs so it sees rejections from the earliest async work.
  await page.addInitScript(() => {
    window.__whUnhandled = 0;
    window.addEventListener('unhandledrejection', () => { window.__whUnhandled++; });
  });
  const consoleMsgs = [];
  const netResp = [];
  page.on('console', m => { const t = m.type(); if (t === 'error' || t === 'warning') consoleMsgs.push({ t, text: (m.text() || '').slice(0, 300) }); });
  page.on('response', r => { const s = r.status(); if (s >= 400) netResp.push({ url: r.url(), status: s, method: r.request().method() }); });
  page.on('pageerror', e => consoleMsgs.push({ t: 'error', text: 'PAGEERROR ' + String(e).slice(0, 300) }));

  try {
    // ── P1 Smoke ──
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto(`${SEEDER}/workhive/${pageFile}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000); // settle async render
    const body = await page.evaluate(() => {
      const txt = (document.body?.innerText || '');
      // Precise error-state phrases only (bare "500"/"internal server" over-match legit copy
      // like "500 hrs" / "500 members" — dropped to kill false positives).
      const ERR_RE = /(something went wrong|failed to load|error loading|could not load|unable to load|500 internal server error|unexpected error occurred|an error occurred)/i;
      const m = txt.slice(0, 6000).match(ERR_RE);
      return { len: txt.trim().length, hasErrBanner: !!m, errSnippet: m ? txt.slice(Math.max(0, m.index - 30), m.index + 80) : null, title: document.title };
    }).catch(() => ({ len: 0, hasErrBanner: false, errSnippet: null, title: '' }));
    const loadErrors = consoleMsgs.filter(m => m.t === 'error' && !isBenign(BENIGN_CONSOLE, m.text));
    rec.P1.notes.push(`bodyLen=${body.len} title="${body.title}" loadErrors=${loadErrors.length}`);
    if (body.len > 200 && !body.hasErrBanner && loadErrors.length === 0) rec.P1.score = 100;
    else if (body.len > 200 && loadErrors.length === 0) rec.P1.score = 75;
    else if (body.len > 200) rec.P1.score = 50;
    else rec.P1.score = 25;
    if (body.hasErrBanner) rec.findings.push({ phase: 'P1', sev: 3, detail: `error banner text in body: "${(body.errSnippet || '').replace(/\s+/g, ' ').trim()}"` });
    if (body.len <= 200) rec.findings.push({ phase: 'P1', sev: 3, detail: `near-blank body (len=${body.len})` });
    for (const e of loadErrors) rec.findings.push({ phase: 'P1', sev: 3, detail: `console error on load: ${e.text}` });

    // ── P2 Console + Network (post-load capture) ──
    const warns = consoleMsgs.filter(m => m.t === 'warning' && !isBenign(BENIGN_CONSOLE, m.text));
    const errs = consoleMsgs.filter(m => m.t === 'error' && !isBenign(BENIGN_CONSOLE, m.text));
    const badNet = netResp.filter(n => !isBenign(BENIGN_NET, n.url));
    rec.P2.consoleErrors = errs.slice(0, 12); rec.P2.consoleWarns = warns.slice(0, 12); rec.P2.badNet = badNet.slice(0, 20);
    if (errs.length === 0 && badNet.length === 0 && warns.length === 0) rec.P2.score = 100;
    else if (errs.length === 0 && badNet.length === 0) rec.P2.score = 75; // warns only
    else if (errs.length === 0) rec.P2.score = 50; // bad net but no JS errors
    else rec.P2.score = 25;
    for (const n of badNet) rec.findings.push({ phase: 'P2', sev: n.status >= 500 ? 3 : 2, detail: `${n.method} ${n.status} ${n.url.slice(0, 120)}` });

    // ── P4 SAFE input probe (reflected-XSS + handler-crash; NO submit) ──
    const errsBefore = consoleMsgs.length;
    await page.evaluate(() => { window.__wh_xss_fired = 0; });
    const inputs = await page.$$('input:not([type=hidden]):not([type=file]):not([type=checkbox]):not([type=radio]), textarea, [contenteditable="true"]');
    let fuzzed = 0, reflected = false;
    for (const inp of inputs.slice(0, 12)) { // cap to keep it fast
      try {
        const vis = await inp.isVisible().catch(() => false);
        if (!vis) continue;
        const editable = await inp.isEditable().catch(() => false);
        if (!editable) continue;
        await inp.fill(XSS, { timeout: 2500 }).catch(() => {});
        await page.waitForTimeout(120);
        await inp.fill(OVERSIZE.slice(0, 2000), { timeout: 2500 }).catch(() => {});
        await inp.fill(UNICODE, { timeout: 2500 }).catch(() => {});
        fuzzed++;
      } catch (e) { /* per-input best-effort */ }
    }
    await page.waitForTimeout(400);
    const xssExecuted = await page.evaluate(() => !!window.__wh_xss_fired).catch(() => false);
    // reflected (unescaped) check: does the literal <img src=x onerror payload appear as a REAL element?
    reflected = await page.evaluate(() => !!document.querySelector('img[src="x"][onerror]')).catch(() => false);
    const handlerErrs = consoleMsgs.slice(errsBefore).filter(m => m.t === 'error' && !isBenign(BENIGN_CONSOLE, m.text));
    rec.P4.inputsFuzzed = fuzzed; rec.P4.xssExecuted = xssExecuted; rec.P4.xssReflected = reflected;
    rec.P4.handlerErrors = handlerErrs.slice(0, 8).map(e => e.text);
    if (fuzzed === 0) rec.P4.score = 10; // no inputs found to probe (page may be read-only)
    else if (!xssExecuted && !reflected && handlerErrs.length === 0) rec.P4.score = 60; // safe probe clean (submit-path still MCP)
    else rec.P4.score = 25;
    if (xssExecuted) rec.findings.push({ phase: 'P4', sev: 4, detail: 'XSS onerror EXECUTED via typed input (reflected-DOM)' });
    if (reflected) rec.findings.push({ phase: 'P4', sev: 4, detail: 'XSS payload reflected as live <img onerror> node' });
    for (const e of handlerErrs) rec.findings.push({ phase: 'P4', sev: 2, detail: `input-handler error: ${e.text}` });

    // ── P8 horizontal overflow @390 + @1280 ──
    async function overflow(w) {
      await page.setViewportSize({ width: w, height: 800 });
      await page.waitForTimeout(500);
      return page.evaluate(() => {
        const de = document.documentElement;
        const over = de.scrollWidth - de.clientWidth;
        let worst = null;
        if (over > 1) {
          for (const el of document.querySelectorAll('*')) {
            const r = el.getBoundingClientRect();
            if (r.right > window.innerWidth + 2 && r.width > 40) { worst = (el.tagName + '.' + (el.className || '').toString().slice(0, 40)); break; }
          }
        }
        return { scrollW: de.scrollWidth, clientW: de.clientWidth, over, worst };
      });
    }
    const o390 = await overflow(390);
    const o1280 = await overflow(1280);
    rec.P8.overflow390 = o390.over > 1 ? o390 : 0; rec.P8.scrollW390 = o390.scrollW;
    rec.P8.overflow1280 = o1280.over > 1 ? o1280 : 0;
    if (o390.over <= 1 && o1280.over <= 1) rec.P8.score = 75; // clean overflow, ungated here => cap 75
    else rec.P8.score = 25;
    // @390 mobile overflow is a hard invariant (currently 0 platform-wide) => sev 3 (gate-failing);
    // @1280 desktop overflow is sev 2 (report, don't hard-fail — desktop is less brittle).
    if (o390.over > 1) rec.findings.push({ phase: 'P8', sev: 3, detail: `overflow @390: scrollW=${o390.scrollW} over=${o390.over}px worst=${o390.worst}` });
    if (o1280.over > 1) rec.findings.push({ phase: 'P8', sev: 2, detail: `overflow @1280: scrollW=${o1280.scrollW} over=${o1280.over}px worst=${o1280.worst}` });

    // ── P12 error-handling: unhandled-rejection-free on load ──
    const unhandled = await page.evaluate(() => window.__whUnhandled || 0).catch(() => 0);
    rec.P12.unhandledRejections = unhandled;
    rec.P12.score = unhandled === 0 ? 100 : 50;
    // sev 3 (GATE-FAILING): all 30 pages verified 0 unhandled rejections on load (2026-07-19 battery run),
    // so this is now a locked invariant — a NEW unhandled promise rejection (an error path that fails open)
    // FAILs the gate, exactly like a broken load / 5xx / XSS / @390 overflow.
    if (unhandled > 0) rec.findings.push({ phase: 'P12', sev: 3, detail: `${unhandled} unhandled promise rejection(s) on load (error path fails open — add a .catch)` });

    // ── P9 accessibility (lightweight): the 2 highest-frequency SERIOUS axe failures without the CDN —
    //    (a) a VISIBLE <img> with no alt attribute (missing text alternative), (b) a VISIBLE actionable
    //    control (<button>/<a href>/[role=button]) with NO accessible name (no text, aria-label,
    //    aria-labelledby, or title). Icon-only buttons are the usual offender. Full axe serious/critical
    //    stays MCP-interactive; this catches regressions of the two commonest violations mechanically.
    const a11y = await page.evaluate(() => {
      const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
      const imgsNoAlt = [...document.querySelectorAll('img:not([alt]):not([role="presentation"]):not([aria-hidden="true"])')].filter(vis).length;
      const ctrls = [...document.querySelectorAll('button, a[href], [role="button"]')].filter(vis);
      const namedless = ctrls.filter(el => {
        const name = (el.textContent || '').trim() || el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.getAttribute('title')
          || (el.querySelector('img[alt]') && el.querySelector('img[alt]').getAttribute('alt')) || '';
        return !String(name).trim();
      }).length;
      return { imgsNoAlt, namedless };
    }).catch(() => ({ imgsNoAlt: 0, namedless: 0 }));
    rec.P9 = { score: (a11y.imgsNoAlt === 0 && a11y.namedless === 0) ? 90 : 50, imgsNoAlt: a11y.imgsNoAlt, namedlessControls: a11y.namedless };
    // sev 3 (GATE-FAILING): all 30 pages verified 0 img-no-alt AND 0 namedless-control (2026-07-19 battery
    // run), so these two highest-frequency SERIOUS axe failures are now locked — a NEW one FAILs the gate.
    if (a11y.imgsNoAlt > 0) rec.findings.push({ phase: 'P9', sev: 3, detail: `${a11y.imgsNoAlt} visible <img> with no alt (missing text alternative)` });
    if (a11y.namedless > 0) rec.findings.push({ phase: 'P9', sev: 3, detail: `${a11y.namedless} visible control(s) with NO accessible name (icon-only button/link)` });

    rec.ok = true;
  } catch (e) {
    rec.err = String(e).slice(0, 240);
    rec.findings.push({ phase: 'P1', sev: 3, detail: `page threw: ${rec.err}` });
  } finally {
    await page.close().catch(() => {});
  }
  return rec;
}

(async () => {
  const pages = PAGE_ONLY ? [PAGE_ONLY] : PAGES;
  const browser = await chromium.launch({ headless: !HEADED });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: 'Asia/Manila' });
  const si = await signIn(ctx, ROLE);
  console.log(`[BATTERY] sign-in ${ROLE} (${ACCOUNTS[ROLE]?.email || '?'}): ${si.ok ? 'OK' : 'FAIL ' + si.err}`);
  if (!si.ok) { console.error('sign-in failed, aborting'); process.exit(2); }

  const out = { ran: new Date().toISOString(), role: ROLE, seeder: SEEDER, hive: process.env.WH_TEST_HIVE || '(default)', pages: [] };
  for (const p of pages) {
    const rec = await runPage(ctx, p);
    out.pages.push(rec);
    const f = rec.findings.length;
    console.log(`  ${p.padEnd(26)} P1=${rec.P1.score} P2=${rec.P2.score} P4=${rec.P4.score} P8=${rec.P8.score} P9=${rec.P9.score} P12=${rec.P12.score}  findings=${f}${rec.err ? '  ERR ' + rec.err : ''}`);
    for (const fd of rec.findings.filter(x => x.sev >= 3)) console.log(`      [S${fd.sev}|${fd.phase}] ${fd.detail}`);
  }
  await ctx.close(); await browser.close();

  // rollups
  const avg = k => Math.round(out.pages.reduce((s, p) => s + (p[k]?.score || 0), 0) / out.pages.length);
  out.summary = { pages: out.pages.length, P1: avg('P1'), P2: avg('P2'), P4: avg('P4'), P8: avg('P8'), P9: avg('P9'), P12: avg('P12'), total_findings: out.pages.reduce((s, p) => s + p.findings.length, 0), high_sev: out.pages.reduce((s, p) => s + p.findings.filter(f => f.sev >= 3).length, 0), unhandled_pages: out.pages.filter(p => p.P12.unhandledRejections > 0).map(p => p.page), a11y_pages: out.pages.filter(p => (p.P9.imgsNoAlt + p.P9.namedlessControls) > 0).map(p => `${p.page}(alt:${p.P9.imgsNoAlt},noname:${p.P9.namedlessControls})`) };
  writeFileSync(RESULTS, JSON.stringify(out, null, 2));
  console.log('\n' + '='.repeat(64));
  console.log(`PAGE BATTERY — P1=${out.summary.P1} P2=${out.summary.P2} P4=${out.summary.P4} P8=${out.summary.P8} P9=${out.summary.P9} P12=${out.summary.P12} (mean across ${out.summary.pages} pages)`);
  if (out.summary.unhandled_pages.length) console.log(`  ⚠ P12 unhandled rejections on: ${out.summary.unhandled_pages.join(', ')}`);
  if (out.summary.a11y_pages.length) console.log(`  ⚠ P9 a11y gaps on: ${out.summary.a11y_pages.join(', ')}`);
  console.log(`findings=${out.summary.total_findings} (high-sev=${out.summary.high_sev})  -> ${RESULTS}`);

  // ── gate mode: fail on any sev>=3 regression (broken load / 5xx / executed-or-reflected XSS / mobile overflow) ──
  if (GATE) {
    const hard = [];
    for (const p of out.pages) for (const f of p.findings) if (f.sev >= 3) hard.push(`${p.page} [S${f.sev}|${f.phase}] ${f.detail}`);
    if (hard.length) {
      console.log(`\n[GATE] FAIL — ${hard.length} sev>=3 regression(s):`);
      for (const h of hard) console.log(`  ${h}`);
      process.exit(1);
    }
    console.log(`\n[GATE] PASS — all ${out.pages.length} pages: clean load (P1), no 5xx (P2), no executed/reflected XSS (P4), no @390 overflow (P8), 0 img-no-alt/namedless-control (P9), 0 unhandled rejections (P12).`);
  }
})();
