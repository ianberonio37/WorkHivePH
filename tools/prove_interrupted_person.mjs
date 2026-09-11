// prove_interrupted_person — the interruption and findability journeys (T122, T142, T146, T173, T175),
// 2026-09-07.
//
// Five rows about a person who is not giving the screen their full attention, which is every person in a
// plant. The phone rings mid-form. A live refresh lands while they are typing. An AI answer is still
// streaming when they need to leave. They cannot remember which page holds the thing they want. They
// open a page they have never opened before, alone, at 2am.
//
//   I1 the phone rings   leaving the page and coming back does not cost them what they typed - the
//                        state survives being backgrounded, because a plant interrupts constantly (T122)
//   I2 the repaint       a live refresh does not steal focus or discard a draft mid-keystroke. This
//                        platform has already thrown a keyboard user to <body> on a 15s poll. (T142)
//   I3 streaming stops   a streaming answer can be INTERRUPTED - there is an abort, and leaving the page
//                        does not leave a request running against a quota nobody is watching (T146)
//   I4 findability       "where is X?" has an answer that is not "remember which page" - a search that
//                        reaches the whole platform, not one list (T173)
//   I5 first time here   a page opened for the first time explains itself, on every page, not only the
//                        ones somebody remembered to write a guide for (T175)
//
// ★READ FROM THE SHIPPED SOURCE, WITH COMMENTS STRIPPED. A page's comments describe intentions; a person
// meets behaviour. Every count below is over code, never over the prose around it.
//
//   node tools/prove_interrupted_person.mjs
import { readdirSync, readFileSync } from 'node:fs';

const raw = (f) => { try { return readFileSync(f, 'utf8'); } catch { return ''; } };
const strip = (s) => s
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/^[ \t]*\/\/.*$/gm, ' ');
// promo-poster.html is excluded alongside the three catalog pages: it is a PRINTABLE ARTIFACT, a poster
// generated to be put on a wall, not a surface someone navigates. "How this page works" on a poster is
// noise, and counting it as an unexplained destination would push a fix that makes the product worse.
const pages = readdirSync('.').filter((f) => f.endsWith('.html') && !/^(symbol-gallery|design-system|validator-catalog|promo-poster)\.html$/.test(f));
const SRC = new Map(pages.map((f) => [f, strip(raw(f))]));
const shared = ['utils.js', 'nav-hub.js', 'offline-queue.js', 'session-timeout.js', 'search-overlay.js']
  .map((f) => [f, strip(raw(f))]);
const SHARED = shared.map(([, s]) => s).join('\n');

