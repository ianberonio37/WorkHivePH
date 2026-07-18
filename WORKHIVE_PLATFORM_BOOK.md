# WorkHive: The Platform and the Framework

A complete reference to the platform you have built (WorkHive) and the framework you build it with (WAT + Skill-First + Platform Guardian).

Version: 2026-05-09. Author: Ian Beronio. Generated from the live codebase, the Supabase schema, the validator registry, the WorkHive Tester, and the project's `CLAUDE.md` standing instructions.

---

## Table of Contents

**Part I. The Platform: WorkHive**
1. Vision and Positioning
2. The User Map: Field to Management
3. The Module Map
4. Anatomy of a Page
5. The Hive: Multi-Tenant Core
6. The Logbook
7. The PM Scheduler
8. The Inventory
9. The Skill Matrix
10. The Engineering Design Calculator
11. The Marketplace (Contact-Only Launch)
12. The Project Manager
13. CMMS Bridge and Integrations
14. Predictive Analytics and Risk Scoring
15. PH Industrial Intelligence
16. Achievements and Gamification
17. Community and Public Feed
18. Analytics, Reporting, and the Day Planner
19. The AI Assistant Layer
20. Tech Stack and Hosting

**Part II. The Framework: WAT, Skill-First, Guardian**
21. Why a Framework at All
22. WAT: Workflows, Agents, Tools
23. The Skill-First Rule
24. The Full Skill Roster
25. The Self-Improvement Loop
26. The Platform Guardian
27. The WorkHive Tester (Testing Battlefield)
28. The Validator Catalog
29. The Validation Workflow
30. The Commit and Deploy Workflow
31. Standing Rules of Engagement

**Part III. Operating the System**
32. Daily Loop
33. Building a New Feature End to End
34. Fixing a Bug End to End
35. What Goes Wrong and How to Recover
36. The Road Ahead

**Appendices**
- A. File and Folder Map
- B. Supabase Migrations Timeline
- C. Edge Function Catalog
- D. Validator Index (full list)
- E. Glossary

---

# Part I. The Platform: WorkHive

## 1. Vision and Positioning

WorkHive is a free industrial intelligence platform for Filipino workers at every level, from the technician on the plant floor to the supervisor on shift to the manager reading the morning report. The bet is simple: most plants in the Philippines run on paper logbooks, scattered spreadsheets, and tribal memory. The cost of that gap is not visible in any single shift; it shows up in shortened equipment life, missed PMs, lost spares, and skills that walk out the door when a senior tech retires.

WorkHive's promise is that you can walk into a small or mid-size plant on Day 1 and have a real digital logbook, PM checklist, inventory ledger, skill matrix, project manager, and AI work assistant working for you, with no procurement cycle, no IT project, no per-seat license. It is free at the worker tier because the value compounds only when the whole crew is on it.

The positioning rule, written into project memory, is explicit: WorkHive is for every worker, from field to management, not technicians only. Every UI choice, every tutorial, and every piece of marketing copy lives or dies by that rule.

The platform is bilingual at the level of vocabulary (Tagalog and English) and Filipino at the level of practice. The defaults assume Philippine norms: ISO 8528-1 generator sets, IEC 60617 single-line diagrams, NFPA 13 suppression layouts, ISA-5.1 P&IDs, IESNA lux levels for shop floor lighting, ASHRAE comfort bands tuned to local climate, and unit conventions familiar to a Filipino engineering shop. The PH Intelligence layer pushes that further: industry benchmarks, failure signatures, and risk scores are all calibrated to Philippine industrial conditions (typhoon season, brownouts, humidity, salt-air corrosion).

## 2. The User Map: Field to Management

WorkHive's user model is not "an account." It is a worker placed inside a hive (the plant or the team), with a role that defines what they can see and do.

**Worker tier (default).** A technician, operator, or maintenance staff member. Reads and writes logbook entries, runs PM checklists, draws parts from inventory, takes skill matrix assessments, executes assigned project tasks, and uses the AI assistant for on-shift help. Sees the data of their own hive and nothing else.

**Supervisor tier.** A shift supervisor or maintenance lead. Approves things: inventory restocks, PM completions, marketplace listings, hive joins, skill matrix promotions, project change orders. Reads the analytics for their hive. Triggers shift handover reports. Sends end-of-shift digests. Manages the project plan and assigns tasks.

**Manager tier.** A plant manager or engineering manager. Reads cross-shift trends (MTBF, MTTR, OEE), reviews the predictive analytics and risk scores, signs off on engineering designs and BOM/SOWs, approves project budgets and lessons learned, and holds the keys to integrations with SAP PM, IBM Maximo, or whatever CMMS is in place.

**Platform Admin tier.** Introduced in May 2026 with the marketplace go-live work. A small set of identities recorded in `marketplace_platform_admins` that hold cross-hive moderation rights for the marketplace and the public feed. Distinct from a plant-level supervisor; gated by a separate role check.

**Public tier.** Any visitor to `workhiveph.com`. Lands on the public homepage, can read public posts in the cross-hive feed, browse the marketplace, and explore the engineering design calculator without joining a hive.

The hive is the unit of multi-tenancy. Two plants on the same instance never see each other's logbook, inventory, project, or analytics. Cross-hive features (the public feed, the marketplace, the community forum, the PH Intelligence benchmarks) are explicit, opt-in, and scoped at the row level by Postgres Row Level Security.

## 3. The Module Map

Below is the live page roster, grouped by what the worker is trying to do. Every page is a single self-contained HTML file with its own CSS and JavaScript, plus the shared utilities in `utils.js`, `nav-hub.js`, `floating-ai.js`, `skill-content.js`, and `drawing-symbols.js`.

**Identity and entry**
- `index.html`: public homepage, hero, social proof, install-as-PWA hook
- `hive.html`: hive selector, join-by-code, role assignment, supervisor approval queue

**Daily work**
- `logbook.html`: digital shift logbook, offline queue, edit-in-place, parts deduction guard, work-order sign-off
- `pm-scheduler.html`: PM template library, due dates, completion logging, category mapping
- `inventory.html`: parts ledger, use/restock workflow with approval, transaction log
- `skillmatrix.html`: discipline-by-level matrix, badges, cooldown logic, pass thresholds
- `dayplanner.html`: DILO/WILO/MILO/YILO time blocks for personal planning
- `project-manager.html`: capital project planning, CPM scheduling, scope, resources, change orders, lessons learned
- `project-report.html`: print-ready project status PDF compiled from the project plan and execution log

**Knowledge and design**
- `engineering-design.html`: parametric calculator across six engineering disciplines

**Communication**
- `community.html`: forum, profiles, gamification, weekly digest (deferred until domain verified)
- `public-feed.html`: cross-hive public posts, opt-in only
- `report-sender.html`: shift handover and end-of-day digest, multi-channel (email, PDF)

**Marketplace (contact-only launch)**
- `marketplace.html`: buyer-facing listings (parts, training, jobs)
- `marketplace-seller.html`: seller dashboard with listings, inquiries, watchlist, analytics
- `marketplace-seller-profile.html`: public seller profile with verification badges
- `marketplace-admin.html`: platform admin approval queue, KYB verification

**Analytics and intelligence**
- `analytics.html`: cross-hive KPIs, MTBF/MTTR/OEE, trend charts
- `analytics-report.html`: print-ready PDF compiled from all four analytics phases
- `predictive.html`: ML-driven failure prediction, asset risk scores, anomaly detection (under review per the Canonical Sources Audit; per-asset risk is moving to Asset Hub, daily ranking to Shift Brain, aggregate narrative to Analytics Phase 3)
- `ph-intelligence.html`: Philippine industry benchmarks, failure signature matching, peer comparison
- `achievements.html`: gamification surface for badges, streaks, XP, and recognition
- `asset-hub.html`: Asset Brain 360 view per asset, with QR/barcode camera scan to jump straight to an asset
- `shift-brain.html`: autonomous shift planner with 4 sub-agents and supervisor publish-to-crew
- `alert-hub.html`: unified alert aggregator across risk, PM, stock, pattern, and automation

**Integrations**
- `integrations.html`: CMMS bridge configuration (SAP PM, IBM Maximo), webhook setup, sync status, audit log

**Operations and oversight**
- `assistant.html`: AI assistant landing page with platform context registry
- `alert-hub.html`: unified alert aggregator (risk scores, PM overdue, low stock, pattern alerts, failed automation jobs) in one chronological feed with type-filter chips

Two pages are explicitly retired and must never re-appear in the nav registry: `checklist.html` and `parts-tracker.html`. They were earlier prototypes that got absorbed into `pm-scheduler.html` and `inventory.html` respectively. (Note: `parts-tracker.html` still exists on disk for a backwards-compatibility canonical URL but is not in the nav array.)

A third page is now retired in favor of a stronger replacement: `platform-health.html` was the live Guardian dashboard from Phase 1 through Phase 6, but Phase 7 superseded it with the WorkHive Tester app. New dev-tooling features go into `test-data-seeder/`, not `platform-health.html`. The dashboard file remains for archival but is gated behind the `marketplace_platform_admins` check and is not the active surface.

Two more pages retired 2026-05-13 alongside the Maturity Stack landing-page revamp: `architecture.html` (the platform self-overview) and `symbol-gallery.html` (the drawing-symbol catalog). Neither earned a slot in the new public-facing 4-stage maturity ladder — Architecture is admin-only reference content, Symbol Gallery is a helper that belongs inside the Engineering Design Calculator. Both files remain on disk for direct-URL archival but are absent from nav-hub, assistant context, floating-ai context, the Stage Popout cards, and the WorkHive Tester PUBLIC_PAGES. Per-validator allowlists are marked `RETIRED 2026-05-13` so the Guardian recognises them as intentionally non-active.

## 4. Anatomy of a Page

Every WorkHive page follows the same skeleton, by convention rather than framework. There is no React, no Vue, no build step. It is vanilla HTML, vanilla CSS (with Tailwind via CDN for utility classes), and vanilla JavaScript.

A page does five things in this order:
1. Loads `utils.js` first, which wires the shared escHtml helper, hive context loader, role gate, and toast plumbing.
2. Loads `nav-hub.js`, which renders the two-tier nav (quick-access row of the four most-recent tools, plus the collapsible All Tools grid). v3 added the 4-column grid, search bar, and Ctrl+K shortcut. The May 9 update adds **role-based visibility** per tile (`roles: ['field','supervisor','engineer']`) so workers see fewer tiles than supervisors and engineers, and lazy-loads `search-overlay.js` so Cmd+K opens a platform-wide command palette searching assets, jobs, parts, and PMs from any page.
3. Loads page-local styles inline in `<style>` blocks, scoped by class.
4. Wires its own DOMContentLoaded handler, which reads the hive context, fetches Supabase rows, renders the UI, and subscribes to Realtime channels.
5. Loads `floating-ai.js` last, which mounts the AI assistant pill that follows the user across the platform.

