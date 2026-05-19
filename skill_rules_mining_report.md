# Skill-Rule Mining Report (Layer -1.5)

Documented rules from `C:/Users/ILBeronio/.claude/skills/<skill>/SKILL.md` files,
mined against the codebase. Source manifest: `skill_rules_manifest.json`.

- Rules evaluated: **47**
- Critical / high-severity violations: **6**
- Promotion candidates (drift band): **11**
- Rules by source: skill_md:designer=2, skill_md:mobile-maestro=2, skill_md:security=3, manifest=40

## Per-skill roll-up

| Skill | Rules | Avg conformance | Total violators |
|---|---:|---:|---:|
| architect | 2 | 100% | 0 |
| data-engineer | 1 | 90% | 3 |
| designer | 7 | 83% | 25 |
| frontend | 10 | 62% | 99 |
| mobile-maestro | 7 | 85% | 1 |
| qa-tester | 6 | 98% | 4 |
| security | 14 | 91% | 16 |

## Critical / high-severity violations -- act immediately

### `data_engineer_restore_identity_from_session` (high)  -- data-engineer :: Auth identity restoration
- **Rule:** Pages reading localStorage worker_name must also call restoreIdentityFromSession(db) to sync with Supabase Auth
- **Conformance:** 90%  (27 / 30)
- **Violators (3):** analytics-report.html, assistant.html, index.html
- **Why it matters:** Identity migration (C1-C4) replaced string localStorage with Supabase Auth sessions. Any page still reading the localStorage worker_name must call restoreIdentityFromSession(db) on load or it diverges from the canonical auth.uid() identity. Surfaced by AI extraction 2026-05-18, manually reviewed.

