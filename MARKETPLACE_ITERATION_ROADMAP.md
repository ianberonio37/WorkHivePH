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

## §1 · SCOREBOARD (measured 2026-08-04)

| | scenarios | green | owed | green% |
|---|---|---|---|---|
| **Existing A–W bank** | 364 | 124 | 240 | 34.1% |
| **F1 · Architecture** (AX/AY/AZ/BA) | 178 | 18 | 160 | 10.1% |
| **F2 · UFAI** (BB/BC/BD/BE) | 120 | 5 | 115 | 4.2% |
| **F3 · UI** (BF/BG/BH) | 105 | 0 | 105 | 0% |
| **F4 · UX** (BI/BJ/BK) | 110 | 0 | 110 | 0% |
| **TOTAL** | **877** | **148** | **729** | **16.9%** |

**Why the number fell from 343 to 124.** 220 rows were re-opened because a structural probe had been
answering a behavioural oracle. Each carries the reason in its findings. The 124 that survived cite psql or
a named source value. This is the honest starting line, and it is the point — a bank that cannot go down
is a bank that cannot be trusted when it goes up.

---

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
NEXT: ALL SEVEN SEAMS WALKED. F1 18/178 · F2 5/120. The seam family is the one that keeps paying,
      and it is now covered end to end.
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
  NOW:
  1. BC-ufai-F effect_in_db + money_matches_ledger — assert each surface's effect against psql
  2. BF-ui-layout w390/w641/w1280 across the 7 surfaces — three VERIFIED widths, never the requested
  3. BI-ux-comprehension what_is_this_number / reward_explained — the vanished-chip class
  4. AZ fail_null_field on the REMAINING surfaces (only the seller surface is walked)
```

---

## §5 · OPEN FOR IAN

- **₱360 repealed-commission overhang.** `commission_pct = 0`, but three historical rows stand and *Pablo
  Aguilar Mechanical Works* sits at **−₱200**, blocked from listing and told to top up to clear a fee the
  platform renounced. Compensating entries satisfy both plan rules at once ("no commission" + "history is
  never rewritten"); five-line migration. **His money, his call.**
- **The cross-skill lessons table** — CLAUDE.md requires one-pass approval before writing to skills.
- **Ian's gate:** push · prod-deploy migrations 16–47 · deploy 2 edge fns (`gcash-receipt-ocr`
  **separately** — verify_jwt=true) · set `GCASH_INBOUND_SECRET` + `AZURE_DOC_INTELLIGENCE_*` ·
  **ROTATE the exposed prod service-role key.**
