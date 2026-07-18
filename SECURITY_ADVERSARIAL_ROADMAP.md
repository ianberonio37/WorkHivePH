# Arc R — Security / Adversarial Red-Team

> **The 11th arc** (and the boundary-correctness twin of Arc Q). Q proved *the value the
> user sees is right*; **R proves the attack surface is right.** Every time this platform has
> been probed adversarially we found a real cross-tenant bug — G DEFINER-IDOR, H view
> `security_invoker`, J realtime-RLS leak — but those were all the **DB boundary**. The
> **frontend (XSS/DOM/CSP/SRI), edge (BOLA/BFLA/SSRF), supply-chain (secret-egress/CVE), and
> AI (prompt-injection)** surfaces have never been swept as **one ratcheted, adversarially-
> verified, measured-% frame.** Highest risk for a multi-tenant industrial SaaS holding client
> asset/maintenance data + a marketplace + an AI companion.

_Spine doc. Scorer/harness: `tools/security_adversarial_sweep.py` (R0). Started 2026-06-23. LOCAL._
_Selected by `NEXT_ARC_STUDY_post_Q.md` §2 (Candidate A ★) — Ian's pick, 2026-06-23._

---

## 0. Why this arc, and what already exists (measured, not assumed)

Arc R is **NOT greenfield.** The platform already has a substantial, *registered* security base —
13 focused validators + the `sast_scan.py` OWASP aggregator — built incrementally across Arcs E/G/H/I/J:

| OWASP lens | Existing gate(s) (at project ROOT) | What it proves |
|---|---|---|
| A01 Access control | `validate_gateway_bypass`, `validate_definer_tenant_gate`, `validate_function_security`, `validate_rls_no_permissive_bypass`, `validate_rls_tenant_isolation`, `validate_anon_key_retirement` | tenant boundary on the 4 DB read-paths |
| A02/A06 Secrets | `validate_integration_security` (key-format, service-role) | no service-role/secret egress |
| A03 Injection/XSS | `validate_xss`, `validate_companion_output_escaping` | escHtml coverage, AI-output escaping |
| A04 RLS design | `validate_rls_coverage`, `validate_truth_view_security_invoker`, `validate_view_security_invoker` | RLS on every table + view-as-invoker |
| A05 Misconfig | `validate_security_definer_search_path`, CORS dynamic | search_path pinned, CORS echo |
| A07 Auth | `validate_login_proxy_lockout`, `validate_signup_enumeration_safety`, `validate_signup_bot_protection`, `validate_password_recovery`, `validate_account_deactivation` | brute-force, enum-safety, recovery |
| A08 Integrity/supply | `validate_python_api_deps` (pip-audit), Stripe webhook sig | dep CVEs, webhook auth |
| Realtime path | `validate_realtime_subscription_isolation` | published-table RLS = 4th read-path |
| AI/prompt | `validate_ai_prompt_injection`, `validate_ai_retrieval_isolation` | prompt-injection, RAG hive-scope |

**So what does Arc R *add*?** Three things the existing base does NOT do:

1. **One ratcheted, measured-% frame** across all four attack surfaces (the validators are scattered,
   each with its own baseline; no single board says "the platform's adversarial posture is N%").
2. **The un-swept surfaces** the scattered gates miss — **SRI on every CDN script** (supply-chain),
   **SSRF egress** from the 60 public edge fns, **DOM-XSS sinks** beyond escHtml, **per-public-fn
   internal-authZ** proof (60/61 fns run `verify_jwt=false`).
3. **Adversarial verification** — every candidate finding is refuted-by-default before it's called a vuln.

