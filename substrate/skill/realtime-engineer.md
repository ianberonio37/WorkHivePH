---
name: skill-realtime-engineer
type: skill
source: skill:realtime-engineer
source_sha: 446ecee7ef183a64
last_verified: 2026-07-13
supersedes: null
---
## skill · realtime-engineer

Real-time data, WebSockets, Supabase Realtime, live dashboards, and event streaming. Triggers on "real-time", "live", "WebSocket", "Supabase Realtime", "streaming", "live updates", "push data", "event

**Sections:** Real-time Engineer Agent · Your Responsibilities · How to Operate · This Platform's Real-time Context · Subscription Isolation — SECURITY (Arc J, 2026-06-21) ⚠️ · Supabase Realtime Pattern (Stage 2) · Connection Reliability Pattern · Real-time Features by Stage · Output Format · Community Page Lessons (May 2026) · 1. Realtime publication is per-table opt-in — listeners are silently dead otherwise · 2. Default REPLICA IDENTITY = PK only — DELETE filters on non-PK columns silently drop every event · 3. Realtime UPDATE filters apply to the NEW row — transitions away are missed · 4. Cross-hive realtime needs a separate, no-hive-scope channel · 6. Query-first feeds get a tap-to-refresh BADGE, never an auto-prepend (D3.2, 2026-06-29) · Live-verifying a feed without a second browser (D3.2, 2026-06-29) · 7. Subscribe to the TABLE behind a VIEW; pick the filter key carefully (D3.3, 2026-06-29) · 8. Suppress the echo of the local device's own write (D3.3, 2026-06-29) · 5. Optimistic UI on multi-list pages must sync ALL relevant lists · 9. A batch-computed snapshot on a DETAIL page is silently stale — subscribe its source on the page's EXISTING channel (D4, 2026-06-29) · Auto-learned (2026-07-23: offline post-queue + optimistic render dedup by client id, not server id)

(Deep source: `skill:realtime-engineer` — retrieve this TOC to know WHICH section to read.)
