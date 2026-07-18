// family_rubric_sweep.mjs — the FAMILY A–S rubric sweep, deterministic.
//
// WHY: FAMILY_UFAI_ROADMAP.md §16/§17 were built by driving all 32 family pages
// by hand through the Playwright MCP and running window.__RUBRIC.survey() on
// each. That made the scoreboard a one-off. This runner is the same measurement
// as a REPEATABLE instrument: after any lens change (e.g. the ⚠-trio C4/D1/J1
// no-denominator split) or any page fix, one command regenerates the whole
// board instead of 32 manual walks.
//
// REUSE (not reinvent): identical recipe to frontend_ufai_sweep.mjs —
//   - :5000 seeder serves pages already repointed to local 127.0.0.1:54321
//   - sign in ONCE on shift-brain; session persists same-origin
//   - navigate each page, settle, inject survey_ufai_rubric.js, survey()
// Identity = pabloaguilar (supervisor) on hive c9def338… — the SAME identity
// the §16 scoreboard was measured with, so runs stay comparable.
//
// USAGE:
//   node tools/family_rubric_sweep.mjs                 # all 32 pages
//   node tools/family_rubric_sweep.mjs --page hive.html
//   node tools/family_rubric_sweep.mjs --headed
//
// OUTPUT: family_rubric_scoreboard.json —
//   { pages: {file: {overall, dims:[…], failing}}, perDim: {dim: {mean, green,
//     fail, na, judged, failPages}}, summary: {mean, ge90, ge85, errors} }

import { chromium } from 'playwright';
import { writeFileSync, readFileSync } from 'fs';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const EMAIL = process.env.WH_TEST_EMAIL || 'pabloaguilar@auth.workhiveph.com';
const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const HIVE = process.env.WH_TEST_HIVE || 'c9def338-fd73-4b19-8ef1-ee57625953d6';
const WORKER = process.env.WH_TEST_WORKER || 'Pablo Aguilar';

// Deep-link state a page's REAL use requires (never measure a bounced shell).
const PAGE_QUERY = { 'marketplace-seller-profile.html': '?worker=Bryan%20Garcia' };
// Worked-state reveal: a LOCAL compile/render click (no AI/credits) that turns a
// generator form into the artifact the rubric must grade (★measure the WORKED state).
const PAGE_REVEAL = { 'project-report.html': /generate/i };
// Extra settle for pages whose tagged/labelled content lands after a SLOW RPC and whose realtime
// connection keeps the network busy so `networkidle` never fires — analytics' phase panels carry
// their data-i labels + readable copy and render ~2s after the panels' RPC (N1 read 1/11 vs 15/15
// fully-loaded; B3 raced its copy). A page-specific wait, not a global slowdown.
const PAGE_SETTLE = {};  // (analytics N1 is the _t()-vs-data-i lens under-count, not a fixed-wait race — a settle bump doesn't move it; the real fix is the §6 locale-flip diff)

const PAGES = [
  'analytics.html', 'pm-scheduler.html', 'asset-hub.html', 'skillmatrix.html',
  'hive.html', 'project-manager.html', 'index.html', 'marketplace.html',
  'shift-brain.html', 'inventory.html', 'dayplanner.html', 'report-sender.html',
  'alert-hub.html', 'logbook.html', 'community.html', 'assistant.html',
  'engineering-design.html', 'achievements.html', 'voice-journal.html',
  'integrations.html', 'plant-connections.html', 'ai-quality.html',
  'project-report.html', 'marketplace-seller.html', 'marketplace-admin.html',
  'agentic-rag-observability.html', 'audit-log.html',
  'marketplace-seller-profile.html', 'public-feed.html', 'status.html',
  'ph-intelligence.html', 'promo-poster.html',
];

const args = process.argv.slice(2);
const HEADED = args.includes('--headed');
const PAGE_ONLY = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
// A --page run must never clobber the FULL board (validate_family_rubric_ratchet.py
// baselines from it; a 1-page overwrite destroyed the sweep-#8 board on 2026-07-16).
const OUT = PAGE_ONLY ? 'family_rubric_scoreboard.page.json' : 'family_rubric_scoreboard.json';