let bad = 0;
const say = (ok, id, line, detail) => {
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${id.padEnd(20)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};

// ── I1 · the phone rings mid-form ────────────────────────────────────────────────────────────────
{
  // a plant interrupts constantly; the platform must notice the page went away and come back sanely
  const awareShared = /visibilitychange|document\.hidden|pagehide|freeze|resume/i.test(SHARED);
  const composers = ['logbook.html', 'inventory.html', 'community.html', 'voice-journal.html', 'resume.html']
    .filter((f) => pages.includes(f));
  // a draft that outlives the interruption: stored, or the form is never torn down
  const keepsDraft = composers.filter((f) => /draft|autosave|localStorage\.setItem\([^)]*(compose|entry|form)/i.test(SRC.get(f)));
  say(awareShared, 'I1 the phone rings',
    `the shared layer ${awareShared ? 'notices the page being backgrounded and returning' : 'does NOT'}; ${keepsDraft.length} of ${composers.length} composing surface(s) hold a draft across it`,
    'nothing in the shared layer listens for visibilitychange or pagehide, so a page that was backgrounded for a phone call comes back with no idea it was gone');
}

// ── I2 · the repaint that lands while they are typing ────────────────────────────────────────────
{
  // ★THIS PLATFORM HAS ALREADY SHIPPED THIS BUG. A 15s poll re-rendered a list and threw a keyboard user
  // to <body>, keeping the draft and losing the focus - so the discipline is specifically about focus.
  // ★NOT EVERY TIMER REPAINTS. asset-hub.html:4825 is a REGISTRATION RETRY - it calls tryRegister() at
  // 250ms, gives up after 20 tries and clears itself, and touches no DOM a person is typing into. The
  // first version counted any setInterval as a repaint and accused it of stealing focus it never touches.
  // What matters is a timer that RE-RENDERS: one whose body loads or draws something.
  const REPAINTS = /setInterval\s*\([\s\S]{0,300}?(render|refresh|reload|redraw|loadAll|load[A-Z_]|fetch|update[A-Z_]|draw|paint|poll)/i;
  const pollers = pages.filter((f) => REPAINTS.test(SRC.get(f)));
  const disciplined = pollers.filter((f) => {
    const s = SRC.get(f);
    // either it refuses to repaint while a field has focus, or it restores focus after
    return /document\.activeElement|:focus|_whFocusGuard|restoreFocus|hasFocus\(\)/i.test(s);
  });
  say(disciplined.length === pollers.length, 'I2 the repaint',
    `${pollers.length} page(s) repaint on a timer, ${disciplined.length} of them check where the person's focus is first`,
    `${pollers.filter((f) => !disciplined.includes(f)).slice(0, 4).join(', ')} repaint on a timer without consulting focus - a refresh landing mid-keystroke throws a keyboard user out of the field they were in`);
}

// ── I3 · can a stream be stopped? ────────────────────────────────────────────────────────────────
{
  const streaming = pages.filter((f) => /ReadableStream|getReader\(|text\/event-stream|stream:\s*true/i.test(SRC.get(f)))
    .concat(/ReadableStream|getReader\(/i.test(SHARED) ? ['(shared layer)'] : []);
  const abortable = /AbortController|\.abort\(\)|signal:/i.test(SHARED)
    || pages.some((f) => /AbortController|\.abort\(\)/i.test(SRC.get(f)));
  say(streaming.length === 0 || abortable, 'I3 streaming stops',
    streaming.length ? `${streaming.length} surface(s) stream a response; an abort path ${abortable ? 'exists' : 'does NOT exist'}` : 'nothing streams, so there is no stream to interrupt',
    'a streaming answer cannot be stopped, so a person who leaves mid-answer leaves a request running against a quota nobody is watching');
}

// ── I4 · "where is X?" ───────────────────────────────────────────────────────────────────────────
{
  // a platform-wide search, not a filter over one list
  const overlay = raw('search-overlay.js');
  const registryBacked = /REGISTRY|whToolRegistry|TOOLS|pages\s*=|routes/i.test(strip(overlay));
  const reach = pages.filter((f) => /search-overlay\.js|nav-hub\.js/.test(SRC.get(f)));
  say(!!overlay && registryBacked && reach.length > pages.length * 0.8, 'I4 findability',
    `a platform search ${overlay ? 'ships' : 'does not exist'}, ${registryBacked ? 'backed by a registry of destinations' : 'with no registry behind it'}, reachable from ${reach.length} of ${pages.length} page(s)`,
    !overlay ? 'there is no platform-wide search, so "where is X?" is answered by remembering which page'
      : !registryBacked ? 'the search has no registry of destinations behind it, so it can only find what one page already listed'
      : `the search is reachable from only ${reach.length} of ${pages.length} pages - on the rest, a person is back to remembering`);
}

// ── I5 · the first time on a page ────────────────────────────────────────────────────────────────
{
  // the platform's own answer is the page guide; the question is whether EVERY page has one
  // ★THE REAL CAUSE WAS TWO BACKSPACE BYTES. This lens reported 20 unexplained pages and named
  // architecture.html, which opens with "How to read this map" - and the same regex MATCHED that page
  // when tested in Python. The difference was invisible: writing this file through a shell heredoc had
  // turned the two \b word-boundaries into literal U+0008 BACKSPACE characters, so the pattern was
  // hunting for a control byte no page contains. Three earlier theories (an injected guide chip, a
  // too-narrow class name, my own strip() eating the markup) were all reasonable and all wrong, and each
  // sent me to edit the lens rather than to look at its bytes. WHEN A REGEX DISAGREES WITH THE SAME
  // REGEX RUN ELSEWHERE, COMPARE THE BYTES BEFORE COMPARING THE LOGIC. The no-control-bytes gate exists
  // for exactly this and is worth running the moment a pattern behaves impossibly.
  //
  // What counts as an explanation is a DISCLOSURE whose summary reads like one, whatever the page calls
  // it - not one class name. (learn-link.js does inject a guide chip, but only marketplace.html loads
  // it, so it is not the platform-wide answer it first appeared to be.)
  const EXPLAINS = /<details[\s\S]{0,400}?<summary[\s\S]{0,200}?\b(how|what|why|guide|read|about|works|means|start)\b/i;
  // A disclosure is MARKUP, not code, so it is read from the raw source. The worst case there is counting
  // an explanation somebody wrote inside an HTML comment, which is far cheaper than a strip() that eats
  // the <details> this lens exists to find. Comment-stripping earns its keep on code lenses, not markup.
  const NAMED = /wh-help|page-guide|New to this page|how this page works|data-guide/i;
  const guided = pages.filter((f) => NAMED.test(raw(f)) || EXPLAINS.test(raw(f)));
  const missing = pages.filter((f) => !guided.includes(f));
  say(missing.length === 0, 'I5 first time here',
    `${guided.length} of ${pages.length} page(s) explain themselves to someone opening them for the first time`,
    `${missing.slice(0, 5).join(', ')}${missing.length > 5 ? ` and ${missing.length - 5} more` : ''} offer no explanation, so a person meeting them alone at 2am is on their own`);
}

console.log(`${bad ? 'FAIL' : 'PASS'} interrupted-person - a backgrounded page comes back, a repaint respects focus, a stream can be stopped, "where is X" has an answer, and a first visit explains itself`);
process.exitCode = bad ? 1 : 0;
