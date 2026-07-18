# GRAFANA MAXIMIZATION — the sole-founder ops cockpit

**Created:** 2026-07-18 · **Owner:** Ian + Claude · **Status: BUILDING — G1–G4 shipped LOCALLY, live-MCP-verified. Channel = EMAIL. Commit/deploy = Ian's gate.**
**Origin (Ian, 2026-07-18):** *"use night crawler to understand my platform … then get outside sources on how to maximize the grafana because as a sole founder I want it to fully maximize and optimize."* → then *"let's build now, I use email then build the rest let's complete it, what are the other observabilities we need to add?"*

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

## Phase G4 — THE OTHER OBSERVABILITIES (Ian: *"what are the other observabilities we need to add?"*)
The founder-ops board watched the *product* (usage, revenue, AI). It was **blind to the infrastructure keeping the product alive.** G4 adds the operational golden signals a sole founder can't watch by hand. Priority = *how silently it fails* × *how bad the failure is.*

**✅ BUILT + LIVE-VERIFIED this session:**
- **G4.1 Cron-job health** *(the standout — biggest silent risk)*. 16 pg_cron jobs run the platform's automation (PM-overdue, risk-scoring, AI-eval, digests). A failing job was **totally silent** — the first probe found **27+ failed runs in 7 days** (batch-risk-scoring 6, pm-overdue 6, ai-eval 4…). pg_cron restricts run history to the job owner, so the fix is the postgres-owned view **`public.v_cron_health`** (migration `20260718000002`) that `grafana_reader` can read. Surfaced on **Founder Home** (a "Cron jobs failed (24h)" stat + a "Recent cron failures (7d)" table) + alert **`wh_founder_cron_failed`** (any failure in 24h → email).
- **G4.2 DB & Security Health** — new drill-down `workhive-db-health` (linked from Home). **Infra:** connections vs 100-cap (saturation = silent outage), DB size, cache-hit ratio, deadlocks. **Performance:** slowest queries from `pg_stat_statements` (found a `WITH pgrst_source` at 145 calls/2.09 min total + our own worker-count panel at 787 ms — real tuning targets). **Security:** failed-login sum + locked-out identifiers + a suspicious-identifier table (from the `login_attempts` rate-limiter). Grant = **`pg_monitor`** (standard read-only stats role) + RLS read policies on the auth tables. Alerts: **`wh_founder_db_connections`** (>80/100) + **`wh_founder_failed_login_surge`** (>25 fails/15m → brute-force signal).
- **G4.4 Storage usage** — postgres-owned aggregate view **`public.v_storage_health`** (migration `20260718000003`) over RLS-scoped `storage.objects` (counts/bytes per bucket, no per-object paths). Added to the DB-health board: "Object storage used" stat (151 kB) + "Storage by bucket" table (`tts-cache` 5/150 kB, `marketplace-listings` 1/759 B). Billed usage — the value is watching the trend over time.
- **G4.5 Growth / funnel** — new drill-down `workhive-growth` (linked from Home). Hive-lifecycle **funnel barchart** (Signed up 3 → Onboarded 3 → Activated 2 → Active 7d 2 → Active 24h 2 — the gap between bars = the leak), **onboarding-completion %** (intent/persona set), new-hives-30d, active-hives-7d, DAU-proxy, + a "Top product actions" table (`resume_*` events, page_view excluded). Reads existing `hives` + `analytics_events` (hive-joined to avoid the orphan-hive_id quirk). Live-verified.
- **Hardening (found by the live walk):** the datasource silently 400'd ("password authentication failed") — a 3-way `grafana_reader` password drift (`.env.mcp` vs stale container env vs role), and re-running `grafana_reader.sql` for grants **re-clobbered** the role password to the placeholder. Fixed both: aligned all three to the `.env.mcp` secret + made `grafana_reader.sql`'s re-run branch never reset the password. Added a **datasource-health assertion** to `validate_grafana_reader_reads.py` (the per-table reads use `127.0.0.1 trust` and are blind to password mismatch; the health check exercises the real scram path) — it now fails loudly instead of shipping dark panels.

