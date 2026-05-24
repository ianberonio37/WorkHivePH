"""
Dialog Quality Extended Validator -- WorkHive AI Companion (turns #5-#14)
==========================================================================
Forward-only L0 ratchet covering the 10-turn dialog-quality flywheel
expansion shipped on 2026-05-20. Sister to:

  validate_dialog_affirmation_bypass.py  (turn #1)
  validate_dialog_followup_handlers.py   (turn #2)
  validate_dialog_continuity.py          (turn #3)
  validate_dialog_recovery_safety.py     (turn #4)

This one bundles turns #5 → #14 because each new bug class is small
(one helper + one call-site guard or one prompt anchor). Bundling keeps
the Mega Gate dimension count manageable while preserving the
forward-only-baseline-0 ratchet pattern.

10-layer audit:

  L1  Persona-switch utterance (turn #5)
      `_isPersonaSwitchUtterance` + `_PERSONA_SWITCH_RE` declared.
      Call-site handler persists the chosen persona to localStorage
      ("wh_voice_journal_persona") and clears dialog state.

  L2  Stale dialog-state guard (turn #6)
      `_isStaleDialogState(dialogState)` declared with explicit
      threshold comparison. Wired into the call site so the prior
      dialog state is replaced with null when stale.

  L3  Topic-interruption signal (turn #7)
      `_isTopicShiftSignal` + `_TOPIC_SHIFT_RE` declared. The
      affirmation bypass call site invokes `!_isTopicShiftSignal(...)`
      so explicit interruptions ("hold on", "wait", "teka") SUPPRESS
      the bypass and let normal classification run.

  L4  Thanks / acknowledgment handler (turn #8)
      `_isThanksReply` + `_THANKS_RE` declared. Call-site short-
      circuit renders a brief "walang anuman" beat, clears state,
      skips the LLM call.

  L5  Asset-context auto-priming (turn #9)
      `_maybePrimeAssetContext` declared, queries v_logbook_truth,
      injects asset_tag into context_slots when slot is empty AND
      the recent logbook entry is fresh (<60 min).

  L6  First-turn greeting (turn #10)
      `_isGreeting` + `_GREETING_RE` declared. Call-site short-circuit
      fires ONLY when there is no prior dialog state AND no session
      memory — so it never overrides a real conversation.

  L7  Code-switching anchor (turn #11)
      _buildVoiceSystemPrompt emits a LANGUAGE NOTE block instructing
      the LLM NOT to translate PH words to English mid-sentence.

  L8  Sensitive-topic redirect (turn #12)
      _buildVoiceSystemPrompt emits a SENSITIVE TOPIC REDIRECT block
      that routes HR / legal / financial / payroll questions to the
      supervisor instead of having the companion advise.

  L9  Worker-name personalization (turn #13)
      _buildVoiceSystemPrompt emits a "You are talking to <name>"
      anchor with a "kapatid" fallback when name is empty.

  L10 Repeat-that handler (turn #14)
      `_isRepeatRequest` + `_REPEAT_RE` declared. Call-site short-
      circuit replays the LAST assistant turn from session memory
      instead of running the LLM again.

Usage:  python validate_dialog_quality_extended.py

Skills consulted: ai-engineer (dialog-state machine + prompt design),
qa (multi-turn conversation edge cases), maintenance-expert (PH plant
vocabulary + noise environments), security (sensitive-topic boundary).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


VOICE_HANDLER_JS = "voice-handler.js"


def _read() -> str | None:
    return read_file(VOICE_HANDLER_JS)


def check_persona_switch(c: str) -> list[dict]:
    """L1 — Turn #5: persona-switch utterance handler."""
    if not c:
        return [{"check": "persona_switch", "reason": f"{VOICE_HANDLER_JS} not found"}]
    issues: list[dict] = []
    for sym in ("_isPersonaSwitchUtterance", "_PERSONA_SWITCH_RE"):
        if sym not in c:
            issues.append({"check": "persona_switch",
                           "reason": f"{sym} missing from voice-handler.js — workers saying 'switch to Hezekiah' will trip the clarification UI."})
    if "wh_voice_journal_persona" not in c:
        issues.append({"check": "persona_switch",
                       "reason": "Persona switch call site does not persist to localStorage('wh_voice_journal_persona') — choice will not propagate to other surfaces."})
    return issues


