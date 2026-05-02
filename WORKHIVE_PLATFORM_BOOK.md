# WorkHive: The Platform and the Framework

A complete reference to the platform you have built (WorkHive) and the framework you build it with (WAT + Skill-First + Platform Guardian).

Version: 2026-05-01. Author: Ian Beronio. Generated from the live codebase, the Supabase schema, the validator registry, and the project's `CLAUDE.md` standing instructions.

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
11. The Marketplace
12. Community and Public Feed
13. Analytics, Reporting, and the Day Planner
14. The AI Assistant Layer
15. Tech Stack and Hosting

**Part II. The Framework: WAT, Skill-First, Guardian**
16. Why a Framework at All
17. WAT: Workflows, Agents, Tools
18. The Skill-First Rule
19. The Full Skill Roster
20. The Self-Improvement Loop
21. The Platform Guardian
22. The Validator Catalog
23. The Validation Workflow
24. The Commit and Deploy Workflow
25. Standing Rules of Engagement

**Part III. Operating the System**
26. Daily Loop
27. Building a New Feature End to End
28. Fixing a Bug End to End
29. What Goes Wrong and How to Recover
30. The Road Ahead

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

WorkHive's promise is that you can walk into a small or mid-size plant on Day 1 and have a real digital logbook, PM checklist, inventory ledger, skill matrix, and AI work assistant working for you, with no procurement cycle, no IT project, no per-seat license. It is free at the worker tier because the value compounds only when the whole crew is on it.

The positioning rule, written into project memory, is explicit: WorkHive is for every worker, from field to management, not technicians only. Every UI choice, every tutorial, and every piece of marketing copy lives or dies by that rule.

The platform is bilingual at the level of vocabulary (Tagalog and English) and Filipino at the level of practice. The defaults assume Philippine norms: ISO 8528-1 generator sets, IEC 60617 single-line diagrams, NFPA 13 suppression layouts, ISA-5.1 P&IDs, IESNA lux levels for shop floor lighting, ASHRAE comfort bands tuned to local climate, and unit conventions familiar to a Filipino engineering shop.

## 2. The User Map: Field to Management

WorkHive's user model is not "an account." It is a worker placed inside a hive (the plant or the team), with a role that defines what they can see and do.

**Worker tier (default).** A technician, operator, or maintenance staff member. Reads and writes logbook entries, runs PM checklists, draws parts from inventory, takes skill matrix assessments, and uses the AI assistant for on-shift help. Sees the data of their own hive and nothing else.

**Supervisor tier.** A shift supervisor or maintenance lead. Approves things: inventory restocks, PM completions, marketplace listings, hive joins, skill matrix promotions. Reads the analytics for their hive. Triggers shift handover reports. Sends end-of-shift digests.

**Manager tier.** A plant manager or engineering manager. Reads cross-shift trends (MTBF, MTTR, OEE), reviews the predictive analytics, signs off on engineering designs and BOM/SOWs, and holds the keys to integrations with SAP PM, IBM Maximo, or whatever CMMS is in place.

**Public tier.** Any visitor to `workhiveph.com`. Lands on the public homepage, can read public posts in the cross-hive feed, browse the marketplace, and explore the engineering design calculator without joining a hive.

The hive is the unit of multi-tenancy. Two plants on the same instance never see each other's logbook, inventory, or analytics. Cross-hive features (the public feed, the marketplace, the community forum) are explicit, opt-in, and scoped at the row level by Postgres Row Level Security.

## 3. The Module Map

Below is the live page roster, grouped by what the worker is trying to do. Every page is a single self-contained HTML file with its own CSS and JavaScript, plus the shared utilities in `utils.js`, `nav-hub.js`, `floating-ai.js`, `skill-content.js`, and `drawing-symbols.js`.

**Identity and entry**
- `index.html`: public homepage, hero, social proof, install-as-PWA hook
- `hive.html`: hive selector, join-by-code, role assignment, supervisor approval queue

**Daily work**
- `logbook.html`: digital shift logbook, offline queue, edit-in-place, parts deduction guard
- `pm-scheduler.html`: PM template library, due dates, completion logging, category mapping
- `inventory.html`: parts ledger, use/restock workflow with approval, transaction log
- `skillmatrix.html`: discipline-by-level matrix, badges, cooldown logic, pass thresholds
- `dayplanner.html`: DILO/WILO/MILO/YILO time blocks for personal planning

**Knowledge and design**
- `engineering-design.html`: parametric calculator across six engineering disciplines
- `architecture.html`: house-style overview of the platform's own architecture
- `symbol-gallery.html`: every drawing symbol the calculator can emit, with standard refs

**Communication**
- `community.html`: forum, profiles, gamification, weekly digest (deferred until domain verified)
- `public-feed.html`: cross-hive public posts, opt-in only
- `report-sender.html`: shift handover and end-of-day digest, multi-channel (email, PDF)

**Marketplace**
- `marketplace.html`: buyer-facing listings (parts, training, jobs)
- `marketplace-seller.html`: seller dashboard with listings, inquiries, orders, earnings
- `marketplace-admin.html`: supervisor approval queue, KYB verification

**Operations and oversight**
- `analytics.html`: cross-hive KPIs, MTBF/MTTR/OEE, trend charts
- `assistant.html`: AI assistant landing page with platform context registry
- `platform-health.html`: live Guardian dashboard

Two pages are explicitly retired and must never re-appear in the nav registry: `checklist.html` and `parts-tracker.html`. They were earlier prototypes that got absorbed into `pm-scheduler.html` and `inventory.html` respectively.

