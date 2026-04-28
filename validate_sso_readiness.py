"""
SSO Readiness Validator — WorkHive Platform
============================================
WorkHive currently uses localStorage-based string identity (WORKER_NAME
read from up to 3 legacy keys). The multitenant-engineer skill says:
"Auth migration path: Phase 1 (string identity) → Phase 2 (Supabase Auth)".

Before SSO/SAML can be added for enterprise clients, the identity layer
must be consistent. An inconsistent identity layer means:
- Some pages accept SSO tokens but others still read stale localStorage keys
- Sign-out leaves ghost identities that SSO cannot clear
- Workers from Device A stay "logged in" on Device B because old keys persist

  Layer 1 — Identity chain consistency
    1.  3-key fallback chain on all pages  — all app pages agree on key priority
    2.  Sign-out clears all identity keys  — no ghost identity after sign-out

  Layer 2 — Write consistency
    3.  Identity only written to primary key — legacy keys not set by any page

  Layer 3 — URL injection guard
    4.  WORKER_NAME never from URL params  — URL identity bypasses SSO entirely
    5.  HIVE_ID never from URL params      — URL hive injection = tenant escape

  Layer 4 — Full session clearance
    6.  Sign-out also clears hive keys     — worker + hive context cleared together

Usage:  python validate_sso_readiness.py
Output: sso_readiness_report.json
"""
import re, json, sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

TOOLS_PAGES = [
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "assistant.html",
    "skillmatrix.html",
    "dayplanner.html",
    "engineering-design.html",
]

SIGNIN_PAGE   = "index.html"
IDENTITY_KEYS = ["wh_last_worker", "wh_worker_name", "workerName"]
PRIMARY_KEY   = "wh_last_worker"

# Hive context keys that must also be cleared on sign-out
HIVE_KEYS = [
    "wh_active_hive_id",
    "wh_hive_id",
    "wh_hive_role",
    "wh_hive_name",
]


# ── Layer 1: Identity chain consistency ───────────────────────────────────────

def check_identity_chain(pages, keys):
    """Every app page must read WORKER_NAME using all 3 localStorage keys. When
    SSO is added it writes to wh_last_worker — pages missing this key break."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            issues.append({"check": "identity_chain", "page": page,
                           "reason": f"{page} not found"})
            continue
        missing = [k for k in keys if k not in content]
        if missing:
            issues.append({"check": "identity_chain", "page": page,
                           "reason": (f"{page} identity chain missing keys: {missing} — "
                                      f"workers whose session used a missing key appear anonymous; "
                                      f"SSO migration cannot consistently target one key across all pages")})
    return issues


def check_signout_clearance(page, keys):
    """sign-out must remove all 3 identity keys — stale legacy keys create ghost
    identities when SSO expires the primary token."""
    content = read_file(page)
    if content is None:
        return [{"check": "signout_clearance", "page": page,
                 "reason": f"{page} not found"}]
    signout_m = re.search(r"function\s+signOut\s*\(([\s\S]{0,800}?)\}", content)
    if not signout_m:
        return [{"check": "signout_clearance", "page": page,
                 "reason": (f"{page} has no signOut() function — "
                            f"worker identity is never explicitly cleared on sign-out")}]
    body = signout_m.group(0)
    not_cleared = [k for k in keys if k not in body]
    if not_cleared:
        return [{"check": "signout_clearance", "page": page,
                 "reason": (f"{page} signOut() does not clear {not_cleared} — "
                            f"stale legacy keys persist after sign-out, creating ghost identities "
                            f"when SSO expires the primary token")}]
    return []


# ── Layer 2: Write consistency ────────────────────────────────────────────────

def check_identity_write_consistency(pages, signin_page, primary_key, legacy_keys):
    """Worker identity must ONLY be written to the primary key (wh_last_worker).
    Writing to legacy keys creates a parallel identity SSO cannot track."""
    issues = []
    for page in pages + [signin_page]:
        content = read_file(page)
        if content is None:
            continue
        for legacy_key in legacy_keys:
            if re.search(
                rf"localStorage\.setItem\s*\(\s*['\"]({re.escape(legacy_key)})['\"]",
                content
            ):
                issues.append({"check": "identity_write_consistency", "page": page,
                               "reason": (f"{page} writes identity to legacy key '{legacy_key}' — "
                                          f"only '{primary_key}' should be written; SSO cannot "
                                          f"invalidate keys it didn't write")})
    return issues


# ── Layer 3: URL injection guard ─────────────────────────────────────────────

def check_no_url_identity(pages, signin_page):
    """WORKER_NAME must come from localStorage, never from URL parameters —
    URL-injected identity bypasses SSO authentication entirely."""
    issues = []
    for page in pages + [signin_page]:
        content = read_file(page)
        if content is None:
            continue
        for pattern in [
            r"WORKER_NAME\s*=\s*.*URLSearchParams",
            r"WORKER_NAME\s*=\s*.*location\.search",
            r"WORKER_NAME\s*=\s*.*searchParams\.get",
            r"wh_last_worker.*URLSearchParams",
            r"wh_last_worker.*location\.search",
        ]:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append({"check": "no_url_identity", "page": page,
                               "reason": (f"{page} assigns worker identity from URL parameters — "
                                          f"any user can claim any identity by editing the URL, "
                                          f"bypassing SSO authentication entirely")})
                break
    return issues


def check_hive_id_not_from_url(pages):
    """
    HIVE_ID must come from localStorage (wh_active_hive_id / wh_hive_id),
    never from URL parameters. URL-injected HIVE_ID is a tenant boundary escape:
    any worker can access a different hive's data by appending ?hive=<uuid> to
    any app URL. SSO migration cannot seal this hole if the URL injection path exists.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        for pattern in [
            r"HIVE_ID\s*=\s*.*URLSearchParams",
            r"HIVE_ID\s*=\s*.*location\.search",
            r"HIVE_ID\s*=\s*.*searchParams\.get",
            r"wh_active_hive_id.*URLSearchParams",
            r"wh_hive_id.*URLSearchParams",
        ]:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append({"check": "hive_id_not_from_url", "page": page,
                               "reason": (f"{page} assigns HIVE_ID from URL parameters — "
                                          f"tenant boundary escape: worker can switch hives by "
                                          f"editing the URL; HIVE_ID must only come from localStorage")})
                break
    return issues


