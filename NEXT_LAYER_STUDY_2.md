# Next Architectural Layer — Comprehensive Study, Round 2 (pick the Arc I target)

**Created:** 2026-06-21 · **Method:** same as Round 1 (`NEXT_LAYER_STUDY.md`, which picked Arc F→G) —
enumerate every architectural layer → map what each prior arc covered → ground against reputable sources
→ rank by **risk × coverage-gap** → recommend the next UFAI arc. ("Study, then roadmap, so we don't drift.")
**Status: STUDY — awaiting Ian's layer pick before the Arc I roadmap is drafted.**

> **The two "layer" framings (unchanged from Round 1):**
> 1. **The 13 infra/SaaS layers** — matured to **100% capability** by the Fullstack-Maturity roadmap
>    (`COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §12`). Proves a layer's *capability bar* is met.
> 2. **The UFAI arc series** — deep **per-unit U·F·A·I quality** sweeps of one tier at a time.
> "The next architectural layer" = the next **UFAI-depth** sweep of a tier not yet swept that way.

---

## §1 — The platform's architectural layers (re-sized, 2026-06-21)

Since Round 1, **four more arcs landed**: Arc F (Python API), Arc G (Data/DB), Arc H (AI/Companion).
With Arc D (frontend) and Arc E (edge) before them, **six of the request/data-path tiers are now swept.**

| # | Layer | Size (measured) | Swept by | UFAI-depth | Residual gap |
|---|---|---|---|---|---|
| 1 | Frontend / DOM | 47 HTML · 32 JS | **Arc D** | ✅ deep | low |
| 2 | Edge backend | 59 fns · `_shared` | **Arc E** | ✅ deep | structural-only |
| 3 | Python compute API | 87 py · 7 subsystems | **Arc F** | ✅ deep | low |
| 4 | Data / Database | 147 tables · 256 pol · 53 DEFINER | **Arc G** | ✅ deep (488/488 obj) | low |
| 5 | AI / Companion | 50 surfaces | **Arc H** | ✅ deep (all floors) | probabilistic residual (named) |
| 6 | **Auth / Identity / Session** | **22 auth-flow files · 21 pages · in-flight Supabase-Auth migration** | Gateway Pillar I + multitenant (cross-cutting only) | 🟡 **never a dedicated arc** | **HIGH — see §3** |
| 7 | **Realtime / event** | **11 subscription surfaces** | incidental (Arc D/E touched edges) | 🟡 thin | medium (subscription isolation) |
| 8 | **Client-side shared JS** | **32 root modules** | Arc D (page behaviour only) | 🟡 partial | medium-low (per-function logic) |
| 9 | Storage / Files / Object | 2 files · 2 bucket migrations | incidental | 🟡 thin but small | low (small surface) |
| 10 | PWA / offline / SW | report-sender + sw.js | incidental | 🟡 thin | low-medium |
| 11 | Integrations (SAP/Maximo/OPC-UA/MQTT/webhook) | mostly framework/stubs | Arc E (E7) | 🟡 partial | medium-but-future (connectors not all built) |
| 12 | 13 infra/SaaS layers | — | **Fullstack-Maturity** | ✅ capability (not cell-deep) | low (mature) |
| 13 | Quality/Gate apparatus | 397 validators | self-covering | ✅ | n/a (the instrument) |

**Genuinely-unswept dedicated-UFAI candidates: #6 Auth/Identity, #7 Realtime, #8 Client-side JS** (plus
small/future #9 Storage, #10 PWA, #11 Integrations). Everything else is deeply swept or capability-matured.

---

## §2 — External grounding (reputable sources)

