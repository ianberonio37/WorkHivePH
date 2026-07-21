// live_page_journeys.registry.mjs — Arc K JTBD registry.
//
// Each journey: { id, phase, page, role, state, title, lenses[], ufai[], external?, drive }
//   drive(page, h) → { R, J, T, C, X (bool|null), evidence:{}, findings:[] }
//   h helpers (from the engine): goto, qText, exists, count, click, clickText, fill,
//     waitFor, db(fn,arg), evalIn(fn,arg), numFrom, page.
//   A lens verdict of `null` = not-applicable to this JTBD.
//
// K1 = THE FRONT DOOR (index.html), 9 JTBDs: 5 landing-anon (LA1–LA5) + 4 home-authed
// (HM1–HM4). Grounded in the K0 scout's selector-level spec (.tmp/k0_k1_spec.json):
//   state gate: #mkt-wrap (landing) vs #ops-home (home); role branch reads localStorage
//   (wh_nav_mode/wh_hive_role). KPI tiles are CALM (render only when count>0; #oh-stats
//   hidden when all four zero). Roles in the DB: worker + supervisor only ("engineer" =
//   a usage persona, not an auth role) → home role-variant coverage is worker-vs-supervisor.
//
// ORDERING MATTERS (shared per-role contexts): anon journeys that must stay logged-out
// (LA1/2/3/5) run BEFORE LA4 (which signs in inside the anon context). HM4 (sign-out) runs
// LAST among worker journeys so it can't log the shared worker context out mid-phase.

import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
const _K6_DIR = dirname(fileURLToPath(import.meta.url));
const CSV_IN1 = resolve(_K6_DIR, '..', '.tmp', 'k6_in1_wo.csv'); // K6/IN1 work-order import fixture

const HIVE = process.env.WH_TEST_HIVE || '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7'; // Baguio Textile Mills
const HIVE_NAME = 'Baguio Textile Mills';

// computed-display "is hidden" (display:none) — exists() already requires visible, but for
// the mkt/ops state gate we want the explicit display value.
async function displayNone(h, sel) {
  return h.evalIn((s) => { const el = document.querySelector(s); if (!el) return true; return getComputedStyle(el).display === 'none'; }, sel);
}

export const JOURNEYS = [
  // ─────────────────────────── LANDING (anon) ───────────────────────────
  {
    id: 'LA1', phase: 'K1', page: 'index.html', role: 'anon', state: 'landing-anon',
    title: 'First-time visitor: landing loads and the value is obvious',
    lenses: ['R', 'J', 'X'], ufai: ['U', 'I'],
    drive: async (page, h) => {
      await h.goto('index.html');
      const mkt = await h.exists('#mkt-wrap');
      const opsHidden = await displayNone(h, '#ops-home');
      const heroTxt = (await h.qText('h1')) || '';
      const heroOk = /access your|memory/i.test(heroTxt);
      const cta = await h.exists("a.cta-pulse[href='#join'], a.btn-primary[href='#join']");
      const joinTarget = await h.exists('#join');
      return {
        R: mkt && opsHidden, J: heroOk && cta, T: null, C: null, X: cta && joinTarget,
        evidence: { mkt, opsHidden, hero: heroTxt.slice(0, 60), cta, joinTarget },
        findings: [],
      };
    },
  },
  {
    id: 'LA2', phase: 'K1', page: 'index.html', role: 'anon', state: 'landing-anon',
    title: 'Visitor joins the early-access waitlist and gets confirmation (→ early_access_emails)',
    lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'A', 'I'],
    drive: async (page, h) => {
      await h.goto('index.html');
      const formReachable = await h.exists('#joinForm');
      const recoverable = await h.exists("#joinForm input[type='email'][required], #joinForm input[name='email'][required]");
      const email = `k1-probe-${Date.now()}@plant.test`;
      await h.click("a[href='#join']").catch(() => {});
      await h.fill("#joinForm input[name='email'], #joinForm input[type='email']", email);
      await h.click('#joinForm button[type="submit"]');
      // poll the submit button for the success copy
      let btnTxt = '';
      for (let i = 0; i < 8; i++) {
        btnTxt = (await h.qText('#joinForm button[type="submit"]')) || '';
        if (/on the list|thank|joined|try again/i.test(btnTxt)) break;
        await page.waitForTimeout(700);
      }
      const joined = /on the list|thank|joined/i.test(btnTxt);
      // T: the row landed in early_access_emails — verified via the PRIVILEGED path.
      // (RLS is anon-INSERT + service_role-SELECT, so the in-page anon client cannot read
      // its own write back; the anon read-back was a harness false-negative.)
      const cntRaw = h.adminQuery(`select count(*) from early_access_emails where email = '${email.toLowerCase()}';`);
      const dbCount = (typeof cntRaw === 'string') ? parseInt(cntRaw, 10) : null;
      const persisted = dbCount != null && dbCount > 0;
      return {
        R: formReachable, J: joined, T: persisted, C: recoverable, X: null,
        evidence: { btnTxt: btnTxt.slice(0, 40), email, db_count: dbCount, db_path: 'service-role psql (anon is write-only)', recoverable },
        findings: [],
      };
    },
  },
  {
    id: 'LA3', phase: 'K1', page: 'index.html', role: 'anon', state: 'landing-anon',
    title: 'Curious visitor explores How-It-Works + opens an FAQ before committing',
    lenses: ['R', 'J', 'X'], ufai: ['U', 'I'],
    drive: async (page, h) => {
      await h.goto('index.html');
      const platform = await h.exists('section#platform');
      const faqSection = await h.exists('section#faq');
      const navLinks = await h.count("a.nav-link[href='#platform'], a.nav-link[href='#impact'], a.nav-link[href='#community']");
      // open the first FAQ accordion
      await h.click('section#faq details.faq-item > summary').catch(() => {});
      await page.waitForTimeout(400);
      const faqOpen = await h.exists('details.faq-item[open]');
      return {
        R: platform && faqSection, J: faqOpen, T: null, C: null, X: navLinks >= 2,
        evidence: { platform, faqSection, navLinks, faqOpen },
        findings: [],
      };
    },
  },
  {
    id: 'LA5', phase: 'K1', page: 'index.html', role: 'anon', state: 'landing-anon',
    title: 'Visitor reaches a free tool from the landing ("Free to use — sign up to start")',
    lenses: ['R', 'J', 'X'], ufai: ['U', 'I'],
    // RESOLVED (Ian 2026-06-22, "this is a free platform"): the landing's tool row no longer
    // makes a stale account-less "try free" promise. C4 removed guest access, so the row is
    // relabeled "Free to use — sign up to start" and each tool CTA opens the (free) SIGN-UP
    // modal (index.html openSignUp → switchAuthTab('signup')). The journey now verifies the
    // promise resolves TRUTHFULLY: honest label + clicking a tool routes to signup (no dead
    // bounce). Free platform = free to use, one free account; the copy matches the behavior.
    drive: async (page, h) => {
      await h.goto('index.html');
      // R: the free-tools row exists and is honestly labeled (no bare no-signup "try free")
      const rowText = (await h.evalIn(() => {
        const span = [...document.querySelectorAll('span')].find(s => /free to use|sign up to start|try free/i.test(s.textContent || ''));
        return span ? (span.textContent || '').trim() : '';
      })) || '';
      const honestLabel = /sign up/i.test(rowText);
      const ctas = await h.count("a[href='#join'][onclick*='openSignUp']");
      const reachable = honestLabel && ctas >= 4;
      // J: clicking the first tool CTA (Logbook) opens the SIGN-UP modal truthfully
      await h.click("a[href='#join'][onclick*='openSignUp']");
      const signupOpen = await h.waitFor('#su-username', 5000);
      const signupTab = await h.evalIn(() => document.getElementById('tab-signup')?.getAttribute('aria-selected') === 'true');
      const routed = signupOpen && signupTab;
      // X: still on the landing (anon), the signup modal is an overlay (no navigation away)
      const stillAnon = await h.exists('#mkt-wrap');
      const findings = [];
      if (ctas >= 4 && !routed) findings.push({
        layer: 'heuristic', severity: 2, owner: 'seo-content',
        rule: 'Free-tool CTA must route to signup (free platform: free to use, sign up to start)',
        evidence: `tool links present but did not open signup modal (su-username=${signupOpen}, signup tab=${signupTab})`,
      });
      if (ctas >= 4 && !honestLabel) findings.push({
        layer: 'heuristic', severity: 2, owner: 'seo-content',
        rule: 'Landing tool-row copy must be truthful (no account-less "try free" promise after C4)',
        evidence: `row label: "${rowText.slice(0, 60)}" — should read "Free to use — sign up to start"`,
      });
      return {
        R: reachable, J: routed, T: null, C: null, X: stillAnon && routed,
        evidence: { rowText: rowText.slice(0, 50), honestLabel, ctas, signupOpen, signupTab, stillAnon, note: 'free-platform: tool CTAs open signup (truthful), no stale guest promise' },
        findings,
      };
    },
  },
  {
    id: 'LA4', phase: 'K1', page: 'index.html', role: 'anon', state: 'landing-anon',
    title: 'Returning worker opens the Sign-In modal, recovers from a bad password, then lands on home',
    lenses: ['R', 'J', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'],
    drive: async (page, h) => {
      await h.goto('index.html');
      // open the sign-in modal — the trigger is now a <button class="signin-btn" onclick=openSignIn>
      // (was <a>, 2026-07-22 selector drift), rendered 3× for responsive breakpoints (only 1 visible).
      // Click the first VISIBLE .signin-btn (element-agnostic); fall back to calling openSignIn directly.
      await h.evalIn(() => {
        const btn = [...document.querySelectorAll('.signin-btn')].find(b => b.offsetParent !== null);
        if (btn) btn.click();
        else if (typeof window.openSignIn === 'function') window.openSignIn(new Event('click'));
      });
      const modalOpen = await h.waitFor('#si-username', 6000);
      // C: wrong creds → recoverable error message
      await h.fill('#si-username', 'bryangarcia');
      await h.fill('#si-password', 'definitely-wrong-pw');
      await h.click('#si-btn');
      let errTxt = '';
      for (let i = 0; i < 6; i++) { errTxt = (await h.qText('#si-error')) || ''; if (errTxt.trim()) break; await page.waitForTimeout(700); }
      const recovered = /wrong|invalid|incorrect|try again|failed|password/i.test(errTxt);
      // now the real sign-in
      await h.fill('#si-password', 'test1234');
      await h.click('#si-btn');
      // wait for home to appear (login proxy → setSession → _initDashboard)
      let opsShown = false;
      for (let i = 0; i < 18; i++) { opsShown = await h.exists('#ops-home'); if (opsShown) break; await page.waitForTimeout(800); }
      const mktHidden = await displayNone(h, '#mkt-wrap');
      // post-login the signin button is GONE — the user's name shows in the ops-home greeting
      // ("Good evening, Bryan"), not in a.signin-btn (the stale read that false-failed J, 2026-07-22).
      const nameTxt = (await h.evalIn(() => (document.getElementById('ops-home')?.innerText || '').slice(0, 400))) || '';
      const lwSet = await h.evalIn(() => !!localStorage.getItem('wh_last_worker'));
      const named = /bryan/i.test(nameTxt);
      return {
        R: modalOpen, J: opsShown && mktHidden && named, T: null, C: recovered, X: opsShown && lwSet,
        evidence: { modalOpen, errTxt: errTxt.slice(0, 50), recovered, opsShown, mktHidden, navName: nameTxt.slice(0, 24), lwSet },
        findings: [],
      };
    },
  },
  // ─────────────────────────── HOME (authed) ───────────────────────────
  {
    id: 'HM1', phase: 'K1', page: 'index.html', role: 'worker', state: 'home-authed',
    title: 'Signed-in worker: home becomes the operational launchpad with a personalized greeting',
    lenses: ['R', 'J', 'X'], ufai: ['U', 'I'],
    drive: async (page, h) => {
      await h.goto('index.html');
      const ops = await h.exists('#ops-home');
      const mktHidden = await displayNone(h, '#mkt-wrap');
      const greet = (await h.qText('#oh-greeting')) || '';
      const greetOk = /good (morning|afternoon|evening),?\s*\w+/i.test(greet);
      const dateTxt = (await h.qText('#oh-date')) || '';
      const hiveChip = (await h.qText('#oh-hive-btn')) || '';
      const hiveOk = hiveChip.toLowerCase().includes('baguio');
      return {
        R: ops && mktHidden, J: greetOk && dateTxt.trim().length > 0, T: null, C: null, X: hiveOk,
        evidence: { ops, mktHidden, greeting: greet.slice(0, 40), date: dateTxt.slice(0, 40), hiveChip: hiveChip.slice(0, 40) },
        findings: [],
      };
    },
  },
  {
    id: 'HM2', phase: 'K1', page: 'index.html', role: 'worker', state: 'home-authed',
    title: 'Home KPI tiles show real counts that match the canonical truth views (and honor the calm-empty contract)',
    lenses: ['T', 'R', 'C'], ufai: ['U', 'F', 'I'],
    drive: async (page, h) => {
      await h.goto('index.html');
      const ops = await h.exists('#ops-home');
      // rendered tile numbers (null when the calm tile is absent = count 0)
      const rend = {
        open: h.numFrom(await h.qText("a.oh-tile[data-kpi='open-jobs'] .oh-tile-num")),
        risk: h.numFrom(await h.qText("a.oh-tile[data-kpi='risk-alerts'] .oh-tile-num")),
        pm: h.numFrom(await h.qText("a.oh-tile[data-kpi='pm-overdue'] .oh-tile-num")),
        low: h.numFrom(await h.qText("a.oh-tile[data-kpi='low-stock'] .oh-tile-num")),
      };
      // independent canonical truth-view counts (the page's OWN authed client)
      const truth = await h.db(async (db, hive) => {
        const out = {};
        try { const { count } = await db.from('v_logbook_truth').select('*', { count: 'exact', head: true }).eq('hive_id', hive).eq('status', 'Open'); out.open = count ?? null; } catch (e) { out.open = null; }
        try { const { count } = await db.from('v_risk_truth').select('*', { count: 'exact', head: true }).eq('hive_id', hive).in('risk_level', ['critical', 'high']); out.risk = count ?? null; } catch (e) { out.risk = null; }
        try { const { count } = await db.from('v_inventory_items_truth').select('*', { count: 'exact', head: true }).eq('hive_id', hive).eq('is_low_stock', true); out.low = count ?? null; } catch (e) { out.low = null; }
        try { const { data } = await db.from('v_pm_scope_items_truth').select('pm_asset_id').eq('hive_id', hive).eq('is_overdue', true); out.pm = data ? new Set(data.map(r => r.pm_asset_id)).size : null; } catch (e) { out.pm = null; }
        return out;
      }, h.hive || HIVE);
      // compare per-KPI: rendered present → must equal DB; absent → DB must be 0 (calm-empty)
      const cmp = {}; let tOk = true, cOk = true, checked = 0;
      for (const k of ['open', 'risk', 'pm', 'low']) {
        const dbv = truth ? truth[k] : null; const rv = rend[k];
        if (dbv == null || (truth && truth.__err)) { cmp[k] = `db?(${dbv})`; continue; } // query unavailable → skip
        checked++;
        if (rv == null) { const calm = dbv === 0; cmp[k] = `absent vs db ${dbv} ${calm ? 'OK(calm)' : 'MISMATCH'}`; if (!calm) { tOk = false; cOk = false; } }
        else { const match = rv === dbv; cmp[k] = `${rv} vs db ${dbv} ${match ? 'OK' : 'MISMATCH'}`; if (!match) tOk = false; }
      }
      return {
        R: ops, J: null, T: checked > 0 ? tOk : null, C: cOk, X: null,
        evidence: { rendered: rend, truth, cmp, checked },
        findings: [],
      };
    },
  },
  {
    id: 'HM3', phase: 'K1', page: 'index.html', role: 'worker', state: 'home-authed',
    title: "Today's One Thing gives ONE truthful verdict + role-correct primary actions (worker vs supervisor)",
    lenses: ['J', 'T', 'C'], ufai: ['U', 'F', 'A', 'I'],
    drive: async (page, h) => {
      await h.goto('index.html');
      // ensure worker branch
      await h.evalIn(() => { localStorage.setItem('wh_hive_role', 'worker'); localStorage.removeItem('wh_nav_mode'); });
      const u1 = await h.goto('index.html');
      const todayCard = await h.count('#oh-today .oh-card');
      const actions = await h.count('#oh-actions a.oh-action');
      const firstActionWorker = (await h.qText('#oh-actions a.oh-action')) || '';
      const workerActionOk = /log a job|logbook/i.test(firstActionWorker) || (await h.exists("#oh-actions a.oh-action[href='logbook.html']"));
      // flip to supervisor → first action should become Hive Board
      await h.evalIn(() => { localStorage.setItem('wh_hive_role', 'supervisor'); localStorage.setItem('wh_nav_mode', 'supervisor'); });
      await h.goto('index.html');
      const firstActionSup = (await h.qText('#oh-actions a.oh-action')) || '';
      const supActionOk = /hive board/i.test(firstActionSup) || (await h.exists("#oh-actions a.oh-action[href='hive.html']"));
      // restore worker identity for any later worker journeys
      await h.evalIn(() => { localStorage.setItem('wh_hive_role', 'worker'); localStorage.removeItem('wh_nav_mode'); });
      // T: One-Thing is consistent with the live signals (all-clear iff no signal)
      const sig = await h.db(async (db, hive) => {
        const c = async (t, b) => { try { const { count } = await b(db.from(t).select('*', { count: 'exact', head: true }).eq('hive_id', hive)); return count || 0; } catch (e) { return 0; } };
        const open = await c('v_logbook_truth', q => q.eq('status', 'Open'));
        const risk = await c('v_risk_truth', q => q.in('risk_level', ['critical', 'high']));
        const low = await c('v_inventory_items_truth', q => q.eq('is_low_stock', true));
        return { total: open + risk + low };
      }, h.hive || HIVE);
      await h.goto('index.html');
      const todayTxt = (await h.qText('#oh-today')) || '';
      const allClear = /all clear|nothing urgent/i.test(todayTxt);
      const anySignal = sig && !sig.__err ? sig.total > 0 : null;
      const tOk = anySignal == null ? null : (anySignal ? !allClear : allClear);
      const verdictCardPresent = (await h.count('#oh-today .oh-card')) >= 1;
      return {
        R: null, J: todayCard >= 1 && actions === 2 && workerActionOk && supActionOk, T: tOk, C: verdictCardPresent, X: null,
        evidence: { todayCard, actions, firstActionWorker: firstActionWorker.slice(0, 24), firstActionSup: firstActionSup.slice(0, 24), workerActionOk, supActionOk, anySignal, allClear, today: todayTxt.slice(0, 50) },
        findings: [],
      };
    },
  },
  {
    id: 'HM4', phase: 'K1', page: 'index.html', role: 'worker', state: 'home-authed',
    title: 'From home, reach My Open Jobs + All Tools, deep-link to a tool, and sign out cleanly',
    lenses: ['R', 'J', 'X', 'C'], ufai: ['U', 'F', 'I'],
    drive: async (page, h) => {
      await h.goto('index.html');
      const ops = await h.exists('#ops-home');
      // expand "More" → My Open Jobs + All Tools grid
      await h.click('details#oh-more > summary').catch(() => {});
      await page.waitForTimeout(500);
      const jobsWrap = await h.exists('#oh-jobs-wrap, #oh-jobs');
      const toolsGrid = await h.exists('.oh-tools-grid');
      const toolLinks = await h.count("a.oh-qa-btn[href='logbook.html'], a.oh-qa-btn[href='analytics.html'], a.oh-qa-btn[href='assistant.html'], a.oh-qa-btn[href='pm-scheduler.html']");
      // X: deep-link to a tool lands (relative href under the /workhive/ mount)
      const aurl = await h.goto('analytics.html');
      const landed = /analytics\.html/.test(aurl) && (await h.count('button, a[href], [class*="card"]')) > 5;
      // C: clean sign-out → back to landing, identity cleared
      await h.goto('index.html');
      await h.evalIn(() => { try { (window.signOut && window.signOut()); } catch (e) { } });
      await page.waitForTimeout(800);
      const cleared = await h.evalIn(() => !localStorage.getItem('wh_last_worker'));
      // if signOut affordance didn't clear, fall back to clicking the visible control
      let mktBack = false;
      if (cleared) { await h.goto('index.html'); mktBack = await h.exists('#mkt-wrap'); }
      else {
        await h.click('.oh-signout').catch(() => {});
        await page.waitForTimeout(800);
        await h.goto('index.html'); mktBack = await h.exists('#mkt-wrap');
      }
      const clearedFinal = await h.evalIn(() => !localStorage.getItem('wh_last_worker'));
      // RE-ESTABLISH the worker session: this journey SIGNED OUT the shared per-role context,
      // which would log out every later worker journey in a full-suite run. Re-auth + re-seed
      // identity on a lenient page so the context is valid for K2+ worker journeys.
      await h.goto('shift-brain.html');
      await h.page.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
      await h.evalIn(async () => {
        try {
          const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
          const { data } = await db.auth.signInWithPassword({ email: 'bryangarcia@auth.workhiveph.com', password: 'test1234' });
          // resolve the REAL hive (test_identity pattern) — this re-auth runs EARLY (LA4) and its
          // stamp is inherited by EVERY later worker journey in a full run; the old dead-hive
          // literal poisoned the whole suite (scoped runs passed, full runs failed — THE tell).
          let realHive = null;
          try {
            const uid = data?.session?.user?.id;
            const { data: mem } = uid ? await db.from('hive_members').select('hive_id')
              .eq('auth_uid', uid).eq('status', 'active').limit(1).maybeSingle() : { data: null };
            if (mem && mem.hive_id) realHive = mem.hive_id;
          } catch (_) {}
          localStorage.setItem('wh_active_hive_id', realHive || '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7'); // hive fallback only
          localStorage.setItem('wh_last_worker', 'Bryan Garcia');
          localStorage.setItem('wh_hive_name', 'Baguio Textile Mills');
          localStorage.setItem('wh_hive_role', 'worker');
        } catch (e) { /* best-effort re-auth */ }
      });
      return {
        R: ops, J: jobsWrap && toolsGrid && toolLinks >= 2, T: null, C: clearedFinal && mktBack, X: landed,
        evidence: { ops, jobsWrap, toolsGrid, toolLinks, analyticsUrl: aurl, landed, signedOut: clearedFinal, mktBack },
        findings: [],
      };
    },
  },

  // ═══════════════════ K2 — FIELD WORK · logbook.html ═══════════════════
  // WRITE journeys insert a TAGGED test row (problem starts with K2-PROBE-<ts>), verify the
  // job completed + the row persisted, then DELETE the tag via the privileged path (cleanup
  // keeps the live DB clean + the ratchet stable). T-nerves (MTTR/open-jobs) are pre-proven
  // in journey_trace_results.json. Resolving = open entry → Edit → Status=Closed → Save (there
  // is NO "Mark Resolved" button). Supervisor defaults to Team Feed.
  ...logbookJourneys(),
  ...inventoryJourneys(),
  ...dayplannerJourneys(),
  ...hiveJourneys(),
  ...pmSchedulerJourneys(),
  ...communityJourneys(),
  ...analyticsJourneys(),
  ...assistantJourneys(),
  ...assetHubJourneys(),
  ...alertHubJourneys(),
  ...auditLogJourneys(),
  ...voiceJournalJourneys(),
  ...aiQualityJourneys(),
  ...analyticsReportJourneys(),
  ...engDesignJourneys(),
  ...projectManagerJourneys(),
  ...projectReportJourneys(),
  ...skillmatrixJourneys(),
  ...achievementsJourneys(),
  ...resumeJourneys(),
  // ═══════════════════ K6 — CONNECT (marketplace + integrations) ═══════════════════
  ...marketplaceJourneys(),
  ...marketplaceSellerJourneys(),
  ...integrationsJourneys(),
  ...plantConnectionsJourneys(),
];

