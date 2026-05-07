"""CMMS Syncer -- Phase 4: Reference Sync Implementation.

Makes HTTP calls to the mock CMMS API (or a real CMMS when configured with
a different base_url) and imports the results into external_sync.

This is both the seeder's Tier 2 test harness AND the reference
implementation for WorkHive's scheduled sync Edge Function.

Requires the Flask server to be running on MOCK_BASE_URL (default 5000)
when calling the mock API endpoints.
"""

from datetime import datetime, timezone

import requests

from data.cmms_templates import (
    SAP_ISTAT_TO_STATUS, SAP_AUART_TO_TYPE,
    MAXIMO_STATUS_TO_STATUS, MAXIMO_WORKTYPE_TO_TYPE,
    GENERIC_STATUS_TO_STATUS, GENERIC_TYPE_TO_TYPE,
)
from seeders.cmms_importer import import_raw_rows

MOCK_BASE_URL = "http://127.0.0.1:5000"


class CMMSSyncer:
    """HTTP sync client for the mock CMMS API (or a real CMMS endpoint).

    Args:
        cmms_type: 'sap_pm' | 'maximo' | 'generic'
        base_url:  Root URL of the CMMS API (default: mock server at port 5000)
        timeout:   HTTP request timeout in seconds
    """

    def __init__(self, cmms_type: str, base_url: str = MOCK_BASE_URL, timeout: int = 15):
        self.cmms_type = cmms_type
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.request_count = 0

    # -----------------------------------------------------------------------
    # Connectivity check
    # -----------------------------------------------------------------------

    def is_reachable(self) -> tuple[bool, str]:
        """Return (True, "") or (False, error_message)."""
        try:
            requests.get(self.base_url + "/api/cmms/status", timeout=5)
            return True, ""
        except requests.exceptions.ConnectionError:
            return False, f"Cannot reach {self.base_url} -- is the seeder server running?"
        except Exception as e:
            return False, str(e)

    # -----------------------------------------------------------------------
    # HTTP helpers
    # -----------------------------------------------------------------------

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = requests.get(self.base_url + path, params=params, timeout=self.timeout)
        resp.raise_for_status()
        self.request_count += 1
        return resp.json()

    def _post(self, path: str, payload: dict | None = None) -> dict:
        resp = requests.post(self.base_url + path, json=payload or {}, timeout=self.timeout)
        resp.raise_for_status()
        self.request_count += 1
        return resp.json()

    def _patch(self, path: str, payload: dict | None = None) -> dict:
        resp = requests.patch(self.base_url + path, json=payload or {}, timeout=self.timeout)
        resp.raise_for_status()
        self.request_count += 1
        return resp.json()

    # -----------------------------------------------------------------------
    # Fetch one page of records
    # -----------------------------------------------------------------------

    def fetch_work_orders_page(self, top: int = 100, skip: int = 0,
                               updated_after: str | None = None) -> list:
        if self.cmms_type == "sap_pm":
            params = {"$top": top, "$skip": skip}
            if updated_after:
                params["$filter"] = f"ERDAT ge '{updated_after[:10]}'"
            return self._get("/mock/sap/odata/WorkOrders", params)["d"]["results"]

        elif self.cmms_type == "maximo":
            params = {"oslc.pageSize": top, "oslc.pageIndex": skip // top + 1}
            if updated_after:
                params["oslc.where"] = f'reportdate>="{updated_after[:10]}"'
            return self._get("/mock/maximo/oslc/os/mxwo", params)["rdfs:member"]

        else:  # generic
            params = {"limit": top, "offset": skip}
            if updated_after:
                params["updated_after"] = updated_after[:10]
            return self._get("/mock/generic/api/work-orders", params)["data"]

    def fetch_assets_page(self, top: int = 100, skip: int = 0, **_) -> list:
        if self.cmms_type == "sap_pm":
            return self._get("/mock/sap/odata/Assets", {"$top": top, "$skip": skip})["d"]["results"]
        elif self.cmms_type == "maximo":
            return self._get("/mock/maximo/oslc/os/mxasset",
                             {"oslc.pageSize": top, "oslc.pageIndex": skip // top + 1})["rdfs:member"]
        else:
            return self._get("/mock/generic/api/assets", {"limit": top, "offset": skip})["data"]

    # -----------------------------------------------------------------------
    # Paginated fetch (follows all pages until empty or partial page)
    # -----------------------------------------------------------------------

    def fetch_all_pages(self, fetch_fn, page_size: int = 100,
                        log=None, **kwargs) -> tuple[list, int]:
        """Fetch all pages using fetch_fn. Returns (all_rows, pages_fetched)."""
        all_rows, skip, pages = [], 0, 0
        while True:
            page = fetch_fn(top=page_size, skip=skip, **kwargs)
            pages += 1
            if not page:
                break
            all_rows.extend(page)
            skip += len(page)
            if log:
                log(f"    page {pages}: {len(page)} rows (total so far: {len(all_rows)})")
            if len(page) < page_size:
                break
        return all_rows, pages

    # -----------------------------------------------------------------------
    # Normalization: CMMS raw record -> external_sync row
    # -----------------------------------------------------------------------

    def normalize_work_order(self, wo: dict, hive_id=None) -> dict:
        if self.cmms_type == "sap_pm":
            return {
                "hive_id":        hive_id,
                "system_type":    "sap_pm",
                "external_id":    wo.get("AUFNR"),
                "entity_type":    "work_order",
                "workhive_table": "logbook",
                "status":         SAP_ISTAT_TO_STATUS.get(wo.get("ISTAT", ""), "Open"),
                "sync_payload": {
                    "machine":          wo.get("EQUNR", ""),
                    "description":      wo.get("LTXT", ""),
                    "maintenance_type": SAP_AUART_TO_TYPE.get(wo.get("AUART", ""), "Breakdown / Corrective"),
                    "actual_hours":     float(wo.get("ARBEI") or 0),
                    "created_at":       wo.get("ERDAT", ""),
                    "closed_at":        wo.get("RUCKMDAT") or None,
                },
                "sync_status": "active",
                "last_synced_at": datetime.now(timezone.utc).isoformat(),
            }
        elif self.cmms_type == "maximo":
            return {
                "hive_id":        hive_id,
                "system_type":    "maximo",
                "external_id":    wo.get("WONUM"),
                "entity_type":    "work_order",
                "workhive_table": "logbook",
                "status":         MAXIMO_STATUS_TO_STATUS.get(wo.get("STATUS", ""), "Open"),
                "sync_payload": {
                    "machine":          wo.get("ASSETNUM", ""),
                    "description":      wo.get("DESCRIPTION", ""),
                    "maintenance_type": MAXIMO_WORKTYPE_TO_TYPE.get(wo.get("WORKTYPE", ""), "Breakdown / Corrective"),
                    "actual_hours":     float(wo.get("ACTLABHRS") or 0),
                    "created_at":       wo.get("REPORTDATE", ""),
                    "closed_at":        wo.get("ACTFINISH") or None,
                },
                "sync_status": "active",
                "last_synced_at": datetime.now(timezone.utc).isoformat(),
            }
        else:  # generic
            return {
                "hive_id":        hive_id,
                "system_type":    "generic",
                "external_id":    wo.get("work_order_no"),
                "entity_type":    "work_order",
                "workhive_table": "logbook",
                "status":         GENERIC_STATUS_TO_STATUS.get(wo.get("status", ""), "Open"),
                "sync_payload": {
                    "machine":          wo.get("asset_tag", ""),
                    "description":      wo.get("description", ""),
                    "maintenance_type": GENERIC_TYPE_TO_TYPE.get(wo.get("type", ""), "Breakdown / Corrective"),
                    "actual_hours":     float(wo.get("actual_hours") or 0),
                    "created_at":       wo.get("created_date", ""),
                    "closed_at":        wo.get("closed_date") or None,
                },
                "sync_status": "active",
                "last_synced_at": datetime.now(timezone.utc).isoformat(),
            }

    def normalize_asset(self, asset: dict, hive_id=None) -> dict:
        if self.cmms_type == "sap_pm":
            return {
                "hive_id": hive_id, "system_type": "sap_pm",
                "external_id": asset.get("EQUNR"), "entity_type": "asset",
                "workhive_table": "assets", "status": "active",
                "sync_payload": {"name": asset.get("EQKTX", ""), "location": asset.get("ILOAN", ""),
                                 "manufacturer": asset.get("HERST", ""), "model": asset.get("TYPBZ", "")},
                "sync_status": "active",
                "last_synced_at": datetime.now(timezone.utc).isoformat(),
            }
        elif self.cmms_type == "maximo":
            return {
                "hive_id": hive_id, "system_type": "maximo",
                "external_id": asset.get("ASSETNUM"), "entity_type": "asset",
                "workhive_table": "assets", "status": "active",
                "sync_payload": {"name": asset.get("DESCRIPTION", ""), "location": asset.get("LOCATION", ""),
                                 "manufacturer": asset.get("MANUFACTURER", ""), "model": asset.get("MODEL", "")},
                "sync_status": "active",
                "last_synced_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            return {
                "hive_id": hive_id, "system_type": "generic",
                "external_id": asset.get("asset_tag"), "entity_type": "asset",
                "workhive_table": "assets", "status": "active",
                "sync_payload": {"name": asset.get("name", ""), "location": asset.get("location", ""),
                                 "manufacturer": asset.get("manufacturer", ""), "model": asset.get("model", "")},
                "sync_status": "active",
                "last_synced_at": datetime.now(timezone.utc).isoformat(),
            }

    # -----------------------------------------------------------------------
    # High-level sync methods
    # -----------------------------------------------------------------------

    def sync_work_orders(self, client, hive_id=None, page_size: int = 100,
                         updated_after: str | None = None, log=None) -> dict:
        """Fetch all work order pages and upsert to external_sync."""
        raw, pages = self.fetch_all_pages(
            self.fetch_work_orders_page,
            page_size=page_size,
            updated_after=updated_after,
            log=log,
        )
        rows = [self.normalize_work_order(wo, hive_id) for wo in raw]
        result = import_raw_rows(client, rows)
        result["fetched"] = len(raw)
        result["pages"]   = pages
        result["request_count"] = self.request_count
        return result

    def sync_assets(self, client, hive_id=None, page_size: int = 100,
                    log=None) -> dict:
        """Fetch all asset pages and upsert to external_sync."""
        raw, pages = self.fetch_all_pages(self.fetch_assets_page, page_size=page_size, log=log)
        rows = [self.normalize_asset(a, hive_id) for a in raw]
        result = import_raw_rows(client, rows)
        result["fetched"] = len(raw)
        result["pages"]   = pages
        return result

    # -----------------------------------------------------------------------
    # Push methods (WorkHive -> CMMS)
    # -----------------------------------------------------------------------

    def push_completion(self, external_id: str, payload: dict) -> dict:
        """Push a completed work order back to the mock CMMS."""
        if self.cmms_type == "sap_pm":
            return self._post(f"/mock/sap/odata/WorkOrders/{external_id}/complete", payload)
        elif self.cmms_type == "maximo":
            return self._post("/mock/maximo/oslc/os/mxwo", {"WONUM": external_id, **payload})
        else:
            return self._post("/mock/generic/api/work-orders/complete",
                              {"work_order_no": external_id, **payload})

    def push_pm_order(self, payload: dict) -> dict | None:
        """Push an AI-generated PM order back to SAP (intelligence -> CMMS)."""
        if self.cmms_type == "sap_pm":
            return self._post("/mock/sap/odata/PMOrders", payload)
        return None

    def get_push_log(self) -> list:
        """Return what the mock CMMS received from WorkHive."""
        return self._get("/api/cmms/mock/log").get("push_log", [])

    def reset_mock_log(self):
        """Clear the mock API request and push logs."""
        requests.post(self.base_url + "/api/cmms/mock/reset", timeout=5)
