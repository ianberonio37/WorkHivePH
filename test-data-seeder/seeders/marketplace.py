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

# Real PH trade credentials, so a seeded "Certified" badge has something to actually show. Newline
# separated because that is the format marketplace-seller.html reads and writes ("one per line").
CERT_SAMPLES = [
    "PRC Registered Mechanical Engineer\nTESDA HVAC/R NC II",
    "PRC Registered Electrical Engineer\nDOLE Safety Officer 2",
    "TESDA Shielded Metal Arc Welding NC II\nDOLE Safety Officer 1",
    "Vibration Analysis ISO 18436-2 Category I\nTESDA Instrumentation NC III",
]

# Review copy for the seeded verified purchases. Ordinary buyer voice, not marketing.
REVIEW_COMMENTS = [
    "Item was exactly as described. Met at the plant gate, no issues.",
    "Good unit, seller let me inspect and run it before I paid.",
    "Fair price and honest about the wear. Would buy again.",
    "Packaging was fine and the part number matched what I needed.",
    "Quick to reply and flexible on the pickup time.",
    "Condition matched the photos. Straightforward transaction.",
]


def _verified_stamp(rng) -> str:
    """A verification badge needs a record of WHEN it happened, or it is an unauditable claim."""
    # rng is threaded through so this stays on the caller's LOCAL deterministic stream.
    return to_iso(random_timestamp_in_last_n_days(rng.randint(20, 180), rng=rng))


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
        for _p_idx, tpl in enumerate(random.sample(LISTING_TEMPLATES_PARTS, k=min(5, len(LISTING_TEMPLATES_PARTS)))):
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
                # Deterministic worked-state: the FIRST parts listing per hive is ALWAYS a draft so the
                # marketplace-seller "draft" state renders on EVERY reseed (was pure ~15% random -> a hive
                # could roll 0 drafts). Makes the UFAI DB-only fix (SKF 6205-2RS draft) reseed-durable. 2026-07-19.
                "status": "draft" if _p_idx == 0 else random.choices(["published", "draft", "sold"], weights=[70, 15, 15])[0],
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
         (grant the skill_badge if absent) — so the Community-trusted chip has
         something real to show after every reset.
      2. Every published-listing seller + a couple more community-active workers get
         a seller profile too.

    ★ EARNED-ONLY TRUST (2026-07-24 deepwalk). This function used to ASSIGN the trust display
    directly: a random rating with no reviews, a random sales count against an empty orders table, a
    tier from community XP that contradicted the platform's own 51/11 thresholds, and verification
    flags with no dates and, for certifications, nothing to verify. Those are states no user or admin
    action can produce, and the deepwalk found every one of them being shown to buyers as evidence.
    It now seeds the CAUSE and lets the platform's own triggers derive the display: verified reviews
    produce the rating, sold listings produce total_sales and the tier, and a verification always
    carries its date. Some sellers are deliberately left unrated, because that is a real state.
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

    # total_sales comes from listings actually marked sold, which is the only observable sale event in a
    # contact-only marketplace, and listings_by_seller gives the reviews below something real to attach
    # to. Both replace invented numbers: see the earned-only trust block further down.
    sold_by_seller: dict = {}
    listings_by_seller: dict = {}
    for r in _fetch("marketplace_listings", "id, seller_name, status"):
        nm = r.get("seller_name")
        if not nm:
            continue
        if r.get("status") == "sold":
            sold_by_seller[nm] = sold_by_seller.get(nm, 0) + 1
        if r.get("status") in ("published", "sold"):
            listings_by_seller.setdefault(nm, []).append(r["id"])

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
            # ── EARNED-ONLY TRUST STATE (marketplace deepwalk 2026-07-24) ──────────────────────────
            # This block used to fabricate every trust signal directly: a random rating_avg/rating_count
            # with no reviews behind them, a random total_sales against an empty orders table, a tier
            # derived from community XP rather than from sales (so it contradicted the platform's own
            # 51/gold, 11/silver thresholds -- gold at 16 sales, silver at 0), kyb_verified with no
            # kyb_verified_at, and cert_verified with NO certifications and no cert_verified_at. Every
            # one of those was a state no user or admin action can produce, and the deepwalk found all
            # of them displayed to buyers as evidence. Migrations 20260724000007/8/9 cleaned the data;
            # this is the source, so without it every RESET would put all of it straight back.
            #
            # The rule now: seed the CAUSE and let the platform's own triggers derive the display.
            #   rating_avg / rating_count -> omitted; produced by the verified-review trigger from the
            #                                real reviews seeded below (20260719000003).
            #   response_rate / _time_h   -> omitted; produced from real inquiries (20260724000006).
            #   total_sales / tier        -> derived from listings actually marked sold, with the
            #                                documented thresholds (20260724000008).
            #   kyb / cert verification   -> stamped with a date, and cert only when there are
            #                                certifications for it to cover (20260724000009).
            sold_count = sold_by_seller.get(name, 0)
            certs = CERT_SAMPLES[rng.randrange(len(CERT_SAMPLES))] if is_voice else None
            row = {
                "worker_name": name,
                "hive_id": hid,
                "auth_uid": (w or {}).get("auth_uid"),
                "total_sales": sold_count,
                "tier": "gold" if sold_count >= 51 else ("silver" if sold_count >= 11 else "bronze"),
                "kyb_verified": bool(is_voice or rng.random() < 0.4),
            }
            # A verification is only real if there is a record of it happening.
            row["kyb_verified_at"] = _verified_stamp(rng) if row["kyb_verified"] else None
            if certs:
                row["certifications"]    = certs
                row["cert_verified"]     = True
                row["cert_verified_at"]  = _verified_stamp(rng)
            else:
                row["certifications"]    = None
                row["cert_verified"]     = False
                row["cert_verified_at"]  = None
            seller_rows.append(row)

    if new_badges:
        try:
            client.table("skill_badges").insert(new_badges).execute()
        except Exception as e:
            log(f"  (voice-of-hive grant skipped: {e})")
    if seller_rows:
        client.table("marketplace_sellers").upsert(seller_rows, on_conflict="worker_name").execute()

    # Seed the CAUSE of a rating, not the rating. update_seller_rating (20260719000003) recomputes
    # rating_avg/rating_count over VERIFIED purchases only, so inserting real verified reviews here is
    # what makes a displayed star rating true. Deliberately leaves some sellers with no reviews at all:
    # "Not rated" is a real state a marketplace must show honestly, and it is the state the UI empty
    # path is built for. Runs after the seller upsert so the trigger has a row to update.
    review_rows = []
    reviewer_pool = [w["display_name"] for w in workers if w.get("display_name")]
    for name in sorted(seen_sellers):
        ids = listings_by_seller.get(name) or []
        if not ids or not reviewer_pool or rng.random() < 0.35:
            continue
        for _ in range(rng.randint(1, 4)):
            reviewer = reviewer_pool[rng.randrange(len(reviewer_pool))]
            if reviewer == name:      # never let a seller review their own listing
                continue
            review_rows.append({
                "listing_id": ids[rng.randrange(len(ids))],
                "reviewer_name": reviewer,
                "rating": rng.choice([3, 4, 4, 5, 5, 5]),
                "comment": REVIEW_COMMENTS[rng.randrange(len(REVIEW_COMMENTS))],
                "verified_purchase": True,
                "created_at": to_iso(random_timestamp_in_last_n_days(rng.randint(1, 120), rng=rng)),
            })
    if review_rows:
        try:
            client.table("marketplace_reviews").insert(review_rows).execute()
        except Exception as e:
            log(f"  (verified reviews skipped: {e})")

    rated = len({r["listing_id"] for r in review_rows})
    log(f"  linked {len(seller_rows)} marketplace_sellers "
        f"(tier + total_sales derived from sold listings; "
        f"{sum(1 for r in seller_rows if r['cert_verified'])} with verified certifications; "
        f"+{len(new_badges)} voice badges granted)")
    log(f"  seeded {len(review_rows)} VERIFIED reviews across {rated} listings "
        f"-> ratings are trigger-computed, never invented (sellers without reviews stay unrated)")
    return {"marketplace_sellers_count": len(seller_rows)}


