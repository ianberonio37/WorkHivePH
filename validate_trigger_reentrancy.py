"""
Trigger Reentrancy Safety -- WorkHive Platform
================================================
Catches the classic infinite-recursion bug where a trigger function
writes to the same table that fires it without a guard. Postgres
allows trigger recursion up to `max_stack_depth` (default 2MB), at
which point the entire transaction rolls back -- often surfacing as
a cryptic "stack depth limit exceeded" error in production.

The safe pattern:
  CREATE TRIGGER trg ... FOR EACH ROW
  WHEN (NEW.x IS DISTINCT FROM OLD.x)                <-- guard at trigger
  EXECUTE FUNCTION ...

Or inside the function:
  IF NEW.x IS NOT DISTINCT FROM OLD.x THEN RETURN NEW; END IF;

Or via `pg_trigger_depth()` check for trigger-call recursion limits.

Layer 1 -- Trigger fn writes to its own trigger table without guard     [FAIL]
  Any trigger function that contains `UPDATE <same_table>` or
  `INSERT INTO <same_table>` where <same_table> equals the table the
  trigger is attached to, AND the function body has NO recursion
  guard (`IS DISTINCT FROM` / `pg_trigger_depth() > 1` / explicit
  WHEN clause on the CREATE TRIGGER).

Layer 2 -- Trigger writes to a table that has its own trigger          [WARN]
  Indirect-loop risk: trigger on A writes to B; B has its own
  trigger that writes back to A. Detects pairs of write-chains
  between tables. Manual review needed.

Layer 3 -- Trigger inventory per table (informational)                  [INFO]
  Per-table count of attached triggers + functions. Helps spot
  tables with high trigger density worth scrutinising.

Layer 4 -- pg_trigger_depth() usage adoption (informational)            [INFO]
  Functions that explicitly check pg_trigger_depth() — the most
  bulletproof recursion guard. Counts adoption.

Skills consulted: data-engineer (Postgres trigger semantics), security
(stack-depth exhaustion is a DoS surface), architect (table-coupling
review through trigger graphs).
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

# Per (fn_name, table) exemptions for L1 with one-line justification.
TRIGGER_REENTRANCY_OK: dict[tuple[str, str], str] = {
    # ("fn_name", "table"): "reason"
}

CREATE_FN_RE = re.compile(
    r"""CREATE(?:\s+OR\s+REPLACE)?\s+FUNCTION\s+
        (?:(?:public|auth|"\w+")\.)?
        "?(?P<name>\w+)"?\s*\([^)]*\)""",
    re.IGNORECASE | re.VERBOSE,
)
DOLLAR_QUOTE_RE = re.compile(r"\$(?P<tag>\w*)\$")

TRIGGER_DECL_RE = re.compile(
    r"""CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+(?P<tname>\w+)\s+
        (?:BEFORE|AFTER|INSTEAD\s+OF)[\s\S]*?
        ON\s+(?:(?:public|auth)\.)?"?(?P<table>\w+)"?
        [\s\S]*?
        (?:WHEN\s*\((?P<when>[^)]*)\)\s+)?
        EXECUTE\s+(?:PROCEDURE|FUNCTION)\s+
        (?:(?:public|auth)\.)?"?(?P<fn>\w+)""",
    re.IGNORECASE | re.VERBOSE,
)

# Guard patterns inside a function body.
GUARD_PATTERNS = [
    re.compile(r"\bIS\s+(?:NOT\s+)?DISTINCT\s+FROM\b", re.IGNORECASE),
    re.compile(r"\bpg_trigger_depth\s*\(\s*\)", re.IGNORECASE),
    re.compile(r"\bNEW\.\w+\s*!=\s*OLD\.\w+", re.IGNORECASE),
    re.compile(r"\bOLD\.\w+\s*!=\s*NEW\.\w+", re.IGNORECASE),
    re.compile(r"\bNEW\.\w+\s*<>\s*OLD\.\w+", re.IGNORECASE),
]


