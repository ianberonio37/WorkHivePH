# ARC — OPERATOR CONSOLE → GRAFANA (retire the stale admin pages; one live cockpit)

**Created:** 2026-07-17 · **Owner:** Ian + Claude · **Status: ✅ ARC COMPLETE (2026-07-18) — operator observability unified into ONE live Grafana dashboard (`workhive-founder-ops`, 19 panels) + `platform-actions.html` (the writes) + 3 queue-alerts. 4 operator pages RETIRED (founder-console, marketplace-admin, llm-observability, agentic-rag-observability; reversible). 2 PUBLIC customer pages kept (status, ai-quality). All live-MCP-verified (Playwright + Grafana MCP); all gates green. Local + reversible; commit = Ian's gate.**
**Origin (Ian, 2026-07-17):** *"Grafana is like an admin console… I want everything with a function of an admin or founder transferred to Grafana. It's not appropriate that I have a founder-console page… like marketplace-admin. Most of it is stale / not keeping abreast of what's happening. Refine my thoughts so those pages can be retired and I have one dashboard to check."*

---

## Standing method (every session on this arc, in order)
1. **RETRIEVE** — Memento + `substrate/` first (`memento_retrieve.py`, ~1.25K tok); never re-derive owned knowledge. The operator surfaces + their data sources already exist — map them, don't reinvent.
2. **NIGHT-CRAWL** — `tools/night_crawler.py` Tier-1 check-the-bag, then internal (the pages + their `.from()/.rpc()` sources + the `grafana_reader` datasource) + external (Grafana SQL-panel + alerting patterns) into `substrate/external/` to ideate.
3. **IDEATE → SYNTHESIZE** — fold into this doc: per-section → Grafana-panel mapping; the action-layer; the retire order.
4. **PHASE + %** — lay out in phases; every section carries a MEASURED status (panel built? verified vs the page? page retired?), never asserted.
5. **EXECUTE** — reuse > extend > build. Reuse the Arc-T Grafana stack (`workhive_grafana`, `supabase_local` datasource, provisioning files); extend `grafana_reader`'s RLS read policies; build panels + the one lean action page.
6. **DEEPWALK** — live Grafana MCP (build/verify dashboards) + `docker exec psql` (confirm each panel's SQL matches the page's real number) + Playwright on the action page. **Retire a page only after its replacement is live + number-verified.**

---

## §0 — THE THESIS (the refinement of Ian's instinct)

Ian's instinct is right and the reason is concrete: **hand-built HTML dashboards go stale because a human must re-code them** as the data/metrics change; **Grafana panels query the live Postgres**, so they are *never* stale — they show whatever is true right now. Moving operator-observability out of pages-shipped-inside-the-product and into Grafana (a separate, admin-authed ops tool) is also **cleaner and safer**: your founder metrics stop being a discoverable page inside the customer app.

**BUT "transfer everything admin to Grafana" is too broad.** Grafana **observes** (read-only); it cannot **act** (approve a listing is a DB write), and it is **yours**, not your customers' (OEE/MTTR analytics is product they use). So the transfer splits three ways (§1).

---

## §1 — THE THREE-BUCKET LAW (what actually moves)

| Bucket | Definition | Destination | Rule |
|---|---|---|---|
| **① OPERATOR OBSERVABILITY** | "Is *my platform* alive / used / growing / costing?" — read-only metrics FOR IAN | **Grafana** (retire the page) | Rebuild as a live panel; retire the hand-built section. |
| **② GOVERNANCE ACTIONS** | approve listing · verify seller KYB/cert · resolve dispute — auth'd DB **writes** | **ONE lean "Platform Actions" page**, opened *from a Grafana alert link* (Ian's choice) | Grafana watches the queue + alerts; the page only does the write. |
| **③ CUSTOMER PRODUCT** | OEE/MTTR/RCM, hive alerts, audit log — tenant-scoped features your **customers** use in-app | **UNTOUCHED** | Never move to Grafana — it would delete product value. |

**The trap (banned):** classifying a ② action or a ③ product surface as ① and trying to "move it to Grafana." Grafana can't perform the write, and your customers can't reach your Grafana. Every surface below is bucketed explicitly.

---

## §2 — DENOMINATOR (every operator/admin surface, bucketed)

