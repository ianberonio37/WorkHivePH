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


def seed_marketplace_sellers(client, log, ctx: dict) -> dict:
    """Seed marketplace_sellers profiles LINKED to community reputation.

    Runs AFTER community + achievements so a seller's community standing already
    exists. Before this, the seeder created listings with NO seller profiles, and
    the seeder never granted the `voice_of_the_hive` skill_badge either — so on a
    fresh reset the whole Community<->Marketplace bridge was dead: no seller pages,
    no tiers, and the "Community-trusted" chip (grid + detail) never lit up.

    This makes the bridge reproducible out of the box:
      1. Each hive's TOP community-XP member becomes the hive's "voice of the hive"
         (grant the skill_badge if absent) + a GOLD seller — so the Community-trusted
         chip has something real to show after every reset.
      2. Every published-listing seller + a couple more community-active workers get
         a seller profile too (tier/rating scaled by community standing).
    Idempotent: skips already-granted badges; upserts sellers on the unique worker_name.
    Uses a LOCAL RNG so it never perturbs the global deterministic seeder stream.
    """
    import random as _random
    rng = _random.Random(20260711)
    hives = ctx.get("hives", [])
    workers = ctx.get("workers", [])

    def _fetch(table, cols, **eqs):
        try:
            q = client.table(table).select(cols)
            for k, v in eqs.items():
                q = q.eq(k, v)
            return q.execute().data or []
        except Exception as e:  # best-effort: never break a reseed on a linkage miss
            log(f"  (marketplace_sellers: {table} read skipped: {e})")
            return []

    voice = {r["worker_name"] for r in _fetch("skill_badges", "worker_name", badge_key="voice_of_the_hive")}
    xp_by = {(r["hive_id"], r["worker_name"]): (r.get("xp_total") or 0)
             for r in _fetch("community_xp", "worker_name, hive_id, xp_total")}
    sellers_by_hive: dict = {}
    for r in _fetch("marketplace_listings", "hive_id, seller_name", status="published"):
        if r.get("seller_name"):
            sellers_by_hive.setdefault(r["hive_id"], set()).add(r["seller_name"])

    new_badges, seller_rows = [], []
    seen_sellers = set()          # worker_name is globally UNIQUE -> dedupe across hives
    for hive in hives:
        hid = hive["id"]
        hive_workers = [w for w in workers if w["hive_id"] == hid]
        if not hive_workers:
            continue
        # the hive's community voice = its top-XP member (with any real activity)
        top = max(hive_workers, key=lambda w: xp_by.get((hid, w["display_name"]), 0), default=None)
        top_name = top["display_name"] if top and xp_by.get((hid, top["display_name"]), 0) > 0 else None
        if top_name and top_name not in voice:
            new_badges.append({
                "worker_name": top_name, "discipline": "Community", "level": 1,
                "badge_key": "voice_of_the_hive", "exam_score": 0,
                "auth_uid": (top or {}).get("auth_uid"),
            })
            voice.add(top_name)

        # community-active workers (top 3 by XP) + everyone who already has a listing
        ranked = sorted(hive_workers, key=lambda w: xp_by.get((hid, w["display_name"]), 0), reverse=True)
        names = set(sellers_by_hive.get(hid, set())) | {w["display_name"] for w in ranked[:3]}
        by_name = {w["display_name"]: w for w in hive_workers}
        for name in sorted(names):
            if name in seen_sellers:
                continue
            seen_sellers.add(name)
            w = by_name.get(name)
            is_voice = name in voice
            xp = xp_by.get((hid, name), 0)
            tier = "gold" if is_voice else ("silver" if xp >= 25 else "bronze")
            seller_rows.append({
                "worker_name": name,
                "hive_id": hid,
                "auth_uid": (w or {}).get("auth_uid"),
                "tier": tier,
                "rating_avg": round(rng.uniform(4.4, 5.0) if is_voice else rng.uniform(3.8, 4.8), 2),
                "rating_count": rng.randint(6, 14) if is_voice else rng.randint(1, 8),
                "response_rate": round(rng.uniform(0.85, 1.0), 2),
                "response_time_h": rng.randint(1, 12),
                "total_sales": rng.randint(4, 20) if is_voice else rng.randint(0, 8),
                "kyb_verified": bool(is_voice or rng.random() < 0.4),
                "cert_verified": bool(is_voice),
            })

    if new_badges:
        try:
            client.table("skill_badges").insert(new_badges).execute()
        except Exception as e:
            log(f"  (voice-of-hive grant skipped: {e})")
    if seller_rows:
        client.table("marketplace_sellers").upsert(seller_rows, on_conflict="worker_name").execute()
    log(f"  linked {len(seller_rows)} marketplace_sellers "
        f"({sum(1 for r in seller_rows if r['tier'] == 'gold')} community-trusted / voice-of-hive; "
        f"+{len(new_badges)} voice badges granted)")
    return {"marketplace_sellers_count": len(seller_rows)}
