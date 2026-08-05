# MARKETPLACE ITERATION ROADMAP — the 877-scenario bank, and the rails that keep it honest

_Opened 2026-08-04. Ian: "add 500 diverse live mcps in test banks, make it in categories of system design
and full architecture layers, UFAI, UI, UX, we will reiteratively improve the entire marketplace. then lock
it in our roadmap framework with anti-drift discipline and momentum drive."_

---

## §0 · ANTI-DRIFT DOCTRINE (read first, every session)

The four rules below already existed in prose — `DEEPWALK_JOURNEY_BUGHUNT_ROADMAP.md` §0 and
`CORRECTNESS_SCOREBOARD.md` §6.0 say them plainly. **Prose did not hold.** The bank read 343 green / 0 owed
and the true figure was 124. So each rule now names the mechanism that enforces it, and a rule without a
mechanism is a wish.

| # | rule | what enforces it |
|---|---|---|
| 1 | **A green cell must say WHY it is green.** | `evidence{kind, ref, asserts}` — R1 of `validate_live_mcp_bank.py`. A non-owed row without it is **invalid** and the gate fails. |
| 2 | **Evidence EXPIRES when the code under it changes.** | `evidence.sha` over `evidence.depends_on`; a touched file flips the row to **stale**. Proven: appending one comment to `marketplace.html` expired 52 rows on the spot. |
| 3 | **A STRUCTURAL probe may not settle a BEHAVIOURAL oracle.** | R6. "The page renders" is a real property and it is not "the number is right". This is the exact gap the credits-back chip lived in. |
| 4 | **LIVE-MCP walks only.** Headless may triage; it may not bank. | Ian, 2026-08-04. `tools/walk_owed_scenarios.mjs` is pre-flight triage; `live-state-runner.js` runs in the real browser and produces the evidence. |
| 5 | **Stale is visible, never absorbed.** | green% is computed over non-stale; the forward-only ratchet fails on a decrease with *"re-walk, do not re-baseline"*. |
| 6 | **Verify the instrument before the page.** | Six instrument bugs in one session — a scrollbar gutter read as overflow, a curly apostrophe, a force-click that bypassed the guard under test. An implausible reading is a broken probe until proven otherwise. |

> **The one line to remember:** *green is a claim with a receipt and a shelf life.*

---

## §1 · SCOREBOARD (measured 2026-08-05, after the harness re-runs and mig 53)

| | scenarios | green | stale | owed | green% |
|---|---|---|---|---|---|
| **A-W** | 364 | 323 | 37 | 4 | 88.7% |
| **F1** | 178 | 146 | 29 | 3 | 82.0% |
| **F2** | 120 | 29 | 90 | 1 | 24.2% |
| **F3** | 105 | 104 | 0 | 1 | 99.0% |
| **F4** | 110 | 72 | 36 | 2 | 65.5% |
| **TOTAL** | 877 | 674 | 192 | 11 | 76.9% |

**Stale is not owed and not green.** A stale row was true when it was walked and its ground has since moved — the sha over its `depends_on` no longer matches. It is the honest cost of editing the code the bank measures, and the reason the number moves DOWN when a page is fixed. Driving it to zero means re-running the harness that produced it, not re-declaring the row.

**What the re-runs bought this session:** the 124 layer/seam rows and 6 identity rows were re-earned from harnesses that actually ran again (`verify_layer_invariants.py`, `verify_identity_boundaries.py`) rather than re-stamped, and the identity rows were re-anchored to `supabase/migrations` — they had named three HTML pages for a boundary the database enforces, which expired them for nothing and would have kept them green through a migration that mattered.

## §2 · WHAT EACH FAMILY ASKS

- **F1 · Architecture** — the bank used to walk *pages*; this walks the *stack*, and mostly the **seams**.
  Every money defect found this month lived on a join: a trigger wrote a number the view never exposed, an
  edge fn returned 200 with an error body, a NULL meaning "no cap" arrived as a cap of zero. Seven seam
  surfaces, eight layer surfaces, 77 new oracles.
- **F2 · UFAI** — the same four dimensions the platform already grades itself on (`CROSS_ARC_UFAI_REVIEW`):
  U understandable · F functional · A available · I identity.
- **F3 · UI** — layout at three **verified** widths (`window.innerWidth`, never the requested viewport),
  the six component states, and the visual facts a screenshot cannot confirm (WCAG **and** APCA, focus,
  motion, icon names).
