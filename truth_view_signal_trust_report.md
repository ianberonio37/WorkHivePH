# Truth-View Signal-Trust Miner (L-1)

Catches **semantic drift inside the same canonical column** —
two surfaces read the same `v_*_truth` column but interpret it
differently (one trusts it; one re-gates on another field).

## Summary

- View/column pairs scanned: **336**
- AT_RISK pairs (re-gating detected): **0**
- REVIEW pairs (local-math smell on at least one consumer): **9**
- Files scanned: **209**

## Smell legend

Smells are file-level hints that the consumer may be locally
re-deriving what the canonical view should expose:
- `re_computes_overdue` — `Date.now() - new Date(last_completed)` arithmetic
- `hardcoded_freq_days` — `FREQ_DAYS[...]` / `calcNextDue(...)` / `getItemStatus(...)`
- `manual_qty_threshold` — `qty_on_hand < reorder_point` instead of `is_low_stock`
- `manual_risk_band` — `risk_score > 80` instead of view-exposed band
- `manual_age_days` — `daysUntil(...)` / floor(now - x / 86400000) arithmetic
- `nodata_fallback` — `'nodata'` string literal (re-gating signature)

## ⚠️ REVIEW pairs (multiple consumers with local-math smell)

| View | Column | Consumers (file → shape) | File-level smells |
|---|---|---|---|
| `v_pm_scope_items_truth` | `anchor_date` | `logbook.html` → `direct` 🚩nodata_fallback<br>`pm-scheduler.html` → `direct` | nodata_fallback |
| `v_pm_scope_items_truth` | `asset_id` | `logbook.html` → `direct` 🚩nodata_fallback<br>`pm-scheduler.html` → `direct`<br>`supabase/functions/analytics-orchestrator/index.ts` → `direct`<br>`supabase/functions/batch-risk-scoring/index.ts` → `direct`<br>`supabase/functions/trigger-ml-retrain/index.ts` → `direct` | nodata_fallback |
| `v_pm_scope_items_truth` | `days_until_due` | `logbook.html` → `direct` 🚩nodata_fallback<br>`pm-scheduler.html` → `direct` | nodata_fallback |
| `v_pm_scope_items_truth` | `frequency` | `hive.html` → `direct`<br>`logbook.html` → `direct` 🚩nodata_fallback<br>`pm-scheduler.html` → `direct`<br>`supabase/functions/analytics-orchestrator/index.ts` → `direct`<br>`supabase/functions/batch-risk-scoring/index.ts` → `direct`<br>`supabase/functions/trigger-ml-retrain/index.ts` → `direct` | nodata_fallback |
| `v_pm_scope_items_truth` | `is_due_soon` | `hive.html` → `direct`<br>`logbook.html` → `mapped_enum` 🚩nodata_fallback<br>`pm-scheduler.html` → `direct` | nodata_fallback |
| `v_pm_scope_items_truth` | `is_overdue` | `hive.html` → `direct`<br>`index.html` → `direct`<br>`logbook.html` → `mapped_enum` 🚩nodata_fallback<br>`pm-scheduler.html` → `direct` | nodata_fallback |
| `v_pm_scope_items_truth` | `item_text` | `hive.html` → `direct`<br>`logbook.html` → `direct` 🚩nodata_fallback<br>`pm-scheduler.html` → `direct`<br>`supabase/functions/analytics-orchestrator/index.ts` → `direct`<br>`supabase/functions/batch-risk-scoring/index.ts` → `direct`<br>`supabase/functions/trigger-ml-retrain/index.ts` → `direct` | nodata_fallback |
| `v_pm_scope_items_truth` | `next_due_date` | `logbook.html` → `direct` 🚩nodata_fallback<br>`pm-scheduler.html` → `direct` | nodata_fallback |
| `v_pm_scope_items_truth` | `scope_item_id` | `hive.html` → `direct`<br>`logbook.html` → `direct` 🚩nodata_fallback<br>`pm-scheduler.html` → `direct`<br>`supabase/functions/platform-scraper/index.ts` → `direct` | nodata_fallback |

## All pairs (informational)

