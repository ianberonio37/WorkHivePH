"""CMMS Dataset Generator -- Phase 0: Dual-State Data Foundation.

Generates a realistic fake company CMMS dataset and computes the expected
WorkHive state after a successful sync. Every record exists on both sides
so agreement checks can compare them field-by-field.

Usage:
    from seeders.cmms import CMMSDataset
    ds = CMMSDataset(industry="food_processing", size="medium", cmms_type="sap_pm")
    ds.generate()

    ds.assets          # CMMS-format asset records
    ds.work_orders     # CMMS-format work order records
    ds.pm_schedules    # CMMS-format PM schedule records
    ds.inventory       # CMMS-format inventory records

    ds.expected_logbook    # WorkHive-format logbook rows expected after sync
    ds.expected_assets     # WorkHive-format asset rows
    ds.expected_inventory  # WorkHive-format inventory rows
    ds.sync_map            # Agreement map: {cmms_id, expected_wh_status, entity_type}
"""

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from data.ph_equipment import EQUIPMENT_CATALOG
from data.ph_faults import FAULTS_BY_CATEGORY
from data.cmms_templates import (
    DATASET_SIZES, HISTORY_DAYS,
    INDUSTRY_PROFILES, DEFAULT_INDUSTRY,
    PM_TASKS_BY_CATEGORY,
    SAP_ISTAT_TO_STATUS, SAP_AUART_TO_TYPE, SAP_PRIOK_TO_PRIORITY,
    SAP_CLOSED_STATUSES,
    MAXIMO_STATUS_TO_STATUS, MAXIMO_WORKTYPE_TO_TYPE,
    GENERIC_TYPE_TO_TYPE, GENERIC_STATUS_TO_STATUS,
    unit_for_part,
)
from .utils import random_timestamp_in_last_n_days, to_iso


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sap_aufnr(counter: int) -> str:
    """12-digit zero-padded SAP work order number."""
    return str(counter).zfill(12)


def _sap_matnr(counter: int) -> str:
    """10-digit zero-padded SAP material number."""
    return str(counter).zfill(10)


def _maximo_wonum(counter: int) -> str:
    return f"WO-{counter:06d}"


