"""Seed hives + Supabase Auth users + worker_profiles + hive_members.

The platform stores `display_name` (e.g. 'Rosalia Vergara') as `worker_name`
in every hive-scoped table. So our seeded `worker_name` MUST equal
`display_name`. The `username` (sanitized) is only used for sign-in lookup.
"""
import random

from data.filipino_names import random_full_name
from data.ph_locations import CITIES, HIVE_TEMPLATES
from .utils import random_invite_code

WORKER_PROFILES = [
    {"role": "supervisor", "tier": "heavy", "logbook_target": 500, "count": 3},
    {"role": "worker", "tier": "active", "logbook_target": 300, "count": 5},
    {"role": "worker", "tier": "light", "logbook_target": 100, "count": 7},
]

# All seeded workers share this password — for local testing only.
TEST_PASSWORD = "test1234"
AUTH_DOMAIN = "@auth.workhiveph.com"


def _sanitize_username(name: str) -> str:
    """Match the platform's _syntheticEmail() sanitization: lowercase, only [a-z0-9_]."""
    out = []
    for ch in name.lower().replace("ñ", "n"):
        if ch.isalnum() or ch == "_":
            out.append(ch)
    sanitized = "".join(out)[:30]
    if len(sanitized) < 3:
        sanitized = (sanitized + "user")[:30]
    return sanitized


def _synthetic_email(username: str) -> str:
    return f"{username}{AUTH_DOMAIN}"


def seed_hives_and_workers(client, log) -> dict:
    log("Seeding 3 hives across PH industrial sectors...")

    used_cities = random.sample(CITIES, k=3)
    used_templates = random.sample(HIVE_TEMPLATES, k=3)

    hive_rows = []
    for city, tpl in zip(used_cities, used_templates):
        hive_rows.append({
            "name": tpl["name"].format(city=city),
            "invite_code": random_invite_code(),
            "created_by": "Seed Admin",
        })

    res = client.table("hives").insert(hive_rows).execute()
    hives = res.data
    log(f"  inserted {len(hives)} hives: {', '.join(h['name'] for h in hives)}")

    log("Generating 15 workers (3 supervisors, 5 active, 7 light) + Auth users...")
    workers = []
    used_display_names: set = set()
    used_usernames: set = set()

    for profile in WORKER_PROFILES:
        for _ in range(profile["count"]):
            # Generate unique full name + unique username
            for _attempt in range(40):
                full = random_full_name()
                base_username = _sanitize_username(full)
                if full in used_display_names or base_username in used_usernames:
                    continue
                # Add suffix if base collides
                username = base_username
                suffix = 0
                while username in used_usernames:
                    suffix += 1
                    username = (base_username[: 30 - len(str(suffix))]) + str(suffix)
                used_display_names.add(full)
                used_usernames.add(username)
                break

            email = _synthetic_email(username)

            # Create Supabase Auth user
            try:
                auth_resp = client.auth.admin.create_user({
                    "email": email,
                    "password": TEST_PASSWORD,
                    "email_confirm": True,
                })
                auth_uid = auth_resp.user.id
            except Exception as e:
                # If user already exists from a prior run, look up
                msg = str(e).lower()
                if "already" in msg or "exists" in msg or "registered" in msg:
                    log(f"  WARN: auth user {email} already exists — skipping creation")
                    # Best-effort: try to fetch user list and find by email
                    try:
                        users = client.auth.admin.list_users()
                        match = next((u for u in users if getattr(u, "email", None) == email), None)
                        auth_uid = match.id if match else None
                    except Exception:
                        auth_uid = None
                else:
                    log(f"  ERROR creating auth user {email}: {e}")
                    raise

            workers.append({
                "display_name": full,
                "worker_name": full,           # platform uses display_name as worker_name
                "username": username,
                "email": email,
                "auth_uid": auth_uid,
                "role": profile["role"],
                "tier": profile["tier"],
                "logbook_target": profile["logbook_target"],
                "hive_id": random.choice(hives)["id"],
            })

    log(f"  created {len(workers)} auth users (password for all: '{TEST_PASSWORD}')")

    # worker_profiles
    profile_rows = [
        {
            "auth_uid": w["auth_uid"],
            "username": w["username"],
            "display_name": w["display_name"],
            "email": w["email"],
        }
        for w in workers if w["auth_uid"]
    ]
    if profile_rows:
        client.table("worker_profiles").insert(profile_rows).execute()
    log(f"  inserted {len(profile_rows)} worker_profiles")

    # hive_members
    member_rows = [
        {
            "hive_id": w["hive_id"],
            "worker_name": w["worker_name"],
            "auth_uid": w["auth_uid"],
            "role": w["role"],
            "status": "active",
        }
        for w in workers
    ]
    client.table("hive_members").insert(member_rows).execute()
    log(f"  inserted {len(member_rows)} hive_members")

    hive_lookup = {h["id"]: h["name"] for h in hives}
    summary: dict = {}
    for w in workers:
        summary.setdefault(hive_lookup[w["hive_id"]], []).append(
            f"{w['display_name']} ({w['role']}/{w['tier']}, login: {w['username']})"
        )
    for hname, ws in summary.items():
        log(f"  {hname}: {len(ws)} members")
        for entry in ws:
            log(f"    - {entry}")

    return {"hives": hives, "workers": workers}
