/**
// capability: voice_to_journal
 * voice-journal-agent - Specialist behind the gateway's "voice-journal" route.
 *
 * The voice journal is the worker's private spoken log. Each turn:
 *   1. Browser records audio, hits voice-transcribe (Whisper auto-language).
 *   2. Browser hits ai-gateway with { agent: "voice-journal", message, context: { lang } }.
 *   3. Gateway redacts PII, loads memory (last 10 turns + rolling summary),
 *      forwards to THIS function with { message, context, memory, gateway: true }.
 *   4. This function builds a journal companion prompt that:
 *        - Speaks back in the same language the user used.
 *        - Acknowledges what was shared in 1-3 sentences.
 *        - Asks at most one gentle follow-up to keep the journal flowing.
 *        - Surfaces a recurring theme when the memory block shows one.
 *   5. Returns { answer, lang } envelope. Gateway saves the turn pair to
 *      agent_memory with meta.lang for per-language semantic recall later.
 *
 * Notes:
 *  - No DB queries here. The journal is purely conversational; recall is
 *    already injected via the memory block built by the gateway.
 *  - jsonMode is off because the answer is freeform prose, not a schema.
 *  - The system prompt is a `const` for future prompt-cache compatibility.
 *
 * Skills consulted: ai-engineer (callAI defaults, 500-char transcript cap
 * already enforced upstream, system prompt as const), security (no PII
 * leak: worker_name comes in already redacted as "<redacted>"), mobile-
 * maestro (response targets browser speechSynthesis, so keep replies short).
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

// contract-allow: voice journal write + retrieval
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { log } from "../_shared/logger.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
import { redactPII } from "../_shared/redactPII.ts";
// Persona Contract: one shared module across every conversational AI
// surface. See WORKHIVE_PERSONA_CONTRACT.md. Voice Journal runs in the
// "conversational" mode — full persona, freeform prose.
import { clampPersona, buildPersonaBlock } from "../_shared/persona.ts";
import { gateNumericProvenance } from "../_shared/numeric_provenance.ts";
// Phase G3 (Grounding Doctrine §2): typed fact-sheet + slot-fill render. On a
// value-seeking data-read turn the model emits {{FACT:id}} placeholders and CODE
// inserts the real numbers — closing G1's coincidental-match residual by
// construction. Strictly additive: any miss falls back to the G1 free-prose path.
import {
  buildOpsFactSheet, isDataReadTurn, buildFactSheetPromptBlock,
  parseG3Json, renderFactSheet,
} from "../_shared/factsheet_render.ts";

// Warm module-scope client (PRODUCTION_FIXES #46 pattern). Cost log writes
// service-role, RLS-bypass; no per-request createClient cost on warm cold-start.
const _WH_SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const _WH_SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const _whWarmClient: SupabaseClient | null =
  _WH_SUPABASE_URL && _WH_SERVICE_KEY
    ? createClient(_WH_SUPABASE_URL, _WH_SERVICE_KEY)
    : null;
void _whWarmClient;

const MODEL_VERSION     = "voice-journal-v1";
const MAX_MESSAGE_CHARS = 500;        // matches gateway-side cap, prompt-injection safety
const MAX_TOKENS_OUT    = 280;        // keep TTS-friendly: ~30s spoken reply max

const LANGUAGE_NAMES: Record<string, string> = {
  en:  "English",
  tl:  "Filipino (Tagalog)",
  fil: "Filipino (Tagalog)",
  ceb: "Cebuano",
  ilo: "Ilocano",
  hil: "Hiligaynon",
  pam: "Kapampangan",
  war: "Waray",
  bik: "Bikol",
  pag: "Pangasinan",
};

// Persona Contract: tone/voice/name come from the shared module so every
// conversational surface (voice-journal, floating-AI, assistant) feels
// like one companion. Voice Journal extends the shared "conversational"
// block with two Voice-Journal-only rules below (memory recall behavior
// + journal-finality guidance).
const VOICE_JOURNAL_EXTRA_RULES = `
Voice-Journal-specific rules:
- The memory block may include a "Past journal entries that look related to today's voice note" section. If the worker mentioned the same person, asset, feeling, or goal before, name it gently in one short sentence. Paraphrase only — never invent.
- If the memory shows a recent recurring theme, naming it is fine, but prefer the most relevant signal.
- LIVE OPERATIONS SNAPSHOT: the memory block may begin with a "=== LIVE OPERATIONS SNAPSHOT ===" section listing this hive's verified active alerts, overdue PM count, and the full list of registered asset tags. When present, it is your SINGLE SOURCE OF TRUTH for current operational questions. If the worker asks about anything the snapshot prints — open jobs/alerts, overdue PM, which assets exist, MTBF/MTTR/OEE, inventory/stock, PM compliance, team/skills, projects, or asset risk — answer from the snapshot's real numbers and names; do NOT deflect for things the snapshot already contains. If the snapshot is absent or a specific figure (a metric not listed above, or a per-item reading not shown) is not in it, then say plainly you don't have that number on this surface and point them to the matching page.
- ASSET EXISTENCE: only treat an asset tag as real if it appears in the snapshot's registered-asset list (or the worker is clearly inventing a hypothetical). If they ask about a tag that is not in that list (e.g. a "P-203" when only "P-001" is registered), tell them it is not one of their registered assets and ask if they meant a real one — do NOT describe its condition, history, temperature, or events as if it existed.
- THE SNAPSHOT IS YOUR LIVE DATA — quote ONLY what it literally prints, but it now carries MANY of this hive's computed figures, not just counts. Depending on what's available it includes: the active-alert count + top alerts, the overdue-PM count, the registered-asset list, reliability (hive-average and per-machine MTBF/MTTR), OEE, inventory/stock (parts tracked, how many are low or out, which parts), PM compliance %, team/skills (member count, disciplines, skill levels), projects (codes, % complete, blockers), and asset risk (which assets are highest-risk, their level and days-to-failure). When the worker asks about ANY figure that IS printed in the snapshot, quote its real number/name directly — that is the correct grounded answer, NOT a reason to deflect. You still do NOT have anything the snapshot does NOT print: a metric not listed, a per-item reading or history beyond what's shown, temperatures, or a value for an asset with no detail in the snapshot. For those, say plainly it isn't in this snapshot and point to the matching page — and never compute, estimate, or state a number that isn't printed.
- EVEN FOR A REGISTERED ASSET, do not invent its failure history, event counts ("three corrective events"), recurrence, or readings. If the asset is in the list but the snapshot has no detail for it, say it is one of your registered assets but you don't have its detailed history on this surface (the Work Assistant has it). Naming it as a "top alert" is fine ONLY if the snapshot lists it among the top alerts.
- OUT-OF-SCOPE DOMAINS (genuinely NOT in the snapshot): marketplace listings/prices, the day-plan schedule, community/forum posts, individual logbook-entry narrative, and any per-item detail not shown above (e.g. a single part's full transaction history, one asset's reading). When the worker asks about THESE, do NOT invent specifics — no listing or price, no scheduled day-plan slot, no certification you can't see, no fabricated detail. Say plainly you don't have that here and point them to the right page (Marketplace / Day Planner / Community / Logbook). IMPORTANT: inventory/stock, the skill matrix (team & disciplines), project status (% complete, blockers), PM compliance, MTBF/MTTR/OEE, and asset risk ARE in the snapshot now when listed above — ANSWER those from the snapshot's real numbers, do NOT deflect them to another page. Only deflect a domain when its figure is genuinely absent from the snapshot.
- CAPABILITY BOUNDS: you are a conversational companion, NOT an action service. You CANNOT place orders, buy parts, send emails or texts, make phone calls, book or schedule visits, process payments, control or start equipment remotely, grant hive/system access, or read a photo/PDF the worker holds up to the screen. When asked to DO one of these, say plainly you can't do that from here — do NOT claim you did it, and do NOT say "I can book/order/pay/call/translate it". Offer the real alternative instead: you can DRAFT the message/text for them to send, summarise what to tell the vendor, or point them to the right page or person (Inventory page, their supplier, their supervisor, the SCADA/HMI for equipment). Honesty about a limit is correct; faking the action is not.
- "You mentioned earlier" refers ONLY to a fact stated in a PRIOR turn shown in the memory block. NEVER restate the worker's CURRENT question or request as something they "mentioned earlier" (do not say "you mentioned earlier that you want a shift summary" when they just asked for one) — just answer it directly.
- MEMORY IS NOT LIVE TRUTH: a value, asset, reading, or "situation" that appears only in your memory block / rolling summary is something the worker SAID at some point, not a verified current fact. You may reference it as "you mentioned earlier…", but never restate a remembered number (a backlog figure, a PM-compliance %, a temperature, an event count) as the CURRENT live value, and never volunteer a remembered specific into an answer as if you just looked it up. When they directly ask "what did I tell you the torque was?" you DO quote their own stated value back verbatim (see the Conversation memory rule above) — that legitimate recall is unchanged; what is banned is dressing up stale or uncertain memory as current operational truth.
- NEVER make up a record, a count, an OEE, an MTBF, a temperature, an event tally, or any KPI value, and never name an internal database view. If you don't have it in the snapshot, the conversation, or what the worker just told you, say so plainly.
- FALSE-PREMISE GUARD (the most important recall rule): a question can falsely PRESUPPOSE you already hold a value — "what OEE number did I give you?", "what PM compliance figure did I quote?", "what was that vibration reading I told you about?", "what did we decide about the boiler last shift?". If that specific value/decision is NOT actually written in your memory block, the premise is FALSE. Answer "You haven't given me that figure" or "I don't have a record of you telling me that" and supply NO number, reading, percentage, or decision. The grammar of a question assuming a value exists does NOT make one exist, and a worker asking confidently does NOT mean they told you before. Refuse the presupposition; never emit a plausible figure just to satisfy the shape of the question.

You will be given:
- The worker's latest spoken message
- The detected language code (ISO-639-1)
- A memory block with their recent turns, a rolling summary, and optionally a "Past journal entries" section

Reply with just the prose response, nothing else.`;

interface AgentRequest {
  message?:     string;
  context?:     Record<string, unknown>;
  memory?:      string;
  hive_id?:     string | null;
  worker_name?: string;
  gateway?:     boolean;
}

interface AgentResponse {
  answer: string;
  lang:   string;
  error?: string;
}

// ── Unsupported false-recall guard (Grounding Doctrine, 2026-06-14 — the family-I tic) ─────
// The prompt already bans "you mentioned earlier you wanted X" when the worker didn't (rule above),
// but a weak free-tier model still pads filler/greeting turns ("are you still there?", "what can
// you help me with?") with an INVENTED recall frame ("you mentioned earlier you wanted a shift
// summary"). WAT: a must-be-exact behaviour is enforced in CODE, not by re-asking the model
// (same call as the em-dash and numeric-provenance rules). When there is NO conversational memory
// (a fresh / cleared session — the snapshot-only or empty case), ANY "you mentioned / you wanted /
// as you noted …" claim is unsupported BY CONSTRUCTION, so strip those sentences. Gated strictly on
// no-conversational-memory, so legitimate C-family recall (the worker DID state something earlier)
// is never touched. Mirrors the G1 numeric strip: drop the offending sentence, keep the rest.
const _RECALL_FRAME_RE = /\b(?:you (?:mentioned|said|told me|noted|wanted|asked|brought up|indicated)|earlier,? you|as you (?:mentioned|noted|said)|last time you|previously you|we (?:discussed|talked about)|came up earlier)\b/i;
function stripUnsupportedRecall(text: string, hasConvoMemory: boolean): string {
  if (hasConvoMemory || !text) return text;            // legitimate recall is possible → leave it
  const sentences = text.split(/(?<=[.!?])\s+/);
  const kept = sentences.filter((s) => !_RECALL_FRAME_RE.test(s));
  const out = kept.join(" ").replace(/\s+/g, " ").trim();
  return out.length >= 12 ? out : text;                // never gut the whole reply to nothing
}

// ── False-premise affirmation guard (Grounding Doctrine, 2026-06-14 — family-C false-bait) ─────
// The worker FALSELY claims they gave a value earlier ("earlier I gave you an OEE number, what was
// it?", "what PM compliance figure did I quote you?"). The prompt's false-premise rule says deny it,
// but the weak model TICS: it opens with a hollow affirmation ("you mentioned earlier about the OEE
// number") that rubber-stamps the false premise, before (sometimes) serving the real snapshot value
// or denying. Reading every probe: the model NEVER invents a fake number here — the only defect is
// that hollow opener. So strip ONLY a recall-frame sentence that carries NO digit, and ONLY when the
// question claims a prior value. A genuine recall ("you told me 85 Nm") keeps its digit → untouched;
// the grounded remainder ("the snapshot shows OEE is 86%") survives → the reply becomes a clean
// grounded answer or an honest denial. Cannot break legitimate recall (which always carries the value).
const _CLAIMS_PRIOR_VALUE_RE = /\b(i (?:gave|told|quoted|mentioned|sent) you|did i (?:give|tell|quote|mention)|i (?:gave|told|quoted) you (?:a|an|the)|that .* i told you about)\b/i;
function stripFalsePremiseAffirmation(text: string, message: string, convoMemory: string, snapText: string): string {
  if (!text || !_CLAIMS_PRIOR_VALUE_RE.test(message || "")) return text;
  // numbers ACTUALLY stated by the WORKER. The memory string labels turns "Worker:" / "Agent:"
  // (memory.ts); a number the COMPANION volunteered earlier (e.g. an invented "14-day watch line")
  // must NOT count as "what you told me", so exclude "Agent:"/"Assistant:" lines. The rolling summary
  // is already worker-only (it records only facts the worker stated), so non-Agent lines are kept.
  // Trust ONLY the live conversation's worker turns + the (worker-only) summary. Exclude:
  //  - "Agent:"/"Assistant:" turns (a number the companion volunteered is not "what you told me"),
  //  - the "Past journal entries … (… similar)" SEMANTIC-RECALL section — RAG-retrieved old entries
  //    that can contain the companion's OWN earlier fabrications (the false-memory LOOP), so they are
  //    not a reliable proof the worker stated a value for THIS recall.
  const workerText = (convoMemory || "").split(/\n/)
    .filter((ln) =>
      !/^\s*(agent|assistant)\s*:/i.test(ln) &&
      !/past journal entries|similar\)\s*:|^\s*#\d/i.test(ln))
    .join(" ");
  const memNums = new Set(workerText.match(/\d+\.?\d*/g) || []);
  // …versus numbers that are LIVE snapshot KPIs (alerts/OEE/MTBF/PM%). A snapshot KPI presented as
  // "the figure YOU gave me earlier" is a misattribution by construction — it's the current metric,
  // not a worker quote — even if it leaked into convo memory via a PRIOR COMPANION turn (the
  // who-said-what hole). So a recalled number that is a snapshot value is NOT a valid recall.
  const snapNums = new Set((snapText || "").match(/\d+\.?\d*/g) || []);
  const sentences = text.split(/(?<=[.!?])\s+/);
  const kept = sentences.filter((s) => {
    if (!_RECALL_FRAME_RE.test(s)) return true;                 // not a recall claim → keep
    const nums = s.match(/\d+\.?\d*/g) || [];
    if (nums.length === 0) return false;                        // hollow recall affirmation → strip
    // keep ONLY if every recalled number was really stated by the worker AND is not just a live KPI
    return nums.every((n) => memNums.has(n) && !snapNums.has(n));
  });
  const out = kept.join(" ").replace(/\s+/g, " ").trim();
  return out.length >= 12
    ? out
    : "I don't have a record of you giving me that figure. Want to tell me now, or should I pull what the live snapshot has?";
}

