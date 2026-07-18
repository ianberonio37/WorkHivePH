# Bug-Hunt Denominator Expansion — external-taxonomy gap analysis (2026-07-17)

**Ask (Ian):** the bug-hunt roadmap's coverage may be stale — understand our denominator internally,
search authoritative taxonomies externally for bug classes we're **missing**, and gather best
practices for **handling** them.

**Method (framework dogfood):** Triage → **Audit→Synthesis**, inline + retrieve-first, no fan-out.
Internal: read `PER_PAGE_BUGHUNT_ROADMAP.md` + `sast_scan.py`. External: the **Night Crawler**
distilled OWASP **Top 10:2025**, **CWE Top 25 (2023)**, OWASP **Proactive Controls** into
`substrate/external/`. (The hardened crawler refused two junk sources live — the OWASP WSTG nav-stub
and an NN/g 404 — proving the guard works.)

> **Verification note — evidence discipline caught TWO false leads in this analysis** (both from a
> point-in-time memory + a wrong-directory check): (1) a memory said `sast_scan.py` overstates OWASP
> as "7/10"; the current code maps **10/10** and PASSes. (2) A `tools/`-only `ls` suggested 5 mapped
> validators were "missing"; they resolve at **repo root** (`_resolve()` checks root first). Both were
> corrected by verifying against current code + running the tool. The claims below are the survivors.

---

## 1 · Our denominator is TWO instruments (this is the key realisation)

- **Instrument A — the 8-phase per-page battery** (`PER_PAGE_BUGHUNT_ROADMAP.md`): P1 Smoke · P2
  Console/Network · P3 CRUD-at-DB · P4 Inputs/edge (XSS, SQLi) · P5 Role/RLS/authZ + UI-only-auth-
  bypass · P6 Concurrent-edit · P7 UI-locks/recovery · P8 Visual. **Scored per page.** Covers the
  *functional + access-control* axes.
- **Instrument B — the platform SAST layer** (`sast_scan.py`): **VERIFIED 10/10 OWASP-2021 categories
  covered, 26 scanners aggregated, PASS**, backed by ~150 `validate_*.py`. Covers the *security* axes
  **platform-wide** (not per-page).

**So the platform is NOT blind to security** — A02 misconfig (`validate_cors_wildcard`, `validate_csp`),
A04/2021-crypto (`hardcoded_secrets`, `committed_env_secret`), A07 authN (`login_proxy_lockout`,
`signup_enumeration_safety`), A08 integrity (`sri`), A09 logging (`observability`,
`edge_observed_coverage`), A10 SSRF (`ssrf_egress`) all have scanners. The "security gap" my first
draft implied does **not** exist at the platform level.

---

## 2 · The REAL, verified gaps

### Gap A — OWASP 2021 → 2025 taxonomy drift *(crawl-verified)*
`sast_scan.py` maps the **2021** Top 10. The crawl shows OWASP has moved to **2025**, which reshuffles
and adds emphasis:
- **A03:2025 Software Supply-Chain Failures** — elevated to #3 (was A06 "Vulnerable Components"). Our
  coverage is one validator (`validate_python_api_deps`); 2025 treats the whole supply chain (lockfile
  integrity, build/CI, transitive deps, CDN SRI) as top-tier. **Deepen it.**
- **A10:2025 Mishandling of Exceptional Conditions** — a **new** named category (error-leakage,
  fail-open, unhandled rejections). We have no scanner named for it; P7 covers empty-vs-error *UI* only.
- Relabel the map 2021→2025 so the coverage claim tracks the current standard.

