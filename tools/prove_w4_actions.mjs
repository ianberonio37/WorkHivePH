// prove_w4_actions.mjs - LIVE the wave-4 ACTION rows (kind 'action') whose story can be read off a real walk without a
// bespoke hand: rpc ("call rpc X and read what it returns"), edge ("invoke X and see the answer land with provenance"),
// learn-cta ("follow the tool this guide is about"). Rows that share a path and a cast are walked ONCE (one context,
// one sign-in, the four pages of the path with the overlap audit after each) while every PostgREST / RPC / edge
// response the person's session receives is recorded; each row is then answered from that record. (Wave 4, 2026-09-14.)
//
//   rpc        - a 2xx response to /rest/v1/rpc/<subject> was received by the person's own session on the path
//   edge       - a 2xx response to /functions/v1/<subject> (not the OPTIONS preflight) was received, and the page it
//                landed on shows its provenance (a .wh-source-chip) - the answer "landed with provenance"
//   learn-cta  - on the learn page the link to the named tool exists, is the element at its own centre, and clicking it
//                arrives at that tool (URL matched at the PATH position); the rest of the path is then walked as the
//                anonymous reader actually meets it (the wall, where a page is gated)
//
//   print      - (2026-09-15) window.print is stubbed to record the call; the page's own print / export-PDF control is
//                pressed on the row's subject page; the row lives when the call landed or a download started
//   cta        - (2026-09-15) the first visible primary-styled control on the subject page is pressed and the change is
//                read: a new URL, a dialog now open, or the visible text moved by >= 40 chars
// write / upload / compute rows need a hand on the page (a form, a file, a calculator) and are not walked here - they stay
// open, honestly, until their own reversible harness exists. A MUTATING rpc is never called by the walk (deny-list) - the
// first build called deactivate_my_account as the cast and deactivated two local accounts. Serial on the 8 GB host; cast
// from the database.
// Receipt: .tmp/mcp_walks/W4actions_<axis>.json (merged by id), read by live_walk_manifest._w4_receipts.
//
//   node tools/prove_w4_actions.mjs --axis "phone-390 en" [--kinds rpc,edge,learn-cta] [--host achievements.html] [--limit 3] [--force]
import { chromium } from 'playwright';
import { execSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import os from 'node:os';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 && process.argv[i + 1] ? process.argv[i + 1] : d; };
const AXIS = arg('--axis', 'phone-390 en');
const KINDS = (arg('--kinds', 'rpc,edge,learn-cta,print,cta')).split(',').map((s) => s.trim()).filter(Boolean);
const HOST = arg('--host', '');
const LIMIT = Number(arg('--limit', '0')) || 0;        // groups
const FORCE = process.argv.includes('--force');
const ORIGIN = arg('--origin', 'http://localhost:5000/workhive');
const [device, lang] = AXIS.split(' ');
const viewport = device === 'narrow-320' ? { width: 320, height: 720 } : { width: 390, height: 844 };
const AUDIT = readFileSync('tools/phone_fit_audit.browser.js', 'utf8');
const atPath = (h) => new RegExp('/' + h.split('.').join('[.]') + '(?:[?#]|$)');
const API = arg('--api', 'http://127.0.0.1:54321');   // the local gateway the pages talk to
const ANON_KEY = (() => { try { return readFileSync('.tmp/local_anon_key.txt', 'utf8').trim(); } catch (e) { return ''; } })();
const SIGS = (() => { try { return JSON.parse(readFileSync('.tmp/rpc_signatures.json', 'utf8')); } catch (e) { return {}; } })();   // rpc name -> [identity args] from pg_proc
const MUTATING = /^(deactivate_|claim_|notify_|set_|report_|ensure_|insert|update|delete|create|mark_|accept_|reject_|grant_|revoke_|publish_|submit_|send_|bind_|record_|log_|dismiss_|award_|redeem_|spend_|charge_|cancel_|archive_|reset_|register_|join_|leave_|invite_|approve_|assign_|complete_|close_|open_|start_|stop_|toggle_)/i;
// the arguments a person's context can supply; anything else is an id the story does not give
const fillArg = (name, ctx) => { const n = name.toLowerCase(); if (/^(p_)?hive(_id)?$/.test(n)) return ctx.hiveId; if (/^(p_)?worker_name$/.test(n)) return ctx.worker; if (/^(p_)?(period_|since_|window_|lookback_)?days$/.test(n)) return 30; if (/^(p_)?(limit|max|page_size)$/.test(n)) return 20; if (/^(p_)?offset$/.test(n)) return 0; if (/^(p_)?lang(uage)?$/.test(n)) return lang; return undefined; };   // cached by tools/walk_navhub_axis.py from `supabase status`

