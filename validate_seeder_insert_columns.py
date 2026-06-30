"""
Seeder Insert-Column Validator -- WorkHive Platform Guardian (forward-only ratchet)
===================================================================================
Catches the bug class found 2026-06-09 (live MCP gate drive): a seeder INSERTs a
column that does not exist on the target table. `seeders/sensor_readings.py` kept
inserting 'sensor_type' after it was dropped (20260520000008) -> every insert
400'd (PGRST204) -> sensor_readings seeded 0 rows SILENTLY, starving
predictive/analytics for ~3 weeks. The existing schema-coverage validator checks
`db.from().select()` columns but NOT seeder INSERT payloads -- that gap let it ship.

For each `batch_insert(client, "<table>", <rows>)` and inline
`.table("t").insert({...})` / `.from("t").insert({...})` in
test-data-seeder/seeders/*.py, it verifies every TOP-LEVEL string-literal payload
key is a real column of <table>. Source of truth = the LIVE DB
(information_schema), NOT migrations -- build_schema() has known parse gaps that
caused false positives. Degrades to SKIP (pass) if the DB is unreachable.

FORWARD-ONLY RATCHET (Mega Gate Rule B): there is an existing backlog of
seeders inserting non-existent columns (mostly dead/optional CMMS seeders).
This gate FAILs only when the mismatch count rises ABOVE the frozen baseline --
i.e. a NEW sensor_type-class regression. The baseline auto-tightens as the
backlog is paid down. Dispose the backlog by fixing each seeder, then the
baseline drops automatically.

Baseline: seeder_insert_columns_baseline.json   Output: seeder_insert_columns_report.json
Sentinel binding: name the L2 test 'test('seeder_insert_columns: ...')'.
"""
import re, json, sys, os, glob, subprocess
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

from validator_utils import format_result  # noqa: E402

ROOT = Path(__file__).resolve().parent
SEEDERS_DIR = ROOT / "test-data-seeder" / "seeders"
BASELINE = ROOT / "seeder_insert_columns_baseline.json"
DB_CONTAINER = "supabase_db_workhive"

CHECK_NAMES = ["seeder_inserts_real_columns"]
CHECK_LABELS = {
    "seeder_inserts_real_columns":
        "L1  No NEW seeder INSERT writes a column absent from the live table (forward-only; catches dropped-column-still-seeded)",
}

RE_BATCH = re.compile(r'batch_insert\(\s*\w+\s*,\s*["\']([a-z_][a-z0-9_]*)["\']\s*,\s*([A-Za-z_]\w*)', re.I)
RE_INLINE = re.compile(r'\.(?:table|from)\(\s*["\']([a-z_][a-z0-9_]*)["\']\s*\)\s*\.insert\(', re.I)
NON_COLUMN_KEYS = {"_offline", "_pending_edit", "returning", "count", "on_conflict"}


def live_schema():
    """{table: set(columns)} from the live DB, or None if unreachable."""
    try:
        r = subprocess.run(
            ["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tAc",
             "select table_name||'|'||column_name from information_schema.columns where table_schema='public';"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
    except Exception:
        return None
    schema = {}
    for line in r.stdout.splitlines():
        if "|" in line:
            t, c = line.split("|", 1)
            schema.setdefault(t.strip(), set()).add(c.strip())
    return schema or None


def _payload_keys(src, start_idx):
    """Top-level (depth-1) string keys of the first {...} dict at/after start_idx.
    String- and depth-aware: ignores nested JSONB dict keys and f-string braces."""
    i = src.find("{", start_idx)
    if i < 0:
        return set()
    depth, instr, cur, keys, k, n = 0, None, None, set(), i, len(src)
    while k < n:
        c = src[k]
        if instr:
            if c == "\\":
                k += 2; continue
            if c == instr:
                instr = None
            elif cur is not None:
                cur += c
            k += 1; continue
        if c in ('"', "'"):
            instr = c
            cur = "" if depth == 1 else None
            k += 1; continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        elif c == ":" and depth == 1 and cur is not None:
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", cur):
                keys.add(cur)
            cur = None
        elif c not in (" ", "\t", "\n", "\r"):
            cur = None
        k += 1
    return keys


def find_mismatches(schema):
    mismatches = []
    for path in sorted(glob.glob(str(SEEDERS_DIR / "*.py"))):
        try:
            src = open(path, encoding="utf-8").read()
        except Exception:
            continue
        fname = os.path.basename(path)

        def check(table, keys):
            cols = schema.get(table)
            if cols is None:           # table not in live DB -> separate concern; skip
                return
            for kk in keys:
                if kk in NON_COLUMN_KEYS:
                    continue
                if kk not in cols:
                    mismatches.append(f"{fname}:{table}.{kk}")

        for m in RE_BATCH.finditer(src):
            table, listvar = m.group(1), m.group(2)
            for am in re.finditer(re.escape(listvar) + r'\.append\(', src):
                check(table, _payload_keys(src, am.end()))
        for m in RE_INLINE.finditer(src):
            check(m.group(1), _payload_keys(src, m.end()))
    return sorted(set(mismatches))


def main():
    print("Seeder Insert-Column Validator (forward-only ratchet)")
    print("=====================================================")
    schema = live_schema()
    if schema is None:
        print("  live DB unreachable -> SKIP (DB-dependent validator; no false alarms offline)")
        n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS,
                                               [{"check": "seeder_inserts_real_columns", "skip": True}])
        json.dump({"skipped": True}, open("seeder_insert_columns_report.json", "w"))
        sys.exit(0)

    mismatches = find_mismatches(schema)
    cur = len(mismatches)
    base = None
    if BASELINE.exists():
        try:
            base = json.load(open(BASELINE, encoding="utf-8")).get("count")
        except Exception:
            base = None

    issues = []
    if base is None:
        json.dump({"count": cur, "mismatches": mismatches}, open(BASELINE, "w", encoding="utf-8"), indent=2)
        print(f"  baseline SEEDED at {cur} pre-existing mismatch(es) (dispose to tighten). First run PASS.")
    elif cur > base:
        new = [m for m in mismatches]
        issues.append({"check": "seeder_inserts_real_columns",
                       "reason": f"NEW seeder->dropped-column insert(s): count rose {base} -> {cur}. "
                                 f"A seeder now writes a column absent from the live table (will 400 -> 0 rows "
                                 f"silently). Offenders: {', '.join(new)}"})
    elif cur < base:
        json.dump({"count": cur, "mismatches": mismatches}, open(BASELINE, "w", encoding="utf-8"), indent=2)
        print(f"  backlog fell {base} -> {cur}; baseline auto-tightened (Rule B).")
    else:
        print(f"  at baseline ({cur} known pre-existing mismatch(es)).")

    if mismatches:
        print(f"  current backlog ({cur}): {', '.join(mismatches[:12])}{' ...' if cur > 12 else ''}")
    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    print(f"\nSeeder insert-columns: {n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP")
    json.dump({"count": cur, "baseline": base, "mismatches": mismatches, "n_fail": n_fail},
              open("seeder_insert_columns_report.json", "w", encoding="utf-8"), indent=2)
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
