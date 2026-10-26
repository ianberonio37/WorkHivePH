// validate_turn_steering.mjs - the companion's server-side safety steering, exercised (BRH-AP, 2026-10-27). No network.
//
// _shared/turn-steering.ts decides, from the worker's own words, which safety rules the voice-journal prompt states, and
// after the model it puts the server's own sentence first when the reply missed a life-safety rule. This runs the module
// itself (Node strips its types) over a sample per rule and a set of controls, and over the enforcement:
//   - each rule fires on its sample (English and Taglish), and nothing fires on everyday questions
//   - a reply missing a life-safety rule gets the server's line FIRST; a reply that carries it is left alone
//   - an empty reply (no model answered) becomes the safety lines, so an injury is never answered with an error
//   - no rule tells the model to promise something that does not exist (an SOS button, a near-miss filing)
//
//   node tools/validate_turn_steering.mjs
import { copyFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SRC = path.join(ROOT, 'supabase', 'functions', '_shared', 'turn-steering.ts');
mkdirSync(path.join(ROOT, '.tmp'), { recursive: true });
const MTS = path.join(ROOT, '.tmp', 'turn-steering.gate.mts');   // .mts: Node runs it as an ES module with types stripped
copyFileSync(SRC, MTS);
const m = await import(pathToFileURL(MTS).href);

let ok = 0, bad = 0;
const ck = (cond, msg) => { console.log((cond ? '  ok   ' : '  FAIL ') + msg); cond ? ok++ : bad++; };
const fires = (t) => m.turnSteering(t).kinds;

const SAMPLES = [
  ['i-lockout ko na yung motor ng conveyor', 'loto'], ['lock out tag out the panel first', 'loto'],
  ['welding on the pipe rack later', 'hot_work'], ['mag paghihinang ako sa tangke', 'hot_work'],
  ['first time doing a tank entry sa sump', 'confined_space'], ['confined space entry tomorrow', 'confined_space'],
  ['what PPE for grinding?', 'ppe'], ['ano ang PPE para dito', 'ppe'],
  ['may kasamahan nasaktan sa line', 'incident'], ['need first aid now', 'incident'],
  ['muntik na akong mahulog sa hagdan', 'near_miss'], ['close call on the forklift', 'near_miss'],
  ['first time doing a bearing change', 'jsa'], ['gusto ko nang magpakamatay', 'crisis_self_harm'],
  ['he threatened me at the gate', 'crisis_violence'], ['bobo talaga yung system na to', 'toxicity'],
  ['is MaintainX better than this?', 'forbidden_competitor'],
];
for (const [t, k] of SAMPLES) ck(fires(t).includes(k), `'${t}' states ${k}`);
for (const t of ['what is the MTBF of the main compressor this month?', 'show me the PM list for line 2',
                 'blockout dates for the shutdown', 'the tagline on the poster', 'how many parts are low on stock']) {
  ck(fires(t).length === 0, `'${t}' states nothing`);
}
const inc = m.turnSteering('may kasamahan nasaktan sa line');
const e1 = m.enforceSteering('Okay po, ingat kayo.', inc.kinds);
ck(e1.enforced.includes('incident') && e1.reply.startsWith('Call the site Safety Officer now'), 'a reply missing the injury rule gets the server line first');
const e2 = m.enforceSteering('Call the site Safety Officer now. Stop the bleeding.', inc.kinds);
ck(e2.enforced.length === 0 && e2.reply.startsWith('Call the site Safety Officer now. Stop'), 'a reply that carries the rule is left alone');
const cs = m.turnSteering('first time doing a tank entry sa sump');
const e3 = m.enforceSteering('Good start with LOTO. Have you got that yet?', cs.kinds);   // the measured codestral reply
ck(e3.enforced.includes('confined_space') && /4-gas reading/.test(e3.reply), "the walk's real miss (LOTO talk, no gas reading) is caught");
const e4 = m.enforceSteering('', m.turnSteering('gusto ko nang magpakamatay').kinds);
ck(/1553/.test(e4.reply) && e4.enforced.includes('crisis_self_harm'), 'an empty reply (no model answered) becomes the crisis line');
const e5 = m.enforceSteering('Sure, the PM list is on the scheduler.', m.turnSteering('show me the PM list').kinds);
ck(e5.enforced.length === 0 && e5.reply === 'Sure, the PM list is on the scheduler.', 'an everyday reply is untouched');
const all = SAMPLES.map(([t]) => m.turnSteering(t).text).join('\n');
for (const p of ['SOS button', 'file this as a near-miss', 'PH OSHS limits']) ck(!all.includes(p), `no rule tells the model to promise '${p}'`);
const order = m.turnSteering('may kasamahan nasaktan sa tank entry, need first aid now').kinds;
ck(order.indexOf('incident') < order.indexOf('confined_space'), 'an injury leads a turn that also mentions a tank entry');

// ── conversation steering (BRH-AP part 2): how a turn is answered ───────────────────────────────────────────────────────
const conv = (t) => m.conversationSteering(t).kinds;
const CONV = [
  ['pagod na ako sa compressor na to', 'fatigue'], ['summarize this conversation please', 'summary'],
  ['no, I meant the other pump', 'correction'], ['i-check mo nga yung motor', 'tagalog_imperative'],
  ['sa tagalog na lang please', 'language'], ['unsa man ni asa na ang pump', 'dialect_cebuano'],
  ['why is the MTBF that low', 'explain'], ['is this data current', 'freshness'], ['morning summary please', 'digest'],
  ['energy cost of the compressor', 'energy'], ['what can you do', 'scope'], ['help', 'help'],
  ['qwrtyzxcv plmnbvcxz qwrtsdfgh', 'stt_mangled'], ['opo, salamat po', 'register_formal'],
];
for (const [t, k] of CONV) ck(conv(t).includes(k), `'${t}' answers as ${k}`);
for (const t of ['what is the MTBF of the main compressor this month?', 'show me the PM list for line 2']) {
  // a question shape and late-night brevity apply to everyday turns by design; nothing ELSE should fire on these
  ck(conv(t).filter((k) => !k.startsWith('shape_') && k !== 'quiet_hours').length === 0, `'${t}' needs no answering rule beyond its shape`);
}
const allConv = CONV.map(([t]) => m.conversationSteering(t).text).join('\n');
ck(!/\bv_\w+_truth\b/.test(allConv), 'no answering rule names an internal view (the persona forbids it)');
ck(!/0\.717|EnPI \(ISO|energy block/.test(allConv), 'the energy rule invents no grid factor or snapshot block');

// question shape and quiet hours (BRH-AP part 3), at fixed times so the gate does not depend on when it runs
const NOON = new Date('2026-10-27T04:00:00Z'), LATE = new Date('2026-10-27T15:00:00Z');   // 12:00 and 23:00 in Manila
for (const [t, k] of [['how do I fix a pump that trips', 'shape_how_to'], ['should I replace the bearing', 'shape_opinion'],
                      ['why is the motor hot', 'shape_troubleshoot'], ['hello po', 'shape_social']]) {
  ck(m.conversationSteering(t, NOON).kinds.includes(k), `'${t}' is shaped ${k}`);
}
ck(!m.conversationSteering('why is the motor hot', NOON).kinds.includes('explain'), "'why is the motor hot' is a fault question, not 'how do you know'");
ck(m.conversationSteering('why did you say 14 days', NOON).kinds.includes('explain'), "'why did you say 14 days' asks how the companion knows");
ck(m.conversationSteering('show me the PM list', LATE).kinds.includes('quiet_hours'), '23:00 in Manila is quiet hours');
ck(!m.conversationSteering('show me the PM list', NOON).kinds.includes('quiet_hours'), 'noon is not');

// a tired worker's reply is kept to two sentences, in code (the walk's measured reply stacked four)
const lecture = 'Naks, pagod na talaga yan. First, check the discharge pressure and the impeller wear ring gap. If the gap is over spec, replace the ring. Then re-run it.';
const shaped = m.shapeReply(lecture, m.conversationSteering('pagod na ako, sira ulit yung compressor').kinds);
ck(shaped.shaped.includes('fatigue') && (shaped.reply.match(/[.!?]/g) || []).length === 2, "a tired worker's lecture is cut to two sentences");
ck(m.shapeReply(lecture, []).reply === lecture, 'a reply on any other turn is not cut');
const both = m.turnSteering('pagod na ako, may kasamahan nasaktan sa line');
const tiredInjury = m.enforceSteering(m.shapeReply(lecture, m.conversationSteering('pagod na ako, may kasamahan nasaktan sa line').kinds).reply, both.kinds);
ck(tiredInjury.reply.startsWith('Call the site Safety Officer now'), 'on a tired turn that reports an injury the safety line still leads after the trim');

const offTopic = 'Naks, pagod talaga yan. First, LOTO the motor before anything else.';   // the walk's measured scope reply
const sc = m.shapeReply(offTopic, m.conversationSteering('what can you do?').kinds);
ck(sc.shaped.includes('scope') && /can't make changes/.test(sc.reply), "an off-topic answer to 'what can you do' is replaced by the fixed capability answer");
ck(m.shapeReply('I answer from your records and fill a card you confirm.', ['scope']).shaped.length === 0, 'a capability answer that states the facts is kept');

// the browser kept copies of these triggers; while it does, each is the same expression on both sides
import { readFileSync } from 'node:fs';
const vh = readFileSync(path.join(ROOT, 'voice-handler.js'), 'utf8');
const ts = readFileSync(SRC, 'utf8');
const src = (text, re) => { const x = text.match(re); return x ? x[1] : null; };
for (const n of ['_FATIGUE_RE', '_SUMMARY_RE', '_CORRECTION_RE', '_TGL_IMPERATIVE_RE', '_LANG_OPT_RE', '_EXPLAIN_RE', '_FRESHNESS_RE',
                 '_DIGEST_RE', '_ENERGY_QUERY_RE', '_SCOPE_RE', '_HELP_RE', '_CEBUANO_MARKERS', '_ILONGGO_MARKERS']) {
  const a = src(vh, new RegExp('^  const ' + n + ' = (.+);\\s*$', 'm'));
  const b = src(ts, new RegExp('^export const ' + n.slice(1) + ' = (.+);\\s*$', 'm'));
  if (a !== null) ck(a === b, `${n} is the same in the browser and on the server`);
}

console.log(bad ? `FAIL turn-steering - ${bad} of ${ok + bad} checks` : `PASS turn-steering - ${ok} checks`);
process.exitCode = bad ? 1 : 0;
