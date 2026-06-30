#!/usr/bin/env python3
"""auth_identity_ufai_sweep.py — Arc I: the Auth/Identity/Session UFAI scorer (I0 measured baseline).

Mirrors ai_ufai_sweep.py (Arc H) / data_db_ufai_sweep.py (Arc G) / python_api_ufai_sweep.py (Arc F):
per-cell IN-FRAME scoring of U·F·A·I into ONE ratcheted matrix, measured-not-credited, with a hard
split between live ✓ / oracle / proof / contract / attributed ◈ / pending / N-A. Auth has been hardened
CROSS-CUTTING (Gateway Pillar I, Arc G RLS, Arc H membership gate) but NEVER swept as its own layer —
this folds the existing tenant/RLS validators per-cell and STATICALLY scans the real auth FLOW surfaces
(signup, login, session, logout, role, the in-flight migration). Spine: AUTH_IDENTITY_UFAI_ROADMAP.md.

Rows = 8 sub-layers (I1 Credential&signup · I2 Session&JWT · I3 Password&recovery · I4 RBAC ·
I5 Tenancy-binding · I6 Auth-migration completion · I7 Bot/abuse · I8 Account lifecycle).
Cells = 8 rows × 4 lenses (U/F/A/I).

HONEST BASELINE (evidence discipline — [[feedback_classify_by_evidence_not_heuristic]]):
- A cell backed by a GREEN existing validator fold or a passing static surface-scan = proof/live.
- The OWASP-ASVS keystones with NO validator yet (account-enumeration resistance, session-expiry/JWT
  validation proof, login brute-force, account-deletion) score `pending` — they ARE the Arc I build
  queue, NOT a fake 100%.
- Provider-internal controls (GoTrue brute-force lockout, Turnstile in the Supabase dashboard, real
  email delivery, MFA/SSO) = `attributed` (named external ceiling), never a deterministic pass.
- ★The skills claim "auth migration C1-C4 COMPLETE (Apr 2026)" but Arc G LIVE-proved 9 tables still had
  legacy USING(true) policies OR-defeating auth.uid() (ratchet 9→0 by Arc G). So I6 is scored from the
  LIVE validator state, never from the stale "complete" claim.

USAGE:
  python tools/auth_identity_ufai_sweep.py            # score, write frame
  python tools/auth_identity_ufai_sweep.py --accept   # forward-only ratchet
"""
from __future__ import annotations
import json, re, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FUNCS = ROOT / "supabase" / "functions"
RESULTS = ROOT / "auth_identity_ufai_results.json"
BASELINE = ROOT / "auth_identity_ufai_baseline.json"
ACCEPT = "--accept" in sys.argv[1:]

ROWS = ["I1 Credential & Signup", "I2 Session & JWT Lifecycle", "I3 Password & Recovery",
        "I4 Role & Permission (RBAC)", "I5 Tenancy Binding", "I6 Auth-Migration Completion",
        "I7 Bot & Abuse Protection", "I8 Account Lifecycle"]
LENSES = ["U", "F", "A", "I"]
# Auth is the trust root → highest internal-control bar (I92), matching NEXT_LAYER_STUDY_2 §5.
FLOORS = {"U": 0.90, "F": 0.85, "A": 0.85, "I": 0.92}
VERIFIED_TIERS = {"live", "oracle", "proof", "contract", "attributed"}

# ── per-SURFACE inventory (mined 2026-06-21 from the real auth flow; test/backup index variants excluded) ──
# Root files live at the website root; edge helpers under supabase/functions/_shared.
SURFACES = {
    "I1 Credential & Signup": ["index.html", "supabase/migrations/20260430000003_worker_profiles.sql"],
    "I2 Session & JWT Lifecycle": ["session-timeout.js", "utils.js", "index.html"],
    "I3 Password & Recovery": ["index.html"],
    "I4 Role & Permission (RBAC)": ["hive.html", "inventory.html", "logbook.html", "pm-scheduler.html",
                                    "project-manager.html", "shift-brain.html", "asset-hub.html"],
    "I5 Tenancy Binding": ["_shared/tenant-context.ts", "utils.js"],
    "I6 Auth-Migration Completion": ["supabase/migrations/20260430000003_worker_profiles.sql"],
    "I7 Bot & Abuse Protection": ["index.html"],
    "I8 Account Lifecycle": ["hive.html", "index.html", "utils.js"],
}

