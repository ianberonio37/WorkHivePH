"""
Dialog Recovery + Safety Validator -- WorkHive AI Companion
============================================================
Forward-only L0 ratchet for flywheel turn #4 of the dialog-quality stack.
Two distinct concerns share this validator because both sit at the
"escape hatch" layer:

  Phase 4.7  Clarification-recovery routing — break the clarify loop
             by routing bare page-name replies (after the streak ceiling
             prompt) to a real intent.

  Phase 4.8  Crisis-line safety override — the self-harm + helpline
             clause in persona.ts must STAY in the conversational mode
             prompt no matter what other dialog rules get rewritten.

Why these matter together:

  - Recovery: the previous turn (#2) added the streak ceiling that fires
    "what page would help: Analytics, Logbook, PM, or Asset Hub?". Without
    a recovery detector, the worker's "logbook" reply still enters intent
    classification, gets 'unknown', and trips clarify again. The ceiling
    is meaningless if there's no exit.

  - Crisis: voice-journal is a private spoken journal. Workers WILL
    eventually mention something the platform can't address (self-harm,
    severe psychological distress). The persona contract has always had
    a one-sentence helpline pointer. Forward-only enforcement keeps it
    from being silently optimised away as a future refactor "simplifies"
    the prompt.

5-layer audit:

  L1  _isPageRecoveryReply + _PAGE_RECOVERY_MAP declared in voice-handler.js
      The detector + the slug→intent lookup table.

  L2  Page-recovery vocabulary covers the post-ceiling answer space
      Map must include at minimum: analytics, logbook, pm, asset
      (matching the page names the ceiling prompt offers).

  L3  Call-site recovery handler guarded on clarification_pending
      The `_isPageRecoveryReply(transcript)` call must be wrapped in a
      `priorDialogState && priorDialogState.clarification_pending`
      guard so the detector only fires when the prior turn actually
      asked the recovery question.

  L4  persona.ts crisis line present in conversational mode
      The string `self-harm` AND `helpline` (or close variant) must
      appear inside the conversational-mode prompt body returned by
      `buildPersonaBlock(key, 'conversational')`.

  L5  Crisis line positioned alongside the safety rules block
      The crisis sentence must appear in the same vicinity as "No medical,
      legal, financial, or safety advice" — i.e. inside the Reply rules
      block, not stranded somewhere the model might compress away. We
      anchor on the safety-advice line and check the crisis line is
      within ~250 chars of it.

Usage:  python validate_dialog_recovery_safety.py

Skills consulted: ai-engineer (recovery routing + dialog-state escape
hatches), security (safety override durability under prompt rewrites),
qa (multi-turn loop-exit tests), maintenance-expert (worker mental-health
context — long shifts + plant stress, real concern, not theatre).

Related:
- [[project-dialog-affirmation-bypass-2026-05-20]] (turn #1)
- [[project-dialog-followup-handlers-2026-05-20]] (turn #2 — added the
  streak ceiling this turn provides the recovery exit for)
- [[project-dialog-continuity-2026-05-20]] (turn #3)
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


VOICE_HANDLER_JS  = "voice-handler.js"
PERSONA_TS        = os.path.join("supabase", "functions", "_shared", "persona.ts")

# Bare-minimum page-name slugs the recovery map must handle (mirrors the
# ceiling prompt's answer set).
REQUIRED_RECOVERY_KEYS = (
    "analytics",
    "logbook",
    "pm",
    "asset",
)


def _read(path: str) -> str | None:
    return read_file(path)


def check_recovery_helper_exists(content: str) -> list[dict]:
    """L1 — _isPageRecoveryReply + _PAGE_RECOVERY_MAP declared."""
    if not content:
        return [{
            "check": "recovery_helper_exists",
            "reason": f"{VOICE_HANDLER_JS} not found",
        }]
    issues: list[dict] = []
    if "_isPageRecoveryReply" not in content:
        issues.append({
            "check": "recovery_helper_exists",
            "reason": (
                "voice-handler.js does not declare _isPageRecoveryReply. "
                "Without the detector, the streak-ceiling prompt 'what page "
                "would help?' has no machine-readable exit — workers' bare "
                "page-name replies fall through to normal classification "
                "and re-trigger the clarify loop."
            ),
        })
    if "_PAGE_RECOVERY_MAP" not in content:
        issues.append({
            "check": "recovery_helper_exists",
            "reason": (
                "voice-handler.js does not declare _PAGE_RECOVERY_MAP. "
                "The slug→intent lookup table is required for the recovery "
                "handler to know what intent to route to."
            ),
        })
    return issues


def check_recovery_vocabulary(content: str) -> list[dict]:
    """L2 — recovery map covers the ceiling prompt's answer space."""
    if not content:
        return []
    m = re.search(
        r"_PAGE_RECOVERY_MAP\s*=\s*\{([^}]+)\}",
        content,
        re.DOTALL,
    )
    if not m:
        return []  # Caught by L1.
    map_body = m.group(1).lower()
    missing = [k for k in REQUIRED_RECOVERY_KEYS if f"'{k.lower()}'" not in map_body
               and f'"{k.lower()}"' not in map_body]
    if missing:
        return [{
            "check": "recovery_vocabulary",
            "reason": (
                f"_PAGE_RECOVERY_MAP is missing keys: {missing}. The "
                "streak-ceiling prompt offers 'Analytics / Logbook / PM "
                "Scheduler / Asset Hub' — each one needs a recovery slug "
                "or the ceiling prompt becomes a dead-end the worker can't "
                "navigate."
            ),
        }]
    return []


