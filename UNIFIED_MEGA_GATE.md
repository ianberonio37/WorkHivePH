# Unified Mega Gate Architecture
## Integrated Platform Quality System

**Created:** 2026-05-16
**Last upgraded:** 2026-05-27 (v2 — 3-layer → 6-gate-layer model)
**Status:** Architecture Definition + Standing Rule Formalization
**Integration Level:** Single Entry Point for All Quality Checks
**Companion study:** [COMPREHENSIVE_STUDY_FULLSTACK_GATE.md](COMPREHENSIVE_STUDY_FULLSTACK_GATE.md) — the 13 × 6 coverage matrix that maps production layers to gate layers.

---

## v2 Overview (2026-05-27)

The original 3-layer model below describes Layer 0 / Layer 1 (WorkHive Tester) / Layer 2. That model is now a *subset* of a 6-gate architecture that grew across the 2026-05-21 → 2026-05-27 flywheel turns. Use this section as the canonical gate definition; the 3-layer section below remains as the Layer 1 interactive tester reference.

### The 6 gate layers

| ID | Layer | Purpose | Coverage today | Execution |
|---|---|---|---|---|
| **G-1.5** | Substrate / Pre-architecture | Pattern miners detect code-shape drift before it becomes a bug | 13 miners aggregated in `substrate_manifest.json` | ~30 sec (info-only) |
| **G-1** | Auto-discovery / Drift mining | Detects new pages, edge fns, validators; ensures registration | `validate_auto_discovery.py`, `validator_self_coverage`, `NEW_SURFACES_REPORT.json` | ~20 sec |
| **G0** | Fast Guardian | 330 validators run in parallel (`--workers 6`); every rule baseline-ratcheted | 330 validators across 18 groups | ~90 sec parallel; ~7 min serial |
| **GH** | Hardening Loop | Layer 2 finding → seeder + validator (the bug becomes the gate) | `/harden` skill, `tools/hardening_auto_trigger.py` | on-demand |
| **GS** | Sentinel | Layer 0 rule → Playwright scenario (every TIER 1 rule has ≥2 anchored tests) | `sentinels/multi_scenario_per_rule.py` (0 gaps) | ~15 sec |
| **G2** | Comprehensive E2E | 60+ Playwright specs, 5 tiers, ~375 scenarios | All TIER 1 rules anchored | ~90 sec Tier 1; ~5-15 min full |

### Bridges + flow

```
  G-1.5  ──────►  G-1  ──────►  G0  ──────►  G2
SUBSTRATE   AUTODISCOVER   GUARDIAN     PLAYWRIGHT
                                 ▲           │
                                 │           ▼
                              GH HARDEN  GS SENTINEL
                              (L2 → L0)  (L0 → L2)
```

The **hardening loop** (GH) and **sentinel** (GS) are the bidirectional bridges that make the gate self-improving. Every flywheel turn moves rules through both bridges:

- A failing L2 scenario → Hardening Loop → new L0 validator → next turn catches the bug class earlier
- A new L0 validator → Sentinel → proposed L2 scenario → next turn covers it behaviorally

### Coverage matrix