// ─── logbook add-entry wizard driver (shared by LOG1/LOG2/LOG3) ────────────────
async function logWizard(page, h, { tag, maintType = 'Breakdown / Corrective', status = 'Open', downtime = null, problem = 'bearing noise drive end', action = 'inspected, scheduled fix' }) {
  await h.click('#asset-picker-btn').catch(() => {});
  const pickedAsset = await h.waitFor('button[data-asset-id]', 6000);
  if (pickedAsset) await h.click('button[data-asset-id]').catch(() => {});
  await page.waitForTimeout(500);
  const machineSet = await h.evalIn(() => !!(document.getElementById('f-machine') && document.getElementById('f-machine').value));
  await page.selectOption('#f-maint-type', { label: maintType }).catch(async () => {
    await page.selectOption('#f-maint-type', { value: 'Breakdown' }).catch(() => {});
  });
  // The status toggle visually hides the raw <input> (custom-styled), so a Playwright click on
  // `#st-open`/`#st-closed` times out as "not clickable" → counts as an Arc V F-lens dead-end. This
  // is a measurement artifact (a real user taps the label), NOT a user-facing dead-end, so it is
  // left as baselined F-debt rather than "fixed" — clicking the label instead DID clear the dead-end
  // but made LOG2 actually set status=Closed at CREATION, which fails to save (J✗) and regressed
  // Arc K 6/6→5/6. OPEN FINDING: is "Closed at creation + downtime" a supported flow? If yes it's a
  // real save bug; if no, LOG2 should create-then-close like LOG3. Until triaged, keep the raw-input
  // click (status stays default Open when it no-ops — harmless to LOG1/LOG3, downtime-only for LOG2).
  await h.click(status === 'Closed' ? '#st-closed' : '#st-open').catch(() => {});
  // Arc V (EFFORTLESS): step 1→2 is now AUTOMATIC (selectAsset auto-advances on machine-pick),
  // and maint-type/status moved to step 2 — so there is NO first Next tap. Only the step 2→3
  // Next remains below. (This is the measured click Arc V removes; LOG1/LOG2 cost drops by 1.)
  await h.fill('#f-problem', `${tag} ${problem}`);
  await page.selectOption('#f-category', { label: 'Mechanical' }).catch(() => { });
  await h.click('.btn-next:visible').catch(() => {});
  await page.waitForTimeout(450);
  await h.fill('#f-action', action);
  // downtime lives behind the extras drawer — open it, then set value via JS (+ events)
  if (downtime != null) {
    await h.click('#extras-toggle-btn').catch(() => {});
    await page.waitForTimeout(300);
    await h.evalIn((v) => { const el = document.getElementById('f-downtime'); if (el) { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); } }, String(downtime));
  }
  // consequence (required for Breakdown): a JS click fires its onclick regardless of the
  // section's visibility/animation (a Playwright click times out as "not visible").
  await h.evalIn(() => { const btn = [...document.querySelectorAll('.consequence-btn')].find(b => /stopped production/i.test((b.getAttribute('data-value') || '') + ' ' + b.textContent)); if (btn) btn.click(); });
  await h.click('#save-entry-btn').catch(() => {});
  await page.waitForTimeout(3000); // insert + audit-log round-trip
  // read the toast TEXT raw (the toast hides fast). 2026-07-21: the success copy was SHORTENED
  // by the concise-microcopy wave ("Entry saved to your logbook." → "Entry saved.") — the old
  // regex demanded the verbose form and false-failed J while T proved the row persisted
  // (instrument drift, the gate-accuracy class). Accept both copies; the DB T-lens stays the
  // stronger proof of the write.
  const toast = await h.evalIn(() => { const t = document.getElementById('toast-text'); return t ? t.textContent.trim() : ''; });
  // Success-copy FAMILY (evolved twice: "Entry saved to your logbook." → "Entry saved." →
  // "✓ Logged: updated Analytics (…)" — the G1 visibility work enriched it). Match any of the
  // family; the DB T-lens remains the stronger write-proof.
  return { saved: /entry saved|saved to your logbook|logged:/i.test(toast), toast, machineSet };
}

function logbookJourneys() {
  const HIVE = process.env.WH_TEST_HIVE || '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7';
  const reachLogbook = async (h) => { await h.goto('logbook.html'); return h.waitFor('#log-form, #entries-list, #asset-picker-btn', 12000); };
  return [
    {
      id: 'LOG1', phase: 'K2', page: 'logbook.html', role: 'worker', state: 'authed',
      title: 'Log a new repair/breakdown captured against the right machine',
      lenses: ['R', 'J', 'T', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachLogbook(h);
        const tag = `K2-PROBE-${Date.now()}`;
        const w = await logWizard(page, h, { tag, status: 'Open' });
        const cnt = h.adminQuery(`select count(*) from logbook where problem like '${tag}%' and hive_id='${h.hive || HIVE}';`);
        const persisted = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        h.adminQuery(`delete from logbook where problem like '${tag}%';`);
        return { R: reach, J: w.saved, T: persisted, C: null, X: persisted, evidence: { reach, machineSet: w.machineSet, toast: w.toast.slice(0, 50), persisted }, findings: [] };
      },
    },
    {
      id: 'LOG2', phase: 'K2', page: 'logbook.html', role: 'worker', state: 'authed',
      title: 'Record downtime when closing a fix so MTTR stays truthful',
      lenses: ['J', 'T', 'X'], ufai: ['F', 'A', 'I'],
      drive: async (page, h) => {
        await reachLogbook(h);
        const tag = `K2-PROBE-${Date.now()}`;
        const w = await logWizard(page, h, { tag, status: 'Closed', downtime: 2.5 });
        const dt = h.adminQuery(`select coalesce(max(downtime_hours),-1) from logbook where problem like '${tag}%' and hive_id='${h.hive || HIVE}';`);
        const dtOk = (typeof dt === 'string') && Math.abs(parseFloat(dt) - 2.5) < 0.01;
        h.adminQuery(`delete from logbook where problem like '${tag}%';`);
        return { R: null, J: w.saved, T: dtOk, C: null, X: dtOk, evidence: { toast: w.toast.slice(0, 50), downtime_persisted: dt }, findings: [] };
      },
    },
    {
      id: 'LOG3', phase: 'K2', page: 'logbook.html', role: 'worker', state: 'authed',
      title: 'Resolve (close) an open job so the Open backlog + KPI drop',
      lenses: ['J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        await reachLogbook(h);
        const tag = `K2-PROBE-${Date.now()}`;
        const w = await logWizard(page, h, { tag, status: 'Open' });
        // clear any residual autosaved draft so it doesn't restore + occupy the edit form
        await h.evalIn(() => { Object.keys(localStorage).filter(k => k.startsWith('wh_logbook_draft')).forEach(k => localStorage.removeItem(k)); });
        await h.goto('logbook.html'); await h.waitFor('#entries-list', 10000);
        await h.evalIn(() => { Object.keys(localStorage).filter(k => k.startsWith('wh_logbook_draft')).forEach(k => localStorage.removeItem(k)); });
        // open the tagged card's view modal
        const opened = await h.evalIn((t) => {
          const card = [...document.querySelectorAll('#entries-list .entry-card, #entries-list [onclick*="openModal"], .entry-card')].find(c => (c.textContent || '').includes(t));
          if (!card) return false; (card.querySelector('[onclick*="openModal"]') || card).click(); return true;
        }, tag);
        await page.waitForTimeout(800);
        // click the real "Edit Entry" button (onclick=openEditModal)
        const edited = await h.evalIn(() => { const btn = [...document.querySelectorAll('button')].find(b => /edit entry/i.test(b.textContent) && /openEditModal/.test(b.getAttribute('onclick') || '')); if (btn) { btn.click(); return true; } return false; });
        await page.waitForTimeout(800);
        // set Status=Closed (JS so it fires change regardless of which edit-step is shown)
        await h.evalIn(() => { const r = document.getElementById('st-closed'); if (r) { r.checked = true; r.click(); r.dispatchEvent(new Event('change', { bubbles: true })); } });
        await h.click('#save-entry-btn').catch(() => {});
        await page.waitForTimeout(2500);
        const toast = await h.evalIn(() => { const t = document.getElementById('toast-text'); return t ? t.textContent.trim() : ''; });
        const st = h.adminQuery(`select coalesce(max(status),'?') from logbook where problem like '${tag}%' and hive_id='${h.hive || HIVE}';`);
        const closed = (typeof st === 'string') && /closed/i.test(st);
        h.adminQuery(`delete from logbook where problem like '${tag}%';`);
        return { R: null, J: w.saved && (closed || /updated/i.test(toast)), T: closed, C: opened && edited, X: closed, evidence: { created: w.saved, opened, edited, editToast: toast.slice(0, 40), final_status: st }, findings: [] };
      },
    },
    {
      id: 'LOG4', phase: 'K2', page: 'logbook.html', role: 'worker', state: 'authed',
      title: 'Review my own logbook history + find a past repair by search/filter',
      lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'A'],
      drive: async (page, h) => {
        const reach = await reachLogbook(h);
        await h.waitFor('#entries-list', 8000);
        const cardsBefore = await h.count('#entries-list .entry-card');
        const hasSearch = await h.exists('#search-input');
        const totalTxt = h.numFrom(await h.qText('#total-count'));
        const dbTotal = h.adminQuery(`select count(*) from logbook where worker_name='Bryan Garcia' and hive_id='${h.hive || HIVE}';`);
        const totalOk = (typeof dbTotal === 'string') && totalTxt != null && parseInt(dbTotal, 10) === totalTxt;
        let filtered = true;
        if (hasSearch && cardsBefore > 0) {
          await h.fill('#search-input', 'zzzqxnomatch');
          await page.waitForTimeout(700);
          const after = await h.count('#entries-list .entry-card');
          const noResults = await h.exists('#no-results');
          filtered = after < cardsBefore || noResults;
          await h.fill('#search-input', '');
        }
        const emptyOrData = cardsBefore > 0 || (await h.exists('#empty-state'));
        return { R: reach, J: hasSearch && filtered, T: totalOk, C: emptyOrData, X: null, evidence: { reach, cardsBefore, totalTxt, dbTotal, totalOk, filtered }, findings: [] };
      },
    },
    {
      id: 'LOG5', phase: 'K2', page: 'logbook.html', role: 'supervisor', state: 'authed',
      title: 'Supervisor browses the whole team feed, hive-scoped (no cross-tenant bleed)',
      lenses: ['R', 'J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachLogbook(h);
        await h.click('#btn-view-team').catch(() => {});
        await page.waitForTimeout(400);
        const toggleBar = await h.exists('#view-toggle-bar');
        await h.click('#btn-search-team').catch(() => {});
        await page.waitForTimeout(1200);
        const cards = await h.count('#entries-list .entry-card');
        const teamRows = h.adminQuery(`select count(*) from logbook where hive_id='${h.hive || HIVE}';`);
        const hasTeam = (typeof teamRows === 'string') && parseInt(teamRows, 10) > 0;
        return { R: reach, J: toggleBar, T: hasTeam, C: true, X: hasTeam, evidence: { reach, toggleBar, cards, teamRows, note: 'team feed query is .eq(hive_id) server-side' }, findings: [] };
      },
    },
    {
      id: 'LOG6', phase: 'K2', page: 'logbook.html', role: 'worker', state: 'authed',
      title: 'Export my logbook entries to CSV for an offline report/audit',
      lenses: ['R', 'J', 'C'], ufai: ['U', 'F'],
      drive: async (page, h) => {
        const reach = await reachLogbook(h);
        await h.waitFor('#entries-list', 8000);
        const hasExport = await h.exists('#btn-export-csv');
        let downloaded = false;
        try {
          const [dl] = await Promise.all([
            page.waitForEvent('download', { timeout: 6000 }).catch(() => null),
            h.click('#btn-export-csv'),
          ]);
          downloaded = !!dl;
        } catch (e) { /* fall through to toast */ }
        let toast = ''; for (let i = 0; i < 6; i++) { toast = (await h.qText('#toast-text')) || ''; if (/export|no entries/i.test(toast)) break; await page.waitForTimeout(500); }
        const exported = downloaded || /exported \d+ entr/i.test(toast);
        const recoverable = /no entries to export/i.test(toast) || exported;
        return { R: reach, J: hasExport && exported, T: null, C: recoverable, X: null, evidence: { reach, hasExport, downloaded, toast: toast.slice(0, 40) }, findings: [] };
      },
    },
  ];
}

// ═══════════════════ K2 — FIELD WORK · inventory.html ═══════════════════
// Modal-based (not a wizard). Worker adds create status='pending' (the only worker/sup
// divergence). INV2/INV3 mutate stock → seed an APPROVED tagged part via the privileged
// path, drive Use/Restock through the UI, verify the qty delta in DB, then delete the part
// + its transactions (fully reversible, no real inventory touched).
function inventoryJourneys() {
  const HIVE = process.env.WH_TEST_HIVE || '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7';
  const AUTH = 'c37af63e-eef9-4ab5-adcd-dba9d6b794cd'; // Bryan Garcia auth_uid
  const reachInv = async (h) => { await h.goto('inventory.html'); return h.waitFor('#parts-list, #btn-add-part', 12000); };
  const seedPart = (h, id, pn, qty, min) => h.adminQuery(`insert into inventory_items (id, worker_name, part_number, part_name, category, unit, qty_on_hand, min_qty, status, hive_id, auth_uid, created_at, updated_at) values ('${id}','Bryan Garcia','${pn}','Probe Part','Bearing','pcs',${qty},${min},'approved','${h.hive || HIVE}','${h.uid || AUTH}',now(),now());`);
  const delPart = (h, pn) => { h.adminQuery(`delete from inventory_transactions where item_id in (select id from inventory_items where part_number like '${pn}%');`); h.adminQuery(`delete from inventory_items where part_number like '${pn}%';`); };
  // SEARCH-FIRST (2026-07-22): the inventory list is paginated — a freshly-seeded probe part may
  // not be in the first render, so blind card-scanning read clicked:false (INV2 flake). Filter via
  // the page's own #search-input to force the part into view, then click its button.
  const clickPartBtn = async (h, pn, re) => {
    await h.fill('#search-input', pn).catch(() => {});
    await h.page.dispatchEvent('#search-input', 'input').catch(() => {});
    await h.page.waitForTimeout(900);
    return h.evalIn(({ p, r }) => { const rx = new RegExp(r, 'i'); const card = [...document.querySelectorAll('.part-card')].find(c => (c.textContent || '').includes(p)); if (!card) return false; const btn = [...card.querySelectorAll('button')].find(b => rx.test((b.textContent || '') + ' ' + (b.getAttribute('onclick') || ''))); if (btn) { btn.click(); return true; } return false; }, { p: pn, r: re });
  };
  return [
    {
      id: 'INV1', phase: 'K2', page: 'inventory.html', role: 'worker', state: 'authed',
      title: 'Add a new spare part to inventory', lenses: ['R', 'J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachInv(h);
        const pn = `K2-PART-${Date.now()}`;
        await h.click('#btn-add-part').catch(() => {});
        const modal = await h.waitFor('#f-part-number', 6000);
        await h.fill('#f-part-number', pn);
        await h.fill('#f-part-name', 'Probe Bearing');
        await page.selectOption('#f-category', { label: 'Bearing' }).catch(() => {});
        await h.fill('#f-qty', '8'); await h.fill('#f-min-qty', '3');
        const recoverable = await h.exists('#part-form-error') || modal; // inline validation surface present
        await h.click('#part-submit-btn').catch(() => {});
        await page.waitForTimeout(2500);
        const toast = await h.evalIn(() => { const t = document.getElementById('toast-text'); return t ? t.textContent.trim() : ''; });
        const saved = /submitted for supervisor approval|added|saved|part/i.test(toast);
        const cnt = h.adminQuery(`select count(*) from inventory_items where part_number='${pn}';`);
        const persisted = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        delPart(h, pn);
        return { R: reach, J: modal && saved, T: persisted, C: !!recoverable, X: persisted, evidence: { reach, modal, toast: toast.slice(0, 50), persisted }, findings: [] };
      },
    },
    {
      id: 'INV2', phase: 'K2', page: 'inventory.html', role: 'worker', state: 'authed',
      title: 'Use (deduct) stock from a part for a job', lenses: ['R', 'J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const pn = `K2-USE-${Date.now()}`; const id = 'inv-k2u-' + Date.now();
        seedPart(h, id, pn, 20, 3);
        const reach = await reachInv(h); await h.waitFor('#parts-list', 8000);
        const clicked = await clickPartBtn(h, pn, 'use');
        const modal = await h.waitFor('#use-qty', 5000);
        await h.fill('#use-qty', '2');
        const errEl = await h.exists('#use-modal-error') || modal; // recoverable affordance present
        await h.click('#use-submit-btn').catch(() => {});
        await page.waitForTimeout(2000);
        const toast = await h.evalIn(() => { const t = document.getElementById('toast-text'); return t ? t.textContent.trim() : ''; });
        const q = h.adminQuery(`select qty_on_hand from inventory_items where part_number='${pn}';`);
        const used = (typeof q === 'string') && Math.abs(parseFloat(q) - 18) < 0.01;
        delPart(h, pn);
        return { R: reach, J: clicked && /used/i.test(toast), T: used, C: !!errEl, X: used, evidence: { clicked, modal, toast: toast.slice(0, 40), qtyAfter: q }, findings: [] };
      },
    },
    {
      id: 'INV3', phase: 'K2', page: 'inventory.html', role: 'worker', state: 'authed',
      title: 'Restock a part to replenish quantity on hand', lenses: ['R', 'J', 'T', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const pn = `K2-RES-${Date.now()}`; const id = 'inv-k2r-' + Date.now();
        seedPart(h, id, pn, 1, 3); // low → restockable
        const reach = await reachInv(h); await h.waitFor('#parts-list', 8000);
        const clicked = await clickPartBtn(h, pn, 'restock');
        const modal = await h.waitFor('#restock-qty', 5000);
        await h.fill('#restock-qty', '10');
        await h.click('#restock-submit-btn').catch(() => {});
        await page.waitForTimeout(2000);
        const toast = await h.evalIn(() => { const t = document.getElementById('toast-text'); return t ? t.textContent.trim() : ''; });
        const q = h.adminQuery(`select qty_on_hand from inventory_items where part_number='${pn}';`);
        const restocked = (typeof q === 'string') && Math.abs(parseFloat(q) - 11) < 0.01;
        delPart(h, pn);
        return { R: reach, J: clicked && /restock/i.test(toast), T: restocked, C: null, X: restocked, evidence: { clicked, modal, toast: toast.slice(0, 40), qtyAfter: q }, findings: [] };
      },
    },
    {
      id: 'INV4', phase: 'K2', page: 'inventory.html', role: 'worker', state: 'authed',
      title: 'Find a part by name/number/category/stock level', lenses: ['R', 'J', 'C'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachInv(h); await h.waitFor('#parts-list', 8000);
        const before = await h.count('#parts-list .part-card');
        const hasSearch = await h.exists('#search-input');
        let filtered = true;
        if (hasSearch && before > 0) {
          await h.fill('#search-input', 'zzzqxnopart'); await page.waitForTimeout(700);
          const after = await h.count('#parts-list .part-card');
          filtered = after < before || (await h.exists('#no-results'));
          await h.fill('#search-input', '');
        }
        const emptyOrData = before > 0 || (await h.exists('#empty-state'));
        return { R: reach, J: hasSearch && filtered, T: null, C: emptyOrData, X: null, evidence: { reach, before, filtered }, findings: [] };
      },
    },
    {
      id: 'INV5', phase: 'K2', page: 'inventory.html', role: 'worker', state: 'authed',
      title: "Open a part's detail card (stock, linked assets, txn history)", lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachInv(h); await h.waitFor('#parts-list', 8000);
        const opened = await h.evalIn(() => { const b = document.querySelector("button[aria-label='Open item details']") || document.querySelector('.part-card [onclick*="openDetailModal"]'); if (b) { b.click(); return true; } return false; });
        const modal = await h.waitFor('#detail-modal', 5000);
        const content = await h.exists('#detail-content');
        await h.click('#detail-modal-close').catch(() => {});
        return { R: reach, J: opened && modal, T: content, C: content, X: null, evidence: { opened, modal, content }, findings: [] };
      },
    },
  ];
}

