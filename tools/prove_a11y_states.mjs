// prove_a11y_states.mjs — four hand-walked-twice families, promoted to a prover (A16.C4 rule of two):
//   focus_visible    keyboard focus is visible on every interactive element, including custom ones
//   reduced_motion   prefers-reduced-motion is honoured - no animation that ignores it
//   icon_only_name   an icon-only control has an accessible name that says what it DOES
//   no_raw_enum      no lowercase_with_underscores status reaches a person
//
// INSTRUMENT NOTES, each from a recorded lesson:
//  · Focus is walked with TRUSTED Tab presses — programmatic el.focus() never matches :focus-visible
//    in Chromium, so an evaluate()-driven walk would report every ring missing.
//  · "Visible focus" is a DELTA, not a property: an element whose box-shadow exists while blurred is
//    not showing focus. Each stop's focused style is compared against the SAME element unfocused
//    (snapshots stashed on window.__fvEls, diffed after the walk when all but the last are blurred).
//  · Reduced motion is measured as the RESULT: emulateMedia({reducedMotion:'reduce'}) BEFORE load,
//    then document.getAnimations() — only infinite/long-running animations still playing count; a
//    finished 200ms transition is not "ignoring" the preference.
//  · icon_only reuses CLARITY_PROBE (live_page_journeys.effort.mjs) — ancestor-aware visibility, the
//    same classifier the effort lens calibrated; no second definition to drift.
//  · no_raw_enum reads innerText OUTSIDE code/pre/script/style — a dev console legitimately shows
//    snake_case; a person-facing status must not.
//  · A SAMPLE is not "every": the focus walk caps at 25 stops and SAYS so in its verdict.
//
// NON-WRITING: navigation + Tab presses + DOM reads only.
import { chromium } from 'playwright';
import { writeFileSync, readdirSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
import { CLARITY_PROBE } from './live_page_journeys.effort.mjs';
import { TARGETS } from './dialog_targets.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

// The denominator is the page-bank roster itself — one cell per bank per family, no hand-kept list.
const PAGES = ONE ? [ONE.replace(/\.html$/, '')]
  : readdirSync('banks').filter((f) => f.endsWith('_live_mcp_bank.json'))
      .map((f) => f.replace(/_live_mcp_bank\.json$/, '')).sort();

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
await assertSignedIn(signIn(ctx, 'supervisor'));

const cells = [];
const push = (page, family, ok, verdict) => {
  // page may arrive as "page·V2" from the view pass — split it into structured fields so the
  // report's consumers match on (page, view, family) instead of parsing labels.
  const [pg0, view] = String(page).split('·');
  cells.push({ page: pg0, view: view || 'V1', family, ok, verdict });
  const tag = ok === true ? 'PASS' : ok === false ? 'FAIL' : 'n/a ';
  console.log(`  ${String(page).padEnd(20)} ${family.padEnd(16)} ${tag}  ${verdict.slice(0, 95)}`);
};

for (const pg of PAGES) {
  const page = await ctx.newPage();
  try {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto(`${ORIGIN}/${pg}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(3500);
    const landed = (page.url().split('/').pop() || '').replace(/\.html.*$/, '');
    if (landed !== pg) {
      for (const f of ['focus_visible', 'reduced_motion', 'icon_only_name', 'no_raw_enum']) {
        push(pg, f, null, `landed on ${landed}, not the page under test — ungraded`);
      }
      continue;
    }

    // reduced_motion — after settle, under the emulated preference, what is STILL animating?
    const anims = await page.evaluate(() => {
      const bad = [];
      for (const a of document.getAnimations()) {
        if (a.playState !== 'running') continue;
        const t = a.effect && a.effect.getTiming ? a.effect.getTiming() : {};
        const iters = t.iterations === undefined ? 1 : t.iterations;
        const total = (Number(t.duration) || 0) * (iters === Infinity ? Infinity : iters);
        if (iters === Infinity || total > 1500) {
          const el = a.effect && a.effect.target;
          bad.push((el && (el.id ? '#' + el.id : el.className && String(el.className).slice(0, 40) || el.tagName)) || 'unknown');
        }
      }
      return bad;
    });
    push(pg, 'reduced_motion', anims.length === 0,
      anims.length === 0 ? 'reduce emulated before load; no infinite or >1.5s animation still running after settle'
        : `${anims.length} animation(s) ignore prefers-reduced-motion: ${anims.slice(0, 4).join(', ')}`);

    // icon_only_name — the calibrated clarity classifier, ancestor-aware.
    const clar = await page.evaluate(CLARITY_PROBE);
    push(pg, 'icon_only_name', (clar.icon_only_unlabeled || 0) === 0,
      (clar.icon_only_unlabeled || 0) === 0
        ? 'every visible interactive control carries an accessible name (CLARITY_PROBE, ancestor-aware)'
        : `${clar.icon_only_unlabeled} icon-only control(s) with NO accessible name`);

    // no_raw_enum — innerText outside code/pre/script/style.
    const enums = await page.evaluate(() => {
      const clone = document.body.cloneNode(true);
      clone.querySelectorAll('code, pre, script, style, noscript, template').forEach((n) => n.remove());
      const text = clone.innerText || '';
      const hits = [...new Set((text.match(/\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g) || []))];
      return hits.slice(0, 10);
    });
    push(pg, 'no_raw_enum', enums.length === 0,
      enums.length === 0 ? 'no lowercase_with_underscores token in person-facing text (code/pre excluded)'
        : `raw token(s) reach the person: ${enums.slice(0, 5).join(', ')}`);

    // focus_visible — trusted Tab walk, focused-vs-unfocused delta per stop.
    await page.evaluate(() => {
      window.__fvEls = [];
      if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur();
    });
    const MAX_STOPS = 25;
    for (let i = 0; i < MAX_STOPS; i++) {
      await page.keyboard.press('Tab');
      const done = await page.evaluate(() => {
        const a = document.activeElement;
        if (!a || a === document.body || a === document.documentElement) return true;
        if (window.__fvEls.some((r) => r.el === a)) return true;   // wrapped around
        const s = getComputedStyle(a);
        window.__fvEls.push({
          el: a,
          label: a.id ? '#' + a.id : (a.tagName + (a.className ? '.' + String(a.className).split(' ')[0] : '')),
          focused: { outline: `${s.outlineStyle}/${s.outlineWidth}/${s.outlineColor}`, boxShadow: s.boxShadow, borderColor: s.borderColor },
        });
        return false;
      });
      if (done) break;
    }
    const fv = await page.evaluate(() => {
      const a = document.activeElement;
      if (a && a !== document.body) a.blur();
      const bare = [];
      let sampled = 0;
      for (const r of window.__fvEls) {
        sampled++;
        const s = getComputedStyle(r.el);
        const un = { outline: `${s.outlineStyle}/${s.outlineWidth}/${s.outlineColor}`, boxShadow: s.boxShadow, borderColor: s.borderColor };
        const delta = un.outline !== r.focused.outline || un.boxShadow !== r.focused.boxShadow
          || un.borderColor !== r.focused.borderColor;
        if (!delta) bare.push(r.label);
      }
      return { sampled, bare };
    });
    if (fv.sampled === 0) {
      push(pg, 'focus_visible', null, 'zero tab stops reached — nothing was measured, so nothing is claimed');
    } else {
      push(pg, 'focus_visible', fv.bare.length === 0,
        fv.bare.length === 0
          ? `all ${fv.sampled} sampled tab stops (trusted Tab, cap ${MAX_STOPS}) show a focus-style delta vs their unfocused state`
          : `${fv.bare.length} of ${fv.sampled} sampled stop(s) show NO visible focus change: ${fv.bare.slice(0, 4).join(', ')}`);
    }
  } catch (e) {
    for (const f of ['focus_visible', 'reduced_motion', 'icon_only_name', 'no_raw_enum']) {
      push(pg, f, null, `probe error — ${String(e).slice(0, 90)}`);
    }
  } finally {
    await page.close();
  }

  // ── V2/V3 PASS: the same four families, measured WITH THE VIEW OPEN and SCOPED to its root.
  // The shared dialog_targets roster supplies the open path (the same table the escape and layout
  // provers drive, so views cannot drift between provers). Scoping is what makes these the VIEW's
  // rows and not V1 measured twice: icon/enum scans read only inside the view root, and the focus
  // walk counts only stops INSIDE it (for dialogs the focus trap makes that the natural walk).
  // state-kind targets need their inject in a fresh context and are skipped here (their oracle set
  // is the state's, already covered by the escape prover); unreachable/notDrivable stay ungraded.
  for (const view of ['V2', 'V3']) {
    const t = TARGETS.find((x) => x.page === pg && x.view === view);
    const fams = ['focus_visible', 'reduced_motion', 'icon_only_name', 'no_raw_enum'];
    if (!t || t.kind === 'state' || t.notDrivable || t.unreachable) {
      const why = !t ? 'no target registered for this view'
        : t.kind === 'state' ? 'state view — its a11y is the page state, measured by the state provers'
        : 'not drivable read-only (roster fact)';
      for (const f of fams) push(`${pg}·${view}`, f, null, why);
      continue;
    }
    const vp = await ctx.newPage();
    try {
      await vp.emulateMedia({ reducedMotion: 'reduce' });
      await vp.goto(`${ORIGIN}/${pg}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
      await vp.waitForTimeout(3200);
      if (t.pre) {
        const pr = await vp.evaluate((code) => { try { eval(code); return 'ok'; } catch (e) { return 'threw: ' + String(e).slice(0, 80); } }, t.pre);
        await vp.waitForTimeout(1200);
        if (String(pr).startsWith('threw')) {
          for (const f of fams) push(`${pg}·${view}`, f, null, `precondition ${pr}`);
          continue;
        }
      }
      if (t.openBy === 'click' && t.opener) {
        try { await vp.click(t.opener, { timeout: 5000 }); } catch { /* measured below */ }
      } else if (t.fn) {
        await vp.evaluate((code) => { try { eval(code); } catch { /* measured below */ } }, t.fn);
      }
      await vp.waitForTimeout(900);
      const opened = await vp.evaluate((id) => {
        const el = document.getElementById(id);
        if (!el) return false;
        const s = getComputedStyle(el); const b = el.getBoundingClientRect();
        return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0;
      }, t.modal);
      if (!opened) {
        for (const f of fams) push(`${pg}·${view}`, f, null, `#${t.modal} did not open — ungraded, not failed`);
        continue;
      }

      const scoped = await vp.evaluate(({ id, probeSrc }) => {
        const root = document.getElementById(id);
        // reduced_motion — animations whose target sits inside the view root
        const anims = [];
        for (const a of document.getAnimations()) {
          if (a.playState !== 'running') continue;
          const el = a.effect && a.effect.target;
          if (!el || !root.contains(el)) continue;
          const t2 = a.effect.getTiming ? a.effect.getTiming() : {};
          const iters = t2.iterations === undefined ? 1 : t2.iterations;
          if (iters === Infinity || (Number(t2.duration) || 0) * iters > 1500) {
            anims.push(el.id ? '#' + el.id : el.tagName);
          }
        }
        // icon_only — CLARITY_PROBE logic, but querying inside the root only
        const probe = eval('(' + probeSrc + ')');
        const saved = document.querySelectorAll.bind(document);
        document.querySelectorAll = (sel) => root.querySelectorAll(sel);
        let clar;
        try { clar = probe(); } finally { document.querySelectorAll = saved; }
        // no_raw_enum — the root's own text, code/pre excluded
        const clone = root.cloneNode(true);
        clone.querySelectorAll('code, pre, script, style').forEach((n) => n.remove());
        const enums = [...new Set(((clone.innerText || '').match(/\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g) || []))].slice(0, 6);
        return { anims, iconOnly: clar.icon_only_unlabeled || 0, enums };
      }, { id: t.modal, probeSrc: CLARITY_PROBE.toString() });

      push(`${pg}·${view}`, 'reduced_motion', scoped.anims.length === 0,
        scoped.anims.length === 0 ? `no animation inside #${t.modal} ignores reduce`
          : `${scoped.anims.length} animation(s) in the open view ignore reduce: ${scoped.anims.slice(0, 3).join(', ')}`);
      push(`${pg}·${view}`, 'icon_only_name', scoped.iconOnly === 0,
        scoped.iconOnly === 0 ? `every visible control inside #${t.modal} carries an accessible name`
          : `${scoped.iconOnly} icon-only control(s) inside the open view lack a name`);
      push(`${pg}·${view}`, 'no_raw_enum', scoped.enums.length === 0,
        scoped.enums.length === 0 ? `no raw snake_case token inside #${t.modal}`
          : `raw token(s) inside the view: ${scoped.enums.slice(0, 4).join(', ')}`);

      // focus walk, counting only stops inside the view root
      await vp.evaluate(() => { window.__fvEls = []; });
      for (let i = 0; i < 15; i++) {
        await vp.keyboard.press('Tab');
        const done = await vp.evaluate((id) => {
          const root = document.getElementById(id);
          const a = document.activeElement;
          if (!a || a === document.body) return false;
          if (!root.contains(a)) return false;          // outside the view: skip, keep walking
          if (window.__fvEls.some((r) => r.el === a)) return true;   // wrapped
          const s = getComputedStyle(a);
          window.__fvEls.push({ el: a, label: a.id ? '#' + a.id : a.tagName,
            focused: { outline: `${s.outlineStyle}/${s.outlineWidth}`, boxShadow: s.boxShadow, borderColor: s.borderColor } });
          return false;
        }, t.modal);
        if (done) break;
      }
      const fv2 = await vp.evaluate(() => {
        const a = document.activeElement; if (a && a !== document.body) a.blur();
        const bare = []; let sampled = 0;
        for (const r of window.__fvEls) {
          sampled++;
          const s = getComputedStyle(r.el);
          const delta = `${s.outlineStyle}/${s.outlineWidth}` !== r.focused.outline
            || s.boxShadow !== r.focused.boxShadow || s.borderColor !== r.focused.borderColor;
          if (!delta) bare.push(r.label);
        }
        return { sampled, bare };
      });
      if (fv2.sampled === 0) {
        push(`${pg}·${view}`, 'focus_visible', null, 'no tab stop landed inside the view — nothing measured');
      } else {
        push(`${pg}·${view}`, 'focus_visible', fv2.bare.length === 0,
          fv2.bare.length === 0
            ? `all ${fv2.sampled} in-view tab stops show a focus-style delta`
            : `${fv2.bare.length} of ${fv2.sampled} in-view stop(s) show no focus change: ${fv2.bare.slice(0, 3).join(', ')}`);
      }
    } catch (e) {
      for (const f of fams) push(`${pg}·${view}`, f, null, `probe error — ${String(e).slice(0, 80)}`);
    } finally {
      await vp.close();
    }
  }
}
await browser.close();

const graded = cells.filter((c) => c.ok !== null);
const bad = graded.filter((c) => c.ok === false);
// A narrowed run writes a SEPARATE file (the journey prover's rule): a --page check finishing after
// a full walk must not replace the full roster's report with a 4-cell one.
const OUT = ONE ? 'a11y_states.partial.json' : 'a11y_states_report.json';
writeFileSync(OUT, JSON.stringify({
  totals: { cells: cells.length, graded: graded.length, failing: bad.length,
            ungraded: cells.length - graded.length },
  cells,
}, null, 1));
console.log(`\n  wrote ${OUT}`);
console.log(`  ${graded.length} of ${cells.length} cell(s) graded · ${bad.length} failing`);
if (GATE) process.exit(bad.length || !graded.length ? 1 : 0);
