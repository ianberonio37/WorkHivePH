// _shared/action_provenance.ts
// ============================================================================
// CL10 ACTION-faithfulness rail (2026-07-08, live-caught on the assistant/chat surface).
//
// PRINCIPLE (sibling of numeric_provenance.ts §1b, ai-engineer SKILL.md L821-822): the
// companion/assistant BRAIN is READ-ONLY + advisory. From a chat turn it NEVER writes to the
// logbook, schedules a PM or follow-up, updates a maintenance record, notifies a person, sends
// a message, or places an order. So a sentence asserting such a system write WAS COMPLETED
// ("Log entry added to CT-001 maintenance history", "Updated maintenance record for CT-001",
// "I've scheduled the follow-up", "Reminder set") is a fabrication BY CONSTRUCTION — a confident
// false "I did X" that, in a safety-adjacent maintenance context, makes a worker believe the
// system recorded something it did NOT. Live proof (assistant.html, Leandro/Baguio 2026-07-08):
// acknowledging "we set CT-001 torque to 137 Nm", the model returned "Updated maintenance record
// for CT-001: … Log entry added to CT-001 maintenance history." — verified against the DB: 0 new
// logbook rows, 0 agent_followups. The user was told it was logged; nothing was.
//
// SCOPE (tight, to preserve legit RECOMMENDATIONS): this strips ONLY COMPLETED-write claims
// (past-tense / passive-done: "added", "logged", "updated", "I've scheduled", "has been
// created"). It LEAVES advice intact — imperatives ("Schedule a vibration check in 48h", "Notify
// the L1 tech"), modals ("you should log this", "you can add…"), and drafting offers ("I can
// draft the request", "I've drafted the message") are recommendations / things the advisory
// assistant genuinely CAN do, not claims of a completed system write. The first-person branch
// additionally REQUIRES a system-record target so a discourse marker like "I've added the
// following recommendations:" is never stripped.
//
// Repair = STRIP the fabricated sentence; the CALLER appends one honest advisory clarifier when
// anything was stripped (the assistant can't write records; the worker must log it). Mirrors
// _shared/numeric_provenance.ts (strip + caller honest-fallback).
// ============================================================================

export interface ActionProvenanceResult {
  clean: string;      // answer with completed-write fabrication sentences removed
  stripped: string[]; // dropped sentences (for cost-log / debugging)
  hit: boolean;       // true if anything was stripped
}

