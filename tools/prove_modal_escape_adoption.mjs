// prove_modal_escape_adoption.mjs — half ONE of the CO `back_out` oracle for V2/V3 (the modal views).
//
// WHY THIS SHAPE INSTEAD OF DRIVING 17 MODALS THROUGH A BROWSER. Every V2/V3 modal in the bank is named
// in `page_bank_anatomy/*.json` with a `seen.ref` that gives its element id — but opening one needs its
// OPENER, and openers are per-page. The roadmap already records what guessing them costs: a generic
// label regex matched "Load more posts" instead of a composer, and dayplanner's "+ Add to my day" opens
// no modal at all. Nothing was written on those runs, and nothing was proven either.
//
// The platform makes a much better test available, because the way out of a modal is not per-page at
// all — it is ONE shared helper. `whModalA11y(el)` wires Escape-to-close and focus-restore, and
// inventory.html:583-589 registers all four of its modals through it in a single loop. So the question
// splits cleanly, and BOTH halves are needed — the `banner_adoption_is_not_write_refusal` lesson, where
// 14 of 17 writes fired into a dead network while the banner said the right thing:
//
//   HALF 1 (this file, static, all 22 pages): is each V2/V3 modal actually REGISTERED with the helper?
//           An unregistered modal has no Escape, no focus restore, and no keyboard way out — and that is
//           a real defect a browser walk of a *different* modal would never surface.
//   HALF 2 (tools/arc_u_focus_trap_probe.mjs, live): does the helper DELIVER Escape-closes +
//           focus-returns? Already proven there for a representative sheet. Adoption without behaviour is
//           a claim about source; behaviour without adoption is a claim about one lucky modal.
//
// This file is half 1 only, and says so on every row it produces. It reads source and touches nothing.
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { globSync } from 'fs';

const args = process.argv.slice(2);
const GATE = args.includes('--gate');

// The helper names that wire a keyboard way out. `wireSheetA11y` delegates to `whModalA11y`.
const WIRERS = ['whModalA11y', 'wireSheetA11y'];

const anat = globSync('page_bank_anatomy/*.json').sort();
const results = [];