def seed_marketplace_orders(client, log, ctx: dict) -> dict:
    """Seed marketplace_orders — ONE order per lifecycle state (T96).

    Why this exists: marketplace_orders carries a CHECK constraint enumerating a real escrow
    flow — pending_payment -> escrow_hold -> buyer_confirmed -> released, with refunded and
    disputed as its two exits — and the table has never held a single row. reset.py knew how to
    TRUNCATE orders; nothing knew how to make one. So the goods lifecycle was defined and
    unwalkable: no state transition on this table had ever been exercised, and "the constraint
    allows it" is not "the product does it".

    One row per state rather than a random spread, because the point is COVERAGE — a two-sided
    walk needs to find a buyer_confirmed order to look at, not hope one was rolled. Timestamps
    are set to match each state so a row is internally consistent (a released order has a
    released_at; a pending one does not), since a fixture that contradicts itself teaches a
    walker the wrong thing about the schema.
    """
    listings = (client.table("marketplace_listings")
                .select("id, hive_id, title, price, seller_name")
                .limit(6).execute().data) or []
    if not listings:
        log("  marketplace_orders: no listings to reference — run seed_marketplace first")
        return {"marketplace_orders_count": 0}

    buyers = ["Christine Dizon", "Pablo Aguilar", "Hector Salvador", "Romeo Beltran"]
    states = [
        ("pending_payment", {}),
        ("escrow_hold", {"escrow_release_at": 3}),
        ("buyer_confirmed", {"escrow_release_at": 1, "buyer_confirmed_at": -1}),
        ("released", {"buyer_confirmed_at": -3, "released_at": -2}),
        ("refunded", {"buyer_confirmed_at": -5}),
        ("disputed", {"escrow_release_at": 2}),
    ]
    rows = []
    for i, (status, stamps) in enumerate(states):
        lst = listings[i % len(listings)]
        ts = random_timestamp_in_last_n_days(14)
        row = {
            "listing_id": lst.get("id"),
            "hive_id": lst.get("hive_id"),
            "buyer_name": buyers[i % len(buyers)],
            "seller_name": lst.get("seller_name") or "Bryan Garcia",
            "price": lst.get("price") or 1500,
            "currency": "PHP",
            "status": status,
            "created_at": to_iso(ts),
            "updated_at": to_iso(ts),
        }
        for col, day_offset in stamps.items():
            row[col] = to_iso(random_timestamp_in_last_n_days(abs(day_offset) or 1))
        rows.append(row)

    client.table("marketplace_orders").insert(rows).execute()
    log(f"  inserted {len(rows)} marketplace_orders (one per lifecycle state)")
    return {"marketplace_orders_count": len(rows)}


