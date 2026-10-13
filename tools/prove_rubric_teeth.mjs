// prove_rubric_teeth.mjs - the rubric's blind-spot TEETH (Wave 4, 2026-09-14).
//
// 118 of 119 public pages read green on V1 while a person on a phone saw overlap
// ([[feedback_a_gates_blind_spot_is_a_green_light]]): V1 excluded fixed/sticky chrome and the hub/companion shell
// as "by design" and had no occlusion check at all, and overflow was measured only at page level. This wave gave
// V1 an OCCLUSION branch (document.elementFromPoint at a control's centre must be the control) and added R6
// (element overflow inside its clipping container). A gate that only ever passes is a no-op
// ([[feedback_a_mutation_score_is_the_only_teeth_metric]]), so before the two dims bank a single finding they are
// asked to bite, deterministically, on synthetic pages whose truth is known:
//
//   occluded  - a fixed 56px FAB sitting ON the Save button, and a 420px box inside a 300px overflow:hidden card
//               -> V1 MUST fail naming the FAB, R6 MUST fail naming the box
//   clean     - the same 56px companion FAB in the corner covering nothing, every box inside its card
//               -> V1 and R6 MUST pass (the control is a false-positive check, without which "refuse everything"
//                  would look like a working detector)
//   modal     - a control UNDER an open aria-modal dialog is covered BY DESIGN -> V1 MUST pass (the dialog's own
//               Close button is the reachable control)
//
//   node tools/prove_rubric_teeth.mjs --self-test
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';