def check_stale_guard(c: str) -> list[dict]:
    """L2 — Turn #6: stale dialog-state guard."""
    if not c:
        return []
    if "_isStaleDialogState" not in c:
        return [{"check": "stale_guard",
                 "reason": "_isStaleDialogState missing — workers returning hours later get stale priorIntent applied to fresh questions."}]
    if not re.search(r"_STALE_THRESHOLD_MS\s*=", c):
        return [{"check": "stale_guard",
                 "reason": "_STALE_THRESHOLD_MS constant missing — threshold should be explicit, not magic-number."}]
    if "_isStaleDialogState(priorDialogStateRaw)" not in c:
        return [{"check": "stale_guard",
                 "reason": "Stale guard not wired at the call site — _isStaleDialogState(priorDialogStateRaw) must replace priorDialogState with null when stale."}]
    return []


def check_topic_interruption(c: str) -> list[dict]:
    """L3 — Turn #7: topic-shift signal suppresses affirmation bypass."""
    if not c:
        return []
    issues: list[dict] = []
    for sym in ("_isTopicShiftSignal", "_TOPIC_SHIFT_RE"):
        if sym not in c:
            issues.append({"check": "topic_interruption",
                           "reason": f"{sym} missing — 'hold on / wait / teka' interruptions get treated as affirmations."})
    # Affirmation bypass must include !_isTopicShiftSignal(transcript)
    if not re.search(r"_isFollowupAffirmation\s*\(\s*transcript\s*\)\s*&&\s*!_isTopicShiftSignal\s*\(\s*transcript\s*\)", c):
        issues.append({"check": "topic_interruption",
                       "reason": "Affirmation bypass does not check !_isTopicShiftSignal(transcript) — interruptions still get bypassed as continuations."})
    return issues


def check_thanks_handler(c: str) -> list[dict]:
    """L4 — Turn #8: thanks/ack short-circuit."""
    if not c:
        return []
    for sym in ("_isThanksReply", "_THANKS_RE"):
        if sym not in c:
            return [{"check": "thanks_handler",
                     "reason": f"{sym} missing — 'thanks / salamat' replies trigger an LLM call when they shouldn't."}]
    if "_isThanksReply(transcript)" not in c:
        return [{"check": "thanks_handler",
                 "reason": "Call site does not invoke _isThanksReply(transcript) — handler exists but is never called."}]
    return []


def check_asset_priming(c: str) -> list[dict]:
    """L5 — Turn #9: asset-context auto-priming."""
    if not c:
        return []
    if "_maybePrimeAssetContext" not in c:
        return [{"check": "asset_priming",
                 "reason": "_maybePrimeAssetContext missing — recent logbook asset_tag is not auto-injected into context_slots."}]
    if "v_logbook_truth" not in c:
        return [{"check": "asset_priming",
                 "reason": "_maybePrimeAssetContext doesn't query v_logbook_truth — must read the canonical recent-logbook view."}]
    if "_maybePrimeAssetContext(db" not in c:
        return [{"check": "asset_priming",
                 "reason": "Call site does not invoke _maybePrimeAssetContext — priming function exists but is never called."}]
    return []


def check_greeting(c: str) -> list[dict]:
    """L6 — Turn #10: first-turn greeting."""
    if not c:
        return []
    for sym in ("_isGreeting", "_GREETING_RE"):
        if sym not in c:
            return [{"check": "greeting",
                     "reason": f"{sym} missing — first-turn 'hi / kumusta' utterances run through full LLM grounding."}]
    if not re.search(r"!priorDialogState\s*&&\s*_sessionTurns\.length\s*===\s*0\s*&&\s*_isGreeting", c):
        return [{"check": "greeting",
                 "reason": "Greeting short-circuit does not require BOTH zero priorDialogState AND zero session turns. Without both, the greeting overrides real conversations."}]
    return []


def check_codeswitch_anchor(c: str) -> list[dict]:
    """L7 — Turn #11: code-switching anchor in prompt."""
    if not c:
        return []
    if "LANGUAGE NOTE" not in c:
        return [{"check": "codeswitch_anchor",
                 "reason": "LANGUAGE NOTE block missing from _buildVoiceSystemPrompt — LLM may translate PH words to English losing affective tone."}]
    if "codeSwitchAnchor" not in c:
        return [{"check": "codeswitch_anchor",
                 "reason": "codeSwitchAnchor const missing — block anchor was renamed or removed."}]
    return []


