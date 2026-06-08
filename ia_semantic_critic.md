# IA Semantic Critic — reasoned consolidation/transfer/relabel proposals

> Gap-5 of BATTERY_INTELLIGENCE_GAPS.md. A free-tier LLM product-architect reasons over the
> grounded info-unit corpus. **Proposals, not actions** — engine proposes, owner disposes.
> Grounded on 84 real units. LLM returned 6 proposals; 6 grounded, 0 dropped (hallucinated).

## CONSOLIDATE — these N surfaces serve ONE job → one canonical home + deep-links.

### Unify pending approval counts  ·  _high confidence · Major_
- **Units:** `asset-hub:pending_approval`, `inventory:pending_approval`
- **Canonical home:** asset-hub.html
- **Why it confuses the user:** Technicians see two separate 'Pending approval' numbers and wonder if they refer to the same set of items.
- **Recommendation:** Create a single approvals dashboard; surface the combined count and provide filters for assets vs inventory.

## REMOVE — this duplicates another and adds no context (pure redundancy).

### Eliminate marketplace UI state tile  ·  _high confidence · Polish_
- **Units:** `marketplace:current_tab`
- **Canonical home:** n/a
- **Why it confuses the user:** The 'Current tab' tile shows UI navigation state, which adds no operational value and confuses users about its purpose.
- **Recommendation:** Delete this tile; UI should indicate active tab visually.

### Deduplicate marketplace listings view  ·  _high confidence · Minor_
- **Units:** `marketplace:listing_grid`
- **Canonical home:** n/a
- **Why it confuses the user:** Both 'Listings in view' and 'Marketplace listing grid' display the same set of listings, causing double counting.
- **Recommendation:** Keep one tile (e.g., 'Listings in view') and remove the duplicate grid tile.

## RELABEL — same word, different meaning across pages → disambiguate.

### Distinguish PM due vs task due  ·  _high confidence · Major_
- **Units:** `pm-scheduler:due_soon`, `dayplanner:week_count`
- **Canonical home:** n/a
- **Why it confuses the user:** Both tiles read 'Due this week', causing techs to mix up preventive maintenance jobs with daily tasks.
- **Recommendation:** Rename pm-scheduler:due_soon to 'PMs due this week' and dayplanner:week_count to 'Tasks due this week'.

### Clarify shift risk vs system alerts  ·  _medium confidence · Minor_
- **Units:** `shift-brain:top_risk_this_shift`, `alert-hub:high_severity_alerts`
- **Canonical home:** n/a
- **Why it confuses the user:** Both tiles use risk language; users may think a shift‑risk entry is the same as a high‑severity system alert.
- **Recommendation:** Rename shift-brain:top_risk_this_shift to 'Shift‑specific top risk' and keep alert-hub label as 'System high‑severity alerts'.

### Differentiate asset risk categories  ·  _medium confidence · Minor_
- **Units:** `asset-hub:critical_assets`, `predictive:hot_assets`
- **Canonical home:** n/a
- **Why it confuses the user:** Both show 'critical/hot' assets, leading supervisors to think they are the same list.
- **Recommendation:** Rename asset-hub:critical_assets to 'AMC‑flagged critical assets' and predictive:hot_assets to 'Forecasted hot assets'.
