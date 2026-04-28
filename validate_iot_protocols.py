"""
IoT/MQTT Protocol Safety Validator — WorkHive Platform
=======================================================
When WorkHive connects to plant sensors via MQTT or OPC-UA, the connection
handling must follow industrial security standards. The integration-engineer
skill provides the code patterns — this validator catches the common mistakes
that come from copying example code directly to production without the
security hardening.

  Layer 1 — Transport security
    1.  TLS on all MQTT connections        — mqtt:// exposes telemetry in plain text
    2.  Unique clientId per connection     — shared ID ghost-disconnects other sessions

  Layer 2 — Data quality
    3.  quality_flag on sensor inserts     — bad/stale readings corrupt MTBF and predictive models

  Layer 3 — Tenant isolation
    4.  Hive-scoped MQTT topics            — unscoped topics leak sensor data across tenants

  Layer 4 — Reliability
    5.  QoS >= 1 on sensor data paths      — QoS 0 drops readings silently on unstable networks
    6.  Reconnect logic with backoff       — no reconnect = permanent data loss on disconnect

Usage:  python validate_iot_protocols.py
Output: iot_protocols_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

FUNCTIONS_DIR = os.path.join("supabase", "functions")

LIVE_PAGES = [
    "logbook.html", "inventory.html", "pm-scheduler.html", "hive.html",
    "assistant.html", "skillmatrix.html", "dayplanner.html",
    "engineering-design.html", "floating-ai.js", "nav-hub.js",
]

ALL_SCAN_PATHS = list(LIVE_PAGES)
if os.path.isdir(FUNCTIONS_DIR):
    for func_name in os.listdir(FUNCTIONS_DIR):
        ts_path = os.path.join(FUNCTIONS_DIR, func_name, "index.ts")
        if os.path.exists(ts_path):
            ALL_SCAN_PATHS.append(ts_path)


def short_path(path):
    return path.replace(os.path.join("supabase", "functions") + os.sep, "functions/")


def _has_mqtt_connect(content):
    return bool(re.search(r"mqtt\.connect\s*\(|createConnection.*mqtt|new.*mqtt\.Client", content, re.IGNORECASE))


# ── Layer 1: Transport security ───────────────────────────────────────────────

def check_mqtt_tls(scan_paths):
    """mqtt:// for non-localhost hosts sends telemetry and credentials in plain
    text across the factory network — use mqtts:// instead."""
    issues = []
    for path in scan_paths:
        content = read_file(path)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("//") or line.strip().startswith("*"):
                continue
            m = re.search(r"""mqtt://([^'"`\s]+)""", line)
            if not m:
                continue
            host = m.group(1).split("/")[0].split(":")[0]
            if host in ("localhost", "127.0.0.1", "0.0.0.0"):
                continue
            issues.append({"check": "mqtt_tls", "path": path, "line": i + 1,
                           "reason": (f"{short_path(path)}:{i + 1} MQTT uses unencrypted "
                                      f"mqtt:// for host '{host}' — use mqtts:// to encrypt "
                                      f"sensor telemetry and credentials in transit")})
    return issues


def check_mqtt_client_id(scan_paths):
    """MQTT clients must specify a unique clientId — two instances without unique
    IDs ghost-disconnect each other, causing silent sensor data loss."""
    issues = []
    for path in scan_paths:
        content = read_file(path)
        if content is None:
            continue
        if not _has_mqtt_connect(content):
            continue
        if not re.search(r"clientId\s*:", content):
            issues.append({"check": "mqtt_client_id", "path": path,
                           "reason": (f"{short_path(path)} MQTT connection has no clientId — "
                                      f"two instances without unique IDs disconnect each other, "
                                      f"causing silent sensor data loss")})
    return issues


# ── Layer 2: Data quality ─────────────────────────────────────────────────────