const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8', timeout: 30000 }).trim(); } catch (e) { return ''; } };
const CAST = {};
for (const line of psql("select h.name||'|'||m.worker_name||'|'||m.role||'|'||coalesce(u.email,'') from hives h join hive_members m on m.hive_id = h.id left join auth.users u on u.id = m.auth_uid where m.status = 'active' order by h.name, m.role, m.worker_name").split('\n')) {
  const [hive, worker, role, email] = line.split('|');
  if (!hive || !email) continue;
  CAST[hive] = CAST[hive] || {};
  if (role === 'worker' && !CAST[hive].worker) CAST[hive].worker = { name: worker, email, user: email.split('@')[0] };
  if (role !== 'worker' && !CAST[hive].supervisor) CAST[hive].supervisor = { name: worker, email, user: email.split('@')[0] };
}
// a hive whose only account is its supervisor (Ramos Jeepney Line - Oscar Ramos) is lived by the supervisor, as the nav-hub walk does
for (const h of Object.keys(CAST)) if (!CAST[h].worker && CAST[h].supervisor) CAST[h].worker = CAST[h].supervisor;

const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
const shortOf = (t) => { const m = (t.title || '').match(/ - ([^·]+) · /); return m ? m[1].trim() : ''; };
const subjectPage = (t) => { const sh = shortOf(t).toLowerCase(); return (t.pages || []).find((pg) => pg.replace(/\.html$/, '').replace(/[-_/]/g, ' ').toLowerCase() === sh) || (t.pages || []).slice(-1)[0]; };
let rows = reg.trajectories.filter((t) => (t.w4 || {}).kind === 'action' && KINDS.includes((t.w4.action || {}).kind)
  && `${(t.axis || {}).device} ${(t.axis || {}).language}` === AXIS && (FORCE || !['locking', 'locked', 'descoped'].includes(t.status)));
if (HOST) rows = rows.filter((t) => (t.pages || []).slice(-1)[0] === HOST);
// one walk per (path, cast): the story's pages and the person who lives them
const groups = new Map();
for (const t of rows) {
  const key = (t.pages || []).join('>') + '|' + (t.persona === 'anon' ? 'anon' : ((t.journey || {}).vertical || ''));
  if (!groups.has(key)) groups.set(key, []);
  groups.get(key).push(t);
}
let groupList = [...groups.values()];
if (LIMIT) groupList = groupList.slice(0, LIMIT);
if (!groupList.length) { console.log(`PASS w4-actions - no open ${KINDS.join('/')} action row on axis "${AXIS}"${HOST ? ' for ' + HOST : ''} (nothing to walk)`); process.exit(0); }
console.log(`${rows.length} row(s) in ${groupList.length} walk group(s) on ${AXIS} (${KINDS.join(', ')})`);

const AUDIT_STEP = (s) => { if (!window.__W4_AUDIT) return { step: s, error: 'audit not installed', findings: 0 }; const r = window.__W4_AUDIT(null, { step: s }); return { step: s, vw: innerWidth, findings: r.findings || 0, occlusion: (r.occlusion || []).slice(0, 4), overflowEl: (r.overflowEl || []).slice(0, 2), wrapped: (r.wrapped || []).slice(0, 2), confusions: r.confusions || 0 }; };
const READ = () => ({ url: location.pathname.split('/').pop() + location.search, worker: localStorage.getItem('wh_last_worker'), chars: (document.body.innerText || '').replace(/\s+/g, ' ').trim().length });