def _generic_wono(counter: int) -> str:
    return f"WRK-{counter:05d}"


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _dt_str(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_parts_catalog(rng: random.Random) -> list[dict]:
    """Collect unique part names from all fault templates and assign IDs."""
    seen = {}
    counter = 1000
    for faults in FAULTS_BY_CATEGORY.values():
        for fault in faults:
            for part_name in fault.get("parts_used", []):
                if part_name not in seen:
                    seen[part_name] = counter
                    counter += 1
    # Also add generic consumables
    generics = [
        "Grease NLGI 2", "Lube oil 20L SAE 15W-40", "PTFE tape",
        "Cable tie 300mm", "Cable gland 25mm", "Wire terminal lug",
        "O-ring set", "V-belt SPB 1700", "Seal kit", "Gasket set",
    ]
    for name in generics:
        if name not in seen:
            seen[name] = counter
            counter += 1
    result = []
    for name, num in seen.items():
        qty = rng.randint(5, 50)
        reorder = rng.randint(2, 10)
        result.append({
            "_name": name,
            "_num": num,
            "_unit": unit_for_part(name),
            "_qty": qty,
            "_reorder": reorder,
        })
    return result


# ---------------------------------------------------------------------------
# Main dataset class
# ---------------------------------------------------------------------------

class CMMSDataset:
    """Dual-state CMMS dataset: CMMS side + expected WorkHive side.

    Args:
        industry:  Key from INDUSTRY_PROFILES ("food_processing", "cement", etc.)
        size:      "small", "medium", or "large"
        cmms_type: "sap_pm", "maximo", or "generic"
        seed:      Random seed for reproducibility (None = random each time)
    """

    def __init__(
        self,
        industry: str = DEFAULT_INDUSTRY,
        size: str = "medium",
        cmms_type: str = "sap_pm",
        seed: Optional[int] = None,
    ):
        self.industry = industry if industry in INDUSTRY_PROFILES else DEFAULT_INDUSTRY
        self.size = size if size in DATASET_SIZES else "medium"
        self.cmms_type = cmms_type if cmms_type in ("sap_pm", "maximo", "generic") else "sap_pm"
        self.seed = seed if seed is not None else random.randint(1000, 9999)
        self.rng = random.Random(self.seed)

        self._profile = INDUSTRY_PROFILES[self.industry]
        self._counts = DATASET_SIZES[self.size]
        self._history_days = HISTORY_DAYS[self.size]
        self._parts_catalog: list[dict] = []

        # CMMS-format records (what the external system holds)
        self.assets: list[dict] = []
        self.work_orders: list[dict] = []
        self.pm_schedules: list[dict] = []
        self.inventory: list[dict] = []

        # WorkHive-format expected records (what should exist after sync)
        self.expected_assets: list[dict] = []
        self.expected_logbook: list[dict] = []
        self.expected_pm: list[dict] = []
        self.expected_inventory: list[dict] = []

        # Agreement map: [{cmms_id, entity_type, cmms_status, expected_wh_status}]
        self.sync_map: list[dict] = []

        self._generated = False

    # -----------------------------------------------------------------------
    # Public interface
    # -----------------------------------------------------------------------

    def generate(self) -> "CMMSDataset":
        """Generate all data. Safe to call multiple times (idempotent)."""
        if self._generated:
            return self
        self._parts_catalog = _build_parts_catalog(self.rng)
        self._gen_assets()
        self._gen_inventory()
        self._gen_work_orders()
        self._gen_pm_schedules()
        self._generated = True
        return self

    def summary(self) -> dict:
        """Quick stats about what was generated."""
        return {
            "industry":    self._profile["label"],
            "cmms_type":   self.cmms_type,
            "size":        self.size,
            "seed":        self.seed,
            "assets":      len(self.assets),
            "work_orders": len(self.work_orders),
            "pm_schedules":len(self.pm_schedules),
            "inventory":   len(self.inventory),
            "expected_logbook":   len(self.expected_logbook),
            "expected_assets":    len(self.expected_assets),
            "expected_inventory": len(self.expected_inventory),
            "sync_map_entries":   len(self.sync_map),
        }

    # -----------------------------------------------------------------------
    # Asset generation
    # -----------------------------------------------------------------------

    def _gen_assets(self):
        n = self._counts["assets"]
        allowed_cats = set(self._profile["equipment_categories"])
        pool = [e for e in EQUIPMENT_CATALOG if e["category"] in allowed_cats]
        if not pool:
            pool = EQUIPMENT_CATALOG

        tag_counters: dict[str, int] = {}
        now = datetime.now(timezone.utc)

        for _ in range(n):
            arch = self.rng.choice(pool)
            prefix = arch["tag_prefix"]
            tag_counters[prefix] = tag_counters.get(prefix, 0) + 1
            tag_num = tag_counters[prefix]
            tag_id = f"{prefix}-{tag_num:03d}"

            install_days_ago = self.rng.randint(365, 365 * 8)
            install_dt = now - timedelta(days=install_days_ago)
            location = self.rng.choice(self._profile["locations"])
            serial = f"SN-{prefix}-{tag_num:04d}-{install_dt.year}"

            cmms_rec = self._make_asset_record(
                tag_id=tag_id,
                description=f"{arch['make']} {arch['model']} {arch['spec']}",
                category=arch["category"],
                location=location,
                install_date=install_dt,
                manufacturer=arch["make"],
                model=arch["model"],
                serial=serial,
            )
            self.assets.append(cmms_rec)

            # WorkHive expected side
            wh_rec = {
                "_external_id": tag_id,
                "_system_type": self.cmms_type,
                "name": f"{arch['category']} -- {tag_id}",
                "category": arch["category"],
                "location": location,
                "make": arch["make"],
                "model": arch["model"],
                "serial_no": serial,
                "discipline": arch.get("discipline", "Mechanical"),
            }
            self.expected_assets.append(wh_rec)
            self.sync_map.append({
                "cmms_id":          tag_id,
                "entity_type":      "asset",
                "cmms_status":      "active",
                "expected_wh_status": "active",
            })

    def _make_asset_record(self, tag_id, description, category, location,
                           install_date, manufacturer, model, serial) -> dict:
        profile = self._profile
        if self.cmms_type == "sap_pm":
            return {
                "EQUNR": tag_id,
                "EQKTX": description,
                "EQART": category[:4].upper(),
                "ILOAN": location,
                "INBDT": _date_str(install_date),
                "HERST": manufacturer,
                "TYPBZ": model,
                "TIDNR": serial,
                "KOSTL": profile["cost_center"],
                "WERKS": profile["plant_code"],
            }
        elif self.cmms_type == "maximo":
            return {
                "ASSETNUM":    tag_id,
                "DESCRIPTION": description,
                "ASSETTYPE":   category[:8].upper(),
                "LOCATION":    location,
                "INSTALLDATE": _date_str(install_date),
                "MANUFACTURER": manufacturer,
                "MODEL":        model,
                "SERIALNUM":    serial,
                "SITEID":       profile["site_id"],
            }
        else:  # generic
            return {
                "asset_tag":      tag_id,
                "name":           description,
                "category":       category,
                "location":       location,
                "installed_date": _date_str(install_date),
                "manufacturer":   manufacturer,
                "model":          model,
                "serial_no":      serial,
            }

    # -----------------------------------------------------------------------
    # Inventory generation
    # -----------------------------------------------------------------------

    def _gen_inventory(self):
        n = self._counts["parts"]
        sample = self.rng.sample(self._parts_catalog, min(n, len(self._parts_catalog)))
        profile = self._profile
        counter = 1

        for p in sample:
            # Inject realistic failure: 15% of parts below reorder point
            is_low = self.rng.random() < 0.15
            qty = self.rng.randint(1, p["_reorder"] - 1) if is_low else p["_qty"]

            cmms_rec = self._make_inventory_record(
                num=p["_num"],
                description=p["_name"],
                unit=p["_unit"],
                qty=qty,
                reorder=p["_reorder"],
                counter=counter,
            )
            self.inventory.append(cmms_rec)

            wh_rec = {
                "_external_id": str(p["_num"]),
                "_system_type": self.cmms_type,
                "name":         p["_name"],
                "unit":         p["_unit"].lower(),
                "qty_on_hand":  qty,
                "reorder_point": p["_reorder"],
                "is_low_stock": is_low,
            }
            self.expected_inventory.append(wh_rec)
            self.sync_map.append({
                "cmms_id":            str(p["_num"]),
                "entity_type":        "inventory",
                "cmms_status":        "low" if is_low else "ok",
                "expected_wh_status": "low" if is_low else "ok",
            })
            counter += 1

    def _make_inventory_record(self, num, description, unit, qty, reorder, counter) -> dict:
        profile = self._profile
        if self.cmms_type == "sap_pm":
            return {
                "MATNR": _sap_matnr(num),
                "MAKTX": description,
                "MEINS": unit,
                "MENGE": qty,
                "MINBE": reorder,
                "EISBE": max(1, reorder - 1),
                "WERKS": profile["plant_code"],
                "LGORT": "WH01",
            }
        elif self.cmms_type == "maximo":
            return {
                "ITEMNUM":     str(num).zfill(8),
                "DESCRIPTION": description,
                "ORDERUNIT":   unit,
                "CURBAL":      qty,
                "REORDER":     reorder,
                "SITEID":      profile["site_id"],
                "LOCATION":    "MAIN-STORE",
            }
        else:
            return {
                "part_number":  f"PRT-{num}",
                "description":  description,
                "unit":         unit.lower(),
                "qty_on_hand":  qty,
                "reorder_point": reorder,
                "location":     "Main Storeroom",
            }

    # -----------------------------------------------------------------------
    # Work order generation
    # -----------------------------------------------------------------------

    def _gen_work_orders(self):
        n = self._counts["work_orders"]
        assets = self.assets
        if not assets:
            return

        # Build fault pool scoped to relevant equipment categories
        allowed_cats = set(self._profile["equipment_categories"])
        fault_pool = []
        for cat, faults in FAULTS_BY_CATEGORY.items():
            if cat in allowed_cats:
                fault_pool.extend([(cat, f) for f in faults])
        if not fault_pool:
            for faults in FAULTS_BY_CATEGORY.values():
                fault_pool.extend(faults)

        # Inject repeat-failure pattern: 20% of assets get 30% of all WOs
        n_repeat_assets = max(1, len(assets) // 5)
        repeat_assets = self.rng.sample(assets, n_repeat_assets)
        repeat_asset_ids = {self._asset_id(a) for a in repeat_assets}

        counter = 10000
        now = datetime.now(timezone.utc)

        for i in range(n):
            counter += 1

            # Pick asset -- repeat assets get higher frequency
            if self.rng.random() < 0.30 and repeat_asset_ids:
                asset = self.rng.choice(repeat_assets)
            else:
                asset = self.rng.choice(assets)

            asset_id = self._asset_id(asset)

            # Pick fault
            if fault_pool:
                _, fault = self.rng.choice(fault_pool)
            else:
                fault = {
                    "problem": "Routine inspection finding",
                    "root_cause": "Normal wear",
                    "action": "Maintenance performed as scheduled",
                    "parts_used": [],
                    "severity": "low",
                }

            # Determine order type and status
            is_breakdown = fault["severity"] == "high" or self.rng.random() < 0.35
            is_closed = self.rng.random() < 0.70

            created_dt = random_timestamp_in_last_n_days(self._history_days, self.rng)

            if is_closed:
                hours_to_close = self.rng.uniform(1.0, 48.0)
                closed_dt = created_dt + timedelta(hours=hours_to_close)
                if closed_dt > now:
                    closed_dt = now - timedelta(hours=1)
                actual_hours = round(self.rng.uniform(0.5, 16.0), 1)
            else:
                closed_dt = None
                actual_hours = 0.0

            description = f"{fault['problem']} -- {fault['root_cause']}"

            cmms_rec = self._make_wo_record(
                counter=counter,
                asset_id=asset_id,
                asset=asset,
                description=description,
                is_breakdown=is_breakdown,
                is_closed=is_closed,
                created_dt=created_dt,
                closed_dt=closed_dt,
                actual_hours=actual_hours,
                severity=fault["severity"],
            )
            self.work_orders.append(cmms_rec)

            # WorkHive expected side
            cmms_status = self._wo_cmms_status(cmms_rec)
            wh_status = self._cmms_status_to_wh(cmms_status)
            wh_type = ("Breakdown / Corrective" if is_breakdown
                       else "Preventive Maintenance")

            wh_logbook = {
                "_external_id": self._wo_id(cmms_rec),
                "_system_type": self.cmms_type,
                "machine":           asset_id,
                "problem":           fault["problem"],
                "root_cause":        fault["root_cause"],
                "action":            fault["action"],
                "maintenance_type":  wh_type,
                "status":            wh_status,
                "downtime_hours":    actual_hours if is_breakdown else 0,
                "created_at":        to_iso(created_dt),
                "closed_at":         to_iso(closed_dt) if closed_dt else None,
            }
            self.expected_logbook.append(wh_logbook)
            self.sync_map.append({
                "cmms_id":            self._wo_id(cmms_rec),
                "entity_type":        "work_order",
                "cmms_status":        cmms_status,
                "expected_wh_status": wh_status,
            })

    def _make_wo_record(self, counter, asset_id, asset, description,
                        is_breakdown, is_closed, created_dt, closed_dt,
                        actual_hours, severity) -> dict:
        profile = self._profile
        priority_num = {"high": "1", "medium": "3", "low": "4"}.get(severity, "3")

        if self.cmms_type == "sap_pm":
            auart = "PM02" if is_breakdown else "PM01"
            istat = "I0045" if is_closed else "I0002"
            return {
                "AUFNR":    _sap_aufnr(counter),
                "AUART":    auart,
                "LTXT":     description,
                "ISTAT":    istat,
                "ARBEI":    actual_hours,
                "ERDAT":    _date_str(created_dt),
                "AEDAT":    _date_str(closed_dt or created_dt),
                "RUCKMDAT": _date_str(closed_dt) if closed_dt else "",
                "EQUNR":    asset_id,
                "KOSTL":    profile["cost_center"],
                "PRIOK":    priority_num,
                "ARBPL":    "MAINT-01",
                "QMNUM":    f"QM-{counter}" if is_breakdown else "",
            }
        elif self.cmms_type == "maximo":
            worktype = "CM" if is_breakdown else "PM"
            status = "CLOSE" if is_closed else "APPR"
            return {
                "WONUM":         _maximo_wonum(counter),
                "DESCRIPTION":   description,
                "STATUS":        status,
                "WORKTYPE":      worktype,
                "ACTLABHRS":     actual_hours,
                "REPORTDATE":    _dt_str(created_dt),
                "TARGSTARTDATE": _date_str(created_dt),
                "ACTFINISH":     _dt_str(closed_dt) if closed_dt else "",
                "ASSETNUM":      asset_id,
                "LOCATION":      self._asset_location(asset),
                "PRIORITY":      int(priority_num),
                "GLACCOUNT":     profile["cost_center"],
            }
        else:  # generic
            wo_type = "corrective" if is_breakdown else "preventive"
            status = "closed" if is_closed else "open"
            priority = {"1": "critical", "2": "high", "3": "medium", "4": "low"}.get(
                priority_num, "medium"
            )
            return {
                "work_order_no":  _generic_wono(counter),
                "description":    description,
                "type":           wo_type,
                "status":         status,
                "actual_hours":   actual_hours,
                "created_date":   _dt_str(created_dt),
                "closed_date":    _dt_str(closed_dt) if closed_dt else None,
                "asset_tag":      asset_id,
                "location":       self._asset_location(asset),
                "priority":       priority,
                "reported_by":    "system",
            }

    # -----------------------------------------------------------------------
    # PM schedule generation
    # -----------------------------------------------------------------------

    def _gen_pm_schedules(self):
        n = self._counts["pm_schedules"]
        if not self.assets:
            return
        # Pick a random subset of assets to have PM schedules
        pm_assets = self.rng.sample(self.assets, min(n, len(self.assets)))
        now = datetime.now(timezone.utc)
        counter = 1

        for asset in pm_assets:
            asset_id = self._asset_id(asset)
            cat = self._asset_category(asset)
            tasks = PM_TASKS_BY_CATEGORY.get(cat, PM_TASKS_BY_CATEGORY["default"])
            task_desc, cycle_days = self.rng.choice(tasks)

            # Inject overdue pattern: 15% of PMs are overdue
            is_overdue = self.rng.random() < 0.15
            last_done_days_ago = (
                self.rng.randint(cycle_days + 1, cycle_days + 45)
                if is_overdue
                else self.rng.randint(1, cycle_days - 1)
            )
            last_done_dt = now - timedelta(days=last_done_days_ago)
            next_due_dt = last_done_dt + timedelta(days=cycle_days)

            cmms_rec = self._make_pm_record(
                counter=counter,
                asset_id=asset_id,
                task_desc=task_desc,
                cycle_days=cycle_days,
                last_done_dt=last_done_dt,
                next_due_dt=next_due_dt,
            )
            self.pm_schedules.append(cmms_rec)

            pm_status = "overdue" if is_overdue else "on_track"
            wh_pm = {
                "_external_id":  self._pm_id(cmms_rec),
                "_system_type":  self.cmms_type,
                "asset_tag":     asset_id,
                "task":          task_desc,
                "interval_days": cycle_days,
                "last_done":     _date_str(last_done_dt),
                "next_due":      _date_str(next_due_dt),
                "status":        pm_status,
                "is_overdue":    is_overdue,
            }
            self.expected_pm.append(wh_pm)
            self.sync_map.append({
                "cmms_id":            self._pm_id(cmms_rec),
                "entity_type":        "pm_schedule",
                "cmms_status":        "ACTIVE",
                "expected_wh_status": pm_status,
            })
            counter += 1

    def _make_pm_record(self, counter, asset_id, task_desc, cycle_days,
                        last_done_dt, next_due_dt) -> dict:
        profile = self._profile
        plan_no = f"PM-{profile['plant_code']}-{counter:04d}"
        if self.cmms_type == "sap_pm":
            return {
                "PLAN_NO":    plan_no,
                "EQUNR":      asset_id,
                "CYCLE_DAYS": cycle_days,
                "LAST_DONE":  _date_str(last_done_dt),
                "NEXT_DUE":   _date_str(next_due_dt),
                "TASK_DESC":  task_desc,
                "TASK_LIST":  f"TL-{asset_id}",
                "IWERK":      profile["plant_code"],
                "STATUS":     "ACTIVE",
            }
        elif self.cmms_type == "maximo":
            freq_unit, freq_val = ("DAYS", cycle_days)
            if cycle_days % 365 == 0:
                freq_unit, freq_val = "YEARS", cycle_days // 365
            elif cycle_days % 30 == 0:
                freq_unit, freq_val = "MONTHS", cycle_days // 30
            elif cycle_days % 7 == 0:
                freq_unit, freq_val = "WEEKS", cycle_days // 7
            return {
                "PMNUM":        plan_no,
                "ASSETNUM":     asset_id,
                "FREQUENCY":    freq_val,
                "FREQUNIT":     freq_unit,
                "LASTCOMPDATE": _date_str(last_done_dt),
                "NEXTDUEDATE":  _date_str(next_due_dt),
                "DESCRIPTION":  task_desc,
                "SITEID":       profile["site_id"],
                "STATUS":       "ACTIVE",
            }
        else:
            return {
                "pm_id":         plan_no,
                "asset_tag":     asset_id,
                "interval_days": cycle_days,
                "last_done":     _date_str(last_done_dt),
                "next_due":      _date_str(next_due_dt),
                "task":          task_desc,
                "status":        "active",
            }

    # -----------------------------------------------------------------------
    # Status extraction helpers (system-agnostic)
    # -----------------------------------------------------------------------

    def _asset_id(self, asset: dict) -> str:
        if self.cmms_type == "sap_pm":
            return asset["EQUNR"]
        elif self.cmms_type == "maximo":
            return asset["ASSETNUM"]
        return asset["asset_tag"]

    def _asset_location(self, asset: dict) -> str:
        if self.cmms_type == "sap_pm":
            return asset.get("ILOAN", "")
        elif self.cmms_type == "maximo":
            return asset.get("LOCATION", "")
        return asset.get("location", "")

    def _asset_category(self, asset: dict) -> str:
        if self.cmms_type == "sap_pm":
            # EQKTX contains "Make Model Spec" -- not category.
            # Use EQART as proxy (first 4 chars) -- fallback to default.
            return asset.get("EQART", "default")
        elif self.cmms_type == "maximo":
            return asset.get("ASSETTYPE", "default")
        return asset.get("category", "default")

    def _wo_id(self, wo: dict) -> str:
        if self.cmms_type == "sap_pm":
            return wo["AUFNR"]
        elif self.cmms_type == "maximo":
            return wo["WONUM"]
        return wo["work_order_no"]

    def _wo_cmms_status(self, wo: dict) -> str:
        if self.cmms_type == "sap_pm":
            return wo["ISTAT"]
        elif self.cmms_type == "maximo":
            return wo["STATUS"]
        return wo["status"]

    def _cmms_status_to_wh(self, cmms_status: str) -> str:
        if self.cmms_type == "sap_pm":
            return SAP_ISTAT_TO_STATUS.get(cmms_status, "Open")
        elif self.cmms_type == "maximo":
            return MAXIMO_STATUS_TO_STATUS.get(cmms_status, "Open")
        return GENERIC_STATUS_TO_STATUS.get(cmms_status, "Open")

    def _pm_id(self, pm: dict) -> str:
        if self.cmms_type == "sap_pm":
            return pm["PLAN_NO"]
        elif self.cmms_type == "maximo":
            return pm["PMNUM"]
        return pm["pm_id"]

    # -----------------------------------------------------------------------
    # Agreement check (used by Phase 3+ tests)
    # -----------------------------------------------------------------------

    def check_agreement(self, wh_logbook_rows: list[dict]) -> dict:
        """Compare expected WorkHive logbook state against actual rows from Supabase.

        Args:
            wh_logbook_rows: Rows fetched from Supabase after sync.

        Returns:
            {matches, mismatches, missing, total_expected, details}
        """
        actual_by_ext_id = {
            r.get("external_id"): r
            for r in wh_logbook_rows
            if r.get("external_id")
        }

        matches, mismatches, missing = 0, 0, 0
        details = []

        for expected in self.expected_logbook:
            ext_id = expected["_external_id"]
            actual = actual_by_ext_id.get(ext_id)
            if actual is None:
                missing += 1
                details.append({
                    "external_id": ext_id,
                    "result": "MISSING",
                    "note": "Record not found in WorkHive after sync",
                })
                continue

            field_issues = []
            for field in ("status", "maintenance_type"):
                exp_val = expected.get(field)
                act_val = actual.get(field)
                if exp_val and act_val and exp_val != act_val:
                    field_issues.append(
                        f"{field}: expected '{exp_val}', got '{act_val}'"
                    )

            if field_issues:
                mismatches += 1
                details.append({
                    "external_id": ext_id,
                    "result": "MISMATCH",
                    "note": "; ".join(field_issues),
                })
            else:
                matches += 1

        return {
            "matches":        matches,
            "mismatches":     mismatches,
            "missing":        missing,
            "total_expected": len(self.expected_logbook),
            "details":        details,
        }


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def generate_dataset(
    industry: str = DEFAULT_INDUSTRY,
    size: str = "medium",
    cmms_type: str = "sap_pm",
    seed: Optional[int] = None,
    log=None,
) -> CMMSDataset:
    """Generate and return a ready-to-use CMMSDataset.

    Args:
        log: Optional callable(str) for streaming progress (seeder pattern).
    """
    ds = CMMSDataset(industry=industry, size=size, cmms_type=cmms_type, seed=seed)
    if log:
        log(f"Generating {size} {cmms_type} dataset for {industry} (seed={ds.seed})...")
    ds.generate()
    if log:
        s = ds.summary()
        log(f"  Generated: {s['assets']} assets, {s['work_orders']} work orders, "
            f"{s['pm_schedules']} PM schedules, {s['inventory']} parts")
        overdue = sum(1 for p in ds.expected_pm if p["is_overdue"])
        low_stock = sum(1 for i in ds.expected_inventory if i["is_low_stock"])
        log(f"  Patterns: {overdue} overdue PM schedules, {low_stock} low-stock parts")
    return ds
