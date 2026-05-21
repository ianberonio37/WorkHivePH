"""
AI Companion Proactive Assistance + Learning Validator (turns #105-#114)
=========================================================================
Forward-only L0 ratchet for the eleventh 10-turn flywheel batch (2026-05-21).

  T105  Adaptive PM sync drift
  T106  Skill-level adaptation (apprentice/standard/senior)
  T107  Cross-asset pattern detection
  T108  Voice command vocabulary learning
  T109  Sentiment-over-time tracking
  T110  Anticipatory data warm-up
  T111  Maintenance vocabulary normalizer (symptom -> failure_mode)
  T112  Shift-boundary context reset
  T113  Knowledge gap logging (ai_knowledge_gap)
  T114  Mentor-mode handoff (mentor_relay_queue)

10-layer audit.
"""

from __future__ import annotations

import os, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

VOICE_HANDLER_JS = "voice-handler.js"


def _read() -> str:
    return read_file(VOICE_HANDLER_JS) or ""


def check_pm_sync(c: str) -> list[dict]:
    if "_detectPmSyncDrift" not in c:
        return [{"check": "pm_sync", "reason": "_detectPmSyncDrift missing."}]
    return []


def check_skill_adapt(c: str) -> list[dict]:
    issues = []
    for sym in ("_skillDepthForLevel", "_vocabularyForDepth"):
        if sym not in c:
            issues.append({"check": "skill_adapt", "reason": f"{sym} missing."})
    for d in ("'apprentice'", "'standard'", "'senior'"):
        if d not in c:
            issues.append({"check": "skill_adapt", "reason": f"Depth tier {d} missing."})
    return issues


def check_cross_asset(c: str) -> list[dict]:
    if "_detectCrossAssetPattern" not in c:
        return [{"check": "cross_asset", "reason": "_detectCrossAssetPattern missing."}]
    return []


def check_intent_history(c: str) -> list[dict]:
    issues = []
    for sym in ("_INTENT_HISTORY_KEY", "_recordIntent", "_topRecurringIntents"):
        if sym not in c:
            issues.append({"check": "intent_history", "reason": f"{sym} missing."})
    if "wh_voice_intent_hist_" not in c:
        issues.append({"check": "intent_history", "reason": "localStorage key prefix wh_voice_intent_hist_ missing."})
    return issues


def check_sentiment(c: str) -> list[dict]:
    issues = []
    for sym in ("_SENTIMENT_KEY", "_classifySessionSentiment", "_recordDailySentiment", "_isPersistentNegative"):
        if sym not in c:
            issues.append({"check": "sentiment", "reason": f"{sym} missing."})
    if "wh_voice_sentiment_" not in c:
        issues.append({"check": "sentiment", "reason": "localStorage key prefix wh_voice_sentiment_ missing."})
    for label in ("'positive'", "'neutral'", "'negative'"):
        if label not in c:
            issues.append({"check": "sentiment", "reason": f"Sentiment label {label} missing."})
    return issues


def check_warmup(c: str) -> list[dict]:
    issues = []
    for sym in ("_WARMUP_TTL_MS", "_warmupCache", "_warmAssetRecord"):
        if sym not in c:
            issues.append({"check": "warmup", "reason": f"{sym} missing."})
    if "v_asset_truth" not in c:
        issues.append({"check": "warmup", "reason": "_warmAssetRecord doesn't reference v_asset_truth."})
    return issues


def check_symptom(c: str) -> list[dict]:
    issues = []
    if "_SYMPTOM_TO_FMODE" not in c:
        issues.append({"check": "symptom", "reason": "_SYMPTOM_TO_FMODE missing."})
    if "_normalizeSymptom" not in c:
        issues.append({"check": "symptom", "reason": "_normalizeSymptom missing."})
    for mode in ("vibration_anomaly", "overheat", "noise_anomaly", "leak", "no_start"):
        if mode + ":" not in c:
            issues.append({"check": "symptom", "reason": f"Failure mode {mode} missing from symptom map."})
    return issues


def check_shift_boundary(c: str) -> list[dict]:
    if "_crossedShiftBoundary" not in c:
        return [{"check": "shift_boundary", "reason": "_crossedShiftBoundary missing."}]
    return []


def check_knowledge_gap(c: str) -> list[dict]:
    issues = []
    if "_logKnowledgeGap" not in c:
        issues.append({"check": "knowledge_gap", "reason": "_logKnowledgeGap missing."})
    if "ai_knowledge_gap" not in c:
        issues.append({"check": "knowledge_gap", "reason": "ai_knowledge_gap table reference missing."})
    return issues


def check_mentor(c: str) -> list[dict]:
    issues = []
    for sym in ("_isMentorHandoff", "_MENTOR_HANDOFF_RE", "_relayMentorQuestion"):
        if sym not in c:
            issues.append({"check": "mentor", "reason": f"{sym} missing."})
    if "mentor_relay_queue" not in c:
        issues.append({"check": "mentor", "reason": "mentor_relay_queue table reference missing."})
    return issues


def check_phase_a_wires(c: str) -> list[dict]:
    issues = []
    if "MENTOR HANDOFF" not in c:
        issues.append({"check": "wires", "reason": "T114 MENTOR HANDOFF anchor string missing."})
    if "_isMentorHandoff(transcript)" not in c:
        issues.append({"check": "wires", "reason": "T114 _isMentorHandoff(transcript) callsite missing."})
    return issues


CHECK_NAMES = [
    "pm_sync", "skill_adapt", "cross_asset", "intent_history", "sentiment",
    "warmup", "symptom", "shift_boundary", "knowledge_gap", "mentor",
    "wires",
]
CHECK_LABELS = {
    "pm_sync":         "T105 _detectPmSyncDrift",
    "skill_adapt":     "T106 _skillDepthForLevel + _vocabularyForDepth (apprentice/standard/senior)",
    "cross_asset":     "T107 _detectCrossAssetPattern",
    "intent_history":  "T108 _INTENT_HISTORY_KEY + _recordIntent + _topRecurringIntents + wh_voice_intent_hist_ key",
    "sentiment":       "T109 _SENTIMENT_KEY + _classifySessionSentiment + _recordDailySentiment + _isPersistentNegative + positive/neutral/negative labels",
    "warmup":          "T110 _WARMUP_TTL_MS + _warmupCache + _warmAssetRecord + v_asset_truth reference",
    "symptom":         "T111 _SYMPTOM_TO_FMODE map (vibration_anomaly/overheat/noise_anomaly/leak/no_start) + _normalizeSymptom",
    "shift_boundary":  "T112 _crossedShiftBoundary",
    "knowledge_gap":   "T113 _logKnowledgeGap + ai_knowledge_gap table",
    "mentor":          "T114 _isMentorHandoff + _MENTOR_HANDOFF_RE + _relayMentorQuestion + mentor_relay_queue table",
    "wires":           "PHASE A wires — T114 MENTOR HANDOFF anchor live in perTurnAnchors",
}


def main() -> int:
    print("\033[1m\nAI Companion Proactive Assistance + Learning Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_pm_sync(c)
    issues += check_skill_adapt(c)
    issues += check_cross_asset(c)
    issues += check_intent_history(c)
    issues += check_sentiment(c)
    issues += check_warmup(c)
    issues += check_symptom(c)
    issues += check_shift_boundary(c)
    issues += check_knowledge_gap(c)
    issues += check_mentor(c)
    issues += check_phase_a_wires(c)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
