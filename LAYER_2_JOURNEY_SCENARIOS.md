# Layer 2 Journey Scenarios — Playwright Coverage Map

**Purpose:** comprehensive E2E journey coverage for Mega Gate Layer 2. 70 scenarios across 12 tiers. Every test name uses the auto-match convention (`scenario_id_check_name: ...`) so Sentinel coverage grows automatically.

**Test identity (per `reference_playwright_test_identity`):**
- **Pablo Aguilar (supervisor)** in hive `586fd158-42d1-4853-a406-64a4695e71c4` (Baguio Textile Mills, Stair 2, composite 87)
- Leandro Marquez is NOT in any hive (use for negative tests of `validateHiveMembership`)

**Spec files (13):**
- `tests/journey-auth-identity.spec.ts` (Tier 1)
- `tests/journey-worker-core.spec.ts` (Tier 2)
- `tests/journey-supervisor.spec.ts` (Tier 3)
- `tests/journey-engineer.spec.ts` (Tier 4)
- `tests/journey-project.spec.ts` (Tier 5a)
- `tests/journey-marketplace.spec.ts` (Tier 5b)
- `tests/journey-mobile-a11y.spec.ts` (Tier 6)
- `tests/journey-offline.spec.ts` (Tier 7)
- `tests/journey-security.spec.ts` (Tier 8)
- `tests/journey-ai-assisted.spec.ts` (Tier 9)
- `tests/journey-realtime.spec.ts` (Tier 10)
- `tests/journey-cross-page.spec.ts` (Tier 11)
- `tests/journey-regression-pins.spec.ts` (Tier 12)

---

## Tier 1 — Authentication & identity (P0, 5 scenarios)

| ID | Title | Role | Surface |
|---|---|---|---|
| A1 | First signup (username + synthetic email) | new worker | index.html |
| A2 | Sign-in with username + password | returning worker | index.html |
| A3 | Identity restoration on new device | existing worker | hive.html or logbook.html |
| A4 | Sign-out clears ALL 7 localStorage keys | any | any |
| A5 | Hive membership revalidation on protected page load | worker | hive.html |

## Tier 2 — Worker core flows (P0, 8 scenarios)

| ID | Title | Surface |
|---|---|---|
| B1 | Submit a logbook entry (full form) | logbook.html |
| B2 | Edit-in-place + close an open entry | logbook.html |
| B3 | Add asset to register via logbook modal | logbook.html |
| B4 | Voice-journal a maintenance event | voice-journal.html |
| B5 | Visual defect capture | logbook.html (modal) |
| B6 | Record inventory transaction (out / in) | inventory.html |
| B7 | Complete a PM scope item | pm-scheduler.html |
| B8 | Voice-to-logbook structured intent | voice-journal.html |

## Tier 3 — Supervisor flows (P0, 7 scenarios)

| ID | Title | Surface |
|---|---|---|
| C1 | Approve pending inventory items | hive.html or inventory.html |
| C2 | Approve pending asset additions | asset-hub.html |
| C3 | Approve pending PM templates | pm-scheduler.html |
| C4 | Reject/kick hive member | hive.html |
| C5 | Live hive activity feed (realtime) | hive.html |
| C6 | Acknowledge AMC alert | alert-hub.html |
| C7 | Generate shift handover summary | shift-brain.html |

## Tier 4 — Engineer flows (P1, 5 scenarios)

| ID | Title | Surface |
|---|---|---|
| D1 | Run engineering calc (BOM + SOW) | engineering-design.html |
| D2 | Generate signed PDF report | engineering-design.html |
| D3 | Skill matrix update + level-up | skillmatrix.html |
| D4 | MTBF view for an asset | predictive.html |
| D5 | Diagram-builder (3-step atomic rule) | engineering-design.html |
| D6 | Calc reuse from logbook anchor | logbook.html → engineering-design.html |

## Tier 5 — Project & marketplace (P1, 8 scenarios)

| ID | Title | Surface |
|---|---|---|
| E1 | Create project, link to hive | project-manager.html |
| E2 | Executive project report | project-report.html |
| E3 | Project progress update | project-manager.html |
| F1 | Seller lists a new item | marketplace-seller.html |
| F2 | Admin approves listing | marketplace-admin.html |
| F3 | Buyer checkout flow (Stripe) | marketplace.html |
| F4 | Stripe webhook signature verification | edge fn: marketplace-webhook |
| F5 | Seller views + responds to inquiries | marketplace-seller-profile.html |

## Tier 6 — Mobile / accessibility (P1, 6 scenarios)

| ID | Title | Scope |
|---|---|---|
| G1 | All pages render at 375px width | every public page |
| G2 | Keyboard navigation reaches every interactive element | hive, logbook, alert-hub |
| G3 | Screen reader announces toast confirmations | logbook |
| G4 | iOS auto-zoom does NOT trigger on form focus | logbook, engineering-design |
| G5 | `<main>` landmark present on every page | every page |
| G6 | PDF export on mobile (no blank first page) | engineering-design, project-report |

