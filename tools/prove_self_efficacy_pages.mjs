// prove_self_efficacy_pages.mjs - T2 SE (2026-10-27): the 27 production pages, met by a person who has never used them.
//
// For each page the row's own cast is made fresh: a new account, added to the row's hive with the persona's role
// (supervisor for the supervising casts, worker otherwise), never on the page before - removed after the walk. The
// page's primary job is the journey drive tools/live_page_journeys.registry.mjs already holds for it, run as that
// person. One walk per page and viewport answers the four sources of self-efficacy:
//   vicarious   at first paint, before any action: what a finished one looks like is on the screen - the hive's records
//               (a peer's entry, part, plan, post) or a sample / example / template the page offers
//   mastery     the drive completes the job, on the page, with the interactions counted
//   verbal      the completed act is told in words: a sentence that appeared in the page's status / toast regions
//   emotional   acting is safe: every destructive control the page carries is in the roster with its confirm or undo
//               (destructive_control_registry; recovery-path proves them live) and deletes stay recoverable (SL D3)
//
//   node tools/prove_self_efficacy_pages.mjs [--page logbook.html]
// Report: self_efficacy_pages_report.json, read-merged per page.
import { removeWalkAccounts } from './lib/walk_accounts.mjs';
import { ALL_ROWS_DRAWN } from './lib/long_list_text.mjs';
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { JOURNEYS } from './live_page_journeys.registry.mjs';
import { makeHelpers } from './live_page_journeys.mjs';
import { SEEDER } from './prover_harness.mjs';
import { NEXT_RE } from './lib/what_happens_next_vocab.mjs';

// ★A PEER'S RECORD IS A ROW OF THE HIVE, NOT A CARD ON THE PAGE. The first walk counted logbook's own wizard card
// ("Log a Repair 1 2 3 STEP 1 ...") as "a record of the hive". The record is now taken from the DATABASE - the newest
// row of the page's own kind in the member's hive - and the page must show its text at first paint. Pages whose
// first screen is not a list of the hive's rows are judged by the example they offer instead.
const PEER = {
  'logbook.html': (h) => `select problem from logbook where hive_id = '${h}' and problem is not null and deleted_at is null order by created_at desc limit 20`,
  'inventory.html': (h) => `select part_name from inventory_items where hive_id = '${h}' and status = 'approved' and deleted_at is null order by created_at desc limit 20`,
  'pm-scheduler.html': (h) => `select asset_name from pm_assets where hive_id = '${h}' and deleted_at is null order by created_at desc limit 20`,
  'asset-hub.html': (h) => `select name from asset_nodes where hive_id = '${h}' and status = 'approved' and deleted_at is null order by created_at desc limit 20`,
  'community.html': (h) => `select left(content, 40) from community_posts where hive_id = '${h}' and deleted_at is null order by created_at desc limit 20`,
  'marketplace.html': () => `select title from marketplace_listings where status = 'published' order by created_at desc limit 20`,
  'project-manager.html': (h) => `select name from projects where hive_id = '${h}' and deleted_at is null order by created_at desc limit 20`,
  // the plan's open work: the hive's newest PM task, offered as "+ Add to my day"
  'dayplanner.html': (h) => `select item_text from pm_scope_items where hive_id = '${h}' order by created_at desc limit 20`,
  // "Or choose one of your hive's recent projects": the hive's projects, each a finished report away
  'project-report.html': (h) => `select name from projects where hive_id = '${h}' and deleted_at is null order by created_at desc limit 20`,
  // a seller's profile is opened from a listing (?worker=): that seller's live listing is the record a buyer sees
  'marketplace-seller-profile.html': () => `select title from marketplace_listings where seller_name = 'Isidro Suarez' and status = 'published' order by created_at desc limit 20`,
};
const PAGE_QUERY = { 'marketplace-seller-profile.html': '?worker=Isidro%20Suarez' };
// pages whose first screen IS the hive's live state (the alert feed, this shift's plan, the home's "today at a glance"):
// what a finished one looks like is that state, so a non-zero figure of it on screen is the evidence
const HIVE_VIEW = new Set(['alert-hub.html', 'shift-brain.html', 'index.html']);
// pages whose first screen is a TEMPLATE of the finished thing: every badge named with what earns it; every calculator
// named with what it computes
const TEMPLATE = {
  'achievements.html': () => ((document.querySelector('main') || document.body).innerText.match(/XP to Lv \d/g) || []).length >= 3,
  'engineering-design.html': () => [...document.querySelectorAll('.calc-card')].filter((c) => c.checkVisibility() && c.innerText.trim().length > 20).length >= 10,
};

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const VIEWPORTS = { 'phone-390': { width: 390, height: 844 }, 'desktop-1280': { width: 1280, height: 900 } };
const REPORT = process.argv.includes('--paint-only') ? 'self_efficacy_pages_paint.json' : 'self_efficacy_pages_report.json';
const psql = (sql) => execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim();

