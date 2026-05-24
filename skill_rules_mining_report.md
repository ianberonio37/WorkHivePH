# Skill-Rule Mining Report (Layer -1.5)

Documented rules from `C:/Users/ILBeronio/.claude/skills/<skill>/SKILL.md` files,
mined against the codebase. Source manifest: `skill_rules_manifest.json`.

- Rules evaluated: **53**
- Critical / high-severity violations: **1**
- Promotion candidates (drift band): **7**
- Rules by source: skill_md:designer=2, skill_md:mobile-maestro=2, skill_md:security=3, manifest=46

## Per-skill roll-up

| Skill | Rules | Avg conformance | Total violators |
|---|---:|---:|---:|
| architect | 2 | 100% | 0 |
| data-engineer | 1 | 96% | 1 |
| designer | 7 | 92% | 4 |
| frontend | 16 | 91% | 43 |
| mobile-maestro | 7 | 85% | 1 |
| qa-tester | 6 | 99% | 1 |
| security | 14 | 100% | 0 |

## Critical / high-severity violations -- act immediately

### `data_engineer_restore_identity_from_session` (high)  -- data-engineer :: Auth identity restoration
- **Rule:** Pages reading localStorage worker_name must also call restoreIdentityFromSession(db) to sync with Supabase Auth
- **Conformance:** 96%  (30 / 31)
- **Violators (1):** agentic-rag-observability.html
- **Why it matters:** Identity migration (C1-C4) replaced string localStorage with Supabase Auth sessions. Any page still reading the localStorage worker_name must call restoreIdentityFromSession(db) on load or it diverges from the canonical auth.uid() identity. Surfaced by AI extraction 2026-05-18, manually reviewed.

## Promotion candidates (documented rules with measurable drift)

| Rule | Skill | Severity | Conformance | Violators |
|---|---|---|---:|---|
| `frontend_no_em_dash_in_prompt_template` | frontend | medium | 98% | analytics-orchestrator |
| `a11y_main_landmark_present` | qa-tester | medium | 97% | agentic-rag-observability.html |
| `data_engineer_restore_identity_from_session` | data-engineer | high | 96% | agentic-rag-observability.html |
| `frontend_calm_dashboard_has_verdict` | frontend | medium | 93% | agentic-rag-observability.html |
| `frontend_calm_dashboard_uses_details_disclosure` | frontend | medium | 93% | agentic-rag-observability.html |
| `frontend_calm_dashboard_filters_zero_kpis` | frontend | medium | 93% | agentic-rag-observability.html |
| `frontend_calm_dashboard_declares_source_chip` | frontend | medium | 80% | agentic-rag-observability.html, ph-intelligence.html, platform-health.html |

## All rules (full conformance ranking)

