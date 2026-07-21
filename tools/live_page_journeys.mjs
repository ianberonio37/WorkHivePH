// live_page_journeys.mjs — Arc K: the LIVE per-page USER-JOURNEY + UI/UX-CRITIC sweep.
//
// WHY (LIVE_PAGE_JOURNEYS_ROADMAP.md): Arcs D–J each verify a TECHNICAL axis
// (frontend cells, edge fns, DB, AI, auth, realtime). NONE asks the only question a
// paying customer cares about: "on THIS page, can a real user get the job done — and
// how could the UI/UX be better?" Arc K makes the harness behave like a real
// worker/supervisor: it signs in, lands, drives each page's jobs-to-be-done end-to-end
// against the LIVE stack, and judges success by what it OBSERVES — then critiques the
// UI/UX and emits a ranked improvement backlog.
//
// TWO OUTPUT STREAMS (live_page_journeys_results.json):
//   journeys[] — each JTBD scored on 5 journey lenses (R·J·T·C·X) → the ratcheted live%
//   findings[] — the UI/UX Critic's severity-ranked backlog (deterministic floor → 0,
//                + heuristic judgment queue)
//
// LENSES (roadmap §1): R Reachable · J Job-completable · T Truthful (shown==DB) ·
//   C reCoverable (empty/error) · X cross-page-coherent. Each crosswalks to U·F·A·I.
//
// REUSE (not reinvent — WAT How-to-Operate #1):
//   - frontend_ufai_sweep.mjs recipe: :5000 seeder, sign-in-once, navigate, settle
//   - ufai_battery.js (window.__UFAI): axe-core WCAG2.2 + tap/focus/input/CWV = the
//     Critic's deterministic FLOOR (the ~30–40% machine-provable)
//   - journey_trace_results.json: 17 verified rendered-KPI←DB nerves = T-lens ATTRIBUTED
//     proofs (the §13 differential nerve-probe; folded like Arc-D F2/F5 attribution)
//   - journey_battery.js (window.__JOURNEY): cross-page state+number continuity = X-lens
//
// USAGE:
//   node tools/live_page_journeys.mjs                 # all registered journeys
//   node tools/live_page_journeys.mjs --phase K1      # one phase
//   node tools/live_page_journeys.mjs --page index.html
//   node tools/live_page_journeys.mjs --headed
//   node tools/live_page_journeys.mjs --accept        # forward-only live% ratchet
//
// ROLES (live DB): only `worker` + `supervisor` exist (no distinct "engineer" auth role —
//   engineering pages are member-accessible; "engineer" is a usage persona). The recipe
//   account Leandro Marquez is the SUPERVISOR; Bryan Garcia is a WORKER.

import { chromium } from 'playwright';
import { writeFileSync, readFileSync, existsSync } from 'fs';
import { execSync } from 'child_process';
import { pathToFileURL } from 'url';

// IS_MAIN: true only when invoked directly (node tools/live_page_journeys.mjs), false when
// imported (e.g. by tools/effortless_sweep.mjs, which reuses signIn/makeHelpers). Guards the
// Arc-K sweep IIFE so importing the recipe does NOT re-run the whole sweep on import.
const IS_MAIN = !!process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;

