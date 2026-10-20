#!/usr/bin/env python3
"""prove_rewrite_equivalence.py - a policy, view or function rewritten for SPEED must leave every reader's rows as they were.

SL LB2 (2026-10-20) rewrites RLS policies, views and functions so their reads ride an index as the tables grow. A rewrite
like that is only a speed change if nobody can see one row more or one row fewer afterwards. This proves it the only way
that counts - by asking, as every reader:

  one transaction, rolled back at the end (nothing is kept):
    1. optional --setup SQL seeds the edge rows the rewrite could treat differently (a soft-deleted parent, a NULL key,
       a member who was removed ...) - so the proof is not limited to the shapes the local data happens to hold;
    2. as EVERY account in auth.users, plus anon and a signed-in stranger who owns nothing, each --probe is fingerprinted:
       its row count and an md5 over the sorted md5 of every row;
    3. the rewrite SQL (--sql, a migration file) is applied;
    4. every fingerprint is taken again.
  equivalent  = every (reader, probe) fingerprint is unchanged;
  not vacuous = for each probe at least two readers get different non-empty answers (a blanket deny, before and after,
                would otherwise "prove" anything) - a probe that fails this is reported NOT PROVEN, never passed.

    python tools/prove_rewrite_equivalence.py --sql supabase/migrations/X.sql --probe "select * from public.pm_scope_items" \
        [--probe "..."] [--setup edges.sql] [--allow-uniform PROBE_INDEX]

Exit 0 = equivalent and proven; 1 = a reader's answer changed or a probe is not proven; 2 = could not run.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CONTAINER = "supabase_db_workhive"
STRANGER = "00000000-0000-4000-8000-00000000dead"


def psql(script: str, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-X", "-q"],
                          input=script, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=dict(os.environ, MSYS_NO_PATHCONV="1"), timeout=timeout)


def readers() -> list[tuple[str, str]]:
    r = psql("\\pset format unaligned\n\\pset tuples_only on\nselect id::text from auth.users order by id;\n", timeout=60)
    if r.returncode != 0:
        raise SystemExit(f"could not list readers: {r.stderr.strip()[:300]}")
    uids = [ln.strip() for ln in r.stdout.splitlines() if re.fullmatch(r"[0-9a-f-]{36}", ln.strip())]
    return [("anon", "")] + [("authenticated", STRANGER)] + [("authenticated", u) for u in uids]


def claims(role: str, uid: str) -> str:
    return json.dumps({"role": "anon"} if role == "anon" else {"sub": uid, "role": "authenticated", "aud": "authenticated"})


def closure_block(tag: str, probes: list[str]) -> list[str]:
    """As postgres, for every probe: the functions it can reach - named in it, used by the views it reads (recursively),
    by the policies of every table under them, and named in the body of an INVOKER function it calls. Stored in psql
    variables fn<tag>_<i>, in lower case: an unquoted SQL alias is folded and gset names the variable after it (the
    first version wrote fnB_0, set fnb_0, and every reader read "no EXECUTE"). Asked again after the rewrite: a rewrite
    may add a function (a new set, a new helper)."""
    out = []
    for pi, p in enumerate(probes):
        words = sorted(set(re.findall(r"\b([a-z_][a-z0-9_]*)\b", p.lower())))
        calls = sorted(set(re.findall(r"\b([a-z_][a-z0-9_]*)\s*\(", p.lower())))
        arr = lambda xs: "ARRAY[%s]::text[]" % ",".join("'%s'" % x for x in xs) if xs else "ARRAY[]::text[]"
        out.append(f"""WITH RECURSIVE direct(f) AS (
    SELECT p.oid FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace AND p.proname = ANY({arr(calls)})
), rels(oid) AS (
    SELECT c.oid FROM pg_class c WHERE c.relnamespace = 'public'::regnamespace AND c.relname = ANY({arr(words)})
  UNION
    SELECT c.oid FROM direct d JOIN pg_proc p ON p.oid = d.f AND NOT p.prosecdef
      CROSS JOIN LATERAL regexp_matches(lower(p.prosrc), '([a-z_][a-z0-9_]*)', 'g') m(w)
      JOIN pg_class c ON c.relnamespace = 'public'::regnamespace AND c.relname = m.w[1]
  UNION
    SELECT d.refobjid FROM rels JOIN pg_rewrite r ON r.ev_class = rels.oid
      JOIN pg_depend d ON d.classid = 'pg_rewrite'::regclass AND d.objid = r.oid AND d.refclassid = 'pg_class'::regclass
     WHERE d.refobjid <> rels.oid
), fns(f) AS (
    SELECT f FROM direct
  UNION
    SELECT p2.oid FROM direct d JOIN pg_proc p ON p.oid = d.f AND NOT p.prosecdef
      CROSS JOIN LATERAL regexp_matches(lower(p.prosrc), '([a-z_][a-z0-9_]*)\\s*\\(', 'g') m(w)
      JOIN pg_proc p2 ON p2.pronamespace = 'public'::regnamespace AND p2.proname = m.w[1]
  UNION
    SELECT d.refobjid FROM rels JOIN pg_rewrite r ON r.ev_class = rels.oid
      JOIN pg_depend d ON d.classid = 'pg_rewrite'::regclass AND d.objid = r.oid AND d.refclassid = 'pg_proc'::regclass
  UNION
    SELECT d.refobjid FROM rels JOIN pg_policy po ON po.polrelid = rels.oid
      JOIN pg_depend d ON d.classid = 'pg_policy'::regclass AND d.objid = po.oid AND d.refclassid = 'pg_proc'::regclass
)
SELECT coalesce(string_agg(DISTINCT f::text, ','), '') AS fn{tag.lower()}_{pi} FROM fns \\gset""")
    return out


def fingerprint_block(tag: str, rd: list, probes: list[str]) -> list[str]:
    # a reader who is REFUSED (permission denied, say) has an answer too: the refusal's SQLSTATE is its fingerprint, and it
    # must be the same refusal afterwards. Only the probes may fail and go on; setup and rewrite stop the proof on error.
    # A FUNCTION the reader may not EXECUTE is never called: from this harness (superuser psql that SET ROLEs down) that
    # denial segfaults PostgreSQL 17.6 and takes the whole local stack into recovery (the real path, PostgREST as
    # authenticator, refuses cleanly - memory feedback_my_probe_crashed_the_db_not_the_product). The catalogue answers
    # instead, and such a reader is recorded "not asked: no EXECUTE" - before and after alike.
    out = ["\\set ON_ERROR_STOP 0", "\\set ON_ERROR_ROLLBACK on"]
    for ri, (role, uid) in enumerate(rd):
        oks = ", ".join(f"coalesce((SELECT bool_and(has_function_privilege('{role}', f::oid, 'EXECUTE')) "
                        f"FROM unnest(string_to_array(:'fn{tag.lower()}_{pi}', ',')) f WHERE f <> ''), true) AS ok_{pi}" for pi in range(len(probes)))
        out.append(f"SELECT {oks} \\gset")
        out.append(f"SET LOCAL ROLE {role};")
        out.append("SET LOCAL request.jwt.claims = '%s';" % claims(role, uid).replace("'", "''"))
        for pi, p in enumerate(probes):
            out.append(f"\\if :ok_{pi}")
            out.append(f"SELECT '@@{tag}|{ri}|{pi}|' || count(*) || '|' || coalesce(md5(string_agg(h, ',' ORDER BY h)), '-') "
                       f"FROM (SELECT md5(t::text) AS h FROM ({p}) t) x;")
            out.append(f"\\if :ERROR \\echo '@@{tag}|{ri}|{pi}|ERR|' :LAST_ERROR_SQLSTATE \\endif")
            out.append("\\else")
            out.append(f"\\echo '@@{tag}|{ri}|{pi}|ERR|' NOEXEC")
            out.append("\\endif")
        out.append("RESET ROLE;")
    out += ["\\set ON_ERROR_ROLLBACK off", "\\set ON_ERROR_STOP 1"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sql", required=True, help="the rewrite (a migration file)")
    ap.add_argument("--probe", action="append", default=[], help="a SELECT whose rows every reader must keep")
    ap.add_argument("--probes-file", help="one probe SELECT per line (for a sweep over many tables)")
    ap.add_argument("--setup", help="SQL run first (as postgres) to seed edge rows; rolled back with everything else")
    ap.add_argument("--allow-uniform", action="append", type=int, default=[],
                    help="probe index allowed to give every reader the same answer (a public read), stated on purpose")
    a = ap.parse_args()
    if a.probes_file:
        a.probe += [ln.strip() for ln in Path(a.probes_file).read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("--")]
    if not a.probe:
        ap.error("no probe given (--probe or --probes-file)")

    rewrite =(ROOT / a.sql).read_text(encoding="utf-8") if not Path(a.sql).is_absolute() else Path(a.sql).read_text(encoding="utf-8")
    if re.search(r"^\s*(commit|rollback|begin)\s*;", rewrite, re.I | re.M):
        print("the rewrite carries its own transaction control - refuse (it would end the proof's transaction)")
        return 2
    setup = Path(a.setup).read_text(encoding="utf-8") if a.setup else ""
    rd = readers()
    lines = ["\\set ON_ERROR_STOP 1", "\\pset format unaligned", "\\pset tuples_only on", "BEGIN;",
             "SET LOCAL statement_timeout = '120s';", "SET LOCAL lock_timeout = '10s';"]
    if setup:
        lines += ["\\echo '@@SETUP'", setup]
    lines += closure_block("B", a.probe) + fingerprint_block("B", rd, a.probe)
    lines += ["\\echo '@@REWRITE'", rewrite]
    lines += closure_block("A", a.probe) + fingerprint_block("A", rd, a.probe)
    lines += ["ROLLBACK;"]
    r = psql("\n".join(lines) + "\n")
    if r.returncode != 0 or "@@REWRITE" not in r.stdout:
        print("the proof did not run to the end (nothing was kept):", (r.stderr or "").strip()[:800])
        return 2

    fp = {}
    for ln in r.stdout.splitlines():
        m = re.match(r"@@([AB])\|(\d+)\|(\d+)\|(\d+)\|(\S+)$", ln.strip())
        if m:
            fp[(m.group(1), int(m.group(2)), int(m.group(3)))] = (int(m.group(4)), m.group(5))
            continue
        m = re.match(r"@@([AB])\|(\d+)\|(\d+)\|ERR\|\s*(\w+)$", ln.strip())
        if m:
            fp[(m.group(1), int(m.group(2)), int(m.group(3)))] = (-1, "refused " + m.group(4))
    bad = 0
    for pi, p in enumerate(a.probe):
        before = {ri: fp.get(("B", ri, pi)) for ri in range(len(rd))}
        after = {ri: fp.get(("A", ri, pi)) for ri in range(len(rd))}
        missing = [ri for ri in range(len(rd)) if before[ri] is None or after[ri] is None]
        changed = [ri for ri in range(len(rd)) if before[ri] != after[ri]]
        nonempty = {before[ri] for ri in range(len(rd)) if before[ri] and before[ri][0] > 0}
        proven = len(nonempty) >= 2 or pi in a.allow_uniform
        seen = sum(1 for ri in range(len(rd)) if before[ri] and before[ri][0] > 0)
        verdict = "EQUIVALENT" if not changed and not missing and proven else ("CHANGED" if changed else "NOT PROVEN")
        if verdict != "EQUIVALENT":
            bad += 1
        rows = sorted({before[ri][0] for ri in range(len(rd)) if before[ri] and before[ri][0] >= 0})
        refused = sorted({before[ri][1].replace("refused NOEXEC", "not asked: no EXECUTE") for ri in range(len(rd))
                          if before[ri] and before[ri][0] < 0})
        print(f"[{verdict}] probe {pi}: {p[:110]}")
        print(f"    {len(rd)} readers (anon, a stranger, {len(rd) - 2} accounts): {seen} see rows, {len(nonempty)} distinct "
              f"non-empty answers, row counts {rows[:8]}{' ...' if len(rows) > 8 else ''}"
              + (f"; {sum(1 for ri in range(len(rd)) if before[ri] and before[ri][0] < 0)} refused ({', '.join(refused)})" if refused else ""))
        for ri in changed[:12]:
            role, uid = rd[ri]
            print(f"    CHANGED {role} {uid or '-'}: before {before[ri]} after {after[ri]}")
        if missing:
            print(f"    {len(missing)} reader(s) returned no fingerprint")
    print(f"{'EQUIVALENT' if not bad else 'NOT EQUIVALENT'}: {len(a.probe) - bad}/{len(a.probe)} probes - {a.sql}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
