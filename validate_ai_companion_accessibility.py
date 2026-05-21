"""
AI Companion Multi-Modal + Accessibility Validator (turns #125-#134)
=====================================================================
Forward-only L0 ratchet for the thirteenth 10-turn flywheel batch (2026-05-21).

  T125  Image capture (camera still)
  T126  File attachment (image/PDF)
  T127  Reduced motion accessibility
  T128  Screen-reader aria-live region
  T129  Keyboard navigation
  T130  Color-blind safe palette
  T131  Large-text mode
  T132  Haptic feedback patterns
  T133  Voice-only mode
  T134  Live captions

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


def check_image(c: str) -> list[dict]:
    issues = []
    if "_captureImageStill" not in c:
        issues.append({"check": "image", "reason": "_captureImageStill missing."})
    if "getUserMedia" not in c:
        issues.append({"check": "image", "reason": "getUserMedia not referenced — camera capture won't work."})
    if "'no_media_devices'" not in c:
        issues.append({"check": "image", "reason": "no_media_devices fallback blocker missing."})
    return issues


def check_file(c: str) -> list[dict]:
    issues = []
    if "_openFileAttachment" not in c:
        issues.append({"check": "file", "reason": "_openFileAttachment missing."})
    if "'too_large'" not in c:
        issues.append({"check": "file", "reason": "too_large blocker missing (size limit not enforced)."})
    if "readAsDataURL" not in c:
        issues.append({"check": "file", "reason": "FileReader.readAsDataURL not used — base64 not produced."})
    return issues


def check_reduced_motion(c: str) -> list[dict]:
    issues = []
    for sym in ("_REDUCED_MOTION_KEY", "_isReducedMotionRequested", "_setReducedMotion"):
        if sym not in c:
            issues.append({"check": "reduced_motion", "reason": f"{sym} missing."})
    if "prefers-reduced-motion" not in c:
        issues.append({"check": "reduced_motion", "reason": "prefers-reduced-motion media query not honoured."})
    if "wh_voice_reduced_motion" not in c:
        issues.append({"check": "reduced_motion", "reason": "localStorage key wh_voice_reduced_motion missing."})
    return issues


def check_aria_live(c: str) -> list[dict]:
    issues = []
    for sym in ("_ensureAriaLiveRegion", "_announceForScreenReader"):
        if sym not in c:
            issues.append({"check": "aria_live", "reason": f"{sym} missing."})
    if "aria-live" not in c:
        issues.append({"check": "aria_live", "reason": "aria-live attribute not set."})
    if "wh-voice-aria-live" not in c:
        issues.append({"check": "aria_live", "reason": "aria-live region id wh-voice-aria-live missing."})
    return issues


def check_keyboard(c: str) -> list[dict]:
    issues = []
    if "_KEY_ACTIONS" not in c:
        issues.append({"check": "keyboard", "reason": "_KEY_ACTIONS map missing."})
    if "_resolveKeyAction" not in c:
        issues.append({"check": "keyboard", "reason": "_resolveKeyAction missing."})
    for key in ("'Escape'", "'Space'", "'Enter'"):
        if key not in c:
            issues.append({"check": "keyboard", "reason": f"Key {key} not bound."})
    if "_isEditableTarget" not in c:
        issues.append({"check": "keyboard", "reason": "_isEditableTarget guard missing — Space would steal input focus."})
    return issues


def check_color_blind(c: str) -> list[dict]:
    issues = []
    for sym in ("_CB_PALETTE_KEY", "_PALETTE_DEFAULT", "_PALETTE_CB_SAFE",
                "_isColorBlindMode", "_setColorBlindMode", "_currentPalette"):
        if sym not in c:
            issues.append({"check": "color_blind", "reason": f"{sym} missing."})
    if "wh_voice_cb_palette" not in c:
        issues.append({"check": "color_blind", "reason": "localStorage key wh_voice_cb_palette missing."})
    for severity in ("critical:", "high:", "medium:", "low:", "info:"):
        if severity not in c:
            issues.append({"check": "color_blind", "reason": f"Palette tier {severity} missing."})
    return issues


def check_large_text(c: str) -> list[dict]:
    issues = []
    for sym in ("_LARGE_TEXT_KEY", "_isLargeTextMode", "_setLargeTextMode"):
        if sym not in c:
            issues.append({"check": "large_text", "reason": f"{sym} missing."})
    if "wh_voice_large_text" not in c:
        issues.append({"check": "large_text", "reason": "localStorage key wh_voice_large_text missing."})
    if "data-text-size" not in c:
        issues.append({"check": "large_text", "reason": "data-text-size attribute not set."})
    return issues


def check_haptic(c: str) -> list[dict]:
    issues = []
    if "_HAPTIC_PATTERNS" not in c:
        issues.append({"check": "haptic", "reason": "_HAPTIC_PATTERNS missing."})
    if "_hapticPulse" not in c:
        issues.append({"check": "haptic", "reason": "_hapticPulse missing."})
    for kind in ("confirm:", "success:", "warning:", "critical:"):
        if kind not in c:
            issues.append({"check": "haptic", "reason": f"Pattern {kind} missing."})
    if "navigator.vibrate" not in c:
        issues.append({"check": "haptic", "reason": "navigator.vibrate not invoked."})
    return issues


def check_voice_only(c: str) -> list[dict]:
    issues = []
    for sym in ("_VOICE_ONLY_KEY", "_isVoiceOnlyMode", "_setVoiceOnlyMode",
                "_detectVoiceOnlyToggle", "_VOICE_ONLY_TOGGLE_RE"):
        if sym not in c:
            issues.append({"check": "voice_only", "reason": f"{sym} missing."})
    if "wh_voice_only_mode" not in c:
        issues.append({"check": "voice_only", "reason": "localStorage key wh_voice_only_mode missing."})
    return issues


def check_captions(c: str) -> list[dict]:
    issues = []
    for sym in ("_CAPTIONS_KEY", "_isCaptionsOn", "_setCaptionsOn", "_renderCaption"):
        if sym not in c:
            issues.append({"check": "captions", "reason": f"{sym} missing."})
    if "wh_voice_captions" not in c:
        issues.append({"check": "captions", "reason": "localStorage key wh_voice_captions missing."})
    if "wh-voice-caption-bar" not in c:
        issues.append({"check": "captions", "reason": "Caption DOM id missing — visible captions can't render."})
    return issues


def check_phase_a_wires(c: str) -> list[dict]:
    issues = []
    if "VOICE-ONLY TOGGLE" not in c:
        issues.append({"check": "wires", "reason": "T133 VOICE-ONLY TOGGLE anchor missing."})
    if "_detectVoiceOnlyToggle(transcript)" not in c:
        issues.append({"check": "wires", "reason": "T133 _detectVoiceOnlyToggle(transcript) callsite missing."})
    return issues


CHECK_NAMES = [
    "image", "file", "reduced_motion", "aria_live", "keyboard",
    "color_blind", "large_text", "haptic", "voice_only", "captions",
    "wires",
]
CHECK_LABELS = {
    "image":          "T125 _captureImageStill + getUserMedia + no_media_devices fallback",
    "file":           "T126 _openFileAttachment + too_large blocker + readAsDataURL",
    "reduced_motion": "T127 _REDUCED_MOTION_KEY + is/set helpers + prefers-reduced-motion media query + wh_voice_reduced_motion key",
    "aria_live":      "T128 _ensureAriaLiveRegion + _announceForScreenReader + aria-live attr + wh-voice-aria-live id",
    "keyboard":       "T129 _KEY_ACTIONS + _resolveKeyAction + Escape/Space/Enter bindings + _isEditableTarget guard",
    "color_blind":    "T130 _CB_PALETTE_KEY + _PALETTE_DEFAULT + _PALETTE_CB_SAFE + critical/high/medium/low/info tiers",
    "large_text":     "T131 _LARGE_TEXT_KEY + is/set helpers + data-text-size attribute",
    "haptic":         "T132 _HAPTIC_PATTERNS (confirm/success/warning/critical) + _hapticPulse + navigator.vibrate",
    "voice_only":     "T133 _VOICE_ONLY_KEY + is/set/detect helpers + _VOICE_ONLY_TOGGLE_RE + wh_voice_only_mode key",
    "captions":       "T134 _CAPTIONS_KEY + is/set helpers + _renderCaption + wh-voice-caption-bar DOM id",
    "wires":          "PHASE A wires — T133 VOICE-ONLY TOGGLE anchor live in perTurnAnchors",
}


def main() -> int:
    print("\033[1m\nAI Companion Multi-Modal + Accessibility Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_image(c)
    issues += check_file(c)
    issues += check_reduced_motion(c)
    issues += check_aria_live(c)
    issues += check_keyboard(c)
    issues += check_color_blind(c)
    issues += check_large_text(c)
    issues += check_haptic(c)
    issues += check_voice_only(c)
    issues += check_captions(c)
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
