"""Wipe all seeded data, child tables first to respect FK constraints.
Also wipes Supabase Auth users (locally) so re-seed doesn't collide."""

# Order matters -- children before parents. Tables with PK other than 'id'
# go in RESET_TABLES_NON_ID below (uses a different sentinel filter).
RESET_TABLES = [
    # Project Manager (child -> parent)
    "project_progress_logs",
    "project_links",
    "project_items",
    "projects",
    # Auto-Staging (Phase ML-2)
    "parts_staged_reservations",
    "parts_staging_recommendations",
    # Predictive Analytics
    "asset_risk_scores",
    # Achievements (child -> parent)
    "achievement_xp_log",
    "worker_achievements",
    "achievement_definitions",
    # Asset Brain graph (child -> parent)
    "asset_embeddings",
    "asset_edges",
    "asset_nodes",
    # Shift Brain
    "shift_plans",
    # Community + marketplace
    "community_replies",
    "community_reactions",
    "community_posts",
    "marketplace_reviews",
    "marketplace_orders",
    "marketplace_listings",
    # Skill matrix
    "skill_exam_attempts",
    "skill_badges",
    "skill_profiles",
    "schedule_items",
    "engineering_calcs",
    # Knowledge + alerts
    "fault_knowledge",
    "failure_signature_alerts",
    # Benchmarks
    "hive_benchmarks",
    "network_benchmarks",
    # CMMS
    "cmms_audit_log",
    "external_sync",
    # Inventory
    "inventory_transactions",
    "inventory_items",
    # PM
    "pm_completions",
    "pm_scope_items",
    "pm_assets",
    # Logbook + assets
    "logbook",
    "assets",
    # Hive membership last (root)
    "hive_members",
    "worker_profiles",
    "hives",
]

# Tables that don't have an 'id' PK. Reset filters by a different column.
# Maps table -> (column, sentinel_value) used for the .neq() delete filter.
RESET_TABLES_NON_ID = {
    "ai_rate_limits": ("hive_id", "00000000-0000-0000-0000-000000000000"),
}


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

    # Tables without an 'id' column (e.g. ai_rate_limits keyed on hive_id)
    for t, (col, sentinel) in RESET_TABLES_NON_ID.items():
        try:
            res = client.table(t).delete().neq(col, sentinel).execute()
            n = len(res.data) if res.data else 0
            summary[t] = n
            log(f"  cleared {t} via {col} ({n} rows)")
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
