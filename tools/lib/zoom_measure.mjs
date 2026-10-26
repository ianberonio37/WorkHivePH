// zoom_measure.mjs - the in-page measurement prove_zoom200 and prove_text_grows share (moved here 2026-10-27).
// Both provers grade DIFFERENTIALLY: they call measure() on one page in two states and a finding is only what the
// second state has and the first does not. The comments are the lessons each false red taught; they moved with the code.

// Runs in-page. Returns FACTS only; the verdict is computed outside, by comparing two runs.
export const measure = () => {
  const de = document.documentElement;
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden'
      && Number(cs.opacity) > 0.05;
  };
  // A stable-enough identity to match an element across two page loads. Position is deliberately NOT
  // part of it — the whole point of the comparison is that position changes between the two runs.
  // ★A TEXT KEY COLLAPSES REPEATS, AND THAT UNDER-REPORTED A REAL FINDING 30-FOLD. dayplanner hides
  // THIRTY "+ Add to my day" buttons at a halved viewport; keyed by text alone they became one dict
  // entry and the report said "1 control". An under-count is the same class of error as an over-count:
  // the number in a finding is part of the claim. Occurrence index restores the count and stays stable
  // across two loads of the same page, because DOM order does not depend on viewport width.
  const _seen = Object.create(null);
  const key = (el) => {
    const id = el.id ? '#' + el.id : '';
    const txt = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40);
    const base = el.tagName + id + '|' + txt;
    _seen[base] = (_seen[base] || 0) + 1;
    return base + '#' + _seen[base];
  };

  // ★"REACHABLE" IS ABOUT CAPABILITY, NOT ABOUT ELEMENT IDENTITY — matching per-element manufactured
  // three false reds in one run. voice-journal reported its "Home" link lost, when a responsive layout
  // simply swaps a desktop nav for a mobile one and Home is right there under a different node;
  // community reported an unnamed icon button lost, matched only by its position among other unnamed
  // buttons. WCAG 1.4.4 asks whether the person can still DO the thing, so the comparison is over the
  // set of ACCESSIBLE NAMES of visible controls: a name offered at 100% and offered nowhere at 200% is
  // a lost capability, and the same name under a different element is not a loss at all.
  // ★AN UNNAMED CONTROL IS EXCLUDED, not silently passed: it cannot be tracked by name, and "this
  // button has no name" is `icon_only_name`'s finding to make, not this oracle's.
  const nameOf = (el) => {
    const img = el.querySelector && el.querySelector('img[alt]');
    return (el.getAttribute('aria-label') || el.title || (el.innerText || '').trim()
      || (img && img.alt) || el.getAttribute('name') || el.value || '').replace(/\s+/g, ' ').trim();
  };
  const CTRL = 'button, a[href], input, select, textarea, [role="button"], [role="tab"], [onclick]';
  const controls = {};
  const names = {};
  for (const el of document.querySelectorAll(CTRL)) {
    const r = el.getBoundingClientRect();
    const shown = vis(el);
    // Reachable = inside the document's scrollable extent. A box at x=3000 on a page that only
    // scrolls to 640 is a control nobody can get to.
    const offRight = Math.round(r.left + window.scrollX - de.scrollWidth);
    controls[key(el)] = { shown, w: Math.round(r.width), h: Math.round(r.height), offRight };
    const n = nameOf(el).slice(0, 60);
    if (n && shown && offRight <= 4) names[n] = (names[n] || 0) + 1;
  }

  const clipped = {};
  for (const el of document.querySelectorAll('*')) {
    const cs = getComputedStyle(el);
    const ox = cs.overflowX;
    if (ox !== 'hidden' && ox !== 'clip') continue;
    // ★AN ELLIPSIS IS A DESIGNED TRUNCATION, NOT A ZOOM DEFECT. `longest` owns that judgement.
    if (cs.textOverflow === 'ellipsis') continue;
    if (!vis(el)) continue;
    const over = el.scrollWidth - el.clientWidth;
    if (over <= 2) continue;                    // sub-pixel and 1px rounding are not clipping
    const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
    if (!t) continue;                           // a clipped decoration is not clipped TEXT
    clipped[key(el)] = { over, text: t.slice(0, 60) };
  }

  // ★TEXT SPACING CLIPS DOWNWARD. 1.4.12's line-height 1.5 / paragraph 2em grow a box's text TALLER, and the box that
  // fails is a fixed height with overflow hidden - which the x-only check above cannot see. A line clamp is a designed
  // truncation, exactly as an ellipsis is, and is excluded for the same reason (added 2026-10-27, prove_text_grows).
  const clippedY = {};
  for (const el of document.querySelectorAll('*')) {
    const cs = getComputedStyle(el);
    const oy = cs.overflowY;
    if (oy !== 'hidden' && oy !== 'clip') continue;
    if (cs.webkitLineClamp && cs.webkitLineClamp !== 'none') continue;
    if (!vis(el)) continue;
    const over = el.scrollHeight - el.clientHeight;
    if (over <= 2) continue;
    const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
    if (!t) continue;
    clippedY[key(el)] = { over, text: t.slice(0, 60) };
  }

  return {
    docScrollX: de.scrollWidth - de.clientWidth,
    controls, names, clipped, clippedY,
    nControls: Object.keys(controls).length,
    textLen: (document.body.innerText || '').replace(/\s+/g, ' ').trim().length,
  };
};

// The page's own disclosures, pressed to reveal what a halved viewport tucked away (see prove_zoom200's walk).
// Returns how many were pressed.
export const recoverDisclosures = () => {
  const NAME = /sidebar|menu|expand|collapse|show|more|toggle|filter|open/i;
  const hits = [...document.querySelectorAll('button, [role="button"]')].filter((el) => {
    if (el.tagName === 'A' || el.closest('a')) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    // ★A RECOVERY PRESS MUST ONLY EVER REVEAL. shift-brain's summary disclosure is OPEN by
    // default, and "toggle"/"show" matched its button — so the recovery press CLOSED it and the
    // six PM rows inside became "controls lost at 200%". The probe created the defect it then
    // reported. A control already expanded is skipped; so is a <details> already open.
    if (el.getAttribute('aria-expanded') === 'true') return false;
    const det = el.closest('details');
    if (det && det.open) return false;
    const n = (el.getAttribute('aria-label') || el.title || el.innerText || '').trim();
    return NAME.test(n);
  }).slice(0, 6);
  hits.forEach((el) => { try { el.click(); } catch (_) { /* empty-catch-allow */ } });
  return hits.length;
};
