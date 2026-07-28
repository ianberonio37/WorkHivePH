#!/usr/bin/env python3
"""
validate_rpc_overloads — no PostgREST-exposed function may have two signatures.

WHY THIS GATE EXISTS (PJ18, 2026-07-28)
---------------------------------------
Migration 20260728000029 fixed generate_project_code, and while editing it I retyped the third
parameter from `integer` to `text`. A different signature is a different function, so CREATE OR
REPLACE created a SECOND overload and left the old, buggy one in place.

The fix was therefore dead code. But the real damage was on the wire: PostgREST resolves an RPC by
NAME, and when two candidates differ only in a parameter it can coerce to either, it refuses both:

    POST /rest/v1/rpc/generate_project_code  {"p_year": 2026}    -> PGRST203
    POST /rest/v1/rpc/generate_project_code  {"p_year": "2026"}  -> PGRST203
    "Could not choose the best candidate function between: ..."

Both callers on project-manager.html run that RPC first and abort on error, so "+ New project" and
"AI: from text" were both dead — and the migration had already gone out to production.

WHY NOTHING ELSE CAUGHT IT
  * psql resolves overloads by the literal's type, so every psql verification passed.
  * The migration applied cleanly — creating an overload is legal SQL, not an error.
  * Static gates read the migration text, where CREATE OR REPLACE looks like a replacement.
  * The page's own gates never called the RPC.
It surfaced only because the SECURITY DEFINER membership gate complained about the function and I
went to read its grants — and saw two rows where there should have been one.

WHAT THIS CHECKS. Every function in `public` that is EXECUTE-granted to `anon` or `authenticated`
is reachable over PostgREST. If any such name has more than one signature, that name is either
already returning PGRST203 or one signature is unreachable dead code. Both are defects.

Overloads that are NOT granted to a browser role are ignored — those are internal, resolved by SQL,
and overloading them is legitimate.

EXTENSION-OWNED FUNCTIONS ARE EXCLUDED. pgvector installs a dozen deliberately overloaded names
(l2_distance, cosine_distance, subvector, ...) that dispatch on vector/halfvec/sparsevec. That is
type-based dispatch inside SQL, it is the extension's design, and we neither own it nor call it over
PostgREST. Including them would bury our own overloads under twelve permanent failures — the shape
of a gate nobody can act on. Ownership comes from pg_depend, so this stays correct as extensions
are added or upgraded rather than being a hand-maintained ignore list.

Needs the local database. Skips cleanly (0) when it cannot connect, like the other live gates.
"""
import io
import json
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

CONTAINER = "supabase_db_workhive"

# One row per (name, arity-group): every public function exposed to a browser role.
SQL = r"""
SELECT coalesce(json_agg(row_to_json(t)), '[]'::json)::text FROM (
  SELECT p.proname AS name,
         pg_get_function_identity_arguments(p.oid) AS args,
         p.prosecdef AS secdef
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'public'
     AND p.prokind = 'f'
     AND (has_function_privilege('authenticated', p.oid, 'EXECUTE')
          OR has_function_privilege('anon', p.oid, 'EXECUTE'))
     -- Not owned by an installed extension. pgvector's l2_distance/cosine_distance/subvector
     -- family is overloaded BY DESIGN on vector/halfvec/sparsevec; that is the extension's
     -- dispatch, not our drift, and we do not call it over PostgREST.
     AND NOT EXISTS (
       SELECT 1 FROM pg_depend d
        WHERE d.objid = p.oid AND d.classid = 'pg_proc'::regclass AND d.deptype = 'e')
   ORDER BY p.proname, args
) t;
"""


def fetch():
    try:
        out = subprocess.run(
            ["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c", SQL],
            capture_output=True, text=True, timeout=90)
    except Exception as exc:
        return None, str(exc)
    if out.returncode != 0:
        return None, (out.stderr or "psql failed").strip()[:200]
    try:
        return json.loads(out.stdout.strip() or "[]"), None
    except Exception as exc:
        return None, "unparseable psql output: %s" % exc


def main():
    rows, err = fetch()
    if rows is None:
        print("  SKIP — local database not reachable (%s)." % err)
        return 0

    by_name = {}
    for r in rows:
        by_name.setdefault(r["name"], []).append(r)

    dupes = {n: sigs for n, sigs in by_name.items() if len(sigs) > 1}

    if dupes:
        print("  FAIL — %d PostgREST-exposed function name(s) have more than one signature:\n"
              % len(dupes))
        for name in sorted(dupes):
            print("    %s" % name)
            for s in dupes[name]:
                print("      (%s)%s" % (s["args"], "  SECURITY DEFINER" if s["secdef"] else ""))
            print()
        print("  PostgREST resolves an RPC by NAME. With two candidates it cannot choose between,")
        print("  it rejects the call with PGRST203 — so the endpoint is DOWN, not merely ambiguous.")
        print("  This is almost always a CREATE OR REPLACE whose parameter types drifted from the")
        print("  original: a changed type makes a NEW function instead of replacing the old one.")
        print("  Fix by DROPping the signature nothing calls, then re-creating on the one the")
        print("  client actually sends.")
        return 1

    print("  PASS — all %d PostgREST-exposed functions have exactly one signature." % len(by_name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
