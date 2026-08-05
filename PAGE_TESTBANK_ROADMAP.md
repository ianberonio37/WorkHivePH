# PAGE TESTBANK ROADMAP — 200 live-MCP scenarios per production page, 22 pages, 4,400 rows

_Opened 2026-08-05. Ian: "get 200 scenarios each for every production pages … same manner using the
framework with anti-drift discipline and momentum discipline … author those scenarios first [walk
later] … lay it out so that we have an objective 200 scenarios each … itemized each and with
percentage completion per page so that you won't drift."_

The marketplace bank (877 scenarios, `live_mcp_registry.json`, `MARKETPLACE_ITERATION_ROADMAP.md`)
is the proven instrument. This arc runs the same instrument over every other production page. The
marketplace bank stays its own bank, on its own board — merging 4,400 fresh owed rows into it would
bury both numbers.

---

## §0 · ANTI-DRIFT RAILS (read first, every session)

Rules 1–6 are inherited **verbatim** from `MARKETPLACE_ITERATION_ROADMAP.md` §0 and enforced by the
same gate (`tools/validate_live_mcp_bank.py`, now multi-bank): typed evidence; evidence expires with
the code under it (R4/R4b/R4c/R7); a structural probe may not settle a behavioural oracle (R6);
LIVE-MCP walks only bank; stale is visible, never absorbed (R5); verify the instrument before the
page. Four new rails, because this arc's failure mode is **authoring fiction at scale** — 4,400
grounded rows and 4,400 plausible ones look identical in a JSON file:

| # | rule | what enforces it |
|---|---|---|
| A7 | **A subject must be OBSERVED, not assumed.** Every anatomy entry carries `seen:{how, ref}` — a file:line or a live enumeration. | `build_page_live_mcp_bank.py` refuses to build a page whose anatomy has an unsourced subject. |
| A8 | **Exactly 200 rows, or the build fails.** Under-supply = incomplete Ground pass; over-supply = the ranked tail is recorded `deferred` with its reason. | The generator's frame arithmetic is asserted at build time; `--selftest` proves it fires. |
| A9 | **A claim already proven in another bank INHERITS its evidence; it is never re-walked.** Keyed on `(url, oracle, persona/state)`. | The generator's inherit pass copies the original evidence (ref, sha, fn_digests) so it **expires with the original**. |
| A10 | **A vacuous cell is recorded, never counted.** An oracle with no subject on a page (public-feed has no writes) is swapped for a ranked-tail row and the vacuity is recorded in the bank's `declared_na` list with its reason + receipt. | The generator refuses an `na` entry without `reason` + `replace_with`; the bank still totals exactly 200 scored rows. |

> Named A7–A10 (arc rails) rather than R7–R10 because the validator already owns R7 — "a layer/seam
> claim must depend on what it actually rests on" — and two rules sharing one name is itself drift.

**The one line to remember:** *a scenario without a receipt for its subject is a tour, not a test.*

---

## §1 · THE FRAME — fixed arithmetic, page-specific fill

Identical for all 22 pages. What differs per page is the **subjects** its anatomy supplies
(`page_bank_anatomy/<page>.json`): 4 layers · 5 seams · ≥3 views · ≥3 components · ≥3 journey
personas · 2 identity personas · 6 bespoke invariants · 8 bespoke domain truths. Oracle text for
the templated families is taken **verbatim** from the `ORACLES` table in
`tools/build_live_mcp_registry.py` — one source of truth, imported, never copied.

Row numbering is fixed platform-wide, so `PB-<page>-###` means the same thing on every page:

