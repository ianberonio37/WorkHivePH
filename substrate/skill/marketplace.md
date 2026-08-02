---
name: skill-marketplace
type: skill
source: skill:marketplace
source_sha: 3a030467c9d88e0c
last_verified: 2026-07-13
supersedes: null
---
## skill · marketplace

Listings, payments, trust/safety, dispute resolution, and seller onboarding. Triggers on "marketplace", "listing", "offers", "auction", "Stripe", "seller", "buyer", "payment", "transaction".

**Sections:** Marketplace Agent · Your Responsibilities · How to Operate · Security Rules for Marketplace · Common Flows · Output Format · AI listing-assist — server OWNS the category whitelist; multimodal with a text fallback (2026-07-11) · Data-loss bug: a REQUIRED form field dropped on insert — validate the payload carries every validated field (2026-06-17, §13 P-fully sweep) · Arc K — FREE-platform reframe: PAYMENTS_ENABLED gates Stripe; the free flows are the real jobs (2026-06-22) — ★SUPERSEDED by full removal 2026-06-30 · ★ STRIPE REMOVED ENTIRELY — the flag is gone, not just off (2026-06-30) · Community reputation is a marketplace trust signal — the "Community-trusted" bridge (Community PDDA, 2026-07-11) · The browse-GRID trust chip was RLS-DEAD — a batch DEFINER RPC fixes + deepens it (2026-07-11) · A bridge that depends on a table the SEEDER never populates is DEAD ON RESET — seed the linking rows + any milestone badge the trigger would grant (2026-07-11) · Every inquiry insert must set `seller_name` itself — the truth view projects the BASE column, and the two inquiry paths must stay consistent (2026-07-11) · Inventory <-> Marketplace parts-flow bridge: `part_number` is the strong join key; provenance is base-only; the receive round-trip reuses inventory's ledger path (Marketplace PDDA X keystone, 2026-07-11) · Auto-learned (2026-07-23: CLASS TR — trust & credibility UX, buyer-facing) · Auto-learned (2026-07-24: the unbacked-trust-signal sweep + disclose gating BEFORE the effort) · Service-Hailing Arc lessons (2026-07-29, SERVICE_HAILING_ROADMAP.md) · Service-Hailing close-out: the gate-debt sweep (2026-07-29) · Service-Hailing Arc lessons (2026-07-29, SERVICE_HAILING_ROADMAP.md) · Service-Hailing Arc lessons (2026-07-29, SERVICE_HAILING_ROADMAP.md) · The EXPANSION pass: a green phase table over unmeasured axes (2026-07-29) · ★ Live end-to-end walks, 2026-08-01/02 — eight real defects the gates could not see · 1. A shared render target = last writer wins (seller could not see their own listings) · 2. `[hidden]` loses to any explicit `display` · 3. `opacity:0` hides from EYES only — not from keyboard or screen readers · 4. A truth view does NOT inherit new base columns · 5. Seed data healthier than the product hides real gaps · 6. The only path to transact was 699px below the fold · 7. A refusal must be reachable *and* true

(Deep source: `skill:marketplace` — retrieve this TOC to know WHICH section to read.)
