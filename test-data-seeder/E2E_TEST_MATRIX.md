# Layer 2: End-to-End Test Matrix
## WorkHive Platform — Complete Coverage Plan

**Last Updated:** 2026-05-16  
**Status:** Infrastructure Setup  
**Goal:** 99.9% confidence in all user journeys (read + write + additional paths)

---

## Test Coverage Overview

- **Total Pages:** 35 live pages
- **Paths per Page:** 9-12 scenarios
- **Total Test Cases:** ~380+ scenarios
- **Test Execution:** Automated via `run_flows.py`

---

## Page Categorization

### Tier 1: Core Workflows (Data CRUD) — 8 pages
Critical write/read paths that affect business logic directly.

| Page | Read Path | Write Path | Additional Path | Status |
|------|-----------|-----------|-----------------|--------|
| **logbook.html** | Load entries + filters | Create/Edit/Delete entry + parts | Offline queue, validation, permissions | TODO |
| **inventory.html** | Load items + stock | Restock/Deduct quantity | Low-stock alerts, approval queue | TODO |
| **pm-scheduler.html** | Load PM tasks + assets | Complete PM task + anchor date | Overdue detection, skip logic | TODO |
| **hive.html** | Load dashboard KPIs | Switch hive context | Hive permissions, realtime updates | TODO |
| **community.html** | Load posts + feed | Create/Edit/Delete post + reactions | Supervisor edit, XP awards, realtime | TODO |
| **marketplace.html** | Load listings | Create/Edit listing + publish | Seller verification, approval queue | TODO |
| **project-manager.html** | Load projects + workorders | Create/Update workorder + assign | Status transitions, approval flow | TODO |
| **inventory.html** | (duplicate above) | (duplicate above) | (duplicate above) | TODO |

### Tier 2: Reporting & Analytics — 7 pages
Read-heavy with calculated/aggregated data.

| Page | Read Path | Write Path | Additional Path | Status |
|------|-----------|-----------|-----------------|--------|
| **analytics.html** | Load KPIs + charts | Period selector changes | OEE/MTBF accuracy, export | TODO |
| **analytics-report.html** | Load report sections | Generate report + download | Filter by machine/discipline | TODO |
| **shift-brain.html** | Load shift handover | Submit handover notes | Team visibility, realtime | TODO |
| **asset-hub.html** | Load asset details | Update asset metadata | Risk scoring, related logbook | TODO |
| **alert-hub.html** | Load alerts + patterns | Acknowledge/Resolve alert | Filtering, auto-dismiss | TODO |
| **predictive.html** | Load failure predictions | Trigger ML scoring | Calendar view, export | TODO |
| **ai-quality.html** | Load AI quality metrics | Manual evaluate result | Cost tracking, model comparison | TODO |

### Tier 3: Admin & Config — 8 pages
Supervisor/Admin-only features with role-based access.

| Page | Read Path | Write Path | Additional Path | Status |
|------|-----------|-----------|-----------------|--------|
| **skillmatrix.html** | Load skill levels + badges | Update skill target level | Badge awards, XP tracking | TODO |
| **report-sender.html** | Load report template | Send report to recipients | Multi-recipient, retry on fail | TODO |
| **plant-connections.html** | Load enterprise settings | Update plant/site config | Multi-tenant isolation | TODO |
| **audit-log.html** | Load audit trail | (read-only) | Filter by action/user/date | TODO |
| **platform-health.html** | Load health dashboard | (read-only) | Validator status, trend analysis | TODO |
| **achievements.html** | Load badges + progress | (awarded by system) | Badge unlock notifications | TODO |
| **voice-journal.html** | Load voice logs | Record voice note + transcribe | Real-time transcription, error recovery | TODO |
| **integrations.html** | Load CMMS config | Update integration settings | Webhook testing, credential rotation | TODO |

### Tier 4: Public & Landing — 5 pages
Unauthenticated or minimal-auth pages.

| Page | Read Path | Write Path | Additional Path | Status |
|------|-----------|-----------|-----------------|--------|
| **index.html** | Load home (hero + auth forms) | Sign-up / Sign-in | Redirect after auth, remember hive | TODO |
| **public-feed.html** | Load cross-hive posts | (no direct write) | Pagination, search, filter by hive | TODO |
| **assistant.html** | Load AI chat | Send message + get response | Rate limiting, history truncate | TODO |
| **ph-intelligence.html** | Load PH-specific insights | (no direct write) | Data freshness, error fallback | TODO |
| **marketplace-admin.html** | Load seller listings (admin) | Approve/Reject listing | Verification, payment settings | TODO |

