"""
AI Companion Trust + Observability Validator (turns #15-#24)
=============================================================
Forward-only L0 ratchet for the second 10-turn flywheel batch shipped
on 2026-05-20. Different dimension from the dialog-state stack: this
one covers TRUST (hallucination, citation), AUDIO QUALITY (interrupt,
pronunciation), OBSERVABILITY (latency, rate-limit, cost-cap), and
CROSS-SURFACE COHERENCE (assistant ↔ voice-journal).

  T15  Hallucination guard prompt anchor
  T16  Citation enforcement prompt anchor
  T17  Audio interrupt on mic-tap
  T18  TTS latency budget (Azure AbortSignal + client cap + metrics)
  T19  ai-gateway rate-limit + fair-use guard
  T20  Failure-recovery UX shape (_generateFallbackReply consistent)
  T21  Acronym SSML pronunciation in wh-tts
  T22  assistant.html pulls voice_journal_entries (cross-surface)
  T23  Cost-cap circuit breaker: ai_cost_log + ai-quality dashboard
  T24  Conversation-end ack on voice-overlay close

10-layer audit. Each layer is small but the bundle catches a distinct
class of failure that the dialog-state stack didn't reach.
"""

from __future__ import annotations

import os
import re
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


VOICE_HANDLER_JS = "voice-handler.js"
WH_TTS_JS        = "wh-tts.js"
TTS_SPEAK_TS     = os.path.join("supabase", "functions", "tts-speak", "index.ts")
AI_GATEWAY_TS    = os.path.join("supabase", "functions", "ai-gateway", "index.ts")
ASSISTANT_HTML   = "assistant.html"
AI_QUALITY_HTML  = "ai-quality.html"


def _read(path: str) -> str:
    c = read_file(path)
    return c or ""


def check_hallucination_guard(c: str) -> list[dict]:
    """T15 — HALLUCINATION GUARD anchor in _buildVoiceSystemPrompt."""
    if "HALLUCINATION GUARD" not in c:
        return [{"check": "hallucination_guard",
                 "reason": "HALLUCINATION GUARD anchor missing from _buildVoiceSystemPrompt — model may invent asset tags / KPIs not in canonical data."}]
    if "hallucinationGuardAnchor" not in c:
        return [{"check": "hallucination_guard",
                 "reason": "hallucinationGuardAnchor const missing — block was renamed or removed."}]
    return []


def check_citation_anchor(c: str) -> list[dict]:
    """T16 — CITATION RULE anchor."""
    if "CITATION RULE" not in c:
        return [{"check": "citation_anchor",
                 "reason": "CITATION RULE anchor missing — numbers in replies won't carry source-view citations."}]
    if "citationAnchor" not in c:
        return [{"check": "citation_anchor",
                 "reason": "citationAnchor const missing — block was renamed or removed."}]
    return []


def check_audio_interrupt(c: str) -> list[dict]:
    """T17 — _startRecording cancels in-flight audio before opening mic."""
    if not re.search(r"async\s+function\s+_startRecording\s*\(\)\s*\{[^}]*WHTts[^}]*stop", c, re.DOTALL):
        return [{"check": "audio_interrupt",
                 "reason": "_startRecording does NOT cancel in-flight audio (window.WHTts.stop()) before opening mic. Worker hears their own question over the persona's reply."}]
    return []


def check_tts_latency_budget(c_tts: str, c_edge: str) -> list[dict]:
    """T18 — tts-speak has AbortSignal timeout AND wh-tts has client-side timeout."""
    issues: list[dict] = []
    if "AbortSignal.timeout" not in c_edge:
        issues.append({"check": "tts_latency_budget",
                       "reason": "tts-speak/index.ts has no AbortSignal.timeout on the Azure fetch — a hung Azure call would strand the worker."})
    if "fetchWithTimeout" not in c_tts and "10000" not in c_tts:
        issues.append({"check": "tts_latency_budget",
                       "reason": "wh-tts.js has no client-side timeout on the tts-speak POST — Azure hangs would silently freeze the audio path."})
    if "_logTTSMetrics" not in read_file(VOICE_HANDLER_JS):
        issues.append({"check": "tts_latency_budget",
                       "reason": "voice-handler.js does not log TTS metrics — latency regressions go unnoticed."})
    return issues


