"""
Cascade Behavior Detector -- WorkHive Platform
===============================================
Catches FK constraints declared without explicit ON DELETE behaviour.
Postgres defaults to NO ACTION when ON DELETE is omitted, which means
attempting to delete a referenced parent row fails with a constraint
violation -- in practice this surfaces as a confusing UI error ("Could
not delete: foreign key violation"). The right pattern is to declare
explicit intent: CASCADE (children deleted with parent), SET NULL
(children kept, FK column nulled), or RESTRICT (delete is blocked
deliberately).

Layer 1 -- FK without ON DELETE clause                                  [WARN]
  Any FK declared without an ON DELETE clause. Defaults to NO ACTION,
  which tends to surface as a UI error rather than a deliberate design
  choice.

Layer 2 -- FK with ON DELETE NO ACTION explicit                         [WARN]
  Same effect as L1 but written explicitly. Often a copy-paste of an
  earlier declaration where the author didn't think about the semantic
  -- worth surfacing for review.

Layer 3 -- Cascade distribution by behaviour (informational)            [INFO]
  Per-behaviour count: CASCADE / SET NULL / RESTRICT / NO ACTION.
  Helps spot lopsided patterns (e.g., everything is CASCADE -> delete
  ripple risk) or absence of SET NULL where a soft-detach would fit.

Layer 4 -- Tables most exposed to orphan risk (informational)           [INFO]
  Tables whose inbound FKs all use NO ACTION / RESTRICT / no-clause:
  if the parent row is deleted, the operation fails entirely. Common
  for catalog tables (intentional) but worth surfacing.

Skills consulted: data-engineer (FK design, RLS from day one), architect
(schema decisions, breaking-change flagging), maintenance-expert
(industrial domain rule: deleting an asset should NOT silently destroy
its work history -- SET NULL or RESTRICT are usually right for those FKs).
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

# Per-FK exemptions -- declared by (source_table, fk_column). Each entry
# needs a one-line justification.
CASCADE_OK = {
    # Both entries SUPERSEDED by 20260511000002_db_hygiene_batch.sql:
    #   parts_records.asset_ref_id -> assets : ON DELETE SET NULL
    #   worker_achievements.achievement_id -> achievement_definitions : ON DELETE CASCADE
    # The new migration drops the old constraint and re-creates it with
    # explicit clause. Allowlist kept as audit trail.
    ("parts_records", "asset_ref_id"):
        "SUPERSEDED by 20260511000002 (ON DELETE SET NULL)",
    ("worker_achievements", "achievement_id"):
        "SUPERSEDED by 20260511000002 (ON DELETE CASCADE)",
}

# Source tables we don't audit (third-party extensions, supabase metadata).
OPAQUE_SOURCES = {"users", "auth"}


# Inline FK in CREATE TABLE body:
#   col uuid REFERENCES tablename(id) ON DELETE CASCADE
# We capture col, target, ondelete
INLINE_FK_RE = re.compile(
    r"""(?P<col>\w+)\s+
        (?:uuid|bigint|integer|serial|text|smallint)\b
        [^,;\n]*?
        \bREFERENCES\s+
        (?:public\.|"public"\.)?
        "?(?P<target>\w+)"?
        \s*(?:\(\s*"?\w+"?\s*\))?
        (?P<tail>[^,;]*)""",
    re.IGNORECASE | re.VERBOSE,
)
# Constraint-style FK in CREATE TABLE body:
#   CONSTRAINT name FOREIGN KEY (col) REFERENCES table(col) ON DELETE ...
CONSTRAINT_FK_BODY_RE = re.compile(
    r"""(?:CONSTRAINT\s+\w+\s+)?
        FOREIGN\s+KEY\s*\(\s*"?(?P<col>\w+)"?\s*\)
        \s*REFERENCES\s+
        (?:public\.|"public"\.)?
        "?(?P<target>\w+)"?
        \s*(?:\(\s*"?\w+"?\s*\))?
        (?P<tail>[^,;]*)""",
    re.IGNORECASE | re.VERBOSE,
)
# pg_dump ALTER TABLE ONLY ... ADD CONSTRAINT ... FOREIGN KEY ... REFERENCES
ALTER_FK_RE = re.compile(
    r"""ALTER\s+TABLE\s+(?:ONLY\s+)?(?:public\.|"public"\.|IF\s+EXISTS\s+)?
        "?(?P<source>\w+)"?
        \s+ADD\s+(?:CONSTRAINT\s+"?\w+"?\s+)?
        FOREIGN\s+KEY\s*\(\s*"?(?P<col>\w+)"?\s*\)
        \s+REFERENCES\s+(?:public\.|"public"\.)?
        "?(?P<target>\w+)"?
        \s*(?:\(\s*"?\w+"?\s*\))?
        (?P<tail>[^;]*)""",
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)
# Match the ON DELETE clause inside a tail; default to "NO_CLAUSE".
ON_DELETE_RE = re.compile(
    r"\bON\s+DELETE\s+(CASCADE|SET\s+NULL|SET\s+DEFAULT|RESTRICT|NO\s+ACTION)\b",
    re.IGNORECASE,
)
CREATE_TABLE_RE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
        (?:public\.|"public"\.)?
        "?(?P<name>\w+)"?\s*\(
        (?P<body>[\s\S]*?)\n\s*\);""",
    re.IGNORECASE | re.VERBOSE,
)


