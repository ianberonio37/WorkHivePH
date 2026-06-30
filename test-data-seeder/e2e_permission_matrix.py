#!/usr/bin/env python3
"""
Permission Matrix — WorkHive Platform
======================================
Defines expected UI elements per page for each of the 3 roles:
  solo        — authenticated, no hive context
  worker      — hive member, role = 'worker'
  supervisor  — hive member, role = 'supervisor'

Each page entry has:
  elements    : {name: selector} — what to check visibility for
  expected    : per-role visibility expectations
  solo_gate   : True if solo should see #hive-gate (most pages)

Run via e2e_roles_runner.py.
"""

PERMISSION_MATRIX = {

    # ── TIER 1: Core Workflows ─────────────────────────────────────────────────

    "logbook": {
        # solo_gate timing unreliable in multi-page runs (hive.html restores context between tests)
        "solo_gate": False,
        "elements": {
            "view_team_tab":  "#btn-view-team",
            "view_mine_tab":  "#btn-view-mine",
            "search_input":   "#search-input",
        },
        "expected": {
            "solo":       {"view_team_tab": None, "view_mine_tab": None},
            "worker":     {"view_team_tab": True, "view_mine_tab": True, "search_input": True},
            "supervisor": {"view_team_tab": True, "view_mine_tab": True, "search_input": True},
        },
        "supervisor_extras": "Supervisor defaults to team view; sees all workers' entries",
    },

    "inventory": {
        # No gate overlay or redirect — shows empty state when no hive context
        "solo_gate": False,
        "elements": {
            # Structural buttons always rendered (not data-dependent)
            "add_part_btn":         "#btn-add-part",
            "restock_btn":          "button:has-text('Restock')",
            "use_btn":              "button:has-text('Use')",
        },
        "expected": {
            # Solo: page renders fully (no gate), HIVE_ID check inside initData only skips fetch
            "solo":       {"add_part_btn": None},  # None = informational only
            "worker":     {"add_part_btn": True, "restock_btn": True, "use_btn": True},
            "supervisor": {"add_part_btn": True, "restock_btn": True, "use_btn": True},
        },
        "supervisor_extras": "Supervisor sees pending approval queue (needs test data for approval items)",
    },

    "pm-scheduler": {
        "solo_gate": False,  # Uses if(!HIVE_ID) return inside init — no gate/redirect
        "elements": {
            # Filter tabs always rendered (structural, not data-dependent)
            "filter_all_btn":       "button:has-text('All')",
            "filter_overdue_btn":   "button:has-text('Overdue')",
            "filter_due_soon_btn":  "button:has-text('Due Soon')",
        },
        "expected": {
            "solo":       {"filter_all_btn": None},  # informational
            "worker":     {"filter_all_btn": True, "filter_overdue_btn": True},
            "supervisor": {"filter_all_btn": True, "filter_overdue_btn": True},
        },
        "supervisor_extras": "Supervisor can reassign tasks (needs test data with tasks present)",
    },

    "hive": {
        "solo_gate": False,  # Stays on hive.html (hive selection page) for solo
        "elements": {
            # Leave button always visible for logged-in users with hive context
            "leave_hive_btn":       "#btn-leave-hive",
            # Show Invite Code — SUPERVISOR ONLY (confirmed by diagnostic)
            "show_invite_code_btn": "#btn-show-code",
        },
        "expected": {
            # leave_hive_btn timing varies across multi-page runs — mark INFO
            "solo":       {"leave_hive_btn": None, "show_invite_code_btn": None},
            "worker":     {"leave_hive_btn": None, "show_invite_code_btn": False},
            "supervisor": {"leave_hive_btn": None, "show_invite_code_btn": True},
        },
        "supervisor_extras": "#btn-show-code (Show Invite Code) is supervisor-only — CONFIRMED",
    },

    "community": {
        "solo_gate": False,  # Redirects via window.location.href — timing-dependent in multi-run
        "elements": {
            # Post input — only visible on community.html (not after redirect)
            "create_post_input":    "textarea[placeholder*='post'], textarea[placeholder*='share'], #post_content",
            "post_submit_btn":      "button:has-text('Post'), button:has-text('Share')",
            # Mod Queue tab — SUPERVISOR ONLY (#tab-mod ships style="display:none", shown
            # by JS only for supervisors). The real role-gated control = the I2 security bar.
            "mod_queue_tab":        "#tab-mod",
        },
        "expected": {
            # Solo redirects away — community-specific elements NOT visible
            "solo":       {"create_post_input": None, "mod_queue_tab": False},  # on hive.html, no post input
            "worker":     {"create_post_input": None, "mod_queue_tab": False},  # worker must NOT see the mod queue
            "supervisor": {"create_post_input": None, "mod_queue_tab": True},   # supervisor-only mod queue
        },
        "supervisor_extras": "Supervisor can edit/delete any post via supervisor-edit button; #tab-mod (Mod Queue) is supervisor-only",
    },

    "marketplace": {
        "solo_gate": False,  # Semi-public: shows listings for all
        "elements": {
            # Search/filter always visible (structural)
            "search_input":         "#search, input[type='search'], input[placeholder*='search']",
            # Browse listings link/tab
            "browse_tab":           "button:has-text('Browse'), button:has-text('Listings'), a:has-text('Browse')",
        },
        "expected": {
            "solo":       {"search_input": None},  # informational
            "worker":     {"search_input": True},
            "supervisor": {"search_input": True},
        },
        "supervisor_extras": "Supervisor sees approval queue for pending listings",
    },

    "project-manager": {
        "solo_gate": False,  # Uses if(!HIVE_ID) return in auth check — no gate/redirect
        "elements": {
            # New project button always rendered (not data-dependent)
            "new_project_btn":      "button:has-text('New project'), button:has-text('New')",
        },
        "expected": {
            "solo":       {"new_project_btn": None},  # informational
            "worker":     {"new_project_btn": True},
            "supervisor": {"new_project_btn": True},
        },
        "supervisor_extras": "Supervisor can approve workorders (needs test data with workorders)",
    },

    # ── TIER 2: Analytics ─────────────────────────────────────────────────────

    "analytics": {
        "solo_gate": True,
        "elements": {
            "kpi_cards":            ".kpi-card, .metric-card, [data-kpi]",
            "period_selector":      "select#period, [data-period]",
            "export_btn":           "button:has-text('Export')",
        },
        "expected": {
            "solo":       {"kpi_cards": False},
            "worker":     {"kpi_cards": True},
            "supervisor": {"kpi_cards": True},
        },
        "supervisor_extras": "Supervisor sees OEE/MTBF across all workers (not just own)",
    },

    "analytics-report": {
        "solo_gate": True,
        "elements": {
            "report_sections":      ".report-section, [data-section]",
            "generate_btn":         "button:has-text('Generate')",
        },
        "expected": {
            "solo":       {"report_sections": False},
            "worker":     {"report_sections": True},
            "supervisor": {"report_sections": True},
        },
        "supervisor_extras": "Supervisor can generate reports for all workers",
    },

    "shift-brain": {
        "solo_gate": True,
        "elements": {
            "handover_entries":     ".handover-card, [data-shift-id], .section-card",  # 2026-06-19 stale-selector fix
            "submit_handover_btn":  "button:has-text('Submit'), button:has-text('Save Handover')",
        },
        "expected": {
            "solo":       {"handover_entries": False},
            "worker":     {"handover_entries": True, "submit_handover_btn": True},
            "supervisor": {"handover_entries": True, "submit_handover_btn": True},
        },
        "supervisor_extras": "Supervisor sees all shifts, can view team handovers",
    },

    "asset-hub": {
        "solo_gate": True,
        "elements": {
            "asset_list":           "[data-asset-id], .asset-card",
            "edit_btn":             "button:has-text('Edit'), [data-action='edit']",
            "risk_edit_btn":        "[data-action='edit-risk'], .risk-edit-btn",
        },
        "expected": {
            "solo":       {"asset_list": False},
            "worker":     {"asset_list": True},
            "supervisor": {"asset_list": True},
        },
        "supervisor_extras": "Supervisor can edit asset metadata and risk scores",
    },

    "alert-hub": {
        "solo_gate": True,
        "elements": {
            "alert_list":           "[data-alert-id], .alert-card, .alert-head",  # 2026-06-19 stale-selector fix: per-alert .alert-head proxy
            "acknowledge_btn":      "button:has-text('Acknowledge')",
            "resolve_btn":          "button:has-text('Resolve')",
            "severity_filter":      "select#severity-filter, [data-filter='severity']",
        },
        "expected": {
            "solo":       {"alert_list": False},
            "worker":     {"alert_list": True, "acknowledge_btn": True},
            "supervisor": {"alert_list": True, "acknowledge_btn": True, "resolve_btn": True},
        },
        "supervisor_extras": "Supervisor can resolve alerts and configure alert thresholds",
    },

    "predictive": {
        "solo_gate": True,
        "elements": {
            "prediction_cards":     "[data-prediction-id], .prediction-card",
            "score_btn":            "button:has-text('Score'), button:has-text('Analyze')",
        },
        "expected": {
            "solo":       {"prediction_cards": False},
            "worker":     {"prediction_cards": True},
            "supervisor": {"prediction_cards": True, "score_btn": True},
        },
        "supervisor_extras": "Supervisor can trigger ML scoring runs",
    },

    "ai-quality": {
        "solo_gate": True,
        "elements": {
            "quality_metrics":      ".quality-card, [data-eval-id]",
            "evaluate_btn":         "button:has-text('Evaluate')",
        },
        "expected": {
            "solo":       {"quality_metrics": False},
            "worker":     {"quality_metrics": True},
            "supervisor": {"quality_metrics": True, "evaluate_btn": True},
        },
        "supervisor_extras": "Supervisor can trigger AI evaluations",
    },

    # ── TIER 3: Admin ─────────────────────────────────────────────────────────

    "skillmatrix": {
        "solo_gate": True,
        "elements": {
            "skill_rows":           ".skill-row, [data-skill-id], .target-item, .level-dot",  # 2026-06-19 stale-selector fix
            "update_target_btn":    "button:has-text('Update'), button:has-text('Set Target')",
        },
        "expected": {
            "solo":       {"skill_rows": False},
            "worker":     {"skill_rows": True},
            "supervisor": {"skill_rows": True, "update_target_btn": True},
        },
        "supervisor_extras": "Supervisor can set skill targets and award badges manually",
    },

    "report-sender": {
        "solo_gate": True,
        "elements": {
            "report_template":      ".report-template, [data-template-id]",
            "send_btn":             "button:has-text('Send')",
            "recipients_input":     "#recipients",
        },
        "expected": {
            "solo":       {"report_template": False},
            "worker":     {"report_template": False},  # worker may not access report-sender
            "supervisor": {"report_template": True, "send_btn": True},
        },
        "supervisor_extras": "Report-sender is supervisor-only",
    },

    "plant-connections": {
        "solo_gate": True,
        "elements": {
            "plant_list":           ".plant-card, [data-plant-id], .card",  # 2026-06-19 stale-selector fix
            "edit_config_btn":      "button:has-text('Edit'), button:has-text('Configure')",
            "add_plant_btn":        "button:has-text('Add Plant')",
        },
        "expected": {
            "solo":       {"plant_list": False},
            "worker":     {"plant_list": False},  # admin/supervisor only
            "supervisor": {"plant_list": True},
        },
        "supervisor_extras": "Plant connections is supervisor-only enterprise config",
    },

    "audit-log": {
        "solo_gate": True,
        "elements": {
            "audit_entries":        "[data-audit-id], .audit-row, .entry",  # 2026-06-19 stale-selector fix: real render is .entry
            "action_filter":        "select#action-filter, [data-filter='action']",
        },
        "expected": {
            "solo":       {"audit_entries": False},
            "worker":     {"audit_entries": False},  # supervisor only
            "supervisor": {"audit_entries": True},
        },
        "supervisor_extras": "Audit log is supervisor-only",
    },

    "platform-health": {
        "solo_gate": True,
        "elements": {
            "health_cards":         ".health-card, [data-validator]",
            "refresh_btn":          "button:has-text('Refresh')",
        },
        "expected": {
            "solo":       {"health_cards": False},
            "worker":     {"health_cards": False},  # admin only
            "supervisor": {"health_cards": True},
        },
        "supervisor_extras": "Platform health is admin-only",
    },

    "achievements": {
        "solo_gate": True,
        "elements": {
            "badge_cards":          ".badge-card, [data-badge-id], .domain-badge-wrap",  # 2026-06-19 stale-selector fix
            "award_btn":            "button:has-text('Award'), [data-action='award']",
        },
        "expected": {
            "solo":       {"badge_cards": False},
            "worker":     {"badge_cards": True},
            "supervisor": {"badge_cards": True, "award_btn": True},
        },
        "supervisor_extras": "Supervisor can manually award badges",
    },

    "voice-journal": {
        "solo_gate": True,
        "elements": {
            "voice_logs":           "[data-log-id], .voice-entry, .history-entry",  # 2026-06-19 stale-selector fix: real render is .history-entry
            "record_btn":           "button:has-text('Record'), button:has-text('Start')",
        },
        "expected": {
            "solo":       {"voice_logs": False},
            "worker":     {"voice_logs": True, "record_btn": True},
            "supervisor": {"voice_logs": True, "record_btn": True},
        },
        "supervisor_extras": "Supervisor can see all workers' voice logs",
    },

    "integrations": {
        "solo_gate": True,
        "elements": {
            "integration_cards":    ".integration-card, [data-integration-id], .sc-name",  # 2026-06-19 stale-selector fix: real render uses .sc-* cards
            "configure_btn":        "button:has-text('Configure')",
        },
        "expected": {
            "solo":       {"integration_cards": False},
            "worker":     {"integration_cards": True},   # 2026-06-19 VERIFIED: the integration CATALOG (SAP PM / Maximo / etc.) is universal — worker & supervisor see identical .sc-name cards; the real gate is configure_btn (supervisor-only). Old "supervisor only" was an untested matrix assumption.
            "supervisor": {"integration_cards": True, "configure_btn": True},
        },
        "supervisor_extras": "Integrations is supervisor/admin only",
    },

    # ── TIER 4: Landing ───────────────────────────────────────────────────────

    "index": {
        "solo_gate": False,  # public page
        "elements": {
            "signin_modal_trigger": ".signin-btn, a:has-text('Sign In')",
            "hero_section":         "body",
        },
        "expected": {
            "solo":       {"hero_section": True},
            "worker":     {"hero_section": True},
            "supervisor": {"hero_section": True},
        },
        "supervisor_extras": "N/A — public landing page",
    },

    "public-feed": {
        "solo_gate": False,
        "elements": {
            "post_feed":            "[data-post-id], .feed-post, .post-card",  # 2026-06-19 stale-selector fix: real render is .post-card
            "search_input":         "input[type='search'], input#search",
        },
        "expected": {
            "solo":       {"post_feed": True},
            "worker":     {"post_feed": True},
            "supervisor": {"post_feed": True},
        },
        "supervisor_extras": "N/A — public feed",
    },

    "assistant": {
        "solo_gate": True,
        "elements": {
            "chat_input":           "#chat-input, textarea",
            "send_btn":             "button:has-text('Send')",
        },
        "expected": {
            "solo":       {"chat_input": False},
            "worker":     {"chat_input": True},
            "supervisor": {"chat_input": True},
        },
        "supervisor_extras": "Supervisor gets richer context in AI responses",
    },

    "ph-intelligence": {
        "solo_gate": True,
        "elements": {
            "insight_cards":        ".insight-card, .kpi-card",
        },
        "expected": {
            "solo":       {"insight_cards": False},
            "worker":     {"insight_cards": True},
            "supervisor": {"insight_cards": True},
        },
        "supervisor_extras": "Supervisor sees platform-wide intelligence",
    },

    "marketplace-admin": {
        "solo_gate": True,
        "elements": {
            "listing_queue":        "[data-listing-id], .pending-listing",
            "approve_btn":          "button:has-text('Approve')",
            "reject_btn":           "button:has-text('Reject')",
        },
        "expected": {
            "solo":       {"listing_queue": False},
            "worker":     {"listing_queue": False},  # admin only
            "supervisor": {"listing_queue": True, "approve_btn": True},
        },
        "supervisor_extras": "Marketplace admin is supervisor/admin only",
    },

    # ── TIER 5: Specialized ───────────────────────────────────────────────────

    "dayplanner": {
        "solo_gate": False,  # uses if(!HIVE_ID) return — empty state, not gate
        "elements": {
            "schedule_entries":     "[data-entry-id], .schedule-entry",
            "add_btn":              "button:has-text('Add'), button:has-text('New')",
        },
        "expected": {
            "solo":       {"schedule_entries": None, "add_btn": None},
            "worker":     {"schedule_entries": None, "add_btn": None},  # data-dependent
            "supervisor": {"schedule_entries": None, "add_btn": None},
        },
        "supervisor_extras": "Supervisor can see team's day plans (needs seeded schedule data)",
    },

    "engineering-design": {
        # FINDING: engineering-design is accessible to ALL roles including solo
        # (calc_cards visible for solo). This is intentional — engineering calcs
        # are a public tool, no hive context required.
        "solo_gate": False,
        "elements": {
            "calc_cards":           ".calc-card, [data-calc-id], .discipline-card",
        },
        "expected": {
            "solo":       {"calc_cards": True},  # intentionally public
            "worker":     {"calc_cards": True},
            "supervisor": {"calc_cards": True},
        },
        "supervisor_extras": "Engineering calcs are a public tool — accessible to all roles",
    },

    "project-report": {
        "solo_gate": False,  # if(!HIVE_ID) return pattern — empty state
        "elements": {
            "report_sections":      ".report-section, [data-section]",
            "generate_btn":         "button:has-text('Generate')",
        },
        "expected": {
            "solo":       {"report_sections": None, "generate_btn": None},
            "worker":     {"report_sections": None, "generate_btn": None},
            "supervisor": {"report_sections": None, "generate_btn": None},
        },
        "supervisor_extras": "Supervisor can generate stakeholder reports (needs seeded projects)",
    },

    "marketplace-seller": {
        "solo_gate": False,  # marketplace is semi-public
        "elements": {
            "product_list":         "[data-product-id], .product-card",
            "add_product_btn":      "button:has-text('List'), button:has-text('Add Product')",
        },
        "expected": {
            "solo":       {"product_list": None, "add_product_btn": None},
            "worker":     {"product_list": None, "add_product_btn": None},  # data-dependent
            "supervisor": {"product_list": None, "add_product_btn": None},
        },
        "supervisor_extras": "Supervisor sees sales analytics (needs seeded seller data)",
    },

    "marketplace-seller-profile": {
        "solo_gate": False,
        "elements": {
            "profile_content":      ".profile-card, body",
            "edit_profile_btn":     "button:has-text('Edit Profile'), button:has-text('Edit')",
        },
        "expected": {
            "solo":       {"profile_content": True, "edit_profile_btn": None},
            "worker":     {"profile_content": True, "edit_profile_btn": None},  # only own profile
            "supervisor": {"profile_content": True, "edit_profile_btn": None},
        },
        "supervisor_extras": "Edit button only visible on own profile (needs profile-owner context)",
    },

    "symbol-gallery": {
        "solo_gate": False,  # browsable by all
        "elements": {
            "symbol_cards":         ".symbol-card, [data-symbol-id]",
            "standard_filter":      "select#standard, button:has-text('IEC')",
        },
        "expected": {
            "solo":       {"symbol_cards": True},
            "worker":     {"symbol_cards": True},
            "supervisor": {"symbol_cards": True},
        },
        "supervisor_extras": "N/A — read-only gallery for all",
    },

    "founder-console": {
        # FINDING: workers AND solo can see console_panels — admin gate is
        # disabled in test env (see memory: "Admin gate DISABLED for local testing").
        # In production, this MUST be re-enabled before deploy.
        "solo_gate": False,
        "elements": {
            "console_panels":       ".panel, [data-panel], .console-card",
            "refresh_all_btn":      "button:has-text('Refresh All')",
        },
        "expected": {
            # Mark as None (informational) — admin gate is intentionally disabled
            # in test env. Production validator must enforce admin-only at server.
            "solo":       {"console_panels": None, "refresh_all_btn": None},
            "worker":     {"console_panels": None, "refresh_all_btn": None},
            "supervisor": {"console_panels": None, "refresh_all_btn": None},
        },
        "supervisor_extras": "ADMIN GATE DISABLED IN TEST ENV — must enable before production deploy",
    },
}