// ─── privileged DB query (local-substitute, docker psql) ──────────────────────
// Some T-lens checks must run as a PRIVILEGED reader: e.g. early_access_emails is
// anon-INSERT but service_role-SELECT only, so the in-page anon client cannot read its
// own write back. A node-side psql query is the honest verifier (NOT faking live — it
// reads the real local DB the page wrote to). Returns trimmed stdout or {__err}.
const DB_CONTAINER = process.env.WH_DB_CONTAINER || 'supabase_db_workhive';
function adminQuery(sql) {
  try { return execSync(`docker exec ${DB_CONTAINER} psql -U postgres -d postgres -t -A -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); }
  catch (e) { return { __err: String(e.message || e).slice(0, 140) }; }
}

// ─── config ─────────────────────────────────────────────────────────────────
const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SUPABASE_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
// HIVE default fixed 2026-07-19 (Ian-sanctioned systemic stale-hive drive): was 9b4eaeac — BOTH test
// accounts (leandromarquez + bryangarcia) are members of 636cf7e8, NOT 9b4eaeac. The stale default made
// every gate using this recipe get RLS 0-rows → scan EMPTY pages (false confidence). 636cf7e8 = the real
// Baguio Textile Mills hive both accounts belong to.
const HIVE = process.env.WH_TEST_HIVE || '636cf7e8-431a-4907-8a9f-43dd4cc216d6'; // hive fallback only — signIn resolves live membership
const ACCOUNTS = {
  supervisor: { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234', worker: 'Leandro Marquez' },
  worker: { email: 'bryangarcia@auth.workhiveph.com', pw: 'test1234', worker: 'Bryan Garcia' },
  // anon = no sign-in (a fresh context with no session)
};
// "engineer" persona maps to the supervisor account (no separate E auth role exists).
ACCOUNTS.engineer = ACCOUNTS.supervisor;

const args = process.argv.slice(2);
const HEADED = args.includes('--headed');
const ACCEPT = args.includes('--accept');
const UPDATE_BASELINE = args.includes('--update-baseline');
const PHASE_ONLY = (() => { const i = args.indexOf('--phase'); return i >= 0 ? args[i + 1] : null; })();
const PAGE_ONLY = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const RESULTS = 'live_page_journeys_results.json';
const BASELINE = 'live_page_journeys_baseline.json';
const FINDINGS = 'live_page_journeys_findings.json';

function loadJson(p) { try { return JSON.parse(readFileSync(p, 'utf8')); } catch (e) { return null; } }

// ─── Critic deterministic-floor thresholds (skills-grounded; the machine-provable set) ──
// ≥44px tap (WCAG 2.5.5 / mobile-maestro), ≥16px input font (iOS no-zoom),
// contrast ≥4.5:1 (WCAG 1.4.3 via axe), CWV LCP≤2.5s/INP≤200ms/CLS≤0.1 (performance skill),
// focus-visible present (WCAG 2.4.7), empty-state-has-CTA (designer/qa), no FAB occlusion.
const FLOOR = { tap: 44, inputFont: 16, contrast: 4.5, lcp: 2500, inp: 200, cls: 0.1 };

// ─── T-lens attribution: page → verified rendered-KPI←DB nerves ────────────────
// journey_trace_results.json proves (via tools/journey_trace.py, §13 nerve-probe) that a
// page's rendered KPI traces correctly to its canonical DB view. A page with a verified
// nerve gets its Truthful lens ATTRIBUTED (counted, labelled ◈attributed — same honesty
// as Arc-D F2/F5), unless the journey also does a fresh in-page T-check (then: live ✓).
const TRACES = loadJson('journey_trace_results.json') || { nerves: {} };
const T_ATTRIBUTED = {}; // input_surface (page slug) -> [{nerve, field, consumers}]
for (const [nerve, n] of Object.entries(TRACES.nerves || {})) {
  if (!n.verified) continue;
  const slug = n.input_surface;
  (T_ATTRIBUTED[slug] = T_ATTRIBUTED[slug] || []).push({ nerve, field: n.field, termini: `${n.termini_ok}/${n.termini_total}` });
}
function pageSlug(pageFile) { return pageFile.replace(/\.html$/, ''); }

// ─── ufai_battery.js (axe-core + tap/focus/input/CWV) = the Critic's FLOOR referee ──
const BATTERY_SRC = readFileSync('ufai_battery.js', 'utf8');

// ─── Heuristic-judgment catalog (Layer 2 — Nielsen-10 + Norman-7 + WCAG-POUR + skills) ──
// AUTO_HEURISTICS = the live axe-complementary detectors; CATALOG = the full 209-rule
// skills-synthesis (reference/triage). Only the deterministic floor ratchets to 0.
import { AUTO_HEURISTICS, CATALOG } from './live_page_journeys.heuristics.mjs';

// ═══════════════════════════════════════════════════════════════════════════════
// JOURNEY REGISTRY — each JTBD is one user job that must complete LIVE on the page.
//   { id, page, role, state, title, lenses:[R/J/T/C/X], ufai:[U/F/A/I], external?:bool,
//     drive: async (page, h) => ({ R,J,T,C,X (bool|null), evidence:{}, findings:[] }) }
//   - role: 'anon' | 'worker' | 'supervisor' | 'engineer'(=supervisor)
//   - a lens verdict of `null` = not-applicable to this JTBD (excluded from its denom)
//   - external:true = ◈ external-key ceiling (Stripe/Resend/CMMS) — Ian-gated, excluded
//     from the LOCAL live% target
//   - h (helpers): { goto, q, qText, click, fill, waitFor, db, truthEqual, exists, count }
// K1 journeys + the rest are registered in ./live_page_journeys.registry.mjs (filled per
// phase). K0 ships the ENGINE + K1; later phases append.
import { JOURNEYS } from './live_page_journeys.registry.mjs';

// ─── sign-in (per role; reuses the frontend_ufai_sweep recipe) ─────────────────
async function signIn(context, role) {
  if (role === 'anon') return { ok: true, anon: true };
  const acct = ACCOUNTS[role];
  if (!acct) return { ok: false, err: `unknown role ${role}` };
  const page = await context.newPage();
  await page.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
  const r = await page.evaluate(async ({ email, password, hive, worker, role, hiveName, url }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email, password });
      // RESOLVE the hive from the DB membership SSOT, don't assert it (2026-07-21).
      // The hardcoded HIVE constant drifted from the reseeded DB (accounts moved to another
      // hive), so every journey stamped a hive the account is NOT a member of → RLS returned
      // 0 rows → pages showed the "needs a hive" gate and the Arc-W probe read cards 0
      // (a false focal regression on asset-hub). The DB is the membership SSOT — read it;
      // the passed constant is only the fallback if the lookup fails.
      let realHive = hive, realWorker = worker, realName = hiveName, realUid = null;
      try {
        const uid = data?.session?.user?.id;
        realUid = uid || null;
        if (uid) {
          const { data: mem } = await db.from('hive_members')
            .select('hive_id, worker_name, status').eq('auth_uid', uid).eq('status', 'active')
            .limit(1).maybeSingle();
          if (mem && mem.hive_id) {
            realHive = mem.hive_id;
            realWorker = mem.worker_name || worker;
            const { data: hv } = await db.from('hives').select('name').eq('id', mem.hive_id)
              .limit(1).maybeSingle();
            if (hv && hv.name) realName = hv.name;
          }
        }
      } catch (_) { /* fall back to the passed constants */ }
      // seed the full home-authed identity so index.html's _showOpsHome path renders
      // the role launchpad (hive chip + supervisor/worker action branch) deterministically.
      localStorage.setItem('wh_active_hive_id', realHive);
      localStorage.setItem('wh_last_worker', realWorker);
      localStorage.setItem('wh_hive_name', realName);
      localStorage.setItem('wh_hive_role', role);
      if (role === 'supervisor') localStorage.setItem('wh_nav_mode', 'supervisor');
      return { ok: !error && !!data?.session, hive: realHive, uid: realUid,
               err: error ? String(error.message || error) : null };
    } catch (e) { return { ok: false, err: String(e) }; }
  }, { email: acct.email, password: acct.pw, hive: HIVE, worker: acct.worker, role, hiveName: 'Baguio Textile Mills', url: SUPABASE_URL });
  await page.close();
  return r;
}

// Per-role hive resolved at sign-in from the LIVE hive_members row (the .mjs mirror of
// tools/lib/test_identity.py — "a hard-coded UUID is the bug"; reseed-proof).
const RESOLVED_HIVES = {};
const RESOLVED_UIDS = {};

// ─── helpers handed to each journey's drive() — thin, observation-first ─────────
function makeHelpers(page, hive, uid) {
  return {
    page,
    hive: hive || null,   // the signed-in role's REAL hive (DB membership SSOT); oracles use this
    uid: uid || null,     // the signed-in role's REAL auth_uid (pinned uids rot across reseeds too)
    goto: async (pageFile, query = '') => {
      await page.goto(`${SEEDER}/workhive/${pageFile}${query}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(2500); // settle async render
      return page.url();
    },
    // first matching visible element's trimmed text (or null)
    qText: async (sel) => page.evaluate((s) => {
      const vis = el => { const b = el.getBoundingClientRect(); const st = getComputedStyle(el); return b.width > 0 && b.height > 0 && st.visibility !== 'hidden' && st.display !== 'none'; };
      const el = [...document.querySelectorAll(s)].find(vis); return el ? (el.textContent || '').trim() : null;
    }, sel),
    exists: async (sel) => page.evaluate((s) => {
      const vis = el => { const b = el.getBoundingClientRect(); const st = getComputedStyle(el); return b.width > 0 && b.height > 0 && st.visibility !== 'hidden' && st.display !== 'none'; };
      return [...document.querySelectorAll(s)].some(vis);
    }, sel),
    count: async (sel) => page.evaluate((s) => document.querySelectorAll(s).length, sel),
    click: async (sel) => { try { await page.click(sel, { timeout: 5000 }); await page.waitForTimeout(800); return true; } catch (e) { return false; } },
    clickText: async (text) => page.evaluate(async (t) => {
      const vis = el => { const b = el.getBoundingClientRect(); const st = getComputedStyle(el); return b.width > 0 && b.height > 0 && st.visibility !== 'hidden' && st.display !== 'none'; };
      const el = [...document.querySelectorAll('button,a,[role="button"],[onclick],.btn')].find(e => vis(e) && (e.textContent || '').trim().toLowerCase().includes(String(t).toLowerCase()));
      if (!el) return false; el.click(); await new Promise(r => setTimeout(r, 800)); return true;
    }, text),
    fill: async (sel, val) => { try { await page.fill(sel, val, { timeout: 5000 }); return true; } catch (e) { return false; } },
    waitFor: async (sel, t = 6000) => { try { await page.waitForSelector(sel, { timeout: t, state: 'visible' }); return true; } catch (e) { return false; } },
    // T-lens: run a query with the page's OWN authed supabase client (same identity the
    // page uses) and return the result. `fn` is (db, arg) => …; `arg` is serialized in.
    db: async (fn, arg) => page.evaluate(async ({ src, arg }) => {
      try { const db = window._whSupabaseClient || window.getDb(window.SUPABASE_URL || 'http://127.0.0.1:54321', window.SUPABASE_KEY); return await (eval('(' + src + ')'))(db, arg); }
      catch (e) { return { __err: String(e) }; }
    }, { src: fn.toString(), arg }),
    // raw in-page evaluate passthrough (custom DOM probes / localStorage flips)
    evalIn: (fn, arg) => page.evaluate(fn, arg),
    // privileged T-lens verifier for anon-write-only tables (node-side psql)
    adminQuery,
    // reset the 3 AI rate-limit buckets before an LLM journey (the Arc D–J gotcha —
    // narrative_grounding/LLM validators drain them; a 429 fakes a journey failure)
    resetRates: () => { for (const t of ['ai_rate_limits', 'ai_user_rate_limits', 'hive_route_calls']) { try { adminQuery(`delete from ${t};`); } catch (e) { /* table may not exist locally */ } } },
    numFrom: (s) => { if (s == null) return null; const m = String(s).replace(/[, ]/g, '').match(/-?\d+(?:\.\d+)?/); return m ? parseFloat(m[0]) : null; },
  };
}