## 4. Anatomy of a Page

Every WorkHive page follows the same skeleton, by convention rather than framework. There is no React, no Vue, no build step. It is vanilla HTML, vanilla CSS (with Tailwind via CDN for utility classes), and vanilla JavaScript.

A page does five things in this order:
1. Loads `utils.js` first, which wires the shared escHtml helper, hive context loader, role gate, and toast plumbing.
2. Loads `nav-hub.js`, which renders the two-tier nav (quick-access row of the four most-recent tools, plus the collapsible All Tools grid).
3. Loads page-local styles inline in `<style>` blocks, scoped by class.
4. Wires its own DOMContentLoaded handler, which reads the hive context, fetches Supabase rows, renders the UI, and subscribes to Realtime channels.
5. Loads `floating-ai.js` last, which mounts the AI assistant pill that follows the user across the platform.

The convention `const e = escHtml` at the top of every renderer is non-negotiable: the QA validator scans for it on every render function. The same QA pass checks that every `getElementById` call has a null guard, that every Realtime subscription has a matching teardown, and that every `hive_id` is included in every Supabase insert.

## 5. The Hive: Multi-Tenant Core

The hive is the tenant. Tables that hold worker data carry a `hive_id` column and are gated by Row Level Security policies that compare `hive_id` to the caller's membership. The migration `20260430000006_c4_enforce_rls.sql` flipped RLS on across the data tables, and the follow-on migrations (`20260501000003_missing_table_rls.sql`, `20260501000004_remaining_table_rls.sql`) closed the gaps.

A worker joins a hive by code. The supervisor approves. The membership row carries the role. Every page query and every Realtime subscription is scoped by the hive context loaded from local storage at boot. The Hive Validator (`validate_hive.py`) checks four things on every commit: that Realtime channels cover the page's writeable tables, that every insert carries `hive_id`, that the approval flow handles both `approved` and `rejected` states, and that every channel has a teardown call on page unload.

A standing decision in project memory: a full Supabase Auth migration is planned but deferred. The current model uses worker name plus hive code; the planned migration will introduce `auth.uid()` and remove the cache-clear pain when a worker rejoins on a fresh device. The `c3_auth_uid.sql` and `c3b_auth_uid_remaining.sql` migrations have already laid the foundation by adding `auth_uid` columns and policies; the cutover is a future job.

## 6. The Logbook

The logbook is the most-used page on the platform. It is the modern replacement for the bound paper book on the maintenance shop floor.

What it does:
- Capture shift entries with category (electrical, mechanical, instrumentation, utilities, civil, HVAC), severity, equipment tag, free-text narrative, photos, and the worker's signature.
- Deduct parts from inventory inline, with a guard: an entry that says "replaced 2x V-belt" actually decrements stock and writes a row to `inventory_transactions`.
- Queue offline. The page persists drafts in IndexedDB; when connectivity returns, it flushes the queue.
- Edit in place. A worker who realizes they wrote the wrong tag taps the entry and corrects it; the form is the same form used to add, not a new modal.
- Tag a failure consequence (downtime, rework, safety) and a closed_at timestamp once the issue is resolved. These two columns feed MTBF and MTTR in analytics.

The logbook validator (`validate_logbook.py`) defends three rules: every entry has a `closed_at` either null or in the future of `created_at`; every parts deduction has a matching `inventory_transactions` row; and the PM-category-to-log-category mapping does not write a log under a category that does not exist (a real bug found in April 2026 where HVAC, Utilities, and Civil PMs were mapping to invalid log categories).

## 7. The PM Scheduler

The PM scheduler holds the preventive maintenance template library. A template defines: equipment class, frequency in days, checklist steps, expected duration, required parts, and required skills. The page renders the upcoming and overdue PMs for the hive, and a worker checks them off through the same form the logbook uses.

The PM Validator (`validate_pm.py`) runs five checks: that every template's `freq_days` matches the canonical FREQ_DAYS table; that template categories cover every supported discipline; that the PM-to-logbook category mapping resolves to a real logbook category; that the payload schema matches the columns expected by the renderer; and that midnight is normalized in UTC so a Manila-timezone PM does not skip a day on the boundary.

## 8. The Inventory

The inventory is the parts ledger. Workers draw parts; supervisors approve restocks. Every transaction writes to `inventory_transactions` with a `qty_after` column (the running balance after the transaction), so the page never has to recompute history to render a balance.

The Inventory Validator (`validate_inventory.py`) covers six guards: every transaction has a non-null `qty_after`; every transaction is hive-scoped; the use and restock paths emit transactions of the correct sign; the approval workflow handles both `approved` and `rejected`; the page never permits a negative balance overflow; and the cross-page flow into the logbook deduction is consistent (the bug that surfaced in April 2026 was a missing `qty_after` column on the cross-page insert from logbook into inventory_transactions).

## 9. The Skill Matrix

The skill matrix tracks who can do what, by discipline and by level. A worker takes an assessment; on pass, a badge unlocks; cooldown logic prevents re-taking until a wait period elapses. The matrix is what powers job listings on the marketplace ("must hold Level 2 Electrical") and the PM eligibility filter ("only Level 3 Mechanical can sign off this PM").

The Skill Matrix Validator (`validate_skillmatrix.py`) checks that disciplines and levels match the canonical constants, that the badge conflict key prevents two badges with the same identity, that cooldown logic respects the configured wait, that the pass threshold is enforced, and that the content coverage matches the disciplines registered on the page.

## 10. The Engineering Design Calculator