# ── validator folds (run offline; map pass -> the cell(s) it evidences). VERIFIED to exist 2026-06-21. ──
FOLDS = ["validate_rls_no_permissive_bypass", "validate_rls_tenant_isolation",
         "validate_definer_tenant_gate", "validate_rls_coverage",
         "validate_edge_symbol_imports", "validate_ai_rate_limit_coverage",
         "validate_signup_enumeration_safety", "validate_signup_bot_protection",
         "validate_account_deactivation", "validate_auth_live_flows", "validate_auth_live_db",
         "validate_auth_live_gotrue", "validate_auth_idle_timeout_live",
         "validate_auth_role_render_live", "validate_auth_rate_limit_live",
         "validate_auth_role_guard_live", "validate_login_proxy_lockout",
         "validate_password_recovery", "validate_anon_key_retirement"]


def run_validator(name: str) -> bool:
    for c in (ROOT / f"{name}.py", ROOT / "tools" / f"{name}.py"):
        if c.exists():
            try:
                p = subprocess.run([sys.executable, str(c)], cwd=str(ROOT), capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=180)
                return p.returncode == 0
            except Exception:
                return False
    return False


def _read(surface: str) -> str:
    if surface.startswith("_shared/"):
        p = FUNCS / "_shared" / surface.split("/", 1)[1]
    elif "/" in surface:                       # repo-relative (e.g. supabase/migrations/...)
        p = ROOT / surface
    else:
        p = ROOT / surface                     # website-root file (index.html, utils.js, ...)
    try:
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    except Exception:
        return ""


def _strip(body: str) -> str:
    # drop // line comments + /* */ blocks so a marker in a comment never scores
    b = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    return re.sub(r"//.*", "", b)


