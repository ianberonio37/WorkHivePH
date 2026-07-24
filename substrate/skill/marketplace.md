---
name: skill-marketplace
type: skill
source: skill:marketplace
source_sha: 25b2313d4664d77e
last_verified: 2026-07-13
supersedes: null
---
## skill · marketplace

Listings, payments, trust/safety, dispute resolution, and seller onboarding. Triggers on "marketplace", "listing", "offers", "auction", "Stripe", "seller", "buyer", "payment", "transaction".

**Sections:** Marketplace Agent · Your Responsibilities · How to Operate · Security Rules for Marketplace · Common Flows · Output Format · AI listing-assist — server OWNS the category whitelist; multimodal with a text fallback (2026-07-11) · Data-loss bug: a REQUIRED form field dropped on insert — validate the payload carries every validated field (2026-06-17, §13 P-fully sweep) · Arc K — FREE-platform reframe: PAYMENTS_ENABLED gates Stripe; the free flows are the real jobs (2026-06-22) — ★SUPERSEDED by full removal 2026-06-30 · ★ STRIPE REMOVED ENTIRELY — the flag is gone, not just off (2026-06-30) · Community reputation is a marketplace trust signal — the "Community-trusted" bridge (Community PDDA, 2026-07-11) · The browse-GRID trust chip was RLS-DEAD — a batch DEFINER RPC fixes + deepens it (2026-07-11) · A bridge that depends on a table the SEEDER never populates is DEAD ON RESET — seed the linking rows + any milestone badge the trigger would grant (2026-07-11) · Every inquiry insert must set `seller_name` itself — the truth view projects the BASE column, and the two inquiry paths must stay consistent (2026-07-11) · Inventory <-> Marketplace parts-flow bridge: `part_number` is the strong join key; provenance is base-only; the receive round-trip reuses inventory's ledger path (Marketplace PDDA X keystone, 2026-07-11) · Auto-learned (2026-07-23: CLASS TR — trust & credibility UX, buyer-facing)

(Deep source: `skill:marketplace` — retrieve this TOC to know WHICH section to read.)
