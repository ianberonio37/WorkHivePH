"""Seed the service-hailing substrate (SERVICE_HAILING_ROADMAP.md P1) — catalog,
providers, requests across the WHOLE state machine, offers, credits, vouchers.

Design notes (why, not just what):
- BOTH segments seeded from day one (industrial + consumer common services) so every
  schema/matching decision is proven against both — consumer rows sit behind the
  `segment` flag until P8 opens the consumer door.
- Requests are seeded across the full lifecycle (broadcasting, quote-pending, accepted,
  in_progress, completed, settled, cancelled, expired) so every page/rubric measurement
  grades the WORKED state, never an empty shell.
- The verified top-up is seeded through the REAL path (insert pending -> UPDATE to
  verified) so the trigger mints the ledger row exactly as the founder's verification
  will in production — the trust signal has a living producer, not a painted number.
- The seeder runs service-role (auth.uid() IS NULL) so the state-machine guards allow
  direct status seeding; provider availability is set explicitly for in-flight jobs
  because the availability-sync trigger fires on UPDATE, not on seeded INSERTs.
"""

# PH city coordinates (lng/lat for PostGIS POINT WKT — note the order: POINT(lng lat)).
CITY_COORDS = {
    "Manila":    (120.9842, 14.5995),
    "Cebu":      (123.8854, 10.3157),
    "Davao":     (125.4553, 7.1907),
    "Baguio":    (120.5960, 16.4023),
    "Batangas":  (121.0583, 13.7565),
    "Calamba":   (121.1653, 14.2117),
    "Angeles":   (120.5887, 15.1450),
    "Iloilo":    (122.5621, 10.7202),
}

CATALOG_INDUSTRIAL = [
    ("Electrical",   "Motor & MCC Troubleshooting Visit", "Diagnose and repair LV motor / MCC faults on site.", "per_visit", 3500),
    ("Electrical",   "VFD Commissioning & Parameter Tune", "Drive setup, motor ID run, parameter sheet handover.", "per_visit", 4500),
    ("HVAC",         "Industrial AHU/Chiller PM Visit", "Coil cleaning, refrigerant check, controls verification.", "per_visit", 5000),
    ("Mechanical",   "Pump Overhaul (site)", "Bearing/seal replacement, alignment, test run.", "per_visit", 6000),
    ("Mechanical",   "Laser Shaft Alignment", "Pump/motor sets, report with before/after readings.", "per_visit", 4000),
    ("Calibration",  "Pressure/Temp Instrument Calibration", "Per-loop calibration with certificates.", "per_hour", 800),
    ("Generator",    "Genset PM Service (A-check)", "Filters, fluids, load test, report.", "per_visit", 5500),
    ("Welding",      "Certified Welding (SMAW) Call-out", "NC II welder with WPS adherence.", "per_hour", 650),
]
CATALOG_CONSUMER = [
    ("Aircon",     "Split-type Aircon Cleaning", "Full clean: coils, blower, drain flush.", "per_visit", 800),
    ("Aircon",     "Aircon Repair / No-Cool Diagnosis", "Leak test, charging, parts quote if needed.", "per_visit", 1200),
    ("Plumbing",   "Leak Repair / Faucet Replacement", "Common household plumbing fixes.", "per_visit", 900),
    ("Electrical", "House Wiring Repair / Outlet Addition", "Licensed electrician, materials quoted separately.", "per_visit", 1000),
    ("Appliance",  "Washing Machine / Ref Repair", "Diagnosis + repair, parts quoted.", "per_visit", 1100),
    ("Handyman",   "General Handyman (2-hr block)", "Mounting, assembly, small fixes.", "per_hour", 400),
]


def _pt(city: str) -> str:
    lng, lat = CITY_COORDS[city]
    return f"POINT({lng} {lat})"


