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

import os, re, sys
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
    # (*)THIS ASSERTED A VALUE NO WRITER COULD EVER HAVE STORED. It required the literal
    # "right_to_erasure", and the code did write it - into `event_type`, a column ai_audit_log does not
    # have (its migration declares `event text NOT NULL` and documents the vocabulary in a comment:
    # 'logbook.create' / 'pm.schedule' / 'erasure_request'). So the check passed on a row that could only
    # ever have been refused, and it was asserting a spelling the table had never agreed to. Both sides
    # now follow the table: `event`, value `erasure_request`.
    if "erasure_request" not in c:
        issues.append({"check": "erasure", "reason": "the erasure_request audit event is not logged."})
    # Match the KEY being written, not the word, AND ignore comment lines - this file now explains the
    # mistake in prose, and the first version of this check fired on its own explanation. A check that
    # reads a comment as code is the same error one level up, and it caught me the same afternoon.
    code = "\n".join(l for l in c.splitlines() if not l.lstrip().startswith(("//", "*", "/*")))
    if re.search(r"(?m)^\s*event_type\s*:", code) or re.search(r"\br\.event_type\b", code):
        issues.append({"check": "erasure",
                       "reason": "a writer still names `event_type`; ai_audit_log's column is `event`."})
    return issues


def check_audit_export(c: str) -> list[dict]:
    """T119 audit export - now checked WHERE IT LIVES, not where it was first written.

    This asked whether voice-handler.js spelled `_buildAuditCsv` and `_toCsvRow`. Both were removed on
    2026-09-08: they were a second, weaker CSV writer, defined and exported and called by nothing since
    the day they were written, and wrong the whole time (an `event_type` header against a table whose
    column is `event`) precisely because nothing exercised them. audit-log.html owns the real export, and
    it now reads ai_audit_log alongside hive_audit_log, so the voice rows are covered by it.

    The requirement has not been relaxed - a compliance export of voice activity must still be producible.
    Only the address changed, and it is checked at the new one: the page must READ the table and OFFER the
    export. If either disappears, this reddens."""
    issues = []
    try:
        page = read_file("audit-log.html") or ""
    except Exception:
        page = ""
    if not page:
        issues.append({"check": "audit_export", "reason": "audit-log.html could not be read, so whether "
                                                          "voice activity is exportable is unknown."})
        return issues
    if "ai_audit_log" not in page:
        issues.append({"check": "audit_export", "reason": "audit-log.html no longer reads ai_audit_log, so "
                                                          "voice activity is in no export."})
    if "exportCsv" not in page:
        issues.append({"check": "audit_export", "reason": "audit-log.html no longer offers a CSV export."})
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


# (*)EVERY CHECK ABOVE ASKS WHETHER A NAME IS SPELLED IN THE FILE, and a function defined once and called
# never satisfies all of them. Measured 2026-09-08: _emitAuditEvent, _executeErasure, _enforceRetention and
# _buildAuditCsv each appear EXACTLY TWICE in voice-handler.js - the definition and the export list - so
# every one of these promises is dead code that this validator has been certifying for months.
#
# What that means in the product, in the order it matters:
#   · the assistant tells a worker "I can clear your voice + journal history for this hive. Confirm with
#     yes - this cannot be undone." On yes, NOTHING IS DELETED. That is a Data Privacy Act right offered
#     and not performed, which is worse than not offering it: the person stops asking.
#   · the header over _emitAuditEvent says "every confirmed write action (log entry, schedule, alert flag)
#     writes to ai_audit_log so we can replay every voice-driven decision". Four actions really are
#     registered by pages (asset.lookup, inventory.deduct, logbook.create, pm.complete) and the emitter is
#     on none of them - which is exactly why ai_audit_log holds zero rows in all six hives and the
#     AI-assisted-day journey reads "the chain is empty" everywhere it is cast.
#   · retention never ages anything out, and the compliance CSV cannot be produced by anyone.
#
# A "wires" check already exists and passes, because it looks for the PROMPT ANCHOR - the sentence the
# assistant is told to say. Saying it is precisely what the product does; doing it is what it does not.
# So this check asks the one question the others cannot: is there a CALL?
REACHABLE = {
    "_emitAuditEvent":   "the audit row behind 'we can replay every voice-driven decision'",
    "_executeErasure":   "the deletion the assistant promises on a confirmed yes",
    "_enforceRetention": "the retention policy that ages voice data out",
    # The one still open, and the reason is a chain rather than a missing line: audit-log.html already
    # owns a mature CSV export (its own escaping, a UTF-8 BOM for Excel, a header stating the file's
    # scope), so this second builder is the weaker duplicate and should not be wired to a new button.
    # What is actually missing is a READER: ai_audit_log - where voice-driven actions now land - is
    # displayed by no page at all, and v_audit_unified, the platform's own four-table audit view, is read
    # by no page either. Give the page the rows and the export it already has covers them.
    "_buildAuditCsv":    "the compliance export of voice activity (blocked upstream: no page reads ai_audit_log, and v_audit_unified has no reader either)",
}

