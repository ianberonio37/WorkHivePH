"""Client Hive Seeder -- Phase 7 extension.

Creates a complete "client hive" from a CMMS dataset in one shot:
  1. Creates a hive with the industry's real company name
  2. Creates 1 supervisor + 4 workers (Supabase Auth + worker_profiles + hive_members)
  3. Generates a CMMSDataset for the chosen industry
  4. Bridges the dataset into WorkHive's native tables via cmms_bridge
  5. Returns test login credentials

After this runs, the hive is fully live in the WorkHive Tester proxy.
Log in at http://127.0.0.1:5000/workhive/ and the platform shows the
client's CMMS data in production format.
"""

import random

from data.filipino_names import random_full_name
from data.cmms_templates import INDUSTRY_PROFILES
from seeders.cmms import generate_dataset
from seeders.cmms_bridge import bridge_to_workhive
from seeders.utils import random_invite_code

TEST_PASSWORD = "test1234"
AUTH_DOMAIN   = "@auth.workhiveph.com"
N_WORKERS     = 4  # + 1 supervisor = 5 total


def _sanitize_username(name: str) -> str:
    out = []
    for ch in name.lower().replace("ñ", "n"):
        if ch.isalnum() or ch == "_":
            out.append(ch)
    s = "".join(out)[:28]
    return s if len(s) >= 3 else (s + "usr")[:28]


