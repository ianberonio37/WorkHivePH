# INVENTORY — Page-Deep UFAI PDDA Arc  (drafted for a fresh window)

**Drafted 2026-07-12** (LOGBOOK arc's fresh window, wrapping on Ian's (e)). Same 6-phase PDDA
(Understand → Deepwalk → Ideate → Roadmap → Execute → Re-deepwalk) as eng-design / resume / landing /
analytics / integrations / Hive / Community / Marketplace / Project-Manager / **Logbook** (the last just landed).
Ian: *"I love the PDDA flow — the same as eng-design & resume-builder (we regressed from that clean flow last
arc). Another, refined: PDDA for the Inventory page + its subdirs, extend the UI/UX + UFAI we already have.
I'm striving for the BEST inventory + its cross-page connectivity to the appropriate pages using the reuse
discipline. Refine + extend the terms I've missed. Wrap up, proceed in a fresh window."*

> **What this arc IS.** Deep-walk `inventory.html` (+ its `learn/` subdir) as the real personas, measure every
> axis LIVE, and drive it to the **best spare-parts inventory** — a field tech's fastest, most trustworthy way to
> FIND / RECEIVE / CONSUME / REORDER a part — by (1) perfecting the **stock-management UX** (fast, mobile-first at
> the shelf, scan-first, low-friction, the right ACTIONS for the right STOCK-STATE), (2) treating inventory as the
> platform's **canonical parts SOURCE + a tamper-safe LEDGER** whose count + provenance must reconcile and flow
> accurately into every consumer, and (3) applying the **reuse discipline** so the part-picker / reorder /
> marketplace-listing / CMMS-sync **compose FROM** the inventory item rather than re-inventing "a part."

---

## Scope (grounded, 2026-07-12)

- **Surfaces:** `inventory.html` (2077 lines — the tool: item list + low-stock triage + item detail/edit +
  receive/consume/adjust + part-picker + approval) · `learn/` subdir: `spare-parts-inventory-philippine-plants`.
  (Confirm any deep-link/embed states + the parts-picker modal reused by logbook/PM in Phase 0.)
- **Data model (rich — already exists):** `inventory_items` (81 rows) via **`v_inventory_items_truth`** (23 cols:
  part identity `part_number/part_name/category/unit` + stock `qty_on_hand/min_qty/reorder_point` + location
  `bin_location` + **asset-linkage `linked_asset_node_ids` (uuid[])** + approval `status/submitted_by/approved_by/
  approved_at` + derived flags **`is_out_of_stock`/`is_low_stock`/`is_critical_low`** + `notes/photo/worker_name`)
  · **`inventory_transactions`** (423 rows — the **LEDGER**: every receive/use/adjust movement with `qty_after`).
- **Connectivity is ALREADY SUBSTANTIAL (like logbook, unlike PM's X≈0) — inventory is a HUB and the SOURCE:**
  - **Reads IN (inventory.html):** `asset_nodes` (part↔asset linkage), `inventory_transactions` (the ledger),
    approval workflow. Written INTO by **logbook** (`inventory_deduct` — parts consumed on a fault, ledger-safe),
    **PM-scheduler** (parts on a PM), **marketplace** (part_number/source_inventory_item_id bridge), **CMMS sync**.
  - **Feeds OUT (`v_inventory_items_truth` consumed by ~10 surfaces + a dozen edge fns):** `logbook`/`pm-scheduler`
    (parts-picker), `marketplace` (list surplus / source a part), `alert-hub` (low-stock alerts), `analytics`
    (parts-consumed / stock value), `index`/`hive` (low-stock tiles), `assistant` (companion grounding),
    `shift-planner-orchestrator` (parts-prestage for the shift), **`parts-staging-recommender`** (predictive
    replenishment from failure history), `batch-risk-scoring`, `intelligence-report`, `cmms-webhook-receiver`.

---

## ★ THE HEAVYWEIGHTS (refined + extended from Ian's thoughts)

### Heavyweight 1 — U: the BEST stock-management UX (the tech at the shelf)
The core job is a technician on the floor who needs a part FAST — find it (search/scan/bin-location), see if it's
in stock, consume it against a job (ledger-safe), receive a delivery, or flag a reorder. "Best" = lowest friction
to a TRUSTWORTHY stock action: the part-search/scan, the mobile-390px field view (the tech at the shelf is THE
persona), barcode/QR scan, photo, bin-location wayfinding, and the right ACTIONS surfaced for the right STOCK-STATE
(a critical-low item screams reorder; an out-of-stock blocks the deduct + offers marketplace-source). Extend the
UI/UX we already have (the item list, the parts-picker modal, low-stock triage) — measured LIVE against plant reality.

### Heavyweight 2 — X: the canonical parts SOURCE + tamper-safe LEDGER + provenance spine
Inventory is a **LEDGER**, not just a count. The keystone is **ledger integrity**: `qty_on_hand` must reconcile
with the `inventory_transactions` ledger's running `qty_after` at every point (precedent bug:
[[reference_inventory_ledger_seesaw]] — qty_on_hand vs latest qty_after drifted on **77/82** items; a seesaw between
the balance column and the ledger). Every deduct/receive/adjust must be ledger-safe (write `qty_after`, never
double-deduct, never go negative) AND traceable. And downstream (analytics parts-consumed, marketplace part flow,
PM parts, alert-hub low-stock) must trace back to real ledger movements — no undercount, no phantom stock.