The convention `const e = escHtml` at the top of every renderer is non-negotiable: the QA validator scans for it on every render function. The same QA pass checks that every `getElementById` call has a null guard, that every Realtime subscription has a matching teardown, and that every `hive_id` is included in every Supabase insert. The DOM Reference Integrity Validator (`validate_dom_refs.py`) catches the missing-null-guard pattern that was responsible for several silent crashes on iOS Safari.

A standing iOS rule: every form input renders at 16px or larger, since iOS Safari auto-zooms on inputs below 16px. The rule was learned the hard way (commit 5d0f9da) when the nav-hub search and the floating-AI input both shipped at 12px.

## 5. The Hive: Multi-Tenant Core

The hive is the tenant. Tables that hold worker data carry a `hive_id` column and are gated by Row Level Security policies that compare `hive_id` to the caller's membership. The migration `20260430000006_c4_enforce_rls.sql` flipped RLS on across the data tables, and the follow-on migrations (`20260501000003_missing_table_rls.sql`, `20260501000004_remaining_table_rls.sql`, `20260501_skill_profiles_auth_uid.sql`) closed the gaps.

A worker joins a hive by code. The supervisor approves. The membership row carries the role. Every page query and every Realtime subscription is scoped by the hive context loaded from local storage at boot. The Hive Validator (`validate_hive.py`) checks four things on every commit: that Realtime channels cover the page's writeable tables, that every insert carries `hive_id`, that the approval flow handles both `approved` and `rejected` states, and that every channel has a teardown call on page unload. A companion validator, `validate_hive_state_consistency.py`, catches the role and name persistence drift that surfaced when a supervisor's role flipped to worker on cache clear (commit 7effd1f).

A standing decision in project memory: a full Supabase Auth migration is planned but deferred. The current model uses worker name plus hive code; the planned migration will introduce `auth.uid()` everywhere and remove the cache-clear pain when a worker rejoins on a fresh device. The `c3_auth_uid.sql` and `c3b_auth_uid_remaining.sql` migrations have already laid the foundation by adding `auth_uid` columns and policies; the cutover is a future job. The `fix_auth_uid_backfill.sql` migration patched the trigger that was failing to populate `auth_uid` on insert.

## 6. The Logbook

The logbook is the most-used page on the platform. It is the modern replacement for the bound paper book on the maintenance shop floor.

What it does:
- Capture shift entries with category (electrical, mechanical, instrumentation, utilities, civil, HVAC), severity, equipment tag, free-text narrative, photos, and the worker's signature.
- Deduct parts from inventory inline, with a guard: an entry that says "replaced 2x V-belt" actually decrements stock and writes a row to `inventory_transactions`.
- Queue offline. The page persists drafts in IndexedDB; when connectivity returns, it flushes the queue.
- Edit in place. A worker who realizes they wrote the wrong tag taps the entry and corrects it; the form is the same form used to add, not a new modal.
- Sign off work orders. The work-order sign-off flow added in May 2026 (commit bf30916) lets the responsible worker close out a logged issue with a signature, a closed_at timestamp, and a one-tap link back to the originating PM or project task.
- Flow through a formal work-order state machine. Phase E.4 (migration `20260508000015_work_order_state.sql`) adds two ADDITIVE columns (`wo_state`, `wo_state_meta`) so logbook entries can flow through requested -> approved -> assigned -> in_progress -> completed -> verified, with rejected and re-open branches. Existing rows stay null and behave exactly as before; the workflow is opt-in per entry. Composite indexes on (hive_id, wo_state) support board-style queries.
- Tag a failure consequence (downtime, rework, safety) and a closed_at timestamp once the issue is resolved. These two columns feed MTBF and MTTR in analytics.
- Voice capture. The `voice-logbook-entry` edge function takes a recording, transcribes it, classifies the intent, and writes a draft entry the worker can confirm.
- Auto-link to active projects. When a project is in execution, log entries that match the project's equipment scope and date window auto-attach to the project's execution log (Phase 3B/3C).

The logbook validator (`validate_logbook.py`) defends three rules: every entry has a `closed_at` either null or in the future of `created_at`; every parts deduction has a matching `inventory_transactions` row; and the PM-category-to-log-category mapping does not write a log under a category that does not exist (a real bug found in April 2026 where HVAC, Utilities, and Civil PMs were mapping to invalid log categories). A second validator, `validate_logbook_consistency.py`, catches drift between the logbook UI and the underlying schema.

## 7. The PM Scheduler

The PM scheduler holds the preventive maintenance template library. A template defines: equipment class, frequency in days, checklist steps, expected duration, required parts, and required skills. The page renders the upcoming and overdue PMs for the hive, and a worker checks them off through the same form the logbook uses.

The PM Validator (`validate_pm.py`) runs five checks: that every template's `freq_days` matches the canonical FREQ_DAYS table; that template categories cover every supported discipline; that the PM-to-logbook category mapping resolves to a real logbook category; that the payload schema matches the columns expected by the renderer; and that midnight is normalized in UTC so a Manila-timezone PM does not skip a day on the boundary.

PM completions also auto-link to active projects (Phase 3B/3C, commit f8c8558), so a PM run during a planned shutdown shows up in the project's execution log without manual reconciliation.

## 8. The Inventory

The inventory is the parts ledger. Workers draw parts; supervisors approve restocks. Every transaction writes to `inventory_transactions` with a `qty_after` column (the running balance after the transaction), so the page never has to recompute history to render a balance.

The Inventory Validator (`validate_inventory.py`) covers six guards: every transaction has a non-null `qty_after`; every transaction is hive-scoped; the use and restock paths emit transactions of the correct sign; the approval workflow handles both `approved` and `rejected`; the page never permits a negative balance overflow; and the cross-page flow into the logbook deduction is consistent (the bug that surfaced in April 2026 was a missing `qty_after` column on the cross-page insert from logbook into inventory_transactions). A second validator, `validate_inventory_integrity.py`, runs deeper consistency checks across the ledger and the equipment registry.

Production fix #29 (May 5, 2026) added `id` to the `inventory_transactions` insert path. Before the fix, every parts-deduction save from logbook entries was failing silently; the fix is now part of `PRODUCTION_FIXES.md` at the project root.

## 9. The Skill Matrix

The skill matrix tracks who can do what, by discipline and by level. A worker takes an assessment; on pass, a badge unlocks; cooldown logic prevents re-taking until a wait period elapses. The matrix is what powers job listings on the marketplace ("must hold Level 2 Electrical") and the PM eligibility filter ("only Level 3 Mechanical can sign off this PM"), and it now also gates project task assignment ("this task requires Level 3 HVAC").

The Skill Matrix Validator (`validate_skillmatrix.py`) checks that disciplines and levels match the canonical constants, that the badge conflict key prevents two badges with the same identity, that cooldown logic respects the configured wait, that the pass threshold is enforced, and that the content coverage matches the disciplines registered on the page. The `skill_badges_badge_key` migration (May 4) closed a latent bug where the community badge trigger was inserting against a missing column.

## 10. The Engineering Design Calculator

This page is one of the larger pieces of work in the platform. It is a parametric calculator across six engineering disciplines: electrical, mechanical, instrumentation and controls, plumbing and fire suppression, lighting, and HVAC. For each calc type, the worker enters parameters; the page validates the inputs, runs the calculation, generates a single-line diagram or schematic, emits a Bill of Materials and a Scope of Work, and renders a print-ready report.

The calculator is governed by a four-layer validator suite (`run_all_checks.py`):
- **Layer 1: Schema and field validators.** Inputs match the declared schema; required fields are present.
- **Layer 2a: Renderer validators.** Every `renderXxxReport` function declares `const e = escHtml` at the top, every diagram input is sanitized, every calc emits the BOM/SOW dual artifact, and every print path uses the validated print popup pattern (margin:0, body padding, color override).
- **Layer 2b: BOM/SOW mismatch validators.** The BOM and the SOW are derived from the same calc payload, but they read it through two different render paths. Any drift between the parts in BOM and the activities in SOW is a fail.
- **Layer 3: Live integration test.** Calls the deployed `engineering-calc-agent` and `engineering-bom-sow` edge functions with a representative payload and verifies the response shape.

A standing practice from project memory: the validator suite must run on every Python, renderer, or BOM/SOW change, and zero FAIL is the precondition for a UI spot-check. The Standards Validator additionally cross-references every formula against the live web on first introduction (IEC, NFPA, IESNA, ISO, ASHRAE), so a calc cannot ship with a formula that does not match the cited standard.

The Group 3 Fire and Life Safety calc diagram fixes (commit 5d8959f, May 4) closed four diagram bugs across calcs #23 to #26. The field-name alignment work (commit 8d87d7d, May 3) unified field names across calc payload, diagram emitter, and BOM/SOW so renamed inputs no longer silently broke one of the three render paths.

## 11. The Marketplace (Contact-Only Launch)

The marketplace was the most recent module to land in late April / early May. The original architecture targeted full Stripe Connect escrow; on May 2, 2026 the launch posture pivoted to contact-only (payments feature-flagged off, commit 3d7691a), and on **2026-06-30 Stripe was removed entirely** — the marketplace is now permanently FREE and contact-only, with no payment code in the tree. The seller is contacted directly by the buyer through Facebook Messenger (commit ebe03b2) or a JSON-LD/OG-tagged inquiry form, with the inquiry templates and real-time listing quality score driving conversion.

The reason for the pivot, captured in the marketplace go-live roadmap at the project root: DTI registration is not yet complete, and the platform cannot accept escrow funds in WorkHive's name until that step lands. The roadmap is six phases; Phase 1 is the active blocker.

The product types remain the same:
- **Parts.** Surplus spares, OEM components, refurbished tools.
- **Training.** Skill-aligned courses sold by accredited trainers.
- **Jobs.** Short-term industrial gigs, scoped to a hive's region and skill matrix.

The contact-only flow:
1. A seller lists. A platform admin (not a hive supervisor) approves the listing.
2. A buyer browses, filters, saves searches (`saved_searches`), watchlists items (`marketplace_watchlist`), and contacts the seller through Messenger or the inquiry template.
3. Communication and fulfilment happen off-platform until DTI registration is in place.

