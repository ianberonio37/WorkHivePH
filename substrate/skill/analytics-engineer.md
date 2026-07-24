---
name: skill-analytics-engineer
type: skill
source: skill:analytics-engineer
source_sha: 3b69a997226d2080
last_verified: 2026-07-13
supersedes: null
---
## skill · analytics-engineer

OEE dashboards, cross-hive reporting, maintenance analytics, data visualization with Recharts/Tremor, and KPI design. Triggers on "dashboard", "OEE", "analytics", "report", "chart", "KPI", "trend", "R

**Sections:** Analytics Engineer Agent · Your Responsibilities · How to Operate · This Platform's Analytics Context · Core KPIs to Implement (The Hive Framework) · Analytics Query Patterns (Supabase) · Dashboard Design by Stage · Chart Component Patterns (Recharts) · Performance Rules for Analytics Queries · Custom Composite Scores Must Be Labeled as Custom · RAG Dashboard Pattern — Red/Amber/Green Thresholds Must Be Documented · Role-Based Dashboard Views Are Essential for Field Workers · Output Format · Statistical Correlation — Zero-Variance Guard Required Before scipy Calls · PM Compliance — due_count Must Scale With Period Length · Monthly (30d) in 90-day period  → 3 due · Quarterly (90d) in 90-day period → 1 due · Plotly Charts — Tab Cache Pattern for Analytics Dashboards · Prescriptive Analytics — "All Green" Is a Data Problem, Not a Success · Same KPI, Two Surfaces — One Source (2026-05-20) · "Availability" is TWO different metrics — never conflate them in display or parity (2026-06-08) · A daily-snapshot KPI needs an on-demand RECOMPUTE companion (2026-06-08) · Analytics is a SOURCE OF TRUTH — verify it exhaustively, and know "redundancy" has two kinds (2026-06-08) · One page, ONE scope — audit every query's scope, not just the headline (2026-06-09) · Deep-link tiles must match the destination's roll-up GRANULARITY (2026-06-09) · The KPI Source Registry — one metric, one derivation, machine-enforced (2026-06-10, Phase 5) · DOM-parity (`__ANALYTICS_PARITY`) is NOT value-correctness — verify the ENGINE math against an independent standard oracle (2026-06-17, §13 analytics-correctness build) · Credit a read-aggregate page by proving its OWN aggregate() via the real page fn — not a live tile==DB render when the query is windowed/ordered (2026-06-17, ai-quality P-axis) · The cross-hive benchmark network (benchmark-compute → network_benchmarks) was SILENTLY EMPTY its whole life — and was NOT actually "external" (2026-06-17, ph-intelligence) · Dashboard render == canonical, per VALUE per PAGE — the V-axis proves one tile; a page renders many (2026-06-18, Arc C)

(Deep source: `skill:analytics-engineer` — retrieve this TOC to know WHICH section to read.)
