# DB Adoption Report — Layer D (FULLSTACK_COMPONENT_LIBRARY_ROADMAP §1)

> MEASURED 2026-08-25 over **122** tables + **63** views (substrate live-DB derivation).

| ID | Canonical pattern | Adoption | % | Gap (first 8) |
|---|---|---|---|---|
| D1 | RLS enabled on tenant tables | **111/111** | **100%** | — |
| D2 | hive-membership scoping policy | **105/107** | **98%** | hive_service_settings, service_providers |
| D3 | auth_uid ownership policy | **31/33** | **94%** | credit_starter_grants, embedding_outbox |
| D4 | security_invoker on views | **57/63** | **90%** | v_cron_health, v_inventory_items_truth, v_service_job_tracking, v_service_open_broadcasts, v_service_provider_leaderboard, v_storage_health |
| D5 | bind_* attribution triggers | 15 table(s): analytics_events, asset_nodes, community_posts, community_reactions, community_replies, engineering_calcs, inventory_items, logbook | n/a | — |
