"""
Realtime Payload Consumer Contract Validator — WorkHive Platform
=================================================================
WorkHive subscribes to Supabase Realtime (postgres_changes) on 17+ tables.
Each handler receives `payload.new` (INSERT/UPDATE) or `payload.old`
(UPDATE/DELETE) and reads columns from those objects. When a column is
renamed in a migration but the realtime consumer still tries to read the
old name, the value is undefined: the handler runs, comparison logic
fails silently, the toast/UI update doesn't fire, nobody notices until
a user reports "I don't see new posts in real-time anymore."

Same silent-failure class as schema phantom (HTML SELECT vs DB column)
and edge caller contract (HTML invoke body vs edge fn destructure). This
is the third side of the contract triangle: HTML realtime handler vs DB
column.

  Layer 1 — Subscribed table exists
    1.  Every `.on('postgres_changes', { table: 'foo' }, ...)` references
        a real table. Catches typos like 'logbok' or stale references
        after a table was renamed.
    [FAIL] Subscription opens, never fires (table doesn't exist in DB
    publication).

  Layer 2 — Payload columns exist
    2.  Every `payload.new.X` and `payload.old.X` read inside the handler
        body references a column that exists on the subscribed table.
    [FAIL] Handler runs, value is undefined; UI silently ignores the
    realtime event because comparisons / lookups produce no match.

  Layer 3 — Filter clause columns exist
    3.  Every `filter: 'col=eq.value'` references a column that exists
        on the subscribed table. PostgREST silently ignores filters on
        non-existent columns, so the subscription receives MORE events
        than expected (cross-hive leak risk for `hive_id` filters).
    [FAIL] Tenant boundary leak when the filter intended to scope by
    hive_id quietly drops because the column was renamed.

  Layer 4 — Channel name collision
    4.  Within a single file, no two `db.channel('name')` calls share
        the same name. Same-named channels share state — the second
        subscription replaces the first silently, breaking the page's
        realtime feature.
    [WARN] Two subscriptions on the same channel name in one file.

Usage:  python validate_realtime_payload_contract.py
Output: realtime_payload_contract_report.json
"""
import json
import os
import re
import sys
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))

# Reuse the migration-derived schema from validate_schema_phantom so this
# validator stays in lock-step as the schema evolves.
sys.path.insert(0, ROOT)
from validate_schema_phantom import load_table_columns  # noqa: E402


# Files we don't lint (test copies, retired pages).
SKIP_FILES = {
    "engineering-design-test.html",
    "hive-test.html",
}

# payload columns whose presence is universal in Supabase Realtime payloads
# regardless of table schema. These are envelope fields, not user columns.
PAYLOAD_ENVELOPE_FIELDS = {
    "id",          # always present (PK) — every PG table has a PK
    "created_at",  # convention; most tables have it but not all
    "updated_at",  # convention
}


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _list_caller_files() -> list[str]:
    out: list[str] = []
    for fname in os.listdir(ROOT):
        if fname in SKIP_FILES:
            continue
        if not (fname.endswith(".html") or fname.endswith(".js")):
            continue
        out.append(os.path.join(ROOT, fname))
    return out


# ─── Subscription parsing ────────────────────────────────────────────────────

# Locate each .on('postgres_changes', { ... }, handler).
# Captures: position of the opening `{` of the options object.
ON_HEAD_RE = re.compile(
    r"\.on\(\s*['\"`]postgres_changes['\"`]\s*,\s*\{",
)

# Within the options object, extract `table: '...'` and `filter: '...'`.
TABLE_RE  = re.compile(r"table\s*:\s*['\"`]([a-z_][a-z0-9_]*)['\"`]")
FILTER_RE = re.compile(r"filter\s*:\s*['\"`]([^'\"`]+)['\"`]")
EVENT_RE  = re.compile(r"event\s*:\s*['\"`](INSERT|UPDATE|DELETE|\*)['\"`]")

# Channel name (for L4 collision check).
CHANNEL_RE = re.compile(r"\.channel\(\s*['\"`]([^'\"`]+)['\"`]\s*\)")