Full 13 production layers × 6 gate layers matrix lives in [COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4](COMPREHENSIVE_STUDY_FULLSTACK_GATE.md#4-the-coverage-matrix-13--6). Current state: **56 / 78 cells filled (72%)**. The 22 uncovered cells are the gap list in §7 of that study.

### Persistence mechanisms

15 concrete artefacts persist progress across sessions (frozen baselines, migration hashes, PLATFORM_ROADMAP.md, memory entries, validator registrations, etc.) — see [COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §5](COMPREHENSIVE_STUDY_FULLSTACK_GATE.md#5-persistence-mechanisms--how-progress-doesnt-get-lost). Every new artefact must declare which of these it relies on, or it doesn't persist and doesn't belong in the gate.

### Compounding evidence

5 flywheel turns, combined coverage **14% → 17% → 21% → 28% → 37%**. See [COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §6](COMPREHENSIVE_STUDY_FULLSTACK_GATE.md#6-compounding-evidence-5-turns) for the per-turn data. The bridges (GH + GS) are what make the curve compound rather than plateau.

### Standing rules (v2)

Three invariants the gate enforces. Any work that violates them must be reverted.

- **Rule A — Every production change lands with a gate change.** Helpers without validators don't count.
- **Rule B — Baselines only move down.** A baseline that increments is a real regression, not a "rebase."
- **Rule C — Every fix updates ≥3 skills.** Lessons compound across the platform's collective intelligence, not just the codebase.

---

## v1 Overview (legacy 3-layer model — kept for Layer 1 interactive tester reference)

The Unified Mega Gate is a three-layer integrated quality system that ensures 99.9% confidence in platform correctness:

| Layer | Component | Purpose | Coverage | Execution |
|-------|-----------|---------|----------|-----------|
| **Layer 0** | Fast Platform Guardian | Schema + code architecture validation | **330** validators (was 160 in v1) | **~90 sec parallel** (was <90 sec serial) |
| **Layer 1** | WorkHive Tester | Local interactive testing + flow specs | 24 journey flows + 6 test panes | Manual or via SSE |
| **Layer 2** | E2E Comprehensive Tests | Complete user journey validation | 35 pages × 380 scenarios | <5 min (full) / <90 sec (Tier 1) |

**Flow (v1):** Code change → Fast Guardian (Layer 0) → WorkHive Tester (Layer 1) → E2E Tests (Layer 2) → Seeding update → Validator creation → Layer 0 smarter

**Flow (v2):** Code change → G-1.5 substrate → G-1 auto-discovery → G0 guardian → G2 layer 2 → GH harden (if red) → GS sentinel (if new rule) → next turn smarter

---

## Layer 0: Fast Platform Guardian

**File:** `run_platform_checks.py --fast`

**Purpose:** Catch architectural, schema, and code issues before they reach QA

**Coverage:**
- 160 validators across 10 categories
- Schema integrity (migrations, RLS, triggers)
- Security (DEFINER+search_path, secrets exposure, CORS)
- Performance (cold-start, caching, indexes)
- Architecture (cascade behavior, optimistic concurrency, provider bypass)

**Execution:**
```bash
python run_platform_checks.py --fast      # Tier 1-3 validators only (~90 sec)
python run_platform_checks.py --full      # All 160 validators (~5-8 min)
```

**Output:**
- Exit code 0 = all checks PASS
- Exit code 1 = ≥1 FAIL detected
- `platform_health.json` with full results
- Console: colored PASS/FAIL/WARN summary

**Decision Point:** If Layer 0 has FAIL, stop. Fix before moving to Layer 1.

---

## Layer 1: WorkHive Tester (Local Interactive Testing)

**URL:** `http://127.0.0.1:5000/workhive`

**Purpose:** Real-world testing with immediate visual feedback

**Components:**

### 6 Testing Panes

1. **LIVE TOOLS PAGE** — Open any live page (35 pages selectable)
2. **FLOW SPEC RUNNER** — Run 24 pre-recorded journey specs
3. **SMOKE TEST** — All pages, 1 click, 2 min
4. **MOBILE TESTS** — Responsive viewport (375px) validation
5. **SIGNUP TESTS** — Auth flow validation
6. **LAYER 2 RUNNER** — E2E comprehensive tests (new integration)

### SSE Live Log Drawer

- Real-time output from every test run
- Job-id counter prevents display state resets
- Hover-tips on every control
- Result summary (X PASS / Y FAIL / Z WARN)

**Execution:**
```
UI: Click any gate → SSE logs stream → Results summary
Manual: Walk through page, screenshot regressions
Visual: Compare before/after screenshots side-by-side
```

**Decision Point:** FAIL or WARN → screenshot → document in test notes → proceed to Layer 2 if architectural

---

## Layer 2: E2E Comprehensive Tests

**File:** `python e2e_runner.py` + `flows/e2e_*.py`

**Purpose:** Journey-level validation covering all user paths (read + write + additional)

**Coverage:**
- 35 live pages
- 3 path types per page: read (data load), write (CRUD), additional (permissions/offline/mobile)
- ~380 total scenarios
- 5 tiers organized by criticality

### Test Matrix Structure

```
Tier 1 (Core Workflows) — 8 pages × 12 scenarios = 96 tests
  logbook, inventory, pm-scheduler, hive, community, marketplace, project-manager

Tier 2 (Analytics) — 7 pages × 11 scenarios = 77 tests
  analytics, asset-hub, alert-hub, predictive, ai-quality, shift-brain, analytics-report

Tier 3 (Admin) — 8 pages × 10 scenarios = 80 tests
  skillmatrix, report-sender, plant-connections, audit-log, voice-journal, achievements, integrations, platform-health

Tier 4 (Landing) — 5 pages × 9 scenarios = 45 tests
  index, public-feed, assistant, ph-intelligence, marketplace-admin

Tier 5 (Specialized) — 7 pages × 11 scenarios = 77 tests
  dayplanner, engineering-design, project-report, marketplace-seller, marketplace-seller-profile, symbol-gallery, founder-console

Total: 375 scenarios
```

### Path Types

**READ PATH** (2-3 scenarios)
- Happy path: Load page → query data → render correctly
- Empty state: No data → honest placeholder
- Loading state: Slow network → spinner, no flickering

**WRITE PATH** (4-5 scenarios)
- Happy path: Form → validate → submit → DB → UI refresh
- Validation error: Invalid input → error message
- API error: DB fails → retry button visible
- Permission denied: Worker trying supervisor action → "Not allowed"
- Concurrent edit: Stale data → conflict message

**ADDITIONAL PATH** (3-4 scenarios)
- Offline mode: Network down → queue → sync when online
- Edge cases: Special chars, max length, boundary values
- Mobile: 375px viewport → no overflow, tap targets ≥44px
- Console errors: Zero critical errors, max 1 warning

### Execution Modes

```bash
# Fast mode (Tier 1 only, all paths)
python e2e_runner.py --tier 1              # ~90 sec

# Single page
python e2e_runner.py --page logbook        # ~15 sec

# Specific path only
python e2e_runner.py --path write          # Only write scenarios

# Full tiers 1-5
python e2e_runner.py --tier 1 --tier 2 --tier 3 --tier 4 --tier 5  # ~5 min

# Mobile focus
python e2e_runner.py --mobile              # Mobile only

# With report
python e2e_runner.py --tier 1 --report     # Generates e2e_report.md + e2e_results.json
```

**Output:**
```
LAYER 2: E2E COMPREHENSIVE TESTS
================================

Tier 1: Core Workflows
  logbook:           12/12 PASS
  inventory:         11/12 PASS (1 FAIL: offline queue)
  pm-scheduler:      11/11 PASS
  ...

Results: X PASS / Y FAIL / Z WARN
Duration: 45 seconds
Coverage: 87/87 scenarios (100%)

[Failures with root causes if any]
```

---

## Standing Rule: Layer 2 → Layer 1 Feedback Loop

**When Layer 2 E2E finds a bug that Layer 0 (validators) missed:**

1. **Document** the bug (page, path, scenario, actual vs expected, root cause)
2. **Fix** the underlying code issue
3. **Update Seeding** (test-data-seeder/seeders/) to create test data that would have caught this
4. **Create or Extend Validator** (validators/) to detect this bug class automatically in Layer 0
5. **Verify** that the new validator catches the bug in Layer 0
6. **Commit** with message format:
   ```
   [Layer 2 → Layer 1 Feedback] <page>: <issue> + new validator #XX

   Scenario: <read/write/additional>: <scenario name>
   Root cause: <technical detail>
   Fix: <what changed in code>
   Seeding: <what changed in test data>
   Validator: <which new checks added to which gate>
   
   This prevents recurrence by catching the bug class at Layer 0.
   ```

**Rationale:** Every Layer 2 finding teaches Layer 0 a new pattern. This closes the loop so Layer 0 becomes smarter with every deployment.

**Example:**

```
Layer 2 finds: logbook.html doesn't show "Create Entry" button for workers without logbook_write permission
  ↓
Document: Read path / permission check scenario
  ↓
Fix code: Add check for hive_role in permissions before rendering button
  ↓
Update seeding: Create test worker with logbook_read-only role
  ↓
Create validator: New check in validate_permissions.py "UI elements match RLS rules"
  ↓
Verify: Layer 0 now catches permission mismatches automatically
  ↓
Commit: Platform becomes more resilient
```

---

## Complete Workflow (Unified Mega Gate)

### Scenario 1: Normal Development Cycle

```
1. Make code change
   ↓
2. Run Fast Platform Guardian
   python run_platform_checks.py --fast
   ↓
   PASS → Continue
   FAIL → Fix code/schema, retry step 2
   ↓
3. Open WorkHive Tester
   http://127.0.0.1:5000/workhive
   ↓
   a) Click LIVE TOOLS → Open affected page
   b) Manual walkthrough → screenshot any regressions
   c) Click FLOW SPEC RUNNER → Run affected flows
   ↓
   All flow specs PASS? Continue
   Any FAIL/WARN? → Fix code, retry steps 2-3
   ↓
4. Run Layer 2 E2E Tests (affected pages only)
   python e2e_runner.py --page <affected>
   ↓
   PASS → Ready to commit
   FAIL → Document bug → Go to Layer 2→L1 feedback loop
```

### Scenario 2: Pre-Deployment (Mega Gate Full)

```
1. Fast Guardian
   python run_platform_checks.py --fast
   ↓
2. WorkHive Tester
   Click SMOKE TEST → all pages, 2 min
   ↓
3. Layer 2 E2E Full Run
   python e2e_runner.py --tier 1 --tier 2 --tier 3 --tier 4 --tier 5 --report
   ↓
   All 3 layers PASS → Safe to deploy
   Any FAIL → Investigate via Layer 2→L1 feedback loop
```

### Scenario 3: Layer 2 Finds Bug (Feedback Loop)

```
1. Layer 2 E2E test fails
   e.g., logbook.html offline queue doesn't sync on reconnect
   ↓
2. Document in findings.json
   {
     "layer": 2,
     "page": "logbook",
     "path": "additional/offline",
     "scenario": "offline queue sync",
     "root_cause": "IndexedDB transaction not atomic on concurrent writes",
     "status": "NEEDS FIX"
   }
   ↓
3. Fix code
   e.g., Add transaction lock to offline-queue helper
   ↓
4. Update seeding
   Add test data: offline transaction with 3 concurrent writes
   ↓
5. Create validator
   Add to validate_offline_queue.py:
   - Check all offline-queue helpers have transaction locks
   - Check IndexedDB operations are atomic
   ↓
6. Verify Layer 0 now catches it
   python run_platform_checks.py --fast
   ↓
   New validator PASS
   ↓
7. Commit
   [Layer 2 → Layer 1 Feedback] logbook: offline queue sync
   ...
   ↓
8. Update memory
   Record what was learned in /skill-name or memory file
```

---

## Layer Integration Points

### Data Flow Between Layers

```
Layer 0 (Fast Guardian)
├─ Detects: schema breaks, code violations, config issues
├─ Output: platform_health.json
└─ Feeds → Layer 1

Layer 1 (WorkHive Tester)
├─ Detects: UI regressions, visual bugs, happy-path failures
├─ Output: test notes, screenshots, findings.json
└─ Feeds → Layer 2 (if architectural) or Layer 2→L1 loop (if new finding)

Layer 2 (E2E Tests)
├─ Detects: journey failures, edge cases, permission gaps, offline bugs
├─ Output: e2e_results.json, e2e_report.md
└─ Feeds → Layer 2→L1 loop (create new validator)
    └─ Feeds back → Layer 0 (new validator registered)
```

### Shared Test Data

All layers use the same seeding database:
```
test-data-seeder/
├─ seeders/catalogs.py      # Catalog tables (equipment, standards)
├─ seeders/workers.py       # Test workers (roles, hives, permissions)
├─ seeders/data.py          # Fixture data (logbook entries, inventory items, etc.)
└─ flows/                   # Journey flows + E2E tests
```

**Update Pattern:** When Layer 2 finds a gap, update seeding FIRST, then validator. This ensures the next test run has proper test data.

---

## Execution Contexts

### Context 1: Local Development (Tester's Workstation)

```bash
# Fast Guardian
python run_platform_checks.py --fast

# Open Tester in browser
http://127.0.0.1:5000/workhive

# Run specific E2E test
python e2e_runner.py --page logbook --path write
```

**Time:** 90 sec (fast) + 5 min (manual) + 15 sec (E2E page) = ~6 min for one change

### Context 2: Pre-Commit Validation

```bash
# Before git commit
python run_platform_checks.py --fast
python e2e_runner.py --tier 1                    # Fastest comprehensive check

# If FAIL, fix + retry both commands
# If PASS, commit
```

**Time:** 90 sec + 90 sec = ~3 min

### Context 3: CI/CD Pipeline (Pre-Deploy)

```bash
# Full validation
python run_platform_checks.py --full             # 5-8 min, all validators
python e2e_runner.py --tier 1 --tier 2 --tier 3 --tier 4 --tier 5 --report  # ~5 min

# If any FAIL, block deploy
# If all PASS, proceed to production
```

**Time:** ~13 min total

### Context 4: Regression Testing (Weekly)

```bash
# Full suite + detailed reporting
python run_platform_checks.py --full
python e2e_runner.py --tier 1 --tier 2 --tier 3 --tier 4 --tier 5 --report --mobile

# Generate regression report comparing against baseline
# Identify new failures vs baseline
```

**Time:** ~20 min

---

## What's Missing / Overlaps

### Overlaps (By Design)

| Check | Layer 0 | Layer 1 | Layer 2 | Rationale |
|-------|---------|---------|---------|-----------|
| **No console errors** | ✓ (via headless Playwright) | ✓ (manual walk) | ✓ (e2e_helpers.check_console_errors) | Catch at multiple levels |
| **Mobile responsive** | ✓ (CSS analyzer) | ✓ (manual 375px) | ✓ (verify_no_horizontal_scroll + tap targets) | Different angles: code, UI, interaction |
| **Form validation** | ✓ (schema checks) | ✓ (fill+submit flow) | ✓ (write path validation scenario) | Code level + UI level + journey level |
| **API error handling** | ✓ (edge fn contracts) | ✓ (manual network throttle) | ✓ (API mocking in write scenario) | Catches code issues + interaction issues |

**Why overlaps are good:** Each layer catches a different class of issue. A validator might pass (code correct) but Layer 1 finds a UI bug (missing label). Or Layer 2 finds an edge case the code didn't anticipate.

### Gaps (To Address)

| Gap | Impact | Solution | Timeline |
|-----|--------|----------|----------|
| **Tier 2-5 E2E tests not yet written** | Can't catch analytics/admin/landing bugs at journey level | Implement flows e2e_*.py files | Phase 2-4 (2-3 weeks) |
| **No concurrent user testing** | Can't detect race conditions in multi-user scenarios | Layer 2 deferred to Phase 2 (needs test harness) | Post-Phase 1 |
| **No performance profiling** | Can't detect render lag, memory leaks | Layer 2 phase 2 can add perf checks via e2e_helpers.measure_page_load_time | Phase 2 |
| **No cross-page integration tests** | Logbook→Inventory flows tested independently, not together | Layer 2 phase 4 adds integration tier | Phase 4 |
| **No mobile app testing** | Only web (Playwright). No iOS/Android. | Out of scope for now (web-first platform) | Future milestone |

---

## Command Reference (All Unified)

```bash
# ──── LAYER 0: Fast Platform Guardian ────────────────────────────
python run_platform_checks.py --fast              # 160 validators, ~90 sec
python run_platform_checks.py --full              # All categories, ~5-8 min

# ──── LAYER 1: WorkHive Tester (Interactive) ────────────────────
# Open browser: http://127.0.0.1:5000/workhive
# Available panes: LIVE TOOLS PAGE, FLOW SPEC RUNNER, SMOKE TEST, MOBILE TESTS, SIGNUP TESTS, LAYER 2 RUNNER

# ──── LAYER 2: E2E Comprehensive Tests ─────────────────────────
python e2e_runner.py --tier 1                     # Core workflows only, ~90 sec
python e2e_runner.py --tier 1 --tier 2            # Tiers 1-2, ~2 min
python e2e_runner.py --tier 1 --tier 2 --tier 3 --tier 4 --tier 5  # All tiers, ~5 min
python e2e_runner.py --page logbook               # Single page, ~15 sec
python e2e_runner.py --page logbook --path write  # Single page, single path, ~5 sec
python e2e_runner.py --page logbook --path write --report  # With markdown report
python e2e_runner.py --mobile                     # Mobile viewport tests only

# ──── UNIFIED MEGA GATE (All Layers) ──────────────────────────
# Recommended: Run in sequence
python run_platform_checks.py --fast && \
python e2e_runner.py --tier 1 && \
echo "✓ Mega Gate PASS - Ready to commit"
```

---

## Standing Rule Summary (Non-Negotiable)

**Every Layer 2 E2E finding that Layer 0 missed becomes a new Layer 0 validator.**

This ensures:
- ✓ Bugs found once are never missed again
- ✓ Each layer makes every other layer smarter
- ✓ Platform quality improves continuously
- ✓ Test data evolves with real user paths

**Process:**
1. Layer 2 finds bug (journey test fails)
2. Fix code + update seeding
3. Create/extend validator (Layer 0)
4. Verify validator catches it
5. Commit with feedback-loop message
6. Layer 0 is now smarter for next developer

---

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Layer 0 PASS rate | 100% | 160/160 validators (baseline) |
| Layer 1 FAIL rate | 0% | 24/24 flows (baseline) |
| Layer 2 coverage (pages) | 35/35 | 1/35 (logbook example) |
| Layer 2 coverage (scenarios) | ~380 | ~12 (logbook example) |
| Layer 2→L1 feedback loop active | Yes | Starting Phase 2 |
| New validators from Layer 2 findings | 5-10 per phase | 0 (Phase 1 infrastructure) |

---

## Phase Roadmap

### Phase 1: Infrastructure (THIS SESSION — DONE ✓)
- [x] Fast Platform Guardian baseline (160 validators)
- [x] WorkHive Tester 6-pane interface
- [x] E2E test matrix (35 pages, 380 scenarios)
- [x] E2E runner + helpers library
- [x] Example test (logbook)
- [x] Integration guide
- [x] Standing rule documented

### Phase 2: Tier 1 Implementation (NEXT)
- [ ] Implement e2e_inventory.py, e2e_pm.py, e2e_hive.py, e2e_community.py, e2e_marketplace.py, e2e_project_manager.py
- [ ] Run Layer 2 tests, find bugs, apply feedback loop
- [ ] Create 5-10 new validators from findings
- [ ] Baseline: 35 PASS / 0 FAIL on Tier 1

### Phase 3: Tier 2-4 Implementation
- [ ] Implement analytics, admin, landing page tests
- [ ] Find 10-15 more bugs
- [ ] Create 10-15 new validators
- [ ] Baseline: 100+ PASS / 0 FAIL

### Phase 4: Tier 5 + Integration Tests
- [ ] Implement specialized page tests
- [ ] Add cross-page integration tests (logbook→inventory, etc.)
- [ ] Find remaining bugs
- [ ] Full platform coverage: 35/35 pages tested

---

## Files in This Architecture

**Layer 0 (Validators):**
- `validators/` — 160 validators registered in run_platform_checks.py

**Layer 1 (Tester):**
- `test-data-seeder/app.py` — Flask app with 6 panes
- `test-data-seeder/flows/` — 24 journey specs

**Layer 2 (E2E):**
- `test-data-seeder/E2E_TEST_MATRIX.md` — Test matrix (35 pages, 380 scenarios)
- `test-data-seeder/e2e_runner.py` — Test orchestrator
- `test-data-seeder/e2e_helpers.py` — Reusable test methods
- `test-data-seeder/flows/e2e_logbook_comprehensive.py` — Example implementation
- `test-data-seeder/LAYER2_INTEGRATION.md` — Integration guide
- `test-data-seeder/flows/e2e_inventory.py` — (To be created)
- `test-data-seeder/flows/e2e_pm.py` — (To be created)
- ... etc.

**This Document:**
- `UNIFIED_MEGA_GATE.md` — Architecture + standing rule (this file)

---

## Next Step

**Proceed to Phase 2:** Implement Tier 1 E2E tests (7 core pages).

For each page:
1. Copy `flows/e2e_logbook_comprehensive.py` pattern
2. Adapt selectors for page-specific fields
3. Run tests, document findings
4. Apply Layer 2→L1 feedback loop for each bug
5. Commit with feedback-loop message

**Start with:** `flows/e2e_inventory.py` (most critical after logbook)