def _parse_on_delete(tail: str) -> str:
    m = ON_DELETE_RE.search(tail or "")
    if not m:
        return "NO_CLAUSE"
    return m.group(1).upper().replace("  ", " ")


def collect_fks() -> list[dict]:
    """Return [{source, column, target, on_delete, file}] across all migrations."""
    fks: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        rel = os.path.relpath(path, MIGRATIONS_DIR)

        # Walk CREATE TABLE blocks; INSIDE the body extract inline FKs and
        # constraint-style FKs, treating the table as the source.
        for tm in CREATE_TABLE_RE.finditer(sql):
            source = tm.group("name").lower()
            body = tm.group("body")
            for fk in INLINE_FK_RE.finditer(body):
                key = (source, fk.group("col").lower(), fk.group("target").lower())
                if key in seen:
                    continue
                seen.add(key)
                fks.append({
                    "source":    source,
                    "column":    fk.group("col").lower(),
                    "target":    fk.group("target").lower(),
                    "on_delete": _parse_on_delete(fk.group("tail")),
                    "file":      rel,
                    "shape":     "inline",
                })
            for fk in CONSTRAINT_FK_BODY_RE.finditer(body):
                key = (source, fk.group("col").lower(), fk.group("target").lower())
                if key in seen:
                    continue
                seen.add(key)
                fks.append({
                    "source":    source,
                    "column":    fk.group("col").lower(),
                    "target":    fk.group("target").lower(),
                    "on_delete": _parse_on_delete(fk.group("tail")),
                    "file":      rel,
                    "shape":     "constraint_inline",
                })

        # ALTER TABLE ... ADD CONSTRAINT FOREIGN KEY (pg_dump format)
        for fk in ALTER_FK_RE.finditer(sql):
            key = (fk.group("source").lower(), fk.group("col").lower(), fk.group("target").lower())
            if key in seen:
                continue
            seen.add(key)
            fks.append({
                "source":    fk.group("source").lower(),
                "column":    fk.group("col").lower(),
                "target":    fk.group("target").lower(),
                "on_delete": _parse_on_delete(fk.group("tail")),
                "file":      rel,
                "shape":     "alter_pg_dump",
            })
    return fks


# -- Layer 1: FK without ON DELETE clause -----------------------------------

