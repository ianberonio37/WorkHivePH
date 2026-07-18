#!/usr/bin/env python3
# DEEPWALK-CELL: agent-memory-store D26
"""
validate_agent_memory_persist_complete.py  --  LOCK for the "RPC insert omits a NOT NULL /
CHECK-required column -> 100% silent runtime failure" class.

Bug (found live 2026-07-07, deep-walk dim-4/dim-13): the `store_memory_turn` RPC — the client
companion's session-scoped memory writer (voice-handler.js `_storeTurn`) — INSERTed into
`agent_memory` while OMITTING three columns that are NOT NULL with no default (`worker_name`,
`agent_id`, `kind`). So every companion turn's session-memory write threw a not-null violation,
which the client swallows (console.warn). The "highest fidelity" session layer that
`_fetchRecentMemory` reads (by session_id) was 100% dead; recall silently ran on the
voice_journal fallback + the gateway saveTurn path. It also violated the
`agent_memory_kind_check` CHECK once the NOT NULL cols were added. Root cause: an agent_memory
schema refactor added the required columns but this legacy RPC was never updated.

Fixed by migration 20260707000005 (derive worker_name from hive_members, set agent_id constant,
set kind='session_turn' + extend the kind CHECK to allow it). This gate locks the invariant so a
future CREATE OR REPLACE can't silently drop a required column again.

Contract enforced: the LATEST `CREATE ... FUNCTION store_memory_turn` across supabase/migrations
must, in its INSERT INTO agent_memory, name every REQUIRED column and set `kind` to a CHECK-allowed
literal. FAIL = a required column missing from the insert column-list, or a non-allowed kind literal.

Usage:  python tools/validate_agent_memory_persist_complete.py [--json] [--selftest]
Exit 0 = clean, 1 = violations (or self-test failure).
"""
import re, sys, pathlib, json

ROOT = pathlib.Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "supabase" / "migrations"

# agent_memory columns that are NOT NULL with NO default -> any INSERT must name them.
# (Kept as an explicit contract; update if the agent_memory schema's NOT NULL set changes.)
REQUIRED_COLS = ["worker_name", "agent_id", "kind"]
# Values the agent_memory_kind_check CHECK allows.
ALLOWED_KINDS = ["turn", "summary", "session_turn"]

# Capture the WHOLE function incl. its body: from CREATE ... store_memory_turn through the
# CLOSING $function$ delimiter (the body sits between the opening and closing $function$).
FUNC_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:public\.)?store_memory_turn\b.*?\$function\$.*?\$function\$",
    re.IGNORECASE | re.DOTALL,
)
# The INSERT INTO agent_memory ( <col-list> ) block.
INSERT_RE = re.compile(
    r"insert\s+into\s+(?:public\.)?agent_memory\s*\((.*?)\)\s*values",
    re.IGNORECASE | re.DOTALL,
)
# `kind` set to a quoted literal anywhere in the function body: kind ... 'literal' OR a bare
# 'literal' in the VALUES aligned to kind. We check the set of quoted literals present.
QUOTED_RE = re.compile(r"'([a-z_]+)'")


def latest_store_memory_turn_def():
    """Return (path, body) of the store_memory_turn definition in the LAST migration that defines it."""
    hit = None
    for p in sorted(MIGRATIONS.glob("*.sql")):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for m in FUNC_RE.finditer(txt):
            hit = (p.name, m.group(0))
    return hit


def analyze(func_text):
    """Return list of violation strings for a store_memory_turn function definition text."""
    viols = []
    im = INSERT_RE.search(func_text)
    if not im:
        return ["no INSERT INTO agent_memory found in store_memory_turn (cannot verify column coverage)"]
    col_list = im.group(1)
    cols = {c.strip().lower() for c in col_list.replace("\n", " ").split(",")}
    for req in REQUIRED_COLS:
        if req not in cols:
            viols.append(f"INSERT INTO agent_memory omits NOT NULL column '{req}' -> the RPC will fail at runtime")
    # kind must be set to a CHECK-allowed literal somewhere in the body.
    if "kind" in cols:
        literals = set(QUOTED_RE.findall(func_text))
        if not (literals & set(ALLOWED_KINDS)):
            viols.append(
                f"'kind' is inserted but no CHECK-allowed literal {ALLOWED_KINDS} appears in the body "
                f"-> violates agent_memory_kind_check"
            )
    return viols


def selftest():
    ok_fix = (
        "CREATE OR REPLACE FUNCTION public.store_memory_turn(p_hive_id uuid) RETURNS json AS $function$\n"
        "begin\n"
        "  insert into agent_memory (hive_id, worker_name, auth_uid, agent_id, kind, session_id, user_input)\n"
        "  values (p_hive_id, coalesce(v_worker_name,'system'), auth.uid(), 'voice-companion', 'session_turn', s, u);\n"
        "end; $function$"
    )
    bug_missing = (   # the real pre-fix bug: omits worker_name, agent_id, kind
        "CREATE OR REPLACE FUNCTION public.store_memory_turn(p_hive_id uuid) RETURNS json AS $function$\n"
        "begin\n"
        "  insert into agent_memory (hive_id, worker_id, session_id, turn_num, user_input, user_input_hash)\n"
        "  values (p_hive_id, auth.uid(), s, n, u, h);\n"
        "end; $function$"
    )
    bug_badkind = (   # names kind but with a non-allowed literal
        "CREATE OR REPLACE FUNCTION public.store_memory_turn(p_hive_id uuid) RETURNS json AS $function$\n"
        "begin\n"
        "  insert into agent_memory (hive_id, worker_name, agent_id, kind, session_id, user_input)\n"
        "  values (p_hive_id, w, 'voice-companion', 'chatlog', s, u);\n"
        "end; $function$"
    )
    cases = [
        ("schema-complete fix", ok_fix, False),
        ("omits worker_name/agent_id/kind (the bug)", bug_missing, True),
        ("kind literal not CHECK-allowed", bug_badkind, True),
    ]
    ok = True
    for name, text, expect in cases:
        got = bool(analyze(text))
        status = "PASS" if got == expect else "FAIL"
        if got != expect:
            ok = False
        print(f"  selftest {status}: {name}  (expected violation={expect}, got={got})")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        rc = selftest()
        print("agent_memory persist-complete selftest:", "OK" if rc == 0 else "FAILED")
        return rc
    as_json = "--json" in sys.argv
    hit = latest_store_memory_turn_def()
    if not hit:
        msg = "store_memory_turn not found in supabase/migrations (nothing to verify)"
        print(json.dumps({"violations": [], "note": msg}) if as_json else "  SKIP: " + msg)
        return 0
    fname, body = hit
    viols = analyze(body)
    if as_json:
        print(json.dumps({"file": fname, "violations": viols, "count": len(viols)}, indent=2))
    else:
        print(f"agent_memory persist-complete (store_memory_turn INSERT covers NOT NULL + CHECK cols) [{fname}]")
        if not viols:
            print(f"  PASS: store_memory_turn INSERT names all required cols {REQUIRED_COLS} + a valid kind")
        else:
            print(f"  FAIL: {len(viols)} issue(s) in store_memory_turn:")
            for v in viols:
                print(f"    {v}")
    return 1 if viols else 0


if __name__ == "__main__":
    sys.exit(main())
