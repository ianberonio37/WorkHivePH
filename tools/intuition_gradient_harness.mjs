/* ============================================================================
 * intuition_gradient_harness.mjs — Arc Y (THE INTUITION GRADIENT) · Y0 harness
 * ============================================================================
 * A persona-driven, OPERATE-AND-OBSERVE cognitive-walkthrough harness. NOT a
 * screenshot referee — it loads each surface as a persona at TRUE CSS width and
 * scores the deterministic signals of the 5 intuitiveness lenses, emitting a
 * per-surface + per-persona Intuition-Gradient scorecard (measured %, not vibes).
 *
 * THE GRADIENT (Ian's bar: "intuitive to ALL users"): the SAME page scores
 * differently for a novice field worker vs a reliability-literate engineer vs an
 * ops supervisor. The spread between them IS the intuition gradient; the NOVICE
 * floor is the gate (a page intuitive only to the expert FAILS the arc).
 *
 * PERSONAS (auth reality: the DB has only `worker` + `supervisor` roles — there
 * is no distinct "engineer" auth role; engineer is a COMPREHENSION persona on the
 * supervisor session). We therefore run the 2 real auth sessions and derive 3
 * persona scores by re-weighting the SAME measured DOM signals through
 * persona-specific lens weights (documented in PERSONAS below) — honest: the
 * measurement is real, the persona view is a transparent re-weighting.
 *   - worker     (novice)     → punishes jargon (L1) + overwhelm (L3) hardest
 *   - engineer   (RE-literate)→ jargon-tolerant; cares about cross-surface (L4)+affordance
 *   - supervisor (ops-literate)→ density-tolerant; cares about flow/back (L5)+cross-surface
 *
 * Lenses (deterministic signal measured here):
 *   L1 Comprehension — jargon terms present with NO plain-language gloss nearby
 *   L3 Overwhelm     — first-paint INTERACTIVE element count at 390px (>12 = flag)
 *   L4 Cross-surface — a displayed KPI matches the DB truth via the page's OWN
 *                      authed client (Gulf-of-Evaluation; READ-ONLY, no DB writes)
 *   L5 Flow/Back     — is there an in-app Back / breadcrumb affordance? (FAB-only = fail)
 *   L6 Affordance    — dead clickables (href=#/void, empty onclick) + unlabeled inputs
 *   (L2 Redundancy is a JUDGMENT lens — the harness emits a cross-page label
 *    corpus → intuition_gradient_corpus.json → tools/ia_semantic_critic.py.)
 *
 * Usage:  node tools/intuition_gradient_harness.mjs [--all] [--pages a,b,c] [--roles worker,supervisor]
 * Output: intuition_gradient_report.json   (per-surface × per-persona scorecard + aggregate)
 *         intuition_gradient_corpus.json    (L2 redundancy corpus for the semantic critic)
 * Reuses the live_page_journeys sign-in shape (real Supabase session + hive keys).
 * ==========================================================================*/
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

const BASE   = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL  || 'http://127.0.0.1:54321';
const HIVE   = process.env.WH_TEST_HIVE     || '636cf7e8-431a-4907-8a9f-43dd4cc216d6'; // hive fallback only — signIn resolves the real hive from the live membership

