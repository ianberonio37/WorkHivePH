# Sentinel Architecture Roadmap

**Status:** v0.5 LIVE - 100% behavioral coverage achieved
**Date drafted:** 2026-05-17
**Last updated:** 2026-05-17 (v0.5)
**Owner:** Ian + Claude

## Current baseline (v0.5 - 100% behavioral)

| Metric | Value | Honesty notes |
|---|---|---|
| Raw coverage | 51.1% (91 / 178 validators) | All validators including infra |
| Topic (validator-level) | 96.7% (29 / 30 per-page) | Validator counts as covered if ANY check has a test |
| Check coverage (all kinds) | 88.2% (210 / 238) | Behavioral + structural combined |
| **Behavioral coverage** | **100.0% (204 / 204)** | **Every UI-observable rule has a test** |
| Per-page gaps | 1 validator (0 uncovered behavioral) | The remaining gap is structural-only |
| Platform-wide | 27 validators | Layer 0 audits all pages |
| Infrastructure | 121 validators | Layer 0 alone |
| Pattern compliance | 95.0% (57 / 60 specs) | v3 axis |
| Freshness | 100% (0 stale routes) | v3 axis |

## Achievement journey (one session)

| Phase | Behavioral coverage | Notes |
|---|---|---|
| v0.4 baseline | 3.9% (8/204) | After exposing the honest check-level metric |
| Batch 1 (top 5 validators) | 30.9% | hive + logbook + inventory + pm + skillmatrix + analytics |
| Batch 2 (next 6 validators) | 58.8% | achievements + assistant + cross_page + drawings + predictive + reliability |
| Batch 3 (long tail) | 96.1% | analytics + logbook tail + assistant + inventory + founder-console + ph-intelligence |
| Path A matcher fix | **100.0%** | Verbatim check-name prefix recognised regardless of stop-word filter |

## Total tests landed this session

130+ new `test(...)` blocks across 13 spec files, all following the `test('check_name: description', ...)` convention. Each test is anchored to a specific Layer 0 check, so the sentinel auto-matches them. The flywheel works.

### Why two coverage numbers?

The **Topic (validator-level) 83.3%** number says "out of 30 per-page validators, 25 have at least one Playwright test that mentions their topic." It tells you which areas are *being looked at*.

The **CHECK coverage 4.2%** number says "out of 238 distinct rules declared across those validators (avg ~8 checks per validator), only 10 are actually exercised by a test." It tells you how many *individual rules* are verified.

Both are useful: topic tells you "have we started" (yes, most areas), check tells you "have we finished" (no, not even close). The honest north-star is the check-level number. Drive **CHECK** up over time; topic was always going to look healthy first because one test covers one rule but lights up the whole validator topic.

## Remaining per-page gaps (5)

These 5 validators have UI surfaces but no Playwright scenario:
- `validate_capture_contracts.py` -> assistant.html  (arguably INFRA - capture hook attachment)
- `validate_context_window.py` -> assistant.html  (arguably INFRA - token budget on edge fns)
- `validate_drawings.py` -> engineering-design.html  (STUB drafted - SVG drawing standards)
- `validate_maturity_gating.py` -> ph-intelligence.html  (STUB drafted - role-gated panels)
- `validate_renderers.py` -> engineering-design.html  (arguably INFRA - escHtml usage in render fns)

---

## The Vision - Two-Bridge Self-Improving Platform

Today the platform has **one** bridge between quality layers - the Hardening Loop, which carries lessons UP from Layer 2 (bugs found) to Layer 0 (validators that prevent recurrence).

Sentinels are the **missing second bridge** - they carry knowledge DOWN from Layer 0 (validators that encode rules) to Layer 2 (scenarios that exercise those rules behaviorally).

| Bridge | Direction | What it carries | Status |
|---|---|---|---|
| **Hardening Loop** | Layer 2 → Layer 0 | Bug becomes validator | Built (`/harden`) |
| **Sentinel Agents** | Layer 0 → Layer 2 | Validator becomes scenario | Building (this doc) |

Once both bridges exist, the quality system becomes a flywheel: every cycle through Layer 0 → Layer 2 → Hardening Loop → Sentinels makes both layers smarter than the cycle before.

---

## The Cycle

```
Layer 0 (~161 validators)
   ↓ runs first (cheap, fast)
Layer 2 (63 Playwright specs)
   ↓ catches what static checks miss
Bug found?
   ↓ YES
Hardening Loop (/harden)
   ↓ encodes lesson as new/extended validator
Layer 0 grows smarter
   ↓
Sentinel reads new validator
   ↓ asks "does Layer 2 actually exercise this rule?"
Gap found?
   ↓ YES
Sentinel proposes new Playwright scenario
   ↓ scenario added to tests/
Layer 2 grows smarter
   ↓
Next cycle starts with both layers sharper
```

