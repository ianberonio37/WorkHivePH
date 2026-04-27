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

This validator does NOT check if SSO is built — it checks that the platform
is STRUCTURALLY READY for SSO to be added without breaking pages.

From the Integration Engineer skill (SSO/SAML pattern), Multitenant Engineer
skill (auth migration path), and enterprise integration research.

Four things checked:

  1. All TOOLS pages use the standard 3-key identity fallback chain
     — Every app page must read WORKER_NAME with all 3 legacy keys in order:
         localStorage.getItem('wh_last_worker') ||
         localStorage.getItem('wh_worker_name') ||
         localStorage.getItem('workerName') || ''
       A page that only reads the primary key will break for workers whose
       session was set by an older version of the app. SSO migration requires
       all pages to agree on which key takes precedence.

  2. Sign-out clears all 3 identity keys
     — index.html signOut() currently only removes 'wh_last_worker'.
       When SSO expires the token and the primary key is cleared, stale
       'wh_worker_name' or 'workerName' keys from old sessions auto-fill
       the identity — the worker stays "logged in" as a ghost identity.
       All 3 keys must be cleared together on sign-out.

  3. Identity is only ever written to the primary key (wh_last_worker)
     — setItem() calls that write worker identity must ONLY write to
       'wh_last_worker'. Writing to legacy keys creates a parallel
       identity that SSO cannot track or invalidate. This is the single-
       source-of-truth requirement for SSO migration.

  4. WORKER_NAME never set from URL parameters
     — WORKER_NAME must come from localStorage (managed by sign-in / SSO),
       never from URLSearchParams or location.search. URL-injected identity
       bypasses SSO authentication entirely and lets any user claim any
       identity by editing the URL.

Usage:  python validate_sso_readiness.py
Output: sso_readiness_report.json
"""
import re, json, sys

# App pages that must use the 3-key fallback chain
# (index.html is the landing page and intentionally uses only the primary key)
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

# The page that handles sign-out — must clear all 3 keys
SIGNIN_PAGE = "index.html"

# The 3 identity keys in priority order
IDENTITY_KEYS = ["wh_last_worker", "wh_worker_name", "workerName"]

# The ONLY key that should ever be written (primary key)
PRIMARY_KEY = "wh_last_worker"


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ── Check 1: All TOOLS pages use the 3-key fallback chain ────────────────────

def check_identity_chain(pages, keys):
    """
    Every app page must read WORKER_NAME using all 3 localStorage keys in
    the standard fallback order. This backward compatibility chain ensures
    that workers who signed in on an older version of the app (where
    'workerName' was the key) are still recognised.

    When SSO is added, it writes to 'wh_last_worker'. Pages that only
    check 'workerName' will see a blank WORKER_NAME even after SSO login
    — broken pages in an enterprise deployment.

    The check also accepts the KEY_WORKER constant pattern used in
    assistant.html where the key is read via a named constant.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            issues.append({
                "page": page,
                "reason": f"{page} not found",
            })
            continue

        # Check for the standard 3-key fallback pattern
        # Also accept the KEY_WORKER constant pattern (assistant.html style)
        has_primary   = keys[0] in content
        has_secondary = keys[1] in content
        has_tertiary  = keys[2] in content

        if not (has_primary and has_secondary and has_tertiary):
            missing = [k for k in keys
                       if k not in content]
            issues.append({
                "page":    page,
                "missing": missing,
                "reason": (
                    f"{page} identity chain is missing keys: {missing} — "
                    f"workers whose session used a missing key will appear "
                    f"anonymous, and SSO migration cannot consistently target "
                    f"one authoritative key across all pages"
                ),
            })
    return issues


# ── Check 2: Sign-out clears all 3 identity keys ─────────────────────────────

def check_signout_clearance(page, keys):
    """
    The sign-out function must remove ALL 3 identity keys, not just the
    primary one.

    Current state: signOut() only removes 'wh_last_worker'.

    When SSO expires and clears the primary key, leftover 'wh_worker_name'
    or 'workerName' keys from previous sessions auto-fill the identity
    fallback chain — the worker appears still logged in as a ghost identity.

    For an enterprise client using SSO, this means:
    - Worker A logs out via SSO (token cleared)
    - Worker B uses the same machine
    - The app reads stale 'wh_worker_name = WorkerA' from localStorage
    - All of Worker B's logbook entries are attributed to Worker A
    """
    issues = []
    content = read_file(page)
    if content is None:
        return [{"page": page, "reason": f"{page} not found"}]

    # Find the signOut function body
    signout_m = re.search(r"function\s+signOut\s*\(([\s\S]{0,800}?)\}", content)
    if not signout_m:
        issues.append({
            "page": page,
            "reason": (
                f"{page} has no signOut() function — "
                f"worker identity is never explicitly cleared on sign-out"
            ),
        })
        return issues

    signout_body = signout_m.group(0)
    cleared = [k for k in keys if k in signout_body]
    not_cleared = [k for k in keys if k not in signout_body]

    if not_cleared:
        issues.append({
            "page":       page,
            "cleared":    cleared,
            "not_cleared": not_cleared,
            "reason": (
                f"{page} signOut() clears {cleared} but NOT {not_cleared} — "
                f"stale legacy keys persist after sign-out. When SSO expires the "
                f"primary token, the fallback chain reads these stale keys and "
                f"auto-fills a ghost worker identity instead of showing login"
            ),
        })
    return issues