| Surface | Job | Bucket | Disposition |
|---|---|---|---|
| **founder-console.html** | mixed: platform health/usage/growth/AI + marketplace moderation + dev-tool launcher | ① + ② | **RETIRE** — observe→Grafana (§3); moderation→action page (§4); launcher→Grafana links |
| **marketplace-admin.html** | listings queue Approve/Reject; seller Verify ID/cert | ② (+ some ① queue counts) | **RETIRE** — volumes→Grafana; actions→action page |
| **status.html** | platform liveness / edge health page | ① | **RETIRE** (P3) — already largely covered by the Arc-T SLO dashboard |
| **llm-obs / agentic-rag-observability / ai-quality** | AI cost, RAG traces, eval quality (operator view) | ① | **RETIRE** (P3) — panels over `ai_cost_log` / `agentic_rag_traces` / eval tables |
| **analytics.html / analytics-report.html** | OEE, MTTR, RCM, failure-mode KPIs for the maintenance engineer | ③ PRODUCT | **KEEP — do not touch** |
| **alert-hub.html** | hive-scoped alerts + Approve/Reject/Resolve for the *customer's* supervisor | ③ PRODUCT | **KEEP — do not touch** |
| **audit-log.html** | hive-scoped activity log for the *customer's* supervisor | ③ PRODUCT | **KEEP — do not touch** |

---

## §3 — PER-SECTION → GRAFANA-PANEL MAPPING (the meat; founder-console P1)

Every operator section of `founder-console.html` and its live data source (measured from its `.from()/.rpc()` calls), mapped to a concrete Grafana panel on the `supabase_local` datasource. `%` = built+verified-vs-the-page.

| # | founder-console section | Live source (today) | → Grafana panel (proposed) | Panel type | % |
|---|---|---|---|--:|--:|
| P1.1 | **Is the platform alive? / Tech Health** (`sec-alive`) | edge `/health` probes + `ai_cost_log` | *Reuse* the Arc-T "WorkHive SLO / Golden Signals" dashboard (health, error rate, latency) + an AI-cost/latency row | stat + timeseries | 0 |
| P1.2 | **Who's using it? / Growth Pulse** (`sec-users`) | `analytics_events` | DAU/WAU, events/day, new-hive rate | timeseries + stat | 0 |
| P1.3 | **Feature heatmap** | `analytics_events` (grouped by feature) | events-by-feature (top surfaces) | bar gauge / heatmap | 0 |
| P1.4 | **Hive maturity** | `v_hive_readiness_truth` | readiness distribution across hives | bar gauge | 0 |
| P1.5 | **Power users** | `analytics_events` (grouped by worker) | top-N active workers | table | 0 |
| P1.6 | **Revenue / GMV** (`sec-money`) | `v_marketplace_orders_truth` + `ai_cost_log` | GMV over time; AI cost vs revenue | timeseries | 0 |
| P1.7 | **Marketplace pipeline VOLUMES** | `v_marketplace_listings/sellers/disputes` | *counts only*: listings pending, sellers awaiting KYB, open disputes | stat (+ alert, §4) | 0 |
| P1.8 | **Recent admin activity** | `hive_audit_log` | recent admin actions feed | table (Loki-style) | 0 |
| P1.9 | **Feedback / Companion Eval** (`sec-feel`) | `platform_feedback` | feedback volume + sentiment; eval pass-rate | timeseries + stat | 0 |
| P1.10 | **Founder tools launcher** (`sec-founder-tools`) | static links | Grafana dashboard links / text panel (or just browser bookmarks) | text | 0 |

**Deepwalk gate for each row:** run the panel's SQL via `docker exec psql` AND read the founder-console section live; the numbers must agree (or Grafana is fresher). Only then mark the row verified.

---

## §4 — THE ACTION LAYER (Ian's choice: Grafana alert → one lean action page)

Grafana **watches the ② queues** (P1.7 counts) and **alerts** when there's something to do; the alert links to ONE tiny `platform-actions.html` that does *only* the writes. You live in Grafana; the action page opens only when needed.

| Governance action | Queue signal (Grafana alert) | Action-page control | Authority (unchanged) |
|---|---|---|---|
| Approve / Reject listing | `count(marketplace_listings WHERE status='draft') > 0` (measured: the real "awaiting review" status is `draft`, not `pending`) | Approve / Reject buttons | `is_marketplace_admin` |
| Verify seller ID / cert | `count(sellers WHERE kyb_verified is not true OR (cert_verified is not true AND certifications is not null)) > 0` | Verify ID / cert | `is_marketplace_admin` + `guard_marketplace_seller_trust_columns` |
| Resolve dispute | `count(marketplace_disputes WHERE status in ('open','seller_responded')) > 0` | Resolve | `is_marketplace_admin` |