def _walk_function_blocks(sql: str) -> list[dict]:
    """Same dollar-quote-aware walker as validate_function_security."""
    out: list[dict] = []
    pos = 0
    while True:
        m = CREATE_FN_RE.search(sql, pos)
        if not m:
            break
        start = m.start()
        i = m.end()
        opened_tag: str | None = None
        end = -1
        while i < len(sql):
            if opened_tag is None:
                ch = sql[i]
                if ch == "$":
                    qm = DOLLAR_QUOTE_RE.match(sql, i)
                    if qm:
                        opened_tag = qm.group("tag")
                        i = qm.end()
                        continue
                if ch == ";":
                    end = i + 1
                    break
                i += 1
            else:
                tag_close = f"${opened_tag}$"
                idx = sql.find(tag_close, i)
                if idx == -1:
                    i = len(sql)
                else:
                    i = idx + len(tag_close)
                    opened_tag = None
        if end < 0:
            end = i
        out.append({
            "name":      m.group("name"),
            "full_text": sql[start:end],
            "start":     start,
            "end":       end,
        })
        pos = end
    return out


def _write_targets(fn_body: str) -> set[str]:
    """Return the set of tables this fn writes to (INSERT/UPDATE/DELETE)."""
    out: set[str] = set()
    patterns = [
        r"INSERT\s+INTO\s+(?:(?:public|auth)\.)?\"?(\w+)\"?",
        r"UPDATE\s+(?:(?:public|auth)\.)?\"?(\w+)\"?",
        r"DELETE\s+FROM\s+(?:(?:public|auth)\.)?\"?(\w+)\"?",
    ]
    for pat in patterns:
        for m in re.finditer(pat, fn_body, re.IGNORECASE):
            tbl = m.group(1).lower()
            # Skip SQL keywords that look like table names.
            if tbl in {"ONLY", "RECURSIVE", "TABLE", "INTO"}:
                continue
            out.add(tbl)
    return out


def _has_guard(fn_body: str) -> bool:
    for rx in GUARD_PATTERNS:
        if rx.search(fn_body):
            return True
    return False


def _read_all_migrations() -> str:
    return "\n".join(read_file(p) or "" for p in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))))


# -- Build: triggers + their attached tables + fns ---------------------

def collect_triggers() -> list[dict]:
    out: list[dict] = []
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        for tm in TRIGGER_DECL_RE.finditer(sql):
            out.append({
                "file":  os.path.basename(path),
                "name":  tm.group("tname"),
                "table": tm.group("table").lower(),
                "fn":    tm.group("fn"),
                "when":  (tm.group("when") or "").strip(),
            })
    return out


def collect_function_bodies() -> dict[str, str]:
    """{fn_name: full_text} for every CREATE FUNCTION (last-writer-wins by name)."""
    out: dict[str, str] = {}
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        for fn in _walk_function_blocks(sql):
            out[fn["name"]] = fn["full_text"]
    return out


# -- Layer 1: fn writes to its own trigger table without guard ---------

def check_self_write_without_guard() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    triggers = collect_triggers()
    fn_bodies = collect_function_bodies()
    for trig in triggers:
        fn_body = fn_bodies.get(trig["fn"])
        if not fn_body:
            continue
        writes = _write_targets(fn_body)
        if trig["table"] not in writes:
            continue
        # WHEN clause on the CREATE TRIGGER acts as a guard.
        if trig["when"] and re.search(r"DISTINCT|!=|<>", trig["when"], re.IGNORECASE):
            continue
        if _has_guard(fn_body):
            continue
        if (trig["fn"], trig["table"]) in TRIGGER_REENTRANCY_OK:
            continue
        report.append({
            "trigger": trig["name"],
            "table":   trig["table"],
            "fn":      trig["fn"],
            "file":    trig["file"],
        })
        issues.append({
            "check": "self_write_without_guard", "skip": False,
            "reason": (
                f"{trig['file']}: trigger `{trig['name']}` on `{trig['table']}` "
                f"calls function `{trig['fn']}` which writes back to the "
                f"same table WITHOUT a recursion guard (IS DISTINCT FROM / "
                f"pg_trigger_depth() / WHEN clause). Risks infinite "
                f"recursion until stack depth exhausts. Add a guard "
                f"clause, or list (`{trig['fn']}`, `{trig['table']}`) in "
                f"TRIGGER_REENTRANCY_OK with a justification."
            ),
        })
    return issues, report