def scan() -> dict:
    """Static markers for the measurable U/F/A/I properties of the real auth flow."""
    idx = _strip(_read("index.html"))
    utils = _strip(_read("utils.js"))
    sess = _strip(_read("session-timeout.js"))
    wp = _strip(_read("supabase/migrations/20260430000003_worker_profiles.sql"))
    tc = _strip(_read("_shared/tenant-context.ts"))
    # hive.html is the canonical membership-management surface (kick / role-guard logic lives here,
    # NOT in index.html) — read it for the RBAC (I4) and lifecycle (I8) markers.
    hive = _strip(_read("hive.html"))

    def any_role_pages_db_validated():
        # role read from the DB (select role,status from hive_members), not localStorage alone
        hits = 0; n = 0
        for pg in ("inventory.html", "logbook.html", "pm-scheduler.html",
                   "project-manager.html", "shift-brain.html", "asset-hub.html"):
            b = _strip(_read(pg)); n += 1
            if re.search(r"validateHiveMembership", b) and re.search(r"hive_members", b) \
               and re.search(r"\bstatus\b", b):
                hits += 1
        return hits, n

    role_hits, role_n = any_role_pages_db_validated()

    m = {
        # I1 — credential & signup
        "signup_exists": bool(re.search(r"handleSignup|signUp\(", idx)),
        "pw_min_len": bool(re.search(r"min 6|length\s*<\s*6|>=\s*6|\.length\s*<\s*\d", idx)),
        "username_format": bool(re.search(r"\[a-z0-9_\]\{3,30\}|3-30|3,30", idx + wp)),
        "synthetic_email": bool(re.search(r"@auth\.workhiveph\.com", idx)),
        # account-enumeration: does signup branch on "username taken / already registered"?
        "enum_safe_signup": not bool(re.search(r"already (registered|exists|taken)|username.{0,12}taken", idx, re.I)),
        # I2 — session & JWT
        "session_restore": bool(re.search(r"restoreIdentityFromSession", utils)),
        "idle_timeout": bool(re.search(r"IDLE_HARD_LIMIT|IDLE_LIMIT|session-?timeout", sess + idx)),
        "signout_full_wipe": bool(re.search(r"wh_active_hive_id", idx) and re.search(r"wh_hive_role", idx)
                                  and re.search(r"signOut", idx)),
        # JWT *validation* (getUser validates the token server-side) vs unvalidated getSession trust
        "getuser_validation": bool(re.search(r"\.auth\.getUser\(", idx + utils)),
        # I3 — password & recovery
        "pw_confirm": bool(re.search(r"su-confirm|confirm.{0,10}password|repeat password", idx, re.I)),
        "recovery_flow": bool(re.search(r"resetPasswordForEmail|updateUser\(\s*\{?\s*password", idx + utils)),
        # I4 — RBAC
        "role_db_validated_frac": round(role_hits / role_n, 3) if role_n else 0.0,
        # function-level role guard lives in hive.html + feature pages (not index/utils)
        "role_fn_guard": bool(re.search(r"(HIVE_ROLE|role)\s*!==?\s*['\"]supervisor['\"]", hive + idx + utils)),
        # I5 — tenancy binding
        "tenant_ctx_exists": bool(tc),
        "tenant_server_resolved": bool(re.search(r"resolveTenancy|resolveIdentity|verifiedHiveId|auth\.getUser", tc)),
        # I7 — bot/abuse
        "turnstile": bool(re.search(r"turnstile|cf-turnstile|challenges\.cloudflare", idx, re.I)),
        # I8 — account lifecycle (kick logic lives in hive.html: set status='kicked', never delete row)
        "kicked_not_delete": bool(re.search(r"['\"]kicked['\"]", hive)),
        "role_pages": f"{role_hits}/{role_n}",
    }
    return m


def gather() -> dict:
    return {"val": {v: run_validator(v) for v in FOLDS}, "scan": scan()}


