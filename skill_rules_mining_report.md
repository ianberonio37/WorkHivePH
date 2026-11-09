# Skill-Rule Mining Report (Layer -1.5)

Documented rules from `C:/Users/ILBeronio/.claude/skills/<skill>/SKILL.md` files,
mined against the codebase. Source manifest: `skill_rules_manifest.json`.

- Rules evaluated: **57**
- Critical / high-severity violations: **7**
- Promotion candidates (drift band): **17**
- Rules by source: skill_md:designer=2, skill_md:mobile-maestro=2, skill_md:security=3, manifest=50

## Per-skill roll-up

| Skill | Rules | Avg conformance | Total violators |
|---|---:|---:|---:|
| architect | 2 | 100% | 0 |
| data-engineer | 1 | 100% | 0 |
| designer | 7 | 78% | 31 |
| frontend | 20 | 88% | 60 |
| mobile-maestro | 7 | 77% | 8 |
| qa-tester | 6 | 99% | 2 |
| security | 14 | 95% | 17 |

## Critical / high-severity violations -- act immediately

### `mobile_decorative_anim_has_mobile_kill` (high)  -- mobile-maestro :: Auto-Mineable Rules
- **Rule:** Pages with DECORATIVE infinite CSS animations include a @media (max-width: 767px) animation:none kill
- **Conformance:** 50%  (4 / 8)
- **Violators (4):** analytics-report.html, assistant.html, logbook.html, voice-journal.html
- **Why it matters:** iOS WebKit kills tabs with too many simultaneous infinite animations -- 'A problem repeatedly occurred'. Only DECORATIVE animations need a mobile kill -- functional ones (skeleton loaders, spinners, blink/pulse status indicators, mic-pulse, dot-pulse) are whitelisted per the skill's explicit guidance. Trigger uses a negative lookahead to exclude the whitelist.

### `security_voice_transcript_length_cap` (high)  -- security :: Auto-Mineable Rules
- **Rule:** Edge fns passing user voice transcripts to AI must `.slice(0, N)` to prevent prompt injection
- **Conformance:** 50%  (1 / 2)
- **Violators (1):** ai-gateway
- **Why it matters:** An attacker speaking a long prompt could override the system prompt. Always cap before passing to callAI(). Reference: April 2026 Report Sender lessons.

### `mobile_viewport_fit_cover` (high)  -- mobile-maestro :: viewport-fit=cover is required before safe areas work
- **Rule:** Every HTML page's viewport meta must include viewport-fit=cover
- **Conformance:** 97%  (37 / 38)
- **Violators (1):** promo-poster.html
- **Why it matters:** env(safe-area-inset-*) returns 0 unless viewport-fit=cover is set -- iPhone notch + home indicator overlap content.

### `mobile_toast_has_aria_live` (high)  -- mobile-maestro :: Toast containers need ARIA -- mobile screen readers depend on this
- **Rule:** Toast containers must have role="alert" aria-live="polite"
- **Conformance:** 96%  (29 / 30)
- **Violators (1):** platform-actions.html
- **Why it matters:** VoiceOver/TalkBack rely on aria-live for toast announcements. Without it, save confirmations are completely silent on mobile.