**📋 RECOMMENDED NEXT (ranked; each local + buildable):**
| # | Observability | Why a solo founder needs it | Source / build sketch | Priority |
|---|---|---|---|---|
| G4.5 | **Business funnel / conversion** | signup → onboarded → active → (paid). The founder metric — where users drop off. | Funnel panel over `hives` + `analytics_events` milestones (bar/state-timeline) on a "Growth" drill-down; week-over-week deltas (ties into G2 #8). | **MED-HIGH** |
| G4.3 | **App error tracking (GlitchTip)** ⚠️ *needs a scope decision* | Exceptions the SLO's `wh_traces` count can't explain — stack trace + release. | **NOT a quick add:** the 5-container GlitchTip stack is **stopped (OOM-exited 137, 5wk ago)** AND **no `SENTRY_DSN` is wired** — nothing reports to it, so it'd render empty. Real build = start the (memory-heavy) stack + wire DSNs across edge-fn prod code + new datasource + panels. A lighter alternative: enrich the error view from `wh_traces` (data we already have). | **HIGH value, but forked** |
| G4.4b | **DB-size growth over time** | Point-in-time size is shown; the *trend* needs history. | A tiny table snapshotting `pg_database_size` + storage bytes daily (a cron or the Stop hook) → a time-series panel. | **MED** |
| G4.6 | **Realtime / subscription health** | If Supabase Realtime silently drops, live pages go stale with no error. | Connection/channel counts (realtime schema or a probe) → stat + alert on 0 active when expected. | **LOW-MED** |
| G4.7 | **Backup / PITR freshness** | A backup that silently stopped is only discovered when you need it. | Assert last-backup timestamp is recent (local: WAL/pg_dump freshness) → "hours since last backup" stat + alert. | **MED** (prod-weighted) |

**Verdict / opinion:** the two biggest *silent-failure* blind spots (cron + infra/DB) are now covered with real signal. Next-best is **G4.5 (funnel)** — the founder-growth lens, and it reads data we already have (`hives` + `analytics_events`). **G4.3 (GlitchTip)** is the highest *potential* value but is a genuine fork: it needs the OOM-prone stack started + DSNs wired into prod code, and would be empty until then — worth doing as its own arc, or replacing with a lighter `wh_traces`-based error view. Recommend: **G4.5 next, then a scope call on G4.3 vs the wh_traces-lite alternative.**

---

## What you're ALREADY doing right (per the sources)
Version-controlled dashboard JSON ✓ · golden-signals SLO dashboard ✓ · symptom-based alerting (error-budget, queue-depth) ✓ · read-only least-privilege datasource role ✓ · one provisioned source of truth (no browser editing) ✓.

## Build ledger (what shipped this session)
- **G1 ✅** EMAIL contact point (`wh_slo_email` → ian.beronio37@gmail.com) on the `workhive-slo` contact point; SMTP via `GF_SMTP_*` → local **Mailpit** (`supabase_inbucket_workhive:1025`, view at :54324), SMTP path proven end-to-end. Mute-timing `off-hours` (00:00–08:00 + 21:00–24:00 + weekends) on the ops route; founder route NOT muted. Founder-critical alerts: AI-cost-runaway, new-signup, hive-churn.
- **G2 ✅** `workhive-founder-home` — 6 status tiles + `$hive` template variable + drill-down links (Ops, SLO, DB-health, Platform Actions). Live-verified: errors 5, workers 3, events 872, queue 5, hives 3.
- **G3 ✅ (partial)** AI-cost-by-provider **pie → bar** (founder-ops panel 14). Remaining G3: annotations (#10), weekly digest (#11), playlist (#12), Loki (#13).
- **G4 ✅** cron-health (G4.1) + DB & Security Health (G4.2) + storage (G4.4) + Growth/funnel (G4.5). **10 alert rules** total, **5 dashboards** (Home, Ops, SLO, DB-health, Growth), read-path gate green across **19 tables** + datasource-health. Durable views (`v_cron_health`, `v_storage_health`) in migrations `20260718000002/3`.

## Recommended order (remaining)
Highest-value silent-failure observabilities (cron, DB/infra, storage) + the growth lens are DONE. Remaining are forked or lower-local-value: **G4.3 GlitchTip** (fork — start the OOM stack + wire prod DSNs, or a `wh_traces`-lite view), **G3** polish (annotations → weekly email digest → Loki), **G4.4b** DB-size-over-time snapshot, **G4.6/G4.7** realtime/backup (prod-weighted). Each local + reversible; a prod Grafana host + a real SMTP provider (override `GF_SMTP_*`) are your gate.

## NEXT
- **G4.3 scope decision (fork — needs Ian):** GlitchTip is stopped (OOM) + no DSN wired → standing it up = start heavy containers on the running machine + wire DSNs across edge-fn prod code, and it renders empty until then. Options: (a) full GlitchTip arc, (b) a lighter `wh_traces`-based error-detail view, (c) defer. **Ian's call — it changes WHAT gets built.**
- Non-forked next units: **G4.4b** DB-size snapshot table + daily writer + trend panel; **G3** weekly EMAIL digest (script over the same SQL → Mailpit/SMTP); **G4.6** realtime probe.
- Every step live-MCP-verified (Playwright full-render + Grafana MCP); stay LOCAL; **commit = Ian's gate.**
