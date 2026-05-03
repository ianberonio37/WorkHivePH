"""Wipe all seeded data, child tables first to respect FK constraints.
Also wipes Supabase Auth users (locally) so re-seed doesn't collide."""

# Order matters — children before parents.
RESET_TABLES = [
    "community_replies",
    "community_reactions",
    "community_posts",
    "marketplace_reviews",
    "marketplace_orders",
    "marketplace_listings",
    "skill_exam_attempts",
    "skill_badges",
    "skill_profiles",
    "inventory_transactions",
    "inventory_items",
    "pm_completions",
    "pm_scope_items",
    "pm_assets",
    "logbook",
    "assets",
    "hive_members",
    "worker_profiles",
    "hives",
]


def reset_all(client, log) -> dict:
    log("Wiping seeded tables (children first)...")
    summary: dict = {}
    for t in RESET_TABLES:
        try:
            res = client.table(t).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            n = len(res.data) if res.data else 0
            summary[t] = n
            log(f"  cleared {t} ({n} rows)")
        except Exception as e:
            log(f"  WARN: skipped {t}: {type(e).__name__}: {e}")
            summary[t] = f"error: {e}"

    # Wipe Auth users — only those with our test domain
    log("Wiping local Supabase Auth users (test domain only)...")
    auth_deleted = 0
    try:
        users_resp = client.auth.admin.list_users()
        # Response shape varies by SDK version; try both common forms
        users_iter = users_resp if isinstance(users_resp, list) else getattr(users_resp, "users", users_resp)
        for u in users_iter:
            email = getattr(u, "email", None) or (u.get("email") if isinstance(u, dict) else None)
            uid = getattr(u, "id", None) or (u.get("id") if isinstance(u, dict) else None)
            if email and "@auth.workhiveph.com" in email and uid:
                try:
                    client.auth.admin.delete_user(uid)
                    auth_deleted += 1
                except Exception as ex:
                    log(f"  WARN: could not delete auth user {email}: {ex}")
        log(f"  deleted {auth_deleted} auth users")
    except Exception as e:
        log(f"  WARN: auth wipe failed: {type(e).__name__}: {e}")

    summary["auth_users_deleted"] = auth_deleted
    return summary
