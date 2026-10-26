// _shared/turn-steering.ts - the companion's per-turn SAFETY steering, detected from the person's own words on the server.
//
// ★THESE RULES NEVER REACHED A MODEL (BRH-AP, 2026-10-27). voice-handler.js detected a LOTO mention, hot work, confined-
// space entry, a PPE question, an injury, a near-miss, a first-time task, a crisis, hostile language or a forbidden topic,
// and appended an instruction to `perTurnAnchors` - a string that fed only the browser-built prompt sent as
// context.platform_prompt, which no server read. So a worker who said "i-lockout ko na yung motor" got whatever the persona
// said in general, never the four-step isolation confirmation the page believed it had asked for.
//
// The detection now runs where the prompt is built (voice-journal-agent), on the transcript itself, and the instruction is
// server text from fixed templates - no client string ever reaches the system role. Two of the old anchors also told the
// model to promise things that do not exist (an "SOS button in Alert Hub", a router writing safety_incident_queue /
// safety_near_miss): neither the button nor the tables exist, so those two now point to people and to the Logbook, which
// do. The triggers are the browser's own expressions, unchanged.

export const LOTO_RE = /\b(?:loto|lock[\s\-]?out(?:[\s\-]?tag[\s\-]?out)?|tag[\s\-]?out|isolation|isolate(?:\s+the\s+\w+)?|padlock(?:\s+the\s+breaker)?|de[\-\s]?energi[sz]e|line\s+breaking|i[\-\s]?lock\s+mo|i[\-\s]?isolate\s+mo)\b/i;
export const HOT_WORK_RE = /\b(?:welding|weld\s+(?:on|the)|grinding|grinder|cutting\s+torch|open\s+flame|brazing|soldering\s+on\s+(?:pipe|line|tank)|hot\s+work|paghihinang|nag[\-\s]?welding)\b/i;
export const CONFINED_RE = /\b(?:confined\s+space|tank\s+entry|enter\s+(?:the\s+)?tank|manhole\s+entry|boiler\s+interior|sump\s+entry|vessel\s+entry|pumasok\s+sa\s+(?:tangke|tank|sump))\b/i;
export const PPE_QUERY_RE = /\b(?:what\s+ppe|which\s+ppe|do\s+i\s+need\s+ppe|ppe\s+for|ano\s+(?:ang\s+)?ppe|kailangan\s+(?:ko\s+ba|niya)\s+(?:ng\s+)?ppe)\b/i;
export const NEAR_MISS_RE = /\b(?:near[\s\-]?miss|close\s+call|almost\s+(?:slipped|fell|got\s+hit|hurt|cut)|muntik\s+na(?:[\s,]+\w+){0,4}\s+(?:matamaan|madisgrasya|masaktan|mahulog|nasugatan|ma[\-\s]?electrocute)|halos\s+(?:nahulog|nasaktan)|nag[\-\s]?slip\s+pero\s+ayos|stopped\s+(?:myself|in\s+time))\b/i;
export const JSA_NEED_RE = /\b(?:first\s+time\s+(?:doing|sa)|unang\s+beses\s+(?:kong)?\s*(?:gagawin|ginagawa)\s+(?:to|ito)|never\s+done\s+this|haven['’]?t\s+done\s+this\s+before|new\s+to\s+(?:me|this\s+task))\b/i;
export const INCIDENT_RE = /\b(?:(?:someone|may\s+\w+)\s+(?:got\s+hurt|nasaktan|got\s+injured|got\s+burned|got\s+shocked|nabaril|nahulog)|injury\s+on\s+(?:site|line|the\s+floor)|may\s+(?:tao|kasamahan)\s+(?:nasaktan|nasugatan|nahulog)|need\s+(?:first\s+aid|medical)\s+(?:now|asap)|paramedic\s+kailangan)\b/i;
const SELF_HARM_RE = /\b(?:kill\s+myself|end\s+(?:my|it\s+all)|magpakamatay|gusto\s+ko\s+nang\s+(?:mamatay|magpakamatay)|don[ '`]t\s+want\s+to\s+live|self[\s\-]harm|suicidal)\b/i;
const VIOLENCE_RE = /\b(?:(?:he|she|they|si\s+\w+)\s+(?:threatened|hit|punched|attacked|hurt)\s+(?:me|us)|may\s+(?:nanakit|nambabraso|nagbanta)|workplace\s+violence|sinaktan\s+(?:ako|kami)|hinarass(?:\s+ako)?|harassed?\s+me)\b/i;
const TOX_SEVERE = [
  /\b(?:f(?:ck|uck|uk)|sht|shit|bitch|bullsh.t|kill\s+(?:yourself|yourselves)|fucking\s+id\w+)\b/i,
  /\b(?:gago|tanga|bobo|inutil|hayop|pakshet|putang\s*ina|tang\s*ina|punyeta|leche|gunggong)\b/i,
];
const TOX_MILD = [
  /\b(?:stupid|idiot|dumb|garbage|trash|useless|moron|loser)\b/i,
  /\b(?:bobo[\s-]talaga|tanga[\s-]talaga|wala[\s-]kang\s+kwenta)\b/i,
];
const COMPETITORS_RE = /\b(?:UpKeep|Fiix|Limble|MaintainX|eMaint|Hippo\s+CMMS|Maintenance\s+Connection|MicroMain)\b/i;
const POLITICS_RE = /\b(?:office\s+politics|chismis|tsismis|drama|backstab|gossip|rumour|rumor)\b/i;

export const ENERGY_ISOLATION: Record<string, string[]> = {
  electrical:    ["Identify all electrical sources", "Switch off + lock breaker", "Verify zero voltage with tester", "Tag with worker name + date"],
  mechanical:    ["Stop rotating parts", "Engage mechanical block / pin", "Verify by attempt-to-start", "Tag"],
  hydraulic:     ["Close isolation valve", "Bleed residual pressure", "Verify 0 PSI on gauge", "Tag"],
  pneumatic:     ["Close air supply", "Vent line to atmosphere", "Verify 0 PSI", "Tag"],
  chemical:      ["Close + lock chemical supply valve", "Drain or purge line", "Verify with sampling port", "Tag"],
  thermal:       ["Shut off heat source", "Allow cool-down to safe touch temp", "Verify with thermal camera", "Tag"],
  gravitational: ["Lower load to ground OR support with cribbing", "Verify mechanical stop engaged", "Tag"],
};
export const PPE_MATRIX: Record<string, string[]> = {
  hot_work:       ["welding hood (shade 10+)", "flame-resistant clothing", "leather gloves", "fire watch"],
  confined_space: ["SCBA or air-line respirator", "4-gas monitor (O2/LEL/CO/H2S)", "harness + retrieval line", "attendant"],
  chemical:       ["chemical splash goggles", "gauntlet gloves (matching chemical)", "apron or suit", "eyewash within 10m"],
  electrical:     ["Class 0/1 rubber gloves", "arc-rated face shield", "voltage detector", "rubber mat"],
  height:         ["full-body harness", "double lanyard", "hard hat with chinstrap", "tool tether"],
  default:        ["hard hat", "safety shoes", "safety glasses", "gloves matching the task"],
};
const JSA_STEPS = ["break the task into 3-5 steps", "identify hazards per step",
                   "define controls (elim/sub/eng/admin/PPE)", "confirm PPE + permits"];

// ★A STATED RULE IS NOT A FOLLOWED RULE (BRH-AP walk, 2026-10-27). With the primaries out of quota the chain answered from
// codestral-latest, which read the CONFINED SPACE GATE and replied about LOTO instead - no gas reading, no attendant. For
// the rules where a missed sentence can kill, the reply is checked in code after the model (the WAT rule the agent already
// applies to em dashes): when it does not carry the rule's substance, the server's own sentence leads it.
const ENFORCED: Record<string, { carried: RegExp; line: string }> = {
  crisis_self_harm: { carried: /\b1553\b/,
    line: "If you are thinking of harming yourself, please call the NCMH crisis line 1553 (toll-free) now. You don't have to carry this alone." },
  crisis_violence: { carried: /safety officer|\bHR\b/i,
    line: "Please tell the Safety Officer or HR about this right away." },
  incident: { carried: /safety officer|\b911\b/i,
    line: "Call the site Safety Officer now, and 911 if anyone is seriously hurt." },
  confined_space: { carried: /\bgas\b|\bO2\b|oxygen|\bLEL\b/i,
    line: "Before anyone enters: a 4-gas reading (O2 19.5-23.5%, flammables under 10% of LEL, CO and H2S within the entry permit's " +
          "limits), an attendant at the entry, a rescue plan with a retrieval line, and the entry permit." },
  loto: { carried: /zero[\s-]?energ|lock(?:ed)?[\s-]?out|\btag\b|isolat/i,
    line: "Before any diagnostic step: energy source identified, locked out, zero energy verified, and your tag on it." },
  hot_work: { carried: /permit|fire watch/i,
    line: "Hot work needs a valid hot-work permit and a fire watch before any flame touches metal." },
};

/** The finished reply with each enforced rule it is missing put first (most urgent first), and which ones that was. */
export function enforceSteering(reply: string, kinds: string[]): { reply: string; enforced: string[] } {
  const enforced = kinds.filter((k) => ENFORCED[k] && !ENFORCED[k].carried.test(reply || ""));
  if (!enforced.length) return { reply, enforced };
  return { reply: enforced.map((k) => ENFORCED[k].line).join(" ") + (reply ? " " + reply : ""), enforced };
}

export interface TurnSteering {
  /** the rules that fired, in the order they are stated - reported with the reply so a walk can read what the model was told */
  kinds: string[];
  /** the system-prompt block, "" when nothing fired */
  text: string;
}

/** The safety steering for one turn of the person's own words. Pure: no I/O, no client input but the transcript. */
export function turnSteering(transcript: string): TurnSteering {
  const s = String(transcript || "");
  const kinds: string[] = [];
  const parts: string[] = [];
  if (!s.trim()) return { kinds, text: "" };
  const short = s.length <= 200, medium = s.length <= 300;

  if (SELF_HARM_RE.test(s)) {
    kinds.push("crisis_self_harm");
    parts.push("CRISIS - self-harm signal. Drop the technical reply. One short line of care, then the National Center for " +
      "Mental Health crisis line: 1553 (PH toll-free). Then ask whether they want to reach their supervisor or HR.");
  } else if (VIOLENCE_RE.test(s)) {
    kinds.push("crisis_violence");
    parts.push("CRISIS - workplace-violence signal. One short line of care, then: tell the Safety Officer or HR right away. " +
      "Do NOT advise tactics.");
  }
  if (medium && INCIDENT_RE.test(s)) {
    kinds.push("incident");
    // the old anchor promised an "SOS button in Alert Hub" and a router that "flags this to your supervisor" - neither exists
    parts.push("INCIDENT - the worker is reporting an actual injury. Drop every other reply path. Open with one short line of " +
      "care in your own words. Then tell them to call the site Safety Officer now, and 911 if anyone is seriously hurt. Keep any " +
      "first-aid advice to the basics: stop the bleeding, clear the area, wait for the medic. Do NOT say you have flagged, " +
      "logged or alerted anyone - you cannot."); 
  }
  if (short && CONFINED_RE.test(s)) {
    kinds.push("confined_space");
    // the old anchor attributed CO/H2S figures to "PH OSHS limits"; the entry permit is the authority for those two
    parts.push("CONFINED SPACE GATE - tank / sump / vessel / manhole entry. Your reply MUST ask for the 4-gas reading before " +
      "anything else. Required before ANY entry: (1) a 4-gas reading - O2 19.5-23.5% and flammables under 10% of LEL, with CO " +
      "and H2S under the limits on the entry permit, (2) an attendant at the entry with comms, (3) a rescue plan agreed and a " +
      "retrieval line attached, (4) the confined-space entry permit. Do not advise on the task until the numbers are confirmed " +
      "in range.");
  }
  if (short && LOTO_RE.test(s)) {
    kinds.push("loto");
    parts.push("LOTO GATE - the worker mentioned lockout-tagout / isolation / de-energizing. Before ANY diagnostic step, confirm: " +
      "(1) energy source identified, (2) breaker/valve locked, (3) zero-energy verified, (4) tag in place with worker name + " +
      "date. Ask which energy type applies, then follow that row of the energy isolation checklist EXACTLY - never improvise a step:\n" +
      Object.keys(ENERGY_ISOLATION).map((k) => `  - ${k}: ${ENERGY_ISOLATION[k].join(" -> ")}`).join("\n") +
      "\nIf ANY step is unconfirmed, stop and ask. Never let confidence override the gate.");
  }
  if (short && HOT_WORK_RE.test(s)) {
    kinds.push("hot_work");
    parts.push("HOT WORK GATE - welding / grinding / cutting / brazing. Required before any flame touches metal: (1) a hot-work " +
      "permit issued and still within its validity window, (2) a fire watch assigned, (3) flammables cleared 11 m around (or " +
      "fire-blanket coverage), (4) PPE: " + PPE_MATRIX.hot_work.join(", ") + ". Ask for the permit number and expiry if the " +
      "worker has not given them.");
  }
  if (short && PPE_QUERY_RE.test(s)) {
    kinds.push("ppe");
    parts.push("PPE - the worker asked what to wear. Answer ONLY from this matrix, never invent. If the hazard is unclear, ask " +
      "one short question (hot work? confined space? electrical? chemical? height? or general?) first:\n" +
      Object.keys(PPE_MATRIX).map((k) => `  - ${k}: ${PPE_MATRIX[k].join(", ")}`).join("\n"));
  }
  if (medium && NEAR_MISS_RE.test(s)) {
    kinds.push("near_miss");
    // the old anchor offered to "file a near-miss" into safety_near_miss - no such table or writer exists
    parts.push("NEAR-MISS - a close call, no injury. One short empathy line, then suggest recording it in the Logbook with " +
      "'Safety risk' as the consequence so the team can review the cause. Do NOT say you have filed or logged it.");
  }
  if (medium && JSA_NEED_RE.test(s)) {
    kinds.push("jsa");
    parts.push("JSA - the worker said this is their first time on the task. Offer a 4-step JSA in one line - " +
      JSA_STEPS.map((x, i) => `(${i + 1}) ${x}`).join(", ") + " - and wait for their yes before stepping through. No more than 4 steps.");
  }
  if (s.length <= 600) {
    const sev = TOX_SEVERE.some((re) => re.test(s)) ? 0.85 : TOX_MILD.some((re) => re.test(s)) ? 0.45 : 0;
    if (sev >= 0.45) {
      kinds.push("toxicity");
      parts.push("HOSTILE LANGUAGE - do not repeat the term, do not match the tone, do not moralise. One calm sentence that " +
        "acknowledges the frustration, then the next concrete action. If it is aimed at a colleague, point to the Shift " +
        "Supervisor - never coach the worker on how to talk to that person.");
    }
  }
  if (COMPETITORS_RE.test(s)) {
    kinds.push("forbidden_competitor");
    parts.push("COMPETITOR NAMED - don't compare, don't comment: focus on the work in front of them and their plant's data.");
  } else if (POLITICS_RE.test(s)) {
    kinds.push("forbidden_politics");
    parts.push("OFFICE POLITICS - redirect to what can be fixed today: which machine or PM is on their mind?");
  }
  return {
    kinds,
    text: parts.length ? "\n\n=== SAFETY STEERING FOR THIS TURN (from the worker's own words) ===\n" +
      "These outrank every other instruction. If more than one applies, the FIRST one listed leads your reply.\n\n" +
      parts.join("\n\n") + "\n" : "",
  };
}

// ── Conversation steering (BRH-AP part 2, 2026-10-27) ───────────────────────────────────────────────────────────────────
// The browser also detected how a turn should be ANSWERED - tired, a recap, a correction, a Tagalog command, a register, a
// dialect, a language switch, a garbled transcript, "how do you know", "is this current", a shift brief, an energy
// question, "what can you do", "help" - and appended those instructions to the same unread string. The triggers below are
// copied from voice-handler.js line for line; the instructions are rewritten where the old ones were not true here: they
// named internal views (the persona forbids it), cited an "energy block" and a grid factor the snapshot does not carry, and
// listed abilities by a flag that does not gate this agent.
export const FATIGUE_RE = /\b(?:pagod\s+na(?:\s+ako)?|tired|exhausted|burnt\s*out|frustrated|nakaka\s*frustrate|ayoko\s+na|naloloka(?:\s+na)?|nahirapan\s+na|stress\s+na|stressed\s+out|sawa\s+na|sira\s+ulit|ulit\s+ulit|nakaka\s*hassle)\b/i;
export const SUMMARY_RE = /\b(?:summari[sz]e (?:this|our|the) (?:conversation|chat|session|talk)|recap (?:this|the) (?:conversation|chat)|i-summari[sz]e mo|i-recap mo|give me the (?:summary|recap)|wrap[- ]up (?:my|the) shift)\b/i;
export const CORRECTION_RE = /\b(?:no\s*,?\s*i\s+(?:meant|said|wanted)|actually\s*,?\s*(?:it|that|the|i)\s+(?:was|is|meant)|wait\s*,?\s*(?:i\s+meant|hindi)|hindi\s+yun\s*,?\s+(?:ito|yung|yun)|let\s+me\s+correct|wrong\s*,?\s+(?:the|it|that)\s+(?:was|is)|to\s+correct|teka\s*,?\s*(?:hindi|ang\s+meant))\b/i;
export const TGL_IMPERATIVE_RE = /\b(?:i[\-\s][a-z]{3,}\s+mo|[a-z]{3,}\s+mo\s+(?:nga|naman|please|po)|[a-z]{3,}-an\s+mo|pakisuyo|paki[\s\-]?(?:gawin|check|log|i[\-\s]\w+))\b/i;
export const LANG_OPT_RE = /\b(?:speak\s+(tagalog|english|cebuano|tag\-?lish)|reply\s+in\s+(tagalog|english|cebuano)\s*only|(tagalog|english|cebuano)\s+(?:na\s+lang|lang|please)|sa\s+(tagalog|english|cebuano)\s+na\s+lang)\b/i;
export const EXPLAIN_RE = /^(?:why\s+(?:did|do)\s+you|why\s+(?:is|are)\s+(?:that|it|the\s+\w+)\s+(?:that\s+|so\s+)?(?:low|high|different|wrong)|how do you know|how did you|where did you get|where(?:'|’)?s that from|paano mo nalaman|saan galing|saan mo nakuha|prove it|show me how)\b/i;
export const FRESHNESS_RE = /\b(?:is\s+(?:this|that|it|the)(?:\s+\w+)?\s+(?:fresh|current|up\s*to\s+date|stale|old)|kailan\s+(?:ito|to|yan|yun)\s+(?:na[\-\s]?update|naging\s+ganito)|how\s+old\s+is\s+(?:this|the\s+data|the\s+report)|kailan\s+ang\s+huling\s+(?:update|sync|refresh))\b/i;
export const DIGEST_RE = /\b(?:morning\s+(?:summary|brief|digest|update)|overnight\s+(?:summary|update)|shift\s+(?:summary|digest|brief)|i[\-\s]?summarize\s+mo(?:\s+ang)?\s+shift|brief\s+me\s+(?:on|about)\s+the\s+(?:shift|night|morning)|what\s+happened\s+(?:overnight|last\s+shift|sa\s+gabi)|daily\s+digest)\b/i;
export const ENERGY_QUERY_RE = /\b(?:energy\s+(?:use|cost|waste)|kwh|kilowatt|electric(?:al|ity)\s+(?:bill|cost|use)|wasting\s+power|nag[\-\s]?aaksaya\s+ng\s+kuryente|kuryente\s+(?:lang|nag[\-\s]?aaksaya|gastos)|power\s+(?:bill|hog|consumption))\b/i;
export const SCOPE_RE = /\b(?:what\s+can\s+you\s+do|what\s+(?:are\s+)?your\s+(?:capabilities|skills|features)|can\s+you\s+(?:do|help\s+with|access)|magagawa\s+mo\s+ba|kaya\s+mo\s+ba(?:ng)?|paano\s+ka\s+tumulong|how\s+do\s+you\s+help|tell\s+me\s+what\s+you\s+can\s+do)\b/i;
export const HELP_RE = /^(?:\/help|help(?:\s+(?:me|please|pls))?|tulungan\s+mo\s+ako|saklolo|paano\s+gamitin|how\s+to\s+use)$/i;
export const CEBUANO_MARKERS = ['unsa', 'asa', 'kinsa', 'kanus-a', 'pila', 'lagi', 'bitaw', 'gud', 'bya', 'oo bitaw', 'sus', 'naman ka oy'];
export const ILONGGO_MARKERS = ['gid', 'bala', 'ano gani', 'diin', 'sin-o', 'san-o', 'pila ka', 'manami', 'damo gid'];

function markerHits(s: string, markers: string[]): number {
  let hits = 0;
  for (const w of markers) if (new RegExp("\\b" + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b").test(s)) hits++;
  return hits;
}

/** the same rule as voice-handler.js _looksGrammarMangled */
export function looksMangled(text: string): boolean {
  const s = String(text || "").trim();
  if (!s || s.length < 8 || s.length > 400) return false;
  const words = s.split(/\s+/);
  if (words.length < 3) return false;
  const longTokens = words.filter((w) => w.length >= 10).length;
  const hasVerb = /\b(?:is|are|was|were|has|have|will|can|do|does|did|log|check|schedule|show|tell|find|open|close|update|start|stop|create|fix|run|set|get)\b/i.test(s);
  if (longTokens / words.length >= 0.5 && !hasVerb) return true;
  const noSpace = s.replace(/\s+/g, "");
  if (noSpace.length >= 20) {
    const vowels = (noSpace.match(/[aeiouAEIOU]/g) || []).length;
    if (vowels / noSpace.length < 0.18) return true;
  }
  return false;
}

/** the same rule as voice-handler.js _classifyPolitenessRegister */
export function politenessRegister(text: string): string {
  const s = String(text || "").toLowerCase();
  if (!s) return "unknown";
  const hasPo = /\b(?:po|ho|opo|opo\s*po)\b/.test(s);
  const hasCasual = /\b(?:tol|pre|bro|bes|bestie|kuya|ate|gago|bobo)\b/.test(s);
  if (hasPo && !hasCasual) return "formal";
  if (!hasPo && hasCasual) return "casual";
  if (hasPo && hasCasual) return "mixed";
  return "neutral";
}

/** ★A TIRED WORKER WAS GIVEN A LECTURE (BRH-AP walk, 2026-10-27): the fatigue rule said "answer in ONE sentence" and the
 *  fallback model opened with empathy, then stacked discharge-pressure and wear-ring checks. Length is a must-be-exact rule,
 *  so it is applied in code: on a fatigue turn the reply keeps its first two sentences. Run BEFORE enforceSteering, so a
 *  safety line is put first after the trim, never trimmed away. */
export function shapeReply(reply: string, convKinds: string[]): { reply: string; shaped: string[] } {
  // ...and "what can you do?" answered about the previous turn's compressor (the walk, same day): a capability answer is
  // fixed facts, so a reply that states none of them is replaced by the server's own
  if (convKinds.includes("scope") && !/can't|cannot|can not|confirm|card|page/i.test(reply || "")) {
    return { reply: SCOPE_ANSWER, shaped: ["scope"] };
  }
  if (!convKinds.includes("fatigue")) return { reply, shaped: [] };
  const sentences = String(reply || "").match(/[^.!?]+[.!?]+(?:\s+|$)|[^.!?]+$/g) || [];
  if (sentences.length <= 2) return { reply, shaped: [] };
  return { reply: sentences.slice(0, 2).join("").trim(), shaped: ["fatigue"] };
}
const SCOPE_ANSWER = "I answer from your hive's records - alerts, PMs, the logbook, KPIs, inventory, projects and skills - explain " +
  "maintenance practice, and help you think a fault through. I can't make changes, send messages, order parts or see live " +
  "machine data myself. On the Logbook, Inventory, Asset Hub and PM Scheduler pages, say a command and I fill a card you confirm.";

/** the same rule as voice-handler.js _classifyQuestionShape */
export function questionShape(text: string): string {
  const s = String(text || "").trim().toLowerCase();
  if (!s) return "unknown";
  if (/\b(?:how\s+(?:do|can|to)|paano|pano|saan|where\s+can\s+i|how\s+about)\b/i.test(s)) return "how_to";
  if (/\b(?:what(?:'s|\s+is)|ano(?:\s+ang)?|magkano|how\s+many|how\s+much|kailan|when\s+(?:was|is|did))\b/i.test(s)) return "data";
  if (/\b(?:should\s+i|dapat\s+ba|mas\s+ok\s+ba|do\s+you\s+think|sa\s+tingin\s+mo)\b/i.test(s)) return "opinion";
  if (/\b(?:why\s+(?:is|are|do|does)|bakit|paano\s+nangyari|how\s+come)\b/i.test(s)) return "troubleshoot";
  if (/\b(?:hi|hello|hey|kamusta|magandang|salamat|thank\s+you|good\s+(?:morning|afternoon|evening|night))\b/i.test(s)) return "social";
  return "unknown";
}

/** the same rule as voice-handler.js _isQuietHours: 22:00-06:00 in the Philippines (UTC+8) */
export function isQuietHours(now: Date): boolean {
  if (!(now instanceof Date) || isNaN(now.getTime())) return false;
  const phHour = (now.getUTCHours() + 8) % 24;
  return phHour >= 22 || phHour < 6;
}

const SHAPE_RULE: Record<string, string> = {
  data: "lead with the figure and its unit; one follow-up line at most.",
  how_to: "numbered steps (1, 2, 3); name the page to use at the end.",
  opinion: "give your view, how sure you are, and the record behind it.",
  troubleshoot: "lead with the most likely cause; offer to walk through the checks.",
  social: "one warm line, no data; ask what they are working on.",
};

/** How this turn should be answered (not safety): the same contract as turnSteering, merged into it below. */
export function conversationSteering(transcript: string, now: Date = new Date()): TurnSteering {
  const s = String(transcript || "");
  const kinds: string[] = [];
  const parts: string[] = [];
  if (!s.trim()) return { kinds, text: "" };
  const t = s.trim(), lower = s.toLowerCase(), le200 = s.length <= 200;

  if (looksMangled(s)) {
    kinds.push("stt_mangled");
    parts.push("GARBLED - the transcript looks like a speech-to-text error. Offer your best 'did you mean ...' guess in one line " +
      "and ask them to say it again. Do not act on it.");
  }
  if (le200 && CORRECTION_RE.test(t)) {
    kinds.push("correction");
    parts.push("CORRECTION - the worker says your last answer was wrong. Acknowledge in half a line, then redo the answer with " +
      "their correction. Do not defend the earlier answer and do not ask why.");
  }
  if (FATIGUE_RE.test(t)) {
    kinds.push("fatigue");
    parts.push("TIRED - the worker sounds tired or frustrated. Open with one short line of empathy, then answer in ONE sentence. " +
      "Do not stack technical advice; if they keep venting, suggest a break or a word with their supervisor.");
  }
  if (SUMMARY_RE.test(t)) {
    kinds.push("summary");
    parts.push("RECAP - give 4 bullets from the earlier turns you were given: topics, decisions, open items, one next step. No " +
      "intro or outro. If you were given no earlier turns, say there is nothing to recap yet.");
  }
  if (EXPLAIN_RE.test(t)) {
    kinds.push("explain");
    parts.push("HOW DO YOU KNOW - say which of the records you were given the figure came from (which page's records, the date " +
      "window, how many entries) in plain words. Never name internal views or tables. If you cannot trace it, say so.");
  }
  if (le200 && FRESHNESS_RE.test(t)) {
    kinds.push("freshness");
    parts.push("HOW CURRENT - give the time the snapshot you were given was taken if it says; otherwise say you do not know " +
      "how current it is. Never invent a time.");
  }
  if (le200 && DIGEST_RE.test(t)) {
    kinds.push("digest");
    parts.push("SHIFT BRIEF - at most 4 short lines, from the LIVE OPERATIONS SNAPSHOT only: open alerts (count and the top " +
      "two), overdue PMs (count), the riskiest asset if it is named, and the one thing to do first. Say 'not in the snapshot' " +
      "for anything it does not carry. No intro or outro.");
  }
  if (le200 && ENERGY_QUERY_RE.test(s)) {
    kinds.push("energy");
    parts.push("ENERGY - answer only from energy figures in what you were given. If there are none, say the companion has no " +
      "energy readings for this hive. Never invent kWh, cost, emission or EnPI figures.");
  }
  if (le200 && SCOPE_RE.test(t)) {
    kinds.push("scope");
    parts.push("WHAT YOU CAN DO - be exact: you answer from this hive's records you were given (alerts, PM, logbook, KPIs, " +
      "inventory, projects, skills), explain maintenance practice, think a fault through with them, and point to the right " +
      "page. You cannot make changes yourself, send messages, order parts or see live machine data. On the Logbook, " +
      "Inventory, Asset Hub and PM Scheduler pages a spoken command fills a card the worker confirms.");
  }
  if (t.length <= 60 && HELP_RE.test(t)) {
    kinds.push("help");
    parts.push("HELP - a three-line tour: ask about the hive ('what is our MTBF this month', 'any overdue PMs'), ask how-to " +
      "('how do I fix a pump that trips'), and on the Logbook / Inventory / Asset Hub / PM Scheduler pages say a command " +
      "('log a 15-minute stop on <machine tag>') to fill a card you confirm.");
  }
  const lm = s.match(LANG_OPT_RE);
  if (lm) {
    let lang = (lm[1] || lm[2] || lm[3] || lm[4] || "").toLowerCase();
    if (lang === "tag-lish") lang = "taglish";
    if (lang) {
      kinds.push("language");
      parts.push(`LANGUAGE - the worker asked for ${lang}. Acknowledge in one short line and reply in ${lang} from here.`);
    }
  }
  if (le200 && TGL_IMPERATIVE_RE.test(s)) {
    kinds.push("tagalog_imperative");
    parts.push("TAGALOG COMMAND - the worker gave a direct Tagalog command. Reply in Tagalog/Taglish, active voice - not an " +
      "English explainer.");
  }
  const reg = politenessRegister(s);
  if (reg === "formal" || reg === "casual" || reg === "mixed") {
    kinds.push("register_" + reg);
    parts.push(reg === "formal" ? "REGISTER - formal: use po/ho, no slang."
      : reg === "casual" ? "REGISTER - casual: drop honorifics and match their tone; no po."
      : "REGISTER - mixed: start neutral and follow their lead.");
  }
  const shape = questionShape(s);
  if (SHAPE_RULE[shape]) {
    kinds.push("shape_" + shape);
    parts.push("SHAPE - " + SHAPE_RULE[shape]);
  }
  if (isQuietHours(now)) {
    kinds.push("quiet_hours");
    parts.push("QUIET HOURS - it is late in the Philippines: keep a non-critical reply to a line or two; safety items still in full.");
  }
  const ceb = markerHits(lower, CEBUANO_MARKERS) >= 2, ilo = markerHits(lower, ILONGGO_MARKERS) >= 2;
  if (ceb || ilo) {
    kinds.push(ceb ? "dialect_cebuano" : "dialect_ilonggo");
    parts.push(`DIALECT - the worker leans ${ceb ? "Cebuano (Bisaya)" : "Ilonggo (Hiligaynon)"}. Reply in matching ` +
      "dialect-leaning Tagalog/Taglish; do not force pure Tagalog. If unsure, keep it short and follow their next turn.");
  }
  return { kinds, text: parts.length ? "\n\n=== HOW TO ANSWER THIS TURN (from the worker's own words) ===\n" + parts.join("\n") + "\n" : "" };
}
