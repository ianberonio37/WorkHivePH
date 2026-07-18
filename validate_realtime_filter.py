"""
Cross-Hive Realtime Filter Coverage -- WorkHive Platform
=========================================================
Sister gate to `validate_realtime_payload_contract` (which validates
payload SHAPE) and `validate_realtime_cleanup` (which validates
listener removal). This gate validates SCOPE: every realtime
subscription on a hive-scoped table must include
`filter: 'hive_id=eq.${HIVE_ID}'` so a worker browser only receives
events from their own hive. Without it, a worker on Hive A sees
postgres_changes events from Hive B in real time -- cross-tenant leak.

Layer 1 -- Hive-scoped table without filter clause                       [WARN]
  Any `db.channel(...).on('postgres_changes', { table: 'X' }, ...)`
  subscribing to a table that has a `hive_id` column, where the
  config object lacks `filter: '...hive_id=eq...'`. The worker
  browser receives ALL hives' events.

Layer 2 -- Hive-scoped channel name without HIVE_ID interpolation        [WARN]
  Channels named `'hive-feed'`, `'hive-pm'`, etc. without a
  `${HIVE_ID}` suffix. Channel names are partition keys for
  Supabase Realtime; a name without the hive id means workers
  from other hives JOIN the same channel.

Layer 3 -- Per-table subscription distribution (informational)           [INFO]
  Counts of subscriptions per (table, hive_filtered) combination.
  Surfaces tables that get watched but never filtered.

Layer 4 -- Per-page subscription density (informational)                 [INFO]
  Pages ranked by total realtime subscriptions. High density pages
  benefit most from filter discipline.

Skills consulted: realtime-engineer (Realtime channel partitioning,
filter syntax), multitenant-engineer (hive isolation -- the same
discipline that powers RLS at the DB level must extend to live
events), security (cross-tenant leak via realtime is the asymmetric
counterpart of RLS-permissive policies).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


MIGRATIONS_DIR = os.path.join("supabase", "migrations")

EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")


# Per-subscription exemptions. Each entry needs a one-line justification.
REALTIME_FILTER_OK = {
    # Global channels intentionally cross-hive (public feed / marketplace).
    ("community.html", "community_posts"):
        "community-global-feed is the cross-hive public feed; rendered as opt-in tab",
    ("marketplace.html", "marketplace_listings"):
        "marketplace listings are platform-wide by design (cross-hive sellers)",
    # Worker-scoped channel (`'worker-appr:' + WORKER_NAME`); the channel
    # name partition is by worker_name, so RLS + worker-name filter on the
    # subscribed table give the same isolation guarantee as hive-id.
    ("hive.html", "assets"):
        "worker-appr:WORKER_NAME channel; worker-scoped not hive-scoped",
    ("hive.html", "inventory_items"):
        "worker-appr:WORKER_NAME channel; worker-scoped not hive-scoped",
}

CREATE_TABLE_RE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
        (?:public\.|"public"\.)?
        "?(?P<name>\w+)"?\s*\(
        (?P<body>[\s\S]*?)\n\s*\);""",
    re.IGNORECASE | re.VERBOSE,
)
ALTER_ADD_RE = re.compile(
    r"""ALTER\s+TABLE\s+(?:public\.|"public"\.|IF\s+EXISTS\s+)?
        "?(?P<name>\w+)"?\s+ADD\s+COLUMN(?:\s+IF\s+NOT\s+EXISTS)?\s+
        "?(?P<col>\w+)"?""",
    re.IGNORECASE | re.VERBOSE,
)


def collect_hive_scoped_tables() -> set[str]:
    out: set[str] = set()
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        for tm in CREATE_TABLE_RE.finditer(sql):
            table = tm.group("name").lower()
            body = tm.group("body").lower()
            if re.search(r"\bhive_id\b", body):
                out.add(table)
        for am in ALTER_ADD_RE.finditer(sql):
            if am.group("col").lower() == "hive_id":
                out.add(am.group("name").lower())
    return out


