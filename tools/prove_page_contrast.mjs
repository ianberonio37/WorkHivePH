// prove_page_contrast.mjs — measure BOTH contrast oracles on every production page, populated.
//
// WHY THIS EXISTS. 78 rows sat owed across the 22 page banks (contrast_wcag 44, contrast_apca 34)
// behind a recorded belief that "contrast is not computable from CSSOM here" — uncomposited alpha
// gave ratio 1.00, and a gradient blocked most text. That was true of the NAIVE probe that produced
// it. It is not true of this platform's instruments, which had already solved every part of it:
//
//   · live-state-runner.js::visual() composites alpha up the ancestor chain (_overlay), averages
//     gradient stops (_gradientAvg), resolves background-clip:text glyphs to the gradient's first
//     stop, excludes emoji-ONLY nodes while KEEPING numeric ones, scopes to document.body rather
//     than <main>, and reports `candidates`/`truncated` so a cap can never hide under "0 failing".
//     Its APCA maths is calibrated against APCA's published anchors to 2 decimals and is
//     fault-injected (all-white -> 88%, muted-grey -> 0%).
//   · axe-core judges WCAG 2.x contrast on the REAL rendering and, crucially, returns `incomplete`
//     rather than a verdict when it cannot see behind the text.
//
// So this file writes NO contrast maths of its own. It drives the two existing instruments and
// reports them side by side. A third implementation would be a third source of truth, which is the
// drift this bank exists to prevent.
//
// WHY POPULATED, AND WHY THAT IS NOT A DETAIL. tools/axe_scan.js runs each page against a static
// server with a seeded identity, on the reasoning that "contrast does not depend on data". It does
// not depend on data being CORRECT — but it very much depends on data being THERE. An unpopulated
// page has no KPI figures, no rows, no chips: exactly the small, tinted, dense text most at risk.
// Measuring contrast on an empty page is the empty-denominator shape wearing a different hat, so
// this driver signs in and waits for the page to settle before it measures anything.
//
// THE TWO LENSES DISAGREE BY DESIGN, and that is the point of running both. WCAG 2.x is a luminance
// quotient that OVERESTIMATES legibility on dark backgrounds — which is this entire platform. APCA
// scores perceived lightness against the text's real size and weight. Measured live, logbook scored
// WCAG 35/35 and APCA 2/8 on the SAME page. Neither is a substitute for the other, so each banks its
// own row, and a page that clears one is not credited with the other.
//
// USAGE:  node tools/prove_page_contrast.mjs [--page <name>]
// OUTPUT: page_contrast_report.json

import { chromium } from 'playwright';
import { writeFileSync, existsSync, readFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
// --teeth: plant a KNOWN-FAILING and a KNOWN-PASSING text node into the page before the existing
// measurement runs, then require the instrument to catch exactly the failing one. Without this a
// "0 failing" across 22 pages is unfalsifiable, and this file's only teeth claim was a COMMENT
// about live-state-runner.js's maths -- a claim about a different file, quoted rather than run.
// The pair is planted BEFORE the measure step and read out of its normal result, so there is no
// second copy of the contrast maths here (a third implementation is the drift this bank prevents).
const TEETH = args.includes('--teeth');

const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager',
  'dayplanner', 'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain',
  'voice-journal', 'assistant', 'community', 'public-feed', 'achievements',
  'engineering-design', 'resume', 'report-sender', 'project-report', 'analytics-report',
  // ★MARKETPLACE SURFACES, added 2026-08-20. BH-ui-visual in the marketplace bank is 35 rows,
  // ALL live-walk, and this prover is the only instrument that can settle them -- but its
  // roster was the 22 product pages. Safe to widen mid-suite ONLY because the contrast gates
  // were registered AFTER suite_v5 loaded its registry, so v5 never runs this prover.
  // Re-run clean and confirm --teeth still fires on these surfaces before banking.
  'marketplace', 'marketplace-seller', 'marketplace-seller-profile', 'platform-actions'];