This page is one of the larger pieces of work in the platform. It is a parametric calculator across six engineering disciplines: electrical, mechanical, instrumentation and controls, plumbing and fire suppression, lighting, and HVAC. For each calc type, the worker enters parameters; the page validates the inputs, runs the calculation, generates a single-line diagram or schematic, emits a Bill of Materials and a Scope of Work, and renders a print-ready report.

The calculator is governed by a four-layer validator suite (`run_all_checks.py`):
- **Layer 1: Schema and field validators.** Inputs match the declared schema; required fields are present.
- **Layer 2a: Renderer validators.** Every `renderXxxReport` function declares `const e = escHtml` at the top, every diagram input is sanitized, every calc emits the BOM/SOW dual artifact, and every print path uses the validated print popup pattern (margin:0, body padding, color override).
- **Layer 2b: BOM/SOW mismatch validators.** The BOM and the SOW are derived from the same calc payload, but they read it through two different render paths. Any drift between the parts in BOM and the activities in SOW is a fail.
- **Layer 3: Live integration test.** Calls the deployed `engineering-calc-agent` and `engineering-bom-sow` edge functions with a representative payload and verifies the response shape.

A standing practice from project memory: the validator suite must run on every Python, renderer, or BOM/SOW change, and zero FAIL is the precondition for a UI spot-check. The Standards Validator additionally cross-references every formula against the live web on first introduction (IEC, NFPA, IESNA, ISO, ASHRAE), so a calc cannot ship with a formula that does not match the cited standard.

## 11. The Marketplace

The marketplace was the most recent module to land (commits e2b0e57, 739f235, 1fab68f, d057c27, 5931cd8 in the May 1 batch). It is a Stripe-escrow marketplace for three product types:
- **Parts.** Surplus spares, OEM components, refurbished tools.
- **Training.** Skill-aligned courses sold by accredited trainers.
- **Jobs.** Short-term industrial gigs, scoped to a hive's region and skill matrix.

The flow:
1. A seller lists. The hive supervisor approves the listing (KYB step, with auto-verification on Stripe Connect return).
2. A buyer purchases through Stripe Checkout. Funds are escrowed.
3. The seller fulfills (ship the part, deliver the training, complete the gig).
4. The buyer marks the order released; the buyer also submits a review.
5. Stripe transfers the funds to the seller's connected account.

The page set:
- `marketplace.html`: buyer-facing browse, search, filter, checkout.
- `marketplace-seller.html`: seller dashboard with listings, inquiries, orders, earnings.
- `marketplace-admin.html`: supervisor listing approval queue plus KYB verification.

The edge functions that drive it:
- `marketplace-checkout`: creates the Stripe Checkout session.
- `marketplace-connect-onboard`: initiates Stripe Connect onboarding for a seller.
- `marketplace-connect-status`: polls Stripe for KYB completion.
- `marketplace-release`: releases escrowed funds on buyer confirmation.
- `marketplace-webhook`: receives Stripe events and reconciles state.

The migrations land the schema in three steps: `20260501000005_marketplace.sql` (core tables), `20260501000006_marketplace_scale.sql` (indexes and pagination support), and `20260501000007_seller_dashboard.sql` (denormalized views for the seller page). `20260501000008_buyer_reviews.sql` completes the loop with the review submission table and trigger.

## 12. Community and Public Feed

The community module is a forum-and-profile layer for cross-hive participation. Workers earn XP, unlock badges, and post questions or how-tos that can be seen by other hives if marked public. The migration sequence (`20260430000000_community_tables.sql` through `20260501000000_d2_cross_hive_feed.sql`) builds the schema in seven steps, including the public-post visibility rules and the cross-hive feed query path.

**Capability matrix as of May 2026** (after the analyse-and-improve session): posts with categories (general / safety / technical / announcement); reactions (👍 🔧 🔥 👀) with INSERT + DELETE realtime sync across devices; threads with replies; supervisor mod queue; pin / flag / public / soft-delete actions; **worker report flow** with reason picker (harassment / unsafe / spam / other) plus optional details, captured in the audit log; **soft-delete with 5s undo** via `community_posts.deleted_at` and a parallel `showUndoToast` component; **edit post** via `edited_at` column with an "edited" badge in the timestamp; **`@mentions`** with autocomplete dropdown, longest-first parser, and realtime "X mentioned you" notifications; **deep-link to thread** (`?post=<uuid>`) with copy-link button and hive-scope guard on cross-hive links; **composer "Make public" toggle** (supervisor-only, auto-locked for announcements); **cross-hive Global tab** powered by a separate `community-global-feed` realtime channel filtered by `public=eq.true`; **community guidelines** collapsible inside the composer; **welcome card** on empty state with role-aware tips; **full WCAG 2.2 AA accessibility kit** (focus trap on every sheet, Escape closes any open sheet, `:focus-visible` rings, `role="status" aria-live="polite"` on the connection chip, `aria-pressed` and reaction-count in `aria-label` on toggle buttons). **Dual-layer rate limit**: client-side cooldown (5s posts, 3s replies) for UX, plus Postgres `BEFORE INSERT` triggers `trg_community_post_rate_limit` (3 posts / 30s) and `trg_community_reply_rate_limit` (5 replies / 15s) for actual abuse prevention.

The session also surfaced two non-obvious failure modes that are now standing rules: (a) any new realtime-subscribed table requires `ALTER PUBLICATION supabase_realtime ADD TABLE <name>` — without it, listeners are silently dead, hidden by optimistic UI on the originating client; (b) Postgres default `REPLICA IDENTITY = PK` only, so DELETE realtime filters on non-PK columns silently drop every event. Both are documented in the multitenant-engineer, realtime-engineer, architect, devops, and qa-tester skills, and the new-feature registration checklist in memory.