| Rule | Skill | Conformance | Scope | Polarity |
|---|---|---:|---|---|
| `mobile_pdf_pagebreak_covers_p` | mobile-maestro | 0% (0/1) | html_pages | convention |
| `frontend_classlist_over_classname` | frontend | 45% (17/37) | html_pages | anti_pattern |
| `designer_dialog_has_aria_modal_true` | designer | 50% (4/8) | html_pages | convention |
| `frontend_no_innerhtml_in_foreach` | frontend | 56% (21/37) | html_pages | anti_pattern |
| `frontend_calm_dashboard_declares_source_chip` | frontend | 80% (12/15) | html_pages | convention |
| `frontend_calm_dashboard_has_verdict` | frontend | 93% (14/15) | html_pages | convention |
| `frontend_calm_dashboard_uses_details_disclosure` | frontend | 93% (14/15) | html_pages | convention |
| `frontend_calm_dashboard_filters_zero_kpis` | frontend | 93% (14/15) | html_pages | convention |
| `data_engineer_restore_identity_from_session` | data-engineer | 96% (30/31) | html_pages | convention |
| `a11y_main_landmark_present` | qa-tester | 97% (36/37) | html_pages | convention |
| `frontend_no_em_dash_in_prompt_template` | frontend | 98% (55/56) | edge_fns | anti_pattern |
| `designer_btn_primary_canonical_gradient` | designer | 100% (14/14) | html_and_js | convention |
| `mobile_decorative_anim_has_mobile_kill` | mobile-maestro | 100% (8/8) | html_pages | convention |
| `security_inventory_status_approved_scope` | security | 100% (1/1) | html_pages | convention |
| `security_voice_transcript_length_cap` | security | 100% (2/2) | edge_fns | convention |
| `security_inline_onclick_role_check_inside_fn` | security | 100% (3/3) | html_pages | convention |
| `security_no_inline_eschtml` | security | 100% (37/37) | html_pages | anti_pattern |
| `security_no_service_role_key_frontend` | security | 100% (62/62) | html_and_js | anti_pattern |
| `security_no_eval_user_input` | security | 100% (62/62) | html_and_js | anti_pattern |
| `security_no_stripe_secret_in_frontend` | security | 100% (62/62) | html_and_js | anti_pattern |
| `security_no_static_cors_origin_edge_fn` | security | 100% (56/56) | edge_fns | anti_pattern |
| `mobile_viewport_fit_cover` | mobile-maestro | 100% (37/37) | html_pages | convention |
| `mobile_no_text_sm_on_wh_input` | mobile-maestro | 100% (37/37) | html_pages | anti_pattern |
| `mobile_no_avoid_all_in_pdf_pagebreak` | mobile-maestro | 100% (37/37) | html_pages | anti_pattern |
| `mobile_toast_has_aria_live` | mobile-maestro | 100% (19/19) | html_pages | convention |
| `mobile_sw_cache_name_present` | mobile-maestro | 100% (0/0) | js_modules | convention |
| `designer_no_off_brand_orange_e8920a` | designer | 100% (62/62) | html_and_js | anti_pattern |
| `designer_no_wrong_input_bg_rgba_black` | designer | 100% (37/37) | html_pages | anti_pattern |
| `designer_uses_canonical_orange` | designer | 100% (35/35) | html_pages | convention |
| `designer_poppins_font` | designer | 100% (34/34) | html_pages | convention |
| `qa_supabase_cdn_when_createclient_used` | qa-tester | 100% (33/33) | html_pages | convention |
| `qa_no_innerhtml_plus_equals` | qa-tester | 100% (37/37) | html_pages | anti_pattern |
| `qa_no_alert_call` | qa-tester | 100% (62/62) | html_and_js | anti_pattern |
| `frontend_eschtml_imported_not_inline` | frontend | 100% (34/34) | html_pages | convention |
| `frontend_writeAuditLog_called` | frontend | 100% (3/3) | html_pages | convention |
| `edge_fn_uses_get_cors_headers` | security | 100% (55/55) | edge_fns | convention |
| `edge_fn_handles_options_preflight` | security | 100% (56/56) | edge_fns | convention |
| `migration_grant_when_rls_enabled` | security | 100% (46/46) | migrations | convention |
| `migration_function_sets_search_path` | security | 100% (30/30) | migrations | convention |
| `security_no_function_constructor` | security | 100% (62/62) | html_and_js | anti_pattern |
| `security_no_token_in_localstorage` | security | 100% (62/62) | html_and_js | anti_pattern |
| `designer_card_radius_not_125rem` | designer | 100% (37/37) | html_pages | anti_pattern |
| `a11y_img_has_alt` | qa-tester | 100% (37/37) | html_pages | anti_pattern |
| `qa_utils_js_loads_before_inline_script` | qa-tester | 100% (31/31) | html_pages | convention |
| `kg_voice_handler_must_call_platform_rpc` | architect | 100% (1/1) | js_modules | convention |
| `kg_migrations_no_broadcast_across_hives` | architect | 100% (187/187) | migrations | anti_pattern |
| `frontend_list_view_has_empty_state` | frontend | 100% (28/28) | html_pages | convention |
| `frontend_list_view_has_no_results_state` | frontend | 100% (11/11) | html_pages | convention |
| `frontend_list_view_has_load_more` | frontend | 100% (12/12) | html_pages | convention |
| `frontend_filter_tabs_have_aria_roles` | frontend | 100% (6/6) | html_pages | convention |
| `frontend_phantom_capture_allow_has_reason` | frontend | 100% (37/37) | html_pages | anti_pattern |
| `frontend_kpi_page_no_local_truth_math` | frontend | 100% (22/22) | html_pages | anti_pattern |
| `frontend_search_resets_pagination` | frontend | 100% (8/8) | html_pages | convention |

## Allowlisted suppressions (documented-legit divergences)

