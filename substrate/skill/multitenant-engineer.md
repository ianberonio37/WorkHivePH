---
name: skill-multitenant-engineer
type: skill
source: skill:multitenant-engineer
source_sha: c435dc4f1da21884
last_verified: 2026-07-13
supersedes: null
---
## skill · multitenant-engineer

Hive access control, role-based permissions, Supabase RLS for multi-tenancy, data isolation between hives, bot protection, cross-hive data access prevention, and auth migration. Triggers on "hive", "m

**Sections:** Multitenant Engineer Agent · WorkHive's Multitenant Model · Current Auth Model (String Identity — CRITICAL Gap) · A UI-only approval gate is NO gate — and RLS alone can't enforce it; use a BEFORE trigger (2026-07-07, deep-walk dim-2, CONFIRMED EXPLOIT) · Column-guard BEFORE-trigger: allow self-downgrade, block self-upgrade of a verification flag; and a SECURITY INVOKER trigger writing ANOTHER table hits that table's RLS (Marketplace PDDA, 2026-07-11) · A child/ledger table's INSERT must membership-JOIN the PARENT's hive — the parent's RLS does NOT cover it (Inventory PDDA, 2026-07-12, CONFIRMED EXPLOIT) · Auth Migration Path — POLICIES ADDED (C1–C4, April 2026), ENFORCEMENT completed by Arc G (June 2026) · RLS Policies — Correct Patterns for WorkHive · The Hive Membership Join Pattern · Auth Backfill Must Run AFTER Workers Sign Up — Timing Is Critical · GRANT Statements Are Required When Creating Tables via SQL Migrations · Supervisor-Only Actions in RLS · Solo Mode (No Hive) — RLS Must Still Work · Hive Isolation Checklist — Run on Every New Feature · `.in('worker_name', memberNames)` Is Not Hive Isolation · Hive Switch Must DB-Validate Membership Before Loading Board · Role-Based Permission Patterns · The Three-State Role Model · Supervisor Auto-Approve Rule · Role-Gated UI Buttons — Template Level, Not Function Level · Cross-Hive Data Flow Audit · Bot Protection — Platform-Level · Registration Bots · Data Flooding Per Hive · Kicked Member Re-Entry · Account Offboarding — Soft-Deactivate + Anonymize (GDPR/PDPA, Arc I I8/I, 2026-06-21) · Detail-View Hive Scope Must Match Picker Scope · Sub-Queries Fetched by Array Do Not Inherit Parent Hive Scope · status=approved Required on Every Catalog Query Exposed to Users · Pre-Launch Multitenant Checklist

(Deep source: `skill:multitenant-engineer` — retrieve this TOC to know WHICH section to read.)
