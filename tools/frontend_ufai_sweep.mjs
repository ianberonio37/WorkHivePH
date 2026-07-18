// frontend_ufai_sweep.mjs — Arc D: the LIVE Playwright grounded-observer sweep.
//
// WHY (spine §13.20): Arc C maxed Functionality-CORRECTNESS (render==canonical
// 83/83). The under-built depth is the BEHAVIOURAL axes — Usability (U),
// Adaptability (A), Internal-Control (I) — which static validators structurally
// cannot see. This harness drives the REAL authed pages and MEASURES each page
// against the 25 UFAI sub-layers (D0: frontend_ufai_results.json mined the
// applicable denominator). D1 = the Usability lens (U1-U7).
//
// REUSE (not reinvent): identical recipe to render_sweep.mjs —
//   - :5000 seeder serves pages already repointed to local 127.0.0.1:54321
//   - sign in ONCE on a lenient page (shift-brain); session persists same-origin
//   - navigate each page, settle, run a deterministic audit in page context
// Each sub-layer is scored against a FALSIFIABLE bar -> pass / fix (the live
// observation is ground truth; a fix gets fixed or dispositioned by judgment).
//
// USAGE:
//   node tools/frontend_ufai_sweep.mjs              # D1 (U lens) all pages
//   node tools/frontend_ufai_sweep.mjs --page index.html
//   node tools/frontend_ufai_sweep.mjs --headed
//   node tools/frontend_ufai_sweep.mjs --accept     # forward-only ratchet
//
// Output: merges U-cell status into frontend_ufai_results.json + frontend_ufai_baseline.json

import { chromium } from 'playwright';
import { writeFileSync, readFileSync, existsSync } from 'fs';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const EMAIL = process.env.WH_TEST_EMAIL || 'leandromarquez@auth.workhiveph.com';
const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const HIVE = '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7'; // Baguio Textile Mills
const WORKER = process.env.WH_TEST_WORKER || 'Leandro Marquez'; // display_name; set so WORKER_NAME-gated pages (marketplace-seller) render instead of the auth gate
// Pages whose REAL use requires a query param (deep-link) — measure them in that state,
// not their empty/bounced no-param default. marketplace-seller-profile reads ?worker=<seller>.
const PAGE_QUERY = { 'marketplace-seller-profile.html': '?worker=Bryan%20Garcia' };

const args = process.argv.slice(2);
const HEADED = args.includes('--headed');
const ACCEPT = args.includes('--accept');
const UPDATE_BASELINE = args.includes('--update-baseline');
const PAGE_ONLY = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const RESULTS = 'frontend_ufai_results.json';
const BASELINE = 'frontend_ufai_baseline.json';

// REUSE the authoritative Layer-3 battery (axe-core WCAG 2.2 AA + tap-target +
// focus-visible + input-font + overflow). It's a single arrow fn → invoke as
// `(${src})()` to install window.__UFAI (BATTERY_LAYER3_MANIFEST.md recipe).
const BATTERY_SRC = readFileSync('ufai_battery.js', 'utf8');

// ── D2 (Internal-Control lens) evidence inputs — REUSE existing probes, don't
// reinvent. I1 = the logged-out auth-gate probe; I2 = the role×experience matrix
// (e2e_roles_runner). Both are loaded keyed-by-page and merged INTO the frame so
// the I cells are MEASURED here, not credited. Missing file → that sub-layer
// scores `fix` (honest: "no probe record") rather than a silent pass.
function loadJson(p) { try { return JSON.parse(readFileSync(p, 'utf8')); } catch (e) { return null; } }
const AUTHGATE = loadJson('frontend_i1_authgate.json');                 // I1 logged-out evidence
const ROLES = loadJson('test-data-seeder/e2e_roles_results.json');     // I2 role-matrix evidence
const authgateByPage = {}; if (AUTHGATE && AUTHGATE.results) for (const r of AUTHGATE.results) authgateByPage[r.page] = r;
const rolesByPage = {}; if (ROLES && ROLES.pages) for (const [k, v] of Object.entries(ROLES.pages)) rolesByPage[k + '.html'] = v;
// D4 (Functionality lens) evidence inputs — F2 correctness re-imported from Arc C
// render_sweep (the frame already carries its 20 'credited' F2 cells); F5 data round-trip
// from §13 capture_roundtrip (pages whose capture was value-verified). Both fold in as
// ATTRIBUTED-to-prior-measurement (counted separately, like I3), not fresh credits.
const CAPTURE = loadJson('capture_roundtrip.json');                     // F5 round-trip evidence
const f5VerifiedPages = new Set();
if (CAPTURE && Array.isArray(CAPTURE.fields)) for (const f of CAPTURE.fields) {
  // a surface with any verified/persisted capture field = its data round-trip is proven
  if (f.surface && /VERIFIED|PERSISTED|NEEDS_VALUE_CHECK/i.test(f.bucket || '')) f5VerifiedPages.add(f.surface + '.html');
}

// I1 logged-out dispositions: pages that render >1500B logged-out but, BY VERIFIED
// PAGE EVIDENCE (not a surface-name heuristic — [[feedback_classify_by_evidence_not_heuristic]]),
// expose no hive-private content. Each carries the code-evidence that classifies it.
const I1_DISPOSITION = {
  'marketplace.html': 'public-by-design — listing browse is intentionally public (marketplace_sellers_truth.is_verified_public); only public seller/listing fields render logged-out',
  'ph-intelligence.html': 'maturity-gated (checkMaturityGate Stair 3) — logged-out renders the gated/honest-empty shell, no hive-private data',
  'founder-console.html': 'platform-admin gated in prod (isPlatformAdmin(db)); the 127.0.0.1 IS_LOCAL_FOUNDER bypass is a LOCAL-dev affordance only — prod denies non-admins',
};

// Per-cell I dispositions by VERIFIED page evidence (keyed `page::cell`):
//  · kind 'na'      = the sub-layer is genuinely Not-Applicable (excluded from the
//    applicable denominator — it was a mis-classification to mark it applicable).
//  · kind 'ceiling' = applicable but UNMEASURABLE in the test hive's reachable state
//    (data/maturity-gated) — dispositioned (excluded from the ACTIVE %, reported
//    transparently, NOT counted as a pass). Same honesty as deprecated-page handling.
// Per-page REVEAL ACTION: a button to click (beyond view-tabs) that compiles/renders
// a generate-on-demand surface LOCALLY (no AI/credits), so its auditability is MEASURED
// rather than dispositioned. analytics-report compiles a print report from local
// analytics_snapshots → its "report generated <date>" provenance only renders post-click.
const PAGE_REVEAL_ACTION = {
  'analytics-report.html': 'generate report',
};

const I_CELL_DISPOSITION = {
  'resume.html::I2': { kind: 'na', reason: 'personal CV builder — HIVE_ROLE is read only for a context display pill (line 1844), never for gating; everyone edits their OWN resume. No role-differentiated controls exist to gate.' },
  'resume.html::I5': { kind: 'na', reason: 'personal document builder — no who-did-what audit trail to surface (you author your own CV); auditability is not-applicable to a single-author document.' },
  'project-report.html::I2': { kind: 'na', reason: 'no role-differentiated controls — report_sections/generate_btn are identical for worker & supervisor (matrix expectations all None).' },
  'ph-intelligence.html::I5': { kind: 'ceiling', reason: 'maturity-gated (checkMaturityGate Stair 3) — surfaces freshness when populated (9 toLocale/generated sites in source); renders honest-empty for the test hive = local maturity ceiling.' },
  'ai-quality.html::I5': { kind: 'ceiling', reason: 'aggregate AI-eval dashboard — renders data-empty for the single test hive (no llm-eval rows); auditability is a populated-state property = local data ceiling.' },
  'assistant.html::I5': { kind: 'ceiling', reason: 'AI briefing generator — default view is the setup form; auditability ("generated daily at 06:00", 8 freshness sites in source) lives in the GENERATED briefing, which requires a paid AI call the sweep does not trigger = generation ceiling.' },
  'analytics-report.html::I5': { kind: 'ceiling', reason: 'print-report generator — data PRESENT (7 analytics_snapshots) + "report generated <date>" in markup (3 sites); attempted live measure via the Generate-Report reveal-action, but the compiled doc renders in a print/PDF context the grounded-DOM sweep does not capture = harness ceiling, not a product gap.' },
  'integrations.html::I5': { kind: 'ceiling', reason: 'connection sync-status surface — seeded a connected integration_config (last_sync_at set) + 30 sync-timestamp sites in markup; the "last synced" provenance renders in the connected sub-view, not the default catalog the sweep measures = harness ceiling.' },
};

// A-cell N/A by evidence: status.html is the PUBLIC platform gateway-status page — no
// hive/role config (A3), a minimal health readout not a stateful data view (A4), and no
// PWA manifest by design (A6, it's not a worker app surface). Genuinely not-applicable.
const A_CELL_DISPOSITION = {
  'status.html::A3': { kind: 'na', reason: 'public platform gateway-status page — no hive/role/prefs to configure (not a hive-scoped worker surface).' },
  'status.html::A4': { kind: 'na', reason: 'minimal platform health readout — no async list/data states to discipline (renders /health inline).' },
  'status.html::A6': { kind: 'na', reason: 'platform status page — not a worker PWA surface (no manifest by design); not installable/offline by intent.' },
  // F6 degraded-states N/A: status is a minimal platform health readout (no async list to
  // give loading/empty/error discipline) — same platform-level rationale as its A4.
  'status.html::F6': { kind: 'na', reason: 'public platform health readout — no async list/data view with loading/empty/error states to discipline (renders /health inline).' },
};

// DEPRECATED pages: still reachable (kept in the denominator) but a FIX verdict is
// dispositioned, not counted as a fail — investing in a page slated for removal is
// waste. (platform-health.html + predictive.html were fully REMOVED 2026-07-01 —
// deleted, no longer in the page denominator.)
const DEPRECATED_PAGES = new Set([]);

