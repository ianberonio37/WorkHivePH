// page_walk_state.mjs - the state a page needs before a lens may grade it (2026-10-13).
//
// ONE copy, imported by tools/family_rubric_sweep.mjs and tools/critic_walk_batch.mjs. The batch had copied the sweep's
// PAGE_QUERY by hand and never its PAGE_REVEAL, so its first run graded project-report's chooser as the report on every
// walk (E3, O2, C3, S1). What a page needs in order to be the page is a fact about the page, not about whichever tool
// happens to walk it. Settle times stay per tool: they are about the tool's pace, not the page's state.

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