---

## ★ EXTENSION 1 — STOCK-STATE is the "kind" facet of an inventory item (refining "the best inventory")
Parallel to the logbook arc's entry-kind facet: an item is fundamentally in one STATE, and the state should ROUTE
its actions + downstream. The schema already half-models this (`is_out_of_stock`/`is_low_stock`/`is_critical_low`,
`reorder_point`) — refine it into a first-class **stock-state** facet that shapes the UI + the routing:
- **healthy / in-stock** → the default; quick consume/receive.
- **low** (`qty ≤ min_qty`) → surface a reorder nudge; feed alert-hub.
- **critical-low / at-reorder-point** (`qty ≤ reorder_point`) → escalate: alert-hub + a reorder action + the
  parts-staging-recommender.
- **out-of-stock** (`qty = 0`) → BLOCK the deduct (can't consume what isn't there — negative-stock guard) + offer
  **marketplace-source** (buy from another hive) + a reorder.
- **over-stock / surplus** → offer **marketplace-sell** the surplus (ties the marketplace reuse).
Phase-3 fork (fresh window): surface stock-state as a first-class triage lens + action-router vs. a derived pill.

## ★ EXTENSION 2 — REUSE discipline: the inventory ITEM is the canonical PART; others COMPOSE from it
Several surfaces do "pick / reserve / list / sync a part" that overlaps inventory — **the parts-picker**
(logbook `inventory_deduct`, PM parts), the **reorder/reservation**, the **marketplace part-listing**
(`part_number`/`source_inventory_item_id` bridge the Marketplace arc built — [[reference_marketplace_partsflow_and_trust]]),
the **CMMS parts-sync**, and the **parts-staging-recommender**. The discipline: **the inventory item is the canonical
parts primitive; each should REUSE / COMPOSE from it (via `part_number` / `source_inventory_item_id`) rather than
re-invent its own part record.** Phase-3 synthesis deliverable: FUSE (compose from the inventory item, name what's
deleted, blast radius) vs. KEEP-DISTINCT-with-a-reason (fitness-gated — [[feedback_synthesis_not_just_audit]] +
the reuse-is-fitness-gated discipline). Lead with the strongest fusion case (likely the parts-picker, which is
definitionally inventory-derived, reused by logbook + PM).

## ★ EXTENSION 3 — the REORDER / REPLENISHMENT loop (a term Ian implied via `reorder_point` + CMMS/marketplace)
Inventory isn't a static count — it's a **replenishment LOOP**: `reorder_point` → reorder (PO / marketplace-source /
CMMS) → receive (ledger-safe) → back in stock. Extend the arc to verify the loop closes: low-stock → alert-hub →
reorder action → receive → stock restored, all ledger-safe + traceable. The **`parts-staging-recommender`** edge fn
already recommends parts from failure history — the **predictive-replenishment** tie-in (stage the parts a failing
asset will need before it fails). This is the "supply-chain with teeth" axis.

## ★ EXTENSION 4 — ASSET-LINKAGE / spare-parts-BOM (the `linked_asset_node_ids` array Ian didn't name)
Inventory items link to assets (`linked_asset_node_ids uuid[]` — which parts fit which equipment). This is the
**spare-parts-BOM** relationship: a tech at a broken pump should instantly see "which parts fit THIS asset + are they
in stock + which bin." Extend to verify the asset↔part linkage is bidirectional (asset-hub shows its spares;
inventory shows the item's assets) and DRIVES the fault-parts-picker (logbook's parts-picker for a fault on asset X
should default to X's linked, in-stock parts). Ties Heavyweight 1 (fast fault-consume) + the asset-hub reuse.

---

