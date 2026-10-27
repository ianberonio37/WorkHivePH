// what_happens_next_vocab.mjs - the harvested vocabulary of 'after an action, the surface says what happens next'
// (moved verbatim from tools/prove_what_happens_next.mjs, 2026-10-27, so the T2 SE verbal-persuasion walk asks the SAME
// oracle instead of a second word list; every comment below is the history of why each phrase is there).

// Names a FOLLOWING step — someone or something else acts, or the person must do one more thing.
// Built from a source STRING, not a multi-line regex literal: my first version spliced string
// concatenation into a `/.../i` literal, which is a parse error, and the file would not even load.
export const NEXT_SRC = [
  'submitted for', 'pending', 'awaiting', 'for (supervisor|approval|review)', 'will be',
  "we['’ ]?ll", 'queued', 'scheduled', 'sent to', 'notified', 'try again', 'check your',
  'next step', 'then ', 'once ', 'after (it|we|the)', 'under review', 'in review',
  'being (processed|reviewed|generated)',
  // EFFECT-NAMING counts as naming what happens next, because that is how this platform speaks: asset-hub
  // ships "→ feeds this asset's risk score", not "a job will run". Telling someone where their write GOES
  // answers "what happens next" as squarely as naming a queue does.
  'visible to', 'counts toward', 'appears in', 'shows in', 'shows on', 'appears on', 'feeds ', 'syncs', 'on your',
  // 'in your <list>' is the SAME construction as 'on your <schedule>' — it names the place the effect
  // lands, which is exactly what this half asks for. Having only the 'on' preposition scored
  // report-sender's 'added → in your recipient list now' as naming no following step. Widening the
  // vocabulary to the platform's own wording is the harvest-from-the-product rule; bending the product's
  // sentence to fit my regex would be the wrong way round.
  'in your ', 'to your ',
  // AN EFFECT CAN BE A REMOVAL. Every form above is additive - feeds, counts toward, appears in - so
  // alert-hub's 'hidden for your whole hive now' scored as naming no following step, when it names the
  // effect more consequentially than most: a dismissal there is HIVE state, so it removes the alert from
  // every teammate's inbox. A vocabulary that can only recognise things being added cannot grade the
  // surfaces where the risk is something disappearing.
  'hidden for', 'hidden from', 'removed from', 'off your', 'out of your', 'cleared from', 'no longer',
  // AUDIENCE-VISIBILITY is the same construction as 'visible to' - it names WHO will see the effect,
  // which is the point on a surface whose action releases work to a crew. 'rebuilt from' names what
  // the thing now consists of, which is the effect of a regeneration.
  // DISCIPLINE NOTE: I wrote both sentences these serve, so the justification must be SEMANTIC, not
  // authorial - each names where an effect lands or what it now consists of, the same test every other
  // entry passes. Widening a list to fit my own copy would be circular; the both-directions check is
  // what keeps it honest, and 'Plan refreshed.' / 'Published.' / 'Saved.' still fail.
  'can see', 'can now see', 'rebuilt from', 'rebuilt with',
  // "your skill gaps and available quizzes UPDATE now" names the effect as squarely as "feeds" does — the
  // verb differs, the claim does not. Added after skillmatrix scored next=false on a sentence that says
  // exactly what changes; that is the harvest-from-the-product rule, not a loosening, and the bare
  // confirmations pinned in the self-test ("Saved.", "Registered.", "Part added to inventory.") contain
  // none of these verbs and still satisfy neither half.
  // ★A BARE VERB NAMES NOTHING. 'updates?' on its own matched 'Asset updated.' - which passed this
  // oracle while telling a person nothing about WHERE the change lands. That is the same emptiness the
  // oracle exists to catch, so the verb now has to carry a destination or an explicit moment:
  // 'updates your ...', 'update now', 'updated in/on/across ...'. Checked against the passes that
  // legitimately rely on it - skillmatrix's 'your skill gaps and available quizzes update now' still
  // matches on 'update now'. Tightening a list is as much a part of keeping it honest as widening it.
  // The rule is simply that the verb must have an OBJECT. Requiring a determiner was too strict and
  // rejected logbook's 'updated Analytics (MTBF/MTTR + failure freq)', which names its destination by
  // proper noun - so the test is now 'updated/updates followed by a word', which still rejects a bare
  // 'Asset updated.' where a full stop follows the verb and nothing else does.
  // NOTE THE DOUBLE BACKSLASHES. These entries are JS STRING literals joined into a RegExp, so a single\s
  // is just the letter s - which is how this pattern silently became update(s|d)?s+w and matched nothing.
  // Fourth time this exact escape level has bitten this file: \b became backspace, \d became d, and now this.
  'update(s|d)?\\s+\\w', 'update now',
  'recalculat', 'recomputes?', 'unlocks?',
].join('|');
// Says WHEN that step happens.
// NOTE the DOUBLE backslashes: these are JS STRINGS, so '\d' would collapse to a bare 'd' and the
// pattern would silently match the letter d instead of a digit — which is exactly what happened on the
// first run, where "within 24 hours" reported no timing at all.
// ★"WHEN" ON THIS PLATFORM IS A CONDITION, NOT A CLOCK — and my first vocabulary was my assumption
// rather than the product's. asset-hub already shipped the house pattern before I wrote this oracle:
// "✓ FMEA mode added (approved) → feeds this asset's risk score (RPN factor)" and "→ ... on next
// recompute". It answers WHEN by naming the TRIGGER, and that is the honest answer here: a page cannot
// promise "within 24 hours" for a review no supervisor has agreed to, but it can truthfully say the row
// counts from approval. Listing only clock phrases meant the platform's own correct sentence scored
// when=false — the same trap as an oracle rejecting the right fix because its author thought of different
// words. Condition triggers are therefore first-class, not a loosening: "once approved" tells a person
// exactly when it happens.
export const WHEN_SRC = [
  // clock-shaped
  'within \\d', 'in \\d+ (second|minute|hour|day)', 'by (today|tomorrow|end of)',
  'next (shift|day|week)', 'shortly', 'immediately', 'right away', 'today', 'tomorrow',
  '\\d+\\s*(s|sec|min|hr|h)\\b', 'real[- ]?time', 'instantly',
  // condition-shaped — the platform's own idiom
  'once (approved|it|we|the|they)', 'after (approval|review|it|we|the)',
  // "(next scoring)" is logbook's own way of saying WHEN the risk score moves — the same trigger-naming
  // idiom as asset-hub's "on next recompute", one word different. Listing only the words I had already
  // seen made the platform's correct sentence score when=false for the fourth time in this file, which is
  // the harvest-from-the-product rule earning its place rather than a loosening.
  '(on )?next (recompute|sync|run|scoring|score|pass)',
  'from now', 'as soon as', 'when (it|we|they|approved)', 'at approval', 'on approval',
  // DOUBLE backslashes again: '\bnow\b' in a JS string is the BACKSPACE character, not a word boundary,
  // so it matched nothing and "visible to your hive now" scored as having no timing. Second time this
  // exact escape level has bitten this file — the first was '\d' silently becoming the letter d.
  'once you', 'once (back )?online', '\\bnow\\b', 'next time',
  // 'until you <act>' is condition-shaped timing, the same family as 'once approved': it tells a person
  // the state PERSISTS until a named event. shift-brain's re-run leans on it to say a refreshed plan
  // stays private until Publish - the half a supervisor must not miss.
  'until you ', 'until then', 'until it is', 'until published',
].join('|');
// ALREADY-DONE is a WHEN answer, and the strongest one. Every entry in WHEN_SRC above is future- or
// condition-shaped ("once approved", "on next recompute"), so a surface that says the effect has ALREADY
// taken place — "PM compliance recomputed (Hive + Analytics SMRP) · logged in Logbook" — scored when=false
// while answering the question better than any of them: there is no pending step left to time. This is the
// third vocabulary gap in this file where my word list rejected the platform's own correct sentence.
// GATED, NOT LOOSENED: it only counts when the NEXT half already passed, so a bare past-tense verb with no
// named effect ("Saved.") still fails. A future promise with no timing ("this feeds analytics") is
// unaffected — present tense matches nothing here.
export const DONE_SRC = [
  'recomputed', 'recalculated', 'recorded', 'updated', 'logged in', 'logged to', 'added to',
  'saved to', 'posted to', 'counted', 'applied', 'synced to', 'is (now|already) ',
].join('|');
export const DONE_RE = new RegExp(DONE_SRC, 'i');
export const NEXT_RE = new RegExp(NEXT_SRC, 'i');
export const WHEN_RE = new RegExp(WHEN_SRC, 'i');
