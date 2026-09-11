// ai_ask.mjs - how a prover ASKS an AI surface the way a person does (lifted from prove_ai_trust.mjs, 2026-09-07).
//
// Two provers need the same move: the AI-trust wave (T1..T4 on every AI surface) and the PX quota-spent cell
// (the same spent-quota moment at the persona's viewport). The first PX walk judged assistant.html without
// asking it anything - "the AI quota is gone and nothing on the page says so" - because nothing had been asked,
// so nothing could be refused. One module, so the OPEN / PREP / TRIGGER / BOX vocabulary is written once.
//
//   armQuotaRefusal(p)           every AI front door answers 429 the way rate-limit.ts does on a spent quota
//   askSurface(p, file, launcherOnly)  open what must be opened, prepare what must exist, type the question and
//                                send it (or press the page's own trigger); returns which box was asked, or false
//   VIEW_ONLY                   surfaces that only SHOW AI output - they cannot be asked, so nothing can be refused
import { readFileSync } from 'node:fs';

export const REFUSAL = { error: 'AI call limit reached for this hive. Try again in about 12 minutes.', scope: 'hour', retryAfter: 720, retry_after: 720 };
export const VIEW_ONLY = new Set(['ai-quality.html', 'agentic-rag-observability.html', 'llm-observability.html']);

export async function armQuotaRefusal(p) {
  await p.route('**/functions/v1/ai-gateway**', (r) => r.fulfill({ status: 429, contentType: 'application/json', headers: { 'Retry-After': '720' }, body: JSON.stringify(REFUSAL) })).catch(() => {});
  await p.route('**/functions/v1/asset-brain-query**', (r) => r.fulfill({ status: 429, contentType: 'application/json', body: JSON.stringify(REFUSAL) })).catch(() => {});
  // the other AI front doors on the roster - each answers as the platform's rate-limit.ts does on a spent quota
  for (const fn of ['analytics-orchestrator', 'resume-polish', 'resume-extract', 'shift-planner-orchestrator', 'voice-journal-agent']) {
    await p.route(`**/functions/v1/${fn}**`, (r) => r.fulfill({ status: 429, contentType: 'application/json', headers: { 'Retry-After': '720' }, body: JSON.stringify(REFUSAL) })).catch(() => {});
  }
}

