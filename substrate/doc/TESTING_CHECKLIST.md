---
name: doc-TESTING_CHECKLIST
type: doc
source: file:TESTING_CHECKLIST.md
source_sha: 728313ac2cdc8fae
last_verified: 2026-07-13
supersedes: null
---
## doc · TESTING_CHECKLIST

A page-by-page test list drawn from your skill files (QA, Frontend, Mobile Maestro, Multitenant, Performance) — covers angles you wouldn't think of from your own seat.

**Sections:** WorkHive Testing Checklist — Pre-Launch · 0. Pre-test smoke tests (every reset+seed) · 1. Authentication & identity (cross-page) · Sign in · Sign up · Session restore (cache-clear scenario) · Sign out · Identity consistency (run on EVERY page) · 2. Hive isolation (multi-tenant) — critical · 3. Logbook (`logbook.html`) · Render with seeded data · Add new entry (real interaction) · Edit-in-place · Field parity (silent data loss check) · Offline queue (DevTools → Network → Offline) · Team feed · Mobile-specific · 4. Inventory (`inventory.html`) · Use part flow · Restock flow · Approval flow (for shared catalog) · Field parity · 5. PM Scheduler (`pm-scheduler.html`) · Frequency math · Mark complete · Calendar / overview · 6. Analytics (`analytics.html`) · Hero numbers (top of page) · Period selector (critical — common bug area) · Direction indicators

(Deep source: `file:TESTING_CHECKLIST.md` — retrieve this TOC to know WHICH section to read.)
