// prove_w4_confusions.mjs - LIVE each seeded confusion (w4_confusions.json -> registry rows of kind 'confusion') on its
// real page, at its axis, as the row's own cast, start to end along the row's path - and write the W4-shaped receipt
// (steps with per-step fit + the confusion's predicate) that live_walk_manifest._w4_missing accepts. (Wave 4, 2026-09-14.)
//
// Ian: "even you sometimes confused like the sign in, that is why we have to have more trajectories, targeting that
// makes you confused, and work our way to improve it" - "any other kinds and types". A confusion row is answered by
// meeting the SAME moment again, on the same page, and reading whether the improvement now holds: the two "Sign In"s
// (C1), the 8-second still-signing-in hint (C2), the outage said plainly instead of "name resolution failed" (C3),
// the scoped tools filter that names its view and offers all tools (C4), focus back on the fab after Escape (C5),
// a search launcher and a filter that no longer look alike (C6), no `_tt is not defined` on a mode click (C7), the
// two hive disclosures told apart by name (C8), the offline banner clearing the wayfinding pill (C10), assistant's own
// back button left alone by wayfinding (C11), the offline banner dropping a page's fixed nav (C12), the consent card
// covering no sign-in control (C13), the transport notice with a way out (C15). C9 has no predicate yet and reads as
// open (2026-09-14 later: C9 now has one - the page-guide chip stands down or covers nothing). A predicate that FAILS keeps the row open - that is the point: a walked confusion that is not fixed stays owed.
//
// Serial by design (one context at a time on the 8 GB host); the cast is a worker of the row's hive from the database,
// never invented; every reading uses window.__W4_AUDIT (tools/phone_fit_audit.browser.js) like the nav-hub walk.
// Receipt: .tmp/mcp_walks/W4confusions_<axis>.json (merged by id with the prior file), read by _w4_receipts.
//
//   node tools/prove_w4_confusions.mjs --axis "phone-390 en" [--confusion C13,C15] [--ids W45791] [--limit 3] [--force]
import { chromium } from 'playwright';
import { execSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import os from 'node:os';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 && process.argv[i + 1] ? process.argv[i + 1] : d; };
const AXIS = arg('--axis', 'phone-390 en');
const ONLY = (arg('--confusion', '') || '').split(',').map((s) => s.trim()).filter(Boolean);
const IDS = (arg('--ids', '') || '').split(',').map((s) => s.trim()).filter(Boolean);
const LIMIT = Number(arg('--limit', '0')) || 0;
const FORCE = process.argv.includes('--force');   // re-live rows already banked (a re-verification after a predicate change)
const ORIGIN = arg('--origin', 'http://localhost:5000/workhive');
const [device, lang] = AXIS.split(' ');
const viewport = device === 'narrow-320' ? { width: 320, height: 720 } : { width: 390, height: 844 };
const AUDIT = readFileSync('tools/phone_fit_audit.browser.js', 'utf8');
const ledger = JSON.parse(readFileSync('w4_confusions.json', 'utf8'));
const ENTRY = Object.fromEntries((ledger.entries || []).map((e) => [e.id, e]));
const atPath = (h) => new RegExp('/' + h.split('.').join('[.]') + '(?:[?#]|$)');

// the cast: a WORKER of the row's own hive (the wave-3 rule) - username = the e-mail's local part, seed password
const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8', timeout: 30000 }).trim(); } catch (e) { return ''; } };
const CAST = {};
for (const line of psql("select h.name||'|'||m.worker_name||'|'||m.role||'|'||coalesce(u.email,'') from hives h join hive_members m on m.hive_id = h.id left join auth.users u on u.id = m.auth_uid where m.status = 'active' order by h.name, m.role, m.worker_name").split('\n')) {
  const [hive, worker, role, email] = line.split('|');
  if (!hive || !email) continue;
  CAST[hive] = CAST[hive] || {};
  if (role === 'worker' && !CAST[hive].worker) CAST[hive].worker = { name: worker, email, user: email.split('@')[0] };
}

const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
let rows = reg.trajectories.filter((t) => (t.w4 || {}).kind === 'confusion' && `${(t.axis || {}).device} ${(t.axis || {}).language}` === AXIS && (FORCE || !['locking', 'locked'].includes(t.status)));
if (ONLY.length) rows = rows.filter((t) => ONLY.includes(t.w4.confusion));
if (IDS.length) rows = rows.filter((t) => IDS.includes(t.id));
if (LIMIT) rows = rows.slice(0, LIMIT);
if (!rows.length) { console.log(`PASS w4-confusions - no open confusion row on axis "${AXIS}" matches (nothing to walk)`); process.exit(0); }

// ── helpers that run inside the page ──────────────────────────────────────────────────────────────────────────────
const AUDIT_STEP = (s) => { if (!window.__W4_AUDIT) return { step: s, error: 'audit not installed', findings: 0 }; const r = window.__W4_AUDIT(null, { step: s }); return { step: s, vw: innerWidth, findings: r.findings || 0, occlusion: (r.occlusion || []).slice(0, 4), overflowEl: (r.overflowEl || []).slice(0, 2), wrapped: (r.wrapped || []).slice(0, 2), ambiguity: (r.ambiguity || []).slice(0, 3), unactionable: (r.unactionable || []).slice(0, 3), confusions: r.confusions || 0 }; };
const READ = () => ({ url: location.pathname.split('/').pop(), worker: localStorage.getItem('wh_last_worker'), chars: (document.body.innerText || '').replace(/\s+/g, ' ').trim().length });
// is the control the element at its OWN visible centre (scrolled into view first - the walk's own rule)?
const REACH = (sel) => { const e = typeof sel === 'string' ? document.querySelector(sel) : sel; if (!e) return { exists: false }; e.scrollIntoView({ block: 'center', inline: 'nearest' }); const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return { exists: true, shown: false }; const t = document.elementFromPoint(Math.min(innerWidth - 1, Math.max(0, r.left + r.width / 2)), Math.min(innerHeight - 1, Math.max(0, r.top + r.height / 2))); const ok = !!t && (t === e || e.contains(t)); return { exists: true, shown: true, ok, hit: t ? (t.id ? '#' + t.id : t.tagName.toLowerCase() + (typeof t.className === 'string' && t.className ? '.' + t.className.trim().split(/\s+/)[0] : '')) : null, rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)] }; };
const BY_TEXT = (re) => [...document.querySelectorAll('a, button')].find((e) => re.test((e.textContent || '').replace(/\s+/g, ' ').trim()) && e.getBoundingClientRect().width > 0) || null;

