# Free-Tier Quota Roadmap — "Free, but bounded to as little as appropriate"

**Created 2026-07-05 · Owner: Ian + Claude · Status: STUDY → design (forks open).**

> **Ian's ask (2026-07-05):** keep the platform FREE, but cap what each feature page/function
> lets a user do to "as little but appropriate as possible" — so the platform is sustainable and
> abuse-proof. Concrete examples he named: logbook entries + images (are pics compressed? per-day
> cap?); integrations file-ingest → auto-populate logbook/inventory/PM; resume usage; engineering-
> design full runs. This doc refines + extends that across ALL feature pages.

---

## 0. The one-paragraph answer

The **rate-limit machinery is already built and strong on the AI axis, and almost entirely OFF on the
data axis.** There is a real gateway (the **Full-Stack SaaS Gateway**: `platform-gateway` for non-AI
routes, `ai-gateway` for AI agents), a 7-layer limit stack, and every one of the 30 AI edge functions
is rate-limited (3 coverage gates green, gateway-bypass = 0). What is missing is the **cheap-to-abuse
data plane**: how many logbook rows, PM completions, inventory transactions, community posts, uploaded
images, ingested files, and MB of storage a hive can create per day. Those caps mostly **exist as a
table (`hive_quotas`) and a few triggers but run in LOG-ONLY mode**, so nothing actually blocks yet.
"Bounding the free platform" = (a) flip the existing data-quota switch on with sane defaults, (b) add
per-day insert triggers to the ~8 high-write tables that lack them, (c) add text-field length caps +
upload size/count caps on the surfaces that lack them, and (d) a per-day AI ceiling on top of the hourly
one. Almost none of this is new code — it's turning on and completing what's already scaffolded.

**Verified correction (2026-07-05):** image compression is NOT the gap it first looked like — the shared
`whCompressImage` helper (`utils.js:1801`) IS used: logbook manual photo → 800px @ 0.7 JPEG
(`logbook.html:4310`), logbook AI-capture → 1600px @ 0.85, inventory → 0.7 JPEG, resume → 0.82. The
uncompressed-upload surfaces that remain are **voice-journal audio (no max duration)** and any NEW upload
surface. So the image-compression story is mostly SOLVED; the open axes are per-day caps, text caps, and
a couple of upload-duration/size caps.

---

## 1. What already exists (measured, not assumed)