The B2 weekly digest (a Resend-powered email summary of community activity) is built but deferred. Project memory makes the rule clear: do not enable digest sending until the sending domain is verified at Resend. The full scope of the digest is documented in the deferred memory entry.

## 13. Analytics, Reporting, and the Day Planner

**Analytics (`analytics.html`).** Cross-shift KPIs: MTBF, MTTR, OEE, parts spend, PM compliance, top fault classes. The page is read-only for workers and supervisors, with a manager-tier toggle for cross-hive comparisons. The Analytics Validator (`validate_analytics.py`) covers 22 checks across three layers: HTML structure, the `analytics-orchestrator` edge function contract, and the Python backend that builds the rolled-up RPC views.

**Report Sender (`report-sender.html`).** End-of-shift handover and end-of-day digest. The validated pattern (per project memory) is the a-f handover structure, calendar-period dates, the print popup pattern (margin:0 plus body padding plus color override), and a regex-based LOTO detection that scans logbook narratives for the standard isolation phrases. 32 checks across four layers (page structure, UI, logic, PWA and edge functions).

**Day Planner (`dayplanner.html`).** Personal planning page with four time-block modes: DILO (Day in the Life Of), WILO (Week), MILO (Month), YILO (Year). Already shipped; project memory marks it as built so it is not re-treated as a future feature.

## 14. The AI Assistant Layer

A floating AI pill is mounted on every page through `floating-ai.js`. It reads the page context (which page, which hive, which logged-in worker, what is on screen) from a registry maintained in `assistant.html` and calls the `ai-orchestrator` edge function. The orchestrator routes to the right model: Claude Sonnet 4.6 for reasoning-heavy work, Gemini Flash for cheap classification on the free tier, with a Groq fallback for latency-sensitive paths.

There are five edge functions in the AI layer:
- `ai-orchestrator`: the main router, with prompt caching and model selection.
- `analytics-orchestrator`: runs analytics queries with an LLM-on-top summary.
- `engineering-calc-agent`: drives the engineering design calculator's natural-language entry path.
- `engineering-bom-sow`: derives the BOM and SOW from a calc payload.
- `voice-report-intent`, `voice-transcribe`: voice-first capture for shift reports.
- `embed-entry`, `semantic-search`: pgvector-backed retrieval for the knowledge base (`pgvector_semantic_foundation.sql` migration, April 2026).
- `send-report-email`: email send through Resend with the digest payload.
- `scheduled-agents`: pg_cron-driven jobs that wake an agent on a schedule (e.g. weekly digest, daily PM nudge).

The Assistant Validator (`validate_assistant.py`) ensures three things: every page has a context entry in the registry, the PLATFORM TOOLS list is complete, and the disciplines named in the assistant prompt match the disciplines registered in the skill matrix. A bug surfaced in April 2026 where the engineering-design page was missing from the registry and the Skill Matrix disciplines on the assistant did not match the live ones; the validator now catches both.

## 15. Tech Stack and Hosting

**Front end.** Vanilla HTML, CSS, JavaScript. Tailwind via CDN. Poppins as the type face. No build step. Every page is a self-contained file. PWA enabled through `sw.js` and `manifest.json`.

**Back end.** Supabase: Postgres with RLS, Realtime, Edge Functions (Deno), Storage, Auth (in migration). pg_cron for scheduled work. pgvector for semantic search.

**AI.** Claude Sonnet 4.6 as primary. Gemini Flash on the free tier for cheap operations. Groq for latency fallback. Anthropic prompt caching is on for every Claude path.

**Payments.** Stripe Connect (escrow model) for the marketplace.

**Email.** Resend, with the sending domain pending verification before the weekly digest goes live.

**Hosting.** Cloudflare Pages for the static site, Supabase for everything stateful. The `_headers` file at the root sets the security and caching headers; the `sw.js` file is the PWA service worker.

**Local dev.** A peculiarity in project memory: the parent folder name has an `&` character, which breaks `npx supabase deploy`. The standing workaround is to run `subst Z:` first to give the working tree a clean drive letter, then run `.\deploy-functions.ps1` from there.

---

# Part II. The Framework: WAT, Skill-First, Guardian

## 16. Why a Framework at All

The platform is one project. The framework is how it stays buildable as the project grows past the point where any one human (or any one Claude Code session) can hold the whole thing in working memory.

The math is honest. If each step in a multi-step build is 90% accurate, five steps gets you 59% reliability; ten steps gets you 35%. That is the curve that makes ad-hoc AI-driven coding fail at scale. The framework's job is to bend that curve, by separating reasoning (which AI does well) from execution (which deterministic code does perfectly) and by capturing every lesson learned so the next session does not relearn it.

There are three layers of leverage in the framework, and they nest: WAT separates reasoning from execution; Skill-First captures lessons as input to the next reasoning step; the Platform Guardian enforces that the lessons stayed enforced.

## 17. WAT: Workflows, Agents, Tools

WAT stands for Workflows, Agents, Tools. The three layers are clean and the boundary between them is enforced by file location, not by convention.

**Layer 1: Workflows. The instructions.** Markdown SOPs in `workflows/`. Each workflow names an objective, the inputs it needs, the tools it should use, the expected outputs, and the edge cases it has to handle. They are written like a brief to a human teammate. They are the version-controlled, human-readable record of how this work gets done.

