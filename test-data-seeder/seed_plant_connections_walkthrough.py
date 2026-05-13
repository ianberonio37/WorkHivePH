"""Walkthrough 2026-05-13: seed Lucena plant-connections.html so the
six supervisor panels render with realistic Stair 3 data.

Panels seeded:
  1. hive_retention_config — 1 row with custom PDPA windows
  2. sso_configs           — Microsoft Entra in pending_review (typical
                              enterprise pilot state)
  3. integration_configs   — SAP PM + generic CSV
  4. external_sync         — 30 sync events over 30 days
  5. sensor_topic_map      — 6 MQTT topics mapped to Lucena equipment
  6. gateway_audit_log     — 60 calls over 7 days, mostly 2xx

Idempotent within window. Safe to re-run.
"""
import sys
import random
import hashlib
from datetime import datetime, timedelta, timezone

sys.path.insert(0, '.')
from lib.supabase_client import get_client


LUCENA_HIVE = '586fd158-42d1-4853-a406-64a4695e71c4'
SUPERVISOR = 'Pablo Aguilar'


def seed_retention(db, now):
    db.table('hive_retention_config').upsert({
        'hive_id': LUCENA_HIVE,
        'soft_delete_retention_days': 45,
        'audit_retention_days': 730,
        'ai_telemetry_retention_days': 60,
        'updated_at': now.isoformat(),
        'updated_by': SUPERVISOR,
    }, on_conflict='hive_id').execute()
    print('  hive_retention_config: 1 row')


def seed_sso(db, now):
    db.table('sso_configs').delete().eq('hive_id', LUCENA_HIVE).execute()
    db.table('sso_configs').insert({
        'hive_id': LUCENA_HIVE,
        'provider': 'microsoft_entra',
        'status': 'pending_review',
        'idp_entity_id': 'https://sts.windows.net/lucena-pharma/',
        'acs_url': 'https://workhive.app/auth/saml/lucena/acs',
        'metadata_url': 'https://login.microsoftonline.com/lucena/federationmetadata.xml',
        'enforced': False,
        'created_by': SUPERVISOR,
        'notes': 'IT submitted metadata 2026-05-08. Awaiting SAML cert thumbprint from Entra admin.',
    }).execute()
    print('  sso_configs: 1 row (pending_review)')


def seed_integrations(db, now):
    db.table('integration_configs').delete().eq('hive_id', LUCENA_HIVE).execute()
    rows = [
        {
            'hive_id': LUCENA_HIVE,
            'system_type': 'sap_pm',
            'label': 'SAP Plant Lucena (PH-LUC-01)',
            'endpoint_url': 'https://sap-prod.lucenapharma.ph/sap/opu/odata/sap/ZPM_WORKHIVE_SRV',
            'auth_method': 'oauth',
            'sync_freq': 'hourly',
            'enabled': True,
            'last_sync_at': (now - timedelta(hours=2)).isoformat(),
            'last_sync_count': 14,
        },
        {
            'hive_id': LUCENA_HIVE,
            'system_type': 'generic',
            'label': 'Spare Parts CSV (weekly drop)',
            'endpoint_url': 'sftp://files.lucenapharma.ph/workhive/inventory/',
            'auth_method': 'basic',
            'sync_freq': 'daily',
            'enabled': True,
            'last_sync_at': (now - timedelta(days=3, hours=4)).isoformat(),
            'last_sync_count': 0,
        },
    ]
    db.table('integration_configs').insert(rows).execute()
    print(f'  integration_configs: {len(rows)} rows')


def seed_external_sync(db, now):
    db.table('external_sync').delete().eq('hive_id', LUCENA_HIVE).execute()
    entity_types = ['work_order', 'asset', 'pm_schedule', 'inventory']
    workhive_tables = {
        'work_order': 'logbook',
        'asset': 'asset_nodes',
        'pm_schedule': 'pm_schedules',
        'inventory': 'inventory_items',
    }
    statuses = ['active'] * 9 + ['error'] * 1
    rows = []
    for i in range(30):
        et = random.choice(entity_types)
        sys_type = random.choice(['sap_pm'] * 4 + ['generic'])
        synced_at = now - timedelta(days=random.uniform(0, 30), hours=random.uniform(0, 24))
        ext_id_prefix = 'AUFNR' if sys_type == 'sap_pm' else 'CSV'
        rows.append({
            'hive_id': LUCENA_HIVE,
            'system_type': sys_type,
            'external_id': f'{ext_id_prefix}-{40000 + i:06d}',
            'entity_type': et,
            'workhive_table': workhive_tables[et],
            'status': random.choice(['Open', 'Open', 'Closed', 'Closed', 'Cancelled']),
            'sync_payload': {},
            'last_synced_at': synced_at.isoformat(),
            'sync_status': random.choice(statuses),
        })
    db.table('external_sync').insert(rows).execute()
    print(f'  external_sync: {len(rows)} rows')