def seed_client_hive(
    client,
    log,
    industry:  str = "food_processing",
    size:      str = "medium",
    cmms_type: str = "sap_pm",
    seed:      int | None = None,
) -> dict:
    """Full end-to-end: create hive → create workers → generate data → bridge.

    Returns:
        {
          "hive":    {id, name, invite_code},
          "workers": [{username, password, role, display_name}],
          "bridge":  {assets, logbook, inventory, pm_assets, pm_scope_items},
          "dataset_summary": {...},
          "login_url": "http://127.0.0.1:5000/workhive/index.html",
        }
    """
    profile = INDUSTRY_PROFILES.get(industry, INDUSTRY_PROFILES["food_processing"])

    # ── 1. Create hive ───────────────────────────────────────────────────────
    company_name = profile["company"]
    invite_code  = random_invite_code()
    log(f"Creating client hive: {company_name}...")

    res   = client.table("hives").insert({
        "name":       company_name,
        "invite_code": invite_code,
        "created_by": "CMMS Bridge",
    }).execute()
    hive  = res.data[0]
    hive_id = hive["id"]
    log(f"  hive created: {hive_id[:8]}... invite={invite_code}")

    # ── 2. Create workers ────────────────────────────────────────────────────
    log(f"Creating 1 supervisor + {N_WORKERS} workers...")
    workers       = []
    used_names:   set = set()
    used_usernames: set = set()

    roles = [("supervisor", 1)] + [("worker", N_WORKERS)]
    creds = []  # returned to caller

    for role, count in roles:
        for _ in range(count):
            # Unique name + username
            for _attempt in range(40):
                full = random_full_name()
                base = _sanitize_username(full)
                if full in used_names or base in used_usernames:
                    continue
                username = base
                suffix   = 0
                while username in used_usernames:
                    suffix  += 1
                    username = base[: 28 - len(str(suffix))] + str(suffix)
                used_names.add(full)
                used_usernames.add(username)
                break

            email = f"{username}{AUTH_DOMAIN}"

            # Supabase Auth user
            try:
                auth_resp = client.auth.admin.create_user({
                    "email":         email,
                    "password":      TEST_PASSWORD,
                    "email_confirm": True,
                })
                auth_uid = auth_resp.user.id
            except Exception as e:
                msg = str(e).lower()
                if "already" in msg or "exists" in msg or "registered" in msg:
                    log(f"  WARN: {email} already exists -- skipping")
                    try:
                        users = client.auth.admin.list_users()
                        match = next((u for u in users
                                      if getattr(u, "email", None) == email), None)
                        auth_uid = match.id if match else None
                    except Exception:
                        auth_uid = None
                else:
                    log(f"  ERROR creating {email}: {e}")
                    raise

            workers.append({
                "display_name": full,
                "worker_name":  full,
                "username":     username,
                "email":        email,
                "auth_uid":     auth_uid,
                "role":         role,
                "hive_id":      hive_id,
            })
            creds.append({
                "display_name": full,
                "username":     username,
                "password":     TEST_PASSWORD,
                "role":         role,
            })

    # worker_profiles
    profile_rows = [
        {"auth_uid": w["auth_uid"], "username": w["username"],
         "display_name": w["display_name"], "email": w["email"]}
        for w in workers if w["auth_uid"]
    ]
    if profile_rows:
        client.table("worker_profiles").insert(profile_rows).execute()

    # hive_members
    member_rows = [
        {"hive_id": w["hive_id"], "worker_name": w["worker_name"],
         "auth_uid": w["auth_uid"], "role": w["role"], "status": "active"}
        for w in workers
    ]
    client.table("hive_members").insert(member_rows).execute()
    log(f"  created {len(workers)} workers: "
        + ", ".join(f"{w['worker_name']} ({w['role']})" for w in workers))

    # Platform admin allowlist. The supervisor of a freshly-seeded local hive
    # is the founder for that environment; grant them Founder Console access
    # so the page is usable on first sign-in instead of bouncing to the gate.
    # 'Pablo Aguilar' is always inserted too (canonical local test identity,
    # see memory: reference_playwright_test_identity) so reseeds don't drop
    # the founder's saved wh_last_worker login.
    admin_rows = []
    sup = next((w for w in workers if w["role"] == "supervisor"), None)
    if sup:
        admin_rows.append({"worker_name": sup["worker_name"], "granted_by": "seeder"})
    if not any(r["worker_name"] == "Pablo Aguilar" for r in admin_rows):
        admin_rows.append({"worker_name": "Pablo Aguilar", "granted_by": "seeder"})
    try:
        client.table("marketplace_platform_admins") \
            .upsert(admin_rows, on_conflict="worker_name").execute()
        log(f"  platform admins seeded: " + ", ".join(r["worker_name"] for r in admin_rows))
    except Exception as e:
        log(f"  WARN: could not seed platform admins: {e}")

    # ── 3. Generate CMMS dataset ─────────────────────────────────────────────
    log(f"Generating {size} {cmms_type} dataset for {profile['label']}...")
    ds = generate_dataset(industry=industry, size=size, cmms_type=cmms_type,
                          seed=seed, log=log)

    # ── 4. Bridge into WorkHive tables ──────────────────────────────────────
    log("Bridging CMMS data into WorkHive tables...")
    bridge_result = bridge_to_workhive(client, ds, hive_id, workers, log=log)

    # Also write to external_sync for completeness
    from seeders.cmms_importer import import_from_dataset
    log("Writing to external_sync...")
    import_from_dataset(client, ds, hive_id=hive_id, log=log)

    # Seed integration_configs + api_keys so integrations.html has data on first load
    from seeders.cmms_config_seeder import seed_integration_config
    log("Seeding integration_configs and api_keys...")
    seed_integration_config(client, hive_id, cmms_type=cmms_type, log=log)

    supervisor_creds = next(c for c in creds if c["role"] == "supervisor")
    log(f"\nClient hive ready!")
    log(f"  Company: {company_name}")
    log(f"  Industry: {profile['label']} | CMMS: {cmms_type} | Size: {size}")
    log(f"  Login as supervisor: {supervisor_creds['username']} / {TEST_PASSWORD}")
    log(f"  Invite code: {invite_code}")
    log(f"  Logbook: {bridge_result['logbook']} entries | "
        f"Assets: {bridge_result['assets']} | "
        f"PM: {bridge_result['pm_assets']} schedules | "
        f"Parts: {bridge_result['inventory']}")

    return {
        "hive": {
            "id":          hive_id,
            "name":        company_name,
            "invite_code": invite_code,
            "industry":    profile["label"],
        },
        "workers":        creds,
        "bridge":         bridge_result,
        "dataset_summary": ds.summary(),
        "login_url":      "http://127.0.0.1:5000/workhive/index.html",
        "supervisor":     supervisor_creds,
    }
