"""Seed marketplace_listings — contact-only flow per current launch plan."""
import random

from data.ph_locations import CITIES
from .utils import random_timestamp_in_last_n_days, to_iso

LISTING_TEMPLATES_PARTS = [
    ("Used ABB ACS580 VFD 75kW", "Removed from working line, tested OK. Includes EMC filter.", "VFDs", "used"),
    ("Refurbished Grundfos CR 95-3 pump", "Refurb: new bearings, seal, casing wear rings replaced.", "Pumps", "refurb"),
    ("New (boxed) Bearing 6313 C3 - SKF", "Original SKF, sealed box, never used.", "Bearings", "new"),
    ("Atlas Copco GA75 - reconditioned", "5000 hrs since recon. Includes service history.", "Compressors", "refurb"),
    ("Set of Filter Cartridges (8 pcs)", "DFO 4-32 type. New, surplus from project.", "Filters", "new"),
    ("Caterpillar 3516B genset spares lot", "PSV, fuel filters, governor parts. Mixed lot.", "Generators", "used"),
    ("Honeywell Pressure Transmitter", "Range 0-10 barg, 4-20 mA, HART. Surplus.", "Instrumentation", "new"),
    ("Schneider MCCB 160A 3P", "3 pcs, sealed box.", "Switchgear", "new"),
]
LISTING_TEMPLATES_TRAINING = [
    ("ASHRAE HVAC Design Workshop", "3-day workshop, includes manual. Local Manila venue.", "HVAC"),
    ("Vibration Analysis ISO 18436 Cat I", "5-day intensive, certificate of completion.", "Reliability"),
    ("Permit-to-Work Refresher (1 day)", "On-site delivery, up to 20 attendees.", "Safety"),
    ("PLC Siemens TIA Portal Basics", "5 days, hands-on with S7-1500 trainer rigs.", "Controls"),
]
LISTING_TEMPLATES_JOBS = [
    ("Maintenance Supervisor — F&B Plant", "Cebu site. 5+ yrs FMCG experience required.", "Supervisor"),
    ("Reliability Engineer — Cement", "Davao plant, vibration analysis Cat II preferred.", "Engineer"),
    ("Electrical Tech — VFDs/MCC", "Calamba assembly, 3 yrs MV exposure ideal.", "Technician"),
    ("Mechanical Fitter — Pump Shop", "Manila, NCII certificate required.", "Technician"),
]


def seed_marketplace(client, log, ctx: dict) -> dict:
    hives = ctx["hives"]
    workers = ctx["workers"]
    workers_by_hive: dict = {}
    for w in workers:
        workers_by_hive.setdefault(w["hive_id"], []).append(w)

    log(f"Seeding marketplace listings (parts/training/jobs) across {len(hives)} hives...")

    rows = []
    for hive in hives:
        hive_workers = workers_by_hive.get(hive["id"], [])
        if not hive_workers:
            continue

        # Parts listings (3-5 per hive)
        for tpl in random.sample(LISTING_TEMPLATES_PARTS, k=min(5, len(LISTING_TEMPLATES_PARTS))):
            seller = random.choice(hive_workers)
            ts = random_timestamp_in_last_n_days(60)
            rows.append({
                "hive_id": hive["id"],
                "seller_name": seller["display_name"],
                "seller_contact": f"+639{random.randint(100000000, 999999999)}",
                "seller_verified": random.random() < 0.4,
                "completed_sales": random.randint(0, 12),
                "rating_avg": round(random.uniform(3.5, 5.0), 2),
                "section": "parts",
                "category": tpl[2],
                "title": tpl[0],
                "description": tpl[1],
                "price": round(random.uniform(2500, 250000), 2),
                "condition": tpl[3],
                "location": random.choice(CITIES),
                "status": random.choices(["published", "draft", "sold"], weights=[70, 15, 15])[0],
                "created_at": to_iso(ts),
                "updated_at": to_iso(ts),
                "view_count": random.randint(0, 200),
            })

        # Training listings (1-2 per hive)
        for tpl in random.sample(LISTING_TEMPLATES_TRAINING, k=min(2, len(LISTING_TEMPLATES_TRAINING))):
            seller = random.choice(hive_workers)
            ts = random_timestamp_in_last_n_days(60)
            rows.append({
                "hive_id": hive["id"],
                "seller_name": seller["display_name"],
                "seller_contact": f"+639{random.randint(100000000, 999999999)}",
                "seller_verified": random.random() < 0.6,
                "completed_sales": random.randint(0, 25),
                "rating_avg": round(random.uniform(4.0, 5.0), 2),
                "section": "training",
                "category": tpl[2],
                "title": tpl[0],
                "description": tpl[1],
                "price": round(random.uniform(8000, 80000), 2),
                "condition": "new",
                "location": random.choice(CITIES),
                "status": "published",
                "created_at": to_iso(ts),
                "updated_at": to_iso(ts),
                "view_count": random.randint(10, 300),
            })

        # Jobs listings (1-2 per hive)
        for tpl in random.sample(LISTING_TEMPLATES_JOBS, k=min(2, len(LISTING_TEMPLATES_JOBS))):
            seller = random.choice(hive_workers)
            ts = random_timestamp_in_last_n_days(45)
            rows.append({
                "hive_id": hive["id"],
                "seller_name": seller["display_name"],
                "seller_contact": f"hr-{random.randint(1000, 9999)}@example.ph",
                "seller_verified": True,
                "completed_sales": 0,
                "rating_avg": None,
                "section": "jobs",
                "category": tpl[2],
                "title": tpl[0],
                "description": tpl[1],
                "price": None,
                "condition": "new",
                "location": random.choice(CITIES),
                "status": "published",
                "created_at": to_iso(ts),
                "updated_at": to_iso(ts),
                "view_count": random.randint(20, 500),
            })

    client.table("marketplace_listings").insert(rows).execute()
    log(f"  inserted {len(rows)} marketplace_listings")

    return {"marketplace_listings_count": len(rows)}
