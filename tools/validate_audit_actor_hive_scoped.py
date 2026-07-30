#!/usr/bin/env python3
"""validate_audit_actor_hive_scoped.py — every audit trigger must resolve its actor IN THE AUDITED ROW'S HIVE.

WHY A STATIC GATE AND NOT A CELL. Seven audit triggers resolve the acting worker with

    SELECT hm.worker_name INTO v_actor FROM public.hive_members hm
     WHERE hm.auth_uid = auth.uid() ...

and two of them (mig 20260730000007) did it WITHOUT constraining the hive. `LIMIT 1` with no `ORDER BY` and no
hive predicate picks an ARBITRARY membership, so a member of two hives could have an amendment in hive A logged
under the worker_name they use in hive B. This platform has been bitten by the same shape before
([[feedback_resolving_live_is_not_enough_be_deterministic]]).

The fix is correct by construction — it constrains something that was unconstrained. It is also, and this is
the point, **not verifiable by an outcome test**: I wrote a behavioural probe that manufactured the missing
state (two hives, deliberately different worker_names for one person, an amendment in hive B) and then restored
the PRE-FIX definition inside the same rolled-back transaction to see it fail. It did not fail. The arbitrary
`LIMIT 1` happened to return the hive-B row anyway, so the probe reported the correct actor in BOTH worlds and
proved nothing. A test that passes against the bug is not evidence, and banking it would have been exactly the
false-green this platform keeps finding.

A non-deterministic failure cannot be reliably reproduced, so it is locked where it IS deterministic: in the
source. This asserts the predicate exists in every actor lookup. Unscope one and this goes red — which is a
falsifiable claim about the property that actually matters.

Usage:  python tools/validate_audit_actor_hive_scoped.py [--selftest]
"""
from __future__ import annotations

import re
import subprocess
import sys

DB = "supabase_db_workhive"
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# The lookup, and the hive constraint in any of the forms the codebase uses. Both orderings and the
# parenthesised `IS NULL OR` allowance count — an earlier version of this check tested only
# `auth_uid = ... AND hm.hive_id` and reported all SEVEN functions unscoped when five were already correct.
# A count taken with the wrong instrument is not a count.
LOOKUP = re.compile(r"INTO\s+v_actor", re.I)
SCOPED = re.compile(r"hm\.hive_id", re.I)


def psql(sql: str):
    try:
        r = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-At", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except Exception:
        return None
    return r.stdout if r.returncode == 0 else None


def audit_functions():
    out = psql("select p.proname from pg_proc p join pg_namespace n on n.oid=p.pronamespace "
               "where n.nspname='public' and p.prorettype='trigger'::regtype "
               "and p.prosrc ~* 'INTO v_actor' order by 1;")
    return [l.strip() for l in (out or "").splitlines() if l.strip()]


def body(fn: str):
    return psql(f"select pg_get_functiondef(oid) from pg_proc where proname='{fn}';") or ""


def check(bodies=None):
    """-> (unscoped, checked). `bodies` lets the self-test inject a regressed source."""
    fns = audit_functions()
    if not fns:
        return None, []
    unscoped = []
    for fn in fns:
        src = (bodies or {}).get(fn) or body(fn)
        if not LOOKUP.search(src):
            continue
        # The predicate must appear in the same statement as the lookup, not merely somewhere in the function:
        # several of these functions ALSO read hive_members elsewhere (for a role check), and accepting that
        # would let an unscoped actor lookup hide behind an unrelated scoped query.
        m = LOOKUP.search(src)
        stmt = src[m.start(): src.find(";", m.start()) + 1]
        if not SCOPED.search(stmt):
            unscoped.append(fn)
    return unscoped, fns


def selftest():
    print("  selftest: an UNSCOPED actor lookup must FAIL the gate")
    unscoped, fns = check()
    if unscoped is None:
        print(f"  {YEL}SKIP{RST} — docker/psql unavailable")
        return 0
    if unscoped:
        print(f"  {RED}FAIL{RST} the clean tree is already red ({', '.join(unscoped)}) — fix that first, "
              f"a self-test on a red tree measures nothing.")
        return 1
    # Regress ONE function through the reader, so nothing on disk or in the database is touched.
    victim = fns[0]
    poisoned = dict.fromkeys([victim])
    poisoned[victim] = re.sub(r"(INTO\s+v_actor[\s\S]{0,400}?);", lambda m: re.sub(
        r"\s*AND\s*\([A-Z]+\.hive_id IS NULL OR hm\.hive_id = [A-Z]+\.hive_id\)", "", m.group(1)) + ";",
        body(victim), count=1, flags=re.I)
    dirty, _ = check(poisoned)
    if victim in dirty:
        print(f"  {GREEN}PASS{RST} — clean tree: {len(fns)} lookups all scoped; with the predicate stripped "
              f"from {victim}, the gate names it. The claim is falsifiable.")
        return 0
    print(f"  {RED}FAIL{RST} — stripping the predicate from {victim} did NOT go red, so this gate cannot "
          f"detect the thing it exists to detect (dirty={dirty}).")
    return 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{BOLD}Audit actor resolution{RST} — the acting worker must be resolved in the AUDITED ROW'S hive")
    unscoped, fns = check()
    if unscoped is None:
        print(f"  {YEL}SKIP{RST} — docker/psql unavailable; nothing asserted.")
        return 0
    print(f"  {DIM}{len(fns)} audit trigger(s) resolve an actor: {', '.join(fns)}{RST}")
    if unscoped:
        for fn in unscoped:
            print(f"  {RED}FAIL{RST} {fn}: the actor lookup does not constrain hm.hive_id, so `LIMIT 1` picks "
                  f"an ARBITRARY membership — a member of two hives can be logged under the wrong hive's "
                  f"worker_name. Add `AND (<row>.hive_id IS NULL OR hm.hive_id = <row>.hive_id)`, the form the "
                  f"other lookups already use.")
        return 1
    print(f"  {GREEN}PASS{RST} every actor lookup constrains the hive, so attribution cannot depend on which "
          f"membership row the planner happens to return first.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