**Layer 2: Agents. The decision-maker.** This is the role Claude Code plays. The agent reads the workflow, picks the right tools in the right order, handles failures with judgment, and asks the user when the workflow does not cover an edge case. The agent does not do the work directly. It coordinates.

**Layer 3: Tools. The execution.** Python scripts in `tools/`, plus the Supabase edge functions in `supabase/functions/`. These are the deterministic parts. They make the API call, transform the data, write the file, query the database. Credentials live in `.env`, never in code.

The point of the separation is that a task with five tool calls, each with 99% reliability, gets you 95% reliability end to end. A task where the AI tries to do all five steps directly gets you 59%. The split is the productivity hack.

The agent's job description, written in `CLAUDE.md` as the standing brief: "You sit between what I want (workflows) and what actually gets done (tools). Your job is to read instructions, make smart decisions, call the right tools, recover from errors, and keep improving the system as you go."

## 18. The Skill-First Rule

The Skill-First Rule is not negotiable: before writing any code, fixing any bug, or building any feature, the agent reads the relevant skill files. Skills live at `C:/Users/ILBeronio/.claude/skills/<skill-name>/SKILL.md`. They are not documentation. They are accumulated lessons from past sessions. Ignoring them means repeating mistakes that have already been solved, in front of the same user, on the same code.

The four-step practice:
1. Identify which domains the task touches. A bug in a report renderer touches Frontend and QA. A new calc type touches Frontend, QA, and Maintenance Expert. An edge function deploy touches DevOps and AI Engineer.
2. Read those skill files before writing a single line. One Read call per skill. Scan for sections that match the task: checklist items, anti-patterns, rules.
3. Apply what you find. If QA says "every renderer must declare `const e = escHtml`," check that before writing the renderer, not after. If Frontend says "BOM/SOW has 10 sync points across 2 render functions," that is the task checklist.
4. After the task, update the skills with what you learned. (See the Self-Improvement Loop, below.)

The cost is one Read per skill. The payoff is catching known issues before they become bugs.

## 19. The Full Skill Roster

Skills are partitioned by when they are in scope. Some are checked every session. Some come in when their domain is touched. Some come in only when a domain lesson surfaces.

**Always in scope (every session):**
- **QA.** Test checklist items, edge cases, empty and error states, broken flows.
- **Frontend.** Coding patterns, anti-patterns, state management rules.
- **Performance.** Query efficiency, render bottlenecks, caching patterns.
- **Mobile Maestro.** Touch targets, safe areas, iOS and Android quirks, PWA rules.
- **Security.** XSS vectors, data exposure, auth bypass, injection risks.

**In scope when the domain is touched:**
- Architect, Data Engineer, Multitenant Engineer, Realtime Engineer, Notifications, Analytics Engineer, AI Engineer, DevOps.

**In scope when a domain lesson surfaces:**
- Designer, Maintenance Expert, Knowledge Manager, Community, SEO and Content, TCG Expert (legacy from a sibling project, kept dormant).

There are also platform-specific validator skills, each of which is a wrapper around the matching `validate_*.py` script:
- Codebase Integrity, Cross-Page Flow Validator, Hive Validator, Inventory Validator, Logbook Validator, PM Validator, Skill Matrix Validator, Assistant Validator, Standards Validator, Engineering Calc Validator, Drawing Standards Skill, Platform Guardian.

A standing rule: the Skill-First Rule applies whether the user invoked a skill explicitly with a slash command or not. Every code change reads the skills first. Every code change writes back to the skills after.

## 20. The Self-Improvement Loop

After every skill run, and after any bug fix or refactor or issue resolution (even with no formal skill invocation), the agent runs the Self-Improvement Loop. The rule is non-negotiable, and the reason is captured in project memory: findings that stay only in the session are wasted. Every session leaves all relevant skills smarter, not just the one that was invoked.

The loop is four steps:
1. Review what was discovered or fixed during the session.
2. For each lesson, scan the full skill roster and ask: would this skill have caught or prevented this? One bug often teaches rules that belong in three or four skills at once. Write to all of them, each from its own angle. (A null-pointer crash in a renderer is a Frontend lesson about defensive checks, a QA lesson about empty-state coverage, a Mobile lesson about iOS-specific render order, and a Security lesson about user-input echo. One bug, four skills.)
3. Present proposals as a cross-skill table for one-pass approval, so the user signs off without having to read four edits.
4. Once approved, write to all relevant skill files in one Edit pass.

The compound effect is what makes this loop work. After 100 sessions, the QA skill has 100 checklist items added by past failures, and the next session inherits all 100 for free.

## 21. The Platform Guardian

The Platform Guardian (`run_platform_checks.py`) is the master orchestrator. It runs every validator, checks the readiness gate, and compares the result to the saved baseline. It is the gate before commit, the gate before deploy, the gate before "done."

The Guardian wraps four loops, of which Phase 1 implements two and the rest are on the roadmap:
- **Loop 0: Observation.** Compare to baseline. If a previously passing check now fails, that is a regression and exits with code 2.
- **Loop 1: Retrospection.** Run all validators. Classify failures.
- **Loop 2: Self-Learning.** Auto-update skill files when patterns repeat. (Phase 3.)
- **Loop 3: Readiness Gate.** Git status, deployment status, API status. If git is dirty in a way that should not ship, exit with code 3. (Implemented.)
- **Loop 4: Improvement.** Open a backlog item with web-search context when the same FAIL trips three runs in a row. (Phase 4.)