const RUBRIC = readFileSync('survey_ufai_rubric.js', 'utf8');
const HEAD = '<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width"><style>body{margin:0;font-family:sans-serif}main{padding:16px 16px 120px}.card{border:1px solid #ccc;padding:12px;margin:12px 0;overflow:hidden;width:300px}.fab{position:fixed;right:16px;bottom:16px;width:56px;height:56px;border-radius:50%;background:#e33;color:#fff;z-index:1000;border:0}</style></head><body>';
const PAGES = {
  occluded: HEAD + '<main><h1>Synthetic occlusion and overflow</h1><p>A card spilling under overflow:hidden and a FAB sitting on the Save button.</p>'
    + '<div class="card" id="card"><div id="wide" style="width:420px;height:40px;background:#eee">too wide for its card</div></div>'
    + '<p><a href="#a">A link</a> and <button id="plain">Plain button</button></p>'
    + '<button id="save" style="position:fixed;right:20px;bottom:24px;height:40px;width:80px">Save</button></main>'
    + '<button class="fab" id="fab" aria-label="Open companion">+</button></body></html>',
  clean: HEAD + '<main><h1>Synthetic clean page</h1><p>A revealed 56px companion FAB in the corner, covering nothing.</p>'
    + '<div class="card" id="card"><div style="width:200px;height:40px;background:#eee">fits its card</div></div>'
    + '<p><a href="#a">A link</a> <button id="save">Save</button></p></main>'
    + '<button class="fab" id="fab" aria-label="Open companion">+</button></body></html>',
  modal: HEAD + '<main><h1>Synthetic modal page</h1><p>A control under an open dialog is covered by design.</p>'
    + '<p><button id="under">Under the dialog</button></p></main>'
    + '<div role="dialog" aria-modal="true" id="dlg" style="position:fixed;inset:0;background:rgba(0,0,0,.4)"><div style="background:#fff;margin:120px 24px;padding:16px"><h2>Confirm</h2><p>Sure?</p><button id="close">Close</button></div></div></body></html>',
  // ★2026-10-13: a cover found by climbing to a chrome-looking ANCESTOR named the page's own <main id="wh-main-content">
  // (assistant, 226 rows). A veil inside main sits on the summary: V1 must fail naming the veil, never wh-main-content.
  ancestor: HEAD + '<main id="wh-main-content" style="position:relative"><h1>Synthetic covered summary</h1>'
    + '<details><summary id="sum">How this page works</summary><p>Help text.</p></details>'
    + '<div class="veil" style="position:absolute;left:0;right:0;top:40px;height:120px;background:rgba(0,0,0,.05)"></div></main></body></html>',
  // ★2026-10-13: a <br> added no whitespace in the text B3 reads, so a sentence and the link on the next line merged
  // (project-report: "...then Print Report.Go to Project Manager"). 16 words, <br>, a 9-word link: merged they are one
  // 25-word sentence; a reader sees two lines. B3 must count no sentence over 20 words.
  // ★2026-10-13: a summary NESTED inside a closed disclosure is hidden, and Chrome still lays it out, so V1 found the
  // panel painted at its centre and called it covered (assistant: the help twin inside the closed scope disclosure).
  // V1 must pass: nothing a person can see is covered.
  nested: HEAD + '<main><h1>Synthetic closed disclosure</h1><details id="outer"><summary>Scope of answers</summary>'
    + '<p>Inside the closed outer disclosure.</p><details id="inner"><summary id="innersum">How this page works</summary>'
    + '<p>Help text.</p><p><a href="#mail">admin@example.com</a></p></details></details>'
    + '<section style="background:#234;padding:80px 16px;margin-top:0"><p>Panel text that really is painted here.</p></section></main></body></html>',
  // ★2026-10-13: B4 read a middot-separated chip line as one 38-word sentence (hive readiness). The meta line must
  // pass; a real 38-word sentence in the same disclosure must still fail.
  b4meta: HEAD + '<main><h1>Synthetic readiness</h1><details open><summary>How we compute hive readiness</summary>'
    + '<p>Live · updates automatically · as of 13:59 PHT · Based on your hive readiness snapshot · Weighted: Process 25%'
    + ' · Data 20% · Resilience 15% · Leadership 25% · Culture 15% of the score</p></details></main></body></html>',
  b4long: HEAD + '<main><h1>Synthetic readiness</h1><details open><summary>How we compute hive readiness</summary>'
    + '<p>The readiness score is calculated by combining the weighted process, data, resilience, leadership and culture'
    + ' dimension scores that are recomputed whenever the underlying hive records change so that supervisors can'
    + ' always compare the current standing against the previous snapshot.</p></details></main></body></html>',
  // ★2026-10-13: J1 counted a CTA link ("Clear 2 overdue PMs") and modal-opening "Use" buttons as unguarded deletes.
  j1ok: HEAD + '<main><h1>Synthetic parts</h1><p><a href="#overdue" id="cta">Clear 2 overdue PMs</a></p>'
    + '<p><button class="btn-danger" onclick="openUseModal(1)">Use</button></p>'
    + '<div id="use-modal" role="dialog" hidden><p>How many?</p></div>'
    + '<script>window.openUseModal = function (id) { document.getElementById("use-modal").hidden = false; };</script></main></body></html>',
  j1bad: HEAD + '<main><h1>Synthetic parts</h1><p><button class="btn-danger" onclick="deleteRow(1)">Delete</button></p>'
    + '<script>window.deleteRow = function (id) { window.__rows = (window.__rows || 0) - 1; };</script></main></body></html>',
  // ★2026-10-13: B3 graded a one-middot chip line as a sentence (project-report, grade 9.8). Two facts, not one; and a
  // genuinely over-grade 14-word sentence beside it must still fail.
  b3meta: HEAD + '<main><h1>Synthetic report</h1><p class="wh-source-chip">Recomputed each time you generate this report'
    + ' · Based on your project items, project progression and accumulated expenditure</p></main></body></html>',
  // 14 words, as the note above says: B3 grades Flesch-Kincaid only from 12 words up (TH.B3.minGradedWords), and the
  // 11-word version of this sentence sat under that floor, so the case could never bite (found 2026-10-14).
  b3grade: HEAD + '<main><h1>Synthetic report</h1><p>Consolidated expenditure categorization necessitates comprehensive'
    + ' interdepartmental reconciliation procedures before managerial authorization formally occurs annually.</p></main></body></html>',
  // ★2026-10-14: K2 read the landing's stage badges "01".."04" as four small KPIs. Ordinal labels must not count;
  // a real KPI at 16px beside a label must still fail K2's glanceable check.
  k2ordinal: HEAD + '<main><h1>Synthetic stages</h1><div class="card"><span class="step-dot" style="font-size:16px">01</span>'
    + '<h2>Find the gap</h2></div><div class="card"><span class="step-dot" style="font-size:16px">02</span><h2>Close it</h2></div></main></body></html>',
  k2small: HEAD + '<main><h1>Synthetic tiles</h1><div class="card"><p style="font-size:16px">12</p><p>Open work orders</p></div>'
    + '<div class="card"><span class="step-dot" style="font-size:16px">01</span><h2>Step one</h2></div></main></body></html>',
  // ★2026-10-14: a dialog open over a page that made itself inert. Only the dialog's button is a choice (G3 must pass);
  // the same page WITHOUT inert offers three filled buttons at once (G3 must still fail).
  g3modal: HEAD + '<main inert aria-hidden="true"><h1>Synthetic landing</h1><p><button class="btn-primary">Join the hive</button></p>'
    + '<p><button class="btn-primary">Create your free account</button></p></main>'
    + '<div role="dialog" aria-modal="true" aria-label="Sign in"><button class="btn-primary">Sign in</button></div></body></html>',
  g3bare: HEAD + '<main><h1>Synthetic landing</h1><p><button class="btn-primary">Join the hive</button></p>'
    + '<p><button class="btn-primary">Create your free account</button></p>'
    + '<p><button class="btn-primary">Sign in</button></p></main></body></html>',
  brjoin: HEAD + '<main><h1>Synthetic line break</h1><p>Each report covers one project and lists its tasks, costs and sign-offs'
    + ' for the whole team.<br><a href="#pm" style="display:inline-flex;min-height:44px;align-items:center">Open the project'
    + ' manager to choose one project now</a></p></main></body></html>',
};

