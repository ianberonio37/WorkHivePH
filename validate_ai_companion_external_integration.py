"""
AI Companion External Integration Validator (turns #155-#164)
==============================================================
Forward-only L0 ratchet for the sixteenth 10-turn flywheel batch (2026-05-21).

  T155  SAP PM webhook receiver
  T156  Maximo poll sync
  T157  OPC-UA tag mapping
  T158  MQTT topic + payload
  T159  Slack webhook
  T160  Email digest body
  T161  Microsoft Teams card
  T162  Calendar ICS event
  T163  Webhook signature constant-time compare
  T164  Outbound retry queue

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


def check_sap(c: str) -> list[dict]:
    issues = []
    if "_validateSapWorkOrder" not in c:
        issues.append({"check": "sap", "reason": "_validateSapWorkOrder missing."})
    for kind in ("'PM01'", "'PM02'", "'PM03'", "'PM04'"):
        if kind not in c:
            issues.append({"check": "sap", "reason": f"SAP order type {kind} missing."})
    if "'sap_pm'" not in c:
        issues.append({"check": "sap", "reason": "source_system 'sap_pm' marker missing."})
    return issues


def check_maximo(c: str) -> list[dict]:
    issues = []
    for sym in ("_buildMaximoQuery", "_parseMaximoResponse"):
        if sym not in c:
            issues.append({"check": "maximo", "reason": f"{sym} missing."})
    if "/maximo/rest/mxapi" not in c:
        issues.append({"check": "maximo", "reason": "Maximo REST path not referenced."})
    if "'maximo'" not in c:
        issues.append({"check": "maximo", "reason": "source_system 'maximo' marker missing."})
    return issues


def check_opc(c: str) -> list[dict]:
    if "_parseOpcTag" not in c:
        return [{"check": "opc", "reason": "_parseOpcTag missing."}]
    return []


def check_mqtt(c: str) -> list[dict]:
    issues = []
    for sym in ("_buildMqttTopic", "_parseMqttPayload"):
        if sym not in c:
            issues.append({"check": "mqtt", "reason": f"{sym} missing."})
    if "'workhive/'" not in c:
        issues.append({"check": "mqtt", "reason": "MQTT topic root 'workhive/' missing."})
    return issues


def check_slack(c: str) -> list[dict]:
    if "_sendSlackMessage" not in c:
        return [{"check": "slack", "reason": "_sendSlackMessage missing."}]
    return []


def check_email(c: str) -> list[dict]:
    if "_buildEmailDigestBody" not in c:
        return [{"check": "email", "reason": "_buildEmailDigestBody missing."}]
    issues = []
    for line in ("Open alerts:", "Closed PMs:", "Overdue PMs:", "Watch list:", "Focus:"):
        if line not in c:
            issues.append({"check": "email", "reason": f"Digest line '{line}' missing."})
    return issues


def check_teams(c: str) -> list[dict]:
    issues = []
    if "_buildTeamsCard" not in c:
        issues.append({"check": "teams", "reason": "_buildTeamsCard missing."})
    if "AdaptiveCard" not in c:
        issues.append({"check": "teams", "reason": "AdaptiveCard schema not referenced."})
    if "adaptive-card.json" not in c:
        issues.append({"check": "teams", "reason": "Adaptive card schema URL missing."})
    return issues


def check_ics(c: str) -> list[dict]:
    issues = []
    if "_buildIcsEvent" not in c:
        issues.append({"check": "ics", "reason": "_buildIcsEvent missing."})
    for line in ("BEGIN:VCALENDAR", "BEGIN:VEVENT", "END:VEVENT", "END:VCALENDAR"):
        if line not in c:
            issues.append({"check": "ics", "reason": f"ICS line {line} missing."})
    return issues


def check_signature(c: str) -> list[dict]:
    issues = []
    if "_constantTimeCompare" not in c:
        issues.append({"check": "signature", "reason": "_constantTimeCompare missing."})
    if "charCodeAt" not in c:
        issues.append({"check": "signature", "reason": "_constantTimeCompare doesn't XOR character codes."})
    return issues


def check_retry_queue(c: str) -> list[dict]:
    issues = []
    for sym in ("_OUTBOUND_QUEUE_KEY", "_OUTBOUND_MAX", "_enqueueOutbound",
                "_getOutboundQueue", "_drainOutboundQueue"):
        if sym not in c:
            issues.append({"check": "retry_queue", "reason": f"{sym} missing."})
    if "wh_voice_outbound_queue" not in c:
        issues.append({"check": "retry_queue", "reason": "wh_voice_outbound_queue localStorage key missing."})
    return issues


CHECK_NAMES = [
    "sap", "maximo", "opc", "mqtt", "slack",
    "email", "teams", "ics", "signature", "retry_queue",
]
CHECK_LABELS = {
    "sap":         "T155 _validateSapWorkOrder + PM01-PM04 order types + sap_pm source",
    "maximo":      "T156 _buildMaximoQuery + _parseMaximoResponse + REST path + maximo source",
    "opc":         "T157 _parseOpcTag",
    "mqtt":        "T158 _buildMqttTopic + _parseMqttPayload + workhive/ root",
    "slack":       "T159 _sendSlackMessage",
    "email":       "T160 _buildEmailDigestBody + 5 digest lines",
    "teams":       "T161 _buildTeamsCard + AdaptiveCard schema",
    "ics":         "T162 _buildIcsEvent + ICS structure",
    "signature":   "T163 _constantTimeCompare with XOR via charCodeAt",
    "retry_queue": "T164 outbound queue key/max/enqueue/get/drain + wh_voice_outbound_queue key",
}


def main() -> int:
    print("\033[1m\nAI Companion External Integration Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")

    issues: list[dict] = []
    issues += check_sap(c)
    issues += check_maximo(c)
    issues += check_opc(c)
    issues += check_mqtt(c)
    issues += check_slack(c)
    issues += check_email(c)
    issues += check_teams(c)
    issues += check_ics(c)
    issues += check_signature(c)
    issues += check_retry_queue(c)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