The exit codes are the contract:
- `0`: all pass. Safe to commit, deploy, or start the next feature.
- `1`: one or more validators failed. Fix before commit.
- `2`: regression detected. The check used to pass; now it does not. Top priority.
- `3`: readiness gate blocked. Git or deploy state is not safe.

The Guardian writes two artifacts every run:
- `platform_health.json`: machine-readable report of the run.
- `platform_baseline.json`: saved when all checks pass. Used for regression detection on the next run.

The dashboard (`platform-health.html`) is a static page that reads `platform_health.json` and renders the green/yellow/red board. It is the always-on view of platform health.

## 22. The Validator Catalog

There are 51 validators registered in the Guardian as of May 2026. Below is a topic-grouped overview.

**Engineering Calculator suite (run via `run_all_checks.py`):**
- Layer 1: Schema and field validators (`validate_schema.py`, `validate_fields.py`, `validate_input_guards.py`).
- Layer 2a: Renderer validators (`validate_renderers.py`, `validate_xss.py`, `validate_drawings.py`, `validate_diagram_inputs.py`).
- Layer 2b: BOM and SOW (`validate_bom_sow.py`).
- Layer 3: Live integration through `validate_analytics_live.py` and direct edge-function calls.

**Platform-wide validators:**
- `validate_edge_config.py`: every `supabase/functions/` directory has an entry in `config.toml` with explicit `verify_jwt`. Catches the silent JWT default that produced an analytics 500 in April 2026.
- `validate_cross_page.py`: cross-page inserts carry every required column. Found the missing `qty_after` column on the logbook-to-inventory_transactions insert in April 2026.
- `validate_dom_refs.py`: every `getElementById` has a null guard. Skips template-literal IDs.
- `validate_hive.py`, `validate_inventory.py`, `validate_logbook.py`, `validate_pm.py`, `validate_skillmatrix.py`, `validate_assistant.py`, `validate_analytics.py`, `validate_report_sender.py`: each enumerated above in Part I.
- `validate_integration_security.py`: 9 checks across CORS, JWT, deploy script coverage. Flags the dynamic CORS pattern that allows wildcard origin echoing.

**Crash-prevention validators (added after a production Safari iOS crash, April 2026):**
- `validate_mobile.py`: `will-change: filter` mobile override and `body { animation }` prefers-reduced-motion override.
- `validate_performance.py`: `body { animation }` animationend safety guard, with `index.html` in the LIVE_PAGES scope.

**Compliance and governance:**
- `validate_compliance.py`, `validate_data_governance.py`, `validate_governance.py`, `validate_knowledge_freshness.py`, `validate_observability.py`, `validate_sso_readiness.py`, `validate_tenant_boundary.py`.

**AI surface validators:**
- `validate_ai_attribution.py`, `validate_ai_context.py`, `validate_ai_data_pipeline.py`, `validate_ai_regression.py`, `validate_groq_fallback.py`, `validate_vector_schema.py`, `validate_context_window.py`.

**Content and SEO:**
- `validate_content_quality.py`, `validate_seo.py`, `validate_accessibility.py`.

**Catalogue and registry:**
- `validate_catalog_scope.py`, `validate_nav_registry.py`, `validate_idempotency.py`, `validate_timers.py`, `validate_data_quality.py`, `validate_iot_protocols.py`, `validate_predictive.py`, `validate_pwa.py`, `validate_notifications.py`, `validate_community.py`, `validate_digital_twin.py`, `validate_integration.py`, `validate_edge_contracts.py`.

The full registry is in Appendix D.

## 23. The Validation Workflow

The standing order, captured in project memory:
1. Run the relevant API or domain validation first.
2. Apply fixes.
3. Run `validate_codebase_integrity` (the cross-page architecture audit) on the changed page and its dependencies.
4. Run the QA skill on the changed page and the affected pages.

For a UI bug, that order is enough. For a deploy, the Guardian runs a full sweep. For an engineering calc change, `run_all_checks.py` is the precondition before a UI spot check.

A separate review-and-QA rule: before a fix lands, the agent produces a ripple-effect map (with manual validation steps) and waits for user approval. The reasoning, in project memory: a fix that looks contained often is not, and a 60-second ripple map is cheaper than a regression.

## 24. The Commit and Deploy Workflow

The rule is explicit and is one of the most-cited entries in project memory: never commit and push directly. The order is:
1. Leave changes uncommitted.
2. Run `python run_platform_checks.py --fast`.
3. Fix all FAILs.
4. Commit with a message that explains the why, not the what.
5. Push.

For deploys that touch the Supabase edge functions, the workaround for the `&` in the parent folder name applies: run `subst Z:` first to map the project tree to a clean drive letter, then run `.\deploy-functions.ps1`. Without the subst, `npx supabase deploy` breaks on the ampersand.

When a new page, edge function, validator, or table lands, project memory enforces a registration checklist. Missing any of these will trip the Guardian on the next run:
- Validators' `LIVE_PAGES` and `TARGET_PAGES` constants.
- `floating-ai.js` page registry.
- `assistant.html` PLATFORM TOOLS list.
- `nav-hub.js` TOOLS array (unless the page is on the retired list).
- `supabase/config.toml` `verify_jwt` entry for every new edge function.
- `platform-health.html` count fields, so the dashboard reflects the new check.

## 25. Standing Rules of Engagement

These are the project's house rules, codified in project memory. They are not advice; they are inputs to every session.

**Style.**
- No em dashes. Use colons, commas, parentheses, or restructure.
- Default to no comments in code. Write a comment only when the why is non-obvious.
- Brief responses. The user can read the diff.

