// page_walk_state.mjs - the state a page needs before a lens may grade it (2026-10-13).
//
// ONE copy, imported by tools/family_rubric_sweep.mjs and tools/critic_walk_batch.mjs. The batch had copied the sweep's
// PAGE_QUERY by hand and never its PAGE_REVEAL, so its first run graded project-report's chooser as the report on every
// walk (E3, O2, C3, S1). What a page needs in order to be the page is a fact about the page, not about whichever tool
// happens to walk it. Settle times stay per tool: they are about the tool's pace, not the page's state.

import { readdirSync, readFileSync } from 'fs';

// ★THE PAGE'S OWN SCRIPT FILES ARE ITS CODE (CF12, 2026-11-08; the GJ prover's rule of 2026-11-06, now one copy). The rubric's
// J1 looks for a destructive control's guard in the page's code - the inline scripts, plus window.__WH_PAGE_OWN_JS. The
// founder console confirms "Remove", "Reject" and the rest through whConfirm in operator-actions.js, loaded by src, so a
// walker that did not fill __WH_PAGE_OWN_JS graded J1 0/8 on eight guarded controls (critic walk SL32, as oversight). A
// script four or more pages load is shared chrome (utils.js, the nav hub), graded once on its own; fewer is the page's own.
let _shared = null;
export function sharedScripts() {
  if (_shared) return _shared;
  const uses = new Map();
  const htmls = [...readdirSync('.').filter((f) => f.endsWith('.html')),
    ...['feedback', 'learn', 'tools'].flatMap((d) => { try { return readdirSync(d, { withFileTypes: true }).filter((x) => x.isDirectory()).map((x) => `${d}/${x.name}/index.html`); } catch (_) { return []; } })];
  for (const h of new Set(htmls)) {
    let src = '';
    try { src = readFileSync(h, 'utf8'); } catch (_) { continue; }
    for (const m of src.matchAll(/<script[^>]*\bsrc="([^"]+)"/g)) {
      const base = m[1].split('?')[0].split('/').pop();
      uses.set(base, (uses.get(base) || 0) + 1);
    }
  }
  _shared = new Set([...uses].filter(([, n]) => n >= 4).map(([b]) => b));
  return _shared;
}
export async function loadPageOwnJs(page) {
  await page.evaluate(async (shared) => {
    let t = '';
    for (const sc of [...document.scripts].filter((x) => x.src && new URL(x.src).origin === location.origin)) {
      const base = new URL(sc.src).pathname.split('/').pop();
      if (shared.includes(base)) continue;
      try { t += '\n' + await (await fetch(sc.src)).text(); } catch (_) { /* a script that cannot be re-read is left out */ }
    }
    window.__WH_PAGE_OWN_JS = t;
  }, [...sharedScripts()]).catch(() => {});
}

// Deep-link state a page's REAL use requires (never measure a bounced shell).
export const PAGE_QUERY = { 'marketplace-seller-profile.html': '?worker=Bryan%20Garcia' };

// Worked-state reveal: the step (local, no AI, no credits) that turns a page's empty or choosing state into the artifact
// the rubric must grade. Two forms:
//   { click: /regex/ }  - click the first visible button/[onclick] whose text matches (a generator form's local render)
//   { follow: 'css' }   - follow the first matching link (a chooser whose real state is one of its choices)
// ★project-report LOST ITS GENERATE BUTTON and the reveal kept pointing at it (2026-10-13). The page now needs
// ?project_id=; with none it says "Choose a project" and lists the hive's recent projects. The old /generate/i click
// matched nothing, silently, so every walk graded the chooser. Its worked state is the first recent project's report.
export const PAGE_REVEAL = {
  'project-report.html': { follow: 'a[href*="project-report.html?project_id="]' },
  // ★the report, not the generator's empty area (2026-11-07): every critic walk that met analytics-report graded its
  // pre-Generate area (h1=0, headings=0, cta=0). Its worked state is the generated report; the batch's model-call wire
  // (critic_walk_batch.mjs) makes the generation local - the plan comes from the records.
  'analytics-report.html': { click: /^Generate Report$/, noModel: 'analytics-orchestrator' },
};

// Run the page's reveal, if it has one. Returns what was done (a label or href) or null when nothing applied.
// A reveal that finds nothing to act on returns null rather than throwing: the caller then grades the page as found,
// and should say so (a silent no-op reveal is how the chooser was graded as the report for a whole batch).
export async function revealWorkedState(page, rel) {
  const r = PAGE_REVEAL[rel];
  if (!r) return null;
  if (r.follow) {
    const href = await page.evaluate((sel) => {
      const a = document.querySelector(sel);
      return a ? a.getAttribute('href') : null;
    }, r.follow);
    if (!href) return null;
    await page.goto(new URL(href, page.url()).toString(), { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
    await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
    await page.waitForTimeout(2500);
    return href;
  }
  if (r.click) {
    // ★NO REVEAL SPENDS A MODEL CALL (2026-11-07). A generator whose result ends in a model-written section carries the
    // group walks' local-only flag (debug_fault_inject, honoured only on kong/localhost), so it renders from the records.
    // route.fallback hands the flagged request on, so a context-level dependency-down 503 still answers it.
    if (r.noModel) {
      await page.route(`**/functions/v1/${r.noModel}**`, async (route) => {
        const req = route.request();
        if (req.method() !== 'POST') return route.fallback();
        let body;
        try { body = JSON.parse(req.postData() || '{}'); } catch (_) { return route.fallback(); }
        body.debug_fault_inject = true;
        return route.fallback({ postData: JSON.stringify(body) });
      }).catch(() => {});
    }
    const clicked = await page.evaluate((reSrc) => {
      const re = new RegExp(reSrc, 'i');
      const vis = (el) => el && el.offsetParent !== null;
      const btn = [...document.querySelectorAll('button, a[role="button"], [onclick]')]
        .find((el) => vis(el) && re.test((el.textContent || '').trim()));
      if (btn) { btn.click(); return (btn.textContent || '').trim().slice(0, 30); }
      return null;
    }, r.click.source);
    if (clicked) await page.waitForTimeout(2500);
    return clicked;
  }
  return null;
}