The seller surface added in May:
- Multi-tier verification badges (`seller_badges`, commit 2d62b76) that attach to the seller's public profile.
- Seller analytics dashboard (commit f86b63f) with views, inquiries, conversion.
- Image upload via Supabase Storage (commit ce68b26).
- Bulk inquiry / RFQ flow (commit 2810f99).
- Public seller profile page (`marketplace-seller-profile.html`).

The page set:
- `marketplace.html`: buyer-facing browse, search, filter, contact.
- `marketplace-seller.html`: seller dashboard with listings, inquiries, and analytics.
- `marketplace-seller-profile.html`: public seller profile with badges and listings.
- `marketplace-admin.html`: platform admin approval queue plus KYB verification (gated behind the `marketplace_platform_admins` role).

> **★ Stripe removed entirely (2026-06-30).** The marketplace is FREE and contact-only — no payments. The 5 Stripe edge functions (`marketplace-checkout`, `marketplace-connect-onboard`, `marketplace-connect-status`, `marketplace-release`, `marketplace-webhook`) were **deleted** (not flag-disabled), the `stripe_*` DB columns dropped (migration `20260630000000_remove_stripe_free_marketplace.sql`), and the `PAYMENTS_ENABLED` flag + all checkout/escrow/payout/order UI removed. The buyer action is the **Contact-Seller inquiry** (`marketplace_inquiries`), and sellers are reached via phone/email/Messenger. There is no payment rail to "flip on."

The migrations land the schema in stages: `20260501000005_marketplace.sql` (core tables), `20260501000006_marketplace_scale.sql` (indexes), `20260501000007_seller_dashboard.sql` (denormalized views), `20260501000008_buyer_reviews.sql` (review submission), `20260502000000_seller_messenger.sql`, `20260502000001_marketplace_watchlist.sql`, `20260502000002_marketplace_storage.sql`, `20260502000003_seller_badges.sql`, `20260502000004_listing_view_count.sql`, `20260502000005_saved_searches.sql`, `20260502000006_platform_admins.sql`.

The Marketplace Validator (`validate_marketplace.py`) runs 14 checks across four layers: schema integrity, edge-function security, UI gates, and money flow. The May 2026 baseline is 14 of 14 PASS.

## 12. The Project Manager

The Project Manager landed on May 5, 2026 in a sustained build (Phase 0 through Phase 6.6, commits 71e5ea0 through 577ed0a). It is the first module in WorkHive that is genuinely cross-cutting: it pulls from the logbook, the PM scheduler, the inventory, the skill matrix, and the engineering calculator into a single project plan and execution log.

What it does:
- **3-step wizard.** Project type (turnaround, capex, retrofit, decommissioning), template (each type ships with sane defaults), and scope. Smart defaults are filled from the hive's history.
- **Phase-grouped scope.** The scope is grouped into phases; each phase contains tasks; each task has predecessors, resources, and a status pill that cycles through plan / execute / done.
- **CPM via Python backend.** Critical Path Method scheduling runs on the Python analytics API using `networkx`. The edge function `project-orchestrator` brokers the call; the Python service computes the schedule and returns the timeline.
- **Resources and multi-role.** A task can require multiple roles (e.g. one Level 2 Mechanical and one Level 1 Electrical). Resource conflicts are surfaced.
- **Risk and change orders.** Every project carries a risk register and a change-order log. Change orders capture scope, cost, and schedule deltas, with supervisor approval.
- **Auto-link from logbook and PM.** A logbook entry tagged to the project's equipment during the project's date window auto-links to the execution log. Same for a PM run during the project window. (Phase 3B/3C.)
- **Project Report PDF.** `project-report.html` compiles the project plan, the execution log, the risk register, the change orders, and the lessons learned into a single print-ready PDF (Phase 4).
- **Lessons Learned.** A structured close-out section that goes into the project's knowledge entry, indexed by the `project_knowledge` migration's pgvector embedding for retrieval by future projects.
- **Background AI.** The `project-progress` edge function runs in the background to nudge the project forward: due-date reminders, scope-creep flags, and a daily summary of execution-log activity.

The schema lives in three migrations:
- `20260505000000_project_manager.sql`: core tables (projects, phases, tasks, predecessors, resources, status).
- `20260505000001_project_advanced.sql`: risk register, change orders, multi-role resource assignments.
- `20260505000002_project_knowledge.sql`: project knowledge with `vector(384)` embedding (corrected from the initial vector(1024) embedding-dim bug, commit 25f7274).

The edge functions are `project-orchestrator` and `project-progress`. The Project Manager Validator (`validate_project_manager.py`) covers the schema, the wizard flow, the CPM contract, the auto-link rules, and the print path.

The full roadmap is in `PROJECT_MANAGER_ROADMAP.md` at the project root. Phases 1 through 6 are done; Phase 7+ is on the road ahead.

## 13. CMMS Bridge and Integrations

The CMMS bridge landed May 6 to 8, 2026 (commits leading into 3d7e52b). It connects WorkHive to upstream CMMS systems (SAP PM, IBM Maximo, generic CMMS via REST) and downstream systems (mobile dispatch, ERP). The page surface is `integrations.html`; the backend is three edge functions plus a webhook receiver.

What it does:
- **Configure live sync.** The page guides a manager through connection setup: endpoint, auth method, field mapping, sync window. Auth supports API key, OAuth 2.0, and SAP PM's specific session token model.
- **Push completion events.** When a logbook entry closes a work order, the `cmms-push-completion` edge function pushes the completion (with parts, hours, photos, sign-off) back to the upstream CMMS.
- **Pull work orders.** The `cmms-sync` edge function pulls the upstream backlog on a configurable schedule.
- **Receive webhooks.** The `cmms-webhook-receiver` edge function accepts pushed events (work order created, status change, assignment change) from the upstream CMMS and reconciles them into WorkHive.
- **Audit log.** Every sync operation is logged to `cmms_audit_log` with payload, response, and reconciliation outcome. The integrations page renders the audit log inline so a manager can debug a failed sync without leaving the surface.

The schema:
- `20260506000000_external_sync.sql`: connection registry, field mappings, sync state.
- `20260507000001_integration_auth.sql`: auth credentials with envelope encryption.
- `20260508000003_cmms_audit_log.sql`: audit log table.

The validators:
- `validate_cmms_contracts.py`: checks the schema of the push and pull payloads against the canonical CMMS contracts.
- `validate_cmms_reconciliation.py`: checks that every webhook event is reconciled (matched to an existing WorkHive row or queued for manual review).
- `validate_integration_security.py`: 9 checks across CORS, JWT, deploy script coverage, dynamic CORS pattern, deploy script coverage; covers both the marketplace and CMMS edge functions.

The mock CMMS at `test-data-seeder/mock_cmms/` lets the integrations page be tested end to end without a real SAP or Maximo instance. The WorkHive Tester drives both ends: it seeds an upstream backlog, lets WorkHive sync it, executes work in WorkHive, and verifies the push-back lands in the mock.

## 14. Predictive Analytics and Risk Scoring

The predictive layer is the ML brain of the platform. It went from rule-based thresholds to a real model pipeline in May 2026.

What it does:
- **Asset risk scores.** Every asset gets a daily risk score on a 0 to 100 scale, computed by `batch-risk-scoring` running on a `risk_scoring_cron` schedule. The score is a blend of failure history, MTBF deviation, anomaly signals from sensor readings, and the failure-signature match rate.
- **Failure signature matching.** Known failure patterns are stored as `failure_signatures` rows: a vector embedding of the symptom narrative plus the equipment class. The `failure-signature-scan` edge function runs on every new logbook entry, checks for a high-similarity match, and surfaces "this looks like a known failure pattern" inline. The match also feeds into the asset's risk score.
- **Pattern alerts.** When a hive's risk score curve breaks trend (a step jump in failures across an asset class, an unusual co-occurrence), `validate_pattern_alerts.py` flags it for the manager's morning review.
- **Predictive page.** `predictive.html` renders the risk score leaderboard, the asset trend charts, and the recommended action queue. A worker sees the top three assets to attend to today; a supervisor sees the hive's overall risk posture.
- **Retrain trigger.** `trigger-ml-retrain` is the manual override for re-fitting the model when a new failure mode is added or a sensor's calibration changes.

The schema:
- `20260507000000_failure_signatures.sql`: signature library with pgvector embeddings.
- `20260508000000_asset_risk_scores.sql`: daily scores per asset.
- `20260508000001_risk_scoring_cron.sql`: pg_cron schedule for the daily batch.

The validator (`validate_ml.py`) checks the model contract, the score range, the feature freshness, and the retrain trigger gates. `validate_predictive.py` covers the page-side rendering and the alert triggers.

**Phase ML-2 Auto-Staging** (May 9). When `batch-risk-scoring` writes a row above the 0.7 risk floor, `parts-staging-recommender` runs daily after it and proposes which parts to pre-stage from inventory. The model is deterministic v1: a part is recommended when it appears in at least 3 of the last 365 days of corrective records for the same asset AND inventory has stock on hand, with confidence equal to history_hits divided by total corrective records. Recommendations expire after 7 days so stale ones do not accumulate, and only one active recommendation per (hive, asset) is kept. Two new tables: `parts_staging_recommendations` (the recommendation itself with rationale + confidence + status pending/accepted/dismissed/expired) and `parts_staged_reservations` (when a worker accepts, the recommendation creates a reservation that holds inventory without consuming it until the actual repair logbook entry closes). Inventory page now surfaces staged reservations alongside on-hand stock so workers see what is committed.

## 14b. Alert Hub

`alert-hub.html` (May 9) is the unified alert aggregator. Rather than each module having its own alert UI, the hub pulls from five sources into one chronological feed: asset risk scores above threshold, PM overdue items, low-stock inventory rows, pattern-alert triggers from `validate_pattern_alerts.py`, and failed automation jobs from `automation_log`. Type-filter chips (Risk / PM / Stock / Pattern / Automation) let a supervisor focus on one class at a time. Each alert row deep-links to the source page (Asset Hub for risk, PM Scheduler for PM, Inventory for stock, etc.) with the relevant filter pre-applied. The AI assistant on this page is context-aware of which alerts are visible and which one was last clicked.

## 15. PH Industrial Intelligence

The PH Intelligence layer is what makes WorkHive Filipino, not just translated. It correlates a hive's data with anonymized peer data across other hives to produce industry benchmarks calibrated to Philippine industrial conditions.

