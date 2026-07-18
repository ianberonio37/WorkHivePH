# Marketplace Deep Arc (PDDA) — Page-Deep UFAI + "Best Marketplace" + Inventory-Connection

> **Arc kind:** *Page-depth* — the SAME refined PDDA method (Understand → Deepwalk → Ideate →
> Roadmap → Execute → Re-deepwalk) that took `engineering-design` ≈59%→~99%, Resume Builder
> ~52%→100%, Landing + Home ~52%→96.4%, the Analytics Engine → all-axes-clean, CMMS Integrations
> 25%→100%, the Hive Board (U-heavyweight), and **Community → TRUE 100%** (this program). The
> platform-wide breadth ruler scores every page *shallow*; this arc scores the **Marketplace
> surface deep** — a fine UFAI sub-dimension decomposition, grounded in reputable marketplace /
> trust-economy / circular-economy standards, driven LIVE via Playwright MCP, improved with skill +
> source ideas, ratcheted by gates.
>
> **Status: DRAFTED — awaiting fresh-window execution (Ian, 2026-07-11).** Ian: "the best
> marketplace… it seems disconnected to Inventory… extend the UI/UX we already have."

**Scope (surfaces, grounded):** `marketplace.html` (browse grid) · `marketplace-seller-profile.html`
(public seller) · `marketplace-seller.html` (seller's own listing management) · `marketplace-admin.html`
(moderation/trust-safety). Data: `marketplace_listings`, `marketplace_sellers`, `marketplace_inquiries`,
`marketplace_watchlist`, `marketplace_saved_searches`, `marketplace_reviews`, `marketplace_disputes`,
`marketplace_orders`. Contact-only, free (no payments) — a DELIBERATE constraint, not a gap.

---

## ★ THIS ARC HAS TWO HEAVYWEIGHTS (both refined from Ian's two sentences)

### Heavyweight 1 — X: Marketplace ↔ Inventory = ONE parts-flow fabric (Ian's keystone insight)

The disconnect is structural and total: `inventory_items` / `v_inventory_items_truth` (what a plant HAS
— qty_on_hand, reorder point, obsolete flags) and `marketplace_listings` (what's FOR SALE) are unlinked
islands — **exactly the state Community↔Marketplace was in before this program, and the same fix applies.**
The unlock is bidirectional + closes a loop:

- **Inventory → Marketplace (dead stock → supply).** A plant's surplus / obsolete / overstocked parts
  (`inventory_items` above reorder + slow-moving, or flagged obsolete) become **one-tap listable**
  ("Sell your surplus"). Pre-fill the listing from the inventory item (name, part number, category, qty,
  photo). Turns dead capital into value AND supplies other plants.
- **Marketplace → Inventory (shortage → reorder channel).** A **below-reorder** inventory item surfaces
  **"Find on the Marketplace"** → a listings search scoped to that part. The marketplace becomes a
  peer-to-peer reorder channel — often the ONLY source for a discontinued part.
- **The round-trip (close the loop).** A marketplace contact/receipt → optional **"Receive into inventory"**
  → writes `inventory_transactions`. Surplus at Plant A physically becomes stock at Plant B.
- **The identity join.** Part number / name / category. Add a `part_number`/category link between
  `marketplace_listings` and `inventory_items` (same pattern as the Community `auth_uid` identityJoin +
  the thread→listings keyword matcher already shipped).
- **★ The DEEPER value (why this makes it "the BEST marketplace," the thing Ian was reaching for):** the
  moat is NOT competing with Amazon/OEM on NEW parts — it is being the **only place to source
  DISCONTINUED / legacy / surplus industrial parts** (bearings, VFDs, boards, obsolete PLC modules). OEM
  lead times for legacy spares are weeks-to-never; but one plant's obsolete part is another's critical
  spare. A **network of Philippine plants sharing surplus = a circular economy for maintenance parts** —
  resilience + cost + uptime that no catalog offers. Inventory is the SUPPLY ENGINE of that network; the
  disconnect Ian feels is the marketplace running on empty because its natural supply (every plant's
  stockroom) isn't wired in.

### Heavyweight 2 — U: the "best marketplace" buyer + seller experience

What makes a marketplace genuinely great, refined for the industrial-maintenance buyer:
- **Trust — cold-start AND depth.** The Community-trusted bridge (shipped this program) already solves
  SELLER cold-start (a new seller with community standing isn't a stranger). Extend to depth: response
  time, completed-sales, KYB-verified, dispute history, "trades safely" signals — and a NEW-BUYER onramp
  (trust flows both ways).
- **Discovery — the hard problem.** Beyond search/filters (present): **"Parts for YOUR assets"** — match
  listings to the buyer's asset fleet / the parts their machines actually use (the marketplace analog of
  Community "my people" / expertise-driven discovery). **Saved-search ALERTS** ("ping me when an obsolete
  X is listed" — the killer feature for legacy-part hunters; extends the nav-hub unread-badge pattern).
  **Proximity** ("parts near you" — pickup vs ship).
- **Effortless listing (seller side).** One-tap from inventory (Heavyweight 1), **AI-assisted listing**
  (photo / part-number → category + description + price-range), photo upload. Low friction = more supply
  = a better marketplace for everyone.
- **The contact-only transaction, done frictionlessly.** Free + contact-only is deliberate. Make contact
  effortless (phone / Messenger / email inquiry — present), then a lightweight post-contact "did this
  work out?" → rating + optional inventory-receive. Never add fees; the UX is the product.
- **Belonging.** It should feel like a trusted trade network of plant peers, not a cold classifieds board.

---

## The scored axes (Marketplace sub-dimension decomposition)

| Axis | What it measures (Marketplace-specific) | Heavyweight? |
|---|---|---|
| **U — Marketplace UI/UX** | buyer + seller journeys; trust legibility (why trust this seller?); discovery (search/filter/"for-my-assets"/saved-search-alerts/proximity); effortless listing (1-tap-from-inventory, AI-assist, photo); ≤5-sec "what is this + what do I do"; grid/detail/seller-profile/inquiry arrangement + wording + clickables; new-buyer + new-seller onramp; extend (not patch) the existing surface. | ★★ (Ian) |
| **X — Marketplace ↔ Inventory** | surplus/obsolete inventory → 1-tap listing; below-reorder → "find on marketplace"; marketplace receipt → inventory_transactions round-trip; part-identity join; the circular-economy "list your dead stock / source legacy parts" loop. Baseline = **0 cross-refs** (to measure). | ★★ (Ian) |
| **F — Functionality** | post/edit/delete listing, contact/inquiry, saved searches, watchlist, reviews, disputes, seller profile, admin moderation — all end-to-end; counts accurate; realtime for new listings; search/filter reset. |  |
| **A — Adaptability/Accessibility** | axe=0 (grid/detail/seller/inquiry/admin modals); full keyboard; plant-floor mobile-first + safe-area; responsive both viewports; plain language; 4G grid rules; PH date/₱ formatting. |  |
| **I — Integrity / Trust & Safety** | seller KYB verification; listing moderation (admin); dispute resolution; spam/fraud prevention; cross-hive isolation (private inventory NEVER leaks — only *listed* parts are public); the trust badge can't be gamed (community_xp locked ✓); inquiry PII handling; the RLS-dead-read discipline (grid trust chip fixed this program). |  |
| **AI — Marketplace AI** | listing-assist (photo/part# → category/description/price); buyer-matching ("parts for your assets"); **price guidance GROUNDED in comparable real listings** (WAT split: LLM prose, code computes the comp — never a fabricated price); fraud/spam triage; the marketplace companion grounded on marketplace data (ops-snapshot pattern — the OPS_SNAPSHOT_AGENTS fix this program means factual marketplace Qs can ground). |  |

---

## The PDDA loop (6 phases — identical to the prior arcs)

1. **Understand** — map every surface (4 pages + subdirs), every table, every current cross-ref (X baseline
   = 0, measure it), the buyer + seller + admin journeys, file:line attach points.
2. **Deepwalk baseline (MEASURED LIVE)** — Playwright MCP as buyer / seller / admin / new-buyer personas
   (pabloaguilar/Lucena + a seed buyer), cross-checked at the DB (postgres MCP). Fill the scoreboard % per
   axis. **Deepwalk the WORKED state** (real listings, a real inquiry, a real dispute), not the empty page.
3. **Ideate** — fan-out relevant skills (marketplace, designer, mobile-maestro, security, multitenant,
   data-engineer, ai-engineer) + reputable sources (marketplace trust/UX, circular-economy for MRO parts)
   → cited improvement backlog per axis.
4. **Roadmap** — synthesize into the scoreboard (% per axis, owning skill, citation, locking gate).
5. **Execute** — keystone first (the Inventory bridge), then cheapest-first; LIVE-verify EACH slice; ratchet
   a measured-% board; forward-only gate in `run_platform_checks`; skill + memory writeback.
6. **Re-deepwalk** — re-run the persona walk; confirm every axis at its roadmap target, measured + gated.

**Done = every axis at its roadmap target, MEASURED + gate-locked** — not one headline metric (the
Hive-Board / Community lesson: a green F/A/I headline must not mask the two Ian-stated heavyweights U + X).

---

## What we already built that this arc EXTENDS (don't re-do; build on)

- **Community↔Marketplace bridge (this program):** portable reputation, Community-trusted grid/detail
  chips (grid RLS-dead read fixed via `get_marketplace_trust_badges`), person-card ↔ seller-profile
  cross-nav, knowledge→commerce category + thread→listings matcher, community-linked seller seeder.
- **Trust store locked:** `community_xp` BOLA closed → the trust badge is not mintable.
- **UI patterns to reuse/extend:** the clickable person-card + trust-chip; the nav-hub unread-badge
  (→ "new matching listing" alert badge); the seller-profile trust panel; the source-chip provenance.
- **AI grounding:** the ops-snapshot + PII-safe `page_context` pattern (Community) + the OPS_SNAPSHOT_AGENTS
  fix → the marketplace companion can ground factual answers the same way.

## NEXT (fresh-window execution starts here)

1. **Phase 0-1 (Understand):** mine the denominator — every marketplace surface × axis; measure X=0
   cross-refs to Inventory; locate the `inventory_items` ↔ `marketplace_listings` part-identity join point.
2. **Phase 2 (Deepwalk baseline):** live persona walk (buyer/seller/admin/new-buyer), DB-verified, fill
   the scoreboard %. Confirm the two heavyweights (U, X) are the two lowest, as thesis predicts.
3. **Phase 3-5:** keystone = the **Inventory↔Marketplace bridge** (1-tap-list-surplus + find-on-marketplace
   + receive-into-inventory + part-identity join + circular-economy framing), then the U "best-marketplace"
   discovery/trust/listing-assist slices, each LIVE-verified + gated.
Test identity: `pabloaguilar`/Lucena `b86f9ef6` (+ seed a buyer persona). Reuse the Community-arc harness.

---

## Phase 0-2 — MEASURED BASELINE (LIVE, 2026-07-11)

**Data denominator (postgres MCP, hive Lucena `b86f9ef6`):** marketplace_listings **28** (21 published /
5 sold / 2 draft) · marketplace_sellers **12** · inquiries / watchlist / saved_searches / reviews /
disputes / orders = **ALL 0** (empty worked-state — the LIVE walk must create it) · inventory_items **81**
(all approved: **72 surplus** qty>min, **9 below-reorder** qty≤min) · inventory_transactions 453.

**X-baseline = 0 — LIVE-confirmed on BOTH islands (Playwright MCP):**
- **Schema:** `marketplace_listings` has **no `part_number`, no `source_inventory_item_id`** (0 occurrences
  in migrations). Category taxonomies DIVERGE — inventory = material classes (electrical/chemicals/
  consumables/seals&gaskets/…), listings = equipment classes (compressors/VFDs/switchgear/generators/…);
  **only bearings/filters/instrumentation overlap** → the X-join must key on **part_number (strong) + name
  text**, never category equality.
- **marketplace.html grid + `sheet-detail` modal:** shows category/condition/location/age/description +
  trust chips — but **no part number, no "reorder / find in inventory / add to my inventory"**. (A seed
  listing's description literally says *"Community PDDA X-bridge demo"* — the intent was scouted, the bridge
  was never built.)
- **inventory.html:** `hasSellSurplus=false`, `hasFindOnMarketplace=false`, **surplus concept not even
  labelled** (`hasSurplusConcept=false`); the only "marketplace" token is the nav link. Reorder/min-qty
  concept **does** exist (`hasReorderConcept=true`) = the attach point for "Find on Marketplace".
- **marketplace-seller.html:** `hasListFromInventory=false`.

**Measured axis baseline (LIVE evidence — provisional %, gate-denominators set in Execute):**
| Axis | Baseline | Evidence (LIVE) |
|---|---|---|
| **X** | **~0%** ★ | zero bridge affordance on grid/detail/seller/inventory; no part identity; two unlinked islands. **Keystone.** |
| **U** | **~55%** ★ | STRONG base: grid, detail, contact (2 ways + Messenger), watchlist, saved-search, RFQ/quote, **Seller-Score 0/100 quality coach**, trust chips (tier/ID-Verified/Certified/Top-Rated/Community-trusted), ₱+PH location. GAPS: trust **depth not surfaced** (response_time_h/response_rate/dispute-history/KYB-date/completed-sales EXIST in `marketplace_sellers` but detail shows only badges + "No ratings/reviews yet"); no "Parts for YOUR assets"; no saved-search **ALERT** badge; internal-plumbing leak *"Saving updates 7 pages across the platform"* on the Post sheet. |
| **F** | **~80%** | listings CRUD, inquiries (wired, 0 rows), Analytics tab, watchlist, saved searches, RFQ, admin moderation queue (Approve/Reject), disputes tab, seller verification + admin-reviewed certifications. TO VERIFY LIVE: inquiry insert; saved-search alert firing. |
| **A** | **?** | UNMEASURED — axe scan pending (grid/detail/seller/admin/modals), keyboard, mobile/safe-area. marketplace 0 console errors; inventory 1 console warning (unchecked). |
| **I** | **~75%** | insert `WITH CHECK seller_name IN auth_worker_names()` → **seller-spoof closed**; listings read = `published OR own OR admin`; inventory read = **hive-members-only** (private, no cross-hive leak); admin moderation + cert review + verification; 2 platform admins. TO VERIFY: cross-hive isolation live; **"escrow" jargon** (orders/disputes carry `escrow_release_at`/`buyer_confirmed_at` — contradicts contact-only/free + plain-language rule IF surfaced). |
| **AI** | **~30%** | Seller-Score quality coach present. MISSING: grounded **price guidance** (comparable listings, WAT-split), **buyer-matching** (parts-for-assets), marketplace companion grounding (ops-snapshot pattern). |

→ **Thesis CONFIRMED: X (~0) and U (~55) are the two lowest axes.** Keystone = the Inventory↔Marketplace bridge.

**Keystone attach points (CONFIRMED, ready to build):**
- **DB:** `ALTER marketplace_listings ADD part_number text, source_inventory_item_id text` (informational
  same-hive provenance to `inventory_items.id`). Reorder-match **DEFINER RPC** mirroring
  `get_marketplace_trust_badges` (`SECURITY DEFINER, SET search_path='', STABLE, GRANT anon+authenticated`):
  given part_number/name → published listings.
- **inventory.html (per-row):** surplus (qty>min) → **"Sell surplus"** → opens Post-listing **pre-filled**
  (name→title, part_number, category-mapped, qty, photo); below-reorder (qty≤min) → **"Find on Marketplace"**
  → scoped listings search.
- **`sheet-detail`:** surface `part_number` when present; **"Receive into inventory"** → writes
  `inventory_transactions` (`item_id, type='receipt', qty_change, qty_after, note='Received via Marketplace:
  <title>', job_ref=<listing id>`).
- **marketplace-seller.html Post:** "List from inventory" picker.
- **Isolation invariant:** the bridge copies SELLER-CHOSEN fields into a listing the seller explicitly
  publishes; it NEVER exposes `inventory_items` to marketplace readers (RLS blocks the join regardless).
  Only `published` listings are public; private inventory never leaks.

NEXT: (a) background Understand+Ideate workflow `wf_ac4c8bc5-e3a` → merge its static map + cited backlog;
(b) build the keystone DB migration + inventory-side affordances; (c) create worked-state via LIVE walk
(real inquiry/watchlist/saved-search) so re-deepwalk measures the WORKED page.

---

## EXECUTE PROGRESS (2026-07-11) — keystone + security + founder-console fusion

**F bug (found via LIVE deepwalk, fixed+gated):** the direct Contact-Seller inquiry insert omitted
`seller_name` → the seller dashboard filters `v_marketplace_inquiries_truth` by seller_name → the primary
buyer→seller path was a silent BLACK-HOLE. Fixed (stash seller on `#inq-listing-id.dataset.seller`),
backfill migration `20260711000007`, gate `inquiry_insert_sets_seller_name`. LIVE-verified.

**X KEYSTONE — Inventory↔Marketplace parts-flow fabric BUILT + LIVE-VERIFIED (0 → working loop):**
- Schema `20260712000000`: `marketplace_listings.part_number` (public, on truth view) +
  `source_inventory_item_id` (TEXT FK to inventory_items.id, base-only). Part# is the strong join key
  (inventory=material vs listing=equipment taxonomies diverge; only bearings/filters/instrumentation overlap).
- **Sell** (inventory surplus/above-reorder rows → prefilled Post writing part#+source id) ✓
- **Find on Marketplace** (below-reorder rows → `?section=parts&q=<part#>`, buyer search extended to
  `part_number.ilike`) ✓ — proven: `q=FLT-AIR` resolves the listing via part_number, not title.
- **Receive into inventory** (listing detail → `inventory.html?receive=1` → reuses inventory's OWN
  Restock/Add ledger-consistent path; matched→Restock, new→Add prefilled) ✓
- Taxonomy fix: added `Filters` to `CATS['parts']` (listings existed with it but it was unfilterable).
- Gated: `partsflow_bridge_schema` + `partsflow_bridge_ui`.

**I — two trust-poisoning holes LIVE-EXPLOITED then FIXED + re-verified (migration `20260712000001`):**
1. `marketplace_reviews` RLS was OFF + anon INSERT → anyone injected fake `verified_purchase=true`
   reviews that the rating trigger recomputes. Fixed: RLS on, public SELECT, INSERT forbids non-admin
   self-claimed verified_purchase; anon SELECT-only. `update_seller_rating`/`_tier` made SECURITY DEFINER
   so the reviewer-triggered sellers-upsert isn't RLS-blocked.
2. `marketplace_sellers` self-grant BOLA — a seller self-UPDATE set kyb_verified/tier/rating/sales.
   Fixed: `guard_marketplace_seller_trust_columns` BEFORE trigger blocks non-admin self-UPGRADE of
   verification/tier/rating/sales (allows self-downgrade; exempts admins + service-role + the recompute
   triggers via a txn-local GUC). Verified with a NON-ADMIN simulated session: self-grant → 42501,
   legit edits ok. Gated: `reviews_rls_locked` + `seller_trust_guard`. validate_marketplace = **14/14**.

**FOUNDER-CONSOLE FUSION (Ian, 2026-07-11: "sole founder → one page to manage"):** fused marketplace-admin
moderation INLINE into `founder-console.html` (Marketplace moderation section: listings Approve/Reject,
seller Verify ID/certs, disputes — event-delegated, XSS-safe, same is_marketplace_admin authority) +
a "Founder tools" launcher to every non-production surface (marketplace-admin full, llm-obs, agentic-rag,
validator-catalog, architecture, symbol-gallery, status, promo-poster). marketplace.html Admin link →
`founder-console.html#sec-mkt-mod`. axe=0, admin-gates 2/2. marketplace-admin.html kept as the deep view
(≈20 validators scan it) not deleted.

### Continuation (same session) — U + AI heavyweights BUILT, I-sweep complete (validate_marketplace 9→18)

**U (Ian heavyweight #2) — BUILT + LIVE-VERIFIED:**
- **Trust DEPTH** on listing detail: "Responds in ~Xh · Y% reply rate · Z sales" (data already on
  `v_marketplace_sellers_truth`; response_rate is a FRACTION → ×100) + the **#part-number chip** in Details.
- **"Parts for YOUR assets"** discovery rail (grid) — `get_marketplace_parts_for_my_assets(hive_id)` DEFINER
  RPC, active-membership-guarded, joins published listings to the viewer hive's inventory by part_number.
  Verified: Lucena sees a cross-hive BRG-6313 listing it stocks. Gate `parts_for_assets_guarded`.
- **Saved-search ALERTS** — `get_saved_search_matches()` self-scoped RPC (auth_worker_names, no IDOR) →
  badge on the Searches button + per-search "N new" pill; **Apply marks-seen** (last_sent_at=now) so the
  badge clears. Verified E2E. Gate `saved_search_alerts_selfscoped`.

**AI — grounded price-comps BUILT:** `get_marketplace_price_comps(cat,cond,part#)` DEFINER RPC (min/median/
max/n) → Post-sheet hint shows the band only when n>=3, else honest note / nothing (WAT split, never
fabricated). Verified (Bearings n=4 band; Lubricants n=0 hidden). Gate `price_comps_grounded`.

**I-axis sweep COMPLETE — 4 real holes fixed + LIVE-exploited-then-verified, 2 false-positives dismissed:**
1. reviews RLS-off (anon fake verified reviews) — `20260712000001`, gate `reviews_rls_locked`.
2. seller self-grant BOLA (kyb/tier/rating) — guard trigger, gate `seller_trust_guard`.
3. storage anon-DELETE (photo vandalism) + anon-upload — `20260712000002`, gate `storage_delete_owner_scoped`.
4. rate-limit NULL-hive bypass — `20260712000004` (cap by seller_name).
   FALSE POSITIVES (verified, no fix): handleReply/handleCloseInquiry "IDOR" (RLS scopes it by
   buyer/seller/admin); "Saving updates 7 pages" (intentional impact-preview component, not a leak).

**Migrations added:** 20260711000007, 20260712000000–000006 (8). **validate_marketplace = 18/18, axe = 0.**

**AI companion grounding — client wired, but LIVE still CONFABULATES (honest RED, server-side fix needed):**
marketplace.html now calls `WHAssistant.setContext({key:'marketplace', summary:<counts>, piiSafe:true})` with
a retry-until-WHAssistant-ready guard (companion-launcher loads after the page IIFE). BUT a live probe shows
the companion answers "27 parts published" when the truth is **11** (parts_all=17, all_published=23,
all_listings=29 — 27 matches NOTHING = confabulation). So the client `page_context` is NOT reaching/steering
the LLM. The real fix is server-side: the gateway/ops-snapshot (OPS_SNAPSHOT_AGENTS pattern in
`ai-gateway/index.ts` + `_shared/companion_source_registry.json`) must feed a correct marketplace snapshot,
or page_context must be honored. NOT gated (evidence discipline: don't gate a confabulating answer green).

**TRUE remaining backlog:** (1) marketplace companion grounding server-side fix (above — the one open RED);
(2) AI listing-assist (photo/part#→category/desc auto-fill); (3) F flows full E2E (watchlist/RFQ/dispute-
creation live); (4) A full keyboard/mobile sweep on the new affordances. All local at Ian's commit gate.

## ✅ TRUE-remaining-backlog CLEARED (2026-07-11, fresh window) — arc at roadmap target

1. **Companion marketplace grounding (RED→GREEN, verified live).** Root: `_shared/companion_source_registry.json`
   marked all marketplace views `out_of_scope`. Fix: flipped `v_marketplace_listings_truth` to
   `served_on_demand` (marketplace match keywords + a count engine) and added a composite `count_where`
   `eq:[field,value]` predicate to BOTH engine copies in lockstep (`ai-gateway/index.ts buildFromRegistry`
   + `tools/companion_fabrication_sweep.py _run_engine_spec`). Live edge fn now answers "9 published
   listings / 5 parts" (was confabulating "27"); `mkt` fabrication family 0.0%. Also triaged an untriaged
   `v_community_reputation_truth` → coverage gate PASS; grader self-test 74/74. Reseed-proofed the grader
   harness (hardcoded hive_id 403'd every probe). Memory `reference_companion_marketplace_grounding`.
2. **AI listing-assist BUILT + verified live + gated.** New `supabase/functions/marketplace-listing-assist`
   edge fn: server-owned `SERVER_CATS` whitelist (WAT guard — AI picks a category ONLY from the real
   taxonomy), no-invention description, multimodal (photo data-URL) with text fallback, membership +
   rate-limit gates. Post-form "✨ AI assist" button (44px, aria-label, keyboard-reachable). Live: "Honeywell
   pressure transmitter 4-20mA" → category auto-set Instrumentation + accurate description, 0 console errors,
   cross-hive → 403. `validate_marketplace` 18→**19/19** (new `ai_listing_assist` check gates the SERVER_CATS↔CATS
   sync). Registered in config.toml + deploy-functions.ps1. Memory `reference_marketplace_ai_listing_assist`.
3. **F flows E2E — watchlist ✅ + RFQ ✅ live-verified with DB persistence.** Watchlist: UI click → real
   `marketplace_watchlist` row (Pablo→Honeywell). RFQ: Compare 2 listings → Send All → 2 real
   `marketplace_inquiries` rows (Leonardo + Ricardo, status pending, seller_name correctly set = the
   inquiry-black-hole fix holding). **Dispute-creation = by-design N/A finding:** `marketplace_disputes` is
   `order_id`-scoped and marketplace.html has NO dispute-creation UI; Stripe/orders were removed entirely
   (free, contact-only), so a buyer dispute has no on-platform order to raise. The dispute *moderation* UI in
   founder-console is order-era vestigial. **SYNTHESIS (fork, Ian's call, non-blocking):** either (a) remove
   the vestigial dispute moderation UI, or (b) re-scope disputes to `inquiry_id` so a buyer CAN dispute a bad
   off-platform deal (makes the moderation UI live again). Default lean = (a) out-of-scope like off-platform payment.
4. **A keyboard/mobile sweep ✅.** AI-assist affordance: native `<button>` (Enter/Space activate), 44px touch
   target, aria-label, focusable; at 430px mobile — visible, within viewport, NO horizontal overflow; 0 console errors.

**Arc status:** the two heavyweights (X, U) + I-sweep + AI (companion + listing-assist) + F (watchlist/RFQ) + A
are all at roadmap target, measured live + gated. All LOCAL/uncommitted at Ian's commit gate.
**PROGRAM NEXT (per NEXT_ARCS_ROADMAP §6):** Stream 2 — **Arc R (Security red-team)** at `build R0`.
