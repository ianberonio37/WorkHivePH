// phone_fit_audit.mjs - the ONE per-step overlap / overflow / occlusion record, shared by three callers
// (Wave 4, 2026-09-14: "overlapping and overflowing in using the platform through phone").
//
//   1. tools/prove_phone_fit.mjs        - the at-rest page sweep (390 / 360 / 320, anon or signed in, en or fil)
//   2. tools/prove_full_journeys.mjs    - the per-step hook: after every step's reading, the same record
//   3. an MCP walk                       - `node tools/phone_fit_audit.mjs --print` emits the injectable for
//                                          playwright's browser_evaluate / chrome-devtools' evaluate_script, so a
//                                          walk driven by hand takes the identical record a script would
//
// WHY ONE FILE: the rubric's V1 excludes fixed/sticky chrome and the hub/companion shell as "by design", has no
// occlusion check at all, measures overflow only at page level, only at rest, at 390, in English - and 118 of 119
// public pages read green while a person on a phone saw overlap (feedback_a_gates_blind_spot_is_a_green_light).
// The sloppiness lives in the states a journey passes through. So the record is taken INSIDE the journey, after
// each step, at rest and after each interaction (sheet, menu, modal, focused input, hub, companion), and a
// finding that appears only after a step is tagged with that step.
//
// WHAT IT RECORDS (each finding names the element, its rect, and for occlusion the covering element + z-index):
//   occlusion   - for every visible interactive control, document.elementFromPoint(centre) must be the control
//                 or a descendant. A FAB, sticky header, consent bar, toast, hub or companion panel covering a
//                 control is a finding REGARDLESS of position:fixed - the case V1 excludes today. This is the
//                 tools/walk_page.mjs question (the one check that covers display, visibility, zero boxes,
//                 off-screen AND occlusion), asked of controls instead of text.
//   overflowEl  - a child past its scroll-parent's box; scrollWidth > clientWidth under overflow:hidden/clip
//                 with no ellipsis; an unbroken token wider than its container (prove_phone_fit's checks).
//   outside / clipped / wrapped / spill / overflow - prove_phone_fit's own at-rest checks, unchanged.
//
// The audit is a REAL function handed to page.evaluate - never a template string (inside a template literal `\s`
// is an unrecognised escape and silently becomes `s`; the first phone-fit version ran as an s-stripper).
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

