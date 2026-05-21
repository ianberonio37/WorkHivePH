"""
AI Companion Compliance + Data Governance Validator (turns #115-#124)
======================================================================
Forward-only L0 ratchet for the twelfth 10-turn flywheel batch (2026-05-21).

  T115  PII scrubber (phone, email, ID)
  T116  Consent capture (PH Data Privacy Act)
  T117  Data retention policy enforcement
  T118  Right-to-erasure
  T119  Audit export CSV
  T120  Suspicious activity flag
  T121  AI disclosure policy
  T122  Locale-aware date format
  T123  Per-hive monthly cost cap
  T124  Voice drift advisory (NOT auth)

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


def check_pii(c: str) -> list[dict]:
    if "_scrubPii" not in c:
        return [{"check": "pii", "reason": "_scrubPii missing."}]
    issues = []
    for marker in ("[PHONE]", "[EMAIL]", "[ID]"):
        if marker not in c:
            issues.append({"check": "pii", "reason": f"Scrub marker {marker} missing — coverage gap."})
    return issues


def check_consent(c: str) -> list[dict]:
    issues = []
    for sym in ("_CONSENT_KEY", "_hasConsent", "_captureConsent", "_revokeConsent",
                "_detectConsentChange", "_CONSENT_GRANT_RE", "_CONSENT_REVOKE_RE"):
        if sym not in c:
            issues.append({"check": "consent", "reason": f"{sym} missing."})
    if "wh_voice_consent" not in c:
        issues.append({"check": "consent", "reason": "localStorage key wh_voice_consent missing."})
    return issues


def check_retention(c: str) -> list[dict]:
    issues = []
    for sym in ("_retentionCutoffIso", "_enforceRetention"):
        if sym not in c:
            issues.append({"check": "retention", "reason": f"{sym} missing."})
    return issues


def check_erasure(c: str) -> list[dict]:
    issues = []
    for sym in ("_isErasureRequest", "_ERASURE_RE", "_executeErasure"):
        if sym not in c:
            issues.append({"check": "erasure", "reason": f"{sym} missing."})
    if "right_to_erasure" not in c:
        issues.append({"check": "erasure", "reason": "right_to_erasure event_type not logged."})
    return issues


def check_audit_export(c: str) -> list[dict]:
    issues = []
    if "_buildAuditCsv" not in c:
        issues.append({"check": "audit_export", "reason": "_buildAuditCsv missing."})
    if "_toCsvRow" not in c:
        issues.append({"check": "audit_export", "reason": "_toCsvRow missing."})
    return issues


def check_suspicious(c: str) -> list[dict]:
    issues = []
    if "_detectSuspiciousActivity" not in c:
        issues.append({"check": "suspicious", "reason": "_detectSuspiciousActivity missing."})
    for kind in ("'rapid_fire'", "'off_hours_bulk'"):
        if kind not in c:
            issues.append({"check": "suspicious", "reason": f"Kind {kind} missing."})
    return issues


def check_ai_disclosure(c: str) -> list[dict]:
    issues = []
    for sym in ("_AI_DISCLOSURE_FLAG_KEY", "_setAiDisclosurePolicy",
                "_needsAiDisclosure", "_markAiDisclosureShown", "_aiDisclosureLine"):
        if sym not in c:
            issues.append({"check": "ai_disclosure", "reason": f"{sym} missing."})
    if "wh_voice_ai_disclosure_policy" not in c:
        issues.append({"check": "ai_disclosure", "reason": "localStorage key wh_voice_ai_disclosure_policy missing."})
    return issues


def check_locale_date(c: str) -> list[dict]:
    if "_formatLocaleDate" not in c:
        return [{"check": "locale_date", "reason": "_formatLocaleDate missing."}]
    return []


def check_cost_cap(c: str) -> list[dict]:
    issues = []
    for sym in ("_getMonthlyCost", "_exceededCostCap"):
        if sym not in c:
            issues.append({"check": "cost_cap", "reason": f"{sym} missing."})
    if "ai_cost_log" not in c:
        issues.append({"check": "cost_cap", "reason": "ai_cost_log table reference missing."})
    return issues


def check_voice_drift(c: str) -> list[dict]:
    issues = []
    for sym in ("_DRIFT_KEY_PREFIX", "_signatureKey", "_recordVoiceSignature", "_voiceSignatureDrift"):
        if sym not in c:
            issues.append({"check": "voice_drift", "reason": f"{sym} missing."})
    if "wh_voice_signature_" not in c:
        issues.append({"check": "voice_drift", "reason": "localStorage key prefix wh_voice_signature_ missing."})
    # Belt-and-suspenders: must say ADVISORY ONLY in the surrounding comments
    if "ADVISORY ONLY" not in c.upper():
        issues.append({"check": "voice_drift", "reason": "Voice drift must declare ADVISORY ONLY — never an auth signal."})
    return issues


def check_phase_a_wires(c: str) -> list[dict]:
    issues = []
    pairs = [
        ("PII SCRUBBED",        "_scrubPii(transcript)",            "T115 PII SCRUBBED anchor"),
        ("CONSENT CHANGE",      "_detectConsentChange(transcript)", "T116 CONSENT CHANGE anchor"),
        ("ERASURE REQUEST",     "_isErasureRequest(transcript)",    "T118 ERASURE REQUEST anchor"),
        ("SUSPICIOUS ACTIVITY", "_detectSuspiciousActivity(ctx.worker_name)", "T120 SUSPICIOUS ACTIVITY anchor"),
    ]
    for anchor, callsite, label in pairs:
        if anchor not in c:
            issues.append({"check": "wires", "reason": f"{label} anchor '{anchor}' missing."})
        if callsite not in c:
            issues.append({"check": "wires", "reason": f"{label} call '{callsite}' missing."})
    return issues


CHECK_NAMES = [
    "pii", "consent", "retention", "erasure", "audit_export",
    "suspicious", "ai_disclosure", "locale_date", "cost_cap", "voice_drift",
    "wires",
]
CHECK_LABELS = {
    "pii":           "T115 _scrubPii + [PHONE]/[EMAIL]/[ID] markers",
    "consent":       "T116 consent get/set/revoke/detect helpers + wh_voice_consent key + grant/revoke regex",
    "retention":     "T117 _retentionCutoffIso + _enforceRetention",
    "erasure":       "T118 _isErasureRequest + _ERASURE_RE + _executeErasure + right_to_erasure event",
    "audit_export":  "T119 _buildAuditCsv + _toCsvRow",
    "suspicious":    "T120 _detectSuspiciousActivity + rapid_fire + off_hours_bulk kinds",
    "ai_disclosure": "T121 policy flag + needs/mark/line helpers + wh_voice_ai_disclosure_policy key",
    "locale_date":   "T122 _formatLocaleDate",
    "cost_cap":      "T123 _getMonthlyCost + _exceededCostCap + ai_cost_log reference",
    "voice_drift":   "T124 signature record + drift detect + wh_voice_signature_ key + ADVISORY ONLY declaration",
    "wires":         "PHASE A wires — T115/T116/T118/T120 anchors live in perTurnAnchors",
}


def main() -> int:
    print("\033[1m\nAI Companion Compliance + Data Governance Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_pii(c)
    issues += check_consent(c)
    issues += check_retention(c)
    issues += check_erasure(c)
    issues += check_audit_export(c)
    issues += check_suspicious(c)
    issues += check_ai_disclosure(c)
    issues += check_locale_date(c)
    issues += check_cost_cap(c)
    issues += check_voice_drift(c)
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