async function grade(page, html, root = 'main') {
  await page.setContent(html, { waitUntil: 'load' });
  await page.evaluate((src) => (0, eval)('(' + src + ')')(), RUBRIC);
  const res = await page.evaluate((r) => window.__RUBRIC.survey({ pageId: 'synthetic', root: r }), root);
  const dim = (id) => (res.dims || []).find((d) => d.dim === id) || {};
  return { V1: dim('V1'), R6: dim('R6'), B3: dim('B3'), B4: dim('B4'), J1: dim('J1'), K2: dim('K2'), G3: dim('G3') };
}

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
const page = await ctx.newPage();
const fails = [];
const occ = await grade(page, PAGES.occluded);
if (occ.V1.pass !== 0 || !/occludes an interactive control/.test(occ.V1.note || '') || !/fab/i.test(occ.V1.note || '')) fails.push(`V1 must FAIL on a FAB over Save naming the fab - got pass=${occ.V1.pass} note="${(occ.V1.note || '').slice(0, 120)}"`);
if (occ.R6.pass !== 0 || !/wide|420/.test(occ.R6.note || '')) fails.push(`R6 must FAIL on a 420px box in a 300px hidden card - got pass=${occ.R6.pass} note="${(occ.R6.note || '').slice(0, 120)}"`);
const clean = await grade(page, PAGES.clean);
if (clean.V1.pass !== 1) fails.push(`V1 must PASS on the clean page (control) - got pass=${clean.V1.pass} note="${(clean.V1.note || '').slice(0, 120)}"`);
if (clean.R6.pass !== 1) fails.push(`R6 must PASS on the clean page (control) - got pass=${clean.R6.pass} note="${(clean.R6.note || '').slice(0, 120)}"`);
const modal = await grade(page, PAGES.modal);
const anc = await grade(page, PAGES.ancestor);
if (anc.V1.pass !== 0 || !/veil/.test(anc.V1.note || '') || /wh-main-content/.test(anc.V1.note || ''))
  fails.push(`V1 must FAIL naming the veil over the summary, never its ancestor <main> - got pass=${anc.V1.pass} note="${(anc.V1.note || '').slice(0, 140)}"`);
const nst = await grade(page, PAGES.nested);
if (nst.V1.pass !== 1)
  fails.push(`V1 must PASS when the only "covered" controls sit inside a closed disclosure (hidden, not covered) - got pass=${nst.V1.pass} note="${(nst.V1.note || '').slice(0, 140)}"`);
