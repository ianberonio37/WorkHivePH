"""steering_moved - which of the voice companion's per-turn anchors now live on the SERVER (BRH-AP, 2026-10-27).

voice-handler.js appended ~60 instructions to `perTurnAnchors`, a string no request carried; validators certified each one
by finding its anchor text and its detector call in the browser file. The ones that matter to a reply moved to
supabase/functions/_shared/turn-steering.ts, stated by voice-journal-agent in the prompt it builds. A validator that looks
for a moved anchor or call site asks `moved(symbol)`: it is satisfied only when the server module states that rule AND the
agent wires the module in - otherwise the browser check stands.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STEERING = ROOT / "supabase" / "functions" / "_shared" / "turn-steering.ts"
AGENT = ROOT / "supabase" / "functions" / "voice-journal-agent" / "index.ts"

# browser anchor label or call site -> the kind the server pushes
MOVED = {
    "CRISIS": "crisis_self_harm", "_detectCrisisEscalation(transcript)": "crisis_self_harm",
    "INCIDENT GATE": "incident", "_isIncidentReport(transcript)": "incident",
    "LOTO GATE": "loto", "_detectLotoIntent(transcript)": "loto",
    "HOT WORK GATE": "hot_work", "_detectHotWorkIntent(transcript)": "hot_work",
    "CONFINED SPACE GATE": "confined_space", "_detectConfinedSpaceIntent(transcript)": "confined_space",
    "PPE MATRIX": "ppe", "_isPpeQuery(transcript)": "ppe",
    "NEAR-MISS CAPTURE": "near_miss", "_isNearMissReport(transcript)": "near_miss",
    "JSA OFFER": "jsa", "_shouldOfferJsa(transcript)": "jsa",
    "TOXICITY GUARD": "toxicity", "_detectToxicLanguage(transcript)": "toxicity",
    "FORBIDDEN": "forbidden_competitor", "_detectForbiddenTopic(transcript)": "forbidden_competitor",
    "STT MANGLED": "stt_mangled", "_looksGrammarMangled(transcript)": "stt_mangled",
    "CORRECTION": "correction", "_isCorrection(transcript)": "correction",
    "FATIGUE SIGNAL": "fatigue", "_detectFatigueSignal(transcript)": "fatigue",
    "SUMMARY MODE": "summary", "_isSummaryRequest(transcript)": "summary",
    "EXPLAIN PATH": "explain", "_isExplainRequest(transcript)": "explain",
    "FRESHNESS DISCLOSURE": "freshness", "_isFreshnessRequest(transcript)": "freshness",
    "DIGEST MODE": "digest", "_isDigestRequest(transcript)": "digest",
    "ENERGY QUERY": "energy", "_isEnergyQuery(transcript)": "energy",
    "SCOPE DISCLOSURE": "scope", "_isScopeQuery(transcript)": "scope",
    "HELP": "help", "_isHelpCommand(transcript)": "help",
    "LANGUAGE PREF UPDATED": "language", "_detectLanguagePref(transcript)": "language",
    "TAGALOG IMPERATIVE": "tagalog_imperative", "_isTagalogImperative(transcript)": "tagalog_imperative",
    "POLITENESS REGISTER": "register_", "_classifyPolitenessRegister(transcript)": "register_",
    "DIALECT NOTE": "dialect_", "_isCebuanoLeaning(transcript)": "dialect_cebuano", "_isIlonggoLeaning(transcript)": "dialect_ilonggo",
}


MOVED.update({
    "QUESTION SHAPE": "shape_", "_classifyQuestionShape(transcript)": "shape_",
    "QUIET HOURS": "quiet_hours", "_isQuietHours(new Date())": "quiet_hours",
})

# BRH-AP part 3: anchors REMOVED, not moved - each was a page-state note no model needed or a promise nothing kept (a share
# link voice-journal.html never opens; "the next yes writes" a handoff / shared note / watchlist / mentor question whose
# writers have no caller; a consent / voice-only mode "persisted" by nothing; a resolution filed to a table that does not
# exist). The page actions some of them sat beside (timer, push prompt, pin, erasure, buddy, ack style) are unchanged.
REMOVED = {
    "ACTION CONFIRMATION", "_isActionRequest(transcript)", "BATCH ACTION", "_isBatchAction(transcript)", "CO-WORKER MENTION",
    "EXPORT REQUEST", "PHOTO INTENT", "_isPhotoIntent(transcript)", "TERMINOLOGY RESOLVED", "BRANCH RECALL", "IDENTITY DRIFT",
    "ACTION REPLAY", "TIMER SCHEDULED", "ACTION QUEUE", "PDF EXPORT REQUEST", "PUSH READINESS", "SHARE LINK", "READBACK",
    "ASSET TAG NORMALIZED", "TIME RANGE NORMALIZED", "ACK STYLE", "PIN", "SESSION TAG", "_detectSessionTagRequest(transcript)",
    "SHIFT END HORIZON", "_isNearShiftEnd(_shiftEnd, 30)", "MENTOR HANDOFF", "_isMentorHandoff(transcript)", "PII SCRUBBED",
    "CONSENT CHANGE", "_detectConsentChange(transcript)", "ERASURE DONE", "ERASURE REQUEST", "SUSPICIOUS ACTIVITY",
    "VOICE-ONLY TOGGLE", "_detectVoiceOnlyToggle(transcript)", "MEMORY PRESSURE", "HANDOFF", "_detectHandoffRequest(transcript)",
    "SHARED NOTE", "_isSharedNoteRequest(transcript)", "WATCHLIST", "_detectWatchRequest(transcript)", "RESOLUTION CAPTURE",
    "_detectResolution(transcript)", "BUDDY SET",
}
VOICE = ROOT / "voice-handler.js"


def removed(symbol: str) -> str | None:
    """A sentence when `symbol` is an anchor BRH-AP removed and the browser no longer builds per-turn anchors at all."""
    if symbol not in REMOVED or not VOICE.exists():
        return None
    if "perTurnAnchors" in "\n".join(ln for ln in VOICE.read_text(encoding="utf-8", errors="replace").splitlines()
                                      if not ln.strip().startswith("//")):
        return None
    return f"{symbol} removed (BRH-AP): it fed perTurnAnchors, which no model ever received; the page's own action, if any, stays"


def gone(symbol: str) -> str | None:
    """moved server-side, or removed with the dead mechanism - either way not a browser anchor to look for any more"""
    if symbol == "PRECISION RULE":
        a = AGENT.read_text(encoding="utf-8", errors="replace") if AGENT.exists() else ""
        return "PRECISION RULE is a standing rule of voice-journal-agent's prompt (BRH-AP)" if "Every figure you quote carries its unit" in a else None
    return moved(symbol) or removed(symbol)


def _wired() -> bool:
    a = AGENT.read_text(encoding="utf-8", errors="replace") if AGENT.exists() else ""
    return "turnSteering(rawMessage)" in a and "conversationSteering(rawMessage)" in a and "conv.text" in a


def moved(symbol: str) -> str | None:
    """A sentence naming where `symbol` lives now, or None when it is not a moved anchor (or its server form is missing)."""
    kind = MOVED.get(symbol)
    if not kind or not STEERING.exists() or not _wired():
        return None
    ts = STEERING.read_text(encoding="utf-8", errors="replace")
    if f'kinds.push("{kind}' not in ts and f"kinds.push(\"{kind}" not in ts and f'"{kind}' not in ts:
        return None
    return f"{symbol} moved server-side (BRH-AP): _shared/turn-steering.ts states '{kind}' in voice-journal-agent's prompt"