**Engineering.**
- The Performance Standing Rule: every code change is checked for JS and DOM performance issues before it ships.
- Responsive design: every UI change is verified on desktop and mobile before "done."
- Skill-First: read skills before writing code.
- Self-Improvement: write back to skills after.
- Validation order: API, fixes, codebase integrity, QA.
- Commit workflow: validate, then commit, then push.

**Architecture.**
- WorkHive is for every worker, field to management.
- Two pages are retired and may not re-enter the nav: `checklist.html`, `parts-tracker.html`.
- The Day Planner is already built. It is not a future feature.
- RLS is on. The Supabase Auth migration is deferred but planned.
- The B2 weekly digest is built but waits on Resend domain verification.

---

# Part III. Operating the System

## 26. Daily Loop

A day on the platform, from the agent's point of view:
1. Read the user's request.
2. Identify the domains the task touches. Read the relevant skill files.
3. Identify the workflow that applies (or ask the user if none does).
4. Pick the tools the workflow calls for. Run them in order.
5. Validate as you go: page-specific validator first, codebase-integrity after, QA on the affected pages.
6. Run `run_platform_checks.py --fast` before commit.
7. Commit with a message that explains the why.
8. Push only after the user has seen the diff or explicitly authorized the push.
9. Run the Self-Improvement Loop. Update skill files. Update workflows.

## 27. Building a New Feature End to End

Take "add a new engineering calc type for variable-frequency drives" as the worked example.

