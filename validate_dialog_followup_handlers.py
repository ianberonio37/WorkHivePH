"""
Dialog Follow-up Handlers Validator -- WorkHive AI Companion
=============================================================
Forward-only L0 ratchet on the dialog-state follow-up handlers in
voice-handler.js. Sister to validate_dialog_affirmation_bypass.py — that
validator locks the AFFIRMATIVE side ("yes / sige / the details"); this
one locks the three remaining bug classes that surfaced during the
2026-05-20 dialog-quality flywheel:

  Phase 4.2  Negation handler        ("no / cancel / wala / hindi" exits)
  Phase 4.3  Noisy transcript guard  (empty / "uh" / pure punctuation)
  Phase 4.4  Clarification-loop ceiling (after 2 clarifies, switch shape)

Why these matter:

  - Negation without a handler: worker says "no, cancel that" after a
    clarification prompt. The negation gets classified as 'unknown',
    confidence low, _shouldClarify fires AGAIN, and the worker is stuck.
  - Empty / noise transcript without a guard: background sound triggers
    speech recognition, transcript is "" or "uh", LLM is called (cost!),
    classifier returns 'unknown', clarification UI trips for what was
    really just silence.
  - No clarification ceiling: worker gives a low-confidence reply, gets
    a clarification, replies with another low-confidence reply, gets
    clarified again, forever. The companion feels broken.

6-layer audit:

  L1  Negation helper exists
      voice-handler.js declares `_isFollowupNegation` + `_NEGATION_RE`.

  L2  Negation vocabulary covers PH + English short replies
      Regex must include at minimum: no, cancel, wala, hindi, never mind.
      These are the bare-minimum phrases that should exit the topic.

  L3  Noise transcript guard exists with length checks
      `_isNoisyTranscript(text)` declared, body must include explicit
      length comparisons (so "" / 1-2 char / pure punctuation routes to
      the "didn't catch that" path BEFORE intent classification).

  L4  Negation handler clears dialog state
      Call-site negation block must call `_updateDialogState(..., null,
      ..., false, null)` — clearing priorIntent AND clarification_pending.
      Without this, the prior topic / pending clarify leaks into the
      next turn even though the worker explicitly said "no".

  L5  Noisy transcript guard is UPSTREAM of the LLM call
      The guard must fire BEFORE the `Promise.all([_fetchFullPlatformSnapshot,
      ...])` block. If it runs after, we've already paid the LLM call
      cost on what was silence.

  L6  Clarification-streak counter exists with break logic
      `_clarifyStreak` / `_bumpClarifyStreak()` / `_resetClarifyStreak()`
      declared, AND the _shouldClarify block must branch on
      `streak >= 2` to render a different prompt + reset. Without this,
      clarifications can loop indefinitely.

Usage:  python validate_dialog_followup_handlers.py

Skills consulted: ai-engineer (dialog-state machine integrity),
qa (multi-turn conversation edge cases), frontend (intent-classification
+ persona-handoff anti-patterns), performance (cost of running the LLM
on noise transcripts).

Related: [[project-dialog-affirmation-bypass-2026-05-20]] (sister fix
for the affirmative side), [[feedback-dialog-affirmation-bypass]].
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

# Phrases that MUST be in the negation regex. These are the bare-minimum
# vocabulary the bug class taught us. Add more as field reports surface.
REQUIRED_NEGATION_PHRASES = (
    "no",
    "cancel",
    "wala",
    "hindi",
    "never mind",
)


def _read_voice_handler() -> str | None:
    return read_file(VOICE_HANDLER_JS)


def check_negation_helper_exists(content: str) -> list[dict]:
    """L1 — _isFollowupNegation + _NEGATION_RE declared in voice-handler.js."""
    if not content:
        return [{
            "check": "negation_helper_exists",
            "reason": f"{VOICE_HANDLER_JS} not found",
        }]
    issues: list[dict] = []
    if "_isFollowupNegation" not in content:
        issues.append({
            "check": "negation_helper_exists",
            "reason": (
                "voice-handler.js does not declare _isFollowupNegation. "
                "Without it, 'no / cancel / wala / hindi' replies are "
                "classified as 'unknown' (low confidence) and trip the "
                "topic-switch clarification UI — the same bug class as "
                "the affirmation side (Phase 4.1), inverted."
            ),
        })
    if "_NEGATION_RE" not in content:
        issues.append({
            "check": "negation_helper_exists",
            "reason": (
                "voice-handler.js does not declare _NEGATION_RE. "
                "_isFollowupNegation cannot work without the regex."
            ),
        })
    return issues


def check_negation_vocabulary(content: str) -> list[dict]:
    """L2 — required PH + English negation phrases live in _NEGATION_RE."""
    if not content:
        return []
    m = re.search(r"_NEGATION_RE\s*=\s*/([^/]+)/", content)
    if not m:
        return []  # Caught by L1.
    regex_body = m.group(1).lower()
    missing = [p for p in REQUIRED_NEGATION_PHRASES if p.lower() not in regex_body]
    if missing:
        return [{
            "check": "negation_vocabulary",
            "reason": (
                f"_NEGATION_RE is missing required phrases: {missing}. "
                "Bare-minimum English + PH short replies that must exit "
                "the prior topic — each removal is a regression. "
                "Workers in the Philippines say 'wala na' / 'hindi pa' / "
                "'huwag na' as often as the English equivalents."
            ),
        }]
    return []


def check_noise_guard_exists(content: str) -> list[dict]:
    """L3 — _isNoisyTranscript declared with explicit length checks."""
    if not content:
        return []
    if "_isNoisyTranscript" not in content:
        return [{
            "check": "noise_guard_exists",
            "reason": (
                "voice-handler.js does not declare _isNoisyTranscript. "
                "Background sound / false mic triggers / lone 'uh' replies "
                "must route to a 'didn't catch that' prompt instead of "
                "running through intent classification (which would tag "
                "them 'unknown' and trip the clarification UI)."
            ),
        }]
    # Body must contain at least one explicit length comparison.
    fn_match = re.search(
        r"function\s+_isNoisyTranscript\s*\(\s*text\s*\)\s*\{([^}]+(?:\{[^}]*\}[^}]*)*?)\}",
        content,
        re.DOTALL,
    )
    if not fn_match:
        return [{
            "check": "noise_guard_exists",
            "reason": (
                "Could not parse _isNoisyTranscript body — check that the "
                "function is declared with `function` (not arrow / method)."
            ),
        }]
    body = fn_match.group(1)
    if not re.search(r"\.length\s*[<>]=?\s*\d+", body):
        return [{
            "check": "noise_guard_exists",
            "reason": (
                "_isNoisyTranscript has no explicit length comparison. "
                "Empty + 1-2 char + pure-filler transcripts need a length "
                "check to be classified as noise. Without it, the guard "
                "won't fire and the LLM gets called on silence."
            ),
        }]
    return []


def check_negation_clears_state(content: str) -> list[dict]:
    """L4 — call-site negation handler clears dialog state."""
    if not content:
        return []
    # Locate the negation guard's opening line, then scan the next ~30
    # lines (the block is short) for the cleared _updateDialogState call.
    # We can't use a single `[^}]*?` skipper because the `{}` arg literal
    # inside _updateDialogState(..., {}, ...) would terminate the class.
    guard_match = re.search(
        r"if\s*\(\s*priorIntent\s*&&\s*_isFollowupNegation\s*\(\s*transcript\s*\)\s*\)\s*\{",
        content,
    )
    if not guard_match:
        return [{
            "check": "negation_clears_state",
            "reason": (
                "Could not locate the `if (priorIntent && _isFollowupNegation"
                "(transcript))` guard at the call site. The negation helper "
                "may exist but is never invoked from the conversational flow."
            ),
        }]
    block_start = guard_match.end()
    # Scan up to ~1500 chars (block is short — render + persist + return).
    block_window = content[block_start: block_start + 1500]
    # Cleared call: _updateDialogState(..., sessionId, null, ...) — the
    # 4th positional arg (priorIntent) must be the literal `null` and
    # somewhere downstream another `null` (clarification_prompt) must also
    # appear. Same call also has `false` for clarification_pending.
    cleared_pattern = re.compile(
        r"_updateDialogState\s*\(\s*[^,]+,\s*[^,]+,\s*[^,]+,\s*null\s*,"
        r"[^;]*\bfalse\b[^;]*\bnull\b",
    )
    if not cleared_pattern.search(block_window):
        return [{
            "check": "negation_clears_state",
            "reason": (
                "Negation handler does not clear dialog state. Required "
                "shape inside the `if (priorIntent && _isFollowupNegation"
                "(transcript))` block:\n"
                "  _updateDialogState(db, ctx.hive_id, sessionId, null, "
                "0, {}, false, null);\n"
                "Both the priorIntent arg AND the clarification_prompt arg "
                "must be null. Otherwise the next turn still sees the "
                "stale topic / pending clarify even though the worker "
                "explicitly said 'no, cancel that'."
            ),
        }]
    return []


def check_noise_guard_upstream_of_llm(content: str) -> list[dict]:
    """L5 — _isNoisyTranscript fires BEFORE the LLM / heavy fetch."""
    if not content:
        return []
    noise_call = content.find("_isNoisyTranscript(transcript)")
    if noise_call < 0:
        return [{
            "check": "noise_guard_upstream",
            "reason": (
                "Could not locate `_isNoisyTranscript(transcript)` call site. "
                "The guard helper exists but is never invoked."
            ),
        }]
    # The ai-gateway POST + Promise.all fetch must come AFTER the noise
    # call. Greppable anchor: `_fetchFullPlatformSnapshot(` or
    # `agent:\s*'voice-journal'`.
    snapshot_call = content.find("_fetchFullPlatformSnapshot(", noise_call)
    gateway_call = content.find("agent:   'voice-journal'", noise_call)
    if snapshot_call < 0 and gateway_call < 0:
        return [{
            "check": "noise_guard_upstream",
            "reason": (
                "Could not find _fetchFullPlatformSnapshot or the ai-gateway "
                "POST downstream of the noise check. The guard may be "
                "placed at the end of the function — too late to skip the "
                "LLM call."
            ),
        }]
    # Both must be downstream (later in the file).
    if (snapshot_call >= 0 and snapshot_call < noise_call) or \
       (gateway_call >= 0 and gateway_call < noise_call):
        return [{
            "check": "noise_guard_upstream",
            "reason": (
                "_isNoisyTranscript fires AFTER the LLM call / heavy fetch. "
                "Move it upstream — right after priorIntent is read from "
                "_fetchDialogState — so noise transcripts skip both the "
                "Promise.all platform fetch AND the ai-gateway POST."
            ),
        }]
    return []


def check_clarify_streak_ceiling(content: str) -> list[dict]:
    """L6 — clarification-streak counter + break logic exist."""
    if not content:
        return []
    issues: list[dict] = []
    if "_clarifyStreak" not in content:
        issues.append({
            "check": "clarify_streak_ceiling",
            "reason": (
                "voice-handler.js does not declare a _clarifyStreak counter. "
                "Without it, the clarification UI can loop indefinitely — "
                "worker gives a low-confidence reply, gets clarified, gives "
                "another low-confidence reply, gets clarified again, etc."
            ),
        })
    for sym in ("_bumpClarifyStreak", "_resetClarifyStreak"):
        if sym not in content:
            issues.append({
                "check": "clarify_streak_ceiling",
                "reason": (
                    f"voice-handler.js does not declare {sym}. The streak "
                    "counter has no public mutator — the L2 sentinel can't "
                    "reach in to drive the loop-ceiling test, and the "
                    "ceiling can't actually fire."
                ),
            })
    # Break logic: inside the `if (_shouldClarify(...))` block, look for a
    # branch that triggers when `streak >= 2` (or similar) AND switches
    # the clarifyAnswer to a different shape.
    block_match = re.search(
        r"if\s*\(\s*_shouldClarify\s*\([^)]+\)\s*\)\s*\{([^}]+(?:\{[^}]*\}[^}]*)*?)\}",
        content,
        re.DOTALL,
    )
    if block_match:
        block = block_match.group(1)
        has_ceiling = bool(
            re.search(r"_bumpClarifyStreak\s*\(\s*\)", block) and
            re.search(r"streak\s*>=\s*\d+", block)
        )
        if not has_ceiling:
            issues.append({
                "check": "clarify_streak_ceiling",
                "reason": (
                    "The _shouldClarify branch does not call _bumpClarifyStreak() "
                    "and compare against >= 2. Required shape:\n"
                    "  const streak = _bumpClarifyStreak();\n"
                    "  let clarifyAnswer;\n"
                    "  if (streak >= 2) {\n"
                    "    clarifyAnswer = '<different-shape prompt>';\n"
                    "    _resetClarifyStreak();\n"
                    "  } else { clarifyAnswer = _generateClarification(...); }\n"
                    "Without this, two consecutive low-confidence replies "
                    "loop the same prompt forever."
                ),
            })
    else:
        issues.append({
            "check": "clarify_streak_ceiling",
            "reason": (
                "Could not parse the _shouldClarify(...) `if` block to "
                "verify the ceiling logic. Check the call site at the "
                "Phase 4 intent-refinement section."
            ),
        })
    return issues


CHECK_NAMES = [
    "negation_helper_exists",
    "negation_vocabulary",
    "noise_guard_exists",
    "negation_clears_state",
    "noise_guard_upstream",
    "clarify_streak_ceiling",
]

CHECK_LABELS = {
    "negation_helper_exists":  "L1  _isFollowupNegation + _NEGATION_RE exist in voice-handler.js",
    "negation_vocabulary":     "L2  Negation regex covers PH + English (no, cancel, wala, hindi, never mind)",
    "noise_guard_exists":      "L3  _isNoisyTranscript declared with explicit length checks",
    "negation_clears_state":   "L4  Call-site negation handler resets dialog state (null priorIntent + clarification_prompt)",
    "noise_guard_upstream":    "L5  _isNoisyTranscript fires BEFORE the LLM call + heavy parallel fetch",
    "clarify_streak_ceiling":  "L6  _clarifyStreak counter + >= 2 break logic prevent infinite clarification loops",
}


def main() -> int:
    print("\033[1m\nDialog Follow-up Handlers Validator (6-layer)\033[0m")
    print("=" * 60)
    content = _read_voice_handler()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_negation_helper_exists(content or "")
    if content:
        issues += check_negation_vocabulary(content)
        issues += check_noise_guard_exists(content)
        issues += check_negation_clears_state(content)
        issues += check_noise_guard_upstream_of_llm(content)
        issues += check_clarify_streak_ceiling(content)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
