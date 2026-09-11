#!/usr/bin/env python3
"""
Does every read and write name a column its table actually has?  (L0, static, no DB)
==========================================================================

THE CLASS, found 2026-09-08 in one file and worth a gate because of HOW it hides.

`supabase-js` does not throw when PostgREST refuses a row - it resolves with `{ error }`. So a write that
names a column the table does not have fails in the quietest way available: no exception, no console error
unless someone reads the result, and a `return true` immediately afterwards reporting success. Five of them
were sitting in `voice-handler.js`, all from the same batch of companion infra writes:

  · _emitAuditEvent    wrote `event_type`     - ai_audit_log's column is `event`
  · _executeErasure    wrote `event_type`     - the record OF a deletion, same mistake
  · _buildAuditCsv     emitted an `event_type` header and read `r.event_type` off every row
  · _logKnowledgeGap   wrote `source`         - ai_knowledge_gap has no such column
  · the escalation upsert wrote `negative_count` - the column is `thumbs_down_7d`

The last one is the reason this is a gate and not a note. It is on a LIVE path - every thumbs-down from a
worker with three negatives in a week - and its own comment says "the dashboard reads this flag to prompt
supervisor outreach". The flag had never once been set. Four of the five were in functions nothing called,
which is the second lesson: dead code is not merely absent, it is unexercised, so its bugs keep.

WHERE THE COLUMNS COME FROM. `substrate/table-rls/*.md`, the platform's own knowledge substrate, one file
per table carrying a `Columns (*=NOT NULL)` line. That is the retrieve-first source this repo already
prefers over reading schema by hand, and it needs no database, so this gate runs in `--fast`.

WHAT IT READS. `.from('<table>').insert|update|upsert({ ... })` with an inline object, AND the shape that
hid the worst of the five: `.insert(row)` where `row` is a `const` object built just above. An object using
a spread, computed keys or shorthand is SKIPPED rather than guessed at - a gate that invents an answer for
what it cannot parse is worse than one that says nothing about it, and the count of skips is printed so the
silence is visible.

A table with no substrate note is skipped and counted, for the same reason.

  python validate_write_names_a_real_column.py
  python validate_write_names_a_real_column.py --selftest
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"
BASELINE = 0
REPORT = "write_column_report.json"

# ★AND THE SAME QUESTION OF READS, which fail LOUDER and just as invisibly: PostgREST rejects the whole
# query with a 400 when a select names a column that is not there, supabase-js resolves it, and a caller
# doing `data || []` renders an empty list. worker-drawer.js selected `reorder_point` from inventory_items -
# a column the platform KNOWS does not exist, because migration 20260510000003 created
# v_inventory_items_truth precisely to alias it - so the supervisor's worker drawer has always said "No
# low-stock items assigned" on a read that never once succeeded.
READ_SELECT = re.compile(r"\.from\(\s*['\"]([a-z0-9_]+)['\"]\s*\)\s*\.\s*select\(\s*['\"]([^'\"]*)['\"]")
WRITE_INLINE = re.compile(r"\.from\(\s*['\"]([a-z0-9_]+)['\"]\s*\)\s*\.\s*(insert|update|upsert)\s*\(\s*\{")
WRITE_IDENT = re.compile(r"\.from\(\s*['\"]([a-z0-9_]+)['\"]\s*\)\s*\.\s*(insert|update|upsert)\s*\(\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*[,)]")


def table_columns(root: str = "substrate/table-rls") -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for path in glob.glob(os.path.join(root, "*.md")):
        name = os.path.basename(path)[:-3]
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        m = re.search(r"^Columns \(\*=NOT NULL\): (.+)$", text, re.M)
        if m:
            cols = [c.strip().rstrip("*") for c in m.group(1).split(",") if c.strip()]
            # ★THE SUBSTRATE PRINTS AT MOST 50 COLUMNS (`_cols[:50]` in build_substrate.py). A table at
            # that cap has a tail this cannot see, and treating a truncated list as complete would make
            # every column past the fiftieth read as "unknown" - the gate manufacturing findings out of
            # its own source's limit. The widest table today is 31 columns so nothing is truncated, but a
            # list sitting exactly at 50 is not evidence of a complete list, so it is not used as one.
            if len(cols) >= 50:
                continue
            out[name] = set(cols)
    return out


CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?([a-z0-9_]+)\s*\(", re.I)
ADD_COLUMN = re.compile(
    r"ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:public\.)?([a-z0-9_]+)\s+ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-z0-9_]+)", re.I)
# a column definition's leading name, skipping table-level constraint lines
COLUMN_LINE = re.compile(r"^\s*([a-z_][a-z0-9_]*)\s+[a-z]", re.I)
NOT_A_COLUMN = re.compile(r"^\s*(constraint|primary|unique|foreign|check|exclude|like|inherits)\b", re.I)


def migration_columns(root: str = "supabase/migrations") -> dict[str, set[str]]:
    """Columns parsed from CREATE TABLE / ALTER TABLE ADD COLUMN.

    ★A SUPPLEMENT, NEVER AN OVERRIDE. substrate/table-rls covers TENANT tables only - by design, it is
    built for tables carrying hive_id or auth_uid - so 19 relations the pages really use (hives,
    marketplace_reviews, service_vouchers, the platform-admin table) had no note and were skipped
    entirely. Migrations describe all of them and need no database. But regex is not a SQL parser, and
    a WRONG column list manufactures findings, which is the failure this whole gate exists to avoid: so
    a parsed table is used ONLY where the substrate has nothing, and only when the parse looks sane."""
    out: dict[str, set[str]] = {}
    for path in sorted(glob.glob(os.path.join(root, "*.sql"))):
        try:
            sql = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for m in CREATE_TABLE.finditer(sql):
            table = m.group(1).lower()
            depth, j, body = 1, m.end(), []
            while j < len(sql) and depth:
                ch = sql[j]
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        break
                body.append(ch)
                j += 1
            cols, para = set(), 0
            for raw in "".join(body).split("\n"):
                # only top-level lines: a CHECK (...) spanning lines must not contribute names
                line = raw
                if para == 0 and not NOT_A_COLUMN.match(line):
                    cm = COLUMN_LINE.match(line)
                    if cm:
                        cols.add(cm.group(1).lower())
                para += line.count("(") - line.count(")")
                if para < 0:
                    para = 0
            if len(cols) >= 2:
                out.setdefault(table, set()).update(cols)
        for m in ADD_COLUMN.finditer(sql):
            out.setdefault(m.group(1).lower(), set()).add(m.group(2).lower())
    return out


def object_body(src: str, brace_index: int) -> str | None:
    """The text between a `{` and its matching `}`; None if unbalanced."""
    depth = 0
    for j in range(brace_index, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[brace_index + 1:j]
    return None


def top_level_keys(body: str) -> list[str] | None:
    """Keys of an object literal, or None when it cannot be read honestly."""
    if "..." in body:
        return None                      # a spread carries keys this cannot see
    parts, depth, buf = [], 0, ""
    for ch in body:
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    keys = []
    for part in parts:
        if not part.strip():
            continue
        m = re.match(r"\s*(?:\/\/[^\n]*\n\s*)*([A-Za-z_$][A-Za-z0-9_$]*)\s*:", part)
        if m:
            keys.append(m.group(1))
        else:
            return None                  # shorthand, computed key, comment shape we do not model
    return keys


def scan(paths, cols) -> tuple[list[dict], int, int]:
    """Returns (findings, checked, skipped)."""
    findings, checked, skipped = [], 0, 0
    for path in paths:
        try:
            src = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue

        def record(table, op, keys, at):
            nonlocal checked, skipped
            if table not in cols:
                skipped += 1
                return
            if keys is None:
                skipped += 1
                return
            checked += 1
            unknown = [k for k in keys if k not in cols[table]]
            if unknown:
                findings.append({
                    "file": path, "line": src[:at].count("\n") + 1, "table": table,
                    "op": op, "unknown": unknown,
                    "have": sorted(cols[table]),
                })

        for m in WRITE_INLINE.finditer(src):
            body = object_body(src, m.end() - 1)
            record(m.group(1), m.group(2), top_level_keys(body) if body is not None else None, m.start())

        # ★AND THE SHAPE THAT HID THE WORST ONE: `.insert(row)` with the object built above. _emitAuditEvent
        # is exactly this, so an inline-only reader would have missed the write that mattered most.
        for m in WRITE_IDENT.finditer(src):
            ident = m.group(3)
            # (*)THE NEAREST PRECEDING DECLARATION, NOT THE FIRST IN THE FILE. `re.search` returns the
            # first match, so a common name like `payload` resolved to whichever function happened to
            # declare it earliest - and this gate's first two findings were its own bug: asset-hub's
            # rcm_strategies write, graded against a `payload` built for a different table in a different
            # function. Every key came back "unknown", which is the tell: a real mistake is one or two
            # columns, a whole object rejected means the instrument fetched the wrong object.
            decls = list(re.finditer(r"(?:const|let|var)\s+" + re.escape(ident) + r"\s*=\s*\{", src[:m.start()]))
            if not decls:
                skipped += 1
                continue
            decl = decls[-1]
            body = object_body(src, decl.end() - 1)
            record(m.group(1), m.group(2), top_level_keys(body) if body is not None else None, m.start())

        for m in READ_SELECT.finditer(src):
            sel = m.group(2)
            # An embedded resource, an alias, a wildcard, a json path or an aggregate is a shape this does
            # not model. Skipped and counted - the same rule as a spread on the write side.
            if any(ch in sel for ch in "(*:->"):
                skipped += 1
                continue
            names = [c.strip() for c in sel.split(",") if c.strip()]
            record(m.group(1), "select", names or None, m.start())

    return findings, checked, skipped


def selftest() -> int:
    cols = {"t": {"id", "event", "hive_id"}}
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {GREEN + 'PASS' + RESET if good else RED + 'FAIL' + RESET}  {label}: got {got}, want {want}")

    import tempfile
    def run(js):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "x.js")
        open(p, "w", encoding="utf-8").write(js)
        f, checked, skipped = scan([p], cols)
        return [tuple(x["unknown"]) for x in f], checked, skipped

    chk("a wrong column is caught",
        run("db.from('t').insert({ id: 1, event_type: 'x' })")[0], [("event_type",)])
    chk("the right columns are clean",
        run("db.from('t').insert({ id: 1, event: 'x' })")[0], [])
    # the shape that hid the real one
    chk("an object built above and passed by name is caught",
        run("const row = { id: 1, event_type: 'x' };\ndb.from('t').insert(row)")[0], [("event_type",)])
    # the bug this gate shipped with, pinned: two functions declaring the same name, and the write must be
    # graded against the one nearest ABOVE it. Reading the first in the file invented two findings.
    chk("the nearest preceding declaration wins, not the first in the file",
        run("function a(){ const payload = { nope: 1 }; db.from('other').insert(payload); }\n"
            "function b(){ const payload = { id: 1, event: 'x' }; db.from('t').insert(payload); }")[0], [])
    chk("and it still catches a genuine one in the second function",
        run("function a(){ const payload = { id: 1 }; }\n"
            "function b(){ const payload = { id: 1, event_type: 'x' }; db.from('t').insert(payload); }")[0],
        [("event_type",)])
    chk("update and upsert are read too",
        run("db.from('t').update({ nope: 1 });db.from('t').upsert({ alsonope: 2 })")[0],
        [("nope",), ("alsonope",)])
    # what it must NOT do
    # the read side, which fails the whole query rather than one column
    chk("a select naming a missing column is caught",
        run("db.from('t').select('id, reorder_point')")[0], [("reorder_point",)])
    chk("a select of real columns is clean", run("db.from('t').select('id, event')")[0], [])
    chk("an embedded resource is skipped, not guessed",
        run("db.from('t').select('id, other(name)')")[1:], (0, 1))
    chk("a wildcard select is skipped", run("db.from('t').select('*')")[1:], (0, 1))
    chk("a spread is skipped, not guessed", run("db.from('t').insert({ ...base, id: 1 })")[1:], (0, 1))
    chk("a table with no substrate note is skipped",
        run("db.from('unknown_table').insert({ whatever: 1 })")[1:], (0, 1))
    chk("shorthand is skipped rather than misread", run("db.from('t').insert({ id, event })")[1:], (0, 1))
    print(f"\n  SELFTEST: {GREEN + 'PASS' + RESET if ok else RED + 'FAIL' + RESET}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    print(f"{BOLD}\nDoes every read and write name a column its table has? (static){RESET}")
    print("=" * 60)
    cols = table_columns()
    # ★AND THE MIGRATION PARSE IS DELIBERATELY NOT USED AS A COLUMN AUTHORITY. substrate/table-rls covers
    # TENANT tables only - by design, it is generated for tables carrying hive_id or auth_uid - so 19
    # relations the pages really use (hives, marketplace_reviews, service_vouchers, the platform-admin
    # table) have no note and are skipped. Migrations describe all of them, so filling the gap from
    # `CREATE TABLE` looked obvious. MEASURED FIRST, against the 120 tables both sources describe: the
    # parser misses a real column on 26 of them, 155 columns in all - it does not follow every ALTER shape,
    # and it cannot see a later rename. A source that wrong would MANUFACTURE findings on the very tables
    # it was added to cover, which is the failure this gate exists to prevent. The honest fix is upstream:
    # widen build_substrate.py past tenant tables, which needs the database and is queued. Until then these
    # relations are counted in `skipped`, where the silence is visible.
    unchecked = sorted(t for t in migration_columns() if t not in cols)
    if not cols:
        print(f"  {YELLOW}SKIP{RESET}  no substrate table notes found - cannot tell, so nothing is claimed")
        return 0
    paths = sorted(glob.glob("*.html") + glob.glob("*.js"))
    findings, checked, skipped = scan(paths, cols)
    print(f"  tables known:      {len(cols)}  (substrate, generated from the live database)")
    print(f"  tables NOT known:  {len(unchecked)}  (migrations describe them, the substrate covers tenant "
          f"tables only - every read and write to these is skipped, not passed)")
    print(f"  reads+writes read: {checked}")
    print(f"  skipped:           {skipped}  (spread / shorthand / no substrate note - counted, never guessed)")
    print(f"  findings:          {len(findings)}  (baseline: {BASELINE})")
    if findings:
        print(f"\n{RED}Writes naming a column the table does not have:{RESET}")
        for f in findings:
            print(f"  {f['file']}:{f['line']}  {f['op']} into {f['table']}  ->  {', '.join(f['unknown'])}")
    try:
        with open(REPORT, "w", encoding="utf-8") as fh:
            json.dump({"checked": checked, "skipped": skipped, "findings": findings}, fh, indent=2)
    except OSError:
        pass
    if len(findings) > BASELINE:
        print(f"\n{RED}FAIL - {len(findings)} > baseline {BASELINE}. A refusal resolves rather than "
              f"throws, so these fail silently.{RESET}")
        return 1
    print(f"\n{GREEN}PASS - every read and write this can parse names columns its table has.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
