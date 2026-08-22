// prove_zoom200.mjs — the CF `zoom200` oracle, measured on the rendered page.
//
// THE ORACLE: "at 200% browser zoom every control stays reachable and no text is clipped (WCAG 1.4.4)."
//
// ★200% ZOOM IS A HALVED CSS VIEWPORT, NOT A TRANSFORM. Browser zoom does not scale pixels — it halves
// the number of CSS pixels the layout is given, so 1280×1024 at 200% is a 640×512 CSS viewport at the
// same physical size. Emulating it with `transform: scale(2)` or a deviceScaleFactor would measure a
// different thing entirely: the page would never reflow and every media query would still fire at the
// desktop breakpoint. So the measurement is two contexts, same page, 1280×1024 and 640×512.
//
// ★EVERY FINDING IS DIFFERENTIAL — a defect counts ONLY if it is absent at 100% and present at 200%.
// This bank has manufactured false reds five separate ways by measuring one state and blaming the
// nearest element (a 0.109px abutment read as occlusion; a badge blamed for a scrollWidth that was a
// rendering fact; seven tap-targets fabricated by measuring the box instead of the target). A page
// whose table always overflows is not a ZOOM defect — it overflows at every width, and blaming zoom for
// it would file a true observation under a false cause. The 100% run is the control, and without it
// this prover has no business reporting anything.
//
// WHAT IS MEASURED, each limited to what a browser can actually settle:
//   · REFLOW — the document scrolls horizontally at 200% but not at 100%. WCAG 1.4.10 treats a
//     two-axis scroll as content loss, and it is the failure people actually hit.
//   · CLIPPED TEXT — an element that CLIPS on x (overflow hidden/clip) whose content is wider than its
//     box at 200% but fit at 100%. An ellipsis is a DESIGNED truncation and is excluded: `longest` is
//     the oracle that judges truncation, not this one.
//   · UNREACHABLE CONTROL — an interactive element that had a box at 100% and has none at 200%, or that
//     sits outside the scrollable document so no amount of scrolling reaches it.
//
// ★ZERO-DENOMINATOR RAIL. A page that renders no control and no text at 200% was not measured — it
// failed to load, or auth bounced it — and reporting "0 defects" over that is the vacuous green this
// bank exists to refuse. Such a page returns UNGRADED with its counter.
//
// USAGE:  node tools/prove_zoom200.mjs [--page <name>]
// OUTPUT: zoom200_report.json

import { chromium } from 'playwright';
import { writeFileSync, readFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager', 'dayplanner',
  'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain', 'voice-journal', 'assistant',
  'community', 'public-feed', 'achievements', 'engineering-design', 'resume', 'report-sender',
  'project-report', 'analytics-report'];

const QUERY = { 'project-report': '?project_id=539e0d9a-9ff7-474b-ab03-9254406ca7dc' };

// Runs in-page. Returns FACTS only; the verdict is computed outside, by comparing two runs.
const measure = () => {
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

  return {
    docScrollX: de.scrollWidth - de.clientWidth,
    controls, names, clipped,
    nControls: Object.keys(controls).length,
    textLen: (document.body.innerText || '').replace(/\s+/g, ' ').trim().length,
  };
};