export async function askSurface(p, file, launcherOnly) {
  const TRIGGER = { 'analytics.html': /recompute|refresh|re-?run|run analysis/i, 'shift-brain.html': /generate plan|regenerate|re-?run/i, 'resume.html': /polish/i };
  // a surface whose ask box lives one press deeper (Asset Brain sits inside an asset's 360 view) is opened first
  const OPEN = { 'asset-hub.html': '.asset-card', 'voice-journal.html': '#type-fallback summary' };
  if (OPEN[file]) {
    await p.evaluate((sel) => { const el = [...document.querySelectorAll(sel)].find((e) => e.checkVisibility && e.checkVisibility()); if (el) el.click(); }, OPEN[file]).catch(() => {});
    await p.waitForTimeout(2500);
  }
  // the resume polish calls the AI only once an experience line exists - the person adds one first
  const PREP = { 'resume.html': [{ click: '[data-action="add"][data-sec="work"]' }, { fill: '[data-sec="work"][data-field="highlights"]', value: 'Repaired Pump P-204B; cut downtime by 4 hours' }] };
  for (const step of (PREP[file] || [])) {
    await p.evaluate((s) => {
      const el = [...document.querySelectorAll(s.click || s.fill)].find((e) => e.checkVisibility && e.checkVisibility());
      if (!el) return;
      if (s.click) el.click();
      else { el.focus(); el.value = s.value; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); el.blur(); }
    }, step).catch(() => {});
    await p.waitForTimeout(900);
  }
  // a page whose only AI is the launcher (community) also has its OWN boxes - "New Post" matched the ask regex
  // and the question went into a community post; the launcher is opened FIRST there and its box preferred
  await p.evaluate((launcherFirst) => {
    const vis = (e) => e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
    const box = [...document.querySelectorAll('textarea, input[type="text"]')].find((e) => vis(e) && !e.readOnly && !e.disabled && /ask|question|message|chat|search|prompt/i.test(e.id + ' ' + e.placeholder + ' ' + e.getAttribute('aria-label')));
    const trig = document.getElementById('wh-ai-trigger');
    // the trigger fades in: a visibility check that includes opacity read it as hidden at this moment, so click it as it is
    if ((launcherFirst || !box) && trig) trig.click();
    // a toast lives ~4 s and the read comes at 7 s: remember every notice the page paints from here on
    window.__whNotices = [];
    const grab = (n) => { if (n && n.nodeType === 1) { const t = (n.innerText || '').replace(/\s+/g, ' ').trim(); if (t && /limit|quota|try again|wait|resets|spent|out of/i.test(t)) window.__whNotices.push(t.slice(0, 200)); } };
    new MutationObserver((muts) => muts.forEach((m) => { m.addedNodes.forEach(grab); if (m.type === 'characterData' || m.type === 'childList') grab(m.target); }))
      .observe(document.body, { childList: true, subtree: true, characterData: true });
  }, launcherOnly).catch(() => {});
  await p.waitForTimeout(1200);
  // a surface whose box does not NAME itself (voice-journal's #type-input) is reached by its own id
  const BOX = { 'voice-journal.html': '#type-input' };
  const asked = await p.evaluate(([trigRx, boxSel, launcherFirst]) => {
    const vis = (e) => e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
    const lb = launcherFirst ? document.getElementById('wh-ai-input') : null;
    const box = (lb && vis(lb) ? lb : null)
      || (boxSel && document.querySelector(boxSel) && vis(document.querySelector(boxSel)) ? document.querySelector(boxSel) : null)
      || [...document.querySelectorAll('textarea, input[type="text"]')].find((e) => vis(e) && !e.readOnly && !e.disabled && /ask|question|message|chat|search|prompt/i.test(e.id + ' ' + e.placeholder + ' ' + e.getAttribute('aria-label')));
    if (!box) {
      if (!trigRx) return false;
      const rx = new RegExp(trigRx, 'i');
      const btn = [...document.querySelectorAll('button, [role="button"], a.btn')].find((e) => vis(e) && !e.disabled && rx.test((e.innerText || e.getAttribute('aria-label') || '').trim()));
      if (!btn) return false;
      btn.click();
      return true;
    }
    box.focus(); box.value = 'What torque for an M12 grade 8.8 bolt?';
    box.dispatchEvent(new Event('input', { bubbles: true }));
    // the launcher's send is #wh-ai-send (a glyph, no word); the voice journal's is #type-send - the box's own sibling first
    const own = box.id === 'wh-ai-input' ? document.getElementById('wh-ai-send') : (box.id === 'type-input' ? document.getElementById('type-send') : null);
    const send = (own && vis(own)) ? own : [...document.querySelectorAll('button, [role="button"]')].find((e) => vis(e) && /^(ask|send|submit|go|search|generate|➤|→)/i.test((e.innerText || e.getAttribute('aria-label') || '').trim()));
    if (send) send.click(); else box.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    return box.id || box.getAttribute('aria-label') || box.placeholder || 'box';   // which box was asked - printed on the line
  }, [TRIGGER[file] ? TRIGGER[file].source : null, BOX[file] || null, launcherOnly]).catch(() => false);
  return asked;
}

// the prover-side decision the AI-trust wave makes from the page source: a page whose only AI is the companion
// launcher has no own front door, so the launcher is opened FIRST and its box preferred
export function launcherOnlyFor(file) {
  let src = '';
  try { src = readFileSync(file, 'utf8'); } catch (_) { src = ''; }
  const ownAi = /functions\/v1\/|functions\.invoke\(/.test(src);
  const usesLauncher = /companion-launcher\.js/.test(src);
  return usesLauncher && !ownAi;
}
