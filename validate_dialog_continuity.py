"""
Dialog Continuity Validator -- WorkHive AI Companion
=====================================================
Forward-only L0 ratchet on the multi-turn continuity surface inside
voice-handler.js `_buildVoiceSystemPrompt`. Flywheel turn #3 of the
dialog-quality stack:

  Turn #1  validate_dialog_affirmation_bypass.py  (yes / sige / the details)
  Turn #2  validate_dialog_followup_handlers.py   (no / cancel / noise / streak)
  Turn #3  validate_dialog_continuity.py          (THIS — pronouns + slots)

Why turn #3:

When a worker says "tell me more about IT" or "details on that one?" after
a prior turn about (say) Pump P-203, the LLM has no anchor unless the
SYSTEM PROMPT explicitly resolves the pronoun. Without it the model has
to guess or ask "which one?", which feels like the companion forgot. The
fix is in the prompt builder, not the intent classifier — adding a clear
PRIOR TOPIC HANDLE block + a natural-language SLOT ENUMERATION turns the
LLM's reference resolution into a deterministic lookup.

The same surface fixes the older "context_slots JSON dump" weakness —
dumping `{"asset_tag":"P-203","time_window":"this_week"}` is technically
information, but models honour natural-language enumerations like "You
already know: asset tag = P-203, time window = this week" much more
reliably.

5-layer audit:

  L1  _buildVoiceSystemPrompt exists
      The dialog state has to land in SOMETHING. If the prompt-builder
      function is gone, there's nothing to ratchet.

  L2  DIALOG STATE block declared in the prompt body
      String literal "DIALOG STATE:" must appear inside the function
      body. Removing it strips the continuity floor.

  L3  PRIOR TOPIC HANDLE clause emitted when intent is known
      The function must emit a `PRIOR TOPIC HANDLE` string when
      dialogState.current_intent is truthy and not 'unknown'. The string
      must explicitly list pronouns (it / that / yan / yun) AND tell the
      model to resolve to the prior intent.

  L4  SLOT ENUMERATION uses natural language, not raw JSON
      The function must build a "You already know:" enumeration over
      Object.keys(context_slots). Falling back to JSON.stringify is OK
      when slots are empty, but the named-bullet path must exist.

  L5  Pronoun vocabulary covers PH + English
      The PRIOR TOPIC HANDLE clause must list at minimum: it, that,
      yan, yun. These are the pronouns workers in the field actually
      use to refer back to a prior topic.

Usage:  python validate_dialog_continuity.py

Skills consulted: ai-engineer (system-prompt design + reference resolution),
qa (multi-turn continuity edge cases), frontend (intent-handoff
state machine), maintenance-expert (the PH-English pronoun vocabulary
workers actually use in plant settings).

Related: [[project-dialog-affirmation-bypass-2026-05-20]] (turn #1),
[[project-dialog-followup-handlers-2026-05-20]] (turn #2),
[[feedback-dialog-affirmation-bypass]] (guards future refactors).
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

# Required pronouns inside the PRIOR TOPIC HANDLE clause. Add new ones as
# field reports surface — Cebuano, Ilocano, etc.
REQUIRED_PRONOUNS = (
    "it",
    "that",
    "yan",
    "yun",
)


def _read_voice_handler() -> str | None:
    return read_file(VOICE_HANDLER_JS)


def _extract_prompt_builder(content: str) -> str | None:
    """Pull the body of _buildVoiceSystemPrompt out for targeted checks.
    Returns None when the function can't be found."""
    if not content:
        return None
    m = re.search(
        r"function\s+_buildVoiceSystemPrompt\s*\(",
        content,
    )
    if not m:
        return None
    # Walk to find the matching closing brace.
    body_start = content.find("{", m.end())
    if body_start < 0:
        return None
    depth = 1
    i = body_start + 1
    while i < len(content) and depth > 0:
        ch = content[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    if depth != 0:
        return None
    return content[body_start: i]


def check_prompt_builder_exists(content: str) -> list[dict]:
    """L1 — _buildVoiceSystemPrompt declared."""
    if not content:
        return [{
            "check": "prompt_builder_exists",
            "reason": f"{VOICE_HANDLER_JS} not found",
        }]
    if "_buildVoiceSystemPrompt" not in content:
        return [{
            "check": "prompt_builder_exists",
            "reason": (
                "voice-handler.js does not declare _buildVoiceSystemPrompt. "
                "The continuity ratchet has nothing to anchor on."
            ),
        }]
    return []


def check_dialog_state_block(body: str | None) -> list[dict]:
    """L2 — string literal 'DIALOG STATE:' inside the function body."""
    if body is None:
        return []  # Caught by L1.
    if "DIALOG STATE:" not in body:
        return [{
            "check": "dialog_state_block",
            "reason": (
                "_buildVoiceSystemPrompt does not emit a 'DIALOG STATE:' "
                "block in the system prompt. Without it the LLM never sees "
                "the prior intent / confidence / slots, and every turn "
                "starts cold — workers feel the companion 'forgot' them."
            ),
        }]
    return []


def check_prior_topic_handle(body: str | None) -> list[dict]:
    """L3 — PRIOR TOPIC HANDLE clause guarded on current_intent."""
    if body is None:
        return []
    if "PRIOR TOPIC HANDLE" not in body:
        return [{
            "check": "prior_topic_handle",
            "reason": (
                "_buildVoiceSystemPrompt does not emit a 'PRIOR TOPIC HANDLE' "
                "clause. Without it, the LLM has no deterministic anchor for "
                "pronouns ('it', 'that', 'yan', 'yun') and falls back to "
                "asking 'which one?' — the same UX symptom the 2026-05-20 "
                "screenshot showed."
            ),
        }]
    # Guard: emit ONLY when intent is meaningful (truthy + not 'unknown').
    # Resolving to "unknown" would actively mislead the model.
    if not re.search(r"intent\s*!==?\s*['\"]unknown['\"]", body):
        return [{
            "check": "prior_topic_handle",
            "reason": (
                "PRIOR TOPIC HANDLE clause exists but is not guarded against "
                "the 'unknown' intent. Emitting the clause when intent is "
                "'unknown' tells the LLM to resolve pronouns to nothing — "
                "worse than not emitting it at all."
            ),
        }]
    return []


def check_slot_enumeration(body: str | None) -> list[dict]:
    """L4 — natural-language slot enumeration over Object.keys(context_slots)."""
    if body is None:
        return []
    # Anchor on the "You already know:" string + a loop / map over slots.
    has_phrase = "You already know" in body
    has_loop = bool(
        re.search(r"Object\.keys\s*\(\s*slots\s*\)", body) or
        re.search(r"slotKeys\.map\s*\(", body)
    )
    if not has_phrase:
        return [{
            "check": "slot_enumeration",
            "reason": (
                "_buildVoiceSystemPrompt does not emit a 'You already know:' "
                "natural-language enumeration of context_slots. Models honour "
                "named-bullet slot lists ('asset tag = P-203') far more "
                "reliably than raw JSON dumps. The carryover info is in the "
                "prompt but in a shape the model tends to ignore."
            ),
        }]
    if not has_loop:
        return [{
            "check": "slot_enumeration",
            "reason": (
                "'You already know:' phrase is in the prompt but there is "
                "no iteration over the slot keys. The enumeration must be "
                "built from Object.keys(slots) or an equivalent .map() — "
                "hard-coding any slot keys would silently drift away from "
                "whatever the dialog_state RPC returns."
            ),
        }]
    return []


def check_pronoun_vocabulary(body: str | None) -> list[dict]:
    """L5 — required PH + English pronouns in the PRIOR TOPIC HANDLE clause."""
    if body is None:
        return []
    # Look only at the substring around the PRIOR TOPIC HANDLE block so
    # we don't accidentally match "it" / "that" in unrelated comments.
    idx = body.find("PRIOR TOPIC HANDLE")
    if idx < 0:
        return []  # Caught by L3.
    # Take ~600 chars of the clause body.
    clause = body[idx: idx + 600].lower()
    missing = [p for p in REQUIRED_PRONOUNS if p.lower() not in clause]
    if missing:
        return [{
            "check": "pronoun_vocabulary",
            "reason": (
                f"PRIOR TOPIC HANDLE clause is missing required pronouns: "
                f"{missing}. Workers in the field switch between English "
                f"('it', 'that') and Tagalog ('yan', 'yun', 'iyon') — every "
                f"removal is a regression. Add at the same indentation."
            ),
        }]
    return []


CHECK_NAMES = [
    "prompt_builder_exists",
    "dialog_state_block",
    "prior_topic_handle",
    "slot_enumeration",
    "pronoun_vocabulary",
]

CHECK_LABELS = {
    "prompt_builder_exists": "L1  _buildVoiceSystemPrompt exists in voice-handler.js",
    "dialog_state_block":    "L2  DIALOG STATE: block emitted in the system prompt",
    "prior_topic_handle":    "L3  PRIOR TOPIC HANDLE clause emitted when current_intent is known (not 'unknown')",
    "slot_enumeration":      "L4  SLOT CARRYOVER uses natural-language enumeration ('You already know:' + iteration over Object.keys(slots))",
    "pronoun_vocabulary":    "L5  PRIOR TOPIC HANDLE covers PH + English pronouns (it / that / yan / yun)",
}


def main() -> int:
    print("\033[1m\nDialog Continuity Validator (5-layer)\033[0m")
    print("=" * 60)
    content = _read_voice_handler()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_prompt_builder_exists(content or "")
    body = _extract_prompt_builder(content or "")
    issues += check_dialog_state_block(body)
    issues += check_prior_topic_handle(body)
    issues += check_slot_enumeration(body)
    issues += check_pronoun_vocabulary(body)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
