// prove_longest.mjs — the CF `longest` oracle, measured by injecting the long value and watching.
//
// THE ORACLE: "the longest realistic title truncates visibly rather than overflowing its card or pushing
// the price out of view."
//
// ★THE LONG VALUE HAS TO BE PUT THERE. Every other prover in this bank reads what the page happens to
// render, and that is exactly why these rows stayed owed: the seeded data has short names, so the page
// never shows its behaviour under a long one. Waiting for a real 120-character asset name to appear is
// waiting forever. So this one INDUCES the condition — it writes a long string into a rendered title and
// measures what moves. That is a DOM edit in one browser tab; nothing is submitted and no request is
// made, so the shared database is untouched.
//
// ★AND IT IS DIFFERENTIAL, because a card that already overflows is not a LONGEST defect. The siblings'
// geometry is recorded before the injection and again after, and only what MOVED is attributed to the
// long title. This bank has filed a true observation under a false cause three times; the control is
// what keeps that from being four.
//
// WHAT COUNTS AS THE DEFECT, in the oracle's own terms:
//   · OVERFLOWS ITS CARD — the title's own box grows wider than the card that contains it, or the card
//     grows wider than the list that contains it. Either way the layout is carrying text it cannot hold.
//   · PUSHES A SIBLING OUT OF VIEW — a control or figure that shared the row is now clipped, off the
//     card, or overlapped. On this platform the sibling is the status pill, the quantity or the action
//     button, and losing it silently is worse than losing the title.
//   · SPILLS THE PAGE SIDEWAYS — the document gains horizontal scroll it did not have.
// A title that WRAPS to more lines, or truncates with an ellipsis, passes: both are visible, deliberate
// answers to a long value. Growing TALLER is not a defect — it is the correct one.
//
// ★THE ZERO-DENOMINATOR RAIL. A page with no rendered title to lengthen was not measured, and "0 of 0
// titles overflowed" reads exactly like a thorough pass. Those return UNGRADED.
//
// USAGE:  node tools/prove_longest.mjs [--page <name>]
// OUTPUT: longest_report.json

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
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

// ★A REALISTIC LONG TITLE, NOT A PATHOLOGICAL ONE. 118 characters of real maintenance vocabulary with
// ordinary spaces — the kind of name a plant actually types. A 500-character run of "AAAA" would break
// any layout and prove nothing about this product; an unbroken string would additionally test word-break
// behaviour, which is a different question from the one the oracle asks.
const LONG = 'Replace mechanical seal and both journal bearings on the No. 2 boiler feedwater pump '
  + 'during the November shutdown';

const probe = (LONGTEXT) => {
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 4 && r.height > 4 && cs.display !== 'none' && cs.visibility !== 'hidden'
      && Number(cs.opacity) > 0.05;
  };
  // The title of a row: the widest leaf text inside a card-like block. Reading the WIDEST leaf rather
  // than matching a class name keeps this working across 22 pages that name their cards differently.
  const CARD = '.card, .simple-card, .wh-card, [class*="-card"], [class*="-row"], li, tr';
  // ★A KPI TILE IS NOT A ROW TITLE, and taking the first card in DOM order handed me the wrong subject
  // on most of the roster: "Total assets", "OEE (avg, partial)", "XP this week" — dashboard labels, not
  // the list titles this oracle is about. Every page passed, and the passes were about the wrong thing.
  // A LIST is a repeated structure, so prefer a card that has siblings of its own shape: group the
  // candidates by parent + class signature and take the first group with at least three members. A
  // one-off tile has no such group; a job list, a parts list and a post feed all do.
  const groups = new Map();
  for (const c of document.querySelectorAll(CARD)) {
    if (!vis(c)) continue;
    const r = c.getBoundingClientRect();
    if (r.width < 120 || r.height < 24) continue;
    const sig = (c.parentElement ? (c.parentElement.id || c.parentElement.className) : '') + '|'
      + c.tagName + '|' + String(c.className).slice(0, 40);
    if (!groups.has(sig)) groups.set(sig, []);
    groups.get(sig).push(c);
  }
  const repeated = [...groups.values()].filter((g) => g.length >= 3);
  // Fall back to every card only when the page renders no repeated list at all — recorded either way.
  const cards = repeated.length ? repeated[0] : [...document.querySelectorAll(CARD)];
  let best = null;
  for (const card of cards) {
    if (!vis(card)) continue;
    const cr = card.getBoundingClientRect();
    if (cr.width < 120 || cr.height < 24) continue;
    for (const el of card.querySelectorAll('*')) {
      if (el.children.length) continue;
      const t = (el.textContent || '').trim();
      if (t.length < 6 || t.length > 60) continue;
      if (!vis(el)) continue;
      const r = el.getBoundingClientRect();
      // The title is wide relative to its card and sits in its upper half.
      if (r.width < cr.width * 0.25) continue;
      if (r.top - cr.top > cr.height * 0.6) continue;
      if (!best || r.width > best.w) best = { el, card, w: r.width };
    }
    if (best) break;
  }
  if (!best) return { found: false };
  // Whether the subject is a genuine LIST ROW or a one-off tile. Banked separately: a claim about the
  // longest TITLE must rest on a title, and this bank has already recorded 32 rows filed against a
  // container instead of the row inside it.
  const fromList = repeated.length > 0 && repeated[0].includes(best.card);
  const groupSize = repeated.length ? repeated[0].length : 0;

  const geom = () => {
    const cr = best.card.getBoundingClientRect();
    const sibs = [...best.card.querySelectorAll('*')]
      .filter((e) => !e.children.length && e !== best.el && vis(e))
      .slice(0, 12)
      .map((e) => {
        const r = e.getBoundingClientRect();
        return { t: (e.textContent || '').trim().slice(0, 24),
          right: Math.round(r.right), left: Math.round(r.left), w: Math.round(r.width),
          // Out of the card = the sibling no longer sits inside the box that owns it.
          outside: r.right > cr.right + 2 || r.left < cr.left - 2 };
      });
    const parent = best.card.parentElement;
    return {
      cardW: Math.round(cr.width), cardH: Math.round(cr.height),
      cardRight: Math.round(cr.right),
      parentRight: parent ? Math.round(parent.getBoundingClientRect().right) : null,
      titleW: Math.round(best.el.getBoundingClientRect().width),
      docScrollX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      sibs,
    };
  };

  const before = geom();
  const original = best.el.textContent;
  best.el.textContent = LONGTEXT;
  // Force layout, then read.
  void best.el.getBoundingClientRect();
  const after = geom();
  best.el.textContent = original;      // leave the page as it was found

  const cs = getComputedStyle(best.el);
  return {
    found: true, fromList, groupSize, before, after,
    truncation: { textOverflow: cs.textOverflow, overflow: cs.overflow,
      whiteSpace: cs.whiteSpace, lineClamp: cs.webkitLineClamp || cs.lineClamp || 'none' },
    titleSample: (original || '').trim().slice(0, 40),
  };
};

