"""
Webhook and Integration Idempotency Validator — WorkHive Platform
==================================================================
Idempotency means: running the same operation twice produces the same
result as running it once. This is critical for enterprise integrations:
SAP PM and IBM Maximo retry failed API calls. CMMS systems re-send
webhooks on timeout. CSV import jobs sometimes run twice.

Without idempotency, each retry creates a duplicate:
- A SAP work order gets created twice in WorkHive
- A PM completion fires two logbook entries
- A parts import adds 500 rows twice = 1000 rows

The Integration Engineer skill says explicitly:
"Idempotent imports — importing the same data twice should not create
duplicates; use external IDs as deduplication keys."

Four things checked:

  1. external_sync table has required UNIQUE constraint
     — The integration skill defines: CREATE TABLE external_sync with
       UNIQUE(system_type, external_id, entity_type). This constraint
       is the deduplication anchor for ALL external system IDs.
       Without it, a retry creates a duplicate sync record.
       This is a forward guard: PASS if table doesn't exist yet,
       FAIL if it exists without the constraint.

  2. Any webhook edge function verifies HMAC before payload access
     — Inbound webhook handlers must verify the HMAC signature on
       the X-WorkHive-Signature header BEFORE reading req.json().
       An unverified webhook is a spoofing vector: any client can
       send fake events. Also, HMAC verification IS the idempotency
       gate — the same signed event cannot be replayed once processed.
       Forward guard: PASS if no webhook handler exists, FAIL if it
       exists without verification.

  3. Upserts on shared tables specify onConflict within 5 lines
     — .upsert() without onConflict relies on the primary key for
       conflict resolution. For tables with UNIQUE constraints on
       non-PK columns (assets, hive_members), a bare upsert may
       CREATE instead of UPDATE when only the unique column matches.
       Check that .upsert() calls on shared tables have onConflict
       within the next 5 lines.

  4. Batch import operations use upsert not raw insert on shared tables
     — Any function processing a batch of items (forEach, map over
       an array into a DB write) must use .upsert() not .insert() on
       shared tables. A raw batch insert retried after failure creates
       duplicates. upsert is idempotent by design.

Usage:  python validate_idempotency.py
Output: idempotency_report.json
"""
import re, json, sys, os

MIGRATIONS_DIR = os.path.join("supabase", "migrations")
FUNCTIONS_DIR  = os.path.join("supabase", "functions")

LIVE_PAGES = [
    "logbook.html", "inventory.html", "pm-scheduler.html",
    "hive.html", "skillmatrix.html", "dayplanner.html",
    "engineering-design.html", "assistant.html",
]

# Shared multi-tenant tables — upserts on these must specify onConflict
SHARED_TABLES = [
    "inventory_items", "assets", "hive_members",
    "pm_assets", "skill_profiles", "schedule_items",
]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def read_all_migrations():
    content = ""
    if not os.path.isdir(MIGRATIONS_DIR):
        return content
    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        if fname.endswith(".sql"):
            c = read_file(os.path.join(MIGRATIONS_DIR, fname))
            if c:
                content += c
    return content


# ── Check 1: external_sync UNIQUE constraint ──────────────────────────────────

def check_external_sync_schema(migrations):
    """
    The external_sync table (defined in the Integration Engineer skill) maps
    WorkHive records to their external system equivalents (SAP AUFNR, Maximo
    ASSETNUM, etc.). Without a UNIQUE(system_type, external_id, entity_type)
    constraint, retried sync operations create duplicate mapping records.

    Forward guard: PASS if table not yet built.
    FAIL if table exists without the required uniqueness constraint.
    """
    issues = []
    if not migrations:
        return []

    has_table = bool(re.search(
        r"CREATE TABLE.*\bexternal_sync\b", migrations, re.IGNORECASE
    ))
    if not has_table:
        return []   # table not built yet — forward guard passes

    # Table exists — verify the UNIQUE constraint
    has_unique = bool(re.search(
        r"UNIQUE\s*\(\s*system_type\s*,\s*external_id\s*,\s*entity_type\s*\)"
        r"|UNIQUE\s*\(\s*external_id\s*,\s*system_type\s*,\s*entity_type\s*\)",
        migrations, re.IGNORECASE
    ))
    if not has_unique:
        issues.append({
            "source": MIGRATIONS_DIR,
            "reason": (
                "external_sync table exists but is missing "
                "UNIQUE(system_type, external_id, entity_type) — "
                "retried sync operations will create duplicate mapping records "
                "instead of updating existing ones"
            ),
        })
    return issues


# ── Check 2: Webhook edge functions verify HMAC before payload access ──────────

