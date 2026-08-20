// prove_source_chip.mjs — does a surface's provenance chip name the sources it ACTUALLY read?
//
// THE ORACLE. A source chip is a promise: "this number came from these feeds." It is worth more than
// most UI text, because a reader uses it to decide whether to trust a figure — and a chip that names
// a feed the page never queried is worse than no chip at all, since it manufactures confidence.
//
// WHY A NEW DRIVER RATHER THAN A NEW PROBE. tools/walk_owed_scenarios.mjs already carries a correct
// source_chip_true probe, including the correction that matters: the HOST (#<page>-source-chip) and
// the chip it renders (.wh-source-chip) both match the selector and occupy the identical rect, so a
// naive count reports two chips where one is on screen; only the outermost of any nested pair counts.
// That file is top-level self-executing over the MARKETPLACE job list, so it cannot be imported — the
// probe body is reproduced here with that lineage stated, the same drift warning as the WCAG probe.
//
// ★SCOPED PER VIEW, DELIBERATELY, AND THIS IS THE PART LEARNED THE HARD WAY THIS SESSION. The bank
// authors this oracle against V1 AND V2. A page-level reading settles V1 — the default view — and says
// NOTHING about V2, which on most pages is a dialog with its own chip or no chip at all. Crediting a
// V2 row with a V1 reading is the one-measurement-swept-two-views error that has already put rows in
// this bank carrying another view's verdict. So V1 is read at page scope and V2 is read INSIDE the
// opened view, through the shared tools/dialog_targets.mjs registry.
//
// WHAT COUNTS AS A PASS, AND WHAT DELIBERATELY DOES NOT:
//   · no chip on screen        -> NOT a pass. The surface makes no provenance claim, which is not the
//                                 same as making a true one. Recorded as `no-claim`.
//   · chip names a relation the page did not request -> FAIL, with the unmatched name.
//   · chip names only relations actually requested   -> PASS.
// Relations are captured from the NETWORK (PostgREST /rest/v1/<relation>), not from source, because
// what a page reads at runtime is the only thing a provenance claim can be checked against.
//
// USAGE:  node tools/prove_source_chip.mjs [--page <name>]
// OUTPUT: source_chip_report.json

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

const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager',
  'dayplanner', 'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain',
  'voice-journal', 'assistant', 'community', 'public-feed', 'achievements',
  'engineering-design', 'resume', 'report-sender', 'project-report', 'analytics-report'];

