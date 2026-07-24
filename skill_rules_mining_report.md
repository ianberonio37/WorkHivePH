# Skill-Rule Mining Report (Layer -1.5)

Documented rules from `C:/Users/ILBeronio/.claude/skills/<skill>/SKILL.md` files,
mined against the codebase. Source manifest: `skill_rules_manifest.json`.

- Rules evaluated: **57**
- Critical / high-severity violations: **7**
- Promotion candidates (drift band): **16**
- Rules by source: skill_md:designer=2, skill_md:mobile-maestro=2, skill_md:security=3, manifest=50

## Per-skill roll-up

| Skill | Rules | Avg conformance | Total violators |
|---|---:|---:|---:|
| architect | 2 | 100% | 0 |
| data-engineer | 1 | 100% | 0 |
| designer | 7 | 78% | 35 |
| frontend | 20 | 91% | 53 |
| mobile-maestro | 7 | 83% | 6 |
| qa-tester | 6 | 96% | 9 |
| security | 14 | 95% | 7 |

## Critical / high-severity violations -- act immediately

### `qa_utils_js_loads_before_inline_script` (high)  -- qa-tester :: utils.js must load BEFORE the main script block
- **Rule:** Pages that call escHtml/getDb must load utils.js before the main inline <script> block
- **Conformance:** 91%  (34 / 37)
- **Violators (3):** architecture.html, symbol-gallery.html, validator-catalog.html
- **Why it matters:** If utils.js loads AFTER the inline script that calls escHtml/getDb, the call throws ReferenceError and silently kills the entire <script> block.

### `mobile_viewport_fit_cover` (high)  -- mobile-maestro :: viewport-fit=cover is required before safe areas work
- **Rule:** Every HTML page's viewport meta must include viewport-fit=cover
- **Conformance:** 95%  (40 / 42)
- **Violators (2):** promo-poster.html, validator-catalog.html
- **Why it matters:** env(safe-area-inset-*) returns 0 unless viewport-fit=cover is set -- iPhone notch + home indicator overlap content.

