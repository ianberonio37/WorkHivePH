"""
AI Companion Workflow + Personalization Validator (turns #55-#64)
==================================================================
Forward-only L0 ratchet for the sixth 10-turn flywheel batch (2026-05-21).
Covers PROACTIVE behaviour, MATURITY-AWARE gating, FINE-GRAINED MEMORY,
WORKFLOW EFFICIENCY (action replay, action queue, timer), and
PERSONALIZATION (language pref, brevity pref).

  T55  Proactive companion turn (open() accepts an alert payload)
  T56  Maturity-stair gating (<2 hive → no predictive promises)
  T57  Per-slot expiry windows (asset_tag 60m, time_window 2h, etc.)
  T58  Action replay ("same fix on P-205")
  T59  Language opt-in (tagalog / english / cebuano)
  T60  Brevity preference (brief / full)
  T61  Timer follow-up ("remind me in 20 min")
  T62  URL-context pre-fill (?asset=P-203 → context_slots.asset_tag)
  T63  Mic quality meter (low-volume warning)
  T64  Action queue ("log entry then start PM")

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


def check_proactive_open(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_selectProactiveAlertForSpeak" not in c:
        issues.append({"check": "proactive_open",
                       "reason": "_selectProactiveAlertForSpeak missing — companion can't pick the highest-severity unacknowledged alert."})
    if "function open(initOpts)" not in c:
        issues.append({"check": "proactive_open",
                       "reason": "open() signature does not accept initOpts — callers can't pass a proactive alert payload."})
    if "initOpts && initOpts.alert" not in c:
        issues.append({"check": "proactive_open",
                       "reason": "open() doesn't branch on initOpts.alert — proactive lines never render."})
    return issues


def check_maturity_gating(c: str) -> list[dict]:
    if "MATURITY GATING" not in c:
        return [{"check": "maturity_gating",
                 "reason": "MATURITY GATING anchor missing — Stair 0/1 hives still get predictive promises."}]
    if "_readHiveMaturityStair" not in c:
        return [{"check": "maturity_gating",
                 "reason": "_readHiveMaturityStair missing — anchor has no source value to gate on."}]
    if "wh_hive_maturity_stair" not in c:
        return [{"check": "maturity_gating",
                 "reason": "Stair value never read from localStorage key wh_hive_maturity_stair — gating is dead code."}]
    return []


def check_per_slot_expiry(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_pruneStaleSlots" not in c:
        issues.append({"check": "per_slot_expiry",
                       "reason": "_pruneStaleSlots missing — slot-level TTL can't be enforced (T6 only does session-level)."})
    if "_SLOT_TTL_MS" not in c:
        issues.append({"check": "per_slot_expiry",
                       "reason": "_SLOT_TTL_MS map missing — per-slot TTLs not declared."})
    # Required slot TTLs.
    for slot in ("asset_tag", "machine_status", "time_window"):
        if slot + ":" not in c.replace(" ", "") and slot + ' :' not in c:
            # Fallback: look for the slot name in the TTL map body specifically.
            m = re.search(r"_SLOT_TTL_MS\s*=\s*\{([^}]+)\}", c, re.DOTALL)
            if m and slot not in m.group(1):
                issues.append({"check": "per_slot_expiry",
                               "reason": f"_SLOT_TTL_MS missing slot '{slot}' — that slot uses session-default which may not match the worker's expectations."})
    if "_pruneStaleSlots(rawSlots" not in c:
        issues.append({"check": "per_slot_expiry",
                       "reason": "Call site doesn't invoke _pruneStaleSlots(rawSlots, dialogState.updated_at) — helper exists but never runs."})
    return issues


def check_action_replay(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_detectActionReplay", "_REPLAY_RE", "_lastConfirmedAction", "_stashConfirmedAction"):
        if sym not in c:
            issues.append({"check": "action_replay",
                           "reason": f"{sym} missing — 'same fix on P-205' can't replay the prior action shape."})
    if "ACTION REPLAY" not in c:
        issues.append({"check": "action_replay",
                       "reason": "ACTION REPLAY anchor missing — detector exists but LLM has no instruction to substitute the asset."})
    return issues


def check_language_pref(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_detectLanguagePref", "_setLanguagePref", "_getLanguagePref", "_LANG_OPT_RE"):
        if sym not in c:
            issues.append({"check": "language_pref",
                           "reason": f"{sym} missing — language opt-in doesn't persist or load."})
    if "LANGUAGE PREFERENCE" not in c:
        issues.append({"check": "language_pref",
                       "reason": "LANGUAGE PREFERENCE anchor missing — pref stored but never reaches the LLM."})
    if "wh_voice_lang_pref" not in c:
        issues.append({"check": "language_pref",
                       "reason": "localStorage key wh_voice_lang_pref missing — pref doesn't survive page reload."})
    return issues


def check_brevity_pref(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_detectBrevityToggle", "_setBrevityPref", "_getBrevityPref", "_BREVITY_ON_RE", "_BREVITY_OFF_RE"):
        if sym not in c:
            issues.append({"check": "brevity_pref",
                           "reason": f"{sym} missing — brevity pref doesn't toggle on 'shorter' / 'be brief'."})
    if "BREVITY MODE" not in c:
        issues.append({"check": "brevity_pref",
                       "reason": "BREVITY MODE anchor missing — pref stored but never caps the reply length."})
    return []


def check_timer(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_detectTimerRequest", "_scheduleTimer", "_TIMER_LIST_MAX", "_TIMER_RE"):
        if sym not in c:
            issues.append({"check": "timer",
                           "reason": f"{sym} missing — 'remind me in 20 min' doesn't schedule a callback."})
    if "TIMER SCHEDULED" not in c:
        issues.append({"check": "timer",
                       "reason": "TIMER SCHEDULED anchor missing — scheduled but LLM has no instruction to acknowledge."})
    return issues


def check_url_prefill(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_readUrlAssetParam" not in c:
        issues.append({"check": "url_prefill",
                       "reason": "_readUrlAssetParam missing — voice opened from ?asset=P-203 doesn't seed context_slots."})
    if "context_slots.asset_tag = urlAsset" not in c.replace(" ", "") and \
       "context_slots.asset_tag\\s*=\\s*urlAsset" not in c:
        # accept formatting variants
        if not re.search(r"context_slots\.asset_tag\s*=\s*urlAsset", c):
            issues.append({"check": "url_prefill",
                           "reason": "Call site doesn't assign context_slots.asset_tag = urlAsset — URL param read but never injected."})
    return issues


def check_mic_quality(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_attachMicQualityMeter" not in c:
        issues.append({"check": "mic_quality",
                       "reason": "_attachMicQualityMeter missing — no audio-level monitor on the live stream."})
    if "AnalyserNode" not in c and "createAnalyser" not in c:
        issues.append({"check": "mic_quality",
                       "reason": "Meter doesn't use AudioContext.createAnalyser — there's no actual level monitoring."})
    if "_micQualityMeter" not in c:
        issues.append({"check": "mic_quality",
                       "reason": "Module slot _micQualityMeter missing — meter can't be torn down on close."})
    return issues


def check_action_queue(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_parseActionQueue" not in c:
        issues.append({"check": "action_queue",
                       "reason": "_parseActionQueue missing — 'log entry then start PM' parses as one step."})
    if "ACTION QUEUE" not in c:
        issues.append({"check": "action_queue",
                       "reason": "ACTION QUEUE anchor missing — parser splits but LLM has no instruction to enumerate."})
    if "_ACTION_SPLIT_RE" not in c:
        issues.append({"check": "action_queue",
                       "reason": "_ACTION_SPLIT_RE missing — no separator regex to drive the split."})
    return issues


CHECK_NAMES = [
    "proactive_open", "maturity_gating", "per_slot_expiry", "action_replay",
    "language_pref", "brevity_pref", "timer", "url_prefill",
    "mic_quality", "action_queue",
]

CHECK_LABELS = {
    "proactive_open":   "T55 _selectProactiveAlertForSpeak + open(initOpts) accepts alert payload",
    "maturity_gating":  "T56 MATURITY GATING anchor + _readHiveMaturityStair + Stair <2 branch",
    "per_slot_expiry":  "T57 _pruneStaleSlots + _SLOT_TTL_MS (asset_tag / machine_status / time_window) + call-site invoke",
    "action_replay":    "T58 _detectActionReplay + _lastConfirmedAction snapshot + ACTION REPLAY anchor",
    "language_pref":    "T59 _detectLanguagePref + persist to wh_voice_lang_pref + LANGUAGE PREFERENCE anchor",
    "brevity_pref":     "T60 _detectBrevityToggle (on/off) + BREVITY MODE anchor",
    "timer":            "T61 _detectTimerRequest + _scheduleTimer + bounded timer list + TIMER SCHEDULED anchor",
    "url_prefill":      "T62 _readUrlAssetParam + context_slots.asset_tag = urlAsset injection",
    "mic_quality":      "T63 _attachMicQualityMeter (AnalyserNode) + module slot _micQualityMeter",
    "action_queue":     "T64 _parseActionQueue + _ACTION_SPLIT_RE + ACTION QUEUE anchor",
}


def main() -> int:
    print("\033[1m\nAI Companion Workflow + Personalization Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_proactive_open(c)
    issues += check_maturity_gating(c)
    issues += check_per_slot_expiry(c)
    issues += check_action_replay(c)
    issues += check_language_pref(c)
    issues += check_brevity_pref(c)
    issues += check_timer(c)
    issues += check_url_prefill(c)
    issues += check_mic_quality(c)
    issues += check_action_queue(c)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