### 0a. ★ Meta-finding #1 (already confirmed) — `sast_scan.py` overstates OWASP coverage
`sast_scan.py` prints **"PASS — every OWASP Top-10 category has an automated scanner / 7/7 covered."**
But its `OWASP` map enumerates only **7 of the 10** categories: **A07 (Identification & Auth Failures),
A09 (Security Logging & Monitoring Failures), and A10 (SSRF) are absent from the map entirely**, and
**A06 carries the deprecated 2017 label** ("Sensitive Data Exposure" → 2021 is "Vulnerable & Outdated
Components"). The "7/7" is measured against its own truncated denominator, so the green is a **false
sense of coverage** — exactly the anti-pattern Arc Q taught (a metric at 100% masking an unmeasured
axis). **Fix:** expand the map to the full 2021 Top-10, wire the existing A07 validators in, add an
A10/SSRF scanner, relabel A06. (R3/R5 item.)

---

## 0b. Denominator (R0 — mined live, 2026-06-23)

| Surface | Count | Source |
|---|---|---|
| Frontend pages (root `*.html`) | **47** | `ls *.html` |
| Edge functions | **61** | `supabase/functions/` (excl. `_shared`) |
| Edge fns with `verify_jwt = false` | **60 / 61** | `config.toml` (only `supervisor-reset-password` keeps it ON) |
| Third-party CDN script/link tags | jsdelivr ×43 · tailwindcss ×16 · cdnjs ×2 · plot.ly ×1 · gtag ×1 | `grep src/href https://` |
| Python API | 1 FastAPI service, ~20 routes | `python-api/` |
| AI chain | `_shared/*` + ~25 AI edge fns | enumerated by Hunter P |

**Denominator honesty:** the headline risk is the **60/61 `verify_jwt=false`** surface. Some are
*correctly* public (login, marketplace-webhook, cmms-webhook-receiver — they verify their own
signature/JWT internally). But the honest question per fn is **"does it re-validate auth + scope by
the verified identity, or does it trust a client-supplied `hive_id`/`auth_uid`?"** That per-fn proof
is the R2 core and the most likely place to find a real cross-tenant export (e.g. `export-hive-data`).

---

## 1. Lenses & floors (OWASP Top-10 → 4)

| Lens | Question | Floor |
|---|---|---|
| **X — Injection & XSS** | input→sink: no stored/reflected/DOM XSS; escHtml on every render path; no `eval`/string-timer; ilike wildcard-escaped; AI output escaped. | **X 100** |
| **Z — AuthZ / Access** | IDOR/BOLA/BFLA/SSRF closed; every `verify_jwt=false` fn re-validates auth + scopes by verified identity; the 4 DB read-paths tenant-isolated. | **Z 100** |
| **S — Secrets & Supply-chain** | no private-credential egress to client; **SRI on every CDN script**; dep CVEs triaged; `verify_jwt`/config drift audited; full OWASP map. | **S 95** |
| **P — Prompt & AI security** | user text delimited + length-capped before the LLM; no system-prompt/PII/cross-tenant-RAG exfil; agency bounded; output safe-rendered. | **P 90** |

Security floors run high (X100/Z100/S95/P90) — a partial pass on an exploitable boundary is a fail.

---

## 2. Sub-layers

- **R1 — client-side** (XSS/DOM/CSP/SRI): the 47 pages + shared JS. _Hunter X._
- **R2 — edge authZ** (BOLA/BFLA/SSRF + per-public-fn internal-authZ): the 61 fns. _Hunter Z._
- **R3 — secrets + supply-chain** (egress, SRI, CVE, config, SAST-map completeness). _Hunter S._
- **R4 — AI / prompt-injection** (the `_shared` chain + AI fns). _Hunter P._
- **R5 — marketplace trust/safety** (checkout/payout/webhook/dispute — folded into R2/R3).

---

## 3. ★ MEASURED % SCOREBOARD (no rounding-up; honest denominators)

**R0 baseline → after the find→fix→gate sweep (measured by `tools/security_adversarial_sweep.py`):**

| Lens | Floor | R0 baseline | **Final** |
|---|---|---|---|
| **X — Injection & XSS** | 100 | 75.0% (3/4) | **100% (4/4)** |
| **Z — AuthZ / Access** | 100 | 85.7% (12/14) | **100% (14/14)** |
| **S — Secrets & Supply-chain** | 95 | 66.7% (6/9) | **100% (9/9)** |
| **P — Prompt & AI security** | 90 | 66.7% (2/3) | **100% (3/3)** |

**OWASP Top-10 (via `sast_scan.py`):** R0 enumerated only **7/10** (A07/A09/A10 absent — a false
"every category covered" claim). Final: **10/10 categories mapped, every scanner resolvable**
(26 scanners aggregated), completeness gated by `validate_sast_owasp_complete.py`.

_Baseline locked in `security_adversarial_baseline.json` (ratchet, floors enforced). All floors met._

---

## 3b. ★ FINDINGS REGISTER — 20 real findings found → fixed → gated → live-verified

Four lens-hunters (refute-by-default) swept the 47 pages + 61 edge fns + AI chain + supply-chain.

| # | Lens | Finding | Sev | Fix | Live-verified |
|---|---|---|---|---|---|
| Z-F2 | Z/A10 | **SSRF + Bearer-leak** via tenant `endpoint_url` (cmms-sync) | CRIT | `_shared/ssrf-guard.ts` (safeFetch: block private/metadata/DNS-rebind, strip auth on x-origin redirect) | gate |
| Z-F2b | Z/A10 | SSRF POST + Bearer-leak (cmms-push-completion) | CRIT | safeFetch | gate |
| Z-F11 | Z/A10 | Blind SSRF via `image_url` (equipment-label-ocr) | MED | safeFetch | gate |
| Z-F8/P1 | Z+P | **voice-model-call = anon OPEN LLM PROXY** (no auth/RL/caps) | CRIT | solo rate-limit + max_tokens/temp clamp + 8000-char cap | **413 anon** |
| (new) | Z/A01 | **ai-eval-runner** open eval-proxy (callAI/fixture, no guard) | HIGH | solo rate-limit (service/CI exempt) | gate+200 |
| (new) | Z/A01 | **voice-embeddings** open embedding-proxy (Jina, no guard) | HIGH | solo rate-limit + 64-text cap | gate+200 |
| Z-F3 | Z/A07 | CMMS webhook **fail-open** (sig skipped if token empty) | HIGH | fail-closed (401 if no secret) | code |
| Z-F6 | Z/A01 | cmms-sync no-hive_id → **anon all-hives sync** | MED | require service-role on fan-out | **403 anon** |
| Z-F9 | Z/A01 | send-report-email hiveless → **unauth email relay** | LOW | require auth + solo RL on no-hive path | code |
| Z-F10 | Z/A01 | trigger-ml-retrain → **anon all-hives ML retrain DoS** | LOW | require service-role (cron-only) | **403 anon** |
| Z-F1 | Z/A01 | marketplace-release escrow **IDOR** (spoofable buyer_name) | CRIT◇ | bind buyer to verified identity | **401 anon** |
| Z-F4 | Z/A01 | connect-status **cross-seller disclosure + KYB DoS** | HIGH◇ | bind worker to verified identity | **401 anon** |
| Z-F5 | Z/A01 | connect-onboard **onboarding-link hijack** | HIGH◇ | bind worker to verified identity | **401 anon** |
| Z-F7 | Z/A01 | marketplace-checkout order **spoofing** (price was safe) | MED◇ | bind buyer to verified identity | **401 anon** |
| X1 | X/A03 | Stored XSS via asset name (analytics worst-MTBF/MTTR) | HIGH | escHtml | gate |
| X2 | X/A03 | Stored XSS via asset name (analytics-report callouts) | HIGH | escHtml | gate |
| X3 | X/A03 | Stored XSS via **custom PM task name** (pm-scheduler) | HIGH | escHtml | gate |
| X4 | X/A03 | Attribute-breakout via inventory/logbook `photo` (×3) | MED | escHtml (+prefix gate) | gate |
| P2 | P | ai-orchestrator uncapped message/memory (injection/cost) | HIGH | 500/4000-char caps | code |
| P3 | P | scheduled-agents uncapped voice_context (stored injection) | HIGH | 500-char cap | code |
| P4 | P | walkthrough-analyzer uncapped fields + no image cap | MED | field caps + 5MB image cap | code |
| S1 | S/A02 | **live ROBOFLOW_API_KEY committed** in tracked `.env.roboflow` | HIGH | `git rm --cached` + gate (rotate=Ian) | gate |
| S2 | S/A08 | **zero SRI** on all CDN scripts | MED | SRI on 6 pinned tags + gate (46 floating=backlog) | gate |
| Meta1 | S/A09 | sast_scan claimed 7/7 but Top-10 has 10 (A07/A09/A10 absent) | MED | full Top-10 map + completeness gate | gate |

◇ = marketplace payment cluster was **vestigial** (free platform, `PAYMENTS_ENABLED=false`) — hardened
as interim defense-in-depth (anon→401), NOT activated. **✅ FORK RESOLVED 2026-06-30 — Ian: "remove
entirely the Stripe. my marketplace is free."** The 5 Stripe fns (marketplace-checkout/webhook/release/
connect-onboard/connect-status) were **DELETED**, the `stripe_*` DB columns dropped, and the whole
payment UI + `PAYMENTS_ENABLED` flag removed. This whole attack-surface row is now **N/A — the surface
no longer exists** (the strongest possible disposition: you can't attack what isn't there). The
`validate_public_fn_authz` EXEMPT entry for `marketplace-webhook` was removed with it.