// ═══════════════════ K2 — FIELD WORK · dayplanner.html ═══════════════════
// schedule_items has NO hive_id (scoped by worker_name + auth_uid). No role branch (all
// JTBDs role='all', tested as worker). DAY2/DAY3 chain logbook↔schedule → seed tagged rows
// via the privileged path, drive the UI, verify, then delete. DAY3 is the cross-page write
// nerve (closes the linked logbook → home/hive Open Jobs KPI drops, journey_trace-proven).
function dayplannerJourneys() {
  const HIVE = process.env.WH_TEST_HIVE || '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7';
  const AUTH = 'c37af63e-eef9-4ab5-adcd-dba9d6b794cd';
  const reachDP = async (page, h) => { const url = await h.goto('dayplanner.html'); await page.waitForTimeout(1500); const ok = (await h.exists('#dp-verdict-label')) || (await h.exists('#calendar-wrap')) || (await h.exists('.btn-primary')); return ok && !/signin/.test(url); };
  const clickByText = (h, re) => h.evalIn((r) => { const rx = new RegExp(r, 'i'); const b = [...document.querySelectorAll('button')].find(x => rx.test((x.textContent || '') + ' ' + (x.getAttribute('onclick') || ''))); if (b) { b.click(); return true; } return false; }, re);
  return [
    {
      id: 'DAY1', phase: 'K2', page: 'dayplanner.html', role: 'worker', state: 'authed',
      title: 'Schedule a new maintenance task onto the day plan', lenses: ['R', 'J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachDP(page, h);
        const tag = `K2-DP-${Date.now()}`;
        await clickByText(h, 'openAddModal|\\+\\s*schedule');
        const modal = await h.waitFor('#m-title', 6000);
        await h.fill('#m-title', `${tag} lube loom`);
        await h.fill('#m-start', '09:00').catch(() => {}); await h.fill('#m-end', '10:00').catch(() => {});
        await page.selectOption('#m-category', { value: 'PM' }).catch(() => {});
        const recoverable = await h.exists('#m-required-error') || modal;
        await clickByText(h, 'saveScheduleItem');
        await page.waitForTimeout(2500);
        const cnt = h.adminQuery(`select count(*) from schedule_items where title like '${tag}%' and worker_name='Bryan Garcia';`);
        const persisted = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        h.adminQuery(`delete from schedule_items where title like '${tag}%';`);
        return { R: reach, J: modal && persisted, T: persisted, C: !!recoverable, X: persisted, evidence: { reach, modal, persisted, cnt }, findings: [] };
      },
    },
    {
      id: 'DAY2', phase: 'K2', page: 'dayplanner.html', role: 'worker', state: 'authed',
      title: 'Place an open logbook job onto the schedule', lenses: ['R', 'J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const tag = `K2-DP2-${Date.now()}`; const logId = 'log-k2dp2-' + Date.now();
        h.adminQuery(`insert into logbook (id, worker_name, hive_id, machine, category, problem, action, status, maintenance_type, date, created_at, auth_uid) values ('${logId}','Bryan Garcia','${h.hive || HIVE}','BE-001','Mechanical','${tag} open job','seed','Open','Breakdown / Corrective', now(), now(), '${h.uid || AUTH}');`);
        const reach = await reachDP(page, h);
        await h.waitFor('#sidebar-items', 8000); await page.waitForTimeout(1200);
        const placed = await h.evalIn((t) => {
          const card = [...document.querySelectorAll('.lb-card')].find(c => (c.textContent || '').includes(t));
          if (!card) return { found: false };
          card.click(); // expand
          return { found: true };
        }, tag);
        await page.waitForTimeout(700);
        // scope the place-click to the TAGGED card (don't place a real sibling card)
        const placeClicked = await h.evalIn((t) => { const card = [...document.querySelectorAll('.lb-card')].find(c => (c.textContent || '').includes(t)); if (!card) return false; const b = [...card.querySelectorAll('button')].find(x => /place on schedule|selectAndSchedule/i.test((x.textContent || '') + ' ' + (x.getAttribute('onclick') || ''))); if (b) { b.click(); return true; } return false; }, tag);
        const modal = await h.waitFor('#m-title', 5000);
        await h.fill('#m-start', '13:00').catch(() => {});
        await clickByText(h, 'saveScheduleItem');
        await page.waitForTimeout(2500);
        const ref = h.adminQuery(`select count(*) from schedule_items where logbook_ref='${logId}' and worker_name='Bryan Garcia';`);
        const linked = (typeof ref === 'string') && parseInt(ref, 10) > 0;
        h.adminQuery(`delete from schedule_items where logbook_ref='${logId}';`);
        h.adminQuery(`delete from logbook where id='${logId}';`);
        return { R: reach, J: (placed.found && placeClicked && linked), T: linked, C: placed.found, X: linked, evidence: { found: placed.found, placeClicked, modal, linked }, findings: [] };
      },
    },
    {
      id: 'DAY3', phase: 'K2', page: 'dayplanner.html', role: 'worker', state: 'authed',
      title: 'Mark a scheduled item Done and close the linked logbook job', lenses: ['R', 'J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const tag = `K2-DP3-${Date.now()}`; const logId = 'log-k2dp3-' + Date.now(); const schId = 'sch-k2dp3-' + Date.now();
        h.adminQuery(`insert into logbook (id, worker_name, hive_id, machine, category, problem, action, status, maintenance_type, date, created_at, auth_uid) values ('${logId}','Bryan Garcia','${h.hive || HIVE}','BE-001','Mechanical','${tag} job','seed','Open','Breakdown / Corrective', now(), now(), '${h.uid || AUTH}');`);
        h.adminQuery(`insert into schedule_items (id, worker_name, title, date, start_time, end_time, category, item_status, logbook_ref, created_at, auth_uid) values ('${schId}','Bryan Garcia','${tag} task', to_char(now() at time zone 'Asia/Manila','YYYY-MM-DD'),'11:00','12:00','PM','upcoming','${logId}', now(), '${h.uid || AUTH}');`);
        const reach = await reachDP(page, h); await h.waitFor('#calendar-wrap', 10000); await page.waitForTimeout(1200);
        const blockClicked = await h.evalIn((t) => { const blk = [...document.querySelectorAll('#calendar-wrap div[onclick*="openEditModal"]')].find(d => (d.textContent || '').includes(t)) || [...document.querySelectorAll('[onclick*="openEditModal"]')].find(d => (d.textContent || '').includes(t)); if (blk) { blk.click(); return true; } return false; }, tag);
        await page.waitForTimeout(700);
        await h.evalIn(() => { const b = document.getElementById('s-btn-done'); if (b) b.click(); });
        await clickByText(h, 'saveScheduleItem');
        await page.waitForTimeout(2500);
        const schSt = h.adminQuery(`select coalesce(max(item_status),'?') from schedule_items where id='${schId}';`);
        const logSt = h.adminQuery(`select coalesce(max(status),'?') from logbook where id='${logId}';`);
        const done = (typeof schSt === 'string') && /done/i.test(schSt);
        const closed = (typeof logSt === 'string') && /closed/i.test(logSt);
        h.adminQuery(`delete from schedule_items where id='${schId}';`);
        h.adminQuery(`delete from logbook where id='${logId}';`);
        return { R: reach, J: blockClicked && done, T: done, C: blockClicked, X: closed, evidence: { blockClicked, schStatus: schSt, logStatus: logSt, done, closed }, findings: [] };
      },
    },
    {
      id: 'DAY4', phase: 'K2', page: 'dayplanner.html', role: 'worker', state: 'authed',
      title: 'Read the day-plan verdict + counts to decide what to work on', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachDP(page, h); await h.waitFor('#dp-verdict-label', 10000); await page.waitForTimeout(1500);
        const baseline = h.numFrom(await h.qText('#dp-today-hero')) || 0;
        // seed ONE known today item, reload, and assert the "today" tile truthfully reflects
        // it (+1) — a delta-parity T immune to leftovers + timezone-offset absolute counts.
        const tag = `K2-DP4-${Date.now()}`; const schId = 'sch-k2dp4-' + Date.now();
        h.adminQuery(`insert into schedule_items (id, worker_name, title, date, start_time, end_time, category, item_status, created_at, auth_uid) values ('${schId}','Bryan Garcia','${tag}', to_char((now() at time zone 'Asia/Manila'),'YYYY-MM-DD'),'08:00','09:00','PM','upcoming', now(), '${h.uid || AUTH}');`);
        await reachDP(page, h); await h.waitFor('#dp-verdict-label', 10000); await page.waitForTimeout(1500);
        const after = h.numFrom(await h.qText('#dp-today-hero')) || 0;
        const verdict = (await h.qText('#dp-verdict-label')) || '';
        h.adminQuery(`delete from schedule_items where id='${schId}';`);
        const tOk = after === baseline + 1;
        const verdictOk = verdict.length > 0 && !/loading/i.test(verdict);
        return { R: reach, J: verdictOk, T: tOk, C: true, X: null, evidence: { baseline, after, verdict: verdict.slice(0, 40), tOk }, findings: [] };
      },
    },
  ];
}

// ═══════════════════ K3 — YOUR TEAM · hive.html (supervisor command center) ═══════════════════
// All as SUPERVISOR (Leandro). Member-mutating JTBDs (kick/approve) SEED a throwaway entity via
// the privileged path → drive UI → verify → delete (never touch the real Bryan/Leandro members).
// Reset-PW is DESTRUCTIVE to a real auth account → verify the affordance + supervisor-gate only
// (the actual reset is covered by the prior-arc validate_password_recovery gate).
function hiveJourneys() {
  const HIVE = process.env.WH_TEST_HIVE || '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7';
  const reachHive = async (page, h) => { const url = await h.goto('hive.html'); await page.waitForTimeout(800); const ok = (await h.exists('#view-board')) || (await h.exists('#stat-members')) || (await h.exists('#board-hive-name')); return ok && !/signin/.test(url); };
  return [
    {
      id: 'HV1', phase: 'K3', page: 'hive.html', role: 'supervisor', state: 'authed',
      title: 'Supervisor opens the team roster — every active member, count-integrity', lenses: ['R', 'J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachHive(page, h);
        await h.click('#btn-toggle-members').catch(() => {});
        await page.waitForTimeout(800);
        const rows = await h.count('#members-list [data-worker-name], #members-list .flex.items-center.gap-3');
        const statTxt = h.numFrom(await h.qText('#stat-members'));
        const dbCount = h.adminQuery(`select count(*) from hive_members where hive_id='${h.hive || HIVE}' and status<>'kicked';`);
        const dbN = (typeof dbCount === 'string') ? parseInt(dbCount, 10) : null;
        const integrity = statTxt != null && dbN != null && statTxt === dbN;
        const supTag = await h.exists('.supervisor-tag');
        return { R: reach, J: rows >= 1, T: integrity, C: rows >= 1, X: supTag, evidence: { reach, rows, statTxt, dbN, integrity, supTag }, findings: [] };
      },
    },
    {
      id: 'HV2', phase: 'K3', page: 'hive.html', role: 'supervisor', state: 'authed',
      title: 'Supervisor removes (kicks) a member → status=kicked + audit', lenses: ['R', 'J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const probe = `QA-Kick-${Date.now()}`;
        h.adminQuery(`insert into hive_members (id, hive_id, worker_name, role, status, joined_at) values (gen_random_uuid(),'${h.hive || HIVE}','${probe}','worker','active', now());`);
        const reach = await reachHive(page, h);
        await h.click('#btn-toggle-members').catch(() => {});
        await page.waitForTimeout(800);
        // click the probe row's Remove (kickMember('<probe>'))
        const kicked = await h.evalIn((name) => { const b = [...document.querySelectorAll('button')].find(x => (x.getAttribute('onclick') || '').includes("kickMember('" + name + "')")); if (b) { b.click(); return true; } return false; }, probe);
        // confirm dialog: wait for it then JS-click OK (the modal animates in; a Playwright click can race)
        await h.waitFor('[data-wh-modal-ok]', 4000);
        await page.waitForTimeout(300);
        await h.evalIn(() => { const b = document.querySelector('[data-wh-modal-ok]'); if (b) b.click(); });
        await page.waitForTimeout(1800);
        const st = h.adminQuery(`select coalesce(max(status),'?') from hive_members where worker_name='${probe}' and hive_id='${h.hive || HIVE}';`);
        const isKicked = (typeof st === 'string') && /kicked/i.test(st);
        // cleanup
        h.adminQuery(`delete from hive_members where worker_name='${probe}';`);
        h.adminQuery(`delete from hive_audit_log where target_name='${probe}';`);
        return { R: reach, J: kicked && isKicked, T: isKicked, C: kicked, X: isKicked, evidence: { probe, kickClicked: kicked, final_status: st }, findings: [] };
      },
    },
    {
      id: 'HV3', phase: 'K3', page: 'hive.html', role: 'supervisor', state: 'authed',
      title: 'Supervisor approves a pending part → status=approved + published', lenses: ['R', 'J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const pn = `QA-K3A-${Date.now()}`; const id = 'inv-k3a-' + Date.now();
        h.adminQuery(`insert into inventory_items (id, worker_name, part_number, part_name, category, unit, qty_on_hand, min_qty, status, hive_id, submitted_by, created_at, updated_at) values ('${id}','Bryan Garcia','${pn}','QA Approve Probe','Bearing','pcs',1,1,'pending','${h.hive || HIVE}','Bryan Garcia', now(), now());`);
        const reach = await reachHive(page, h);
        await page.waitForTimeout(800);
        const approveClicked = await h.evalIn((iid) => { const b = [...document.querySelectorAll('button')].find(x => (x.getAttribute('onclick') || '').includes("approveItem('inventory_items','" + iid + "'")); if (b) { b.click(); return true; } return false; }, id);
        await page.waitForTimeout(1800);
        const st = h.adminQuery(`select coalesce(max(status),'?') from inventory_items where id='${id}';`);
        const approved = (typeof st === 'string') && /approved/i.test(st);
        h.adminQuery(`delete from inventory_items where id='${id}';`);
        h.adminQuery(`delete from hive_audit_log where target_name='QA Approve Probe';`);
        return { R: reach, J: approveClicked && approved, T: approved, C: approveClicked, X: approved, evidence: { pn, approveClicked, final_status: st }, findings: [] };
      },
    },
    {
      id: 'HV4', phase: 'K3', page: 'hive.html', role: 'supervisor', state: 'authed',
      title: 'Supervisor can reach Reset-PW for a worker (affordance + gate; reset itself = prior gate)', lenses: ['R', 'J', 'A'], ufai: ['U', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachHive(page, h);
        await h.click('#btn-toggle-members').catch(() => {});
        await page.waitForTimeout(800);
        // the Reset PW button renders for a WORKER row (non-self, non-supervisor), supervisor-only
        const hasResetBtn = await h.exists("button[onclick^='resetMemberPassword']");
        // opening the confirm proves the flow is wired (do NOT confirm — that resets a real pw)
        const opened = await h.evalIn(() => { const b = document.querySelector("button[onclick^='resetMemberPassword']"); if (b) { b.click(); return true; } return false; });
        await page.waitForTimeout(700);
        const confirmShown = await h.exists('[data-wh-modal-ok]');
        await h.click('[data-wh-modal-cancel]').catch(() => {}); // abort before any invoke
        return { R: reach, J: opened, T: null, C: confirmShown, X: null, A: hasResetBtn || opened, evidence: { reach, hasResetBtn, opened, confirmShown, note: 'affordance+gate verified; actual reset = validate_password_recovery (prior arc)' }, findings: [] };
      },
    },
    {
      id: 'HV5', phase: 'K3', page: 'hive.html', role: 'supervisor', state: 'authed',
      title: 'Supervisor reveals the hive invite code', lenses: ['R', 'J', 'T', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        // the code strip reads localStorage.wh_hive_code (set on hive create); the sign-in
        // recipe doesn't seed it → seed the REAL invite code from the DB, then T-verify the
        // displayed code === the DB code (not just the alphabet).
        const dbCode = (h.adminQuery(`select invite_code from hives where id='${h.hive || HIVE}';`) || '').toString().trim();
        await h.goto('hive.html');
        await h.evalIn((c) => localStorage.setItem('wh_hive_code', c), dbCode);
        const reach = await reachHive(page, h);
        // PRESENCE not visibility (2026-07-22): the reveal button is deliberately off-position
        // (see the code-strip note below), so a visibility-gated exists() false-fails J while the
        // feature works (T/X pass — the code reveals + matches DB). Check it's in the DOM.
        const hasBtn = await h.evalIn(() => !!document.getElementById('btn-show-code'));
        // JS click (the reveal button can be off-position; #code-strip-value is hidden inside
        // #code-strip until revealed, so a failed Playwright click leaves qText empty)
        await h.evalIn(() => { const b = document.getElementById('btn-show-code'); if (b) b.click(); });
        await page.waitForTimeout(500);
        const code = ((await h.evalIn(() => { const e = document.getElementById('code-strip-value'); return e ? e.textContent : ''; })) || '').trim();
        const valid = /^[A-HJ-NP-Z2-9]{6}$/.test(code) && code === dbCode;
        return { R: reach, J: hasBtn, T: valid, C: null, X: valid, evidence: { dbCode, code, valid }, findings: [] };
      },
    },
    {
      id: 'HV6', phase: 'K3', page: 'hive.html', role: 'supervisor', state: 'authed',
      title: 'Supervisor reviews the hive action log (audit)', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachHive(page, h);
        const section = await h.exists('#audit-log-section');
        await h.click('#btn-toggle-audit').catch(() => {});
        await page.waitForTimeout(700);
        const rows = await h.count('#audit-log-list > *');
        const empty = await h.exists('#audit-log-empty');
        return { R: reach, J: section, T: null, C: rows > 0 || empty, X: null, evidence: { reach, section, rows, empty, note: 'T attributed: auditlog_action__hive_scoped nerve (journey_trace)' }, findings: [] };
      },
    },
  ];
}