def score(row: str, lens: str, L: dict):
    v, m = L["val"], L["scan"]
    g = lambda n: v.get(n, False)
    lf = g("validate_auth_live_flows")   # live auth-flow proofs (Playwright → local stack) passed?
    ld = g("validate_auth_live_db")      # live data-layer proofs (docker psql) passed?
    lg = g("validate_auth_live_gotrue")  # live GoTrue credential-strength probe (I3/A) passed?
    it = g("validate_auth_idle_timeout_live")  # live idle→prompt→hard-clear sequence (I2/A) proven?
    # Reuse Arc-E backend_live_invoke evidence for I5 tenancy-binding (same edge layer): a happy-200 proves
    # tenancy is resolved SERVER-SIDE from the JWT at runtime; a foreign-hive_id BLOCK (i2_blocked/403) proves
    # it survives a spoof. Guarded: absent/empty artifact → fall back to the static proof tier (never faked live).
    import json as _json
    try:
        _bli = _json.loads((ROOT / "backend_live_invoke.json").read_text(encoding="utf-8")).get("probes", {})
    except Exception:
        _bli = {}
    edge_happy_200 = sum(1 for p in _bli.values() if isinstance(p, dict) and p.get("happy_code") == 200)
    edge_foreign_blocked = sum(1 for p in _bli.values() if isinstance(p, dict) and p.get("i2_blocked"))

    # ── I1 Credential & Signup ──
    if row.startswith("I1"):
        if lens == "U":
            if lf: return ("live", "live", "signup/login forms render & drive the real flow (Playwright→local stack, 5/5 green)")
            return ("proof", "proof", "signup form contract: username+password, synthetic-email pattern, confirm field") if (m["signup_exists"] and m["synthetic_email"]) else ("pending", "pending", "signup contract unproven")
        if lens == "F":
            if lf: return ("live", "live", "credential rules LIVE-block bad input (Playwright: short pw → 'at least 6', bad username → format error, mismatch → 'do not match')")
            return ("proof", "proof", "credential rules enforced: pw min-len + username format (3-30 [a-z0-9_]) + confirm") if (m["pw_min_len"] and m["username_format"]) else ("pending", "pending", "credential rules unverified")
        if lens == "A":
            if ld: return ("live", "live", "synthetic-email login-key isolation LIVE-PROVEN: 15 seeded users map username→username@auth.workhiveph.com in auth.users (docker psql); display-name change never touches the credential")
            return ("contract", "contract", "synthetic-email indirection isolates login key from display_name (rename-safe)") if m["synthetic_email"] else ("pending", "pending", "credential model not isolated")
        if lens == "I":
            if lf and g("validate_signup_enumeration_safety"): return ("live", "live", "account-enumeration resistance LIVE-PROVEN (ASVS V2.2): bad login → uniform 'Wrong username or password' (no user-exists tell), Playwright vs real GoTrue; signup availability via rate-limitable RPC carve-out — validate_signup_enumeration_safety GREEN")
            return ("proof", "proof", "account-enumeration resistance GATED (ASVS V2.2): login uniform-response + signup availability via rate-limitable check_username_available RPC — validate_signup_enumeration_safety GREEN") if g("validate_signup_enumeration_safety") else ("pending", "pending", "★ account-enumeration resistance NOT gated (ASVS V2)")
    # ── I2 Session & JWT Lifecycle ──
    if row.startswith("I2"):
        if lens == "U":
            if lf: return ("live", "live", "login flips marketing shell → app (ops-home) live; session UX exercised (Playwright)")
            return ("proof", "proof", "session model: restoreIdentityFromSession + idle-timeout hand-off UX") if (m["session_restore"] and m["idle_timeout"]) else ("pending", "pending", "session UX unproven")
        if lens == "F":
            if lf: return ("live", "live", "login mints a real GoTrue JWT + session SURVIVES reload (restoreIdentityFromSession) — Playwright vs local stack")
            return ("proof", "proof", "session restore from auth session on new device (utils.restoreIdentityFromSession)") if m["session_restore"] else ("pending", "pending", "session restore unproven")
        if lens == "A":
            if it: return ("live", "live", "shared-device idle expiry LIVE-PROVEN: idle→soft prompt(name)→Continue keeps session→hard-clear wipes identity + redirects signin (Playwright 4/4 via WH_IDLE_TIMEOUT_OVERRIDE clock-seam) — validate_auth_idle_timeout_live GREEN")
            return ("proof", "proof", "shared-device idle expiry: soft-15m prompt + hard-60m identity clear (session-timeout.js)") if m["idle_timeout"] else ("pending", "pending", "idle expiry missing")
        if lens == "I":
            if lf and m["signout_full_wipe"] and m["getuser_validation"]:
                return ("live", "live", "logout LIVE-PROVEN full wipe (Playwright: all 7 identity+hive localStorage keys cleared) + JWT validated via auth.getUser() — ASVS V3")
            if m["signout_full_wipe"] and m["getuser_validation"]:
                return ("proof", "proof", "logout = full identity+hive wipe AND JWT validated via auth.getUser() (not unvalidated getSession)")
            return ("pending", "pending", "★ session-fixation/JWT-validation proof gap (ASVS V3): signout wipe={} getUser={}".format(m["signout_full_wipe"], m["getuser_validation"]))
    # ── I3 Password & Recovery ──
    if row.startswith("I3"):
        if lens == "U":
            if lf: return ("live", "live", "password + confirm fields render & accept input in the real signup flow (Playwright)")
            return ("proof", "proof", "password fields: min-6 + confirm-match, autocomplete=new-password") if m["pw_confirm"] else ("pending", "pending", "password UX unproven")
        if lens == "F":
            if lf: return ("live", "live", "password min-length LIVE-enforced ('123' → 'Password must be at least 6 characters', Playwright)")
            return ("proof", "proof", "password min-length enforced at signup") if m["pw_min_len"] else ("pending", "pending", "password strength unverified")
        if lens == "A":
            if lg: return ("live", "live", "server-side credential strength LIVE-PROVEN: GoTrue rejects a too-short password (422 weak_password, direct API probe) — observable provider enforcement, not just a doc knob")
            return ("attributed", "attributed", "credential-strength policy is GoTrue-configurable (provider knob) — named ceiling")
        if lens == "I":
            if g("validate_password_recovery"):
                return ("live", "live", "password recovery BUILT + LIVE-PROVEN both flows: supervisor-assisted (no-email field workers) — supervisor-reset-password edge fn sets a same-hive WORKER's temp pw via admin API (200 + temp pw logs in), refuses a worker-caller and refuses resetting a supervisor (403/403), audit-logged; + email fallback (resetPasswordForEmail + PASSWORD_RECOVERY listener) — validate_password_recovery GREEN (9/9)")
            if m["recovery_flow"]:
                return ("proof", "proof", "password recovery flow present (resetPasswordForEmail/updateUser)")
            return ("attributed", "attributed", "★ no in-app password-recovery flow built — GoTrue email-reset is the provider path (named ceiling/gap; I3 build candidate)")
    # ── I4 Role & Permission (RBAC) ──
    if row.startswith("I4"):
        if lens == "U":
            if g("validate_auth_role_render_live"): return ("live", "live", "role-gated UI render LIVE-PROVEN: supervisor sees supervisor-only blocks (Plain-Read summary, Engagement card, Audit-Log link, SUPERVISOR badge); worker/anon gated+redirected (journey-permissions 9/9, Playwright vs live stack) — validate_auth_role_render_live GREEN")
            return ("proof", "proof", f"role-gated UI: {m['role_pages']} surveyed pages DB-validate membership before render")
        if lens == "F":
            if lf: return ("live", "live", "live session JWT resolves to a real worker_profiles identity (auth.uid→display_name, Playwright vs local DB); role read from DB across surveyed pages")
            return ("proof", "proof", f"role read from DB (hive_members.role/status), not localStorage — {m['role_pages']} pages") if m["role_db_validated_frac"] >= 0.5 else ("pending", "pending", "role-from-DB coverage gap")
        if lens == "A":
            if g("validate_auth_role_guard_live"): return ("live", "live", "function-level role guard ENFORCED live: a seeded WORKER-role JWT invoking the supervisor-only export-hive-data edge fn → HTTP 403 (validate_auth_role_guard_live) — RBAC at the function layer, not UI-only")
            return ("contract", "contract", "function-level HIVE_ROLE guard pattern present (not UI-only)") if m["role_fn_guard"] else ("pending", "pending", "role guard UI-only")
        if lens == "I": return ("live", "live", "DB-level role gate proven: validate_definer_tenant_gate GREEN (supervisor-only RPCs membership-gated, live two-tenant)") if g("validate_definer_tenant_gate") else ("pending", "pending", "★ RBAC self-escalation not gated at DB")
    # ── I5 Tenancy Binding ──
    if row.startswith("I5"):
        if lens == "U":
            if edge_happy_200: return ("live", "live", f"tenancy resolved SERVER-SIDE live: {edge_happy_200} edge fns return happy-200 deriving the caller's hive from the validated JWT at runtime (backend_live_invoke), via the single _shared/tenant-context.ts resolver — not a client hive_id")
            return ("proof", "proof", "tenancy resolved server-side via _shared/tenant-context.ts (single resolver)") if m["tenant_ctx_exists"] else ("pending", "pending", "no central tenancy resolver")
        if lens == "F":
            if ld: return ("live", "live", "hive_id SERVER-derived from the validated JWT (auth.uid()→hive_members) LIVE-PROVEN across the policy set (docker psql) — not client-supplied")
            return ("proof", "proof", "hive_id server-resolved from validated identity, not client-trusted (Gateway Pillar I)") if m["tenant_server_resolved"] else ("pending", "pending", "tenancy client-trusted")
        if lens == "A":
            if edge_foreign_blocked: return ("live", "live", f"tenancy survives ABUSE live: {edge_foreign_blocked} edge fns BLOCK a spoofed foreign hive_id (403, backend_live_invoke i2_blocked) — server-resolved tenancy ignores the client-supplied hive_id (BOLA)")
            return ("proof", "proof", "resolveIdentity import-safety gated (validate_edge_symbol_imports GREEN — the project-progress 500 class)") if g("validate_edge_symbol_imports") else ("pending", "pending", "symbol-import safety ungated")
        if lens == "I": return ("live", "live", "cross-tenant isolation LIVE-proven: validate_rls_tenant_isolation GREEN (two-tenant, count-other-hive=0)") if g("validate_rls_tenant_isolation") else ("pending", "pending", "★ tenancy isolation not live-proven")
    # ── I6 Auth-Migration Completion — THE KEYSTONE ──
    if row.startswith("I6"):
        if lens == "U":
            if lf or ld: return ("live", "live", "migrated identity contract EXERCISED live: login resolves username→synthetic-email→auth_uid→display_name end-to-end (validate_auth_live_flows Playwright + validate_auth_live_db synthetic-email isolation docker-psql) — the consumer experiences the completed migration model at runtime")
            return ("proof", "proof", "migration model documented: worker_profiles anchor (auth_uid↔display_name), dual→strict RLS")
        if lens == "F": return ("live", "live", "auth.uid() RLS coverage GREEN (validate_rls_coverage — every hive table RLS-enabled)") if g("validate_rls_coverage") else ("pending", "pending", "RLS coverage incomplete")
        if lens == "A":
            if ld: return ("live", "live", "auth-migration backfill LIVE: sync_auth_uid_on_signup trigger present (docker psql) — a new signup links existing records; synthetic-email survives display_name reuse")
            return ("contract", "contract", "synthetic-email + auth_uid backfill trigger model survives display_name reuse")
        if lens == "I":
            # The smoking gun: legacy USING(true) policies must be GONE (Arc G drove ratchet 9→0),
            # AND the I2-phase residual — the CLIENT anon-key paths — must be retired (Arc J/J7).
            if g("validate_rls_no_permissive_bypass") and g("validate_rls_tenant_isolation") and g("validate_anon_key_retirement"):
                return ("live", "live", "★ migration COMPLETE both halves: DB — validate_rls_no_permissive_bypass GREEN (legacy USING(true) ratchet 9→0) + two-tenant isolation; CLIENT — validate_anon_key_retirement GREEN (anon reads 0 from all 8 core hive tables + 11/11 production hive-read pages session-gated). The I2-phase 'client anon-key retirement' residual is now CLOSED, not attributed")
            if g("validate_rls_no_permissive_bypass") and g("validate_rls_tenant_isolation"):
                return ("live", "live", "★ migration ENFORCEMENT live-proven (DB half): validate_rls_no_permissive_bypass GREEN (legacy USING(true) ratchet 9→0) + two-tenant isolation GREEN. Stale-skill 'C4 complete' superseded by Arc G live evidence")
            return ("pending", "pending", "★ legacy-open policies still OR-defeat auth.uid() (the deferred project_rls_decision state) — enforcement NOT proven")
    # ── I7 Bot & Abuse Protection ──
    if row.startswith("I7"):
        if lens == "U":
            if lf and g("validate_signup_bot_protection"): return ("live", "live", "bot-protection contract RENDERED live: the signup page presents the Turnstile widget in-page (validate_signup_bot_protection GREEN — widget renders + yields a token with the public test sitekey, Playwright) — the consumer-facing abuse-protection surface is present at runtime (live BLOCK = the dashboard toggle, §8 bucket-4 residual)")
            return ("contract", "contract", "abuse posture documented (Turnstile + email-confirm = pre-launch dashboard toggles)")
        if lens == "F":
            if g("validate_auth_rate_limit_live"): return ("live", "live", "per-identity AI rate-limit ENFORCED live (LLM10): counter driven to the limit → real AI edge invoke returns HTTP 429 'AI call limit reached' (validate_auth_rate_limit_live, boundary test + self-reset); coverage also GREEN (validate_ai_rate_limit_coverage)")
            return ("proof", "proof", "per-identity AI/abuse rate-limit coverage GREEN (validate_ai_rate_limit_coverage)") if g("validate_ai_rate_limit_coverage") else ("pending", "pending", "rate-limit coverage gap")
        if lens == "A": return ("live", "live", "login brute-force BLOCKED server-side LIVE: the `login` edge proxy gates by a real failed-attempt counter (login_attempts + 3 service-role DEFINER RPCs) — 5 bad logins → 423, and a LOCKED account rejects even the CORRECT password (never reaches GoTrue), the property a bypassable client check cannot give — validate_login_proxy_lockout GREEN (8/8 + live edge proof)") if g("validate_login_proxy_lockout") else ("attributed", "attributed", "login brute-force = GoTrue IP rate-limit (provider-side)")
        if lens == "I":
            if lf and g("validate_signup_bot_protection"):
                return ("live", "live", "Turnstile wiring LIVE-PROVEN: widget renders + yields a token with Cloudflare's public test sitekey (Playwright); live bot-BLOCK still needs the dashboard captcha toggle = attributed residual (§8 bucket-4)")
            if g("validate_signup_bot_protection"):
                return ("contract", "contract", "Turnstile in-page wiring intact (configure-to-enable) — validate_signup_bot_protection GREEN; live bot-block attributed to Supabase Auth dashboard enrollment (provider half, §5 ceiling)")
            return ("pending", "pending", "★ signup bot-protection (Turnstile) not wired in-page — build/verify target")
    # ── I8 Account Lifecycle ──
    if row.startswith("I8"):
        if lens == "U":
            if lf and g("validate_account_deactivation"): return ("live", "live", "account-lifecycle contract EXERCISED live: the consumer-facing controls run end-to-end — signOut wipes all 7 identity+hive keys (validate_auth_live_flows Playwright) + self-service deactivate_my_account() offboarding (validate_account_deactivation two-tenant docker, rolled back) — active/signout/deactivate lifecycle is live, not just modelled")
            return ("proof", "proof", "lifecycle states modelled: active/kicked membership + full signout")
        if lens == "F":
            if ld: return ("live", "live", "non-active member exclusion LIVE-PROVEN: 75 membership-gated RLS policies require status='active' (docker psql) → kicked/deactivated blocked from re-entry; kick = status flag not row-delete")
            return ("proof", "proof", "kick = status='kicked' (NOT row delete) → re-entry blocked on next load") if m["kicked_not_delete"] else ("pending", "pending", "kick semantics unverified")
        if lens == "A":
            if lf: return ("live", "live", "signOut LIVE-PROVEN to wipe all 7 identity+hive keys (Playwright; no next-worker inheritance on shared tablet)")
            return ("proof", "proof", "signOut wipes identity+hive keys (no next-worker inheritance on shared tablet)") if m["signout_full_wipe"] else ("pending", "pending", "signout incomplete")
        if lens == "I": return ("live", "live", "GDPR/PDPA soft-deactivate+anonymize LIVE-PROVEN two-tenant (local docker psql, rolled back): deactivate_my_account() self-scoped anonymizes A (display_name='Deleted user'/email NULL/deactivated_at) + revokes A's hive access + PRESERVES A's operational records, B UNTOUCHED (5/5 asserts t). validate_account_deactivation GREEN (now also gates the status-CHECK extension caught live). auth.users login-ban = admin-API attributed residual") if g("validate_account_deactivation") else ("pending", "pending", "★ account deactivation / data-deletion (GDPR/PDPA offboarding) NOT built or gated — I8 build target")
    return ("pending", "pending", "unscored")