| rows | family | mandate | expansion |
|---|---|---|---|
| 1–20 | CA layer-contract | F1 | 4 layers × (envelope_shape · status_body_agreement · idempotency · ordering_totality · units_declared) |
| 21–40 | CB seam | F1 | 5 seams × (value_survives · name_survives · null_semantics · partial_write) |
| 41–54 | CC failure-injection | F1 | 2 views × (fail_500 · fail_401 · fail_timeout · fail_partial · fail_slow · fail_offline · fail_null_field) |
| 55–60 | CD invariant | F1 | 6 bespoke, written per page in the anatomy |
| 61–70 | CE ufai-U | F2 | 2 views × (one_vocabulary · source_chip_true · units_visible · no_raw_enum · number_explained) |
| 71–82 | CF ufai-F | F2 | 2 views × (effect_in_db · effect_visible · count_matches_source · money_matches_ledger · idempotent_repeat · cross_surface_agreement) |
| 83–92 | CG ufai-A | F2 | 2 views × (offline_refusal · retry_path · rate_limit_legible · fallback_engaged · slow_honest) |
| 93–102 | CH ufai-I | F2 | 2 identity personas × (bola_object · bfla_function · tenant_boundary · jwt_not_body · boundary_not_emptiness) |
| 103–110 | CI domain-truth | F2 | 8 bespoke, written per page in the anatomy |
| 111–125 | CJ ui-layout | F3 | 3 views × (w390_overflow · w641_overflow · w1280_overflow · tap_target_44 · safe_area) |
| 126–140 | CK ui-state | F3 | 3 components × (component_loading · component_skeleton · component_disabled · component_busy · component_populated) |
| 141–155 | CL ui-visual | F3 | 3 views × (contrast_wcag · contrast_apca · focus_visible · reduced_motion · icon_only_name) |
| 156–170 | CM ux-comprehension | F4 | 3 views × (what_is_this_number · what_happens_next · what_does_it_cost · why_refused · reward_explained) |
| 171–185 | CN ux-journey | F4 | 3 journey personas × (first_run_to_value · repeat_visit · cross_surface_handoff · two_sided_same_object · abandon_resume) |
| 186–200 | CO ux-recovery | F4 | 3 views × (double_tap · back_out · session_died · wrong_then_fix · did_it_land) |

**F1 60 + F2 50 + F3 45 + F4 45 = 200.** The generator fails on any other number (A8).

---

## §2 · THE %-BOARD — computed, never typed

**Every number comes from `python tools/validate_live_mcp_bank.py --report`.** Denominator rule:
green ÷ (green + owed), **stale excluded** so drift shows instead of being absorbed. A hand-edited
percentage in this document is the drift this document exists to prevent — this section names the
command and holds only the *targets*:

- **Per page:** all 22 pages to 100% green over non-stale — the walk arc's target.
- **Per family:** the walk drives the **lowest-green family across pages**, not page-by-page only —
  a low family across N pages is usually ONE unadopted central component, never N page bugs
  (CENTRALIZE-FIRST). Known cohort already found at authoring time: `analytics` / `alert-hub` /
  `shift-brain` render the same verdict/hero chrome under `an-`/`ah-`/`sb-` prefixes — a defect on
  one is asserted against all three.
- **A page is not done at one green family.** Page-% AND family-% must both be read; F3 100% over
  F1 20% is pretty layout over an unproven stack.

Roster (22): index · hive · logbook · inventory · pm-scheduler · project-manager · dayplanner ·
asset-hub · analytics · alert-hub · skillmatrix · shift-brain · voice-journal · assistant ·
community · public-feed · achievements · engineering-design · resume · report-sender ·
project-report · analytics-report.

**Out of scope, recorded not skipped:** design-system, symbol-gallery, validator-catalog,
architecture, status, audit-log, ai-quality, llm-observability, agentic-rag-observability (ops/meta
consoles), and the marketplace surfaces (they keep their own 877-row bank).

**Un-grounded subjects (A7 holds them open):** analytics' full chart-source list, assistant's panel
ids, resume's anon persona, report-sender's send transport — each carries a `static-partial` seen
ref and MUST be re-grounded live before its rows may bank green.

---

## §3 · THE ITERATION LOOP (momentum drive)

```
AUTHORING (this arc): per page — transcribe anatomy (A7 receipts) → generate 200 (A8/A10)
   → validate (0 invalid) → next page → arc closes at 22 × 200 authored, all owed
WALK (next arc): pick the lowest-green family across all banks
   → walk its owed rows on the LIVE MCP browser (live-state-runner.js lenses)
       → fix what it finds → re-walk to green with typed evidence
           → --accept the per-bank ratchet → next family
```