# Match `db.channel('NAME', ...)` followed by chained `.on(...)` calls.
# We do depth-aware capture per channel block so multi-line `.on()` configs
# don't get truncated. Channel block is bounded by the next semicolon at
# depth 0 OR the next `db.channel(` start.
CHANNEL_START_RE = re.compile(r"""\bdb\.channel\s*\(\s*(?P<name>['"`][^'"`]+['"`])""")


def _slice_channel_block(src: str, start: int) -> tuple[str, int]:
    """From start (position of `db.channel(`), walk forward to the closing
    `.subscribe()` call or the next top-level `db.channel(` / `;` boundary."""
    i = start
    depth = 0
    in_str: str | None = None
    end = len(src)
    while i < len(src):
        ch = src[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
        elif ch in "\"'`":
            in_str = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == ";" and depth == 0:
            return src[start:i+1], i + 1
        i += 1
    return src[start:], end


# Inside a channel block, find each `.on('postgres_changes', { ... }, ...)`
# and extract the table + filter.
ON_PG_RE = re.compile(
    r"""\.on\s*\(\s*['"`]postgres_changes['"`]\s*,\s*\{(?P<config>[^{}]*(?:\{[^{}]*\}[^{}]*)*?)\}""",
    re.DOTALL | re.VERBOSE,
)
TABLE_RE  = re.compile(r"""['"`]?table['"`]?\s*:\s*['"`](?P<table>[a-z_][a-z0-9_]*)['"`]""")
FILTER_RE = re.compile(r"""['"`]?filter['"`]?\s*:\s*['"`](?P<filter>[^'"`]+)['"`]""")
HIVE_FILTER_RE = re.compile(r"""hive_id\s*=\s*eq\.""", re.IGNORECASE)
HIVE_ID_NAME_RE = re.compile(r"""\$\{[^}]*HIVE_ID[^}]*\}""")


def list_pages() -> list[str]:
    out: list[str] = []
    for path in sorted(glob.glob("*.html")):
        if any(p in path.lower() for p in EXCLUDED_HTML_PATTERNS):
            continue
        out.append(path)
    for path in sorted(glob.glob("*.js")):
        if path.endswith(".min.js"):
            continue
        out.append(path)
    return out


def find_subscriptions(src: str) -> list[dict]:
    """Return [{name, table, has_filter, has_hive_filter, channel_has_hive_id}]."""
    out: list[dict] = []
    # Capture the channel argument up to the closing `)` of `db.channel(...)`
    # so concat patterns like `'hive-feed:' + HIVE_ID` are visible.
    for m in CHANNEL_START_RE.finditer(src):
        name = m.group("name")
        # Look at the next ~150 chars after `db.channel(` to capture the
        # full first argument including any `+ HIVE_ID` concat.
        first_arg_window = src[m.end():m.end()+200]
        # Stop at the first `)` at depth 0 in the argument list.
        depth = 0
        cut = len(first_arg_window)
        for i, ch in enumerate(first_arg_window):
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    cut = i
                    break
                depth -= 1
            elif ch == "," and depth == 0:
                cut = i
                break
        first_arg_full = name + first_arg_window[:cut]
        block, _ = _slice_channel_block(src, m.start())
        channel_has_hive_id = bool(
            HIVE_ID_NAME_RE.search(first_arg_full)
            or re.search(r"""\+\s*\w*HIVE_ID""", first_arg_full)
            or re.search(r"""\$\{[^}]*HIVE_ID""", first_arg_full)
        )
        for om in ON_PG_RE.finditer(block):
            config = om.group("config")
            tm = TABLE_RE.search(config)
            if not tm:
                continue
            table = tm.group("table").lower()
            fm = FILTER_RE.search(config)
            filter_text = fm.group("filter") if fm else ""
            out.append({
                "name":               name,
                "table":              table,
                "has_filter":         bool(fm),
                "has_hive_filter":    bool(fm and HIVE_FILTER_RE.search(filter_text)),
                "channel_has_hive_id": channel_has_hive_id,
                "filter_text":        filter_text[:60],
            })
    return out


# -- Layer 1: Hive-scoped table without filter ----------------------------

def check_missing_filter(
    pages: list[str],
    hive_tables: set[str],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path in pages:
        src = read_file(path) or ""
        for sub in find_subscriptions(src):
            if (path, sub["table"]) in REALTIME_FILTER_OK:
                continue
            if sub["table"] not in hive_tables:
                continue
            if sub["has_hive_filter"]:
                continue
            # Channel name with HIVE_ID interpolation also counts as scope.
            if sub["channel_has_hive_id"]:
                continue
            report.append({
                "path":    path,
                "channel": sub["name"],
                "table":   sub["table"],
            })
            issues.append({
                "check": "missing_filter", "skip": True,
                "reason": (
                    f"{path}: db.channel({sub['name']}).on('postgres_changes', "
                    f"{{ table: '{sub['table']}', ... }}) lacks "
                    f"`filter: 'hive_id=eq.${{HIVE_ID}}'` AND the channel "
                    f"name does not include ${{HIVE_ID}} either. Workers "
                    f"on other hives will receive these events. Add the "
                    f"filter or scope the channel name."
                ),
            })
    return issues, report


# -- Layer 2: Hive-scoped channel name without HIVE_ID interpolation -------

def check_channel_naming(pages: list[str]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    HIVE_PREFIX_RE = re.compile(r"""['"`](?:hive-|hive_)[\w-]*['"`]""")
    for path in pages:
        src = read_file(path) or ""
        for m in CHANNEL_START_RE.finditer(src):
            name = m.group("name")
            if not HIVE_PREFIX_RE.match(name):
                continue
            # If the very next chars include `+` followed by a HIVE_ID-ish
            # variable, the name IS scoped.
            tail = src[m.end():m.end()+60]
            if re.match(r"""\s*\+\s*\w*HIVE_ID""", tail) or "${" in name:
                continue
            report.append({"path": path, "channel": name})
            issues.append({
                "check": "channel_naming", "skip": True,
                "reason": (
                    f"{path}: channel name {name} starts with `hive-` / "
                    f"`hive_` but does not include the HIVE_ID variable. "
                    f"Different hives' workers all join the same channel. "
                    f"Either append `+ HIVE_ID` / `:${{HIVE_ID}}` to the "
                    f"name, or rename to a non-hive prefix."
                ),
            })
    return issues, report


# -- Layer 1c: Compound (multi-predicate) filter = silently-dead feed [FAIL] --

def check_compound_filter(pages: list[str]) -> tuple[list[dict], list[dict]]:
    """Supabase Realtime accepts EXACTLY ONE predicate per postgres_changes listener.
    A compound '&'-joined filter string (e.g. 'status=eq.published&section=eq.parts') is a
    single MALFORMED predicate whose value is the literal 'published&section=eq.parts' — it
    matches no WAL row, so the feed is silently dead. Found live on marketplace.html:2478
    (deep-walk dim-11, 2026-07-06): the "New listing just posted" toast/prepend never fired.
    Fix = a single predicate + re-check the rest of the conditions in the callback."""
    issues: list[dict] = []
    report: list[dict] = []
    for path in pages:
        src = read_file(path) or ""
        for sub in find_subscriptions(src):
            if "&" in sub.get("filter_text", ""):
                report.append({"path": path, "table": sub["table"], "filter": sub["filter_text"]})
                issues.append({
                    "check": "compound_filter",
                    "reason": (
                        f"{path}: db.channel({sub['name']}).on('postgres_changes', "
                        f"{{ table: '{sub['table']}', filter: '{sub['filter_text']}' }}) uses a "
                        f"COMPOUND '&'-joined filter. Supabase Realtime allows exactly ONE predicate "
                        f"per listener, so the '&' string matches no row and the feed is silently "
                        f"dead. Use one predicate (e.g. 'section=eq.X') and re-check the other "
                        f"conditions inside the callback."
                    ),
                })
    return issues, report


# -- Layer 3: Subscription distribution (informational) -------------------

def check_distribution(
    pages: list[str],
    hive_tables: set[str],
) -> tuple[list[dict], list[dict]]:
    counter: dict[tuple[str, bool], int] = defaultdict(int)
    for path in pages:
        src = read_file(path) or ""
        for sub in find_subscriptions(src):
            scoped = sub["has_hive_filter"] or sub["channel_has_hive_id"]
            if sub["table"] in hive_tables:
                counter[(sub["table"], scoped)] += 1
    rows: list[dict] = []
    by_table: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for (table, scoped), n in counter.items():
        by_table[table]["scoped" if scoped else "unscoped"] += n
    for table, by in sorted(by_table.items(), key=lambda kv: -sum(kv[1].values())):
        rows.append({
            "table":    table,
            "scoped":   by.get("scoped",   0),
            "unscoped": by.get("unscoped", 0),
        })
    return [], rows


# -- Layer 4: Per-page density (informational) ----------------------------

def check_page_density(pages: list[str]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for path in pages:
        src = read_file(path) or ""
        subs = find_subscriptions(src)
        if not subs:
            continue
        rows.append({
            "path":    path,
            "n_subs":  len(subs),
            "tables":  sorted({s["table"] for s in subs})[:6],
        })
    rows.sort(key=lambda r: -r["n_subs"])
    return [], rows


# -- Runner ---------------------------------------------------------------

CHECK_NAMES = [
    "compound_filter",
    "missing_filter",
    "channel_naming",
    "distribution",
    "page_density",
]
CHECK_LABELS = {
    "compound_filter": "L1c Realtime filter is a SINGLE predicate (no '&'-joined compound = dead feed) [FAIL]",
    "missing_filter":  "L1  Hive-scoped table subscription has hive_id filter or HIVE_ID name [WARN]",
    "channel_naming":  "L2  Channel name with `hive-` prefix includes HIVE_ID variable        [WARN]",
    "distribution":    "L3  Per-table subscription scoped/unscoped distribution (info)        [INFO]",
    "page_density":    "L4  Per-page realtime subscription density (informational)            [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nCross-Hive Realtime Filter Coverage (4-layer)"))
    print("=" * 60)

    hive_tables = collect_hive_scoped_tables()
    pages = list_pages()
    print(f"  {len(hive_tables)} hive-scoped table(s); "
          f"{len(pages)} page(s) scanned.\n")

    l1c_issues, l1c_report = check_compound_filter(pages)
    l1_issues, l1_report = check_missing_filter(pages, hive_tables)
    l2_issues, l2_report = check_channel_naming(pages)
    l3_issues, l3_report = check_distribution(pages, hive_tables)
    l4_issues, l4_report = check_page_density(pages)

    all_issues = l1c_issues + l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l3_report:
        print(f"\n{bold('SUBSCRIPTION SCOPING DISTRIBUTION (informational)')}")
        print("  " + "-" * 56)
        for r in l3_report[:8]:
            print(f"  {r['table']:<32}  scoped={r['scoped']:<3}  unscoped={r['unscoped']}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":      "realtime_filter",
        "total_checks":   total,
        "passed":         n_pass,
        "warned":         n_warn,
        "failed":         n_fail,
        "n_hive_tables":  len(hive_tables),
        "compound_filter": l1c_report,
        "missing_filter": l1_report,
        "channel_naming": l2_report,
        "distribution":   l3_report,
        "page_density":   l4_report,
        "issues":         [i for i in all_issues if not i.get("skip")],
        "warnings":       [i for i in all_issues if i.get("skip")],
    }
    with open("realtime_filter_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