// ── Misbound-recall guard (Grounding Doctrine, 2026-06-15 — G-Accept family-K residual) ───────
// G-Accept surfaced the recall-precision floor: the SAME tic ("grab the nearest remembered number")
// in two shapes, both of which the persona prompt ALREADY forbids (CONVERSATION_RECALL "MATCH THE
// THING ASKED, NEVER SUBSTITUTE… a regrease interval is NOT a vibration reading… 'what did Bryan say'
// is NOT your own torque value") but a weak free-tier model violates run-to-run → WAT: enforce in CODE.
//   (A) CROSS-SLOT: "what VIBRATION reading did I give you?" (only a TORQUE was stated) → model pivots
//       to "the flange torque is 85 Nm" instead of abstaining on the asked parameter.
//   (B) ISOLATION: "what did Bryan tell you privately?" → model answers with the worker's OWN stored
//       number (torque 85) instead of abstaining — it has no access to another worker's private words.
// Common mechanic: a reply RECALL-frame sentence surfacing a DIGIT that the question did NOT ask for.
// (A) keeps a recall that names the asked PARAMETER; (B) drops ANY remembered-number recall. A clean
// abstention (recall frame with no digit) and an unrelated reply are untouched.
// NB "current" is deliberately EXCLUDED — it is far more often the adjective ("the current
// regrease interval I set") than the electrical-current parameter, which would false-match; motor
// current is covered by "amperage". Each noun is a DISTINCTIVE physical quantity a worker states.
const _PARAM_NOUNS = [
  "torque", "vibration", "regrease", "temperature", "temp", "pressure", "speed", "rpm",
  "flow", "clearance", "tolerance", "runout", "thickness", "viscosity", "amperage",
  "voltage", "setpoint", "backlash", "deflection", "preload",
];
const _PARAM_RE = new RegExp(`\\b(${_PARAM_NOUNS.join("|")})\\b`, "ig");
// first-person "a value I PROVIDED earlier" cue — distinguishes a recall ask from a live data ask.
const _RECALL_PROVISION_RE = /\b(did i (?:give|tell|mention|set|say|quote|report)|i (?:gave|told|mentioned|set|said|quoted|reported)|i told you|i gave you|remind me what i|recall (?:the|my|what i))\b/i;
// a reply sentence that ASSERTS a worker-provided value: the shared recall frame OR a "you did
// mention/give/say" variant the shared regex (which keys on "you mentioned", not "you did mention")
// would otherwise miss.
const _ASSERTS_RECALL_RE = /\byou did (?:mention|say|give|tell|set|quote)\b/i;
// isolation ask: another worker's / private words the companion must not claim to hold.
const _ISOLATION_RE = /\b(what did \w+ (?:tell|say|share|mention|report|whisper)|privately|in private|behind closed doors|another (?:worker|tech|technician|person|colleague)|someone else (?:told|said|shared)|the other (?:guy|tech|worker))\b/i;
function _paramsIn(s: string): Set<string> {
  const out = new Set<string>();
  for (const m of s.toLowerCase().matchAll(_PARAM_RE)) out.add(m[1] === "temp" ? "temperature" : m[1]);
  return out;
}
function stripCrossSlotRecall(text: string, message: string): string {
  if (!text) return text;
  const msgParams = _paramsIn(message);
  let dropped = false;
  const sentences = text.split(/(?<=[.!?])\s+/);
  const kept = sentences.filter((s) => {
    if (!_RECALL_FRAME_RE.test(s) && !_ASSERTS_RECALL_RE.test(s)) return true;  // not a recall claim → keep
    if (!/\d/.test(s)) return true;                                   // recall with no value (honest abstention) → keep
    const sParams = _paramsIn(s);
    if (sParams.size === 0) return true;                              // generic number recall (no param noun) → other guards
    // THE INVARIANT: a recalled parameter-VALUE is legitimate ONLY if the worker's CURRENT message
    // references that parameter. Covers all three family-K shapes uniformly — a cross-slot recall ask
    // (asked vibration, recalled torque), an isolation ask ("what did Bryan say" names no param), and
    // an unprompted store/command turn ("regrease every 2 weeks now" → volunteered torque 85). A
    // legitimate recall (the worker named the parameter) is untouched.
    if ([...sParams].some((p) => msgParams.has(p))) return true;
    dropped = true;
    return false;
  });
  if (!dropped) return text;
  // Isolation ask: nothing the worker stored answers "what did X say privately" — give a clean
  // abstention rather than keep a dangling "want me to note that?" remainder.
  if (_ISOLATION_RE.test(message || "")) {
    return "I can only recall what you've told me directly, I don't have access to what another worker shared privately.";
  }
  const out = kept.join(" ").replace(/\s+/g, " ").trim();
  if (out.length >= 12) return out;                                  // useful remainder (advice, ack) survives
  // Whole reply was the misbound recall → honest fallback keyed to the ask type.
  if (msgParams.size && _RECALL_PROVISION_RE.test(message || "")) {
    return `I don't have a ${[...msgParams][0]} value from you in this conversation that I can point to. Want to tell me now and I'll hold onto it?`;
  }
  return "Got it.";
}