def _now() -> str:
    # PostgREST takes timestamp LITERALS, not SQL expressions — _now() would 22007.
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def seed_services(client, log, ctx: dict) -> dict:
    hives = ctx["hives"]
    workers = [w for w in ctx["workers"] if w.get("auth_uid")]
    if not workers or not hives:
        log("services: no seeded workers/hives in ctx — skipping")
        return {"catalog": 0, "providers": 0, "requests": 0}

    # self-cleaning (child -> parent) so a reseed never duplicates
    for t in ("service_voucher_redemptions", "service_vouchers", "service_offers",
              "service_job_events", "service_requests", "service_credit_topups",
              "service_credit_ledger", "service_providers", "service_catalog"):
        try:
            client.table(t).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        except Exception:
            client.table(t).delete().gte("id", 0).execute()  # bigint-id tables

    # ---- 1. Catalog (both segments; consumer behind the flag until P8) ----
    catalog_rows = [
        {"segment": "industrial", "category": c, "name": n, "description": d, "unit": u, "base_rate": r, "active": True}
        for (c, n, d, u, r) in CATALOG_INDUSTRIAL
    ] + [
        {"segment": "consumer", "category": c, "name": n, "description": d, "unit": u, "base_rate": r, "active": True}
        for (c, n, d, u, r) in CATALOG_CONSUMER
    ]
    cat = client.table("service_catalog").insert(catalog_rows).execute().data
    cat_by_name = {row["name"]: row for row in cat}
    log(f"services: catalog {len(cat)} rows (industrial {len(CATALOG_INDUSTRIAL)} + consumer {len(CATALOG_CONSUMER)})")

    # ---- 2. Providers: freelancers (from real seeded workers) + hive companies ----
    freelancer_specs = [
        # (worker index, display suffix, categories, city, availability, verified)
        (0, "Electrical Services", ["Electrical", "Generator"], "Baguio",  "online",  True),
        (1, "HVAC & Refrigeration", ["HVAC", "Aircon"],        "Manila",  "online",  True),
        (2, "Mechanical Works",     ["Mechanical", "Welding"],  "Cebu",    "online",  False),
        (3, "Calibration Services", ["Calibration"],            "Calamba", "offline", True),
        # CONSUMER-side supply (added 2026-07-29 after the D-G deepwalk): the catalog seeded FIVE
        # consumer categories but providers covered only Aircon + Electrical, so a consumer hailing
        # Plumbing / Appliance / Handyman could never be served and that half of the segment axis
        # was unwalkable. A rate card with no supply behind it is a shop window with an empty shop.
        (4, "Home Services",        ["Plumbing", "Handyman"],   "Manila",  "online",  True),
        (5, "Appliance Repair",     ["Appliance", "Aircon"],    "Manila",  "online",  False),
    ]
    provider_rows = []
    for idx, suffix, cats, city, avail, verified in freelancer_specs:
        w = workers[idx % len(workers)]
        provider_rows.append({
            "provider_type": "freelancer",
            "auth_uid": w["auth_uid"],
            "worker_name": w["worker_name"],
            "display_name": f"{w['worker_name']} {suffix}",
            "contact": f"09{17_0000000 + idx * 111111}",
            "categories": cats,
            "service_areas": [city],
            "base_location": _pt(city),
            "availability": avail,
            "verified": verified,
        })
    for i, (hive, city) in enumerate(zip(hives[:2], ["Batangas", "Angeles"])):
        provider_rows.append({
            "provider_type": "hive",
            "hive_id": hive["id"],
            "display_name": f"{hive.get('name', 'Hive')} Field Services",
            "contact": f"09{18_0000000 + i * 222222}",
            "categories": ["Electrical", "Mechanical", "HVAC"],
            "service_areas": [city, "Manila"],
            "base_location": _pt(city),
            "availability": "online",
            "verified": True,
        })
    providers = client.table("service_providers").insert(provider_rows).execute().data
    log(f"services: providers {len(providers)} (4 freelancers + {len(providers) - 4} hive companies)")
    p_elec, p_hvac, p_mech, p_cal = providers[0], providers[1], providers[2], providers[3]
    p_hive1 = providers[4] if len(providers) > 4 else providers[0]

    # ---- 3. Requests across the WHOLE state machine (the worked states) ----
    client_hive = hives[0]
    client_workers = [w for w in workers if w.get("hive_id") == client_hive["id"]] or workers
    cw = client_workers[0]

    def req(mode, cat_name, scope, city, status, provider=None, segment="industrial", **extra):
        # batch insert = union-of-keys: a key missing on ONE row is sent as explicit
        # null for that row (defaults do NOT apply) — so every NOT NULL default gets
        # a value here, and timestamps are literals via _now().
        row = {
            "client_auth_uid": cw["auth_uid"],
            "client_worker_name": cw["worker_name"],
            "hive_id": client_hive["id"] if segment == "industrial" else None,
            "segment": segment,
            "mode": mode,
            "catalog_item_id": cat_by_name[cat_name]["id"] if cat_name else None,
            "custom_scope": scope,
            "address": f"{city} industrial area" if segment == "industrial" else f"{city} residential",
            "location": _pt(city),
            "status": status,
            "urgency": "normal",
            "matched_provider_id": provider["id"] if provider else None,
        }
        row.update(extra)
        return row

    # fixture broadcasts get a FAR-FUTURE TTL so the per-minute sweep_service_broadcasts()
    # cron (mig 20260728000042) doesn't widen/expire the WORKED states the rubric measures
    from datetime import datetime, timedelta, timezone
    fixture_ttl = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    request_rows = [
        # live broadcast, awaiting accepts (instant)
        req("instant", "Motor & MCC Troubleshooting Visit", None, "Baguio", "broadcasting",
            urgency="high", offer_ttl_expires_at=fixture_ttl),
        # quote-mode, quotes pending client choice
        req("quote", None, "Rewind or replace 75kW induction motor, bearing noise + insulation test needed.",
            "Manila", "broadcasting", urgency="normal", budget=25000, offer_ttl_expires_at=fixture_ttl),
        # accepted, provider en-route soon
        req("instant", "Genset PM Service (A-check)", None, "Baguio", "accepted", provider=p_elec,
            urgency="normal", accepted_at=_now()),
        # mid-job
        req("instant", "Industrial AHU/Chiller PM Visit", None, "Manila", "in_progress", provider=p_hvac,
            urgency="normal", accepted_at=_now(), en_route_at=_now(), on_site_at=_now(), in_progress_at=_now()),
        # done, awaiting settlement
        req("instant", "Pump Overhaul (site)", None, "Cebu", "completed", provider=p_mech,
            urgency="high", accepted_at=_now(), en_route_at=_now(), on_site_at=_now(),
            in_progress_at=_now(), completed_at=_now()),
        # fully settled (feeds trust + commission)
        req("instant", "Laser Shaft Alignment", None, "Cebu", "settled", provider=p_mech,
            urgency="normal", accepted_at=_now(), en_route_at=_now(), on_site_at=_now(),
            in_progress_at=_now(), completed_at=_now(), settled_at=_now()),
        # branches
        req("instant", "VFD Commissioning & Parameter Tune", None, "Calamba", "cancelled_by_client",
            cancelled_at=_now()),
        req("instant", "Certified Welding (SMAW) Call-out", None, "Davao", "expired"),
        # consumer segment worked state (hive-less client), behind the P8 door but schema-proven NOW
        req("instant", "Split-type Aircon Cleaning", None, "Manila", "settled", provider=p_hvac,
            segment="consumer", accepted_at=_now(), en_route_at=_now(), on_site_at=_now(),
            in_progress_at=_now(), completed_at=_now(), settled_at=_now()),
    ]
    requests = client.table("service_requests").insert(request_rows).execute().data
    log(f"services: requests {len(requests)} across the state machine (incl. 1 consumer settled)")
    r_broadcast, r_quote, r_accepted, r_inprog, r_completed, r_settled = requests[0], requests[1], requests[2], requests[3], requests[4], requests[5]
    r_consumer = requests[8]

    # availability-sync fires on UPDATE, not seeded INSERT — set in-flight providers explicitly
    client.table("service_providers").update({"availability": "on_job"}).eq("id", p_hvac["id"]).execute()

    # ---- 4. Offers ----
    offer_rows = [
        # two quotes pending on the quote-mode request
        {"request_id": r_quote["id"], "provider_id": p_mech["id"], "kind": "quote",
         "price": 22000, "eta_minutes": 2880, "message": "Includes pickup, rewind shop partner, 2-day turnaround.", "status": "pending"},
        {"request_id": r_quote["id"], "provider_id": p_hive1["id"], "kind": "quote",
         "price": 26500, "eta_minutes": 1440, "message": "On-site megger + replacement unit option, next-day.", "status": "pending"},
        # the accepted/in-flight/settled requests carry their winning accept
        {"request_id": r_accepted["id"], "provider_id": p_elec["id"], "kind": "accept", "status": "selected", "eta_minutes": 45},
        {"request_id": r_inprog["id"], "provider_id": p_hvac["id"], "kind": "accept", "status": "selected", "eta_minutes": 30},
        {"request_id": r_completed["id"], "provider_id": p_mech["id"], "kind": "accept", "status": "selected", "eta_minutes": 60},
        {"request_id": r_settled["id"], "provider_id": p_mech["id"], "kind": "accept", "status": "selected", "eta_minutes": 40},
        {"request_id": r_consumer["id"], "provider_id": p_hvac["id"], "kind": "accept", "status": "selected", "eta_minutes": 90},
    ]
    offers = client.table("service_offers").insert(offer_rows).execute().data
    log(f"services: offers {len(offers)} (2 pending quotes + 5 accepts)")

    # ---- 5. Credits: top-ups through the REAL verification path + commission entries ----
    topup_specs = [
        (p_elec, 1000, "1001234567890", True),
        (p_hvac, 500,  "1009876543210", True),
        (p_mech, 300,  "1005556667770", False),  # stays pending -> founder verification queue has a live row
    ]
    verified_count = 0
    for prov, amount, ref, verify in topup_specs:
        payer = prov.get("auth_uid") or cw["auth_uid"]
        row = client.table("service_credit_topups").insert({
            "account_type": "provider", "account_id": prov["id"],
            "payer_auth_uid": payer, "amount": amount, "gcash_ref": ref,
        }).execute().data[0]
        if verify:
            # UPDATE pending->verified exercises the REAL trigger path: it mints the ledger row
            client.table("service_credit_topups").update({"status": "verified"}).eq("id", row["id"]).execute()
            verified_count += 1
    # commission on the settled jobs (what complete_job()/settlement will mint in P2 — 5% industrial)
    client.table("service_credit_ledger").insert([
        {"account_type": "provider", "account_id": p_mech["id"], "entry_type": "commission",
         "amount": -200, "ref_kind": "request", "ref_id": r_settled["id"], "note": "5% commission — Laser Shaft Alignment ₱4,000"},
        {"account_type": "provider", "account_id": p_hvac["id"], "entry_type": "commission",
         "amount": -80, "ref_kind": "request", "ref_id": r_consumer["id"], "note": "10% commission — Aircon Cleaning ₱800"},
    ]).execute()
    log(f"services: topups 3 ({verified_count} verified via real trigger path -> ledger minted) + 2 commissions")

    # ---- 6. Vouchers ----
    client.table("service_vouchers").insert([
        {"code": "WELCOME100", "kind": "fixed", "value": 100, "segment": "consumer",
         "max_uses": 500, "per_user_limit": 1, "active": True},
        {"code": "HAIL10", "kind": "percent", "value": 10, "segment": None,
         "max_uses": 200, "per_user_limit": 2, "active": True},
    ]).execute()
    log("services: vouchers 2 (WELCOME100 fixed / HAIL10 percent)")

    ledger_rows = client.table("service_credit_ledger").select("id", count="exact").execute().count or 0
    return {
        "service_catalog": len(cat),
        "service_providers": len(providers),
        "service_requests": len(requests),
        "service_offers": len(offers),
        "service_credit_ledger": ledger_rows,
    }