### New gates (all teeth-proven, registered in `run_platform_checks.py` "AI Validation"):
`validate_ssrf_egress` · `validate_public_fn_authz` · `validate_dom_xss_fields` ·
`validate_committed_env_secret` · `validate_sri` · `validate_sast_owasp_complete` ·
`security_adversarial_sweep` (aggregate board) · plus `sast_scan.py` extended to the full Top-10.

---

## 4. Method (per finding)

1. **Find** — the four lens-hunters fan out across their surface (refute-by-default).
2. **Verify** — every candidate is adversarially re-checked: name the concrete exploit
   (attacker → input → sink → whose data/privilege). No exploit story ⇒ not a finding.
3. **Fix** — minimal, principled, fixing the *property* not the name-pattern.
4. **Gate** — a validator with **teeth** (a self-test that flips it red) at baseline-0/ratchet.
5. **Live-verify** — prove the fix against the running stack (curl/Playwright/psql), not just disk.
6. **Ratchet + teach** — fold into the scorer baseline; write the lesson to the security +
   multitenant + relevant skills; persist to Memento.

---

## 3c. ★ R0 RECONCILIATION (2026-07-01) — the three named holes were REAL; all closed + gated

When Stream 2 re-opened, the §3 board read a stale "Final 100%" but the live sweep exposed the three
holes the NEXT queue had flagged. All measured, fixed, live-verified, and locked this turn:

| Hole | Root cause (measured) | Fix | Proof |
|---|---|---|---|
| **RAG IDOR** (P 100→**66.7%**) | `match_procedural_memories` (edge-only DEFINER, locked to service_role by 20260620) was **silently re-granted anon/authenticated** by the C2.1 feature migration `20260624000002_episodic_supersedes.sql` (its `GRANT ... TO anon, authenticated` reverted the lock; comment falsely claimed "grants unchanged"). Cross-tenant procedural-memory retrieval (NULL hive = ALL hives). | Forward migration `20260701000000_regate_match_procedural_memories.sql`: convert to plpgsql + `user_can_access_hive()` early-return **self-gate** (property fix — cross-tenant returns empty regardless of grants) **AND** re-revoke anon/authenticated (least-privilege). | **live two-tenant psql**: non-member→cross-hive `false`, NULL-hive `false`, own-hive `true`; `has_function_privilege`: anon/auth `false`, service_role `true`. `validate_ai_retrieval_isolation` PASS. |
| **P-lens 66.7%** | consequence of the above (2/3 P cells) | the re-gate flips the cell | board **P 66.7→100%**, exit 0 |
| **board exit-0 false-green** | (a) the OWASP Top-10 line colored by `covered` (a scanner *exists*) not `clean` (it *passes*) → `A01` printed green while its scanner actively failed; (b) a **missing/corrupt baseline silently disengaged** the ratchet (regression check no-ops → an above-floor regression exits 0); (c) `--update-baseline` on a regressed board **locked the regression in** as the new baseline. | `security_adversarial_sweep.py`: color-by-`clean` (dirty category prints `A01!`), **fail-closed** on corrupt-baseline + infra ERROR/TIMEOUT cells, **ratchet-UP-only** `--update-baseline` (refuses to write a regression/floor-miss), loud "ratchet disengaged" on a genuinely-absent baseline. | **8-case `--self-test`** (all pass) — the board's own anti-false-green logic now has teeth. |