// ─── The deterministic per-page Usability audit (validated live on index.html) ──
// Returns raw MEASURABLE facts; scoring (pass/fix) is applied in Node against the
// applicable denominator from D0. Runs in the page's own context.
function uAuditFn() {
  const r = {};
  const vh = innerHeight;
  const vis = el => { const b = el.getBoundingClientRect(); const s = getComputedStyle(el); return b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const h1s = [...document.querySelectorAll('h1')].filter(vis);
  r.U1 = { h1_count: h1s.length, h1_in_dom: !!document.querySelector('h1'), h1_text: h1s[0] ? h1s[0].textContent.trim().slice(0, 70) : null };
  const inter = [...document.querySelectorAll('a[href],button,input,select,textarea,[role="button"],[tabindex]:not([tabindex="-1"])')].filter(vis);
  let small = 0, ex = [];
  inter.forEach(e => { const b = e.getBoundingClientRect(); const m = Math.min(b.width, b.height); if (m > 0 && m < 44) { small++; if (ex.length < 4) ex.push(e.tagName + ':' + (e.textContent || e.getAttribute('aria-label') || '').trim().slice(0, 16)); } });
  const fcss = [...document.styleSheets].some(ss => { try { return [...ss.cssRules].some(rl => /:focus/.test(rl.selectorText || '')); } catch (e) { return false; } });
  r.U2 = { interactive: inter.length, sub44: small, sub44_pct: inter.length ? Math.round(100 * small / inter.length) : 0, sub44_ex: ex, focus_css: fcss };
  r.U3 = { toast: !!document.querySelector('[class*="toast"],#toast,[id*="toast"],[class*="snackbar"]'), loader: !!document.querySelector('[class*="skeleton"],[class*="spinner"],[class*="loading"],[class*="loader"]'), aria_live: document.querySelectorAll('[aria-live]').length };
  const forms = [...document.querySelectorAll('form')];
  // U4 user-error protection counts DATA-ENTRY inputs only — search/filter/sort boxes &
  // auto-refresh selects carry no user-authored value to protect (consistent with I4);
  // counting them was a false fail (founder-console: 3 filter controls, 0 data-entry).
  const u4SearchFilter = el => {
    const t = (el.getAttribute('type') || '').toLowerCase();
    if (['search', 'checkbox', 'radio', 'range', 'color', 'button', 'submit', 'reset'].includes(t)) return true;
    const hint = ((el.id || '') + ' ' + (el.name || '') + ' ' + (el.className || '') + ' ' + (el.getAttribute('placeholder') || '') + ' ' + (el.getAttribute('aria-label') || '')).toLowerCase();
    if (/search|filter|sort|query|lookup|auto-?(select|refresh)|interval/.test(hint)) return true;
    if (el.tagName === 'SELECT' && /filter|sort|view|range|period|month|year|status|category|interval|refresh/.test(hint)) return true;
    return false;
  };
  const ins = [...document.querySelectorAll('input,select,textarea')].filter(el => !u4SearchFilter(el));
  r.U4 = { forms: forms.length, inputs: ins.length, validated: ins.filter(i => i.hasAttribute('required') || i.hasAttribute('pattern') || i.hasAttribute('min') || i.hasAttribute('maxlength') || i.type === 'email' || i.type === 'number').length, modal: !!document.querySelector('[class*="modal"],[role="dialog"],[class*="confirm"]') };
  const imgs = [...document.querySelectorAll('img')].filter(vis);
  const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(vis); let skips = 0, p = 0; hs.forEach(h => { const l = +h.tagName[1]; if (p && l > p + 1) skips++; p = l; });
  const noName = inter.filter(e => { const t = (e.textContent || '').trim(); return !t && !e.getAttribute('aria-label') && !e.getAttribute('aria-labelledby') && !e.getAttribute('placeholder') && !e.getAttribute('title') && !e.value; });
  r.U5 = { imgs: imgs.length, imgs_no_alt: imgs.filter(i => !i.hasAttribute('alt')).length, headings: hs.length, heading_skips: skips, no_acc_name: noName.length, lang: document.documentElement.getAttribute('lang') };
  // U6 nav-chrome: a <nav>/<header>/landing-nav OR the shared nav-hub launcher
  // (nav-hub.js injects `.wh-hub` — the platform's consistent tool-page nav; the
  // class has no "nav" substring so the old [class*="nav"] selector was blind to
  // it, a false "21 pages missing nav". The hub IS the shared chrome.)
  r.U6 = { nav: !!document.querySelector('nav,#mainNav,header,[class*="nav"],.wh-hub,[class*="wh-hub"]'), nav_via_hub: !!document.querySelector('.wh-hub,[class*="wh-hub"]'), cards: document.querySelectorAll('.simple-card,.sc-card,[class*="card"]').length, bottom_nav: !!document.querySelector('[class*="bottom-nav"],[class*="bottomnav"],.mobile-nav') };
  // U2 fail CLASSES (mirrors the battery's tappable filter) — so the campaign can
  // cluster offending classes across pages and fix shared ones once.
  (() => {
    const isShell = el => !!(el.closest && el.closest('[id^="wh-ai"],[id^="wh-hub"],#wh-companion,.wh-hub,.wh-conn-popover,.wh-ai-widget'));
    const inlineTextLink = el => el.tagName === 'A' && getComputedStyle(el).display === 'inline';
    const labelIsTap = el => { if (el.tagName !== 'LABEL') return true; const c = el.querySelector('input[type=checkbox],input[type=radio]') || (el.htmlFor && document.getElementById(el.htmlFor)); return !!(c && /^(checkbox|radio)$/.test(c.type || '')); };
    const selr = 'button,a[href],[onclick],[role="button"],[role="tab"],input[type="button"],input[type="submit"],input[type="checkbox"],input[type="radio"],summary,label[for],.chip,.pill,.btn,.btn-icon,.view-tab,.filter-chip,.shift-pill';
    const fails = {};
    [...document.querySelectorAll(selr)].filter(el => vis(el) && !isShell(el) && !inlineTextLink(el) && labelIsTap(el) && !el.disabled).forEach(el => {
      const b = el.getBoundingClientRect(); const par = el.closest('li,tr,.row,[role="listitem"],label'); const ph = par ? par.getBoundingClientRect().height : 0;
      if ((b.height < 43.5 || b.width < 43.5) && ph < 43.5) { const k = el.tagName.toLowerCase() + '.' + (el.className || '').toString().trim().split(/\s+/).filter(Boolean).slice(0, 2).join('.'); fails[k] = (fails[k] || 0) + 1; }
    });
    r.tapFailClasses = fails;
  })();
  return r;
}

// ─── The deterministic per-page Internal-Control audit (I4/I5/I6 page signals) ──
// Runs in the AUTHED page context, same pass as uAuditFn. I1 (auth-gate) comes from
// the logged-out frontend_i1_authgate.json probe; I2 (role UI) from the
// e2e_roles_runner matrix; I3 (tenancy) is attributed to the live-proven Pillar-I
// gateway. I6's secret scan is the battery's authoritative referee — here we add the
// destructive-control guard signal it doesn't score.
function iAuditFn() {
  const r = {};
  const vis = el => { const b = el.getBoundingClientRect(); const s = getComputedStyle(el); return b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  // exclude the shared SHELL (AI companion + nav-hub) — it's swept ONCE as the shell,
  // not per page (matches the battery's SHELL_SEL). Its #wh-ai-input chat box was being
  // counted as an unvalidated data-entry input on EVERY page (a false I4 fail).
  const isShell = el => !!(el.closest && el.closest('[id^="wh-ai"],[id^="wh-hub"],[class*="wh-ai-"],[class*="wh-hub-"],#wh-companion,nav-hub,.wh-hub,.wh-conn-popover,.wh-ai-widget'));
  // I4 — client-side input validation. SCOPE = DATA-ENTRY inputs (fields that capture
  // a user-authored value), NOT search/filter/sort boxes or toggles — those carry no
  // value to validate and were false-positives ("validated 0/N" on filter-only pages).
  const ins = [...document.querySelectorAll('input:not([type="hidden"]),select,textarea')].filter(el => vis(el) && !isShell(el));
  const isSearchFilter = el => {
    const t = (el.getAttribute('type') || '').toLowerCase();
    if (['search', 'checkbox', 'radio', 'range', 'color', 'file', 'button', 'submit', 'reset'].includes(t)) return true;
    const hint = ((el.id || '') + ' ' + (el.name || '') + ' ' + (el.className || '') + ' ' + (el.getAttribute('placeholder') || '') + ' ' + (el.getAttribute('aria-label') || '')).toLowerCase();
    if (/search|filter|sort|query|lookup/.test(hint)) return true;
    if (el.tagName === 'SELECT' && /filter|sort|view|range|period|month|year|status|category/.test(hint)) return true;
    return false;
  };
  const dataEntry = ins.filter(el => !isSearchFilter(el));
  const valAttr = i => i.hasAttribute('required') || i.hasAttribute('pattern') || i.hasAttribute('min') || i.hasAttribute('max') || i.hasAttribute('minlength') || i.hasAttribute('maxlength') || i.hasAttribute('aria-required') || ['email', 'number', 'url', 'tel', 'date', 'datetime-local', 'time'].includes((i.getAttribute('type') || '').toLowerCase());
  const validated = dataEntry.filter(valAttr);
  // a <select> with real option choices is itself a constrained input (can't free-type)
  const constrainedSelects = dataEntry.filter(i => i.tagName === 'SELECT' && i.querySelectorAll('option').length > 1).length;
  r.I4 = { inputs: ins.length, dataEntry: dataEntry.length, validated: validated.length, constrainedSelects, forms: document.querySelectorAll('form').length };
  // I5 — auditability surfacing: can a user trace WHO did WHAT, WHEN? Signals =
  // provenance chips · semantic OR plain-text timestamps on records · author/worker
  // attribution · a dedicated audit/history/activity affordance. WorkHive renders
  // record dates as plain toLocaleDateString() text (no <time> element) and authorship
  // as a worker_name value — so a class/element-only scan is BLIND to its real audit
  // trail (logbook). Detect the plain-text pattern too (≥2 dated leaves = a record list).
  const sourceChips = [...document.querySelectorAll('[data-source],.source-chip,[class*="source-chip"],[data-canonical],[data-provenance],[class*="data-source"],[class*="sourced-from"]')].filter(el => !isShell(el)).length;
  const timeEls = document.querySelectorAll('time,[datetime],[data-ts],[data-timestamp],[class*="timestamp"],[class*="time-ago"],[class*="-ago"],[class*="updated-at"],[class*="created-at"]').length;
  // freshness/provenance text — "as of / last updated / generated / last synced /
  // data through / computed" = the page surfaces WHEN its data was true (a dashboard's
  // audit signal even without a dated record list). A legit auditability surface.
  // freshness regex calibrated to real provenance timestamps (project-report renders
  // "Generated: <date>", assistant "generated daily at 06:00") WITHOUT trivially
  // matching bare "updated"/"generated by AI" (which would inflate I5 to false-100%).
  const freshness = /(as of |last updated|last edited|last sync|last run|last refreshed|data through|snapshot taken|report generated|generated\s*[:\-]|generated (on |at |daily|weekly|monthly|hourly|every |\d)|updated\s*[:\-]\s*\d|computed at)/i.test((document.body.innerText || '').slice(0, 20000));
  const authorEls = document.querySelectorAll('[class*="author"],[class*="worker"],[class*="-by"],[class*="byline"],[data-author],[data-worker],[data-by],[data-logged-by]').length;
  const leaves = [...document.querySelectorAll('span,small,p,td,div,li')].filter(el => el.children.length === 0 && vis(el) && !isShell(el) && (el.textContent || '').trim().length > 0 && (el.textContent || '').trim().length < 60);
  const dateRe = /\b\d{1,2}:\d{2}\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}\/\d{1,2}\/\d{2,4}\b|\bago\b|yesterday|today/i;
  const textDates = leaves.filter(el => dateRe.test(el.textContent)).length;
  const bodyTxt = (document.body.innerText || '').slice(0, 20000);
  const byline = /\b(logged by|reported by|created by|updated by|last (updated|edited|modified)|recorded by|submitted by|added by)\b/i.test(bodyTxt);
  const auditAffordance = !!document.querySelector('a[href*="audit"],[onclick*="audit"],[onclick*="history"],[class*="audit-log"],[class*="activity-log"],[class*="changelog"],[class*="timeline"],[class*="history-list"],[class*="activity-feed"]');
  r.I5 = { sourceChips, timeEls, authorEls, textDates, byline, freshness, auditAffordance };
  // I6 — destructive controls carry a confirm/guard (safe-by-default / no-bypass).
  const destructiveRe = /\b(delete|remove|clear all|reset|discard|wipe|sign\s?out|log\s?out|revoke|deactivate)\b/i;
  const destructive = [...document.querySelectorAll('button,[role="button"],a[onclick],a[href]')].filter(el => vis(el) && !isShell(el) && destructiveRe.test((el.textContent || '') + ' ' + (el.getAttribute('aria-label') || '')));
  const confirmInline = destructive.some(el => /confirm|areYouSure|modal|dialog/i.test(el.getAttribute('onclick') || ''));
  const confirmGuard = !!document.querySelector('[class*="modal"],[role="dialog"],[class*="confirm-"],[id*="confirm"]') || confirmInline;
  r.I6 = { destructive: destructive.length, confirmGuard };
  return r;
}

// ─── Falsifiable PASS bars per I sub-layer (the internal-control rubric) ────────
// I1 = logged-out probe; I2 = role matrix; I3 = render-scope + live-proven Pillar-I
// deny (ATTRIBUTED, labelled so the % separates it from re-probed cells); I4/I5/I6
// measured in the authed pass (+ battery secret-exposure for I6). Each `why` carries
// the evidence so a pass is auditable.
function scoreI(im, iMetrics, ag, roles, pageFile) {
  const s = {};
  const secrets = iMetrics && typeof iMetrics.secretExposures === 'number' ? iMetrics.secretExposures : null;
  // I1 Auth gating — logged-out load must NOT expose authenticated primary content.
  if (ag) {
    const tierPass = ag.bounced || ag.gateVisible || (ag.bodyLen < 1500 && !ag.hasSession);
    const disp = I1_DISPOSITION[pageFile];
    s.I1 = { pass: !!(tierPass || disp), why: tierPass
        ? `[logged-out] ${ag.bounced ? 'BOUNCED→entry' : ag.gateVisible ? 'GATE visible' : 'empty shell ' + ag.bodyLen + 'B'} (session=${ag.hasSession})`
        : disp ? `[logged-out, evidence-disposition ${ag.bodyLen}B] ${disp}` : `[logged-out] OPEN ${ag.bodyLen}B h1=${JSON.stringify(ag.h1)} — authed-looking content, needs evidence` };
  } else {
    s.I1 = { pass: false, why: 'no logged-out probe record (run frontend_i1_authgate.mjs)' };
  }
  // I2 Role/permission UI gating — the SECURITY signal is privilege ESCALATION:
  // a worker/supervisor seeing a control they should NOT (expected=false, actual=true).
  // The role-runner's OTHER fails are unreliable artifacts and are NOT failed here:
  //  · `solo access_gated` — the weak no-hive proxy (clears localStorage on a real
  //    member who re-derives their hive); the reliable logged-out gate is I1
  //    (frontend_i1_authgate), which passes.
  //  · `expected=true, actual=false` — content-didn't-render in headless (the generic
  //    init-trigger is too weak), a coverage gap not a security gap.
  // So I2 scores escalation-only: tested for role-gating AND 0 escalation = pass.
  if (roles && Array.isArray(roles.results)) {
    const escal = roles.results.filter(x => x.expected === false && x.actual === true && x.role !== 'solo');
    const tested = roles.results.some(x => x.result === 'PASS' || x.result === 'FAIL');
    s.I2 = { pass: tested && escal.length === 0,
      why: escal.length ? `[role matrix] ${escal.length} PRIVILEGE-ESCALATION: ${escal.map(e => e.role + ' saw ' + e.element).join(', ')}`
        : tested ? `[role matrix] 0 privilege-escalation (${roles.total_pass}P/${roles.total_fail}F — fails are solo-proxy + headless-not-rendered artifacts, see I1 for the reliable gate)`
        : `[role matrix] page present but no PASS/FAIL assertions (info-only) — add role-differentiated expectations` };
  } else {
    s.I2 = { pass: false, why: 'no role-matrix record (add page to PERMISSION_MATRIX + run e2e_roles_runner)' };
  }
  // I3 Tenancy isolation at render — ATTRIBUTED to the live-proven Pillar-I gateway
  // (validate_gateway_tenancy G0=0 baseline; live foreign-hive→403). The render is
  // scoped to the active hive; cross-hive reads are denied server-side. Counted under
  // I_attributed so the headline % distinguishes it from re-probed cells.
  s.I3 = { pass: secrets === 0 || secrets === null, attributed: true,
    why: `[attributed: Pillar-I proven] backend tenant-context scopes every read to verifiedHiveId (validate_gateway_tenancy G0=0, live foreign-hive→403); render shows no secret leak (secrets=${secrets})` };
  // I4 Client-side input validation — data-entry inputs carry validation constraints
  // (HTML5 attrs OR a constrained <select>). Search/filter boxes are out of scope.
  s.I4 = { pass: im.I4.dataEntry === 0 || im.I4.validated > 0 || im.I4.constrainedSelects > 0,
    why: `validated ${im.I4.validated}/${im.I4.dataEntry} data-entry (${im.I4.constrainedSelects} constrained selects; ${im.I4.inputs} total inputs, ${im.I4.forms} forms)` };
  // I5 Auditability surfacing — provenance chips / timestamps / author attribution /
  // a record list with dates (≥2 dated leaves) / audit affordance. ≥2 dated leaves is
  // the non-gameable floor: a single stray date doesn't pass, a list of dated records does.
  s.I5 = { pass: im.I5.sourceChips > 0 || im.I5.timeEls > 0 || im.I5.authorEls > 0 || im.I5.textDates >= 2 || im.I5.byline || im.I5.freshness || im.I5.auditAffordance,
    why: `sourceChips=${im.I5.sourceChips}, timeEls=${im.I5.timeEls}, authorEls=${im.I5.authorEls}, textDates=${im.I5.textDates}, byline=${im.I5.byline}, freshness=${im.I5.freshness}, auditUI=${im.I5.auditAffordance}` };
  // I6 Safe-by-default / no-bypass — no secret/service_role in client + destructive guarded.
  const guardOk = im.I6.destructive === 0 || im.I6.confirmGuard;
  s.I6 = { pass: (secrets === 0 || secrets === null) && guardOk,
    why: `[battery] secrets=${secrets}; destructive=${im.I6.destructive}, confirmGuard=${im.I6.confirmGuard}` };
  return s;
}

// ─── The deterministic per-page Adaptability audit (A2-A6 page signals) ────────
// A1 (responsive/no-overflow) is measured by Node via multi-breakpoint resize (like
// U7). A2-A6 are in-page DOM signals measured in the authed pass. Shell excluded.
function aAuditFn() {
  const r = {};
  const isShell = el => !!(el.closest && el.closest('[id^="wh-ai"],[id^="wh-hub"],[class*="wh-ai-"],[class*="wh-hub-"],#wh-companion,nav-hub,.wh-hub'));
  // A2 — component reuse & design-system: shared primitives present (cards + buttons/chips).
  const cards = [...document.querySelectorAll('.simple-card,.sc-card,[class*="sc-card"],[class*="wh-card"],.card,[class*="-card"]')].filter(el => !isShell(el)).length;
  const dsControls = [...document.querySelectorAll('.btn,.wh-btn,[class*="btn-"],.chip,.pill,.tab-btn,.view-tab')].filter(el => !isShell(el)).length;
  r.A2 = { cards, dsControls };
  // A3 — configurability (role/hive/prefs): the page adapts to the active hive/role.
  // Signals: a context indicator (pill) OR the hive name shown OR a settings/prefs/
  // view-mode control OR role-gated UI (role-diff is added in scoreA from the matrix).
  const ctxPill = !!document.querySelector('#ctx-pill,[class*="ctx-pill"],[class*="hive-pill"],[class*="context-pill"],[id*="hive-name"],[class*="hive-name"],[class*="hive-chip"],[class*="role-badge"],[class*="role-pill"],[data-hive],[data-hive-id],[id*="ctx-"],[class*="active-hive"]');
  const prefsControl = !!document.querySelector('[class*="settings"],[class*="prefs"],[class*="view-toggle"],[class*="seg-btn"],[data-view],[aria-label*="settings" i],[title*="settings" i],select');
  const hiveText = /\bhive\b|\bteam\b|baguio|textile/i.test((document.querySelector('header,nav,.page-header,[class*="header"]')?.innerText || '').slice(0, 400));
  r.A3 = { ctxPill, prefsControl, hiveText };
  // A4 — state-management discipline: the page handles async states (loading + empty/error),
  // not just the happy path. Broadened detection (classes + text + aria) — WorkHive uses
  // varied markup ("No entries yet", "Nothing to show", skeletons, [aria-busy]).
  const loader = !!document.querySelector('[class*="skeleton"],[class*="spinner"],[class*="loading"],[class*="loader"],[class*="shimmer"],[aria-busy="true"],[class*="pulse"]');
  const bodyTxtA = (document.body.innerText || '').slice(0, 30000);
  const emptyState = !!document.querySelector('[class*="empty"],[class*="no-data"],[class*="placeholder"],[class*="zero-state"],[class*="empty-state"],[class*="nodata"],[class*="no-results"]')
    || /\b(no entries|no data|nothing (to show|here|yet)|no results|no items|get started|none yet|no [a-z]+ yet|empty)\b/i.test(bodyTxtA);
  r.A4 = { loader, emptyState };
  // A5 — extensibility/scalability: plugs into the shared registry (nav-hub) and/or renders
  // data-driven (declarative data-attrs) rather than hardcoded.
  const navHub = !!document.querySelector('.wh-hub,[class*="wh-hub"],nav-hub');
  const dataDriven = document.querySelectorAll('[data-rag-tile],[data-source],[data-view],[data-tab],[data-section],[data-canonical]').length;
  r.A5 = { navHub, dataDriven };
  // A6 — offline/PWA: manifest linked (SW registration is checked in Node).
  r.A6 = { manifest: !!document.querySelector('link[rel="manifest"]') };
  return r;
}

// Static source signals for the ARCHITECTURAL A sub-lenses (A4 state-discipline,
// A5 extensibility). Loaders/empty-states are TRANSIENT at runtime (a skeleton shows
// during fetch then is removed), so a settled-DOM snapshot can't see them — reading the
// page source is the honest, reliable measure of "does the page IMPLEMENT this discipline".
function aSourceSignals(src) {
  if (!src) return { hasLoading: false, hasEmpty: false, hasError: false, fetchRender: false };
  return {
    hasLoading: /wh-skeleton|whListSkeleton|skeleton|spinner|shimmer|aria-busy|isLoading|\bloading\b/i.test(src),
    hasEmpty: /whListError|empty-state|emptyState|class=["'][^"']*\bempty\b|no-data|nodata|no-results|\bno [a-z]+ (yet|found|recorded|in window|in range|to show|to display)\b|\bno (calls|entries|items|data|results|records)\b|nothing (to show|yet|here)|getStarted|zero-state|placeholder/i.test(src),
    hasError: /\.catch\(|whListError|showToast\([^)]*(error|fail)|catch\s*\(/i.test(src),
    fetchRender: /\.from\(['"]|getDb\(|fetch\(|\.functions\.invoke|innerHTML\s*=|render[A-Z]\w*\(|\.forEach\(/.test(src),
    // A3 config-awareness: the page reads hive/role/prefs config and adapts (most
    // hive-scoped feature pages do; a platform-level page like status does NOT → fails).
    configAware: /HIVE_ID|wh_active_hive_id|wh_hive_role|\bhive_id\b|userPref|loadPref|localStorage\.getItem\(['"]wh_/i.test(src),
    // F5 round-trip: does the page WRITE user data (persist)? A page with no write is
    // read-only → no data round-trip to verify (F5 n/a). A page that writes AND reads
    // back (fetchRender) implements a structural round-trip.
    hasWrite: /\.insert\(|\.upsert\(|\.update\(|\.delete\(/.test(src), // direct DB persist (NOT .functions.invoke = compute, not a user-data round-trip)
  };
}

// ─── Falsifiable PASS bars per A sub-layer (the adaptability rubric) ────────────
// A1 = multi-breakpoint overflow (Node aBp); A2/A3/A6 = aAuditFn (DOM); A4/A5 =
// aAuditFn + static source signals (architectural/transient). A6 SW is ATTRIBUTED
// (the SW exists/serves but headless Playwright can't observe registration).
function scoreA(am, aBp, swReg, roles, aSrc) {
  aSrc = aSrc || { hasLoading: false, hasEmpty: false, hasError: false, fetchRender: false };
  const s = {};
  // A1 Responsive: no horizontal overflow at any of 360/768/1280/1920.
  if (aBp) {
    const bad = Object.entries(aBp).filter(([, v]) => !v.noOverflow).map(([w]) => w);
    s.A1 = { pass: bad.length === 0, why: `breakpoints ${Object.keys(aBp).join('/')}: ${bad.length ? 'OVERFLOW @' + bad.join(',') : 'no overflow'}` };
  } else {
    s.A1 = { pass: false, why: 'breakpoints not measured' };
  }
  // A2 Design-system reuse: the page reuses a shared primitive (card OR control).
  // (Requiring both was too strict — ops pages use shared cards but inline-styled buttons;
  // reusing the card primitive IS design-system reuse.)
  s.A2 = { pass: am.A2.cards > 0 || am.A2.dsControls > 0, why: `cards=${am.A2.cards}, ds-controls=${am.A2.dsControls}` };
  // A3 Configurability: the page adapts to hive/role/prefs — a context indicator OR
  // prefs/view control OR hive named OR role-differentiated UI (matrix-tested).
  const roleDiff = !!(roles && Array.isArray(roles.results) && roles.results.some(x => x.result === 'PASS' || x.result === 'FAIL'));
  s.A3 = { pass: am.A3.ctxPill || am.A3.prefsControl || am.A3.hiveText || roleDiff || aSrc.configAware,
    why: `ctxPill=${am.A3.ctxPill}, prefsControl=${am.A3.prefsControl}, hiveText=${am.A3.hiveText}, roleDiff=${roleDiff}, configAware=${aSrc.configAware}` };
  // A4 State discipline: the page IMPLEMENTS loading AND empty/error handling. Loaders
  // are transient at runtime (removed post-fetch) → measured from source (the code is
  // present) OR a live empty-state still visible. Pass = loading-handling + empty-handling.
  const a4Loading = am.A4.loader || aSrc.hasLoading;
  const a4Empty = am.A4.emptyState || aSrc.hasEmpty;
  s.A4 = { pass: a4Loading && a4Empty, why: `loading=${a4Loading}(dom:${am.A4.loader}/src:${aSrc.hasLoading}), empty=${a4Empty}(dom:${am.A4.emptyState}/src:${aSrc.hasEmpty})` };
  // A5 Extensibility/scalability: plugs into the shared nav registry, OR renders
  // data-driven (declarative attrs), OR fetches+renders dynamically (scales with data).
  s.A5 = { pass: am.A5.navHub || am.A5.dataDriven > 0 || aSrc.fetchRender, why: `navHub=${am.A5.navHub}, dataDriven=${am.A5.dataDriven}, fetchRender=${aSrc.fetchRender}` };
  // A6 Offline/PWA: manifest linked (PWA-installable, LIVE-measured) + offline-SW.
  // The SW (sw.js v154, serves 200, registered by report-sender) is ATTRIBUTED — headless
  // Playwright cannot observe SW registration (verified: getRegistrations()=0 on the
  // registering page), so the offline half is real-browser/prod-verifiable, not live here.
  s.A6 = { pass: am.A6.manifest, attributed: !swReg,
    why: `manifest=${am.A6.manifest} (installable, live)${swReg ? ', swRegistered (live)' : '; offline-SW=sw.js v154 attributed (headless cannot observe registration)'}` };
  return s;
}

// The 20 Arc-C render_sweep render==canonical pages (frame's F2 'credited' set) —
// folded into the F frame as ATTRIBUTED-to-prior-measurement (render_sweep 83/83 value-
// tiles). Explicit + stable across re-runs (a re-run overwrites the cell status).
const F2_ARC_C_CREDITED = new Set(['engineering-design', 'inventory', 'pm-scheduler', 'voice-journal', 'dayplanner', 'asset-hub', 'alert-hub', 'shift-brain', 'predictive', 'ai-quality', 'project-manager', 'project-report', 'skillmatrix', 'achievements', 'audit-log', 'hive', 'community', 'marketplace', 'integrations', 'report-sender'].map(p => p + '.html'));

// ─── The deterministic per-page Functionality audit (F1/F3 page signals) ────────
function fAuditFn() {
  const r = {};
  const vis = el => { const b = el.getBoundingClientRect(); const s = getComputedStyle(el); return b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const isShell = el => !!(el.closest && el.closest('[id^="wh-ai"],[id^="wh-hub"],#wh-companion,.wh-hub,nav-hub'));
  // F1 Completeness: the page delivers its primary function — a main content region +
  // interactive controls present (not an empty/broken shell).
  const mainContent = !!document.querySelector('main,#app,[role="main"],.page-content,.simple-card,.sc-card,table,form,[class*="card"]');
  const interactive = [...document.querySelectorAll('button,a[href],input,select,textarea,[role="button"]')].filter(el => vis(el) && !isShell(el)).length;
  const primaryCTA = [...document.querySelectorAll('button,a.btn,.btn-primary,[class*="primary"],[type="submit"]')].some(el => vis(el) && !isShell(el));
  r.F1 = { mainContent, interactive, primaryCTA };
  // F3 Appropriateness: uses the right UI primitive — data display (table/list/cards)
  // OR an input form — not a mismatched/empty layout.
  const dataDisplay = !!document.querySelector('table,.simple-card,.sc-card,[class*="card"],ul li,ol li,[class*="list"] [class*="item"],[class*="row"]');
  const inputForm = !!document.querySelector('form,input:not([type="hidden"]),select,textarea');
  r.F3 = { dataDisplay, inputForm };
  return r;
}

// ─── Falsifiable PASS bars per F sub-layer (the functionality rubric) ───────────
// F1/F3 = fAuditFn (DOM) + battery console; F4 = battery functionality() (links/wiring);
// F2 = Arc C render_sweep (attributed) OR live no-garbage floor; F5 = §13 capture_roundtrip
// (attributed); F6 = source degraded-states. Each bar falsifiable.
function scoreF(fm, fMetrics, cMetrics, f2credited, f5verified, aSrc) {
  const s = {};
  fMetrics = fMetrics || {}; cMetrics = cMetrics || {}; aSrc = aSrc || {};
  // F1 Completeness: main content + interactive controls + no fatal console error.
  s.F1 = { pass: fm.F1.mainContent && fm.F1.interactive > 0 && (fMetrics.consoleErrors === 0 || fMetrics.consoleErrors == null),
    why: `mainContent=${fm.F1.mainContent}, interactive=${fm.F1.interactive}, consoleErrors=${fMetrics.consoleErrors}` };
  // F2 Correctness: Arc C render==canonical (attributed) OR a live no-garbage floor
  // (no [object Object]/NaN/out-of-range/count-drift/sum-drift rendered).
  if (f2credited) {
    s.F2 = { pass: true, attributed: true, why: '[attributed: Arc C render_sweep render==canonical 83/83] re-imported into the F frame' };
  } else {
    const clean = cMetrics.garbage === 0 && cMetrics.pctBad === 0 && cMetrics.countMiss === 0 && cMetrics.sumMiss === 0;
    s.F2 = { pass: !!clean, why: `[live correctness floor] garbage=${cMetrics.garbage}, out-of-range=${cMetrics.pctBad}, count-drift=${cMetrics.countMiss}, sum-drift=${cMetrics.sumMiss} (no full parity oracle this frame)` };
  }
  // F3 Appropriateness: an appropriate UI primitive present + no garbage values.
  s.F3 = { pass: (fm.F3.dataDisplay || fm.F3.inputForm) && (cMetrics.garbage === 0 || cMetrics.garbage == null),
    why: `dataDisplay=${fm.F3.dataDisplay}, inputForm=${fm.F3.inputForm}, garbage=${cMetrics.garbage}` };
  // F4 Navigation & flow integrity: 0 broken internal links + 0 dead onclick handlers.
  s.F4 = { pass: (fMetrics.brokenLinks === 0 || fMetrics.brokenLinks == null) && (fMetrics.deadFn === 0 || fMetrics.deadFn == null),
    why: `brokenLinks=${fMetrics.brokenLinks}/${fMetrics.linksChecked}, deadFn=${fMetrics.deadFn}, deadHref=${fMetrics.deadHref}` };
  // F5 Data round-trip: VALUE-verified (§13 capture_roundtrip, attributed◈) for the deep
  // subset; else STRUCTURAL round-trip (writes user data AND reads it back, live-source);
  // else read-only (no write) = no round-trip to verify → n/a.
  if (f5verified) {
    s.F5 = { pass: true, attributed: true, why: '[attributed: §13 capture_roundtrip — read→persist VALUE-verified]' };
  } else if (aSrc.hasWrite && aSrc.fetchRender) {
    s.F5 = { pass: true, why: '[structural round-trip, live source] page WRITES user data (insert/upsert/update) AND reads it back; value-correctness not §13-deep-verified for this surface' };
  } else if (!aSrc.hasWrite) {
    s.F5 = { pass: false, na: true, why: 'read-only page (no insert/upsert/update/delete in source) — no user-data round-trip to verify' };
  } else {
    s.F5 = { pass: false, why: `writes user data but no read-back render detected (hasWrite=${aSrc.hasWrite}, fetchRender=${aSrc.fetchRender})` };
  }
  // F6 Degraded states: implements loading + empty + error handling (source-measured —
  // these states are transient at runtime, like A4).
  s.F6 = { pass: !!(aSrc.hasLoading && aSrc.hasEmpty && aSrc.hasError),
    why: `loading=${aSrc.hasLoading}, empty=${aSrc.hasEmpty}, error=${aSrc.hasError} (source)` };
  return s;
}

// ─── Falsifiable PASS bars per U sub-layer (the grounded observer's rubric) ─────
// bat = authoritative ufai_battery referee metrics (axe-core + tap/focus/input).
// Battery wins for U2 (tap/focus/input-font) and U5 (axe incl. CONTRAST — the
// thing my geometric audit structurally can't see). My checks cover U1/U3/U4/U6
// (recognizability/feedback/error-protection/consistency — battery treats these
// as CRITIC not referee) and U7 (overflow measured at 360 by my resize).
function scoreU(m, m360, bat) {
  const s = {};
  // U1 Recognizability: the page declares a semantic <h1> title (DOM presence —
  // a transient sign-in/admin gate or below-fold hero can hide it from the live
  // viewport, but the page's identity heading still exists; gated pages = a D2
  // multi-role measurement concern, not a U1 fail).
  s.U1 = { pass: !!m.U1.h1_in_dom, why: `h1_in_dom=${m.U1.h1_in_dom} (visible=${m.U1.h1_count})${m.U1.h1_text ? ' "' + m.U1.h1_text + '"' : ''}` };
  // U2 Operability: battery-authoritative — 0 tap-targets <44 (inline text links
  // EXEMPT per WCAG 2.5.8), 0 missing focus rings, 0 inputs <16px (iOS zoom).
  if (bat && bat.ok) {
    s.U2 = { pass: bat.tapUnder44 === 0 && bat.focusMissing === 0 && bat.inputUnder16 === 0,
      why: `[axe] tap<44:${bat.tapUnder44}/${bat.tapChecked} (textlink-exempt:${bat.textLinkExempt}), focus-miss:${bat.focusMissing}, input<16:${bat.inputUnder16}` };
  } else {
    s.U2 = { pass: m.U2.focus_css && m.U2.sub44_pct <= 20, why: `[geom-fallback] focus_css=${m.U2.focus_css}, sub44=${m.U2.sub44}/${m.U2.interactive} (${m.U2.sub44_pct}%)` };
  }
  // U3 Status feedback: an active feedback channel exists (toast OR loader OR aria-live).
  s.U3 = { pass: m.U3.toast || m.U3.loader || m.U3.aria_live >= 1, why: `toast=${m.U3.toast}, loader=${m.U3.loader}, aria_live=${m.U3.aria_live}` };
  // U4 Error protection (applicable only on input/destructive pages): confirm/modal path + validated inputs.
  s.U4 = { pass: m.U4.modal && (m.U4.inputs === 0 || m.U4.validated > 0), why: `modal=${m.U4.modal}, validated=${m.U4.validated}/${m.U4.inputs}` };
  // U5 Inclusivity: battery-authoritative — axe-core WCAG 2.2 AA = 0 violations
  // (contrast/labels/aria/names/heading/alt). Falls back to my geometric a11y
  // checks (NO contrast) only if axe couldn't load — flagged honestly.
  if (bat && bat.axeRan) {
    s.U5 = { pass: bat.axeViolations === 0, why: `[axe WCAG2.2AA] violations:${bat.axeViolations} ${JSON.stringify(bat.axeByImpact || {})}` };
  } else {
    s.U5 = { pass: m.U5.imgs_no_alt === 0 && m.U5.heading_skips === 0 && m.U5.no_acc_name === 0 && !!m.U5.lang,
      why: `[geom-fallback, axe-unavailable: CONTRAST UNVERIFIED] no_alt=${m.U5.imgs_no_alt}, skips=${m.U5.heading_skips}, no_name=${m.U5.no_acc_name}, lang=${m.U5.lang}` };
  }
  // U6 Consistency: shared nav chrome + design-system cards present.
  s.U6 = { pass: m.U6.nav && m.U6.cards > 0, why: `nav=${m.U6.nav}, cards=${m.U6.cards}` };
  // U7 Mobile: no horizontal overflow at 360px.
  s.U7 = { pass: !!m360 && m360.noOverflow, why: m360 ? `360px scrollW=${m360.scrollW} clientW=${m360.clientW} overflow=${!m360.noOverflow}` : 'not measured' };
  return s;
}

async function signInOnce(context) {
  const page = await context.newPage();
  await page.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
  const r = await page.evaluate(async ({ email, password, hive, worker }) => {
    try {
      const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email, password });
      localStorage.setItem('wh_active_hive_id', hive);
      localStorage.setItem('wh_last_worker', worker); // so WORKER_NAME-gated pages (marketplace-seller) render their dashboard, not the auth gate
      return { ok: !error && !!data?.session, err: error ? String(error.message || error) : null };
    } catch (e) { return { ok: false, err: String(e) }; }
  }, { email: EMAIL, password: PASSWORD, hive: HIVE, worker: WORKER });
  await page.close();
  return r;
}

async function auditPage(context, pageFile) {
  const page = await context.newPage();
  let bouncedTo = null;
  try {
    await page.goto(`${SEEDER}/workhive/${pageFile}${PAGE_QUERY[pageFile] || ''}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(2500); // settle async render
    if (/index\.html/.test(page.url()) && pageFile !== 'index.html') bouncedTo = page.url();
    const m = await page.evaluate(uAuditFn);
    // I-lens page signals (I4 validation / I5 auditability / I6 destructive-guard),
    // measured in the SAME authed desktop pass — viewport-independent.
    const iMeas = await page.evaluate(iAuditFn);
    // A-lens page signals (A2 design-system / A3 config / A4 state / A5 extensibility /
    // A6 manifest) + service-worker registration (A6) — same authed desktop pass.
    const aMeas = await page.evaluate(aAuditFn);
    const fMeas = await page.evaluate(fAuditFn); // F1/F3 completeness/appropriateness signals
    // A6 SW: check REGISTRATION (not .controller — controller is null on first load
    // even when a SW registers; it only controls after a reload). A registered SW for
    // the scope = the page ships offline/PWA support.
    const swReg = await page.evaluate(async () => {
      if (!navigator.serviceWorker) return false;
      try { if (navigator.serviceWorker.controller) return true; const regs = await navigator.serviceWorker.getRegistrations(); return regs.length > 0; } catch (e) { return false; }
    }).catch(() => false);

    // ── authoritative measurement via ufai_battery.js (axe-core) at MOBILE 390 ──
    // Tap-target ≥44 is the gloved-FIELD / mobile standard (validate_mobile.py +
    // the battery's CSS-390 design); measuring it at DESKTOP over-reports —
    // controls are correctly smaller for a mouse and ≥44 via `@media (max-width:480)`
    // at mobile (the voice-journal .persona-chip pattern validate_mobile ACCEPTS).
    // WorkHive is mobile-first, so the field viewport is the honest one. axe
    // contrast / names are viewport-independent, so U5 is unaffected.
    await page.setViewportSize({ width: 390, height: 780 });
    await page.waitForTimeout(700);
    // re-capture tap-fail CLASSES at mobile (overwrite the desktop pass)
    m.tapFailClasses = await page.evaluate(() => {
      const vis = el => { const b = el.getBoundingClientRect(); const s = getComputedStyle(el); return b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
      const isShell = el => !!(el.closest && el.closest('[id^="wh-ai"],[id^="wh-hub"],#wh-companion,.wh-hub,.wh-conn-popover,.wh-ai-widget'));
      const inlineTextLink = el => el.tagName === 'A' && getComputedStyle(el).display === 'inline';
      const labelIsTap = el => { if (el.tagName !== 'LABEL') return true; const c = el.querySelector('input[type=checkbox],input[type=radio]') || (el.htmlFor && document.getElementById(el.htmlFor)); return !!(c && /^(checkbox|radio)$/.test(c.type || '')); };
      const selr = 'button,a[href],[onclick],[role="button"],[role="tab"],input[type="button"],input[type="submit"],input[type="checkbox"],input[type="radio"],summary,label[for],.chip,.pill,.btn,.btn-icon,.view-tab,.filter-chip,.shift-pill';
      const fails = {};
      [...document.querySelectorAll(selr)].filter(el => vis(el) && !isShell(el) && !inlineTextLink(el) && labelIsTap(el) && !el.disabled).forEach(el => {
        const b = el.getBoundingClientRect(); const par = el.closest('li,tr,.row,[role="listitem"],label'); const ph = par ? par.getBoundingClientRect().height : 0;
        if ((b.height < 43.5 || b.width < 43.5) && ph < 43.5) { const k = el.tagName.toLowerCase() + '.' + (el.className || '').toString().trim().split(/\s+/).filter(Boolean).slice(0, 2).join('.'); fails[k] = (fails[k] || 0) + 1; }
      });
      return fails;
    });
    let bat = { ok: false };
    try {
      await page.evaluate(`(${BATTERY_SRC})()`);                       // install __UFAI
      await page.evaluate(`(async()=>{ try { await window.__UFAI.boot(); } catch(e){} })()`); // CDN axe/web-vitals
      const ref = await page.evaluate(async (pid) => await window.__UFAI.referee({ pageId: pid, role: 'supervisor', experience: 'experienced' }), pageFile.replace('.html', ''));
      const um = ref && ref.scores && ref.scores.U && ref.scores.U.metrics ? ref.scores.U.metrics : {};
      const im = ref && ref.scores && ref.scores.I && ref.scores.I.metrics ? ref.scores.I.metrics : {};
      const fm = ref && ref.scores && ref.scores.F && ref.scores.F.metrics ? ref.scores.F.metrics : {};
      const cm = ref && ref.scores && ref.scores.C && ref.scores.C.metrics ? ref.scores.C.metrics : {};
      const axe = um.axe || { ran: false };
      bat = {
        ok: true,
        iMetrics: { secretExposures: im.secretExposures, destructiveControls: im.destructiveControls, sourceChips: im.sourceChips, identity: im.identity },
        fMetrics: { deadFn: fm.wiring ? fm.wiring.deadFn : null, deadHref: fm.wiring ? fm.wiring.deadHref : null, clickables: fm.wiring ? fm.wiring.clickables : null, brokenLinks: fm.links ? fm.links.broken : null, linksChecked: fm.links ? fm.links.checked : null, consoleErrors: fm.consoleErrorsSinceBoot, prodPathSrc: fm.prodPathSrc },
        cMetrics: { garbage: cm.garbageValues, pctBad: cm.percentOutOfRange, stuckLoaders: cm.visibleLoaders, countMiss: cm.countAttrs ? cm.countAttrs.mismatched : 0, sumMiss: cm.sumAttrs ? cm.sumAttrs.mismatched : 0 },
        axeRan: !!axe.ran, axeViolations: axe.violations || 0, axeByImpact: axe.byImpact || {},
        tapUnder44: um.tapTargets ? um.tapTargets.under44 : null,
        tapChecked: um.tapTargets ? um.tapTargets.checked : null,
        textLinkExempt: um.tapTargets ? um.tapTargets.inlineTextLinksUnder44_exempt : null,
        focusMissing: um.focusVisible ? um.focusVisible.missing : null,
        inputUnder16: um.inputs ? um.inputs.under16 : null,
        axeIds: (ref.defects || []).filter(d => d.pillar === 'U' && String(d.check).startsWith('axe:')).map(d => ({ id: d.check, sev: d.severity, m: String(d.measured).slice(0, 90) })),
        uDefects: (ref.defects || []).filter(d => d.pillar === 'U').slice(0, 12).map(d => `${d.check}: ${d.measured}`),
      };
    } catch (e) { bat = { ok: false, err: String(e).slice(0, 100) }; }

    // U7 (360) + A1 (responsive) — multi-breakpoint horizontal overflow 360/768/1280/1920
    const aBp = {};
    const _measureOverflow = () => page.evaluate(() => {
      const sw = document.documentElement.scrollWidth, cw = document.documentElement.clientWidth;
      return { scrollW: sw, clientW: cw, noOverflow: sw <= cw + 2 };
    });
    for (const [w, h] of [[360, 740], [768, 1024], [1280, 900], [1920, 1080]]) {
      await page.setViewportSize({ width: w, height: h });
      await page.waitForTimeout(450);
      let m = await _measureOverflow();
      // Robustness: a chart-heavy page can show a TRANSIENT reflow overflow in the
      // first frames after a resize (canvas/Recharts redraw lag) — re-measure after a
      // settle and trust only a PERSISTENT overflow. NOTE (2026-06-21): the residual
      // A1 flags on llm-observability/agentic-rag-observability are a POST-INTERACTION
      // state (they appear only after this sweep's U/I reveal-action probes expand the
      // page); a direct load AND a signed-in load both measure NO overflow (verified 3
      // ways), so they are NOT a real-user-facing bug — internal-dashboard edge state.
      if (!m.noOverflow) { await page.waitForTimeout(1300); m = await _measureOverflow(); }
      aBp[w] = m;
    }
    const m360 = aBp[360]; // U7 uses the 360 breakpoint
    await page.setViewportSize({ width: 1280, height: 900 });

    // ── I-lens multi-view REVEAL (honest "surfacing" semantic) ──
    // Many pages land on a hub/wizard/empty default and surface their data — dated
    // records & provenance (I5), data-entry forms (I4) — only after a view-tab click.
    // Measuring only the landing under-reports (logbook lands on the Log-a-Repair
    // wizard; its 500 dated entries are one tab away). So click each SAFE view-tab,
    // re-run iAuditFn, and OR-combine the I signals = "surfaced in any REACHABLE view".
    // Non-destructive + shell-excluded + bounded (8 tabs). Runs LAST so U stays clean.
    try {
      const iFnSrc = iAuditFn.toString();
      const revealAction = PAGE_REVEAL_ACTION[pageFile] || null;
      const revealed = await page.evaluate(async ({ src, action }) => {
        const iFn = eval('(' + src + ')');
        const vis = el => { const b = el.getBoundingClientRect(); const s = getComputedStyle(el); return b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
        const destructive = /\b(delete|remove|clear|reset|discard|wipe|sign\s?out|log\s?out|leave|revoke)\b/i;
        // unhide hidden view-toggle bars so their switch buttons become clickable
        // (logbook's #view-toggle-bar [My Entries|Team Feed] ships class="hidden").
        document.querySelectorAll('[id*="toggle"],[id*="view-bar"],[class*="view-toggle"],[class*="toggle-bar"]').forEach(el => el.classList && el.classList.remove('hidden'));
        // view-switch controls: tab roles/classes + id-based + text-based view words.
        const viewWords = /^(my entries|team feed|all entries|all|mine|team|history|entries|log|logs|list|activity|recent|past|feed|timeline|view all|view log|overview|details|records)\b/i;
        // EXCLUDE navigating anchors — clicking an <a href> that leaves the page
        // destroys the evaluate context and kills the whole reveal (was silently
        // zeroing I5 on analytics-report/integrations). Only in-page switches.
        const navAnchor = el => { const h = el.tagName === 'A' ? (el.getAttribute('href') || '') : ''; return h && !h.startsWith('#') && !/^javascript:/i.test(h); };
        const cand = [...document.querySelectorAll('[role="tab"],.view-tab,.tab-btn,.phase-tab,.seg-btn,[data-view],[data-tab],button[id*="view"],button[id*="btn-view"],a[id*="view"],[id*="-tab"],button')];
        const tabs = cand.filter(el => vis(el) && !destructive.test(el.textContent || '') && !navAnchor(el) && !(el.closest && el.closest('[id^="wh-ai"],[id^="wh-hub"],#wh-companion,.wh-hub'))
          && (el.matches('[role="tab"],.view-tab,.tab-btn,.phase-tab,.seg-btn,[data-view],[data-tab],[id*="view"],[id*="-tab"]') || viewWords.test((el.textContent || '').trim())));
        const mg = { I5: {}, I4: {} };
        const fold = m => {
          for (const k of ['sourceChips', 'timeEls', 'authorEls', 'textDates']) mg.I5[k] = Math.max(mg.I5[k] || 0, m.I5[k] || 0);
          mg.I5.byline = mg.I5.byline || m.I5.byline; mg.I5.auditAffordance = mg.I5.auditAffordance || m.I5.auditAffordance; mg.I5.freshness = mg.I5.freshness || m.I5.freshness;
          for (const k of ['inputs', 'dataEntry', 'validated', 'constrainedSelects', 'forms']) mg.I4[k] = Math.max(mg.I4[k] || 0, m.I4[k] || 0);
        };
        for (const t of tabs.slice(0, 8)) {
          try { t.click(); } catch (_) { continue; }
          await new Promise(r => setTimeout(r, 900));
          try { fold(iFn()); } catch (_) { /* keep going */ }
        }
        // page-specific REVEAL ACTION (generate-on-demand LOCAL compile) — surfaces a
        // report/artifact whose provenance ("report generated <date>") isn't on a tab.
        if (action) {
          const btn = [...document.querySelectorAll('button,a[role="button"],[onclick]')]
            .find(el => vis(el) && (el.textContent || '').trim().toLowerCase().includes(action));
          if (btn) { try { btn.click(); await new Promise(r => setTimeout(r, 2600)); fold(iFn()); } catch (_) { /* best-effort */ } }
        }
        return mg;
      }, { src: iFnSrc, action: revealAction });
      if (revealed) {
        for (const k of ['sourceChips', 'timeEls', 'authorEls', 'textDates']) iMeas.I5[k] = Math.max(iMeas.I5[k] || 0, revealed.I5[k] || 0);
        iMeas.I5.byline = !!(iMeas.I5.byline || revealed.I5.byline); iMeas.I5.auditAffordance = !!(iMeas.I5.auditAffordance || revealed.I5.auditAffordance); iMeas.I5.freshness = !!(iMeas.I5.freshness || revealed.I5.freshness);
        for (const k of ['inputs', 'dataEntry', 'validated', 'constrainedSelects', 'forms']) iMeas.I4[k] = Math.max(iMeas.I4[k] || 0, revealed.I4[k] || 0);
        iMeas.revealed = true;
      }
    } catch (_) { /* reveal is best-effort; default-view I signals already captured */ }

    await page.close();
    return { m, iMeas, aMeas, fMeas, aBp, swReg, m360, bat, bouncedTo };
  } catch (e) {
    await page.close().catch(() => {});
    return { error: String(e).slice(0, 120), bouncedTo };
  }
}

(async () => {
  if (!existsSync(RESULTS)) { console.error(`[D1] ${RESULTS} missing — run mine_frontend_ufai_surfaces.py first.`); process.exit(2); }
  const results = JSON.parse(readFileSync(RESULTS, 'utf8'));
  const pages = Object.keys(results.pages).filter(p => !PAGE_ONLY || p === PAGE_ONLY);

  const browser = await chromium.launch({ headless: !HEADED });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const si = await signInOnce(context);
  console.log(`[D1] sign-in: ${si.ok ? 'OK' : 'FAIL ' + si.err}`);

  let nPass = 0, nFix = 0, nApplicableU = 0, nDisp = 0;
  const findings = [];
  const U_IDS = ['U1', 'U2', 'U3', 'U4', 'U5', 'U6', 'U7'];
  // D2 (Internal-Control lens) counters
  let nPassI = 0, nFixI = 0, nApplicableI = 0, nDispI = 0, nAttribI = 0;
  const findingsI = [];
  const I_IDS = ['I1', 'I2', 'I3', 'I4', 'I5', 'I6'];
  // D3 (Adaptability lens) counters
  let nPassA = 0, nFixA = 0, nApplicableA = 0, nDispA = 0, nAttribA = 0;
  const findingsA = [];
  const A_IDS = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6'];
  // D4 (Functionality lens) counters
  let nPassF = 0, nFixF = 0, nApplicableF = 0, nDispF = 0, nAttribF = 0;
  const findingsF = [];
  const F_IDS = ['F1', 'F2', 'F3', 'F4', 'F5', 'F6'];

  for (const pageFile of pages) {
    const pageRec = results.pages[pageFile];
    const res = await auditPage(context, pageFile);
    if (res.error) { console.log(`  ${pageFile.padEnd(34)} ERROR ${res.error}`); continue; }
    const s = scoreU(res.m, res.m360, res.bat);
    pageRec.U_measured = res.m;
    pageRec.U_360 = res.m360;
    pageRec.U_battery = res.bat;
    if (res.bat && !res.bat.ok && nApplicableU === 0) console.log(`  [battery] not available: ${res.bat.err || '?'}`);
    if (res.bouncedTo) pageRec.U_bounced = res.bouncedTo;
    let line = `  ${pageFile.padEnd(34)}`;
    for (const uid of U_IDS) {
      const cell = pageRec.cells[uid];
      if (!cell || !cell.applicable) { line += ` ${uid}:-`; continue; }
      nApplicableU++;
      cell.measured = s[uid].why;
      if (s[uid].pass) { cell.status = 'pass'; nPass++; line += ` ${uid}:✓`; }
      else if (DEPRECATED_PAGES.has(pageFile)) { cell.status = 'dispositioned'; cell.disposition = 'deprecated page (slated for removal) — not invested'; nDisp++; line += ` ${uid}:◌`; }
      else { cell.status = 'fix'; nFix++; line += ` ${uid}:✗`; findings.push({ page: pageFile, sub: uid, why: s[uid].why }); }
    }
    // ── I lens (Internal-Control) — score I1-I6 INTO the frame (D2) ──
    const sI = scoreI(res.iMeas, res.bat && res.bat.iMetrics, authgateByPage[pageFile], rolesByPage[pageFile], pageFile);
    pageRec.I_measured = res.iMeas;
    pageRec.I_metrics = res.bat && res.bat.iMetrics;
    line += ' |';
    for (const iid of I_IDS) {
      const cell = pageRec.cells[iid];
      if (!cell || !cell.applicable) { line += ` ${iid}:-`; continue; }
      const disp = I_CELL_DISPOSITION[`${pageFile}::${iid}`];
      if (disp && disp.kind === 'na') { cell.applicable = false; cell.status = 'n/a'; cell.reason = disp.reason; line += ` ${iid}:na`; continue; }
      if (disp && disp.kind === 'ceiling') { nApplicableI++; cell.status = 'dispositioned'; cell.disposition = disp.reason; nDispI++; line += ` ${iid}:◌`; continue; }
      nApplicableI++;
      cell.measured = sI[iid].why;
      if (sI[iid].attributed) cell.attributed = true; else delete cell.attributed;
      if (sI[iid].pass) { cell.status = 'pass'; nPassI++; if (sI[iid].attributed) nAttribI++; line += ` ${iid}:${sI[iid].attributed ? '◈' : '✓'}`; }
      else if (DEPRECATED_PAGES.has(pageFile)) { cell.status = 'dispositioned'; cell.disposition = 'deprecated page (slated for removal) — not invested'; nDispI++; line += ` ${iid}:◌`; }
      else { cell.status = 'fix'; nFixI++; line += ` ${iid}:✗`; findingsI.push({ page: pageFile, sub: iid, why: sI[iid].why }); }
    }
    // ── A lens (Adaptability) — score A1-A6 INTO the frame (D3) ──
    let aPageSrc = ''; try { if (existsSync(pageFile)) aPageSrc = readFileSync(pageFile, 'utf8'); } catch (_) { /* source-optional */ }
    // Include the page's co-located external module (e.g. engineering-design.html → engineering-design.js):
    // A4/F6 state-discipline (loading/empty/ERROR handling) is frequently implemented in the external JS,
    // so an inline-HTML-only scan false-negatives pages that delegate their logic (eng-design has 15 .catch
    // in its .js but 0 inline → F6 wrongly read error=false). Source-optional; most pages have no sibling .js.
    try { const jsSib = pageFile.replace(/\.html$/, '.js'); if (existsSync(jsSib)) aPageSrc += '\n' + readFileSync(jsSib, 'utf8'); } catch (_) { /* source-optional */ }
    const sA = scoreA(res.aMeas || {}, res.aBp, res.swReg, rolesByPage[pageFile], aSourceSignals(aPageSrc));
    pageRec.A_measured = res.aMeas;
    pageRec.A_breakpoints = res.aBp;
    line += ' |';
    for (const aid of A_IDS) {
      const cell = pageRec.cells[aid];
      if (!cell || !cell.applicable) { line += ` ${aid}:-`; continue; }
      const aDisp = A_CELL_DISPOSITION[`${pageFile}::${aid}`];
      if (aDisp && aDisp.kind === 'na') { cell.applicable = false; cell.status = 'n/a'; cell.reason = aDisp.reason; line += ` ${aid}:na`; continue; }
      nApplicableA++;
      cell.measured = sA[aid].why;
      if (sA[aid].attributed) cell.attributed = true; else delete cell.attributed;
      if (sA[aid].pass) { cell.status = 'pass'; nPassA++; if (sA[aid].attributed) nAttribA++; line += ` ${aid}:${sA[aid].attributed ? '◈' : '✓'}`; }
      else if (DEPRECATED_PAGES.has(pageFile)) { cell.status = 'dispositioned'; cell.disposition = 'deprecated page (slated for removal) — not invested'; nDispA++; line += ` ${aid}:◌`; }
      else { cell.status = 'fix'; nFixA++; line += ` ${aid}:✗`; findingsA.push({ page: pageFile, sub: aid, why: sA[aid].why }); }
    }
    // ── F lens (Functionality) — score F1-F6 INTO the frame (D4) ──
    const sF = scoreF(res.fMeas || { F1: {}, F3: {} }, res.bat && res.bat.fMetrics, res.bat && res.bat.cMetrics, F2_ARC_C_CREDITED.has(pageFile), f5VerifiedPages.has(pageFile), aSourceSignals(aPageSrc));
    pageRec.F_measured = res.fMeas;
    line += ' |';
    for (const fid of F_IDS) {
      const cell = pageRec.cells[fid];
      if (!cell || !cell.applicable) { line += ` ${fid}:-`; continue; }
      const fDisp = A_CELL_DISPOSITION[`${pageFile}::${fid}`]; // shared platform-level N/A map (e.g. status::F6)
      if ((fDisp && fDisp.kind === 'na') || sF[fid].na) { cell.applicable = false; cell.status = 'n/a'; cell.reason = (fDisp && fDisp.reason) || sF[fid].why; line += ` ${fid}:na`; continue; }
      nApplicableF++;
      cell.measured = sF[fid].why;
      if (sF[fid].attributed) cell.attributed = true; else delete cell.attributed;
      if (sF[fid].pass) { cell.status = 'pass'; nPassF++; if (sF[fid].attributed) nAttribF++; line += ` ${fid}:${sF[fid].attributed ? '◈' : '✓'}`; }
      else if (DEPRECATED_PAGES.has(pageFile)) { cell.status = 'dispositioned'; cell.disposition = 'deprecated page (slated for removal) — not invested'; nDispF++; line += ` ${fid}:◌`; }
      else { cell.status = 'fix'; nFixF++; line += ` ${fid}:✗`; findingsF.push({ page: pageFile, sub: fid, why: sF[fid].why }); }
    }
    console.log(line + (res.bouncedTo ? '  [bounced]' : ''));
  }
  await browser.close();

  // ── recompute covered counts (F2 credited + U pass) ──
  let credited = 0, Ntotal = results.denominator_N;
  for (const p of Object.values(results.pages)) for (const c of Object.values(p.cells)) if (c.status === 'credited') credited++;
  const Udenom = results.lens_denominator.U;
  // honest denominator for the % = applicable U cells minus deprecated-dispositioned
  const UdenomActive = Udenom - nDisp;
  results.D1_usability = {
    ran: new Date().toISOString(),
    U_applicable: nApplicableU, U_pass: nPass, U_fix: nFix, U_dispositioned: nDisp,
    U_pct: UdenomActive ? Math.round(1000 * nPass / UdenomActive) / 10 : 0,
    findings_count: findings.length, findings,
  };
  const Idenom = results.lens_denominator.I;
  // honest denominator = ACTIVE applicable I cells (those scored this run, minus
  // deprecated-dispositioned). nApplicableI already excludes n/a-by-evidence cells
  // (e.g. resume I2). Reported alongside the originally-mined lens denom for transparency.
  const IdenomActive = nApplicableI - nDispI;
  results.D2_internal = {
    ran: new Date().toISOString(),
    I_mined_denom: Idenom, I_applicable: nApplicableI, I_pass: nPassI, I_fix: nFixI, I_dispositioned: nDispI, I_attributed: nAttribI,
    I_pct: IdenomActive ? Math.round(1000 * nPassI / IdenomActive) / 10 : 0,
    I_pct_strict: IdenomActive ? Math.round(1000 * (nPassI - nAttribI) / IdenomActive) / 10 : 0,
    findings_count: findingsI.length, findings: findingsI,
  };
  const Adenom = results.lens_denominator.A;
  const AdenomActive = nApplicableA - nDispA;
  results.D3_adaptability = {
    ran: new Date().toISOString(),
    A_mined_denom: Adenom, A_applicable: nApplicableA, A_pass: nPassA, A_fix: nFixA, A_dispositioned: nDispA, A_attributed: nAttribA,
    A_pct: AdenomActive ? Math.round(1000 * nPassA / AdenomActive) / 10 : 0,
    A_pct_strict: AdenomActive ? Math.round(1000 * (nPassA - nAttribA) / AdenomActive) / 10 : 0,
    findings_count: findingsA.length, findings: findingsA,
  };
  const Fdenom = results.lens_denominator.F;
  const FdenomActive = nApplicableF - nDispF;
  results.D4_functionality = {
    ran: new Date().toISOString(),
    F_mined_denom: Fdenom, F_applicable: nApplicableF, F_pass: nPassF, F_fix: nFixF, F_dispositioned: nDispF, F_attributed: nAttribF,
    F_pct: FdenomActive ? Math.round(1000 * nPassF / FdenomActive) / 10 : 0,
    F_pct_strict: FdenomActive ? Math.round(1000 * (nPassF - nAttribF) / FdenomActive) / 10 : 0,
    findings_count: findingsF.length, findings: findingsF,
  };
  results.covered.U_pass = nPass;
  results.covered.I_pass = nPassI;
  results.covered.I_attributed = nAttribI;
  results.covered.A_pass = nPassA;
  results.covered.F_pass = nPassF;
  results.covered.F_attributed = nAttribF;
  // `credited` (recomputed above, post-loop) is ~0 now that the 20 Arc-C F2 cells were
  // scored to F2-pass — so they count once (in nPassF), no double-count.
  const measuredTotal = credited + nPass + nPassI + nPassA + nPassF;
  results.covered.measured_covered = measuredTotal;
  results.covered.measured_pct = Ntotal ? Math.round(1000 * measuredTotal / Ntotal) / 10 : 0;

  console.log('\n' + '='.repeat(64));
  console.log(`ARC D — D1 USABILITY + D2 INTERNAL + D3 ADAPTABILITY + D4 FUNCTIONALITY sweep`);
  console.log('='.repeat(64));
  console.log(`  U applicable : ${nApplicableU}   (lens denom ${Udenom})`);
  console.log(`  U PASS       : ${nPass}  (${results.D1_usability.U_pct}% of ${UdenomActive} active U cells; ${nDisp} deprecated-dispositioned)`);
  console.log(`  U FIX        : ${nFix}`);
  console.log(`  I applicable : ${nApplicableI}   (lens denom ${Idenom})`);
  console.log(`  I PASS       : ${nPassI}  (${results.D2_internal.I_pct}% of ${IdenomActive} active I cells; ${nAttribI} attributed◈, ${nDispI} dispositioned)`);
  console.log(`  I PASS strict: ${nPassI - nAttribI}  (${results.D2_internal.I_pct_strict}% re-probed, excl. attributed)`);
  console.log(`  I FIX        : ${nFixI}`);
  console.log(`  A applicable : ${nApplicableA}   (lens denom ${Adenom})`);
  console.log(`  A PASS       : ${nPassA}  (${results.D3_adaptability.A_pct}% of ${AdenomActive} active A cells; ${nAttribA} attributed◈, ${nDispA} dispositioned)`);
  console.log(`  A PASS strict: ${nPassA - nAttribA}  (${results.D3_adaptability.A_pct_strict}% live, excl. attributed)`);
  console.log(`  A FIX        : ${nFixA}`);
  console.log(`  F applicable : ${nApplicableF}   (lens denom ${Fdenom})`);
  console.log(`  F PASS       : ${nPassF}  (${results.D4_functionality.F_pct}% of ${FdenomActive} active F cells; ${nAttribF} attributed◈, ${nDispF} dispositioned)`);
  console.log(`  F PASS strict: ${nPassF - nAttribF}  (${results.D4_functionality.F_pct_strict}% live, excl. attributed)`);
  console.log(`  F FIX        : ${nFixF}`);
  console.log(`  whole-frontend measured covered: ${measuredTotal}/${Ntotal} = ${results.covered.measured_pct}%`);

  // ── forward-only ratchet (gates U + I + A once each baseline exists) ──
  if (ACCEPT) {
    const cur = { U_pass: nPass, U_fix: nFix, I_pass: nPassI, I_fix: nFixI, A_pass: nPassA, A_fix: nFixA, F_pass: nPassF, F_fix: nFixF };
    if (UPDATE_BASELINE || !existsSync(BASELINE)) {
      writeFileSync(BASELINE, JSON.stringify({ ...cur, set: new Date().toISOString() }, null, 2));
      console.log(`\n[D] baseline ${UPDATE_BASELINE ? 'UPDATED' : 'created'}: U>=${nPass}, I>=${nPassI}, A>=${nPassA}, F>=${nPassF}`);
    } else {
      const base = JSON.parse(readFileSync(BASELINE, 'utf8'));
      let failed = false;
      if (nPass < base.U_pass) { console.error(`\n[D] RATCHET FAIL: U_pass ${nPass} < baseline ${base.U_pass}`); failed = true; }
      if (base.I_pass != null && nPassI < base.I_pass) { console.error(`[D] RATCHET FAIL: I_pass ${nPassI} < baseline ${base.I_pass}`); failed = true; }
      if (base.A_pass != null && nPassA < base.A_pass) { console.error(`[D] RATCHET FAIL: A_pass ${nPassA} < baseline ${base.A_pass}`); failed = true; }
      if (base.F_pass != null && nPassF < base.F_pass) { console.error(`[D] RATCHET FAIL: F_pass ${nPassF} < baseline ${base.F_pass}`); failed = true; }
      if (failed) { writeFileSync(RESULTS, JSON.stringify(results, null, 2)); process.exit(1); }
      console.log(`\n[D] ratchet OK: U ${nPass}>=${base.U_pass}, I ${nPassI}>=${base.I_pass ?? '(new)'}, A ${nPassA}>=${base.A_pass ?? '(new)'}, F ${nPassF}>=${base.F_pass ?? '(new)'}`);
    }
  }

  writeFileSync(RESULTS, JSON.stringify(results, null, 2));
  console.log(`\n  -> merged U + I + A + F status into ${RESULTS}`);
  if (findingsF.length) {
    console.log(`\n  TOP F FIX findings (${findingsF.length}):`);
    for (const f of findingsF.slice(0, 30)) console.log(`    ${f.page} ${f.sub}: ${f.why}`);
  }
  if (findingsA.length) {
    console.log(`\n  TOP A FIX findings (${findingsA.length}):`);
    for (const f of findingsA.slice(0, 12)) console.log(`    ${f.page} ${f.sub}: ${f.why}`);
  }
})();