- **F4 · UX** — comprehension, journey (including two-sided), recovery. *"Can a person say what this number
  means, what happens next, and what it costs?"*

---

## §3 · THE ITERATION LOOP (momentum drive)

```
pick the lowest-green family
   → walk its owed rows on the LIVE MCP browser
       → fix what it finds (the bank has found something real every time it was pointed somewhere new)
           → re-walk to green with typed evidence
               → --accept the ratchet
                   → next family
```

Rules that keep the loop turning:
- `.momentum_drive` stays armed; the Stop guard blocks a turn-end while a known unit exists.
- The bank gate runs inside `run_platform_checks.py`, so drift appears in the normal suite rather than on
  request.
- Every session ends by updating **`NEXT:`** below and mirroring it into the Memento handoff.

---

## §4 · NEXT

```
NEXT: F3 BF-ui-layout CLOSED — 35/35, all seven surfaces at three VERIFIED widths.
  DONE 2026-08-04 (BF walk):
    · BF-ui-layout 35/35: w390 / w641 / w1280 x 7 surfaces, plus tap-target and safe-area.
      Every width SOLVED FOR, never requested: browser_resize reported 390 while innerWidth read
      585 (dpr 0.667), so the target was reached by requesting target x dpr and re-read from the
      page. A row whose verifiedWidth misses its target is not evidence for that target.
    · 2 real defects found and fixed (both invisible to a desktop screenshot):
      - marketplace.html .sheet padded a flat 2rem while its own seller twin used
        calc(2rem + env(safe-area-inset-bottom)) -> on a notched phone the last control in the
        buyer's sheets ("Save Search", the submit) sat under the home indicator
      - platform-actions.html .mod-main was flex:1 (basis 0), so a flex-wrap:wrap row never
        DECIDED to wrap and the pending-top-up line collapsed to 67px, pushing
        "PHP300 · ref 1005556667770" 41px off screen -- the 13-digit GCash reference an admin
        must match before releasing real credits
    · 2 instruments corrected mid-walk rather than believed:
      - the safe-area probe read inline style only; getComputedStyle RESOLVES env() to 0 on
        desktop, so a guarded and an unguarded sheet both compute to 32px. It reads the CSSOM now.
      - live-state-runner's edge/script_name passed on overflow alone, so a page whose loader
        could not be re-run scored a clean pass for a boundary it had never rendered. They now
        REQUIRE the induced payload to have landed and report `inconclusive` otherwise --
        public-feed was a false green under the old rule, and is a real one under the new.
        Its keyset cursor also defeated the re-run (loadInitial paginated past the end, 0 rows);
        the runner now drops the cursor filter from the request so the re-run asks for page one.
  DONE 2026-08-05 (harness re-runs, mig 53, and four new instruments):
    · MIG 53 — a REAL money defect. mint_settlement_commission() inserted a negative ledger row and
      never called retire_credits(), while both other money paths pair their write. The treasury
      published issued_credits 1500.00 against a ledger totalling 1140.00 — a gap of exactly 360.00,
      the whole commission history. Trigger now pairs; the drift is reconciled by a DO block that
      REFUSES to run if the gap is not exactly the un-retired commission, so it cannot paper over a
      different unbalanced writer.
    · The gate that should have caught it was blind BY CONSTRUCTION. db_credits_conserved compared
      issued_credits against `sum(amount) where entry_type='topup'` — the ONE entry type whose two
      sides are written by the same trigger, so a one-sided write was impossible there. It now sums
      the WHOLE ledger and names the net per entry_type when it fails. Teeth-tested by perturbing
      the treasury +7.50 and restoring in a finally.
    · Re-earned rather than re-stamped: 124 layer/seam rows (verify_layer_invariants.py re-run) and
      6 identity rows (verify_identity_boundaries.py, 5/5 hold as a verified NON-admin). The identity
      rows were re-anchored from three HTML pages to supabase/migrations — a page edit cannot move a
      server-side refusal, and naming the page kept them green through migrations that could.
    · Four new instruments built, none of them yet banked: tools/verify_money_lifecycle.py (13
      checks), tests/ux-journeys.spec.ts (12), tests/effect-and-agreement.spec.ts (3, writes and
      restores in finally), and five walker probes — no_raw_enum, units_visible, one_vocabulary,
      source_chip_true, boundary_not_emptiness — covering 36 of the 90 stale F2 rows.
    · INSTRUMENT DISCIPLINE RE-EARNED: a "20 passed" from the failure-injection spec was a TRUNCATED
      capture of a 43-test file, and the 2 failures found when re-running one group were a sign-in
      fixture timing out while psql work ran on the same machine. Never bank on a run whose count
      does not reconcile with the file's inventory, and never run psql or a second suite alongside a
      browser suite.

  DONE 2026-08-04 (live MCP + psql, every row value-backed):
    · AY-seam ALL SEVEN: client<->gateway, gateway<->edge, edge<->DB, trigger<->view,
      realtime<->client (subscribed in the browser, committed from psql, value + names + 20 columns
      arrived), cron<->DB (sweep_service_completions wrote settled; the view returned settled to the
      row's own client), storage<->client (67-byte PNG round-tripped byte-identical, then deleted)
    · AX layer-contract: envelope/status-body (BOTH paths, on the wire) · ordering_totality
      (forced-tie non-vacuity) · idempotency (two verifies mint 500.00, not 1000.00)
    · BA invariants: credits_conserved · cap_respected (breach attempted and refused)
    · AZ fail_null_field: found + fixed absent-vs-zero in whFmtPeso, swept the seller money renders
    · BE-ufai-I: bola · bfla · jwt_not_body · boundary_not_emptiness x2 (two real identities)
  DONE 2026-08-04 (BI walk) — BI-ux-comprehension CLOSED 35/35, all seven surfaces:
    · 3 real defects, each one a thing the surface KNEW and did not say:
      - the credits-back chip was on the browse card and absent from the DETAIL SHEET, so the
        reward vanished at the exact moment the buyer decides. Both sites now render from ONE
        helper, since two copies are what let them drift apart.
      - credits never said they were not cash. On a PHP68,980.48 listing "PHP6,898.05 credits
        back" reads like money coming back, and it is spend-only.
      - the seller's refusal named a remedy the reader could not take: "Top up by PHP200 to clear
        this" was a plain div, and the only top-up control lives in a tab the sentence never
        mentions. The panel's own comment had already diagnosed this ("no explanation AND no
        route") and the previous pass fixed only the explanation.
      - and on the profile, the TIER was the one badge that did not explain itself, while its
        neighbours all did. Now carries the real thresholds (silver 11, gold 51) and the fact
        that WorkHive sets it, taken from the enforcing trigger rather than invented.
    · VACUITY IS RECORDED, NOT COUNTED. public-feed renders ZERO numbers, so
      what_is_this_number has no subject there and says so; the same for refusals on read-only
      surfaces. A green over an empty denominator is the false pass this bank exists to stop.
    · one refusal was exercised WITHOUT a money write: the admin's optimistic-lock message needs a
      second press, and the first would mint real credits against a real GCash filing. The PATCH
      was intercepted and never forwarded, and psql confirmed afterwards that nothing moved.

  DONE 2026-08-04 (BG + BH): BG-ui-state CLOSED 35/35 · BH 21/35 (the 14 contrast rows are §5).
    · THE STATE LENS WROTE TO THE DATABASE and had to be fixed before it could be trusted:
      component_busy clicks a real commit control, and delaying-then-forwarding the request moved
      marketplace_sellers.updated_at for Pablo Aguilar. Every POST/PATCH/PUT/DELETE is now answered
      synthetically and never forwarded; re-proven with 2 blocked writes on the seller Save and a
      blocked PATCH on the admin's "Verify: mint credits", with psql confirming nothing moved.
    · The lens also DEADLOCKED itself for 1803s (held every read open, then awaited the loaders that
      await those reads). Bounded delay + a 40s ceiling on every call.
    · REUSED ufai_battery.js for contrast/focus/names rather than hand-rolling — and it earned it,
      refusing to call a single-state scan an all-clear. sweepAll found 3 defects on the seller and
      2 on community that the default state never showed.

  DONE 2026-08-04 (the null-field sweep): AZ fail_null_field on 5 surfaces, 3 real defects fixed
    (seller wallet + hold preview, admin cover badge, marketplace price pill). Plus AZ fail_401 /
    fail_partial / fail_timeout on seller and admin, BC money_matches_ledger + effect_in_db proven
    against psql in a rolled-back transaction, BB no_raw_enum 6/6 with the enum planted to prove
    the scanner works, and the BE identity rows RE-PROVED (the first jwt_not_body attempt refused
    on a SIGNATURE mismatch, which says nothing about auth).

  NOW (F2 at 15.0% and F1 at 18.0% are the two lowest):
  1. community/fail_null_field — find that page's own route back to the network and land the
     induction; the current clean reading is vacuous
  2. BD retry_path · fallback_engaged · rate_limit_legible · slow_honest (offline_refusal is
     answered and OPEN in §5)
  3. BB one_vocabulary · source_chip_true — the cross-surface vocabulary check
  4. AX / AY / BA on the remaining surfaces
  5. BJ-ux-journey / BK-ux-recovery — including the two-sided walk, and the question this walk
     raised but did not settle: minting credits is irreversible and does not confirm. The button
     names its effect ("Verify: mint credits") and the queue is worked at speed, so it is a design
     fork rather than a defect — it belongs to BK-recovery.
  6. Triage the battery's un-triaged finds: 1 defect on admin, the seller's Analytics-tab
     axe:color-contrast, and whether edit-image-file (a FILE picker at 13.3px) is a real iOS
     auto-zoom risk or a battery false positive.
  DEFERRED to arc close (Ian, 2026-08-04: reserve the full gate until the walk is done):
     the full suite + the clone-debt collapse of the 374-line Supabase bootstrap.
```