def check_sensor_quality_flag(scan_paths):
    """sensor_readings inserts must include quality_flag (Good/Uncertain/Bad) —
    without it, readings from disconnected probes corrupt MTBF and predictive models."""
    issues = []
    for path in scan_paths:
        content = read_file(path)
        if content is None:
            continue
        for m in re.finditer(r"db\.from\(['\"]sensor_readings['\"]\)\.insert\s*\(", content):
            block = "\n".join(content[m.start():m.start() + 600].splitlines()[:12])
            if "quality_flag" not in block:
                line_no = content[:m.start()].count("\n") + 1
                issues.append({"check": "sensor_quality_flag", "path": path, "line": line_no,
                               "reason": (f"{short_path(path)}:{line_no} sensor_readings insert "
                                          f"missing quality_flag — bad/stale readings corrupt "
                                          f"MTBF and predictive models")})
    return issues


# ── Layer 3: Tenant isolation ─────────────────────────────────────────────────

def check_mqtt_topic_scope(scan_paths):
    """MQTT subscriptions must include a hive/tenant identifier — unscoped topics
    expose all clients' sensor data to each other on a shared broker."""
    issues = []
    for path in scan_paths:
        content = read_file(path)
        if content is None:
            continue
        for m in re.finditer(r"\.subscribe\s*\(\s*['\"]([^'\"]+)['\"]", content):
            topic = m.group(1)
            if "/" not in topic:
                continue
            if not re.search(r"hive|tenant|client|HIVE_ID|hiveId|\$\{.*hive", topic, re.IGNORECASE):
                line_no = content[:m.start()].count("\n") + 1
                issues.append({"check": "mqtt_topic_scope", "path": path,
                               "skip": True,
                               "line": line_no,
                               "reason": (f"{short_path(path)}:{line_no} MQTT topic '{topic}' "
                                          f"has no hive/tenant identifier — shared broker leaks "
                                          f"sensor data across tenants; use hive/{{hiveId}}/sensors/#")})
    return issues


# ── Layer 4: Reliability ──────────────────────────────────────────────────────

def check_mqtt_qos_level(scan_paths):
    """
    MQTT sensor data subscriptions and publishes must use QoS >= 1 (at-least-once).
    QoS 0 (fire-and-forget) drops messages silently when:
    - The factory network has packet loss (common on industrial WiFi)
    - The MQTT broker is briefly overloaded (peak shift change)
    - The subscriber temporarily disconnects (sensor firmware reset)

    With QoS 0, a missed sensor reading produces a gap in the time series.
    The predictive model sees no reading and either interpolates incorrectly
    or marks the sensor as stale — both outcomes degrade failure detection.

    The integration-engineer skill specifies QoS 1 for sensor_readings ingestion.
    Any MQTT publish/subscribe call that specifies qos: 0 is flagged.
    Forward guard: PASS if no MQTT code exists yet.
    """
    issues = []
    for path in scan_paths:
        content = read_file(path)
        if content is None:
            continue
        if not _has_mqtt_connect(content):
            continue
        # Flag qos: 0 explicitly — missing qos defaults to 0 in most libraries
        for m in re.finditer(r"\bqos\s*:\s*0\b", content):
            line_no = content[:m.start()].count("\n") + 1
            # Is this in a subscribe or publish context?
            context = content[max(0, m.start() - 200):m.start() + 50]
            if re.search(r"subscribe|publish|sensor", context, re.IGNORECASE):
                issues.append({"check": "mqtt_qos_level", "path": path, "line": line_no,
                               "reason": (f"{short_path(path)}:{line_no} MQTT uses qos: 0 "
                                          f"(fire-and-forget) for sensor data — packet loss on "
                                          f"industrial WiFi drops readings silently, creating gaps "
                                          f"in the time series; use qos: 1 (at-least-once) for "
                                          f"all sensor data paths")})
        # Also check for publish/subscribe calls with no qos option
        for m in re.finditer(r"\.(subscribe|publish)\s*\(", content, re.IGNORECASE):
            block = content[m.start():m.start() + 300]
            if not re.search(r"\bqos\s*:", block):
                line_no = content[:m.start()].count("\n") + 1
                # Only flag if it looks like a sensor data path
                if re.search(r"sensor|readings|telemetry", block, re.IGNORECASE):
                    issues.append({"check": "mqtt_qos_level", "path": path, "line": line_no,
                                   "reason": (f"{short_path(path)}:{line_no} MQTT "
                                              f"{m.group(1)}() on sensor data path has no qos "
                                              f"option — defaults to QoS 0 which drops messages "
                                              f"on unstable factory networks; add qos: 1")})
    return issues


