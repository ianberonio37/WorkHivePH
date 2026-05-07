"""CMMS Config Seeder -- seeds integration_configs + api_keys for a hive.

Called by client_hive.py after the bridge step so that:
  - integrations.html Live Sync tab has a pre-configured SAP/Maximo/Generic entry
  - integrations.html API Keys tab has one key to test revocation (Scenario I)

Can also be called standalone via POST /api/cmms/seed-integration-config
to attach a config to any already-existing hive.
"""

import hashlib
import secrets


# Mock server endpoints for each CMMS type (local Flask server).
# Edge functions run in Docker and cannot reach 127.0.0.1 — use host.docker.internal
# so the Deno container can reach the host's Flask server on port 5000.
MOCK_ENDPOINTS = {
    "sap_pm":  "http://host.docker.internal:5000/mock/sap/odata/WorkOrders",
    "maximo":  "http://host.docker.internal:5000/mock/maximo/oslc/os/mxwo",
    "generic": "http://host.docker.internal:5000/mock/generic/api/work-orders",
}

# Default field maps for each CMMS type -- mirrors cmms-sync/index.ts STATUS_MAP.
FIELD_MAPS = {
    "sap_pm": {
        "external_id":      "AUFNR",
        "machine":          "EQUNR",
        "status":           "ISTAT",
        "maintenance_type": "AUART",
        "problem":          "LTXT",
        "actual_hours":     "ARBEI",
        "created_at":       "ERDAT",
        "closed_at":        "RUCKMDAT",
    },
    "maximo": {
        "external_id":      "WONUM",
        "machine":          "ASSETNUM",
        "status":           "STATUS",
        "maintenance_type": "WORKTYPE",
        "problem":          "DESCRIPTION",
        "actual_hours":     "ACTLABHRS",
        "created_at":       "REPORTDATE",
        "closed_at":        "ACTFINISH",
    },
    "generic": {
        "external_id":      "work_order_no",
        "machine":          "asset_tag",
        "status":           "status",
        "maintenance_type": "type",
        "problem":          "description",
        "actual_hours":     "actual_hours",
        "created_at":       "created_date",
        "closed_at":        "closed_date",
    },
}

LABEL_MAP = {
    "sap_pm":  "SAP PM (Local Mock)",
    "maximo":  "IBM Maximo (Local Mock)",
    "generic": "Generic REST (Local Mock)",
}


def seed_integration_config(
    client,
    hive_id: str,
    cmms_type: str = "sap_pm",
    replace: bool = True,
    log=None,
) -> dict:
    """Seed integration_configs and api_keys rows for a hive.

    Args:
        client:    Supabase Python client.
        hive_id:   UUID of the target hive.
        cmms_type: 'sap_pm' | 'maximo' | 'generic'.
        replace:   If True, delete existing test configs/keys for this hive first.
        log:       Optional callable(str) for progress messages.

    Returns:
        {
            "config_id":   UUID string or None,
            "key_id":      UUID string or None,
            "key_prefix":  "wh_" + 8 hex chars (shown in Active Keys list),
            "endpoint_url": mock endpoint URL,
        }
    """
    def _log(msg):
        if log:
            log(msg)

    endpoint_url = MOCK_ENDPOINTS.get(cmms_type, MOCK_ENDPOINTS["sap_pm"])
    field_map    = FIELD_MAPS.get(cmms_type, FIELD_MAPS["sap_pm"])
    label        = LABEL_MAP.get(cmms_type, cmms_type)

    # ── 1. integration_configs ────────────────────────────────────────────────
    if replace:
        try:
            client.table("integration_configs").delete() \
                .eq("hive_id", hive_id) \
                .like("label", "%(Local Mock)") \
                .execute()
        except Exception:
            pass

    config_row = {
        "hive_id":      hive_id,
        "system_type":  cmms_type,
        "label":        label,
        "endpoint_url": endpoint_url,
        "auth_method":  "api_key",
        "field_map":    field_map,
        "sync_freq":    "manual",
        "enabled":      True,
    }

    config_id = None
    try:
        res = client.table("integration_configs").insert(config_row).execute()
        config_id = res.data[0]["id"] if res.data else None
        _log(f"  integration_configs: {config_id[:8] if config_id else 'FAILED'} "
             f"({cmms_type} -> {endpoint_url})")
    except Exception as e:
        _log(f"  integration_configs FAILED: {e}")

    # ── 2. api_keys ───────────────────────────────────────────────────────────
    # Generate a deterministic-looking test key:
    #   raw  = "wh_" + 32 random hex chars  (35 chars total)
    #   prefix = first 11 chars shown in UI  (e.g. wh_a1b2c3d4e)
    #   hash   = sha256(raw) stored in DB
    if replace:
        try:
            client.table("api_keys").delete() \
                .eq("hive_id", hive_id) \
                .eq("label", "Seeder Test Key") \
                .execute()
        except Exception:
            pass

    raw_key    = "wh_" + secrets.token_hex(16)
    key_prefix = raw_key[:11]
    key_hash   = hashlib.sha256(raw_key.encode()).hexdigest()

    key_id = None
    try:
        res = client.table("api_keys").insert({
            "hive_id":    hive_id,
            "key_prefix": key_prefix,
            "key_hash":   key_hash,
            "label":      "Seeder Test Key",
            "enabled":    True,
        }).execute()
        key_id = res.data[0]["id"] if res.data else None
        _log(f"  api_keys: {key_id[:8] if key_id else 'FAILED'} (prefix={key_prefix})")
    except Exception as e:
        _log(f"  api_keys FAILED: {e}")

    return {
        "config_id":    config_id,
        "key_id":       key_id,
        "key_prefix":   key_prefix,
        "endpoint_url": endpoint_url,
    }