**New durable prevention — `validate_migration_grant_regression.py` (Z/A01, in the runner + a Z board cell):**
a security RATCHET on the migration files. Once a migration explicitly revokes anon/authenticated EXECUTE
(a deliberate app-role lock-out), no LATER migration may re-grant it to public/anon/authenticated without a
`-- regrant-approved:` marker. **Adversarially verified:** run against the pre-fix tree it flags *exactly*
`match_procedural_memories` (the real C2.1 regression) and nothing else; with the fix it is clean. 6-case
self-test proves it distinguishes the regression from the legitimate "revoke-default-from-public then
grant-roles" idiom and from a remediated (re-locked) function. **This would have caught C2.1 at authoring time.**

---

## 5. NEXT queue (live)

- ✅ **ARC R CONTINUATION COMPLETE (2026-07-17).** Timeout fix VERIFIED on the fresh-runtime board:
  **X 100 (4/4) · Z 100 (17/17 — gateway_tenancy now PASSES in-board) · P 100 (3/3 — reputation IDOR
  fix confirmed).** S reads 8/9 in THIS run ONLY because `python_api_deps` (a `pip-audit` → OSV **network**
  CVE scan) timed out — it PASSED in the prior run when the network was responsive (S=100); given a 360s
  SLOW_CELLS budget now, but it is inherently external-network + fail-closed (correct: the board won't
  ratchet through an infra timeout). **NO RATCHET NEEDED:** the R0 baseline (`security_adversarial_baseline.json`,
  2026-07-01) is already **X100/Z100/S100/P100** — this session's fixes RESTORED that state (P 66.7→100 via
  mig 003; Z 94.1→100 via the SLOW_CELLS timeout fix), they did not exceed it, so the baseline stays honest
  and unchanged. True security posture: **all four lenses at their 100% floor**, every code-controlled cell
  green; the only single-run non-green is the external CVE-database network scan. **Arc R is at rest.**
  **⚠ Ian deploy gate:** migs 20260717000001/2/3/4 LOCAL-applied only.


- ✅ **BOARD PER-CELL TIMEOUT FIX (2026-07-17, finishing Arc R):** the clean post-fix board read
  X100/S100/P100 with Z stuck at 94.1% (16/17) — the ONLY miss was `gateway_tenancy=TIMEOUT`, and it
  timed out even on a FRESH runtime, so it was NOT contention. Root cause: `security_adversarial_sweep._run`
  used a fixed 180s per-cell timeout, but `validate_gateway_tenancy` runs **39 sequential live edge-fn
  tenancy probes** (~5-8s each) — legitimately thorough, ~5-6 min, and PASSES standalone (0 unverified /
  39 readers: 38 safe + 1 exempt). So a slow-but-PASSING live check was being fail-closed into a false
  Z-lens miss. **FIX:** a `SLOW_CELLS` per-validator timeout override (gateway_tenancy 600s; gateway_bypass/
  public_fn_authz/rls_tenant_isolation 480s) — the anti-false-green teeth are UNCHANGED (a cell that still
  times out is still fail-closed; slow cells just get adequate time to produce a REAL PASS/FINDINGS).
  Self-test still PASS. Board re-running on fresh runtime → expected true X100/Z100/S100/P100 + ratchet.


