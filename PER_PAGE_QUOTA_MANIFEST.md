# Per-Page Quota Manifest — every production feature page (2026-07-05)

The complete per-page quota picture, pulled from live `pg_trigger` + edge-fn limiters. This is the
canonical reference for the 10k-user analysis and for extending the roadmap. All caps are LOCAL-verified;
migrations `20260705000000..000005` + the `_shared/rate-limit.ts` daily-AI change are **not yet deployed**
(Ian's commit/deploy gate). "hive/day · user/day" = per-hive and per-user rolling daily caps (Asia/Manila).

## Shared limiter definitions (referenced by the AI column)

| Limiter | Cap | Keyed on | Used for |
|---|---|---|---|
| **AI-hive** (`checkAIRateLimit`) | 50/hr + **300/day** per hive | verified `hive_id` | team AI features |
| **AI-user** (`checkUserRateLimit`) | 50/hr hive + 25/hr per user | `(hive, user)` | per-user cap inside hive |
| **AI-solo** (`checkSoloRateLimit`) | 30/hr + **100/day** per identity | `auth_uid` → IP floor | personal / anon-capable AI fns |
| **AI-route** (`checkRouteRateLimit`) | 50/hr per (hive, route) | `(hive, route)` | gateway per-route |
| **compute** | none (no LLM) | — | deterministic math/aggregation fns |

Uploads: logbook/inventory photo **≤700 KB** (client-compressed) · resume file **≤10 MB** · voice audio **≤60 s** · marketplace image **≤5 MB** · pdf-ingest **≤200 chunks + 20 jobs/day/hive**.

## Per-page quota table

| Page | Data write caps (hive/day · user/day) | Text caps | AI runs (fn → limiter) | Uploads |
|---|---|---|---|---|
| **logbook** | logbook 200·100 · pm_completions 500·200 · asset_nodes 200·100 · project_links 300·300 | problem/action/knowledge ≤2000, root_cause ≤200 | voice-logbook-entry→AI-hive · visual-defect-capture→AI-hive · equipment-label-ocr→AI-solo | photo ≤700 KB |
| **inventory** | inventory_items 500·200 · inventory_transactions 1000·400 · asset_nodes 200·100 | part_name ≤200, bin ≤200, notes/note ≤2000, job_ref ≤200 | equipment-label-ocr→AI-solo (scan) | photo ≤700 KB |
| **pm-scheduler** | pm_assets 200·80 · pm_scope_items 500·200 · pm_completions 500·200 · project_links 300·300 | asset_name ≤120, item_text ≤250, notes ≤2000 | — (writes only) | — |
| **asset-hub** | asset_nodes 200·100 · rcm_fmea_modes* · rcm_strategies* · parts_staged_reservations* | fmea/strategy text ≤500–2000 | ai-gateway · asset-brain-query→AI-hive · fmea-populator→AI-hive · pf-calculator/weibull-fitter→compute | — |
| **project-manager** | projects 100·40 · project_items 300·150 · project_links 300·300 · project_progress_logs 300·150 · project_change_orders 100·50 · project_roles* | name ≤200, description/notes/scope ≤2000 | project-orchestrator→AI-hive · project-progress→compute | — |
| **community** | community_posts 200·100 · community_replies 500·200 · community_reactions 500·300 | content ≤CHECK, emoji ≤16 | — | — |
| **marketplace** (+seller/admin) | marketplace_listings **20/day/hive** (baseline) · marketplace_watchlist 300·300 · inquiries* · sellers* · saved_searches* | title ≤120, description ≤2000, message ≤1000, certs ≤1000 | — | image ≤5 MB |
| **dayplanner** | schedule_items 300·300 | title ≤200, notes ≤2000 | — | — |
| **skillmatrix** | skill_exam_attempts 50·50 · skill_badges 50·50 · skill_profiles* | primary_skill ≤120 | — | — |
| **engineering-design** | engineering_calcs 200·80 | sow_text ≤4000, project_name ≤200, calc_type/discipline ≤100 | engineering-calc-agent→AI-solo · engineering-bom-sow→AI-solo | — |
| **resume** | resume_documents 50·20 · resume_versions 200·200 | title ≤200, note ≤1000 | resume-extract / resume-polish → AI-solo | file ≤10 MB/file |
| **voice-journal** | (writes via gateway) | — | ai-gateway→AI-hive+user+solo+route | audio ≤60 s |
| **shift-brain** | (edge writes) | — | analytics-orchestrator→AI-hive · shift-planner-orchestrator→AI-hive | — |
| **alert-hub** | alert_dismissals 500·200 · anomaly_signals (system) | alert_key ≤200 | analytics-orchestrator→AI-hive | — |
| **assistant** | ai_reply_feedback (baseline daily) | — | ai-gateway→AI-hive+user+solo+route | — |
| **ph-intelligence** | — (read) | — | intelligence-report→AI-user | — |
| **analytics** | — (read) | — | batch-risk-scoring→AI-hive | — |
| **index** (landing/home) | worker_profiles* · early_access_emails **20·20 (anon)** | display_name ≤120, email ≤254 | — | — |
| **hive** (dashboard) | hive_members/hives (admin) | — | ai-gateway · ai-orchestrator→AI-hive · benchmark-compute→compute | — |
| **report-sender** | report_contacts 100·50 | name ≤120, email ≤254 | — | — |

`*` = text-capped only (natural row-bound: config/profile/1-per-entity, not flood-prone).

## 10k-user analysis — what binds first

> **✅ GROUNDED 2026-07-05 (Step 0 — external limits WebSearch-verified + per-user footprint MEASURED on the live local DB).**
> This replaces the earlier UNVERIFIED block. The re-derivation **overturned the previous priority order**: blob-offload was
> #1 on an *assumption*; the measured photo attach-rate is **0%** and the real DB driver is **indexes + embeddings**, so
> **a global LLM guard is the true #1** and blob-offload demotes to a detector-guard. The CAPS/gates stand regardless
> (abuse-stops); this is the capacity STORY, now measured.

**Free-tier ceilings — VERIFIED against current provider docs (2026-07-05), not memory:**

| Provider | Verified free-tier limit (2026) | Note |
|---|---|---|
| **Supabase** | 500 MB DB · 1 GB Storage · **5 GB egress/mo** · 500K edge inv/mo · **200 concurrent realtime** · 50K MAU · 2 projects · pauses after 1 wk idle | egress was previously untracked — a real new ceiling |
| **Groq** | **30 RPM / 1,000 RPD** for good models (llama-3.3-70b = 1K RPD / 100K TPD); llama-3.1-8b-instant = 14,400 RPD / 500K TPD. **Limits are ORG-LEVEL (shared across ALL our users on one key), whichever limit hits first** | the old "9k/day" AND the "128/min" correction were BOTH wrong |
| **Cerebras** | 30 RPM (some models 5 RPM) · 60–100K TPM · **1M tokens/day** · context capped 8,192 | token-bucket refill; the `contextCap:8192` in ai-chain matches |
| **Gemini** | flash = **1,500 RPD / 10 RPM / 1M TPM**; 2.5-pro = 50 RPD | 2 flash models in chain |
| **Mistral** | **~1 B tokens/month** (token-based, no hard RPD) | the generous backstop of the chain |
| **OpenRouter :free** | 20 RPM · **50 RPD uncredited** (rises to 1,000 RPD/model with $10+ credit) | nearly useless at $0 credit — 6 models × 50 = 300/day |

**Chain aggregate (org-wide, shared):** if perfectly load-balanced, the 19-model / 5-provider chain yields **~10–30K quality LLM calls/day** — but two grounded caveats the old analysis missed: (1) it is **ORG-LEVEL shared**, so per-hive (300/day) + per-solo (100/day) caps do **NOT** protect the shared pool — only a **global** guard does; (2) the true wall is **per-MINUTE aggregate ≈ 100–150 RPM** (Groq 30 + Cerebras 5–30 + Gemini 10 + Mistral ~60 + OpenRouter 20), so a **synchronized burst** (7am shift-start) saturates every provider's minute-window at once and forces quality-decay down-chain.

**MEASURED per-user footprint (live local DB, `docker exec psql`, 2026-07-05):**

| Metric | Measured value | Implication |
|---|---|---|
| logbook all-in bytes/row | **4,491 B** (raw text only **104 B** — 16 MB / 3,705 rows) | **indexes dominate**, not text or photos |
| **photo attach-rate** | **0%** (0/3,705 logbook; inventory `photo` col = empty string) | blob-offload is **speculative** → demote to a detector-guard |
| voice_journal_entries | **45 MB / 11,701 rows @ 384-dim embedding** (~3.9 KB/row) | **embeddings are the silent DB driver** |
| all embedding tables (19) | **~62 MB allocated** (~12% of the 500 MB budget already) | retention MUST cover embedding tables, not just text |
| tenants (seed) | 3 hives · 15 members | seed scale; power-law modeled below |

| Resource | At 10k (power-law: ~15–20% DAU ≈ 1,500–2,000 active) | GROUNDED verdict |
|---|---|---|
| **LLM (org-shared)** | ~1,500–2,000 DAU × ~2 calls = **3–4K calls/day** competing for ONE org pool; synchronized peaks hit the ~100–150 RPM wall | **⛔ TRUE #1 BINDING CONSTRAINT.** Per-tenant caps don't protect an org-shared pool → needs a **global daily budget guard + per-minute burst smoother**. Binds at ~1–2K DAU, well before DB size. |
| **DB size (500 MB)** | driver = **indexes + embeddings** (4.5 KB/logbook row, 3.9 KB/voice-journal row); grows over months | **⛔ #2.** `enforce_blocking` cumulative row/MB quota (**Q1**) + **retention/archival covering embedding tables** hold the line. |
| **Realtime (200 concurrent)** | 2,000 DAU not all live at once, but 200 binds at moderate scale | **⚠ #3.** hard per-hive/session channel cap + graceful 429. |
| **Egress (5 GB/mo)** | 5 GB ÷ 10k = **500 KB/user/mo**; heavy dashboards can exceed | **⚠ NEW #4 watch** — previously untracked; add egress telemetry. |
| **Embeddings (multi-provider ~300M tok/mo)** | RAG-path embed calls + embedding DB size | **⚠ watch (not binding)** — CORRECTED 2026-07-06: Voyage 200M + Jina 100M tok/mo free, per-minute-limited (Jina 100 RPM), query-cached. NOT the "~8K/mo" over-pessimism. DB-size covered by Q5-b retention. |
| **Edge (500K/mo)** | 500K ÷ 10k = ~1.6/user/day | ✅ AI caps cover it. |

**RE-DERIVED conclusion (grounded, replaces the old "blob-offload #1"):**
1. **Global LLM budget guard + per-minute burst smoother (Q6, PROMOTED to #1)** — the org-shared pool + per-minute wall bind FIRST, and per-tenant caps can't hold a shared ceiling. This is now the top scale lever.
2. **Q1 flip (`enforce_blocking`) + retention/archival (Q5-b)** — DB size binds #2 via index+embedding accumulation; retention must include embedding tables.
3. **Realtime channel caps + graceful 429 (Q5)** — the 200-concurrent ceiling.
4. **Egress telemetry (NEW watch)** — 5 GB/mo egress. (Embedding-API is NOT binding: ~300M tok/mo multi-provider headroom, query-cached — the "~8K/mo" was corrected 2026-07-06.)
5. **Blob-offload photos (DEMOTED from #1 → detector-guard)** — 0% real attach-rate; build a lightweight "base64-in-row detector" that flags/blocks oversized inline images, and only build the full Storage-offload pipeline if attach-rate telemetry later shows photos actually landing.

Honest capacity (grounded): the binding constraint is **LLM (org-shared), not DB size or photos** — free-tier realistically serves **~1,500–2,500 daily-active users** (≈ the LLM burst wall) before quality decays down-chain; DB size follows within months without retention. A true 10,000 concurrent-active needs a paid Supabase tier + more LLM providers/credit. The caps make that migration point **predictable, not a surprise bill.**
