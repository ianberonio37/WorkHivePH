"""validate_pattern_alerts.py — Failure Signature Alert quality checks.

Checks:
  1. no_think_leak    — no alert_detail contains <think> reasoning tokens
  2. active_not_empty — active alerts have non-empty title AND detail
  3. valid_rule_ids   — every alert uses a known rule_id
  4. severity_valid   — every alert severity is in (info, warning, critical)
  5. expiry_set       — active alerts have expires_at IS NOT NULL

The <think> leak was found in production (May 2026) when Qwen3-32B
outputted chain-of-thought reasoning into user-facing alert text.
Fix: strip <think>...</think> in failure-signature-scan before storing.
This validator confirms the fix holds and no leaked alerts remain.
"""

import sys, json, re
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "test-data-seeder"))
from lib.supabase_client import get_client

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

VALID_RULE_IDS = {"repeat_failure", "escalating_frequency", "multi_symptom", "missed_pm"}
VALID_SEVERITIES = {"info", "warning", "critical"}


def main():
    db = get_client()
    results = []
    total_pass = total_fail = total_warn = 0

    print(f"\n{BOLD}PATTERN ALERTS VALIDATOR{RESET}")
    print("─" * 40)

    alerts = db.table("failure_signature_alerts") \
        .select("id, machine, rule_id, alert_title, alert_detail, severity, status, expires_at") \
        .limit(500).execute().data or []

    active = [a for a in alerts if a.get("status") == "active"]
    print(f"  Total alerts: {len(alerts)} | Active: {len(active)}")

    # ── Check 1: No <think> leak ─────────────────────────────────────────────
    think_pattern = re.compile(r"<think>", re.IGNORECASE)
    leaked = [a for a in alerts if think_pattern.search(a.get("alert_detail") or "")]

    if not leaked:
        print(f"  {GREEN}PASS{RESET}  no_think_leak: no alerts contain <think> reasoning tokens")
        total_pass += 1
        results.append({"check": "no_think_leak", "status": "PASS", "count": 0})
    else:
        n = len(leaked)
        print(f"  {RED}FAIL{RESET}  no_think_leak: {n} alerts have <think> tokens in alert_detail")
        for a in leaked[:2]:
            print(f"         → {a['machine']}/{a['rule_id']}: {(a['alert_detail'] or '')[:60]}...")
        total_fail += 1
        results.append({"check": "no_think_leak", "status": "FAIL", "count": n,
                        "examples": [a["id"] for a in leaked[:5]]})

    # ── Check 2: Active alerts have non-empty title and detail ───────────────
    empty_active = [
        a for a in active
        if not (a.get("alert_title") or "").strip() or not (a.get("alert_detail") or "").strip()
    ]

    if not empty_active:
        print(f"  {GREEN}PASS{RESET}  active_not_empty: all {len(active)} active alerts have title and detail")
        total_pass += 1
        results.append({"check": "active_not_empty", "status": "PASS", "count": 0})
    else:
        n = len(empty_active)
        print(f"  {RED}FAIL{RESET}  active_not_empty: {n} active alerts missing title or detail text")
        total_fail += 1
        results.append({"check": "active_not_empty", "status": "FAIL", "count": n})

    # ── Check 3: Valid rule_ids ───────────────────────────────────────────────
    invalid_rules = [a for a in alerts if a.get("rule_id") not in VALID_RULE_IDS]

    if not invalid_rules:
        print(f"  {GREEN}PASS{RESET}  valid_rule_ids: all alerts use known rule_id values")
        total_pass += 1
        results.append({"check": "valid_rule_ids", "status": "PASS", "count": 0})
    else:
        bad = list({a["rule_id"] for a in invalid_rules})
        print(f"  {RED}FAIL{RESET}  valid_rule_ids: {len(invalid_rules)} alerts with unknown rule_id: {bad}")
        total_fail += 1
        results.append({"check": "valid_rule_ids", "status": "FAIL",
                        "count": len(invalid_rules), "unknown_rule_ids": bad})

    # ── Check 4: Valid severity values ────────────────────────────────────────
    invalid_sev = [a for a in alerts if a.get("severity") not in VALID_SEVERITIES]

    if not invalid_sev:
        print(f"  {GREEN}PASS{RESET}  severity_valid: all alerts use known severity values")
        total_pass += 1
        results.append({"check": "severity_valid", "status": "PASS", "count": 0})
    else:
        bad_sev = list({a["severity"] for a in invalid_sev})
        print(f"  {YELLOW}WARN{RESET}  severity_valid: {len(invalid_sev)} alerts with unexpected severity: {bad_sev}")
        total_warn += 1
        results.append({"check": "severity_valid", "status": "WARN", "count": len(invalid_sev)})

    # ── Check 5: Active alerts have expires_at ────────────────────────────────
    no_expiry = [a for a in active if not a.get("expires_at")]

    if not no_expiry:
        print(f"  {GREEN}PASS{RESET}  expiry_set: all active alerts have expires_at set")
        total_pass += 1
        results.append({"check": "expiry_set", "status": "PASS", "count": 0})
    else:
        n = len(no_expiry)
        print(f"  {YELLOW}WARN{RESET}  expiry_set: {n} active alerts missing expires_at (will never auto-expire)")
        total_warn += 1
        results.append({"check": "expiry_set", "status": "WARN", "count": n})

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n  Summary: {total_pass} pass · {total_warn} warn · {total_fail} fail")

    report = {
        "validator": "pattern_alerts",
        "pass": total_pass, "warn": total_warn, "fail": total_fail,
        "total_alerts": len(alerts), "active_alerts": len(active),
        "checks": results,
    }
    out = ROOT / "pattern_alerts_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    sys.exit(0 if total_fail == 0 else 1)


if __name__ == "__main__":
    main()
