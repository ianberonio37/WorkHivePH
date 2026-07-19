---
name: skill-performance
type: skill
source: skill:performance
source_sha: 28d18ca0dced0f16
last_verified: 2026-07-13
supersedes: null
---
## skill · performance

Page speed, query optimization, caching, and Core Web Vitals. Triggers on "slow", "optimize", "speed", "cache", "Core Web Vitals", "performance", "loading", "lag".

**Sections:** Performance Agent · Your Responsibilities · How to Operate · This Platform's Performance Context · Core Web Vitals — live measurement lessons (2026-06-07) · CWV measurement HONESTY — traps an adversarial gate caught in the Arc-L L0 scorer (2026-06-22) · The `display:none → block` page reveal is a ~1.0 CLS bomb — ship the skeleton VISIBLE, hide on gate-fail (2026-06-22, Arc L L1) · CLS sources attribute to the element that MOVED, not the one that GREW — reserve the GROWER ABOVE them (2026-06-23, Arc L L1 in-place-render cluster) · Query-boundedness classification — what actually caps rows (2026-06-22) · L2 query-cap patterns — flipping filtered reads to bounded (2026-06-23) · Scorer architecture — preserve live-measured cells across a re-mine (2026-06-23) · Performance Checklist · Platform-Specific Script Loading Pattern (learned from production) · 0. CRITICAL: Moving supabase-js to end of body breaks pages that call supabase.createClient() at top level · 1. Check WHERE CDN scripts are loaded, not just whether they're deferred · 2. Flag sequential async init calls — always check the bottom of the script block · 3. `filter` animations require `will-change: filter` — not just `will-change: transform` · 4. Cache the entry being edited — do not re-fetch from DB in the save handler · 5. All Board Data Loads Must Be in Promise.allSettled — Including New Feature Panels · In-Memory Cache + reload Flag Pattern — Avoid Re-Fetching on Filter · Scaling Strategy — When and How to Scale WorkHive · The Scaling Ladder · Vertical vs. Horizontal — What They Mean for This Stack · 1. Indexes — Highest Leverage, Free · 2. Narrow Selects — Reduce Wire Payload · 3. Keyset Pagination — Stays Fast at Any Depth · 4. Supabase Realtime — Subscribe Selectively · 5. Analytics: Postgres Views and RPC Functions · 6. RLS Policy Complexity · Checklist Before Shipping Any New Table

(Deep source: `skill:performance` — retrieve this TOC to know WHICH section to read.)