## The scored axes (Inventory sub-dimension decomposition — fill % LIVE in Phase 2)
- **U — best stock UX** (search/scan/bin-wayfinding, stock-state action-router, mobile-390px shelf view, receive/
  consume/adjust speed, low-stock triage, photo). Expect this + reuse to be a heavyweight.
- **X — ledger integrity + PROVENANCE** (qty_on_hand ↔ inventory_transactions reconciliation, anti-seesaw; the ~10
  consumers safe-keyed; asset-linkage bidirectional; no phantom/undercounted stock).
- **F — flows E2E** (receive stock · consume on a fault ledger-safe · adjust · reorder · approve · marketplace-source ·
  marketplace-sell surplus · CMMS-sync · offline?).
- **A — plant-floor mobile** (axe-0 full WCAG 2.2 AA + 44px @390px; the tech at the shelf; reuse `arc_u_full_impact_scan.mjs`).
- **I — integrity + audit** (hive isolation on every read/write; auth_uid on every client write; approval-gate NOT
  Postgres-bypassable [[feedback_ui_only_approval_gate_is_bypassable]]; **negative-stock guard** [Math.max(0,…)];
  ledger tamper-evidence; parts-double-deduct guard).
- **AI — grounded** (companion answers stock questions grounded via `v_inventory_items_truth`; parts-staging-recommender
  fed by real failure history; any AI narrative WAT-split — counts/qty from the truth view, never model-authored).

## The PDDA loop (6 phases — identical to the prior arcs)
1. **Understand** — map `inventory.html` + subdir + every table + every connectivity edge (IN writes + OUT consumers).
   File:line attach points; measure the provenance chain (item → ledger → analytics/alert/marketplace) + the
   qty_on_hand↔ledger reconciliation (expect a seesaw gap per the DI §10.5 lesson).
2. **Deepwalk baseline (MEASURED LIVE)** — Playwright MCP as tech/supervisor/new-user (390px shelf-first) + postgres
   MCP at the DB. Deepwalk the WORKED state (receive a delivery, consume a part on a fault, adjust, hit a low-stock).
   Fill the scoreboard %. Confirm U + reuse + ledger-integrity are the frontier.
3. **Ideate** — fan-out skills (frontend, mobile-maestro, qa-tester, inventory-validator, data-engineer, multitenant,
   ai-engineer, analytics-engineer, integration-engineer for CMMS, marketplace for the reuse) + reputable sources
   (spare-parts inventory / MRO stock UX, reorder-point/EOQ, barcode field UX) → cited backlog per axis.
4. **Roadmap** — synthesize the scoreboard (% per axis, owning skill, citation, locking gate) + the synthesis
   decisions (stock-state facet; the reuse FUSE/keep-distinct verdicts for parts-picker/reorder/marketplace/CMMS;
   the asset-BOM linkage).
5. **Execute** — keystone-first (best stock UX + ledger integrity + the highest-value reuse fusion), then cheapest-
   first; LIVE-verify EACH slice; ratchet a measured-% board; forward-only gate in `run_platform_checks` (extend
   `validate_inventory.py` / `validate_inventory_integrity.py` / the `inventory-validator` skill); skill + memory writeback.
6. **Re-deepwalk** — re-run the persona walk; confirm every axis at its roadmap target, measured + gated.

## What we already built that this arc EXTENDS (don't re-do; build on)
- **`inventory-validator` skill + `validate_inventory.py` + `validate_inventory_integrity.py`** → extend for the
  stock-state facet, ledger reconciliation, negative-stock guard, reorder loop.
- **The anti-seesaw ledger lesson** ([[reference_inventory_ledger_seesaw]] — qty_on_hand vs latest qty_after; 77/82
  drifted) → the X/ledger-integrity keystone.
- **`inventory_deduct` ledger-safe** (logbook/PM/marketplace arcs) → the "parts consumed on a fault" flow (verify).
- **Marketplace part_number bridge** ([[reference_marketplace_partsflow_and_trust]] — part_number/source_inventory_item_id
  Sell/Find/Receive) → the reuse Extension 2 keystone.
- **`parts-staging-recommender`** edge fn (predictive parts from failure history) → the reorder/replenishment Extension 3.
- **`v_inventory_items_truth`** (derived stock flags, approval-workflow) + the FK/array linkage → the provenance keystone.
- **Arc-U a11y instruments** (`arc_u_full_impact_scan.mjs`, focus-trap probe, whModalA11y) → the A axis (390px shelf).
- **The Logbook/PM/Community/Marketplace fabric + provenance-chip pattern** → the X provenance chips + reuse verdicts.
- **`feedback_ui_only_approval_gate_is_bypassable`** + **`feedback_authuid_attribution_on_every_write`** → the I axis.

