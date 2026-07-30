# Marketplace Deepwalk — EXPANSION Arc (journeys × personas × states, + new MK dimension classes)

> **Ian, 2026-07-24: *"let us expand and extend deepwalk journey with this same page. lay out the comprehensive roadmap."***
> The "same page" = the **marketplace family** (4 surfaces + 2 bridges). This arc EXPANDS the
> deepwalk denominator; it is NOT a re-verification of the existing UFAI sub-layers
> ([[feedback_expand_dimensions_not_reverify]] — *"a dimension we already have, verified harder, is
> not an expansion; the DENOMINATOR itself must grow"*).

---

## §0 · WHY THIS ARC EXISTS — the honest depth gap (measured, not asserted)

`MARKETPLACE_DEEP_ARC.md` (2026-07-11) drove the marketplace PDDA arc to **"roadmap target"** —
2 heavyweights, an I-sweep (`validate_marketplace` 9→18 checks), founder-console fusion. It was
genuinely good work. **And yet a single diverse deepwalk on 2026-07-24 found three real defects it
never saw**, one of them a live security hole:

| Found 2026-07-24 | Severity | Why the "completed" arc missed it |
|---|---|---|
| **Self-publish moderation bypass** — non-admin seller `PATCH status='published'` → live, unmoderated | 🔴 HIGH | The I-sweep guarded **trust** columns (`marketplace_sellers`) + reviews, but nobody enumerated the **state/moderation** column. The arc's denominator had "trust integrity" but no **moderation integrity**. |
| **P7 load-failure rendered the first-run "Be the first to sell" CTA** | 🟠 MED | The rubric had empty-vs-filtered (D3) but **no third state**: load-FAILURE. A toast was mistaken for a fix. |
| **Stale-identity cache role-gated the admin link** | 🟡→root | Journeys were walked as ONE persona in ONE session. A **persona/session SWITCH** was never a journey. |

**The lesson that defines this arc:** each miss was a *missing axis*, not a missed check —
a state (load-failure), a column class (moderation), a transition (persona switch). **So the
expansion is structural: more journeys, more personas, more states, and new dimension CLASSES.**

---

## §1 · FRAMEWORK (reused, not reinvented — anti-drift)

Per [[feedback_follow_framework_antidrift_before_building]]: structure FIRST, then build.

- **Phases per journey (canonical 5, from `journey_deepwalk_state.json`):**
  `G-ground` (map steps+surfaces) → `W-walk` (live MCP deepwalk end-to-end, **carrying the FULL
  99-dim lens**, not spot-checks — [[feedback_shallow_journey_carry_the_full_lens]]) →
  `O-observe` (record friction/ideas) → `H-harvest` (Engine B night-crawl on a REAL observed
  friction, or mark clean) → `R-resolve` (dim built / candidate killed / fix shipped / clean).
- **Type taxonomy (canonical 12):** this arc uses the marketplace-relevant subset
  T1/T2/T3/T4/T8/T9/T10/T11/T12.
- **Engine A DRIVES Engine B** ([[feedback_engine_a_drives_engine_b_journey_seeds_harvest]]):
  the live journey's OBSERVED friction becomes the crawler query. Never crawl blind.
- **The %-board is the anti-drift compass** ([[feedback_roadmap_percent_is_the_anti_drift_compass]]):
  MEASURED by `tools/marketplace_deepwalk_scoreboard.py` from `marketplace_deepwalk_state.json`,
  never vibed ([[feedback_measured_percent_not_qualitative_done]]).
- **Token economy:** retrieve-first, INLINE execution, no fan-out (CLAUDE.md non-negotiable).

### The surfaces in scope
| Surface | Role | Size |
|---|---|---|
| `marketplace.html` | buyer + post | 168KB · 63 fns |
| `marketplace-seller.html` | seller dashboard | 75KB · 28 fns |
| `marketplace-seller-profile.html` | public seller profile (anon-visible, JSON-LD) | 40KB · 15 fns |
| `marketplace-admin.html` | moderation console | 52KB · 20 fns |
| `founder-console.html#sec-mkt-mod` | fused moderation (same authority, 2nd surface) | bridge |
| `inventory.html` ↔ marketplace | parts-flow bridge (both directions) | bridge |

---

## §2 · EXPANSION 1 — THE JOURNEY MATRIX (grow the JOURNEY denominator)

**20 journeys**, segregated by type. Each is walked across the **persona** and **state** axes below —
that cross-product is the real expansion (the old arc walked ~1 persona in the populated state).

### Persona axis (5) — *the axis that hid the stale-identity bug*
`P-anon` (logged out, SEO surface) · `P-buyer` (authed, non-seller) · `P-seller` (owns listings) ·
`P-admin` (platform admin) · `P-switch` (**session/persona SWITCH** on one device — admin→buyer, the
axis that exposed the identity-cache root)

### State axis (5) — *the axis that hid the P7 bug*
`S-empty` (no listings/inquiries/reviews) · `S-populated` · `S-filtered0` (search returns 0) ·
`S-error` (load fails: offline / 401 / 5xx) · `S-edge` (draft, rejected, sold, removed, stale, thin-supply)

### The journeys

| ID | Type | Journey (end-to-end) | Primary personas |
|---|---|---|---|
| **J1** | T8 | Anon discovery → browse → search/filter → listing detail → signin wall | P-anon |
| **J2** | T8 | Authed buyer → detail → **Contact seller** (inquiry) → seller replies → close | P-buyer, P-seller |
| **J3** | T8 | Compare mode → multi-select → **RFQ bulk quote** → N inquiries land | P-buyer |
| **J4** | T8 | **Watchlist**: save → revisit → badge → listing goes sold/removed (stale item) | P-buyer |
| **J5** | T8 | **Saved search** → match badge → apply → results | P-buyer |
| **J6** | T8 | Price comps / "parts for my assets" recommendation → listing | P-buyer |
| **J7** | T2 | **Post listing**: form + category/condition + price validation + image + AI assist + quality widget → draft | P-seller |
| **J8** | T2 | **Post FROM inventory** (prefill part_number + `source_inventory_item_id`) | P-seller |
| **J9** | T1 | **First-time seller**: no seller row → post first listing → seller row created → dashboard empty states | P-seller, S-empty |
| **J10** | T3 | **Moderation**: draft → admin approve → buyer sees it \| reject → seller sees WHY | P-admin, P-seller |
| **J11** | T3 | **Cert verification**: seller adds certs → `cert_verified=false` → admin verifies → badge | P-seller, P-admin |
| **J12** | T3 | **Dispute** lifecycle (⚠ `PAYMENTS_ENABLED=false` — verify live vs dead code) | P-admin |
| **J13** | T9 | Seller profile config: messenger, certifications, contact | P-seller |
| **J14** | T4 | Seller **analytics** tab (views/inquiries/conversion honesty) | P-seller |
| **J15** | T10 | **Review flow**: buyer reviews → rating recomputes (verified-only) → displays | P-buyer, P-seller |
| **J16** | T10 | **Trust badges**: community rep → "Community-trusted" chip; tier bronze/silver/gold | P-buyer |
| **J17** | T12 | Marketplace → **"Received this? Add to your inventory"** → inventory row | P-buyer |
| **J18** | T12 | Inventory low-stock → **"Find on Marketplace"** by part number → listing | P-buyer |
| **J19** | T12 | Listing → **public seller profile** → back (anon-visible bridge, JSON-LD) | P-anon |
| **J20** | T11 | **Founder-console fused moderation** — must AGREE with marketplace-admin (2 surfaces, 1 authority) | P-admin |

> **Coverage rule:** a journey is `W-walk` complete only when walked in **≥2 personas** and
> **≥2 states** (always including `S-error` or `S-empty` where reachable). One-persona/one-state
> = the shallowness this arc exists to kill.

---

## §3 · EXPANSION 2 — NEW DIMENSION CLASSES `MK1-MK10` (grow the DIMENSION denominator)

The 99-dim A-Z/UFAI lens is **generic** (contrast, spacing, readability, empty-states, RLS…). A
**marketplace** has failure modes no generic lens names. Each class below is **seeded by something
actually observed** in the 2026-07-24 walk (never invented), and each must be proven **DISTINCT**
before it ships ([[feedback_ai_pp_dl_deeper_dimension_classes]] — a candidate that duplicates an
existing dim gets KILLED, with proof).

| Class | What it governs | Seed observation (real) | Measure (detector) | Harvest source (Engine B) | Owning skill | Locking gate |
|---|---|---|---|---|---|---|
| **MK1 · Trust-signal integrity** | every displayed trust signal (stars, verified, sales, tier, response rate) is DERIVED from a forge-proof canonical source | listing showed **"★3.9 · 1 completed"** beside **"No reviews yet"** (seed data had rating w/ 0 review rows) | for each rendered trust signal, assert a canonical backing row-count > 0 or the signal is suppressed | Google fake-review policy; marketplace trust taxonomies | security + analytics-engineer | extend `validate_marketplace.py` |
| **MK2 · Moderation-state honesty** | the UI's review promise == server enforcement, AND the seller can see WHERE a listing sits (draft/pending/published/**rejected + reason**) | **self-publish bypass** (fixed); rejection **reason surface unverified** | non-admin state-transition probe + "is there a rejected-with-reason surface?" | EU DSA statement-of-reasons; P2B | security + frontend | `guard_marketplace_listing_status` (✅ shipped) + a rejected-reason UI gate |
| **MK3 · Contact/disclosure staging** | what seller/buyer PII appears at which stage; anti-scraping | detail sheet correctly hid phone/email pre-contact (**passed** — lock it) | scan each stage's DOM for PII patterns vs an allowed-stage map | PH Data Privacy Act; C2C safety UX | security | new detector |
| **MK4 · Listing lifecycle completeness** | every state (draft→published→sold→removed→rejected) has a surface, a transition affordance, an honest badge; no dead-end | `status` domain = {draft, published, sold, removed} — is **sold/removed** reachable + visible to the seller? | enumerate the status domain; assert each has a render + a transition path | — (internal) | frontend + qa-tester | new gate |
| **MK5 · Two-sided liquidity honesty** | thin/zero supply must not read as broken; "Be the first to sell" must never show to a **buyer** | P7 error→first-run CTA (fixed); **thin-supply** case still unmeasured | 3-state assert (empty/filtered0/error) + audience-correct CTA | NfX/a16z marketplace cold-start | qa-tester + community | extend the P7 gate |
| **MK6 · Parts-flow continuity** | inventory↔marketplace round trip preserves part identity + never dead-ends | `part_number` + `source_inventory_item_id` exist in the insert — **round trip unwalked** | walk J8+J17+J18; assert identity survives each hop | — (internal keystone) | data-engineer | extend `validate_marketplace` |
| **MK7 · Public/SEO surface truth** | anon-visible listing/profile + **JSON-LD** must not claim more than canonical data | `injectJsonLd` on seller-profile — does it emit `AggregateRating` for a seller with 0 reviews? | parse emitted JSON-LD; cross-check each claim vs DB | schema.org Product/Offer; Google structured-data policy | seo-content + security | new gate |
| **MK8 · Marketplace safety & fraud** | scam/spam/duplicate/impersonation signals; off-platform payment pressure | free contact-only marketplace = **no escrow**; `PAYMENTS_ENABLED=false` | duplicate-listing + price-anomaly + contact-pattern detectors | PH **Internet Transactions Act (RA 11967)**; DTI e-commerce rules | security + marketplace | new detector |
| **MK9 · Response-SLA honesty** | "Responds in ~1h · 95% reply rate" computed from real inquiry data, not seeded/static | rendered on the detail sheet — **provenance unverified** | recompute from `marketplace_inquiries` and diff vs displayed | — (internal) | analytics-engineer | extend `validate_marketplace` |
| **MK10 · Ranking/sort transparency** | *why* these listings, in this order — disclosed (legally required for marketplaces in EU P2B; good practice everywhere) | grid sorts `created_at desc` with **no disclosure** to the buyer | assert an explainable ranking disclosure exists where a ranked list is shown | **EU P2B Reg. 2019/1150 Art.5**; DSA | seo-content + designer | new gate |

> **Kill-list discipline:** MK1-MK10 are **candidates**. Any class that a live probe shows is already
> covered by an existing dim gets **KILLED with the proof recorded** (the arc's §3 candidate-kill
> ledger). Expansion means *net-new measurable ground*, not renaming.

---

## §4 · THE %-BOARD (anti-drift compass — MEASURED)

Two boards, both computed by `tools/marketplace_deepwalk_scoreboard.py` from
`marketplace_deepwalk_state.json`:

1. **Journey board** — per TYPE and overall: `% = done_phases / (journeys × 5 phases)`, where a
   phase is `done` / `partial` (0.5) / `todo`.
2. **Class board** — per MK class across 6 stages: `harvest → define → detect → sweep → fix → gate`.

**Baseline is honest: everything starts `todo` except the three cells the 2026-07-24 walk already
earned** (see §6). A green headline on one board never means the arc is done — **both** boards plus
the §7 NEXT queue define "done" ([[feedback_seed_resolved_is_not_roadmap_done]]).

---

## §5 · DRIVE ORDER (lowest-first / risk-first)

1. **Security-adjacent classes first** — MK2 (rejected-reason surface), MK1 (trust integrity), MK7
   (JSON-LD truth), MK8 (fraud). A trust/moderation defect is the one that costs a real user money.
2. **Then the persona/state axes that hid bugs** — `P-switch` and `S-error` on every journey.
3. **Then the unwalked bridges** — J8/J17/J18 (MK6 parts-flow round trip), J20 (2-surface agreement).
4. **Then breadth** — remaining journeys to ≥2 personas × ≥2 states.

---

## §6 · SEED EVIDENCE (already earned, 2026-07-24 — the M0 baseline)

| Item | Phase credit | Evidence |
|---|---|---|
| Moderation bypass found→fixed→deployed | J10 `O`+`H`+`R` partial; MK2 `detect`+`fix` | mig `20260724000003`; live 42501; prod-applied |
| P7 load-error state | J1 `O`+`R` partial; MK5 `detect`+`fix` | `_loadError` branch; SW v188 |
| Stale-identity role gate | `P-switch` axis proven real; MK-cross | `restoreIdentityFromSession` reconcile; verified |
| Trust-signal anomaly observed | MK1 `harvest` seed | ★3.9 vs "No reviews yet" (local seed) |
| Disclosure staging PASSED | MK3 seed (lock it) | no phone/email pre-contact |

---

## §7 · NEXT (the standing queue — drive top-down)

1. **J1 `W`+`O` as `P-anon` × `S-populated`** — full 99-dim lens on the anon surface (SEO/JSON-LD path), seeds MK7.
2. **J9 `W`+`O` as `P-seller` × `S-empty`** — first-time-seller empty states, seeds MK4/MK5.
3. **MK2 `detect`** — is there a **rejected-with-reason** surface for the seller? (probe, then build if absent).
4. **MK7 `detect`** — parse `injectJsonLd` output vs canonical (fake `AggregateRating` = trust lie + Google penalty).
5. **Engine B harvest** on whichever friction J1/J9 actually surfaces (never crawl blind).

---

## §8 · THE FLYWHEEL — the standing SOP (one turn = one journey advanced)

> **Ian, 2026-07-24: *"solidify it as a framework with anti-drift discipline and momentum drive, and
> as a flywheel where a night crawler harvest best practices in between."*** This section IS the
> framework. It is not narrative — it is the loop to execute, with the crawler as a **mandatory
> in-between spoke**, not an optional side-trip.

```
        ┌───────────────────────────── the board PICKS (never the tangent) ─────────────────────────────┐
        │                                                                                               │
   ① PICK ──▶ ② G-ground ──▶ ③ W-walk ──▶ ④ O-observe ──▶ ⑤ H-HARVEST ──▶ ⑥ R-resolve ──▶ ⑦ RATCHET ──┘
   lowest-%   retrieve-first   live MCP     friction WITH   ★NIGHT-CRAWLER   build+verify   state→board
   risk-first  (no fan-out)   FULL lens     evidence        (Engine B)       LOCK w/ gate   →--accept
                              ≥2 personas   or "clean"      ↑ driven by ④                        │
                              ≥2 states                     never crawl blind                    │
                                                                                                 ▼
                                                                                          ⑧ NEXT journey
                                                                                     (no hand-back between spokes)
```

| # | Spoke | The rule | Instrument |
|---|---|---|---|
| ① | **PICK** | The **board** chooses — lowest %, risk-first (§5). Never the interesting tangent in front of you. | `marketplace_deepwalk_scoreboard.py` |
| ② | **G-ground** | Retrieve-first: `substrate/page/*.md`, the owning `SKILL.md`, Memento. **No fan-out** — never re-derive what we already have. | `memento_retrieve.py`, substrate |
| ③ | **W-walk** | Live Playwright-MCP, carrying the **FULL 99-dim lens** (`family_rubric_sweep.mjs`), **≥2 personas × ≥2 states**. Read `perDim.failPages`, never the page mean. | Playwright MCP + the lens |
| ④ | **O-observe** | Record friction **with evidence** (repro + `file:line`). Genuinely clean? Say so plainly — a clean walk is a real result. | the state file `notes` |
| ⑤ | **★H-HARVEST (the in-between spoke)** | Take the **observed friction verbatim** as the crawler query. **Engine A drives Engine B** — never crawl blind. Tier-1 `--query` costs **0 crawl tokens**; escalate to `--ensure/--url` only on a bag-miss. | `python tools/night_crawler.py --query "<the friction>"` |
| ⑥ | **R-resolve** | The harvest yields **either** (a) a NEW measurable dim class (build the detector → sweep → fix → **lock with a gate**), **or** (b) proof an existing dim already covers it → **KILL the candidate, record the proof**. Both are progress. | validators / migrations / lens dims |
| ⑦ | **RATCHET** | Update the state → re-run the board → `--accept`. The gain becomes **un-regressable** (the gate FAILs on any fall). | `--accept` + the registered gate |
| ⑧ | **NEXT** | Immediately pick the next journey. **The turn does not end between spokes.** | §7 queue |

**Why the crawler sits at ⑤ and nowhere else:** harvesting *before* a walk produces generic
best-practice noise we can't act on; harvesting *after* a real observed friction produces a
**citable standard for a defect we can prove we have**. That ordering is the whole reason
MK8 (PH Internet Transactions Act) and MK10 (EU P2B ranking transparency) are real candidates
rather than a reading list — each traces to something the walk actually surfaced.

### The queue can only look empty if you stopped harvesting
Every ⑤ that yields a new class **refills** the queue with 6 new stages. That is the structural cure
for "only forks and ceilings remain" ([[feedback_apca_perceptual_contrast_c5.md]] — the C5/APCA dim
was born exactly this way, from one in-loop harvest).

## §9 · THE TWO DISCIPLINES (non-negotiable)

**ANTI-DRIFT — the board decides, and it has teeth**
- The % is **MEASURED** by the tool from the state file, never asserted in prose.
- `marketplace_deepwalk_ratchet` is a **registered gate** (`run_platform_checks.py`, AI Validation,
  runs in `--fast`): a fall in either board **FAILs the build**. The roadmap cannot rot into a stale doc.
- **`shallow_W` flag**: a `W` marked done with <2 personas or <2 states is flagged ⚠ — the exact
  shallowness that hid the stale-identity bug is now mechanically detectable.
- **"Done" = BOTH boards + the §7 queue empty.** One green headline is necessary, never sufficient.
- At ANY *"what next / is this done?"* doubt → **run the board + re-read §7**, then act.

**MOMENTUM — the flywheel does not stop between spokes**
- A completed spoke is a **checkpoint, not a turn-end**. ①→⑧ chains within one turn.
- Writing the NEXT queue is **not** delegating it to a future turn — the next action after
  authoring a `NEXT:` line is **executing its first item**.
- An Ian-gated outward step (commit/push/deploy) is **not** a stop — **PIVOT** to the remaining
  local work and let the gate happen on his schedule.
- Legitimate enders only: **(a)** a genuine fork needing Ian's decision, **(b)** a hard EXTERNAL
  ceiling, **(c)** the irreversible action is the SOLE remaining item, **(d)** the local queue is
  genuinely empty, **(e)** Ian says wrap in his current message.

---

*Anti-drift: at ANY "what next / is this done?" doubt → run the scoreboard + re-read §7. The board
decides, not the tangent in front of you.*

---

## §10 · EXPANSION 3 — THE TEST BANK (walks become re-runnable assertions)

> **Ian, 2026-07-29: *"we have to make a tests bank for our journey deepwalk live mcps for our entire architectural and design of our marketplace… we have to extend and expand the roadmap."***
> Locked with Ian: **unified marketplace** (this arc's J1–J20 + the 33 service-hailing journeys) · **bank-as-DATA + two runners** · extend THIS roadmap rather than start a fourth.

### §10.0 · Why — the 100% that measures the wrong thing

§4's two boards read **100.0%**, and they are honest about what they measure: *a journey was walked once, by a person, on a date*. They are silent about what they don't. This arc's own state file says it out loud — `J2-buyer-contact-seller` is `W: done` while its notes read **"End-to-end round trip NOT yet walked."** A walk leaves no artifact that fails when the behaviour regresses; nothing replays it next month. The bank converts each walk into a declarative, evidence-seeded, **re-runnable** assertion.

### §10.1 · The denominator is DERIVED FROM THE DATABASE, never enumerated

A hand-written list of "journeys we should test" is an opinion that silently stops being true the day someone adds a transition. The marketplace's state machines already exist as guard functions, and **each guarded transition names its authorised actor**. `tools/derive_transition_matrix.py` reads them and computes what the bank owes — so a new transition grows the denominator by itself and the bank reports an untested cell instead of a false 100 ([[feedback_short_denominator_is_a_false_100]]). This is *all-transitions coverage* in the model-based-testing sense: the guards ARE the automaton; the bank is the abstract test suite derived from it; the two runners are its concretisation.

The guards come in **two shapes**, and conflating them would fabricate coverage:

| Shape | Guard | Reading |
|---|---|---|
| **allow-list** | `guard_service_request_status` | every permitted `(actor, from, to)` triple is spelled out; anything unlisted is refused |
| **deny-rule** | `guard_marketplace_listing_status` · `guard_marketplace_order_status` · `guard_service_topup_status` | only the *dangerous* target states are named; the rest are permitted by omission — which licenses **no** coverage claim, so those are reported separately as UNGOVERNED |

**Measured 2026-07-29 (`transition_matrix.json`):**

| Machine | Vocabulary | Positives | Authority-negatives | Sneak-paths |
|---|---|---|---|---|
| `service_requests` | 12 states | **16** | 80 | 64 |
| `marketplace_listings` | 4 | 1 | 4 | 4 |
| `marketplace_orders` | 6 | 2 | 8 | 8 |
| `service_credit_topups` | 3 | 1 | 4 | 4 |
| **BANK DENOMINATOR** | | **20** | **96** | **80** = **196 obligations** |

Every cell also owes the four **sneak paths** — the illegal-but-reachable sequences that have each already bitten this platform: **replay** (the partial unique indexes exist because of it) · **concurrency** (the first-accept race, proven live) · **out-of-order** · **session-switch / stale token** (the identity-cache root this arc's persona axis exposed).

> **Instrument lesson, banked immediately.** The first run derived only **6** of the 16 service positives and then reported `cancelled_by_client`, `cancelled_by_provider` and `disputed` as *ungoverned* — a phantom architectural finding. Cause: those permission clauses **wrap across two lines**, and a line-by-line reader loses them. Fixed by flattening the source before matching, with the wrapped case pinned as a self-test. The tool prints the guard source line behind every derived cell precisely so this class is visible ([[feedback_verify_the_instrument_before_the_page]]).

### §10.2 · Anti-duplication FIRST — the bank must not re-prove what already passes

With **554 gates registered**, the largest risk is building a slower copy of a passing test. `gate_coverage_map.json` declares which derived obligations an existing gate already locks, each claim carrying **the gate's own printed check text** as evidence, so an over-claim is visible rather than silently inflating coverage. Same discipline as `DEEPWALK_JOURNEY_BUGHUNT_ROADMAP.md` §6.2 ("why D5/D6/D9/D10 are already COVERED everywhere"), and the MK kill-list rule applied to tests.

**★ THE FINDING THIS PASS PRODUCED — the platform locks REFUSAL and barely locks PERMISSION.**
Of 20 derived positives, **4 have a gate; 16 do not.** Specifically unproven in the *authorised* direction:

- the **entire provider execution chain** — `accepted → en_route → on_site → in_progress → completed`
- **all 8 cancel transitions** (5 client-side, 3 provider-side)
- **both dispute transitions**, and `completed → settled` (the one that mints commission)
- `marketplace_listings → published` and `marketplace_orders → released / refunded` positives

The asymmetry is explicable: every one of those gates was written *after a security finding*, so they encode "this must not happen". Nothing yet asserts **"this must still work"** — which is exactly how a guard tightened one notch too far ships silently. That is the bank's first real value, and it is why P2 leads with the positive direction.

### §10.3 · ★ SECOND FINDING — MK2's rejection surface cannot exist as specced

`marketplace_listings` carries `moderation_reason`, `moderated_at`, `moderated_by` — but its status CHECK is `{draft, published, sold, removed}`, with **no `rejected` state**. A moderator can therefore write a rejection reason that has no state to attach to, and the seller sees their listing sitting in `draft` with no visible rejection. This is precisely MK2's long-open cell ("rejection reason surface **unverified**"), and the derivation explains *why* it was never verifiable: the state the UI would render does not exist in the vocabulary. **Disposition: a schema question for Ian** (add `rejected` to the domain, or redefine MK2 around `draft + moderation_reason`) — not a test to write.

### §10.4 · Design rules (from the external harvest, 2026-07-29)

The bag held **nothing** on test-bank design across 166 external chunks, so six sources were harvested. Four changed the design:

- **Cheapest honest altitude** (Fowler's pyramid + Google's flake study: UI tests are the most flake-prone and *flakiness masks real bugs*). A DB invariant is proven in **rolled-back SQL**, never through a browser. Only cross-page continuity, PII staging, dead-ends and role-gated rendering earn the journey altitude.
- **Equivalence partitions, not a cross-product.** Authority (`anon · member · owner · counterparty · admin · cross-tenant`), data-shape (`empty · populated · filtered0 · error · edge`), path (`happy · error · degraded`), viewport (`390 · 1280` — the axis that caught Z3) and language are *partitions*: one cell each, every N/A carrying a printed reason.
- **User-facing locators** (`getByRole` / `getByText`), never CSS or data-attributes — per Playwright's own guidance; the first draft's `[data-tb=…]` selectors were implementation coupling.
- **Every cell names its ORACLE** — `db-truth` · `continuity` · `rubric` · `refusal` (a specific SQLSTATE) · `eval` (for non-deterministic AI surfaces). Without one, a test asserts only "nothing threw".

**Flake policy:** a cell yielding both outcomes on unchanged code is **quarantined with a count and first-seen date, never deleted**, and stays printed on the board. An unexplained quarantine is debt with a name — the same reasoning that removed a "reasonable" cron exclusion this session, which had been hiding a nine-job outage.

### §10.5 · Lanes

| Lane | Content | Runs in |
|---|---|---|
| **SQL** | transition legality, authority + sneak-path negatives, money once-only — rolled back, deterministic, seconds | **`--fast`** |
| **Journey** | cross-page continuity, PII staging, dead-ends, role-gated rendering, viewport + language partitions | full mode only |

Runner A drives the journey lane live through **both MCPs** — Playwright for the screen, postgres for the row, in the *same* walk — so a cell proves the screen and the record together. Runner B (`marketplace-test-bank`, registered) replays everything headlessly so the bank cannot rot.

### §10.6 · Boards added to §4 (existing two keep their 100% and their ratchet)

| Board | % = | Answers |
|---|---|---|
| **Transition coverage** | covered obligations ÷ 196 derived | is every guarded state change proven, for **and** against? |
| **Layer coverage** | S1–S9 with ≥1 passing cell ÷ 9 | **architecture** — which layer no test exercises |
| **Dimension coverage** | MK1–MK13 + UFAI classes asserted by ≥1 journey ÷ total | **design** — which failure-class nothing asserts |

Never folded into a %: the **quarantine list**, the **superseded list** (cells retired by a guard change, with reasons), and the **lane runtimes**.


### §10.7 · SPROUTING FROM THE LAYERS — the board became the work list (Ian, 2026-07-29)

Ian asked two things in a row: *"why is it we have no journeys e2e for using the realtime map x
personas"*, then *"you have to sprout from that layers."*

**The first question named a real hole in the coverage RULE, not just in the coverage.** `J29-live-map-tracking`
was W-walk complete under the arc's *"≥2 personas and ≥2 states"* rule — walked as `P-client-supervisor`
and `P-client-worker`. Both are **watchers**. The provider, whose `watchPosition` is the only thing that
ever *publishes* `live_location`, had never been in the walk. The rule was satisfied by COUNT while the
axis that carries the entire feature was untouched. `J31-consumer-track-review` had the same shape.

> **A two-sided journey owes a ROLE-PAIR, not a persona count.** `publisher × watcher`,
> `sender × recipient`, `submitter × approver`, `client × matched provider`, `subscriber × trigger`,
> `writer × reader`. Where the value of the journey IS the handoff, one side proves nothing.
> ([[feedback_two_sided_journeys_need_a_role_pair]])

**The second instruction changed what the layer board is for.** A board reporting "S2, S5, S7, S8, S9
untested" is a complaint. Each untested layer now names the journey and the role-pair that would move
it, so the board *generates* the queue. Every one of those five was then built.

#### The authored lane — the cells were WALKED, not banked

The first two sprouted cells were run by hand in psql and written into the bank as `banked`. That is
the exact defect this whole arc exists to replace: the J2 note that read `W: done` beside *"round trip
NOT yet walked."* A bank entry backed by a memory of a green terminal is not an assertion.

So the SQL lane grew an **authored-probe lane**: `tests/bank_probes/<cell-id>.sql` owns its own
`begin/rollback` and mints its own identities, emits `RESULT <key>=<value>` lines, and the cell
declares the `expect` block the runner diffs against. Teeth are proven, not assumed — the self-test
runs a probe with a deliberately WRONG expectation and requires the failure to name the **observed**
value. (The first cut of that teeth-check passed for the wrong reason: the probe was not executing at
all, so every assertion read `got None` — a red that looked like teeth and was actually a dead lane.)

#### The two-context harness — the structural unlock

Every other spec in the repo drives ONE identity, which is *why* the two-sided journeys had never been
walked end to end. `tests/marketplace-bank-two-context.spec.ts` holds two independent Playwright
contexts with two real Supabase Auth sessions and one shared row of truth between them, driven by
`tools/validate_marketplace_bank_journey.py` (registered `marketplace-bank-journey`). The live-map cell
passes **through the page's own `watchPosition`**, not a test-only write, and `WH_TB_FREEZE=1` parks the
publisher so the watcher assertion must go RED — the teeth are executed, not claimed.

#### What the sprout actually found

| Layer | Cell | What it proved — and what it FOUND |
|---|---|---|
| **S6-realtime** | data path + UI | provider publishes → client sees 16.4100 → moves → 16.4200 → a stranger reads **0 rows**. Then the marker repaints on a real second browser. |
| **S5-edge** | fan-out **audience** | `outbox-delivery` proves delivery but hand-builds its payload, so `fanout_broadcast_push`'s own audience query had **never been executed by any gate**. Offline, wrong-trade, 96 km out, and the client's OWN provider profile are each excluded; exactly 1 recipient; a re-fire enqueues no duplicate. **FOUND: the urgent branch was DEAD** — it tested `urgency = 'emergency'`, a value the CHECK forbids (`{low, normal, high, critical}`), so a *"production is down"* hail pushed with the same words as *"whenever convenient"* and nothing ever failed (mig `20260729000017`). |
| **S9-knowledge** | writeback round-trip | the provider completes, the **CLIENT** reads the entry, `[PUMP-207]` lands in `machine`, the provider is named, a different hive reads 0 rows, and a re-fire yields exactly 1 entry. **Counting the idempotence under the PROVIDER's JWT first returned 0 — RLS, not duplication. The assertion was measuring the wrong thing and would have read green either way.** |
| **S2-pwa** | offline refusal | **FOUND: `svcRequireOnline` existed and guarded 2 of 7 client writes; the seller page guarded 1 of 10.** `svcSettle` ("I paid"), `svcApplyVoucher`, `svcPickQuote`, `svcPickStar`, `svcClientCancel` (whose confirm dialog made the person commit *before* failing opaquely), and `svcFileTopup` (where the provider may have ALREADY sent the GCash payment) all fired into a dead network. **14 write paths fixed**, locked by `offline-write-guard`. |
| **S8-gates** | the console's own honesty | **FOUND: the regressions block truncated at 6 with no overflow line** — the highest-severity signal on the page, a gate that was passing and now is not, and everything past the sixth vanished. Locked by `gate-panel-honesty`. |
| **S7-ai** | the eval oracle | rubric, never exact-match: the suggestion must be **in the live vocabulary**, because `marketplace.html` applies it by finding the matching `<option>` — so "Plumbing Services" sets nothing, reports nothing, and the person watches a form that does not move. Vocabularies read from the DB each run. A rate-limited chain is a **SKIP, never a PASS**. |

**Why `degraded-state-central` and `offline-queue-confirm` both stayed green through the S2 defect:**
one proves every page adopts the offline **banner** — and both pages did, the whole time; a passive
warning does not stop a button. The other proves a queue **drain** never calls 0 rows "synced" — but
these surfaces deliberately do not queue, because a queued accept would claim a job someone else
already took. Adoption of a warning and correctness of a drain are not the same thing as the write
itself refusing. That third thing had no gate.

#### Boards after the sprout

| Board | Before | After |
|---|---|---|
| Transition | 37.2% (83/223) | **39.7%** (89/224) |
| **Layer** | 33.3% | **100.0%** — every one of S1–S9 has an executing cell |
| Dimension | 23.1% | **53.8%** |

Five product/instrument defects were found by *building the cells*, not by reading the code: the dead
urgency branch, 14 unguarded writes, the silent regression truncation, an assertion measuring RLS
instead of duplication, and a teeth-check that bit for the wrong reason. That ratio — one real finding
per layer sprouted — is the argument for the layer board being a work generator rather than a report.

#### §10.8 · Two more cells the sprout led straight to

**L4 · the party-scoped view family.** With the layers green, the per-page bughunt scoreboard turned red
with **3 GAP pages**. Five service views appear in page footprints and carry **no `hive_id` column at
all**, so `validate_truth_view_read_isolation` — which probes by reading each view *filtered to a
foreign hive* — could not reach them, and reported 35/35 green while they sat uncovered. One of them
exposes a **GCash reference**, which ties a real phone number to a real payment.

> **"No hive column" is precisely the shape a hive-shaped gate cannot see.** Isolation has more than
> one shape: hive-scoped (foreign hive → 0) · **party-scoped** (a signed-in *stranger* → 0) ·
> owner-scoped · public-by-design (asserted **positively**, so "public" is a decision on the record).

The gate grew a `PARTY_SCOPED` family with a stranger probe — the stranger is *minted*, never borrowed,
because a seeded identity may turn out to be a party to something. It also asserts the **owner** sees
their own row (a view nobody can read isolates perfectly and serves no one) and that the public price
list **is** readable (a marketplace with no rate card is broken, not secured). Scoreboard: **3 GAP → 0**.

**MK7 · JSON-LD truth.** The roadmap's own open question was *"`injectJsonLd` on seller-profile — does
it emit `AggregateRating`?"* It does, correctly gated on a review **count** — and nothing locked that.
The registered `seo-technical` gate reads JSON-LD *written into* the HTML; it cannot see structured
data *built at runtime* from database values, which is where the claims with something at stake live: a
star rating and a listing count are what a buyer sees in the search result before they ever reach the
page. An `aggregateRating` gated on the average ALONE would ship a rating for a seller with no reviews —
an average can be non-null with zero reviews — which is both a trust lie and a Google structured-data
violation. Locked by `jsonld-truth`; no defect found, which is the point of locking it.

Boards after these two: transition **39.4%** · layer **100%** (S1–S9) · dimension **61.5%**.

#### §10.9 · What the suite said — and one instrument lesson

Running the full 554-gate suite *while* driving the two-context spec by hand produced a red on
`marketplace-bank-journey` that was **my own collision**: both runs planted an `en_route` job for the
same provider, and the spec's `getByRole('button', {name:/track provider/i}).first()` picked the other
run's card. The locator is now scoped to the request the spec created.

> A role+name locator that can address the wrong row is not testing user-visible behaviour, it is
> testing whichever row sorted first. Playwright's "prefer role and name" is right about *stability*
> and silent about *which one* — under concurrency you must still scope to the entity under test.

#### §10.10 · The dimension denominator — a wrong diagnosis, corrected by reading the registry

The board read `max(len(dims_hit), 13)` — a hardcoded floor — and the first diagnosis here was that
the 13 was **invented**, because the roadmap's §-table lists MK1–MK10 and stops. That diagnosis was
**wrong, and the fix built on it would have been a new bug**: deriving the denominator from this
document's prose would have dropped three live classes and reported 100% while three were unasserted —
a short denominator, the exact failure the change was meant to prevent.

`marketplace_deepwalk_state.json` tracks **thirteen** `dim_classes`. `MK11-error-remedy-actionability`,
`MK12-post-action-coherence` and `MK13-reachable-capability` were added after the §-table was written,
and Board 2 has been scoring all thirteen the whole time. **The prose was stale; the registry was
right.**

> **Derive from the REGISTRY the other board already scores, not from the prose that describes it.**
> "Hardcoded" was the real defect and "invented" was not — a floor that happens to match today's
> registry is still a floor, and it silently stops matching the day a fourteenth class lands. The
> correct source is `dim_classes` itself, so a new class enters the denominator by existing.

Two things survive the correction:

1. **The UFAI half was never measured at all.** The board's label promised "MK/UFAI classes" and a
   single blended number cannot say that one family is complete while the other is untouched. UFAI is
   now its own axis, read from `ufai_pillar_map.json` — the artifact the UFAI instrument produces,
   whose per-page dim keys *are* the class list. Folding two denominators together is how a green axis
   hides an untouched one ([[feedback_phase_table_is_one_axis_build_the_compass]]).
2. **MK11–13 were genuinely unasserted by the bank** — and each already has a registered gate, so the
   cells are recorded `covered_by` with that gate's own printed result quoted, never rebuilt:
   `error-remedy-actionable` (an error must not propose a remedy the system knows cannot work),
   `post-action-coherence` (a success message must not outrun the page), `reachable_capability` (an
   empty state must not promise what nothing can produce — both admin consoles said "No open disputes"
   for a queue no buyer can ever file into, because the dispute flow left with the payment rail).

The three cells that closed the MK1–MK10 half each found or locked something nothing else did:
**MK7 `jsonld-truth`** (runtime structured data may not outrun the row — `seo-technical` reads only
JSON-LD *written into* the HTML); **MK4 `lifecycle-state-reachability`** (found `sold`: a chip, a border
rule, a schema.org/SoldOut mapping and a *seller-tier calculation that counts sold listings* — with
nothing that writes it, so the tier counts a number that is always zero); **MK8 `payment-disclosure`**
(while `PAYMENTS_ENABLED=false`, the money step must say WorkHive never holds the payment and therefore
cannot reverse it).

| Board | Before | After |
|---|---|---|
| dimension (MK) | 76.9% *against a hardcoded floor* | **100.0%** of the 13 the registry tracks |
| ufai | *not measured, but implied by the label* | **24.0% of 25** — stated, not hidden |

#### §10.11 · Opening the UFAI axis without over-claiming it

`ufai 0.0% of 25` was the honest starting point, and the temptation was to close it by declaring the
bank's cells "related to" UFAI classes. That is the over-claim the whole anti-duplication discipline
exists to stop.

The instrument answered it instead. `ufai_pillar_map.json` records nine cells on `marketplace.html` as
**`pct: null` with no dims** — genuinely unmeasured *by the UFAI walk itself*: `F2_correctness`,
`F5_round_trip`, `I1_auth_gating`, `I2_role_permission`, `I3_tenancy_isolation`, `I5_auditability`,
and three architecture cells. Several of those are things the bank had **already proven** and simply
never declared.

So each tag is earned by an assertion the cell already makes, and the earning sentence is written into
the cell as `ufai_earned` so the claim is auditable rather than asserted:

| Cell | Class | The assertion that earns it |
|---|---|---|
| `TB-L4-service-views-party-scope` | I3 · I2 | a signed-in stranger reads 0 rows; the **owner** still sees their own top-up |
| `TB-S9-knowledge-writeback-roundtrip` | F5 · I3 | provider completes → the **client** reads the entry; a different hive reads 0 |
| `TB-S6-realtime-map-datapath` | F5 · I2 | publisher writes → watcher sees the **new** position; a third identity sees nothing |
| `TB-J2-inquiry-roundtrip` | F5 | the round trip the journey board marked done and never walked |
| `TB-MK1-trust-signal-integrity` | F2 | every rendered star rating has a canonical backing row count |
| `TB-S5-edge-push-audience-selection` | I2 | the client's own provider profile is excluded from their own hail |
| `TB-MK8-payment-disclosure` | F2 | the copy states what the platform actually does with money |

**ufai 0.0% → 16.0% (4 of 25),** every point of it backed by a re-runnable assertion that already
existed. The bank does not re-grade what `service-ufai-deep` walks; it claims only cells that walk
records as unmeasured.

#### §10.12 · I5 and I1 — the two the bank could honestly claim, and what building them exposed

**`I5_auditability`** pulls in two directions at once and the cell is the distinction between them:
*history is append-only, consequences are not.* A job walked forward by the provider and then cancelled
by the client keeps all **4** of its state events, attributed — the provider's two moves recorded as the
provider's, the cancel as the client's — while the settlement commission that only makes sense for a
completed job **does not exist**. A surviving claim is not an audit trail; it is a wrong number that
will be believed because it sits in a ledger. (The mirror defect is already on record:
[[feedback_records_that_outlive_the_action]], where an audit row, a ledger row and a knowledge row all
outlived a reversal.)

That cell also carries a **visibility control** — it plants a ledger row and proves the same query can
see it — because of a mistake made earlier in this very arc: the S9 idempotence count ran under an
identity RLS hid the rows from, returned 0, and would have read green either way. **Any assertion of
ABSENCE now has to prove it could have seen a presence.**

**`I1_auth_gating`** turned out to be a hole in the bank's OWN lane. The derived matrix generates an
`anon` authority-negative for *every* guarded transition — and the SQL runner maps `anon` to no probe
identity, so it **skipped every one of them**. The partition with the largest possible blast radius, an
unauthenticated stranger on the public internet, was enumerated as an obligation and never executed.
The cell executes it: anon **can** read the active catalogue (a marketplace nobody can price has nobody
to join it) and reads **0** live positions, **0** top-ups, **0** requests, and cannot create a job.

It also records an OBSERVED contract rather than a wish: the service provider directory **refuses anon
today** — its only page read is inside `svcShowQuotes`, where the caller is a signed-in client — which
is correct for the current product and worth knowing if that directory is ever meant to become an SEO
surface the way the classic seller profiles are.

Two instrument fixes fell out, both now permanent: a single 42501 **aborts a postgres transaction**, so
each anon read is its own plpgsql exception block or the sequence stops at the first denial and the
rest silently never run; and emitting from inside one requires `RAISE NOTICE`, which psql writes to
**stderr** — the runner parsed stdout alone and reported a fully-passing probe as having emitted
nothing.

**ufai 0.0% → 24.0% (6 of 25):** F2, F5, I1, I2, I3, I5.

#### §10.13 · A3/A4/A5 — the attempt, and why the answer is "owed with evidence"

The last three cells the UFAI map calls unmeasured got a real build attempt rather than a shrug, and
the attempt is the record:

**A4 (state management)** was hunted as a concrete stale-hive defect. `marketplace.html` captures
`const HIVE_ID = whHiveId()` at load and stamps it on every hail — which would file work into the
**wrong hive** if a switch could happen while the page is open. It cannot: every `wh_active_hive_id`
write lives on `hive.html`, and reaching the marketplace from there is a full page load, so the const
is read fresh. **No defect — and that is a finding, not a shrug.** It also names its own unblock: the
moment an in-page hive switcher exists, the claim becomes "a write reads the hive at WRITE time" and
the cell is buildable that day.

**A3 (configurability)** reduces to the D9 knobs, which have no values yet and are Ian's to set.
**A5 (extensibility)** is *demonstrated* rather than assertable — this arc's own denominator grows by
itself when a guard changes, which is precisely the claim A5 makes; a cell asserting it would be a cell
asserting the bank exists.

All three are recorded as **`owed` with the evidence and the unblock written into the cell**, not
quietly excluded and not banked as a weak green. Inflating a board with an assertion that proves
nothing is the same defect as a short denominator, one step later
([[feedback_build_structure_to_make_it_liveable]]).

#### §10.14 · The role-pair rule is now ENFORCED — and it was never one journey's problem

Ian's finding is no longer a note in a memory file; the scoreboard computes it.

**`W` is DERIVED, never trusted.** The service board already computed the walk phase from
`walked.personas`/`walked.states`; this board read whatever was typed into `phases.W`, so a hand-set
`done` could outrank the evidence. It now derives — and on today's state all 21 marketplace journeys
already agreed, so the board did not move. That is the point: the change closes a door nobody had yet
walked through.

**A declared `role_pair` caps the walk at `partial` until BOTH sides appear.** `>=2 personas AND
>=2 states` is satisfiable by two people standing on the same side of a handoff. The rule now reads
`role_pair: ["publisher:P-provider", "watcher:P-client"]` and requires each named persona in
`walked.personas`. The selftest proves all three directions: two watchers do **not** complete a
two-sided walk, the missing side is **named** (a number would hide *which* side), and one persona per
side completes it.

**MEASURED after the merge: FOURTEEN of the 54 journeys are provably one-sided.** The estimate before
running it was "five more"; the rule found nearly three times that, which is the argument for encoding
a rule in the instrument rather than eyeballing it.

| Journey | The side never walked |
|---|---|
| `SJ-J29-live-map-tracking` | **publisher** — the only thing that emits a position (Ian's original) |
| `SJ-J31-consumer-track-review` | publisher, again |
| `SJ-J28-push-job-offer` | **trigger** — nobody hailed |
| `SJ-J33-idle-area-presence` | publisher |
| `SJ-J27-dayplanner-job-lands` | the **client** whose job lands |
| `SJ-J01` / `SJ-J02` / `SJ-J22` / `SJ-J24` / `SJ-J30` | the **responder/quoter** — every hail was walked as the hailer only |
| `SJ-J06-quote-select` | the **quoter** who has to send the quote |
| `SJ-J07-job-run-full-state-walk` | the **watcher** — the client never saw the job run |
| `SJ-J09-cancel-client` / `SJ-J10-cancel-provider` | the **notified party** — a cancellation walked only from the canceller's side proves nobody was told |

`SJ-J09`/`SJ-J10` are the sharpest: a cancellation is *only* meaningful to the person it strands, and
both were complete on the canceller's side alone.

Each was `W: done` on a persona count. Declaring the pair does not fix the walk — **it makes the gap
measurable**, which is the only thing a board can honestly do.

Equally deliberate: journeys with **no** pair declared. `J05-accept-race` walks two providers because
the race *is* between two providers; `J17-voucher-redeem` is genuinely a client-only act. Manufacturing
a pair where none exists would invent a gap as dishonestly as ignoring a real one.

**The journey ratchet grew a scope-growth proof** to match the transition board's: absorbing 33
journeys drops a 100% board, so `--accept` allows a journey-board fall **only** when the count grew and
the earned phase-points did not — "we added journeys" can never become the cover story for a walk that
stopped holding. The merge itself is staged and deliberately not run while the full suite is in flight,
because it moves a denominator the suite's ratchet gate is about to read.

**The merge landed and the ratchet re-baselined with proof:** journeys **100% -> 96.9%** over
**21 -> 54** journeys while earned phase-points rose **105.0 -> 261.5**. `--accept` REFUSED the first
attempt — the baseline predated the proof fields, so scope growth could not be demonstrated — and only
succeeded after the prior counters were backfilled by MEASURING the pre-absorption state file. A
ratchet that cannot be talked into moving down without evidence is the whole point of having one.

**NEXT:** walk the 14 missing sides — `SJ-J09`/`SJ-J10` first, because a cancellation walked only from
the canceller's side proves nobody was told. The two-context harness already exists for exactly this.
Then harvest the 6 night-crawler dry-run chunks into `substrate/external/`.

#### §10.15 · What walking the missing sides actually found

The role-pair rule was supposed to be a measurement change. Walking the first two gaps it named turned
up a product defect and a live security exposure.

**`SJ-J09` / `SJ-J10` — the cancellation told nobody.** Both journeys were walk-complete from the
canceller's side alone. Searching every function that touches `cancelled_by_client` /
`cancelled_by_provider` returned exactly two: the availability sync and the status guard. **Nothing
notified the other party.** A client could cancel while the provider was EN ROUTE — their availability
quietly flipped back to `online`, the job vanished from their list, and they kept driving to a site for
work that no longer existed. Wired in mig `20260729000018` onto the push rail that already carries
"New job nearby", and banked with 8 assertions: the right party in each direction, an ACTIONABLE
message (*"stand down - do not travel"*, not just "Job cancelled"), the canceller not paged about their
own action, no duplicate on a re-fire, and nobody paged for a hail cancelled while still broadcasting.
`enqueue_service_push_uids` is a NEW NAME, never an overload — a second PostgREST signature would
PGRST203 the endpoint for every caller.

**`SJ-J06` — the quoter side had no evidence at any altitude.** A quote-selection journey walked as two
CLIENTS has no content: nobody sends a quote. Every other flagged journey had its missing half's data
path banked by some cell built this session; this one had nothing. The probe found the RLS posture
already correct in all four directions — the provider can quote, a rival cannot forge one under their
name, the client cannot mint one, and a rival reads 0 of a competitor's price — which is worth locking
precisely because *"nobody has checked"* is not the same as *"nobody can forge one"*.

**Arc G's view gate then surfaced a live exposure.** Probing what it flagged, **as `anon`, with no
login at all**, returned **2182 rows of `v_cron_health`** — every scheduled job by name, its run
history, and which ones were failing. `v_storage_health` and `v_service_slo` (allocation rate,
time-to-accept, completion rate) were the same shape. No consumer existed for any of them anywhere in
the repo. Revoked in migs `20260729000019` / `20260729000020`.

Three things that came out of fixing it:

1. **The test bank rejected the obvious fix in seconds.** Setting `security_invoker = on` on
   `v_service_job_tracking` made the live tracking map return **nothing** for every legitimate client —
   the view executes as the caller, and a client deliberately has no SELECT on `service_providers`.
   `TB-S6-realtime-map-datapath  watcher_sees_1: want '16.4100' got None`. The two party-scoped views
   are legitimately owner-executed with their own `auth.uid()` predicates; the gate learned a NAMED
   exemption that **re-reads the view definition** and reds if the predicate ever disappears — because
   a `DROP VIEW` + `CREATE VIEW` carries neither options nor predicates across, which is exactly how
   two marketplace views once reverted to owner-runs and leaked every hive's orders.
2. **A client GRANT is the other half of the leak.** After the revoke the gate still reported the same
   views as leaking: it checked the view option and not the grant, so it could not tell *closed* from
   *still open*. It now reads `information_schema.table_privileges`. Verified in both directions — GREEN
   on the current state, and a synthetic client-granted owner view still reds.
3. **Probe as `anon`, not only as a signed-in stranger.** That role is reachable by anyone with the page
   source, and it was the whole difference between "internal metric" and "public".

#### §10.16 · The UI half of the cancellation — a second defect, under the first one

The SQL cell proved the provider is *told*. The two-context walk asked whether the screen they are
actually looking at agrees. **It did not.**

`marketplace-seller.html` had **no interval and no realtime subscription**: once loaded, the job list
was frozen. So the sequence was — client cancels → the push says *"stand down - do not travel"* → and
the page the provider is holding still lists the job as live, indefinitely. **The product contradicted
its own notification, and the screen is the one they trust while driving.**

The walk was written to fail first and did, holding the dead job for the full 40-second window. The fix
is a **poll, not a subscription**, and deliberately so: the client's tracker already polls every 10s, so
this matches a cadence the platform already pays for rather than adding a realtime channel with its own
cleanup contract (L3/L4 — every channel in a module-level variable, counted on `beforeunload`). It runs
only while a job is live, pauses on a hidden tab, and clears on unload — the same discipline as
`svcGeoSync`, because **a timer that outlives its reason is the leak that discipline exists to prevent.**
Green in 27s, caught on the second poll.

**And the registration cascade fired in the same run.** `validate_timers.py` immediately reported
`marketplace-seller.html uses setInterval but is not in LIVE_PAGES` — the page had to join the list that
gets checked. That is the platform's own gate catching a new feature's missing registration within
minutes of it existing, which is what the cascade discipline is for.

**NEXT:** the remaining 11 missing sides, the live reds re-run cleanly once the full suite lands, then
the substrate rebuild (LAST, after every doc write).

#### §10.17 · The client side had the same defect, and fixing it cost three more

`SJ-J07` was walked as two clients — the *mover* was never in it. Walking that side found the mirror of
the seller-page bug, and worse: the tracker map **does** poll, so on a job being watched **the map moved
while the label beside it still read "Provider accepted."** A screen that disagrees with *itself* is
worse than one merely stale, because the person cannot tell which half to believe.

Fixing it produced three further defects, **every one caught by another cell in the same file** and not
one of them visible from reading the code:

1. **The poll hammered a dead network.** Offline, it kept calling the loader whose catch repainted the
   pane as "Couldn't load services" every 15s — a page flapping into an error state on its own, on top
   of a person who already knows they are offline. Caught by the S2 offline cell.
2. **It repainted the pane out from under an OPEN tracker map**, destroying it. Caught by the S6
   live-map cell: *"a provider marker was never placed on the watcher's map."* The tracker owns the
   refresh while it is up; the list poll yields to it.
3. **`whLivePoll` evaluated its condition only at ARM time**, so a condition that became false never
   stopped the timer. It re-checks every tick now. *A poll that cannot notice its own reason has ended
   is the same defect as a timer with no `clearInterval`, one step subtler.*

And a fourth, from the centralization itself: **`showToast` is defined inside each page's IIFE and is
not on `window`**, so the shared `whRequireOnline` reached nothing and the guard refused writes **in
total silence** — worse than no guard. The wording stays central; the **sink is passed in** by the
caller. That one was found by reading the live page state rather than guessing a third time.

**The pattern worth keeping:** every one of these was a bug I introduced while fixing a bug, and every
one was caught within minutes by a cell built earlier in the same session. That is the difference
between a bank and a checklist.

**NEXT:** the remaining 10 missing sides, then the live gates the contaminated suite run left
unverified (`ufai-deep`, `read-battery`, `jsonb-shape`, `axe-live`, `arc-I idle`) re-run one at a time
now that nothing else is driving the browser.

#### §10.18 · The clean re-run — and a dead UUID that had been inventing page defects

With the suite finished and nothing else driving the browser, the contaminated live gates were re-run
one at a time.

**`service-ufai-deep` went GREEN** — the 16px `← WorkHive` back link was the whole of it.

**`read-battery` was the interesting one.** It reported six pages failing *"DB empty -> empty-state
(no error)"*, each with `db=0`. None of those pages were wrong. **The hive UUID hardcoded as the
battery's fallback does not exist** — a reseed removed it, and every assertion had been quietly
measuring an empty world.

> That is the worst shape a test failure can take. It does not error and it does not skip: it renders
> six plausible, specific, entirely fictional defects and sends you to read page code that was never
> wrong.

**Seventeen registered instruments were pinned to hives that are gone.** The class already had a memory
([[feedback_stale_hive_fixture_mjs_mirror]], "3 stale UUIDs"); it had grown. New gate
`fixture-hive-exists` resolves every pinned hive against the live DB, with two principled exemptions —
the all-zeros UUID proves a NEGATIVE, and a UUID the file itself INSERTs is self-minted inside a
rolled-back probe and is *supposed* not to exist. **My first cut flagged 37, most of them correct
code**; scoping to instruments the suite actually runs and exempting self-minted fixtures brought it to
the real 19, now baselined forward-only so a NEW one reds while the recorded ones stay printed.

`read-battery` itself now **resolves** its hive — the signed-in supervisor's own most-populated hive
with a deterministic tie-break — rather than pinning a literal that cannot survive a reseed. And the
resolver had to learn the same lesson `_fixtures.ts` learned earlier this session: **prefer the hive
where they hold the ROLE**, not the one with the most rows.

**Six phantoms became two real findings**, plus one spec bug of my own making:

| | |
|---|---|
| `audit-log` 30-of-187 | **my instrument, fixed** — the page paginates at 30 behind "Load more"; comparing the rendered count to the full row count asserted that pagination is a bug |
| `integrations.html` | **REAL, reproducible**: shows an empty state while the signed-in **supervisor** has 9 `integration_configs` in the active hive and the RLS policy plainly admits them |
| `plant-connections.html` | **REAL**: every hero reads 0 while `v_external_sync_truth` holds 4 rows |

**CORRECTION — both of those "real findings" were the instrument too, and I had already written the
lesson that should have stopped me claiming otherwise.** Triaged properly:

* `integrations.html` renders all 9 configs correctly. Its **hero check passed in the same run**, which
  was the proof sitting right beside the failure. The empty-state detector was a regex over the WHOLE
  DOCUMENT, and that page legitimately carries six secondary empty strings — *"No keys yet"*, *"No
  conflicts found"*, *"No synced records found"*, *"No live sync configs yet"*. Any one of them, doing
  its job, flipped the flag.
* `plant-connections.html`'s hero selector `#wh-conn-queue` **does not exist on that page at all** (its
  ids are `content` / `details-pane` / `empty-state`). A missing selector reads as 0 and accuses the
  page of rendering nothing.

Both are fixed in the instrument, not the pages: emptiness is now scoped to an `emptyIn` region that
names what the claim is about, and **the battery checks its own selectors** — a declared selector that
is not on the page now fails as *"the SPEC is stale, not the page"* instead of quietly returning zero.

**49/58 → 68/68 green.** Six phantoms, then two more, all from three instrument defects: a dead hive, a
document-wide regex, and a selector for an element that never existed.

> Three times in one triage the instrument was the culprit, and the third time was *after* I had
> written the memory saying so. Having the lesson is not the same as reaching for it — the habit that
> actually works is mechanical: **before reporting a page defect, check whether another assertion in
> the same run already contradicts it.** Integrations' passing hero check was visible the whole time.

**NEXT:** triage `integrations` and `plant-connections`; the remaining 10 missing sides; and the last
contaminated live gates (`jsonb-shape`, `axe-live`, `arc-I idle`).

#### §10.19 · The 14 suite failures, closed one at a time

| Failure | Verdict |
|---|---|
| substrate-freshness | **mine** — this session's doc/skill writes; rebuilt, 715 chunks fresh |
| render-budget | **mine** — scope-grown on Ian's call, with a proof the gate re-checks every run |
| bughunt anti-drift | **fixed** — 3 GAP → 0, party-scoped views joined the isolation gate |
| marketplace-bank-journey | **mine** — my own concurrency collision; locator scoped, flake/quarantine policy added; 4/4 |
| service-ufai-deep | **fixed** — the 16px `← WorkHive` back link, the only in-layout door on the page |
| read-battery | **THREE instrument defects**, zero page defects; 49/58 → **68/68** |
| intelligence-jsonb-shape | **a REAL defect** — see below |
| arc-I idle-timeout | contamination; **4/4 PASS** run clean |
| axe-live authed surfaces | contamination; **PASS at baseline 0** run clean |
| Arc G view security_invoker | **fixed** — the anon cron-history exposure closed, gate refined and verified both ways |
| calc-L3 · Arc H · FB4 | the AI chain rate-limited by **this session's own eval burst** — correct behaviour, self-clearing |
| Arc X Family C | **triaged** — and it was a fourth instrument false-positive |

**The jsonb one was real and had a live source.** `asset_risk_scores.top_factors` held a jsonb STRING
in 2 of 352 rows, and `parts_staging_recommendations.parts` in 1 of 4:

```
top_factors = "[\"pm_overdue\", \"repeat_fault\", \"mtbf_approaching\"]"   -- a jsonb STRING
top_factors =  ["pm_overdue", "repeat_fault", "mtbf_approaching"]           -- what a reader needs
```

A consumer's `.map()` gets **nothing** from the first. The asset does not say "no risk factors" — it
renders an empty list beside a real risk score, which reads as *this asset's risk has no explanation*.
No error, no null, no empty column.

Repairing the rows would have been the shallow half: **the seeder itself was writing
`json.dumps([...])` into jsonb columns** in two flows, so the next reseed would have written them
straight back. Both sites now pass the list. Migration `20260730000001` repairs the existing rows and
is idempotent — a second run touches 0.

**Ten of the fourteen were instruments or my own edits.** One was a real product defect. Three are a
rate limit I caused. That ratio is worth remembering the next time a red suite looks like a broken
platform.

#### §10.20 · Arc X Family C — the fourth instrument false-positive in a row

The last open suite item flagged `marketplace.html#review-comment` as a C1 *recall-dependent entity
input*: a free-text field naming an enumerable entity with no picker.

It is a **prose review box**. The rule fired on the word **"part" inside the QUESTION** — *"How was the
part, and how did the seller handle it?"* There is nothing enumerable to pick from, because the answer
is an opinion. And it already carries a persistent visible label (*"What happened?"*, line 2331), so the
sibling C2 recall concern does not apply either.

**My first instinct was wrong in an instructive way.** I read "C1" and assumed *missing label* — and
went to add one that was already there, one line above. The rule I was actually failing was a different
one entirely. **Reading the gate's own definition before acting on its output cost thirty seconds and
saved a pointless edit to working markup.**

Triaged as `NL_NOTE` in `arc_x_baseline.json` with the reasoning recorded — the 17th classified
exemption, version-controlled and auditable rather than buried in the scanner. That is what the gate
asks for: *"un-triaged, need a picker"* means **either** a picker **or** a written classification.

**All 14 suite failures are now closed**, every one re-verified by running it clean:

* **1** real product defect (the double-encoded jsonb, plus the seeder that was its live source)
* **1** real security exposure (anon reading 2182 rows of cron history)
* **2** real product defects found by walking role-pair gaps (the cancellation telling nobody; both UI
  halves frozen after load)
* **4** instrument false-positives (a dead hive, a document-wide regex, a selector for an element that
  never existed, and a rule I misread)
* **3** contamination from my own concurrent browser runs
* **3** an AI rate limit my own eval burst caused, correct behaviour and self-clearing

> **The lesson worth keeping from the whole triage:** a red suite is not a broken platform. Ten of
> fourteen were the measuring equipment or my own edits. Check whether another assertion in the same
> run already contradicts the finding, and read the rule before you act on it.

**NEXT:** the remaining 10 role-pair missing sides, then a CLEAN full suite run end to end.

#### §10.21 · The worst of the frozen-page findings was caused by my own fix

Walking `SJ-J28`'s missing side — the **trigger** — found something worse than the two before it, and
the cause was the fix I had shipped an hour earlier.

The first poll armed only while `jobs.some(SVC_ACTIVE)`. That froze the page in **exactly the state the
product exists to serve**: a provider who is online, holding no job, waiting for work. A hail arrived
and they were told nothing.

> Refreshing only once you already have work is the opposite of a job feed.

I had read that condition after writing it and thought it was right. What found it was not re-reading
the code — it was **walking the state I had not considered.** A fix verified only in the case that
motivated it is a fix with an untested half. The poll now arms while the provider is AVAILABLE (a hail
can land) **or** has a live job (its state can change under them).

**And the S6 marker assertion was flaking on my own instrumentation.** Green on a direct run, red under
the gate, nothing about the product different: `whMap` is lazy-loaded on the first Track press, so my
wrapper polls for it every 100ms and can install *after* `svcTrack` has already called `marker()`. The
assertion now accepts either witness of the same claim — the recorded call **or** the DOM overlay
MapLibre actually rendered. Stable across consecutive runs.

Worth separating from the quarantine policy deliberately: that policy is for **fixture** failures, where
the harness could not put the journey in a position to be judged. **Assertion flake is a different
animal and must be fixed, not quarantined** — quarantining it would have hidden a race in my own test
rather than removing it.

| | Before | After |
|---|---|---|
| journeys | 96.9% | **97.4%** (ratchet up, not scope-grown) |
| one-sided journeys | 14 | **11** |
| transition | 41.0% | **43.1%** (103/239) |
| journey lane | 4 cells | **5**, twice consecutively green |

**NEXT:** the remaining 11 one-sided journeys — `SJ-J29`/`SJ-J31`/`SJ-J33` (the publisher side, where
the SQL data path is banked and only the render is owed), then the five hail-responder sides, then a
CLEAN full suite run end to end.

#### §10.22 · SJ-J33 and the two publisher sides — and a poll I deliberately did NOT add

**`SJ-J33-idle-area-presence`** was walked as two VIEWERS. The publisher — a provider flipping their
availability, the only act that changes the number — was never in it. Now walked in two contexts: the
provider is taken **offline first** so "came online" is a real transition rather than a coincidence of
the seed, goes online through their **own session**, `v_service_area_presence` rises by exactly 1, and
the viewer's rendered count **equals the view's total**. *A liquidity hint that overstates is worse than
no hint — it tells someone to wait for help that is not there.*

**I did not add a poll here, and that is the point.** `svcLoadPresence` runs once, and the design says
why in its own comment: the hint is **additive** and *silence is golden* — it renders nothing rather
than a discouraging "0 providers" the client can do nothing about. Three frozen-page findings in a row
made a poll feel like the answer to everything; adding a third timer here would have been **inventing a
requirement the design explicitly rejected.** The assertable claim is that the number is TRUE when
shown, not that it live-updates.

**`SJ-J29` and `SJ-J31`'s publisher side were already walked** and simply never credited —
`TB-S6-realtime-map-ui` drives the provider's own page and logs which path fired (*"publisher path: page
watchPosition"*). J29 is the exact side Ian named. J31's residual is stated rather than glossed: that
cell's watcher was a client-supervisor, not a consumer, and it does not cover J31's review step, so the
pair is satisfied while the consumer-specific half stays owed.

**A cleanup bug found on the way.** `afterAll` opened with `if (!requestId) return;` — a leftover from
when this file held one test. Every later restore sat behind it, so a `--grep` at a single cell left
another cell's state behind. Each restore now guards only on its own id, and the presence walk captures
the provider's original availability so a real seeded row goes back exactly as it was.

| | Before | After |
|---|---|---|
| journeys | 96.9% | **98.0%** |
| one-sided journeys | 14 | **8** |
| journey lane | 4 cells | **6** |

**NEXT:** the 8 remaining — five hail **responder** sides (`SJ-J01/J02/J22/J24/J30`), the **quoter**
(`SJ-J06` UI half), the **notified client** (`SJ-J10`), and the **client** of a landed dayplan job
(`SJ-J27`). Then a CLEAN full suite run end to end.

#### §10.23 · Every role-pair side walked — 14 to ZERO — and four root causes I nearly widened away

The rule Ian's finding produced exposed 14 one-sided journeys. **All 14 are now walked**, in nine
two-context cells, stable at 9/9 across three consecutive full-lane runs with the `WH_TB_FREEZE` teeth
still biting.

The last stretch was almost entirely me debugging my own harness, and the shape of that is the lesson:

**1 · An INSTANT insert is normalised to `requested`.** `status: 'broadcasting'` in the payload is a
*request*, not a fact — and a hail that is not broadcasting cannot appear in any provider feed. It read
as *"the page never refreshed"* and sent me to look at polls. The sibling cell never hit it because a
`quote`-mode insert keeps its status. Every hail cell now patches the status and **asserts it stuck**.

**2 · "The first provider bound to a login" reads an UNORDERED list.** One run picks a provider beside
the fixture site, the next picks one 200km away; one has a `worker_name`, one is a hive company. A cell
passed alone and failed in sequence with nothing about the product changed. All nine now share one
deterministic resolver that also demands a login owning **exactly one** provider profile — because
`accept_service_request` and `submit_service_quote` each choose *which* profile acts, so asserting on a
single id fails on correct behaviour.

**3 · Cross-test chip bleed.** An earlier cell legitimately leaves the client with a second accepted
job, so a page-wide `getByText('Provider accepted')` reported the *other* card and the cancellation
looked unnoticed. Scoped to the card that names its own request.

**4 · An assertion that depended on MapLibre and an external tile host.** Counting `marker()` calls
races the lazy load of `wh-map.js`; the DOM fallback needs WebGL plus `tiles.openfreemap.org`. One run in
three failed, and **two timing widenings did not help because timing was never the cause** — the cell was
measuring network weather. It now asserts the tracker's own in-DOM confirmation, which the page writes
only after a position arrives. 5/5 where it had been 1-in-3.

> **I reported that de-flake once before it existed.** Two string replaces failed *silently* on a
> JS-escaped apostrophe, so the file never changed and four lucky passes looked like a fix. A silently
> failed edit is worse than a loud one: it turns "I fixed it" into a false statement. It is applied now
> by line index and verified by grepping for **both** the old string's absence and the new string's
> presence — and that verification is the habit, not the exception.

**`SJ-J27` closed by evidence rather than argument.** `schedule_items` is owner-only RLS
(`auth_uid = auth.uid()`) and `marketplace.html` reads it **zero** times — a provider's calendar is
deliberately invisible to the client, so the client half has nothing further to walk. What the client is
owed is that the job reads accepted, which is walked; and the accept cell now asserts the dayplan entry
**landed**, so the provider side is proven rather than assumed.

| | Start of arc | Now |
|---|---|---|
| one-sided journeys | 14 | **0** |
| journeys board | 96.9% | **99.4%** |
| journey lane | 1 cell | **9**, 9/9 × 3 runs |
| SQL lane | 49 | **57/57** |

#### §10.24 · The ufai board, and saying which instrument owns what

Tagging the nine journey cells with the UFAI classes their **own assertions already earn** took the
board **24% → 36%** (F2, F5, F6, I1, I2, I3, I5, U3, U4). Every point has the earning sentence written
into the cell as `ufai_earned`, so the claim is auditable instead of asserted.

**But 36% would read as 64% of neglect, and most of that 64% is another gate's job.** So the split is now
recorded rather than left to inference — the same "one metric masks another axis" failure this compass
exists to prevent:

| Family | Owner |
|---|---|
| **F2 F5 F6 · I1 I2 I3 I5 · U3 U4** | **the bank** — claimed, each by a named cell |
| **U1 U2 U5 U6 U7** | **the UFAI walk** (`service-ufai-deep`): 44px targets, vendored axe, 360–1920 overflow. A bank cell asserting these would duplicate a live browser sweep that already runs — and duplicate it worse. |
| **A1–A6** | **not yet assertable, with evidence.** A4 was *hunted* as a concrete stale-hive defect and found genuinely absent (a full page load makes the cached value fresh); A3 reduces to the D9 knobs, which have no values yet; A5 is *demonstrated* by this arc's denominator growing by itself. Owed-with-evidence, never banked as a weak green. |
| **I6** | **claimed** — safe-by-default is exactly what the offline guard does: refuse the write *before* it fires, across 17 user-triggered writes. |
| **F1 · I4** | **the honest next frontier**, and smaller than it first looked. |

**CORRECTION, made before acting on it.** I first wrote that `F1/F3/F4/I4/I6` had "no cell and no
evidence." Reading `ufai_pillar_map.json` per page instead of per class shows otherwise: **F3 and F4 are
graded 100% on every marketplace page** with named dims (X1/E4, W1/X3), so they were never open. The
genuinely unmeasured cells are `A3/A4/A5` on all four pages (dispositioned owed-with-evidence),
`F1` on three, `I4` on two, and `I6` on three — and `I6` is claimable today, which is why it moved to
the row above.

That is the third time in this session I read a number before checking what produced it. The habit that
would have caught all three is the same one: **open the artifact the number came from, per row, before
writing a sentence about it.**

**NEXT:** a CLEAN full suite run end to end — nothing else driving the browser this time — then `F1`
(completeness on the seller/admin/profile surfaces) and `I4` (client validation on admin/profile), which
is the whole remaining frontier once the A-series is set aside with its evidence.

---

### §10.25 · ★★ THE SKIPPED PARTITION — two authority classes were enumerated, never executed, and one hid a live exploit for five weeks (2026-07-30)

The bank's transition board sat at **44.0%** with 136 owed cells. Reading *why* they were owed, rather
than working down the list, found that the runner was **silently skipping two entire authority
partitions** — `anon` (18 cells) and `admin` (18 cells) — because `actor_uid()` returned `None` for both
and the loop's `if ok is None: continue` swallowed them. Not failing. Not skipping loudly. Counted as
obligations, reported as owed, never once run.

Both were skipped for the same shallow reason: **the runner needed a uid to mint, and neither partition
is a uid.** `anon` is the ABSENCE of an identity (`set local role anon`, no JWT at all). `admin` is an
identity plus two rows (`hive_members` -> `auth_worker_names()` -> `marketplace_platform_admins`),
because `is_marketplace_admin()` cannot be faked with a flag. Teaching the runner both took ~30 lines and
moved the executed lane **57 -> 94 cells**, the board **44.0% -> 59.3%** (146/246).

> A partition with no probe identity is not a covered partition. It is a **silent** one — and it reads
> exactly like a covered one on the board.

**What was behind each door:**

| Partition | What executing it found |
|---|---|
| `anon` (18) | On the marketplace surface, RLS held everywhere — 0 rows on insert/update/delete, and `service_requests`/`service_providers`/`service_credit_topups` refuse at the GRANT layer (42501) before RLS is consulted. The finding was one level up. |
| `admin` (18) | The bank had **already derived** the assertion *an admin must be refused this transition* — and never run it. Building the admin identity to run it is what surfaced a live self-deal exploit in four guards. |

#### §10.25a · 1,430 rows an unauthenticated caller could destroy

Executing `anon` prompted the question one level up: *where is RLS not there to catch it?* **16 public
tables had `relrowsecurity = false` while granting `anon` INSERT/UPDATE/DELETE/TRUNCATE.** A rolled-back
`delete ... where true` as the `anon` role:

```
persona_knowledge   434 · embedding_cache 766 · multilingual_terms 207
equipment_reading_templates 15 · service_slo_targets 3 · avatar_state 3
ai_global_budget      1  <- the platform's AI spend cap
ph_intelligence_reports 1
                  ------
                   1,430 rows destroyable with only the anon key
```

The grants are the Supabase template default (`GRANT ALL ON ALL TABLES IN SCHEMA public TO anon,
authenticated`). That default is harmless on the ~130 tables where RLS is enabled and catastrophic on
these 16 — **the same grant, and the only difference is one line of DDL somewhere else.** So the
invariant is a CONJUNCTION, never a grant rule: *a base table may grant a write verb only if RLS is
enabled on it.* Fixed by **mig 20260730000002** (REVOKE on the 14 system tables; real RLS on the two the
client writes) and locked by the new **`unprotected-write-grant`** gate, which runs in `--fast` and whose
self-test PLANTS the defect and requires detection. Re-probed after the fix: **1,430 -> 0.**

Two sub-findings recorded as measured, not reasoned:

- **13 `v_*` views** were auto-updatable with anon write grants, 11 not `security_invoker` — the textbook
  RLS bypass (a write through a non-invoker view runs as the view OWNER, `postgres`, and an owner is
  RLS-exempt when `forced=false`). **Probed, it did not bypass**: 0 rows through `v_hives_truth` and
  `v_asset_truth`, and even a plain SELECT returned 0. The mechanism I predicted did not fire; the
  empirical result governs. Revoked anyway — a repo-wide grep finds zero writes through any `v_*` view,
  and a privilege nobody uses is only ever a future foothold.
- **TRUNCATE is the one verb RLS never covers.** An anon TRUNCATE on `marketplace_listings` fails today
  with `0A000 — cannot truncate a table referenced in a foreign key constraint`. That is a coincidence of
  the schema, not a security control, and it evaporates the day that FK is dropped.

#### §10.25b · the self-deal class, standing in FOUR guards five weeks after being fixed in a fifth

Minting the admin identity meant reading `guard_service_request_status`, which early-returned on
`is_marketplace_admin()` **before any party check**. A rolled-back probe minted an identity that is both
a platform admin and the matched provider on a completed job:

```
RESULT is_admin=t
RESULT provider_admin_settles_own_job_rows=1     <- completed->settled, the CLIENT's "I paid"
```

`completed -> settled` is reserved for `v_is_client` and fires `trg_mint_settlement_commission`. **A
provider-admin confirmed their own payment and minted their own commission.**

On 2026-07-29, mig `20260729000003` fixed *exactly this shape* in `guard_service_review` — the admin
bypass now applies only when the admin is not a party. That fix went to the one guard the live probe
happened to walk. **The identical unqualified bypass was left standing in all four status-machine
guards**, each defeating an invariant its own comments state out loud:

| Guard | Its own words | What the bypass allowed |
|---|---|---|
| `guard_service_request_status` | "the client confirms they paid" | provider-admin settles own job, mints own commission |
| `guard_service_topup_status` | the admin branch MINTS the credit inline | payer-admin verifies own GCash top-up -> **credits from a ref nobody checked** |
| `guard_marketplace_order_status` | "neither may be self-assigned by a buyer or seller" | seller-admin self-releases (self-minted `total_sales` + tier) or self-refunds |
| `guard_marketplace_listing_status` | "a listing goes live only after WorkHive review" | seller-admin publishes own listing unreviewed |

Fixed in **mig 20260730000003**, all four gated on `NOT <is a party>`. The exploit identity is not
hypothetical: there are two platform admins and one is the founder, who also sells services.

**Locked by the authored probe `TB-I2-admin-bypass-only-for-non-parties`, which asserts BOTH halves** —
because a fix that only closes the hole may have closed moderation with it:

```
selfdeal_publish_own_listing=blocked   moderation_publish_other_listing=works
selfdeal_release_own_order=blocked     moderation_release_other_order=works
selfdeal_verify_own_topup=blocked      moderation_verify_other_topup=works
selfdeal_credit_minted=0               moderation_credit_minted=1      <- the money oracle, read back
```

**TEETH VERIFIED** by restoring the vulnerable guard inside a rolled-back transaction: the self-deal
returned as ALLOWED, so the `blocked` assertions bite. The same technique settled a subtler question —
`service_requests` moderation returned **0 rows before AND after** the fix, because
`service_requests_party_update` RLS has no admin clause and filters a non-party admin's row away before
any guard runs. So on that table the bypass had exactly **one reachable effect: the self-deal**. The
probe therefore asserts moderation only on the three tables whose RLS *does* have an admin clause —
demanding a behaviour the platform never shipped is how a test gets "fixed" by inventing it.

#### §10.25c · two things I got wrong, both caught before they shipped

1. **I reconstructed a guard from a partial read.** My first draft of mig 003 rewrote
   `guard_service_request_status` from a grep of ~20 lines and **silently dropped three real rules**: the
   hive-provider branch of `v_is_matched_provider` (a hive's active member acts for the hive's provider
   profile), the "a new request cannot be born matched" refusal, and BOTH the `matched_provider_id` and
   `client_auth_uid` reassignment refusals. A security fix that quietly deletes three other security
   rules is a net loss. Caught by reading the whole function before replacing it, then changing exactly
   one line. I also nearly rewrote all four functions' `search_path` to one uniform value — they differ
   per function, and changing a `SECURITY DEFINER` function's search_path is itself a security change
   smuggled inside a security fix.
2. **My own fix opened an RLS hole one layer down.** Mig 002 closed the GRANT hole using three
   `USING (true)` policies, and `rls-open-policy` flagged all three against a forward-only baseline of 2
   — correctly. I had even written *"the permissiveness that remains is now WRITTEN DOWN instead of
   implied,"* which is not the same as not having it, and I had called owner-scoping `avatar_state` "not
   expressible without a schema change" and stopped there. It is a reason to make the change: **mig
   20260730000004** gives `avatar_state` the `auth_uid uuid DEFAULT auth.uid()` column it always needed
   (invisible to `voice-handler.js:1133`, which names no owner) and scopes both policies to it. That also
   closed a hole nobody had noticed: under the permissive policy one signed-in user could **hijack
   another's `session_id` row silently**. Now `stranger_hijack_rows=0`, `owner_upsert_rows=1`. Open
   policies back to the baseline 2, and the two gates that disagreed about these tables now agree.

**Boards:** transition **59.3%** (146/246, 100 owed) · layer 100% · dimension 100% · ufai 48% (its
documented ceiling — 12 of 25 earned by a named cell or gate; the rest owned by the live UFAI walk or the
three A-series cells recorded owed-with-evidence) · journeys 99.4% over 54 · one-sided 0 · SQL lane
**94/94** · ratchet PASS.

**NEXT:** re-run `playwright-smoke` standalone (it reported `skipped: seeder offline` after 20 min
against a label that says ~3 — the seeder answers in 0.06s now, so this is my own concurrency, the third
time this session; `trigger-function` passes standalone too, same cause) -> then the **85 sneak-path
cells** (replay / concurrency / out-of-order), the largest remaining block and the one the runner
explicitly excludes -> then the 17 `admin-or-system` cells on the three non-`service_requests` machines,
which need a deny-shape runner path.

---

### §10.26 · The transition board to 98.8%, and a registered gate that had never once run (2026-07-30)

Continuing from §10.25, the remaining owed cells were worked by asking of each one *why is this owed*
rather than *how do I mark this covered*. Four answers, four different kinds of work.

| Block | Answer | Result |
|---|---|---|
| `out-of-order` (22) | Executable all along — a one-UPDATE cell from an illegal origin | EXECUTED |
| `concurrency` (21) | Already locked, live, with teeth, by `service-dispatch-isolation` | `covered_by` |
| `replay` (20) | Money paths locked by `service-idempotency`; the ordinary chain was not | `covered_by` + a new probe |
| `session-switch` (22) | DB half executable; client half locked by `client-singleton` | probe + `covered_by` |
| deny-shape machines (16) | The runner only knew `service_requests` | EXECUTED via a new lane |
| `TB-MK9` (1) | Recorded "vacuous"; the vacuum was the thing to fix | EXECUTED |

**SQL lane 57 → 130 executed cells, transition board 44.0% → 98.8%** (244/247), all green, ratchet PASS.

#### §10.26a · The anti-duplication check paid for itself

Before building anything for the 85 sneak-path cells, the ~700-gate registry was read (§10.2's rule).
Two of the four kinds were already proven, better than a new cell would have:

- **`service-idempotency` (C14)** enforces once-only with four partial UNIQUE indexes AND attempts every
  replay live in a rolled-back transaction, *requiring* a refusal — because a partial predicate can be
  narrowed to uselessness without dropping the index, so presence is not proof.
- **`service-dispatch-isolation` (C3)** proves the accept race has EXACTLY ONE winner (the 2nd caller
  gets `lost_race_or_closed`), which is the concurrency sneak path exactly.

Rebuilding either would have been a slower second copy. What they did *not* cover became the authored
probe `TB-SNEAK-replay-and-session-switch`, and both halves of it were things I nearly wrote off as
"covered by nature":

```
first_fire_rows=1   replay_changed_status=no   journal_rows_for_one_transition=1
switched_uid_is_stranger=yes   stranger_continues_the_job=refused   real_provider_still_works=yes
```

The replay assertion is the **side effect**, not the status: `trg_journal_service_request` appends to
`service_job_events`, so a replay that journals twice writes a history saying the provider set off for the
job twice. Nothing errors — the timeline just becomes fiction. And session-switch is executed by changing
`request.jwt.claims` *between two statements of one transaction*: the second is refused, the real provider
still works afterwards, so the refusal is about identity rather than a poisoned row.

#### §10.26b · Two instrument bugs of my own, in the same shape as the arc's finding

1. **My out-of-order probe failed four cells on correct behaviour.** The first cut planted "two states
   earlier in the chain" — but `cancelled_by_client` is authorised from FIVE states, so an earlier
   position is very often *another legal origin*. The probe was demanding a refusal the guard rightly
   does not give: **the bank accusing the product**, which the derived-negatives code already carries a
   comment about, walked into from the other side. Fixed by deriving the origin from the authorised set
   itself (`legal_origins()` reads the bank's own `expect: allowed` cells), so it updates when a
   migration changes a transition. All 22 then passed and the 3 "inexpressible" cells became expressible.
2. **Seven more cells were hiding one layer above the skip I had just fixed.** §10.25 fixed a silent
   `if ok is None: continue` in the loop; `admin-or-system` was being dropped by the *comprehension*
   (`actor_uid(...) is not None`), before the loop, so it never reached the skip reporter and printed
   nothing at all. **A filter that excludes is exactly as silent as a bare `continue`.** Replaced with a
   named `has_identity()` that says which three answers exist and why.

The deny-shape lane also needed a different oracle. On a deny machine the guard blocks the *transition*
into the forbidden state (`NEW.status='published' AND OLD.status IS DISTINCT FROM 'published'`), so
re-firing at a row already there raises nothing and reports `UPDATE 1` — a row count alone reads that as
the guard having failed. Every deny cell now reads the row BACK (`FINAL=`), and on the one machine that
MINTS money it reads the ledger too (`LEDGER=`), because a second credit is invisible in `status`.

#### §10.26c · `TB-MK9`: the vacuum was the finding

MK9 was recorded owed as *"VACUOUS TODAY — 0 sellers carry a response_rate and marketplace_inquiries is
empty, so there is no rendered claim to diff against source truth."* That was the right call about
banking a green over an empty denominator, and the wrong place to stop: **the fix for a vacuous cell is to
manufacture the denominator.**

Checked before assuming, and the check mattered — there IS a living producer
(`trg_update_seller_response_stats` recomputes both columns from the inquiry history), so the NULLs are
the page's honest empty state, not a dead counter ([[feedback_trust_signal_needs_a_living_producer]] was
the suspicion; the code answered it). The probe plants four inquiries with controlled deltas and compares
the stored figure against a recomputation done independently in the file, then pins it to fixed
arithmetic — `(1+2+6)/3 = 3.0` and `3/4 = 0.75` — so a producer that agrees with itself while being wrong
still fails. The second half asserts the honesty rule the producer's own comment states: a seller with
inquiries but **no replies yet** keeps both columns NULL rather than inventing a 0% reply rate that
punishes a brand-new seller. **TEETH VERIFIED** against exactly that bug: replacing the producer with one
that `COALESCE`s the empty state to 0 made both assertions report `NO 0.0` / `NO 0.00`.

#### §10.26d · 🔴 `playwright-smoke` has been silently skipping — the arc's own lesson, in the suite

The clean full suite finished **694 PASS · 7 FAIL · 0 WARN · 0 SKIP** in 87 minutes. Triaging the seven
found one that matters far more than a red:

```
http://127.0.0.1:5000            -> 200, but after 5.86 SECONDS   <- what the validator pinged
http://127.0.0.1:5000/workhive/  -> 200 in 0.01 seconds           <- where the site actually is
```

`validate_playwright_smoke.py` pinged the bare root with a **2-second** timeout, timed out, and reported
*"Flask seeder not running"* — deferring all three of its checks and exiting **0**. The seeder was up the
whole time. So a registered gate could report *nothing ran* as a clean exit, and in a suite summary a skip
is indistinguishable from a pass. Same class as §10.25's two skipped authority partitions, found in the
harness instead of the bank: *a skip reads like coverage.* Fixed to ping `/workhive/` (where the site
lives, and the path the tests drive) with a 6s timeout, so a slow seeder is reported as slow-but-up rather
than absent.

> **CORRECTION, made before this section was believed.** I first wrote that the *suite's* 1200s FAIL was
> this skip. It was not, and the tell was sitting in the file listing: `playwright_smoke_report.json` was
> stamped at **11:13**, which is when **my own standalone run** wrote it — not the suite's. Attributing
> the suite's failure to a report my own command had just overwritten is
> [[feedback_verify_the_instrument_before_the_page]] in miniature. Running it after the ping fix exposed
> the real cause: **the 180s bound does not bound anything.** `subprocess.run(cmd, timeout=RUN_TIMEOUT,
> shell=True)` kills the *shell*, never the `npx` → `node` → worker tree it spawned, and with
> `capture_output=True` the call then blocks waiting to drain pipes those orphaned workers still hold. 13
> minutes in, `tasklist` showed **37 live node/python processes** from a gate that had "timed out" at 180
> seconds. That is where 1200.1s came from — and the orphans are also a plausible source of the
> concurrency contamination blamed on me three separate times this session.
>
> Two further defects in the same function, both already answered by existing project memory:
> `cmd = ["npx", ...]` relies on `npx`, which is **broken in this repo** because the path contains `&`
> ([[reference_npx_ampersand_path_bug]] — the fix is `node node_modules/@playwright/test/cli.js`), working
> only while a `Z:` subst happens to be mapped; and the gate runs the **whole `tests/` tree**, which is a
> ~20-minute full suite, not a smoke test. Fixing the bound is the next unit, not this section's claim.

**The other six, honestly attributed:**

| Gate | Verdict |
|---|---|
| `rls-open-policy` | **MINE, real.** Fixed — see §10.26e |
| `webhook-idempotency` | **MINE, real.** `CREATE POLICY` without a preceding `DROP POLICY IF EXISTS`, plus two tables with RLS enabled in a migration and no GRANT stated. Fixed; **11 PASS 3 WARN 0 FAIL** |
| `Arc R` security | Downstream of `rls_strict` counting my permissive policies. **100% (17/17), no regression** |
| `Arc S` resilience | Downstream of the migration lock drifting when I edited mig 002. **100% on all four lenses** |
| `trigger-function` | **Passes standalone** (drift 0). Failed while I was applying migrations concurrently |
| `Arc I` password recovery | `code=429` twice. **My attribution was wrong twice over — corrected in §10.29.** |

Four real fixes, one instrument fix, two of my own concurrency. **The contamination lesson recurred for
the third time this session** and it is the same one every time: driving work alongside a suite makes its
verdict unusable.

#### §10.26e · My REVOKE fix opened an RLS hole, and then a second gate disagreed with the first

Mig 002 closed the anon-write hole using three `USING (true)` policies. `rls-open-policy` flagged all
three against a forward-only baseline of 2 — correctly; I had closed a GRANT hole by opening an RLS hole
one layer down. I had also written *"the permissiveness that remains is now WRITTEN DOWN instead of
implied,"* which is not the same as not having it, and called owner-scoping `avatar_state` *"not
expressible without a schema change"* and stopped there.

**Mig 20260730000004** makes the schema change: `avatar_state` gains `auth_uid uuid DEFAULT auth.uid()`,
invisible to `voice-handler.js:1133` (which names no owner), and both policies scope to it. That closed a
hole nobody had noticed — under the permissive policy one signed-in user could **silently hijack
another's `session_id` row**. Verified: `owner_upsert_rows=1`, `owner_reads_own=1`,
`stranger_hijack_rows=0`, `stranger_reads_others=0`.

Then the two file-scanning gates disagreed with each other, which is worth recording because both were
right: `rls-open-policy` understands DROP-supersede and read mig 002 + 004 as clean, while
`mine_rls_policies` scans migration TEXT and kept counting mig 002's three CREATEs —
`USING(true) 21 vs baseline 18` **on a database that had none of them.** The resolution was not to teach a
second scanner to forgive dead DDL: mig 002 was creating three policies for the very next migration to
immediately drop, which is churn from my own iteration left in the tree as if it were history. Deleted.
Mig 002 now REVOKEs and turns RLS on (failing CLOSED until 004 defines the policies); 004 owns the column,
the policies, and — stated explicitly rather than inherited from the Supabase template — the GRANTs.
*A migration that fixes an invisible grant should not itself rely on one.*

All three migrations were then proven idempotent across two consecutive re-applications, and the migration
lock was re-locked for mig 002 **behind an assertion that it is untracked with no commit history** — a
re-lock of a shipped migration would make a restore silently diverge from prod, which is the one thing
that lock exists to prevent ([[feedback_a_ratchet_that_turns_both_ways]]).

**Boards:** transition **98.8%** (244/247) · layer 100% · dimension 100% · ufai 48% (documented ceiling) ·
journeys 99.4% over 54 · one-sided 0 · SQL lane **130/130** · ratchet PASS.

**NEXT:** read the smoke suite's verdict now that it actually runs (the first real signal from that gate);
re-run `Arc I` password recovery once Supabase Auth's rate limit has cooled; then the last 3 owed cells —
`TB-S5-edge-push-delivery-roundtrip` (the buildable half is a Playwright assertion that the SW's `push`
handler calls `showNotification`; **no gate asserts that today** — the OS notification tray is the only
genuinely un-probeable part) and `TB-A345`, which stays owed-with-evidence.

---

### §10.27 · The smoke gate: from never-running to 24/27, and four stacked defects in six lines (2026-07-30)

Fixing `validate_playwright_smoke` took four rounds, each exposing the next defect underneath. Recorded
in order because the ORDER is the lesson — every layer had to be peeled before the one below became
visible, and three of the four produced output that looked like a product finding.

| # | Defect | What it made the gate say |
|---|---|---|
| 1 | pinged the bare seeder root (5.86s) with a **2s** timeout | *"Flask seeder not running"* → skipped all 3 checks, **exit 0** |
| 2 | `subprocess.run(timeout=…, shell=True)` killed the shell, not the tree | "timed out at 180s" while **37 workers ran on for 13 min**; suite logged 1200.1s |
| 3 | parsed a **3-hour-old** report, and counted "no result" as FAILED | *"9 of 9 tests FAILed"* with five named titles — the report's own stats said `skipped: 9, unexpected: 0` |
| 4 | `--reporter=json` on the CLI overrides the config and writes to **stdout** | report file never written → parser fell back to the stale one, closing the loop |

Plus a scope defect: a gate named *smoke*, registered `# ~3 min runtime`, was running the **entire
`tests/` tree — 138 spec files.** Its bound could never fit its scope. Now scoped to the platform's own
`WORKER_CRITICAL_PAGES` list (borrowed from `validate_sw_offline`, so two gates agree on what "critical"
means) with the bound raised to 300s against a *measured* cost (`logbook.spec.ts` alone = 31s).

Also fixed: **L3 could report "All UI smoke tests passed" over ZERO tests.** An empty denominator is not
a pass — the same false green this arc removed from the bank an hour earlier, sitting in the harness.

#### §10.27a · What the working gate then found: 5 → 3 → 1, and not one was a product defect

**Round 1 — 5 failures.** Two were `TypeError: Failed to fetch` from `supabase.auth.getUser()` through our
own `_timeoutFetch` wrapper, on pages that had been hammered by this session's probe volume; one named a
**429** outright. Re-running dropped it to 3 — so those two were transient auth saturation, and reporting
them as page defects would have been the fourth instrument-blame of the session. They were not reported.

**Round 2 — 3 stable failures**, including the regression test for the **2026-05-12 silent-fail bug**.
Every one claimed the page had silently failed to save. The tell was that the "last seen toast" was
**byte-identical across three different pages**: *"Live · refreshed on load · Based on your logbook, asset
nodes & inventory"*. A per-action toast varies; shared status chrome does not.

The cause is a correct accessibility fix colliding with a test assumption. `whSourceChip` (utils.js)
renders the provenance/freshness chip as:

```html
<p class="wh-source-chip" role="status" aria-live="polite">Live &middot; Based on your … &middot; updated …</p>
```

`role="status"` was added deliberately so every page satisfies the G1 *"visibility of system status"*
rubric. But `readToast` located `'#toast, .wh-toast, [role="status"]'` and took `.first()` — **DOM order,
not recency** — so it locked onto the persistent chip and could never see a toast however long it polled.
The 5-second poll was futile by construction. Excluding `.wh-source-chip` cleared all three.

> **The page was right; the selector was wrong.** A central a11y improvement silently broke every spec
> that read a toast, and it stayed invisible because the gate that would have caught it never ran.

**Round 3 — 1 failure**, `hive.html … no page errors`, which had PASSED in round 2 on unchanged code.
That is the arc's own definition of a **flake**: the same intermittent `getUser()` → `_timeoutFetch`
abort, surfacing as a `console.error` that a "no page errors" assertion treats as a defect. Recorded as
such rather than fixed by widening — the honest open question is whether a transient auth timeout the
page RECOVERS from should log `console.error` at all.

**Final: 27 tests · 24 passed · 1 failed (flake) · 2 skipped**, from a report written one second before
the run ended, with **0 orphaned processes**.

**Boards unchanged and green:** transition **99.6%** (246/247) · layer 100% · dimension 100% · ufai 48%
(documented ceiling) · journeys 99.4% · SQL lane **130/130** · ratchet PASS · substrate 716 fresh.

**NEXT:** re-run `Arc I` password recovery once Supabase Auth's rate limit has cooled (its two failures
were `code=429`, not product); decide whether `_timeoutFetch`'s abort should `console.error` on a path the
page retries (that decides the last smoke flake); then the runtime tier of `TB-S5` — dispatch a push event
to a registered worker and assert `showNotification` fired, which is the one rung above the new
`push-handler-contract` gate and below the OS tray, the only genuinely unprobeable part.

---

### §10.28 · 🔴 "Enable job alerts" hung forever — found by building TB-S5's runtime tier (2026-07-30)

The `NEXT:` line said *dispatch a push event to a registered worker and assert `showNotification` fired.*
Building it found a live product defect before a single push was delivered.

**`svcEnablePush()` in `marketplace-seller.html` awaited a promise that never settles.**

```js
const reg = await navigator.serviceWorker.ready;   // <- hangs forever
```

`navigator.serviceWorker.ready` resolves **only when an active registration exists for the page's scope**.
A repo-wide grep finds `serviceWorker.register` on exactly **one page in the entire app** —
`report-sender.html` — and not on this one, not in `utils.js`, not in any shared include. Measured live:

```
registrations = 0 · controller = false · scopes = [] · ready NEVER SETTLED
```

So the real sequence was: a provider taps **"Enable job alerts"** → grants the notification permission →
and then nothing. No subscription stored, no toast, no error, no console line. Forever.

> The function's `catch` is thorough — it handles permission refusal, VAPID mismatch, unsupported
> browsers, and logs so failures are greppable. But **`ready` does not reject; it simply never resolves.**
> The one failure that fires in practice was the only one the catch could not see.

**Fixed** by registering the worker on that path (`getRegistration` → `register('/workhive/sw.js')` →
`ready`) and **racing the wait against a timer**, so a worker that will not activate says so instead of
leaving a dead button. Registration stays LAZY by design — no background worker until the provider
actually asks for alerts.

#### §10.28a · Three settings between "un-probeable ceiling" and a passing test

The spec fails to measure anything without all three, and each looked like a product failure first:

| Setting | Without it |
|---|---|
| `serviceWorkers: 'allow'` | Playwright **blocks** registration by default — its bundle replaces `navigator.serviceWorker.register` with a warning stub, so every SW assertion silently measures nothing |
| `permissions: ['notifications']` | `Notification.permission` is `denied`; `showNotification` rejects |
| `channel: 'chromium'` | **the deciding one** — the BUNDLED headless Chromium has no notification platform bridge, so the permission cannot be granted at all and `getNotifications()` is always empty… which is the exact symptom of a handler that renders nothing |

Probed both ways rather than assumed: default headless → `perm 'denied', count 0`; Chrome's new headless
→ `perm 'granted', count 1`. **I was one step from recording this as an un-probeable ceiling. It was a
one-line config** ([[feedback_build_structure_to_make_it_liveable]] — the last-resort bucket is claimed
only after the build attempt genuinely fails, and mine had not).

#### §10.28b · TB-S5 now stands on three executed tiers

| Tier | Proof |
|---|---|
| **send** | `notify-push` is VAPID-signed, proven E2E against the real FCM service |
| **static** | `push-handler-contract` — 7 invariants on sw.js, teeth proven against 5 broken workers |
| **runtime** | `push-runtime-delivery` — a real push through CDP `ServiceWorker.deliverPushMessage` (the same entry point FCM uses, so the listener runs its actual code path) renders a notification whose **title and body** are read back off `registration.getNotifications()` |

The render oracle has teeth by construction: every misconfiguration during development produced
`getNotifications() == []` and a RED test — the identical signal a handler that stopped calling
`showNotification` would give.

**Residual gap, named and unchanged:** only the **OS notification tray**. *The handler rendered it* is now
proven; *the human saw it* is not, and no harness can read the tray. That is the whole of what remains.

#### §10.28c · A larger finding this exposed, NOT unilaterally acted on

`validate_sw_offline` asserts that worker-critical pages appear in sw.js's `SHELL_FILES` so they work
offline — a premise that only means anything **if the service worker is registered on load**. It is not,
on any app page. So the offline PWA story may be as dormant as push was. Turning on platform-wide
registration activates shell caching everywhere and has real blast radius (the `CACHE_NAME` bump comments
in sw.js document how carefully stale-shell invalidation is managed), so this is recorded for Ian rather
than switched on mid-arc.

**Boards:** transition **99.6%** (246/247; the 1 owed is `TB-A345`, owed-with-evidence) · layer 100% ·
dimension 100% · ufai 48% · journeys 99.4% · SQL lane 130/130 · `--fast` suite **0 FAIL** with a new clean
baseline saved · ratchet PASS.

---

### §10.29 · Arc I closed 9/9 — and my attribution was wrong TWICE before it was right (2026-07-30)

The last of the seven suite failures. `validate_password_recovery` returned `code=429` on both live checks,
and I called it *"Supabase Auth rate-limiting my own probe traffic"*. That was wrong, and so was my second
guess. The sequence is worth recording because each wrong answer was plausible and each was disproved by
one measurement:

| Guess | Disproved by |
|---|---|
| GoTrue's own auth rate limits | the container's env caps are 150/30 — nowhere near hit |
| in-memory counters, so restart clears them | **restarted the auth container; still 429** |
| my probe volume in the naive sense | the counters are a persistent TABLE, and the actual blocker was a control nobody had exceeded by accident |

The truth: `supervisor-reset-password` carries a **deliberate product control** — *"5/hour, 20/day per
actor, plus a CGNAT-aware per-IP ceiling, because a compromised supervisor mass-resetting members is
exactly the abuse this contains."* Its counters live in `ai_user_rate_limits`, a persistent table, which is
why restarting anything changed nothing.

Two buckets were spent, and each had to be measured separately:

```
ip:172.18.0.1                          hour=2  day=24     <- against a 20/day ceiling
bcb5a6e3… (the supervisor it signs in as)  hour=23 day=28  <- against a 5/hour cap
```

**Inside Docker every edge-function call arrives from the same gateway address**, so the per-IP ceiling —
correct and valuable in production, where it catches one IP rotating spoofed uids — collapses onto the test
harness locally and accumulates every invocation on the machine. Clearing only the IP rows still returned
429, because the limiter is per-identity *and* per-IP: the supervisor had also spent its own hourly budget
on this session's re-runs.

**Fix in the GATE, not the control:** it now clears its own two buckets before the live probe — docker-only
IP rows (`ip:172.%`) and the actor resolved from `auth.users` by the same email it authenticates with, so it
can never drift onto a different account. The rate limit itself is untouched; a gate must not be red because
it ran too often, and the product control must not be weakened to make a test pass.

**Result: 9/9, GREEN, three consecutive runs.** `code=200` with a temp password that actually logs in,
`403` for supervisor→supervisor, `403` for worker→anyone. The product had been correct the entire time.

> Three guesses, three measurements, and only the third guess survived contact. Writing down which
> measurement killed which guess is what stops the first plausible story from becoming the recorded cause —
> and this is the fourth time this session an instrument, not the product, was the culprit.

**ALL SEVEN suite failures are now closed:** 4 real fixes of my own making (`rls-open-policy`,
`webhook-idempotency`, and `Arc R`/`Arc S` downstream of them), 2 instrument defects
(`playwright-smoke`'s four stacked bugs, `Arc I`'s self-exhausted budget), 1 transient
(`trigger-function`, green standalone). **Zero were product defects the suite had found.**

---

### §10.30 · The smoke gate closed GREEN — and the last "silent-fail regression" was a draft refilling the form (2026-07-30)

```
27 tests · 25 passed · 0 failed · 2 skipped   —   exit 0, TWICE consecutively
```

The gate that had **never run once** is green and stable. The remaining failures resolved into two
different things, and only one needed a fix.

#### The one that needed a fix: a test asserting against a form state it did not control

`logbook.spec.ts`'s regression test for the **2026-05-12 silent-fail bug** deliberately leaves the problem
field empty and asserts the submit is blocked. It failed reporting:

```
toast didn't match expected error pattern: Draft restored. Continue where you left off.
[browser log] [capture-validate] logbook_add_entry_v1 passed
```

The page's own instrumentation said the validation **passed** — and it was right. `restoreDraft()` refills
`f-problem` from a saved draft during page load, so a draft left by an earlier test meant the field the
spec believed was empty had content, and a valid submit correctly produced no error toast.

> **The test was asserting against a form state it did not control.** It only fails when a draft happens to
> exist, which is exactly why it read as a flake rather than a bug. Draft-restore is a real, valuable
> feature — the fix belongs in the spec's isolation, never in the page.

`clearFormDrafts()` (new shared helper) removes `*_draft_*` keys in an **init script**, because the draft is
restored *during* load and clearing storage afterwards is too late. Wired into a `beforeEach` in both
`logbook.spec.ts` and `journey-logbook.spec.ts` — the sibling had the identical exposure, calling
`assertSubmitBlocked` on a deliberately empty field.

**Two masks over one flaw.** Before the draft, the same assertion had locked onto the persistent
`.wh-source-chip` status region (§10.27a). Both were possible because `assertSubmitBlocked` judged on a
**single `readToast()` snapshot** while its sibling `assertSubmitSucceeded` already polled — with a comment
explaining precisely why ("transient toasts … can briefly mask" the one you want). It now polls and
collects **every** toast seen, which also makes the leak check *stronger* than before: the old code asserted
"the one toast I saw is not a success toast"; it now asserts no success toast appeared **at all** during the
window, which is the actual regression being locked.

#### The ones that needed no fix: load-dependent, and proven so by re-running

`hive.html` and `pm-scheduler.html` page-error failures were both the same `_timeoutFetch` abort on
`supabase.auth.getUser()`, and `asset-hub`'s telemetry tile was a `waitForFunction` timeout. All three
cleared once the auth service was warm and unloaded — no code change. `_timeoutFetch`'s own budget is 45s,
so these were genuine load artifacts of a session that had been hammering auth, not a product timeout to
widen. **Not reported as defects.**

#### The tally, honestly

**All seven suite failures closed**, and the composition is the finding:

| Cause | Count |
|---|---|
| Real defects **of my own making**, caught by gates within minutes | 4 (`rls-open-policy`, `webhook-idempotency`, and `Arc R`/`Arc S` downstream of them) |
| **Instrument** defects | 2 (`playwright-smoke`'s four stacked bugs + the toast/draft pair; `Arc I`'s self-exhausted rate budget) |
| Transient / contamination | 1 (`trigger-function`, green standalone) |
| **Product defects the suite had found** | **0** |

Every product defect this session found came from *building new instruments* — the anon partition, the
admin partition, the push runtime tier — not from the existing suite going red.

**Final state:** transition **99.6%** (246/247) · layer 100% · dimension 100% · ufai 48% (ceiling) ·
journeys 99.4% · overall roadmap **99.6%** · SQL lane 130/130 · smoke 25/25 green ×2 · `--fast` 0 FAIL ·
substrate 716 fresh · ratchet PASS.

#### §10.30a · CORRECTION to the section above — two greens was not "closed", and two more causes followed

§10.30 declared the smoke gate closed on **two consecutive green runs**. That was premature: the next two
runs failed, each with a **different** cause, and neither was the one I had just fixed. Recorded because the
over-claim is the mistake, not the flakes.

| Run | Result | Cause |
|---|---|---|
| 1–2 | green ×2 | (what §10.30 was written on) |
| 3 | FAIL | `parts-tracker.html` — `getUser()` → `_timeoutFetch` transport abort |
| 4 | FAIL | `pm_write_isolation` on pm-scheduler — a **partial page source** |

**Cause 3 — the transport abort — was measured, not guessed.** Ruled out: parallel workers (`workers: 1` is
already the config) and the wrapper's own budget (45s, far too long to be a timeout). Across six runs it
appeared in roughly half, rotating between `hive.html`, `pm-scheduler.html` and `parts-tracker.html`, and in
one **serialized** run the error was logged while every test passed — proving whether it reddens a gate is
pure timing. It looks like a keep-alive connection-reuse race against the local auth service and predates
this session. `_smoke-template.ts`'s existing benign-error filter (which already excludes asset 404s and
`net::ERR_`) now also tolerates it — matched narrowly on OUR wrapper's own frame (`_timeoutFetch`), so a
`Failed to fetch` thrown by a page's own code is still a hard failure — and every tolerated blip is
`console.warn`ed so it cannot become invisible.

**Cause 4 was the same silent-skip class one more time, in a shared helper.** `pageSrcWithExternals()` reads
the page plus its same-origin scripts and had `if (r.ok) …` with `catch (_) { /* ignore */ }` — so a blipped
script was **silently dropped and the returned source was silently partial.** Every caller greps that string
for a symbol, so a dropped script made the assertion announce a product defect: *"PM write payloads must
carry hive_id"* failed on a page that was perfectly correct — the script containing `hive_id` simply had not
been read. It now retries once and then **throws by URL**, saying explicitly that the harness failed to read
the page rather than answering a question it no longer has the evidence for.

**Final, stable: `exit 0` twice with IDENTICAL composition — 27 tests · 24 passed · 0 failed · 3 skipped.**
Identical composition across runs is the real stability signal; two green runs with *different* tallies were
not. All three skips are explicit in-spec `test.skip()` guards with stated data-conditional reasons
(`pm_templates not queryable`; two shift-brain "live window in CI" guards) — pre-existing and principled.

> **The lesson I keep re-learning, now four times in one session: a silently dropped read produces a
> confident wrong answer.** A skipped partition, a stale report, a `getNotifications()` that could never
> populate, and now a partial source — every one of them reported a product defect that did not exist.
> `catch (_) { /* ignore */ }` is where that begins.

---

## §11 · TEST BANK II — proving the bank has TEETH, and letting the score admit new breadth (2026-07-30)

> Ian: *"do what's appropriate and needed for my platform. then let us check internally and external
> sources if we could improve and add more in our marketplace testbank."*

### §11.0 · Why a successor arc, from the bank's own data

The bank finished at transition 99.6%, SQL lane 130/130, layer 100%, dimension 100%. Those numbers say the
cells RAN and AGREED with the guards. Neither says anyone would have NOTICED had a guard behaved
differently — and this session's own triage is the evidence that the difference is real: of seven suite
failures, **four were defects I had just introduced, two were instruments, one was contamination, and ZERO
were product defects the suite had found.** Every genuine defect came from *building a new instrument*.

So the first move was to measure the bank against itself, which found six gaps:

| Measured gap | Evidence |
|---|---|
| two axes were decoration | `viewport [390,1280]` and `lang [en,fil]` declared, used on **0 of 247** cells |
| state partitions unset | `state` `None` on **212/247** — the inducers §7b required were **never built** |
| oracle mix lopsided | **194 refusal**, 35 db-truth, 10 rubric, 7 continuity, **eval = 1** |
| layer 100% was short-denominator | `layer_pct` counts any layer with **≥1** cell. S4-db 235 · **S2-pwa 1, S7-ai 1, S9-knowledge 1** · S5-edge 5 against **26 client-called** edge functions |
| sneak-paths were a human's list | 4 hand-named kinds, not generated sequences |
| nothing measured teeth | no mutation/metamorphic/property infrastructure existed |

**Method held (Engine A drives Engine B).** These are frictions measured in our own data, not standards
harvested cold — the correction that killed two of three cold harvests in a prior session
([[feedback_engine_a_drives_engine_b_journey_seeds_harvest]]). Four external sources were then read against
those specific gaps and **written to `substrate/external/`** (166 → 170 chunks), closing a gap the original
plan opened and never closed: it said to harvest its six sources, and the bag still held **zero** chunks on
test-bank design.

| Technique | Gap it answers | The finding that mattered |
|---|---|---|
| mutation testing | nothing measured teeth | *100% line coverage can score **below 50%*** |
| metamorphic testing | `eval` = 1 | an MR is *"a necessary property … that MUST involve MULTIPLE EXECUTIONS"* — and the canonical published example is our exact shape: a filtered search *"should return a subset of the previous results"* |
| stateful property-based testing | sneak-paths hand-named | preconditions reject illegal sequences BEFORE they reach the system — precisely the bug my out-of-order probe had |
| consumer-driven contracts | S5-edge 5 of 26 | the contract is generated from **running consumer code**, so it cannot drift from what is implemented |

**Locked with Ian:** mutation scoped to the four SQL guards · retire the dead axes naming their owners ·
**both directions, with depth GATING breadth.**

### §11.1 · P0 — the two decoration axes, retired and PROVEN irrelevant

`viewport` and `lang` are gone from the axes, each recorded with the instrument that actually measures it:
the live UFAI deep walk (390/1280, real tap-target and overflow numbers, worse-per-dimension) and
`validate_i18n`. Same disposition already applied to U1/U2/U5/U6/U7 — the bank NAMES what another instrument
proves rather than re-measuring it worse.

Two disciplines, because retiring an axis is the kind of change that can quietly flatter a board:
- the script **asserts 0 usages** before removing either axis, so this is not done on assumption;
- the full board was captured before and after and **`diff` was EMPTY**. Had any % moved, the axis was
  load-bearing and the retirement would have been wrong.

### §11.2 · P1 — a mutation SCORE on the four guards

`tools/validate_guard_mutation_score.py`, registered `guard-mutation-score`. Nine operators, each a way one
of THESE guards has actually rotted: negate the party gate, drop it, force `v_is_party` false, force
`v_is_client`/`v_is_matched_provider` true, restore the unconditional admin bypass, turn a `raise exception`
into `return new` (**fail OPEN**), widen an authorised from-state list. One fault per mutant — two can mask
each other and make a mutant unkillable for the wrong reason.

**A mutant can never outlive its test.** The mutated `CREATE OR REPLACE` is injected INSIDE each cell's own
`begin … rollback`, so the mutation and the cell judging it die together. DDL is transactional, so a crash
cannot leave a weakened guard installed, and no migration is ever written. The run asserts **0 mutated
guards persist**. Committing a mutant and restoring afterwards would leave a window where the platform's own
security guard is deliberately broken — not a risk worth a metric.

**The first run caught MY OWN instrument, not the bank.** It reported `guard_service_topup_status` at
**0% on 1 cell** — a headline that would have read as "the money-minting guard is unguarded". It was wrong:
authored probes carry no `transition` field, so my cell selection could not see them, while
`TB-I2-admin-bypass-only-for-non-parties` sat in the bank asserting exactly the top-up self-deal those
mutants create and reading the credit ledger back. Probes now declare **`covers_tables` explicitly** —
auditable, and it cannot drift silently when a probe is edited — and that guard scores 100%.

> Under-counting the bank is the same class of error as over-claiming it: both report a number whose
> evidence is somewhere the reader cannot see.

**The self-test failed first, correctly, and taught me the harness.** Its "weak set" was `full[:1]`, which
after the ordering change is the *strongest* single cell (an authored probe asserting a whole scenario), so
it killed 9 of 9 and the test reported no sensitivity. Rebuilt around a single **derived** cell:

```
full set        (107 cells) killed 9
derived only    (103 cells) killed 9    <- the derived grid carries its own weight here
one derived cell(  1 cell ) killed 0    <- so the score measures ASSERTIONS, not scaffolding
```

It also now reports how many mutants die *only* to authored probes — the punch list for a thin derived grid.

**Result: 27 viable mutants, 27 killed, 100%, forward-only baselined.** Read honestly, that is not "the bank
is perfect": it is "the bank objects to every fault these nine operators can express." More operators is how
that number earns more meaning, and a survivor would be a named punch-list item rather than a worry.

### §11.3 · P2 — metamorphic relations, so the oracle mix stops being 78% refusal

`TB-MR-metamorphic-relations` (new `metamorphic` oracle type), 10 assertions, all green:

| MR | Relation | Why it needed no expected value |
|---|---|---|
| MR1 | a filtered listing set ⊆ the unfiltered one, for category and price independently | the "right" result set depends on live data nobody froze |
| MR2 | a member's visible requests ⊂ a supervisor's on the same hive | a POSITIVE statement on an authority axis that is otherwise 100% refusal |
| MR3 | verifying two top-ups in either order reaches the same balance | commutativity on the money path; no balance is written down anywhere in the file |

**Every MR carries its own non-vacuity check**, because these are the easiest assertions in the bank to
satisfy trivially — an empty filter result is a subset of anything, a system that shows nobody anything is
monotonic, and 0 = 0 is order-independent. So MR1 asserts the filter kept AND removed rows; MR2 asserts the
supervisor sees something AND that the subset is **STRICT**; MR3 asserts both orderings actually minted.

That strictness check exists because my first MR2 fixture was weak: both requests carried a `hive_id`, which
made the two visible sets **identical** — subset held by equality while proving no permission boundary
existed at all. Rebuilt so one request is visible to the supervisor only.

Two mechanical lessons worth keeping: `ROLLBACK TO SAVEPOINT` is **not legal inside plpgsql**, so MR3 uses a
nested `BEGIN … EXCEPTION` block (DB effects roll back, plpgsql VARIABLES keep their values) and reports any
*unexpected* error rather than swallowing it into a NULL that reads as a failed relation. And `set local
request.jwt.claims` inside a DO block is **transaction-scoped, not block-scoped** — `reset role` alone left
the member's identity in place and the top-up guard correctly refused MR3's own fixture, a probe accusing the
product of a bug in the probe's setup.

**Teeth:** inverting MR1's `<@` to `@>` makes it report `NO`.

### §11.4 · P4 — the boards now disclose their own rules

```
layer      : 100.0%  architecture, on a >=1-CELL rule — untested: none
    cells/layer: S1 23 · S2 1 · S3 6 · S4 236 · S5 5 · S6 3 · S7 1 · S8 12 · S9 1
    thin (<=2 cells, counted as covered by the rule): S2-pwa=1, S7-ai=1, S9-knowledge=1
oracles    : refusal 194 · db-truth 35 · rubric 9 · continuity 7 · eval 1 · metamorphic 1
mutation   : 100.0%  of 27 seeded guard faults the bank NOTICES
```

> ⚠️ **That mutation line is left verbatim because it is a record of what the tool printed, and it was
> false.** The injection was swallowing each cell's next statement, so no mutant ever ran; the honest first
> measurement was **50.0%**. See §11.11 — the board machinery below is unaffected, only the number is.

The layer number was always true and the impression it gave was false. A % whose rule is invisible will be
misread, so the rule is printed beside it and the thin layers are named — two lines that make a
short-denominator 100% impossible to mistake for architecture coverage
([[feedback_short_denominator_is_a_false_100]]). The oracle mix is a SHAPE and is deliberately never reduced
to one figure: a bank that overwhelmingly proves "this must not happen" can be green on a system that does
nothing at all, which is the asymmetry this whole arc exists to correct.

**State:** transition 99.6% (247/248) · SQL lane **131/131** · mutation ~~**100%**~~ **⚠️ fabricated by a
broken injection — the honest figure was 50.0%, see §11.11** · layer 100% (rule
disclosed) · dimension 100% · ufai 48% · roadmap 99.6% · ratchet PASS · canonical_status **all 82 green**.

**NEXT (P3, admitted only by the score):** the admission rule is that a new cell counts once it demonstrably
kills a mutant or fails when its invariant is inverted. Highest value first — **CDC on the 26 client-called
edge functions** (5 covered; the bug class is already proven, `urgency='emergency'` written against a CHECK
that forbade it), then the **state inducers** §7b never got, then the three **one-cell layers** now named on
the board. Each user-facing addition preceded by a live journey establishing the friction, per the method
constraint above.

### §11.5 · P3 first move — the CDC candidate is a KILL, and the premise was wrong before the code was

The plan's breadth phase led with *"consumer-driven contracts on the client-called edge functions — 26
candidates, 5 covered."* Checking the premise before building found **both halves of that sentence wrong**,
which is the anti-duplication rule earning its place rather than a wasted detour.

**Wrong scope.** 26 is the PLATFORM's client-called set. This is the MARKETPLACE bank, and the marketplace
pages call exactly **two** edge functions: `ai-gateway` and `marketplace-listing-assist`.
`marketplace-seller.html`, `marketplace-admin.html` and the seller profile call **none**.

**Wrong gap.** All three questions CDC would ask are already gated, by three different instruments:

| CDC question | Already owned by |
|---|---|
| does the provider honour its response shape? (CORS/OPTIONS, `{error:string}`, required fields 400-not-500, registration) | `validate_edge_contracts.py` — provider-side, static |
| do the client's values agree with the provider's VOCABULARY? | `service-triage-eval` — reads the catalog + urgency/mode vocabularies from the DATABASE every run, so a new category is graded against without touching the gate |
| does the route the client calls exist and reach the right agent? | `gateway-coverage` + `edge-fn-invoke-targets` |

A fourth gate, `validate_marketplace.py`, also references the function. Building a CDC harness here would
have produced a slower fourth copy of coverage that already bites — the outcome the method constraint
predicts, and the reason two of three cold harvests in a prior session were KILLS.

**And a suspected finding that did NOT survive contact.** `grep -rn service_triage --include=*.html` returns
NOTHING, so `marketplace-listing-assist`'s `mode: 'service_triage'` branch looked like dead provider code
reachable from no surface. It is not: `ai-gateway/index.ts:1384` sets `forwardExtras.mode = "service_triage"`
and forwards to it. The page calls the gateway (`agent: 'service-triage'`) and the gateway calls the
function — the "ONE front door / coach-fold" pattern the page's own comment describes. The chain is:

```
marketplace.html  --{agent:'service-triage', message, hive_id}-->  ai-gateway
ai-gateway        --{mode:'service_triage', message, ...}------->  marketplace-listing-assist
                  <--{category, urgency, mode}-------------------
client reads      data.data.route_result.triage.{urgency, category}
```

Reported as measured, not as reasoned: a client-side grep is not evidence about a server-to-server hop, and
"no HTML calls it" would have been a confident wrong answer about dead code
([[feedback_check_the_premise_before_building_the_pattern]]).

**What P3 therefore still genuinely owes**, unchanged by this kill:
- the **state inducers** §7b required and never got (`filtered0` / `error` / `degraded` / `empty` / `edge`),
  which is why `state` is `None` on 212 cells — and only for cells whose surface truly renders per-state;
- the **three one-cell layers** the board now names out loud (S2-pwa, S7-ai, S9-knowledge), each preceded by
  a live journey establishing the friction;
- the admission rule stands: a new cell counts once it kills a mutant, or fails when its invariant is
  inverted.

### §11.6 · P3 second move — the state axis is INDUCED, and my "silent truncation" finding did not survive contact

`TB-STATE-inducers-empty-filtered0-edge`, 9 assertions, all green. The original plan named the cost of not
doing this in its own words — *"a state axis with no induction mechanism is decoration"* — and `state` was
`None` on 212 of 247 cells because §7b's inducers were never built. Two axes were retired today for exactly
that reason; this is the other half of the answer: induce the states that CAN be induced rather than remove
them.

**Three states induced at SQL altitude**, and `error`/`degraded` deliberately left to the journey lane — a
route abort and an offline write queue are browser facts, and claiming them here would break the
cheapest-honest-altitude rule in the expensive direction.

**The assertion worth having** is one our own history earned. `read-battery` once reported SIX named page
failures, all *"DB empty → empty-state (no error)"*, and not one was real: the hive it pinned had been
reseeded away ([[feedback_a_dead_fixture_invents_page_defects]]). So the probe proves both halves of why
that happened:

```
state_empty_rows=0            a real tenant that owns nothing
state_filtered0_rows=0        real rows, and a filter none of them match
state_ghost_tenant_rows=0     a hive id that does not exist at all
three_states_indistinguishable_by_count=yes      <- a count is never a diagnosis
tenant_exists_separates_empty_from_ghost=yes     <- and this is the check that DOES separate them
```

Those are three completely different truths — *"nothing yet"*, *"nothing matches"*, *"you are asking about
nobody"* — and a surface rendering the same thing for all three will one day tell a real user their data is
gone.

#### The finding I did not report, for the third time today

The edge assertion first demanded a 200-character title survive. It came back **120**, which looked like
silent truncation of user content: `title` is unbounded `text`, `marketplace-listing-assist` slices titles at
200 (`.slice(0, 200)`), and `cap_marketplace_listings_text` does `left(NEW.title, 120)` — an 80-character
loss with no error, no toast, no log. `condition` shows the same shape (sliced at 60, capped at 40).

**Unreachable.** `#post-title` in marketplace.html carries `maxlength="120"`, matching the DB cap exactly,
and the AI assist writes only `category` and `description` — never the title. Both ENDS of the chain agree
at 120; only the middle layer is slack. That is defence-in-depth that happens to be loose, not a defect.

So the assertion was corrected rather than the product: it now locks the **agreement** at 120, which reddens
if `maxlength` is raised without the trigger or the trigger is lowered without the form. Demanding "200
survives" would have asked the product to abandon a deliberate cap
([[feedback_gates_lock_refusal_not_permission]] — lock the behaviour that EXISTS).

> Three suspected findings this session, three that dissolved on inspection: the `service_triage` "dead
> branch" (reached server-to-server), the top-up guard "at 0%" (my cell selection), and this truncation
> (capped at both ends). **The habit that caught all three is the same one: before reporting, check whether
> another layer already contradicts it.**

**State:** transition 99.6% (248/249) · SQL lane **132/132** · mutation **100%** (27/27, 0 persist) ·
oracles refusal 194 · db-truth 36 · rubric 9 · continuity 7 · eval 1 · metamorphic 1 · ratchet PASS.

**NEXT:** the three one-cell layers the board now names out loud — S2-pwa, S7-ai, S9-knowledge — each
preceded by a live journey establishing the friction, and each admitted only by the standing rule: a new
cell counts once it kills a mutant or fails when its invariant is inverted.

### §11.7 · P3 third move — the three "thin" layers needed OWNERS NAMED, not three new cells

Naming the thin layers in §11.4 removed one misreading and introduced its opposite. A reader seeing
`S2-pwa=1` would reasonably conclude the PWA layer is barely tested. It is not:

| Layer | bank cells | owned platform-wide by |
|---|---|---|
| S2-pwa | 1 | **8** gates — `pwa`, `sw-offline`, `sw-shell-membership`, `offline-resilience`, `offline-write-guard`, `cache-invalidation`, `push-handler-contract`, `push-runtime-delivery` |
| S7-ai | 1 | **9** gates — `service-triage-eval`, `ai-alignment`, `ai-attribution`, `ai-chain-mirror`, `ai-context`, `agentic-rag-loop`, … |
| S9-knowledge | 1 | **5** gates — `knowledge-freshness`, `substrate-freshness`, `substrate-manifest`, `data-governance-kb`, `ai-companion-knowledge-graph` |

Out of **550 registered gates**. So the honest fix was not three new cells — it was to make the board say
*both* facts, and it now does:

```
thin (<=2 BANK cells — the rule counts them covered)
  S2-pwa         1 bank cell · owned platform-wide by 8 gates: pwa, sw-offline, sw-shell-membership, …
  S7-ai          1 bank cell · owned platform-wide by 9 gates: service-triage-eval, ai-alignment, …
  S9-knowledge   1 bank cell · owned platform-wide by 5 gates: knowledge-freshness, substrate-freshness, …
```

A layer with NO declared owner still prints in yellow as *"genuinely uncovered"*, so the mechanism cannot be
used to paper over a real hole. **A thin layer is a statement about the BANK's shape, never a claim that
nothing tests it** — the bank's job is the marketplace's transitions and journeys, and a whole-platform
concern like offline shell caching or an AI cost ceiling is owned by its own instrument.

**Two disciplines kept this honest.** The owner lists are **curated, not regex-counted**: a first crude match
reported *"S7-ai: 85 gates"*, inflated by substring false positives (`storage-keys` matches `rag` inside
"sto**rag**e"). And the registration script **asserts every named owner exists in the live registry** —
a stale owner id would be a claim of coverage that does not exist, which is precisely the failure this whole
arc has been removing.

> **The pattern across all three P3 moves is the same, and it is the arc's real lesson.** CDC: already owned,
> killed. Thin layers: already owned, named. Only the state inducers were genuinely missing, and building
> them turned up a fourth suspected defect that dissolved on inspection. **Three of four "gaps" were the
> map, not the territory** — which is why the anti-duplication check runs BEFORE the build, not after.

**Final state:** transition **99.6%** (248/249) · SQL lane **132/132** · mutation ~~**100%** (27/27)~~
**⚠️ fabricated, see §11.11** (0 persist
· layer 100% with its rule and owners disclosed · dimension 100% · oracles refusal 194 · db-truth 36 ·
rubric 9 · continuity 7 · eval 1 · metamorphic 1 · roadmap 99.6% · ratchet PASS · canonical_status all 82
green · substrate 720 fresh.

**NEXT:** the one owed cell is `TB-A345` (A3 = the D9 knobs, yours to set; A4 hunted and found absent; A5
demonstrated by the denominator growing itself). Beyond that the honest queue is *more mutation operators* —
the 100% means the bank objects to every fault nine operators can express, and each new operator is a real
increase in what that number is worth.

### §11.8 · The operators went 9 → 15, and the score held: 36/36 — ⚠️ SUPERSEDED, see §11.11

A mutation score is worth exactly what its operators can express, and §11.7 closed by saying so. So six more
were added — each a rot mode these guards specifically could suffer, not a generic character edit:

| Operator | The fault it expresses |
|---|---|
| `birth_status_unchecked` | a new request may be BORN in any state, including a privileged/terminal one |
| `attribution_pin_removed` | a caller may file a request AS SOMEONE ELSE |
| `born_matched_allowed` | a request may be born already MATCHED, bypassing the accept RPC |
| `reassignment_allowed` | matching may be reassigned by a direct write instead of the RPC |
| `ownership_transfer_allowed` | a request's OWNERSHIP may be moved to another account |
| `guc_bypass_always_on` | the announced system-write bypass is permanently ON, so every caller gets the backend path |

**27 → 36 viable mutants, and all 36 still killed.** `guard_service_request_status` alone went 9 → 15.

That is a different claim from the one at 27, and a stronger one: the bank now demonstrably objects to
losing the attribution pin, to a request born matched, to ownership transfer, and to the GUC bypass being
stuck open — none of which the first nine operators could reach. The number did not move; **what it means
did.**

**Remaining honest queue:** more operators still. 36 is not a ceiling, it is the current vocabulary — and a
survivor, when one eventually appears, is a named punch-list item rather than a worry.

### §11.9 · The state axis closed across BOTH altitudes — and a fifth finding that dissolved

`error` and `degraded` were deliberately excluded from the SQL tier as browser facts. They are now induced
in a real browser by `marketplace-state-inducers` (new gate, `TB-STATE-journey-error-and-degraded`), which
closes the state axis at the cheapest honest altitude for each state rather than one altitude for all.

**`error` is the one that matters.** A failed read and an empty result are identical to a row count, and from
the user's side the ambiguity is worse than from ours: a seller whose query merely failed must not be told
*"be the first to sell"*, because that reads as **your listings are gone**. `marketplace.html` already gets
this right — `_loadError` is documented at line 1064 as *"P7: a FAILED listings fetch must render an error
state, not the first-run 'be the first to sell' CTA"* — but it had **no browser test**, because a static grep
cannot prove which branch renders when the network actually fails. The gate locks the fix and asserts the CTA
is **absent** as well as the error being present.

**The product was right and my test was wrong, twice, before it passed:**

| What I did | What it actually measured |
|---|---|
| slept 2.5s then asserted | the page's **retry budget** — aborts climb 12 → 20 → 32 and the error lands at **~8s**, so a fixed sleep failed on correct behaviour. Fixed by POLLING (the same lesson as judging a toast on one snapshot) |
| matched `body.innerText` | other sections' markup — both the error copy **and** the CTA exist elsewhere in the document, so a whole-page match goes green for the wrong reason, and `innerText` silently omits inactive tabs. Fixed by asserting inside `#listing-grid` |

`degraded` requires the offline guard to **refuse AND announce**, including the sentence that nothing was
sent — a guard that refuses in silence is the exact failure this platform found live when a centralised
offline guard produced no toast because `showToast` is page-local. Both halves are non-vacuous by
construction: the error test fails if the request was never intercepted, the offline test fails if
`whRequireOnline` is absent rather than merely permissive.

> **Five suspected findings this session; five dissolved on inspection** — the `service_triage` "dead branch"
> (reached server-to-server), the top-up guard "at 0%" (my cell selection), the "80-char silent truncation"
> (capped identically at both ends), and now two impatient assertions. Not one was a product defect. The
> single habit behind all five: **before reporting, check whether another layer, another retry, or another
> assertion in the same run already contradicts it.**

**Final state:** transition **99.6%** (249/250) · SQL lane 132/132 · journey lane 14 cells · mutation
~~**100% of 36**~~ **⚠️ fabricated by a broken injection — see §11.11 for the defect and the honest 50.0%
first measurement** · layer 100% with rule + owners disclosed (S2-pwa now 2 cells) · dimension 100% · oracles
refusal 194 · db-truth 36 · rubric 10 · continuity 7 · eval 1 · metamorphic 1 · ratchet PASS.

### §11.10 · Flake ledger — `push-runtime-delivery`

Recorded rather than left to hide, per the arc's own flake policy (a cell that yields both outcomes on
unchanged code is listed, never quietly deleted).

`push-runtime-delivery` went RED once inside a back-to-back verification sweep and has passed **four** other
times, including immediately afterwards and again when deliberately re-run in the sweep's exact order
(`marketplace-state-inducers` → `push-runtime-delivery`) to test for interference between two browser gates.
There is none.

The likeliest cause is the transport blip already characterised in §10.27a: an intermittent
`supabase.auth.getUser()` → `_timeoutFetch` abort that appeared in roughly half of that day's smoke runs,
rotating across pages, and which the smoke template now tolerates explicitly with a logged warning. The push
spec signs in and registers a worker, so it touches the same path.

**Not fixed, and deliberately not widened** — a timeout is not the cause (the wrapper's budget is 45s) and
widening it would measure network weather instead of the product. It is one instance against four, with a
named suspected cause, and the underlying question is already on Ian's list: should the shared Supabase fetch
wrapper retry once on a transport failure for idempotent reads? That decision closes this flake and the smoke
one together, which is why it belongs there rather than in a per-spec patch.

### §11.11 · CORRECTION — the 100% in §11.2, §11.7, §11.8 and §11.9 was FABRICATED BY THE HARNESS

Every mutation figure recorded above this section (27/27, 36/36, 42/42) is **wrong, and wrong in the
flattering direction**. They were not measurements of the bank. They were measurements of a broken injection.
The honest first score, once the harness was fixed, was **50.0%**.

**The defect.** `pg_get_functiondef()` returns a `CREATE OR REPLACE …` **without a trailing semicolon**. The
mutated definition was injected straight after each cell's `begin;`, so the statement that followed it — the
cell's own `insert` — was swallowed into the function body as a continuation of the DDL. Every mutated run
therefore died with `syntax error at or near "insert"` before a single assertion executed.

**Why that produced a 100% instead of an obvious failure.** The runner's oracle treats an ERROR as a
REFUSAL, which is correct for a guard test and catastrophic here:

| cell kind | what actually happened | how the harness read it |
|---|---|---|
| negative (expects refusal) | the fixture never ran; psql errored | "refused" → the cell **PASSED** |
| positive (expects the write to work) | the fixture never ran; psql errored | "refused" → the cell **FAILED** → mutant "killed" |

So every mutant was "killed" by a positive cell that had never run, while every negative cell passed
silently. A 100% built entirely out of a broken fixture. Nothing was ever mutated, and nothing was ever
asserted.

**What caught it.** Not a review — a prediction that failed. The third operator wave was written *expecting
a survivor*, and `hive_provider_branch_removed` came back "killed" when every fixture provider is a
`freelancer` and the hive branch is therefore unreachable. A kill that is impossible on the evidence is a
report about the instrument, not the code ([[feedback_verify_the_instrument_before_the_page]]).

**Three more instrument defects surfaced in the same audit**, each of which had also moved the number in a
direction that was not real:

| defect | effect on the score | fix |
|---|---|---|
| `is_party_false` injected `false or (…)` — and `false OR X ≡ X` | a perfect no-op, unkillable, counted as a SURVIVOR on 3 guards | replace the WHOLE assignment statement |
| then `false and (…)`, on guards whose party test is a DISJUNCTION — `(false and A) or B ≡ B` | collapsed to "is the seller a party", still true, so it "survived" again | prefix mutation of any boolean expression is precedence-dependent; statement replacement is not |
| `refusal_removed_upper` duplicated `refusal_removed` under `re.IGNORECASE` | every guard contributed two IDENTICAL mutants; one real gap printed twice | deleted the operator |
| the leak check grepped `prosrc` for the FIRST draft's mutation text | after the operator was corrected it hunted a string no mutation emits — a safety check that had silently stopped checking | compare each guard's definition byte-for-byte against the pre-mutation capture |

Diagnosing the precedence one needed the **SQLSTATE**, not the row count: mutated and unmutated both raised
an identical `23514`, which is the tell that the mutation never took effect at all.

#### What the honest measurement then found — the actual finding of this arc

| guard | score | cells |
|---|---|---|
| `guard_service_request_status` | **31.6%** — 13 of 19 faults survived | **107** |
| `guard_marketplace_order_status` | 83.3% | 11 |
| `guard_service_topup_status` | 85.7% | 3 |
| `guard_marketplace_listing_status` | 100% | 8 |

**The largest cell population had the weakest teeth**, and the survivors named one coherent blind spot. Every
cell in the bank is derived from the authorised-**transition** set, so every cell is an `UPDATE … SET status`.
Two whole regions of each guard had never been entered:

- **the `TG_OP = 'INSERT'` branch** — what state a row may be BORN in. A top-up born `verified` mints credit
  without ever entering the verification path; an order born `released` skips escrow; a request born
  `accepted` or already matched skips the accept RPC.
- **the `status unchanged` branch** — the rules that hold when a field other than status is edited:
  reassignment of matching, transfer of ownership, a stranger's edit.

A suite organised around one axis is blind along every other, and *adding more cells on that axis cannot
find it*. That is the whole argument for measuring teeth rather than counting cells.

#### The two lanes built to close it

`TB-BIRTH-privileged-birth-refused` (11 assertions, 3 tables) and
`TB-FIELD-nonstatus-edits-and-hive-party` (8 assertions). Both pair every refusal with the legitimate write,
because a guard that refuses everything satisfies all the negatives while breaking the product.

Reachability was checked against `pg_policies` **before** authoring, so no cell asserts a rule RLS already
owns — `status` appears in no INSERT policy, so the born-privileged rules are the guard's alone.

**Two things the live run corrected, both about WHICH LAYER SPEAKS FIRST:**

1. I expected the attribution rule (`client_auth_uid` must be the caller) to be RLS-masked, since
   `WITH CHECK (client_auth_uid = auth.uid())` enforces it too. It came back `guard`. **A BEFORE ROW trigger
   fires before WITH CHECK is evaluated**, so on INSERT the guard always speaks first and RLS is the backstop.
2. The stranger case is genuinely masked, and for the opposite reason: `USING` filters row **visibility**, so
   the UPDATE matches zero rows and the trigger never runs. **`USING` pre-empts a trigger; `WITH CHECK` does
   not.** Same policy, opposite ordering — and only executing it tells you which one you are in
   ([[feedback_check_the_premise_before_building_the_pattern]]).

`ownership_transfer_allowed` survived even after its cell existed, and it was right to: strip the guard's rule
and RLS still rejects the row, so a `blocked` assertion stays green either way. **A refusal is not evidence
about who refused.** Rewritten to assert the layer (`guard` vs `rls`), it kills the mutant. I had written that
exact reasoning into TB-BIRTH one file earlier and still reproduced the mistake.

`state_list_widened` demanded the case a transition grid structurally cannot produce: `settled →
cancelled_by_client`, a client retroactively cancelling a job that is done **and paid**. The derived grid
enumerates neither that transition nor that illegal origin, so 109 cells missed it. **A boundary is only
tested from both sides.**

#### The exclusion discipline, now implemented rather than promised

§11.2 said an unreachable mutant must be excluded with a printed reason. Nothing implemented it. One mutant
qualifies (`stranger_field_edit_allowed`), and the mechanism is the bar: **an exclusion must name why
observation is impossible, not that no cell observes it.** Three admin-bypass mutants looked unreachable for
exactly that weaker reason and were nearly excluded on the strength of TB-I2's prose — then TB-FIELD gave the
guard an admin who is a party *via hive membership* (so `USING` lets the row through) and all three died.

Excluded mutants are **still run every time**. Skipping them would make the list a trapdoor, which is how a
skipped partition reads as a covered one ([[feedback_a_skipped_partition_reads_as_a_covered_one]]). If a cell
ever objects to an excluded mutant, the gate **FAILS** with `STALE EXCLUSION` rather than pocketing the kill.

#### The hive-party self-deal, which nothing had ever covered

`v_is_party` is satisfied either by owning the provider profile **or** by active membership of the hive that
owns it. TB-I2 covers the first. Nothing covered the second — so dropping the hive branch would let an admin
whose *own hive* is performing the job compute as a non-party moderator, take the admin bypass, and drive
transitions on both sides of their own deal. The mutation operator rewrites the first occurrence of that
branch, which is the copy inside `v_is_party` used **only** by the admin bypass, so an admin-party-via-hive is
the only caller who can observe it. Working out which caller can even see a mutant is the actual work;
declaring one "untested" is the easy part.

#### Honest final numbers

```
platform mutation score: 100.0%   (37 killed / 37 viable)   was 50.0% (21/42) when first measured honestly
  guard_service_request_status      100%   18 killed · 0 survived · 109 cells · 1 excluded, printed
  guard_service_topup_status        100%    7 killed · 0 survived ·   4 cells
  guard_marketplace_order_status    100%    6 killed · 0 survived ·  12 cells
  guard_marketplace_listing_status  100%    6 killed · 0 survived ·   8 cells
  verified: every guard byte-identical to its pre-mutation capture
selftest: 1 cell -> 1 kill · 103 derived cells -> 6 · full 109 -> 18
```

**This 100% is not the same claim as the one it replaces.** The first was 42 mutants that never ran. This is
37 mutants each killed by a named assertion, one excluded with a mechanism plus on-disk evidence plus a
falsifiable re-run, and a selftest proving the score tracks cell-set strength.

The selftest also discloses the uncomfortable part, printed on every run: **12 of the 18 kills on the request
guard come only from authored probes — the 103-cell derived grid kills 6.** The grid is broad and shallow.
That is the next punch list, and it is exactly the kind of thing a fabricated 100% would have kept hidden.

> **The sixth dissolved finding is a reversal of the previous five.** §11.9 recorded five suspected findings
> that dissolved on inspection, none a product defect. This one went the other way: a result that looked
> *perfect* was the defect, and the tell was a kill that was impossible rather than a failure that was
> suspicious. **Check an implausibly GOOD result with the same suspicion as a bad one** — a green number is
> a claim, and this one was false four times running while I recorded it as verified in three commits.

**Superseded by this section:** the mutation figures in §11.2 (27/27), §11.7 (100% of 27), §11.8 (36/36) and
§11.9 (100% of 36), plus the same claim in commits `5f134b40`, `59222bff` and `2e5de62a`. The migrations,
probes and gates those commits ship are unaffected — only the mutation number they quote was wrong.

### §11.12 · Re-challenging the fresh 100% immediately — three more survivors, all on the money guard

A 100% earned an hour after discovering a fabricated one does not get banked. §11.11 closed by saying a score
is worth exactly what its operators can express, so a **fourth wave** was written against rules no operator
touched. `guard_service_topup_status` is the only guard on this platform that CREATES money — verifying a
top-up inserts the `service_credit_ledger` row inline — and it had **four cells**. Three of the four new
operators survived it:

| survivor | what it means |
|---|---|
| `mint_on_any_prior_status` | the mint stops caring what the top-up came FROM, so re-verifying an already-verified top-up mints the credit a **second** time |
| `party_provider_account_branch_removed` | verifying **someone else's** top-up into a provider account **you own** stops counting as self-dealing |
| `party_consumer_account_branch_removed` | the same hole for a consumer wallet |

**The shipped guard is correct in all three cases.** These are test gaps, and that distinction is the whole
value of the metric: a survivor says *"nothing would notice if this rule were deleted"*, which is a statement
about the bank, so the fix is a cell and not a migration.

Two structural lessons the wave taught:

- **Authority derived through a DISJUNCTION gives every branch its own authorisation path.** `v_is_party` here
  is three branches — the payer, a provider account you own, a consumer wallet that is you — and the guard's
  own comment says why the second matters: *"verifying a top-up you filed is self-minting, and so is
  verifying someone else's top-up into your own provider account."* Only the payer branch had a cell. An
  untested disjunct is unmonitored code, and an admin who owns the **destination** mints real credit into an
  account they control just as surely as the one who filed the receipt.
- **Mint-once is invisible to a status assertion.** Before and after a re-verify the row reads `verified`
  either way; only a ledger **COUNT** separates "accepted, minted nothing" from "accepted, minted again".

`TB-MINT-topup-party-routes-and-mint-once` (10 assertions) closes all three, with the admin made a party via
the **account** and never the payer — a payer-route party would be refused by the branch TB-I2 already covers,
so the cell would pass without exercising anything new. It carries the moderation half too (an unrelated
top-up still verifies, and mints exactly one entry) and a non-vacuity check that the system path minted once
to begin with, or the mint-once assertion would be comparing 0 to 0.

#### The ratchet had to learn that a GROWN denominator is not a regression

Adding those four operators dropped the score 100% → 92.7%, and the forward-only ratchet called it a
**REGRESSION** and failed the gate. It was wrong, and wrong in a way that punishes the only move that makes
the score worth anything: the bank had not lost a single tooth, it had been asked four new questions and could
not answer three. Left alone, that ratchet would have pressured me to either drop the new operators or fake
the baseline — the ratchet-that-turns-both-ways trap.

The board is now forward-only on **three axes**, which is the same "derived denominator grows by itself"
principle §10 already applies to transition coverage:

| axis | rule |
|---|---|
| `killed` | may **never** fall — the absolute count of faults the bank catches |
| `score` | may fall **only** when `viable` grew; at an unchanged vocabulary it may never fall |
| `fixture_kills` | may only fall — a kill via an errored fixture is weaker evidence than a kill via an assertion, and a spike is the signature of a broken injection |

Two more instances of the **same** defect class showed up while wiring this, both mine: a newly-added ratchet
axis sat **unseeded** because the steady-state path (`score == base`) never wrote the baseline file, so
`killed` stayed absent and `viable` stayed at 37 while the real vocabulary was 41 — a gate that looks
implemented and checks nothing, exactly like the leak detector in §11.11 that was still grepping for the first
draft's mutation text. Persistence is now triggered by any tracked field being **missing or out of date**, not
by the headline number moving.

**State:** mutation **100.0% (41/41)**, 1 excluded with mechanism + evidence + a falsifiable re-run ·
SQL lane **135/135** · transition 99.6% · substrate 720 fresh · canonical_status all green.

> **The pattern worth keeping from §11.11 + §11.12:** the fabricated 100% was caught by an operator written to
> FAIL, and the three real money-path gaps were found by writing four more of them. **A metric you have not
> tried to break is not a measurement.** Every wave of operators so far has either found a real gap or found a
> defect in the harness — none has ever merely confirmed the previous number.

### §11.13 · The last `owed` cell — checking its own reasoning corrected it twice, and its finding is now ENFORCED

`TB-A345-architecture-quality` was the single owed obligation behind the transition board's 99.6%. Its A4 third
carried a documented finding: marketplace.html does `const HIVE_ID = whHiveId()` once at load and stamps it on
every hail, which would file work into the **wrong tenant** if the active hive could change while the page is
open — and it cannot, because reaching the marketplace is always a full page load. **No defect.**

That is a real finding and also a conclusion resting on an invariant nobody enforced. Re-checking it corrected
the reasoning **twice, both errors mine**:

| the claim | what execution showed |
|---|---|
| "every `wh_active_hive_id` write lives on hive.html" | **false** — `index.html:2953` writes it too, during the sign-in hive bootstrap. The *conclusion* survived (index → marketplace is a full page load) but a gate built on the stated premise would have enforced something untrue |
| index.html also does `const HIVE_ID = whHiveId()` — the same stale-capture shape? | **no** — that capture is **function-scoped** inside the ops-home renderer, so it is re-read per call, and the write is deliberately followed by `_initDashboard(...)` to re-render against the new hive. Verified by reading both sites rather than trusting the comment |

So the distinction that matters is **SCOPE, not filename**: a module-scope capture is read once per page load; a
function-scope capture cannot go stale. Of the 16 pages that capture the hive this way, that difference is the
whole safety argument.

**`tools/validate_hive_capture_invariant.py`** (registered `hive-capture-invariant`, static, always runs) turns
the observation into an enforced contract, per the rule that a covered-by-nature cell still gets a gate
asserting what it rests on ([[feedback_build_structure_to_make_it_liveable]]):

- **the writer allowlist** — exactly hive.html and index.html may write the key. A third page is not
  automatically a bug, but it *is* always a decision that requires re-checking capture scope on every reader,
  so it goes red saying exactly that;
- **the capturing pages must not write it** — marketplace / seller / admin must contain zero writers, which is
  the live-bug condition, since a writer in the same document can run after the capture.

It deliberately does **not** compute JS scope from a regex: brace and regex-literal counting over inline script
is the brittle-validator trap this platform has already been bitten by twice
([[feedback_fixed_char_window_validator_is_brittle]], [[feedback_python_heredoc_eats_js_regex_boundaries]]). It
asserts the two cheap, unarguable properties instead, and its self-test injects a writer into marketplace.html
**through the reader** — no file on disk is touched, the same discipline as injecting a mutant inside a
transaction — and requires the gate to go red naming that page.

**The cell stays `owed`, deliberately.** A3 (configurability) reduces to the D9 knobs, which are Ian's to set;
A5 (extensibility) is *demonstrated* rather than assertable — this arc's denominator grows by itself when a
guard changes, which is the claim A5 makes. Banking the remaining two thirds would be a weak cell inflating the
UFAI board, and the A4 third is now owned by a **platform gate** rather than a bank cell, which is the same
disposition the thin layers already use. The board therefore does **not** move, and that is the honest outcome:
the work closed a risk, not a percentage.

### §11.14 · Flake ledger — `platform-page-battery` false-red inside a full-suite run

Recorded rather than left to hide, per the arc's flake policy.

`platform-page-battery` went **FAIL (178.6s)** during a full (non-`--fast`) suite run, then **PASSED all 35
pages** when re-driven standalone immediately afterwards (`P1/P2/P4/P8/P9/P12`, findings=0). Nothing in the
commit it ran against touches a page: the changes were the bank JSON, the mutation harness, three SQL probes,
docs, skills and one new static gate.

The likeliest cause is **contention, not the product**: that suite run drove two live headless-Playwright
batteries back to back (`hive-battery` 35.0s PASS, then the 35-page sweep) while a heavy local DB workload was
still settling, and this platform has already recorded the shape where a heavy gate running *inside* the runner
false-fails on timing and the fix was to judge on a robust statistic rather than a single observation
([[feedback_gate_inside_gate_false_fails_use_median]]).

**Not widened, and not "fixed".** One red against a standalone 35/35 green, cause named, left visible. The
standing question it belongs to is the same one the `push-runtime-delivery` flake raised: whether the shared
fetch wrapper should retry once on a transport failure for idempotent reads — which is on Ian's list, because it
closes both flakes at the source rather than per-spec.

> **Observed while registering the new gate:** the gate registry has **three duplicate `id`s** —
> `memory-integrity`, `companion-page-coverage`, `companion-source-coverage`. Pre-existing and untouched by
> this arc. Flagged because a duplicated id is how two gates can share one baseline entry and quietly
> overwrite each other's floor; worth a look before it matters. **Chased in §11.15 — it already mattered, and
> there was a fourth.** (An earlier draft of this note said "out of 555"; the real registry holds **704**
> entries. 555 came from a regex of mine that silently dropped every id containing an underscore — which is
> also why it missed the fourth problem entirely. A count taken with the wrong instrument is not a count.)

### §11.15 · The registry was never checking itself — 3 duplicate gates, and one collision that was DISCARDING a verdict

Flagged in §11.14 as "observed, not chased". Chasing it found something worse than duplication.

**Four id problems in a 704-gate registry, none of which anything was looking for:**

| id | what was wrong |
|---|---|
| `memory-integrity` | registered **twice**, same script, same args — and the duplicate's label claimed "4-layer: schema + **RLS + index + retention**", none of which that script checks (it checks the `agent_memory` schema, per-tab `session_id` tracking, >90%-similarity dedup, and the memory window passed to the LLM) |
| `companion-page-coverage` | registered **twice**, same script |
| `companion-source-coverage` | registered **twice**, same script |
| `marketplace_deepwalk_ratchet` | **two DIFFERENT gates sharing one id** — `tools/marketplace_deepwalk_scoreboard.py --check` and `validate_marketplace_deepwalk.py` |

The first three cost duplicated runtime and an overstated gate count. **The fourth was live damage.** An id is the
key results, baselines and ratchets are stored under, so two different scripts under one id collide in the
results dict and whichever runs second overwrites the first. `gate_efficacy_ledger.json` shows which way it
went: its lone `marketplace_deepwalk_ratchet` entry carries the *other* gate's label, so the scoreboard gate —
the one that prints the transition, layer, oracle and mutation boards — **was having its verdict discarded, and
could have gone red without registering.** A gate whose result is silently overwritten is worse than a gate that
does not exist, because the registry still lists it and the summary still counts it.

The duplicate label is the more expensive half of the first three, for the same reason: a reader trusting it
would believe memory **retention** was gated when nothing asserts retention anywhere.

**The fix is the assertion that was missing, not just the edits.** `main()` now checks id uniqueness before
running anything and exits non-zero naming the offenders, because a registry that cannot be trusted makes every
number under it unreliable. The three exact duplicates are deleted (keeping, in each case, the copy that emits
a `report` artifact — deleting the wrong twin would have silently dropped a report), and the scoreboard gate is
renamed `marketplace_deepwalk_scoreboard` while the other keeps the original id so its ledger history stays
attached.

> **And the uniqueness check itself shipped broken for about two minutes.** I wrote it against `CHECKS`; the
> registry variable is `VALIDATORS`. `ast.parse` passed — a `NameError` is a runtime error — so a syntax check
> said fine while the suite would have crashed on its first line of real work. It was caught by *running* the
> thing against the real registry instead of trusting that it parsed, which is the same move that caught the
> fabricated mutation score: **execute the instrument, do not merely compile it.** Verified after the fix by
> importing the module and counting ids — 704 entries, 0 duplicates, both deepwalk gates present and distinct.

### §11.16 · The BIRTH lane — deriving the obligations that a transition-shaped bank structurally cannot see

§11.11 found the blind spot and TB-BIRTH closed four of its cells **by hand**. This derives the rest, which is
the difference between fixing an instance and fixing the class: a status added to a CHECK constraint tomorrow
now arrives as an obligation instead of silently not existing.

`derive_transition_matrix.py` already computes the bank's denominator from the guards themselves. It gained a
`parse_births()` that reads each guard's `TG_OP = 'INSERT'` rules, in the **same two shapes** the file already
models for transitions — conflating them would fabricate coverage here exactly as it would there:

| shape | source form | obligations |
|---|---|---|
| ALLOW-LIST | `new.status not in ('requested','broadcasting')` · `new.status <> 'pending_verification'` | the legal set is spelled out, so **every other status in the vocabulary is a refusal obligation** |
| DENY-RULE | `NEW.status = 'published' AND (TG_OP = 'INSERT' OR …)` | only the dangerous target is named; the rest are permitted **by omission** and are reported as ungoverned, never claimed |

**22 birth obligations**, derived from the live guards:

```
service_requests        allow  born: requested, broadcasting          + 10 refusal obligations
marketplace_orders      allow  born: pending_payment                  +  5
service_credit_topups   allow  born: pending_verification             +  2
marketplace_listings    deny   refuses: published    ungoverned-by-omission: draft, removed, sold
```

The runner gained a birth executor (`from: "(insert)"` dispatch). `(insert)` is deliberately not a status: a
birth has no origin state, and giving it a fake one would let a transition-shaped cell claim to cover it —
the exact conflation that hid these 22 obligations in the first place.

#### Three things the build got wrong first, each caught by running it

1. **Six of ten cases came back SKIP, not PASS.** A guard that raises aborts the transaction, so the `BORN=`
   read-back could not run (`current transaction is aborted`) and every REFUSAL was unscoreable. Wrapping the
   INSERT in a plpgsql `BEGIN … EXCEPTION` block keeps the transaction alive so the read-back **always**
   executes — which upgrades the oracle from "did psql print an error" to "does the row exist in that state
   now", the only question that separates a refusal from a silent RLS filter. It was caught by the executor's
   own *"no `BORN=` read-back"* SKIP branch rather than by a green run: **a cell that could not execute must
   never be scored as a refusal**, which is precisely how a broken injection fabricated a 100% in §11.11.
2. **An errcode is the author's CHOICE, not a layer identifier.** `marketplace_listings` born-as-`published`
   returns **42501**, which reads as "RLS refused" under the mapping used elsewhere in this file — yet
   `mkt_listings_insert` only checks `seller_name`, and `draft`/`sold` inserts by the same identity succeed
   (`born=1`). The guard raises `USING ERRCODE = '42501'` deliberately. The sqlstate only distinguishes layers
   where the guards happen to use different codes, as `guard_service_request_status` does (`check_violation`
   throughout — which is what makes TB-BIRTH's attribution assertion sound). Corroboration, never the oracle.
3. **A one-directional teeth check would have passed a lane that always says "refused"** — which this lane
   literally was before fix #1. The selftest therefore asserts both directions **and their inversions**: a
   top-up may be born `pending_verification`, may not be born `verified`, and swapping either expectation must
   FAIL. That is what proves the oracle reads the row rather than echoing the expectation back.

The deriver's own selftest gained four birth cases, including the **ordering trap**: a real guard carries both
a `not in (...)` INSERT rule *and* later `<> 'x'` comparisons, so checking the single form first would return a
one-element legal set and mark two legitimate birth states as refusals — the bank accusing the product, the
same failure this file was already burned by on the wrapped-clause case. Plus a teeth case: a guard with **no**
INSERT rule must yield **no** birth obligations, or every table would be handed phantom cells.

**Why this matters beyond the 22 cells.** The mutation score reported that 12 of 18 kills on the request guard
came only from authored probes — the 103-cell derived grid killed 6. Birth cells are derived, and they flow
into the mutation harness's selection automatically, so the *grid* starts killing the birth mutants that only
`TB-BIRTH` could kill before. Coverage that rests on three hand-written probes is coverage one deletion away
from vanishing.

### §11.17 · Deriving the FIELD lane too — investigated and KILLED, with the numbers

Births were worth deriving: 22 obligations, only 4 of which a hand-written probe covered. The obvious next
move was to do the same for the *field* rules — the `status unchanged` branch that `TB-FIELD` asserts by hand
— so that lane would stop depending on one authored file. Checking first says don't.

Grepping all four guards for the immutable-field shape (`new.X is distinct from old.X`) returns:

```
guard_service_request_status    new.status is distinct from old.status              <- NOT a field rule
                                new.matched_provider_id is distinct from old....    <- a real one
                                new.client_auth_uid is distinct from old....        <- a real one
guard_service_topup_status      (none)
guard_marketplace_order_status  NEW.status IN ('released','refunded') AND NEW.status IS DISTINCT FROM OLD...
                                                                                    <- part of a status
                                                                                       condition, not a rule
guard_marketplace_listing_status (none)
```

**Two real obligations across the whole platform, and both are already asserted** by `TB-FIELD`
(`client_reassigns_matching`, `client_transfers_ownership_layer`). Against that, the parser would have to
exclude `status` — the one field the entire transition lane exists to change — and not be fooled by
`NEW.status IS DISTINCT FROM OLD.status` appearing inside a larger boolean. A derivation that emitted "status
is immutable" would have the bank demanding a refusal for the product's core behaviour: the bank accusing the
product, which this arc has already produced twice from over-eager parsing.

So: **killed, for the same reason CDC was killed in §11.6** — the cost is a parser with two known traps, and
the yield is zero new coverage. Recorded here rather than left as an open "we could also…", because the next
session's version of me will otherwise re-derive the idea from scratch and re-run the same investigation.

The distinction worth keeping is **why births were different**: 22 obligations of which 18 were untested, and
the shape (`new.status not in (...)` / `<> 'x'` / a named forbidden target) is the same one the file already
parsed for transitions. Derivation pays when the yield is large and the grammar is already understood; it does
not pay for two cells behind a new grammar with sharp edges.

**Standing punch list after this arc** — the honest remainder, in priority order:

1. **More operators.** Every wave so far (9 → 15 → 20 → 24) has found either a real gap or a defect in the
   harness itself; not one has merely confirmed the previous number. That is the strongest evidence available
   that the current 100% is a statement about the operator vocabulary and not about the bank.
2. `TB-A345` A3 — the D9 knobs, which are Ian's values to set. The only genuinely blocked cell.
3. The registry's fourth id problem is fixed, but nothing yet asserts that a gate's `script` path resolves or
   that a `report` filename is unique. Same class, not yet closed.

### §11.18 · A LIVE money exploit — an admin could mint platform credit to themselves in one statement

The sixth operator wave started as vocabulary work and found a real vulnerability instead. It came from asking
a narrow question about a single expression: **what does `coalesce(old.X, new.X)` actually mean on an UPDATE?**

`guard_service_topup_status` computes party-ness from the **stored** row:

```sql
v_is_party := (coalesce(old.payer_auth_uid, new.payer_auth_uid) = auth.uid())
           or (coalesce(old.account_type, new.account_type) = 'provider'
               and coalesce(old.account_id, new.account_id) in (select id from service_providers
                                                                 where auth_uid = auth.uid()))
           or ...
```

and mints the ledger entry, eight lines later, from the **incoming** row:

```sql
insert into service_credit_ledger (account_type, account_id, ...)
values (new.account_type, new.account_id, 'topup', new.amount, ...);
```

Those two do not have to agree. One statement makes them disagree:

```sql
update service_credit_topups
   set account_id = '<the admin''s OWN provider>',
       status     = 'verified'
 where id = '<a stranger''s pending top-up>';
```

The gate reads the **OLD** account, correctly concludes this admin is a party to nothing, and takes the
bypass. The mint then credits the **NEW** account. Probed end to end in a rolled-back transaction *before*
writing any fix:

```
RESULT redirect_and_verify=ALLOWED
RESULT ledger_rows=1
RESULT credited_account=f2222222-...-a   amount=500.00
RESULT credited_the_ADMIN=YES-EXPLOIT
```

**500 credits, into the admin's own account, from someone else's receipt.** Nothing else stood in the way:
`service_credit_topups_admin_update` is `USING is_marketplace_admin()` with **no WITH CHECK**, so an admin may
rewrite any column. Two platform admins exist today, so this was reachable, not theoretical.

#### Why mig 003 did not already stop it

`20260730000003` closed "the admin bypass applies only to a NON-party" across all four guards, and this arc has
spent three sections asserting that fix from every angle. It held. **The bypass asked the right QUESTION about
the wrong ROW.** A check and the action it guards must agree on which row they describe — and here the check
was deliberately written on OLD (correct: you should not escape party-ness by editing the row in flight) while
the mint necessarily reads NEW (also correct: the credit goes where the row now says). Both defensible, and
together a hole.

#### The fix, and what it says about an admin's power

`20260730000005` makes the money-routing and receipt fields immutable for any real caller —
`account_type`, `account_id`, `payer_auth_uid`, `amount`, `gcash_ref`. The no-JWT backend path and the
announced `workhive.service_system_write` bypass are deliberately untouched, so seeders and sweeps still work.

The framing that makes it obviously right: **an admin's power over a top-up is to DECIDE it, not to rewrite
it.** Verification and rejection are moderation; editing the destination is forgery. Checked against the
shipped surface before writing it — the only UPDATE path in the product is founder-console `svcTopupDecide`,
which writes `status` alone — so no working flow changes.

The new definition was **extracted** with `pg_get_functiondef` and one anchored block inserted, with the build
script asserting the anchor appears exactly once. Retyping a guard from a partial read is how three unrelated
security rules were once silently dropped from its sibling ([[feedback_i_rebuilt_a_guard_from_a_partial_read]]).

#### Locked in both directions

- `TB-MINT` gained the exploit as a cell: `redirect_then_verify=blocked` **and** `credit_minted_by_redirect=0`,
  because a refusal that nevertheless minted would be the worst outcome and the status assertion alone would
  not see it;
- a new operator, `intake_immutability_removed`, deletes the rule and requires a cell to object — the first
  operator here written to **lock** a live exploit rather than to hunt for one.

```
mutation 100.0% (45/45)  ·  SQL lane 157/157  ·  TB-MINT now 14 assertions
the exploit: ALLOWED + 500 credits BEFORE  ->  blocked + 0 minted AFTER
```

> **What actually found this.** Not a review, and not a failing test — a question about the semantics of one
> expression, asked because a mutation operator needed writing. Four of the six waves have now produced
> something the suite could not: three test gaps, two harness defects, and one live money bug. **The exercise
> that makes a metric trustworthy is the same exercise that finds real defects**, which is the strongest case
> for the sixth wave, and the seventh.

### §11.19 · The class had THREE instances, not one — sweeping it found two more live exploits

§11.18 fixed the top-up redirect. A finding is worth more as a *class* than as an instance, so the same
question was put to every guard: **does the decision read the same version of the row as the action it
authorises?** Two more said no, and both were probed live before anything was written.

| guard | one statement | result BEFORE the fix |
|---|---|---|
| `guard_marketplace_order_status` | `set seller_name = '<me>', status = 'released'` on a stranger's order | **ALLOWED** — `admin_total_sales=1`, the real seller left at **0** |
| `guard_marketplace_listing_status` | `set seller_name = '<me>', status = 'published'` on a stranger's listing | **ALLOWED** — `final_seller` became the admin, `final_status` `published` |

The order one is **sales forgery**: `update_seller_tier` bumps `marketplace_sellers` on `NEW.seller_name`
while the party gate reads `coalesce(OLD.seller_name, …)`, and `total_sales`/`tier` are the marketplace's
trust signals. The listing one is a **takeover**: a stranger's listing, published as the admin's own.

**`guard_service_request_status` was already immune**, and that is the most useful part of the sweep: it
already refuses changes to `matched_provider_id` and `client_auth_uid`. The rule existed on exactly one of
four guards. `20260730000006` generalises it rather than inventing anything — pinning `buyer_name`,
`seller_name`, `price`, `currency`, `hive_id` on orders and `seller_name`, `hive_id` on listings.

Scope was checked against the shipped surface first, so the fix pins identity and nothing else: orders are
updated only as `{status, updated_at}` (marketplace-admin:948), listing moderation patches only
`status`/`moderation_*` (marketplace-admin:714), and a seller editing their own listing changes
title/price/description and never `seller_name` (marketplace-seller:918). Both definitions were **extracted**
with `pg_get_functiondef` and one anchored block inserted each, the builder asserting the anchor appears
exactly once per function.

Locked the same way as the first: `TB-I2` gained both cases plus the **trust counter read back**
(`admin_forged_sales=0` — a blocked claim that still bumped the counter would be the worst outcome and the
status assertion could not see it), and two operators, `order_identity_immutability_removed` and
`listing_identity_immutability_removed`, delete the new rules and require a cell to object.

```
both exploits: ALLOWED BEFORE  ->  blocked, counters at 0, owners unchanged AFTER
mutation 100.0% (47/47)  ·  SQL lane 157/157  ·  TB-I2 now 12 assertions
```

> **The generalisable rule, now stated once:** when a guard's decision and its consequence touch the same
> column, check they read the same VERSION of it. `OLD` for the decision is usually right (party-ness must not
> be editable mid-statement) and `NEW` for the effect is usually right (the effect lands where the row now
> points) — which is exactly why this is easy to ship: **both halves are individually correct.** The defect
> lives in the gap between them, and the fix is to pin the column so the gap cannot open.

#### §11.19a · How far the sweep actually went, and what it deliberately did not touch

Stated precisely, because "we swept the platform" is the kind of claim that rots into a false sense of
coverage. Trigger functions in `public` that combine an authority predicate (`is_marketplace_admin` /
`auth_worker_names` / `auth.uid`) with a write are **nine**:

- the **four marketplace status guards** — the population the class actually lives in. Three were holed and are
  now fixed (`20260730000005`, `20260730000006`); `guard_service_request_status` was already immune because it
  already pinned its identity fields;
- **`guard_and_audit_project_removal`** — a real guard, and **structurally immune**: it acts on
  `TG_OP = 'DELETE'`, where there is no `NEW` row for a decision and an effect to disagree about;
- **eight `audit_*` writers** (asset approval/delete, logbook post-close amendment, PM asset delete, PM
  completion amendment, PM scope schedule change, `journal_service_request`). These are a **different class** —
  they record rather than authorise, so the failure mode is a MISATTRIBUTED audit row, not a bypass. Not swept
  here, and named individually so the follow-up is a work list rather than a vague intention.

So the authority-bypass form of this class is closed on the guards that can express it. The
attribution form is **open and enumerated**: for each `audit_*` above, the question is whether the row it
writes is keyed on `NEW.<actor>` while the decision to allow the write was made on `OLD` — which would let an
actor amend a record and have the amendment logged against someone else.

### §11.20 · The attribution half of the sweep — 5 of 7 already correct, 2 fixed, and a probe that proved nothing

§11.19a enumerated the eight `audit_*` writers as the un-swept half of the row-version class. Swept now, and
the yield is smaller and more interesting than expected.

**Five of the seven actor lookups were already correct.** They resolve the acting worker server-side from
`auth.uid()` — never from a client-supplied name — and constrain the membership to the audited row's hive:

```sql
SELECT hm.worker_name INTO v_actor FROM public.hive_members hm
 WHERE hm.auth_uid = auth.uid()
   AND (NEW.hive_id IS NULL OR hm.hive_id = NEW.hive_id)   -- <- the predicate that matters
 LIMIT 1;
```

**Two did not**: `audit_logbook_post_close_amendment` and `audit_pm_completion_amendment` ended at
`WHERE hm.auth_uid = auth.uid() LIMIT 1`. `LIMIT 1` with no `ORDER BY` and no hive predicate picks an
**arbitrary** membership, so a member of two hives could have an amendment in hive A logged under the
worker_name they use in hive B. Same shape as a limit(1) that once picked the wrong hive
([[feedback_resolving_live_is_not_enough_be_deterministic]]). Those same two are also the only ones carrying a
`COALESCE(v_actor, NEW.worker_name, …)` fallback — they were written to an earlier, looser pattern, and the
class was hardened on five of seven with two missed. **The inconsistency is the evidence**: the correct form was
already in the repo five times.

`20260730000007` copies that form verbatim, `IS NULL OR` allowance included.

#### Measured, and honestly bounded

**Latent, not live.** There are **2** multi-hive members today and **0** use a different worker_name across
memberships, so the arbitrary pick currently returns the same string either way. It becomes a real
misattribution the first time one person is "Pablo Aguilar" in one hive and "P. Aguilar" in another — which
needs no code change to happen.

#### The probe that proved nothing, and why it is recorded rather than banked

A behavioural probe was written and it **failed to be evidence**. It manufactured the state the live data
cannot show — two hives, deliberately different worker_names for one person, an amendment in hive B — and
confirmed the fixed function attributes to `Name In Hive B`. Then the **pre-fix definition was restored inside
the same rolled-back transaction** to watch it fail. It did not fail: the arbitrary `LIMIT 1` returned the
hive-B row anyway, so the probe reported the correct actor in **both** worlds.

**A test that passes against the bug is not evidence.** Banking it would have been exactly the false-green this
whole arc exists to detect — a cell asserting a property it cannot distinguish. Three smaller things the probe
also taught, each a lesson this platform already had and I still walked into:

- `amendment_accepted=yes` meant only *no exception was raised*. The UPDATE had matched **zero rows** because
  `logbook_update` is `USING (auth_uid = auth.uid())` and the fixture never set `auth_uid` — so a filtered write
  looked exactly like a broken trigger ([[feedback_zero_row_write_is_not_an_error]]). Fixed by reading
  `GET DIAGNOSTICS row_count` instead of trusting the absence of an error.
- The first reachability count said **all seven** lookups were unscoped. A regex matching only
  `auth_uid = … AND hm.hive_id` missed the five that write the predicate in a parenthesised `IS NULL OR` form.
  Reading each lookup verbatim corrected 7 → 2.

#### So it is locked where it IS deterministic

A non-deterministic failure cannot be reliably reproduced, so the property is asserted in the **source**:
`tools/validate_audit_actor_hive_scoped.py` (registered `audit-actor-hive-scoped`) requires the hive predicate
in the **same statement** as every `INTO v_actor` lookup — same-statement specifically, because several of these
functions also read `hive_members` elsewhere for a role check, and accepting that would let an unscoped actor
lookup hide behind an unrelated scoped query. Its self-test strips the predicate from one function *through the
reader* and requires a red naming it, so the claim is falsifiable even though the runtime failure is not.

```
7 actor lookups · 5 already correct · 2 fixed (mig 007) · 7/7 scoped now
gate PASS + self-test discriminates · registry 705 gates, still clean
```

> **The generalisable point:** when a fix removes NON-DETERMINISM, an outcome test may pass against the bug by
> luck — so the honest lock is a static assertion about the code, not a green cell about the behaviour. Knowing
> which of the two you have is the difference between evidence and decoration.

### §11.21 · Seventh wave, and a gate that reddened because the code got BETTER

Three operators, aimed at questions the previous 30 could not ask. One found a real gap **in my own migration**,
and two are masked for reasons worth writing down.

| operator | verdict |
|---|---|
| `intake_pin_amount_removed` | **SURVIVED — a real gap.** Dropping `amount` from the pinned intake facts lets an admin inflate a stranger's 500-credit top-up to 50000 and verify it in one statement: **value** forgery, which the redirect fix does not cover |
| `admin_check_always_true` | **EXCLUDED** on the three deny-shape guards; **KILLED** on `guard_service_request_status` |
| `party_reads_incoming_row` | **EXCLUDED** — masked by the fix it was written to test, which is the intended outcome |

**The amount gap was aimed at my own work, and that is the point.** Mig `20260730000005` was written eight
sections ago in this same arc; a new rule with no cell behind it is the same gap as any other and does not get a
pass because I wrote it. `TB-MINT` now asserts `inflate_then_verify=blocked` **and**
`credit_value_by_inflation=0` — on a row that is still PENDING when the case runs, because reusing the
already-verified row would have tested a state where the mint cannot fire at all and the assertion would have
held for the wrong reason.

**The masking mechanism on `admin_check_always_true` is the sharpest in the file.** The mutation widens who
counts as an admin *inside the guard*, while the RLS policy on the same table evaluates the **real**
`is_marketplace_admin()`:

```
mkt_listings_update   USING (seller_name IN auth_worker_names() OR is_marketplace_admin())
mkt_orders_update     USING (buyer_name IN ... OR seller_name IN ... OR is_marketplace_admin())
topups_admin_update   USING is_marketplace_admin()
```

So every actor whose refusal could reveal the mutant is filtered before the trigger fires — and a 0-row UPDATE
*is* a refusal — while the only actor the policy admits is the owner, a party, for whom the bypass never
applies. Generalised: **mutating a guard cannot be observed through a path the policy closes using the same
predicate.** It died on `guard_service_request_status` precisely because `TB-FIELD` gives that guard a
*reachable* admin (party via hive membership).

#### The suite came back 555 PASS / 3 FAIL, and not one was a product regression

| failure | cause |
|---|---|
| substrate freshness | I edited tracked files **while the suite ran**. Self-inflicted; rebuilt to 720/720 |
| **Arc X sign-in resolver** | **the gate reddened because the code improved** — see below |
| Memory M3.1 lint | two `MEMORY.md` index lines over the 200-char cap, re-expanded by the index compaction run earlier in this session. Trimmed at a word boundary; 0 ERR |

**Arc X is the one worth keeping.** `validate_arc_x_cognitive.py` asserted that `submitSignIn` calls
`resolveActiveHiveContext(` by taking exactly **3600 characters** from the function anchor and grepping inside.
Earlier in this same session `submitSignIn` gained an 18-line **real bug fix** — a 15s → 30s edge cold-start
budget plus a null-guard, because `fetchWithTimeout` returns `null` rather than throwing and the user was told
"check your connection" on a perfectly good connection — which pushed the resolver call out to offset **4134**.

The wiring was intact. The window was arbitrary. **A gate that reddens when the code it guards improves is
worse than no gate: it teaches you to dismiss its output, and the next red gets waved through too.** This is the
second time the class has bitten this repo ([[feedback_fixed_char_window_validator_is_brittle]] — "comments grew
the body past +3000; brace-matching was the fix"), so it is fixed at the **helper**, not at the one call site
that happened to break: all five call sites shared the flaw and only one had failed yet.

`_window` now brace-matches the real body, skipping braces inside strings and comments (template-literal `${}`
needs no special case — those are balanced), with the char budget demoted to a runaway cap. Teeth verified
rather than assumed: the extracted body is **4907** chars, contains the resolver, ends on its own closing brace,
and does **not** bleed into `submitSignUp` — a bleeding window would pass on a call belonging to another
function. 20/20 checks green.

> **The triage habit that resolved all three quickly:** for each red, ask *which artifact changed since the last
> green* and check `git log` / `git status` on that artifact **before** reading the gate's explanation. Arc X
> pointed at `index.html`; `git log` showed no new commit and `git status` showed it **dirty**, which localised
> the cause to an uncommitted fix from earlier in the session rather than to a regression. And the standing
> corollary: **editing tracked files while a suite runs guarantees a freshness red** — expect it, re-verify
> standalone, and never let a self-inflicted red sit in a report as though it were a finding.

#### Two more instrument defects, both caught by RUNNING rather than parsing

- The four new exclusions landed in the **`GUARDS`** dict instead of `EXCLUDED`, because my insertion anchor
  matched the wrong closing brace. `ast.parse` **accepted** it — a dict may have tuple keys — but
  `for guard, table in GUARDS.items()` would then unpack a 2-tuple *key* and hand a tuple to `functiondef()`.
  Valid syntax, broken program: the same trap as the registry check in §11.15, in the same session. Repaired and
  verified by **importing** the module and asserting `GUARDS` holds exactly four string keys.
- Backticks in a `bash -c` string command-substituted a word out of an assert as I wrote it ("dropping  from the
  pinned intake facts"). Also already a documented lesson here. Repaired.

```
mutation 100.0% (49/49, 6 exclusions each naming a mechanism + a falsifiable re-run)
ratcheted 90.6% -> 100.0%  ·  SQL lane 157/157  ·  TB-MINT 16 assertions
arc-x 20/20  ·  memory lint 0 ERR  ·  substrate 720 fresh
```

#### §11.21a · The 25 unwritten `report` declarations, diagnosed rather than left as an intention

A declared `report` that no gate writes reads as "this gate leaves an artifact you can inspect", and following
it finds nothing — the same fiction that made the `rls-strict` mislabel convincing. Measured: **25 of the 394**
gates that declare one have a script containing no report-writing code. Made a forward-only ceiling in
`main()` (printed every run, only a RISE fails) rather than 25 blocking fixes, and then diagnosed so the
cleanup is mechanical:

- **21 are unambiguous fiction** — no report-writing code AND no file on disk. All `group: Platform`, and
  mostly one cluster: `voice-phase1/1-5/2/3`, `voice-canonical-anchor`, `voice-routing-unification`,
  `voice-alert-formatting`, `voice-data-flow`, `tts-quality`, `avatar-state`, `dialog-flow`,
  `proactive-alerts`, `multilingual-support`, `persona-contract`, `offline-resilience`, `rag-integrity`,
  `analytics-integrity`, `team-coordination`, `c-track-self-coverage`, `grounded-sweep`, `modal-a11y`. A
  convention declared across one arc and never implemented. **Disposition: drop the field** — it points at
  nothing that exists.
- **4 need individual judgment** because the file DOES exist while the script never names it:
  `memory-integrity`, `ai-asset-versioning`, `ai-eval-regression`, `companion-page-coverage`. Either a sibling
  tool writes it (in which case the pointer belongs on THAT gate, exactly as `rls-strict` did) or the file is
  a stale artifact from an older implementation. Not guessed at here.

Left as a precise work list rather than done, because the ceiling already stops the count growing and the
21-entry edit carries no functional change. What is NOT left open is the question — the split above is the
answer, so the next pass is an edit, not an investigation.

---

## §12 · THE TEETH METRIC BEYOND THE MARKETPLACE — scoped by measurement, not by ambition

Ian, after §11 closed: *"do all of that option and extend it to our roadmap."* Three candidates were on the
table (extend the mutation score to other guards · the `_timeoutFetch` retry · the row-version lens at the
edge-function layer). Before committing to any of them the frontier was **measured**, and the measurement
shrank the biggest one by an order of magnitude — which is the whole point of measuring first.

### §12.0 · The sweep that scoped this arc

Every trigger function in `public` that raises an exception, minus the four already scored, is **27 guards**.
Each was scored on four signals: what table it protects, whether it makes a decision from `OLD` and takes an
action on `NEW` (the shape that produced three live exploits), whether it writes at all, and how many
registered gates name it or its table.

**Two findings, and the first is the reassuring one:**

| finding | consequence |
|---|---|
| **0 of 27 carry the row-version shape** | the class found in §11.18–11.19 is **CONFINED to the four marketplace status guards**, three of which were holed. The trigger layer platform-wide is clean of it — asserted by measurement, not assumed because the fixes landed |
| **4 of 27 are named by NO registered gate** | `check_hive_quota_ai_reports` (writes, protects `ai_reports`), `guard_service_provider_writes`, `check_platform_feedback_rate_limit`, `cap_pdf_job_size`. Nothing would notice if these changed |

The high-risk-looking guards by table (`wh_guard_supervisor_approval`, `check_daily_row_cap`,
`guard_change_order_terms_immutable`) are heavily gate-mentioned (95, 95, 5), so the scoring's own ranking
argues *against* starting there. **Option A is therefore not "score 27 guards" — it is "4 unmonitored
guards"**, which is small enough to do properly instead of broadly.

`gate_mentions` is a PROXY (a text search of gate labels and script paths), so a guard could be covered by a
gate that never names it. Zero mentions is a strong signal, not a proof — each of the four gets its coverage
question answered directly before anything is built for it.

### §12.1 · A — the four unmonitored guards

For each: does any gate actually exercise it (proxy → verified), what does it protect, and would anything
object if its rule were deleted? Where the answer is nothing, the guard gets a cell and the mutation harness
gets a judge for that table. `check_hive_quota_ai_reports` leads because it is the only one of the four that
WRITES, and a quota guard that stops refusing is a cost leak rather than a data-integrity one — the failure
mode is an invoice, which is exactly the class this platform cares about.

**Open design fork, deliberately not resolved by guessing:** the harness judges a guard by re-running *bank
cells for its table*, and none of these four tables has a bank. Either build cells (slower; the denominator
then grows by itself as the marketplace one does) or judge against existing registered gates (faster; the score
then measures those gates' teeth, a weaker claim). Ian's steer was "do all of that option", so the cheap sweep
above ran first precisely so this fork is answered per-guard on evidence rather than once in the abstract.

### §12.2 · B — the `_timeoutFetch` idempotent retry

The standing decision that closes **both** known flakes at their source rather than per-spec:
`push-runtime-delivery` (1 red vs 4 green) and the smoke transport blip. The §11 sweep already established the
adjacent fact — `fetchWithTimeout` returns **null** on timeout and three callers dereferenced it, two of them
telling the user the wrong thing — so the retry question is now better posed: a single retry on a transport
failure for an **idempotent read** is the narrow version, and it must not silently retry a write.

### §12.3 · C — the row-version lens at the edge-function layer

The trigger layer is clean (§12.0), but the class generalises: *a check and the action it authorises must read
the same version of the same thing.* At the edge, the analogue is a function that validates one field of a
client payload and then acts on another — "verify id X, act on id Y". 57 edge functions were swept
2026-07-20 for **caller entitlement** and all were gated; none was audited for read/act divergence, which is a
different question about the same functions.

### §12.4 · Method, unchanged from §11

Every claim measured before it is acted on; every fix locked twice (a cell that asserts the behaviour **and**
a mutation operator that deletes the rule); every exclusion names the mechanism that makes observation
impossible and stays executable so a stale one fails loudly. And the standing lesson that produced this whole
arc: **check an implausibly good result with the same suspicion as a bad one.**

### §12.5 · Where this arc actually got to, and what is honestly still open

**§12.1 — three of the four unmonitored guards are scored**, each with a cell, its own operators, and a
verified 100%:

| guard | operators | what it protects | verdict |
|---|---|---|---|
| `check_hive_quota_ai_reports` | 4 | a cost ceiling; the only one of the four that WRITES | correct in both modes, now watched |
| `guard_service_provider_writes` | 4 | `verified` (the trust badge) and `on_job` (dispatch state) | correct on all four rules, now watched |
| `check_platform_feedback_rate_limit` | — | 5 submissions/hour per identity | holds for a stable identity; **evadable** — see below |

**Still open, deliberately:** `cap_pdf_job_size`, the fourth and mildest (a 200-chunk ceiling on `pdf_jobs`).

#### The one real finding, and why it is a fork rather than a fix

The feedback rate limit **is evadable**. Six submissions under six different `worker_name`s were all accepted,
because the bucket is `COALESCE(auth_uid, worker_name, contact_email, 'anonymous')` and `platform_feedback` is
anon-writable — so for an unauthenticated submitter the bucket key is a field the **client supplies**
([[feedback_free_text_identity_is_a_claim]]).

It is **not** silently fixed, because every fix changes product behaviour:

| option | cost |
|---|---|
| bucket all anonymous submissions as `'anonymous'` | spam-proof, but throttles legitimate anonymous users **collectively** at 5/hour platform-wide |
| keep per-name buckets, add a global anonymous ceiling | preserves individual throughput, needs a second number chosen |
| accept it | the form is low-value to spam, and the DB has no IP to key on |

That is a policy trade, not a defect with one right answer, so it is Ian's. The cell asserts only what the
guard genuinely does and **deliberately does not encode the evasion as an expectation** — baking it in would
make the eventual fix read as a regression.

#### §12.3 — the edge-function lens, scoped and sampled, NOT audited

**32 of 59** edge functions take three or more id-ish fields and gate on an identity: that is the population
where "validate one field, act on another" can live. The class is already known one layer down — the AHK4 gate
records that a `WITH CHECK` "validated that hive_id is one the caller belongs to and said NOTHING about whether
the PARENT lived there", closed by mig ...017 with four RESTRICTIVE policies. The edge analogue is a
SERVICE_ROLE function that validates `hive_id` and then acts on a child id without checking the child belongs
to that hive.

**Sampled 1 of 32.** `export-hive-data` is CLEAN and is the reference shape: it calls
`checkSupervisor(jwt, hive_id)` and then exports `p_hive_id: hive_id` — the check and the action read the SAME
id, and the `target_id` the proxy flagged is an audit-log column, not a second input. One clean sample is not
32 audited, and the remaining 31 are the next unit rather than a claim.

#### §12.2 — B is untouched

The `_timeoutFetch` idempotent retry is still open. §11's sweep sharpened the question rather than answering it:
`fetchWithTimeout` returns **null** on timeout and three callers dereferenced it, so the retry must be scoped to
**idempotent reads** and must never silently retry a write.

> **What this arc demonstrates about method, more than about guards:** measuring the frontier turned "27 guards"
> into "4 guards", and 4 into 3-done-plus-1-mild. The measurement was cheaper than any of the work it scoped, and
> it also produced the reassuring half — **0 of 27 carry the row-version shape**, so the class that produced
> three exploits is confined and closed rather than merely patched where it was noticed.

### §12.6 · The rate-limit fork, resolved — a global anonymous ceiling (mig 20260730000008)

Ian chose the global ceiling over bucketing every anonymous submitter together, and the reason is the one that
mattered: the collective option is spam-proof but throttles legitimate anonymous feedback at 5/hour
platform-wide, turning away real users in a busy hour to stop a hypothetical one.

**The fix:** keep the per-identity 5/hour bucket, add **20/hour on `auth_uid IS NULL`** — keyed on the null
check and *not* on the coalesced identity, because **a bound the client can move by changing a string is not a
bound**. 20 is four distinct anonymous submitters at their full individual allowance. Signed-in users are
untouched; their bucket is already an id they cannot forge. Same `ERRCODE 23P01` as the existing limit, so the
client's friendly toast needed no change.

```
BEFORE   6 submissions, 6 different worker_names  -> all 6 accepted   (limit_evaded_by_renaming=YES)
AFTER    25 submissions, 25 different names       -> renaming_still_evades=no, refused 23P01
         6 submissions, 1 name                    -> 5 accepted, 6th refused 23P01  (unchanged)
```

Ratcheted with two operators — `anon_ceiling_removed` and `anon_ceiling_widened` — because a ceiling raised out
of reach is the same hole with a number in front of it. Both die to the new cell.

#### The probe was wrong twice first, and both were visibility mistakes

1. **It reported the evasion as still open after the fix.** The probe made 11 anonymous submissions against a
   ceiling of 20 — it never reached the wall it was testing. A negative aimed short of the bound proves nothing.
2. **Then it computed its own headroom as 20 when the truth was 15.** The `anon` role cannot SELECT unpublished
   feedback (the read policies expose only `is_public` rows), so the probe was blind to the very rows it had
   just written, while the guard — SECURITY DEFINER — counted every one. **A fixture that cannot see the state
   it reasons about will produce a confident wrong number**
   ([[feedback_a_test_asserting_a_state_it_does_not_control]]).

Fixed by stating the property in a form that needs no visibility: attempt 25 under 25 names and require that
renaming does **not** carry all 25 through. That assertion is robust to whatever else is in the hour, which a
computed-headroom assertion never was.

```
mutation 100.0% (67/67) across SEVEN guards  ·  SQL lane 160/160  ·  bank 278 cells
substrate 720 fresh  ·  canonical_status green
```

### §12.7 · §12.1 closed — all four unmonitored guards scored, 8 guards at 100% (70/70)

| guard | ops | protects | outcome |
|---|---|---|---|
| `check_hive_quota_ai_reports` | 4 | a cost ceiling (the only one that WRITES) | correct in both modes; the silent warn-only log now has an oracle |
| `guard_service_provider_writes` | 4 | `verified` (trust badge) + `on_job` (dispatch) | correct on all four rules |
| `check_platform_feedback_rate_limit` | 2 | 5/hour per identity + **20/hour anonymous ceiling** | was EVADABLE; fixed by mig 008 |
| `cap_pdf_job_size` | 3 | a 200-chunk resource bound | correct; boundary pinned from both sides |

Three were correct and merely unwatched. One was genuinely broken. That ratio is the argument for the sweep:
**you cannot tell which is which by reading, and the measurement cost less than either outcome.**

#### Every cell in this section was wrong at least once first, and the same discipline caught each

- **the on_job negative never reached its clause** — the guard tests `new.verified` first, so a
  born-verified-AND-on_job row is refused by the badge rule. Aimed properly, with every earlier clause satisfied.
- **a fixture killed a mutant by BREAKING SETUP** — my first backend-branch fix planted a verified provider in
  the fixture. The evidence-quality ratchet went red (fixture-kills 2 → 3 at an unchanged 100%), correctly: a
  mutant that dies because a cell could not RUN is not one the bank noticed. Restated as a permission assertion.
- **the rate probe never reached the wall** — 11 submissions against a ceiling of 20.
- **then it computed its headroom as 20 when the truth was 15** — the `anon` role cannot SELECT unpublished
  feedback, so it was blind to rows it had just written while the SECURITY DEFINER guard counted every one.
- **the pdf cell reported the cap rejecting a legitimate 200-chunk job** — it was blocked at **23514** by
  `pdf_jobs_target_table_check`, not the guard's **54000**. Only the sqlstate distinguished them.

That last one is the section's lesson in miniature, and it is the same one the AHK4 gate records from an earlier
arc: **verify WHAT blocked a write, never merely THAT something did.** Five cells, five wrong-first drafts, five
caught by asserting the mechanism rather than the outcome.

```
mutation 100.0% (70/70) across EIGHT guards (was four at the start of §12)
SQL lane 161/161  ·  bank 279 cells  ·  transition 99.6% (278/279)
substrate 720 fresh  ·  ratchet holds
```

### §12.2a · B resolved — one retry for idempotent reads, never for writes

The standing decision, taken. Two gates had flaked on the same shape — `push-runtime-delivery` (1 red against 4
greens) and the Playwright smoke tier's Supabase blip — and neither was a product defect or a timeout: the
wrapper's budget is 45s and both failures landed in **milliseconds**. They were the network briefly refusing a
connection. Widening each spec's budget would have measured network weather instead of the product, so the fix
went to the source.

**Scoped by HTTP METHOD, not by an opt-in flag**, and that is the whole design:

| case | behaviour | why |
|---|---|---|
| `GET` + transport failure | retried once, 250ms apart | the flake this closes |
| `POST`/`PUT`/`PATCH`/`DELETE` | **never** retried | a retried write is how one payment becomes two |
| `AbortError` (timeout) | returns `null` on the FIRST attempt | silently doubling a budget breaks the contract callers reason about — and §11 had just fixed three callers for mis-handling that null |
| persistent failure | exactly **2** attempts | the recursion guard is all that stands between "one retry" and an unbounded budget |

A flag would have to be remembered at ~20 call sites and the helper cannot know whether its caller is safe to
repeat. HTTP already answers that: GET is idempotent by contract, so every write method is excluded **by
construction** rather than by discipline.

Locked by `fetch-retry-contract` (registered, static, no DB or browser), whose four assertions run against the
**shipped text of utils.js** — the helper is lifted out of the real file rather than copied into the test, so the
gate cannot drift from the code it guards, which is how every hand-mirrored fixture on this platform has
eventually lied. Its self-test requires all four named cases to have actually run, because a suite that skips its
own cases still reports "4 pass".

```
4/4 assertions · registry 706 gates, ids unique / scripts resolve / reports unclaimed
```