// ── the predicates: each returns { ok, detail } and may push problems ─────────────────────────────────────────────
const PRED = {
  // stage 'wall' runs on index.html?signin=1 with the modal open, BEFORE the sign-in
  C1: { stage: 'wall', run: async (page) => page.evaluate(() => {
    const modal = document.getElementById('signin-modal');
    const outside = [...document.querySelectorAll('a, button')].filter((e) => /^sign in$/i.test((e.textContent || '').replace(/\s+/g, ' ').trim()) && !(modal && modal.contains(e)));
    const hittable = outside.filter((e) => { const r = e.getBoundingClientRect(); if (r.width < 2) return false; const t = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return t === e || e.contains(t); });
    return { ok: hittable.length === 0, detail: `${outside.length} "Sign In" control(s) outside the dialog, ${hittable.length} still hittable while it is open` };
  }) },
  C2: { stage: 'signin', run: null },   // lived inside the sign-in step (a 10 s slow login; the 8 s hint must appear)
  C3: { stage: 'signin', run: null },   // lived inside the sign-in step (one 503 "name resolution failed"; the person must read the plain outage sentence)
  C13: { stage: 'wall', run: async (page) => {
    await page.waitForSelector('#wh-consent', { state: 'visible', timeout: 8000 }).catch(() => {});
    return page.evaluate(() => {
      const REACH = window.__W4_REACH; const BY = (re) => [...document.querySelectorAll('a, button')].find((e) => re.test((e.textContent || '').replace(/\s+/g, ' ').trim()) && e.getBoundingClientRect().width > 0) || null;
      const consent = document.getElementById('wh-consent'); const cs = consent ? getComputedStyle(consent) : null;
      const shown = !!consent && cs.display !== 'none' && consent.getBoundingClientRect().height > 0;
      const checks = [['forgot-password', BY(/forgot your password|nakalimutan/i)], ['sso', document.getElementById('si-sso-btn')], ['create-account', BY(/create one for free|gumawa/i)]];
      const fab = document.getElementById('wh-hub-fab'); if (fab && fab.getBoundingClientRect().width > 0 && getComputedStyle(fab).visibility !== 'hidden') checks.push(['hub-fab', fab]);
      const bad = []; for (const [n, el] of checks) { if (!el) { bad.push(n + ': not on this wall'); continue; } const r = REACH(el); if (!r.ok) bad.push(`${n} covered by ${r.hit}`); }
      return { ok: shown && bad.length === 0, detail: (shown ? `consent card shown (${cs.position}); ` : 'consent card NOT shown (nothing to live); ') + (bad.length ? bad.join(' | ') : `${checks.length} sign-in controls each the element at their own centre`) };
    });
  } },
  C15: { stage: 'wall', run: async (page) => page.evaluate(() => {
    const REACH = window.__W4_REACH;
    if (typeof window._whShowNotice !== 'function') return { ok: false, detail: '_whShowNotice is not on this page' };
    window._whShowNotice('wh-w4-c15', 'Could not load your data. Check your connection and try again.', '88px');
    const n = document.getElementById('wh-w4-c15'); const close = n && n.querySelector('.wh-notice-close'); const cr = close && close.getBoundingClientRect();
    if (!close) return { ok: false, detail: 'the notice has no dismiss control (.wh-notice-close)' };
    if (cr.width < 44 || cr.height < 44) return { ok: false, detail: `dismiss control ${Math.round(cr.width)}x${Math.round(cr.height)} < 44` };
    const before = REACH('#si-sso-btn'); close.click();
    const gone = !document.getElementById('wh-w4-c15'); const after = REACH('#si-sso-btn');
    return { ok: gone && after.ok, detail: `notice triggered through the shared component (the path a failed read takes); SSO ${before.ok ? 'not covered' : 'covered by ' + before.hit} while up; dismiss ${gone ? 'removed it' : 'left it'}; SSO ${after.ok ? 'reachable' : 'still covered by ' + after.hit} after` };
  }) },
  // stage 'page' runs on the confusion's page after sign-in
  // C4 is the STORY's search: a tool that exists under All ("logbook") typed inside a view that hides it. A nonsense
  // term has no hidden match, so the generic "No tools match" is the right answer there (the first run graded that
  // and called it a fault - the predicate was wrong, not the hub). Walk the scoped views until one hides Logbook.
  C4: { stage: 'page', run: async (page, ctx) => {
    await ctx.openHub();
    const modes = await page.$$('#wh-hub-mode .wh-hub-mode-btn:not([data-mode="all"])');
    if (!modes.length) return { ok: false, detail: 'no scoped mode button in the hub' };
    const seen = [];
    for (const m of modes) {
      await m.click({ timeout: 6000 }).catch(() => {}); await page.waitForTimeout(350);
      await page.fill('#wh-hub-search', '', { timeout: 6000 }).catch(() => {});
      await page.fill('#wh-hub-search', 'logbook', { timeout: 6000 }).catch(() => {}); await page.waitForTimeout(500);
      const r = await page.evaluate(() => { const hits = [...document.querySelectorAll('#wh-hub-tiles .wh-hub-tile')].filter((x) => x.checkVisibility && x.checkVisibility()).length; const n = document.querySelector('#wh-hub-no-results'); const shown = !!n && n.checkVisibility && n.checkVisibility(); const txt = (n && n.textContent || '').replace(/\s+/g, ' ').trim(); const offer = n && [...n.querySelectorAll('button, a')].find((b) => /show all|lahat/i.test(b.textContent || '')); const mode = document.querySelector('#wh-hub-mode .wh-hub-mode-btn[aria-selected="true"]'); const view = (mode && mode.textContent || '').replace(/[^\w\s]/g, '').trim(); return { hits, shown, txt, offer: !!offer, view }; });
      seen.push(`${r.view}:${r.hits}`);
      if (r.hits === 0) {
        const names = r.shown && r.view && r.txt.toLowerCase().includes(r.view.toLowerCase().slice(0, 5));
        return { ok: r.shown && r.offer && names, detail: `"logbook" in the ${r.view} view: ${r.shown ? `no-results reads "${r.txt.slice(0, 80)}"` : 'no-results state did not show'} · offer ${r.offer ? 'present' : 'ABSENT'} · view ${names ? 'named' : 'NOT named'}` };
      }
    }
    await page.fill('#wh-hub-search', '', { timeout: 6000 }).catch(() => {});
    return { ok: true, detail: `Logbook is visible in every scoped view (${seen.join(', ')}) - nothing is hidden, the scoped no-results state cannot arise on this page` };
  } },
  C5: { stage: 'page', run: async (page, ctx) => { await ctx.closeAll(); await page.click('#wh-hub-fab', { timeout: 8000 }).catch(() => {}); await page.waitForTimeout(700); await page.keyboard.press('Escape'); await page.waitForTimeout(700); const f = await page.evaluate(() => { const a = document.activeElement; return a ? (a.id || a.tagName.toLowerCase()) : null; }); return { ok: f === 'wh-hub-fab', detail: `focus after Escape: ${f}` }; } },
  C6: { stage: 'page', run: async (page, ctx) => { await ctx.openHub(); return page.evaluate(() => { const g = document.getElementById('wh-hub-global-search'); const s = document.getElementById('wh-hub-search'); const gt = (g && (g.textContent + ' ' + (g.getAttribute('aria-label') || '')) || '').replace(/\s+/g, ' ').trim(); const ph = (s && (s.getAttribute('placeholder') || '') || ''); const badge = /⌘|ctrl/i.test(gt); const filterWord = /filter/i.test(ph); return { ok: !!g && !!s && !badge && filterWord, detail: `launcher "${gt.slice(0, 40)}" ${badge ? 'STILL carries a shortcut badge' : 'no shortcut badge'} · filter placeholder "${ph}"` }; }); } },
  C7: { stage: 'page', run: async (page, ctx) => { const errs = []; const on = (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 120)); }; page.on('console', on); const onErr = (e) => errs.push(String(e.message).slice(0, 120)); page.on('pageerror', onErr); await ctx.openHub(); for (const m of await page.$$('#wh-hub-mode .wh-hub-mode-btn')) { await m.click({ timeout: 6000 }).catch(() => {}); await page.waitForTimeout(300); } page.off('console', on); page.off('pageerror', onErr); const bad = errs.filter((e) => /is not defined|ReferenceError|TypeError/.test(e)); return { ok: bad.length === 0, detail: bad.length ? bad.slice(0, 2).join(' | ') : `${errs.length} console error(s) on the mode clicks, none a script fault` }; } },
  // C9: the page-guide chip (#wh-guide-link, fixed, z 60) either stands down or covers no visible control on the page
  C9: { stage: 'page', run: async (page) => { await page.waitForTimeout(1200); return page.evaluate(() => { const chip = document.getElementById('wh-guide-link'); const shown = !!chip && getComputedStyle(chip).display !== 'none' && getComputedStyle(chip).visibility !== 'hidden' && chip.getBoundingClientRect().width > 0; if (!shown) return { ok: true, detail: chip ? 'the page-guide chip stood down (hidden) on this page' : 'no page-guide chip on this page' }; const c = chip.getBoundingClientRect(); const bad = []; let checked = 0; for (const el of document.querySelectorAll('a[href], button, [role="button"], input, select, textarea, summary')) { if (chip.contains(el)) continue; const r = el.getBoundingClientRect(); if (r.width < 2 || r.height < 2) continue; /* a control inside CLOSED chrome (the hub panel is visibility:hidden when shut) keeps its box but is not hit-testable, so elementFromPoint at its centre returns whatever is visible there - the chip - and reads as a false cover; ask the browser whether the control is actually visible (visibility + opacity, ancestors included) */ if (el.checkVisibility && !el.checkVisibility({ visibilityProperty: true, opacityProperty: true })) continue; const cx = r.left + r.width / 2, cy = r.top + r.height / 2; if (cx < c.left || cx > c.right || cy < c.top || cy > c.bottom) continue; checked++; const t = document.elementFromPoint(cx, cy); if (t && (t === chip || chip.contains(t))) bad.push(((el.getAttribute('aria-label') || el.textContent || el.tagName).replace(/\s+/g, ' ').trim().slice(0, 28)) + ` @${Math.round(r.left)},${Math.round(r.top)}`); } return { ok: bad.length === 0, detail: bad.length ? `the chip @${Math.round(c.left)},${Math.round(c.top)} ${Math.round(c.width)}x${Math.round(c.height)} covers ${bad.slice(0, 3).join(' | ')}` : `the chip @${Math.round(c.left)},${Math.round(c.top)} ${Math.round(c.width)}x${Math.round(c.height)} shown; ${checked} control(s) share its band and each is the element at its own centre` }; }); } },
  // C18: community's own post FAB never sits on a filter chip; C19: analytics-report's tabs never wrap
  C18: { stage: 'page', on: ['community.html'], run: async (page) => page.evaluate(() => { const REACH = window.__W4_REACH; const chips = [...document.querySelectorAll('#filter-chips .filter-chip')].filter((c) => c.checkVisibility && c.checkVisibility()); if (!chips.length) return { ok: false, detail: 'no visible filter chip on this page' }; const fab = document.getElementById('fab-post'); const bad = []; for (const c of chips) { const r = REACH(c); if (!r.ok) bad.push(`"${(c.textContent || '').trim().slice(0, 14)}" @${r.rect ? r.rect.slice(0, 2).join(',') : '?'} covered by ${r.hit}`); } return { ok: bad.length === 0, detail: bad.length ? bad.slice(0, 3).join(' | ') : `${chips.length} filter chips each the element at their own centre (post FAB ${fab ? 'at ' + Math.round(fab.getBoundingClientRect().left) + ',' + Math.round(fab.getBoundingClientRect().top) : 'absent'})` }; }) },
  C19: { stage: 'page', on: ['analytics-report.html'], run: async (page) => page.evaluate(() => { const tabs = [...document.querySelectorAll('.wh-reports-tabs [role="tab"]')].filter((t) => t.getBoundingClientRect().width > 0); if (!tabs.length) return { ok: false, detail: 'no report tabs on this page' }; const bad = []; for (const t of tabs) { const s = t.querySelector('span') || t; const lines = Math.round(s.getBoundingClientRect().height / Math.max(1, parseFloat(getComputedStyle(s).lineHeight) || parseFloat(getComputedStyle(s).fontSize) * 1.3)); const rects = s.getClientRects().length; if (lines > 1 || rects > 1) bad.push(`"${(t.textContent || '').trim().slice(0, 20)}" ${lines} line(s), ${rects} box(es)`); } return { ok: bad.length === 0, detail: bad.length ? bad.join(' | ') : `${tabs.length} tabs, each one line (strip scrollWidth ${document.querySelector('.wh-reports-tabs').scrollWidth} in a ${innerWidth}px viewport)` }; }) },
  // C20: report-sender's Install button inside the viewport; C21/C22: one-line labels on resume's upload buttons and voice-journal's Speak again
  C20: { stage: 'page', on: ['report-sender.html'], run: async (page) => page.evaluate(() => { const b = document.getElementById('install-icon-btn'); if (!b) return { ok: false, detail: 'no #install-icon-btn on this page' }; const r = b.getBoundingClientRect(); if (r.width === 0) return { ok: true, detail: 'the Install button is hidden (app installed) - nothing to overflow' }; const p = b.parentElement.getBoundingClientRect(); const ok = r.right <= innerWidth + 0.5 && r.right <= p.right + 0.5 && document.documentElement.scrollWidth <= innerWidth; return { ok, detail: `Install spans ${Math.round(r.left)}..${Math.round(r.right)} in a ${innerWidth}px viewport (parent right ${Math.round(p.right)}); page scrollWidth ${document.documentElement.scrollWidth}` }; }) },
  C21: { stage: 'page', on: ['resume.html'], run: async (page) => page.evaluate(() => { const one = (el) => { /* measure the TEXT's line boxes (a Range over the contents), never the control's height: a 44px min-height button divided by its line-height read as "two lines" with nowrap in force */ const cs = getComputedStyle(el); const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.3; const rg = document.createRange(); rg.selectNodeContents(el); return rg.getBoundingClientRect().height <= lh * 1.5; }; const bad = []; let n = 0; for (const id of ['btn-photo', 'btn-file']) { const b = document.getElementById(id); if (!b || b.getBoundingClientRect().width === 0) continue; n++; if (!one(b)) bad.push(`#${id} "${(b.textContent || '').trim()}" wraps at ${Math.round(b.getBoundingClientRect().width)}px`); } if (!n) return { ok: false, detail: 'upload buttons not rendered' }; return { ok: bad.length === 0, detail: bad.length ? bad.join(' | ') : `${n} upload buttons, each one line (widths ${['btn-photo', 'btn-file'].map((id) => Math.round((document.getElementById(id) || { getBoundingClientRect: () => ({ width: 0 }) }).getBoundingClientRect().width)).join('/')}px)` }; }) },
  C22: { stage: 'page', on: ['voice-journal.html'], run: async (page) => { await page.waitForTimeout(2500); return page.evaluate(() => { const one = (el) => { /* measure the TEXT's line boxes (a Range over the contents), never the control's height: a 44px min-height button divided by its line-height read as "two lines" with nowrap in force */ const cs = getComputedStyle(el); const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.3; const rg = document.createRange(); rg.selectNodeContents(el); return rg.getBoundingClientRect().height <= lh * 1.5; }; const btns = [...document.querySelectorAll('.speak-btn')].filter((b) => b.checkVisibility && b.checkVisibility()); if (!btns.length) return { ok: false, detail: 'no visible "Speak again" button (this worker has no journal history to replay) - C22 not exercisable for this cast' }; const bad = btns.filter((b) => !one(b)).map((b) => `"${(b.textContent || '').trim()}" wraps at ${Math.round(b.getBoundingClientRect().width)}px`); return { ok: bad.length === 0, detail: bad.length ? bad.slice(0, 2).join(' | ') : `${btns.length} Speak-again button(s), each one line (${Math.round(btns[0].getBoundingClientRect().width)}px wide)` }; }); } },
  C23: { stage: 'page', on: ['analytics-report.html'], run: async (page) => page.evaluate(() => { const b = document.querySelector('.ar-badge'); if (!b || b.getBoundingClientRect().width === 0) return { ok: false, detail: 'no visible .ar-badge on this page' }; const r = b.getBoundingClientRect(); const p = b.parentElement.getBoundingClientRect(); const ok = r.right <= innerWidth + 0.5 && r.right <= p.right + 0.5 && document.documentElement.scrollWidth <= innerWidth; return { ok, detail: `BETA badge spans ${Math.round(r.left)}..${Math.round(r.right)} in a ${innerWidth}px viewport (header right ${Math.round(p.right)}); page scrollWidth ${document.documentElement.scrollWidth}` }; }) },
  // C27: the guide's ?calc=<slug> lands on that calculator (the page navigates itself to the deep link, as the guide's CTA does)
  C27: { stage: 'page', on: ['engineering-design.html'], run: async (page) => { await page.goto(`${ORIGIN}/engineering-design.html?calc=ahu-sizing`, { waitUntil: 'load', timeout: 60000 }).catch(() => {}); await page.waitForTimeout(5000); return page.evaluate(() => { const sel = document.querySelector('.calc-card.selected[data-id]'); const id = sel ? sel.dataset.id : null; const btn = document.getElementById('calc-btn'); const r = btn ? btn.getBoundingClientRect() : null; return { ok: !!id && /ahu/i.test(id), detail: id ? `?calc=ahu-sizing selected "${id}"; Run button ${r && r.top >= 0 && r.bottom <= innerHeight ? 'in view' : 'out of view'}` : 'no calculator selected after ?calc=ahu-sizing (the grid, nothing chosen)' }; }); } },
  // C28: a notice never covers the page-guide chip - the update notice is raised through the shared transport on the
  // signed-in host, the chip paints on its own schedule, and after the notice's re-measure both the chip's link and its
  // Dismiss are the element at their own centre and the notice's bottom edge sits above the chip's top.
  C28: { stage: 'page', on: ['achievements.html'], run: async (page) => {
    await page.waitForSelector('#wh-guide-link', { state: 'visible', timeout: 15000 }).catch(() => {});
    await page.evaluate(() => { if (typeof window._whShowNotice === 'function') window._whShowNotice('wh-update-notice', 'A new version of WorkHive is ready. Reload when you are at a good stopping point.', '160px'); });
    await page.waitForTimeout(1900);
    return page.evaluate(() => {
      const REACH = window.__W4_REACH;
      const chip = document.getElementById('wh-guide-link');
      if (!chip || chip.getBoundingClientRect().width === 0) return { ok: false, detail: 'no page-guide chip painted on this page (nothing to measure)' };
      const n = document.getElementById('wh-update-notice');
      if (!n) return { ok: false, detail: 'the notice did not render through _whShowNotice' };
      const a = REACH('#wh-guide-link a'); const b = REACH('#wh-guide-link button');
      const nr = n.getBoundingClientRect(); const cr = chip.getBoundingClientRect();
      const clear = nr.bottom <= cr.top + 1 || nr.top >= cr.bottom - 1;
      return { ok: a.ok && b.ok && clear, detail: `notice ${Math.round(nr.top)}..${Math.round(nr.bottom)} vs chip ${Math.round(cr.top)}..${Math.round(cr.bottom)}; guide link ${a.ok ? 'clear' : 'covered by ' + a.hit}; dismiss ${b.ok ? 'clear' : 'covered by ' + b.hit}` };
    });
  } },
  // C24: the wall shows the handle it will actually use when normalisation changes what was typed
  C24: { stage: 'wall', run: async (page) => { await page.fill('#si-username', 'jeepney.oscarph', { timeout: 8000 }).catch(() => {}); await page.waitForTimeout(300); const r = await page.evaluate(() => { const h = document.getElementById('si-username-hint'); const shown = !!h && !h.classList.contains('hidden') && h.getBoundingClientRect().height > 0; return { shown, text: h ? (h.textContent || '').trim() : '' }; }); await page.fill('#si-username', '', { timeout: 8000 }).catch(() => {}); return { ok: r.shown && /jeepneyoscarph/.test(r.text), detail: r.shown ? `typing "jeepney.oscarph" shows "${r.text.slice(0, 60)}"` : 'typing a dotted username shows no hint of the handle the wall will send' }; } },
  // C25: on the SIGNED-IN landing page the consent card is a region in the flow and the hub FAB is the element at its own centre
  C25: { stage: 'page', on: ['achievements.html', 'hive.html'], run: async (page) => { await page.goto(`${ORIGIN}/index.html`, { waitUntil: 'load', timeout: 60000 }).catch(() => {}); await page.waitForTimeout(5000); return page.evaluate(() => { const REACH = window.__W4_REACH; const c = document.getElementById('wh-consent'); const cShown = !!c && !c.hidden && c.getBoundingClientRect().height > 0; const role = c ? c.getAttribute('role') : null; const pos = c ? getComputedStyle(c).position : null; const fab = document.getElementById('wh-hub-fab'); if (!fab) return { ok: false, detail: 'no hub FAB on the signed-in landing page' }; const fabVis = getComputedStyle(fab).visibility !== 'hidden' && fab.getBoundingClientRect().width > 0; const r = REACH(fab); const ok = fabVis && r.ok && role !== 'dialog' && (!cShown || pos === 'static'); return { ok, detail: `consent card ${cShown ? 'shown, role=' + role + ', ' + pos : 'not shown'}; hub FAB ${fabVis ? (r.ok ? 'reachable at its own centre' : 'covered by ' + r.hit) : 'HIDDEN (stood down)'}` }; }); } },
  // C26: shift-brain's action row wraps and its press controls keep one-line labels (measured for a supervisor; the rule for a worker)
  C26: { stage: 'page', on: ['shift-brain.html'], run: async (page) => page.evaluate(() => { const row = document.querySelector('.actions-row'); const btn = document.getElementById('publish-btn'); if (!row || !btn) return { ok: false, detail: 'no .actions-row / #publish-btn on this page' }; const rs = getComputedStyle(row), bs = getComputedStyle(btn); const rule = rs.flexWrap === 'wrap' && bs.whiteSpace === 'nowrap' && parseFloat(bs.flexShrink) === 0; const shown = row.getBoundingClientRect().height > 0 && getComputedStyle(row).display !== 'none'; if (shown) { const cs = bs; const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.3; const rg = document.createRange(); rg.selectNodeContents(btn); const one = rg.getBoundingClientRect().height <= lh * 1.5; return { ok: rule && one, detail: `supervisor row shown: "Publish to crew" ${one ? 'one line' : 'WRAPS'} at ${Math.round(btn.getBoundingClientRect().width)}px; row wraps ${rs.flexWrap}, nowrap ${bs.whiteSpace}, shrink ${bs.flexShrink}` }; } return { ok: rule, detail: `the action row is hidden for this cast (a worker); the rule is ${rule ? 'in force' : 'MISSING'} (row flex-wrap ${rs.flexWrap}, button white-space ${bs.whiteSpace}, flex-shrink ${bs.flexShrink})` }; }) },
  C16: { stage: 'page', on: ['hive.html'], run: async (page) => page.evaluate(() => { const REACH = window.__W4_REACH; const sn = [...document.querySelectorAll('.ss-snooze')].filter((e) => e.getBoundingClientRect().width > 0); if (!sn.length) return { ok: false, detail: 'no visible tile snooze on this page (tiles snoozed or not rendered) - C16 not exercisable here' }; const fab = document.getElementById('wh-hub-fab'); const fr = fab ? fab.getBoundingClientRect() : null; const bad = []; for (const e of sn) { const r = REACH(e); const q = e.getBoundingClientRect(); const inFabColumn = innerWidth <= 360 && fr && q.right > fr.left - 4; /* the step-in rule applies below 360px only; at 390 the right tile's corner shares the FAB's x-range by design and must simply be reachable */ if (!r.ok || inFabColumn) bad.push(`snooze @${Math.round(q.left)},${Math.round(q.top)} ${r.ok ? 'reachable but' : 'covered by ' + r.hit + ','} ${inFabColumn ? 'inside the FAB column (right ' + Math.round(q.right) + ' > fab left ' + Math.round(fr.left) + ')' : 'clear of the FAB column'}`); } return { ok: bad.length === 0, detail: bad.length ? bad.slice(0, 2).join(' | ') : `${sn.length} tile snooze control(s), each reachable and clear of the FAB column (fab left ${fr ? Math.round(fr.left) : '?'})` }; }) },
  C17: { stage: 'page', on: ['assistant.html'], run: async (page) => page.evaluate(() => { const b = document.querySelector('button[data-i="newchat"]'); if (!b || b.getBoundingClientRect().width === 0) return { ok: false, detail: 'no visible New Chat button (chat screen not shown)' }; const r = b.getBoundingClientRect(); const p = b.parentElement.getBoundingClientRect(); const inside = r.right <= innerWidth + 0.5 && r.right <= p.right + 0.5 && r.left >= -0.5; const sx = document.documentElement.scrollWidth <= innerWidth; return { ok: inside && sx, detail: `New Chat spans ${Math.round(r.left)}..${Math.round(r.right)} in a ${innerWidth}px viewport (parent right ${Math.round(p.right)}); page scrollWidth ${document.documentElement.scrollWidth}` }; }) },
  C8: { stage: 'page', on: ['hive.html'], run: async (page) => page.evaluate(() => { const names = [...document.querySelectorAll('summary')].filter((s) => s.getBoundingClientRect().width > 0).map((s) => (s.getAttribute('aria-label') || s.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase()); const dup = names.filter((n, i) => names.indexOf(n) !== i); return { ok: names.length > 0 && dup.length === 0, detail: names.length ? `${names.length} disclosure(s): ${names.map((n) => '"' + n.slice(0, 32) + '"').join(', ')}${dup.length ? ' - DUPLICATE name ' + JSON.stringify(dup[0]) : ''}` : 'no visible <summary> on this page' }; }) },
  // C10 needs a page that CARRIES the wayfinding pill (a page with no back affordance of its own): the confusion was
  // found on ai-quality and alert-hub; achievements/assistant own their back and get no pill.
  C10: { stage: 'page', on: ['skillmatrix.html', 'ai-quality.html', 'alert-hub.html'], run: async (page, ctx) => { await ctx.context.setOffline(true); await page.waitForSelector('.wh-offline-banner', { state: 'visible', timeout: 8000 }).catch(() => {}); await page.waitForFunction(() => { const b = document.querySelector('.wh-offline-banner'); return !!b && b.getBoundingClientRect().height >= 20; }, null, { timeout: 6000 }).catch(() => {}); await page.waitForTimeout(500); /* the banner animates its height: measure it SETTLED, not mid-transition */ const r = await page.evaluate(() => { const b = document.querySelector('.wh-offline-banner'); const p = document.querySelector('#wh-wayfinding .wf-back'); if (!b || b.getBoundingClientRect().height === 0) return { ok: false, detail: 'the offline banner did not show' }; if (!p) return { ok: false, detail: 'no wayfinding pill on this page - C10 is not exercisable here' }; const bh = b.getBoundingClientRect().bottom, pt = p.getBoundingClientRect().top; const t = document.elementFromPoint(p.getBoundingClientRect().left + 10, pt + 10); return { ok: pt >= bh - 1 && (t === p || p.contains(t)), detail: `banner bottom ${Math.round(bh)}, pill top ${Math.round(pt)}, at the pill sits ${t ? (t.className || t.tagName) : null}` }; }); await ctx.context.setOffline(false); await page.waitForTimeout(800); return r; } },
  C11: { stage: 'page', on: ['assistant.html'], run: async (page) => page.evaluate(() => { const REACH = window.__W4_REACH; const pill = document.getElementById('wh-wayfinding'); const pillShown = !!pill && pill.getBoundingClientRect().height > 0 && getComputedStyle(pill).display !== 'none'; const own = [...document.querySelectorAll('button.back-link, .back-link')].find((b) => b.getBoundingClientRect().width > 0 && b.getBoundingClientRect().height > 0); if (!own) return { ok: false, detail: 'the page shows no VISIBLE owned back control (.back-link) on the screen it landed on' }; const r = REACH(own); return { ok: !pillShown && r.ok, detail: `wayfinding pill ${pillShown ? 'INJECTED' : 'absent'}; own back "${(own.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 20)}" ${r.ok ? 'reachable at its own centre' : 'covered by ' + r.hit}` }; }) },
  C12: { stage: 'page', on: ['hive.html'], run: async (page, ctx) => { await ctx.context.setOffline(true); await page.waitForSelector('.wh-offline-banner', { state: 'visible', timeout: 8000 }).catch(() => {}); await page.waitForFunction(() => { const b = document.querySelector('.wh-offline-banner'); return !!b && b.getBoundingClientRect().height >= 20; }, null, { timeout: 6000 }).catch(() => {}); await page.waitForTimeout(500); /* the banner animates its height: measure it SETTLED, not mid-transition */ const r = await page.evaluate(() => { const REACH = window.__W4_REACH; const b = document.querySelector('.wh-offline-banner'); if (!b || b.getBoundingClientRect().height === 0) return { ok: false, detail: 'the offline banner did not show' }; const nav = document.querySelector('nav.fixed, header.fixed'); if (!nav) return { ok: false, detail: 'no fixed nav/header on this page - C12 is not exercisable here' }; const link = nav.querySelector('a[data-wh-back], a, button'); if (!link) return { ok: false, detail: 'the fixed nav has no control' }; const r = REACH(link); const nt = nav.getBoundingClientRect().top, bh = b.getBoundingClientRect().bottom; return { ok: r.ok && nt >= bh - 1, detail: `banner bottom ${Math.round(bh)}, fixed nav top ${Math.round(nt)}; its first control ${r.ok ? 'reachable' : 'covered by ' + r.hit}` }; }); await ctx.context.setOffline(false); await page.waitForTimeout(800); return r; } },
};