| Rule | File | Reason |
|---|---|---|
| `designer_uses_canonical_orange` | `analytics-report.html` | Intentional purple-themed analytics report builder (uses #a78bfa as the accent palette). The page is a PDF-export surface, not a normal hive-facing page; the purple framing visually separates report mode from operational mode. |
| `designer_uses_canonical_orange` | `architecture.html` | Intentional dark-themed technical architecture viewer (uses #1c2128 + neutral grays). Renders a static system diagram, not an operational surface; brand orange would distract from the architecture content. |
| `designer_poppins_font` | `architecture.html` | Technical architecture viewer. Uses system fonts (-apple-system, Segoe UI) + monospace for diagram labels. Brand font would clash with the technical-content framing. |
| `designer_poppins_font` | `platform-health.html` | Admin health dashboard. Intentional Segoe UI + Consolas mono for terminal-style readability of health checks and timestamps. |
| `designer_poppins_font` | `symbol-gallery.html` | Static P&ID symbol library. Uses Segoe UI + mono for engineering-drawing context. Reference page, not operational. |
| `frontend_eschtml_imported_not_inline` | `architecture.html` | Static-content page: innerHTML only ever assigned literal strings from a frozen catalog (no user data flows through it). Confirmed 2026-05-19 by grep of innerHTML sites. |
| `frontend_eschtml_imported_not_inline` | `symbol-gallery.html` | Static-content page: renders a fixed P&ID symbol library; innerHTML carries no user input. Confirmed 2026-05-19 by grep of innerHTML sites. |
| `edge_fn_uses_get_cors_headers` | `marketplace-webhook` | Stripe webhook receiver: Stripe servers do not send a browser Origin header and require a wildcard or absent ACAO. Using the dynamic helper would echo back a non-Stripe origin on misrouted traffic. Verified 2026-05-19 against the Stripe webhook signature flow. |
| `migration_grant_when_rls_enabled` | `20260430000000_community_tables.sql` | RLS enabled on community_posts / community_replies / community_reactions. GRANTs added in sibling 20260430000001_community_grants.sql (grep confirmed 2026-05-20). |
| `migration_grant_when_rls_enabled` | `20260516000001_agent_memory_phase2.sql` | RLS enabled on agent_memory. GRANTs added in earlier sibling 20260511000001_agent_memory.sql (grep confirmed 2026-05-20). |
| `migration_grant_when_rls_enabled` | `20260516000002_dialog_state_phase4.sql` | RLS enabled on dialog_state. GRANTs added in 20260519000020_security_hardening_pass.sql (grep confirmed 2026-05-20). |
| `migration_grant_when_rls_enabled` | `20260516000003_anomaly_alerts_phase5.sql` | RLS enabled on anomaly_alerts. GRANTs added in 20260519000020_security_hardening_pass.sql (grep confirmed 2026-05-20). |
| `migration_grant_when_rls_enabled` | `20260516000005_offline_resilience_phase6.sql` | RLS enabled on fallback_model_faq. GRANTs added in 20260519000020_security_hardening_pass.sql (grep confirmed 2026-05-20). |
| `migration_function_sets_search_path` | `20260420000000_baseline.sql` | Historical baseline. SECURITY DEFINER functions retroactively hardened via ALTER FUNCTION ... SET search_path in 20260519000020_security_hardening_pass.sql (e.g., search_skill_knowledge). Runtime DB reflects the hardened definition. |
| `migration_function_sets_search_path` | `20260430000002_community_xp.sql` | Community XP triggers. Hardened in 20260519000020_security_hardening_pass.sql. |
| `migration_function_sets_search_path` | `20260501000001_fix_auth_uid_backfill.sql` | auth_uid backfill helper. Hardened in 20260519000020_security_hardening_pass.sql. |
| `migration_function_sets_search_path` | `20260501000003_missing_table_rls.sql` | RLS-policy SECURITY DEFINER trigger functions. Hardened in 20260519000020_security_hardening_pass.sql. |
| `migration_function_sets_search_path` | `20260501000004_remaining_table_rls.sql` | Same hardening wave as 20260501000003. Hardened in 20260519000020_security_hardening_pass.sql. |
| `migration_function_sets_search_path` | `20260504000001_community_badge_auth_uid.sql` | Badge-grant trigger function. Hardened in 20260519000020_security_hardening_pass.sql. |
| `migration_function_sets_search_path` | `20260508000007_force_pgrst_reload.sql` | One-shot PostgREST reload trigger. SECURITY DEFINER scope is bounded to a single NOTIFY call; no malicious-schema attack surface. Hardened in 20260519000020_security_hardening_pass.sql for consistency. |
| `migration_function_sets_search_path` | `20260508000009_asset_brain_foundation.sql` | Asset Brain vector-search functions. Hardened in 20260519000020_security_hardening_pass.sql. |
| `frontend_list_view_has_empty_state` | `assistant.html` | Chat interface, not a list view. The .map() that triggers the rule renders chat-message rows incrementally; the conversation IS the content (an empty conversation = the welcome screen, which is already custom-designed). |
| `frontend_list_view_has_empty_state` | `index.html` | Marketing landing + operational-home dashboard. The .map() renders dashboard tiles from a fixed set; this is not a filterable list view. Calm Dashboard Contract already governs the page (see [[project-calm-dashboard-contract]]). |
| `frontend_list_view_has_empty_state` | `integrations.html` | Multi-step CSV import wizard with its own state (upload -> preview -> map -> import). The .map() renders preview rows of in-progress import data, not a queryable list. |
| `frontend_list_view_has_empty_state` | `report-sender.html` | Report-builder form, not a list view. The .map() renders recipient chips; the empty state is the form itself. |
| `frontend_list_view_has_load_more` | `engineering-design.html` | Report list rarely exceeds 10-15 saved designs per worker; pagination is overkill. The page is a calculator surface, not a feed. |
| `frontend_list_view_has_load_more` | `founder-console.html` | Admin-only platform-wide tables; row counts are bounded by 'number of platform hives/users' (currently <100). Adding Load More now would gate behind a control that always shows everything anyway. Revisit when row counts exceed ~200. |
| `frontend_list_view_has_load_more` | `marketplace-seller-profile.html` | Single seller's full listing set; cap is naturally small (a seller with 50+ listings is rare). Already has filter-tab UI for parts/training/jobs. |

## How to extend

Add a new rule:

1. Open `skill_rules_manifest.json`
2. Append a rule object (id, skill, section, summary, scope, polarity, pattern, rationale, severity)
3. Re-run `python tools/mine_skill_rules.py`
