"""
IoT/MQTT Protocol Safety Validator — WorkHive Platform
=======================================================
When WorkHive connects to plant sensors via MQTT or OPC-UA, the connection
handling must follow industrial security standards. The integration-engineer
skill provides the code patterns — this validator catches the common mistakes
that come from copying example code directly to production without the
security hardening.

The integration-engineer skill's MQTT example uses:
  mqtt.connect('mqtt://plant-broker.client.local')
  client.subscribe('plant/+/sensors/#')  -- no hive scoping
  supabase.from('sensor_readings').insert({ ...no quality_flag... })

All three of these patterns are unsafe in production. This validator
fires the moment IoT code is added to the codebase.

Four things checked:

  1. No unencrypted MQTT broker URLs in production code
     — MQTT connections to plant equipment must use mqtts:// (TLS).
       mqtt:// sends sensor telemetry, control signals, and credentials
       in plain text across the factory network — visible to any device
       on the same subnet, including PLCs, HMIs, and SCADA workstations.
       localhost URLs are exempt (local development is acceptable).

  2. MQTT client specifies a unique clientId
     — MQTT 3.1.1 protocol: if two clients connect with the same clientId,
       the broker disconnects the first to allow the second. Without an
       explicit clientId, the MQTT library generates a random one — but
       if auto-generation is disabled or the code hard-codes a fixed ID,
       reconnects from different devices will ghost-disconnect each other,
       causing silent data loss from sensors that appear connected.

  3. Sensor data inserts include quality_flag
     — sensor_readings inserts must include a quality_flag field
       (Good/Uncertain/Bad). Without it, a sensor reading from a
       disconnected probe (returning 0 or -999) is stored as valid data
       and silently poisons MTBF calculations and predictive models.
       The field must be explicitly set, not assumed valid.

  4. MQTT topic subscriptions include hive scoping
     — The skill's example subscribes to 'plant/+/sensors/#' — this
       matches ALL plants, not just the client's plant. In a multi-tenant
       deployment where one MQTT broker serves multiple clients, a worker
       from Hive A would receive sensor readings from Hive B.
       Topics must include a hive identifier:
         hive/{hive_id}/sensors/{asset_id}/{sensor_type}

Usage:  python validate_iot_protocols.py
Output: iot_protocols_report.json
"""
import re, json, sys, os

FUNCTIONS_DIR = os.path.join("supabase", "functions")

LIVE_PAGES = [
    "logbook.html", "inventory.html", "pm-scheduler.html", "hive.html",
    "assistant.html", "skillmatrix.html", "dayplanner.html",
    "engineering-design.html", "floating-ai.js", "nav-hub.js",
]

# All files to scan (pages + edge functions + any future IoT scripts)
ALL_SCAN_PATHS = LIVE_PAGES

# Collect edge function paths
if os.path.isdir(FUNCTIONS_DIR):
    for func_name in os.listdir(FUNCTIONS_DIR):
        ts_path = os.path.join(FUNCTIONS_DIR, func_name, "index.ts")
        if os.path.exists(ts_path):
            ALL_SCAN_PATHS = ALL_SCAN_PATHS + [ts_path]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def short_path(path):
    """Return a readable short path for display."""
    return path.replace(
        os.path.join("supabase", "functions") + os.sep, "functions/"
    )


# ── Check 1: No unencrypted MQTT broker URLs ──────────────────────────────────

def check_mqtt_tls(scan_paths):
    """
    MQTT connections to plant equipment must use mqtts:// (TLS encrypted).
    The integration-engineer skill's example uses mqtt:// which is acceptable
    for localhost development but MUST be changed to mqtts:// in production.

    Pattern to flag: mqtt.connect('mqtt://') or mqtt://host (non-localhost)

    Safe:    mqtts://plant-broker.factory.local
             mqtt://localhost
             mqtt://127.0.0.1
    Unsafe:  mqtt://plant-broker.factory.local (no TLS)
    """
    issues = []
    for path in scan_paths:
        content = read_file(path)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            # Find mqtt:// URLs (not mqtts://)
            m = re.search(r"""mqtt://([^'"`\s]+)""", line)
            if not m:
                continue
            host = m.group(1).split("/")[0].split(":")[0]
            if host in ("localhost", "127.0.0.1", "0.0.0.0"):
                continue   # local development — acceptable
            issues.append({
                "path": path,
                "line": i + 1,
                "host": host,
                "reason": (
                    f"{short_path(path)}:{i + 1} — MQTT connection uses "
                    f"unencrypted mqtt:// for host '{host}' — use mqtts:// "
                    f"to encrypt sensor telemetry and credentials in transit"
                ),
            })
    return issues


# ── Check 2: MQTT client specifies a clientId ─────────────────────────────────

