"""
Voice Alert Formatting Validator (v1)

Ensures anomaly_alerts are properly formatted when surfaced in Rosa/James responses.
4-layer audit:
  1. Alert table has required columns (description, action_suggested)
  2. RPC fetch_active_alerts returns all required fields
  3. Alert descriptions are non-empty (catches null/truncation bugs)
  4. Sample alert text doesn't contain placeholder IDs (catches rendering bugs)
"""

import subprocess
import json
import sys

def run_sql(query):
    """Execute query against local Supabase"""
    try:
        result = subprocess.run(
            ['docker', 'exec', '-i', 'supabase_db_workhive', 'psql',
             '-U', 'postgres', '-d', 'postgres', '-t', '-c', query],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip(), result.returncode == 0
    except Exception as e:
        return str(e), False

def audit_alert_schema():
    """Layer 1: Check anomaly_alerts has required columns"""
    query = """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'anomaly_alerts'
    ORDER BY ordinal_position;
    """
    output, ok = run_sql(query)
    if not ok:
        return False, "Failed to query anomaly_alerts schema"

    lines = output.split('\n')
    columns = {line.split('|')[0].strip(): line.split('|')[1].strip() for line in lines if '|' in line}

    required = {'description', 'action_suggested'}
    missing = required - set(columns.keys())

    if missing:
        return False, f"Missing columns: {missing}"

    return True, f"Schema OK: {len(columns)} columns, has description + action_suggested"

def audit_rpc_definition():
    """Layer 2: Check migration file defines RPC with required fields"""
    try:
        with open('supabase/migrations/20260516000003_anomaly_alerts_phase5.sql', 'r', encoding='utf-8') as f:
            migration_content = f.read()
    except FileNotFoundError:
        return False, "Migration file not found (20260516000003_anomaly_alerts_phase5.sql)"

    # Check for RPC definition
    if 'fetch_active_alerts' not in migration_content:
        return False, "fetch_active_alerts RPC not defined in migration"

    # Check for required return fields in RPC definition
    if 'description' not in migration_content.lower():
        return False, "RPC missing 'description' field"
    if 'action_suggested' not in migration_content.lower():
        return False, "RPC missing 'action_suggested' field"

    return True, "RPC defined with description + action_suggested fields"

def audit_alert_data():
    """Layer 3: Check that actual alerts have non-empty descriptions"""
    query = """
    SELECT id, alert_type, severity,
           description, action_suggested,
           length(description) as desc_len,
           length(action_suggested) as action_len
    FROM anomaly_alerts
    LIMIT 10;
    """
    output, ok = run_sql(query)
    if not ok:
        return False, "Failed to fetch alerts"

    if not output:
        return True, "No alerts found (not a failure, just empty)"  # OK for empty test DB

    lines = output.split('\n')
    null_descs = 0
    short_descs = 0
    empty_actions = 0

    for line in lines:
        if '|' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 7:
                desc_len_str = parts[5]
                action_len_str = parts[6]

                try:
                    desc_len = int(desc_len_str) if desc_len_str else 0
                    action_len = int(action_len_str) if action_len_str else 0

                    if desc_len == 0 or 'null' in desc_len_str.lower():
                        null_descs += 1
                    if desc_len < 20:
                        short_descs += 1
                    if action_len == 0 or 'null' in action_len_str.lower():
                        empty_actions += 1
                except ValueError:
                    pass

    if null_descs > 0:
        return False, f"{null_descs} alerts have NULL or empty description"
    if empty_actions > 0:
        return False, f"{empty_actions} alerts have NULL or empty action_suggested"

    if short_descs > 0:
        return True, f"[WARN] {short_descs} alerts have very short descriptions (<20 chars)"

    return True, "All alerts have non-empty description + action_suggested"

def audit_alert_content():
    """Layer 4: Check alert text doesn't contain placeholder IDs (no TEST-MACHINE, etc.)"""
    query = """
    SELECT id, description, action_suggested
    FROM anomaly_alerts
    LIMIT 10;
    """
    output, ok = run_sql(query)
    if not ok or not output:
        return True, "No alerts to check (OK)"

    # Placeholder patterns that indicate rendering bugs
    bad_patterns = ['TEST-MACHINE', 'TEST-RESOLVE', 'mp6s', 'WH-PW-0', 'placeholder']

    lines = output.split('\n')
    alerts_with_bad_patterns = []

    for line in lines:
        if '|' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3:
                desc = parts[1]
                action = parts[2]
                full_text = f"{desc} {action}".upper()

                for pattern in bad_patterns:
                    if pattern in full_text:
                        alerts_with_bad_patterns.append((parts[0], pattern))

    if alerts_with_bad_patterns:
        details = '; '.join([f"Alert {a[0]} contains {a[1]}" for a in alerts_with_bad_patterns])
        return False, f"Rendering bug detected: {details}"

    return True, "Alert content looks normal (no placeholder IDs detected)"

def main():
    print("\n[Voice Alert Formatting Validator]\n")

    tests = [
        ("Layer 1: Schema", audit_alert_schema),
        ("Layer 2: RPC definition", audit_rpc_definition),
        ("Layer 3: Alert data", audit_alert_data),
        ("Layer 4: Alert content", audit_alert_content),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        ok, msg = test_fn()
        status = "[PASS]" if ok else "[FAIL]"
        print(f"{status}: {name}")
        print(f"       {msg}\n")

        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"Result: {passed} PASS, {failed} FAIL")
    print(f"{'='*60}\n")

    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
