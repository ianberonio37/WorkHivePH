"""
AI Companion Trust Deployment Validator (turns #75-#84)
========================================================
Forward-only L0 ratchet for the eighth 10-turn flywheel batch (2026-05-21).
TRUST DEPLOYMENT layer — production safety + collaboration.

  T75  Toxicity guard (de-escalate, never amplify)
  T76  Question shape classifier (drives reply structure)
  T77  Freshness disclosure (last_updated on demand)
  T78  Rate-limit graceful fallback (per-hive cooldown)
  T79  Conversation share link (URL with session id)
  T80  Readback request (TTS replay of prior reply)
  T81  Scope disclosure (capability list)
  T82  Multi-turn correction handler
  T83  Confidence label tier (high/medium/low)
  T84  Crisis escalation extension (workplace violence + self-harm)

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


def check_toxicity(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_detectToxicLanguage", "_TOX_TERMS_SEVERE", "_TOX_TERMS_MILD"):
        if sym not in c:
            issues.append({"check": "toxicity",
                           "reason": f"{sym} missing — toxicity guard incomplete."})
    if "TOXICITY GUARD" not in c:
        issues.append({"check": "toxicity",
                       "reason": "TOXICITY GUARD anchor missing — companion has no instruction to de-escalate."})
    return issues


def check_question_shape(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_classifyQuestionShape" not in c:
        issues.append({"check": "question_shape",
                       "reason": "_classifyQuestionShape missing — shape detector absent."})
    if "QUESTION SHAPE" not in c:
        issues.append({"check": "question_shape",
                       "reason": "QUESTION SHAPE anchor missing — classifier wired but reply structure not steered."})
    # All five shape branches must exist.
    for shape in ("how_to", "data", "opinion", "troubleshoot", "social"):
        if "'" + shape + "'" not in c:
            issues.append({"check": "question_shape",
                           "reason": f"Shape '{shape}' missing from classifier — coverage gap."})
    return issues


def check_freshness(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_isFreshnessRequest" not in c:
        issues.append({"check": "freshness",
                       "reason": "_isFreshnessRequest missing — 'is this fresh?' can't be detected."})
    if "_FRESHNESS_RE" not in c:
        issues.append({"check": "freshness",
                       "reason": "_FRESHNESS_RE missing — detector has no regex."})
    if "FRESHNESS DISCLOSURE" not in c:
        issues.append({"check": "freshness",
                       "reason": "FRESHNESS DISCLOSURE anchor missing — LLM has no instruction to surface last_updated."})
    return issues


def check_rate_limit(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_rateLimitKey", "_setRateLimitCooldown", "_inRateLimitCooldown", "_clearRateLimitCooldown"):
        if sym not in c:
            issues.append({"check": "rate_limit",
                           "reason": f"{sym} missing — rate-limit cooldown incomplete."})
    if "wh_ratelimit_until_" not in c:
        issues.append({"check": "rate_limit",
                       "reason": "localStorage key prefix wh_ratelimit_until_ missing — cooldown doesn't persist."})
    return issues


def check_share(c: str) -> list[dict]:
    issues: list[dict] = []
    for sym in ("_isShareRequest", "_buildShareLink", "_SHARE_RE"):
        if sym not in c:
            issues.append({"check": "share",
                           "reason": f"{sym} missing — share-link path incomplete."})
    if "SHARE LINK" not in c:
        issues.append({"check": "share",
                       "reason": "SHARE LINK anchor missing — link built but LLM has no instruction to surface."})
    if "/voice-journal.html#session=" not in c:
        issues.append({"check": "share",
                       "reason": "Share link doesn't target /voice-journal.html#session= — receiving surface won't pick up the session."})
    return issues


def check_readback(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_isReadbackRequest" not in c:
        issues.append({"check": "readback",
                       "reason": "_isReadbackRequest missing — TTS replay can't be triggered."})
    if "_READBACK_RE" not in c:
        issues.append({"check": "readback",
                       "reason": "_READBACK_RE missing — detector has no regex."})
    if "READBACK" not in c:
        issues.append({"check": "readback",
                       "reason": "READBACK anchor missing — LLM has no instruction to replay verbatim."})
    return issues


def check_scope(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_isScopeQuery" not in c:
        issues.append({"check": "scope",
                       "reason": "_isScopeQuery missing — 'what can you do' can't be detected."})
    if "_SCOPE_RE" not in c:
        issues.append({"check": "scope",
                       "reason": "_SCOPE_RE missing — detector has no regex."})
    if "SCOPE DISCLOSURE" not in c:
        issues.append({"check": "scope",
                       "reason": "SCOPE DISCLOSURE anchor missing — companion would guess at its capabilities."})
    return issues


def check_correction(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_isCorrection" not in c:
        issues.append({"check": "correction",
                       "reason": "_isCorrection missing — 'no, I meant X' can't be detected as correction."})
    if "_CORRECTION_RE" not in c:
        issues.append({"check": "correction",
                       "reason": "_CORRECTION_RE missing — detector has no regex."})
    if "CORRECTION" not in c:
        issues.append({"check": "correction",
                       "reason": "CORRECTION anchor missing — LLM has no instruction to redo answer with new info."})
    return issues


def check_confidence_label(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_confidenceLabel" not in c:
        issues.append({"check": "confidence_label",
                       "reason": "_confidenceLabel missing — confidence tier calculator absent."})
    # Must cover high / medium / low.
    for label in ("'high'", "'medium'", "'low'"):
        if label not in c:
            issues.append({"check": "confidence_label",
                           "reason": f"Label {label} missing from _confidenceLabel — tier coverage gap."})
    return issues


def check_crisis_extension(c: str) -> list[dict]:
    issues: list[dict] = []
    if "_detectCrisisEscalation" not in c:
        issues.append({"check": "crisis_extension",
                       "reason": "_detectCrisisEscalation missing — extended crisis routing absent."})
    if "workplace_violence" not in c:
        issues.append({"check": "crisis_extension",
                       "reason": "workplace_violence kind missing — extension doesn't cover the second crisis class."})
    if "self_harm" not in c:
        issues.append({"check": "crisis_extension",
                       "reason": "self_harm kind missing — extension regressed below T4 baseline."})
    if "CRISIS" not in c or ("Safety Officer" not in c and "safety officer" not in c.lower()):
        issues.append({"check": "crisis_extension",
                       "reason": "CRISIS anchor missing OR doesn't route workplace_violence to Safety Officer / HR."})
    return issues


CHECK_NAMES = [
    "toxicity", "question_shape", "freshness", "rate_limit", "share",
    "readback", "scope", "correction", "confidence_label", "crisis_extension",
]

CHECK_LABELS = {
    "toxicity":          "T75 _detectToxicLanguage + _TOX_TERMS_SEVERE/_MILD + TOXICITY GUARD anchor",
    "question_shape":    "T76 _classifyQuestionShape (how_to/data/opinion/troubleshoot/social) + QUESTION SHAPE anchor",
    "freshness":         "T77 _isFreshnessRequest + _FRESHNESS_RE + FRESHNESS DISCLOSURE anchor",
    "rate_limit":        "T78 _rateLimitKey + set/in/clear RateLimitCooldown + wh_ratelimit_until_ key",
    "share":             "T79 _isShareRequest + _buildShareLink + _SHARE_RE + SHARE LINK anchor + /voice-journal.html#session= target",
    "readback":          "T80 _isReadbackRequest + _READBACK_RE + READBACK anchor",
    "scope":             "T81 _isScopeQuery + _SCOPE_RE + SCOPE DISCLOSURE anchor",
    "correction":        "T82 _isCorrection + _CORRECTION_RE + CORRECTION anchor",
    "confidence_label":  "T83 _confidenceLabel + high/medium/low tiers",
    "crisis_extension":  "T84 _detectCrisisEscalation + self_harm + workplace_violence kinds + CRISIS anchor with Safety Officer routing",
}


def main() -> int:
    print("\033[1m\nAI Companion Trust Deployment Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_toxicity(c)
    issues += check_question_shape(c)
    issues += check_freshness(c)
    issues += check_rate_limit(c)
    issues += check_share(c)
    issues += check_readback(c)
    issues += check_scope(c)
    issues += check_correction(c)
    issues += check_confidence_label(c)
    issues += check_crisis_extension(c)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