What it does:
- **Industry benchmarks.** A hive's MTBF, MTTR, OEE, parts spend, and PM compliance are compared to the median and 75th percentile across peers in the same industry segment (food and beverage, plastics, electronics, semiconductor, automotive parts, packaging). The `benchmark-compute` edge function computes the rollups; `benchmarks` is the stored table.
- **Failure-signature library.** The PH layer maintains a curated library of failure signatures specific to Philippine conditions: typhoon-season impacts (water intrusion, lightning, voltage sag), brownout effects, salt-air corrosion in coastal plants, humidity-driven insulation failure. The library is the source of `failure_signatures` rows that feed predictive analytics.
- **Peer comparison.** `ph-intelligence.html` renders the hive's posture against peers, with the intelligence report compiled by `intelligence-report` and served by `intelligence-api`. The report is exportable as PDF for the morning manager review.
- **Privacy guard.** Every benchmark rollup is computed across at least N=5 hives in the segment to prevent peer-identification by inference. The Tenant Boundary Validator enforces this.

The schema:
- `20260507000002_benchmarks.sql`: benchmark tables and rollup state.
- `20260507000003_ph_intelligence.sql`: intelligence report compilation, peer-comparison metadata.

## 16. Achievements and Gamification

`achievements.html` (May 8, 2026) consolidates the gamification surface that was previously scattered across community profiles, the skill matrix, and the logbook. The schema is `20260508000002_achievements.sql`.

What it does:
- **Streak tracking.** Daily logbook submissions, weekly PM compliance, monthly skill assessments. Streaks unlock visible badges.
- **XP and levels.** XP is earned through logbook entries, PM completions, skill matrix passes, helpful community posts, and project task completions. The community module already had XP triggers; the achievements page is the unified dashboard.
- **Badges.** Badges are the conflict-keyed unlock objects (one per identity). Some are skill-tied; some are tenure-tied; some are community-tied.
- **Recognition feed.** A hive-scoped feed of "X earned the Y badge today," visible to the hive supervisor and optionally posted to the public feed.

The page is read-mostly. Triggers for awarding badges live in Postgres triggers (`handle_community_post_xp`, etc.) and edge functions; the page reads the materialized state.

## 17. Community and Public Feed

The community module is a forum-and-profile layer for cross-hive participation. Workers earn XP, unlock badges, and post questions or how-tos that can be seen by other hives if marked public. The migration sequence (`20260430000000_community_tables.sql` through `20260501000000_d2_cross_hive_feed.sql`) builds the schema in seven steps, including the public-post visibility rules and the cross-hive feed query path.

**Capability matrix as of May 2026** (after the analyse-and-improve session): posts with categories (general, safety, technical, announcement); reactions (👍 🔧 🔥 👀) with INSERT and DELETE realtime sync across devices; threads with replies; supervisor mod queue; pin, flag, public, and soft-delete actions; **worker report flow** with reason picker (harassment, unsafe, spam, other) plus optional details, captured in the audit log; **soft-delete with 5s undo** via `community_posts.deleted_at` and a parallel `showUndoToast` component; **edit post** via `edited_at` column with an "edited" badge in the timestamp; **`@mentions`** with autocomplete dropdown, longest-first parser, and realtime "X mentioned you" notifications; **deep-link to thread** (`?post=<uuid>`) with copy-link button and hive-scope guard on cross-hive links; **composer "Make public" toggle** (supervisor-only, auto-locked for announcements); **cross-hive Global tab** powered by a separate `community-global-feed` realtime channel filtered by `public=eq.true`; **community guidelines** collapsible inside the composer; **welcome card** on empty state with role-aware tips; **full WCAG 2.2 AA accessibility kit** (focus trap on every sheet, Escape closes any open sheet, `:focus-visible` rings, `role="status" aria-live="polite"` on the connection chip, `aria-pressed` and reaction-count in `aria-label` on toggle buttons). **Dual-layer rate limit**: client-side cooldown (5s posts, 3s replies) for UX, plus Postgres `BEFORE INSERT` triggers `trg_community_post_rate_limit` (3 posts / 30s) and `trg_community_reply_rate_limit` (5 replies / 15s) for actual abuse prevention.

The session also surfaced two non-obvious failure modes that are now standing rules: (a) any new realtime-subscribed table requires `ALTER PUBLICATION supabase_realtime ADD TABLE <name>`, otherwise listeners are silently dead, hidden by optimistic UI on the originating client; (b) Postgres default `REPLICA IDENTITY = PK` only, so DELETE realtime filters on non-PK columns silently drop every event. Both are documented in the multitenant-engineer, realtime-engineer, architect, devops, and qa-tester skills, and the new-feature registration checklist in memory. The `validate_realtime_publication.py` validator catches the first; `validate_soft_delete.py` catches the second.

The B2 weekly digest (a Resend-powered email summary of community activity) is built but deferred. Project memory makes the rule clear: do not enable digest sending until the sending domain is verified at Resend. The full scope of the digest is documented in the deferred memory entry.

## 18. Analytics, Reporting, and the Day Planner

**Analytics (`analytics.html`).** Cross-shift KPIs: MTBF, MTTR, OEE, parts spend, PM compliance, top fault classes. The page is read-only for workers and supervisors, with a manager-tier toggle for cross-hive comparisons. The Analytics Validator (`validate_analytics.py`) covers 22 checks across three layers: HTML structure, the `analytics-orchestrator` edge function contract, and the Python backend that builds the rolled-up RPC views. The May 4 UX overhaul (commit ce5118b) restructured the page around scale, filter, role cleanup, and decision-relevant ordering. The April 2026 schema-drift fix (commit a7f485a) corrected asset-key joins and put honest empty states on calc paths that previously silently rendered nothing.

**Analytics Report (`analytics-report.html`).** Print-ready PDF compiled from all four analytics phases (commit c03ca36, May 4). The blank-page-1 and PM-table layout polish (commit 0561b37) closed the residual print issues.

**Report Sender (`report-sender.html`).** End-of-shift handover and end-of-day digest. The validated pattern (per project memory) is the a-f handover structure, calendar-period dates, the print popup pattern (margin:0 plus body padding plus color override), and a regex-based LOTO detection that scans logbook narratives for the standard isolation phrases. 32 checks across four layers (page structure, UI, logic, PWA and edge functions).

**Day Planner (`dayplanner.html`).** Personal planning page with four time-block modes: DILO (Day in the Life Of), WILO (Week), MILO (Month), YILO (Year). Already shipped; project memory marks it as built so it is not re-treated as a future feature.

## 19. The AI Assistant Layer

A floating AI pill is mounted on every page through `floating-ai.js`. It reads the page context (which page, which hive, which logged-in worker, what is on screen) from a registry maintained in `assistant.html` and calls the `ai-orchestrator` edge function. The orchestrator routes to the right model: Claude Sonnet 4.6 for reasoning-heavy work, Gemini Flash for cheap classification on the free tier, with a Groq fallback for latency-sensitive paths. Anthropic prompt caching is on for every Claude path.

The full edge-function surface as of May 8 (27 functions):

**AI core**
- `ai-orchestrator`: main router, prompt caching, model selection.
- `analytics-orchestrator`: analytics with LLM-on-top summary.
- `intelligence-api`, `intelligence-report`: PH Intelligence query and compile.
- `embed-entry`, `semantic-search`: pgvector embed write and KNN read.

**Voice**
- `voice-report-intent`, `voice-transcribe`: voice intent classification and transcription.
- `voice-logbook-entry`: voice-first logbook capture.

**Engineering calc**
- `engineering-calc-agent`: NL entry to calc payload.
- `engineering-bom-sow`: BOM and SOW from calc payload.

**Project**
- `project-orchestrator`: CPM scheduling broker to Python service.
- `project-progress`: background progress nudges and summaries.

**ML pipeline**
- `batch-risk-scoring`: daily asset risk score batch.
- `failure-signature-scan`: per-entry failure-pattern match.
- `benchmark-compute`: peer-comparison rollups.
- `parts-staging-recommender`: Phase ML-2 daily Auto-Staging recommender (post-batch-risk-scoring).
- `trigger-ml-retrain`: manual model retrain trigger.

**CMMS bridge**
- `cmms-sync`, `cmms-push-completion`, `cmms-webhook-receiver`.

**Marketplace** — free + contact-only; the 5 Stripe edge fns were deleted entirely 2026-06-30 (no payment edge fns remain).

**Operations**
- `scheduled-agents`: pg_cron-driven jobs.
- `send-report-email`: Resend send for digests.

The Assistant Validator (`validate_assistant.py`) ensures three things: every page has a context entry in the registry, the PLATFORM TOOLS list is complete, and the disciplines named in the assistant prompt match the disciplines registered in the skill matrix. The April 2026 bug where the engineering-design page was missing from the registry, and the Skill Matrix disciplines on the assistant did not match the live ones, is now caught by the validator on every commit.

A May 2026 fix worth noting (commit 2b14129): the semantic-search retrieval was using a broken Groq embedding path that had silently degraded to a hash-fallback. The fix replaces it with a Voyage and Jina chain, with the Groq path retained only as a last-resort fallback. The `validate_groq_fallback.py` validator now enforces that the chain is in the right order.

## 20. Tech Stack and Hosting

**Front end.** Vanilla HTML, CSS, JavaScript. Tailwind via CDN. Poppins as the type face. No build step. Every page is a self-contained file. PWA enabled through `sw.js` (cache version v12 as of May 5, 2026) and `manifest.json`. No TypeScript in HTML inline JS: the `: string` and `as HTMLElement` annotations silently break the entire script block on file:// load (commit 6e0dba7 fixed a marketplace.js incident).

**Back end.** Supabase: Postgres with RLS, Realtime, Edge Functions (Deno), Storage, Auth (in migration). pg_cron for scheduled work. pgvector for semantic search.

**Python analytics API.** A FastAPI service running locally under `uvicorn` from `C:\wh-venv` against `Z:\python-api` with `--reload`. Required for the Analytics page and the Project Manager's CPM solver. The edge functions reach it through `PYTHON_API_URL=http://host.docker.internal:8000` declared in `supabase/functions/.env`.

**AI.** Claude Sonnet 4.6 as primary. Gemini Flash on the free tier for cheap operations. Groq for latency fallback. Voyage and Jina for semantic-search embeddings. Anthropic prompt caching is on for every Claude path.

**Payments.** None. The marketplace is FREE and contact-only — Stripe was removed entirely on 2026-06-30 (no checkout, escrow, payouts, or webhooks). Buyers and sellers transact off-platform; the platform connects them via the Contact-Seller inquiry + Messenger handle.

