"""
AI Companion Collaboration + Wellbeing Validator (turns #35-#44)
================================================================
Forward-only L0 ratchet for the fourth 10-turn flywheel batch
(2026-05-21). Different dimensions again — covers ACTION SAFETY
(voice action confirmation, batch parsing), EXPLAINABILITY (source
tracing), COLLABORATION (co-worker mention, shift handover),
WELLBEING (graveyard nudge, fatigue signal, encouragement),
SKILL DEVELOPMENT (gap nudge), and EXPORT (transcript request).

  T35  Voice action confirmation (write-verb detector + anchor)
  T36  Wellbeing nudge (graveyard shift auto-anchor)
  T37  Encouragement anchor (recent close = ack the win)
  T38  Skill-gap nudge (v_worker_skill_truth → refresher offer)
  T39  Shift-handover mode (handover language → structured block)
  T40  Batch action parsing detector
  T41  Explainability request detector + EXPLAIN PATH anchor
  T42  Co-worker mention detector
  T43  Fatigue signal detector
  T44  Transcript export detector + EXPORT REQUEST anchor

10-layer audit.
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


def _read() -> str:
    return read_file(VOICE_HANDLER_JS) or ""


def check_action_confirmation(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_isActionRequest", "_ACTION_VERB_RE"):
        if sym not in c:
            issues.append({"check": "action_confirmation",
                           "reason": f"{sym} missing — write-verb utterances ('log this', 'create a PM') run through the LLM with no confirmation prompt, risking silent side effects."})
    if "ACTION CONFIRMATION" not in c:
        issues.append({"check": "action_confirmation",
                       "reason": "ACTION CONFIRMATION anchor missing — detector exists but LLM has no instruction to confirm before voice-action-router executes."})
    if "_isActionRequest(transcript)" not in c:
        issues.append({"check": "action_confirmation",
                       "reason": "Call site does not invoke _isActionRequest(transcript) — detector exists but never runs."})
    return issues


def check_wellbeing(c: str) -> list[dict]:
    if "WELLBEING NUDGE" not in c:
        return [{"check": "wellbeing",
                 "reason": "WELLBEING NUDGE anchor missing — graveyard-shift workers + tired workers get the same advice-heavy tone as the day shift."}]
    if "isGraveyard" not in c:
        return [{"check": "wellbeing",
                 "reason": "isGraveyard branch missing — wellbeing nudge doesn't activate automatically on night-shift."}]
    return []


def check_encouragement(c: str) -> list[dict]:
    if "ENCOURAGEMENT" not in c:
        return [{"check": "encouragement",
                 "reason": "ENCOURAGEMENT anchor missing — workers closing logbook entries / completing PMs get zero verbal recognition."}]
    return []


def check_skill_gap(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_fetchSkillGapFlag" not in c:
        issues.append({"check": "skill_gap",
                       "reason": "_fetchSkillGapFlag missing — skill-gap nudges have no data source."})
    if "v_worker_skill_truth" not in c:
        issues.append({"check": "skill_gap",
                       "reason": "Skill-gap fetch doesn't query v_worker_skill_truth — must use the canonical view."})
    if "SKILL GAPS" not in c:
        issues.append({"check": "skill_gap",
                       "reason": "SKILL GAPS anchor missing — fetched data has no LLM-facing instruction."})
    if "_fetchSkillGapFlag(db" not in c:
        issues.append({"check": "skill_gap",
                       "reason": "Call site does not invoke _fetchSkillGapFlag — helper exists but never runs."})
    return issues


def check_handover(c: str) -> list[dict]:
    if "HANDOVER MODE" not in c:
        return [{"check": "handover",
                 "reason": "HANDOVER MODE anchor missing — workers asking for a handover get prose instead of a structured 4-line block."}]
    if "handoverIntent" not in c:
        return [{"check": "handover",
                 "reason": "handoverIntent detector missing — anchor fires unconditionally or never."}]
    return []


def check_batch_action(c: str) -> list[dict]:
    if "_isBatchAction" not in c:
        return [{"check": "batch_action",
                 "reason": "_isBatchAction missing — multi-item utterances ('log X, Y, and Z') get parsed as one item."}]
    if "BATCH ACTION" not in c:
        return [{"check": "batch_action",
                 "reason": "BATCH ACTION anchor missing — detector fires but LLM has no instruction to restate as a batch."}]
    return []


def check_explainability(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_isExplainRequest", "_EXPLAIN_RE"):
        if sym not in c:
            issues.append({"check": "explainability",
                           "reason": f"{sym} missing — 'why did you say that?' / 'how do you know?' don't trigger source-trace."})
    if "EXPLAIN PATH" not in c:
        issues.append({"check": "explainability",
                       "reason": "EXPLAIN PATH anchor missing — model has no instruction to name the source view + row count + timestamp."})
    return issues


def check_mention(c: str) -> list[dict]:
    if "_detectMention" not in c:
        return [{"check": "mention",
                 "reason": "_detectMention missing — 'kasama si Romeo' / 'with Romeo' co-worker tags don't reach voice-action-router."}]
    if "CO-WORKER MENTION" not in c:
        return [{"check": "mention",
                 "reason": "CO-WORKER MENTION anchor missing — detector captures the name but LLM has no instruction to surface it for logbook tagging."}]
    return []


def check_fatigue(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_detectFatigueSignal", "_FATIGUE_RE"):
        if sym not in c:
            issues.append({"check": "fatigue",
                           "reason": f"{sym} missing — 'pagod' / 'frustrated' / 'ayoko na' don't trigger empathetic tone shift."})
    if "FATIGUE SIGNAL" not in c:
        issues.append({"check": "fatigue",
                       "reason": "FATIGUE SIGNAL anchor missing — detector fires but LLM has no instruction to soften."})
    # PH fatigue words must be covered.
    m = re.search(r"_FATIGUE_RE\s*=\s*/([^/]+)/", c)
    if m:
        body = m.group(1).lower()
        for kw in ("pagod", "ayoko"):
            if kw not in body:
                issues.append({"check": "fatigue",
                               "reason": f"_FATIGUE_RE missing PH word '{kw}' — workers using Tagalog can't trigger the empathetic tone shift."})
    return issues


def check_export(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_isExportRequest", "_EXPORT_RE"):
        if sym not in c:
            issues.append({"check": "export",
                           "reason": f"{sym} missing — 'send the transcript' / 'i-save mo ito' don't trigger the export-to-report-sender path."})
    if "EXPORT REQUEST" not in c:
        issues.append({"check": "export",
                       "reason": "EXPORT REQUEST anchor missing — model may fabricate sending it instead of pointing to Report Sender."})
    return issues


CHECK_NAMES = [
    "action_confirmation", "wellbeing", "encouragement", "skill_gap",
    "handover", "batch_action", "explainability", "mention",
    "fatigue", "export",
]

CHECK_LABELS = {
    "action_confirmation": "T35 _isActionRequest + ACTION CONFIRMATION anchor + call-site invoke",
    "wellbeing":           "T36 WELLBEING NUDGE anchor + isGraveyard automatic branch",
    "encouragement":       "T37 ENCOURAGEMENT anchor in prompt builder",
    "skill_gap":           "T38 _fetchSkillGapFlag (v_worker_skill_truth) + SKILL GAPS anchor + call-site invoke",
    "handover":            "T39 HANDOVER MODE anchor + handoverIntent detector",
    "batch_action":        "T40 _isBatchAction + BATCH ACTION anchor",
    "explainability":      "T41 _isExplainRequest + EXPLAIN PATH anchor (name source view + row count + timestamp)",
    "mention":             "T42 _detectMention + CO-WORKER MENTION anchor",
    "fatigue":             "T43 _detectFatigueSignal + FATIGUE SIGNAL anchor + PH vocabulary (pagod / ayoko)",
    "export":              "T44 _isExportRequest + EXPORT REQUEST anchor",
}


def main() -> int:
    print("\033[1m\nAI Companion Collaboration + Wellbeing Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_action_confirmation(c)
    issues += check_wellbeing(c)
    issues += check_encouragement(c)
    issues += check_skill_gap(c)
    issues += check_handover(c)
    issues += check_batch_action(c)
    issues += check_explainability(c)
    issues += check_mention(c)
    issues += check_fatigue(c)
    issues += check_export(c)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