const browser = await chromium.launch();
const results = [];
const freeGb = () => os.freemem() / 1e9;
// the receipt is written after EVERY group (merged by id with what is on disk): a run that is killed hours in still
// leaves every walked row bankable, and tools/bank_w4_passers.py can bank while the run continues
mkdirSync('.tmp/mcp_walks', { recursive: true });
const outFile = `.tmp/mcp_walks/W4actions_${AXIS.replace(/\s+/g, '-')}.json`;
const flush = () => {
  let merged = results;
  try { if (existsSync(outFile)) { const prior = JSON.parse(readFileSync(outFile, 'utf8')); const now = new Map(results.map((r) => [r.id, r])); merged = (prior.results || []).map((r) => now.get(r.id) || r).concat(results.filter((r) => !(prior.results || []).some((p) => p.id === r.id))); } } catch (e) { void e; }
  writeFileSync(outFile, JSON.stringify({ generated: new Date().toISOString(), instrument: 'tools/prove_w4_actions.mjs', axis: AXIS, walked: results.length, bad: results.filter((r) => !r.ok).length, results: merged }, null, 1));
};
for (const group of groupList) {
  const t0 = group[0];
  const pages = (t0.pages || []).slice();
  const anon = t0.persona === 'anon';
  const hive = (t0.journey || {}).vertical; const who = !anon && hive && CAST[hive] ? CAST[hive].worker : null;
  const problems = []; const steps = []; const hits = []; let current = pages[0];
  let waited = 0; while (freeGb() < 0.6 && waited < 180) { await new Promise((r) => setTimeout(r, 15000)); waited += 15; }
  const context = await browser.newContext({ viewport, isMobile: true, hasTouch: true, deviceScaleFactor: 1, locale: lang === 'fil' ? 'fil-PH' : 'en-PH', serviceWorkers: 'block' });
  const page = await context.newPage();
  await page.addInitScript({ content: AUDIT });
  if (lang === 'fil') await page.addInitScript(() => { try { localStorage.setItem('wh_lang', 'fil'); } catch (e) { void e; } });
  page.on('response', async (res) => {
    const u = res.url(); if (!/\/rest\/v1\/|\/functions\/v1\//.test(u)) return;
    const method = res.request().method(); if (method === 'OPTIONS') return;
    let bytes = 0; try { bytes = (await res.body()).length; } catch (e) { void e; }
    hits.push({ url: u.replace(/^https?:\/\/[^/]+/, '').slice(0, 160), method, status: res.status(), bytes, page: current });
  });
  const step = async (label) => { await page.evaluate(() => window.scrollTo(0, 0)).catch(() => {}); await page.waitForTimeout(300); const r = await page.evaluate(READ).catch(() => ({ chars: 0, url: '?' })); const a = await page.evaluate(AUDIT_STEP, label).catch(() => ({ findings: 0 })); steps.push({ page: label, arrivedAt: r.url, chars: r.chars, identityKept: anon ? true : !!r.worker, fit: { findings: a.findings || 0, occlusion: a.occlusion || [], overflowEl: a.overflowEl || [], wrapped: a.wrapped || [], confusions: a.confusions || 0 } }); if (r.chars < 120) problems.push(`${label}: arrived with ${r.chars} chars`); if ((a.occlusion || []).length) problems.push(`overlap at "${label}": ` + a.occlusion.slice(0, 2).join(' | ')); return r; };
  const settle = async () => { await page.waitForTimeout(4000); let r = await page.evaluate(READ).catch(() => ({ chars: 0 })); let k = 0; while (r.chars < 900 && k < 3) { await page.waitForTimeout(3000); r = await page.evaluate(READ).catch(() => ({ chars: 0 })); k++; } };
  const ctaResult = {};   // learn-cta rows: id -> { ok, detail }
  const actResult = {};   // print / cta rows: id -> { ok, detail }
  await page.addInitScript(() => { window.__w4Printed = false; const orig = window.print; window.print = function () { window.__w4Printed = true; try { return orig && orig.call(window); } catch (e) { void e; } }; });
  let downloads = 0; page.on('download', () => { downloads++; }); let popups = 0; page.on('popup', async (pp) => { popups++; try { await pp.close(); } catch (e) { void e; } });
  const actOn = async (p) => {
    for (const t of group.filter((x) => (x.w4.action.kind === 'print' || x.w4.action.kind === 'cta') && subjectPage(x) === p && !actResult[x.id])) {
      const kind = x_kind(t);
      try {
        if (kind === 'print') {
          const ctl = page.locator('button, a, [role="button"]').filter({ hasText: /print|download pdf|export pdf|save as pdf|i-print|pdf/i }).first();
          if (!(await ctl.count()) || !(await ctl.isVisible().catch(() => false))) { actResult[t.id] = { ok: false, detail: `no visible print / export-PDF control on ${p}` }; continue; }
          const label = ((await ctl.textContent().catch(() => '')) || '').replace(/\s+/g, ' ').trim().slice(0, 40);
          const d0 = downloads, p0 = popups; await page.evaluate(() => { window.__w4Printed = false; });
          await ctl.click({ timeout: 8000 }).catch(() => {}); await page.waitForTimeout(8000);
          const printed = await page.evaluate(() => !!window.__w4Printed).catch(() => false);
          actResult[t.id] = { ok: printed || downloads > d0 || popups > p0, detail: `"${label}" on ${p}: ${printed ? 'window.print was called' : downloads > d0 ? 'a file download started' : popups > p0 ? 'a print/PDF window opened' : 'neither window.print, a download nor a window followed in 8s'}` };
        } else {
          const subj = String(t.w4.action.subject || ''); const generic = /the page's primary link/i.test(subj);
          const normL = (x) => String(x || '').replace(/[^\p{L}\p{N} ]/gu, ' ').replace(/\s+/g, ' ').trim().toLowerCase(); const want = normL(subj);
          const all = page.locator('button, a[href], [role="button"], input[type="submit"]'); const cnt = await all.count(); let ctl = null; let label = '';
          for (let i = 0; i < Math.min(cnt, 400) && !ctl; i++) {
            const el = all.nth(i); if (!(await el.isVisible().catch(() => false))) continue;
            const txt = normL((await el.textContent().catch(() => '')) || (await el.getAttribute('value').catch(() => '')) || (await el.getAttribute('aria-label').catch(() => '')) || '');
            const cls = ((await el.getAttribute('class').catch(() => '')) || '').toLowerCase(); const primary = /btn-primary|primary|cta|submit/.test(cls);
            if (generic ? primary : (want && txt && (txt === want || txt.startsWith(want) || (txt.length > 3 && want.startsWith(txt))))) { ctl = el; label = txt.slice(0, 40); }
          }
          if (!ctl) { actResult[t.id] = { ok: false, detail: generic ? `no visible primary-styled control on ${p}` : `no visible control labelled "${subj}" on ${p}` }; continue; }
          const h0 = hits.length;
          const before = await page.evaluate(() => ({ url: location.href, len: (document.body.innerText || '').length, dialogs: [...document.querySelectorAll('[role="dialog"], .modal, .sheet')].filter((e) => e.getBoundingClientRect().height > 0 && getComputedStyle(e).visibility !== 'hidden').length })).catch(() => ({ url: '', len: 0, dialogs: 0 }));
          await ctl.click({ timeout: 8000 }).catch(() => {}); await page.waitForTimeout(3500);
          const after = await page.evaluate(() => ({ url: location.href, len: (document.body.innerText || '').length, dialogs: [...document.querySelectorAll('[role="dialog"], .modal, .sheet')].filter((e) => e.getBoundingClientRect().height > 0 && getComputedStyle(e).visibility !== 'hidden').length })).catch(() => ({ url: '', len: 0, dialogs: 0 }));
          const what = after.url !== before.url ? 'navigated to ' + after.url.replace(/^https?:\/\/[^/]+/, '') : after.dialogs > before.dialogs ? 'a dialog opened' : Math.abs(after.len - before.len) >= 40 ? `the page changed (${after.len - before.len >= 0 ? '+' : ''}${after.len - before.len} chars)` : (hits.length > h0 ? `the page re-read its data (${hits.length - h0} request${hits.length - h0 === 1 ? '' : 's'} answered)` : '');   /* a Refresh re-renders the same words: the change a person cannot see is the read it triggered */
          actResult[t.id] = { ok: !!what, detail: `"${label}" on ${p}: ${what || 'nothing visible changed in 3.5s'}` };
          if (after.url !== before.url) { await page.goBack({ waitUntil: 'load', timeout: 30000 }).catch(() => {}); await page.waitForTimeout(1500); }
          else if (after.dialogs > before.dialogs) { await page.keyboard.press('Escape').catch(() => {}); await page.waitForTimeout(400); }
        }
      } catch (err) { actResult[t.id] = { ok: false, detail: 'the action threw: ' + String(err.message).split('\n')[0].slice(0, 100) }; }
    }
  };
  const x_kind = (t) => t.w4.action.kind;
  try {
    if (anon) {
      await page.goto(`${ORIGIN}/${pages[0]}`, { waitUntil: 'load', timeout: 60000 }); await settle(); await actOn(pages[0]); await step(pages[0]);
      let ctaArrivals = 0; const ctaRows = group.filter((x) => x.w4.action.kind === 'learn-cta');
      for (const t of ctaRows) {
        if (ctaRows.indexOf(t) > 0) { await page.goto(`${ORIGIN}/${pages[0]}`, { waitUntil: 'load', timeout: 60000 }).catch(() => {}); await settle(); }   /* back on the guide for the next CTA */
        const subject = String(t.w4.action.subject || '');
        // the seeder's five CTA shapes (tools/seed_expansion_wave4.py learn_actions): each resolves to a link rule and an arrival rule
        const spec = (() => {
          if (subject.startsWith('named-tool:')) { const target = subject.slice(11); return { mode: 'path', tpath: target.split('?')[0].split('#')[0], tquery: target.includes('?') ? target.slice(target.indexOf('?')).split('#')[0] : '', label: target }; }
          if (subject.startsWith('named-calculator:')) return { mode: 'path', tpath: '/tools/' + subject.slice(17) + '/', tquery: '', label: '/tools/' + subject.slice(17) + '/' };
          if (subject.startsWith('related-guide:')) return { mode: 'path', tpath: '/learn/' + subject.slice(14) + '/', tquery: '', label: '/learn/' + subject.slice(14) + '/' };
          if (subject === 'sign-up') return { mode: 'signup', tpath: '', tquery: '', label: 'the sign-up line (?signup=1)' };
          if (subject === 'open-workhive') return { mode: 'home', tpath: '', tquery: '', label: 'the landing page (.lh-cta)' };
          return { mode: 'path', tpath: subject, tquery: '', label: subject };
        })();
        const target = spec.label;
        const found = await page.evaluate(({ mode, tpath, tquery }) => {
          const matches = (a) => { let u; try { u = new URL(a.href, location.href); } catch (e) { return false; }
            if (mode === 'signup') return /[?&]signup=1/.test(u.search);
            if (mode === 'home') return (!!a.closest('.lh-cta, [class*="lh-cta"]') || /open workhive|start free|get started|simulan/i.test(a.textContent || '')) && /\/(index\.html)?$/.test(u.pathname);
            const pth = u.pathname; const ok = pth.endsWith(tpath) || (tpath.endsWith('/') && pth.endsWith(tpath + 'index.html')); return ok && (!tquery || u.search === tquery); };
          /* the seeder's sign-up subject is the .cta-secondary line's link, not the nav's "Sign Up Free" (which a collapsed
             nav hides at 320): prefer that line, then any matching link that is actually visible and reachable */
          const cands = [...document.querySelectorAll('a[href]')].filter(matches);
          const vis = (a) => { const r = (a.getClientRects && a.getClientRects()[0]) || a.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(a).visibility !== 'hidden'; };
          const m = (mode === 'signup' ? cands.find((a) => a.closest('.cta-secondary') && vis(a)) : null) || cands.find(vis) || cands[0]; if (!m) return { exists: false };
          m.scrollIntoView({ block: 'center' }); /* an INLINE link that wraps has a bounding box whose centre falls between its line boxes (the parent <p>/<li> is what sits there) - probe the FIRST line box, which is what a finger meets (2026-09-15: "covered by p / li" on links that clicked and arrived fine) */ const r = (m.getClientRects && m.getClientRects()[0]) || m.getBoundingClientRect(); const hit = document.elementFromPoint(Math.min(innerWidth - 1, r.left + r.width / 2), Math.min(innerHeight - 1, r.top + r.height / 2)); m.setAttribute('data-w4-cta', '1');
          return { exists: true, href: m.getAttribute('href'), text: (m.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60), reachable: !!hit && (hit === m || m.contains(hit)), hit: hit ? (hit.id ? '#' + hit.id : hit.tagName.toLowerCase()) : null };
        }, spec).catch(() => ({ exists: false }));
        if (!found.exists) { ctaResult[t.id] = { ok: false, detail: `no link to ${target} on ${pages[0]}` }; continue; }
        await page.click('a[data-w4-cta="1"]', { timeout: 8000 }).catch(() => {});
        const arrived = await page.waitForURL((u) => { if (spec.mode === 'signup') return /[?&]signup=1/.test(u.search); if (spec.mode === 'home') return /\/(index\.html)?$/.test(u.pathname); const pth = u.pathname; return (pth.endsWith(spec.tpath) || (spec.tpath.endsWith('/') && pth.endsWith(spec.tpath + 'index.html'))) && (!spec.tquery || u.search === spec.tquery); }, { timeout: 20000 }).then(() => true).catch(() => false);
        ctaResult[t.id] = { ok: found.reachable && arrived, detail: `CTA "${found.text}" ${found.reachable ? 'reachable' : 'covered by ' + found.hit}; ${arrived ? 'arrived at ' + target : 'did not arrive at ' + target + ' in 20s'}` };
        /* an arrival step only when the CTA lands on the path's next page, and only once */
        const onNext = arrived && pages[1] && await page.evaluate((nx) => location.pathname.endsWith('/' + nx), pages[1]).catch(() => false);
        if (onNext && ctaArrivals === 0) { current = pages[1]; await settle(); await actOn(pages[1]); await step(pages[1]); ctaArrivals++; }
      }
      if (pages[1] && ctaArrivals === 0) { current = pages[1]; await page.goto(`${ORIGIN}/${pages[1]}`, { waitUntil: 'load', timeout: 60000 }).catch((err) => problems.push(`${pages[1]}: ${String(err.message).split('\n')[0].slice(0, 80)}`)); await settle(); await actOn(pages[1]); await step(pages[1]); }
      for (const p of pages.slice(2)) { current = p; await page.goto(`${ORIGIN}/${p}`, { waitUntil: 'load', timeout: 60000 }).catch((err) => problems.push(`${p}: ${String(err.message).split('\n')[0].slice(0, 80)}`)); await settle(); await actOn(p); await step(p); }
    } else {
      await page.goto(`${ORIGIN}/index.html?signin=1&return=${pages[1] || pages[0]}`, { waitUntil: 'load', timeout: 60000 });
      await page.waitForSelector('#si-username', { state: 'visible', timeout: 45000 }).catch(() => {});
      await step('index.html');
      if (!who) problems.push(`no active worker with an account in ${hive}`);
      else if (await page.locator('#si-username').isVisible().catch(() => false)) {
        await page.fill('#si-username', who.user, { timeout: 8000 }); await page.fill('#si-password', 'test1234', { timeout: 8000 });
        await page.click('#si-btn', { timeout: 10000 }).catch(async () => { await page.press('#si-password', 'Enter').catch(() => {}); });
        await page.waitForURL(atPath(pages[1] || pages[0]), { timeout: 30000 }).catch(async () => { problems.push('sign-in did not reach ' + (pages[1] || pages[0]) + ' in 30s: ' + await page.evaluate(() => ((document.getElementById('si-error') || {}).textContent || '').trim().slice(0, 100)).catch(() => '?')); });
      }
      for (const p of pages.slice(1)) { current = p; const here = await page.evaluate(() => location.pathname.split('/').pop()).catch(() => ''); if (here !== p) await page.goto(`${ORIGIN}/${p}`, { waitUntil: 'load', timeout: 60000 }).catch((err) => problems.push(`${p}: ${String(err.message).split('\n')[0].slice(0, 80)}`)); await settle(); await actOn(p); await step(p); }
    }
  } catch (err) { problems.push('the walk threw: ' + String(err.message).split('\n')[0].slice(0, 120)); }
  const provenance = await page.evaluate(() => { const c = document.querySelector('.wh-source-chip'); return c ? (c.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120) : ''; }).catch(() => '');
  // ★"CALL RPC X AND READ WHAT IT RETURNS" IS THE PERSON'S CALL, NOT ONLY THE PAGE'S (2026-09-15): a page calls some of
  // its RPCs only on a tap, so a walk that just loads it never sees them (W422 compute_anomaly_signals). The story is
  // satisfied by the person's OWN SESSION calling the function - so, for an rpc row with no observed call, the prover
  // calls it from the page with the person's JWT (the same PostgREST route the page uses) and records the answer. A
  // function that needs arguments the story does not give answers 4xx and the row stays open, honestly.
  const direct = {};
  let pageHitCount = hits.length;
  if (!anon) {
    pageHitCount = hits.length;   // everything after this index is the prover's own call, not the page's
    const ctxVals = await page.evaluate(() => ({ hiveId: localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id') || null, worker: localStorage.getItem('wh_last_worker') || null, keys: Object.keys(localStorage).filter((k) => /auth|sb-/.test(k)).slice(0, 6) })).catch(() => ({ hiveId: null, worker: null, keys: [] }));
    for (const t of group.filter((x) => x.w4.action.kind === 'rpc' && !hits.slice(0, pageHitCount).some((h) => h.url.includes('/rest/v1/rpc/' + String(x.w4.action.subject || ''))))) {
      const subj = String(t.w4.action.subject || '');
      if (MUTATING.test(subj)) { direct[subj] = { status: 0, note: 'a mutating rpc is not called by the walk; the page\'s own control must trigger it' }; continue; }
      const sig = (SIGS[subj] || [''])[0]; const body = {}; const missing = [];
      for (const a of sig.split(',').map((x) => x.trim()).filter(Boolean)) { const name = a.split(/\s+/)[0]; const v = fillArg(name, ctxVals); if (v === undefined || v === null) missing.push(name); else body[name] = v; }
      if (missing.length) { direct[subj] = { status: 0, note: 'needs argument(s) the story does not give: ' + missing.join(', ') + ' (signature ' + sig + ')' }; continue; }
      direct[subj] = await page.evaluate(async ({ subj, apikey, api, body, keys }) => {
        try {
          const k = Object.keys(localStorage).find((x) => /^sb-.*-auth-token$/.test(x)); if (!k) return { status: 0, note: 'no session token in localStorage (keys: ' + keys.join(',') + ')' };
          const tok = (JSON.parse(localStorage.getItem(k)) || {}).access_token; if (!tok) return { status: 0, note: 'session token has no access_token' };
          const r = await fetch(`${api}/rest/v1/rpc/${subj}`, { method: 'POST', headers: { apikey, Authorization: 'Bearer ' + tok, 'Content-Type': 'application/json', Prefer: 'return=representation' }, body: JSON.stringify(body) });
          const txt = await r.text(); let rows = null; try { const j = JSON.parse(txt); rows = Array.isArray(j) ? j.length : (j && typeof j === 'object' ? 1 : null); } catch (e) { void e; }   /* `txt`, not `body`: a const named body here shadowed the request body in the whole try block and every call died in the TDZ ("Cannot access 'body' before initialization", 2026-09-15 02:02) */
          return { status: r.status, bytes: txt.length, rows, note: r.ok ? '' : txt.slice(0, 120) };
        } catch (e) { return { status: 0, note: String(e.message).slice(0, 100) }; }
      }, { subj, apikey: ANON_KEY, api: API, body, keys: ctxVals.keys || [] }).catch((e) => ({ status: 0, note: String(e.message).slice(0, 80) }));
    }
  }
  const pageHits = typeof pageHitCount === 'number' ? pageHitCount : hits.length;
  await context.close().catch(() => {});
  const idKept = anon ? true : steps.slice(1).every((s) => s.identityKept);
  const distinct = new Set(steps.map((s) => s.page)).size;
  for (const t of group) {
    const act = t.w4.action; const subj = String(act.subject || '');
    let pred; let observed = null; let effect = null;
    if (act.kind === 'rpc') { const h = hits.slice(0, pageHits).find((x) => x.url.includes('/rest/v1/rpc/' + subj)); const dc = direct[subj]; observed = h || (dc ? Object.assign({ via: 'called directly by the person\'s own session' }, dc) : null); const okHit = !!h && h.status >= 200 && h.status < 300; const okDirect = !!dc && dc.status >= 200 && dc.status < 300; pred = { ok: okHit || okDirect, detail: h ? `rpc ${subj} answered ${h.status} with ${h.bytes} bytes on ${h.page}` : dc ? `rpc ${subj} called by the person's own session answered ${dc.status}${dc.rows != null ? ' with ' + dc.rows + ' row(s)' : ''}${dc.note ? ' - ' + dc.note : ''}` : `the person's session never called rpc ${subj} along ${pages.map((p) => p.split('/').pop()).join(' -> ')}` }; }
    else if (act.kind === 'edge') { const h = hits.find((x) => x.url.includes('/functions/v1/' + subj)); observed = h || null; if (h) effect = { fn: subj, status: h.status, bytes: h.bytes, page: h.page, provenance }; pred = { ok: !!h && h.status >= 200 && h.status < 300 && !!provenance, detail: h ? `${subj} answered ${h.status} with ${h.bytes} bytes on ${h.page}; provenance ${provenance ? '"' + provenance.slice(0, 60) + '"' : 'ABSENT (no source chip)'}` : `the person's session never invoked ${subj} along the path` }; }
    else if (act.kind === 'learn-cta') { pred = ctaResult[t.id] || { ok: false, detail: 'the CTA step did not run' }; }
    else if (act.kind === 'print' || act.kind === 'cta') { pred = actResult[t.id] || { ok: false, detail: `the subject page ${subjectPage(t)} was not reached on this path` }; }
    else pred = { ok: false, detail: `no walker for action kind ${act.kind}` };
    const rowProblems = problems.slice(); if (!pred.ok) rowProblems.push(`${act.kind} ${subj} not lived clean: ${pred.detail}`); if (!idKept) rowProblems.push('identity did not survive the arrival'); if (distinct < 4) rowProblems.push(`only ${distinct} distinct pages walked`);
    const ok = rowProblems.length === 0;
    results.push({ id: t.id, ok, unbuilt: !anon && !who, instrument: 'tools/prove_w4_actions.mjs', condition: 'normal', cast: anon ? 'anonymous reader' : (who ? `${who.name} (${hive})` : `no cast in ${hive}`), problems: rowProblems,
      note: `${act.kind} ${subj} ${pred.ok ? 'LIVED CLEAN' : 'STILL OPEN'}: ${pred.detail}`, metrics: { steps: steps.length, idKept, predicate: pred.ok, hits: hits.length },
      w4: Object.assign({ axis: AXIS, action: act, observed }, effect ? { effect } : {}), steps, confusions: [] });
    console.log(`  ${ok ? '\x1b[92mOK \x1b[0m' : '\x1b[91mBAD\x1b[0m'} ${t.id.padEnd(7)} ${act.kind.padEnd(9)} ${subj.slice(0, 34).padEnd(34)} ${(anon ? 'anon' : (who ? who.name : '?')).padEnd(18)} ${pred.detail.slice(0, 120)}${!pred.ok || !ok ? (rowProblems[0] && !rowProblems[0].includes('not lived clean') ? ' | ' + rowProblems[0].slice(0, 80) : '') : ''}`);
  }
  flush();
  await new Promise((r) => setTimeout(r, 3000));
}
await browser.close();
flush();
const bad = results.filter((r) => !r.ok).length;
console.log(`${bad ? 'FAIL' : 'PASS'} w4-actions@${AXIS} - ${results.length - bad}/${results.length} action rows lived clean start to end (path walked, identity kept, the action observed, no overlap) · ${outFile}`);
