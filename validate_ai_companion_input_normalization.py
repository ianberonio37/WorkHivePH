"""
AI Companion Input Normalization + Onboarding Validator (turns #85-#94)
========================================================================
Forward-only L0 ratchet for the ninth 10-turn flywheel batch (2026-05-21).

  T85  Numeric precision rule
  T86  Asset tag normalization (STT -> canonical)
  T87  Time-range normalization (this week -> ISO span)
  T88  Acknowledgement style preference (terse/warm)
  T89  Forbidden-topic redirect (competitors, office politics)
  T90  Noise-floor classifier (mic env)
  T91  Conversation pin / star
  T92  Help command shortcut
  T93  Multi-language KPI label
  T94  New-worker onboarding cue

10-layer audit.
"""

from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

VOICE_HANDLER_JS = "voice-handler.js"


def _read() -> str:
    return read_file(VOICE_HANDLER_JS) or ""


def check_precision(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_formatKpi" not in c:
        issues.append({"check": "precision", "reason": "_formatKpi missing — KPI formatter absent."})
    if "PRECISION RULE" not in c:
        issues.append({"check": "precision", "reason": "PRECISION RULE anchor missing — LLM has no instruction on unit/precision."})
    return issues


def check_asset_tag(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_normalizeAssetTag", "_DIGIT_WORDS", "_LETTER_WORDS"):
        if sym not in c:
            issues.append({"check": "asset_tag", "reason": f"{sym} missing — asset-tag normalization incomplete."})
    if "ASSET TAG NORMALIZED" not in c:
        issues.append({"check": "asset_tag", "reason": "ASSET TAG NORMALIZED anchor missing — normalized tag built but never reaches LLM."})
    return issues


def check_time_range(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_normalizeTimeRange" not in c:
        issues.append({"check": "time_range", "reason": "_normalizeTimeRange missing — phrase-to-ISO span absent."})
    if "TIME RANGE NORMALIZED" not in c:
        issues.append({"check": "time_range", "reason": "TIME RANGE NORMALIZED anchor missing — normalized span never surfaced."})
    # Must cover common spans.
    for phrase in ("this\\s+week", "yesterday|kahapon", "this\\s+month"):
        if phrase not in c:
            issues.append({"check": "time_range", "reason": f"Phrase pattern '{phrase}' missing — coverage gap."})
    return issues


def check_ack_style(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_ACK_STYLE_KEY", "_getAckStyle", "_setAckStyle",
                "_detectAckStyleToggle", "_ACK_TERSE_RE", "_ACK_WARM_RE"):
        if sym not in c:
            issues.append({"check": "ack_style", "reason": f"{sym} missing — ack-style toggle incomplete."})
    if "ACK STYLE" not in c:
        issues.append({"check": "ack_style", "reason": "ACK STYLE anchor missing — pref persists but LLM doesn't read it."})
    if "wh_voice_ack_style" not in c:
        issues.append({"check": "ack_style", "reason": "localStorage key wh_voice_ack_style missing."})
    return issues


def check_forbidden(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_detectForbiddenTopic", "_COMPETITORS_RE", "_POLITICS_RE"):
        if sym not in c:
            issues.append({"check": "forbidden", "reason": f"{sym} missing — forbidden-topic redirect incomplete."})
    if "FORBIDDEN" not in c:
        issues.append({"check": "forbidden", "reason": "FORBIDDEN anchor missing — detector wired but LLM has no redirect instruction."})
    return issues


def check_mic_env(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_classifyMicEnv" not in c:
        issues.append({"check": "mic_env", "reason": "_classifyMicEnv missing — noise-floor classifier absent."})
    for label in ("'quiet'", "'normal'", "'noisy'", "'spotty'"):
        if label not in c:
            issues.append({"check": "mic_env", "reason": f"Label {label} missing from _classifyMicEnv coverage."})
    return issues


def check_pin(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_PIN_KEY_PREFIX", "_pinTurn", "_getPinnedTurns", "_isPinRequest", "_PIN_RE", "_PIN_MAX"):
        if sym not in c:
            issues.append({"check": "pin", "reason": f"{sym} missing — conversation-pin incomplete."})
    if "PIN " not in c:
        issues.append({"check": "pin", "reason": "PIN anchor missing — pin recorded but no LLM acknowledgement."})
    if "wh_voice_pinned_" not in c:
        issues.append({"check": "pin", "reason": "localStorage key prefix wh_voice_pinned_ missing — pins don't persist."})
    return issues


def check_help(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_isHelpCommand" not in c:
        issues.append({"check": "help", "reason": "_isHelpCommand missing — help shortcut absent."})
    if "_HELP_RE" not in c:
        issues.append({"check": "help", "reason": "_HELP_RE missing — regex absent."})
    if "HELP " not in c:
        issues.append({"check": "help", "reason": "HELP anchor missing — detector wired but LLM has no mini-tour instruction."})
    return issues


def check_kpi_translation(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_translateKpiLabel" not in c:
        issues.append({"check": "kpi_translation", "reason": "_translateKpiLabel missing — multi-language KPI labels absent."})
    if "_KPI_LABEL_DICT" not in c:
        issues.append({"check": "kpi_translation", "reason": "_KPI_LABEL_DICT missing — translation dictionary absent."})
    # Required KPIs.
    for metric in ("mtbf", "mttr", "oee"):
        if "'" + metric + "':" not in c:
            issues.append({"check": "kpi_translation", "reason": f"Metric '{metric}' missing from _KPI_LABEL_DICT."})
    return issues


def check_onboarding(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_isFirstTimeWorker", "_firstTimeWelcomeLine"):
        if sym not in c:
            issues.append({"check": "onboarding", "reason": f"{sym} missing — new-worker onboarding incomplete."})
    # Welcome must mention three sample commands (overdue / log / OEE) — keeps the cue concrete.
    if "overdue" not in c.lower():
        issues.append({"check": "onboarding", "reason": "Welcome line missing 'overdue' sample — onboarding cue not concrete."})
    return issues


CHECK_NAMES = [
    "precision", "asset_tag", "time_range", "ack_style", "forbidden",
    "mic_env", "pin", "help", "kpi_translation", "onboarding",
]

CHECK_LABELS = {
    "precision":       "T85 _formatKpi + PRECISION RULE anchor",
    "asset_tag":       "T86 _normalizeAssetTag + _DIGIT_WORDS + _LETTER_WORDS + ASSET TAG NORMALIZED anchor",
    "time_range":      "T87 _normalizeTimeRange + this-week/yesterday/this-month coverage + TIME RANGE NORMALIZED anchor",
    "ack_style":       "T88 _ACK_STYLE_KEY + get/set/detect helpers + ACK STYLE anchor + wh_voice_ack_style key",
    "forbidden":       "T89 _detectForbiddenTopic + _COMPETITORS_RE + _POLITICS_RE + FORBIDDEN anchor",
    "mic_env":         "T90 _classifyMicEnv with quiet/normal/spotty/noisy labels",
    "pin":             "T91 _PIN_KEY_PREFIX + pinTurn/getPinnedTurns/isPinRequest/_PIN_RE/_PIN_MAX + PIN anchor + wh_voice_pinned_ key",
    "help":            "T92 _isHelpCommand + _HELP_RE + HELP anchor",
    "kpi_translation": "T93 _translateKpiLabel + _KPI_LABEL_DICT with mtbf/mttr/oee",
    "onboarding":      "T94 _isFirstTimeWorker + _firstTimeWelcomeLine + sample commands (overdue)",
}


def main() -> int:
    print("\033[1m\nAI Companion Input Normalization + Onboarding Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_precision(c)
    issues += check_asset_tag(c)
    issues += check_time_range(c)
    issues += check_ack_style(c)
    issues += check_forbidden(c)
    issues += check_mic_env(c)
    issues += check_pin(c)
    issues += check_help(c)
    issues += check_kpi_translation(c)
    issues += check_onboarding(c)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