# ★A CAPABILITY MAY LIVE IN ANOTHER LAYER, AND THEN THE CLIENT CALL SITE WOULD BE THE BUG. Retention
# deletes every row in a hive older than the cutoff - every worker's entries, not the speaker's own - so
# calling it from a browser would need RLS to let any member delete a colleague's journal, which is a hole
# rather than a feature. It is a scheduled job or it is nothing. So the requirement stays "this must
# actually happen" and only the place the evidence may be found widens; a symbol with neither a call site
# nor its named external home still fails.
ELSEWHERE = {
    "_enforceRetention": ("supabase/migrations/20260908000003_voice_journal_retention_cron.sql",
                          "voice-journal-retention",
                          "a daily pg_cron job, which is where a hive-wide destructive sweep belongs"),
    # The export was never a missing feature - it was a weaker duplicate. audit-log.html already owns a
    # mature CSV export (its own escaping, a UTF-8 BOM so Excel does not mangle an asset name, a header
    # stating the file's scope), and it exports whatever the feed holds. What was actually missing was a
    # READER: nothing displayed ai_audit_log, so there was nothing for any export to cover. The page now
    # merges both audit tables into one timeline, so the capability happens through the platform's export
    # rather than a second one nobody would maintain.
    "_buildAuditCsv":    ("audit-log.html", "ai_audit_log",
                          "audit-log.html, which now reads the voice rows and exports them with its own CSV"),
}


def _reached_elsewhere(sym: str) -> tuple[bool, str]:
    spec = ELSEWHERE.get(sym)
    if not spec:
        return False, ""
    path, needle, where = spec
    try:
        with open(path, encoding="utf-8") as fh:
            return (needle in fh.read()), where
    except OSError:
        return False, where


def check_reachable(c: str) -> list[dict]:
    """A capability must actually HAPPEN: called in this file, or performed in its declared home.

    The call test is deliberately crude and hard to fool - count `name(` and drop the definition. An
    export list mentions the bare name with no parenthesis, so it cannot pass a function off as reached."""
    issues = []
    for sym, what in REACHABLE.items():
        calls = c.count(sym + "(") - c.count("function " + sym + "(")
        if calls > 0:
            continue
        ok, where = _reached_elsewhere(sym)
        if ok:
            continue
        extra = f" (its declared home, {where}, does not carry it either)" if where else ""
        issues.append({"check": "reachable",
                       "reason": f"{sym} is defined and never called - {what} does not happen{extra}."})
    return issues


CHECK_NAMES = [
    "pii", "consent", "retention", "erasure", "audit_export",
    "suspicious", "ai_disclosure", "locale_date", "cost_cap", "voice_drift",
    "wires", "reachable",
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
    "reachable":     "the four capabilities that DO something are actually called: audit emission, erasure, retention, audit export",
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
    issues += check_reachable(c)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
