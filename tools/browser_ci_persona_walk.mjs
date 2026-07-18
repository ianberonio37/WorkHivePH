// browser_ci_persona_walk.mjs — FB2 (Forward-Build): the headless browser-CI harness.
//
// WHY (NEXT_ARCS_ROADMAP.md ① FB2 — "#7, biggest single live lever"): Arc D's ~852
// frontend cells are measured live by frontend_ufai_sweep.mjs — but as ONE identity
// (supervisor Leandro, desktop). A page can render clean for a supervisor and BREAK for
// a worker (role-gated UI), or clean on desktop and overflow on mobile. The single-
// identity sweep is structurally blind to that. FB2 walks every page as a DIVERSE persona
// roster HEADLESS (the §0 verification doctrine) and ratchets a cross-persona live floor,
// so a regression that only hits ONE persona/viewport is caught in CI, not in the field.
//
// REUSE (not reinvent — WAT premise): the SAME recipe as frontend_ufai_sweep.mjs —
//   - :5000 seeder (or WH_TEST_BASE_URL) serves pages repointed to local Supabase
//   - sign in ONCE per persona on a lenient page (shift-brain); session persists same-origin
//   - per page, install ufai_battery.js (window.__UFAI) + run the AUTHORITATIVE referee
//     keyed by the persona's {role, experience}; the battery's Major/Blocker defects ARE
//     the falsifiable floor ("the agent fixes these inline" — battery doc §35).
//   The NEW dimension is the persona × viewport matrix, run CONCURRENTLY (read-only audit,
//   no DB writes → safe to parallelise; ~4x wall-clock win).
//
// THE PERSONA POOL (NEXT_ARCS §0 — field-tech / supervisor / new-worker / admin), each
// mapped to a (role × viewport × hive) that changes what is RENDERED (= genuine new evidence):
//   field-tech : worker      × MOBILE 390  (gloved/hurried/mobile, Baguio)
//   supervisor : supervisor  × DESKTOP     (planning oversight, Baguio)
//   new-worker : worker      × DESKTOP     (onboarding/unfamiliar, Baguio — novice scoring)
//   admin      : supervisor  × DESKTOP     (platform/founder oversight, a DIFFERENT hive = Lucena,
//                                           so cross-hive render diversity is exercised too)
//
// FALSIFIABLE FLOOR — the PERSONA-DELTA, not a re-derived absolute. Arc D
// (frontend_ufai_sweep.mjs) ALREADY owns the absolute per-page U/I/A/F floor for the
// supervisor identity. FB2's UNIQUE, non-overlapping contribution is breakage that is
// SPECIFIC to a non-supervisor persona (worker role, mobile, cross-hive, novice) and that
// Arc D's single-identity desktop sweep is structurally blind to. So FB2's floor =
// RUNTIME / SECURITY / SERIOUS-A11Y defects in the persona's authed state:
//   · I: secretExposures > 0            (a role/tenant-gated secret leak — top value)
//   · F: console-error / onclick→undefined-fn  (a code path that THROWS or is dead only
//        for this role — the single-identity sweep never exercised it)
//   · U: axe:* at Major severity (critical/serious WCAG)  (serious a11y for this persona)
// EXCLUDED from the floor (recorded for transparency, NOT failed — to avoid DOUBLE-gating
// Arc-D-owned absolutes + a local-env artifact):
//   · tap-target<44 / input-font<16 / focus-not-visible  → Arc D U2/U5 own these (campaign-
//     driven, dispositioned); measured at 390 already. FB2 re-flagging = noise.
//   · CLS>0.1 / LCP>2.5s                                  → Arc W / perf own these.
//   · broken-internal-link / dead-href / prod-path-in-src → root-relative /x.html 404s under
//     the :5000 seeder's /workhive/ mount (resolve in prod — [[feedback_workhive_url_prefix]]);
//     link integrity is Arc D F4-owned.
// A bounce to the sign-in/landing page for a role-gated surface (e.g. a worker on
// founder-console) is the SECURITY-CORRECT outcome → scored `gated` (the gate held), not a
// fail. Deprecated pages (slated for removal) → dispositioned, never invested in.
//
// FB2 floor classes (Major battery checks that DO fail a persona):
const FB2_FLOOR_CHECKS = (check) =>
  check === 'console-error' || check === 'onclick→undefined-fn' || check.startsWith('axe:');
