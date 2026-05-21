"""
AI Companion Operational Excellence Validator (turns #135-#144)
================================================================
Forward-only L0 ratchet for the fourteenth 10-turn flywheel batch (2026-05-21).

  T135  Health check ping (5-min interval)
  T136  Self-test on mount
  T137  Feature flag system
  T138  Browser support banner
  T139  Network condition adaptation
  T140  Memory pressure handler
  T141  Server clock drift check
  T142  Background tab pause
  T143  Auto-recovery on JS exception
  T144  Presence heartbeat

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


def check_health(c: str) -> list[dict]:
    issues = []
    for sym in ("_HEALTH_PING_INTERVAL_MS", "_pingHealthCheck",
                "_scheduleHealthPings", "_stopHealthPings"):
        if sym not in c:
            issues.append({"check": "health", "reason": f"{sym} missing."})
    if "/functions/v1/voice-health" not in c:
        issues.append({"check": "health", "reason": "voice-health endpoint not referenced."})
    return issues


def check_self_test(c: str) -> list[dict]:
    if "_runSelfTest" not in c:
        return [{"check": "self_test", "reason": "_runSelfTest missing."}]
    issues = []
    # Self-test must cover multiple critical helpers
    for hint in ("affirmation regex", "asset tag normalize", "pii scrub"):
        if hint not in c:
            issues.append({"check": "self_test", "reason": f"Self-test missing coverage hint: {hint}."})
    return issues


def check_feature_flags(c: str) -> list[dict]:
    issues = []
    for sym in ("_featureFlagCache", "_FEATURE_FLAG_TTL_MS",
                "_loadFeatureFlags", "_isFeatureOn"):
        if sym not in c:
            issues.append({"check": "feature_flags", "reason": f"{sym} missing."})
    if "wh_feature_flags" not in c:
        issues.append({"check": "feature_flags", "reason": "wh_feature_flags table reference missing."})
    return issues


def check_browser_support(c: str) -> list[dict]:
    issues = []
    for sym in ("_checkBrowserSupport", "_renderBrowserBanner"):
        if sym not in c:
            issues.append({"check": "browser_support", "reason": f"{sym} missing."})
    for api in ("mediaDevices", "AudioContext", "fetch", "Promise"):
        if "'" + api + "'" not in c:
            issues.append({"check": "browser_support", "reason": f"Capability check for {api} missing."})
    return issues


def check_network(c: str) -> list[dict]:
    issues = []
    for sym in ("_currentNetworkClass", "_shouldUseLitePayload"):
        if sym not in c:
            issues.append({"check": "network", "reason": f"{sym} missing."})
    if "navigator.connection" not in c:
        issues.append({"check": "network", "reason": "navigator.connection not read."})
    if "'slow-2g'" not in c or "'2g'" not in c:
        issues.append({"check": "network", "reason": "Lite-payload network classes missing."})
    return issues


def check_memory(c: str) -> list[dict]:
    if "_checkMemoryPressure" not in c:
        return [{"check": "memory", "reason": "_checkMemoryPressure missing."}]
    issues = []
    if "navigator.deviceMemory" not in c:
        issues.append({"check": "memory", "reason": "navigator.deviceMemory not read."})
    if "performance.memory" not in c:
        issues.append({"check": "memory", "reason": "performance.memory not read."})
    for level in ("'high'", "'medium'", "'low'"):
        if level not in c:
            issues.append({"check": "memory", "reason": f"Pressure level {level} missing."})
    return issues


def check_clock(c: str) -> list[dict]:
    if "_checkClockDrift" not in c:
        return [{"check": "clock", "reason": "_checkClockDrift missing."}]
    if "exceeded" not in c:
        return [{"check": "clock", "reason": "_checkClockDrift doesn't return exceeded flag."}]
    return []


def check_background(c: str) -> list[dict]:
    issues = []
    for sym in ("_shouldPauseForBackground", "_attachVisibilityHandler"):
        if sym not in c:
            issues.append({"check": "background", "reason": f"{sym} missing."})
    if "visibilitychange" not in c:
        issues.append({"check": "background", "reason": "visibilitychange listener not attached."})
    return issues


def check_crash(c: str) -> list[dict]:
    issues = []
    for sym in ("_installCrashHandler", "_getLastCrashSummary", "_clearCrashState"):
        if sym not in c:
            issues.append({"check": "crash", "reason": f"{sym} missing."})
    if "window.onerror" not in c:
        issues.append({"check": "crash", "reason": "window.onerror not installed."})
    return issues


def check_presence(c: str) -> list[dict]:
    issues = []
    for sym in ("_PRESENCE_INTERVAL_MS", "_writePresence",
                "_startPresenceHeartbeat", "_stopPresenceHeartbeat"):
        if sym not in c:
            issues.append({"check": "presence", "reason": f"{sym} missing."})
    if "wh_voice_presence" not in c:
        issues.append({"check": "presence", "reason": "wh_voice_presence table reference missing."})
    return issues


def check_phase_a_wires(c: str) -> list[dict]:
    issues = []
    if "MEMORY PRESSURE" not in c:
        issues.append({"check": "wires", "reason": "T140 MEMORY PRESSURE anchor missing."})
    if "_checkMemoryPressure()" not in c:
        issues.append({"check": "wires", "reason": "T140 _checkMemoryPressure() callsite missing."})
    return issues


CHECK_NAMES = [
    "health", "self_test", "feature_flags", "browser_support", "network",
    "memory", "clock", "background", "crash", "presence",
    "wires",
]
CHECK_LABELS = {
    "health":          "T135 _HEALTH_PING_INTERVAL_MS + ping/schedule/stop + voice-health endpoint",
    "self_test":       "T136 _runSelfTest with affirmation/asset-tag/pii coverage",
    "feature_flags":   "T137 _featureFlagCache + _loadFeatureFlags + _isFeatureOn + wh_feature_flags table",
    "browser_support": "T138 _checkBrowserSupport + _renderBrowserBanner + mediaDevices/AudioContext/fetch/Promise capability checks",
    "network":         "T139 _currentNetworkClass + _shouldUseLitePayload + navigator.connection + 'slow-2g'/'2g' classes",
    "memory":          "T140 _checkMemoryPressure + navigator.deviceMemory + performance.memory + high/medium/low",
    "clock":           "T141 _checkClockDrift with exceeded flag",
    "background":      "T142 _shouldPauseForBackground + _attachVisibilityHandler + visibilitychange listener",
    "crash":           "T143 _installCrashHandler + _getLastCrashSummary + _clearCrashState + window.onerror",
    "presence":        "T144 _PRESENCE_INTERVAL_MS + write/start/stop + wh_voice_presence table",
    "wires":           "PHASE A wires — T140 MEMORY PRESSURE anchor live in perTurnAnchors",
}


def main() -> int:
    print("\033[1m\nAI Companion Operational Excellence Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_health(c)
    issues += check_self_test(c)
    issues += check_feature_flags(c)
    issues += check_browser_support(c)
    issues += check_network(c)
    issues += check_memory(c)
    issues += check_clock(c)
    issues += check_background(c)
    issues += check_crash(c)
    issues += check_presence(c)
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