// ─── the Critic — run once per (page,role): deterministic FLOOR (axe + tap/focus/input
//     /CWV + FAB) that ratchets to 0, PLUS the axe-complementary heuristic detectors. ──
async function runCritic(page, pageFile, role) {
  const findings = [];
  let bat = { ok: false };
  // Measure the tap/focus/input FLOOR at the MOBILE field viewport (390). WorkHive is
  // mobile-first: controls are correctly smaller for a mouse at desktop and reach ≥44 via
  // `@media (max-width:480)`, so measuring tap-targets at desktop over-reports (Arc D recipe
  // lesson — frontend_ufai_sweep.mjs:549). axe contrast/names are viewport-independent.
  try { await page.setViewportSize({ width: 390, height: 780 }); await page.waitForTimeout(600); } catch (e) { }
  try {
    await page.evaluate(`(${BATTERY_SRC})()`);
    await page.evaluate(`(async()=>{ try { await window.__UFAI.boot(); } catch(e){} })()`);
    const ref = await page.evaluate(async (pid) => await window.__UFAI.referee({ pageId: pid, role: 'supervisor', experience: 'experienced' }), pageSlug(pageFile));
    const um = ref?.scores?.U?.metrics || {};
    const axe = um.axe || { ran: false };
    bat = {
      ok: true,
      axeRan: !!axe.ran, axeViolations: axe.violations || 0, axeByImpact: axe.byImpact || {},
      tapUnder44: um.tapTargets ? um.tapTargets.under44 : null,
      tapChecked: um.tapTargets ? um.tapTargets.checked : null,
      focusMissing: um.focusVisible ? um.focusVisible.missing : null,
      inputUnder16: um.inputs ? um.inputs.under16 : null,
      axeIds: (ref?.defects || []).filter(d => d.pillar === 'U' && String(d.check).startsWith('axe:')).map(d => ({ id: d.check, sev: d.severity, m: String(d.measured).slice(0, 90) })),
    };
    // deterministic-floor findings (these RATCHET to 0)
    if (bat.tapUnder44 > 0) findings.push({ page: pageFile, role, layer: 'floor', rule: 'tap-target≥44px', severity: 2, evidence: `${bat.tapUnder44}/${bat.tapChecked} interactive <44px`, owner: 'mobile-maestro' });
    if (bat.inputUnder16 > 0) findings.push({ page: pageFile, role, layer: 'floor', rule: 'input-font≥16px (iOS no-zoom)', severity: 2, evidence: `${bat.inputUnder16} inputs <16px`, owner: 'mobile-maestro' });
    if (bat.focusMissing > 0) findings.push({ page: pageFile, role, layer: 'floor', rule: 'focus-visible present', severity: 2, evidence: `${bat.focusMissing} focusable without focus ring`, owner: 'frontend' });
    if (bat.axeRan && bat.axeViolations > 0) for (const a of bat.axeIds) findings.push({ page: pageFile, role, layer: 'floor', rule: a.id, severity: a.sev >= 3 ? 3 : 2, evidence: a.m, owner: 'qa-tester' });
  } catch (e) { bat = { ok: false, err: String(e).slice(0, 120) }; }

  // FAB-occlusion: a bottom-right floating control must not cover page content at 390px.
  try {
    await page.setViewportSize({ width: 390, height: 780 });
    await page.waitForTimeout(500);
    const occ = await page.evaluate(() => {
      const pts = [[0.5, 0.92], [0.85, 0.92]].map(([fx, fy]) => ({ x: Math.round(innerWidth * fx), y: Math.round(innerHeight * fy) }));
      const isShell = el => !!(el && el.closest && el.closest('[id^="wh-ai"],[id^="wh-hub"],#wh-companion,.wh-hub'));
      let covered = 0;
      for (const p of pts) { const el = document.elementFromPoint(p.x, p.y); if (isShell(el)) covered++; }
      return covered;
    });
    if (occ >= 2) findings.push({ page: pageFile, role, layer: 'floor', rule: 'no FAB content-occlusion', severity: 1, evidence: `shell overlay covers ${occ}/2 bottom probe points`, owner: 'mobile-maestro' });
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.waitForTimeout(300);
  } catch (e) { /* best-effort */ }

  // ── Layer 2: axe-complementary heuristic detectors (severity-ranked backlog) ──
  for (const h of AUTO_HEURISTICS) {
    try {
      const hits = await page.evaluate(h.fn);
      for (const hit of (hits || [])) findings.push({ page: pageFile, role, layer: 'heuristic', rule: h.rule, basis: h.basis, severity: hit.severity ?? h.severity, evidence: `${hit.sel} — ${hit.evidence}`, owner: h.owner });
    } catch (e) { /* a detector throwing must not sink the critic */ }
  }

  return { bat, findings };
}