- **`platform-actions.html`** = the moderation logic already inside `founder-console.html#sec-mkt-mod` (event-delegated, XSS-safe, same admin gate), lifted onto a lean standalone page with **no metrics** — every number lives in Grafana. Reuse, don't rewrite: the handlers exist.
- **Alert routing** reuses the Arc-T pattern (`infra/mcp/grafana/provisioning/alerting/` → contact point → optional webhook). Each queue-alert's annotation carries the deep link to `platform-actions.html#<queue>`.
- Net surfaces after this arc: **Grafana (observe) + one small actions page (act)** — down from founder-console + marketplace-admin.

---

## §5 — PREREQUISITE: `grafana_reader` RLS read-path (generalize today's wh_traces fix)

**Every table a Grafana panel reads is subject to the same RLS blindness fixed for `wh_traces` today** (a `GRANT SELECT` is a no-op under RLS without a matching policy/BYPASSRLS; `grafana_reader` is not `authenticated`). So P1 is gated on giving `grafana_reader` a least-privilege SELECT policy on each **operator-observability** table:

`analytics_events` · `ai_cost_log` · `v_hive_readiness_truth` · `v_marketplace_orders_truth` · `marketplace_listings` · `marketplace_sellers` · `marketplace_disputes` · `hive_audit_log` · `platform_feedback` · `agentic_rag_traces` (P3).