### `frontend_eschtml_imported_not_inline` (high)  -- frontend :: escHtml from utils.js
- **Rule:** Pages must use escHtml() (from utils.js) -- either direct call `escHtml(` or canonical alias `const e = escHtml` + e( calls
- **Conformance:** 97%  (34 / 35)
- **Violators (1):** status.html
- **Why it matters:** Any page that uses innerHTML to render user data must escape it. Two canonical idioms are accepted: direct escHtml() calls, or the `const e = escHtml` alias (memory rule -- shortens template literals in renderer functions).

### `edge_fn_handles_options_preflight` (high)  -- security :: Edge Function CORS
- **Rule:** Every edge fn responds to OPTIONS preflight
- **Conformance:** 98%  (61 / 62)
- **Violators (1):** vehicle-doc-extract
- **Why it matters:** Without OPTIONS handling, browsers block the actual request on CORS preflight failure.

### `frontend_filter_tabs_have_aria_roles` (high)  -- frontend :: List View Contract -- Filter Tabs A11y Roles
- **Rule:** Filter tabs and chip rows must declare role="tablist" on the container and role="tab" + aria-selected on each button
- **Conformance:** 83%  (5 / 6)
- **Violators (1):** alert-hub.html
- **Why it matters:** Canonical from marketplace.html:589 (section-tabs) and audit-log.html:188 (filter-row + chip + aria-selected). Screen readers cannot navigate tab UIs without tablist/tab role + aria-selected. A visual tab without these roles is a keyboard-trap regression. Identified 2026-05-19 during list-display uniformity audit.

## Promotion candidates (documented rules with measurable drift)

| Rule | Skill | Severity | Conformance | Violators |
|---|---|---|---:|---|
| `migration_function_sets_search_path` | security | medium | 99% | 20260805000051_an_anonymous_visitor_could_run_the_nightly_sweep.sql, 20260806000058_anchor_the_reaction_xp_award_ledger.sql |
| `edge_fn_handles_options_preflight` | security | high | 98% | vehicle-doc-extract |
| `mobile_viewport_fit_cover` | mobile-maestro | high | 97% | promo-poster.html |
| `qa_no_innerhtml_plus_equals` | qa-tester | medium | 97% | llm-observability.html |
| `a11y_main_landmark_present` | qa-tester | medium | 97% | promo-poster.html |
| `frontend_eschtml_imported_not_inline` | frontend | high | 97% | status.html |
| `mobile_toast_has_aria_live` | mobile-maestro | high | 96% | platform-actions.html |
| `frontend_list_view_has_error_state` | frontend | medium | 96% | status.html |
| `frontend_no_em_dash_in_prompt_template` | frontend | medium | 95% | ai-gateway, analytics-orchestrator, voice-journal-agent |
| `frontend_list_view_has_load_more` | frontend | medium | 92% | platform-actions.html |
| `frontend_list_view_has_no_results_state` | frontend | medium | 91% | platform-actions.html |
| `frontend_calm_dashboard_declares_source_chip` | frontend | medium | 91% | ph-intelligence.html |
| `frontend_list_view_has_loading_state` | frontend | medium | 91% | platform-actions.html, status.html |
| `frontend_list_view_has_empty_state` | frontend | medium | 88% | platform-actions.html, resume.html, status.html |
| `frontend_search_resets_pagination` | frontend | medium | 87% | audit-log.html |
| `frontend_filter_tabs_have_aria_roles` | frontend | high | 83% | alert-hub.html |
| `designer_dialog_has_aria_modal_true` | designer | medium | 81% | audit-log.html, integrations.html |

## All rules (full conformance ranking)

| Rule | Skill | Conformance | Scope | Polarity |
|---|---|---:|---|---|
| `designer_btn_primary_canonical_gradient` | designer | 0% (0/16) | html_and_js | convention |
| `mobile_pdf_pagebreak_covers_p` | mobile-maestro | 0% (0/2) | html_pages | convention |
| `frontend_classlist_over_classname` | frontend | 31% (12/38) | html_pages | anti_pattern |
| `mobile_decorative_anim_has_mobile_kill` | mobile-maestro | 50% (4/8) | html_pages | convention |
| `security_voice_transcript_length_cap` | security | 50% (1/2) | edge_fns | convention |
| `frontend_no_innerhtml_in_foreach` | frontend | 57% (22/38) | html_pages | anti_pattern |
| `frontend_currency_uses_shared_formatter` | frontend | 62% (5/8) | html_pages | convention |
| `designer_uses_canonical_orange` | designer | 64% (24/37) | html_pages | convention |
| `designer_dialog_has_aria_modal_true` | designer | 81% (9/11) | html_pages | convention |
| `frontend_filter_tabs_have_aria_roles` | frontend | 83% (5/6) | html_pages | convention |
| `migration_grant_when_rls_enabled` | security | 84% (72/85) | migrations | convention |
| `frontend_search_resets_pagination` | frontend | 87% (7/8) | html_pages | convention |
| `frontend_list_view_has_empty_state` | frontend | 88% (24/27) | html_pages | convention |
| `frontend_list_view_has_loading_state` | frontend | 91% (22/24) | html_pages | convention |
| `frontend_list_view_has_no_results_state` | frontend | 91% (11/12) | html_pages | convention |
| `frontend_calm_dashboard_declares_source_chip` | frontend | 91% (11/12) | html_pages | convention |
| `frontend_list_view_has_load_more` | frontend | 92% (12/13) | html_pages | convention |
| `frontend_no_em_dash_in_prompt_template` | frontend | 95% (59/62) | edge_fns | anti_pattern |
| `frontend_list_view_has_error_state` | frontend | 96% (25/26) | html_pages | convention |
| `mobile_toast_has_aria_live` | mobile-maestro | 96% (29/30) | html_pages | convention |
| `frontend_eschtml_imported_not_inline` | frontend | 97% (34/35) | html_pages | convention |
| `mobile_viewport_fit_cover` | mobile-maestro | 97% (37/38) | html_pages | convention |
| `qa_no_innerhtml_plus_equals` | qa-tester | 97% (37/38) | html_pages | anti_pattern |
| `a11y_main_landmark_present` | qa-tester | 97% (37/38) | html_pages | convention |
| `edge_fn_handles_options_preflight` | security | 98% (61/62) | edge_fns | convention |
| `migration_function_sets_search_path` | security | 99% (325/327) | migrations | convention |
| `security_inventory_status_approved_scope` | security | 100% (1/1) | html_pages | convention |
| `security_inline_onclick_role_check_inside_fn` | security | 100% (4/4) | html_pages | convention |
| `security_no_inline_eschtml` | security | 100% (38/38) | html_pages | anti_pattern |
| `security_no_service_role_key_frontend` | security | 100% (87/87) | html_and_js | anti_pattern |
| `security_no_eval_user_input` | security | 100% (87/87) | html_and_js | anti_pattern |
| `security_no_stripe_secret_in_frontend` | security | 100% (87/87) | html_and_js | anti_pattern |
| `security_no_static_cors_origin_edge_fn` | security | 100% (62/62) | edge_fns | anti_pattern |
| `mobile_no_text_sm_on_wh_input` | mobile-maestro | 100% (38/38) | html_pages | anti_pattern |
| `mobile_no_avoid_all_in_pdf_pagebreak` | mobile-maestro | 100% (38/38) | html_pages | anti_pattern |
| `mobile_sw_cache_name_present` | mobile-maestro | 100% (0/0) | js_modules | convention |
| `designer_no_off_brand_orange_e8920a` | designer | 100% (87/87) | html_and_js | anti_pattern |
| `designer_no_wrong_input_bg_rgba_black` | designer | 100% (38/38) | html_pages | anti_pattern |
| `designer_poppins_font` | designer | 100% (38/38) | html_pages | convention |
| `qa_supabase_cdn_when_createclient_used` | qa-tester | 100% (0/0) | html_pages | convention |
| `qa_no_alert_call` | qa-tester | 100% (87/87) | html_and_js | anti_pattern |
| `frontend_writeAuditLog_called` | frontend | 100% (3/3) | html_pages | convention |
| `edge_fn_uses_get_cors_headers` | security | 100% (62/62) | edge_fns | convention |
| `data_engineer_restore_identity_from_session` | data-engineer | 100% (3/3) | html_pages | convention |
| `security_no_function_constructor` | security | 100% (87/87) | html_and_js | anti_pattern |
| `security_no_token_in_localstorage` | security | 100% (87/87) | html_and_js | anti_pattern |
| `designer_card_radius_not_125rem` | designer | 100% (38/38) | html_pages | anti_pattern |
| `a11y_img_has_alt` | qa-tester | 100% (38/38) | html_pages | anti_pattern |
| `qa_utils_js_loads_before_inline_script` | qa-tester | 100% (34/34) | html_pages | convention |
| `kg_voice_handler_must_call_platform_rpc` | architect | 100% (0/0) | js_modules | convention |
| `kg_migrations_no_broadcast_across_hives` | architect | 100% (772/772) | migrations | anti_pattern |
| `frontend_detail_toggle_uses_shared_helper` | frontend | 100% (17/17) | html_pages | convention |
| `frontend_calm_dashboard_has_verdict` | frontend | 100% (13/13) | html_pages | convention |
| `frontend_calm_dashboard_uses_details_disclosure` | frontend | 100% (13/13) | html_pages | convention |
| `frontend_phantom_capture_allow_has_reason` | frontend | 100% (38/38) | html_pages | anti_pattern |
| `frontend_kpi_page_no_local_truth_math` | frontend | 100% (28/28) | html_pages | anti_pattern |
| `frontend_calm_dashboard_filters_zero_kpis` | frontend | 100% (13/13) | html_pages | convention |

## Allowlisted suppressions (documented-legit divergences)

| Rule | File | Reason |
|---|---|---|
| `designer_uses_canonical_orange` | `analytics-report.html` | Intentional purple-themed analytics report builder (uses #a78bfa as the accent palette). The page is a PDF-export surface, not a normal hive-facing page; the purple framing visually separates report mode from operational mode. |
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
| `frontend_list_view_has_error_state` | `agentic-rag-observability.html` | Internal AI-ops observability dashboard — RAG retrieval/flywheel telemetry for operators, not a customer-facing product list. Dev-tooling surface, not the List View Contract. |
| `frontend_list_view_has_error_state` | `assistant.html` | Chat interface, not a list view; reply errors surface inline in the conversation. |
| `frontend_list_view_has_error_state` | `index.html` | Marketing landing + operational-home dashboard; governed by the Calm Dashboard Contract. |
| `frontend_list_view_has_error_state` | `integrations.html` | Multi-step CSV import wizard; import errors surface in the wizard step, not a list. |
| `frontend_list_view_has_error_state` | `report-sender.html` | Report-builder form; send errors surface on the form, not a list. |
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