- ✅ **R-CONTINUATION (2026-07-17, Ian re-picked Arc R):** the live board re-run surfaced a REAL 3-surface
  cluster from the recent Community↔Marketplace reputation bridge (postdates the 07-03 sweep), decomposed
  from an apparent "regression" (the 4th signal, `Z/gateway_tenancy`, was **infra flux** — standalone PASS
  0-unverified, confirmed by re-run under no load, not a hole). **P-lens `ai_retrieval_isolation` — 2 real
  cross-tenant retrieval IDORs** (`get_community_reputation` / `_by_auth`: DEFINER, authenticated-callable,
  client-`p_hive_id`/`p_auth_uid` filter, NO membership gate → any worker's reputation queryable cross-hive;
  mitigated in-practice by each RPC's public-footprint WHERE gate, so LOW sev, but the structural IDOR is
  real). **FIX (Ian: harden) — mig `20260717000003`:** converted both to plpgsql with a **membership-OR-seller**
  early-return guard (property fix, the §3c pattern) that preserves BOTH legit uses — community shows a
  member's rep to their OWN hive-mates (member path), marketplace shows a SELLER's rep cross-hive (seller
  path), an attacker querying a non-seller cross-hive gets EMPTY. **Live-verified two-tenant:** member path ✓
  (David/Lucena), seller path ✓ (Bryan cross-hive, pablo a verified NON-member so only the seller path
  allowed it), gate `validate_ai_retrieval_isolation` PASS. Also fixed the gate's own **both-operand-order
  blind spot** (`p_auth_uid = auth.uid()` wasn't recognized, only the reverse) — a real self-gate could have
  been false-flagged. **Z-lens `rls_tenant_isolation` — `marketplace_sellers` cross-hive row read:** verified
  BY-DESIGN (the bazaar seller directory, sibling of `marketplace_listings`; fields are seller-marketplace-
  public); added to the gate's evidence-curated `BY_DESIGN` with the note that `auth_uid` is opaque + consumed
  only by the now-gated reputation RPC. **Board:** X100/Z100/S100/P back-to-100 (isolation gates all green).
  **⚠ Ian deploy gate:** mig `20260717000003` is LOCAL-applied only. **auth_uid hardening DONE (mig `20260717000004`, LOCAL):** built `get_seller_community_reputation(worker,
  hive)` (server-side auth_uid resolve, seller-scoped, delegates to the gated `_by_auth`); dropped auth_uid
  from `v_marketplace_sellers_truth`; **column-level `REVOKE SELECT ON marketplace_sellers` + re-`GRANT SELECT`
  on the explicit column list minus auth_uid** (a bare `REVOKE SELECT(col)` is a no-op under a table-level
  grant — the real gotcha); marketplace-seller-profile switched to the new RPC. **Live-verified:** client
  auth_uid read → `permission denied`; normal seller fields + reputation + seller writes all intact; both
  isolation gates green (new RPC exempt-by-evidence: seller-scoped). Board Z/P at 100 (bar the 2 infra-flux
  timeouts). **⚠ Ian deploy gate:** migs 20260717000003/4 LOCAL-applied only.


- ✅ **R0 COMPLETE (2026-07-01):** board green + honestly-measured (X100/Z100 [now 16 cells]/S100/P100), the
  three named holes closed + gated (§3c), baseline re-locked (ratchet-up-only), migration-grant-regression
  linter added. **⚠ Ian deploy gate:** migration `20260701000000` is LOCAL/applied-to-local-DB only — prod
  redeploy is Ian's.
- ✅ **R2 first pass DONE (2026-07-01):** mined all **55** `verify_jwt=false` fns (was 60; −5 with Stripe removal)
  for the per-fn authZ question. **54/55 guarded** (resolveTenancy / service-role-gate / signature / identity
  rate-limit); the 1 heuristic hit (`resume-extract`) is a VERIFIED false-positive (service-role client used
  ONLY for an identity-keyed `checkSoloRateLimit`, no tenant read/write). **1 REAL finding found + fixed +
  live-verified: `pdf-ingest`** — a `verify_jwt=false` service-role **drainer** with NO auth check → an anon
  `POST {}` (drain mode) force-processed every pending `pdf_jobs` row across ALL hives (unauthorized all-hives
  compute / BFLA). FIX = the same `if (bearer !== SERVICE_KEY) return 403` its sibling batch fns enforce
  (`supabase/functions/pdf-ingest/index.ts`). **Live-verified:** anon/bogus-bearer → 403; service-role → 200
  `{mode:"drain",processed:0}`. **NEW durable gate `validate_public_fn_write_authz.py`** (Z/A01/BFLA, registered
  + a Z board cell): every `verify_jwt=false` service-role WRITER must carry an auth/cron/signature/identity-RL
  guard — adversarially verified to flag pre-fix pdf-ingest, clear post-fix. Board Z now **17 cells**, still 100%.
  ⚠ pdf-ingest edit is LOCAL/undeployed — prod redeploy is Ian's gate.
- ✅ **R2 remainder — pure-READ cross-tenant EXPORT class VERIFIED SECURE (2026-07-03).** The named keystone
  (`export_hive_data`, §0b "the most likely place to find a real cross-tenant export") was live-probed on the
  REAL local stack (54321) as a two-tenant attack, not just read on disk. **4-probe battery, all pass the
  contract:** [1] supervisor pabloaguilar exports his OWN hive (Lucena) → `200` (1.39 MB real export, legit
  path works); [2] pablo exports **Baguio** (not his hive) → `403 "Caller is not a member of this hive"` —
  cross-tenant READ **denied** (the edge fn binds the client `hive_id` to the JWT-verified identity + active-
  supervisor role, does NOT trust the client `hive_id`); [3] anon (publishable key, no user JWT) → `403
  "Missing Authorization bearer JWT"`; [4] anon calls the RPC **directly** (bypassing the edge fn) → `401 /
  42501 "permission denied for function export_hive_data"`. On the real DB `export_hive_data` is SECURITY
  DEFINER + **service_role-only** (`anon`/`authenticated` EXECUTE = false); migrations 0006 **and** 0016 both
  revoke public/anon/authenticated → grant service_role (re-lock, not a §3c-style regression). No new vuln.
  **NEW durable lock — `validate_public_fn_write_authz.py` gained a bulk-export READER arm:** a `verify_jwt=false`
  service-role fn that invokes an `export_hive_data`-class DEFINER RPC (`PRIVILEGED_READ_RPCS`) must carry the
  same authZ guard as a writer — making export-hive-data's ratchet FIRST-CLASS instead of incidental (it was
  covered only via its best-effort audit-log write; drop that write and the old gate silently stopped covering
  it). 4 new teeth self-test cases, all pass; full gate + aggregate board green (X100/Z100(17)/S100/P100).