const AXE = path.join(ROOT, 'tools', 'vendor', 'axe.min.js');

const run = async () => {
  const pages = ONE ? [ONE] : PAGES;
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  // ★STAMP THE MODE. A --teeth run PLANTS failing nodes and writes to this SAME report file,
// so a report on disk is meaningless unless you know which mode produced it. I read a
// teeth-run report as a measurement and reported the planted pair as real defects
// ('2 failing on logbook'). teethRun makes that mistake impossible to repeat.
const out = { origin: ORIGIN, viewport: 390, results: [], teethRun: TEETH };

  for (const name of pages) {
    const rec = { page: name };
    const page = await ctx.newPage();
    try {
      await page.goto(`${ORIGIN}/workhive/${name}.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      // Settle: the figures these oracles care about arrive after the first paint.
      await page.waitForTimeout(3500);

      // ── APCA, from the platform's own calibrated lens ───────────────────────────────────────────
      // ★PLANT BEFORE THE FIRST LENS RUNS. This block sat below, just above wcagComposited --
      // AFTER rec.apca had already measured all 305 nodes. So WCAG caught the violator and APCA
      // could not have: it never saw a node that did not exist yet. The teeth test read
      // 'apca=false' and I first blamed the probe's font size. A planted pair must exist before
      // EVERY lens it claims to exercise, not just the last one.
      if (TEETH) {
        // #6b6b6b on #5a5a5a at 12px/400 is ~1.3:1 -- far below the 4.5 bar and APCA's Lc 30 floor.
        // #ffffff on #000000 at 16px/400 is 21:1 -- above every floor either lens applies.
        await page.evaluate(() => {
          const mk = (id, label, fg, bg) => {
            const d = document.createElement('div');
            d.id = id; d.textContent = label;
            d.style.cssText = `color:${fg};background:${bg};font-size:18px;font-weight:400;padding:4px`;
            document.body.appendChild(d);
          };
          // 18px, NOT 12px. APCA's published table STARTS at 14px -- below that there is no
          // floor to apply, so the lens correctly declines to judge and the planted violator
          // went uncaught (wcag=true, apca=false) on the first run. A probe outside the
          // instrument's valid domain tests nothing. At 18px/400 the floor is a well-defined
          // Lc 75, and #6b6b6b on #5a5a5a is ~Lc 1.3.
          mk('wh-teeth-violator', 'teeth probe FAIL', '#6b6b6b', '#5a5a5a');
          mk('wh-teeth-satisfier', 'teeth probe PASS', '#ffffff', '#000000');
        });
      }
      rec.apca = await page.evaluate(async () => {
        const m = await import('/workhive/live-state-runner.js');
        const v = (m.visual() || {}).apca || {};
        return { ok: v.ok, measured: v.measured, failing: v.failing,
                 inconclusive: v.inconclusive, candidates: v.candidates,
                 truncated: v.truncated, worst: (v.worst || []).slice(0, 5) };
      });

      // ── WCAG 2.x, COMPOSITED ────────────────────────────────────────────────────────────────────
      // This is the probe that actually settles the contrast_wcag rows, because axe cannot (see
      // below). The logic is walk_owed_scenarios.mjs::PROBES.contrast_wcag, which carries the
      // corrections this platform paid for: composite the background up the ancestor chain, treat a
      // gradient behind the text as UNMEASURABLE rather than computing dark-on-dark and reporting a
      // ratio of exactly 1.0, and treat background-clip:text glyphs the same way.
      // ⚠ IT IS A COPY, AND THAT IS A REAL COST. walk_owed_scenarios.mjs is top-level
      // self-executing — importing it launches an entire marketplace walk — so it cannot be reused
      // as a module. Two copies of one probe WILL drift, which is the exact failure this bank was
      // built to catch. If a correction lands on either, it must land on both; the alternative is to
      // lift the probe into live-state-runner.js, which is deferred only because touching that file
      // expires every bank row anchored to it.
      rec.wcagComposited = await page.evaluate(() => {
        const srgb = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
        const lum = ([r, g, b]) => 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b);
        const parse = (s) => {
          const m = (s || '').match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/);
          return m ? [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]] : null;
        };
        const gradientBehind = (el) => {
          let cur = el;
          while (cur) {
            const cs = getComputedStyle(cur);
            if ((cs.backgroundImage || 'none') !== 'none') return true;
            const c = parse(cs.backgroundColor);
            if (c && c[3] >= 0.99) return false;
            cur = cur.parentElement;
          }
          return false;
        };
        const bgOf = (el) => {
          let cur = el, acc = null;
          while (cur) {
            const c = parse(getComputedStyle(cur).backgroundColor);
            if (c && c[3] > 0) {
              acc = acc === null ? c : [
                acc[0] + (c[0] - acc[0]) * (1 - acc[3]),
                acc[1] + (c[1] - acc[1]) * (1 - acc[3]),
                acc[2] + (c[2] - acc[2]) * (1 - acc[3]),
                acc[3] + c[3] * (1 - acc[3]),
              ];
              if (acc[3] >= 0.99) return acc;
            }
            cur = cur.parentElement;
          }
          return acc || [11, 15, 25, 1];
        };
        // Emoji-only nodes are excluded for the same reason the APCA lens excludes them: an emoji
        // paints in its own colours, not the element's. The test requires a pictograph AND no
        // alphanumeric, because \p{Emoji_Component} matches ASCII digits and the naive version
        // silently dropped every numeric-only KPI label.
        const PICT = /\p{Extended_Pictographic}/u, ALNUM = /[a-z0-9]/i;
        const fails = []; const unmeasurable = []; let measured = 0;
        for (const el of document.body.querySelectorAll('*')) {
          if (el.children.length) continue;
          const txt = (el.textContent || '').trim();
          if (txt.length < 1) continue;
          if (PICT.test(txt) && !ALNUM.test(txt)) continue;
          const rect = el.getBoundingClientRect();
          if (!(rect.width > 0 && rect.height > 0)) continue;
          const cs = getComputedStyle(el);
          if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue;
          const fg = parse(cs.color); if (!fg) continue;
          const clip = cs.webkitBackgroundClip || cs.backgroundClip;
          if (fg[3] === 0 || clip === 'text' || gradientBehind(el)) {
            unmeasurable.push(txt.slice(0, 40)); continue;
          }
          const bg = bgOf(el);
          const L1 = lum(fg), L2 = lum(bg);
          const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
          const px = parseFloat(cs.fontSize) || 16;
          const bold = (parseInt(cs.fontWeight, 10) || 400) >= 700;
          const large = px >= 24 || (bold && px >= 18.66);
          const need = large ? 3.0 : 4.5;
          measured++;
          if (ratio < need - 0.05) {
            fails.push({ txt: txt.slice(0, 40), ratio: +ratio.toFixed(2), need, px: Math.round(px) });
          }
        }
        return { measured, failing: fails.length, unmeasurable: unmeasurable.length,
                 worst: fails.sort((a, b) => a.ratio - b.ratio).slice(0, 5) };
      });

      // ── WCAG 2.x, from axe-core — kept as a CROSS-CHECK, not as the verdict ────────────────────
      // axe judges the real rendering and abstains honestly, which is exactly why it cannot settle
      // these rows on this platform: on a dark themed page with alpha and gradients it returns
      // `incomplete` for nearly everything it looks at (logbook: 41 incomplete, 1 pass, over 398
      // text nodes). A "0 violations" from axe here would be a green resting on a denominator of
      // one. Its ABSTENTION RATE is the useful signal and is recorded as such.
      if (existsSync(AXE)) {
        await page.addScriptTag({ content: readFileSync(AXE, 'utf8') });
        rec.wcag = await page.evaluate(async () => {
          // NO `resultTypes` FILTER. Passing one makes axe TRUNCATE every result type it does not
          // name to a single node — so an earlier run of this file reported "1 pass" on all 22
          // pages, a number that was an artifact of this option rather than a reading of anything.
          // A meaningless figure sitting in a report is a figure something downstream will
          // eventually bank, so the option is gone and the counts below are real.
          const r = await window.axe.run(document, {
            runOnly: { type: 'rule', values: ['color-contrast'] },
          });
          const flat = (arr) => arr.flatMap((v) => v.nodes.map((n) => ({
            target: (n.target || []).join(' '),
            msg: ((n.any && n.any[0] && n.any[0].message) || '').slice(0, 120),
          })));
          return {
            violations: flat(r.violations || []),
            // axe ABSTAINS rather than guessing when it cannot see behind the text. That bucket is
            // neither a pass nor a defect, and it is reported rather than folded into either.
            incomplete: flat(r.incomplete || []),
            passes: (r.passes || []).reduce((a, v) => a + v.nodes.length, 0),
          };
        });
      } else {
        rec.wcag = { unavailable: `axe not vendored at ${AXE}` };
      }

      // The honest denominator, recorded so a green can never rest on an empty page.
      rec.textNodes = await page.evaluate(() => {
        let n = 0;
        for (const el of document.body.querySelectorAll('*')) {
          if (!el.children.length && (el.textContent || '').trim().length >= 1) n++;
        }
        return n;
      });
      if (TEETH) {
        const w = (rec.wcagComposited || {}).worst || [];
        const a = (rec.apca || {}).worst || [];
        const hit = (arr, which) => arr.some((x) => (x.txt || '').includes('teeth probe ' + which));
        rec.teeth = {
          wcagCaught: hit(w, 'FAIL'),
          apcaCaught: hit(a, 'FAIL'),
          // The satisfier must NOT be reported. A lens that flags everything has no teeth either,
          // so this half is as load-bearing as the half that catches the violator.
          satisfierClean: !hit(w, 'PASS') && !hit(a, 'PASS'),
        };
        rec.teeth.ok = rec.teeth.wcagCaught && rec.teeth.apcaCaught && rec.teeth.satisfierClean;
      }
    } catch (e) {
      rec.error = String(e.message || e).slice(0, 200);
    }
    await page.close();
    out.results.push(rec);

    const a = rec.apca || {}, c = rec.wcagComposited || {}, w = rec.wcag || {};
    console.log(`  ${name.padEnd(19)} nodes=${String(rec.textNodes ?? '-').padStart(4)}  ` +
      `APCA ${String(a.failing ?? '-').padStart(3)}/${String(a.measured ?? '-').padEnd(3)}  ` +
      `WCAG ${String(c.failing ?? '-').padStart(3)}/${String(c.measured ?? '-').padEnd(3)} ` +
      `(unmeas ${String(c.unmeasurable ?? '-').padEnd(3)})  ` +
      `axe ${w.incomplete ? w.incomplete.length : '-'} incon/${w.passes ?? '-'} pass` +
      (rec.error ? `  ERROR ${rec.error}` : ''));
  }

  await browser.close();
  writeFileSync(path.join(ROOT, 'page_contrast_report.json'), JSON.stringify(out, null, 1));
  if (TEETH) {
    const t = out.results.filter((r) => r.teeth);
    const blunt = t.filter((r) => !r.teeth.ok);
    console.log(`
  TEETH: ${t.length - blunt.length}/${t.length} page(s) caught the planted violator on BOTH lenses`);
    for (const r of blunt) console.log(`    BLUNT ${r.page}: caughtFAIL wcag=${r.teeth.wcagCaught} apca=${r.teeth.apcaCaught}; satisfierClean=${r.teeth.satisfierClean}`);
    if (blunt.length) { console.log('  A 0-failing reading from this instrument cannot be banked.'); process.exitCode = 1; }
  }
  const bad = out.results.filter((r) => r.error).length;
  console.log(`\n  ${out.results.length} page(s) measured, ${bad} errored -> page_contrast_report.json`);
};

run().catch((e) => { console.error(e); process.exit(1); });
