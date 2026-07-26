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
