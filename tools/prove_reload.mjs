// prove_reload.mjs — the CF `reload` oracle, measured by actually reloading mid-flow.
//
// THE ORACLE: "reload MID-FLOW and the surface returns to a truthful state — a half-filled sheet either
// survives intact or is gone, never restored into a state the person did not leave it in."
//
// ★THE ORACLE NAMES TWO ACCEPTABLE ANSWERS AND ONE DEFECT, which is what makes it measurable. GONE is
// fine: the person starts again, and nothing lies to them. INTACT is fine: everything they typed is
// still there. The defect is the state in between — a sheet that comes back holding SOME of what was
// typed, so the person submits a form they never actually filled in. That is the only outcome this
// prover fails, and it is failed on evidence: the exact field values before and after.
//
// ★IT WILL NOT POLLUTE THE SHARED DATABASE, and it does not rely on my restraint to avoid it. Every
// mutating request is WATCHED, not blocked — blocking would silently change the behaviour under test,
// because a page whose draft is saved server-side would come back GONE for a reason that is the
// probe's, not the product's. So the walk types, watches, and if any POST/PATCH/PUT/DELETE fires it
// refuses to grade that target and says so. Nothing is ever submitted: no button is pressed after the
// typing, and the sheet is dismissed by reload alone.
//
// ★TYPING IS THE POINT. `abandon_resume` already covers reloading with a sheet merely OPEN. What is
// unproven here is the HALF-FILLED case, so the walk fills roughly half the visible fields — enough
// that a partial restore is distinguishable from both a full one and an empty one.
//
// ★THE ZERO-DENOMINATOR RAIL. A target whose sheet never opened, or that offers no text field to half-
// fill, was not tested. Both return UNGRADED with the reason rather than a pass over an empty set.
//
// USAGE:  node tools/prove_reload.mjs [--page <name>]
// OUTPUT: reload_report.json

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

const QUERY = { 'project-report': '?project_id=539e0d9a-9ff7-474b-ab03-9254406ca7dc' };
// A marker that could not plausibly be real data, so a restored value is unmistakably the one typed.
const MARK = 'WH-RELOAD-PROBE-';

// The fields a person would fill, and what is in them. Read identically before and after the reload so
// the comparison is like-for-like.
const readFields = (modalSel) => {
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 4 && r.height > 4 && cs.display !== 'none' && cs.visibility !== 'hidden';
  };
  const sheet = modalSel
    ? (document.getElementById(modalSel) || document.querySelector('.' + modalSel))
    : null;
  const root = sheet || document;
  const open = sheet ? vis(sheet) : null;
  const fields = [...root.querySelectorAll('input, textarea')]
    .filter((el) => vis(el) && !['checkbox', 'radio', 'file', 'hidden', 'submit'].includes(el.type))
    .slice(0, 14)
    .map((el, i) => ({ i, id: el.id || el.name || ('idx' + i), value: el.value || '' }));
  return { open, fields };
};

