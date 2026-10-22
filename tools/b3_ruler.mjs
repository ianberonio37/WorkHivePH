// b3_ruler.mjs - grade sentences with the rubric lens's OWN B3 ruler (ENH-C, 2026-10-22).
//
// survey_ufai_rubric.js grades readability inside a page: no sentence over 20 words, no passive voice, and Flesch-Kincaid
// grade 8 or under for a sentence of 12 words or more. A gate that holds a rewritten sentence must use the same ruler,
// so this reads the lens's own syllables(), fk(), PASSIVE and TH.B3 thresholds out of its source - a second, hand-copied
// ruler would drift from the one the critic grades with. If the lens moves those lines this exits 2 and says so.
//
//   node tools/b3_ruler.mjs "first sentence." "second sentence."     exit 0 when every sentence passes, 1 otherwise
//   node tools/b3_ruler.mjs --json "..."                             one JSON line per sentence
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(ROOT, 'survey_ufai_rubric.js'), 'utf8');
const grab = (re, name) => {
  const m = src.match(re);
  if (!m) { console.error(`b3_ruler: the lens no longer carries ${name} where this reads it - update tools/b3_ruler.mjs`); process.exit(2); }
  return m[0];
};
const sylSrc = grab(/const syllables = \(w\) => \{[\s\S]*?\n    \};/, 'syllables()');
const fkSrc = grab(/const fk = \(s\) => \{[\s\S]*?\n    \};/, 'fk()');
const passSrc = grab(/const PASSIVE = \/.*\/;/, 'PASSIVE');
const th = src.match(/B3: \{ maxSentenceWords: (\d+), maxFkGrade: (\d+), minGradedWords: (\d+) \}/);
if (!th) { console.error('b3_ruler: the lens no longer declares TH.B3 where this reads it'); process.exit(2); }
const [maxW, maxG, minW] = th.slice(1).map(Number);
const lib = new Function(`${sylSrc}\n${fkSrc}\n${passSrc}\nreturn { fk, PASSIVE };`)();

export function grade(s) {
  const n = s.split(/\s+/).filter(Boolean).length;
  const g = lib.fk(s);
  const fails = [];
  if (n > maxW) fails.push(`over ${maxW} words (${n})`);
  if (n >= minW && g > maxG) fails.push(`grade ${g.toFixed(1)} over ${maxG}`);
  if (lib.PASSIVE.test(s)) fails.push('passive voice');
  return { sentence: s, words: n, grade: n >= minW ? +g.toFixed(1) : null, fails };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const args = process.argv.slice(2);
  const json = args.includes('--json');
  let bad = 0;
  for (const s of args.filter((a) => a !== '--json')) {
    const r = grade(s);
    if (r.fails.length) bad++;
    console.log(json ? JSON.stringify(r) : `${r.fails.length ? 'FAIL' : 'ok  '} ${r.words}w ${r.grade === null ? '' : 'grade ' + r.grade} ${r.fails.join(', ')} | ${s}`);
  }
  process.exit(bad ? 1 : 0);
}