def check_sensitive_topic(c: str) -> list[dict]:
    """L8 — Turn #12: sensitive-topic redirect."""
    if not c:
        return []
    if "SENSITIVE TOPIC REDIRECT" not in c:
        return [{"check": "sensitive_topic",
                 "reason": "SENSITIVE TOPIC REDIRECT block missing from _buildVoiceSystemPrompt — companion may advise on HR/legal/financial issues it shouldn't."}]
    for kw in ("HR", "legal", "financial"):
        if kw not in c:
            return [{"check": "sensitive_topic",
                     "reason": f"SENSITIVE TOPIC REDIRECT does not list '{kw}' — vocabulary gap means model might fall through."}]
    return []


def check_worker_name(c: str) -> list[dict]:
    """L9 — Turn #13: worker-name personalization."""
    if not c:
        return []
    if "safeWorkerName" not in c:
        return [{"check": "worker_name",
                 "reason": "safeWorkerName const missing — _buildVoiceSystemPrompt may not gracefully handle anon callers."}]
    if "kapatid" not in c:
        return [{"check": "worker_name",
                 "reason": "'kapatid' fallback missing — anon voice-journal callers should still be addressed warmly when name is empty."}]
    return []


def check_repeat_request(c: str) -> list[dict]:
    """L10 — Turn #14: repeat-that handler."""
    if not c:
        return []
    for sym in ("_isRepeatRequest", "_REPEAT_RE"):
        if sym not in c:
            return [{"check": "repeat_request",
                     "reason": f"{sym} missing — workers in noisy plants asking 'ulit nga' burn an LLM call instead of replaying the last reply."}]
    if "_isRepeatRequest(transcript)" not in c:
        return [{"check": "repeat_request",
                 "reason": "Call site does not invoke _isRepeatRequest — helper exists but is never called."}]
    return []


CHECK_NAMES = [
    "persona_switch", "stale_guard", "topic_interruption", "thanks_handler",
    "asset_priming", "greeting", "codeswitch_anchor", "sensitive_topic",
    "worker_name", "repeat_request",
]

CHECK_LABELS = {
    "persona_switch":     "L1  Turn #5: Persona-switch utterance handler (_isPersonaSwitchUtterance + localStorage persistence)",
    "stale_guard":        "L2  Turn #6: Stale dialog-state guard (_isStaleDialogState + _STALE_THRESHOLD_MS + call-site wire)",
    "topic_interruption": "L3  Turn #7: Topic-shift signal suppresses affirmation bypass (_isTopicShiftSignal + bypass guard)",
    "thanks_handler":     "L4  Turn #8: Thanks/ack short-circuit (_isThanksReply + call-site invoke)",
    "asset_priming":      "L5  Turn #9: Asset-context auto-priming (_maybePrimeAssetContext + v_logbook_truth + call-site invoke)",
    "greeting":           "L6  Turn #10: First-turn greeting (only when !priorDialogState && empty _sessionTurns)",
    "codeswitch_anchor":  "L7  Turn #11: LANGUAGE NOTE block in _buildVoiceSystemPrompt (don't translate PH words)",
    "sensitive_topic":    "L8  Turn #12: SENSITIVE TOPIC REDIRECT block (HR / legal / financial → supervisor)",
    "worker_name":        "L9  Turn #13: safeWorkerName const + 'kapatid' fallback in prompt builder",
    "repeat_request":     "L10 Turn #14: Repeat-that handler (_isRepeatRequest replays last assistant turn)",
}


def main() -> int:
    print("\033[1m\nDialog Quality Extended Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read() or ""
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_persona_switch(c)
    issues += check_stale_guard(c)
    issues += check_topic_interruption(c)
    issues += check_thanks_handler(c)
    issues += check_asset_priming(c)
    issues += check_greeting(c)
    issues += check_codeswitch_anchor(c)
    issues += check_sensitive_topic(c)
    issues += check_worker_name(c)
    issues += check_repeat_request(c)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