def seed_sensor_topics(db, now):
    db.table('sensor_topic_map').delete().eq('hive_id', LUCENA_HIVE).execute()
    asset_pool = db.table('asset_nodes').select('id, tag, name').eq('hive_id', LUCENA_HIVE).eq('level', 'equipment').eq('lifecycle', 'active').execute().data
    if not asset_pool:
        print('  sensor_topic_map: SKIPPED (no equipment assets)')
        return
    sensor_specs = [
        ('vibration_mms', 'mm/s'),
        ('motor_amps', 'A'),
        ('bearing_temp_c', '°C'),
        ('discharge_psi', 'psi'),
        ('flow_lpm', 'lpm'),
        ('runtime_hrs', 'h'),
    ]
    rows = []
    for asset, (param, unit) in zip(asset_pool[:6], sensor_specs):
        rows.append({
            'hive_id': LUCENA_HIVE,
            'topic_pattern': f'plant/lucena/sensors/{asset["tag"]}/{param}',
            'asset_id': asset['id'],
            'parameter': param,
            'unit': unit,
            'scale': 1,
            'offset_value': 0,
            'active': True,
        })
    if rows:
        db.table('sensor_topic_map').insert(rows).execute()
    print(f'  sensor_topic_map: {len(rows)} rows')


def seed_gateway_audit(db, now):
    sha = lambda s: hashlib.sha256(s.encode()).hexdigest()
    routes = [
        ('amc-orchestrator',       'POST'),
        ('voice-journal-agent',    'POST'),
        ('visual-defect-capture',  'POST'),
        ('ai-gateway',             'POST'),
        ('export-hive-data',       'POST'),
        ('compute-anomaly-signals','POST'),
        ('knowledge-search',       'POST'),
        ('failure-signature-scan', 'POST'),
    ]
    workers = ['Pablo Aguilar', 'Maria Santos', 'Juan Reyes', 'Lola Cruz']
    cutoff = now - timedelta(days=7)
    rows = []
    for _ in range(60):
        route, method = random.choice(routes)
        worker = random.choice(workers)
        r = random.random()
        if r < 0.88:   status, err = 200, None
        elif r < 0.94: status, err = 401, 'unauthenticated'
        elif r < 0.98: status, err = 429, 'rate_limited'
        else:          status, err = 500, 'upstream_error'
        ts = cutoff + timedelta(seconds=random.uniform(0, 7 * 86400))
        rows.append({
            'hive_id': LUCENA_HIVE,
            'worker_name': worker,
            'route': route,
            'request_id': sha(f'{route}-{worker}-{ts.isoformat()}')[:24],
            'method': method,
            'status_code': status,
            'latency_ms': random.randint(120, 2400),
            'ip_hash': sha(f'192.168.{random.randint(1,254)}.{random.randint(1,254)}')[:32],
            'ua_fingerprint': sha('Mozilla/5.0 Workhive PWA')[:32],
            'error_class': err,
            'created_at': ts.isoformat(),
        })
    db.table('gateway_audit_log').delete() \
        .eq('hive_id', LUCENA_HIVE) \
        .gte('created_at', cutoff.isoformat()).execute()
    db.table('gateway_audit_log').insert(rows).execute()
    print(f'  gateway_audit_log: {len(rows)} rows')


def main():
    db = get_client()
    now = datetime.now(timezone.utc)
    print('Seeding plant-connections for Lucena…')
    seed_retention(db, now)
    seed_sso(db, now)
    seed_integrations(db, now)
    seed_external_sync(db, now)
    seed_sensor_topics(db, now)
    seed_gateway_audit(db, now)
    print('Done.')


if __name__ == '__main__':
    main()
