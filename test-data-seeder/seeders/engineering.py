"""Seed engineering_calcs (calc history + BOM/SOW examples).

The engineering page persists every Calculate run as an engineering_calcs row.
Pre-seeding 2 rows per worker with realistic bom_data and sow_text gives the
History tab and downstream BOM/SOW renderers something to show even when the
live AI generation is offline.
"""
import random

from .utils import random_timestamp_in_last_n_days, to_iso, batch_insert


SAMPLE_BOM = [
    {"item": "Centrifugal pump (KSB Etabloc 80-200)", "qty": 1,    "unit": "set", "remarks": "with mech seal"},
    {"item": "Suction strainer DN80",                  "qty": 1,    "unit": "pcs", "remarks": "Y-type"},
    {"item": "Discharge check valve DN80",             "qty": 1,    "unit": "pcs", "remarks": "swing type"},
    {"item": "Isolation gate valve DN80",              "qty": 2,    "unit": "pcs", "remarks": "rising stem"},
    {"item": "Pressure gauge 0-10 bar",                "qty": 2,    "unit": "pcs", "remarks": "with isolation cock"},
    {"item": "Stainless flexible coupling",            "qty": 1,    "unit": "set", "remarks": "DN80"},
    {"item": "ABB ACS580 VFD 11 kW",                   "qty": 1,    "unit": "pcs", "remarks": "IP55, EMC filter"},
    {"item": "PVC suction line",                       "qty": 12,   "unit": "m",   "remarks": "DN80"},
    {"item": "Galvanised discharge pipe",              "qty": 30,   "unit": "m",   "remarks": "DN80"},
    {"item": "Anti-vibration mounts",                  "qty": 4,    "unit": "set", "remarks": "rubber bonded"},
    {"item": "Anchor bolts M16",                       "qty": 8,    "unit": "pcs", "remarks": "stainless"},
    {"item": "Skid base plate (steel)",                "qty": 1,    "unit": "lot", "remarks": "1.2 x 0.6 m"},
]

SAMPLE_SOW = (
    "1. SCOPE OF WORK\n"
    "The Contractor shall supply, deliver, install, test and commission a complete "
    "centrifugal pump set sized in accordance with the attached calculation report.\n\n"
    "2. EQUIPMENT SUPPLY\n"
    "The Contractor shall furnish all materials and equipment listed in the Bill of "
    "Quantities, including pump, motor, baseplate, coupling, and all associated "
    "instrumentation, in accordance with the project specification.\n\n"
    "3. INSTALLATION\n"
    "The Contractor shall mount the pump set on the prepared concrete plinth, align "
    "the coupling within 0.05 mm runout, and grout the baseplate using non-shrink "
    "epoxy grout.\n\n"
    "4. TESTING & COMMISSIONING\n"
    "The Contractor shall perform a no-load run for 30 minutes, followed by a full "
    "load test against the calculated TDH. The Contractor shall record vibration "
    "readings at DE/NDE bearings and submit a commissioning report.\n\n"
    "5. WARRANTIES\n"
    "The Contractor shall provide a 12-month warranty on all supplied equipment "
    "from date of acceptance, covering parts and labour."
)


def seed_engineering(client, log, ctx: dict) -> dict:
    workers = ctx["workers"]
    log(f"Seeding engineering_calcs (history + BOM/SOW) for {len(workers)} workers...")

    rows = []
    for w in workers:
        # Two rows per worker: one Mechanical TDH, one Electrical (mix of disciplines)
        for disc, calc_type, project in [
            ("Mechanical", "Pump Sizing (TDH)",       "Cooling water booster pump"),
            ("Electrical", "Cable Sizing (Voltage Drop)", "MCC feeder for compressor"),
        ]:
            ts = random_timestamp_in_last_n_days(45)
            rows.append({
                "hive_id":      w["hive_id"],
                "worker_name":  w["worker_name"],
                "discipline":   disc,
                "calc_type":    calc_type,
                "project_name": project,
                "inputs":       {"sample": True, "flow_lps": 12, "tdh_m": 35},
                "results":      {"power_kw": round(random.uniform(7, 22), 1), "efficiency": 0.78},
                "narrative":    {"objective": f"{calc_type} for {project}",
                                 "assumptions": "Standard ambient, single duty",
                                 "recommendations": "Refer to BOM and SOW attached."},
                "bom_data":     SAMPLE_BOM,
                "sow_text":     SAMPLE_SOW,
                "created_at":   to_iso(ts),
                "auth_uid":     w.get("auth_uid"),
            })

    inserted = batch_insert(client, "engineering_calcs", rows, chunk=200)
    log(f"  inserted {inserted} engineering_calcs (history + BOM/SOW)")
    return {"engineering_calcs_count": inserted}