// ── Ungrounded event-tally guard (Grounding Doctrine, 2026-06-14 — found by the HELD-OUT diverse run) ─
// The aggregate snapshot carries alert/PM COUNTS + asset tags + KPIs, but NEVER per-event / per-line
// breakdown attributions ("two of the four breakdowns this week were on the compressor line"). Asked
// an un-served analytics question (e.g. planned-vs-reactive split), the model sometimes fabricates a
// hive-specific event tally — and the G1 numeric gate misses it because the numbers are WORDED
// (two/four), not digits (G1 is digit-only by design, to avoid stripping innocent "you have two
// options"). Strip a sentence that asserts a HIVE-SPECIFIC event/failure/breakdown COUNT, UNLESS the
// on-demand logbook block was fetched this turn (real recent-failure data is then present). Generic
// domain advice ("a pump might see several failures a year") is protected by the hedge guard.
const _EVENT_COUNT_RE = /\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|several|a couple|a few|a handful)\b[^.?!]{0,40}\b(?:corrective|reactive|unplanned|logged|recent)?\s*(?:events?|failures?|breakdowns?|trips?|incidents?)\b/i;
const _HIVE_SPECIFIC_RE = /\b(this (?:week|month|shift|morning|quarter|year)|today|so far|we(?:'ve| have| had)?|you(?:'ve| have| had)?|our |on the \w+ line|recently)\b/i;
const _GENERIC_HEDGE_RE = /\b(typically|usually|generally|often|might|may|can |could|would|if (?:poorly|not|the)|on average|industry|world[- ]class|benchmark|per year|a year\b)\b/i;
function stripUngroundedEventClaim(text: string, userBlock: string): string {
  if (!text || /v_logbook_truth/.test(userBlock || "")) return text;   // real failure data present
  const sentences = text.split(/(?<=[.!?])\s+/);
  const kept = sentences.filter((s) =>
    !(_EVENT_COUNT_RE.test(s) && _HIVE_SPECIFIC_RE.test(s) && !_GENERIC_HEDGE_RE.test(s)));
  const out = kept.join(" ").replace(/\s+/g, " ").trim();
  return out.length >= 15
    ? out
    : "I don't have that detailed failure history on this surface. The Work Assistant and the Analytics page carry the per-asset breakdown and the planned-versus-reactive split.";
}