def check_webhook_hmac():
    """
    Any edge function that receives inbound webhooks must verify the
    HMAC signature before calling req.json(). An unverified webhook
    is a spoofing vector — any client can send fake events.

    The Integration Engineer skill defines the HMAC pattern:
      const signature = hmacSign(`${timestamp}.${JSON.stringify(payload)}`, secret)
      header: 'X-WorkHive-Signature'

    An inbound handler must verify this signature before processing.
    Forward guard: PASS if no webhook handler exists.
    """
    issues = []
    if not os.path.isdir(FUNCTIONS_DIR):
        return []

    for func_name in os.listdir(FUNCTIONS_DIR):
        func_path = os.path.join(FUNCTIONS_DIR, func_name, "index.ts")
        content = read_file(func_path)
        if content is None:
            continue

        # Is this a webhook receiver? (receives inbound events from external systems)
        is_webhook_receiver = bool(re.search(
            r"X-WorkHive-Signature|webhook.*signature|hmac.*verify|verify.*hmac"
            r"|X-Hub-Signature|X-Shopify-Webhook",
            content, re.IGNORECASE
        ))
        if not is_webhook_receiver:
            continue

        # Verify signature check appears BEFORE req.json() call
        hmac_pos = re.search(
            r"hmac|verifySignature|verify.*sign",
            content, re.IGNORECASE
        )
        json_pos = re.search(r"req\.json\(\)", content)

        if hmac_pos and json_pos and hmac_pos.start() > json_pos.start():
            issues.append({
                "func":   func_name,
                "reason": (
                    f"supabase/functions/{func_name}/index.ts — webhook handler "
                    f"reads req.json() BEFORE verifying the HMAC signature — "
                    f"attacker can send spoofed events that bypass signature check"
                ),
            })
        elif json_pos and not hmac_pos:
            issues.append({
                "func":   func_name,
                "reason": (
                    f"supabase/functions/{func_name}/index.ts — "
                    f"webhook handler has no HMAC verification — "
                    f"any client can send fake events without a valid signature"
                ),
            })
    return issues


# ── Check 3: Shared table upserts specify onConflict within 5 lines ───────────

def check_upsert_conflict_spec(pages, tables):
    """
    .upsert() without onConflict uses the primary key for conflict resolution.
    Tables with UNIQUE constraints on non-PK columns (like assets.asset_id,
    hive_members.(hive_id,worker_name)) may CREATE a new row instead of
    merging when the unique column matches but the PK differs.

    Bare .upsert(data) on shared tables without onConflict on the same
    or next 5 lines is flagged as WARN — may behave correctly today but
    breaks silently when the table gains new unique constraints.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()

        for i, line in enumerate(lines):
            # Find .upsert( on a shared table
            table_match = None
            for table in tables:
                if (f"from('{table}')" in line or f'from("{table}")' in line) \
                        and ".upsert(" in line:
                    table_match = table
                    break
            if not table_match:
                continue

            # Check if onConflict appears within the next 8 lines
            # (multi-line upsert calls can span up to 6-7 lines)
            window = "\n".join(lines[i:min(len(lines), i + 8)])
            if "onConflict" not in window:
                issues.append({
                    "page":  page,
                    "table": table_match,
                    "line":  i + 1,
                    "reason": (
                        f"{page}:{i + 1} — .upsert() on '{table_match}' with no "
                        f"onConflict in the next 5 lines — relies on primary key "
                        f"for deduplication; add onConflict: 'unique_column' to "
                        f"make retry behavior explicit and predictable"
                    ),
                })
    return issues


# ── Check 4: Batch array inserts on shared tables use upsert not insert ───────

def check_batch_idempotency(pages, tables):
    """
    When importing or syncing an array of items into a shared table,
    .insert() creates a new row on every call — not idempotent.
    .upsert() merges on conflict — safe to run multiple times.

    Pattern to detect: db.from(SHARED_TABLE).insert( appears after
    a forEach/map/for loop that iterates an array of items.
    This indicates a batch insert that will create duplicates on retry.

    The integration-engineer skill explicitly requires:
    "Upsert — safe to run multiple times" for all import operations.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()

        for i, line in enumerate(lines):
            # Is this a .insert( on a shared table?
            table_match = None
            for table in tables:
                if (f"from('{table}')" in line or f'from("{table}")' in line) \
                        and ".insert(" in line and ".select(" not in line:
                    table_match = table
                    break
            if not table_match:
                continue

            # Look back 8 lines for a loop pattern
            window_back = "\n".join(lines[max(0, i - 8):i])
            in_loop = bool(re.search(
                r"\bforEach\s*\(|\bfor\s*\(|\bfor\s+const\b|\bfor\s+let\b",
                window_back
            ))
            if in_loop:
                issues.append({
                    "page":  page,
                    "table": table_match,
                    "line":  i + 1,
                    "reason": (
                        f"{page}:{i + 1} — .insert() on '{table_match}' inside "
                        f"a loop — batch inserts are not idempotent. Use .upsert() "
                        f"with onConflict so retried imports merge instead of duplicating"
                    ),
                })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Webhook and Integration Idempotency Validator")
print("=" * 70)

migrations = read_all_migrations()
fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] external_sync table has UNIQUE(system_type, external_id, entity_type)",
        check_external_sync_schema(migrations),
        "FAIL",
    ),
    (
        "[2] Webhook edge functions verify HMAC before reading payload",
        check_webhook_hmac(),
        "FAIL",
    ),
    (
        "[3] Shared table upserts specify onConflict (within 5 lines)",
        check_upsert_conflict_spec(LIVE_PAGES, SHARED_TABLES),
        "WARN",
    ),
    (
        "[4] Batch array inserts on shared tables use upsert not insert",
        check_batch_idempotency(LIVE_PAGES, SHARED_TABLES),
        "WARN",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('page', iss.get('func', iss.get('source', '?')))}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("idempotency_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved idempotency_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll idempotency checks PASS.")