export function audit(VIS_JS, opts) {
  opts = opts || {};
  const vis = VIS_JS ? (0, eval)(VIS_JS) : ((e) => !!e && (typeof e.checkVisibility === 'function' ? e.checkVisibility({ visibilityProperty: true }) : e.offsetParent !== null));
  const vw = innerWidth, vh = innerHeight;
  const out = { step: opts.step || null, width: vw, lang: (document.documentElement.lang || '').slice(0, 3) || null,
    overflow: document.documentElement.scrollWidth - vw, outside: [], clipped: [], wrapped: [], spill: [], overflowEl: [], occlusion: [] };
  const poster = ((document.querySelector('meta[name="artifact-genre"]') || {}).content || '') === 'poster';
  if (poster) { out.poster = true; return out; }
  const name = (e) => (e.id ? '#' + e.id : e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\s+/)[0] : ''));
  const rectOf = (r) => `${Math.round(r.left)},${Math.round(r.top)} ${Math.round(r.width)}x${Math.round(r.height)}`;
  const ownText = (e) => [...e.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').replace(/\s+/g, ' ').trim();
  const clipper = (e) => { let a = e.parentElement; while (a && a !== document.body) { const o = getComputedStyle(a); if (/hidden|clip|auto|scroll/.test(o.overflowX + ' ' + o.overflow)) return a; a = a.parentElement; } return null; };
  // the control's VISIBLE rect: its box intersected with every overflow-clipping ancestor's box and the viewport.
  // A control scrolled partway out of its scroll-parent (the last row of a scrolling list, a card below a panel's
  // fold) has a full rect whose geometric centre lands in the CLIPPED band - where elementFromPoint returns the
  // scroll-parent's chrome, not the control - so probing the raw centre false-flags "covered". Probe the centre of
  // what is actually painted instead; a fully-visible control's visible rect equals its full rect, so a real
  // FAB/pill-over-button is still caught. An empty intersection = scrolled off / off-screen = the walk's scroll job.
  const visibleRect = (e, r0) => { let L = r0.left, T = r0.top, R = r0.right, B = r0.bottom, a = e.parentElement; while (a && a !== document.body) { const o = getComputedStyle(a); if (/hidden|clip|auto|scroll/.test(o.overflowX + ' ' + o.overflowY + ' ' + o.overflow)) { const q = a.getBoundingClientRect(); L = Math.max(L, q.left); T = Math.max(T, q.top); R = Math.min(R, q.right); B = Math.min(B, q.bottom); } a = a.parentElement; } L = Math.max(L, 0); T = Math.max(T, 0); R = Math.min(R, vw); B = Math.min(B, vh); return { left: L, top: T, right: R, bottom: B, width: R - L, height: B - T }; };
  const decorative = (e) => getComputedStyle(e).pointerEvents === 'none' && !e.textContent.trim();
  const srOnly = (e, cs) => e.clientWidth <= 1 || e.clientHeight <= 1 || (cs.clip && cs.clip !== 'auto') || (cs.clipPath && cs.clipPath !== 'none');
  const all = [...document.querySelectorAll('body *')].filter((e) => vis(e) && !e.closest('script,style,svg,[aria-hidden="true"]'));

  // ── OCCLUSION: every visible interactive control must be reachable at its own centre ─────────────────────
  // A control inside an OPEN overlay (dialog, menu, sheet, hub panel, companion panel) is judged against that
  // overlay's own contents; a control UNDER an open overlay is expected to be covered (the overlay is modal) and
  // is not a finding - the finding is a control the person is meant to use right now that something else sits on.
  const OVERLAY = '[aria-modal="true"], [role="dialog"], [role="menu"], [role="listbox"], .modal, .sheet.open, [class*="sheet"][class*="open"], #wh-hub-panel, #wh-ai-panel, #wh-feedback-panel';
  const openOverlays = [...document.querySelectorAll(OVERLAY)].filter((e) => vis(e) && e.getBoundingClientRect().height > 0);
  const inOpenOverlay = (e) => openOverlays.some((o) => o.contains(e));
  const controls = all.filter((e) => e.matches('a[href], button, [role="button"], [role="tab"], [role="menuitem"], input:not([type="hidden"]), select, textarea, summary, [tabindex]:not([tabindex="-1"])'));
  for (const c of controls) {
    if (c.closest('[inert], [disabled]') || c.disabled) continue;
    const r = c.getBoundingClientRect(); if (r.width < 4 || r.height < 4) continue;
    const cs = getComputedStyle(c); if (srOnly(c, cs)) continue;
    // probe the centre of what is actually PAINTED (the box clipped to its scroll-parents + viewport); a control
    // scrolled partway out of a list is the walk's scroll-to job, not an occlusion, and its empty/tiny visible
    // rect skips here rather than false-flagging the scroll-parent's chrome as a coverer
    const vr = visibleRect(c, r); if (vr.width < 4 || vr.height < 4) continue;
    const x = Math.min(vw - 1, Math.max(0, vr.left + vr.width / 2)), y = Math.min(vh - 1, Math.max(0, vr.top + vr.height / 2));
    if (openOverlays.length && !inOpenOverlay(c)) continue;          // under a modal overlay: covered by design
    const hit = document.elementFromPoint(x, y);
    if (!hit || hit === c || c.contains(hit) || hit.contains(c)) continue;
    // a label wrapping its input, or an input's own visual twin, is the same control
    if (hit.closest('label') && hit.closest('label').control === c) continue;
    const hcs = getComputedStyle(hit);
    const cover = hit.closest('[class*="fab"], [id*="fab"], header, [role="banner"], .sticky, [class*="sticky"], [class*="toast"], [role="alert"], [role="status"], [class*="consent"], [class*="cookie"], #wh-hub-panel, #wh-ai-panel, #wh-feedback-panel, [id^="wh-"], [class^="wh-"]') || hit;
    out.occlusion.push(`${name(c)} "${(c.getAttribute('aria-label') || ownText(c) || c.value || '').slice(0, 24)}" @${rectOf(r)} covered by ${name(cover)} (${hcs.position}, z ${hcs.zIndex}) @${rectOf(cover.getBoundingClientRect())}`);
  }

  for (const e of all) {
    const r = e.getBoundingClientRect(); if (r.width === 0 || r.height === 0) continue;
    const cs = getComputedStyle(e);
    if (srOnly(e, cs)) continue;
    // (1) PARTIALLY outside the viewport (a closed sheet parked fully off-screen is by design; a menu cut at the edge is not)
    const partial = (r.left < vw - 1 && r.right > vw + 2) || (r.left < -2 && r.right > 1);
    if (partial && !decorative(e)) { const c = clipper(e); const scroller = c && /auto|scroll/.test(getComputedStyle(c).overflowX + getComputedStyle(c).overflow); if (!scroller && !(c && c !== document.body && !/menu|dialog|popover|dropdown/.test(e.className + ' ' + e.getAttribute('role')))) out.outside.push(name(e) + ' ' + Math.round(r.left) + '..' + Math.round(r.right) + (c ? ' (cut by ' + name(c) + ')' : '')); }
    const t = ownText(e);
    // (2) text CLIPPED by its own box (overflow hidden + wider content, no ellipsis)
    if (t && /hidden|clip/.test(cs.overflowX + cs.overflow) && e.scrollWidth > e.clientWidth + 2 && cs.textOverflow !== 'ellipsis') out.clipped.push(name(e) + ' ' + e.scrollWidth + '>' + e.clientWidth + ' "' + t.slice(0, 30) + '"');
    // (2b) ELEMENT OVERFLOW INSIDE ITS CONTAINER - any box (not only text) wider than its clipping parent under
    // overflow:hidden/clip: a card spilling under a hidden edge, an image or table wider than its card
    const cp = clipper(e);
    if (cp && cp !== document.body && /hidden|clip/.test(getComputedStyle(cp).overflowX + getComputedStyle(cp).overflow) && cs.position !== 'absolute' && cs.position !== 'fixed') {
      const pr = cp.getBoundingClientRect();
      if (r.right > pr.right + 3 || r.left < pr.left - 3) out.overflowEl.push(name(e) + ' @' + rectOf(r) + ' past ' + name(cp) + ' @' + rectOf(pr));
    }
    // (3) a CONTROL LABEL wrapped inside its own control
    const isControl = e.matches('button, [role="button"], [role="tab"], .pill, .badge, .chip, .tag, .kpi-label, .sc-label, .simple-label, .stat-label, th, .btn, a.btn, [class*="btn-"], [class*="pill"], [class*="chip"], [class*="badge"]');
    if (isControl && !e.matches('.wh-source-chip') && !e.closest('.wh-source-chip') && !e.querySelector('br') && cs.whiteSpace !== 'pre-line') {
      const shortLabel = e.textContent.trim().split(/\s+/).length <= 4;
      const carriers = [e, ...(shortLabel ? [...e.querySelectorAll('*')].filter((c) => vis(c) && ownText(c).length > 3 && !c.matches('svg, svg *')) : [])];
      const linesOf = (el) => { const rg = document.createRange(); rg.selectNodeContents(el); const rects = [...rg.getClientRects()].filter((q) => q.width > 0 && q.height > 0).sort((x, y) => x.top - y.top); let lines = 0, bottom = -1e9; for (const q of rects) { if (q.top >= bottom - 2) { lines++; bottom = q.bottom; } else bottom = Math.max(bottom, q.bottom); } return lines; };
      for (const el of carriers) {
        const t2 = el === e ? t : ownText(el); if (t2.length <= 3) continue;
        if (el !== e && [...el.children].some((c) => getComputedStyle(c).display === 'block' && c.textContent.trim())) continue;
        if (el === e && e.children.length && [...e.children].some((c) => getComputedStyle(c).display === 'block' && c.textContent.trim())) continue;
        const lines = linesOf(el); const rr = el.getBoundingClientRect();
        const words = t2.split(/\s+/).length; const isTh = e.tagName === 'TH';
        const isLabel = e.matches('.kpi-label, .sc-label, .simple-label, .stat-label, p, div:not([role])') && !e.matches('button, [role="button"], [role="tab"], .btn, a.btn, [class*="btn-"]');
        const isPillish = e.matches('.pill, .badge, .chip, .tag, [class*="pill"], [class*="chip"], [class*="badge"]') && !e.matches('button, [role="button"], [role="tab"]');
        const squeeze = (isTh || isLabel) ? lines >= 3 : isPillish ? (lines >= 2 && words <= 4) : (lines >= 2 && (r.width < 240 || words <= 3));
        if (squeeze) { out.wrapped.push(name(e) + (el === e ? '' : ' > ' + name(el)) + ' ' + lines + ' lines @' + Math.round(rr.width) + 'px "' + t2.slice(0, 34) + '"'); break; }
      }
    }
    // (4) text SPILLING past its parent's box (an unbroken id / email / url / number wider than the card)
    if (t.length > 6 && cs.position !== 'absolute' && cs.position !== 'fixed') { const pr = e.parentElement.getBoundingClientRect(); const po = getComputedStyle(e.parentElement); const negM = Math.max(0, -parseFloat(cs.marginRight) || 0);
      if (r.right > pr.right + 3 + negM && pr.width > 0 && !/auto|scroll/.test(po.overflowX + po.overflow)) out.spill.push(name(e) + ' right ' + Math.round(r.right) + ' > parent ' + Math.round(pr.right) + ' "' + t.slice(0, 30) + '"'); }
  }
  // ── CONFUSION DETECTORS (Ian, 2026-09-14: "any other kinds and types" of confusion, not sign-in alone) ────
  // The walks meet confusion the same way a person does. Two kinds a record can measure on every step:
  //   ambiguity    - two or more VISIBLE controls of the same role announce the same name inside one landmark
  //                  (the sign-in wall's two "Sign In"s: a screen reader hears one name twice, a walker's role
  //                  locator resolves both, a person picks the wrong one). Repeats inside separate list items,
  //                  table rows or cards are the ordinary shape of a list and are not counted.
  //   unactionable - a VISIBLE alert / status / error region carrying the transport's own words ("name
  //                  resolution failed", "failed to fetch", "ECONN", "undefined", "[object Object]", a bare
  //                  HTTP code) - a sentence a person cannot act on.
  // Both are RECORDED, never auto-filed: the walk reads them and appends the real ones to w4_confusions.json.
  {
    const groups = {};
    for (const c of controls) {
      if (c.closest('li, tr, [class*="card"], [class*="tile"], [class*="row"], [role="listitem"], [role="row"], [role="option"]')) continue;
      const r = c.getBoundingClientRect(); if (r.width < 4 || r.height < 4) continue;
      const cs = getComputedStyle(c); if (srOnly(c, cs)) continue;
      if (openOverlays.length && !inOpenOverlay(c)) continue;          // under a modal: not announced, not confusable
      const role = c.getAttribute('role') || c.tagName.toLowerCase() + (c.type ? ':' + c.type : '');
      const nm = (c.getAttribute('aria-label') || (c.labels && c.labels[0] && c.labels[0].textContent) || c.textContent || c.value || c.getAttribute('title') || '').replace(/\s+/g, ' ').trim().toLowerCase();
      if (!nm || nm.length > 40) continue;
      const land = c.closest('main, nav, header, footer, aside, [role="dialog"], [role="region"], form') || document.body;
      const key = (land.id || land.tagName.toLowerCase()) + '|' + role + '|' + nm;
      (groups[key] = groups[key] || []).push(name(c));
    }
    out.ambiguity = Object.entries(groups).filter(([, v]) => v.length > 1).map(([k, v]) => `${k.split('|')[2]} (${k.split('|')[1]}) x${v.length} in ${k.split('|')[0]}: ${v.slice(0, 3).join(', ')}`).slice(0, 8);
    const RAW = /name resolution|failed to fetch|networkerror|econn|etimedout|socket hang up|\bundefined\b|\bnull\b|\[object object\]|\bnan\b|^\s*(?:error|err)[:\s]|status(?:code)?\s*[45]\d\d|\b5\d\d\b(?!\s*(?:px|ms|%))|internal server error|bad gateway|service (?:temporarily )?unavailable|exception|stack ?trace|traceback|typeerror|referenceerror/i;
    out.unactionable = [...document.querySelectorAll('[role="alert"], [role="status"], [aria-live], [class*="error"], [id*="error"], [class*="toast"], [class*="alert"]')]
      .filter((e) => vis(e) && e.getBoundingClientRect().height > 0 && !e.closest('script,style'))
      .map((e) => (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim())
      .filter((t) => t && t.length < 400 && RAW.test(t))
      .map((t) => t.slice(0, 120)).slice(0, 4);
  }
  for (const k of ['outside', 'clipped', 'wrapped', 'spill', 'overflowEl', 'occlusion']) out[k] = [...new Set(out[k])].slice(0, 12);
  out.findings = (out.overflow > 2 ? 1 : 0) + out.outside.length + out.clipped.length + out.wrapped.length + out.spill.length + out.overflowEl.length + out.occlusion.length;
  out.confusions = (out.ambiguity || []).length + (out.unactionable || []).length;
  return out;
}

/** The at-rest lines a caller prints or banks: one string per finding, prefixed by kind (and by step when set). */
export function issuesOf(a, width) {
  if (!a || a.poster) return [];
  const tag = a.step ? `[${a.step}] ` : '';
  return (a.overflow > 2 ? [`${tag}page overflow +${a.overflow}px`] : [])
    .concat((a.occlusion || []).map((s) => tag + 'occlusion: ' + s), (a.overflowEl || []).map((s) => tag + 'overflow-el: ' + s),
      a.outside.map((s) => tag + 'outside: ' + s), a.clipped.map((s) => tag + 'clipped: ' + s),
      (a.wrapped || []).map((s) => tag + 'wrapped: ' + s), (a.spill || []).map((s) => tag + 'spill: ' + s))
    .concat(a.error ? [`${tag}audit error: ${a.error}`] : [])
    .map((s) => (width ? s + ` (vw ${width})` : s));
}

/** The INTERACTION SWEEP: tap what reveals state (sheet / menu / modal / hub / companion / a text input with the
 *  keyboard), take the record after each, Escape back. Returns [{step, ...audit}] - one entry per interaction. */
export async function interactionSweep(page, VIS_JS, opts = {}) {
  const max = opts.max || 6;
  const records = [];
  const triggers = await page.evaluate((MENU_SRC) => {
    const re = new RegExp(MENU_SRC, 'i');
    const vis = (e) => e.checkVisibility && e.checkVisibility();
    const list = [...document.querySelectorAll('button, [role="button"], summary, [aria-haspopup], [aria-controls], [data-sheet], [data-modal]')].filter(vis)
      .filter((e) => ((e.textContent || '').trim().length <= 24 && re.test((e.textContent || '').trim())) || re.test(e.getAttribute('aria-label') || '')
        || !!e.getAttribute('aria-haspopup') || !!e.getAttribute('aria-controls') || e.id === 'wh-hub-fab' || e.id === 'wh-ai-launcher' || /open|filter|sort|add|new|edit|more/i.test(e.id + ' ' + e.className));
    return list.slice(0, 40).map((e, i) => { e.setAttribute('data-pfs', String(i)); return { i, label: (e.getAttribute('aria-label') || e.textContent || e.id || '').trim().slice(0, 24) }; });
  }, opts.menuRe || '(⋯|…|⋮|\\bmore\\b|\\bmenu\\b|\\boptions\\b|\\bactions\\b|\\bfilter\\b|\\bsort\\b|\\badd\\b|\\bnew\\b)');
  for (const t of triggers.slice(0, max)) {
    await page.tap(`[data-pfs="${t.i}"]`, { timeout: 3000, force: true }).catch(async () => { await page.click(`[data-pfs="${t.i}"]`, { timeout: 3000, force: true }).catch(() => {}); });
    await page.waitForTimeout(600);
    const a = await page.evaluate(audit, VIS_JS, { step: `after tapping "${t.label || '⋯'}"` }).catch((e) => ({ error: String(e).slice(0, 120), outside: [], clipped: [], wrapped: [], spill: [], overflowEl: [], occlusion: [], overflow: 0, step: `after tapping "${t.label}"` }));
    records.push(a);
    await page.keyboard.press('Escape').catch(() => {}); await page.waitForTimeout(200);
  }
  // the keyboard state: focus the first visible text input, take the record with it focused
  const focused = await page.evaluate(() => { const i = [...document.querySelectorAll('input[type="text"], input[type="search"], input:not([type]), textarea')].find((e) => e.checkVisibility && e.checkVisibility()); if (!i) return null; i.focus(); return i.id || i.name || i.placeholder || 'input'; }).catch(() => null);
  if (focused) {
    await page.waitForTimeout(300);
    records.push(await page.evaluate(audit, VIS_JS, { step: `with "${focused}" focused (keyboard state)` }).catch(() => null));
    await page.keyboard.press('Escape').catch(() => {});
  }
  return records.filter(Boolean);
}

/** page.evaluate(audit, VIS_JS, {step}) is awkward for two-argument evaluate; this bundles them. */
export async function record(page, VIS_JS, step) {
  return page.evaluate(({ VIS_JS: v, step: s, src }) => (0, eval)('(' + src + ')')(v, { step: s }), { VIS_JS, step, src: audit.toString() })
    .catch((e) => ({ error: String(e).slice(0, 120), step, outside: [], clipped: [], wrapped: [], spill: [], overflowEl: [], occlusion: [], overflow: 0, findings: 0 }));
}

// `node tools/phone_fit_audit.mjs --emit-browser` - writes tools/phone_fit_audit.browser.js, a plain script that installs
// `window.__W4_AUDIT(VIS_JS, {step})`. An MCP walk arms it ONCE per browser session with Playwright's addInitScript
// (browser_run_code_unsafe: `page.addInitScript({ path })`), so every navigation carries the audit and each step's
// record is a one-line evaluate - never 10 KB of pasted source per step. GENERATED from this file; regenerate after
// editing audit() (the walk's receipts name the sha they ran with).
if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1] && process.argv.includes('--emit-browser')) {
  const { writeFileSync } = await import('node:fs');
  const { createHash } = await import('node:crypto');
  const src = audit.toString();
  const sha = createHash('sha256').update(src).digest('hex').slice(0, 12);
  const out = join(dirname(fileURLToPath(import.meta.url)), 'phone_fit_audit.browser.js');
  writeFileSync(out, `// GENERATED by \`node tools/phone_fit_audit.mjs --emit-browser\` from audit() in tools/phone_fit_audit.mjs (sha ${sha}). Do not edit.\n`
    + `(function () { window.__W4_AUDIT = ${src}; window.__W4_AUDIT_SHA = ${JSON.stringify(sha)}; })();\n`);
  process.stdout.write(`wrote ${out} (audit sha ${sha})\n`);
}

// `node tools/phone_fit_audit.mjs --print [step]` - the injectable for an MCP walk (paste into browser_evaluate)
if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1] && process.argv.includes('--print')) {
  const step = process.argv[process.argv.indexOf('--print') + 1] || '';
  let VIS = 'null';
  try {
    const harness = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'prover_harness.mjs'), 'utf8');
    const m = harness.match(/export const VIS_JS\s*=\s*(`[\s\S]*?`|'[\s\S]*?'|"[\s\S]*?");/);
    if (m) VIS = m[1];
  } catch (e) { void e; }
  process.stdout.write(`(() => (${audit.toString()})(${VIS}, { step: ${JSON.stringify(step)} }))()\n`);
}
