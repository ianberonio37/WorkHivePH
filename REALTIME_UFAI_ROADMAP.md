# Arc J — Realtime / Event UFAI Roadmap

**Started:** 2026-06-21 · **Tier:** Realtime / event (Supabase Realtime `postgres_changes` + presence).
**Method:** identical to Arcs D–I — one ratcheted scorer (`tools/realtime_ufai_sweep.py`), denominator
mined FIRST, per-cell U·F·A·I disposed live / oracle / proof / contract / attributed◈ / N-A, floors gated.
**Picked by:** `NEXT_LAYER_STUDY_2.md §4` (rank 2, after Auth/Arc I) — the read-path twin of the Arc G
DEFINER-IDOR / Arc H view-`security_invoker` tenant-boundary work, now on the *live broadcast* path.

---

## §1 — Denominator (mined live, 2026-06-21)

**Client surface — 21 `.channel()` subscription surfaces across 10 pages:**

| Page | Channels | Scope |
|---|---|---|
| hive.html | 8 (readiness, adoption, presence, feed, pm, inventory, approval, worker-appr) | hive / worker |
| community.html | 3 (presence, feed, **global-feed**) | hive + 1 global |
| alert-hub.html | 2 (amc, anomaly) | hive |
| asset-hub.html | 2 (telemetry:node, asset-hub:node) | node |
| achievements.html · audit-log.html · founder-console.html · marketplace.html · pm-scheduler.html · project-manager.html | 1 each | worker / hive / **platform** / section |

**Server surface — 23 tables in the `supabase_realtime` publication** (the exact set whose row-changes
are broadcast). This is the security denominator: a published table's SELECT RLS policy is the ONLY tenant
boundary for its subscribers.

**Measured posture at J0:**
- Listener cleanup: **10/10** channel pages call `removeChannel` (45 removes for 21 channels = the
  beforeunload + leave-hive double-cleanup the realtime skill mandates). ✅
- Connection-timeout resilience (skill's critical rule — pair `subscribe()` with a `setTimeout` offline
  fallback): **10/10** pages (was 3/10). The 7 data-feed pages were wired via a shared `rtConn()` factory
  in `utils.js` (`channel.subscribe(rtConn(onState))` — settles once, fires `'offline'` if SUBSCRIBED never
  arrives, handles CHANNEL_ERROR/TIMED_OUT/CLOSED); asset-hub/community/hive keep their bespoke presence
  timeouts. ✅ (J4 closed this session.)
- Payload-render XSS at the realtime boundary: **0** direct `payload.new → innerHTML` sinks. ✅
- Published-table isolation: **23/23** RLS-enabled; **0 exposed** after the keystone fix (below).

---

## §2 — The keystone finding (J1 — subscription isolation) · FOUND + FIXED + LIVE-VERIFIED + GATED