def check_mqtt_reconnect_logic(scan_paths):
    """
    MQTT clients must implement reconnect logic with exponential backoff.
    Industrial factory networks have intermittent connectivity — PLCs reboot,
    WiFi APs cycle, and VPN tunnels drop. Without reconnect logic:

    - When the connection drops, the client stops receiving sensor data
    - No error is visible to the worker (silent gap in readings)
    - The digital twin health score stops updating
    - Predictive models see 'no readings' and may incorrectly classify the
      asset as failed when it is actually healthy

    The integration-engineer skill specifies:
      client.on('disconnect', () => setTimeout(reconnect, backoffMs))
      const backoffMs = Math.min(1000 * 2 ** attempt, 30000)

    Forward guard: PASS if no MQTT code exists. FAIL if MQTT is added without
    reconnect and backoff logic.
    """
    issues = []
    for path in scan_paths:
        content = read_file(path)
        if content is None:
            continue
        if not _has_mqtt_connect(content):
            continue
        # Must have a disconnect/close/error handler
        has_reconnect_handler = bool(re.search(
            r"on\s*\(\s*['\"](?:disconnect|close|offline|error)['\"]",
            content
        ))
        if not has_reconnect_handler:
            issues.append({"check": "mqtt_reconnect_logic", "path": path,
                           "reason": (f"{short_path(path)} MQTT client has no "
                                      f"disconnect/close event handler — when the factory "
                                      f"network drops, sensor data stops flowing silently; "
                                      f"add on('disconnect') with exponential backoff reconnect")})
            continue
        # Has disconnect handler — check for backoff pattern
        has_backoff = bool(re.search(
            r"setTimeout.*reconnect|backoff|Math\.min.*\d+.*\*\*|exponential",
            content, re.IGNORECASE
        ))
        if not has_backoff:
            issues.append({"check": "mqtt_reconnect_logic", "path": path,
                           "skip": True,
                           "reason": (f"{short_path(path)} MQTT client has a disconnect handler "
                                      f"but no backoff pattern — reconnecting immediately on every "
                                      f"disconnect floods the broker; add exponential backoff: "
                                      f"setTimeout(reconnect, Math.min(1000 * 2 ** attempt, 30000))")})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "mqtt_tls",
    "mqtt_client_id",
    "sensor_quality_flag",
    "mqtt_topic_scope",
    "mqtt_qos_level",
    "mqtt_reconnect_logic",
]

CHECK_LABELS = {
    "mqtt_tls":              "L1  No unencrypted mqtt:// for non-localhost hosts",
    "mqtt_client_id":        "L1  MQTT connections specify unique clientId",
    "sensor_quality_flag":   "L2  sensor_readings inserts include quality_flag",
    "mqtt_topic_scope":      "L3  MQTT topics include hive/tenant scoping  [WARN]",
    "mqtt_qos_level":        "L4  MQTT sensor paths use QoS >= 1 (at-least-once)",
    "mqtt_reconnect_logic":  "L4  MQTT client has reconnect + backoff logic",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nIoT/MQTT Protocol Safety Validator (4-layer)"))
    print("=" * 55)
    n_funcs = len(ALL_SCAN_PATHS) - len(LIVE_PAGES)
    print(f"  {len(LIVE_PAGES)} live pages + {n_funcs} edge functions\n")

    all_issues = []
    all_issues += check_mqtt_tls(ALL_SCAN_PATHS)
    all_issues += check_mqtt_client_id(ALL_SCAN_PATHS)
    all_issues += check_sensor_quality_flag(ALL_SCAN_PATHS)
    all_issues += check_mqtt_topic_scope(ALL_SCAN_PATHS)
    all_issues += check_mqtt_qos_level(ALL_SCAN_PATHS)
    all_issues += check_mqtt_reconnect_logic(ALL_SCAN_PATHS)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "iot_protocols",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("iot_protocols_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
