"""
Dialog Affirmation Bypass Validator -- WorkHive AI Companion
=============================================================
Forward-only L0 ratchet on the dialog-state clarification flow in
voice-handler.js. Locks the affirmation-bypass behaviour so that a
worker saying "yes", "sige", "oo", "the details", etc. NEVER trips
the "Did you mean to keep talking about X or switch to Y?" topic-
switch UI when there is already an active prior intent.

Caught 2026-05-20: Zaniah (the strategist persona) replied to "Yes,
the details." with "I think you're asking about unknown, but we were
just discussing query.ask. Did you mean to keep talking about
query.ask, or switch to unknown?" — even though the worker was
clearly confirming the prior topic. The bypass below ensures this
specific failure mode (and the broader "context loss on short
follow-ups" class) cannot regress silently.

5-layer audit:

  L1  Affirmation helper exists
      voice-handler.js must declare `_isFollowupAffirmation` plus an
      `_AFFIRMATION_RE` regex. The pair is the canonical detector.

  L2  Affirmation vocabulary covers PH + English short replies
      The regex must include at minimum: yes, sige, oo, "the details".
      These are the phrases workers used in the field that exposed
      the bug. Removing any of them = regression.

  L3  Word-cap guard exists
      The detector must cap on utterance length so a long follow-up
      ("yes, but also tell me MTBF") still goes through normal intent
      classification. Bypass without a cap = silent intent loss.

  L4  Call-site bypass clause exists BEFORE _shouldClarify
      voice-handler.js must normalize `newIntentKind = priorIntent`
      when affirmation is detected, BEFORE calling `_shouldClarify`.
      This is the actual fix — the detector is useless without the
      assignment at the call site.

  L5  _shouldClarify symmetry guard
      _shouldClarify(.., priorIntent, newIntent) must return false
      when priorIntent === newIntent. The bypass relies on this — if
      someone later "tightens" _shouldClarify to fire even on
      same-intent flips, the bypass silently breaks.

Usage:  python validate_dialog_affirmation_bypass.py

Skills consulted: ai-engineer (dialog-state machine integrity),
qa (multi-turn conversation edge cases), frontend (intent-classification
+ persona-handoff anti-patterns).
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

# Phrases that MUST be in the affirmation regex. These are the bare-minimum
# vocabulary the bug class taught us. Add more as new field reports surface.
REQUIRED_AFFIRMATION_PHRASES = (
    "yes",
    "sige",
    "oo",
    "the details",
)


def _read_voice_handler() -> str | None:
    return read_file(VOICE_HANDLER_JS)


def check_helper_exists(content: str) -> list[dict]:
    """L1 — _isFollowupAffirmation + _AFFIRMATION_RE declared in voice-handler.js."""
    if not content:
        return [{
            "check": "helper_exists",
            "reason": f"{VOICE_HANDLER_JS} not found",
        }]
    issues: list[dict] = []
    if "_isFollowupAffirmation" not in content:
        issues.append({
            "check": "helper_exists",
            "reason": (
                "voice-handler.js does not declare _isFollowupAffirmation. "
                "Without the detector, every short worker reply ('yes', "
                "'sige', 'the details') trips the topic-switch clarification "
                "UI even when they are clearly continuing the prior topic. "
                "See _AFFIRMATION_RE around the Phase 4 clarification helpers."
            ),
        })
    if "_AFFIRMATION_RE" not in content:
        issues.append({
            "check": "helper_exists",
            "reason": (
                "voice-handler.js does not declare _AFFIRMATION_RE. "
                "The regex is the canonical detector for follow-up "
                "affirmations; _isFollowupAffirmation cannot work without it."
            ),
        })
    return issues


def check_vocabulary_coverage(content: str) -> list[dict]:
    """L2 — required PH + English phrases live inside _AFFIRMATION_RE."""
    if not content:
        return []
    # Extract the regex body. _AFFIRMATION_RE = /^(... )([\s,!.?]|$)/i
    m = re.search(r"_AFFIRMATION_RE\s*=\s*/([^/]+)/", content)
    if not m:
        # Caught by L1 — skip here so we don't double-report.
        return []
    regex_body = m.group(1).lower()
    missing = []
    for phrase in REQUIRED_AFFIRMATION_PHRASES:
        # Word-boundary-ish check inside the alternation group. The phrase
        # may appear as part of a larger alternation (e.g. "yes|yeah|...").
        if phrase.lower() not in regex_body:
            missing.append(phrase)
    if missing:
        return [{
            "check": "vocabulary_coverage",
            "reason": (
                f"_AFFIRMATION_RE is missing required phrases: {missing}. "
                "These are the bare-minimum field-confirmed words that must "
                "bypass the topic-switch clarification (English + PH). "
                "Each removal is a regression by definition — the bug "
                "report on 2026-05-20 had a worker say 'Yes, the details.'"
            ),
        }]
    return []


def check_word_cap_guard(content: str) -> list[dict]:
    """L3 — _isFollowupAffirmation enforces an utterance-length cap."""
    if not content:
        return []
    # Look for a length check inside the helper body: words.length > N
    # or a similar split + length guard.
    fn_match = re.search(
        r"function\s+_isFollowupAffirmation\s*\(\s*text\s*\)\s*\{([^}]+(?:\{[^}]*\}[^}]*)*?)\}",
        content,
        re.DOTALL,
    )
    if not fn_match:
        return [{
            "check": "word_cap_guard",
            "reason": (
                "Could not locate the _isFollowupAffirmation function body "
                "in voice-handler.js. Without parsing the body, the word-cap "
                "guard cannot be verified — check that the function exists "
                "and is declared as a normal function (not arrow / method)."
            ),
        }]
    body = fn_match.group(1)
    # Accept either `.length > N` (number cap) or an explicit `words.length`
    # / `len(...)` comparison. We do NOT want the bypass to apply to long
    # sentences — a real follow-up "yes, but also tell me MTBF" must go
    # through normal intent classification.
    has_cap = bool(re.search(r"\.length\s*[><]=?\s*\d+", body) or
                   re.search(r"split\s*\(.+\)\.length", body))
    if not has_cap:
        return [{
            "check": "word_cap_guard",
            "reason": (
                "_isFollowupAffirmation does not appear to enforce an "
                "utterance-length cap. Without it, 'yes, but also tell me "
                "about MTBF this week' would bypass intent classification "
                "and incorrectly resume the prior topic. Required pattern: "
                "split on whitespace then check .length against a small "
                "integer (e.g. > 5)."
            ),
        }]
    return []


def check_callsite_bypass(content: str) -> list[dict]:
    """L4 — the clarification call site normalises newIntentKind = priorIntent
    when _isFollowupAffirmation(transcript) returns true, BEFORE invoking
    _shouldClarify. This is the actual behavioural fix."""
    if not content:
        return []
    # Pattern: the bypass clause must appear between the `let newIntentKind`
    # declaration and the `_shouldClarify(...)` call. We grep for the
    # signature `_isFollowupAffirmation(transcript)` inside an `if (priorIntent
    # && _isFollowupAffirmation(...))` guard plus a `newIntentKind = priorIntent`
    # assignment.
    #
    # Anchor on the `_isFollowupAffirmation(transcript)` call, then scan
    # forward up to 400 chars for the `newIntentKind = priorIntent;`
    # assignment. We avoid `[^)]` because turn #7's topic-shift suppression
    # adds `!_isTopicShiftSignal(transcript)` to the same condition, which
    # contains a `)` and would terminate the character class prematurely.
    anchor_match = re.search(
        r"_isFollowupAffirmation\s*\(\s*transcript\s*\)",
        content,
    )
    if anchor_match:
        window = content[anchor_match.end(): anchor_match.end() + 400]
        bypass_pattern = re.compile(r"newIntentKind\s*=\s*priorIntent\s*;")
    else:
        # Helper never invoked — fall through and let the search below fail.
        window = ""
        bypass_pattern = re.compile(r"newIntentKind\s*=\s*priorIntent\s*;")
    if not bypass_pattern.search(window):
        return [{
            "check": "callsite_bypass",
            "reason": (
                "Could not locate the affirmation bypass clause at the "
                "_shouldClarify call site. Required shape:\n"
                "  if (priorIntent && _isFollowupAffirmation(transcript)"
                " /* optional && !_isTopicShiftSignal(transcript) */) {\n"
                "    newIntentKind = priorIntent;\n"
                "    newConfidence = Math.max(newConfidence, 0.9);\n"
                "  }\n"
                "BEFORE the _shouldClarify(...) check. Without this "
                "assignment the detector exists but has no effect — "
                "the topic-switch UI still fires for 'yes, the details'."
            ),
        }]
    # Also verify the bypass is upstream of _shouldClarify, not downstream
    # (else the persisted intent / confidence path uses the wrong values).
    assign_in_window = bypass_pattern.search(window)
    bypass_pos = anchor_match.end() + assign_in_window.start()
    clarify_pos = content.find("_shouldClarify(", bypass_pos)
    if clarify_pos < 0:
        # No _shouldClarify after bypass — surface this as a separate
        # finding rather than silently passing.
        return [{
            "check": "callsite_bypass",
            "reason": (
                "Affirmation bypass exists but no subsequent _shouldClarify "
                "call follows it in voice-handler.js. The bypass is meant to "
                "normalise the intent BEFORE the clarification predicate "
                "runs — if the predicate moved or got removed, this "
                "validator can't certify the wiring."
            ),
        }]
    return []


def check_shouldclarify_symmetry(content: str) -> list[dict]:
    """L5 — _shouldClarify returns false when priorIntent === newIntent.
    The affirmation bypass relies on this: it normalises newIntentKind =
    priorIntent, then trusts the predicate to short-circuit. A future
    "tightening" that drops the equality guard would silently break the
    bypass."""
    if not content:
        return []
    fn_match = re.search(
        r"function\s+_shouldClarify\s*\([^)]*\)\s*\{([^}]+(?:\{[^}]*\}[^}]*)*?)\}",
        content,
        re.DOTALL,
    )
    if not fn_match:
        return [{
            "check": "shouldclarify_symmetry",
            "reason": (
                "Could not locate the _shouldClarify function body. The "
                "predicate is the second half of the affirmation contract — "
                "without it, the bypass has nowhere to short-circuit."
            ),
        }]
    body = fn_match.group(1)
    # Require an explicit `priorIntent !== newIntent` (or `!==`/`!=`)
    # equality check inside the body. Accept either ordering.
    has_equality = bool(
        re.search(r"priorIntent\s*!==?\s*newIntent", body) or
        re.search(r"newIntent\s*!==?\s*priorIntent", body)
    )
    if not has_equality:
        return [{
            "check": "shouldclarify_symmetry",
            "reason": (
                "_shouldClarify is missing the `priorIntent !== newIntent` "
                "equality guard. The affirmation bypass relies on the "
                "predicate returning false when the intent is normalised "
                "back to the prior topic. Without this guard, even after "
                "the bypass assigns newIntentKind = priorIntent, the "
                "clarification UI would still fire."
            ),
        }]
    return []


CHECK_NAMES = [
    "helper_exists",
    "vocabulary_coverage",
    "word_cap_guard",
    "callsite_bypass",
    "shouldclarify_symmetry",
]

CHECK_LABELS = {
    "helper_exists":         "L1  _isFollowupAffirmation + _AFFIRMATION_RE exist in voice-handler.js",
    "vocabulary_coverage":   "L2  Affirmation regex covers PH + English short replies (yes, sige, oo, the details)",
    "word_cap_guard":        "L3  _isFollowupAffirmation enforces an utterance-length cap (long follow-ups go through normal classification)",
    "callsite_bypass":       "L4  Call site normalises newIntentKind = priorIntent on affirmation, BEFORE _shouldClarify",
    "shouldclarify_symmetry":"L5  _shouldClarify returns false when priorIntent === newIntent (bypass short-circuit anchor)",
}


def main() -> int:
    print("\033[1m\nDialog Affirmation Bypass Validator (5-layer)\033[0m")
    print("=" * 60)
    content = _read_voice_handler()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_helper_exists(content or "")
    if content:
        issues += check_vocabulary_coverage(content)
        issues += check_word_cap_guard(content)
        issues += check_callsite_bypass(content)
        issues += check_shouldclarify_symmetry(content)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