// the journey that IS each page's primary job for the row's cast
const PRIMARY = {
  'achievements.html': 'ACHK2', 'alert-hub.html': 'AL2', 'analytics-report.html': 'AR1', 'analytics.html': 'AN2',
  'asset-hub.html': 'AH2', 'assistant.html': 'AK1', 'community.html': 'CM1', 'dayplanner.html': 'DAY1',
  'engineering-design.html': 'ED1', 'index.html': 'HM4', 'integrations.html': 'IN1', 'inventory.html': 'INV1',
  'logbook.html': 'LOG1', 'marketplace-seller-profile.html': 'SP1', 'marketplace-seller.html': 'MS3',
  'marketplace.html': 'MK3', 'ph-intelligence.html': 'PI1', 'plant-connections.html': 'PC1', 'pm-scheduler.html': 'PM3',
  'project-manager.html': 'PMK1', 'project-report.html': 'PRK1', 'public-feed.html': 'PF1', 'report-sender.html': 'RS2',
  'resume.html': 'RESK3', 'shift-brain.html': 'SB1', 'skillmatrix.html': 'SKK2',
};
const SUPERVISING = /supervisor|owner|machine-client|oversight/;
// skillmatrix's first act for someone with no matrix is CHOOSING A PRIMARY DISCIPLINE ("No skill matrix yet. Pick your
// primary discipline to start one"); SKK2 raises a target on a matrix a first-timer does not have
const FIRST_MATRIX = {
  id: 'SKFIRST', title: 'A worker with no skill matrix picks a primary discipline and starts one',
  drive: async (page, h) => {
    await h.goto('skillmatrix.html');
    await h.waitFor('#primary-picker .primary-option', 10000);
    const picked = await h.evalIn(() => { const b = document.querySelector('#primary-picker .primary-option'); if (!b) return null; b.click(); return (b.innerText || '').trim().slice(0, 40); });
    await page.waitForTimeout(400);
    await h.evalIn(() => { const s = document.getElementById('onboard-save-btn'); if (s && !s.disabled) s.click(); });
    await page.waitForTimeout(2500);
    const n = Number(psql(`select count(*) from skill_profiles where worker_name = '${h.name.replace(/'/g, "''")}'`));
    return { J: n >= 1, X: n >= 1, evidence: { picked, profiles: n } };
  },
};
// alert-hub's AL2 filters by Risk, and a chip for a kind with no alerts is not drawn - a fresh worker's feed had none.
// A first-timer filters by the first kind the feed actually holds.
const FIRST_FILTER = {
  id: 'ALFIRST', title: 'A worker filters the alert feed by the first kind it holds',
  drive: async (page, h) => {
    await h.goto('alert-hub.html');
    await h.waitFor('#filters .chip', 10000);
    const kind = await h.evalIn(() => { const c = document.querySelector("#filters .chip:not([data-kind='all'])"); if (!c) return null; c.click(); return c.getAttribute('data-kind'); });
    await page.waitForTimeout(700);
    const active = kind ? await h.exists(`#filters .chip[data-kind='${kind}'].active`) : false;
    const only = kind ? await h.evalIn((k) => [...document.querySelectorAll('#feed .alert')].every((r) => r.className.includes('kind-' + k)), kind) : false;
    return { R: true, J: !!active, C: !!only, evidence: { kind, active, only } };
  },
};
const PAINT_ONLY = process.argv.includes('--paint-only');
// the journeys that WRITE (their act must be confirmed in words); every other primary act is a read, completed on the spot
const WRITES = new Set(['CM1', 'DAY1', 'INV1', 'LOG1', 'MS3', 'MK3', 'PM3', 'PMK1', 'RS2', 'RESK3', 'IN1', 'ED1', 'JOIN', 'SKFIRST']);
// the page's sentences: a confirmation is not always a toast (hive.html's welcome view says "Your records are now visible to
// your team"), so a write's confirmation is any sentence that APPEARED after the act, in a status region or on the page
// (the page's body less its chrome: analytics-report renders the finished report in #ar-print-wrapper, a SIBLING of <main>)
const LINES = () => [...document.body.children]
  .filter((e) => !/^(HEADER|NAV|FOOTER|SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(e.tagName))
  .map((e) => e.innerText || '').join('\n')
  .split(/\n+|(?<=[.!?])\s+/).map((t) => t.replace(/\s+/g, ' ').trim()).filter((t) => t.length > 8);
// hive.html's first act for a worker who has never used it is JOINING (the hive journeys are all a supervisor's): the
// fresh account is not added to the hive up front, it types the code a supervisor would hand it and presses Join Hive
const JOIN = {
  id: 'JOIN', title: 'A worker joins the hive with the code a supervisor handed over',
  drive: async (page, h) => {
    await h.goto('hive.html');
    const code = psql(`select invite_code from hives where id = '${h.joinHive}'`);
    await page.click('#btn-go-join');
    await page.fill('#join-code-input', code);
    await page.click('#btn-submit-join');
    await page.waitForTimeout(5000);
    const n = Number(psql(`select count(*) from hive_members where hive_id = '${h.joinHive}' and auth_uid = '${h.uid}' and status = 'active'`));
    return { J: n === 1, X: n === 1, evidence: { joined: n } };
  },
};

const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
const rows = reg.trajectories.filter((r) => r.wave === 'SE' && r.se && !/^(tools|learn)\//.test(r.se.page));
const cast = {};
for (const r of rows) cast[r.se.page] ||= { persona: r.persona, hiveName: (r.journey || {}).vertical, primary: r.se.primary };
// a page whose primary act is READING (rpc / edge / cta): its finished product is the hive's own figures on the screen
const READS = new Set(['rpc', 'edge', 'cta']);
const pages = Object.keys(cast).filter((p) => !ONLY || p === ONLY).sort();
const roster = JSON.parse(readFileSync('substrate/reference/destructive_control_registry.json', 'utf8'));
// the roster is { file: [{ line, message_head }] } - every rostered destructive act has its confirm sentence; a split-out
// script carries its page's controls (engineering-design.js)
const controlsOn = (page) => [...(roster.controls[page] || []), ...(roster.controls[page.replace(/\.html$/, '.js')] || [])];

// what the page TELLS during the walk: text added to its status, toast and live regions
const TOLD = () => {
  window.__whTold = [];
  const SEL = '[role=status], [role=alert], [aria-live], #toast, .toast, [class*="toast"]';
  const seen = (t) => { t = (t || '').replace(/\s+/g, ' ').trim(); if (t && !window.__whTold.includes(t)) window.__whTold.push(t.slice(0, 240)); };
  new MutationObserver((ms) => { for (const m of ms) { const el = m.target.nodeType === 1 ? m.target : m.target.parentElement; const box = el && el.closest(SEL); if (box) seen(box.innerText); } })
    .observe(document, { subtree: true, childList: true, characterData: true });
  // the person's acts are counted in Node (the __whAct binding): a count on window died with every navigation, so HM4 -
  // home, a tool, sign out, all by click - read "0 interactions". Trusted or not: several drives act through the page's
  // own controls in script (CM1 posts with b.click()), and a trusted-only count read that three-act post as 0.
  for (const ev of ['click', 'input', 'change']) document.addEventListener(ev, () => { if (window.__whAct) window.__whAct(); }, true);
};
const FIRST_PAINT = () => {
  const vis = (e) => e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
  const main = document.querySelector('main') || document.body;
  const recs = [...main.querySelectorAll('[data-id], [data-entry-id], .entry-card, .card, tbody tr, ul > li, ol > li, .item, article')]
    .filter((e) => vis(e) && (e.innerText || '').trim().length > 12 && !e.closest('nav, header, footer'));
  // an element's OWN text (its text nodes): a heading like "TRY ASKING" sits beside an icon, so a leaf-only read missed it
  const own = (e) => [...e.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join(' ');
  // (dayplanner's verdict sentence is a <small>: any element that holds prose counts, not a fixed handful of tags)
  // An example is a FINISHED thing someone like the visitor made. A placeholder ("ABC123", "e.g. Juan Dela Cruz") is the
  // shape of one input, and "example" inside an address (seed.contact6@example.test) is a domain: hive, resume and
  // report-sender passed on exactly those (2026-10-27), so neither counts.
  const exEl = [...main.querySelectorAll('p, div, span, small, em, label, button, h2, h3, h4, strong, b, li')]
    .filter((e) => vis(e))
    .find((e) => /\b(for example|for instance|example|sample|template|try asking|(looks|reads) like this)\b/i
      .test((own(e) || '').replace(/[\w.+-]+@[\w-]+(\.[\w-]+)+/g, '')));
  // a bold lead-in ("A finished entry reads like this:") or a heading ("TRY ASKING") is the label; the example is what
  // it introduces - the line, or the heading's block (the assistant's three starter questions)
  const example = exEl ? ((/^(STRONG|B|EM|H2|H3|H4)$/.test(exEl.tagName) && exEl.parentElement ? exEl.parentElement : exEl).innerText || '')
    .replace(/\s+/g, ' ').trim() : null;
  // the hive's own figures on screen (a read page's finished product): visible leaf texts that carry a non-zero number
  const figures = [...main.querySelectorAll('*')].filter((e) => !e.children.length && vis(e) && !e.closest('nav, header, footer'))
    .map((e) => (e.innerText || '').trim()).filter((t) => t.length < 40 && /[1-9]/.test(t)).length;
  return { records: recs.length, sample: recs[0] ? recs[0].innerText.replace(/\s+/g, ' ').trim().slice(0, 90) : null,
           example: example ? example.slice(0, 200) : null, figures,
           text: (main.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 300) };
};

async function freshMember(ctx, hiveName, role) {
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/index.html`, { waitUntil: 'domcontentloaded' });
  await p.waitForFunction(() => !!window._whSupabaseClient || (typeof window.getDb === 'function' && !!window.SUPABASE_KEY), { timeout: 20000 });
  const username = `seprobe_${Date.now().toString(36)}`;
  const name = `SE First-timer ${username.slice(-5)}`;
  const r = await p.evaluate(async ({ username, name }) => {
    const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
    const { data, error } = await db.auth.signUp({ email: username + '@auth.workhiveph.com', password: 'Probe!' + username });
    if (error || !data.session) return { ok: false, err: error ? error.message : 'no session' };
    const { error: pe } = await db.from('worker_profiles').insert({ auth_uid: data.user.id, username, display_name: name });
    if (pe) return { ok: false, err: 'profile: ' + pe.message };
    localStorage.setItem('wh_last_worker', name);
    return { ok: true, uid: data.user.id };
  }, { username, name });
  if (!r.ok) { await p.close(); throw new Error('SIGN-UP FAILED: ' + r.err); }
  let hive = null;
  if (hiveName) {
    hive = psql(`select id from hives where name = '${hiveName.replace(/'/g, "''")}' limit 1`);
    psql(`insert into hive_members (hive_id, auth_uid, worker_name, role, status) values ('${hive}', '${r.uid}', '${name}', '${role}', 'active')`);
    await p.evaluate(({ hive, role, hiveName }) => { localStorage.setItem('wh_active_hive_id', hive); localStorage.setItem('wh_hive_role', role); localStorage.setItem('wh_hive_name', hiveName); }, { hive, role, hiveName });
  }
  await p.close();
  return { username, uid: r.uid, hive, name };
}

