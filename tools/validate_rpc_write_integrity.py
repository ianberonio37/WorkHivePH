#!/usr/bin/env python3
# DEEPWALK-CELL: * D2
"""
validate_rpc_write_integrity.py  --  LIVE-tier LOCK for two "silent 100%-fatal RPC" classes,
generalized platform-wide from the store_memory_turn + delete_worker_data finds (2026-07-07).

A plpgsql function can look fine yet fail on EVERY call at runtime — and if the caller swallows
the error (best-effort catch), nobody notices for months. Two such classes, found live:

  1. NOT-NULL OMISSION: `INSERT INTO T (cols...)` that omits a column of T which is NOT NULL with
     no default -> not-null violation on every insert. (store_memory_turn omitted
     worker_name/agent_id/kind; delete_worker_data omitted hive_audit_log.hive_id.)
  2. STALE TABLE REFERENCE: `INSERT/UPDATE/DELETE public.T` where T was dropped in a schema
     refactor -> "relation does not exist" on every call. (delete_worker_data still UPDATEd the
     legacy `public.assets`, dropped Phase 5c and replaced by asset_nodes.)

This gate introspects the LIVE local DB (docker exec psql) and FAILS if any public function
trips either class. It is a live-tier check (skip_if_fast) and SKIPS cleanly (exit 0) when the
DB is unreachable, so it never blocks a fast/dev run.

Only PUBLIC-SCHEMA-QUALIFIED write targets are checked for existence (CTEs / plpgsql variables
are never `public.`-qualified) -> near-zero false positives. The NOT-NULL check reads the target
table's real column metadata, so it reflects the current schema exactly.

Usage:  python tools/validate_rpc_write_integrity.py [--json] [--selftest]
Exit 0 = clean or DB unreachable, 1 = violations (or self-test failure).
"""
import re, sys, json, subprocess

DOCKER_DB = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-F", "\t", "-c"]

INSERT_RE = re.compile(r"insert\s+into\s+(?:public\.)?([a-z0-9_]+)\s*\((.*?)\)\s*(?:values|select|on\s+conflict)", re.I | re.S)
# public-qualified write targets (existence-checkable without CTE false positives)
QUAL_WRITE_RE = re.compile(r"\b(?:insert\s+into|update|delete\s+from)\s+public\.([a-z0-9_]+)", re.I)
# strip SQL comments so a `-- ... UPDATE public.assets ...` doc line isn't scanned as a real write
LINE_COMMENT_RE = re.compile(r"--[^\n]*")
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)


def strip_sql_comments(sql):
    return LINE_COMMENT_RE.sub("", BLOCK_COMMENT_RE.sub("", sql))