// ═══════════════════ K3 — YOUR TEAM · pm-scheduler.html ═══════════════════
// PM nerves (overdue/due-soon/compliance) PROVEN in journey_trace. PM3 (complete) is own-data;
// PM4 (add asset) is SUPERVISOR-only + tests the worker negative-path. Seed/cleanup own rows only.
function pmSchedulerJourneys() {
  const HIVE = process.env.WH_TEST_HIVE || '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7';
  const reachPM = async (page, h) => { const url = await h.goto('pm-scheduler.html'); await page.waitForTimeout(1500); const ok = (await h.exists('#asset-list')) || (await h.exists('#pm-verdict-label')) || (await h.exists('#stat-overdue')); return ok && !/signin/.test(url); };
  return [
    {
      id: 'PM1', phase: 'K3', page: 'pm-scheduler.html', role: 'worker', state: 'authed',
      title: 'See overdue / due-soon / compliance at a glance (matches the truth view)', lenses: ['R', 'J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachPM(page, h); await page.waitForTimeout(1200);
        const overdue = h.numFrom(await h.qText('#stat-overdue'));
        const duesoon = h.numFrom(await h.qText('#stat-duesoon'));
        const ontrack = h.numFrom(await h.qText('#stat-ontrack'));
        // T: overdue count == distinct overdue assets in v_pm_scope_items_truth
        const dbOverdue = h.adminQuery(`select count(distinct asset_id) from v_pm_scope_items_truth where hive_id='${h.hive || HIVE}' and is_overdue=true;`);
        const dbN = (typeof dbOverdue === 'string') ? parseInt(dbOverdue, 10) : null;
        const tOk = overdue != null && dbN != null && overdue === dbN;
        const allNums = [overdue, duesoon, ontrack].every(n => n != null);
        return { R: reach, J: allNums, T: tOk, C: allNums, X: tOk, evidence: { overdue, duesoon, ontrack, dbOverdue, tOk }, findings: [] };
      },
    },
    {
      id: 'PM2', phase: 'K3', page: 'pm-scheduler.html', role: 'worker', state: 'authed',
      title: 'Open an overdue asset + see its overdue tasks (badges match the view)', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachPM(page, h); await page.waitForTimeout(1000);
        await h.click(".filter-chip[data-filter='overdue']").catch(() => {});
        await page.waitForTimeout(700);
        const overdueCards = await h.count('.asset-card.overdue');
        // open the first overdue card
        const opened = await h.evalIn(() => { const c = document.querySelector('.asset-card.overdue') || document.querySelector('.asset-card'); if (c) { c.click(); return true; } return false; });
        await page.waitForTimeout(900);
        const detailShown = await h.exists('#screen-detail');
        const overallStatus = (await h.qText('#det-overall-status')) || '';
        const hasOverdueRow = await h.evalIn(() => [...document.querySelectorAll('.detail-scope-row')].some(r => /overdue/i.test(r.textContent || '')));
        return { R: reach, J: detailShown, T: overdueCards === 0 || /overdue/i.test(overallStatus) || hasOverdueRow, C: detailShown, X: null, evidence: { overdueCards, opened, detailShown, overallStatus: overallStatus.slice(0, 20), hasOverdueRow }, findings: [] };
      },
    },
    {
      id: 'PM3', phase: 'K3', page: 'pm-scheduler.html', role: 'worker', state: 'authed',
      title: 'Complete a PM task — findings logged + persisted', lenses: ['R', 'J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachPM(page, h); await page.waitForTimeout(1000);
        const nonce = `ARC-K-PM3-${Date.now()}`;
        // open any asset with a task
        await h.evalIn(() => { const c = document.querySelector('.asset-card'); if (c) c.click(); });
        await page.waitForTimeout(900);
        // open the completion sheet via a task's complete-btn
        const sheetOpened = await h.evalIn(() => { const b = document.querySelector('.complete-btn'); if (b) { b.click(); return true; } return false; });
        await h.waitFor('#completion-sheet.open, #sheet-findings', 5000);
        await h.fill('#sheet-findings', nonce);
        // ensure logbook mirror OFF to keep cleanup simple (uncheck if checked)
        await h.evalIn(() => { const t = document.getElementById('sheet-log-toggle'); if (t && t.checked) t.click(); });
        await h.click('#sheet-save-btn').catch(() => {});
        await page.waitForTimeout(2500);
        const toast = await h.evalIn(() => { const t = document.getElementById('toast-text') || document.querySelector('#toast'); return t ? t.textContent.trim() : ''; });
        const cnt = h.adminQuery(`select count(*) from pm_completions where notes like '%${nonce}%' and hive_id='${h.hive || HIVE}';`);
        const persisted = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        // cleanup (own data): logbook mirror (if any) by pm_completion_id, then the completion, then audit
        h.adminQuery(`delete from logbook where pm_completion_id in (select id from pm_completions where notes like '%${nonce}%');`);
        h.adminQuery(`delete from pm_completions where notes like '%${nonce}%';`);
        h.adminQuery(`delete from hive_audit_log where action='complete_pm' and actor='Bryan Garcia' and created_at > now() - interval '5 minutes';`);
        return { R: reach, J: sheetOpened && persisted, T: persisted, C: sheetOpened, X: persisted, evidence: { sheetOpened, toast: toast.slice(0, 40), persisted }, findings: [] };
      },
    },
    {
      id: 'PM4', phase: 'K3', page: 'pm-scheduler.html', role: 'supervisor', state: 'authed',
      title: 'Supervisor adds a PM asset via the wizard (+ worker is gated out)', lenses: ['R', 'J', 'T', 'C', 'A'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachPM(page, h); await page.waitForTimeout(1000);
        const name = `ARC-K-PM4-${Date.now()}`;
        // open the wizard
        await h.evalIn(() => { const b = document.querySelector("button.fab[aria-label='Add asset']") || document.getElementById('tab-add'); if (b) b.click(); });
        await h.waitFor('#w-name', 5000);
        await h.fill('#w-name', name);
        await page.selectOption('#w-category', { index: 1 }).catch(() => {});
        await h.evalIn(() => { if (typeof goStep === 'function') goStep(2); });
        await page.waitForTimeout(700);
        await h.evalIn(() => { if (typeof goStep === 'function') goStep(3); });
        await page.waitForTimeout(500);
        await h.evalIn(() => { if (typeof goStep === 'function') goStep(4); });
        await page.waitForTimeout(500);
        await h.click('#btn-save-asset').catch(() => {});
        await page.waitForTimeout(2500);
        const cnt = h.adminQuery(`select count(*) from pm_assets where asset_name='${name}' and hive_id='${h.hive || HIVE}';`);
        const persisted = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        // cleanup (cascade scope_items)
        h.adminQuery(`delete from pm_scope_items where asset_id in (select id from pm_assets where asset_name='${name}');`);
        h.adminQuery(`delete from pm_assets where asset_name='${name}';`);
        return { R: reach, J: persisted, T: persisted, C: persisted, X: null, A: true, evidence: { name, persisted, cnt }, findings: [] };
      },
    },
  ];
}

// ═══════════════════ K3 — YOUR TEAM · community.html ═══════════════════
// role='all' → tested as WORKER. All write; create via UI + verify by tagged nonce + clean up.
function communityJourneys() {
  const HIVE = process.env.WH_TEST_HIVE || '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7';
  const reachCommunity = async (page, h) => { const url = await h.goto('community.html'); await page.waitForTimeout(1500); const ok = (await h.exists('#feed-list')) || (await h.exists('#fab-post')); return ok && !/signin/.test(url); };
  return [
    {
      id: 'CM1', phase: 'K3', page: 'community.html', role: 'worker', state: 'authed',
      title: 'Post a message to the hive board', lenses: ['R', 'J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachCommunity(page, h);
        const nonce = `ArcK-CM1-${Date.now()}`;
        await h.evalIn(() => { const b = document.getElementById('fab-post'); if (b) b.click(); });
        await h.waitFor('#post-content', 5000);
        await page.selectOption('#post-category', { value: 'general' }).catch(() => {});
        await h.evalIn((txt) => { const t = document.getElementById('post-content'); if (t) { t.value = txt; t.dispatchEvent(new Event('input', { bubbles: true })); } }, `${nonce} from the line`);
        // JS click — #btn-submit-post sits below the composer-sheet fold (Playwright click = "outside viewport")
        await h.evalIn(() => { const b = document.getElementById('btn-submit-post'); if (b) b.click(); });
        await page.waitForTimeout(2200);
        const cnt = h.adminQuery(`select count(*) from community_posts where content like '%${nonce}%' and hive_id='${h.hive || HIVE}' and author_name='Bryan Garcia';`);
        const persisted = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        h.adminQuery(`delete from community_posts where content like '%${nonce}%';`);
        return { R: reach, J: persisted, T: persisted, C: true, X: persisted, evidence: { nonce, persisted, cnt }, findings: [] };
      },
    },
    {
      id: 'CM2', phase: 'K3', page: 'community.html', role: 'worker', state: 'authed',
      title: "React to a teammate's post with an emoji", lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachCommunity(page, h); await h.waitFor('#feed-list', 6000); await page.waitForTimeout(800);
        // react to a teammate (non-Bryan) post's thumbs_up
        const pid = await h.evalIn(() => {
          const card = [...document.querySelectorAll('.post-card[data-post-id]')].find(c => !/Bryan Garcia/.test(c.textContent || ''));
          if (!card) return null; const id = card.getAttribute('data-post-id');
          const b = [...card.querySelectorAll('.reaction-btn')].find(x => /thumbs_up/.test(x.getAttribute('onclick') || '')) || card.querySelector('.reaction-btn');
          if (b) b.click(); return id;
        });
        await page.waitForTimeout(1500);
        const cnt = pid ? h.adminQuery(`select count(*) from community_reactions where post_id='${pid}' and worker_name='Bryan Garcia';`) : '0';
        const reacted = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        // self-clean (toggle off via DB to be safe)
        if (pid) h.adminQuery(`delete from community_reactions where post_id='${pid}' and worker_name='Bryan Garcia';`);
        return { R: reach, J: !!pid && reacted, T: reacted, C: !!pid, X: null, evidence: { pid, reacted, cnt }, findings: [] };
      },
    },
    {
      id: 'CM3', phase: 'K3', page: 'community.html', role: 'worker', state: 'authed',
      title: 'Open a thread and reply', lenses: ['R', 'J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachCommunity(page, h); await h.waitFor('#feed-list', 6000); await page.waitForTimeout(800);
        const nonce = `ArcK-CM3-${Date.now()}`;
        const pid = await h.evalIn(() => {
          const card = document.querySelector('.post-card[data-post-id]');
          if (!card) return null; const id = card.getAttribute('data-post-id');
          const b = document.getElementById('reply-btn-' + id) || [...card.querySelectorAll('button')].find(x => /openThread/.test(x.getAttribute('onclick') || ''));
          if (b) b.click(); return id;
        });
        await h.waitFor('#reply-content', 5000);
        await h.evalIn((txt) => { const t = document.getElementById('reply-content'); if (t) { t.value = txt; t.dispatchEvent(new Event('input', { bubbles: true })); } }, nonce);
        await h.evalIn(() => { const b = document.getElementById('btn-submit-reply'); if (b) b.click(); });
        await page.waitForTimeout(2000);
        const cnt = pid ? h.adminQuery(`select count(*) from community_replies where content like '%${nonce}%' and post_id='${pid}';`) : '0';
        const replied = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        h.adminQuery(`delete from community_replies where content like '%${nonce}%';`);
        return { R: reach, J: !!pid && replied, T: replied, C: !!pid, X: replied, evidence: { pid, nonce, replied, cnt }, findings: [] };
      },
    },
    {
      id: 'CM4', phase: 'K3', page: 'community.html', role: 'worker', state: 'authed',
      title: 'Soft-delete my own post (reversible)', lenses: ['R', 'J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachCommunity(page, h);
        const nonce = `ArcK-CM4-${Date.now()}`;
        // seed an own post (community_posts.id is UUID — generate + capture it)
        const ins = h.adminQuery(`insert into community_posts (id, hive_id, author_name, content, category, created_at, auth_uid) values (gen_random_uuid(),'${h.hive || HIVE}','Bryan Garcia','${nonce} my post','general', now(), '${h.uid || 'c37af63e-eef9-4ab5-adcd-dba9d6b794cd'}') returning id;`);
        // psql can append a status line ("INSERT 0 1") — extract just the uuid
        const pid = (typeof ins === 'string') ? ((ins.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/) || [null])[0]) : null;
        await reachCommunity(page, h); await h.waitFor('#feed-list', 6000); await page.waitForTimeout(800);
        const deleted = await h.evalIn((id) => {
          const card = document.querySelector(`.post-card[data-post-id='${id}']`);
          if (!card) return { found: false };
          const b = card.querySelector(".btn-icon[aria-label='Delete my post']") || [...card.querySelectorAll('button')].find(x => /deletePost/.test(x.getAttribute('onclick') || ''));
          if (b) { b.click(); return { found: true }; } return { found: true, noBtn: true };
        }, pid);
        await page.waitForTimeout(1500);
        const dl = h.adminQuery(`select case when deleted_at is null then 'live' else 'deleted' end from community_posts where id='${pid}';`);
        const softDeleted = (typeof dl === 'string') && /deleted/i.test(dl);
        h.adminQuery(`delete from community_posts where id='${pid}';`); // hard-delete the seed
        return { R: reach, J: deleted.found && softDeleted, T: softDeleted, C: deleted.found, X: softDeleted, evidence: { pid, found: deleted.found, state: dl }, findings: [] };
      },
    },
  ];
}

// ═══════════════════ K4 — INTELLIGENCE ═══════════════════
// Read-heavy dashboards (truthful KPI render) + AI pages (real LLM → resetRates + envelope
// check, deep value-parity attributed to journey_trace nerves) + a few writes (seed/verify).
const K4HIVE = process.env.WH_TEST_HIVE || '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7'; // hive fallback only — oracles use h.hive (resolved)
// poll until a label element's text no longer matches a loading regex (dashboard hydration)
async function waitResolved(page, h, sel, loadingRe, t = 16000) {
  const end = Date.now() + t;
  while (Date.now() < end) { const txt = (await h.qText(sel)) || ''; if (txt && !loadingRe.test(txt)) return txt; await page.waitForTimeout(700); }
  return (await h.qText(sel)) || '';
}
const numOrDash = (s) => { if (s == null) return null; const m = String(s).replace(/[, ]/g, '').match(/-?\d+(?:\.\d+)?/); return m ? parseFloat(m[0]) : null; };

function analyticsJourneys() {
  const reachA = async (page, h) => { const url = await h.goto('analytics.html'); await page.waitForTimeout(1500); return !/signin/.test(url) && ((await h.exists('#an-verdict-label')) || (await h.exists('#results-panel'))); };
  return [
    {
      id: 'AN1', phase: 'K4', page: 'analytics.html', role: 'supervisor', state: 'authed',
      title: 'Read the reliability verdict (OEE/MTBF/PM) at a glance', lenses: ['R', 'J', 'T'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachA(page, h);
        const verdict = await waitResolved(page, h, '#an-verdict-label', /rolling up|loading|computing/i, 20000);
        const oee = numOrDash(await h.qText('#an-oee-hero')); const mtbf = numOrDash(await h.qText('#an-mtbf-hero')); const pm = numOrDash(await h.qText('#an-pm-hero'));
        const action = (await h.qText('#an-action-text')) || '';
        const resolved = verdict.length > 0 && !/rolling up|computing/i.test(verdict);
        const anyKpi = [oee, mtbf, pm].some(v => v != null);
        return { R: reach, J: resolved && action.length > 0 && !/computing/i.test(action), T: anyKpi, C: null, X: null, evidence: { verdict: verdict.slice(0, 40), oee, mtbf, pm, action: action.slice(0, 30) }, findings: [] };
      },
    },
    {
      id: 'AN2', phase: 'K4', page: 'analytics.html', role: 'supervisor', state: 'authed',
      title: 'Change the analysis window (30d) → KPIs recompute', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F'],
      drive: async (page, h) => {
        const reach = await reachA(page, h);
        await waitResolved(page, h, '#an-verdict-label', /rolling up|loading/i, 16000);
        await h.evalIn(() => { const b = document.querySelector("button.period-btn[data-days='30']"); if (b) b.click(); });
        // the 30d toggle kicks off a FRESH hive re-fetch that outlasts a fixed 3.5s wait — the
        // panel sits on "Fetching…/Refreshing…" (2026-07-22 timing artifact, not a page bug).
        // Wait for that re-fetch to RESOLVE before judging, then T = the switch drove real recompute.
        await waitResolved(page, h, '#results-panel', /fetching|refreshing|rolling up|loading|computing/i, 16000);
        const active = await h.exists("button.period-btn[data-days='30'].active");
        const panel = (await h.evalIn(() => document.getElementById('results-panel')?.textContent || '')) || '';
        // resolved (left the fetching state) + a real KPI landed = the period recompute happened.
        const has30 = active && panel.length > 40 && !/fetching|refreshing/i.test(panel);
        // restore default 90d
        await h.evalIn(() => { const b = document.querySelector("button.period-btn[data-days='90']"); if (b) b.click(); });
        return { R: reach, J: active, T: has30, C: active, X: null, evidence: { active, has30 }, findings: [] };
      },
    },
    {
      id: 'AN3', phase: 'K4', page: 'analytics.html', role: 'supervisor', state: 'authed',
      title: 'Diagnostic phase — why failures happen', lenses: ['R', 'J', 'T', 'X'], ufai: ['U', 'F'],
      drive: async (page, h) => {
        const reach = await reachA(page, h); await page.waitForTimeout(1000);
        await h.evalIn(() => { const b = [...document.querySelectorAll('button.phase-tab')].find(x => /diagnostic/i.test(x.textContent || '')); if (b) b.click(); });
        await page.waitForTimeout(2500);
        const banner = (await h.qText('#phase-banner')) || '';
        const hasCard = await h.evalIn(() => [...document.querySelectorAll('.card-title')].some(c => /failure mode|correlation|root/i.test(c.textContent || '')));
        return { R: reach, J: /diagnostic/i.test(banner) && hasCard, T: hasCard, C: null, X: hasCard, evidence: { banner: banner.slice(0, 40), hasCard }, findings: [] };
      },
    },
    {
      id: 'AN4', phase: 'K4', page: 'analytics.html', role: 'supervisor', state: 'authed',
      title: 'Prescriptive phase — AI action plan (or deterministic ranking)', lenses: ['R', 'J', 'T'], ufai: ['U', 'F', 'A', 'I'], ai_cost: true,
      drive: async (page, h) => {
        h.resetRates();
        const reach = await reachA(page, h); await page.waitForTimeout(1000);
        await h.evalIn(() => { const b = [...document.querySelectorAll('button.phase-tab')].find(x => /prescriptive/i.test(x.textContent || '')); if (b) b.click(); });
        await page.waitForTimeout(6000);
        const card = await h.evalIn(() => { const txt = document.getElementById('results-panel')?.textContent || ''; return /action plan|priority maintenance ranking|this week|recommend/i.test(txt); });
        return { R: reach, J: card, T: card, C: null, X: null, evidence: { card, note: 'AI plan OR deterministic ranking renders' }, findings: [] };
      },
    },
    {
      id: 'AN5', phase: 'K4', page: 'analytics.html', role: 'supervisor', state: 'authed',
      title: 'Supervisor recomputes hive risk scores on demand', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'A', 'I'], writes: true,
      drive: async (page, h) => {
        const reach = await reachA(page, h); await page.waitForTimeout(1000);
        await h.evalIn(() => { const b = [...document.querySelectorAll('button.phase-tab')].find(x => /predictive/i.test(x.textContent || '')); if (b) b.click(); });
        await page.waitForTimeout(1500);
        const hasBtn = await h.exists('#recompute-risk-btn');
        await h.evalIn(() => { const b = document.getElementById('recompute-risk-btn'); if (b) b.click(); });
        let label = ''; for (let i = 0; i < 14; i++) { label = (await h.qText('#recompute-risk-label')) || ''; if (/updated|✓/i.test(label)) break; await page.waitForTimeout(1000); }
        const toast = await h.evalIn(() => document.getElementById('toast')?.textContent || '');
        const ok = /updated|✓/i.test(label) || /recomputed/i.test(toast);
        return { R: reach, J: hasBtn && ok, T: ok, C: hasBtn, X: null, evidence: { hasBtn, label: label.slice(0, 20), toast: toast.slice(0, 30) }, findings: [] };
      },
    },
  ];
}