- `.momentum_drive` stays armed; the Stop guard blocks a turn-end while a known unit exists.
- The multi-bank gate runs inside `run_platform_checks.py` (`live_mcp_bank`), so drift appears in
  the normal suite.
- Every session ends by updating **§4 NEXT** and mirroring it into the Memento handoff.

---

## §4 · NEXT

```
NEXT: THE WALK ARC — drive all 22 banks to 100% green via LIVE MCP walks (Ian, 2026-08-05:
  "we use live mcps to achieve and complete all of them"). Pick the lowest-green family across
  banks (§3 loop); reuse live-state-runner.js lenses; typed evidence per row; --accept per bank.
  AUTHORING DONE 2026-08-05 (this arc, all in one session):
    · multi-bank validator: process_bank() per registry, per-bank baseline {"banks":{...}} with
      legacy flat shape read as marketplace; classify()/R1-R7/ratchet untouched. Marketplace's
      674<752 red pre-exists this arc (the parallel walking session's stale drift — its unit).
    · tools/build_page_live_mcp_bank.py — fixed 200-frame (60/50/45/45), ORACLES imported from
      build_live_mcp_registry (one vocabulary), A7/A8/A10 + strict-oracle selftests all fire.
    · page_bank_anatomy/*.json x22 — every subject carries seen{how,ref}; 308 bespoke oracles
      (6 invariants + 8 domain truths per page); writes classified per the Y1b disposition.
    · banks/*_live_mcp_bank.json x22 — 22 x 200 = 4,400 rows, ALL owed, 0 invalid, 105 declared_na
      recorded with receipts, 10-row random spot-check traced clean.
  GROUND CORRECTIONS BANKED DURING AUTHORING (the substrate beat my greps 5 times):
    · pm-scheduler reaches embed-entry via RAW fetchWithTimeout (:2279) — bypasses functions.invoke;
      same pattern on resume (:1140) and skillmatrix (embedSkillEntry). THREE pages bypass the
      shared invoke wrapper = a cross-page walk target.
    · the compliance window is 90d (p_period_days:90 at pm-scheduler:1386), not 30d.
    · report-sender's transport IS known: send-report-email + scheduled-agents + voice pair
      (voice-report-intent/voice-transcribe) + resendReport. A7 hold resolved from substrate.
    · alert-hub writes amc_briefings.update + anomaly_signals.update (not automation_log).
    · inventory stock rule sharpened: qty_on_hand == newest txn qty_after via inventory_deduct/
      inventory_restock RPCs (ARC DI 10.5 seesaw).
  REMAINING A7 HOLDS (rows exist, cannot bank green until re-grounded live): analytics chart
    sources · assistant panel ids · resume anon-upload persona.
  SHARED-COMPONENT COHORT (walk once, assert three times): an-/ah-/sb- verdict chrome on
    analytics / alert-hub / shift-brain.
  SUITE VERDICT AT ARC CLOSE (fast suite, 2026-08-05): 566 PASS · 14 FAIL · 155 SKIP.
    Both REGRESSIONS in this arc's window were cleared the same session: substrate freshness
    (rebuilt -> 786 chunks fresh, PASS) and storage-key registry (transient of the parallel
    walking session's mid-edit state; exits 0). The remaining 12 standing FAILs (em-dash on 8
    learn pages, etc.) PRE-DATE this arc and sit in the full-gate drive Ian explicitly deferred
    to the marketplace walk's arc close ("reserve the full gate until the walk is done",
    2026-08-04) - named here so the deferral is a record, not a silence.
```

---

## §5 · OPEN FOR IAN

- Nothing new. The two §5 blocks in `MARKETPLACE_ITERATION_ROADMAP.md` are settled by recall for
  THIS arc's authoring: the APCA "273/552" figure predates the corrected floor table in
  `live-state-runner.js` (re-measure, then decide); offline-write posture follows the Y1b
  disposition principle (capture queues; financial/approval/role writes refuse with clarity), and
  each anatomy's `writes[]` is classified accordingly.
- Ian's standing gates: commit/push, prod deploys.
