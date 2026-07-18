# GRAFANA MAXIMIZATION — the sole-founder ops cockpit

**Created:** 2026-07-18 · **Owner:** Ian + Claude · **Status: PLAN (Night-Crawler-grounded; nothing built yet).**
**Origin (Ian, 2026-07-18):** *"use night crawler to understand my platform … then get outside sources on how to maximize the grafana because as a sole founder I want it to fully maximize and optimize."*

## Grounding
- **Platform (from our deepwalk):** WorkHive = multi-tenant ("hive") industrial-maintenance SaaS + marketplace + AI companion. Data lives in Postgres (`supabase_local`); edge-fn telemetry in `wh_traces`; usage in `analytics_events`; money in `marketplace_*`; AI spend in `ai_cost_log`. **Sole founder** = one pair of eyes, limited time, pays per AI token, can't watch 24/7.
- **What already exists (this arc):** `workhive-founder-ops` (19 panels) + `workhive-slo-arct` (golden signals) + 4 alert rules (SLO + 3 ops queues) + `grafana_reader` read-path (13 tables) + version-controlled provisioning. Auto-refresh of the 2 file-artifact panels is wired into the Stop hook.
- **External sources (Night-Crawler → `substrate/external/`):** `external-grafana-dashboard-best-practices.md` (USE/RED/Golden-Signals; *a dashboard answers ONE question*; template variables kill sprawl; hierarchical drill-down; alert on **symptoms not causes**; version-control JSON; browsing should be the exception). `external-grafana-alerting-fundamentals-notifications.md` (rules→contact-points→notification-policies via label routing; grouping; **silences + mute-timings** for evenings/weekends). `external-ux-dashboard-preattentive-attributes-kpi.md` (NN/g: **length + 2D position** for quantitative; **color for categorical**; **avoid area/angle** = pie charts + gauges for numbers; operational-vs-analytical split).

## The reframe (the one idea that changes everything)
A best-practice dashboard **answers one question and reduces cognitive load.** Today's 19-panel `founder-ops` is a *wall* — it mixes health + usage + revenue + marketplace + AI + moderation. For a founder's 10-second glance that's overload. The fix isn't more panels; it's a **hierarchy**: one **Home** that answers *"is my business healthy right now?"*, with **drill-downs** for each concern. Plus the thing a solo founder needs most: **alerts that actually reach his phone and stay quiet at night.**

---

## Phase G1 — ALERTS THAT REACH YOU (highest value; you're one person)
Right now alerts fire but route to a **localhost webhook** (a test receiver) — you'd never see them. This is the single biggest gap.
1. **Real contact point → your phone.** Wire a **Telegram bot** (free, instant, no server) or email as the Grafana contact point, replacing the `:9099` webhook. One alert → your pocket.
2. **Mute timings (evenings/weekends).** Add a mute timing so only **critical** (platform-down, error-budget-burning, **AI-cost-runaway**) pages you off-hours; everything else waits for morning. This is the anti-burnout lever the alerting docs call out.
3. **The founder-critical alerts** (symptoms, not causes): (a) **AI cost spike** — `ai_cost_log` daily spend > your $/day budget (you pay per token — a runaway prompt loop is a real money leak); (b) **platform error-budget burn** (already have the SLO alert ✓); (c) **action-queue backing up** (already ✓); (d) **a hive went silent** (no `analytics_events` from a hive in N days = churn signal); (e) **new hive signup** (growth — the good ping).
4. **Severity + grouping** so related alerts collapse into one notification (no alert storms).

## Phase G2 — ONE HOME DASHBOARD + DRILL-DOWNS (kills cognitive overload)
5. **"Founder Home"** — a NEW top dashboard, ~6 stat tiles answering *"is my business healthy?"*: platform-up (SLO), active workers (24h), **GMV / revenue**, **AI cost today vs budget**, open action-queue count, error-budget remaining. Colour = status (green/amber/red) only. This is your daily 10-second view.
6. **Drill-down dashboards** (each answers ONE question), linked from Home: **Growth** (usage/DAU/new-hives/power-users/heatmap), **Marketplace** (listings/sellers/disputes/GMV), **AI/LLM** (cost/tokens/latency/cache/RAG), **SLO/Health** (the Arc-T dashboard). The current 19-panel dashboard becomes these rows/dashboards — same panels, organised as a story.
7. **`$hive` template variable.** You're multi-tenant — add a `hive` dropdown that filters every panel, so you can inspect one plant/team without a separate dashboard. The docs' #1 anti-sprawl tool.
8. **Time comparison.** Enable week-over-week deltas on the Home tiles (is usage/revenue up or down vs last week?) — a founder watches trend, not absolute.

## Phase G3 — POLISH + FEATURES YOU'RE UNDERUSING
9. **NN/g viz fix:** the *AI cost by provider* **pie chart → bar chart** (length beats angle for quantitative); keep colour for the categorical provider, not the value. Same for any gauge showing a number.
10. **Annotations** — mark **deploys** on the timeline (a Grafana annotation on each `git push`/deploy) so you can see *"did my change cause this spike?"* at a glance. Correlation for free.
11. **Weekly digest** — a Sunday-night snapshot/export (or a Telegram summary from a tiny script over the same SQL) so you get a proactive "here's your week" without opening Grafana.
12. **Playlist** — rotate Home → Growth → SLO on a spare monitor/tablet (a passive founder wall).
13. **Loki (logs) datasource** *(bigger)* — add the edge-fn logs so a fired alert links to the actual error text, not just a count. Turns "something broke" into "here's why."

---

## What you're ALREADY doing right (per the sources)
Version-controlled dashboard JSON ✓ · golden-signals SLO dashboard ✓ · symptom-based alerting (error-budget, queue-depth) ✓ · read-only least-privilege datasource role ✓ · one provisioned source of truth (no browser editing) ✓.

## Recommended order
**G1 first** (alerts to your phone — you're solo, this is the point of observability), then **G2** (Home + drill-downs — makes daily use effortless), then **G3** (polish). Each is local + reversible; a real contact point (Telegram/email) + any prod Grafana host is your gate.

## NEXT
- Pick the contact-point channel (Telegram bot / email / Slack) — that's the one input I need to build G1.
- Then G1 → G2 → G3, live-MCP-verified each step; stay LOCAL; commit = Ian's gate.