// ─── 5-lens scorer ─────────────────────────────────────────────────────────────
// A journey is "live-passing" when EVERY applicable (non-null) lens verdict is true.
const LENS_IDS = ['R', 'J', 'T', 'C', 'X'];
function scoreJourney(v) {
  const applicable = LENS_IDS.filter(l => v[l] !== null && v[l] !== undefined);
  const passed = applicable.filter(l => v[l] === true);
  return { applicable, passed, live: applicable.length > 0 && passed.length === applicable.length };
}

// ─── run one journey (context already signed-in for its role) ──────────────────
async function runJourney(context, j, criticCache) {
  const page = await context.newPage();
  const h = makeHelpers(page, RESOLVED_HIVES[j.role] || HIVE, RESOLVED_UIDS[j.role] || null);
  let verdict = { R: null, J: null, T: null, C: null, X: null }, evidence = {}, jfindings = [], err = null;
  try {
    const out = await j.drive(page, h);
    verdict = { R: out.R ?? null, J: out.J ?? null, T: out.T ?? null, C: out.C ?? null, X: out.X ?? null };
    evidence = out.evidence || {};
    jfindings = out.findings || [];
  } catch (e) { err = String(e).slice(0, 200); }

  // attach T-lens attribution if the journey claims T but didn't measure it live.
  // Guard on !err — an errored drive must NOT be credited a "live" via attribution (that
  // would mask a broken journey as passing because only the attributed lens is non-null).
  if (j.lenses.includes('T') && verdict.T == null && !err) {
    const attr = T_ATTRIBUTED[pageSlug(j.page)];
    if (attr && attr.length) { verdict.T = true; evidence.T_attributed = `[attributed: journey_trace.py nerve-probe] ${attr.map(a => a.nerve + ' ' + a.termini).join('; ')}`; }
  }

  // critic (cached per page+role — run once): deterministic floor + heuristic backlog
  const key = `${j.page}::${j.role}`;
  let critic = criticCache.get(key);
  if (!critic) { critic = await runCritic(page, j.page, j.role); criticCache.set(key, critic); }

  await page.close();
  const sc = scoreJourney(verdict);
  return { verdict, evidence, score: sc, findings: jfindings, criticFindings: critic.findings, bat: critic.bat, err };
}

