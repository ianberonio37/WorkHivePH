/**
 * walk_page.mjs — read what a person can ACTUALLY SEE on a page. (2026-08-28)
 *
 * Written after one session's ad-hoc walk scripts produced three false alarms in a row, each caught
 * only because the finding was verified a second way against source or the database. All three were
 * the same mistake in different clothes — asking the DOM a question that sounds like "is this
 * visible" and is not:
 *
 *   1. innerText IS NOT A VISIBILITY FILTER. Per spec, an element that is NOT BEING RENDERED
 *      returns textContent from innerText. So a display:none empty-state reads exactly like a
 *      visible one — this reported "You're offline" on a page that was online, and "No tools match
 *      your search" on a page listing tools.
 *   2. A BOUNDING BOX IS NOT VISIBILITY EITHER. marketplace-admin is covered by a
 *      position:fixed inset:0 z-index:100000 retirement overlay; everything behind it still has a
 *      non-zero box and display:block, so the walk read a retired page's live figures as current.
 *   3. A TOP-N SAMPLE IS NOT A PAGE. Truncating to the first six strings hid project-report's
 *      "No project specified" and "not found" refusals further down, and nearly produced a filed
 *      defect against a page that had already solved it.
 *
 * So this asks the only question that answers all three: for each candidate element, is the element
 * at its own centre point itself-or-a-descendant? That is document.elementFromPoint, and it accounts
 * for display, visibility, zero boxes, off-screen position AND occlusion in one check.
 *
 * It also never truncates silently: the result carries `dropped`, so a caller can see that it is
 * reading a sample rather than the page.
 *
 * USAGE (from another probe):
 *   import { visibleText } from './walk_page.mjs';
 *   const lines = await visibleText(page, { max: 40, maxLen: 130 });
 *
 * The returned object is { lines, dropped, scanned }.
 */

/**
 * Collect the visible text lines of a page, occlusion-aware.
 * @param {import('playwright').Page} page
 * @param {{max?:number, maxLen?:number, match?:RegExp}} opts
 */
export async function visibleText(page, opts = {}) {
  const { max = 40, maxLen = 130, match = null } = opts;
  return page.evaluate(({ max, maxLen, matchSrc }) => {
    const re = matchSrc ? new RegExp(matchSrc, 'i') : null;

    // ★THE ONE CHECK THAT COVERS ALL THREE FAILURE MODES. elementFromPoint returns whatever is
    // painted at that coordinate, so a display:none element (no box), an off-screen element, and an
    // element buried under a fixed overlay all fail it — while a genuinely visible one passes.
    const reallyVisible = (el) => {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return false;
      if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) return false;
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') return false;
      const x = Math.min(Math.max(r.left + r.width / 2, 1), innerWidth - 1);
      const y = Math.min(Math.max(r.top + r.height / 2, 1), innerHeight - 1);
      const hit = document.elementFromPoint(x, y);
      return !!hit && (hit === el || el.contains(hit) || hit.contains(el));
    };

    const seen = new Set();
    const lines = [];
    let scanned = 0, dropped = 0;
    for (const el of document.querySelectorAll('*')) {
      if (el.children.length > 2) continue;          // leaf-ish nodes carry the readable text
      scanned++;
      if (!reallyVisible(el)) continue;
      const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
      if (!t || t.length > maxLen || seen.has(t)) continue;
      if (t.startsWith('.') || t.startsWith('@') || t.startsWith('{')) continue;  // stylesheet text
      if (re && !re.test(t)) continue;
      seen.add(t);
      if (lines.length < max) lines.push(t); else dropped++;
    }
    // ★NEVER TRUNCATE SILENTLY: a caller that cannot see `dropped` cannot tell a page from a sample.
    return { lines, dropped, scanned };
  }, { max, maxLen, matchSrc: match ? match.source : null });
}
