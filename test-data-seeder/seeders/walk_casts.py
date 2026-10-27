"""Walk casts - a supervisor the cube's walks may sign in as, in every hive whose only supervisor is a platform admin
(2026-10-28).

WHY: the cube (CX-PROD) walks each production page as each gate-admitted persona, and tools/lx_walk_args.py casts the
supervisor, fleet-supervisor and oversight personas as a NON-ADMIN active supervisor of the row's hive - an admin sees
surfaces nobody else does, so his page is not the persona's page. Baguio's and Lucena's only supervisors (Leandro
Marquez, Pablo Aguilar) are platform admins, so 430 rows had no cast, and the walk had been quietly falling back to a
WORKER for them - a supervisor's page judged as somebody who cannot see it.

WHAT: one deterministic, plainly-sample supervisor per such hive (an account, a worker profile, an active supervisor
membership), with the seed's shared test password. Idempotent: an existing account or membership is left alone. Runs
AFTER the probe fixtures, so the members those were authored by stay the members the probes pick.
"""
from .hives_workers import AUTH_DOMAIN, TEST_PASSWORD, PINNED_HIVE_IDS

# hive name -> the cast added to it (a name nothing else in the seed draws)
CASTS = {
    "Baguio Textile Mills": ("Ramon Castillo", "ramoncastillo"),
    "Lucena Pharmaceutical Mfg.": ("Marites Villanueva", "maritesvillanueva"),
}


def seed_walk_casts(client, log) -> dict:
    admins = {a["auth_uid"] for a in (client.table("marketplace_platform_admins").select("auth_uid").execute().data or [])}
    added = 0
    for hive_name, (display, username) in CASTS.items():
        hive_id = PINNED_HIVE_IDS.get(hive_name)
        if not hive_id:
            continue
        sups = (client.table("hive_members").select("auth_uid").eq("hive_id", hive_id).eq("role", "supervisor")
                .eq("status", "active").execute().data or [])
        if any(s.get("auth_uid") and s["auth_uid"] not in admins for s in sups):
            continue                                     # the hive already has a supervisor a walk may be
        email = f"{username}{AUTH_DOMAIN}"
        try:
            uid = client.auth.admin.create_user({"email": email, "password": TEST_PASSWORD, "email_confirm": True}).user.id
        except Exception as e:                           # an account left by an earlier run: find it
            if not any(w in str(e).lower() for w in ("already", "exists", "registered")):
                raise
            uid = next((u.id for u in client.auth.admin.list_users() if getattr(u, "email", None) == email), None)
        if not uid:
            log(f"  WARN walk cast {display}: no account")
            continue
        if not (client.table("worker_profiles").select("auth_uid").eq("auth_uid", uid).execute().data or []):
            client.table("worker_profiles").insert({"auth_uid": uid, "username": username, "display_name": display}).execute()
        client.table("hive_members").insert({"hive_id": hive_id, "auth_uid": uid, "worker_name": display,
                                             "role": "supervisor", "status": "active"}).execute()
        added += 1
        log(f"  walk cast: {display} - supervisor of {hive_name} (not a platform admin)")
    return {"walk_casts": added}