**Email.** Resend, with the sending domain pending verification before the weekly digest goes live.

**Hosting.** Cloudflare Pages for the static site, Supabase for everything stateful. The `_headers` file at the root sets the security and caching headers; the `sw.js` file is the PWA service worker.

**Local dev.** A peculiarity in project memory: the parent folder name has an `&` character, which breaks `npx supabase deploy`. The standing workaround is to run `subst Z:` first to give the working tree a clean drive letter, then run `.\deploy-functions.ps1` from there. PowerShell scripts at the project root must be pure ASCII (no em dashes, no smart quotes), or Windows PS 5.1 will reject them.

---

# Part II. The Framework: WAT, Skill-First, Guardian

## 21. Why a Framework at All

The platform is one project. The framework is how it stays buildable as the project grows past the point where any one human (or any one Claude Code session) can hold the whole thing in working memory.

The math is honest. If each step in a multi-step build is 90% accurate, five steps gets you 59% reliability; ten steps gets you 35%. That is the curve that makes ad-hoc AI-driven coding fail at scale. The framework's job is to bend that curve, by separating reasoning (which AI does well) from execution (which deterministic code does perfectly) and by capturing every lesson learned so the next session does not relearn it.

There are four layers of leverage in the framework, and they nest: WAT separates reasoning from execution; Skill-First captures lessons as input to the next reasoning step; the Platform Guardian enforces that the lessons stayed enforced; the WorkHive Tester drives end-to-end flows so the validators are not the only line of defense.

## 22. WAT: Workflows, Agents, Tools

WAT stands for Workflows, Agents, Tools. The three layers are clean and the boundary between them is enforced by file location, not by convention.

**Layer 1: Workflows. The instructions.** Markdown SOPs in `workflows/`. Each workflow names an objective, the inputs it needs, the tools it should use, the expected outputs, and the edge cases it has to handle. They are written like a brief to a human teammate. They are the version-controlled, human-readable record of how this work gets done.

**Layer 2: Agents. The decision-maker.** This is the role Claude Code plays. The agent reads the workflow, picks the right tools in the right order, handles failures with judgment, and asks the user when the workflow does not cover an edge case. The agent does not do the work directly. It coordinates.

**Layer 3: Tools. The execution.** Python scripts in `tools/`, plus the Supabase edge functions in `supabase/functions/`. These are the deterministic parts. They make the API call, transform the data, write the file, query the database. Credentials live in `.env`, never in code.

The point of the separation is that a task with five tool calls, each with 99% reliability, gets you 95% reliability end to end. A task where the AI tries to do all five steps directly gets you 59%. The split is the productivity hack.

The agent's job description, written in `CLAUDE.md` as the standing brief: "You sit between what I want (workflows) and what actually gets done (tools). Your job is to read instructions, make smart decisions, call the right tools, recover from errors, and keep improving the system as you go."

## 23. The Skill-First Rule

The Skill-First Rule is not negotiable: before writing any code, fixing any bug, or building any feature, the agent reads the relevant skill files. Skills live at `C:/Users/ILBeronio/.claude/skills/<skill-name>/SKILL.md`. They are not documentation. They are accumulated lessons from past sessions. Ignoring them means repeating mistakes that have already been solved, in front of the same user, on the same code.

The four-step practice:
1. Identify which domains the task touches. A bug in a report renderer touches Frontend and QA. A new calc type touches Frontend, QA, and Maintenance Expert. An edge function deploy touches DevOps and AI Engineer.
2. Read those skill files before writing a single line. One Read call per skill. Scan for sections that match the task: checklist items, anti-patterns, rules.
3. Apply what you find. If QA says "every renderer must declare `const e = escHtml`," check that before writing the renderer, not after. If Frontend says "BOM/SOW has 10 sync points across 2 render functions," that is the task checklist.
4. After the task, update the skills with what you learned. (See the Self-Improvement Loop, below.)

The cost is one Read per skill. The payoff is catching known issues before they become bugs.

## 24. The Full Skill Roster

Skills are partitioned by when they are in scope. Some are checked every session. Some come in when their domain is touched. Some come in only when a domain lesson surfaces.

**Always in scope (every session):**
- **QA.** Test checklist items, edge cases, empty and error states, broken flows.
- **Frontend.** Coding patterns, anti-patterns, state management rules.
- **Performance.** Query efficiency, render bottlenecks, caching patterns.
- **Mobile Maestro.** Touch targets, safe areas, iOS and Android quirks, PWA rules.
- **Security.** XSS vectors, data exposure, auth bypass, injection risks.

**In scope when the domain is touched:**
- Architect, Data Engineer, Multitenant Engineer, Realtime Engineer, Notifications, Analytics Engineer, AI Engineer, DevOps, Integration Engineer, Predictive Analytics, Knowledge Manager, Enterprise Compliance.

**In scope when a domain lesson surfaces:**
- Designer, Maintenance Expert, Community, SEO and Content, TCG Expert (legacy from a sibling project, kept dormant).

There are also platform-specific validator skills, each of which is a wrapper around the matching `validate_*.py` script:
- Codebase Integrity, Cross-Page Flow Validator, Hive Validator, Inventory Validator, Logbook Validator, PM Validator, Skill Matrix Validator, Assistant Validator, Standards Validator, Engineering Calc Validator, Drawing Standards Skill, Platform Guardian.

A standing rule: the Skill-First Rule applies whether the user invoked a skill explicitly with a slash command or not. Every code change reads the skills first. Every code change writes back to the skills after.

## 25. The Self-Improvement Loop

After every skill run, and after any bug fix or refactor or issue resolution (even with no formal skill invocation), the agent runs the Self-Improvement Loop. The rule is non-negotiable, and the reason is captured in project memory: findings that stay only in the session are wasted. Every session leaves all relevant skills smarter, not just the one that was invoked.

The loop is four steps:
1. Review what was discovered or fixed during the session.
2. For each lesson, scan the full skill roster and ask: would this skill have caught or prevented this? One bug often teaches rules that belong in three or four skills at once. Write to all of them, each from its own angle. (A null-pointer crash in a renderer is a Frontend lesson about defensive checks, a QA lesson about empty-state coverage, a Mobile lesson about iOS-specific render order, and a Security lesson about user-input echo. One bug, four skills.)
3. Present proposals as a cross-skill table for one-pass approval, so the user signs off without having to read four edits.
4. Once approved, write to all relevant skill files in one Edit pass.

The compound effect is what makes this loop work. After 100 sessions, the QA skill has 100 checklist items added by past failures, and the next session inherits all 100 for free.

## 26. The Platform Guardian

The Platform Guardian (`run_platform_checks.py`) is the master orchestrator. It runs every validator, checks the readiness gate, and compares the result to the saved baseline. It is the gate before commit, the gate before deploy, the gate before "done."

The Guardian wraps four loops:
- **Loop 0: Observation.** Compare to baseline. If a previously passing check now fails, that is a regression and exits with code 2.
- **Loop 1: Retrospection.** Run all validators. Classify failures.
- **Loop 2: Self-Learning.** Auto-update skill files when patterns repeat.
- **Loop 3: Readiness Gate.** Git status, deployment status, API status. If git is dirty in a way that should not ship, exit with code 3.
- **Loop 4: Improvement.** Open a backlog item with web-search context when the same FAIL trips three runs in a row.

The closed-loop dashboard added on May 3 (commit b5eb51f) wired the loops together with a unified health score, run history, bug intake, trend alerts, fix wizards, skill lessons, and an AI diagnose path. Phases 1, 10, and 11 of that work added the auto-discovery validator and the schema-coverage validator, which together close the registration-gap loop: a new HTML page, a new edge function, or a new validator that is missing from any of the platform's six registries (validators' LIVE_PAGES and TARGET_PAGES, `floating-ai.js`, `assistant.html`, `nav-hub.js`, `config.toml`) is flagged automatically.

The exit codes are the contract:
- `0`: all pass. Safe to commit, deploy, or start the next feature.
- `1`: one or more validators failed. Fix before commit.
- `2`: regression detected. The check used to pass; now it does not. Top priority.
- `3`: readiness gate blocked. Git or deploy state is not safe.

The Guardian writes two artifacts every run:
- `platform_health.json`: machine-readable report of the run.
- `platform_baseline.json`: saved when all checks pass. Used for regression detection on the next run.

The legacy dashboard (`platform-health.html`) is retired in favor of the WorkHive Tester (next section). The dashboard file remains at the project root for archival, gated by the `marketplace_platform_admins` check.

## 27. The WorkHive Tester (Testing Battlefield)

The WorkHive Tester is the testing battlefield. It is a Python and Playwright app under `test-data-seeder/` that drives every flow in the platform end to end, with five named gates:

1. **Smoke gate.** Every page loads. No console errors. No 4xx or 5xx from Supabase.
2. **CRUD gate.** Every page can create, read, update, and delete its primary entity, with hive scoping respected.
3. **Cross-page gate.** Every cross-page flow (logbook deduction into inventory, PM completion into logbook, project auto-link, CMMS push) writes the right rows in the right places.
4. **AI gate.** Every AI surface (orchestrator, voice, semantic search, predictive, intelligence) returns a sane response on a representative payload, including the multi-agent chain tests at Tier 4 (write, embed, retrieve, full RAG).
5. **Mega Gate.** The unified end-to-end journey across the whole platform: a worker joins a hive, runs a shift, closes a work order, watches the analytics, sees the predictive nudge, contacts a marketplace seller, syncs a CMMS work order. Everything wired. (Commit fc08c72 unified the dashboard around this gate.)

The Tester is the standing rule for testing changes. Project memory states explicitly: always test changes through the WorkHive Tester (its 5 gates), never raw `file://`. Coverage is enforced by `validate_tester_coverage.py`: every LIVE_TOOL_PAGE must be in the PUBLIC_PAGES list and in all four flow PAGES lists. The May 2026 baseline is 5 of 5 PASS.

The Tester also runs:
- **Visual regression.** Pixel-diff each page against a saved baseline (commit 423c238).
- **Performance budget flow.** Page load timings against fixed budgets (commit 7f19bfe).
- **Production fixes log.** Real production bugs found via the Tester land in `PRODUCTION_FIXES.md` at the project root, with a template and a Flask viewer at `/findings`.
- **In-app workflow guides.** Per-section help blocks added on May 4 (commit e01f8be) so the Tester is self-explanatory to a new operator.
- **9-place registration wizard.** Extended on May 4 (commit a4e3f1f) to seed every place the platform expects a hive to be wired.