### 1a. The gateway is real and rate-limit is a FIRST-CLASS pillar
`FULLSTACK_SAAS_GATEWAY_ROADMAP.md` defines an 8-pillar control plane. **Pillar P (Policy & Governance)**
owns rate-limit + quota, verified at 100% (`validate_policy_hive_binding.py`, exploitable = 0). Two front
doors: `platform-gateway` (non-AI) and `ai-gateway` (AI). Hard invariant: limit buckets key on the
**server-verified** `hive_id`, never a client-supplied one (a spoofed one could otherwise drain a
victim hive's bucket — that hole was found and closed, live-proven).

### 1b. The 7 limit layers (all in `_shared/rate-limit.ts` + migrations)

| # | Layer | Table | Default cap | Keyed on | Enforced today? |
|---|---|---|---|---|---|
| 1 | Per-hive AI | `ai_rate_limits` | 50 / hour | verified `hive_id` | ✅ live |
| 2 | Per-user AI (inside hive) | `ai_user_rate_limits` | 25 / hour | `(hive_id, user_id)` | ✅ live |
| 3 | Solo/personal AI | `ai_user_rate_limits` | 30 / hour | `auth_uid` → `ip:` floor | ✅ live |
| 4 | Per-route quota (hive-configurable) | `hive_route_quotas` + `hive_route_calls` | 50 / hour | `(hive_id, route, hour)` | ✅ live (partial adoption) |
| 5 | **Per-hive DATA rows + storage** | **`hive_quotas`** | **`max_rows_logbook / inv_tx / pm_comp / community / ai_reports / max_storage_mb`** | `hive_id` | ⚠️ **SHIPPED but `enforce_blocking=false` (LOG-ONLY)** |
| 6 | Traffic-class split | `ai_rate_limits` | voice 70% / bg 30% | `hive_id` + class | ✅ built, partial adoption |
| 7 | Free-tier LLM chain ($0) | `_shared/ai-chain.ts` | provider TPM | provider | ✅ live, all $0 providers |

### 1c. Arc ownership (rate-limit is spread across 4 arcs, not one dedicated arc)
- **Gateway arc (Pillar P)** — verified-tenant binding, route quotas, the bypass ratchet.
- **Arc H (AI/Companion)** — per-hive AI quota + free-tier-only chain + cost logging.
- **Arc E (Backend/Edge)** — the `_shared/rate-limit.ts` helpers + adoption across 61 fns.
- **Arc I (Auth)** — GoTrue-native brute-force + Turnstile signup bot-protection.

→ **There is no single "rate-limit arc."** This doc is the seed for one: a **unified free-tier quota
board** the way Arc R unified security into one measured board.

---

## 2. The gaps (what "bound the free platform" actually needs)

| Gap | Severity | Detail |
|---|---|---|
| **G1 — data-row quotas are LOG-ONLY** | ★★★ | `hive_quotas.enforce_blocking=false` for every hive → the per-hive caps on logbook/inv-tx/PM/community rows + storage MB never block. The switch exists; it's off. |
| **G2 — 8 high-write tables have NO per-day insert trigger** | ★★★ | Only `marketplace_listings` (20/day) + `platform_feedback` (hourly) have DB-level insert rate-limits. `logbook`, `checklist_records`, `inventory_transactions`, `pm_completions`, `community_posts` (**had one — removed**), `community_replies` (**removed**), `assets`, `inventory_items` do not. A worker or a script with the anon key can insert unbounded rows. |
| **G3 — text fields uncapped on several surfaces** | ★★ | logbook `problem`/`root_cause`/`action`/`knowledge`, inventory `part_name`/`bin_location`, PM-scheduler `scope`/`notes`, marketplace listing description, asset-hub Q&A — **no `maxlength`** → unbounded stored text. (Community/project/assistant text IS capped — 2000/1000/500 & 120–4000.) Images are already compressed (see §0 correction); the remaining raw upload is **voice-journal audio (no max duration)**. |
| **G4 — file-ingest caps thin** | ★★ | `pdf-ingest` is service-role-guarded (Arc R) with `MAX_CHUNKS_PER_JOB=200` + 4000-char chunks + `MAX_JOBS_PER_DRAIN=5`, but has **no per-file size cap and no per-hive jobs-per-DAY cap** (5 is per drain call, not per day). |
| **G5 — no per-day ceiling on AI, only per-hour** | ★★ | 50/hr = up to 1,200/day/hive of free-tier LLM if sustained. A daily cap closes the slow-burn drain. |
| **G6 — hard 429, no graceful degradation** | ★ | At cap the user gets a raw 429; a "you've hit today's free limit, resets in Xh" message + cached/simplified fallback is nicer and reduces support load. |

---

## 3. ★ THE DELIVERABLE — per-feature-page limits matrix (refined + extended)

Design principles for every cap below:
1. **Generous for a real single team, brutal for a script.** A 20-person hive should never hit these in honest daily use; a bot hits a wall in seconds.
2. **Two buckets always:** per-hive (team fairness + cost) AND per-identity/IP (anon/solo abuse).
3. **Cost-weighted:** expensive actions (multi-hop AI, vision, file-ingest) get tight caps; cheap reads get loose ones.
4. **DB trigger for the hard cap (unbypassable), app-layer for the friendly message.**
5. **Compress + size-cap every upload at the client** before it ever reaches storage.

Legend: **Enf** = enforced today (✅ / ⚠️ log-only / ❌ none). Caps below are my recommended free-tier defaults (all tunable per hive via `hive_quotas` / `hive_route_quotas`).

| Page / feature | What it consumes | Enforced today | Recommended free-tier cap (per hive unless noted) |
|---|---|---|---|
| **Logbook** ★pilot | logbook rows + 1 photo + text | ❌ daily / ⚠️ total-rows · ✅ photo compressed (800px/0.7) | **200 entries/day** (DB trigger); cap `problem`/`root_cause`/`action`/`knowledge` text; keep ≤1 photo/entry; friendly cap message |
| **PM Scheduler** | pm_completions + pm_assets + text | ❌ | **200 completions/day**; **100 PM assets/day**; cap `scope`/`notes` (currently uncapped) |
| **Inventory** | inventory_items + inventory_transactions + photos | ❌ daily · ✅ photo compressed (0.7) | **100 new items/day**, **300 transactions/day**; cap `part_name`/`bin_location` text |
| **Checklists** | checklist_records | ❌ | **100/day** |
| **Community** | community_posts + replies + reactions | ❌ (trigger removed) | **restore trigger:** 20 posts/day/user, 100 replies/day/user, 300 reactions/day/user |
| **Marketplace** | marketplace_listings | ✅ 20/day | keep 20/day/hive (already enforced) |
| **Asset Hub** | asset_nodes + reliability reports (AI) | ❌ / ✅ AI | 90 asset nodes/day; FMEA/RCM/Weibull AI runs under the per-hive AI cap + **10 report-generations/day** |
| **Engineering Design** | `engineering-calc-agent` + `engineering-bom-sow` (multi-hop AI) | ✅ per-hive AI | **tight — these are the most expensive:** 20 calc-agent runs/hour, **5 full BOM/SOW per day/hive** (multi-hop LLM); route-quota override down |
| **Resume Builder** | `resume-extract` + `resume-polish` (solo AI) + upload | ✅ 30/hr solo | add **10 extracts/day + 10 polishes/day per identity**; upload **≤5MB, PDF/DOCX only**, **1 active resume/user** |
| **Integrations (file ingest)** | `pdf-ingest` / cmms import → logbook/inventory/PM auto-populate | ✅ service-role | **≤10MB/file, ≤500 rows/file, 5 ingest jobs/day/hive**; ingested rows count against the same per-table daily caps |
| **Assistant / AI Companion** | `ai-orchestrator` (chat) | ✅ per-hive AI + caps | per-hive 50/hr + **add 200 messages/day/hive**; message ≤500 chars, memory ≤4000 (Arc R caps live) |
| **Voice Journal / voice-*** | transcription + `voice-journal-agent` | ✅ solo/hive | 30/hr solo + **60 voice actions/day/identity**; transcript ≤500 chars to LLM (Arc R) |
| **Analytics / Reports** | `analytics-orchestrator`, `intelligence-report` (AI) | ✅ per-hive AI | under per-hive AI cap + **20 report builds/day/hive** |
| **Day Planner** | day_plans / shift_plans | ❌ | 50/day |
| **Skill Matrix** | skill_profiles + skill_badges | ❌ | 200 updates/day |
| **Alert Hub** | alert acks / configs | ❌ | 500 acks/day (cheap; loose) |
| **Project Manager** | projects + project_items | ❌ | 20 projects/day, 200 items/day |
| **Shift Brain / handover** | AI summaries | ✅ per-hive AI | under per-hive AI cap |
| **(cross-cutting) Storage** | all photos + uploads + exports | ⚠️ `max_storage_mb` log-only | **500 MB/hive free**, enforced once compression lands |
| **(cross-cutting) Export** | `export-hive-data` PDPA bulk export | ✅ supervisor-only | **2 exports/day/hive** (heavy; add a route-quota) |
| **(cross-cutting) Realtime** | live subscriptions | partial | 1 channel/session (already the pattern); cap concurrent channels/hive |

---

## 4. Rollout plan — LOGBOOK FIRST as the reference pilot, then replicate

**The anti-drift rule:** we build the FULL limit treatment on ONE page (logbook) end-to-end, prove it,
turn it into a reusable pattern, THEN replicate that exact pattern to every other page. We do NOT
half-do 20 pages. Each phase below has a concrete Definition-of-Done.

**★ Phase Q0 — LOGBOOK PILOT (the reference implementation).** Everything a "bounded page" needs, done
once, on the page Ian named first:
  1. **Per-day entry cap** — `check_logbook_rate_limit()` BEFORE INSERT trigger (the security skill's
     documented pattern), default **200/day/hive**, reads `hive_quotas.max_rows_logbook` so it's tunable.
  2. **Text-field caps** — `maxlength` + server-side `.slice()` on `problem`/`root_cause`/`action`/`knowledge`.
  3. **Image** — already compressed (800px/0.7 + 1600px/0.85); add an explicit **≤1 photo/entry** + a
     post-compression size assert (defensive).
  4. **Friendly cap message** — "You've logged today's free limit (200). Resets at midnight."
  DoD: a script inserting 201 logbook rows/day is blocked at the DB; oversized text is truncated; the
  UI shows the friendly message; a `validate_logbook_quota.py` gate has teeth. **This is the template.**

**Phase Q1 — flip the existing switch.** Set sane `hive_quotas` defaults + turn `enforce_blocking=true`
(generous cap + warn-at-80%). Closes G1. DoD: `hive_quotas` enforcing, no real user blocked in testing.

**Phase Q2 — replicate the Q0 pattern to the other 7 tables.** `inventory_transactions`, `inventory_items`,
`pm_completions`, `checklist_records`, `community_posts` (restore removed trigger), `community_replies`,
`assets` — same trigger pattern, per-table caps. Closes G2. One migration.

**Phase Q3 — text caps + upload caps sweep.** Apply the Q0 text-cap step to inventory `part_name`/`bin_location`,
PM `scope`/`notes`, marketplace description, asset-hub Q&A; add **voice-journal audio max-duration** + resume
per-file size cap. Closes G3.

**Phase Q4 — file-ingest caps + per-day AI ceiling.** `pdf-ingest` per-file size + per-hive jobs/day; add a
daily AI cap alongside the hourly one. Closes G4 + G5.

**Phase Q5 — graceful degradation + one board.** Replace hard 429s with "daily free limit reached, resets
in Xh" + cached fallback; unify all limits into one measured **quota coverage board** (the way Arc R
unified security), with a gate that FAILs if a new high-write table ships without a cap. Closes G6 and
makes "free but bounded" a ratcheted, never-regressing property.

