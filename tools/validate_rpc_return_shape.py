#!/usr/bin/env python3
"""validate_rpc_return_shape.py — Arc G G3 (U/F): every app RPC has an introspectable return shape.

THE CONSUMER CONTRACT: a PostgREST/RPC caller relies on the function's declared return type to know what
columns/fields come back. A function that `RETURNS record` (or `RETURNS SETOF record`) WITHOUT OUT/TABLE
parameters is OPAQUE — PostgREST cannot expose its columns and the caller must blindly `AS (col type, ...)`
cast at every call site, so any column rename/reorder silently breaks consumers with no contract to check
against. That is the U (consumer-contract) / F (correctness) failure this gate forbids.

RULE: no public, user-defined (non-extension), non-trigger function may return bare `record`/`SETOF record`
without OUT or TABLE() parameters. Well-defined shapes — scalar, named composite type, `RETURNS TABLE(...)`,
OUT params, or `json`/`jsonb` (opaque-BY-CHOICE: the JSON schema is the documented contract) — all pass.
Baseline 0 opaque. The json/jsonb count is reported as a tracked (soft) category, not a failure.

Live introspection via `docker exec supabase_db_workhive psql`. Hermetic to the local DB.

USAGE:      python tools/validate_rpc_return_shape.py
Self-test:  python tools/validate_rpc_return_shape.py --self-test   (proves the teeth)
"""
from __future__ import annotations
import json
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

DB = "supabase_db_workhive"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"


def psql_json(sql: str):
    try:
        p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if p.returncode != 0:
            return None
        out = p.stdout.strip()
        return json.loads(out) if out else []
    except Exception:
        return None


def gather():
    # app RPCs = public schema · non-trigger · NOT an extension member (excludes pgvector/pg_trgm internals)
    return psql_json("""
      SELECT coalesce(json_agg(json_build_object(
        'name', p.proname,
        'rettype', p.prorettype::regtype::text,
        'setof', p.proretset,
        'is_record', (p.prorettype = 'record'::regtype),
        'has_out', EXISTS (SELECT 1 FROM unnest(coalesce(p.proargmodes,'{}')) m WHERE m IN ('o','b','t')),
        'is_json', (p.prorettype IN ('json'::regtype,'jsonb'::regtype))
      )), '[]'::json)
      FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='public' AND p.prorettype <> 'trigger'::regtype
        AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid=p.oid AND d.deptype='e');""")


def classify(fn) -> str:
    """-> 'opaque' (FAIL) | 'json' (soft/tracked) | 'typed' (pass)."""
    if fn["is_record"] and not fn["has_out"]:
        return "opaque"
    if fn["is_json"]:
        return "json"
    return "typed"


def evaluate(fns):
    opaque, jsonish, typed = [], [], []
    for f in fns:
        c = classify(f)
        (opaque if c == "opaque" else jsonish if c == "json" else typed).append(f["name"])
    return opaque, jsonish, typed


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    fns = gather()
    if fns is None:
        print(f"  {RED}ERROR{RST}: could not introspect (is {DB} running?)")
        return 1
    opaque, jsonish, typed = evaluate(fns)

    print("=" * 74)
    print("  Arc G G3 (U/F) — RPC return-shape contract (no opaque record returns)")
    print("=" * 74)
    print(f"  {len(fns)} app RPCs · {len(typed)} strictly-typed · {len(jsonish)} json/jsonb (opaque-by-choice) · {len(opaque)} opaque-record")

    if self_test:
        synth = [{"name": "__synthetic_opaque__", "rettype": "record", "setof": True,
                  "is_record": True, "has_out": False, "is_json": False}]
        o2, *_ = evaluate(synth)
        ok = "__synthetic_opaque__" in o2
        print(f"  TEETH [{GREEN+'PASS'+RST if ok else RED+'FAIL'+RST}] a RETURNS (SETOF) record fn with no OUT params is caught")
        if not ok:
            return 1

    print()
    if opaque:
        for n in opaque:
            print(f"  {RED}FAIL{RST}  {n} returns bare record/SETOF record with no OUT/TABLE params — opaque to consumers")
        print(f"\n  {RED}{len(opaque)} opaque-record RPC(s){RST} (baseline 0) — consumer-contract break")
        return 1
    print(f"  {GREEN}PASS{RST} — every app RPC has an introspectable return shape (typed or json-by-choice)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