# Inside the handler body: payload.new.X / payload.old.X references.
# We tolerate optional chaining (?.) — payload?.new?.X is identical semantics.
PAYLOAD_FIELD_RE = re.compile(
    r"payload\??\.\s*(?:new|old)\??\.\s*([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)


def _find_matching_brace(src: str, open_brace_pos: int) -> int:
    """Walk character-by-character to find the matching `}`. Aware of JS
    strings, template literals, and line/block comments."""
    if open_brace_pos < 0 or open_brace_pos >= len(src) or src[open_brace_pos] != "{":
        return -1
    depth = 0
    i = open_brace_pos
    in_string: str = ""
    while i < len(src):
        ch = src[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == in_string:
                in_string = ""
            i += 1
            continue
        if ch == "/" and i + 1 < len(src):
            if src[i + 1] == "/":
                nl = src.find("\n", i)
                i = nl + 1 if nl != -1 else len(src)
                continue
            if src[i + 1] == "*":
                end = src.find("*/", i + 2)
                i = end + 2 if end != -1 else len(src)
                continue
        if ch in "\"'`":
            in_string = ch
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _extract_handler_body(src: str, options_close_pos: int) -> str:
    """After the options object closes, the handler is the next argument.
    Walk forward to find the handler's body — either an arrow-fn `=>` block,
    a function literal, or a single-expression arrow. Return the body text
    bounded by either `{...}` block or the closing `)` of the .on() call."""
    # Look for a comma + arrow-fn opening within ~8 chars
    after = src[options_close_pos + 1:]
    # Match `, payload =>` or `, function(payload)`
    m = re.match(r"\s*,\s*(?:async\s+)?(?:\([^)]*\)|[\w]+)\s*=>\s*", after)
    if m:
        body_start = options_close_pos + 1 + m.end()
        if body_start < len(src) and src[body_start] == "{":
            close = _find_matching_brace(src, body_start)
            return src[body_start: close + 1] if close != -1 else ""
        # Single-expression arrow — body until the next `)` at depth 0
        depth = 0
        i = body_start
        while i < len(src):
            ch = src[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    return src[body_start: i]
                depth -= 1
            i += 1
        return src[body_start: body_start + 200]
    # Match `, function(payload) {`
    m = re.match(r"\s*,\s*(?:async\s+)?function\s*\([^)]*\)\s*", after)
    if m:
        body_start = options_close_pos + 1 + m.end()
        if body_start < len(src) and src[body_start] == "{":
            close = _find_matching_brace(src, body_start)
            return src[body_start: close + 1] if close != -1 else ""
    return ""


def _collect_subscriptions() -> list[dict]:
    """Returns list of {file, line, table, filter, event, payload_fields}."""
    out: list[dict] = []
    for path in _list_caller_files():
        src = _read(path)
        if not src:
            continue
        rel = os.path.relpath(path, ROOT)
        for m in ON_HEAD_RE.finditer(src):
            opt_open = m.end() - 1     # the `{` at the end of the head match
            opt_close = _find_matching_brace(src, opt_open)
            if opt_close == -1:
                continue
            opts_text = src[opt_open: opt_close + 1]
            tm = TABLE_RE.search(opts_text)
            if not tm:
                continue
            table = tm.group(1)
            fm = FILTER_RE.search(opts_text)
            em = EVENT_RE.search(opts_text)
            handler_body = _extract_handler_body(src, opt_close)
            payload_fields = sorted({
                pm.group(1) for pm in PAYLOAD_FIELD_RE.finditer(handler_body)
            })
            line = src[: m.start()].count("\n") + 1
            out.append({
                "file":           rel,
                "line":           line,
                "table":          table,
                "filter":         fm.group(1) if fm else None,
                "event":          em.group(1) if em else "*",
                "payload_fields": payload_fields,
            })
    return out


def _collect_channel_names() -> dict[str, list[tuple[int, str]]]:
    """Returns {file: [(line, channel_name), ...]} for L4 collision check."""
    out: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for path in _list_caller_files():
        src = _read(path)
        if not src:
            continue
        rel = os.path.relpath(path, ROOT)
        for m in CHANNEL_RE.finditer(src):
            line = src[: m.start()].count("\n") + 1
            out[rel].append((line, m.group(1)))
    return out


# ─── Layer checks ────────────────────────────────────────────────────────────

def check_subscribed_tables_exist(subs: list[dict], schema: dict) -> list[dict]:
    issues: list[dict] = []
    for s in subs:
        if s["table"] in schema:
            continue
        issues.append({
            "check":  "realtime_subscribed_table_exists",
            "file":   s["file"], "line": s["line"], "table": s["table"],
            "reason": (
                f"{s['file']}:{s['line']} subscribes to .on('postgres_changes', "
                f"{{ table: '{s['table']}' }}) but no such table exists in any "
                f"migration. Possible typo or stale reference after the table "
                f"was renamed/dropped. The subscription will silently never "
                f"fire — page realtime feature is dead."
            ),
        })
    return issues


def check_payload_columns_exist(subs: list[dict], schema: dict) -> list[dict]:
    issues: list[dict] = []
    for s in subs:
        cols = schema.get(s["table"], set())
        if not cols:
            continue   # already flagged by L1
        for field in s["payload_fields"]:
            if field in cols:
                continue
            if field in PAYLOAD_ENVELOPE_FIELDS and field in {c.lower() for c in cols}:
                continue
            issues.append({
                "check":  "realtime_payload_column_exists",
                "file":   s["file"], "line": s["line"],
                "table":  s["table"], "field": field,
                "reason": (
                    f"{s['file']}:{s['line']} reads payload.new/old.{field} "
                    f"in the handler but '{field}' is NOT a column on table "
                    f"'{s['table']}'. The realtime event fires; payload[field] "
                    f"is undefined; downstream comparison/UI logic silently "
                    f"no-ops. Either rename to the actual column, drop the "
                    f"reference, or add the column in a migration."
                ),
            })
    return issues


def check_filter_columns_exist(subs: list[dict], schema: dict) -> list[dict]:
    issues: list[dict] = []
    for s in subs:
        if not s["filter"]:
            continue
        cols = schema.get(s["table"], set())
        if not cols:
            continue
        # filter format: 'col=op.value' (e.g., 'hive_id=eq.<uuid>')
        m = re.match(r"([a-z_][a-z0-9_]*)\s*=", s["filter"])
        if not m:
            continue
        filter_col = m.group(1)
        if filter_col in cols:
            continue
        issues.append({
            "check":  "realtime_filter_column_exists",
            "file":   s["file"], "line": s["line"],
            "table":  s["table"], "filter_column": filter_col,
            "reason": (
                f"{s['file']}:{s['line']} subscribes with filter "
                f"'{s['filter']}' but '{filter_col}' is NOT a column on "
                f"'{s['table']}'. PostgREST silently ignores filters on "
                f"non-existent columns — the subscription receives MORE "
                f"events than intended. Tenant boundary leak risk if the "
                f"filter was meant to scope by hive_id."
            ),
        })
    return issues


def check_channel_name_collisions(channels: dict) -> list[dict]:
    issues: list[dict] = []
    for path, occurrences in channels.items():
        seen: dict[str, int] = {}
        for line, name in occurrences:
            if name in seen:
                issues.append({
                    "check": "realtime_channel_name_collision", "skip": True,
                    "file":  path, "line": line, "channel": name,
                    "reason": (
                        f"{path}:{line} creates db.channel('{name}') but "
                        f"another channel with the same name already exists "
                        f"at line {seen[name]}. Same-named channels share "
                        f"state in supabase-js — the second subscription "
                        f"silently replaces the first, breaking the earlier "
                        f"page feature. Either rename one or merge the "
                        f"subscriptions."
                    ),
                })
            else:
                seen[name] = line
    return issues


# ─── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "realtime_subscribed_table_exists",
    "realtime_payload_column_exists",
    "realtime_filter_column_exists",
    "realtime_channel_name_collision",
]
CHECK_LABELS = {
    "realtime_subscribed_table_exists": "L1  Every subscribed table exists in the schema",
    "realtime_payload_column_exists":   "L2  Every payload.new/old.X reads a real column on the subscribed table",
    "realtime_filter_column_exists":    "L3  Every filter clause column exists on the subscribed table",
    "realtime_channel_name_collision":  "L4  No two .channel('name') calls within one file share a name  [WARN]",
}


def main() -> None:
    def bold(s: str) -> str:
        return f"\033[1m{s}\033[0m"
    print(bold("\nRealtime Payload Consumer Contract Validator (4-layer)"))
    print("=" * 65)

    schema = load_table_columns()
    subs = _collect_subscriptions()
    channels = _collect_channel_names()
    print(f"  {len(schema)} tables in schema, {len(subs)} realtime subscriptions, "
          f"{sum(len(s['payload_fields']) for s in subs)} payload field reads.\n")

    all_issues: list[dict] = []
    all_issues += check_subscribed_tables_exist(subs, schema)
    all_issues += check_payload_columns_exist(subs, schema)
    all_issues += check_filter_columns_exist(subs, schema)
    all_issues += check_channel_name_collisions(channels)

    by_check: dict = defaultdict(list)
    for i in all_issues:
        by_check[i["check"]].append(i)

    n_pass = n_warn = n_fail = 0
    for name in CHECK_NAMES:
        items = by_check.get(name, [])
        warns = [i for i in items if i.get("skip")]
        fails = [i for i in items if not i.get("skip")]
        label = CHECK_LABELS[name]
        if not items:
            print(f"  \033[92mPASS\033[0m  {label}")
            n_pass += 1
        elif not fails:
            print(f"  \033[93mSKIP\033[0m  {label}")
            n_warn += 1
        else:
            print(f"  \033[91mFAIL\033[0m  {label}")
            n_fail += 1

    if all_issues:
        print(f"\n\033[91mIssues:\033[0m")
        for i in all_issues:
            tag = "\033[93mSKIP\033[0m" if i.get("skip") else "\033[91mFAIL\033[0m"
            print(f"  [{tag}] [{i['check']}]  {i['reason']}")

    print(f"\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL")

    report = {
        "validator":     "realtime_payload_contract",
        "subscriptions": subs,
        "summary":       {"pass": n_pass, "warn": n_warn, "fail": n_fail},
        "issues":        [i for i in all_issues if not i.get("skip")],
        "warnings":      [i for i in all_issues if i.get("skip")],
    }
    out = os.path.join(ROOT, "realtime_payload_contract_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=lambda o: list(o) if isinstance(o, set) else o)

    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