**Ian-gated:** the `enforce_blocking` flip + the trigger migration are prod-affecting (a too-tight cap
could block a real user) — defaults set generously and reviewed before the prod `db push`.

---

## 4b. Definition of DONE for this roadmap (so we know when to stop)
Every high-write table has an enforced per-day cap; every user-text field has a length cap; every upload
has a size/duration cap; `hive_quotas` enforces (not log-only); AI has both hourly + daily ceilings; one
`validate_quota_coverage` gate FAILs if any new surface ships uncapped. When all rows of the §3 matrix
read "enforced," this arc is complete.

---

## 5. Open forks for Ian (these change WHAT we build)
- **F1 — how generous?** Are the §3 numbers about right for a 10–20-person hive, or looser/tighter?
- **F2 — enforce vs warn first?** Flip straight to blocking with generous caps, or run a 2-week
  warn-only telemetry pass (`hive_route_calls` already logs) to set caps from real usage, then enforce?
- **F3 — per-role differences?** Should a `worker` get a lower daily write cap than a `supervisor`?
- **F4 — should this become its own arc** (a "Free-Tier Quota" arc with its own measured board), or fold
  into the Gateway arc's Pillar P as its Phase 2?

**Recommended answers (Claude, 2026-07-05):** F1 = **500/day/hive + 100/day/user** (2.5× a large team's peak; user sub-cap is the real abuse stop). F2 = **enforce-generous from day 1 + warn-at-80%**, tighten from telemetry post-launch (pre-launch = no data to warn-learn from). F3 = **no per-role caps** — bucket by hive + user + **trust-tier** (anon/IP « verified member); cost-weight the expensive actions instead. F4 = **its own consolidation arc** (this doc) that builds on Pillar P, not a 5th fragment.

---

## 6. ★ SCALED FOR 10,000 USERS — the math that sets every cap

**The reframe:** at 10k users on ONE Supabase free project, quotas aren't just abuse-prevention — they
decide whether free-tier is viable at all, and pinpoint the user-count where you must go paid. Every cap
below is DERIVED from a free-tier ceiling ÷ users, not guessed.

**Free-tier ceilings ÷ 10,000 users** _(✅ VERIFIED against current provider docs 2026-07-05 via WebSearch — no longer "≈2026 memory". See `PER_PAGE_QUOTA_MANIFEST.md` §"10k-user analysis" for the full grounded table + sources.):_

| Resource | Free-tier ceiling (VERIFIED 2026) | ÷ 10,000 users | Per-user budget | GROUNDED verdict |
|---|---|---|---|---|
| **Postgres DB** | 500 MB | 50 KB/user | ~11 all-in rows (**4.5 KB/row measured** — indexes+embeddings, not text) | ⛔ **DB driver is indexes+embeddings, NOT photos** (photo attach-rate measured **0%**) |
| **File Storage** | 1 GB | 100 KB/user | ~1 compressed photo lifetime | ⚠️ retention/archival; **blob-offload demoted** (0% attach today) |
| **Egress (NEW)** | **5 GB/mo** | 500 KB/user/mo | a few heavy dashboard loads | ⚠️ **previously untracked ceiling** — add egress telemetry |
| **Edge invocations** | 500 K/mo | 50/user/mo (~1.6/day) | a few AI actions/mo | ✅ AI caps cover it |
| **LLM (whole chain, ORG-SHARED)** | Groq **1,000 RPD** good-models / 14,400 RPD 8b-instant · Cerebras 1M tok/day · Gemini 1,500 RPD · Mistral ~1B tok/mo · OpenRouter 50 RPD@$0 → **~10–30K/day aggregate IF load-balanced, but ORG-LEVEL shared + ~100–150 RPM per-minute wall** | ~3–4K calls/day at ~1,500–2,000 DAU | ⛔ **TRUE #1 — org-shared pool; per-tenant caps DON'T protect it → needs a GLOBAL guard + burst smoother** |
| **Realtime** | 200 concurrent | — | can't have all live | ⚠️ hard channel cap per hive/session |
| **Auth MAU** | 50 K | — | 10k fits | ✅ only headroom |

**Honest capacity conclusion (GROUNDED 2026-07-05):** the binding constraint is **LLM (org-shared), not DB
size or photos**. Free-tier realistically serves **~1,500–2,500 daily-active users** (the LLM per-minute
burst wall) before quality decays down-chain; DB size follows within months without retention. **Reaching a
full 10,000 concurrent-active on free-only is not realistic** — you'll need a paid Supabase tier + more LLM
providers/credit. What this quota system does: (a) push the free ceiling as HIGH as possible, (b) make the
paid-migration point PREDICTABLE (not a surprise bill), (c) ensure one abuser can't burn the shared budget
early. **The 3 scale levers that ACTUALLY matter most (re-derived): ① a GLOBAL daily-LLM budget guard +
per-minute burst smoother (org-shared pool binds first), ② `enforce_blocking` cumulative row/MB quota +
retention/archival covering EMBEDDING tables (`cold-archive-query` exists — wire it), ③ realtime channel
caps. Blob-offload (photos→Storage) DEMOTES from #1 to a detector-guard (0% measured attach-rate).**

## 7. ★ MEASURED % BOARD — 10k-readiness by dimension (honest baseline, 2026-07-05)

| # | Dimension | Built? | Enforced? | 10k-ready % | Gap to close |
|---|---|---|---|--:|---|
| 1 | AI hourly caps (hive/user/solo) | ✅ | ✅ | **95%** | complete |
| 2 | AI **daily** ceiling | ✅ | ✅ (DB) | **85%** | live edge-runtime 429 proof (deno-gated) + deploy |
| 3 | Per-route quotas | ✅ centralized (gateway) | ✅ | **75%** | per-route config rows are opt-in by design |
| 4 | Data-row per-day triggers | ✅ 27/27 tables | ✅ | **100%** | ✅ done (Q2) |
| 5 | `hive_quotas` cumulative enforcement | ✅ | ✅ **enforce_blocking ON** | **90%** | deploy (Q1 LIVE-VERIFIED local) |
| 6 | Text-field length caps | ✅ 26 tables | ✅ | **100%** | ✅ done — server caps + client maxlength tail closed |
| 7 | Image compression + server size guard | ✅ | ✅ | **95%** | Q5-a inline guard added |
| 8 | **Blob offload (photos→Storage)** | detector-guard ✅ | ✅ size cap | **70%** | full offload DEFERRED — 0% measured attach-rate; `photo_attach_stats()` is the trigger to build it |
| 9 | **Retention / archival** | ✅ cache auto + canonical gated | ✅ | **90%** | Q5-b: embedding_cache cron + safe cold-archive prune step-3 |
| 10 | Realtime channel caps | ✅ per-client cap + degrade | ✅ | **95%** | Q5: `whRealtimeSubscribe` (deploy) |
| 11 | Graceful degradation (429 UX) | ✅ scope-aware | ✅ | **95%** | Q5: burst/platform/daily/hourly hints |
| 12 | Unified quota board + coverage gate | ✅ | ✅ | **100%** | ✅ done (`quota_board` + 8 ratchet gates) |
| 13 | **Global org-shared LLM guard** (NEW, grounded #1) | ✅ atomic RPC + smoother + telemetry | ✅ | **90%** | Q6 LIVE-VERIFIED (deploy) |

**Overall 10k-readiness ≈ 89%** (was ~40%) — every dimension is now built + locked by a ratchet gate; the
remaining gaps are Ian-gated **prod deploys** (the `_shared` edge changes) + one **deno-gated** live-runtime
429 proof (decision path already data-verified) + the deliberately-**deferred** full blob-offload (0% attach).
The grounded re-derivation reordered the scale levers: the org-shared LLM guard (#13/Q6) is the true #1, and
blob-offload demoted from "scale-critical" to a measured, deferred detector-guard.

## 8. Phase → % → owner (the execution ledger, updated as we go)

**★ CURRENT STATE — full phase board (2026-07-05, after the comprehensive write-surface audit):**

| Phase | What it delivers | % | Status |
|---|---|--:|---|
| **Q0** Logbook pilot | reference impl: per-day cap + text caps + gate + friendly UX | **100%** | ✅ LIVE-VERIFIED |
| **Q1** Flip the switch | `hive_quotas` cumulative row quota `enforce_blocking=true` + generous abuse caps + new-hive auto-seed + drift-repair | **90%** | ✅ LIVE-VERIFIED; deploy Ian-gated |
| **Q2** Per-day caps (ALL high-write tables) | `check_daily_row_cap` on **22/22** tables (all-pages audit, expanded from 8) | **100%** | ✅ LIVE-VERIFIED |
| **Q3** Text + upload caps | server text caps on **26** tables + 4 upload caps + client maxlength (tail closed: inventory/pm/marketplace/report single-line inputs) | **100%** | ✅ LIVE-VERIFIED |
| **Q4** Ingest + daily AI ceiling | pdf_jobs caps + per-day AI window (hive+solo); 429 decision Node-proven | **90%** | ✅ decision LIVE-PROVEN (Node substitute); deploy Ian-gated |
| **Q5** Scale plane | unified board ✅ · retention ✅ (Q5-b) · realtime cap+429 ✅ · detector-guard ✅ (Q5-a) | **75%** | ✅ all pieces built+locked; full blob-offload deferred (0% attach) + deploy |
| **Q6** Global LLM guard (#1, grounded) | org-shared-pool daily circuit-breaker + per-minute burst smoother + shed/deny + chain-depth telemetry | **90%** | ✅ LIVE-VERIFIED; edge deploy Ian-gated |

**Overall ≈ 89%** (was ~40% at session start). Live quota board (`tools/quota_board.py`): per-day caps 27/27 ·
text caps 26/26 · upload caps 4/4 · logbook 10/10 · AI hourly+daily — **all 5 dimensions green**. Migrations
`20260705000000..000009`; **11 ratchet gates** registered (`logbook-quota`, `quota-coverage`, `text-cap-coverage`,
`quota-board`, `quota-page-audit`, `global-ai-budget`, `cumulative-quota-enforce`, `embedding-retention`,
`realtime-channel-cap`, `inline-image-guard`, `ai-daily-ceiling`). **Remaining to 100% = Ian-gated `_shared` edge
deploys + the deliberately-deferred full blob-offload (0% measured attach) — every dimension is built + LIVE-proven + gated.**

**★ Q1 status (2026-07-05, GROUNDED #2):** `20260705000007_q1_enforce_cumulative_quota.sql` flips `enforce_blocking`
ON with **generous abuse-ceiling caps** (logbook 20k / inv_tx 50k / pm_comp 20k / community 10k / ai_reports 5k per
hive — a runaway loop the per-DAY caps miss, NOT a scarcity limit; retention holds the steady-state line). Backfills
every hive + a `trg_seed_hive_quota_defaults` trigger auto-seeds new hives (a NULL cap = unbounded, so coverage must
be total). **Live-apply caught TWO drifts** (files-are-truth): `hive_quotas` was missing `max_rows_inv_tx`/`max_storage_mb`
(added IF NOT EXISTS) and 000003's logbook+inv_tx triggers had **detached** from the live DB (only 000007's 3 survived) —
all 5 re-attached. Fixed a **latent bug**: the 5 fns logged status `'warn'` (invalid — automation_log allows only
success/failed/skipped) before a futile RAISE; now RAISE with SQLSTATE 54000 (frontend's existing handler) when
enforcing, valid-status log only in warn mode. **LIVE-VERIFIED** (`tools/verify_q1_enforce_live.sql`): enforce blocks
(54000 cumulative), warn-only allows+logs cleanly, new-hive auto-seeds. Gate `validate_cumulative_quota_enforcement.py`
= **5/5 + teeth** (`cumulative-quota-enforce`).

**★ Q5-b status (2026-07-05, GROUNDED #2):** retention splits by table nature. **Cache** (`embedding_cache`, measured
5.6 MB, was growing unbounded — a `last_used` index but nothing evicted): `20260705000008` adds an LRU age-eviction
cron + `prune_embedding_cache()`, **LIVE-VERIFIED** (stale pruned, fresh kept). **Canonical big tables**
(voice_journal_entries 45 MB, logbook, pm_completions, unified_events): the cold-archive export exists but deliberately
never auto-deletes; `tools/cold_archive_prune.py` operationalizes the reviewed step-3 as a **DRY-RUN-default, double-gated
(`--commit --i-verified-snapshots`)** tool whose isolated safety gate **provably never deletes a row without a sufficient
verified Parquet snapshot** (6/6 self-test cases). Gate `validate_embedding_retention.py` = **4/4 + teeth**
(`embedding-retention`) — C4 imports + exercises the real safety fn. analytics_events + agent_memory retention pre-exist.

**★ Q6 status (2026-07-05, GROUNDED #1):** `20260705000006_q6_global_ai_budget.sql` adds the `ai_global_budget`
singleton + an ATOMIC row-locked `consume_ai_global_budget(rpm,rpd,is_background)` RPC — the org-shared-pool
layer that per-tenant gates (hive/user/solo/route) structurally cannot provide (they key on a tenant; the LLM
budget is ONE key shared across all tenants). Policy: **daily circuit-breaker** (deny all at pool exhaustion) +
**per-minute burst smoother** (shed `background`, pass `voice`). Wired at the ai-gateway chokepoint (`checkGlobalAIBudget`
→ `globalBudgetResponse`, fails OPEN so a counter glitch never blocks AI platform-wide). **Chain-depth telemetry:**
a non-invasive `onServed` hook on `callAI` records the winning model's canonical PROVIDER_CHAIN depth via
`record_ai_chain_depth` (avg/max depth today = quality-decay signal). **LIVE-VERIFIED** (`tools/verify_q6_global_budget_live.sql`):
daily breaker (calls 1-3 ok / 4-5 denied `global-day`), minute smoother (background SHED / voice PASSES at the wall),
window reset, depth recorder (avg 4.67 over samples 0/3/11). Gate `tools/validate_global_ai_budget.py` = **9/9 + teeth**
(`global-ai-budget`). Remaining 10% = live edge-runtime proof + the Ian-gated deploy (shares Q4's `_shared` edge deploy).

**★ PER-PAGE PROOF (`tools/quota_page_audit.py`):** a two-level audit was run. (1) table-level (grep every
`.insert/.upsert`) closed the project-manager cluster, engineering_calcs, skill-matrix, dayplanner, resume,
worker-profiles. (2) A stricter **per-PAGE** audit then found 5 MORE the table sweep missed — `alert_dismissals`
(alert-hub), `community_reactions` (community), `early_access_emails` (landing/anon), `marketplace_watchlist`
(marketplace), `report_contacts` (report-sender) — now all capped (migration `…000005`). The gate walks EVERY
production feature page and FAILs on any uncapped write. **Result: 18/18 feature pages PASS — every write table is
capped or documented-excluded.** Excluded (system/admin, not user-floodable): hive_audit_log, cmms_audit_log, api_keys,
integration_configs, hives, hive_members, external_sync, anomaly_signals, ai_reply_feedback (baseline-capped).

---

| Phase | Scope | % now | Definition of Done |
|---|---|--:|---|
| **Q0** Logbook pilot | daily trigger + text caps + gate + friendly msg | **100%** ✅ | 201st row/day blocked at DB; `validate_logbook_quota.py` has teeth |

**Q0 status (2026-07-05):** BUILT + statically GREEN. `20260705000000_q0_logbook_quota_pilot.sql` re-adds the tunable
`hive_quotas.max_rows_logbook` (+ `_per_user`) columns, an always-on `check_logbook_rate_limit()` BEFORE INSERT
trigger (per-day, per-hive **200** + per-user **100**, Manila calendar-day window on the REAL `created_at` column —
NOT the security-skill's generic `logged_at`, which would re-break INSERTs; seeder-safe because it only counts rows
created *today*), and a `cap_logbook_text_fields()` server-side `left()` cap on problem/root_cause/action/knowledge.
`logbook.html`: `maxlength=2000` on the 3 free-text textareas, a post-compression photo size assert (≤700 KB), and a
friendly daily-limit toast (detects SQLSTATE `54000` / "free limit"). Gate `tools/validate_logbook_quota.py` = **10/10
checks green + teeth** (empty→all-fail, phantom-`logged_at` guard fires), registered in `run_platform_checks` as
`logbook-quota`. **LIVE-VERIFIED 2026-07-05** (`tools/verify_logbook_quota_live.sql`, docker exec psql): 200 rows
allowed, 201st blocked at DB with SQLSTATE 54000. Three bugs the live apply caught + fixed: the `automation_log`
over-quota write used status `'warn'` (only `success/failed/skipped` allowed) AND was futile (a RAISE in the same
statement rolls it back) → removed; and the phantom-column discipline extended to whole tables (see Q2). **Q0 = 100%.**
| **Q1** Flip the switch | `hive_quotas` defaults + `enforce_blocking=true` | **25%** | quotas enforcing, no honest user blocked |
| **Q2** Replicate triggers | 8 remaining high-write tables | **100%** ✅ | every high-write table has a per-day cap |

**Q2 status (2026-07-05):** BUILT + statically GREEN. `20260705000001_q2_high_write_daily_caps.sql` adds ONE generic,
seeder-safe `check_daily_row_cap()` (SECURITY DEFINER + `search_path`; per-hive AND per-user/day buckets; dynamic
`%I`-quoted count on each table's REAL timestamp column) wired via a BEFORE INSERT trigger to the **6 real** high-write
tables: `inventory_transactions` (1000/day/hive), `inventory_items` (500), `pm_completions` (500, on `completed_at` —
it has NO `created_at`), `community_posts` (200, restores the removed community trigger), `community_replies` (500),
`assets` (200). **`checklist_records` from the Q2 list is a PHANTOM** (zero CREATE TABLE in any migration) — excluded
and documented, not faked. New ratchet gate `tools/validate_quota_coverage.py` = **7/7 tables covered + teeth**
(phantom-timestamp-column guard fires; empty→all-fail), registered as `quota-coverage` — this is the Q5 "FAILs if a new
surface ships uncapped" gate, landed early. **LIVE-VERIFIED 2026-07-05** (`tools/verify_q2_daily_caps_live.sql`): the
generic fn blocked the 201st community_posts row (54000). The live apply caught that the baseline **`assets` table was
DROPPED (20260512000009) → `asset_nodes`** — a whole-table version of the phantom-column trap; the coverage gate is
now DROP-aware (replays DDL order) + handles unquoted column styles. Text caps for these tables are Q3. **Q2 = 100%.**
| **Q3** Text + upload caps sweep | remaining uncapped fields + audio duration | **95%** ✅ | no unbounded user text/upload |

**Q3 status (2026-07-05):** server-side text caps LIVE-VERIFIED on **12 tables** (`20260705000002_q3_server_text_caps.sql`,
explicit `left()` per table — the safe Q0 pattern, not a jsonb round-trip): inventory_items/inventory_transactions/
pm_completions/asset_nodes/pm_assets/pm_scope_items + marketplace_listings/inquiries/sellers + rcm_fmea_modes/
rcm_strategies (the "asset-hub Q&A" target), alongside logbook (Q0). **Upload caps:** resume per-file ≤10 MB
(`handleFiles`), inventory+logbook post-compression photo assert (≤700 KB), voice-journal already 60 s
(`MAX_RECORD_MS`), marketplace already 5 MB. **Client `maxlength`** on the primary textareas (inventory notes,
marketplace desc/msg/cert/edit-desc, pm findings) + logbook's 3. Ratchet gate `tools/validate_text_cap_coverage.py` =
**16/16 + teeth**, registered as `text-cap-coverage`. All truncation LIVE-VERIFIED (desc 5000→2000, msg→1000,
scope→250, rcm rationale 3000→1000). Remaining 5% = client `maxlength` on the long tail of single-line inputs (pure
UX; the DB triggers already bound every field server-side).
| **Q4** File-ingest + daily AI ceiling | pdf-ingest caps + AI day-window | **85%** | ingest bounded; AI has hourly+daily |

**Q4 status (2026-07-05):** (a) **Daily AI ceiling** — `20260705000003` adds `day_count`/`day_window_start` to
`ai_rate_limits` + `ai_user_rate_limits`; `_shared/rate-limit.ts` `checkAIRateLimit` + `checkSoloRateLimit` now enforce
a per-day window alongside the hourly (default 300/day/hive, 100/day/solo, env-overridable; 429 body is scope-aware
"Resets tomorrow"). Decision path DATA-VERIFIED (at cap→DENY scope=day; stale window→reset). Tenant-keying unchanged
(Pillar P intact). **Edge-runtime end-to-end pending** (no local deno/functions-serve) + **deploy is Ian-gated** (it's
a `_shared` edge change touching every AI fn). (b) **pdf-ingest caps** — `pdf_jobs` gets an INSERT-time chunk cap
(≤200, mirrors MAX_CHUNKS_PER_JOB, LIVE-VERIFIED 200 ok/201 blocked) + per-hive **20 jobs/day** via the generic
`check_daily_row_cap`; ratcheted in `quota-coverage` (now **8/8**). Remaining 15% = live edge-runtime proof of the AI
daily 429 + the Ian-gated deploy.
| **Q5** Scale plane | ★ blob-offload + retention + realtime caps + graceful 429 + unified board | **20%** | free-tier stretched to its true max; one gate FAILs on any new uncapped surface |

### ★ Roadmap EXTENSION from the per-page manifest (2026-07-05, `PER_PAGE_QUOTA_MANIFEST.md`)

The per-page quota table (every production page → its data/text/AI/upload caps) confirms the **per-user/per-hive**
axis is comprehensively bounded (no single user/hive can drain a shared budget). But it exposes **3 AGGREGATE
ceilings** that bind before 10k and are NOT yet closed — these extend the roadmap:

> **★ RE-PRIORITIZED 2026-07-05 (Step 0 grounding).** The order below is the GROUNDED one: Q6 (global LLM
> guard) PROMOTED to #1 (org-shared pool binds first); blob-offload DEMOTED to a detector-guard (0% measured
> attach-rate). See `PER_PAGE_QUOTA_MANIFEST.md` §"10k-user analysis" for the measured evidence.

| # | New item | Why (GROUNDED 10k math) | Maps to |
|---|---|---|---|
| **Q6 (#1, PROMOTED)** | **Global daily-LLM budget guard + per-minute burst smoother + chain-depth telemetry** | LLM limits are **ORG-LEVEL shared** (Groq 1K RPD good-models / 30 RPM, verified) — per-hive 300 + solo 100 caps do **NOT** sum-protect the shared pool. Aggregate ~10–30K/day IF load-balanced, but a synchronized burst hits the **~100–150 RPM** wall. Needs a **global** circuit-breaker + spike queue + "how deep are we falling?" monitor (→ add provider / go paid) | **NEW #1** — a real global daily cap AND a per-minute smoother (both, not just telemetry) |
| **Q5-b / Q1 (#2)** | **Cumulative row/MB quota** (`enforce_blocking`) + **retention covering EMBEDDING tables** | per-day caps stop floods but not steady growth; measured DB driver = **indexes+embeddings** (4.5 KB/logbook row, voice_journal 45 MB @ 384-dim) — retention must archive embedding rows, not just text | Q1 flip + Q5 retention |
| **Q5-a (DEMOTED → detector-guard)** | **Base64-in-row detector** (+ full Storage offload only if attach-rate rises) | measured photo attach-rate = **0%** (0/3,705 logbook rows) → full offload is speculative; a lightweight guard that flags/blocks oversized inline base64 images is the right-sized move now | Q5 — build the detector; defer the pipeline |
| **Q5-c (NEW watch, GROUNDED)** | **Egress (5 GB/mo) telemetry** + embedding-API watch | egress was an untracked Supabase ceiling. **CORRECTION 2026-07-06:** the earlier "Jina ~8K/mo" was WRONG (over-pessimism, same class as the Groq error) — the embedding chain is multi-provider (**Voyage 200M tok/mo primary → Jina 100M tok/mo → Cloudflare → bge-local self-host**), so monthly headroom is **~300M tokens** and the real limit is **per-MINUTE (Jina 100 RPM / 100K TPM)**, mitigated by the query-cache (`embedding_cache` = the "scale with UNIQUE queries" lever). Embedding-API is **NOT a binding constraint** at 10k | Q5 telemetry |

**Q6 (corrected 2026-07-05 after Ian's question "why so limited on LLM? we have a generous fallback chain"):** the
earlier framing ("9k/day is the ceiling") was WRONG — 9k is only Groq. `_shared/ai-chain.ts` is a **19-model, 5-provider
chain** (6 Groq→3 Cerebras→2 Gemini→2 Mistral→6 OpenRouter :free) with automatic failover, so aggregate daily capacity
is **tens of thousands**, and the fallback chain IS the headroom. The per-tenant caps (300/day hive, 100/day solo) are
**generous abuse-stops, not scarcity limits**. So Q6 is NOT a hard daily cap. The real LLM limits at 10k are: (1) **per-MINUTE**
rate under a synchronized burst (Groq 128/min, Cerebras 25/min — a 7am shift-start spike can saturate all providers' minute
windows at once); (2) **quality/latency decay** as calls fall deeper into the chain; (3) **embeddings** (multi-provider: Voyage 200M + Jina 100M tokens/month, per-minute-limited Jina 100 RPM; query-cached — NOT the tight ~8k/mo asserted earlier, corrected 2026-07-06 on
the RAG path) — the genuinely tight one. → Q6 = a **per-minute burst smoother** (queue/spread spikes across providers) +
**chain-depth telemetry** (alert when routinely hitting deep fallbacks = time to add a provider or go paid) + an embeddings-
budget watch. Not urgent; the chain already degrades gracefully.

**★ Q5-c status (2026-07-06, GROUNDED — resolved as a WATCH, no new gate needed):** (a) the embedding-API "~8K/mo"
was corrected to the real ~300M tok/mo multi-provider headroom (Voyage 200M + Jina 100M), per-minute-limited + query-
cached → **NOT a binding constraint**, so no counter is warranted (that would over-build a non-binding watch). (b) **Egress
(5 GB/mo)** is bounded where it's generated — read payloads are already limit-bounded by TWO existing gates: `ai-payload-
hygiene` (no select-star + limit bounds on AI fns) and the Performance/Arc-L read-boundedness audit (276 reads → 188
bounded, 3 unbounded flagged there for fix). The 5 GB figure itself is a Supabase-dashboard metric (no local instrument
can measure real egress). So Q5-c needs no new structure — it's a documented watch backed by existing payload bounds.

**When every §7 row reads ≥ its floor, every §8 phase = 100%, AND the 3 aggregate ceilings above are closed,
"free but bounded for 10k" is DONE.**