// Arc-D / perf / env-owned classes (recorded but EXCLUDED from the FB2 floor):
const EXCLUDED_CHECK = (check) =>
  check === 'tap-target<44' || check === 'input-font<16' || check === 'focus-not-visible' ||
  check === 'CLS>0.1' || check === 'LCP>2.5s' ||
  check === 'broken-internal-link' || check === 'dead-href' || check === 'prod-path-in-src' ||
  check === 'horiz-overflow';
//
// USAGE:
//   node tools/browser_ci_persona_walk.mjs                     # all personas × all pages
//   node tools/browser_ci_persona_walk.mjs --persona field-tech
//   node tools/browser_ci_persona_walk.mjs --page logbook.html
//   node tools/browser_ci_persona_walk.mjs --limit 5          # smoke (first 5 pages)
//   node tools/browser_ci_persona_walk.mjs --headed
//   node tools/browser_ci_persona_walk.mjs --accept            # forward-only ratchet
//   node tools/browser_ci_persona_walk.mjs --accept --update-baseline
//
// Output: browser_ci_persona_board.json (per-persona × per-page) + browser_ci_persona_baseline.json

import { chromium } from 'playwright';
import { writeFileSync, readFileSync, existsSync } from 'fs';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SUPABASE_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const RESULTS_SRC = 'frontend_ufai_results.json';     // the mined page denominator (37 pages)
// BOARD output path is overridable (--out <path> / WH_FB2_BOARD) so concurrent per-page
// verify runs (e.g. a parallel fix workflow) don't clobber the canonical board file.
const _outArg = (() => { const i = process.argv.indexOf('--out'); return i >= 0 ? process.argv[i + 1] : null; })();
const BOARD = _outArg || process.env.WH_FB2_BOARD || 'browser_ci_persona_board.json';
const BASELINE = 'browser_ci_persona_baseline.json';

const HIVES = {
  baguio: '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7',
  lucena: '3792d7f0-59e2-42e6-b04f-6e6ef4e4713d',
  manila: 'ba383fb9-1e76-420e-a8cd-8ecf45bfe5a7',
};

// The diverse persona roster. pw is the shared seed password (test1234).
const PERSONAS = [
  { id: 'field-tech', label: 'Field technician (worker, mobile)', email: 'bryangarcia@auth.workhiveph.com',      role: 'worker',     experience: 'novice',       worker: 'Bryan Garcia',      hive: HIVES.baguio, vw: 390,  vh: 780 },
  { id: 'supervisor', label: 'Supervisor (desktop)',             email: 'leandromarquez@auth.workhiveph.com',    role: 'supervisor', experience: 'experienced',  worker: 'Leandro Marquez',   hive: HIVES.baguio, vw: 1280, vh: 900 },
  { id: 'new-worker', label: 'New worker (worker, desktop)',     email: 'wilfredomalabanan@auth.workhiveph.com', role: 'worker',     experience: 'novice',       worker: 'Wilfredo Malabanan', hive: HIVES.baguio, vw: 1280, vh: 900 },
  { id: 'admin',      label: 'Admin/founder (supervisor, cross-hive)', email: 'pabloaguilar@auth.workhiveph.com', role: 'supervisor', experience: 'experienced', worker: 'Pablo Aguilar',     hive: HIVES.lucena, vw: 1366, vh: 900 },
];
const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';

// Pages whose REAL use requires a deep-link query param (measure them in that state).
const PAGE_QUERY = { 'marketplace-seller-profile.html': '?worker=Bryan%20Garcia' };

// DEPRECATED pages set (platform-health.html + predictive.html were REMOVED 2026-07-01).
const DEPRECATED_PAGES = new Set([]);