def check_mqtt_client_id(scan_paths):
    """
    If MQTT connection code exists, each client must specify a unique clientId.
    Without it, two reconnects from different processes or devices compete
    for the same auto-generated ID, causing one to silently disconnect.

    A plant-specific clientId format:
      clientId: `workhive-${hiveId}-${Date.now()}`

    or at minimum a non-random stable ID per deployment.
    """
    issues = []
    for path in scan_paths:
        content = read_file(path)
        if content is None:
            continue

        # Does this file have an MQTT connect call?
        has_mqtt_connect = bool(re.search(
            r"mqtt\.connect\s*\(|createConnection.*mqtt|new.*mqtt\.Client",
            content, re.IGNORECASE
        ))
        if not has_mqtt_connect:
            continue

        # Is there a clientId anywhere in the MQTT setup?
        has_client_id = bool(re.search(r"clientId\s*:", content))
        if not has_client_id:
            issues.append({
                "path": path,
                "reason": (
                    f"{short_path(path)} — MQTT client connection has no "
                    f"clientId specified — two instances connecting without "
                    f"unique clientId will disconnect each other, causing "
                    f"silent sensor data loss"
                ),
            })
    return issues


# ── Check 3: Sensor data inserts include quality_flag ────────────────────────

def check_sensor_quality_flag(scan_paths):
    """
    Any insert into a sensor_readings table must include quality_flag.
    This field marks data as Good/Uncertain/Bad, allowing downstream analytics
    to filter out readings from disconnected probes, stale values, or
    sensor errors before computing MTBF and predictive risk scores.

    The skill's insert example omits quality_flag — the validator flags
    any sensor_readings insert that lacks it.
    """
    issues = []
    for path in scan_paths:
        content = read_file(path)
        if content is None:
            continue

        # Find sensor_readings insert calls
        for m in re.finditer(
            r"db\.from\(['\"]sensor_readings['\"]\)\.insert\s*\(",
            content
        ):
            # Check the next 12 lines for quality_flag
            start = m.start()
            block = "\n".join(content[start:start + 600].splitlines()[:12])
            if "quality_flag" not in block:
                line_no = content[:start].count("\n") + 1
                issues.append({
                    "path": path,
                    "line": line_no,
                    "reason": (
                        f"{short_path(path)}:{line_no} — sensor_readings insert "
                        f"does not include quality_flag — bad/stale sensor data "
                        f"(disconnected probes, null returns) will be treated as "
                        f"valid readings, corrupting MTBF and predictive models"
                    ),
                })
    return issues


# ── Check 4: MQTT topic subscriptions include hive scoping ───────────────────

def check_mqtt_topic_scope(scan_paths):
    """
    MQTT topic subscriptions must include a hive/tenant identifier to
    prevent cross-client data leakage in multi-tenant deployments.

    The skill's example subscribes to 'plant/+/sensors/#' — this matches
    ALL plants. If one MQTT broker serves multiple enterprise clients, a
    worker from Client A would receive sensor data from Client B.

    Safe:    hive/{hive_id}/sensors/{asset_id}/{type}
             plant/{plant_id}/hive/{hive_id}/sensors/#
    Unsafe:  plant/+/sensors/#  (no tenant scoping)
    """
    issues = []
    for path in scan_paths:
        content = read_file(path)
        if content is None:
            continue

        # Find MQTT subscribe calls
        for m in re.finditer(
            r"\.subscribe\s*\(\s*['\"]([^'\"]+)['\"]",
            content
        ):
            topic = m.group(1)
            # Is this an MQTT-style hierarchical topic? (contains /)
            if "/" not in topic:
                continue
            # Does it contain a hive or tenant identifier?
            has_tenant = bool(re.search(
                r"hive|tenant|client|HIVE_ID|hiveId|\$\{.*hive",
                topic, re.IGNORECASE
            ))
            if not has_tenant:
                line_no = content[:m.start()].count("\n") + 1
                issues.append({
                    "path":  path,
                    "line":  line_no,
                    "topic": topic,
                    "reason": (
                        f"{short_path(path)}:{line_no} — MQTT subscription "
                        f"topic '{topic}' has no hive/tenant identifier — "
                        f"in a shared broker all clients receive each other's "
                        f"sensor data. Use: hive/{{hiveId}}/sensors/# instead"
                    ),
                })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("IoT/MQTT Protocol Safety Validator")
print("=" * 70)
print(f"\n  Scanning {len(LIVE_PAGES)} live pages + {len(ALL_SCAN_PATHS) - len(LIVE_PAGES)} edge functions\n")

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] No unencrypted MQTT broker URLs (mqtt:// for non-localhost hosts)",
        check_mqtt_tls(ALL_SCAN_PATHS),
        "FAIL",
    ),
    (
        "[2] MQTT client connections specify unique clientId",
        check_mqtt_client_id(ALL_SCAN_PATHS),
        "FAIL",
    ),
    (
        "[3] sensor_readings inserts include quality_flag",
        check_sensor_quality_flag(ALL_SCAN_PATHS),
        "FAIL",
    ),
    (
        "[4] MQTT topic subscriptions include hive/tenant scoping",
        check_mqtt_topic_scope(ALL_SCAN_PATHS),
        "WARN",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {short_path(iss.get('path', '?'))}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("iot_protocols_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved iot_protocols_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll IoT protocol safety checks PASS.")
