// prove_ai_trust — the EX-AT wave: the confident wrong answer (2026-09-07).
//
// A maintenance engineer about to act on what the AI said needs four things from every AI surface, and
// this platform had no trajectory asking for any of them. A confident wrong torque value, acted on, is
// a stripped bolt or a dropped load - so the lens is not "is the AI good" but "can the person catch it
// and be heard when they do".
//
//   T1 flaggable    after an answer, a person can say IT IS WRONG in one press, and the press is recorded
//                   (ai_reply_feedback) - not a mailto, not a form on another page
//   T2 sourced      the surface says what the answer was grounded ON, in a source chip a person can read
//   T3 disagreement the down-vote is a real path: it records the disagreement with the reply it was about
//   T4 degraded honestly when the AI quota is spent the surface SAYS so, and does not render a thinner
//                   answer as though it were the full one
//
// ★T4 IS PROVOKED, NOT REASONED ABOUT. The AI gateway is intercepted with a 429 carrying the platform's own
// refusal body, so the surface meets exactly what it meets on a real spent quota - and what it shows a
// person is read from the screen.
//
//   node tools/prove_ai_trust.mjs
//   node tools/prove_ai_trust.mjs --page assistant.html
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS } from './prover_harness.mjs';
import { REFUSAL, VIEW_ONLY, armQuotaRefusal, askSurface } from './ai_ask.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const read = (f) => { try { return readFileSync(f, 'utf8'); } catch { return ''; } };
const ROSTER = (() => {
  try {
    const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
    return [...new Set(reg.trajectories.filter((t) => t.wave === 'EX-AT').flatMap((t) => t.pages || []))];
  } catch { return []; }
})();
// the surfaces that only SHOW AI output (observability) cannot be asked to flag it

const SAYS_LIMIT = /limit|quota|try again|wait|resets|spent|out of/i;

const b = await chromium.launch();
let bad = 0, n = 0;
for (const file of (ONLY ? [ONLY] : ROSTER)) {
  n++;
  const src = read(file);
  const viewOnly = VIEW_ONLY.has(file);
  // static: does this surface even carry the pieces. whAiTrustRow (utils.js, EX-AT) renders button[data-rate]
  // 👍/👎 writing ai_reply_feedback AND a .wh-source-chip - one shared row, so its call is the contract here.
  // A page whose ONLY AI surface is the companion launcher (community.html) flags through the launcher's own
  // 👍/👎 (companion-launcher.js:812) - the page source cannot carry what the shared script renders.
  const ownAi = /functions\/v1\/|functions\.invoke\(/.test(src);
  const usesLauncher = /companion-launcher\.js/.test(src);
  const canFlag = /data-rate|ai_reply_feedback|_attachChatFeedback|whAiTrustRow|thumbs|helpful/i.test(src) || (usesLauncher && !ownAi);
  const hasChip = /wh-source-chip|data-source-chip|source-chip|whAiTrustRow/i.test(src);

  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  await signIn(ctx);
  const p = await ctx.newPage();
  // T4: the gateway answers as it does on a spent quota
  await armQuotaRefusal(p);
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);

  // ask the surface something, the way a person does. A surface with no ask box is provoked the way its
  // person provokes it: the analytics "Recompute", the shift-brain "Generate Plan", the resume "Polish" - and
  // a page whose AI is the companion launcher gets the launcher opened first (its box says "Ask anything…").
  const launcherOnly = usesLauncher && !ownAi;
  const asked = await askSurface(p, file, launcherOnly);
  await p.waitForTimeout(7000);

  const seen = await p.evaluate((VIS_JS) => {
    const vis = (0, eval)(VIS_JS);
    // #toast is the platform's own toast element (shift-brain.html:383, analytics.html) - a class-only selector read past it
    const notices = [...document.querySelectorAll('[role="alert"], [role="status"], .wh-list-error, .honest-empty, [id$="-notice"], .toast, #toast, [id$="toast"], .wh-toast, .assistant-msg, .msg, .wh-msg, .bubble, [id$="-verdict-label"], [id$="-verdict-sub"]')]
      .filter(vis).map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean).concat(window.__whNotices || []);
    const chip = [...document.querySelectorAll('.wh-source-chip, [data-source-chip], .source-chip')].filter(vis).map((e) => (e.innerText || '').trim()).filter(Boolean);
    const rate = [...document.querySelectorAll('button[data-rate]')].filter(vis);
    const main = document.querySelector('main, [role="main"], #app') || document.body;
    return { notices: notices.slice(0, 6), chip: chip.slice(0, 2), rateButtons: rate.length, down: rate.some((e) => e.getAttribute('data-rate') === '-1'), text: (main.innerText || '').replace(/\s+/g, ' ').slice(0, 400) };
  }, VIS_JS).catch(() => ({ notices: [], chip: [], rateButtons: 0, down: false, text: '' }));
  await ctx.close();

  const said = seen.notices.join(' | ') + ' ' + seen.text;
  const issues = [];
  if (!viewOnly && !canFlag) issues.push('T1 no way to say an answer is wrong exists on this surface - a person who catches a mistake cannot be heard');
  if (!hasChip && !seen.chip.length) issues.push('T2 the surface never says what its answers are grounded on');
  if (!viewOnly && canFlag && !/data-rate="-1"|rating\s*[:=]\s*-1|\(-1[,)]|whAiTrustRow/.test(src) && !(usesLauncher && !ownAi)) issues.push('T3 the feedback control has no down-vote, so disagreement has no path');
  if (asked && !SAYS_LIMIT.test(said)) issues.push(`T4 on a spent quota the surface said nothing about a limit - what it showed: "${said.slice(0, 70)}"`);
  if (!asked && !viewOnly) issues.push('T4 no ask box was reachable, so the spent-quota moment was not provoked - unmeasured, not clean');

  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${file.padEnd(32)} ${viewOnly ? 'view-only' : (canFlag ? 'flaggable' : 'NOT flaggable')} · chip ${hasChip || seen.chip.length ? 'yes' : 'NO'} · asked ${asked} · on 429 said: "${(seen.notices[0] || seen.text || '').slice(0, 56)}"`);
  for (const s of issues.slice(0, ONLY ? 8 : 2)) console.log(`        ${s.slice(0, 158)}`);
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} ai-trust - ${n - bad}/${n} AI surface(s) let a person flag a wrong answer, say what it was grounded on, record disagreement, and admit a spent quota`);
process.exitCode = bad ? 1 : 0;