### `frontend_eschtml_imported_not_inline` (high)  -- frontend :: escHtml from utils.js
- **Rule:** Pages must use escHtml() (from utils.js) -- either direct call `escHtml(` or canonical alias `const e = escHtml` + e( calls
- **Conformance:** 94%  (35 / 37)
- **Violators (2):** platform-actions.html, status.html
- **Why it matters:** Any page that uses innerHTML to render user data must escape it. Two canonical idioms are accepted: direct escHtml() calls, or the `const e = escHtml` alias (memory rule -- shortens template literals in renderer functions).

### `mobile_decorative_anim_has_mobile_kill` (high)  -- mobile-maestro :: Auto-Mineable Rules
- **Rule:** Pages with DECORATIVE infinite CSS animations include a @media (max-width: 767px) animation:none kill
- **Conformance:** 88%  (8 / 9)
- **Violators (1):** voice-journal.html
- **Why it matters:** iOS WebKit kills tabs with too many simultaneous infinite animations -- 'A problem repeatedly occurred'. Only DECORATIVE animations need a mobile kill -- functional ones (skeleton loaders, spinners, blink/pulse status indicators, mic-pulse, dot-pulse) are whitelisted per the skill's explicit guidance. Trigger uses a negative lookahead to exclude the whitelist.

### `security_voice_transcript_length_cap` (high)  -- security :: Auto-Mineable Rules
- **Rule:** Edge fns passing user voice transcripts to AI must `.slice(0, N)` to prevent prompt injection
- **Conformance:** 50%  (1 / 2)
- **Violators (1):** ai-gateway
- **Why it matters:** An attacker speaking a long prompt could override the system prompt. Always cap before passing to callAI(). Reference: April 2026 Report Sender lessons.

### `mobile_toast_has_aria_live` (high)  -- mobile-maestro :: Toast containers need ARIA -- mobile screen readers depend on this
- **Rule:** Toast containers must have role="alert" aria-live="polite"
- **Conformance:** 96%  (29 / 30)
- **Violators (1):** platform-actions.html
- **Why it matters:** VoiceOver/TalkBack rely on aria-live for toast announcements. Without it, save confirmations are completely silent on mobile.

### `edge_fn_handles_options_preflight` (high)  -- security :: Edge Function CORS
- **Rule:** Every edge fn responds to OPTIONS preflight
- **Conformance:** 98%  (56 / 57)
- **Violators (1):** visual-defect-capture
- **Why it matters:** Without OPTIONS handling, browsers block the actual request on CORS preflight failure.

## Promotion candidates (documented rules with measurable drift)

| Rule | Skill | Severity | Conformance | Violators |
|---|---|---|---:|---|
| `qa_no_alert_call` | qa-tester | medium | 98% | index.html |
| `edge_fn_handles_options_preflight` | security | high | 98% | visual-defect-capture |
| `qa_no_innerhtml_plus_equals` | qa-tester | medium | 97% | design-system.html |
| `designer_poppins_font` | designer | info | 97% | validator-catalog.html |
| `mobile_toast_has_aria_live` | mobile-maestro | high | 96% | platform-actions.html |
| `frontend_list_view_has_error_state` | frontend | medium | 96% | status.html |
| `mobile_viewport_fit_cover` | mobile-maestro | high | 95% | promo-poster.html, validator-catalog.html |
| `frontend_no_em_dash_in_prompt_template` | frontend | medium | 94% | ai-gateway, analytics-orchestrator, voice-journal-agent |
| `frontend_eschtml_imported_not_inline` | frontend | high | 94% | platform-actions.html, status.html |
| `frontend_calm_dashboard_declares_source_chip` | frontend | medium | 92% | ph-intelligence.html |
| `frontend_list_view_has_loading_state` | frontend | medium | 92% | platform-actions.html, status.html |
| `migration_grant_when_rls_enabled` | security | medium | 92% | 20260620000007_rls_enable_project_family.sql, 20260620000008_rls_enable_remaining_hive_tables.sql, 20260707000001_marketplace_watchlist_savedsearch_rls.sql, 20260707000004_achievement_xp_log_rls.sql, 20260718000001_ops_artifact_metrics.sql |
| `qa_utils_js_loads_before_inline_script` | qa-tester | high | 91% | architecture.html, symbol-gallery.html, validator-catalog.html |
| `a11y_main_landmark_present` | qa-tester | medium | 90% | design-system.html, platform-actions.html, promo-poster.html, status.html |
| `mobile_decorative_anim_has_mobile_kill` | mobile-maestro | high | 88% | voice-journal.html |
| `frontend_list_view_has_empty_state` | frontend | medium | 83% | design-system.html, platform-actions.html, resume.html, status.html, validator-catalog.html |

## All rules (full conformance ranking)

| Rule | Skill | Conformance | Scope | Polarity |
|---|---|---:|---|---|
| `designer_btn_primary_canonical_gradient` | designer | 0% (0/15) | html_and_js | convention |
| `mobile_pdf_pagebreak_covers_p` | mobile-maestro | 0% (0/2) | html_pages | convention |
| `security_voice_transcript_length_cap` | security | 50% (1/2) | edge_fns | convention |
| `frontend_classlist_over_classname` | frontend | 52% (22/42) | html_pages | anti_pattern |
| `designer_uses_canonical_orange` | designer | 52% (21/40) | html_pages | convention |
| `frontend_no_innerhtml_in_foreach` | frontend | 59% (25/42) | html_pages | anti_pattern |
| `frontend_currency_uses_shared_formatter` | frontend | 66% (4/6) | html_pages | convention |
| `frontend_list_view_has_empty_state` | frontend | 83% (25/30) | html_pages | convention |
| `mobile_decorative_anim_has_mobile_kill` | mobile-maestro | 88% (8/9) | html_pages | convention |
| `a11y_main_landmark_present` | qa-tester | 90% (38/42) | html_pages | convention |
| `qa_utils_js_loads_before_inline_script` | qa-tester | 91% (34/37) | html_pages | convention |
| `migration_grant_when_rls_enabled` | security | 92% (60/65) | migrations | convention |
| `frontend_list_view_has_loading_state` | frontend | 92% (24/26) | html_pages | convention |
| `frontend_calm_dashboard_declares_source_chip` | frontend | 92% (12/13) | html_pages | convention |
| `frontend_eschtml_imported_not_inline` | frontend | 94% (35/37) | html_pages | convention |
| `frontend_no_em_dash_in_prompt_template` | frontend | 94% (54/57) | edge_fns | anti_pattern |
| `mobile_viewport_fit_cover` | mobile-maestro | 95% (40/42) | html_pages | convention |
| `frontend_list_view_has_error_state` | frontend | 96% (27/28) | html_pages | convention |
| `mobile_toast_has_aria_live` | mobile-maestro | 96% (29/30) | html_pages | convention |
| `designer_poppins_font` | designer | 97% (39/40) | html_pages | convention |
| `qa_no_innerhtml_plus_equals` | qa-tester | 97% (41/42) | html_pages | anti_pattern |
| `edge_fn_handles_options_preflight` | security | 98% (56/57) | edge_fns | convention |
| `qa_no_alert_call` | qa-tester | 98% (80/81) | html_and_js | anti_pattern |
| `designer_dialog_has_aria_modal_true` | designer | 100% (8/8) | html_pages | convention |
| `security_inventory_status_approved_scope` | security | 100% (1/1) | html_pages | convention |
| `security_inline_onclick_role_check_inside_fn` | security | 100% (3/3) | html_pages | convention |
| `security_no_inline_eschtml` | security | 100% (42/42) | html_pages | anti_pattern |
| `security_no_service_role_key_frontend` | security | 100% (81/81) | html_and_js | anti_pattern |
| `security_no_eval_user_input` | security | 100% (81/81) | html_and_js | anti_pattern |
| `security_no_stripe_secret_in_frontend` | security | 100% (81/81) | html_and_js | anti_pattern |
| `security_no_static_cors_origin_edge_fn` | security | 100% (57/57) | edge_fns | anti_pattern |
| `mobile_no_text_sm_on_wh_input` | mobile-maestro | 100% (42/42) | html_pages | anti_pattern |
| `mobile_no_avoid_all_in_pdf_pagebreak` | mobile-maestro | 100% (42/42) | html_pages | anti_pattern |
| `mobile_sw_cache_name_present` | mobile-maestro | 100% (0/0) | js_modules | convention |
| `designer_no_off_brand_orange_e8920a` | designer | 100% (81/81) | html_and_js | anti_pattern |
| `designer_no_wrong_input_bg_rgba_black` | designer | 100% (42/42) | html_pages | anti_pattern |
| `qa_supabase_cdn_when_createclient_used` | qa-tester | 100% (0/0) | html_pages | convention |
| `frontend_writeAuditLog_called` | frontend | 100% (2/2) | html_pages | convention |
| `edge_fn_uses_get_cors_headers` | security | 100% (57/57) | edge_fns | convention |
| `data_engineer_restore_identity_from_session` | data-engineer | 100% (1/1) | html_pages | convention |
| `migration_function_sets_search_path` | security | 100% (107/107) | migrations | convention |
| `security_no_function_constructor` | security | 100% (81/81) | html_and_js | anti_pattern |
| `security_no_token_in_localstorage` | security | 100% (81/81) | html_and_js | anti_pattern |
| `designer_card_radius_not_125rem` | designer | 100% (42/42) | html_pages | anti_pattern |
| `a11y_img_has_alt` | qa-tester | 100% (42/42) | html_pages | anti_pattern |
| `kg_voice_handler_must_call_platform_rpc` | architect | 100% (1/1) | js_modules | convention |
| `kg_migrations_no_broadcast_across_hives` | architect | 100% (366/366) | migrations | anti_pattern |
| `frontend_detail_toggle_uses_shared_helper` | frontend | 100% (17/17) | html_pages | convention |
| `frontend_list_view_has_no_results_state` | frontend | 100% (11/11) | html_pages | convention |
| `frontend_list_view_has_load_more` | frontend | 100% (12/12) | html_pages | convention |
| `frontend_filter_tabs_have_aria_roles` | frontend | 100% (6/6) | html_pages | convention |
| `frontend_calm_dashboard_has_verdict` | frontend | 100% (13/13) | html_pages | convention |
| `frontend_calm_dashboard_uses_details_disclosure` | frontend | 100% (13/13) | html_pages | convention |
| `frontend_phantom_capture_allow_has_reason` | frontend | 100% (42/42) | html_pages | anti_pattern |
| `frontend_kpi_page_no_local_truth_math` | frontend | 100% (26/26) | html_pages | anti_pattern |
| `frontend_calm_dashboard_filters_zero_kpis` | frontend | 100% (13/13) | html_pages | convention |
| `frontend_search_resets_pagination` | frontend | 100% (8/8) | html_pages | convention |

## Allowlisted suppressions (documented-legit divergences)

| Rule | File | Reason |
|---|---|---|
| `designer_uses_canonical_orange` | `analytics-report.html` | Intentional purple-themed analytics report builder (uses #a78bfa as the accent palette). The page is a PDF-export surface, not a normal hive-facing page; the purple framing visually separates report mode from operational mode. |
| `designer_uses_canonical_orange` | `architecture.html` | Intentional dark-themed technical architecture viewer (uses #1c2128 + neutral grays). Renders a static system diagram, not an operational surface; brand orange would distract from the architecture content. |
| `designer_poppins_font` | `architecture.html` | Technical architecture viewer. Uses system fonts (-apple-system, Segoe UI) + monospace for diagram labels. Brand font would clash with the technical-content framing. |
| `designer_poppins_font` | `symbol-gallery.html` | Static P&ID symbol library. Uses Segoe UI + mono for engineering-drawing context. Reference page, not operational. |
| `frontend_eschtml_imported_not_inline` | `architecture.html` | Static-content page: innerHTML only ever assigned literal strings from a frozen catalog (no user data flows through it). Confirmed 2026-05-19 by grep of innerHTML sites. |
| `frontend_eschtml_imported_not_inline` | `symbol-gallery.html` | Static-content page: renders a fixed P&ID symbol library; innerHTML carries no user input. Confirmed 2026-05-19 by grep of innerHTML sites. |
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
| `frontend_list_view_has_loading_state` | `agentic-rag-observability.html` | Internal AI-ops observability dashboard — RAG retrieval/flywheel telemetry for operators, not a customer-facing product list. Dev-tooling surface, not the List View Contract. |
| `frontend_list_view_has_loading_state` | `assistant.html` | Chat interface, not a list view; the streaming reply IS the loading affordance. |
| `frontend_list_view_has_loading_state` | `founder-console.html` | Internal founder/admin console (isPlatformAdmin-gated, noindex, same class as Ian's personal pages per the Phase-4 IA tier-split) — platform-ops surface, not a customer-facing product list. |
| `frontend_list_view_has_loading_state` | `index.html` | Marketing landing + operational-home dashboard; tiles render from a fixed set, governed by the Calm Dashboard Contract. |
| `frontend_list_view_has_loading_state` | `integrations.html` | Multi-step CSV import wizard; the .map() renders preview rows of in-progress data, not a fetched list. |
| `frontend_list_view_has_loading_state` | `marketplace-admin.html` | Platform-staff approval/KYB queue gated behind the marketplace_platform_admins role — internal moderation surface, not a customer-facing product list. |
| `frontend_list_view_has_loading_state` | `report-sender.html` | Report-builder form; the .map() renders recipient chips, not a fetched list. |
| `frontend_list_view_has_loading_state` | `validator-catalog.html` | Internal dev/observability dashboard — renders the validator catalog from a local platform_health.json into a dense data table for operators, not a customer-facing product list. Table-tbody surface where the div-based whListSkeleton doesn't fit; governed by dev-tooling conventions, not the user-facing List View Contract (cf. the E1 internal-dashboard exemption). |
| `frontend_list_view_has_error_state` | `agentic-rag-observability.html` | Internal AI-ops observability dashboard — RAG retrieval/flywheel telemetry for operators, not a customer-facing product list. Dev-tooling surface, not the List View Contract. |
| `frontend_list_view_has_error_state` | `assistant.html` | Chat interface, not a list view; reply errors surface inline in the conversation. |
| `frontend_list_view_has_error_state` | `index.html` | Marketing landing + operational-home dashboard; governed by the Calm Dashboard Contract. |
| `frontend_list_view_has_error_state` | `integrations.html` | Multi-step CSV import wizard; import errors surface in the wizard step, not a list. |
| `frontend_list_view_has_error_state` | `report-sender.html` | Report-builder form; send errors surface on the form, not a list. |
| `frontend_list_view_has_error_state` | `validator-catalog.html` | Internal dev/observability dashboard — renders the validator catalog from a local platform_health.json into a dense data table for operators, not a customer-facing product list; already logs a load failure to console + shows a 'not found' row. Dev-tooling surface, not the user-facing List View Contract (cf. the E1 internal-dashboard exemption). |
| `frontend_currency_uses_shared_formatter` | `engineering-design.html` | The only ₱ is the static input-unit label '₱/kWh' (electricity-tariff suffix on a number field) — a constant unit, not a runtime currency value. whFmtPeso would be the wrong tool here. |
| `frontend_currency_uses_shared_formatter` | `index.html` | Marketing landing + operational-home dashboard; the only ₱ are fixed prose constants (the '₱800K–₱2.4M' knowledge-loss copy), not dynamic peso values. Governed by the Calm Dashboard Contract. |
| `frontend_list_view_has_load_more` | `engineering-design.html` | Report list rarely exceeds 10-15 saved designs per worker; pagination is overkill. The page is a calculator surface, not a feed. |
| `frontend_list_view_has_load_more` | `founder-console.html` | Admin-only platform-wide tables; row counts are bounded by 'number of platform hives/users' (currently <100). Adding Load More now would gate behind a control that always shows everything anyway. Revisit when row counts exceed ~200. |
| `frontend_list_view_has_load_more` | `marketplace-seller-profile.html` | Single seller's full listing set; cap is naturally small (a seller with 50+ listings is rare). Already has filter-tab UI for parts/training/jobs. |

## How to extend

Add a new rule:

1. Open `skill_rules_manifest.json`
2. Append a rule object (id, skill, section, summary, scope, polarity, pattern, rationale, severity)
3. Re-run `python tools/mine_skill_rules.py`