// A sentence that is clearly a RECOMMENDATION / capability offer — never stripped even if a
// done-verb appears coincidentally ("you should have logged it", "I can draft the log entry").
const ADVICE_FRAME =
  /\b(?:you (?:should|can|could|may|might|need to|want to|ought to|must|have to)|please|consider|recommend(?:ed|ing)?|suggest(?:ed|ing)?|i (?:can|could|will|'ll|would|recommend|suggest) (?:draft|prepare|help|write|create|outline|show|point|send you)|want me to|make sure|be sure|remember to|don'?t forget|next step|to-?do|advise)\b/i;

// First-person completed system write: "I've logged…", "we scheduled…", "I just updated…".
// EXCLUDES advisory verbs (draft/prepare/outline/suggest/recommend/note) and conversational
// "noted/recorded that" — this branch also requires a SYSTEM_TARGET (below) to fire.
const FP_DONE =
  /\b(?:i|we)\b(?:'ve|'d|\s+(?:have|had|just|already|also|now|then)){0,3}\s+(?:added|logged|created|updated|saved|scheduled|filed|posted|registered|booked|ordered|submitted|assigned|set up|marked)\b/i;

// A system-record object/target the assistant CANNOT actually create or mutate from chat.
const SYSTEM_TARGET =
  /\b(?:log(?:book)?(?:\s*entr(?:y|ies))?|maintenance\s+(?:record|history|log)|service\s+history|asset\s+history|work\s*order|pm\s+(?:task|completion|schedule|record)?|follow[- ]?up|reminder|ticket|cmms|the\s+system|database|record\b)/i;

// Verb-FIRST completed write at a sentence / bullet start: "Updated maintenance record",
// "Added log entry", "Logged to history", "Scheduled follow-up" (PAST tense only — the present
// imperative "Schedule…"/"Add…"/"Log…" is advice and does NOT match).
const VERB_FIRST_DONE =
  /(?:^|[\n\-*•:]\s*)(?:updated|added|logged|created|saved|recorded|scheduled|filed|registered|marked)\s+(?:the\s+|a\s+|an\s+|your\s+|this\s+|new\s+)?(?:maintenance\s+|logbook\s+|log\s+|pm\s+|service\s+)?(?:record|entr(?:y|ies)|history|work\s*order|follow[- ]?up|reminder|ticket|note|schedule|log(?:book)?)\b/i;

// Nominal-passive completed write: "log entry added", "maintenance record has been updated",
// "reminder was set", "follow-up scheduled".
const NOMINAL_DONE =
  /\b(?:log(?:book)?\s*entr(?:y|ies)|maintenance\s+(?:record|history)|work\s*order|follow[- ]?up|reminder|ticket)\b[^.?!\n]{0,24}?\b(?:has been\s+|have been\s+|was\s+|were\s+|been\s+|is now\s+|now\s+)?(?:added|logged|created|updated|saved|recorded|scheduled|set|placed|filed|posted)\b/i;

// "added / logged it to the … history / record / log / system".
const ADDED_TO_STORE =
  /\b(?:added|logged|saved|recorded|posted|entered)\b[^.?!\n]{0,20}\b(?:to|in|into|onto)\s+[^.?!\n]{0,28}\b(?:history|record|log(?:book)?|system|cmms|database|file)\b/i;

// Action-log LABEL fabrication (live-caught 2026-07-08): the model returns an "Action:"/"Action
// Items:" block whose entries START with a PAST-TENSE record-write verb + colon — "Logged: PB-002
// bearing replaced", "Recorded: …", "Updated: …", "- - Logged: …". Colon-anchored so a present-tense
// imperative ("Log this…", "Schedule…", "Update the record when done") never matches — only a
// completed "I already did it" label does. Zero-or-more bullet markers eats "- - " list prefixes.
const LABEL_DONE =
  /^\s*(?:[-*•]\s*)*(?:\*\*)?(?:logged|recorded|updated|added|created|filed|saved|entered|posted)(?:\*\*)?\s*:/i;
// "<maintenance/task/it> logged", "logged as follows/below" — the header form "PB-001 pump
// maintenance logged as follows:".
const MAINT_LOGGED =
  /\b(?:maintenance|service|repair|task|entry|it|this)\s+(?:has been\s+|was\s+|is\s+|now\s+)?logged\b|\blogged\s+as\s+(?:follows|below|shown)\b/i;

// Split into units at newlines AND sentence boundaries so a markdown action-log ("Logged: …" on its
// own line) and a prose run ("Acknowledged. Log entry added. Notify X.") both break into per-claim
// units the filter can drop individually.
const UNIT_SPLIT = /\n+|(?<=[.?!])\s+/;

/** True if a single unit (line / sentence) asserts a COMPLETED system write by the assistant/system. */
function isCompletedWriteClaim(unit: string): boolean {
  if (!unit || ADVICE_FRAME.test(unit)) return false;
  if (LABEL_DONE.test(unit)) return true;                            // "Logged:", "Recorded:", "Updated:"
  if (MAINT_LOGGED.test(unit)) return true;                          // "… maintenance logged as follows"
  if (FP_DONE.test(unit) && SYSTEM_TARGET.test(unit)) return true;   // first-person + target
  if (VERB_FIRST_DONE.test(unit)) return true;
  if (NOMINAL_DONE.test(unit)) return true;
  if (ADDED_TO_STORE.test(unit)) return true;
  return false;
}

/**
 * CL10 action gate. Returns the answer with every sentence that fabricates a completed system
 * write removed. Recommendations, acknowledgements, and drafting offers are preserved.
 */
export function stripFalseActionClaims(answer: string): ActionProvenanceResult {
  if (!answer) return { clean: answer, stripped: [], hit: false };
  const stripped: string[] = [];
  const kept = answer.split(UNIT_SPLIT).filter((unit) => {
    if (isCompletedWriteClaim(unit)) {
      stripped.push(unit.trim());
      return false;
    }
    return true;
  });
  const clean = kept.join(" ").replace(/[ \t]+/g, " ").replace(/\s+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
  return { clean, stripped, hit: stripped.length > 0 };
}

// The honest clarifier the CALLER appends when a completed-write fabrication was stripped, so the
// worker knows the record was NOT written and how to actually persist it.
export const ACTION_HONEST_CLARIFIER =
  "Note: I can't write to your records directly — I've flagged what to capture, but you'll need to add it in the Logbook or PM page to save it.";

// ============================================================================
// PROPOSAL-surface rail (2026-10-08, voice-action-router).
//
// The voice router CLASSIFIES a spoken sentence and writes nothing. The page shows each intent as a card,
// and nothing is saved until the person confirms (logbook.create only fills the form they then save). So
// in the router's `narration`, ANY claim that a platform write already happened is false by construction.
// The advisory rail above misses the commonest shape, because it guards the assistant's own "I did X" and
// never looks at "you": live 2026-10-07 the router said "Naks, you logged a 2 hour brake pad replacement"
// with nothing saved. A proposal surface is therefore STRICTER than an advisory one: the subject does not
// matter (I / we / you / passive / elided), only that a record-write verb is in the past tense and is not
// hedged as future ("will be saved", "once logged") or negated ("nothing is saved yet"). The worker's own
// PHYSICAL work stays past tense and is never touched: "you replaced the V-belt" is true.
//
// The gateway's advisory rail stays OFF this route on purpose: its clarifier tells the person to add the
// record in the Logbook themselves, which is wrong here - the page applies the intent once they confirm.
// ============================================================================

// Record-write verbs whose past tense, on a proposal surface, can only mean "the platform did it".
const PROPOSAL_WRITE_VERBS = "logged|recorded|saved|deducted|filed|submitted|posted|entered|booked|stored";
// Verbs that are a platform write when the assistant is the subject, or when the object is a record.
const PROPOSAL_SYSTEM_VERBS =
  PROPOSAL_WRITE_VERBS + "|added|created|updated|scheduled|marked|closed|completed|removed|subtracted|registered|assigned|adjusted|reduced";

// Each pattern names its verb `v`; the text BEFORE that verb decides whether it is hedged or negated.
const PROPOSAL_DONE_PATTERNS: RegExp[] = [
  // anyone did the write: "you logged", "you've recorded", "I just saved", "we deducted"
  new RegExp(String.raw`\b(?:i|we|you)\b(?:'ve|'d|\s+(?:have|had|just|already|also|now|then|all)){0,3}\s+(?<v>${PROPOSAL_WRITE_VERBS})\b`, "gid"),
  // the assistant did a system change: "I've updated the PM", "we marked it", "I removed two from stock"
  new RegExp(String.raw`\b(?:i|we)\b(?:'ve|'d|\s+(?:have|had|just|already|also|now|then)){0,3}\s+(?<v>${PROPOSAL_SYSTEM_VERBS})\b`, "gid"),
  // passive, done: "has been logged", "have already been deducted"
  new RegExp(String.raw`\b(?:has|have|had)\s+(?:now\s+|just\s+|already\s+)?been\s+(?<v>${PROPOSAL_SYSTEM_VERBS})\b`, "gid"),
  // passive, state: "is now saved", "was deducted", "it's logged"
  new RegExp(String.raw`\b(?:is|are|was|were|it's|that's)\s+(?:now\s+|all\s+|already\s+)?(?<v>${PROPOSAL_WRITE_VERBS})\b`, "gid"),
  // a record as the subject: "stock updated", "PM marked as complete", "log entry added"
  new RegExp(String.raw`\b(?:stock|inventory|logbook|log\s*entry|entry|record|pm|work\s*order|count)\b[^.?!\n]{0,20}?\b(?<v>${PROPOSAL_SYSTEM_VERBS})\b`, "gid"),
  // the subject elided (the speaker is the assistant): "Logged it.", "Got it, deducted two", "and saved"
  new RegExp(String.raw`(?:^|[,;:!]\s*|\band\s+)(?<v>${PROPOSAL_WRITE_VERBS}|added|created|updated|marked|closed)\b`, "gid"),
  // "marked ... complete / done"
  new RegExp(String.raw`\b(?<v>marked)\b[^.?!\n]{0,30}\b(?:complete|completed|done|closed|finished)\b`, "gid"),
  // a bare "Done." / "All done!" as its own clause
  new RegExp(String.raw`(?:^|[,;:]\s*)(?:all\s+)?(?<v>done)\s*(?:[.!,]|$)`, "gid"),
];
// a verb led by these is future or conditional: "will be saved", "once logged", "to get logged"
const PROPOSAL_FUTURE_LEAD =
  /\b(?:be|get|gets|getting|being|once|when|after|if|until|before|to)\s+(?:(?:now|then|also|only|automatically|properly|all)\s+)?$/i;
// a verb led by these is negated: "nothing is saved yet", "hasn't been logged" (idiomatic "no problem" excluded)
const PROPOSAL_NEGATED_LEAD =
  /(?:\bnothing\b|\bnot\b|\bnever\b|\bnone\b|\bnor\b|n't\b|\bno\b(?!\s+(?:worries|problem|prob|sweat)\b))[^.,;!?]{0,40}$/i;

/** True if a unit claims, in the past tense, that a platform write already happened. */
function isProposalDoneClaim(unit: string): boolean {
  if (!unit || !unit.trim()) return false;
  for (const re of PROPOSAL_DONE_PATTERNS) {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(unit)) !== null) {
      const v = (m as RegExpExecArray & { indices?: { groups?: Record<string, [number, number]> } }).indices?.groups?.v;
      const at = v ? v[0] : m.index;
      const lead = unit.slice(Math.max(0, at - 60), at);
      if (!PROPOSAL_FUTURE_LEAD.test(lead) && !PROPOSAL_NEGATED_LEAD.test(lead)) return true;
      if (m[0].length === 0) re.lastIndex++;
    }
  }
  return false;
}

/**
 * Proposal rail: removes every unit of a PROPOSAL narration (nothing is saved yet) that claims a platform
 * write already happened. Future/conditional proposals and the worker's own physical work are kept.
 */
export function stripProposalDoneClaims(narration: string): ActionProvenanceResult {
  if (!narration) return { clean: narration, stripped: [], hit: false };
  const stripped: string[] = [];
  const kept = narration.split(UNIT_SPLIT).filter((unit) => {
    if (isProposalDoneClaim(unit)) {
      stripped.push(unit.trim());
      return false;
    }
    return true;
  });
  const clean = kept.join(" ").replace(/[ \t]+/g, " ").trim();
  return { clean, stripped, hit: stripped.length > 0 };
}

// What the person hears instead of a stripped claim: true on every route the router returns.
export const PROPOSAL_HONEST_CLARIFIER = "Nothing is saved yet. Check the details and confirm to continue.";

/** The router's narration made honest: stripped claims replaced by the clarifier, kept under `cap` chars. */
export function honestProposalNarration(narration: string, cap = 280): { narration: string; stripped: string[] } {
  const g = stripProposalDoneClaims(narration || "");
  if (!g.hit) return { narration: (narration || "").slice(0, cap), stripped: [] };
  const room = Math.max(0, cap - PROPOSAL_HONEST_CLARIFIER.length - 1);
  const kept = g.clean.slice(0, room).trim();
  return { narration: kept ? `${kept} ${PROPOSAL_HONEST_CLARIFIER}` : PROPOSAL_HONEST_CLARIFIER, stripped: g.stripped };
}