## NEXT (fresh-window execution starts here)
1. **Phase 0–1 (Understand):** map the tool + subdir × every axis; measure the connectivity (IN writes + the ~10 OUT
   consumers) and the **qty_on_hand ↔ inventory_transactions ledger reconciliation** (expect a seesaw gap per DI §10.5);
   inventory the reuse-overlap surfaces (parts-picker, reorder, marketplace, CMMS, parts-staging).
2. **Phase 2 (Deepwalk baseline):** live persona walk (tech/supervisor/new-user, 390px shelf-first), DB-verified; fill
   the scoreboard %. Confirm U (best stock UX) + reuse + ledger-integrity are the frontier.
3. **Phase 3–5:** keystone = **best stock UX** (stock-state action-router + scan/find speed) + **ledger integrity**
   (close the seesaw + negative-stock guard) + the highest-value **reuse fusion** (parts-picker composes FROM the item)
   + the **asset-BOM** fault-parts-picker; then cheapest-first per axis; each slice LIVE-verified + gated.
Test: pabloaguilar / test1234, hive resolves via `wh_active_hive_id` (reseed rotates auth_uids — re-sign-in + set the
key; see [[reference_gate_regression_fanout_recovery]]). Pairs the Logbook arc (entry-kind facet + reuse + ledger-safe
pattern) + [[feedback_synthesis_not_just_audit]] (fuse-into-ONE / keep-distinct-with-reason) + the anti-seesaw lineage
discipline ([[feedback_anti_seesaw_lineage_discipline]]) + the marketplace part_number bridge + the inventory-validator skill.

---

# ═══ EXECUTION LOG + SCOREBOARD + SYNTHESIS (2026-07-12) ═══

## Measured baseline (Phase 2, LIVE — pabloaguilar / hive c9def338, 390px)

| Axis | Baseline finding (measured) | Disposition |
|---|---|---|
| **X — ledger integrity** | Reconciliation ALREADY GREEN: 81 items / 423 txns, **0 drift, 0 chain-breaks** (DI §10.5 gate holds). The arc doc's "expect a seesaw" was stale. BUT the ledger was reconciled, **not tamper-safe**. | verify-live, not re-fix |
| **I — isolation/integrity** | **KEYSTONE (confirmed exploit):** `inventory_transactions_write` WITH CHECK = `auth.uid() IS NOT NULL` only → a hive-A member inserted a ledger row against a hive-B **item** → SECURITY DEFINER sync trigger mirrored bogus qty_after onto the foreign item (**78→88888**). Approval-gate on items IS db-enforced (good). | FIXED + gated |
| **U — best stock UX** | Strong page, 2 gaps: **critical-low invisible** (LOCT-567 2/min-4 wore the same "Low" badge as a merely-low part); **"Sell surplus" mis-gated** on every `ok` item (CHAIN-12B at 2/min-1 offered Sell). `reorder_point` is a **fake alias** of `min_qty` in the view. | FIXED (5-state facet) |
| **Reuse** | logbook fault-parts-picker read RAW `inventory_items` (no derived flags); project-manager's picker read the view — inconsistent. | FIXED (compose from view) |
| **Asset-BOM (Ext 4)** | `linked_asset_node_ids` schema-present but **0/81 populated** → inventory asset badges + the "which parts fit this asset" fault-picker were dead. | FIXED (seed + tool + post-step) |
| **A — a11y (390px)** | Inventory's OWN controls clean (0 btns w/o name, 0 imgs w/o alt, 0 inputs w/o label). 14 sub-44px hits are SHARED components (nav-hub tabs 42px, companion launcher micro-controls 17px) — cross-page, noted for mobile-maestro. | mostly green; shared-cpt backlog |
| **F — flows** | Use/Restock happy path ledger-safe + attributed live (14→13, qty_after=13, job_ref+auth_uid set). Marketplace bridge (Sell/Find) present; reorder loop present via alert-hub. | green (happy path) |

## Shipped this turn (keystone-first, each LIVE-verified + gated)

