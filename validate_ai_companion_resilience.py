"""
AI Companion Resilience + Memory Validator (turns #45-#54)
===========================================================
Forward-only L0 ratchet for the fifth 10-turn flywheel batch (2026-05-21).
Different dimensions again — RESILIENCE (offline degradation, reply
cache), TRUST OPS (feedback escalation, identity drift), KNOWLEDGE
(custom plant terminology, conversation branching, cross-hive
benchmark), MULTI-MODAL (photo intent), UX (avatar emotion, summary
on demand).

  T45  Offline degradation tracker (_isOffline / _setOffline + flag set on error)
  T46  Reply cache memoization (10-min TTL + LRU)
  T47  Worker-feedback escalation (3+ negative in 7d → ai_quality_escalation)
  T48  Custom plant terminology resolver (v_asset_truth fuzzy match)
  T49  Conversation branching stack ("back to the X thing")
  T50  Multi-modal photo intent → Visual Defect Capture pointer
  T51  Avatar emotion state classifier
  T52  Cross-hive anonymised benchmark anchor
  T53  Summary-on-demand detector + SUMMARY MODE anchor
  T54  Identity drift tracker (worker_name change mid-session)

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


def check_offline(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_isOffline", "_setOffline", "_offlineFlag"):
        if sym not in c:
            issues.append({"check": "offline",
                           "reason": f"{sym} missing — gateway failures don't flip an offline indicator, so the UI keeps pretending to call the LLM."})
    if "_setOffline(true)" not in c:
        issues.append({"check": "offline",
                       "reason": "Error path doesn't set _setOffline(true) — flag never trips."})
    if "_setOffline(false)" not in c:
        issues.append({"check": "offline",
                       "reason": "Success path doesn't clear _setOffline(false) — flag stays stuck after recovery."})
    return issues


def check_reply_cache(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_lookupReplyCache", "_writeReplyCache", "_REPLY_CACHE_TTL_MS"):
        if sym not in c:
            issues.append({"check": "reply_cache",
                           "reason": f"{sym} missing — repeat-tap of the same question runs the LLM redundantly."})
    if "_lookupReplyCache(transcript" not in c:
        issues.append({"check": "reply_cache",
                       "reason": "Call site doesn't invoke _lookupReplyCache(transcript, ctx.hive_id) — helper exists but never runs."})
    if "_writeReplyCache(transcript" not in c:
        issues.append({"check": "reply_cache",
                       "reason": "Success path doesn't invoke _writeReplyCache(transcript, ctx.hive_id, answer) — replies never cached."})
    if "10 * 60 * 1000" not in c and "600000" not in c:
        issues.append({"check": "reply_cache",
                       "reason": "TTL not set to ~10 minutes — too-short cache wastes the optimisation, too-long cache serves stale answers."})
    return issues


def check_feedback_escalation(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_checkFeedbackEscalation" not in c:
        issues.append({"check": "feedback_escalation",
                       "reason": "_checkFeedbackEscalation missing — 3+ thumbs-down in 7d never escalates to ai-quality dashboard."})
    if "ai_quality_escalation" not in c:
        issues.append({"check": "feedback_escalation",
                       "reason": "Escalation upsert target missing — ratings accumulate but never reach supervisor view."})
    if "negative_count" not in c:
        issues.append({"check": "feedback_escalation",
                       "reason": "negative_count field missing — supervisor can't see how many low ratings triggered the flag."})
    return issues


def check_terminology(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_resolveTerminology" not in c:
        issues.append({"check": "terminology",
                       "reason": "_resolveTerminology missing — workers using 'the big chiller' / 'yung pump sa loading area' get unresolved nicknames."})
    if "v_asset_truth" not in c:
        issues.append({"check": "terminology",
                       "reason": "Terminology resolver doesn't query v_asset_truth — must use the canonical asset view."})
    if "TERMINOLOGY RESOLVED" not in c:
        issues.append({"check": "terminology",
                       "reason": "TERMINOLOGY RESOLVED anchor missing — resolver finds the asset but LLM has no instruction to use the resolved tag."})
    return issues


def check_branching(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_pushBranch", "_detectBranchRecall", "_branchStack", "_BRANCH_STACK_MAX"):
        if sym not in c:
            issues.append({"check": "branching",
                           "reason": f"{sym} missing — 'back to the X thing' doesn't restore that prior thread."})
    if "_pushBranch(newIntentKind" not in c:
        issues.append({"check": "branching",
                       "reason": "Success path doesn't push the resolved intent onto _branchStack — stack stays empty."})
    if "BRANCH RECALL" not in c:
        issues.append({"check": "branching",
                       "reason": "BRANCH RECALL anchor missing — detector exists but LLM has no instruction to resume the thread."})
    return issues


def check_photo_intent(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_isPhotoIntent", "_PHOTO_INTENT_RE"):
        if sym not in c:
            issues.append({"check": "photo_intent",
                           "reason": f"{sym} missing — 'let me show you' / 'tingnan mo to' doesn't suggest Visual Defect Capture."})
    if "PHOTO INTENT" not in c:
        issues.append({"check": "photo_intent",
                       "reason": "PHOTO INTENT anchor missing — detector fires but LLM has no instruction to point to the capture page."})
    return issues


def check_avatar_state(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_classifyAvatarState" not in c:
        issues.append({"check": "avatar_state",
                       "reason": "_classifyAvatarState missing — avatar emotion never reflects reply tone."})
    for state in ("urgent", "celebratory", "concerned", "helpful"):
        if "'" + state + "'" not in c and '"' + state + '"' not in c:
            issues.append({"check": "avatar_state",
                           "reason": f"avatar state '{state}' missing from classifier — UI tint layer has gaps."})
    if "data-avatar-state" not in c:
        issues.append({"check": "avatar_state",
                       "reason": "data-avatar-state attribute not stamped on the bubble — UI has no hook to read."})
    return issues


def check_benchmark(c: str) -> list[dict]:
    if "CROSS-HIVE BENCHMARK" not in c:
        return [{"check": "benchmark",
                 "reason": "CROSS-HIVE BENCHMARK anchor missing — anonymised PH industry medians never reach the reply."}]
    if "crossHiveBenchmarkAnchor" not in c:
        return [{"check": "benchmark",
                 "reason": "crossHiveBenchmarkAnchor const missing — block renamed or removed."}]
    if "anonymised" not in c.lower() and "anonymized" not in c.lower():
        return [{"check": "benchmark",
                 "reason": "Anchor doesn't insist on anonymised comparison — model might name other plants."}]
    return []


def check_summary(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_isSummaryRequest", "_SUMMARY_RE"):
        if sym not in c:
            issues.append({"check": "summary",
                           "reason": f"{sym} missing — 'summarise this conversation' / 'i-summarize mo' doesn't trigger summary mode."})
    if "SUMMARY MODE" not in c:
        issues.append({"check": "summary",
                       "reason": "SUMMARY MODE anchor missing — detector fires but LLM produces prose instead of a 4-bullet recap."})
    return issues


def check_identity_drift(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_trackIdentity", "_identityFirstSeen", "_resetIdentityTracking"):
        if sym not in c:
            issues.append({"check": "identity_drift",
                           "reason": f"{sym} missing — worker handing phone to a colleague mid-session goes undetected."})
    if "IDENTITY DRIFT" not in c:
        issues.append({"check": "identity_drift",
                       "reason": "IDENTITY DRIFT anchor missing — detector fires but LLM has no instruction to ask for verification."})
    return issues


CHECK_NAMES = [
    "offline", "reply_cache", "feedback_escalation", "terminology",
    "branching", "photo_intent", "avatar_state", "benchmark",
    "summary", "identity_drift",
]

CHECK_LABELS = {
    "offline":              "T45 _isOffline / _setOffline + error sets / success clears",
    "reply_cache":          "T46 _lookupReplyCache + _writeReplyCache + 10-min TTL + call-site invokes",
    "feedback_escalation":  "T47 _checkFeedbackEscalation + ai_quality_escalation upsert + negative_count field",
    "terminology":          "T48 _resolveTerminology (v_asset_truth fuzzy match) + TERMINOLOGY RESOLVED anchor",
    "branching":            "T49 _pushBranch + _detectBranchRecall + _branchStack + BRANCH RECALL anchor",
    "photo_intent":         "T50 _isPhotoIntent + PHOTO INTENT anchor (points to Visual Defect Capture)",
    "avatar_state":         "T51 _classifyAvatarState covers urgent/celebratory/concerned/helpful + data-avatar-state stamped on bubble",
    "benchmark":            "T52 CROSS-HIVE BENCHMARK anchor + anonymised comparison rule",
    "summary":              "T53 _isSummaryRequest + SUMMARY MODE anchor (4-bullet recap)",
    "identity_drift":       "T54 _trackIdentity + _identityFirstSeen + IDENTITY DRIFT anchor",
}


def main() -> int:
    print("\033[1m\nAI Companion Resilience + Memory Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_offline(c)
    issues += check_reply_cache(c)
    issues += check_feedback_escalation(c)
    issues += check_terminology(c)
    issues += check_branching(c)
    issues += check_photo_intent(c)
    issues += check_avatar_state(c)
    issues += check_benchmark(c)
    issues += check_summary(c)
    issues += check_identity_drift(c)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
