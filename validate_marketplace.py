"""
Marketplace Validator — WorkHive Platform (FREE marketplace)
============================================================
Holistic check for the FREE marketplace stack: schema, UI gates, and the
buyer-search column contract. The marketplace is contact-only (no payments) —
Stripe was removed entirely (2026-06-30), so the old Layer-2 edge-function
security and Layer-4 money-flow checks are gone with it.

  Layer 1 — Schema integrity
    1.  All marketplace tables defined          — listings, inquiries, reviews, sellers, orders, disputes
    2.  Required CHECK constraints present      — status enums, tier enum, section enum, condition enum
    3.  Required triggers present               — update_seller_tier, check_listing_rate, update_seller_rating
    4.  Migration timestamps unique             — conflicting prefixes block supabase db push
    5.  Listing storage bucket defined          — size limit + MIME whitelist

  Layer 3 — UI integrity
    6.  marketplace-admin platform-admin gate   — DB check on marketplace_platform_admins
    7.  marketplace-seller identity gate        — WORKER_NAME check
    8.  Sub-page path ordering                  — marketplace-admin/seller checked BEFORE marketplace
                                                  in companion-launcher.js (path.includes() match conflict)

  Layer 4 — Buyer-search column contract
    9.  Search uses existing columns            — no textSearch('search_vector') → PostgREST 400

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
    ("marketplace_sellers",   ["id", "worker_name", "tier", "kyb_verified", "rating_avg"]),
    ("marketplace_orders",    ["id", "listing_id", "buyer_name", "seller_name", "price", "status"]),
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

CHECK_NAMES = [
    "tables_defined",
    "check_constraints",
    "triggers_present",
    "migration_timestamps_unique",
    "storage_bucket_defined",
    "admin_supervisor_gate",
    "seller_identity_gate",
    "subpage_path_ordering",
    "search_uses_existing_columns",
    "inquiry_insert_sets_seller_name",
    "partsflow_bridge_schema",
    "partsflow_bridge_ui",
    "reviews_rls_locked",
    "seller_trust_guard",
    "storage_delete_owner_scoped",
    "price_comps_grounded",
    "parts_for_assets_guarded",
    "saved_search_alerts_selfscoped",
    "ai_listing_assist",
]

CHECK_LABELS = {
    "tables_defined":              "L1  All 9 marketplace tables defined with required columns",
    "check_constraints":           "L1  All CHECK constraints present (section, status, tier, condition)",
    "triggers_present":            "L1  All 3 marketplace triggers present (tier, rate-limit, rating)",
    "migration_timestamps_unique": "L1  Migration timestamp prefixes unique (no supabase db push conflict)",
    "storage_bucket_defined":      "L1  marketplace-listings storage bucket defined with size limit + MIME whitelist",
    "admin_supervisor_gate":       "L3  marketplace-admin.html gates on marketplace_platform_admins (not just hive supervisor)",
    "seller_identity_gate":        "L3  marketplace-seller.html has WORKER_NAME identity gate",
    "subpage_path_ordering":       "L3  marketplace-admin/seller checked BEFORE marketplace in companion-launcher.js",
    "search_uses_existing_columns":"L4  Buyer search queries columns the truth view exposes (no search_vector tsvector → 400)",
    "inquiry_insert_sets_seller_name":"L4  Every marketplace_inquiries insert sets seller_name (else the inquiry is invisible in the seller inbox)",
    "partsflow_bridge_schema":     "L1  Inventory<->Marketplace bridge columns present (marketplace_listings.part_number + source_inventory_item_id)",
    "partsflow_bridge_ui":         "L3  Inventory<->Marketplace bridge wired (inventory Sell/Find, post writes part identity, search matches part_number, receive round-trip)",
    "reviews_rls_locked":          "L2  marketplace_reviews has RLS enabled + insert policy blocking anon + self-claimed verified_purchase (no rating poisoning)",
    "seller_trust_guard":          "L2  marketplace_sellers has a BEFORE-trigger guard blocking non-admin self-grant of KYB/cert/tier/rating/sales",
    "storage_delete_owner_scoped": "L2  marketplace-listings image DELETE is owner/admin-scoped (not anon-open → no photo vandalism)",
    "price_comps_grounded":        "L4  Price guidance is grounded (get_marketplace_price_comps RPC) + the caller never renders a range below 3 comps (no fabricated price)",
    "parts_for_assets_guarded":    "L2  'Parts for your assets' RPC exists and is active-membership-guarded (no cross-hive inventory-usage leak)",
    "saved_search_alerts_selfscoped":"L2  Saved-search alert RPC (get_saved_search_matches) exists and is SELF-scoped (auth_worker_names, no p_worker_name IDOR)",
    "ai_listing_assist":           "L4  AI Post-form assist (marketplace-listing-assist) wired + SERVER_CATS whitelist stays in sync with the Post dropdown CATS (no category drift)",
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
    content = read_file("companion-launcher.js")
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
                    "reason": f"companion-launcher.js: path.includes('{sub_name}') appears AFTER path.includes('{parent}') — the parent match catches the sub-page first, sub-page context never fires",
                })
    return issues


# ── Layer 4: Buyer-search column contract ─────────────────────────────────────
def check_search_uses_existing_columns():
    """The buyer browse search must query columns the canonical truth view actually
    exposes. marketplace.html queried v_marketplace_listings_truth via
    textSearch('search_vector', ...) but that view has NO search_vector tsvector column,
    so EVERY search returned HTTP 400 (search fully broken). Fixed to an ILIKE on
    title+description; this guard prevents the broken-tsvector pattern from returning."""
    issues = []
    content = read_file("marketplace.html") or ""
    if re.search(r"textSearch\(\s*['\"]search_vector['\"]", content):
        issues.append({
            "check":  "search_uses_existing_columns",
            "reason": "marketplace.html calls textSearch('search_vector', ...) on "
                      "v_marketplace_listings_truth, which exposes NO search_vector column "
                      "-> PostgREST 400 on every buyer search (search silently broken). "
                      "Use .or('title.ilike.%q%,description.ilike.%q%') on columns the view exposes.",
        })
    return issues


def check_price_comps_grounded(migrations):
    """Price guidance must be GROUNDED (a real comp computed in SQL), never LLM-fabricated.
    Guard: the get_marketplace_price_comps RPC exists AND marketplace.html's caller refuses
    to render a range when comparables are too few (an `n < 3` guard)."""
    issues = []
    if "get_marketplace_price_comps" not in migrations:
        issues.append({"check": "price_comps_grounded",
                        "reason": "get_marketplace_price_comps RPC not defined — price guidance would have no grounded comp source (fabrication risk)."})
    mkt = read_file("marketplace.html") or ""
    if "get_marketplace_price_comps" in mkt and not re.search(r"n\s*<\s*3", mkt):
        issues.append({"check": "price_comps_grounded",
                        "reason": "marketplace.html calls get_marketplace_price_comps but has no `n < 3` guard — it may render a price range from too few comparables (unreliable/fabricated-feeling price)."})
    return issues


def check_saved_search_alerts_selfscoped(migrations):
    """The saved-search alert matcher must be SELF-scoped: it exposes which listings match a
    user's saved searches, so it must never take a p_worker_name param (IDOR) — it scopes by
    auth_worker_names(). Guard: the RPC exists, references auth_worker_names, and takes no
    worker-name parameter; and marketplace.html wires the badge."""
    issues = []
    m = migrations
    if "get_saved_search_matches" not in m:
        issues.append({"check": "saved_search_alerts_selfscoped",
                        "reason": "get_saved_search_matches RPC not defined — saved-search alerts have no matcher."})
        return issues
    fn = re.search(r"function\s+public\.get_saved_search_matches\s*\(([^)]*)\)", m, re.IGNORECASE)
    params = (fn.group(1) if fn else "").strip()
    if params:
        issues.append({"check": "saved_search_alerts_selfscoped",
                        "reason": "get_saved_search_matches takes parameters — it must be SELF-scoped (no p_worker_name) or a caller can read another user's saved-search matches (IDOR)."})
    body = re.search(r"get_saved_search_matches[\s\S]{0,1800}", m, re.IGNORECASE)
    if body and "auth_worker_names" not in body.group(0):
        issues.append({"check": "saved_search_alerts_selfscoped",
                        "reason": "get_saved_search_matches does not scope by auth_worker_names() — it is not self-scoped."})
    return issues


def check_parts_for_assets_guarded(migrations):
    """The "Parts for your assets" discovery RPC joins PUBLIC listings against a hive's
    PRIVATE inventory (DEFINER). It MUST verify the caller is an active member of the
    hive it is asked about, or it leaks another hive's part-usage. Guard: the RPC exists
    and references hive_members + auth.uid() (the membership check)."""
    issues = []
    m = migrations
    if "get_marketplace_parts_for_my_assets" not in m:
        issues.append({"check": "parts_for_assets_guarded",
                        "reason": "get_marketplace_parts_for_my_assets RPC not defined — the 'Parts for your assets' discovery has no backend."})
        return issues
    # crude but effective: the function body must gate on hive_members + auth.uid()
    fn = re.search(r"get_marketplace_parts_for_my_assets[\s\S]{0,1600}", m, re.IGNORECASE)
    body = fn.group(0) if fn else ""
    if "hive_members" not in body or "auth.uid()" not in body:
        issues.append({"check": "parts_for_assets_guarded",
                        "reason": "get_marketplace_parts_for_my_assets does not gate on an active hive_members + auth.uid() membership check — a caller could read another hive's part usage (cross-hive leak)."})
    return issues


def check_storage_delete_owner_scoped(migrations):
    """The 'marketplace-listings' storage bucket shipped with an anon-open DELETE policy
    (USING bucket_id only) — anyone could delete any seller's listing photo (vandalism).
    Guard: a later migration must scope the DELETE to the object owner or an admin."""
    issues = []
    m = migrations
    # must have an owner/admin-scoped delete on the bucket
    scoped = re.search(r"for\s+delete[\s\S]{0,200}marketplace-listings[\s\S]{0,200}owner\s*=\s*auth\.uid\(\)", m, re.IGNORECASE) \
             or re.search(r"marketplace-listings[\s\S]{0,200}owner\s*=\s*auth\.uid\(\)", m, re.IGNORECASE)
    if not scoped:
        issues.append({"check": "storage_delete_owner_scoped",
                        "reason": "No owner/admin-scoped DELETE policy for the marketplace-listings bucket found — "
                                  "listing images may be anon-deletable (photo vandalism). Scope DELETE to owner = auth.uid() OR is_marketplace_admin()."})
    return issues


def check_reviews_rls_locked(migrations):
    """marketplace_reviews shipped with RLS DISABLED + anon INSERT grant — anyone (even
    logged-out) could inject reviews with verified_purchase=true, and trg_update_seller_rating
    recomputes the seller's rating from them (trust/rating poisoning). Guard: RLS must be
    enabled and the insert policy must forbid a self-claimed verified_purchase."""
    issues = []
    m = migrations
    if not re.search(r"alter\s+table\s+(?:public\.)?marketplace_reviews\s+enable\s+row\s+level\s+security", m, re.IGNORECASE):
        issues.append({"check": "reviews_rls_locked",
                        "reason": "No 'ALTER TABLE marketplace_reviews ENABLE ROW LEVEL SECURITY' — reviews table is world-writable (rating poisoning)."})
    # the insert policy must tie verified_purchase to false for non-admins
    if "mkt_reviews_insert" not in m or "verified_purchase = false" not in m:
        issues.append({"check": "reviews_rls_locked",
                        "reason": "marketplace_reviews INSERT policy missing or does not force verified_purchase=false for non-admins — sellers/anon can fabricate 'verified' reviews."})
    return issues


def check_seller_trust_guard(migrations):
    """marketplace_sellers UPDATE RLS checks only auth_uid=auth.uid() with no column-level
    restriction, so a seller could self-grant kyb_verified/cert_verified/tier/rating/sales
    (live-exploited). RLS WITH CHECK cannot express column-level or transition rules, so the
    fix is a BEFORE trigger. Guard: the guard function + trigger must exist."""
    issues = []
    m = migrations
    if "guard_marketplace_seller_trust_columns" not in m:
        issues.append({"check": "seller_trust_guard",
                        "reason": "No guard_marketplace_seller_trust_columns() function — a seller can self-grant KYB/cert/tier/rating/sales (fabricated trust)."})
    if not re.search(r"create\s+trigger\s+trg_guard_seller_trust", m, re.IGNORECASE):
        issues.append({"check": "seller_trust_guard",
                        "reason": "guard function exists but no trg_guard_seller_trust BEFORE trigger on marketplace_sellers wires it — the guard never fires."})
    return issues


def check_partsflow_bridge_schema(migrations):
    """The Inventory<->Marketplace parts-flow fabric (X keystone) needs part identity +
    provenance on listings: marketplace_listings.part_number (buyer search + reorder match)
    and source_inventory_item_id (which inventory item a 'Sell surplus' listing came from).
    Without these columns the two islands stay unlinked."""
    issues = []
    need = ["part_number", "source_inventory_item_id"]
    # look specifically at an ALTER/CREATE touching marketplace_listings with the columns
    has_alter = re.search(r"alter\s+table\s+(?:public\.)?marketplace_listings", migrations, re.IGNORECASE)
    for col in need:
        if not re.search(rf"\b{col}\b", migrations):
            issues.append({
                "check":  "partsflow_bridge_schema",
                "reason": f"marketplace_listings.{col} not found in any migration — the Inventory<->Marketplace "
                          "parts-flow bridge (X keystone) has no part identity/provenance to join on.",
            })
    if need and not has_alter and not issues:
        # columns exist textually but not via an ALTER on the table — weak signal, warn-worthy
        issues.append({
            "check": "partsflow_bridge_schema", "skip": True,
            "reason": "part_number/source_inventory_item_id appear in migrations but no ALTER TABLE "
                      "marketplace_listings was found — verify the columns are actually on the listings table.",
        })
    return issues


def check_partsflow_bridge_ui():
    """The parts-flow bridge must be wired end-to-end across the two pages:
      inventory.html  — sellSurplus() + findOnMarketplace() (supply + demand affordances)
      marketplace.html— post insert writes part_number + source_inventory_item_id;
                        buyer search matches part_number; prefillPostFromInventory (Sell landing);
                        the receive round-trip deep-links back to inventory (?receive=)."""
    issues = []
    inv = read_file("inventory.html") or ""
    mkt = read_file("marketplace.html") or ""

    if "function sellSurplus" not in inv:
        issues.append({"check": "partsflow_bridge_ui",
                        "reason": "inventory.html missing sellSurplus() — no 'Sell surplus' affordance (supply side of the bridge)."})
    if "function findOnMarketplace" not in inv:
        issues.append({"check": "partsflow_bridge_ui",
                        "reason": "inventory.html missing findOnMarketplace() — no below-reorder 'Find on Marketplace' (demand side)."})
    if "receive" not in inv or "openRestockModal" not in inv:
        issues.append({"check": "partsflow_bridge_ui",
                        "reason": "inventory.html missing the ?receive= round-trip handler that lands a marketplace receipt into stock."})
    # marketplace: the post insert must carry both bridge fields
    m = re.search(r"marketplace_listings['\"]\)\s*\.insert\(", mkt)
    if m:
        window = mkt[m.start():m.start() + 900]
        if "part_number" not in window or "source_inventory_item_id" not in window:
            issues.append({"check": "partsflow_bridge_ui",
                            "reason": "marketplace.html post insert does not write part_number + source_inventory_item_id — listed-from-inventory provenance/identity is lost."})
    if "part_number.ilike" not in mkt:
        issues.append({"check": "partsflow_bridge_ui",
                        "reason": "marketplace.html buyer search does not match part_number (part_number.ilike) — 'Find on Marketplace' by part number cannot resolve."})
    if "function prefillPostFromInventory" not in mkt:
        issues.append({"check": "partsflow_bridge_ui",
                        "reason": "marketplace.html missing prefillPostFromInventory() — the inventory 'Sell surplus' deep-link has no prefilled Post landing."})
    return issues


def check_inquiry_insert_sets_seller_name():
    """Every marketplace_inquiries insert MUST set seller_name. The seller dashboard
    surfaces inquiries via v_marketplace_inquiries_truth ... .eq('seller_name', WORKER_NAME),
    and that view selects the base i.seller_name (NOT the joined listing's seller_name). So an
    insert that omits seller_name -> NULL -> the inquiry NEVER matches the seller's filter and
    becomes a silent BLACK-HOLE (the buyer sees 'Inquiry sent!' but no seller ever sees it).
    Found via LIVE deepwalk 2026-07-11: the primary Contact-Seller path omitted it while the
    RFQ/bulk-quote path set it. Guard both inquiry-insert call sites."""
    issues = []
    content = read_file("marketplace.html") or ""
    for m in re.finditer(r"marketplace_inquiries['\"]\)\s*\.insert\(", content):
        # Window spans BOTH sides of the insert call: the inline-object path sets
        # seller_name AFTER `.insert([{`, but the bulk/RFQ path builds the `rows`
        # array (with seller_name) a few lines BEFORE and passes the variable in.
        window = content[max(0, m.start() - 700):m.start() + 700]
        if "seller_name" not in window:
            line_no = content[:m.start()].count("\n") + 1
            issues.append({
                "check":  "inquiry_insert_sets_seller_name",
                "line":   line_no,
                "reason": f"A marketplace_inquiries insert (marketplace.html:{line_no}) omits seller_name "
                          "-> NULL. The seller dashboard filters v_marketplace_inquiries_truth by "
                          "seller_name, so the inquiry is a silent black-hole the seller never sees. "
                          "Set seller_name from the listing (e.g. stashed on #inq-listing-id.dataset.seller).",
            })
    return issues


# ── Runner ────────────────────────────────────────────────────────────────────
def check_ai_listing_assist(migrations):
    """AI Post-form assist (marketplace-listing-assist edge fn) must be present + wired, and its
    SERVER-owned category whitelist (SERVER_CATS) must stay in SYNC with marketplace.html CATS.
    Drift is a real bug: if the AI suggests a category the dropdown no longer has, the frontend
    silently drops it (canonical-option check fails); if the dropdown gains a category the server
    whitelist lacks, the AI can never suggest it. The server whitelist is CATS minus the 'All'
    filter pseudo-category."""
    issues = []
    fn  = read_file("supabase/functions/marketplace-listing-assist/index.ts") or ""
    mkt = read_file("marketplace.html") or ""
    if not fn:
        return [{"check": "ai_listing_assist",
                 "reason": "supabase/functions/marketplace-listing-assist/index.ts missing — the Post-form AI assist edge fn is gone (frontend calls it)."}]
    for tok, why in [("post-ai-assist", "AI assist button id"),
                     ("handleAiAssist", "AI assist click handler"),
                     ("marketplace-listing-assist", "edge fn invoke")]:
        if tok not in mkt:
            issues.append({"check": "ai_listing_assist",
                           "reason": f"marketplace.html missing {why} ('{tok}') — AI listing assist not wired into the Post form."})
    def cats_in(text, var_re):
        m = re.search(var_re, text, re.S)
        return set(re.findall(r"['\"]([^'\"]+)['\"]", m.group(1))) if m else None
    server = cats_in(fn,  r"SERVER_CATS[^{]*\{(.*?)\n\s*\};")
    client = cats_in(mkt, r"const CATS\s*=\s*\{(.*?)\n\s*\};")
    if server is None:
        issues.append({"check": "ai_listing_assist", "reason": "SERVER_CATS taxonomy not found in the edge fn (regex miss or block removed)."})
    elif client is None:
        issues.append({"check": "ai_listing_assist", "reason": "CATS taxonomy not found in marketplace.html (regex miss or block removed)."})
    else:
        client_no_all = {c for c in client if c != "All"}
        missing = client_no_all - server   # in dropdown, not in server whitelist
        extra   = server - client_no_all   # in server whitelist, not offered in the dropdown
        if missing or extra:
            issues.append({"check": "ai_listing_assist",
                           "reason": ("SERVER_CATS (marketplace-listing-assist) drifted from marketplace.html CATS. "
                                      f"In dropdown but not the AI whitelist: {sorted(missing)}; "
                                      f"in the AI whitelist but not the dropdown: {sorted(extra)}. "
                                      "Keep the edge fn's SERVER_CATS == CATS minus 'All'.")})
    return issues


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nMarketplace Validator (free marketplace — schema + UI + search)"))
    print("=" * 55)

    migrations = read_all_migrations()

    all_issues = []
    all_issues.extend(check_tables_defined(migrations))
    all_issues.extend(check_check_constraints(migrations))
    all_issues.extend(check_triggers_present(migrations))
    all_issues.extend(check_migration_timestamps_unique())
    all_issues.extend(check_storage_bucket_defined(migrations))
    all_issues.extend(check_admin_supervisor_gate())
    all_issues.extend(check_seller_identity_gate())
    all_issues.extend(check_subpage_path_ordering())
    all_issues.extend(check_search_uses_existing_columns())
    all_issues.extend(check_inquiry_insert_sets_seller_name())
    all_issues.extend(check_partsflow_bridge_schema(migrations))
    all_issues.extend(check_partsflow_bridge_ui())
    all_issues.extend(check_reviews_rls_locked(migrations))
    all_issues.extend(check_seller_trust_guard(migrations))
    all_issues.extend(check_storage_delete_owner_scoped(migrations))
    all_issues.extend(check_price_comps_grounded(migrations))
    all_issues.extend(check_parts_for_assets_guarded(migrations))
    all_issues.extend(check_saved_search_alerts_selfscoped(migrations))
    all_issues.extend(check_ai_listing_assist(migrations))

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