### Tier 5: Specialized — 7 pages
Feature-specific workflows.

| Page | Read Path | Write Path | Additional Path | Status |
|------|-----------|-----------|-----------------|--------|
| **dayplanner.html** | Load schedule (DILO/WILO) | Create schedule entry | Shift context, team visibility | TODO |
| **engineering-design.html** | Load calc form | Run calc + generate report | Diagram generation, PDF export | TODO |
| **project-report.html** | Load project details | Generate project report | Scope items, stakeholder export | TODO |
| **marketplace-seller.html** | Load seller dashboard | List own products | Inventory sync, rating display | TODO |
| **marketplace-seller-profile.html** | Load seller profile | Update seller bio/rating | Verification status, reviews | TODO |
| **symbol-gallery.html** | Load drawing symbols | (design-time only) | Filter by standard (IEC/NFPA) | TODO |
| **founder-console.html** | Load platform dashboard | Admin panel controls | All hives, cost aggregation | TODO |

---

## Path Definition (9-12 scenarios per page)

### Read Path (2-3 scenarios)
- ✓ Happy path: Load page → query data → render correctly
- ✓ Empty state: No data → show honest empty placeholder
- ✓ Loading state: Slow network → show spinner, no flickering

### Write Path (4-5 scenarios)
- ✓ Happy path: Form input → validate → submit → DB → UI refresh
- ✓ Validation error: Invalid input → show error message → user can correct
- ✓ API error: DB fails → show retry button → user can retry
- ✓ Permission denied: Worker trying supervisor action → show "Not allowed" + no button
- ✓ Concurrent edit: Stale data → show conflict message → user can reload

### Additional Path (3-4 scenarios)
- ✓ Offline mode: Network down → queue entry → sync when online
- ✓ Edge case: Boundary values (0, max, special chars) → handle gracefully
- ✓ Mobile: 375px viewport → no horizontal scroll, tap targets ≥44px
- ✓ Browser error: Console errors → zero critical errors, max 1 warning

---

## Test Execution Layers

### L2.1: Unit Tests (Playwright per-page)
```
test_logbook.js    → 12 scenarios
test_inventory.js  → 12 scenarios
test_community.js  → 12 scenarios
... (35 pages × 10-12 scenarios)
```

### L2.2: Integration Tests (Cross-page flows)
```
logbook → inventory (parts deduction)
logbook → PM (maintenance sync)
marketplace → payment (transaction flow)
... (8-10 multi-page journeys)
```

### L2.3: Smoke Tests (All pages)
```
Open every page → no console errors → layout intact
(~2 min total execution)
```

### L2.4: Mobile Tests (Responsive)
```
375px viewport → no overflow → all buttons accessible
(~10 pages, critical paths only)
```

---

## Success Criteria

| Criterion | Target | Current | Status |
|-----------|--------|---------|--------|
| Pages with tests | 35/35 | 0/35 | ❌ TODO |
| Read path pass rate | 100% | TBD | ⏳ |
| Write path pass rate | 100% | TBD | ⏳ |
| Additional path pass rate | 100% | TBD | ⏳ |
| Mobile compatibility | 100% | TBD | ⏳ |
| Console errors (critical) | 0 | TBD | ⏳ |
| Test execution time | <5 min | TBD | ⏳ |

---

## Build Plan

### Phase 1: Infrastructure (This session)
- [ ] Test runner scaffold
- [ ] Helper functions (login, form fill, validation checks)
- [ ] Reporter (PASS/FAIL/WARN with details)
- [ ] Coverage tracking

### Phase 2: Tier 1 Pages (Next session)
- [ ] logbook, inventory, pm-scheduler, hive, community, marketplace, project-manager
- [ ] All 3 paths per page
- [ ] Fix all bugs found

### Phase 3: Tier 2-4 Pages
- [ ] Analytics, reporting, admin, landing pages
- [ ] All paths
- [ ] Fix bugs

### Phase 4: Tier 5 + Integration Tests
- [ ] Specialized pages
- [ ] Cross-page flows
- [ ] Mobile + edge cases

---

## Test Report Template

After each phase, produce:

```
PHASE X REPORT
=============
Date: YYYY-MM-DD
Pages tested: X
Total scenarios: Y
Results: Z PASS / W FAIL / V WARN

Bugs Found:
- [Page] [Path] [Issue] [Root Cause] [Fix Applied] [Status: FIXED/DEFERRED]

Remaining Risks:
- [Risk] [Mitigation]

Commands Run:
$ python run_flows.py --layer2-tier-X
```

---

**Next Step:** Build test infrastructure (helpers, runner, reporters)
