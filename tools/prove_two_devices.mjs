// prove_two_devices.mjs - one account open on a phone (390) and a desktop (1280) at once: a write on the phone appears on
// the desktop within the realtime budget or by an honest refresh, with no conflict and no lost draft (OWN "two devices",
// 2026-10-27).
//
// THE INSTRUMENT. Two browser contexts signed in as the SAME account. The desktop (B) opens the page first and starts a
// draft (in a composer it opens, or the first free-text field). The phone (A) then performs the write by running the
// registered journey's own drive (tools/live_page_journeys.registry.mjs) - the UI path the journey proves, not a
// back-door insert - or a SCENARIO below where the write needs state both devices must hold first. The journey's cleanup
// is DEFERRED until B has looked. B is watched for the write's own effect (OBSERVE: a marker the write created, or the
// value it changed) for the realtime budget WITHOUT reloading; two seconds in, the person "comes back" to the desktop
// (focus + visibilitychange, still no reload). If the effect never shows, B reloads once ("refresh"). The draft is read
// back after the live window and after any reload.
//
// ★A MARKER MUST BE THE WRITE'S OWN (learned on the first runs): a word lifted from a cleanup statement ("assistant")
// was on the page already, and a listing the journey SEEDED before its write reached the desktop by realtime and read as
// the phone's inquiry. So every marker is checked against the desktop's page as it was BEFORE the write, and journeys
// whose write changes a value are observed on the value (INV2: 20 -> 18), not on a seeded name.
//
//   node tools/prove_two_devices.mjs --journey CM1 [--journey AL4X ...] [--budget 15000]
// writes two_devices_results.json (one entry per id, merged).
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { signIn, makeHelpers, assertSignedIn } from './live_page_journeys.mjs';
import { JOURNEYS } from './live_page_journeys.registry.mjs';

const args = process.argv.slice(2);
// one check per page the OWN two-devices lens names (OWN144..158), in that order
const ALL = ['AL4X', 'LOG1@asset-hub', 'LOG1@assistant', 'CM1', 'DAY1', 'ED2', 'LOG1@index', 'SYNCCFG@integrations', 'INV2',
  'MK5', 'SYNCCFG@plant-connections', 'PMK1', 'RS2', 'SBPUB', 'SKK2'];
const ASKED = args.flatMap((a, i) => (a === '--journey' ? [args[i + 1]] : []));
const IDS = ASKED.length ? ASKED : ALL;
const BUDGET = Number((args[args.indexOf('--budget') + 1]) || 15000) || 15000;
const OUT = 'two_devices_results.json';

const lit = (deferred, rx = /'%?([A-Za-z0-9][A-Za-z0-9 ._@-]{5,})%?'/) => {
  for (const sql of deferred) { const m = sql.match(rx); if (m) return m[1]; }
  return null;
};