const b4m = await grade(page, PAGES.b4meta);
if (b4m.B4.pass !== 1)
  fails.push(`B4 must read a middot-separated chip line as a list of facts - got pass=${b4m.B4.pass} note="${(b4m.B4.note || '').slice(0, 120)}"`);
const b4l = await grade(page, PAGES.b4long);
if (b4l.B4.pass !== 0)
  fails.push(`B4 must still fail a real 38-word sentence in a disclosure - got pass=${b4l.B4.pass} note="${(b4l.B4.note || '').slice(0, 120)}"`);
const j1o = await grade(page, PAGES.j1ok);
if (j1o.J1.kind === 'MEASURED' && j1o.J1.pass !== j1o.J1.total)
  fails.push(`J1 must not count a CTA link or a modal-opening Use as an unguarded delete - got ${j1o.J1.pass}/${j1o.J1.total} "${j1o.J1.note || ''}"`);
const j1b = await grade(page, PAGES.j1bad);
if (!(j1b.J1.kind === 'MEASURED' && j1b.J1.pass === 0))
  fails.push(`J1 must still fail an unguarded delete - got kind=${j1b.J1.kind} ${j1b.J1.pass}/${j1b.J1.total}`);
const b3m = await grade(page, PAGES.b3meta);
if (!/grade>8=0\b/.test(b3m.B3.note || ''))
  fails.push(`B3 must read a one-middot chip line as two facts - got note="${(b3m.B3.note || '').slice(0, 120)}"`);
const b3g = await grade(page, PAGES.b3grade);
if (/grade>8=0\b/.test(b3g.B3.note || ''))
  fails.push(`B3 must still grade a real over-grade sentence - got note="${(b3g.B3.note || '').slice(0, 120)}"`);
const brj = await grade(page, PAGES.brjoin);
if (!/>20w=0\b/.test(brj.B3.note || ''))
  fails.push(`B3 must read a <br> as a line break (no 25-word merge of a sentence and the link below it) - got note="${(brj.B3.note || '').slice(0, 140)}"`);
const g3m = await grade(page, PAGES.g3modal, 'body');
if (g3m.G3.pass !== 1) fails.push(`G3 must not count buttons behind an open modal (inert) - got ${g3m.G3.pass}/${g3m.G3.total} "${(g3m.G3.note || '').slice(0, 80)}"`);
const g3b = await grade(page, PAGES.g3bare, 'body');
if (g3b.G3.pass !== 0) fails.push(`G3 must still fail three reachable filled buttons - got ${g3b.G3.pass}/${g3b.G3.total} "${(g3b.G3.note || '').slice(0, 80)}"`);
const k2o = await grade(page, PAGES.k2ordinal);
if (!(k2o.K2.kind === 'MEASURED' && k2o.K2.pass === k2o.K2.total))
  fails.push(`K2 must not read zero-padded stage badges as KPIs - got ${k2o.K2.pass}/${k2o.K2.total} "${(k2o.K2.note || '').slice(0, 100)}"`);
const k2s = await grade(page, PAGES.k2small);
if (!(k2s.K2.kind === 'MEASURED' && k2s.K2.pass < k2s.K2.total && /0\/1 glanceable/.test(k2s.K2.note || '')))
  fails.push(`K2 must still fail a real 16px KPI (and count only it, not the badge) - got ${k2s.K2.pass}/${k2s.K2.total} "${(k2s.K2.note || '').slice(0, 100)}"`);
if (modal.V1.pass !== 1) fails.push(`V1 must PASS with a control under an OPEN modal (covered by design) - got pass=${modal.V1.pass} note="${(modal.V1.note || '').slice(0, 120)}"`);
await b.close();
if (fails.length) {
  console.log('FAIL rubric-teeth - ' + fails.join(' | '));
  process.exit(1);
}
console.log(`PASS rubric-teeth - V1 bites on a FAB over Save ("${(occ.V1.note || '').slice(0, 70)}"), R6 bites on a box past its hidden card ("${(occ.R6.note || '').slice(0, 60)}"); both stay quiet on the clean page, V1 stays quiet under an open modal and over a closed disclosure's hidden content, B3 reads a <br> as a line break, B4 reads a middot line as a list but still fails a long sentence, and J1 spares a link and a modal opener but not an unguarded delete`);