// ★ONE PAGE, RESIZED — NOT TWO LOADS. Loading the page twice made the CONTENT a variable, and on
// community that produced a finding I nearly banked: "Edit my post" and "Make post private" appeared at
// 1280 and not at 640, reproducibly. Neither control has any width conditional in its render — both are
// gated on `isMine` and `HIVE_ROLE`, which resolved identically in both runs — so the difference was
// never the viewport. A live feed with 12 realtime channels simply does not render identically twice,
// and I would have filed a true observation under a false cause for the third time in this bank.
// Resizing ONE page holds the DOM, the identity and the data fixed by construction, so a difference
// that survives IS the viewport. It also halves the loads.
const walk = async (browser, name, recover) => {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 1024 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const page = await ctx.newPage();
  const out = {};
  try {
    await page.goto(ORIGIN + '/workhive/' + name + '.html' + (QUERY[name] || ''),
      { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(6500);
    out.at100 = await page.evaluate(measure);
    await page.setViewportSize({ width: 640, height: 512 });
    // Reflow, re-run any resize handlers, and let a media-query-driven re-render settle.
    await page.waitForTimeout(2500);
    out.at200 = await page.evaluate(measure);
    // ★A CONTROL BEHIND A DISCLOSURE IS STILL REACHABLE, and not modelling that would red-flag every
    // collapsible sidebar on the roster. dayplanner collapses its sidebar at <=640px and offers a
    // visible, labelled toggle that restores all 30 of its buttons — WCAG 1.4.4 asks whether the
    // functionality survives the zoom, not whether it survives without a press.
    // ★ONLY BUTTONS, NEVER LINKS: an inducing probe ACTS, and one that clicks an <a> navigates away and
    // then measures a different page - an error already recorded in this bank.
    if (recover) {
      const opened = await page.evaluate(() => {
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
      }).catch(() => 0);
      if (opened) {
        await page.waitForTimeout(1200);
        out.at200.afterDisclosure = await page.evaluate(measure);
        out.at200.disclosuresPressed = opened;
      }
    }
  } catch (e) { out.error = String(e.message || e).slice(0, 140); }
  await ctx.close();
  return out;
};

const run = async () => {
  const browser = await chromium.launch();
  const out = {
    origin: ORIGIN,
    note: '200% zoom emulated as a halved CSS viewport (1280x1024 -> 640x512); every finding is '
      + 'differential - present at 200% and absent at 100%',
    pages: [],
  };

  for (const name of (ONE ? ONE.split(',') : PAGES)) {
    const rec = { page: name };
    const w = await walk(browser, name, true);
    const at100 = w.at100 || {}; const at200 = w.at200 || {};

    if (w.error || !w.at100 || !w.at200) {
      rec.error = w.error || 'no measurement';
      rec.ok = null;
      rec.why = 'could not measure: ' + rec.error;
    } else if (at200.nControls === 0 && at200.textLen < 40) {
      rec.ok = null;
      rec.why = 'the page rendered no control and no text at 200% - it did not load, so nothing was '
        + 'judged; UNGRADED rather than a pass over an empty set';
    } else {
      const reflow = at200.docScrollX > 4 && at100.docScrollX <= 4;
      const newClip = Object.entries(at200.clipped)
        .filter(([k]) => !(k in at100.clipped))
        .map(([k, v]) => ({ el: k, over: v.over, text: v.text }));
      const after200 = (at200.afterDisclosure || {}).names || {};
      const lost = Object.keys(at100.names)
        // Reachable at 200% directly, or after pressing the page's own disclosure = not a loss.
        .filter((n) => !at200.names[n] && !after200[n])
        .map((n) => ({ control: n, reason: 'offered at 100% and nowhere at 200%',
          instancesAt100: at100.names[n] }));

      rec.controls100 = at100.nControls;
      if (at200.disclosuresPressed) rec.disclosuresPressed = at200.disclosuresPressed;
      rec.docScrollX = { at100: at100.docScrollX, at200: at200.docScrollX };
      rec.reflow = reflow;
      rec.clipped = newClip.slice(0, 6);
      rec.unreachable = lost.slice(0, 6);
      rec.ok = !reflow && newClip.length === 0 && lost.length === 0;
      rec.why = rec.ok
        ? 'at a halved viewport nothing new is clipped, no control is lost and the document does not '
          + 'scroll sideways (' + at100.nControls + ' controls compared across both widths)'
        : [reflow ? 'the document scrolls ' + at200.docScrollX + 'px sideways at 200% but not at 100%' : '',
           newClip.length ? newClip.length + ' element(s) clip text only at 200%' : '',
           lost.length ? lost.length + ' control(s) reachable at 100% are not at 200%' : '']
          .filter(Boolean).join('; ');
    }
    out.pages.push(rec);
    console.log('  ' + (rec.ok === null ? 'UNGRADED' : rec.ok ? 'PASS    ' : 'FAIL    ')
      + ' ' + name.padEnd(19) + ' ' + (rec.why || '').slice(0, 98));
  }
  await browser.close();
  // Merge with any prior partial run so the roster can be walked in halves without losing the first.
  const dest = path.join(ROOT, 'zoom200_report.json');
  try {
    const prev = JSON.parse(readFileSync(dest, 'utf8'));
    const have = new Set(out.pages.map((p) => p.page));
    out.pages = [...(prev.pages || []).filter((p) => !have.has(p.page)), ...out.pages];
  } catch (_) { /* empty-catch-allow: no prior report is the normal first run */ }
  writeFileSync(dest, JSON.stringify(out, null, 1));
  const g = out.pages.filter((p) => p.ok !== null);
  // gate promotion 2026-08-21: failing rows set the exit code.
  if (process.argv.includes('--gate')) process.exitCode = g.filter((p) => !p.ok).length ? 1 : 0;
  console.log('\n  ' + g.filter((p) => p.ok).length + ' pass | ' + g.filter((p) => !p.ok).length
    + ' fail | ' + (out.pages.length - g.length) + ' ungraded');
};
run().catch((e) => { console.error(e); process.exit(1); });
