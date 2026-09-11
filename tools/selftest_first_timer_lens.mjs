// selftest_first_timer_lens — does the "explains itself cold" rule still discriminate?
//
// ★LENGTH WAS THE WHOLE TEST, AND A CONCISE PAGE FAILED IT WHILE EXPLAINING ITSELF PERFECTLY.
// ph-intelligence answers a first-timer in 379 characters: it names itself, says what it is for
// ("benchmarks your plant against anonymised peers"), says why it is empty ("there is no hive to
// report on yet"), and offers the Hive Board. That is the model of what this lens asks for, and
// 500 characters is the wrong ruler for it.
//
// Widening a threshold is the easiest way to make a gate vacuous, so the replacement is pinned in
// BOTH directions here: the concise page passes, and a page missing any ONE of the three things
// still fails. Run with: node tools/selftest_first_timer_lens.mjs
//
// (Written as a FILE rather than an inline shell test on purpose: four times this session a bash
// heredoc turned a `\b` into a literal backspace byte and produced a false result about a rule that
// was correct. The prover is edited with a file tool for the same reason.)

const rule = (page, text, chars, controls, inputs) => {
  const subject = page.replace(/\.html$/, '').replace(/-/g, ' ').trim();
  const namesItself = subject.split(' ').filter((w) => w.length > 3)
    .some((w) => new RegExp('\\b' + w, 'i').test(text));
  const saysWhatFor = /\b(?:benchmarks?|tracks?|shows?|records?|plans?|builds?|lets you|helps you|is a|it is)\b/i.test(text);
  const routeOnward = /\b(?:join (?:or create )?a hive|sign in|create an account|hive board|get started)\b/i.test(text);
  const concise = chars > 250 && namesItself && saysWhatFor && routeOnward;
  // a page with no form field anywhere is read-only by construction, and a read-only board that
  // explains itself needs only a refresh and a way home - asking for a third control asks it to
  // invent one. status.html: 1,293 characters, zero inputs, two controls.
  const readOnly = (inputs || 0) === 0;
  const enoughToDo = controls > 2 || (readOnly && controls >= 2);
  return (chars > 500 && enoughToDo) || (concise && enoughToDo);
};

// the real text, read off the page with a first-timer's own session
const PI = 'Skip to main content Join or create a hive to see PH Intelligence PH Intelligence benchmarks '
         + 'your plant against anonymised peers. It is a team tool, so you need a hive first. This is not '
         + 'an empty report; there is no hive to report on yet. Hive Board Back Home';

const CASES = [
  ['the real ph-intelligence, 379 chars', 'ph-intelligence.html', PI, 379, 5, 0, true],
  ['a long ordinary page still passes on length', 'logbook.html', 'x'.repeat(900), 900, 9, 4, true],
  ['a bare title and nothing else', 'some-page.html', 'Some Page', 60, 1, 0, false],
  ['names itself and what it is for, but no way in', 'ph-intelligence.html',
   'PH Intelligence benchmarks your plant against peers.', 300, 4, 0, false],
  ['a way in, but never says what it is', 'ph-intelligence.html',
   'Join or create a hive. Hive Board. Back Home.', 300, 4, 0, false],
  ['says what it is for and offers a way in, but never names itself', 'ph-intelligence.html',
   'This is a team tool. Join or create a hive to see it.', 300, 4, 0, false],
  ['concise and complete, two controls, but it HAS a form to fill', 'ph-intelligence.html', PI, 379, 2, 3, false],
  ['concise and complete, but under 250 chars', 'ph-intelligence.html', PI, 200, 5, 0, false],
  ['a read-only board: long, self-explaining, two controls, no form', 'status.html',
   'WorkHive Gateway Status. This page shows a live health check across the edge gateway. Refresh. Home.', 1293, 2, 0, true],
  ['...but an INTERACTIVE page with two controls still fails', 'logbook.html', 'x'.repeat(900), 900, 2, 5, false],
];

let bad = 0;
for (const [name, page, text, chars, controls, inputs, want] of CASES) {
  const got = rule(page, text, chars, controls, inputs);
  if (got !== want) bad++;
  console.log(`  ${got === want ? 'ok ' : 'BAD'} ${name.padEnd(64)} -> ${got}`);
}
console.log();
console.log(bad
  ? `  FAIL - ${bad} case(s) wrong; the rule no longer discriminates`
  : '  PASS - a concise page that does all three passes; missing any one still fails');
process.exit(bad ? 1 : 0);