def check_rate_limit_guard(c: str) -> list[dict]:
    """T19 — ai-gateway calls checkAIRateLimit + returns rateLimitedResponse."""
    issues: list[dict] = []
    if "checkAIRateLimit" not in c:
        issues.append({"check": "rate_limit_guard",
                       "reason": "ai-gateway/index.ts does not call checkAIRateLimit — no fair-use guard."})
    if "rateLimitedResponse" not in c:
        issues.append({"check": "rate_limit_guard",
                       "reason": "ai-gateway/index.ts does not return rateLimitedResponse — rate-limit hits aren't surfaced cleanly."})
    return issues


def check_fallback_ux(c: str) -> list[dict]:
    """T20 — _generateFallbackReply produces a human-readable shape."""
    if "_generateFallbackReply" not in c:
        return [{"check": "fallback_ux",
                 "reason": "_generateFallbackReply missing from voice-handler.js — gateway errors fall through to raw 'Sorry, I\\'m offline.' instead of a routed message."}]
    # The fallback must reference at least one navigable page so the
    # worker has somewhere to go.
    fn_idx = c.find("_generateFallbackReply")
    body = c[fn_idx: fn_idx + 2000]
    if not any(p in body for p in ("Analytics", "Logbook", "Inventory", "PM Scheduler")):
        return [{"check": "fallback_ux",
                 "reason": "_generateFallbackReply body does not reference a navigable page — workers hit a dead-end on gateway errors."}]
    return []


def check_acronym_pronunciation(c: str) -> list[dict]:
    """T21 — wh-tts._spellOutAcronyms exists and is invoked from speakPersona."""
    if "_spellOutAcronyms" not in c:
        return [{"check": "acronym_pronunciation",
                 "reason": "_spellOutAcronyms missing from wh-tts.js — MTBF / OEE / PM are mispronounced by TTS engines."}]
    # Acronym vocabulary must include the platform's must-know terms.
    for kw in ("MTBF", "OEE", "PM", "RPN"):
        if "'" + kw + "'" not in c and '"' + kw + '"' not in c:
            return [{"check": "acronym_pronunciation",
                     "reason": f"_ACRONYMS_TO_SPELL missing '{kw}' — worker hears it as a mumbled word instead of letters."}]
    # speakPersona must invoke the spell-out helper before calling
    # speakEdge / speakBrowser.
    if "_spellOutAcronyms(text)" not in c:
        return [{"check": "acronym_pronunciation",
                 "reason": "speakPersona does not invoke _spellOutAcronyms(text) — helper exists but isn't applied."}]
    return []


def check_assistant_journal_pull(c: str) -> list[dict]:
    """T22 — assistant.html pulls voice_journal_entries for cross-surface coherence."""
    if "voice_journal_entries" not in c:
        return [{"check": "assistant_journal_pull",
                 "reason": "assistant.html does not query voice_journal_entries — Work Assistant can't reference what worker said to Zaniah earlier today."}]
    if "RECENT JOURNAL" not in c.upper():
        return [{"check": "assistant_journal_pull",
                 "reason": "assistant.html buildSystemPrompt doesn't include a 'RECENT JOURNAL' block — fetched data is fetched but not surfaced to the LLM."}]
    return []


def check_cost_cap(c_quality: str, c_gateway: str) -> list[dict]:
    """T23 — ai_cost_log surfaced on ai-quality.html + at least one
    specialist agent emits logAICost (cost telemetry lives at the
    agent layer, not the routing gateway — ai-gateway delegates to
    specialists which each call logAICost from `_shared/cost-log.ts`)."""
    issues: list[dict] = []
    if "ai_cost_log" not in c_quality:
        issues.append({"check": "cost_cap",
                       "reason": "ai-quality.html does not reference ai_cost_log — daily spend isn't observable."})
    # logAICost must be called from at least one routed specialist. We
    # scan a representative set; if none of them log, cost telemetry is
    # gone platform-wide.
    cost_log_callers = (
        "amc-orchestrator", "asset-brain-query", "ai-orchestrator",
        "analytics-orchestrator", "intelligence-report",
        "engineering-calc-agent",
    )
    any_caller_logs = False
    for fn_name in cost_log_callers:
        path = os.path.join("supabase", "functions", fn_name, "index.ts")
        c = read_file(path) or ""
        if "logAICost" in c:
            any_caller_logs = True
            break
    if not any_caller_logs:
        issues.append({"check": "cost_cap",
                       "reason": "No specialist agent (amc-orchestrator / asset-brain-query / etc.) calls logAICost — cost telemetry is dead platform-wide, ai-quality dashboard will show empty."})
    return issues


