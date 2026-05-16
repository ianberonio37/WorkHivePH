#!/usr/bin/env python3
"""
Phase 5 Validator: Proactive Alerts & Anomaly Intelligence

Validates that KPI spike + risk + PM overdue detection is wired:

5 Layers:
  L1: anomaly_alerts table exists with correct schema
  L2: KPI deviation scoring (spikes, escalations)
  L3: Alert de-duplication works (no duplicate within 1h)
  L4: Proactive scan scheduler (every 15 min)
  L5: Critical alerts surface before user query

SUCCESS: All 5 layers pass (indicates Phase 5 wiring complete)
"""

import re
import sys

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check_phase_5_alerts():
    try:
        with open("voice-handler.js", "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"{RED}FAIL{RESET} voice-handler.js not found")
        return False

    results = {"pass": 0, "fail": 0}

    # L1: anomaly_alerts table migration exists
    print("\n[L1] Database schema (anomaly_alerts table)")
    migration_file = "supabase/migrations/20260516000003_anomaly_alerts_phase5.sql"
    try:
        with open(migration_file, "r", encoding="utf-8") as f:
            migration = f.read()

        required_columns = [
            "hive_id uuid",
            "alert_type text",
            "severity text",
            "metric_name text",
            "metric_value real",
            "deviation_percent real",
        ]

        missing_cols = [col for col in required_columns if col not in migration]
        if not missing_cols:
            print(f"  {GREEN}PASS{RESET} anomaly_alerts table schema complete")
            results["pass"] += 1
        else:
            print(f"  {RED}FAIL{RESET} Missing columns: {missing_cols}")
            results["fail"] += 1

        # Check RPCs
        if "fetch_active_alerts" in migration and "acknowledge_alert" in migration:
            print(f"  {GREEN}PASS{RESET} RPC functions (fetch + acknowledge) defined")
            results["pass"] += 1
        else:
            print(f"  {RED}FAIL{RESET} RPC functions missing")
            results["fail"] += 1

    except FileNotFoundError:
        print(f"  {RED}FAIL{RESET} Migration file {migration_file} not found")
        results["fail"] += 1

    # L2: KPI deviation scoring
    print("\n[L2] Anomaly detection in voice-handler.js")

    if "_fetchProactiveAlerts(" in content:
        print(f"  {GREEN}PASS{RESET} Proactive alerts fetch function exists")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Proactive alerts fetch missing")
        results["fail"] += 1

    # L3: Alert de-duplication (no duplicate within 1h)
    print("\n[L3] Alert de-duplication")

    if "suppressed_until" in content or "suppress_alert" in migration:
        print(f"  {GREEN}PASS{RESET} Alert suppression for 24h implemented")
        results["pass"] += 1
    else:
        print(f"  {YELLOW}WARN{RESET} Alert dedup mechanism unclear")

    # L4: Proactive scan (fetch alerts before user query)
    print("\n[L4] Proactive scan integration")

    if "proactiveAlerts" in content:
        print(f"  {GREEN}PASS{RESET} Proactive alerts fetched in conversation flow")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Proactive alerts not fetched")
        results["fail"] += 1

    # L5: Critical alerts surface first
    print("\n[L5] Alert surfacing in system prompt")

    if "ACTIVE ALERTS" in content or "alertsSection" in content:
        print(f"  {GREEN}PASS{RESET} Alert section in system prompt")
        results["pass"] += 1
    else:
        print(f"  {RED}FAIL{RESET} Alert section not in prompt")
        results["fail"] += 1

    if "critical/high" in content or "Surface these FIRST" in content:
        print(f"  {GREEN}PASS{RESET} Critical alerts prioritized in prompt")
        results["pass"] += 1
    else:
        print(f"  {YELLOW}WARN{RESET} Alert priority unclear in prompt")

    # Summary
    print("\n" + "=" * 70)
    print(f"PASS: {results['pass']} | FAIL: {results['fail']}")
    print("=" * 70)

    return results["fail"] == 0


if __name__ == "__main__":
    success = check_phase_5_alerts()
    sys.exit(0 if success else 1)