def check_recovery_callsite_guard(content: str) -> list[dict]:
    """L3 — call-site detector wrapped in clarification_pending guard."""
    if not content:
        return []
    # [\s\S]{0,80} spans the closing paren + optional newline + indent
    # between `clarification_pending)` and the `?` of the ternary. We
    # cap at 80 chars so a refactor that completely changed the shape
    # (e.g. moved to a multi-line `if`) still gets flagged.
    pattern = re.compile(
        r"priorDialogState\s*&&\s*priorDialogState\.clarification_pending"
        r"[\s\S]{0,80}"
        r"\?\s*_isPageRecoveryReply\s*\(\s*transcript\s*\)",
    )
    if not pattern.search(content):
        return [{
            "check": "recovery_callsite_guard",
            "reason": (
                "Call site does not guard _isPageRecoveryReply on "
                "clarification_pending. Required shape:\n"
                "  const recoveryIntent = (priorDialogState && priorDialogState"
                ".clarification_pending)\n"
                "    ? _isPageRecoveryReply(transcript) : null;\n"
                "Without the guard the detector fires on EVERY turn, "
                "swallowing legitimate utterances that happen to match a "
                "page name ('logbook' in the middle of a sentence)."
            ),
        }]
    return []


def check_crisis_line_present(content: str) -> list[dict]:
    """L4 — persona.ts crisis line present in the conversational mode body."""
    if not content:
        return [{
            "check": "crisis_line_present",
            "reason": f"{PERSONA_TS} not found",
        }]
    # The conversational-mode prompt is the long return statement at the
    # bottom of buildPersonaBlock. Both 'self-harm' AND 'helpline' must
    # appear somewhere in the file (case-insensitive).
    lower = content.lower()
    has_self_harm = "self-harm" in lower or "self harm" in lower
    has_helpline  = "helpline" in lower or "hotline" in lower
    issues: list[dict] = []
    if not has_self_harm:
        issues.append({
            "check": "crisis_line_present",
            "reason": (
                f"{PERSONA_TS} is missing the 'self-harm' clause. The "
                "voice-journal companion is a private spoken journal — "
                "workers WILL eventually mention crisis material. The "
                "persona contract requires a one-sentence helpline pointer "
                "in the conversational-mode prompt; removing it lets the "
                "model drift into medical/safety advice it isn't qualified "
                "to give."
            ),
        })
    if not has_helpline:
        issues.append({
            "check": "crisis_line_present",
            "reason": (
                f"{PERSONA_TS} is missing the 'helpline' / 'hotline' "
                "pointer. The crisis sentence is meaningless without an "
                "exit destination — the worker hears 'I'm not the right "
                "audience' but nowhere to go next."
            ),
        })
    return issues


def check_crisis_line_positioned(content: str) -> list[dict]:
    """L5 — crisis line sits in the same block as the other safety rules."""
    if not content:
        return []
    # Anchor on the "No medical, legal, financial, or safety advice" string.
    safety_idx = content.lower().find("no medical")
    if safety_idx < 0:
        return [{
            "check": "crisis_line_positioned",
            "reason": (
                "Could not find the 'No medical, legal, financial, or "
                "safety advice' anchor in persona.ts. The crisis line is "
                "meant to sit alongside this safety-rules clause — if the "
                "anchor moved, the positioning check can't certify the "
                "crisis sentence is in the right context."
            ),
        }]
    # Crisis line must be within 400 chars of the safety anchor (in the
    # same logical paragraph of the conversational reply rules).
    window = content[safety_idx: safety_idx + 600].lower()
    if "self-harm" not in window and "self harm" not in window:
        return [{
            "check": "crisis_line_positioned",
            "reason": (
                "'self-harm' clause exists in persona.ts but is NOT in the "
                "same vicinity as the 'No medical/legal/financial/safety "
                "advice' block. The two MUST sit together — separated, "
                "the model is more likely to ignore the crisis pointer "
                "when compressing the prompt. Move the crisis sentence "
                "back inside the conversational Reply rules: block."
            ),
        }]
    return []


CHECK_NAMES = [
    "recovery_helper_exists",
    "recovery_vocabulary",
    "recovery_callsite_guard",
    "crisis_line_present",
    "crisis_line_positioned",
]

CHECK_LABELS = {
    "recovery_helper_exists":   "L1  _isPageRecoveryReply + _PAGE_RECOVERY_MAP declared in voice-handler.js",
    "recovery_vocabulary":      "L2  _PAGE_RECOVERY_MAP covers Analytics / Logbook / PM / Asset (the ceiling prompt answer space)",
    "recovery_callsite_guard":  "L3  Call site guards _isPageRecoveryReply on priorDialogState.clarification_pending",
    "crisis_line_present":      "L4  persona.ts conversational mode contains 'self-harm' + 'helpline' clauses",
    "crisis_line_positioned":   "L5  Crisis clause sits alongside the No-medical/legal/financial/safety-advice block",
}


def main() -> int:
    print("\033[1m\nDialog Recovery + Safety Validator (5-layer)\033[0m")
    print("=" * 60)
    vh_content = _read(VOICE_HANDLER_JS)
    persona_content = _read(PERSONA_TS)
    print(f"  Scanning {VOICE_HANDLER_JS} and {PERSONA_TS}")

    issues: list[dict] = []
    issues += check_recovery_helper_exists(vh_content or "")
    if vh_content:
        issues += check_recovery_vocabulary(vh_content)
        issues += check_recovery_callsite_guard(vh_content)
    issues += check_crisis_line_present(persona_content or "")
    if persona_content:
        issues += check_crisis_line_positioned(persona_content)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
