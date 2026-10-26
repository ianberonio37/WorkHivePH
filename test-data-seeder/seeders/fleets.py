"""The three fleet hives - a vehicle vertical the seed now makes instead of inheriting it from walks (2026-10-27).

WHY: Dela Cruz Delivery Fleet, Ramos Jeepney Line and Tan Delivery Vans are a third of the platform's verticals: the
trajectory registry casts journeys in them and tools/validate_fixture_depth.py measures their history. They were born
from the vehicle arc's walks (an owner signing up and adding vans through the UI), so no seeder knew them; the
2026-10-26 reset deleted them and nothing could bring them back. This creates the hives, their people (the accounts the
walk tooling names: tools/record_mcp_walk.py) and their vehicles; tools/seed_fleet_history.py,
tools/backfill_fleet_seed_gaps.py and tools/seed_multi_hive_worker.py then give them an operating history, exactly as
they did for the walked fleets.
"""
from .hives_workers import TEST_PASSWORD, _synthetic_email
from .utils import random_invite_code

FLEETS = {
    "Dela Cruz Delivery Fleet": {
        "people": [("Rosa dela Cruz", "delacruzfleet", "supervisor"), ("Ben Ocampo", "driverben", "worker")],
        "vehicles": [("Isuzu N-Series Truck", "DCF-TRK-01", "NAB 4512", "Isuzu", "NLR 77", 2019, 142300),
                     ("Toyota Hiace Van", "DCF-VAN-02", "NBC 7781", "Toyota", "Hiace Commuter", 2021, 88400),
                     ("Mitsubishi L300", "DCF-VAN-03", "NCD 2209", "Mitsubishi", "L300 FB", 2018, 163900)],
    },
    "Ramos Jeepney Line": {
        "people": [("Oscar Ramos", "jeepneyoscarph", "supervisor")],
        "vehicles": [("Jeepney Unit 1", "RJL-JP-01", "PUJ 1123", "Sarao", "Jeepney (Isuzu 4BC2)", 2012, 412500),
                     ("Jeepney Unit 2", "RJL-JP-02", "PUJ 1187", "Francisco", "Jeepney (Isuzu 4JA1)", 2015, 298700)],
    },
    "Tan Delivery Vans": {
        "people": [("Gloria Tan", "vanfleetgloriaph", "supervisor")],
        "vehicles": [("Toyota Hiace Van", "TDV-VAN-01", "NFE 5530", "Toyota", "Hiace GL Grandia", 2020, 104200),
                     ("Nissan Urvan", "TDV-VAN-02", "NGH 6618", "Nissan", "NV350 Urvan", 2017, 187600)],
    },
}


# a fleet driver's OWN vehicle, outside any hive (the solo lane): tools/prove_logbook_asset_picker_identity.mjs proves
# the logbook picker finds it by ACCOUNT, so it must exist (a walk created it; the 2026-10-26 reset took it)
PERSONAL = [("driverben", "Ben Ocampo", "Honda TMX 155", "BEN 4477", "Honda", "TMX 155", 2020, 38400)]


def _account(client, email: str, log):
    """The account for this email: created with the local test password, or the one a previous run left."""
    try:
        return client.auth.admin.create_user({"email": email, "password": TEST_PASSWORD, "email_confirm": True}).user.id
    except Exception as e:
        if not any(w in str(e).lower() for w in ("already", "exists", "registered")):
            raise
        try:
            for u in client.auth.admin.list_users():
                if getattr(u, "email", None) == email:
                    return u.id
        except Exception:
            pass
        log(f"  WARN: {email} exists and could not be read back")
        return None


def seed_fleets(client, log) -> dict:
    log("Seeding the three fleet hives (people + vehicles; history comes from the fleet tools)...")
    out = {"hives": 0, "people": 0, "vehicles": 0}
    for hive_name, spec in FLEETS.items():
        if client.table("hives").select("id").eq("name", hive_name).limit(1).execute().data:
            log(f"  {hive_name}: already present - left as it is")
            continue
        people = []
        for full, username, role in spec["people"]:
            email = _synthetic_email(username)
            uid = _account(client, email, log)
            if uid:
                # a profile username is [a-z0-9_]{3,30} (worker_profiles_username_check); the front door signs in by it
                client.table("worker_profiles").upsert({"auth_uid": uid, "username": username.replace(".", "_"),
                                                        "display_name": full, "email": email},
                                                       on_conflict="auth_uid").execute()
            people.append((full, uid, role))
        hive = client.table("hives").insert({"name": hive_name, "invite_code": random_invite_code(),
                                             "created_by": people[0][0]}).execute().data[0]
        client.table("hive_members").insert([{"hive_id": hive["id"], "worker_name": full, "auth_uid": uid, "role": role,
                                              "status": "active"} for full, uid, role in people]).execute()
        owner_name, owner_uid, _ = people[0]
        client.table("asset_nodes").insert([{
            "hive_id": hive["id"], "name": name, "tag": tag, "level": "equipment", "status": "approved",
            "criticality": "high", "auth_uid": owner_uid, "worker_name": owner_name, "lifecycle": "active",
            "vehicle_meta": {"plate": plate, "make": make, "model": model, "year": year,
                             "odometer_km": km, "odometer_baseline_km": km},
        } for name, tag, plate, make, model, year, km in spec["vehicles"]]).execute()
        out["hives"] += 1
        out["people"] += len(people)
        out["vehicles"] += len(spec["vehicles"])
        log(f"  {hive_name}: {len(people)} people, {len(spec['vehicles'])} vehicles")
    for username, full, name, plate, make, model, year, km in PERSONAL:
        prof = client.table("worker_profiles").select("auth_uid").eq("username", username).limit(1).execute().data
        if not prof or client.table("asset_nodes").select("id").eq("tag", plate).is_("hive_id", "null").limit(1).execute().data:
            continue
        client.table("asset_nodes").insert({
            "hive_id": None, "name": name, "tag": plate, "level": "equipment", "status": "approved",
            "criticality": "medium", "auth_uid": prof[0]["auth_uid"], "worker_name": full, "lifecycle": "active",
            "vehicle_meta": {"plate": plate, "make": make, "model": model, "year": year,
                             "odometer_km": km, "odometer_baseline_km": km},
        }).execute()
        out["vehicles"] += 1
        log(f"  {full}: a personal {name} ({plate}), no hive")
    return out