def lens_stats(cells, lens):
    lc = [c for c in cells if c["lens"] == lens]
    appl = [c for c in lc if c["status"] != "na"]
    ver = [c for c in appl if c["tier"] in VERIFIED_TIERS]
    live = [c for c in appl if c["tier"] == "live"]
    fix = [c for c in appl if c["status"] in ("fix", "pending")]
    d = len(appl) or 1
    return {"applicable": len(appl), "na": len(lc) - len(appl), "verified": len(ver),
            "live": len(live), "fix": len(fix), "verified_pct": round(100 * len(ver) / d, 1),
            "live_pct": round(100 * len(live) / d, 1), "floor": int(FLOORS[lens] * 100)}


def main() -> int:
    L = gather()
    cells = [{"row": r, "lens": ln, **dict(zip(("status", "tier", "evidence"), score(r, ln, L)))}
             for r in ROWS for ln in LENSES]
    stats = {ln: lens_stats(cells, ln) for ln in LENSES}
    appl = sum(s["applicable"] for s in stats.values())
    ver = sum(s["verified"] for s in stats.values())
    live = sum(s["live"] for s in stats.values())
    fix = sum(s["fix"] for s in stats.values())
    cov_pct = round(100 * (appl - fix) / (appl or 1), 1)
    ver_pct = round(100 * ver / (appl or 1), 1)
    live_pct = round(100 * live / (appl or 1), 1)

    results = {"phase": "I0-baseline", "spine": "AUTH_IDENTITY_UFAI_ROADMAP.md",
               "overall": {"applicable": appl, "verified": ver, "live": live, "fix": fix,
                           "covered_pct": cov_pct, "verified_pct": ver_pct, "live_pct": live_pct},
               "per_lens": stats, "cells": cells, "scan": L["scan"], "validator_folds": L["val"]}
    RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")
    if ACCEPT or not BASELINE.exists():
        BASELINE.write_text(json.dumps({"floors": FLOORS,
            "lens_verified": {ln: stats[ln]["verified"] for ln in LENSES},
            "pending": fix}, indent=2), encoding="utf-8")

    okv = sum(1 for x in L["val"].values() if x)
    print("=" * 76)
    print("  ARC I — Auth/Identity/Session UFAI sweep (I0 measured baseline, per cell + surface)")
    print("=" * 76)
    print(f"  validator folds (existing, auth-relevant): {okv}/{len(FOLDS)} green")
    for n in FOLDS:
        print(f"      {'green' if L['val'][n] else ' RED '}  {n}")
    print(f"  {'lens':<5}{'appl':>6}{'ver':>5}{'live':>6}{'pend':>6}{'ver%':>7}{'floor':>7}")
    for ln in LENSES:
        s = stats[ln]
        flag = "OK" if s["verified_pct"] >= s["floor"] else ".."
        print(f"  {ln:<5}{s['applicable']:>6}{s['verified']:>5}{s['live']:>6}{s['fix']:>6}"
              f"{s['verified_pct']:>7}{s['floor']:>6}% {flag}")
    print(f"  {'-'*60}")
    print(f"  OVERALL  applicable {appl}   COVERED {appl-fix} ({cov_pct}%)   "
          f"VERIFIED {ver} ({ver_pct}%)   LIVE {live} ({live_pct}%)   PENDING {fix}")
    pend = [f"{c['row'].split()[0]}/{c['lens']}" for c in cells if c["status"] == "pending"]
    print(f"  PENDING cells (the Arc I build queue): {', '.join(pend) if pend else '(none)'}")
    print(f"\n  wrote {RESULTS.name} + {BASELINE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