1. Read the Frontend, QA, Maintenance Expert, AI Engineer, and Standards Validator skill files.
2. Cross-reference the calc formulas against IEC 61800 (the standard for adjustable speed electrical power drive systems). Run a web search to confirm the live standard text. Capture the citation in the calc's metadata.
3. Add the calc type to `engineering-design.html`: schema entry, field definitions, render function (with `const e = escHtml` at the top), diagram emitter (using the IEC 60617 symbols from `drawing-symbols.js`), BOM and SOW derivation.
4. Add the matching prompt to `engineering-calc-agent` and `engineering-bom-sow` so the natural-language entry path covers the new calc.
5. Run `python run_all_checks.py --fast`. Fix every FAIL.
6. Run `python run_platform_checks.py --fast`. Fix every FAIL.
7. Spot-check the UI: enter a sample case, verify the report, BOM, SOW, and diagram look right.
8. Commit. Update the Frontend, QA, and Maintenance Expert skills with what you learned (the new calc's quirks, the standard reference, the BOM and SOW sync points specific to this calc).
9. Push.

## 28. Fixing a Bug End to End

Take "the inventory page does not render the qty_after column on a transaction created from the logbook" as the worked example. (This is a real bug from April 2026.)

1. Read the QA, Frontend, Logbook Validator, and Inventory Validator skill files.
2. Reproduce. Confirm the bug. Confirm it does not happen on a transaction created directly on the inventory page.
3. Produce a ripple-effect map: every place in the codebase that writes to `inventory_transactions`, every renderer that reads `qty_after`, every validator that should have caught this.
4. Wait for the user's approval on the ripple map.
5. Fix the cross-page insert in the logbook handler to include `qty_after`.
6. Add a check to `validate_cross_page.py` so the same omission is caught on the next change.
7. Run `python validate_cross_page.py`. Confirm green.
8. Run `python run_platform_checks.py --fast`. Confirm green.
9. Commit with a message that explains the why ("logbook deduction was writing inventory_transactions without qty_after; renderer expected qty_after; cross_page validator extended to catch the missing column").
10. Update the Logbook Validator and Cross-Page Flow Validator skill files. The lesson is "every cross-page insert must mirror the schema of the canonical insert path." Push.

## 29. What Goes Wrong and How to Recover

**A validator regresses (Guardian exit 2).** Top priority. The check used to pass; something in the latest change broke it. Read the validator's report JSON, identify the failing check, fix it, re-run. Do not commit until green.

**The Skill-First Rule was skipped.** A bug ships that a skill would have caught. The fix is two-step: fix the bug, then run the Self-Improvement Loop with double weight on whichever skill should have caught it. Add a checklist item that names the bug. The next session will catch it.

**Edge function deploy fails.** Almost always one of three things: the `&` in the parent folder name (use `subst Z:`), a missing `config.toml` entry (`validate_edge_config.py` will say so), or a missing environment variable (the deploy script lists the required ones at the top).

**RLS denies a query that should succeed.** The auth_uid is null (the user is on the worker-name fallback) and the policy is checking `auth.uid()`. Two paths: backfill the auth_uid, or extend the policy to accept the worker-name path. Memory entry on the Supabase Auth migration captures the long-term plan.

**The marketplace KYB stalls.** The seller did not complete Stripe Connect. `marketplace-connect-status` polls Stripe and updates the row. The supervisor sees the pending row in `marketplace-admin.html` and can resend the onboarding link.

## 30. The Road Ahead

Honest list of what is built, what is partial, and what is planned.

**Built and live (May 2026):**
- All daily-work pages (logbook, PM scheduler, inventory, skill matrix, day planner).
- The engineering design calculator across six disciplines, with BOM and SOW.
- The marketplace, end to end, with Stripe escrow and buyer reviews.
- The community module with cross-hive feed.
- The analytics page with the analytics-orchestrator edge function.
- The AI assistant with platform context across every page.
- The Platform Guardian with 51 validators.

**Built but waiting on a single dependency:**
- The B2 weekly digest. Waiting on Resend domain verification.
- The full Supabase Auth migration. Foundation laid; cutover deferred.

**Planned (Phase 2 Guardian and beyond):**
- Phase 2: visual dashboard with trend charts on `platform-health.html`.
- Phase 3: self-learning loop where the Guardian updates skill files automatically when a pattern of failures repeats.
- Phase 4: auto-fix loop where the Guardian opens a backlog item with web-search context when a FAIL persists across three runs.

**Domain expansions on the roadmap:**
- SAP PM and IBM Maximo connectors (`integration-engineer` skill is ready; the connector code is not).
- OPC-UA and MQTT IoT protocol bridges for live equipment telemetry.
- Predictive analytics models for failure prediction, beyond the current rule-based thresholds.
- Enterprise compliance (ISO 27001, SOC 2 Type II) for the industrial-client tier.

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
├── engineering-design.html          # calculator across 6 disciplines
├── architecture.html                # platform self-overview
├── symbol-gallery.html              # drawing symbol catalog
├── community.html                   # forum + profiles
├── public-feed.html                 # cross-hive public posts
├── report-sender.html               # handover + digest
├── marketplace.html                 # buyer-facing
├── marketplace-seller.html          # seller dashboard
├── marketplace-admin.html           # supervisor approval + KYB
├── analytics.html                   # KPIs and trends
├── assistant.html                   # AI context registry
├── platform-health.html             # Guardian dashboard
│
├── utils.js                         # escHtml, hive context, role gate, toast
├── nav-hub.js                       # two-tier nav
├── floating-ai.js                   # AI pill on every page
├── skill-content.js                 # skill matrix content
├── drawing-symbols.js               # IEC/ISA/NFPA symbol library
├── sw.js                            # service worker
│
├── run_platform_checks.py           # Guardian orchestrator
├── run_all_checks.py                # engineering calc 4-layer suite
├── validate_*.py                    # 51 validators
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
│   ├── migrations/                  # 32 timestamped migrations
│   └── functions/                   # 16 edge functions
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
```

## Appendix C. Edge Function Catalog

```
_shared/                       # shared CORS, auth, retry helpers
ai-orchestrator                # main AI router with prompt caching
analytics-orchestrator         # analytics LLM-on-top summary
embed-entry                    # pgvector embed write
semantic-search                # pgvector knn read
engineering-calc-agent         # NL entry to calc payload
engineering-bom-sow            # BOM + SOW from calc payload
marketplace-checkout           # Stripe Checkout session
marketplace-connect-onboard    # Stripe Connect onboarding
marketplace-connect-status     # KYB status poll
marketplace-release            # release escrow on confirmation
marketplace-webhook            # Stripe event reconciler
scheduled-agents               # pg_cron-driven jobs
send-report-email              # Resend send for digests
voice-report-intent            # voice intent classification
voice-transcribe               # voice to text
```

## Appendix D. Validator Index

The 51 registered validators, alphabetical:

```
validate_accessibility
validate_ai_attribution
validate_ai_context
validate_ai_data_pipeline
validate_ai_regression
validate_analytics
validate_analytics_live
validate_assistant
validate_bom_sow
validate_catalog_scope
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
validate_idempotency
validate_input_guards
validate_integration
validate_integration_security
validate_inventory
validate_iot_protocols
validate_knowledge_freshness
validate_logbook
validate_mobile
validate_nav_registry
validate_notifications
validate_observability
validate_performance
validate_pm
validate_predictive
validate_pwa
validate_renderers
validate_report_sender
validate_schema
validate_seo
validate_skillmatrix
validate_sso_readiness
validate_tenant_boundary
validate_timers
validate_vector_schema
validate_xss
```

Each validator owns a single JSON report (`<name>_report.json`) at the project root. The Guardian aggregates them into `platform_health.json`.

## Appendix E. Glossary

- **Hive.** The tenant. Usually a plant, a shift, or a team. The unit of multi-tenancy.
- **Worker.** The default user role inside a hive.
- **Supervisor.** The role that approves things: restocks, listings, joins, promotions.
- **Manager.** The role that reads cross-hive analytics and signs off on engineering designs.
- **WAT.** Workflows, Agents, Tools. The three-layer architecture.
- **Skill.** An accumulated lessons file at `~/.claude/skills/<name>/SKILL.md`. Read first, written back after.
- **Guardian.** The master validator orchestrator (`run_platform_checks.py`).
- **Baseline.** The last all-green snapshot of the Guardian run. Used for regression detection.
- **Readiness Gate.** Loop 3 of the Guardian: git, deploy, API status.
- **MTBF, MTTR, OEE.** Mean Time Between Failures, Mean Time To Repair, Overall Equipment Effectiveness. The three core maintenance KPIs the analytics page rolls up.
- **BOM, SOW.** Bill of Materials, Scope of Work. The dual artifacts the engineering calculator emits.
- **DILO, WILO, MILO, YILO.** Day, Week, Month, Year In the Life Of. The four time-block modes of the day planner.
- **KYB.** Know Your Business. The Stripe Connect compliance step for marketplace sellers.
- **LOTO.** Lock Out, Tag Out. The isolation procedure detected by regex in shift handover reports.
- **PWA.** Progressive Web App. The platform installs to the home screen on iOS and Android via `sw.js` and `manifest.json`.
- **RLS.** Postgres Row Level Security. The mechanism that scopes hive data to its tenant.
- **pgvector.** The Postgres extension for embedding storage and KNN search. Foundation of the AI assistant's retrieval.

---

End of book. Version 2026-05-01.