The Tester replaces `platform-health.html` as the active dev-tooling surface. New testing features go into the Tester, not the legacy dashboard.

## 28. The Validator Catalog

There are 70 validators registered in the Guardian as of May 9, 2026, up from 51 on May 1. Below is a topic-grouped overview. The May 9 additions are `validate_reset_coverage.py` (every migration table is in `reset.py` so the Tester can scrub state cleanly) plus `validate_canonical_sources.py` is on the roadmap from the audit doc.

**Engineering Calculator suite (run via `run_all_checks.py`):**
- Layer 1: Schema and field validators (`validate_schema.py`, `validate_fields.py`, `validate_input_guards.py`).
- Layer 2a: Renderer validators (`validate_renderers.py`, `validate_xss.py`, `validate_drawings.py`, `validate_diagram_inputs.py`).
- Layer 2b: BOM and SOW (`validate_bom_sow.py`).
- Layer 3: Live integration through `validate_analytics_live.py` and direct edge-function calls.

**Platform-wide validators:**
- `validate_edge_config.py`: every `supabase/functions/` directory has an entry in `config.toml` with explicit `verify_jwt`. Catches the silent JWT default that produced an analytics 500 in April 2026.
- `validate_cross_page.py`: cross-page inserts carry every required column. Found the missing `qty_after` column on the logbook-to-inventory_transactions insert in April 2026.
- `validate_dom_refs.py`: every `getElementById` has a null guard. Skips template-literal IDs.
- `validate_hive.py`, `validate_hive_state_consistency.py`, `validate_inventory.py`, `validate_inventory_integrity.py`, `validate_logbook.py`, `validate_logbook_consistency.py`, `validate_pm.py`, `validate_skillmatrix.py`, `validate_assistant.py`, `validate_analytics.py`, `validate_report_sender.py`: page-specific validators, each enumerated in Part I.
- `validate_integration_security.py`: 9 checks across CORS, JWT, deploy script coverage. Flags the dynamic CORS pattern that allows wildcard origin echoing.

**New module validators (May 2026):**
- `validate_marketplace.py`: 14 checks across schema, edge fn security, UI gates, money flow.
- `validate_project_manager.py`: schema, wizard, CPM contract, auto-link, print path.
- `validate_cmms_contracts.py`, `validate_cmms_reconciliation.py`: CMMS bridge contract and reconciliation guards.
- `validate_ml.py`: model contract, score range, feature freshness, retrain trigger gates.
- `validate_pattern_alerts.py`: trend-break detection on risk score curves.
- `validate_realtime_publication.py`: every realtime-subscribed table is in `supabase_realtime` publication.
- `validate_soft_delete.py`: REPLICA IDENTITY rule for DELETE realtime filters.
- `validate_auto_discovery.py`: auto-detects HTML, edge function, validator registration gaps. 3 of 3 PASS baseline.
- `validate_schema_coverage.py`: auto-derives schema from migrations; checks every `db.from().select()` references a real table and column. May 9 update teaches it to recognise CREATE VIEW + CREATE OR REPLACE [MATERIALIZED] VIEW so views skip column verification.
- `validate_schema_drift.py`: complementary check against the live database schema.
- `validate_tester_coverage.py`: enforces that every LIVE_TOOL_PAGE is wired into the WorkHive Tester's PUBLIC_PAGES and four flow PAGES.
- `validate_reset_coverage.py` (May 9): every table in any migration is wired into `reset.py` so the Tester can scrub state cleanly. Caught 25 missed tables on first run.
- `validate_asset_brain.py` (May 8): 24 checks across 6 layers covering Asset Brain + Shift Brain (schema, RLS, realtime publication, backfill correctness, edge function rate-limit and hive scoping, supervisor-write policy, parallel sub-agents).

**Crash-prevention validators:**
- `validate_mobile.py`: `will-change: filter` mobile override and `body { animation }` prefers-reduced-motion override.
- `validate_performance.py`: `body { animation }` animationend safety guard.

**Compliance and governance:**
- `validate_compliance.py`, `validate_data_governance.py`, `validate_governance.py`, `validate_knowledge_freshness.py`, `validate_observability.py`, `validate_sso_readiness.py`, `validate_tenant_boundary.py`.

**AI surface validators:**
- `validate_ai_attribution.py`, `validate_ai_context.py`, `validate_ai_data_pipeline.py`, `validate_ai_regression.py`, `validate_groq_fallback.py`, `validate_vector_schema.py`, `validate_context_window.py`.

**Content and SEO:**
- `validate_content_quality.py`, `validate_seo.py`, `validate_accessibility.py`.

**Catalogue and registry:**
- `validate_catalog_scope.py`, `validate_nav_registry.py`, `validate_idempotency.py`, `validate_timers.py`, `validate_data_quality.py`, `validate_iot_protocols.py`, `validate_predictive.py`, `validate_pwa.py`, `validate_notifications.py`, `validate_community.py`, `validate_digital_twin.py`, `validate_integration.py`, `validate_edge_contracts.py`.

The full registry is in Appendix D.

## 29. The Validation Workflow

The standing order, captured in project memory:
1. Run the relevant API or domain validation first.
2. Apply fixes.
3. Run `validate_codebase_integrity` (the cross-page architecture audit) on the changed page and its dependencies.
4. Run the QA skill on the changed page and the affected pages.
5. Run the WorkHive Tester's relevant gate (smoke for a UI tweak, CRUD for a data-write change, cross-page for a flow change, mega for anything that crosses three or more modules).

For a UI bug, that order is enough. For a deploy, the Guardian runs a full sweep. For an engineering calc change, `run_all_checks.py` is the precondition before a UI spot check.

A separate review-and-QA rule: before a fix lands, the agent produces a ripple-effect map (with manual validation steps) and waits for user approval. The reasoning, in project memory: a fix that looks contained often is not, and a 60-second ripple map is cheaper than a regression.

## 30. The Commit and Deploy Workflow

The rule is explicit and is one of the most-cited entries in project memory: never commit and push directly. The order is:
1. Leave changes uncommitted.
2. Run `python run_platform_checks.py --fast`.
3. Fix all FAILs.
4. Commit with a message that explains the why, not the what.
5. Push.

For deploys that touch the Supabase edge functions, the workaround for the `&` in the parent folder name applies: run `subst Z:` first to map the project tree to a clean drive letter, then run `.\deploy-functions.ps1` from there. Without the subst, `npx supabase deploy` breaks on the ampersand.

When a new page, edge function, validator, or table lands, project memory enforces a registration checklist. Missing any of these will trip the Guardian on the next run:
- Validators' `LIVE_PAGES` and `TARGET_PAGES` constants.
- `floating-ai.js` page registry.
- `assistant.html` PLATFORM TOOLS list.
- `nav-hub.js` TOOLS array (unless the page is on the retired list).
- `supabase/config.toml` `verify_jwt` entry for every new edge function.
- WorkHive Tester PUBLIC_PAGES and four flow PAGES (enforced by `validate_tester_coverage.py`).

`validate_auto_discovery.py` automates most of the checklist; if a new file ships without registering, the validator says so on the next Guardian run.

## 31. Standing Rules of Engagement

These are the project's house rules, codified in project memory. They are not advice; they are inputs to every session.

**Style.**
- No em dashes. Use colons, commas, parentheses, or restructure.
- Default to no comments in code. Write a comment only when the why is non-obvious.
- Brief responses. The user can read the diff.
- PowerShell scripts at the project root must be pure ASCII.
- No TypeScript-only syntax in HTML inline JavaScript.

**Engineering.**
- The Performance Standing Rule: every code change is checked for JS and DOM performance issues before it ships.
- Responsive design: every UI change is verified on desktop and mobile before "done."
- Skill-First: read skills before writing code.
- Self-Improvement: write back to skills after.
- Validation order: API, fixes, codebase integrity, QA, Tester.
- Commit workflow: validate, then commit, then push.
- Test through the WorkHive Tester (5 gates), not raw `file://`.

**Architecture.**
- WorkHive is for every worker, field to management.
- Three pages are retired and may not re-enter the nav: `checklist.html`, `parts-tracker.html`, `platform-health.html` (superseded by the WorkHive Tester).
- The Day Planner is already built. It is not a future feature.
- RLS is on. The Supabase Auth migration is deferred but planned.
- The B2 weekly digest is built but waits on Resend domain verification.
- The marketplace is FREE and contact-only by design (Stripe removed entirely 2026-06-30); never propose adding payments, checkout, escrow, or Stripe — the buyer action is the Contact-Seller inquiry.
- iOS form inputs render at 16px or larger to avoid Safari auto-zoom.

---

# Part III. Operating the System

## 32. Daily Loop

A day on the platform, from the agent's point of view:
1. Read the user's request.
2. Identify the domains the task touches. Read the relevant skill files.
3. Identify the workflow that applies (or ask the user if none does).
4. Pick the tools the workflow calls for. Run them in order.
5. Validate as you go: page-specific validator first, codebase-integrity after, QA on the affected pages, Tester gate where applicable.
6. Run `run_platform_checks.py --fast` before commit.
7. Commit with a message that explains the why.
8. Push only after the user has seen the diff or explicitly authorized the push.
9. Run the Self-Improvement Loop. Update skill files. Update workflows.

## 33. Building a New Feature End to End

Take "add a new engineering calc type for variable-frequency drives" as the worked example.