# ── Check 3: Identity only ever written to primary key ────────────────────────

def check_identity_write_consistency(pages, signin_page, primary_key, legacy_keys):
    """
    Worker identity (worker name) must ONLY be written to the primary key
    ('wh_last_worker'). Writing to legacy keys creates a second source of
    truth that SSO cannot track or invalidate.

    If 'workerName' is still being set by any page:
    - SSO clears 'wh_last_worker' on logout
    - 'workerName' remains with the old value
    - Any page in the fallback chain reads the stale 'workerName'
    - The worker is "stuck" as their pre-SSO identity until the legacy
      key is manually cleared from DevTools
    """
    issues = []
    all_pages = pages + [signin_page]
    for page in all_pages:
        content = read_file(page)
        if content is None:
            continue
        for legacy_key in legacy_keys:
            # Check if this page writes (setItem) to a legacy key
            if re.search(
                rf"localStorage\.setItem\s*\(\s*['\"]({re.escape(legacy_key)})['\"]",
                content
            ):
                issues.append({
                    "page": page,
                    "key":  legacy_key,
                    "reason": (
                        f"{page} writes worker identity to legacy key '{legacy_key}' "
                        f"— only '{primary_key}' should be written. SSO cannot "
                        f"invalidate keys it didn't write, leaving the legacy key "
                        f"as a persistent ghost identity"
                    ),
                })
    return issues


# ── Check 4: WORKER_NAME never set from URL parameters ───────────────────────

def check_no_url_identity(pages, signin_page):
    """
    WORKER_NAME must come from localStorage (set by sign-in or SSO),
    never from URL parameters.

    A URL like: logbook.html?worker=admin

    ...that assigns WORKER_NAME from URLSearchParams would let any user
    claim any identity by editing the URL in their browser — SSO
    authentication would be completely bypassed for data access.

    This is a critical pre-SSO security gate: if URL-injected identity
    exists before SSO is added, the SSO migration will not close the
    attack surface.
    """
    issues = []
    all_pages = pages + [signin_page]
    for page in all_pages:
        content = read_file(page)
        if content is None:
            continue

        # Check for WORKER_NAME being assigned from URL params
        for pattern in [
            r"WORKER_NAME\s*=\s*.*URLSearchParams",
            r"WORKER_NAME\s*=\s*.*location\.search",
            r"WORKER_NAME\s*=\s*.*searchParams\.get",
            r"wh_last_worker.*URLSearchParams",
            r"wh_last_worker.*location\.search",
        ]:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append({
                    "page": page,
                    "reason": (
                        f"{page} assigns worker identity from URL parameters — "
                        f"any user can claim any identity by editing the URL, "
                        f"bypassing SSO authentication entirely"
                    ),
                })
                break
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("SSO Readiness Validator")
print("=" * 70)
print(f"\n  Identity keys: {' || '.join(IDENTITY_KEYS)}")
print(f"  Primary key (write target): {PRIMARY_KEY}")
print(f"  Sign-out page: {SIGNIN_PAGE}\n")

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] All TOOLS pages use the 3-key identity fallback chain",
        check_identity_chain(TOOLS_PAGES, IDENTITY_KEYS),
        "FAIL",
    ),
    (
        "[2] Sign-out clears all 3 identity keys (not just primary)",
        check_signout_clearance(SIGNIN_PAGE, IDENTITY_KEYS),
        "FAIL",
    ),
    (
        "[3] Worker identity only ever written to primary key (wh_last_worker)",
        check_identity_write_consistency(
            TOOLS_PAGES, SIGNIN_PAGE, PRIMARY_KEY,
            [k for k in IDENTITY_KEYS if k != PRIMARY_KEY]
        ),
        "WARN",
    ),
    (
        "[4] WORKER_NAME never set from URL parameters",
        check_no_url_identity(TOOLS_PAGES, SIGNIN_PAGE),
        "FAIL",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('page', '?')}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("sso_readiness_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved sso_readiness_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll SSO readiness checks PASS.")