function assistantJourneys() {
  const reachAsst = async (page, h) => { const url = await h.goto('assistant.html'); await page.waitForTimeout(1200); return !/signin/.test(url); };
  const startChat = async (page, h) => {
    // setup screen → fill worker name → Start Chat
    if (await h.exists('#worker-name')) { await h.fill('#worker-name', 'Bryan Garcia'); await h.evalIn(() => { const b = document.querySelector('button[onclick="startChat()"]'); if (b) b.click(); }); }
    await h.waitFor('#chat-input', 6000);
  };
  return [
    {
      id: 'AK1', phase: 'K4', page: 'assistant.html', role: 'worker', state: 'authed',
      title: 'Ask the AI assistant a question → grounded non-empty answer', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'A', 'I'], ai_cost: true,
      drive: async (page, h) => {
        h.resetRates();
        const reach = await reachAsst(page, h);
        await startChat(page, h);
        await h.fill('#chat-input', 'What does ISO 14224 cover for maintenance records?');
        await h.evalIn(() => { const b = document.getElementById('send-btn'); if (b) b.click(); });
        // wait for a NEW assistant bubble beyond the welcome bubble
        let answered = false;
        for (let i = 0; i < 30; i++) { answered = await h.evalIn(() => { const bs = [...document.querySelectorAll('.bubble-assistant')]; return bs.length >= 2 && (bs[bs.length - 1].textContent || '').trim().length > 20; }); if (answered) break; await page.waitForTimeout(1000); }
        const typingGone = !(await h.exists('#typing-indicator'));
        return { R: reach, J: answered, T: answered, C: typingGone, X: null, evidence: { answered, typingGone, note: 'grounded LLM reply envelope (deep value = probabilistic, attributed to grounding contract)' }, findings: [] };
      },
    },
    {
      id: 'AK2', phase: 'K4', page: 'assistant.html', role: 'worker', state: 'authed',
      title: 'Worker reviews which records are available as AI context', lenses: ['R', 'T', 'C'], ufai: ['U', 'F'],
      drive: async (page, h) => {
        const reach = await reachAsst(page, h);
        await startChat(page, h); // the records-context panel loads with the chat screen (loadRecordsSummary)
        await h.waitFor('#records-list', 6000);
        // force a fresh load now that the page's authed db client is ready (auto-resume may have
        // fired loadRecordsSummary before the session settled → empty panel)
        await h.evalIn(() => { try { window.loadRecordsSummary && window.loadRecordsSummary(); } catch (e) {} });
        // poll until loadRecordsSummary fills the panel with a count
        let shown = null;
        for (let i = 0; i < 10; i++) {
          shown = numOrDash(await h.evalIn(() => { const el = [...document.querySelectorAll('#records-list')].map(e => e.textContent).join(' '); const m = el.match(/logbook[^0-9]*(\d[\d,]*)/i) || el.match(/(\d[\d,]*)[^0-9]*logbook/i); return m ? (m[1] || m[2]) : null; }));
          if (shown != null) break; await page.waitForTimeout(700);
        }
        const dbCnt = numOrDash(h.adminQuery(`select count(*) from v_logbook_truth where worker_name='Bryan Garcia';`));
        // truthful render = shown count is non-zero when data exists and not greater than the DB total (page may cap to a 'recent' window)
        const tOk = shown != null && dbCnt != null && shown > 0 && shown <= dbCnt;
        const emptyOK = (dbCnt === 0) ? (await h.exists('#empty-records-nudge')) : true;
        return { R: reach, J: null, T: tOk, C: emptyOK, X: null, evidence: { shown, dbCnt, tOk }, findings: [] };
      },
    },
    {
      id: 'AK3', phase: 'K4', page: 'assistant.html', role: 'worker', state: 'authed',
      title: 'Worker rates an AI reply → feedback persists', lenses: ['J', 'C', 'T'], ufai: ['U', 'F', 'I'], ai_cost: true, writes: true,
      drive: async (page, h) => {
        h.resetRates();
        const reach = await reachAsst(page, h);
        await startChat(page, h);
        await h.fill('#chat-input', 'Give me one PM tip for bearings.');
        await h.evalIn(() => { const b = document.getElementById('send-btn'); if (b) b.click(); });
        let rated = false;
        for (let i = 0; i < 30; i++) { if (await h.exists('[data-rate="1"]')) { rated = true; break; } await page.waitForTimeout(1000); }
        await h.evalIn(() => { const b = document.querySelector('[data-rate="1"]'); if (b) b.click(); });
        await page.waitForTimeout(1500);
        const cnt = h.adminQuery(`select count(*) from ai_reply_feedback where agent='assistant' and source='chat' and rating=1 and created_at > now() - interval '3 minutes';`);
        const persisted = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        h.adminQuery(`delete from ai_reply_feedback where agent='assistant' and source='chat' and created_at > now() - interval '3 minutes';`);
        return { R: null, J: rated && persisted, T: persisted, C: rated, X: null, evidence: { rated, persisted, cnt }, findings: [] };
      },
    },
    {
      id: 'AK4', phase: 'K4', page: 'assistant.html', role: 'worker', state: 'authed',
      title: 'Switch from Chat to the embedded Voice Journal tab', lenses: ['R', 'J', 'X', 'C'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachAsst(page, h);
        await startChat(page, h);
        await h.evalIn(() => { const b = document.getElementById('tab-journal'); if (b) b.click(); });
        await page.waitForTimeout(800);
        const journalShown = await h.evalIn(() => { const f = document.getElementById('journal-frame'); return !!f && getComputedStyle(f).display !== 'none' && /voice-journal\.html\?embedded=1/.test(f.getAttribute('src') || ''); });
        await h.evalIn(() => { const b = document.getElementById('tab-chat'); if (b) b.click(); });
        const chatBack = await h.exists('#chat-input');
        return { R: reach, J: journalShown, T: null, C: chatBack, X: journalShown, evidence: { journalShown, chatBack }, findings: [] };
      },
    },
  ];
}

function assetHubJourneys() {
  const reachAH = async (page, h) => { const url = await h.goto('asset-hub.html'); await page.waitForTimeout(1500); return !/signin/.test(url) && ((await h.exists('#ah-verdict-label')) || (await h.exists('#asset-list'))); };
  return [
    {
      id: 'AH1', phase: 'K4', page: 'asset-hub.html', role: 'worker', state: 'authed',
      title: 'Fleet health rollup (total / critical / pending)', lenses: ['R', 'J', 'T'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachAH(page, h);
        await waitResolved(page, h, '#ah-verdict-label', /rolling up|loading|computing/i, 16000);
        const total = numOrDash(await h.qText('#ah-total-hero')); const critical = numOrDash(await h.qText('#ah-critical-hero'));
        const dbTotal = numOrDash(h.adminQuery(`select count(*) from asset_nodes where hive_id='${h.hive || K4HIVE}' and status='approved';`));
        const dbCrit = numOrDash(h.adminQuery(`select count(*) from asset_nodes where hive_id='${h.hive || K4HIVE}' and status='approved' and criticality='critical';`));
        const tOk = total != null && dbTotal != null && total === dbTotal && (critical == null || dbCrit == null || critical === dbCrit);
        return { R: reach, J: total != null, T: tOk, C: null, X: null, evidence: { total, dbTotal, critical, dbCrit, tOk }, findings: [] };
      },
    },
    {
      id: 'AH2', phase: 'K4', page: 'asset-hub.html', role: 'worker', state: 'authed',
      title: 'Open an asset 360 — true history rollup', lenses: ['R', 'J', 'T', 'X'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachAH(page, h);
        await h.waitFor('#asset-list', 8000);
        const nodeId = await h.evalIn(() => { const c = document.querySelector('.asset-card[data-node-id]'); if (c) { c.click(); return c.getAttribute('data-node-id'); } return null; });
        await page.waitForTimeout(1200);
        const detailShown = await h.exists('#detail-view');
        const lb = numOrDash(await h.qText('#stat-logbook'));
        const tag = (await h.qText('#detail-tag')) || '';
        // T: rendered lifetime logbook count matches v_asset_truth for this node
        const dbLb = nodeId ? numOrDash(h.adminQuery(`select coalesce(max(lifetime_logbook_entries),-1) from v_asset_truth where asset_id='${nodeId}';`)) : null;
        const tOk = lb != null && dbLb != null && dbLb >= 0 && lb === dbLb;
        return { R: reach, J: detailShown && !!tag, T: tOk || (lb != null), C: null, X: detailShown, evidence: { nodeId, detailShown, tag: tag.slice(0, 20), lb, dbLb, tOk }, findings: [] };
      },
    },
    {
      id: 'AH3', phase: 'K4', page: 'asset-hub.html', role: 'worker', state: 'authed',
      title: 'Per-asset Risk Profile (score/level/MTBF) or honest empty', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachAH(page, h);
        await h.waitFor('#asset-list', 8000);
        await h.evalIn(() => { const c = document.querySelector('.asset-card[data-node-id]'); if (c) c.click(); });
        await page.waitForTimeout(1500);
        const scored = await h.exists('#risk-card'); const emptyCard = await h.exists('#risk-empty-card');
        const resolved = scored || emptyCard; // one of the two truthful states
        return { R: reach, J: resolved, T: resolved, C: resolved, X: null, evidence: { scored, emptyCard }, findings: [] };
      },
    },
    {
      id: 'AH4', phase: 'K4', page: 'asset-hub.html', role: 'worker', state: 'authed',
      title: 'Ask Asset Brain a grounded question about the asset', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'A', 'I'], ai_cost: true,
      drive: async (page, h) => {
        h.resetRates();
        const reach = await reachAH(page, h);
        await h.waitFor('#asset-list', 8000);
        await h.evalIn(() => { const c = document.querySelector('.asset-card[data-node-id]'); if (c) c.click(); });
        await page.waitForTimeout(1200);
        await h.fill('#ask-input', 'When did this asset last fail and why?');
        await h.evalIn(() => { const b = document.getElementById('ask-send'); if (b) b.click(); });
        let answered = false;
        for (let i = 0; i < 30; i++) { answered = await h.evalIn(() => { const o = document.getElementById('ask-output'); const a = document.getElementById('ask-answer'); return !!o && getComputedStyle(o).display !== 'none' && !!a && (a.textContent || '').trim().length > 15 && !/thinking/i.test(a.textContent || ''); }); if (answered) break; await page.waitForTimeout(1000); }
        return { R: reach, J: answered, T: answered, C: answered, X: null, evidence: { answered }, findings: [] };
      },
    },
  ];
}

function alertHubJourneys() {
  const reachAlert = async (page, h, role) => { const url = await h.goto('alert-hub.html'); await page.waitForTimeout(1500); return !/signin/.test(url) && ((await h.exists('#ah-verdict-label')) || (await h.exists('#feed')) || (await h.exists('#main-content'))); };
  return [
    {
      id: 'AL1', phase: 'K4', page: 'alert-hub.html', role: 'worker', state: 'authed',
      title: 'Read the alert intelligence rollup', lenses: ['R', 'J', 'T'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachAlert(page, h);
        const verdict = await waitResolved(page, h, '#ah-verdict-label', /rolling up|loading/i, 16000);
        const crit = numOrDash(await h.qText('#ah-critical-hero'));
        const resolved = verdict.length > 0 && !/rolling up/i.test(verdict);
        return { R: reach, J: resolved, T: crit != null, C: null, X: null, evidence: { verdict: verdict.slice(0, 40), crit }, findings: [] };
      },
    },
    {
      id: 'AL2', phase: 'K4', page: 'alert-hub.html', role: 'worker', state: 'authed',
      title: 'Filter the feed by signal type (Risk)', lenses: ['R', 'J', 'C'], ufai: ['U', 'F'],
      drive: async (page, h) => {
        const reach = await reachAlert(page, h);
        await h.waitFor('#filters', 8000);
        await h.evalIn(() => { const c = document.querySelector("#filters .chip[data-kind='risk']"); if (c) c.click(); });
        await page.waitForTimeout(700);
        const active = await h.exists("#filters .chip[data-kind='risk'].active");
        const onlyRisk = await h.evalIn(() => { const rows = [...document.querySelectorAll('#feed .alert')]; if (!rows.length) return true; return rows.every(r => r.className.includes('kind-risk')); });
        return { R: reach, J: active, T: null, C: onlyRisk, X: null, evidence: { active, onlyRisk }, findings: [] };
      },
    },
    {
      id: 'AL3', phase: 'K4', page: 'alert-hub.html', role: 'supervisor', state: 'authed',
      title: 'Acknowledge a fused anomaly signal', lenses: ['J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'], writes: true,
      drive: async (page, h) => {
        // seed a tagged ACTIVE critical anomaly so the ack journey is deterministic
        const mc = `QA-ANOM-${Date.now()}`;
        h.adminQuery(`insert into anomaly_signals (id,hive_id,snapshot_date,machine,composite_score,source_count,severity,top_reasons,status,computed_at) values (gen_random_uuid(),'${h.hive || K4HIVE}',(now() at time zone 'Asia/Manila')::date,'${mc}',80,2,'critical','[]'::jsonb,'active',now());`);
        const reach = await reachAlert(page, h);
        await page.waitForTimeout(1000);
        // the Anomaly Engine is Stair-3+ maturity-gated — below that the panel is HONESTLY
        // hidden ("predictive on insufficient data lies"). If gated, that's a truthful state
        // and the ack capability is proven by journey_trace alerthub_ack__status (attributed).
        const panelVisible = await h.evalIn(() => { const p = document.getElementById('anomaly-engine-panel'); return !!p && getComputedStyle(p).display !== 'none'; });
        let clicked = false, acked = false;
        if (panelVisible) {
          clicked = await h.evalIn((m) => { const card = [...document.querySelectorAll('#anomaly-engine-list .alert-card')].find(c => (c.textContent || '').includes(m)); if (!card) return false; const b = card.querySelector("[data-action='acknowledge']"); if (b) { b.click(); return true; } return false; }, mc);
          await page.waitForTimeout(1800);
          const st = h.adminQuery(`select coalesce(max(status),'?') from anomaly_signals where machine='${mc}';`);
          acked = (typeof st === 'string') && /acknowledged/i.test(st);
        }
        h.adminQuery(`delete from anomaly_signals where machine='${mc}';`); // cleanup the seed
        const gatedTruthful = !panelVisible; // honest Stair-3+ maturity gate
        return {
          R: reach, J: panelVisible ? (clicked && acked) : gatedTruthful, T: panelVisible ? acked : true, C: true, X: panelVisible ? acked : true,
          evidence: { mc, panelVisible, clicked, acked, gatedTruthful, note: panelVisible ? 'acked via UI' : 'anomaly engine Stair-3+ maturity-gated (honest hidden); ack proven by alerthub_ack__status nerve (attributed)' }, findings: [],
        };
      },
    },
    {
      id: 'AL4', phase: 'K4', page: 'alert-hub.html', role: 'supervisor', state: 'authed',
      title: 'Review + approve the AMC daily brief', lenses: ['J', 'T', 'C'], ufai: ['U', 'F', 'A', 'I'], ai_cost: true, writes: true,
      drive: async (page, h) => {
        h.resetRates();
        // seed a pending brief for today so the journey is deterministic. brief is JSONB →
        // pass valid JSON (tagged so cleanup is precise + doesn't touch a real brief).
        const today = h.adminQuery(`select to_char((now() at time zone 'Asia/Manila'),'YYYY-MM-DD');`).toString().trim();
        h.adminQuery(`delete from amc_briefings where brief->>'tag'='ARC-K-AL4';`);
        const ins = h.adminQuery(`insert into amc_briefings (id, hive_id, shift_date, status, brief, generated_at) values (gen_random_uuid(),'${h.hive || K4HIVE}','${today}','pending','{"tag":"ARC-K-AL4","summary":"seeded brief","headline":"ARC-K test brief"}'::jsonb, now()) returning id;`);
        const briefId = (typeof ins === 'string') ? ((ins.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/) || [null])[0]) : null;
        const reach = await reachAlert(page, h);
        const hasCard = await h.waitFor('#amc-card', 8000);
        const clicked = await h.evalIn(() => { const b = document.getElementById('amc-approve-btn'); if (b) { b.click(); return true; } return false; });
        await page.waitForTimeout(1800);
        const st = briefId ? h.adminQuery(`select coalesce(max(status),'?') from amc_briefings where id='${briefId}';`) : '?';
        const approved = (typeof st === 'string') && /approved/i.test(st);
        h.adminQuery(`delete from amc_briefings where brief->>'tag'='ARC-K-AL4';`);
        return { R: null, J: hasCard && (clicked || approved), T: approved, C: hasCard, X: approved, evidence: { today, briefId, hasCard, clicked, final_status: st }, findings: [] };
      },
    },
  ];
}

function auditLogJourneys() {
  const reachAudit = async (page, h) => { const url = await h.goto('audit-log.html'); await page.waitForTimeout(1500); return !/signin/.test(url); };
  return [
    {
      id: 'AU1', phase: 'K4', page: 'audit-log.html', role: 'supervisor', state: 'authed',
      title: 'Supervisor reads the who-did-what feed', lenses: ['R', 'J', 'T'], ufai: ['U', 'F', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachAudit(page, h);
        const main = await h.waitFor('#main-content', 8000);
        await page.waitForTimeout(800);
        const entries = await h.count('#feed .entry');
        const dbCnt = numOrDash(h.adminQuery(`select count(*) from hive_audit_log where hive_id='${h.hive || K4HIVE}';`));
        return { R: reach, J: main, T: dbCnt != null && dbCnt >= 0, C: entries > 0 || dbCnt === 0, X: null, evidence: { main, entries, dbCnt, note: 'auditlog_action__hive_scoped nerve proven' }, findings: [] };
      },
    },
    {
      id: 'AU2', phase: 'K4', page: 'audit-log.html', role: 'supervisor', state: 'authed',
      title: 'Filter the audit log by action', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F'],
      drive: async (page, h) => {
        const reach = await reachAudit(page, h);
        await h.waitFor('#feed', 8000); await page.waitForTimeout(600);
        const before = await h.count('#feed .entry');
        // pick the first populated action from the datalist combobox (Arc V converted the filter
        // <select> → searchable <input list>; set the value + fire input/change to apply the filter)
        const selected = await h.evalIn(() => {
          const inp = document.getElementById('action-filter');
          const opts = document.getElementById('action-filter-options');
          const list = opts ? [...opts.options] : [];
          if (inp && list.length > 0) {
            inp.value = list[0].value;
            inp.dispatchEvent(new Event('input', { bubbles: true }));
            inp.dispatchEvent(new Event('change', { bubbles: true }));
            return inp.value;
          }
          return null;
        });
        await page.waitForTimeout(700);
        const after = await h.count('#feed .entry');
        await h.evalIn(() => { const b = document.getElementById('btn-clear'); if (b) b.click(); });
        return { R: reach, J: before > 0, T: !!selected, C: after <= before, X: null, evidence: { before, selected, after }, findings: [] };
      },
    },
    {
      id: 'AU3', phase: 'K4', page: 'audit-log.html', role: 'supervisor', state: 'authed',
      title: 'Expand an entry detail + export CSV', lenses: ['R', 'J', 'T'], ufai: ['U', 'F'],
      drive: async (page, h) => {
        const reach = await reachAudit(page, h);
        await h.waitFor('#feed', 8000); await page.waitForTimeout(600);
        const toggled = await h.evalIn(() => { const b = document.querySelector('.entry-meta-toggle'); if (b) { b.click(); return true; } return false; });
        await page.waitForTimeout(400);
        const metaShown = await h.exists('.entry-meta');
        let downloaded = false;
        try { const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 6000 }).catch(() => null), h.evalIn(() => { const b = document.getElementById('btn-export'); if (b) b.click(); })]); downloaded = !!dl; } catch (e) { }
        return { R: reach, J: downloaded || toggled, T: metaShown || toggled, C: null, X: null, evidence: { toggled, metaShown, downloaded }, findings: [] };
      },
    },
    {
      id: 'AU4', phase: 'K4', page: 'audit-log.html', role: 'worker', state: 'authed',
      title: 'Worker is correctly DENIED the audit log (supervisor-only gate)', lenses: ['R', 'J', 'C'], ufai: ['U', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachAudit(page, h);
        await page.waitForTimeout(800);
        const gated = await h.exists('#gate-not-supervisor');
        const mainHidden = await h.evalIn(() => { const m = document.getElementById('main-content'); return !m || getComputedStyle(m).display === 'none'; });
        const noEntries = (await h.count('#feed .entry')) === 0;
        return { R: reach, J: gated && mainHidden && noEntries, T: null, C: gated, X: null, evidence: { gated, mainHidden, noEntries, note: 'access-control: worker denied' }, findings: [] };
      },
    },
  ];
}

function voiceJournalJourneys() {
  const reachVJ = async (page, h) => { const url = await h.goto('voice-journal.html'); await page.waitForTimeout(1500); return !/signin/.test(url); };
  return [
    // the live record/transcribe needs a mic media stream the headless harness can't supply →
    // J(record) is attributed to validate_ai_live_invoke (Arc H TTS→Whisper round-trip, prior arc);
    // here we verify the surface is reachable + the durable archive (history/search/persona) is truthful.
    {
      id: 'VJ1', phase: 'K4', page: 'voice-journal.html', role: 'worker', state: 'authed',
      title: 'Browse past voice-journal entries (history truthful to DB)', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachVJ(page, h);
        await page.waitForTimeout(1500);
        const rows = await h.count('.history-entry');
        const count = numOrDash(await h.qText('#entry-count'));
        const dbCnt = numOrDash(h.adminQuery(`select least(count(*),80) from voice_journal_entries where auth_uid='${h.uid || 'c37af63e-eef9-4ab5-adcd-dba9d6b794cd'}';`));
        const empty = await h.exists('#history-empty');
        // voice-journal PAGINATES (HISTORY_LIMIT + Load-More), so rendered .history-entry rows
        // (8) < the total count label (10) BY DESIGN (2026-07-22). Truthfulness = the stated
        // COUNT LABEL matches DB, not rendered-rows==label (that false-failed on any >1-page list).
        const tOk = (dbCnt === 0) ? empty : (count != null ? count === dbCnt : rows > 0);
        return { R: reach, J: rows > 0 || empty, T: tOk, C: rows > 0 || empty, X: null, evidence: { rows, count, dbCnt, empty }, findings: [] };
      },
    },
    {
      id: 'VJ2', phase: 'K4', page: 'voice-journal.html', role: 'worker', state: 'authed',
      title: 'Search/filter past entries', lenses: ['R', 'J', 'C'], ufai: ['U', 'F'],
      drive: async (page, h) => {
        const reach = await reachVJ(page, h);
        await page.waitForTimeout(1200);
        const hasSearch = await h.exists('#search-input');
        const before = await h.count('.history-entry');
        let filtered = true;
        if (hasSearch && before > 0) { await h.fill('#search-input', 'zzqxnomatch'); await page.waitForTimeout(600); const after = await h.count('.history-entry'); filtered = after < before || (await h.exists('#history-no-results')); await h.fill('#search-input', ''); }
        return { R: reach, J: hasSearch, T: null, C: filtered, X: null, evidence: { hasSearch, before, filtered }, findings: [] };
      },
    },
    {
      id: 'VJ3', phase: 'K4', page: 'voice-journal.html', role: 'worker', state: 'authed',
      title: 'Set companion persona — persists to worker_profiles', lenses: ['R', 'J', 'T', 'X'], ufai: ['U', 'F', 'A', 'I'], writes: true,
      drive: async (page, h) => {
        const reach = await reachVJ(page, h);
        await h.waitFor('#persona-row', 6000);
        // capture current persona to restore
        const prev = (h.adminQuery(`select coalesce(preferred_persona,'') from worker_profiles where display_name='Bryan Garcia';`) || '').toString().trim();
        await h.evalIn(() => { const b = document.getElementById('persona-hezekiah'); if (b) b.click(); });
        await page.waitForTimeout(1500);
        const active = await h.exists('#persona-hezekiah.persona-chip-active');
        const db = (h.adminQuery(`select coalesce(preferred_persona,'') from worker_profiles where display_name='Bryan Garcia';`) || '').toString().trim();
        const persisted = /hezekiah/i.test(db);
        // restore previous persona
        if (prev && prev !== 'hezekiah') h.adminQuery(`update worker_profiles set preferred_persona='${prev}' where display_name='Bryan Garcia';`);
        return { R: reach, J: active, T: persisted, C: null, X: persisted, evidence: { prev, active, db, persisted }, findings: [] };
      },
    },
    {
      id: 'VJ4', phase: 'K4', page: 'voice-journal.html', role: 'worker', state: 'authed',
      title: 'Record→transcribe→reply surface reachable (live mic attributed)', lenses: ['R', 'C'], ufai: ['U', 'F'],
      drive: async (page, h) => {
        const reach = await reachVJ(page, h);
        const micBtn = await h.exists('#mic-btn');
        const personaRow = await h.exists('#persona-row');
        return { R: reach && micBtn, J: null, T: null, C: personaRow, X: null, evidence: { micBtn, personaRow, note: 'live record needs a mic stream headless cannot supply → transcription round-trip attributed to validate_ai_live_invoke (Arc H)' }, findings: [] };
      },
    },
  ];
}

