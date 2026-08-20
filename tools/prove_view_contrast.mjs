// prove_view_contrast.mjs — contrast measured INSIDE each V2/V3 view, not across the page.
//
// WHY THIS EXISTS, AND WHY THE PAGE-LEVEL SWEEP COULD NOT DO IT. tools/prove_page_contrast.mjs
// measures each page in its default view and found the platform clean. It settles NOTHING here:
// every one of the 78 owed contrast rows in the page banks is authored against V2 or V3 — the
// dialogs — and their V1 siblings are already green. Banking a page-default reading onto a V2 row
// is the one-measurement-swept-two-views error that once put 14 V2 rows in this bank carrying V1's
// verdict. A view has to be read inside itself.
//
// SO: open each view through tools/dialog_targets.mjs — the same shared registry ten other provers
// use, so the view graded here is the view they grade — and scope both instruments to the dialog:
//
//   · APCA  — live-state-runner.js::visual(root). The lens took no root until this session; it now
//     accepts one and defaults to document.body, so every existing caller is unchanged. Its maths is
//     calibrated against APCA's published anchors and is fault-injected (measured live this session
//     on logbook: 0/44 baseline, 36/44 muted-grey, 1/44 all-white — monotonic, stable denominator).
//   · WCAG  — the composited probe, scoped to the dialog subtree.
//
// AN EMPTY DIALOG IS NOT A CLEAN DIALOG. Each view reports its own `measured` count and a view that
// measured nothing is UNGRADED, never green — the empty-denominator failure this bank exists to
// catch, and one that has already cost it once in this very family (six views whose focus oracle
// passed over zero controls).
//
// USAGE:  node tools/prove_view_contrast.mjs [--page <name>]
// OUTPUT: view_contrast_report.json

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
import { TARGETS } from './dialog_targets.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
// --teeth: MIRRORED from prove_page_contrast.mjs, because this file's own header states that a
// correction to one must land on the other -- and a declared mirror obligation that nobody checks
// is how the same defect survives in a sibling. Same planted pair, but appended INSIDE the dialog
// root, since every lens here is scoped to getElementById(id) and a node on document.body would
// simply not be measured (a teeth test that cannot fire is worse than none).
const TEETH = args.includes('--teeth');

// The composited WCAG probe, scoped. Same logic as prove_page_contrast.mjs — see the drift warning
// in that file's header; a correction to one must land on the other.
const WCAG_SCOPED = ({ id }) => {
  const root = document.getElementById(id);
  if (!root) return { error: 'root absent' };
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
  const PICT = /\p{Extended_Pictographic}/u, ALNUM = /[a-z0-9]/i;
  const fails = []; let unmeasurable = 0, measured = 0;
  for (const el of root.querySelectorAll('*')) {
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
    if (fg[3] === 0 || clip === 'text' || gradientBehind(el)) { unmeasurable++; continue; }
    const bg = bgOf(el);
    const L1 = lum(fg), L2 = lum(bg);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const px = parseFloat(cs.fontSize) || 16;
    const bold = (parseInt(cs.fontWeight, 10) || 400) >= 700;
    const large = px >= 24 || (bold && px >= 18.66);
    const need = large ? 3.0 : 4.5;
    measured++;
    if (ratio < need - 0.05) fails.push({ txt: txt.slice(0, 40), ratio: +ratio.toFixed(2), need, px: Math.round(px) });
  }
  return { measured, failing: fails.length, unmeasurable,
           worst: fails.sort((a, b) => a.ratio - b.ratio).slice(0, 5) };
};