const READ_CHIPS = ({ rootId }) => {
  const root = rootId ? document.getElementById(rootId) : document.body;
  if (!root) return { rootMissing: true };
  const chips = [...root.querySelectorAll('[id$="source-chip"], [class*="source-chip"]')]
    .filter((el) => (el.offsetParent || el.getClientRects().length))
    .filter((el, _i, arr) => !arr.some((o) => o !== el && o.contains(el)));
  return { chips: chips.map((c) => (c.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean) };
};

const grade = (chips, requested) => {
  if (!chips.length) {
    return { ok: false, kind: 'no-claim',
             note: 'no source chip is on screen, so this surface makes no provenance claim at all — '
                 + 'which is not the same as making a true one, and is not banked as a pass' };
  }
  // A chip names feeds in friendly prose. The check is deliberately one-directional: every RELATION
  // TOKEN the chip mentions must correspond to something the page actually requested. It does not
  // demand the chip list every relation — a chip that summarises is fine; a chip that INVENTS is not.
  const text = chips.join(' | ').toLowerCase();
  const tokens = [...new Set((text.match(/[a-z][a-z0-9_]{4,}/g) || []))];
  const reqNorm = requested.map((r) => r.toLowerCase());
  // ★A RELATION TOKEN MUST LOOK LIKE A TABLE, NOT LIKE ENGLISH. The first version of this regex
  // included bare `^logbook$` and `^assets$`, and both asset-hub and analytics were reported as
  // naming an unread feed on the strength of the word "logbook" inside ordinary prose — "Based on
  // your asset records, risk scores, logbook, failure analysis". That is a chip describing FEATURES
  // in a sentence a person can read, not asserting a table name, and analytics is right on its own
  // terms: it reads analytics_snapshots, a snapshot DERIVED from logbook data, which is exactly what
  // "saved snapshot ... based on your logbook" says. Two manufactured findings, from a keyword match
  // over human prose — the same shape as scoring a page's own helper text as a failure message.
  // So a claim is only counted when the token is unmistakably schema-shaped: a v_ prefix, a _truth
  // suffix, or a known table prefix followed by an underscore. Bare English words never qualify.
  const looksLikeRelation = (t) => /^v_[a-z0-9_]+$|_truth$|^(pm|hive|community|project|inventory|resume|skill|alert|asset|schedule|logbook)_[a-z0-9_]+$/.test(t);
  const claimed = tokens.filter(looksLikeRelation);
  const unmatched = claimed.filter((t) => !reqNorm.some((r) => r === t || r.includes(t) || t.includes(r)));
  return {
    ok: unmatched.length === 0,
    kind: unmatched.length ? 'names-unread-feed' : 'true',
    claimedRelations: claimed, unmatched,
    note: unmatched.length
      ? `the chip names ${unmatched.join(', ')}, which this surface never requested`
      : (claimed.length ? 'every relation the chip names was actually requested by this surface'
                        : 'the chip is prose and names no relation token; nothing false is claimed'),
  };
};

const run = async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const anonCtx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const out = { origin: ORIGIN, results: [] };
  const pages = ONE ? [ONE] : PAGES;

  for (const name of pages) {
    // ── V1: the page's own default view ────────────────────────────────────────────────────────────
    {
      const rec = { page: name, view: 'V1' };
      const page = await ctx.newPage();
      const requested = new Set();
      page.on('request', (req) => {
        const m = /\/rest\/v1\/(?:rpc\/)?([a-zA-Z0-9_]+)/.exec(req.url());
        if (m) requested.add(m[1]);
      });
      try {
        await page.goto(`${ORIGIN}/workhive/${name}.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(3500);
        const r = await page.evaluate(READ_CHIPS, { rootId: null });
        rec.requested = [...requested];
        rec.chips = r.chips || [];
        Object.assign(rec, grade(rec.chips, rec.requested));
      } catch (e) { rec.error = String(e.message || e).slice(0, 160); }
      await page.close();
      out.results.push(rec);
    }

    // ── V2: the registry's second view, read INSIDE itself ─────────────────────────────────────────
    const t = TARGETS.find((x) => x.page === name && x.view === 'V2' && !x.notDrivable);
    if (t) {
      const rec = { page: name, view: 'V2', modal: t.modal };
      const page = await (t.signedOut ? anonCtx : ctx).newPage();
      const requested = new Set();
      page.on('request', (req) => {
        const m = /\/rest\/v1\/(?:rpc\/)?([a-zA-Z0-9_]+)/.exec(req.url());
        if (m) requested.add(m[1]);
      });
      try {
        await page.goto(`${ORIGIN}/workhive/${name}.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(3000);
        if (t.pre) {
          await page.evaluate((c) => { try { eval(c); } catch (e) { /* reported via open check */ } }, t.pre);
          await page.waitForTimeout(1500);
        }
        if (!t.mayStartOpen) {
          if (t.openBy === 'click') await page.click(t.opener, { timeout: 4000 });
          else await page.evaluate((c) => { try { eval(c); } catch (e) { /* reported below */ } }, t.fn);
          await page.waitForTimeout(1200);
        }
        const state = await page.evaluate(({ id }) => {
          const d = document.getElementById(id); if (!d) return 'absent';
          const s = getComputedStyle(d); const b = d.getBoundingClientRect();
          return (s.display !== 'none' && s.visibility !== 'hidden' && b.height > 0) ? 'open' : 'closed';
        }, { id: t.modal });
        if (state !== 'open') throw new Error(`#${t.modal} is ${state} — it did not open`);
        const r = await page.evaluate(READ_CHIPS, { rootId: t.modal });
        rec.requested = [...requested];
        rec.chips = r.chips || [];
        Object.assign(rec, grade(rec.chips, rec.requested));
      } catch (e) { rec.error = String(e.message || e).slice(0, 160); }
      await page.close();
      out.results.push(rec);
    } else {
      out.results.push({ page: name, view: 'V2', skipped: 'no drivable V2 in dialog_targets.mjs' });
    }

    for (const r of out.results.filter((x) => x.page === name)) {
      console.log(`  ${(r.kind || (r.error ? 'ERROR' : r.skipped ? 'skip' : '?')).padEnd(17)} ` +
        `${name.padEnd(19)} ${r.view}  chips=${(r.chips || []).length} ` +
        `read=${(r.requested || []).length}` +
        (r.unmatched && r.unmatched.length ? `  UNMATCHED ${r.unmatched.join(',')}` : '') +
        (r.error ? `  ${r.error}` : ''));
    }
  }

  await browser.close();
  writeFileSync(path.join(ROOT, 'source_chip_report.json'), JSON.stringify(out, null, 1));
  const graded = out.results.filter((r) => r.kind);
  console.log(`\n  ${graded.length} view(s) graded · ${graded.filter((r) => r.ok).length} true · ` +
    `${graded.filter((r) => r.kind === 'no-claim').length} make no claim · ` +
    `${graded.filter((r) => r.kind === 'names-unread-feed').length} name an unread feed`);
};

run().catch((e) => { console.error(e); process.exit(1); });