**Auth / Identity (#6 candidate) — the audit dimensions a complete sweep must cover:**
- **OWASP ASVS** V2 Authentication (credential strength, **account-enumeration resistance**, anti-automation/
  **brute-force rate-limit**, credential recovery) + V3 Session Management (token lifecycle, **session
  fixation/expiry/logout invalidation**, secure cookie/JWT handling) + V4 Access Control (**privilege
  escalation / RBAC**, IDOR, least privilege).
- **OWASP Auth / Session / JWT cheat sheets** — JWT signature+exp validation, `getUser(jwt)` vs unvalidated
  `getSession`, refresh-token rotation.
- **Supabase Auth (GoTrue) specifics** — anon-key vs authenticated client, RLS depends on a *valid JWT*;
  the "deferred auth-migration" anti-pattern (RLS policies added but anon-key paths still live = isolation
  is theatre) — the exact `project_rls_decision` state Arc G/H kept hitting.

**Realtime (#7)** — Supabase Realtime respects RLS only when the channel uses an authenticated client;
listener cleanup (memory leaks), per-subscription tenant isolation, the `postgres_changes` RLS gotcha.

**Client-side JS (#8)** — per-module unit correctness (state machines, parsers, the journey engines),
DOM-XSS sinks beyond the render layer, dependency/CDN integrity.

---

## §3 — Why Auth / Identity is the highest risk × gap

**Risk — it's the trust root.** Every other layer's isolation *assumes* identity is correct: Arc G's RLS,
Arc H's `user_can_access_hive`, the Gateway's `resolveTenancy` all trust that `auth.uid()` is the real,
validated caller. If signup, session, or role assignment is weak, **every downstream isolation proof rests
on sand.** Auth bugs are the highest blast radius on the platform.

**Gap — touched everywhere, swept nowhere.** Identity has been hardened *cross-cutting* (Gateway Pillar I
fixed client-trusted `hive_id`; Arc G hardened `hive_members` INSERT against self-escalation; Arc H gated
retrieval by membership) — but **no arc ever swept the auth FLOWS themselves**: signup, invite-code
redemption, login, password reset, email verification, session/JWT lifecycle, logout invalidation,
account-enumeration, brute-force resistance, the worker→supervisor role model.

**The in-flight migration is the smoking gun.** Arc G and Arc H *both* repeatedly bumped into "the deferred
auth-migration RLS state" (`project_rls_decision` / `project_supabase_auth_migration`): RLS policies were
added but legacy anon-key paths were never fully retired. **Completing and proving that migration is the
natural capstone of all the tenant-isolation work** — and it belongs to a dedicated Auth arc, not another
table sweep.

**Evidence it's under-tested:** 22 frontend files carry auth calls; 21 pages touch invite/`hive_members`/
`auth_uid`; the only edge helper is `tenant-context.ts` (tenancy resolution) — there is **no validator for
signup safety, session expiry, account enumeration, or brute-force**, and the auth migration has no
completion gate.

---

## §4 — Ranking (risk × coverage-gap)

| Rank | Layer | Coverage gap | Demonstrated risk | Verdict |
|---|---|---|---|---|
| **1** | **Auth / Identity / Session** | auth flows + session/JWT + RBAC + the in-flight migration | trust root; every isolation proof depends on it; migration provably incomplete | **★ RECOMMEND — Arc I** |
| 2 | Realtime / event | subscription isolation + listener lifecycle | medium (a realtime channel on an anon client can leak cross-tenant) | Arc J (later) |
| 3 | Client-side shared JS | per-function logic beyond DOM | low-medium (Arc D covered behaviour) | fold into an Arc D extension |
| 4 | Storage / PWA / Integrations | small or not-yet-built | low / future | defer |

---

## §5 — Proposed Arc I skeleton (Auth / Identity / Session) — for the roadmap step

Same UFAI method: one ratcheted scorer, per-cell live/oracle/proof/contract/attributed◈/N-A, denominator
mined first. **Lenses re-projected onto an auth surface:** U = the flow's contract + no info leak; F = it
actually authenticates / the session/role is correct / the migration is complete; A = brute-force +
rate-limit + graceful session expiry/refresh; I = the OWASP ASVS controls (session fixation, JWT validation,
privilege escalation, enumeration, **the auth-migration RLS enforcement = the keystone**).

- **Rows (sub-layers):** I1 Credential & signup · I2 Session & JWT lifecycle · I3 Password & recovery ·
  I4 Role & permission (RBAC worker/supervisor, self-escalation) · I5 Tenancy binding (consolidate Gateway
  Pillar I `resolveIdentity`/`resolveTenancy`/`verifiedHiveId`) · I6 **Auth-migration completion** (retire
  anon-key paths, drop remaining legacy-open policies — the in-flight keystone) · I7 Bot/abuse protection
  (signup bot, login brute-force) · I8 Account lifecycle (deactivation, offboarding, data deletion).
- **Floors (proposed):** U90 / F85 / A85 / **I92** (auth is the trust root — highest internal-control bar).
- **Likely keystone fixes:** (1) complete the Supabase-Auth migration + a completion gate; (2) account-
  enumeration resistance on signup/reset; (3) brute-force rate-limit on login; (4) session expiry/logout
  invalidation proof; (5) RBAC self-escalation closure (extends Arc G's `hive_members` INSERT work).
- **Honest ceilings:** GoTrue/provider internals, real email delivery, MFA/SSO/SAML (enterprise, likely
  unbuilt) = attributed/external.

---

## §6 — Recommendation

**Arc I = the Auth / Identity / Session tier.** It is the single highest **risk × gap** layer remaining: the
**trust root every other isolation proof depends on**, hardened only cross-cutting and **never swept as its
own layer**, with a **provably-incomplete auth migration** that Arc G and Arc H both kept colliding with.
Realtime (Arc J) and a client-side-JS extension are the next two, but lower-urgency.

**Next step on approval:** draft `AUTH_IDENTITY_UFAI_ROADMAP.md` (Arc I spine) with the I1–I8 × U·F·A·I
matrix (denominator mined first via a new `tools/auth_identity_ufai_sweep.py`), led by the auth-migration
completion keystone. Fresh window opens at **`build I0`**.