const args = process.argv.slice(2);
const HEADED = args.includes('--headed');
const ACCEPT = args.includes('--accept');
const UPDATE_BASELINE = args.includes('--update-baseline');
const PAGE_ONLY = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const PERSONA_ONLY = (() => { const i = args.indexOf('--persona'); return i >= 0 ? args[i + 1] : null; })();
const LIMIT = (() => { const i = args.indexOf('--limit'); return i >= 0 ? parseInt(args[i + 1], 10) : null; })();

const BATTERY_SRC = readFileSync('ufai_battery.js', 'utf8');

async function signIn(context, persona) {
  const page = await context.newPage();
  try {
    await page.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
    const r = await page.evaluate(async ({ email, password, hive, worker, role, surl }) => {
      try {
        const db = window._whSupabaseClient || window.getDb(surl, window.SUPABASE_KEY);
        const { data, error } = await db.auth.signInWithPassword({ email, password });
        localStorage.setItem('wh_active_hive_id', hive);
        localStorage.setItem('wh_last_worker', worker);
        localStorage.setItem('wh_hive_role', role);   // role-gated UI reads this
        return { ok: !error && !!data?.session, err: error ? String(error.message || error) : null };
      } catch (e) { return { ok: false, err: String(e) }; }
    }, { email: persona.email, password: PASSWORD, hive: persona.hive, worker: persona.worker, role: persona.role, surl: SUPABASE_URL });
    return r;
  } catch (e) { return { ok: false, err: String(e).slice(0, 120) }; }
  finally { await page.close().catch(() => {}); }
}