# -- Layer 2: indirect loop risk ----------------------------------------

def check_indirect_loop() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    triggers = collect_triggers()
    fn_bodies = collect_function_bodies()
    # Build write graph: (source_table) -> {target_tables}
    writes_by_table: dict[str, set[str]] = defaultdict(set)
    for trig in triggers:
        fn_body = fn_bodies.get(trig["fn"]) or ""
        for tgt in _write_targets(fn_body):
            writes_by_table[trig["table"]].add(tgt)
    # Look for any pair (A,B) where A writes to B and B writes back to A.
    seen_pairs: set[tuple[str, str]] = set()
    for source, targets in writes_by_table.items():
        for tgt in targets:
            if tgt == source:
                continue   # self-write — L1 covers
            if source in writes_by_table.get(tgt, set()):
                pair = tuple(sorted([source, tgt]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                report.append({"pair": list(pair)})
                issues.append({
                    "check": "indirect_loop", "skip": True,
                    "reason": (
                        f"Tables `{pair[0]}` <-> `{pair[1]}` have triggers "
                        f"writing back to each other. Risk of mutual "
                        f"recursion. Manual review: add guard clauses or "
                        f"merge the writes into one direction."
                    ),
                })
    return issues, report


# -- Layer 3: trigger inventory per table ------------------------------

def check_inventory() -> tuple[list[dict], list[dict]]:
    triggers = collect_triggers()
    by_table: dict[str, list[str]] = defaultdict(list)
    for t in triggers:
        by_table[t["table"]].append(t["name"])
    rows: list[dict] = []
    for table, names in sorted(by_table.items(), key=lambda kv: -len(kv[1])):
        rows.append({"table": table, "n_triggers": len(names), "names": names[:5]})
    return [], rows


# -- Layer 4: pg_trigger_depth() adoption ------------------------------

def check_depth_adoption() -> tuple[list[dict], list[dict]]:
    sql = _read_all_migrations()
    matches = re.findall(r"pg_trigger_depth\s*\(", sql, re.IGNORECASE)
    return [], [{"metric": "pg_trigger_depth_call_sites", "count": len(matches)}]


# -- Runner --------------------------------------------------------------

CHECK_NAMES = [
    "self_write_without_guard",
    "indirect_loop",
    "inventory",
    "depth_adoption",
]
CHECK_LABELS = {
    "self_write_without_guard": "L1  No trigger fn writes to its own table without a guard      [FAIL]",
    "indirect_loop":            "L2  No mutual A<->B trigger write loops                        [WARN]",
    "inventory":                "L3  Trigger count per table (informational)                    [INFO]",
    "depth_adoption":           "L4  pg_trigger_depth() guard adoption count (informational)    [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nTrigger Reentrancy Safety (4-layer)"))
    print("=" * 60)

    l1_issues, l1_report = check_self_write_without_guard()
    l2_issues, l2_report = check_indirect_loop()
    l3_issues, l3_report = check_inventory()
    l4_issues, l4_report = check_depth_adoption()

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l3_report:
        print(f"\n{bold('TRIGGER INVENTORY (top tables)')}")
        print("  " + "-" * 56)
        for r in l3_report[:8]:
            sample = ", ".join(r["names"][:3])
            print(f"  {r['table']:<28}  triggers={r['n_triggers']:<2}  ({sample})")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":                "trigger_reentrancy",
        "total_checks":             total,
        "passed":                   n_pass,
        "warned":                   n_warn,
        "failed":                   n_fail,
        "self_write_without_guard": l1_report,
        "indirect_loop":            l2_report,
        "inventory":                l3_report,
        "depth_adoption":           l4_report,
        "issues":                   [i for i in all_issues if not i.get("skip")],
        "warnings":                 [i for i in all_issues if i.get("skip")],
    }
    with open("trigger_reentrancy_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