// ── Unregistered-asset claim guard (Grounding Doctrine, 2026-06-14 — HELD-OUT diverse run dv-03) ─
// A worker can ASSERT a false event for a non-existent asset ("PUMP-X tripped again overnight, walk
// me through its history"). The model sometimes ECHOES the premise ("another trip on PUMP-X adds to
// the reactive load") before deflecting — affirming a fake asset's event. The snapshot lists the
// ONLY real asset tags; strip any sentence that makes a claim about a tag NOT in that list, while
// KEEPING explicit denials ("PUMP-X isn't one of your registered assets"). Tags = UPPER hyphenated
// tokens (AC-001, PUMP-X, CHILLER-7), so lowercase prose ("planned-versus-reactive") is never a tag.
const _ASSET_TAG_RE = /\b[A-Z]{1,8}-[A-Z0-9]{1,4}\b/g;
const _ASSET_DENIAL_RE = /\b(not one of|isn't|is not|not (a |an )?registered|no record|doesn't (show|have|exist|include)|does not|don't have|no asset|couldn't find|could not find|not listed|no such|not in (your|the)|isn't registered)\b/i;
function _registeredTags(userBlock: string): Set<string> | null {
  const m = userBlock.match(/ONLY real asset tags[^:]*:\s*([^\n.]+)/i);
  if (!m) return null;                                   // no registered list in grounding → can't judge
  const tags = m[1].match(_ASSET_TAG_RE) || [];
  return tags.length ? new Set(tags.map((t) => t.toUpperCase())) : null;
}
function stripUnregisteredAssetClaim(text: string, userBlock: string): string {
  const reg = _registeredTags(userBlock);
  if (!text || !reg) return text;
  const sentences = text.split(/(?<=[.!?])\s+/);
  const kept = sentences.filter((s) => {
    const tags = (s.match(_ASSET_TAG_RE) || []).map((t) => t.toUpperCase());
    if (!tags.some((t) => !reg.has(t))) return true;     // only registered tags (or none) → keep
    return _ASSET_DENIAL_RE.test(s);                     // unregistered tag present: keep a denial, strip an affirmation
  });
  const out = kept.join(" ").replace(/\s+/g, " ").trim();
  return out.length >= 12
    ? out
    : "That isn't one of your registered assets. Did you mean one of the tags in your hive? I can pull its details if so.";
}

// ── Un-served-metric claim guard (Grounding Doctrine, 2026-06-14 — HELD-OUT diverse run dv-10) ─
// The ops snapshot is a POINT-IN-TIME aggregate: it has NO per-metric TARGETS, NO time-series TRENDS,
// and does NOT compute the planned-vs-reactive ratio. The model nonetheless fabricates these by
// borrowing an unrelated grounded number ("your planned-vs-reactive ratio is 37%" — that's PM
// compliance; "below your 80% target"; "falling for two months"). G1 misses them via coincidental
// number-match (the G3-class residual). Strip, by construction: a fabricated %-TARGET (not benchmark-
// framed), a multi-period TREND assertion (snapshot has no history), and any planned-vs-reactive
// ratio VALUE (not a computed metric). Offers ("pull the trend graph?") survive (no trend VERB).
// per-metric TARGET/THRESHOLD words — the snapshot defines none of these, so an "N% target/
// threshold/watch-line/limit" is fabricated UNLESS N is a real world-class benchmark value.
const _TARGET_PCT_RE = /\b(?:target|goal|threshold|watch[- ]?line|limit|cap|ceiling|quota|benchmark)\b/i;
const _BENCH_VALS = new Set(["85", "90", "95", "99", "100"]);   // ISO-22400 world-class OEE family
const _TREND_VERB_RE = /\b(falling|fallen|rising|risen|declin(?:e|ed|ing)|dropp?(?:ing|ed)?|climb(?:ing|ed)|worsen(?:ing|ed)|trending (?:up|down)|been (?:going )?(?:up|down))\b/i;
const _PERIOD_RE = /\b(?:month|week|quarter|day|year)s?\b/i;
const _PVR_RE = /\bplanned[- ]?(?:vs\.?|versus|to)[- ]?reactive\b/i;
function stripUnservedMetricClaims(text: string): string {
  if (!text) return text;
  const sentences = text.split(/(?<=[.!?])\s+/);
  const kept = sentences.filter((s) => {
    const pctM = s.match(/(\d{1,3})\s*%/);
    const hasPct = !!pctM;
    // a per-metric target/threshold with a NON-benchmark value (e.g. "80% target", "65% threshold")
    // is fabricated; a real world-class value ("85%") in a benchmark statement is fine.
    const fabTarget = _TARGET_PCT_RE.test(s) && hasPct && !_BENCH_VALS.has(pctM![1]);
    // a trend over time (snapshot is point-in-time): a trend verb + a period, OR an explicit
    // "trending up/down" / "trend is up/down" (inherently temporal, no period word needed).
    const fabTrend = (_TREND_VERB_RE.test(s) && _PERIOD_RE.test(s))
      || /\btrend(?:ing)?\b[^.?!]{0,20}\b(up|down|upward|downward|worse|better|higher|lower)\b/i.test(s)
      || /\b(trending (?:up|down)|been (?:climbing|dropping|falling|rising))\b/i.test(s);
    const fabPvr = _PVR_RE.test(s) && (hasPct || /\bratio|split|\d/.test(s));   // we don't compute this
    return !(fabTarget || fabTrend || fabPvr);
  });
  const out = kept.join(" ").replace(/\s+/g, " ").trim();
  return out.length >= 12
    ? out
    : "I don't compute a planned-versus-reactive split or trend on this surface, the Analytics page has those. I can pull the live counts I do have if useful.";
}

// ── Numeric-provenance gate (Grounding Doctrine Phase G1, 2026-06-14) ─────────
// SUPERSEDES the reactive `stripUngroundedKpi` KPI-keyword rail (which leaked on
// the first unknown framing - the live "...41% from a target of 80%" fabrication).
// The new gate enumerates NO KPI names; it traces EVERY number in the answer to
// the grounded input / benchmark table / a tight date-duration-ordinal allowlist
// and strips any sentence with an untraceable number (STRICT, locked with Ian).
// Logic lives in `_shared/numeric_provenance.ts`; the eval counterpart in
// companion_fabrication_sweep.py grade() uses INDEPENDENT logic. See the usage in
// the response pipeline below (was the stripUngroundedKpi call).

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);

  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return json(corsHeaders, 405, { error: "POST only" });
  }

  let body: AgentRequest;
  try {
    body = await req.json();
  } catch {
    return json(corsHeaders, 400, { error: "Invalid JSON" });
  }

  const rawMessage = typeof body.message === "string" ? body.message.trim() : "";
  if (!rawMessage) {
    return json(corsHeaders, 400, { error: "Missing message" });
  }
  // Defence-in-depth: even when called via the gateway (which already redacts),
  // run redactPII again so a direct-from-cron or test caller cannot leak emails
  // or phone numbers to the LLM provider. The gateway-redacted "<redacted>"
  // tokens pass through unchanged.
  const message = redactPII(rawMessage.slice(0, MAX_MESSAGE_CHARS));

  const ctx = body.context && typeof body.context === "object" ? body.context : {};
  const rawLang = typeof ctx.lang === "string" ? ctx.lang.trim().toLowerCase() : "";
  // Clamp to supported languages. Whisper occasionally mis-tags short
  // multilingual phrases (e.g. an English sentence starting with "Hai"
  // gets tagged Indonesian). The voice journal only supports English +
  // Philippine languages; everything else falls back to English so the
  // user-facing lang chip stays meaningful and the prompt's "reply in
  // English" rule is consistent with the displayed detection.
  const lang     = LANGUAGE_NAMES[rawLang] ? rawLang : "en";
  const langName = LANGUAGE_NAMES[lang];

  // Persona Contract: ctx.persona wins (per-call override from the chip
  // picker); falls back to worker_profiles.preferred_persona via the
  // gateway-side identity layer (already in ctx if provided). Unknown
  // values clamp to DEFAULT_PERSONA.
  const personaKey = clampPersona(ctx.persona);
  const systemPrompt =
    buildPersonaBlock(personaKey, "conversational") +
    VOICE_JOURNAL_EXTRA_RULES;

  // Memory block can contain raw worker_name slips if the gateway memory layer
  // wrote them; redact again here at the LLM boundary.
  const rawMemory = typeof body.memory === "string" && body.memory.trim()
    ? body.memory.trim()
    : "";
  // The gateway PREPENDS the "=== LIVE OPERATIONS SNAPSHOT ===" block (computed hive-internal truth
  // from canonical views — counts, KPIs, asset tags, project/part names; PII-free BY CONSTRUCTION)
  // before the conversational memory, separated by a blank line. Re-redacting it MANGLES computed
  // codes/IDs: the loose phone regex turns a project code "CON-2026-001 75%" into "CON-<phone>%",
  // silently deleting the value the companion is meant to serve. So redact ONLY the conversational
  // memory and pass the snapshot through verbatim. (Snapshot helpers must only emit non-PII computed
  // fields — never a raw worker name / email / notes free-text — which buildOpsSnapshot honours.)
  const SNAP_HEAD = "=== LIVE OPERATIONS SNAPSHOT";
  let memoryBlock: string;
  // Does the block carry actual CONVERSATIONAL memory (prior turns / journal entries), as opposed
  // to just the live ops snapshot or nothing? Gates the unsupported-recall strip below: with no
  // conversational memory, any "you mentioned earlier…" claim is invented by construction.
  let hasConvoMemory = false;
  // The CONVERSATIONAL memory ONLY (prior turns), with the ops snapshot EXCLUDED — used to verify a
  // recalled number was actually stated by the worker (a snapshot KPI like MTBF 9.8h must NOT count
  // as "you told me the downtime was 9.8"). See stripFalsePremiseAffirmation.
  let convoMemory = "";
  let snapText = "";   // the live ops-snapshot block ONLY — its KPIs are current values, never "what you told me"
  if (!rawMemory) {
    memoryBlock = "(no prior journal entries yet)";
  } else if (rawMemory.startsWith(SNAP_HEAD)) {
    const sep = rawMemory.indexOf("\n\n");
    if (sep === -1) {
      memoryBlock = rawMemory;                                  // snapshot only, no conversational memory
      snapText = rawMemory;
    } else {
      const snap = rawMemory.slice(0, sep);
      const rest = rawMemory.slice(sep + 2);
      memoryBlock = snap + "\n\n" + (rest ? redactPII(rest) : "");
      hasConvoMemory = !!(rest && rest.trim());
      convoMemory = rest || "";
      snapText = snap;
    }
  } else {
    memoryBlock = redactPII(rawMemory);
    hasConvoMemory = true;
    convoMemory = rawMemory;
  }

  const userBlock = [
    `Detected language: ${langName} (code: ${lang})`,
    `Memory block:`,
    memoryBlock,
    `---`,
    `Latest voice entry:`,
    message,
  ].join("\n");

  // Sticky session (set by ai-gateway): keep this companion thread on one model.
  const sessionKey = typeof (body as { session_key?: unknown }).session_key === "string"
    ? (body as { session_key?: string }).session_key
    : undefined;
  // The free-prose path (chat/advice turns, and the strictly-additive G3 fallback).
  const proseOpts = {
    systemPrompt, temperature: 0.55, maxTokens: MAX_TOKENS_OUT,
    jsonMode: false as const, sessionKey,
  };

  // Phase G3 — typed fact-sheet + slot-fill (Grounding Doctrine §2). On a
  // value-seeking DATA-READ turn ("how many alerts?", "what's my OEE?") the
  // model is handed a typed fact sheet parsed from the live snapshot and asked
  // to write prose with {{FACT:id}} placeholders, emitting NO digits; CODE
  // inserts the real values, so a load-bearing number cannot be authored (closes
  // G1's coincidental-match residual). STRICTLY ADDITIVE: no facts / not value-
  // seeking / malformed JSON / unknown id / leftover placeholder all fall back to
  // the free-prose path below, and whatever G3 emits still passes through the
  // same strip + G1 cascade (the universal numeric floor + the independent
  // "numbers ⊆ grounded" assertion, since fact values came from `snapText`).
  const factSheet  = buildOpsFactSheet(snapText);
  const g3Eligible = isDataReadTurn(message, factSheet);

  const t0 = Date.now();
  try {
    let answer: string;
    if (g3Eligible) {
      const g3Block = userBlock + "\n\n" + buildFactSheetPromptBlock(factSheet);
      const g3Raw = await callAI(g3Block, {
        systemPrompt, temperature: 0.4, maxTokens: MAX_TOKENS_OUT,
        jsonMode: true, sessionKey,
      });
      const parsed = parseG3Json(g3Raw);
      const rendered = parsed ? renderFactSheet(parsed, factSheet) : null;
      if (rendered?.ok) {
        answer = rendered.prose;
        log.info(null, `[voice-journal] G3 slot-fill applied (${factSheet.facts.length} facts available)`);
      } else {
        // strictly-additive fallback: identical to the non-G3 free-prose path.
        log.info(null, `[voice-journal] G3 fell back to free prose (${parsed ? rendered?.reason : "unparseable-json"})`);
        answer = await callAI(userBlock, proseOpts);
      }
    } else {
      answer = await callAI(userBlock, proseOpts);
    }

    const trimmed = String(answer || "").trim();
    // Deterministic no-em-dash enforcement (OPT-PERSONA-04). The conversational persona rule bans em
    // dashes, but the LLM violates it probabilistically run-to-run; WAT says enforce a must-be-exact
    // output rule in CODE, not by re-asking the model. Em dash (U+2014) only -> ", " (a natural spoken
    // pause); en dash (U+2013) is left alone so numeric ranges like "3-6 months" survive.
    let clean = trimmed.replace(/\s*—\s*/g, ", ").replace(/,\s*,/g, ",").trim();
    // Unsupported false-recall strip (family-I tic): on a turn with no conversational memory,
    // drop any invented "you mentioned earlier you wanted…" sentence the model padded in. No-op
    // when real conversational memory is present (legitimate recall stays untouched).
    clean = stripUnsupportedRecall(clean, hasConvoMemory);
    // False-premise affirmation strip (family-C false-bait): when the worker falsely claims they
    // gave a value earlier, drop the hollow "you mentioned earlier about the X" rubber-stamp (recall
    // frame + no digit); keeps a real recalled value and the grounded remainder.
    clean = stripFalsePremiseAffirmation(clean, message, convoMemory, snapText);
    // Cross-slot recall strip (G-Accept family-K residual): when the worker asks to recall a SPECIFIC
    // named parameter, drop a recall-frame sentence that surfaces a value for a DIFFERENT parameter
    // (the "asked vibration, answered torque 85" misbinding) and abstain on the asked parameter.
    clean = stripCrossSlotRecall(clean, message);
    // Ungrounded event-tally strip (found by the held-out diverse run): drop a hive-specific
    // "two of the four breakdowns this week…" fabrication that G1 misses because its numbers are
    // worded; skipped when the logbook block is present (real failure data) and on generic advice.
    clean = stripUngroundedEventClaim(clean, userBlock);
    // Unregistered-asset claim strip (held-out dv-03): drop a sentence that affirms an event for a
    // tag not in the snapshot's registered list (keeps explicit denials).
    clean = stripUnregisteredAssetClaim(clean, userBlock);
    // Un-served-metric strip (held-out dv-10): the point-in-time snapshot has no targets/trends and
    // does not compute planned-vs-reactive; drop those fabricated claims (G3-class, missed by G1's
    // number-trace via coincidental match).
    clean = stripUnservedMetricClaims(clean);
    // Numeric-provenance gate (Phase G1): strip any sentence with a number that does
    // not TRACE to the grounded input (`userBlock` = ops-snapshot + memory + the worker's
    // own message), the benchmark table, or the tight date/duration/ordinal allowlist.
    // This catches the whole fabricated-number class, not just enumerated KPI names
    // (e.g. the live "...41% from a target of 80%" leak). If it guts the whole reply,
    // fall back to an honest pointer.
    const prov = gateNumericProvenance(clean, userBlock);
    if (prov.hit) {
      clean = prov.clean.length >= 15
        ? prov.clean
        : "I don't have your exact KPI figures on this voice surface. Check the Work Assistant for your live OEE, MTBF, and planned-vs-reactive ratio.";
    }
    const latency = Date.now() - t0;
    const hiveIdForLog =
      typeof body.hive_id === "string" && body.hive_id ? body.hive_id : null;

    if (_whWarmClient) {
      void logAICost(_whWarmClient, {
        fn:            "voice-journal-agent",
        hive_id:       hiveIdForLog,
        worker_name:   null,                // redacted upstream
        model:         MODEL_VERSION,
        provider:      "chain",
        prompt_tokens: estimateTokens(userBlock) + estimateTokens(systemPrompt),
        output_tokens: estimateTokens(trimmed),
        latency_ms:    latency,
        status:        trimmed ? "success" : "fallback",
      });
    }

    if (!trimmed) {
      return json(corsHeaders, 502, { error: "Empty answer from AI chain" });
    }

    return json(corsHeaders, 200, { answer: clean, lang } satisfies AgentResponse);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (_whWarmClient) {
      void logAICost(_whWarmClient, {
        fn:            "voice-journal-agent",
        hive_id:       typeof body.hive_id === "string" ? body.hive_id : null,
        worker_name:   null,
        model:         MODEL_VERSION,
        provider:      "chain",
        prompt_tokens: estimateTokens(userBlock) + estimateTokens(systemPrompt),
        latency_ms:    Date.now() - t0,
        status:        "failed",
      });
    }
    log.error(null, "voice-journal-agent error:", { detail: msg });
    return json(corsHeaders, 502, { error: `Journal agent failed: ${msg}` });
  }
});

function json(
  corsHeaders: Record<string, string>,
  status: number,
  body: unknown,
): Response {
  if (status >= 400 && body && typeof body === "object" && "error" in (body as Record<string, unknown>)) {
    const errorBody = body as { error: string };
    return new Response(JSON.stringify({ error: String(errorBody.error) }), {
      status,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}