# ── Layer 4: Full session clearance ──────────────────────────────────────────

def check_hive_keys_cleared_on_signout(page, hive_keys):
    """
    signOut() clears the 3 worker identity keys but does NOT clear hive context
    keys (wh_active_hive_id, wh_hive_id, wh_hive_role, wh_hive_name).

    When Worker A signs out and Worker B signs in on the same device, Worker B
    inherits Worker A's hive membership context from localStorage. Worker B
    could see Worker A's team hive board briefly before the membership check
    runs and detects the mismatch.

    For SSO readiness: sign-out must be a complete session wipe — both the
    worker identity and the hive context must be cleared together. SSO logout
    clears the auth token but cannot clear application-specific localStorage
    keys — the application's signOut must handle this itself.
    """
    content = read_file(page)
    if content is None:
        return []
    signout_m = re.search(r"function\s+signOut\s*\(([\s\S]{0,800}?)\}", content)
    if not signout_m:
        return []
    body = signout_m.group(0)
    not_cleared = [k for k in hive_keys if k not in body]
    if not_cleared:
        return [{"check": "hive_keys_cleared_on_signout", "page": page,
                 "reason": (f"{page} signOut() does not clear hive context keys: {not_cleared} — "
                            f"Worker B signing in on the same device inherits Worker A's hive "
                            f"membership context; add removeItem for all hive keys to signOut()")}]
    return []


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "identity_chain",
    "signout_clearance",
    "identity_write_consistency",
    "no_url_identity",
    "hive_id_not_from_url",
    "hive_keys_cleared_on_signout",
]

CHECK_LABELS = {
    "identity_chain":              "L1  All TOOLS pages use the 3-key identity fallback chain",
    "signout_clearance":           "L1  Sign-out clears all 3 identity keys",
    "identity_write_consistency":  "L2  Worker identity only written to primary key (wh_last_worker)",
    "no_url_identity":             "L3  WORKER_NAME never set from URL parameters",
    "hive_id_not_from_url":        "L3  HIVE_ID never set from URL parameters",
    "hive_keys_cleared_on_signout":"L4  Sign-out also clears all hive context keys",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nSSO Readiness Validator (4-layer)"))
    print("=" * 55)
    print(f"  Identity keys: {' || '.join(IDENTITY_KEYS)}")
    print(f"  Primary key: {PRIMARY_KEY}\n")

    all_issues = []
    all_issues += check_identity_chain(TOOLS_PAGES, IDENTITY_KEYS)
    all_issues += check_signout_clearance(SIGNIN_PAGE, IDENTITY_KEYS)
    all_issues += check_identity_write_consistency(
        TOOLS_PAGES, SIGNIN_PAGE, PRIMARY_KEY,
        [k for k in IDENTITY_KEYS if k != PRIMARY_KEY]
    )
    all_issues += check_no_url_identity(TOOLS_PAGES, SIGNIN_PAGE)
    all_issues += check_hive_id_not_from_url(TOOLS_PAGES)
    all_issues += check_hive_keys_cleared_on_signout(SIGNIN_PAGE, HIVE_KEYS)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "sso_readiness",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("sso_readiness_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
