"""
AI Companion Orchestration + Integration Validator (turns #65-#74)
===================================================================
Forward-only L0 ratchet for the seventh 10-turn flywheel batch (2026-05-21).
Covers ORCHESTRATION + INTEGRATION — pdf export, pronunciation overrides,
voice-execute safety lock, persona portrait animation, cross-hive
benchmark RPC, daily digest, push notifications, multi-worker concurrency
lock, accent adaptation, streaming SSE.

  T65  PDF export request detector
  T66  Custom pronunciation library
  T67  Voice execute lock (safety gate)
  T68  Persona portrait animation state
  T69  Cross-hive benchmark RPC wiring
  T70  Daily digest mode
  T71  Push notification readiness
  T72  Multi-worker concurrency lock
  T73  Accent / voice signature adaptation
  T74  Streaming SSE response indicator

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


def check_pdf_export(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_isPdfExportRequest" not in c:
        issues.append({"check": "pdf_export",
                       "reason": "_isPdfExportRequest missing — 'save as PDF' / 'i-PDF mo ito' can't be detected."})
    if "_PDF_EXPORT_RE" not in c:
        issues.append({"check": "pdf_export",
                       "reason": "_PDF_EXPORT_RE missing — detector has no regex to match against."})
    if "PDF EXPORT REQUEST" not in c:
        issues.append({"check": "pdf_export",
                       "reason": "PDF EXPORT REQUEST anchor missing — detector wired but LLM has no instruction."})
    return issues


def check_pronunciation(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_PRONUNCIATION_KEY", "_getPronunciationMap",
                "_setPronunciationOverride", "_applyPronunciation"):
        if sym not in c:
            issues.append({"check": "pronunciation",
                           "reason": f"{sym} missing — custom pronunciation library doesn't persist or apply."})
    if "PRONUNCIATION RESPECT" not in c:
        issues.append({"check": "pronunciation",
                       "reason": "PRONUNCIATION RESPECT anchor missing — overrides stored but LLM still says it the STT way."})
    if "wh_pronunciation_overrides" not in c:
        issues.append({"check": "pronunciation",
                       "reason": "localStorage key wh_pronunciation_overrides missing — overrides don't survive reload."})
    return issues


def check_voice_execute_lock(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_isVoiceExecuteAuth", "_setVoiceExecuteAuth"):
        if sym not in c:
            issues.append({"check": "voice_execute_lock",
                           "reason": f"{sym} missing — voice-execute safety gate is dead code."})
    if "VOICE EXECUTE LOCK" not in c:
        issues.append({"check": "voice_execute_lock",
                       "reason": "VOICE EXECUTE LOCK anchor missing — write-verb intents would auto-dispatch even when device hasn't opted in."})
    if "wh_voice_execute_authorised" not in c:
        issues.append({"check": "voice_execute_lock",
                       "reason": "localStorage key wh_voice_execute_authorised missing — opt-in doesn't persist."})
    return issues


def check_avatar_animation(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_setAvatarAnimation" not in c:
        issues.append({"check": "avatar_animation",
                       "reason": "_setAvatarAnimation missing — persona portrait can't animate per state."})
    if "_AVATAR_ANIM_STATES" not in c:
        issues.append({"check": "avatar_animation",
                       "reason": "_AVATAR_ANIM_STATES list missing — animation states aren't allow-listed."})
    if "data-avatar-anim" not in c:
        issues.append({"check": "avatar_animation",
                       "reason": "data-avatar-anim DOM attribute never set — CSS animation hook is unreachable."})
    # Open() should set 'listening'; close() should set 'idle'.
    if "_setAvatarAnimation('listening')" not in c:
        issues.append({"check": "avatar_animation",
                       "reason": "open() doesn't set 'listening' state — avatar never reflects mic-hot."})
    if "_setAvatarAnimation('idle')" not in c:
        issues.append({"check": "avatar_animation",
                       "reason": "close() doesn't reset to 'idle' — avatar stays on prior state across opens."})
    return issues


def check_cross_hive_rpc(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_fetchCrossHiveBenchmark" not in c:
        issues.append({"check": "cross_hive_rpc",
                       "reason": "_fetchCrossHiveBenchmark missing — T54 CROSS-HIVE BENCHMARK anchor has no real RPC backing it."})
    if "_CROSS_HIVE_RPC" not in c:
        issues.append({"check": "cross_hive_rpc",
                       "reason": "_CROSS_HIVE_RPC constant missing — RPC name not bound."})
    if "fn_cross_hive_benchmark" not in c:
        issues.append({"check": "cross_hive_rpc",
                       "reason": "RPC fn_cross_hive_benchmark not referenced — wiring incomplete."})
    if "_benchmarkCache" not in c:
        issues.append({"check": "cross_hive_rpc",
                       "reason": "_benchmarkCache missing — every turn hammers the RPC instead of caching."})
    return issues


def check_digest(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_isDigestRequest" not in c:
        issues.append({"check": "digest",
                       "reason": "_isDigestRequest missing — 'morning summary' can't flip into digest mode."})
    if "_DIGEST_RE" not in c:
        issues.append({"check": "digest",
                       "reason": "_DIGEST_RE missing — detector has no regex."})
    if "DIGEST MODE" not in c:
        issues.append({"check": "digest",
                       "reason": "DIGEST MODE anchor missing — LLM has no 5-line briefing instruction."})
    return issues


def check_push(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_canPushNotify", "_pushNotifyState",
                "_requestPushPerm", "_isPushOptInReply", "_PUSH_OPT_IN_RE"):
        if sym not in c:
            issues.append({"check": "push",
                           "reason": f"{sym} missing — push notification path is incomplete."})
    if "PUSH READINESS" not in c:
        issues.append({"check": "push",
                       "reason": "PUSH READINESS anchor missing — companion would promise alerts the browser may have denied."})
    return issues


def check_session_lock(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_SESSION_LOCK_TTL_MS", "_sessionLockKey",
                "_acquireSessionLock", "_isSessionLocked", "_releaseSessionLock"):
        if sym not in c:
            issues.append({"check": "session_lock",
                           "reason": f"{sym} missing — multi-worker concurrency lock is incomplete."})
    if "wh_voice_session_lock_" not in c:
        issues.append({"check": "session_lock",
                       "reason": "localStorage key prefix wh_voice_session_lock_ missing — lock doesn't persist across devices."})
    if "_acquireSessionLock(ctxOpen.hive_id" not in c:
        issues.append({"check": "session_lock",
                       "reason": "open() doesn't acquire the lock — helper exists but never runs."})
    if "_releaseSessionLock(ctxClose.hive_id" not in c:
        issues.append({"check": "session_lock",
                       "reason": "close() doesn't release the lock — stale lock would block the same worker for 10 min."})
    return issues


def check_accent(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_detectAccentHint", "_getAccentPref",
                "_setAccentPref", "_TGL_HINT_WORDS"):
        if sym not in c:
            issues.append({"check": "accent",
                           "reason": f"{sym} missing — accent / voice signature adaptation is incomplete."})
    if "ACCENT MATCH" not in c:
        issues.append({"check": "accent",
                       "reason": "ACCENT MATCH anchor missing — accent detected but LLM has no instruction to mirror."})
    if "wh_voice_accent_pref" not in c:
        issues.append({"check": "accent",
                       "reason": "localStorage key wh_voice_accent_pref missing — accent pref doesn't survive reload."})
    return issues


def check_streaming(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_setStreamingState", "_isStreaming",
                "_bindStreamingBubble", "_appendStreamingChunk", "_finalizeStream"):
        if sym not in c:
            issues.append({"check": "streaming",
                           "reason": f"{sym} missing — streaming SSE incremental update is incomplete."})
    if "data-streaming" not in c:
        issues.append({"check": "streaming",
                       "reason": "data-streaming DOM attribute never set — CSS cursor indicator can't react."})
    return issues


CHECK_NAMES = [
    "pdf_export", "pronunciation", "voice_execute_lock",
    "avatar_animation", "cross_hive_rpc", "digest",
    "push", "session_lock", "accent", "streaming",
]

CHECK_LABELS = {
    "pdf_export":         "T65 _isPdfExportRequest + _PDF_EXPORT_RE + PDF EXPORT REQUEST anchor",
    "pronunciation":      "T66 _PRONUNCIATION_KEY + _getPronunciationMap / _setPronunciationOverride / _applyPronunciation + PRONUNCIATION RESPECT anchor",
    "voice_execute_lock": "T67 _isVoiceExecuteAuth + _setVoiceExecuteAuth + VOICE EXECUTE LOCK anchor + wh_voice_execute_authorised key",
    "avatar_animation":   "T68 _setAvatarAnimation + _AVATAR_ANIM_STATES + data-avatar-anim + open/close wiring",
    "cross_hive_rpc":     "T69 _fetchCrossHiveBenchmark + _CROSS_HIVE_RPC + fn_cross_hive_benchmark + _benchmarkCache",
    "digest":             "T70 _isDigestRequest + _DIGEST_RE + DIGEST MODE anchor",
    "push":               "T71 _canPushNotify + _pushNotifyState + _requestPushPerm + _isPushOptInReply + _PUSH_OPT_IN_RE + PUSH READINESS anchor",
    "session_lock":       "T72 _SESSION_LOCK_TTL_MS + _sessionLockKey + acquire/check/release + key prefix + open/close wiring",
    "accent":             "T73 _detectAccentHint + _getAccentPref + _setAccentPref + _TGL_HINT_WORDS + ACCENT MATCH anchor + wh_voice_accent_pref",
    "streaming":          "T74 _setStreamingState + _isStreaming + _bindStreamingBubble + _appendStreamingChunk + _finalizeStream + data-streaming attribute",
}


def main() -> int:
    print("\033[1m\nAI Companion Orchestration + Integration Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_pdf_export(c)
    issues += check_pronunciation(c)
    issues += check_voice_execute_lock(c)
    issues += check_avatar_animation(c)
    issues += check_cross_hive_rpc(c)
    issues += check_digest(c)
    issues += check_push(c)
    issues += check_session_lock(c)
    issues += check_accent(c)
    issues += check_streaming(c)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