const run = async () => {
  const targets = TARGETS.filter((t) => !t.notDrivable && (!ONE || t.page === ONE));
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  // A SIGNED-OUT TARGET NEEDS A SIGNED-OUT CONTEXT, and getting this wrong looks like a page defect.
  // index is two products behind one URL: an inline script sets html.wh-signed-in before <body>
  // parses, so #mkt-wrap (V2, the anon landing) is HIDDEN for a signed-in visitor and #signin-modal
  // (V3) is never reachable. Driving them from the signed-in context reported "it did not open" —
  // an instrument limitation wearing the costume of a broken opener. The registry already marks
  // these `signedOut`; it was this prover that ignored the flag.
  const anonCtx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  // ★STAMP THE MODE. A --teeth run PLANTS failing nodes and writes to this SAME report file,
// so a report on disk is meaningless unless you know which mode produced it. I read a
// teeth-run report as a measurement and reported the planted pair as real defects
// ('2 failing on logbook'). teethRun makes that mistake impossible to repeat.
const out = { origin: ORIGIN, viewport: 390, targets: [], teethRun: TEETH };

  for (const t of targets) {
    const rec = { page: t.page, view: t.view, modal: t.modal, signedOut: !!t.signedOut };
    const page = await (t.signedOut ? anonCtx : ctx).newPage();
    try {
      await page.goto(`${ORIGIN}/workhive/${t.page}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
      await page.waitForTimeout(3000);
      if (t.pre) {
        const pr = await page.evaluate((c) => {
          try { eval(c); return 'ok'; } catch (e) { return 'threw: ' + String(e.message || e).slice(0, 80); }
        }, t.pre);
        if (String(pr).startsWith('threw')) throw new Error(`precondition ${pr}`);
        await page.waitForTimeout(1500);
      }
      if (!t.mayStartOpen) {
        if (t.openBy === 'click') {
          const shown = await page.evaluate((sel) => {
            const el = document.querySelector(sel); if (!el) return false;
            const b = el.getBoundingClientRect(); const s = getComputedStyle(el);
            return s.display !== 'none' && s.visibility !== 'hidden' && b.height > 0;
          }, t.opener);
          if (!shown) throw new Error(`opener ${t.opener} is absent or not visible`);
          await page.click(t.opener, { timeout: 4000 });
        } else {
          const fr = await page.evaluate((c) => {
            try { eval(c); return 'ok'; } catch (e) { return 'threw: ' + String(e.message || e).slice(0, 80); }
          }, t.fn);
          if (String(fr).startsWith('threw')) throw new Error(`opener fn ${fr}`);
        }
        await page.waitForTimeout(1200);
      }
      const state = await page.evaluate(({ id }) => {
        const d = document.getElementById(id);
        if (!d) return 'absent';
        const s = getComputedStyle(d); const b = d.getBoundingClientRect();
        return (s.display !== 'none' && s.visibility !== 'hidden' && b.height > 0) ? 'open' : 'closed';
      }, { id: t.modal });
      if (state !== 'open') throw new Error(`#${t.modal} is ${state} — it did not open`);

      if (TEETH) {
        await page.evaluate((id) => {
          const root = document.getElementById(id);
          if (!root) return;
          const mk = (label, fg, bg) => {
            const d = document.createElement('div');
            d.textContent = label;
            d.style.cssText = `color:${fg};background:${bg};font-size:18px;font-weight:400;padding:4px`;
            root.appendChild(d);
          };
          mk('teeth probe FAIL', '#6b6b6b', '#5a5a5a');   // ~1.3:1 -- under every floor
          mk('teeth probe PASS', '#ffffff', '#000000');   // 21:1  -- over every floor
        }, t.modal);
      }
      const lens = await page.evaluate(async ({ id }) => {
        const m = await import('/workhive/live-state-runner.js');
        const el = document.getElementById(id);
        const v = m.visual(el) || {};
        const pick = (o) => o ? { ok: o.ok, measured: o.measured, failing: o.failing,
                                  inconclusive: o.inconclusive, worst: (o.worst || []).slice(0, 4) } : null;
        return { apca: pick(v.apca), wcag: pick(v.wcag) };
      }, { id: t.modal });
      rec.apca = lens.apca;
      // WCAG COMES FROM THE LENS NOW, NOT THE STANDALONE PROBE. The standalone probe abstains inside
      // every dialog on this platform — a translucent gradient card over a translucent scrim leaves
      // no flat second colour for a ratio — which left 17 bank rows owed and, worse, removed the
      // small-text backstop from exactly the views that most need it. The lens resolves the backdrop
      // with _effectiveBg(), which averages the gradient's stops, so it measures where the probe
      // cannot: 61 samples inside #part-modal against the probe's 0.
      rec.wcag = lens.wcag;
      // The standalone probe is kept as a CROSS-CHECK and its abstention rate is itself the evidence
      // that the lens route was necessary.
      rec.wcagComposited = await page.evaluate(WCAG_SCOPED, { id: t.modal });
    } catch (e) {
      rec.error = String(e.message || e).slice(0, 160);
    }
    await page.close();
    if (TEETH) {
      const hit = (arr, which) => (arr || []).some((x) => (x.txt || '').includes('teeth probe ' + which));
      const w = (rec.wcagComposited || {}).worst || [], a = (rec.apca || {}).worst || [];
      rec.teeth = {
        wcagCaught: hit(w, 'FAIL'), apcaCaught: hit(a, 'FAIL'),
        satisfierClean: !hit(w, 'PASS') && !hit(a, 'PASS'),
      };
      rec.teeth.ok = rec.teeth.wcagCaught && rec.teeth.apcaCaught && rec.teeth.satisfierClean;
    }
    out.targets.push(rec);

    const a = rec.apca || {}, w = rec.wcag || {};
    const grade = rec.error ? 'ERR ' : ((a.measured || 0) + (w.measured || 0) === 0 ? 'NONE'
      : ((a.failing || 0) + (w.failing || 0) === 0 ? 'PASS' : 'FAIL'));
    console.log(`  ${grade}  ${t.page.padEnd(19)} ${t.view} #${(t.modal || '').padEnd(22)} ` +
      `APCA ${a.failing ?? '-'}/${a.measured ?? '-'}  WCAG ${w.failing ?? '-'}/${w.measured ?? '-'}` +
      (rec.error ? `  ${rec.error}` : ''));
  }

  await browser.close();
  writeFileSync(path.join(ROOT, 'view_contrast_report.json'), JSON.stringify(out, null, 1));
  if (TEETH) {
    // A view that never OPENED has no surface a planted violator could land on, so it is
    // UNGRADED, not BLUNT. hive/V2 is the case: the target itself records that the handover
    // feature has no reachable entry point (.handover-btn lives inside #handover-panel, which
    // ships class="hidden"), so its planted node was unmeasurable by construction. Counting it
    // as a blunt instrument blocked registration for a PRODUCT gap rather than an instrument
    // fault -- two different truth conditions. BLUNT now means only: the view opened, text was
    // measurable, and the violator STILL was not caught.
    const measurable = (r) => ((r.apca?.measured || 0) + (r.wcag?.measured || 0)) > 0;
    const all = out.targets.filter((r) => r.teeth);
    const unmeasurable = all.filter((r) => !r.teeth.ok && !measurable(r));
    const t = all.filter((r) => measurable(r) || r.teeth.ok);
    const blunt = t.filter((r) => !r.teeth.ok);
    for (const r of unmeasurable) {
      console.log(`    UNGRADED ${r.page}/${r.view}: the view never opened, so the planted violator ` +
        `had no surface to land on${r.unreachable ? " (target records it as unreachable)" : ""}`);
    }
    console.log(`  TEETH: ${t.length - blunt.length}/${t.length} view(s) caught the planted violator on BOTH lenses`);
    for (const r of blunt) console.log(`    BLUNT ${r.page}/${r.view}: caughtFAIL wcag=${r.teeth.wcagCaught} apca=${r.teeth.apcaCaught}; satisfierClean=${r.teeth.satisfierClean}`);
    if (blunt.length) { console.log('  A 0-failing reading from this instrument cannot be banked.'); process.exitCode = 1; }
  }
  const graded = out.targets.filter((r) => !r.error && ((r.apca?.measured || 0) + (r.wcag?.measured || 0)) > 0);
  const failing = graded.filter((r) => (r.apca?.failing || 0) + (r.wcag?.failing || 0) > 0);
  console.log(`\n  ${graded.length} of ${out.targets.length} view(s) carried text to measure · ${failing.length} failing`);
  console.log('  -> view_contrast_report.json');
};

run().catch((e) => { console.error(e); process.exit(1); });