for (const fp of anat) {
  const d = JSON.parse(readFileSync(fp, 'utf8'));
  const page = d.page || fp.split(/[/\\]/).pop().replace(/\.json$/, '');
  const file = `${page}.html`;
  if (!existsSync(file)) { results.push({ page, error: `${file} missing` }); continue; }
  const src = readFileSync(file, 'utf8');
  // Also read the page's sidecar .js — several pages keep their wiring there.
  const side = existsSync(`${page}.js`) ? readFileSync(`${page}.js`, 'utf8') : '';
  const hay = src + '\n' + side;

  const rec = { page, modals: [] };
  for (const v of (d.views || [])) {
    if (v.key !== 'V2' && v.key !== 'V3') continue;
    const ref = (v.seen && v.seen.ref) || '';
    // Only views the anatomy identifies as a real dialog with an id are in scope here. A tab or a data
    // state is a different question and is NOT silently folded in — it is recorded as out-of-scope with
    // its reason, so the denominator stays honest.
    const ids = [...ref.matchAll(/#([A-Za-z0-9_-]+)/g)].map((m) => m[1]);
    const isDialog = /role=dialog|aria-modal/i.test(ref);
    if (!ids.length || !isDialog) {
      rec.modals.push({ view: v.key, name: v.name, id: ids[0] || null, inScope: false,
                        why: !ids.length ? 'the anatomy names no element id for this view — it is a tab '
                                         + 'or a data state, not an overlay with its own exit'
                                         : 'the anatomy does not mark this view role=dialog/aria-modal, '
                                         + 'so its way out is the page-level affordance already '
                                         + 'measured at V1, not a modal Escape' });
      continue;
    }
    // Registered if any wirer is called with this id, or with a variable assigned from it, or the id
    // appears inside an array literal that is iterated into a wirer (the inventory.html:585 pattern).
    const id = ids[0];
    const direct = WIRERS.some((w) =>
      new RegExp(`${w}\\s*\\(\\s*document\\.getElementById\\(\\s*['"\`]${id}['"\`]`).test(hay)
      || new RegExp(`${w}\\s*\\(\\s*['"\`]#?${id}['"\`]`).test(hay)
      || new RegExp(`${w}\\s*\\(\\s*\\$\\(\\s*['"\`]#${id}['"\`]`).test(hay));
    // THE LOOP FORM — and the first version of this regex produced SIX FALSE FINDINGS, including one I
    // had already read with my own eyes. inventory.html:583-589 registers all four of its modals in one
    // pass:
    //     ['part-modal','use-modal','restock-modal','detail-modal'].forEach(function (id) {
    //       var el = document.getElementById(id);
    //       if (el) whModalA11y(el);
    //     });
    // The original pattern tried to capture the callback body as `([\s\S]{0,400}?)\)` — LAZY, so it
    // stopped at the FIRST `)` in the body, which is `document.getElementById(id)`. The capture ended
    // before `whModalA11y(el)` ever appeared, and the prover reported `#part-modal` as having no
    // keyboard way out. Balanced delimiters are not a job for a lazy regex. So: find the array literal
    // containing the id, then scan a WINDOW of the following source for a wirer name — no attempt to
    // parse the callback's extent, which is the part that cannot be done this way.
    let viaLoop = false;
    for (const m of hay.matchAll(/\[[^\]]*?\]\s*\.forEach\s*\(/g)) {
      const arr = m[0];
      if (!new RegExp(`['"\`]${id}['"\`]`).test(arr)) continue;
      const window_ = hay.slice(m.index, m.index + arr.length + 500);
      if (WIRERS.some((w) => window_.includes(w))) { viaLoop = true; break; }
    }
    // A PAGE THAT HAND-ROLLS THE BEHAVIOUR HAS NOT FAILED — and calling it a failure was this prover's
    // second false claim. After the loop-regex fix left `community`, `index` and `resume` as the only
    // three "with no registered keyboard way out", none of them calls the shared helper at all — but all
    // three implement it themselves. community.html:2822 says so outright ("and restores focus on close.
    // One trap at a time — sheets stack via Escape") with the handler at :2862-2864, and resume.html:2088
    // has its own `if (e.key !== 'Escape') return;`. So the honest finding is not "no way out", it is a
    // DIVERGENCE from the shared helper — the CENTRALIZE-FIRST class, three copies of one behaviour being
    // exactly what let the credits chip drift. And a page-level Escape handler is EVIDENCE that the page
    // implements this, not PROOF that it covers THIS modal, which only the live probe can settle. So a
    // hand-rolled page is UNGRADED with the divergence recorded, never failed and never passed.
    // THE THIRD FALSE CLASSIFICATION, AND THE ONE THAT MATTERED MOST: a page does not have to CALL the
    // helper to be wired to it. utils.js:2800-2830 (`whSheetA11y`) finds every `.sheet-overlay` and
    // `.modal-overlay` and passes it to `whModalA11y` — at load AND via a MutationObserver for overlays
    // injected later — explicitly so pages need no per-overlay call. So `#resume-manager`
    // (`class="sheet-overlay"`), `#thread-overlay`, `#composer-overlay` and `#signin-modal` are all
    // ALREADY wired, and reporting them as "hand-rolled" was reading the absence of a page-level call as
    // the absence of wiring. It also mattered practically: acting on that misreading, a focus-restore
    // repair was written into resume.html's own `closeResumeManager` — which Escape never calls, because
    // the shared helper owns it — and the probe correctly showed no change. Grepping for the CALL missed
    // the CONVENTION; the class on the element IS the registration.
    const autoWired = new RegExp(
      `id=["']${id}["'][^>]*class=["'][^"']*(?:sheet-overlay|modal-overlay)`
      + `|class=["'][^"']*(?:sheet-overlay|modal-overlay)[^"']*["'][^>]*id=["']${id}["']`).test(src);
    const ownEscape = /e\.key\s*[!=]==?\s*['"`]Escape['"`]|key\s*===?\s*['"`]Escape['"`]/.test(hay);
    rec.modals.push({ view: v.key, name: v.name, id, inScope: true,
                      registered: direct || viaLoop || autoWired,
                      autoWired, ownEscape,
                      how: direct ? 'named directly in a wirer call'
                         : viaLoop ? 'included in an id array iterated into a wirer'
                         : autoWired ? 'AUTO-WIRED by utils.js whSheetA11y — the element carries '
                                     + '.sheet-overlay/.modal-overlay, which the shared wirer sweeps at '
                                     + 'load and on mutation, so no page-level call is needed'
                         : ownEscape ? 'NOT via the shared helper — this page hand-rolls an Escape '
                                     + 'handler, so the live probe must confirm it covers this modal'
                         : null });
  }
  const scoped = rec.modals.filter((m) => m.inScope);
  rec.inScope = scoped.length;
  // Three outcomes, not two. NO WAY OUT is the only failure.
  rec.noWayOut = scoped.filter((m) => !m.registered && !m.ownEscape).map((m) => `${m.view} #${m.id}`);
  rec.handRolled = scoped.filter((m) => !m.registered && m.ownEscape).map((m) => `${m.view} #${m.id}`);
  rec.ok = !scoped.length ? null
         : rec.noWayOut.length ? false
         : rec.handRolled.length ? null            // needs the live probe — not a pass, not a failure
         : true;
  results.push(rec);
  const label = rec.ok === false ? 'FAIL'
              : rec.ok === true ? 'PASS'
              : scoped.length ? 'UNGRADED' : 'no-modal-view';
  console.log(`  ${page.padEnd(20)} ${label}  in-scope=${rec.inScope}`
    + (rec.noWayOut.length ? `  NO WAY OUT: ${rec.noWayOut.join(', ')}` : '')
    + (rec.handRolled.length ? `  hand-rolled (needs live probe): ${rec.handRolled.join(', ')}` : ''));
}

const graded = results.filter((r) => r.ok !== null && !r.error);
const bad = graded.filter((r) => !r.ok);
writeFileSync('modal_escape_adoption_report.json', JSON.stringify({
  half: '1 of 2 — ADOPTION only. Behaviour (Escape closes + focus returns) is proven live by '
      + 'tools/arc_u_focus_trap_probe.mjs; this file proves only that each modal is REGISTERED with the '
      + 'helper that provides it.',
  wirers: WIRERS,
  totals: { pages: results.length, graded: graded.length,
            modalsInScope: results.reduce((a, r) => a + (r.inScope || 0), 0),
            outOfScope: results.reduce((a, r) =>
              a + ((r.modals || []).filter((m) => !m.inScope).length), 0),
            failing: bad.length },
  pages: results,
}, null, 1));

const nModals = results.reduce((a, r) => a + (r.inScope || 0), 0);
console.log('\n  wrote modal_escape_adoption_report.json');
console.log(`  ${graded.length} page(s) graded, ${nModals} dialog view(s) in scope, ${bad.length} failing`);
if (!graded.length || !nModals) {
  console.log('  FAIL — NOTHING WAS MEASURED (0 graded pages or 0 modals in scope). Zero failures over '
    + 'an empty denominator is not a pass.');
} else if (bad.length) {
  console.log('  FAIL — dialog views with NO keyboard way out at all: '
    + bad.map((r) => `${r.page} (${r.noWayOut.join(', ')})`).join('; '));
} else {
  console.log(`  PASS — all ${graded.length} graded page(s) register their dialog views with the shared `
    + 'helper that wires Escape + focus-restore (ADOPTION half only)');
}
const diverge = results.filter((r) => (r.handRolled || []).length);
if (diverge.length) {
  console.log('\n  CENTRALIZE-FIRST divergence (recorded, NOT failed — these implement the behaviour '
    + 'themselves rather than through the shared helper, so the live probe must confirm each covers its '
    + 'own modal):');
  for (const r of diverge) console.log(`    ${r.page.padEnd(20)} ${r.handRolled.join(', ')}`);
}
if (GATE) process.exit(bad.length || !graded.length || !nModals ? 1 : 0);