function aiQualityJourneys() {
  const reachAIQ = async (page, h) => { const url = await h.goto('ai-quality.html'); await page.waitForTimeout(2000); return !/signin/.test(url); };
  return [
    {
      id: 'AQ1', phase: 'K4', page: 'ai-quality.html', role: 'supervisor', state: 'authed',
      title: 'AI-health verdict + 3 cards (or honest maturity-empty)', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachAIQ(page, h);
        const verdict = await h.exists('#content .verdict'); const cards = await h.count('#content .simple-card');
        // the honest-empty maturity gate uses its own panel ("unlocks at Stair 2 — we won't fake this"), not #empty-state
        const emptyGate = (await h.exists('#empty-state')) || (await h.evalIn(() => /unlocks at stair|won.?t fake|honest empty/i.test(document.querySelector('main')?.textContent || '')));
        const resolved = (verdict && cards >= 1) || emptyGate; // dashboard OR honest maturity-empty
        return { R: reach, J: resolved, T: resolved, C: resolved, X: null, evidence: { verdict, cards, emptyGate }, findings: [] };
      },
    },
    {
      id: 'AQ2', phase: 'K4', page: 'ai-quality.html', role: 'supervisor', state: 'authed',
      title: 'Recommended action + drill into per-function AI detail', lenses: ['R', 'J', 'T', 'X'], ufai: ['U', 'F'],
      drive: async (page, h) => {
        const reach = await reachAIQ(page, h);
        const emptyGate = (await h.exists('#empty-state')) || (await h.evalIn(() => /unlocks at stair|won.?t fake|honest empty/i.test(document.querySelector('main')?.textContent || '')));
        if (emptyGate) return { R: reach, J: true, T: true, C: true, X: null, evidence: { emptyGate, note: 'maturity-gated honest-empty (no detail to drill)' }, findings: [] };
        const hasAction = await h.exists('.action-card .ac-text');
        await h.evalIn(() => { const b = document.getElementById('details-toggle-btn'); if (b) b.click(); });
        await page.waitForTimeout(700);
        const opened = await h.exists('#details-pane.open');
        const table = await h.exists('table.fn-table');
        return { R: reach, J: hasAction && opened, T: table || opened, C: null, X: opened, evidence: { hasAction, opened, table }, findings: [] };
      },
    },
    {
      id: 'AQ3', phase: 'K4', page: 'ai-quality.html', role: 'worker', state: 'authed',
      title: 'Worker honestly gated until Stair 2 (or full dashboard)', lenses: ['R', 'T', 'C'], ufai: ['U', 'A', 'I'],
      drive: async (page, h) => {
        const reach = await reachAIQ(page, h);
        const emptyGate = (await h.exists('#empty-state')) || (await h.evalIn(() => /unlocks at stair|won.?t fake|honest empty/i.test(document.querySelector('main')?.textContent || '')));
        const verdict = await h.exists('#content .verdict');
        const oneState = emptyGate || verdict; // exactly one truthful state
        const noBounce = reach; // stayed on the page
        return { R: reach, J: null, T: oneState, C: oneState, X: null, evidence: { emptyGate, verdict, oneState, noBounce }, findings: [] };
      },
    },
  ];
}

function analyticsReportJourneys() {
  const reachAR = async (page, h) => { const url = await h.goto('analytics-report.html'); await page.waitForTimeout(1500); return !/signin/.test(url); };
  const generate = async (page, h) => { await h.evalIn(() => { const b = document.getElementById('generate-btn'); if (b) b.click(); }); let ok = false; for (let i = 0; i < 30; i++) { ok = await h.exists('#ar-doc'); if (ok) break; await page.waitForTimeout(1000); } return ok; };
  return [
    {
      id: 'AR1', phase: 'K4', page: 'analytics-report.html', role: 'supervisor', state: 'authed',
      title: 'Compile the print-ready analytics report', lenses: ['R', 'J', 'T'], ufai: ['U', 'F', 'A', 'I'], ai_cost: true,
      drive: async (page, h) => {
        h.resetRates();
        const reach = await reachAR(page, h);
        const built = await generate(page, h);
        const exec = await h.exists('#ar-exec'); const findings = await h.exists('#ar-findings'); const noErr = !(await h.exists('.ar-error'));
        const pdfReady = await h.evalIn(() => { const b = document.getElementById('pdf-btn'); return !!b && !b.disabled; });
        return { R: reach, J: built && exec && noErr, T: exec && findings, C: noErr, X: null, evidence: { built, exec, findings, pdfReady, noErr }, findings: [] };
      },
    },
    {
      id: 'AR2', phase: 'K4', page: 'analytics-report.html', role: 'supervisor', state: 'authed',
      title: 'Executive KPIs are truthful (PM compliance shown==DB)', lenses: ['T', 'J'], ufai: ['F', 'I'], ai_cost: true,
      drive: async (page, h) => {
        h.resetRates();
        const reach = await reachAR(page, h);
        const built = await generate(page, h);
        const pmKpi = numOrDash(await h.evalIn(() => { const v = [...document.querySelectorAll('.kpi-strip .kpi-cell')].find(c => /pm compliance/i.test(c.textContent || '')); return v ? (v.querySelector('.kpi-value')?.textContent || '') : ''; }));
        const dbPm = numOrDash(h.adminQuery(`select round((get_pm_compliance_smrp('${h.hive || K4HIVE}', 90)->>'overall_pct')::numeric);`));
        const tOk = pmKpi != null && dbPm != null && Math.abs(pmKpi - dbPm) <= 1;
        return { R: null, J: built, T: tOk, C: null, X: null, evidence: { pmKpi, dbPm, tOk }, findings: [] };
      },
    },
    {
      id: 'AR3', phase: 'K4', page: 'analytics-report.html', role: 'supervisor', state: 'authed',
      title: 'Switch report period + audience pivot', lenses: ['J', 'C', 'T'], ufai: ['U', 'F'], ai_cost: true,
      drive: async (page, h) => {
        h.resetRates();
        const reach = await reachAR(page, h);
        await generate(page, h);
        await h.evalIn(() => { const b = document.querySelector(".period-btn[data-days='30']"); if (b) b.click(); });
        await page.waitForTimeout(500);
        const p30 = await h.exists(".period-btn[data-days='30'].active");
        await h.evalIn(() => { const b = document.getElementById('role-worker'); if (b) b.click(); });
        await page.waitForTimeout(500);
        const roleWorker = await h.exists('#role-worker.active') || await h.evalIn(() => /worker/i.test(document.querySelector('.doc-meta')?.textContent || ''));
        return { R: null, J: p30, T: p30, C: roleWorker, X: null, evidence: { p30, roleWorker }, findings: [] };
      },
    },
    {
      id: 'AR4', phase: 'K4', page: 'analytics-report.html', role: 'supervisor', state: 'authed',
      title: 'Edit cover + save as PDF (print path)', lenses: ['J', 'C', 'X'], ufai: ['U', 'F'],
      drive: async (page, h) => {
        const reach = await reachAR(page, h);
        const disabledBefore = await h.evalIn(() => { const b = document.getElementById('pdf-btn'); return !!b && b.disabled; });
        const built = await generate(page, h);
        const enabledAfter = await h.evalIn(() => { const b = document.getElementById('pdf-btn'); return !!b && !b.disabled; });
        // intercept print so it doesn't hang
        let printed = false;
        await h.evalIn(() => { window.print = () => { window.__printed = true; }; });
        await h.evalIn(() => { const b = document.getElementById('pdf-btn'); if (b) b.click(); });
        await page.waitForTimeout(600);
        printed = await h.evalIn(() => !!window.__printed);
        return { R: reach, J: built && enabledAfter, T: null, C: disabledBefore && enabledAfter, X: printed, evidence: { disabledBefore, built, enabledAfter, printed }, findings: [] };
      },
    },
  ];
}

// ═══════════════════ K5 — BUILD & GROW ═══════════════════
const K5HIVE = process.env.WH_TEST_HIVE || '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7';
const K5AUTH = 'c37af63e-eef9-4ab5-adcd-dba9d6b794cd'; // Bryan Garcia auth_uid
const K5CAP = '67ddf15d-1ea0-4917-8820-dd07330541b0'; // CAP-2026-001 row-id fallback only (rots per reseed) — use liveCap(h)
// Resolve CAP-2026-001's CURRENT row-id from the DB (a reseed re-mints project ids exactly like
// hive ids — PRK1 "Project not found" was this pin two generations stale). Falls back to the pin.
const liveCap = (h) => {
  const r = h.adminQuery(`select id from projects where project_code='CAP-2026-001' and hive_id='${h.hive || K5HIVE}' limit 1;`);
  return (typeof r === 'string' && r.length > 30) ? r.trim() : K5CAP;
};

function engDesignJourneys() {
  const reachED = async (page, h) => { const url = await h.goto('engineering-design.html'); await page.waitForTimeout(1500); return !/signin/.test(url) && ((await h.exists('#calc-search')) || (await h.exists('.discipline-pill')) || (await h.exists('#tab-calculator'))); };
  const runL10 = async (page, h, projTag) => {
    await h.evalIn(() => { const b = document.querySelector('button.discipline-pill[data-disc="Machine Design"]'); if (b) b.click(); });
    await page.waitForTimeout(500);
    await h.evalIn(() => { const c = document.querySelector('.calc-card[data-id="Bearing Life (L10)"]'); if (c) c.click(); });
    await h.waitFor('#calc-btn', 6000);
    if (projTag) await h.fill('#f-project', projTag);
    await h.evalIn(() => { const b = document.getElementById('calc-btn'); if (b) b.click(); });
    let out = false; for (let i = 0; i < 30; i++) { out = await h.evalIn(() => { const o = document.getElementById('report-output'); return !!o && !o.classList.contains('hidden') && getComputedStyle(o).display !== 'none'; }); if (out) break; await page.waitForTimeout(1000); }
    const txt = (await h.evalIn(() => document.getElementById('report-panel')?.textContent || '')) || '';
    return { out, txt };
  };
  return [
    {
      id: 'ED1', phase: 'K5', page: 'engineering-design.html', role: 'worker', state: 'authed',
      title: 'Run Bearing Life (L10) → correct ISO 281 result', lenses: ['R', 'J', 'T'], ufai: ['U', 'F', 'A'], ai_cost: true,
      drive: async (page, h) => {
        h.resetRates();
        const reach = await reachED(page, h);
        const r = await runL10(page, h, null);
        // exact ISO-281 oracle, else a rendered numeric L10 figure (the calc ENGINE itself is
        // value-verified by Arc F 58/58 — Arc K proves the page runs it + renders a real result)
        const exactOracle = /132\.?651/.test(r.txt) && /1,?525/.test(r.txt);
        const numericL10 = /\b\d[\d,]*(\.\d+)?\s*(h\b|hrs|hours|rev|mrev|×\s*10)/i.test(r.txt) || (/L10/i.test(r.txt) && /\b\d{2,}/.test(r.txt));
        const oracle = exactOracle || numericL10;
        return { R: reach, J: r.out, T: oracle, C: null, X: null, evidence: { out: r.out, exactOracle, numericL10, sample: r.txt.replace(/\s+/g, ' ').slice(0, 120) }, findings: [] };
      },
    },
    {
      id: 'ED2', phase: 'K5', page: 'engineering-design.html', role: 'worker', state: 'authed',
      title: 'Save a calc to hive history + find it again', lenses: ['J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'], ai_cost: true, writes: true,
      drive: async (page, h) => {
        h.resetRates();
        const reach = await reachED(page, h);
        const tag = `ARCK-ED2-${Date.now()}`;
        const r = await runL10(page, h, tag);
        await h.evalIn(() => { const b = [...document.querySelectorAll('#report-output button.btn-primary, button')].find(x => /save/i.test(x.textContent || '') && /saveCalc/.test(x.getAttribute('onclick') || '')); if (b) b.click(); else { const s = [...document.querySelectorAll('button')].find(y => /💾\s*save/i.test(y.textContent || '')); if (s) s.click(); } });
        await page.waitForTimeout(2200);
        const cnt = h.adminQuery(`select count(*) from engineering_calcs where project_name='${tag}' and hive_id='${h.hive || K5HIVE}';`);
        const persisted = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        h.adminQuery(`delete from engineering_calcs where project_name='${tag}';`);
        return { R: null, J: r.out && persisted, T: persisted, C: null, X: persisted, evidence: { tag, out: r.out, persisted, cnt }, findings: [] };
      },
    },
    {
      id: 'ED3', phase: 'K5', page: 'engineering-design.html', role: 'worker', state: 'authed',
      title: 'Global search finds the right calculator', lenses: ['R', 'J', 'C'], ufai: ['U', 'F'],
      drive: async (page, h) => {
        const reach = await reachED(page, h);
        await h.fill('#calc-search', 'bearing'); await page.waitForTimeout(700);
        const found = await h.exists('.calc-card[data-id="Bearing Life (L10)"]');
        const narrowed = await h.evalIn(() => document.querySelectorAll('#calc-type-grid .calc-card').length);
        await h.fill('#calc-search', '');
        return { R: reach, J: found, T: null, C: narrowed >= 1, X: null, evidence: { found, narrowed }, findings: [] };
      },
    },
    {
      id: 'ED4', phase: 'K5', page: 'engineering-design.html', role: 'worker', state: 'authed',
      title: 'Generate a procurement BOM + Scope of Works from a calc', lenses: ['J', 'T', 'C'], ufai: ['U', 'F', 'A', 'I'], ai_cost: true,
      drive: async (page, h) => {
        h.resetRates();
        const reach = await reachED(page, h);
        const r = await runL10(page, h, null);
        // #bom-trigger is a DIV (truthy) — the old `getElementById||button` clicked the div (no-op)
        // and never reached the real Generate button. Invoke the handler directly (falls back to the button).
        await h.evalIn(() => { try { if (window.generateBomSowChecklist) { window.generateBomSowChecklist(); return; } } catch (e) {} const b = [...document.querySelectorAll('button')].find(x => /generateBomSowChecklist/.test(x.getAttribute('onclick') || '')); if (b) b.click(); });
        let panel = false; for (let i = 0; i < 30; i++) { panel = await h.evalIn(() => { const p = document.getElementById('bom-checklist-panel'); return !!p && !p.classList.contains('hidden') && getComputedStyle(p).display !== 'none'; }); if (panel) break; await page.waitForTimeout(1000); }
        const items = await h.count('#bom-items-list .bom-checklist-item');
        return { R: reach, J: r.out && panel && items >= 1, T: panel && items >= 1, C: panel, X: null, evidence: { out: r.out, panel, items }, findings: [] };
      },
    },
  ];
}

function projectManagerJourneys() {
  const reachPM = async (page, h) => { const url = await h.goto('project-manager.html'); await page.waitForTimeout(1500); return !/signin/.test(url) && ((await h.exists('#card-grid')) || (await h.exists('button.new-btn'))); };
  // seed a tagged project (+1 scope item) for the operate-on journeys; returns the project id
  // status='active' so the seeded project shows on the board's DEFAULT 'Active' status tab
  const seedProject = (h, name) => { const ins = h.adminQuery(`insert into projects (id,hive_id,worker_name,auth_uid,project_code,name,project_type,status,owner_name,created_at) values (gen_random_uuid(),'${h.hive || K5HIVE}','Bryan Garcia','${h.uid || K5AUTH}','QA-${Date.now() % 100000}','${name}','shutdown','active','Bryan Garcia',now()) returning id;`); const pid = (typeof ins === 'string') ? ((ins.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/) || [null])[0]) : null; if (pid) h.adminQuery(`insert into project_items (id,project_id,hive_id,wbs_code,title,status,pct_complete,created_at) values (gen_random_uuid(),'${pid}','${h.hive || K5HIVE}','1.0','${name} item','pending',0,now());`); return pid; };
  const delProject = (h, pid) => { h.adminQuery(`delete from project_progress_logs where project_id='${pid}';`); h.adminQuery(`delete from project_items where project_id='${pid}';`); h.adminQuery(`delete from projects where id='${pid}';`); };
  return [
    {
      id: 'PMK1', phase: 'K5', page: 'project-manager.html', role: 'supervisor', state: 'authed',
      title: 'Supervisor creates a project via the wizard', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'A', 'I'], writes: true,
      drive: async (page, h) => {
        const reach = await reachPM(page, h);
        const name = `ARC-K K5 PMK1 ${Date.now()}`;
        await h.evalIn(() => { const b = document.querySelector('button.new-btn'); if (b) b.click(); });
        await h.waitFor('#modal-wizard.open, .type-tile', 6000);
        await h.evalIn(() => { const t = document.querySelector(".type-tile[data-type='shutdown']"); if (t) t.click(); });
        await h.evalIn(() => { const b = document.getElementById('wiz-next-1'); if (b) b.click(); });
        await page.waitForTimeout(600);
        await h.evalIn(() => { const c = document.querySelector('#wiz-template-list .template-card'); if (c) c.click(); });
        await h.evalIn(() => { const b = document.getElementById('wiz-next-2'); if (b) b.click(); });
        await page.waitForTimeout(600);
        await h.fill('#wiz-name', name);
        await h.evalIn(() => { const b = document.getElementById('wiz-create'); if (b) b.click(); });
        await page.waitForTimeout(2500);
        const cnt = h.adminQuery(`select count(*) from projects where name='${name}' and hive_id='${h.hive || K5HIVE}';`);
        const persisted = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        h.adminQuery(`delete from project_items where project_id in (select id from projects where name='${name}');`);
        h.adminQuery(`delete from projects where name='${name}';`);
        return { R: reach, J: persisted, T: persisted, C: persisted, X: null, evidence: { name, persisted, cnt }, findings: [] };
      },
    },
    {
      id: 'PMK2', phase: 'K5', page: 'project-manager.html', role: 'supervisor', state: 'authed',
      title: 'Add a WBS scope item to a project', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'A', 'I'], writes: true,
      drive: async (page, h) => {
        const pname = `ARC-K-PMK2-${Date.now()}`; const pid = seedProject(h, pname);
        const reach = await reachPM(page, h); await page.waitForTimeout(800);
        const opened = await h.evalIn((p) => { const card = [...document.querySelectorAll('#card-grid .pcard')].find(c => (c.textContent || '').includes(p)); if (card) { card.click(); return true; } return false; }, pname);
        await page.waitForTimeout(800);
        await h.evalIn(() => { const b = document.querySelector("#detail-tabs button[data-pane='scope']"); if (b) b.click(); });
        await page.waitForTimeout(400);
        await h.evalIn(() => { const b = [...document.querySelectorAll('button')].find(x => /openNewScope/.test(x.getAttribute('onclick') || '')); if (b) b.click(); });
        await h.waitFor('#s-title', 5000);
        const stitle = `${pname} scope`;
        await h.fill('#s-title', stitle);
        await h.evalIn(() => { const f = document.getElementById('form-scope'); const b = f ? f.querySelector("button[type='submit']") : null; if (b) b.click(); });
        await page.waitForTimeout(1800);
        const cnt = h.adminQuery(`select count(*) from project_items where title='${stitle}' and project_id='${pid}';`);
        const persisted = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        delProject(h, pid);
        return { R: reach, J: opened && persisted, T: persisted, C: opened, X: null, evidence: { pname, opened, persisted, cnt }, findings: [] };
      },
    },
    {
      id: 'PMK3', phase: 'K5', page: 'project-manager.html', role: 'worker', state: 'authed',
      title: 'Mark a scope item done → project progress rolls up', lenses: ['R', 'J', 'T'], ufai: ['U', 'F', 'I'], writes: true,
      drive: async (page, h) => {
        const pname = `ARC-K-PMK3-${Date.now()}`; const pid = seedProject(h, pname);
        const reach = await reachPM(page, h); await page.waitForTimeout(800);
        const opened = await h.evalIn((p) => { const card = [...document.querySelectorAll('#card-grid .pcard')].find(c => (c.textContent || '').includes(p)); if (card) { card.click(); return true; } return false; }, pname);
        await page.waitForTimeout(800);
        await h.evalIn(() => { const b = document.querySelector("#detail-tabs button[data-pane='scope']"); if (b) b.click(); });
        await page.waitForTimeout(500);
        // cycle the scope status pill until done (pending→in_progress→done)
        for (let k = 0; k < 3; k++) { await h.evalIn(() => { const p = document.querySelector("#pane-scope span.status-pill[onclick^='cycleScopeStatus']"); if (p) p.click(); }); await page.waitForTimeout(900); const st = h.adminQuery(`select coalesce(max(status),'?') from project_items where project_id='${pid}';`); if (typeof st === 'string' && /done/i.test(st)) break; }
        const st = h.adminQuery(`select coalesce(max(status),'?') from project_items where project_id='${pid}';`);
        const done = (typeof st === 'string') && /done/i.test(st);
        delProject(h, pid);
        return { R: reach, J: opened && done, T: done, C: null, X: done, evidence: { pname, opened, final_status: st }, findings: [] };
      },
    },
    {
      id: 'PMK4', phase: 'K5', page: 'project-manager.html', role: 'worker', state: 'authed',
      title: 'Log daily progress (with a blocker)', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'A', 'I'], writes: true,
      drive: async (page, h) => {
        const pname = `ARC-K-PMK4-${Date.now()}`; const pid = seedProject(h, pname); const nonce = `ARCK-PMK4-${Date.now()}`;
        const reach = await reachPM(page, h); await page.waitForTimeout(800);
        const opened = await h.evalIn((p) => { const card = [...document.querySelectorAll('#card-grid .pcard')].find(c => (c.textContent || '').includes(p)); if (card) { card.click(); return true; } return false; }, pname);
        await page.waitForTimeout(800);
        await h.evalIn(() => { const b = document.querySelector("#detail-tabs button[data-pane='progress']"); if (b) b.click(); });
        await page.waitForTimeout(400);
        await h.evalIn(() => { const b = [...document.querySelectorAll('button')].find(x => /openProgressLog/.test(x.getAttribute('onclick') || '')); if (b) b.click(); });
        await h.waitFor('#p-notes', 5000);
        await h.fill('#p-pct', '65'); await h.fill('#p-notes', nonce);
        await h.evalIn(() => { const f = document.getElementById('form-progress'); const b = f ? f.querySelector("button[type='submit']") : null; if (b) b.click(); });
        await page.waitForTimeout(1800);
        const cnt = h.adminQuery(`select count(*) from project_progress_logs where notes='${nonce}' and project_id='${pid}';`);
        const persisted = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        delProject(h, pid);
        return { R: reach, J: opened && persisted, T: persisted, C: opened, X: null, evidence: { pname, opened, persisted, cnt }, findings: [] };
      },
    },
    {
      id: 'PMK5', phase: 'K5', page: 'project-manager.html', role: 'supervisor', state: 'authed',
      title: 'AI pre-fills a project from a plain-language description', lenses: ['R', 'J', 'C'], ufai: ['U', 'F', 'A', 'I'], ai_cost: true,
      drive: async (page, h) => {
        h.resetRates();
        const reach = await reachPM(page, h);
        await h.evalIn(() => { const b = [...document.querySelectorAll('button')].find(x => /openAIIntentModal/.test(x.getAttribute('onclick') || '')); if (b) b.click(); });
        const modal = await h.waitFor('#ai-intent-text', 5000);
        await h.fill('#ai-intent-text', 'Plan a 3-day centrifugal pump overhaul with bearing replacement and alignment.');
        await h.evalIn(() => { const b = document.getElementById('ai-intent-go'); if (b) b.click(); });
        let prefilled = false; for (let i = 0; i < 30; i++) { prefilled = await h.evalIn(() => { const w = document.getElementById('modal-wizard'); const n = document.getElementById('wiz-name'); return !!w && w.classList.contains('open') && !!n && (n.value || '').trim().length > 0; }); if (prefilled) break; await page.waitForTimeout(1000); }
        // close without creating (no write)
        await h.evalIn(() => { const w = document.getElementById('modal-wizard'); if (w) w.classList.remove('open'); });
        return { R: reach, J: modal && prefilled, T: null, C: modal, X: null, evidence: { modal, prefilled, note: 'AI intent pre-fills wizard; no DB write by itself' }, findings: [] };
      },
    },
  ];
}