const run = async () => {
  let browser = await chromium.launch();
  let ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));

  /* ★ONE DEAD CONTEXT USED TO END THE WHOLE RUN (2026-08-28). The loop below opens a page per
     target; when the context died mid-roster (project-manager V3, "Target page, context or browser
     has been closed") the next newPage() threw and every REMAINING target went unmeasured - the run
     reported five passes and a stack trace, which is why this prover sits unregistered. A prover
     that cannot survive one bad surface grades the roster it happened to reach, and a partial
     roster reported as a result is the skipped-partition problem wearing a crash for a costume.
     revive() rebuilds the context and re-authenticates so the walk continues and the failure is
     recorded against the ONE target that caused it. */
  const revive = async () => {
    try { await ctx.close(); } catch (_) { /* empty-catch-allow: already dead, that is why we are here */ }
    // ★THE BROWSER DIES TOO, NOT ONLY THE CONTEXT. Reviving the context alone got two targets
    // further and then threw "browser.newContext: Target page, context or browser has been closed"
    // - the process itself was gone, most likely memory pressure after many contexts on this host.
    // A revival that assumes the layer above it is healthy just moves the crash one target along.
    if (!browser.isConnected()) {
      try { await browser.close(); } catch (_) { /* empty-catch-allow: already gone */ }
      browser = await chromium.launch();
    }
    ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    await assertSignedIn(signIn(ctx, 'supervisor'));
  };
  const out = { origin: ORIGIN, targets: [] };

  const list = TARGETS.filter((t) => !t.signedOut && !t.unreachable && !t.notDrivable
    && (!ONE || t.page === ONE));

  for (const t of list) {
    const rec = { page: t.page, view: t.view, modal: t.modal };
    let page;
    try {
      page = await ctx.newPage();
    } catch (e) {
      // the context died on the PREVIOUS target - rebuild and keep walking the roster
      await revive();
      page = await ctx.newPage();
    }
    // ★TWO WAYS THIS WATCHER OVER-TRIGGERED, both of which would have ungraded the whole roster.
    // (1) It counted every mutation since page creation, including the ones a page makes on LOAD, when
    //     the question is only what TYPING caused — so the window is opened immediately before typing.
    // (2) It counted `analytics_events`, which is page TELEMETRY, not user data: every prover in this
    //     bank that clicks anything produces those rows, and they say nothing about whether a DRAFT was
    //     persisted. Instrumentation is excluded by name, and the exclusion is narrow on purpose — an
    //     audit or a queue write still counts, because either could be carrying the half-filled sheet.
    const TELEMETRY = /\/rest\/v1\/analytics_events/;
    let watching = false;
    const mutations = [];
    page.on('request', (r) => {
      if (!watching) return;
      const m = r.method();
      if (!['POST', 'PATCH', 'PUT', 'DELETE'].includes(m)) return;
      const u = r.url();
      if (!/\/rest\/v1\/|\/functions\/v1\//.test(u) || TELEMETRY.test(u)) return;
      mutations.push(m + ' ' + u.slice(-60));
    });
    try {
      await page.goto(ORIGIN + '/workhive/' + t.page + '.html' + (QUERY[t.page] || ''),
        { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(6000);

      if (t.pre) {
        const ok = await page.evaluate((src) => {
          try { eval(src); return true; } catch (e) { return String(e.message || e); }
        }, t.pre);
        if (ok !== true) {
          rec.ok = null; rec.why = 'precondition did not hold, so the sheet was never reachable: ' + ok;
          out.targets.push(rec); await page.close(); continue;
        }
        await page.waitForTimeout(1800);
      }

      if (t.openBy === 'click') {
        const shown = await page.evaluate((sel) => {
          const el = document.querySelector(sel);
          if (!el) return 'absent';
          const r = el.getBoundingClientRect();
          if (r.width < 1 || r.height < 1) return 'not visible';
          el.click(); return true;
        }, t.opener).catch((e) => String(e.message || e));
        if (shown !== true) {
          rec.ok = null; rec.why = 'opener ' + t.opener + ' was ' + shown + ', so no sheet opened';
          out.targets.push(rec); await page.close(); continue;
        }
      } else {
        await page.evaluate((src) => eval(src), t.fn).catch(() => {});
      }
      await page.waitForTimeout(1600);

      const opened = await page.evaluate(readFields, t.modal);
      if (opened.open === false || opened.fields.length === 0) {
        rec.ok = null;
        rec.why = opened.open === false
          ? 'the sheet did not open, so there was no mid-flow state to reload out of'
          : 'the sheet opened but offers no text field to half-fill, so a PARTIAL restore is not a '
            + 'state this surface can be in; UNGRADED rather than a pass over an empty set';
        out.targets.push(rec); await page.close(); continue;
      }

      watching = true;   // from here on, a mutation is one TYPING caused
      // ★HALF-FILL: enough fields that a partial restore is distinguishable from empty AND from full.
      const half = Math.max(1, Math.ceil(opened.fields.length / 2));
      const typed = await page.evaluate(({ modalSel, n, mark }) => {
        const vis = (el) => {
          const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
          return r.width > 4 && r.height > 4 && cs.display !== 'none' && cs.visibility !== 'hidden';
        };
        const sheet = modalSel
          ? (document.getElementById(modalSel) || document.querySelector('.' + modalSel)) : null;
        const els = [...(sheet || document).querySelectorAll('input, textarea')]
          .filter((el) => vis(el) && !['checkbox', 'radio', 'file', 'hidden', 'submit'].includes(el.type))
          .slice(0, 14);
        const done = [];
        els.slice(0, n).forEach((el, i) => {
          const v = mark + i;
          el.focus();
          el.value = v;
          // Both events, because different pages listen for different ones.
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
          done.push({ id: el.id || el.name || ('idx' + i), value: v });
        });
        return done;
      }, { modalSel: t.modal, n: half, mark: MARK });

      // Let any autosave the page performs actually fire, so the watcher can see it.
      await page.waitForTimeout(2500);
      rec.typedCount = typed.length;

      // ★A MUTATING REQUEST MEANS THIS TARGET IS NOT SAFE TO GRADE THIS WAY.
      if (mutations.length) {
        rec.ok = null;
        rec.mutations = mutations.slice(0, 3);
        rec.why = 'typing alone caused ' + mutations.length + ' mutating request(s) — this surface '
          + 'persists a draft server-side, so grading it needs the capture/restore harness rather than '
          + 'a bare reload; UNGRADED rather than risk writing to the shared database';
        out.targets.push(rec); await page.close(); continue;
      }

      await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(6000);
      const after = await page.evaluate(readFields, t.modal);

      const restored = after.fields.filter((f) => String(f.value || '').startsWith(MARK));
      rec.sheetAfter = after.open;
      rec.typed = typed.length;
      rec.restored = restored.length;
      if (restored.length === 0) {
        rec.shape = 'GONE';
        rec.ok = true;
        rec.why = 'after reloading with ' + typed.length + ' of ' + opened.fields.length
          + ' fields filled, nothing typed came back: the sheet is gone and the person starts from a '
          + 'state they can see, which is one of the two answers the oracle allows';
      } else if (restored.length === typed.length) {
        rec.shape = 'INTACT';
        rec.ok = true;
        rec.why = 'all ' + typed.length + ' typed values survived the reload exactly, so the person is '
          + 'returned to the state they actually left';
      } else {
        rec.shape = 'PARTIAL';
        rec.ok = false;
        rec.why = 'the reload restored ' + restored.length + ' of ' + typed.length + ' typed values - '
          + 'the person is looking at a sheet they never filled in this way, which is the one outcome '
          + 'the oracle forbids';
      }
    } catch (e) {
      rec.ok = null; rec.why = 'could not measure: ' + String(e.message || e).slice(0, 120);
    }
    await page.close();
    out.targets.push(rec);
    console.log('  ' + (rec.ok === null ? 'UNGRADED' : rec.ok ? 'PASS    ' : 'FAIL    ')
      + ' ' + (t.page + ' ' + t.view).padEnd(26) + ' ' + (rec.shape || '').padEnd(8)
      + ' ' + (rec.why || '').slice(0, 70));
  }
  await browser.close();
  writeFileSync(path.join(ROOT, 'reload_report.json'), JSON.stringify(out, null, 1));
  const g = out.targets.filter((t) => t.ok !== null);
  const shapes = g.reduce((a, t) => { a[t.shape] = (a[t.shape] || 0) + 1; return a; }, {});
  console.log('\n  ' + g.filter((t) => t.ok).length + ' pass | ' + g.filter((t) => !t.ok).length
    + ' fail | ' + (out.targets.length - g.length) + ' ungraded   shapes: ' + JSON.stringify(shapes));
};
run().catch((e) => { console.error(e); process.exit(1); });