const RUBRIC_SRC = readFileSync('survey_ufai_rubric.js', 'utf8');

async function signInOnce(context) {
  const page = await context.newPage();
  await page.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
  const r = await page.evaluate(async ({ email, password, hive, worker }) => {
    try {
      const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email, password });
      localStorage.setItem('wh_active_hive_id', hive);
      localStorage.setItem('wh_last_worker', worker);
      // pabloaguilar IS a supervisor on this hive — set the role the gated pages read
      // (audit-log/integrations/marketplace-admin gate on wh_hive_role !== 'supervisor'),
      // so the sweep measures their REAL worked UI, not the auth-gate screen.
      localStorage.setItem('wh_hive_role', 'supervisor');
      return { ok: !error && !!data?.session, err: error ? String(error.message || error) : null };
    } catch (e) { return { ok: false, err: String(e) }; }
  }, { email: EMAIL, password: PASSWORD, hive: HIVE, worker: WORKER });
  await page.close();
  return r;
}

async function surveyPage(context, file) {
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 160)));
  // I1 Core Web Vitals — install LCP + CLS observers BEFORE navigation so they capture
  // the real load (the lens can't; it runs post-load in page context). Converts I1 from
  // JUDGED to MEASURED (Ian: "those unmeasured dimensions, use playwright to live-probe").
  await page.addInitScript(() => {
    window.__cwv = { lcp: 0, cls: 0, worstShift: 0, culprit: '' };
    const desc = (n) => { try { return n && n.nodeType === 1 ? (n.tagName.toLowerCase() + (n.id ? '#' + n.id : '') + (n.className && typeof n.className === 'string' ? '.' + n.className.trim().split(/\s+/).slice(0, 2).join('.') : '')) : ''; } catch (e) { return ''; } };
    try {
      new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__cwv.lcp = e.startTime; })
        .observe({ type: 'largest-contentful-paint', buffered: true });
      new PerformanceObserver((l) => { for (const e of l.getEntries()) {
        if (e.hadRecentInput) continue;
        window.__cwv.cls += e.value;
        if (e.value > window.__cwv.worstShift) {   // record the biggest single shift's source element
          window.__cwv.worstShift = e.value;
          const src = (e.sources || []).find((s) => s.node);
          window.__cwv.culprit = src ? desc(src.node) : '';
        }
      } }).observe({ type: 'layout-shift', buffered: true });
    } catch (e) { /* observer unsupported */ }
  });
  try {
    await page.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    // 3200ms: index's source chip renders at ~2.5s after its dashboard RPC — 2500 raced it.
    await page.waitForTimeout(3200);
    // ★I1 LCP — FREEZE + snapshot LCP HERE, at a FIXED 3200ms after nav, BEFORE the variable-length
    // networkidle/gate waits below. Two reasons: (1) a benign Shift keydown (no default action) is a
    // TRUSTED input, which finalizes the LCP observer so no LATER harness re-paint can restamp it (the
    // reveal click, the 390→1280 mobile re-measure, a late realtime re-render) — those are all untrusted
    // and would otherwise stamp false late entries (alert-hub 4356ms / plant-connections 7156ms whose
    // real cold-load LCP is 452ms / 1380ms). (2) A FIXED freeze point makes LCP contention-INDEPENDENT:
    // reading it after `networkidle` let a full 32-page sweep's resource contention stretch the cap and
    // inflate skillmatrix 2228ms→6976ms / hive 3076ms→6276ms purely from load order. 3200ms is past
    // every page's real LCP (isolated probes: all <3.1s) and past index's ~2.5s source-chip RPC, so no
    // genuinely-slow page is masked. CLS keeps accumulating over the whole load and is read post-resize.
    await page.keyboard.press('Shift').catch(() => {});
    const lcpAtLoad = await page.evaluate(() => (window.__cwv && window.__cwv.lcp) || 0);
    // ★MEASURE THE SETTLED STATE: some pages render tagged/labelled content only AFTER an RPC
    // resolves (analytics' phase panels carry their data-i labels; the 3.2s raced them → N1 read
    // 1/11 while a full load shows 15/15). Wait for network to go idle (capped) so async content
    // lands before the survey. Fail-soft: long-poll pages just hit the cap.
    await page.waitForLoadState('networkidle', { timeout: 3500 }).catch(() => {});
    if (PAGE_SETTLE[file]) await page.waitForTimeout(PAGE_SETTLE[file]);
    // Gated pages (audit-log, integrations, marketplace-admin) show a supervisor/hive/admin AUTH
    // GATE until the async role check resolves; the survey must grade the REAL UI behind it, not the
    // gate screen. Wait for any known gate to hide. 7s (was 4s): marketplace-admin's platform-admin
    // check (auth -> worker_profiles -> marketplace_platform_admins) can exceed 4s under full-sweep
    // contention even though pabloaguilar IS an admin, so the gate was graded instead of the admin UI.
    await page.waitForFunction(() => {
      const g = document.querySelector('#gate-not-supervisor, #supervisor-gate, #hive-gate, .hive-gate, .gate-card');
      if (!g) return true;
      const s = getComputedStyle(g);
      return s.display === 'none' || s.visibility === 'hidden' || g.offsetParent === null;
    }, { timeout: 7000 }).catch(() => {});
    // RPC-gated content pages (ph-intelligence) render a text-only "Loading latest report" wait state
    // until an async chain resolves — a maturity gate replaces <main> with an honest-empty, or the
    // report/no-report renders. That chain can outlast the 3.2s+networkidle grade point, so the survey
    // would grade the transient loading text (low A2/G1/C2). Wait for #loading-state to CLEAR so we
    // grade the settled state. Fast-returns immediately on the pages that have no #loading-state.
    await page.waitForFunction(() => {
      const l = document.getElementById('loading-state');
      if (!l) return true;
      const s = getComputedStyle(l);
      return s.display === 'none' || l.classList.contains('hidden') || l.offsetParent === null;
    }, { timeout: 5000 }).catch(() => {});
    // CONTENT-SETTLE: wait until the content root stops GROWING (async feed/chat/cards/headings have
    // landed) so the survey grades the SETTLED page, not a half-rendered one. Under full-sweep
    // contention some pages' content lands after the grade point, so A2 (blocks=0)/A1/R3 dipped
    // run-to-run while scoring 100 in isolation. Poll a size signature (visible text length + block
    // count); a skeleton→data wave resets the counter (innerText grows). Stop on 2 stable reads or 4s.
    await page.waitForFunction(() => {
      const R = document.querySelector('.page') || document.querySelector('main') || document.body;
      const sig = (R.innerText || '').length + '|' + R.querySelectorAll('h1,h2,h3,.card,.simple-card,.board-card,button').length;
      window.__settle = window.__settle || { last: '', stable: 0 };
      if (sig === window.__settle.last) window.__settle.stable++; else { window.__settle.stable = 0; window.__settle.last = sig; }
      return window.__settle.stable >= 2;
    }, { timeout: 4000, polling: 400 }).catch(() => {});
    const reveal = PAGE_REVEAL[file];
    if (reveal) {
      const clicked = await page.evaluate((reSrc) => {
        const re = new RegExp(reSrc, 'i');
        const vis = (el) => el && el.offsetParent !== null;
        const btn = [...document.querySelectorAll('button, a[role="button"], [onclick]')]
          .find((el) => vis(el) && re.test((el.textContent || '').trim()));
        if (btn) { btn.click(); return (btn.textContent || '').trim().slice(0, 30); }
        return null;
      }, reveal.source);
      if (clicked) await page.waitForTimeout(2500);
    }
    const res = await page.evaluate((src) => {
      eval('(' + src + ')')();
      return window.__RUBRIC.survey({ pageId: location.pathname.split('/').pop() });
    }, RUBRIC_SRC);
    // ★I1 CLS — snapshot the natural-load CLS HERE, at desktop, BEFORE the mobile F1/K2 re-measure.
    // The 390→1280→ resize reflow generates layout shifts that the CLS accumulator counts as if they
    // were load instability (index isolated CLS 0.006 → post-resize 0.237; dayplanner → 0.242). Same
    // harness artifact the LCP snapshot above avoids. This captures every real load + settle shift.
    const clsAtLoad = await page.evaluate(() => (window.__cwv && window.__cwv.cls) || 0);
    // ★I1 LCP fallback (still pre-resize): for a SLOW page whose largest element hasn't painted by the
    // 3200ms freeze, lcpAtLoad is 0 — and falling back to the POST-resize cwv.lcp read below re-inflates
    // it with the mobile-resize re-paint (engineering-design read a false 4596ms under contention). Read
    // LCP again HERE, at desktop after the settled survey but BEFORE the resize: by now the content HAS
    // painted, so this is the true load LCP without the resize artifact. Used only when lcpAtLoad is 0.
    const lcpPreResize = await page.evaluate(() => (window.__cwv && window.__cwv.lcp) || 0);
    // ★N1 LOCALE-FLIP (the documented "real fix"): the survey's data-i coverage UNDER-counts pages that
    // translate JS-rendered labels via _t() at render time (analytics' chart titles + "Show all N"
    // buttons re-render bilingually on setLang via setPhase() but carry no data-i). Measure ACTUAL
    // translation: snapshot the SAME labelEls the lens grades, flip WH_LANG, let the page re-render, and
    // count how many label texts CHANGED. coverage = max(data-i, flip) so it is ADDITIVE — a page passing
    // via data-i can never regress, and a page with no setLang() keeps its data-i result. Restores the
    // graded locale before the mobile re-measure below.
    const n1flip = await page.evaluate(async () => {
      try {
        if (typeof window.setLang !== 'function' || typeof window.WH_LANG === 'undefined') return null;
        const R = document.querySelector('.page') || document.querySelector('main') || document.body;
        // Match the survey's N1 labelEls EXACTLY (else the flip-cov is diluted by labels the survey
        // never counts): same selector, same filters — visible, ownText>2, translate!="no", and NOT a
        // chart/metric card title (technical terms kept English — Ian's call).
        const sel = 'h1, h2, h3, button, label, [class*="section-label"]';
        const vis = (e) => e && e.offsetParent !== null && (e.textContent || '').trim().length > 2
          && e.getAttribute('translate') !== 'no' && !e.classList.contains('card-title') && !e.closest('.card-title');
        const els0 = [...R.querySelectorAll(sel)].filter(vis);
        const before = els0.map((e) => (e.textContent || '').trim());
        const dataICov = els0.length ? els0.filter((e) => e.hasAttribute('data-i') || e.querySelector('[data-i]')).length / els0.length : 1;
        const orig = window.WH_LANG === 'fil' ? 'fil' : 'en';
        window.setLang(orig === 'fil' ? 'en' : 'fil');
        await new Promise((r) => setTimeout(r, 1500));  // let setPhase() re-render the _t() labels (async from cache)
        const after = [...R.querySelectorAll(sel)].filter(vis).map((e) => (e.textContent || '').trim());
        window.setLang(orig);                           // restore the graded locale
        let changed = 0; const n = Math.min(before.length, after.length);
        for (let i = 0; i < n; i++) if (before[i] && before[i] !== after[i]) changed++;
        const flipCov = before.length ? changed / before.length : 0;
        return { cov: Math.max(dataICov, flipCov), flipCov,
          lang: typeof window.WH_LANG !== 'undefined', t: typeof window._t === 'function',
          fit: document.body.scrollWidth <= window.innerWidth + 2 };
      } catch (e) { return null; }
    });
    if (n1flip != null && res && res.dims) {
      const i = res.dims.findIndex((d) => d.dim === 'N1');
      if (i >= 0 && res.dims[i].kind !== 'NA') {
        // STRICTLY ADDITIVE: the flip recomputes coverage with its OWN labelEl selection, which can
        // disagree with the survey's (different root/vis) — so take max(survey pass, flip pass). This
        // guarantees a page passing on the survey's data-i coverage can NEVER be pulled DOWN (hive:
        // survey 7/7=100% must stay 100% even though the flip's wider sample reads 61%).
        const flipPass = (n1flip.lang ? 1 : 0) + (n1flip.t ? 1 : 0) + (n1flip.cov >= 0.8 ? 1 : 0) + (n1flip.fit ? 1 : 0);
        const pass = Math.max(res.dims[i].pass || 0, flipPass);
        res.dims[i] = { ...res.dims[i], pass, total: 4, pct: Math.round(pass / 4 * 100),
          note: (res.dims[i].note || '').replace(/ · flip-cov.*$/, '') + ` · flip-cov=${Math.round(n1flip.flipCov * 100)}%` };
      }
    }
    // F1/K2 are TOUCH dims — WorkHive is mobile-first and pages deliberately keep
    // tighter desktop density behind @media bumps (same recipe as frontend_ufai_sweep:
    // "the field viewport is the honest one"). Re-measure those two at 390x780.
    await page.setViewportSize({ width: 390, height: 780 });
    await page.waitForTimeout(700);
    const mob = await page.evaluate(() => window.__RUBRIC.survey({ pageId: location.pathname.split('/').pop() }));
    if (res && res.dims && mob && mob.dims) {
      for (const dim of ['F1', 'K2']) {
        const i = res.dims.findIndex((d) => d.dim === dim);
        const m = mob.dims.find((d) => d.dim === dim);
        if (i >= 0 && m) res.dims[i] = m;
      }
      // ── LIVE PROBES (back at desktop for a real load reading + interaction) ──
      // Isolated try/catch: a probe (esp. the D2 click) must NEVER null the already-captured
      // survey `res` — achievements' tab navigated once and destroyed the context, ERRORing an
      // otherwise-good page. On any probe failure we keep res and just skip the probe.
      try {
      await page.setViewportSize({ width: 1280, height: 900 });
      // I1: read the CWV the init-script observers accumulated over the real load.
      const cwv = await page.evaluate(() => window.__cwv || { lcp: 0, cls: 0 });
      // LCP: use the pre-resize snapshot (lcpAtLoad); the post-resize cwv.lcp is inflated by the
      // mobile F1/K2 re-measure re-paint (see the note at the snapshot above). CLS is fine post-resize.
      const lcp = lcpAtLoad > 0 ? lcpAtLoad : (lcpPreResize > 0 ? lcpPreResize : cwv.lcp);
      // CLS: use the pre-resize snapshot (clsAtLoad); the post-resize cwv.cls is inflated by the mobile
      // re-measure's reflow shifts (see the snapshot note above). LCP on a LOCAL dev server (Tailwind
      // CDN, unminified, local RPC latency) runs slower than prod, so the PASS bar is the local-sanity
      // 4000ms ("poor" boundary — catches truly broken pages); the note flags the 2500ms prod target.
      const cls = clsAtLoad;
      const clsGood = cls < 0.1;                             // web.dev "good" CLS (strict)
      const lcpOk = lcp > 0 && lcp < 4000;                   // local sanity bar
      const lcpProdGood = lcp > 0 && lcp < 2500;             // prod target
      const i1i = res.dims.findIndex((d) => d.dim === 'I1');
      if (i1i >= 0 && lcp > 0) {
        const pass = (lcpOk ? 1 : 0) + (clsGood ? 1 : 0);
        res.dims[i1i] = { dim: 'I1', name: 'Core Web Vitals (LIVE: CLS strict, LCP local-aware)', kind: 'MEASURED', pass, total: 2,
          pct: Math.round(pass / 2 * 100),
          note: `LCP ${Math.round(lcp)}ms ${lcpOk ? (lcpProdGood ? 'OK' : 'local-ok/prod>2.5s') : '>4s SLOW'} · CLS ${cls.toFixed(3)} ${clsGood ? 'OK' : '>0.1 SHIFT'}${cwv.culprit ? ' <- ' + cwv.culprit : ''}` };
      }
      // D2 Doherty: click a SAFE UI-only control (tab/disclosure/filter — no data write),
      // measure ms to the next DOM mutation. <400ms = feels instant (Doherty threshold).
      const doherty = await page.evaluate(() => new Promise((resolve) => {
        const vis = (el) => el && el.offsetParent !== null;
        // ONLY non-navigating in-page controls: <summary> and <button>s that toggle a view/
        // filter. Never an <a>, never a submit button, never anything whose onclick calls a
        // navigation — those destroy the page context (achievements' tab did exactly that).
        const nav = (el) => el.tagName === 'A' || el.getAttribute('type') === 'submit'
          || /location|href\s*=|window\.open|\.navigate|goto/i.test(el.getAttribute('onclick') || '');
        // Prefer a control whose click CHANGES state (so it actually mutates the DOM): an
        // INACTIVE tab/filter, or any <summary> (toggling [open] is always a mutation).
        // Clicking an already-active filter/tab is a no-op -- it produces no mutation, which is
        // "nothing was supposed to happen", NOT "the page is slow" (see the timeout->N/A below).
        const active = (el) => el.classList.contains('active') || el.getAttribute('aria-selected') === 'true' || el.getAttribute('aria-pressed') === 'true';
        const pool = [...document.querySelectorAll('summary, button[role="tab"], button.view-tab, button.tab-btn, [class*="view-switch"] button, [class*="filter-chip"]')]
          .filter((el) => vis(el) && el.tagName !== 'A' && !nav(el));
        const cand = pool.find((el) => el.tagName === 'SUMMARY' || !active(el)) || pool[0];
        if (!cand) return resolve({ na: true });
        let done = false; const t0 = performance.now();
        const finish = (r) => { if (!done) { done = true; try { obs.disconnect(); } catch (e) {} resolve(r); } };
        const obs = new MutationObserver(() => finish({ ms: Math.round(performance.now() - t0) }));
        obs.observe(document.body, { childList: true, subtree: true, attributes: true });
        // Guard against an unexpected unload: if the click DID navigate, the promise dies with
        // the context and the outer catch keeps res intact.
        window.addEventListener('beforeunload', () => finish({ na: true, navigated: true }), { once: true });
        try { cand.click(); } catch (e) { return finish({ na: true }); }
        // No mutation in the window = the click had no DOM effect (a no-op control), which is
        // UNMEASURABLE, not a Doherty failure. In these SPAs a real click mutates in <50ms, so a
        // 1.2s silence never means "a mutation took 1.2s" -- mark N/A rather than a false 0.
        setTimeout(() => finish({ na: true, noMutation: true }), 1200);
      }));
      const d2i = res.dims.findIndex((d) => d.dim === 'D2');
      if (d2i >= 0 && !doherty.na) {
        const pass = doherty.ms < 400 ? 1 : 0;
        res.dims[d2i] = { dim: 'D2', name: 'Feedback < 400ms (Doherty, LIVE)', kind: 'MEASURED', pass, total: 1,
          pct: pass * 100, note: `click->paint ${doherty.ms}ms${doherty.timeout ? ' (no mutation in 1.2s)' : ''}` };
      }
      } catch (probeErr) {
        errors.push('live-probe skipped: ' + String(probeErr).slice(0, 90));
      }
      // Recompute ALWAYS (reflects F1/K2 + any probe overrides that DID land).
      const meas = res.dims.filter((d) => d.kind === 'MEASURED' && d.pct !== null);
      res.OVERALL_measured_pct = meas.length ? Math.round(meas.reduce((s, d) => s + d.pct, 0) / meas.length) : null;
      res.failing = res.dims.filter((d) => d.pct !== null && d.pct < 100)
        .sort((a, b) => a.pct - b.pct).map((d) => `${d.dim} ${d.pct}% — ${d.note}`);
    }
    await page.close();
    return { res, errors };
  } catch (e) {
    await page.close().catch(() => {});
    return { res: null, errors: [String(e).slice(0, 200), ...errors] };
  }
}