| View | Column | Risk | Consumer count | Distinct shapes |
|---|---|:---:|---:|---|
| `v_adoption_truth` | `active_ratio_risk` | ✅ OK | 1 | direct |
| `v_adoption_truth` | `active_workers_week` | ✅ OK | 2 | direct |
| `v_adoption_truth` | `adoption_score` | ✅ OK | 2 | direct |
| `v_adoption_truth` | `momentum_risk` | ✅ OK | 1 | direct |
| `v_adoption_truth` | `risk_score` | ✅ OK | 1 | direct |
| `v_adoption_truth` | `risk_tier` | ✅ OK | 1 | direct |
| `v_adoption_truth` | `snapshot_date` | ✅ OK | 1 | direct |
| `v_ai_reports_truth` | `generated_at` | ✅ OK | 1 | direct |
| `v_ai_reports_truth` | `report_json` | ✅ OK | 1 | direct |
| `v_ai_reports_truth` | `report_type` | ✅ OK | 2 | direct |
| `v_ai_reports_truth` | `summary` | ✅ OK | 2 | direct |
| `v_alert_truth` | `alert_id` | ✅ OK | 1 | direct |
| `v_alert_truth` | `category` | ✅ OK | 1 | direct |
| `v_alert_truth` | `detail` | ✅ OK | 1 | direct |
| `v_alert_truth` | `detected_at` | ✅ OK | 2 | direct |
| `v_alert_truth` | `machine` | ✅ OK | 2 | direct |
| `v_alert_truth` | `rule_id` | ✅ OK | 1 | direct |
| `v_alert_truth` | `severity` | ✅ OK | 2 | direct |
| `v_alert_truth` | `title` | ✅ OK | 2 | direct |
| `v_amc_truth` | `amc_id` | ✅ OK | 1 | direct |
| `v_amc_truth` | `headline` | ✅ OK | 1 | direct |
| `v_amc_truth` | `shift_date` | ✅ OK | 1 | direct |
| `v_amc_truth` | `status` | ✅ OK | 2 | direct |
| `v_amc_truth` | `summary` | ✅ OK | 1 | direct |
| `v_anomaly_truth` | `composite_score` | ✅ OK | 2 | direct |
| `v_anomaly_truth` | `computed_at` | ✅ OK | 1 | direct |
| `v_anomaly_truth` | `logbook_cluster_score` | ✅ OK | 1 | direct |
| `v_anomaly_truth` | `machine` | ✅ OK | 2 | direct |
| `v_anomaly_truth` | `severity` | ✅ OK | 1 | direct |
| `v_anomaly_truth` | `snapshot_date` | ✅ OK | 1 | direct |
| `v_anomaly_truth` | `source_count` | ✅ OK | 1 | direct |
| `v_anomaly_truth` | `status` | ✅ OK | 1 | direct |
| `v_anomaly_truth` | `top_reasons` | ✅ OK | 1 | direct |
| `v_asset_state_truth` | `asset_tag` | ✅ OK | 1 | direct |
| `v_asset_state_truth` | `conflict_count` | ✅ OK | 1 | direct |
| `v_asset_state_truth` | `event_type` | ✅ OK | 1 | direct |
| `v_asset_state_truth` | `ingested_at` | ✅ OK | 1 | direct |
| `v_asset_state_truth` | `source_id` | ✅ OK | 1 | direct |
| `v_asset_state_truth` | `superseded_count` | ✅ OK | 1 | direct |
| `v_asset_state_truth` | `verified_at` | ✅ OK | 1 | direct |
| `v_asset_state_truth` | `verified_payload` | ✅ OK | 1 | direct |
| `v_asset_state_truth` | `verified_source` | ✅ OK | 1 | direct |
| `v_asset_state_truth` | `verified_source_rank` | ✅ OK | 1 | direct |
| `v_asset_state_truth` | `verified_text` | ✅ OK | 1 | direct |
| `v_asset_truth` | `asset_id` | ✅ OK | 7 | direct |
| `v_asset_truth` | `asset_tag` | ✅ OK | 1 | direct |
| `v_asset_truth` | `category` | ✅ OK | 1 | direct |
| `v_asset_truth` | `count` | ✅ OK | 2 | direct |
| `v_asset_truth` | `criticality` | ✅ OK | 3 | direct |
| `v_asset_truth` | `description` | ✅ OK | 1 | direct |
| `v_asset_truth` | `edge_count` | ✅ OK | 2 | direct |
| `v_asset_truth` | `external_ids` | ✅ OK | 1 | direct |
| `v_asset_truth` | `iso_class` | ✅ OK | 5 | direct |
| `v_asset_truth` | `last_failure_at` | ✅ OK | 3 | direct |
| `v_asset_truth` | `last_pm_at` | ✅ OK | 1 | direct |
| `v_asset_truth` | `legacy_asset_id` | ✅ OK | 5 | direct |
| `v_asset_truth` | `level` | ✅ OK | 2 | direct |
| `v_asset_truth` | `lifetime_logbook_entries` | ✅ OK | 3 | direct |
| `v_asset_truth` | `location` | ✅ OK | 2 | direct |
| `v_asset_truth` | `manufacturer` | ✅ OK | 2 | direct |
| `v_asset_truth` | `model` | ✅ OK | 2 | direct |
| `v_asset_truth` | `name` | ✅ OK | 10 | direct |
| `v_asset_truth` | `next_pm_at` | ✅ OK | 1 | direct |
| `v_asset_truth` | `parent_id` | ✅ OK | 1 | direct |
| `v_asset_truth` | `pm_asset_id` | ✅ OK | 1 | direct |
| `v_asset_truth` | `pm_completed_count` | ✅ OK | 2 | direct |
| `v_asset_truth` | `state` | ✅ OK | 2 | direct |
| `v_asset_truth` | `status` | ✅ OK | 1 | direct |
| `v_asset_truth` | `tag` | ✅ OK | 11 | direct |
| `v_community_posts_truth` | `author_name` | ✅ OK | 2 | direct |
| `v_community_posts_truth` | `category` | ✅ OK | 2 | direct |
| `v_community_posts_truth` | `content` | ✅ OK | 2 | direct |
| `v_community_posts_truth` | `edited_at` | ✅ OK | 1 | direct |
| `v_community_posts_truth` | `flagged` | ✅ OK | 1 | direct |
| `v_community_posts_truth` | `hive_name` | ✅ OK | 1 | direct |
| `v_community_posts_truth` | `mentions` | ✅ OK | 1 | direct |
| `v_community_posts_truth` | `pinned` | ✅ OK | 1 | direct |
| `v_community_posts_truth` | `public` | ✅ OK | 1 | direct |
| `v_external_sync_truth` | `entity_type` | ✅ OK | 2 | direct |
| `v_external_sync_truth` | `external_id` | ✅ OK | 4 | direct |
| `v_external_sync_truth` | `last_synced_at` | ✅ OK | 3 | direct |
| `v_external_sync_truth` | `status` | ✅ OK | 3 | direct |
| `v_external_sync_truth` | `sync_payload` | ✅ OK | 2 | direct |
| `v_external_sync_truth` | `sync_status` | ✅ OK | 1 | direct |
| `v_external_sync_truth` | `system_type` | ✅ OK | 3 | direct |
| `v_external_sync_truth` | `workhive_table` | ✅ OK | 1 | direct |
| `v_fmea_truth` | `ai_confidence` | ✅ OK | 1 | direct |
| `v_fmea_truth` | `approved_at` | ✅ OK | 1 | direct |
| `v_fmea_truth` | `asset_id` | ✅ OK | 1 | direct |
| `v_fmea_truth` | `cause_text` | ✅ OK | 2 | direct |
| `v_fmea_truth` | `consequence_class` | ✅ OK | 2 | direct |
| `v_fmea_truth` | `detection` | ✅ OK | 2 | direct |
| `v_fmea_truth` | `effect_text` | ✅ OK | 2 | direct |
| `v_fmea_truth` | `failure_mode` | ✅ OK | 3 | direct |
| `v_fmea_truth` | `function_text` | ✅ OK | 2 | direct |
| `v_fmea_truth` | `occurrence` | ✅ OK | 2 | direct |
| `v_fmea_truth` | `rpn` | ✅ OK | 3 | direct |
| `v_fmea_truth` | `severity` | ✅ OK | 2 | direct |
| `v_fmea_truth` | `source` | ✅ OK | 2 | direct |
| `v_hive_readiness_truth` | `blocker_summary` | ✅ OK | 2 | direct |
| `v_hive_readiness_truth` | `composite_score` | ✅ OK | 2 | direct |
| `v_hive_readiness_truth` | `current_stair` | ✅ OK | 2 | direct |
| `v_hive_readiness_truth` | `evidence` | ✅ OK | 1 | direct |
| `v_hives_truth` | `created_by` | ✅ OK | 1 | direct |
| `v_hives_truth` | `hive_members` | ✅ OK | 1 | direct |
| `v_hives_truth` | `intent` | ✅ OK | 1 | direct |
| `v_hives_truth` | `name` | ✅ OK | 7 | direct |
| `v_hives_truth` | `preferred_persona` | ✅ OK | 2 | direct |
| `v_inventory_items_truth` | `bin_location` | ✅ OK | 2 | direct |
| `v_inventory_items_truth` | `category` | ✅ OK | 1 | direct |
| `v_inventory_items_truth` | `count` | ✅ OK | 1 | direct |
| `v_inventory_items_truth` | `is_low_stock` | ✅ OK | 3 | direct |
| `v_inventory_items_truth` | `is_out_of_stock` | ✅ OK | 1 | direct |
| `v_inventory_items_truth` | `min_qty` | ✅ OK | 4 | direct |
| `v_inventory_items_truth` | `part_name` | ✅ OK | 13 | direct |
| `v_inventory_items_truth` | `part_number` | ✅ OK | 5 | direct |
| `v_inventory_items_truth` | `qty_on_hand` | ✅ OK | 11 | direct |
| `v_inventory_items_truth` | `reorder_point` | ✅ OK | 7 | direct |
| `v_inventory_items_truth` | `status` | ✅ OK | 2 | direct |
| `v_inventory_items_truth` | `unit` | ✅ OK | 2 | direct |
| `v_inventory_items_truth` | `worker_name` | ✅ OK | 1 | direct |
| `v_inventory_transactions_truth` | `inventory_items` | ✅ OK | 3 | direct |
| `v_inventory_transactions_truth` | `item_id` | ✅ OK | 1 | direct |
| `v_inventory_transactions_truth` | `job_ref` | ✅ OK | 1 | direct |
| `v_inventory_transactions_truth` | `note` | ✅ OK | 1 | direct |
| `v_inventory_transactions_truth` | `qty_change` | ✅ OK | 4 | direct |
| `v_inventory_transactions_truth` | `type` | ✅ OK | 3 | direct |
| `v_knowledge_freshness_truth` | `days_since_last_embed` | ✅ OK | 1 | direct |
| `v_knowledge_freshness_truth` | `embedded_pct` | ✅ OK | 1 | direct |
| `v_knowledge_freshness_truth` | `embedded_rows` | ✅ OK | 1 | direct |
| `v_knowledge_freshness_truth` | `kind` | ✅ OK | 1 | direct |
| `v_knowledge_freshness_truth` | `last_embedded_at` | ✅ OK | 1 | direct |
| `v_knowledge_freshness_truth` | `pending_rows` | ✅ OK | 1 | direct |
| `v_knowledge_freshness_truth` | `total_rows` | ✅ OK | 1 | direct |
| `v_knowledge_truth` | `content` | ✅ OK | 1 | direct |
| `v_knowledge_truth` | `source` | ✅ OK | 1 | direct |
| `v_kpi_truth` | `failures_30d` | ✅ OK | 1 | direct |
| `v_kpi_truth` | `machine` | ✅ OK | 1 | direct |
| `v_kpi_truth` | `mtbf_30d` | ✅ OK | 1 | direct |
| `v_kpi_truth` | `mttr_30d` | ✅ OK | 1 | direct |
| `v_kpi_truth` | `total_downtime_30d` | ✅ OK | 1 | direct |
| `v_logbook_truth` | `action` | ✅ OK | 10 | direct |
| `v_logbook_truth` | `asset_node_id` | ✅ OK | 1 | direct |
| `v_logbook_truth` | `asset_tag` | ✅ OK | 2 | direct |
| `v_logbook_truth` | `category` | ✅ OK | 12 | direct |
| `v_logbook_truth` | `closed_at` | ✅ OK | 4 | direct |
| `v_logbook_truth` | `date` | ✅ OK | 6 | direct |
| `v_logbook_truth` | `downtime_hours` | ✅ OK | 14 | direct |
| `v_logbook_truth` | `failure_consequence` | ✅ OK | 3 | direct |
| `v_logbook_truth` | `issue` | ✅ OK | 1 | direct |
| `v_logbook_truth` | `knowledge` | ✅ OK | 2 | direct |
| `v_logbook_truth` | `machine` | ✅ OK | 23 | direct |
| `v_logbook_truth` | `maintenance_type` | ✅ OK | 21 | direct |
| `v_logbook_truth` | `parts_used` | ✅ OK | 2 | direct |
| `v_logbook_truth` | `problem` | ✅ OK | 14 | direct |
| `v_logbook_truth` | `production_output` | ✅ OK | 1 | direct |
| `v_logbook_truth` | `readings_json` | ✅ OK | 2 | direct |
| `v_logbook_truth` | `root_cause` | ✅ OK | 15 | direct |
| `v_logbook_truth` | `status` | ✅ OK | 17 | direct |
| `v_logbook_truth` | `worker_name` | ✅ OK | 7 | direct |
| `v_marketplace_inquiries_truth` | `buyer_contact` | ✅ OK | 1 | direct |
| `v_marketplace_inquiries_truth` | `buyer_name` | ✅ OK | 1 | direct |
| `v_marketplace_inquiries_truth` | `listing_id` | ✅ OK | 1 | direct |
| `v_marketplace_inquiries_truth` | `listing_title` | ✅ OK | 1 | direct |
| `v_marketplace_inquiries_truth` | `message` | ✅ OK | 1 | direct |
| `v_marketplace_inquiries_truth` | `replied_at` | ✅ OK | 2 | direct |
| `v_marketplace_inquiries_truth` | `reply_text` | ✅ OK | 1 | direct |
| `v_marketplace_inquiries_truth` | `status` | ✅ OK | 2 | direct |
| `v_marketplace_listings_truth` | `category` | ✅ OK | 5 | direct |
| `v_marketplace_listings_truth` | `completed_sales` | ✅ OK | 1 | direct |
| `v_marketplace_listings_truth` | `condition` | ✅ OK | 5 | direct, mapped_enum |
| `v_marketplace_listings_truth` | `description` | ✅ OK | 2 | direct |
| `v_marketplace_listings_truth` | `image_url` | ✅ OK | 5 | direct |
| `v_marketplace_listings_truth` | `location` | ✅ OK | 5 | direct, mapped_enum |
| `v_marketplace_listings_truth` | `price` | ✅ OK | 6 | direct |
| `v_marketplace_listings_truth` | `rating_avg` | ✅ OK | 1 | direct |
| `v_marketplace_listings_truth` | `section` | ✅ OK | 6 | direct |
| `v_marketplace_listings_truth` | `seller_contact` | ✅ OK | 2 | direct |
| `v_marketplace_listings_truth` | `seller_name` | ✅ OK | 4 | direct |
| `v_marketplace_listings_truth` | `seller_verified` | ✅ OK | 2 | direct, mapped_enum |
| `v_marketplace_listings_truth` | `status` | ✅ OK | 5 | direct |
| `v_marketplace_listings_truth` | `title` | ✅ OK | 7 | direct |
| `v_marketplace_listings_truth` | `view_count` | ✅ OK | 1 | direct |
| `v_marketplace_orders_truth` | `buyer_name` | ✅ OK | 2 | direct |
| `v_marketplace_orders_truth` | `escrow_release_at` | ✅ OK | 2 | direct |
| `v_marketplace_orders_truth` | `listing_id` | ✅ OK | 2 | direct |
| `v_marketplace_orders_truth` | `marketplace_listings` | ✅ OK | 1 | direct |
| `v_marketplace_orders_truth` | `price` | ✅ OK | 5 | direct |
| `v_marketplace_orders_truth` | `reviewed_at` | ✅ OK | 1 | direct |
| `v_marketplace_orders_truth` | `seller_name` | ✅ OK | 2 | direct |
| `v_marketplace_orders_truth` | `status` | ✅ OK | 5 | direct |
| `v_marketplace_orders_truth` | `stripe_payment_id` | ✅ OK | 1 | direct |
| `v_marketplace_orders_truth` | `stripe_session_id` | ✅ OK | 1 | direct |
| `v_marketplace_orders_truth` | `stripe_transfer_id` | ✅ OK | 1 | direct |
| `v_marketplace_sellers_truth` | `active_listings_count` | ✅ OK | 3 | direct |
| `v_marketplace_sellers_truth` | `cert_verified` | ✅ OK | 3 | direct |
| `v_marketplace_sellers_truth` | `cert_verified_at` | ✅ OK | 2 | direct |
| `v_marketplace_sellers_truth` | `certifications` | ✅ OK | 3 | direct |
| `v_marketplace_sellers_truth` | `is_verified_public` | ✅ OK | 3 | direct |
| `v_marketplace_sellers_truth` | `kyb_verified` | ✅ OK | 6 | direct |
| `v_marketplace_sellers_truth` | `kyb_verified_at` | ✅ OK | 2 | direct |
| `v_marketplace_sellers_truth` | `last_listed_at` | ✅ OK | 2 | direct |
| `v_marketplace_sellers_truth` | `messenger_username` | ✅ OK | 2 | direct |
| `v_marketplace_sellers_truth` | `rating_avg` | ✅ OK | 3 | direct |
| `v_marketplace_sellers_truth` | `rating_count` | ✅ OK | 2 | direct |
| `v_marketplace_sellers_truth` | `stripe_account_id` | ✅ OK | 5 | direct |
| `v_marketplace_sellers_truth` | `tier` | ✅ OK | 4 | direct |
| `v_marketplace_sellers_truth` | `total_sales` | ✅ OK | 2 | direct |
| `v_marketplace_sellers_truth` | `worker_name` | ✅ OK | 2 | direct |
| `v_pf_truth` | `basis` | ✅ OK | 2 | direct |
| `v_pf_truth` | `f_threshold` | ✅ OK | 2 | direct |
| `v_pf_truth` | `generated_at` | ✅ OK | 1 | direct |
| `v_pf_truth` | `p_threshold` | ✅ OK | 2 | direct |
| `v_pf_truth` | `parameter` | ✅ OK | 2 | direct |
| `v_pf_truth` | `pf_days` | ✅ OK | 2 | direct |
| `v_pf_truth` | `recommended_interval_days` | ✅ OK | 2 | direct |
| `v_pm_compliance_truth` | `asset_id` | ✅ OK | 6 | direct |
| `v_pm_compliance_truth` | `asset_name` | ✅ OK | 14 | direct |
| `v_pm_compliance_truth` | `category` | ✅ OK | 13 | direct |
| `v_pm_compliance_truth` | `completed_at` | ✅ OK | 6 | direct |
| `v_pm_compliance_truth` | `completions_30d` | ✅ OK | 2 | direct |
| `v_pm_compliance_truth` | `criticality` | ✅ OK | 6 | direct |
| `v_pm_compliance_truth` | `days_since_last_completion` | ✅ OK | 4 | direct |
| `v_pm_compliance_truth` | `is_due` | ✅ OK | 4 | direct |
| `v_pm_compliance_truth` | `last_anchor_date` | ✅ OK | 4 | direct |
| `v_pm_compliance_truth` | `last_completion_at` | ✅ OK | 1 | direct |
| `v_pm_compliance_truth` | `location` | ✅ OK | 1 | direct |
| `v_pm_compliance_truth` | `pm_asset_id` | ✅ OK | 6 | direct |
| `v_pm_compliance_truth` | `scope_item_id` | ✅ OK | 4 | direct |
| `v_pm_compliance_truth` | `status` | ✅ OK | 3 | direct |
| `v_pm_compliance_truth` | `tag_id` | ✅ OK | 5 | direct |
| `v_pm_compliance_truth` | `worker_name` | ✅ OK | 2 | direct |
| `v_pm_scope_items_truth` | `anchor_date` | ⚠️ REVIEW | 2 | direct |
| `v_pm_scope_items_truth` | `asset_criticality` | ✅ OK | 1 | direct |
| `v_pm_scope_items_truth` | `asset_id` | ⚠️ REVIEW | 5 | direct |
| `v_pm_scope_items_truth` | `asset_name` | ✅ OK | 2 | direct |
| `v_pm_scope_items_truth` | `asset_tag` | ✅ OK | 1 | direct |
| `v_pm_scope_items_truth` | `count` | ✅ OK | 1 | direct |
| `v_pm_scope_items_truth` | `days_until_due` | ⚠️ REVIEW | 2 | direct |
| `v_pm_scope_items_truth` | `frequency` | ⚠️ REVIEW | 6 | direct |
| `v_pm_scope_items_truth` | `frequency_days` | ✅ OK | 1 | direct |
| `v_pm_scope_items_truth` | `is_custom` | ✅ OK | 1 | direct |
| `v_pm_scope_items_truth` | `is_due_soon` | ⚠️ REVIEW | 3 | direct, mapped_enum |
| `v_pm_scope_items_truth` | `is_overdue` | ⚠️ REVIEW | 4 | direct, mapped_enum |
| `v_pm_scope_items_truth` | `item_text` | ⚠️ REVIEW | 6 | direct |
| `v_pm_scope_items_truth` | `last_completed_at` | ✅ OK | 1 | direct |
| `v_pm_scope_items_truth` | `last_completed_by` | ✅ OK | 1 | direct |
| `v_pm_scope_items_truth` | `next_due_date` | ⚠️ REVIEW | 2 | direct |
| `v_pm_scope_items_truth` | `pm_asset_id` | ✅ OK | 2 | direct |
| `v_pm_scope_items_truth` | `scope_item_id` | ⚠️ REVIEW | 4 | direct |
| `v_project_items_truth` | `actual_hours` | ✅ OK | 2 | direct |
| `v_project_items_truth` | `estimated_hours` | ✅ OK | 3 | direct |
| `v_project_items_truth` | `notes` | ✅ OK | 2 | direct |
| `v_project_items_truth` | `owner_name` | ✅ OK | 2 | direct |
| `v_project_items_truth` | `pct_complete` | ✅ OK | 3 | direct |
| `v_project_items_truth` | `planned_end` | ✅ OK | 2 | direct |
| `v_project_items_truth` | `planned_start` | ✅ OK | 1 | direct |
| `v_project_items_truth` | `predecessors` | ✅ OK | 1 | direct |
| `v_project_items_truth` | `project_id` | ✅ OK | 1 | direct |
| `v_project_items_truth` | `sort_order` | ✅ OK | 1 | direct |
| `v_project_items_truth` | `status` | ✅ OK | 3 | direct |
| `v_project_items_truth` | `title` | ✅ OK | 2 | direct |
| `v_project_progress_truth` | `acknowledged_at` | ✅ OK | 1 | direct |
| `v_project_progress_truth` | `acknowledged_by` | ✅ OK | 1 | direct |
| `v_project_progress_truth` | `blockers` | ✅ OK | 3 | direct |
| `v_project_progress_truth` | `hours_worked` | ✅ OK | 2 | direct |
| `v_project_progress_truth` | `log_date` | ✅ OK | 3 | direct |
| `v_project_progress_truth` | `notes` | ✅ OK | 2 | direct |
| `v_project_progress_truth` | `pct_complete` | ✅ OK | 2 | direct |
| `v_project_progress_truth` | `project_id` | ✅ OK | 1 | direct |
| `v_project_progress_truth` | `reported_by` | ✅ OK | 2 | direct |
| `v_project_truth` | `budget_php` | ✅ OK | 1 | direct |
| `v_project_truth` | `end_date` | ✅ OK | 1 | direct |
| `v_project_truth` | `name` | ✅ OK | 2 | direct |
| `v_project_truth` | `priority` | ✅ OK | 1 | direct |
| `v_project_truth` | `project_code` | ✅ OK | 3 | direct |
| `v_project_truth` | `project_type` | ✅ OK | 3 | direct |
| `v_project_truth` | `start_date` | ✅ OK | 1 | direct |
| `v_project_truth` | `status` | ✅ OK | 3 | direct |
| `v_rcm_truth` | `approved_at` | ✅ OK | 1 | direct |
| `v_rcm_truth` | `decision` | ✅ OK | 2 | direct |
| `v_rcm_truth` | `fmea_mode_id` | ✅ OK | 1 | direct |
| `v_rcm_truth` | `interval_days` | ✅ OK | 2 | direct |
| `v_rcm_truth` | `rationale` | ✅ OK | 2 | direct |
| `v_rcm_truth` | `source` | ✅ OK | 1 | direct |
| `v_rcm_truth` | `strategy_id` | ✅ OK | 1 | direct |
| `v_rcm_truth` | `task_text` | ✅ OK | 2 | direct |
| `v_rcm_truth` | `written_to_pm_scope_item_id` | ✅ OK | 2 | direct |
| `v_risk_truth` | `asset_id` | ✅ OK | 5 | direct |
| `v_risk_truth` | `asset_name` | ✅ OK | 11 | direct |
| `v_risk_truth` | `days_until_failure` | ✅ OK | 6 | direct |
| `v_risk_truth` | `generated_at` | ✅ OK | 8 | direct |
| `v_risk_truth` | `health_score` | ✅ OK | 2 | direct |
| `v_risk_truth` | `model_version` | ✅ OK | 3 | direct |
| `v_risk_truth` | `mtbf_days` | ✅ OK | 7 | direct |
| `v_risk_truth` | `risk_level` | ✅ OK | 10 | direct |
| `v_risk_truth` | `risk_score` | ✅ OK | 10 | direct |
| `v_risk_truth` | `top_factors` | ✅ OK | 8 | direct |
| `v_sensor_truth` | `asset_id` | ✅ OK | 1 | direct |
| `v_sensor_truth` | `is_anomaly` | ✅ OK | 2 | direct |
| `v_sensor_truth` | `parameter` | ✅ OK | 2 | direct |
| `v_sensor_truth` | `quality_flag` | ✅ OK | 2 | direct |
| `v_sensor_truth` | `recorded_at` | ✅ OK | 2 | direct |
| `v_sensor_truth` | `value` | ✅ OK | 1 | direct |
| `v_skill_badges_truth` | `badge_key` | ✅ OK | 1 | direct |
| `v_skill_badges_truth` | `discipline` | ✅ OK | 4 | direct |
| `v_skill_badges_truth` | `level` | ✅ OK | 4 | direct |
| `v_weibull_truth` | `asset_id` | ✅ OK | 1 | direct |
| `v_weibull_truth` | `beta` | ✅ OK | 3 | direct |
| `v_weibull_truth` | `eta_days` | ✅ OK | 3 | direct |
| `v_weibull_truth` | `failure_pattern` | ✅ OK | 3 | direct |
| `v_weibull_truth` | `generated_at` | ✅ OK | 2 | direct |
| `v_weibull_truth` | `log_likelihood` | ✅ OK | 1 | direct |
| `v_weibull_truth` | `n_censored` | ✅ OK | 2 | direct |
| `v_weibull_truth` | `n_failures` | ✅ OK | 2 | direct |
| `v_weibull_truth` | `source_window_days` | ✅ OK | 1 | direct |
| `v_worker_achievements_truth` | `achievement_id` | ✅ OK | 1 | direct |
| `v_worker_achievements_truth` | `current_level` | ✅ OK | 2 | direct |
| `v_worker_achievements_truth` | `last_action_at` | ✅ OK | 1 | direct |
| `v_worker_achievements_truth` | `worker_name` | ✅ OK | 2 | direct |
| `v_worker_achievements_truth` | `xp_total` | ✅ OK | 1 | direct |
| `v_worker_assignment_truth` | `capacity_signal` | ✅ OK | 1 | direct |
| `v_worker_assignment_truth` | `last_category` | ✅ OK | 1 | direct |
| `v_worker_assignment_truth` | `open_jobs` | ✅ OK | 1 | direct |
| `v_worker_assignment_truth` | `worker_name` | ✅ OK | 1 | direct |
| `v_worker_skill_truth` | `badge_count` | ✅ OK | 1 | direct |
| `v_worker_skill_truth` | `current_level` | ✅ OK | 3 | direct |
| `v_worker_skill_truth` | `discipline` | ✅ OK | 4 | direct |
| `v_worker_skill_truth` | `level` | ✅ OK | 1 | direct |
| `v_worker_skill_truth` | `primary_skill` | ✅ OK | 2 | direct |
| `v_worker_skill_truth` | `role` | ✅ OK | 2 | direct |
| `v_worker_skill_truth` | `worker_name` | ✅ OK | 3 | direct |
| `v_worker_truth` | `hive_status` | ✅ OK | 6 | direct |
| `v_worker_truth` | `preferred_persona` | ✅ OK | 2 | direct |
| `v_worker_truth` | `role` | ✅ OK | 4 | direct |
| `v_worker_truth` | `worker_name` | ✅ OK | 11 | direct |
