"""
AI Companion Integration + Audit Validator (turns #95-#104)
============================================================
Forward-only L0 ratchet for the tenth 10-turn flywheel batch (2026-05-21).

  T95   Audit log emission
  T96   Quiet hours
  T97   Action preflight
  T98   Idle session cleanup
  T99   Companion-error analytics
  T100  Session tag
  T101  Cross-page deep-link shorthand
  T102  STT grammar-mangled guess
  T103  Persona phrase pool
  T104  Shift-end handover trigger

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


def check_audit(c: str) -> list[dict]:
    issues = []
    if "_emitAuditEvent" not in c:
        issues.append({"check": "audit", "reason": "_emitAuditEvent missing."})
    if "ai_audit_log" not in c:
        issues.append({"check": "audit", "reason": "ai_audit_log table reference missing."})
    return issues


def check_quiet_hours(c: str) -> list[dict]:
    if "_isQuietHours" not in c:
        return [{"check": "quiet_hours", "reason": "_isQuietHours missing."}]
    return []


def check_preflight(c: str) -> list[dict]:
    issues = []
    if "_preflightAction" not in c:
        issues.append({"check": "preflight", "reason": "_preflightAction missing."})
    for blocker in ("'no_intent'", "'missing_asset_tag'", "'malformed_asset_tag'", "'voice_execute_lock'"):
        if blocker not in c:
            issues.append({"check": "preflight", "reason": f"Blocker {blocker} missing from preflight."})
    return issues


def check_idle(c: str) -> list[dict]:
    issues = []
    for sym in ("_IDLE_TIMEOUT_MS", "_scheduleIdleCleanup", "_cancelIdleCleanup"):
        if sym not in c:
            issues.append({"check": "idle", "reason": f"{sym} missing."})
    return issues


def check_error_analytics(c: str) -> list[dict]:
    issues = []
    for sym in ("_errorKey", "_bumpErrorCount", "_getErrorCounts"):
        if sym not in c:
            issues.append({"check": "error_analytics", "reason": f"{sym} missing."})
    if "wh_voice_errors_" not in c:
        issues.append({"check": "error_analytics", "reason": "localStorage key prefix wh_voice_errors_ missing."})
    return issues


def check_session_tag(c: str) -> list[dict]:
    issues = []
    for sym in ("_sessionTagKey", "_setSessionTag", "_getSessionTag", "_detectSessionTagRequest", "_TAG_RE"):
        if sym not in c:
            issues.append({"check": "session_tag", "reason": f"{sym} missing."})
    if "wh_voice_session_tag_" not in c:
        issues.append({"check": "session_tag", "reason": "localStorage key prefix wh_voice_session_tag_ missing."})
    return issues


def check_deep_link(c: str) -> list[dict]:
    issues = []
    for sym in ("_buildDeepLink", "_parseDeepLinkToken"):
        if sym not in c:
            issues.append({"check": "deep_link", "reason": f"{sym} missing."})
    if "wh-link" not in c:
        issues.append({"check": "deep_link", "reason": "wh-link token format not referenced."})
    return issues


def check_grammar_guess(c: str) -> list[dict]:
    if "_looksGrammarMangled" not in c:
        return [{"check": "grammar_guess", "reason": "_looksGrammarMangled missing."}]
    return []


def check_phrase_pool(c: str) -> list[dict]:
    issues = []
    if "_PHRASE_POOL" not in c:
        issues.append({"check": "phrase_pool", "reason": "_PHRASE_POOL missing."})
    if "_pickPersonaPhrase" not in c:
        issues.append({"check": "phrase_pool", "reason": "_pickPersonaPhrase missing."})
    for cat in ("ack:", "encourage:", "concern:", "closing:"):
        if cat not in c:
            issues.append({"check": "phrase_pool", "reason": f"Pool category {cat} missing."})
    return issues


def check_shift_end(c: str) -> list[dict]:
    if "_isNearShiftEnd" not in c:
        return [{"check": "shift_end", "reason": "_isNearShiftEnd missing."}]
    return []


def check_phase_a_wires(c: str) -> list[dict]:
    """Phase A wiring ratchet — T96/T100/T102/T104 anchors plumbed into perTurnAnchors."""
    issues = []
    pairs = [
        ("SESSION TAG",       "_detectSessionTagRequest(transcript)", "T100 SESSION TAG anchor"),
        ("STT MANGLED",       "_looksGrammarMangled(transcript)",     "T102 STT MANGLED anchor"),
        ("SHIFT END HORIZON", "_isNearShiftEnd(_shiftEnd, 30)",       "T104 SHIFT END HORIZON anchor"),
        ("QUIET HOURS",       "_isQuietHours(new Date())",            "T96 QUIET HOURS anchor"),
    ]
    for anchor, callsite, label in pairs:
        if anchor not in c:
            issues.append({"check": "wires", "reason": f"{label} string '{anchor}' missing."})
        if callsite not in c:
            issues.append({"check": "wires", "reason": f"{label} call '{callsite}' missing."})
    return issues


CHECK_NAMES = [
    "audit", "quiet_hours", "preflight", "idle", "error_analytics",
    "session_tag", "deep_link", "grammar_guess", "phrase_pool", "shift_end",
    "wires",
]
CHECK_LABELS = {
    "audit":            "T95 _emitAuditEvent + ai_audit_log table",
    "quiet_hours":      "T96 _isQuietHours (22:00-06:00 PHT)",
    "preflight":        "T97 _preflightAction + 4 blocker kinds",
    "idle":             "T98 _IDLE_TIMEOUT_MS + schedule/cancel idle cleanup",
    "error_analytics":  "T99 _errorKey + bump/get error count + wh_voice_errors_ key",
    "session_tag":      "T100 session tag get/set/detect + _TAG_RE + wh_voice_session_tag_ key",
    "deep_link":        "T101 _buildDeepLink + _parseDeepLinkToken + wh-link token",
    "grammar_guess":    "T102 _looksGrammarMangled",
    "phrase_pool":      "T103 _PHRASE_POOL with ack/encourage/concern/closing categories + _pickPersonaPhrase",
    "shift_end":        "T104 _isNearShiftEnd",
    "wires":            "PHASE A wires — T96/T100/T102/T104 anchors live in perTurnAnchors",
}


def main() -> int:
    print("\033[1m\nAI Companion Integration + Audit Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_audit(c)
    issues += check_quiet_hours(c)
    issues += check_preflight(c)
    issues += check_idle(c)
    issues += check_error_analytics(c)
    issues += check_session_tag(c)
    issues += check_deep_link(c)
    issues += check_grammar_guess(c)
    issues += check_phrase_pool(c)
    issues += check_shift_end(c)
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