1. Read the Frontend, QA, Maintenance Expert, AI Engineer, and Standards Validator skill files.
2. Cross-reference the calc formulas against IEC 61800 (the standard for adjustable speed electrical power drive systems). Run a web search to confirm the live standard text. Capture the citation in the calc's metadata.
3. Add the calc type to `engineering-design.html`: schema entry, field definitions, render function (with `const e = escHtml` at the top), diagram emitter (using the IEC 60617 symbols from `drawing-symbols.js`), BOM and SOW derivation.
4. Add the matching prompt to `engineering-calc-agent` and `engineering-bom-sow` so the natural-language entry path covers the new calc.
5. Run `python run_all_checks.py --fast`. Fix every FAIL.
6. Run `python run_platform_checks.py --fast`. Fix every FAIL.
7. Run the WorkHive Tester's smoke gate and CRUD gate on the engineering-design page.
8. Spot-check the UI: enter a sample case, verify the report, BOM, SOW, and diagram look right.
9. Commit. Update the Frontend, QA, and Maintenance Expert skills with what you learned (the new calc's quirks, the standard reference, the BOM and SOW sync points specific to this calc).
10. Push.

## 34. Fixing a Bug End to End

Take "the inventory page does not render the qty_after column on a transaction created from the logbook" as the worked example. (This is a real bug from April 2026.)

1. Read the QA, Frontend, Logbook Validator, and Inventory Validator skill files.
2. Reproduce. Confirm the bug. Confirm it does not happen on a transaction created directly on the inventory page.
3. Produce a ripple-effect map: every place in the codebase that writes to `inventory_transactions`, every renderer that reads `qty_after`, every validator that should have caught this.
4. Wait for the user's approval on the ripple map.
5. Fix the cross-page insert in the logbook handler to include `qty_after`.
6. Add a check to `validate_cross_page.py` so the same omission is caught on the next change.
7. Run `python validate_cross_page.py`. Confirm green.
8. Run `python run_platform_checks.py --fast`. Confirm green.
9. Run the WorkHive Tester's cross-page gate. Confirm the logbook-to-inventory deduction writes a complete row.
10. Commit with a message that explains the why ("logbook deduction was writing inventory_transactions without qty_after; renderer expected qty_after; cross_page validator extended to catch the missing column").
11. Update the Logbook Validator and Cross-Page Flow Validator skill files. The lesson is "every cross-page insert must mirror the schema of the canonical insert path." Push.

## 35. What Goes Wrong and How to Recover

**A validator regresses (Guardian exit 2).** Top priority. The check used to pass; something in the latest change broke it. Read the validator's report JSON, identify the failing check, fix it, re-run. Do not commit until green.

**The Skill-First Rule was skipped.** A bug ships that a skill would have caught. The fix is two-step: fix the bug, then run the Self-Improvement Loop with double weight on whichever skill should have caught it. Add a checklist item that names the bug. The next session will catch it.

**Edge function deploy fails.** Almost always one of three things: the `&` in the parent folder name (use `subst Z:`), a missing `config.toml` entry (`validate_edge_config.py` will say so), or a missing environment variable (the deploy script lists the required ones at the top). The `getCorsHeaders` unification (commit 78eeb91) closed a fourth class of failure where dynamic CORS origin echoing across functions had drifted.

**RLS denies a query that should succeed.** The auth_uid is null (the user is on the worker-name fallback) and the policy is checking `auth.uid()`. Two paths: backfill the auth_uid, or extend the policy to accept the worker-name path. Memory entry on the Supabase Auth migration captures the long-term plan.

**The marketplace is contact-only.** There is no payment step at all (Stripe removed entirely 2026-06-30) — sellers connect with buyers through Messenger or the inquiry template, and arrange anything else off-platform. The platform admin sees pending listings/sellers in `marketplace-admin.html` and can approve, verify KYB/certs, or escalate.

**A CMMS sync row is stuck.** The audit log in `cmms_audit_log` has the payload, the response, and the failure reason. The integrations page renders the log inline. Re-run from the page or queue for manual review.

**A predictive risk score looks wrong.** Check `failure_signatures` for the matched signature; check `asset_risk_scores` for the score history; trigger `trigger-ml-retrain` if a calibration change is needed.

**A Tester gate fails on a page that was untouched.** Run the visual regression baseline check first. A stale baseline (e.g. a brand color tweak that was not regenerated) is the most common cause; if real, treat as a regression.

## 36. The Road Ahead

Honest list of what is built, what is partial, and what is planned.

**Built and live (May 9, 2026):**
- All daily-work pages (logbook with work-order sign-off and the new Phase E.4 wo_state machine, PM scheduler, inventory with staged-reservation visibility, skill matrix, day planner).
- The engineering design calculator across six disciplines, with BOM and SOW.
- The marketplace, end to end, in free contact-only mode (no payments; Stripe removed entirely 2026-06-30).
- The Project Manager with CPM scheduling, advanced scope, risk register, change orders, and lessons-learned indexing.
- The CMMS bridge with sync, push-completion, webhook receive, and audit log.
- The predictive analytics layer with daily risk scoring, failure-signature matching, pattern alerts, and Phase ML-2 Auto-Staging.
- The PH Industrial Intelligence layer with peer benchmarks and the intelligence report.
- The Achievements page with unified badges, streaks, and XP.
- The community module with cross-hive feed.
- The analytics page plus the analytics report PDF.
- Asset Brain (Asset Hub + asset_nodes graph + GraphRAG edge fn + canonical hierarchy).
- Shift Brain (autonomous shift planner with 4 sub-agents + AI briefing).
- Alert Hub (unified cross-source alert feed).
- Global Cmd+K search overlay (lazy-loaded by nav-hub on every page).
- The AI assistant with platform context across every page.
- The Platform Guardian with 70 validators and the closed-loop dashboard.
- The WorkHive Tester with 5 gates and visual regression.

**Built but waiting on a single dependency:**
- (Removed) The marketplace Stripe escrow path was deleted entirely on 2026-06-30 — the marketplace is free + contact-only.
- The B2 weekly digest. Waiting on Resend domain verification.
- The full Supabase Auth migration. Foundation laid; cutover deferred.

**Planned (Phase 2 Guardian and beyond):**
- Phase 2: visual dashboard with trend charts on the Tester (the legacy `platform-health.html` is retired).
- Phase 3: self-learning loop where the Guardian updates skill files automatically when a pattern of failures repeats.
- Phase 4: auto-fix loop where the Guardian opens a backlog item with web-search context when a FAIL persists across three runs.

**Domain expansions on the roadmap:**
- Deeper SAP PM and IBM Maximo connectors (the bridge is live; the per-vendor field-mapping libraries grow as new hives onboard).
- OPC-UA and MQTT IoT protocol bridges for live equipment telemetry.
- Predictive analytics models beyond the current signature-match plus risk-score blend (true time-series forecasts on sensor data).
- Enterprise compliance (ISO 27001, SOC 2 Type II) for the industrial-client tier.
- The community badge trigger latent bug fix (the `handle_community_post_xp` trigger inserts against a column that does not exist; will break in production when any worker hits 10 posts in a hive).

**Canonical Sources initiative (in audit, not yet built):**
The May 9 `CANONICAL_SOURCES_AUDIT.md` identified 20 domain concepts across three tiers (5 in active drift, 9 convergent, 6 already aligned). The plan is to publish a `canonical_sources` registry table, a set of `v_*_truth` views, a `validate_canonical_sources.py` validator, and a one-line agent contract added to every AI agent system prompt. Migration order starts with `v_asset_truth` (unifies 3 asset IDs), `v_risk_truth` (replaces the predictive-page model), and `v_pm_compliance_truth` (kills the 4-way math drift). Roughly 10 sessions of work over the lifetime of the initiative; the registry + validator land first so all subsequent work is provably clean.

The platform is bigger than any one session can hold. The framework is what makes that scale possible.

---

# Appendices

## Appendix A. File and Folder Map

```
Website simple 1st/
├── index.html                       # public homepage
├── hive.html                        # hive selector + role assignment
├── logbook.html                     # digital shift logbook
├── pm-scheduler.html                # PM template library
├── inventory.html                   # parts ledger
├── skillmatrix.html                 # skill matrix
├── dayplanner.html                  # DILO/WILO/MILO/YILO
├── project-manager.html             # capital project planning + CPM
├── project-report.html              # project status PDF
├── engineering-design.html          # calculator across 6 disciplines
├── architecture.html                # platform self-overview
├── symbol-gallery.html              # drawing symbol catalog
├── community.html                   # forum + profiles
├── public-feed.html                 # cross-hive public posts
├── report-sender.html               # handover + digest
├── marketplace.html                 # buyer-facing
├── marketplace-seller.html          # seller dashboard
├── marketplace-seller-profile.html  # public seller profile
├── marketplace-admin.html           # platform admin approval + KYB
├── analytics.html                   # KPIs and trends
├── analytics-report.html            # print-ready analytics PDF
├── predictive.html                  # ML failure prediction + risk
├── ph-intelligence.html             # PH industry benchmarks
├── achievements.html                # gamification surface
├── integrations.html                # CMMS bridge config + audit log
├── asset-hub.html                   # Asset Brain 360 view per asset (with QR scan)
├── shift-brain.html                 # autonomous shift planner (3 windows, 4 sub-agents)
├── alert-hub.html                   # unified alert aggregator
├── assistant.html                   # AI context registry
├── platform-health.html             # legacy Guardian dashboard (retired, archival only)
│
├── utils.js                         # escHtml, hive context, role gate, toast
├── nav-hub.js                       # two-tier nav (v3: 4-col grid, search, Ctrl+K, role-based visibility)
├── search-overlay.js                # Cmd+K global command palette (lazy-loaded by nav-hub.js)
├── floating-ai.js                   # AI pill on every page
├── skill-content.js                 # skill matrix content
├── drawing-symbols.js               # IEC/ISA/NFPA symbol library
├── sw.js                            # service worker (cache v12)
│
├── run_platform_checks.py           # Guardian orchestrator
├── run_all_checks.py                # engineering calc 4-layer suite
├── validate_*.py                    # 70 validators
├── validator_utils.py               # shared validator helpers
├── autofix.py                       # automated fix application
├── improve.py                       # improvement backlog runner
├── learn.py                         # self-learning loop runner
├── revalidate.py                    # incremental revalidation
├── guardian_server.py               # local guardian web server
├── schedule_guardian.py             # scheduled guardian
│
├── supabase/
│   ├── config.toml                  # edge function gates (verify_jwt)
│   ├── migrations/                  # 60 timestamped migrations
│   └── functions/                   # 28 edge functions
│
├── test-data-seeder/                # WorkHive Tester (5-gate battlefield)
│   ├── app.py                       # Flask viewer + dashboard
│   ├── run_tests.py                 # gate runner
│   ├── run_flows.py                 # flow runner
│   ├── flows/                       # named flow modules per page
│   ├── seeders/                     # entity seeders per module
│   ├── mock_cmms/                   # mock SAP/Maximo for CMMS bridge tests
│   └── templates/                   # dashboard HTML templates
│
├── PROJECT_MANAGER_ROADMAP.md       # 7-phase roadmap (Phase 1+ active)
├── MARKETPLACE_GO_LIVE_ROADMAP.md   # 6-phase roadmap (blocked at Phase 1: DTI)
├── PRODUCTION_FIXES.md              # real prod bugs + fixes log
├── CANONICAL_SOURCES_AUDIT.md       # 20-domain truth-scattering audit (May 9)
├── enable_shift_brain_cron.sql      # SUPERSEDED 2026-06-10: shift handover now computes on first open (migration 20260610000005)
│
├── _headers                         # CDN headers
├── manifest.json                    # PWA manifest
├── sitemap.xml                      # SEO
├── deploy-functions.ps1             # Windows deploy with subst workaround
└── platform_health.json             # latest Guardian run
    platform_baseline.json           # last all-green snapshot
```

## Appendix B. Supabase Migrations Timeline

The order in which the schema came into being.

```
20260420  baseline
20260422  remote_commit                       # first remote-applied migration
20260425  hive_audit_log                      # tenant audit trail
20260425  analytics_indexes_cache             # analytics index set
20260425  pgvector_semantic_foundation        # vector column + ivfflat index
20260425  scheduled_agents                    # pg_cron-driven agent table
20260426  calc_bom_knowledge                  # calc bom knowledge table
20260428  logbook_failure_consequence         # MTBF/MTTR feeder columns
20260428  logbook_readings                    # equipment readings
20260428  logbook_production_output           # OEE feeder column
20260428  analytics_new_field_indexes
20260428  inventory_transactions_hive_id      # hive scoping fix
20260428  analytics_rpc_functions             # rolled-up KPI views
20260428  equipment_reading_templates
20260429  knowledge_table_governance
20260429  early_access_emails
20260430  community_tables                    # forum + profiles
20260430  community_grants
20260430  community_xp
20260430  worker_profiles
20260430  c3_auth_uid                         # auth.uid foundation
20260430  c3b_auth_uid_remaining
20260430  c4_enforce_rls                      # RLS flip across data tables
20260430  d1_public_posts
20260501  d2_cross_hive_feed
20260501  fix_auth_uid_backfill
20260501  skill_profiles_auth_uid
20260501  missing_table_rls
20260501  remaining_table_rls
20260501  marketplace                         # marketplace core
20260501  marketplace_scale                   # marketplace indexes
20260501  seller_dashboard                    # seller views
20260501  buyer_reviews                       # buyer review table
20260502  seller_messenger                    # Facebook Messenger contact
20260502  marketplace_watchlist               # watchlist table
20260502  marketplace_storage                 # image upload via Storage
20260502  seller_badges                       # multi-tier verification
20260502  listing_view_count
20260502  saved_searches
20260502  platform_admins                     # marketplace admin role
20260504  skill_badges_badge_key              # community badge trigger column
20260504  community_badge_auth_uid
20260505  project_manager                     # project core schema
20260505  project_advanced                    # risk, change orders, multi-role
20260505  project_knowledge                   # vector(384) embedding
20260506  external_sync                       # CMMS bridge connection registry
20260507  failure_signatures                  # signature library w/ pgvector
20260507  integration_auth                    # CMMS auth credentials
20260507  benchmarks                          # PH peer benchmarks
20260507  ph_intelligence                     # intelligence report compilation
20260508  asset_risk_scores                   # daily ML risk scores
20260508  risk_scoring_cron                   # pg_cron schedule
20260508  achievements                        # gamification consolidation
20260508  achievements_rls_fix                # +rls_fix2, disable_rls, force_pgrst_reload, achievements_view
20260508  cmms_audit_log
20260508  asset_brain_foundation              # asset_nodes + asset_edges + asset_embeddings + ai_rate_limits + view
20260508  asset_brain_backfill                # idempotent backfill from pm_assets + legacy assets
20260508  shift_brain_foundation              # shift_plans + supervisor-write RLS + cron-ready (commented)
20260508  work_order_state                    # Phase E.4 wo_state machine on logbook (additive)
20260509  parts_staging                       # Phase ML-2 parts_staging_recommendations + parts_staged_reservations
```

## Appendix C. Edge Function Catalog

```
_shared/                       # shared CORS, auth, retry helpers, getCorsHeaders
ai-orchestrator                # main AI router with prompt caching
analytics-orchestrator         # analytics LLM-on-top summary
intelligence-api               # PH Intelligence query
intelligence-report            # PH Intelligence compile
embed-entry                    # pgvector embed write
semantic-search                # pgvector knn read (Voyage+Jina chain)
engineering-calc-agent         # NL entry to calc payload
engineering-bom-sow            # BOM + SOW from calc payload
project-orchestrator           # project CPM broker to Python service
project-progress               # background project progress nudges
batch-risk-scoring             # daily asset risk score batch
failure-signature-scan         # per-entry failure-pattern match
benchmark-compute              # peer-comparison rollups
parts-staging-recommender      # Phase ML-2 daily Auto-Staging recommender
trigger-ml-retrain             # manual model retrain trigger
cmms-sync                      # pull upstream CMMS work orders
cmms-push-completion           # push WorkHive completion to CMMS
cmms-webhook-receiver          # accept pushed CMMS events
# (the 5 marketplace Stripe edge fns were deleted 2026-06-30 — marketplace is free + contact-only)
asset-brain-query              # GraphRAG retrieval for Asset Hub Ask box (May 8, deployed)
shift-planner-orchestrator     # multi-agent shift planner (May 8, deployed)
scheduled-agents               # pg_cron-driven jobs
send-report-email              # Resend send for digests
voice-report-intent            # voice intent classification
voice-transcribe               # voice to text
voice-logbook-entry            # voice-first logbook capture
```

## Appendix D. Validator Index

The 70 registered validators, alphabetical:

```
validate_accessibility
validate_ai_attribution
validate_ai_context
validate_ai_data_pipeline
validate_ai_regression
validate_analytics
validate_analytics_live
validate_asset_brain
validate_assistant
validate_auto_discovery
validate_bom_sow
validate_catalog_scope
validate_cmms_contracts
validate_cmms_reconciliation
validate_community
validate_compliance
validate_content_quality
validate_context_window
validate_cross_page
validate_data_governance
validate_data_quality
validate_diagram_inputs
validate_digital_twin
validate_dom_refs
validate_drawings
validate_edge_config
validate_edge_contracts
validate_fields
validate_governance
validate_groq_fallback
validate_hive
validate_hive_state_consistency
validate_idempotency
validate_input_guards
validate_integration
validate_integration_security
validate_inventory
validate_inventory_integrity
validate_iot_protocols
validate_knowledge_freshness
validate_logbook
validate_logbook_consistency
validate_marketplace
validate_ml
validate_mobile
validate_nav_registry
validate_notifications
validate_observability
validate_pattern_alerts
validate_performance
validate_pm
validate_predictive
validate_project_manager
validate_pwa
validate_realtime_publication
validate_renderers
validate_report_sender
validate_reset_coverage
validate_schema
validate_schema_coverage
validate_schema_drift
validate_seo
validate_skillmatrix
validate_soft_delete
validate_sso_readiness
validate_tenant_boundary
validate_tester_coverage
validate_timers
validate_vector_schema
validate_xss
```

Each validator owns a single JSON report (`<name>_report.json`) at the project root. The Guardian aggregates them into `platform_health.json`.

## Appendix E. Glossary

- **Hive.** The tenant. Usually a plant, a shift, or a team. The unit of multi-tenancy.
- **Worker.** The default user role inside a hive.
- **Supervisor.** The role that approves things: restocks, listings, joins, promotions, change orders.
- **Manager.** The role that reads cross-hive analytics and signs off on engineering designs and project budgets.
- **Platform Admin.** Cross-hive moderation role for the marketplace and the public feed; recorded in `marketplace_platform_admins`.
- **WAT.** Workflows, Agents, Tools. The three-layer architecture.
- **Skill.** An accumulated lessons file at `~/.claude/skills/<name>/SKILL.md`. Read first, written back after.
- **Guardian.** The master validator orchestrator (`run_platform_checks.py`).
- **Tester.** The WorkHive Tester app at `test-data-seeder/`. The 5-gate end-to-end testing battlefield. Replaces `platform-health.html` as the active dev surface.
- **Mega Gate.** The Tester's unified end-to-end journey across the whole platform.
- **Baseline.** The last all-green snapshot of the Guardian run. Used for regression detection.
- **Readiness Gate.** Loop 3 of the Guardian: git, deploy, API status.
- **MTBF, MTTR, OEE.** Mean Time Between Failures, Mean Time To Repair, Overall Equipment Effectiveness. The three core maintenance KPIs the analytics page rolls up.
- **CPM.** Critical Path Method. The scheduling algorithm in the Project Manager, computed by `networkx` on the Python analytics API.
- **BOM, SOW.** Bill of Materials, Scope of Work. The dual artifacts the engineering calculator emits.
- **DILO, WILO, MILO, YILO.** Day, Week, Month, Year In the Life Of. The four time-block modes of the day planner.
- **KYB.** Know Your Business. The seller-verification step for the marketplace (now a trust/badge signal only — admin-verified `kyb_verified`; no longer tied to any payment onboarding since Stripe was removed 2026-06-30).
- **DTI.** Department of Trade and Industry (Philippines). Seller registration is a trust signal; it is no longer a precondition for anything (the marketplace is free + contact-only, no payment path to gate).
- **LOTO.** Lock Out, Tag Out. The isolation procedure detected by regex in shift handover reports.
- **PWA.** Progressive Web App. The platform installs to the home screen on iOS and Android via `sw.js` and `manifest.json`.
- **RLS.** Postgres Row Level Security. The mechanism that scopes hive data to its tenant.
- **pgvector.** The Postgres extension for embedding storage and KNN search. Foundation of the AI assistant's retrieval and the failure-signature library.
- **PH Intelligence.** The peer-comparison and benchmark layer calibrated to Philippine industrial conditions.
- **CMMS.** Computerized Maintenance Management System. The upstream system class (SAP PM, IBM Maximo, etc.) that the integrations bridge connects to.
- **Auto-Staging.** Phase ML-2: predictive parts pre-staging. When an asset crosses the 0.7 risk floor, `parts-staging-recommender` proposes parts to reserve from inventory based on historical fix patterns. Worker accepts -> reservation holds inventory until the actual repair logbook entry closes.
- **wo_state.** Phase E.4 work-order state machine on logbook (requested -> approved -> assigned -> in_progress -> completed -> verified, with rejected and re-open branches). Additive columns; null = legacy entry.
- **Alert Hub.** Unified alert aggregator at `alert-hub.html`; pulls risk, PM, stock, pattern, and automation alerts into one chronological feed.
- **Canonical Source.** A single view, table, or RPC declared as the authoritative answer for a domain concept. Listed in `canonical_sources` registry. AI agents read from canonicals first per the agent contract.

---

End of book. Version 2026-05-09.