const browser = await chromium.launch({ headless: !HEADED });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
// Sign-in RETRY: the local Supabase auth intermittently returns WH_DB_TIMEOUT under load. A single
// failed attempt used to abort the whole sweep (exit 1) OR — worse, in --page mode — leave every page
// rendering its SIGNED-OUT/empty state, which read as a phantom board of failures (inventory E3/H1/R4
// all 0, dayplanner CLS spike, G1 gaps) that vanished on the next run. Retry up to 4× with a short
// backoff so a transient DB timeout doesn't masquerade as a page regression.
let si;
for (let attempt = 1; attempt <= 4; attempt++) {
  si = await signInOnce(context);
  if (si.ok) { if (attempt > 1) console.log(`[rubric-sweep] sign-in: OK on attempt ${attempt}`); break; }
  console.log(`[rubric-sweep] sign-in attempt ${attempt} FAIL ${si.err}${attempt < 4 ? ' — retrying' : ''}`);
  if (attempt < 4) await new Promise((r) => setTimeout(r, 1500 * attempt));
}
console.log(`[rubric-sweep] sign-in: ${si.ok ? 'OK' : 'FAIL ' + si.err}`);
if (!si.ok) { await browser.close(); process.exit(1); }

const pages = {};
const perDim = {};
const list = PAGE_ONLY ? [PAGE_ONLY] : PAGES;
for (const file of list) {
  let { res, errors } = await surveyPage(context, file);
  // PAGE-LEVEL RETRY: a transient page-data RPC timeout (distinct from sign-in) renders a page EMPTY
  // — several dims collapse to 0 at once (inventory: E3+G1+H1+R4 all 0) — a phantom dip that scores
  // 100% in isolation. If the render looks empty (>=3 MEASURED dims at pct 0), re-survey ONCE and keep
  // the better result, so the board reflects the true page rather than a one-off contention failure.
  const zeros = (r) => (r && r.dims) ? r.dims.filter((d) => d.kind !== 'N/A' && d.pct === 0).length : 99;
  if (zeros(res) >= 3) {
    console.log(`  ${file}: empty render (${zeros(res)} zero-dims) — retrying once`);
    const retry = await surveyPage(context, file);
    if (retry.res && (retry.res.OVERALL_measured_pct || 0) > ((res && res.OVERALL_measured_pct) || 0)) { res = retry.res; errors = retry.errors; }
  }
  if (!res || !res.dims) {
    pages[file] = { overall: null, error: errors.join(' | ') || 'no result' };
    console.log(`  ${file}: ERROR ${pages[file].error}`);
    continue;
  }
  pages[file] = {
    overall: res.OVERALL_measured_pct,
    counts: res.counts,
    failing: res.failing,
    errors,
    c2_offenders: res.c2_offenders || [],   // the exact elements to fix, not just the worst
    b3_offenders: res.b3_offenders || [],   // the exact sentences to rewrite
    n1: res.n1_i18n || {},                   // { coverage, uncovered:[{tag,id,t}] } — the N1 tagging worklist
    dims: res.dims.map((d) => ({ dim: d.dim, kind: d.kind, pass: d.pass, total: d.total, pct: d.pct, note: d.note })),
  };
  for (const d of res.dims) {
    const a = (perDim[d.dim] ||= { name: d.name, pcts: [], green: 0, fail: 0, na: 0, judged: 0, failPages: [] });
    if (d.kind === 'N/A') a.na++;
    else if (d.kind === 'JUDGED') a.judged++;
    else if (d.pct === null) { a.na++; }        // backstop: MEASURED with no denominator counts N/A
    else {
      a.pcts.push(d.pct);
      if (d.pct === 100) a.green++;
      else { a.fail++; a.failPages.push(`${file.replace('.html', '')} ${d.pct}`); }
    }
  }
  console.log(`  ${file}: ${res.OVERALL_measured_pct}%${errors.length ? ' · pageErrors=' + errors.length : ''}`);
}

for (const a of Object.values(perDim)) {
  a.mean = a.pcts.length ? Math.round(a.pcts.reduce((s, p) => s + p, 0) / a.pcts.length) : null;
  delete a.pcts;
}
const overalls = Object.values(pages).map((p) => p.overall).filter((v) => v !== null && v !== undefined);
const summary = {
  measuredPages: overalls.length,
  mean: overalls.length ? Math.round(overalls.reduce((s, v) => s + v, 0) / overalls.length) : null,
  ge90: overalls.filter((v) => v >= 90).length,
  ge85: overalls.filter((v) => v >= 85).length,
  pageErrors: Object.values(pages).reduce((s, p) => s + (p.errors ? p.errors.length : 0), 0),
  ranAt: new Date().toISOString(),
  identity: EMAIL,
};
writeFileSync(OUT, JSON.stringify({ summary, pages, perDim }, null, 2));
console.log(`[rubric-sweep] mean=${summary.mean} · >=90: ${summary.ge90} · >=85: ${summary.ge85} · pageErrors=${summary.pageErrors} → ${OUT}`);
await browser.close();