### `frontend_eschtml_imported_not_inline` (high)  -- frontend :: escHtml from utils.js
- **Rule:** Pages must use escHtml() (from utils.js) -- either direct call `escHtml(` or canonical alias `const e = escHtml` + e( calls
- **Conformance:** 94%  (33 / 35)
- **Violators (2):** architecture.html, symbol-gallery.html
- **Why it matters:** Any page that uses innerHTML to render user data must escape it. Two canonical idioms are accepted: direct escHtml() calls, or the `const e = escHtml` alias (memory rule -- shortens template literals in renderer functions).

### `frontend_filter_tabs_have_aria_roles` (high)  -- frontend :: List View Contract -- Filter Tabs A11y Roles
- **Rule:** Filter tabs and chip rows must declare role="tablist" on the container and role="tab" + aria-selected on each button
- **Conformance:** 66%  (4 / 6)
- **Violators (2):** marketplace-seller-profile.html, project-manager.html
- **Why it matters:** Canonical from marketplace.html:589 (section-tabs) and audit-log.html:188 (filter-row + chip + aria-selected). Screen readers cannot navigate tab UIs without tablist/tab role + aria-selected. A visual tab without these roles is a keyboard-trap regression. Identified 2026-05-19 during list-display uniformity audit.

### `security_inventory_status_approved_scope` (high)  -- security :: Auto-Mineable Rules
- **Rule:** inventory_items queries that render in worker UI must include `.eq('status', 'approved')`
- **Conformance:** 66%  (2 / 3)
- **Violators (1):** integrations.html
- **Why it matters:** Worker-facing inventory queries must hide unapproved rows -- omitting this bypasses the supervisor approval gate at the data-exposure level. See `validate_security` rule.

### `security_voice_transcript_length_cap` (high)  -- security :: Auto-Mineable Rules
- **Rule:** Edge fns passing user voice transcripts to AI must `.slice(0, N)` to prevent prompt injection
- **Conformance:** 50%  (1 / 2)
- **Violators (1):** project-orchestrator
- **Why it matters:** An attacker speaking a long prompt could override the system prompt. Always cap before passing to callAI(). Reference: April 2026 Report Sender lessons.

### `edge_fn_uses_get_cors_headers` (high)  -- security :: Edge Function CORS
- **Rule:** Every edge fn imports getCorsHeaders from _shared/cors.ts
- **Conformance:** 98%  (49 / 50)
- **Violators (1):** marketplace-webhook
- **Why it matters:** Static CORS origin is always wrong; the dynamic helper handles file:// (null origin) for local testing.

## Promotion candidates (documented rules with measurable drift)

| Rule | Skill | Severity | Conformance | Violators |
|---|---|---|---:|---|
| `edge_fn_uses_get_cors_headers` | security | high | 98% | marketplace-webhook |
| `designer_uses_canonical_orange` | designer | info | 94% | analytics-report.html, architecture.html |
| `frontend_eschtml_imported_not_inline` | frontend | high | 94% | architecture.html, symbol-gallery.html |
| `frontend_no_em_dash_in_prompt_template` | frontend | medium | 94% | analytics-orchestrator, project-orchestrator, voice-logbook-entry |
| `qa_no_alert_call` | qa-tester | medium | 93% | analytics-report.html, audit-log.html, index.html, project-report.html |
| `data_engineer_restore_identity_from_session` | data-engineer | high | 90% | analytics-report.html, assistant.html, index.html |
| `migration_grant_when_rls_enabled` | security | medium | 88% | 20260430000000_community_tables.sql, 20260516000001_agent_memory_phase2.sql, 20260516000002_dialog_state_phase4.sql, 20260516000003_anomaly_alerts_phase5.sql, 20260516000005_offline_resilience_phase6.sql |
| `designer_btn_primary_canonical_gradient` | designer | low | 85% | pm-scheduler.html, shift-brain.html |
| `designer_poppins_font` | designer | info | 80% | alert-hub.html, architecture.html, audit-log.html, parts-tracker.html, platform-health.html ... |
| `migration_function_sets_search_path` | security | medium | 77% | 20260420000000_baseline.sql, 20260430000002_community_xp.sql, 20260501000001_fix_auth_uid_backfill.sql, 20260501000003_missing_table_rls.sql, 20260501000004_remaining_table_rls.sql ... |
| `designer_card_radius_not_125rem` | designer | low | 72% | achievements.html, asset-hub.html, dayplanner.html, marketplace-seller-profile.html, marketplace-seller.html ... |

## All rules (full conformance ranking)

| Rule | Skill | Conformance | Scope | Polarity |
|---|---|---:|---|---|
| `mobile_pdf_pagebreak_covers_p` | mobile-maestro | 0% (0/1) | html_pages | convention |
| `frontend_list_view_has_no_results_state` | frontend | 18% (2/11) | html_pages | convention |
| `frontend_list_view_has_load_more` | frontend | 19% (6/31) | html_pages | convention |
| `frontend_list_view_has_empty_state` | frontend | 28% (9/31) | html_pages | convention |
| `frontend_classlist_over_classname` | frontend | 44% (16/36) | html_pages | anti_pattern |
| `designer_dialog_has_aria_modal_true` | designer | 50% (4/8) | html_pages | convention |
| `security_voice_transcript_length_cap` | security | 50% (1/2) | edge_fns | convention |
| `frontend_no_innerhtml_in_foreach` | frontend | 55% (20/36) | html_pages | anti_pattern |
| `security_inventory_status_approved_scope` | security | 66% (2/3) | html_pages | convention |
| `frontend_filter_tabs_have_aria_roles` | frontend | 66% (4/6) | html_pages | convention |
| `designer_card_radius_not_125rem` | designer | 72% (26/36) | html_pages | anti_pattern |
| `migration_function_sets_search_path` | security | 77% (28/36) | migrations | convention |
| `designer_poppins_font` | designer | 80% (29/36) | html_pages | convention |
| `designer_btn_primary_canonical_gradient` | designer | 85% (12/14) | html_and_js | convention |
| `migration_grant_when_rls_enabled` | security | 88% (40/45) | migrations | convention |
| `data_engineer_restore_identity_from_session` | data-engineer | 90% (27/30) | html_pages | convention |
| `qa_no_alert_call` | qa-tester | 93% (57/61) | html_and_js | anti_pattern |
| `frontend_no_em_dash_in_prompt_template` | frontend | 94% (47/50) | edge_fns | anti_pattern |
| `frontend_eschtml_imported_not_inline` | frontend | 94% (33/35) | html_pages | convention |
| `designer_uses_canonical_orange` | designer | 94% (34/36) | html_pages | convention |
| `edge_fn_uses_get_cors_headers` | security | 98% (49/50) | edge_fns | convention |
| `mobile_decorative_anim_has_mobile_kill` | mobile-maestro | 100% (8/8) | html_pages | convention |
| `security_inline_onclick_role_check_inside_fn` | security | 100% (3/3) | html_pages | convention |
| `security_no_inline_eschtml` | security | 100% (36/36) | html_pages | anti_pattern |
| `security_no_service_role_key_frontend` | security | 100% (61/61) | html_and_js | anti_pattern |
| `security_no_eval_user_input` | security | 100% (61/61) | html_and_js | anti_pattern |
| `security_no_stripe_secret_in_frontend` | security | 100% (61/61) | html_and_js | anti_pattern |
| `security_no_static_cors_origin_edge_fn` | security | 100% (50/50) | edge_fns | anti_pattern |
| `mobile_viewport_fit_cover` | mobile-maestro | 100% (36/36) | html_pages | convention |
| `mobile_no_text_sm_on_wh_input` | mobile-maestro | 100% (36/36) | html_pages | anti_pattern |
| `mobile_no_avoid_all_in_pdf_pagebreak` | mobile-maestro | 100% (36/36) | html_pages | anti_pattern |
| `mobile_toast_has_aria_live` | mobile-maestro | 100% (19/19) | html_pages | convention |
| `mobile_sw_cache_name_present` | mobile-maestro | 100% (0/0) | js_modules | convention |
| `designer_no_off_brand_orange_e8920a` | designer | 100% (61/61) | html_and_js | anti_pattern |
| `designer_no_wrong_input_bg_rgba_black` | designer | 100% (36/36) | html_pages | anti_pattern |
| `qa_supabase_cdn_when_createclient_used` | qa-tester | 100% (32/32) | html_pages | convention |
| `qa_no_innerhtml_plus_equals` | qa-tester | 100% (36/36) | html_pages | anti_pattern |
| `frontend_writeAuditLog_called` | frontend | 100% (3/3) | html_pages | convention |
| `edge_fn_handles_options_preflight` | security | 100% (50/50) | edge_fns | convention |
| `security_no_function_constructor` | security | 100% (61/61) | html_and_js | anti_pattern |
| `security_no_token_in_localstorage` | security | 100% (61/61) | html_and_js | anti_pattern |
| `a11y_main_landmark_present` | qa-tester | 100% (36/36) | html_pages | convention |
| `a11y_img_has_alt` | qa-tester | 100% (36/36) | html_pages | anti_pattern |
| `qa_utils_js_loads_before_inline_script` | qa-tester | 100% (29/29) | html_pages | convention |
| `kg_voice_handler_must_call_platform_rpc` | architect | 100% (1/1) | js_modules | convention |
| `kg_migrations_no_broadcast_across_hives` | architect | 100% (151/151) | migrations | anti_pattern |
| `frontend_search_resets_pagination` | frontend | 100% (3/3) | html_pages | convention |

## How to extend

Add a new rule:

1. Open `skill_rules_manifest.json`
2. Append a rule object (id, skill, section, summary, scope, polarity, pattern, rationale, severity)
3. Re-run `python tools/mine_skill_rules.py`