const browser = await chromium.launch();
const results = [];
const freeGb = () => os.freemem() / 1e9;
for (const t of rows) {
  const cid = t.w4.confusion; const e = ENTRY[cid] || {}; const pred = PRED[cid];
  const hive = (t.journey || {}).vertical; const who = hive && CAST[hive] ? CAST[hive].worker : null;
  // ★A CONFUSION IS LIVED WHERE IT LIVES (2026-09-14, first full run): C12 (hive's fixed nav under the offline banner),
  // C16 (hive's tile snooze) and C17 (assistant's chat header) were graded on skillmatrix - the first non-hub page of
  // the row's path - and read "not exercisable here". A predicate names the page(s) that carry its control (`on`);
  // the first of them already on the path is the target, else the first is appended as an extra step.
  const pref = (pred && pred.on) || [];
  const path = (t.pages && t.pages.length ? t.pages : ['index.html']).slice();
  if (path[0] !== 'index.html') path.unshift('index.html');
  const target = pref.find((p) => path.includes(p)) || pref[0] || e.host
    || (e.page && e.page.endsWith('.html') ? e.page : path[path.length - 1] !== 'index.html' ? path[path.length - 1] : 'achievements.html');
  if (!path.includes(target)) path.push(target);
  const problems = []; const steps = []; let predicate = null;
  let waited = 0; while (freeGb() < 0.7 && waited < 120) { await new Promise((r) => setTimeout(r, 15000)); waited += 15; }
  const context = await browser.newContext({ viewport, isMobile: true, hasTouch: true, deviceScaleFactor: 1, locale: lang === 'fil' ? 'fil-PH' : 'en-PH', serviceWorkers: 'block' });
  const page = await context.newPage();
  await page.addInitScript({ content: AUDIT });
  await page.addInitScript({ content: 'window.__W4_REACH = ' + REACH.toString() + ';' });   // CDP-injected: no page CSP can refuse it
  if (lang === 'fil') await page.addInitScript(() => { try { localStorage.setItem('wh_lang', 'fil'); } catch (e) { void e; } });
  const ctx = { context, openHub: async () => { const shown = await page.evaluate(() => { const p = document.querySelector('#wh-hub-panel'); return !!p && getComputedStyle(p).visibility !== 'hidden' && p.getBoundingClientRect().height > 0; }); if (shown) return; const ok = await page.click('#wh-hub-fab', { timeout: 8000 }).then(() => true).catch(() => false); if (!ok) await page.keyboard.press('Control+k').catch(() => {}); await page.waitForTimeout(700); }, closeAll: async () => { await page.keyboard.press('Escape'); await page.waitForTimeout(250); await page.keyboard.press('Escape'); await page.waitForTimeout(250); } };
  const audit = (s) => page.evaluate(AUDIT_STEP, s).catch(() => ({ step: s, error: 'audit failed', findings: 0 }));
  // ★AT REST MEANS AT REST (2026-09-14): a predicate's reach probe scrolls controls into view and left the page
  // scrolled, so the step's overlap audit ran at that position and read a post's reply button under the hub FAB on
  // community at 320 - a state no person had reached. Every step audit starts from the top, like the nav-hub walk.
  const step = async (pageName, extra) => { await page.evaluate(() => window.scrollTo(0, 0)).catch(() => {}); await page.waitForTimeout(300); const r = await page.evaluate(READ).catch(() => ({ chars: 0 })); const a = await audit(pageName); steps.push(Object.assign({ page: pageName, chars: r.chars, identityKept: !!r.worker, fit: { findings: a.findings || 0, occlusion: a.occlusion || [], overflowEl: a.overflowEl || [], wrapped: a.wrapped || [], confusions: a.confusions || 0 } }, extra || {})); if (r.chars < 120) problems.push(`${pageName}: arrived with ${r.chars} chars`); if ((a.occlusion || []).length) problems.push(`overlap at "${pageName}": ` + a.occlusion.slice(0, 2).join(' | ')); return r; };
  try {
    // 1. the wall, as the person arrives at it
    const next = path[1] || target;
    await page.goto(`${ORIGIN}/index.html?signin=1&return=${next}`, { waitUntil: 'load', timeout: 60000 });
    await page.waitForSelector('#si-username', { state: 'visible', timeout: 45000 }).catch(() => {});
    if (pred && pred.stage === 'wall') { predicate = await pred.run(page, ctx).catch((err) => ({ ok: false, detail: 'predicate threw: ' + String(err.message).split('\n')[0] })); }
    await step('index.html');
    // 2. sign in (C2 lives a slow login here; C3 lives one gateway outage here)
    if (who && await page.locator('#si-username').isVisible().catch(() => false)) {
      if (cid === 'C2') await page.route('**/functions/v1/login', async (route) => { await new Promise((r) => setTimeout(r, 10000)); await route.continue(); });
      if (cid === 'C3') { let once = false; await page.route('**/functions/v1/login', async (route) => { if (!once && route.request().method() === 'POST') { once = true; await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ message: 'name resolution failed' }) }); } else await route.continue(); }); }
      await page.fill('#si-username', who.user, { timeout: 8000 }); await page.fill('#si-password', 'test1234', { timeout: 8000 });
      await page.click('#si-btn', { timeout: 10000 }).catch(async () => { await page.press('#si-password', 'Enter').catch(() => {}); });
      if (cid === 'C2') { await page.waitForTimeout(9500); const hint = await page.evaluate(() => { const e = document.getElementById('si-error'); return e && !e.classList.contains('hidden') ? (e.textContent || '').trim() : ''; }); predicate = { ok: /still signing in|nagsa-sign in pa/i.test(hint), detail: hint ? `at 9.5 s the wall said "${hint.slice(0, 80)}"` : 'at 9.5 s the wall said nothing' }; }
      if (cid === 'C3') { await page.waitForFunction(() => { const e = document.getElementById('si-error'); return e && !e.classList.contains('hidden') && (e.textContent || '').trim().length > 0; }, null, { timeout: 15000 }).catch(() => {}); const said = await page.evaluate(() => { const e = document.getElementById('si-error'); return e ? (e.textContent || '').trim() : ''; }); predicate = { ok: !/name resolution|upstream|gateway/i.test(said) && /temporarily unavailable|pansamantala|try again/i.test(said), detail: `after a 503 "name resolution failed" the wall said "${said.slice(0, 90)}"` }; await page.unroute('**/functions/v1/login'); await page.click('#si-btn', { timeout: 10000 }).catch(() => {}); }
      await page.waitForURL(atPath(next), { timeout: 30000 }).catch(async () => { problems.push('sign-in did not reach ' + next + ' in 30s: ' + await page.evaluate(() => ((document.getElementById('si-error') || {}).textContent || '').trim().slice(0, 100)).catch(() => '?')); });
      await page.waitForTimeout(3000);
    } else if (!who) problems.push(`no active worker with an account in ${hive}`);
    // 3. the path onward, the confusion's predicate on its page
    for (const p of path.slice(1)) {
      const here = await page.evaluate(() => location.pathname.split('/').pop()).catch(() => '');
      if (here !== p) { await page.goto(`${ORIGIN}/${p}`, { waitUntil: 'load', timeout: 60000 }).catch((err) => problems.push(`${p}: ${String(err.message).split('\n')[0].slice(0, 80)}`)); await page.waitForTimeout(4000); }
      let r = await page.evaluate(READ).catch(() => ({ chars: 0 })); let k = 0; while (r.chars < 900 && k < 3) { await page.waitForTimeout(3000); r = await page.evaluate(READ).catch(() => ({ chars: 0 })); k++; }
      if (pred && pred.stage === 'page' && p === target && predicate === null) { predicate = await pred.run(page, ctx).catch((err) => ({ ok: false, detail: 'predicate threw: ' + String(err.message).split('\n')[0] })); await ctx.closeAll().catch(() => {}); }
      await step(p);
    }
  } catch (err) { problems.push('the walk threw: ' + String(err.message).split('\n')[0].slice(0, 120)); }
  await context.close().catch(() => {});
  if (!pred) predicate = { ok: false, detail: `no predicate for ${cid} yet - the confusion was not lived` };
  if (!predicate) predicate = { ok: false, detail: `${cid}: its page ${target} was never reached on this path` };
  if (!predicate.ok) problems.push(`${cid} not lived clean: ${predicate.detail}`);
  const idKept = steps.slice(1).every((s) => s.identityKept);
  if (!idKept) problems.push('identity did not survive the arrival');
  const ok = problems.length === 0 && new Set(steps.map((s) => s.page)).size >= 4;
  if (new Set(steps.map((s) => s.page)).size < 4) problems.push(`only ${new Set(steps.map((s) => s.page)).size} distinct pages walked`);
  results.push({ id: t.id, ok, unbuilt: !who, instrument: 'tools/prove_w4_confusions.mjs', condition: 'normal', cast: who ? `${who.name} (${hive})` : `no cast in ${hive}`, problems,
    note: `${cid} ${predicate.ok ? 'LIVED CLEAN' : 'STILL CONFUSING'}: ${predicate.detail}`, metrics: { steps: steps.length, idKept, predicate: predicate.ok },
    w4: { axis: AXIS, confusion: cid, predicate: predicate.detail }, steps, confusions: [] });
  console.log(`  ${ok ? '\x1b[92mOK \x1b[0m' : '\x1b[91mBAD\x1b[0m'} ${t.id} ${cid.padEnd(4)} ${target.padEnd(28)} ${(who ? who.name : '?').padEnd(20)} ${predicate.ok ? 'lived clean' : 'still confusing'} - ${predicate.detail.slice(0, 110)}${problems.length && !problems[0].startsWith(cid) ? ' | ' + problems[0].slice(0, 90) : ''}`);
  await new Promise((r) => setTimeout(r, 3000));
}
await browser.close();
mkdirSync('.tmp/mcp_walks', { recursive: true });
const outFile = `.tmp/mcp_walks/W4confusions_${AXIS.replace(/\s+/g, '-')}.json`;
let merged = results;
try { if (existsSync(outFile)) { const prior = JSON.parse(readFileSync(outFile, 'utf8')); const now = new Map(results.map((r) => [r.id, r])); merged = (prior.results || []).map((r) => now.get(r.id) || r).concat(results.filter((r) => !(prior.results || []).some((p) => p.id === r.id))); } } catch (e) { void e; }
writeFileSync(outFile, JSON.stringify({ generated: new Date().toISOString(), instrument: 'tools/prove_w4_confusions.mjs', axis: AXIS, walked: results.length, bad: results.filter((r) => !r.ok).length, results: merged }, null, 1));
const bad = results.filter((r) => !r.ok).length;
console.log(`${bad ? 'FAIL' : 'PASS'} w4-confusions@${AXIS} - ${results.length - bad}/${results.length} confusion rows lived clean start to end (path walked, identity kept, predicate holds, no overlap) · ${outFile}`);
