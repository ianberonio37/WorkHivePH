# Ian-gated items — the honest list

**Was 60. Then 17. Then 12. Now 11.** Each pass was me reading what I had only pattern-matched.

`60 -> 17`: the first count regex-matched decision-language anywhere in a basis, including HISTORICAL
requests a later note in the same basis had already answered (T121 shipped as *ownership, not purge*;
T96 *"FIXED AND PROVEN ON BOTH SIDES"*; T135's premise refuted; T19 answered by the code's own List
View Contract).

`17 -> 12`: four more were mine once read, and one was simply CHECKABLE.

## Resolved by checking, not escalating

- **T153** — filed "For Ian". It was a fact: `build_calc_pages.py` computes each worked example AT
  BUILD from the calc module, so 58 of 60 pages hold parity **by construction**. The 3 KPI pages with
  `"module": None` carry typed numbers — hand-checked today and all correct against their own
  standards (OEE 0.90x0.95x0.98 = 83.8%; MTBF 4000/5 = 800h, MTTR 40/5 = 8h, avail 800/808 = 99.0%).
  **Advanced 84 -> 90%, off this list.**

## Mine, not yours (reclassified today)

- **T168** (94%) — Abuse resistance as UX: rate limits meet real users
  > substantive fix landed (the silent-wall counter); what remains is runtime observation the LOCAL edge runtime can show — not inherently prod-only
- **T18** (86%) — Worker takes a skill exam / updates skill profile
  > not a decision — its live remainder is a WALK (revocation messaging + badge propagation)
- **T115** (82%) — PC 1920+: the wide-screen supervisor
  > the measurement WAS the deliverable — its note says "THE GATE IS RIGHT NOT TO ENFORCE THIS"
- **T181** (82%) — Loading-state choreography coherence
  > its own data settles it — 26 skeleton vs 8 text, "the eight were never deliberate"; converging accidental drift to the dominant idiom is the platform consistency rule, and it is reversible

## Genuinely yours — these change WHAT gets built

- **T71** (92%) — Status page & public trust surface
  > SO THE REMAINING ITEM IS A SCOPED BUILD WITH A FORK FOR IAN, not a slice: it needs (1) an incident MODEL with a start, an end and a severity, (2) a PRODUCER that detects and records one, and (3) a delivery shape that keeps the page database-independe
- **T20** (86%) — Supervisor clears the approval queue
  > Remaining: bulk actions for large queues (scoped product decision).
- **T104** (86%) — The marketplace's first-time seller conversion (supply growth)
  > Whether the platform should invite supply, and how gently, is Ian's call; the evidence that it COULD is now concrete rather than hypothetical.
- **T30** (84%) — Low-stock → inventory → marketplace procurement
  > Remaining: the on-order back-reference on inventory (likely needs schema - flag as a scoped decision for Ian per spec), price-vs-consumption basis, seller-side inquiry receipt (T35 harness) - wave close.
- **T59** (84%) — The account-security-conscious user
  > Per spec this is the SCOPED PRODUCT DECISION for Ian: an account-security surface (change password + sessions + revoke + honest 2FA absence note).
- **T156** (84%) — Social share cards (OG) truth
  > Remaining: per-page card IMAGES (all 116 share one generic asset) - a design job and Ian's call, not a defect.
- **T97** (82%) — Dispute resolution end-to-end
  > The remaining build is smaller than it looks - an intake form and a party-facing case view, onto machinery that already exists - but it is a build and a product decision (who may file, against what, within what window), so it goes to Ian.
- **T55** (80%) — Supplier/contractor persona enters via marketplace
  > ★THAT IS A PRODUCT DECISION, not a defect to patch: adding a fourth mode changes the mode switcher for everyone and only makes sense if WorkHive intends seller-only accounts as a first-class persona rather than as plant workers who happen to sell.
- **T110** (80%) — Notification storms under real activity
  > REMAINS (why 80): the digest-style merge of DIFFERENT notifications ('3 new replies') is a wording+cadence design decision for Ian, and catch-up UX after a storm is unbuilt.
- **T111** (80%) — The re-engagement email that lies (DP applied to comms)
  > REMAINS (why 80): the rendered-HTML snapshot of the real footer still needs a Resend key run - Ian-gated - and the fn needs a redeploy.
- **T188** (76%) — The renewal moment: is this worth it?
  > THE SCOPED DECISION for Ian: the whole-platform value summary, honestly measurable from existing tables.
- **T191** (60%) — The growing hive splits (or federates)
  > Remaining: a growth-guidance learn article (content decision - 'one hive per site or per team?'), split/merge demand evidence for Ian, the impossibility statement (wave close).

---

## Proposed defaults — so these are a yes/no, not a design session

Each is grounded in something the platform already does. **Say nothing and I will take the default**,
except T111 which needs a secret only Ian has.

| | trajectory | proposed default | grounded in |
|---|---|---|---|
| **T71** | status page incident model | derive incidents from the health signal that already exists (`platform_health.json` + `automation_log`) — start/end/severity from gate transitions — rather than a new incident table and a new producer | status.html is already static-first so it survives the outage it reports |
| **T20** | bulk approvals | "select all visible" + ONE confirm that names the count and the consequence | T50's proportional-confirm discipline + the existing `whConfirm` vocabulary |
| **T104** | invite supply | show a single dismissible "you have surplus of X — list it?" line **only** where inventory already shows surplus; never a nag, never a badge | DP1-3 manipulation-absence dims — an invitation must be truthful about effort and economics |
| **T30** | on-order back-reference | additive `on_order_qty` + `expected_at` on `inventory_items`, written by the procurement hop — no new table | the platform's additive-migration discipline |
| **T59** | account security | the minimal honest surface: change password + **sign out everywhere** + an explicit "2FA is not available yet" line | T59's own finding that sign-out surprises people who expected all sessions; honesty over silence |
| **T156** | OG cards | one templated card per learn CLUSTER (not 116 bespoke images) — better than the single generic asset, far cheaper than artwork | the learn cluster structure already groups them |
| **T97** | dispute filing | either party may file within **14 days of handover**; admin adjudicates; reuse `dispute_adjustment` | the machinery exists; only the policy was missing |
| **T55** | seller-only persona | do **not** add a fourth mode — let the nav hide plant tools when the account holds no hive membership | exactly the membership state built today (`whHiveMembershipLost`) |
| **T110** | notification digests | coalesce as "N new X" on the **existing** push-dedupe window rather than inventing a cadence | migration `20260826000001_push_dedupe_window` already defines the window |
| **T111** | re-engagement email | **blocked — needs the Resend key.** No default possible | a secret only Ian holds |
| **T188** | value summary | compute from existing tables only (PMs kept, faults resolved, knowledge written) — no new schema, no new collection | T188's own note: "honestly measurable from existing tables" |
| **T191** | growth guidance | a learn article stating **one hive per site**, with multi-hive membership as the answer for shared staff | T51 already makes multi-hive membership work |

**So the real ask is one secret (T111) and eleven yes/no confirmations** — not a third of the roadmap.