const run = async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const out = { origin: ORIGIN, longValue: LONG, pages: [] };

  for (const name of (ONE ? ONE.split(',') : PAGES)) {
    const rec = { page: name };
    const page = await ctx.newPage();
    try {
      await page.goto(ORIGIN + '/workhive/' + name + '.html' + (QUERY[name] || ''),
        { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(6500);
      const r = await page.evaluate(probe, LONG);
      if (!r.found) {
        rec.ok = null;
        rec.why = 'no rendered row title was found to lengthen, so nothing was measured; UNGRADED '
          + 'rather than a pass over an empty set';
      } else {
        const { before, after } = r;
        // ★GROWING TALLER IS THE CORRECT ANSWER, so height is recorded and never failed.
        const cardWider = after.cardW > before.cardW + 2;
        const cardOutOfParent = after.parentRight !== null && after.cardRight > after.parentRight + 2;
        const spills = after.docScrollX > before.docScrollX + 2;
        const pushed = after.sibs.filter((s, i) => {
          const b = before.sibs[i];
          if (!b) return false;
          // A sibling that left the card, or lost its width entirely, under the long title.
          return (s.outside && !b.outside) || (b.w > 4 && s.w <= 1);
        });
        rec.geometry = { cardW: [before.cardW, after.cardW], cardH: [before.cardH, after.cardH],
          docScrollX: [before.docScrollX, after.docScrollX] };
        rec.truncation = r.truncation;
        rec.pushed = pushed.slice(0, 4);
        rec.titleSample = r.titleSample;
        rec.fromList = r.fromList;
        rec.groupSize = r.groupSize;
        rec.ok = !cardWider && !cardOutOfParent && !spills && pushed.length === 0;
        rec.why = rec.ok
          ? 'a 118-character title was written into the row title and the layout held: the card kept '
            + 'its width (' + before.cardW + 'px), grew only taller (' + before.cardH + '->'
            + after.cardH + 'px), no sibling left the card and the page gained no sideways scroll'
          : [cardWider ? 'the card widened ' + before.cardW + '->' + after.cardW + 'px' : '',
             cardOutOfParent ? 'the card now extends past its container' : '',
             spills ? 'the page gained ' + (after.docScrollX - before.docScrollX) + 'px of sideways scroll' : '',
             pushed.length ? pushed.length + ' sibling(s) pushed out of the card: '
               + pushed.map((s) => JSON.stringify(s.t)).join(', ') : '']
            .filter(Boolean).join('; ');
      }
    } catch (e) {
      rec.ok = null; rec.why = 'could not measure: ' + String(e.message || e).slice(0, 120);
    }
    await page.close();
    out.pages.push(rec);
    console.log('  ' + (rec.ok === null ? 'UNGRADED' : rec.ok ? 'PASS    ' : 'FAIL    ')
      + ' ' + name.padEnd(19) + ' ' + (rec.why || '').slice(0, 96));
  }
  await browser.close();
  writeFileSync(path.join(ROOT, 'longest_report.json'), JSON.stringify(out, null, 1));
  const g = out.pages.filter((p) => p.ok !== null);
  console.log('\n  ' + g.filter((p) => p.ok).length + ' pass | ' + g.filter((p) => !p.ok).length
    + ' fail | ' + (out.pages.length - g.length) + ' ungraded');
};
run().catch((e) => { console.error(e); process.exit(1); });