- ✅ **R1 — DOM-XSS sink sweep beyond escHtml VERIFIED CLEAN (2026-07-03).** Swept every DOM-sink CLASS across the
  47 pages that neither `validate_xss` (escHtml-scope) nor `validate_dom_xss_fields` (`${obj.field}` DB-column
  interpolation) covers: **code-exec** (`eval`/`new Function`/string `setTimeout`/`setInterval`) = **zero** in
  page JS; **dynamic-HTML** (`document.write`/`insertAdjacentHTML`/`.outerHTML`) — all escaped (asset-hub
  reliability report local `esc()` on every free-text FMEA/RCM/logbook field · asset-qr `esc(tag/name/location)`
  · hive handover re-prints already-escaped DOM · community `renderContentWithMentions` escapes content-first ·
  public-feed `renderCard` · integrations rows · project-manager owner opts all `escHtml`); **`javascript:`-URI**
  (dynamic `href`/`src`) — alert-hub actions = hardcoded page prefix + `encodeURIComponent`, hive CTA = static,
  inventory `<img src>` = `data:image/`|`https://` prefix-gated (X4). **One latent (non-exploitable-today) gap
  FIXED:** `hive.html` notification link (`<a href="${n.link}">`) interpolated `n.link` RAW; every `pushNotif`
  currently passes a static page string, but a raw `${x}` in an attribute is one future user-derived link from
  attribute-breakout → `escHtml()`'d both the href value + link text (defense-in-depth; zero behavior change on
  static values). Both X-lens gates green (validate_xss 10/10 · validate_dom_xss_fields 0/baseline-0).