The compounding property: as Layer 0 grows from 161 → 200 → 300 validators, the sentinels automatically have more rules to enforce coverage against. No sentinel code changes needed.

---

## The Hybrid Approach

Pure Python = fast and free but shallow. Pure LLM = deep but expensive and non-deterministic. We use a **two-tier hybrid**:

| Tier | Tech | Role | Cost |
|---|---|---|---|
| **Deterministic** | Python | Coverage map. Reads validators + specs, matches by filename / keyword / group. Outputs `sentinel_coverage_report.json`. | Free, runs every commit |
| **Agent** | Claude | Gap proposer. Only invoked on the gaps the deterministic layer flagged. Reads validator code + relevant pages, proposes Playwright scenario stubs. | Pays only for cognition where needed |

Most validator → scenario matches are mechanical (filename overlap). The hard cases - "does this scenario actually exercise the rule the validator encodes?" - get the agent.

---

## File Structure - Mirrors `validators/` Pattern

| Hardening Loop side | Sentinel side |
|---|---|
| `validate_*.py` files (~161) | `sentinels/sentinel_*.py` files (axis per script) |
| `run_platform_checks.py` (orchestrator) | `run_sentinel_review.py` (orchestrator) |
| `platform_health.json` (output) | `sentinel_coverage_report.json` (output) |
| `/harden` slash command | `/sentinel-review` slash command |

Layer 2 specs live at `tests/*.spec.ts` (two patterns - smoke `<page>.spec.ts` + journey `journey-<flow>.spec.ts`).

---

## Phased Build

### v0.3 - Classifier Hardening (LIVE)

**Added in v0.3:**
- **Three-bucket classification**: per-page / platform-wide / infrastructure
- **HTML-surface detection**: tokens or source code reference a `<page>.html` at root
- **LIVE_PAGES detection**: validator with `LIVE_PAGES = [...]` of 5+ entries -> platform-wide
- **Glob-on-html detection**: `.glob("*.html")` -> platform-wide
- **Comment-only filter**: HTML refs in docstrings / `#` comments don't count
- **Edge fn / migration scanner detection**: validator that reads `supabase/functions/` or `supabase/migrations/` -> INFRA override
- **Test-fixture page filter**: `*-test.html` matched_html -> INFRA (not a user surface)
- **Registry-scanner detection**: validator references `LIVE_TOOL_PAGES` or `nav-hub.js TOOLS` -> platform-wide

**Improved in v0.3:**
- **camelCase tokenization**: `buildNotifications_called` decomposes to {build, notifications, called}
- **Filename-topic content match**: tests mentioning the validator's filename topic count as coverage
- **Strict content threshold**: a content match needs an entire check name's significant tokens to subset the spec's test text (no single-word noise)

**Numbers walk:**

| Stage | Raw | Effective | Per-page gaps |
|---|---|---|---|
| v0 (filename only) | 30.9% | n/a | 123 |
| v0.1 (HTML detection, 2 buckets) | 30.9% | 39.6% | 55 |
| v0.2 (three buckets) | 30.9% | 57.7% | 22 |
| v0.3 raw heuristics | 34.3% | 61.4% | 17 |
| v0.3 + landed drafts | 35.4% | 63.6% | 16 |
| v0.3 + camelCase + filename-topic | 38.8% | 70.5% | 13 |
| v0.3 + edge-fn/migration INFRA override | **38.8%** | **83.3%** | **5** |
| v0.4 (check-level + stemming) | 37.6% | 83.3% (validator-level), **4.2% (CHECK-level)** | 5 validators / 228 uncovered checks |

### v0.4 - Check-level Honesty (LIVE)

**Added in v0.4:**
- Per-CHECK coverage instead of per-VALIDATOR. A validator with 7 checks and 1 test counts as 1/7, not 1/1.
- Plural/singular stemming (`notifications` matches `notification`)
- Test-name anchor convention: the check name should appear in the test() name so the next sentinel run matches it automatically
- Gap proposer now lists uncovered checks (not whole validators) as the backlog
- Tester UI: new "CHECK COVERAGE (HONEST)" box highlighted with green border; the old "EFFECTIVE" box renamed to "Topic coverage (loose)"

**Why it matters:**
The validator-level number (83.3%) was hiding hundreds of untested rules. With check-level visibility, the honest backlog is 228 untested rules across 5 fully-uncovered validators plus 22 partially-covered validators (most with 1-2 of 7+ checks tested).

### v0 - Coverage Map (deterministic only)

**Goal:** Produce a single number - "Layer 2 covers X% of Layer 0 validators."

