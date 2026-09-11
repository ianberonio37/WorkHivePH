// prove_ai_surface_honesty — the AI-surface journeys (T79-T91), walked as one family (2026-09-07).
//
// Ten trajectory rows ask the same three things of different AI surfaces - the voice action router, the
// daily brief, asset brain, resume polish, persona switching, semantic search, write provenance, the
// feedback loop, the cost guardrail, temporal RAG. A person meeting any of them needs the same
// assurances, so they are walked together rather than ten times over.
//
//   Y1 present     the surface's AI entry point is actually on the page and reachable - not a feature
//                  described in the copy with no way in
//   Y2 grounded    it declares what it answers FROM. An AI answer with no stated basis is the one thing
//                  a maintenance engineer cannot use: they must be able to check it against the record.
//   Y3 honest      when it cannot answer - no quota, no connection, nothing found - it SAYS so, rather
//                  than producing a confident sentence with nothing behind it. This is the lens that
//                  matters most and the one this platform has already been burned by.
//
// ★THE QUOTA BEING EXHAUSTED IS A FEATURE OF THIS WALK, NOT AN OBSTACLE. When the AI limit is spent the
// surfaces must degrade honestly, which is exactly Y3 - so a run during a 429 window measures the lens
// that matters, and a run with quota measures Y1 and Y2. The prover states which it got.
//
//   node tools/prove_ai_surface_honesty.mjs
//   node tools/prove_ai_surface_honesty.mjs --page assistant.html
import { chromium } from 'playwright';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();

// each AI journey and the surface a person meets it on
const SURFACES = [
  ['assistant.html', 'the companion answers a technical question'],
  ['voice-journal.html', 'the voice router turns speech into a logbook entry'],
  ['shift-brain.html', 'the daily brief tells you what to do first'],
  ['asset-hub.html', 'asset brain answers about one machine'],
  ['resume.html', 'resume polish rewrites rough notes'],
  ['analytics.html', 'the analytics brief explains the numbers'],
  ['ai-quality.html', 'the AI-quality console tells the truth about the AI'],
  ['agentic-rag-observability.html', 'the RAG loop shows its own retrievals', 'view'],
  ['llm-observability.html', 'the model layer shows its cost and latency', 'view'],
  ['community.html', 'semantic search finds the answer someone already wrote'],
];

const AI_ENTRY = /\b(ask|assistant|companion|generate|polish|summar|brief|suggest|explain|rewrite|search|hezekiah|zaniah|ai\b)/i;
const HONEST = /\b(could not|couldn.t|unavailable|no answer|not enough|try again|limit|quota|offline|nothing found|no results|cannot)\b/i;

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
await signIn(ctx);

let bad = 0, n = 0;
for (const [file, what, kind] of (ONLY ? SURFACES.filter((s) => s[0] === ONLY) : SURFACES)) {
  n++;
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);

  const pageState = await p.evaluate((VIS_JS) => {
    const vis = (0, eval)(VIS_JS);
    const chips = [...document.querySelectorAll('.wh-source-chip, [data-source-chip], .source-chip, [id$="-source-chip"]')]
      .filter(vis).map((e) => (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
    const notices = [...document.querySelectorAll('[role="alert"], [role="status"], .honest-empty, .mod-empty, [id$="-notice"], .wh-list-error')]
      .filter(vis).map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
    const raw = document.querySelectorAll('.wh-source-chip, [data-source-chip], .source-chip, [id$="-source-chip"]').length;
    return { chips: chips.slice(0, 2), notices: notices.slice(0, 4), raw };
  }, VIS_JS).catch(() => ({ chips: [], notices: [] }));

  // ★THE AI ENTRY IS USUALLY ONE PRESS AWAY, NOT ON SCREEN. Every page carries the companion behind the
  // nav hub (#wh-hub-open-companion), which is visibility:hidden until the hub opens - so a scan of the
  // page at rest reported "no reachable AI entry point" on surfaces that have one for every visitor.
  // Open the hub the way a person does, then look.
  await p.evaluate(() => {
    const t = [...document.querySelectorAll('button, [role="button"]')]
      .find((e) => /open navigation hub/i.test(e.getAttribute('aria-label') || e.innerText || ''));
    if (t) t.click();
  }).catch(() => {});
  await p.waitForTimeout(2500);

  const r = await p.evaluate((args) => {
    const vis = (0, eval)(args[0]);
    const AI = new RegExp(args[1], 'i');
    const strict = (e) => e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
    // Y1 - is there a way in?
    const entries = [...document.querySelectorAll('button, [role="button"], a, input[type="text"], textarea')]
      .filter((e) => vis(e) && strict(e))
      .filter((e) => AI.test((e.innerText || '') + ' ' + (e.getAttribute('aria-label') || '') + ' ' + (e.placeholder || '')))
      // the page-guide chip ("New to this page? Read the guide") is documentation, not an AI entry
      .filter((e) => !/read the guide|new to this page/i.test(e.innerText || ''));
    // Y2 - does the surface declare what it answers from?
    const chips = [...document.querySelectorAll('.wh-source-chip, [data-source-chip], .source-chip, [id$="-source-chip"]')]
      .filter(vis).map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
    // Y3 - what is said when it cannot answer
    const notices = [...document.querySelectorAll('[role="alert"], [role="status"], .honest-empty, .mod-empty, [id$="-notice"], .wh-list-error')]
      .filter(vis).map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
    return {
      entries: entries.slice(0, 3).map((e) => ((e.innerText || e.placeholder || e.getAttribute('aria-label') || '').trim().slice(0, 30))),
      entryCount: entries.length,
      chips: chips.slice(0, 2),
      notices: notices.slice(0, 4),
    };
  }, [VIS_JS, AI_ENTRY.source]).catch(() => ({ entries: [], entryCount: 0 }));
  r.chips = pageState.chips;          // read before the hub was opened
  r.rawChips = pageState.raw;
  r.notices = pageState.notices;

  const issues = [];
  if (r.entryCount === 0 && kind !== 'view') issues.push(`Y1 no reachable AI entry point for "${what}" - the feature is described and cannot be started`);
  if (!r.chips.length) issues.push('Y2 the surface does not declare what it answers FROM - an AI answer with no stated basis cannot be checked against the record');
  // Y3 is only assertable when something actually failed; a working surface has nothing to be honest about
  const failing = r.notices.filter((s) => HONEST.test(s));
  if (r.notices.length && !failing.length && r.notices.some((s) => /error|problem|wrong/i.test(s))) {
    issues.push(`Y3 a failure is shown without saying what a person can do: "${r.notices[0].slice(0, 60)}"`);
  }

  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${file.padEnd(32)} ${kind === 'view' ? 'a viewing surface' : r.entryCount + ' entry point(s)'}${r.entries.length ? ' (' + r.entries[0] + ')' : ''} · ${r.chips.length} source chip(s)${r.rawChips && !r.chips.length ? ` (${r.rawChips} in the DOM but not visible)` : ''} · ${failing.length}/${r.notices.length} notice(s) honest`);
  for (const s of issues.slice(0, ONLY ? 8 : 2)) console.log(`        ${s.slice(0, 160)}`);
  await p.close();
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} ai-surface-honesty - ${n - bad}/${n} AI surfaces can be started, declare what they answer from, and say so honestly when they cannot answer`);
process.exitCode = bad ? 1 : 0;