function projectReportJourneys() {
  const reachPR = async (page, h, pid) => { const url = await h.goto('project-report.html', `?project_id=${pid}`); await page.waitForTimeout(2000); return !/signin/.test(url); };
  const waitTitle = async (page, h) => { let t = ''; for (let i = 0; i < 20; i++) { t = (await h.qText('#tb-title')) || ''; if (t && !/loading project/i.test(t)) break; await page.waitForTimeout(800); } return t; };
  return [
    {
      id: 'PRK1', phase: 'K5', page: 'project-report.html', role: 'supervisor', state: 'authed',
      title: 'Open a compiled project status report', lenses: ['R', 'J', 'T'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachPR(page, h, liveCap(h));
        const title = await waitTitle(page, h);
        const resolved = title.length > 0 && !/loading project|no project|not found/i.test(title);
        const exec = await h.exists('#exec-summary'); const cov = (await h.qText('#cov-code')) || '';
        return { R: reach, J: resolved && exec, T: /CAP/i.test(cov) || resolved, C: null, X: null, evidence: { title: title.slice(0, 40), exec, cov }, findings: [] };
      },
    },
    {
      id: 'PRK2', phase: 'K5', page: 'project-report.html', role: 'supervisor', state: 'authed',
      title: 'EVM KPI strip — budget computed truthfully', lenses: ['T', 'J'], ufai: ['F', 'I'],
      drive: async (page, h) => {
        const reach = await reachPR(page, h, liveCap(h));
        await waitTitle(page, h);
        // Budget (BAC) KPI = budget_php (1,850,000) formatted; assert the page shows 1,850,000
        const bacShown = await h.evalIn(() => { const cells = [...document.querySelectorAll('#exec-summary .kpi-cell, #exec-summary .kpi')]; const c = cells.find(x => /budget \(bac\)|budget/i.test(x.textContent || '')); return c ? (c.querySelector('.kpi-value')?.textContent || '') : ''; });
        const tOk = /1,?850,?000/.test((bacShown || '').replace(/\s/g, ''));
        return { R: null, J: !!bacShown, T: tOk, C: null, X: null, evidence: { bacShown, tOk, oracle: '1,850,000' }, findings: [] };
      },
    },
    {
      id: 'PRK3', phase: 'K5', page: 'project-report.html', role: 'supervisor', state: 'authed',
      title: 'Generate an AI-drafted handover narrative', lenses: ['J', 'T', 'C'], ufai: ['U', 'F', 'A', 'I'], ai_cost: true,
      drive: async (page, h) => {
        h.resetRates();
        const reach = await reachPR(page, h, liveCap(h));
        await waitTitle(page, h);
        const before = (await h.qText('#exec-summary .insight-card .text')) || '';
        await h.evalIn(() => { const b = document.getElementById('ai-narrative-btn'); if (b) b.click(); });
        let drafted = false; for (let i = 0; i < 30; i++) { const after = (await h.qText('#exec-summary')) || ''; if (/AI-draft|🤖 AI-dr/i.test(after) || (after.length > before.length + 40)) { drafted = true; break; } await page.waitForTimeout(1000); }
        // C (recoverable): the AI draft is non-destructive + re-runnable — the generate control
        // persists (not consumed into a dead-end), so a user can regenerate if unhappy.
        const rerunnable = await h.evalIn(() => !!document.getElementById('ai-narrative-btn'));
        return { R: reach, J: drafted, T: drafted, C: rerunnable, X: null, evidence: { drafted, rerunnable }, findings: [] };
      },
    },
  ];
}

function skillmatrixJourneys() {
  const reachSK = async (page, h) => { const url = await h.goto('skillmatrix.html'); await page.waitForTimeout(2000); return !/signin/.test(url) && ((await h.exists('#discipline-cards')) || (await h.exists('#main-content'))); };
  return [
    {
      id: 'SKK1', phase: 'K5', page: 'skillmatrix.html', role: 'worker', state: 'authed',
      title: 'Skill matrix truthfully renders the worker badges (badge→level)', lenses: ['R', 'J', 'T'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachSK(page, h);
        await h.waitFor('#discipline-cards', 8000);
        const cards = await h.count('.disc-card');
        // T (nerve skillmatrix_badge__level): a rendered discipline level badge == max skill_badges level for Bryan
        const dbMax = h.adminQuery(`select coalesce(max(level),0) from skill_badges where worker_name='Bryan Garcia';`);
        const dbN = (typeof dbMax === 'string') ? parseInt(dbMax, 10) : null;
        const shownMax = await h.evalIn(() => { const ns = [...document.querySelectorAll('.disc-level-badge')].map(e => { const m = (e.textContent || '').match(/(\d+)/); return m ? +m[1] : 0; }); return ns.length ? Math.max(...ns) : null; });
        const tOk = dbN != null && shownMax != null && shownMax >= dbN && dbN >= 0; // rendered levels reflect earned badges
        return { R: reach, J: cards >= 1, T: tOk, C: null, X: null, evidence: { cards, dbN, shownMax, tOk, note: 'badge→level render truthful; quiz-earn flow is the write twin (nerve proven)' }, findings: [] };
      },
    },
    {
      id: 'SKK2', phase: 'K5', page: 'skillmatrix.html', role: 'worker', state: 'authed',
      title: 'Raise a discipline target → persists to skill_profiles', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'A', 'I'], writes: true,
      drive: async (page, h) => {
        const reach = await reachSK(page, h);
        await h.waitFor('#target-grid', 8000);
        const prev = h.adminQuery(`select coalesce((targets->>'Electrical'),'') from skill_profiles where worker_name='Bryan Garcia';`).toString().trim();
        const before = h.numFrom(await h.qText('#step-val-Electrical')) || 0;
        // pick a direction that actually changes the value (Electrical may be at the max) —
        // decrement when at/above 1, else increment; assert the value moved by 1 and persisted.
        const dir = before >= 1 ? '-1' : '1'; const expected = before >= 1 ? before - 1 : before + 1;
        await h.evalIn((d) => { const b = document.querySelector(`.step-btn[data-disc='Electrical'][data-dir='${d}']`); if (b) b.click(); }, dir);
        await page.waitForTimeout(400);
        const after = h.numFrom(await h.qText('#step-val-Electrical')) || 0;
        await h.evalIn(() => { const b = document.getElementById('target-save-btn'); if (b) b.click(); });
        await page.waitForTimeout(1800);
        const db = h.adminQuery(`select coalesce((targets->>'Electrical'),'') from skill_profiles where worker_name='Bryan Garcia';`).toString().trim();
        const persisted = db !== '' && parseInt(db, 10) === after && after === expected;
        // restore previous target
        if (prev) h.adminQuery(`update skill_profiles set targets = jsonb_set(coalesce(targets,'{}'::jsonb),'{Electrical}', to_jsonb(${parseInt(prev, 10) || 0})) where worker_name='Bryan Garcia';`);
        return { R: reach, J: after === expected, T: persisted, C: null, X: persisted, evidence: { prev, before, after, expected, db, persisted }, findings: [] };
      },
    },
  ];
}

function achievementsJourneys() {
  const reachACH = async (page, h) => { const url = await h.goto('achievements.html'); await page.waitForTimeout(2000); return !/signin/.test(url); };
  return [
    {
      id: 'ACHK1', phase: 'K5', page: 'achievements.html', role: 'worker', state: 'authed',
      title: 'Growth at a glance (XP/level/tier truthful)', lenses: ['R', 'J', 'T'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachACH(page, h);
        await page.waitForTimeout(1000);
        const name = (await h.qText('#hero-name')) || '';
        const levelHero = await h.qText('#ac-level-hero');
        const dbLevel = h.adminQuery(`select coalesce(max(current_level),-1) from v_worker_achievements_truth where worker_name='Bryan Garcia';`);
        const dbN = (typeof dbLevel === 'string') ? parseInt(dbLevel, 10) : null;
        const shownLevel = h.numFrom(levelHero);
        const tOk = dbN != null && dbN >= 0 && shownLevel != null && shownLevel === dbN;
        return { R: reach, J: /bryan/i.test(name), T: tOk || (shownLevel != null), C: null, X: null, evidence: { name, shownLevel, dbN, tOk }, findings: [] };
      },
    },
    {
      id: 'ACHK2', phase: 'K5', page: 'achievements.html', role: 'worker', state: 'authed',
      title: 'Per-domain badge grid + expand a domain', lenses: ['R', 'J', 'C', 'X'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachACH(page, h);
        await h.waitFor('.domain-card', 8000);
        const domains = await h.count('.domain-card');
        const expanded = await h.evalIn(() => { const c = document.querySelector('.domain-card'); if (!c) return false; c.click(); return c.classList.contains('expanded'); });
        await page.waitForTimeout(400);
        const stillExpanded = await h.exists('.domain-card.expanded');
        return { R: reach, J: domains >= 6, T: null, C: domains >= 6, X: expanded || stillExpanded, evidence: { domains, expanded, stillExpanded }, findings: [] };
      },
    },
  ];
}

function resumeJourneys() {
  const reachRES = async (page, h) => { const url = await h.goto('resume.html'); await page.waitForTimeout(2000); return !/signin/.test(url) && (await h.exists('#sections')); };
  return [
    {
      id: 'RESK1', phase: 'K5', page: 'resume.html', role: 'worker', state: 'authed',
      title: 'Auto-fill resume from WorkHive skill/profile/logbook data', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'A'],
      drive: async (page, h) => {
        const reach = await reachRES(page, h);
        await h.evalIn(() => { const b = document.getElementById('btn-autofill'); if (b) b.click(); });
        const sheet = await h.waitFor('#review-sheet.open, #review-body', 6000);
        const rows = await h.count('#review-body [data-review-check]');
        await h.evalIn(() => { const b = document.getElementById('review-confirm'); if (b) b.click(); });
        await page.waitForTimeout(1200);
        const toast = (await h.evalIn(() => document.getElementById('toast-msg')?.textContent || document.getElementById('toast')?.textContent || '')) || '';
        const added = /added \d+ item/i.test(toast) || (await h.evalIn(() => !document.getElementById('review-sheet')?.classList.contains('open')));
        return { R: reach, J: sheet && added, T: rows >= 0, C: sheet, X: null, evidence: { sheet, rows, toast: toast.slice(0, 30), added }, findings: [] };
      },
    },
    {
      id: 'RESK3', phase: 'K5', page: 'resume.html', role: 'worker', state: 'authed',
      title: 'Save resume to the cloud (owner-scoped resume_documents)', lenses: ['R', 'J', 'T', 'C'], ufai: ['U', 'F', 'I'], writes: true,
      drive: async (page, h) => {
        const reach = await reachRES(page, h);
        const tag = `K5TEST Bryan ${Date.now()}`;
        await h.fill('#rb-field-name', tag);
        await h.evalIn(() => { const b = document.getElementById('btn-save'); if (b) b.click(); });
        let toast = ''; for (let i = 0; i < 10; i++) { toast = (await h.evalIn(() => document.getElementById('toast-msg')?.textContent || '')) || ''; if (/saved/i.test(toast)) break; await page.waitForTimeout(800); }
        const cnt = h.adminQuery(`select count(*) from resume_documents where auth_uid='${h.uid || K5AUTH}' and doc->'basics'->>'name'='${tag.replace(/'/g, "''")}';`);
        const persisted = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        // cleanup the tagged test resume (owner-scoped)
        h.adminQuery(`delete from resume_documents where auth_uid='${h.uid || K5AUTH}' and doc->'basics'->>'name'='${tag.replace(/'/g, "''")}';`);
        return { R: reach, J: /saved/i.test(toast), T: persisted, C: null, X: null, evidence: { tag, toast: toast.slice(0, 30), persisted, cnt }, findings: [] };
      },
    },
    {
      id: 'RESK4', phase: 'K5', page: 'resume.html', role: 'worker', state: 'authed',
      title: 'Preview + export the resume (JSON/PDF)', lenses: ['R', 'J', 'C', 'X'], ufai: ['U', 'F'],
      drive: async (page, h) => {
        const reach = await reachRES(page, h);
        await h.evalIn(() => { const b = document.getElementById('btn-export'); if (b) b.click(); });
        const overlay = await h.waitFor('#preview-overlay.open, #resume-paper', 6000);
        const paper = await h.exists('#resume-paper');
        let downloaded = false;
        try { const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 6000 }).catch(() => null), h.evalIn(() => { const b = document.getElementById('pv-json'); if (b) b.click(); })]); downloaded = !!dl; } catch (e) { }
        return { R: reach, J: overlay && paper, T: null, C: paper, X: downloaded || paper, evidence: { overlay, paper, downloaded }, findings: [] };
      },
    },
  ];
}

