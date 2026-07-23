---
name: skill-security
type: skill
source: skill:security
source_sha: 793a1490380b35c2
last_verified: 2026-07-13
supersedes: null
---
## skill · security

OWASP Top 10, auth audit, XSS/CSRF hardening, and security review. Triggers on "security", "vulnerability", "XSS", "CSRF", "harden", "auth", "injection", "exploit".

**Sections:** Security Agent · A secret-leak scanner must match the CREDENTIAL SHAPE, not a sensitive NOUN (2026-07-01, FB2) · A secret scanner must cover DOCS + config, not just code + `.env` — and verify each provider PREFIX against a real sample (2026-07-18, prod-leak) · Your Responsibilities · How to Operate · This Platform's Security Context · Security Checklist · XSS Audit Rules (learned from production bugs) · 1. Verify `escHtml` is defined per-file — never assume it exists · 2. Audit ALL innerHTML rendering paths — not just the main form · 3. Stored XSS is worse than reflected — prioritise accordingly · Auth Identity Audit Rules (learned from production patterns) · 4. LIKE Injection — Escape % and _ Before ilike Queries · 5. Flag auth-by-string-identity as HIGH even when RLS is enabled · Duplicate escHtml — Silent Single-Quote XSS · Dynamic href/src Attributes — escHtml Does NOT Stop `javascript:` URIs (Arc R R1, 2026-07-03) · Subresource Integrity — Pin to the Current-Resolved Version (Zero Behavior Change), and Know What Can't Be Pinned (Arc R R3, 2026-07-03) · RLS: distinguish a restricted INFRA role from an app-user isolation regression · Inline onclick Functions — Role Check Must Be Internal · Delete Scope in Hive Mode — `hive_id` Not `worker_name` · Missing Realtime DELETE Handler — Deleted Data Persists in UI · Realtime Subscription Isolation — a published table's RLS is the ONLY tenant boundary (Arc J, 2026-06-21) · The EDGE-FN read/write path: a SERVICE_ROLE fn keyed on a CLIENT hive_id must gate the caller FIRST (per-page bughunt v3 L6, 2026-07-20) · RLS-off + an anon grant = WORLD-WRITABLE; a column / verification-flag rule needs a BEFORE trigger, not RLS WITH CHECK (Marketplace PDDA, 2026-07-11) · A LEDGER/child table's INSERT WITH CHECK must scope to the PARENT's hive, and a SECURITY DEFINER sync-trigger must self-enforce that scope (Inventory PDDA, 2026-07-12, CONFIRMED EXPLOIT) · A self-COMPUTED credential written by the CLIENT is forgeable — RLS proves WHO, never WHETHER-EARNED (Dayplanner/Growth PDDA, 2026-07-12, CONFIRMED EXPLOIT) · status=approved Missing From Catalog Queries — Pending Items Exposed to Workers · Edge Function CORS — Static Origin Is a Misconfiguration · Rate Limiting and Bot Protection · Bot Registration — Cloudflare Turnstile (Free)

(Deep source: `skill:security` — retrieve this TOC to know WHICH section to read.)