async function walkPage(context, persona, pageFile) {
  const page = await context.newPage();
  await page.setViewportSize({ width: persona.vw, height: persona.vh });
  try {
    await page.goto(`${SEEDER}/workhive/${pageFile}${PAGE_QUERY[pageFile] || ''}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(2200); // settle async render

    // a worker bounced off a role-gated admin surface = the gate held (security-correct).
    const bounced = /index\.html(\?|#|$)/.test(page.url()) && pageFile !== 'index.html';

    // install + boot the authoritative referee, keyed by THIS persona's role/experience.
    let ref = null, err = null;
    try {
      await page.evaluate(`(${BATTERY_SRC})()`);
      await page.evaluate(`(async()=>{ try { await window.__UFAI.boot(); } catch(e){} })()`);
      ref = await page.evaluate(async ({ pid, role, experience }) =>
        await window.__UFAI.referee({ pageId: pid, role, experience }),
        { pid: pageFile.replace('.html', ''), role: persona.role, experience: persona.experience });
    } catch (e) { err = String(e).slice(0, 120); }

    // horizontal overflow at THE PERSONA'S viewport (the field reality for field-tech=390).
    const ov = await page.evaluate(() => {
      const sw = document.documentElement.scrollWidth, cw = document.documentElement.clientWidth;
      return { scrollW: sw, clientW: cw, overflow: sw > cw + 2 };
    }).catch(() => ({ overflow: false }));

    if (!ref) return { pageFile, bounced, err: err || 'referee returned null', floorMajor: -1 };

    const majors = (ref.defects || []).filter(d => d.severity === 'Major' || d.severity === 'Blocker');
    const floor = majors.filter(d => FB2_FLOOR_CHECKS(d.check));     // the persona-delta floor
    const excluded = majors.filter(d => EXCLUDED_CHECK(d.check));    // Arc-D / perf / env owned
    const other = majors.filter(d => !FB2_FLOOR_CHECKS(d.check) && !EXCLUDED_CHECK(d.check)); // any unclassified major → floor too (fail-safe)
    const floorAll = floor.concat(other);
    const byPillar = {};
    for (const d of floorAll) byPillar[d.pillar] = (byPillar[d.pillar] || 0) + 1;
    const secrets = ref.scores && ref.scores.I && ref.scores.I.metrics ? ref.scores.I.metrics.secretExposures : null;
    return {
      pageFile, bounced,
      floorMajor: floorAll.length,
      excludedMajor: excluded.length,
      overflow: ov.overflow,
      byPillar,
      secrets: typeof secrets === 'number' ? secrets : null,
      axeViolations: ref.scores && ref.scores.U && ref.scores.U.metrics && ref.scores.U.metrics.axe ? (ref.scores.U.metrics.axe.violations || 0) : null,
      topDefects: floorAll.slice(0, 8).map(d => `${d.pillar}:${d.check} = ${String(d.measured).slice(0, 70)}`),
      topExcluded: excluded.slice(0, 3).map(d => `${d.check}×`),
    };
  } catch (e) {
    return { pageFile, err: String(e).slice(0, 120), major: -1 };
  } finally { await page.close().catch(() => {}); }
}

async function walkPersona(browser, persona, pages) {
  const context = await browser.newContext({ viewport: { width: persona.vw, height: persona.vh } });
  const si = await signIn(context, persona);
  const rec = { id: persona.id, label: persona.label, role: persona.role, viewport: `${persona.vw}x${persona.vh}`, signIn: si.ok, pages: {}, pass: 0, fix: 0, gated: 0, disp: 0, error: 0 };
  if (!si.ok) { rec.signInErr = si.err; }
  for (const pageFile of pages) {
    const r = await walkPage(context, persona, pageFile);
    let status;
    if (DEPRECATED_PAGES.has(pageFile)) { status = 'disp'; rec.disp++; }
    else if (r.err || r.floorMajor < 0) { status = 'error'; rec.error++; }
    else if (r.bounced) { status = 'gated'; rec.gated++; }          // role-gate held = correct
    else if (r.floorMajor === 0 && (r.secrets === 0 || r.secrets === null)) { status = 'pass'; rec.pass++; }
    else { status = 'fix'; rec.fix++; }
    rec.pages[pageFile] = { status, floorMajor: r.floorMajor, excludedMajor: r.excludedMajor, overflow: !!r.overflow, secrets: r.secrets, axeViolations: r.axeViolations, byPillar: r.byPillar || {}, bounced: !!r.bounced, err: r.err, top: r.topDefects || [], topExcluded: r.topExcluded || [] };
    const mark = { pass: 'OK ', fix: 'FIX', gated: 'gat', disp: 'dep', error: 'ERR' }[status];
    console.log(`  [${persona.id.padEnd(10)}] ${pageFile.padEnd(34)} ${mark}` + (status === 'fix' ? `  floor=${r.floorMajor}${r.secrets ? ' +secrets=' + r.secrets : ''}  ${(r.topDefects || []).slice(0, 2).join(' | ')}` : '') + (r.err ? '  ' + r.err : ''));
  }
  await context.close();
  return rec;
}

(async () => {
  if (!existsSync(RESULTS_SRC)) { console.error(`[FB2] ${RESULTS_SRC} missing — run mine_frontend_ufai_surfaces.py first.`); process.exit(2); }
  const src = JSON.parse(readFileSync(RESULTS_SRC, 'utf8'));
  let pages = Object.keys(src.pages).filter(p => !PAGE_ONLY || p === PAGE_ONLY);
  if (LIMIT) pages = pages.slice(0, LIMIT);
  const personas = PERSONAS.filter(p => !PERSONA_ONLY || p.id === PERSONA_ONLY);

  console.log(`[FB2] browser-CI persona walk — ${personas.length} persona(s) × ${pages.length} page(s) @ ${SEEDER}`);
  const browser = await chromium.launch({ headless: !HEADED });
  // personas run CONCURRENTLY (each its own context; read-only audit → no DB-write collision)
  const records = await Promise.all(personas.map(p => walkPersona(browser, p, pages)));
  await browser.close();

  // ── board ──────────────────────────────────────────────────────────────────
  const perPersona = {};
  let walks = 0, pass = 0, fix = 0, gated = 0, disp = 0, error = 0;
  for (const rec of records) {
    perPersona[rec.id] = { label: rec.label, role: rec.role, viewport: rec.viewport, signIn: rec.signIn, pass: rec.pass, fix: rec.fix, gated: rec.gated, disp: rec.disp, error: rec.error, pages: rec.pages };
    walks += rec.pass + rec.fix + rec.gated + rec.disp + rec.error;
    pass += rec.pass; fix += rec.fix; gated += rec.gated; disp += rec.disp; error += rec.error;
  }
  // live% = (pass + gated) / (walks - disp) — gated is a correct outcome; deprecated excluded.
  const active = walks - disp;
  const live = pass + gated;
  const board = {
    ran: new Date().toISOString(), seeder: SEEDER,
    personas: personas.map(p => p.id),
    pages_per_persona: pages.length,
    totals: { walks, active, pass, fix, gated, disp, error, live, live_pct: active ? Math.round(1000 * live / active) / 10 : 0 },
    per_persona: perPersona,
    fixes: records.flatMap(r => Object.entries(r.pages).filter(([, v]) => v.status === 'fix').map(([pg, v]) => ({ persona: r.id, page: pg, floorMajor: v.floorMajor, overflow: v.overflow, secrets: v.secrets, byPillar: v.byPillar, top: v.top }))),
    errors: records.flatMap(r => Object.entries(r.pages).filter(([, v]) => v.status === 'error').map(([pg, v]) => ({ persona: r.id, page: pg, err: v.err }))),
  };

  console.log('\n' + '='.repeat(64));
  console.log('FB2 — BROWSER-CI PERSONA WALK');
  console.log('='.repeat(64));
  for (const rec of records) {
    console.log(`  ${rec.id.padEnd(11)} signIn=${rec.signIn ? 'OK' : 'FAIL ' + (rec.signInErr || '')}  pass=${rec.pass} fix=${rec.fix} gated=${rec.gated} disp=${rec.disp} err=${rec.error}`);
  }
  console.log(`  TOTAL: ${live}/${active} live-or-gated = ${board.totals.live_pct}%  (fix=${fix}, err=${error}, disp=${disp})`);
  if (board.fixes.length) {
    console.log(`\n  FIX findings (${board.fixes.length}):`);
    for (const f of board.fixes.slice(0, 40)) console.log(`    [${f.persona}] ${f.page}  floor=${f.floorMajor}${f.secrets ? ' +secrets' : ''}  ${(f.top || []).slice(0, 3).join(' | ')}`);
  }
  if (board.errors.length) {
    console.log(`\n  ERRORS (${board.errors.length}):`);
    for (const e of board.errors.slice(0, 20)) console.log(`    [${e.persona}] ${e.page}  ${e.err}`);
  }

  // ── forward-only ratchet ─────────────────────────────────────────────────────
  if (ACCEPT) {
    const cur = { live, pass, gated, per_persona: Object.fromEntries(records.map(r => [r.id, { pass: r.pass, gated: r.gated }])) };
    if (UPDATE_BASELINE || !existsSync(BASELINE)) {
      writeFileSync(BASELINE, JSON.stringify({ ...cur, set: new Date().toISOString() }, null, 2));
      console.log(`\n[FB2] baseline ${UPDATE_BASELINE ? 'UPDATED' : 'created'}: live>=${live} (pass>=${pass}, gated>=${gated})`);
    } else {
      const base = JSON.parse(readFileSync(BASELINE, 'utf8'));
      let failed = false;
      if (live < base.live) { console.error(`\n[FB2] RATCHET FAIL: live ${live} < baseline ${base.live}`); failed = true; }
      for (const [id, b] of Object.entries(base.per_persona || {})) {
        const c = cur.per_persona[id];
        if (c && (c.pass + c.gated) < (b.pass + b.gated)) { console.error(`[FB2] RATCHET FAIL: persona ${id} live ${c.pass + c.gated} < baseline ${b.pass + b.gated}`); failed = true; }
      }
      writeFileSync(BOARD, JSON.stringify(board, null, 2));
      if (failed) process.exit(1);
      console.log(`\n[FB2] ratchet OK: live ${live} >= ${base.live}`);
    }
  }

  writeFileSync(BOARD, JSON.stringify(board, null, 2));
  console.log(`\n  -> wrote ${BOARD}`);
})();