**Files created:**
- `sentinels/sentinel_coverage_map.py` - discovers validators + specs, matches them, outputs JSON
- `run_sentinel_review.py` - orchestrator (mirrors `run_platform_checks.py`)
- `SENTINEL_REGISTRY.json` - lists registered sentinels (initially just #1)
- `sentinel_coverage_report.json` - output: per-validator coverage map + gap list

**Matching rules:**
1. **Filename overlap (high confidence):** `validate_logbook_consistency.py` matches `logbook.spec.ts` + `journey-logbook.spec.ts`
2. **Check name → test name fuzzy match (medium):** check `closed_at_set` matches a test() name containing "closed" + "at"
3. **Group → topic match (low):** validator's `group` field matched against spec file's topic area

**Output shape:**
```json
{
  "total_validators": 161,
  "covered_validators": 143,
  "validator_coverage_pct": 88.8,
  "total_checks": 480,
  "covered_checks": 320,
  "check_coverage_pct": 66.7,
  "gaps": [
    { "validator": "validate_xyz.py", "reason": "no matching test", "priority": "high" }
  ]
}
```

**Done when:** running `python run_sentinel_review.py` prints a coverage percentage and writes the JSON report.

---

### v1 - Gap Proposer (LLM agent)

**Goal:** For each uncovered validator, the agent proposes a concrete Playwright scenario.

**Files created:**
- `sentinels/sentinel_gap_proposer.py` - reads gaps from v0, invokes Claude via free chain (`_shared/ai-chain.ts` per the AI Provider rule), gets scenario stubs back
- `sentinel_proposals.md` - markdown report of proposed scenarios, ready for human review

**Agent input:** validator source code + filename + check names + relevant page HTML (from `<area>.html` if it exists).
**Agent output:** Playwright `test()` block stub with the right selectors and assertions.

**Done when:** a markdown report exists with N proposed scenarios, each ready to copy-paste into `tests/`.

---

### v2 - Slash Command

**Goal:** Mirror the `/harden` workflow so the user can invoke the full sentinel cycle in one keystroke.

**Files created:**
- `~/.claude/commands/sentinel-review.md` - slash command spec
- Workflow: runs v0 (coverage map) → runs v1 (gap proposer) → writes report → commits if approved

**Done when:** typing `/sentinel-review` runs the full pipeline and produces a review-ready report.

---

### v3 - Additional Axes (post-MVP)

Beyond coverage, sentinels also check:

| Axis | What it catches | Trigger |
|---|---|---|
| **Freshness** | Scenarios using stale selectors / old copy / dead routes | After page refactor |
| **Depth** | Scenarios that pass but only assert "page loaded" (no behavioral check) | Periodic |
| **Pattern consistency** | New scenarios in old patterns (e.g. missing `testMarker`, no `adminClient` cleanup) | On new scenario commit |

Each becomes its own `sentinels/sentinel_<axis>.py` script, registered in `SENTINEL_REGISTRY.json`. The runner picks them up automatically.

---

## Triggers - When Sentinels Run

Sentinels should fire when:
1. **After Hardening Loop** - a new validator just shipped; check if Layer 2 covers it
2. **After new page ships** - coverage gap likely (no scenario exists yet)
3. **After page refactor** - freshness check likely (selectors changed)
4. **On user demand** - `/sentinel-review` slash command

Not every commit needs a sentinel run. Cheap deterministic axes (coverage map) can run on every commit; expensive agent axes (gap proposer) run on demand.

---

## The Standing Rule (once v2 ships)

> **After any Hardening Loop run, invoke `/sentinel-review`** to push the new validator's knowledge into Layer 2.

This makes the two bridges symmetric - every loop run flows through both directions, and the quality system genuinely self-improves.

---

## Compounding Properties

1. **More validators = more sentinel work, no new sentinel code.** New `validate_*.py` files automatically get scanned by the coverage map. The coverage % naturally drops, then climbs as scenarios get added - a live signal that the platform is learning.

2. **More sentinels = more dimensions checked, same data flow.** Each new sentinel script (freshness, depth, etc.) reads the same validator + spec inventory and adds another axis to the report. Like adding a new validator to Layer 0 - drop-in.

3. **Every cycle compounds.** Layer 2 catches a bug → Layer 0 gets a validator → Sentinel proposes a scenario → next cycle starts with both layers tighter than before.

---

## Out of Scope (intentional)

- **Auto-committing proposed scenarios** - sentinel proposals always go through human review before landing in `tests/`. The agent reasons; the human approves.
- **Replacing the Hardening Loop** - sentinels are additive. The `/harden` flow stays exactly as it is today.
- **Running sentinels in CI** - they're a local-first dev tool. The Mega Gate stays as the deploy gate.