// What the phone's write leaves on the desktop. marker(): text the write itself created (must be absent before it).
// check(): a value the write changed, read in place. reveal(): where on the page a person would look.
const OBSERVE = {
  CM1: { marker: (ev) => ev.nonce },
  DAY1: { marker: (ev, d) => lit(d) },
  ED2: { marker: (ev) => ev.tag,
         reveal: async (p) => { await p.evaluate(() => { if (typeof window.switchTab === 'function') window.switchTab('history'); }); await p.waitForTimeout(1500); } },
  PMK1: { marker: (ev) => ev.name,
          reveal: async (p) => { try { await p.click('button[data-status="planning"]', { timeout: 4000 }); } catch (_) { /* tab missing */ } await p.waitForTimeout(800); } },
  RS2: { marker: (ev) => ev.email },
  MK5: { marker: (ev, d) => lit(d),
         reveal: async (p) => { try { await p.click('#btn-saved-searches', { timeout: 4000 }); } catch (_) { /* button missing */ } await p.waitForTimeout(1500); } },
  // the write is "use 2 of 20": the part is seeded by the journey, so its NAME proves nothing; its quantity does
  INV2: { reveal: async (p, c) => {   // a new part sits past the first page: the person searches for it
            const pn = lit((c && c.deferred) || [], /'(K2-USE-\d+)%?'/);
            if (pn) await p.evaluate((n) => { const s = document.getElementById('search-input'); if (s) { s.value = n; s.dispatchEvent(new Event('input', { bubbles: true })); } }, pn);
            await p.waitForTimeout(800); },
          check: async (p, c) => {
    const pn = lit(c.deferred, /'(K2-USE-\d+)%?'/);
    return pn ? p.evaluate((n) => { const card = [...document.querySelectorAll('.part-card')].find((e) => (e.textContent || '').includes(n));
      const fig = card && card.querySelector('[data-fig="qty"]');
      return !!fig && parseFloat(fig.textContent) === 18; }, pn) : false;
  } },
  // a breakdown logged on the phone: the desktop home's My Open Jobs, and the machine's own history in the asset hub
  // My Open Jobs shows the machine and the time, not the problem text: the row's own link names the entry
  'LOG1@index': { observer: 'index.html', marker: (ev, d, q) => {
    const tag = lit(d);
    const id = tag ? String(q(`select id from logbook where problem like '${tag}%' limit 1;`) || '').trim() : '';
    return id ? `logbook.html?id=${encodeURIComponent(id)}` : null; } },
  'LOG1@asset-hub': { observer: 'asset-hub.html', marker: (ev, d) => lit(d),
    reveal: async (p, c) => {   // the person opens that machine
      const tag = lit(c.deferred);
      const node = tag ? String(c.q(`select coalesce(asset_node_id::text,'') from logbook where problem like '${tag}%' limit 1;`) || '').trim() : '';
      if (/^[0-9a-f-]{36}$/.test(node)) { await p.goto(`http://127.0.0.1:5000/workhive/asset-hub.html?node_id=${node}`, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(4000); }
    } },
  // The assistant's conversation is this device's own (sessionStorage) and its records summary sits on the setup screen
  // only; what crosses devices is GROUNDING - an entry logged on the phone must inform the desktop's next answer. So the
  // desktop asks, and the reply must carry the entry's unique tag, which it can only have by retrieving that entry.
  'LOG1@assistant': { observer: 'assistant.html', budget: 45000, mode: 'in the answer when asked', noDraft: true,
    snapshot: async (p) => p.evaluate(() => { const bs = [...document.querySelectorAll('.bubble-assistant')]; return bs.length ? (bs[bs.length - 1].textContent || '').slice(0, 400) : null; }),
    reveal: async (p, c) => {
      const tag = lit(c.deferred);
      // the person names the machine they just logged (the seeded hive holds entries dated after today, so 'most recent'
      // by date is not this one); the gateway reads that machine's entries when its tag is in the message
      const machine = tag ? String(c.q(`select coalesce(machine,'') from logbook where problem like '${tag}%' limit 1;`) || '').trim() : '';
      await p.fill('#chat-input', `I just logged a repair on ${machine || 'a machine'}. What problem did I write for it? Quote it exactly.`).catch(() => {});
      await p.evaluate(() => { const b = document.getElementById('send-btn') || [...document.querySelectorAll('button')].find((x) => /send/i.test(x.getAttribute('aria-label') || x.textContent || '')); if (b) b.click(); });
      c.tag = tag; },
    check: async (p, c) => { const tag = lit(c.deferred); return !!tag && p.evaluate((t) => { const bs = [...document.querySelectorAll('.bubble-assistant')]; return bs.length > 0 && (bs[bs.length - 1].textContent || '').includes(t); }, tag); } },
  SKK2: { check: async (p, c) => {
    const want = c.ev && Number(c.ev.after);
    return Number.isFinite(want) && p.evaluate((w) => { const el = document.getElementById('step-val-Electrical'); return !!el && parseInt(el.textContent, 10) === w; }, want);
  } },
};
// statements the journey runs after its write that must wait until the desktop has looked (default: DELETEs)
const DEFER = { SKK2: /^\s*(delete|update skill_profiles)\b/i };

// Writes whose state both devices must already hold (the desktop must have the brief on screen before the phone approves
// it, and AL4 seeds its brief inside its own drive).
const SCENARIOS = {
  AL4X: {
    page: 'alert-hub.html', role: 'supervisor',
    async setup(q, hive) {
      const today = String(q(`select to_char((now() at time zone 'Asia/Manila'),'YYYY-MM-DD');`)).trim();
      q(`delete from amc_briefings where brief->>'tag'='TWO-DEV-AL4';`);
      const realId = String(q(`select id from amc_briefings where hive_id='${hive}' and shift_date='${today}';`) || '').trim();
      if (/^[0-9a-f-]{36}$/.test(realId)) q(`update amc_briefings set shift_date = shift_date - 36500 where id='${realId}';`);
      const ins = String(q(`insert into amc_briefings (id, hive_id, shift_date, status, brief, generated_at) values (gen_random_uuid(),'${hive}','${today}','pending','{"tag":"TWO-DEV-AL4","summary":"Two-device check: approve on the phone."}'::jsonb, now()) returning id;`));
      return { realId: /^[0-9a-f-]{36}$/.test(realId) ? realId : null, briefId: (ins.match(/[0-9a-f]{8}-[0-9a-f-]{27}/) || [null])[0] };
    },
    async write(pageA, hA) {
      await hA.goto('alert-hub.html');
      await hA.waitFor('#amc-approve-btn:not([style*="display: none"]):not([style*="display:none"])', 9000);
      const clicked = await hA.evalIn(() => { const b = document.getElementById('amc-approve-btn'); if (b && b.offsetParent !== null) { b.click(); return true; } return false; });
      await hA.waitFor('[data-wh-modal-ok]', 4000); await pageA.waitForTimeout(300);
      await hA.evalIn(() => { const b = document.querySelector('[data-wh-modal-ok]'); if (b) b.click(); });
      await pageA.waitForTimeout(2200);
      return { clicked };
    },
    observe: async (p) => p.evaluate(() => /approved/i.test((document.getElementById('amc-status-pill') || {}).textContent || '')
      && /Approved by/.test((document.getElementById('amc-status-msg') || {}).textContent || '')),
    preCheck: async (p) => p.evaluate(() => /pending/i.test((document.getElementById('amc-status-pill') || {}).textContent || '')),
    cleanup(q, ctx) {
      q(`delete from amc_briefings where brief->>'tag'='TWO-DEV-AL4';`);
      if (ctx.briefId) q(`delete from hive_audit_log where target_id='${ctx.briefId}';`);
      if (ctx.realId) q(`update amc_briefings set shift_date = shift_date + 36500 where id='${ctx.realId}';`);
    },
  },
  // a connector saved on the phone: the desktop's connector list, and the plant-connections status table
  'SYNCCFG@integrations': syncCfg('integrations.html', async (p) => { await p.evaluate(() => { try { window.switchTab && window.switchTab('sync'); } catch (_) { /* tab */ } }); await p.waitForTimeout(1500); }),
  'SYNCCFG@plant-connections': syncCfg('plant-connections.html', null),
  // the supervisor publishes the shift plan on the phone; the same supervisor's desktop has the draft on screen
  SBPUB: {
    page: 'shift-brain.html', role: 'supervisor',
    async setup(q, hive) {
      const h = new Date(Date.now() + 8 * 3600 * 1000).getUTCHours();
      const win = h >= 6 && h < 14 ? '06-14' : (h >= 14 && h < 22 ? '14-22' : '22-06');
      const today = String(q(`select to_char((now() at time zone 'Asia/Manila'),'YYYY-MM-DD');`)).trim();
      q(`delete from shift_plans where briefing like 'TWO-DEV-SB%';`);
      const ins = String(q(`insert into shift_plans (id, hive_id, shift_window, shift_date, status, generated_at, generated_by, briefing, payload, created_at, updated_at) values (gen_random_uuid(),'${hive}','${win}','${today}','draft', now(), 'two-device check', 'TWO-DEV-SB plan for the two-device check.', '{}'::jsonb, now(), now()) returning id;`));
      return { planId: (ins.match(/[0-9a-f]{8}-[0-9a-f-]{27}/) || [null])[0] };
    },
    async write(pageA, hA) {
      await hA.goto('shift-brain.html');
      await hA.waitFor('#publish-btn:not([disabled])', 9000);
      const clicked = await hA.evalIn(() => { const b = document.getElementById('publish-btn'); if (b && !b.disabled && b.offsetParent !== null) { b.click(); return true; } return false; });
      await hA.waitFor('[data-wh-modal-ok]', 4000); await pageA.waitForTimeout(300);
      await hA.evalIn(() => { const b = document.querySelector('[data-wh-modal-ok]'); if (b) b.click(); });
      await pageA.waitForTimeout(2500);
      return { clicked };
    },
    preCheck: async (p) => p.evaluate(() => { const b = document.getElementById('publish-btn'); return !!b && !b.disabled && /TWO-DEV-SB/.test(document.body.innerText || ''); }),
    observe: async (p) => p.evaluate(() => { const b = document.getElementById('publish-btn'); return !!b && b.disabled && /published/i.test(b.textContent || ''); }),
    cleanup(q, ctx) { q(`delete from shift_plans where briefing like 'TWO-DEV-SB%';`); },
  },
};

function syncCfg(observer, reveal) {
  const label = `TWO-DEV connector ${Date.now()}`;
  return {
    page: observer, role: 'supervisor', reveal,
    async setup(q) { q(`delete from integration_configs where label like 'TWO-DEV connector%';`); return { label }; },
    async write(pageA, hA) {
      await hA.goto('integrations.html');
      await hA.evalIn(() => { try { window.switchTab && window.switchTab('sync'); } catch (_) { /* tab */ } });
      await hA.waitFor('#sc-label', 6000);
      await hA.fill('#sc-label', label);
      await pageA.selectOption('#sc-type', { value: 'generic' }).catch(() => {});
      await hA.fill('#sc-url', 'https://cmms.example.invalid/api/work-orders');
      const clicked = await hA.evalIn(() => { const b = [...document.querySelectorAll('button')].find((x) => /Save & Enable/.test(x.textContent || '')); if (b) { b.click(); return true; } return false; });
      await pageA.waitForTimeout(2500);
      return { clicked };
    },
    observe: async (p) => (await pageText(p)).includes(label),
    cleanup(q) { q(`delete from integration_configs where label like 'TWO-DEV connector%';`); },
  };
}

const DRAFT_OPENERS = {
  'community.html': ['#fab-post', '#post-content'],
  'dayplanner.html': ['button[onclick="openAddModal()"]', '#m-title'],
  'report-sender.html': ['#add-contact-btn', '#contact-name'],
  'inventory.html': ['#btn-add-part', '#f-part-name'],
};

async function startDraft(page, text, pageFile) {
  const op = DRAFT_OPENERS[pageFile];
  if (op) {
    try { await page.click(op[0], { timeout: 4000 }); await page.waitForTimeout(700); await page.fill(op[1], text); return op[1]; }
    catch (_) { /* fall through to the field visible at rest */ }
  }
  return page.evaluate((t) => {
    const vis = (el) => { const b = el.getBoundingClientRect(); const s = getComputedStyle(el); return b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
    const field = [...document.querySelectorAll('textarea, input[type="text"], input:not([type])')].find((el) => vis(el) && !el.disabled && !el.readOnly
      && !/search|filter|find|query/i.test(`${el.id} ${el.name} ${el.placeholder} ${el.getAttribute('aria-label') || ''}`));
    if (!field) return null;
    field.focus(); field.value = t; field.dispatchEvent(new Event('input', { bubbles: true }));
    return field.id ? `#${field.id}` : (field.name ? `[name="${field.name}"]` : field.tagName.toLowerCase());
  }, text);
}

const draftKept = async (page, sel, text) => (sel ? page.evaluate(({ s, t }) => { const el = document.querySelector(s); return !!el && el.value === t; }, { s: sel, t: text }) : null);
const pageText = (page) => page.evaluate(() => (document.body.innerText || '') + '\n' + (document.body.innerHTML || ''));

async function runOne(browser, id) {
  const sc = SCENARIOS[id];
  // 'LOG1@index': the phone runs LOG1 (on logbook.html) and the desktop watches the page the effect lives on
  const [jid] = id.split('@');
  const j = sc ? null : JOURNEYS.find((x) => x.id === jid);
  if (!sc && !j) return { id, error: 'not in the registry or the scenarios' };
  const obs = OBSERVE[id] || {};
  const pageFile = sc ? sc.page : (obs.observer || j.page), role = sc ? sc.role : j.role;
  const out = { id, page: pageFile, role, ran: new Date().toISOString() };
  const ctxB = await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: 'Asia/Manila' });
  const ctxA = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, timezoneId: 'Asia/Manila' });
  let scCtx = null, qReal = null;
  try {
    const sb = await assertSignedIn(signIn(ctxB, role));
    const sa = await assertSignedIn(signIn(ctxA, role));
    out.same_account = !!sb.uid && sb.uid === sa.uid;
    const pageB = await ctxB.newPage();
    const errsB = [];
    pageB.on('pageerror', (e) => errsB.push(String(e.message || e).slice(0, 120)));
    const hB = makeHelpers(pageB, sb.hive, sb.uid);
    qReal = hB.adminQuery;
    if (sc) scCtx = await sc.setup(qReal, sb.hive);
    await hB.goto(pageFile);
    if (sc && sc.preCheck) out.pre_state_ok = await sc.preCheck(pageB);
    const draftText = `two-device draft ${Date.now()}`;
    const draftSel = (OBSERVE[id] && OBSERVE[id].noDraft) ? null : await startDraft(pageB, draftText, pageFile);
    out.draft_field = draftSel;
    const before = await pageText(pageB);
    const base = (!sc && OBSERVE[id] && OBSERVE[id].baseline) ? await OBSERVE[id].baseline(pageB) : null;
    out.baseline = base;

    const pageA = await ctxA.newPage();
    const hA = makeHelpers(pageA, sa.hive, sa.uid);
    const deferred = [];
    const deferRx = DEFER[id] || /^\s*delete\b/i;
    hA.adminQuery = (sql) => { if (!sc && deferRx.test(sql)) { deferred.push(sql); return ''; } return qReal(sql); };
    let r = null;
    try { r = sc ? await sc.write(pageA, hA) : await j.drive(pageA, hA); } catch (e) { out.error = `phone write threw: ${String(e.message || e).slice(0, 160)}`; }
    out.phone = r ? (sc ? r : { lenses: { R: r.R, J: r.J, T: r.T }, evidence: r.evidence }) : null;

    const ev = (r && r.evidence) || {};
    const marker = obs.marker ? obs.marker(ev, deferred, qReal) : null;
    out.marker = marker;
    let probe = null;
    if (sc) probe = () => sc.observe(pageB);
    else if (obs.check) probe = () => obs.check(pageB, { ev, deferred, base });
    else if (marker) {
      if (before.includes(marker)) { out.why = `the marker '${marker}' was on the desktop before the write - not the write's own`; }
      else probe = async () => (await pageText(pageB)).includes(marker);
    } else out.why = 'no observation defined for this write';
    const wrote = sc ? !!(r && r.clicked) : !!(r && r.T !== false && r.J !== false);
    if (probe && wrote) {
      const reveal = (sc && sc.reveal) || obs.reveal;
      if (reveal) await reveal(pageB, { ev, deferred, q: qReal });
      const t0 = Date.now();
      let live = false, returned = false;
      const budget = obs.budget || BUDGET;
      while (Date.now() - t0 < budget) {
        if (await probe()) { live = true; break; }
        if (!returned && Date.now() - t0 > 2000) {   // the person comes back to the desktop: focus, no reload
          returned = true;
          await pageB.bringToFront().catch(() => {});
          await pageB.evaluate(() => { window.dispatchEvent(new Event('focus')); document.dispatchEvent(new Event('visibilitychange')); });
        }
        await pageB.waitForTimeout(1000);
      }
      out.live = live; out.live_ms = live ? Date.now() - t0 : null;
      out.mode = live ? (obs.mode || (returned ? 'on return to the tab' : (reveal ? 'on opening the view it lives in' : 'realtime'))) : null;
      out.draft_kept_live = await draftKept(pageB, draftSel, draftText);
      if (obs.snapshot) out.observed = await obs.snapshot(pageB);
      if (!live) {
        await hB.goto(pageFile);
        if (reveal) await reveal(pageB, { ev, deferred, q: qReal });
        out.after_refresh = await probe();
        out.mode = out.after_refresh ? 'after a refresh' : null;
        out.draft_kept_refresh = await draftKept(pageB, draftSel, draftText);
      }
      out.appears = live || !!out.after_refresh;
    } else {
      out.appears = false;
      out.why = out.why || (wrote ? 'nothing to observe' : 'the phone write did not complete');
    }
    out.page_errors_desktop = errsB;
    for (const sql of deferred) qReal(sql);
    out.cleaned = deferred.length;
    return out;
  } finally {
    if (sc && scCtx && qReal) { try { sc.cleanup(qReal, scCtx); out.cleaned = 'scenario'; } catch (_) { /* reported by the next run */ } }
    await ctxA.close().catch(() => {});
    await ctxB.close().catch(() => {});
  }
}

const browser = await chromium.launch({ headless: true });
const prior = existsSync(OUT) ? JSON.parse(readFileSync(OUT, 'utf8')) : { runs: {} };
for (const id of IDS) {
  const res = await runOne(browser, id);
  prior.runs[id] = res;
  console.log(`${id}: ${res.page} appears=${res.appears} ${res.mode || ''}${res.live_ms != null ? ` ${res.live_ms}ms` : ''} draft live=${res.draft_kept_live} refresh=${res.draft_kept_refresh ?? '-'} errors=${(res.page_errors_desktop || []).length}${res.error ? ' ERR ' + res.error : ''}${res.why ? ' (' + res.why + ')' : ''}`);
}
prior.generated = new Date().toISOString();
writeFileSync(OUT, JSON.stringify(prior, null, 1));
await browser.close();
// a gate: any write this run could not see on the desktop fails it
const missed = IDS.filter((id) => !(prior.runs[id] && prior.runs[id].appears));
console.log(missed.length ? `FAIL two-devices - ${missed.length} write(s) never reached the desktop: ${missed.join(', ')}` : `PASS two-devices - ${IDS.length} write(s) on the phone reached the desktop`);
process.exitCode = missed.length ? 1 : 0;