## Tier 7 — Offline & resilience (P1, 4 scenarios)

| ID | Title | Surface |
|---|---|---|
| H1 | Submit form offline → IndexedDB queue → sync on reconnect | logbook |
| H2 | Service worker serves cached HTML offline | any SHELL_FILE |
| H3 | CACHE_NAME bump invalidates stale cache | sw.js |
| H4 | Offline banner shows pending count | logbook |

## Tier 8 — Security & multi-tenancy (P0, 6 scenarios)

| ID | Title |
|---|---|
| I1 | Worker A cannot read Worker B's data in another hive |
| I2 | Console call to deleteCalc cannot delete another user's row |
| I3 | Inline onclick approve/reject requires internal HIVE_ROLE check |
| I4 | XSS attempt in user-supplied text is escaped |
| I5 | service_role key never appears in page source |
| I6 | Stripe webhook rejects invalid signature |

## Tier 9 — AI-assisted flows (P1, 5 scenarios)

| ID | Title | Surface / edge fn |
|---|---|---|
| J1 | AI assistant answers via ai-gateway | assistant.html |
| J2 | Voice journal: multilingual transcript + reply | voice-journal.html |
| J3 | RAG: answer cites industry_standards | assistant.html |
| J4 | Visual defect: photo → AI label → asset match | logbook.html |
| J5 | AI gateway PII redaction round-trip | edge fn: ai-gateway |

## Tier 10 — Realtime (P1, 4 scenarios)

| ID | Title | Surface |
|---|---|---|
| K1 | Logbook INSERT propagates to hive feed | hive.html |
| K2 | Logbook DELETE propagates | hive.html |
| K3 | Presence indicator (live status) | hive.html |
| K4 | Inventory low-stock alert (push) | hive.html or alert-hub.html |

## Tier 11 — Cross-page consistency (P2, 4 scenarios)

| ID | Title | Pages compared |
|---|---|---|
| L1 | PM count matches across home + pm-scheduler | index ↔ pm-scheduler |
| L2 | Open-jobs count identical on hive + logbook | hive ↔ logbook |
| L3 | Inventory low-stock count consistent | hive ↔ inventory ↔ alert-hub |
| L4 | Worker XP / level identical on achievements + hive | achievements ↔ hive |

## Tier 12 — Regression pins (P0, 7 scenarios)

| ID | Title | Past bug |
|---|---|---|
| M1 | ph-intelligence escapes single-quote in escHtml | 2026-05-19 real XSS hole |
| M2 | Every validate_*.py has the cp1252 stdout guard | 33 latent Windows crashes patched |
| M3 | Every public page has `<main>` landmark | 21 a11y-broken pages fixed |
| M4 | No inline `function escHtml` on any HTML page | 8 drift points eliminated |
| M5 | Marketplace edge fns import getCorsHeaders from shared | 6 fns migrated |
| M6 | logbook ↔ pm-scheduler overlap stays in allowlist | Allowlist freshness |
| M7 | No phantom views (v_*_truth referenced but undefined) | platform-scraper fixed |

---

## Implementation status

| Tier | Spec file | Scenarios | State |
|---|---|---:|---|
| 1 | journey-auth-identity.spec.ts | 5 | shipped |
| 2 | journey-worker-core.spec.ts | 8 | shipped |
| 3 | journey-supervisor.spec.ts | 7 | shipped |
| 4 | journey-engineer.spec.ts | 5 | shipped (D4_predictive retired 2026-07-01 — predictive.html removed) |
| 5a | journey-project.spec.ts | 3 | shipped |
| 5b | journey-marketplace.spec.ts | 5 | shipped |
| 6 | journey-mobile-a11y.spec.ts | 6 | shipped |
| 7 | journey-offline.spec.ts | 4 | shipped |
| 8 | journey-security.spec.ts | 6 | shipped |
| 9 | journey-ai-assisted.spec.ts | 5 | shipped |
| 10 | journey-realtime.spec.ts | 4 | shipped |
| 11 | journey-cross-page.spec.ts | 4 | shipped |
| 12 | journey-regression-pins.spec.ts | 7 | shipped (real assertions) |

## Conventions used

1. **Test name prefix** = scenario ID + check name slug. Sentinel coverage map auto-matches.
2. **`test.fixme(...)`** marks scaffolds that need real DB / Stripe / Azure setup. They skip rather than fail.
3. **Regression pins (Tier 12)** use REAL assertions — they read files / reports and assert invariants without needing a live server.
4. **Existing fixtures** (`whPage`, `adminClient`) from `tests/_fixtures.ts` are used everywhere.

## How to fill in a scaffold

Each scaffolded test has 3 sections:
```ts
// WHY: <regression class this prevents>
// SETUP: <preconditions to seed>
// ACT: <user steps in code>
// ASSERT: <expected outcome>
```

Replace `test.fixme(` with `test(` once the test data + assertions are wired. The test name stays the same so Sentinel coverage is unaffected.