---

## §5 · OPEN FOR IAN

- **THE OFFLINE-WRITE DECISION (blocks 5 BD rows).** Offline, the seller's Save *fires* two writes
  instead of refusing — there is no pre-flight guard — and the write is then lost. The copy half is
  fixed: the shared connectivity widget was promising *"pending writes save to this device and drain
  automatically"* on **every** page, which is earned only on the six that register a queue; all four
  marketplace surfaces register none (three of them load `offline-queue.js` and never call it). It
  now tells the truth per page. **The behaviour is unchanged and deliberately so.** Closing these
  rows means either a pre-flight refusal on the marketplace writes, or real queue adoption on those
  four surfaces — and queueing a **GCash top-up filing** is not free: a filing that drains later can
  land *after* the provider gave up and re-filed, which is the duplicate the unique index exists to
  refuse. Your call on which.

- **THE CONTRAST DECISION (blocks the last 14 F3 rows).** Two findings that are really one:
  - **axe cannot see it.** axe-core reports **0 contrast violations** on every surface — and
    *abstains* on the text it cannot read: **185 incomplete nodes on marketplace, 39 on
    marketplace-seller**, nearly all "Element's background color could not be determined due to a
    background gradient". A scan that abstains has not shown the text passes AA; it has shown it
    cannot tell. One `contrast_wcag` row had already been banked green on that zero and has been
    **withdrawn**.
  - **APCA can, and it is unhappy.** The BH lens composites gradients, so it measures exactly the
    nodes axe skips: **273 of 552 text nodes across the seven surfaces sit below their APCA floor.**
    Not decoration — the admin's 13px **"Reject"** on the money queue at Lc 44, the seller's
    Published / Draft / Removed chips at Lc 41, the profile's PRC and TESDA credential lines at
    Lc 42.7.

  The cause is the platform's small-text colour tokens at 10–13px, so the fix changes how the
  product **looks** on every surface. That is a design call, not a probe's. Three ways to go:
  lift the token lightness and keep the type scale; raise the small sizes and keep the palette;
  or accept APCA as advisory and hold the WCAG line — in which case the 14 rows close as
  "measured, accepted" rather than staying open. **Not started either way.**

- **₱360 repealed-commission overhang.** `commission_pct = 0`, but three historical rows stand and *Pablo
  Aguilar Mechanical Works* sits at **−₱200**, blocked from listing and told to top up to clear a fee the
  platform renounced. Compensating entries satisfy both plan rules at once ("no commission" + "history is
  never rewritten"); five-line migration. **His money, his call.**
- **The cross-skill lessons table** — CLAUDE.md requires one-pass approval before writing to skills.
- **Ian's gate:** push · prod-deploy migrations 16–47 · deploy 2 edge fns (`gcash-receipt-ocr`
  **separately** — verify_jwt=true) · set `GCASH_INBOUND_SECRET` + `AZURE_DOC_INTELLIGENCE_*` ·
  **ROTATE the exposed prod service-role key.**
