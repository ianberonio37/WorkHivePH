# Next Architectural Layer — Comprehensive Study (pick the Arc F target rigorously)

**Created:** 2026-06-20 · **Method:** enumerate every architectural layer → map what each prior
arc covered → ground against reputable sources → rank by **risk × coverage-gap** → recommend the
next UFAI arc. ("Study, then roadmap, so we don't drift.") **Status: STUDY — awaiting the layer
pick before the Arc F roadmap is drafted.**

> **The two "layer" framings (don't conflate them):**
> 1. **The 13 infra/SaaS layers** (F·A·D·AU·S·C·RL·AV·LB·H·CI·L·DR) — matured to **100% capability**
>    by the Fullstack-Maturity roadmap (`COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §12`, matrix 78/78).
>    That arc proves a layer's *capability bar* is met (AWS-WA / SRE / 12-Factor / Fowler).
> 2. **The UFAI arc series** — deep **per-unit U·F·A·I quality** sweeps of one tier at a time
>    (Arc D = frontend/DOM, Arc E = edge backend). This goes *cell-deep* on each unit's Usability·
>    Functionality·Adaptability·Internal-Control, finding real value/security bugs.
>
> "The next architectural layer" = the next **UFAI-depth** sweep of a tier not yet swept that way.

---

## §1 — The platform's architectural layers (sized)

| # | Layer | Size (measured) | Swept by | UFAI-depth coverage | Residual gap |
|---|---|---|---|---|---|
| 1 | **Frontend / DOM** | 47 HTML pages · 32 root JS · 2 CSS | **Arc D** (UFAI) + Arc C (render) | ✅ deep | low — render+behaviour swept |
| 2 | **Edge backend** | 59 edge fns · 33 `_shared` | **Arc E** (UFAI 100% verified) | ✅ deep | structural-only (the honest ceiling) |
| 3 | **Python compute API** | **87 py files · 21 endpoints · 7 subsystems** (calcs·ml·analytics·diagrams·projects·reliability·sensors) | **Arc B** (calcs *value* only) | ⚠️ **1 of 7 subsystems** | **HIGH — see §3** |
| 4 | **Data / Database** | 223 migrations · 147 tables · 254 policies · 38 truth views · 17 DEFINER fns | **Arc E** (D1–D5 *summary*, live) | 🟡 summary | medium — deep per-object not done |
| 5 | Auth / Identity / Tenancy | front-door + ~30 edge fns | **Gateway Pillar I** (✅) + multitenant | ✅ | low |
| 6 | AI / Companion (RAG, grounding, wiring) | 7 memory layers · §0.8 surface map | Companion roadmaps (grounding/wiring/capability) | ✅ own arc family | medium (its own track) |
| 7 | 13 infra/SaaS layers (reliability/cache/observ/CI/DR…) | — | **Fullstack-Maturity** (✅ 100% capability) | ✅ capability | low (capability met; not UFAI-cell-deep, but mature) |
| 8 | Quality/Gate apparatus | 607 validators · 129 specs | self-covering (meta-gates) | ✅ | n/a (the instrument, not a product tier) |

**Two tiers have NO dedicated UFAI-depth arc: #3 Python compute API and #4 Data/DB.** Everything
else is either deeply swept (1,2,5,6) or capability-matured (7).

---

## §2 — External grounding (reputable sources)

**FastAPI production-readiness** (the #3 candidate) — the audit dimensions a complete sweep must cover:
- **AuthN/Z** on every route (API-key/JWT, key rotation, per-key scoping + rate-limit), **security
  logging** (failed auth, 403s, validation probes).
- **Dependency / supply-chain scanning** (`pip-audit`) — *this is exactly the class of the joblib bug*.
- **Observability** (request context, metrics, traces — Logfire/Prometheus), readiness checks,
  graceful shutdown, worker model, async DB access.
- Sources: [FastAPI Production Checklist (Compile N Run)](https://www.compilenrun.com/docs/framework/fastapi/fastapi-best-practices/fastapi-production-checklist/) ·
  [Auditing a production ML inference API (Morgan-Dibie)](https://medium.com/@KingHenryMorgansDiary/how-to-audit-a-production-ml-inference-api-a-practical-checklist-1e596d7a3847) ·
  [Practical Guide to FastAPI Security (Muraya)](https://davidmuraya.com/blog/fastapi-security-guide/)

**Supabase / Postgres data-tier audit** (the #4 candidate):
- **SECURITY DEFINER can silently bypass RLS** unless `FORCE ROW LEVEL SECURITY` — a definer fn runs
  as owner and skips RLS predicates. RLS-enabled-with-no-policy = inaccessible (safe default).
  DEFINER fns must not live in API-exposed schemas; bundle GRANTs with the RLS migration.
- Sources: [Supabase RLS docs](https://supabase.com/docs/guides/database/postgres/row-level-security) ·
  [Supabase RLS best-practices (MakerKit)](https://makerkit.dev/blog/tutorials/supabase-rls-best-practices) ·
  [Real-world Supabase pentests (Pentestly)](https://www.pentestly.io/blog/supabase-security-best-practices-2025-guide)

---

## §3 — Why the Python compute API tier is the highest risk × gap

**Evidence it is under-tested (two production bugs already found there, both by *other* arcs):**
1. **Arc B — numpy-500:** HVAC calc returned `numpy.bool_`, FastAPI 500'd `/calculate`, the edge
   *silently* served the un-validated TS value (46% wrong). Only the browser tier exposed it.
2. **Arc E — joblib-502:** `scikit-learn`+`joblib` missing from `requirements.txt` → `/ml/train`,
   `/ml/predict`, `/ml/status` all 502; the rules-fallback was unreachable. A dependency-scan
   (`pip-audit`) would have caught it pre-ship.

**Headline gap — the Python API has NO authentication:** `main.py` sets `CORSMiddleware
allow_origins=["*"]`, has **no `Depends`/API-key/Bearer check on any route**, and the edge calls it
with only `Content-Type` (no auth header). It binds `0.0.0.0:8000` on Railway (`EXPOSE 8000`). If the
deploy URL is reachable, **anyone can invoke `/calculate`, `/ml/train`, `/analytics`, `/project/progress`
with no credential** — an open compute API doing real work (and `/ml/train` reads cross-hive data).

**Coverage gap — 6 of 7 subsystems are UFAI-dark:** only `calcs` (via Arc B's value-oracle) has been
swept. `ml` · `analytics` · `diagrams` · `projects` · `reliability` · `sensors` have **no** U (API
contract) · F (correctness) · A (resilience/config/deps) · I (auth/security/observability) coverage.

**By contrast, the Data/DB tier is the MOST mature** — Arc E live-verified 0 orphan-RLS, 0
FK-type-mismatch, 17/17 DEFINER gated, 254 policies, 38 truth views. A DB arc would *deepen
already-strong* coverage (the one fresh dimension from §2 = `FORCE ROW LEVEL SECURITY` on
definer-bypass — a narrow, high-value check, not a whole-tier gap).

---

## §4 — Ranking (risk × coverage-gap)

| Rank | Layer | Coverage gap | Demonstrated risk | Verdict |
|---|---|---|---|---|
| **1** | **Python compute API** | **6/7 subsystems + all auth/security/observability/deps** | **2 prod bugs + NO auth + open CORS** | **★ RECOMMEND — Arc F** |
| 2 | Data / Database (deep) | per-object RLS/RPC/DEFINER/migration value | low (most mature; FORCE-RLS is the one fresh check) | Arc G (later) |
| 3 | Client-side JS logic (per-module) | per-function logic beyond DOM behaviour | low (Arc D covered behaviour) | fold into a future Arc D extension |

---

## §5 — Proposed Arc F skeleton (Python Compute API tier) — for the roadmap step

Same UFAI method as Arc D/E: one ratcheted scorer, per-cell **live / oracle / proof / contract /
attributed◈ / N-A-by-evidence**, measured-not-credited, denominator mined first.

- **Rows (sub-layers) = the 7 subsystems + app-shell:** P1 calcs · P2 ml · P3 analytics · P4 diagrams ·
  P5 projects · P6 reliability · P7 sensors · P8 app-shell (`main.py`: CORS, error handling, `_to_jsonable`
  boundary, `/health`, startup).
- **Lenses re-projected onto a FastAPI endpoint:**
  - **U** (consumer contract): request/response schema (pydantic), status semantics, error contract, `/health`, `/calcs` discoverability.
  - **F** (correctness of effect): value-oracle (calcs 58/58 already ✅; extend to reliability/analytics/projects), model correctness (ml), determinism, serialization boundary (`_to_jsonable`).
  - **A** (change-resilience): config-in-env (12-Factor), **dependency declaration + `pip-audit` supply-chain** (the joblib lesson, gated by `validate_ml_deps.py` — generalize it), graceful degradation/fallback (the numpy lesson), statelessness, worker model.
  - **I** (security + observability): **authN/Z on every route** (the open-API finding — the keystone fix), CORS lockdown, input validation, secret/PII handling, structured logging + traces, per-route observability.
- **Likely keystone fixes the arc will surface:** (1) add an auth gate (shared-secret/JWT between
  edge↔python, or network isolation) — close the open API; (2) lock CORS to known origins; (3) a
  `pip-audit` gate over `requirements.txt`; (4) extend the value-oracle to the non-calc compute
  subsystems (reliability/analytics).
- **Honest ceilings to name up front:** Railway deploy/scaling (prod), real Azure-TTS, anything
  needing the live host server (cf. the trigger-ml-retrain restart) = attributed/external.

---

## §6 — Recommendation

**Arc F = the Python Compute API tier.** It is the single highest **risk × gap** layer: an
unauthenticated, CORS-open FastAPI app doing real compute, where **two production bugs have already
surfaced** and **six of seven subsystems have zero UFAI-depth coverage**. The Data/DB deep sweep
(Arc G) is valuable but lower-urgency — that tier is already the most live-verified on the platform.

**Next step on approval:** draft `PYTHON_API_UFAI_ROADMAP.md` (Arc F spine) with the per-cell matrix,
the P1–P8 × U·F·A·I denominator mined first, and the keystone-fix queue led by the auth gate.
