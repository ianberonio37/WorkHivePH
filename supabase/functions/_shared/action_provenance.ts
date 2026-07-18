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
