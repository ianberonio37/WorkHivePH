"""Wipe all seeded data, child tables first to respect FK constraints.
Also wipes Supabase Auth users (locally) so re-seed doesn't collide.

NOTE: Catalog/reference tables populated only by migration INSERTs (no Python
seeder) MUST NOT be added here. Wiping them empties data that no seeder will
restore, and DB triggers FK-into them will then fail on the next user action.
Known catalog tables: achievement_definitions, equipment_reading_templates.
The reset-coverage validator skips these via CATALOG_TABLES_IGNORED."""

# Order matters -- children before parents. Tables with PK other than 'id'
# go in RESET_TABLES_NON_ID below (uses a different sentinel filter).
RESET_TABLES = [
    # 2026-05-21 paydown: new platform tables added in migrations, register
    # in reset.py so reset-coverage validator passes.
    "agentic_rag_traces",          # 20260521120000 — append-only RAG trace log
    "canonical_period_summaries",  # 20260521121000 — period rollup cache
    "agent_episodic_memory",       # 20260521122000 — per-worker episodic memory
    "unified_events",              # 20260521123000 — unified event stream
    # Voice Companion infra tables (20260521125000) — referenced from voice-handler.js
    "ai_audit_log",                # T95 audit log
    "ai_knowledge_gap",            # T113 knowledge gap logging
    "ai_quality_escalation",       # T46 thumbs-down escalation
    "shared_voice_notes",          # T147 team-thread notes
    "mentor_relay_queue",          # T114 mentor defer queue
    "companion_handoff",           # T146/T150/T154 cross-worker messages
    # Founder Console analytics (Phase 0) - append-only, no FKs
    "analytics_events",
    # Platform feedback (2026-05-19) - votes references feedback, so child first
    "platform_feedback_votes",
    "platform_feedback",
    # Platform Knowledge Graph facts (2026-05-19) - platform-wide hive-agnostic KG
    "platform_knowledge_graph_facts",
    # Project Manager (child -> parent)
    "project_progress_logs",
    "project_change_orders",
    "project_roles",
    "project_knowledge",
    "project_links",
    "project_items",
    "projects",
    # Auto-Staging (Phase ML-2)
    "parts_staged_reservations",
    "parts_staging_recommendations",
    # Reliability Engineering Workbench (Phase R.1) - children before parents.
    # rcm_strategies + weibull_fits + pf_intervals all reference rcm_fmea_modes.
    "pf_intervals",
    "weibull_fits",
    "rcm_strategies",
    "rcm_fmea_modes",
    # Predictive Analytics
    "asset_risk_scores",
    # Achievements (child -> parent).
    # achievement_definitions is a CATALOG table (migration-seeded), do NOT wipe.
    "achievement_xp_log",
    "worker_achievements",
    # Asset Brain graph (child -> parent)
    "asset_embeddings",
    "asset_edges",
    "asset_nodes",
    # Shift Brain
    "shift_plans",
    # Community + XP
    "community_xp",
    "community_replies",
    "community_reactions",
    "community_posts",
    # Marketplace (children -> parents)
    "marketplace_disputes",
    "marketplace_inquiries",
    "marketplace_watchlist",
    "marketplace_saved_searches",
    "marketplace_reviews",
    "marketplace_orders",
    "marketplace_listings",
    "marketplace_sellers",
    "marketplace_platform_admins",
    # Skill matrix + lessons
    "skill_exam_attempts",
    "skill_badges",
    "skill_profiles",
    "skill_knowledge",
    "schedule_items",
    "engineering_calcs",
    # Knowledge tables
    "bom_knowledge",
    "calc_knowledge",
    "pm_knowledge",
    "fault_knowledge",
    # Alerts
    "failure_signature_alerts",
    # Benchmarks + reports
    "ph_intelligence_reports",
    "hive_benchmarks",
    "network_benchmarks",
    "ai_reports",
    "report_contacts",
    # CMMS
    "cmms_audit_log",
    "external_sync",
    "integration_configs",
    "api_keys",
    # Logs + cache + audit
    "automation_log",
    "hive_audit_log",
    "hive_analytics_cache",
    "agent_memory",
    "dialog_state",
    "anomaly_alerts",
    "kb_documents",
    "kb_chunks",
    "industry_standards_chunks",
    "offline_snapshot_cache",
    "voice_response_queue",
    "fallback_model_faq",
    "tts_cache",
    "tts_quality_log",
    "conversation_analytics",
    "cross_hive_alerts",
    "best_practices",
    "avatar_state",
    "avatar_animations",
    "multilingual_terms",
    "language_preferences",
    "terminology_gaps",
    "voice_journal_entries",
    "amc_briefings",
    "hive_readiness_audit",
    "hive_readiness",
    "hive_adoption_score",
    "anomaly_signals",
    "auth_session_events",
    # Phase 5 enterprise scaffolding — config-class but listed here so re-seed
    # against a fresh local stack is idempotent. Production operators
    # provision these via the supervisor UI, not the seeder; the reset.py
    # write is a no-op when nothing exists.
    "hive_retention_config",
    "mfa_enrollments",
    "sso_configs",
    # Phase 6 industry-defining scaffolding. industry_standards is a catalog
    # table (migration-seeded) — do NOT wipe in normal flow. The other three
    # are hive-scoped runtime tables and reset cleanly.
    "knowledge_graph_facts",
    "drone_inspections",
    "consulting_engagements",
    "sensor_readings",
    "sensor_topic_map",
    "hive_quotas",
    "ai_cost_log",
    "ai_quality_log",
    "gateway_audit_log",
    "pdf_jobs",
    "hive_route_calls",
    "hive_route_quotas",
    # Inventory + parts
    "parts_records",
    "inventory_transactions",
    "inventory_items",
    # PM
    "pm_completions",
    "pm_scope_items",
    "pm_assets",
    # equipment_reading_templates is a CATALOG table (migration-seeded), do NOT wipe.
    # Logbook (asset_nodes is wiped earlier in the canonical layer; the
    # legacy `assets` table was dropped in Phase 5c 2026-05-12).
    "logbook",
    # Standalone misc
    "early_access_emails",
    # Hive membership last (root)
    "hive_members",
    "worker_profiles",
    "hives",
    # Canonical contract glue (2026-05-20). Platform-scoped, hive-agnostic;
    # safe to wipe between resets since seed data is in canonical/*.json.
    "canonical_lineage_edges",
]

# Tables that don't have an 'id' PK. Reset filters by a different column.
# Maps table -> (column, sentinel_value) used for the .neq() delete filter.
RESET_TABLES_NON_ID = {
    "ai_rate_limits":   ("hive_id", "00000000-0000-0000-0000-000000000000"),
    # 2026-05-21 paydown: composite-PK tables from voice-handler infra migration.
    "asset_watchlist":   ("hive_id", "00000000-0000-0000-0000-000000000000"),
    "wh_feature_flags":  ("hive_id", "00000000-0000-0000-0000-000000000000"),
    "wh_voice_presence": ("hive_id", "00000000-0000-0000-0000-000000000000"),
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