**Threat model.** Supabase Realtime `postgres_changes` broadcasts row changes to every subscriber on a
channel. The **channel name** (`hive-feed:<HIVE_ID>`) and the client-supplied **`filter`**
(`hive_id=eq.<X>`) are *strings the client chooses* — NOT security boundaries. The only tenant boundary is
the table's **SELECT RLS policy**, evaluated by Realtime against the subscribing connection's role/JWT. A
published table with RLS-off OR a permissive always-true (`USING(true)`) SELECT/ALL policy streams **every**
row change to **any** anon subscriber — cross-tenant LIVE exfiltration (a stream, strictly worse than the
one-shot read Arc G's gate covers).

**The vuln (live-proven, rolled back).** `platform_feedback` was in the publication with three anon
`USING(true)` policies (SELECT / UPDATE / DELETE). A no-JWT anon client could:
- **READ** private (`is_public=false`) feedback incl. `contact_email` PII + body,
- **UPDATE** (tamper) any row, **DELETE** any row,
- subscribe to a Realtime channel and receive a **live stream of every feedback submission** platform-wide.

**Cross-arc flywheel.** Arc G's `validate_rls_no_permissive_bypass.py` had EXEMPTED `platform_feedback`
as *"global public product-feedback board — cross-hive by design."* That was a **surface-heuristic
classification** ([[feedback_classify_by_evidence_not_heuristic]]): "public board" means anon reads
PUBLISHED rows, not unrestricted read/write of the whole table incl. private PII. The realtime lens
re-examined by evidence and **retracted the exemption**.

**Fix** (`supabase/migrations/20260621000003_platform_feedback_rls_harden.sql`, non-breaking — every anon
path verified first, NOT a blind drop):
- `is_platform_admin()` DEFINER helper (search-path-pinned; mirrors the proven `analytics_events_select_admin`
  EXISTS pattern + Arc G/H `user_hive_ids()`).
- SELECT → public reads `is_public=true` only · admins read all.
- INSERT → anyone may submit but **cannot self-publish** (`is_public IS NOT TRUE AND status='new' AND
  admin_note IS NULL`) — defaults satisfy it, so `wh-feedback-fab.js` is unaffected.
- UPDATE / DELETE → platform admins only. Upvotes unaffected (DEFINER `toggle_feedback_upvote` RPC).

**Verified live (two-tenant, rolled back):** anon → reads only the published row (no PII), 0 tamper, 0
delete, can submit, **cannot self-publish** (RLS violation); admin (`is_platform_admin()=t`) → reads all
incl. private. Public `/feedback/` (is_public=true) + founder console (authenticates) both intact.

**Gate** (`tools/validate_realtime_subscription_isolation.py`, registered `run_platform_checks` AI
Validation, `skip_if_fast`): every realtime-published table must be RLS-enabled with no always-true
SELECT/ALL policy. **Baseline 0 exposed**, forward-only DOWN ratchet, teeth-proven (inject always-true →
REGRESSION; drop → HELD). Arc G's permissive-bypass gate also updated — exemption removed, so it now
PROTECTS `platform_feedback` from a regression too.

---

## §3 — Rows × lenses (J1–J8 × U·F·A·I)

Lenses re-projected onto realtime: **U** = subscription contract (channel naming, payload shape, conn-state
UI) · **F** = it delivers live updates correctly (handler updates UI, merge/dedupe, reconnect) · **A** =
resilience/abuse (conn-timeout + offline fallback, listener cleanup = no leak, debounce) · **I** =
isolation/security (subscription RLS, publication hygiene, auth binding, payload XSS at the realtime sink).

| Row (sub-layer) | Keystone concern |
|---|---|
| **J1 Subscription isolation** | postgres_changes RLS on published tables — **the keystone (done)** |
| J2 Channel scoping & naming | per-hive channel names; global channels are by-design only |
| J3 Listener lifecycle / cleanup | `removeChannel` on unload + leave-hive (no leaked subscription) |
| J4 Connection reliability | `subscribe()` paired with timeout + offline fallback (skill rule) |
| J5 Presence | presence key, no PII broadcast, track/untrack symmetry |
| J6 Payload handling | escHtml at the realtime render boundary; client-side filter fallback |
| J7 Auth binding | client is authenticated so Realtime applies RLS (the anon-key gotcha) |
| J8 Publication hygiene | only intended tables in `supabase_realtime`; no over-publication |

**Floors:** U90 / F85 / A85 / **I92** (isolation is the trust-sensitive lens; mirrors Arc I).

---

## §4 — Status (J0 board: 29 applicable · 100% covered · 100% VERIFIED · 0 fix · all floors met · **live 100%**)

| lens | ver% | live% | floor | |
|---|---|---|---|---|
| U | 100 | **100** | 90 | ✅ |
| F | 100 | **100** | 85 | ✅ |
| A | 100 | **100** | 85 | ✅ |
| I | 100 | **100** | 92 | ✅ |

**ARC J = 100% LIVE (29/29).** Driven 37.9% → 100% by BUILDING the runtime structure for every cell Ian
flagged as a wrongly-claimed "covered-by-nature ceiling" ([[feedback_build_structure_to_make_it_liveable]]).
The new structure: `tests/realtime-arc-j.spec.ts` (4 browser tests — presence sync · **cross-tenant
subscription isolation** [authed member subscribes `filter=<foreignHive>` → 0 rows via RLS = the client
filter is NOT a boundary] · listener-lifecycle `getChannels()` probe · `rtConn()` offline/live unit test) +
the rewritten `feedback-realtime.spec.ts` (admin-auth WS delivery) + `validate_anon_key_retirement.py`
(J7) + `validate_realtime_publication`/`validate_observability` folds. All 6 realtime specs green; folds 6/6.

- **J1 keystone:** found + fixed + live-verified + gated (the platform_feedback realtime PII leak).
- **J4 connection reliability:** shared `rtConn()` helper wired across all 10 channel pages (J4/A→live).
- **Live-push (this session, real runtime evidence only — no inflation):** live 37.9% → **62.1%** via 3
  Playwright specs against the real WS + RLS (folded by `tools/validate_realtime_live.py`, 5/5 green):
  - `feedback-realtime.spec` — authenticated admin receives `is_public=false` feedback live via real
    WebSocket+RLS (anon correctly excluded post-fix) → **J1/F, J6/F** live. *(This test was REWRITTEN to
    sign in as a platform admin — the old version relied on the anon-open hole the keystone closed.)*
  - `realtime-arc-j.spec` (NEW) — two same-hive workers see each other's presence live; hive-scoped, no
    cross-hive bleed → **J5/F·U·A·I** live.
  - `journey-realtime.spec` (K1–K4) + `validate_realtime_publication` (live DB) + `validate_observability`
    (cleanup gate) → **J8/F, J3/A·F** live.
  - **Env fix:** `supabase_realtime_workhive` was Exited 8 days — `docker start`ed it (the WS was down,
    not the RLS; the "start the stopped container" move).

### J7 — auth-migration completion DONE this session (Ian picked it as the cross-arc live lever)
The deferred `project_rls_decision` **client half** is now proven + gated. DB half was already done (Arc G
hardened policies to `auth.uid()`-derived, bypass ratchet 9→0). New gate
`tools/validate_anon_key_retirement.py` (registered, teeth-proven, baseline-locked) proves both halves:
- **L1 (live DB):** an `anon`-role read of all **8 core hive tables returns 0** rows — the bare anon-key
  path reads NOTHING; RLS applies only because the client carries a session JWT. (Teeth: inject an anon
  `USING(true)` → 3700-row leak → REGRESSION; drop → HELD.)
- **L2 (static):** all **11/11 production hive-read pages** establish a session (`restoreIdentityFromSession`
  / `getSession`) before reading. The 8 throwaway/dev pages (`GROUNDED_SWEEP_ROADMAP.md` "Explicitly
  EXCLUDED" — `engineering-design-test.html` et al.) are exempt, not a gap.
→ **J7/I·F·A flipped to live**; live 62.1% → **72.4%**. This gate is the shared forward ratchet Arcs G/I
left open, so it lifts their live-subset too.

### Live backlog — CLEARED (the "covered-by-nature ceiling" was un-built test harness)
Ian rejected the earlier "remaining ~28% = covered-by-nature, no runtime to probe" framing as a
stop-in-disguise. Each "contract" cell DID have runtime behaviour; the structure to exercise it just wasn't
built yet. What made each live:
- **J1/U + J2/F** (filter/channel is not a boundary) → the cross-tenant subscription test: an authed Manila
  member subscribes with `filter=<Lucena>` and receives **0 rows** (RLS blocks at the realtime layer despite
  the filter matching); own-hive delivers.
- **J3/U + J3/I** (lifecycle) → `getChannels()` before/after `removeChannel` (subscribe adds, remove drops).
- **J4/U** (conn-state) → `rtConn()` unit test (offline-on-timeout / live-on-SUBSCRIBED / offline-on-error).
- **J6/U** (payload shape) → the delivered row renders as an inbox card (handler consumes `payload.new`).
- **J6/A** (payload resilience) → REPLICA-IDENTITY-safe `payload.old?.id` (K2). The legacy Stage-1.5
  client-side member-filter is unused (0 pages) — the server filter + RLS is the live path.
- **J8/A** (publication hygiene) → migration-tracked (15 migrations declare the publication adds) + live-DB.
- **J7/I·F·A** (auth binding) → `validate_anon_key_retirement.py` (anon reads 0 from 8 core hive tables).

- **NEXT:** §4-rank-3 layer (Client-side shared JS — 0 SRI on CDN scripts found) per `NEXT_LAYER_STUDY_2.md`.
- **Ian-gated:** commit + `supabase db push` (mig 20260621000003); no new edge fns. Keep realtime container
  up for the live folds.