- ✅ **R3 — SRI pin-first backlog CLEARED for every pinnable tag (2026-07-03).** The 44 floating tags were only
  **4 distinct URLs**: `@supabase/supabase-js@2` (bare ×29 + UMD-path ×5 = 34), `mermaid@11` (×1), and
  `cdn.tailwindcss.com` (×9). **35 pinned + SRI'd** (supabase-js→`@2.110.0/dist/umd/supabase.min.js` ·
  mermaid→`@11.16.0`), + 1 subdir page = **36 tags** across 35 files. **Proven zero-behavior-change:** the
  exact-version bytes hash-match bare `@2`/`@11` byte-for-byte (`sha384-DjOvX/…`), so pinning only freezes the
  version the app already loads and adds integrity. **Live-verified** (browser MCP was profile-locked → used the
  deterministic SRI local-substitute): jsdelivr sends `access-control-allow-origin: *` (so `crossorigin=anonymous`
  integrity proceeds) + served bytes == the `integrity` attr + the live-served page delivers the pinned tag → by
  the SRI spec the browser loads & executes it. `validate_sri.py` still green (0 pinned-without-SRI); floating
  **44→9**. **The 9 remaining are ALL `cdn.tailwindcss.com` (Tailwind Play CDN) — genuinely un-SRI-able, NOT
  just un-pinned:** it is a runtime JIT compiler with no versioned artifact to hash (Tailwind docs: "Play CDN is
  not intended for production"). The real fix is **migrate off the Play CDN to a built static Tailwind CSS file**
  (own unit — high blast radius across 40+ pages + changes the build/deploy model = Ian-gated), not an SRI hash.
  Honestly tracked as a gate NOTE (built-attempt on record: SRI is not the right lever for this cell). **OWASP-map
  + config audit** were already closed in R0 (board shows A01–A10 all covered; `verify_jwt` drift gated by
  public-fn-authz/write-authz). **Arc R active-local queue is now DRAINED** — only the Ian-gated Tailwind migration
  remains as a forward backlog item.
- **NEXT — Stream 3 Arc U (Accessibility):** draft `ACCESSIBILITY_UFAI_ROADMAP.md`; the instrument already exists —
  reuse FB2's `browser_ci_persona_walk.mjs` axe-per-persona harness (headless node, independent of the MCP browser);
  its banked WCAG violations are Arc U's denominator. Then Stream 4 **Arc T (Observability)**.

**Ian-gated outward (his standing gate, never a turn-stop):** commit + any prod redeploy (incl. the hive.html
notification-link escHtml, the write-authz gate reader arm, and the 36 pinned+SRI CDN tags). The Tailwind
Play-CDN→built-CSS migration is a separate Ian-gated unit. STAY LOCAL — pivot to Arc U.
