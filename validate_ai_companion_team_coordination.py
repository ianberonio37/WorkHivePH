"""
AI Companion Team Coordination Validator (turns #145-#154)
============================================================
Forward-only L0 ratchet for the fifteenth 10-turn flywheel batch (2026-05-21).

  T145  Active voice worker list
  T146  Cross-worker handoff
  T147  Shared note thread
  T148  High-concurrency alert
  T149  Watchlist subscriptions
  T150  Voice broadcast (supervisor-gated)
  T151  Knowledge sharing nudge (resolution detector)
  T152  Cross-shift continuity
  T153  Buddy mode
  T154  Mention notifications

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


def check_active_list(c: str) -> list[dict]:
    if "_listActiveVoiceWorkers" not in c:
        return [{"check": "active_list", "reason": "_listActiveVoiceWorkers missing."}]
    if "wh_voice_presence" not in c:
        return [{"check": "active_list", "reason": "wh_voice_presence not queried."}]
    return []


def check_handoff(c: str) -> list[dict]:
    issues = []
    for sym in ("_HANDOFF_RE", "_detectHandoffRequest", "_sendHandoff", "_fetchPendingHandoffs"):
        if sym not in c:
            issues.append({"check": "handoff", "reason": f"{sym} missing."})
    if "companion_handoff" not in c:
        issues.append({"check": "handoff", "reason": "companion_handoff table missing."})
    return issues


def check_shared_note(c: str) -> list[dict]:
    issues = []
    for sym in ("_SHARED_NOTE_RE", "_isSharedNoteRequest", "_postSharedNote"):
        if sym not in c:
            issues.append({"check": "shared_note", "reason": f"{sym} missing."})
    if "shared_voice_notes" not in c:
        issues.append({"check": "shared_note", "reason": "shared_voice_notes table missing."})
    return issues


def check_concurrency(c: str) -> list[dict]:
    if "_shouldFlagHighConcurrency" not in c:
        return [{"check": "concurrency", "reason": "_shouldFlagHighConcurrency missing."}]
    return []


def check_watchlist(c: str) -> list[dict]:
    issues = []
    for sym in ("_subscribeWatchlist", "_unsubscribeWatchlist", "_detectWatchRequest", "_WATCH_RE"):
        if sym not in c:
            issues.append({"check": "watchlist", "reason": f"{sym} missing."})
    if "asset_watchlist" not in c:
        issues.append({"check": "watchlist", "reason": "asset_watchlist table missing."})
    return issues


def check_broadcast(c: str) -> list[dict]:
    issues = []
    if "_sendBroadcast" not in c:
        issues.append({"check": "broadcast", "reason": "_sendBroadcast missing."})
    if "'not_supervisor'" not in c:
        issues.append({"check": "broadcast", "reason": "not_supervisor blocker missing — broadcast must be gated."})
    if "__broadcast__" not in c:
        issues.append({"check": "broadcast", "reason": "__broadcast__ marker missing — recipients can't filter broadcasts."})
    return issues


def check_resolution(c: str) -> list[dict]:
    issues = []
    if "_RESOLUTION_RE" not in c:
        issues.append({"check": "resolution", "reason": "_RESOLUTION_RE missing."})
    if "_detectResolution" not in c:
        issues.append({"check": "resolution", "reason": "_detectResolution missing."})
    return issues


def check_cross_shift(c: str) -> list[dict]:
    if "_fetchPriorShiftOpenItems" not in c:
        return [{"check": "cross_shift", "reason": "_fetchPriorShiftOpenItems missing."}]
    if "v_logbook_truth" not in c:
        return [{"check": "cross_shift", "reason": "v_logbook_truth not queried."}]
    return []


def check_buddy(c: str) -> list[dict]:
    issues = []
    for sym in ("_BUDDY_KEY_PREFIX", "_buddyKey", "_setBuddy", "_getBuddy",
                "_clearBuddy", "_detectBuddySet", "_BUDDY_SET_RE"):
        if sym not in c:
            issues.append({"check": "buddy", "reason": f"{sym} missing."})
    if "wh_voice_buddy_" not in c:
        issues.append({"check": "buddy", "reason": "wh_voice_buddy_ localStorage key prefix missing."})
    return issues


def check_mention(c: str) -> list[dict]:
    if "_sendMentionNotice" not in c:
        return [{"check": "mention", "reason": "_sendMentionNotice missing."}]
    if "'mention'" not in c:
        return [{"check": "mention", "reason": "'mention' status not used."}]
    return []


def check_phase_a_wires(c: str) -> list[dict]:
    issues = []
    pairs = [
        ("HANDOFF",            "_detectHandoffRequest(transcript)",  "T146 HANDOFF anchor"),
        ("SHARED NOTE",        "_isSharedNoteRequest(transcript)",   "T147 SHARED NOTE anchor"),
        ("WATCHLIST",          "_detectWatchRequest(transcript)",    "T149 WATCHLIST anchor"),
        ("RESOLUTION CAPTURE", "_detectResolution(transcript)",      "T151 RESOLUTION CAPTURE anchor"),
        ("BUDDY SET",          "_detectBuddySet(transcript)",        "T153 BUDDY SET anchor"),
    ]
    for anchor, callsite, label in pairs:
        if anchor not in c:
            issues.append({"check": "wires", "reason": f"{label} anchor '{anchor}' missing."})
        if callsite not in c:
            issues.append({"check": "wires", "reason": f"{label} call '{callsite}' missing."})
    return issues


CHECK_NAMES = [
    "active_list", "handoff", "shared_note", "concurrency", "watchlist",
    "broadcast", "resolution", "cross_shift", "buddy", "mention",
    "wires",
]
CHECK_LABELS = {
    "active_list":  "T145 _listActiveVoiceWorkers + wh_voice_presence query",
    "handoff":      "T146 handoff detect/send/fetch + companion_handoff table",
    "shared_note":  "T147 shared note detect/post + shared_voice_notes table",
    "concurrency":  "T148 _shouldFlagHighConcurrency",
    "watchlist":    "T149 subscribe/unsubscribe/detect + asset_watchlist table",
    "broadcast":    "T150 _sendBroadcast + not_supervisor gate + __broadcast__ marker",
    "resolution":   "T151 _RESOLUTION_RE + _detectResolution",
    "cross_shift":  "T152 _fetchPriorShiftOpenItems + v_logbook_truth query",
    "buddy":        "T153 buddy key/set/get/clear/detect + wh_voice_buddy_ key",
    "mention":      "T154 _sendMentionNotice + 'mention' status",
    "wires":        "PHASE A wires — T146/T147/T149/T151 anchors live in perTurnAnchors",
}


def main() -> int:
    print("\033[1m\nAI Companion Team Coordination Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_active_list(c)
    issues += check_handoff(c)
    issues += check_shared_note(c)
    issues += check_concurrency(c)
    issues += check_watchlist(c)
    issues += check_broadcast(c)
    issues += check_resolution(c)
    issues += check_cross_shift(c)
    issues += check_buddy(c)
    issues += check_mention(c)
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