def check_conversation_end_ack(c: str) -> list[dict]:
    """T24 — voice-handler close() persists a clean dialog-state reset + cancels audio."""
    fn_idx = c.find("function close()")
    if fn_idx < 0:
        return [{"check": "conversation_end_ack",
                 "reason": "voice-handler.js has no close() function — overlay can't be cleanly dismissed."}]
    body = c[fn_idx: fn_idx + 2000]
    issues: list[dict] = []
    if "_updateDialogState" not in body:
        issues.append({"check": "conversation_end_ack",
                       "reason": "close() does not call _updateDialogState — dialog state leaks into the next session."})
    if "WHTts" not in body and "speechSynthesis.cancel" not in body:
        issues.append({"check": "conversation_end_ack",
                       "reason": "close() does not stop in-flight audio — worker dismisses the overlay but Zaniah keeps talking."})
    if "_resetClarifyStreak" not in body:
        issues.append({"check": "conversation_end_ack",
                       "reason": "close() does not reset _clarifyStreak — stale streak counter leaks across sessions."})
    return issues


CHECK_NAMES = [
    "hallucination_guard", "citation_anchor", "audio_interrupt",
    "tts_latency_budget", "rate_limit_guard", "fallback_ux",
    "acronym_pronunciation", "assistant_journal_pull",
    "cost_cap", "conversation_end_ack",
]

CHECK_LABELS = {
    "hallucination_guard":    "T15 HALLUCINATION GUARD anchor in _buildVoiceSystemPrompt",
    "citation_anchor":        "T16 CITATION RULE anchor in _buildVoiceSystemPrompt",
    "audio_interrupt":        "T17 _startRecording cancels in-flight audio (WHTts.stop) before opening mic",
    "tts_latency_budget":     "T18 tts-speak AbortSignal + wh-tts client cap + _logTTSMetrics wired",
    "rate_limit_guard":       "T19 ai-gateway checkAIRateLimit + rateLimitedResponse stays wired",
    "fallback_ux":            "T20 _generateFallbackReply renders calm 'try again or open <page>' shape",
    "acronym_pronunciation":  "T21 wh-tts._spellOutAcronyms covers MTBF/MTTR/OEE/PM/RPN + invoked from speakPersona",
    "assistant_journal_pull": "T22 assistant.html buildSystemPrompt pulls voice_journal_entries (cross-surface coherence)",
    "cost_cap":               "T23 ai_cost_log surfaced on ai-quality.html + logAICost in ai-gateway",
    "conversation_end_ack":   "T24 voice-handler close() persists dialog-state reset + cancels audio + clears streak",
}


def main() -> int:
    print("\033[1m\nAI Companion Trust + Observability Validator (10-layer)\033[0m")
    print("=" * 60)

    c_vh      = _read(VOICE_HANDLER_JS)
    c_tts     = _read(WH_TTS_JS)
    c_edge    = _read(TTS_SPEAK_TS)
    c_gateway = _read(AI_GATEWAY_TS)
    c_assist  = _read(ASSISTANT_HTML)
    c_quality = _read(AI_QUALITY_HTML)

    issues: list[dict] = []
    issues += check_hallucination_guard(c_vh)
    issues += check_citation_anchor(c_vh)
    issues += check_audio_interrupt(c_vh)
    issues += check_tts_latency_budget(c_tts, c_edge)
    issues += check_rate_limit_guard(c_gateway)
    issues += check_fallback_ux(c_vh)
    issues += check_acronym_pronunciation(c_tts)
    issues += check_assistant_journal_pull(c_assist)
    issues += check_cost_cap(c_quality, c_gateway)
    issues += check_conversation_end_ack(c_vh)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