### Gap B — CWE classes, RE-SCOPED against verified reality *(a live grep corrected my first draft)*
A grep for `storage.from().upload(` returns **zero hits** — the platform has **no server-side file
storage**; files are read **client-side** (resume → AI-extract, logbook photo → data-URI) and never
persisted. That changes the picture:
- **CWE-22 Path Traversal — N/A** (no server file paths exist).
- **CWE-434 Unrestricted Upload — LOW** (no bucket, no exec) — the classic risk is absent.
- **The real residual is client-side: a missing `file.size` cap** (DoS — a huge file OOMs
  FileReader/canvas/the AI extractor). **`validate_file_upload_safety.py` BUILT + registered** (advisory
  gate `file-upload-safety`, `--selftest`): of **9 file-upload surfaces, 2 have no size cap —
  `integrations.html` + `inventory.html`**; the other 7 (incl. resume) handle `file.size`. Heuristic
  v1 flags absence-of-size-awareness reliably; "guarded" is a weaker signal (references vs enforces) —
  a v2 should parse the actual cap comparison.
- **CWE-352 CSRF — LOW** (JWT-bearer, no cookie-auth), but a cheap static assertion is still worth it.

### Gap C — the per-page battery doesn't SCORE security per-page
Security lives in Instrument B (platform SAST), not the 8 phases. That's a legitimate split — but a
reader seeing "logbook 73%" can misread it as "security 73%." **Cross-reference SAST coverage into the
per-page roadmap** (a per-page "security = platform-gated ✓" column), so the two instruments compose.

### Gap D — non-security classes aren't battery phases
**Accessibility (WCAG/axe), Performance (Core Web Vitals/render-budget), i18n (EN/FIL coverage)** have
gates but aren't scored per-page phases. A full "bug hunt" denominator should promote them.

---

## 3 · Candidate additions (proposed — Ian prioritises)

Focused, not a rewrite — the security base is already strong:
1. **Refresh `sast_scan.py` to OWASP 2025** — relabel; add a supply-chain-depth check (lockfile/SRI/
   transitive) for A03; add an exceptional-conditions / error-leak scanner for A10.
2. **Build 3 validators** (highest-value first): `validate_file_upload_safety.py` (CWE-434) →
   `validate_path_traversal.py` (CWE-22) → `validate_csrf_surface.py` (CWE-352).
3. **Cross-ref SAST into the per-page roadmap** — add a "security (platform SAST)" column so the two
   instruments compose into one honest coverage picture.
4. **Promote A11y / Perf / i18n** into scored battery phases (P9/P10/P11) or cross-ref their gates.

## 4 · Best practices to HANDLE (from Proactive Controls + WSTG + our own method)

1. **Traceable denominator** — tag every scanner & finding with its **OWASP-2025 + CWE id**, so
   coverage % maps to a named standard (kills the "7/10 vs 10/10" ambiguity this analysis hit).
2. **OWASP ASVS as the requirements superset** — Proactive Controls points to ASVS; use it as the
   master checklist behind the scanners.
3. **Threat-model (STRIDE) per high-blast-radius page** — for A06 Insecure Design, the one class you
   can't scan for.
4. **Prioritise by KEV / exploitability** — CWE Top-25 ranks by real-world exploitation; file-upload &
   path-traversal outrank CSRF here.
5. **Keep our winning method** — per-page full-stack **live-MCP**, **live-confirm-before-claiming**,
   **gate-every-fix** (Hardening Loop), denominator mined from the live registry. The method is
   best-practice; only *breadth of classes* + *taxonomy freshness* need work.
6. **WSTG as the per-page security sub-checklist** — its 12 categories (INFO/CONF/IDNT/ATHN/ATHZ/SESS/
   INPV/ERRH/CRYP/BUSL/CLNT/APIT) are a ready per-page test list.

---

## 5 · Bottom line

The method is excellent and security coverage is **broad and OWASP-2021-complete** (10/10, 26 scanners).
The denominator is **not** 40%-empty (my first draft was wrong and is corrected above). The genuine,
verified gaps are narrow and actionable: **(A)** refresh 2021→2025 (supply-chain + exceptional-
conditions), **(B)** three CWE classes with zero scanners (**file-upload, path-traversal, CSRF**),
**(C)** compose the per-page battery with the platform SAST so security isn't misread as per-page-
untested, **(D)** promote a11y/perf/i18n to scored phases. That is a focused half-dozen additions,
each mapped to a named OWASP-2025 / CWE id — not a doubling.