def psql(sql):
    try:
        r = subprocess.run(DOCKER_DB + [sql], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        if r.returncode != 0:
            return None
        return r.stdout or ""
    except Exception:
        return None


def load_schema():
    """Return (required_cols_by_table, existing_tables) from the live DB, or (None, None) if down.

    A "required" column is NOT NULL with NO way for the DB to fill it itself — so a function's
    INSERT that omits it trips a not-null violation. Columns the DB AUTO-POPULATES are therefore
    EXEMPT and must be excluded, or the gate false-positives:
      - column_default IS NOT NULL  -> has a DEFAULT (now(), gen_random_uuid(), serial, ...)
      - is_identity='YES'           -> GENERATED ALWAYS/BY DEFAULT AS IDENTITY (id bigint identity):
                                        NOT NULL, column_default IS NULL, yet inserting into it ERRORS.
      - is_generated='ALWAYS'       -> GENERATED ... STORED computed column: must not be inserted.
    (This exclusion only removes auto-populated columns; a real app-supplied NOT-NULL column keeps
    is_identity='NO' + is_generated='NEVER', so genuine omissions are still caught.)"""
    rows = psql("""SELECT table_name, column_name FROM information_schema.columns
      WHERE table_schema='public' AND is_nullable='NO' AND column_default IS NULL
        AND is_identity='NO' AND is_generated='NEVER';""")
    if rows is None:
        return None, None
    req = {}
    for ln in rows.strip().splitlines():
        if "\t" not in ln:
            continue
        t, c = ln.split("\t", 1)
        req.setdefault(t.strip(), set()).add(c.strip())
    tbls = psql("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
    existing = {ln.strip() for ln in (tbls or "").splitlines() if ln.strip()}
    return req, existing


def load_functions():
    raw = psql("""SELECT p.proname, pg_get_functiondef(p.oid)
      FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='public' AND p.prokind='f';""")
    if raw is None:
        return None
    funcs, cur, buf = {}, None, []
    for ln in raw.splitlines():
        m = re.match(r"^([a-z0-9_]+)\t(.*)$", ln)
        if m and ("CREATE " in m.group(2)):
            if cur:
                funcs[cur] = "\n".join(buf)
            cur, buf = m.group(1), [m.group(2)]
        else:
            buf.append(ln)
    if cur:
        funcs[cur] = "\n".join(buf)
    return funcs


def analyze(funcs, req, existing):
    viols = []
    for fn, raw_body in funcs.items():
        body = strip_sql_comments(raw_body)
        # class 1: NOT-NULL omission on INSERT
        for m in INSERT_RE.finditer(body):
            tbl = m.group(1).strip().lower()
            cols = {c.strip().lower() for c in m.group(2).replace("\n", " ").split(",")}
            missing = req.get(tbl, set()) - cols
            if missing:
                viols.append({"fn": fn, "class": "notnull-omission", "table": tbl,
                              "detail": f"INSERT omits NOT NULL column(s): {sorted(missing)}"})
        # class 2: stale (public-qualified) write target
        for m in QUAL_WRITE_RE.finditer(body):
            tbl = m.group(1).strip().lower()
            if existing and tbl not in existing:
                viols.append({"fn": fn, "class": "stale-table", "table": tbl,
                              "detail": f"writes public.{tbl} which does not exist (dropped?)"})
    # de-dup
    seen, out = set(), []
    for v in viols:
        k = (v["fn"], v["class"], v["table"], v["detail"])
        if k not in seen:
            seen.add(k); out.append(v)
    return out


def selftest():
    # NOTE: `req` is what load_schema() returns AFTER filtering — it already EXCLUDES DB-auto-populated
    # columns (DEFAULT / identity / generated). So `ops_db_size_history` here lists only db_bytes as
    # required, NOT its `id bigint GENERATED ALWAYS AS IDENTITY` — proving a fn that omits an identity
    # id (snapshot_db_size, the 2026-07-22 false-positive) is correctly NOT flagged.
    req = {"agent_memory": {"worker_name", "agent_id", "kind"}, "hive_audit_log": {"hive_id", "actor", "action"},
           "ops_db_size_history": {"db_bytes"}}
    existing = {"agent_memory", "hive_audit_log", "asset_nodes", "ops_db_size_history"}
    funcs = {
        "good_fn": "CREATE FUNCTION good_fn() AS $$ begin insert into agent_memory (worker_name, agent_id, kind, session_id) values (w,a,k,s); update public.asset_nodes set x=1; end $$;",
        "good_identity_fn": "CREATE FUNCTION good_identity_fn() AS $$ begin insert into public.ops_db_size_history (captured_at, db_bytes) select now(), 1; end $$;",
        "bug_notnull": "CREATE FUNCTION bug_notnull() AS $$ begin insert into hive_audit_log (action, actor, target_name) values ('e','system',n); end $$;",
        "bug_stale": "CREATE FUNCTION bug_stale() AS $$ begin update public.assets set worker_name=a where worker_name=p; end $$;",
    }
    v = analyze(funcs, req, existing)
    got = {(x["fn"], x["class"]) for x in v}
    expect = {("bug_notnull", "notnull-omission"), ("bug_stale", "stale-table")}
    ok = got == expect
    print("  selftest", "PASS" if ok else "FAIL", "->", "detected:", sorted(got))
    if not ok:
        print("    expected:", sorted(expect))
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        rc = selftest()
        print("rpc-write-integrity selftest:", "OK" if rc == 0 else "FAILED")
        return rc
    as_json = "--json" in sys.argv
    req, existing = load_schema()
    funcs = load_functions()
    if req is None or funcs is None:
        msg = "local DB unreachable (docker supabase_db_workhive) — live check skipped"
        print(json.dumps({"skipped": True, "note": msg}) if as_json else "  SKIP: " + msg)
        return 0
    viols = analyze(funcs, req, existing)
    if as_json:
        print(json.dumps({"functions": len(funcs), "violations": viols, "count": len(viols)}, indent=2))
    else:
        print(f"rpc-write-integrity (every function's INSERT covers NOT NULL cols + writes existing tables) [{len(funcs)} fns]")
        if not viols:
            print(f"  PASS: no NOT-NULL-omission or stale-table write across {len(funcs)} public functions")
        else:
            print(f"  FAIL: {len(viols)} function write-integrity violation(s):")
            for v in viols:
                print(f"    {v['fn']}  [{v['class']}]  {v['detail']}")
    return 1 if viols else 0


if __name__ == "__main__":
    sys.exit(main())