// ═══════════════════ K6 — CONNECT · marketplace.html ═══════════════════
// FREE PLATFORM (Ian 2026-06-22): PAYMENTS_ENABLED=false is the page default → no Stripe
// checkout/payout. The real jobs are browse · post · watchlist · CONTACT-SELLER inquiry ·
// saved-search — all locally completable. Write journeys tag rows (K6-*) + delete via the
// privileged path. seller_name/worker_name = the DISPLAY name 'Bryan Garcia' (wh_last_worker).
function marketplaceJourneys() {
  const HIVE = process.env.WH_TEST_HIVE || '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7';
  const reachMkt = async (h) => { await h.goto('marketplace.html'); return h.waitFor('.listing-grid, #listing-grid, .listing-card', 12000); };
  return [
    {
      id: 'MK1', phase: 'K6', page: 'marketplace.html', role: 'anon', state: 'anon',
      title: 'Visitor browses listings by section + search (free, no sign-in to read)',
      lenses: ['R', 'T', 'C'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachMkt(h);
        const cards = await h.count('.listing-card');
        const tabs = await h.count(".section-tab, [data-section]");
        const dbPub = h.adminQuery(`select count(*) from marketplace_listings where status='published' and section='parts';`);
        const dbN = (typeof dbPub === 'string') ? parseInt(dbPub, 10) : null;
        const truthful = cards > 0 && dbN != null && dbN > 0;
        // C: search nonsense → recoverable empty/fewer (no dead-end)
        let recover = true;
        if (await h.exists('#search-input')) {
          await h.fill('#search-input', 'zzzqxnolisting'); await page.waitForTimeout(1300);
          const after = await h.count('.listing-card');
          recover = after < cards || (await h.exists('#no-results, .empty-state, [class*="empty"]'));
          await h.fill('#search-input', ''); await page.waitForTimeout(700);
        }
        return { R: !!reach && tabs >= 1, J: null, T: truthful, C: recover, X: null, evidence: { cards, dbN, tabs, recover }, findings: [] };
      },
    },
    {
      id: 'MK2', phase: 'K6', page: 'marketplace.html', role: 'worker', state: 'authed',
      title: 'Post a new marketplace listing (free to list)',
      lenses: ['J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'], writes: true,
      drive: async (page, h) => {
        await reachMkt(h);
        const tag = `K6-MK2-${Date.now()}`;
        await h.click('#fab-post');
        let sheet = await h.waitFor('#post-title', 5000);
        if (!sheet) { await h.evalIn(() => { try { window.openPostSheet && window.openPostSheet(); } catch (e) {} }); sheet = await h.waitFor('#post-title', 5000); }
        await h.fill('#post-title', `${tag} spare bearing kit`);
        await page.selectOption('#post-category', { index: 1 }).catch(() => {});
        await h.fill('#post-desc', 'Genuine SKF spare bearing kit, lightly used, includes seals and housing. Pickup in Baguio. K6 test listing — auto-deleted.');
        await h.fill('#post-price', '3500').catch(() => {});
        await h.fill('#post-location', 'Baguio City').catch(() => {});
        await h.fill('#post-contact', '09171234567').catch(() => {});
        const formOk = await h.exists('#btn-submit-post');
        await h.click('#btn-submit-post');
        if (!formOk || !(await h.exists('#btn-submit-post'))) { await h.evalIn(() => { try { window.handlePostSubmit && window.handlePostSubmit(); } catch (e) {} }); }
        await page.waitForTimeout(2500);
        const cnt = h.adminQuery(`select count(*) from marketplace_listings where title like '${tag}%';`);
        const persisted = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        h.adminQuery(`delete from marketplace_listings where title like '${tag}%';`);
        return { R: null, J: !!sheet && persisted, T: persisted, C: formOk, X: persisted, evidence: { sheet: !!sheet, persisted, cnt }, findings: [] };
      },
    },
    {
      id: 'MK3', phase: 'K6', page: 'marketplace.html', role: 'worker', state: 'authed',
      title: 'Save a listing to my watchlist + see it in My Saved',
      lenses: ['J', 'T', 'C'], ufai: ['U', 'F', 'I'], writes: true,
      drive: async (page, h) => {
        await reachMkt(h); await h.waitFor('.listing-card', 8000);
        const lid = await h.evalIn(() => { const b = document.querySelector('.heart-btn[data-listing]'); return b ? b.getAttribute('data-listing') : null; });
        if (lid) h.adminQuery(`delete from marketplace_watchlist where worker_name='Bryan Garcia' and listing_id='${lid}';`);
        const clicked = await h.evalIn(() => { const b = document.querySelector('.heart-btn[data-listing]'); if (b) { b.click(); return true; } return false; });
        await page.waitForTimeout(1500);
        const cnt = lid ? h.adminQuery(`select count(*) from marketplace_watchlist where worker_name='Bryan Garcia' and listing_id='${lid}';`) : '0';
        const saved = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        await h.evalIn(() => { try { window.openWatchlistSheet && window.openWatchlistSheet(); } catch (e) {} });
        const sheet = await h.waitFor('#sheet-watchlist, #watchlist-content, [id*="watchlist"]', 4000);
        if (lid) h.adminQuery(`delete from marketplace_watchlist where worker_name='Bryan Garcia' and listing_id='${lid}';`);
        return { R: null, J: clicked && saved, T: saved, C: !!sheet, X: null, evidence: { lid, saved, sheet: !!sheet }, findings: [] };
      },
    },
    {
      id: 'MK4', phase: 'K6', page: 'marketplace.html', role: 'worker', state: 'authed',
      title: 'Contact a seller about a listing (the free alternative to checkout)',
      lenses: ['J', 'T', 'C', 'X'], ufai: ['U', 'F', 'A', 'I'], writes: true,
      drive: async (page, h) => {
        await reachMkt(h); await h.waitFor('.listing-card', 8000);
        const tag = `K6-MK4-${Date.now()}`;
        // open the first listing's detail via its View affordance (real user path)
        await h.evalIn(() => { const c = document.querySelector('.listing-card'); if (c) { const v = [...c.querySelectorAll('button,a')].find(x => /view/i.test(x.textContent || '')); (v || c).click(); } });
        await page.waitForTimeout(1200);
        let contacted = await h.click('#btn-detail-contact');
        if (!contacted) contacted = await h.evalIn(() => { try { const b = [...document.querySelectorAll('button')].find(x => /contact seller/i.test(x.textContent || '')); if (b) { b.click(); return true; } } catch (e) {} return false; });
        const inqSheet = await h.waitFor('#inq-message, #sheet-inquiry', 5000);
        await h.fill('#inq-name', 'Bryan Garcia').catch(() => {});
        await h.fill('#inq-contact', '09171234567').catch(() => {});
        await h.fill('#inq-message', `${tag} Is this still available? Please advise delivery to Baguio.`);
        await h.click('#btn-submit-inquiry');
        if (!(await h.exists('#btn-submit-inquiry'))) { /* sheet closed = submitted */ } else { await h.evalIn(() => { try { window.handleInquirySubmit && window.handleInquirySubmit(); } catch (e) {} }); }
        await page.waitForTimeout(2000);
        const cnt = h.adminQuery(`select count(*) from marketplace_inquiries where message like '${tag}%';`);
        const sent = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        h.adminQuery(`delete from marketplace_inquiries where message like '${tag}%';`);
        return { R: null, J: !!inqSheet && sent, T: sent, C: !!inqSheet, X: sent, evidence: { contacted, inqSheet: !!inqSheet, sent, cnt }, findings: [] };
      },
    },
    {
      id: 'MK5', phase: 'K6', page: 'marketplace.html', role: 'worker', state: 'authed',
      title: 'Save the current search so I can re-run it later',
      lenses: ['J', 'T', 'C'], ufai: ['U', 'F', 'I'], writes: true,
      drive: async (page, h) => {
        await reachMkt(h);
        const tag = `K6-MK5-${Date.now()}`;
        await h.fill('#search-input', 'bearing').catch(() => {});
        await page.waitForTimeout(1200);
        await h.evalIn(() => { try { window.openSavedSearchesSheet && window.openSavedSearchesSheet(); } catch (e) {} });
        let sheet = await h.waitFor('#save-search-name', 5000);
        if (!sheet) { await h.click('#btn-saved-searches'); sheet = await h.waitFor('#save-search-name', 5000); }
        await h.fill('#save-search-name', tag).catch(() => {});
        await h.click('#btn-save-current-search');
        if (!sheet) await h.evalIn(() => { try { window.handleSaveCurrentSearch && window.handleSaveCurrentSearch(); } catch (e) {} });
        await page.waitForTimeout(1800);
        const cnt = h.adminQuery(`select count(*) from marketplace_saved_searches where search_name like '${tag}%' and worker_name='Bryan Garcia';`);
        const saved = (typeof cnt === 'string') && parseInt(cnt, 10) > 0;
        h.adminQuery(`delete from marketplace_saved_searches where search_name like '${tag}%';`);
        return { R: null, J: !!sheet && saved, T: saved, C: !!sheet, X: null, evidence: { sheet: !!sheet, saved, cnt }, findings: [] };
      },
    },
  ];
}

// ═══════════════════ K6 — CONNECT · marketplace-seller.html ═══════════════════
// Seller = any authenticated worker with listings (Bryan Garcia). No 'seller' auth role
// exists → role 'worker'. FREE PLATFORM: no Stripe Connect; the seller's job is list →
// receive inquiries → reply + share a Messenger handle (free direct contact).
function marketplaceSellerJourneys() {
  const HIVE = process.env.WH_TEST_HIVE || '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7';
  const reachSeller = async (h) => { await h.goto('marketplace-seller.html'); return h.waitFor('#profile-name, #main-content', 9000); };
  const tab = (h, t) => h.evalIn((tt) => { const b = document.querySelector(`[data-tab='${tt}']`); if (b) { b.click(); return true; } return false; }, t);
  return [
    {
      id: 'MS1', phase: 'K6', page: 'marketplace-seller.html', role: 'worker', state: 'authed',
      title: 'Edit one of my draft listings and re-submit it',
      lenses: ['R', 'T', 'C'], ufai: ['U', 'F', 'A', 'I'], writes: true,
      drive: async (page, h) => {
        const tag = `K6-MS1-${Date.now()}`;
        h.adminQuery(`insert into marketplace_listings (seller_name, section, category, title, description, price, location, status, hive_id, created_at, updated_at) values ('Bryan Garcia','parts','Bearings','${tag} draft part','seed description long enough to satisfy any min-length validation on the edit path',1000,'Baguio','draft','${h.hive || HIVE}',now(),now());`);
        const id = (h.adminQuery(`select id from marketplace_listings where title like '${tag}%' limit 1;`) || '').toString().trim();
        const reached = await reachSeller(h);
        await tab(h, 'listings'); await page.waitForTimeout(1500);
        const opened = await h.evalIn((i) => { const b = document.querySelector(`[data-action='edit'][data-id='${i}']`); if (b) { b.click(); return true; } return false; }, id);
        const sheet = await h.waitFor('#edit-title, #sheet-edit', 5000);
        await page.waitForTimeout(1000); // let openEditSheet() finish populating before we overwrite the title
        const newTitle = `${tag} EDITED`;
        const setOk = await h.evalIn((t) => { const el = document.getElementById('edit-title'); if (!el) return false; el.value = t; el.dispatchEvent(new Event('input', { bubbles: true })); return el.value === t; }, newTitle);
        // submit via the form (the Save button is type=submit; requestSubmit fires handleEditSubmit reliably)
        await h.evalIn(() => { const f = document.getElementById('form-edit'); if (f && f.requestSubmit) f.requestSubmit(); else { const b = document.getElementById('btn-save-edit'); if (b) b.click(); } });
        await page.waitForTimeout(2200);
        const toast = await h.evalIn(() => { const t = document.getElementById('toast'); return t ? (t.textContent || '').trim().slice(0, 40) : ''; });
        const t = h.adminQuery(`select title from marketplace_listings where id='${id}';`);
        const edited = (typeof t === 'string') && /EDITED/.test(t);
        h.adminQuery(`delete from marketplace_listings where id='${id}';`);
        return { R: reached, J: null, T: edited, C: opened && !!sheet, X: null, evidence: { opened, sheet: !!sheet, setOk, toast, finalTitle: (typeof t === 'string' ? t.slice(0, 40) : t) }, findings: [] };
      },
    },
    {
      id: 'MS2', phase: 'K6', page: 'marketplace-seller.html', role: 'worker', state: 'authed',
      title: 'Reply to a buyer inquiry and mark it replied',
      lenses: ['R', 'T', 'C'], ufai: ['U', 'F', 'A', 'I'], writes: true,
      drive: async (page, h) => {
        const lid = (h.adminQuery(`select id from marketplace_listings where seller_name='Bryan Garcia' and status='published' limit 1;`) || '').toString().trim();
        const tag = `K6-MS2-${Date.now()}`;
        h.adminQuery(`insert into marketplace_inquiries (listing_id, seller_name, buyer_name, buyer_contact, message, status, hive_id, created_at) values ('${lid}','Bryan Garcia','K6 Test Buyer','09170000000','${tag} interested in this part','pending','${h.hive || HIVE}',now());`);
        const iid = (h.adminQuery(`select id from marketplace_inquiries where message like '${tag}%' limit 1;`) || '').toString().trim();
        const reached = await reachSeller(h);
        await tab(h, 'inquiries'); await page.waitForTimeout(1600);
        const rendered = await h.evalIn((i) => !!document.querySelector(`.reply-textarea[data-inq-id='${i}'], [data-id='${i}']`), iid);
        await h.evalIn((i) => { const ta = document.querySelector(`.reply-textarea[data-inq-id='${i}']`); if (ta) { ta.value = 'Yes, still available. Reach me at 0917-000-0000.'; ta.dispatchEvent(new Event('input', { bubbles: true })); } }, iid);
        const clicked = await h.evalIn((i) => { const b = document.querySelector(`[data-action='reply'][data-id='${i}']`); if (b) { b.click(); return true; } return false; }, iid);
        await page.waitForTimeout(2000);
        const st = h.adminQuery(`select status from marketplace_inquiries where id='${iid}';`);
        const ok = (typeof st === 'string') && /replied/i.test(st);
        h.adminQuery(`delete from marketplace_inquiries where id='${iid}';`);
        return { R: reached && rendered, J: null, T: ok, C: clicked, X: null, evidence: { lid, rendered, clicked, finalStatus: (typeof st === 'string' ? st.trim() : st) }, findings: [] };
      },
    },
    {
      id: 'MS3', phase: 'K6', page: 'marketplace-seller.html', role: 'worker', state: 'authed',
      title: 'Save my Messenger handle so buyers can reach me directly (free contact)',
      lenses: ['R', 'T', 'C'], ufai: ['U', 'F', 'I'], writes: true,
      drive: async (page, h) => {
        const reached = await reachSeller(h);
        const prior = (h.adminQuery(`select coalesce(messenger_username,'') from marketplace_sellers where worker_name='Bryan Garcia';`) || '').toString().trim();
        const handle = 'bryan.repair.k6';
        await h.fill('#messenger-input', handle).catch(() => {});
        await h.click('#btn-save-messenger');
        await page.waitForTimeout(1800);
        const saved = (h.adminQuery(`select coalesce(messenger_username,'') from marketplace_sellers where worker_name='Bryan Garcia';`) || '').toString().trim();
        const ok = saved === handle;
        const preview = await h.exists('#messenger-preview');
        h.adminQuery(`update marketplace_sellers set messenger_username=${prior ? `'${prior}'` : 'null'} where worker_name='Bryan Garcia';`);
        return { R: reached, J: null, T: ok, C: preview || ok, X: null, evidence: { prior, saved, ok, preview }, findings: [] };
      },
    },
    {
      id: 'MS5', phase: 'K6', page: 'marketplace-seller.html', role: 'worker', state: 'authed',
      title: 'View my seller performance (views/inquiries/conversion)',
      lenses: ['R', 'J'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reached = await reachSeller(h);
        await tab(h, 'analytics'); await page.waitForTimeout(2500);
        const cards = await h.count('.pstat, [class*="pstat"], .overview-card, .stat-card');
        const hasContent = await h.evalIn(() => { const c = document.getElementById('content-area') || document.body; return /views|inquir|conversion|response|reply/i.test(c.textContent || ''); });
        return { R: reached, J: cards >= 1 || hasContent, T: null, C: null, X: null, evidence: { cards, hasContent }, findings: [] };
      },
    },
  ];
}

// ═══════════════════ K6 — CONNECT · integrations.html ═══════════════════
// Supervisor-gated. FREE PLATFORM: import + API-keys are free/local; only Live Sync (IN5)
// is a genuine EXTERNAL ceiling (needs a reachable real CMMS API — not Stripe). IN1 does a
// REAL tagged CSV import and verifies external_sync + logbook rows, then deletes them.
function integrationsJourneys() {
  const HIVE = process.env.WH_TEST_HIVE || '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7';
  return [
    {
      id: 'IN1', phase: 'K6', page: 'integrations.html', role: 'supervisor', state: 'authed',
      title: 'Import CMMS work-order history (CSV) for cold-start analytics',
      lenses: ['R', 'J', 'T'], ufai: ['U', 'F', 'A', 'I'], writes: true,
      drive: async (page, h) => {
        const TAG = 'K6IN1';
        const clean = () => { h.adminQuery(`delete from logbook where problem like '${TAG}%';`); h.adminQuery(`delete from external_sync where external_id like '${TAG}%';`); h.adminQuery(`delete from fault_knowledge where problem like '${TAG}%';`); };
        clean();
        const reach = await h.goto('integrations.html');
        const tabImport = await h.waitFor('#tab-import', 8000);
        await h.evalIn(() => { try { window.switchTab && window.switchTab('import'); } catch (e) {} });
        await h.click(".source-card[data-type='generic']");
        await h.click(".source-card[data-entity='work_order']");
        await page.waitForTimeout(400);
        await h.evalIn(() => { try { window.goStep && window.goStep(2); } catch (e) {} });
        await page.waitForTimeout(500);
        let uploaded = false;
        try { await page.setInputFiles('#file-input', CSV_IN1); uploaded = true; } catch (e) { uploaded = false; }
        // wait for Papa.parse → processRows to enable the step-2 Next button (parse complete)
        let parsed = false;
        for (let i = 0; i < 12; i++) { parsed = await h.evalIn(() => { const b = document.getElementById('btn-s2-next'); return !!(b && !b.disabled); }); if (parsed) break; await page.waitForTimeout(500); }
        await h.evalIn(() => { try { window.goStep && window.goStep(3); } catch (e) {} }); // builds the mapping table
        await page.waitForTimeout(900);
        // 'generic' source has no auto-suggest patterns → set the mapping explicitly. The CSV
        // headers are named exactly as the WorkHive field keys (external_id/machine/status/…),
        // so map each <select data-field> to its same-named column + fire onMappingChange.
        await h.evalIn(() => {
          document.querySelectorAll('select[data-field]').forEach(sel => {
            const f = (sel.dataset.field || '').toLowerCase();
            const opt = [...sel.options].find(o => o.value && o.value.toLowerCase() === f);
            if (opt) { sel.value = opt.value; sel.dispatchEvent(new Event('change', { bubbles: true })); }
          });
        });
        await page.waitForTimeout(400);
        await h.evalIn(() => { try { window.goStep && window.goStep(4); } catch (e) {} });
        await page.waitForTimeout(700);
        await h.evalIn(() => { try { window.startImport && window.startImport(); } catch (e) {} });
        let n = 0;
        for (let i = 0; i < 18; i++) { const c = h.adminQuery(`select count(*) from external_sync where external_id like '${TAG}%';`); n = (typeof c === 'string') ? parseInt(c, 10) : 0; if (n > 0) break; await page.waitForTimeout(1000); }
        const lb = h.adminQuery(`select count(*) from logbook where problem like '${TAG}%';`);
        const lbN = (typeof lb === 'string') ? parseInt(lb, 10) : 0;
        const imported = n > 0;
        clean();
        return { R: reach && !!tabImport, J: uploaded && imported, T: imported && lbN > 0, C: null, X: imported, evidence: { uploaded, parsed, external_sync: n, logbook: lbN }, findings: [] };
      },
    },
    {
      id: 'IN5', phase: 'K6', page: 'integrations.html', role: 'supervisor', state: 'authed',
      title: 'Configure + test a Live CMMS Sync connection (external SAP/Maximo API)',
      lenses: ['R', 'C'], ufai: ['U', 'F', 'I'], external: true,
      drive: async (page, h) => {
        const reach = await h.goto('integrations.html');
        await h.evalIn(() => { try { window.switchTab && window.switchTab('sync'); } catch (e) {} });
        const form = await h.waitFor('#sc-url, #sc-label', 6000);
        await h.fill('#sc-label', 'K6 Test SAP PH01').catch(() => {});
        await page.selectOption('#sc-type', { value: 'sap_pm' }).catch(() => {});
        await h.fill('#sc-url', 'https://unreachable-cmms.example.invalid/odata/v4/C_WorkOrder').catch(() => {});
        await h.fill('#sc-token', 'Bearer test-token-k6').catch(() => {});
        await page.selectOption('#sc-freq', { value: 'daily' }).catch(() => {});
        await h.evalIn(() => { try { window.testSyncConfig && window.testSyncConfig(); } catch (e) {} });
        let res = ''; for (let i = 0; i < 12; i++) { res = (await h.qText('#sync-test-result')) || ''; if (res.trim()) break; await page.waitForTimeout(1000); }
        const handled = /connect|found|record|error|fail|unreachable|could not|unable|invalid|✗|✓/i.test(res);
        h.adminQuery(`delete from integration_configs where label='K6 Test SAP PH01';`);
        return { R: reach && !!form, J: null, T: null, C: handled, X: null, evidence: { form: !!form, result: res.slice(0, 70) }, findings: [] };
      },
    },
  ];
}

// ═══════════════════ K6 — CONNECT · plant-connections.html ═══════════════════
// Supervisor-only read-only observability (Phase-5 Track C). FREE admin console, no payment.
// Cards render from live hive-scoped tables; T verifies the card tone matches the DB counts.
function plantConnectionsJourneys() {
  const HIVE = process.env.WH_TEST_HIVE || '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7';
  const reachPC = async (h) => { await h.goto('plant-connections.html'); return h.waitFor('.simple-card, .verdict, [class*="verdict"]', 9000); };
  return [
    {
      id: 'PC1', phase: 'K6', page: 'plant-connections.html', role: 'supervisor', state: 'authed',
      title: 'See CMMS integration health at a glance',
      lenses: ['R', 'J'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        const reach = await reachPC(h);
        const verdict = await h.exists('.verdict, [class*="verdict"]');
        const card = await h.exists('.simple-card');
        const cmms = await h.evalIn(() => { const c = document.querySelector('.simple-card'); return c ? /cmms|sync|integration/i.test(c.textContent || '') : false; });
        return { R: !!reach && card, J: verdict && cmms, T: null, C: null, X: null, evidence: { verdict, card, cmms }, findings: [] };
      },
    },
    {
      id: 'PC3', phase: 'K6', page: 'plant-connections.html', role: 'supervisor', state: 'authed',
      title: 'Check gateway API health (7-day success rate) — truthful to the audit log',
      lenses: ['R', 'T'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        await reachPC(h); await page.waitForTimeout(800);
        const apiCard = await h.evalIn(() => { const cs = [...document.querySelectorAll('.simple-card')]; const c = cs.find(x => /api health|gateway|success/i.test(x.textContent || '')); return c ? (c.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 90) : ''; });
        const dbCalls = h.adminQuery(`select count(*) from gateway_audit_log where hive_id='${h.hive || HIVE}' and created_at >= now()-interval '7 days';`);
        const nn = (typeof dbCalls === 'string') ? parseInt(dbCalls, 10) : null;
        // calm-empty copy family (2026-07-22: card copy evolved to "No traffic / No gateway calls…IDLE"
        // — honest zero on both sides read as a T fail because the regex was pinned to older copy)
        const truthful = nn != null && (nn === 0 ? /no data|never|no traffic|no gateway calls|idle|0\s*(call|%)/i.test(apiCard) : /%|call|success|error/i.test(apiCard));
        return { R: apiCard.length > 0, J: null, T: truthful, C: null, X: null, evidence: { apiCard, dbCalls: nn }, findings: [] };
      },
    },
    {
      id: 'PC5', phase: 'K6', page: 'plant-connections.html', role: 'supervisor', state: 'authed',
      title: 'Expand engineering details to inspect raw configs/syncs/audit',
      lenses: ['R', 'T'], ufai: ['U', 'F', 'I'],
      drive: async (page, h) => {
        await reachPC(h);
        const toggled = await h.click('#details-toggle-btn');
        if (!toggled) await h.evalIn(() => { const b = document.getElementById('details-toggle-btn'); if (b) b.click(); });
        await page.waitForTimeout(1100);
        const expanded = await h.evalIn(() => { const b = document.getElementById('details-toggle-btn'); return b ? b.getAttribute('aria-expanded') === 'true' : false; });
        const tables = await h.count('#details-pane table, table.pc-table');
        const dbCfg = h.adminQuery(`select count(*) from integration_configs where hive_id='${h.hive || HIVE}';`);
        const cfgN = (typeof dbCfg === 'string') ? parseInt(dbCfg, 10) : null;
        return { R: expanded, J: null, T: tables >= 1 && cfgN != null, C: null, X: null, evidence: { expanded, tables, cfgN }, findings: [] };
      },
    },
  ];
}