// ═══════════════════════════════════════════════════════════════════════════════
// Reusable recipe exported for Arc V (Effortless, tools/effortless_sweep.mjs) + any future
// journey consumer — so the sign-in/helper/critic recipe has ONE source of truth (no drift).
export { signIn, makeHelpers, runCritic, runJourney, scoreJourney, pageSlug, adminQuery, ACCOUNTS, SEEDER, SUPABASE_URL, HIVE, T_ATTRIBUTED, LENS_IDS };

// ─── SERVICE PREFLIGHT (2026-07-21) — a dead service must never masquerade as journey
// regressions. Runs #2/#3 read an identical 59/102 "regression" that was actually the edge
// runtime container being DOWN (every fn 503 via Kong → every edge-touching J/T false-failed)
// + the python-API socat forwarder exited (analytics "unavailable"). Check every backing
// service BEFORE sign-in; a hard-down core service ABORTS (exit 3) so the run can't emit a
// corrupted board. Override with --force-degraded to run anyway (recorded in the summary).
async function preflight() {
  const checks = {};
  const httpCode = async (url, opts = {}) => {
    try { const r = await fetch(url, { ...opts, signal: AbortSignal.timeout(6000) }); return r.status; }
    catch (e) { return 0; }
  };
  checks.seeder = await httpCode(`${SEEDER}/workhive/index.html`);
  checks.gotrue = await httpCode(`${SUPABASE_URL}/auth/v1/health`, { headers: { apikey: 'x' } });
  // edge runtime: any fn responding NON-503 means Kong routes to a LIVE runtime (401/400 are fine)
  checks.edge_fn = await httpCode(`${SUPABASE_URL}/functions/v1/analytics-orchestrator`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  checks.python_api = await httpCode('http://127.0.0.1:8000/health');
  const psql = adminQuery('SELECT 1;');
  checks.db_psql = (psql === '1');
  const bad = [];
  if (!checks.seeder) bad.push('flask seeder :5000 unreachable');
  if (!checks.gotrue) bad.push('supabase gotrue :54321 unreachable');
  if (checks.edge_fn === 503 || checks.edge_fn === 0) bad.push(`edge runtime DOWN (fn probe ${checks.edge_fn}) — docker start supabase_edge_runtime_workhive`);
  if (!checks.python_api) bad.push('python API :8000 down — docker start workhive_python_api_fwd (socat)');
  if (!checks.db_psql) bad.push('docker psql failed — is supabase_db_workhive up?');
  console.log(`[K] preflight: seeder ${checks.seeder} · gotrue ${checks.gotrue} · edge_fn ${checks.edge_fn} · python ${checks.python_api} · psql ${checks.db_psql}${bad.length ? '  ⚠ ' + bad.join(' | ') : '  ✓ all services live'}`);
  return { checks, bad };
}

const __runArcK = async () => {
  let journeys = JOURNEYS.filter(j => (!PHASE_ONLY || j.phase === PHASE_ONLY) && (!PAGE_ONLY || j.page === PAGE_ONLY));
  if (!journeys.length) { console.error(`[K] no journeys match (phase=${PHASE_ONLY} page=${PAGE_ONLY}). Registered: ${JOURNEYS.length}`); process.exit(2); }

  const pf = await preflight();
  if (pf.bad.length && !args.includes('--force-degraded')) {
    console.error(`[K] ABORT — ${pf.bad.length} backing service(s) down (a degraded run emits a FALSE board). Fix the services above or pass --force-degraded to run anyway.`);
    process.exit(3);
  }

  const browser = await chromium.launch({ headless: !HEADED });
  // one signed-in context per role used by the selected journeys
  const rolesNeeded = [...new Set(journeys.map(j => j.role))];
  const contexts = {};
  for (const role of rolesNeeded) {
    // Asia/Manila: the harness must see dates the way a real PH user's browser does (the
    // app derives "today" from the browser's local date — a UTC headless browser would be
    // a day behind in the evening, breaking date-scoped journeys like the day planner).
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: 'Asia/Manila' });
    const si = await signIn(ctx, role);
    if (si.hive) RESOLVED_HIVES[role] = si.hive;   // DB-truth hive for this role's oracles
    if (si.uid) RESOLVED_UIDS[role] = si.uid;      // DB-truth auth_uid (probe-row inserts)
    console.log(`[K] sign-in ${role.padEnd(11)}: ${si.ok ? (si.anon ? 'ANON (no session)' : 'OK') : 'FAIL ' + si.err}${si.hive ? ' hive ' + si.hive.slice(0, 8) : ''}`);
    contexts[role] = ctx;
  }

  const out = { ran: new Date().toISOString(), seeder: SEEDER, hive: HIVE,
                preflight: pf.checks, degraded: pf.bad, journeys: [], findings: [] };
  const criticCache = new Map();
  const allCritic = [];
  let nLive = 0, nApplicable = 0, nExternal = 0;
  const perPage = {};

  for (const j of journeys) {
    const res = await runJourney(contexts[j.role], j, criticCache);
    const rec = {
      id: j.id, phase: j.phase, page: j.page, role: j.role, state: j.state, title: j.title,
      lenses: j.lenses, ufai: j.ufai, external: !!j.external,
      verdict: res.verdict, live: res.score.live, applicable_lenses: res.score.applicable, passed_lenses: res.score.passed,
      evidence: res.evidence, err: res.err,
    };
    out.journeys.push(rec);
    for (const f of res.findings) out.findings.push({ page: j.page, role: j.role, ...f, layer: f.layer || 'heuristic', id: j.id });
    for (const f of res.criticFindings) allCritic.push(f);

    const pk = j.page;
    perPage[pk] = perPage[pk] || { page: pk, live: 0, applicable: 0, external: 0 };
    if (j.external) { nExternal++; perPage[pk].external++; }
    else { nApplicable++; perPage[pk].applicable++; if (res.score.live) { nLive++; perPage[pk].live++; } }

    const lensStr = LENS_IDS.map(l => res.verdict[l] === true ? `${l}✓` : res.verdict[l] === false ? `${l}✗` : `${l}-`).join(' ');
    console.log(`  ${(j.id + ' ' + j.role).padEnd(22)} ${j.page.padEnd(22)} ${lensStr}  ${j.external ? '◈ext' : res.score.live ? 'LIVE' : 'gap'}${res.err ? '  ERR ' + res.err : ''}`);
  }

  // dedupe critic findings (page+role+rule+lead-selector) then merge into findings stream
  const seen = new Set();
  for (const f of allCritic) { const k = `${f.page}::${f.role}::${f.rule}::${(f.evidence || '').slice(0, 40)}`; if (seen.has(k)) continue; seen.add(k); out.findings.push(f); }

  for (const c of Object.values(contexts)) await c.close();
  await browser.close();

  // ── rollups ──
  out.summary = {
    journeys_total: journeys.length,
    applicable: nApplicable, live: nLive, external: nExternal,
    live_pct: nApplicable ? Math.round(1000 * nLive / nApplicable) / 10 : 0,
    floor_findings: out.findings.filter(f => f.layer === 'floor').length,
    heuristic_findings: out.findings.filter(f => f.layer === 'heuristic').length,
    critic_catalog_rules: CATALOG.count || (CATALOG.rules || []).length,
  };
  out.per_page = Object.values(perPage).map(p => ({ ...p, live_pct: p.applicable ? Math.round(1000 * p.live / p.applicable) / 10 : 0 }));
  // per-lens rollup
  out.per_lens = {};
  for (const l of LENS_IDS) {
    const appl = out.journeys.filter(j => !j.external && j.verdict[l] != null);
    const pass = appl.filter(j => j.verdict[l] === true);
    out.per_lens[l] = { applicable: appl.length, pass: pass.length, pct: appl.length ? Math.round(1000 * pass.length / appl.length) / 10 : 0 };
  }

  console.log('\n' + '='.repeat(70));
  console.log('ARC K — LIVE PAGE JOURNEYS + UI/UX CRITIC');
  console.log('='.repeat(70));
  console.log(`  journeys      : ${journeys.length} (${nExternal} ◈ external-ceiling, excluded from local target)`);
  console.log(`  LIVE          : ${nLive}/${nApplicable} = ${out.summary.live_pct}%  (local target)`);
  console.log(`  per-lens      : ${LENS_IDS.map(l => `${l} ${out.per_lens[l].pct}%`).join(' · ')}`);
  console.log(`  floor findings: ${out.summary.floor_findings} (RATCHET → 0)`);
  console.log(`  heuristic     : ${out.summary.heuristic_findings} (severity-ranked backlog)`);
  for (const p of out.per_page) console.log(`    ${p.page.padEnd(26)} ${p.live}/${p.applicable} live = ${p.live_pct}%${p.external ? ` (+${p.external} ◈)` : ''}`);

  // ── forward-only ratchet on live count + floor=0 ──
  if (ACCEPT) {
    const cur = { live: nLive, applicable: nApplicable, floor: out.summary.floor_findings };
    if (UPDATE_BASELINE || !existsSync(BASELINE)) {
      writeFileSync(BASELINE, JSON.stringify({ ...cur, set: new Date().toISOString() }, null, 2));
      console.log(`\n[K] baseline ${UPDATE_BASELINE ? 'UPDATED' : 'created'}: live>=${nLive}, floor<=${cur.floor}`);
    } else {
      const base = JSON.parse(readFileSync(BASELINE, 'utf8'));
      let failed = false;
      if (nLive < base.live) { console.error(`\n[K] RATCHET FAIL: live ${nLive} < baseline ${base.live}`); failed = true; }
      if (base.floor != null && cur.floor > base.floor) { console.error(`[K] RATCHET FAIL: floor findings ${cur.floor} > baseline ${base.floor}`); failed = true; }
      if (failed) { writeFileSync(RESULTS, JSON.stringify(out, null, 2)); process.exit(1); }
      console.log(`\n[K] ratchet OK: live ${nLive}>=${base.live}, floor ${cur.floor}<=${base.floor ?? '(new)'}`);
    }
  }

  writeFileSync(RESULTS, JSON.stringify(out, null, 2));
  writeFileSync(FINDINGS, JSON.stringify({ ran: out.ran, findings: out.findings }, null, 2));
  console.log(`\n  -> wrote ${RESULTS} (${out.journeys.length} journeys) + ${FINDINGS} (${out.findings.length} findings)`);

  // top findings preview
  const bySev = [...out.findings].sort((a, b) => (b.severity || 0) - (a.severity || 0));
  if (bySev.length) {
    console.log(`\n  TOP findings:`);
    for (const f of bySev.slice(0, 20)) console.log(`    [S${f.severity}|${f.layer}] ${f.page} ${f.rule}: ${String(f.evidence || '').slice(0, 80)}`);
  }
};

// Run the Arc-K sweep ONLY when invoked directly — not when imported as a recipe library.
if (IS_MAIN) __runArcK();