1. **X/I — cross-hive ledger-tamper fix** — migration `20260712000011`: hive-scoped WITH CHECK (parent-item membership-join + `txn.hive_id = item.hive_id`), trigger hive-guard, `qty_after >= 0` CHECK. Gate `validate_inventory_txn_isolation.py` (LIVE rolled-back two-tenant, reseed-robust). Pre-fix exploit → post-fix 42501/23514, legit path unaffected. PRODUCTION_FIXES #41. Taught security + multitenant-engineer + inventory-validator.
2. **U — 5-state stock facet** — `out / critical / low / ok / surplus`; critical surfaced (badge + banner + verdict escalation), `Sell` gated to genuine surplus (qty≥3×min, honest copy), `Find on Marketplace` extended to critical. Gate `validate_inventory.py` L5.
3. **Reuse (Ext 2)** — logbook picker composes from `v_inventory_items_truth` (security_invoker) → inherits the derived flags → LOW/CRITICAL chip when consuming a scarce part on a fault.
4. **Asset-BOM (Ext 4)** — `tools/backfill_asset_part_bom.py` (reproducible, ledger-untouched) + shared `compute_asset_links` mapping (one-per-family spread) + born-on-reseed via the `run_post_seed_edges` post-step; 64/81 parts linked. Fault-picker floats the fault's-asset spares to the top + "Fits this asset" chip. Canary `validate_inventory_integrity.py` `asset_bom_coverage`.
5. **AI grounding** — inventory.html called NO `WHAssistant.setContext` (only 4 pages did), so the "Inventory Manager" companion confabulated stock counts. Added `setInventoryCompanionContext()` (piiSafe LIVE snapshot from the truth-view data: total + 5 stock-state counts + at/below-reorder SKUs, no PII). Verified live via `WHAssistant.getContext()`. Taught inventory-validator.
6. **Ext-3 reorder loop — VERIFIED CLOSED:** low(min_qty)→alert-hub `is_low_stock` signal (3 live) → Find-on-Marketplace / reorder → Restock/receive (ledger-safe). The only gap is that `reorder_point` ≡ `min_qty` (a naming observation, not a bug — the loop functions on the min_qty threshold); a real lead-time reorder point is a future data-model enhancement.

## SYNTHESIS — reuse FUSE / keep-distinct verdicts

- **Parts-picker (logbook + PM) → FUSE the SOURCE.** Both are definitionally inventory-derived; they must read the ONE canonical truth view (`v_inventory_items_truth`), not the raw table. DONE for logbook; PM already did. The ACTIONS stay distinct (logbook consumes → `inventory_deduct`; PM links → `project_links`) — same source, different verbs. **Lead verdict: one source, many verbs.**
- **Stock-state facet → FUSE onto the derived flags.** The view already computes `is_low_stock`/`is_critical_low`; the UI must not re-derive or flatten them. 5-state is the single canonical ladder now consumed by inventory.html + the picker chip.
- **Marketplace bridge → KEEP DISTINCT (fitness-gated).** Sell-surplus / Find-on-Marketplace compose FROM the item (via `part_number`/`source_inventory_item_id`, the Marketplace-arc bridge) but are a genuinely different job (cross-hive trade) — keep as a routed action, now correctly gated by stock-state.
- **Reorder loop (Ext 3) → `reorder_point` ≡ `min_qty` is CORRECT, verified against the published guide (NOT a fork).** The `learn/spare-parts-inventory-philippine-plants` article's own math proves it: step 3 "min = monthly-usage × lead-time-months + safety buffer; **below min triggers a reorder**" and step 5 "**Reorder Point** = daily-usage × lead-time-days + safety stock; when inventory hits this, trigger the PO" are the **same formula in different units** (monthly×months ≡ daily×days) naming the **same trigger**. So min ≡ RP by the guide's teaching, and the view's `min_qty AS reorder_point` faithfully reflects that. The reorder LOOP closes (low→alert-hub→Find/Restock, ledger-safe); the ~10 consumers that read `qty ≤ reorder_point` (worker-drawer, voice-handler, ai-orchestrator, alert-hub, analytics) correctly trigger at min. Verdict: **keep as-is; the article is the spec and the tool matches it.** Article live-verified: renders clean, CTA "Open the Inventory" → `/workhive/inventory.html` (tool-aligned).

## NEXT (queue)
1. **Ext 3 — reorder loop:** decide reorder_point (drop alias vs real lead-time column); verify low→alert-hub→reorder→receive closes ledger-safe; parts-staging-recommender predictive tie-in.
2. **AI axis:** live-verify companion answers stock questions grounded via `v_inventory_items_truth` (WAT-split, counts from the truth view).
3. **A axis:** run the authed axe scan (`tools/axe_scan_live.js`) over inventory @390px for the full WCAG pass; file the shared nav-hub/companion sub-44px hits to mobile-maestro.
4. **Phase 6 re-deepwalk** + full `run_platform_checks` gate.