def check_no_clause(fks: list[dict]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for fk in fks:
        if fk["source"] in OPAQUE_SOURCES:
            continue
        if (fk["source"], fk["column"]) in CASCADE_OK:
            continue
        if fk["on_delete"] != "NO_CLAUSE":
            continue
        report.append({
            "source": fk["source"], "column": fk["column"],
            "target": fk["target"], "shape": fk["shape"],
            "file":   fk["file"],
        })
        issues.append({
            "check": "no_on_delete_clause", "skip": True,
            "reason": (
                f"{fk['file']}: FK {fk['source']}.{fk['column']} -> "
                f"{fk['target']} declared without ON DELETE clause "
                f"(defaults to NO ACTION). When a {fk['target']} row is "
                f"deleted, the operation fails -- usually surfaces as a "
                f"confusing UI error. Add explicit `ON DELETE CASCADE` "
                f"(child goes with parent), `ON DELETE SET NULL` "
                f"(detach but keep child), or `ON DELETE RESTRICT` "
                f"(deliberate block, document why)."
            ),
        })
    return issues, report


# -- Layer 2: Explicit NO ACTION --------------------------------------------

def check_no_action_explicit(fks: list[dict]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for fk in fks:
        if fk["source"] in OPAQUE_SOURCES:
            continue
        if (fk["source"], fk["column"]) in CASCADE_OK:
            continue
        if fk["on_delete"] != "NO ACTION":
            continue
        report.append({
            "source": fk["source"], "column": fk["column"],
            "target": fk["target"],
        })
        issues.append({
            "check": "no_action_explicit", "skip": True,
            "reason": (
                f"{fk['file']}: FK {fk['source']}.{fk['column']} -> "
                f"{fk['target']} uses explicit `ON DELETE NO ACTION`. "
                f"Same UI behaviour as no-clause -- if the block is "
                f"deliberate use `ON DELETE RESTRICT` (semantically "
                f"clearer); if not, switch to CASCADE or SET NULL."
            ),
        })
    return issues, report


# -- Layer 3: Cascade distribution (informational) -------------------------

def check_distribution(fks: list[dict]) -> tuple[list[dict], list[dict]]:
    counter: dict[str, int] = defaultdict(int)
    for fk in fks:
        counter[fk["on_delete"]] += 1
    rows = [
        {"behaviour": k, "count": v}
        for k, v in sorted(counter.items(), key=lambda kv: -kv[1])
    ]
    return [], rows


# -- Layer 4: Orphan-risk inventory (informational) -----------------------

def check_orphan_risk(fks: list[dict]) -> tuple[list[dict], list[dict]]:
    """Per-target table: count of inbound FKs by behaviour. Targets where
    100% of inbound FKs are NO ACTION / RESTRICT / NO_CLAUSE will block
    deletion entirely."""
    by_target: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for fk in fks:
        by_target[fk["target"]][fk["on_delete"]] += 1
    rows: list[dict] = []
    for target, counts in by_target.items():
        total = sum(counts.values())
        blockers = (counts.get("NO ACTION", 0)
                    + counts.get("RESTRICT", 0)
                    + counts.get("NO_CLAUSE", 0))
        if blockers == 0:
            continue
        rows.append({
            "target":      target,
            "total_in":    total,
            "blockers":    blockers,
            "by_behaviour": dict(counts),
        })
    rows.sort(key=lambda r: -r["blockers"])
    return [], rows


# -- Runner ----------------------------------------------------------------

CHECK_NAMES = [
    "no_on_delete_clause",
    "no_action_explicit",
    "distribution",
    "orphan_risk",
]
CHECK_LABELS = {
    "no_on_delete_clause":  "L1  Every FK declares an explicit ON DELETE behaviour          [WARN]",
    "no_action_explicit":   "L2  No FK uses explicit ON DELETE NO ACTION (use RESTRICT)     [WARN]",
    "distribution":         "L3  Cascade behaviour distribution (informational)             [INFO]",
    "orphan_risk":          "L4  Tables whose inbound FKs would block deletion (informational) [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nCascade Behavior Detector (4-layer)"))
    print("=" * 60)

    fks = collect_fks()
    print(f"  {len(fks)} FK constraint(s) parsed from migrations.\n")

    l1_issues, l1_report = check_no_clause(fks)
    l2_issues, l2_report = check_no_action_explicit(fks)
    l3_issues, l3_report = check_distribution(fks)
    l4_issues, l4_report = check_orphan_risk(fks)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l3_report:
        print(f"\n{bold('CASCADE BEHAVIOUR DISTRIBUTION (informational)')}")
        print("  " + "-" * 56)
        for r in l3_report:
            print(f"  {r['behaviour']:<24}  count={r['count']}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":            "cascade_behavior",
        "total_checks":         total,
        "passed":               n_pass,
        "warned":               n_warn,
        "failed":               n_fail,
        "n_fks":                len(fks),
        "no_on_delete_clause":  l1_report,
        "no_action_explicit":   l2_report,
        "distribution":         l3_report,
        "orphan_risk":          l4_report,
        "issues":               [i for i in all_issues if not i.get("skip")],
        "warnings":             [i for i in all_issues if i.get("skip")],
    }
    with open("cascade_behavior_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
