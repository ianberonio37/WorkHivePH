"""
Phase 5: Proactive Alerts seeder

Populates anomaly_alerts table with realistic KPI spikes, risk escalations, and maintenance overdue alerts.
Used to test Rosa/James alert surfacing logic (Hard Rule: surface critical alerts FIRST).
"""

def seed_anomaly_alerts(client, log, ctx):
    """Seed anomaly alerts for proactive alert testing."""

    log("\n[Voice Companion Phase 5] Seeding proactive alerts...")

    # Get first hive for seeding
    hives = ctx.get("hives", [])
    if not hives:
        log("  SKIP: No hives found, cannot seed alerts")
        return 0
    hive_id = hives[0]["id"]

    # Use generic asset names (no need to query assets table)
    assets = [
        {"name": "Pump A", "tag": "PUMP-001"},
        {"name": "Motor B", "tag": "MOTOR-002"},
        {"name": "Compressor C", "tag": "COMP-003"},
        {"name": "Bearing D", "tag": "BRG-004"},
        {"name": "Valve E", "tag": "VLV-005"},
    ]

    # Create realistic alert scenarios
    alert_scenarios = [
        {
            "alert_type": "maintenance_overdue",
            "severity": "critical",
            "metric_name": "pm_days_overdue",
            "metric_value": 3,
            "metric_threshold": 0,
            "deviation_percent": 300.0,
            "description": f"Preventive Maintenance overdue for {assets[0]['name']} (tag: {assets[0]['tag']}). Last PM was 3 days ago, scheduled every 30 days.",
            "action_suggested": "Schedule PM for this asset within 24 hours to prevent failure escalation.",
            "asset_idx": 0,
        },
        {
            "alert_type": "kpi_spike",
            "severity": "high",
            "metric_name": "mttr",
            "metric_value": 4.5,
            "metric_threshold": 2.8,
            "deviation_percent": 160.7,
            "description": f"MTTR spike on {assets[1]['name'] if len(assets) > 1 else assets[0]['name']}: 4.5 hours (60% above baseline 2.8 hours). Last 3 repairs averaged 5.2 hours.",
            "action_suggested": "Review recent repairs for this asset. Root cause likely related to parts availability or technician skill gaps.",
            "asset_idx": 1 if len(assets) > 1 else 0,
        },
        {
            "alert_type": "risk_escalation",
            "severity": "critical",
            "metric_name": "risk_score",
            "metric_value": 0.92,
            "metric_threshold": 0.75,
            "deviation_percent": 122.7,
            "description": f"Risk score escalation on {assets[0]['name']}: 0.92 (critical threshold). MTBF down 15% week-over-week.",
            "action_suggested": "Implement daily condition monitoring (vibration, temperature). Consider emergency PM or asset replacement.",
            "asset_idx": 0,
        },
        {
            "alert_type": "kpi_spike",
            "severity": "high",
            "metric_name": "downtime",
            "metric_value": 8.5,
            "metric_threshold": 4.0,
            "deviation_percent": 212.5,
            "description": f"Downtime spike: {assets[2]['name'] if len(assets) > 2 else assets[0]['name']} down 8.5 hours this week (vs. 4 hour avg). Multiple restart failures.",
            "action_suggested": "Check control panel diagnostics and power supply health. May indicate electrical issue.",
            "asset_idx": 2 if len(assets) > 2 else 0,
        },
        {
            "alert_type": "maintenance_overdue",
            "severity": "high",
            "metric_name": "pm_days_overdue",
            "metric_value": 2,
            "metric_threshold": 0,
            "deviation_percent": 200.0,
            "description": f"PM approaching overdue for {assets[3]['name'] if len(assets) > 3 else assets[1]['name']}. Scheduled 2 days ago, not yet completed.",
            "action_suggested": "Confirm PM schedule and resource availability. Flag technician if task is blocked.",
            "asset_idx": 3 if len(assets) > 3 else 1 if len(assets) > 1 else 0,
        },
    ]

    alerts_inserted = 0

    for scenario in alert_scenarios:
        try:
            asset = assets[scenario['asset_idx']] if scenario['asset_idx'] < len(assets) else assets[0]

            res = client.from_('anomaly_alerts').insert({
                'hive_id': hive_id,
                'asset_id': None,  # Asset ID lookup would happen in production
                'alert_type': scenario['alert_type'],
                'severity': scenario['severity'],
                'metric_name': scenario['metric_name'],
                'metric_value': scenario['metric_value'],
                'metric_threshold': scenario['metric_threshold'],
                'deviation_percent': scenario['deviation_percent'],
                'description': scenario['description'],
                'action_suggested': scenario['action_suggested'],
                'detected_at': 'now()',
                'suppressed_until': None,
                'acknowledged_at': None,
            }).execute()

            if res.data:
                alerts_inserted += 1
                severity_emoji = "🔴" if scenario['severity'] == 'critical' else "🟠"
                log(f"  {severity_emoji} [{scenario['alert_type'].upper()}] {scenario['description'][:60]}...")
        except Exception as e:
            log(f"  WARN: Could not insert alert: {e}")

    log(f"  Phase 5 seeding complete: {alerts_inserted} proactive alerts created")
    return alerts_inserted


# Hook for test-data-seeder orchestrator
def run(client, log, ctx):
    """
    Entry point for test-data-seeder.
    Expected signature: run(client, log, ctx) -> int (rows inserted)
    """
    return seed_anomaly_alerts(client, log, ctx)