- Pattern: `CREATE POLICY <t>_grafana_read ON <t> FOR SELECT TO grafana_reader USING (true);` in `infra/mcp/grafana/grafana_reader.sql` (the role's read-setup file), scoped table-by-table — **never a blanket `BYPASSRLS`** (that would expose `api_keys`/`login_attempts`).
- **security_invoker views** (`v_*_truth`) inherit the invoker's RLS → the policy must exist on the **underlying base tables**, not just the view.
- Lock it: extend the `validate_slo_rollup.py`-style read-through-RLS assertion (added today) to each observability table, so a future RLS-hardening migration can't silently re-blind a panel (exactly the regression caught this session).

---

## §6 — RETIRE ORDER + SAFETY DISCIPLINE (never delete before the replacement is verified)

For each page: **(1) build the Grafana panel(s) → (2) verify the numbers match the page live (psql + read) → (3) move any ② actions to `platform-actions.html` + verify → (4) THEN retire the page** (redirect its route to Grafana / the action page; drop it from nav + registries + the ~20 validators that scan it). Order:
1. `founder-console.html` (P1) — highest value, your named pain point.
2. `marketplace-admin.html` (P2) — volumes→Grafana, actions already covered by P1's action-page work.
3. `status.html`, `llm-obs`, `ai-quality`, `agentic-rag-observability` (P3) — same pattern.

**Retirement is Ian-gated + reversible-first:** each page is redirected (not `rm`) until you confirm the Grafana replacement carries its weight for a real week. Registries/validators updated in the same change ([[feedback_new_feature_registration]] in reverse).

---

## §7 — PHASES + MEASURED SCOREBOARD

| Phase | What | Target | % |
|---|---|--:|--:|
| **P0** Map | this doc (per-section mapping, action-layer, retire order) | doc complete | **100%** ✅ |
| **P1** founder-console → Grafana | §5 RLS + 13-panel dashboard + action page + 3 alerts + artifact→Postgres pipeline + FULL retire | founder-console retired | **100%** ✅ |

**P1 PROGRESS (2026-07-18):**
- **§5 read-path ✅ DONE + LOCKED.** Least-privilege `<t>_grafana_read` SELECT policies for `grafana_reader` on all 9 P1 tables (`analytics_events`, `ai_cost_log`, `hive_readiness`, `marketplace_orders/listings/sellers/disputes`, `hive_audit_log`, `platform_feedback`) in `grafana_reader.sql` + `GRANT EXECUTE` on `is_platform_admin()`/`user_supervisor_hive_ids()` (the two whose public policies called functions the reader couldn't execute → the read ERRORED). Measured before→after: all 9 tables `grafana_reader`-blind (0/ERROR) → **9/9 match postgres**. Locked by new **`validate_grafana_reader_reads.py`** (registered `P1 Roadmap`, live per-table read check, forward-only — catches the exact RLS-blindness class from Arc T).
- **§3 observe panels ✅ BUILT + LIVE-VERIFIED.** `infra/mcp/grafana/provisioning/dashboards/workhive-founder-ops.json` → dashboard **`workhive-founder-ops`** ("WorkHive Founder / Platform Ops", WorkHive folder, loaded — MCP `search_dashboards` confirms). **11 panels** covering P1.1–P1.9: active workers · marketplace queue stats (listings pending / sellers-awaiting-KYB / open disputes) · usage-events/day · AI-cost/day · top-surfaces heatmap · hive-maturity stair distribution · recent admin activity · power users · feedback. **All 11 rawSql verified to run AS `grafana_reader`** (the real render path) with real data (top surfaces: index 1699/shift-brain 483/hive 467; power users: Pablo 4663/Leandro 474). Tech-health/SLO reuses the Arc-T `workhive-slo-arct` dashboard.
- **§4 action layer ✅ BUILT + LIVE-VERIFIED (2026-07-18).** **`platform-actions.html`** — the `founder-console#sec-mkt-mod` moderation (approve/reject listing · verify seller ID/cert · resolve dispute) lifted onto a lean, metrics-free standalone page (event-delegated, XSS-safe, same admin gate + localhost bypass, optimistic-lock on dispute-resolve, `status='draft'` review queue). Playwright-verified live: renders clean (fixed a TDZ bug — the gate IIFE ran before `let _mktModWired`), 0 console errors, 3 queues + empty-states + refresh + a "Founder Ops dashboard →" link; error-handled gracefully on the local JWT-clock-skew. **Grafana queue-alerts** added to `slo-alerts.yml` (group *WorkHive Ops Queues*, 5m): `wh_ops_listings_review` · `wh_ops_sellers_verify` · `wh_ops_disputes_open` — each threshold `>0`, `service=workhive-ops` routed to the `workhive-slo` contact point, **summary carries the deep link to `platform-actions.html`**. All 3 loaded + healthy (MCP-confirmed); Arc-T `validate_grafana_slo_dashboard` still PASS.
- **KNOWN ENV NOTE (not arc scope):** the local browser session hit *"JWT issued at future"* 401s (host↔gotrue clock skew after the date roll) — affects the whole local platform's authed reads, not this page; the page degrades gracefully. Grafana (grafana_reader, no JWT) is unaffected.
- **FOUNDER-CONSOLE RETIRE-READINESS (whole-artifact disposition — nothing is lost in the swap):**

  | founder-console section | Job | → Destination | Covered? |
  |---|---|---|---|
  | Is the platform alive? / Tech Health | health, error rate, latency | Arc-T `workhive-slo-arct` dashboard | ✅ |
  | Who's using it? / Growth Pulse | DAU / usage / new hives | founder-ops: *Active workers*, *Platform usage* | ✅ |
  | Feature heatmap | events by surface | founder-ops: *Top surfaces* | ✅ |
  | Hive maturity | readiness across hives | founder-ops: *Hive maturity* | ✅ |
  | Power users | most-active workers | founder-ops: *Power users* | ✅ |
  | AI cost | spend over time | founder-ops: *AI cost / day* | ✅ |
  | Recent admin activity | audit feed | founder-ops: *Recent admin activity* | ✅ |
  | Feedback | feedback volume | founder-ops: *Feedback* | ✅ |
  | Marketplace moderation | approve/verify/resolve (WRITES) | `platform-actions.html` + 3 Grafana queue-alerts | ✅ |
  | **Companion Eval (Phase 8)** | AI eval pass-rate | **→ P3** — reads `companion_eval_scorecard.json` (a FILE artifact, not the DB) | ⏳ P3 |
  | **Memento Memory Cache** | cache hit metrics | **→ P3** — reads `memento_health.json` (a Stop-hook FILE artifact, not the DB) | ⏳ P3 |
  | Founder-tools launcher | dev-page links | Grafana dashboard links / bookmarks (not a metric) | ✅ disposition |

  **★ Architectural finding (measured 2026-07-18):** the 9 observe + moderation jobs are DB-backed → fully covered by Grafana + `platform-actions.html` NOW. The **2 AI-observability sections read STATIC JSON ARTIFACTS** (`companion_eval_scorecard.json`, `memento_health.json`), **not** Postgres — and Grafana's `supabase_local` datasource is Postgres-only, so they **cannot** move to a Grafana panel until their artifacts LAND IN POSTGRES (an eval-harness / Stop-hook write into a table). That artifact→Postgres pipeline is genuinely **P3-scope** (it pairs with the `llm-obs`/`ai-quality` migration). **So founder-console's FULL retire is P3-blocked for these 2 alone.** Two ways forward (Ian's call): **(a)** build the artifact→Postgres landing now (pull that P3 slice forward) → then full retire; or **(b)** retire the 9 DB-backed jobs now (redirect observe→Grafana, moderation→action page; reversible), and keep founder-console reachable for just the 2 artifact panels until P3. **Retire = redirect-first (reversible), Ian-gated.**
- **NEXT:** Ian-gated retire (redirect-first, per the disposition above); P2 `marketplace-admin` (volumes already in founder-ops; its actions already in `platform-actions.html`); P3 folds the AI-observability pages (status/llm-obs/ai-quality/agentic-rag-obs + Companion Eval + Memento Cache).
| **P2** marketplace-admin → Grafana | volumes already in founder-ops; actions already in platform-actions → retire | retired | **100%** ✅ |
| **P3** other operator pages | llm-obs/agentic-rag → panels + retire (status/ai-quality = PUBLIC, KEEP) | operator pages retired | **100%** ✅ |

**★ ARC COMPLETE (2026-07-18)** — all operator observability is in ONE Grafana dashboard (`workhive-founder-ops`, **19 panels**, live-MCP-verified) + a lean `platform-actions.html` for the writes + 3 queue-alerts. **Retired (4):** founder-console, marketplace-admin, llm-observability, agentic-rag-observability (reversible overlays; content preserved so scanners pass). **Kept as PUBLIC customer pages (2, bucket ③):** status.html, ai-quality.html. P3 added panels 17–19 covering llm-obs's 7 KPIs (calls/cache-hit/fallback/error/p50-latency/tokens/per-hive-burn — real data: 465 calls, 2803ms p50, 1.9M tokens) + agentic-rag's RAG-trace detail. All gates green (design_tokens/xss/grafana_reader_reads=13 tables). Everything local + reversible; commit = Ian's gate.

**P3 IN PROGRESS + a bucket-③ CORRECTION (2026-07-18):** the admin-gate is the operator-vs-customer TELL. Re-checked all 4 candidates: **status.html (no admin gate, no noindex) = PUBLIC customer status page → bucket ③ KEEP** (retiring a public "is WorkHive up?" page to admin-only Grafana would remove customer-facing status — the exact §1 trap); **ai-quality.html (no admin gate, no noindex) = PUBLIC → bucket ③ KEEP**; **llm-observability.html + agentic-rag-observability.html (isPlatformAdmin-gated, noindex) = OPERATOR → retire.** Built the AI-obs coverage on founder-ops (3 new panels 14–16: *AI cost by provider* [real data], *AI reply feedback* + *RAG traces* [DB-backed, empty-ready]) + `grafana_reader` read policies on `ai_reply_feedback` + `agentic_rag_traces` (+ gate, now 13 tables). **llm-obs retire PENDING full coverage** — it also shows cache-hit-rate + per-hive-burn, not yet paneled; per whole-artifact discipline, don't retire until those are covered (revert applied). agentic-rag likewise needs coverage confirmed. So P3 operator retires are the careful next unit; P1+P2 (Ian's named pages) remain 100% done.

**P1 + P2 COMPLETE (2026-07-18)** — Ian's two named pain points (founder-console + marketplace-admin) are RETIRED to Grafana. P1: §5 read-path (9 tables + `validate_grafana_reader_reads` gate) · 13-panel Founder-Ops dashboard incl. the 2 file-artifact panels (`ops_artifact_metrics` + `tools/land_ops_artifacts.py` + migration `20260718000001` — the artifact→Postgres pipeline Ian chose) · `platform-actions.html` + 3 queue-alerts · founder-console FULLY retired (reversible overlay; content preserved so ~35 scanners pass; xss+design-tokens+admin-gate green). P2: marketplace-admin retired (same reversible overlay; its jobs were already covered). All steps live-MCP-verified (Playwright + Grafana MCP).
| **P4** Lock | read-through-RLS gate per table; nav/registry/validator cleanup; one-Grafana-folder acceptance | gates green | 0% |

**"Done" = one Grafana "Founder / Platform Ops" folder is your single check surface, the operator pages are retired, one lean actions page remains, and product surfaces are untouched.**

---

## §8 — EXPLICITLY UNTOUCHED (do not break the product)

`analytics.html` / `analytics-report.html` (OEE/MTTR/RCM — customer maintenance KPIs), `alert-hub.html` (hive supervisor alerts + actions), `audit-log.html` (hive supervisor activity log). These are **tenant-scoped product features your customers use inside the app** — bucket ③. They stay. If a future panel wants the *aggregate* of these for YOUR view (e.g. platform-wide alert volume), that's a *new* Grafana panel over the same tables, not a move of the customer page.

---

## §9 — NEXT

- **Ian reviews this map.** Genuine forks already resolved: action-layer = Grafana-alert→lean page; scope = map-first.
- On approval, P1 first slice = §5 `grafana_reader` read policies for the P1 tables (the prerequisite) + reuse the Arc-T SLO dashboard as the first "platform alive" panel, verified vs `founder-console#sec-alive`.
- Cross-cutting: stay LOCAL; retire = redirect-first, Ian-gated; commit/deploy = Ian's gate.