// Real auth accounts (live DB): worker + supervisor only. engineer == supervisor session.
const ACCOUNTS = {
  worker:     { email: 'bryangarcia@auth.workhiveph.com',   pw: 'test1234', worker: 'Bryan Garcia',    role: 'worker' },
  supervisor: { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234', worker: 'Leandro Marquez', role: 'supervisor' },
};
const HIVE_NAME = 'Baguio Textile Mills';

// Persona lens-weights (sum to 1 per persona). The measured signals are identical;
// the persona is WHO is reading and therefore what hurts most.
const PERSONAS = {
  worker:     { authRole: 'worker',     w: { L1: 0.34, L3: 0.30, L4: 0.12, L5: 0.12, L6: 0.12 } }, // novice: comprehension+overwhelm dominate
  engineer:   { authRole: 'supervisor', w: { L1: 0.08, L3: 0.18, L4: 0.32, L5: 0.18, L6: 0.24 } }, // jargon-tolerant: cross-surface+affordance
  supervisor: { authRole: 'supervisor', w: { L1: 0.12, L3: 0.14, L4: 0.30, L5: 0.30, L6: 0.14 } }, // density-tolerant: flow/back+cross-surface
};

// CSS width of the design target (phone-first). Playwright viewport is in CSS px.
const VW = 390, VH = 844;
const OVERWHELM_BUDGET = 12;   // >12 first-paint interactive elements demands disclosure

// L1 jargon dictionary: terms a novice Filipino technician would NOT know cold.
// Scored as a comprehension flag ONLY when the term appears with no plain gloss
// (a parenthetical / "i.e." / title= / adjacent sub-line) within ~120 chars.
const JARGON = [
  'FMEA','RPN','\\bSOD\\b','Weibull','\\bbeta\\b','\\beta\\b','\\bP-F\\b','RCM','JA1011','AIAG',
  'wearout','infant mortality','Spearman','\\bSPC\\b','Z-score','bathtub',
  'parent_of','redundant_with','\\bedge\\b','MTBF','MTTR','SMRP','ISO 14224','ISO 55001',
  'descriptive','diagnostic','predictive','prescriptive','escrow','KYB','tsvector',
];
const GLOSS_HINT = /\(|\bi\.e\.|\be\.g\.|\bmeans\b|title="/i;

// ─── L4 cross-surface VALUE-CONSISTENCY registry (READ-ONLY) ───────────────────
// "When this page shows a number, is it the DB truth?" A silent/contradictory loop
// (the F4 hive-board finding) is the Gulf of Evaluation made measurable WITHOUT any
// write. Each entry: a page, a fn that reads the DISPLAYED value from the DOM, and a
// fn that reads the TRUTH from the page's own authed supabase client. score = match.
// `db` runs (db, hive) => value in-page; `dom` runs () => number-or-null in-page.
// Pages not listed get L4 = null (N/A, excluded from their denominator).
const L4_CHECKS = {
  // Hive board verdict vs open-WO truth (F4: "mostly healthy" contradicting "8 open WOs")
  'hive.html': {
    label: 'open work-orders shown == open WOs in DB',
    dom: () => {
      const t = document.body.innerText;
      const m = t.match(/(\d+)\s+open\s+(?:WOs?|work[\s-]?orders?)/i);
      return m ? parseInt(m[1], 10) : null;
    },
    db: async (db, hive) => {
      try {
        // canonical fuel the hive board declares for stat-open: v_logbook_truth, status='Open'
        const { count } = await db.from('v_logbook_truth').select('id', { count: 'exact', head: true })
          .eq('hive_id', hive).eq('status', 'Open');
        return count ?? null;
      } catch (e) { return null; }
    },
  },
  // Inventory low-stock count shown vs DB truth (same canonical fuel the hive board uses:
  // v_inventory_items_truth.is_low_stock, hive + status='approved'). Unambiguous, non-PM.
  'inventory.html': {
    label: 'low-stock count shown == is_low_stock rows in DB',
    dom: () => {
      var el = document.getElementById('inv-low-hero') || document.getElementById('stat-low');
      if (el) { var n = parseInt((el.textContent || '').replace(/[^0-9]/g, ''), 10); if (!isNaN(n)) return n; }
      var m = (document.body.innerText || '').match(/(\d+)\s+(?:items?\s+)?low[\s-]?stock/i);
      return m ? parseInt(m[1], 10) : null;
    },
    db: async (db, hive) => {
      try {
        // inventory's "Low Stock" tile shows LOW excluding OUT-OF-STOCK (the out-of-stock
        // count is a separate tile); is_low_stock alone INCLUDES out-of-stock, so exclude it.
        const { count } = await db.from('v_inventory_items_truth').select('id', { count: 'exact', head: true })
          .eq('hive_id', hive).eq('status', 'approved').eq('is_low_stock', true).eq('is_out_of_stock', false);
        return count ?? null;
      } catch (e) { return null; }
    },
  },
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ─── canonical feature-page set (~42): all *.html minus backups + test variants ──
function canonicalPages() {
  const EXCLUDE = /(\.backup\d*\.html$)|(-test\.html$)/i;
  return fs.readdirSync(ROOT)
    .filter(f => f.endsWith('.html') && !EXCLUDE.test(f))
    .sort();
}

async function signIn(context, role) {
  const acct = ACCOUNTS[role];
  const page = await context.newPage();
  await page.goto(`${BASE}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof window.getDb === 'function' && !!window.SUPABASE_KEY, { timeout: 15000 }).catch(() => {});
  const r = await page.evaluate(async ({ acct, hive, hiveName, url }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
      // resolve the REAL hive from the live membership (test_identity pattern); the passed
      // constant is a stale-known fallback (pins rot across reseeds).
      let realHive = hive;
      try {
        const uid = data?.session?.user?.id;
        const { data: mem } = uid ? await db.from('hive_members').select('hive_id')
          .eq('auth_uid', uid).eq('status', 'active').limit(1).maybeSingle() : { data: null };
        if (mem && mem.hive_id) realHive = mem.hive_id;
      } catch (_) { /* keep fallback */ }
      localStorage.setItem('wh_active_hive_id', realHive); localStorage.setItem('wh_hive_id', realHive);
      localStorage.setItem('wh_last_worker', acct.worker); localStorage.setItem('wh_hive_name', hiveName);
      localStorage.setItem('wh_hive_role', acct.role);
      if (acct.role === 'supervisor') localStorage.setItem('wh_nav_mode', 'supervisor');
      else localStorage.removeItem('wh_nav_mode');
      return { ok: !error && !!data?.session, err: error ? String(error.message || error) : null };
    } catch (e) { return { ok: false, err: String(e) }; }
  }, { acct, hive: HIVE, hiveName: HIVE_NAME, url: SB_URL });
  await page.close();
  return r;
}

async function scorePage(context, slug, role) {
  const page = await context.newPage();
  await page.setViewportSize({ width: VW, height: VH });
  const card = { page: slug, role };
  try {
    await page.goto(`${BASE}/workhive/${slug}`, { waitUntil: 'domcontentloaded' });
    await sleep(2600); // let the live render settle
    const m = await page.evaluate(({ budget, jargon, glossSrc }) => {
      const glossRe = new RegExp(glossSrc, 'i');
      const vh = window.innerHeight, vw = window.innerWidth;
      const isVisible = (el) => {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity) > 0.05;
      };
      const inFirstPaint = (el) => { const r = el.getBoundingClientRect(); return r.top < vh && r.bottom > 0 && r.left < vw && r.right > 0; };
      // Persistent SHARED CHROME present on every page (companion launcher wh-ai-*, nav-hub
      // wh-hub-*, feedback FAB, connectivity chip, wayfinding back/breadcrumb). These are
      // CONSTANT affordances, not the page's CONTENT — counting them as "overwhelm" inflates
      // every page by ~10 and makes the progressive-disclosure budget meaningless. L3 measures
      // CONTENT cognitive load, so exclude them (calibrate the instrument to its stated intent).
      const CHROME_SEL = '[id^="wh-"], .back-btn, .wf-back, .wf-crumb, #wh-wayfinding';
      const isChrome = (el) => !!el.closest(CHROME_SEL);
      // L3 — first-paint interactive CONTENT elements (chrome excluded)
      const interactives = [...document.querySelectorAll('a,button,input,select,textarea,[role="button"],[role="tab"],[onclick]')]
        .filter(e => isVisible(e) && inFirstPaint(e) && !isChrome(e));
      // L5 — in-app back / breadcrumb affordance (NOT the tool-switcher FAB)
      const backAff = [...document.querySelectorAll('a,button,[role="link"]')].some(e => {
        const t = (e.textContent || '').trim().toLowerCase();
        const al = (e.getAttribute('aria-label') || '').toLowerCase();
        return isVisible(e) && (/^(back|‹|<|←|‹)\b/.test(t) || /\bback\b/.test(al) || e.classList.contains('back-btn') || e.classList.contains('breadcrumb'));
      });
      const hasBreadcrumb = !!document.querySelector('.breadcrumb,[aria-label="breadcrumb"],nav.crumbs');
      // L6 — dead clickables + unlabeled inputs
      const links = [...document.querySelectorAll('a[href]')];
      const dead = links.filter(a => { const h=a.getAttribute('href'); return h==='#'||/^javascript:\s*void/.test(h||''); }).length;
      const inputs = [...document.querySelectorAll('input,select,textarea')].filter(e => {
        const t=(e.type||'').toLowerCase(); return !['hidden','submit','button','checkbox','radio','range','file','color'].includes(t) && isVisible(e);
      });
      const labelFor = new Set([...document.querySelectorAll('label[for]')].map(l=>l.getAttribute('for')));
      const unlabeled = inputs.filter(e => !(e.getAttribute('aria-label')||e.getAttribute('aria-labelledby')||(e.id&&labelFor.has(e.id))||e.closest('label'))).length;
      // L1 — jargon without a nearby gloss (scan visible text)
      const bodyText = document.body.innerText;
      const jargonHits = [];
      for (const j of jargon) {
        const re = new RegExp(j, 'i'); const mm = re.exec(bodyText);
        if (mm) {
          const around = bodyText.slice(Math.max(0, mm.index-80), mm.index + 120);
          if (!glossRe.test(around)) jargonHits.push(j.replace(/\\b/g,''));
        }
      }
      // L2 corpus — the visible section/KPI/tab labels on this page (for the semantic critic)
      const labels = [...document.querySelectorAll('h1,h2,h3,h4,[role="tab"],.kpi-label,.card-title,.section-title,.tile-label')]
        .filter(isVisible).map(e => (e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 80))
        .filter(Boolean).slice(0, 40);
      return { firstPaintInteractive: interactives.length, overwhelm: interactives.length > budget,
               backAffordance: backAff || hasBreadcrumb, deadLinks: dead, unlabeledInputs: unlabeled,
               jargonNoGloss: [...new Set(jargonHits)], labels: [...new Set(labels)],
               totalInteractiveOnPage: document.querySelectorAll('a,button,input,select,textarea').length };
    }, { budget: OVERWHELM_BUDGET, jargon: JARGON, glossSrc: GLOSS_HINT.source });
    Object.assign(card, m);

    // ── L4 cross-surface value consistency (READ-ONLY) ──
    let L4 = null;
    const chk = L4_CHECKS[slug];
    if (chk) {
      const shown = await page.evaluate((src) => { try { return (eval('(' + src + ')'))(); } catch (e) { return null; } }, chk.dom.toString());
      const truth = await page.evaluate(async ({ src, hive, url }) => {
        try {
          const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
          return await (eval('(' + src + ')'))(db, hive);
        } catch (e) { return null; }
      }, { src: chk.db.toString(), hive: HIVE, url: SB_URL });
      card.l4 = { label: chk.label, shown, truth };
      // both readable + equal → loop is truthful (1); readable + mismatch → silent/contradictory (0);
      // unreadable (null on either side) → can't probe this run → leave L4 null (N/A, not a fail)
      if (shown != null && truth != null) L4 = (Number(shown) === Number(truth)) ? 1 : 0;
    }

    // L1/L3/L4/L5/L6 → per-lens 0..1 intuition score (1 = good)
    const lens = {
      L1: m.jargonNoGloss.length === 0 ? 1 : Math.max(0, 1 - m.jargonNoGloss.length / 8),
      L3: m.overwhelm ? Math.max(0, 1 - (m.firstPaintInteractive - OVERWHELM_BUDGET) / OVERWHELM_BUDGET) : 1,
      L4,                                  // null = N/A
      L5: m.backAffordance ? 1 : 0,
      L6: (m.deadLinks + m.unlabeledInputs) === 0 ? 1 : Math.max(0, 1 - (m.deadLinks + m.unlabeledInputs) / 10),
    };
    card.lens = lens;
    // Plain (unweighted) intuition over the APPLICABLE lenses
    const applic = Object.entries(lens).filter(([, v]) => v != null);
    card.intuition_pct = Math.round(100 * applic.reduce((a, [, v]) => a + v, 0) / applic.length);

    // ── per-persona weighted intuition (renormalize weights over applicable lenses) ──
    card.persona_pct = {};
    for (const [pk, p] of Object.entries(PERSONAS)) {
      let num = 0, den = 0;
      for (const [lk, v] of applic) { const w = p.w[lk] ?? 0; num += w * v; den += w; }
      card.persona_pct[pk] = den > 0 ? Math.round(100 * num / den) : null;
    }
  } catch (e) {
    card.error = String(e).slice(0, 160);
  } finally { await page.close(); }
  return card;
}

function argv(flag, def) { const i = process.argv.indexOf(flag); return i > -1 ? process.argv[i+1] : def; }

const DEFAULT_PAGES = ['analytics.html','asset-hub.html','alert-hub.html','hive.html','logbook.html','project-manager.html'];

// ── --inspect <slug> [--role r] : list the FIRST-PAINT interactive elements (tag/label/top)
// so an overwhelm-reduction (Y2 Home-Stack) is evidence-based, not a blind reorg. No report write.
async function inspectFirstPaint(slug, role) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: VW, height: VH }, deviceScaleFactor: 1 });
  const si = await signIn(context, role);
  if (!si.ok) { console.error(`sign-in failed (${role}):`, si); await browser.close(); process.exit(2); }
  const page = await context.newPage();
  await page.setViewportSize({ width: VW, height: VH });
  await page.goto(`${BASE}/workhive/${slug}`, { waitUntil: 'domcontentloaded' });
  await sleep(2800);
  const items = await page.evaluate(() => {
    const vh = window.innerHeight, vw = window.innerWidth;
    const isVisible = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width>0 && r.height>0 && s.display!=='none' && s.visibility!=='hidden' && Number(s.opacity)>0.05; };
    const inFP = (el) => { const r = el.getBoundingClientRect(); return r.top < vh && r.bottom > 0 && r.left < vw && r.right > 0; };
    const isChrome = (el) => !!el.closest('[id^="wh-"], .back-btn, .wf-back, .wf-crumb, #wh-wayfinding');
    return [...document.querySelectorAll('a,button,input,select,textarea,[role="button"],[role="tab"],[onclick]')]
      .filter(e => isVisible(e) && inFP(e) && !isChrome(e))
      .map(e => {
        const r = e.getBoundingClientRect();
        const label = (e.getAttribute('aria-label') || e.textContent || e.getAttribute('title') || e.getAttribute('placeholder') || '').trim().replace(/\s+/g,' ').slice(0,42);
        // nearest ancestor with an id → which board section it lives in
        let sec = ''; let n = e;
        for (let i=0;i<8 && n;i++){ if (n.id){ sec = n.id; break; } n = n.parentElement; }
        return { tag: e.tagName.toLowerCase(), top: Math.round(r.top), label, section: sec };
      })
      .sort((a,b) => a.top - b.top);
  });
  console.log(`\n[inspect] ${slug} (role=${role}) — ${items.length} first-paint interactive elements @${VW}x${VH}:`);
  // group by section for the reorg plan
  const bySec = {};
  for (const it of items) (bySec[it.section || '(no-id ancestor)'] = bySec[it.section || '(no-id ancestor)'] || []).push(it);
  for (const [sec, list] of Object.entries(bySec).sort((a,b)=>b[1].length-a[1].length)) {
    console.log(`  ${String(list.length).padStart(2)}× section#${sec}  [top ${Math.min(...list.map(i=>i.top))}–${Math.max(...list.map(i=>i.top))}px]`);
    for (const it of list.slice(0,6)) console.log(`        ${it.tag.padEnd(7)} @${String(it.top).padStart(4)}  "${it.label}"`);
    if (list.length > 6) console.log(`        … +${list.length-6} more`);
  }
  await browser.close();
  process.exit(0);
}

(async () => {
  const inspectSlug = argv('--inspect', '');
  if (inspectSlug) { await inspectFirstPaint(inspectSlug, argv('--role', 'supervisor')); return; }
  const all   = process.argv.includes('--all');
  const pages = argv('--pages', '') ? argv('--pages','').split(',') : (all ? canonicalPages() : DEFAULT_PAGES);
  const roles = (argv('--roles', 'worker,supervisor')).split(',');   // the 2 real auth sessions
  const browser = await chromium.launch({ headless: true });

  console.log(`\nArc Y — Intuition Gradient Harness  (${VW}px CSS · ${pages.length} pages × ${roles.length} auth-sessions)`);
  console.log('='.repeat(72));

  // measure each page under each REAL auth session
  const byKey = {};   // `${slug}` -> { worker:card, supervisor:card }
  for (const role of roles) {
    const context = await browser.newContext({ viewport: { width: VW, height: VH }, deviceScaleFactor: 1 });
    const si = await signIn(context, role);
    if (!si.ok) { console.error(`sign-in failed (${role}):`, si); await context.close(); continue; }
    console.log(`\n[auth: ${role}]`);
    for (const slug of pages) {
      const c = await scorePage(context, slug, role);
      (byKey[slug] = byKey[slug] || {})[role] = c;
      console.log(`  ${String(c.intuition_pct ?? '--').padStart(3)}%  ${slug.padEnd(26)} ` +
        (c.error ? 'ERR '+c.error
                 : `fp:${String(c.firstPaintInteractive).padStart(2)}${c.overwhelm?'⚠':' '} back:${c.backAffordance?'Y':'N'} jargon:${c.jargonNoGloss.length} dead:${c.deadLinks} unlbl:${c.unlabeledInputs}${c.l4?` l4:${c.l4.shown}/${c.l4.truth}`:''}`));
    }
    await context.close();
  }
  await browser.close();

  // fold the per-role cards into one per-page record carrying the persona gradient.
  // Each persona reads through ITS auth session: worker→worker card; engineer/supervisor→supervisor card.
  const cards = [];
  const corpus = [];
  for (const slug of pages) {
    const w = byKey[slug]?.worker, s = byKey[slug]?.supervisor;
    const src = { worker: w, engineer: s, supervisor: s };
    const persona_pct = {};
    for (const pk of Object.keys(PERSONAS)) persona_pct[pk] = src[pk]?.persona_pct?.[pk] ?? null;
    const vals = Object.values(persona_pct).filter(v => v != null);
    const gradient = vals.length ? Math.max(...vals) - Math.min(...vals) : null;   // the spread = the gradient
    const novice_floor = persona_pct.worker;                                       // the gate bar
    cards.push({
      page: slug,
      persona_pct, gradient, novice_floor,
      worker: w && !w.error ? { intuition_pct: w.intuition_pct, lens: w.lens, firstPaintInteractive: w.firstPaintInteractive, overwhelm: w.overwhelm, backAffordance: w.backAffordance, jargonNoGloss: w.jargonNoGloss, deadLinks: w.deadLinks, unlabeledInputs: w.unlabeledInputs, l4: w.l4 } : { error: w?.error || 'no worker run' },
      supervisor: s && !s.error ? { intuition_pct: s.intuition_pct, lens: s.lens, firstPaintInteractive: s.firstPaintInteractive, overwhelm: s.overwhelm, backAffordance: s.backAffordance, jargonNoGloss: s.jargonNoGloss, deadLinks: s.deadLinks, unlabeledInputs: s.unlabeledInputs, l4: s.l4 } : { error: s?.error || 'no supervisor run' },
    });
    // L2 corpus row — visible labels per page (union across sessions), for the semantic critic
    const labels = [...new Set([...(w?.labels||[]), ...(s?.labels||[])])];
    if (labels.length) corpus.push({ page: slug, labels });
  }

  const scored = cards.filter(c => c.novice_floor != null);
  const avgNovice = scored.length ? Math.round(scored.reduce((a,c)=>a+c.novice_floor,0)/scored.length) : 0;
  const avgGrad   = scored.length ? Math.round(scored.reduce((a,c)=>a+(c.gradient||0),0)/scored.length) : 0;
  const report = {
    arc: 'Y', harness: 'intuition_gradient', vw: VW, overwhelm_budget: OVERWHELM_BUDGET,
    personas: Object.fromEntries(Object.entries(PERSONAS).map(([k,v]) => [k, { authRole: v.authRole, weights: v.w }])),
    pages_scored: scored.length, pages_total: pages.length,
    avg_novice_floor_pct: avgNovice, avg_gradient_pts: avgGrad,
    cards,
  };
  fs.writeFileSync(path.join(ROOT, 'intuition_gradient_report.json'), JSON.stringify(report, null, 2));
  fs.writeFileSync(path.join(ROOT, 'intuition_gradient_corpus.json'), JSON.stringify({ arc:'Y', source:'intuition_gradient_harness', pages: corpus.length, corpus }, null, 2));

  console.log(`\n  GRADIENT SUMMARY  ·  avg novice-floor: ${avgNovice}%  ·  avg persona spread: ${avgGrad} pts  ·  ${scored.length}/${pages.length} pages`);
  console.log('  → intuition_gradient_report.json  +  intuition_gradient_corpus.json');
  // worst novice surfaces (the backlog the fix-phases attack first)
  const worst = [...scored].sort((a,b)=>a.novice_floor-b.novice_floor).slice(0,10);
  console.log('\n  WORST NOVICE-FLOOR (Y0.5 backlog head):');
  for (const c of worst) console.log(`    ${String(c.novice_floor).padStart(3)}%  ${c.page.padEnd(26)} grad:${c.gradient}pts  W/E/S=${c.persona_pct.worker}/${c.persona_pct.engineer}/${c.persona_pct.supervisor}`);
  process.exit(0);
})();