def seed_marketplace_inquiries(client, log, ctx: dict) -> dict:
    """Seed marketplace_inquiries — the LIVE goods path (T96).

    ★THIS IS THE TABLE THE PRODUCT ACTUALLY USES, and it matters which one gets seeded.
    marketplace_orders describes a full escrow flow (pending_payment -> escrow_hold ->
    buyer_confirmed -> released) and is read by exactly one page, marketplace-admin, which is
    RETIRED behind an overlay. The live goods flow is contact-only, exactly as this module's
    own docstring says: a buyer sends an INQUIRY against a listing, the seller replies, contact
    details are exchanged, and the transaction completes off-platform. marketplace-seller's
    Inquiries tab reads v_marketplace_inquiries_truth in six places; it never reads orders.

    So this is the fixture that makes the two-sided goods walk possible: pending gives the
    seller something waiting for a reply, replied gives both parties a thread to compare, and
    closed gives the walk an end state. A replied row carries BOTH reply_text and replied_at,
    because a reply with no timestamp is a state the UI cannot render honestly.
    """
    listings = (client.table("marketplace_listings")
                .select("id, hive_id, title, seller_name")
                .limit(8).execute().data) or []
    if not listings:
        log("  marketplace_inquiries: no listings to reference — run seed_marketplace first")
        return {"marketplace_inquiries_count": 0}

    asks = [
        ("Christine Dizon", "0917 555 0142", "Is this still available? Can you hold it until Friday?"),
        ("Pablo Aguilar", "0918 555 0233", "What's the hour meter reading, and do you have the service history?"),
        ("Hector Salvador", "0920 555 0311", "Can you deliver to Laguna? What would freight cost?"),
        ("Romeo Beltran", "0921 555 0498", "Is the price negotiable for two units?"),
        ("Leonardo Romero", "0927 555 0570", "Do you have the calibration certificate for this?"),
        ("Isidro Suarez", "0939 555 0655", "Any warranty on the refurb work?"),
    ]
    replies = [
        "Yes, still available. I can hold it until Friday noon.",
        "5,000 hours. Service records are with the unit — I can send photos.",
        "Delivery to Laguna is fine, freight is around PHP 2,500.",
    ]
    rows = []
    for i, (buyer, contact, msg) in enumerate(asks):
        lst = listings[i % len(listings)]
        ts = random_timestamp_in_last_n_days(21)
        status = "pending" if i < 2 else ("replied" if i < 5 else "closed")
        row = {
            "listing_id": lst.get("id"),
            "hive_id": lst.get("hive_id"),
            "buyer_name": buyer,
            "buyer_contact": contact,
            "seller_name": lst.get("seller_name"),
            "message": msg,
            "status": status,
            "created_at": to_iso(ts),
        }
        if status in ("replied", "closed"):
            row["reply_text"] = replies[i % len(replies)]
            row["replied_at"] = to_iso(random_timestamp_in_last_n_days(7))
        rows.append(row)

    client.table("marketplace_inquiries").insert(rows).execute()
    log(f"  inserted {len(rows)} marketplace_inquiries (pending / replied / closed)")
    return {"marketplace_inquiries_count": len(rows)}
