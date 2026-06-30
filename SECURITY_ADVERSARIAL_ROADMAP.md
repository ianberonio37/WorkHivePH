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

◇ = marketplace payment cluster is **vestigial** (free platform, `PAYMENTS_ENABLED=false`) — hardened
as interim defense-in-depth (anon→401), NOT activated. **Disposition fork for Ian: REMOVE the 5
Stripe fns (per the free-platform decision) vs keep-hardened.**

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

## 5. NEXT queue (live)

- R0: spine ✓ · scorer (building) · baseline-lock.
- Triage the 4 hunter reports → verify → fix keystone(s) → gate → ratchet.
- Fix the SAST OWASP-map gap (A07/A09/A10 + A06 relabel).
- Per-public-fn internal-authZ proof for the 60 `verify_jwt=false` fns (R2 core).
- SRI sweep across the CDN tags (R3).
- Register scorer + new gates in the platform runner; teach skills.

**Ian-gated outward (his standing gate, never a turn-stop):** commit + any prod redeploy. STAY LOCAL.