const prev = existsSync(REPORT) ? JSON.parse(readFileSync(REPORT, 'utf8')) : {};
const made = [];
const b = await chromium.launch();
let bad = 0;
for (const page of pages) {
  const j = page === 'hive.html' ? JOIN : page === 'skillmatrix.html' ? FIRST_MATRIX : page === 'alert-hub.html' ? FIRST_FILTER
    : JOURNEYS.find((x) => x.id === PRIMARY[page]);
  const c = cast[page];
  const role = SUPERVISING.test(c.persona) ? 'supervisor' : 'worker';
  const anon = c.persona === 'anon';
  for (const [vp, size] of Object.entries(VIEWPORTS)) {
    const ctx = await b.newContext({ viewport: size, serviceWorkers: 'block' });
    await ctx.route('**/rest/v1/analytics_events*', (r) => (r.request().method() === 'POST' ? r.fulfill({ status: 201, body: '' }) : r.continue()));
    await ctx.addInitScript(TOLD);
    await ctx.addInitScript(ALL_ROWS_DRAWN);   // SL LB3: a long list draws every row, so a page's text is the whole page
    let acted = 0;
    await ctx.exposeBinding('__whAct', () => { acted++; });
    let who = null, v;
    try {
      if (!j) throw new Error(`no primary journey mapped for ${page}`);
      const joining = j.id === 'JOIN';
      if (!anon) { who = await freshMember(ctx, joining ? null : c.hiveName, role); made.push(who.username); }
      const p = await ctx.newPage();
      await p.goto(`${SEEDER}/workhive/${page}${PAGE_QUERY[page] || ''}`, { waitUntil: 'load', timeout: 45000 }).catch(() => {});
      await p.waitForTimeout(3500);
      const paint = await p.evaluate(FIRST_PAINT).catch(() => ({ records: 0 }));
      if (TEMPLATE[page]) paint.template = await p.evaluate(TEMPLATE[page]).catch(() => false);
      const before = new Set(await p.evaluate(LINES).catch(() => []));
      // the hive's own newest record of this page's kind, read from the database, and whether it is on the screen
      if (PEER[page]) {
        // ANY of the hive's recent records on screen: a phone list draws only the rows in view (whRenderRows), so the single
        // newest part was off screen at 390 while the list plainly showed the hive's parts (2026-10-27)
        const wants = psql(PEER[page](who && who.hive ? who.hive : '')).split(/\r?\n/).map((t) => t.replace(/\s+/g, ' ').trim()).filter(Boolean);
        const hit = wants.length ? await p.evaluate((ws) => { const b = document.body.innerText.replace(/\s+/g, ' '); return ws.find((w) => b.includes(w.slice(0, 40))) || null; }, wants) : null;
        paint.peer = { record: (hit || wants[0] || '').slice(0, 60), shown: !!hit, candidates: wants.length };
      }
      if (PAINT_ONLY) {   // a survey of first paint: what a first-timer sees before acting, no drive run
        paint.fullText = await p.evaluate(() => ((document.querySelector('main') || document.body).innerText || '').replace(/\s+/g, ' ').trim().slice(0, 900)).catch(() => '');
        throw Object.assign(new Error('paint-only'), { paint });
      }
      const h = makeHelpers(p, who ? who.hive : null, who ? who.uid : null);
      h.name = who ? who.name : null;   // the drives check rows under the name of whoever ran them (registry: h.name || seed)
      if (joining) h.joinHive = psql(`select id from hives where name = '${c.hiveName.replace(/'/g, "''")}' limit 1`);
      acted = 0;   // the drive's acts only - not the first-paint reads above
      const out = await Promise.race([j.drive(p, h), new Promise((_, rej) => setTimeout(() => rej(new Error('drive ran past 150 s')), 150000))]);
      await p.waitForTimeout(1200);
      const told = await p.evaluate(() => window.__whTold || []).catch(() => []);
      const acts = acted;
      const onPage = new URL(p.url()).pathname.endsWith(page) || page === 'index.html';
      const done = out.J !== false && (out.J === true || out.X === true || out.R === true);
      // the SAME oracle as prove_what_happens_next: the told sentence must name where the act lands or what it enables -
      // "Entry saved." confirms an act and says nothing of its effect, and a validation prompt is not a confirmation
      const after = await p.evaluate(LINES).catch(() => []);
      const writes = WRITES.has(j.id);
      // a write: what was told or newly appeared; a read: the page after the act names what the person can do next
      const pool = writes ? [...told, ...after.filter((t) => !before.has(t))] : [...told, ...after];
      const sentence = pool.find((t) => NEXT_RE.test(t) && !/^(loading|checking|saving|please )/i.test(t)) || null;
      const ctl = controlsOn(page);
      v = {
        persona: c.persona, role: anon ? 'anon' : role, hive: c.hiveName, journey: j.id, title: j.title,
        vicarious: { pass: !!paint.example || !!paint.template || (paint.peer ? paint.peer.shown
                       : (READS.has(c.primary) && paint.figures >= 3) || (HIVE_VIEW.has(page) && paint.figures >= 1)),
                     reads: READS.has(c.primary), hiveView: HIVE_VIEW.has(page), ...paint },
        mastery: { pass: done && onPage, done, onPage, interactions: acts, verdict: { R: out.R, J: out.J, T: out.T, X: out.X } },
        verbal: { pass: !!sentence, sentence, act: writes ? 'write' : 'read', told: told.slice(0, 4),
                  appeared: writes ? after.filter((t) => !before.has(t)).slice(0, 4) : undefined },
        emotional: { pass: ctl.every((x) => (x.message_head || '').trim().length >= 12),
                     destructive: ctl.length, confirms: ctl.slice(0, 3).map((x) => (x.message_head || '').slice(0, 80)) },
      };
      await p.close();
    } catch (e) { v = e.paint ? { persona: c.persona, role: anon ? 'anon' : role, hive: c.hiveName, paint: e.paint } : { error: String(e).slice(0, 220) }; }
    await ctx.close();
    const ok = v && !v.error && (v.paint ? true : ['vicarious', 'mastery', 'verbal', 'emotional'].every((k) => v[k].pass));
    if (!ok) bad++;
    prev[page] = { ...(prev[page] || {}), [vp]: { ...v, at: new Date().toISOString() } };
    const flags = v.error ? v.error : v.paint ? `paint: ${v.paint.figures} figures, example=${!!v.paint.example}`
      : ['vicarious', 'mastery', 'verbal', 'emotional'].map((k) => `${k}:${v[k].pass ? 'ok' : 'NO'}`).join(' ');
    console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${vp.padEnd(12)} ${page.padEnd(32)} ${flags}`);
    writeFileSync(REPORT, JSON.stringify(prev, null, 1) + '\n');
  }
}
await b.close();
if (made.length) {
  // the account leaves with everything its journeys wrote (tools/lib/walk_accounts.mjs)
  try { removeWalkAccounts(made); console.log(`  removed ${made.length} first-timer account(s) and what they wrote`); }
  catch (e) { console.log(`  WARN cleanup: ${String(e).slice(0, 160)} (accounts: ${made.join(', ')})`); }
}
console.log(`${bad ? 'FAIL' : 'PASS'} self-efficacy pages - ${pages.length * 2 - bad}/${pages.length * 2} page-viewports (report: ${REPORT})`);
process.exit(bad ? 1 : 0);
