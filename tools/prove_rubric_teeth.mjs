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
};

async function grade(page, html) {
  await page.setContent(html, { waitUntil: 'load' });
  await page.evaluate((src) => (0, eval)('(' + src + ')')(), RUBRIC);
  const res = await page.evaluate(() => window.__RUBRIC.survey({ pageId: 'synthetic', root: 'main' }));
  const dim = (id) => (res.dims || []).find((d) => d.dim === id) || {};
  return { V1: dim('V1'), R6: dim('R6') };
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
if (modal.V1.pass !== 1) fails.push(`V1 must PASS with a control under an OPEN modal (covered by design) - got pass=${modal.V1.pass} note="${(modal.V1.note || '').slice(0, 120)}"`);
await b.close();
if (fails.length) {
  console.log('FAIL rubric-teeth - ' + fails.join(' | '));
  process.exit(1);
}
console.log(`PASS rubric-teeth - V1 bites on a FAB over Save ("${(occ.V1.note || '').slice(0, 70)}"), R6 bites on a box past its hidden card ("${(occ.R6.note || '').slice(0, 60)}"); both stay quiet on the clean page and V1 stays quiet under an open modal`);
