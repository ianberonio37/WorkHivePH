"""
Marketplace Validator — WorkHive Platform
==========================================
Holistic check for the marketplace stack: schema, edge functions, UI gates,
Stripe security patterns, and money-flow consistency. Built from lessons
discovered while shipping the marketplace end-to-end (May 2026).

  Layer 1 — Schema integrity
    1.  All marketplace tables defined          — listings, inquiries, reviews, sellers, orders, disputes
    2.  Required CHECK constraints present      — status enums, tier enum, section enum, condition enum
    3.  Required triggers present               — update_seller_tier, check_listing_rate, update_seller_rating
    4.  Migration timestamps unique             — conflicting prefixes block supabase db push

  Layer 2 — Edge Function security
    5.  Server-side price fetch                 — checkout reads price from DB, never trusts client
    6.  Webhook signature verification          — webhook handler uses Stripe-Signature + HMAC
    7.  Platform fee enforced                   — checkout uses application_fee_amount
    8.  All 5 functions registered              — config.toml + deploy-functions.ps1 + validators
    9.  Stripe key server-side only             — STRIPE_SECRET_KEY only in Deno.env.get, never on frontend

  Layer 3 — UI integrity
    10. marketplace-admin platform-admin gate   — verifyPlatformAdmin() DB check on marketplace_platform_admins
    11. marketplace-seller identity gate        — WORKER_NAME check
    12. Sub-page path ordering                  — marketplace-admin/seller checked BEFORE marketplace
                                                  in floating-ai.js (path.includes() match conflict)

  Layer 4 — Money-flow consistency
    13. Order status state machine              — only 6 allowed status values used in UI
    14. Platform fee constant consistent        — same percentage across checkout + release

Usage:  python validate_marketplace.py
Output: marketplace_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

# ── Config ────────────────────────────────────────────────────────────────────
MIGRATIONS_DIR = os.path.join("supabase", "migrations")
FUNCTIONS_DIR  = os.path.join("supabase", "functions")

REQUIRED_TABLES = [
    ("marketplace_listings",  ["id", "hive_id", "seller_name", "section", "title", "price", "status", "created_at", "view_count"]),
    ("marketplace_inquiries", ["id", "listing_id", "buyer_name", "message", "status", "created_at"]),
    ("marketplace_reviews",   ["id", "listing_id", "reviewer_name", "rating", "verified_purchase", "created_at"]),
    ("marketplace_sellers",   ["id", "worker_name", "tier", "kyb_verified", "stripe_account_id", "rating_avg"]),
    ("marketplace_orders",    ["id", "listing_id", "buyer_name", "seller_name", "price", "status", "stripe_session_id"]),
    ("marketplace_disputes",  ["id", "order_id", "opened_by", "seller_name", "reason", "status", "created_at"]),
    ("marketplace_watchlist", ["id", "worker_name", "listing_id", "created_at"]),
    ("marketplace_saved_searches", ["id", "worker_name", "search_name", "section", "active", "created_at"]),
    ("marketplace_platform_admins", ["worker_name", "granted_at", "granted_by"]),
]

REQUIRED_CHECK_CONSTRAINTS = [
    # (table, column, allowed_values)
    ("marketplace_listings",  "section",   ["parts", "training", "jobs"]),
    ("marketplace_listings",  "status",    ["draft", "published", "sold", "removed"]),
    ("marketplace_listings",  "condition", ["new", "used", "refurb"]),
    ("marketplace_inquiries", "status",    ["pending", "replied", "closed"]),
    ("marketplace_sellers",   "tier",      ["bronze", "silver", "gold"]),
    ("marketplace_orders",    "status",    ["pending_payment", "escrow_hold", "buyer_confirmed", "released", "refunded", "disputed"]),
]

REQUIRED_TRIGGERS = [
    ("update_seller_tier",        "marketplace_orders"),
    ("check_listing_rate",        "marketplace_listings"),
    ("update_seller_rating",      "marketplace_reviews"),
]

REQUIRED_FUNCTIONS = [
    "marketplace-checkout",
    "marketplace-webhook",
    "marketplace-connect-onboard",
    "marketplace-connect-status",
    "marketplace-release",
]

ORDER_STATUS_VALUES = {
    "pending_payment", "escrow_hold", "buyer_confirmed", "released", "refunded", "disputed"
}

CHECK_NAMES = [
    "tables_defined",
    "check_constraints",
    "triggers_present",
    "migration_timestamps_unique",
    "storage_bucket_defined",
    "server_price_fetch",
    "webhook_signature",
    "platform_fee",
    "functions_registered",
    "stripe_key_server_only",
    "admin_supervisor_gate",
    "seller_identity_gate",
    "subpage_path_ordering",
    "order_status_consistency",
    "platform_fee_consistent",
]

CHECK_LABELS = {
    "tables_defined":              "L1  All 9 marketplace tables defined with required columns",
    "check_constraints":           "L1  All CHECK constraints present (section, status, tier, condition)",
    "triggers_present":            "L1  All 3 marketplace triggers present (tier, rate-limit, rating)",
    "migration_timestamps_unique": "L1  Migration timestamp prefixes unique (no supabase db push conflict)",
    "storage_bucket_defined":      "L1  marketplace-listings storage bucket defined with size limit + MIME whitelist",
    "server_price_fetch":          "L2  marketplace-checkout fetches price from DB (no client trust)",
    "webhook_signature":           "L2  marketplace-webhook verifies Stripe signature with HMAC",
    "platform_fee":                "L2  marketplace-checkout uses application_fee_amount for platform cut",
    "functions_registered":        "L2  All 5 marketplace functions registered in config.toml + deploy-functions.ps1",
    "stripe_key_server_only":      "L2  STRIPE_SECRET_KEY only used in Edge Functions, never on frontend",
    "admin_supervisor_gate":       "L3  marketplace-admin.html gates on marketplace_platform_admins (not just hive supervisor)",
    "seller_identity_gate":        "L3  marketplace-seller.html has WORKER_NAME identity gate",
    "subpage_path_ordering":       "L3  marketplace-admin/seller checked BEFORE marketplace in floating-ai.js",
    "order_status_consistency":    "L4  All 6 order status values declared on backend match UI labels",
    "platform_fee_consistent":     "L4  Platform fee constant matches between checkout and release",
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def read_all_migrations():
    if not os.path.isdir(MIGRATIONS_DIR):
        return ""
    parts = []
    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        if fname.endswith(".sql"):
            c = read_file(os.path.join(MIGRATIONS_DIR, fname))
            if c:
                parts.append(c)
    return "\n".join(parts)


def read_function(name):
    path = os.path.join(FUNCTIONS_DIR, name, "index.ts")
    return read_file(path)


# ── Layer 1: Schema integrity ─────────────────────────────────────────────────
def check_tables_defined(migrations):
    issues = []
    for table, cols in REQUIRED_TABLES:
        if not re.search(rf"create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?{table}\b", migrations, re.IGNORECASE):
            issues.append({
                "check":  "tables_defined",
                "table":  table,
                "reason": f"{table} not defined in any migration — listings/orders/disputes data layer is incomplete",
            })
            continue
        # Check key columns are present in the migration
        missing_cols = [c for c in cols if not re.search(rf"\b{c}\b", migrations)]
        if missing_cols:
            issues.append({
                "check":  "tables_defined",
                "table":  table,
                "reason": f"{table} missing required columns: {', '.join(missing_cols)}",
            })
    return issues


def check_check_constraints(migrations):
    issues = []
    for table, col, values in REQUIRED_CHECK_CONSTRAINTS:
        # Look for: column ... check (... in (...)) — flexible matching
        for v in values:
            if f"'{v}'" not in migrations:
                issues.append({
                    "check":  "check_constraints",
                    "table":  table,
                    "column": col,
                    "reason": f"{table}.{col} CHECK constraint missing value '{v}' — invalid status writes will fail with 23514",
                })
                break  # one missing per col is enough to flag
    return issues


def check_triggers_present(migrations):
    issues = []
    for trig_func, expected_table in REQUIRED_TRIGGERS:
        if not re.search(rf"function\s+(?:public\.)?{trig_func}\b", migrations, re.IGNORECASE):
            issues.append({
                "check":  "triggers_present",
                "trigger": trig_func,
                "reason": f"Trigger function {trig_func} not defined — depended-on side effect on {expected_table} will not fire",
            })
    return issues


def check_storage_bucket_defined(migrations):
    """Listing image upload requires the marketplace-listings bucket to exist
       with a file_size_limit + allowed_mime_types whitelist. Without it,
       uploads fail with cryptic 'bucket not found' or 400 errors."""
    issues = []
    if "'marketplace-listings'" not in migrations:
        issues.append({
            "check":  "storage_bucket_defined",
            "reason": "marketplace-listings storage bucket not declared in any migration — image uploads will fail",
        })
        return issues
    if "file_size_limit" not in migrations or "allowed_mime_types" not in migrations:
        issues.append({
            "check":  "storage_bucket_defined",
            "reason": "marketplace-listings bucket missing file_size_limit or allowed_mime_types — spam guard absent",
        })
    return issues


def check_migration_timestamps_unique():
    issues = []
    if not os.path.isdir(MIGRATIONS_DIR):
        return issues
    seen = {}
    for fname in os.listdir(MIGRATIONS_DIR):
        if not fname.endswith(".sql"):
            continue
        # Extract timestamp prefix (numbers before first underscore)
        m = re.match(r"^(\d+)_", fname)
        if not m:
            continue
        prefix = m.group(1)
        if prefix in seen:
            issues.append({
                "check":  "migration_timestamps_unique",
                "file":   fname,
                "conflict_with": seen[prefix],
                "reason": f"{fname} shares timestamp prefix {prefix} with {seen[prefix]} — supabase db push fails with --include-all required",
            })
        else:
            seen[prefix] = fname
    return issues


# ── Layer 2: Edge Function security ───────────────────────────────────────────
def check_server_price_fetch():
    issues = []
    content = read_function("marketplace-checkout")
    if content is None:
        issues.append({
            "check":  "server_price_fetch",
            "reason": "marketplace-checkout/index.ts not found",
        })
        return issues
    # Must fetch listing from DB before charging
    if not re.search(r"\.from\(\s*['\"]marketplace_listings['\"]\s*\)\s*\.select", content):
        issues.append({
            "check":  "server_price_fetch",
            "reason": "marketplace-checkout does not fetch listing from DB before charging — client could submit any price",
        })
    return issues


def check_webhook_signature():
    issues = []
    content = read_function("marketplace-webhook")
    if content is None:
        issues.append({
            "check":  "webhook_signature",
            "reason": "marketplace-webhook/index.ts not found",
        })
        return issues
    has_sig_header = re.search(r"stripe[-_]signature", content, re.IGNORECASE)
    has_hmac      = re.search(r"\bHMAC\b", content)
    has_secret    = re.search(r"STRIPE_WEBHOOK_SECRET", content)
    if not (has_sig_header and has_hmac and has_secret):
        issues.append({
            "check":  "webhook_signature",
            "missing": [
                k for k, v in (("Stripe-Signature header", has_sig_header), ("HMAC verification", has_hmac), ("STRIPE_WEBHOOK_SECRET env var", has_secret))
                if not v
            ],
            "reason": "marketplace-webhook missing Stripe signature verification — anyone could POST fake escrow_hold events",
        })
    return issues


def check_platform_fee():
    issues = []
    content = read_function("marketplace-checkout")
    if content is None:
        return issues
    if "application_fee_amount" not in content:
        issues.append({
            "check":  "platform_fee",
            "reason": "marketplace-checkout missing application_fee_amount — platform takes no cut on transactions",
        })
    return issues


def check_functions_registered():
    issues = []
    config_path  = os.path.join("supabase", "config.toml")
    deploy_path  = "deploy-functions.ps1"
    config       = read_file(config_path) or ""
    deploy       = read_file(deploy_path) or ""

    for fname in REQUIRED_FUNCTIONS:
        if f"[functions.{fname}]" not in config:
            issues.append({
                "check":  "functions_registered",
                "function": fname,
                "reason": f"{fname} missing [functions.{fname}] section in supabase/config.toml — verify_jwt defaults to true and breaks calls",
            })
        if fname not in deploy:
            issues.append({
                "check":  "functions_registered",
                "function": fname,
                "reason": f"{fname} not in deploy-functions.ps1 — running .\\deploy-functions.ps1 will not push this function",
            })
    return issues


def check_stripe_key_server_only():
    issues = []
    # Stripe secret key must NEVER appear in any frontend file
    frontend_files = [
        "marketplace.html", "marketplace-admin.html", "marketplace-seller.html",
        "floating-ai.js", "nav-hub.js", "utils.js"
    ]
    for f in frontend_files:
        content = read_file(f)
        if content is None:
            continue
        # Look for sk_live_ or sk_test_ literal
        if re.search(r"sk_(live|test)_[A-Za-z0-9]{20,}", content):
            issues.append({
                "check":  "stripe_key_server_only",
                "file":   f,
                "reason": f"{f} contains a Stripe secret key (sk_live_ or sk_test_) — secret keys must NEVER be in frontend; rotate immediately",
            })
    return issues


# ── Layer 3: UI integrity ─────────────────────────────────────────────────────
def check_admin_supervisor_gate():
    issues = []
    content = read_file("marketplace-admin.html")
    if content is None:
        issues.append({
            "check":  "admin_supervisor_gate",
            "reason": "marketplace-admin.html not found",
        })
        return issues
    has_platform_admin_check = re.search(r"marketplace_platform_admins", content)
    if not has_platform_admin_check:
        issues.append({
            "check":  "admin_supervisor_gate",
            "reason": "marketplace-admin.html does not check marketplace_platform_admins table — any hive supervisor (not just platform admins) could access the page",
        })
    return issues


def check_seller_identity_gate():
    issues = []
    content = read_file("marketplace-seller.html")
    if content is None:
        issues.append({
            "check":  "seller_identity_gate",
            "reason": "marketplace-seller.html not found",
        })
        return issues
    if not re.search(r"if\s*\(\s*!\s*WORKER_NAME\s*\)", content):
        issues.append({
            "check":  "seller_identity_gate",
            "reason": "marketplace-seller.html does not gate on !WORKER_NAME — anonymous users see seller dashboard with empty data",
        })
    return issues


def check_subpage_path_ordering():
    """Sub-page path.includes() routes must appear BEFORE the parent page route.
       path.includes('marketplace') matches 'marketplace-admin' too, so the order
       in the if/return chain matters."""
    issues = []
    content = read_file("floating-ai.js")
    if content is None:
        return issues

    # Find positions of each path.includes match in the source
    parent_patterns = ["marketplace"]  # extendable to other subpaged tools
    for parent in parent_patterns:
        parent_match = re.search(rf"path\.includes\(\s*['\"]({parent})['\"]\s*\)", content)
        if not parent_match:
            continue
        parent_pos = parent_match.start()

        # Look for sub-pages that share the prefix
        for sub_match in re.finditer(rf"path\.includes\(\s*['\"]({parent}-[a-z0-9_-]+)['\"]\s*\)", content):
            sub_name = sub_match.group(1)
            if sub_match.start() > parent_pos:
                issues.append({
                    "check":  "subpage_path_ordering",
                    "parent": parent,
                    "sub":    sub_name,
                    "reason": f"floating-ai.js: path.includes('{sub_name}') appears AFTER path.includes('{parent}') — the parent match catches the sub-page first, sub-page context never fires",
                })
    return issues


# ── Layer 4: Money-flow consistency ───────────────────────────────────────────
def check_order_status_consistency():
    issues = []
    files = ["marketplace.html", "marketplace-seller.html", "marketplace-admin.html"]
    declared_statuses = set()
    for f in files:
        content = read_file(f)
        if content is None:
            continue
        # Look for STATUS_LABEL, STATUS_ORDER_LABEL, DISP_STATUS, status: 'xxx'
        for m in re.finditer(r"['\"]([a-z_]+)['\"]\s*:\s*\{\s*label\s*:", content):
            declared_statuses.add(m.group(1))

    invalid = declared_statuses - ORDER_STATUS_VALUES - {"open", "seller_responded", "admin_review", "resolved_refund", "resolved_release"}  # dispute statuses are valid too
    if invalid:
        issues.append({
            "check":  "order_status_consistency",
            "invalid": sorted(invalid),
            "reason": f"Status values declared in UI ({', '.join(sorted(invalid))}) do not match the marketplace_orders.status CHECK constraint — silently misrender",
        })
    return issues


def check_platform_fee_consistent():
    """Platform fee percentage should be the same in checkout and release functions."""
    issues = []
    checkout = read_function("marketplace-checkout") or ""
    release  = read_function("marketplace-release") or ""

    def find_fee(content):
        m = re.search(r"PLATFORM_FEE_PCT\s*=\s*(0?\.\d+)", content)
        return m.group(1) if m else None

    co_fee = find_fee(checkout)
    rl_fee = find_fee(release)

    if co_fee and rl_fee and co_fee != rl_fee:
        issues.append({
            "check":  "platform_fee_consistent",
            "checkout_fee": co_fee,
            "release_fee":  rl_fee,
            "reason": f"PLATFORM_FEE_PCT mismatch — marketplace-checkout uses {co_fee}, marketplace-release uses {rl_fee}; one of them is wrong, sellers will be over- or under-paid",
        })
    return issues


# ── Runner ────────────────────────────────────────────────────────────────────
def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nMarketplace Validator (4-layer)"))
    print("=" * 55)

    migrations = read_all_migrations()

    all_issues = []
    all_issues.extend(check_tables_defined(migrations))
    all_issues.extend(check_check_constraints(migrations))
    all_issues.extend(check_triggers_present(migrations))
    all_issues.extend(check_migration_timestamps_unique())
    all_issues.extend(check_storage_bucket_defined(migrations))
    all_issues.extend(check_server_price_fetch())
    all_issues.extend(check_webhook_signature())
    all_issues.extend(check_platform_fee())
    all_issues.extend(check_functions_registered())
    all_issues.extend(check_stripe_key_server_only())
    all_issues.extend(check_admin_supervisor_gate())
    all_issues.extend(check_seller_identity_gate())
    all_issues.extend(check_subpage_path_ordering())
    all_issues.extend(check_order_status_consistency())
    all_issues.extend(check_platform_fee_consistent())

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "marketplace",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("marketplace_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
